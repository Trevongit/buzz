import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet, type EditorView } from "@tiptap/pm/view";

import { composerExtras } from "./composerExtras";
import {
  matchSpellCase,
  missAtOffset,
  rangesForMisses,
  spellSuggestWords,
} from "./spellCheckWords";

const key = new PluginKey<{ suggestions: Record<string, string[]> }>(
  "composerSpellUnderline",
);

const HOVER_ID = "composer-spell-hover";

const SKIP = new Set(["mention", "code", "codeBlock", "customEmoji"]);

function canDispatch(view: EditorView): boolean {
  try {
    const v = view as EditorView & { isDestroyed?: boolean };
    if (v.isDestroyed) return false;
    if (!view.dom?.isConnected) return false;
    return true;
  } catch {
    return false;
  }
}

function composerPlainText(state: { doc: EditorView["state"]["doc"] }): string {
  const parts: string[] = [];
  state.doc.descendants((node) => {
    if (SKIP.has(node.type.name)) return false;
    if (node.isText && node.text) parts.push(node.text);
    return true;
  });
  return parts.join(" ");
}

type HoverTarget = { from: number; to: number; word: string };

function hideSpellHover() {
  document.getElementById(HOVER_ID)?.remove();
}

function suggestionsFor(
  state: { suggestions: Record<string, string[]> } | undefined,
  word: string,
): string[] {
  const list = state?.suggestions[word.toLowerCase()] ?? [];
  const cap = Math.min(5, Math.max(1, composerExtras().spellSuggestCount));
  return list.slice(0, cap);
}

function replaceMiss(
  view: EditorView,
  from: number,
  to: number,
  word: string,
  suggestion: string,
) {
  const current = view.state.doc.textBetween(from, to, "", "");
  if (current.toLowerCase() !== word.toLowerCase()) return;
  const next = matchSpellCase(current, suggestion);
  view.dispatch(view.state.tr.insertText(next, from, to));
}

function forgetMiss(view: EditorView, word: string) {
  const current = { ...(key.getState(view.state)?.suggestions ?? {}) };
  delete current[word.toLowerCase()];
  view.dispatch(view.state.tr.setMeta(key, { suggestions: current }));
}

async function learnMiss(view: EditorView, word: string) {
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("spell_learn_word", { word });
  if (!canDispatch(view)) return;
  forgetMiss(view, word);
}

function showSpellHover(
  anchor: HTMLElement,
  target: HoverTarget,
  suggestions: string[],
  onPick: (suggestion: string) => void,
  onLearn: () => void,
) {
  const extras = composerExtras();
  hideSpellHover();
  if (suggestions.length === 0 && !extras.spellLearn) return;
  const box = document.createElement("div");
  box.id = HOVER_ID;
  box.className = "composer-spell-hover";
  box.setAttribute("role", "listbox");
  box.setAttribute("aria-label", "Spelling suggestions");
  suggestions.forEach((suggestion, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "composer-spell-hover-item";
    button.setAttribute("role", "option");
    const label = document.createElement("span");
    label.textContent = matchSpellCase(target.word, suggestion);
    button.append(label);
    if (extras.spellTab && (index === 0 || index === 1)) {
      const hint = document.createElement("span");
      hint.className = "composer-spell-hover-hint";
      hint.textContent = index === 0 ? "Tab" : "Shift+Tab";
      button.append(hint);
    }
    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
      onPick(suggestion);
      hideSpellHover();
    });
    box.append(button);
  });
  if (extras.spellLearn) {
    const learn = document.createElement("button");
    learn.type = "button";
    learn.className = "composer-spell-hover-learn";
    learn.textContent = "Learn word";
    learn.addEventListener("mousedown", (event) => {
      event.preventDefault();
      onLearn();
      hideSpellHover();
    });
    box.append(learn);
  }
  document.body.append(box);
  const rect = anchor.getBoundingClientRect();
  box.style.left = `${rect.left}px`;
  box.style.top = `${rect.bottom + 4}px`;
}

function caretMiss(view: EditorView): HoverTarget | null {
  const { from, to, $from } = view.state.selection;
  if (from !== to || !$from.parent.inlineContent) return null;
  const text = $from.parent.textContent ?? "";
  const misses = new Set(
    Object.keys(key.getState(view.state)?.suggestions ?? {}),
  );
  const hit = missAtOffset(text, $from.parentOffset, misses);
  if (!hit) return null;
  const start = $from.start();
  return { word: hit.word, from: start + hit.from, to: start + hit.to };
}

