"""Tests for the registration count. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import registration_count as rc  # noqa: E402

REPORT = """Registration Report,,,,,,,
Report generated time,10/14/2026 08:28:33 PM,,,,,,
Topic,ID,Scheduled Time,Duration (minutes),# Registrants,# Cancelled registrants,# Approved registrants,# Denied registrants
Test Meetup,111 2222 3333,10/21/2026 01:00:00 PM,60,3,1,2,0
Attendee Details,,,,,,,
First Name,Last Name,Email,Registration Time,Approval Status,Organization,Job Title,
Zed,Person,zed@example.org,09/15/2026 01:32:28 PM,approved,Org One,Boss,
Amy,Other,amy@example.org,10/01/2026 12:45:18,approved,,,
Bo,Third,bo@example.org,10/13/2026 03:10:56 PM,cancelled,Org Two,Worker,
"""


def rows(text):
    return list(csv.reader(io.StringIO(text)))


class ParseTests(unittest.TestCase):
    def test_totals(self):
        reg = rc.parse_report(rows(REPORT))
        self.assertEqual((reg.registrants, reg.cancelled, reg.approved, reg.denied), (3, 1, 2, 0))
        self.assertEqual(reg.topic, "Test Meetup")

    def test_listed_rows_counted_and_consistent(self):
        reg = rc.parse_report(rows(REPORT))
        self.assertEqual(reg.listed, 3)
        self.assertTrue(reg.consistent)

    def test_mismatch_detected(self):
        reg = rc.parse_report(rows(REPORT.replace(",60,3,1,2,0", ",60,5,1,2,0")))
        self.assertFalse(reg.consistent)
        self.assertIn("5 registrants but 3", rc.build_digest(reg))

    def test_stale_report_flagged(self):
        reg = rc.parse_report(rows(REPORT))
        self.assertTrue(reg.stale)
        self.assertIn("7 days before the meeting", rc.build_digest(reg))

    def test_fresh_report_not_flagged(self):
        fresh = REPORT.replace("10/14/2026 08:28:33 PM", "10/22/2026 08:28:33 AM")
        reg = rc.parse_report(rows(fresh))
        self.assertFalse(reg.stale)
        self.assertNotIn("registered later", rc.build_digest(reg))

    def test_digest_holds_no_registrant_details(self):
        digest = rc.build_digest(rc.parse_report(rows(REPORT)))
        for leaked in ("Zed", "Amy", "Bo", "example.org", "Org One", "Boss"):
            self.assertNotIn(leaked, digest)

    def test_missing_summary_rejected(self):
        with self.assertRaises(rc.RegistrationFormatError):
            rc.parse_report(rows("Registration Report\nsomething else\n"))

    def test_non_numeric_total_rejected(self):
        with self.assertRaises(rc.RegistrationFormatError):
            rc.parse_report(rows(REPORT.replace(",60,3,1,2,0", ",60,many,1,2,0")))


class RunTests(unittest.TestCase):
    def test_writes_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp)
            (private / "registration_1_2026_10_21.csv").write_text(REPORT, encoding="utf-8")
            blog = Path(tmp) / "blog"
            output, reg = rc.run(private, blog)
            self.assertEqual(output.parent, blog)
            self.assertIn("Registered: **3**", output.read_text(encoding="utf-8"))
            self.assertEqual(reg.registrants, 3)

    def test_no_report_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(rc.run(Path(tmp), Path(tmp) / 'blog'))

    def test_two_reports_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("registration_a.csv", "registration_b.csv"):
                (Path(tmp) / name).write_text(REPORT, encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                rc.run(Path(tmp), Path(tmp) / 'blog')




class OutputFolderTests(unittest.TestCase):
    def test_digest_goes_to_blog_folder_not_beside_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            private, blog = Path(tmp) / "private", Path(tmp) / "out" / "blog-202610"
            private.mkdir()
            (private / "registration_report.csv").write_text(REPORT, encoding="utf-8")
            output, _ = rc.run(private, blog)
            self.assertEqual(output, blog / rc.DIGEST_NAME)
            self.assertEqual(sorted(p.name for p in private.iterdir()), ["registration_report.csv"])


if __name__ == "__main__":
    unittest.main()
