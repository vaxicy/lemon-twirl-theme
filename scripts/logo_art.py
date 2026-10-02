#!/usr/bin/env python3
"""Lemon Twirl Theme - logo artwork (code-drawn, PIL).

Shared art module: palette read from manifest.json + four candidate marks.
Entry points that use it:

  scripts/generate-logo.py          -> logo/logo.png (the chosen design)
  scripts/generate-logo.py --options -> all four candidates + contact sheet

Every colour comes from manifest.json, never from a second hard-coded table.
"""

import json
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "manifest.json")
OUT_DIR = os.path.join(ROOT, "store-assets", "icon-options")
SIZE = 128
SS = 4  # supersampling


# ---------------------------------------------------------------- palette
def load_palette():
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        c = json.load(fh)["theme"]["colors"]
    return {
        "frame": tuple(c["frame"]),          # pale lemon
        "toolbar": tuple(c["toolbar"]),      # cream white
        "tab": tuple(c["background_tab"]),   # muted lemon
        "ink": tuple(c["tab_text"]),         # deep brown
        "leaf": tuple(c["ntp_link"]),        # lemon green
        "rim": (243, 200, 46),               # rind / peel
    }


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def tint(c, toward, t):
    return lerp(c, toward, t)


# ---------------------------------------------------------------- geometry
def leaf_polygon(x, y, length, width, angle_deg, n=48):
    """Pointed-oval leaf, tip at (x, y), growing along angle_deg."""
    a = math.radians(angle_deg)
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    pts = []
    for i in range(n + 1):          # one side out
        t = i / n
        w = (width / 2.0) * math.sin(math.pi * t) ** 0.85
        pts.append((x + ux * length * t + px * w, y + uy * length * t + py * w))
    for i in range(n, -1, -1):      # other side back
        t = i / n
        w = (width / 2.0) * math.sin(math.pi * t) ** 0.85
        pts.append((x + ux * length * t - px * w, y + uy * length * t - py * w))
    return pts


def lemon_polygon(cx, cy, a, b, angle_deg, n=120):
    """Lemon: half-width a*(1-t^2)^0.75 gives pointed tips at t = +-1."""
    th = math.radians(angle_deg)
    wx, wy = math.cos(th), math.sin(th)         # width axis
    lx_, ly_ = math.sin(th), -math.cos(th)      # length axis (tip to tip)
    right, left = [], []
    for i in range(n + 1):
        t = -1.0 + 2.0 * i / n
        w = a * max(0.0, 1.0 - t * t) ** 0.75
        ox, oy = w, b * t
        right.append((cx + wx * ox + lx_ * oy, cy + wy * ox + ly_ * oy))
        left.append((cx - wx * ox + lx_ * oy, cy - wy * ox + ly_ * oy))
    return right + left[::-1]


def spiral_pts(cx, cy, r0, r1, a0, turns, n=240, squash=1.0):
    pts = []
    total = turns * 2 * math.pi
    for i in range(n + 1):
        t = i / n
        a = a0 + total * t
        r = r0 + (r1 - r0) * t
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a) * squash, t))
    return pts


def ribbon_polygon(pts, w_start, w_end):
    n = len(pts)
    left, right = [], []
    for i, (x, y, t) in enumerate(pts):
        j, k = min(i + 1, n - 1), max(i - 1, 0)
        dx, dy = pts[j][0] - pts[k][0], pts[j][1] - pts[k][1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        w = (w_start + (w_end - w_start) * t) / 2.0
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def new_layer():
    img = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def with_shadow(base, dx=0, dy=7, blur=9, alpha=62):
    """Composite a soft drop shadow *under* the solid shape layer."""
    S = SIZE * SS
    a = base.getchannel("A")
    sh = Image.new("RGBA", (S, S), (57, 47, 30, 0))
    sh.putalpha(a.point(lambda v: int(v * alpha / 255)))
    sh = sh.filter(ImageFilter.GaussianBlur(blur * SS / 4))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.alpha_composite(sh, (dx * SS, dy * SS))
    out.alpha_composite(base)
    return out


def add_gloss(img, boxes, alpha=120, blur=1.6):
    """White soft highlights, drawn last so they never feed the shadow."""
    S = SIZE * SS
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    for b in boxes:
        hd.ellipse(b, fill=(255, 255, 255, alpha))
    hl = hl.filter(ImageFilter.GaussianBlur(blur * SS))
    img.alpha_composite(hl)
    return img


# ---------------------------------------------------------------- options
def option_slice(p):
    """1-slice: lemon cross-section wheel."""
    img, d = new_layer()
    S = SIZE * SS
    cx, cy = S / 2, S * 0.52
    r_out = S * 0.415
    r_pith = S * 0.325
    r_core = S * 0.052

    d.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], fill=p["rim"] + (255,))
    d.ellipse([cx - r_pith, cy - r_pith, cx + r_pith, cy + r_pith], fill=(253, 253, 243, 255))

    n_seg = 8
    flesh_a = tint(p["frame"], (255, 255, 255), 0.35)
    flesh_b = tint(p["frame"], p["rim"], 0.30)
    for i in range(n_seg):
        a0 = i * 2 * math.pi / n_seg + 0.085
        a1 = (i + 1) * 2 * math.pi / n_seg - 0.085
        pts = [(cx, cy)]
        for s in range(25):
            a = a0 + (a1 - a0) * s / 24
            r = r_pith - S * 0.022
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        d.polygon(pts, fill=(flesh_a if i % 2 == 0 else flesh_b) + (255,))

    d.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=(253, 253, 243, 255))

    d.polygon(leaf_polygon(cx + S * 0.235, cy - S * 0.255, S * 0.20, S * 0.105, -34),
              fill=p["leaf"] + (255,))
    d.line([(cx + S * 0.30, cy - S * 0.40), (cx + S * 0.40, cy - S * 0.47)],
           fill=tint(p["leaf"], p["ink"], 0.35) + (255,), width=int(2.2 * SS))

    # no gloss highlight on the slice: the blurred white oval read as a bubble
    return with_shadow(img, dy=5, blur=7, alpha=58)


