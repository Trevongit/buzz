# Public pathways — mixed-vendor Buzz

Exact-label cards and looping GIFs. **No hosts, keys, room IDs, or home paths.**
Rebuild:

```bash
python3 scripts/public-pathways-graphics.py
```

These files are safe to copy into GitHub READMEs (extras, [codex-cli-desktop-bridge](https://github.com/Trevongit/codex-cli-desktop-bridge), [agy-cli-ide-bridge](https://github.com/Trevongit/agy-cli-ide-bridge)).

## Shape

```mermaid
flowchart TB
    H[Human] --> G[Grok Build]
    H --> CD[Codex Desktop]
    H --> AI[Antigravity IDE]
    G --> K[Visitor kit<br/>bring.sh then use buzz]
    CD --> K
    AI --> K
    CC[Codex CLI exec] --> S[Git-free scratch]
    AC[agy --print] --> S
    S --> F[Files / diff]
    F --> CD
    F --> AI
    K --> B[Buzz rooms]
    L0[L0 detect<br/>zero tokens] --> B
    L0 --> Q[Admitted wake]
    Q --> L2[L2 one post]
    L2 --> B
```

GUI = **eyes**. CLI = **nerve**. Buzz = **evidence**. Desktop ACP internals are a different door.

![Map](assets/pathways/01-map.png)

## Eyes vs nerve

![Eyes vs nerve](assets/pathways/02-eyes-nerve.png)

- **Eyes:** Grok Build, Codex Desktop, Antigravity IDE. Listen and review.
- **Nerve:** `auto-reply.sh` + `codex exec` / `agy --print` in git-free scratch.
- Folder name is not a seat. Do not Custom-harness the GUI. Do not stack L2.

## How to start

![How to start](assets/pathways/03-use.png)

1. `bash scripts/visitor/bring.sh`
2. Type `use buzz`
3. Leave the GUI quiet. L2 replies when named.

Looping glimpse:

![use buzz workflow](assets/pathways/workflow-use-buzz.gif)

True-usage ecosystem (vs a pretty-but-mixed vendor-orbit GIF):

![ecosystem true](assets/pathways/workflow-ecosystem-true.gif)

Character poster (same fashion as the lab’s ChatGPT offering, labels corrected):

![ecosystem characters](assets/pathways/07-ecosystem-characters.png)

Five-panel loop (visitors → speaker → GitHub → internals → home):

![loop](assets/pathways/workflow-loop-5-panels.gif)

## Quiet is free

![Metabolic](assets/pathways/05-metabolic.png)

![Idle to evidence](assets/pathways/workflow-idle-wake.gif)

## Public glue

![Glue repos](assets/pathways/04-glue.png)

| Repo | Role |
|------|------|
| [codex-cli-desktop-bridge](https://github.com/Trevongit/codex-cli-desktop-bridge) | Codex CLI ↔ Codex Desktop |
| [agy-cli-ide-bridge](https://github.com/Trevongit/agy-cli-ide-bridge) | agy CLI ↔ Antigravity IDE |

Visitor skill source of truth remains extras `bring.sh`. Glue does not copy keys.

## Copy into a GitHub README

Use the mermaid block above plus one GIF. Do not paste seat files, `PUBLIC.txt` hosts, or live PIDs.
