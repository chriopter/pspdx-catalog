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

## An app bundle

One directory per app, named after its id. Here is [a whole one](apps/io.github.chriopter.rustraytracer).

| | |
|---|---|
| [`app.json`](apps/io.github.chriopter.rustraytracer/app.json) | The entry. Half by hand, half by `scan.py`. |
| `icon.png` | 144x80, out of the EBOOT. Optional. |
| [`screenshot.png`](apps/io.github.chriopter.rustraytracer/screenshot.png) | 480x272 still. Optional. |
| [`video.mp4`](apps/io.github.chriopter.rustraytracer/video.mp4) | Ten seconds of H.264 baseline. Optional. |

## The machinery

| | |
|---|---|
| [`scan.py`](scan.py) | Reads the newest release, hashes it, looks inside. |
| [`build.py`](build.py) | Folds every entry into one `catalog.json`. |
| [`scan.yml`](.github/workflows/scan.yml) | Runs the scan hourly, commits, deploys. |
| [`rescan.yml`](.github/workflows/rescan.yml) | Scans one repository when an issue asks. |
| [`pages.yml`](.github/workflows/pages.yml) | Builds the site and publishes it. |

No binaries live here. Those stay in their authors' releases.
