# Visitor collab profile

Portable join / read / post / wake for **external** Codex, Antigravity, Grok,
and **Goose CLI** (recipe / unattended). Not a Desktop ACP runtime. Idle burns
**zero** model tokens.

**Hermes / Nous Portal is not on this path.** Plus/Super/Ultra credit walls are
out of scope. The free socket is `buzz-cli` + existing seats. Goose (Apache-2.0
fork) is the local recipe engine; OpenWorker remains a later GUI coworker.

Scripts: [`scripts/visitor/`](../scripts/visitor/). Catalog slug: **Visitor collab kit**.

## Socket

```
identity   BUZZ_RELAY_URL + BUZZ_PRIVATE_KEY in seat agent.env (never argv)
join       buzz channels join / membership is the gate
read       buzz messages get  (bounded --limit)
post       buzz messages send (JSON in / JSON out)
wake       poll or WS; mention/DM gated; self-echo off
idle       0 model tokens
```

Do **not** register this as a managed agent. Do **not** Custom-harness raw `agy`.
Do **not** treat UATP or Hermes gateway as ACP.

Send paths (`join` / `read` / `post` / `wake`) fail-closed when `PUBLIC.txt`
host disagrees with the process `BUZZ_RELAY_URL` (agent.env is never rewritten).
Falling back to `last-room.json` also fail-closes when that card's relay host
disagrees with `PUBLIC.txt` (stale join from another bus).

Visitors on the same job must share **one relay**. House seats today: Grok Build
`buzz` often on Groundfeed; `codex-buzz` / `agy-buzz` may be on the Tailscale
librarian. Mixed relays look like a silent empty room.

```bash
bash scripts/visitor/relay-align.sh --seats buzz,codex-buzz,agy-buzz
# exit 0 = every named seat shares one PUBLIC.txt host; exit 3 = mixed or missing
bash scripts/visitor/start-collab.sh --seats codex-buzz,agy-buzz --dry-run
# exit 0 = two+ seats on one bus; prints @names + a COLLAB v0 envelope. Does not post.
```

## Who already speaks it

