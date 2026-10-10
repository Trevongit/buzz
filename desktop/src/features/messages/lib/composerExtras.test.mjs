import assert from "node:assert/strict";
import test from "node:test";

import { composerExtras, DEFAULT_COMPOSER_EXTRAS } from "./composerExtras.ts";

test("composer extras default to a 2.5s pause with all layers on", () => {
  assert.deepEqual(composerExtras(), DEFAULT_COMPOSER_EXTRAS);
  assert.equal(DEFAULT_COMPOSER_EXTRAS.spellDict, "en_AU");
  assert.equal(DEFAULT_COMPOSER_EXTRAS.spellSuggestCount, 5);
  assert.equal(DEFAULT_COMPOSER_EXTRAS.spellUnderlines, true);
  assert.equal(DEFAULT_COMPOSER_EXTRAS.paragraphOffer, true);
});
