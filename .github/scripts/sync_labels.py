"""Apply .github/labels.yml to every repository in the organisation.

Creates missing labels and updates the colour and description of existing
ones. Never deletes or renames a label. Archived repositories are skipped.

Usage: GH_TOKEN=... python sync_labels.py ORG [--dry-run] [--repo NAME]
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

API = "https://api.github.com"
LABELS_FILE = Path(__file__).resolve().parent.parent / "labels.yml"


def load_labels(path=LABELS_FILE):
    labels = yaml.safe_load(path.read_text(encoding="utf-8"))
    seen = set()
    for label in labels:
        key = label["name"].lower()
        if key in seen:
            raise ValueError(f"duplicate label {label['name']}")
        seen.add(key)
        if len(label.get("description", "")) > 100:
            raise ValueError(f"description over 100 characters: {label['name']}")
        color = label["color"]
        if not isinstance(color, str) or not re.fullmatch(r"#?[0-9a-fA-F]{6}", color):
            raise ValueError(f"color must be a quoted 6-digit hex string: {label['name']}")
        label["color"] = color.lstrip("#").lower()
    return labels


def plan(wanted, existing):
    """Return (to_create, to_update) for one repo. Matching is case-insensitive,
    as GitHub's is. Labels only present in the repo are left alone."""
    current = {label["name"].lower(): label for label in existing}
    to_create, to_update = [], []
    for label in wanted:
        have = current.get(label["name"].lower())
        if have is None:
            to_create.append(label)
        elif (
            have["color"].lower() != label["color"]
            or (have.get("description") or "") != label.get("description", "")
        ):
            to_update.append((have["name"], label))
    return to_create, to_update


def request(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req) as resp:
        payload = resp.read()
        link = resp.headers.get("Link", "")
    return (json.loads(payload) if payload else None), link


def paginate(url, token):
    items = []
    while url:
        page, link = request("GET", url, token)
        items.extend(page)
        url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part[part.index("<") + 1 : part.index(">")]
    return items


def sync_repo(org, repo, wanted, token, dry_run):
    base = f"{API}/repos/{org}/{repo}/labels"
    existing = paginate(f"{base}?per_page=100", token)
    to_create, to_update = plan(wanted, existing)
    for label in to_create:
        print(f"{repo}: create {label['name']}")
        if not dry_run:
            request("POST", base, token, label)
    for old_name, label in to_update:
        print(f"{repo}: update {old_name}")
        if not dry_run:
            url = f"{base}/{urllib.parse.quote(old_name, safe='')}"
            request("PATCH", url, token, {"new_name": old_name, **{k: label[k] for k in ("color", "description")}})
    return len(to_create) + len(to_update)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("org")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", help="sync only this repository")
    args = parser.parse_args(argv)

    token = os.environ["GH_TOKEN"]
    wanted = load_labels()
    if args.repo:
        repos = [args.repo]
    else:
        repos = [
            r["name"]
            for r in paginate(f"{API}/orgs/{args.org}/repos?per_page=100&type=all", token)
            if not r["archived"]
        ]

    failed = []
    changes = 0
    for repo in sorted(repos):
        try:
            changes += sync_repo(args.org, repo, wanted, token, args.dry_run)
        except urllib.error.HTTPError as err:
            print(f"{repo}: FAILED {err.code} {err.reason}", file=sys.stderr)
            failed.append(repo)

    print(f"{len(repos)} repos, {changes} label changes{' (dry run)' if args.dry_run else ''}")
    if failed:
        print(f"failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