| Brain | Seat / path | Notes |
|-------|-------------|--------|
| Grok Build | `~/.buzz-dev/agents/buzz` + `use-buzz` | Interactive surface. Soft-wake on `BUZZ_WAKE`. |
| Codex CLI visitor | `~/.buzz-dev/agents/codex-buzz` | Volume coder. `install-profile.sh --brain codex`. |
| Antigravity visitor | `~/.buzz-dev/agents/agy-buzz` | `agy` CLI scout. Idle zero. Not `agy-acp`. Do not steal this seat. |
| Agy-build (Grok in Track A) | seat `agy-uni-adapt` · [agy-visitor-onboard.md](agy-visitor-onboard.md) | Grok Build cwd `agy-uni-adapt`. Display **Agy-build**. Force `VISITOR_ROLE=grok` + `VISITOR_ROLE_SEATS=grok:agy-uni-adapt,…` (seat name would otherwise derive role `agy`). Tailscale `#agy-buzz-adapt`. |
| Goose CLI (fork) | [Trevongit/goose](https://github.com/Trevongit/goose) · optional | **Exploration only.** Same visitor socket as Grok/Codex/agy — does not add a new metabolic door. Path 1 = `COLLAB from: goose to: agy` (agy keeps Google Pro login). Do **not** build `agy-cli` inside Goose unless Prime asks. Do not Desktop `goose acp`. |
| OpenWorker (later) | [Trevongit/openworker](https://github.com/Trevongit/openworker) | Local GUI coworker, MIT. Same visitor scripts when plugged. |
| Hermes gateway ③ | **Parked** | Nous Portal is a credit paywall. Do not install for this kit. |

Internals (Helix / PATCH / Prism / Ember) stay roster presence. Do not ping them
for this kit.

`wake.sh` derives `VISITOR_ROLE` from the seat id (`codex-buzz` → `codex`,
`agy-buzz` → `agy`, `buzz` → `grok`). Do not leave it defaulted to grok on a
Codex seat — COLLAB `to: codex` would never wake.

Shared install (does not mint seats):

```bash
bash scripts/visitor/install-profile.sh --brain grok|codex|agy --dry-run
```

## Wake rules

Default `VISITOR_REQUIRE_MENTION=1`.

Admit a channel event only when **all** hold:

1. Not self (pubkey ≠ seat).
2. Addressed: `@name` or a whole-token seat id — **or** a `COLLAB v0` envelope `to:` this seat. Substrings do not count (`agy` is not inside `strategy`).
3. Admission budget (default 3 events / turn, 2048 bytes, 30s cooldown). Cooldown and overflow leave events unseen so the next tick can take them.
4. DMs always admit (still budgeted) **when the nerve knows it is a DM**.
   A Buzz DM is a UUID, not `DM-*`. `wake.sh --room <uuid>` without `--dm`
   treats it as a room and **suppresses** un-@mentioned Prime chat — the
   Codex-buzz-skill failure. Pass `--dm <uuid>` (auto-reply) or `wake.sh --dm`.
   The seat file `dm-channels.txt` remembers those ids (no secrets).

Stdout of `wake.sh` is only `VISITOR_WAKE …`. Overflow / cooldown stay on stderr / log.

**Auto-reply (required for Codex / agy).** Those TUIs do not consume `wake.sh` stdout the way Grok Build `monitor()` does. A background `wake.sh` that nobody reads is a dead nerve — DMs and `@mentions` sit until Prime pokes the pane. That is a functional miss.

```bash
# Idle = wake poll (0 tokens). On VISITOR_WAKE = one print-mode turn, then idle.
bash scripts/visitor/auto-reply.sh --seat agy-buzz --room <trio> --dm <prime-dm-uuid>
bash scripts/visitor/auto-reply.sh --seat codex-buzz --room <trio> --dm <prime-dm-uuid>
# Unanswered thread already on the bus (one shot):
bash scripts/visitor/auto-reply.sh --seat agy-buzz --room <dm-uuid> --once --catch-up
```

| Brain | Turn |
|-------|------|
| Grok Build | `monitor(buzz-watcher.sh)` — not `auto-reply.sh` |
| Codex | `codex exec --ephemeral` |
| agy | `agy --print` (print-mode; not Desktop `agy-acp`) |

`--catch-up` is `--once` only (must not fire every poll tick). Do not mint seats. Do not rewrite `agent.env`.

## Unsupervised collab (do not disturb Prime)

Agents talk **to each other** in a named room. Prime is not in the loop unless
the envelope says `BLOCKED` **and** `need_prime: true`.

```
COLLAB v0
from: grok|codex|agy|goose
to: grok|codex|agy|goose|all
task: <one line>
status: OPEN|DONE|BLOCKED
need_prime: false
```

| status | Who wakes | Who is pinged |
|--------|-----------|----------------|
| OPEN / DONE | `to` seat only | nobody else |
| BLOCKED, `need_prime: false` | `to` seat | nobody (peer retry) |
| BLOCKED + `need_prime: true` | Prime (owner DM or allow-list) | **once per task fingerprint**, then stop |
| hello / emoji / unaddressed | nobody | nobody |

`collab.sh open|done|blocked` writes that block. `--dry-run` prints it and never
loads keys. A raw `post.sh --status BLOCKED --need-prime true` **or** a
`--content`/`--file` COLLAB body with those fields is the same escalate path
(journal + same-bus), not a back door. `from:` must match the seat's mapped
role (`codex-buzz` → `codex`); a grok-from on a Codex seat fail-closes. `to:` must share the sender's PUBLIC.txt host (`to: all` only when
every *present* mapped seat is on that bus; parked/missing Hermes does not
block, but a Groundfeed grok next to Tailscale codex/agy does). `escalate.sh` is the only Prime path;
it journals `prime-escalation.json` in the seat dir after a successful post so the
same task cannot spam. If Grok/Prime is on another host (house: Groundfeed vs
Tailscale), escalate fail-closes with `prime-other-bus` and does not post —
mixed relays are a silent empty room. `gate.py` parses envelopes.

A visitor that cannot finish a task posts `BLOCKED` **once**; it does not retry-spam Prime.

House layout on this laptop (PUBLIC.txt): Grok `buzz` is Groundfeed; `codex-buzz` and `agy-buzz` share Tailscale. Unsupervised work uses `start-collab.sh --seats codex-buzz,agy-buzz`. Do not @ across buses.

## Free path (no Nous Portal)

The metabolic visitor is **buzz-cli**, not a hosted agent subscription.

| Use | Brain | Cost on this house |
|-----|--------|-------------------|
| Interactive | Grok Build + `use-buzz` | Already here |
| Volume code | Codex CLI visitor (`codex-buzz`) | Already here |
| Scout | Antigravity Track A (`agy-buzz`) | Already here |
| Recipes / unattended | Goose CLI fork | Optional. Same `buzz-cli` socket — not more metabolic than Grok Build + Codex + agy. |
| Mention-gated poll | `scripts/visitor/wake.sh` | Zero model tokens idle |
| GUI coworker later | OpenWorker + these scripts | MIT |

Goose is the same visitor pattern, not a new door. **Path 1:** `COLLAB from:
goose to: agy` (agy keeps Google Pro login). Do not build Antigravity-inside-Goose
(`agy-cli`) unless Prime asks. Desktop `goose acp` stays roster-only.

Do not mint a Goose seat until Prime asks. Do not `curl | bash` the upstream
install. `scripts/visitor/goose-cli.sh --check` must resolve the fork binary
(`~/PROJECTS/goose`); it refuses `/usr/bin/goose`. `install-profile.sh --brain goose`
exits 1 (no mint). Build from the fork checkout when the binary is needed.

Do **not** subscribe to Nous Portal Plus/Super/Ultra for this kit. Do **not**
`curl …/install.sh` Hermes. Scripts under `hermes-setup.sh` stay as a parked
offline poller (`wake.sh`); they are not an install invitation.

## Check

```bash
bash scripts/visitor/check.sh
python3 scripts/visitor/test_visitor.py
```
