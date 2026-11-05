"""Tests for the comms-copy stage and the authors in session inputs. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import comms_copy as cc  # noqa: E402
import session_inputs as si  # noqa: E402

COPY = r"""# Email invitation

Dear \<\<name\>\>,

**This month’s theme: RCM Narratives**

The session uses narratives to help RCMs describe their job.

**Speaker**

- **\[Ada Speaker\](https://example.org/people/ada)**, Community Manager, Some Institute

**Host**

- **\[Hal Host\](https://www.example.org/team/Hal-Host/),**Trainer Community Manager, Some Academy

**When: 21st October 2026, 13:00 (UK)**

Please contact Emma (emma@example.org) or Cass (cass@example.org).

# Slack

**This month’s theme: Something else**

**Host**

- **\[Wrong Person\](https://example.org/wrong)**, Not Used
"""

REGISTER = "https://us06web.zoom.us/meeting/register/abc123"
ARCHIVE = "https://github.com/rcmcooperative/Monthly-Meetups/tree/main/docs/materials-202610"
LINKS = {"register_url": REGISTER, "recording_url": "none", "archive_url": ARCHIVE}


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.found = cc.parse_comms(COPY)

    def test_speaker_and_host(self):
        self.assertEqual(self.found["speakers"][0]["name"], "Ada Speaker")
        self.assertEqual(self.found["speakers"][0]["url"], "https://example.org/people/ada")
        self.assertEqual(self.found["speakers"][0]["role"], "Community Manager, Some Institute")
        self.assertEqual(self.found["hosts"][0]["name"], "Hal Host")
        self.assertEqual(self.found["hosts"][0]["role"], "Trainer Community Manager, Some Academy")

    def test_later_channels_ignored(self):
        self.assertEqual(len(self.found["hosts"]), 1)
        self.assertEqual(self.found["theme"], "RCM Narratives")

    def test_theme_description_and_when(self):
        self.assertTrue(self.found["theme_description"].startswith("The session uses narratives"))
        self.assertIn("21st October 2026", self.found["when"])

    def test_emails_not_extracted(self):
        self.assertNotIn("example.org", str({k: v for k, v in self.found.items() if k not in ("hosts", "speakers")}).replace("21st", ""))

    def test_month_check(self):
        self.assertIsNone(cc.check_month("21st October 2026, 13:00 (UK)", "202610"))
        self.assertIn("not November 2026", cc.check_month("21st October 2026", "202611"))


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self.tmp.name, "docs")
        self.blog = Path(self.tmp.name, "blog")
        self.docs.mkdir()
        si.collect_links(self.blog, "202610", LINKS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_people_saved(self):
        (self.docs / "comms-copy.md").write_text(COPY, encoding="utf-8")
        found, notes = cc.run(self.docs, self.blog, "202610")
        data = si.load(self.blog)
        self.assertEqual(data["hosts"][0]["name"], "Hal Host")
        self.assertEqual(data["people_source"], "comms-copy.md")
        self.assertEqual(notes, [])

    def test_no_file_returns_none(self):
        self.assertIsNone(cc.run(self.docs, self.blog, "202610"))

    def test_no_people_rejected(self):
        (self.docs / "comms-copy.md").write_text("# Email\n\nNo lists here\n", encoding="utf-8")
        with self.assertRaises(cc.CommsCopyError):
            cc.run(self.docs, self.blog, "202610")

    def test_sentence_links_host_and_speaker(self):
        (self.docs / "comms-copy.md").write_text(COPY, encoding="utf-8")
        cc.run(self.docs, self.blog, "202610")
        sentence = si.people_sentence(si.load(self.blog))
        self.assertEqual(
            sentence,
            "This session was hosted by [Hal Host](https://www.example.org/team/Hal-Host/) "
            "and featured a presentation from [Ada Speaker](https://example.org/people/ada).",
        )

    def test_sentence_joins_several_people(self):
        people = [{"name": "A", "url": "https://a.org"}, {"name": "B", "url": "https://b.org"},
                  {"name": "C", "url": "https://c.org"}]
        self.assertEqual(si.join_links(people), "[A](https://a.org), [B](https://b.org) and [C](https://c.org)")


class AuthorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blog = Path(self.tmp.name, "blog")

    def tearDown(self):
        self.tmp.cleanup()

    def test_team_and_external(self):
        data = si.collect_authors(self.blog, ["emma-karoune", "Alexandra-Araujo-Alvarez"],
                                  ["Guest Writer|https://example.org/guest"])
        self.assertEqual(data["authors"][0], {"team": "emma-karoune"})
        self.assertEqual(data["authors"][1], {"team": "Alexandra-Araujo-Alvarez"})
        self.assertEqual(data["authors"][2], {"name": "Guest Writer", "url": "https://example.org/guest"})

    def test_md_extension_stripped_and_duplicates_dropped(self):
        data = si.collect_authors(self.blog, ["emma-karoune.md", "Emma-Karoune"], [])
        self.assertEqual(data["authors"], [{"team": "emma-karoune"}])

    def test_full_name_rejected_with_pointer_to_team_folder(self):
        with self.assertRaises(si.InputsError) as raised:
            si.collect_authors(self.blog, ["Emma Karoune"], [])
        self.assertIn("_team", str(raised.exception))

    def test_external_needs_name_and_https_link(self):
        for bad in ("Guest Writer", "Guest|http://example.org", "|https://example.org"):
            with self.assertRaises(si.InputsError):
                si.collect_authors(self.blog, [], [bad])

    def test_missing_authors_rejected(self):
        with self.assertRaises(si.InputsError):
            si.collect_authors(self.blog, [], [])

    def test_saved_authors_reused_and_replaced(self):
        si.collect_authors(self.blog, ["emma-karoune"], [])
        self.assertEqual(si.collect_authors(self.blog, [], [])["authors"], [{"team": "emma-karoune"}])
        replaced = si.collect_authors(self.blog, ["cassandra-gouldvanpraag"], [])
        self.assertEqual(replaced["authors"], [{"team": "cassandra-gouldvanpraag"}])

    def test_prompt_used_when_nothing_saved(self):
        data = si.collect_authors(self.blog, [], [], ask=lambda: (["emma-karoune"], []))
        self.assertEqual(data["authors"], [{"team": "emma-karoune"}])

    def test_front_matter_rendering(self):
        data = {"authors": [{"team": "emma-karoune"}, {"name": "Guest", "url": "https://example.org/g"}]}
        self.assertEqual(
            si.render_authors(data),
            'authors:\n  - team: emma-karoune\n  - name: "Guest"\n    url: https://example.org/g',
        )


if __name__ == "__main__":
    unittest.main()
