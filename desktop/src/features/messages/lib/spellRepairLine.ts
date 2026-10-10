export async function spellRepairLine(line: string): Promise<string> {
  const text = line.trim();
  if (text.length < 8) return "";
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const repaired = await invoke<string>("spell_repair_line", { line: text });
    if (!repaired?.trim() || repaired.trim() === text) return "";
    return repaired.trim();
  } catch {
    return "";
  }
}
