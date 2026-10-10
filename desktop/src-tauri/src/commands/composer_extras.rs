use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

const MIN_PAUSE_MS: u64 = 500;
const MAX_PAUSE_MS: u64 = 8_000;
const DEFAULT_PAUSE_MS: u64 = 2_500;
const DEFAULT_SPELL_DICT: &str = "en_AU";
const MIN_SUGGEST: u8 = 1;
const MAX_SUGGEST: u8 = 5;
const DEFAULT_SUGGEST: u8 = 5;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ComposerExtrasPrefs {
    #[serde(default = "default_pause")]
    pub ghost_pause_ms: u64,
    #[serde(default = "default_pause")]
    pub spell_pause_ms: u64,
    #[serde(default = "default_true")]
    pub phrases: bool,
    #[serde(default = "default_true")]
    pub repair: bool,
    #[serde(default = "default_true")]
    pub ember: bool,
    #[serde(default = "default_true")]
    pub paragraph_offer: bool,
    #[serde(default = "default_dict")]
    pub spell_dict: String,
    #[serde(default = "default_true")]
    pub spell_underlines: bool,
    #[serde(default = "default_suggest")]
    pub spell_suggest_count: u8,
    #[serde(default = "default_true")]
    pub spell_tab: bool,
    #[serde(default = "default_true")]
    pub spell_learn: bool,
}

fn default_pause() -> u64 {
    DEFAULT_PAUSE_MS
}

fn default_true() -> bool {
    true
}

fn default_dict() -> String {
    DEFAULT_SPELL_DICT.to_string()
}

fn default_suggest() -> u8 {
    DEFAULT_SUGGEST
}

impl Default for ComposerExtrasPrefs {
    fn default() -> Self {
        Self {
            ghost_pause_ms: DEFAULT_PAUSE_MS,
            spell_pause_ms: DEFAULT_PAUSE_MS,
            phrases: true,
            repair: true,
            ember: true,
            paragraph_offer: true,
            spell_dict: default_dict(),
            spell_underlines: true,
            spell_suggest_count: DEFAULT_SUGGEST,
            spell_tab: true,
            spell_learn: true,
        }
    }
}

fn prefs_path() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".buzz-dev/composer-extras.json")
}

fn clamp_pause(ms: u64) -> u64 {
    ms.clamp(MIN_PAUSE_MS, MAX_PAUSE_MS)
}

pub(crate) fn clamp_spell_dict(value: &str) -> String {
    match value.trim().replace('-', "_").as_str() {
        "en_GB" | "en_gb" => "en_GB".to_string(),
        "en_US" | "en_us" => "en_US".to_string(),
        _ => DEFAULT_SPELL_DICT.to_string(),
    }
}

fn clamp_suggest(count: u8) -> u8 {
    count.clamp(MIN_SUGGEST, MAX_SUGGEST)
}

fn clamp_prefs(prefs: ComposerExtrasPrefs) -> ComposerExtrasPrefs {
    ComposerExtrasPrefs {
        ghost_pause_ms: clamp_pause(prefs.ghost_pause_ms),
        spell_pause_ms: clamp_pause(prefs.spell_pause_ms),
        phrases: prefs.phrases,
        repair: prefs.repair,
        ember: prefs.ember,
        paragraph_offer: prefs.paragraph_offer,
        spell_dict: clamp_spell_dict(&prefs.spell_dict),
        spell_underlines: prefs.spell_underlines,
        spell_suggest_count: clamp_suggest(prefs.spell_suggest_count),
        spell_tab: prefs.spell_tab,
        spell_learn: prefs.spell_learn,
    }
}

pub(crate) fn load_prefs() -> ComposerExtrasPrefs {
    let raw = match fs::read_to_string(prefs_path()) {
        Ok(text) => text,
        Err(_) => return ComposerExtrasPrefs::default(),
    };
    match serde_json::from_str::<ComposerExtrasPrefs>(&raw) {
        Ok(prefs) => clamp_prefs(prefs),
        Err(_) => ComposerExtrasPrefs::default(),
    }
}

/// Live extras knobs from ~/.buzz-dev/composer-extras.json (control-room 8878).
#[tauri::command]
pub async fn composer_extras_prefs() -> Result<ComposerExtrasPrefs, String> {
    tokio::task::spawn_blocking(load_prefs)
        .await
        .map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::{clamp_prefs, ComposerExtrasPrefs, DEFAULT_PAUSE_MS, MAX_PAUSE_MS, MIN_PAUSE_MS};

    #[test]
    fn clamp_prefs_bounds_pause_and_keeps_layers() {
        let prefs = clamp_prefs(ComposerExtrasPrefs {
            ghost_pause_ms: 12,
            spell_pause_ms: 99_000,
            phrases: false,
            repair: true,
            ember: false,
            paragraph_offer: true,
            spell_dict: "en-US".to_string(),
            spell_underlines: false,
            spell_suggest_count: 9,
            spell_tab: false,
            spell_learn: true,
        });
        assert_eq!(prefs.ghost_pause_ms, MIN_PAUSE_MS);
        assert_eq!(prefs.spell_pause_ms, MAX_PAUSE_MS);
        assert!(!prefs.phrases);
        assert!(prefs.repair);
        assert!(!prefs.ember);
        assert!(prefs.paragraph_offer);
        assert_eq!(prefs.spell_dict, "en_US");
        assert!(!prefs.spell_underlines);
        assert_eq!(prefs.spell_suggest_count, 5);
        assert!(!prefs.spell_tab);
        assert!(prefs.spell_learn);
    }

    #[test]
    fn default_prefs_are_a_quiet_pause_with_all_layers() {
        let prefs = ComposerExtrasPrefs::default();
        assert_eq!(prefs.ghost_pause_ms, DEFAULT_PAUSE_MS);
        assert_eq!(prefs.spell_pause_ms, DEFAULT_PAUSE_MS);
        assert!(prefs.phrases && prefs.repair && prefs.ember && prefs.paragraph_offer);
        assert_eq!(prefs.spell_dict, "en_AU");
        assert!(prefs.spell_underlines && prefs.spell_tab && prefs.spell_learn);
        assert_eq!(prefs.spell_suggest_count, 5);
    }
}
