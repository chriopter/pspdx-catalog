# PSPDX catalog

https://chriopter.github.io/pspdx-catalog/

The list of PSP homebrew [PSPDX](https://github.com/chriopter/pspdx) shows
on the console, and the hourly job that turns it into a catalog. Adding an
app is a line in `repos.txt`; everything about the app itself is in the
`.pspdx` in its own repository.

## Every file here

| | |
|---|---|
| [`repos.txt`](repos.txt) | The list. One GitHub repository a line, `@tag` after the URL to pin a release. The only file a person edits. |
| [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) | Runs `look.py` every hour, on a push and on request, and deploys the site to GitHub Pages when it says something moved. Goes red afterwards if an app was left out. |
| [`.github/look.py`](.github/look.py) | The job itself. Reads each repository's `.pspdx` and checks it against the format, asks GitHub for the repository and its latest release, downloads the one zip, hashes it, finds the one `EBOOT.PBP`, reads its `PARAM.SFO`, and takes the icon, the picture, the film and the sound out of the PBP. Writes `catalog.json`, the media, `state.json` and the page. |
| [`.github/page.py`](.github/page.py) | The page: one card an app, and the apps that were left out with their reason. Style inside it, nothing fetched from anywhere. |
| [`.gitignore`](.gitignore) | `site/` and `__pycache__/`, both built, neither committed. |
| `README.md` | This. |

## What the job publishes

| | |
|---|---|
| `catalog.json` | What the console fetches: every app with its name, author, summary, category, licence, install directory, and the release with its version, date, URL, size and sha256. |
| `icons/`, `shots/`, `vids/`, `snd/` | The four things out of each EBOOT, under names that carry their own bytes, so a changed picture arrives under a new name. |
| `state.json` | What the last run saw: each repository's latest release, plus the hash of the list and of the code. The next run compares against it and publishes nothing when it matches, which is most hours. It is the only memory this repository keeps, and it lives on the site rather than here. |
| `index.html` | The page. |
