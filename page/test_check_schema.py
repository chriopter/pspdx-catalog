import os
import unittest

try:
    import check_schema
except ImportError:
    check_schema = None

# The workflow installs requirements.txt before the tests, so there a missing
# module is a broken step and must fail; on a bare checkout it only skips.
NEEDED = bool(os.environ.get("CI"))

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["generated_at", "apps"],
    "properties": {
        "generated_at": {"type": "string", "format": "date-time"},
        "apps": {"type": "array", "items": {
            "type": "object",
            "required": ["url", "icon", "sha256"],
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "icon": {"type": "string", "format": "uri-reference"},
                "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            }}},
    },
}
APP = {"url": "https://github.com/example/demo/releases/download/v1/demo.zip",
       "icon": "media/demo/icon.png", "sha256": "0" * 64}


@unittest.skipIf(check_schema is None and not NEEDED, "jsonschema is not installed")
class CheckSchemaTests(unittest.TestCase):
    def test_a_good_catalog_has_no_problems(self):
        catalog = {"generated_at": "2026-09-14T12:00:00Z", "apps": [APP]}
        self.assertEqual(check_schema.problems(catalog, SCHEMA), [])

    def test_formats_are_really_checked_and_every_error_has_its_place(self):
        unsigned = {key: value for key, value in APP.items() if key != "sha256"}
        apps = [APP, unsigned, dict(APP, url="not a uri", icon="a b\\c", sha256="xyz")]
        for stamp in ("2026-09-14", "yesterday"):
            with self.subTest(stamp=stamp):
                found = check_schema.problems({"generated_at": stamp, "apps": apps}, SCHEMA)
                self.assertEqual([line.split(":")[0] for line in found],
                                 ["$.apps[1]", "$.apps[2].icon", "$.apps[2].sha256",
                                  "$.apps[2].url", "$.generated_at"])
                self.assertIn("'sha256' is a required property", found[0])
                self.assertIn("is not a 'date-time'", found[-1])


if __name__ == "__main__":
    unittest.main()
