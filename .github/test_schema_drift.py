"""look.validate reads the rules of schema/pspdx-v1.json by hand, so that an
author gets a sentence. Here the two are asked the same questions: a table of
files, one for every rule the format has and most of them broken, and each
must be judged the same by both, and as the table says. The table is the
format as pspdx states it in README.md "Fields" and enforces it on the console
in app/update/pspdx.c, so a rule both sides forgot is caught as well as one
they disagree on.

The schemas are the published ones, as check_schema.py reads them. To try a
schema before it is pushed:

    PSPDX_SCHEMA_DIR=../pspdx/schema python3 -m unittest test_schema_drift
"""
import json
import os
import unittest

import look

try:
    import check_schema
except ImportError:
    check_schema = None

# The workflow installs requirements.txt before the tests, so there a missing
# module is a broken step and must fail; on a bare checkout it only skips.
NEEDED = bool(os.environ.get("CI"))

DIRECTORY = os.environ.get("PSPDX_SCHEMA_DIR")

# The fields the catalog repeats word for word. The install directory is
# repeated by its rule alone: the file may leave it out, the catalog may not,
# and each schema says which in its own description.
FIELDS = ("name", "author", "summary", "type", "category", "tags", "license", "description",
          "listed_by", "source")
SAME_RULE = ("installdir",)
# The fields only a file has: a pinned release becomes the catalog's
# releases, which the builder fills in.
FILE_ONLY = ("release",)

FULL = {
    "schema": look.PSPDX_SCHEMA,
    "source": "https://github.com/chriopter/pspdx",
    "name": "PSPDX",
    "type": "homebrew",
    "category": "app",
    "author": "chriopter",
    "summary": "Download, run and update homebrew on your PSP.",
    "tags": ["app", "Download manager"],
    "license": "GPL-2.0-only",
    "installdir": "PSP/GAME/PSPDX",
    "description": "Download, run and update homebrew on your PSP.\n\nFrom GitHub.",
    "listed_by": "https://wijsman.de/psp-homebrew-database/",
}
MINIMAL = {key: FULL[key] for key in look.REQUIRED}
PLUGIN = {k: v for k, v in dict(FULL, type="plugin").items() if k != "installdir"}


def but(**changes):
    return dict(FULL, **changes)


def without(key):
    return {k: v for k, v in FULL.items() if k != key}


# Cases the schema refuses but every reader accepts: only keys the format
# does not name, which readers pass over.
IGNORED_BY_READERS = {"an unknown key", "a key in another case", "release with an unknown key",
                      "release with a size"}

