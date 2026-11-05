#!/usr/bin/env python3
"""Stage 2 of the meetup blog pipeline: build a chat digest.

Inputs
    project-management/communications/blog-YYYYMM/*_anonymised.txt   from stage 1
    docs/materials-YYYYMM/*briefing*.md         the facilitators' briefing

Output
    project-management/communications/blog-YYYYMM/chat-digest.md   (same folder as the chat)

The digest is everything about the chat that can be extracted deterministically:

* the event purpose and agenda, copied verbatim from the briefing;
* the span of the chat, and message and reaction counts;
* the most-reacted messages (reaction counts come from stage 1);
* every link shared, de-duplicated, with tracking parameters removed, first
  share time, number of shares, reactions on the message that first shared it,
  a category, and a handling note (private links, such as CryptPad edit links
  and Slack invites, are flagged).

Interpretation (summarising the chat against the purpose, spotting "fun"
moments) is NOT done here. That is the one LLM step, and it reads this digest
together with the anonymised chat.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import NamedTuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DIGEST_NAME = "chat-digest.md"
ANONYMISED_SUFFIX = "_anonymised"

HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
HEADER_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\t(.+?):\t(.*)$")
REACTION_NOTE_RE = re.compile(r"\s\[\+(\d+) reactions?: ([^\]]*)\]$")
URL_RE = re.compile(r"https?://[^\s<>\"]+")
TRAILING_PUNCTUATION = ".,;:!?)]}>'\""
TRACKING_PARAMS = {"rcm", "fbclid", "gclid", "si", "mc_cid", "mc_eid"}
CONTEXT_LIMIT = 160  # characters of surrounding message text kept per link
PREVIEW_LIMIT = 120  # characters of message text shown in the reactions table
TOP_REACTED = 10     # how many most-reacted messages to list

# (pattern, category, handling). First match wins.
LINK_RULES = [
    (re.compile(r"cryptpad\.[a-z]+/.*edit", re.I), "Collaborative notes (CryptPad edit link)", "PRIVATE: never publish"),
    (re.compile(r"join\.slack\.com", re.I), "Slack invite", "PRIVATE: do not publish"),
    (re.compile(r"zoom\.us/(?:meeting|webinar)/register", re.I), "Zoom registration", "CHECK: publish only if intended"),
    (re.compile(r"zoom\.us", re.I), "Zoom link", "PRIVATE: do not publish"),
    (re.compile(r"zenodo\.org|doi\.org", re.I), "Slides / publication", "public"),
    (re.compile(r"github\.com", re.I), "GitHub", "public"),
    (re.compile(r"rcmcooperative\.com", re.I), "RCM Cooperative website", "public"),
    (re.compile(r"linkedin\.com", re.I), "LinkedIn", "public"),
    (re.compile(r"wikipedia\.org", re.I), "Reference", "public"),
]
DEFAULT_RULE = ("Other", "public")


class BriefingFormatError(Exception):
    """Raised when the briefing lacks an expected section."""


class ChatMessage(NamedTuple):
    timestamp: str
    label: str
    body: str
    reactions: int = 0
    reaction_detail: str = ""


# --------------------------------------------------------------------------
# Briefing
# --------------------------------------------------------------------------

def extract_section(lines: list[str], title_pattern: str) -> list[str] | None:
    """Lines under the first heading matching the pattern, up to the next heading."""
    pattern = re.compile(title_pattern, re.I)
    for index, line in enumerate(lines):
        heading = HEADING_RE.match(line)
        if heading and pattern.search(heading.group(1)):
            body: list[str] = []
            for following in lines[index + 1:]:
                if HEADING_RE.match(following):
                    break
                body.append(following)
            return body
    return None


def extract_purpose(briefing: str) -> str:
    lines = briefing.replace("\r\n", "\n").split("\n")
    body = extract_section(lines, r"purpose of this session")
    if body is None:
        headings = [m.group(1) for m in map(HEADING_RE.match, lines) if m]
        raise BriefingFormatError(
            "no 'Purpose of this session' heading in the briefing; "
            f"headings found: {headings or '(none)'}"
        )
    purpose = "\n".join(body).strip()
    if not purpose:
        raise BriefingFormatError("the 'Purpose of this session' section is empty")
    return purpose


def extract_agenda(briefing: str) -> list[tuple[str, str]]:
    """(time, activity) rows from the markdown table under the agenda heading."""
    lines = briefing.replace("\r\n", "\n").split("\n")
    body = extract_section(lines, r"agenda")
    if body is None:
        return []
    rows: list[tuple[str, str]] = []
    for line in body:
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set("".join(cells)) <= set("-: "):
            continue
        time, activity = cells[0].replace("**", ""), cells[1].replace("**", "")
        if time.lower() == "time" or not (time or activity):
            continue
        rows.append((time, activity))
    return rows


def extract_date(briefing: str) -> str | None:
    match = re.search(r"\*\*Date:\*\*\s*(.+)", briefing)
    return match.group(1).strip() if match else None


# --------------------------------------------------------------------------
# Chat and links
# --------------------------------------------------------------------------

@dataclass
class Link:
    url: str
    category: str
    handling: str
    first_time: str
    first_sharer: str
    context: str
    reactions: int = 0
    count: int = 1


def clean_url(url: str) -> str:
    url = url.rstrip(TRAILING_PUNCTUATION)
    parts = urlsplit(url)
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit(parts._replace(query=urlencode(query)))


def classify(url: str) -> tuple[str, str]:
    for pattern, category, handling in LINK_RULES:
        if pattern.search(url):
            return category, handling
    return DEFAULT_RULE


def parse_chat(text: str) -> list[ChatMessage]:
    """Messages from an anonymised chat, with any reaction note split off the body."""
    raw: list[list[str]] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        match = HEADER_RE.match(line)
        if match:
            raw.append([match[1], match[2], match[3]])
        elif raw:
            raw[-1][2] += "\n" + line
    messages = []
    for timestamp, label, body in raw:
        body = body.rstrip("\n")
        note = REACTION_NOTE_RE.search(body)
        if note:
            messages.append(
                ChatMessage(timestamp, label, body[:note.start()], int(note[1]), note[2])
            )
        else:
            messages.append(ChatMessage(timestamp, label, body))
    return messages


def extract_links(messages: list[ChatMessage]) -> list[Link]:
    links: dict[str, Link] = {}
    for message in messages:
        for raw in URL_RE.findall(message.body):
            url = clean_url(raw)
            if url in links:
                links[url].count += 1
                continue
            context = " ".join(URL_RE.sub("", message.body).split())
            if len(context) > CONTEXT_LIMIT:
                context = context[:CONTEXT_LIMIT].rsplit(" ", 1)[0] + "…"
            category, handling = classify(url)
            links[url] = Link(
                url, category, handling, message.timestamp, message.label,
                context, message.reactions,
            )
    return list(links.values())


def most_reacted(messages: list[ChatMessage], limit: int = TOP_REACTED) -> list[ChatMessage]:
    """Messages with reactions, most reactions first, ties in chat order."""
    reacted = [m for m in messages if m.reactions > 0]
    return sorted(reacted, key=lambda m: -m.reactions)[:limit]


# --------------------------------------------------------------------------
# Digest
# --------------------------------------------------------------------------

def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _preview(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) > PREVIEW_LIMIT:
        flat = flat[:PREVIEW_LIMIT].rsplit(" ", 1)[0] + "…"
    return flat


def build_digest(
    briefing: str,
    messages: list[ChatMessage],
    chat_name: str,
    briefing_name: str,
    month: str,
) -> str:
    purpose = extract_purpose(briefing)
    agenda = extract_agenda(briefing)
    links = extract_links(messages)
    participants = {m.label for m in messages}
    total_reactions = sum(m.reactions for m in messages)
    with_reactions = sum(1 for m in messages if m.reactions)

    out = [f"# Chat digest: {month}", ""]
    out += [
        "Generated by `chat_digest.py`. Deterministic extraction only; "
        "no interpretation.",
        "",
        "## Session",
        "",
        f"- Briefing: `{briefing_name}`",
        f"- Chat: `{chat_name}`",
    ]
    date = extract_date(briefing)
    if date:
        out.append(f"- Date (from briefing): {date}")
    if messages:
        out.append(f"- Chat span: {messages[0].timestamp} to {messages[-1].timestamp}")
    out += [
        f"- Messages: {len(messages)} from {len(participants)} participants",
        f"- Reactions: {total_reactions} on {with_reactions} messages "
        "(counts only; who reacted is not kept)",
        "",
        "## Event purpose (verbatim from briefing)",
        "",
        purpose,
        "",
    ]
    if agenda:
        out += ["## Agenda (from briefing)", ""]
        out += [f"- {time}: {activity}" for time, activity in agenda]
        out.append("")

    out += ["## Most-reacted messages", ""]
    top = most_reacted(messages)
    if top:
        out += [
            "| Time | Reactions | Breakdown | Message |",
            "|---|---|---|---|",
        ]
        for m in top:
            out.append(
                f"| {m.timestamp} | {m.reactions} | {_cell(m.reaction_detail)} "
                f"| {_cell(_preview(m.body))} |"
            )
        out.append("")
        out.append(f"Top {len(top)} shown; ties are in chat order.")
    else:
        out.append("No reactions were recorded.")
    out.append("")

    out += ["## Links shared in chat", ""]
    if links:
        out += [
            "| # | First shared | Times | Reactions | Category | Handling | URL | Context |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for number, link in enumerate(links, start=1):
            out.append(
                f"| {number} | {link.first_time} | {link.count} | {link.reactions} "
                f"| {_cell(link.category)} | {_cell(link.handling)} "
                f"| {_cell(link.url)} | {_cell(link.context)} |"
            )
        out.append("")
        out.append(
            "Reactions are those on the message that first shared the link. "
            "Tracking parameters (utm_*, rcm, fbclid and similar) are removed from URLs."
        )
    else:
        out.append("No links were shared in the chat.")
    out.append("")
    return "\n".join(out)


def find_one(directory: Path, pattern: str, what: str) -> Path:
    """First file matching a glob pattern, ignoring case (Zoom names vary)."""
    wanted = pattern.lower()
    matches = sorted(p for p in directory.iterdir() if p.is_file() and fnmatch(p.name.lower(), wanted))
    if not matches:
        present = ", ".join(sorted(p.name for p in directory.iterdir())) or "(empty)"
        raise FileNotFoundError(f"no {what} ({pattern}) in {directory}; found: {present}")
    return matches[0]


def run(blog_dir: Path, docs_dir: Path) -> list[Path]:
    """Pipeline stage entrypoint. Reads the anonymised chat in ``blog_dir``, writes chat-digest.md there."""
    month = blog_dir.name.removeprefix("blog-")
    chat = find_one(blog_dir, f"*chat*{ANONYMISED_SUFFIX}.txt", "anonymised chat (run stage 1)")
    briefing = find_one(docs_dir, "*briefing*.md", "facilitators briefing")
    digest = build_digest(
        briefing.read_text(encoding="utf-8-sig"),
        parse_chat(chat.read_text(encoding="utf-8-sig")),
        chat.name,
        briefing.name,
        month,
    )
    blog_dir.mkdir(parents=True, exist_ok=True)
    output = blog_dir / DIGEST_NAME
    output.write_text(digest, encoding="utf-8")
    return [output]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the chat digest.")
    parser.add_argument("blog_dir", type=Path, help="e.g. project-management/communications/blog-202610")
    parser.add_argument("docs_dir", type=Path, help="e.g. docs/materials-202610")
    args = parser.parse_args(argv)
    try:
        for path in run(args.blog_dir, args.docs_dir):
            print(f"wrote {path}")
    except (BriefingFormatError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
