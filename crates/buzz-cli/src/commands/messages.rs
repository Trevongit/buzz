use buzz_sdk::{DeleteMessageOptions, DiffMeta, ThreadRef, VoteDirection};
use nostr::PublicKey;
use uuid::Uuid;

use crate::client::{normalize_events, normalize_write_response, BuzzClient};
use crate::error::CliError;
use crate::validate::{
    infer_language, parse_event_id, parse_uuid, read_or_stdin, truncate_diff,
    validate_content_size, validate_hex64, validate_uuid, MAX_DIFF_BYTES,
};
use buzz_sdk::mentions::{
    extract_at_mentions_with_known, extract_nostr_uris, strip_code_regions, MENTION_CAP,
};

/// Extract the thread root event ID from a Nostr tag array.
///
/// Parses `"e"` tags with NIP-10 markers:
/// - If a `"root"` marker exists, returns that event ID.
/// - Otherwise, if only a `"reply"` marker exists, returns the reply target
///   (a direct reply's parent IS the root, and nested replies need that root
///   to thread correctly).
/// - If no thread markers exist, returns `None` (parent is a top-level message,
///   so it is itself the root).
fn find_root_from_tags(tags: &serde_json::Value) -> Option<String> {
    fn valid_event_id(s: &str) -> bool {
        s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit())
    }
    let arr = tags.as_array()?;
    let mut root = None;
    let mut reply = None;
    for tag in arr {
        let Some(parts) = tag.as_array() else {
            continue;
        };
        if parts.len() >= 4 && parts[0].as_str() == Some("e") {
            // Defensively ignore malformed marker values so a bad tag on the
            // parent event can't block the reply — fall back to root == parent.
            let id = parts[1].as_str().filter(|s| valid_event_id(s));
            match (parts[3].as_str(), id) {
                (Some("root"), Some(id)) => root = Some(id.to_string()),
                (Some("reply"), Some(id)) => reply = Some(id.to_string()),
                _ => {}
            }
        }
    }
    root.or(reply)
}

/// Build a `ThreadRef` for a reply, given the immediate parent's event ID.
///
/// Fetches the parent event from the relay and inspects its NIP-10 `e` tags to
/// determine the thread root:
/// - Direct reply (parent is top-level): `root == parent`.
/// - Nested reply: `root` is the parent's own root marker; `parent` is unchanged.
///
/// Ensures CLI-sent replies thread correctly using the same NIP-10 logic.
async fn resolve_thread_ref(
    client: &BuzzClient,
    parent_event_id: &str,
) -> Result<ThreadRef, CliError> {
    let parent_eid = parse_event_id(parent_event_id)?;
    let filter = serde_json::json!({ "ids": [parent_event_id], "limit": 1 });
    let raw = client.query(&filter).await?;
    let events: serde_json::Value = serde_json::from_str(&raw)
        .map_err(|e| CliError::Other(format!("failed to parse query response: {e}")))?;
    let event = events
        .as_array()
        .and_then(|a| a.first())
        .ok_or_else(|| CliError::Other(format!("parent event {parent_event_id} not found")))?;
    let tags = event
        .get("tags")
        .cloned()
        .unwrap_or(serde_json::Value::Null);

    let root_eid = match find_root_from_tags(&tags) {
        Some(root_hex) if root_hex != parent_event_id => parse_event_id(&root_hex)?,
        _ => parent_eid,
    };

    Ok(ThreadRef {
        root_event_id: root_eid,
        parent_event_id: parent_eid,
    })
}

/// Resolve the channel UUID for an event by querying for it via POST /query.
/// Extracts the `h` tag value from the returned event's tags.
async fn resolve_channel_id(client: &BuzzClient, event_id: &str) -> Result<Uuid, CliError> {
    let filter = serde_json::json!({
        "ids": [event_id]
    });
    let raw = client.query(&filter).await?;
    let events: serde_json::Value = serde_json::from_str(&raw)
        .map_err(|e| CliError::Other(format!("failed to parse query response: {e}")))?;
    let arr = events
        .as_array()
        .ok_or_else(|| CliError::Other("query response is not an array".into()))?;
    let event = arr
        .first()
        .ok_or_else(|| CliError::Other(format!("event {event_id} not found")))?;
    let tags = event
        .get("tags")
        .and_then(|t| t.as_array())
        .ok_or_else(|| CliError::Other("event missing 'tags' field".into()))?;
    for tag in tags {
        if let Some(arr) = tag.as_array() {
            if arr.first().and_then(|v| v.as_str()) == Some("h") {
                if let Some(uuid_str) = arr.get(1).and_then(|v| v.as_str()) {
                    return Uuid::parse_str(uuid_str).map_err(|_| {
                        CliError::Other(format!("event h-tag is not a valid UUID: {uuid_str}"))
                    });
                }
            }
        }
    }
    Err(CliError::Other(format!(
        "event {event_id} has no h-tag — cannot determine channel"
    )))
}

fn resolve_names_to_pubkeys(
    names: &[String],
    name_to_pubkeys: &std::collections::HashMap<String, Vec<String>>,
    has_explicit_mentions: bool,
) -> Result<Vec<String>, CliError> {
    let mut resolved = Vec::new();
    for name in names {
        match name_to_pubkeys
            .get(name)
            .map(Vec::as_slice)
            .unwrap_or_default()
        {
            [pubkey] => resolved.push(pubkey.clone()),
            [] if has_explicit_mentions => {}
            [] => {
                return Err(CliError::Usage(format!(
                    "mention '@{name}' does not match a current channel member; retry with --mention <pubkey>"
                )))
            }
            _ if has_explicit_mentions => {}
            candidates => {
                return Err(CliError::Usage(format!(
                    "mention '@{name}' is ambiguous; candidates: {}. Retry with --mention <pubkey>",
                    candidates.join(", ")
                )))
            }
        }
    }
    Ok(resolved)
}

/// Resolve mention text against the channel membership snapshot.
///
/// Returns both the current member set and uniquely name-resolved pubkeys.
/// Lookup failures are fatal when mention processing is requested: publishing
/// visible mention text without its intended `p` tag is worse than not sending.
async fn resolve_content_mentions(
    client: &BuzzClient,
    channel_id: &str,
    content: &str,
    has_explicit_mentions: bool,
) -> Result<(Vec<String>, Vec<String>), CliError> {
    let stripped = strip_code_regions(content);
    if !stripped.contains('@') && !has_explicit_mentions {
        return Ok((vec![], vec![]));
    }

    let members_filter = serde_json::json!({
        "kinds": [39002],
        "#d": [channel_id],
        "limit": 1,
    });
    let member_pubkeys = fetch_member_pubkeys(client, &members_filter)
        .await
        .ok_or_else(|| {
            CliError::Other("could not load channel membership for mention preflight".into())
        })?;

    if !stripped.contains('@') {
        return Ok((member_pubkeys, vec![]));
    }

    let profiles_filter = serde_json::json!({
        "kinds": [0],
        "authors": member_pubkeys,
        "limit": member_pubkeys.len(),
    });
    let profile_events = fetch_events(client, &profiles_filter)
        .await
        .ok_or_else(|| {
            CliError::Other("could not load member profiles for mention resolution".into())
        })?;

    let mut name_to_pubkeys: std::collections::HashMap<String, Vec<String>> =
        std::collections::HashMap::new();
    let mut display_names = Vec::new();
    for e in &profile_events {
        let Some(pubkey) = e.get("pubkey").and_then(|v| v.as_str()) else {
            continue;
        };
        let Some(content_json) = e.get("content").and_then(|v| v.as_str()) else {
            continue;
        };
        let Ok(v) = serde_json::from_str::<serde_json::Value>(content_json) else {
            continue;
        };
        let Some(name) = v
            .get("display_name")
            .or_else(|| v.get("name"))
            .and_then(|n| n.as_str())
            .filter(|n| !n.is_empty())
        else {
            continue;
        };
        name_to_pubkeys
            .entry(name.to_ascii_lowercase())
            .or_default()
            .push(pubkey.to_string());
        display_names.push(name.to_string());
    }

    let known_refs: Vec<&str> = display_names.iter().map(String::as_str).collect();
    let names = extract_at_mentions_with_known(&stripped, &known_refs);
    let resolved = resolve_names_to_pubkeys(&names, &name_to_pubkeys, has_explicit_mentions)?;
    Ok((member_pubkeys, resolved))
}

