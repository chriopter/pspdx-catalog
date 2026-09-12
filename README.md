# PSPDX catalog

https://chriopter.github.io/pspdx-catalog/

Once an hour [`deploy.yml`](.github/workflows/deploy.yml) runs
[`look.py`](.github/look.py), which asks every repository in
[`repos.txt`](repos.txt) what its latest release is and publishes the
answer as the page above. It deploys only when something moved: the
published `state.json` is what the last run saw, and a run that finds the
same thing again publishes nothing.
