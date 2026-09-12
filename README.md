# PSPDX catalog

The list of PSP homebrew [PSPDX](https://github.com/chriopter/pspdx) shows
on the console.

View it here: https://chriopter.github.io/pspdx-catalog/

## What makes an app appear here

- A `.pspdx` in its root
- Being listed here in [`repos.txt`](repos.txt)

An hourly job scans all listed repos for changes and rebuilds the catalog.

See [pspdx-demo](https://github.com/chriopter/pspdx-demo) for an example entry.

## Every file here

- [`repos.txt`](repos.txt) is the list of all repos in the PSPDX standard.
  One a line, `@tag` after the URL to freeze an app at one release. The only
  file a person edits.
- [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs once an
  hour, on a push and on request. It calls `look.py`, deploys the site when
  something changed, and goes red afterwards if an app was left out.
- [`.github/look.py`](.github/look.py) reads each repo's `.pspdx` and its
  latest release, downloads the zip, hashes it, extracts the XMB media out of
  the EBOOT, and writes the site.
- [`.github/page.py`](.github/page.py) builds the pages: the tiles, one page
  an app, and the style and the wave behind them, all in one file with
  nothing fetched from anywhere.

## Catalog site structure

Built every time, committed never.

- `catalog.json` is the full list of apps with their releases. That way the
  PSP does not have to query every listed repo.
- `index.html` and one page an app, for whoever has no PSP in their hands.
- `icons/ shots/ vids/ snd/` hold the media extracted from each app's EBOOT,
  one file an app in each, named after the app and the bytes it holds.
- `state.json` is the latest release of every repo, and a hash of the list
  and of the code, so the next run can tell whether anything changed.
