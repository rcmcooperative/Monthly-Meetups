#!/usr/bin/env python3
"""Stage 1 of the meetup blog pipeline: anonymise a Zoom chat export.

Input:  a Zoom chat download (tab-separated: ``HH:MM:SS<TAB>Name:<TAB>message``)
        found in ``private/materials-YYYYMM/``.
Output: ``<input-stem>_anonymised.txt`` written to the same directory.

What it does (all deterministic, no LLM involved):

1. Parses the export into messages (a header line plus any continuation lines).
2. Folds reaction events ("Reacted to ... with ...") into a count on the message
   they react to, written as a trailing note such as ``[+3 reactions: 💯×2, 🩷×1]``.
   The events themselves (and who reacted) are dropped. A reaction is matched to
   the most recent earlier message whose text equals the quoted text, or starts
   with it when Zoom has truncated the quote with "...". Quotes of a reply match
   the reply part of the message. Reactions that cannot be matched are counted
   in the report but not attached.
3. Collapses display-name variants of one person into one participant, e.g.
   ``S - Jo Bloggs (she/her)`` and ``Jo (JB) Bloggs`` both become one label.
   Prefixes such as ``S - `` / ``W - ``, pronoun brackets and ", Organisation"
   suffixes are ignored when matching.
4. Replaces every speaker name with a stable pseudonym (``Participant 01``...),
   numbered by order of first appearance. The mapping is never written to disk.
5. Replaces @-mentions and full names inside messages with the same pseudonym.
6. Replaces any remaining individual name parts (first names, surnames,
   nicknames, plus ``--extra-name`` values) with ``[name]``. Text inside URLs is
   left untouched so that links stay usable.
7. Self-checks the output for leaked names and unresolved @-mentions, and exits
   non-zero if it finds a leak.

Known limits: nicknames that never appear in a display name (e.g. "Cass" for
"Cassandra") are only caught if passed via ``--extra-name`` or listed in
``config.py``. Email addresses and other personal data in message text are not
handled here.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

HEADER_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\t(.+?):\t(.*)$")
TIMESTAMP_START_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\t")
PREFIX_RE = re.compile(r"^[A-Za-z]\s*-\s*(?=\S)")  # "S - ", "W - ", "s-"
PAREN_RE = re.compile(r"\(([^)]*)\)")
URL_RE = re.compile(r"https?://\S+")
WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
REACTION_RE = re.compile(
    r'^(?:Reacted to ".*" with \S+|Removed a \S+ reaction from ".*")$', re.DOTALL
)
REACTION_ADD_RE = re.compile(r'^Reacted to "(?P<quote>.*)" with (?P<emoji>\S+)$', re.DOTALL)
REACTION_REMOVE_RE = re.compile(r'^Removed a (?P<emoji>\S+) reaction from "(?P<quote>.*)"$', re.DOTALL)
REPLY_RE = re.compile(r'^Replying to ".*?"\n\n(?P<reply>.*)$', re.DOTALL)
UNRESOLVED_AT_RE = re.compile(r"(?<![\w.])@(?!Participant \d|\[name\])\S")

PRONOUNS = {
    "he", "him", "his", "she", "her", "hers", "they", "them", "their",
    "theirs", "ze", "zir", "xe", "xem", "it", "its", "any", "ask",
}
NAME_PARTICLES = {"van", "der", "den", "von", "del", "dos", "das", "de", "la", "le", "bin", "ibn"}
MIN_TOKEN_LENGTH = 3
OUTPUT_SUFFIX = "_anonymised"
NAME_PLACEHOLDER = "[name]"


class ChatFormatError(Exception):
    """Raised when the chat export does not match the expected format."""


@dataclass
class Message:
    timestamp: str
    name: str
    lines: list[str]
    source_line: int

    @property
    def text(self) -> str:
        return "\n".join(self.lines).rstrip("\n")

    @property
    def is_reaction(self) -> bool:
        return bool(REACTION_RE.match(self.text))


@dataclass
class Person:
    label: str
    display: str
    raw_names: set[str] = field(default_factory=set)
    nicknames: set[str] = field(default_factory=set)

    @property
    def variants(self) -> set[str]:
        out = {self.display}
        for raw in self.raw_names:
            out.add(raw.strip())
            out.add(PREFIX_RE.sub("", raw.strip()))
        return {v for v in out if v}


@dataclass
class Report:
    source: Path
    output: Path
    messages_kept: int = 0
    reactions_dropped: int = 0
    reactions_attached: int = 0
    reactions_unmatched: int = 0
    participants: int = 0
    mentions_replaced: int = 0
    full_names_replaced: int = 0
    tokens_replaced: int = 0
    unresolved_mentions: list[int] = field(default_factory=list)
    leaks: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"  input:                {self.source.name}",
            f"  output:               {self.output.name}",
            f"  messages kept:        {self.messages_kept}",
            f"  reaction events:      {self.reactions_dropped} folded into counts "
            f"({self.reactions_attached} reactions attached, "
            f"{self.reactions_unmatched} events unmatched)",
            f"  participants:         {self.participants}",
            f"  @-mentions replaced:  {self.mentions_replaced}",
            f"  full names replaced:  {self.full_names_replaced}",
            f"  name parts replaced:  {self.tokens_replaced}",
        ]
        if self.unresolved_mentions:
            where = ", ".join(str(n) for n in self.unresolved_mentions)
            lines.append(f"  UNRESOLVED @-mentions on output lines: {where}")
        for leak in self.leaks:
            lines.append(f"  LEAK: {leak}")
        return "\n".join(lines)

    @property
    def ok(self) -> bool:
        return not self.leaks


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def parse_messages(text: str) -> list[Message]:
    """Split a Zoom chat export into messages, failing loudly on odd input."""
    messages: list[Message] = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        match = HEADER_RE.match(line)
        if match:
            messages.append(Message(match[1], match[2], [match[3]], number))
        elif TIMESTAMP_START_RE.match(line):
            raise ChatFormatError(
                f"line {number} starts like a chat entry but has no 'Name:<TAB>' "
                "part; the export format may have changed"
            )
        elif messages:
            messages[-1].lines.append(line)
        elif line.strip():
            raise ChatFormatError(
                f"line {number} appears before any timestamped message; "
                "this does not look like a Zoom chat export"
            )
    if not messages:
        raise ChatFormatError("no timestamped messages found in the chat file")
    return messages


# --------------------------------------------------------------------------
# Reactions
# --------------------------------------------------------------------------

def _squash(text: str) -> str:
    return " ".join(text.split())


def _candidate_texts(text: str) -> list[str]:
    """Texts a reaction quote could refer to: the whole message, or a reply's body."""
    candidates = [_squash(text)]
    reply = REPLY_RE.match(text)
    if reply:
        candidates.append(_squash(reply.group("reply")))
    return candidates


