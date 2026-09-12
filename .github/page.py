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

STYLE = """/* Quiet framing, with the PSP wave kept behind the content. */
:root { --ink: #e7edf5; --dim: #9baabe; --cyan: #8ec9eb; --rule: #ffffff18; color-scheme: dark; }
* { box-sizing: border-box; }
html { background: #0a1422; }
body { margin: 0; padding: 0 24px 40px; color: var(--ink); font: 14px/1.6 system-ui, sans-serif; }
#wave { position: fixed; inset: 0; width: 100%; height: 100%; opacity: .13; pointer-events: none; }
.wrap { position: relative; max-width: 1040px; margin: auto; }
a { color: var(--cyan); text-underline-offset: 3px; }
a:hover { color: #fff; }
a:focus-visible, summary:focus-visible { outline: 2px solid var(--cyan); outline-offset: 4px; }
header { display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap; padding: 24px 0; border-bottom: 1px solid var(--rule); }
h1 { margin: 0; font-size: 17px; font-weight: 400; letter-spacing: .04em; }
h1 b { font-weight: 650; }
h1 a { color: inherit; text-decoration: none; }
.status { display: flex; gap: 18px; flex-wrap: wrap; color: var(--dim); font-size: 12px; }
.status a { text-decoration: none; }
.lede { color: var(--dim); margin: 24px 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(176px, 1fr)); gap: 24px; padding: 28px 0; }
.app { display: flex; flex-direction: column; max-width: 220px; padding: 16px;
  border: 1px solid var(--rule); border-radius: 5px; background: #ffffff03; }
.app-main { flex: 1; color: inherit; text-decoration: none; }
.app img, .noicon { display: block; width: 100%; height: auto; aspect-ratio: 144 / 80; object-fit: contain; background: #080e17; }
.noicon { display: grid; place-items: center; color: var(--dim); }
.name { margin-top: 12px; font-weight: 550; }
.by { color: var(--dim); font-size: 12px; }
.app-main:hover .name { color: var(--cyan); }
.actions { display: flex; gap: 8px; }
.app .actions { margin-top: 12px; }
.get { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border: 1px solid var(--rule); border-radius: 4px; color: var(--cyan); }
.get:hover { background: #ffffff08; border-color: var(--cyan); }
.get svg { width: 18px; height: 18px; }
.hero { display: flex; align-items: center; gap: 20px; padding: 32px 0; }
.hero img { width: 108px; height: 60px; object-fit: contain; }
.hero > div:not(.actions) { flex: 1; min-width: 0; }
.hero h2 { margin: 0 0 3px; font-size: 28px; font-weight: 550; letter-spacing: -.035em; line-height: 1.2; }
.hero .who { font-size: 12px; color: var(--dim); }
.hero p { margin: 10px 0 0; color: var(--dim); }
.hero .actions { flex-shrink: 0; }
.detail-columns { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 32px; padding-bottom: 28px; }
.detail-columns > div { min-width: 0; }
.shots { margin: 0 0 22px; }
.shots img { display: block; width: 100%; height: auto; }
.aside { border-top: 1px solid var(--rule); padding: 16px 0; }
.detail-columns .aside { border-top: 0; padding: 0; }
.release .actions { margin-top: 20px; }
.technical > .aside:first-of-type { border-top: 0; }
.aside h3, .aside summary { margin: 0 0 12px; font-size: 13px; font-weight: 600; }
.aside summary { cursor: pointer; margin: 0; }
.aside[open] summary { margin-bottom: 16px; }
.aside h3 a, .aside summary a { margin-left: 12px; font-weight: 400; font-size: 12px; }
.facts { width: 100%; border-collapse: collapse; font-size: 12px; }
.facts th, .facts td { text-align: left; vertical-align: top; padding: 7px 0; border-bottom: 1px solid var(--rule); }
.facts th { width: 84px; color: var(--dim); font-weight: 400; padding-right: 12px; }
.facts td { overflow-wrap: anywhere; }
.facts .note { color: var(--dim); margin-left: 6px; font-size: 11px; }
.gone { color: var(--dim); }
.aside ul { padding-left: 18px; }
.aside .why { color: #dbb0a7; }
pre.json { margin: 0; padding: 16px; overflow-x: auto; background: #070e18; font: 12px/1.7 ui-monospace, monospace; }
pre.json .k { color: var(--cyan); }
pre.json .s { color: #bdc9d6; }
pre.json .n { color: #c7bca7; }
pre.json .p { color: var(--dim); }
pre.json a { color: inherit; }
footer { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-top: 24px; padding-top: 18px; border-top: 1px solid var(--rule); color: var(--dim); font-size: 11px; }
@media (max-width: 720px) {
  body { padding: 0 18px 28px; }
  header { gap: 12px; padding: 18px 0; }
  .hero { flex-wrap: wrap; gap: 14px; padding: 24px 0; }
  .hero img { width: 72px; height: 40px; }
  .hero h2 { font-size: 24px; }
  .hero .actions { width: 100%; }
  .detail-columns { grid-template-columns: 1fr; gap: 24px; }
  .grid { grid-template-columns: repeat(auto-fill, minmax(144px, 1fr)); gap: 20px; }
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
    <span>Downloads from the authors’ GitHub releases</span>
    <span><a href="https://github.com/chriopter/pspdx-catalog">catalog</a>
      &middot; <a href="https://github.com/chriopter/pspdx-app">client</a>
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
    github = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
              '<path d="M12 .75a11.25 11.25 0 0 0-3.558 21.923c.563.104.769-.244.769-.542'
              ' 0-.267-.01-.975-.015-1.913-3.13.68-3.791-1.509-3.791-1.509'
              '-.512-1.3-1.25-1.646-1.25-1.646-1.022-.699.078-.685.078-.685'
              ' 1.13.08 1.725 1.16 1.725 1.16 1.005 1.724 2.637 1.226 3.28.937'
              '.102-.728.393-1.226.715-1.508-2.499-.284-5.126-1.25-5.126-5.562'
              ' 0-1.229.44-2.233 1.16-3.02-.116-.284-.503-1.429.11-2.978'
              ' 0 0 .945-.303 3.094 1.154A10.79 10.79 0 0 1 12 6.183'
              'c.956.004 1.919.129 2.818.378 2.148-1.457 3.091-1.154 3.091-1.154'
              '.615 1.549.228 2.694.112 2.978.722.787 1.158 1.791 1.158 3.02'
              ' 0 4.323-2.631 5.275-5.138 5.554.404.348.766 1.034.766 2.084'
              ' 0 1.505-.014 2.719-.014 3.088 0 .301.203.652.774.541'
              'A11.252 11.252 0 0 0 12 .75Z"/></svg>')
    download = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
                'aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg>')
    return (f'<div class="actions">'
            f'<a class="get" href="{e(app["repo"])}" target="_blank" '
            f'rel="noopener noreferrer" title="GitHub (new tab)" '
            f'aria-label="{e(app["name"])} on GitHub (new tab)">{github}</a>'
            f'<a class="get" href="{e(app["release"]["url"])}" target="_blank" '
            f'rel="noopener noreferrer" title="Download (new tab)" '
            f'aria-label="Download {e(app["name"])} (new tab)">{download}</a>'
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
    body = f"""  <p class="lede">The PSPDX reference catalog.
    <a href="https://github.com/chriopter/pspdx-catalog" target="_blank" rel="noopener noreferrer">Copy the catalog builder</a>
    to publish your own.</p>
  <div class="grid">
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


