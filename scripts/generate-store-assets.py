#!/usr/bin/env python3
"""Lemon Twirl Theme - store assets (headless Chromium rendering).

Produces, from a single composer:
  store-assets/screenshots/en/screenshot-1-browser.png   1280x800  window mockup
  store-assets/screenshots/en/screenshot-2-palette.png   1280x800  intro + swatches
  store-assets/promo/440x280.png                         440x280   brand tile
  store-assets/promo/1400x560.png                        1400x560  marquee

Every colour is read from manifest.json (single source of truth); the Google
logo colour is the one Chrome derives for this ntp_background (see
chrome-theme-google-logo-color rule). Intermediate HTML/PNG live in
store-assets/references/.

Run:  python3 scripts/generate-store-assets.py
"""

import base64
import colorsys
import json
import os
import re
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "manifest.json")
REF_DIR = os.path.join(ROOT, "store-assets", "references")
SHOT_DIR = os.path.join(ROOT, "store-assets", "screenshots", "en")
PROMO_DIR = os.path.join(ROOT, "store-assets", "promo")
LOGO = os.path.join(ROOT, "logo", "logo.png")

COPY = {
    "name": "Lemon Twirl",
    "kicker": "S Q U E E Z E  O F  S U N S H I N E",
    "tagline": "Pale lemon light with a twist of green.",
    "chips": ["Solid colors", "Playful & bright", "Lemon fresh"],
    "promo_sub": "A playful twist for your new tab.",
    "promo_eyebrow": "C H R O M E  T H E M E",
}

# Chrome Store content-policy red lines - scanned before anything is written.
BANNED = re.compile(
    r"(?i)\b(free|forever|no ads|no subscriptions?|paywall|pro plan|free trial"
    r"|add to chrome|best|official|recommended)\b"
    r"|\u514d\u8d39|\u65e0\u5e7f\u544a|\u6dfb\u52a0\u5230\s*Chrome"
    r"|\bif you (like|love|prefer)\b|\b(your|make) chrome\b|\bchrome feel\b")


# ---------------------------------------------------------------- palette
def load_colors():
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        c = json.load(fh)["theme"]["colors"]

    def hx(name):
        return "#%02X%02X%02X" % tuple(c[name])

    return {
        "frame": hx("frame"),
        "frame_inactive": hx("frame_inactive"),
        "toolbar": hx("toolbar"),
        "tab": hx("background_tab"),
        "ink": hx("tab_text"),
        "tab_sub": hx("tab_background_text"),
        "icon": hx("toolbar_button_icon"),
        "button": hx("button_background"),
        "omnibox": hx("omnibox_background"),
        "omnibox_text": hx("omnibox_text"),
        "bookmark": hx("bookmark_text"),
        "ntp": hx("ntp_background"),
        "ntp_text": hx("ntp_text"),
        "link": hx("ntp_link"),
    }


def _rgb(hx):
    hx = hx.lstrip("#")
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def _lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def contrast(a, b):
    la = sum(w * _lin(c) for w, c in zip((0.2126, 0.7152, 0.0722), _rgb(a)))
    lb = sum(w * _lin(c) for w, c in zip((0.2126, 0.7152, 0.0722), _rgb(b)))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable_on(bg, light="#FFFFFF", dark="#1B220C"):
    return light if contrast(bg, light) >= contrast(bg, dark) else dark


def google_logo_color(ntp_bg):
    """Chrome keeps the hue/saturation of ntp_background and clamps lightness
    to about 0.665 when ntp_logo_alternate is on, so a near-neutral pale NTP
    yields a warm grey wordmark."""
    r, g, b = (v / 255.0 for v in _rgb(ntp_bg))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(h, min(l, 0.665), s)
    return "#%02X%02X%02X" % (round(r2 * 255), round(g2 * 255), round(b2 * 255))


