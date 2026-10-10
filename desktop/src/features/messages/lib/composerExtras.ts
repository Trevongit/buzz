export type ComposerExtrasPrefs = {
  ghostPauseMs: number;
  spellPauseMs: number;
  phrases: boolean;
  repair: boolean;
  ember: boolean;
  paragraphOffer: boolean;
  spellDict: "en_AU" | "en_GB" | "en_US";
  spellUnderlines: boolean;
  spellSuggestCount: number;
  spellTab: boolean;
  spellLearn: boolean;
};

export const DEFAULT_COMPOSER_EXTRAS: ComposerExtrasPrefs = {
  ghostPauseMs: 2500,
  spellPauseMs: 2500,
  phrases: true,
  repair: true,
  ember: true,
  paragraphOffer: true,
  spellDict: "en_AU",
  spellUnderlines: true,
  spellSuggestCount: 5,
  spellTab: true,
  spellLearn: true,
};

function clampPause(ms: number): number {
  if (!Number.isFinite(ms)) return 2500;
  return Math.min(8000, Math.max(500, Math.round(ms)));
}

function clampDict(
  value: string | undefined,
): ComposerExtrasPrefs["spellDict"] {
  const key = (value ?? "").trim().replace("-", "_");
  if (key === "en_GB" || key === "en_US") return key;
  return "en_AU";
}

function clampSuggest(count: number | undefined): number {
  if (!Number.isFinite(count)) return 5;
  return Math.min(5, Math.max(1, Math.round(count as number)));
}

function normalize(
  raw: Partial<ComposerExtrasPrefs> | null,
): ComposerExtrasPrefs {
  return {
    ghostPauseMs: clampPause(raw?.ghostPauseMs ?? 2500),
    spellPauseMs: clampPause(raw?.spellPauseMs ?? 2500),
    phrases: raw?.phrases !== false,
    repair: raw?.repair !== false,
    ember: raw?.ember !== false,
    paragraphOffer: raw?.paragraphOffer !== false,
    spellDict: clampDict(raw?.spellDict),
    spellUnderlines: raw?.spellUnderlines !== false,
    spellSuggestCount: clampSuggest(raw?.spellSuggestCount),
    spellTab: raw?.spellTab !== false,
    spellLearn: raw?.spellLearn !== false,
  };
}

let cache: ComposerExtrasPrefs = DEFAULT_COMPOSER_EXTRAS;
let pollStarted = false;

export function composerExtras(): ComposerExtrasPrefs {
  return cache;
}

export async function refreshComposerExtras(): Promise<ComposerExtrasPrefs> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const prefs = await invoke<Partial<ComposerExtrasPrefs>>(
      "composer_extras_prefs",
    );
    cache = normalize(prefs);
  } catch {
    // Missing file or invoke: keep last/default. Composer must stay up.
  }
  return cache;
}

export function startComposerExtrasPoll(): void {
  if (pollStarted) return;
  pollStarted = true;
  void refreshComposerExtras();
  window.setInterval(() => {
    void refreshComposerExtras();
  }, 3000);
}
