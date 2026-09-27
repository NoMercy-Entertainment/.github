"""Create epics and their sub-issues from a seed file and put them on the board.

The seed file (see .github/seed/) lists epics. An epic with a "number" already
exists in the .github repo; one without is created there with the Epic type.
Each of its issues is created in its own repo with its type and labels, linked
as a sub-issue of the epic, added to the org board, and given the Area, Phase
and Release it lists (or its epic's). An issue or epic whose title is already
open in its repo is reused, never created twice, so a rerun is safe.

Usage: GH_TOKEN=... python seed_board.py SEED_FILE [--dry-run]
"""

import argparse
import json
import os
import sys
import time
import urllib.error

import setup_project
from setup_project import rest_pages

EPIC_REPO = ".github"
BOARD_FIELDS = ("area", "phase", "release")

PROJECT_FIELDS = """query($org:String!,$num:Int!){organization(login:$org){projectV2(number:$num){
id fields(first:50){nodes{... on ProjectV2SingleSelectField{id name options{id name}}}}}}}"""

ADD_ITEM = """mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}"""

SET_VALUE = """mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(
input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}"""


PAUSE = 1.0  # seconds after each write, to stay under GitHub's write rate limits
MAX_WAITS = 30


def is_rate_limited(error):
    """True when GitHub refused a call because of a rate limit."""
    if isinstance(error, urllib.error.HTTPError):
        if error.code == 429:
            return True
        if error.code == 403:
            text = error.read().decode(errors="replace").lower()
            return "rate limit" in text
        return False
    return "rate_limited" in str(error).lower() or "rate limit" in str(error).lower()


def with_backoff(call, sleep=time.sleep):
    """Run call(), waiting and retrying while GitHub answers with a rate limit."""
    for attempt in range(MAX_WAITS):
        try:
            return call()
        except (urllib.error.HTTPError, RuntimeError) as error:
            if not is_rate_limited(error):
                raise
            wait = min(60 * (attempt + 1), 300)
            print(f"  rate limited, waiting {wait}s")
            sleep(wait)
    raise SystemExit("still rate limited after the maximum number of waits")


def rest(token, method, path, body=None):
    result = with_backoff(lambda: setup_project.rest(token, method, path, body))
    if method != "GET":
        time.sleep(PAUSE)
    return result


def gql(token, query, **variables):
    result = with_backoff(lambda: setup_project.gql(token, query, **variables))
    if query.lstrip().startswith("mutation"):
        time.sleep(PAUSE)
    return result


def plan(seed, open_titles):
    """Turn the seed into an ordered list of steps.

    open_titles(repo) returns {title: issue number} of the repo's open issues.
    Each step is a dict: {"kind": "epic"|"issue", "repo", "title", "exists":
    number or None, "epic": index of its epic step (issues only), "fields":
    {area, phase, release}, "type", "labels", "body"}.
    """
    steps = []
    for epic in seed["epics"]:
        epic_index = len(steps)
        epic_fields = {k: epic[k] for k in ("phase", "release") if k in epic}
        steps.append(
            {
                "kind": "epic",
                "repo": EPIC_REPO,
                "title": epic["title"],
                "exists": epic.get("number") or open_titles(EPIC_REPO).get(epic["title"]),
                "fields": epic_fields,
                "type": "Epic",
                "labels": epic.get("labels", []),
                "body": epic.get("body", ""),
            }
        )
        for issue in epic["issues"]:
            fields = dict(epic_fields)
            fields.update({k: issue[k] for k in BOARD_FIELDS if k in issue})
            steps.append(
                {
                    "kind": "issue",
                    "repo": issue["repo"],
                    "title": issue["title"],
                    "exists": open_titles(issue["repo"]).get(issue["title"]),
                    "epic": epic_index,
                    "fields": fields,
                    "type": issue["type"],
                    "labels": issue.get("labels", []),
                    "body": issue.get("body", ""),
                }
            )
    return steps


def issue_body(step, epic_ref):
    lines = [step["body"]] if step["body"] else []
    if epic_ref:
        lines.append(f"Part of {epic_ref}.")
    lines.append("Seeded from the 2026-09-27 work inventory.")
    return "\n\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("seed")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    token = os.environ["GH_TOKEN"]
    tag = " (dry run)" if args.dry_run else ""
    with open(args.seed, encoding="utf-8") as f:
        seed = json.load(f)
    org = seed["org"]

    cache = {}

    def open_titles(repo):
        if repo not in cache:
            issues = rest_pages(token, f"/repos/{org}/{repo}/issues?state=open")
            cache[repo] = {i["title"]: i["number"] for i in issues if "pull_request" not in i}
        return cache[repo]

    steps = plan(seed, open_titles)
    project = gql(token, PROJECT_FIELDS, org=org, num=seed["project"])["organization"]["projectV2"]
    fields = {f["name"].lower(): f for f in project["fields"]["nodes"] if f}
    for step in steps:
        for name, value in step["fields"].items():
            options = {o["name"]: o["id"] for o in fields[name]["options"]}
            if value not in options:
                raise SystemExit(f"{step['repo']}: {step['title']}: no {name} option {value!r} on the board")

    created = reused = 0
    numbers = {}
    for index, step in enumerate(steps):
        ref_repo = f"{org}/{step['repo']}"
        if step["exists"]:
            numbers[index] = step["exists"]
            reused += 1
            print(f"reuse {ref_repo}#{step['exists']} {step['title']}")
        else:
            epic_ref = None
            if step["kind"] == "issue":
                epic_number = numbers.get(step["epic"])
                epic_ref = f"{org}/{EPIC_REPO}#{epic_number}" if epic_number else "its epic"
            print(f"create {ref_repo} [{step['type']}] {step['title']} {step['fields']}{tag}")
            created += 1
            if args.dry_run:
                numbers[index] = None
                continue
            issue = rest(
                token,
                "POST",
                f"/repos/{ref_repo}/issues",
                {
                    "title": step["title"],
                    "body": issue_body(step, epic_ref),
                    "labels": step["labels"],
                    "type": step["type"],
                },
            )
            numbers[index] = issue["number"]
        if args.dry_run:
            continue
        number = numbers[index]
        issue = rest(token, "GET", f"/repos/{ref_repo}/issues/{number}")
        if step["kind"] == "issue":
            parent = numbers[step["epic"]]
            try:
                rest(
                    token,
                    "POST",
                    f"/repos/{org}/{EPIC_REPO}/issues/{parent}/sub_issues",
                    {"sub_issue_id": issue["id"]},
                )
            except urllib.error.HTTPError as error:  # already linked answers 422
                if error.code != 422:
                    raise
        item = gql(token, ADD_ITEM, p=project["id"], c=issue["node_id"])["addProjectV2ItemById"]["item"]
        for name, value in step["fields"].items():
            field = fields[name]
            option = {o["name"]: o["id"] for o in field["options"]}[value]
            gql(token, SET_VALUE, p=project["id"], i=item["id"], f=field["id"], o=option)

    print(f"Steps: {len(steps)}, created: {created}{tag}, reused: {reused}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
