#!/usr/bin/env python3
"""
Generates an animated terminal-style profile banner (hero.svg) for a GitHub README:
a framed panel with a rainbow ASCII knot on the left and an info panel on the right.
The knot is built from the frames of knot.gif: every frame is converted to coloured
characters, so the result stays pure SVG + CSS animations (no JS, no raster images)
and GitHub renders it inside <img>.

Usage:  python3 make_hero.py            -> writes hero.svg
Needs:  pip install pillow
Files:  knot.gif next to this script (the source animation)
Fonts:  put jetbrains-mono-latin-500-normal.woff2 and jetbrains-mono-latin-700-normal.woff2
        into ./fonts/ (npm pack @fontsource/jetbrains-mono) to embed them;
        without them the system monospace font is used.
"""
import base64
import colorsys
import os
from xml.sax.saxutils import escape

from PIL import Image, ImageSequence

# ─────────────────────────── EDIT ME ───────────────────────────
HANDLE   = "vladispot002"
NAME     = "Vladyslav Potapov"
LOCATION = "Ukraine"
SECTIONS = [
    ("About", ["SE student building tools on the side.",
               "Networking, automation, pet projects."]),
    ("Stack", ["C++ · Python · Networking · Git"]),
    ("Projects", ["air-share · secure local & remote data sharing"]),
    ("Elsewhere", ["github.com/vladispot002 · t.me/vlad_pot",
                   "instagram.com/potapov8031",
                   "linkedin.com/in/vladyslav-potapov-348328396"]),
]
SCENES   = [
    ("whoami",        ["Vladyslav Potapov · SE student · Ukraine"]),
    ("fortune",       ['"ship it before the deadline"']),
    ("cat stack.txt", ["C++ · Python · Networking · Git"]),
    ("fortune",       ['"works on my machine"']),
    ("ls projects/",  ["air-share/  telegram-bots/  gym-tracker/  applicants-site/"]),
    ("fortune",       ['"it\'s not a bug, it\'s a feature"']),
]
TYPE_DT, PRE, POST, HOLD = 0.07, 0.35, 0.3, 2.4
OUTPUT   = "hero.svg"
GIF      = "knot.gif"
# ────────────────────────────────────────────────────────────────

FY, FH = 34, 376
BOX_H = 38 + 22 * max(len(o) for _, o in SCENES)
W, H = 846, FY + FH + 14 + BOX_H + 30
COLS, ROWS = 78, 38
FS = 6.2
CW = FS * 0.6
LH = FS
CROP = (100, 20, 812, 600)
ORANGE = "#ff4500"
BG, BAR, LINE, DIM, MID, WHITE = "#0e0d11", "#15141a", "#2c2b36", "#6e6c7a", "#a9a7b8", "#f1f0f7"
RAMP = [".", ":-", "=+/", "\\|/x", "ox*", "o#x", "#$&", "@%#"]
HBINS, SLEV, VLEV = 36, (0.30, 0.65, 1.0), (0.42, 0.60, 0.80, 1.0)


def load_gif():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, GIF)
    if not os.path.exists(path):
        raise SystemExit(f"{GIF} not found next to make_hero.py")
    gif = Image.open(path)
    frames = []
    for fr in ImageSequence.Iterator(gif):
        im = fr.convert("RGB").crop(CROP).resize((COLS, ROWS), Image.BOX)
        frames.append(im)
    return frames


def quant_color(r, g, b, d):
    m = max(r, g, b) or 1
    h, s, _ = colorsys.rgb_to_hsv(r / m, g / m, b / m)
    h = round(h * HBINS) % HBINS / HBINS
    s = min(SLEV, key=lambda x: abs(x - s)) if s > 0.12 else 0.0
    v = min(VLEV, key=lambda x: abs(x - (0.55 + 0.45 * d)))
    rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
    return "#%02x%02x%02x" % (round(rr * 255), round(gg * 255), round(bb * 255))


def build_grids(frames):
    lums = sorted(sum(px) / 3 for im in frames for px in im.get_flattened_data())
    lo = 20.0
    fg = [v for v in lums if v > lo + 2]
    hi = fg[int(len(fg) * 0.9)]
    palette = {}
    grids = []
    for im in frames:
        px = im.load()
        grid = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                R, G, B = px[c, r]
                d = (((R + G + B) / 3) - lo) / (hi - lo)
                if d < 0.06:
                    row.append(None)
                    continue
                d = min(1.0, d) ** 0.6
                opts = RAMP[min(int(d * len(RAMP)), len(RAMP) - 1)]
                ch = opts[(r * 7 + c * 13) % len(opts)]
                col = quant_color(R, G, B, d)
                palette.setdefault(col, f"k{len(palette)}")
                row.append((ch, palette[col]))
            grid.append(row)
        grids.append(grid)
    return grids, palette


