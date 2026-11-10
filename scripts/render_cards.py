#!/usr/bin/env python3
"""Render the animated, Apple-inspired SVG cards used in the profile README.

Every number comes from the GitHub API at render time (no hard-coded stats),
except the facts stated in the README itself (7+ years, 25+ apps shipped).

Layout: full-width cards are 880 wide (width="100%"). Half cards are 440 wide
(width="50%", two per line, no whitespace between them): 432 of card plus an 8px
transparent gutter on the inner side only, so outer edges line up with the
full-width cards and headings, and the gap between columns is 16px. Grid cards
also carry a bottom gutter so the row gap matches the column gap.

Usage:
    GITHUB_TOKEN=... python3 scripts/render_cards.py
    STATIC=1 python3 scripts/render_cards.py   # final frame only, for screenshots
"""
import json
import os
import urllib.request
from collections import OrderedDict
from datetime import datetime
from html import escape
from pathlib import Path

USER = "m-afham"
OUT = Path(__file__).resolve().parent.parent / "cards"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
STATIC = os.environ.get("STATIC") == "1"

GUT = 8          # inner-side gutter of a half card (column gap = 2 * GUT)
ROW_GAP = 12     # bottom gutter on grid cards (plus the ~4px inline baseline gap)
BTN_PAD = 6      # side padding on buttons so neighbours get room
FULL = 880       # width of a full-width card
HALF = FULL // 2 - GUT  # 432

FEATURED = "AirCursor"
RECENT = [
    # repo, short blurb (from the repo description/README), tags
    ("Twinly", "Find your famous twin, fully offline on iPhone. Vision + Core ML ArcFace matching against 9,675 actors.", ["Core ML", "Vision", "SwiftUI"]),
    ("SmartSim", "Native macOS tool for sending push notifications to iOS Simulators. No APNs setup, no server.", ["macOS 15+", "Swift 6"]),
    ("SwiftCleanCode", "Clean Architecture in Swift for live coding interviews, with real API integration and tests.", ["Clean Architecture", "DI", "Tests"]),
    ("SensorMotionEffect", "Add a depth effect to UIImageView using Core Motion Manager.", ["Core Motion", "UIKit"]),
    ("InstagramStoryView", "Story view component that extracts dominant colors from images and applies them as backgrounds.", ["UIKit", "Animation"]),
    ("SmileToUnlock", "A screen that unlocks itself when you smile, with ARKit face tracking, Lottie and haptics.", ["ARKit", "Lottie", "Haptics"]),
]
# Only public repos are featured: private ones would 404 for visitors.

# buttons: file name, label, style, icon
BUTTONS = [
    ("hire", "Hire Me", "primary", "mail"),
    ("book", "Book a 1:1", "secondary", "calendar"),
    ("coffee", "Buy Me a Coffee", "secondary", "cup"),
    ("download", "Download for Mac", "secondary", "download"),
]

FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', Helvetica, Arial, sans-serif"

# One accent (Apple system blue); everything else is greys.
THEMES = {
    "light": dict(card="#F5F5F7", stroke="#E5E5EA", ink="#1D1D1F", sub="#6E6E73", faint="#D2D2D7",
                  chip="#E8E8ED", blue="#0071E3", green="#28A745", window="#FFFFFF", bar="#D2D2D7",
                  on_blue="#FFFFFF"),
    "dark": dict(card="#161618", stroke="#2C2C2E", ink="#F5F5F7", sub="#98989D", faint="#3A3A3C",
                 chip="#2C2C2E", blue="#0A84FF", green="#30D158", window="#1C1C1E", bar="#3A3A3C",
                 on_blue="#FFFFFF"),
}


