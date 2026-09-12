#!/usr/bin/env python3
"""The web pages: the tiles, and one page per app.

The console never reads any of this: it fetches catalog.json and nothing
else. This exists so that a person who lands on the site can see what is
listed, see which repository and which release each entry came from, get the
package without owning a PSP, and so that an author whose app was left out
reads the reason instead of guessing at it.

Everything the browser loads is written here, into the site directory beside
the pictures: the style and the wave are two small files and nothing is
fetched from anywhere. A page that outlives its own CDN is the only kind
worth writing, and the console it is imitating is the whole point. Kept
apart from look.py because a page template is not catalog logic, and because
it is most of the lines.
"""
import html
import os
from datetime import datetime, timezone

STYLE = """/* The XMB, more or less: a blue wave over near-black, thin wide type, and
   icons at the size the console draws them. */
:root {
  --ink: #f2f6fb; --dim: #93a6bd; --cyan: #7fd4ff;
  --rule: rgba(255,255,255,.10);
  color-scheme: dark;
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
.shots img {
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

/* --- the files a browser cannot open, and the apps that are not here ---
   Both are footnotes: a thin rule, small monospace, and no colour that
   competes with the app itself. */
.aside { margin: 38px 4px 0; padding-top: 16px; border-top: 1px solid var(--rule); }
.aside h3 {
  margin: 0 0 6px; font-size: 12px; font-weight: 400; color: var(--dim);
  letter-spacing: .2em; text-transform: uppercase;
}
.aside p { margin: 0 0 12px; max-width: 62ch; color: var(--dim); font-size: 13px; }
.aside ul { margin: 0; padding: 0; list-style: none; }
.aside li {
  padding: 7px 0; border-top: 1px solid rgba(255,255,255,.06);
  font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .04em; word-break: break-word; color: var(--dim);
}
.aside .why { color: #e0a2a2; }

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

/* A phone is narrower than one tile plus the padding, so the grid gives up
   its fixed column and the wide letter-spacing gives up some of its width. */
@media (max-width: 480px) {
  body { padding: 0 14px 56px; }
  h1 { letter-spacing: .22em; font-size: 19px; }
  .grid { grid-template-columns: repeat(auto-fill, minmax(0, 176px)); }
  .app img, .noicon, .hero img { width: 100%; height: auto; aspect-ratio: 144 / 80; }
  .facts th { width: 96px; letter-spacing: .06em; }
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


def size(count):
    """Bytes as a person reads them, which is what a download link is for."""
    mb = count / (1024 * 1024)
    return f"{mb:.1f} MB" if mb >= 1 else f"{count / 1024:.0f} KB"


def render(catalog, apps, broken, out):
    """The whole site: the tiles, a page an app, and the two files they
    share. Called once, after look.py has written the pictures, so that the
    film and the sound can be measured where they now sit."""
    e = html.escape
    with open(os.path.join(out, "style.css"), "w", encoding="utf-8") as file:
        file.write(STYLE)
    with open(os.path.join(out, "wave.js"), "w", encoding="utf-8") as file:
        file.write(WAVE)

    tiles = []
    for app in apps:
        art = (f'<img src="{e(app["icon"])}" alt="" width="144" height="80" '
               f'loading="lazy">' if "icon" in app
               else '<div class="noicon">no icon</div>')
        tiles.append(TILE.format(art=art, id=e(app["id"]), name=e(app["name"]),
                                 author=e(app["author"])))
        with open(os.path.join(out, app["id"] + ".html"), "w",
                  encoding="utf-8") as file:
            file.write(app_page(app, out))

    when = catalog["generated"].replace("T", " ").replace("Z", " UTC")
    count = f"{len(apps)} app" + ("" if len(apps) == 1 else "s")
    body = f"""  <p class="lede">Homebrew for the PlayStation Portable, listed so that
  <a href="https://github.com/chriopter/pspdx">PSPDX</a> on the console can
  install it and say when there is a new version.</p>

  <div class="grid">
{chr(10).join(tiles)}
  </div>
{left_out(broken)}"""
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as file:
        file.write(SHELL.format(
            title="PSPDX catalog",
            status=f"<span>{count}</span><span>read {e(when)}</span>"
                   f'<span><a href="catalog.json">catalog.json</a></span>',
            body=body))


def left_out(broken):
    """What is not on the page and why. An author who reads no workflow log
    can still see, in one line, what their repository has to say differently
    before it is listed."""
    if not broken:
        return ""
    e = html.escape
    rows = []
    for label, why in broken:
        # The label is the line from the list, so it may carry the pinned tag
        # after an @, which is not part of the URL it links to.
        rows.append(f'      <li><a href="{e(label.split("@")[0])}">{e(label)}</a>'
                    f'<br><span class="why">{e(why)}</span></li>')
    return f"""
  <section class="aside">
    <h3>Left out</h3>
    <p>On the list, and not in the catalog. Every one of these is a
    repository saying nothing, or saying something the format does not
    allow.</p>
    <ul>
{chr(10).join(rows)}
    </ul>
  </section>
