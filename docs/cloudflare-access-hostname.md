# Extra hostname + Cloudflare Access

Two doors, one community:

- Tailscale: `https://asus-g501vw.tailb74de6.ts.net` (unchanged)
- Public: `https://buzz.middlewaylabs.com` (Access-gated)

Do not reuse `mesh-test.middlewaylabs.com` or `a2a.middlewaylabs.com`.

## Relay (asus / home-grok)

Keep the community row on the tailnet host. Teach the extra name as an alias:

```
BUZZ_COMMUNITY_HOST_ALIASES=buzz.middlewaylabs.com
```

NIP-42 AUTH and Blossom URLs follow the request `Host`, so a client on the
public door authenticates as `wss://buzz.middlewaylabs.com` and receives media
URLs on that host.

If you lock CORS, include both HTTPS origins:

```
BUZZ_CORS_ORIGINS=https://asus-g501vw.tailb74de6.ts.net,https://buzz.middlewaylabs.com,tauri://localhost
```

`RELAY_URL` scheme (`ws` vs `wss`) is the scheme used in AUTH and media URLs.
Both doors should be TLS, so prefer `wss://asus-g501vw.tailb74de6.ts.net`.

Tunnel, DNS, and the Access application stay on the asus host.

## Clients without Tailscale (Windows PC)

Point the client at the public door and set a Cloudflare Access **service
token** (machine credentials, not a person login):

```
BUZZ_RELAY_URL=https://buzz.middlewaylabs.com
BUZZ_CF_ACCESS_CLIENT_ID=...
BUZZ_CF_ACCESS_CLIENT_SECRET=...
```

The unprefixed Cloudflare names `CF_ACCESS_CLIENT_ID` and
`CF_ACCESS_CLIENT_SECRET` are also accepted. Set both or neither.

`buzz` CLI, Desktop native HTTP/WebSocket, and `buzz-ws-client` attach
`CF-Access-Client-Id` and `CF-Access-Client-Secret` on every request and on
the WebSocket upgrade. Never print those values.

HomeFit and other apps can use the same env pair once this door exists.
This tree does not rewrite HomeFit.
