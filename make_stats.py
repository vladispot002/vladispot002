#!/usr/bin/env python3
"""
Generates stats.svg for a GitHub profile README in the same style as hero.svg:
stats card, contribution streaks and most used languages.
Data comes from the GitHub GraphQL API (standard library only, no dependencies).

Usage:
    GH_TOKEN=<token> python3 make_stats.py      -> writes stats.svg and graph.svg
    python3 make_stats.py --demo                -> writes stats-demo.svg and graph-demo.svg with sample numbers
Env:
    GH_TOKEN   token for the API (in GitHub Actions: secrets.GITHUB_TOKEN or a PAT with read:user)
    GH_LOGIN   GitHub username (default below)
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from xml.sax.saxutils import escape

LOGIN = os.environ.get("GH_LOGIN", "vladispot002")
NAME = "Vladyslav Potapov"
TOP_LANGS = 6

ORANGE = "#ff4500"
BG, LINE, DIM, MID, WHITE = "#0e0d11", "#2c2b36", "#6e6c7a", "#a9a7b8", "#f1f0f7"
LANG_COLORS = ["#ff4500", "#ff6a33", "#ff8c5a", "#ffa882", "#ffc2a6", "#ffdccb"]
W, H = 846, 360
GH = 266
API = "https://api.github.com/graphql"

Q_MAIN = """
query($login:String!){
  user(login:$login){
    name createdAt
    followers{totalCount}
    pullRequests{totalCount}
    issues{totalCount}
    repositoriesContributedTo(first:1,contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY]){totalCount}
    contributionsCollection{
      contributionYears
      totalCommitContributions
      totalPullRequestReviewContributions
    }
    repositories(first:100,ownerAffiliations:OWNER,isFork:false){
      nodes{
        stargazerCount
        languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}
      }
    }
  }
}
"""
Q_YEAR = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from,to:$to){
      contributionCalendar{weeks{contributionDays{date contributionCount}}}
    }
  }
}
"""


