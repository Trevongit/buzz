# Channel index pack

A local file agents and the Foundation page can both eat. Not a second relay.

Path: `~/.buzz-dev/channel-index.json`

extras writes it. grok-app reads it with one host command, the same shape as
Composer extras. The page may search the pack. It must not write the pack in
the first slice. It must not put a key or a relay URL in the file.

Dump:

```bash
bash scripts/visitor/channel-index-dump.sh --seat buzz --room 906ae9ef-4c86-474a-ac15-966c18053432
```

Cap: 80 rooms, 20 messages each. A house dump uses one `--room` per channel
and a small `--limit` so agents can eat every wall without a second relay.

## Shape

```json
{
  "version": 1,
  "written_at": 0,
  "rooms": [
    {
      "id": "906ae9ef-4c86-474a-ac15-966c18053432",
      "name": "buzz-web-app-research",
      "messages": [
        {
          "id": "hex",
          "pubkey": "hex",
          "created_at": 0,
          "kind": 9,
          "content": "plaintext"
        }
      ]
    }
  ]
}
```

Missing keys take empty lists. Unknown keys are ignored. Content is the signed
message body. No nsec. No tags dump in v1.
