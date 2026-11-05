"""Date, time and theme of the next session, read from its Zoom registration page.

``fetch_details`` tries to read the page. It is polite about it: it reads the
site's ``robots.txt`` first and does not fetch anything the site disallows,
identifies itself with a generic client name, and makes one request. Zoom
builds much of its registration page with scripts and may refuse automated
clients, so failure is expected and normal. Whatever cannot be read is
reported, and the caller then asks the person for it.

Nothing here is trusted: every value read from the page is marked "check" and
shown to the person before it goes into the post.
"""

from __future__ import annotations

import datetime
import html.parser
import re
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urlparse

USER_AGENT = "blog-recap/1.0 (meetup blog pipeline)"
TIMEOUT = 10

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

MONTH_LOOKUP = {name.lower(): number for number, name in enumerate(MONTHS, 1)}
MONTH_LOOKUP.update({name[:3].lower(): number for number, name in enumerate(MONTHS, 1)})
MONTH_LOOKUP["sept"] = 9

DATE_MDY = re.compile(r"\b(?P<month>[A-Za-z]{3,9})\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<year>\d{4})\b")
DATE_DMY = re.compile(r"\b(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>[A-Za-z]{3,9})\.?,?\s+(?P<year>\d{4})\b")
TIME_RE = re.compile(r"\b(?P<hour>\d{1,2}):(?P<minute>\d{2})(?:\s*(?P<ampm>[AaPp])\.?[Mm]\.?)?")
TIME_TAIL_RE = re.compile(
    r"^\s*(?:-|–|—|to)\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})(?:\s*(?P<ampm>[AaPp])\.?[Mm]\.?)?",
    re.IGNORECASE,
)
ZONE_RE = re.compile(r"\b(?:GMT|BST|UTC|CET|CEST)(?:[+-]\d{1,2})?\b|\bLondon\b|\bUK time\b", re.IGNORECASE)
THEME_RE = re.compile(
    r"(?:\btheme\s*[:\-]\s*|\bexploring\s+)(?P<theme>.+?)"
    r"(?:\s*,?\s*hosted by|\s+Register\b|[.!]\s|$)",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ fetching --

def robots_allows(url: str, open_url=urllib.request.urlopen, timeout: int = TIMEOUT) -> tuple[bool, str]:
    """(allowed, reason). A site that cannot be reached counts as not allowed."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    try:
        request = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        with open_url(request, timeout=timeout) as response:
            parser.parse(response.read().decode("utf-8", "replace").splitlines())
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False, f"{parsed.netloc} refused the request for its robots.txt (HTTP {error.code})"
        parser.parse([])  # no robots.txt: nothing is disallowed
    except (urllib.error.URLError, OSError) as error:
        return False, f"could not reach {parsed.netloc}: {getattr(error, 'reason', error)}"
    if not parser.can_fetch(USER_AGENT, url):
        return False, f"{parsed.netloc}'s robots.txt does not allow automated access to this page"
    return True, ""


def fetch(url: str, open_url=urllib.request.urlopen, timeout: int = TIMEOUT) -> tuple[str | None, str]:
    """(page text, reason). The text is None when the page could not be read."""
    allowed, reason = robots_allows(url, open_url, timeout)
    if not allowed:
        return None, reason
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with open_url(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace"), ""
    except urllib.error.HTTPError as error:
        return None, f"the page returned HTTP {error.code}"
    except (urllib.error.URLError, OSError) as error:
        return None, f"could not read the page: {getattr(error, 'reason', error)}"


# ------------------------------------------------------------------- parsing --

class _PageText(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.chunks: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            if key and attributes.get("content"):
                self.meta[key] = attributes["content"]

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        else:
            self.chunks.append(data)


def to_24h(hour: str, minute: str, ampm: str | None) -> str | None:
    h, m = int(hour), int(minute)
    if ampm:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ampm.lower() == "p" else 0)
    if h > 23 or m > 59:
        return None
    return f"{h:02d}:{m:02d}"


def find_date(text: str) -> tuple[datetime.date, int] | None:
    """The first calendar date in the text, and where it ends."""
    found = []
    for pattern in (DATE_MDY, DATE_DMY):
        for match in pattern.finditer(text):
            month = MONTH_LOOKUP.get(match["month"].lower())
            if not month:
                continue
            try:
                found.append((match.start(), datetime.date(int(match["year"]), month, int(match["day"])), match.end()))
            except ValueError:
                continue
    if not found:
        return None
    _, date, end = min(found)
    return date, end


def find_time(text: str, start: int) -> str | None:
    """A time (or range) near ``start``, in 24-hour form, with the zone if one is named."""
    match = TIME_RE.search(text, start, start + 200) or TIME_RE.search(text)
    if not match:
        return None
    first = to_24h(match["hour"], match["minute"], match["ampm"])
    if not first:
        return None
    result = first
    tail = TIME_TAIL_RE.match(text[match.end():])
    end_position = match.end()
    if tail:
        second = to_24h(tail["hour"], tail["minute"], tail["ampm"])
        if second:
            result = f"{first} to {second}"
            end_position += tail.end()
    zone = ZONE_RE.search(text, end_position, end_position + 80)
    return f"{result} ({zone.group(0)})" if zone else result


def parse_page(page: str, month: str) -> tuple[dict, list[str]]:
    """Details found in a page, and notes about anything doubtful."""
    reader = _PageText()
    reader.feed(page)
    meta_text = " ".join(reader.meta.get(k, "") for k in
                         ("og:title", "og:description", "description", "twitter:description"))
    text = re.sub(r"\s+", " ", " ".join([reader.title, meta_text, *reader.chunks])).strip()
    details: dict = {}
    notes: list[str] = []

    located = find_date(text)
    if located:
        date, end = located
        meeting_start = datetime.date(int(month[:4]), int(month[4:]), 1)
        if date < meeting_start:
            notes.append(f"the page shows {date.isoformat()}, which is before the meetup month")
        else:
            details["next_date"] = f"{WEEKDAYS[date.weekday()]} {date.day} {MONTHS[date.month - 1]} {date.year}"
            details["next_date_iso"] = date.isoformat()
        time_text = find_time(text, end)
        if time_text:
            details["next_time"] = time_text
            if "(" not in time_text:
                notes.append("the page shows a time but no time zone")
    theme = THEME_RE.search(text)
    if theme:
        details["next_theme"] = theme["theme"].strip().rstrip(",.")
    return details, notes


def fetch_details(url: str, month: str, open_url=urllib.request.urlopen) -> tuple[dict, list[str]]:
    """Read the next session's details from its registration page.

    Returns (details, notes). ``details`` may hold next_date, next_date_iso,
    next_time and next_theme; ``notes`` explain what could not be read.
    """
    page, reason = fetch(url, open_url)
    if page is None:
        return {}, [reason]
    details, notes = parse_page(page, month)
    for key, label in (("next_date", "date"), ("next_time", "time"), ("next_theme", "theme")):
        if key not in details:
            notes.append(f"no {label} found on the page (Zoom builds much of it with scripts)")
    return details, notes
