# PSPDX catalog

The catalog [PSPDX](https://github.com/chriopter/pspdx) fetches. One directory
per app in `apps/`, folded into a single
[catalog.json](https://chriopter.github.io/pspdx-catalog/catalog.json) and
served from Pages.

What the files mean, how a release finds its way in here, and why any of it is
shaped this way: **[see the main repository](https://github.com/chriopter/pspdx)**.

- **To get an app listed** — open a pull request adding `apps/<id>/app.json`,
  or open an issue and ask. Open source licences only.
- **To have a release picked up now** rather than within the hour — open an
  issue titled `rescan: <repo url>`.

## What is in here

| | |
|---|---|
| `apps/<id>/app.json` | The entry. Upper half by hand — `id`, `name`, `author`, `summary`, `category`, `license`, `repo`. Lower half by `scan.py` — `release` and `archive`. |
| `apps/<id>/screenshot.png` | 480x272, optional. Fetched only for the app on screen. |
| `apps/<id>/video.mp4` | Ten seconds of H.264 baseline, optional. What the Media Engine can decode. |
| `scan.py` | Asks GitHub for the newest release, downloads it, hashes the bytes it received, looks inside the archive, writes `release` and `archive`. Refuses when the package has moved inside the archive. Needs the network. |
| `build.py` | Folds `apps/*/app.json` into one `catalog.json`, copies the assets to `shots/` and `vids/`, drops `archive`. Never touches the network. |
| `.github/workflows/scan.yml` | Hourly, plus a weekly heartbeat, plus a button. Runs `scan.py --all`, commits what it found, then calls `pages.yml`, and opens an issue when something needs a person. |
| `.github/workflows/rescan.yml` | Answers an issue titled `rescan: <url>`, but only for repositories already listed. Scans, commits, comments, closes. |
| `.github/workflows/pages.yml` | Builds `_site` and deploys. Callable, because a push made with `GITHUB_TOKEN` starts nothing by itself. |

No binaries live here. Those stay in their authors' releases.
