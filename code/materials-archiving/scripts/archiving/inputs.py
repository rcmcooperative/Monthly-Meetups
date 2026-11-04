"""Find the five expected inputs in a folder and say which are missing."""
from __future__ import annotations

from pathlib import Path

from .common import PipelineError

DOC_ROLES = ("comms", "briefing", "notes")
CSV_ROLES = ("participants", "poll")
ALL_ROLES = DOC_ROLES + CSV_ROLES

LABELS = {
    "comms": "Comms copy (.docx or .md)",
    "briefing": "Facilitators briefing (.docx or .md)",
    "notes": "Collab notes (.md or .docx)",
    "participants": "Zoom participants export (.csv)",
    "poll": "Zoom poll export (.csv)",
}

# A document is assigned to a role when its file name contains one of these words.
KEYWORDS = {
    "comms": ("comms",),
    "briefing": ("brief",),
    "notes": ("note", "collab"),
}


def sniff_csv(path: Path) -> str | None:
    """Recognise a Zoom export from its content, not its name."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    if lines[0].startswith("Topic,Type,ID,Host name"):
        return "participants"
    if lines[0].strip() == "Overview" and any(ln.startswith("Launched Polls") for ln in lines):
        return "poll"
    return None


def resolve_inputs(input_dir: Path, explicit: dict[str, str | None] | None = None):
    """Return (found, problems): found maps role -> Path, problems lists what to fix."""
    explicit = explicit or {}
    found: dict[str, Path] = {}
    problems: list[str] = []

    for role, given in explicit.items():
        if not given:
            continue
        path = Path(given)
        path = path if path.is_absolute() else input_dir / path
        if path.is_file():
            found[role] = path
        else:
            problems.append(f"{LABELS[role]}: file not found: {path}")

    files = sorted(p for p in input_dir.iterdir() if p.is_file() and not p.name.startswith("."))
    taken = set(found.values())

    docs = [
        p for p in files
        if p.suffix.lower() in (".docx", ".md")
        and not p.name.endswith(".review.md")
        and p not in taken
    ]
    claimed: dict[Path, list[str]] = {}
    hits_by_role: dict[str, list[Path]] = {}
    for role in DOC_ROLES:
        if role in found:
            continue
        hits = [p for p in docs if any(k in p.stem.lower() for k in KEYWORDS[role])]
        hits_by_role[role] = hits
        for p in hits:
            claimed.setdefault(p, []).append(role)

    for role, hits in hits_by_role.items():
        if len(hits) == 1 and len(claimed[hits[0]]) == 1:
            found[role] = hits[0]
        elif len(hits) > 1 or (hits and len(claimed[hits[0]]) > 1):
            names = ", ".join(p.name for p in hits)
            problems.append(
                f"{LABELS[role]}: more than one candidate ({names}). "
                f"Name the file with --{role}."
            )

    # Collab notes often carry the meetup's own title, so fall back to the one unclaimed .md file.
    if "notes" not in found and not hits_by_role.get("notes"):
        spare = [
            p for p in docs
            if p.suffix.lower() == ".md" and p not in found.values() and p not in claimed
        ]
        if len(spare) == 1:
            found["notes"] = spare[0]

    csvs: dict[str, list[Path]] = {"participants": [], "poll": []}
    for p in files:
        if p.suffix.lower() == ".csv" and p not in found.values():
            kind = sniff_csv(p)
            if kind:
                csvs[kind].append(p)
    for role in CSV_ROLES:
        if role in found:
            continue
        if len(csvs[role]) == 1:
            found[role] = csvs[role][0]
        elif len(csvs[role]) > 1:
            names = ", ".join(p.name for p in csvs[role])
            problems.append(f"{LABELS[role]}: more than one candidate ({names}). Name the file with --{role}.")

    for role in ALL_ROLES:
        if role not in found and not any(pr.startswith(LABELS[role]) for pr in problems):
            problems.append(f"{LABELS[role]}: not found in {input_dir}")
    return found, problems


def checklist(found: dict[str, Path], problems: list[str]) -> str:
    lines = ["Inputs:"]
    for role in ALL_ROLES:
        mark = "ok     " if role in found else "MISSING"
        where = found[role].name if role in found else ""
        lines.append(f"  [{mark}] {LABELS[role]:<40} {where}")
    if problems:
        lines.append("")
        lines.append("To fix:")
        lines.extend(f"  - {p}" for p in problems)
    return "\n".join(lines)


def require_inputs(input_dir: Path, explicit=None) -> dict[str, Path]:
    found, problems = resolve_inputs(input_dir, explicit)
    print(checklist(found, problems))
    if problems:
        raise PipelineError("Not all inputs are present or unambiguous. Nothing has been processed.")
    return found
