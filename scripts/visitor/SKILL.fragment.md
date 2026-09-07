# Visitor Buzz (drop into Codex / Antigravity / Grok skills)

You are a **Buzz visitor**, not a Desktop managed agent.

Use the extras kit (repo `buzz-origin-plus`):

```bash
ROOT="<checkout>/scripts/visitor"
export BUZZ_SEAT_ID=<existing-seat>   # buzz | codex-buzz | agy-buzz
export VISITOR_ROLE=grok|codex|agy|goose
export VISITOR_REQUIRE_MENTION=1
bash "$ROOT/install-profile.sh" --brain "$VISITOR_ROLE" --dry-run
bash "$ROOT/start-collab.sh" --seats codex-buzz,agy-buzz,goose   # fail-closed on mixed relays
bash "$ROOT/read.sh" --room <name-or-uuid>
bash "$ROOT/collab.sh" open --from "$VISITOR_ROLE" --to <peer> --task "…" --dry-run
bash "$ROOT/collab.sh" open --room <id> --from "$VISITOR_ROLE" --to <peer> --task "…"
bash "$ROOT/collab.sh" done --room <id> --from "$VISITOR_ROLE" --to <peer> --task "…"
# BLOCKED to Prime only when stuck (once per task):
bash "$ROOT/collab.sh" blocked --room <id> --from "$VISITOR_ROLE" --to grok --task "…" --need-prime true
```

Do not install Hermes / Nous Portal for this kit (credit paywall). Idle nerve is `wake.sh`. Goose recipes use the fork CLI (`scripts/visitor/goose-cli.sh --check`), not `/usr/bin/goose` and not a minted goose seat. OpenWorker is the later free coworker plug, not a paid portal.

Rules:

- Do not mint seats (including Goose). Do not Edit Helix / PATCH / Prism / Ember.
- Do not Custom-harness raw `agy`. Do not register this as ACP.
- Idle: do not poll with an LLM. `wake.sh` is the nerve (stdout `VISITOR_WAKE` only).
- Unaddressed hellos are silence. Talk to teammates via `COLLAB v0`.
- `to: all` is fail-closed: every present teammate must share the sender's PUBLIC.txt host.
- Prime is disturbed only on `status: BLOCKED` + `need_prime: true`, once per task fingerprint, and only when that seat shares the sender's PUBLIC.txt host (`prime-other-bus` otherwise).
- Key in `~/.buzz-dev/agents/<seat>/agent.env` only — never argv or chat.

Spec: `docs/visitor-collab.md`.
