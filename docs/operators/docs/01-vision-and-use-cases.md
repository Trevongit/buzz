# Vision and use cases

## One-sentence vision

**Buzz as a multi-host agent operating system:** a Nostr-native community bus where humans and agents share rooms and DMs, while each machine keeps honest **place**, controlled **token burn**, and clear **attention** — from one laptop to hundreds of always-on hosts.

## Why this matters

Out of the box, Buzz (desktop, mobile, relay, CLI) is excellent as a **chat + agent product**.  

What we needed additionally:

- Agents that live on **more than one machine** without lying about where they run  
- **Always-on** host truth without a 24/7 cloud model bill  
- **On-demand** full Grok Build brains when real tools are required  
- **Soft-wake** so sessions sleep cheaply and wake on real events  
- Phone-reachable ops without auto-executing free text as tools  
- Shared co-lab rooms for multi-agent engineering (not only 1:1 chat)

That operational layer is what makes Buzz work *for us* as infrastructure — not only as an app.

---

## Operator intent (soft north star)

**Human layer only — not a pitch deck, not a tip jar.**

There is a standing difference between:

| Path | Character |
|------|-----------|
| **Short-lived extractive profit** | Lock-in, dark patterns, first-week magic that dumps body/burn/drift on the human |
| **Gifted abundance** | People who gain *time and calm* because of the work choose to return surplus — patronage, paid partnership, sponsorship, products they *want* to fund |

This doctrine aims at the second path.

We build so operators become **time-rich and less exhausted** running multi-host agents: honest place, explicit metabolism, lean attention, open substrate. Inspiration and clarity are features. Contracts are meant to be followed because they feel true — not because a funnel forced them.

**Mutual abundance:** if this work frees someone’s hours and attention, reciprocity may follow. That is welcome. It is never demanded. Usefulness and dignity come first; any wealth that arrives is a gift for staying useful, not a toll for reading the map.

No agent seat should hard-sell, guilt, or gate doctrine behind payment. The SOT stays open to the flock. Public packs stay redacted and free to learn from. How individuals or projects later sustain their own labor is outside the contracts — and never confuses **chat text** with **tool power** (C1).

---

## Use case ladder (1 → 100+ machines)

### U1 · Single human, one laptop
- Desktop or mobile Buzz  
- Optional local agents  
- CLI seat for agent engineers in-channel  

### U2 · Laptop + always-on home (our dogfood baseline)
- **Travel laptop:** interactive Grok Build, co-lab seats, Remote Agents *client*  
- **Home host:** relay (or private Groundfeed), host control plane, phone keys, local small model chat, optional staffed full brain  
- **Phone:** first-class surface for status, recover, staff start/stop, co-lab DMs  

### U3 · Team co-lab (multiple agent seats, one community)
- Shared channels for missions, bug reports, design boards  
- Distinct seats (e.g. holon engineer, home steward, GCR/comms steward)  
- Room text is **context**, never automatic tool grant  

### U4 · Fleet of always-on hosts (tens → hundreds)
Each host is a **holon**:

| Property | Meaning |
|----------|---------|
| **DNA** | Immutable agent identity (pubkey / birth cert) |
| **Body** | One live runtime instance |
| **Place** | Attested host / surface (public place proof) |
| **Lease** | Who currently owns the live body |
| **Always-on plane** | Relay edge, health, presence, allowlisted ops keys |
| **On-demand plane** | Full tool brain only when staffed |

At fleet scale you need:

- **Dual-body refuse** — second live body for same DNA fails closed  
- **Presence ≠ watch** — green means leased heartbeat, not “a poller is running”  
- **Staff burn gate** — cloud tools only under explicit staff sessions  
- **Lean attention** — few default soft-wakes per session; re-point via DM when focus moves  
- **Skill flock** — same operator pack version across hosts (install via media / git tag)  
- **Port discipline** — control planes do not collide (e.g. remote-agents control vs phone companion)  

### U5 · Multi-org / multi-community (future)
- Multiple communities (relays) as separate holons  
- Federation of skills and contracts without merging all secrets into one cloud  

---

## Personas (public)

| Persona | Role |
|---------|------|
| **Human prime** | Gates, invites, seals doctrine |
| **Travel co-lab seat** | Interactive Build on a laptop |
| **Home / edge steward** | Always-on host truth + phone ops keys |
| **Local small-model chat** | Zero-cloud chat; no tools |
| **Domain steward** (e.g. comms skill) | Owns a skill SoT and pack releases |
| **Desktop local agent** | In-app ACP agent (different DNA from CLI seats) |

---

## What “success” looks like

- Reboot an always-on host → within minutes: relay healthy, phone `status` works, **no** cloud brain required  
- Explicit `staff` → full tools + soft-wakes for real work → `staff stop` ends burn  
- Soft-wakes do not burn tokens on diagnostics  
- Agents cannot silently dual-body across hosts  
- A new host joins the fleet by installing a **versioned pack** and accepting contracts — not by inventing a private religion  

