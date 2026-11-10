#!/usr/bin/env python3
"""Render the animated, Apple-inspired SVG cards used in the profile README.

Every number comes from the GitHub API at render time (no hard-coded stats),
except the facts stated in the README itself (7+ years, 25+ apps shipped).

Usage:
    GITHUB_TOKEN=... python3 scripts/render_cards.py
    STATIC=1 python3 scripts/render_cards.py   # final frame only, for screenshots
"""
import json
import os
import urllib.request
from collections import OrderedDict
from datetime import date, datetime
from html import escape
from pathlib import Path

USER = "m-afham"
OUT = Path(__file__).resolve().parent.parent / "cards"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
STATIC = os.environ.get("STATIC") == "1"

FEATURED = "AirCursor"
RECENT = [
    # repo, short blurb (from the repo description), tags
    ("Twinly", "Find your famous twin, fully offline on iPhone. Vision + Core ML ArcFace matching against 9,675 actors.", ["Core ML", "Vision", "SwiftUI"]),
    ("SmartSim", "Native macOS tool for sending push notifications to iOS Simulators. No APNs setup, no server.", ["macOS 15+", "Swift 6"]),
    ("SwiftCleanCode", "Clean Architecture in Swift for live coding interviews, with real API integration and tests.", ["Clean Architecture", "DI", "Tests"]),
    ("SensorMotionEffect", "Add a depth effect to UIImageView using Core Motion Manager.", ["Core Motion", "UIKit"]),
    ("InstagramStoryView", "Story view component that extracts dominant colors from images and applies them as backgrounds.", ["UIKit", "Animation"]),
    ("SmileToUnlock", "A screen that unlocks itself when you smile, with ARKit face tracking, Lottie and haptics.", ["ARKit", "Lottie", "Haptics"]),
]
# Only public repos are featured: private ones would 404 for visitors.

FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'SF Mono', ui-monospace, Menlo, Consolas, monospace"
LANG_COLORS = {"Swift": "#F05138", "TypeScript": "#3178C6", "Shell": "#89E051", "HTML": "#E34C26"}

THEMES = {
    "light": dict(bg="#FFFFFF", card="#F5F5F7", stroke="#E5E5EA", ink="#1D1D1F", sub="#6E6E73",
                  faint="#D2D2D7", blue="#0071E3", green="#28A745", orange="#F56300", purple="#A94BD6",
                  pink="#E3245B", window="#FFFFFF", bar="#D2D2D7"),
    "dark": dict(bg="#0D1117", card="#161618", stroke="#2C2C2E", ink="#F5F5F7", sub="#98989D",
                 faint="#3A3A3C", blue="#0A84FF", green="#30D158", orange="#FF9F0A", purple="#BF5AF2",
                 pink="#FF375F", window="#1C1C1E", bar="#3A3A3C"),
}


# ---------------------------------------------------------------- data
def api(path, body=None):
    url = "https://api.github.com" + path
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-card-renderer")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def load_data():
    user = api(f"/users/{USER}")
    repos, page = [], 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    by_name = {r["name"]: r for r in repos}
    total_stars = sum(r["stargazers_count"] for r in repos if not r["fork"])

    q = '{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}' % USER
    cal = api("/graphql", {"query": q})["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    return dict(user=user, repos=by_name, total_stars=total_stars,
                total_contrib=cal["totalContributions"], days=days)


# ---------------------------------------------------------------- helpers
def svg(w, h, body, style="", title=""):
    reduced = ("@media (prefers-reduced-motion: reduce){*{animation:none!important}"
               ".cnt{display:none}.final{opacity:1!important}}")
    if STATIC:
        reduced = "*{animation:none!important}.cnt{display:none}.final{opacity:1!important}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(title)}" font-family="{FONT}">'
            f'<title>{escape(title)}</title><style>{style}{reduced}</style>{body}</svg>')


def counter(value_text, final_num, x, y, attrs, begin=0.5, frames=18, dur=0.9):
    """Count from 0 up to final_num using SMIL <set> frames (CSS can't change text)."""
    if final_num <= 0 or STATIC:
        return f'<text x="{x}" y="{y}" {attrs}>{escape(value_text)}</text>'
    suffix = value_text[len(str(final_num)):]
    out, step = [], dur / frames
    for i in range(frames):
        n = round(final_num * ((i + 1) / frames) ** 0.6)
        if i == frames - 1:
            break
        t = begin + i * step
        out.append(f'<text class="cnt" x="{x}" y="{y}" {attrs} opacity="0">{n}{escape(suffix)}'
                   f'<set attributeName="opacity" to="1" begin="{t:.3f}s" dur="{step:.3f}s"/></text>')
    t = begin + (frames - 1) * step
    out.append(f'<text class="final" x="{x}" y="{y}" {attrs} opacity="0">{escape(value_text)}'
               f'<set attributeName="opacity" to="1" begin="{t:.3f}s" fill="freeze"/></text>')
    # for viewers whose renderer ignores SMIL, the final frame is the fallback via reduced-motion CSS
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


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


