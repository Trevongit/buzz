import assert from "node:assert/strict";
import test from "node:test";

import { getSchema } from "@tiptap/core";
import { EditorState } from "@tiptap/pm/state";
import StarterKit from "@tiptap/starter-kit";

import { createGhostCompleteExtension } from "./ghostCompleteExtension.ts";

const schema = getSchema([
  StarterKit.configure({ heading: false, trailingNode: false, link: false }),
]);
const paragraph = (...content) => schema.nodes.paragraph.create(null, content);
const text = (value) => schema.text(value);
const document = (...content) => schema.nodes.doc.create(null, content);

function stateWithGhost(isEnabled) {
  const extension = createGhostCompleteExtension({ isEnabled });
  const plugins = extension.config.addProseMirrorPlugins.call({});
  return EditorState.create({
    doc: document(paragraph(text("ex"))),
    schema,
    plugins,
  });
}

test("ghost plugin apply stays empty when isEnabled throws", () => {
  const state = stateWithGhost(() => {
    throw new Error("ghost enabled check failed");
  });
  const next = state.apply(state.tr.insertText("tras ", 3));
  assert.equal(next.doc.textContent, "extras ");
});
