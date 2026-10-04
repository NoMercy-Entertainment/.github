"""Bring the org project board in line with docs/project-board.md.

Reads the Fields table from the doc (the only source of truth), compares each
single-select field on the project with it, and rewrites the options of any
field that differs. Values already set on items are carried over to the
renamed option, so no item loses its Status or Phase; an old option the doc
does not name stays on the field while items use it, and the run reports it.
Also puts every open issue of every unarchived repo in the org on the board
(a repo whose issues are disabled is skipped with a note; plus any listed with
--add), and creates every view in the doc's Views table that the
board does not have yet (views are never edited or deleted). Project
workflows have no public API and are not touched.

Usage: GH_TOKEN=... python setup_project.py ORG PROJECT_NUMBER [--dry-run]
       [--add owner/repo#number ...]
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com/graphql"
REST = "https://api.github.com"
# The Projects REST API (fields and views) needs this version header.
REST_VERSION = "2026-03-10"
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


def read_doc_views(path=DOC):
    """Return the doc's Views table as [{name, layout, filter, arrange}]."""
    text = path.read_text(encoding="utf-8")
    section = text.split("## Views", 1)[1].split("\n## ", 1)[0]
    views = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in ("View", "") or cells[0].startswith(":"):
            continue
        name, layout, filter_, arrange = cells
        views.append(
            {
                "name": name,
                "layout": layout.lower(),
                "filter": filter_.strip("`"),
                "arrange": arrange,
            }
        )
    return views


def parse_arrangement(text):
    """'Columns by Status' -> ('columns', 'Status'); also 'Group by' and 'Sort by'."""
    match = re.fullmatch(r"(Columns|Group|Sort) by (.+)", text.strip())
    if not match:
        raise ValueError(f"unknown arrangement in the doc: {text!r}")
    return match.group(1).lower(), match.group(2).strip()


def view_payload(view, field_ids):
    """The REST body that creates the view, plus notes on anything the doc
    asks for that the board cannot do. field_ids maps a lower-case field name
    to its integer id."""
    body = {"name": view["name"], "layout": view["layout"], "filter": view["filter"]}
    kind, field = parse_arrangement(view["arrange"])
    field_id = field_ids.get(field.lower())
    if field_id is None:
        return body, [f"{view['name']}: no field named {field!r} on the board, {kind} not applied"]
    if kind == "columns":
        body["vertical_group_by"] = [field_id]
    elif kind == "group":
        body["group_by"] = [field_id]
    else:
        body["sort_by"] = [[field_id, "asc"]]
    return body, []


def map_option(old_name, new_names):
    """The new option an old option's values move to, or None."""
    old = ALIASES.get(old_name.lower(), old_name.lower())
    for new in new_names:
        low = new.lower()
        if low == old or low.startswith(old + " "):
            return new
    return None


def plan_field(field, wanted, used_option_ids=()):
    """Return (options input, {old option id: new name}, kept) or None if the
    field already matches the doc exactly, in order. An old option the doc does
    not name is dropped only when no item uses it (used_option_ids); otherwise
    it is kept after the doc's options, listed in kept, so no item loses its
    value. The run reports kept options; the doc or the board must be fixed by
    hand."""
    current = [o["name"] for o in field["options"]]
    if current == wanted:
        return None
    by_new = {}
    moves = {}
    kept = []
    for opt in field["options"]:
        target = map_option(opt["name"], wanted)
        if target is None and opt["id"] in used_option_ids:
            target = opt["name"]
            kept.append(target)
        if target:
            moves[opt["id"]] = target
            by_new.setdefault(target, opt)
    options = []
    for name in list(wanted) + kept:
        old = by_new.get(name)
        options.append(
            {
                "name": name,
                "color": old["color"] if old else "GRAY",
                "description": (old.get("description") or "") if old else "",
            }
        )
    return options, moves, kept


