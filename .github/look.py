#!/usr/bin/env python3
"""Reads every repository on the list and writes the cache the console
fetches: one catalog.json, the pictures out of each EBOOT, and a page for
whoever lands on the site.

    look.py                    read repos.txt, write site/
    look.py --list <file>      another list
    look.py --out <dir>        write the site somewhere else

    LIVE=<url>                 the published catalog.json, which is the memory
    FORCE=1                    forget it and read everything again
    GITHUB_TOKEN=<token>       raises the rate limit; a run needs one

There is no state in this repository. The published `catalog.json` is the
memory: a repository whose release is the one already in it is copied out of
it and nothing of that app is fetched, and a run that ends with the same
catalog publishes nothing, which is most hours. That is the whole saving,
and it is the only reason this can run hourly over a list with a 44 MB port
on it.

What it costs is one thing: an author who edits their `.pspdx` and publishes
no release is not noticed until they do. That is accepted, and `FORCE=1`
reads everything from scratch for the hours when it is not.

An app is a GitHub repository that says so: a `.pspdx` file in its root, and
a release that carries one zip with an EBOOT.PBP in it. The file is the
author's consent and their words; everything that changes is derived from the
release and the EBOOT and never written by hand.

Nothing but the standard library, on purpose: this runs in a workflow and
should keep running in ten years. The `.pspdx` is checked by hand against the
rules in schema/v1.pspdx rather than handed to a validator module, for the
same reason, and because a reason that reads like a sentence is what an
author needs to fix their file."""
import concurrent.futures
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

# The catalog that is up now: the memory, and the thing the new one is
# compared against. Empty, unreachable or FORCE=1 all mean the same thing,
# which is what the first run does anyway: read everything.
LIVE = os.environ.get("LIVE", "")
FORCE = os.environ.get("FORCE", "") == "1"

# How many repositories are asked at once. A quiet hour is one small API call
# an app and nothing else, and asking them one after another is a minute of
# waiting for a list that will one day be long. Eight is polite to GitHub and
# plenty: the wait is the network, not this process.
WORKERS = 8

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
INSTALLDIR = re.compile(r"PSP/GAME/(?!\.{1,2}$)[A-Za-z0-9_.-]{1,32}")

# The file's keys, which of them must be there, and the longest each string
# may be. The caps are the schema's: a name fits the XMB, a summary fits one
# line of a 480 pixel screen.
KEYS = ("schema", "name", "summary", "category", "license", "author", "installdir")
REQUIRED = ("schema", "name", "category", "installdir")
LIMITS = {"name": 39, "summary": 60, "license": 64, "author": 39}

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

# Field -> what it is called beside the app's page, and how big it may be.
# The caps exist because these are copied onto a public page and pulled by a
# console with 24 MB of RAM; the PBP format puts no limit on any of them.
# None of the four is required: a PBP that carries no sound is simply an app
# without one.
MEDIA = {"icon": ("icon", 64 * 1024),
         "screenshot": ("picture", 768 * 1024),
         "video": ("film", 8 * 1024 * 1024),
         "sound": ("sound", 2 * 1024 * 1024)}

# Everything about one app lives in one directory, named by its id: its page,
# its four files and the .pspdx the run read. A reader can see the whole of
# an app in one listing, and a run deletes the lot and writes it again.
APPS = "apps"

# The .pspdx as it was read, mirrored beside the page, so that what the
# catalog used is readable next to what the repository says today.
READ = "read.pspdx"

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
                      "[A-Za-z0-9_.-], excluding . and .., in version 1")
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
    # The bytes come back with the parsed file: what the catalog used is
    # mirrored beside the app's page, and a copy is only honest if it is the
    # copy that was read.
    return validate(data), raw


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
             if path.rsplit("/", 1)[-1].lower() == "eboot.pbp"]
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