fn normalize_explicit_mentions(values: &[String]) -> Result<Vec<String>, CliError> {
    let mut normalized = Vec::new();
    for value in values {
        let pubkey = PublicKey::parse(value.trim())
            .map_err(|_| CliError::Usage(format!("invalid --mention pubkey: {value}")))?;
        let hex = pubkey.to_hex();
        if !normalized.contains(&hex) {
            normalized.push(hex);
        }
    }
    if normalized.len() > MENTION_CAP {
        return Err(CliError::Usage(format!(
            "too many --mention values (max {MENTION_CAP})"
        )));
    }
    Ok(normalized)
}

fn merge_message_mentions(
    explicit: &[String],
    uri_pubkeys: &[String],
    auto_resolved: &[String],
) -> Result<Vec<String>, CliError> {
    let mut mentions = Vec::new();
    for pubkey in explicit
        .iter()
        .chain(uri_pubkeys.iter())
        .chain(auto_resolved.iter())
    {
        if !mentions.contains(pubkey) {
            mentions.push(pubkey.clone());
        }
    }
    if mentions.len() > MENTION_CAP {
        return Err(CliError::Usage(format!(
            "too many unique message mentions (max {MENTION_CAP})"
        )));
    }
    Ok(mentions)
}

fn missing_members(mentions: &[String], members: &[String]) -> Vec<String> {
    let members: std::collections::HashSet<&str> = members.iter().map(String::as_str).collect();
    mentions
        .iter()
        .filter(|pk| !members.contains(pk.as_str()))
        .cloned()
        .collect()
}

fn event_mention_pubkeys(event: &nostr::Event) -> Vec<String> {
    event
        .tags
        .iter()
        .filter_map(|tag| {
            let parts = tag.as_slice();
            (parts.first().map(String::as_str) == Some("p"))
                .then(|| parts.get(1).cloned())
                .flatten()
        })
        .collect()
}

/// Fetch raw events for `filter` via the relay's `/query` endpoint.
/// Returns `None` on any I/O or parse failure.
async fn fetch_events(
    client: &BuzzClient,
    filter: &serde_json::Value,
) -> Option<Vec<serde_json::Value>> {
    let raw = client.query(filter).await.ok()?;
    let parsed: serde_json::Value = serde_json::from_str(&raw).ok()?;
    parsed.as_array().cloned()
}

/// Extract member pubkeys (the `p` tag values) from a single 39002 event.
async fn fetch_member_pubkeys(
    client: &BuzzClient,
    filter: &serde_json::Value,
) -> Option<Vec<String>> {
    let events = fetch_events(client, filter).await?;
    Some(parse_member_pubkeys(events.first()?))
}

/// Parse member pubkeys from a kind 39002 event JSON value.
///
/// Filters and canonicalizes via `nostr::PublicKey::from_hex` — matching
/// MCP's typed-Nostr behavior so both surfaces accept exactly the same
/// pubkeys. Pure helper, split out for testing.
fn parse_member_pubkeys(event: &serde_json::Value) -> Vec<String> {
    let Some(tags) = event.get("tags").and_then(|t| t.as_array()) else {
        return vec![];
    };
    tags.iter()
        .filter_map(|t| {
            let arr = t.as_array()?;
            if arr.first()?.as_str()? != "p" {
                return None;
            }
            let pk = arr.get(1)?.as_str()?;
            PublicKey::from_hex(pk).ok().map(|k| k.to_hex())
        })
        .collect()
}

fn format_events(normalized: &str, format: &crate::OutputFormat) -> String {
    match format {
        crate::OutputFormat::Compact => {
            let events: Vec<serde_json::Value> =
                serde_json::from_str(normalized).unwrap_or_default();
            let compact: Vec<serde_json::Value> = events
                .iter()
                .map(|e| {
                    serde_json::json!({
                        "id": e.get("id").cloned().unwrap_or_default(),
                        "content": e.get("content").cloned().unwrap_or_default(),
                        "created_at": e.get("created_at").cloned().unwrap_or_default(),
                    })
                })
                .collect();
            serde_json::to_string(&compact).unwrap_or_default()
        }
        crate::OutputFormat::Json => normalized.to_string(),
    }
}

pub async fn cmd_get_messages(
    client: &BuzzClient,
    channel_id: &str,
    limit: Option<u32>,
    before: Option<i64>,
    since: Option<i64>,
    kinds: Option<&str>,
    format: &crate::OutputFormat,
) -> Result<(), CliError> {
    validate_uuid(channel_id)?;
    let limit = limit.unwrap_or(50).min(200);

    let mut filter = serde_json::json!({
        "kinds": [9, 40002, 40008, 45001, 45003],
        "#h": [channel_id],
        "limit": limit
    });

    // If specific kinds requested, override
    if let Some(k) = kinds {
        let kind_list: Vec<u64> = k.split(',').filter_map(|s| s.trim().parse().ok()).collect();
        if !kind_list.is_empty() {
            filter["kinds"] = serde_json::json!(kind_list);
        }
    }

    if let Some(b) = before {
        filter["until"] = serde_json::json!(b);
    }
    if let Some(s) = since {
        filter["since"] = serde_json::json!(s);
    }

    let resp = client.query(&filter).await?;
    let mut events: Vec<serde_json::Value> = serde_json::from_str(&resp).unwrap_or_default();
    events.sort_by_key(|e| e.get("created_at").and_then(|v| v.as_u64()).unwrap_or(0));
    let normalized = normalize_events(&events);
    println!("{}", format_events(&normalized, format));
    Ok(())
}

pub async fn cmd_get_thread(
    client: &BuzzClient,
    channel_id: &str,
    event_id: &str,
    limit: Option<u32>,
    depth_limit: Option<u32>,
    format: &crate::OutputFormat,
) -> Result<(), CliError> {
    validate_uuid(channel_id)?;
    validate_hex64(event_id)?;
    let limit = limit.unwrap_or(100).min(500);

    // Two filters ORed in a single HTTP call:
    // 1. Replies referencing this event via e-tag (no kind restriction)
    // 2. The root event itself by ID
    let mut reply_filter = serde_json::json!({
        "kinds": [9, 40002, 40003, 40008, 45003],
        "#h": [channel_id],
        "#e": [event_id],
        "limit": limit
    });
    if let Some(d) = depth_limit {
        reply_filter["depth_limit"] = serde_json::json!(d);
    }
    let root_filter = serde_json::json!({
        "ids": [event_id],
        "limit": 1
    });
    let resp = client.query_multi(&[reply_filter, root_filter]).await?;
    let mut events: Vec<serde_json::Value> = serde_json::from_str(&resp).unwrap_or_default();
    events.sort_by_key(|e| e.get("created_at").and_then(|v| v.as_u64()).unwrap_or(0));
    let normalized = normalize_events(&events);
    println!("{}", format_events(&normalized, format));
    Ok(())
}

