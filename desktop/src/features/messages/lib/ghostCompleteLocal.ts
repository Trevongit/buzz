const OLLAMA = "http://127.0.0.1:11434";

export async function suggestGhostFromLocalModel(
  beforeCursor: string,
  signal: AbortSignal,
): Promise<string> {
  const prompt = beforeCursor.trim();
  if (prompt.length < 8) return "";
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
      prompt: `Continue this chat draft with at most eight words. Output only the continuation, no quotes.\n\n${prompt}`,
      stream: false,
      options: { num_predict: 16, temperature: 0.1 },
    }),
  });
  if (!response.ok) return "";
  const generated = (await response.json()) as { response?: string };
  const text = (generated.response ?? "").replace(/\s+/g, " ").trim();
  if (!text || text.length > 80) return "";
  return text.startsWith(" ") ? text : ` ${text}`;
}
