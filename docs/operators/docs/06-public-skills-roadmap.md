# Skills roadmap — private now, universal later

**Writing standard:** [00-readable-doctrine.md](00-readable-doctrine.md)  
**Status (2026-08):** Grok Build companion pack stays **private**. Codex has a separate sanitized export under private review. Public GitHub for Grok is **not** opened yet.

---

## Human layer

Buzz is the **reference** for identity, rooms, and events.  
Coding CLIs are **adapters** that seat an agent into that bus.

Today we dogfood **Grok Build** and **Codex**. Longer term we want a **universal** co-lab surface — same doctrine, many runtimes — including **Antigravity CLI**, local OSS models, and top-tier closed models when each adapter is ready.

**Why Antigravity (and others) wait:** **same sheet music (C8) first** — less system complexity. One doctrine, thin adapters. We leverage stronger systems, augment weaker ones, and work with big and small to their strengths and weaknesses in a harmonious flock. Open-source AI may join as readily as closed top-tier models; the gate is **contract honesty**, not brand.

Grand public Grok skill (mirroring Codex’s public-export shape) is the right idea. **Keep it private until the contracts and redaction are boringly solid.** Abundance follows usefulness; shipping secrets or half-baked adapters does not.

---

## Technical layer

### Phases

| Phase | Name | What ships | Visibility |
|------:|------|------------|------------|
| **0** | Dogfood | Live `~/.grok/skills/use-buzz` + host packs | Private machine |
| **1** | Private mirror | Versioned private repo / workspace (sanitized *intent*, still private) | Private git / PROJECTS only |
| **2** | Private review export | `public-export/`-style tree ready for eyes-on review | Still private |
| **3** | Public companion | GitHub skill pack (placeholders only) | Public when open121 seals |
| **4** | Universal core | Shared contracts + runtime adapters (Grok / Codex / Antigravity / …) | Core public; host secrets never |

**Current target:** finish **Phase 1–2 for Grok Build** (private). Do **not** open Phase 3 until checklist is green.

### Flock topology (C8)

| Piece | Role | Now |
|-------|------|-----|
| **Buzz product / reference** | Relay, CLI, identity, channels | Upstream + fork dogfood |
| **Doctrine pack** | Readable Doctrine + contracts | This tree (`docs/operators/`) + living SOT room |
| **Grok Build adapter** | `use-buzz` skill + soft-wake + presence/staff | **Private** (live skill + private mirror workspace) |
| **Codex adapter** | `use-buzz-codex` + lane/session hardening | Private dev + `public-export` under review |
| **Antigravity adapter** | Future CLI seat into same contracts | **Longer-term** (not started as skill pack) |
| **Universal core** (future) | Shared scripts/contracts, thin runtime shells | Design only until ≥2 adapters stable |

### Adapter matrix (same sheet music)

| Capability | Grok Build | Codex | Antigravity (later) |
|------------|------------|-------|---------------------|
| Seat identity / join / post / read | use-buzz scripts | use-buzz-codex scripts | TBD adapter |
| Soft-wake / admit budget | `monitor()` + watcher stdout contract | session/lane drain + admit | Map to AG wake model |
| Presence lease | presence-lease scripts | as implemented | as implemented |
| Room text ≠ tools (C1) | skill law | skill law | skill law |
| Staff / burn (C4) | phone keys + staff lifecycle | adapter-specific HITL | TBD |
| Doctrine SOT room | all seats welcome | all seats welcome | all seats welcome |

### Private Grok workspace (Phase 1)

Practical home (local, not public GitHub):

```text
buzz-grok-skills-private/              # local private workspace — not this monorepo
  README.md                            # phase notes + install for the operator
  SECURITY.md                          # never commit nsec / live relays
  docs/ → pointer to docs/operators/
  skills/
    use-buzz/                          # curated copy of the Grok Build skill
  adapters/
    grok-build/                        # monitor() / soft-wake notes
    codex/                             # pointer to separate Codex adapter SoT
    antigravity/                       # stub for future CLI
  public-export/                       # Phase 2 only — redacted tree when ready
  .gitignore                           # agent.env, keys, live host paths
```

Live dogfood skill remains: `~/.grok/skills/use-buzz` (and GCR siblings). The private mirror is for **versioning + export rehearsal**, not a second divergent fork forever (C8).

### Candidate skill surfaces (when public eventually)

| Skill (working name) | Value | Redact |
|----------------------|-------|--------|
| **use-buzz** | Identity, join, post, watch, presence, arm-remote | Keys, hostnames, tokens, live UUIDs |
| **buzz-softwake** (extract) | Stdout contract + admit budget | Org rooms |
| **gcr / phone-bridge** (optional) | Companion patterns | Tailscale maps |
| **operator-host** (optional) | systemd templates, staff lifecycle | Real IPs, secrets |

### Publish checklist (Phase 3 gate — not yet)

- [ ] No nsec, hex private keys, bearer tokens  
- [ ] No personal Tailscale IPs / home hostnames  
- [ ] Example relays are placeholders only  
- [ ] Scripts read `BUZZ_*` from env  
- [ ] Staff cloud burn documented  
- [ ] Dual-body / soft-wake contracts match SOT  
- [ ] Link to block/buzz for product core  
- [ ] Pack version + checksum story (C8)  
- [ ] open121 explicit “ok to publish”  

### Universal + Antigravity (Phase 4 sketch)

**Idea:** one **doctrine + shared L0 scripts** (identity via buzz-cli, join, post, admit rules), plus thin **runtime adapters**:

| Adapter | Responsibility |
|---------|----------------|
| `grok-build` | skill frontmatter, `monitor()` soft-wake, Grok skill paths |
| `codex` | Codex skill layout, lane/session, Desktop drain model |
| `antigravity` | AG CLI invoke, workspace bind, wake/drain mapping |

Antigravity work starts with a **stub adapter doc** and one proof: “join room + post seat card + respect C1/C2” — not a full port on day one.

---

## Agent layer

| | |
|--|--|
| **MUST** | Keep Grok companion pack **private** until Phase 3 gate is green |
| **MUST NOT** | Push live dogfood secrets into any `public-export` or GitHub |
| **MUST** | Treat Codex / Grok / (later) Antigravity as adapters under the same contracts |
| **MUST NOT** | Diverge soft-wake / C1 / dual-body per runtime without SOT agreement |
| **MAY** | Version private mirror repos for rehearsal |
| **MAY** | Stub Antigravity adapter docs without implementing full skill yet |

---

## Related

- [02-doctrine-contracts.md](02-doctrine-contracts.md) — C2 soft-wake, C8 skill flock  
- [04-core-vs-skill-pack.md](04-core-vs-skill-pack.md) — upstream vs operator packs  
- [07-security-and-redaction.md](07-security-and-redaction.md) — redaction  
- Live Grok skill: operator machine skill path (e.g. `~/.grok/skills/use-buzz`)  
- Codex adapter: separate private workspace with optional `public-export/`  
- Private Grok mirror: separate private workspace (Phase 1); not published from this monorepo  