def _quote_matches(quote: str, candidates: list[str]) -> bool:
    q = _squash(quote)
    prefix = q[:-3] if q.endswith("...") else None
    if prefix is not None and not prefix.strip():
        prefix = None
    return any(c == q or (prefix is not None and c.startswith(prefix)) for c in candidates)


def attribute_reactions(messages: list[Message]) -> tuple[dict[int, Counter], int]:
    """Map reaction events to the message index they react to.

    Returns ({message index: Counter of emoji}, number of unmatched events).
    """
    tallies: dict[int, Counter] = {}
    seen: list[tuple[int, list[str]]] = []
    unmatched = 0
    for index, message in enumerate(messages):
        text = message.text
        event = REACTION_ADD_RE.match(text) or REACTION_REMOVE_RE.match(text)
        if not event:
            seen.append((index, _candidate_texts(text)))
            continue
        target = next(
            (i for i, candidates in reversed(seen) if _quote_matches(event["quote"], candidates)),
            None,
        )
        if target is None:
            unmatched += 1
            continue
        tally = tallies.setdefault(target, Counter())
        if REACTION_ADD_RE.match(text):
            tally[event["emoji"]] += 1
        elif tally[event["emoji"]] > 0:
            tally[event["emoji"]] -= 1
    return tallies, unmatched


