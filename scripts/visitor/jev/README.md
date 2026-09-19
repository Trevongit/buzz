# Jev three jobs (draft)

Not live. Prime asked extras to keep the three-question file here.
Source of truth for the questions is still
`~/PROJECTS/JEV-research/docs/THREE-JOBS.json`.
This copy is what extras will read on a later bind.

- `THREE-JOBS.json` — one batched System One call
- `prefilter.py` — skip watcher lines before any HTTP
- `compose.py` — apply cutoffs in code (no API)

Set `VISITOR_JEV=1` on `buzz-inbox.sh` to call Jev after each wake.
Key is read from `~/PROJECTS/JEV-research/.env` or `TYPESAFE_API_KEY`.
Never put the key in this tree.

Each decision prints `JEV_DECIDE` and writes
`~/.buzz-dev/control-room/jev-last.json` for the control-room lamp.
HTTP failure prints `JEV_FAIL` and still rings extras (do not hide
Prime). `ignore` and `wake-codex` / `wake-agy` print `JEV_QUIET` instead
of `VISITOR_WAKE` so extras does not spend a turn. Owner pings and DMs
always ring extras (`VISITOR_OWNER_PK`).

Each decision also appends `~/.buzz-dev/control-room/jev-audit.jsonl`
(capped at 2000 lines) so we can see value over time.

Do not start auto-reply from this path.
