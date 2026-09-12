# PSPDX catalog

The list of PSP homebrew [PSPDX](https://github.com/chriopter/pspdx) shows
on the console. View it here: https://chriopter.github.io/pspdx-catalog/

To list an app: a root `.pspdx`, a release with exactly one ZIP containing
exactly one `EBOOT.PBP`, and an issue here. No drafts or prereleases.
The `.pspdx` must include `source`, the project's source URL (a GitHub repository in v1).
See [pspdx-demo](https://github.com/chriopter/pspdx-demo) for an example.

## Workflow

Once an hour:

1. Ask each repository for its release. Same version and publishing date:
   reuse its catalog entry; skip the manifest and ZIP.
2. Read changed apps' `.pspdx`, download and hash the ZIP, extract the
   EBOOT's valid media: icon, picture, film, sound. All optional.
3. Deploy if the catalog changed, copying reused apps' files from the
   published site (re-read the repository if that fails).

Manifest-only edits wait for a release. A push to this catalog's `master`
or a manual run reads everything again. No valid apps: keep the live site.

## Every file here

- [`repos.txt`](repos.txt) is the list. One repo a line, `@tag` to freeze one at a release.
- [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs it hourly, on a push and on request.
- [`.github/look.py`](.github/look.py) reads the repos and writes the site.
- [`.github/page.py`](.github/page.py) builds the pages, the style and the wave.
- [`.github/test_look.py`](.github/test_look.py) runs before each build:

```sh
python3 -m unittest discover -s .github -p 'test_*.py' -v
```

## Catalog site structure

Generated when publishing, never committed.

- `catalog.json` is every app with its release, so the PSP asks once, and
  it is the memory: what is published is what the next run compares against.
  Format: [catalog v1 schema](https://github.com/chriopter/pspdx/blob/master/schema/catalog-v1.json).
- `catalog.html` prints that file for a person to read.
- `index.html` is the tiles, for whoever has no PSP.
- `apps/<id>/` is one app: its page, the available valid media from its
  EBOOT, and the `.pspdx` used for its catalog entry.
