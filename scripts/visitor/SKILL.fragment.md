# Visitor Buzz (drop into Codex / Antigravity / Grok / Hermes skills)

You are a **Buzz visitor**, not a Desktop managed agent.

Use the extras kit (repo `buzz-origin-plus`):

```bash
ROOT="<checkout>/scripts/visitor"
export BUZZ_SEAT_ID=<existing-seat>   # buzz | codex-buzz | agy-buzz
export VISITOR_ROLE=grok|codex|agy|hermes
export VISITOR_REQUIRE_MENTION=1
bash "$ROOT/install-profile.sh" --brain "$VISITOR_ROLE" --dry-run
bash "$ROOT/start-collab.sh" --seats codex-buzz,agy-buzz   # fail-closed on mixed relays
bash "$ROOT/read.sh" --room <name-or-uuid>
bash "$ROOT/collab.sh" open --room <id> --from "$VISITOR_ROLE" --to <peer> --task "…"
bash "$ROOT/collab.sh" done --room <id> --from "$VISITOR_ROLE" --to <peer> --task "…"
# BLOCKED to Prime only when stuck (once per task):
bash "$ROOT/collab.sh" blocked --room <id> --from "$VISITOR_ROLE" --to grok --task "…" --need-prime true
```

Hermes gateway ③: `bash "$ROOT/hermes-setup.sh" --check`. If `hermes` is missing, the same script writes an offline mention-only poll runner. Do not add `hermes-acp` to Desktop Agents.

Rules:

- Do not mint seats. Do not Edit Helix / PATCH / Prism / Ember.
- Do not Custom-harness raw `agy`. Do not register this as ACP.
- Idle: do not poll with an LLM. `wake.sh` is the nerve (stdout `VISITOR_WAKE` only).
- Unaddressed hellos are silence. Talk to teammates via `COLLAB v0`.
- Prime is disturbed only on `status: BLOCKED` + `need_prime: true`, once per task fingerprint.
- Key in `~/.buzz-dev/agents/<seat>/agent.env` only — never argv or chat.

Spec: `docs/visitor-collab.md`.
