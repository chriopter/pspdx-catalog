#!/usr/bin/env python3
"""The web pages: the tiles, and one page per app.

The console never reads any of this -- it fetches catalog.json and nothing
else. This exists so that a person who lands on the site can see what is
listed, watch the clip, and get the file without owning a PSP.

Kept apart from build.py because a page template is not catalog logic, and
because it is most of the lines.
"""
import html
from datetime import datetime, timezone

STYLE = """/* The XMB, more or less: a blue wave over near-black, thin wide type, and
   icons at the size the console draws them. */
:root {
  --ink: #f2f6fb; --dim: #93a6bd; --cyan: #7fd4ff;
  --rule: rgba(255,255,255,.10);
}
* { box-sizing: border-box; }
html { background: #04070d; }
body {
  margin: 0; padding: 0 20px 72px; color: var(--ink); min-height: 100vh;
  font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  background:
    radial-gradient(130% 70% at 50% -20%, #1d4478 0%, #0d1e3d 42%, #05090f 100%)
    no-repeat, #04070d;
  -webkit-font-smoothing: antialiased;
}
#wave {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  width: 100%; height: 100%; display: block;
}
.wrap { position: relative; z-index: 1; max-width: 1000px; margin: 0 auto; }

header {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 16px; flex-wrap: wrap;
  padding: 34px 4px 14px; border-bottom: 1px solid var(--rule);
}
h1 {
  margin: 0; font-size: 22px; font-weight: 300; letter-spacing: .38em;
  text-transform: uppercase;
}
h1 b { font-weight: 600; letter-spacing: .3em; }
h1 a { color: inherit; text-decoration: none; }
.status {
  font: 11px ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .16em; text-transform: uppercase; color: var(--dim);
  display: flex; gap: 16px; flex-wrap: wrap;
}
.lede { margin: 22px 4px 30px; max-width: 62ch; color: var(--dim); font-weight: 300; }
a { color: var(--cyan); }

/* --- the tiles --- */
.grid { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, 176px); }
.app {
  display: block; text-decoration: none; color: inherit;
  padding: 16px 16px 14px; border-radius: 4px;
  background: rgba(255,255,255,.035);
  border: 1px solid rgba(255,255,255,.07);
  transition: background .18s ease, transform .18s ease, border-color .18s ease;
}
.app:hover {
  background: rgba(255,255,255,.09); border-color: rgba(127,212,255,.45);
  transform: translateY(-2px);
}
.app img, .noicon { width: 144px; height: 80px; display: block;
  box-shadow: 0 8px 18px rgba(0,0,0,.55); }
.noicon {
  display: grid; place-items: center; color: var(--dim); box-shadow: none;
  border: 1px dashed var(--rule);
  font: 10px ui-monospace, monospace; letter-spacing: .18em;
}
.name { margin-top: 12px; font-size: 13.5px; line-height: 1.3; }
.app:hover .name { color: var(--cyan); }
.by {
  margin-top: 3px;
  font: 11px ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .08em; color: var(--dim);
}

/* --- one app --- */
.hero { display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap;
  padding: 30px 4px 24px; }
.hero img { width: 144px; height: 80px; box-shadow: 0 10px 22px rgba(0,0,0,.55); }
.hero h2 { margin: 0 0 4px; font-size: 26px; font-weight: 400; letter-spacing: -.01em; }
.hero .who { color: var(--dim); font-size: 13px; }
.hero p { margin: 12px 0 0; max-width: 56ch; color: var(--dim); font-weight: 300; }
.shots { display: flex; gap: 16px; flex-wrap: wrap; padding: 8px 4px 26px; }
.shots img, .shots video {
  width: 480px; max-width: 100%; height: auto; display: block;
  box-shadow: 0 12px 30px rgba(0,0,0,.6); background: #000;
}
.facts {
  width: 100%; border-collapse: collapse; margin: 0 4px;
  font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
}
.facts th, .facts td {
  text-align: left; padding: 9px 0; border-top: 1px solid var(--rule);
  vertical-align: top;
}
.facts th { width: 150px; font-weight: 400; color: var(--dim);
  letter-spacing: .12em; text-transform: uppercase; }
.facts td { word-break: break-all; }
.get {
  display: inline-block; margin: 26px 4px 0; padding: 11px 22px;
  border: 1px solid rgba(127,212,255,.5); border-radius: 3px;
  color: var(--cyan); text-decoration: none;
  font: 12px ui-monospace, monospace; letter-spacing: .16em; text-transform: uppercase;
}
.get:hover { background: rgba(127,212,255,.12); }

footer {
  margin-top: 40px; padding: 14px 4px 0; border-top: 1px solid var(--rule);
  display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  font: 11px ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .14em; text-transform: uppercase; color: var(--dim);
}
.glyph {
  display: inline-grid; place-items: center; width: 15px; height: 15px;
  border: 1px solid currentColor; border-radius: 50%; font-size: 9px;
  vertical-align: -3px; margin-right: 5px;
}
"""

