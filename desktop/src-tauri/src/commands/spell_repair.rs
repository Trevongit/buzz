use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};

/// House English. `colour` is a word. `color` is the miss.
const DEFAULT_SPELL_DICT: &str = "en_AU";

/// If the line has dictionary misspellings, return the same line with those
/// words replaced by the first local suggestion. Empty means "no repair".
#[tauri::command]
pub async fn spell_repair_line(line: String) -> Result<String, String> {
    tokio::task::spawn_blocking(move || repair_line(&line))
        .await
        .map_err(|error| error.to_string())?
}

/// Lowercase misspelled tokens in `line` from the local dictionary.
/// Composer-only underlines; never scans the message wall.
#[tauri::command]
pub async fn spell_check_words(line: String) -> Result<Vec<String>, String> {
    tokio::task::spawn_blocking(move || check_words(&line))
        .await
        .map_err(|error| error.to_string())?
}

/// Ordered dictionary suggestions for each miss in `line`.
/// The first item is the closest spelling. Empty lists stay underlined.
/// Composer-only. Never scans the message wall.
#[tauri::command]
pub async fn spell_suggest_words(line: String) -> Result<HashMap<String, Vec<String>>, String> {
    tokio::task::spawn_blocking(move || suggest_words(&line))
        .await
        .map_err(|error| error.to_string())?
}

/// Remember one composer word in the house list. Later checks treat it as spelled.
/// The word is stored lowercase. Mentions and hyphenated names are not learned here.
#[tauri::command]
pub async fn spell_learn_word(word: String) -> Result<(), String> {
    tokio::task::spawn_blocking(move || learn_word(&word))
        .await
        .map_err(|error| error.to_string())?
}

fn repair_line(line: &str) -> Result<String, String> {
    let word_re = Regex::new(r"[A-Za-z][A-Za-z']{2,}").map_err(|error| error.to_string())?;
    let mut unique = Vec::new();
    for found in word_re.find_iter(line) {
        let word = found.as_str();
        let lower = word.to_ascii_lowercase();
        if !unique.iter().any(|item: &String| item == &lower) {
            unique.push(lower);
        }
    }
    if unique.is_empty() {
        return Ok(String::new());
    }
    let suggestions = drop_learned_first_suggestions(enchant_suggestions(&unique)?);
    let repaired = apply_repairs(line, &suggestions);
    let changed = repaired != line;
    if changed {
        Ok(repaired)
    } else {
        Ok(String::new())
    }
}

fn apply_repairs(line: &str, suggestions: &HashMap<String, String>) -> String {
    let word_re = match Regex::new(r"[A-Za-z][A-Za-z']{2,}") {
        Ok(re) => re,
        Err(_) => return line.to_string(),
    };
    word_re
        .replace_all(line, |caps: &regex::Captures| {
            let Some(found) = caps.get(0) else {
                return String::new();
            };
            let original = found.as_str();
            if protects_name(line, found.start(), found.end()) {
                return original.to_string();
            }
            let key = original.to_ascii_lowercase();
            match suggestions.get(&key) {
                Some(suggestion) if !suggestion.eq_ignore_ascii_case(original) => {
                    match_case(original, suggestion)
                }
                _ => original.to_string(),
            }
        })
        .into_owned()
}

/// Seat names and mentions stay as typed. A hyphen, at-sign, or underscore
/// beside the token means it is part of a name, not a dictionary word.
fn protects_name(line: &str, start: usize, end: usize) -> bool {
    let bytes = line.as_bytes();
    let glue = |byte: u8| matches!(byte, b'-' | b'@' | b'_' | b'.');
    if start > 0 && glue(bytes[start - 1]) {
        return true;
    }
    if end < bytes.len() && glue(bytes[end]) {
        return true;
    }
    if let Some(at) = line[..start].rfind('@') {
        let between = &line[at + 1..start];
        if between
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'))
        {
            return true;
        }
    }
    false
}

fn match_case(original: &str, suggestion: &str) -> String {
    if original.chars().next().is_some_and(char::is_uppercase)
        && original.chars().skip(1).all(|ch| !ch.is_uppercase())
    {
        let mut chars = suggestion.chars();
        match chars.next() {
            Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
            None => suggestion.to_string(),
        }
    } else {
        suggestion.to_string()
    }
}

