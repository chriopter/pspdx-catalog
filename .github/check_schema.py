#!/usr/bin/env python3
"""Checks a built catalog against the published catalog schema, before the
catalog is published: a file consoles cannot trust is not deployed, the site
that is up stays up, and every reason is printed with the place it is at.

    check_schema.py                   site/catalog.json
    check_schema.py <catalog.json>    another file
    check_schema.py --schema <file>   another schema, e.g. an unpushed one

    pip install -r .github/requirements.txt

look.py validates each .pspdx against the same schema as it reads a file; this
is the last word, the whole built catalog against the catalog schema, before
anything consoles rely on is published."""
import json
import os
import sys

import jsonschema

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The schema is vendored as the `pspdx` submodule and read from there, so a
# build reads exactly the version this repository is pinned to and never the
# moving published one: an unrelated change to the format cannot make the
# hourly deploy go red on its own. `git submodule update --remote pspdx` bumps
# it, and the diff shows which rules changed. look.py reads the same folder.
SCHEMA_DIR = os.path.join(HERE, "pspdx", "schema")
SCHEMA = os.path.join(SCHEMA_DIR, "catalog-v1.json")

# jsonschema passes a format it has no checker for without a word, and the
# checkers for these come from separate packages. A check that silently stops
# checking dates and links is worse than none, so their absence is an error.
FORMATS = ("date", "date-time", "uri", "uri-reference")


def load(where):
    with open(where, encoding="utf-8") as source:
        return json.load(source)


# A prepared validator per schema: the meta-schema check, the format checkers
# and the compiled schema are done once and reused, since a build asks the same
# schema of every .pspdx. A broken schema or a missing checker is a fault of
# this program's setup, raised the first time and the same for every file.
_VALIDATORS = {}


def validator(schema):
    # Keyed by the schema object itself, not its $id: a build reuses the one
    # schema it loaded, and two schemas that share an $id must not share a
    # validator, or the second is never checked.
    key = id(schema)
    if key not in _VALIDATORS:
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        checker = cls.FORMAT_CHECKER
        missing = [name for name in FORMATS if name not in checker.checkers]
        if missing:
            raise RuntimeError(f"no checker for format {', '.join(missing)}; "
                               "install .github/requirements.txt")
        _VALIDATORS[key] = cls(schema, format_checker=checker)
    return _VALIDATORS[key]


def problems(catalog, schema):
    """Every place the catalog breaks the schema, in document order."""
    errors = validator(schema).iter_errors(catalog)
    # Numbers before names and 2 before 10, so apps come out in list order.
    order = lambda error: [(0, p, "") if isinstance(p, int) else (1, 0, p)
                           for p in error.absolute_path]
    return [f"{error.json_path}: {error.message}" for error in sorted(errors, key=order)]


def main(argv):
    catalog, schema = os.path.join(HERE, "site", "catalog.json"), SCHEMA
    while argv:
        if argv[0] == "--schema" and len(argv) > 1:
            schema, argv = argv[1], argv[2:]
        elif not argv[0].startswith("-"):
            catalog, argv = argv[0], argv[1:]
        else:
            raise SystemExit(__doc__)
    found = problems(load(catalog), load(schema))
    for line in found:
        print(line)
    print(f"{catalog}: {len(found)} schema errors against {schema}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
