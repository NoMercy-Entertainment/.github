import tempfile
import unittest
from pathlib import Path

from sync_labels import load_labels, plan


class PlanTest(unittest.TestCase):
    wanted = [
        {"name": "needs-triage", "color": "fbca04", "description": "New"},
        {"name": "bug", "color": "d73a4a", "description": "Broken"},
    ]

    def test_creates_missing_and_leaves_extra_labels(self):
        existing = [{"name": "wontfix", "color": "ffffff", "description": ""}]
        create, update = plan(self.wanted, existing)
        self.assertEqual([l["name"] for l in create], ["needs-triage", "bug"])
        self.assertEqual(update, [])

    def test_updates_case_insensitively_and_keeps_repo_spelling(self):
        existing = [{"name": "Bug", "color": "D73A4A", "description": "old"}]
        create, update = plan(self.wanted, existing)
        self.assertEqual([l["name"] for l in create], ["needs-triage"])
        self.assertEqual(update[0][0], "Bug")

    def test_no_change_when_identical(self):
        existing = [dict(l) for l in self.wanted]
        self.assertEqual(plan(self.wanted, existing), ([], []))

    def test_null_description_matches_empty(self):
        wanted = [{"name": "x", "color": "000000", "description": ""}]
        existing = [{"name": "x", "color": "000000", "description": None}]
        self.assertEqual(plan(wanted, existing), ([], []))

    def test_shipped_file_is_valid(self):
        labels = load_labels()
        self.assertTrue(all(len(l["color"]) == 6 for l in labels))

    def test_rejects_unquoted_numeric_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.yml"
            path.write_text("- name: x\n  color: 000000\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_labels(path)


if __name__ == "__main__":
    unittest.main()
