import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

import { suggestGhostSuffix } from "./composerGhostComplete";
import { suggestGhostFromLocalModel } from "./ghostCompleteLocal";

const key = new PluginKey<{ suffix: string }>("composerGhostComplete");

export function createGhostCompleteExtension(options: {
  isEnabled: () => boolean;
  isAutocompleteOpen?: () => boolean;
}) {
  return Extension.create({
    name: "composerGhostComplete",
    addProseMirrorPlugins() {
      let debounce: ReturnType<typeof setTimeout> | undefined;
      let abort: AbortController | undefined;
      return [
        new Plugin({
          key,
          view() {
            return {
              update(next) {
                if (!options.isEnabled()) return;
                if (options.isAutocompleteOpen?.()) return;
                const t1 = key.getState(next.state)?.suffix ?? "";
                if (t1) return;
                const $from = next.state.selection.$from;
                if (
                  !next.state.selection.empty ||
                  !$from.parent.inlineContent
                ) {
                  return;
                }
                const before = next.state.doc.textBetween(
                  $from.start(),
                  $from.pos,
                  " ",
                  " ",
                );
                const pos = next.state.selection.from;
                abort?.abort();
                if (debounce) clearTimeout(debounce);
                debounce = setTimeout(() => {
                  abort = new AbortController();
                  const timer = window.setTimeout(() => abort?.abort(), 400);
                  void suggestGhostFromLocalModel(before, abort.signal)
                    .then((suffix) => {
                      if (!suffix) return;
                      if (next.state.selection.from !== pos) return;
                      next.dispatch(
                        next.state.tr.setMeta(key, { suffix, fromLocal: true }),
                      );
                    })
                    .catch(() => undefined)
                    .finally(() => window.clearTimeout(timer));
                }, 300);
              },
              destroy() {
                if (debounce) clearTimeout(debounce);
                abort?.abort();
              },
            };
          },
          state: {
            init: () => ({ suffix: "" }),
            apply(tr, _value, _oldState, newState) {
              const meta = tr.getMeta(key) as
                | { suffix?: string; fromLocal?: boolean }
                | undefined;
              if (meta && meta.suffix === "") return { suffix: "" };
              if (meta?.fromLocal && meta.suffix) {
                return { suffix: meta.suffix };
              }
              if (!options.isEnabled()) return { suffix: "" };
              if (options.isAutocompleteOpen?.()) return { suffix: "" };
              if (!newState.selection.empty) return { suffix: "" };
              const $from = newState.selection.$from;
              if (!$from.parent.inlineContent) return { suffix: "" };
              if (
                $from.parent.type.name === "codeBlock" ||
                $from.parent.type.name === "code"
              ) {
                return { suffix: "" };
              }
              const before = newState.doc.textBetween(
                $from.start(),
                $from.pos,
                " ",
                " ",
              );
              return { suffix: suggestGhostSuffix(before) };
            },
          },
          props: {
            decorations(state) {
              const suffix = key.getState(state)?.suffix ?? "";
              if (!suffix) return DecorationSet.empty;
              const pos = state.selection.from;
              const widget = Decoration.widget(
                pos,
                () => {
                  const el = document.createElement("span");
                  el.className = "composer-ghost-complete";
                  el.textContent = suffix;
                  el.setAttribute("aria-hidden", "true");
                  return el;
                },
                { side: 1 },
              );
              return DecorationSet.create(state.doc, [widget]);
            },
            handleKeyDown(view, event) {
              if (!options.isEnabled()) return false;
              if (options.isAutocompleteOpen?.()) return false;
              const suffix = key.getState(view.state)?.suffix ?? "";
              if (event.key === "Escape" && suffix) {
                event.preventDefault();
                view.dispatch(view.state.tr.setMeta(key, { suffix: "" }));
                return true;
              }
              const $from = view.state.selection.$from;
              const atLineEnd =
                $from.parent.inlineContent &&
                $from.parentOffset === $from.parent.content.size;
              const takeRight =
                event.key === "ArrowRight" && !event.shiftKey && atLineEnd;
              const takeTab = event.key === "Tab" && !event.shiftKey;
              if ((!takeTab && !takeRight) || !suffix) {
                return false;
              }
              event.preventDefault();
              const { from } = view.state.selection;
              view.dispatch(view.state.tr.insertText(suffix, from, from));
              return true;
            },
          },
        }),
      ];
    },
  });
}
