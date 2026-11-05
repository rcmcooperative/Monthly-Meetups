"""Tests for writing the Claude Code deny rule. Run from the repo root:

    python -m unittest discover -s code/blog-recap/tests -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import claude_settings as cs  # noqa: E402

RULE = ["Read(./private/**)"]


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / ".claude" / "settings.json"

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_creates_file_and_folder(self):
        self.assertEqual(cs.add_deny_rules(self.path, RULE), RULE)
        self.assertEqual(self.read(), {"permissions": {"deny": RULE}})

    def test_keeps_existing_settings_and_rules(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"model": "x", "permissions": {"allow": ["Bash(ls)"], "deny": ["Read(./.env)"]}}),
                             encoding="utf-8")
        cs.add_deny_rules(self.path, RULE)
        data = self.read()
        self.assertEqual(data["model"], "x")
        self.assertEqual(data["permissions"]["allow"], ["Bash(ls)"])
        self.assertEqual(data["permissions"]["deny"], ["Read(./.env)"] + RULE)

    def test_idempotent(self):
        cs.add_deny_rules(self.path, RULE)
        self.assertEqual(cs.add_deny_rules(self.path, RULE), [])
        self.assertEqual(self.read()["permissions"]["deny"], RULE)

    def test_invalid_json_is_not_overwritten(self):
        self.path.parent.mkdir()
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(cs.SettingsError):
            cs.add_deny_rules(self.path, RULE)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{not json")

    def test_unexpected_shape_is_not_changed(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"permissions": {"deny": "oops"}}), encoding="utf-8")
        with self.assertRaises(cs.SettingsError):
            cs.add_deny_rules(self.path, RULE)


if __name__ == "__main__":
    unittest.main()
