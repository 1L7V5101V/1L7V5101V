#!/usr/bin/env python3
"""Refresh the numbers between <!-- STATS:START --> and <!-- STATS:END --> in README.md.

Metrics (public data only, so nothing private ever leaks into the README):

  Stars   - total stargazers across your own (non-fork) public repos
  Repos   - how many own (non-fork) public repos you have
  Commits - commits authored by you in public repos (GitHub search API)

If a metric cannot be fetched (rate limit / API hiccup) the previous number
already present in README.md is kept, so the badges never regress to 0.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

README = pathlib.Path("README.md")
USER = os.environ.get("GITHUB_USER") or "1L7V5101V"
TOKEN = os.environ.get("GH_TOKEN", "")

START = "<!-- STATS:START -->"
END = "<!-- STATS:END -->"

NUM_PATTERNS = {
    "stars": r"Stars-(\d+)",
    "repos": r"Repos-(\d+)",
    "commits": r"Commits-(\d+)",
}


def api(path: str, **params):
    url = "https://api.github.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"{USER}-profile-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def public_own_repos() -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        chunk = api(f"/users/{USER}/repos", per_page=100, page=page, type="owner")
        repos += chunk
        if len(chunk) < 100:
            return repos
        page += 1


def previous_numbers(text: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for key, pattern in NUM_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            found[key] = int(match.group(1))
    return found


def main() -> None:
    text = README.read_text(encoding="utf-8")
    fallback = previous_numbers(text)

    try:
        own = [r for r in public_own_repos() if not r["fork"]]
        stars = sum(r["stargazers_count"] for r in own)
        repos = len(own)
    except Exception as exc:  # noqa: BLE001
        print(f"! repo stats failed ({exc}); keeping previous values")
        stars, repos = fallback.get("stars", 0), fallback.get("repos", 0)

    try:
        commits = api("/search/commits", q=f"author:{USER}", per_page=1)["total_count"]
    except Exception as exc:  # noqa: BLE001
        print(f"! commit stats failed ({exc}); keeping previous value")
        commits = fallback.get("commits", 0)

    block = (
        f"{START}\n"
        "<p>\n"
        f'  <img src="https://img.shields.io/badge/⭐%20Stars-{stars}-purple?style=for-the-badge&color=A855F7" alt="Stars" />\n'
        f'  <img src="https://img.shields.io/badge/📦%20Repos-{repos}-purple?style=for-the-badge&color=A855F7" alt="Repos" />\n'
        f'  <img src="https://img.shields.io/badge/📝%20Commits-{commits}-purple?style=for-the-badge&color=A855F7" alt="Commits" />\n'
        "</p>\n"
        f"{END}"
    )

    new, count = re.subn(
        re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S
    )
    if count != 1:
        raise SystemExit(f"expected exactly one STATS block in README.md, found {count}")

    print(f"Stars={stars} Repos={repos} Commits={commits}")
    if new != text:
        README.write_text(new, encoding="utf-8")
        print("README.md updated")
    else:
        print("README.md already up to date")


if __name__ == "__main__":
    main()
