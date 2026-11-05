"""Links, authors and next-session details that go into the blog but are not
in the meetup's source material.

Everything is saved in ``project-management/communications/blog-YYYYMM/session-inputs.json``, so each
answer is asked for once.

* ``collect_links`` takes the three links the facilitator supplies each month:
  the registration link for the next session, the published call recording and
  the published materials archive. The recording is often not ready yet, which
  is a valid answer (``none``).
* ``collect_authors`` takes the authors as their file names in the website's
  ``_team`` folder (the skill points the person to it); an author who is not on
  the team is given as a name and link.
* ``resolve_next_session`` gets the date, time and theme of the next session
  from its Zoom registration page (``next_session_page``). If the page cannot be
  read, or does not show something, the missing details are reported and the
  person supplies them. Anything read from the page is marked as needing a
  check; a value given on the command line wins.

``write_blog_links`` then renders ``blog-links.md``: the front matter authors,
the host and speaker sentence (names linked, read from ``comms-copy.md`` by
``comms_copy.py``) and the "Join us next time" material. The two fixed GitHub
links (review progress on future sessions, propose a session) come from
``config.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import config
import next_session_page
from next_session_page import MONTHS, WEEKDAYS  # noqa: F401  (re-exported)

INPUTS_NAME = "session-inputs.json"
LINKS_NAME = "blog-links.md"
NOT_AVAILABLE = "none"
SOURCE_PAGE = "Zoom registration page (check)"
SOURCE_MANUAL = "supplied by facilitator"

LINK_KEYS = ("register_url", "recording_url", "archive_url")
NEXT_KEYS = ("next_date", "next_time", "next_theme")

class InputsError(ValueError):
    pass


TEAM_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


# ---------------------------------------------------------------- file ----

def inputs_path(blog_dir: Path) -> Path:
    return blog_dir / INPUTS_NAME


def load(blog_dir: Path) -> dict:
    path = inputs_path(blog_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InputsError(f"{path} is not valid JSON: {error}") from None


def save(blog_dir: Path, data: dict) -> Path:
    blog_dir.mkdir(parents=True, exist_ok=True)
    path = inputs_path(blog_dir)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------------ validation --

def clean_link(value: str) -> str:
    return value.strip()


def validate_link(key: str, value: str, month: str) -> list[str]:
    """Return warnings for a link; raise InputsError if it is not a web link."""
    if key == "recording_url" and value.lower() == NOT_AVAILABLE:
        return []
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise InputsError(f"{key}: '{value}' is not an https link")
    warnings: list[str] = []
    host = parsed.netloc.lower()
    if key == "register_url" and not (host == "zoom.us" or host.endswith(".zoom.us")):
        warnings.append(f"register_url is not a zoom.us link ({host})")
    if key == "register_url" and "/register/" not in parsed.path:
        warnings.append("register_url does not look like a Zoom registration link")
    if key == "archive_url":
        if host != "github.com":
            warnings.append(f"archive_url is not a github.com link ({host})")
        if not parsed.path.rstrip("/").endswith(f"materials-{month}"):
            warnings.append(f"archive_url does not end in materials-{month}")
    return warnings


# ------------------------------------------------------------- collection --

def collect_links(blog_dir: Path, month: str, supplied: dict, ask=None) -> tuple[dict, list[str]]:
    """Merge links (command line > saved file > prompt) and save them.

    ``supplied`` maps link keys to values (None when not given). ``ask`` is a
    callable (key) -> str used for anything still missing, or None when not
    interactive. Raises InputsError listing every missing link.
    """
    data = load(blog_dir)
    warnings: list[str] = []
    missing: list[str] = []
    for key in LINK_KEYS:
        value = supplied.get(key)
        if value is not None:
            if key == "register_url" and data.get(key) not in (None, clean_link(value)):
                for next_key in NEXT_KEYS:  # values read for the old link no longer apply
                    if data.get(next_key + "_source") == SOURCE_PAGE:
                        data.pop(next_key, None)
                        data.pop(next_key + "_source", None)
            data[key] = clean_link(value)
            data[key + "_source"] = SOURCE_MANUAL
        elif key not in data and ask is not None:
            data[key] = clean_link(ask(key))
            data[key + "_source"] = SOURCE_MANUAL
        if key not in data or not data[key]:
            missing.append(key)
            continue
        warnings += [f"{key}: {w}" for w in validate_link(key, data[key], month)]
    if missing:
        raise InputsError("missing: " + ", ".join(missing))
    save(blog_dir, data)
    return data, warnings


# ----------------------------------------------------------------- authors --

def clean_team_slug(text: str) -> str:
    """A team author is the file name in the website's _team folder, without .md."""
    slug = text.strip()
    if slug.lower().endswith(".md"):
        slug = slug[:-3]
    if not TEAM_SLUG_RE.match(slug):
        raise InputsError(
            f"team author '{text}' should be the file name in _team without .md "
            f"(for example emma-karoune), not a full name. See {config.TEAM_DIR_URL}"
        )
    return slug


def parse_external_author(text: str) -> dict:
    """An author who is not on the team: 'Name|https://link'."""
    name, sep, url = text.partition("|")
    name, url = name.strip(), url.strip()
    if not sep or not name or not url:
        raise InputsError(f"external author '{text}': give it as 'Name|https://link'")
    if urlparse(url).scheme != "https" or not urlparse(url).netloc:
        raise InputsError(f"external author '{name}': '{url}' is not an https link")
    return {"name": name, "url": url}