pub async fn cmd_search(
    client: &BuzzClient,
    query: Option<&str>,
    author: Option<&str>,
    since: Option<i64>,
    limit: Option<u32>,
    format: &crate::OutputFormat,
) -> Result<(), CliError> {
    if query.is_none() && author.is_none() {
        return Err(CliError::Usage(
            "at least one of --query or --author is required".into(),
        ));
    }
    let limit = limit.unwrap_or(20).min(100);

    let author_hex = match author {
        Some(a) => Some(resolve_author(client, a).await?),
        None => None,
    };

    let mut filter = serde_json::json!({
        "kinds": [9, 40002, 45001, 45003],
        "limit": limit
    });
    if let Some(q) = query {
        filter["search"] = serde_json::json!(q);
    }
    if let Some(ref pk) = author_hex {
        filter["authors"] = serde_json::json!([pk]);
    }
    if let Some(s) = since {
        filter["since"] = serde_json::json!(s);
    }
    let resp = client.query(&filter).await?;
    let mut events: Vec<serde_json::Value> = serde_json::from_str(&resp).unwrap_or_default();
    // The full-text path returns relevance order; a pure author/time query has
    // no relevance, so present newest-first like `messages get`.
    if query.is_none() {
        events.sort_by_key(|e| {
            std::cmp::Reverse(e.get("created_at").and_then(|v| v.as_u64()).unwrap_or(0))
        });
    }
    let normalized = normalize_events(&events);
    println!("{}", format_events(&normalized, format));
    Ok(())
}

/// Resolve an `--author` value to a 64-char hex pubkey.
///
/// Accepts, in order of precedence: 64-char hex (validated), an `npub1…`
/// bech32 key, or a display name resolved via NIP-50 profile search. A name
/// must match exactly one user (case-insensitive, on `display_name` or
/// `name`) — ambiguity is an error listing the candidates rather than a
/// silent mix of authors.
async fn resolve_author(client: &BuzzClient, author: &str) -> Result<String, CliError> {
    let author = author.trim();
    if author.len() == 64 && author.chars().all(|c| c.is_ascii_hexdigit()) {
        return Ok(author.to_ascii_lowercase());
    }
    if author.starts_with("npub1") {
        return nostr::PublicKey::parse(author)
            .map(|pk| pk.to_hex())
            .map_err(|_| CliError::Usage(format!("invalid npub: {author}")));
    }

    // Display name → NIP-50 search on kind:0, exact case-insensitive match.
    let filter = serde_json::json!({
        "kinds": [0],
        "search": author,
        "limit": 100
    });
    let raw = client.query(&filter).await?;
    let events: Vec<serde_json::Value> = serde_json::from_str(&raw).unwrap_or_default();
    let mut matches = match_profiles_by_name(&events, author);
    match matches.len() {
        0 => Err(CliError::Usage(format!(
            "no user found with name '{author}' — pass a hex pubkey or npub instead"
        ))),
        1 => Ok(matches.remove(0).0),
        _ => {
            // Cap the candidate listing — some names are shared by dozens of
            // users, and an unbounded list turns the error into a wall of text.
            let shown = 5.min(matches.len());
            let mut listing: Vec<String> = matches[..shown]
                .iter()
                .map(|(pk, name)| format!("{name} ({pk})"))
                .collect();
            if matches.len() > shown {
                listing.push(format!("… and {} more", matches.len() - shown));
            }
            Err(CliError::Usage(format!(
                "name '{author}' is ambiguous — matches: {}. Pass a pubkey instead",
                listing.join(", ")
            )))
        }
    }
}

/// Exact case-insensitive profile match on `display_name` or `name` across
/// kind:0 events. Returns deduped `(pubkey, shown name)` pairs. Pure so the
/// name-resolution semantics are unit-testable without a relay.
fn match_profiles_by_name(events: &[serde_json::Value], name: &str) -> Vec<(String, String)> {
    let lower = name.to_ascii_lowercase();
    let mut matches: Vec<(String, String)> = Vec::new();
    for e in events {
        let Some(pubkey) = e.get("pubkey").and_then(|v| v.as_str()) else {
            continue;
        };
        let Some(content) = e
            .get("content")
            .and_then(|v| v.as_str())
            .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok())
        else {
            continue;
        };
        let display_name = content
            .get("display_name")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let plain_name = content.get("name").and_then(|v| v.as_str()).unwrap_or("");
        if display_name.to_ascii_lowercase() == lower || plain_name.to_ascii_lowercase() == lower {
            let shown = if display_name.is_empty() {
                plain_name
            } else {
                display_name
            };
            matches.push((pubkey.to_string(), shown.to_string()));
        }
    }
    matches.sort();
    matches.dedup();
    matches
}

pub struct SendMessageParams {
    pub channel_id: String,
    pub content: String,
    pub kind: Option<u16>,
    pub reply_to: Option<String>,
    pub broadcast: bool,
    pub files: Vec<String>,
    pub mentions: Vec<String>,
}

pub async fn cmd_send_message(
    client: &BuzzClient,
    mut p: SendMessageParams,
) -> Result<(), CliError> {
    // Allow '-' to read content from stdin. This keeps callers from having to
    // jam shell-metacharacter-heavy text (backticks, $vars, etc.) through argv
    // quoting — the source of countless self-inflicted command-substitution
    // bugs for agent and human users alike.
    p.content = read_or_stdin(&p.content)?;
    validate_content_size(&p.content)?;
    if let Some(ref r) = p.reply_to {
        validate_hex64(r)?;
    }
    let channel_uuid = parse_uuid(&p.channel_id)?;

    let explicit_mentions = normalize_explicit_mentions(&p.mentions)?;
    let stripped = strip_code_regions(&p.content);
    let uri_pubkeys = extract_nostr_uris(&stripped);
    // Supplying any identity explicitly authorizes unresolved or ambiguous @Name text
    // as presentation-only, matching Desktop's separate visible-label and p-tag model.
    // Uniquely resolvable member names still add their own p-tags; callers must supply
    // every intended identity whose visible label cannot be resolved uniquely.
    let has_explicit_mentions = !explicit_mentions.is_empty() || !uri_pubkeys.is_empty();
    let (member_pubkeys, auto_resolved) =
        resolve_content_mentions(client, &p.channel_id, &p.content, has_explicit_mentions).await?;
    let mention_pubkeys = merge_message_mentions(&explicit_mentions, &uri_pubkeys, &auto_resolved)?;

    let missing = missing_members(&mention_pubkeys, &member_pubkeys);
    if !missing.is_empty() {
        return Err(CliError::Usage(
            serde_json::json!({
                "message": "mentioned pubkeys are not channel members; add them explicitly before retrying",
                "missing_member_pubkeys": missing,
                "add_member_command": format!("buzz channels add-member --channel {} --pubkey <pubkey> --role <member|bot>", p.channel_id),
            })
            .to_string(),
        ));
    }

    // Upload files and build imeta tags. Markdown form follows Desktop:
    // images/video as inline media; generic files (zip/pdf/…) as plain links
    // so FileCard can render download cards instead of broken images.
    let mut media_tags: Vec<Vec<String>> = Vec::new();
    let mut media_content = String::new();
    for file_path in &p.files {
        let desc = client
            .upload_file(file_path)
            .await
            .map_err(|e| CliError::Other(format!("upload failed for {file_path}: {e}")))?;
        let basename = std::path::Path::new(file_path)
            .file_name()
            .and_then(|s| s.to_str());
        media_tags.push(match basename {
            Some(name) => crate::client::build_imeta_tag_with_filename(&desc, Some(name)),
            None => crate::client::build_imeta_tag(&desc),
        });
        media_content.push_str(&crate::client::format_attachment_markdown(file_path, &desc));
    }
    let final_content = if media_content.is_empty() {
        p.content.clone()
    } else {
        format!("{}{media_content}", p.content)
    };

    // Build thread ref if replying. `--reply-to` is the immediate parent; the
    // thread root is derived from the parent's NIP-10 tags via the relay.
    let thread_ref = if let Some(ref r) = p.reply_to {
        Some(resolve_thread_ref(client, r).await?)
    } else {
        None
    };

    let mention_refs: Vec<&str> = mention_pubkeys.iter().map(String::as_str).collect();

    let builder = match p.kind {
        Some(45001) => {
            buzz_sdk::build_forum_post(channel_uuid, &final_content, &mention_refs, &media_tags)
                .map_err(|e| CliError::Other(format!("build_forum_post failed: {e}")))?
        }
        Some(45003) => {
            let tr = thread_ref.as_ref().ok_or_else(|| {
                CliError::Usage("--reply-to is required for forum comments (kind 45003)".into())
            })?;
            buzz_sdk::build_forum_comment(
                channel_uuid,
                &final_content,
                tr,
                &mention_refs,
                &media_tags,
            )
            .map_err(|e| CliError::Other(format!("build_forum_comment failed: {e}")))?
        }
        None | Some(9) => buzz_sdk::build_message(
            channel_uuid,
            &final_content,
            thread_ref.as_ref(),
            &mention_refs,
            p.broadcast,
            &media_tags,
        )
        .map_err(|e| CliError::Other(format!("build_message failed: {e}")))?,
        Some(k) => {
            return Err(CliError::Usage(format!(
                "--kind {k} is not supported (use 9, 45001, or 45003)"
            )))
        }
    };

    let event = client.sign_event(builder)?;
    let emitted_mentions = event_mention_pubkeys(&event);
    let resp = client.submit_event(event).await?;
    let mut output: serde_json::Value = serde_json::from_str(&normalize_write_response(&resp))
        .unwrap_or_else(|_| serde_json::json!({ "response": resp }));
    if let Some(object) = output.as_object_mut() {
        object.insert(
            "mention_pubkeys".into(),
            serde_json::json!(emitted_mentions),
        );
    }
    println!("{output}");
    Ok(())
}

