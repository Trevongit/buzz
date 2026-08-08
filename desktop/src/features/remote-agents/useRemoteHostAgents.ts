import * as React from "react";

import {
  HostAgentdError,
  hostAgentdArm,
  hostAgentdDisarm,
  hostAgentdStatus,
} from "./hostAgentdClient";
import { deriveRemoteAgentCards } from "./deriveRemoteAgentCards";
import {
  clearRemoteHostConnection,
  loadRemoteHostConnection,
  saveRemoteHostConnection,
} from "./remoteHostSettings";
import type {
  HostAgentStatus,
  RemoteAgentCardModel,
  RemoteAgentPreset,
  RemoteHostConnection,
} from "./types";

const POLL_MS = 15_000;

export function useRemoteHostAgents() {
  const [connection, setConnection] =
    React.useState<RemoteHostConnection | null>(() =>
      loadRemoteHostConnection(),
    );
  const [status, setStatus] = React.useState<HostAgentStatus | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [isPending, setIsPending] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [pendingSeat, setPendingSeat] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    const conn = loadRemoteHostConnection();
    setConnection(conn);
    if (!conn?.baseUrl || !conn.token) {
      setStatus(null);
      setError(null);
      return;
    }
    setIsLoading(true);
    try {
      const next = await hostAgentdStatus(conn.baseUrl, conn.token);
      setStatus(next);
      setError(null);
    } catch (err) {
      const message =
        err instanceof HostAgentdError
          ? err.message
          : err instanceof Error
            ? err.message
            : "status failed";
      setError(message);
      setStatus(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const hasConnection = Boolean(connection?.baseUrl && connection?.token);

  React.useEffect(() => {
    void refresh();
    if (!hasConnection) return;
    const id = window.setInterval(() => {
      void refresh();
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [hasConnection, refresh]);

  const saveConnection = React.useCallback(
    (conn: RemoteHostConnection) => {
      saveRemoteHostConnection(conn);
      setConnection(loadRemoteHostConnection());
      setNotice("Host connection saved");
      void refresh();
    },
    [refresh],
  );

  const clearConnection = React.useCallback(() => {
    clearRemoteHostConnection();
    setConnection(null);
    setStatus(null);
    setError(null);
    setNotice("Host connection cleared");
  }, []);

  const arm = React.useCallback(
    async (seatId: string, preset: RemoteAgentPreset, room?: string) => {
      const conn = loadRemoteHostConnection();
      if (!conn) {
        setError("Configure host connection first");
        return;
      }
      setIsPending(true);
      setPendingSeat(seatId);
      setNotice(null);
      try {
        const result = await hostAgentdArm(
          conn.baseUrl,
          conn.token,
          seatId,
          preset,
          room,
        );
        setNotice(
          result.stdout?.split("\n").find((l) => l.includes("BUZZ_HOST")) ||
            `Armed ${seatId} · ${preset}`,
        );
        setError(null);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "arm failed");
      } finally {
        setIsPending(false);
        setPendingSeat(null);
      }
    },
    [refresh],
  );

  const disarm = React.useCallback(
    async (seatId: string, preset: RemoteAgentPreset) => {
      const conn = loadRemoteHostConnection();
      if (!conn) {
        setError("Configure host connection first");
        return;
      }
      setIsPending(true);
      setPendingSeat(seatId);
      setNotice(null);
      try {
        await hostAgentdDisarm(conn.baseUrl, conn.token, seatId, preset);
        setNotice(`Disarmed ${seatId} · ${preset}`);
        setError(null);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "disarm failed");
      } finally {
        setIsPending(false);
        setPendingSeat(null);
      }
    },
    [refresh],
  );

  const cards: RemoteAgentCardModel[] = React.useMemo(
    () => deriveRemoteAgentCards(status, Boolean(error && !status)),
    [status, error],
  );

  return {
    connection,
    status,
    error,
    notice,
    isLoading,
    isPending,
    pendingSeat,
    cards,
    refresh,
    saveConnection,
    clearConnection,
    arm,
    disarm,
    setNotice,
    setError,
  };
}
