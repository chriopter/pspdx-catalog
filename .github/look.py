#!/usr/bin/env python3
"""Reads every repository on the list and writes the cache the console
fetches: one catalog.json, the pictures out of each EBOOT, and a page for
whoever lands on the site.

    look.py                    read repos.txt, write site/
    look.py --list <file>      another list
    look.py --out <dir>        write the site somewhere else
    look.py --listed <dir>     another folder of listed files

    LIVE=<url>                 the published catalog.json, which is the memory
    FORCE=1                    forget it and read everything again
    GITHUB_TOKEN=<token>       raises the rate limit; a run needs one

There is no state in this repository. The published `catalog.json` is the
memory: a repository whose release is the one already in it reuses its entry
and published media. The site is still published every hour, so generated_at
records the latest snapshot rather than the latest changed release. Reuse
makes hourly runs feasible even with large release ZIPs.

What it costs is one thing: an author who edits their `.pspdx` and publishes
no release is not noticed until they do. That is accepted, and `FORCE=1`
reads everything from scratch for the hours when it is not.

An app is a GitHub repository that says so: a `.pspdx` file in its root, and
a release that carries one zip with an EBOOT.PBP in it. The file is the
author's consent and their words; everything that changes is derived from the
release and the EBOOT and never written by hand.

A repository without a `.pspdx` can still be listed, by this catalog and on
its word: a `.pspdx` for it in `listed/`, and the entry says `listed_by` this
catalog. The moment the repository has a file of its own, that file is read
and the listed one is redundant.

A `.pspdx` may pin a release with `release`: then that release and no other
is listed, and nothing newer is looked for until the file changes.

Nothing but the standard library, on purpose: this runs in a workflow and
should keep running in ten years. The `.pspdx` is checked by hand against the
rules in schema/pspdx-v1.json rather than handed to a validator module, for the
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

import config
import page

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("GITHUB_TOKEN")

# The catalog that is up now: the memory, and the thing the new one is
# compared against. Empty, unreachable or FORCE=1 all mean the same thing,
# which is what the first run does anyway: read everything.
LIVE = os.environ.get("LIVE", config.load()["catalog_url"])
FORCE = os.environ.get("FORCE", "") == "1"

# How many repositories are asked at once. A quiet hour is one small API call
# an app and nothing else, and asking them one after another is a minute of
# waiting for a list that will one day be long. Eight is polite to GitHub and
# plenty: the wait is the network, not this process.
WORKERS = 8

# The catalog names itself: a file found on a stick years from now says where
# it came from and which version of the format it is.
SCHEMA = "https://chriopter.github.io/pspdx/schema/catalog-v1.json"

# What a .pspdx must say in its `schema` line to be a version 1 file. A
# version 2 gets a new name, so an old file is never wrong, only old.
PSPDX_SCHEMA = "https://chriopter.github.io/pspdx/schema/pspdx-v1.json"

# A repository URL as the console reads one, matched whole: an owner of 1 to
# 39 and a repository of 1 to 100 of [A-Za-z0-9_.-], a .git and a slash after
# it allowed. Each needs a letter or digit, the repository besides the .git it
# ends in, since the id is made of those; that also keeps out . and .. . And
# <name>.git.git would be written back as <name>.git, another repository.
# SHAPE is only the outline, so that `repository` can say which rule is broken.
SHAPE = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?")
GITHUB = re.compile(r"https://github\.com/(?=[._-]*[A-Za-z0-9])([A-Za-z0-9_.-]{1,39})/"
                    r"(?=[._-]*[A-Za-z0-9])(?![._-]+\.git/?\Z)(?![A-Za-z0-9_.-]+\.git\.git/?\Z)"
                    r"(?=[A-Za-z0-9_.-]{1,100}/?\Z)([A-Za-z0-9_.-]+?)(?:\.git)?/?")

# The rules out of schema/pspdx-v1.json, by hand. The install directory is
# matched whole, because the schema's `$` is the end of the string and
# Python's is not quite. The folder does not end in a dot, which FAT drops:
# PSP/GAME/Demo. would be PSP/GAME/Demo on the stick, and PSP/GAME/.. the
# folder above. It is not .pspdx-stage in any case: the client unpacks every
# install there first, and the stick does not tell the cases apart.
# test_schema_drift.py holds these to the schema, case by case.
INSTALLDIR = re.compile(r"PSP/GAME/(?!(?i:\.pspdx-stage)\Z)[A-Za-z0-9_.-]{0,31}[A-Za-z0-9_-]")

# The list that vouches for an app: an https:// URL whose host is ASCII with a
# letter or digit in every label, since outside GitHub the id is made of them
# and a label of none would drop out and leave another host's id. A name in
# another script is written in punycode. Who logs in and the port may be
# there; a backslash may not, since a browser reads it as a slash and the
# host would be another. A host of only www. is none.
LABEL = r"-*[A-Za-z0-9][A-Za-z0-9-]*"
LISTED_BY = re.compile(r"https://(?:[^/?#\\\x00-\x1f]*@)?(?!(?i:www)\.(?:[:/?#]|\Z))"
                       rf"(?:{LABEL}\.)*{LABEL}\.?(?::[0-9]*)?(?:[/?#][^\\\x00-\x1f]*)?")
# io.github. starts the ids of GitHub repositories, so a list under github.io
# gives none to an app from anywhere else, whose id its host backwards would
# start. The dashes an id drops are passed over here too.
GITHUB_IO = re.compile(r"https://(?:[^/?#\\]*@)?(?![^/?#\\]*@)(?:[A-Za-z0-9-]*\.)*"
                       r"-*g-*i-*t-*h-*u-*b-*\.-*i-*o-*\.?(?:[:/?#]|\Z)", re.IGNORECASE)

# What a file can be. A homebrew is an EBOOT under PSP/GAME and is the one
# this catalog can check; the other two need other checks than a release with
# an EBOOT in it, and a file that says it is one of them is not wrong, only
# early. A file that says nothing is a homebrew.
TYPES = ("homebrew", "plugin", "iso")
HOMEBREW = "homebrew"

# The file's keys, which of them must be there, and the longest each string
# may be. The caps are the schema's: a name fits the XMB, a summary fits one
# line of a 480 pixel screen, and a list's address fits the URL slot the
# console has for every other address.
KEYS = ("schema", "source", "name", "type", "category", "tags", "installdir", "summary",
        "author", "license", "description", "listed_by", "release")
REQUIRED = ("schema", "source", "name")
LIMITS = {"source": 255, "name": 40, "category": 24, "summary": 60, "author": 60,
          "license": 60, "description": 2500, "listed_by": 255}

# What a pinned release may say, and how long its link may be: the rules of a
# catalog's release, since it becomes one. The size and the hashes are no part
# of it; the builder computes them and a hand never writes them.
RELEASE_KEYS = ("tag", "url", "published_at")
URL = 512
URI = re.compile(r"https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
WHEN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?")

# The folder of .pspdx files this catalog keeps for repositories that have none.
LISTED = "listed"

# Tags say what an app is in as many words as it takes, up to eight, each a
# word or two long; the console makes a tab of the ones it knows.
TAGS, TAG = 8, 24

# No string holds a control character: each of them lands on one line of a
# screen or a page, where a tab or a carriage return is a hole in the layout
# nobody can see in the file. The description is the one text of several
# lines, and a newline is how it says so; the rest of the controls stay out
# of it too.
CONTROL = re.compile(r"[\x00-\x1f]")
PARAGRAPHS = re.compile(r"[\x00-\x09\x0b-\x1f]")

# How many releases an entry carries, newest first. The console installs and
# compares the first; the rest are the history a page or another client can
# show. Every one of them is a zip downloaded once to be hashed, and after
# that its hash is copied forward from the published catalog, so the cost is
# the first run and then one zip a new release.
RELEASES = 20

# GitHub lists this many releases a page; drafts and pre-releases come out of
# them before the newest twenty are taken.
RELEASE_PAGE = 30

# A changelog is the release's own notes, as plain text this long at most.
CHANGELOG = 2500

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


def repository(source):
    """The owner and repository of a source on github.com, as GITHUB reads
    them, or the Problem that names the rule it breaks."""
    shape = SHAPE.fullmatch(source)
    if not shape:
        raise Problem('.pspdx: "source" on github.com must be a repository URL, '
                      "https://github.com/<owner>/<repository>")
    owner, name = shape.groups()
    if len(owner) > 39:
        raise Problem(f'.pspdx: the owner in "source" is {len(owner)} characters, at most 39')
    if len(name) > 100:
        raise Problem(f'.pspdx: the repository in "source" is {len(name)} characters, at most 100')
    if len(name) > 8 and name.endswith(".git.git"):
        raise Problem('.pspdx: the repository in "source" ends in .git.git, which is written '
                      "back without one .git as another repository")
    if len(name) > 4 and name.endswith(".git"):
        name = name[:-4]
    for what, part in (("owner", owner), ("repository", name)):
        if not plain(part):
            raise Problem(f'.pspdx: the {what} in "source", {part!r}, has no letter or digit '
                          "to make an id of")
    found = GITHUB.fullmatch(source)
    if not found:
        raise Problem('.pspdx: "source" on github.com must be a repository URL, '
                      "https://github.com/<owner>/<repository>")
    return found.groups()


def plain(text):
    """One part of an id: the letters and digits of text, in lower case. The
    ASCII ones only, stripped before the case is changed, so that a letter
    whose lower case happens to be ASCII does not slip in here and not on the
    console."""
    return re.sub(r"[^A-Za-z0-9]", "", text).lower()


def identity(spec):
    """The id of the app a valid .pspdx describes, or None when it cannot
    have one. A GitHub repository is io.github.<owner>.<repo>, which is what
    every id already published is. Anywhere else the address says too little
    about which project it is -- a mirror moves, and one page lists many --
    so the id is the list that vouches for the app and the app's name: the
    host of listed_by backwards, as a reverse domain name is written, without
    the www. nobody means, and the name after it."""
    found = GITHUB.fullmatch(spec["source"])
    if found:
        return ident(*found.groups())
    where = spec.get("listed_by", "")
    if not where.startswith("https://"):
        return None
    # A backslash ends the host as a slash does, the way a browser reads it.
    host = re.split(r"[/?#\\]", where[len("https://"):], maxsplit=1)[0]
    # Who logs in and on which port are not part of the name.
    host = host.rsplit("@", 1)[-1].split(":", 1)[0]
    if host[:4].lower() == "www.":
        host = host[4:]
    labels = host.split(".")
    # The empty label after a trailing dot is the only one that may drop out:
    # any other label without a letter or digit would leave another host's id.
    if len(labels) > 1 and not labels[-1]:
        labels.pop()
    labels = [plain(label) for label in labels[::-1]]
    name = plain(spec["name"])
    if not all(labels) or not name:
        return None
    one = ".".join(labels + [name])
    return None if one.startswith("io.github.") else one


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
    # raw.githubusercontent.com is a cache in front of the repository, and it
    # holds a file for minutes after it changed: a run that reads a .pspdx a
    # moment after its author fixed it would read the broken one and leave the
    # app out for an hour. Asking it not to serve the copy costs nothing and
    # makes a run see what the repository says now.
    request = urllib.request.Request(url, headers={
        "User-Agent": "pspdx-catalog",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
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
    """The rules of schema/pspdx-v1.json, one at a time, and the first one broken
    as a Problem. Written out rather than fed to a validator so that the
    reason reads like a sentence: a misspelt key is named, a long summary
    says how long it may be."""
    if not isinstance(data, dict):
        raise Problem(".pspdx is not a JSON object")
    # A field version 1 does not name is ignored, as every reader of the
    # format ignores it: a file written for a later version still says all
    # this one needs. It is never copied on, and `ignored` names it in the
    # log so an author who misspelt a field still finds out.
    data = {key: value for key, value in data.items() if key in KEYS}
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
            if (PARAGRAPHS if key == "description" else CONTROL).search(value):
                raise Problem(f".pspdx: {key!r} holds a control character"
                              + ("; a newline is the only one it may"
                                 if key == "description" else ""))
    # Any https:// address may be where a project lives: a mirror of
    # something abandoned is rarely on GitHub. One on github.com is held to
    # being a repository, because that is what the id, the default folder
    # and the releases are read out of.
    source = data["source"]
    if not source.startswith("https://") or source == "https://":
        raise Problem('.pspdx: "source" must be an https:// URL')
    if source.startswith("https://github.com/"):
        repository(source)
    if not data["name"]:
        raise Problem('.pspdx: "name" is empty')
    # The category is the one group the app belongs in, a word like a tag;
    # an empty one names none.
    if data.get("category") == "":
        raise Problem('.pspdx: "category" is empty')
    if "tags" in data:
        tags = data["tags"]
        if not isinstance(tags, list) or len(tags) > TAGS:
            raise Problem(f'.pspdx: "tags" is a list of at most {TAGS} words')
        for tag in tags:
            if not isinstance(tag, str) or not 1 <= len(tag) <= TAG or CONTROL.search(tag):
                raise Problem(f'.pspdx: a tag is 1 to {TAG} characters and no control '
                              f"character, not {tag!r}")
        if len(set(tags)) != len(tags):
            raise Problem('.pspdx: "tags" names a word twice')
    kind = data.get("type", HOMEBREW)
    if kind not in TYPES:
        raise Problem('.pspdx: "type" is one of ' + ", ".join(TYPES))
    if "listed_by" in data:
        where = data["listed_by"]
        if not where.startswith("https://") or where == "https://":
            raise Problem('.pspdx: "listed_by" must be an https:// URL')
        if "\\" in where:
            raise Problem('.pspdx: "listed_by" holds a backslash, which a browser reads as a slash')
        if not LISTED_BY.fullmatch(where):
            raise Problem('.pspdx: the host of "listed_by" is ASCII letters, digits and hyphens '
                          "with a letter or digit in every label; a name in another script is "
                          "written in punycode (xn--)")
    # Outside GitHub the id is the vouching list's host and the name, so a
    # file without either has no id and describes no app anyone could find.
    if not GITHUB.fullmatch(source):
        if "listed_by" not in data:
            raise Problem('.pspdx: a "source" outside GitHub needs "listed_by", '
                          "whose host and the name make the id")
        if not plain(data["name"]):
            raise Problem('.pspdx: "name" has no letter or digit to make an id of')
        if GITHUB_IO.match(data["listed_by"]):
            raise Problem('.pspdx: "listed_by" is under github.io, and for a "source" outside '
                          "GitHub its host would make an id under io.github., which only a GitHub "
                          "repository has")
        if identity(data) is None:
            raise Problem('.pspdx: "listed_by" has no host to make an id of')
    if "release" in data:
        data["release"] = pinned(data["release"], GITHUB.fullmatch(source) is not None)
    if "installdir" in data:
        if kind != HOMEBREW:
            raise Problem(f'.pspdx: "installdir" is only for type homebrew, not {kind}')
        if not isinstance(data["installdir"], str) \
                or not INSTALLDIR.fullmatch(data["installdir"]):
            raise Problem('.pspdx: "installdir" is PSP/GAME/ and 1 to 32 of '
                          "[A-Za-z0-9_.-], not ending in a dot and not .pspdx-stage, in version 1")
    elif kind == HOMEBREW:
        installdir(data)
    return data


def pinned(pin, github):
    """A `release` as validate keeps it: the known keys, each held to its
    rule. On GitHub the tag is enough, and the release says the rest; anywhere
    else nothing can be asked, so the file says where the zip is and when it
    was published."""
    if not isinstance(pin, dict):
        raise Problem('.pspdx: "release" is an object with a "tag"')
    pin = {key: value for key, value in pin.items() if key in RELEASE_KEYS}
    tag = pin.get("tag")
    if not isinstance(tag, str) or not 1 <= len(tag) <= 64 or CONTROL.search(tag):
        raise Problem('.pspdx: "release" needs a "tag" of 1 to 64 characters '
                      "and no control character")
    if "url" in pin and not (isinstance(pin["url"], str) and len(pin["url"]) <= URL
                             and URI.fullmatch(pin["url"])):
        raise Problem(f'.pspdx: release "url" is an https:// URL of at most {URL} characters')
    if "published_at" in pin and not moment(pin["published_at"]):
        raise Problem('.pspdx: release "published_at" is a UTC time like '
                      "2024-12-20T14:03:00Z, or a date like 2024-12-20")
    if not github and not {"url", "published_at"} <= set(pin):
        raise Problem('.pspdx: a "source" outside GitHub pins its "release" '
                      'with "url" and "published_at"')
    return pin


def moment(text):
    """Whether text is a published_at a catalog may carry: a UTC second with
    its Z, or a bare date, and one the calendar has."""
    if not isinstance(text, str) or not WHEN.fullmatch(text):
        return False
    try:
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ" if "T" in text else "%Y-%m-%d")
    except ValueError:
        return False
    return True


def ignored(raw):
    """The keys of a .pspdx that are no field of version 1, in the order the
    file has them: what validate passed over, for the log."""
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    pin = data.get("release")
    return ([key for key in data if key not in KEYS]
            + [f"release.{key}" for key in (pin if isinstance(pin, dict) else ())
               if key not in RELEASE_KEYS])


def installdir(spec):
    """Where a homebrew goes on the stick: what its file says, or else a
    folder under PSP/GAME named after it and cut to the 32 characters a folder
    may have -- the repository's name from GitHub, which is spelt in the
    characters a folder holds already, and the app's name from anywhere else,
    with every other character left out -- and without the dots it then ends
    in, which FAT would drop. A name that comes out empty or as .pspdx-stage
    has no folder it could go to, and the file then has to say one."""
    if "installdir" in spec:
        return spec["installdir"]
    found = GITHUB.fullmatch(spec["source"])
    name = found.group(2) if found else re.sub(r"[^A-Za-z0-9_.-]", "", spec["name"])
    folder = "PSP/GAME/" + name[:32].rstrip(".")
    if not INSTALLDIR.fullmatch(folder):
        raise Problem(f'.pspdx: no "installdir", and {folder} cannot be one')
    return folder


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
    for key in ignored(raw):
        print(f"  {owner}/{repo}: .pspdx field {key!r} is not in version 1; ignored")
    # The bytes come back with the parsed file: what the catalog used is
    # mirrored beside the app's page, and a copy is only honest if it is the
    # copy that was read.
    return validate(data), raw


def check_source(spec, owner, repo):
    """The manifest must lead back to the repository the list names."""
    found = GITHUB.fullmatch(spec["source"])
    # A file whose project lives elsewhere is a valid file, but this builder
    # reads releases and EBOOTs out of GitHub and has nothing to read there.
    if not found:
        raise Problem("non-GitHub source: only a catalog can list it, "
                      "not supported by this builder yet")
    source_owner, source_repo = found.groups()
    if (source_owner.lower(), source_repo.lower()) != (owner.lower(), repo.lower()):
        raise Problem(f'.pspdx: "source" must point to https://github.com/{owner}/{repo}')


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
    if asset["size"] is None:
        # Outside GitHub nobody said how big it is before: it is as big as
        # what arrives, up to the cap, and that is the size the catalog says.
        log.append(f"fetching {asset['browser_download_url']}")
        raw = fetch(asset["browser_download_url"], MAX_ASSET, asset["name"])
        asset["size"] = len(raw)
    elif asset["size"] > MAX_ASSET:
        raise Problem(f"{asset['name']} is {asset['size']} bytes, "
                      f"over the {MAX_ASSET} cap")
    else:
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
    return sha256(raw), root, sfo, sections, eboot_md5(archive, name)


def eboot_md5(archive, name):
    """The MD5 of the EBOOT.PBP as the install will put it on the stick, read
    out of the zip already in memory: a console holding an EBOOT and no
    record of it can then tell which release it is."""
    digest = hashlib.md5()
    with archive.open(name) as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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

def again(known, where, release_page):
    """The entry out of the published catalog, word for word, and no media
    yet: `complete` fetches the published files after the list is walked.

    Nothing here is derived a second time: the release is the one that was
    read the day this entry was written, so re-reading the .pspdx and the zip
    would cost another ZIP download; manifest-only edits await a forced run."""
    app = dict(known)
    app["_pspdx"] = where
    app["_page"] = release_page
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
        path = page.media_path(known, field)
        if not path:
            continue
        where = urllib.parse.urljoin(LIVE, path)
        data = fetch(where, cap, f"the published {field}")
        suffix = os.path.splitext(path)[1]
        if suffix not in MAGIC or not data.startswith(MAGIC[suffix]):
            raise Problem(f"the published {field} is not a {suffix} file")
        media[field] = (suffix, data)
    raw = fetch(urllib.parse.urljoin(LIVE, f"{APPS}/{known['id']}/{READ}"),
                MAX_PSPDX, f"the published {READ}")
    return media, raw


def dated(release, pinned=False):
    """When a release was published, as the catalog writes it, or the Problem
    that keeps it out: a draft, a pre-release, no date, a date past what a
    console's unsigned seconds hold, or a tag the console cannot make a
    version of. A pinned release may be a pre-release: somebody chose it by name."""
    if not isinstance(release, dict) or not isinstance(release.get("tag_name"), str):
        raise Problem("GitHub answered with something other than a release")
    tag = release["tag_name"]
    if release.get("draft") or (release.get("prerelease") and not pinned):
        raise Problem(f"{tag} is a draft or a pre-release")
    try:
        published = datetime.fromisoformat(
            release["published_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Problem(f"{tag} has no published_at") from None
    check_tag(tag)
    if not 0 < published.timestamp() < 2**32:
        raise Problem(f"{tag}: publication time is outside the PSPDX v1 range")
    return published.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_tag(tag):
    """A tag the console can make a version of."""
    if not tag or tag == "v" or len(tag) > 64 or CONTROL.search(tag):
        raise Problem("release tag must be 1 to 64 characters and not just v")


def the_zip(release, url=None):
    """The zip on a release that is the PSP package: the one zip, or of
    several the one with psp in its name, in any case. One release is one
    package, so anything else is a question for the author, and the run
    cannot guess which is the install. A pin that gives its url names the
    asset itself."""
    assets = [a for a in release.get("assets") or [] if isinstance(a, dict)]
    if url is not None:
        for asset in assets:
            if asset.get("browser_download_url") == url:
                return asset
        raise Problem(f"{release['tag_name']} has no asset at {url}")
    zips = [a for a in assets if str(a.get("name", "")).lower().endswith(".zip")]
    if not zips:
        raise Problem(f"{release['tag_name']} has no zip attached")
    if len(zips) == 1:
        return zips[0]
    psp = [a for a in zips if "psp" in str(a["name"]).lower()]
    if len(psp) == 1:
        return psp[0]
    raise Problem(f"{release['tag_name']} has {len(zips)} zips: "
                  + ", ".join(a["name"] for a in zips)
                  + f"; {len(psp) or 'none'} with psp in the name, "
                  "and one release is one package")


def changelog(body):
    """The release's notes as plain text: a line break however GitHub stored
    it becomes a newline, a tab a space, and any other control character is
    dropped, because the catalog's changelog holds no more than that. Cut on
    a space when it is too long, as a summary is."""
    if not isinstance(body, str):
        return ""
    text = body.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = PARAGRAPHS.sub("", text).strip()
    if len(text) <= CHANGELOG:
        return text
    return text[:CHANGELOG - 3].rsplit(" ", 1)[0].rstrip() + "..."


def published(release, when, asset, sha, md5):
    """One release as the catalog lists it."""
    notes = changelog(release.get("body"))
    return {"tag": release["tag_name"], "published_at": when,
            "url": asset["browser_download_url"], "size": asset["size"], "sha256": sha,
            **({"eboot_md5": md5} if md5 else {}),
            **({"changelog": notes} if notes else {})}


def entry(url, owner, repo, tag, known, listed=None):
    """The app as the catalog carries it and the lines the log should show
    for it, or a Problem saying why it is not listed. `known` is what the
    published catalog says about this id, and is used when the newest release
    it names is still the newest GitHub names. `listed` is a file out of
    listed/ for a repository that has no .pspdx of its own.

    Several of these run at once, so it says nothing itself: what it has to
    report it hands back, and the caller prints it in the list's order."""
    log = []
    ref = tag or "HEAD"
    where = raw_url(owner, repo, ref, ".pspdx")
    # The file first: it is one request to raw.githubusercontent.com, which
    # counts against no limit, and it says whether a release is pinned and so
    # which release the rest is about.
    if listed:
        try:
            spec, raw = read_pspdx(owner, repo, "HEAD")
        except Problem as ex:
            if str(ex) != "no .pspdx":
                raise
            spec, raw, where = listed["spec"], listed["raw"], listed["link"]
        else:
            # The repository's own file is the author's word, and it wins.
            log.append(f"{listed['name']} is redundant: the repository has its own "
                       ".pspdx, which is used")
    else:
        spec, raw = read_pspdx(owner, repo, ref)
    check_source(spec, owner, repo)
    # A plugin or an ISO is a valid file, but everything below is the check
    # for an EBOOT under PSP/GAME, and none of it says whether either of those
    # would install. Left out with that said, rather than listed on a guess.
    if spec.get("type", HOMEBREW) != HOMEBREW:
        raise Problem(f"type {spec['type']} is not supported by this catalog yet")

    pin = spec.get("release")
    if tag and pin and pin["tag"] != tag:
        raise Problem(f'.pspdx at {tag} pins release {pin["tag"]!r}, the list pins {tag!r}')
    fixed = tag or (pin or {}).get("tag")
    # One request either way: a pinned tag is that release and no other, and
    # otherwise the list, of which the drafts and the pre-releases are no part.
    if fixed:
        try:
            releases = [api(f"/repos/{owner}/{repo}/releases/tags/{urllib.parse.quote(fixed)}",
                            "release")]
        except Problem as ex:
            if "has nothing at" in str(ex):
                raise Problem(f"release {fixed!r} does not exist on GitHub") from None
            raise
    else:
        releases = api(f"/repos/{owner}/{repo}/releases?per_page={RELEASE_PAGE}", "releases")
        if not isinstance(releases, list):
            raise Problem("GitHub answered with something other than a list of releases")
        releases = [r for r in releases
                    if not (isinstance(r, dict) and (r.get("draft") or r.get("prerelease")))]
        if not releases:
            raise Problem("no published release")
    # The newest is held to every rule, because it is the one a console
    # installs; an older one that breaks a rule only drops out of the history.
    dates = [(dated(releases[0], pinned=bool(fixed)), releases[0])]
    for release in releases[1:]:
        try:
            dates.append((dated(release), release))
        except Problem as ex:
            log.append(f"left out of the history: {ex}")
    dates.sort(key=lambda pair: pair[0], reverse=True)
    when, latest = dates[0]

    asset = the_zip(latest, (pin or {}).get("url"))
    if pin and "published_at" in pin and pin["published_at"] != when:
        log.append(f'release "published_at" {pin["published_at"]} is ignored; '
                   f"GitHub says {when}")
    page_url = latest.get("html_url", url + "/releases")

    # The same version published at the same second is the same release, and
    # the same release is the same package: what the catalog says about it
    # cannot have changed without the author publishing again. A pin keeps
    # one release, so an entry with a history is not the pinned one, and an
    # entry vouched for by another list is not this one.
    history_was = (known or {}).get("releases") or [{}]
    was = history_was[0]
    if (known and was.get("tag") == latest["tag_name"] and was.get("published_at") == when
            and was.get("url") == asset.get("browser_download_url")
            and (not fixed or len(history_was) == 1)
            and known.get("listed_by") == spec.get("listed_by")):
        return again(known, where, page_url), [f"unchanged, {latest['tag_name']}"]

    meta = api(f"/repos/{owner}/{repo}", "repository")
    if not isinstance(meta, dict):
        raise Problem("GitHub answered with something other than a repository")

    sha, root, sfo, sections, md5 = package(asset, log)
    # The package and the title are said out loud rather than served: the
    # console copies the package into installdir and reads the title off the
    # stick, and whoever reads this log is looking for the zip's own shape.
    log.append(f"{root or 'the zip itself'} is the package, "
               f"PARAM.SFO says {sfo['TITLE']!r}")
    media, notes = pictures(sections)
    log.extend(notes)

    # The older releases: each a zip of its own, held to the same package
    # rules, and hashed only the first time it is seen. What the published
    # catalog already says about the same asset of the same release is
    # copied, since a release asset does not change under its name.
    hashed = {(r.get("tag"), r.get("published_at"), r.get("url"), r.get("size")): r
              for r in (known or {}).get("releases") or [] if isinstance(r, dict)}
    history = [published(latest, when, asset, sha, md5)]
    for older_when, older in dates[1:]:
        if len(history) == RELEASES:
            break
        try:
            older_asset = the_zip(older)
            before = hashed.get((older["tag_name"], older_when,
                                 older_asset["browser_download_url"], older_asset["size"]))
            if before and isinstance(before.get("sha256"), str):
                older_sha, older_md5 = before["sha256"], before.get("eboot_md5")
            else:
                older_sha, _, _, _, older_md5 = package(older_asset, log)
        except Problem as ex:
            log.append(f"left out of the history: {ex}")
            continue
        history.append(published(older, older_when, older_asset, older_sha, older_md5))

    # The licence GitHub reports when it recognises the file; NOASSERTION is
    # its word for a file it cannot place, and that is no licence to list.
    spdx = (meta.get("license") or {}).get("spdx_id") or ""
    if spdx == "NOASSERTION":
        spdx = ""
    # The project's own page, when GitHub has one that fits the catalog's rule
    # for an address.
    home = meta.get("homepage")
    website = (home if isinstance(home, str) and home.startswith("https://")
               and 8 < len(home) <= 255 and not CONTROL.search(home) else None)

    # The file wins over what was derived: what it says, it says on purpose,
    # for the summary GitHub's description gets wrong or the licence GitHub
    # cannot see.
    app = {
        "id": ident(owner, repo),
        "source": url,
        "name": spec["name"],
        # The words nothing stands in for: a file that gives no tags, no
        # type, no category, no description or no list is an entry without
        # them, not one with a guess.
        **{key: spec[key] for key in ("type", "category", "tags") if key in spec},
        # Always there for a homebrew, derived where the file said nothing,
        # so that a console reading the catalog never has to know the rule.
        "installdir": installdir(spec),
        "summary": spec.get("summary", trim(meta.get("description") or "")),
        "author": spec.get("author", owner),
        "license": spec.get("license", spdx),
        **{key: spec[key] for key in ("description", "listed_by") if key in spec},
        **({"website": website} if website else {}),
        "releases": history,
        "_media": media,
        "_raw": raw,
        # Where the file that consented to all of this can be read, at the ref
        # it was read at, or in this catalog's listed/. The page links it so
        # that whoever wonders where a name or a summary came from reads it at
        # its source.
        "_pspdx": where,
        # Which of the words above the author actually wrote: the optional
        # three fall back to GitHub, and a page that shows where a fact came
        # from has to know which of the two it was.
        "_said": sorted(spec),
        "_page": page_url,
    }
    log.append(f"{app['id']} {latest['tag_name']}: {app['name']!r}, "
               + (", ".join(sorted(media)) or "nothing in the PBP")
               + f", {len(history)} release{'' if len(history) == 1 else 's'}")
    return app, log