fn enchant_suggestions(words: &[String]) -> Result<HashMap<String, String>, String> {
    let stdout = enchant_stdout(words)?;
    let mut map = HashMap::new();
    for line in stdout.lines() {
        if let Some(rest) = line.strip_prefix("& ") {
            let (head, suggestions) = rest.split_once(':').unwrap_or((rest, ""));
            let miss = head.split_whitespace().next().unwrap_or("");
            let first = suggestions
                .split(',')
                .next()
                .map(str::trim)
                .filter(|item| !item.is_empty());
            if let Some(suggestion) = first {
                map.insert(miss.to_ascii_lowercase(), suggestion.to_string());
            }
        }
    }
    Ok(map)
}

const MAX_CHECK_CHARS: usize = 2000;
const MAX_CHECK_WORDS: usize = 40;

fn check_words(line: &str) -> Result<Vec<String>, String> {
    let clipped = if line.len() > MAX_CHECK_CHARS {
        &line[..MAX_CHECK_CHARS]
    } else {
        line
    };
    let word_re = Regex::new(r"[A-Za-z][A-Za-z']{2,}").map_err(|error| error.to_string())?;
    let mut unique = Vec::new();
    for found in word_re.find_iter(clipped) {
        let lower = found.as_str().to_ascii_lowercase();
        if !unique.iter().any(|item: &String| item == &lower) {
            unique.push(lower);
        }
        if unique.len() >= MAX_CHECK_WORDS {
            break;
        }
    }
    if unique.is_empty() {
        return Ok(Vec::new());
    }
    let stdout = enchant_stdout(&unique)?;
    Ok(drop_learned_words(parse_enchant_misses(&stdout)))
}

fn learned_wordlist_path() -> Result<PathBuf, String> {
    let home = std::env::var("HOME").map_err(|_| "HOME is unset".to_string())?;
    Ok(PathBuf::from(home).join(".config/enchant/buzz-learned.dic"))
}

/// Line to append, or `None` when the word is already learned or not a word.
fn learned_append(existing: &str, word: &str) -> Result<Option<String>, String> {
    let trimmed = word.trim();
    let word_re = Regex::new(r"^[A-Za-z][A-Za-z']{2,}$").map_err(|error| error.to_string())?;
    if !word_re.is_match(trimmed) {
        return Err("not a learnable word".to_string());
    }
    let lower = trimmed.to_ascii_lowercase();
    if existing
        .lines()
        .any(|line| line.trim().eq_ignore_ascii_case(&lower))
    {
        return Ok(None);
    }
    Ok(Some(lower))
}

fn learn_word(word: &str) -> Result<(), String> {
    let path = learned_wordlist_path()?;
    let existing = fs::read_to_string(&path).unwrap_or_default();
    let Some(line) = learned_append(&existing, word)? else {
        return Ok(());
    };
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|error| error.to_string())?;
    writeln!(file, "{line}").map_err(|error| error.to_string())?;
    Ok(())
}

fn spell_dictionary() -> String {
    spell_dictionary_from(
        std::env::var("BUZZ_SPELL_DICT").ok().as_deref(),
        Some(
            crate::commands::composer_extras::load_prefs()
                .spell_dict
                .as_str(),
        ),
    )
}

fn spell_dictionary_from(env: Option<&str>, extras: Option<&str>) -> String {
    if let Some(value) = env {
        if !value.trim().is_empty() {
            return crate::commands::composer_extras::clamp_spell_dict(value);
        }
    }
    if let Some(value) = extras {
        return crate::commands::composer_extras::clamp_spell_dict(value);
    }
    DEFAULT_SPELL_DICT.to_string()
}

/// Enchant `-p` on this host replaces the system dictionary. Learned words
/// are applied after the parse so suggestions stay on the Australian dict.
fn enchant_args(dict: &str) -> Vec<String> {
    vec![
        "1".to_string(),
        "enchant-2".to_string(),
        "-a".to_string(),
        "-d".to_string(),
        dict.to_string(),
    ]
}

fn learned_words() -> HashSet<String> {
    let Ok(path) = learned_wordlist_path() else {
        return HashSet::new();
    };
    let Ok(existing) = fs::read_to_string(path) else {
        return HashSet::new();
    };
    existing
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(str::to_ascii_lowercase)
        .collect()
}

