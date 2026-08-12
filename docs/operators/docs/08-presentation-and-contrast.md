# 08 · Presentation & contrast (why not “agent-in-Slack”)

**Writing standard:** [00-readable-doctrine.md](00-readable-doctrine.md)  
**Visual artifact:** [../presentations/multi-host-doctrine-responsive.html](../presentations/multi-host-doctrine-responsive.html) (open in a local browser)  
**Channel-safe:** [../presentations/multi-host-doctrine-glance.md](../presentations/multi-host-doctrine-glance.md) (PDF/PNG can be rendered locally when needed — HTML is blocked on Blossom)  

---

## Human layer

People already know agent-in-chat products. They are good at the first week: shared context, a coworker that “lives” in the room, tasks that move.

The quiet failure mode is later: **drift**. Bodies without place, silent token burn, rooms that multiply, humans who become the only real governor.

This doctrine is not “Buzz instead of chat.” It is a **higher class of requirements** for multi-host, long-lived agent practice — and an honest contrast table for outsiders who only know platform-locked agent workflows.

The presentation’s job is **inspiration with honesty** — not a funnel. Soft north star for why we write this way: [01-vision-and-use-cases.md · Operator intent](01-vision-and-use-cases.md#operator-intent-soft-north-star) (gifted abundance over short-lived extraction; usefulness first).

## Technical layer

### Media constraint (operators)

| Format | In Buzz channel / Blossom? | Why |
|--------|----------------------------|-----|
| `.html` / `text/html` | **Blocked** | Stored XSS risk (CLI + relay) |
| `.svg` / JS | **Blocked** | Same class of active content |
| `.md` / `.pdf` / images | **Allowed** | Safe generic / image pipelines |
| Local HTML file | **Yes on disk** | Open in browser; not via media attach |

Do not work around the block by renaming `.html` → `.txt` — content sniff still rejects HTML.

### Contrast table (public-safe)

See presentation markdown. Names like “typical agent-in-chat systems” stay generic in public packs; private SOT may say “Slack-style agent workflows” when the team is comparing product posture.

### Where presentation fits in the package

| Artifact | Role |
|----------|------|
| Responsive HTML | Inspiring, phone-friendly **landing** for humans |
| Glance markdown | SOT + channel attach, agent-parseable |
| PDF / PNG | Channel attach when HTML cannot travel |
| Contracts 02 | Enforceable DNA under the inspiration |

## Agent layer

| | |
|--|--|
| **MUST** | Prefer md/pdf/png for channel doctrine attachments |
| **MUST NOT** | Attempt HTML/SVG/JS uploads as media (will fail; by design) |
| **MAY** | Point operators to local HTML for the best reading experience |
| **MUST** | Keep contrast claims honest — no over-claim that core product already ships full dual-body/staff |
