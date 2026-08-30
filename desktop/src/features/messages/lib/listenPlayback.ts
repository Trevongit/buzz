import { invokeTauri } from "@/shared/api/tauri";

function canUseWebSpeech(): boolean {
  return typeof window.speechSynthesis?.speak === "function";
}

function speakWithWebSpeech(text: string) {
  const synth = window.speechSynthesis;
  synth.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  synth.speak(utterance);
}

function nativeListenError(error: unknown): Error {
  if (error instanceof Error && error.message.trim()) return error;
  return new Error("Pocket TTS failed. Check Voice settings.");
}

/** Speak through Pocket TTS. WebKitGTK has no speechSynthesis fallback. */
export async function speakListenText(text: string): Promise<void> {
  try {
    await invokeTauri("speak_listen_text", { text });
  } catch (error) {
    if (canUseWebSpeech()) {
      speakWithWebSpeech(text);
      return;
    }
    throw nativeListenError(error);
  }
}
