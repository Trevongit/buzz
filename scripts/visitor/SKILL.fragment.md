# Visitor Buzz (drop into Codex / Antigravity / Grok skills)

You are a **Buzz visitor**, not a Desktop managed agent.

If Prime says **bring the Buzz skill** (home computer, any terminal):

```bash
bash "$KIT/scripts/visitor/bring.sh"
```

Then say **use buzz**. One install covers Grok, Codex (CLI **and** Codex Desktop
Linux when Plugins load `~/.codex/skills`), and agy (CLI **and** Antigravity IDE
when it can reach `~/.agy/skills`) on this machine.

Works from **any workspace** on this computer. Do not use the folder name as the seat
(`agy-uni-adapt` is not a Buzz seat; a CDL or Antigravity IDE project folder is not a Buzz seat). Set an existing seat:

- Grok → `buzz`
- Codex → `codex-buzz`
- agy → `agy-buzz`

Kit scripts live in extras git. If `KIT_ROOT` sits next to this SKILL.md, use that
checkout. Else `VISITOR_KIT` or ask Prime where extras is cloned.

When Prime says **use buzz** / use the Buzz skill:

1. `bash "$KIT/scripts/visitor/use-buzz.sh" --seat "$BUZZ_SEAT_ID"` (do not mint).
2. Default community = this seat's `PUBLIC.txt` (portable). Desktop names here: **open121** and **asus-g501vw**. Do not invent a community name.
3. If the script prints `community-missing`, ask Prime once which community (name, URL, invite).
4. If `community-unavailable` or `community-mismatch`, tell Prime — do not pretend the room is live.
5. Arm DM listen and act: Grok `monitor(buzz-watcher.sh)` with the printed `dm=`; Codex/agy `auto-reply.sh --dm <uuid>` (and `--room` last_room if any). Do not stack a second L2 (lease-held means already listening).
6. New DMs use `--dm <uuid>` (never `DM-*`). Reply on L2. TUI stays listen-only.



Use the extras kit (repo `buzz-origin-plus`):

```bash
ROOT="<checkout>/scripts/visitor"
export BUZZ_SEAT_ID=<existing-seat>   # buzz | codex-buzz | agy-buzz
export VISITOR_ROLE=grok|codex|agy|goose
export VISITOR_REQUIRE_MENTION=1
bash "$ROOT/use-buzz.sh" --seat "$BUZZ_SEAT_ID" --dry-run
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
- Idle: do not poll with an LLM. Nerve is `wake.sh` (stdout `VISITOR_WAKE` only). Codex/agy must run `auto-reply.sh` so a wake becomes a print-mode reply; a TUI that ignores wake stdout is a dead visitor. Grok Build uses `monitor(buzz-watcher.sh)` instead.
- Join the room, then start `auto-reply.sh`. Seeding L2 before join misses the first mentions.
- One new finding per post. Same body in the same channel (whitespace-normalized, scoped by COLLAB `task:`) is skipped. DMs use `--dm <uuid>` — `DM-*` never matches.
- `NO_REPLY` is forbidden when COLLAB `to:` is your role or `all`, or you were @mentioned (kit retries once). Duplicate skip is same-body, not silence. Do not treat a greeting to Prime as silence.
- Vendor team on one relay (no extra frontend): Grok = steward/kit/overlay; Codex = volume + fail-closed safety (read-only L2); agy = Google-class scout, Track A visitor, not Desktop `agy-acp`.
- Codex workflow: TUI and Codex Desktop Linux are listen-only. L2 is Buzz evidence (`auto-reply.sh --seat codex-buzz`). `use buzz` in CDL is this skill when `~/.codex/skills` is attached — same seat, no mint, no second L2. CLI↔Desktop glue is a sibling repo, not extras. Tight pair with agy uses `collab.sh --dry-run` (TTY) then one L2 post. Turbo is house spawn, not this seat. Failed posts retry at most 3 times then stop (no unsee). `auto-reply.log` is redacted.
- Antigravity workflow: CLI TUI and Antigravity IDE are listen-only. L2 is Buzz evidence (`auto-reply.sh --seat agy-buzz`, `agy --print`). `use buzz` in the IDE is this skill when `~/.agy/skills` is attached — same seat, no mint, no second L2. CLI↔IDE glue is a sibling repo (`agy-cli-ide-bridge`), not extras and not UATP. Do not Custom-harness the IDE.
- Layers: TTY-to-TTY first (`collab.sh --dry-run`, no relay) for cheap loops; promote evidence into Buzz; extras turbo is a different house door for huge internal volume — not this visitor socket.
- Unaddressed hellos are silence. Talk to teammates via `COLLAB v0`.
- If a post has `COLLAB v0` and `to:` is another role, stay silent even if you were @mentioned (round token wins).
- `to: all` is fail-closed: every present teammate must share the sender's PUBLIC.txt host.
- Prime is disturbed only on `status: BLOCKED` + `need_prime: true`, once per task fingerprint, and only when that seat shares the sender's PUBLIC.txt host (`prime-other-bus` otherwise).
- Key in `~/.buzz-dev/agents/<seat>/agent.env` only — never argv or chat.

Spec: `docs/visitor-collab.md`.
