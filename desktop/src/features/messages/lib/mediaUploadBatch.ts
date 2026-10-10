/** Hard cap for one composer pick, drop, or paste. */
export const MAX_MEDIA_FILES_PER_MESSAGE = 20;

/** In-flight uploads from one composer burst. Matches the relay per-pubkey default. */
export const MEDIA_UPLOAD_CONCURRENCY = 4;

export function capMediaFiles<T>(files: T[]): { files: T[]; dropped: number } {
  if (files.length <= MAX_MEDIA_FILES_PER_MESSAGE) {
    return { files, dropped: 0 };
  }
  return {
    files: files.slice(0, MAX_MEDIA_FILES_PER_MESSAGE),
    dropped: files.length - MAX_MEDIA_FILES_PER_MESSAGE,
  };
}

export function isRetryableMediaUploadError(err: unknown): boolean {
  const msg = String(err).toLowerCase();
  return (
    msg.includes("rate-limited") ||
    msg.includes("rate limit") ||
    msg.includes("concurrency limit") ||
    msg.includes("quota exceeded")
  );
}

export async function withMediaUploadRetries<T>(
  run: () => Promise<T>,
  attempts = 4,
): Promise<T> {
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await run();
    } catch (error) {
      last = error;
      if (!isRetryableMediaUploadError(error) || i === attempts - 1) {
        throw error;
      }
      await new Promise((resolve) => {
        setTimeout(resolve, 1000 * 2 ** i);
      });
    }
  }
  throw last;
}

export async function runWithConcurrency<T>(
  items: T[],
  limit: number,
  worker: (item: T, index: number) => Promise<void>,
): Promise<void> {
  if (items.length === 0) {
    return;
  }
  let next = 0;
  const n = Math.max(1, Math.min(limit, items.length));
  await Promise.all(
    Array.from({ length: n }, async () => {
      for (;;) {
        const i = next;
        next += 1;
        if (i >= items.length) {
          return;
        }
        await worker(items[i], i);
      }
    }),
  );
}
