# Scalability and shortfalls

## Scaling story (what works as machines grow)

| Scale | What holds | What you add |
|-------|------------|--------------|
| 1 machine | App + CLI | Presence lease optional |
| 2 machines (laptop + home) | Always-on home + staff gate | Phone keys, dual seats |
| 10 hosts | Skill flock + place proof | Host roster, pack versions |
| 100+ hosts | Dual-body refuse + lean wakes | Automation of pack install, metrics on staff burn, per-host health |

**Horizontal scale** is mostly: more holons (hosts), each with allowlisted always-on + rare staffed brains — not one infinite soft-wake graph.

## Shortfalls of “core only” today (honest)

These are **product/operator gaps**, not attacks:

1. **Little public day-to-day doctrine** — README covers product, not multi-host metabolism  
2. **Soft-wake cost is easy to get wrong** — any stdout line can become a paid turn  
3. **Multi-surface confusion** — same DM can be keys vs staffed brain vs small-model chat  
4. **Remote control planes need CORS/bind discipline** — webviews and port clashes are real  
5. **Agent delete / persona / instance lifecycle** — operators must understand template vs instance  
6. **Token burn is not a first-class product meter** in-app for “staffed session running 6 hours”  
7. **External skill ecosystems** (Grok Build skills) are powerful but undocumented relative to the monorepo  

## What we want core to grow toward (upstream-friendly)

- Documented soft-wake / agent attention guidance for agent engineers  
- Place / dual-body as first-class product (where ready)  
- Clear Remote Agents host networking docs (bind, token, CORS)  
- Optional hooks for staff-session metrics  
- Stable buzz-cli contracts for skill authors  