BASE_CSS = """
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{0%{opacity:0;transform:scale(.6)}70%{opacity:1;transform:scale(1.06)}100%{opacity:1;transform:scale(1)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
@keyframes ring{0%{r:5;opacity:.6}100%{r:13;opacity:0}}
@keyframes nudge{0%,80%,100%{transform:translateX(0)}90%{transform:translateX(4px)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
.r{animation:rise .8s cubic-bezier(.2,.8,.2,1) both}
.f{animation:fade .8s ease both}
"""


# ---------------------------------------------------------------- cards
def hero(t, d):
    W, H = 880, 300
    years, apps = "7+", "25+"
    icons, colors = [], [t["blue"], t["purple"], t["pink"], t["orange"], t["green"], "#5AC8FA", "#FFCC00", "#5856D6", "#FF2D55"]
    for i in range(9):
        cx, cy = 650 + (i % 3) * 66, 66 + (i // 3) * 66
        c = colors[i]
        delay = 0.9 + i * 0.08
        icons.append(
            f'<g style="transform-box:fill-box;transform-origin:center;'
            f'animation:pop .6s cubic-bezier(.2,.8,.2,1) {delay:.2f}s both">'
            f'<g style="animation:float 4s ease-in-out {i*0.3:.1f}s infinite">'
            f'<rect x="{cx}" y="{cy}" width="54" height="54" rx="13" fill="url(#ic{i})"/>'
            f'<rect x="{cx}" y="{cy}" width="54" height="27" rx="13" fill="#fff" opacity=".12"/>'
            f'</g></g>'
            f'<defs><linearGradient id="ic{i}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{c}" stop-opacity=".95"/><stop offset="1" stop-color="{c}"/></linearGradient></defs>')
    body = f"""
<defs>
  <linearGradient id="glow" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="{H}">
    <stop offset="0" stop-color="{t['blue']}"/><stop offset=".35" stop-color="{t['purple']}"/>
    <stop offset=".65" stop-color="{t['pink']}"/><stop offset="1" stop-color="{t['orange']}"/>
    <animateTransform attributeName="gradientTransform" type="rotate" values="0 440 150;360 440 150" dur="10s" repeatCount="indefinite"/>
  </linearGradient>
  <linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="560" y2="0">
    <stop offset="0" stop-color="{t['ink']}"/><stop offset=".42" stop-color="{t['ink']}"/>
    <stop offset=".5" stop-color="{t['blue']}"/><stop offset=".58" stop-color="{t['ink']}"/>
    <stop offset="1" stop-color="{t['ink']}"/>
    <animateTransform attributeName="gradientTransform" type="translate" values="-600 0;-600 0;600 0;600 0" keyTimes="0;.55;.85;1" dur="6s" repeatCount="indefinite"/>
  </linearGradient>
</defs>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="24" fill="{t['card']}"/>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="24" fill="none" stroke="url(#glow)" stroke-width="2" opacity=".85"/>
<g class="r" style="animation-delay:.1s"><text x="48" y="74" font-size="13" font-weight="600" letter-spacing="1.6" fill="{t['blue']}">LEAD iOS &amp; macOS ENGINEER · MOBILE ARCHITECTURE</text></g>
<g class="r" style="animation-delay:.25s"><text x="46" y="134" font-size="52" font-weight="700" letter-spacing="-1.2" fill="url(#shine)">Muhammad Afham</text></g>
<g class="r" style="animation-delay:.4s"><text x="48" y="174" font-size="18" fill="{t['sub']}">Crafting exceptional mobile experiences with precision and passion.</text></g>
<g class="r" style="animation-delay:.55s"><text x="48" y="212" font-size="15" fill="{t['ink']}">
  <tspan font-weight="600">{years}</tspan><tspan fill="{t['sub']}"> years  ·  </tspan><tspan font-weight="600">{apps}</tspan><tspan fill="{t['sub']}"> apps shipped  ·  iOS &amp; macOS  ·  Pakistan</tspan></text></g>
<g class="r" style="animation-delay:.7s">
  <rect x="48" y="232" width="336" height="32" rx="16" fill="{t['green']}" opacity=".12"/>
  <circle cx="68" cy="248" r="5" fill="{t['green']}" style="animation:pulse 2s ease-in-out infinite"/>
  <circle cx="68" cy="248" r="5" fill="none" stroke="{t['green']}" style="animation:ring 2s ease-out infinite"/>
  <text x="82" y="253" font-size="13.5" font-weight="500" fill="{t['green']}">Available for contract &amp; consulting work</text>
</g>
{''.join(icons)}
"""
    return svg(W, H, body, BASE_CSS, "Muhammad Afham, Lead iOS & macOS Engineer")


def tile(t, accent, value_text, num, label, caption, idx):
    W, H = 286, 176
    a = t[accent]
    body = f"""
<g class="r" style="animation-delay:{0.15*idx:.2f}s">
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="22" fill="{t['card']}" stroke="{t['stroke']}"/>
<circle cx="{W-34}" cy="34" r="16" fill="{a}" opacity=".12"/>
<g style="animation:nudge 3s ease-in-out {1.5+idx*.3:.1f}s infinite">
<path d="M{W-40} 34h11m-4.5-4.5 4.5 4.5-4.5 4.5" stroke="{a}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>
{counter(value_text, num, 26, 92, f'font-size="54" font-weight="700" letter-spacing="-1.5" fill="{a}"', begin=0.4 + 0.15*idx)}
<text x="27" y="126" font-size="16" font-weight="600" fill="{t['ink']}">{escape(label)}</text>
<text x="27" y="150" font-size="13" fill="{t['sub']}">{escape(caption)}</text>
</g>"""
    return svg(W, H, body, BASE_CSS, f"{value_text} {label}")


def spotlight(t, d):
    W, H = 880, 290
    r = d["repos"][FEATURED]
    stars, forks = r["stargazers_count"], r["forks_count"]
    # cursor animation: start → button, dwell (ring fills) → click → drift back
    cur = f"""
<g>
  <animateTransform attributeName="transform" type="translate" dur="7s" repeatCount="indefinite"
    values="600 120;600 120;748 214;748 214;748 214;640 150;600 120" keyTimes="0;.08;.35;.62;.7;.9;1"
    calcMode="spline" keySplines=".4 0 .2 1;.4 0 .2 1;0 0 1 1;0 0 1 1;.4 0 .2 1;.4 0 .2 1"/>
  <path d="M0 0v17l4.6-4.3 3.1 6.7 2.6-1.1-3-6.6h6.4z" fill="{t['ink']}" stroke="{t['window']}" stroke-width="1.3" stroke-linejoin="round"/>
</g>"""
    body = f"""
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="24" fill="{t['card']}" stroke="{t['stroke']}"/>
<g class="r" style="animation-delay:.1s">
  <rect x="40" y="38" width="218" height="26" rx="13" fill="{t['orange']}" opacity=".14"/>
  <text x="54" y="56" font-size="12" font-weight="700" letter-spacing="1.2" fill="{t['orange']}">FEATURED · OPEN SOURCE</text>
</g>
<g class="r" style="animation-delay:.25s"><text x="38" y="114" font-size="44" font-weight="700" letter-spacing="-1" fill="{t['ink']}">AirCursor</text></g>
<g class="r" style="animation-delay:.4s"><text x="40" y="150" font-size="21" font-weight="600" fill="{t['ink']}">Your AirPods are now a mouse.</text></g>
<g class="r" style="animation-delay:.55s">
  <text x="40" y="180" font-size="15" fill="{t['sub']}">Turn your head to point. Rest on a button to click.</text>
  <text x="40" y="201" font-size="15" fill="{t['sub']}">Hands-free, private, open source, on macOS.</text>
</g>
<g class="r" style="animation-delay:.7s">
  <path d="M48 230l3.1 6.3 6.9 1-5 4.9 1.2 6.9-6.2-3.3-6.2 3.3 1.2-6.9-5-4.9 6.9-1z" fill="{t['orange']}"/>
  {counter(f"{stars}", stars, 64, 246, f'font-size="18" font-weight="700" fill="{t["ink"]}"', begin=0.9, dur=1.1)}
  <text x="{70 + 11*len(str(stars))}" y="246" font-size="15" fill="{t['sub']}">stars</text>
  <text x="{130 + 11*len(str(stars))}" y="246" font-size="15" fill="{t['sub']}"><tspan font-weight="700" fill="{t['ink']}" font-size="18">{forks}</tspan> forks</text>
  <text x="{215 + 11*len(str(stars))}" y="246" font-size="13" fill="{t['sub']}">Swift · SwiftUI · macOS 15+ · MIT</text>
</g>
<g class="f" style="animation-delay:.5s">
  <rect x="540" y="34" width="306" height="222" rx="14" fill="{t['window']}" stroke="{t['stroke']}"/>
  <circle cx="560" cy="54" r="5.5" fill="#FF5F57"/><circle cx="578" cy="54" r="5.5" fill="#FEBC2E"/><circle cx="596" cy="54" r="5.5" fill="#28C840"/>
  <text x="693" y="58" font-size="12" font-weight="600" text-anchor="middle" fill="{t['sub']}">AirCursor</text>
  <line x1="540" y1="72" x2="846" y2="72" stroke="{t['stroke']}"/>
  <rect x="562" y="92" width="150" height="10" rx="5" fill="{t['faint']}"/>
  <rect x="562" y="112" width="232" height="8" rx="4" fill="{t['faint']}" opacity=".6"/>
  <rect x="562" y="128" width="200" height="8" rx="4" fill="{t['faint']}" opacity=".6"/>
  <rect x="562" y="144" width="216" height="8" rx="4" fill="{t['faint']}" opacity=".6"/>
  <rect x="610" y="200" width="96" height="30" rx="8" fill="{t['faint']}" opacity=".7"/>
  <text x="658" y="220" font-size="13" text-anchor="middle" fill="{t['ink']}">Not now</text>
  <rect x="716" y="200" width="108" height="30" rx="8" fill="{t['blue']}">
    <animate attributeName="opacity" values="1;1;.55;1;1" keyTimes="0;.62;.66;.72;1" dur="7s" repeatCount="indefinite"/></rect>
  <text x="770" y="220" font-size="13" font-weight="600" text-anchor="middle" fill="#fff">Continue</text>
  <circle cx="752" cy="218" r="15" fill="none" stroke="{t['blue']}" stroke-width="3" stroke-linecap="round"
    stroke-dasharray="94.25" stroke-dashoffset="94.25" transform="rotate(-90 752 218)" opacity="0">
    <animate attributeName="stroke-dashoffset" values="94.25;94.25;0;0;94.25" keyTimes="0;.36;.62;.7;1" dur="7s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;.35;.37;.66;.7;1" dur="7s" repeatCount="indefinite"/>
  </circle>
  {cur}
</g>
"""
    return svg(W, H, body, BASE_CSS, f"AirCursor: {stars} stars")


def activity(t, d):
    W, H = 880, 270
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
    # longest streak
    longest = cur = 0
    for _, c in days:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)

    x0, base, bw, gap, hmax = 44, 214, 30, 12, 130
    bars = []
    for i, (k, v) in enumerate(zip(keys, vals)):
        x = x0 + i * (bw + gap)
        h = max(3, v / peak * hmax)
        fill = t["blue"] if i == best_i else t["bar"]
        delay = 0.35 + i * 0.06
        bars.append(f'<rect x="{x}" y="{base-h:.1f}" width="{bw}" height="{h:.1f}" rx="6" fill="{fill}" '
                    f'style="transform-box:fill-box;transform-origin:bottom;animation:grow .9s cubic-bezier(.2,.8,.2,1) {delay:.2f}s both"/>')
        mlabel = datetime.strptime(k, "%Y-%m").strftime("%b")
        bars.append(f'<text x="{x+bw/2}" y="{base+20}" font-size="11.5" text-anchor="middle" fill="{t["sub"]}">{mlabel}</text>')
        if i == best_i:
            bars.append(f'<g class="f" style="animation-delay:{delay+0.8:.2f}s"><text x="{x+bw/2}" y="{base-h-9:.1f}" font-size="13" '
                        f'font-weight="700" text-anchor="middle" fill="{t["blue"]}">{v}</text></g>')

    bd = datetime.strptime(best_day[0], "%Y-%m-%d").strftime("%b %-d, %Y")
    bm = datetime.strptime(keys[best_i], "%Y-%m").strftime("%B %Y")
    stats = [("Contributions", fmt(d["total_contrib"]), "in the last year"),
             ("Best month", str(vals[best_i]), bm),
             ("Best day", str(best_day[1]), bd),
             ("Active days", str(active), f"longest streak {longest}d")]
    st = []
    for i, (lab, val, cap) in enumerate(stats):
        cx, cy = 580 + (i % 2) * 140, 92 + (i // 2) * 88
        st.append(f'<g class="r" style="animation-delay:{0.5+i*0.12:.2f}s">'
                  f'<text x="{cx}" y="{cy}" font-size="12" font-weight="600" letter-spacing=".6" fill="{t["sub"]}">{lab.upper()}</text>'
                  f'<text x="{cx}" y="{cy+32}" font-size="30" font-weight="700" letter-spacing="-.8" fill="{t["ink"]}">{val}</text>'
                  f'<text x="{cx}" y="{cy+52}" font-size="12" fill="{t["sub"]}">{escape(cap)}</text></g>')
    body = f"""
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="24" fill="{t['card']}" stroke="{t['stroke']}"/>
<g class="r"><text x="44" y="50" font-size="20" font-weight="700" fill="{t['ink']}">Activity</text>
<text x="132" y="50" font-size="14" fill="{t['sub']}">contributions per month</text></g>
<line x1="{x0}" y1="{base}" x2="{x0+12*(bw+gap)-gap}" y2="{base}" stroke="{t['stroke']}"/>
{''.join(bars)}
<line x1="556" y1="60" x2="556" y2="232" stroke="{t['stroke']}"/>
{''.join(st)}
"""
    return svg(W, H, body, BASE_CSS, f"{d['total_contrib']} contributions in the last year")


def repo_card(t, d, name, blurb, tags, idx):
    W, H = 432, 158
    r = d["repos"][name]
    lang = r.get("language") or ""
    lc = LANG_COLORS.get(lang, t["sub"])
    lines = wrap(blurb, 54)
    desc = "".join(f'<text x="24" y="{78 + i*20}" font-size="13.5" fill="{t["sub"]}">{escape(l)}</text>' for i, l in enumerate(lines))
    chips, cx = [], 24
    for tg in tags:
        w = 7.2 * len(tg) + 18
        chips.append(f'<rect x="{cx}" y="{H-42}" width="{w:.0f}" height="22" rx="11" fill="{t["blue"]}" opacity=".1"/>'
                     f'<text x="{cx + w/2:.0f}" y="{H-27}" font-size="11.5" font-weight="500" text-anchor="middle" fill="{t["blue"]}">{escape(tg)}</text>')
        cx += w + 6
    meta = f'<circle cx="{W-110}" cy="{H-31}" r="5" fill="{lc}"/><text x="{W-100}" y="{H-27}" font-size="12" fill="{t["sub"]}">{escape(lang)}</text>' if lang else ""
    star = ""
    if r["stargazers_count"]:
        star = f'<text x="{W-24}" y="44" font-size="12.5" text-anchor="end" fill="{t["sub"]}">★ {r["stargazers_count"]}</text>'
    body = f"""
<g class="r" style="animation-delay:{0.12*idx:.2f}s">
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="20" fill="{t['card']}" stroke="{t['stroke']}"/>
<path d="M26 30.5h5l2 2.5h9a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H26a2 2 0 0 1-2-2v-10.5a2 2 0 0 1 2-2z" fill="none" stroke="{t['blue']}" stroke-width="1.6"/>
<text x="54" y="44" font-size="17" font-weight="700" fill="{t['ink']}">{escape(name)}</text>
{star}{desc}{''.join(chips)}{meta}
</g>"""
    return svg(W, H, body, BASE_CSS, f"{name}: {blurb}")


def main():
    d = load_data()
    OUT.mkdir(exist_ok=True)
    pub = d["user"]["public_repos"]
    for mode, t in THEMES.items():
        files = {
            f"hero-{mode}.svg": hero(t, d),
            f"spotlight-{mode}.svg": spotlight(t, d),
            f"activity-{mode}.svg": activity(t, d),
            f"tile-apps-{mode}.svg": tile(t, "blue", "25+", 25, "Apps shipped", "iPhone, iPad, Mac & Apple Watch", 0),
            f"tile-years-{mode}.svg": tile(t, "purple", "7+", 7, "Years on Apple platforms", "Lead iOS Engineer", 1),
            f"tile-repos-{mode}.svg": tile(t, "orange", str(pub), pub, "Public repositories", f"{d['total_stars']} stars earned", 2),
        }
        for i, (name, blurb, tags) in enumerate(RECENT):
            files[f"repo-{name.lower()}-{mode}.svg"] = repo_card(t, d, name, blurb, tags, i % 2)
        for fn, content in files.items():
            (OUT / fn).write_text(content)
    print(f"rendered {len(list(OUT.glob('*.svg')))} cards → {OUT}")


if __name__ == "__main__":
    main()
