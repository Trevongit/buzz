/** Ollama output tokens for Listen (summary). 180 cut DMs mid-sentence. */
export const LISTEN_SUMMARY_NUM_PREDICT = 512;

/** Plain text a TTS engine can speak from a chat body. */
export function listenPlainText(body: string, maxChars = 2_500): string {
  const stripped = body
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)]\([^)]*\)/g, "$1")
    .replace(/[#*_>~]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (stripped.length <= maxChars) return stripped;
  return `${stripped.slice(0, maxChars).trim()}…`;
}

export const READER_AGENT_NAME = "Reader-laptop";

export function isReaderAgentName(name: string): boolean {
  const normalized = name.trim().toLowerCase().replace(/\s+/g, "-");
  return normalized === "reader-laptop" || normalized === "reader";
}

/** CLI/Grok Pocket posts that Listen (summary) should treat as the Reader reply. */
export function isPocketFollowAlongBody(content: string): boolean {
  return /follow-along for Pocket/i.test(content || "");
}

function eventRepliesTo(tags: string[][], eventId: string | null): boolean {
  if (!eventId) return false;
  const want = eventId.toLowerCase();
  return tags.some((tag) => tag[0] === "e" && tag[1]?.toLowerCase() === want);
}

/**
 * Whether a live/polled channel event is the Listen (summary) reply.
 * Reader pubkey always counts (original path). A CLI/Grok Pocket post
 * counts only when it is in this ask's thread — not another room thread.
 */
export function isListenSummaryReplyEvent(input: {
  body: string;
  eventPubkey: string;
  readerPubkey: string;
  askEventId: string | null;
  threadRootId: string;
  tags: string[][];
}): boolean {
  const body = input.body.trim();
  if (!body) return false;
  const fromReader =
    input.eventPubkey.toLowerCase() === input.readerPubkey.toLowerCase();
  if (fromReader) return true;
  if (eventRepliesTo(input.tags, input.askEventId)) return true;
  return (
    isPocketFollowAlongBody(body) &&
    (eventRepliesTo(input.tags, input.askEventId) ||
      eventRepliesTo(input.tags, input.threadRootId))
  );
}

export function isFollowAlongMessage(
  message: {
    author: string;
    body: string;
    isAgent?: boolean;
  },
  preferredAgentName?: string | null,
): boolean {
  if (isReaderAgentName(message.author)) return true;
  const preferred = preferredAgentName?.trim();
  if (
    preferred &&
    message.author.trim().toLowerCase() === preferred.toLowerCase()
  ) {
    return true;
  }
  return Boolean(message.isAgent && /\bread-along\b/i.test(message.body));
}

export function listenSummaryPrompt(text: string): string {
  return `Rewrite the following Buzz message as spoken prose a person can listen to. Keep names, decisions, and numbers. Use complete sentences and always finish the last sentence. No markdown, no bullets, no preamble.\n\n${text}`;
}

/** Channel ask so the chosen Listen-summary agent writes Pocket prose. */
export function listenReaderAsk(agentName: string, text: string): string {
  const mention = agentName.trim() || READER_AGENT_NAME;
  return `@${mention} Summarize this message in this thread for follow-along. You are a tour guide for the human who clicked Listen. Speak clearly. When a term is not obvious (L2, mint, ACP, visitor kit, glue, named visitor), say what it means in one short sentence the first time. Keep vendor names exact: green helper is Antigravity, teal is Codex, purple is Grok Build. Never say Claude.

First: spoken prose for Pocket (complete sentences, finish the last sentence, no markdown). Point at the pictures already attached. Describe what those pictures show so ears and eyes match.

Then in the same reply: a read-along with phone-safe bullets only. Reuse pictures already in this message or thread. Do not invent, generate, or attach a replacement infographic. If the original pictures are more informative, keep them. Do not add a weaker diagram.

Prime will click your post to hear Pocket and can keep talking in the thread for more clarity.

${text}`;
}

/** Prefer the Spoken section when Reader also attached a read-along. */
export function spokenProseFromReaderReply(content: string): string {
  const match = content.match(/spoken\s*\n([\s\S]*?)(?:\n\s*read-along\b|$)/i);
  const raw = match?.[1]?.trim() || content;
  return finishSpokenSummary(listenPlainText(raw, 8_000));
}

/** Drop a token-capped trailing fragment so Pocket does not speak a half sentence. */
export function finishSpokenSummary(text: string): string {
  const trimmed = text.replace(/\s+/g, " ").trim();
  if (!trimmed) return trimmed;
  if (/[.!?]["')\]]?$/.test(trimmed)) return trimmed;
  const lastStop = Math.max(
    trimmed.lastIndexOf(". "),
    trimmed.lastIndexOf("! "),
    trimmed.lastIndexOf("? "),
  );
  if (lastStop >= 0) return trimmed.slice(0, lastStop + 1).trim();
  return trimmed;
}
