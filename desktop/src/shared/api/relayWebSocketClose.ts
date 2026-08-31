import { invoke } from "@tauri-apps/api/core";

/**
 * Remove the connection from the native manager before waiting for its socket
 * task to stop. The command is bounded and idempotent; failures mean the
 * process is already tearing down or the socket is already gone.
 */
export function closeWebSocket(
  id: number,
  reason: string,
  invokeFn: typeof invoke = invoke,
): Promise<void> {
  return invokeFn("plugin:websocket|disconnect", { id }).then(
    () => undefined,
    (err) => {
      console.debug(`closeWebSocket(${id}, ${reason}) rejected:`, err);
    },
  );
}

/** Serialize native disconnect so a new connect does not race a close. */
export class NativeSocketCloser {
  private pending: Promise<void> | null = null;

  begin(id: number, reason: string) {
    this.pending = (this.pending ?? Promise.resolve()).then(() =>
      closeWebSocket(id, reason),
    );
  }

  async wait() {
    if (this.pending === null) return;
    await this.pending;
    this.pending = null;
  }

  discard(id: number, reason: string) {
    return closeWebSocket(id, reason);
  }
}

export function closeAllWebSockets(
  invokeFn: typeof invoke = invoke,
): Promise<void> {
  return invokeFn("plugin:websocket|disconnect_all").then(
    () => undefined,
    (err) => {
      console.debug("closeAllWebSockets() rejected:", err);
    },
  );
}