pub struct SendDiffParams {
    pub channel_id: String,
    pub diff: String,
    pub repo_url: String,
    pub commit_sha: String,
    pub file_path: Option<String>,
    pub parent_commit_sha: Option<String>,
    pub source_branch: Option<String>,
    pub target_branch: Option<String>,
    pub pr_number: Option<u32>,
    pub language: Option<String>,
    pub description: Option<String>,
    pub reply_to: Option<String>,
}

pub async fn cmd_send_diff_message(client: &BuzzClient, p: SendDiffParams) -> Result<(), CliError> {
    if let Some(r) = &p.reply_to {
        validate_hex64(r)?;
    }

    // Branch pairing: both or neither
    match (&p.source_branch, &p.target_branch) {
        (Some(_), None) | (None, Some(_)) => {
            return Err(CliError::Usage(
                "--source-branch and --target-branch must both be provided or both omitted".into(),
            ));
        }
        _ => {}
    }

    let channel_uuid = parse_uuid(&p.channel_id)?;

    // Read diff from stdin if "--diff -"
    let diff_content = read_or_stdin(&p.diff)?;

    // Truncate at 60 KiB hunk boundary
    let (diff, truncated) = truncate_diff(&diff_content, MAX_DIFF_BYTES);

    // Language inference: explicit flag wins, then infer from file path
    let language = p
        .language
        .clone()
        .or_else(|| p.file_path.as_deref().and_then(infer_language));

    // NIP-31 alt tag
    let alt = match (&p.file_path, &p.description) {
        (Some(fp), Some(desc)) => format!("Diff: {} — {}", fp, desc),
        (Some(fp), None) => format!("Diff: {}", fp),
        _ => "Diff".to_string(),
    };

    // `--reply-to` is the immediate parent; the thread root is derived from
    // the parent's NIP-10 tags via the relay.
    let thread_ref = if let Some(r) = &p.reply_to {
        Some(resolve_thread_ref(client, r).await?)
    } else {
        None
    };

    let branch = match (&p.source_branch, &p.target_branch) {
        (Some(src), Some(tgt)) => Some((src.clone(), tgt.clone())),
        _ => None,
    };

    let diff_meta = DiffMeta {
        repo_url: p.repo_url.clone(),
        commit_sha: p.commit_sha.clone(),
        file_path: p.file_path.clone(),
        parent_commit: p.parent_commit_sha.clone(),
        branch,
        pr_number: p.pr_number,
        language,
        description: p.description.clone(),
        truncated,
        alt_text: Some(alt),
    };

    let builder =
        buzz_sdk::build_diff_message(channel_uuid, &diff, &diff_meta, thread_ref.as_ref())
            .map_err(|e| CliError::Other(format!("build_diff_message failed: {e}")))?;

    let event = client.sign_event(builder)?;

    let resp = client.submit_event(event).await?;
    println!("{}", normalize_write_response(&resp));
    Ok(())
}

pub async fn cmd_delete_message(
    client: &BuzzClient,
    event_id: &str,
    action_id: Option<Uuid>,
    reason_code: Option<&str>,
    public_reason: Option<&str>,
) -> Result<(), CliError> {
    validate_hex64(event_id)?;

    // Resolve channel_id from the event's h-tag
    let channel_uuid = resolve_channel_id(client, event_id).await?;
    let target_eid = parse_event_id(event_id)?;

    let builder = buzz_sdk::build_delete_message_with_options(
        channel_uuid,
        target_eid,
        DeleteMessageOptions {
            action_id,
            reason_code,
            public_reason,
        },
    )
    .map_err(|e| CliError::Other(format!("build_delete_message failed: {e}")))?;

    let event = client.sign_event(builder)?;

    let resp = client.submit_event(event).await?;
    println!("{}", normalize_write_response(&resp));
    Ok(())
}

/// Edit a message you previously sent.
pub async fn cmd_edit_message(
    client: &BuzzClient,
    event_id: &str,
    content: &str,
) -> Result<(), CliError> {
    validate_hex64(event_id)?;
    validate_content_size(content)?;

    // Resolve channel_id from the event's h-tag
    let channel_uuid = resolve_channel_id(client, event_id).await?;
    let target_eid = parse_event_id(event_id)?;

    let builder = buzz_sdk::build_edit(channel_uuid, target_eid, content)
        .map_err(|e| CliError::Other(format!("build_edit failed: {e}")))?;

    let event = client.sign_event(builder)?;

    let resp = client.submit_event(event).await?;
    println!("{}", normalize_write_response(&resp));
    Ok(())
}

/// Vote on a forum post or comment.
pub async fn cmd_vote_on_post(
    client: &BuzzClient,
    event_id: &str,
    direction: &str,
) -> Result<(), CliError> {
    validate_hex64(event_id)?;
    let vote_dir = match direction {
        "up" => VoteDirection::Up,
        "down" => VoteDirection::Down,
        _ => {
            return Err(CliError::Usage(format!(
                "--direction must be 'up' or 'down' (got: {direction})"
            )))
        }
    };

    // Resolve channel_id from the event's h-tag
    let channel_uuid = resolve_channel_id(client, event_id).await?;
    let target_eid = parse_event_id(event_id)?;

    let builder = buzz_sdk::build_vote(channel_uuid, target_eid, vote_dir)
        .map_err(|e| CliError::Other(format!("build_vote failed: {e}")))?;

    let event = client.sign_event(builder)?;

    let resp = client.submit_event(event).await?;
    println!("{}", normalize_write_response(&resp));
    Ok(())
}

pub async fn dispatch(
    cmd: crate::MessagesCmd,
    client: &BuzzClient,
    format: &crate::OutputFormat,
) -> Result<(), CliError> {
    use crate::MessagesCmd;
    match cmd {
        MessagesCmd::Send {
            channel,
            content,
            kind,
            reply_to,
            broadcast,
            files,
            mentions,
        } => {
            cmd_send_message(
                client,
                SendMessageParams {
                    channel_id: channel,
                    content,
                    kind,
                    reply_to,
                    broadcast,
                    files,
                    mentions,
                },
            )
            .await
        }
        MessagesCmd::SendDiff {
            channel,
            diff,
            repo,
            commit,
            file,
            parent_commit,
            source_branch,
            target_branch,
            pr,
            lang,
            description,
            reply_to,
        } => {
            cmd_send_diff_message(
                client,
                SendDiffParams {
                    channel_id: channel,
                    diff,
                    repo_url: repo,
                    commit_sha: commit,
                    file_path: file,
                    parent_commit_sha: parent_commit,
                    source_branch,
                    target_branch,
                    pr_number: pr,
                    language: lang,
                    description,
                    reply_to,
                },
            )
            .await
        }
        MessagesCmd::Edit { event, content } => cmd_edit_message(client, &event, &content).await,
        MessagesCmd::Delete {
            event,
            action_id,
            reason_code,
            public_reason,
        } => {
            cmd_delete_message(
                client,
                &event,
                action_id,
                reason_code.as_deref(),
                public_reason.as_deref(),
            )
            .await
        }
        MessagesCmd::Get {
            channel,
            limit,
            before,
            since,
            kinds,
        } => {
            cmd_get_messages(
                client,
                &channel,
                limit,
                before,
                since,
                kinds.as_deref(),
                format,
            )
            .await
        }
        MessagesCmd::Thread {
            channel,
            event,
            limit,
            depth_limit,
        } => cmd_get_thread(client, &channel, &event, limit, depth_limit, format).await,
        MessagesCmd::Search {
            query,
            author,
            since,
            limit,
        } => {
            cmd_search(
                client,
                query.as_deref(),
                author.as_deref(),
                since,
                limit,
                format,
            )
            .await
        }
        MessagesCmd::Vote { event, direction } => {
            cmd_vote_on_post(client, &event, &direction).await
        }
        MessagesCmd::Watch {
            channels,
            since,
            format,
            timeout,
            limit,
        } => cmd_watch_messages(client, &channels, since, &format, timeout, limit).await,
    }
}