def frame_svg(grid, idx, n, loop_s):
    delay = -(loop_s - idx * loop_s / n)
    parts = [f'<text class="f{" f0" if idx == 0 else ""}" xml:space="preserve" style="animation-delay:{delay:.3f}s">']
    for r, row in enumerate(grid):
        cells = row
        first = next((i for i, x in enumerate(cells) if x), None)
        if first is None:
            continue
        last = max(i for i, x in enumerate(cells) if x)
        runs = []
        for x in cells[first:last + 1]:
            if x is None:
                runs[-1][1] += " "
            elif runs and runs[-1][0] == x[1]:
                runs[-1][1] += x[0]
            else:
                runs.append([x[1], x[0]])
        spans = "".join(f'<tspan class="{k}">{escape(s)}</tspan>' for k, s in runs)
        parts.append(f'<tspan x="{first * CW:.1f}" y="{(r + 1) * LH:.1f}">{spans}</tspan>')
    parts.append("</text>")
    return "".join(parts)


def font_faces():
    here = os.path.dirname(os.path.abspath(__file__))
    css = ""
    for weight in (500, 700):
        path = os.path.join(here, "fonts", f"jetbrains-mono-latin-{weight}-normal.woff2")
        if os.path.exists(path):
            b64 = base64.b64encode(open(path, "rb").read()).decode()
            css += f"@font-face{{font-family:JB;font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        else:
            print(f"note: {path} not found, falling back to system monospace")
    return css


