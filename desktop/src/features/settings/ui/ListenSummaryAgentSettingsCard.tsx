import * as React from "react";

import { useListenSummaryAgentPreference } from "@/features/messages/lib/listenSummaryAgentPreference";
import { listManagedAgents } from "@/shared/api/tauri";
import type { ManagedAgent } from "@/shared/api/types";

import { SettingsOptionGroup, SettingsOptionRow } from "./SettingsOptionGroup";

export function ListenSummaryAgentSettingsCard() {
  const [pref, setPref] = useListenSummaryAgentPreference();
  const [agents, setAgents] = React.useState<ManagedAgent[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    void listManagedAgents()
      .then((next) => {
        if (!cancelled) setAgents(next);
      })
      .catch(() => {
        if (!cancelled) setAgents([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const value = pref?.pubkey ?? "";

  return (
    <SettingsOptionGroup
      data-testid="settings-listen-summary-agent"
      description="Listen (summary) @-asks this managed agent in the thread. Pocket speaks when they post. Defaults to Reader-laptop when unset."
      title="Listen summary"
    >
      <SettingsOptionRow>
        <div className="min-w-0">
          <label
            className="font-medium text-foreground"
            htmlFor="settings-listen-summary-agent-select"
          >
            Agent
          </label>
          <p
            className="mt-0.5 text-sm text-muted-foreground/70"
            data-settings-subcopy
          >
            Used only for Listen (summary), not plain Listen
          </p>
        </div>
        <select
          className="h-8 max-w-56 rounded-md border border-input bg-background px-2 text-sm shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
          data-testid="settings-listen-summary-agent-select"
          id="settings-listen-summary-agent-select"
          onChange={(event) => {
            const pubkey = event.target.value;
            if (!pubkey) {
              setPref(null);
              return;
            }
            const agent = agents.find((item) => item.pubkey === pubkey);
            if (!agent) return;
            setPref({ name: agent.name, pubkey: agent.pubkey });
          }}
          value={value}
        >
          <option value="">Reader-laptop (default)</option>
          {agents.map((agent) => (
            <option key={agent.pubkey} value={agent.pubkey}>
              {agent.name}
            </option>
          ))}
        </select>
      </SettingsOptionRow>
    </SettingsOptionGroup>
  );
}
