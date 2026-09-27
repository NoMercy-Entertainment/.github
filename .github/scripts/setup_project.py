"""Bring the org project board in line with docs/project-board.md.

Reads the Fields table from the doc (the only source of truth), compares each
single-select field on the project with it, and rewrites the options of any
field that differs. Values already set on items are carried over to the
renamed option, so no item loses its Status or Phase. Also adds the listed
issues to the board. Views and project workflows have no public API and are
not touched.

Usage: GH_TOKEN=... python setup_project.py ORG PROJECT_NUMBER [--dry-run]
       [--add owner/repo#number ...]
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com/graphql"
DOC = Path(__file__).resolve().parents[2] / "docs" / "project-board.md"

# GitHub's default Status option "Todo" means not started, which the doc calls
# Inbox. Every other old option maps by name (see map_option).
ALIASES = {"todo": "inbox"}


def read_doc_fields(path=DOC):
    """Return {field name: [option names]} from the doc's Fields table."""
    text = path.read_text(encoding="utf-8")
    section = text.split("## Fields", 1)[1].split("\n## ", 1)[0]
    fields = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[1] != "Single select":
            continue
        name, _, values = cells
        values = re.sub(r"\s*\(.*\)\s*$", "", values)
        options = [v.strip() for v in values.split(",")]
        if name == "Priority":
            # "P0 blocks release" is the option P0 plus its meaning.
            options = [o.split()[0] for o in options]
        fields[name] = options
    return fields


def map_option(old_name, new_names):
    """The new option an old option's values move to, or None."""
    old = ALIASES.get(old_name.lower(), old_name.lower())
    for new in new_names:
        low = new.lower()
        if low == old or low.startswith(old + " "):
            return new
    return None


def plan_field(field, wanted):
    """Return (options input, {old option id: new name}) or None if the field
    already matches the doc exactly, in order."""
    current = [o["name"] for o in field["options"]]
    if current == wanted:
        return None
    by_new = {}
    moves = {}
    for opt in field["options"]:
        target = map_option(opt["name"], wanted)
        if target:
            moves[opt["id"]] = target
            by_new.setdefault(target, opt)
    options = []
    for name in wanted:
        old = by_new.get(name)
        options.append(
            {
                "name": name,
                "color": old["color"] if old else "GRAY",
                "description": (old.get("description") or "") if old else "",
            }
        )
    return options, moves


def gql(token, query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"]))
    return payload["data"]


PROJECT = """query($org:String!,$num:Int!){organization(login:$org){projectV2(number:$num){
id title fields(first:50){nodes{... on ProjectV2SingleSelectField{id name
options{id name color description}}}}}}}"""

ITEMS = """query($id:ID!,$cursor:String){node(id:$id){... on ProjectV2{
items(first:100,after:$cursor){pageInfo{hasNextPage endCursor} nodes{id
content{... on Issue{number repository{nameWithOwner}}
... on PullRequest{number repository{nameWithOwner}}}
fieldValues(first:30){nodes{... on ProjectV2ItemFieldSingleSelectValue{optionId
field{... on ProjectV2SingleSelectField{id}}}}}}}}}}"""

UPDATE_FIELD = """mutation($f:ID!,$opts:[ProjectV2SingleSelectFieldOptionInput!]){
updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:$opts}){projectV2Field{
... on ProjectV2SingleSelectField{id options{id name}}}}}"""

SET_VALUE = """mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(
input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}"""

ISSUE_ID = """query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){issue(number:$n){id}}}"""

ADD_ITEM = """mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}"""


def load_items(token, project_id):
    items, cursor = [], None
    while True:
        page = gql(token, ITEMS, id=project_id, cursor=cursor)["node"]["items"]
        items.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return items
        cursor = page["pageInfo"]["endCursor"]


def item_label(item):
    c = item.get("content") or {}
    return f"{c.get('repository', {}).get('nameWithOwner', '?')}#{c.get('number', '?')}"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("org")
    parser.add_argument("number", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--add", nargs="*", default=[], help="owner/repo#number")
    args = parser.parse_args(argv)
    token = os.environ["GH_TOKEN"]
    tag = " (dry run)" if args.dry_run else ""

    wanted = read_doc_fields()
    project = gql(token, PROJECT, org=args.org, num=args.number)["organization"]["projectV2"]
    project_id = project["id"]
    print(f"Project: {project['title']} ({args.org} #{args.number})")
    fields = {f["name"]: f for f in project["fields"]["nodes"] if f}
    items = load_items(token, project_id)
    print(f"Items on board: {len(items)}")

    for name, options in wanted.items():
        field = fields.get(name)
        if field is None:
            print(f"{name}: MISSING on the board, not created (add it in the UI)")
            continue
        plan = plan_field(field, options)
        if plan is None:
            print(f"{name}: matches the doc")
            continue
        new_options, moves = plan
        print(f"{name}: {[o['name'] for o in field['options']]} -> {options}{tag}")
        carried = []
        for item in items:
            for value in item["fieldValues"]["nodes"]:
                if value and value.get("field", {}).get("id") == field["id"] and value["optionId"] in moves:
                    carried.append((item, moves[value["optionId"]]))
        for item, target in carried:
            print(f"  {item_label(item)}: keeps value as {target}{tag}")
        if args.dry_run:
            continue
        updated = gql(token, UPDATE_FIELD, f=field["id"], opts=new_options)
        new_ids = {o["name"]: o["id"] for o in updated["updateProjectV2Field"]["projectV2Field"]["options"]}
        for item, target in carried:
            gql(token, SET_VALUE, p=project_id, i=item["id"], f=field["id"], o=new_ids[target])

    on_board = {item_label(i) for i in items}
    for ref in args.add:
        repo, number = ref.split("#")
        if ref in on_board:
            print(f"{ref}: already on the board")
            continue
        print(f"{ref}: add{tag}")
        if args.dry_run:
            continue
        owner, name = repo.split("/")
        issue = gql(token, ISSUE_ID, o=owner, r=name, n=int(number))["repository"]["issue"]
        gql(token, ADD_ITEM, p=project_id, c=issue["id"])

    if not args.dry_run:
        after = gql(token, PROJECT, org=args.org, num=args.number)["organization"]["projectV2"]
        print("Read back:")
        for f in after["fields"]["nodes"]:
            if f and f["name"] in wanted:
                names = [o["name"] for o in f["options"]]
                ok = "OK" if names == wanted[f["name"]] else "DIFFERS"
                print(f"  {f['name']}: {names} {ok}")
        print(f"  Items on board: {len(load_items(token, project_id))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