def option_drop(p):
    """2-drop: glossy gummy lemon, tilted, with a leaf."""
    S = SIZE * SS
    img, d = new_layer()
    cx, cy = S / 2, S * 0.555
    angle = 16.0
    a, b = S * 0.285, S * 0.375

    body = tint(p["frame"], p["rim"], 0.20)
    deep = tint(body, p["rim"], 0.42)

    # build the lemon upright on its own layer, then tilt it as a whole
    box = int(2 * b + S * 0.25)
    lh = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lh)
    ox = oy = box / 2
    ld.polygon(lemon_polygon(ox, oy, a, b, 0), fill=body + (255,))

    for k in (-0.56, -0.19, 0.19, 0.56):
        ld.line([(ox + k * a * 0.36, oy - b * 0.28),
                 (ox + k * a * 0.94, oy + b * 0.34)],
                fill=(253, 253, 243, 205), width=int(2.8 * SS))

    sh = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon(
        lemon_polygon(ox, oy + b * 0.18, a * 0.70, b * 0.60, 0), fill=deep + (255,))
    mask = Image.new("L", (box, box), 0)
    ImageDraw.Draw(mask).polygon(lemon_polygon(ox, oy, a, b, 0), fill=255)
    sh.putalpha(ImageChops.multiply(sh.getchannel("A"), mask))
    lh.alpha_composite(sh)

    lh = lh.rotate(angle, resample=Image.BICUBIC)
    img.paste(lh, (int(cx - ox), int(cy - oy)), lh)

    th = math.radians(angle)
    tipx, tipy = cx - b * math.sin(th), cy - b * math.cos(th)
    d.polygon(leaf_polygon(tipx + S * 0.015, tipy - S * 0.035, S * 0.215, S * 0.105, -18),
              fill=p["leaf"] + (255,))
    d.line([(tipx, tipy - S * 0.02), (tipx + S * 0.155, tipy - S * 0.125)],
           fill=tint(p["leaf"], p["ink"], 0.35) + (255,), width=int(2.2 * SS))

    img = with_shadow(img, dy=7, blur=9, alpha=60)
    return add_gloss(img, [(cx - S * 0.190, cy - S * 0.235,
                            cx - S * 0.055, cy - S * 0.075)], alpha=115, blur=2.2)


def option_twist(p):
    """3-twist: two-tone soft-serve swirl."""
    img, d = new_layer()
    S = SIZE * SS
    cx, cy = S / 2, S * 0.525

    yellow = tint(p["frame"], p["rim"], 0.55)
    white = (253, 252, 240)

    # silhouette outline keeps the swirl readable when scaled down
    base = spiral_pts(cx, cy, S * 0.415, S * 0.045, -1.35, 1.52, n=300, squash=0.97)
    d.polygon(ribbon_polygon(base, S * 0.196, S * 0.135),
              fill=tint(p["rim"], p["ink"], 0.10) + (255,))

    for off, col in ((0.0, yellow), (math.pi, white)):
        pts = spiral_pts(cx, cy, S * 0.415, S * 0.045, -1.35 + off, 1.52,
                         n=300, squash=0.97)
        d.polygon(ribbon_polygon(pts, S * 0.170, S * 0.110), fill=col + (255,))

    # crown tip: short ribbon rising out of the centre
    tip = spiral_pts(cx, cy, S * 0.075, S * 0.012, 8.6, 0.55, n=80, squash=0.97)
    d.polygon(ribbon_polygon(tip, S * 0.105, S * 0.055),
              fill=tint(yellow, p["rim"], 0.30) + (255,))

    # leaf tucked at the lower right of the swirl
    d.polygon(leaf_polygon(cx + S * 0.185, cy + S * 0.325, S * 0.20, S * 0.10, -148),
              fill=p["leaf"] + (255,))

    img = with_shadow(img, dy=7, blur=9, alpha=58)
    return add_gloss(img, [(cx - S * 0.175, cy - S * 0.055,
                            cx - S * 0.075, cy + S * 0.045)], alpha=70, blur=3.0)