fn drop_learned_words(misses: Vec<String>) -> Vec<String> {
    let learned = learned_words();
    if learned.is_empty() {
        return misses;
    }
    misses
        .into_iter()
        .filter(|word| !learned.contains(word))
        .collect()
}

fn drop_learned_suggestions(
    mut suggestions: HashMap<String, Vec<String>>,
) -> HashMap<String, Vec<String>> {
    let learned = learned_words();
    if learned.is_empty() {
        return suggestions;
    }
    for word in &learned {
        suggestions.remove(word);
    }
    suggestions
}

fn drop_learned_first_suggestions(
    mut suggestions: HashMap<String, String>,
) -> HashMap<String, String> {
    let learned = learned_words();
    if learned.is_empty() {
        return suggestions;
    }
    for word in &learned {
        suggestions.remove(word);
    }
    suggestions
}

fn enchant_stdout(words: &[String]) -> Result<String, String> {
    let dict = spell_dictionary();
    let mut child = Command::new("timeout")
        .args(enchant_args(&dict))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| error.to_string())?;
    {
        let stdin = child
            .stdin
            .as_mut()
            .ok_or_else(|| "enchant stdin".to_string())?;
        for word in words {
            writeln!(stdin, "{word}").map_err(|error| error.to_string())?;
        }
    }
    let output = child
        .wait_with_output()
        .map_err(|error| error.to_string())?;
    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    if stdout.trim().is_empty() {
        return Ok(String::new());
    }
    Ok(stdout)
}

const MAX_SUGGESTIONS: usize = 5;

fn suggest_words(line: &str) -> Result<HashMap<String, Vec<String>>, String> {
    let clipped = if line.len() > MAX_CHECK_CHARS {
        &line[..MAX_CHECK_CHARS]
    } else {
        line
    };
    let word_re = Regex::new(r"[A-Za-z][A-Za-z']{2,}").map_err(|error| error.to_string())?;
    let mut unique = Vec::new();
    for found in word_re.find_iter(clipped) {
        let lower = found.as_str().to_ascii_lowercase();
        if !unique.iter().any(|item: &String| item == &lower) {
            unique.push(lower);
        }
        if unique.len() >= MAX_CHECK_WORDS {
            break;
        }
    }
    if unique.is_empty() {
        return Ok(HashMap::new());
    }
    let stdout = enchant_stdout(&unique)?;
    Ok(drop_learned_suggestions(parse_enchant_suggestions(&stdout)))
}

fn parse_enchant_suggestions(stdout: &str) -> HashMap<String, Vec<String>> {
    let mut map = HashMap::new();
    for line in stdout.lines() {
        if let Some(rest) = line.strip_prefix("& ") {
            let (head, tail) = rest.split_once(':').unwrap_or((rest, ""));
            let Some(word) = head.split_whitespace().next() else {
                continue;
            };
            let suggestions = tail
                .split(',')
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .take(MAX_SUGGESTIONS)
                .map(str::to_string)
                .collect();
            map.entry(word.to_ascii_lowercase()).or_insert(suggestions);
        } else if let Some(rest) = line.strip_prefix("# ") {
            let Some(word) = rest.split_whitespace().next() else {
                continue;
            };
            map.entry(word.to_ascii_lowercase())
                .or_insert_with(Vec::new);
        }
    }
    map
}

