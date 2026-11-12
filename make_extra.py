#!/usr/bin/env python3
"""
Extra profile blocks in the same style as stats.svg (reuses helpers from make_stats.py).

Writes:
    repos.svg     top repositories + latest releases
    activity.svg  recent public activity
    wakatime.svg  coding time last 7 days (only if WAKATIME_API_KEY is set)

Usage:
    GH_TOKEN=<token> [WAKATIME_API_KEY=<key>] python3 make_extra.py
    python3 make_extra.py --demo      -> writes *-demo.svg with sample data
Env:
    GH_LOGIN  GitHub username (default from make_stats.py)
    TZ_NAME   timezone for the "updated" stamp (default Europe/Kyiv)
"""
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from make_stats import (BG, DIM, LANG_COLORS, LINE, LOGIN, MID, NAME, ORANGE, W, WHITE,
                        font_faces, gql, panel)

TZ = ZoneInfo(os.environ.get("TZ_NAME", "Europe/Kyiv"))
HEAT = [LINE, "#7a2a10", "#b83810", ORANGE, "#ff9a70"]

Q = """
query($login:String!,$id:ID!){
  user(login:$login){
    pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{name}}}
    repositories(first:60,ownerAffiliations:OWNER,isFork:false,orderBy:{field:PUSHED_AT,direction:DESC}){
      nodes{
        name description stargazerCount forkCount createdAt isPrivate
        primaryLanguage{name}
        releases(first:1,orderBy:{field:CREATED_AT,direction:DESC}){nodes{name tagName publishedAt}}
        defaultBranchRef{target{... on Commit{history(first:100,author:{id:$id}){nodes{committedDate}}}}}
      }
    }
  }
}
"""


def http_json(url, headers):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats", **headers})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch(token):
    uid = gql("query($l:String!){user(login:$l){id}}", {"l": LOGIN}, token)["user"]["id"]
    u = gql(Q, {"login": LOGIN, "id": uid}, token)["user"]
    all_repos = u["repositories"]["nodes"]
    repos = [r for r in all_repos if not r["isPrivate"] and r["name"] != LOGIN]  # private repos stay out of public cards
    pinned = [p["name"] for p in u["pinnedItems"]["nodes"] if p]
    top = [r for n in pinned for r in repos if r["name"] == n]
    if len(top) < 4:
        rest = sorted((r for r in repos if r not in top), key=lambda r: -r["stargazerCount"])
        top += rest[:4 - len(top)]
    commits = []  # time-of-day only, so private repos are safe to include
    for r in all_repos:
        t = (r.get("defaultBranchRef") or {}).get("target") or {}
        commits += [c["committedDate"] for c in (t.get("history") or {}).get("nodes", [])]
    rel = []
    for r in repos:
        for x in r["releases"]["nodes"]:
            rel.append((x["publishedAt"], r["name"], x["name"] or x["tagName"]))
    rel.sort(reverse=True)
    ev = http_json(f"https://api.github.com/users/{LOGIN}/events/public?per_page=100",
                   {"Authorization": f"bearer {token}"})
    return {"top": top[:4], "releases": rel[:3], "commits": commits, "repos": repos, "events": ev}


