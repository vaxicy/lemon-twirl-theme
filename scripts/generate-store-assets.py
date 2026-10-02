#!/usr/bin/env python3
"""Lemon Twirl Theme - store assets (headless Chromium rendering).

Produces, from a single composer:
  store-assets/screenshots/en/screenshot-1-browser.png   1280x800  window mockup
  store-assets/screenshots/en/screenshot-2-palette.png   1280x800  intro + swatches
  store-assets/promo/440x280.png                         440x280   brand tile
  store-assets/promo/1400x560.png                        1400x560  marquee

Colours come from manifest.json (single source of truth). The browser mockup
geometry is calibrated against a real 1080x647 Chrome screenshot of this theme
(2026-10-02), scaled by 1280/1080 and positioned by its ratio inside the NTP
band - see NTP_METRICS. Includes: inactive tabs painted in background_tab, the
Chrome-derived single-colour wordmark, the real search box size, tan shortcut
circles, and the Customize Chrome pill.

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
    "search_placeholder": "Search Google or type a URL",
}

# ---------------------------------------------------------------- real-browser metrics
# Sampled from the real 1080x647 screenshot; WINDOW scales them to the 1280 wide
# asset, NTP bands are placed by their ratio inside the new-tab area.
WINDOW = 1280 / 1080.0
GOOGLE_LOGO_REAL = "#C1B49B"   # Chrome's computed wordmark colour, sampled
NTP_METRICS = {
    "tabstrip": 32 * WINDOW,        # 38
    "toolbar": 33 * WINDOW,         # 39
    "bookmarkbar": 31 * WINDOW,     # 37
    "wordmark_ink_h": 76,           # ink height 64 * WINDOW
    "wordmark_tracking": -5.2,      # calibrated so the ink width matches 229 px
    "wordmark_center": 0.2292,      # ink centre offset / NTP height
    "search_w": 640,                # 540 * WINDOW
    "search_h": 44,                 # 37 * WINDOW
    "search_top": 0.3406,
    "circle_d": 56,                 # 47 * WINDOW
    "circle_gap": 94,               # 79 * WINDOW
    "circle_top": 0.4511,
    "label_top": 0.5360,
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


def luminance(hx):
    return sum(w * _lin(c) for w, c in zip((0.2126, 0.7152, 0.0722), _rgb(hx)))


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable_on(bg, light="#FFFFFF", dark="#1B220C"):
    return light if contrast(bg, light) >= contrast(bg, dark) else dark


def mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#%02X%02X%02X" % tuple(round(ra[i] + (rb[i] - ra[i]) * t) for i in range(3))


def google_logo_color(ntp_bg):
    """Fallback derivation when no real screenshot is available: Chrome keeps the
    hue/saturation of ntp_background and clamps lightness to ~0.68."""
    r, g, b = (v / 255.0 for v in _rgb(ntp_bg))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(h, min(l, 0.68), s)
    return "#%02X%02X%02X" % (round(r2 * 255), round(g2 * 255), round(b2 * 255))


# ---------------------------------------------------------------- svg bits
ICON = {
    "back": '<path d="M15 5 8 12l7 7" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "forward": '<path d="m9 5 7 7-7 7" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "reload": '<path d="M12 5a7 7 0 1 1-6.6 4.6M12 2v4h4" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "home": '<path d="M4 10.4 10 5l6 5.4V16a1 1 0 0 1-1 1h-3v-4H8v4H5a1 1 0 0 1-1-1Z" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    "star": '<path d="m10 3.6 2 4.1 4.5.65-3.25 3.17.77 4.48L10 14.55 6 16l.77-4.48L3.5 8.35l4.5-.65Z" fill="none" stroke="currentColor" stroke-width="1.4"/>',
    "puzzle": '<path d="M8 4.5a1.5 1.5 0 0 1 3 0V6h2.5a1 1 0 0 1 1 1v2.5h1a1.5 1.5 0 0 1 0 3h-1V15a1 1 0 0 1-1 1H10v-1.5a1.5 1.5 0 0 0-3 0V16H4.5a1 1 0 0 1-1-1v-2.6h1a1.5 1.5 0 0 0 0-3h-1V7a1 1 0 0 1 1-1H8Z" fill="none" stroke="currentColor" stroke-width="1.4"/>',
    "download": '<path d="M10 3v9m0 0 3.4-3.4M10 12 6.6 8.6M4 15.5h12" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    "dots": '<circle cx="4.6" cy="10" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="15.4" cy="10" r="1.5"/>',
    "search": '<circle cx="9" cy="9" r="5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m12.8 12.8 4 4" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "mic": '<rect x="7.6" y="3" width="4.8" height="9" rx="2.4" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M5 9.4a5 5 0 0 0 10 0M10 14.6V17" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    "camera": '<rect x="3" y="5.5" width="14" height="10" rx="2.4" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="10" cy="10.5" r="2.8" fill="none" stroke="currentColor" stroke-width="1.5"/>',
    "grid": '<circle cx="5" cy="5" r="1.4"/><circle cx="10" cy="5" r="1.4"/><circle cx="15" cy="5" r="1.4"/><circle cx="5" cy="10" r="1.4"/><circle cx="10" cy="10" r="1.4"/><circle cx="15" cy="10" r="1.4"/><circle cx="5" cy="15" r="1.4"/><circle cx="10" cy="15" r="1.4"/><circle cx="15" cy="15" r="1.4"/>',
    "close": '<path d="m5 5 6 6m0-6-6 6" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    "plus": '<path d="M8 4v8m-4-4h8" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    "pencil": '<path d="m4.5 13.2-.7 2.9 2.9-.7 7-7a1.6 1.6 0 0 0-2.2-2.2Z" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "win_min": '<path d="M4 10h12" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "win_max": '<rect x="4.5" y="4.5" width="11" height="11" rx="1.4" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "win_close": '<path d="m5 5 10 10m0-10L5 15" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "folder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h3l1.4 1.6h6.6A1.5 1.5 0 0 1 17 8.1v5.4A1.5 1.5 0 0 1 15.5 15h-11A1.5 1.5 0 0 1 3 13.5Z" fill="currentColor" opacity=".75"/>',
    "play_tri": '<path d="M8 6.2 14 10l-6 3.8Z" fill="#FFFFFF"/>',
}


def svg(key, size=16, color="currentColor"):
    return ('<svg viewBox="0 0 20 20" width="%d" height="%d" style="color:%s">%s</svg>'
            % (size, size, color, ICON[key]))


# ---------------------------------------------------------------- browser mockup
def browser_layer(c):
    """Inner markup of the 1280x800 window mockup - reused by the marquee."""
    bm = [("Tools", c["button"]), ("AI", c["tab"]), ("UI", c["frame"]),
          ("G", c["omnibox"]), ("Nav", c["button"]), ("Temp", c["tab"]),
          ("API", c["frame"]), ("Dev", c["omnibox"])]
    bookmarks = "".join(
        '<div class="bm"><span class="bmi" style="background:%s"></span>%s</div>' % (col, name)
        for name, col in bm)
    tabs = "".join(
        '<div class="tab"><span class="tfav" style="background:%s"></span>'
        '<span class="tlabel">%s</span></div>' % (col, name)
        for name, col in (("Design Notes", "#C7D2FE"), ("Recipes", "#F9A8A8"),
                          ("Travel", "#A7D8F0")))
    shortcuts = [
        ("YouTube", '<span class="sc" style="background:#FF0000">%s</span>'
                    % svg("play_tri", 30, "#FFFFFF")),
        ("Web Store",
         '<span class="sc">%s</span>'
         % '<svg viewBox="0 0 20 20" width="26" height="26">'
           '<circle cx="10" cy="10" r="7" fill="#7CD5F0"/>'
           '<path d="M10 6.6 12 12l4.6-1.6z" fill="#F6F6F1" opacity=".9"/></svg>'),
        ("Add shortcut", '<span class="sc">%s</span>' % svg("plus", 26, "#5F5B4C")),
    ]
    shortcut_html = "".join(
        '<div class="scwrap"><span class="scc">%s</span><span class="sclab">%s</span></div>'
        % (art, label) for label, art in shortcuts)

    return f"""
