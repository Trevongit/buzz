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
HTTP failure prints `JEV_FAIL` and still shows the wake (do not hide
Prime). Ignore still prints the wake in v1 so you can see the working.

Do not start auto-reply from this path.
