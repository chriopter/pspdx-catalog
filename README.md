# PSPDX catalog

The catalog [PSPDX](https://github.com/chriopter/pspdx) fetches: one directory
per app, folded into a single
[catalog.json](https://chriopter.github.io/pspdx-catalog/catalog.json) and
served from Pages.

What the fields mean, and why any of it is shaped this way, lives in the
[main repository](https://github.com/chriopter/pspdx).

## Currently listed apps

| | | |
|---|---|---|
| **[Abandoned Test App](https://github.com/chriopter/psp-dx-testapp-abandoned)** | apps · MIT | 1 |
| **[Extreme Tux Racer](https://github.com/chriopter/psp-tuxracer)** | games · GPL-2.0 | 0.21.0 |
| **[PSPDX Test App](https://github.com/chriopter/psp-dx-testapp)** | apps · MIT | 2 |
| **[Rust Raytracer](https://github.com/chriopter/psp-rust-raytracer)** | demos · MIT | 0.1.0 |

Maintained by hand for now; the versions come from the last scan.

## Getting in

- **To have an app listed** — open a pull request adding `apps/<id>/app.json`,
  or open an issue and ask. Open source licences only.
- **To have a release picked up now** rather than within the hour — open an
  issue titled `rescan: <repo url>`.

## How a release gets here

```
              hourly-scan  ·  every hour
                        |
                        v
               scan.py asks GitHub
                        |
            +-----------+-----------+
            |                       |
            v                       v
     304, unchanged          a newer release
            |                       |
            v                       v
          done        download · hash · look inside
                                    |
                                    v
                        scan.py commits the entry
                                    |
                                    |    a pull request, or you
                                    |    fixing a line by hand
                                    |              |
                                    +-------+------+
                                            |
                                            v
                          any commit runs build-catalog
                                            |
                                            v
              catalog.json  ·  shots/  ·  vids/  on Pages
```


`scan.py` reads releases, never repositories. It rewrites `release` and
`archive` and nothing else — name, summary, category and licence stay as a
person wrote them. Nothing is built unless something was committed.

## What a release has to look like

Nothing has to change in the author's project, but three things have to be
true of the release:

1. **One `.zip` attached.** More assets is fine, but then the entry has to say
   which one, with a glob in `archive.asset` — half of all releases carry more
   than one file. `.7z` and `.rar` cannot be opened.
2. **An `EBOOT.PBP` somewhere inside it.** `X/EBOOT.PBP`, at the root, or
   `PSP/GAME/X/EBOOT.PBP` all work: the shallowest one wins.
3. **Everything the app needs sits beside that EBOOT or below it.** Its
   directory *is* the package and goes onto the Memory Stick whole. Anything
   above it — `LICENSES/`, a README, a source tarball — is ignored and can
   stay in the zip.

No manifest, no naming convention, no signature. The title in the XMB comes
from the `PARAM.SFO` inside the EBOOT, which the toolchain already writes.

Two ways to get it wrong: two EBOOTs at the same depth make the choice a coin
toss — one zip is one package — and an archive that moves its package between
releases is refused rather than published, with an issue instead.

## An app bundle

One directory per app, named exactly after the `id` inside it. Here is
[a whole one](apps/io.github.chriopter.rustraytracer).

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

No binaries live here. Those stay in their authors' releases.
