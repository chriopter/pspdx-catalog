#!/usr/bin/env python3
"""Fills in what a release is, so that nobody has to type a sha256.

Most PSP homebrew was published once and left alone, and its author is never
going to maintain a file for us. So the index looks: it asks GitHub what the
newest release is, downloads the archive, hashes the bytes it actually got,
and looks inside to see where the EBOOT sits.

    scan.py https://github.com/user/repo   add that repository
    scan.py --all                          refresh every entry
    scan.py --all --check                  report what would change, write nothing

An entry is two halves. Everything above `release` is written by a person and
never touched here; `release` and `archive` are this script's and nobody
edits them by hand.

No dependencies beyond the standard library: this runs in a workflow and
should keep running in ten years.
"""
import fnmatch
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPS = HERE / "apps"
GITHUB = re.compile(r"https://github\.com/([^/]+)/([^/]+?)/?$")

# A release with several assets has to be told apart; one .zip needs no rule.
DEFAULT_ASSET = "*.zip"


def token():
    """gh's token if there is one. Unauthenticated works, just 60 calls an hour."""
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        return out.stdout.strip() or None
    except FileNotFoundError:
        return None


def api(path, etag=None):
    """Returns (json, etag), or (None, etag) for 304 -- which GitHub does not
    count against the rate limit, so an hourly scan of an unchanged repository
    is free."""
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    t = token()
    if t:
        req.add_header("Authorization", "Bearer " + t)
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, etag
        raise


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pspdx-scan"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def pick_asset(release, pattern):
    names = [a for a in release.get("assets", [])
             if fnmatch.fnmatch(a["name"].lower(), pattern.lower())]
    if len(names) == 1:
        return names[0]
    if not names:
        raise SystemExit(f"  no asset matches {pattern!r}; release has "
                         + ", ".join(a["name"] for a in release.get("assets", []))
                         + "\n  put the right glob in archive.asset")
    raise SystemExit(f"  {len(names)} assets match {pattern!r}: "
                     + ", ".join(a["name"] for a in names)
                     + "\n  narrow archive.asset")


def eboot_root(raw):
    """Where the package sits inside the archive.

    The shallowest EBOOT.PBP wins and its directory is the package -- of
    sixteen surveyed archives that hold an EBOOT, ten put it one directory
    down, three at the root and only two under PSP/GAME/. An empty root means
    the archive is the package.
    """
    z = zipfile.ZipFile(io.BytesIO(raw))
    ebs = [n for n in z.namelist() if n.lower().endswith("eboot.pbp")]
    if not ebs:
        raise SystemExit("  no EBOOT.PBP in the archive")
    path = min(ebs, key=lambda n: (n.count("/"), len(n)))
    return path.rsplit("/", 1)[0] + "/" if "/" in path else ""


def scan(entry, check=False):
    """Returns True if the entry changed. Leaves the human half alone."""
    m = GITHUB.match(entry["repo"])
    if not m:
        raise SystemExit(f"  {entry['repo']} is not a GitHub repository")
    owner, repo = m.group(1), m.group(2)

    archive = entry.setdefault("archive", {})
    rel, etag = api(f"/repos/{owner}/{repo}/releases/latest", archive.get("etag"))
    if rel is None:
        return False                       # 304: nothing has been published
    published = rel["published_at"]
    rev = int(__import__("datetime").datetime.fromisoformat(
        published.replace("Z", "+00:00")).timestamp())
    if entry.get("release", {}).get("rev") == rev:
        archive["etag"] = etag
        return False

    asset = pick_asset(rel, archive.get("asset", DEFAULT_ASSET))
    raw = fetch(asset["browser_download_url"])
    root = eboot_root(raw)

    # A layout that moved is not something to publish quietly: the entry keeps
    # the release that is known to install, and a person is told what changed.
    if "root" in archive and archive["root"] != root:
        raise SystemExit(f"  {rel['tag_name']} moved the package: "
                         f"expected {archive['root']!r}, found {root!r}\n"
                         "  fix archive.root if the new layout is right")

    if check:
        return True
    archive.update({"asset": archive.get("asset", DEFAULT_ASSET),
                    "root": root, "etag": etag})
    entry["release"] = {
        "rev": rev,
        "version": rel["tag_name"].lstrip("v"),
        "url": asset["browser_download_url"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": asset["size"],
    }
    return True


def new_entry(url):
    m = GITHUB.match(url)
    if not m:
        raise SystemExit(f"{url} is not a GitHub repository")
    owner, repo = m.group(1), m.group(2)
    meta, _ = api(f"/repos/{owner}/{repo}")
    lic = (meta.get("license") or {}).get("spdx_id")
    return {
        "id": f"io.github.{owner.lower()}.{re.sub(r'[^a-z0-9]', '', repo.lower())}",
        "name": repo.replace("-", " ").replace("_", " ").title(),
        "author": owner,
        "summary": (meta.get("description") or "")[:60],
        "category": "apps",
        "license": lic if lic and lic != "NOASSERTION" else "",
        "repo": f"https://github.com/{owner}/{repo}",
    }


def save(entry):
    d = APPS / entry["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "app.json").write_text(json.dumps(entry, indent=2) + "\n")
    return d / "app.json"


def main(argv):
    check = "--check" in argv
    argv = [a for a in argv if a != "--check"]
    if argv and argv[0] == "--all":
        changed, broken = [], []
        for p in sorted(APPS.glob("*/app.json")):
            entry = json.loads(p.read_text())
            if entry.get("scan") is False:
                continue
            print(entry["id"])
            # One app whose upstream moved must not stop the other forty from
            # being refreshed, so a failure is collected rather than raised.
            try:
                if scan(entry, check):
                    changed.append(entry["id"])
                    if not check:
                        save(entry)
            except SystemExit as e:
                print(str(e))
                broken.append(f"{entry['id']}:{e}")
            except Exception as e:
                print(f"  {type(e).__name__}: {e}")
                broken.append(f"{entry['id']}: {type(e).__name__}: {e}")
        print(f"{len(changed)} changed" + (": " + ", ".join(changed) if changed else ""))
        if broken:
            print(f"{len(broken)} need a person:")
            for b in broken:
                print(b)
            return 1
        return 0
    if not argv:
        raise SystemExit(__doc__)
    # An id is not derivable from a repository name -- the entry may well be
    # called something else -- so an existing entry is found by its repo URL.
    want = argv[0].rstrip("/").removesuffix(".git").lower()
    entry = None
    for q in sorted(APPS.glob("*/app.json")):
        e = json.loads(q.read_text())
        if e["repo"].rstrip("/").lower() == want:
            entry = e
            break
    if entry is None:
        entry = new_entry(argv[0])
    print(entry["id"])
    scan(entry, check)
    if not check:
        print("->", save(entry))
    else:
        print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
