import assert from "node:assert/strict";
import test from "node:test";

import {
  rememberComposerGhostPhrase,
  suggestGhostSuffix,
} from "./composerGhostComplete.ts";

test("ghost complete is quiet on a short prefix", () => {
  assert.equal(suggestGhostSuffix(""), "");
  assert.equal(suggestGhostSuffix("e"), "");
});

test("ghost complete finishes a seeded house phrase", () => {
  const suffix = suggestGhostSuffix("extras st");
  assert.equal(suffix.toLowerCase().startsWith("ays buzz"), true);
});

test("remembered phrases beat the seed for a later prefix", () => {
  rememberComposerGhostPhrase("named chair stays empty");
  const suffix = suggestGhostSuffix("named ch");
  assert.ok(suffix.toLowerCase().includes("air"));
});
