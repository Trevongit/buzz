import type {
  HostAgentHealth,
  HostAgentStatus,
  RemoteAgentCardModel,
} from "./types";

const FRESH_SECS = 60;
const STALE_SECS = 120;
const DEAD_SECS = 300;

export function deriveHealthFromStatus(
  status: HostAgentStatus | null,
  fetchError: boolean,
  nowSecs: number = Math.floor(Date.now() / 1000),
): { health: HostAgentHealth; label: string } {
  if (fetchError || !status) {
    return { health: "unknown", label: "unreachable" };
  }
  if (status.ok === false) {
    return { health: "stopped", label: status.error || "error" };
  }
  const ts = typeof status.ts === "number" ? status.ts : nowSecs;
  const age = Math.max(0, nowSecs - ts);
  const hasUnit =
    (status.watchers?.unit_pids ?? 0) > 0 ||
    (status.watchers?.process_matches ?? 0) > 0;
  const expected = (status.seats ?? []).some((s) => s.expected_online);

  if (age > DEAD_SECS) {
    return { health: "stale", label: `stale ${age}s` };
  }
  if (age > STALE_SECS) {
    return { health: "stale", label: `amber ${age}s` };
  }
  if (expected && !hasUnit && age <= FRESH_SECS) {
    return { health: "stopped", label: "expected online · no unit" };
  }
  if (hasUnit || status.relay?.ok) {
    return {
      health: "online",
      label: age <= FRESH_SECS ? "live" : `ok ${age}s`,
    };
  }
  return { health: "unknown", label: "unknown" };
}

export function deriveRemoteAgentCards(
  status: HostAgentStatus | null,
  fetchError: boolean,
): RemoteAgentCardModel[] {
  const hostId = status?.host_id || "unknown-host";
  const hostRole = status?.host_role || "home";
  const { health, label } = deriveHealthFromStatus(status, fetchError);
  const seats = status?.seats ?? [];

  if (seats.length === 0 && status && !fetchError) {
    return [
      {
        seatId: "(no seats in registry)",
        hostId,
        hostRole,
        model: "",
        runtimes: [],
        channels: [],
        expectedOnline: false,
        health,
        healthLabel: label,
        relayOk: Boolean(status.relay?.ok),
        ollamaOk: Boolean(status.ollama?.ok),
      },
    ];
  }

  return seats.map((seat) => {
    let seatHealth = health;
    let seatLabel = label;
    if (seat.unit_alive === false && seat.expected_online) {
      seatHealth = "stopped";
      seatLabel = "unit dead";
    } else if (seat.unit_alive === true) {
      seatHealth = "online";
      seatLabel = seat.unit_pid ? `pid ${seat.unit_pid}` : "unit live";
    } else if (!seat.expected_online) {
      seatHealth = "stopped";
      seatLabel = "not expected online";
    }
    return {
      seatId: seat.seat_id,
      hostId,
      hostRole,
      model: seat.model || "",
      runtimes: seat.runtimes || [],
      channels: seat.channels || [],
      expectedOnline: Boolean(seat.expected_online),
      health: seatHealth,
      healthLabel: seatLabel,
      relayOk: Boolean(status?.relay?.ok),
      ollamaOk: Boolean(status?.ollama?.ok),
    };
  });
}
