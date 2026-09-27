import unittest

from setup_project import map_option, plan_field, read_doc_fields


class DocTest(unittest.TestCase):
    def test_reads_every_field_from_the_doc(self):
        f = read_doc_fields()
        self.assertEqual(f["Status"], ["Inbox", "Ready", "In progress", "In review", "Done"])
        self.assertEqual(f["Priority"], ["P0", "P1", "P2", "P3"])
        self.assertEqual(f["Release"], ["v1.0-beta", "v1.0", "v1.1", "v1.2", "later"])
        self.assertEqual(f["Size"], ["S", "M", "L"])
        self.assertEqual(len(f["Area"]), 10)
        self.assertEqual(f["Phase"][0], "P0 Foundations")
        self.assertEqual(f["Phase"][1], "P1 Stable + first run")
        self.assertEqual(len(f["Phase"]), 6)


class MapTest(unittest.TestCase):
    status = ["Inbox", "Ready", "In progress", "In review", "Done"]

    def test_default_status_options(self):
        self.assertEqual(map_option("Todo", self.status), "Inbox")
        self.assertEqual(map_option("In Progress", self.status), "In progress")
        self.assertEqual(map_option("Done", self.status), "Done")

    def test_bare_phase_moves_to_descriptive(self):
        phases = ["P0 Foundations", "P1 Stable + first run"]
        self.assertEqual(map_option("P1", phases), "P1 Stable + first run")

    def test_v1_0_does_not_match_v1_0_beta(self):
        self.assertEqual(map_option("v1.0", ["v1.0-beta", "v1.0"]), "v1.0")

    def test_unknown_option_has_no_target(self):
        self.assertIsNone(map_option("Blocked", self.status))


class PlanTest(unittest.TestCase):
    def test_matching_field_needs_nothing(self):
        field = {"options": [{"id": "a", "name": "S", "color": "RED"}]}
        self.assertIsNone(plan_field(field, ["S"]))

    def test_keeps_colour_and_moves_values(self):
        field = {"options": [
            {"id": "t", "name": "Todo", "color": "GREEN", "description": "x"},
            {"id": "d", "name": "Done", "color": "PURPLE", "description": ""},
        ]}
        options, moves = plan_field(field, ["Inbox", "Ready", "Done"])
        self.assertEqual([o["name"] for o in options], ["Inbox", "Ready", "Done"])
        self.assertEqual(options[0]["color"], "GREEN")
        self.assertEqual(options[1]["color"], "GRAY")
        self.assertEqual(moves, {"t": "Inbox", "d": "Done"})


if __name__ == "__main__":
    unittest.main()