# ---------------------------------------------------------------- svg bits
ICON = {
    "back": '<path d="M15 5 8 12l7 7" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "forward": '<path d="m9 5 7 7-7 7" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "reload": '<path d="M12 5a7 7 0 1 1-6.6 4.6M12 2v4h4" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "lock": '<rect x="5" y="10" width="9" height="7" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M7.2 10V8.2a2.3 2.3 0 0 1 4.6 0V10" fill="none" stroke="currentColor" stroke-width="1.4"/>',
    "star": '<path d="m10 3.6 2 4.1 4.5.65-3.25 3.17.77 4.48L10 14.55 6 16l.77-4.48L3.5 8.35l4.5-.65Z" fill="none" stroke="currentColor" stroke-width="1.4"/>',
    "puzzle": '<path d="M8 4.5a1.5 1.5 0 0 1 3 0V6h2.5a1 1 0 0 1 1 1v2.5h1a1.5 1.5 0 0 1 0 3h-1V15a1 1 0 0 1-1 1H10v-1.5a1.5 1.5 0 0 0-3 0V16H4.5a1 1 0 0 1-1-1v-2.6h1a1.5 1.5 0 0 0 0-3h-1V7a1 1 0 0 1 1-1H8Z" fill="none" stroke="currentColor" stroke-width="1.4"/>',
    "dots": '<circle cx="6" cy="10" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="14" cy="10" r="1.5"/>',
    "search": '<circle cx="9" cy="9" r="5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m12.8 12.8 4 4" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "globe": '<circle cx="10" cy="10" r="6.4" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M3.6 10h12.8M10 3.6c1.9 2 1.9 10.8 0 12.8-1.9-2-1.9-10.8 0-12.8Z" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    "play": '<path d="M7.5 5.5 15 10l-7.5 4.5Z" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    "pin": '<path d="M10 17s5.2-5.1 5.2-8.4a5.2 5.2 0 1 0-10.4 0C4.8 11.9 10 17 10 17Z" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="10" cy="8.6" r="1.7" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    "note": '<path d="M8 15V5.6l7-1.3V14" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="6.2" cy="15" r="1.9" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="13.2" cy="14" r="1.9" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    "close": '<path d="m5 5 6 6m0-6-6 6" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    "plus": '<path d="M8 4v8m-4-4h8" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    "pencil": '<path d="m4.5 13.2-.7 2.9 2.9-.7 7-7a1.6 1.6 0 0 0-2.2-2.2Z" fill="none" stroke="currentColor" stroke-width="1.3"/>',
}


def svg(key, size=16, color="currentColor", width=None):
    return ('<svg viewBox="0 0 20 20" width="%d" height="%d" style="color:%s;%s">%s</svg>'
            % (size, size, color, ("width:%dpx;height:%dpx;" % (width, width)) if width else "",
               ICON[key]))


# ---------------------------------------------------------------- browser mockup
def browser_layer(c):
    """Inner markup of the window mockup (1280x800) - reused by the marquee."""
    bm = [("Design", c["button"]), ("Recipes", c["tab"]),
          ("Travel", c["frame"]), ("Reading", c["omnibox"])]
    bookmarks = "".join(
        '<div class="bm"><span class="bmi" style="background:%s"></span>%s</div>' % (col, name)
        for name, col in bm)
    tabs = "".join(
        '<div class="tab"><span class="tfav"></span><span class="tlabel">%s</span></div>' % name
        for name in ("Design Notes", "Recipes", "Travel"))
    shortcuts = "".join(
        '<div class="sc"><span class="scc">%s</span></div>'
        % svg(k, 20, "#5F6368") for k in ("globe", "play", "pin", "note"))

    return f"""
<div class="win">
  <div class="tabstrip">
    <div class="tab active">
      <span class="tfav"></span><span class="tlabel">New Tab</span>
      <span class="tclose">{svg('close', 12, c['tab_sub'])}</span>
    </div>
    {tabs}
    <div class="newtab">{svg('plus', 14, c['tab_sub'])}</div>
  </div>
  <div class="toolbar">
    <div class="navicons">
      {svg('back', 18, c['icon'])}{svg('forward', 18, c['icon'])}{svg('reload', 18, c['icon'])}
    </div>
    <div class="omnibox">
      {svg('lock', 14, '#8A8574')}
      <span class="omni-text">Search Google or type a URL</span>
      {svg('star', 17, c['icon'])}
    </div>
    <div class="navicons right">
      {svg('puzzle', 18, c['icon'])}
      <span class="avatar"></span>
      {svg('dots', 18, c['icon'])}
    </div>
  </div>
  <div class="bookmarkbar">{bookmarks}</div>
  <div class="ntp">
    <div class="ntp-center">
      <div class="glogo">Google</div>
      <div class="searchbox">
        <span class="sbicon">{svg('search', 19, '#5F6368')}</span>
        <span class="sbtext">Search Google or type a URL</span>
      </div>
      <div class="shortcuts">{shortcuts}</div>
    </div>
    <div class="customize">{svg('pencil', 14, '#FFFFFF')}<span>Customize Chrome</span></div>
  </div>
</div>"""


