# PSPDX catalog

The catalog [PSPDX](https://github.com/chriopter/pspdx) fetches, served as one
[catalog.json](https://chriopter.github.io/pspdx-catalog/catalog.json). Fields
and reasoning: [main repository](https://github.com/chriopter/pspdx).

**Hourly scan, or an issue opened here → release changed → catalog rebuilt.**

## Currently listed apps

| | | |
|---|---|---|
| **[Abandoned Test App](https://github.com/chriopter/psp-dx-testapp-abandoned)** | apps · MIT | 1 |
| **[Extreme Tux Racer](https://github.com/chriopter/psp-tuxracer)** | games · GPL-2.0 | 0.21.0 |
| **[PSPDX Test App](https://github.com/chriopter/psp-dx-testapp)** | apps · MIT | 2 |
| **[Rust Raytracer](https://github.com/chriopter/psp-rust-raytracer)** | demos · MIT | 0.1.0 |

By hand for now.

## Getting in

- **List an app** — a pull request adding `apps/<id>/app.json`, or an issue.
  Open source licences only.
- **Pick a release up now** — an issue titled `rescan: <repo url>`.

## What a release needs

- One `.zip` attached. More assets, and the entry names one in
  `archive.asset`. No 7z, no rar.
- An `EBOOT.PBP` anywhere inside. The shallowest wins.
- Everything the app needs beside it or below: that directory is the package.

Two EBOOTs at the same depth is a coin toss. A layout that moves between
releases is refused, with an issue.

## An app bundle

Named after the `id` inside it. [One of them](apps/io.github.chriopter.rustraytracer).

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
| [`hourly-scan.yml`](.github/workflows/hourly-scan.yml) | Runs the scan hourly, commits, deploys. |
| [`trigger-scan.yml`](.github/workflows/trigger-scan.yml) | Scans one repository when an issue asks. |
| [`build-catalog.yml`](.github/workflows/build-catalog.yml) | Builds the site and publishes it. |

No binaries here. Those stay in their authors' releases.