def package(asset, log):
    """Downloads the zip GitHub named, checks it is the size GitHub said, and
    returns (sha256, the package directory, the SFO, the PBP sections). This
    is the part the console cannot afford and the reason the cache exists.

    What it has to say goes on `log` rather than to the screen: several of
    these run at once, and a log with two repositories talking over each
    other is no log."""
    if asset["size"] > MAX_ASSET:
        raise Problem(f"{asset['name']} is {asset['size']} bytes, "
                      f"over the {MAX_ASSET} cap")
    log.append(f"fetching {asset['name']}, {asset['size']} bytes")
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

def again(known, ref, owner, repo, release):
    """The entry out of the published catalog, word for word, and no media
    yet: whether this run publishes at all is not known while the list is
    being walked, and an hour that publishes nothing should cost nothing.
    `complete` fetches the files afterwards, for the runs that do.

    Nothing here is derived a second time: the release is the one that was
    read the day this entry was written, so re-reading the .pspdx and the zip
    could only produce the same object at the cost of the whole download."""
    app = dict(known)
    app["_pspdx"] = raw_url(owner, repo, ref, ".pspdx")
    app["_page"] = release.get("html_url", app["repo"] + "/releases")
    # No `_said`: which fields the author wrote and which fell back to GitHub
    # is in the .pspdx, which was not read. The page shows no origin for them
    # rather than guessing at one.
    return app


def served(known):
    """Everything the published site holds beside this entry's page, fetched
    back: its media in the shape a fresh read produces, and the .pspdx the
    run that wrote it read. Anything gone, too big or not what it claims is a
    Problem, and the caller then reads the app the long way, which puts all
    of it back."""
    if not LIVE:
        raise Problem("no published catalog to copy the files from")
    media = {}
    for field, (_, cap) in MEDIA.items():
        if field not in known:
            continue
        where = urllib.parse.urljoin(LIVE, known[field])
        data = fetch(where, cap, f"the published {field}")
        suffix = os.path.splitext(known[field])[1]
        if suffix not in MAGIC or not data.startswith(MAGIC[suffix]):
            raise Problem(f"the published {field} is not a {suffix} file")
        media[field] = (suffix, data)
    raw = fetch(urllib.parse.urljoin(LIVE, f"{APPS}/{known['id']}/{READ}"),
                MAX_PSPDX, f"the published {READ}")
    return media, raw


def entry(url, owner, repo, tag, known):
    """The app as the catalog carries it and the lines the log should show
    for it, or a Problem saying why it is not listed. `known` is what the
    published catalog says about this id, and is used when the release it
    names is still the release GitHub names.

    Several of these run at once, so it says nothing itself: what it has to
    report it hands back, and the caller prints it in the list's order."""
    log = []
    ref = tag or "HEAD"
    # The release first, because it is the cheap question that decides
    # whether any of the expensive ones have to be asked at all.
    where = (f"/releases/tags/{urllib.parse.quote(tag)}" if tag
             else "/releases/latest")
    release = api(f"/repos/{owner}/{repo}{where}", "release")
    if not isinstance(release, dict) or "tag_name" not in release:
        raise Problem("GitHub answered with something other than a release")
    # /releases/latest never answers with one of these; a pinned tag can.
    if release.get("draft") or release.get("prerelease"):
        raise Problem(f"{release['tag_name']} is a draft or a pre-release")
    try:
        published = datetime.fromisoformat(
            release["published_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Problem("the release has no published_at") from None
    version = release["tag_name"].removeprefix("v")
    rev = int(published.timestamp())

    # The same version published at the same second is the same release, and
    # the same release is the same package: what the catalog says about it
    # cannot have changed without the author publishing again.
    was = (known or {}).get("release", {})
    if known and was.get("version") == version and was.get("rev") == rev:
        return again(known, ref, owner, repo, release), [f"unchanged, {version}"]

    spec, raw = read_pspdx(owner, repo, ref)
    meta = api(f"/repos/{owner}/{repo}", "repository")
    if not isinstance(meta, dict):
        raise Problem("GitHub answered with something other than a repository")

    zips = [a for a in release.get("assets", [])
            if a["name"].lower().endswith(".zip")]
    if not zips:
        raise Problem(f"{release['tag_name']} has no zip attached")
    if len(zips) > 1:
        raise Problem(f"{release['tag_name']} has {len(zips)} zips: "
                      + ", ".join(a["name"] for a in zips)
                      + "; one release is one package")
    asset = zips[0]

    sha, root, sfo, sections = package(asset, log)
    # The package and the title are said out loud rather than served: the
    # console copies the package into installdir and reads the title off the
    # stick, and whoever reads this log is looking for the zip's own shape.
    log.append(f"{root or 'the zip itself'} is the package, "
               f"PARAM.SFO says {sfo['TITLE']!r}")
    media, notes = pictures(sections)
    log.extend(notes)

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
            "rev": rev,
            "url": asset["browser_download_url"],
            "sha256": sha,
            "size": asset["size"],
            "version": version,
        },
        "_media": media,
        "_raw": raw,
        # Where the file that consented to all of this can be read, at the ref
        # it was read at. The page links it so that whoever wonders where a
        # name or a summary came from reads it at its source.
        "_pspdx": raw_url(owner, repo, ref, ".pspdx"),
        # Which of the words above the author actually wrote: the optional
        # three fall back to GitHub, and a page that shows where a fact came
        # from has to know which of the two it was.
        "_said": sorted(spec),
        "_page": release.get("html_url", url + "/releases"),
    }
    log.append(f"{app['id']} {version}: {app['name']!r}, "
               + (", ".join(sorted(media)) or "nothing in the PBP"))
    return app, log


