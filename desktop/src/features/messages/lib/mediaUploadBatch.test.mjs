import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_MEDIA_FILES_PER_MESSAGE,
  capMediaFiles,
  isRetryableMediaUploadError,
  runWithConcurrency,
  withMediaUploadRetries,
} from "./mediaUploadBatch.ts";

test("capMediaFiles keeps a ten-file burst", () => {
  const files = Array.from({ length: 10 }, (_, i) => i);
  assert.deepEqual(capMediaFiles(files), { files, dropped: 0 });
});

test("capMediaFiles drops files past the per-message cap", () => {
  const files = Array.from(
    { length: MAX_MEDIA_FILES_PER_MESSAGE + 5 },
    (_, i) => i,
  );
  const capped = capMediaFiles(files);
  assert.equal(capped.files.length, MAX_MEDIA_FILES_PER_MESSAGE);
  assert.equal(capped.dropped, 5);
  assert.equal(capped.files[0], 0);
  assert.equal(capped.files.at(-1), MAX_MEDIA_FILES_PER_MESSAGE - 1);
});

test("isRetryableMediaUploadError matches the composer 429 text", () => {
  assert.equal(
    isRetryableMediaUploadError("Error: relay rate-limited: quota exceeded"),
    true,
  );
  assert.equal(
    isRetryableMediaUploadError("upload concurrency limit reached"),
    true,
  );
  assert.equal(
    isRetryableMediaUploadError("Please choose an image file."),
    false,
  );
});

test("withMediaUploadRetries succeeds after a quota 429", async () => {
  let calls = 0;
  const value = await withMediaUploadRetries(async () => {
    calls += 1;
    if (calls < 3) {
      throw new Error("relay rate-limited: quota exceeded");
    }
    return "ok";
  });
  assert.equal(value, "ok");
  assert.equal(calls, 3);
});

test("runWithConcurrency never runs more workers than the limit", async () => {
  let inFlight = 0;
  let maxInFlight = 0;
  const items = Array.from({ length: 10 }, (_, i) => i);
  await runWithConcurrency(items, 4, async () => {
    inFlight += 1;
    maxInFlight = Math.max(maxInFlight, inFlight);
    await new Promise((resolve) => {
      setTimeout(resolve, 5);
    });
    inFlight -= 1;
  });
  assert.equal(maxInFlight, 4);
});
