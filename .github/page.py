#!/usr/bin/env python3
"""The page, which is the catalog for whoever has no PSP in their hands.

The console never reads any of this: it fetches catalog.json and nothing
else. This exists so that a person landing on the site sees what is listed,
sees which repository and which release each entry came from, and so that an
author whose app was left out reads the reason instead of guessing at it.

One file, with its style inside it and nothing fetched from anywhere: the
whole site is a handful of files on GitHub Pages, and a page that outlives
its own CDN is the only kind worth writing. Kept apart from look.py because
a page template is not catalog logic.
"""
import html
from datetime import datetime, timezone

STYLE = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 20px 64px; background: #0a0d12; color: #e8edf4;
  font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 820px; margin: 0 auto; }
a { color: #7fd4ff; }
h1 {
  margin: 40px 0 10px; font-size: 20px; font-weight: 400;
  letter-spacing: .34em; text-transform: uppercase;
}
h1 b { font-weight: 600; }
.lede { margin: 0 0 6px; max-width: 62ch; color: #9bb0c8; }
.status {
  margin: 0 0 30px; color: #6f8299;
  font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .1em;
}

.app {
  border: 1px solid rgba(255,255,255,.09); border-radius: 6px;
  background: rgba(255,255,255,.03); padding: 18px; margin: 0 0 14px;
}
.head { display: flex; gap: 18px; align-items: flex-start; flex-wrap: wrap; }
.icon, .noicon {
  width: 144px; height: 80px; display: block; border-radius: 3px;
  background: #05070a; box-shadow: 0 6px 16px rgba(0,0,0,.5);
}
.noicon {
  display: grid; place-items: center; color: #52627a;
  border: 1px dashed rgba(255,255,255,.14); box-shadow: none;
  font: 10px ui-monospace, monospace; letter-spacing: .16em;
}
.what { flex: 1 1 300px; min-width: 0; }
.what h2 { margin: 0; font-size: 19px; font-weight: 500; }
.by { margin: 2px 0 0; color: #9bb0c8; font-size: 13px; }
.summary { margin: 8px 0 0; }
.facts {
  margin: 10px 0 0; color: #6f8299;
  font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .04em; word-break: break-word;
}
.facts a { text-decoration: none; }
.facts a:hover { text-decoration: underline; }
.shot {
  display: block; width: 480px; max-width: 100%; height: auto; margin: 16px 0 0;
  border-radius: 3px; background: #000; box-shadow: 0 8px 22px rgba(0,0,0,.55);
}

.out { margin: 38px 0 0; border-top: 1px solid rgba(255,255,255,.09); padding-top: 18px; }
.out h2 {
  margin: 0 0 6px; font-size: 12px; font-weight: 400; color: #9bb0c8;
  letter-spacing: .2em; text-transform: uppercase;
}
.out p { margin: 0 0 12px; color: #6f8299; font-size: 13px; }
.out ul { margin: 0; padding: 0; list-style: none; }
.out li {
  padding: 7px 0; border-top: 1px solid rgba(255,255,255,.06);
  font: 12.5px ui-monospace, SFMono-Regular, Menlo, monospace;
  word-break: break-word;
}
.out .why { color: #e0a2a2; }

footer {
  margin: 34px 0 0; padding-top: 14px; border-top: 1px solid rgba(255,255,255,.09);
  color: #6f8299; font-size: 12px;
}
@media (max-width: 480px) {
  body { padding: 0 14px 48px; }
  h1 { letter-spacing: .22em; }
  .icon, .noicon { width: 100%; height: auto; aspect-ratio: 144 / 80; }
}
"""


def size(count):
    """Bytes as a person reads them, which is what a download link is for."""
    mb = count / (1024 * 1024)
    return f"{mb:.1f} MB" if mb >= 1 else f"{count / 1024:.0f} KB"


def card(app):
    e = html.escape
    release = app["release"]
    when = datetime.fromtimestamp(release["rev"], timezone.utc).strftime("%Y-%m-%d")
    art = (f'<img class="icon" src="{e(app["icon"])}" alt="" '
           f'width="144" height="80" loading="lazy">' if "icon" in app
           else '<div class="noicon">no icon</div>')
    # The category and the licence sit on the same line as the author because
    # they are three short words about who made this and on what terms, and a
    # table of them would be a debug dump.
    about = " &middot; ".join(x for x in (e(app["author"]), e(app["category"]),
                                          e(app["license"])) if x)
    facts = " &middot; ".join([
        f'{e(release["version"])}, {when}',
        f'<a href="{e(app["repo"])}">repository</a>',
        f'<a href="{e(app["_page"])}">release</a>',
        f'<a href="{e(release["url"])}">zip, {size(release["size"])}</a>',
    ])
    shot = (f'\n    <img class="shot" src="{e(app["screenshot"])}" '
            f'alt="{e(app["name"])} running" loading="lazy">'
            if "screenshot" in app else "")
    return f"""  <article class="app">
    <div class="head">
      {art}
      <div class="what">
        <h2>{e(app["name"])}</h2>
        <p class="by">{about}</p>
        <p class="summary">{e(app["summary"])}</p>
        <p class="facts">{facts}</p>
      </div>
    </div>{shot}
  </article>"""


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
        rows.append(f'    <li><a href="{e(label.split("@")[0])}">{e(label)}</a>'
                    f'<br><span class="why">{e(why)}</span></li>')
    return f"""
  <section class="out">
    <h2>Left out</h2>
    <p>On the list, and not in the catalog. Every one of these is a
    repository saying nothing, or saying something the format does not
    allow.</p>
    <ul>
{chr(10).join(rows)}
    </ul>
  </section>
"""


def render(catalog, apps, broken):
    """The whole site as one string: a line saying what this is, a card an
    app, and the reasons underneath."""
    when = catalog["generated"].replace("T", " ").replace("Z", " UTC")
    cards = "\n".join(card(app) for app in apps)
    count = f"{len(apps)} app" + ("" if len(apps) == 1 else "s")
    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSPDX catalog</title>
<style>{STYLE}</style>
<div class="wrap">
  <h1><b>PSPDX</b> catalog</h1>
  <p class="lede">Homebrew for the PlayStation Portable, listed so that
  <a href="https://github.com/chriopter/pspdx">PSPDX</a> on the console can
  install it and say when there is a new version. Every app is a GitHub
  repository with a <code>.pspdx</code> in its root; the version, the
  package and the pictures are read out of its latest release.</p>
  <p class="status">{count} &middot; read {html.escape(when)} &middot;
  <a href="catalog.json">catalog.json</a></p>

{cards}
{left_out(broken)}
  <footer>Every download comes from its author&#39;s own release.
  <a href="https://github.com/chriopter/pspdx-catalog">This list</a> is a
  text file; adding an app is a line in it.</footer>
</div>
"""
