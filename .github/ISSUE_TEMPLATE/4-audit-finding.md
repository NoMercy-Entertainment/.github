---
name: Audit finding
about: One finding from the 100% audit, in 5W1H form. Filed from a findings/*.json file that passed finding-gate.mjs.
labels: source/audit, needs-triage
---
## Who
Who is hit: a new user on first install / a self-hosted admin / a beta household / a developer / a client (name it). Who owns the fix: repo + area.

## What
One sentence: what is wrong or missing. Then the observed behaviour and the expected behaviour.

## Where
Repo, file:line (integration branch commit), or the surface (web page, TV screen, API route, workflow name).

## When
When it happens: the trigger, the version or commit, the first time seen, how often.

## Why
Root cause as read in the code, or "not checked" if it is a hypothesis.

## How
How to reproduce (steps), and how to fix (the smallest proven change), and how to prove it (the test that must go red then green).

## Evidence
- `path/file.cs:123` on commit `abc1234` (branch dev): quoted line
- Command: `gh run view 123 --log` → quoted output

## Ports
Same fix needed in: kmp / cast / web / saas / none. (label `port/*` per line)

## Placement
Stage: S0..S6 / After 1.0. Goal: 1 Watch without help | 2 Security | 3 Stability | 4 Feature. Area: ... Size: S/M/L.

## Not checked
List every claim above you did not read or run.