# --- the site ---------------------------------------------------------------

def shape(apps, generated):
    """Where each media file will be served, and the catalog that says so.

    Everything of one app sits in one directory named by its id, and the
    name of each file still carries its bytes: a client caches a picture by
    the name it was fetched under and never asks again, so a changed icon has
    to arrive under a new name or it never arrives. The same bytes therefore
    land on the same name, which is why an entry copied out of the published
    catalog keeps the paths it already has.

    Nothing is written here, because this is also what the run compares
    against the published catalog before deciding to write anything at all."""
    for app in apps:
        for field, (suffix, data) in app.get("_media", {}).items():
            called, _ = MEDIA[field]
            app[field] = (f"{APPS}/{app['id']}/"
                          f"{called}-{sha256(data)[:8]}{suffix}")
    return {
        "schema": SCHEMA,
        "generated": generated,
        "apps": [{k: v for k, v in app.items() if not k.startswith("_")}
                 for app in apps],
    }


def write_site(apps, broken, catalog, out):
    # Whatever a previous run left here is not evidence that any of it is
    # still in anybody's EBOOT, or that the app is still on the list.
    shutil.rmtree(os.path.join(out, APPS), ignore_errors=True)
    for app in apps:
        home = os.path.join(out, APPS, app["id"])
        os.makedirs(home, exist_ok=True)
        for field, (_, data) in app.pop("_media", {}).items():
            with open(os.path.join(out, *app[field].split("/")), "wb") as file:
                file.write(data)
        with open(os.path.join(home, READ), "wb") as file:
            file.write(app.pop("_raw"))

    # Compact separators: the console holds this in RAM, and a PSP has 24 MB.
    text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out, "catalog.json"), "w", encoding="utf-8") as file:
        file.write(text + "\n")
    # The site is more than one file now: the tiles, a page an app, and the
    # style and the wave they share, so the pages write themselves. It comes
    # after the pictures because a page measures the film and the sound where
    # they have just been written.
    page.render(catalog, apps, broken, out)

    have = ", ".join(f"{sum(field in app for app in apps)} {field}s"
                     for field in MEDIA)
    print(f"{len(apps)} app{'' if len(apps) == 1 else 's'}, {have}, "
          f"{len(text)} bytes -> " + os.path.join(out, "catalog.json"))