fn parse_enchant_misses(stdout: &str) -> Vec<String> {
    let mut out = Vec::new();
    for line in stdout.lines() {
        let miss = line
            .strip_prefix("& ")
            .or_else(|| line.strip_prefix("# "))
            .and_then(|rest| rest.split_whitespace().next());
        let Some(word) = miss else {
            continue;
        };
        let key = word.to_ascii_lowercase();
        if !out.iter().any(|item: &String| item == &key) {
            out.push(key);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::{
        apply_repairs, drop_learned_suggestions, drop_learned_words, enchant_args, learned_append,
        match_case, parse_enchant_misses, parse_enchant_suggestions, protects_name,
        spell_dictionary_from, suggest_words, DEFAULT_SPELL_DICT,
    };
    use std::collections::HashMap;

    #[test]
    fn title_case_follows_the_typed_word() {
        assert_eq!(match_case("Shouldd", "should"), "Should");
    }

    #[test]
    fn parse_enchant_misses_keeps_ampersand_and_hash_tokens() {
        let stdout = "\
@(#) International Ispell Version 3.1.20 (but really Enchant 2.3.3)
& seee 71 0: seer, see
*
# xyzzy 0
";
        let misses = parse_enchant_misses(stdout);
        assert_eq!(misses, vec!["seee".to_string(), "xyzzy".to_string()]);
    }

    #[test]
    fn parse_enchant_suggestions_keeps_dictionary_order() {
        let stdout = "\
& seee 71 0: seer, see, seed, seep, seem
# xyzzy 0
";
        let map = parse_enchant_suggestions(stdout);
        assert_eq!(
            map.get("seee"),
            Some(&vec![
                "seer".to_string(),
                "see".to_string(),
                "seed".to_string(),
                "seep".to_string(),
                "seem".to_string(),
            ])
        );
        assert_eq!(map.get("xyzzy").map(Vec::len), Some(0));
    }

    #[test]
    fn repair_leaves_seat_names_and_mentions() {
        let mut suggestions = HashMap::new();
        suggestions.insert("grok".to_string(), "frog".to_string());
        suggestions.insert("comms".to_string(), "comes".to_string());
        suggestions.insert("hotdg".to_string(), "hotdog".to_string());
        let line = "@buzz-grok-comms-remote spellinge the hotdg";
        let repaired = apply_repairs(line, &suggestions);
        assert!(repaired.contains("@buzz-grok-comms-remote"));
        assert!(repaired.contains("hotdog"));
        assert!(protects_name(
            line,
            line.find("grok").unwrap(),
            line.find("grok").unwrap() + 4
        ));
    }

    #[test]
    fn learned_append_stores_a_word_once() {
        assert_eq!(
            learned_append("", "Kokoro").expect("word"),
            Some("kokoro".to_string())
        );
        assert_eq!(learned_append("kokoro\n", "KOKORO").expect("dup"), None);
        assert!(learned_append("", "@comms").is_err());
    }

    #[test]
    fn house_dictionary_is_australian_english() {
        assert_eq!(DEFAULT_SPELL_DICT, "en_AU");
        assert_eq!(spell_dictionary_from(None, None), "en_AU");
        assert_eq!(spell_dictionary_from(Some(""), Some("en_US")), "en_US");
        assert_eq!(
            spell_dictionary_from(Some(" en_GB "), Some("en_US")),
            "en_GB"
        );
        assert_eq!(spell_dictionary_from(None, Some("en-US")), "en_US");
    }

    #[test]
    fn enchant_args_keep_the_system_dictionary() {
        let args = enchant_args("en_AU");
        assert_eq!(
            args,
            vec![
                "1".to_string(),
                "enchant-2".to_string(),
                "-a".to_string(),
                "-d".to_string(),
                "en_AU".to_string()
            ]
        );
        assert!(!args.iter().any(|item| item == "-p"));
    }

    #[test]
    fn learned_filter_drops_known_house_words() {
        let misses = vec!["kokoro".to_string(), "abilites".to_string()];
        let empty: HashMap<String, Vec<String>> = HashMap::new();
        assert!(drop_learned_suggestions(empty).is_empty());
        assert_eq!(drop_learned_words(misses.clone()), misses);
        let map = parse_enchant_suggestions(
            "& abilites 4 0: abilities, ability's, ablates, ability\n# colour 0\n",
        );
        assert_eq!(
            map.get("abilites"),
            Some(&vec![
                "abilities".to_string(),
                "ability's".to_string(),
                "ablates".to_string(),
                "ability".to_string(),
            ])
        );
        assert_eq!(map.get("colour").map(Vec::len), Some(0));
    }

    #[test]
    fn live_australian_dict_offers_abilities() {
        let Ok(map) = suggest_words("the abilites of colour") else {
            return;
        };
        if map.is_empty() {
            return;
        }
        assert!(
            !map.contains_key("colour"),
            "colour is Australian English and should not be underlined"
        );
        let list = map
            .get("abilites")
            .expect("abilites is a miss with suggestions");
        assert!(
            list.iter().any(|item| item == "abilities"),
            "expected abilities, got {list:?}"
        );
    }
}
