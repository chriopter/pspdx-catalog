#!/usr/bin/env python3
"""Reads every repository on the list and writes the cache the console
fetches: one catalog.json, the pictures out of each EBOOT, and a page for
whoever lands on the site.

    look.py                    read repos.txt, write site/
    look.py --list <file>      another list
    look.py --out <dir>        write the site somewhere else

There is no state in this repository. The published `state.json` is what the
last run saw, so the comparison is against the live site, and a run that
finds nothing new publishes nothing, which is most hours. What the apps say
about themselves is read every time and kept nowhere: the next run derives
it all again.

An app is a GitHub repository that says so: a `.pspdx` file in its root, and
a release that carries one zip with an EBOOT.PBP in it. The file is the
author's consent and their words; everything that changes is derived from the
release and the EBOOT and never written by hand.

Nothing but the standard library, on purpose: this runs in a workflow and
should keep running in ten years. The `.pspdx` is checked by hand against the
rules in schema/v1.pspdx rather than handed to a validator module, for the
same reason, and because a reason that reads like a sentence is what an
author needs to fix their file."""
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

import page

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("GITHUB_TOKEN")
LIVE = os.environ.get("LIVE", "")

# The catalog names itself: a file found on a stick years from now says where
# it came from and which version of the format it is.
SCHEMA = "https://github.com/chriopter/pspdx/blob/master/manifest.md"

# What a .pspdx must say in its `schema` line to be a version 1 file. A
# version 2 gets a new name, so an old file is never wrong, only old.
PSPDX_SCHEMA = "https://github.com/chriopter/pspdx/blob/master/schema/v1.pspdx"

GITHUB = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")

# The rules out of schema/v1.pspdx, by hand. The category is one word for
# what this one app is, and the install directory is matched whole, because
# the schema's `$` is the end of the string and Python's is not quite.
CATEGORIES = ("game", "emulator", "app", "plugin", "demo")
INSTALLDIR = re.compile(r"PSP/GAME/[A-Za-z0-9_.-]{1,32}")

# The file's keys, which of them must be there, and the longest each string
# may be. The caps are the schema's: a name fits the XMB, a summary fits one
# line of a 480 pixel screen.
KEYS = ("schema", "name", "summary", "category", "license", "author", "installdir")
REQUIRED = ("schema", "name", "category", "installdir")
LIMITS = {"name": 39, "summary": 60, "license": 15, "author": 39}

# The whole archive is held in memory to hash it and read its index. GitHub
# allows 2 GB assets; a PSP package that size is a mistake.
MAX_ASSET = 256 * 1024 * 1024

# A .pspdx is a few lines. Anything bigger is not one.
MAX_PSPDX = 64 * 1024

# The eight sections of a PBP, in the order their offsets sit in the header.
# The console shows four of them and reads the title out of a fifth; the rest
# stay in the zip.
PBP = ("PARAM.SFO", "ICON0.PNG", "ICON1.PMF", "PIC0.PNG", "PIC1.PNG",
       "SND0.AT3", "DATA.PSP", "DATA.PSAR")
SECTIONS = {"ICON0.PNG": ("icon", ".png"),
            "PIC1.PNG": ("screenshot", ".png"),
            "ICON1.PMF": ("video", ".pmf"),
            "SND0.AT3": ("sound", ".at3")}

# Field -> where it is served and how big it may be. The caps exist because
# these are copied onto a public page and pulled by a console with 24 MB of
# RAM; the PBP format puts no limit on any of them. None of the four is
# required: a PBP that carries no sound is simply an app without one.
MEDIA = {"icon": ("icons", 64 * 1024),
         "screenshot": ("shots", 768 * 1024),
         "video": ("vids", 8 * 1024 * 1024),
         "sound": ("snd", 2 * 1024 * 1024)}

# What a file of each kind starts with, so that a section is what its name in
# the header claims and not whatever the author's packer put there.
MAGIC = {".png": b"\x89PNG\r\n\x1a\n", ".pmf": b"PSMF", ".at3": b"RIFF"}


