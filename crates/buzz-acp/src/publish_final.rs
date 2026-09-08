//! Opt-in fallback: publish the turn's assistant text when the agent never
//! called `buzz messages send`.
//!
//! Buzz Agent streams the answer as `agent_message_chunk` into Activity. The
//! room/DM only sees a bubble if the model also runs `buzz messages send`.
//! Small local models skip that tool. Origin tracked this as block/buzz#2698;
//! extras-only `--publish-final-if-unsent` / `BUZZ_ACP_PUBLISH_FINAL_IF_UNSENT`
//! is the #5579 fallback, default off so a tool-using agent cannot double-post.
//!
//! Reactions (`reactions add`) do **not** count as a publish. Ember used 👀/💬
//! then kept the answer private; treating a reaction as delivery would re-arm
//! that hole.

use std::collections::{HashMap, HashSet};

use serde_json::Value;
use uuid::Uuid;

/// Cap matches `buzz_sdk` message content size.
pub(crate) const MAX_FALLBACK_CHARS: usize = 65_536;

/// Per-turn buffer of assistant text and detected `messages send` attempts.
#[derive(Debug, Default)]
pub(crate) struct TurnPublishTracker {
    text: String,
    /// Tool-call IDs whose command looks like `buzz messages send`.
    pending_sends: HashSet<String>,
    /// Command text keyed by tool-call id, for `--channel` matching on complete.
    pending_cmds: HashMap<String, String>,
    /// Channel UUIDs that received a successful send this turn.
    /// `None` means a send with no parseable `--channel` (ambient CLI default).
    published_channels: HashSet<Option<Uuid>>,
}

impl TurnPublishTracker {
    pub(crate) fn new() -> Self {
        Self::default()
    }

    pub(crate) fn text(&self) -> &str {
        self.text.trim()
    }

    /// True when a successful `messages send` targeted `channel` or omitted
    /// `--channel`.
    pub(crate) fn published_to(&self, channel: &Uuid) -> bool {
        self.published_channels.contains(&Some(*channel)) || self.published_channels.contains(&None)
    }

    pub(crate) fn ingest(&mut self, update: &Value) {
        let kind = update
            .get("sessionUpdate")
            .and_then(Value::as_str)
            .unwrap_or("");
        match kind {
            "agent_message_chunk" => {
                if let Some(chunk) = update
                    .pointer("/content/text")
                    .and_then(Value::as_str)
                    .filter(|s| !s.is_empty())
                {
                    append_capped(&mut self.text, chunk, MAX_FALLBACK_CHARS);
                }
            }
            "tool_call" => self.note_send_candidate(update),
            "tool_call_update" => {
                self.note_send_candidate(update);
                let Some(id) = tool_call_id(update) else {
                    return;
                };
                if !self.pending_sends.contains(id) {
                    return;
                }
                if tool_call_failed(update) {
                    return;
                }
                if !tool_call_completed(update) {
                    return;
                }
                let channel = self
                    .pending_cmds
                    .get(id)
                    .and_then(|cmd| parse_channel_flag(cmd));
                self.published_channels.insert(channel);
            }
            _ => {}
        }
    }

    fn note_send_candidate(&mut self, update: &Value) {
        let Some(cmd) = command_from_update(update) else {
            return;
        };
        if !is_messages_send(cmd) {
            return;
        }
        let Some(id) = tool_call_id(update) else {
            return;
        };
        self.pending_sends.insert(id.to_string());
        self.pending_cmds.insert(id.to_string(), cmd.to_string());
    }
}

/// Whether the harness should post buffered Activity text as a kind:9.
pub(crate) fn should_publish_final(
    armed: bool,
    clean_end_turn: bool,
    channel_sourced: bool,
    already_published: bool,
    text: &str,
) -> bool {
    armed && clean_end_turn && channel_sourced && !already_published && !text.trim().is_empty()
}

/// Body to post when publish-final fires.
///
/// A 9B Buzz Agent often prints `buzz messages send … --content "Hello"`
/// instead of calling the shell tool. Posting that argv is noise. If the
/// Activity text is a dumped send, unwrap `--content`. If it looks like a
/// send but has no content flag, post nothing. Plain prose is unchanged.
pub(crate) fn fallback_room_content(text: &str) -> String {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    if !is_messages_send(trimmed) {
        return trimmed.to_string();
    }
    parse_content_flag(trimmed).unwrap_or_default()
}

