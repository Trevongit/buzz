import assert from "node:assert/strict";
import test from "node:test";

import { getMountedEditorDom } from "./selectionFormattingTrayEditorDom.ts";

test("returns null while the TipTap editor view is not mounted", () => {
  const editor = {
    get view() {
      return new Proxy(
        {},
        {
          get(_target, key) {
            throw new Error(`editor view cannot access ${String(key)}`);
          },
        },
      );
    },
  };

  assert.equal(getMountedEditorDom(editor), null);
});

test("returns null for the Pulse TipTap unmounted-view error", () => {
  const editor = {
    get view() {
      throw new Error(
        "[tiptap error]: The editor view is not available. Cannot access view['dom']. The editor may not be mounted yet.",
      );
    },
  };

  assert.equal(getMountedEditorDom(editor), null);
});

test("returns the editor DOM after the TipTap view mounts", () => {
  const dom = {};
  const editor = { view: { dom } };

  assert.equal(getMountedEditorDom(editor), dom);
});
