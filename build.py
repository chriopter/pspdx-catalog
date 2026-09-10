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
  :root {{
    --ground: #eceeea; --card: #fff; --ink: #14181a; --dim: #5c665f;
    --rule: #d6dcd6; --accent: #12702a;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --ground: #080b09; --card: #111614; --ink: #e3e9e4; --dim: #8b968e;
      --rule: #232c26; --accent: #3ed255;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 40px 20px 64px; background: var(--ground); color: var(--ink);
    font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  header {{ border-bottom: 1px solid var(--rule); padding-bottom: 20px; margin-bottom: 28px; }}
  h1 {{ margin: 0 0 6px; font-size: 26px; letter-spacing: -.02em; }}
  h1 span {{ color: var(--accent); }}
  .lede {{ margin: 0; color: var(--dim); max-width: 60ch; }}
  .meta {{
    margin-top: 14px; font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--dim); display: flex; gap: 18px; flex-wrap: wrap;
  }}
  a {{ color: var(--accent); }}
  .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }}
  .app {{
    background: var(--card); border: 1px solid var(--rule);
    display: flex; flex-direction: column; overflow: hidden;
  }}
  .media {{
    display: grid; place-items: center; padding: 16px 12px;
    background: var(--ground); border-bottom: 1px solid var(--rule);
  }}
  .media img {{ display: block; width: 144px; height: 80px; }}
  .noicon {{
    width: 144px; height: 80px; display: grid; place-items: center;
    border: 1px dashed var(--rule); color: var(--dim);
    font: 11px ui-monospace, monospace; letter-spacing: .1em;
  }}
  .body {{ padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 6px; flex: 1; }}
  .name {{ font-weight: 600; font-size: 16px; }}
  .name a {{ text-decoration: none; }}
  .name a:hover {{ text-decoration: underline; }}
  .by {{ color: var(--dim); font-size: 13px; }}
  .summary {{ margin: 2px 0 8px; flex: 1; }}
  .tags {{
    font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--dim);
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
    border-top: 1px solid var(--rule); padding-top: 10px;
  }}
  .ver {{ color: var(--accent); }}
  footer {{
    margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--rule);
    color: var(--dim); font-size: 13px;
  }}
</style>
<div class="wrap">
  <header>
    <h1>PSPDX <span>catalog</span></h1>
    <p class="lede">Homebrew for the PlayStation Portable, listed so that
    <a href="https://github.com/chriopter/pspdx">PSPDX</a> on the console can
    install it and tell you when there is a new version. Downloads come from
    each author&#39;s own release.</p>
    <div class="meta">
      <span>{count} apps</span>
      <span>last checked {generated}</span>
      <span><a href="catalog.json">catalog.json</a></span>
      <span><a href="https://github.com/chriopter/pspdx-catalog">add yours</a></span>
    </div>
  </header>
  <div class="grid">
{cards}
  </div>
  <footer>Nothing is hosted here. Every download links to the release its
  author published.</footer>
</div>
"""

CARD = """    <article class="app">
      <div class="media">{art}</div>
      <div class="body">
        <div class="name"><a href="{repo}">{name}</a></div>
        <div class="by">{author}</div>
        <p class="summary">{summary}</p>
        <div class="tags">
          <span class="ver">{version}</span>
          <span>{category}</span>
          <span>{license}</span>
          <span><a href="{url}">download</a></span>
        </div>
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