fn parse_content_flag(cmd: &str) -> Option<String> {
    let bytes = cmd.as_bytes();
    let key = b"--content";
    let mut i = 0;
    while i + key.len() <= bytes.len() {
        if bytes[i..].starts_with(key) {
            let after = i + key.len();
            if after < bytes.len() && bytes[after] == b'=' {
                return Some(unquote_content(&cmd[after + 1..]));
            }
            let rest = cmd[after..].trim_start();
            if rest.is_empty() {
                return None;
            }
            return Some(unquote_content(rest));
        }
        i += 1;
    }
    None
}

fn unquote_content(rest: &str) -> String {
    let rest = rest.trim_start();
    let Some(first) = rest.chars().next() else {
        return String::new();
    };
    if first == '"' || first == '\'' {
        let quote = first;
        let mut out = String::new();
        let mut chars = rest.chars();
        chars.next();
        while let Some(c) = chars.next() {
            if c == '\\' {
                if let Some(n) = chars.next() {
                    out.push(n);
                }
                continue;
            }
            if c == quote {
                break;
            }
            out.push(c);
        }
        return out;
    }
    let mut out = String::new();
    for tok in rest.split_whitespace() {
        if tok.starts_with("--") {
            break;
        }
        if !out.is_empty() {
            out.push(' ');
        }
        out.push_str(tok);
    }
    out
}

fn append_capped(dst: &mut String, chunk: &str, cap: usize) {
    let remaining = cap.saturating_sub(dst.chars().count());
    if remaining == 0 {
        return;
    }
    dst.push_str(&chunk.chars().take(remaining).collect::<String>());
}

fn tool_call_id(update: &Value) -> Option<&str> {
    update.get("toolCallId").and_then(Value::as_str)
}

fn command_from_update(update: &Value) -> Option<&str> {
    update
        .pointer("/rawInput/command")
        .and_then(Value::as_str)
        .or_else(|| {
            update
                .pointer("/rawInput/arguments/command")
                .and_then(Value::as_str)
        })
        .or_else(|| {
            update
                .get("content")
                .and_then(Value::as_array)
                .and_then(|items| {
                    items.iter().find_map(|item| {
                        item.get("text")
                            .and_then(Value::as_str)
                            .filter(|t| is_messages_send(t))
                    })
                })
        })
}

fn is_messages_send(cmd: &str) -> bool {
    // Coarse, same family as buzz-agent's reply-guard: inspect the command
    // string, not a shell parse. Do not treat `reactions add` as a send.
    cmd.contains("messages send")
}

fn parse_channel_flag(cmd: &str) -> Option<Uuid> {
    let mut parts = cmd.split_whitespace();
    while let Some(tok) = parts.next() {
        if tok == "--channel" {
            return parts.next().and_then(|v| Uuid::parse_str(v).ok());
        }
        if let Some(v) = tok.strip_prefix("--channel=") {
            return Uuid::parse_str(v).ok();
        }
    }
    None
}

fn tool_call_completed(update: &Value) -> bool {
    matches!(
        update.get("status").and_then(Value::as_str),
        Some("completed" | "success")
    )
}

