"""Tests for reading the next session from its registration page. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v

No test touches the network: the page reader is given a fake opener.
"""

import io
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import next_session_page as nsp  # noqa: E402

URL = "https://us06web.zoom.us/meeting/register/abc123"

PAGE = """<html><head>
<title>Register for RCM Cooperative Monthly Meetup - November 2026</title>
<meta property="og:description" content="Join us on Thursday, November 19, 2026 at 1:00 PM - 2:00 PM London.
We’ll be exploring Communications with your Community, hosted by two of us.">
<script>var x = "Oct 3, 2020 9:00 AM";</script>
</head><body><p>Register now</p></body></html>"""


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def opener(robots=b"User-agent: *\nAllow: /\n", page=PAGE.encode(), robots_error=None, page_error=None):
    calls = []

    def open_url(request, timeout=None):
        url = request.full_url
        calls.append(url)
        if url.endswith("/robots.txt"):
            if robots_error:
                raise robots_error
            return Response(robots)
        if page_error:
            raise page_error
        return Response(page)

    open_url.calls = calls
    return open_url


class ParseTests(unittest.TestCase):
    def test_date_time_theme(self):
        details, notes = nsp.parse_page(PAGE, "202610")
        self.assertEqual(details["next_date"], "Thursday 19 November 2026")
        self.assertEqual(details["next_date_iso"], "2026-11-19")
        self.assertEqual(details["next_time"], "13:00 to 14:00 (London)")
        self.assertEqual(details["next_theme"], "Communications with your Community")
        self.assertEqual(notes, [])

    def test_script_text_ignored(self):
        details, _ = nsp.parse_page(PAGE, "202610")
        self.assertNotIn("2020", details["next_date"])

    def test_day_month_year_and_24_hour(self):
        page = "<body>Thursday 19th November 2026, 13:00 - 14:00 (UK time)</body>"
        details, _ = nsp.parse_page(page, "202610")
        self.assertEqual(details["next_date"], "Thursday 19 November 2026")
        self.assertEqual(details["next_time"], "13:00 to 14:00 (UK time)")

    def test_weekday_comes_from_the_date_not_the_page(self):
        details, _ = nsp.parse_page("<body>Friday 19 November 2026 13:00</body>", "202610")
        self.assertEqual(details["next_date"], "Thursday 19 November 2026")

    def test_time_without_zone_noted(self):
        details, notes = nsp.parse_page("<body>19 November 2026 at 13:00</body>", "202610")
        self.assertEqual(details["next_time"], "13:00")
        self.assertTrue(any("no time zone" in n for n in notes))

    def test_date_before_the_meetup_month_rejected(self):
        details, notes = nsp.parse_page("<body>3 March 2025 at 13:00</body>", "202610")
        self.assertNotIn("next_date", details)
        self.assertTrue(any("before the meetup month" in n for n in notes))

    def test_page_without_details(self):
        details, _ = nsp.parse_page("<body>Loading...</body>", "202610")
        self.assertEqual(details, {})

    def test_pm_conversion(self):
        self.assertEqual(nsp.to_24h("12", "30", "a"), "00:30")
        self.assertEqual(nsp.to_24h("12", "30", "p"), "12:30")
        self.assertEqual(nsp.to_24h("1", "05", "P"), "13:05")
        self.assertIsNone(nsp.to_24h("25", "00", None))


class FetchTests(unittest.TestCase):
    def test_reads_the_page_when_robots_allows(self):
        details, notes = nsp.fetch_details(URL, "202610", opener())
        self.assertEqual(details["next_date"], "Thursday 19 November 2026")

    def test_robots_checked_before_the_page(self):
        open_url = opener()
        nsp.fetch_details(URL, "202610", open_url)
        self.assertTrue(open_url.calls[0].endswith("/robots.txt"))
        self.assertEqual(len(open_url.calls), 2)

    def test_disallowed_page_is_not_fetched(self):
        open_url = opener(robots=b"User-agent: *\nDisallow: /\n")
        details, notes = nsp.fetch_details(URL, "202610", open_url)
        self.assertEqual(details, {})
        self.assertIn("robots.txt does not allow", notes[0])
        self.assertEqual(len(open_url.calls), 1)

    def test_robots_refused_counts_as_not_allowed(self):
        error = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        details, notes = nsp.fetch_details(URL, "202610", opener(robots_error=error))
        self.assertEqual(details, {})
        self.assertIn("403", notes[0])

    def test_no_robots_file_means_allowed(self):
        error = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        details, _ = nsp.fetch_details(URL, "202610", opener(robots_error=error))
        self.assertIn("next_date", details)

    def test_unreachable_site_reported(self):
        details, notes = nsp.fetch_details(URL, "202610", opener(robots_error=urllib.error.URLError("no route")))
        self.assertEqual(details, {})
        self.assertIn("could not reach", notes[0])

    def test_page_error_reported(self):
        error = urllib.error.HTTPError("u", 500, "Oops", {}, None)
        details, notes = nsp.fetch_details(URL, "202610", opener(page_error=error))
        self.assertEqual(details, {})
        self.assertIn("HTTP 500", notes[0])

    def test_missing_parts_explained(self):
        page = b"<body>Register for the meetup</body>"
        details, notes = nsp.fetch_details(URL, "202610", opener(page=page))
        self.assertEqual(details, {})
        self.assertEqual(len(notes), 3)


if __name__ == "__main__":
    unittest.main()
