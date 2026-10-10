import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet, type EditorView } from "@tiptap/pm/view";

import { composerExtras } from "./composerExtras";
import { suggestGhostSuffix } from "./composerGhostComplete";
import { suggestGhostFromLocalModel } from "./ghostCompleteLocal";
import { isParagraphDraft, suggestParagraphOffer } from "./paragraphOffer";
import { spellRepairLine } from "./spellRepairLine";

const key = new PluginKey<{
  suffix: string;
  repair: boolean;
  fromLocal: boolean;
  paragraph: boolean;
}>("composerGhostComplete");

function canDispatch(view: EditorView): boolean {
  try {
    const v = view as EditorView & {
      isDestroyed?: boolean;
      composing?: boolean;
    };
    if (v.isDestroyed) return false;
    if (v.composing) return false;
    if (!view.dom?.isConnected) return false;
    return true;
  } catch {
    return false;
  }
}

function safeDispatch(view: EditorView, meta: Record<string, unknown>) {
  if (!canDispatch(view)) return;
  try {
    view.dispatch(view.state.tr.setMeta(key, meta));
  } catch {
    // A failed decoration must never take the window down.
  }
}

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
                try {
                  if (!canDispatch(next)) return;
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
                  let hasMention = false;
                  $from.parent.forEach((node) => {
                    if (node.type.name === "mention") hasMention = true;
                  });
                  const line = $from.parent.textContent;
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
                    const timer = window.setTimeout(() => abort?.abort(), 4500);
                    const stillHere = () => next.state.selection.from === pos;
                    void (async () => {
                      const extras = composerExtras();
                      if (extras.phrases) {
                        const phrase = suggestGhostSuffix(before);
                        if (phrase && stillHere() && canDispatch(next)) {
                          safeDispatch(next, { suffix: phrase });
                          return;
                        }
                      }
                      if (extras.repair && !hasMention) {
                        const repaired = await spellRepairLine(line);
                        if (repaired && stillHere() && canDispatch(next)) {
                          safeDispatch(next, {
                            suffix: repaired,
                            repair: true,
                          });
                          return;
                        }
                      }
                      const draft = next.state.doc.textBetween(
                        0,
                        next.state.doc.content.size,
                        "\n",
                        " ",
                      );
                      if (
                        extras.paragraphOffer &&
                        !hasMention &&
                        isParagraphDraft(draft)
                      ) {
                        const offered = await suggestParagraphOffer(
                          draft,
                          abort.signal,
                        );
                        if (offered && stillHere() && canDispatch(next)) {
                          safeDispatch(next, {
                            suffix: offered,
                            paragraph: true,
                          });
                          return;
                        }
                      }
                      if (!extras.ember) return;
                      const suffix = await suggestGhostFromLocalModel(
                        before,
                        abort.signal,
                      );
                      if (!suffix || !stillHere() || !canDispatch(next)) return;
                      safeDispatch(next, { suffix, fromLocal: true });
                    })()
                      .catch(() => undefined)
                      .finally(() => window.clearTimeout(timer));
                  }, composerExtras().ghostPauseMs);
                } catch {
                  // Ghost complete must not take the window down.
                }
              },
              destroy() {
                if (debounce) clearTimeout(debounce);
                abort?.abort();
              },
            };
          },
          state: {
            init: () => ({
              suffix: "",
              repair: false,
              fromLocal: false,
              paragraph: false,
            }),
            apply(tr, value, _oldState, _newState) {
              const empty = {
                suffix: "",
                repair: false,
                fromLocal: false,
                paragraph: false,
              };
              try {
                const meta = tr.getMeta(key) as
                  | {
                      suffix?: string;
                      fromLocal?: boolean;
                      repair?: boolean;
                      paragraph?: boolean;
                    }
                  | undefined;
                if (meta && meta.suffix === "") return empty;
                if (meta?.paragraph && meta.suffix) {
                  return {
                    suffix: meta.suffix,
                    repair: false,
                    fromLocal: false,
                    paragraph: true,
                  };
                }
                if (meta?.repair && meta.suffix) {
                  return {
                    suffix: meta.suffix,
                    repair: true,
                    fromLocal: false,
                    paragraph: false,
                  };
                }
                if (meta?.fromLocal && meta.suffix) {
                  return {
                    suffix: meta.suffix,
                    repair: false,
                    fromLocal: true,
                    paragraph: false,
                  };
                }
                if (meta?.suffix) {
                  return {
                    suffix: meta.suffix,
                    repair: false,
                    fromLocal: false,
                    paragraph: false,
                  };
                }
                if (!options.isEnabled()) return empty;
                if (tr.docChanged) return empty;
                return value;
              } catch {
                return empty;
              }
            },
          },
          props: {
            decorations(state) {
              try {
                const pluginState = key.getState(state);
                const suffix = pluginState?.suffix ?? "";
                if (!suffix) return DecorationSet.empty;
                const pos = state.selection.from;
                const widget = Decoration.widget(
                  pos,
                  () => {
                    const el = document.createElement("span");
                    el.className = pluginState?.paragraph
                      ? "composer-ghost-paragraph"
                      : pluginState?.repair
                        ? "composer-ghost-repair"
                        : pluginState?.fromLocal
                          ? "composer-ghost-ember"
                          : "composer-ghost-complete";
                    const preview = suffix.replace(/\s+/g, " ");
                    el.textContent = pluginState?.paragraph
                      ? ` ↷ ${preview.slice(0, 72)}${preview.length > 72 ? "…" : ""}`
                      : pluginState?.repair
                        ? ` → ${suffix}`
                        : suffix;
                    el.setAttribute("aria-hidden", "true");
                    return el;
                  },
                  { side: 1 },
                );
                return DecorationSet.create(state.doc, [widget]);
              } catch {
                return DecorationSet.empty;
              }
            },
            handleKeyDown(view, event) {
              try {
                if (!options.isEnabled()) return false;
                if (options.isAutocompleteOpen?.()) return false;
                const pluginState = key.getState(view.state);
                const suffix = pluginState?.suffix ?? "";
                if (event.key === "Escape" && suffix) {
                  event.preventDefault();
                  safeDispatch(view, { suffix: "" });
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
                if (!canDispatch(view)) return false;
                if (pluginState?.paragraph) {
                  if (!takeTab) return false;
                  const end = view.state.doc.content.size;
                  view.dispatch(view.state.tr.insertText(suffix, 0, end));
                  return true;
                }
                if (pluginState?.repair) {
                  const start = $from.start();
                  const end = start + $from.parent.content.size;
                  view.dispatch(view.state.tr.insertText(suffix, start, end));
                  return true;
                }
                const { from } = view.state.selection;
                view.dispatch(view.state.tr.insertText(suffix, from, from));
                return true;
              } catch {
                return false;
              }
            },
          },
        }),
      ];
    },
  });
}
