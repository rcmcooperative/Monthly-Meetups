"""Tests for the exercise task checklist. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import exercise_tasks as et  # noqa: E402

EXERCISES = """1. Personal origin story
  - 1 person: tell it (3-5 min)
  - Everyone else takes notes
  - Reflect on how you received the story (5 min)
    - What details stood out to you?
    - Did you notice specific inflection points?
    - How do your notes differ from eachother?
2. Collaborative origin story (10 min)
  - Redraft this origin story together. It should be/do:
    - Concise, easy to remember
    - Articulate our values
    - Provide an entrance into this community
  - What does it mean if we emphasise different parts?
  - Who are the audiences for this story?
""".split("\n")

IDS = [
    "1", "1.1", "1.2", "1.3", "1.3.1", "1.3.2", "1.3.3",
    "2", "2.1", "2.1.1", "2.1.2", "2.1.3", "2.2", "2.3",
]


def completion(statuses=None, skip=(), extra=(), todo=False):
    statuses = statuses or {}
    rows = ["| ID | Task | Status | Evidence |", "|---|---|---|---|"]
    for task_id in [*IDS, *extra]:
        if task_id in skip:
            continue
        rows.append(f"| {task_id} | task | {statuses.get(task_id, et.STATUS_DONE)} | evidence |")
    text = "\n".join(rows)
    return text + ("\n\n<mark>TODO: finish</mark>" if todo else "")


class ParseTests(unittest.TestCase):
    def test_numbering_from_structure(self):
        self.assertEqual([t.id for t in et.parse_tasks(EXERCISES)], IDS)

    def test_depths(self):
        depths = {t.id: t.depth for t in et.parse_tasks(EXERCISES)}
        self.assertEqual((depths["1"], depths["1.3"], depths["1.3.2"]), (0, 1, 2))

    def test_text_kept(self):
        tasks = {t.id: t.text for t in et.parse_tasks(EXERCISES)}
        self.assertEqual(tasks["2.3"], "Who are the audiences for this story?")

    def test_bulleted_top_level_numbered_sequentially(self):
        tasks = et.parse_tasks(["- First", "  - Child", "- Second"])
        self.assertEqual([t.id for t in tasks], ["1", "1.1", "2"])

    def test_non_list_lines_ignored(self):
        self.assertEqual(et.parse_tasks(["", "plain text", "1. Only item"])[0].id, "1")

    def test_checklist_lines_indent_by_depth(self):
        lines = et.checklist_lines(et.parse_tasks(EXERCISES))
        self.assertTrue(lines[0].startswith("- **1**"))
        self.assertTrue(lines[4].startswith("    - **1.3.1**"))


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tasks = et.parse_tasks(EXERCISES)

    def test_complete_document_passes(self):
        self.assertEqual(et.check_completion(self.tasks, completion()), [])

    def test_all_three_statuses_accepted(self):
        text = completion({"1": et.STATUS_PARTLY, "1.3.2": et.STATUS_COMPLETED_HERE})
        self.assertEqual(et.check_completion(self.tasks, text), [])

    def test_missing_row_reported(self):
        problems = et.check_completion(self.tasks, completion(skip={"2.3"}))
        self.assertEqual(len(problems), 1)
        self.assertIn("2.3", problems[0])

    def test_invalid_status_reported(self):
        problems = et.check_completion(self.tasks, completion({"1.1": "Finished"}))
        self.assertTrue(any("1.1" in p and "Finished" in p for p in problems))

    def test_stale_row_reported(self):
        problems = et.check_completion(self.tasks, completion(extra=["3"]))
        self.assertTrue(any("3" in p and "does not match" in p for p in problems))

    def test_todo_reported(self):
        problems = et.check_completion(self.tasks, completion(todo=True))
        self.assertTrue(any("TODO" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