# ---------------------------------------------------------------- data
def api(path, body=None):
    req = urllib.request.Request("https://api.github.com" + path,
                                 data=json.dumps(body).encode() if body else None)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-card-renderer")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def load_data():
    repos, page = [], 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    q = '{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}' % USER
    cal = api("/graphql", {"query": q})["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    return dict(repos={r["name"]: r for r in repos}, total_contrib=cal["totalContributions"], days=days)


# ---------------------------------------------------------------- helpers
def svg(w, h, body, title, side=None, pad_bottom=0, pad_x=0):
    """side: 'L' (gutter on the right), 'R' (gutter on the left) or None."""
    reduced = ("@media (prefers-reduced-motion: reduce){*{animation:none!important}"
               ".cnt{display:none}.final{opacity:1!important}}")
    if STATIC:
        reduced = "*{animation:none!important}.cnt{display:none}.final{opacity:1!important}"
    ow = w + (GUT if side else 0) + 2 * pad_x
    dx = (GUT if side == "R" else 0) + pad_x
    oh = h + pad_bottom
    inner = f'<g transform="translate({dx} 0)">{body}</g>' if dx else body
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" viewBox="0 0 {ow} {oh}" '
            f'role="img" aria-label="{escape(title)}" font-family="{FONT}">'
            f'<title>{escape(title)}</title><style>{BASE_CSS}{reduced}</style>{inner}</svg>')


def counter(value_text, final_num, x, y, attrs, begin=0.5, frames=18, dur=0.9):
    """Count from 0 up to final_num using SMIL <set> frames (CSS can't change text)."""
    if final_num <= 0 or STATIC:
        return f'<text x="{x}" y="{y}" {attrs}>{escape(value_text)}</text>'
    suffix = value_text[len(str(final_num)):]
    out, step = [], dur / frames
    for i in range(frames - 1):
        n = round(final_num * ((i + 1) / frames) ** 0.6)
        t = begin + i * step
        out.append(f'<text class="cnt" x="{x}" y="{y}" {attrs} opacity="0">{n}{escape(suffix)}'
                   f'<set attributeName="opacity" to="1" begin="{t:.3f}s" dur="{step:.3f}s"/></text>')
    t = begin + (frames - 1) * step
    out.append(f'<text class="final" x="{x}" y="{y}" {attrs} opacity="0">{escape(value_text)}'
               f'<set attributeName="opacity" to="1" begin="{t:.3f}s" fill="freeze"/></text>')
    return "".join(out)


def wrap(text, width, max_lines=2):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,:;") + "…"
    return lines


def card_bg(t, w, h, rx=22):
    return f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{rx}" fill="{t["card"]}" stroke="{t["stroke"]}"/>'


BASE_CSS = """
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{0%{opacity:0;transform:scale(.7)}100%{opacity:1;transform:scale(1)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
@keyframes nudge{0%,80%,100%{transform:translateX(0)}90%{transform:translateX(4px)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
.r{animation:rise .8s cubic-bezier(.2,.8,.2,1) both}
.f{animation:fade .8s ease both}
"""


