"""Fetch all packages from UpliftGames/wally-index with their last update dates."""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "UpliftGames/wally-index"
API_BASE = f"https://api.github.com/repos/{REPO}"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = ROOT / "data" / "registry.json"

MSG_PATTERN = re.compile(r"^Publish (\S+/\S+)@")


def get_token() -> str | None:
    token = os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        )
        token = result.stdout.strip()
        if token:
            return token
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "wally.ltrx.lol",
    }
    tok = get_token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def api_get(path: str) -> dict | list:
    url = f"{API_BASE}/{path}"
    req = Request(url, headers=headers())
    with urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    last_sha: str | None = None
    if OUTPUT.exists():
        existing = json.loads(OUTPUT.read_text("utf-8"))
        last_sha = existing.pop("__last_commit_sha", None)

    t0 = time.time()
    packages: dict[str, str] = {}
    newest_sha: str | None = None

    page = 1
    while True:
        resp = api_get(f"commits?per_page=100&page={page}&sha=main")
        if not isinstance(resp, list) or not resp:
            break

        stop = False
        for c in resp:
            sha = c["sha"]
            date = c["commit"]["committer"]["date"]
            if newest_sha is None:
                newest_sha = sha

            m = MSG_PATTERN.match(c["commit"]["message"])
            if m:
                pkg = m.group(1)
                if pkg not in packages:
                    packages[pkg] = date

            if last_sha and sha == last_sha:
                stop = True
                break

        if stop:
            break
        page += 1
        time.sleep(0.05)

    packages.update({k: v for k, v in existing.items() if k not in packages})

    if newest_sha:
        packages["__last_commit_sha"] = newest_sha

    packages = dict(sorted(packages.items()))

    OUTPUT.write_text(
        json.dumps(packages, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    print(f"Done, {len(packages) - 1} packages ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
