const OLLAMA = "http://127.0.0.1:11434";

export async function suggestGhostFromLocalModel(
  beforeCursor: string,
  signal: AbortSignal,
): Promise<string> {
  const prompt = beforeCursor.trim();
  if (prompt.length < 8) return "";
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const bridged = await invoke<string>("ghost_complete_local", {
      before: prompt,
    });
    if (bridged?.trim()) {
      const text = bridged.replace(/\s+/g, " ").trim();
      if (text && text.length <= 80) {
        return text.startsWith(" ") ? text : ` ${text}`;
      }
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
      prompt: `Finish the same sentence with at most eight words. Do not comment. Do not reply. Do not explain. Output only the missing words.\n\n${prompt}`,
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
