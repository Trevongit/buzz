import * as React from "react";

import { isReaderAgentName } from "./listenSpeech";

export const LISTEN_SUMMARY_AGENT_KEY = "buzz.desktop.listen-summary-agent";

export type ListenSummaryAgentPref = {
  pubkey: string;
  name: string;
};

let memory: ListenSummaryAgentPref | null | undefined;

function storage(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

function parsePref(raw: string | null): ListenSummaryAgentPref | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<ListenSummaryAgentPref>;
    const pubkey = parsed.pubkey?.trim().toLowerCase() ?? "";
    const name = parsed.name?.trim() ?? "";
    if (!pubkey || !name) return null;
    return { pubkey, name };
  } catch {
    return null;
  }
}

export function readListenSummaryAgentPreference(): ListenSummaryAgentPref | null {
  if (memory !== undefined) return memory;
  memory = parsePref(storage()?.getItem(LISTEN_SUMMARY_AGENT_KEY) ?? null);
  return memory;
}

export function writeListenSummaryAgentPreference(
  pref: ListenSummaryAgentPref | null,
): void {
  memory = pref;
  const store = storage();
  if (!store) return;
  try {
    if (!pref) {
      store.removeItem(LISTEN_SUMMARY_AGENT_KEY);
      return;
    }
    store.setItem(
      LISTEN_SUMMARY_AGENT_KEY,
      JSON.stringify({
        pubkey: pref.pubkey.trim().toLowerCase(),
        name: pref.name.trim(),
      }),
    );
  } catch {
    // Quota / private-mode — in-memory still holds for this session.
  }
}

/** Test-only. */
export function resetListenSummaryAgentPreferenceForTests(): void {
  memory = undefined;
}

export function pickListenSummaryAgent<
  T extends { pubkey: string; name: string },
>(agents: T[]): T | undefined {
  const pref = readListenSummaryAgentPreference();
  if (pref) {
    const byKey = agents.find(
      (agent) => agent.pubkey.toLowerCase() === pref.pubkey,
    );
    if (byKey) return byKey;
    const byName = agents.find(
      (agent) => agent.name.trim().toLowerCase() === pref.name.toLowerCase(),
    );
    if (byName) return byName;
  }
  return agents.find((agent) => isReaderAgentName(agent.name));
}

export function useListenSummaryAgentPreference(): [
  ListenSummaryAgentPref | null,
  (pref: ListenSummaryAgentPref | null) => void,
] {
  const [pref, setPref] = React.useState(readListenSummaryAgentPreference);
  const persist = React.useCallback((next: ListenSummaryAgentPref | null) => {
    writeListenSummaryAgentPreference(next);
    setPref(next);
  }, []);
  return [pref, persist];
}
