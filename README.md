# PSPDX Catalog

Browse PSP homebrew on the **[catalog website →](https://chriopter.github.io/pspdx-catalog/)**
or in [PSPDX](https://github.com/chriopter/pspdx) on your PSP.

## How it works

- **A list.** [`repos.txt`](repos.txt) holds one GitHub repository per line.
  It's just like a phonebook.
- **A builder.** Every hour a GitHub workflow reads each repo's `.pspdx` and
  latest release → hashes the ZIP → extracts artwork from the EBOOT →
  publishes `catalog.json`.
- **Fast on the PSP.** One request lists every app. Downloads still come from
  the authors.

## Add an app

- Open an [issue](https://github.com/chriopter/pspdx-catalog/issues) with the
  repository URL.
- The repo needs a root `.pspdx` and a release with one ZIP holding one
  `EBOOT.PBP`. [PSPDX Demo](https://github.com/chriopter/pspdx-demo) is a
  complete example.
- Drafts and prereleases are skipped.

## Make your own catalog

1. Fork this repository.
2. Put your repositories in [`repos.txt`](repos.txt).
3. Set name, Pages URL and repository URL in
   [`catalog.config.json`](catalog.config.json).
4. Enable GitHub Pages. Done! It updates every hour.

Keep the schema URLs as they are: they identify the shared formats.

<details>
<summary><b>Builder</b> · runs, reuse, failures</summary>

#### Runs

- **Hourly, release unchanged** → same tag and `published_at` → reuse the entry
- **Hourly, new release** → read `.pspdx` → download and hash the ZIP →
  extract icon, picture, video and sound
- **Push to `master` or manual run** → read everything again, including
  manifest-only edits

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
| [`catalog.config.json`](catalog.config.json) | Catalog name and URLs |
| [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) | Tests, builds and deploys |
| [`.github/look.py`](.github/look.py) | Reads releases and builds the catalog |
| [`.github/page.py`](.github/page.py) | Renders the website |

#### Site

| File | Purpose |
|---|---|
| `catalog.json` | Fast browsing; [catalog schema](https://chriopter.github.io/pspdx/schema/catalog-v1.json) |
| `catalog.txt` | Copy of `repos.txt`; PSPDX falls back to it and asks the repos directly |
| `index.html`, `catalog.html` | Browse page and readable catalog |
| `apps/<id>/` | One page and the EBOOT media per app |

</details>
