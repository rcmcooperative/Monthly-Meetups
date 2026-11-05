"""Redact links and secrets in the anonymised chat, reusing materials-archiving's rules.

Zoom chats are outside the archiving skill's own link rules, but a chat holds the same
kinds of secret (CryptPad edit links, Slack invitations, Zoom links, credentials) and the
anonymised chat is read by Claude and committed. So the chat goes through the same
flag, review, apply flow:

    flag    every URL and email address that the rules do not allow is wrapped in
            <redact>...</redact> in a review file in private/ (it still holds the links)
    review  the person edits the review file: leave a tag to redact, delete the two tags to
            keep the text, wrap more text to redact something the rules missed
    apply   tags are validated, replaced with a placeholder, and the result is re-checked;
            a blocking item left visible stops the run; any other URL or email left
            visible stops it unless --accept-residual says that was on purpose

The detector and ``redaction.toml`` are imported from ``code/materials-archiving`` (see
``config.ARCHIVING_DIR``), never copied, so the rules are changed in one place.
See that skill's handover note for what is flagged and why.
"""

from __future__ import annotations

import importlib
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import config

ROLE = "chat"  # no role_allow entry: URLs in a chat are never allowed by position
REVIEW_SUFFIX = ".review"


class RedactionError(Exception):
    pass


@dataclass
class Rules:
    config: dict
    flagging: object
    redaction: object
    error: type  # the archiving skill's PipelineError, raised for malformed tags

    @property
    def placeholder(self) -> str:
        return self.config["redaction"].get("placeholder", "`<redacted>`")


def load(base: Path | None = None) -> Rules:
    """Import the detector and read redaction.toml from the materials-archiving skill."""
    base = base or Path.cwd() / config.ARCHIVING_DIR
    toml_path = base / "config" / "redaction.toml"
    scripts = base / "scripts"
    if not toml_path.is_file() or not (scripts / "archiving").is_dir():
        raise RedactionError(
            f"the materials-archiving skill was not found at {base}. The chat's links are redacted "
            "with its rules (config/redaction.toml and scripts/archiving/): it must be in the repo "
            f"at {config.ARCHIVING_DIR}/"
        )
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        flagging = importlib.import_module("archiving.flagging")
        redaction = importlib.import_module("archiving.redaction")
        error = importlib.import_module("archiving.common").PipelineError
    except ImportError as error:
        raise RedactionError(f"could not import the redaction code from {scripts}: {error}") from error
    with toml_path.open("rb") as handle:
        return Rules({"redaction": tomllib.load(handle)}, flagging, redaction, error)


def flag(text: str, rules: Rules) -> tuple[str, list]:
    """Wrap everything to review in <redact> tags. Returns (flagged text, findings)."""
    findings = rules.flagging.find_findings(text, rules.config, ROLE)
    return rules.flagging.wrap_findings(text, findings), findings


def review_path(anonymised: Path) -> Path:
    """The review file for an anonymised chat: name_anonymised.review.txt, beside the raw export."""
    return anonymised.with_name(anonymised.stem + REVIEW_SUFFIX + anonymised.suffix)


def final_name(review: Path) -> str:
    return review.name.replace(REVIEW_SUFFIX + review.suffix, review.suffix)


def flag_report(findings: list, original: str, source: str, rules: Rules) -> str:
    """A table of what was flagged and why. It holds the links, so it stays in private/."""
    out = [f"# Link flags: {source}", "",
           "*Holds unredacted links: keep it in private/. Edit the review file, not this one.*", "",
           "| Line | Kind | Blocking | Reason | Text |", "|---|---|---|---|---|"]
    for f in findings:
        shown = rules.flagging.preview(f.text(original))
        out.append(f"| {f.line} | {f.kind} | {'yes' if f.blocking else 'no'} | {f.reason} | `{shown}` |")
    if not findings:
        out.append("| | | | nothing flagged | |")
    out.append("")
    return "\n".join(out)


def apply(review_text: str, name: str, rules: Rules, accept_residual: bool = False) -> tuple[str, int, list[str]]:
    """Validate tags, replace them, and re-check. Returns (final text, spans replaced, problems).

    Nothing is final if ``problems`` is not empty.
    """
    rules.redaction.validate_tags(review_text, name)  # raises PipelineError with the line
    final, count = rules.redaction.apply_redactions(review_text, rules.placeholder)
    problems = []
    for f in rules.redaction.residual_findings(final, rules.config, ROLE):
        where = f"{name}, line {f.line}"
        if f.blocking:
            problems.append(f"{where}: {f.reason} is still visible and may never be left (blocking)")
        elif not accept_residual:
            problems.append(f"{where}: {f.reason} is still visible (pass --accept-residual if that is intended)")
    return final, count, problems


def residual_in(text: str, rules: Rules) -> list:
    """What the rules would still flag in a text (used as a safety net on the notes digest)."""
    return rules.redaction.residual_findings(text, rules.config, "notes")
