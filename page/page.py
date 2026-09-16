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
import shutil
import struct
import urllib.parse
from datetime import datetime

import config

# The stylesheet and the wave script live beside this file as real .css and
# .js; the site is built by copying them out, and a page links them by name.
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")



SHELL = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{base}style.css">
<canvas id="wave" aria-hidden="true"></canvas>
<div class="wrap">
  <header>
    <h1><a href="{base}">{site_name}</a></h1>
    <div class="status">{status}</div>
  </header>
{body}
  <footer>
    <span>Downloads from the authors’ own releases</span>
    <span><a href="{repository_url}">catalog</a>
      &middot; <a href="{issues_url}">issues</a></span>
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

# The format catalog.json follows, as people read it: the standard's overview,
# opened at the catalog, not this catalog's, so a copy rebranded through
# catalog/config.json still points at the same page.
SCHEMA = "https://chriopter.github.io/pspdx/#catalog-v1"

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
    three small links, the braces for the page that prints it, the brackets
    for the file itself, and the dollar of `$schema` for the rules it keeps."""
    marks = list(bits) + [f'<a href="{base}catalog.html">{{ }} catalog</a>',
                          f'<a href="{base}catalog.json">[ ] json</a>',
                          f'<a href="{SCHEMA}">$ schema</a>']
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
    # A source elsewhere than GitHub -- the elsewhere() path -- is no GitHub
    # repository, so it gets a plain external-link mark and is named its source,
    # not GitHub.
    external = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
                'aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M17 13v6a1 1 0 0 1-1 1'
                'H5a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h6"/></svg>')
    download = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
                'aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg>')
    on_github = app["source"].startswith("https://github.com/")
    mark, where = (github, "GitHub") if on_github else (external, "its source")
    return (f'<div class="actions">'
            f'<a class="get" href="{e(app["source"])}" target="_blank" '
            f'rel="noopener noreferrer" title="{where} (new tab)" '
            f'aria-label="{e(app["name"])} at {where} (new tab)">{mark}</a>'
            f'<a class="get" href="{e(app["releases"][0]["url"])}" target="_blank" '
            f'rel="noopener noreferrer" title="Download (new tab)" '
            f'aria-label="Download {e(app["name"])} (new tab)">{download}</a>'
            '</div>')


def shell(title, base, status, body, settings):
    """Escape the catalog owner's words before putting them in HTML."""
    e = html.escape
    repo = settings["repository_url"].rstrip("/")
    return SHELL.format(title=e(title), base=base, status=status, body=body,
                        site_name=e(settings["name"]), repository_url=e(repo, quote=True),
                        issues_url=e(repo + "/issues", quote=True))


def render(catalog, apps, broken, out, settings=None, notes=None):
    """The whole site: the tiles, a directory an app with its page and its
    files, the catalog as a page, and the style and the wave they share.
    Called once, after look.py has written what each app carries, so that
    every file can be measured where it now sits."""
    settings = settings or config.load()
    e = html.escape
    for name in ("style.css", "wave.js"):
        shutil.copyfile(os.path.join(ASSETS, name), os.path.join(out, name))

    tiles = []
    for app in apps:
        art = (f'<img src="{e(app["media"]["icon"])}" alt="" width="144" height="80" '
               f'loading="lazy">' if "icon" in app.get("media", {})
               else '<div class="noicon">no icon</div>')
        tiles.append(TILE.format(art=art, id=e(app["id"]), name=e(app["name"]),
                                 author=e(app.get("author", "")), actions=actions(app)))
        home = os.path.join(out, *HOME.format(id=app["id"]).split("/")[:-1])
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, "index.html"), "w",
                  encoding="utf-8") as file:
            file.write(app_page(app, out, settings))

    day = catalog["generated_at"].split("T")[0]
    count = f"{len(apps)} app" + ("" if len(apps) == 1 else "s")
    updates = notes or []
    change_items = ("\n".join(f"    <li>{e(kind)}: {e(name)}"
                              + (f" ({e(tag)})" if tag else "") + "</li>"
                              for kind, name, tag in updates)
                    if updates else "    <li>No app changes</li>")
    body = f"""  <p class="lede">{e(settings["description"])}
    <a href="{e(settings["repository_url"], quote=True)}" target="_blank" rel="noopener noreferrer">Copy the catalog builder</a>
    to publish your own.</p>
  <section class="changes">
    <h2>Latest changes</h2>
    <ul>
{change_items}
    </ul>
  </section>
  <div class="grid">
{chr(10).join(tiles)}
  </div>
{left_out(broken)}"""
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as file:
        file.write(shell(settings["name"], "./", bar("", count, e(day)), body, settings))
    with open(os.path.join(out, "catalog.html"), "w", encoding="utf-8") as file:
        file.write(catalog_page(catalog, count, day, settings))


def catalog_page(catalog, count, day, settings):
    """The file itself, printed so a person can read it. Nothing here is a
    second source of truth: it is the same object the console is handed,
    walked once more for colour."""
    body = f'''  <p class="lede">Exactly what the console fetches, and the only
  thing on this site it reads.</p>

  <pre class="json">{shine(catalog)}</pre>
'''
    return shell(f'catalog.json - {settings["name"]}', "./",
                 bar("", count, html.escape(day)), body, settings)


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


