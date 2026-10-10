use serde::Deserialize;
use std::time::Duration;

#[derive(Deserialize)]
struct GhostLlmConfig {
    url: String,
    model: String,
    #[serde(default)]
    key: String,
}

fn config_path() -> std::path::PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join(".buzz-dev/ghost-llm.json")
}

/// Continue a composer draft using the local organ (EMBER / llama.cpp).
/// The API key lives in ~/.buzz-dev/ghost-llm.json, never in git.
#[tauri::command]
pub async fn ghost_complete_local(before: String) -> Result<String, String> {
    let prompt = before.trim();
    if prompt.len() < 8 {
        return Ok(String::new());
    }
    let raw = tokio::fs::read_to_string(config_path())
        .await
        .map_err(|_| "no local llm config".to_string())?;
    let cfg: GhostLlmConfig = serde_json::from_str(&raw).map_err(|error| error.to_string())?;
    if cfg.url.trim().is_empty() {
        return Ok(String::new());
    }
    let client = reqwest::Client::builder()
        .timeout(Duration::from_millis(2500))
        .build()
        .map_err(|error| error.to_string())?;
    let body = serde_json::json!({
        "model": cfg.model,
        "messages": [{
            "role": "user",
            "content": format!(
                "Finish the same sentence with at most eight words. Do not comment. Do not reply. Do not explain. Output only the missing words.\n\n{prompt}"
            )
        }],
        "max_tokens": 16,
        "temperature": 0.1,
        "stream": false
    });
    let mut request = client.post(cfg.url.trim()).json(&body);
    if !cfg.key.is_empty() {
        request = request.bearer_auth(cfg.key.trim());
    }
    let response = request.send().await.map_err(|error| error.to_string())?;
    if !response.status().is_success() {
        return Ok(String::new());
    }
    let payload: serde_json::Value = response.json().await.map_err(|error| error.to_string())?;
    let text = payload["choices"][0]["message"]["content"]
        .as_str()
        .unwrap_or("")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");
    if text.is_empty() || text.len() > 80 {
        return Ok(String::new());
    }
    Ok(if text.starts_with(' ') {
        text
    } else {
        format!(" {text}")
    })
}

/// One clearer paragraph. Same meaning. Repeated bits dropped.
#[tauri::command]
pub async fn paragraph_offer(draft: String) -> Result<String, String> {
    let prompt = draft.split_whitespace().collect::<Vec<_>>().join(" ");
    if prompt.len() < 80 {
        return Ok(String::new());
    }
    let raw = tokio::fs::read_to_string(config_path())
        .await
        .map_err(|_| "no local llm config".to_string())?;
    let cfg: GhostLlmConfig = serde_json::from_str(&raw).map_err(|error| error.to_string())?;
    if cfg.url.trim().is_empty() {
        return Ok(String::new());
    }
    let client = reqwest::Client::builder()
        .timeout(Duration::from_millis(4000))
        .build()
        .map_err(|error| error.to_string())?;
    let body = serde_json::json!({
        "model": cfg.model,
        "messages": [{
            "role": "user",
            "content": format!(
                "Rewrite this paragraph so it keeps the same meaning, is clearer, and drops repeated words. Do not add new facts. Do not comment. Output only the rewritten paragraph.\n\n{prompt}"
            )
        }],
        "max_tokens": 180,
        "temperature": 0.2,
        "stream": false
    });
    let mut request = client.post(cfg.url.trim()).json(&body);
    if !cfg.key.is_empty() {
        request = request.bearer_auth(cfg.key.trim());
    }
    let response = request.send().await.map_err(|error| error.to_string())?;
    if !response.status().is_success() {
        return Ok(String::new());
    }
    let payload: serde_json::Value = response.json().await.map_err(|error| error.to_string())?;
    let text = payload["choices"][0]["message"]["content"]
        .as_str()
        .unwrap_or("")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");
    if text.is_empty() || text.len() > 800 {
        return Ok(String::new());
    }
    if text.eq_ignore_ascii_case(&prompt) {
        return Ok(String::new());
    }
    Ok(text)
}
