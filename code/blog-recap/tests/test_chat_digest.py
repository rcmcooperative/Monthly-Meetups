"""Tests for the chat digest stage. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import chat_digest as cd  # noqa: E402

BRIEFING = """**Date:** 1st January 2026, 13:00 UK

# Purpose of this session:

- First aim

1.  one
2.  two

# Meetup agenda:

| **Time** | **Activity** | **Task** |
|----|----|----|
| 0-2mins; (2 mins) | Welcome | Start recording |
| 2-14 mins; (12 min) | Ice breaker | Breakouts |

# Something else

Not part of the purpose.
"""

M = cd.ChatMessage

CHAT = [
    M("00:01:00", "Participant 01", "Notes: https://cryptpad.fr/code/#/2/code/edit/abc/"),
    M("00:02:00", "Participant 02", "See https://example.org/page?utm_source=x&keep=1.", 3, "💯×2, 🩷×1"),
    M("00:03:00", "Participant 01", "Notes again https://cryptpad.fr/code/#/2/code/edit/abc/"),
    M("00:04:00", "Participant 03", "https://join.slack.com/t/x/shared_invite/zt-123"),
    M("00:05:00", "Participant 03", "Just talking", 1, "😂×1"),
]


class BriefingTests(unittest.TestCase):
    def test_purpose_stops_at_next_heading(self):
        purpose = cd.extract_purpose(BRIEFING)
        self.assertIn("First aim", purpose)
        self.assertIn("two", purpose)
        self.assertNotIn("Not part of the purpose", purpose)

    def test_missing_purpose_raises(self):
        with self.assertRaises(cd.BriefingFormatError):
            cd.extract_purpose("# Other\n\ntext")

    def test_agenda_rows(self):
        self.assertEqual(
            cd.extract_agenda(BRIEFING),
            [("0-2mins; (2 mins)", "Welcome"), ("2-14 mins; (12 min)", "Ice breaker")],
        )

    def test_date(self):
        self.assertEqual(cd.extract_date(BRIEFING), "1st January 2026, 13:00 UK")


class LinkTests(unittest.TestCase):
    def test_dedupe_and_counts(self):
        links = cd.extract_links(CHAT)
        self.assertEqual(len(links), 3)
        notes = links[0]
        self.assertEqual(notes.count, 2)
        self.assertEqual(notes.first_time, "00:01:00")

    def test_tracking_removed_and_trailing_punctuation_stripped(self):
        links = cd.extract_links(CHAT)
        self.assertEqual(links[1].url, "https://example.org/page?keep=1")

    def test_private_links_flagged(self):
        links = cd.extract_links(CHAT)
        self.assertTrue(links[0].handling.startswith("PRIVATE"))
        self.assertTrue(links[2].handling.startswith("PRIVATE"))
        self.assertEqual(links[1].handling, "public")

    def test_fragment_preserved(self):
        self.assertIn("#/2/code/edit/abc/", cd.clean_url("https://cryptpad.fr/code/#/2/code/edit/abc/"))

    def test_digest_contains_sections(self):
        digest = cd.build_digest(BRIEFING, CHAT, "chat.txt", "brief.md", "202601")
        for heading in ["## Event purpose", "## Agenda", "## Most-reacted messages", "## Links shared in chat"]:
            self.assertIn(heading, digest)
        self.assertIn("Chat span: 00:01:00 to 00:05:00", digest)
        self.assertIn("Reactions: 4 on 2 messages", digest)

    def test_link_carries_reactions_of_first_message(self):
        links = cd.extract_links(CHAT)
        self.assertEqual(links[1].reactions, 3)
        self.assertEqual(links[0].reactions, 0)


class ReactionParsingTests(unittest.TestCase):
    TEXT = (
        "00:00:01\tParticipant 01:\tHello [+3 reactions: 💯×2, 🩷×1]\n"
        "00:00:02\tParticipant 02:\tFirst line\n"
        "second line [+1 reaction: 😂×1]\n"
        "00:00:03\tParticipant 02:\tNo reactions here\n"
    )

    def test_note_split_from_body(self):
        first, second, third = cd.parse_chat(self.TEXT)
        self.assertEqual((first.body, first.reactions, first.reaction_detail), ("Hello", 3, "💯×2, 🩷×1"))
        self.assertEqual((second.body, second.reactions), ("First line\nsecond line", 1))
        self.assertEqual((third.body, third.reactions), ("No reactions here", 0))

    def test_most_reacted_ordering_and_limit(self):
        top = cd.most_reacted(CHAT)
        self.assertEqual([m.timestamp for m in top], ["00:02:00", "00:05:00"])
        self.assertEqual(len(cd.most_reacted(CHAT, limit=1)), 1)

    def test_link_context_excludes_reaction_note(self):
        messages = cd.parse_chat(
            "00:00:01\tParticipant 01:\tSee https://example.org [+2 reactions: 👍×2]\n"
        )
        (link,) = cd.extract_links(messages)
        self.assertEqual(link.url, "https://example.org")
        self.assertEqual(link.context, "See")
        self.assertEqual(link.reactions, 2)


class RunTests(unittest.TestCase):
    def test_run_writes_digest_beside_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "project-management" / "communications" / "blog-202601"
            docs = Path(tmp) / "docs" / "materials-202601"
            private.mkdir(parents=True)
            docs.mkdir(parents=True)
            (docs / "facilitators-briefing.md").write_text(BRIEFING, encoding="utf-8")
            (private / "x_Chat_anonymised.txt").write_text(
                "00:00:01\tParticipant 01:\thello https://example.org\n", encoding="utf-8"
            )
            (output,) = cd.run(private, docs)
            self.assertEqual(output.parent, private)
            self.assertIn("https://example.org", output.read_text(encoding="utf-8"))

    def test_missing_briefing(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "p"
            docs = Path(tmp) / "d"
            private.mkdir()
            docs.mkdir()
            (private / "x_Chat_anonymised.txt").write_text("00:00:01\tParticipant 01:\thi\n", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                cd.run(private, docs)


if __name__ == "__main__":
    unittest.main()
