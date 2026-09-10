#!/usr/bin/env python3
"""Folds apps/*/{app.json,latest.json} into one catalog.json for the client.

One directory per app is what gets edited -- one package per pull request, no
merge conflicts, and a place to put the icon next to the metadata it belongs
to. One file is what gets served -- the PSP pays per handshake, not per byte,
so it must get everything in a single fetch.

No dependencies beyond the standard library, on purpose: this runs in a Pages
workflow and should keep running in ten years.
"""
import html
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = ("id", "name", "author", "summary", "category", "license", "repo")

# The format names itself: a file found on a stick years from now says where
# it came from and which version of the format it is.
SCHEMA = "https://github.com/chriopter/pspdx/blob/master/manifest.md"

# What scan.py writes into latest.json, and what the client needs in order to
# install anything. `root` stays here: the console works the layout out of the
# archive itself.
RELEASE = ("rev", "url", "sha256", "size")

# Optional file in an app directory -> where it is served, and the field that
# points at it. Everything is 480x272, the size of the screen; the video is
# H.264 baseline, which is what the Media Engine decodes.
ASSETS = {
    "icon.png": ("icons", "icon"),
    "screenshot.png": ("shots", "screenshot"),
    "video.mp4": ("vids", "video"),
}


def load(path):
    """path is <id>/app.json. The directory name is the id, and latest.json
    beside it is what scan.py last saw."""
    with path.open(encoding="utf-8") as f:
        app = json.load(f)
    missing = [k for k in REQUIRED if k not in app]
    if missing:
        sys.exit(f"{path.parent.name}: missing {', '.join(missing)}")
    if app["id"] != path.parent.name:
        sys.exit(f"{path.parent.name}: id {app['id']!r} does not match the directory")

    state = path.parent / "latest.json"
    if not state.exists():
        sys.exit(f"{path.parent.name}: no latest.json; run scan.py")
    with state.open(encoding="utf-8") as f:
        latest = json.load(f)
    missing = [k for k in RELEASE if k not in latest]
    if missing:
        sys.exit(f"{path.parent.name}: latest.json is missing "
                 f"{', '.join(missing)}; run scan.py")

    stray = [k for k in RELEASE + ("version",) if k in app]
    if stray:
        sys.exit(f"{path.parent.name}: app.json carries {', '.join(stray)}; "
                 "that belongs in latest.json, and the scanner owns it")

    # asset and scan steer the scanner, root is how it recognises the next
    # release. None of the three is any of the console's business.
    app.pop("asset", None)
    app.pop("scan", None)
    app["release"] = {k: v for k, v in latest.items() if k != "root"}
    return app


PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSPDX catalog</title>
<style>
  /* The XMB, more or less: a blue wave over near-black, thin wide type, and
     icons at the size the console draws them. */
  :root {{
    --ink: #f2f6fb; --dim: #93a6bd; --faint: #5f7391;
    --cyan: #7fd4ff; --rule: rgba(255,255,255,.10);
  }}
  * {{ box-sizing: border-box; }}
  html {{ background: #04070d; }}
  body {{
    margin: 0; padding: 0 20px 72px; color: var(--ink); min-height: 100vh;
    font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    background:
      radial-gradient(130% 70% at 50% -20%, #1d4478 0%, #0d1e3d 42%, #05090f 100%)
      no-repeat, #04070d;
    -webkit-font-smoothing: antialiased;
  }}
  .wave {{
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    opacity: .5; overflow: hidden;
  }}
  .wave svg {{ position: absolute; top: 8%; left: -5%; width: 110%; height: 60%; }}
  .wrap {{ position: relative; z-index: 1; max-width: 1000px; margin: 0 auto; }}

  header {{
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 16px; flex-wrap: wrap;
    padding: 34px 4px 14px; border-bottom: 1px solid var(--rule);
  }}
  h1 {{
    margin: 0; font-size: 22px; font-weight: 300; letter-spacing: .38em;
    text-transform: uppercase;
  }}
  h1 b {{ font-weight: 600; letter-spacing: .3em; }}
  .status {{
    font: 11px ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: .16em; text-transform: uppercase; color: var(--dim);
    display: flex; gap: 16px; flex-wrap: wrap;
  }}
  .lede {{
    margin: 22px 4px 30px; max-width: 62ch; color: var(--dim); font-weight: 300;
  }}
  a {{ color: var(--cyan); }}

  .grid {{
    display: grid; gap: 4px;
    grid-template-columns: repeat(auto-fill, minmax(228px, 1fr));
  }}
  .app {{
    display: flex; flex-direction: column; align-items: center; text-align: center;
    padding: 22px 16px 18px; gap: 4px; border-radius: 3px; height: 100%;
    transition: background .18s ease, transform .18s ease;
  }}
  .app:hover {{ background: rgba(255,255,255,.055); transform: translateY(-2px); }}
  .app img, .noicon {{
    width: 144px; height: 80px; display: block; margin-bottom: 12px;
    box-shadow: 0 10px 22px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.08);
  }}
  .noicon {{
    display: grid; place-items: center; color: var(--dim);
    border: 1px dashed var(--rule); box-shadow: none;
    font: 10px ui-monospace, monospace; letter-spacing: .18em;
  }}
  .name {{ font-size: 16px; font-weight: 400; letter-spacing: .01em; }}
  .name a {{ color: var(--ink); text-decoration: none; }}
  .name a:hover {{ color: var(--cyan); }}
  .by {{ font-size: 12px; color: var(--dim); }}
  .summary {{
    margin: 8px 0 14px; font-size: 13.5px; color: var(--dim); font-weight: 300;
    flex: 1;
  }}
  .tags {{
    margin-top: auto;
    font: 11px ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: .1em; color: var(--dim);
    display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;
  }}
  .ver {{ color: var(--cyan); }}

  footer {{
    margin-top: 40px; padding: 14px 4px 0; border-top: 1px solid var(--rule);
    display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
    font: 11px ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: .14em; text-transform: uppercase; color: var(--dim);
  }}
  .glyph {{
    display: inline-grid; place-items: center; width: 15px; height: 15px;
    border: 1px solid currentColor; border-radius: 50%; font-size: 9px;
    vertical-align: -3px; margin-right: 5px;
  }}
</style>
<div class="wave" aria-hidden="true">
  <svg viewBox="0 0 1200 400" preserveAspectRatio="none">
    <path d="M0 250 C 220 120, 380 330, 620 210 S 1000 90, 1200 180"
          fill="none" stroke="#8fd0ff" stroke-opacity=".30" stroke-width="1.5"/>
    <path d="M0 285 C 240 165, 420 360, 660 245 S 1020 130, 1200 215"
          fill="none" stroke="#8fd0ff" stroke-opacity=".18" stroke-width="1"/>
    <path d="M0 320 C 260 210, 460 395, 700 280 S 1040 175, 1200 250"
          fill="none" stroke="#8fd0ff" stroke-opacity=".10" stroke-width="1"/>
  </svg>
</div>
<div class="wrap">
  <header>
    <h1><b>PSPDX</b> catalog</h1>
    <div class="status">
      <span>{count} apps</span>
      <span>checked {generated}</span>
      <span><a href="catalog.json">catalog.json</a></span>
    </div>
  </header>

  <p class="lede">Homebrew for the PlayStation Portable, listed so that
  <a href="https://github.com/chriopter/pspdx">PSPDX</a> on the console can
  install it and tell you when there is a new version. Every download comes
  from the release its author published &mdash; nothing is hosted here.</p>

  <div class="grid">
{cards}
  </div>

  <footer>
    <span><span class="glyph">&#10005;</span>download links to the author&#39;s release</span>
    <span><a href="https://github.com/chriopter/pspdx-catalog">add an app</a></span>
  </footer>
</div>
"""

CARD = """    <article class="app">
      {art}
      <div class="name"><a href="{repo}">{name}</a></div>
      <div class="by">{author}</div>
      <p class="summary">{summary}</p>
      <div class="tags">
        <span class="ver">{version}</span>
        <span>{category}</span>
        <span>{license}</span>
        <span><a href="{url}">download</a></span>
      </div>
    </article>"""


def write_page(apps, out):
    """The page a person lands on. The console never reads it."""
    e = html.escape
    cards = []
    for a in apps:
        art = (f'<img src="{e(a["icon"])}" alt="" loading="lazy">'
               if "icon" in a else '<div class="noicon">no icon</div>')
        cards.append(CARD.format(
            art=art, repo=e(a["repo"]), name=e(a["name"]), author=e(a["author"]),
            summary=e(a["summary"]), version=e(a["release"].get("version", "")),
            category=e(a["category"]), license=e(a["license"]),
            url=e(a["release"]["url"])))
    out.write_text(PAGE.format(
        count=len(apps),
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        cards="\n".join(cards)), encoding="utf-8")


def main(out):
    out = Path(out)
    apps = [load(p) for p in sorted((HERE / "apps").glob("*/app.json"))]

    # Assets are never named by hand: an entry gets the field only if the file
    # is there, so the client never spends a request discovering a 404.
    for name, (subdir, field) in ASSETS.items():
        for app in apps:
            src = HERE / "apps" / app["id"] / name
            if not src.exists():
                continue
            dest = out.parent / subdir
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest / (app["id"] + src.suffix))
            app[field] = f"{subdir}/{app['id']}{src.suffix}"
    catalog = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "apps": apps,
    }
    # Compact separators: the client holds this in RAM, and the PSP has 24 MB.
    text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    out.write_text(text + "\n", encoding="utf-8")
    write_page(apps, out.parent / "index.html")
    have = ", ".join(f"{sum(f in a for a in apps)} {f}s"
                     for _, f in ASSETS.values())
    print(f"{len(apps)} apps, {have}, {len(text)} bytes -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "catalog.json")
