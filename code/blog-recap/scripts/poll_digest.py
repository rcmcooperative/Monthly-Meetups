"""Stage 4: turn the Zoom poll export into a poll digest.

Reads ``docs/materials-YYYYMM/*poll*.csv`` (the feedback poll is the same
every session) and writes ``project-management/communications/blog-YYYYMM/poll-digest.md`` with
the number of responses and, for each question, the percentage of respondents
at each Likert point (5 strongly agree to 1 strongly disagree).

Zoom exports a poll as a few blocks: an overview, a list of launched polls,
then one block per poll whose header row is
``#,[User Name,Email Address,]Submitted Date and Time,<question>...``.
Respondent columns, if present, are ignored and never written out. Data rows
carry trailing empty cells, which are dropped.
"""

from __future__ import annotations

import csv
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SUBMITTED = "Submitted Date and Time"
SCALE = (1, 2, 3, 4, 5)
# Likert scale: 5 = strongly agree ... 1 = strongly disagree. Shown agree-first.
SENTIMENTS = (
    (5, "Strongly agree"),
    (4, "Agree"),
    (3, "Neutral"),
    (2, "Disagree"),
    (1, "Strongly disagree"),
)
AGREE = (4, 5)
DIGEST_NAME = "poll-digest.md"


class PollFormatError(ValueError):
    pass


@dataclass
class Question:
    label: str
    statement: str
    ratings: list[int]

    @property
    def mean(self) -> float:
        return statistics.mean(self.ratings)

    @property
    def agree_share(self) -> float:
        return sum(r in AGREE for r in self.ratings) / len(self.ratings)

    def distribution(self) -> Counter:
        return Counter(self.ratings)


@dataclass
class Poll:
    name: str
    responses: int
    questions: list[Question]


def split_question(text: str) -> tuple[str, str]:
    """'Building RCM capacity: This session…' -> (label, statement)."""
    label, sep, statement = text.partition(":")
    if sep and len(label) <= 60:
        return label.strip(), statement.strip()
    return text.strip(), ""


def parse_poll(rows: list[list[str]]) -> list[Poll]:
    polls: list[Poll] = []
    i = 0
    while i < len(rows):
        row = rows[i]
        if SUBMITTED in row:
            start = row.index(SUBMITTED) + 1
            header = [c for c in row[start:] if c.strip()]
            width = len(header)
            data: list[list[str]] = []
            i += 1
            while i < len(rows) and any(c.strip() for c in rows[i]):
                data.append(rows[i][start:start + width])
                i += 1
            ratings = [[] for _ in header]
            for line_no, record in enumerate(data, 1):
                for col, cell in enumerate(record):
                    cell = cell.strip()
                    if not cell:
                        continue
                    try:
                        value = int(cell)
                    except ValueError:
                        raise PollFormatError(
                            f"response {line_no}, question {col + 1}: '{cell}' is not a number"
                        ) from None
                    if value not in SCALE:
                        raise PollFormatError(
                            f"response {line_no}, question {col + 1}: {value} is outside 1-5"
                        )
                    ratings[col].append(value)
            name = polls_title(rows, len(polls))
            polls.append(Poll(
                name=name,
                responses=len(data),
                questions=[Question(*split_question(h), r) for h, r in zip(header, ratings)],
            ))
        else:
            i += 1
    if not polls:
        raise PollFormatError(f"no poll block found (looked for a '{SUBMITTED}' header)")
    empty = [q.label for p in polls for q in p.questions if not q.ratings]
    if empty:
        raise PollFormatError(f"no ratings for: {', '.join(empty)}")
    return polls


def polls_title(rows: list[list[str]], index: int) -> str:
    """Poll name from the 'Launched Polls' table, else a placeholder."""
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Launched Polls":
            names = []
            for r in rows[i + 2:]:
                if not any(c.strip() for c in r):
                    break
                names.append(r[1].strip() if len(r) > 1 else "")
            if index < len(names):
                return names[index]
    return f"Poll {index + 1}"


def percent(count: int, total: int) -> str:
    return f"{count / total:.0%} ({count})"


def build_digest(polls: list[Poll], meeting_topic: str) -> str:
    out = ["# Poll digest", "",
           f"*Meeting: {meeting_topic}.*",
           "*Likert scale from strongly agree (5) to strongly disagree (1). "
           "Each cell is the percentage of respondents, with the number in brackets. "
           "Percentages are rounded, so a row may not add up to exactly 100%. "
           "Respondents are anonymous.*", ""]
    names = " | ".join(name for _, name in SENTIMENTS)
    for poll in polls:
        out += [f"## {poll.name}", "", f"Responses: {poll.responses}", "",
                f"| Question | Statement | {names} | Agree or strongly agree |",
                "|---|---|" + "---|" * (len(SENTIMENTS) + 1)]
        for q in poll.questions:
            dist = q.distribution()
            total = len(q.ratings)
            cells = " | ".join(percent(dist.get(score, 0), total) for score, _ in SENTIMENTS)
            agreed = sum(dist.get(score, 0) for score in AGREE)
            out.append(
                f"| {q.label} | {q.statement} | {cells} | {percent(agreed, total)} |"
            )
        out.append("")
    return "\n".join(out)


def meeting_topic(rows: list[list[str]]) -> str:
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Generate Time" and "Meeting Topic" in row:
            topic_col = row.index("Meeting Topic")
            if i + 1 < len(rows) and len(rows[i + 1]) > topic_col:
                return rows[i + 1][topic_col].strip()
    return "unknown"


def find_poll_file(docs_dir: Path) -> Path | None:
    found = sorted(p for p in docs_dir.glob("*.csv") if "poll" in p.name.lower())
    if len(found) > 1:
        raise FileNotFoundError(
            f"more than one poll file in {docs_dir}: {', '.join(p.name for p in found)}"
        )
    return found[0] if found else None


def run(docs_dir: Path, blog_dir: Path) -> tuple[Path, list[Poll]] | None:
    """Write poll-digest.md; return None when the session had no poll file."""
    source = find_poll_file(docs_dir)
    if source is None:
        return None
    with source.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    polls = parse_poll(rows)
    blog_dir.mkdir(parents=True, exist_ok=True)
    output = blog_dir / DIGEST_NAME
    output.write_text(build_digest(polls, meeting_topic(rows)), encoding="utf-8")
    return output, polls
