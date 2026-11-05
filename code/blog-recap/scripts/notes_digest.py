#!/usr/bin/env python3
"""Stage 3 of the meetup blog pipeline: build a digest of the collaborative notes.

Inputs
    docs/materials-YYYYMM/*collab*notes*.md    the archived collaborative notes

Output
    project-management/communications/blog-YYYYMM/notes-digest.md

Deterministic extraction only. The digest contains:

* the exercise instructions, verbatim from the notes;
* anything written before the breakouts (icebreaker, speaker introduction);
* for each breakout room: the speaker's story notes (one block per note-taker),
  any reflection, and the collaborative story, each as written;
* a completeness table (note-takers, word counts, reflection recorded).

What it removes: the attendee list, the privacy notice and the markdown help
text. Names are removed throughout: every name on the attendee list, every
name used in a speaker or note-taker heading, and any ``EXTRA_NAMES`` from
config.py become ``[name]``. Note-takers become "Note-taker N". URLs are left
alone. The digest is self-checked for leaked names.

Interpretation (themes, comparison with the exercise brief and event purpose)
is NOT done here. That is the LLM step, and it reads this digest.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import chat_digest
import exercise_tasks
from anonymise_chat import MIN_TOKEN_LENGTH, NAME_PARTICLES, NAME_PLACEHOLDER, URL_RE, WORD_RE

DIGEST_NAME = "notes-digest.md"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
ROOM_RE = re.compile(r"^Breakout Room\s+(\d+)\b", re.I)
SPEAKER_RE = re.compile(r"^\s*[-*]?\s*Speaker:\s*(.*)$", re.I)
REFLECTION_RE = re.compile(r"^\s*Reflection:?\s*$", re.I)
THEME_RE = re.compile(r"^#\s*Theme title:\s*(.+?)\s*$", re.M | re.I)
EMPTY_BULLET_RE = re.compile(r"^\s*[-*]\s*$")
NAME_RUN_RE = re.compile(re.escape(NAME_PLACEHOLDER) + r"(?:\s+" + re.escape(NAME_PLACEHOLDER) + r")+")
SKIP_NAME_WORDS = {"everyone", "all", "tbc", "notes", "speaker"}


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

@dataclass
class Block:
    kind: str  # "notes", "story" or "other"
    title: str
    lines: list[str] = field(default_factory=list)


@dataclass
class Room:
    number: int
    speaker: str = ""
    room_lines: list[str] = field(default_factory=list)  # before the first ##### block
    blocks: list[Block] = field(default_factory=list)


@dataclass
class NotesDoc:
    theme: str | None
    attendee_names: list[str]
    exercises: list[str]
    before: list[str]
    rooms: list[Room]
    after: list[str]


def _block_kind(title: str) -> str:
    lowered = title.lower()
    if lowered.startswith("collaborative"):
        return "story"
    if lowered.startswith("note"):
        return "notes"
    return "other"


def extract_attendee_names(lines: list[str]) -> list[str]:
    body = chat_digest.extract_section(lines, r"^attendees$") or []
    names = []
    for line in body:
        match = re.match(r"^\s*[-*]\s+(.*)$", line)
        if match:
            first = match.group(1).split("/")[0].strip()
            if first:
                names.append(first)
    return names


def parse_notes(text: str) -> NotesDoc:
    lines = text.replace("\r\n", "\n").split("\n")
    theme_match = THEME_RE.search(text)
    exercises = chat_digest.extract_section(lines, r"^exercises?$") or []

    before: list[str] = []
    after: list[str] = []
    rooms: list[Room] = []
    state = "head"  # head -> before -> room -> after
    skipping_exercises = False

    for line in lines:
        heading = HEADING_RE.match(line)
        level = len(heading.group(1)) if heading else None
        title = heading.group(2) if heading else ""

        if heading and level == 2 and title.lower() == "notes":
            state = "before"
            continue
        if state == "head":
            continue

        if heading and level is not None and level <= 4:
            room_match = ROOM_RE.match(title)
            if room_match:
                rooms.append(Room(number=int(room_match.group(1))))
                state = "room"
                skipping_exercises = False
                continue
            if state == "room":
                state = "after"
        if state == "before":
            if heading and re.match(r"^exercises?$", title, re.I):
                skipping_exercises = True
                continue
            if heading:
                skipping_exercises = False
            if not skipping_exercises:
                before.append(line)
        elif state == "after":
            after.append(line)
        elif state == "room":
            room = rooms[-1]
            if heading and level == 5:
                room.blocks.append(Block(_block_kind(title), title))
                continue
            speaker = SPEAKER_RE.match(line)
            if speaker and not room.blocks and not room.speaker:
                room.speaker = speaker.group(1).strip()
                continue
            (room.blocks[-1].lines if room.blocks else room.room_lines).append(line)

    return NotesDoc(
        theme=theme_match.group(1) if theme_match else None,
        attendee_names=extract_attendee_names(lines),
        exercises=exercises,
        before=before,
        rooms=rooms,
        after=after,
    )


def split_reflection(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split a block's lines at a standalone 'Reflection' line."""
    for index, line in enumerate(lines):
        if REFLECTION_RE.match(line):
            return lines[:index], lines[index + 1:]
    return lines, []