class Problem(Exception):
    """One repository that cannot be listed. The rest of the list is still
    read and still published: an author breaking their release at night must
    not take the catalog down for everybody else."""


def ident(owner, repo):
    """The id, out of the repository URL and nothing else. Nobody types it,
    so it cannot be wrong, and a fork is its own app. Dashes and dots are
    dropped and the case with them, because the parts of a reverse domain
    name are [a-z0-9] here."""
    return "io.github." + ".".join(re.sub(r"[^a-z0-9]", "", part.lower())
                                   for part in (owner, repo))


def trim(text, limit=LIMITS["summary"]):
    """A summary cut mid-word reads like a bug. Cut on a space instead."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "..."


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# --- GitHub -----------------------------------------------------------------

def get(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "pspdx-catalog",
        "Accept": "application/vnd.github+json",
        **({"Authorization": "Bearer " + TOKEN} if TOKEN else {}),
    })
    with urllib.request.urlopen(request, timeout=30) as answer:
        return json.load(answer)


def api(path, what):
    """One small GET against api.github.com, as JSON. Every way it can fail
    is turned into a sentence about this one repository, because every one of
    them means this entry is left out and the run carries on."""
    try:
        return get("https://api.github.com" + path)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise Problem(f"{what}: GitHub has nothing at {path}") from None
        if e.code == 403 and e.headers.get("x-ratelimit-remaining") == "0":
            raise Problem(f"{what}: rate limited; set GITHUB_TOKEN") from None
        raise Problem(f"{what}: GitHub said {e.code} for {path}") from None
    except urllib.error.URLError as e:
        raise Problem(f"{what}: cannot reach GitHub: {e.reason}") from None
    except ValueError as e:
        raise Problem(f"{what}: GitHub sent no JSON for {path}: {e}") from None


def fetch(url, cap, what):
    """Bytes, never more than cap of them: one read of cap + 1 is enough to
    know the thing is too big without pulling all of it into memory."""
    request = urllib.request.Request(url, headers={"User-Agent": "pspdx-catalog"})
    try:
        with urllib.request.urlopen(request, timeout=300) as answer:
            data = answer.read(cap + 1)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise Problem(f"{what}: nothing at {url}") from None
        raise Problem(f"{what}: GitHub said {e.code} for {url}") from None
    except urllib.error.URLError as e:
        raise Problem(f"{what}: cannot reach {url}: {e.reason}") from None
    if len(data) > cap:
        raise Problem(f"{what}: over {cap} bytes")
    return data


def raw_url(owner, repo, ref, path):
    """A file on raw.githubusercontent.com, which is where the console reads
    it too: the same bytes from the same host, whether or not a cache ever
    looked."""
    return (f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/"
            + urllib.parse.quote(path))


# --- the list ---------------------------------------------------------------

def repos(path):
    """A line is a GitHub URL, and `@tag` after it pins a release.

    What can be wrong with a line is wrong with the list, not with anybody's
    repository, so it stops the run before anything is fetched: a curator
    wrote this file and can fix it."""
    name, seen, out = os.path.basename(path), {}, []
    for number, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        url, at, tag = line.partition("@")
        url = url.rstrip("/")
        found = GITHUB.fullmatch(url)
        if not found or len(line.split()) != 1:
            sys.exit(f"{name}:{number}: one GitHub repository URL a line")
        if at and not tag:
            sys.exit(f"{name}:{number}: @ with no tag after it")
        owner, repo = found.group(1), found.group(2)
        # The same repository twice would be the same app twice in the
        # catalog, and so would two repositories whose names come out as one
        # id once the dashes and the case are dropped. Both are the list's
        # mistake and are known before anything is fetched.
        slug, one = f"{owner}/{repo}".lower(), ident(owner, repo)
        if slug in seen:
            sys.exit(f"{name}:{number}: {slug} is listed twice")
        if one in seen:
            sys.exit(f"{name}:{number}: {slug} and {seen[one]} are both {one}")
        seen[slug] = seen[one] = slug
        out.append((url, owner, repo, tag))
    # The whole list is read before the first repository is fetched, so that
    # a typo on the last line is not found half an hour into a run.
    if not out:
        sys.exit(f"{name}: lists nothing")
    return out


# --- the file ---------------------------------------------------------------

def validate(data):
    """The rules of schema/v1.pspdx, one at a time, and the first one broken
    as a Problem. Written out rather than fed to a validator so that the
    reason reads like a sentence: a misspelt key is named, a long summary
    says how long it may be."""
    if not isinstance(data, dict):
        raise Problem(".pspdx is not a JSON object")
    for key in data:
        if key not in KEYS:
            raise Problem(f".pspdx: {key!r} is not a field; "
                          "the fields are " + ", ".join(KEYS))
    for key in REQUIRED:
        if key not in data:
            raise Problem(f".pspdx: no {key!r}")
    if data["schema"] != PSPDX_SCHEMA:
        raise Problem(f'.pspdx: "schema" must be {PSPDX_SCHEMA}')
    for key, limit in LIMITS.items():
        if key in data:
            value = data[key]
            if not isinstance(value, str):
                raise Problem(f".pspdx: {key!r} is not a string")
            if len(value) > limit:
                raise Problem(f".pspdx: {key!r} is {len(value)} characters, "
                              f"at most {limit}")
    if not data["name"]:
        raise Problem('.pspdx: "name" is empty')
    if data["category"] not in CATEGORIES:
        raise Problem('.pspdx: "category" is one of ' + ", ".join(CATEGORIES))
    if not isinstance(data["installdir"], str) \
            or not INSTALLDIR.fullmatch(data["installdir"]):
        raise Problem('.pspdx: "installdir" is PSP/GAME/ and 1 to 32 of '
                      "[A-Za-z0-9_.-], and nothing else in version 1")
    return data


def read_pspdx(owner, repo, ref):
    """The repository's .pspdx at ref, validated, or the reason there is
    none. A repository without one is not listed, by any list: the file is
    the consent."""
    try:
        raw = fetch(raw_url(owner, repo, ref, ".pspdx"), MAX_PSPDX, ".pspdx")
    except Problem as ex:
        if "nothing at" in str(ex):
            # At a pinned tag the file is missing as often as the tag is, so
            # the tag is named.
            raise Problem("no .pspdx" + (f" at {ref}" if ref != "HEAD" else "")) from None
        raise
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise Problem(".pspdx is not UTF-8") from None
    except ValueError as e:
        raise Problem(f".pspdx is not JSON: {e}") from None
    return validate(data)


# --- the package ------------------------------------------------------------

def eboot(archive):
    """Where the one EBOOT.PBP sits in the zip, and the directory holding it,
    which is the package. One archive is one package: two EBOOTs are a
    question for the author, and the run cannot guess which of them the
    install would copy."""
    # A zip written on Windows carries backslashes, and without this a path
    # inside a directory looks like a name at the root.
    members = [(name.replace("\\", "/"), name) for name in archive.namelist()]
    found = [(path, name) for path, name in members
             if path.lower().endswith("eboot.pbp")]
    if not found:
        raise Problem("no EBOOT.PBP in the zip")
    if len(found) > 1:
        raise Problem(f"{len(found)} EBOOT.PBP in the zip: "
                      + ", ".join(sorted(path for path, _ in found)))
    path, name = found[0]
    if path.startswith("/") or ".." in path.split("/"):
        raise Problem(f"the zip puts its EBOOT at {path!r}")
    return name, (path.rsplit("/", 1)[0] + "/" if "/" in path else "")


def pbp_sections(f):
    """The sections before DATA.PSP, out of an open EBOOT.PBP, by name.

    A PBP is a header of eight little-endian offsets and the sections laid end
    to end in that order, so a section is empty when its offset equals the
    next one. Everything the console shows sits before DATA.PSP, which is why
    only that much of the file is read: the PSAR behind it is the whole game.
    """
    head = f.read(40)
    if len(head) < 40 or head[:4] != b"\0PBP":
        raise Problem("EBOOT.PBP does not start with a PBP header")
    offsets = struct.unpack("<8I", head[8:40])
    if list(offsets) != sorted(offsets) or offsets[0] < 40:
        raise Problem("EBOOT.PBP has its sections out of order")
    body = f.read(offsets[6] - 40)
    out = {}
    for i, section in enumerate(PBP[:6]):
        start, end = offsets[i] - 40, offsets[i + 1] - 40
        if end > start:
            out[section] = body[start:end]
    return out


def sfo_strings(data):
    """The string values out of a PARAM.SFO, by key; empty when malformed.

    The SFO is a header, an index of 16-byte entries, a table of key names
    and a table of values; each entry says where its key and its value sit in
    those tables. Only the strings are wanted, TITLE and CATEGORY among them,
    so the integers are walked past. Anything malformed is treated as no
    entries: the caller then says what is missing, which is more useful than
    a traceback about an author's build tool.
    """
    out = {}
    if len(data) < 20 or data[:4] != b"\0PSF":
        return out
    keys, values, count = struct.unpack("<III", data[8:20])
    for i in range(count):
        entry = data[20 + 16 * i:36 + 16 * i]
        if len(entry) < 16:
            return {}
        key_off, fmt, length, _, value_off = struct.unpack("<HHIII", entry)
        end = data.find(b"\0", keys + key_off)
        if end < 0:
            return {}
        if fmt != 0x0204:
            continue
        key = data[keys + key_off:end].decode("ascii", "replace")
        raw = data[values + value_off:values + value_off + length]
        # The string is stored with its terminator inside `length`, and a tool
        # that pads the value pads it with more of them.
        out[key] = raw.split(b"\0", 1)[0].decode("utf-8", "replace").strip()
    return out


def package(asset):
    """Downloads the zip GitHub named, checks it is the size GitHub said, and
    returns (sha256, the package directory, the SFO, the PBP sections). This
    is the part the console cannot afford and the reason the cache exists."""
    if asset["size"] > MAX_ASSET:
        raise Problem(f"{asset['name']} is {asset['size']} bytes, "
                      f"over the {MAX_ASSET} cap")
    print(f"  fetching {asset['name']}, {asset['size']} bytes")
    raw = fetch(asset["browser_download_url"], asset["size"], asset["name"])
    # GitHub says how big the asset is before it is fetched, so a short or a
    # padded answer is caught here rather than as a puzzling zip error.
    if len(raw) != asset["size"]:
        raise Problem(f"{asset['name']}: got {len(raw)} bytes, "
                      f"GitHub said {asset['size']}")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as e:
        raise Problem(f"{asset['name']} is not a zip: {e}") from None
    name, root = eboot(archive)
    with archive.open(name) as f:
        sections = pbp_sections(f)
    sfo = sfo_strings(sections.get("PARAM.SFO", b""))
    if not sfo.get("TITLE"):
        raise Problem("no TITLE in the EBOOT's PARAM.SFO")
    # MG is a game or app for the Memory Stick, the one kind that unpacks
    # under PSP/GAME/ and runs from there. A PBP that says otherwise is a
    # theme, a save or a UMD's, and no install would run it.
    if sfo.get("CATEGORY") != "MG":
        raise Problem("the EBOOT's PARAM.SFO says CATEGORY "
                      f"{sfo.get('CATEGORY', '')!r}, not 'MG'")
    return sha256(raw), root, sfo, sections


def pictures(sections):
    """The icon, the picture, the film and the sound out of the PBP, each one
    only if it is what the header calls it and small enough to serve. Returns
    (media, notes): a section that fails neither delists the app nor is
    published, because a sound loop that is too long is not a reason to
    vanish from the list."""
    media, notes = {}, []
    for section, (field, suffix) in SECTIONS.items():
        if section not in sections:
            continue
        data = sections[section]
        cap = MEDIA[field][1]
        if len(data) > cap:
            notes.append(f"{section} is {len(data)} bytes, the limit is {cap}; left out")
        elif not data.startswith(MAGIC[suffix]):
            notes.append(f"{section} is not a {suffix[1:]} file; left out")
        else:
            media[field] = (suffix, data)
    return media, notes


# --- one entry --------------------------------------------------------------

def entry(url, owner, repo, tag):
    """The app as the catalog carries it, or a Problem saying why it is not
    listed."""
    ref = tag or "HEAD"
    # The file first: a repository without one is not an app, and nothing
    # else needs asking.
    spec = read_pspdx(owner, repo, ref)
    meta = api(f"/repos/{owner}/{repo}", "repository")
    where = (f"/releases/tags/{urllib.parse.quote(tag)}" if tag
             else "/releases/latest")
    release = api(f"/repos/{owner}/{repo}{where}", "release")
    if not isinstance(meta, dict) or not isinstance(release, dict) \
            or "tag_name" not in release:
        raise Problem("GitHub answered with something other than a repository "
                      "and a release")
    # /releases/latest never answers with one of these; a pinned tag can.
    if release.get("draft") or release.get("prerelease"):
        raise Problem(f"{release['tag_name']} is a draft or a pre-release")

    zips = [a for a in release.get("assets", [])
            if a["name"].lower().endswith(".zip")]
    if not zips:
        raise Problem(f"{release['tag_name']} has no zip attached")
    if len(zips) > 1:
        raise Problem(f"{release['tag_name']} has {len(zips)} zips: "
                      + ", ".join(a["name"] for a in zips)
                      + "; one release is one package")
    asset = zips[0]
    try:
        published = datetime.fromisoformat(
            release["published_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Problem("the release has no published_at") from None

    sha, root, sfo, sections = package(asset)
    # The package and the title are said out loud rather than served: the
    # console copies the package into installdir and reads the title off the
    # stick, and whoever reads this log is looking for the zip's own shape.
    print(f"  {root or 'the zip itself'} is the package, "
          f"PARAM.SFO says {sfo['TITLE']!r}")
    media, notes = pictures(sections)
    for note in notes:
        print(f"  {note}")

    # The licence GitHub reports when it recognises the file; NOASSERTION is
    # its word for a file it cannot place, and that is no licence to list.
    spdx = (meta.get("license") or {}).get("spdx_id") or ""
    if spdx == "NOASSERTION":
        spdx = ""

    # The file wins over what was derived: what it says, it says on purpose,
    # for the summary GitHub's description gets wrong or the licence GitHub
    # cannot see.
    app = {
        "id": ident(owner, repo),
        "name": spec["name"],
        "author": spec.get("author", owner),
        "summary": spec.get("summary", trim(meta.get("description") or "")),
        "category": spec["category"],
        "license": spec.get("license", spdx),
        "repo": url,
        "installdir": spec["installdir"],
        "release": {
            "rev": int(published.timestamp()),
            "url": asset["browser_download_url"],
            "sha256": sha,
            "size": asset["size"],
            "version": release["tag_name"].removeprefix("v"),
        },
        "_media": media,
        "_page": release.get("html_url", url + "/releases"),
        "_tag": release["tag_name"],
        "_published": release["published_at"],
    }
    return app


# --- the site ---------------------------------------------------------------

def write_site(apps, broken, state, out):
    for subdir, _ in MEDIA.values():
        # Whatever a previous run left here is not evidence that the file is
        # still in anybody's EBOOT.
        shutil.rmtree(os.path.join(out, subdir), ignore_errors=True)
    for app in apps:
        for field, (suffix, data) in app.pop("_media").items():
            subdir, _ = MEDIA[field]
            # The name carries the bytes: a client caches a picture by the
            # name it was fetched under and never asks again, so a changed
            # icon or clip has to arrive under a new name or it never arrives.
            served = f"{app['id']}-{sha256(data)[:8]}{suffix}"
            os.makedirs(os.path.join(out, subdir), exist_ok=True)
            with open(os.path.join(out, subdir, served), "wb") as picture:
                picture.write(data)
            app[field] = f"{subdir}/{served}"

    catalog = {
        "schema": SCHEMA,
        "generated": state["generated"],
        "apps": [{k: v for k, v in app.items() if not k.startswith("_")}
                 for app in apps],
    }
    # Compact separators: the console holds this in RAM, and a PSP has 24 MB.
    text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out, "catalog.json"), "w", encoding="utf-8") as file:
        file.write(text + "\n")
    with open(os.path.join(out, "state.json"), "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)
        file.write("\n")
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as file:
        file.write(page.render(catalog, apps, broken))

    have = ", ".join(f"{sum(field in app for app in apps)} {field}s"
                     for field in MEDIA)
    print(f"{len(apps)} app{'' if len(apps) == 1 else 's'}, {have}, "
          f"{len(text)} bytes -> " + os.path.join(out, "catalog.json"))


def hashed(*paths):
    """One digest over some files, so that a change in any of them is a
    change."""
    digest = hashlib.sha256()
    for path in paths:
        with open(path, "rb") as file:
            digest.update(file.read())
    return digest.hexdigest()


def output(name, value):
    """A line for the workflow, when there is a workflow to read it."""
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"{name}={value}\n")


def main(argv):
    listing, out = os.path.join(HERE, "repos.txt"), os.path.join(HERE, "site")
    while argv:
        if argv[0] == "--list" and len(argv) > 1:
            listing = os.path.abspath(argv[1])
        elif argv[0] == "--out" and len(argv) > 1:
            out = os.path.abspath(argv[1])
        else:
            raise SystemExit(__doc__)
        argv = argv[2:]

    state = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # The list and the code decide what the catalog says as much as the
        # releases do, so a line added to one or a rule changed in the other
        # has to reach the site even in an hour when nobody released anything.
        "list": hashed(listing),
        "code": hashed(os.path.abspath(__file__), os.path.abspath(page.__file__)),
        "repos": {},
    }

    apps, broken = [], []
    for url, owner, repo, tag in repos(listing):
        label = url + (f"@{tag}" if tag else "")
        print(label)
        # Everything sits inside the try: one broken release must not end the
        # run before the rest of the list has been looked at.
        try:
            app = entry(url, owner, repo, tag)
            print(f"  {app['id']} {app['release']['version']}: {app['name']!r}, "
                  + (", ".join(sorted(app["_media"])) or "nothing in the PBP"))
        except Problem as ex:
            app = None
            print(f"  {ex}")
            broken.append((label, str(ex)))
        except Exception as ex:
            app = None
            print(f"  {type(ex).__name__}: {ex}")
            broken.append((label, f"{type(ex).__name__}: {ex}"))
        # The memory is the release of every repository that is listed, and
        # nothing for one that is not: a repository whose file or zip is
        # broken looks the same every hour and stays quiet, and the hour it
        # is mended its release appears here and the site is written again.
        state["repos"][f"{owner}/{repo}"] = {
            "tag": app["_tag"] if app else None,
            "published": app["_published"] if app else None,
        }
        if app:
            apps.append(app)

    apps.sort(key=lambda app: app["id"])

    # The one thing that decides whether anything is published: what is on
    # the site now, minus the time it says it was made.
    changed = "yes"
    try:
        with urllib.request.urlopen(LIVE, timeout=30) as answer:
            live = json.load(answer)
        if all(live.get(key) == value for key, value in state.items()
               if key != "generated"):
            changed = "no"
    except Exception:
        pass

    if changed == "yes" and not apps:
        # Every repository failing at once is far more likely to be GitHub
        # having a bad minute than every author breaking at once, and an
        # empty catalog would uninstall nothing but would list nothing
        # either. The site that is already up is the better answer.
        print("no app could be derived; leaving the published catalog alone")
        changed = "no"
    if changed == "yes":
        os.makedirs(out, exist_ok=True)
        write_site(apps, broken, state, out)

    for label, why in broken:
        print(f"left out: {label}: {why}")
    print("changed:", changed)
    output("changed", changed)
    # The job fails on this afterwards, so that a broken entry is visible as
    # a red run without keeping the rest of the catalog off the site.
    output("left_out", len(broken))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