def reaction_note(tally: Counter | None) -> str:
    """Trailing note for a message, e.g. ``[+3 reactions: 💯×2, 🩷×1]``; empty if none."""
    if not tally:
        return ""
    items = [(emoji, count) for emoji, count in tally.most_common() if count > 0]
    total = sum(count for _, count in items)
    if not total:
        return ""
    word = "reaction" if total == 1 else "reactions"
    detail = ", ".join(f"{emoji}×{count}" for emoji, count in items)
    return f"[+{total} {word}: {detail}]"


# --------------------------------------------------------------------------
# Name handling
# --------------------------------------------------------------------------

def _is_pronoun_group(text: str) -> bool:
    words = [w.lower() for w in WORD_RE.findall(text)]
    return bool(words) and all(w in PRONOUNS for w in words)


def normalise_name(raw: str) -> tuple[str, set[str]]:
    """Return (canonical display name, nicknames) for a raw Zoom display name."""
    stripped = PREFIX_RE.sub("", raw.strip())
    nicknames = {
        group.strip()
        for group in PAREN_RE.findall(stripped)
        if group.strip() and not _is_pronoun_group(group)
    }
    stripped = PAREN_RE.sub("", stripped)
    stripped = stripped.split(",")[0]
    canonical = " ".join(stripped.split()) or raw.strip()
    return canonical, nicknames


def build_registry(messages: list[Message]) -> dict[str, Person]:
    """Group display-name variants into people, labelled by first appearance."""
    people: dict[str, Person] = {}
    for message in messages:
        canonical, nicknames = normalise_name(message.name)
        key = canonical.casefold()
        if key not in people:
            people[key] = Person(label="", display=canonical)
        people[key].raw_names.add(message.name)
        people[key].nicknames.update(nicknames)
    width = max(2, len(str(len(people))))
    for index, person in enumerate(people.values(), start=1):
        person.label = f"Participant {index:0{width}d}"
    return people


