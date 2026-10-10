# Composer extras contract

Shared knobs for the daily origin-plus composer and a second-client page in
`buzz-app`. One file. Two glasses.

Path: `~/.buzz-dev/composer-extras.json`

The control-room page at `http://127.0.0.1:8878/composer.html` writes it.
Origin-plus Desktop reads it every few seconds. A local page plugin in
`buzz-app` may read and write the same file. It must not put a relay URL, a
key, or a harness in the file. It must not copy origin-plus source.

Schema: `http://127.0.0.1:8878/composer-extras.schema.json`

## Fields

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `ghostPauseMs` | number 500–8000 | 2500 | Wait before gray / lime / amber / paragraph |
| `spellPauseMs` | number 500–8000 | 2500 | Wait before red-wave underlines |
| `phrases` | bool | true | Gray: finish a remembered phrase |
| `repair` | bool | true | Lime: dictionary rewrite of the current line |
| `ember` | bool | true | Amber: local model finishes a short sentence |
| `paragraphOffer` | bool | true | Teal: one clearer paragraph. Tab takes it. Keep typing and it goes away. Skips amber on long drafts. |
| `spellDict` | `en_AU` / `en_GB` / `en_US` | `en_AU` | House English is Australian |
| `spellUnderlines` | bool | true | Wavy mark on a miss |
| `spellSuggestCount` | 1–5 | 5 | Hover list length |
| `spellTab` | bool | true | Tab first pick, Shift+Tab second |
| `spellLearn` | bool | true | Learn word on the hover |

Unknown keys are ignored. Missing keys take the defaults above.

## Exact-text

Search, npubs, and code stay exact. Origin-plus search (`SearchDialogInputRow`)
already sets `autoCorrect=off`, `autoCapitalize=none`, `spellCheck=false`.
Shared `input` and `textarea` do the same. Composer code spans and code blocks
set `spellcheck=false`. The composer body is the writing field. The red wave
lives there. Paragraph offer never runs on a mention line.

## Limits

- Do not start `just web` or `just desktop` from a chair.
- A person opens buzz-app by hand, with their own public pin, in a session they
  are watching.
- Origin-plus stays the daily window.
