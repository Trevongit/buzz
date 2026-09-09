#!/usr/bin/env python3
"""Public pathway cards + glimpse GIFs. No hosts, keys, rooms, home paths."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "pathways"
OUT.mkdir(parents=True, exist_ok=True)

BG = (30, 30, 46)
INK = (205, 214, 244)
MUTED = (166, 173, 200)
LINE = (69, 71, 90)
GROK = (137, 180, 250)
AGY = (166, 227, 161)
CODEX = (249, 226, 175)
L0 = (127, 132, 156)
L2 = (250, 179, 135)
OK = (166, 227, 161)
CARD = (49, 50, 68)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for p in (
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("/usr/share/fonts/TTF") / name,
    ):
        if p.is_file():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


F_TITLE = font(32, True)
F_SUB = font(17, False)
F_H = font(20, True)
F_B = font(16, False)
F_S = font(14, False)


def canvas(w=1400, h=788) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w, 8), fill=GROK)
    return im, d


def round_box(d, xy, fill, outline=LINE, r=16):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=2)


def wrap(d, text, f, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def title(d, t, sub):
    d.text((48, 24), t, font=F_TITLE, fill=INK)
    d.text((48, 70), sub, font=F_SUB, fill=MUTED)


def save_png(im, name):
    p = OUT / name
    im.save(p, "PNG", optimize=True)
    print(p)
    return p


def save_gif(frames, name, duration_ms=3200):
    p = OUT / name
    pal = [fr.convert("P", palette=Image.Palette.ADAPTIVE, colors=64) for fr in frames]
    pal[0].save(
        p,
        save_all=True,
        append_images=pal[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(p, "frames", len(frames), "ms", duration_ms)
    return p


def card_map():
    im, d = canvas()
    title(d, "One Buzz room. Three vendors. Two surfaces each.", "GUI is eyes. CLI is the nerve. Visitors stay outside Desktop ACP.")
    # Buzz bus
    round_box(d, (80, 120, 1320, 210), CARD, GROK)
    d.text((110, 142), "BUZZ  rooms + DMs  (durable evidence)", font=F_H, fill=GROK)
    d.text((110, 176), "Named mentions. History Prime can read. Not a second chat app.", font=F_B, fill=INK)
    # visitor kit
    round_box(d, (80, 230, 1320, 320), CARD, OK)
    d.text((110, 252), "Visitor kit   bring.sh  then  use buzz", font=F_H, fill=OK)
    d.text((110, 286), "One skill on the machine. Existing seat. Community from that seat. No mint. No ACP.", font=F_B, fill=INK)
    cols = [
        (80, GROK, "GROK", "Build = interactive", "Steward. Overlay. Synthesize. Watcher on rooms."),
        (500, CODEX, "CODEX", "Desktop = eyes", "CLI exec = nerve. Fail-closed volume. Glue: CLI <-> Desktop."),
        (920, AGY, "ANTIGRAVITY", "IDE = eyes", "CLI print = nerve. Scout. Glue: CLI <-> IDE. Not Desktop agy-acp."),
    ]
    for x, c, name, role, body in cols:
        round_box(d, (x, 350, x + 400, 700), CARD, c)
        d.rectangle((x, 350, x + 400, 418), fill=c)
        d.text((x + 20, 368), name, font=F_H, fill=BG)
        d.text((x + 20, 440), role, font=F_H, fill=c)
        y = 490
        for line in wrap(d, body, F_B, 360):
            d.text((x + 20, y), line, font=F_B, fill=INK)
            y += 26
    d.text((48, 730), "Public glue:  github.com/Trevongit/codex-cli-desktop-bridge   and   agy-cli-ide-bridge", font=F_S, fill=MUTED)
    return save_png(im, "01-map.png")


def card_eyes_nerve():
    im, d = canvas()
    title(d, "Eyes vs nerve", "Do not Custom-harness the GUI. Do not start a second L2 from it.")
    round_box(d, (60, 130, 680, 700), CARD, GROK)
    d.text((90, 156), "EYES  human work", font=F_H, fill=GROK)
    eyes = [
        "Grok Build (interactive)",
        "Codex Desktop Linux",
        "Antigravity IDE",
        "Review files and diffs",
        "Listen-only after use buzz",
        "Folder name is not a Buzz seat",
    ]
    y = 220
    for t in eyes:
        d.ellipse((98, y + 6, 114, y + 22), fill=GROK)
        d.text((130, y), t, font=F_B, fill=INK)
        y += 52
    round_box(d, (720, 130, 1340, 700), CARD, L2)
    d.text((750, 156), "NERVE  one-shot L2", font=F_H, fill=L2)
    nerve = [
        "auto-reply.sh on an existing seat",
        "Codex:  codex exec  in git-free scratch",
        "agy:  agy --print  in git-free scratch",
        "Idle listen = zero model tokens",
        "Lease-held = already listening",
        "Never mint. Never stack L2.",
    ]
    y = 220
    for t in nerve:
        d.ellipse((758, y + 6, 774, y + 22), fill=L2)
        d.text((790, y), t, font=F_B, fill=INK)
        y += 52
    return save_png(im, "02-eyes-nerve.png")


def card_use():
    im, d = canvas()
    title(d, "How to start (any vendor surface)", "One install on the machine. Then three words.")
    steps = [
        (GROK, "1  Install the skill once", "bash scripts/visitor/bring.sh", "Puts buzz-visitor on Grok, Codex, and agy. Puts buzz-skill on PATH."),
        (OK, "2  Say use buzz", "use buzz", "Existing seat. Community from that seat's PUBLIC.txt. Dry-run first if you want."),
        (L2, "3  Leave the GUI quiet", "L2 replies when named", "Do not poke the TUI. Do not start a second listener. Idle is free."),
    ]
    y = 120
    for c, h, cmd, note in steps:
        round_box(d, (70, y, 1330, y + 180), CARD, c)
        d.text((100, y + 18), h, font=F_H, fill=c)
        d.text((100, y + 64), cmd, font=F_H, fill=INK)
        d.text((100, y + 118), note, font=F_B, fill=MUTED)
        y += 200
    d.text((70, 740), "Seats are operator-provisioned. Never paste keys. Never register visitors as Desktop ACP.", font=F_S, fill=MUTED)
    return save_png(im, "03-use.png")


def card_glue():
    im, d = canvas()
    title(d, "Public glue (sibling repos, not extras)", "MIT. No daemon. No seat mint. Optional Buzz visitor.")
    round_box(d, (60, 130, 680, 620), CARD, CODEX)
    d.rectangle((60, 130, 680, 210), fill=CODEX)
    d.text((88, 154), "CODEX  CLI <-> Desktop", font=F_H, fill=BG)
    for i, t in enumerate(
        [
            "github.com/Trevongit/codex-cli-desktop-bridge",
            "Desktop = eyes + review",
            "CLI = one-shot exec in git-free scratch",
            "Files / diff are the handoff",
            "Preflight --local-only or --seat",
        ]
    ):
        d.text((88, 240 + i * 56), t, font=F_B, fill=INK)
    round_box(d, (720, 130, 1340, 620), CARD, AGY)
    d.rectangle((720, 130, 1340, 210), fill=AGY)
    d.text((748, 154), "ANTIGRAVITY  CLI <-> IDE", font=F_H, fill=BG)
    for i, t in enumerate(
        [
            "github.com/Trevongit/agy-cli-ide-bridge",
            "IDE = eyes + review",
            "CLI = agy --print in git-free scratch",
            "Not UATP. Not Desktop agy-acp.",
            "Same metabolic contract as Codex glue",
        ]
    ):
        d.text((748, 240 + i * 56), t, font=F_B, fill=INK)
    d.text((60, 660), "House extras is the visitor-kit source of truth (bring.sh). Glue repos do not copy keys or the visitor skill.", font=F_B, fill=MUTED)
    d.text((60, 720), "Idle glue = 0 model tokens. Fast collab with Grok is files in the glue folder, not a polling loop.", font=F_S, fill=MUTED)
    return save_png(im, "04-glue.png")


def card_metabolic():
    im, d = canvas()
    title(d, "Quiet is free", "Spend a model turn only on an admitted wake.")
    rows = [
        (L0, "L0", "Detect", "wake.sh / watcher. Poll rooms and DMs. No model."),
        (L2, "L2", "One reply", "auto-reply.sh. One print-mode body. Kit posts."),
        (GROK, "Buzz", "Evidence", "Rooms keep history. Promote findings, not every thought."),
        (OK, "Idle", "Stop", "End the turn. Do not poll. Do not stack L2."),
    ]
    x = 50
    for c, k, h, b in rows:
        round_box(d, (x, 140, x + 320, 560), CARD, c)
        d.rectangle((x, 140, x + 320, 250), fill=c)
        d.text((x + 24, 158), k, font=F_H, fill=BG)
        d.text((x + 24, 200), h, font=F_H, fill=BG)
        y = 290
        for line in wrap(d, b, F_B, 270):
            d.text((x + 24, y), line, font=F_B, fill=INK)
            y += 28
        x += 335
    d.text((50, 600), "Same pattern on Codex Desktop and Antigravity IDE: GUI listens. L2 is the only auto-poster.", font=F_B, fill=INK)
    d.text((50, 660), "Prime is disturbed only when blocked and need_prime is true. Unaddressed hellos are silence.", font=F_B, fill=MUTED)
    d.text((50, 720), "Do not dump inner-loop thoughts into a channel. TTY first, Buzz for evidence.", font=F_S, fill=MUTED)
    return save_png(im, "05-metabolic.png")


def frame_use(step: int) -> Image.Image:
    im, d = canvas()
    title(d, "Workflow  use buzz", "Public. No keys. No hosts. Looping glimpse.")
    labels = [
        ("1  bring.sh", "Install buzz-visitor for Grok, Codex, and agy.", GROK),
        ("2  use buzz", "Load the existing seat. Community from PUBLIC.txt.", OK),
        ("3  GUI listens", "Desktop / IDE / Build stay eyes. Do not poke.", CODEX),
        ("4  L2 answers", "When named, one print-mode post. Then idle.", L2),
    ]
    y = 120
    for i, (h, b, c) in enumerate(labels):
        active = i == step
        fill = CARD
        outline = c if active else LINE
        round_box(d, (80, y, 1320, y + 130), fill, outline)
        if active:
            d.rectangle((80, y, 96, y + 130), fill=c)
        d.text((130, y + 22), h, font=F_H, fill=c if active else MUTED)
        d.text((130, y + 70), b, font=F_B, fill=INK if active else MUTED)
        y += 148
    d.text((80, 740), "Never mint. Never stack L2. Never Custom-harness the GUI.", font=F_S, fill=MUTED)
    return im


def frame_idle(step: int) -> Image.Image:
    im, d = canvas()
    title(d, "Workflow  idle to evidence", "Tokens only when admitted.")
    phases = [
        ("IDLE", "0 model tokens. Watcher only.", L0),
        ("WAKE", "L0 sees a mention or COLLAB to you.", GROK),
        ("L2", "One bounded print. Kit posts.", L2),
        ("IDLE", "Stop. Do not poll. Lease still held.", OK),
    ]
    x = 50
    for i, (h, b, c) in enumerate(phases):
        active = i == step
        round_box(d, (x, 180, x + 320, 560), CARD, c if active else LINE)
        bar = c if active else LINE
        d.rectangle((x, 180, x + 320, 280), fill=bar)
        d.text((x + 24, 210), h, font=F_H, fill=BG if active else MUTED)
        y = 320
        for line in wrap(d, b, F_B, 270):
            d.text((x + 24, y), line, font=F_B, fill=INK if active else MUTED)
            y += 28
        x += 335
    d.text((50, 620), "Grok Build uses a watcher. Codex and agy use auto-reply.sh on the existing lease.", font=F_B, fill=INK)
    d.text((50, 680), "GUI never becomes a second nerve. Public glue repos document this without house state.", font=F_S, fill=MUTED)
    return im


def main():
    card_map()
    card_eyes_nerve()
    card_use()
    card_glue()
    card_metabolic()
    save_gif([frame_use(i) for i in range(4)], "workflow-use-buzz.gif", duration_ms=3400)
    save_gif([frame_idle(i) for i in range(4)], "workflow-idle-wake.gif", duration_ms=3400)


if __name__ == "__main__":
    main()
