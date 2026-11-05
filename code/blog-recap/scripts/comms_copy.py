r"""Stage 7: host, speaker and theme of the session, from the comms copy.

Reads ``docs/materials-YYYYMM/comms-copy.md`` (the invitation drafted before the
session) and adds the people to ``project-management/communications/blog-YYYYMM/session-inputs.json``.

Only the "Speaker" and "Host" lists are used. Each entry is a markdown link
(name and profile page) followed by a role, for example::

    **Speaker**

    - **\[Name\](https://example.org/person)**, Community Manager, Some Institute

Email addresses elsewhere in the copy are ignored. The session theme and the
sentence that follows it are kept for the "About this session" notes.
"""

from __future__ import annotations

import re
from pathlib import Path

import session_inputs

COMMS_NAME = "comms-copy.md"
SOURCE = "comms-copy.md"

SECTION_RE = re.compile(r"^\*\*(?P<kind>Speakers?|Hosts?)\*\*\s*$", re.IGNORECASE)
PERSON_RE = re.compile(r"\*\*\\?\[(?P<name>[^\]\\]+)\\?\]\((?P<url>https?://[^)\s]+)\)")
THEME_RE = re.compile(r"^\*\*This month\S{0,3}s theme:\s*(?P<theme>.+?)\*\*\s*$", re.IGNORECASE)
WHEN_RE = re.compile(r"^\*\*When:\s*(?P<when>.+?)\*\*\s*$", re.IGNORECASE)


class CommsCopyError(ValueError):
    pass


def parse_person(line: str) -> dict | None:
    match = PERSON_RE.search(line)
    if not match:
        return None
    role = line[match.end():].strip(" *,\t")
    return {"name": match["name"].strip(), "url": match["url"], "role": role}


def parse_comms(text: str) -> dict:
    lines = text.split("\n")
    found: dict = {"hosts": [], "speakers": []}
    section = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# "):
            section = None
            if found.get("theme") and (found["hosts"] or found["speakers"]):
                break  # later headings are other channels (Slack, LinkedIn)
            continue
        heading = SECTION_RE.match(stripped)
        if heading:
            section = "speakers" if heading["kind"].lower().startswith("speaker") else "hosts"
            continue
        if stripped.startswith("- ") and section:
            person = parse_person(stripped)
            if person:
                found[section].append(person)
            continue
        if stripped and not stripped.startswith("-"):
            section = None
        theme = THEME_RE.match(stripped)
        if theme and "theme" not in found:
            found["theme"] = theme["theme"].strip()
            for follower in lines[index + 1:]:
                if follower.strip():
                    found["theme_description"] = re.sub(r"\s+", " ", follower.strip())
                    break
        when = WHEN_RE.match(stripped)
        if when and "when" not in found:
            found["when"] = when["when"].strip()
    return found


def check_month(when: str | None, month: str) -> str | None:
    """A note if the invitation's date is not in the meetup month."""
    if not when:
        return None
    month_name = session_inputs.MONTHS[int(month[4:]) - 1]
    if month_name.lower() in when.lower() and month[:4] in when:
        return None
    return f"the invitation says '{when}', which is not {month_name} {month[:4]}"


def run(docs_dir: Path, blog_dir: Path, month: str) -> tuple[dict, list[str]] | None:
    """Add people and theme to session-inputs.json; None if there is no comms copy."""
    source = docs_dir / COMMS_NAME
    if not source.exists():
        return None
    found = parse_comms(source.read_text(encoding="utf-8"))
    notes: list[str] = []
    if not found["hosts"] and not found["speakers"]:
        raise CommsCopyError(
            f"no Speaker or Host list found in {source.name} "
            "(expected '**Speaker**' / '**Host**' followed by '- **\\[Name\\](link)**, role')"
        )
    if not found["hosts"]:
        notes.append("no host found in the comms copy")
    if not found["speakers"]:
        notes.append("no speaker found in the comms copy")
    note = check_month(found.get("when"), month)
    if note:
        notes.append(note)
    data = session_inputs.load(blog_dir)
    for key in ("hosts", "speakers", "theme", "theme_description"):
        if found.get(key):
            data[key] = found[key]
    data["people_source"] = SOURCE
    session_inputs.save(blog_dir, data)
    return found, notes