def _alternation(words: set[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


class Scrubber:
    """Replaces names in message text, leaving URLs untouched."""

    def __init__(self, people: dict[str, Person], extra_names: list[str]):
        mention_map: dict[str, str] = {}
        bare_map: dict[str, str] = {}
        tokens: set[str] = set()
        for person in people.values():
            for variant in person.variants:
                mention_map[variant.lower()] = person.label
                if len(variant.split()) > 1:
                    bare_map[variant.lower()] = person.label
            for source in [person.display, *person.nicknames]:
                tokens.update(w.lower() for w in WORD_RE.findall(source))
        for extra in extra_names:
            tokens.update(w.lower() for w in WORD_RE.findall(extra))
        tokens = {t for t in tokens if len(t) >= MIN_TOKEN_LENGTH and t not in NAME_PARTICLES}

        self.mention_map = mention_map
        self.bare_map = bare_map
        self.mention_re = (
            re.compile(rf"(?<!\w)@({_alternation(set(mention_map))})(?!\w)", re.IGNORECASE)
            if mention_map else None
        )
        self.bare_re = (
            re.compile(rf"(?<![\w@])({_alternation(set(bare_map))})(?!\w)", re.IGNORECASE)
            if bare_map else None
        )
        self.token_re = (
            re.compile(rf"(?<!\w)({_alternation(tokens)})(?!\w)", re.IGNORECASE)
            if tokens else None
        )
        self.mentions_replaced = 0
        self.full_names_replaced = 0
        self.tokens_replaced = 0

    def _segment(self, segment: str) -> str:
        if self.mention_re:
            def mention(m: re.Match) -> str:
                self.mentions_replaced += 1
                return "@" + self.mention_map[m.group(1).lower()]
            segment = self.mention_re.sub(mention, segment)
        if self.bare_re:
            def bare(m: re.Match) -> str:
                self.full_names_replaced += 1
                return self.bare_map[m.group(1).lower()]
            segment = self.bare_re.sub(bare, segment)
        if self.token_re:
            def token(m: re.Match) -> str:
                self.tokens_replaced += 1
                return NAME_PLACEHOLDER
            segment = self.token_re.sub(token, segment)
        return segment

    def scrub(self, text: str) -> str:
        out: list[str] = []
        position = 0
        for url in URL_RE.finditer(text):
            out.append(self._segment(text[position:url.start()]))
            out.append(url.group(0))
            position = url.end()
        out.append(self._segment(text[position:]))
        return "".join(out)

    def residual_token_lines(self, output_lines: list[str]) -> list[int]:
        """1-based output lines where a name part still appears outside URLs."""
        if not self.token_re:
            return []
        hits = []
        for number, line in enumerate(output_lines, start=1):
            rest = URL_RE.sub(" ", line)
            if self.token_re.search(rest):
                hits.append(number)
        return hits


# --------------------------------------------------------------------------
# Processing
# --------------------------------------------------------------------------

def anonymise_text(text: str, extra_names: list[str], report: Report) -> str:
    messages = parse_messages(text)
    people = build_registry(messages)
    scrubber = Scrubber(people, extra_names)
    tallies, report.reactions_unmatched = attribute_reactions(messages)

    output_lines: list[str] = []
    for index, message in enumerate(messages):
        if message.is_reaction:
            report.reactions_dropped += 1
            continue
        label = people[normalise_name(message.name)[0].casefold()].label
        body = scrubber.scrub(message.text)
        note = reaction_note(tallies.get(index))
        if note:
            body = f"{body} {note}"
            report.reactions_attached += sum(c for c in tallies[index].values() if c > 0)
        output_lines.append(f"{message.timestamp}\t{label}:\t{body}")
        report.messages_kept += 1

    output = "\n".join(output_lines).split("\n")  # one entry per physical line
    report.participants = len(people)
    report.mentions_replaced = scrubber.mentions_replaced
    report.full_names_replaced = scrubber.full_names_replaced
    report.tokens_replaced = scrubber.tokens_replaced

    for number in scrubber.residual_token_lines(output):
        report.leaks.append(f"name part still present on output line {number}")
    flat = "\n".join(output).casefold()
    for person in people.values():
        for variant in person.variants:
            if variant.casefold() in flat:
                report.leaks.append("a full display name is still present in the output")
                break
    for number, line in enumerate(output, start=1):
        if UNRESOLVED_AT_RE.search(URL_RE.sub(" ", line)):
            report.unresolved_mentions.append(number)

    return "\n".join(output) + "\n"


def find_chat_files(materials_dir: Path) -> list[Path]:
    """Chat exports (*chat*.txt) in the raw materials folder."""
    candidates = sorted(
        p for p in materials_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".txt"
        and "chat" in p.name.lower()
        and OUTPUT_SUFFIX not in p.stem  # not an output, nor its .review file
    )
    if candidates:
        return candidates
    present = ", ".join(sorted(p.name for p in materials_dir.iterdir())) or "(empty)"
    raise FileNotFoundError(
        f"no Zoom chat export (*chat*.txt) found in {materials_dir}; found: {present}"
    )


def process_file(path: Path, extra_names: list[str], output_dir: Path | None = None) -> Report:
    """Anonymise one export. The output goes in ``output_dir`` (default: beside the export)."""
    output_dir = output_dir or path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (path.stem + OUTPUT_SUFFIX + path.suffix)
    report = Report(source=path, output=output)
    text = path.read_text(encoding="utf-8-sig")
    anonymised = anonymise_text(text, extra_names, report)
    output.write_text(anonymised, encoding="utf-8")
    return report


def run(materials_dir: Path, extra_names: list[str] | None = None,
        output_dir: Path | None = None) -> list[Report]:
    """Pipeline stage entrypoint: anonymise every chat export in the directory.

    Outputs go in ``output_dir`` (the blog folder Claude may read), default beside the export.
    """
    extra = list(extra_names or [])
    return [process_file(path, extra, output_dir) for path in find_chat_files(materials_dir)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Anonymise a Zoom chat export.")
    parser.add_argument("materials_dir", type=Path, help="e.g. private/materials-202610")
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="where to write the anonymised chat (default: beside the export)",
    )
    parser.add_argument(
        "--extra-name", action="append", default=[],
        help="additional name or nickname to scrub (repeatable)",
    )
    args = parser.parse_args(argv)
    try:
        reports = run(args.materials_dir, args.extra_name, args.output_dir)
    except (ChatFormatError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for report in reports:
        print(report.summary())
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
