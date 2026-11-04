"""Plain-text reports. The processing log holds counts only: no names, emails or URLs."""
from __future__ import annotations

from .common import VERSION
from .flagging import Finding, preview

DOC_TITLES = {
    "comms": "Comms copy",
    "briefing": "Facilitators briefing",
    "notes": "Collab notes",
}


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("`", "'")


def flag_report(entries: list[dict]) -> str:
    """entries: {role, review_file, text, findings}. Contains the flagged text: keep it private."""
    lines = [
        "# Redaction review: flagged items",
        "",
        "**This report contains the text that was flagged. Do not commit or share it.**",
        "",
        "Open each `*.review.md` file and look at every `<redact>…</redact>` span.",
        "Delete the tags around anything that should stay visible.",
        "Wrap anything else that should go in `<redact>…</redact>`.",
        "When you are happy, run the `apply` step.",
        "",
    ]
    for e in entries:
        findings: list[Finding] = e["findings"]
        lines += [f"## {DOC_TITLES[e['role']]} (`{e['review_file']}`)", ""]
        if not findings:
            lines += ["Nothing flagged.", ""]
            continue
        lines += ["| Line | Kind | Why | Text |", "| ---: | --- | --- | --- |"]
        for f in findings:
            lines.append(f"| {f.line} | {f.kind} | {_cell(f.reason)} | {_cell(preview(f.text(e['text'])))} |")
        lines.append("")
    return "\n".join(lines)


def processing_log(manifest: dict, apply_info: dict) -> str:
    lines = [
        f"# Processing log: {manifest['topic']}",
        "",
        f"Meeting date: {manifest['date']}",
        f"Prepared with materials-archiving {VERSION}.",
        "",
        "This log records what was done, as counts only.",
        "It contains no names, email addresses or links.",
        "",
        "## Inputs",
        "",
    ]
    for role, info in manifest["inputs"].items():
        lines.append(f"- {role}: `{info['name']}` (SHA-256 `{info['sha256'][:16]}…`)")
    lines += ["", "## Documents", ""]
    for role, d in manifest["docs"].items():
        a = apply_info["docs"][role]
        lines.append(f"### {DOC_TITLES[role]}")
        lines.append("")
        lines.append(f"- Items flagged for review: {d['flagged']} ({_kinds(d['by_kind'])})")
        lines.append(f"- Redactions applied after review: {a['redacted']}")
        if a["left_visible"]:
            lines.append(f"- Unlisted items left visible by choice (`--accept-residual`): {a['left_visible']}")
        for name, n in d["cleanups"].items():
            lines.append(f"- Conversion clean-up: {name} ({n})")
        for w in d["warnings"]:
            lines.append(f"- Warning: {w}")
        lines.append("- Checks passed: tags balanced, no always-flag item remains")
        lines.append("")
    p, q = manifest["participants"], manifest["poll"]
    lines += [
        "## Zoom participants",
        "",
        f"- Rows in export: {p['rows_total']}; other meetings removed: {p['rows_other_meetings']}",
        f"- Session rows for this meeting: {p['rows_selected']}, merged to {p['people']} people "
        "(first join to last leave, waiting room included)",
        f"- Columns removed or replaced: {', '.join(p['columns_removed'])}",
        "- Participant IDs are random and no key was kept",
        "- Checks passed: no email addresses outside the host columns, IDs unique",
        "",
        "## Zoom poll",
        "",
        f"- Response tables: {q['response_tables']}; responses: {q['responses']}",
        f"- Columns removed: {', '.join(q['columns_removed'])}",
        "- Checks passed: no email addresses, removed columns absent",
        "",
    ]
    return "\n".join(lines)


def _kinds(by_kind: dict) -> str:
    return ", ".join(f"{n} {k}" for k, n in sorted(by_kind.items())) or "none"
