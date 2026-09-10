# PSPDX catalog

The list of apps [PSPDX](https://github.com/chriopter/pspdx) shows on the PSP.
One file per app, served as one
[catalog.json](https://chriopter.github.io/pspdx-catalog/catalog.json).
Downloads come from your own GitHub release, not from here.

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

## App package format

One directory per app, named after the `id` in it —
[one of them](apps/io.github.chriopter.rustraytracer):

| | |
|---|---|
| [`app.json`](apps/io.github.chriopter.rustraytracer/app.json) | The entry. You write the top half. |
| `icon.png` | 144x80, out of the EBOOT. Optional. |
| [`screenshot.png`](apps/io.github.chriopter.rustraytracer/screenshot.png) | 480x272. Optional. |
| [`video.mp4`](apps/io.github.chriopter.rustraytracer/video.mp4) | Ten seconds, H.264 baseline. Optional. |

## Files

| | |
|---|---|
| [`scan.py`](scan.py) | Finds new releases, downloads, checks. |
| [`build.py`](build.py) | Builds `catalog.json`. |
| [`.github/workflows/`](.github/workflows) | Hourly, on request, and publishing. |
