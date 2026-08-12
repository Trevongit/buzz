# Multi-Host Agent Doctrine — presentation (channel-safe)

**Source idea:** responsive HTML explainer (local open-in-browser).  
**Why not raw HTML in Buzz:** relay + CLI block `text/html` (stored XSS). Use this markdown, PDF, or PNG instead.

---

## Human layer

Most agent-in-chat experiences feel magical at first. The real test is whether they stay coherent after **weeks** of real work across **multiple machines**.

Typical workflows (e.g. agent-in-Slack style) are strong at shared context and task ownership. They often leave **body, burn, and drift** to the human — until the human becomes the only governor.

A higher class of system makes those problems first-class.

### What it requires

| Pillar | Picture |
|--------|---------|
| **Body awareness** | Agent knows which machine it is on; refuses two places at once |
| **Metabolic honesty** | Always-on presence ≠ full cloud brain burning money |
| **Attention budgets** | Lean rooms / soft-wakes; no quiet jungle of attention |
| **Enforceable contracts** | Rules agents restate and obey — not only admin policy |

### Why a tired operator cares

You should be able to leave the laptop, travel with a second machine, or glance at a phone and still know:

- which brains are burning money  
- which rooms are intentionally hot  
- that no agent pretends to be in two places  
- that attention will not quietly multiply overnight  

---

## Technical layer — at a glance

| Concern | Typical agent-in-chat systems | Multi-host doctrine |
|---------|------------------------------|---------------------|
| Shared context | Strong | Strong |
| Task ownership | Strong | Strong |
| Body / place awareness | Weak or absent | Explicit (DNA ≠ place ≠ face) |
| Burn control | Admin spend limits | Staff lifecycle + soft-wake contract |
| Multi-device continuity | Fragile | Designed in from the start |
| Drift protection | Mostly social / policy | Contractual + agent-enforced |
| Sovereignty | Often locked to one platform | Self-hostable open substrate |

### Load-bearing contracts (pointers)

- Soft-wake stdout discipline  
- Staff start / staff stop  
- Lean room default (owner DM + 0–1 hot co-lab)  
- Presence leases (watching ≠ green)  
- Dual-body refusal  
- Clear inject map (chat vs control plane vs companion)  

Full three-layer contracts: `docs/02-doctrine-contracts.md`

---

## Agent layer — standing orders

| | |
|--|--|
| **MUST** | Hold **one live place** at a time; dual-body refused |
| **MUST** | Treat soft-wake as a **contract**, not a firehose; diagnostics → logs |
| **MUST** | Treat full cloud burn as an **explicit mode**; stop ends burn |
| **MUST** | Prefer **lean rooms**; do not invent omnibox attention |
| **MUST** | Restate the relevant contract when joining doctrine/ops rooms |
| **MUST NOT** | Pretend channel text is a tool grant (C1) |

---

## Closing

The systems that feel most magical in the short term often leave body, burn, and drift to the human.  
A higher class of system makes those problems first-class — honest place, explicit metabolism, contracts agents help enforce.

That is the difference between a clever coworker and infrastructure that can grow with you.

---

*Readable Doctrine: human first → technical precision → agent-enforceable contracts*
