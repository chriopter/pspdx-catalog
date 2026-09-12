# PSPDX catalog

The list of PSP homebrew [PSPDX](https://github.com/chriopter/pspdx) shows
on the console. View it here: https://chriopter.github.io/pspdx-catalog/

To list an app, add a `.pspdx` to its repository root and publish a release
with exactly one ZIP containing exactly one `EBOOT.PBP`. Drafts and
pre-releases are not listed. Then open an issue here to request inclusion.
See [pspdx-demo](https://github.com/chriopter/pspdx-demo) for an example.

Once an hour:

1. Every repository on the list is asked for its latest release. An app
   whose version and publishing date are already in the published catalog is
   reused: its entry is copied from the published catalog without fetching
   its `.pspdx` or ZIP again.
2. For the rest, the `.pspdx` is read, the zip on the release is downloaded
   and hashed, and the icon, the picture, the film and the sound are taken
   out of the EBOOT inside it, where present and valid. All four media
   files are optional.
3. If the catalog that comes out says anything the published one does not,
   it and this site are built again and deployed. Media and saved `.pspdx`
   files for reused entries are copied from the published site; if that
   fails, those apps are read from their repositories again.
   Most hours there is nothing to deploy.

An author who edits their `.pspdx` without publishing a release is not
noticed until they do. A push to this catalog repository's `master` branch,
or a workflow run started by hand, reads everything again and publishes
the result when at least one app can be listed.

## Every file here

- [`repos.txt`](repos.txt) is the list. One repo a line, `@tag` to freeze one at a release.
- [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs it hourly, on a push and on request.
- [`.github/look.py`](.github/look.py) reads the repos and writes the site.
- [`.github/page.py`](.github/page.py) builds the pages, the style and the wave.
- [`.github/test_look.py`](.github/test_look.py) checks catalog processing;
  the workflow runs these tests before reading the repositories.

Run the tests locally with:

```sh
python3 -m unittest discover -s .github -p 'test_*.py' -v
```

## Catalog site structure

Generated when publishing, never committed.

- `catalog.json` is every app with its release, so the PSP asks once, and
  it is the memory: what is published is what the next run compares against.
- `catalog.html` prints that file for a person to read.
- `index.html` is the tiles, for whoever has no PSP.
- `apps/<id>/` is one app: its page, the available valid media from its
  EBOOT, and the `.pspdx` used for its catalog entry.