def elsewhere(listed, known):
    """A listed app whose project lives outside GitHub: nothing can be asked
    there, so the pinned release in the file says where the zip is and when
    it was published, and the zip is read as any release's is."""
    spec, log = listed["spec"], []
    if spec.get("type", HOMEBREW) != HOMEBREW:
        raise Problem(f"type {spec['type']} is not supported by this catalog yet")
    pin = spec.get("release")
    if not pin:
        raise Problem('a "source" outside GitHub is built only with a pinned "release"')
    check_tag(pin["tag"])
    when = pin["published_at"]
    moment_ = datetime.fromisoformat(when.replace("Z", "+00:00") if "T" in when
                                     else when + "T00:00:00+00:00")
    if not 0 < moment_.timestamp() < 2**32:
        raise Problem(f"{pin['tag']}: publication time is outside the PSPDX v1 range")
    was_all = (known or {}).get("releases") or [{}]
    was = was_all[0]
    if (known and len(was_all) == 1 and was.get("tag") == pin["tag"]
            and was.get("published_at") == when and was.get("url") == pin["url"]
            and known.get("listed_by") == spec.get("listed_by")):
        return again(known, listed["link"], spec["source"]), [f"unchanged, {pin['tag']}"]
    name = urllib.parse.unquote(pin["url"].split("?", 1)[0].rsplit("/", 1)[-1]) or "the zip"
    asset = {"name": name, "size": None, "browser_download_url": pin["url"]}
    sha, root, sfo, sections, md5 = package(asset, log)
    log.append(f"{root or 'the zip itself'} is the package, "
               f"PARAM.SFO says {sfo['TITLE']!r}")
    media, notes = pictures(sections)
    log.extend(notes)
    app = {
        "id": identity(spec),
        "source": spec["source"],
        "name": spec["name"],
        **{key: spec[key] for key in ("type", "category", "tags") if key in spec},
        "installdir": installdir(spec),
        # Nothing to fall back on out here: what the file does not say, the
        # entry says empty.
        **{key: spec.get(key, "") for key in ("summary", "author", "license")},
        **{key: spec[key] for key in ("description", "listed_by") if key in spec},
        "releases": [published({"tag_name": pin["tag"]}, when, asset, sha, md5)],
        "_media": media,
        "_raw": listed["raw"],
        "_pspdx": listed["link"],
        "_said": sorted(spec),
        "_page": spec["source"],
    }
    log.append(f"{app['id']} {pin['tag']}: {app['name']!r}, "
               + (", ".join(sorted(media)) or "nothing in the PBP") + ", 1 release")
    return app, log


