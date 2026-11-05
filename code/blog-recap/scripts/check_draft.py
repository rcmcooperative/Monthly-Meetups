"""Final checks on the drafted post, before it goes to the website repo.

Reads ``project-management/communications/blog-YYYYMM/mm-recap-YYYYMM.md`` and reports:

problems (always fail)
    * template notes or guidance comments left in the draft
    * ``{{PLACEHOLDER}}`` text not filled in (the header image ones are held
      back until the very end: see ``image`` below)
    * missing front matter keys
    * room numbers, ``Participant NN`` labels or ``[name]`` markers
    * a CryptPad or Slack invite link
    * the name or email address of a registrant who is not the host, speaker or
      an author (read from the registration report; nothing is written out)

to-dos (fail only with --final)
    * ``<mark>`` highlights still in the draft

image (fail only with --final)
    * the header image filename and alt text not yet filled in
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import config
import registration_count
import session_inputs

DRAFT_TEMPLATE = "mm-recap-{month}.md"
FRONT_KEYS = ("title", "date", "image", "alt", "excerpt", "authors")
IMAGE_PLACEHOLDERS = {"IMAGE_SLUG", "IMAGE_ALT"}

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")
ROOM_RE = re.compile(r"\b[Rr]ooms?\s+\d+\b")
LABEL_RE = re.compile(r"\bParticipant\s+\d{2}\b|\[name\]")
PRIVATE_LINK_RE = re.compile(r"https?://\S*(?:cryptpad|join\.slack\.com|shared_invite)\S*", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@dataclass
class Finding:
    level: str  # "problem", "todo" or "image"
    line: int
    message: str


def draft_path(blog_dir: Path, month: str) -> Path:
    return blog_dir / DRAFT_TEMPLATE.format(month=month)


def line_of(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def registrants(private_dir: Path) -> list[dict]:
    """First name, last name and email of each registrant (kept in memory only)."""
    report = registration_count.find_report(private_dir)
    if report is None:
        return []
    with report.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    for index, row in enumerate(rows):
        if "First Name" in row and "Last Name" in row:
            header = row
            first, last = header.index("First Name"), header.index("Last Name")
            email = header.index("Email") if "Email" in header else None
            people = []
            for record in rows[index + 1:]:
                if len(record) > max(first, last) and (record[first].strip() or record[last].strip()):
                    people.append({
                        "first": record[first].strip(),
                        "last": record[last].strip(),
                        "email": record[email].strip().lower() if email is not None and len(record) > email else "",
                    })
            return people
    return []


def allowed_tokens(data: dict) -> set[str]:
    """Lower-case name parts that may appear: team, hosts, speakers and authors."""
    names = list(config.ALLOWED_NAMES)
    names += [p["name"] for p in data.get("hosts", []) + data.get("speakers", [])]
    names += [a["name"] for a in data.get("authors", []) if "name" in a]
    tokens: set[str] = set()
    for name in names:
        tokens.update(re.split(r"[\s-]+", name.lower()))
        tokens.add(name.lower().split()[-1].replace(" ", ""))
        tokens.add("".join(name.lower().split()[1:]))
    for author in data.get("authors", []):
        if "team" in author:
            tokens.update(author["team"].lower().split("-"))
    return {t for t in tokens if t}


def is_allowed(person: dict, tokens: set[str]) -> bool:
    first = person["first"].lower()
    last = person["last"].lower().replace(" ", "")
    return first in tokens and last in tokens


def check_text(text: str, people: list[dict], data: dict) -> list[Finding]:
    findings: list[Finding] = []

    for match in COMMENT_RE.finditer(text):
        label = "template notes" if "TEMPLATE NOTES" in match.group() else "a template comment"
        findings.append(Finding("problem", line_of(text, match.start()), f"{label} is still in the draft"))
    body = COMMENT_RE.sub(lambda m: "\n" * m.group().count("\n"), text)

    for match in PLACEHOLDER_RE.finditer(body):
        level = "image" if match.group(1) in IMAGE_PLACEHOLDERS else "problem"
        findings.append(Finding(level, line_of(body, match.start()), f"{{{{{match.group(1)}}}}} is not filled in"))

    front = re.match(r"---\n(.*?)\n---", body, re.DOTALL)
    if not front:
        findings.append(Finding("problem", 1, "no front matter at the top of the draft"))
    else:
        for key in FRONT_KEYS:
            if not re.search(rf"^{key}:", front.group(1), re.MULTILINE):
                findings.append(Finding("problem", 1, f"front matter has no '{key}:'"))

    for pattern, message in (
        (ROOM_RE, "mentions a room number: write 'in small groups' instead"),
        (LABEL_RE, "contains an anonymisation label"),
        (PRIVATE_LINK_RE, "links to a private CryptPad or Slack invite"),
    ):
        for match in pattern.finditer(body):
            findings.append(Finding("problem", line_of(body, match.start()), f"{message}: '{match.group().strip()}'"))

    tokens = allowed_tokens(data)
    emails = {p["email"] for p in people if p["email"] and not is_allowed(p, tokens)}
    for match in EMAIL_RE.finditer(body):
        if match.group().lower() in emails:
            findings.append(Finding("problem", line_of(body, match.start()), "contains a registrant's email address"))
    for person in people:
        if is_allowed(person, tokens):
            continue
        full = re.compile(rf"\b{re.escape(person['first'])}\s+{re.escape(person['last'])}\b", re.IGNORECASE) if person["first"] and person["last"] else None
        surname = re.compile(rf"\b{re.escape(person['last'])}\b") if len(person["last"]) >= 5 else None
        for pattern in (full, surname):
            if pattern is None:
                continue
            match = pattern.search(body)
            if match:
                findings.append(Finding(
                    "problem", line_of(body, match.start()),
                    "contains the name of a registrant who is not the host, speaker or an author "
                    "(the name is not shown here: look at this line)",
                ))
                break

    for match in re.finditer(r"<mark>", body):
        findings.append(Finding("todo", line_of(body, match.start()), "a <mark> highlight is still in the draft"))
    return findings


def run(blog_dir: Path, private_dir: Path, month: str) -> tuple[Path, list[Finding]] | None:
    """Check the draft; None if there is no draft yet."""
    path = draft_path(blog_dir, month)
    if not path.exists():
        return None
    data = session_inputs.load(blog_dir)
    findings = check_text(path.read_text(encoding="utf-8"), registrants(private_dir), data)
    return path, findings


def exit_code(findings: list[Finding], final: bool) -> int:
    failing = {"problem"} | ({"todo", "image"} if final else set())
    return 1 if any(f.level in failing for f in findings) else 0