/// F2: id-primary dedupe — first sight of an event id emits; repeats skip.
fn watch_should_emit(seen: &mut std::collections::HashSet<String>, event_id: &str) -> bool {
    seen.insert(event_id.to_string())
}

/// F3: transport watermark — max `created_at` among successfully emitted facts.
/// Used as REQ `since` on reconnect (with id-dedupe providing replay overlap safety).
fn watch_advance_watermark(watermark: &mut Option<u64>, created_at: u64) {
    *watermark = Some(watermark.map_or(created_at, |w| w.max(created_at)));
}

/// F3: resume cursor for REQ after reconnect.
///
/// Prefers the emit watermark (with optional 1s overlap for same-second bursts).
/// Falls back to the caller-supplied initial `--since`.
fn watch_resume_since(initial_since: Option<i64>, watermark: Option<u64>) -> Option<i64> {
    match (watermark, initial_since) {
        (Some(w), Some(s)) => Some(i64::try_from(w.saturating_sub(1)).unwrap_or(0).max(s)),
        (Some(w), None) => Some(i64::try_from(w.saturating_sub(1)).unwrap_or(0)),
        (None, s) => s,
    }
}

/// F3 deterministic fixture: feed synthetic (id, created_at) through emit+watermark
/// state across a simulated disconnect. Returns emitted ids in order.
#[cfg(test)]
fn watch_f3_replay_sequence(
    events_before_drop: &[(&str, u64)],
    events_after_resume: &[(&str, u64)],
) -> (Vec<String>, Option<u64>, Option<i64>) {
    let mut seen = std::collections::HashSet::new();
    let mut watermark = None;
    let mut out = Vec::new();
    for (id, ts) in events_before_drop {
        if watch_should_emit(&mut seen, id) {
            watch_advance_watermark(&mut watermark, *ts);
            out.push((*id).to_string());
        }
    }
    let resume = watch_resume_since(None, watermark);
    for (id, ts) in events_after_resume {
        if watch_should_emit(&mut seen, id) {
            watch_advance_watermark(&mut watermark, *ts);
            out.push((*id).to_string());
        }
    }
    (out, watermark, resume)
}

/// Build one stdout JSONL fact object from a Nostr event (v1 field set).
fn watch_jsonl_fact(event: &nostr::Event) -> serde_json::Value {
    let id = event.id.to_hex();
    let channel_id = event
        .tags
        .iter()
        .find_map(|t| {
            let v = t.clone().to_vec();
            if v.first().map(String::as_str) == Some("h") {
                v.get(1).cloned()
            } else {
                None
            }
        })
        .unwrap_or_default();
    let tags: Vec<Vec<String>> = event.tags.iter().map(|t| t.clone().to_vec()).collect();
    serde_json::json!({
        "id": id,
        "created_at": event.created_at.as_secs(),
        "kind": event.kind.as_u16(),
        "pubkey": event.pubkey.to_hex(),
        "channel_id": channel_id,
        "content": event.content,
        "tags": tags,
    })
}