# --- listed files -----------------------------------------------------------

def read_listed(path, settings):
    """One file out of listed/, as entry and elsewhere take it, or the Problem
    that keeps it out. It is held to the rules a repository's .pspdx is held
    to, and it is this catalog's word, so its listed_by is this catalog: left
    out it is filled in, and another list's is a mistake."""
    name = f"{LISTED}/{os.path.basename(path)}"
    site = settings["site_url"]
    listed = {"name": name,
              "link": (settings["repository_url"] + "/blob/HEAD/" + LISTED + "/"
                       + urllib.parse.quote(os.path.basename(path)))}
    with open(path, "rb") as file:
        raw = file.read(MAX_PSPDX + 1)
    if len(raw) > MAX_PSPDX:
        raise Problem(f"{name}: over {MAX_PSPDX} bytes")
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise Problem(f"{name} is not UTF-8") from None
    except ValueError as e:
        raise Problem(f"{name} is not JSON: {e}") from None
    if isinstance(data, dict):
        if data.get("listed_by", site) != site:
            raise Problem(f'{name}: "listed_by" is this catalog, {site}, or left out')
        data = dict(data, listed_by=site)
    try:
        spec = validate(data)
    except Problem as ex:
        raise Problem(f"{name}: {ex}") from None
    for key in ignored(raw):
        print(f"  {name}: field {key!r} is not in version 1; ignored")
    return dict(listed, spec=spec, raw=raw)


