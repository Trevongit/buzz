const OLLAMA = "http://127.0.0.1:11434";

/** A draft is a paragraph when it is long enough to rewrite, not a short line. */
export function isParagraphDraft(text: string): boolean {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length < 80) return false;
  const sentences = cleaned
    .split(/[.!?]+\s+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return sentences.length >= 2 || cleaned.length >= 120;
}

function sameMeaning(original: string, offered: string): boolean {
  const a = original.replace(/\s+/g, " ").trim().toLowerCase();
  const b = offered.replace(/\s+/g, " ").trim().toLowerCase();
  return a.length > 0 && a === b;
}

export async function suggestParagraphOffer(
  draft: string,
  signal: AbortSignal,
): Promise<string> {
  const prompt = draft.replace(/\s+/g, " ").trim();
  if (!isParagraphDraft(prompt)) return "";
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const bridged = await invoke<string>("paragraph_offer", { draft: prompt });
    const text = (bridged ?? "").replace(/\s+/g, " ").trim();
    if (text && !sameMeaning(prompt, text) && text.length <= 800) {
      return text;
    }
  } catch {
    // Fall through to Ollama if the Desktop bridge is missing.
  }
  if (signal.aborted) return "";
  const tags = await fetch(`${OLLAMA}/api/tags`, { signal });
  if (!tags.ok) return "";
  const body = (await tags.json()) as { models?: { name?: string }[] };
  const model = body.models?.find((item) => item.name)?.name;
  if (!model) return "";
  const response = await fetch(`${OLLAMA}/api/generate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    signal,
    body: JSON.stringify({
      model,
      prompt: `Rewrite this paragraph so it keeps the same meaning, is clearer, and drops repeated words. Do not add new facts. Do not comment. Output only the rewritten paragraph.\n\n${prompt}`,
      stream: false,
      options: { num_predict: 180, temperature: 0.2 },
    }),
  });
  if (!response.ok) return "";
  const generated = (await response.json()) as { response?: string };
  const text = (generated.response ?? "").replace(/\s+/g, " ").trim();
  if (!text || text.length > 800 || sameMeaning(prompt, text)) return "";
  return text;
}
