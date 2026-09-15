# PSPDX Catalog

An example catalog using the [PSPDX standard](https://chriopter.github.io/pspdx/),
rebuilt every hour.

Browse PSP homebrew on the **[catalog website →](https://chriopter.github.io/pspdx-catalog/)**
or in [PSPDX](https://github.com/chriopter/pspdx) on your PSP.

## Add your app

[Open an issue](https://github.com/chriopter/pspdx-catalog/issues) with your repository URL.
No `.pspdx` in the repository? It can be listed from a file in [`listed/`](listed/),
like [this example](listed/pspdx-demo-abandoned.pspdx).

## Make your own catalog

Fork this repository, list your repos in [`repos.txt`](repos.txt),
set [`catalog.config.json`](catalog.config.json), enable GitHub Pages.

<details>
<summary><b>Builder</b> · runs, reuse, failures</summary>

#### Runs

- **Hourly, newest release unchanged** → same tag and `published_at` → reuse
  the entry
- **Hourly, new release** → read `.pspdx` → download and hash every ZIP not
  hashed before → extract icon, picture, video and sound
- **Push to `master` or manual run** → read everything again, including
  manifest-only edits
- Drafts and prereleases are skipped, unless a `.pspdx` pins one with `release`.
- Keep the schema URLs as they are: they identify the shared formats.

#### Timestamp

- The site is published every hour, so `generated_at` is the last run.
- PSPDX warns when it is a day old.
- The published `catalog.json` is the builder's only memory.

#### Failures

- A broken app is left out, the run goes red, the rest stays on the site.
- A fresh timestamp does not guarantee every app was checked.
- No valid app at all → the live site stays as it is.

</details>

<details>
<summary><b>Files</b> · repository, site</summary>

#### Repository

| File | Purpose |
|---|---|
| [`repos.txt`](repos.txt) | One repository per line; `@tag` pins a release |
| [`listed/`](listed/) | A `.pspdx` for each repository without its own |
| [`catalog.config.json`](catalog.config.json) | Catalog name and URLs |
| [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) | Tests, builds and deploys |
| [`.github/look.py`](.github/look.py) | Reads releases and builds the catalog |
| [`.github/page.py`](.github/page.py) | Renders the website |

#### Site

| File | Purpose |
|---|---|
| `catalog.json` | Fast browsing; [catalog format](https://chriopter.github.io/pspdx/#catalog-v1) |
| `catalog.txt` | Copy of `repos.txt`; PSPDX falls back to it and asks the repos directly |
| `index.html`, `catalog.html` | Browse page and readable catalog |
| `apps/<id>/` | One page per app (summary, description, screenshots, latest release, where each value came from) and its EBOOT media |

</details>
