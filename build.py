#!/usr/bin/env python3
"""Folds apps/*/{app.json,latest.json} into one catalog.json for the client.

One directory per app is what gets edited -- one package per pull request, no
merge conflicts, and a place to put the icon next to the metadata it belongs
to. One file is what gets served -- the PSP pays per handshake, not per byte,
so it must get everything in a single fetch.

No dependencies beyond the standard library, on purpose: this runs in a Pages
workflow and should keep running in ten years.
"""
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import page

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
    page.render(apps, out.parent)
    have = ", ".join(f"{sum(f in a for a in apps)} {f}s"
                     for _, f in ASSETS.values())   # counted after copying
    print(f"{len(apps)} apps, {have}, {len(text)} bytes -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "catalog.json")