def refuse(problem):
    """A listed file that is no .pspdx, reported where its app would be."""
    raise problem


def plan(lines, directory, settings):
    """Everything this run reads, as (label, id, how): the list's lines, and
    after them every file in listed/ in the order of their names.

    What is wrong between them is the curator's to fix and is known before
    anything is fetched, so it stops the run: two files for one app, or a
    repository both on the list and in listed/. A file that breaks the rules
    of a .pspdx is only that file's problem, and is left out with its reason
    as a broken repository is."""
    items, seen = [], {}
    for url, owner, repo, tag in lines:
        seen[ident(owner, repo)] = "repos.txt"
        items.append((url + (f"@{tag}" if tag else ""), ident(owner, repo),
                      lambda known, line=(url, owner, repo, tag): entry(*line, known)))
    names = sorted(f for f in os.listdir(directory)
                   if f.endswith(".pspdx")) if os.path.isdir(directory) else []
    for file in names:
        label = f"{LISTED}/{file}"
        try:
            listed = read_listed(os.path.join(directory, file), settings)
        except Problem as ex:
            items.append((label, None, lambda known, ex=ex: refuse(ex)))
            continue
        spec = listed["spec"]
        found = GITHUB.fullmatch(spec["source"])
        one = ident(*found.groups()) if found else identity(spec)
        if one in seen:
            sys.exit(f"{label}: {one} is already listed by {seen[one]}; keep one")
        seen[one] = label
        if found:
            owner, repo = found.groups()
            items.append((label, one, lambda known, owner=owner, repo=repo, listed=listed:
                          entry(f"https://github.com/{owner}/{repo}", owner, repo, "",
                                known, listed)))
        else:
            items.append((label, one, lambda known, listed=listed: elsewhere(listed, known)))
    return items


