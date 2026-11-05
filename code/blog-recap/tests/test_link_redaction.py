"""Tests for link redaction in the anonymised chat. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v

They use the detector and redaction.toml of the materials-archiving skill, which must be in
the repo at code/materials-archiving/ (the tests are skipped if it is not).
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import anonymise_chat  # noqa: E402
import link_redaction as lr  # noqa: E402

ARCHIVING = Path(__file__).resolve().parents[2] / "materials-archiving"

CHAT = (
    "00:01:00\tParticipant 01:\tNotes https://cryptpad.fr/pad/#/2/pad/edit/SECRET/\n"
    "00:01:05\tParticipant 02:\tJoin https://join.slack.com/t/team/shared_invite/zt-abc\n"
    "00:01:10\tParticipant 03:\tSee https://www.rcmcooperative.com/join/\n"
    "00:01:20\tParticipant 04:\tMy page https://www.linkedin.com/in/someone and mail x@example.org\n"
)


@unittest.skipUnless((ARCHIVING / "config" / "redaction.toml").is_file(), "materials-archiving not in repo")
class RedactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = lr.load(ARCHIVING)

    def test_flags_blocking_and_unlisted_but_not_allowed(self):
        flagged, findings = lr.flag(CHAT, self.rules)
        self.assertIn("<redact>https://cryptpad.fr/pad/#/2/pad/edit/SECRET/</redact>", flagged)
        self.assertIn("<redact>https://join.slack.com", flagged)
        self.assertIn("<redact>https://www.linkedin.com/in/someone</redact>", flagged)
        self.assertIn("<redact>x@example.org</redact>", flagged)
        self.assertNotIn("<redact>https://www.rcmcooperative.com", flagged)
        self.assertEqual(sum(f.blocking for f in findings), 2)

    def test_apply_replaces_every_tag(self):
        flagged, _ = lr.flag(CHAT, self.rules)
        final, count, problems = lr.apply(flagged, "x", self.rules)
        self.assertEqual(count, 4)
        self.assertEqual(problems, [])
        self.assertNotIn("cryptpad", final)
        self.assertNotIn("slack", final)
        self.assertIn("rcmcooperative.com", final)
        self.assertIn("`<redacted>`", final)

    def test_untagged_blocking_link_blocks_even_when_residual_accepted(self):
        flagged, _ = lr.flag(CHAT, self.rules)
        untagged = flagged.replace("<redact>https://join.slack.com", "https://join.slack.com", 1)
        untagged = untagged.replace("shared_invite/zt-abc</redact>", "shared_invite/zt-abc")
        _, _, problems = lr.apply(untagged, "x", self.rules, accept_residual=True)
        self.assertTrue(any("blocking" in p for p in problems))

    def test_untagged_ordinary_link_needs_accept_residual(self):
        flagged, _ = lr.flag(CHAT, self.rules)
        kept = flagged.replace("<redact>https://www.linkedin.com/in/someone</redact>",
                               "https://www.linkedin.com/in/someone")
        _, _, problems = lr.apply(kept, "x", self.rules)
        self.assertEqual(len(problems), 1)
        _, _, problems = lr.apply(kept, "x", self.rules, accept_residual=True)
        self.assertEqual(problems, [])

    def test_person_added_tag_is_applied(self):
        flagged, _ = lr.flag(CHAT, self.rules)
        flagged = flagged.replace("My page", "<redact>My page</redact>")
        final, _, _ = lr.apply(flagged, "x", self.rules)
        self.assertNotIn("My page", final)

    def test_malformed_tags_raise_with_line(self):
        with self.assertRaises(self.rules.error) as caught:
            lr.apply("one\n<redact>open", "chat.review.txt", self.rules)
        self.assertIn("chat.review.txt", str(caught.exception))

    def test_rerunning_flag_does_not_double_wrap(self):
        flagged, _ = lr.flag(CHAT, self.rules)
        again, findings = lr.flag(flagged, self.rules)
        self.assertEqual(again, flagged)
        self.assertEqual(findings, [])

    def test_flag_report_lists_every_finding(self):
        _, findings = lr.flag(CHAT, self.rules)
        report = lr.flag_report(findings, CHAT, "chat.txt", self.rules)
        self.assertEqual(report.count("\n| "), len(findings) + 1)  # header row plus one per finding
        self.assertIn("yes", report)


class MissingArchivingTests(unittest.TestCase):
    def test_clear_error_when_archiving_skill_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lr.RedactionError) as caught:
                lr.load(Path(tmp))
            self.assertIn("materials-archiving", str(caught.exception))


class NamingTests(unittest.TestCase):
    def test_review_and_final_names(self):
        anonymised = Path("private/materials-202610/chat_anonymised.txt")
        review = lr.review_path(anonymised)
        self.assertEqual(review.name, "chat_anonymised.review.txt")
        self.assertEqual(lr.final_name(review), "chat_anonymised.txt")

    def test_review_file_is_not_mistaken_for_a_chat_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "GMT-chat.txt").write_text("x", encoding="utf-8")
            (folder / "GMT-chat_anonymised.review.txt").write_text("x", encoding="utf-8")
            self.assertEqual([p.name for p in anonymise_chat.find_chat_files(folder)], ["GMT-chat.txt"])


if __name__ == "__main__":
    unittest.main()
