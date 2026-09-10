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
    have = ", ".join(f"{sum(f in a for a in apps)} {f}s"
                     for _, f in ASSETS.values())
    print(f"{len(apps)} apps, {have}, {len(text)} bytes -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "catalog.json")
