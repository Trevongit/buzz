const WORD_RE = /[A-Za-z][A-Za-z']{2,}/g;
const ENTITY_RE = /@[A-Za-z0-9][A-Za-z0-9._-]*/g;
const MAX_CHARS = 2000;

export type SpellRange = { from: number; to: number };

export type SpellHit = { word: string; from: number; to: number };

const MAX_SUGGESTIONS = 5;

/** `@name` tokens, including hyphenated seat names. Spell check skips these. */
export function entitySpans(text: string): SpellRange[] {
  const spans: SpellRange[] = [];
  ENTITY_RE.lastIndex = 0;
  let match: RegExpExecArray | null = ENTITY_RE.exec(text);
  while (match) {
    const token = match[0] ?? "";
    spans.push({ from: match.index, to: match.index + token.length });
    match = ENTITY_RE.exec(text);
  }
  return spans;
}

function insideEntity(
  start: number,
  end: number,
  spans: readonly SpellRange[],
) {
  return spans.some((span) => start < span.to && end > span.from);
}

/** Positions of dictionary misses inside `text`, using document `basePos`. */
export function rangesForMisses(
  text: string,
  basePos: number,
  misses: ReadonlySet<string>,
): SpellRange[] {
  if (!text || misses.size === 0) return [];
  const protectedSpans = entitySpans(text);
  const ranges: SpellRange[] = [];
  WORD_RE.lastIndex = 0;
  let match: RegExpExecArray | null = WORD_RE.exec(text);
  while (match) {
    const word = match[0] ?? "";
    const start = match.index;
    const end = start + word.length;
    if (
      misses.has(word.toLowerCase()) &&
      !insideEntity(start, end, protectedSpans)
    ) {
      ranges.push({ from: basePos + start, to: basePos + end });
    }
    match = WORD_RE.exec(text);
  }
  return ranges;
}

/** Title-case a suggestion when the typed word is title case. */
export function matchSpellCase(original: string, suggestion: string): string {
  const first = original[0];
  if (!first) return suggestion;
  const restIsLower = [...original.slice(1)].every(
    (ch) => ch === ch.toLowerCase(),
  );
  const firstIsUpper =
    first !== first.toLowerCase() && first === first.toUpperCase();
  if (firstIsUpper && restIsLower) {
    return suggestion.charAt(0).toUpperCase() + suggestion.slice(1);
  }
  return suggestion;
}

/** Miss whose range contains `offset`, including the caret just after the word. */
export function missAtOffset(
  text: string,
  offset: number,
  misses: ReadonlySet<string>,
): SpellHit | null {
  for (const range of rangesForMisses(text, 0, misses)) {
    if (offset >= range.from && offset <= range.to) {
      return {
        word: text.slice(range.from, range.to),
        from: range.from,
        to: range.to,
      };
    }
  }
  return null;
}

export async function spellSuggestWords(
  line: string,
): Promise<Record<string, string[]>> {
  const text = line.length > MAX_CHARS ? line.slice(0, MAX_CHARS) : line;
  if (!/[A-Za-z][A-Za-z']{2,}/.test(text)) return {};
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const raw = await invoke<Record<string, string[]>>("spell_suggest_words", {
      line: text,
    });
    if (!raw || typeof raw !== "object") return {};
    const out: Record<string, string[]> = {};
    for (const [word, list] of Object.entries(raw)) {
      if (typeof word !== "string" || word.length < 3) continue;
      const suggestions = Array.isArray(list)
        ? list
            .filter((item) => typeof item === "string" && item.length > 0)
            .slice(0, MAX_SUGGESTIONS)
        : [];
      out[word.toLowerCase()] = suggestions;
    }
    return out;
  } catch {
    return {};
  }
}

export async function spellCheckWords(line: string): Promise<string[]> {
  const text = line.length > MAX_CHARS ? line.slice(0, MAX_CHARS) : line;
  if (!/[A-Za-z][A-Za-z']{2,}/.test(text)) return [];
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const misses = await invoke<string[]>("spell_check_words", { line: text });
    return Array.isArray(misses)
      ? misses.filter((item) => typeof item === "string" && item.length > 2)
      : [];
  } catch {
    return [];
  }
}
