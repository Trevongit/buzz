# Remote Agents dogfood (laptop ↔ headless home)

## Rebuild?

| Who | Need Desktop rebuild? |
|-----|------------------------|
| home-grok / host-agentd | **No** — CLI + Python daemon |
| Traveling laptop Desktop | **Yes** — `feat/remote-agents-desktop` |
| Home Desktop GUI | Optional only |

## Home (already P3 GREEN)

```bash
# ensure daemon
systemctl --user status host-agentd.service
curl -sS -H "Authorization: Bearer $(cat ~/.buzz-dev/hosts/home/controller.token)" \
  http://127.0.0.1:8787/v1/health
```

Keep bind on `127.0.0.1` until laptop tunnel is proven (Codex gate).

## Laptop tunnel

```bash
ssh -L 8787:127.0.0.1:8787 <user>@asus-g501vw.tailb74de6.ts.net
# token: from open121 DM / never paste in Buzz room
curl -sS -H "Authorization: Bearer $HOST_AGENTD_TOKEN" http://127.0.0.1:8787/v1/status | head
```

## Desktop UI

```bash
cd <buzz-repo>
git checkout feat/remote-agents-desktop
just desktop-dev   # or just dev
# Agents → Remote Agents → Host
#   baseUrl: http://127.0.0.1:8787
#   token:   (from DM)
#   default room: agent-metabolism UUID
# Refresh → Arm co-lab-gemma / Stop
```

## Negative checks

```bash
# no auth
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/v1/status
# expect 401

# bad token
curl -sS -o /dev/null -w '%{http_code}\n' \
  -H 'Authorization: Bearer wrong' http://127.0.0.1:8787/v1/status
# expect 401

# unknown preset
curl -sS -X POST -H "Authorization: Bearer $HOST_AGENTD_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"preset":"rm-rf"}' \
  http://127.0.0.1:8787/v1/agents/home-grok/arm
# expect 400 unknown preset
```
