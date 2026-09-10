#!/usr/bin/env python3
"""Fills in what a release is, so that nobody has to type a sha256.

Most PSP homebrew was published once and left alone, and its author is never
going to maintain a file for us. So the index looks: it asks GitHub what the
newest release is, downloads the archive, hashes the bytes it actually got,
and looks inside to see where the EBOOT sits.

    scan.py https://github.com/user/repo   add that repository
    scan.py --all                          refresh every entry
    scan.py --all --check                  report what would change, write nothing
    scan.py --listed <url>                 exit 0 if that repository is listed

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
GITHUB = re.compile(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")

# A release with several assets has to be told apart; one .zip needs no rule.
DEFAULT_ASSET = "*.zip"

# The whole archive is held in memory to hash it and read its index.
# GitHub allows 2 GB assets; a PSP package that size is a mistake.
MAX_ASSET = 256 * 1024 * 1024


def _token():
    """gh's token if there is one. Unauthenticated works, just 60 calls an hour."""
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        return out.stdout.strip() or None
    except FileNotFoundError:
        return None


TOKEN = _token()          # once: this used to spawn gh twice per app per run


def api(path):
    """One small GET. Conditional requests were tried and dropped: the release
    JSON carries each asset's download_count, so its ETag changes whenever
    anybody downloads anything, and a 304 almost never arrives."""
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404 and path.endswith("/releases/latest"):
            raise SystemExit("  no releases yet") from None
        if e.code == 404:
            raise SystemExit("  no such repository, or it is private") from None
        if e.code == 403 and e.headers.get("x-ratelimit-remaining") == "0":
            raise SystemExit("  rate limited; set GITHUB_TOKEN") from None
        raise SystemExit(f"  GitHub said {e.code} for {path}") from None
    except urllib.error.URLError as e:
        raise SystemExit(f"  cannot reach GitHub: {e.reason}") from None


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pspdx-scan"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def pick_asset(release, pattern):
    names = [a for a in release.get("assets", [])
             if fnmatch.fnmatch(a["name"].lower(), pattern.lower())]
    if len(names) == 1:
        return names[0]
    have = [a["name"] for a in release.get("assets", [])]
    if not have:
        raise SystemExit(f"  {release['tag_name']} has no assets attached")
    if not names:
        raise SystemExit(f"  no asset matches {pattern!r}; release has "
                         + ", ".join(have) + "\n  set \"asset\" in app.json")
    raise SystemExit(f"  {len(names)} assets match {pattern!r}: "
                     + ", ".join(a["name"] for a in names)
                     + "\n  narrow \"asset\" in app.json")


def eboot_root(raw):
    """Where the package sits inside the archive.

    The shallowest EBOOT.PBP wins and its directory is the package -- of
    sixteen surveyed archives that hold an EBOOT, ten put it one directory
    down, three at the root and only two under PSP/GAME/. An empty root means
    the archive is the package.
    """
    z = zipfile.ZipFile(io.BytesIO(raw))
    # A zip written on Windows carries backslashes, and without this the depth
    # test sees one component and calls every layout the root.
    ebs = [n.replace("\\", "/") for n in z.namelist()
           if n.lower().endswith("eboot.pbp")]
    if not ebs:
        raise SystemExit("  no EBOOT.PBP in the archive")
    key = lambda n: (n.count("/"), len(n))
    ebs.sort(key=key)
    tied = [n for n in ebs if key(n) == key(ebs[0])]
    if len(tied) > 1:
        raise SystemExit("  two EBOOT.PBP at the same depth: "
                         + ", ".join(tied) + "\n  one archive is one package")
    path = ebs[0]
    if path.startswith("/") or ".." in path.split("/"):
        raise SystemExit(f"  the archive puts its EBOOT at {path!r}")
    return path.rsplit("/", 1)[0] + "/" if "/" in path else ""


def scan(app, state, check=False):
    """Refreshes `state` from the newest release. Never touches `app`."""
    m = GITHUB.match(app["repo"])
    if not m:
        raise SystemExit(f"  {app['repo']} is not a GitHub repository")
    owner, repo = m.group(1), m.group(2)

    rel = api(f"/repos/{owner}/{repo}/releases/latest")

    # published_at does not move when an author deletes an asset and uploads a
    # replacement under the same tag. Watching only that leaves the catalog
    # serving a checksum for bytes nobody can download any more, for ever.
    stamps = [rel["published_at"]] + [a["updated_at"] for a in rel.get("assets", [])]
    published = max(int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())
                    for t in stamps)
    if state.get("seen") == published:
        return False

    asset = pick_asset(rel, app.get("asset", DEFAULT_ASSET))
    if asset["size"] > MAX_ASSET:
        raise SystemExit(f"  {asset['name']} is {asset['size']} bytes, over the "
                         f"{MAX_ASSET} cap")
    raw = fetch(asset["browser_download_url"])
    if len(raw) != asset["size"]:
        raise SystemExit(f"  {asset['name']}: got {len(raw)} bytes, GitHub said "
                         f"{asset['size']}")
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
        "version": rel["tag_name"].removeprefix("v"),
        "url": asset["browser_download_url"],
        "sha256": sha,
        "size": asset["size"],
        "root": root,
    })
    return True


