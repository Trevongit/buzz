# Security and redaction for public docs

**Writing standard:** [00-readable-doctrine.md](00-readable-doctrine.md)  
**Pairs with:** C7 public-snapshot rules in [02-doctrine-contracts.md](02-doctrine-contracts.md)

---

## Human layer

We teach the map. We do not leave the keys under the mat in the photo.

Dogfood runs on real relays and real paths. **Public doctrine** shows roles, contracts, and redacted results — not live credentials or home coordinates.

## Technical layer

### Never publish

- Private keys (nsec, hex), seed phrases  
- Bearer tokens, controller tokens, API keys, auth tags  
- Personal Tailscale IPs / hostnames, home GPS, street addresses  
- Internal company URLs or unreleased product secrets  
- Full channel UUIDs tied to private communities (use placeholders)  
- Screenshots with live tokens or private DMs  
- Absolute host-local paths that fingerprint a machine  

### Placeholder table (public snapshots)

| Real dogfood | Public stand-in |
|--------------|-----------------|
| Live relay URL | `https://relay.example` / `wss://relay.example` |
| Host / Tailscale name | `home-host`, `laptop-host` |
| Absolute paths | `$SEAT_ROOT`, `~/.buzz-dev/agents/<seat>/` |
| Seat keys / auth | omit or `<redacted>` |
| Private channel ids | `#example-co-lab` or `xxxxxxxx-…` |

### Safe to publish

- Architecture diagrams with roles  
- Contract tables (stdout, staff, lean rooms)  
- systemd **templates** with `%h` and env placeholders  
- Example channel **names** like `#agent-co-lab`  
- Public place-proof field names (not host-local paths)  
- Scaling narratives grounded in dogfood, without private evidence dumps  

### Evidence split

| Layer | Where it lives |
|-------|----------------|
| Contract + redacted result | Public packs / SOT docs |
| Raw dogfood transcripts, live URLs, seat env | Private workspace only |

## Agent layer

| | |
|--|--|
| **MUST** | Redact relay URLs, hostnames, absolute paths, keys before public-shaped posts |
| **MUST** | Keep dogfood evidence private; publish contracts + redacted outcomes |
| **MUST NOT** | Paste `agent.env`, nsec, or live controller tokens into SOT or packs |
| **MAY** | Use named placeholders consistently across a whole pack |

## Screenshot policy

Prefer diagrams and redacted tables over live product screenshots. If screenshots are needed, crop tokens and private hosts.