def gql(token, query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"]))
    return payload["data"]


def rest(token, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(REST + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", REST_VERSION)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        if headers is not None:
            headers.update(resp.headers)
        return json.loads(resp.read())


def rest_pages(token, path):
    """Every item of a paginated list endpoint."""
    items = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        batch = rest(token, "GET", f"{path}{sep}per_page=100&page={page}")
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


def open_issue_refs(repos, issues_of, report=print):
    """owner/repo#number for every open issue (not pull request) of every
    unarchived repo. issues_of(full_name) returns the repo's open issues. A
    repo whose issues cannot be listed (410 when issues are disabled) is
    skipped with a note through report."""
    refs = []
    for repo in repos:
        if repo.get("archived"):
            continue
        try:
            issues = issues_of(repo["full_name"])
        except urllib.error.HTTPError as err:
            report(f"{repo['full_name']}: issues not listed ({err.code} {err.reason}), skipped")
            continue
        for issue in issues:
            if "pull_request" in issue:
                continue
            refs.append(f"{repo['full_name']}#{issue['number']}")
    return refs


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

VIEWS = """query($org:String!,$num:Int!){organization(login:$org){projectV2(number:$num){
views(first:50){nodes{number name layout filter
groupByFields(first:5){nodes{... on ProjectV2FieldCommon{name}}}
sortByFields(first:5){nodes{direction field{... on ProjectV2FieldCommon{name}}}}}}}}}"""

ADD_ITEM = """mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}"""


def load_items(token, project_id):
    items, cursor = [], None
    while True:
        page = gql(token, ITEMS, id=project_id, cursor=cursor)["node"]["items"]
        items.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return items
        cursor = page["pageInfo"]["endCursor"]


def load_views(token, org, number):
    return gql(token, VIEWS, org=org, num=number)["organization"]["projectV2"]["views"]["nodes"]


def describe_view(view):
    groups = [f["name"] for f in view["groupByFields"]["nodes"] if f]
    sorts = [f"{s['field']['name']} {s['direction']}" for s in view["sortByFields"]["nodes"] if s]
    return f"{view['name']}: {view['layout']} filter={view['filter']!r} group={groups} sort={sorts}"


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
        used = {
            value["optionId"]
            for item in items
            for value in item["fieldValues"]["nodes"]
            if value and value.get("field", {}).get("id") == field["id"]
        }
        plan = plan_field(field, options, used)
        if plan is None:
            print(f"{name}: matches the doc")
            continue
        new_options, moves, kept = plan
        print(f"{name}: {[o['name'] for o in field['options']]} -> {[o['name'] for o in new_options]}{tag}")
        for extra in kept:
            print(f"  KEPT {extra!r}: not in the doc but items use it; add it to the doc or move the items")
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
    repos = rest_pages(token, f"/orgs/{args.org}/repos?type=all")
    wanted_refs = open_issue_refs(
        repos,
        lambda name: rest_pages(token, f"/repos/{name}/issues?state=open"),
        report=lambda note: print(note, file=sys.stderr),
    )
    print(f"Open issues in {len(repos)} repos: {len(wanted_refs)}")
    for ref in list(args.add) + [r for r in wanted_refs if r not in args.add]:
        repo, number = ref.split("#")
        if ref in on_board:
            continue
        print(f"{ref}: add{tag}")
        if args.dry_run:
            continue
        owner, name = repo.split("/")
        issue = gql(token, ISSUE_ID, o=owner, r=name, n=int(number))["repository"]["issue"]
        gql(token, ADD_ITEM, p=project_id, c=issue["id"])

    existing = {v["name"] for v in load_views(token, args.org, args.number)}
    rest_fields = rest(token, "GET", f"/orgs/{args.org}/projectsV2/{args.number}/fields")
    field_ids = {f["name"].lower(): f["id"] for f in rest_fields}
    for view in read_doc_views():
        if view["name"] in existing:
            print(f"View {view['name']}: exists")
            continue
        body, notes = view_payload(view, field_ids)
        for note in notes:
            print(f"  NOT POSSIBLE {note}")
        print(f"View {view['name']}: create {json.dumps(body)}{tag}")
        if args.dry_run:
            continue
        rest(token, "POST", f"/orgs/{args.org}/projectsV2/{args.number}/views", body)

    if not args.dry_run:
        after = gql(token, PROJECT, org=args.org, num=args.number)["organization"]["projectV2"]
        print("Read back:")
        for f in after["fields"]["nodes"]:
            if f and f["name"] in wanted:
                names = [o["name"] for o in f["options"]]
                ok = "OK" if names == wanted[f["name"]] else "DIFFERS"
                print(f"  {f['name']}: {names} {ok}")
        print(f"  Items on board: {len(load_items(token, project_id))}")
        for view in load_views(token, args.org, args.number):
            print(f"  View {describe_view(view)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
