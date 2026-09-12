# PSPDX catalog

https://chriopter.github.io/pspdx-catalog/

Once an hour [`deploy.yml`](.github/workflows/deploy.yml) runs
[`look.py`](.github/look.py), which reads every repository in
[`repos.txt`](repos.txt): its `.pspdx`, checked by hand against
[the format](https://github.com/chriopter/pspdx/blob/master/schema/v1.pspdx),
its repository and its latest release from GitHub, and the zip on that
release, which it hashes and opens to find the one `EBOOT.PBP` and take the
icon, the picture, the film and the sound out of it. Out comes
`catalog.json`, which is what the console fetches, the pictures beside it,
and [the page](.github/page.py), which is the same catalog for whoever has
no PSP in their hands.

It deploys only when something moved: the published `state.json` is what the
last run saw, and a run that finds the same releases, the same list and the
same code again publishes nothing.

A repository that cannot be listed is left out with the reason, at the
bottom of the page and in the log, and the run goes red after the deploy, so
that the failure is visible without keeping anybody else off the site.

Adding an app is a line in `repos.txt`, and `@tag` after the URL pins it to
one release. Nothing about the app itself is written here: the repository
says what it is in the `.pspdx` in its own root.
