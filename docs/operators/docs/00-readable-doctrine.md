# 00 · Readable Doctrine (locked writing principle)

**Status:** Locked standing principle for the team SOT  
**Applies to:** Every post and document in `#multi-host-doctrine` and later public operator packs  
**Name:** *Readable Doctrine*

---

## Human layer

Imagine you open the room after a long day. You have sixty seconds.

If the first thing you meet is a wall of ports, hex ids, and nested rules, you close the app — and the doctrine dies of neglect. Agents can chew dense text all night. Humans cannot, and should not have to.

So we write **human-first**: a clear picture and a reason to care, then the precise contract, then the checklist machines can obey. Inspiration and clarity are features, not decoration. If the doctrine is not enjoyable to read, it will not be followed.

**The rule in one sentence**  
Write so a tired human can grasp the idea in under a minute, then give the precise technical contract, then give the machine-readable layer — never the other way around.

---

## Technical layer

### Practical shape every major post/doc should follow

| Order | Layer | What it contains |
|------:|-------|------------------|
| 1 | **Human** | Plain language, concrete picture, why it matters, one metaphor or visual |
| 2 | **Technical** | Tables, exact rules, ports, failure modes, “what we actually do” |
| 3 | **Agent / machine** | Must / may / must-never; checklists agents can act on |

### Simple touches we keep

- Short paragraphs and real white space  
- One high-signal diagram or table per major idea  
- “At a glance” boxes where helpful  
- **No walls of text in the channel** — long drafts live in files; the channel gets the clear summary + pointer  

### Why it matters (ops)

| Failure mode | Result |
|--------------|--------|
| Dense-first posts | Human attention drops → contracts drift |
| Agent-only checklists | Operators cannot teach or audit the flock |
| Inspiration without rules | Warm feelings, no enforcement |

---

## Agent / machine layer

When writing doctrine (or a SOT post that locks anything):

| Obligation | Rule |
|------------|------|
| **MUST** | Lead with human layer (≤ ~1 minute read) |
| **MUST** | Follow with scannable technical rules (tables preferred) |
| **MUST** | End with enforceable agent checklist (must / may / never) |
| **MUST** | Keep channel posts short; point to files for long form |
| **MUST NOT** | Lead with hex dumps, full scripts, or unskimable walls |
| **MUST NOT** | Put secrets, keys, or private host details in public-shaped posts |
| **MAY** | Use one metaphor or diagram per major idea |
| **MAY** | Split a large contract into multiple short posts (one idea each) |

**Acceptance test:** Would a tired open121 still understand the point before the first table?

---

## Relationship to other docs

This principle governs *how* we write.  
[02-doctrine-contracts.md](02-doctrine-contracts.md) is the first major doc written fully under this standard.