export function createSpellUnderlineExtension(options: {
  isEnabled: () => boolean;
  isAutocompleteOpen?: () => boolean;
}) {
  return Extension.create({
    name: "composerSpellUnderline",
    addProseMirrorPlugins() {
      let debounce: ReturnType<typeof setTimeout> | undefined;
      let lastText = "\0";
      let hovered: HoverTarget | null = null;
      const spellingOn = () =>
        options.isEnabled() && composerExtras().spellUnderlines;
      return [
        new Plugin({
          key,
          view() {
            return {
              update(next) {
                try {
                  if (!canDispatch(next)) return;
                  if (!spellingOn()) {
                    lastText = "\0";
                    hovered = null;
                    hideSpellHover();
                    const current = key.getState(next.state)?.suggestions ?? {};
                    if (Object.keys(current).length > 0) {
                      next.dispatch(
                        next.state.tr.setMeta(key, { suggestions: {} }),
                      );
                    }
                    return;
                  }
                  const text = composerPlainText(next.state);
                  if (text === lastText) return;
                  lastText = text;
                  const snapshot = text;
                  if (debounce) clearTimeout(debounce);
                  debounce = setTimeout(() => {
                    void spellSuggestWords(snapshot)
                      .then((suggestions) => {
                        if (!canDispatch(next)) return;
                        if (composerPlainText(next.state) !== snapshot) return;
                        next.dispatch(
                          next.state.tr.setMeta(key, { suggestions }),
                        );
                      })
                      .catch(() => undefined);
                  }, composerExtras().spellPauseMs);
                } catch {
                  // Composer-only underlines must not take the window down.
                }
              },
              destroy() {
                if (debounce) clearTimeout(debounce);
                hovered = null;
                hideSpellHover();
              },
            };
          },
          state: {
            init: () => ({ suggestions: {} as Record<string, string[]> }),
            apply(tr, value) {
              const meta = tr.getMeta(key) as
                | { suggestions?: Record<string, string[]> }
                | undefined;
              if (meta?.suggestions) {
                return { suggestions: meta.suggestions };
              }
              if (!spellingOn()) return { suggestions: {} };
              return value;
            },
          },
          props: {
            decorations(state) {
              try {
                const misses = new Set(
                  Object.keys(key.getState(state)?.suggestions ?? {}),
                );
                if (misses.size === 0) return DecorationSet.empty;
                const widgets: ReturnType<typeof Decoration.inline>[] = [];
                state.doc.descendants((node, pos) => {
                  if (SKIP.has(node.type.name)) return false;
                  if (!node.isText || !node.text) return true;
                  for (const range of rangesForMisses(node.text, pos, misses)) {
                    const word = state.doc.textBetween(
                      range.from,
                      range.to,
                      "",
                      "",
                    );
                    widgets.push(
                      Decoration.inline(range.from, range.to, {
                        class: "composer-spell-miss",
                        "data-spell-word": word,
                        "data-spell-from": String(range.from),
                        "data-spell-to": String(range.to),
                      }),
                    );
                  }
                  return true;
                });
                return DecorationSet.create(state.doc, widgets);
              } catch {
                return DecorationSet.empty;
              }
            },
            handleDOMEvents: {
              mouseover(view, event) {
                try {
                  if (!spellingOn()) return false;
                  const node = event.target;
                  if (!(node instanceof Element)) return false;
                  const miss = node.closest(".composer-spell-miss");
                  if (!(miss instanceof HTMLElement)) return false;
                  const word = miss.dataset.spellWord ?? "";
                  const from = Number(miss.dataset.spellFrom);
                  const to = Number(miss.dataset.spellTo);
                  if (!word || !Number.isFinite(from) || !Number.isFinite(to)) {
                    return false;
                  }
                  hovered = { word, from, to };
                  const list = suggestionsFor(key.getState(view.state), word);
                  showSpellHover(
                    miss,
                    hovered,
                    list,
                    (suggestion) => {
                      if (!canDispatch(view)) return;
                      replaceMiss(view, from, to, word, suggestion);
                    },
                    () => {
                      void learnMiss(view, word).catch(() => undefined);
                    },
                  );
                  return false;
                } catch {
                  return false;
                }
              },
              mouseout(_view, event) {
                const node = event.target;
                if (!(node instanceof Element)) return false;
                const miss = node.closest(".composer-spell-miss");
                const next = event.relatedTarget;
                if (
                  miss &&
                  next instanceof Node &&
                  (miss.contains(next) ||
                    document.getElementById(HOVER_ID)?.contains(next))
                ) {
                  return false;
                }
                if (next instanceof Element && next.closest(`#${HOVER_ID}`)) {
                  return false;
                }
                hovered = null;
                hideSpellHover();
                return false;
              },
            },
            handleKeyDown(view, event) {
              try {
                if (!spellingOn()) return false;
                if (!composerExtras().spellTab) return false;
                if (options.isAutocompleteOpen?.()) return false;
                if (event.key !== "Tab") return false;
                if (!view.state.selection.empty) return false;
                const index = event.shiftKey ? 1 : 0;
                const target = hovered ?? caretMiss(view);
                if (!target) return false;
                const list = suggestionsFor(
                  key.getState(view.state),
                  target.word,
                );
                const suggestion = list[index];
                if (!suggestion) return false;
                event.preventDefault();
                if (!canDispatch(view)) return false;
                replaceMiss(
                  view,
                  target.from,
                  target.to,
                  target.word,
                  suggestion,
                );
                hovered = null;
                hideSpellHover();
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
