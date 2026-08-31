//! Local Listen TTS — message hover-bar playback, not huddle audio.
//!
//! Uses a dedicated Pocket pipeline (same construction as voice preview) so
//! Listen never shares the huddle DeviceSink or requires an active huddle.

use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex, OnceLock,
};
use std::time::{Duration, Instant};

use serde::Deserialize;
use tauri::{AppHandle, State};

use crate::app_state::AppState;

use super::agent_tts_routing::normalize_agent_tts_text;
use super::human_floor::HumanFloor;
use super::models;
use super::tts::TtsPipeline;
use super::tts_settings;

const LISTEN_PLAYBACK_TIMEOUT: Duration = Duration::from_secs(180);
const OLLAMA_GENERATE_URL: &str = "http://127.0.0.1:11434/api/generate";
const LISTEN_SUMMARY_MODEL: &str = "gemma3:4b";
/// 180 tokens cut long DMs mid-sentence. 512 is enough for a spoken paragraph.
const LISTEN_SUMMARY_NUM_PREDICT: u32 = 512;
const LISTEN_SUMMARY_TIMEOUT: Duration = Duration::from_secs(90);

struct ListenRuntime {
    pipeline: Arc<TtsPipeline>,
    active: Arc<AtomicBool>,
    cancel: Arc<AtomicBool>,
}

fn listen_runtime() -> &'static Mutex<Option<ListenRuntime>> {
    static RUNTIME: OnceLock<Mutex<Option<ListenRuntime>>> = OnceLock::new();
    RUNTIME.get_or_init(|| Mutex::new(None))
}

pub(crate) fn listen_summary_prompt(text: &str) -> String {
    format!(
        "Rewrite the following Buzz message as spoken prose a person can listen to. Keep names, decisions, and numbers. Use complete sentences and always finish the last sentence. No markdown, no bullets, no preamble.\n\n{text}"
    )
}

/// Drop a token-capped trailing fragment so Pocket does not speak a half sentence.
pub(crate) fn finish_spoken_summary(text: &str) -> String {
    let trimmed = text.split_whitespace().collect::<Vec<_>>().join(" ");
    if trimmed.is_empty() {
        return trimmed;
    }
    let complete = trimmed.ends_with('.')
        || trimmed.ends_with('!')
        || trimmed.ends_with('?')
        || trimmed.ends_with(".”")
        || trimmed.ends_with("!\"")
        || trimmed.ends_with("?\"");
    if complete {
        return trimmed;
    }
    let last_stop = [". ", "! ", "? "]
        .into_iter()
        .filter_map(|mark| trimmed.rfind(mark).map(|index| index + 1))
        .max();
    match last_stop {
        Some(end) => trimmed[..end].trim().to_string(),
        None => trimmed,
    }
}

fn ensure_listen_runtime(app: &AppHandle, state: &AppState) -> Result<ListenRuntime, String> {
    if !models::is_tts_ready() {
        return Err("Voice files are still downloading. Try Listen again shortly.".to_string());
    }
    let model_dir = models::tts_model_dir().ok_or("Pocket voice files are unavailable")?;
    let output_device = state
        .huddle_audio
        .output_device
        .lock()
        .unwrap_or_else(|error| error.into_inner())
        .clone();
    let voice_preferences = state
        .huddle_audio
        .tts
        .lock()
        .map_err(|error| format!("text-to-speech settings lock poisoned: {error}"))?
        .voice_preferences
        .clone();
    let voice_name = tts_settings::pocket_voice_reference(app, &voice_preferences)?;
    let active = Arc::new(AtomicBool::new(false));
    let cancel = Arc::new(AtomicBool::new(false));
    let pipeline = Arc::new(TtsPipeline::new_with_voice(
        model_dir,
        Arc::clone(&active),
        Arc::clone(&cancel),
        HumanFloor::new(),
        &voice_name,
        output_device,
        None,
    )?);
    Ok(ListenRuntime {
        pipeline,
        active,
        cancel,
    })
}

fn runtime_snapshot() -> Result<ListenRuntime, String> {
    listen_runtime()
        .lock()
        .map_err(|error| format!("listen TTS lock poisoned: {error}"))?
        .as_ref()
        .map(|runtime| ListenRuntime {
            pipeline: Arc::clone(&runtime.pipeline),
            active: Arc::clone(&runtime.active),
            cancel: Arc::clone(&runtime.cancel),
        })
        .ok_or_else(|| "Listen TTS pipeline is unavailable".to_string())
}

