#!/usr/bin/env python3
"""Asks every repository on the list what its latest release is, writes the
answer as the site, and says whether it differs from the answer already
published.

There is no state in this repository. The published `state.json` is what the
last run saw, so the comparison is against the live site, and a run that
finds nothing new publishes nothing. Reading what the apps say about
themselves comes later; this only watches for movement."""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("GITHUB_TOKEN")
LIVE = os.environ.get("LIVE", "")


def get(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "pspdx-catalog",
        "Accept": "application/vnd.github+json",
        **({"Authorization": "Bearer " + TOKEN} if TOKEN else {}),
    })
    with urllib.request.urlopen(request, timeout=30) as answer:
        return json.load(answer)


def repos(path):
    """A line is a GitHub URL, and `@tag` after it pins a release."""
    for line in open(path, encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        url, _, tag = line.partition("@")
        yield url.rstrip("/"), tag


def release(slug, tag):
    """The tag and the date GitHub published it, or nothing at all. A draft
    or a pre-release is not an answer: `releases/latest` skips both."""
    path = f"releases/tags/{tag}" if tag else "releases/latest"
    try:
        answer = get(f"https://api.github.com/repos/{slug}/{path}")
    except urllib.error.HTTPError:
        return {"tag": None, "published": None}
    return {"tag": answer.get("tag_name"), "published": answer.get("published_at")}


def main():
    state = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "repos": {}}
    listed = []
    for url, tag in repos(os.path.join(HERE, "repos.txt")):
        slug = url.replace("https://github.com/", "")
        state["repos"][slug] = release(slug, tag)
        listed.append((url, slug, state["repos"][slug]))
        print(f"{slug}: {state['repos'][slug]['tag'] or 'no release'}")

    site = os.path.join(HERE, "site")
    os.makedirs(site, exist_ok=True)
    with open(os.path.join(site, "state.json"), "w", encoding="utf-8") as out:
        json.dump(state, out, indent=2)
        out.write("\n")

    rows = "\n".join(
        f'    <li><a href="{url}">{slug}</a> {found["tag"] or "no release"}</li>'
        for url, slug, found in listed)
    with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as out:
        out.write(f"""<!doctype html>
<meta charset="utf-8">
<title>PSPDX catalog</title>
<h1>PSPDX catalog</h1>
<p>The list PSPDX reads. Every repository says what it is in the
<code>.pspdx</code> in its own root.</p>
<ul>
{rows}
</ul>
<p>Looked at {state["generated"]}.</p>
""")

    # The one thing that decides whether anything is published: what is on
    # the site now, minus the time it says it was made.
    changed = "yes"
    try:
        with urllib.request.urlopen(LIVE, timeout=30) as answer:
            live = json.load(answer)
        if live.get("repos") == state["repos"]:
            changed = "no"
    except Exception:
        pass
    print("changed:", changed)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        out.write(f"changed={changed}\n")


if __name__ == "__main__":
    sys.exit(main())