def gql(query, variables, token, retries=4):
    body = json.dumps({"query": query, "variables": variables}).encode()
    headers = {"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-stats"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(API, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            code = getattr(e, "code", None)
            # retry on network errors, 5xx and rate limiting; fail fast on other 4xx
            if attempt == retries - 1 or (code is not None and code < 500 and code not in (403, 429)):
                raise
            time.sleep(2 ** attempt * 5)
            continue
        if "errors" in data:
            raise SystemExit(json.dumps(data["errors"], indent=1))
        return data["data"]


def fetch(token):
    u = gql(Q_MAIN, {"login": LOGIN}, token)["user"]
    cc = u["contributionsCollection"]
    days = {}
    for y in cc["contributionYears"]:
        v = {"login": LOGIN, "from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"}
        cal = gql(Q_YEAR, v, token)["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    langs = {}
    stars = 0
    for repo in u["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])
    top = [(n, s * 100 / total) for n, s in top]
    return {
        "stars": stars, "commits": cc["totalCommitContributions"], "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"], "contrib": u["repositoriesContributedTo"]["totalCount"],
        "reviews": cc["totalPullRequestReviewContributions"], "followers": u["followers"]["totalCount"],
        "langs": top, "days": days,
    }


def demo():
    days = {}
    d0 = date.today() - timedelta(days=400)
    for i in range(401):
        d = d0 + timedelta(days=i)
        r = (i * 2654435761 % 2 ** 32) / 2 ** 32
        days[d.isoformat()] = 0 if r < 0.45 or i < 120 else int(r * r * 14) + 1
    return {
        "stars": 3, "commits": 126, "prs": 4, "issues": 1, "contrib": 2, "reviews": 0, "followers": 2,
        "langs": [("C++", 61.4), ("Python", 24.9), ("JavaScript", 7.3), ("CMake", 3.9), ("HTML", 1.7), ("CSS", 0.8)],
        "days": days,
    }


def streaks(days):
    seq = sorted((date.fromisoformat(k), v) for k, v in days.items())
    seq = [x for x in seq if x[0] <= date.today()]
    total = sum(v for _, v in seq)
    first = next((d for d, v in seq if v > 0), None)
    best, best_rng, run, start = 0, None, 0, None
    for d, v in seq:
        if v > 0:
            if run == 0:
                start = d
            run += 1
            if run > best:
                best, best_rng = run, (start, d)
        else:
            run = 0
    i = len(seq) - 1
    if i >= 0 and seq[i][1] == 0:
        i -= 1
    cur, cur_end = 0, None
    while i >= 0 and seq[i][1] > 0:
        cur_end = cur_end or seq[i][0]
        cur += 1
        i -= 1
    cur_rng = (seq[i + 1][0], cur_end) if cur else None
    return total, first, cur, cur_rng, best, best_rng


def fmt(d):
    return f"{d:%b} {d.day}"


def fmt_rng(rng):
    if not rng:
        return "-"
    a, b = rng
    return fmt(a) if a == b else f"{fmt(a)} - {fmt(b)}"


def grade(d):
    ex = lambda x: 1 - 2 ** -x
    ln = lambda x: x / (1 + x)
    r = 1 - (2 * ex(d["commits"] / 250) + 3 * ex(d["prs"] / 50) + 1 * ex(d["issues"] / 25)
             + 1 * ex(d["reviews"] / 2) + 4 * ln(d["stars"] / 50) + 1 * ln(d["followers"] / 10)) / 12
    pct = r * 100
    for t, lv in zip([1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100], ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]):
        if pct <= t:
            return lv, (100 - pct) / 100
    return "C", 0.0


def font_faces():
    here = os.path.dirname(os.path.abspath(__file__))
    css = ""
    for weight in (500, 700):
        path = os.path.join(here, "fonts", f"jetbrains-mono-latin-{weight}-normal.woff2")
        if os.path.exists(path):
            b64 = base64.b64encode(open(path, "rb").read()).decode()
            css += f"@font-face{{font-family:JB;font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
    return css


def ring(cx, cy, r, frac, sw=5):
    frac = max(0.03, min(1.0, frac))
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{LINE}" stroke-width="{sw}"/>'
            f'<circle class="rg" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ORANGE}" stroke-width="{sw}" '
            f'stroke-linecap="round" pathLength="1" stroke-dasharray="1" '
            f'style="stroke-dashoffset:{1 - frac:.4f}" transform="rotate(-90 {cx} {cy})"/>')


def panel(x, y, w, h, tag, idx):
    tw = len(tag) * 13 * 0.6 + 16
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="none" stroke="{ORANGE}" stroke-width="1.4" '
            f'pathLength="1" class="dr"/>'
            f'<g class="a" style="animation-delay:{0.3 + idx * 0.12:.2f}s"><rect x="{x + 14}" y="{y - 8}" width="{tw:.1f}" '
            f'height="16" fill="{BG}"/><text x="{x + 22}" y="{y + 4.5}" font-size="13" fill="{ORANGE}">{escape(tag)}</text></g>')