def base_css(c):
    return f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"Segoe UI", Arial, sans-serif; -webkit-font-smoothing:antialiased; }}
.win {{ width:1280px; height:800px; overflow:hidden; background:{c['ntp']}; }}

.tabstrip {{ height:42px; background:{c['frame']}; display:flex; align-items:flex-end;
             padding:0 8px; gap:4px; }}
.tab {{ height:34px; display:flex; align-items:center; gap:8px; padding:0 12px;
        border-radius:9px 9px 0 0; font-size:12.5px; color:{c['tab_sub']}; }}
.tab.active {{ height:34px; width:232px; background:{c['toolbar']}; color:{c['ink']};
               border-radius:9px 9px 0 0; box-shadow:0 -1px 2px rgba(0,0,0,.05); }}
.tlabel {{ flex:1; overflow:hidden; white-space:nowrap; }}
.tfav {{ width:14px; height:14px; border-radius:4px; background:{c['button']};
         flex:0 0 auto; }}
.tclose {{ display:flex; }}
.newtab {{ display:flex; align-items:center; padding:0 10px 9px; }}

.toolbar {{ height:40px; background:{c['toolbar']}; display:flex; align-items:center;
            padding:0 12px; gap:10px; }}
.navicons {{ display:flex; align-items:center; gap:6px; }}
.navicons.right {{ gap:12px; margin-left:auto; }}
.omnibox {{ flex:1; max-width:760px; height:30px; margin:0 auto; background:{c['omnibox']};
            border:1px solid rgba(0,0,0,.09); border-radius:15px; display:flex;
            align-items:center; gap:9px; padding:0 12px; }}
.omni-text {{ flex:1; font-size:13px; color:{c['omnibox_text']}; opacity:.82; }}
.avatar {{ width:22px; height:22px; border-radius:50%; background:{c['link']};
           opacity:.85; display:inline-block; }}

.bookmarkbar {{ height:34px; background:{c['toolbar']}; display:flex; align-items:center;
                gap:22px; padding:0 14px; }}
.bm {{ display:flex; align-items:center; gap:7px; font-size:12px; color:{c['bookmark']}; }}
.bmi {{ width:14px; height:14px; border-radius:4px; border:1px solid rgba(0,0,0,.10); }}

.ntp {{ position:relative; height:684px; background:{c['ntp']}; display:flex;
        align-items:center; justify-content:center; }}
.ntp-center {{ display:flex; flex-direction:column; align-items:center;
               margin-top:-26px; }}
/* Chrome derives this single-colour wordmark from ntp_background; it is not a
   theme-controlled value (chrome-theme-google-logo-color). */
.glogo {{ font-family:Arial, Helvetica, sans-serif; font-size:74px; letter-spacing:-3.2px;
          color:{google_logo_color(c['ntp'])}; margin-bottom:30px; }}
.searchbox {{ width:566px; height:46px; background:#FFFFFF; border-radius:23px;
              border:1px solid rgba(0,0,0,.10); box-shadow:0 1px 4px rgba(0,0,0,.06);
              display:flex; align-items:center; gap:14px; padding:0 20px; }}
