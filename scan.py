#!/usr/bin/env python3
"""Fills in what a release is, so that nobody has to type a sha256.

Most PSP homebrew was published once and left alone, and its author is never
going to maintain a file for us. So the index looks: it asks GitHub what the
newest release is, downloads the archive, hashes the bytes it actually got,
and looks inside to see where the EBOOT sits.

    scan.py https://github.com/user/repo   add that repository
    scan.py --all                          refresh every entry
    scan.py --all --check                  report what would change, write nothing

Two files per app, and the split is deliberate. `app.json` is a person's:
what the app is called, who wrote it, which licence, which asset to take.
Nothing automated ever writes it. `latest.json` is this script's, rewritten
whole, and nobody edits it by hand.

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
from datetime import datetime
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


def api(path):
    """One small GET. Conditional requests were tried and dropped: the release
    JSON carries each asset's download_count, so its ETag changes whenever
    anybody downloads anything, and a 304 almost never arrives."""
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    t = token()
    if t:
        req.add_header("Authorization", "Bearer " + t)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


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


def scan(app, state, check=False):
    """Refreshes `state` from the newest release. Never touches `app`."""
    m = GITHUB.match(app["repo"])
    if not m:
        raise SystemExit(f"  {app['repo']} is not a GitHub repository")
    owner, repo = m.group(1), m.group(2)

    rel = api(f"/repos/{owner}/{repo}/releases/latest")
    published = int(datetime.fromisoformat(
        rel["published_at"].replace("Z", "+00:00")).timestamp())
    if state.get("seen") == published:
        return False

    asset = pick_asset(rel, app.get("asset", DEFAULT_ASSET))
    raw = fetch(asset["browser_download_url"])
    root = eboot_root(raw)
    sha = hashlib.sha256(raw).hexdigest()

    # A layout that moved is not something to publish quietly: the app keeps
    # the release that is known to install, and a person is told what changed.
    if "root" in state and state["root"] != root:
        raise SystemExit(f"  {rel['tag_name']} moved the package: "
                         f"expected {state['root']!r}, found {root!r}\n"
                         "  delete latest.json if the new layout is right")

    if check:
        return True

    # Two numbers, because a re-tagged release is not an update. `seen` is the
    # release we last looked at and always moves; `rev` is the revision of the
    # bytes and only moves when they do. Without that split, an author who
    # tags the same build again costs every user the whole download.
    same = state.get("sha256") == sha
    rev = state["rev"] if same and "rev" in state else published
    state.clear()
    state.update({
        "rev": rev,
        "seen": published,
        "version": rel["tag_name"].lstrip("v"),
        "url": asset["browser_download_url"],
        "sha256": sha,
        "size": asset["size"],
        "root": root,
    })
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


def save_state(app_id, state):
    d = APPS / app_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "latest.json").write_text(json.dumps(state, indent=2) + "\n")
    return d / "latest.json"


def load_state(app_id):
    p = APPS / app_id / "latest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def main(argv):
    check = "--check" in argv
    argv = [a for a in argv if a != "--check"]

    if argv and argv[0] == "--all":
        changed, broken = [], []
        for p in sorted(APPS.glob("*/app.json")):
            app = json.loads(p.read_text())
            if app.get("scan") is False:
                continue
            print(app["id"])
            # One app whose upstream moved must not stop the other forty from
            # being refreshed, so a failure is collected rather than raised.
            try:
                state = load_state(app["id"])
                if scan(app, state, check):
                    changed.append(app["id"])
                    if not check:
                        save_state(app["id"], state)
            except SystemExit as e:
                print(str(e))
                broken.append(f"{app['id']}:{e}")
            except Exception as e:
                print(f"  {type(e).__name__}: {e}")
                broken.append(f"{app['id']}: {type(e).__name__}: {e}")
        print(f"{len(changed)} changed" + (": " + ", ".join(changed) if changed else ""))
        # A commit that says which packages moved beats four identical ones.
        out = os.environ.get("GITHUB_OUTPUT")
        if out and changed:
            names = [n for n in (json.loads((APPS / c / "app.json").read_text())
                                 .get("name", c) for c in changed)]
            line = ", ".join(names[:3])
            if len(names) > 3:
                line += f" and {len(names) - 3} more"
            with open(out, "a") as f:
                f.write(f"changed={line}\n")
        if broken:
            print(f"{len(broken)} need a person:")
            for b in broken:
                print(b)
            return 1
        return 0

    if not argv:
        raise SystemExit(__doc__)

    # An id is not derivable from a repository name -- the app may well be
    # called something else -- so an existing one is found by its repo URL.
    want = argv[0].rstrip("/").removesuffix(".git").lower()
    app = None
    for q in sorted(APPS.glob("*/app.json")):
        e = json.loads(q.read_text())
        if e["repo"].rstrip("/").lower() == want:
            app = e
            break

    # The only place app.json is ever written, and only when there is none:
    # a draft for a person to correct before committing it.
    fresh = app is None
    if fresh:
        app = new_entry(argv[0])

    print(app["id"])
    state = load_state(app["id"])
    scan(app, state, check)
    if check:
        print(json.dumps({"app": app, "latest": state}, indent=2))
        return 0
    if fresh:
        d = APPS / app["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "app.json").write_text(json.dumps(app, indent=2) + "\n")
        print("-> ", d / "app.json", "  (a draft; read it before committing)")
    print("->", save_state(app["id"], state))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