# (what it is, the file, whether it is a valid .pspdx)
CASES = [
    ("every field", FULL, True),
    ("only the required fields", MINIMAL, True),
    ("empty optional strings", but(author="", summary="", license="", description=""), True),
    ("an unknown key", but(version="1.0"), False),
    ("a key in another case", dict(MINIMAL, Name="PSPDX"), False),
    *[(f"no {key}", without(key), False) for key in look.REQUIRED],
    *[(f"no {key}", without(key), True)
      for key in look.KEYS if key not in look.REQUIRED],
    ("type homebrew", but(type="homebrew"), True),
    ("type plugin without installdir", PLUGIN, True),
    ("type iso without installdir", dict(PLUGIN, type="iso"), True),
    ("type plugin with installdir", but(type="plugin"), False),
    ("type iso with installdir", but(type="iso"), False),
    ("type in another case", but(type="Plugin"), False),
    ("type empty", but(type=""), False),
    ("type unknown", but(type="theme"), False),
    ("type null", but(type=None), False),
    ("type a list", but(type=["homebrew"]), False),
    ("no installdir from a 40 character repository",
     without("installdir") | {"source": "https://github.com/chriopter/" + "r" * 40}, True),
    ("schema from before Pages", but(schema="https://raw.githubusercontent.com/"
                                     "chriopter/pspdx/master/schema/pspdx-v1.json"), False),
    ("schema v2", but(schema="https://chriopter.github.io/pspdx/schema/pspdx-v2.json"), False),
    ("schema over http",
     but(schema="http://chriopter.github.io/pspdx/schema/pspdx-v1.json"), False),
    ("schema a number", but(schema=1), False),
    ("source ending .git", but(source="https://github.com/chriopter/pspdx.git"), True),
    ("source ending /", but(source="https://github.com/chriopter/pspdx/"), True),
    ("source ending .git/", but(source="https://github.com/chriopter/pspdx.git/"), True),
    ("source ending //", but(source="https://github.com/chriopter/pspdx//"), False),
    ("source over http", but(source="http://github.com/chriopter/pspdx"), False),
    ("source elsewhere over http", but(source="http://archive.org/details/psp-blocks"), False),
    ("source over ftp", but(source="ftp://archive.org/details/psp-blocks"), False),
    ("source only the scheme", but(source="https://"), False),
    ("source on GitLab", but(source="https://gitlab.com/chriopter/pspdx"), True),
    ("source with www", but(source="https://www.github.com/chriopter/pspdx"), True),
    ("source elsewhere", but(source="https://archive.org/details/psp-blocks"), True),
    ("source elsewhere with a query", but(source="https://example.com/p?id=7#top"), True),
    ("source elsewhere without installdir",
     without("installdir") | {"source": "https://archive.org/details/psp-blocks"}, True),
    ("source elsewhere of type homebrew without installdir",
     without("installdir") | {"source": "https://example.com/x", "type": "homebrew"}, True),
    ("source elsewhere, a plugin", dict(PLUGIN, source="https://example.com/plugin"), True),
    ("source elsewhere with a tab", but(source="https://example.com/a\tb"), False),
    ("source elsewhere without listed_by",
     without("listed_by") | {"source": "https://archive.org/details/psp-blocks"}, False),
    ("source elsewhere, a name of no letter or digit",
     but(source="https://archive.org/details/psp-blocks", name="★ — ★"), False),
    ("source elsewhere, a name of one digit",
     but(source="https://archive.org/details/psp-blocks", name="★ 2 ★"), True),
    ("source on GitHub, a name of no letter or digit", but(name="★ — ★"), True),
    ("source 255", but(source="https://example.com/" + "x" * 235), True),
    ("source 256", but(source="https://example.com/" + "x" * 236), False),
    ("source on github.com a list of repositories",
     but(source="https://github.com/chriopter?tab=repositories"), False),
    ("source an owner", but(source="https://github.com/chriopter"), False),
    ("source a page in a repository",
     but(source="https://github.com/chriopter/pspdx/issues"), False),
    ("source pinned", but(source="https://github.com/chriopter/pspdx@v1"), False),
    ("source with a query", but(source="https://github.com/chriopter/pspdx?tab=readme"), False),
    ("source with a newline", but(source="https://github.com/chriopter/pspdx\n"), False),
    # The owner and the repository as the console reads them: GitHub's lengths,
    # a letter or digit in each for the id, and no .git.git to be read back as
    # another repository.
    ("source an owner of 39", but(source="https://github.com/" + "o" * 39 + "/pspdx"), True),
    ("source an owner of 40", but(source="https://github.com/" + "o" * 40 + "/pspdx"), False),
    ("source a repository of 100", but(source="https://github.com/chriopter/" + "r" * 100), True),
    ("source a repository of 101", but(source="https://github.com/chriopter/" + "r" * 101), False),
    ("source a repository of 100 with .git",
     but(source="https://github.com/chriopter/" + "r" * 96 + ".git"), True),
    ("source a repository of 101 with .git",
     but(source="https://github.com/chriopter/" + "r" * 97 + ".git/"), False),
    *[(f"source an owner {owner}", but(source=f"https://github.com/{owner}/pspdx"), False)
      for owner in (".", "..", "-", "_.-")],
    *[(f"source a repository {repo}", but(source=f"https://github.com/chriopter/{repo}"), False)
      for repo in (".", "..", "_", "..git", "-.git", ".../")],
    ("source a repository .git", but(source="https://github.com/chriopter/.git"), True),
    ("source a repository -git", but(source="https://github.com/chriopter/-git"), True),
    ("source ending .git.git", but(source="https://github.com/chriopter/pspdx.git.git"), False),
    ("source ending .git.git/", but(source="https://github.com/chriopter/pspdx.git.git/"), False),
    ("source a repository .git.git", but(source="https://github.com/chriopter/.git.git"), True),
    ("source a repository Demo.", but(source="https://github.com/chriopter/Demo."), True),
    ("source a list", but(source=["https://github.com/chriopter/pspdx"]), False),
    ("name empty", but(name=""), False),
    ("name 39", but(name="n" * 39), True),
    ("name 40", but(name="n" * 40), True),
    ("name 40 characters of two bytes", but(name="\u00e9" * 40), True),
    ("name 40 characters of four bytes", but(name="\U0001f3ae" * 40), True),
    ("name 41", but(name="n" * 41), False),
    ("summary 60", but(summary="s" * 60), True),
    ("summary 61", but(summary="s" * 61), False),
    ("license 60", but(license="l" * 60), True),
    ("license 61", but(license="l" * 61), False),
    ("license free text", but(license="Public domain, see README"), True),
    ("author 39", but(author="a" * 39), True),
    ("author 60", but(author="a" * 60), True),
    ("author 60 characters of three bytes", but(author="€" * 60), True),
    ("author 61", but(author="a" * 61), False),
    ("name a number", but(name=5), False),
    ("summary null", but(summary=None), False),
    ("author true", but(author=True), False),
    ("license a list", but(license=["MIT"]), False),
    ("installdir a number", but(installdir=5), False),
    ("tags a string", but(tags="app"), False),
    ("tags an object", but(tags={"app": True}), False),
    ("tags empty", but(tags=[]), True),
    ("a tag a number", but(tags=["app", 1]), False),
    ("a tag null", but(tags=[None]), False),
    *[(f"tags {t!r}", but(tags=t), True)
      for t in (["game"], ["emulator", "app"], ["plugin", "demo"], ["App", "app"],
                ["games", "tool", " app", "Jeu de rôle"])],
    ("a tag empty", but(tags=["app", ""]), False),
    ("a tag 24", but(tags=["c" * 24]), True),
    ("a tag 24 characters of four bytes", but(tags=["\U0001f3ae" * 24]), True),
    ("a tag 25", but(tags=["c" * 25]), False),
    ("tags 8", but(tags=[f"t{i}" for i in range(8)]), True),
    ("tags 9", but(tags=[f"t{i}" for i in range(9)]), False),
    ("a tag twice", but(tags=["game", "app", "game"]), False),
    ("a tag with a newline", but(tags=["one\ntwo"]), False),
    ("a tag with a tab", but(tags=["one\ttwo"]), False),
    ("category a tab's word", but(category="game"), True),
    ("category no tab has", but(category="Rundenbasierte Strategie"), True),
    ("category 24 characters of four bytes", but(category="\U0001f3ae" * 24), True),
    ("category 25", but(category="c" * 25), False),
    ("category empty", but(category=""), False),
    ("category a list", but(category=["game"]), False),
    ("category null", but(category=None), False),
    ("category with a newline", but(category="one\ntwo"), False),
    ("description 2500", but(description="d" * 2500), True),
    ("description 2500 newlines", but(description="\n" * 2500), True),
    ("description 2501", but(description="d" * 2501), False),
    ("description a number", but(description=1), False),
    ("description with a tab", but(description="one\ttwo"), False),
    ("description with a carriage return", but(description="one\r\ntwo"), False),
    ("description with a NUL", but(description="one\x00two"), False),
    ("description with an escape", but(description="one\x1btwo"), False),
    *[(f"{key} with a newline", but(**{key: "one\ntwo"}), False)
      for key in ("name", "summary", "author", "license")],
    *[(f"{key} with a tab", but(**{key: "one\ttwo"}), False)
      for key in ("name", "summary", "author", "license")],
    ("name with a carriage return", but(name="PSP\rDX"), False),
    ("summary with unit separator", but(summary="a\x1fb"), False),
    ("name with DEL", but(name="PSP\x7fDX"), True),
    ("listed_by https", but(listed_by="https://example.com/"), True),
    ("listed_by http", but(listed_by="http://wijsman.de/psp-homebrew-database/"), False),
    ("listed_by only the scheme", but(listed_by="https://"), False),
    ("listed_by empty", but(listed_by=""), False),
    ("listed_by no scheme", but(listed_by="wijsman.de/psp-homebrew-database/"), False),
    ("listed_by HTTPS in capitals", but(listed_by="HTTPS://wijsman.de/"), False),
    ("listed_by with a newline", but(listed_by="https://wijsman.de/\n"), False),
    ("listed_by 255", but(listed_by="https://" + "u" * 247), True),
    ("listed_by 256", but(listed_by="https://" + "u" * 248), False),
    ("listed_by a number", but(listed_by=1), False),
    # The host makes the id outside GitHub, so it is ASCII with a letter or digit
    # in every label, and nothing a browser would read as another host.
    ("listed_by 例え.jp", but(listed_by="https://例え.jp/"), False),
    ("listed_by xn--r8jz45g.jp", but(listed_by="https://xn--r8jz45g.jp/"), True),
    ("listed_by who logs in and a port", but(listed_by="https://user@wijsman.de:8443/list"), True),
    ("listed_by a query after the host", but(listed_by="https://wijsman.de?list#top"), True),
    ("listed_by www.", but(listed_by="https://www.wijsman.de/"), True),
    ("listed_by only www.", but(listed_by="https://www./list"), False),
    ("listed_by a trailing dot", but(listed_by="https://wijsman.de./"), True),
    ("listed_by an empty label", but(listed_by="https://wijsman..de/"), False),
    ("listed_by a leading dot", but(listed_by="https://.wijsman.de/"), False),
    ("listed_by a label of a hyphen", but(listed_by="https://-.wijsman.de/"), False),
    ("listed_by a label of hyphens and a digit", but(listed_by="https://-1-.wijsman.de/"), True),
    ("listed_by a backslash before the host",
     but(listed_by="https://evil.example\\@wijsman.de/"), False),
    ("listed_by a backslash in the path", but(listed_by="https://wijsman.de/a\\b"), False),
    # Outside GitHub the host backwards starts the id, and io.github. is GitHub's.
    ("listed_by under github.io, source on GitHub",
     but(listed_by="https://chriopter.github.io/list/"), True),
    *[(f"listed_by {where}, source elsewhere",
       but(source="https://archive.org/details/psp-blocks", listed_by=where), False)
      for where in ("https://chriopter.github.io/list/", "https://github.io", "https://github.io:443/",
                    "https://WWW.GitHub.IO./", "https://git-hub.io?x", "https://a.b.github.io#top",
                    "https://user@chriopter.github.io/")],
    *[(f"listed_by {where}, source elsewhere",
       but(source="https://archive.org/details/psp-blocks", listed_by=where), True)
      for where in ("https://github.io.example.com/", "https://notgithub.io/", "https://github.com/",
                    "https://io.github.example/", "https://x.github.io@wijsman.de/")],
    ("installdir with dots inside", but(installdir="PSP/GAME/Example-1.2_b"), True),
    ("installdir starting with a dot", but(installdir="PSP/GAME/.example"), True),
    ("installdir three dots", but(installdir="PSP/GAME/..."), False),
    ("installdir Demo", but(installdir="PSP/GAME/Demo"), True),
    ("installdir Demo.", but(installdir="PSP/GAME/Demo."), False),
    ("installdir Demo_", but(installdir="PSP/GAME/Demo_"), True),
    ("installdir 32 ending in a dot", but(installdir="PSP/GAME/" + "D" * 31 + "."), False),
    ("installdir .pspdx-stage.", but(installdir="PSP/GAME/.pspdx-stage."), False),
    ("no installdir from a repository ending in a dot",
     without("installdir") | {"source": "https://github.com/chriopter/Demo."}, True),
    ("no installdir from a name elsewhere ending in dots",
     without("installdir") | {"source": "https://archive.org/details/psp-blocks", "name": "Demo..."}, True),
    ("installdir 32", but(installdir="PSP/GAME/" + "D" * 32), True),
    ("installdir 33", but(installdir="PSP/GAME/" + "D" * 33), False),
    ("installdir .", but(installdir="PSP/GAME/."), False),
    ("installdir ..", but(installdir="PSP/GAME/.."), False),
    ("installdir .pspdx-stage", but(installdir="PSP/GAME/.pspdx-stage"), False),
    ("installdir .PSPDX-Stage", but(installdir="PSP/GAME/.PSPDX-Stage"), False),
    ("installdir .pspdx-stage2", but(installdir="PSP/GAME/.pspdx-stage2"), True),
    ("installdir no folder", but(installdir="PSP/GAME/"), False),
    ("installdir PSP/GAME", but(installdir="PSP/GAME"), False),
    ("installdir outside PSP/GAME", but(installdir="PSP/SAVEDATA/PSPDX"), False),
    ("installdir in lower case", but(installdir="psp/game/PSPDX"), False),
    ("installdir with the device", but(installdir="ms0:/PSP/GAME/PSPDX"), False),
    ("installdir absolute", but(installdir="/PSP/GAME/PSPDX"), False),
    ("installdir two deep", but(installdir="PSP/GAME/PSPDX/Sub"), False),
    ("installdir climbing out", but(installdir="PSP/GAME/../PSPDX"), False),
    ("installdir with a space", but(installdir="PSP/GAME/PSP DX"), False),
    ("installdir with a backslash", but(installdir="PSP/GAME/PSP\\DX"), False),
    ("installdir with an accent", but(installdir="PSP/GAME/D\u00e9mo"), False),
    ("installdir with a newline", but(installdir="PSP/GAME/PSPDX\n"), False),
    ("release a tag", but(release={"tag": "v1.0"}), True),
    ("release a prerelease tag", but(release={"tag": "0.0.3-rc1"}), True),
    ("release a tag of 64", but(release={"tag": "t" * 64}), True),
    ("release a tag of 65", but(release={"tag": "t" * 65}), False),
    ("release a tag empty", but(release={"tag": ""}), False),
    ("release a tag with a tab", but(release={"tag": "v1\t2"}), False),
    ("release a tag a number", but(release={"tag": 1}), False),
    ("release without a tag", but(release={"url": "https://example.com/a.zip"}), False),
    ("release empty", but(release={}), False),
    ("release a string", but(release="v1.0"), False),
    ("release null", but(release=None), False),
    ("release with an unknown key", but(release={"tag": "v1", "notes": "x"}), False),
    ("release with a size", but(release={"tag": "v1", "size": 1}), False),
    ("release every key", but(release={"tag": "v1", "published_at": "2026-09-12T00:00:00Z",
                                       "url": "https://github.com/chriopter/pspdx/releases/"
                                              "download/v1/pspdx.zip"}), True),
    ("release a bare date", but(release={"tag": "v1", "published_at": "2026-09-12"}), True),
    ("release a date with an offset",
     but(release={"tag": "v1", "published_at": "2026-09-12T00:00:00+02:00"}), False),
    ("release a date the calendar lacks", but(release={"tag": "v1", "published_at": "2026-02-30"}),
     False),
    *[(f"release published {when}", but(release={"tag": "v1", "published_at": when}), valid)
      for when, valid in (("2024-02-29", True), ("2023-02-29", False), ("2023-02-31", False),
                          ("2024-02-29T12:00:00Z", True), ("2023-02-29T12:00:00Z", False),
                          ("2023-02-31T12:00:00Z", False))],
    ("release a url with a non-ASCII character",
     but(release={"tag": "v1", "url": "https://example.com/d\u00e9mo.zip"}), False),
    ("release a url over http", but(release={"tag": "v1", "url": "http://example.com/a.zip"}), False),
    ("release a url of 512",
     but(release={"tag": "v1", "url": "https://example.com/" + "u" * 492}), True),
    ("release a url of 513",
     but(release={"tag": "v1", "url": "https://example.com/" + "u" * 493}), False),
    ("release a url with a space", but(release={"tag": "v1", "url": "https://example.com/a b.zip"}),
     False),
    ("release elsewhere with url and published_at",
     but(source="https://archive.org/details/psp-blocks",
         release={"tag": "1.0", "url": "https://archive.org/download/b/b.zip",
                  "published_at": "2011-05-04"}), True),
    ("release elsewhere only a tag",
     but(source="https://archive.org/details/psp-blocks", release={"tag": "1.0"}), False),
    ("release elsewhere without published_at",
     but(source="https://archive.org/details/psp-blocks",
         release={"tag": "1.0", "url": "https://archive.org/download/b/b.zip"}), False),
    ("release elsewhere without url",
     but(source="https://archive.org/details/psp-blocks",
         release={"tag": "1.0", "published_at": "2011-05-04"}), False),
    ("a list", [FULL], False),
    ("a string", "PSPDX", False),
    ("null", None, False),
    ("a number", 1, False),
]


