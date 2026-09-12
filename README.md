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

| | |
|---|---|
| [`repos.txt`](repos.txt) | The list of all repos in the PSPDX standard. One a line, `@tag` after the URL to freeze an app at one release. The only file a person edits. |
| [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) | Runs once an hour, on a push and on request. Calls `look.py`, deploys the site when something changed, and goes red afterwards if an app was left out. |
| [`.github/look.py`](.github/look.py) | Reads each repo's `.pspdx` and its latest release, downloads the zip, hashes it, extracts the XMB media out of the EBOOT, and writes the site. |
| [`.github/page.py`](.github/page.py) | Builds the browsable catalog page: the markup and the style, all in one file, nothing fetched from anywhere. |

## Catalog site structure

| | |
|---|---|
| `catalog.json` | The full list of apps with their releases. That way the PSP does not have to query every listed repo. |
| `index.html` | The page, for whoever has no PSP in their hands. |
| `icons/ shots/ vids/ snd/` | The media extracted from each app's EBOOT, one file an app in each, named after the app and the bytes it holds. |
| `state.json` | The latest release of every repo, and a hash of the list and of the code, so the next run can tell whether anything changed. |
