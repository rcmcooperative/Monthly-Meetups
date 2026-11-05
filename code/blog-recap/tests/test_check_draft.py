"""Tests for the draft checks. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_draft as cd  # noqa: E402

DATA = {
    "hosts": [{"name": "Hal Host", "url": "https://example.org/hal"}],
    "speakers": [{"name": "Ada Speaker", "url": "https://example.org/ada"}],
    "authors": [{"team": "emma-karoune"}, {"name": "Guest Writer", "url": "https://example.org/g"}],
}
PEOPLE = [
    {"first": "Ada", "last": "Speaker", "email": "ada@example.org"},
    {"first": "Emma", "last": "Karoune", "email": "emma@example.org"},
    {"first": "Zed", "last": "Participant", "email": "zed@example.org"},
    {"first": "Bo", "last": "Li", "email": "bo@example.org"},
]
GOOD = """---
title: "A title"
date: 2026-11-05
image: /assets/img/blog/mm-202610-story.png
alt: a description
excerpt: One sentence.
authors:
  - team: emma-karoune
---

We met on 21 October 2026, hosted by Hal Host with a talk from Ada Speaker.
"""


def levels(findings):
    return sorted({f.level for f in findings})


def messages(findings):
    return " | ".join(f.message for f in findings)


class CheckTests(unittest.TestCase):
    def test_clean_draft_has_no_findings(self):
        self.assertEqual(cd.check_text(GOOD, PEOPLE, DATA), [])

    def test_placeholder_reported_with_line(self):
        findings = cd.check_text(GOOD + "\nHello {{WHAT_WORKED}}\n", PEOPLE, DATA)
        self.assertEqual(levels(findings), ["problem"])
        self.assertIn("WHAT_WORKED", findings[0].message)
        self.assertEqual(findings[0].line, GOOD.count("\n") + 2)

    def test_image_placeholders_are_held_back(self):
        text = GOOD.replace("mm-202610-story.png", "mm-202610-{{IMAGE_SLUG}}.png").replace("a description", "{{IMAGE_ALT}}")
        findings = cd.check_text(text, PEOPLE, DATA)
        self.assertEqual(levels(findings), ["image"])
        self.assertEqual(cd.exit_code(findings, final=False), 0)
        self.assertEqual(cd.exit_code(findings, final=True), 1)

    def test_comments_flagged_and_their_placeholders_ignored(self):
        findings = cd.check_text(GOOD + "<!-- TEMPLATE NOTES {{TITLE}} -->\n<!-- guidance -->\n", PEOPLE, DATA)
        self.assertEqual(len(findings), 2)
        self.assertIn("template notes", findings[0].message)
        self.assertIn("template comment", findings[1].message)

    def test_missing_front_matter_key(self):
        findings = cd.check_text(GOOD.replace("excerpt: One sentence.\n", ""), PEOPLE, DATA)
        self.assertIn("'excerpt:'", messages(findings))

    def test_no_front_matter(self):
        self.assertIn("no front matter", messages(cd.check_text("Just text", PEOPLE, DATA)))

    def test_room_numbers_and_labels(self):
        text = GOOD + "In Room 3 and Rooms 4 we heard Participant 07 say [name].\n"
        found = messages(cd.check_text(text, PEOPLE, DATA))
        self.assertIn("Room 3", found)
        self.assertIn("Rooms 4", found)
        self.assertIn("Participant 07", found)
        self.assertIn("[name]", found)

    def test_breakout_room_without_number_is_fine(self):
        self.assertEqual(cd.check_text(GOOD + "We used breakout rooms.\n", PEOPLE, DATA), [])

    def test_private_links(self):
        text = GOOD + "Notes: https://cryptpad.fr/pad/#/2/pad/edit/abc/\nJoin: https://join.slack.com/t/x/shared_invite/zt-1\n"
        findings = cd.check_text(text, PEOPLE, DATA)
        self.assertEqual(len(findings), 2)

    def test_registrant_name_flagged(self):
        findings = cd.check_text(GOOD + "Thanks to Zed Participant for the idea.\n", PEOPLE, DATA)
        self.assertEqual(levels(findings), ["problem"])
        self.assertNotIn("Zed", findings[0].message)  # the name is not echoed
        self.assertNotIn("Participant", findings[0].message)

    def test_registrant_surname_alone_flagged(self):
        findings = cd.check_text(GOOD + "Participant said so.\n", PEOPLE, DATA)
        self.assertIn("registrant", messages(findings))

    def test_short_surnames_not_matched_on_their_own(self):
        self.assertEqual(cd.check_text(GOOD + "Where Li went next.\n", PEOPLE, DATA), [])

    def test_host_speaker_and_authors_allowed(self):
        text = GOOD + "Ada Speaker and Emma Karoune and Hal Host.\n"
        self.assertEqual(cd.check_text(text, PEOPLE, DATA), [])

    def test_config_team_names_allowed(self):
        people = [{"first": "Cassandra", "last": "Gould van Praag", "email": ""}]
        self.assertEqual(cd.check_text(GOOD + "Cassandra Gould van Praag wrote this.\n", people, DATA), [])

    def test_registrant_email_flagged(self):
        findings = cd.check_text(GOOD + "Write to zed@example.org\n", PEOPLE, DATA)
        self.assertIn("email", messages(findings))

    def test_team_email_not_flagged(self):
        self.assertEqual(cd.check_text(GOOD + "Write to emma@example.org\n", PEOPLE, DATA), [])

    def test_marks_are_to_dos(self):
        findings = cd.check_text(GOOD + "<mark>check this</mark>\n", PEOPLE, DATA)
        self.assertEqual(levels(findings), ["todo"])
        self.assertEqual(cd.exit_code(findings, final=False), 0)
        self.assertEqual(cd.exit_code(findings, final=True), 1)


REPORT = """Registration Report,,,,,,,
Topic,ID,Scheduled Time,Duration (minutes),# Registrants,# Cancelled registrants,# Approved registrants,# Denied registrants
Test,1,10/21/2026 01:00:00 PM,60,2,0,2,0
Attendee Details,,,,,,,
First Name,Last Name,Email,Registration Time,Approval Status,Organization,Job Title,
Zed,Participant,zed@example.org,09/15/2026 01:32:28 PM,approved,Org,Job,
Amy,Other,amy@example.org,09/15/2026 01:32:28 PM,approved,,,
"""


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blog = Path(self.tmp.name, "blog")
        self.private = Path(self.tmp.name, "private")
        self.blog.mkdir()
        self.private.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_draft_returns_none(self):
        self.assertIsNone(cd.run(self.blog, self.private, "202610"))

    def test_registrants_read_from_report(self):
        (self.private / "registration_1.csv").write_text(REPORT, encoding="utf-8")
        people = cd.registrants(self.private)
        self.assertEqual([(p["first"], p["last"]) for p in people], [("Zed", "Participant"), ("Amy", "Other")])

    def test_no_report_means_no_name_check(self):
        self.assertEqual(cd.registrants(self.private), [])

    def test_run_checks_draft_against_registrants(self):
        (self.private / "registration_1.csv").write_text(REPORT, encoding="utf-8")
        (self.blog / "mm-recap-202610.md").write_text(GOOD + "Thanks, Zed Participant.\n", encoding="utf-8")
        path, findings = cd.run(self.blog, self.private, "202610")
        self.assertEqual(path.name, "mm-recap-202610.md")
        self.assertEqual(levels(findings), ["problem"])


if __name__ == "__main__":
    unittest.main()
