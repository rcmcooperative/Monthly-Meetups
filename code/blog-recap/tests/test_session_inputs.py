"""Tests for session inputs. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import session_inputs as si  # noqa: E402

REGISTER = "https://us06web.zoom.us/meeting/register/abc123"
ARCHIVE = "https://github.com/rcmcooperative/Monthly-Meetups/tree/main/docs/materials-202610"
LINKS = {"register_url": REGISTER, "recording_url": "none", "archive_url": ARCHIVE}


class ValidateTests(unittest.TestCase):
    def test_good_links_have_no_warnings(self):
        for key, value in LINKS.items():
            self.assertEqual(si.validate_link(key, value, "202610"), [])

    def test_not_https_rejected(self):
        with self.assertRaises(si.InputsError):
            si.validate_link("register_url", "http://zoom.us/meeting/register/x", "202610")

    def test_archive_for_wrong_month_warned(self):
        warnings = si.validate_link("archive_url", ARCHIVE.replace("202610", "202609"), "202610")
        self.assertTrue(any("materials-202610" in w for w in warnings))

    def test_non_zoom_registration_warned(self):
        warnings = si.validate_link("register_url", "https://example.org/register/x", "202610")
        self.assertTrue(any("zoom.us" in w for w in warnings))

    def test_none_only_valid_for_recording(self):
        self.assertEqual(si.validate_link("recording_url", "None", "202610"), [])
        with self.assertRaises(si.InputsError):
            si.validate_link("archive_url", "none", "202610")


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blog = Path(self.tmp.name) / "blog-202610"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_links_listed_together(self):
        with self.assertRaises(si.InputsError) as raised:
            si.collect_links(self.blog, "202610", {})
        for key in si.LINK_KEYS:
            self.assertIn(key, str(raised.exception))

    def test_saved_and_reused(self):
        si.collect_links(self.blog, "202610", LINKS)
        data, _ = si.collect_links(self.blog, "202610", {})
        self.assertEqual(data["register_url"], REGISTER)

    def test_supplied_value_replaces_saved(self):
        si.collect_links(self.blog, "202610", LINKS)
        data, _ = si.collect_links(self.blog, "202610", {"recording_url": "https://example.org/rec"})
        self.assertEqual(data["recording_url"], "https://example.org/rec")

    def test_prompt_used_for_missing_only(self):
        asked = []
        si.collect_links(self.blog, "202610", {"register_url": REGISTER},
                         ask=lambda key: asked.append(key) or (ARCHIVE if key == "archive_url" else "none"))
        self.assertEqual(sorted(asked), ["archive_url", "recording_url"])


PAGE_DETAILS = {
    "next_date": "Thursday 19 November 2026",
    "next_date_iso": "2026-11-19",
    "next_time": "13:00 to 14:00 (London)",
    "next_theme": "Communications with your Community",
}


def fake_fetch(details, notes=()):
    calls = []

    def fetch(url, month):
        calls.append(url)
        return dict(details), list(notes)

    fetch.calls = calls
    return fetch


class ResolveAndRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blog = Path(self.tmp.name) / "blog-202610"
        si.collect_links(self.blog, "202610", LINKS)
        si.collect_authors(self.blog, ["emma-karoune"], [])

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_from_page_and_marked_for_check(self):
        data, _ = si.resolve_next_session(self.blog, "202610", {}, fake_fetch(PAGE_DETAILS))
        self.assertEqual(data["next_theme"], "Communications with your Community")
        self.assertEqual(data["next_theme_source"], si.SOURCE_PAGE)

    def test_missing_details_raise_after_saving_what_was_found(self):
        partial = {"next_date": "Thursday 19 November 2026"}
        with self.assertRaises(si.InputsError) as raised:
            si.resolve_next_session(self.blog, "202610", {}, fake_fetch(partial, ["no time found"]))
        self.assertIn("next_time, next_theme", str(raised.exception))
        self.assertIn("no time found", str(raised.exception))
        self.assertEqual(si.load(self.blog)["next_date"], "Thursday 19 November 2026")

    def test_unreadable_page_asks_for_everything(self):
        with self.assertRaises(si.InputsError) as raised:
            si.resolve_next_session(self.blog, "202610", {}, fake_fetch({}, ["robots.txt does not allow it"]))
        self.assertIn("next_date, next_time, next_theme", str(raised.exception))
        self.assertIn("robots.txt", str(raised.exception))

    def test_supplied_values_complete_the_set_without_fetching(self):
        fetch = fake_fetch({})
        supplied = {"next_date": "Thursday 19 November 2026", "next_time": "13:00", "next_theme": "Funding"}
        data, _ = si.resolve_next_session(self.blog, "202610", supplied, fetch)
        self.assertEqual(fetch.calls, [])
        self.assertEqual(data["next_theme_source"], si.SOURCE_MANUAL)

    def test_supplied_value_wins_over_page_and_is_kept_on_rerun(self):
        si.resolve_next_session(self.blog, "202610", {"next_theme": "Funding"}, fake_fetch(PAGE_DETAILS))
        data, _ = si.resolve_next_session(self.blog, "202610", {}, fake_fetch({}))
        self.assertEqual(data["next_theme"], "Funding")
        self.assertEqual(data["next_theme_source"], si.SOURCE_MANUAL)
        self.assertEqual(data["next_date_source"], si.SOURCE_PAGE)

    def test_changed_registration_link_drops_page_values(self):
        si.resolve_next_session(self.blog, "202610", {}, fake_fetch(PAGE_DETAILS))
        si.collect_links(self.blog, "202610", {"register_url": "https://us06web.zoom.us/meeting/register/other"})
        data = si.load(self.blog)
        self.assertNotIn("next_date", data)

    def test_changed_registration_link_keeps_hand_supplied_values(self):
        si.resolve_next_session(self.blog, "202610", {"next_theme": "Funding"}, fake_fetch(PAGE_DETAILS))
        si.collect_links(self.blog, "202610", {"register_url": "https://us06web.zoom.us/meeting/register/other"})
        data = si.load(self.blog)
        self.assertEqual(data["next_theme"], "Funding")

    def test_rendered_links_file(self):
        si.resolve_next_session(self.blog, "202610", {"next_hosts": "A and B"}, fake_fetch(PAGE_DETAILS))
        text = si.write_blog_links(self.blog, "202610").read_text(encoding="utf-8")
        self.assertIn("<mark>not available yet", text)
        self.assertIn(REGISTER, text)
        self.assertIn(ARCHIVE, text)
        self.assertIn("Hosted by: A and B", text)
        self.assertIn("Monthly Meetup Suggestion", text)
        self.assertIn("/Monthly-Meetups/issues", text)
        self.assertIn("read from the Zoom registration page: please check", text)

    def test_missing_details_flagged_not_blank(self):
        text = si.write_blog_links(self.blog, "202610").read_text(encoding="utf-8")
        self.assertIn("not found: please supply", text)


if __name__ == "__main__":
    unittest.main()