def demo():
    import random
    rnd = random.Random(1)
    commits = [datetime(2026, 1 + rnd.randrange(10), 1 + rnd.randrange(27), rnd.choice([9, 10, 14, 15, 16, 20, 21, 22, 23]),
                        0, tzinfo=timezone.utc).isoformat() for _ in range(300)]
    top = [{"name": f"project-{i}", "description": "Sample repository description that is a bit long to test truncation",
            "stargazerCount": i, "forkCount": i // 2, "primaryLanguage": {"name": l}}
           for i, l in enumerate(["C++", "Python", "JavaScript", "CMake"])]
    repos = [{"createdAt": f"{y}-03-01T00:00:00Z", "primaryLanguage": {"name": l}}
             for y, l in [(2023, "C++"), (2024, "C++"), (2024, "Python"), (2025, "Python"), (2025, "C++"), (2026, "JavaScript"), (2026, "Python")]]
    ev = [{"type": "PushEvent", "repo": {"name": f"{LOGIN}/project-1"}, "payload": {"size": 3},
           "created_at": "2026-11-11T10:00:00Z"},
          {"type": "PullRequestEvent", "repo": {"name": "org/lib"}, "payload": {"action": "opened"},
           "created_at": "2026-11-10T10:00:00Z"}]
    return {"top": top, "releases": [("2026-10-01T00:00:00Z", "project-1", "v1.2.0")], "commits": commits,
            "repos": repos, "events": ev}


# ---------- svg helpers ----------
def trunc(s, n):
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def ago(iso):
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    d = datetime.now(timezone.utc) - t
    if d.days >= 30:
        return f"{d.days // 30}mo ago"
    if d.days:
        return f"{d.days}d ago"
    if d.seconds >= 3600:
        return f"{d.seconds // 3600}h ago"
    return f"{max(1, d.seconds // 60)}m ago"


def wrap(body, h, label, out):
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")
    body = (f'<rect width="{W}" height="{h}" rx="12" fill="{BG}"/>' + "".join(body)
            + f'<text x="{W - 24}" y="{h - 10}" font-size="10" fill="{DIM}" text-anchor="end">updated {stamp}</text>'
            + f'<rect width="{W}" height="{h}" rx="12" fill="url(#dots)" pointer-events="none"/>')
    css = (font_faces()
           + "text{font-family:JB,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-weight:500;white-space:pre;font-variant-ligatures:none}"
           + ".a{animation:in .55s cubic-bezier(.2,.7,.2,1) both}"
           + "@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
           + ".dr{stroke-dasharray:1;animation:dr .9s cubic-bezier(.65,0,.35,1) .25s both}"
           + "@keyframes dr{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" '
           f'aria-label="{escape(label)}"><title>{escape(label)}</title>'
           f'<defs><pattern id="dots" width="6" height="6" patternUnits="userSpaceOnUse">'
           f'<circle cx="3" cy="3" r=".6" fill="#ffffff" opacity=".07"/></pattern></defs>'
           f"<style>{css}</style>{body}</svg>")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out} ({len(svg) / 1024:.0f} KB)")


def text(x, y, s, size=12, fill=MID, weight=None, anchor=None, delay=None):
    w = f' font-weight="{weight}"' if weight else ""
    an = f' text-anchor="{anchor}"' if anchor else ""
    t = f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}"{w}{an}>{escape(str(s))}</text>'
    return f'<g class="a" style="animation-delay:{delay:.2f}s">{t}</g>' if delay is not None else t


def bullet(y, delay):
    return (f'<g class="a" style="animation-delay:{delay:.2f}s">'
            f'<rect x="42" y="{y - 10}" width="3" height="12" rx="1.5" fill="{ORANGE}"/></g>')