WAVE = """/* The XMB wave: bands of offset sine curves drifting past each other. Hand
   written, because the console it is imitating is the whole point and a
   dependency would outlive its own CDN. */
(function () {
  var c = document.getElementById("wave"), x = c.getContext("2d");
  var still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var w, h, t = 0;

  function size() { w = c.width = innerWidth; h = c.height = innerHeight; }

  function band(mid, amp, freq, phase, lines, alpha) {
    for (var i = 0; i < lines; i++) {
      var lift = (i - lines / 2) * (amp * 0.13);
      x.beginPath();
      for (var px = 0; px <= w; px += 8) {
        var u = px / w;
        var y = mid + lift
              + Math.sin(u * freq + phase + i * 0.10) * amp
              + Math.sin(u * freq * 2.7 + phase * 1.6) * amp * 0.28;
        px ? x.lineTo(px, y) : x.moveTo(px, y);
      }
      x.strokeStyle = "rgba(158,214,255," +
        (alpha * (1 - Math.abs(i - lines / 2) / lines)) + ")";
      x.lineWidth = 1;
      x.stroke();
    }
  }

  function frame() {
    x.clearRect(0, 0, w, h);
    band(h * 0.42, h * 0.075, 4.2, t, 16, 0.30);
    band(h * 0.56, h * 0.055, 5.6, t * 0.7 + 2, 12, 0.20);
    band(h * 0.70, h * 0.045, 3.4, -t * 0.5, 10, 0.13);
    if (!still) { t += 0.004; requestAnimationFrame(frame); }
  }

  addEventListener("resize", function () { size(); if (still) frame(); });
  size();
  frame();
})();
"""

SHELL = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="style.css">
<canvas id="wave" aria-hidden="true"></canvas>
<div class="wrap">
  <header>
    <h1><a href="./"><b>PSPDX</b> catalog</a></h1>
    <div class="status">{status}</div>
  </header>
{body}
  <footer>
    <span><span class="glyph">&#10005;</span>every download comes from its author&#39;s release</span>
    <span><a href="https://github.com/chriopter/pspdx-catalog">add an app</a></span>
  </footer>
</div>
<script src="wave.js"></script>
"""

TILE = """    <a class="app" href="{id}.html">
      {art}
      <div class="name">{name}</div>
      <div class="by">{author}</div>
    </a>"""


def render(apps, out):
    """Writes the tiles, one page per app, and the two files they share."""
    e = html.escape
    (out / "style.css").write_text(STYLE, encoding="utf-8")
    (out / "wave.js").write_text(WAVE, encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    tiles = []
    for a in apps:
        art = (f'<img src="{e(a["icon"])}" alt="" loading="lazy">'
               if "icon" in a else '<div class="noicon">no icon</div>')
        tiles.append(TILE.format(art=art, id=e(a["id"]), name=e(a["name"]),
                                 author=e(a["author"])))
        (out / (a["id"] + ".html")).write_text(app_page(a), encoding="utf-8")

    body = f'''  <p class="lede">Homebrew for the PlayStation Portable, listed so that
  <a href="https://github.com/chriopter/pspdx">PSPDX</a> on the console can
  install it and tell you when there is a new version.</p>

  <div class="grid">
{chr(10).join(tiles)}
  </div>
'''
    (out / "index.html").write_text(SHELL.format(
        title="PSPDX catalog",
        status=f"<span>{len(apps)} apps</span><span>checked {now}</span>"
               f'<span><a href="catalog.json">catalog.json</a></span>',
        body=body), encoding="utf-8")


def app_page(a):
    e = html.escape
    r = a["release"]
    icon = f'<img src="{e(a["icon"])}" alt="">' if "icon" in a else ""
    media = []
    if "screenshot" in a:
        media.append(f'<img src="{e(a["screenshot"])}" alt="A screenshot of '
                     f'{e(a["name"])} running">')
    if "video" in a:
        poster = f' poster="{e(a["screenshot"])}"' if "screenshot" in a else ""
        media.append(f'<video src="{e(a["video"])}"{poster} controls '
                     f'preload="none" playsinline></video>')

    when = datetime.fromtimestamp(r["rev"], timezone.utc).strftime("%Y-%m-%d")
    mb = r["size"] / (1024 * 1024)
    size = f"{mb:.1f} MB" if mb >= 1 else f"{r['size'] / 1024:.0f} KB"

    body = f'''  <div class="hero">
    {icon}
    <div>
      <h2>{e(a["name"])}</h2>
      <div class="who">by {e(a["author"])}</div>
      <p>{e(a["summary"])}</p>
    </div>
  </div>

  <div class="shots">
{chr(10).join("    " + m for m in media)}
  </div>

  <table class="facts">
    <tr><th>version</th><td>{e(r.get("version", ""))}, published {when}</td></tr>
    <tr><th>download</th><td>{size}</td></tr>
    <tr><th>sha256</th><td>{e(r["sha256"])}</td></tr>
    <tr><th>category</th><td>{e(a["category"])}</td></tr>
    <tr><th>licence</th><td>{e(a["license"])}</td></tr>
    <tr><th>source</th><td><a href="{e(a["repo"])}">{e(a["repo"])}</a></td></tr>
    <tr><th>id</th><td>{e(a["id"])}</td></tr>
  </table>

  <a class="get" href="{e(r["url"])}">Download</a>
'''
    return SHELL.format(title=f'{e(a["name"])} — PSPDX',
                        status=f'<span>{e(a["category"])}</span>'
                               f'<span>{e(a["license"])}</span>'
                               f'<span><a href="./">all apps</a></span>',
                        body=body)
