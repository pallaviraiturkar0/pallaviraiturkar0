"""Render neon terminal-style profile cards as SVGs from live GitHub data."""

import io
import json
import math
import os
import random
import urllib.request
from datetime import datetime, timezone
from html import escape

from PIL import Image

USERNAME = os.environ.get("GH_USERNAME", "pallaviraiturkar0")
TAGLINE = "Full-stack engineer · Human-centered AI & ML"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

MONO = "'JetBrains Mono','SF Mono',Menlo,Consolas,monospace"
SANS = "'Segoe UI','Helvetica Neue',Helvetica,Arial,sans-serif"
BG = "#0b1020"
PANEL = "#0f172a"
ACCENT = "#5eead4"
GLOW = "#22d3ee"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login name avatarUrl
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
      totalCount
      nodes {
        name description stargazerCount pushedAt
        primaryLanguage { name color }
        repositoryTopics(first: 3) { nodes { topic { name } } }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    pinnedItems(first: 2, types: REPOSITORY) {
      nodes { ... on Repository { name } }
    }
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 100) {
        repository { primaryLanguage { name color } }
        contributions { totalCount }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { primaryLanguage { name color } }
        contributions { totalCount }
      }
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode(),
        headers={"Authorization": f"bearer {os.environ.get('PROFILE_TOKEN') or os.environ['GH_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]["user"]


def window(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <linearGradient id="border" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{GLOW}"/><stop offset="0.5" stop-color="#a78bfa"/><stop offset="1" stop-color="{ACCENT}"/>
  </linearGradient>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<style>
  .mono {{ font-family: {MONO}; }}
  .sans {{ font-family: {SANS}; }}
  .pulse {{ animation: pulse 3s ease-in-out infinite; }}
  .tw {{ animation: tw 2.4s ease-in-out infinite; }}
  .blink {{ animation: blink 1s step-end infinite; }}
  .lit {{ animation: lit 3.2s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: .55 }} 50% {{ opacity: 1 }} }}
  @keyframes tw {{ 0%,100% {{ opacity: .15 }} 50% {{ opacity: 1 }} }}
  @keyframes blink {{ 50% {{ opacity: 0 }} }}
  @keyframes lit {{ 0%,100% {{ opacity: 1 }} 50% {{ opacity: .55 }} }}
