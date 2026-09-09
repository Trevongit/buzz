#!/usr/bin/env python3
"""True-usage ecosystem GIF for #BUZZ pathways-lab. No hosts, keys, room IDs."""
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
HUMAN = (250, 179, 135)
OK = (166, 227, 161)
CARD = (49, 50, 68)
DIM = (69, 71, 90)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for p in (
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("/usr/share/fonts/TTF") / name,
    ):
        if p.is_file():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


F_TITLE = font(28, True)
F_SUB = font(16, False)
F_H = font(18, True)
F_B = font(15, False)
F_S = font(14, False)


def round_box(d, xy, fill, outline=LINE, r=14, width=2):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


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


BEATS = [
    (
        "1  Human says use buzz",
        "One skill on the machine. Existing seat. Community from PUBLIC.txt. No mint.",
    ),
    (
        "2  GUI stays eyes",
        "Grok Build, Codex Desktop, Antigravity IDE listen and review. Do not Custom-harness.",
    ),
    (
        "3  Only the named visitor wakes",
        "L0 detect is free. Idle vendors do not poll with a model. Lease-held = already listening.",
    ),
    (
        "4  Nerve runs in git-free scratch",
        "codex exec / agy --print. Folder name is not a seat. Files and diffs go back to the GUI.",
    ),
    (
        "5  Buzz keeps one piece of evidence",
        "Rooms are shared history. Promote findings, not every inner-loop thought. TTY first.",
    ),
    (
        "6  Idle = 0 tokens",
        "Stop. Do not stack L2. Glue (CLI <-> GUI) is optional. Visitor kit is extras bring.sh.",
    ),
]


def draw_frame(step: int) -> Image.Image:
    im = Image.new("RGB", (1400, 820), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1400, 8), fill=GROK)
    d.text((40, 22), "How we actually use Buzz", font=F_TITLE, fill=INK)
    d.text(
        (40, 60),
        "Visitor kit outside Desktop ACP.  GUI = eyes.  CLI = nerve.  Buzz = evidence.",
        font=F_SUB,
        fill=MUTED,
    )

    def vendor(xy, color, title, lines, hot: bool):
        outline = color if hot else LINE
        round_box(d, xy, CARD, outline, width=3 if hot else 2)
        x1, y1, x2, y2 = xy
        d.rectangle((x1, y1, x2, y1 + 44), fill=color if hot else DIM)
        d.text((x1 + 16, y1 + 12), title, font=F_H, fill=BG if hot else MUTED)
        yy = y1 + 58
        for line in lines:
            d.text((x1 + 16, yy), line, font=F_B, fill=INK if hot else MUTED)
            yy += 22

    # hot vendors per beat
    hot_h = step in (0, 5)
    hot_g = step in (0, 1, 2, 5)
    hot_c = step in (1, 2, 3, 4)
    hot_a = step in (1, 2, 3, 4)
    hot_b = step in (0, 2, 4, 5)
    hot_k = step in (0, 2)

    vendor(
        (40, 110, 430, 300),
        HUMAN,
        "HUMAN",
        ["decides", "reviews diffs in the GUI", "never pastes keys"],
        hot_h,
    )
    vendor(
        (970, 110, 1360, 300),
        GROK,
        "GROK BUILD",
        ["interactive steward", "watcher, not a second L2", "synthesizes for Prime"],
        hot_g,
    )
    vendor(
        (40, 320, 430, 530),
        CODEX,
        "CODEX",
        ["Desktop = eyes", "CLI exec = nerve", "glue is CLI <-> Desktop"],
        hot_c,
    )
    vendor(
        (970, 320, 1360, 530),
        AGY,
        "ANTIGRAVITY",
        ["IDE = eyes", "CLI print = nerve", "not Desktop agy-acp"],
        hot_a,
    )

    # center Buzz + kit
    round_box(d, (460, 140, 940, 430), CARD, GROK if hot_b else LINE, width=3 if hot_b else 2)
    d.text((490, 160), "BUZZ  rooms", font=F_H, fill=GROK if hot_b else MUTED)
    for i, t in enumerate(
        [
            "shared membership, signed events",
            "evidence Prime can read",
            "not a second chat app",
            "not vendor ownership",
        ]
    ):
        d.text((490, 200 + i * 26), t, font=F_B, fill=INK if hot_b else MUTED)

    round_box(d, (460, 450, 940, 530), CARD, OK if hot_k else LINE, width=3 if hot_k else 2)
    d.text((490, 462), "VISITOR KIT", font=F_H, fill=OK if hot_k else MUTED)
    d.text((490, 494), "bring.sh   then   use buzz   (not UATP, not ACP)", font=F_B, fill=INK if hot_k else MUTED)

    caption, body = BEATS[step]
    round_box(d, (40, 560, 1360, 720), CARD, HUMAN)
    d.rectangle((40, 560, 56, 720), fill=HUMAN)
    d.text((80, 580), caption, font=F_H, fill=HUMAN)
    yy = 624
    for line in wrap(d, body, F_B, 1220):
        d.text((80, yy), line, font=F_B, fill=INK)
        yy += 26

    d.text(
        (40, 750),
        "Two doors: Desktop ACP internals stay inside. Visitors stay outside. Do not mix.",
        font=F_S,
        fill=MUTED,
    )
    d.text(
        (40, 778),
        "MOCK of true usage  ·  LIVE-SAFE labels  ·  no hosts, keys, or room IDs",
        font=F_S,
        fill=MUTED,
    )
    return im


def main():
    frames = [draw_frame(i) for i in range(6)]
    still = OUT / "06-ecosystem-true.png"
    frames[0].save(still, "PNG", optimize=True)
    print(still)
    pal = [fr.convert("P", palette=Image.Palette.ADAPTIVE, colors=64) for fr in frames]
    gif = OUT / "workflow-ecosystem-true.gif"
    pal[0].save(
        gif,
        save_all=True,
        append_images=pal[1:],
        duration=4200,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(gif, "frames", len(frames), "ms 4200")


if __name__ == "__main__":
    main()