# --- the site ---------------------------------------------------------------

def shape(apps, generated):
    """Where each media file will be served, and the catalog that says so.

    Everything of one app sits in one directory named by its id, and the
    name of each file still carries its bytes: a client caches a picture by
    the name it was fetched under and never asks again, so a changed icon has
    to arrive under a new name or it never arrives. The same bytes therefore
    land on the same name, which is why an entry copied out of the published
    catalog keeps the paths it already has.

    Nothing is written here; the run compares the shape to the live catalog
    only to report whether app data moved."""
    for app in apps:
        for field, (suffix, data) in app.get("_media", {}).items():
            called, _ = MEDIA[field]
            path = f"{APPS}/{app['id']}/{called}-{sha256(data)[:8]}{suffix}"
            # The catalog has room for several pictures of an app; the EBOOT
            # carries one, and it is the first.
            if field == "screenshot":
                app.setdefault("media", {})["screenshots"] = [path]
            else:
                app.setdefault("media", {})[field] = path
    return {
        "schema": SCHEMA,
        "generated_at": generated,
        "apps": [{k: v for k, v in app.items() if not k.startswith("_")}
                 for app in apps],
    }


def write_site(apps, broken, catalog, out, listing=None, notes=None):
    # Whatever a previous run left here is not evidence that any of it is
    # still in anybody's EBOOT, or that the app is still on the list.
    shutil.rmtree(os.path.join(out, APPS), ignore_errors=True)
    for app in apps:
        home = os.path.join(out, APPS, app["id"])
        os.makedirs(home, exist_ok=True)
        for field, (_, data) in app.pop("_media", {}).items():
            with open(os.path.join(out, *page.media_path(app, field).split("/")), "wb") as file:
                file.write(data)
        with open(os.path.join(home, READ), "wb") as file:
            file.write(app.pop("_raw"))

    # Compact separators: the console holds this in RAM, and a PSP has 24 MB.
    text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out, "catalog.json"), "w", encoding="utf-8") as file:
        file.write(text + "\n")
    shutil.copyfile(listing or os.path.join(HERE, "repos.txt"),
                    os.path.join(out, "catalog.txt"))
    # The site is more than one file now: the tiles, a page an app, and the
    # style and the wave they share, so the pages write themselves. It comes
    # after the pictures because a page measures the film and the sound where
    # they have just been written.
    page.render(catalog, apps, broken, out, notes=notes)

    have = ", ".join(f"{sum(field in app.get('media', {}) for app in apps)} {field}s"
                     for field in MEDIA)
    print(f"{len(apps)} app{'' if len(apps) == 1 else 's'}, {have}, "
          f"{len(text)} bytes -> " + os.path.join(out, "catalog.json"))


