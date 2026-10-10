import assert from "node:assert/strict";
import test from "node:test";

import {
  matchSpellCase,
  missAtOffset,
  rangesForMisses,
} from "./spellCheckWords.ts";

test("rangesForMisses underlines only dictionary misses", () => {
  const misses = new Set(["seee", "teh"]);
  const ranges = rangesForMisses("this is seee and teh ok", 1, misses);
  assert.deepEqual(ranges, [
    { from: 9, to: 13 },
    { from: 18, to: 21 },
  ]);
});

test("rangesForMisses is quiet when the dictionary is empty", () => {
  assert.deepEqual(rangesForMisses("seee", 1, new Set()), []);
});

test("rangesForMisses does not underline words inside an @ entity", () => {
  const misses = new Set(["comms", "remote", "grok"]);
  const ranges = rangesForMisses(
    "@buzz-grok @comms @remote and comms",
    0,
    misses,
  );
  assert.deepEqual(ranges, [{ from: 30, to: 35 }]);
});

test("missAtOffset includes the caret just after the word", () => {
  const misses = new Set(["seee"]);
  assert.deepEqual(missAtOffset("see seee", 8, misses), {
    word: "seee",
    from: 4,
    to: 8,
  });
  assert.equal(missAtOffset("see seee", 2, misses), null);
});

test("matchSpellCase keeps a title-case typed word", () => {
  assert.equal(matchSpellCase("Shouldd", "should"), "Should");
  assert.equal(matchSpellCase("shouldd", "should"), "should");
});
