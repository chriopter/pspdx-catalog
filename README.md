# PSPDX catalog

The list of apps [PSPDX](https://github.com/chriopter/pspdx) shows on the PSP.
One file per app, served as one
[catalog.json](https://chriopter.github.io/pspdx-catalog/catalog.json).
Downloads come from your own GitHub release, not from here.

**[Browse what is listed →](https://chriopter.github.io/pspdx-catalog/)**

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

`category` is one of `games`, `emulators`, `apps`, `plugins`, `demos`. The
directory has to be named exactly like the `id`.

That is all you write. The version, URL and checksum land in a second file,
`latest.json`, which the scanner owns — no workflow here ever writes
`app.json`. A pull request that adds only `app.json` is correct: the entry
appears in the catalog after the next scan.

## Release your app

One `.zip` on a GitHub release, with an `EBOOT.PBP` anywhere inside it.
Everything the app needs goes in the EBOOT's folder or below: that folder is
what lands on the Memory Stick.

More than one file attached? Say which, in `app.json`: `"asset": "*-psp.zip"`.

## Auto refresh

So that the PSP can show you that an app has a new version, the catalog has to
know before the console asks. Nobody is going to tell it, so it goes and looks.

Checked hourly. A new release is downloaded, checked and entered on its own —
you tell us nothing. Faster: open an issue titled `rescan: <repo url>`.

Move the EBOOT somewhere else and the catalog stays put, with an issue, rather
than shipping something that will not install.

To freeze an entry where it is — a newer release that breaks the PSP build,
say — put `"scan": false` in its `app.json`.

## App package format

One directory per app, named after the `id` in it —
[one of them](apps/io.github.chriopter.rustraytracer):

| | |
|---|---|
| [`app.json`](apps/io.github.chriopter.rustraytracer/app.json) | Yours. Name, licence, repository. Never touched by automation. |
| [`latest.json`](apps/io.github.chriopter.rustraytracer/latest.json) | The scanner's. Version, URL, checksum. Never edited by hand. |
| `icon.png` | 144x80, out of the EBOOT. Optional. |
| [`screenshot.png`](apps/io.github.chriopter.rustraytracer/screenshot.png) | 480x272. Optional. |
| [`video.mp4`](apps/io.github.chriopter.rustraytracer/video.mp4) | Ten seconds, H.264 baseline. Optional. |

## Files

| | |
|---|---|
| [`scan.py`](scan.py) | Finds new releases, downloads, checks. |
| [`build.py`](build.py) | Builds `catalog.json`. |
| [`.github/workflows/`](.github/workflows) | Hourly, on request, and publishing. |