def media_path(app, field):
    """Where the catalog says one of an app's EBOOT files is, or None. The
    picture is the first of the catalog's screenshots, since the EBOOT
    carries one and the catalog has room for more."""
    media = app.get("media") or {}
    if field == "screenshot":
        return (media.get("screenshots") or [None])[0]
    return media.get(field)


def linked(path):
    """A file the catalog names, as an app's own page links it: an address
    elsewhere as it stands, one relative to the catalog from two directories
    down, where the page sits."""
    return path if "://" in path else UP + path


def host(url):
    """The host of an address, which is what a person calls a site: no scheme,
    no login, no port, no path."""
    return urllib.parse.urlsplit(url).hostname or url


def beside(app, field):
    """A file of this app as its own page addresses it: they sit in the same
    directory, so the name is the whole link."""
    return media_path(app, field).rsplit("/", 1)[-1]


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
    release = app["releases"][0]

    said = []
    for field, what in (("name", "name"), ("author", "author"),
                        ("summary", "summary"), ("type", "type"), ("tags", "tags"),
                        ("license", "licence"), ("installdir", "installdir")):
        # Tags are the author's to give or not, so an entry may have none.
        value = app.get(field, "")
        value = e(", ".join(value) if isinstance(value, list) else value) \
            or '<span class="gone">none</span>'
        # Which of these the author wrote is known only when the .pspdx was
        # read this run. An entry copied out of the published catalog says
        # nothing about that, so the page claims nothing about it either.
        wrote = app.get("_said")
        if wrote is not None and field in INSTEAD and field not in wrote:
            value += ' <span class="note">github</span>'
        said.append((what, value))

    day = release["published_at"].split("T")[0]
    download = release
    published = [
        ("tag", e(release["tag"])),
        ("published", e(day)),
        ("package", f'<a href="{e(download["url"])}">'
                    f'{e(download["url"].rsplit("/", 1)[-1])}</a> '
                    f'<span class="note">{size(download["size"])}</span>'),
        ("sha256", e(download["sha256"])),
        ("history", f'{len(app["releases"])} release'
                    + ("" if len(app["releases"]) == 1 else "s")),
        ("release", f'<a href="{e(app["_page"])}">'
                    f'{e(app["_page"].rsplit("/", 1)[-1])}</a>'),
        ("repository", f'<a href="{e(app["source"])}">'
                       f'{e(app["source"].split("github.com/")[-1])}</a>'),
    ]

    # A file the EBOOT did not carry is a row saying absent rather than no row
    # at all: an app with no film and an app whose film the catalog dropped
    # look the same to a reader otherwise.
    carried = []
    for field, what, called in ARTEFACTS:
        if media_path(app, field):
            here = beside(app, field)
            told = f'<a href="{e(here)}">{called}</a>'
            shape = pixels(os.path.join(out, *media_path(app, field).split("/")))
            if shape:
                told += f' <span class="note">{shape}</span>'
            told += (' <span class="note">'
                     + size(os.path.getsize(os.path.join(out, *media_path(app, field).split("/"))))
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


def app_page(app, out, settings):
    """One app, as the person who has no console sees it: the icon at the
    size the XMB draws it, the picture out of the EBOOT, where every value
    came from, and the zip."""
    e = html.escape
    release = app["releases"][0]
    icon = (f'<img src="{e(beside(app, "icon"))}" alt="" width="144" height="80">'
            if "icon" in app.get("media", {}) else "")
    about = " &middot; ".join(x for x in (f'by {e(app["author"])}' if app.get("author") else "",
                                          e(app.get("type", "")),
                                          e(", ".join(app.get("tags", []))),
                                          e(app.get("license", ""))) if x)
    # The author's own words, as plain text: every line of it a line here,
    # and nothing in it read as markup.
    description = ""
    if app.get("description"):
        lines = "<br>\n    ".join(e(line) for line in app["description"].split("\n"))
        description = f'  <div class="description">\n    <p>{lines}</p>\n  </div>\n'

    # Every picture the catalog has, the one out of the EBOOT first.
    pictures = (app.get("media") or {}).get("screenshots") or []
    shots = ""
    if pictures:
        shots = ('\n  <div class="shots">\n'
                 + "".join(f'    <img src="{e(linked(path))}" '
                           f'alt="{e(app["name"])} running" loading="lazy">\n'
                           for path in pictures)
                 + '  </div>\n')

    manifest, published, media = origins(app, out)
    day = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00")).strftime("%d %b %Y")
    latest = section("Latest release", [
        ("Version", f'<a href="{e(app["_page"])}" target="_blank" '
                    f'rel="noopener noreferrer">{e(release["tag"])}</a>'),
        ("Updated", day),
        ("Download", size(release["size"])),
        ("Installs to", e(app.get("installdir", ""))),
        *([("Website", f'<a href="{e(app["website"])}" target="_blank" '
                       f'rel="noopener noreferrer">{e(host(app["website"]))}</a>')]
          if app.get("website") else []),
    ])
    body = f"""  <main class="detail">
  <div class="hero">
    {icon}
    <div>
      <h2>{e(app["name"])}</h2>
      <div class="who">{about}</div>
      <p>{e(app.get("summary", ""))}</p>
    </div>
  </div>
{description}  <div class="detail-columns">
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
    return shell(f'{app["name"]} - {settings["name"]}', UP,
                 bar(UP, f'<a href="{UP}">all apps</a>'), body, settings)
