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
  return `@${mention} Summarize this message in this thread for follow-along. First: spoken prose for Pocket (complete sentences, finish the last sentence, no markdown). Then in the same reply: a read-along with phone-safe bullets and glimpse diagrams or pictures if they help understanding. Prime will click your post to hear Pocket and can keep talking in the thread for more clarity.\n\n${text}`;
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