def collect_authors(blog_dir: Path, team: list[str], external: list[str], ask=None) -> dict:
    """Authors (command line > saved file > prompt), saved in the inputs file.

    ``ask`` is a callable () -> (team_slugs, external_texts) or None. Supplying
    any author on the command line replaces the saved list.
    """
    data = load(blog_dir)
    if not team and not external and not data.get("authors") and ask is not None:
        team, external = ask()
    if team or external:
        authors: list[dict] = []
        seen: set[str] = set()
        for slug in (clean_team_slug(t) for t in team):
            if slug.lower() not in seen:
                seen.add(slug.lower())
                authors.append({"team": slug})
        authors += [parse_external_author(e) for e in external]
        data["authors"] = authors
        data["authors_source"] = SOURCE_MANUAL
    if not data.get("authors"):
        raise InputsError("missing: authors")
    save(blog_dir, data)
    return data


def render_authors(data: dict) -> str:
    lines = ["authors:"]
    for author in data["authors"]:
        if "team" in author:
            lines.append(f"  - team: {author['team']}")
        else:
            lines += [f"  - name: \"{author['name']}\"", f"    url: {author['url']}"]
    return "\n".join(lines)


# ------------------------------------------------------ next-session facts --

def resolve_next_session(blog_dir: Path, month: str, supplied: dict, fetch=None) -> tuple[dict, list[str]]:
    """Fill the next session's date, time and theme.

    Command-line values win, then values saved earlier. Anything still missing is
    read from the registration page by ``fetch`` (default: the real page reader).
    Raises InputsError, after saving what was found, if any detail is still
    missing, so the person can be asked for exactly those.
    """
    data = load(blog_dir)
    if not data.get("register_url"):
        raise InputsError("register_url not set; collect the links first")
    for key in (*NEXT_KEYS, "next_hosts"):
        if supplied.get(key):
            data[key] = supplied[key].strip()
            data[key + "_source"] = SOURCE_MANUAL
    notes: list[str] = []
    if [k for k in NEXT_KEYS if not data.get(k)]:
        reader = fetch or next_session_page.fetch_details
        details, notes = reader(data["register_url"], month)
        for key in NEXT_KEYS:
            if not data.get(key) and details.get(key):
                data[key] = details[key]
                data[key + "_source"] = SOURCE_PAGE
        if details.get("next_date_iso") and data.get("next_date_source") == SOURCE_PAGE:
            data["next_date_iso"] = details["next_date_iso"]
    save(blog_dir, data)
    still_missing = [k for k in NEXT_KEYS if not data.get(k)]
    if still_missing:
        why = f" ({'; '.join(notes)})" if notes else ""
        raise InputsError("missing: " + ", ".join(still_missing) + why)
    return data, notes


# ------------------------------------------------------------------ render --

def describe(data: dict, key: str) -> str:
    value = data.get(key)
    if not value:
        return "<mark>not found: please supply</mark>"
    if data.get(key + "_source") == SOURCE_PAGE:
        return f"{value} <mark>(read from the Zoom registration page: please check)</mark>"
    return value


def join_links(people: list[dict]) -> str:
    links = [f"[{p['name']}]({p['url']})" for p in people]
    if len(links) <= 1:
        return "".join(links)
    return ", ".join(links[:-1]) + " and " + links[-1]


def people_sentence(data: dict) -> str:
    hosts, speakers = data.get("hosts", []), data.get("speakers", [])
    if not hosts and not speakers:
        return "<mark>host and speaker not found: add comms-copy.md to the docs folder</mark>"
    if hosts:
        sentence = f"This session was hosted by {join_links(hosts)}"
        if speakers:
            sentence += f" and featured a presentation from {join_links(speakers)}"
    else:
        sentence = f"This session featured a presentation from {join_links(speakers)}"
    return sentence + "."


def render_links(data: dict, month: str) -> str:
    issues = config.ISSUES_URL
    out = ["# Links and details for the post", "",
           "*Generated from `session-inputs.json`. Items in highlight need a check.*", ""]

    out += ["## Front matter: authors", "", "```yaml", render_authors(data), "```", ""]
    if any("team" not in a for a in data["authors"]):
        out += ["<mark>Authors who are not on the team are written as name and url. "
                "Check this matches how an existing post credits an outside author.</mark>", ""]

    out += ["## About this session", ""]
    if data.get("theme"):
        out.append(f"- Theme: {data['theme']}")
    if data.get("theme_description"):
        out.append(f"- Invitation text: {data['theme_description']}")
    out += ["", "## Host and speaker", "", people_sentence(data), ""]

    out += ["## Recording and materials", ""]
    if data["recording_url"].lower() == NOT_AVAILABLE:
        out.append("- Call recording: <mark>not available yet: add the link when published</mark>")
    else:
        out.append(f"- Call recording: {data['recording_url']}")
    out += [f"- Materials archive: {data['archive_url']}", ""]

    out += ["## Join us next time", ""]
    out.append(f"- Theme: {describe(data, 'next_theme')}")
    out.append(f"- Date: {describe(data, 'next_date')}")
    out.append(f"- Time: {describe(data, 'next_time')}")
    if data.get("next_hosts"):
        out.append(f"- Hosted by: {data['next_hosts']}")
    out.append(f"- Register: {data['register_url']}")
    out += ["",
            "### Help shape future sessions", "",
            f"- Follow our progress in organising future sessions on the [Monthly Meetups issues]({issues}).",
            f"- Propose a session by [submitting an issue]({issues}) "
            f"using the \"{config.SUGGESTION_TEMPLATE}\" issue template.", ""]
    return "\n".join(out)


def write_blog_links(blog_dir: Path, month: str) -> Path:
    data = load(blog_dir)
    missing = [k for k in (*LINK_KEYS, "authors") if not data.get(k)]
    if missing:
        raise InputsError("missing: " + ", ".join(missing))
    path = blog_dir / LINKS_NAME
    path.write_text(render_links(data, month), encoding="utf-8")
    return path
