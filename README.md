# PSPDX catalog

The list of PSP homebrew [PSPDX](https://github.com/chriopter/pspdx) shows
on the console. View it here: https://chriopter.github.io/pspdx-catalog/

To list an app, add a `.pspdx` to its repository and open an issue here.
See [pspdx-demo](https://github.com/chriopter/pspdx-demo) for an example.

Once an hour:

1. Every repository on the list is asked for its latest release. An app
   whose version and publishing date are already in the published catalog is
   skipped: its entry is copied out, and nothing of it is fetched.
2. For the rest, the `.pspdx` is read, the zip on the release is downloaded
   and hashed, and the icon, the picture, the film and the sound are taken
   out of the EBOOT inside it.
3. If the catalog that comes out says anything the published one does not,
   it and this site are built again and deployed. Most hours it does not.

An author who edits their `.pspdx` without publishing a release is not
noticed until they do; a push, or a run started by hand, reads everything
again.

## Every file here

- [`repos.txt`](repos.txt) is the list. One repo a line, `@tag` to freeze one at a release.
- [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs it hourly, on a push and on request.
- [`.github/look.py`](.github/look.py) reads the repos and writes the site.
- [`.github/page.py`](.github/page.py) builds the pages, the style and the wave.

## Catalog site structure

Built every time, committed never.

- `catalog.json` is every app with its release, so the PSP asks once, and
  it is the memory: what is published is what the next run compares against.
- `catalog.html` prints that file for a person to read.
- `index.html` is the tiles, for whoever has no PSP.
- `apps/<id>/` is one app: its page, its icon, picture, film and sound out
  of the EBOOT, and the `.pspdx` the run read.