<div class="win">
  <div class="tabstrip">
    <div class="caret">{svg('back', 15, c['tab_sub'])}</div>
    <div class="tab active">
      <span class="tfav" style="background:#FEFBB4"></span>
      <span class="tlabel">New Tab</span>
      <span class="tclose">{svg('close', 12, c['tab_sub'])}</span>
    </div>
    {tabs}
    <div class="newtab">{svg('plus', 14, c['tab_sub'])}</div>
    <div class="wincontrols">
      {svg('win_min', 15, c['tab_sub'])}{svg('win_max', 15, c['tab_sub'])}
      {svg('win_close', 15, c['tab_sub'])}
    </div>
  </div>
  <div class="toolbar">
    <div class="navicons">
      {svg('back', 18, c['icon'])}{svg('forward', 18, c['icon'])}
      {svg('reload', 18, c['icon'])}{svg('home', 18, c['icon'])}
    </div>
    <div class="omnibox">
      <span class="omni-fav">G</span>
      <span class="omni-text">{COPY['search_placeholder']}</span>
      {svg('star', 17, c['icon'])}
    </div>
    <div class="navicons right">
      {svg('camera', 18, c['icon'])}{svg('puzzle', 18, c['icon'])}
      <span class="download">{svg('download', 18, c['icon'])}<i>3</i></span>
      <span class="avatar"></span>
      {svg('dots', 18, c['icon'])}
    </div>
  </div>
  <div class="bookmarkbar">
    <span class="bmfolder">{svg('folder', 16, c['bookmark'])}</span>{bookmarks}
  </div>
  <div class="ntp">
    <div class="ntp-topright">
      <span>Images</span>{svg('grid', 19, '#444746')}
    </div>
    <div class="glogo">Google</div>
    <div class="searchbox">
      <span class="sbicon">{svg('search', 19, '#6B6A66')}</span>
      <span class="sbtext">{COPY['search_placeholder']}</span>
      <span class="sbicons">{svg('mic', 21, '#6B6A66')}{svg('camera', 21, '#6B6A66')}</span>
    </div>
    <div class="shortcuts">{shortcut_html}</div>
    <div class="customize">{svg('pencil', 14, '#FFFFFF')}<span>Customize Chrome</span></div>
  </div>
