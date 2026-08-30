export const RECONNECT_BASE_DELAY_MS = 1_000;
export const RECONNECT_MAX_DELAY_MS = 30_000;
export const EVENT_BATCH_MS = 16;

/**
 * Op-level timeouts tolerate degraded networks where TLS handshakes and DNS
 * resolution can take several seconds.
 */
export const AUTH_TIMEOUT_MS = 25_000;
export const HISTORY_TIMEOUT_MS = 25_000;
export const PUBLISH_TIMEOUT_MS = 25_000;

/**
 * A stability-gated reset prevents reconnect flapping from erasing backoff.
 */
export const BACKOFF_RESET_STABLE_MS = 60_000;

/** Passive liveness thresholds for the relay heartbeat stream. */
export const STALL_CHECK_INTERVAL_MS = 10_000;
// Quiet threads (no EVENT frames) used to look stalled at 60s and force a
// reconnect; the next AUTH then flaps every few seconds. Relay pings plus
// native Pong keep the socket; give inbound traffic 5 minutes before we
// declare a stall.
export const STALL_IDLE_TIMEOUT_MS = 5 * 60_000;
