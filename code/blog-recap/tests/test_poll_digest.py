"""Tests for the poll digest. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import poll_digest as pd  # noqa: E402

CSV = """Overview
Generate Time,Meeting Topic,Meeting/Webinar ID,Actual Start Time
10/21/2026 05:19:27 PM,Test Meetup,123,10/21/2026 12:41:51 PM

Launched Polls
#,Poll Name,Questions,Responses
1,Feedback,2,3

Feedback
#,Submitted Date and Time,"Capacity: This helped me.",Network: This connected me.
1,10/21/2026 01:58:58 PM,5,4,,,,
2,10/21/2026 01:58:55 PM,3,4,,,,
3,10/21/2026 01:58:57 PM,4,2,,,,

"""

NAMED = CSV.replace(
    "#,Submitted Date and Time", "#,User Name,Email Address,Submitted Date and Time"
).replace("1,10/21", "1,Zed Person,z@example.org,10/21").replace(
    "2,10/21", "2,Amy Other,a@example.org,10/21"
).replace("3,10/21", "3,Bo Third,b@example.org,10/21")


def rows(text):
    return list(csv.reader(io.StringIO(text)))


class ParseTests(unittest.TestCase):
    def test_counts_and_means(self):
        poll = pd.parse_poll(rows(CSV))[0]
        self.assertEqual((poll.name, poll.responses), ("Feedback", 3))
        self.assertEqual([round(q.mean, 2) for q in poll.questions], [4.0, 3.33])

    def test_label_and_statement_split(self):
        q = pd.parse_poll(rows(CSV))[0].questions[0]
        self.assertEqual((q.label, q.statement), ("Capacity", "This helped me."))

    def test_agree_share_and_distribution(self):
        q = pd.parse_poll(rows(CSV))[0].questions[1]
        self.assertAlmostEqual(q.agree_share, 2 / 3)
        self.assertEqual(q.distribution()[2], 1)

    def test_respondent_columns_ignored_and_not_written(self):
        poll = pd.parse_poll(rows(NAMED))[0]
        self.assertEqual([round(q.mean, 2) for q in poll.questions], [4.0, 3.33])
        digest = pd.build_digest([poll], "Test Meetup")
        for leaked in ("Zed", "Amy", "example.org"):
            self.assertNotIn(leaked, digest)

    def test_digest_gives_percentage_per_sentiment(self):
        digest = pd.build_digest(pd.parse_poll(rows(CSV)), "Test Meetup")
        self.assertIn("Strongly agree | Agree | Neutral | Disagree | Strongly disagree", digest)
        # Network question: ratings 4, 4, 2 -> Agree 67%, Disagree 33%
        self.assertIn("| 0% (0) | 67% (2) | 0% (0) | 33% (1) | 0% (0) | 67% (2) |", digest)

    def test_non_numeric_rating_rejected(self):
        with self.assertRaises(pd.PollFormatError):
            pd.parse_poll(rows(CSV.replace(",5,4,", ",x,4,")))

    def test_out_of_range_rejected(self):
        with self.assertRaises(pd.PollFormatError):
            pd.parse_poll(rows(CSV.replace(",5,4,", ",7,4,")))

    def test_no_poll_block_rejected(self):
        with self.assertRaises(pd.PollFormatError):
            pd.parse_poll(rows("Overview\nGenerate Time,Meeting Topic\n"))


class RunTests(unittest.TestCase):
    def test_writes_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, private = Path(tmp, "docs"), Path(tmp, "private")
            docs.mkdir()
            private.mkdir()
            (docs / "zoom-poll.csv").write_text(CSV, encoding="utf-8")
            output, polls = pd.run(docs, private)
            text = output.read_text(encoding="utf-8")
            self.assertIn("Responses: 3", text)
            self.assertIn("Test Meetup", text)
            self.assertEqual(len(polls), 1)

    def test_no_poll_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(pd.run(Path(tmp), Path(tmp)))


if __name__ == "__main__":
    unittest.main()