# A catalog entry keeps the file's rule for a source outside GitHub: the list
# that vouches for it and a name with a letter or a digit, since those two make
# its id. The entry is judged by the catalog schema, and the file it would be
# built from by look.py, and the two must agree with the table.
RELEASE = {"tag": "v1.0", "published_at": "2026-09-12T00:00:00Z",
           "url": "https://github.com/chriopter/pspdx/releases/download/v1.0/pspdx.zip",
           "size": 1, "sha256": "0" * 64}
ENTRY = {"id": "io.github.chriopter.pspdx", "source": "https://github.com/chriopter/pspdx",
         "name": "PSPDX", "releases": [RELEASE]}
MIRROR = dict(ENTRY, id="de.wijsman.pspblocks", source="https://archive.org/details/psp-blocks",
              name="PSP Blocks", listed_by="https://wijsman.de/psp-homebrew-database/")
UNLISTED = {k: v for k, v in MIRROR.items() if k != "listed_by"}

ENTRY_CASES = [
    ("an entry from GitHub", ENTRY, True),
    ("an entry from GitHub, listed by a list", dict(ENTRY, listed_by="https://wijsman.de/"), True),
    ("an entry from GitHub, a name of no letter or digit", dict(ENTRY, name="\u2605 \u2014 \u2605"), True),
    ("an entry from elsewhere", MIRROR, True),
    ("an entry from elsewhere without listed_by", UNLISTED, False),
    ("an entry on GitLab without listed_by",
     dict(UNLISTED, source="https://gitlab.com/chriopter/pspdx"), False),
    ("an entry on www.github.com without listed_by",
     dict(UNLISTED, source="https://www.github.com/chriopter/pspdx"), False),
    ("an entry from elsewhere, a name of no letter or digit", dict(MIRROR, name="\u2605 \u2014 \u2605"), False),
    ("an entry from elsewhere, a name of one digit", dict(MIRROR, name="\u2605 2 \u2605"), True),
    ("an entry from elsewhere, listed_by empty", dict(MIRROR, listed_by=""), False),
    ("an entry from elsewhere, listed under github.io",
     dict(MIRROR, listed_by="https://chriopter.github.io/"), False),
    ("an entry from GitHub, listed under github.io",
     dict(ENTRY, listed_by="https://chriopter.github.io/"), True),
    ("an entry from elsewhere, listed by 例え.jp", dict(MIRROR, listed_by="https://例え.jp/"), False),
    ("an entry from elsewhere, listed by xn--r8jz45g.jp",
     dict(MIRROR, listed_by="https://xn--r8jz45g.jp/"), True),
    ("an entry from GitHub, an owner of 39",
     dict(ENTRY, source="https://github.com/" + "o" * 39 + "/pspdx"), True),
    ("an entry from GitHub, an owner of 40",
     dict(ENTRY, source="https://github.com/" + "o" * 40 + "/pspdx"), False),
    ("an entry from GitHub, a repository of 100",
     dict(ENTRY, source="https://github.com/chriopter/" + "r" * 100), True),
    ("an entry from GitHub, a repository of 101",
     dict(ENTRY, source="https://github.com/chriopter/" + "r" * 101), False),
    ("an entry from GitHub, ending .git.git",
     dict(ENTRY, source="https://github.com/chriopter/pspdx.git.git"), False),
    ("an entry installed to PSP/GAME/Demo", dict(ENTRY, installdir="PSP/GAME/Demo"), True),
    ("an entry installed to PSP/GAME/Demo.", dict(ENTRY, installdir="PSP/GAME/Demo."), False),
]