def build(d, out):
    total, first, cur, cur_rng, best, best_rng = streaks(d["days"])
    lv, frac = grade(d)
    body = [f'<rect width="{W}" height="{H}" rx="12" fill="{BG}"/>']

    ax, ay, aw, ah = 24, 34, 372, 176
    body.append(panel(ax, ay, aw, ah, f"{LOGIN} / stats", 0))
    rows = [("Total Stars Earned", d["stars"]), ("Total Commits (last year)", d["commits"]),
            ("Total PRs", d["prs"]), ("Total Issues", d["issues"]), ("Contributed to", d["contrib"])]
    for i, (k, v) in enumerate(rows):
        y = ay + 46 + i * 26
        body.append(f'<g class="a" style="animation-delay:{0.5 + i * 0.08:.2f}s">'
                    f'<rect x="{ax + 18}" y="{y - 10}" width="3" height="12" rx="1.5" fill="{ORANGE}"/>'
                    f'<text x="{ax + 30}" y="{y}" font-size="13" fill="{MID}">{escape(k)}</text>'
                    f'<text x="{ax + 262}" y="{y}" font-size="13" font-weight="700" fill="{WHITE}" text-anchor="end">{v}</text></g>')
    rcx, rcy = ax + 318, ay + 90
    body.append(ring(rcx, rcy, 32, frac))
    body.append(f'<text x="{rcx}" y="{rcy + 8}" font-size="22" font-weight="700" fill="{WHITE}" text-anchor="middle">{lv}</text>')

    bx, by, bw, bh = 408, 34, 414, 176
    body.append(panel(bx, by, bw, bh, "streak", 1))
    cols = [bx + bw * (2 * i + 1) / 6 for i in range(3)]
    for xd in (bx + bw / 3, bx + 2 * bw / 3):
        body.append(f'<path d="M{xd:.1f} {by + 28}V{by + bh - 24}" stroke="{LINE}" stroke-width="1.2"/>')
    first_txt = f"since {fmt(first)}, {first.year}" if first else "-"
    body.append(f'<g class="a" style="animation-delay:.7s"><text x="{cols[0]:.1f}" y="{by + 88}" font-size="30" font-weight="700" '
                f'fill="{WHITE}" text-anchor="middle">{total}</text>'
                f'<text x="{cols[0]:.1f}" y="{by + 136}" font-size="13" fill="{MID}" text-anchor="middle">Contributions</text>'
                f'<text x="{cols[0]:.1f}" y="{by + 158}" font-size="11" fill="{DIM}" text-anchor="middle">{escape(first_txt)}</text></g>')
    body.append(ring(round(cols[1], 1), by + 76, 32, 1.0 if cur else 0.0))
    body.append(f'<g class="a" style="animation-delay:.8s"><text x="{cols[1]:.1f}" y="{by + 86}" font-size="26" font-weight="700" '
                f'fill="{WHITE}" text-anchor="middle">{cur}</text>'
                f'<text x="{cols[1]:.1f}" y="{by + 136}" font-size="13" font-weight="700" fill="{ORANGE}" text-anchor="middle">Current Streak</text>'
                f'<text x="{cols[1]:.1f}" y="{by + 158}" font-size="11" fill="{DIM}" text-anchor="middle">{escape(fmt_rng(cur_rng))}</text></g>')
    body.append(f'<g class="a" style="animation-delay:.9s"><text x="{cols[2]:.1f}" y="{by + 88}" font-size="30" font-weight="700" '
                f'fill="{WHITE}" text-anchor="middle">{best}</text>'
                f'<text x="{cols[2]:.1f}" y="{by + 136}" font-size="13" fill="{MID}" text-anchor="middle">Longest Streak</text>'
                f'<text x="{cols[2]:.1f}" y="{by + 158}" font-size="11" fill="{DIM}" text-anchor="middle">{escape(fmt_rng(best_rng))}</text></g>')

    cx0, cy0, cw, ch = 24, 224, 798, 112
    body.append(panel(cx0, cy0, cw, ch, "most used languages", 2))
    langs = d["langs"][:TOP_LANGS]
    if langs:
        tot = sum(p for _, p in langs) or 1
        x0, bw2, yb = 42, 762, cy0 + 28
        body.append(f'<clipPath id="bar"><rect x="{x0}" y="{yb}" width="{bw2}" height="10" rx="5"/></clipPath>')
        segs, x = [], x0
        for i, (n, p) in enumerate(langs):
            w = bw2 * p / tot
            segs.append(f'<rect x="{x:.2f}" y="{yb}" width="{w + 0.5:.2f}" height="10" fill="{LANG_COLORS[i % len(LANG_COLORS)]}"/>')
            x += w
        body.append(f'<g clip-path="url(#bar)"><g class="grow">{"".join(segs)}</g></g>')
        for i, (n, p) in enumerate(langs):
            lx = x0 + (i % 3) * 262
            ly = cy0 + 66 + (i // 3) * 24
            body.append(f'<g class="a" style="animation-delay:{1.0 + i * 0.07:.2f}s">'
                        f'<circle cx="{lx + 4}" cy="{ly - 4}" r="4" fill="{LANG_COLORS[i % len(LANG_COLORS)]}"/>'
                        f'<text x="{lx + 16}" y="{ly}" font-size="12" fill="{MID}">{escape(n)} {p * 100 / tot:.2f}%</text></g>')

    body.append(f'<rect width="{W}" height="{H}" rx="12" fill="url(#dots)" pointer-events="none"/>')

    css = (font_faces()
           + "text{font-family:JB,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-weight:500;white-space:pre;font-variant-ligatures:none}"
           + ".a{animation:in .55s cubic-bezier(.2,.7,.2,1) both}"
           + "@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
           + ".dr{stroke-dasharray:1;animation:dr .9s cubic-bezier(.65,0,.35,1) .25s both}"
           + "@keyframes dr{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
           + ".rg{animation:rg 1.1s cubic-bezier(.4,0,.2,1) .6s both}@keyframes rg{from{stroke-dashoffset:1}}"
           + ".grow{transform-origin:42px 0;animation:gr 1s cubic-bezier(.4,0,.2,1) .8s both}"
           + "@keyframes gr{from{transform:scaleX(0)}to{transform:none}}")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="GitHub stats for {escape(NAME)}"><title>{escape(NAME)} GitHub stats</title>'
           f'<defs><pattern id="dots" width="6" height="6" patternUnits="userSpaceOnUse">'
           f'<circle cx="3" cy="3" r=".6" fill="#ffffff" opacity=".07"/></pattern></defs>'
           f"<style>{css}</style>{''.join(body)}</svg>")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out} ({len(svg) / 1024:.0f} KB)")