def clean(part):
    return re.sub(r"[^a-z0-9]", "", part.lower())


def trim(text, limit=60):
    """A summary cut mid-word reads like a bug. Cut on a space instead."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "..."


def new_entry(url):
    m = GITHUB.match(url)
    if not m:
        raise SystemExit(f"{url} is not a GitHub repository")
    owner, repo = m.group(1), m.group(2)
    meta = api(f"/repos/{owner}/{repo}")
    lic = (meta.get("license") or {}).get("spdx_id")
    return {
        "id": "io.github.{}.{}".format(clean(owner), clean(repo)),
        "name": repo.replace("-", " ").replace("_", " ").title(),
        "author": owner,
        "summary": trim(meta.get("description") or ""),
        "category": "apps",
        "license": lic if lic and lic != "NOASSERTION" else "",
        "repo": f"https://github.com/{owner}/{repo}",
    }


def save_state(d, state):
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "latest.json.new"
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(d / "latest.json")            # never a half-written file
    return d / "latest.json"


def load_state(d):
    p = d / "latest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def main(argv):
    check = "--check" in argv
    argv = [a for a in argv if a != "--check"]

    if argv and argv[0] == "--all":
        changed, broken = [], []
        for p in sorted(APPS.glob("*/app.json")):
            # Reading and printing sit inside the try as well: one unparseable
            # app.json used to abort the run before anything else was scanned.
            try:
                app = json.loads(p.read_text())
                if app.get("scan") is False:
                    continue
                print(app["id"])
                state = load_state(p.parent)
                if scan(app, state, check):
                    changed.append(p.parent.name)
                    if not check:
                        save_state(p.parent, state)
            except SystemExit as e:
                print(str(e))
                broken.append(f"{p.parent.name}:{e}")
            except Exception as e:
                print(f"  {p.parent.name}: {type(e).__name__}: {e}")
                broken.append(f"{p.parent.name}: {type(e).__name__}: {e}")
        print(f"{len(changed)} changed" + (": " + ", ".join(changed) if changed else ""))
        # A commit that says which packages moved beats four identical ones.
        out = os.environ.get("GITHUB_OUTPUT")
        if out and changed:
            names = []
            for c in changed:
                try:
                    names.append(json.loads((APPS / c / "app.json").read_text())["name"])
                except Exception:
                    names.append(c)
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

    listed_only = argv[0] == "--listed"
    if listed_only:
        argv = argv[1:]
        if not argv:
            raise SystemExit(__doc__)

    # An id is not derivable from a repository name -- the app may well be
    # called something else -- so an existing one is found by its repo URL.
    def norm(u):
        return u.rstrip("/").removesuffix(".git").lower()

    want, found = norm(argv[0]), []
    for q in sorted(APPS.glob("*/app.json")):
        try:
            e = json.loads(q.read_text())
        except Exception as exc:
            raise SystemExit(f"{q.parent.name}/app.json: {exc}")
        if norm(e.get("repo", "")) == want:
            found.append((q.parent, e))
    if len(found) > 1:
        raise SystemExit("  listed twice: "
                         + ", ".join(d.name for d, _ in found))

    if listed_only:
        return 0 if found else 1

    fresh = not found
    if fresh:
        app = new_entry(argv[0])
        d = APPS / app["id"]
    else:
        d, app = found[0]

    if app.get("scan") is False:
        raise SystemExit(f"  {app['id']} is pinned with \"scan\": false")

    print(app["id"])
    state = load_state(d)
    scan(app, state, check)
    if check:
        print(json.dumps({"app": app, "latest": state}, indent=2))
        return 0
    if fresh:
        d.mkdir(parents=True, exist_ok=True)
        (d / "app.json").write_text(json.dumps(app, indent=2) + "\n")
        print("-> ", d / "app.json", "  (a draft; read it before committing)")
    print("->", save_state(d, state))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