def memory():
    """The catalog that is published now, which is the only memory there is,
    or None when there is none to be had: the first run, an unreachable site,
    something that is not a catalog, or a run told to forget."""
    if FORCE:
        print("FORCE=1: reading every repository from scratch")
        return None
    if not LIVE:
        return None
    try:
        request = urllib.request.Request(LIVE, headers={"User-Agent": "pspdx-catalog"})
        with urllib.request.urlopen(request, timeout=30) as answer:
            live = json.load(answer)
    except Exception as ex:
        print(f"no catalog at {LIVE} ({ex}); reading every repository")
        return None
    if not isinstance(live, dict) or not isinstance(live.get("apps"), list):
        print(f"what is at {LIVE} is not a catalog; reading every repository")
        return None
    return live


def unlike(catalog, live):
    """Whether the new catalog says anything the published one does not. The
    minute it was made is not something it says: two runs an hour apart that
    found the same releases are the same catalog."""
    if live is None:
        return True
    return ({k: v for k, v in catalog.items() if k != "generated"}
            != {k: v for k, v in live.items() if k != "generated"})


def walk(lines, known):
    """Every repository on the list, asked at once and reported in the
    list's order: the result of each is printed when it is collected, not
    from inside the thread that found it, so a log still reads top to bottom.

    One broken repository never ends the run, here as everywhere: the reason
    is kept, the rest of the list is still read, and what could be derived is
    still published."""
    apps, broken = [], []
    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        jobs = [(line, pool.submit(entry, *line, known.get(ident(line[1], line[2]))))
                for line in lines]
        for (url, owner, repo, tag), job in jobs:
            label = url + (f"@{tag}" if tag else "")
            print(label)
            try:
                app, log = job.result()
            except Problem as ex:
                print(f"  {ex}")
                broken.append((label, str(ex)))
            except Exception as ex:
                print(f"  {type(ex).__name__}: {ex}")
                broken.append((label, f"{type(ex).__name__}: {ex}"))
            else:
                for line in log:
                    print(f"  {line}")
                apps.append(app)
    return apps, broken


def complete(apps, broken, lines):
    """The media of every entry copied out of the published catalog, fetched
    off the live site now that it is known there will be a deploy.

    A file the site no longer has is a hole in the site, and reading that one
    app the long way is what fills it. That costs a zip, in the run that was
    going to publish anyway, and it means a gap heals itself rather than
    being copied forward for ever."""
    reused = [app for app in apps if "_media" not in app]
    if not reused:
        return apps, broken
    print(f"fetching the media of {len(reused)} unchanged "
          f"app{'' if len(reused) == 1 else 's'}")
    holes = []
    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        jobs = [(app, pool.submit(served, app)) for app in reused]
        for app, job in jobs:
            try:
                app["_media"], app["_raw"] = job.result()
            except Problem as ex:
                print(f"  {app['id']}: {ex}; reading it again")
                holes.append(app)
            except Exception as ex:
                print(f"  {app['id']}: {type(ex).__name__}: {ex}; reading it again")
                holes.append(app)
    if holes:
        whose = {ident(line[1], line[2]): line for line in lines}
        read, broke = walk([whose[app["id"]] for app in holes], {})
        apps = [app for app in apps if app not in holes] + read
        broken = broken + broke
        apps.sort(key=lambda app: app["id"])
    return apps, broken


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

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = memory()
    known = {app["id"]: app for app in (live or {}).get("apps", [])
             if isinstance(app, dict) and "id" in app}

    lines = repos(listing)
    apps, broken = walk(lines, known)
    apps.sort(key=lambda app: app["id"])

    if not apps:
        # Every repository failing at once is far more likely to be GitHub
        # having a bad minute than every author breaking at once, and an
        # empty catalog would uninstall nothing but would list nothing
        # either. The site that is already up is the better answer.
        print("no app could be derived; leaving the published catalog alone")
        changed = "no"
    else:
        # What this run would publish, before a byte of it is fetched or
        # written: a forced run publishes anyway, because what forced it is a
        # change to the list or to the code, which the catalog can be
        # identical through.
        changed = "yes" if FORCE or unlike(shape(apps, generated), live) else "no"
    if changed == "yes":
        apps, broken = complete(apps, broken, lines)
        os.makedirs(out, exist_ok=True)
        write_site(apps, broken, shape(apps, generated), out)

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
