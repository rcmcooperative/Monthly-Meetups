"""Apply confirmed redactions and check that nothing sensitive is left behind."""
from __future__ import annotations

import re

from .common import PipelineError
from .flagging import Finding, find_findings

OPEN, CLOSE = "<redact>", "</redact>"
TAG_RE = re.compile(r"<redact>.*?</redact>", re.S)
# A markdown link whose destination is redacted: [text](<redact>…</redact>), brackets possibly escaped.
LINK_RE = re.compile(r"\\?\[([^\]\n]*?)\\?\]\(<redact>.*?</redact>\)", re.S)


def validate_tags(text: str, name: str) -> None:
    """Every <redact> must be closed, and tags must not be nested."""
    depth, line = 0, 1
    for m in re.finditer(r"</?redact>|\n", text):
        token = m.group(0)
        if token == "\n":
            line += 1
        elif token == OPEN:
            if depth:
                raise PipelineError(f"{name}, line {line}: a <redact> tag is opened inside another. Nesting is not allowed.")
            depth = 1
        else:
            if not depth:
                raise PipelineError(f"{name}, line {line}: a </redact> tag has no matching <redact>.")
            depth = 0
    if depth:
        raise PipelineError(f"{name}: a <redact> tag is never closed.")


def apply_redactions(text: str, placeholder: str) -> tuple[str, int]:
    """Replace each <redact> span with the placeholder. Returns (new text, spans replaced)."""
    total = len(TAG_RE.findall(text))
    text = LINK_RE.sub(lambda m: f"{m.group(1)} ({placeholder})", text)
    text = TAG_RE.sub(placeholder, text)
    return text, total


def residual_findings(text: str, config: dict, role: str) -> list[Finding]:
    """Run the same detectors over the final text. Anything found was left visible."""
    return find_findings(text, config, role)
