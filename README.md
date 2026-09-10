# PSPDX catalog

This is the list of apps that [PSPDX](https://github.com/chriopter/pspdx) shows
on the PSP. One file per app, all of them served as a single
[catalog.json](https://chriopter.github.io/pspdx-catalog/catalog.json) that the
console downloads.

Downloads are not hosted here. Your app is downloaded from your own GitHub
release.

## Currently listed apps

| | | |
|---|---|---|
| **[Abandoned Test App](https://github.com/chriopter/psp-dx-testapp-abandoned)** | apps · MIT | 1 |
| **[Extreme Tux Racer](https://github.com/chriopter/psp-tuxracer)** | games · GPL-2.0 | 0.21.0 |
| **[PSPDX Test App](https://github.com/chriopter/psp-dx-testapp)** | apps · MIT | 2 |
| **[Rust Raytracer](https://github.com/chriopter/psp-rust-raytracer)** | demos · MIT | 0.1.0 |

This list is written by hand for now.

## How to get your app listed

Open a pull request that adds one file, `apps/<id>/app.json`:

```json
{
  "id": "io.github.<your-user>.<your-app>",
  "name": "Your App",
  "author": "<your-user>",
  "summary": "One line, short enough for a PSP screen.",
  "category": "games",
  "license": "MIT",
  "repo": "https://github.com/<your-user>/<your-repo>"
}
```

Or open an issue and ask, and someone will write it for you. The licence has
to be an open source one. You do not have to change anything in your own
project.

## How to release your app

Attach **one `.zip`** to a GitHub release. It has to contain an `EBOOT.PBP`.

- **Where the EBOOT sits does not matter.** `MyApp/EBOOT.PBP`, or straight in
  the root of the zip, or `PSP/GAME/MyApp/EBOOT.PBP` — all fine.
- **Put everything your app needs in the same folder as the EBOOT, or below
  it.** That folder is what ends up on the Memory Stick. A `LICENSE` or a
  `README` next to it is ignored and can stay.
- **Attaching more files than the zip is fine**, but then say which one is the
  app: add `"archive": { "asset": "*-psp.zip" }` to your entry.
- `.7z` and `.rar` cannot be read.

## How the catalog stays up to date

Every hour, a script asks GitHub whether any listed app has a newer release.
If one has, it downloads the zip, checks what is inside, and writes the new
version, URL and checksum into that app's file. The catalog is rebuilt a
minute later. **You do not have to tell us anything.**

Do not want to wait the hour? Open an issue titled `rescan: <your repo url>`.

If a new release moves the EBOOT somewhere else, the catalog is **not**
updated. An issue is opened instead, so that nobody downloads something that
will not install.

## Files in this repository

One directory per app, named after the `id` in it —
[here is one](apps/io.github.chriopter.rustraytracer):

| | |
|---|---|
| [`app.json`](apps/io.github.chriopter.rustraytracer/app.json) | The entry. You write the top half, `scan.py` writes the rest. |
| `icon.png` | 144x80, taken out of the EBOOT. Optional. |
| [`screenshot.png`](apps/io.github.chriopter.rustraytracer/screenshot.png) | 480x272. Optional. |
| [`video.mp4`](apps/io.github.chriopter.rustraytracer/video.mp4) | Ten seconds, H.264 baseline. Optional. |

And the scripts that keep it running:

| | |
|---|---|
| [`scan.py`](scan.py) | Looks for new releases, downloads them, checks them. |
| [`build.py`](build.py) | Turns every entry into one `catalog.json`. |
| [`hourly-scan.yml`](.github/workflows/hourly-scan.yml) | Runs the scan every hour. |
| [`trigger-scan.yml`](.github/workflows/trigger-scan.yml) | Runs it for one app when an issue asks. |
| [`build-catalog.yml`](.github/workflows/build-catalog.yml) | Publishes the catalog. |