fn tool_call_failed(update: &Value) -> bool {
    if matches!(
        update.get("status").and_then(Value::as_str),
        Some("failed" | "cancelled" | "error")
    ) {
        return true;
    }
    update
        .pointer("/rawOutput/isError")
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn channel() -> Uuid {
        Uuid::parse_str("b8fa3b6c-665a-41e8-8a73-39bed60b97af").unwrap()
    }

    fn other() -> Uuid {
        Uuid::parse_str("e14d024b-be75-4153-b034-ec46231bcd7c").unwrap()
    }

    #[test]
    fn fallback_fires_on_clean_unsent_channel_turn() {
        assert!(should_publish_final(
            true,
            true,
            true,
            false,
            "10 + 10 equals 20."
        ));
    }

    #[test]
    fn fallback_stays_off_when_disarmed() {
        assert!(!should_publish_final(false, true, true, false, "20"));
    }

    #[test]
    fn fallback_skips_heartbeat_and_non_end_turn() {
        assert!(!should_publish_final(true, true, false, false, "20"));
        assert!(!should_publish_final(true, false, true, false, "20"));
    }

    #[test]
    fn fallback_skips_blank_and_already_sent() {
        assert!(!should_publish_final(true, true, true, false, "  \n"));
        assert!(!should_publish_final(true, true, true, true, "20"));
    }

    #[test]
    fn reaction_is_not_a_send() {
        let mut t = TurnPublishTracker::new();
        t.ingest(&json!({
            "sessionUpdate": "tool_call",
            "toolCallId": "r1",
            "rawInput": { "command": "buzz reactions add --event abc --emoji 👀" }
        }));
        t.ingest(&json!({
            "sessionUpdate": "tool_call_update",
            "toolCallId": "r1",
            "status": "completed"
        }));
        assert!(!t.published_to(&channel()));
    }

    #[test]
    fn successful_send_to_matching_channel_suppresses() {
        let mut t = TurnPublishTracker::new();
        let cmd = format!("buzz messages send --channel {} --content 20", channel());
        t.ingest(&json!({
            "sessionUpdate": "tool_call",
            "toolCallId": "s1",
            "rawInput": { "command": cmd }
        }));
        t.ingest(&json!({
            "sessionUpdate": "tool_call_update",
            "toolCallId": "s1",
            "status": "completed",
            "rawOutput": { "isError": false }
        }));
        assert!(t.published_to(&channel()));
        assert!(!t.published_to(&other()));
    }

    #[test]
    fn failed_send_leaves_fallback_armed() {
        let mut t = TurnPublishTracker::new();
        t.ingest(&json!({
            "sessionUpdate": "agent_message_chunk",
            "content": { "text": "20" }
        }));
        t.ingest(&json!({
            "sessionUpdate": "tool_call",
            "toolCallId": "s1",
            "rawInput": { "command": format!("buzz messages send --channel {} --content 20", channel()) }
        }));
        t.ingest(&json!({
            "sessionUpdate": "tool_call_update",
            "toolCallId": "s1",
            "status": "completed",
            "rawOutput": { "isError": true }
        }));
        assert!(!t.published_to(&channel()));
        assert!(should_publish_final(
            true,
            true,
            true,
            t.published_to(&channel()),
            t.text()
        ));
    }

    #[test]
    fn send_without_channel_flag_counts_as_ambient_publish() {
        let mut t = TurnPublishTracker::new();
        t.ingest(&json!({
            "sessionUpdate": "tool_call",
            "toolCallId": "s1",
            "rawInput": { "command": "buzz messages send --content 20" }
        }));
        t.ingest(&json!({
            "sessionUpdate": "tool_call_update",
            "toolCallId": "s1",
            "status": "completed"
        }));
        assert!(t.published_to(&channel()));
    }

    #[test]
    fn buffers_chunks_and_caps() {
        let mut t = TurnPublishTracker::new();
        t.ingest(&json!({
            "sessionUpdate": "agent_message_chunk",
            "content": { "text": "10 + 10 " }
        }));
        t.ingest(&json!({
            "sessionUpdate": "agent_message_chunk",
            "content": { "text": "equals 20." }
        }));
        assert_eq!(t.text(), "10 + 10 equals 20.");

        let mut big = TurnPublishTracker::new();
        let chunk = "x".repeat(MAX_FALLBACK_CHARS + 50);
        big.ingest(&json!({
            "sessionUpdate": "agent_message_chunk",
            "content": { "text": chunk }
        }));
        assert_eq!(big.text().chars().count(), MAX_FALLBACK_CHARS);
    }

    #[test]
    fn echo_quoting_send_still_matches_coarse_detector() {
        // Same known limit as buzz-agent's reply-guard: quoted text matches.
        assert!(is_messages_send(r#"echo "buzz messages send""#));
        assert!(!is_messages_send("buzz reactions add --emoji 💬"));
    }

    #[test]
    fn unwraps_dumped_send_argv_to_quoted_content() {
        let dumped = r#"buzz messages send --channel 9140aca4-ac29-44cb-9a20-ddee02aece91 --content "Hello. I'm EMBER, a small on-machine check running qwen3.5:9b on Intel Arc via llama.cpp SYCL." --mention 5a757911b9df05fcd3ff2bf44ace1125c14553c79e7bc9653150873572122cc3"#;
        assert_eq!(
            fallback_room_content(dumped),
            "Hello. I'm EMBER, a small on-machine check running qwen3.5:9b on Intel Arc via llama.cpp SYCL."
        );
    }

    #[test]
    fn unwraps_equals_and_single_quoted_content() {
        assert_eq!(
            fallback_room_content(r#"buzz messages send --content='hi there'"#),
            "hi there"
        );
        assert_eq!(
            fallback_room_content("buzz messages send --content hello"),
            "hello"
        );
    }

    #[test]
    fn dumped_send_without_content_posts_nothing() {
        assert_eq!(
            fallback_room_content(
                "buzz messages send --channel 9140aca4-ac29-44cb-9a20-ddee02aece91"
            ),
            ""
        );
        assert!(!should_publish_final(
            true,
            true,
            true,
            false,
            &fallback_room_content("buzz messages send --channel x")
        ));
    }

    #[test]
    fn plain_prose_is_unchanged() {
        assert_eq!(
            fallback_room_content("Hello. I'm EMBER on qwen3.5:9b."),
            "Hello. I'm EMBER on qwen3.5:9b."
        );
    }
}
