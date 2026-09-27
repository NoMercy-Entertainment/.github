import json
import unittest
from pathlib import Path

from seed_board import issue_body, plan, with_backoff

SEED = Path(__file__).resolve().parents[1] / "seed" / "2026-09-27-inventory.json"

AREAS = {"server", "web", "kmp", "cast", "saas", "players-web", "players-kmp", "infra", "docs", "labs"}
PHASES = {"P0 Foundations", "P1 Stable + first run", "P2 Private beta", "P3 Hardening", "P4 1.0", "P5 After 1.0"}
RELEASES = {"v1.0-beta", "v1.0", "v1.1", "v1.2", "later"}
LABELS = {"needs-triage", "needs-info", "decision", "blocked", "v1-gate", "breaking-change", "regression",
          "security", "documentation", "bug", "enhancement", "good first issue", "help wanted", "dependencies"}


class PlanTest(unittest.TestCase):
    seed = {
        "epics": [
            {"number": 6, "title": "[Epic] Old", "issues": [
                {"repo": "r", "title": "Done already", "type": "Task", "area": "server"},
                {"repo": "r", "title": "New", "type": "Bug", "area": "web", "phase": "P3 Hardening"},
            ]},
            {"title": "[Epic] New one", "phase": "P1 Stable + first run", "release": "v1.0", "issues": [
                {"repo": "s", "title": "Thing", "type": "Task", "area": "kmp"},
            ]},
        ]
    }

    def open_titles(self, repo):
        return {"r": {"Done already": 5}, ".github": {}, "s": {}}[repo]

    def test_existing_titles_are_reused_and_epics_come_first(self):
        steps = plan(self.seed, self.open_titles)
        self.assertEqual([s["kind"] for s in steps], ["epic", "issue", "issue", "epic", "issue"])
        self.assertEqual(steps[0]["exists"], 6)
        self.assertEqual(steps[1]["exists"], 5)
        self.assertIsNone(steps[2]["exists"])
        self.assertIsNone(steps[3]["exists"])
        self.assertEqual(steps[4]["epic"], 3)

    def test_issue_inherits_epic_fields_and_overrides_them(self):
        steps = plan(self.seed, self.open_titles)
        self.assertEqual(steps[2]["fields"], {"area": "web", "phase": "P3 Hardening"})
        self.assertEqual(steps[4]["fields"], {"phase": "P1 Stable + first run", "release": "v1.0", "area": "kmp"})

    def test_body_links_the_epic(self):
        step = {"body": "Slice A08."}
        self.assertEqual(issue_body(step, "o/.github#6"),
                         "Slice A08.\n\nPart of o/.github#6.\n\nSeeded from the 2026-09-27 work inventory.")


class BackoffTest(unittest.TestCase):
    def test_waits_on_a_rate_limit_then_returns(self):
        calls, waits = [], []

        def call():
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError('[{"type": "RATE_LIMITED"}]')
            return "ok"

        self.assertEqual(with_backoff(call, sleep=waits.append), "ok")
        self.assertEqual(waits, [60, 120])

    def test_other_errors_are_raised_at_once(self):
        def call():
            raise RuntimeError('[{"type": "NOT_FOUND"}]')

        with self.assertRaises(RuntimeError):
            with_backoff(call, sleep=lambda s: None)


class SeedFileTest(unittest.TestCase):
    def test_every_value_is_one_the_board_and_labels_have(self):
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        steps = plan(seed, lambda repo: {})
        for step in steps:
            f = step["fields"]
            self.assertIn(f.get("area", "server"), AREAS, step["title"])
            self.assertIn(f.get("phase"), PHASES, step["title"])
            self.assertIn(f.get("release", "later"), RELEASES, step["title"])
            self.assertTrue(set(step["labels"]) <= LABELS, step["title"])
            if step["kind"] == "issue":
                self.assertIn("area", f, step["title"])
                if f["phase"].startswith("P5"):
                    self.assertEqual(f.get("release"), "later", step["title"])
                if f["phase"][:2] in ("P3", "P4"):
                    self.assertNotEqual(f.get("release"), "v1.0-beta", step["title"])

    def test_no_title_twice_in_one_repo(self):
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        pairs = [(i["repo"], i["title"]) for e in seed["epics"] for i in e["issues"]]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_public_text_names_no_other_media_server(self):
        text = SEED.read_text(encoding="utf-8").lower()
        for name in ("plex", "jellyfin", "emby", "netflix"):
            self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
