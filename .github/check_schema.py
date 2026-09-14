#!/usr/bin/env python3
"""Checks a built catalog against the published catalog schema, before the
catalog is published: a file consoles cannot trust is not deployed, the site
that is up stays up, and every reason is printed with the place it is at.

    check_schema.py                      site/catalog.json
    check_schema.py <catalog.json>       another file
    check_schema.py --schema <file|url>  another schema, e.g. offline

    pip install -r .github/requirements.txt

look.py reads the rules by hand so an author gets a sentence; this is the
other half, the whole file against the schema as written, so the two cannot
drift apart unnoticed."""
import json
import os
import sys
import urllib.request

import jsonschema

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = "https://chriopter.github.io/pspdx/schema/catalog-v1.json"

# jsonschema passes a format it has no checker for without a word, and the
# checkers for these come from separate packages. A check that silently stops
# checking dates and links is worse than none, so their absence is an error.
FORMATS = ("date-time", "uri", "uri-reference")


def load(where):
    if where.startswith("https://"):
        with urllib.request.urlopen(where, timeout=30) as response:
            return json.load(response)
    with open(where, encoding="utf-8") as source:
        return json.load(source)


def problems(catalog, schema):
    """Every place the catalog breaks the schema, in document order."""
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    checker = cls.FORMAT_CHECKER
    missing = [name for name in FORMATS if name not in checker.checkers]
    if missing:
        raise RuntimeError(f"no checker for format {', '.join(missing)}; "
                           "install .github/requirements.txt")
    errors = cls(schema, format_checker=checker).iter_errors(catalog)
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
