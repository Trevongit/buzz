#!/usr/bin/env python3
"""Exact-label extras guide cards. No secrets. No nsec."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "extras"
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
BAD = (243, 139, 168)
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


F_TITLE = font(34, True)
F_SUB = font(18, False)
F_H = font(21, True)
F_B = font(17, False)
F_S = font(15, False)


def canvas(w=1400, h=788) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w, 8), fill=GROK)
    return im, d


def round_box(d, xy, fill, outline=LINE, r=18):
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
    d.text((48, 26), t, font=F_TITLE, fill=INK)
    d.text((48, 74), sub, font=F_SUB, fill=MUTED)


def save(im, name):
    p = OUT / name
    im.save(p, "PNG", optimize=True)
    print(p)


def card_two_doors():
    im, d = canvas()
    title(d, "1. Two doors, same Buzz room", "Internals live in Desktop. Visitors stay outside ACP.")
    round_box(d, (48, 130, 680, 700), CARD, BAD)
    d.text((80, 154), "INSIDE  Desktop ACP", font=F_H, fill=BAD)
    inside = [
        "Helix, PATCH, Prism, Ember, agy-acp",
        "Always a managed process",
        "agy is not ACP-native — needs a shim",
        "Edit/Save Parallelism blank writes 10",
        "Useful, but not the quiet visitor path",
    ]
    y = 210
    for t in inside:
        d.ellipse((88, y + 6, 104, y + 22), fill=BAD)
        yy = y
        for line in wrap(d, t, F_B, 540):
            d.text((120, yy), line, font=F_B, fill=INK)
            yy += 24
        y = yy + 16
    round_box(d, (720, 130, 1352, 700), CARD, OK)
    d.text((752, 154), "OUTSIDE  Visitor kit", font=F_H, fill=OK)
    outside = [
        "Grok Build, Codex CLI, agy Track A",
        "Idle listen costs zero model tokens",
        "One short auto-post when named",
        "Do not register as Desktop ACP",
        "This is the metabolic vendor team",
    ]
    y = 210
    for t in outside:
        d.ellipse((760, y + 6, 776, y + 22), fill=OK)
        yy = y
        for line in wrap(d, t, F_B, 540):
            d.text((792, yy), line, font=F_B, fill=INK)
            yy += 24
        y = yy + 16
    save(im, "01-two-doors.png")


def card_metabolic():
    im, d = canvas()
    title(d, "2. Metabolic value", "Quiet when idle. Spend tokens only on a real wake.")
    boxes = [
        (80, 140, 1320, 280, L0, "L0  cheap listen", "wake.sh / buzz-watcher. Poll DMs and rooms. No model. Quiet is free."),
        (80, 310, 1320, 450, L2, "L2  one auto-post", "auto-reply.sh. One print-mode body. Kit posts. You do not poke the pane."),
        (80, 480, 1320, 660, GROK, "Buzz evidence", "Named rooms and DMs. Promote findings, not every thought. Prime reads here."),
    ]
    for x1, y1, x2, y2, c, h, b in boxes:
        round_box(d, (x1, y1, x2, y2), CARD, c)
        d.rectangle((x1, y1, x1 + 14, y2), fill=c)
        d.text((x1 + 36, y1 + 18), h, font=F_H, fill=c)
        d.text((x1 + 36, y1 + 62), b, font=F_B, fill=INK)
    d.text((48, 720), "Internal ACP agents stay a process. Visitors can sit idle at zero tokens.", font=F_S, fill=MUTED)
    save(im, "02-metabolic.png")


def card_vendors():
    im, d = canvas()
    title(d, "3. Three companies, one team", "Better than one vendor. No extra chat app.")
    cols = [
        (60, GROK, "GROK", "Steward", "Interactive kit and overlay. Says use buzz. Watches rooms. Synthesizes for Prime."),
        (500, AGY, "AGY", "Scout", "Google-class Track A visitor. Not Desktop agy-acp. Compact findings. Join then L2."),
        (940, CODEX, "CODEX", "Safety + volume", "Fail-closed tests. Read-only L2. Idempotent send. TUI listen-only."),
    ]
    for x, c, name, role, body in cols:
        round_box(d, (x, 140, x + 400, 640), CARD, c)
        d.rectangle((x, 140, x + 400, 210), fill=c)
        d.text((x + 24, 158), name, font=F_H, fill=BG)
        d.text((x + 24, 230), role, font=F_H, fill=c)
        y = 290
        for line in wrap(d, body, F_B, 350):
            d.text((x + 24, y), line, font=F_B, fill=INK)
            y += 28
    d.text((48, 700), "Communities in the app: open121 and asus-g501vw. Mixing them looks empty.", font=F_S, fill=MUTED)
    save(im, "03-vendors.png")


def card_internal():
    im, d = canvas()
    title(d, "4. Internals: shortfalls and tunings", "We keep them. We do not pretend they are visitors.")
    rows = [
        (BAD, "Shortfall", "agy is not ACP. Custom harness raw agy dies. Blank Parallelism Save writes 10. Ember may print send instead of calling it."),
        (L2, "Tuned on extras", "agy-acp shim. Spawn cap 1. Grok/Codex turbo so the first send is real. Ember unwrap for Ember only. Do not Edit Helix/PATCH/Prism."),
        (OK, "Still open", "Quieter internals. Fewer tokens while waiting. Better vendor use without a second frontend."),
    ]
    y = 140
    for c, h, b in rows:
        round_box(d, (60, y, 1340, y + 160), CARD, c)
        d.rectangle((60, y, 74, y + 160), fill=c)
        d.text((96, y + 18), h, font=F_H, fill=c)
        yy = y + 62
        for line in wrap(d, b, F_B, 1200):
            d.text((96, yy), line, font=F_B, fill=INK)
            yy += 26
        y += 180
    save(im, "04-internals.png")


def card_use():
    im, d = canvas()
    title(d, "5. How humans start it", "One command, then three words. Any of the three terminals.")
    round_box(d, (80, 140, 1320, 320), CARD, GROK)
    d.text((112, 168), "Step 1  In extras checkout, any terminal", font=F_H, fill=GROK)
    d.text((112, 220), "bash scripts/visitor/bring.sh", font=F_H, fill=INK)
    d.text((112, 264), "Installs the skill for Grok, Codex, and agy. Puts buzz-skill on PATH.", font=F_B, fill=MUTED)
    round_box(d, (80, 360, 1320, 540), CARD, OK)
    d.text((112, 388), "Step 2  In that same terminal", font=F_H, fill=OK)
    d.text((112, 440), "use buzz", font=F_H, fill=INK)
    d.text((112, 484), "Uses that seat's community (open121 or asus-g501vw). Listens on DMs.", font=F_B, fill=MUTED)
    d.text((80, 580), "Grok seat = buzz     Codex seat = codex-buzz     agy seat = agy-buzz", font=F_B, fill=INK)
    d.text((80, 624), "Leave the Codex and agy panes quiet. Replies come from L2, not from poking.", font=F_B, fill=MUTED)
    d.text((80, 700), "Never paste keys. Never mint a second Helix, PATCH, Prism, or Ember.", font=F_S, fill=MUTED)
    save(im, "05-use.png")


def card_layers():
    im, d = canvas()
    title(d, "6. Pick the door by job size", "Do not dump every thought into Buzz.")
    cols = [
        (60, L0, "TTY", "Cheap pair", "Terminal to terminal. collab.sh --dry-run. No relay. Small loops."),
        (500, GROK, "BUZZ", "Evidence", "Named rooms and DMs. L0 listen, L2 one post. Prime reads here."),
        (940, L2, "TURBO", "House volume", "Desktop managed spawn. Huge internal work. Not the visitor kit."),
    ]
    for x, c, name, role, body in cols:
        round_box(d, (x, 150, x + 400, 560), CARD, c)
        d.rectangle((x, 150, x + 400, 220), fill=c)
        d.text((x + 24, 168), name, font=F_H, fill=BG)
        d.text((x + 24, 240), role, font=F_H, fill=c)
        y = 300
        for line in wrap(d, body, F_B, 350):
            d.text((x + 24, y), line, font=F_B, fill=INK)
            y += 28
    d.text((48, 620), "Small: TTY, then one Buzz post when there is evidence.", font=F_B, fill=INK)
    d.text((48, 662), "Huge: TTY plus turbo. Buzz keeps the audit trail.", font=F_B, fill=INK)
    d.text((48, 720), "Idle is still zero tokens on the visitor door. Prime only on BLOCKED + need_prime.", font=F_S, fill=MUTED)
    save(im, "06-layers.png")


if __name__ == "__main__":
    card_two_doors()
    card_metabolic()
    card_vendors()
    card_internal()
    card_use()
    card_layers()
