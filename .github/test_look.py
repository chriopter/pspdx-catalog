import io
import json
import pathlib
import struct
import tempfile
import unittest
import zipfile

import look
import page


class CatalogRegressionTests(unittest.TestCase):
    def test_repo_is_required_and_must_be_a_github_url(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "category": "demo", "installdir": "PSP/GAME/Example"}
        with self.assertRaisesRegex(look.Problem, "repo"):
            look.validate(spec)
        for repo in (None, 12, "", "example/demo", "http://github.com/example/demo",
                     "https://example.com/demo", "https://github.com/example/demo\n",
                     "https://github.com/example/demo/issues"):
            with self.subTest(repo=repo), self.assertRaisesRegex(look.Problem, "repo"):
                look.validate(dict(spec, repo=repo))
        look.validate(dict(spec, repo="https://github.com/example/demo"))

    def test_spdx_license_with_or_later_suffix(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "repo": "https://github.com/example/demo",
                "category": "game", "installdir": "PSP/GAME/Example",
                "license": "GPL-2.0-or-later"}
        self.assertEqual(look.validate(spec)["license"], "GPL-2.0-or-later")

    def test_site_build_survives_truncated_png(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "repo": "https://github.com/example/demo",
                "category": "demo", "installdir": "PSP/GAME/Example"}
        media, _ = look.pictures({
            "ICON0.PNG": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"})
        app = dict(spec, id="io.github.example.demo", author="example",
                   summary="Example", license="MIT",
                   repo="https://github.com/example/demo",
                   release={"version": "1.0", "rev": 1, "size": 123,
                            "sha256": "0" * 64,
                            "url": "https://github.com/example/demo/releases/download/v1/demo.zip"},
                   _media=media, _raw=json.dumps(spec).encode(),
                   _pspdx="https://github.com/example/demo/blob/master/.pspdx",
                   _page="https://github.com/example/demo/releases/tag/v1")
        with tempfile.TemporaryDirectory() as directory:
            catalog = look.shape([app], "2026-09-12T00:00:00Z")
            look.write_site([app], [], catalog, directory)
            out = pathlib.Path(directory)
            self.assertEqual(json.loads((out / "catalog.json").read_text()), catalog)
            self.assertIn("Example", (out / "index.html").read_text())
            self.assertTrue((out / "apps" / app["id"] / "index.html").is_file())

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
                "repo": "https://github.com/example/demo",
                "category": "demo"}
        for folder in (".", "..", "../Other", "Example\n"):
            with self.subTest(folder=folder), self.assertRaises(look.Problem):
                look.validate(dict(spec, installdir="PSP/GAME/" + folder))
        for folder in ("PSPDXDemo", "Example-1.2", ".example", "A" * 32):
            with self.subTest(folder=folder):
                look.validate(dict(spec, installdir="PSP/GAME/" + folder))


if __name__ == "__main__":
    unittest.main()
