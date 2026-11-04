"""Convert .docx materials to markdown. Markdown inputs pass through unchanged."""
from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from .common import PipelineError

LUA_FILTER = Path(__file__).with_name("flatten_tables.lua")


def _clean(text: str) -> tuple[str, dict]:
    """Remove conversion artefacts. Each fix is counted so it can be logged."""
    counts = {}

    def sub(name: str, pattern: str, repl, flags=0):
        nonlocal text
        text, n = re.subn(pattern, repl, text, flags=flags)
        if n:
            counts[name] = n

    sub("underline tags removed", r"</?u>", "")
    sub("empty spans removed", r"<span[^>]*></span>", "")
    sub("link text that repeated its URL simplified", r"\[(https?://[^\]\s]+)\]\(\1\)", r"\1")
    sub("empty headings removed", r"^#+[ \t]*\n", "", re.M)
    sub("runs of blank lines collapsed", r"\n{3,}", "\n\n")
    return text.strip() + "\n", counts


def docx_to_markdown(src: Path) -> tuple[str, dict, list[str]]:
    if not shutil.which("pandoc"):
        raise PipelineError("pandoc is not installed. Install it from https://pandoc.org/installing.html and retry.")
    warnings = []
    with zipfile.ZipFile(src) as archive:
        images = [n for n in archive.namelist() if n.startswith("word/media/") and not n.endswith("/")]
    if images:
        warnings.append(f"{src.name}: {len(images)} embedded image(s) are not carried over to the markdown.")

    result = subprocess.run(
        ["pandoc", str(src), "-f", "docx", "-t", "gfm", "--wrap=none", "--lua-filter", str(LUA_FILTER)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise PipelineError(f"pandoc could not convert {src.name}:\n{result.stderr.strip()}")
    text, counts = _clean(result.stdout)
    if "<table" in text:
        warnings.append(f"{src.name}: a table could not be converted to markdown and is kept as HTML.")
    return text, counts, warnings


def load_material(src: Path) -> tuple[str, dict, list[str]]:
    if src.suffix.lower() == ".docx":
        return docx_to_markdown(src)
    if src.suffix.lower() == ".md":
        return src.read_text(encoding="utf-8"), {}, []
    raise PipelineError(f"{src.name}: only .docx and .md files are supported. Export Google Docs before using them.")
