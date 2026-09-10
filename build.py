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
import re
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

# Everything the console is given, and nothing else. A denylist would ship
# whatever scan.py grows next -- `seen` reached the device that way.
SERVED = RELEASE + ("version",)

CATEGORIES = ("games", "emulators", "apps", "plugins", "demos")
ID = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")

# Caps and magic bytes, because these are copied onto a public page and pulled
# by a console with 24 MB of RAM.
LIMITS = {"icon.png": (64 * 1024, b"\x89PNG\r\n\x1a\n"),
          "screenshot.png": (768 * 1024, b"\x89PNG\r\n\x1a\n"),
          "video.mp4": (8 * 1024 * 1024, None)}

# Optional file in an app directory -> where it is served, and the field that
# points at it. Everything is 480x272, the size of the screen; the video is
# H.264 baseline, which is what the Media Engine decodes.
ASSETS = {
    "icon.png": ("icons", "icon"),
    "screenshot.png": ("shots", "screenshot"),
    "video.mp4": ("vids", "video"),
}


def read_json(path):
    """A contributor's trailing comma should name the file, not print a
    traceback from inside the json module."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        sys.exit(f"{path.parent.name}/{path.name}: {e}")
    if not isinstance(d, dict):
        sys.exit(f"{path.parent.name}/{path.name}: not a JSON object")
    return d


def load(path):
    """path is <id>/app.json. The directory name is the id, and latest.json
    beside it is what scan.py last saw."""
    app = read_json(path)
    # Presence is not enough: an empty licence passed the check, and scan.py
    # writes one whenever GitHub reports NOASSERTION.
    missing = [k for k in REQUIRED
               if not isinstance(app.get(k), str) or not app[k].strip()]
    if missing:
        sys.exit(f"{path.parent.name}: missing or empty {', '.join(missing)}")
    if app["id"] != path.parent.name:
        sys.exit(f"{path.parent.name}: id {app['id']!r} does not match the directory")
    if not ID.fullmatch(app["id"]) or len(app["id"]) > 80:
        sys.exit(f"{path.parent.name}: an id is lowercase letters, digits, dots "
                 "and dashes, up to 80 characters -- it becomes a URL and a "
                 "directory on the Memory Stick")
    if app["category"] not in CATEGORIES:
        sys.exit(f"{app['id']}: category {app['category']!r} is not one of "
                 + ", ".join(CATEGORIES))
    if len(app["summary"]) > 80 or "\n" in app["summary"]:
        sys.exit(f"{app['id']}: summary is one line of at most 80 characters")
    if not app["repo"].startswith("https://"):
        sys.exit(f"{app['id']}: repo must be an https URL")

    stray = [k for k in SERVED if k in app]
    if stray:
        sys.exit(f"{app['id']}: app.json carries {', '.join(stray)}; that is "
                 "latest.json's, and the scanner owns it")

    state = path.parent / "latest.json"
    if not state.exists():
        # A pull request adds app.json and nothing else -- the scanner owns
        # the other half and fills it in within the hour. Refusing to build
        # would take the whole catalog down for one half-finished entry.
        print(f"{path.parent.name}: not scanned yet, leaving it out")
        return None
    latest = read_json(state)
    missing = [k for k in RELEASE if k not in latest]
    if missing:
        sys.exit(f"{path.parent.name}: latest.json is missing "
                 f"{', '.join(missing)}; run scan.py")

    # asset and scan steer the scanner, root and seen are how it recognises
    # the next release. None of them is any of the console's business, and the
    # asset fields belong to the builder, not to whoever wrote the entry.
    for k in ("asset", "scan") + tuple(f for _, f in ASSETS.values()):
        app.pop(k, None)
    app["release"] = {k: latest[k] for k in SERVED if k in latest}
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
  #wave {{
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    width: 100%; height: 100%; display: block;
  }}
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
<canvas id="wave" aria-hidden="true"></canvas>
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

<script>
/* The XMB wave: bands of offset sine curves drifting past each other. Hand
   written, because the console it is imitating is the whole point and a
   dependency would outlive its own CDN. */
(function () {{
  var c = document.getElementById("wave"), x = c.getContext("2d");
  var still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var w, h;

  function size() {{
    w = c.width = innerWidth;
    h = c.height = innerHeight;
  }}

  function band(mid, amp, freq, phase, lines, alpha) {{
    for (var i = 0; i < lines; i++) {{
      var lift = (i - lines / 2) * (amp * 0.13);
      x.beginPath();
      for (var px = 0; px <= w; px += 8) {{
        var u = px / w;
        var y = mid + lift
              + Math.sin(u * freq + phase + i * 0.10) * amp
              + Math.sin(u * freq * 2.7 + phase * 1.6) * amp * 0.28;
        px ? x.lineTo(px, y) : x.moveTo(px, y);
      }}
      x.strokeStyle = "rgba(158,214,255," + (alpha * (1 - Math.abs(i - lines / 2) / lines)) + ")";
      x.lineWidth = 1;
      x.stroke();
    }}
  }}

  var t = 0;
  function frame() {{
    x.clearRect(0, 0, w, h);
    band(h * 0.42, h * 0.075, 4.2, t,        16, 0.30);
    band(h * 0.56, h * 0.055, 5.6, t * 0.7 + 2, 12, 0.20);
    band(h * 0.70, h * 0.045, 3.4, -t * 0.5,    10, 0.13);
    if (!still) {{
      t += 0.004;
      requestAnimationFrame(frame);
    }}
  }}

  addEventListener("resize", function () {{ size(); if (still) frame(); }});
  size();
  frame();
}})();
</script>
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
    out.parent.mkdir(parents=True, exist_ok=True)

    # A directory holding a latest.json and no app.json used to be skipped in
    # silence -- a half-finished pull request would simply vanish from the
    # catalog with nothing said.
    for d in sorted((HERE / "apps").glob("*/")):
        if not (d / "app.json").exists():
            sys.exit(f"{d.name}: no app.json")

    apps = [a for a in (load(p) for p in sorted((HERE / "apps").glob("*/app.json")))
            if a is not None]
    if not apps:
        sys.exit("no apps found; refusing to write an empty catalog")

    seen = {}
    for a in apps:
        key = a["repo"].rstrip("/").removesuffix(".git").lower()
        if key in seen:
            sys.exit(f"{a['id']}: same repo as {seen[key]}")
        seen[key] = a["id"]

    # Assets are never named by hand: an entry gets the field only if the file
    # is there, so the client never spends a request discovering a 404.
    for name, (subdir, field) in ASSETS.items():
        # Whatever a previous build left here is not evidence that the file is
        # still in the repository.
        shutil.rmtree(out.parent / subdir, ignore_errors=True)
        for app in apps:
            src = HERE / "apps" / app["id"] / name
            if not src.exists():
                continue
            if src.is_symlink() or not src.is_file():
                sys.exit(f"{app['id']}/{name}: must be a regular file")
            cap, magic = LIMITS[name]
            size = src.stat().st_size
            if size == 0 or size > cap:
                sys.exit(f"{app['id']}/{name}: {size} bytes, the limit is {cap}")
            if magic and src.open("rb").read(len(magic)) != magic:
                sys.exit(f"{app['id']}/{name}: not a {src.suffix[1:]} file")
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
                     for _, f in ASSETS.values())   # counted after copying
    print(f"{len(apps)} apps, {have}, {len(text)} bytes -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "catalog.json")