# A time a catalog carries is one the calendar has: a release's, which may be
# a bare date, and the catalog's own, which is a UTC second. look.moment is the
# builder's word on a pinned release's.
DATE_CASES = [
    ("2024-02-29T12:00:00Z", True),
    ("2023-02-29T12:00:00Z", False),
    ("2023-02-31T00:00:00Z", False),
    ("2024-02-29", True),
    ("2023-02-29", False),
    ("2023-02-31", False),
]


# A catalog calls its entries as it likes: its id is free text, and only one
# of no characters, of more than 159 or with a control character is refused.
ID_CASES = [
    ("no id", {k: v for k, v in ENTRY.items() if k != "id"}, True),
    ("the id the builder derives", ENTRY, True),
    ("a word", dict(ENTRY, id="oceanpop"), True),
    ("an underscore", dict(ENTRY, id="laser_kombat"), True),
    ("a path", dict(ENTRY, id="../../x"), True),
    ("159 characters", dict(ENTRY, id="x" * 159), True),
    ("160 characters", dict(ENTRY, id="x" * 160), False),
    ("empty", dict(ENTRY, id=""), False),
    ("a newline", dict(ENTRY, id="one\ntwo"), False),
    ("a number", dict(ENTRY, id=7), False),
]


def where(url):
    return os.path.join(DIRECTORY, url.rsplit("/", 1)[1]) if DIRECTORY else url