GRAPH_CHARS = ["·", ":", "+", "#", "@"]
GRAPH_COLORS = [LINE, "#7a2a10", "#b83810", ORANGE, "#ff9a70"]


def build_graph(d, out):
    days = {date.fromisoformat(k): v for k, v in d["days"].items()}
    today = date.today()
    sun = today - timedelta(days=(today.weekday() + 1) % 7)
    start = sun - timedelta(weeks=52)
    cols = 53
    gx, gy, step_x, step_y = 66, 82, 13.8, 17
    px, py, pw, ph = 24, 34, 798, 206
    cells, counts, months, last_m, last_c = [], [], [], None, -9
    for c in range(cols):
        first = start + timedelta(weeks=c)
        if first.month != last_m and c - last_c >= 3:
            months.append((c, f"{first:%b}"))
            last_m, last_c = first.month, c
        for r in range(7):
            dt = start + timedelta(weeks=c, days=r)
            if dt > today:
                continue
            v = days.get(dt, 0)
            counts.append((dt, v))
            cells.append((c, r, dt, v))
    mx = max([v for _, v in counts] or [1]) or 1
    lvl = lambda v: 0 if v == 0 else (1 if v <= mx * 0.25 else 2 if v <= mx * 0.5 else 3 if v <= mx * 0.75 else 4)
    total = sum(v for _, v in counts)
    best_dt, best_v = max(counts, key=lambda x: x[1]) if counts else (today, 0)

    body = [f'<rect width="{W}" height="{GH}" rx="12" fill="{BG}"/>']
    body.append(panel(px, py, pw, ph, f"{LOGIN} / commit rain", 0))
    for c, label in months:
        body.append(f'<text x="{gx + c * step_x:.1f}" y="{gy - 14}" font-size="10.5" fill="{DIM}">{label}</text>')
    for r, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body.append(f'<text x="38" y="{gy + r * step_y + 4:.1f}" font-size="10" fill="{DIM}">{label}</text>')
    body.append(f'<clipPath id="gc"><rect x="{gx - 4}" y="{gy - 12}" width="{cols * step_x + 6:.1f}" height="{7 * step_y + 8}"/></clipPath>')
    items = []
    for c, r, dt, v in cells:
        delay = c * 0.05 + r * 0.035 + ((c * 31 + r * 17) % 7) * 0.05 + 0.4
        x = gx + c * step_x + step_x / 2
        y = gy + r * step_y + 4
        l = lvl(v)
        items.append(f'<text class="c l{l}" x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-size="13" '
                     f'style="animation-delay:{delay:.2f}s">{GRAPH_CHARS[l]}</text>')
        if dt == today:
            items.append(f'<rect class="c td" x="{x - 4.2:.1f}" y="{y - 10.5:.1f}" width="8.4" height="14" fill="{WHITE}" '
                         f'style="animation-delay:{delay + 0.9:.2f}s"/>')
    body.append("".join(items))
    body.append(f'<g clip-path="url(#gc)"><rect class="sw" x="{gx - 90}" y="{gy - 12}" width="80" height="{7 * step_y + 8}" '
                f'fill="url(#sg)"/></g>')
    fy = py + ph - 18
    body.append(f'<g class="a" style="animation-delay:1.2s"><text x="42" y="{fy}" font-size="12" fill="{MID}">'
                f'{total} contributions in the last year<tspan fill="{DIM}"> · busiest day: {best_v} on {fmt(best_dt)}</tspan></text>'
                f'<text x="640" y="{fy}" font-size="11" fill="{DIM}">less</text>'
                + "".join(f'<text class="l{i}" x="{676 + i * 16}" y="{fy}" font-size="13">{GRAPH_CHARS[i]}</text>' for i in range(5))
                + f'<text x="762" y="{fy}" font-size="11" fill="{DIM}">more</text></g>')
    body.append(f'<rect width="{W}" height="{GH}" rx="12" fill="url(#dots)" pointer-events="none"/>')

    css = (font_faces()
           + "text{font-family:JB,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-weight:500;white-space:pre;font-variant-ligatures:none}"
           + ".a{animation:in .55s cubic-bezier(.2,.7,.2,1) both}"
           + "@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
           + ".dr{stroke-dasharray:1;animation:dr .9s cubic-bezier(.65,0,.35,1) .25s both}"
           + "@keyframes dr{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
           + "".join(f".l{i}{{fill:{c}}}" for i, c in enumerate(GRAPH_COLORS))
           + ".c{animation:drop 10s linear infinite both}"
           + "@keyframes drop{0%{opacity:0;transform:translateY(-52px);animation-timing-function:cubic-bezier(.5,0,1,.55)}"
             "7%{opacity:1;transform:none}91%{opacity:1;transform:none}100%{opacity:0;transform:none}}"
           + ".td{fill:#ffffff;opacity:.9}"
           + ".sw{animation:sw 4.2s linear 3.4s infinite both}"
           + f"@keyframes sw{{from{{transform:translateX(0)}}to{{transform:translateX({cols * step_x + 110:.0f}px)}}}}")
    css += ".td{animation:drop 10s linear infinite both,bl 1.05s steps(1) infinite}@keyframes bl{50%{fill:#ff4500}}"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{GH}" viewBox="0 0 {W} {GH}" role="img" '
           f'aria-label="Contribution graph for {escape(NAME)}"><title>{escape(NAME)} contributions</title>'
           f'<defs><pattern id="dots" width="6" height="6" patternUnits="userSpaceOnUse">'
           f'<circle cx="3" cy="3" r=".6" fill="#ffffff" opacity=".07"/></pattern>'
           f'<linearGradient id="sg" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="{ORANGE}" stop-opacity="0"/>'
           f'<stop offset=".7" stop-color="{ORANGE}" stop-opacity=".30"/><stop offset="1" stop-color="#ffffff" stop-opacity=".22"/></linearGradient></defs>'
           f"<style>{css}</style>{''.join(body)}</svg>")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out} ({len(svg) / 1024:.0f} KB)")


def main():
    if "--demo" in sys.argv:
        build(demo(), "stats-demo.svg")
        build_graph(demo(), "graph-demo.svg")
        return
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GH_TOKEN (or run with --demo)")
    data = fetch(token)
    build(data, "stats.svg")
    build_graph(data, "graph.svg")


if __name__ == "__main__":
    main()
