"""Stage 6: the number of people registered, from the Zoom registration report.

Reads ``private/materials-YYYYMM/*registration*.csv`` and writes
``project-management/communications/blog-YYYYMM/registration-digest.md`` with the totals only.

The report lists every registrant's name, email, organisation and job title.
Those columns are never read into the output: the digest holds counts and
dates, nothing else. The total comes from the report's own summary row and is
cross-checked against the number of registrant rows listed beneath it.

The report is a snapshot. If it was generated before the meeting, later
registrations are missing, so the digest says so.
"""

from __future__ import annotations

import csv
import datetime
from dataclasses import dataclass
from pathlib import Path

DIGEST_NAME = "registration-digest.md"
TIME_FORMAT = "%m/%d/%Y %I:%M:%S %p"
SUMMARY_COLUMNS = {
    "registrants": "# Registrants",
    "cancelled": "# Cancelled registrants",
    "approved": "# Approved registrants",
    "denied": "# Denied registrants",
}


class RegistrationFormatError(ValueError):
    pass


@dataclass
class Registration:
    topic: str
    scheduled: datetime.datetime | None
    generated: datetime.datetime | None
    registrants: int
    cancelled: int
    approved: int
    denied: int
    listed: int

    @property
    def stale(self) -> bool:
        """True when the report was generated before the meeting began."""
        return bool(self.generated and self.scheduled and self.generated < self.scheduled)

    @property
    def consistent(self) -> bool:
        return self.listed == self.registrants


def parse_time(text: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.strptime(text.strip(), TIME_FORMAT)
    except ValueError:
        return None


def parse_report(rows: list[list[str]]) -> Registration:
    generated = None
    summary_header = None
    summary_values = None
    detail_start = None
    for index, row in enumerate(rows):
        first = row[0].strip() if row else ""
        if first == "Report generated time" and len(row) > 1:
            generated = parse_time(row[1])
        elif first == "Topic" and "# Registrants" in row:
            summary_header = row
            summary_values = rows[index + 1] if index + 1 < len(rows) else None
        elif first == "Attendee Details":
            detail_start = index + 1
    if summary_header is None or summary_values is None:
        raise RegistrationFormatError("no summary row found (looked for a 'Topic' header with '# Registrants')")

    def number(key: str) -> int:
        column = SUMMARY_COLUMNS[key]
        if column not in summary_header:
            raise RegistrationFormatError(f"summary has no '{column}' column")
        position = summary_header.index(column)
        try:
            return int(summary_values[position])
        except (IndexError, ValueError):
            raise RegistrationFormatError(f"'{column}' is not a number") from None

    listed = 0
    if detail_start is not None:
        # first row after "Attendee Details" is the column header
        listed = sum(1 for row in rows[detail_start + 1:] if any(cell.strip() for cell in row))

    def cell(name: str) -> str:
        return summary_values[summary_header.index(name)] if name in summary_header else ""

    return Registration(
        topic=cell("Topic").strip(),
        scheduled=parse_time(cell("Scheduled Time")),
        generated=generated,
        registrants=number("registrants"),
        cancelled=number("cancelled"),
        approved=number("approved"),
        denied=number("denied"),
        listed=listed,
    )


def build_digest(reg: Registration) -> str:
    out = ["# Registration digest", "",
           f"*Meeting: {reg.topic or 'unknown'}.*",
           "*Counts only: no registrant details are kept here.*", "",
           f"- Registered: **{reg.registrants}**",
           f"- Approved: {reg.approved}",
           f"- Cancelled: {reg.cancelled}",
           f"- Denied: {reg.denied}"]
    if reg.generated:
        out.append(f"- Report generated: {reg.generated:%d %B %Y, %H:%M}")
    if reg.scheduled:
        out.append(f"- Meeting scheduled: {reg.scheduled:%d %B %Y, %H:%M}")
    out.append("")
    if reg.stale:
        days = (reg.scheduled.date() - reg.generated.date()).days
        out += [f"<mark>The report was generated {days} days before the meeting, so people who "
                f"registered later are not counted. Download a fresh report after the meeting "
                f"to get the final number.</mark>", ""]
    if not reg.consistent:
        out += [f"<mark>The summary says {reg.registrants} registrants but {reg.listed} are "
                f"listed in the report. Check the file.</mark>", ""]
    return "\n".join(out)


def find_report(private_dir: Path) -> Path | None:
    """The registration report (*registration*.csv) in the raw materials folder."""
    if not private_dir.is_dir():
        return None
    found = sorted(p for p in private_dir.glob("*.csv") if "registration" in p.name.lower())
    if len(found) > 1:
        raise FileNotFoundError(
            f"more than one registration report in {private_dir}: {', '.join(p.name for p in found)}"
        )
    return found[0] if found else None


def run(private_dir: Path, blog_dir: Path) -> tuple[Path, Registration] | None:
    """Read the raw report in ``private_dir``; write registration-digest.md to ``blog_dir``. None when there is no report."""
    source = find_report(private_dir)
    if source is None:
        return None
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reg = parse_report(list(csv.reader(handle)))
    blog_dir.mkdir(parents=True, exist_ok=True)
    output = blog_dir / DIGEST_NAME
    output.write_text(build_digest(reg), encoding="utf-8")
    return output, reg