/// Stream channel events over WebSocket with NIP-42 AUTH (F1–F3 push path).
///
/// Contract (co-lab locked):
/// - stdout: JSONL facts only (`id`, `created_at`, `kind`, `pubkey`, `channel_id`, `content`, `tags`)
/// - stderr: AUTH / EOSE / NOTICE / CLOSED / reconnect diagnostics (never secrets)
/// - AUTH failure → non-zero exit, zero JSONL during unauthenticated intervals
/// - id-primary dedupe within the process (survives reconnect)
/// - F3: on drop, re-AUTH + REQ with transport watermark overlap; no replay storm
/// - `--timeout` / SIGINT after AUTH → exit 0 (clean end of watch)
async fn cmd_watch_messages(
    client: &BuzzClient,
    channels: &[String],
    since: Option<i64>,
    format: &str,
    timeout_secs: Option<u64>,
    limit: u32,
) -> Result<(), CliError> {
    use buzz_ws_client::{NostrWsConnection, RelayMessage, WsClientError};
    use std::collections::HashSet;
    use std::io::{self, Write};
    use std::time::Duration;

    if format != "jsonl" {
        return Err(CliError::Usage(
            "messages watch only supports --format jsonl in v1".into(),
        ));
    }
    if channels.is_empty() {
        return Err(CliError::Usage(
            "messages watch requires at least one --channel UUID".into(),
        ));
    }

    let mut channel_ids = Vec::with_capacity(channels.len());
    for ch in channels {
        let uuid = parse_uuid(ch)?;
        channel_ids.push(uuid.to_string());
    }

    let ws_url = client
        .relay_url()
        .replace("https://", "wss://")
        .replace("http://", "ws://");

    let deadline = timeout_secs.map(|s| tokio::time::Instant::now() + Duration::from_secs(s));
    let mut seen: HashSet<String> = HashSet::new();
    let mut watermark: Option<u64> = None;
    let mut emitted: u32 = 0;
    let mut stdout = io::stdout();
    let mut reconnect_attempt: u32 = 0;
    const MAX_RECONNECT: u32 = 8;

    'sessions: loop {
        if let Some(d) = deadline {
            if tokio::time::Instant::now() >= d {
                eprintln!("BUZZ_WATCH timeout");
                break;
            }
        }

        let resume_since = watch_resume_since(since, watermark);
        if reconnect_attempt > 0 {
            eprintln!(
                "BUZZ_WATCH reconnect attempt={reconnect_attempt} resume_since={resume_since:?} watermark={watermark:?}"
            );
        } else {
            eprintln!("BUZZ_WATCH connecting {ws_url}");
        }

        // Unauthenticated intervals must not emit JSONL (no conn ⇒ no facts).
        let mut conn =
            match NostrWsConnection::connect_authenticated(&ws_url, client.keys(), None).await {
                Ok(c) => c,
                Err(e) => {
                    eprintln!("BUZZ_WATCH AUTH_FAIL {e}");
                    // Permanent auth/config failures: do not spin forever.
                    if matches!(
                        e,
                        WsClientError::AuthFailed(_) | WsClientError::NoAuthChallenge
                    ) {
                        return Err(CliError::Other(format!(
                            "messages watch auth/connect failed: {e}"
                        )));
                    }
                    reconnect_attempt += 1;
                    if reconnect_attempt > MAX_RECONNECT {
                        return Err(CliError::Other(format!(
                            "messages watch reconnect exhausted after AUTH/connect errors: {e}"
                        )));
                    }
                    let backoff = Duration::from_secs(u64::from(reconnect_attempt.min(5)));
                    eprintln!("BUZZ_WATCH backoff {}s", backoff.as_secs());
                    tokio::time::sleep(backoff).await;
                    continue 'sessions;
                }
            };

        eprintln!("BUZZ_WATCH AUTH_OK");
        reconnect_attempt = 0;

        let sub_id = format!("buzz-watch-{}", &uuid::Uuid::new_v4().to_string()[..8]);
        let mut filter = serde_json::json!({
            "kinds": [9, 40002, 40008, 45001, 45003],
            "#h": channel_ids,
            "limit": 50,
        });
        if let Some(ts) = resume_since {
            filter["since"] = serde_json::json!(ts);
        }

        let req = serde_json::json!(["REQ", sub_id, filter]);
        if let Err(e) = conn.send_raw(&req).await {
            eprintln!("BUZZ_WATCH error REQ failed: {e}");
            reconnect_attempt += 1;
            if reconnect_attempt > MAX_RECONNECT {
                return Err(CliError::Other(format!("messages watch REQ failed: {e}")));
            }
            let _ = conn.disconnect().await;
            continue 'sessions;
        }
        eprintln!(
            "BUZZ_WATCH REQ sub={sub_id} channels={} since={resume_since:?}",
            channel_ids.len()
        );

        // Stream until timeout, interrupt, limit, or connection drop → reconnect.
        loop {
            if let Some(d) = deadline {
                if tokio::time::Instant::now() >= d {
                    eprintln!("BUZZ_WATCH timeout");
                    let _ = conn.disconnect().await;
                    break 'sessions;
                }
            }

            let wait = match deadline {
                Some(d) => d.saturating_duration_since(tokio::time::Instant::now()),
                None => Duration::from_secs(30),
            };

            let msg = tokio::select! {
                biased;
                _ = tokio::signal::ctrl_c() => {
                    eprintln!("BUZZ_WATCH interrupt");
                    let _ = conn.disconnect().await;
                    break 'sessions;
                }
                result = conn.next_event(wait) => result,
            };

            let msg = match msg {
                Ok(m) => m,
                Err(WsClientError::Timeout) => continue,
                Err(e @ (WsClientError::ConnectionClosed | WsClientError::WebSocket(_))) => {
                    eprintln!("BUZZ_WATCH disconnect {e}");
                    let _ = conn.disconnect().await;
                    reconnect_attempt += 1;
                    if reconnect_attempt > MAX_RECONNECT {
                        return Err(CliError::Other(format!(
                            "messages watch reconnect exhausted: {e}"
                        )));
                    }
                    continue 'sessions;
                }
                Err(e) => {
                    eprintln!("BUZZ_WATCH error {e}");
                    return Err(CliError::Other(format!("messages watch stream error: {e}")));
                }
            };

            match msg {
                RelayMessage::Event { event, .. } => {
                    let id = event.id.to_hex();
                    let created = event.created_at.as_secs();
                    if !watch_should_emit(&mut seen, &id) {
                        continue; // F2/F3: suppress replay across reconnect
                    }
                    watch_advance_watermark(&mut watermark, created);
                    let fact = watch_jsonl_fact(&event);
                    writeln!(stdout, "{fact}").map_err(|e| CliError::Other(e.to_string()))?;
                    stdout.flush().ok();
                    emitted += 1;
                    if limit > 0 && emitted >= limit {
                        eprintln!("BUZZ_WATCH limit reached count={emitted}");
                        let _ = conn.disconnect().await;
                        break 'sessions;
                    }
                }
                RelayMessage::Eose { subscription_id } => {
                    eprintln!("BUZZ_WATCH EOSE sub={subscription_id}");
                }
                RelayMessage::Closed {
                    subscription_id,
                    message,
                } => {
                    eprintln!("BUZZ_WATCH CLOSED sub={subscription_id} reason={message}");
                    let _ = conn.disconnect().await;
                    // Treat as drop → reconnect with watermark (unless never emitted).
                    if emitted == 0 && watermark.is_none() {
                        return Err(CliError::Other(format!(
                            "subscription closed before events: {message}"
                        )));
                    }
                    reconnect_attempt += 1;
                    if reconnect_attempt > MAX_RECONNECT {
                        break 'sessions;
                    }
                    continue 'sessions;
                }
                RelayMessage::Notice { message } => {
                    eprintln!("BUZZ_WATCH NOTICE {message}");
                }
                RelayMessage::Auth { .. } => {
                    eprintln!("BUZZ_WATCH NOTICE unexpected AUTH challenge while streaming");
                }
                RelayMessage::Ok(_) | RelayMessage::Count { .. } => {}
            }
        }
    }

    eprintln!(
        "BUZZ_WATCH done emitted={emitted} watermark={watermark:?} seen={}",
        seen.len()
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        event_mention_pubkeys, find_root_from_tags, match_profiles_by_name, merge_message_mentions,
        missing_members, normalize_explicit_mentions, parse_member_pubkeys,
        resolve_names_to_pubkeys, watch_advance_watermark, watch_f3_replay_sequence,
        watch_resume_since, watch_should_emit,
    };
    use buzz_sdk::mentions::{
        extract_at_mentions_with_known, extract_at_names, match_names_to_profiles, MentionProfile,
    };
    use serde_json::json;
    use std::collections::HashSet;

    const ID_A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const ID_B: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const PUBKEY: &str = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";

    // Three real pubkeys (lowercase 64-char hex) used by parse_member_pubkeys tests.
    // See the test's own comment on what `PublicKey::from_hex` actually validates.
    const PK_VALID_A: &str = "35c18ae273fccfaf80d629e20e7f8721b90499379addff533054acc2504c12b4";
    const PK_VALID_B: &str = "c6237ef84fa537c78dcee78efd2d4e59f728859c7f194da42ac51ededfa0be05";
    const PK_VALID_C: &str = "f4a42a97e594b77bdbd8ee35191c8b28a94a4cb871d96f32921558275421fb68";

    /// F2a: same event id only emits once within a watch process.
    #[test]
    fn watch_dedupe_same_id_emits_once() {
        let mut seen = HashSet::new();
        assert!(watch_should_emit(&mut seen, ID_A));
        assert!(!watch_should_emit(&mut seen, ID_A));
        assert!(!watch_should_emit(&mut seen, ID_A));
        assert!(watch_should_emit(&mut seen, ID_B));
        assert!(!watch_should_emit(&mut seen, ID_B));
        assert_eq!(seen.len(), 2);
    }

    /// F3: after event A, reconnect replay of A + new B → stdout A,B exactly once.
    #[test]
    fn watch_f3_reconnect_replay_overlap_no_storm() {
        let (out, watermark, resume) = watch_f3_replay_sequence(
            &[(ID_A, 1000)],
            // Replay A (same id) plus new B — A must not re-emit.
            &[(ID_A, 1000), (ID_B, 1005)],
        );
        assert_eq!(out, vec![ID_A.to_string(), ID_B.to_string()]);
        assert_eq!(watermark, Some(1005));
        // Resume cursor is watermark-1 for overlap window.
        assert_eq!(resume, Some(999));
    }

    #[test]
    fn watch_resume_since_prefers_watermark_overlap() {
        assert_eq!(watch_resume_since(Some(50), Some(100)), Some(99));
        assert_eq!(watch_resume_since(Some(100), Some(100)), Some(100));
        assert_eq!(watch_resume_since(None, Some(10)), Some(9));
        assert_eq!(watch_resume_since(Some(7), None), Some(7));
        let mut w = None;
        watch_advance_watermark(&mut w, 5);
        watch_advance_watermark(&mut w, 3);
        watch_advance_watermark(&mut w, 9);
        assert_eq!(w, Some(9));
    }

    /// F4.1: two watch processes (seats) each emit shared event E once.
    #[test]
    fn watch_f4_two_seats_each_emit_shared_event_once() {
        let event_e = ID_A;
        let mut seat_a = HashSet::new();
        let mut seat_b = HashSet::new();
        assert!(watch_should_emit(&mut seat_a, event_e));
        assert!(watch_should_emit(&mut seat_b, event_e));
        // Replays on either process do not re-emit.
        assert!(!watch_should_emit(&mut seat_a, event_e));
        assert!(!watch_should_emit(&mut seat_b, event_e));
        assert_eq!(seat_a.len(), 1);
        assert_eq!(seat_b.len(), 1);
    }

    /// F4.2: one process fan-in (two channels / two deliveries of same id) → one fact.
    #[test]
    fn watch_f4_fan_in_one_process_one_emit() {
        let mut seen = HashSet::new();
        // Same event id arrives twice (e.g. multi-channel fan-in).
        assert!(watch_should_emit(&mut seen, ID_A));
        assert!(!watch_should_emit(&mut seen, ID_A));
        assert_eq!(seen.len(), 1);
    }

    /// F4.3 + F4.5: transport cursors (watermarks) are process-local; reconnect
    /// dedupe state does not cross seats.
    #[test]
    fn watch_f4_cursors_and_replay_are_process_local() {
        let mut wa: Option<u64> = None;
        let mut wb: Option<u64> = None;
        watch_advance_watermark(&mut wa, 1000);
        watch_advance_watermark(&mut wb, 500);
        assert_eq!(watch_resume_since(None, wa), Some(999));
        assert_eq!(watch_resume_since(None, wb), Some(499));
        // Advancing A must not change B.
        watch_advance_watermark(&mut wa, 2000);
        assert_eq!(watch_resume_since(None, wb), Some(499));
        assert_eq!(watch_resume_since(None, wa), Some(1999));

        // Independent reconnect sequences.
        let (out_a, _, _) = watch_f3_replay_sequence(&[(ID_A, 100)], &[(ID_A, 100), (ID_B, 110)]);
        let (out_b, _, _) = watch_f3_replay_sequence(&[(ID_B, 50)], &[(ID_B, 50), (ID_A, 60)]);
        assert_eq!(out_a, vec![ID_A.to_string(), ID_B.to_string()]);
        assert_eq!(out_b, vec![ID_B.to_string(), ID_A.to_string()]);
    }

    /// F4.4 (CLI half): self-pubkey events are still transport facts if the
    /// relay delivers them — skill L1 self-suppress is separate (F6). CLI
    /// dedupe treats them like any other id.
    #[test]
    fn watch_f4_cli_emits_self_pubkey_as_transport_fact() {
        let mut seen = HashSet::new();
        // "Self" is a skill concern; CLI still one-emits by id.
        assert!(watch_should_emit(&mut seen, ID_A));
        assert!(!watch_should_emit(&mut seen, ID_A));
    }

    #[test]
    fn root_marker_wins_over_reply_marker() {
        let tags = json!([
            ["e", ID_A, "", "root"],
            ["e", ID_B, "", "reply"],
            ["p", PUBKEY],
        ]);
        assert_eq!(find_root_from_tags(&tags).as_deref(), Some(ID_A));
    }

    #[test]
    fn reply_only_falls_back_to_reply_target() {
        // Direct reply to a top-level message — the parent's only e-tag is a
        // "reply" marker pointing at it; treat the reply target as the root.
        let tags = json!([["e", ID_B, "", "reply"], ["p", PUBKEY],]);
        assert_eq!(find_root_from_tags(&tags).as_deref(), Some(ID_B));
    }

    #[test]
    fn no_thread_markers_returns_none() {
        let tags = json!([["p", PUBKEY], ["h", "channel-uuid"],]);
        assert!(find_root_from_tags(&tags).is_none());
    }

    #[test]
    fn unmarked_e_tag_ignored() {
        // NIP-10 deprecated positional markers; ignore e-tags lacking an
        // explicit "root"/"reply" marker rather than guessing.
        let tags = json!([["e", ID_A], ["e", ID_B, ""],]);
        assert!(find_root_from_tags(&tags).is_none());
    }

    #[test]
    fn malformed_tags_are_skipped() {
        let tags = json!([
            "not-an-array",
            ["e"],
            ["e", "short"],
            ["e", ID_A, "", "root"],
        ]);
        assert_eq!(find_root_from_tags(&tags).as_deref(), Some(ID_A));
    }

    #[test]
    fn malformed_marker_id_is_ignored() {
        // Parent event has a "root" marker whose value isn't a valid 64-hex
        // event id (other-client bug, relay-accepted). Treat the marker as
        // absent so the caller falls back to root == parent rather than
        // failing to send the reply.
        let tags = json!([["e", "not-a-valid-id", "", "root"], ["p", PUBKEY],]);
        assert!(find_root_from_tags(&tags).is_none());
    }

    #[test]
    fn malformed_root_does_not_shadow_valid_reply() {
        // If "root" is malformed but "reply" is valid, fall back to "reply".
        let tags = json!([["e", "garbage", "", "root"], ["e", ID_B, "", "reply"],]);
        assert_eq!(find_root_from_tags(&tags).as_deref(), Some(ID_B));
    }

    #[test]
    fn non_array_input_returns_none() {
        assert!(find_root_from_tags(&json!({})).is_none());
        assert!(find_root_from_tags(&json!(null)).is_none());
    }

    //
    // These tests don't hit the network — they prove that *given* the
    // events the relay returns, the CLI's parse + match wiring produces
    // the right pubkeys. The async I/O wrapper around them is one
    // straight line; the pure stages it composes are exercised here and
    // in buzz-sdk.

    /// End-to-end (sans I/O): body text → extracted names → matched
    /// member pubkeys, using realistic 39002 + kind:0 event JSON.
    /// This is the regression guard for the previous stub that always
    /// returned `vec![]`.
    #[test]
    fn cli_pipeline_resolves_body_at_names_to_member_pubkeys() {
        // kind 39002 channel-members event with three members.
        let members_event = json!({
            "kind": 39002,
            "tags": [
                ["d", "00000000-0000-0000-0000-000000000000"],
                ["p", PK_VALID_A, "", "member"],
                ["p", PK_VALID_B, "", "member"],
                ["p", PK_VALID_C, "", "member"],
            ],
            "content": "",
        });
        assert_eq!(
            parse_member_pubkeys(&members_event),
            vec![PK_VALID_A, PK_VALID_B, PK_VALID_C]
        );

        // Three kind:0 profile events.
        let entries = vec![
            MentionProfile {
                pubkey: PK_VALID_A,
                content_json: r#"{"display_name":"Alice"}"#,
            },
            MentionProfile {
                pubkey: PK_VALID_B,
                content_json: r#"{"display_name":"Bob"}"#,
            },
            MentionProfile {
                pubkey: PK_VALID_C,
                content_json: r#"{"name":"Carol"}"#,
            },
        ];

        // Body mentions Alice and Carol (display_name fallback to `name`).
        let names = extract_at_names("hello @alice and @CAROL");
        let resolved = match_names_to_profiles(&names, &entries);
        assert_eq!(resolved, vec![PK_VALID_A, PK_VALID_C]);
    }

    #[test]
    fn cli_pipeline_resolves_multiword_display_names() {
        let profile_events: Vec<serde_json::Value> = vec![
            json!({
                "pubkey": PK_VALID_A,
                "content": r#"{"display_name":"Will Pfleger"}"#,
            }),
            json!({
                "pubkey": PK_VALID_B,
                "content": r#"{"display_name":"Alice"}"#,
            }),
        ];

        // Simulate the single-parse pipeline from resolve_content_mentions.
        let mut name_to_pubkeys: std::collections::HashMap<String, Vec<String>> =
            std::collections::HashMap::new();
        let mut display_names: Vec<String> = Vec::new();
        for e in &profile_events {
            let pubkey = e.get("pubkey").unwrap().as_str().unwrap();
            let content_json = e.get("content").unwrap().as_str().unwrap();
            let v: serde_json::Value = serde_json::from_str(content_json).unwrap();
            let name = v
                .get("display_name")
                .or_else(|| v.get("name"))
                .and_then(|n| n.as_str())
                .filter(|n| !n.is_empty())
                .unwrap();
            let lower = name.to_ascii_lowercase();
            name_to_pubkeys
                .entry(lower)
                .or_default()
                .push(pubkey.to_string());
            display_names.push(name.to_string());
        }

        let known_refs: Vec<&str> = display_names.iter().map(|s| s.as_str()).collect();
        let names = extract_at_mentions_with_known("hey @Will Pfleger and @alice!", &known_refs);
        assert_eq!(names, vec!["will pfleger", "alice"]);

        let resolved: Vec<String> = names
            .iter()
            .flat_map(|n| name_to_pubkeys.get(n).into_iter().flatten())
            .cloned()
            .collect();
        assert_eq!(resolved, vec![PK_VALID_A, PK_VALID_B]);
    }

    #[test]
    fn cli_pipeline_returns_empty_when_no_at_names() {
        // Sanity: no `@names` in body → no profile match attempt needed.
        let names = extract_at_names("plain message, no mentions");
        assert!(names.is_empty());
    }

    #[test]
    fn parse_member_pubkeys_ignores_non_p_tags() {
        let event = json!({
            "tags": [
                ["d", "channel-id"],
                ["p", PK_VALID_A],
                ["h", "channel-id"],
                ["e", "some-event"],
                ["p", PK_VALID_B, "wss://relay", "member"],
            ],
        });
        assert_eq!(parse_member_pubkeys(&event), vec![PK_VALID_A, PK_VALID_B]);
    }

    #[test]
    fn parse_member_pubkeys_handles_malformed_event() {
        assert!(parse_member_pubkeys(&json!({})).is_empty());
        assert!(parse_member_pubkeys(&json!({"tags": "not an array"})).is_empty());
        assert!(parse_member_pubkeys(&json!({"tags": [["p"]]})).is_empty());
    }

    #[test]
    fn parse_member_pubkeys_filters_invalid_hex() {
        // `PublicKey::from_hex` rejects non-hex and wrong-length inputs and
        // canonicalizes hex case. (Note: it accepts any 64-char x-only hex
        // whose integer value is in field; it does not verify the point is
        // actually on the curve — same as MCP's behavior.)
        let pk_uppercase: String = PK_VALID_A.to_ascii_uppercase();
        let event = json!({
            "tags": [
                ["p", PK_VALID_A],       // valid, lowercase
                ["p", pk_uppercase],     // valid hex, canonicalized to lowercase
                ["p", "too-short"],      // length fail
                ["p", "z".repeat(64)],   // non-hex chars
                ["p", "a".repeat(63)],   // off-by-one length
            ],
        });
        assert_eq!(parse_member_pubkeys(&event), vec![PK_VALID_A, PK_VALID_A]);
    }

    #[test]
    fn explicit_mentions_accept_hex_and_npub_and_deduplicate() {
        use nostr::ToBech32;
        let npub = nostr::PublicKey::from_hex(PK_VALID_A)
            .unwrap()
            .to_bech32()
            .unwrap();
        assert_eq!(
            normalize_explicit_mentions(&[PK_VALID_A.into(), npub]).unwrap(),
            vec![PK_VALID_A]
        );
        assert!(normalize_explicit_mentions(&["not-a-key".into()]).is_err());
    }

    #[test]
    fn explicit_mentions_authorize_presentation_text_without_name_resolution() {
        let names = vec!["renamed user".into()];
        let profiles = std::collections::HashMap::new();
        assert_eq!(
            resolve_names_to_pubkeys(&names, &profiles, true).unwrap(),
            Vec::<String>::new()
        );
        assert!(resolve_names_to_pubkeys(&names, &profiles, false).is_err());
    }

    #[test]
    fn explicit_mentions_authorize_ambiguous_presentation_text() {
        let names = vec!["alice".into()];
        let profiles = std::collections::HashMap::from([(
            "alice".into(),
            vec![PK_VALID_A.into(), PK_VALID_B.into()],
        )]);
        assert_eq!(
            resolve_names_to_pubkeys(&names, &profiles, true).unwrap(),
            Vec::<String>::new()
        );
        let error = resolve_names_to_pubkeys(&names, &profiles, false).unwrap_err();
        assert!(error.to_string().contains(PK_VALID_A));
        assert!(error.to_string().contains(PK_VALID_B));
    }

    #[test]
    fn explicit_mentions_make_all_at_names_presentation_only() {
        let names = vec!["alice".into(), "bob".into()];
        let profiles = std::collections::HashMap::from([("alice".into(), vec![PK_VALID_A.into()])]);
        assert_eq!(
            resolve_names_to_pubkeys(&names, &profiles, true).unwrap(),
            vec![PK_VALID_A]
        );
        assert!(resolve_names_to_pubkeys(&names, &profiles, false).is_err());
    }

    #[test]
    fn combined_mention_union_errors_instead_of_truncating() {
        let explicit: Vec<String> = (0..50).map(|i| format!("explicit-{i}")).collect();
        assert!(merge_message_mentions(&explicit, &[], &["resolved-bob".into()]).is_err());

        let mut with_duplicate = explicit.clone();
        with_duplicate.push(explicit[0].clone());
        assert_eq!(
            merge_message_mentions(&with_duplicate, &[explicit[1].clone()], &[])
                .unwrap()
                .len(),
            50
        );
    }

    #[test]
    fn membership_preflight_lists_only_missing_mentions() {
        assert_eq!(
            missing_members(
                &[PK_VALID_A.into(), PK_VALID_B.into()],
                &[PK_VALID_A.into()]
            ),
            vec![PK_VALID_B]
        );
    }

    #[test]
    fn mention_evidence_comes_from_signed_event_tags() {
        use nostr::{EventBuilder, Keys, Tag};
        let event = EventBuilder::text_note("hello")
            .tags(vec![Tag::parse(["p", PK_VALID_A]).unwrap()])
            .sign_with_keys(&Keys::generate())
            .unwrap();
        assert_eq!(event_mention_pubkeys(&event), vec![PK_VALID_A]);
    }

    // ---- match_profiles_by_name (author resolution for `messages search --author`) ----

    fn profile_event(
        pubkey: &str,
        display_name: Option<&str>,
        name: Option<&str>,
    ) -> serde_json::Value {
        let mut content = serde_json::Map::new();
        if let Some(d) = display_name {
            content.insert("display_name".into(), json!(d));
        }
        if let Some(n) = name {
            content.insert("name".into(), json!(n));
        }
        json!({
            "pubkey": pubkey,
            "content": serde_json::Value::Object(content).to_string(),
        })
    }

    #[test]
    fn author_name_match_is_exact_case_insensitive() {
        let events = vec![
            profile_event(PK_VALID_A, Some("Aaron"), Some("aaron")),
            // Substring only — NIP-50 may return it, but it must not match.
            profile_event(PK_VALID_B, Some("Aaronson"), None),
        ];
        let matches = match_profiles_by_name(&events, "aArOn");
        assert_eq!(matches, vec![(PK_VALID_A.to_string(), "Aaron".to_string())]);
    }

    #[test]
    fn author_name_ambiguity_returns_all_candidates() {
        let events = vec![
            profile_event(PK_VALID_A, Some("Sam"), None),
            profile_event(PK_VALID_B, None, Some("sam")),
        ];
        let matches = match_profiles_by_name(&events, "sam");
        assert_eq!(matches.len(), 2);
    }

    #[test]
    fn author_name_no_match_and_malformed_content() {
        let events = vec![
            profile_event(PK_VALID_A, Some("Aaron"), None),
            json!({"pubkey": PK_VALID_B, "content": "not-json"}),
            json!({"content": "{}"}), // missing pubkey
        ];
        assert!(match_profiles_by_name(&events, "Zoe").is_empty());
    }

    #[test]
    fn author_name_dedups_replaceable_event_copies() {
        // Same (pubkey, name) appearing twice (e.g. duplicate kind:0 rows)
        // must resolve unambiguously.
        let events = vec![
            profile_event(PK_VALID_A, Some("Aaron"), None),
            profile_event(PK_VALID_A, Some("Aaron"), None),
        ];
        assert_eq!(match_profiles_by_name(&events, "Aaron").len(), 1);
    }
}