# --------------------------------------------------------------------------
# Name removal
# --------------------------------------------------------------------------

def _tokens(text: str, capitalised_only: bool = False) -> set[str]:
    out = set()
    for word in WORD_RE.findall(text):
        if capitalised_only and not word[0].isupper():
            continue
        lowered = word.lower()
        if len(lowered) >= MIN_TOKEN_LENGTH and lowered not in NAME_PARTICLES | SKIP_NAME_WORDS:
            out.add(lowered)
    return out


def collect_name_tokens(doc: NotesDoc, extra_names: list[str]) -> set[str]:
    tokens: set[str] = set()
    for name in [*doc.attendee_names, *extra_names]:
        tokens |= _tokens(name)
    for room in doc.rooms:
        tokens |= _tokens(room.speaker, capitalised_only=True)
        for block in room.blocks:
            if block.kind == "notes":
                tokens |= _tokens(re.sub(r"^notes\b[:\s]*", "", block.title, flags=re.I), capitalised_only=True)
    return tokens


class Scrubber:
    def __init__(self, tokens: set[str]):
        self.tokens = tokens
        self.pattern = (
            re.compile(
                r"(?<!\w)(" + "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True)) + r")(?!\w)",
                re.IGNORECASE,
            )
            if tokens else None
        )
        self.replacements = 0

    def _segment(self, segment: str) -> str:
        if not self.pattern:
            return segment
        def replace(_: re.Match) -> str:
            self.replacements += 1
            return NAME_PLACEHOLDER
        return NAME_RUN_RE.sub(NAME_PLACEHOLDER, self.pattern.sub(replace, segment))

    def scrub(self, text: str) -> str:
        out, position = [], 0
        for url in URL_RE.finditer(text):
            out.append(self._segment(text[position:url.start()]))
            out.append(url.group(0))
            position = url.end()
        out.append(self._segment(text[position:]))
        return "".join(out)

    def leaks(self, text: str) -> list[int]:
        if not self.pattern:
            return []
        return [
            number for number, line in enumerate(text.split("\n"), start=1)
            if self.pattern.search(URL_RE.sub(" ", line))
        ]


# --------------------------------------------------------------------------
# Digest
# --------------------------------------------------------------------------

def tidy(lines: list[str]) -> list[str]:
    """Trim, drop empty bullets, and collapse runs of blank lines."""
    out: list[str] = []
    for line in lines:
        line = line.rstrip()
        if EMPTY_BULLET_RE.match(line):
            continue
        if not line and (not out or not out[-1]):
            continue
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return out


def word_count(lines: list[str]) -> int:
    return len(" ".join(lines).split())


@dataclass
class RoomView:
    number: int
    speaker_named: bool
    room_notes: list[str]
    note_takers: list[list[str]]
    reflection: list[str]
    story: list[str]
    other: list[tuple[str, list[str]]]

    @property
    def notes_words(self) -> int:
        return word_count(self.room_notes) + sum(word_count(n) for n in self.note_takers)


def build_room_view(room: Room, scrubber: Scrubber) -> RoomView:
    reflection: list[str] = []
    note_takers: list[list[str]] = []
    story: list[str] = []
    other: list[tuple[str, list[str]]] = []
    for block in room.blocks:
        lines = tidy([scrubber.scrub(line) for line in block.lines])
        if block.kind == "notes":
            body, reflected = split_reflection(lines)
            note_takers.append(tidy(body))
            reflection += reflected
        elif block.kind == "story":
            story += lines
        else:
            other.append((scrubber.scrub(block.title), lines))
    room_notes, room_reflection = split_reflection(tidy([scrubber.scrub(l) for l in room.room_lines]))
    return RoomView(
        number=room.number,
        speaker_named=bool(room.speaker),
        room_notes=tidy(room_notes),
        note_takers=note_takers,
        reflection=tidy(reflection + room_reflection),
        story=tidy(story),
        other=other,
    )