def memory():
    """The catalog that is published now, which is the only memory there is,
    or None when there is none to be had: the first run, an unreachable site,
    or something that is not a catalog. FORCE still reads the live catalog
    for the change summary, but never reuses its app entries."""
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
    return ({k: v for k, v in catalog.items() if k != "generated_at"}
            != {k: v for k, v in live.items() if k != "generated_at"})


def changes(apps, live):
    """App-level changes since the previously published catalog."""
    if live is None:
        return []
    old = {app["id"]: app for app in live.get("apps", [])
           if isinstance(app, dict) and "id" in app}
    new = {app["id"]: app for app in apps}
    notes = []
    for app in apps:
        before = old.get(app["id"])
        # The newest release is the one a console installs, so it alone makes
        # an update; an older one GitHub forgot is only a change.
        newest = app["releases"][0]
        if before is None:
            notes.append(("New app", app["name"], newest["tag"]))
        elif (before.get("releases") or [None])[0] != newest:
            notes.append(("Update", app["name"], newest["tag"]))
        elif {k: v for k, v in before.items()} != {
                k: v for k, v in app.items() if not k.startswith("_")}:
            notes.append(("Changed", app["name"], ""))
    for app_id, app in old.items():
        if app_id not in new:
            notes.append(("Removed", app.get("name", app_id), ""))
    return notes