def section(heading, rows, folded=False):
    """One group of values under the thing they came from. The heading says
    where they are from; nothing else on the page has to."""
    table = "\n".join(f"      <tr><th>{key}</th><td>{value}</td></tr>"
                      for key, value in rows)
    tag = "details" if folded else "section"
    title = "summary" if folded else "h3"
    return f"""
  <{tag} class="aside">
    <{title}>{heading}</{title}>
    <table class="facts">
{table}
    </table>
  </{tag}>
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

    said.insert(0, ("id", e(app["id"])))
    return (section(f'Manifest <a href="read.pspdx">as read</a>'
                    f'<a href="{e(app["_pspdx"])}">source</a>', said),
            section("Release", published),
            section("EBOOT media", carried))


def entry_block(app):
    """The app as the console is handed it, under everything that says where
    each line of it came from."""
    return f"""
  <section class="aside">
    <h3>Catalog JSON</h3>
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

    manifest, published, media = origins(app, out)
    day = datetime.fromtimestamp(release["rev"], timezone.utc).strftime("%d %b %Y")
    latest = section("Latest release", [
        ("Version", f'<a href="{e(app["_page"])}" target="_blank" '
                    f'rel="noopener noreferrer">{e(release["version"])}</a>'),
        ("Updated", day),
        ("Download", size(release["size"])),
        ("Installs to", e(app["installdir"])),
    ])
    body = f"""  <main class="detail">
  <div class="hero">
    {icon}
    <div>
      <h2>{e(app["name"])}</h2>
      <div class="who">{about}</div>
      <p>{e(app["summary"])}</p>
    </div>
  </div>
  <div class="detail-columns">
    <div class="preview">{shots}</div>
    <div class="release">{latest}{actions(app)}</div>
  </div>
  <details class="aside technical">
    <summary>Technical details</summary>
{published}
{media}
{manifest}
{entry_block(app)}
  </details>"""
    body += "</main>"
    return SHELL.format(
        title=f'{e(app["name"])} - PSPDX catalog', base=UP,
        status=bar(UP, f'<a href="{UP}">all apps</a>'),
        body=body)