@unittest.skipIf(check_schema is None and not NEEDED, "jsonschema is not installed")
class SchemaDriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pspdx = check_schema.load(where(look.PSPDX_SCHEMA))
        cls.catalog = check_schema.load(where(look.SCHEMA))

    def test_look_and_the_schema_judge_every_case_as_the_format_does(self):
        self.assertEqual(self.pspdx["$schema"], "https://json-schema.org/draft/2020-12/schema")
        for what, data, valid in CASES:
            # The one place they part on purpose: a reader ignores a key the
            # format does not name, while the schema refuses it, so that an
            # author checking a file still hears about a misspelt field.
            reader = valid or what in IGNORED_BY_READERS
            with self.subTest(what):
                try:
                    look.validate(data)
                    said = "accepted"
                except look.Problem as problem:
                    said = str(problem)
                # problems() checks the schema itself first, and refuses to
                # run without the format checkers.
                found = check_schema.problems(data, self.pspdx)
                self.assertEqual((said == "accepted", not found), (reader, valid),
                                 f"look.py: {said}; schema: {found or 'accepted'}")

    def test_a_pinned_release_is_held_as_a_catalog_release(self):
        pin = self.pspdx["properties"]["release"]
        release = self.catalog["$defs"]["release"]["properties"]
        self.assertFalse(pin["additionalProperties"])
        self.assertEqual(pin["required"], ["tag"])
        self.assertEqual(set(pin["properties"]), set(look.RELEASE_KEYS))
        for key in look.RELEASE_KEYS:
            with self.subTest(key):
                self.assertEqual({k: v for k, v in pin["properties"][key].items()
                                  if k != "description"},
                                 {k: v for k, v in release[key].items() if k != "description"})
        self.assertEqual(release["url"]["maxLength"], look.URL)

    def test_the_tables_in_look_are_the_schemas(self):
        properties = self.pspdx["properties"]
        self.assertEqual(self.pspdx["$id"], look.PSPDX_SCHEMA)
        self.assertEqual(properties["schema"]["const"], look.PSPDX_SCHEMA)
        self.assertFalse(self.pspdx["additionalProperties"])
        self.assertEqual(set(properties), set(look.KEYS))
        self.assertEqual(set(self.pspdx["required"]), set(look.REQUIRED))
        self.assertEqual(properties["type"]["enum"], list(look.TYPES))
        self.assertEqual(properties["type"]["default"], look.HOMEBREW)
        self.assertEqual((properties["tags"]["maxItems"], properties["tags"]["items"]["maxLength"],
                          properties["tags"]["items"]["minLength"]), (look.TAGS, look.TAG, 1))
        self.assertTrue(properties["tags"]["uniqueItems"])
        self.assertEqual({key: value["maxLength"] for key, value in properties.items()
                          if "maxLength" in value}, look.LIMITS)
        # Every field says what it is and whether it may be left out.
        for key, value in properties.items():
            with self.subTest(key):
                self.assertTrue(value.get("description", "").startswith(
                    "required" if key in look.REQUIRED else "optional"))
        self.assertEqual(self.catalog["$id"], look.SCHEMA)

    def test_the_catalog_repeats_the_fields_as_they_are(self):
        app = self.catalog["$defs"]["app"]["properties"]
        self.assertEqual(set(FIELDS) | set(SAME_RULE) | set(FILE_ONLY) | {"schema"},
                         set(look.KEYS))
        for field in FILE_ONLY:
            self.assertNotIn(field, app)
        for field in FIELDS:
            with self.subTest(field):
                self.assertEqual(app[field], self.pspdx["properties"][field])
        for field in SAME_RULE:
            with self.subTest(field):
                self.assertEqual({k: v for k, v in app[field].items() if k != "description"},
                                 {k: v for k, v in self.pspdx["properties"][field].items()
                                  if k != "description"})
        # An entry needs no more than a file does, and its releases. The id
        # is the catalog's to give or leave out: the builder writes the one it
        # derives, and a console makes its own where a catalog's is none.
        self.assertEqual(set(self.catalog["$defs"]["app"]["required"]),
                         {"source", "name", "releases"})
        self.assertTrue(app["id"]["description"].startswith("optional"))
        # The conditions between fields are the file's, word for word, but
        # for those about a field only a file has.
        self.assertEqual(self.catalog["$defs"]["app"]["allOf"],
                         [rule for rule in self.pspdx["allOf"]
                          if not any(f'"{field}"' in json.dumps(rule) for field in FILE_ONLY)])

    def test_a_catalog_entry_from_outside_github_names_its_list(self):
        for what, app, valid in ENTRY_CASES:
            with self.subTest(what):
                catalog = {"schema": look.SCHEMA, "generated_at": "2026-09-12T00:00:00Z",
                           "apps": [app]}
                found = check_schema.problems(catalog, self.catalog)
                file = dict({k: v for k, v in app.items() if k in look.KEYS},
                            schema=look.PSPDX_SCHEMA)
                try:
                    look.validate(file)
                    said = "accepted"
                except look.Problem as problem:
                    said = str(problem)
                self.assertEqual((not found, said == "accepted"), (valid, valid),
                                 f"schema: {found or 'accepted'}; look.py: {said}")

    def test_a_catalog_dates_only_what_the_calendar_has(self):
        for when, valid in DATE_CASES:
            with self.subTest(when):
                release = dict(RELEASE, published_at=when)
                catalog = {"schema": look.SCHEMA, "generated_at": "2026-09-12T00:00:00Z",
                           "apps": [dict(ENTRY, releases=[release])]}
                found = check_schema.problems(catalog, self.catalog)
                self.assertEqual((not found, look.moment(when)), (valid, valid), found)
                if "T" in when:
                    found = check_schema.problems(dict(catalog, generated_at=when), self.catalog)
                    self.assertEqual(not found, valid, found)

    def test_a_catalog_names_its_entries_as_it_likes(self):
        for what, app, valid in ID_CASES:
            with self.subTest(what):
                catalog = {"schema": look.SCHEMA, "generated_at": "2026-09-12T00:00:00Z",
                           "apps": [app]}
                found = check_schema.problems(catalog, self.catalog)
                self.assertEqual(not found, valid, found)


if __name__ == "__main__":
    unittest.main()