# ---------------------------------------------------------------- cards
def hero(t, d):
    W, H = FULL, 280
    tiles = []
    for i in range(9):
        cx, cy = 668 + (i % 3) * 62, 58 + (i // 3) * 62
        fill, op = (t["blue"], 1) if i == 4 else (t["ink"], [.08, .14, .06, .12, 0, .18, .05, .1, .15][i])
        tiles.append(f'<rect x="{cx}" y="{cy}" width="50" height="50" rx="12" fill="{fill}" fill-opacity="{op}" '
                     f'style="transform-box:fill-box;transform-origin:center;animation:pop .6s cubic-bezier(.2,.8,.2,1) {0.8+i*0.06:.2f}s both"/>')
    body = f"""
<defs>
  <linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="560" y2="0">
    <stop offset="0" stop-color="{t['ink']}"/><stop offset=".42" stop-color="{t['ink']}"/>
    <stop offset=".5" stop-color="{t['blue']}"/><stop offset=".58" stop-color="{t['ink']}"/>
    <stop offset="1" stop-color="{t['ink']}"/>
    <animateTransform attributeName="gradientTransform" type="translate" values="-600 0;-600 0;600 0;600 0" keyTimes="0;.55;.85;1" dur="7s" repeatCount="indefinite"/>
  </linearGradient>
</defs>
{card_bg(t, W, H, 24)}
<g class="r" style="animation-delay:.1s"><text x="48" y="72" font-size="13" font-weight="600" letter-spacing="1.6" fill="{t['blue']}">LEAD iOS &amp; macOS ENGINEER · MOBILE ARCHITECTURE</text></g>
<g class="r" style="animation-delay:.25s"><text x="46" y="130" font-size="52" font-weight="700" letter-spacing="-1.2" fill="url(#shine)">Muhammad Afham</text></g>
<g class="r" style="animation-delay:.4s"><text x="48" y="168" font-size="18" fill="{t['sub']}">Crafting exceptional mobile experiences with precision and passion.</text></g>
<g class="r" style="animation-delay:.55s"><text x="48" y="204" font-size="15" fill="{t['sub']}">
  <tspan font-weight="600" fill="{t['ink']}">7+</tspan> years  ·  <tspan font-weight="600" fill="{t['ink']}">25+</tspan> apps shipped  ·  iOS &amp; macOS  ·  Pakistan</text></g>
<g class="r" style="animation-delay:.7s">
  <rect x="48.5" y="224.5" width="315" height="29" rx="14.5" fill="none" stroke="{t['faint']}"/>
  <circle cx="66" cy="239" r="4.5" fill="{t['green']}" style="animation:pulse 2.4s ease-in-out infinite"/>
  <text x="79" y="243.5" font-size="13" font-weight="500" fill="{t['ink']}">Available for contract &amp; consulting work</text>
</g>
{''.join(tiles)}
"""
    return svg(W, H, body, "Muhammad Afham, Lead iOS & macOS Engineer")


def tile(t, value_text, num, label, caption, idx, side):
    W, H = HALF, 150
    body = f"""
<g class="r" style="animation-delay:{0.15*idx:.2f}s">
{card_bg(t, W, H)}
<g style="animation:nudge 3s ease-in-out {1.5+idx*.3:.1f}s infinite">
<path d="M{W-42} 34h12m-5-5 5 5-5 5" stroke="{t['blue']}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>
{counter(value_text, num, 28, 78, f'font-size="50" font-weight="700" letter-spacing="-1.5" fill="{t["ink"]}"', begin=0.4 + 0.15*idx)}
<text x="29" y="110" font-size="16" font-weight="600" fill="{t['ink']}">{escape(label)}</text>
<text x="29" y="131" font-size="13" fill="{t['sub']}">{escape(caption)}</text>
</g>"""
    return svg(W, H, body, f"{value_text} {label}", side=side)


def spotlight(t, d):
    W, H = FULL, 280
    r = d["repos"][FEATURED]
    stars, forks = r["stargazers_count"], r["forks_count"]
    sw = 11 * len(str(stars))
    cur = f"""
<g>
  <animateTransform attributeName="transform" type="translate" dur="7s" repeatCount="indefinite"
    values="600 115;600 115;748 209;748 209;748 209;640 145;600 115" keyTimes="0;.08;.35;.62;.7;.9;1"
    calcMode="spline" keySplines=".4 0 .2 1;.4 0 .2 1;0 0 1 1;0 0 1 1;.4 0 .2 1;.4 0 .2 1"/>
  <path d="M0 0v17l4.6-4.3 3.1 6.7 2.6-1.1-3-6.6h6.4z" fill="{t['ink']}" stroke="{t['window']}" stroke-width="1.3" stroke-linejoin="round"/>
</g>"""
    body = f"""
{card_bg(t, W, H, 24)}
<g class="r" style="animation-delay:.1s">
  <rect x="40.5" y="36.5" width="196" height="25" rx="12.5" fill="none" stroke="{t['faint']}"/>
  <text x="138.5" y="53.5" font-size="11.5" font-weight="600" letter-spacing="1.1" text-anchor="middle" fill="{t['sub']}">FEATURED · OPEN SOURCE</text>
</g>
<g class="r" style="animation-delay:.25s"><text x="38" y="110" font-size="44" font-weight="700" letter-spacing="-1" fill="{t['ink']}">AirCursor</text></g>
<g class="r" style="animation-delay:.4s"><text x="40" y="146" font-size="21" font-weight="600" fill="{t['ink']}">Your AirPods are now a mouse.</text></g>
<g class="r" style="animation-delay:.55s">
  <text x="40" y="176" font-size="15" fill="{t['sub']}">Turn your head to point. Rest on a button to click.</text>
  <text x="40" y="197" font-size="15" fill="{t['sub']}">Hands-free, private, open source, on macOS.</text>
</g>
<g class="r" style="animation-delay:.7s">
  <path d="M48 224.5l3.1 6.3 6.9 1-5 4.9 1.2 6.9-6.2-3.3-6.2 3.3 1.2-6.9-5-4.9 6.9-1z" fill="{t['ink']}"/>
  {counter(f"{stars}", stars, 64, 241, f'font-size="18" font-weight="700" fill="{t["ink"]}"', begin=0.9, dur=1.1)}
  <text x="{70 + sw}" y="241" font-size="15" fill="{t['sub']}">stars</text>
  <text x="{126 + sw}" y="241" font-size="15" fill="{t['sub']}"><tspan font-weight="700" fill="{t['ink']}" font-size="18">{forks}</tspan> forks</text>
  <text x="{208 + sw}" y="241" font-size="13" fill="{t['sub']}">Swift · SwiftUI · macOS 15+ · MIT</text>
</g>
<g class="f" style="animation-delay:.5s">
  <rect x="540.5" y="30.5" width="305" height="219" rx="14" fill="{t['window']}" stroke="{t['stroke']}"/>
  <circle cx="560" cy="50" r="5.5" fill="{t['faint']}"/><circle cx="578" cy="50" r="5.5" fill="{t['faint']}"/><circle cx="596" cy="50" r="5.5" fill="{t['faint']}"/>
  <text x="693" y="54" font-size="12" font-weight="600" text-anchor="middle" fill="{t['sub']}">AirCursor</text>
  <line x1="541" y1="68" x2="845" y2="68" stroke="{t['stroke']}"/>
  <rect x="562" y="88" width="150" height="10" rx="5" fill="{t['faint']}"/>
  <rect x="562" y="108" width="232" height="8" rx="4" fill="{t['faint']}" opacity=".6"/>
  <rect x="562" y="124" width="200" height="8" rx="4" fill="{t['faint']}" opacity=".6"/>
  <rect x="562" y="140" width="216" height="8" rx="4" fill="{t['faint']}" opacity=".6"/>
  <rect x="610" y="196" width="96" height="30" rx="8" fill="{t['faint']}" opacity=".7"/>
  <text x="658" y="216" font-size="13" text-anchor="middle" fill="{t['ink']}">Not now</text>
  <rect x="716" y="196" width="108" height="30" rx="8" fill="{t['blue']}">
    <animate attributeName="opacity" values="1;1;.55;1;1" keyTimes="0;.62;.66;.72;1" dur="7s" repeatCount="indefinite"/></rect>
  <text x="770" y="216" font-size="13" font-weight="600" text-anchor="middle" fill="{t['on_blue']}">Continue</text>
  <circle cx="752" cy="214" r="15" fill="none" stroke="{t['blue']}" stroke-width="3" stroke-linecap="round"
    stroke-dasharray="94.25" stroke-dashoffset="94.25" transform="rotate(-90 752 214)" opacity="0">
    <animate attributeName="stroke-dashoffset" values="94.25;94.25;0;0;94.25" keyTimes="0;.36;.62;.7;1" dur="7s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;.35;.37;.66;.7;1" dur="7s" repeatCount="indefinite"/>
  </circle>
  {cur}
</g>
"""
    return svg(W, H, body, f"AirCursor: {stars} stars")


def activity(t, d):
    W, H = FULL, 260
    days = d["days"]
    months = OrderedDict()
    for ds, c in days:
        months[ds[:7]] = months.get(ds[:7], 0) + c
    keys = list(months)[-12:]
    vals = [months[k] for k in keys]
    peak = max(vals) or 1
    best_i = vals.index(max(vals))
    best_day = max(days, key=lambda x: x[1])
    active = sum(1 for _, c in days if c > 0)
    longest = cur = 0
    for _, c in days:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)

    x0, base, bw, gap, hmax = 44, 206, 30, 12, 124
    bars = []
    for i, (k, v) in enumerate(zip(keys, vals)):
        x = x0 + i * (bw + gap)
        h = max(3, v / peak * hmax)
        fill = t["blue"] if i == best_i else t["bar"]
        delay = 0.35 + i * 0.06
        bars.append(f'<rect x="{x}" y="{base-h:.1f}" width="{bw}" height="{h:.1f}" rx="6" fill="{fill}" '
                    f'style="transform-box:fill-box;transform-origin:bottom;animation:grow .9s cubic-bezier(.2,.8,.2,1) {delay:.2f}s both"/>')
        mlabel = datetime.strptime(k, "%Y-%m").strftime("%b")
        bars.append(f'<text x="{x+bw/2}" y="{base+22}" font-size="11.5" text-anchor="middle" fill="{t["sub"]}">{mlabel}</text>')
        if i == best_i:
            bars.append(f'<g class="f" style="animation-delay:{delay+0.8:.2f}s"><text x="{x+bw/2}" y="{base-h-9:.1f}" font-size="13" '
                        f'font-weight="700" text-anchor="middle" fill="{t["blue"]}">{v}</text></g>')

    bd = datetime.strptime(best_day[0], "%Y-%m-%d").strftime("%b %-d, %Y")
    bm = datetime.strptime(keys[best_i], "%Y-%m").strftime("%B %Y")
    stats = [("Contributions", str(d["total_contrib"]), "in the last year"),
             ("Best month", str(vals[best_i]), bm),
             ("Best day", str(best_day[1]), bd),
             ("Active days", str(active), f"longest streak {longest}d")]
    st = []
    for i, (lab, val, cap) in enumerate(stats):
        cx, cy = 592 + (i % 2) * 140, 84 + (i // 2) * 86
        st.append(f'<g class="r" style="animation-delay:{0.5+i*0.12:.2f}s">'
                  f'<text x="{cx}" y="{cy}" font-size="11.5" font-weight="600" letter-spacing=".6" fill="{t["sub"]}">{lab.upper()}</text>'
                  f'<text x="{cx}" y="{cy+32}" font-size="30" font-weight="700" letter-spacing="-.8" fill="{t["ink"]}">{val}</text>'
                  f'<text x="{cx}" y="{cy+52}" font-size="12" fill="{t["sub"]}">{escape(cap)}</text></g>')
    body = f"""
{card_bg(t, W, H, 24)}
<g class="r"><text x="44" y="52" font-size="20" font-weight="700" fill="{t['ink']}">Activity</text>
<text x="132" y="52" font-size="14" fill="{t['sub']}">contributions per month</text></g>
<line x1="{x0}" y1="{base}" x2="{x0+12*(bw+gap)-gap}" y2="{base}" stroke="{t['stroke']}"/>
{''.join(bars)}
<line x1="560" y1="64" x2="560" y2="222" stroke="{t['stroke']}"/>
{''.join(st)}
"""
    return svg(W, H, body, f"{d['total_contrib']} contributions in the last year")


def repo_card(t, d, name, blurb, tags, idx):
    W, H = HALF, 158
    r = d["repos"][name]
    lang = r.get("language") or ""
    lines = wrap(blurb, 54)
    desc = "".join(f'<text x="24" y="{80 + i*20}" font-size="13.5" fill="{t["sub"]}">{escape(l)}</text>' for i, l in enumerate(lines))
    chips, cx = [], 24
    for tg in tags:
        w = 7.0 * len(tg) + 20
        chips.append(f'<rect x="{cx}" y="{H-44}" width="{w:.0f}" height="22" rx="11" fill="{t["chip"]}"/>'
                     f'<text x="{cx + w/2:.0f}" y="{H-29}" font-size="11.5" font-weight="500" text-anchor="middle" fill="{t["sub"]}">{escape(tg)}</text>')
        cx += w + 6
    meta = f'<text x="{W-24}" y="{H-29}" font-size="12" text-anchor="end" fill="{t["sub"]}">{escape(lang)}</text>' if lang else ""
    star = ""
    if r["stargazers_count"]:
        star = f'<text x="{W-24}" y="46" font-size="12.5" text-anchor="end" fill="{t["sub"]}">★ {r["stargazers_count"]}</text>'
    body = f"""
<g class="r" style="animation-delay:{0.12*idx:.2f}s">
{card_bg(t, W, H, 20)}
<path d="M26 32.5h5l2 2.5h9a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H26a2 2 0 0 1-2-2v-10.5a2 2 0 0 1 2-2z" fill="none" stroke="{t['blue']}" stroke-width="1.6"/>
<text x="54" y="46" font-size="17" font-weight="700" fill="{t['ink']}">{escape(name)}</text>
{star}{desc}{''.join(chips)}{meta}
</g>"""
    return svg(W, H, body, f"{name}: {blurb}", side="L" if idx == 0 else "R", pad_bottom=ROW_GAP)


ICONS = {
    "mail": '<rect x="0" y="2" width="16" height="12" rx="2.5" fill="none" stroke="{c}" stroke-width="1.6"/><path d="M1 4l7 5 7-5" fill="none" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/>',
    "calendar": '<rect x="0" y="2" width="16" height="13" rx="2.5" fill="none" stroke="{c}" stroke-width="1.6"/><path d="M0 6.5h16M4.5 0v4M11.5 0v4" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
    "cup": '<path d="M1 4h11v5a4.5 4.5 0 0 1-4.5 4.5h-2A4.5 4.5 0 0 1 1 9z" fill="none" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 5.5h1.2a2.3 2.3 0 0 1 0 4.6H12" fill="none" stroke="{c}" stroke-width="1.6"/>',
    "download": '<path d="M8 1v9m-4-4 4 4 4-4M1 14h14" fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
}


def button(t, label, style, icon):
    H = 44
    tw = round(len(label) * 8.6)
    W = 22 + 16 + 9 + tw + 24
    if style == "primary":
        bg = f'<rect x="0" y="0" width="{W}" height="{H}" rx="22" fill="{t["blue"]}"/>'
        c = t["on_blue"]
    else:
        bg = f'<rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="21.25" fill="{t["card"]}" stroke="{t["faint"]}" stroke-width="1.5"/>'
        c = t["ink"]
    body = (f'{bg}<g transform="translate(22 14)">{ICONS[icon].format(c=c)}</g>'
            f'<text x="{22+16+9}" y="27.5" font-size="15" font-weight="600" fill="{c}">{escape(label)}</text>')
    return svg(W, H, body, label, pad_x=BTN_PAD)


def main():
    d = load_data()
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("tile-repos-*.svg"):
        f.unlink()
    for mode, t in THEMES.items():
        files = {
            f"hero-{mode}.svg": hero(t, d),
            f"spotlight-{mode}.svg": spotlight(t, d),
            f"activity-{mode}.svg": activity(t, d),
            f"tile-apps-{mode}.svg": tile(t, "25+", 25, "Apps shipped", "iPhone, iPad, Mac & Apple Watch", 0, "L"),
            f"tile-years-{mode}.svg": tile(t, "7+", 7, "Years on Apple platforms", "Lead iOS Engineer", 1, "R"),
        }
        for i, (name, blurb, tags) in enumerate(RECENT):
            files[f"repo-{name.lower()}-{mode}.svg"] = repo_card(t, d, name, blurb, tags, i % 2)
        for key, label, style, icon in BUTTONS:
            files[f"btn-{key}-{mode}.svg"] = button(t, label, style, icon)
        for fn, content in files.items():
            (OUT / fn).write_text(content)
    print(f"rendered {len(list(OUT.glob('*.svg')))} cards → {OUT}")


if __name__ == "__main__":
    main()
