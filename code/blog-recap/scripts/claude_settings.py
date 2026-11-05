"""Write the Claude Code deny rule that keeps Claude out of private/.

Creates ``.claude/settings.json`` or adds the rule to the existing one. Existing settings
are kept, the rule is added only once, and a file that is not valid JSON is never
overwritten.
"""

from __future__ import annotations

import json
from pathlib import Path

import config


class SettingsError(Exception):
    pass


def add_deny_rules(path: Path, rules: list[str]) -> list[str]:
    """Add ``rules`` to permissions.deny in the settings file. Returns the rules newly added."""
    data: dict = {}
    if path.exists() and path.read_text(encoding="utf-8").strip():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SettingsError(f"{path} is not valid JSON ({error}); fix it by hand, it was not changed") from error
        if not isinstance(data, dict):
            raise SettingsError(f"{path} does not hold a JSON object; it was not changed")
    permissions = data.setdefault("permissions", {})
    if not isinstance(permissions, dict) or not isinstance(permissions.setdefault("deny", []), list):
        raise SettingsError(f"{path}: 'permissions' or 'deny' has an unexpected shape; it was not changed")
    deny = permissions["deny"]
    added = [rule for rule in rules if rule not in deny]
    if added or not path.exists():
        deny.extend(added)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return added


def run() -> list[str]:
    return add_deny_rules(Path.cwd() / config.CLAUDE_SETTINGS, config.CLAUDE_DENY_RULES)
