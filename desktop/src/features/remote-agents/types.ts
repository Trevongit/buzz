/** Host-seat-location types for Remote Agents (layer 3). */

export type HostAgentHealth = "online" | "stale" | "stopped" | "unknown";

export type RemoteAgentPreset =
  | "co-lab-gemma"
  | "co-lab-watch"
  | "push-nerve"
  | "status-only";

export type HostAgentSeat = {
  seat_id: string;
  pubkey_hint?: string;
  runtimes?: string[];
  model?: string;
  channels?: string[];
  expected_online?: boolean;
  notes?: string;
  unit_name?: string;
  unit_pid?: number | null;
  unit_alive?: boolean;
  surface_root?: string;
  surface_kind?: string;
};

export type HostAgentStatus = {
  ok?: boolean;
  schema?: string;
  host_id?: string;
  host_role?: string;
  ts?: number;
  relay?: { http_code?: string; url?: string; ok?: boolean };
  ollama?: { ok?: boolean; models?: string[] };
  watchers?: { process_matches?: number; unit_pids?: number };
  seats?: HostAgentSeat[];
  error?: string;
  raw?: string;
};

export type RemoteHostConnection = {
  /** Display name, e.g. asus-g501vw */
  label: string;
  /** Base URL, e.g. http://127.0.0.1:8787 (SSH tunnel) or http://100.x.y.z:8787 */
  baseUrl: string;
  /** Bearer token for host-agentd — stored locally (v1); prefer OS keyring later */
  token: string;
  /** Default channel UUID for arm (e.g. agent-metabolism) */
  defaultRoom?: string;
};

export type RemoteAgentCardModel = {
  seatId: string;
  hostId: string;
  hostRole: string;
  model: string;
  runtimes: string[];
  channels: string[];
  expectedOnline: boolean;
  health: HostAgentHealth;
  healthLabel: string;
  relayOk: boolean;
  ollamaOk: boolean;
};

export const REMOTE_AGENT_PRESETS: {
  id: RemoteAgentPreset;
  label: string;
  description: string;
}[] = [
  {
    id: "co-lab-gemma",
    label: "Co-lab + Gemma",
    description: "Watch + local-llm drafts (gemma3:4b)",
  },
  {
    id: "co-lab-watch",
    label: "Co-lab watch only",
    description: "Watch/admit without model cortex",
  },
  {
    id: "push-nerve",
    label: "Push nerve / Codex@home",
    description: "Codex-style push L0 on the host",
  },
  {
    id: "status-only",
    label: "Status only",
    description: "No process — refresh board only",
  },
];