def option_zest(p):
    """4-zest: single peel curl with a leaf."""
    img, d = new_layer()
    S = SIZE * SS
    cx, cy = S * 0.45, S * 0.55

    peel = tint(p["frame"], p["rim"], 0.40)
    pith = (253, 252, 240)

    # one continuous ribbon: straight tail (outside) -> curl (inside), no seam
    sp = spiral_pts(cx, cy, S * 0.375, S * 0.080, -0.35, 1.30, n=300, squash=1.0)
    dx, dy = sp[0][0] - sp[1][0], sp[0][1] - sp[1][1]
    ln = math.hypot(dx, dy) or 1.0
    dx, dy = dx / ln, dy / ln
    tail = [(sp[0][0] + dx * S * 0.165 * k, sp[0][1] + dy * S * 0.165 * k, 0.0)
            for k in (1.0, 0.62, 0.28)]
    pts = tail + sp
    w_out, w_in = S * 0.160, S * 0.070
    d.polygon(ribbon_polygon(pts, w_out, w_in), fill=peel + (255,))
    d.ellipse([tail[0][0] - w_out / 2, tail[0][1] - w_out / 2,
               tail[0][0] + w_out / 2, tail[0][1] + w_out / 2], fill=peel + (255,))

    # inner pith band follows the curl
    pts2 = spiral_pts(cx, cy, S * 0.315, S * 0.075, -0.35 + 0.66, 1.16, n=280, squash=1.0)
    d.polygon(ribbon_polygon(pts2, S * 0.055, S * 0.042), fill=pith + (255,))

    d.polygon(leaf_polygon(cx + S * 0.045, cy + S * 0.215, S * 0.235, S * 0.115, -150),
              fill=p["leaf"] + (255,))
    d.line([(cx + S * 0.02, cy + S * 0.28), (cx - S * 0.155, cy + S * 0.40)],
           fill=tint(p["leaf"], p["ink"], 0.35) + (255,), width=int(2.2 * SS))

    return with_shadow(img, dy=6, blur=8, alpha=58)


# ---------------------------------------------------------------- output
OPTIONS = {
    "1-slice": option_slice,
    "2-drop": option_drop,
    "3-twist": option_twist,
    "4-zest": option_zest,
}
CHOSEN = "1-slice"      # user picked the lemon cross-section


def render(name=CHOSEN):
    """Return the finished mark as a 128x128 RGBA image."""
    return OPTIONS[name](load_palette()).resize((SIZE, SIZE), Image.LANCZOS)


def write_options(out_dir):
    """Write every candidate plus a contact sheet (exploration only)."""
    os.makedirs(out_dir, exist_ok=True)
    p = load_palette()
    tiles, labels = [], []
    for name, fn in OPTIONS.items():
        raw = fn(p)
        tile = raw.resize((SIZE, SIZE), Image.LANCZOS)
        tile.save(os.path.join(out_dir, "logo-%s.png" % name))
        tiles.append(tile)
        labels.append(name)
        print("wrote store-assets/icon-options/logo-%s.png" % name)
    big = OPTIONS[CHOSEN](p).resize((256, 256), Image.LANCZOS)
    big.save(os.path.join(out_dir, "logo-%s@2x.png" % CHOSEN))
    print("wrote store-assets/icon-options/logo-%s@2x.png" % CHOSEN)

    pad, label_h, cell = 26, 34, SIZE + 26
    sheet = Image.new("RGB", (pad * 2 + cell * 2, pad * 2 + (cell + label_h) * 2),
                      (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, (tile, label) in enumerate(zip(tiles, labels)):
        x = pad + (i % 2) * cell
        y = pad + (i // 2) * (cell + label_h)
        d.rectangle([x, y, x + cell, y + cell], fill=(246, 246, 241))
        sheet.paste(tile, (x + pad // 2, y + pad // 2), tile)
        d.text((x + pad // 2, y + cell + 8), label, fill=(57, 47, 30))
    sheet.save(os.path.join(out_dir, "options-sheet.png"))
    print("wrote store-assets/icon-options/options-sheet.png")
