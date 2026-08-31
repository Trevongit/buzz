import { abortListenSummaryWait } from "@/features/messages/lib/listenReader";
import { invokeTauri } from "@/shared/api/tauri";
import { toast } from "sonner";

export type ListenPlaybackStatus = "idle" | "playing" | "paused";

const LISTEN_TOAST_ID = "listen-playback";

let status: ListenPlaybackStatus = "idle";
let lastText: string | null = null;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

function setStatus(next: ListenPlaybackStatus) {
  if (status === next) return;
  status = next;
  emit();
}

export function getListenPlaybackStatus(): ListenPlaybackStatus {
  return status;
}

export function subscribeListenPlayback(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

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

function showPlayingToast() {
  toast.message("Listening…", {
    id: LISTEN_TOAST_ID,
    duration: Number.POSITIVE_INFINITY,
    description: "Pause or stop from the Listen menu.",
    action: {
      label: "Stop",
      onClick: () => {
        void stopListenPlayback();
      },
    },
  });
}

function showPausedToast() {
  toast.message("Paused", {
    id: LISTEN_TOAST_ID,
    duration: Number.POSITIVE_INFINITY,
    description: "Resume plays this reading from the start.",
    action: {
      label: "Resume",
      onClick: () => {
        void resumeListenPlayback();
      },
    },
  });
}

async function invokeStop(): Promise<void> {
  try {
    await invokeTauri("stop_listen_text");
  } catch {
    // Nothing playing is fine.
  }
  if (canUseWebSpeech()) {
    window.speechSynthesis?.cancel();
  }
}

/** Speak through Pocket TTS. WebKitGTK has no speechSynthesis fallback. */
export async function speakListenText(text: string): Promise<void> {
  lastText = text;
  setStatus("playing");
  showPlayingToast();
  try {
    await invokeTauri("speak_listen_text", { text });
  } catch (error) {
    if (getListenPlaybackStatus() === "paused") return;
    setStatus("idle");
    toast.dismiss(LISTEN_TOAST_ID);
    if (canUseWebSpeech()) {
      speakWithWebSpeech(text);
      return;
    }
    throw nativeListenError(error);
  }
  if (getListenPlaybackStatus() === "playing") {
    setStatus("idle");
    toast.dismiss(LISTEN_TOAST_ID);
  }
}

export async function pauseListenPlayback(): Promise<void> {
  if (getListenPlaybackStatus() !== "playing") return;
  setStatus("paused");
  showPausedToast();
  await invokeStop();
}

export async function resumeListenPlayback(): Promise<void> {
  const text = lastText;
  if (!text) {
    throw new Error("Nothing paused.");
  }
  await speakListenText(text);
}

export async function stopListenPlayback(): Promise<void> {
  lastText = null;
  abortListenSummaryWait();
  setStatus("idle");
  toast.dismiss(LISTEN_TOAST_ID);
  toast.message("Stopped listening.");
  await invokeStop();
}
