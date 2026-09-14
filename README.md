# PSPDX Catalog

Browse PSP homebrew on the **[catalog website →](https://chriopter.github.io/pspdx-catalog/)**
or in [PSPDX](https://github.com/chriopter/pspdx) on your PSP.

## How it works

- **A list.** [`repos.txt`](repos.txt) holds one GitHub repository per line.
  It's just like a phonebook.
- **A builder.** Every hour a GitHub workflow reads each repo's `.pspdx` and
  its newest releases, up to 20 → hashes the ZIPs → extracts artwork from the
  EBOOT → publishes `catalog.json`.
- **Fast on the PSP.** One request lists every app. Downloads still come from
  the authors.

## Add an app

- Open an [issue](https://github.com/chriopter/pspdx-catalog/issues) with the
  repository URL.
- The repo needs a root `.pspdx` and a release with one ZIP holding one
  `EBOOT.PBP`. [PSPDX Demo](https://github.com/chriopter/pspdx-demo) is a
  complete example.
- Drafts and prereleases are skipped.

<details>
<summary><b>The .pspdx</b> · fields, tags, repos without one</summary>

- **Required** → `schema`, `source` (the repo URL) and `name`, up to 40 characters
- **`tags`** → up to 8 words, each up to 24 characters; `game`, `emulator`,
  `app` and `demo` get a tab on the PSP
- **`installdir`** → only if the folder isn't the repo name; the default is
  `PSP/GAME/<repo name>`
- **`summary`, `author`, `license`** → up to 60 characters each; left out,
  GitHub's description, owner and license fill in
- **`description`** → plain text, up to 2500 characters, newlines allowed;
  shown on the app's page
- **`type`** → `homebrew` by default; this catalog lists only homebrew
- **`listed_by`** → the home page of a list that vouches for the app; shown
  on the app's page as "Listed by"
- **No `.pspdx` in the repo?** The format lets a list serve one and set
  `listed_by`. This catalog lists GitHub repos only and serves no `.pspdx`
  of its own, so the repo needs its own file.

All rules: [the PSPDX standard](https://github.com/chriopter/pspdx#the-pspdx-standard).

</details>

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

- **Hourly, newest release unchanged** → same tag and `published_at` → reuse
  the entry
- **Hourly, new release** → read `.pspdx` → download and hash every ZIP not
  hashed before → extract icon, picture, video and sound
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
| `apps/<id>/` | One page per app (summary, description, screenshots, latest release, where each value came from) and its EBOOT media |

</details>
