# Multi-host architecture (operator view)

## Inject map (how things reach the relay)

| Path | Direction | Role |
|------|-----------|------|
| **buzz-cli** | Publish/query | Agent seats, scripts, skills |
| **Desktop / mobile apps** | Full client | Humans + in-app agents |
| **host control plane** | Control only | Arm/disarm, place proof, health — not general chat inject |
| **Phone companion** (optional) | File-bus / Surfaces | Phone HITL bridge; separate port from host control |
| **Watchers / nerves** | **Read only** | Poll messages → local soft-wake lines |

## Always-on host (edge)

Typical unit set (names illustrative):

- Relay stack (docker or managed)  
- Host agent control plane  
- Presence lease for steward seat  
- Phone **keys** daemon (exact allowlist)  
- Optional **local small-model** chat (no tools)  
- User linger so units survive logout  

## On-demand staff session

Explicit command (e.g. phone key `staff`) starts a full Grok Build (or equivalent) in a fixed workspace with:

- Resume / handoff prompt  
- Soft-wakes for owner DM + hot rooms  
- Hygiene: Build owns owner-DM cursor while staffed  

`staff stop` ends the session and cloud burn.

## Soft-wake pipeline

```text
Relay event
  → L0 watcher poll (cheap)
  → admit (dedupe / budget)
  → stdout BUZZ_WAKE only if worth a turn
  → Build monitor() soft-wake
  → model turn (expensive)
```

## Seats vs Desktop agents

| Kind | Typical use |
|------|-------------|
| CLI / Build seat | Co-lab engineer identity via buzz-cli |
| Desktop managed agent | In-app ACP agent on that glass |
| Host-pinned remote seat | Control-plane row with place proof |

Do not conflate faces across these kinds.

