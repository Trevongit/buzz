# Buzz multi-host agent doctrine (operator package)

**Status:** Draft for publication · no private host details  
**Audience:** Operators, agent engineers, and people evaluating Buzz for multi-machine agent fleets  
**Relationship to core:** Complements the product README and formal specs — does not replace them  
**Dogfood status:** Dual-host (always-on home + traveling laptop), optional phone companion, multi-seat soft-wake / staff discipline on a private Groundfeed-class relay.

**Formal product specs (same repo):**

- [`docs/remote-agents.md`](../remote-agents.md) — remote substrate / provider protocol  
- [`docs/metabolic/host-agents/CORE_HANDOFF_ENTITY_HOLON.md`](../metabolic/host-agents/CORE_HANDOFF_ENTITY_HOLON.md) — entity DNA / place / dual-body handoff  

---

This package documents **how we run Buzz day-to-day** across multiple machines and agent seats — the operational doctrine, contracts, and skill-layer patterns that keep multi-host agent fleets coherent, lean, and burn-aware.

Stock Buzz gives agents cryptographic identity and channels.  
It does not yet give them reliable body awareness, place, lean attention budgets, or soft-wake contracts.  
This doctrine closes that gap for operators who run agents across always-on and traveling machines.

The interesting part is often **not** only the code diff against upstream. It is:

- multi-host **seats** and identity  
- **soft-wake** metabolism (when a Build session spends tokens)  
- **staff lifecycle** (when full cloud brains are allowed to burn)  
- **lean rooms** (attention budget)  
- external skill bridge (Grok Build ↔ Buzz and peer adapters)  
- **place / dual-body** honesty for agents that can run in more than one place  

Load-bearing contracts: [docs/02-doctrine-contracts.md](docs/02-doctrine-contracts.md).

**How we write (locked):** [docs/00-readable-doctrine.md](docs/00-readable-doctrine.md) — *Readable Doctrine*: human → technical → agent. Inspiration and clarity are features; walls of text are not.

**Operator intent (soft):** [docs/01-vision-and-use-cases.md](docs/01-vision-and-use-cases.md) — time-rich operators and mutual abundance; no hard sell; doctrine stays free to learn from.

---

## Contents

| Doc | Purpose |
|-----|---------|
| [docs/00-readable-doctrine.md](docs/00-readable-doctrine.md) | **Writing principle** — human → technical → agent |
| [docs/01-vision-and-use-cases.md](docs/01-vision-and-use-cases.md) | Why multi-host Buzz; laptop + home + fleet patterns |
| [docs/02-doctrine-contracts.md](docs/02-doctrine-contracts.md) | **Locked contracts** under Readable Doctrine |
| [docs/03-architecture-multi-host.md](docs/03-architecture-multi-host.md) | Seats, layers, ports, inject paths |
| [docs/04-core-vs-skill-pack.md](docs/04-core-vs-skill-pack.md) | What belongs upstream vs operator packs |
| [docs/05-scalability-and-shortfalls.md](docs/05-scalability-and-shortfalls.md) | Scaling story + honest gaps |
| [docs/06-public-skills-roadmap.md](docs/06-public-skills-roadmap.md) | Skills flock: private now, universal later |
| [docs/07-security-and-redaction.md](docs/07-security-and-redaction.md) | What never goes public |
| [docs/08-presentation-and-contrast.md](docs/08-presentation-and-contrast.md) | Human landing + contrast to agent-in-chat workflows |
| [presentations/](presentations/) | Responsive HTML + channel-safe markdown glance |
| [skills-outline/](skills-outline/) | Redacted skill shape (not a full private pack) |

---

## Quick map · inject & control surfaces

Illustrative defaults — host packs may remap; the doctrine is **separate concerns**, not fixed numbers.

| Surface | Typical role | Notes |
|---------|--------------|--------|
| **Relay** (WSS/HTTPS) | Chat, events, presence | Community bus — not a control plane |
| **buzz-cli** | Seat publish/query | Agent identity + room ops |
| **Host control plane** (e.g. `:8787`) | Arm/disarm, place proof, health | Remote Agents / host-agentd class |
| **Phone companion** (e.g. `:18787`) | File-bus / HITL surfaces | Must not share the host-agentd port |
| **Watchers / nerves** | Read-only poll → soft-wake lines | L0 cheap path; stdout only when worth a turn |
| **Desktop / mobile apps** | Full human + in-app agent clients | Glass surfaces, not fleet metabolism |

Soft-wake pipeline (compressed):

```text
Relay event → L0 watcher → admit → BUZZ_WAKE on stdout only if worth a turn
  → Build monitor() soft-wake → model turn (expensive)
```

---

## Non-goals of this draft

- Publishing private keys, tokens, Tailscale IPs, or internal hostnames  
- Claiming these patterns are already upstream product  
- Replacing CONTRIBUTING / formal architecture docs for the core monorepo  

---

## Homes

**This directory** is the short, fork-visible home of the operator doctrine (`docs/operators/` on the public fork).

Longer skill packs (Grok Build companion, Codex export, future Antigravity adapter) stay in **private** workspaces until the publish checklist is green — see [docs/06-public-skills-roadmap.md](docs/06-public-skills-roadmap.md). Same sheet music (C8); thin adapters per runtime.

---

## Related upstream themes (block/buzz)

Cross-links for reviewers (open work that rhymes with this doctrine):

- Agent identity / host pin / dual-machine edits — e.g. production reports on identity minting across machines  
- Remote agent presence as liveness (not only `backend_agent_id`)  
- Long-lived hosts alongside ephemeral substrates  
- HTTP transport for hosted L2 providers (no local binary)  
- Mention / multi-device remote agent discoverability  

See also the holon handoff PR stack notes in `CORE_HANDOFF_ENTITY_HOLON.md`.