def build_digest(doc: NotesDoc, scrubber: Scrubber, notes_name: str, month: str) -> str:
    views = [build_room_view(room, scrubber) for room in doc.rooms]
    out = [f"# Collab notes digest: {month}", ""]
    out += [
        "Generated by `notes_digest.py`. Deterministic extraction only; no interpretation.",
        "Names are removed (shown as `[name]`); note-takers appear as Note-taker N; "
        "the attendee list is not included.",
        "",
        "## Session",
        "",
        f"- Notes: `{notes_name}`",
    ]
    if doc.theme:
        out.append(f"- Theme (from notes): {scrubber.scrub(doc.theme)}")
    out += [
        f"- Attendees listed: {len(doc.attendee_names)} (list removed)",
        f"- Breakout rooms: {len(views)}",
        "",
        "## Exercises (verbatim from the notes)",
        "",
        *(tidy([scrubber.scrub(l) for l in doc.exercises]) or ["(none found)"]),
        "",
        "## Exercise tasks (numbered for the completion check)",
        "",
        "Each task needs a row in `exercises-completion.md` saying whether it was done "
        "in the session, partly done, or completed afterwards.",
        "",
        *(exercise_tasks.checklist_lines(exercise_tasks.parse_tasks(doc.exercises)) or ["(none found)"]),
        "",
    ]

    before = tidy([scrubber.scrub(l) for l in doc.before])
    if before:
        out += ["## Before the breakouts", "", *before, ""]

    out += [
        "## Completeness",
        "",
        "| Room | Speaker named | Note-takers | Words in notes | Reflection recorded | Words in collaborative story |",
        "|---|---|---|---|---|---|",
    ]
    for v in views:
        out.append(
            f"| {v.number} | {'yes' if v.speaker_named else 'no'} | {len(v.note_takers)} "
            f"| {v.notes_words} | {'yes' if v.reflection else 'no'} | {word_count(v.story)} |"
        )
    out.append("")

    for v in views:
        out += [f"## Breakout Room {v.number}", ""]
        if v.room_notes:
            out += ["### Untitled room notes", "", *v.room_notes, ""]
        for index, lines in enumerate(v.note_takers, start=1):
            out += [f"### Note-taker {index}", "", *(lines or ["(empty)"]), ""]
        if v.reflection:
            out += ["### Reflection", "", *v.reflection, ""]
        for title, lines in v.other:
            out += [f"### {title}", "", *(lines or ["(empty)"]), ""]
        out += ["### Collaborative story", "", *(v.story or ["(empty)"]), ""]

    after = tidy([scrubber.scrub(l) for l in doc.after])
    if after:
        out += ["## After the breakouts", "", *after, ""]
    return "\n".join(out)


def run(docs_dir: Path, blog_dir: Path, extra_names: list[str] | None = None) -> tuple[Path, dict]:
    """Pipeline stage entrypoint. Returns (output path, stats)."""
    notes = chat_digest.find_one(docs_dir, "*collab*notes*.md", "collaborative notes")
    month = blog_dir.name.removeprefix("blog-")
    doc = parse_notes(notes.read_text(encoding="utf-8-sig"))
    if not doc.rooms:
        raise ValueError(f"no 'Breakout Room N' headings found in {notes.name}")
    scrubber = Scrubber(collect_name_tokens(doc, list(extra_names or [])))
    digest = build_digest(doc, scrubber, notes.name, month)
    blog_dir.mkdir(parents=True, exist_ok=True)
    output = blog_dir / DIGEST_NAME
    output.write_text(digest + "\n", encoding="utf-8")
    stats = {
        "rooms": len(doc.rooms),
        "attendees": len(doc.attendee_names),
        "names_replaced": scrubber.replacements,
        "leak_lines": scrubber.leaks(digest),
    }
    return output, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the collaborative notes digest.")
    parser.add_argument("docs_dir", type=Path, help="e.g. docs/materials-202610")
    parser.add_argument("blog_dir", type=Path, help="e.g. project-management/communications/blog-202610")
    parser.add_argument("--extra-name", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        output, stats = run(args.docs_dir, args.blog_dir, args.extra_name)
    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"wrote {output}")
    print(f"  rooms: {stats['rooms']}, names replaced: {stats['names_replaced']}")
    if stats["leak_lines"]:
        print(f"  LEAK: name still present on digest lines {stats['leak_lines']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
