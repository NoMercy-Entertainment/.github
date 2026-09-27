import unittest

from setup_project import (
    map_option,
    open_issue_refs,
    parse_arrangement,
    plan_field,
    read_doc_fields,
    read_doc_views,
    view_payload,
)


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


class ViewsTest(unittest.TestCase):
    ids = {"status": 1, "priority": 2, "phase": 3, "area": 4}

    def test_reads_seven_views_from_the_doc(self):
        views = read_doc_views()
        self.assertEqual(len(views), 7)
        self.assertEqual(views[0], {"name": "Board", "layout": "board",
                                    "filter": "-status:Done", "arrange": "Columns by Status"})
        self.assertEqual(views[1]["filter"], "release:v1.0-beta,v1.0 priority:P0,P1 -status:Done")
        self.assertEqual(views[2]["layout"], "roadmap")
        self.assertEqual(views[6]["arrange"], "Sort by created")

    def test_parses_each_arrangement(self):
        self.assertEqual(parse_arrangement("Columns by Status"), ("columns", "Status"))
        self.assertEqual(parse_arrangement("Group by Priority"), ("group", "Priority"))
        self.assertEqual(parse_arrangement("Sort by created"), ("sort", "created"))
        with self.assertRaises(ValueError):
            parse_arrangement("Slice by Area")

    def test_board_columns_are_the_vertical_group(self):
        body, notes = view_payload(read_doc_views()[0], self.ids)
        self.assertEqual(body, {"name": "Board", "layout": "board",
                                "filter": "-status:Done", "vertical_group_by": [1]})
        self.assertEqual(notes, [])

    def test_group_and_sort(self):
        views = read_doc_views()
        body, _ = view_payload(views[1], self.ids)
        self.assertEqual(body["group_by"], [2])
        body, _ = view_payload(views[4], self.ids)
        self.assertEqual(body["sort_by"], [[2, "asc"]])

    def test_missing_field_is_reported_not_invented(self):
        body, notes = view_payload(read_doc_views()[6], self.ids)
        self.assertEqual(body, {"name": "Inbox", "layout": "table", "filter": "status:Inbox"})
        self.assertEqual(len(notes), 1)
        self.assertIn("'created'", notes[0])


class OpenIssuesTest(unittest.TestCase):
    def test_skips_archived_repos_and_pull_requests(self):
        repos = [
            {"full_name": "o/live", "archived": False},
            {"full_name": "o/old", "archived": True},
        ]
        issues = {
            "o/live": [{"number": 1}, {"number": 2, "pull_request": {}}, {"number": 3}],
            "o/old": [{"number": 9}],
        }
        self.assertEqual(open_issue_refs(repos, issues.__getitem__), ["o/live#1", "o/live#3"])


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
