import io
import json
import os
import pathlib
import struct
import tempfile
import unittest
import zipfile

import config
import look
import page


class CatalogRegressionTests(unittest.TestCase):
    def test_change_labels_compare_published_apps(self):
        old = {"apps": [{"id": "old", "name": "Old", "releases": [{"tag": "v1"}]},
                        {"id": "gone", "name": "Gone", "releases": [{"tag": "v1"}]}]}
        current = [{"id": "old", "name": "Old", "releases": [{"tag": "v2"}, {"tag": "v1"}]},
                   {"id": "new", "name": "New <App>", "releases": [{"tag": "v1"}]}]
        notes = look.changes(current, old)
        self.assertEqual(notes, [("Update", "Old", "v2"),
                                 ("New app", "New <App>", "v1"),
                                 ("Removed", "Gone", "")])

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

    def test_source_is_required_and_must_be_an_https_url(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "tags": ["demo"], "installdir": "PSP/GAME/Example"}
        with self.assertRaisesRegex(look.Problem, "source"):
            look.validate(spec)
        spec["listed_by"] = "https://wijsman.de/psp-homebrew-database/"
        for repo in (None, 12, "", "example/demo", "http://github.com/example/demo",
                     "http://example.com/demo", "https://", "ftp://example.com/demo",
                     "https://github.com/example/demo\n", "https://example.com/demo\n",
                     "https://github.com/example/demo/issues", "https://github.com/example",
                     "https://example.com/" + "x" * 236):
            with self.subTest(repo=repo), self.assertRaisesRegex(look.Problem, "source"):
                look.validate(dict(spec, source=repo))
        for repo in ("https://github.com/example/demo", "https://example.com/demo",
                     "https://archive.org/details/psp-blocks", "https://example.com/" + "x" * 235):
            with self.subTest(repo=repo):
                look.validate(dict(spec, source=repo))
        # Outside GitHub there is no repository name, and the folder is the
        # app's name in the characters a folder may hold.
        elsewhere = {k: v for k, v in dict(spec, source="https://example.com/demo",
                                           listed_by="https://example.com/").items()
                     if k != "installdir"}
        for name, folder in (("Example", "Example"), ("PSP Blocks: Deluxe!", "PSPBlocksDeluxe"),
                             ("Jeu de rôle 2", "Jeuderle2"), ("A-" * 19 + "B", ("A-" * 19)[:32]),
                             ("v1.2_final", "v1.2_final")):
            with self.subTest(name=name):
                self.assertEqual(look.installdir(look.validate(dict(elsewhere, name=name))),
                                 "PSP/GAME/" + folder)
        for name in (".pspdx-stage", ".PSPDX-Stage", "★ .pspdx-stage ★"):
            with self.subTest(name=name), self.assertRaisesRegex(look.Problem, "cannot be one"):
                look.validate(dict(elsewhere, name=name))
        look.validate(dict(elsewhere, name=".pspdx-stage", installdir="PSP/GAME/Stage"))
        look.validate({"schema": look.PSPDX_SCHEMA, "name": "Example", "type": "plugin",
                       "source": "https://example.com/demo",
                       "listed_by": "https://example.com/"})

    def test_the_id_outside_github_is_the_list_and_the_name(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Blocks", "installdir": "PSP/GAME/Blocks",
                "source": "https://archive.org/details/psp-blocks",
                "listed_by": "https://wijsman.de/psp-homebrew-database/"}
        for changes, expected in (
                ({"source": "https://github.com/example/demo"}, "io.github.example.demo"),
                ({"source": "https://github.com/Example/Demo-1.2.git/"}, "io.github.example.demo12"),
                ({"source": "https://github.com/example/demo", "listed_by": "https://x.org/"},
                 "io.github.example.demo"),
                ({}, "de.wijsman.blocks"),
                ({"name": "PSP Blocks 2 (Deluxe)"}, "de.wijsman.pspblocks2deluxe"),
                ({"name": "Blöcke"}, "de.wijsman.blcke"),
                ({"listed_by": "https://WWW.Wijsman.de"}, "de.wijsman.blocks"),
                ({"listed_by": "https://user@psp-lists.example.co.uk:8443?x#y"},
                 "uk.co.example.psplists.blocks"),
                ({"listed_by": "https://www./list"}, None),
                ({"name": "★ ★"}, None)):
            with self.subTest(changes=changes):
                self.assertEqual(look.identity(dict(spec, **changes)), expected)
        look.validate(spec)
        for changes, reason in (({"listed_by": None}, "needs \"listed_by\""),
                                ({"name": "★ ★"}, "no letter or digit"),
                                ({"listed_by": "https://-/"}, "no host")):
            with self.subTest(changes=changes), self.assertRaisesRegex(look.Problem, reason):
                look.validate({k: v for k, v in dict(spec, **changes).items() if v is not None})
        # A GitHub source needs no list: its id is the repository.
        look.validate({k: v for k, v in dict(spec, source="https://github.com/a/b").items()
                       if k != "listed_by"})

    def test_a_source_outside_github_is_left_out_with_the_reason(self):
        spec = {"source": "https://archive.org/details/psp-blocks"}
        with self.assertRaisesRegex(look.Problem, "non-GitHub source: only a catalog can list it"):
            look.check_source(spec, "example", "demo")

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
                "tags": ["game"], "installdir": "PSP/GAME/Example",
                "license": "GPL-2.0-or-later"}
        self.assertEqual(look.validate(spec)["license"], "GPL-2.0-or-later")

    def test_site_build_survives_truncated_png(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/demo",
                "tags": ["demo"], "installdir": "PSP/GAME/Example"}
        media, _ = look.pictures({
            "ICON0.PNG": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"})
        app = dict(spec, id="io.github.example.demo", author="example",
                   summary="Example", license="MIT",
                   source="https://github.com/example/demo",
                   releases=[{"tag": "v1.0", "published_at": "2026-09-12T00:00:00Z",
                              "size": 123, "sha256": "0" * 64,
                              "url": "https://github.com/example/demo/releases/download/v1/demo.zip"}],
                   _media=media, _raw=json.dumps(spec).encode(),
                   _pspdx="https://github.com/example/demo/blob/master/.pspdx",
                   _page="https://github.com/example/demo/releases/tag/v1")
        with tempfile.TemporaryDirectory() as directory:
            catalog = look.shape([app], "2026-09-12T00:00:00Z")
            look.write_site([app], [], catalog, directory)
            out = pathlib.Path(directory)
            self.assertEqual(json.loads((out / "catalog.json").read_text()), catalog)
            self.assertEqual((out / "catalog.txt").read_text(),
                             (pathlib.Path(look.HERE) / "repos.txt").read_text())
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

    def test_app_page_shows_the_description_the_list_and_every_picture(self):
        home = "apps/io.github.example.demo/"
        app = {"id": "io.github.example.demo", "name": "Demo <One>",
               "source": "https://github.com/example/demo", "author": "example",
               "summary": "Short & sweet", "type": "homebrew", "tags": ["game", "<b>tag</b>"],
               "license": "MIT", "installdir": "PSP/GAME/demo",
               "description": 'First <script>alert("x")</script> & more\nSecond line\n\nThird',
               "listed_by": 'https://user@Wijsman.de:8443/psp?a=1&b="2"',
               "website": "https://example.com/demo?a=1&b=2",
               "media": {"screenshots": [home + "picture-1.png", home + "picture-2.png",
                                         "https://example.com/shot.png"]},
               "releases": [{"tag": "v1.0", "published_at": "2026-09-12", "size": 123,
                             "sha256": "0" * 64,
                             "url": "https://github.com/example/demo/releases/download/v1/demo.zip"}],
               "_pspdx": "https://github.com/example/demo/blob/master/.pspdx",
               "_page": "https://github.com/example/demo/releases/tag/v1"}
        with tempfile.TemporaryDirectory() as directory:
            os.makedirs(os.path.join(directory, *home.split("/")))
            for name in ("picture-1.png", "picture-2.png"):
                pathlib.Path(directory, *home.split("/"), name).write_bytes(b"\x89PNG")
            text = page.app_page(app, directory, config.load())
            self.assertIn("First &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; more<br>",
                          text)
            self.assertIn("Second line<br>\n    <br>\n    Third</p>", text)
            self.assertNotIn("<script>alert", text)
            self.assertIn('Listed by <a href="https://user@Wijsman.de:8443/psp?a=1&amp;b=&quot;2&quot;" '
                          'target="_blank" rel="noopener noreferrer">wijsman.de</a>', text)
            self.assertIn('<a href="https://example.com/demo?a=1&amp;b=2" target="_blank" '
                          'rel="noopener noreferrer">example.com</a>', text)
            self.assertIn("by example &middot; homebrew &middot; game, &lt;b&gt;tag&lt;/b&gt; "
                          "&middot; MIT", text)
            self.assertNotIn("<b>tag</b>", text)
            self.assertIn("<h2>Demo &lt;One&gt;</h2>", text)
            for src in ("../../" + home + "picture-1.png", "../../" + home + "picture-2.png",
                        "https://example.com/shot.png"):
                self.assertIn(f'<img src="{src}" alt="Demo &lt;One&gt; running"', text)

            # Without them the page says nothing about them.
            bare = {k: v for k, v in app.items()
                    if k not in ("description", "listed_by", "website", "media", "type", "tags")}
            text = page.app_page(bare, directory, config.load())
            for absent in ("Listed by", 'class="description"', "Website", 'class="shots"'):
                self.assertNotIn(absent, text)
            self.assertIn("by example &middot; MIT", text)

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
                "tags": ["demo"]}
        for folder in (".", "..", "../Other", "Example\n", ".pspdx-stage", ".PSPDX-Stage"):
            with self.subTest(folder=folder), self.assertRaises(look.Problem):
                look.validate(dict(spec, installdir="PSP/GAME/" + folder))
        for folder in ("PSPDXDemo", "Example-1.2", ".example", "A" * 32):
            with self.subTest(folder=folder):
                look.validate(dict(spec, installdir="PSP/GAME/" + folder))

    def test_install_directory_defaults_to_the_repository_name(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example"}
        for source, folder in (("https://github.com/example/demo", "demo"),
                               ("https://github.com/example/Demo-1.2.git/", "Demo-1.2"),
                               ("https://github.com/example/" + "r" * 40, "r" * 32),
                               ("https://github.com/example/" + "a" * 32 + ".git", "a" * 32)):
            with self.subTest(source=source):
                file = look.validate(dict(spec, source=source))
                self.assertNotIn("installdir", file)
                self.assertEqual(look.installdir(file), "PSP/GAME/" + folder)
                self.assertEqual(look.installdir(dict(file, installdir="PSP/GAME/Other")),
                                 "PSP/GAME/Other")
        for repo in (".", "..", ".pspdx-stage", ".PSPDX-STAGE"):
            with self.subTest(repo=repo):
                source = "https://github.com/example/" + repo
                with self.assertRaisesRegex(look.Problem, "cannot be one"):
                    look.validate(dict(spec, source=source))
                look.validate(dict(spec, source=source, installdir="PSP/GAME/Example"))

    def test_other_types_take_no_install_directory(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/.."}
        for kind in ("plugin", "iso"):
            with self.subTest(kind=kind):
                look.validate(dict(spec, type=kind))
                with self.assertRaisesRegex(look.Problem, "only for type homebrew"):
                    look.validate(dict(spec, type=kind, installdir="PSP/GAME/Example"))

    def entry_with(self, spec):
        """entry() with GitHub answered from here: a release with one zip, a
        repository, and a package that is only its title."""
        return self.history_with(spec, [self.release("v1.0", "2026-09-12T00:00:00Z")])[:2]

    @staticmethod
    def release(tag, when, zips=1, **more):
        return dict({"tag_name": tag, "published_at": when,
                     "html_url": f"https://github.com/example/demo/releases/tag/{tag}",
                     "assets": [{"name": f"demo{i}.zip", "size": 10 + i,
                                 "browser_download_url": "https://github.com/example/demo/"
                                                         f"releases/download/{tag}/demo{i}.zip"}
                                for i in range(zips)]}, **more)

    def history_with(self, spec, releases, known=None, homepage=None):
        """entry() with GitHub answered from here: the releases as the list
        call gives them, a repository, and a package that is only its title.
        Returns the entry, its log and the zips that were downloaded."""
        answers = {"/repos/example/demo/releases?per_page=30": releases,
                   "/repos/example/demo": {"description": "From GitHub", "license": None,
                                           "homepage": homepage}}
        fetched = []

        def package(asset, log):
            fetched.append(asset["browser_download_url"])
            return (asset["browser_download_url"][-9:].encode().hex().ljust(64, "0")[:64], "",
                    {"TITLE": "Demo"}, {}, "5" * 32)
        saved = look.api, look.read_pspdx, look.package
        look.api = lambda path, what: answers[path]
        look.read_pspdx = lambda owner, repo, ref: (look.validate(spec),
                                                    json.dumps(spec).encode())
        look.package = package
        try:
            app, log = look.entry("https://github.com/example/demo", "example", "demo", "", known)
        finally:
            look.api, look.read_pspdx, look.package = saved
        return app, log, fetched

    def test_releases_are_the_newest_twenty_newest_first(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/demo"}
        releases = [self.release(f"v1.{i}", f"2026-01-{i + 1:02d}T00:00:00Z",
                                 body=f"Fixed {i}.\r\n\tIndented\x07") for i in range(25)]
        releases.reverse()
        releases.insert(3, self.release("v9-draft", "2026-02-01T00:00:00Z", draft=True))
        releases.insert(4, self.release("v9-rc", "2026-02-02T00:00:00Z", prerelease=True))
        releases[10]["assets"].append(dict(releases[10]["assets"][0], name="other.zip"))
        releases[11]["tag_name"] = "t" * 65
        app, log, fetched = self.history_with(spec, releases, homepage="https://example.com/demo")
        tags = [r["tag"] for r in app["releases"]]
        self.assertEqual(len(tags), 20)
        self.assertEqual(tags[0], "v1.24")
        self.assertEqual([r["published_at"] for r in app["releases"]],
                         sorted((r["published_at"] for r in app["releases"]), reverse=True))
        self.assertNotIn("v9-draft", tags)
        self.assertNotIn("v9-rc", tags)
        self.assertNotIn(releases[10]["tag_name"], tags)
        self.assertTrue(any("2 zips" in line for line in log), log)
        self.assertTrue(any("1 to 64" in line for line in log), log)
        self.assertEqual(len(fetched), 20)
        newest = app["releases"][0]
        self.assertEqual(newest["changelog"], "Fixed 24.\n Indented")
        self.assertEqual((newest["size"], newest["eboot_md5"]), (10, "5" * 32))
        self.assertEqual(app["website"], "https://example.com/demo")
        self.assertEqual(app["installdir"], "PSP/GAME/demo")

        # A new release is one zip: every older hash is copied forward from the
        # catalog that is published, and an unchanged newest release copies
        # the whole entry.
        known = look.shape([dict(app)], "2026-09-12T00:00:00Z")["apps"][0]
        newer = [self.release("v2.0", "2026-03-01T00:00:00Z")] + releases
        app2, _, fetched = self.history_with(spec, newer, known=known)
        self.assertEqual(fetched, [newer[0]["assets"][0]["browser_download_url"]])
        self.assertEqual(app2["releases"][1:], app["releases"][:19])
        _, log, fetched = self.history_with(spec, newer, known=look.shape(
            [dict(app2)], "2026-09-12T00:00:00Z")["apps"][0])
        self.assertEqual((fetched, log), ([], ["unchanged, v2.0"]))

    def test_the_newest_release_is_held_to_every_rule(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/demo"}
        for broken, reason in ((self.release("v", "2026-01-02T00:00:00Z"), "not just v"),
                               (self.release("v2", "2026-01-02T00:00:00Z", zips=2), "2 zips"),
                               (self.release("v2", "2026-01-02T00:00:00Z", zips=0), "no zip"),
                               (self.release("v2", None), "no published_at")):
            with self.subTest(reason=reason), self.assertRaisesRegex(look.Problem, reason):
                self.history_with(spec, [broken, self.release("v1", "2026-01-01T00:00:00Z")])
        with self.assertRaisesRegex(look.Problem, "no published release"):
            self.history_with(spec, [self.release("v1", "2026-01-01T00:00:00Z", draft=True)])

    def test_other_types_are_left_out_with_the_reason(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/demo"}
        for kind in ("plugin", "iso"):
            with self.subTest(kind=kind), self.assertRaisesRegex(
                    look.Problem, f"type {kind} is not supported by this catalog yet"):
                self.entry_with(dict(spec, type=kind))

    def test_entry_carries_the_new_fields_and_the_derived_directory(self):
        spec = {"schema": look.PSPDX_SCHEMA, "name": "Example",
                "source": "https://github.com/example/demo",
                "description": "Two lines.\nThe second.",
                "listed_by": "https://wijsman.de/psp-homebrew-database/"}
        app, _ = self.entry_with(spec)
        self.assertEqual(app["installdir"], "PSP/GAME/demo")
        self.assertNotIn("tags", app)
        self.assertNotIn("type", app)
        self.assertEqual(app["description"], spec["description"])
        self.assertEqual(app["listed_by"], spec["listed_by"])
        app, _ = self.entry_with(dict(spec, type="homebrew", tags=["Jeu de rôle", "game"],
                                      installdir="PSP/GAME/Example"))
        self.assertEqual((app["type"], app["tags"], app["installdir"]),
                         ("homebrew", ["Jeu de rôle", "game"], "PSP/GAME/Example"))
        # A page for an entry without tags is still a page.
        app, _ = self.entry_with(spec)
        with tempfile.TemporaryDirectory() as directory:
            catalog = look.shape([app], "2026-09-12T00:00:00Z")
            look.write_site([app], [], catalog, directory)
            self.assertIn("Example", (pathlib.Path(directory) / "apps" / app["id"]
                                      / "index.html").read_text())
            try:
                import check_schema
            except ImportError:
                if os.environ.get("CI"):
                    raise
                return
            schema = check_schema.load(os.path.join(os.environ["PSPDX_SCHEMA_DIR"],
                                                    "catalog-v1.json")
                                       if os.environ.get("PSPDX_SCHEMA_DIR") else look.SCHEMA)
            self.assertEqual(check_schema.problems(catalog, schema), [])


if __name__ == "__main__":
    unittest.main()