"""


def app_page(app, out):
    """One app, as the person who has no console sees it: the icon at the
    size the XMB draws it, the picture out of the EBOOT, what the release
    says about itself, and the zip."""
    e = html.escape
    release = app["release"]
    icon = (f'<img src="{e(app["icon"])}" alt="" width="144" height="80">'
            if "icon" in app else "")
    about = " &middot; ".join(x for x in (f'by {e(app["author"])}',
                                          e(app["category"]),
                                          e(app["license"])) if x)

    shots = ""
    if "screenshot" in app:
        shots = (f'\n  <div class="shots">\n'
                 f'    <img src="{e(app["screenshot"])}" alt="{e(app["name"])} '
                 f'running" loading="lazy">\n  </div>\n')

    # The film is an ICON1.PMF and the loop a SND0.AT3: Sony's own formats,
    # which no browser plays, so they are linked as files rather than dressed
    # up in a player that would show a broken frame.
    files = []
    if "video" in app:
        files.append(("The film the XMB plays behind the icon, an ICON1.PMF "
                      "video, which plays on the console and in PPSSPP.",
                      app["video"]))
    if "sound" in app:
        files.append(("The loop under it, a SND0.AT3, which is ATRAC3 and "
                      "opens in the same places.", app["sound"]))
    aside = ""
    if files:
        rows = []
        for what, path in files:
            bytes_ = os.path.getsize(os.path.join(out, path))
            rows.append(f'      <li>{what}<br>'
                        f'<a href="{e(path)}">{e(path)}</a>, {size(bytes_)}</li>')
        aside = f"""
  <section class="aside">
    <h3>Out of the EBOOT</h3>
    <ul>
{chr(10).join(rows)}
    </ul>
  </section>
"""

    published = datetime.fromtimestamp(release["rev"],
                                       timezone.utc).strftime("%Y-%m-%d")
    rows = [("version", f'{e(release["version"])}, published {published}'),
            ("id", e(app["id"])),
            ("installs to", e(app["installdir"])),
            ("repository", f'<a href="{e(app["repo"])}">{e(app["repo"])}</a>'),
            ("release", f'<a href="{e(app["_page"])}">{e(app["_page"])}</a>'),
            ("sha256", e(release["sha256"])),
            ("size", f'{release["size"]} bytes, {size(release["size"])}')]
    facts = "\n".join(f"    <tr><th>{key}</th><td>{value}</td></tr>"
                      for key, value in rows)

    body = f"""  <div class="hero">
    {icon}
    <div>
      <h2>{e(app["name"])}</h2>
      <div class="who">{about}</div>
      <p>{e(app["summary"])}</p>
    </div>
  </div>
{shots}
  <table class="facts">
{facts}
  </table>

  <a class="get" href="{e(release["url"])}">Get the zip &middot; {size(release["size"])}</a>
{aside}"""
    return SHELL.format(
        title=f'{e(app["name"])} - PSPDX catalog',
        status=f'<span>{e(release["version"])}</span>'
               f'<span><a href="./">all apps</a></span>',
        body=body)
