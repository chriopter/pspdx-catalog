# PSPDX catalog

The list of PSP homebrew [PSPDX](https://github.com/chriopter/pspdx) shows
on the console, and the hourly job that turns it into a catalog:

https://chriopter.github.io/pspdx-catalog/

## What makes an app appear here

Two things, both in the app's own repository:

- A `.pspdx` in its root
- A release with an EBOOT that carries the XMB media

Then one line in [`repos.txt`](repos.txt). Nothing about the app is written
here; [pspdx-demo](https://github.com/chriopter/pspdx-demo) is the whole of
it in a hello world.

```
https://github.com/chriopter/pspdx-demo        # a repository a line
https://github.com/someone/psp-thing@v1.2      # @tag freezes it at one release
```

## Every file here

| | |
|---|---|
| [`repos.txt`](repos.txt) | The list. One GitHub repository a line, `@tag` to freeze one at a release. The only file a person edits. |
| [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) | Runs once an hour, on a push and on request. Calls `look.py`, deploys the site to GitHub Pages when it reports a change, and goes red afterwards if an app was left out. |
| [`.github/look.py`](.github/look.py) | Reads every repository on the list: its `.pspdx`, checked against the format, and its latest release from GitHub. Downloads the one zip, hashes it, finds the one `EBOOT.PBP`, reads its `PARAM.SFO`, and takes the icon, the picture, the film and the sound out of it. Writes the whole site, and says whether anything moved since the last run. |
| [`.github/page.py`](.github/page.py) | Turns that into the page: a card an app with its pictures, version and links, and at the bottom the apps that were left out with the reason. |

## Every file on the site

Built every time, committed never.

| | |
|---|---|
| `catalog.json` | What the console fetches, in one request: every app with its name, author, summary, category, licence and install directory, and its release with version, date, URL, size and sha256. |
| `icons/ shots/ vids/ snd/` | The four things out of each EBOOT, under names that carry their own bytes, so a changed picture arrives under a new name and an old one is never asked for again. |
| `state.json` | What the last run saw: each repository's latest release, and the hash of the list and of the code. The next run compares against it and publishes nothing when it matches, which is most hours. The only memory this repository keeps, and it lives on the site rather than in git. |
| `index.html` | The page, for whoever has no PSP in their hands. |