</div>"""


def base_css(c):
    m = NTP_METRICS
    ntp_h = 800 - (m["tabstrip"] + m["toolbar"] + m["bookmarkbar"])
    return f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"Segoe UI", Arial, sans-serif; -webkit-font-smoothing:antialiased; }}
.win {{ width:1280px; height:800px; overflow:hidden; background:{c['ntp']}; }}

/* tab strip: frame shows as a narrow top edge, inactive tabs use background_tab */
.tabstrip {{ position:relative; height:{m['tabstrip']:.0f}px; background:{c['frame']};
             display:flex; align-items:flex-end; padding:0 132px 0 6px; gap:2px; }}
.caret {{ display:flex; align-items:center; padding:0 6px 9px; }}
.tab {{ height:{m['tabstrip'] - 5:.0f}px; display:flex; align-items:center; gap:8px;
        padding:0 12px; border-radius:9px 9px 0 0; font-size:13px;
        color:{c['tab_sub']}; background:{c['tab']}; min-width:150px; }}
.tab.active {{ width:190px; background:{c['toolbar']}; color:{c['ink']}; }}
.tlabel {{ flex:1; overflow:hidden; white-space:nowrap; }}
.tfav {{ width:14px; height:14px; border-radius:4px; flex:0 0 auto; }}
.tclose {{ display:flex; }}
.newtab {{ display:flex; align-items:center; padding:0 10px 9px; }}
.wincontrols {{ position:absolute; right:8px; top:8px; display:flex; gap:12px;
                align-items:center; }}

.toolbar {{ height:{m['toolbar']:.0f}px; background:{c['toolbar']}; display:flex;
            align-items:center; padding:0 12px; gap:10px; }}
.navicons {{ display:flex; align-items:center; gap:8px; }}
.navicons.right {{ gap:13px; margin-left:auto; }}
.omnibox {{ flex:1; max-width:700px; height:31px; margin:0 auto; background:{c['omnibox']};
            border:1px solid rgba(120,140,175,.55); border-radius:16px; display:flex;
            align-items:center; gap:10px; padding:0 12px; }}
.omni-fav {{ font:700 13px/1 Arial, sans-serif; color:#4285F4; }}
.omni-text {{ flex:1; font-size:13.5px; color:{c['omnibox_text']}; opacity:.85; }}
.download {{ position:relative; display:flex; }}
.download i {{ position:absolute; right:-6px; bottom:-3px; font:700 9px/14px Arial;
               font-style:normal; color:#FFFFFF; background:#D93025; border-radius:7px;
               padding:0 4px; }}
.avatar {{ width:23px; height:23px; border-radius:50%; background:#7C4DFF; color:#FFFFFF;
           font:600 12px/23px Arial; text-align:center; display:inline-block; }}

.bookmarkbar {{ height:{m['bookmarkbar']:.0f}px; background:{c['toolbar']};
                display:flex; align-items:center; gap:20px; padding:0 14px;
                border-top:1px solid rgba(0,0,0,.07); }}
.bmfolder {{ display:flex; }}
.bm {{ display:flex; align-items:center; gap:7px; font-size:12px; color:{c['bookmark']}; }}
.bmi {{ width:14px; height:14px; border-radius:4px; border:1px solid rgba(0,0,0,.10); }}

/* new tab page - element positions sampled from the real screenshot */
.ntp {{ position:relative; height:{ntp_h:.0f}px; background:{c['ntp']}; }}
.ntp-topright {{ position:absolute; right:21px; top:21px; display:flex; align-items:center;
                 gap:14px; font-size:15px; color:#444746; }}
/* Chrome derives this single-colour wordmark from ntp_background; it is not a
   theme-controlled value (chrome-theme-google-logo-color), sampled as
   {GOOGLE_LOGO_REAL} on a real install. */
.glogo {{ position:absolute; left:0; right:0; top:{m['wordmark_center'] * ntp_h - 6:.0f}px;
          transform:translateY(-50%); text-align:center; font-family:Arial, Helvetica,
          sans-serif; font-size:{m['wordmark_ink_h'] / 0.928:.0f}px;
          letter-spacing:{m['wordmark_tracking']}px; line-height:1; color:{GOOGLE_LOGO_REAL}; }}
.searchbox {{ position:absolute; top:{m['search_top'] * ntp_h:.0f}px; left:50%;
              transform:translateX(-50%); width:{m['search_w']:.0f}px;
              height:{m['search_h']:.0f}px; border-radius:{m['search_h'] / 2:.0f}px;
              background:linear-gradient(180deg,#FFFFFF 0%,#FFFFFF 62%,#EFEEED 100%);
              box-shadow:0 1px 3px rgba(0,0,0,.10); display:flex; align-items:center;
              gap:14px; padding:0 18px; }}
.sbicon, .sbicons {{ display:flex; }}
.sbicons {{ margin-left:auto; gap:16px; }}
.sbtext {{ font-size:16px; color:#6B6A66; }}
.shortcuts {{ position:absolute; top:{m['circle_top'] * ntp_h:.0f}px; left:0; right:0;
              display:flex; justify-content:center; }}
/* fixed slot width keeps the circle centres {m['circle_gap']:.0f}px apart, as on screen */
.scwrap {{ width:{m['circle_gap']:.0f}px; display:flex; flex-direction:column;
           align-items:center; }}
.sc {{ width:{m['circle_d']:.0f}px; height:{m['circle_d']:.0f}px; border-radius:50%;
       background:#D4CABA; display:flex; align-items:center; justify-content:center; }}
.sclab {{ margin-top:2px; font-size:13px; line-height:1.15; color:#6E6A5E; }}
.customize {{ position:absolute; right:12px; bottom:9px; height:31px; border-radius:16px;
              background:#202124; color:#FFFFFF; display:flex; align-items:center; gap:9px;
              padding:0 15px 0 13px; font-size:13px; }}
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
    # deeper canvas so no swatch can melt into the page (cream on off-white was
    # invisible before); derived from the palette, not a second colour table
    page_bg = mix(c["toolbar"], c["ink"], 0.17)
    ink = c["ink"]
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1280px; height:800px; background:{page_bg};
        font-family:"Segoe UI", Arial, sans-serif; color:{ink};
        display:flex; flex-direction:column; align-items:center; padding-top:60px; }}
.kicker {{ font-size:14px; letter-spacing:3px; color:{mix(c['link'], c['ink'], 0.60)};
           white-space:pre; }}
.title {{ font-family:Georgia, "Times New Roman", serif; font-size:58px;
          margin-top:14px; color:#241E10; }}
.tagline {{ font-size:19px; margin-top:14px; color:{mix(c['ink'], '#FFFFFF', 0.16)}; }}
.grid {{ display:grid; grid-template-columns:520px 520px; gap:30px; margin-top:42px; }}
.card {{ height:186px; border-radius:16px; padding:26px 30px;
         box-shadow:0 4px 14px rgba(43,35,17,.22); border:1px solid rgba(43,35,17,.10);
         display:flex; flex-direction:column; justify-content:center; gap:10px; }}
.cname {{ font-size:25px; font-weight:600; }}
.chex {{ font-size:14px; opacity:.78; }}
.chips {{ display:flex; gap:14px; margin-top:34px; }}
.chip {{ background:{c['frame']}; color:{ink}; font-size:13.5px;
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
/* padding-top, not margin-top on the first child: a collapsed margin would shift
   the whole canvas down and push the accent bar off the top edge */
body {{ width:440px; height:280px; background:{c['frame']}; overflow:hidden;
        font-family:"Segoe UI", Arial, sans-serif; color:{c['ink']};
        display:flex; flex-direction:column; align-items:center; position:relative;
        padding-top:30px; }}
.bar {{ position:absolute; left:0; bottom:0; width:440px; height:14px;
        background:{c['link']}; }}
.card {{ width:112px; height:112px; border-radius:26px; background:#FFFFFF;
         display:flex; align-items:center; justify-content:center;
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
/* padding-top instead of a margin on the title: the collapsed margin used to
   push the canvas down 44px and leave the accent bar floating mid-canvas */
body {{ width:1400px; height:560px; background:{c['ntp']}; overflow:hidden;
        position:relative; text-align:center; padding-top:44px; }}
.accent {{ position:absolute; top:0; left:0; width:1400px; height:8px;
           background:{c['link']}; }}
.title {{ font-family:Georgia, "Times New Roman", serif; font-size:46px;
          color:{c['ink']}; }}
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
    """out_png is project-relative: Playwright gets short ASCII-ish paths too."""
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(html, wait_until="load")
    page.wait_for_timeout(120)
    page.screenshot(path=os.path.relpath(out_png, ROOT))
    return out_png


def to_rgb(src, dst, size):
    """PIL gets project-relative paths: absolute paths with non-ASCII characters
    make Image.save() fail intermittently with OSError 22 on Windows."""
    rel_src, rel_dst = os.path.relpath(src, ROOT), os.path.relpath(dst, ROOT)
    img = Image.open(rel_src).convert("RGB")
    assert img.size == size, "%s is %s, expected %s" % (rel_src, img.size, size)
    img.save(rel_dst)
    print("wrote %s  %dx%d" % (rel_dst.replace("\\", "/"), img.size[0], img.size[1]))


def scan_copy():
    blob = json.dumps(COPY) + json.dumps(load_colors())
    hit = BANNED.search(blob)
    assert not hit, "store copy hits a content-policy red line: %r" % hit.group(0)


def main():
    os.chdir(ROOT)          # every write below is project-relative on purpose
    scan_copy()
    for d in (REF_DIR, SHOT_DIR, PROMO_DIR):
        os.makedirs(d, exist_ok=True)
    c = load_colors()
    print("Google wordmark: %s (sampled) / %s (formula)"
          % (GOOGLE_LOGO_REAL, google_logo_color(c["ntp"])))

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
