# Contributing to NoMercy

Thanks for helping. This file is the default for every repository in the
organisation. A repository with its own `CONTRIBUTING.md` (for example the media
server) has the build steps and branch rules for that code, so read that one
first.

## Before you start

- **Bug?** Open an issue with the Bug report form in the repository where it
  happens. If you are not sure which one, use the media server.
- **Idea?** Open a Feature request. Big changes get agreed on the issue before
  code, so nobody's work is wasted.
- **Question?** Ask on [Discord](https://discord.com/invite/u3A3KXd2Hd).
- **Security problem?** Follow [SECURITY.md](SECURITY.md). Never a public issue.

## How work is tracked

All issues and pull requests in the organisation land on one project board.
New items start in **Inbox** with the `needs-triage` label, and are given a
priority, area and release at the weekly triage.

A feature that touches several repositories is one **epic** issue with a
**sub-issue** in each repository that has to change. The epic closes only when
every sub-issue is done, so a feature reaches every client.

## Pull requests

- Branch from the repository's default branch (`dev` for the media server,
  `master` elsewhere).
- Use a conventional commit title: `type(scope): description`.
- Fill in the pull request template: Before, After, How, and your proof.
- Add or update a test that fails without your change.
- Keep one change per pull request.

## Licences

The player libraries are open source. The media server is source-available,
not open source: read its `LICENSE` before contributing. By opening a pull
request you agree your contribution is licensed under the licence of that
repository.
