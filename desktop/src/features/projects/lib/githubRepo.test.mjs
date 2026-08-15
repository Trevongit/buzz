import assert from "node:assert/strict";
import { test } from "node:test";

import {
  githubPullsApiUrl,
  githubRepoHtmlUrl,
  parseGithubHttpsRepo,
} from "./githubRepo.ts";

test("parses public GitHub clone URLs", () => {
  assert.deepEqual(
    parseGithubHttpsRepo(
      "https://github.com/Trevongit/checkers-game-test-project.git",
    ),
    { owner: "Trevongit", repo: "checkers-game-test-project" },
  );
  assert.equal(parseGithubHttpsRepo("https://gitlab.com/a/b"), null);
  assert.equal(parseGithubHttpsRepo("http://github.com/a/b"), null);
});

test("builds the public pulls API URL", () => {
  assert.equal(
    githubPullsApiUrl(
      "https://github.com/Trevongit/checkers-game-test-project",
    ),
    "https://api.github.com/repos/Trevongit/checkers-game-test-project/pulls?state=open&per_page=30",
  );
});

test("builds the public repository page URL", () => {
  assert.equal(
    githubRepoHtmlUrl(
      "https://github.com/Trevongit/checkers-game-test-project.git",
    ),
    "https://github.com/Trevongit/checkers-game-test-project",
  );
});
