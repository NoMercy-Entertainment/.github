# The NoMercy project board

One GitHub Project for the whole organisation. Every issue and pull request in
every repository lands here, so what is being worked on, and what blocks v1, is
visible in one place.

## Work items

| Kind | Where it lives | Example |
|:--|:--|:--|
| Epic | An issue in this `.github` repo, type **Epic** | Stable release channel |
| Task | A sub-issue of the epic, in the repo that changes | Channel picker in the web app settings |
| Bug | An issue in the repo where it happens, type **Bug** | Seek freezes on Android TV |
| Feature | A user request, type **Feature**. Becomes an epic once agreed | Watch history importer |

An epic lists a sub-issue for every repository it touches. It closes only when
every sub-issue is closed, which is how "a feature ships to every client" is
kept.

Epics live here because this repo is public and belongs to no single
component. A sub-issue in a private repo shows its title only to people who can
see that repo.

## Fields

| Field | Type | Values |
|:--|:--|:--|
| Status | Single select | Inbox, Ready, In progress, In review, Done |
| Priority | Single select | P0 blocks release, P1 this train, P2 next, P3 someday |
| Area | Single select | server, web, kmp, cast, saas, players-web, players-kmp, infra, docs, labs |
| Release | Single select | v1.0-beta, v1.0, v1.1, v1.2, later |
| Size | Single select | S, M, L (an L is split before it moves to Ready) |
| Phase | Single select | P0 Foundations, P1 Stable + first run, P2 Private beta, P3 Hardening, P4 1.0, P5 After 1.0 |

Built-in fields used as they are: Assignees, Repository, Labels, Parent issue,
Sub-issues progress, Linked pull requests.

## Views

| View | Layout | Filter | Group or sort |
|:--|:--|:--|:--|
| Board | Board | `-status:Done` | Columns by Status |
| v1 blockers | Table | `release:v1.0-beta,v1.0 priority:P0,P1 -status:Done` | Group by Priority |
| Roadmap | Roadmap | `type:Epic` | Group by Phase |
| By area | Table | `-status:Done` | Group by Area |
| Bugs | Table | `type:Bug -status:Done` | Sort by Priority |
| Waiting on Stoney | Table | `label:decision -status:Done` | Sort by Priority |
| Inbox | Table | `status:Inbox` | Sort by created |

## Automation

Built-in project workflows (Project, then the `...` menu, then **Workflows**):

- **Item added to project:** set Status to Inbox.
- **Item closed:** set Status to Done.
- **Pull request merged:** set Status to Done.
- **Pull request linked to issue:** set Status to In review.
- **Auto-add to project:** add every new issue and pull request. One auto-add
  workflow watches one repository, and the number allowed depends on the plan
  (GitHub Free allows one). Point it at the busiest repo first. The
  `.github` repo's label sync already runs weekly across every repo, and an
  org-wide auto-add workflow can be added later if the plan limit bites.
- **Auto-archive items:** Done for more than 14 days.

## Triage rhythm

- **Monday:** empty the Inbox. Each item gets Priority, Area and Release, and
  loses `needs-triage`. Or it is closed with a reason.
- **Friday:** review the v1 blockers view before the beta promotion.
- **Monthly:** review Roadmap before the stable release.

## One-time setup (needs an org owner)

These need organisation owner rights, so they are done by hand once.

1. **Issue types.** Organisation **Settings**, then **Planning**, then
   **Issue types**. Keep Bug, Feature and Task. Add **Epic**.
2. **Board.** Organisation page, then **Projects**, then **New project**,
   template **Team planning** or blank **Board**. Name it `NoMercy`. Add the
   fields and views above, then turn on the workflows.
3. **Private vulnerability reporting.** Organisation **Settings**, then
   **Code security**, then **Private vulnerability reporting**: enable for all
   public repositories.
4. **Label sync.** After this PR merges, run the **Sync labels** workflow from
   the Actions tab with `dry_run` ticked, read the log, then run it again
   without. It uses the existing `PAT` secret, which needs the `repo` scope.
