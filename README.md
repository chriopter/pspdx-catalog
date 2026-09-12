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

## What runs, and when

Every hour, on a push and on request,
[`deploy.yml`](.github/workflows/deploy.yml) runs
[`look.py`](.github/look.py), which for every repository on the list reads
the `.pspdx`, asks GitHub for the repository and its latest release,
downloads the one zip, hashes it, finds the one `EBOOT.PBP` and takes the
icon, the picture, the film and the sound out of it. Out of that comes
`catalog.json`, the pictures beside it, and the page,
[`page.py`](.github/page.py).

It deploys only when something moved: `state.json` on the site is what the
last run saw, and a run that finds the same releases, the same list and the
same code publishes nothing. An app that cannot be listed is left out with
the reason, at the bottom of the page and in the log, and the run goes red
afterwards, so a failure is visible without keeping the others off the site.

## Every file here

| | |
|---|---|
| [`repos.txt`](repos.txt) | The list. The only file a person edits. |
| [`.github/look.py`](.github/look.py) | Reads the repositories and writes the site. |
| [`.github/page.py`](.github/page.py) | The page: a card an app, and what was left out. |
| [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) | Runs it hourly and deploys to GitHub Pages. |
| [`.gitignore`](.gitignore) | `site/` and `__pycache__/`, both built, neither committed. |

And on the site, none of it committed here:

| | |
|---|---|
| `catalog.json` | What the console fetches: every app, and its release with version, date, URL, size and sha256. |
| `icons/ shots/ vids/ snd/` | The four things out of each EBOOT, under names that carry their own bytes. |
| `state.json` | What the last run saw. The only memory this repository keeps, and it lives on the site. |
| `index.html` | The page. |