.sbicon {{ display:flex; }}
.sbtext {{ font-size:15px; color:#5F6368; }}
.shortcuts {{ display:flex; gap:26px; margin-top:44px; }}
.sc {{ width:48px; height:48px; border-radius:50%; background:#FFFFFF;
       border:1px solid rgba(0,0,0,.07); display:flex; align-items:center;
       justify-content:center; }}
.scc {{ display:flex; }}
.customize {{ position:absolute; right:24px; bottom:22px; height:32px; border-radius:16px;
              background:#202124; color:#FFFFFF; display:flex; align-items:center; gap:9px;
              padding:0 15px 0 13px; font-size:12.5px; }}
"""


def html_browser(c):
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<style>%s</style></head><body>%s</body></html>"
            % (base_css(c), browser_layer(c)))


# ---------------------------------------------------------------- intro card
def html_intro(c):
    cards = [
        ("Lemon Zest", c["frame"], "Browser frame"),
        ("Cream Glass", c["toolbar"], "Toolbar & active tab"),
        ("Lemon Zing", c["tab"], "Inactive tabs"),
        ("Leaf Green", c["link"], "Links & accents"),
    ]
    card_html = ""
    for name, col, use in cards:
        tcol = readable_on(col)
        card_html += (f'<div class="card" style="background:{col}">'
                      f'<div class="cname" style="color:{tcol}">{name}</div>'
                      f'<div class="chex" style="color:{tcol}">{col} &middot; {use}</div>'
                      f'</div>')
    chips = "".join('<span class="chip">%s</span>' % t for t in COPY["chips"])
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1280px; height:800px; background:{c['ntp']};
        font-family:"Segoe UI", Arial, sans-serif; color:{c['ntp_text']};
        display:flex; flex-direction:column; align-items:center; padding-top:66px; }}
.kicker {{ font-size:14px; letter-spacing:3px; color:{c['link']}; white-space:pre; }}
.title {{ font-family:Georgia, "Times New Roman", serif; font-size:58px;
          margin-top:14px; color:{c['ink']}; }}
.tagline {{ font-size:19px; margin-top:14px; color:{c['bookmark']}; }}
.grid {{ display:grid; grid-template-columns:520px 520px; gap:30px; margin-top:44px; }}
.card {{ height:186px; border-radius:16px; padding:26px 30px;
         box-shadow:0 2px 8px rgba(0,0,0,.06); display:flex; flex-direction:column;
         justify-content:center; gap:10px; }}
.cname {{ font-size:25px; font-weight:600; }}
.chex {{ font-size:14px; opacity:.78; }}
.chips {{ display:flex; gap:14px; margin-top:38px; }}
.chip {{ background:{c['button']}; color:{c['ink']}; font-size:13.5px;
         padding:9px 18px; border-radius:16px; }}
</style></head><body>
<div class="kicker">{COPY['kicker']}</div>
<div class="title">{COPY['name']}</div>
<div class="tagline">{COPY['tagline']}</div>
<div class="grid">{card_html}</div>
<div class="chips">{chips}</div>
</body></html>"""


# ---------------------------------------------------------------- promo tiles
def html_promo_small(c):
    with open(LOGO, "rb") as fh:
        data = base64.b64encode(fh.read()).decode()
    eyebrow = COPY["promo_eyebrow"]
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:440px; height:280px; background:{c['frame']}; overflow:hidden;
        font-family:"Segoe UI", Arial, sans-serif; color:{c['ink']};
        display:flex; flex-direction:column; align-items:center; position:relative; }}
.bar {{ position:absolute; left:0; bottom:0; width:440px; height:14px;
        background:{c['link']}; }}
.card {{ width:112px; height:112px; border-radius:26px; background:#FFFFFF;
         margin-top:30px; display:flex; align-items:center; justify-content:center;
         box-shadow:0 4px 12px rgba(0,0,0,.10); }}
