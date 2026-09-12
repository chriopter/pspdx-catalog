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
import json
import os
import struct
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
  display: flex; flex-direction: column; color: inherit;
  padding: 16px 16px 14px; border-radius: 4px;
  background: rgba(255,255,255,.035);
  border: 1px solid rgba(255,255,255,.07);
  transition: background .18s ease, transform .18s ease, border-color .18s ease;
}
.app-main { display: block; flex: 1; color: inherit; text-decoration: none; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.app .actions { gap: 6px; }
.app .get { flex: 1 0 auto; padding: 8px 4px; font-size: 10px; letter-spacing: 0; text-align: center; white-space: nowrap; }
a:focus-visible { outline: 2px solid var(--cyan); outline-offset: 4px; }
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
.hero .ident {
  margin-top: 6px; color: var(--dim);
  font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .06em;
}
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
  text-align: left; padding: 5px 0; border-top: 1px solid var(--rule);
  vertical-align: top;
}
.facts th { width: 130px; font-weight: 400; color: var(--dim);
  letter-spacing: .12em; text-transform: uppercase; }
.facts td { word-break: break-all; }
.facts .note { color: var(--dim); }
.facts .gone { color: var(--dim); }
.get {
  display: inline-block; padding: 11px 22px;
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
.aside p { margin: 0 0 10px; max-width: 62ch; color: var(--dim); font-size: 13px; }
/* The two little links on a heading line: where this group of values was
   read, and where it can be read now. */
.aside h3 a {
  margin-left: 10px; font-size: 11px; letter-spacing: .1em;
  text-transform: none; text-decoration: none; border-bottom: 1px solid rgba(127,212,255,.35);
}
.aside ul { margin: 0; padding: 0; list-style: none; }
.aside li {
  padding: 7px 0; border-top: 1px solid rgba(255,255,255,.06);
  font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .04em; word-break: break-word; color: var(--dim);
}
.aside .why { color: #e0a2a2; }
/* The table inside a section keeps the section's own gutter and adds none. */
.aside .facts { margin: 0; }
.gone { color: var(--dim); }

/* catalog.json as it is, coloured by walking it: keys in the accent, strings
   in sand, numbers in the same rose the reasons are written in. */
pre.json {
  margin: 0; padding: 14px 16px; overflow-x: auto;
  border: 1px solid var(--rule); border-radius: 4px;
  background: rgba(0,0,0,.32);
  font: 12px/1.7 ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--ink);
}
pre.json .k { color: var(--cyan); }
pre.json .s { color: #e6cf9c; }
pre.json .n { color: #e0a2a2; }
pre.json .p { color: var(--dim); }
pre.json a { color: inherit; }

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
<link rel="stylesheet" href="{base}style.css">
<canvas id="wave" aria-hidden="true"></canvas>
<div class="wrap">
  <header>
    <h1><a href="{base}"><b>PSPDX</b> catalog</a></h1>
    <div class="status">{status}</div>
  </header>
{body}
  <footer>
    <span><span class="glyph">&#10005;</span>author&#39;s release</span>
    <span><a href="https://github.com/chriopter/pspdx-catalog">catalog</a>
      &middot; <a href="https://github.com/chriopter/pspdx">client</a>
      &middot; <a href="https://github.com/chriopter/pspdx-catalog/issues">issues</a></span>
  </footer>
</div>
<script src="{base}wave.js"></script>
"""

# The detail link and external actions are siblings, never nested links.
TILE = """    <article class="app">
      <a class="app-main" href="apps/{id}/">
      {art}
      <div class="name">{name}</div>
      <div class="by">{author}</div>
      </a>
      {actions}
    </article>"""

# Where an app's own page sits, and how far it is from the root from there.
HOME = "apps/{id}/"
UP = "../../"

# What one PBP section is called on the page, and in which order the four are
# listed. The names are Sony's, because that is what they are.
ARTEFACTS = (("icon", "icon", "ICON0.PNG"),
             ("screenshot", "picture", "PIC1.PNG"),
             ("video", "film", "ICON1.PMF"),
             ("sound", "sound", "SND0.AT3"))

# What GitHub answered with where the .pspdx said nothing. Marked in one
# word beside the value, because which of the two wrote a line is the point
# of grouping them by where they came from.
INSTEAD = ("author", "summary", "license")


def size(count):
    """Bytes as a person reads them, which is what a download link is for."""
    mb = count / (1024 * 1024)
    return f"{mb:.1f} MB" if mb >= 1 else f"{count / 1024:.0f} KB"


def shine(value, depth=0):
    """One JSON value as coloured HTML, by walking what was parsed rather
    than by matching patterns in the printed text: a brace inside a summary
    is then a character in a string and can never be mistaken for syntax.
    Whatever looks like a URL is made clickable, because every URL in this
    file is one the console would fetch."""
    e = html.escape
    pad, close = "  " * (depth + 1), "  " * depth
    if isinstance(value, dict) or isinstance(value, list):
        open_, shut = ("{", "}") if isinstance(value, dict) else ("[", "]")
        if not value:
            return f'<span class="p">{open_}{shut}</span>'
        lines = []
        for item in (value.items() if isinstance(value, dict) else value):
            if isinstance(value, dict):
                key, item = item
                lines.append(f'{pad}<span class="k">"{e(key)}"</span>'
                             f'<span class="p">: </span>'
                             + shine(item, depth + 1))
            else:
                lines.append(pad + shine(item, depth + 1))
        body = '<span class="p">,</span>\n'.join(lines)
        return (f'<span class="p">{open_}</span>\n{body}\n'
                f'{close}<span class="p">{shut}</span>')
    if isinstance(value, str):
        # json.dumps writes the quotes and the escapes a JSON string needs;
        # html.escape then makes the result safe to put in a page.
        text = e(json.dumps(value, ensure_ascii=False))
        if value.startswith("https://") or value.startswith("http://"):
            return f'<span class="s"><a href="{e(value)}">{text}</a></span>'
        return f'<span class="s">{text}</span>'
    if value is None or isinstance(value, bool):
        return f'<span class="n">{json.dumps(value)}</span>'
    return f'<span class="n">{e(json.dumps(value))}</span>'


def plain(app):
    """The entry as the console reads it: everything the catalog carries,
    minus the notes this file keeps for itself."""
    return {key: value for key, value in app.items() if not key.startswith("_")}


def bar(base, *bits):
    """The line at the top right: a few marks, not a sentence. The catalog is
    two small links, the braces for the page that prints it and the brackets
    for the file itself."""
    marks = list(bits) + [f'<a href="{base}catalog.html">{{ }} catalog</a>',
                          f'<a href="{base}catalog.json">[ ] json</a>']
    return "".join(f"<span>{mark}</span>" for mark in marks)


def actions(app):
    e = html.escape
    return (f'<div class="actions">'
            f'<a class="get" href="{e(app["repo"])}" target="_blank" '
            f'rel="noopener noreferrer" aria-label="{e(app["name"])} on GitHub (new tab)">GitHub ↗</a>'
            f'<a class="get" href="{e(app["release"]["url"])}" target="_blank" '
            f'rel="noopener noreferrer" aria-label="Download {e(app["name"])} (new tab)">Download ↗</a>'
            '</div>')


def render(catalog, apps, broken, out):
    """The whole site: the tiles, a directory an app with its page and its
    files, the catalog as a page, and the style and the wave they share.
    Called once, after look.py has written what each app carries, so that
    every file can be measured where it now sits."""
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
                                 author=e(app["author"]), actions=actions(app)))
        home = os.path.join(out, *HOME.format(id=app["id"]).split("/")[:-1])
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, "index.html"), "w",
                  encoding="utf-8") as file:
            file.write(app_page(app, out))

    day = catalog["generated"].split("T")[0]
    count = f"{len(apps)} app" + ("" if len(apps) == 1 else "s")
    body = f"""  <div class="grid">
{chr(10).join(tiles)}
  </div>
{left_out(broken)}"""
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as file:
        file.write(SHELL.format(title="PSPDX catalog", base="./",
                                status=bar("", count, e(day)), body=body))
    with open(os.path.join(out, "catalog.html"), "w", encoding="utf-8") as file:
        file.write(catalog_page(catalog, count, day))


def catalog_page(catalog, count, day):
    """The file itself, printed so a person can read it. Nothing here is a
    second source of truth: it is the same object the console is handed,
    walked once more for colour."""
    body = f'''  <p class="lede">Exactly what the console fetches, and the only
  thing on this site it reads.</p>

  <pre class="json">{shine(catalog)}</pre>
'''
    return SHELL.format(title="catalog.json - PSPDX catalog", base="./",
                        status=bar("", count, html.escape(day)), body=body)


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
    <ul>
{chr(10).join(rows)}
    </ul>
  </section>
"""


def beside(app, field):
    """A file of this app as its own page addresses it: they sit in the same
    directory, so the name is the whole link."""
    return app[field].rsplit("/", 1)[-1]


def pixels(path):
    """How wide and high a PNG is, out of its header. Written down rather
    than assumed, because 144 by 80 is what the XMB draws and not what every
    author packed."""
    try:
        with open(path, "rb") as file:
            head = file.read(24)
        if (len(head) == 24 and head[:8] == b"\x89PNG\r\n\x1a\n"
                and head[12:16] == b"IHDR"):
            wide, high = struct.unpack(">II", head[16:24])
            return f"{wide}x{high}"
    except OSError:
        pass
    return ""


def section(heading, rows):
    """One group of values under the thing they came from. The heading says
    where they are from; nothing else on the page has to."""
    table = "\n".join(f"      <tr><th>{key}</th><td>{value}</td></tr>"
                      for key, value in rows)
    return f"""
  <section class="aside">
    <h3>{heading}</h3>
    <table class="facts">
{table}
    </table>
  </section>
"""


def origins(app, out):
    """Every value on the page under the thing that wrote it: what the author
    said in their file, what the release says this week, and what came out of
    the EBOOT. A reader sees at a glance which half of an app is somebody's
    words and which half no hand ever touched."""
    e = html.escape
    release = app["release"]

    said = []
    for field, what in (("name", "name"), ("author", "author"),
                        ("summary", "summary"), ("category", "category"),
                        ("license", "licence"), ("installdir", "installdir")):
        value = e(app[field]) or '<span class="gone">none</span>'
        # Which of these the author wrote is known only when the .pspdx was
        # read this run. An entry copied out of the published catalog says
        # nothing about that, so the page claims nothing about it either.
        wrote = app.get("_said")
        if wrote is not None and field in INSTEAD and field not in wrote:
            value += ' <span class="note">github</span>'
        said.append((what, value))

    day = datetime.fromtimestamp(release["rev"],
                                 timezone.utc).strftime("%Y-%m-%d")
    published = [
        ("version", e(release["version"])),
        ("published", f'{day} <span class="note">rev {release["rev"]}</span>'),
        ("package", f'<a href="{e(release["url"])}">'
                    f'{e(release["url"].rsplit("/", 1)[-1])}</a> '
                    f'<span class="note">{size(release["size"])}</span>'),
        ("sha256", e(release["sha256"])),
        ("release", f'<a href="{e(app["_page"])}">'
                    f'{e(app["_page"].rsplit("/", 1)[-1])}</a>'),
        ("repository", f'<a href="{e(app["repo"])}">'
                       f'{e(app["repo"].split("github.com/")[-1])}</a>'),
    ]

    # A file the EBOOT did not carry is a row saying absent rather than no row
    # at all: an app with no film and an app whose film the catalog dropped
    # look the same to a reader otherwise.
    carried = []
    for field, what, called in ARTEFACTS:
        if field in app:
            here = beside(app, field)
            told = f'<a href="{e(here)}">{called}</a>'
            shape = pixels(os.path.join(out, *app[field].split("/")))
            if shape:
                told += f' <span class="note">{shape}</span>'
            told += (' <span class="note">'
                     + size(os.path.getsize(os.path.join(out, *app[field].split("/"))))
                     + "</span>")
        else:
            told = f'{called} <span class="gone">absent</span>'
        carried.append((what, told))

    return (section(f'From the .pspdx <a href="read.pspdx">as read</a>'
                    f'<a href="{e(app["_pspdx"])}">source</a>', said)
            + section("From the release", published)
            + section("From the EBOOT", carried))


def entry_block(app):
    """The app as the console is handed it, under everything that says where
    each line of it came from."""
    return f"""
  <section class="aside">
    <h3>In catalog.json</h3>
    <pre class="json">{shine(plain(app))}</pre>
  </section>
"""


def app_page(app, out):
    """One app, as the person who has no console sees it: the icon at the
    size the XMB draws it, the picture out of the EBOOT, where every value
    came from, and the zip."""
    e = html.escape
    release = app["release"]
    icon = (f'<img src="{e(beside(app, "icon"))}" alt="" width="144" height="80">'
            if "icon" in app else "")
    about = " &middot; ".join(x for x in (f'by {e(app["author"])}',
                                          e(app["category"]),
                                          e(app["license"])) if x)

    shots = ""
    if "screenshot" in app:
        shots = (f'\n  <div class="shots">\n'
                 f'    <img src="{e(beside(app, "screenshot"))}" '
                 f'alt="{e(app["name"])} running" loading="lazy">\n  </div>\n')

    body = f"""  <div class="hero">
    {icon}
    <div>
      <h2>{e(app["name"])}</h2>
      <div class="who">{about}</div>
      <div class="ident">{e(app["id"])}</div>
      <p>{e(app["summary"])}</p>
      {actions(app)}
    </div>
  </div>
{shots}{origins(app, out)}
{entry_block(app)}"""
    return SHELL.format(
        title=f'{e(app["name"])} - PSPDX catalog', base=UP,
        status=bar(UP, e(release["version"]),
                   f'<a href="{UP}">all apps</a>'),
        body=body)
