"""Where inputs live and where outputs go.

Inputs:   <repo>/private/materials-YYYYMM/   (git-ignored; holds unredacted material)
Outputs:  <repo>/docs/materials-YYYYMM/      (public; `docs/` must already exist)

YYYYMM is the year and month of the session. Run from the repository root.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .common import PipelineError

MONTH_RE = re.compile(r"^\d{4}(0[1-9]|1[0-2])$")
FOLDER_RE = re.compile(r"^materials-(\d{4})(0[1-9]|1[0-2])$")


def resolve_dirs(month: str | None, input_dir: str | None, output_dir: str | None,
                 cwd: Path | None = None) -> tuple[Path, Path]:
    """Return (input folder, output folder). Nothing is created here."""
    if month:
        if not MONTH_RE.match(month):
            raise PipelineError(f"--month must be the session's year and month as YYYYMM, for example 202610 (got {month!r}).")
        repo = Path(cwd) if cwd else Path.cwd()
        if not (repo / "private").is_dir():
            raise PipelineError(
                f"There is no 'private' folder in {repo}.\n"
                "Run this from the Monthly-Meetups repository root, "
                f"after creating private/materials-{month} and downloading the input files into it."
            )
        inp = repo / "private" / f"materials-{month}"
    elif input_dir:
        inp = Path(input_dir)
        repo = inp.resolve().parent.parent
    else:
        raise PipelineError("Give --month YYYYMM (or --input-dir).")

    if not inp.is_dir():
        name = inp.name if FOLDER_RE.match(inp.name) else f"materials-{month or 'YYYYMM'}"
        raise PipelineError(
            f"Input folder not found: {inp.resolve()}\n"
            f"Create it and download the five input files into it:\n  mkdir -p private/{name}"
        )
    inp = inp.resolve()
    if not FOLDER_RE.match(inp.name):
        raise PipelineError(
            f"The input folder must be named materials-YYYYMM (year and month of the session), not {inp.name!r}."
        )
    if not output_dir and inp.parent.name != "private":
        raise PipelineError(
            f"The input folder should be inside a 'private' folder, but it is in {inp.parent}.\n"
            "Move it to private/, or give --output-dir."
        )

    out = Path(output_dir).resolve() if output_dir else repo.resolve() / "docs" / inp.name
    if not out.parent.is_dir():
        raise PipelineError(
            f"The folder {out.parent} does not exist.\n"
            "The output goes in docs/materials-YYYYMM, and docs/ must already exist in the repository."
        )
    return inp, out


def check_month_matches(folder_name: str, meeting_date: str) -> None:
    """The folder's YYYYMM must be the month of the meeting in the Zoom export."""
    m = FOLDER_RE.match(folder_name)
    if m and f"{m.group(1)}{m.group(2)}" != meeting_date[:7].replace("-", ""):
        raise PipelineError(
            f"The folder is named {folder_name}, but the Zoom export says the meeting was on {meeting_date}.\n"
            f"Use materials-{meeting_date[:7].replace('-', '')}, or check that you downloaded the right files."
        )


def ensure_private_is_ignored(input_dir: Path) -> str:
    """Stop if git would track the input folder. Skipped (with a note) outside a git repository."""
    git = shutil.which("git")
    if not git:
        return "git not found: could not check that private/ is excluded by .gitignore"
    probe = input_dir / "review" / "flag-report.md"
    result = subprocess.run([git, "-C", str(input_dir), "check-ignore", "-q", str(probe)], capture_output=True)
    if result.returncode == 0:
        return "private/ is excluded by .gitignore"
    if result.returncode == 1:
        raise PipelineError(
            f"{input_dir} is not excluded by .gitignore, and it will hold unredacted material.\n"
            "Add this line to the repository's .gitignore, then run again:\n  private/"
        )
    return "not a git repository: could not check that private/ is excluded by .gitignore"
