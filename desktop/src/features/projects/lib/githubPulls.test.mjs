import assert from "node:assert/strict";
import { test } from "node:test";

import { mapGithubPulls } from "./githubPulls.ts";

test("maps public GitHub pull JSON and drops junk", () => {
  assert.deepEqual(
    mapGithubPulls([
      {
        number: 3,
        title: "Show last move",
        html_url:
          "https://github.com/Trevongit/checkers-game-test-project/pull/3",
        draft: true,
        created_at: "2026-04-01T00:00:00Z",
        user: { login: "Trevongit" },
        head: { ref: "last-move" },
        base: { ref: "main" },
      },
      { title: "missing number" },
    ]),
    [
      {
        number: 3,
        title: "Show last move",
        htmlUrl:
          "https://github.com/Trevongit/checkers-game-test-project/pull/3",
        userLogin: "Trevongit",
        createdAt: 1775001600,
        draft: true,
        headRef: "last-move",
        baseRef: "main",
      },
    ],
  );
});
