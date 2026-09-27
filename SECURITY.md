# Security policy

This policy covers every repository in the NoMercy Entertainment organisation
that does not have its own `SECURITY.md`.

## Reporting a vulnerability

**Please do not open a public issue.**

Report it privately in either of these ways:

- **GitHub:** open the repository's **Security** tab and choose **Report a vulnerability**.
- **Email:** security@nomercy.tv

Please include:

- The affected component: media server, web app, Android app, Chromecast
  receiver, nomercy.tv, or a player library
- The version you tested
- Steps to reproduce, with a minimal proof of concept
- What an attacker could do with it

## What happens next

- We acknowledge your report within 48 hours.
- We send a status update within 7 days.
- We agree a fix and disclosure date with you, and credit you in the advisory
  unless you would rather stay anonymous.

## Supported versions

Security fixes go to the latest release of each component. Once the stable
release channel exists, the current stable release is supported as well.

## Scope

In scope: code in this organisation's repositories and the services at
nomercy.tv.

Out of scope: vulnerabilities in third-party dependencies (please report those
upstream, then tell us if NoMercy is affected), denial of service by volume,
and findings that need physical access to an unlocked device.