def walk(items, known):
    """Every repository on the list, asked at once and reported in the
    list's order: the result of each is printed when it is collected, not
    from inside the thread that found it, so a log still reads top to bottom.

    One broken repository never ends the run, here as everywhere: the reason
    is kept, the rest of the list is still read, and what could be derived is
    still published."""
    apps, broken = [], []
    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        jobs = [((label, one), pool.submit(how, known.get(one) if one else None))
                for label, one, how in items]
        for (label, one), job in jobs:
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


def complete(apps, broken, items):
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
        whose = {item[1]: item for item in items}
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
    folder = os.path.join(HERE, LISTED)
    while argv:
        if argv[0] == "--list" and len(argv) > 1:
            listing = os.path.abspath(argv[1])
        elif argv[0] == "--listed" and len(argv) > 1:
            folder = os.path.abspath(argv[1])
        elif argv[0] == "--out" and len(argv) > 1:
            out = os.path.abspath(argv[1])
        else:
            raise SystemExit(__doc__)
        argv = argv[2:]

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = memory()
    if FORCE:
        print("FORCE=1: reading every repository from scratch")
    known = {app["id"]: app for app in ({} if FORCE else (live or {})).get("apps", [])
             if isinstance(app, dict) and "id" in app}

    items = plan(repos(listing), folder, config.load())
    apps, broken = walk(items, known)
    apps.sort(key=lambda app: app["id"])
    # shape also assigns the public media paths before the comparison.
    catalog = shape(apps, generated) if apps else None
    notes = changes(catalog["apps"], live) if catalog else []

    if not apps:
        # Every repository failing at once is far more likely to be GitHub
        # having a bad minute than every author breaking at once, and an
        # empty catalog would uninstall nothing but would list nothing
        # either. The site that is already up is the better answer.
        print("no app could be derived; leaving the published catalog alone")
        changed = "no"
    else:
        # Published every run, even when nothing about the apps moved: the
        # generated_at is then the time of this publication, and
        # a console can tell a list nobody looks after -- a stamp a day old
        # -- from one that simply had no news. What moved is still said.
        moved = FORCE or unlike(catalog, live)
        print("apps changed:", "yes" if moved else "no")
        changed = "yes"
    if changed == "yes":
        apps, broken = complete(apps, broken, items)
        os.makedirs(out, exist_ok=True)
        write_site(apps, broken, shape(apps, generated), out, listing, notes)

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## Catalog changes\n\n")
            if notes:
                for kind, name, tag in notes:
                    summary.write(f"- {kind}: {name}" + (f" ({tag})" if tag else "") + "\n")
            else:
                summary.write("No app changes.\n")

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
