# PSPDX Catalog

Browse PSP homebrew on the **[catalog website →](https://chriopter.github.io/pspdx-catalog/)**
or in [PSPDX](https://github.com/chriopter/pspdx) on your PSP.

At its core, this catalog is a [list of repositories](repos.txt). A GitHub
workflow reads each project's `.pspdx` and latest release, then publishes one
`catalog.json` with release details and EBOOT previews. The PSP can browse
and check many apps with one request; downloads still come from the authors.

## Make your own catalog

Fork this repository, put your chosen repositories in [`repos.txt`](repos.txt),
and set your name, Pages URL and repository URL in
[`catalog.config.json`](catalog.config.json). Enable GitHub Pages for the fork.
The workflow builds the site and updates it hourly. The `.pspdx` and catalog
schema URLs stay the same because they identify the shared formats.

## Add an app

Open an [issue](https://github.com/chriopter/pspdx-catalog/issues) with the
repository URL. The project needs a root `.pspdx` and a published release
containing exactly one ZIP with exactly one `EBOOT.PBP`. Drafts and
prereleases are skipped. [PSPDX Demo](https://github.com/chriopter/pspdx-demo)
shows a complete example.

## How it works

The hourly workflow checks each repository's latest release. If its version
and publication date are unchanged, the existing catalog entry is reused.
Otherwise, the builder reads `.pspdx`, downloads and hashes the ZIP, and
extracts any valid icon, picture, video and sound from its EBOOT. These media
files are optional.

The workflow deploys every hour, so `generated` in catalog.json is the time of the last successful look; PSPDX warns when it is a day old. A push to `master` or a
manual run checks everything again, including manifest-only edits. If no app
is valid, the live site stays up. The published `catalog.json` is also the
builder's record of the previous releases.

## Files

- [`repos.txt`](repos.txt) — one GitHub repository per line; `@tag` pins a release.
- [`catalog.config.json`](catalog.config.json) — catalog name and URLs.
- [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) — tests, builds and deploys.
- [`.github/look.py`](.github/look.py) — reads releases and builds the catalog.
- [`.github/page.py`](.github/page.py) — renders the website.

The generated site contains `catalog.json`, a readable `catalog.html`, an
`index.html` for browsing, and a page plus available EBOOT media for each app.
The JSON format is defined by the [catalog schema](https://github.com/chriopter/pspdx/blob/master/schema/catalog-v1.json).
