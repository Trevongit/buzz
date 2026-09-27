const STORAGE_KEY = "buzz.composer.ghost-phrases";
const MAX_PHRASES = 200;

const SEED = [
  "extras stays buzz",
  "job card",
  "Spelling suggestions",
  "one ear",
  "named chair",
  "control-room",
];

function loadPhrases(): string[] {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    if (!raw) return [...SEED];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [...SEED];
    const phrases = parsed.filter(
      (item): item is string => typeof item === "string" && item.trim().length > 1,
    );
    return [...new Set([...SEED, ...phrases])];
  } catch {
    return [...SEED];
  }
}

function savePhrases(phrases: string[]): void {
  try {
    globalThis.localStorage?.setItem(
      STORAGE_KEY,
      JSON.stringify(phrases.slice(-MAX_PHRASES)),
    );
  } catch {
    // Live suggestions still work from memory.
  }
}

let cache = loadPhrases();

export function rememberComposerGhostPhrase(text: string): void {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length < 4) return;
  const next = [...cache.filter((item) => item !== cleaned), cleaned];
  cache = next.slice(-MAX_PHRASES);
  savePhrases(cache);
}

/** Suffix to show as ghost text, or empty. */
export function suggestGhostSuffix(beforeCursor: string): string {
  const text = beforeCursor.replace(/\u00a0/g, " ");
  if (!text.trim()) return "";
  const trailingSpace = /\s$/.test(text);
  const words = text.trim().split(/\s+/);
  if (words.length === 0) return "";
  const last = words[words.length - 1] ?? "";
  if (!trailingSpace && last.length < 2) return "";

  const phrases = cache;
  for (let take = Math.min(3, words.length); take >= 1; take -= 1) {
    const prefix = words.slice(-take).join(" ");
    const hit = phrases.find((phrase) =>
      phrase.toLowerCase().startsWith(prefix.toLowerCase()),
    );
    if (!hit || hit.length <= prefix.length) continue;
    const rest = hit.slice(prefix.length);
    if (trailingSpace) {
      return rest.replace(/^\s+/, "");
    }
    return rest;
  }
  return "";
}