/// Speak message text through local Pocket TTS. Does not join or broadcast a huddle.
#[tauri::command]
pub async fn speak_listen_text(
    text: String,
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let text = normalize_agent_tts_text(text);
    if text.trim().is_empty() {
        return Err("Nothing to read on this message.".to_string());
    }

    let needs_pipeline = {
        let slot = listen_runtime()
            .lock()
            .map_err(|error| format!("listen TTS lock poisoned: {error}"))?;
        slot.is_none()
    };
    if needs_pipeline {
        let constructed = ensure_listen_runtime(&app, &state)?;
        let mut slot = listen_runtime()
            .lock()
            .map_err(|error| format!("listen TTS lock poisoned: {error}"))?;
        if slot.is_none() {
            *slot = Some(constructed);
        }
    }
    {
        let slot = listen_runtime()
            .lock()
            .map_err(|error| format!("listen TTS lock poisoned: {error}"))?;
        if let Some(runtime) = slot.as_ref() {
            runtime.cancel.store(true, Ordering::Release);
        }
    }

    let runtime = runtime_snapshot()?;
    runtime.cancel.store(false, Ordering::Release);
    runtime
        .pipeline
        .speak(text)
        .map_err(|error| format!("Listen TTS failed: {error}"))?;

    tokio::task::spawn_blocking(move || {
        let started = Instant::now();
        let mut heard_audio = false;
        while started.elapsed() < LISTEN_PLAYBACK_TIMEOUT {
            if runtime.cancel.load(Ordering::Acquire) {
                return Ok(());
            }
            let is_active = runtime.active.load(Ordering::Acquire);
            heard_audio |= is_active;
            if heard_audio && !is_active {
                return Ok(());
            }
            std::thread::sleep(Duration::from_millis(25));
        }
        if heard_audio {
            Ok(())
        } else {
            Err("Listen timed out before audio started. Check Voice settings.".to_string())
        }
    })
    .await
    .map_err(|error| format!("Listen TTS task failed: {error}"))?
}

/// Stop Listen / Follow along Pocket playback. Safe if nothing is playing.
#[tauri::command]
pub fn stop_listen_text() -> Result<(), String> {
    let slot = listen_runtime()
        .lock()
        .map_err(|error| format!("listen TTS lock poisoned: {error}"))?;
    if let Some(runtime) = slot.as_ref() {
        runtime.cancel.store(true, Ordering::Release);
    }
    Ok(())
}

#[derive(Deserialize)]
struct OllamaGenerateResponse {
    response: Option<String>,
    error: Option<String>,
}

/// Rewrite message text into spoken prose via the local Ollama gemma3:4b model.
#[tauri::command]
pub async fn summarize_listen_text(
    text: String,
    state: State<'_, AppState>,
) -> Result<String, String> {
    let text = normalize_agent_tts_text(text);
    if text.trim().is_empty() {
        return Err("Nothing to summarize on this message.".to_string());
    }
    let prompt = listen_summary_prompt(&text);
    let response = state
        .http_client
        .post(OLLAMA_GENERATE_URL)
        .timeout(LISTEN_SUMMARY_TIMEOUT)
        .json(&serde_json::json!({
            "model": LISTEN_SUMMARY_MODEL,
            "prompt": prompt,
            "stream": false,
            "options": { "temperature": 0.2, "num_predict": LISTEN_SUMMARY_NUM_PREDICT }
        }))
        .send()
        .await
        .map_err(|error| {
            format!("Local gemma3:4b is not reachable on 127.0.0.1:11434 ({error})")
        })?;
    if !response.status().is_success() {
        return Err(format!(
            "Local gemma3:4b returned HTTP {}",
            response.status()
        ));
    }
    let payload: OllamaGenerateResponse = response
        .json()
        .await
        .map_err(|error| format!("Local gemma3:4b response was not JSON: {error}"))?;
    if let Some(error) = payload.error.filter(|value| !value.is_empty()) {
        return Err(error);
    }
    let summary = finish_spoken_summary(&payload.response.unwrap_or_default());
    if summary.is_empty() {
        return Err("Local gemma3:4b returned an empty summary.".to_string());
    }
    Ok(summary)
}

#[cfg(test)]
mod tests {
    use super::{finish_spoken_summary, listen_summary_prompt};

    #[test]
    fn summary_prompt_asks_for_spoken_prose() {
        let prompt = listen_summary_prompt("Ship extras tonight.");
        assert!(prompt.contains("spoken prose"));
        assert!(prompt.contains("Ship extras tonight."));
        assert!(prompt.contains("No markdown"));
        assert!(prompt.contains("finish the last sentence"));
    }

    #[test]
    fn finish_drops_a_cut_off_trailing_clause() {
        let spoken = finish_spoken_summary(
            "Origin stays the trunk. Extras is a module pack on top. Listen uses Pocket TTS and then the rewrite was",
        );
        assert_eq!(
            spoken,
            "Origin stays the trunk. Extras is a module pack on top."
        );
    }

    #[test]
    fn finish_keeps_a_complete_last_sentence() {
        let spoken = finish_spoken_summary("Keep names, decisions, and numbers.");
        assert_eq!(spoken, "Keep names, decisions, and numbers.");
    }

    #[test]
    fn stop_without_runtime_is_ok() {
        assert!(super::stop_listen_text().is_ok());
    }
}
