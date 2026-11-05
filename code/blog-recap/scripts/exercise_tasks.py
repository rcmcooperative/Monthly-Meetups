#!/usr/bin/env python3
"""Exercise task checklist for the meetup blog pipeline.

Breakout exercises are described in the collaborative notes as a nested list.
Rooms rarely complete every task in the time available. This module turns the
description into a numbered checklist, so that the review step can say, task by
task, what was done in the session and complete the rest afterwards.

Numbering is generated from the list structure::

    1. Personal origin story            -> 1
      - One person tells it             -> 1.1
      - Reflect on how you received it  -> 1.2
        - What stood out?               -> 1.2.1

Two functions are used by the pipeline:

* ``parse_tasks``: exercise lines -> list of ``Task`` (the notes digest lists them).
* ``check_completion``: verifies that the completion document written by the
  review step has one table row per task ID, a valid status for each, no stale
  IDs, and no unresolved ``TODO`` markers. This is a deterministic check on the
  LLM step's output.

The completion document must contain a markdown table whose first column is the
task ID and whose third column is one of ``STATUSES``::

    | ID | Task | Status | Evidence |
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import chat_digest

COMPLETION_NAME = "exercises-completion.md"

STATUS_DONE = "Done in session"
STATUS_PARTLY = "Partly done in session"
STATUS_COMPLETED_HERE = "Not done in session (completed here)"
STATUSES = (STATUS_DONE, STATUS_PARTLY, STATUS_COMPLETED_HERE)

TASK_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)(?:(?P<number>\d+)[.)]|[-*+])[ \t]+(?P<text>\S.*?)\s*$")
TODO_RE = re.compile(r"\bTODO\b")


@dataclass
class Task:
    id: str
    depth: int
    text: str


def parse_tasks(lines: list[str]) -> list[Task]:
    """Number the items of a nested markdown list (numbered or bulleted)."""
    tasks: list[Task] = []
    stack: list[list] = []  # entries: [indent, id, child_count]
    top_level_count = 0
    for line in lines:
        match = TASK_LINE_RE.match(line.expandtabs(2))
        if not match:
            continue
        indent = len(match["indent"])
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            parent = stack[-1]
            parent[2] += 1
            task_id = f"{parent[1]}.{parent[2]}"
        else:
            top_level_count += 1
            task_id = match["number"] or str(top_level_count)
        tasks.append(Task(task_id, len(stack), match["text"]))
        stack.append([indent, task_id, 0])
    return tasks


def checklist_lines(tasks: list[Task]) -> list[str]:
    return [f"{'  ' * task.depth}- **{task.id}** {task.text}" for task in tasks]


def _table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if cells and not set("".join(cells)) <= set("-: "):
            rows.append(cells)
    return rows


def check_completion(tasks: list[Task], completion_text: str) -> list[str]:
    """Return a list of problems; empty means the completion document is sound."""
    problems: list[str] = []
    expected = {task.id for task in tasks}
    found: dict[str, str] = {}
    for cells in _table_rows(completion_text):
        task_id = cells[0].strip("`* ")
        if task_id in expected or re.fullmatch(r"\d+(?:\.\d+)*", task_id):
            found[task_id] = cells[2] if len(cells) > 2 else ""
    for task in tasks:
        if task.id not in found:
            problems.append(f"task {task.id} has no row in the status table")
        elif found[task.id] not in STATUSES:
            problems.append(
                f"task {task.id} has status '{found[task.id]}'; expected one of {list(STATUSES)}"
            )
    for task_id in found:
        if task_id not in expected:
            problems.append(f"table row {task_id} does not match any task in the exercise description")
    if TODO_RE.search(completion_text):
        problems.append("the completion document still contains a TODO marker")
    return problems


def run_check(docs_dir: Path, review_dir: Path) -> list[str]:
    """Check review_dir/exercises-completion.md against the tasks in the notes."""
    notes = chat_digest.find_one(docs_dir, "*collab*notes*.md", "collaborative notes")
    exercises = chat_digest.extract_section(
        notes.read_text(encoding="utf-8-sig").replace("\r\n", "\n").split("\n"), r"^exercises?$"
    )
    if not exercises:
        return ["no 'Exercises' section found in the collaborative notes"]
    completion = review_dir / COMPLETION_NAME
    if not completion.is_file():
        return [f"{completion} does not exist; the review step has not written it yet"]
    return check_completion(parse_tasks(exercises), completion.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the exercise completion document.")
    parser.add_argument("docs_dir", type=Path, help="e.g. docs/materials-202610")
    parser.add_argument("review_dir", type=Path, help="e.g. private/blog-202610/review")
    args = parser.parse_args(argv)
    try:
        problems = run_check(args.docs_dir, args.review_dir)
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if not problems:
        print("exercise completion check passed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