# ---------- blocks ----------
def build_repos(d, out):
    body = []
    n_rel = len(d["releases"])
    h = 34 + 2 * 96 + (24 + 26 * n_rel + 20 if n_rel else 0) + 20
    cw, ch = 391, 84
    for i, r in enumerate(d["top"]):
        x, y = 24 + (i % 2) * (cw + 16), 34 + (i // 2) * 96
        body.append(panel(x, y, cw, ch, trunc(r["name"], 28), i))
        dl = 0.5 + i * 0.1
        body.append(text(x + 18, y + 32, trunc(r["description"] or "No description", 48), 12, MID, delay=dl))
        lang = (r.get("primaryLanguage") or {}).get("name", "-")
        body.append(f'<g class="a" style="animation-delay:{dl + .1:.2f}s"><circle cx="{x + 22}" cy="{y + 60}" r="4" fill="{ORANGE}"/></g>')
        body.append(text(x + 34, y + 64, lang, 12, WHITE, delay=dl + .1))
        body.append(text(x + cw - 18, y + 64, f"★ {r['stargazerCount']}   ⑂ {r['forkCount']}", 12, WHITE, 700, "end", dl + .1))
    if n_rel:
        y0 = 34 + 2 * 96
        body.append(panel(24, y0, 798, 24 + 26 * n_rel, "latest releases", 4))
        for i, (when, repo, name) in enumerate(d["releases"]):
            y = y0 + 34 + i * 26
            dl = .9 + i * .08
            body.append(bullet(y, dl))
            body.append(text(54, y, f"{trunc(repo, 30)} {trunc(name, 40)}", 13, WHITE, delay=dl))
            body.append(text(804, y, ago(when), 12, DIM, anchor="end", delay=dl))
    wrap(body, h, f"Top repositories of {NAME}", out)


def describe(e):
    t, p, repo = e["type"], e.get("payload", {}), e["repo"]["name"].split("/")[-1]
    if t == "PushEvent":
        n = p.get("size", 0) or len(p.get("commits", []))
        return f"pushed {n} commit{'s' if n != 1 else ''} to {repo}"
    if t == "PullRequestEvent":
        a = "merged" if p.get("pull_request", {}).get("merged") else p.get("action", "updated")
        return f"{a} a pull request in {repo}"
    if t == "IssuesEvent":
        return f"{p.get('action', 'updated')} an issue in {repo}"
    if t == "CreateEvent":
        return f"created {p.get('ref_type', 'repository')} in {repo}"
    if t == "WatchEvent":
        return f"starred {repo}"
    if t == "ForkEvent":
        return f"forked {repo}"
    if t == "ReleaseEvent":
        return f"published a release in {repo}"
    return None


def build_activity(d, out):
    items = [(describe(e), e["created_at"]) for e in d["events"]]
    items = [(s, t) for s, t in items if s][:7]
    ph = 30 + 26 * max(len(items), 1)
    body = [panel(24, 34, 798, ph, "recent activity", 0)]
    if not items:
        body.append(text(42, 76, "no public activity yet", 13, DIM, delay=.5))
    for i, (s, t) in enumerate(items):
        y = 34 + 38 + i * 26
        dl = .5 + i * .08
        body.append(bullet(y, dl))
        body.append(text(54, y, trunc(s, 78), 13, WHITE, delay=dl))
        body.append(text(804, y, ago(t), 12, DIM, anchor="end", delay=dl))
    wrap(body, 34 + ph + 34, f"Recent activity of {NAME}", out)


def build_wakatime(key, out):
    auth = base64.b64encode(key.encode()).decode()
    s = http_json("https://wakatime.com/api/v1/users/current/stats/last_7_days", {"Authorization": f"Basic {auth}"})["data"]
    langs = s.get("languages", [])[:5]
    eds = s.get("editors", [])[:3]
    ph = 130 + 24 * len(langs) - 34 + 20
    body = [panel(24, 34, 798, ph, "wakatime / last 7 days", 0)]
    body.append(text(42, 80, s.get("human_readable_total", "-"), 24, WHITE, 700, delay=.5))
    body.append(text(42, 100, f"daily avg {s.get('human_readable_daily_average', '-')}", 12, DIM, delay=.55))
    for i, l in enumerate(langs):
        y = 124 + i * 24
        dl = .6 + i * .06
        body.append(text(42, y + 10, trunc(l["name"], 14), 12, MID, delay=dl))
        body.append(f'<g class="a" style="animation-delay:{dl:.2f}s"><rect x="170" y="{y}" width="{max(3, 4.2 * l["percent"]):.1f}" height="12" rx="3" fill="{LANG_COLORS[i]}"/></g>')
        body.append(text(180 + 4.2 * l["percent"], y + 10, f"{l['text']}  {l['percent']:.0f}%", 11, DIM, delay=dl))
    if eds:
        body.append(text(804, 80, "editors: " + ", ".join(e["name"] for e in eds), 12, MID, anchor="end", delay=.6))
    wrap(body, 34 + ph + 34, f"WakaTime stats of {NAME}", out)


def main():
    suffix = "-demo" if "--demo" in sys.argv else ""
    if suffix:
        d = demo()
    else:
        token = os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("set GH_TOKEN (or run with --demo)")
        d = fetch(token)
    build_repos(d, f"repos{suffix}.svg")
    build_activity(d, f"activity{suffix}.svg")
    key = os.environ.get("WAKATIME_API_KEY")
    if key and not suffix:
        try:
            build_wakatime(key, "wakatime.svg")
        except Exception as e:  # optional block: never fail the whole run
            print(f"wakatime skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