def build():
    gif_frames = load_gif()
    n = len(gif_frames)
    loop_s = n * 0.12
    grids, palette = build_grids(gif_frames)
    frames = [frame_svg(g, i, n, loop_s) for i, g in enumerate(grids)]
    step = 100 / n

    seq = []
    def add(_=0):
        seq.append(1)
        return f"a{len(seq) - 1}"

    fx, fy, fw, fh = 24, FY, 798, FH
    knot_w, knot_h = COLS * CW, ROWS * LH
    cx = 24 + 168
    dx, dy = cx - knot_w / 2, fy + 52 + (fh - 52 - 10 - knot_h) / 2
    div_x, tx = 372, 398

    defs = (
        '<pattern id="dots" width="6" height="6" patternUnits="userSpaceOnUse">'
        '<circle cx="3" cy="3" r=".6" fill="#ffffff" opacity=".07"/></pattern>'
    )

    body = []
    body.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="{BG}"/>')
    body.append(f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="8" fill="none" stroke="{ORANGE}" '
                f'stroke-width="1.4" pathLength="1" class="dr"/>')
    tag_w = len(HANDLE) * 13 * 0.6 + 16
    body.append(f'<g class="{add()}"><rect x="38" y="{fy - 8}" width="{tag_w:.1f}" height="16" fill="{BG}"/>'
                f'<text x="45" y="{fy + 4.5}" font-size="13" fill="{ORANGE}">{escape(HANDLE)}</text></g>')
    body.append(f'<path d="M{div_x} {fy + 22}V{fy + fh - 22}" stroke="{ORANGE}" stroke-width="1.2" opacity=".55" '
                f'class="{add()}" style="transform-origin:{div_x}px {fy + fh / 2:.0f}px"/>')
    body.append(f'<g class="{add()} pop" style="transform-origin:{cx}px {dy + knot_h / 2:.0f}px">'
                f'<g transform="translate({dx:.1f},{dy:.1f})">{"".join(frames)}</g></g>')
    body.append(f'<g class="{add()}"><text x="{cx}" y="{fy + 26}" font-size="14.5" fill="{ORANGE}" '
                f'text-anchor="middle" font-weight="700">{escape(NAME)}</text></g>')
    body.append(f'<g class="{add()}"><text x="{cx}" y="{fy + 44}" font-size="12.5" fill="{DIM}" '
                f'text-anchor="middle">{escape(LOCATION)}</text></g>')

    y = fy + 38
    for si, (head, lines) in enumerate(SECTIONS):
        acc = ORANGE
        if si > 0:
            body.append(f'<path d="M{tx - 2} {y - 8}H{fx + fw - 24}" stroke="{LINE}" stroke-width="1" class="{add()}"/>')
            y += 20
        body.append(f'<g class="{add()}"><rect x="{tx - 14}" y="{y - 10}" width="3" height="12" rx="1.5" fill="{acc}"/>'
                    f'<text x="{tx}" y="{y}" font-size="13" fill="{acc}" font-weight="700">{escape(head)}</text></g>')
        y += 22
        for ln in lines:
            body.append(f'<g class="{add()}"><text x="{tx}" y="{y}" font-size="13" fill="{MID}">{escape(ln)}</text></g>')
            y += 20
        y += 8

    py = fy + fh + 14
    cwp = 13.5 * 0.6
    timing, t0 = [], 0.0
    for cmd, outs in SCENES:
        ty0 = t0 + PRE
        ty1 = ty0 + len(cmd) * TYPE_DT
        o0 = ty1 + POST
        end = o0 + 0.15 * len(outs) + HOLD
        timing.append((t0, ty0, ty1, o0, end))
        t0 = end
    T = t0
    pc = lambda t: t / T * 100
    gname = add()
    D = 0.35 + (len(seq) - 1) * 0.1 + 0.3
    kf = ""
    scenes = []
    for k, ((cmd, outs), (a0, ty0, ty1, o0, end)) in enumerate(zip(SCENES, timing)):
        wc = len(cmd) * cwp
        n = len(cmd)
        if a0 == 0:
            kf += f"@keyframes s{k}{{0%,{pc(end):.3f}%{{opacity:1}}{pc(end) + 0.01:.3f}%,100%{{opacity:0}}}}"
        else:
            kf += (f"@keyframes s{k}{{0%,{pc(a0):.3f}%{{opacity:0}}{pc(a0) + 0.01:.3f}%,{pc(end):.3f}%{{opacity:1}}"
                   f"{pc(end) + 0.01:.3f}%,100%{{opacity:0}}}}")
        kf += (f"@keyframes c{k}{{0%,{pc(ty0):.3f}%{{transform:translateX(0)}}"
               f"{pc(ty1):.3f}%,100%{{transform:translateX({wc:.1f}px)}}}}")
        g = [f'<g style="opacity:0;animation:s{k} {T:.2f}s step-end {D:.2f}s infinite">',
             f'<text x="68" y="{py + 24}" font-size="13.5" fill="{WHITE}">{escape(cmd)}</text>',
             f'<g style="animation:c{k} {T:.2f}s steps({n},end) {D:.2f}s infinite">'
             f'<rect x="68" y="{py + 8}" width="{wc + 14:.1f}" height="26" fill="{BG}"/>'
             f'<rect x="68" y="{py + 12}" width="8.1" height="16" fill="{ORANGE}" class="bl"/></g>']
        for j, ln in enumerate(outs):
            oj = o0 + 0.15 * j
            kf += (f"@keyframes o{k}_{j}{{0%,{pc(oj):.3f}%{{opacity:0;transform:translateY(4px)}}"
                   f"{pc(oj + 0.35):.3f}%,100%{{opacity:1;transform:none}}}}")
            g.append(f'<text x="68" y="{py + 24 + 22 * (j + 1)}" font-size="13.5" fill="{MID}" '
                     f'style="opacity:0;animation:o{k}_{j} {T:.2f}s ease-out {D:.2f}s infinite">{escape(ln)}</text>')
        g.append("</g>")
        scenes.append("".join(g))
    body.append(f'<g class="{gname}"><rect x="{fx}" y="{py}" width="{fw}" height="{BOX_H}" rx="6" fill="none" '
                f'stroke="{ORANGE}" stroke-width="1.2" opacity=".7"/>'
                f'<text x="38" y="{py + 24}" font-size="13.5" fill="{ORANGE}">&gt;</text>'
                + "".join(scenes) + "</g>")
    body.append(f'<g class="{add()}"><text x="38" y="{py + BOX_H + 18}" font-size="12" fill="{DIM}">? for shortcuts</text></g>')
    body.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="url(#dots)" pointer-events="none"/>')

    count = len(seq)
    intro = "".join(
        f".a{i}{{animation:in .55s cubic-bezier(.2,.7,.2,1) {0.35 + i * 0.1:.2f}s both}}" for i in range(count))
    pal_css = "".join(f".{k}{{fill:{c}}}" for c, k in palette.items())

    css = (
        font_faces()
        + "text{font-family:JB,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-weight:500;white-space:pre;font-variant-ligatures:none;font-feature-settings:'liga' 0,'calt' 0}"
        + pal_css
        + f".f{{font-size:{FS}px;opacity:0;animation:fr {loop_s:.2f}s step-end infinite}}.f0{{opacity:1}}"
        + f"@keyframes fr{{0%{{opacity:1}}{step + 0.15:.3f}%{{opacity:0}}100%{{opacity:0}}}}"
        + "@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
        + ".pop{animation-name:pop!important}"
        + "@keyframes pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:none}}"
        + ".bar{animation:bar .4s ease-out both}@keyframes bar{from{opacity:0}to{opacity:1}}"
        + ".dr{stroke-dasharray:1;animation:dr .9s cubic-bezier(.65,0,.35,1) .25s both}"
        + "@keyframes dr{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
        + ".bl{animation:bl 1.05s steps(1) infinite}@keyframes bl{50%{opacity:0}}"
        + kf
        + intro
    )

    label = f"Terminal-style banner for {NAME}: " + " ".join(
        f"{h}: {' '.join(ls)}." for h, ls in SECTIONS)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'role="img" aria-label="{escape(label)}"><title>{escape(NAME)}</title>'
           f"<defs>{defs}</defs><style>{css}</style>{''.join(body)}</svg>")
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {OUTPUT} ({len(svg) / 1024:.0f} KB, {len(palette)} colours)")


if __name__ == "__main__":
    build()
