import io
import json
import pathlib
import struct
import tempfile
import unittest
import zipfile

import config
import look
import page


class CatalogRegressionTests(unittest.TestCase):
    def test_catalog_configuration_rebrands_pages_and_drives_live_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "catalog.config.json"
            data = dict(name="Someone's <Catalog>", description="A & B homebrew",
                        site_url="https://example.github.io/other/",
                        repository_url="https://github.com/example/other")
            path.write_text(json.dumps(data))
            settings = config.load(path)
            self.assertEqual(settings["catalog_url"],
                             "https://example.github.io/other/catalog.json")
            html = page.shell(settings["name"], "./", "", "", settings)
            self.assertIn("Someone&#x27;s &lt;Catalog&gt;", html)
            self.assertIn("https://github.com/example/other/issues", html)
            self.assertNotIn("chriopter/pspdx-catalog", html)
            self.assertNotIn("<Catalog>", html)
            data["site_url"] = "http://example.com/"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "site_url"):
                config.load(path)

    def test_source_is_required_and_must_be_a_github_url(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "category": "demo", "installdir": "PSP/GAME/Example"}
        with self.assertRaisesRegex(look.Problem, "source"):
            look.validate(spec)
        for repo in (None, 12, "", "example/demo", "http://github.com/example/demo",
                     "https://example.com/demo", "https://github.com/example/demo\n",
                     "https://github.com/example/demo/issues"):
            with self.subTest(repo=repo), self.assertRaisesRegex(look.Problem, "source"):
                look.validate(dict(spec, source=repo))
        look.validate(dict(spec, source="https://github.com/example/demo"))

    def test_manifest_source_must_match_listed_repository(self):
        spec = {"source": "https://github.com/example/demo"}
        look.check_source(spec, "example", "demo")
        look.check_source(spec, "Example", "Demo")
        for owner, repo in (("other", "demo"), ("example", "other")):
            with self.subTest(owner=owner, repo=repo), self.assertRaisesRegex(
                    look.Problem, '"source" must point to'):
                look.check_source(spec, owner, repo)

    def test_spdx_license_with_or_later_suffix(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/demo",
                "category": "game", "installdir": "PSP/GAME/Example",
                "license": "GPL-2.0-or-later"}
        self.assertEqual(look.validate(spec)["license"], "GPL-2.0-or-later")

    def test_site_build_survives_truncated_png(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/demo",
                "category": "demo", "installdir": "PSP/GAME/Example"}
        media, _ = look.pictures({
            "ICON0.PNG": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"})
        app = dict(spec, id="io.github.example.demo", author="example",
                   summary="Example", license="MIT",
                   source="https://github.com/example/demo",
                   release={"tag": "v1.0", "published_at": "2026-09-12T00:00:00Z",
                            "download": {"size": 123, "sha256": "0" * 64,
                                         "url": "https://github.com/example/demo/releases/download/v1/demo.zip"}},
                   _media=media, _raw=json.dumps(spec).encode(),
                   _pspdx="https://github.com/example/demo/blob/master/.pspdx",
                   _page="https://github.com/example/demo/releases/tag/v1")
        with tempfile.TemporaryDirectory() as directory:
            catalog = look.shape([app], "2026-09-12T00:00:00Z")
            look.write_site([app], [], catalog, directory)
            out = pathlib.Path(directory)
            self.assertEqual(json.loads((out / "catalog.json").read_text()), catalog)
            self.assertIn("Example", (out / "index.html").read_text())
            self.assertIn("generated_at", (out / "catalog.json").read_text())
            self.assertIn("media", catalog["apps"][0])
            self.assertTrue((out / "apps" / app["id"] / "index.html").is_file())
            settings = dict(config.load(), name="Other catalog",
                            description="Another person's apps",
                            repository_url="https://github.com/example/other")
            page.render(catalog, [app], [], directory, settings)
            self.assertIn("<title>Other catalog</title>", (out / "index.html").read_text())
            self.assertIn("Another person&#x27;s apps", (out / "index.html").read_text())
            self.assertIn("Example - Other catalog",
                          (out / "apps" / app["id"] / "index.html").read_text())
            self.assertIn("catalog.json - Other catalog", (out / "catalog.html").read_text())
            self.assertEqual(json.loads((out / "catalog.json").read_text()), catalog)

    def test_truncated_png_does_not_abort_page_generation(self):
        png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
        png += struct.pack(">II", 144, 80)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "icon.png"
            for length in range(len(png)):
                with self.subTest(length=length):
                    path.write_bytes(png[:length])
                    self.assertEqual(page.pixels(path), "")
            path.write_bytes(png)
            self.assertEqual(page.pixels(path), "144x80")

    def test_eboot_requires_exact_filename(self):
        with zipfile.ZipFile(io.BytesIO(), "w") as archive:
            archive.writestr("Game/NOT_EBOOT.PBP", b"")
            with self.assertRaisesRegex(look.Problem, "no EBOOT"):
                look.eboot(archive)
            archive.writestr("Game\\eboot.pbp", b"")
            self.assertEqual(look.eboot(archive),
                             ("Game\\eboot.pbp", "Game/"))
            archive.writestr("Other/EBOOT.PBP", b"")
            with self.assertRaisesRegex(look.Problem, "2 EBOOT"):
                look.eboot(archive)

    def test_install_directory_excludes_dot_components(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/demo",
                "category": "demo"}
        for folder in (".", "..", "../Other", "Example\n"):
            with self.subTest(folder=folder), self.assertRaises(look.Problem):
                look.validate(dict(spec, installdir="PSP/GAME/" + folder))
        for folder in ("PSPDXDemo", "Example-1.2", ".example", "A" * 32):
            with self.subTest(folder=folder):
                look.validate(dict(spec, installdir="PSP/GAME/" + folder))


if __name__ == "__main__":
    unittest.main()
