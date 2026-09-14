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

FIELDS = ("name", "author", "summary", "category", "license", "installdir", "source")

FULL = {
    "schema": look.PSPDX_SCHEMA,
    "source": "https://github.com/chriopter/pspdx",
    "name": "PSPDX",
    "author": "chriopter",
    "summary": "Download, run and update homebrew on your PSP.",
    "category": "app",
    "license": "GPL-2.0-only",
    "installdir": "PSP/GAME/PSPDX",
}
MINIMAL = {key: FULL[key] for key in look.REQUIRED}


def but(**changes):
    return dict(FULL, **changes)


def without(key):
    return {k: v for k, v in FULL.items() if k != key}


# (what it is, the file, whether it is a valid .pspdx)
CASES = [
    ("every field", FULL, True),
    ("only the required fields", MINIMAL, True),
    ("empty optional strings", but(author="", summary="", license=""), True),
    ("an unknown key", but(version="1.0"), False),
    ("a key in another case", dict(MINIMAL, Name="PSPDX"), False),
    *[(f"no {key}", without(key), False) for key in look.REQUIRED],
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
    ("source on GitLab", but(source="https://gitlab.com/chriopter/pspdx"), False),
    ("source with www", but(source="https://www.github.com/chriopter/pspdx"), False),
    ("source an owner", but(source="https://github.com/chriopter"), False),
    ("source a page in a repository",
     but(source="https://github.com/chriopter/pspdx/issues"), False),
    ("source pinned", but(source="https://github.com/chriopter/pspdx@v1"), False),
    ("source with a query", but(source="https://github.com/chriopter/pspdx?tab=readme"), False),
    ("source with a newline", but(source="https://github.com/chriopter/pspdx\n"), False),
    ("source a list", but(source=["https://github.com/chriopter/pspdx"]), False),
    ("name empty", but(name=""), False),
    ("name 39", but(name="n" * 39), True),
    ("name 39 characters of two bytes", but(name="\u00e9" * 39), True),
    ("name 40", but(name="n" * 40), False),
    ("summary 60", but(summary="s" * 60), True),
    ("summary 61", but(summary="s" * 61), False),
    ("license 64", but(license="l" * 64), True),
    ("license 65", but(license="l" * 65), False),
    ("author 39", but(author="a" * 39), True),
    ("author 40", but(author="a" * 40), False),
    ("name a number", but(name=5), False),
    ("summary null", but(summary=None), False),
    ("author true", but(author=True), False),
    ("license a list", but(license=["MIT"]), False),
    ("installdir a number", but(installdir=5), False),
    ("category a list", but(category=["app"]), False),
    *[(f"category {c!r}", but(category=c), True) for c in look.CATEGORIES],
    *[(f"category {c!r}", but(category=c), False)
      for c in ("App", "apps", "games", "tool", "utility", " app", "")],
    ("installdir with dots inside", but(installdir="PSP/GAME/Example-1.2_b"), True),
    ("installdir starting with a dot", but(installdir="PSP/GAME/.example"), True),
    ("installdir three dots", but(installdir="PSP/GAME/..."), True),
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
    ("a list", [FULL], False),
    ("a string", "PSPDX", False),
    ("null", None, False),
    ("a number", 1, False),
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
            with self.subTest(what):
                try:
                    look.validate(data)
                    said = "accepted"
                except look.Problem as problem:
                    said = str(problem)
                # problems() checks the schema itself first, and refuses to
                # run without the format checkers.
                found = check_schema.problems(data, self.pspdx)
                self.assertEqual((said == "accepted", not found), (valid, valid),
                                 f"look.py: {said}; schema: {found or 'accepted'}")

    def test_the_tables_in_look_are_the_schemas(self):
        properties = self.pspdx["properties"]
        self.assertEqual(self.pspdx["$id"], look.PSPDX_SCHEMA)
        self.assertEqual(properties["schema"], {"const": look.PSPDX_SCHEMA})
        self.assertFalse(self.pspdx["additionalProperties"])
        self.assertEqual(set(properties), set(look.KEYS))
        self.assertEqual(set(self.pspdx["required"]), set(look.REQUIRED))
        self.assertEqual(properties["category"]["enum"], list(look.CATEGORIES))
        self.assertEqual({key: value["maxLength"] for key, value in properties.items()
                          if "maxLength" in value}, look.LIMITS)
        self.assertEqual(self.catalog["$id"], look.SCHEMA)

    def test_the_catalog_repeats_the_fields_as_they_are(self):
        app = self.catalog["$defs"]["app"]["properties"]
        for field in FIELDS:
            with self.subTest(field):
                self.assertEqual(app[field], self.pspdx["properties"][field])


if __name__ == "__main__":
    unittest.main()
