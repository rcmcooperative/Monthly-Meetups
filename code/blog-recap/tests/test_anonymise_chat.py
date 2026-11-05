"""Tests for the chat anonymisation stage. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import anonymise_chat as ac  # noqa: E402

SAMPLE = (
    "00:01:00\tS - Alice Example (she/her), Example Org:\tHello all\n"
    "00:01:05\tBob Tester:\tReacted to \"Hello all\" with 👋\n"
    "00:01:10\tAlice (Ally) Example:\tNotes: https://example.org/alice/notes\n"
    "00:01:20\tW - Carol Mock (they/them):\tThanks @S - Alice Example (she/her), Example Org for this\n"
    "00:01:30\tBob Tester:\tReacted to \"line one\n"
    "line two\" with ❤️\n"
    "00:01:40\tBob Tester:\tGreat session Carol, and thanks Ally!\n"
    "continued line from the same message\n"
    "00:01:50\tCarol Mock:\tPing @Someone Else about it\n"
)


def run_text(text, extra=()):
    report = ac.Report(source=Path("x.txt"), output=Path("y.txt"))
    return ac.anonymise_text(text, list(extra), report), report


class AnonymiseTests(unittest.TestCase):
    def test_name_variants_collapse_to_one_label(self):
        out, report = run_text(SAMPLE)
        self.assertEqual(report.participants, 3)
        self.assertEqual(out.count("Participant 01:"), 2)  # both Alice variants

    def test_reactions_dropped_including_multiline(self):
        out, report = run_text(SAMPLE)
        self.assertEqual(report.reactions_dropped, 2)
        self.assertNotIn("Reacted to", out)
        self.assertNotIn("line two", out)

    def test_mentions_and_names_replaced(self):
        out, _ = run_text(SAMPLE)
        self.assertIn("Thanks @Participant 01 for this", out)
        self.assertIn("Great session [name], and thanks [name]!", out)

    def test_continuation_lines_kept(self):
        out, _ = run_text(SAMPLE)
        self.assertIn("\ncontinued line from the same message\n", out)

    def test_urls_untouched_even_if_they_contain_names(self):
        out, report = run_text(SAMPLE)
        self.assertIn("https://example.org/alice/notes", out)
        self.assertTrue(report.ok)

    def test_no_raw_names_remain(self):
        out, report = run_text(SAMPLE)
        for name in ["Alice", "Bob", "Carol", "Tester", "Example", "Ally", "Mock"]:
            self.assertNotIn(name, out.replace("https://example.org/alice/notes", ""))
        self.assertTrue(report.ok)

    def test_unresolved_mention_reported(self):
        _, report = run_text(SAMPLE)
        self.assertEqual(len(report.unresolved_mentions), 1)

    def test_extra_name_scrubbed(self):
        text = "00:00:01\tAlice Example:\tThanks Zed for hosting\n"
        out, _ = run_text(text, extra=["Zed"])
        self.assertIn("Thanks [name] for hosting", out)

    def test_labels_are_deterministic(self):
        self.assertEqual(run_text(SAMPLE)[0], run_text(SAMPLE)[0])

    def test_malformed_header_raises(self):
        with self.assertRaises(ac.ChatFormatError):
            run_text("00:00:01\tNo colon here\n")

    def test_non_chat_file_raises(self):
        with self.assertRaises(ac.ChatFormatError):
            run_text("just some prose\nwith no timestamps\n")

    def test_run_writes_alongside_input_and_skips_own_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "GMT20261021-000000_RecordingnewChat.txt").write_text(SAMPLE, encoding="utf-8")
            (folder / "notes.md").write_text("not a chat", encoding="utf-8")
            reports = ac.run(folder)
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].output.parent, folder)
            self.assertTrue(reports[0].output.name.endswith("_anonymised.txt"))
            self.assertEqual(len(ac.run(folder)), 1)  # re-run ignores its own output

    def test_output_dir_keeps_raw_folder_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, blog = Path(tmp) / "private", Path(tmp) / "out" / "blog-202610"
            raw.mkdir()
            (raw / "GMT20261021-000000_RecordingnewChat.txt").write_text(SAMPLE, encoding="utf-8")
            reports = ac.run(raw, output_dir=blog)
            self.assertEqual(reports[0].output.parent, blog)
            self.assertTrue(reports[0].output.exists())
            self.assertFalse(list(raw.glob("*_anonymised.txt")))

    def test_missing_chat_file_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                ac.find_chat_files(Path(tmp))


REACTIONS = (
    "00:00:01\tAlice Example:\tMy origin story is long and random\n"
    "00:00:02\tBob Tester:\tReacted to \"My origin sto...\" with 💯\n"
    "00:00:03\tCarol Mock:\tReacted to \"My origin story is long and random\" with 🩷\n"
    "00:00:04\tCarol Mock:\tReplying to \"My origin sto...\"\n"
    "\n"
    "so true\n"
    "00:00:05\tAlice Example:\tReacted to \"so true\" with 😂\n"
    "00:00:06\tBob Tester:\tReacted to \"so true\" with 😂\n"
    "00:00:07\tBob Tester:\tThank you!\n"
    "00:00:08\tCarol Mock:\tThank you!\n"
    "00:00:09\tAlice Example:\tReacted to \"Thank you!\" with 👍\n"
    "00:00:10\tAlice Example:\tRemoved a 👍 reaction from \"Thank you!\"\n"
    "00:00:11\tAlice Example:\tReacted to \"A message that never existed\" with 👍\n"
)


class ReactionTests(unittest.TestCase):
    def setUp(self):
        self.out, self.report = run_text(REACTIONS)
        self.lines = self.out.split("\n")

    def test_truncated_and_full_quotes_attach_to_same_message(self):
        first = next(line for line in self.lines if "My origin story is long" in line)
        self.assertTrue(first.endswith("[+2 reactions: 💯×1, 🩷×1]"))

    def test_quote_of_a_reply_attaches_to_the_reply(self):
        self.assertIn("so true [+2 reactions: 😂×2]", self.out)

    def test_most_recent_matching_message_gets_the_reaction(self):
        thanks = [line for line in self.lines if "Thank you!" in line]
        self.assertEqual(len(thanks), 2)
        self.assertNotIn("reaction", thanks[0])
        self.assertNotIn("reaction", thanks[1])  # added then removed -> zero

    def test_unmatched_events_are_counted_not_attached(self):
        self.assertEqual(self.report.reactions_unmatched, 1)
        self.assertEqual(self.report.reactions_attached, 4)  # 2 + 2; the 👍 was removed

    def test_reaction_events_are_not_left_in_output(self):
        self.assertNotIn("Reacted to", self.out)
        self.assertNotIn("Removed a", self.out)
        self.assertEqual(self.report.reactions_dropped, 7)

    def test_note_format(self):
        from collections import Counter
        self.assertEqual(ac.reaction_note(Counter({"👋": 1})), "[+1 reaction: 👋×1]")
        self.assertEqual(ac.reaction_note(Counter()), "")
        self.assertEqual(ac.reaction_note(Counter({"👍": 0})), "")


if __name__ == "__main__":
    unittest.main()
