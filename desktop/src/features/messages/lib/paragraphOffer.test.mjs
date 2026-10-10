import assert from "node:assert/strict";
import test from "node:test";

import { isParagraphDraft } from "./paragraphOffer.ts";

test("short lines are not paragraphs", () => {
  assert.equal(isParagraphDraft("colour is a word"), false);
  assert.equal(isParagraphDraft("one sentence only."), false);
});

test("two sentences of enough length count as a paragraph", () => {
  const draft =
    "The hover shows the closest spelling for the miss. Tab takes it without needing a mouse click.";
  assert.equal(draft.length >= 80, true);
  assert.equal(isParagraphDraft(draft), true);
});

test("a long run without sentence breaks still counts", () => {
  const draft = "a ".repeat(70).trim();
  assert.equal(draft.length >= 120, true);
  assert.equal(isParagraphDraft(draft), true);
});