</style>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="{BG}"/>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="none" stroke="url(#border)" stroke-width="1.5" class="pulse" filter="url(#glow)"/>
<circle cx="24" cy="22" r="5.5" fill="#ff5f57"/><circle cx="42" cy="22" r="5.5" fill="#febc2e"/><circle cx="60" cy="22" r="5.5" fill="#28c840"/>
<text x="{w-20}" y="27" text-anchor="end" class="mono" font-size="12" fill="{ACCENT}">{escape(title)}<tspan class="blink">_</tspan></text>
{body}
</svg>
"""


def stars(w, h, n, seed):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        x, y = rnd.uniform(10, w - 10), rnd.uniform(40, h - 10)
        r = rnd.choice([0.8, 1, 1.2, 1.6])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" class="tw" style="animation-delay:{rnd.uniform(0, 2.4):.2f}s"/>')
    return "".join(out)


def readable(color):
    # Lift dark language colors (e.g. Lua's navy) so they stay visible on the dark card.
    if not color or not color.startswith("#") or len(color) != 7:
        return MUTED
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum >= 90:
        return color
    k = 0.55
    return "#%02x%02x%02x" % tuple(int(v + (255 - v) * k) for v in (r, g, b))


def languages(user):
    # Weight by the user's commits + PRs per repo so private/enterprise work counts.
    # Only language names and percentages are rendered; repo names never leave this function.
    totals, colors = {}, {}
    cc = user["contributionsCollection"]
    for item in cc["commitContributionsByRepository"] + cc["pullRequestContributionsByRepository"]:
        lang = item["repository"]["primaryLanguage"]
        if lang:
            totals[lang["name"]] = totals.get(lang["name"], 0) + item["contributions"]["totalCount"]
            colors[lang["name"]] = readable(lang["color"])
    if totals:
        s = sum(totals.values())
        return [(n, v / s * 100, colors[n]) for n, v in sorted(totals.items(), key=lambda kv: -kv[1])[:5]]
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            totals[n] = totals.get(n, 0) + e["size"]
            colors[n] = readable(e["node"]["color"])
    s = sum(totals.values()) or 1
    return [(n, v / s * 100, colors[n]) for n, v in sorted(totals.items(), key=lambda kv: -kv[1])[:5]]


def pixel_avatar(url, x0, y0, size, step=7):
    with urllib.request.urlopen(url + ("&" if "?" in url else "?") + "s=120") as r:
        img = Image.open(io.BytesIO(r.read())).convert("RGB")
    n = size // step
    img = img.resize((n, n), Image.NEAREST)
    dots = []
    for j in range(n):
        for i in range(n):
            r, g, b = img.getpixel((i, j))
            cx, cy = x0 + i * step + step / 2, y0 + j * step + step / 2
            if (0.3 * r + 0.59 * g + 0.11 * b) / 255 > 0.92:
                dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="0.9" fill="#334155"/>')
            else:
                dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{step*0.42:.1f}" fill="rgb({r},{g},{b})"/>')
    return "".join(dots)


ICONS = {
    "repo": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z",
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z",
    "commit": "M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z",
    "people": "M2 5.5a3.5 3.5 0 1 1 5.898 2.549 5.508 5.508 0 0 1 3.034 4.084.75.75 0 1 1-1.482.235 4 4 0 0 0-7.9 0 .75.75 0 0 1-1.482-.236A5.507 5.507 0 0 1 3.102 8.05 3.493 3.493 0 0 1 2 5.5ZM11 4a3.001 3.001 0 0 1 2.22 5.018 5.01 5.01 0 0 1 2.56 3.012.749.749 0 0 1-.885.954.752.752 0 0 1-.549-.514 3.507 3.507 0 0 0-2.522-2.372.75.75 0 0 1-.574-.73v-.352a.75.75 0 0 1 .416-.672A1.5 1.5 0 0 0 11 5.5.75.75 0 0 1 11 4Zm-5.5-.5a2 2 0 1 0-.001 3.999A2 2 0 0 0 5.5 3.5Z",
}


def chip(x, y, label, color):
    w = 26 + len(label) * 7.2
    return (f'<rect x="{x}" y="{y}" width="{w:.0f}" height="24" rx="12" fill="{PANEL}" stroke="#334155"/>'
            f'<circle cx="{x+13}" cy="{y+12}" r="4" fill="{color}"/>'
            f'<text x="{x+22}" y="{y+16}" class="mono" font-size="11.5" fill="{TEXT}">{escape(label)}</text>'), w


def header(user, total):
    W, H = 840, 250
    stars_total = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    body = [stars(W, H, 28, 1),
            f'<text x="36" y="78" class="mono" font-size="14" fill="{ACCENT}">@{escape(user["login"])}</text>',
            f'<text x="34" y="122" class="sans" font-size="40" font-weight="800" fill="#fff" filter="url(#glow)">{escape(user["name"] or user["login"])}</text>',
            f'<text x="36" y="152" class="mono" font-size="13" fill="{MUTED}">{escape(TAGLINE)}</text>']
    x = 36
    for n, _, c in languages(user)[:4]:
        g, w = chip(x, 176, n, c)
        body.append(g)
        x += w + 8
    rows = [("repo", user["repositories"]["totalCount"], "Repositories"),
            ("star", stars_total, "Stars"),
            ("commit", f"{total:,}", "Contributions"),
            ("people", user["followers"]["totalCount"], "Followers")]
    for i, (icon, val, label) in enumerate(rows):
        y = 70 + i * 36
        body.append(f'<path d="{ICONS[icon]}" transform="translate(470 {y}) scale(1.05)" fill="{ACCENT}"/>')
        body.append(f'<text x="496" y="{y+13}" class="mono" font-size="14" fill="{TEXT}"><tspan fill="{ACCENT}" font-weight="700">{val}</tspan>  {label}</text>')
    body.append(pixel_avatar(user["avatarUrl"], 650, 46, 168))
    return window(W, H, "README.md", "".join(body))


def city(days, total):
    W, H = 840, 320
    active = sum(1 for *_, c in days if c > 0)
    busiest = max((c for *_, c in days), default=0) or 1
    body = [stars(W, H, 18, 2),
            f'<text x="36" y="72" class="mono" font-size="20" font-weight="700" fill="#fff">The city I built this year</text>',
            f'<text x="36" y="120" class="mono" font-size="12" fill="{ACCENT}" letter-spacing="1.5">CONTRIBUTIONS</text>',
            f'<text x="36" y="160" class="mono" font-size="36" font-weight="700" fill="#fff" filter="url(#glow)">{total:,}</text>',
            f'<text x="36" y="192" class="mono" font-size="13" fill="{MUTED}">{active} active days</text>',
            f'<text x="36" y="214" class="mono" font-size="13" fill="{MUTED}">Busiest day: {busiest}</text>']

    # Isometric basis: weeks run up-right, weekdays run down-right.
    ux, uy, vx, vy = 7.0, -1.7, 6.5, 5.6
    ox, oy, hmax = 330, 250, 120
    # Cap at the 95th percentile so one huge day does not flatten the skyline.
    counts = sorted(c for *_, c in days if c > 0) or [1]
    cap = counts[int(len(counts) * 0.95) - 1] if len(counts) > 1 else counts[0]

    def P(w, d, z=0):
        return (ox + w * ux + d * vx, oy + w * uy + d * vy - z)

    def poly(pts, fill, extra=""):
        return f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="{fill}"{extra}/>'

    cells = sorted(days, key=lambda c: c[0] * uy + c[1] * vy)
    cells.sort(key=lambda c: c[0] * uy + c[1] * vy)
    for wk, d, count in cells:
        base = [P(wk, d), P(wk + 1, d), P(wk + 1, d + 1), P(wk, d + 1)]
        if count == 0:
            body.append(poly(base, "#0f2a2a", ' stroke="#1b4542" stroke-width="0.5"'))
            continue
        t = min(1, count / cap)
        h = 3 + math.sqrt(t) * hmax
        a, b, c, e = P(wk, d, h), P(wk + 1, d, h), P(wk + 1, d + 1, h), P(wk, d + 1, h)
        g = int(170 + 70 * t)
        roof_extra = f' class="lit" style="animation-delay:{(wk * 0.13 + d * 0.4) % 3.2:.2f}s"' if t > 0.6 else ""
        body += [poly([base[0], base[3], e, a], f"rgb(18,{int(g*0.5)},{int(g*0.48)})"),
                 poly([base[3], base[2], c, e], f"rgb(28,{int(g*0.72)},{int(g*0.66)})"),
                 poly([a, b, c, e], f"rgb({int(80+100*t)},{g},{int(g*0.85)})", roof_extra)]
    return window(W, H, "> github-profile-3d", "".join(body))


def lang_card(user):
    W, H = 412, 260
    body = [f'<text x="24" y="70" class="mono" font-size="18" font-weight="700" fill="#fff">Language Stack</text>',
            f'<text x="24" y="90" class="mono" font-size="11" fill="{ACCENT}">Contribution-weighted technologies</text>']
    for i, (n, pct, c) in enumerate(languages(user)):
        y = 124 + i * 27
        body += [f'<circle cx="30" cy="{y-4}" r="5" fill="{c}"/>',
                 f'<text x="42" y="{y}" class="mono" font-size="12.5" fill="{TEXT}">{escape(n)}</text>',
                 f'<text x="200" y="{y}" text-anchor="end" class="mono" font-size="12" fill="{c}">{pct:.0f}%</text>',
                 f'<rect x="214" y="{y-9}" width="174" height="8" rx="4" fill="#1e293b"/>',
                 f'<rect x="214" y="{y-9}" width="{max(6, 174*pct/100):.1f}" height="8" rx="4" fill="{c}" filter="url(#glow)"/>']
    return window(W, H, "> stack.scan", "".join(body))


def ago(iso):
    d = (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    return "today" if d == 0 else f"{d}d ago" if d < 30 else f"{d // 30}mo ago"


def wrap(text, n, lines=2):
    out, cur = [], ""
    for w in (text or "").split():
        if cur and len(cur) + len(w) + 1 > n:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: n - 1] + "…"
    return out


def projects_card(user):
    W, H = 412, 260
    repos = {r["name"]: r for r in user["repositories"]["nodes"]}
    picks = [repos[p["name"]] for p in user["pinnedItems"]["nodes"] if p.get("name") in repos]
    rest = sorted((r for r in repos.values() if r["description"] and r not in picks
                   and r["name"] != user["login"] and not r["name"].endswith(".github.io")),
                  key=lambda r: r["pushedAt"], reverse=True)
    picks = (picks + rest)[:2]
    body = [f'<text x="24" y="66" class="mono" font-size="13" fill="{TEXT}">Projects.list <tspan fill="{MUTED}">./projects.sh --all</tspan></text>']
    for i, r in enumerate(picks):
        x, y, w, h = 20 + i * 190, 84, 182, 156
        lang = r["primaryLanguage"] or {"name": "Code", "color": MUTED}
        body += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{PANEL}" stroke="#1e3a5f"/>',
                 f'<circle cx="{x+14}" cy="{y+22}" r="4" fill="{readable(lang["color"])}"/>',
                 f'<text x="{x+24}" y="{y+26}" class="mono" font-size="13" font-weight="700" fill="#fff">{escape(r["name"][:18])}</text>']
        for j, line in enumerate(wrap(r["description"], 24)):
            body.append(f'<text x="{x+12}" y="{y+50+j*16}" class="mono" font-size="11" fill="{MUTED}">{escape(line)}</text>')
        tx = x + 12
        for t in ([t["topic"]["name"] for t in r["repositoryTopics"]["nodes"]] or [lang["name"]])[:2]:
            tw = 14 + len(t) * 6.6
            if tx + tw > x + w - 10:
                break
            body.append(f'<rect x="{tx}" y="{y+94}" width="{tw:.0f}" height="20" rx="6" fill="none" stroke="{GLOW}" stroke-opacity=".6"/>'
                        f'<text x="{tx+7}" y="{y+108}" class="mono" font-size="10.5" fill="{GLOW}">{escape(t)}</text>')
            tx += tw + 6
        body += [f'<path d="{ICONS["star"]}" transform="translate({x+12} {y+128}) scale(.8)" fill="{MUTED}"/>',
                 f'<text x="{x+28}" y="{y+139}" class="mono" font-size="11" fill="{MUTED}">{r["stargazerCount"]}  updated {ago(r["pushedAt"])}</text>']
    return window(W, H, "~/projects", "".join(body))


def main():
    user = fetch()
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [(wi, (datetime.fromisoformat(d["date"]).weekday() + 1) % 7, d["contributionCount"])
            for wi, w in enumerate(cal["weeks"]) for d in w["contributionDays"]]
    total = cal["totalContributions"]
    os.makedirs(OUT, exist_ok=True)
    for name, svg in [("header.svg", header(user, total)), ("city.svg", city(days, total)),
                      ("languages.svg", lang_card(user)), ("projects.svg", projects_card(user))]:
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg)


if __name__ == "__main__":
    main()