.card img {{ width:88px; height:88px; }}
.name {{ font-family:Georgia, "Times New Roman", serif; font-size:33px; margin-top:16px; }}
.eyebrow {{ font-size:10.5px; letter-spacing:2.4px; color:{c['bookmark']}; margin-top:8px;
            white-space:pre; }}
.sub {{ font-size:13px; color:{c['tab_sub']}; margin-top:9px; }}
</style></head><body>
<div class="card"><img src="data:image/png;base64,{data}" alt="Lemon Twirl logo"></div>
<div class="name">{COPY['name']}</div>
<div class="eyebrow">{eyebrow}</div>
<div class="sub">{COPY['promo_sub']}</div>
<div class="bar"></div>
</body></html>"""


def html_promo_marquee(c):
    eyebrow = COPY["promo_eyebrow"]
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>
{base_css(c)}
body {{ width:1400px; height:560px; background:{c['ntp']}; overflow:hidden;
        position:relative; text-align:center; }}
.accent {{ position:absolute; top:0; left:0; width:1400px; height:8px;
           background:{c['link']}; }}
.title {{ font-family:Georgia, "Times New Roman", serif; font-size:46px;
          color:{c['ink']}; margin-top:44px; }}
.eyebrow {{ font-size:11.5px; letter-spacing:3px; color:{c['link']}; margin-top:10px;
            white-space:pre; }}
.sub {{ font-size:17px; color:{c['bookmark']}; margin-top:12px; }}
.stage {{ position:absolute; left:50%; top:156px; transform:translateX(-50%);
          width:794px; height:366px; border-radius:14px; overflow:hidden;
          border:1px solid rgba(0,0,0,.10); box-shadow:0 8px 26px rgba(0,0,0,.10);
          background:{c['ntp']}; }}
.inner {{ transform:scale(0.62); transform-origin:top left; }}
</style></head><body>
<div class="accent"></div>
<div class="title">{COPY['name']}</div>
<div class="eyebrow">{eyebrow}</div>
<div class="sub">{COPY['tagline']}</div>
<div class="stage"><div class="inner">{browser_layer(c)}</div></div>
</body></html>"""


# ---------------------------------------------------------------- rendering
def render(page, html, out_png, w, h):
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(html, wait_until="load")
    page.wait_for_timeout(120)
    page.screenshot(path=out_png)
    return out_png


def to_rgb(src, dst, size):
    img = Image.open(src).convert("RGB")
    assert img.size == size, "%s is %s, expected %s" % (src, img.size, size)
    img.save(dst)
    print("wrote %s  %dx%d" % (os.path.relpath(dst, ROOT).replace("\\", "/"),
                               img.size[0], img.size[1]))


def scan_copy():
    blob = json.dumps(COPY) + json.dumps(load_colors())
    hit = BANNED.search(blob)
    assert not hit, "store copy hits a content-policy red line: %r" % hit.group(0)


def main():
    scan_copy()
    for d in (REF_DIR, SHOT_DIR, PROMO_DIR):
        os.makedirs(d, exist_ok=True)
    c = load_colors()

    pages = [
        ("screenshot-1-browser", html_browser(c), (1280, 800), SHOT_DIR),
        ("screenshot-2-palette", html_intro(c), (1280, 800), SHOT_DIR),
        ("promo-440x280", html_promo_small(c), (440, 280), PROMO_DIR),
        ("promo-1400x560", html_promo_marquee(c), (1400, 560), PROMO_DIR),
    ]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(device_scale_factor=1)
        for name, html, size, out_dir in pages:
            ref_html = os.path.join(REF_DIR, name + ".html")
            with open(ref_html, "w", encoding="utf-8") as fh:
                fh.write(html)
            ref_png = os.path.join(REF_DIR, name + ".png")
            render(page, html, ref_png, *size)
            final = ("440x280.png" if name == "promo-440x280" else
                     "1400x560.png" if name == "promo-1400x560" else name + ".png")
            to_rgb(ref_png, os.path.join(out_dir, final), size)
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
