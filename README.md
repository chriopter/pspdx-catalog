# PSPDX catalog

The list of apps [PSPDX](https://github.com/chriopter/pspdx) shows on the PSP.
One file per app, served as one
[catalog.json](https://chriopter.github.io/pspdx-catalog/catalog.json).
Downloads come from your own GitHub release, not from here.

## Listed

| | | |
|---|---|---|
| **[Abandoned Test App](https://github.com/chriopter/psp-dx-testapp-abandoned)** | apps · MIT | 1 |
| **[Extreme Tux Racer](https://github.com/chriopter/psp-tuxracer)** | games · GPL-2.0 | 0.21.0 |
| **[PSPDX Test App](https://github.com/chriopter/psp-dx-testapp)** | apps · MIT | 2 |
| **[Rust Raytracer](https://github.com/chriopter/psp-rust-raytracer)** | demos · MIT | 0.1.0 |

## Get listed

A pull request adding `apps/<id>/app.json`. Or open an issue and ask. Open
source licences only.

```json
{
  "id": "io.github.<user>.<app>",
  "name": "Your App",
  "author": "<user>",
  "summary": "One line, short enough for a PSP screen.",
  "category": "games",
  "license": "MIT",
  "repo": "https://github.com/<user>/<repo>"
}
```

That is all you write. `scan.py` fills in the version, URL and checksum.

## Release your app

One `.zip` on a GitHub release, with an `EBOOT.PBP` anywhere inside it.
Everything the app needs goes in the EBOOT's folder or below: that folder is
what lands on the Memory Stick.

More than one file attached? Say which: `"archive": { "asset": "*-psp.zip" }`.

## Staying current

Checked hourly. A new release is downloaded, checked and entered on its own —
you tell us nothing. Faster: open an issue titled `rescan: <repo url>`.

Move the EBOOT somewhere else and the catalog stays put, with an issue, rather
than shipping something that will not install.

## Files

| | |
|---|---|
| [`app.json`](apps/io.github.chriopter.rustraytracer/app.json) | The entry. You write the top half. |
| `icon.png` · [`screenshot.png`](apps/io.github.chriopter.rustraytracer/screenshot.png) · [`video.mp4`](apps/io.github.chriopter.rustraytracer/video.mp4) | 144x80, 480x272, ten seconds. All optional. |
| [`scan.py`](scan.py) | Finds new releases, downloads, checks. |
| [`build.py`](build.py) | Builds `catalog.json`. |
| [`.github/workflows/`](.github/workflows) | Hourly, on request, and publishing. |
