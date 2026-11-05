"""Tests for the collaborative notes digest stage. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import notes_digest as nd  # noqa: E402

NOTES = """# Monthly Meet-up

# Theme title: Test Theme

**PRIVACY NOTICE**
- Do not include confidential information.

## Attendees

(Name / Pronouns / Affiliation / Email)

- Alice Example / she/her / Some Org / alice@example.org / @alice
- Bob "Bobby" Tester / he/him / Other Org / `<redacted>`
- Carol Mock / they/them / Third Org

## Notes

### Icebreaker

### Alice Example

Likes theatre. See https://example.org/alice for more.

### Exercises
1. Origin story
  - tell it
2. Collaborative story
  - draft it

#### Breakout Room 1
- Speaker: Dana Newcomer

##### Notes Bob
Joined in 2020 via a seminar series.
Reflection
- Alice noticed the mentor thread.

##### Notes [Carol Mock]
- Started as a volunteer
-

##### Collaborative story
Roles arise from needs.
- Bobby said: share tools

#### Breakout Room 2
- Speaker: Everyone

- Untitled line about Dana.

##### Collaborative story

### Actions
- Follow up with Newcomer
"""


def parse():
    return nd.parse_notes(NOTES)


def scrubber(doc=None, extra=()):
    doc = doc or parse()
    return nd.Scrubber(nd.collect_name_tokens(doc, list(extra)))


class ParseTests(unittest.TestCase):
    def test_structure(self):
        doc = parse()
        self.assertEqual(doc.theme, "Test Theme")
        self.assertEqual([r.number for r in doc.rooms], [1, 2])
        self.assertEqual(len(doc.attendee_names), 3)
        self.assertEqual([b.kind for b in doc.rooms[0].blocks], ["notes", "notes", "story"])
        self.assertEqual(doc.rooms[0].speaker, "Dana Newcomer")

    def test_exercises_verbatim_and_not_in_before(self):
        doc = parse()
        self.assertIn("1. Origin story", doc.exercises)
        self.assertFalse(any("Origin story" in line for line in doc.before))

    def test_content_after_rooms_is_kept(self):
        doc = parse()
        self.assertTrue(any("Follow up" in line for line in doc.after))

    def test_room_level_untitled_notes(self):
        doc = parse()
        self.assertTrue(any("Untitled line" in line for line in doc.rooms[1].room_lines))

    def test_reflection_split(self):
        body, reflection = nd.split_reflection(["a", "Reflection", "b"])
        self.assertEqual((body, reflection), (["a"], ["b"]))


class ScrubTests(unittest.TestCase):
    def test_names_from_attendees_headings_and_speakers_removed(self):
        text = "Alice and Bobby met Carol; Dana joined; Newcomer left"
        out = scrubber().scrub(text)
        for name in ["Alice", "Bobby", "Carol", "Dana", "Newcomer"]:
            self.assertNotIn(name, out)

    def test_adjacent_names_collapse(self):
        self.assertEqual(scrubber().scrub("Alice Example said hi"), "[name] said hi")

    def test_urls_untouched(self):
        self.assertIn("https://example.org/alice", scrubber().scrub("see https://example.org/alice"))

    def test_extra_names(self):
        self.assertEqual(scrubber(extra=["Zed"]).scrub("thanks Zed"), "thanks [name]")

    def test_generic_speaker_words_not_scrubbed(self):
        self.assertEqual(scrubber().scrub("Everyone agreed"), "Everyone agreed")


class DigestTests(unittest.TestCase):
    def setUp(self):
        doc = parse()
        self.scrub = scrubber(doc)
        self.digest = nd.build_digest(doc, self.scrub, "notes.md", "202601")

    def test_attendee_list_and_privacy_notice_removed(self):
        self.assertNotIn("@example.org", self.digest)
        self.assertNotIn("PRIVACY NOTICE", self.digest)
        self.assertIn("Attendees listed: 3 (list removed)", self.digest)

    def test_note_takers_generic_and_reflection_separate(self):
        self.assertIn("### Note-taker 1", self.digest)
        self.assertIn("### Note-taker 2", self.digest)
        self.assertIn("### Reflection", self.digest)
        self.assertNotIn("Notes Bob", self.digest)

    def test_empty_bullet_dropped_and_empty_story_marked(self):
        self.assertNotIn("\n-\n", self.digest)
        self.assertIn("(empty)", self.digest)

    def test_completeness_table(self):
        self.assertIn("| 1 | yes | 2 |", self.digest)
        self.assertIn("| 2 | yes | 0 |", self.digest)

    def test_no_leaks(self):
        self.assertEqual(self.scrub.leaks(self.digest), [])


class RunTests(unittest.TestCase):
    def test_run_writes_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs" / "materials-202601"
            private = Path(tmp) / "project-management" / "communications" / "blog-202601"
            docs.mkdir(parents=True)
            private.mkdir(parents=True)
            (docs / "collab-notes.md").write_text(NOTES, encoding="utf-8")
            output, stats = nd.run(docs, private)
            self.assertEqual(output.parent, private)
            self.assertEqual(stats["rooms"], 2)
            self.assertEqual(stats["leak_lines"], [])

    def test_missing_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, private = Path(tmp) / "d", Path(tmp) / "p"
            docs.mkdir()
            private.mkdir()
            with self.assertRaises(FileNotFoundError):
                nd.run(docs, private)

    def test_no_rooms_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, private = Path(tmp) / "d", Path(tmp) / "p"
            docs.mkdir()
            private.mkdir()
            (docs / "collab-notes.md").write_text("# Notes only\n\n## Notes\n\ntext\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                nd.run(docs, private)


if __name__ == "__main__":
    unittest.main()
