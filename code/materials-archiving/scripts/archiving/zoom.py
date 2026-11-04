"""Validate and anonymise the two Zoom exports.

Both exports are checked against config/zoom_schema.toml before anything is written.
No names or emails are kept, and no key linking the new IDs back to people is stored.
"""
from __future__ import annotations

import csv
import uuid
from datetime import datetime
from pathlib import Path

from .common import PipelineError


def _read_rows(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.reader(handle))


def _write_rows(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows(rows)


def _header_diff(expected: list[str], found: list[str]) -> str:
    lines = [f"  expected {len(expected)} columns, found {len(found)}"]
    for i in range(max(len(expected), len(found))):
        e = expected[i] if i < len(expected) else "(none)"
        f = found[i] if i < len(found) else "(none)"
        if e != f:
            lines.append(f"  column {i + 1}: expected {e!r}, found {f!r}")
    return "\n".join(lines[:12])


# --- participants -----------------------------------------------------------------------------

def validate_participants(path: Path, schema: dict, topic: str) -> dict:
    cfg = schema["participants"]
    rows = [r for r in _read_rows(path) if r]
    if not rows:
        raise PipelineError(f"{path.name}: the file is empty.")
    header, body = rows[0], rows[1:]
    if header != cfg["columns"]:
        raise PipelineError(
            f"{path.name}: the Zoom participants export does not have the expected columns.\n"
            f"{_header_diff(cfg['columns'], header)}\n"
            "Zoom may have changed its format. Check the file, then update config/zoom_schema.toml."
        )
    short = [i for i, r in enumerate(body, start=2) if len(r) != len(header)]
    if short:
        raise PipelineError(f"{path.name}: rows with the wrong number of fields at lines {short[:5]}.")

    t = header.index("Topic")
    topics = sorted({r[t] for r in body})
    selected = [r for r in body if r[t] == topic]
    if not selected:
        listing = "\n".join(f"    - {x}" for x in topics)
        raise PipelineError(
            f"{path.name}: no rows have the topic {topic!r}.\n"
            "The topic must match the 'Topic' column of the participants file exactly. Topics found:\n"
            f"{listing}"
        )

    type_i = header.index("Type")
    bad_types = sorted({r[type_i] for r in selected} - set(cfg["allowed_types"]))
    if bad_types:
        raise PipelineError(f"{path.name}: unexpected meeting Type {bad_types} (expected {cfg['allowed_types']}).")

    for column in cfg["time_columns"]:
        i = header.index(column)
        for r in selected:
            try:
                datetime.strptime(r[i], cfg["time_format"])
            except ValueError:
                raise PipelineError(
                    f"{path.name}: '{column}' is not in the expected date format "
                    f"{cfg['time_format']} (found {r[i]!r})."
                )

    key_i = header.index(cfg["person_key"])
    blank = sum(1 for r in selected if not r[key_i].strip())
    if blank:
        raise PipelineError(
            f"{path.name}: {blank} rows for this meeting have no '{cfg['person_key']}', "
            "so sessions cannot be matched to people. Nothing has been processed."
        )

    start = datetime.strptime(selected[0][header.index("Start time")], cfg["time_format"])
    return {
        "rows_total": len(body),
        "rows_selected": len(selected),
        "rows_other_meetings": len(body) - len(selected),
        "date": start.strftime("%Y-%m-%d"),
    }


def process_participants(path: Path, schema: dict, topic: str, dest: Path) -> dict:
    info = validate_participants(path, schema, topic)
    cfg = schema["participants"]
    rows = [r for r in _read_rows(path) if r]
    header, body = rows[0], rows[1:]
    fmt = cfg["time_format"]

    t = header.index("Topic")
    selected = [r for r in body if r[t] == topic]

    # The last "Duration (minutes)" is the participant's own duration.
    dur_i = max(i for i, h in enumerate(header) if h == "Duration (minutes)")
    key_i = header.index(cfg["person_key"])
    name_i = header.index(cfg["name_column"])
    join_i, leave_i = header.index("Join time"), header.index("Leave time")
    guest_i = header.index("Guest")
    rec_i = header.index("Recording disclaimer response")
    wait_i = header.index("In waiting room")

    people: dict[str, list[list[str]]] = {}
    for r in selected:
        people.setdefault(r[key_i].strip().lower(), []).append(r)

    dropped = {"Email", "In waiting room", *cfg.get("drop_columns", [])}
    keep = [i for i, h in enumerate(header) if h not in dropped]

    out_header = [("Participant ID" if i == name_i else header[i]) for i in keep] + ["Sessions merged"]
    out_rows = []
    for sessions in people.values():
        sessions.sort(key=lambda s: datetime.strptime(s[join_i], fmt))
        first = list(sessions[0])
        joins = [datetime.strptime(s[join_i], fmt) for s in sessions]
        leaves = [datetime.strptime(s[leave_i], fmt) for s in sessions]
        join, leave = min(joins), max(leaves)
        first[join_i] = join.strftime(fmt)
        first[leave_i] = leave.strftime(fmt)
        first[dur_i] = str(round((leave - join).total_seconds() / 60))
        first[guest_i] = "Yes" if any(s[guest_i] == "Yes" for s in sessions) else sessions[0][guest_i]
        responses = [s[rec_i] for s in sessions]
        first[rec_i] = "OK" if "OK" in responses else responses[0]
        first[name_i] = str(uuid.uuid4())
        out_rows.append((join, [first[i] for i in keep] + [str(len(sessions))]))
    out_rows.sort(key=lambda x: x[0])

    _write_rows(dest, [out_header] + [r for _, r in out_rows])
    waiting = sum(1 for r in selected if r[wait_i] == "Yes")
    info.update({
        "people": len(people),
        "sessions_merged": len(selected),
        "waiting_room_rows": waiting,
        "columns_removed": sorted(dropped | {cfg["name_column"] + " (replaced by Participant ID)"}),
    })
    return info


# --- poll -------------------------------------------------------------------------------------

def _is_response_header(row: list[str]) -> bool:
    return bool(row) and row[0] == "#" and len(row) > 1 and row[1] != "Poll Name"


def validate_poll(path: Path, schema: dict) -> dict:
    cfg = schema["poll"]
    rows = _read_rows(path)
    nonblank = [r for r in rows if any(c.strip() for c in r)]
    if not nonblank or nonblank[0][0].strip() != "Overview":
        raise PipelineError(f"{path.name}: the Zoom poll export should start with an 'Overview' section.")
    if len(nonblank) < 2:
        raise PipelineError(f"{path.name}: the poll export is too short to contain an Overview table.")
    if nonblank[1][: len(cfg["overview_columns"])] != cfg["overview_columns"]:
        raise PipelineError(
            f"{path.name}: the Overview section does not have the expected columns.\n"
            f"{_header_diff(cfg['overview_columns'], nonblank[1])}"
        )
    try:
        launched = next(i for i, r in enumerate(nonblank) if r and r[0].strip() == "Launched Polls")
    except StopIteration:
        raise PipelineError(f"{path.name}: no 'Launched Polls' section found.")
    if launched + 1 >= len(nonblank):
        raise PipelineError(f"{path.name}: the Launched Polls section has no table.")
    if nonblank[launched + 1][: len(cfg["launched_columns"])] != cfg["launched_columns"]:
        raise PipelineError(
            f"{path.name}: the Launched Polls table does not have the expected columns.\n"
            f"{_header_diff(cfg['launched_columns'], nonblank[launched + 1])}"
        )
    prefix = cfg["response_prefix"]
    tables = 0
    for r in nonblank:
        if _is_response_header(r):
            tables += 1
            if r[: len(prefix)] != prefix or len(r) <= len(prefix):
                raise PipelineError(
                    f"{path.name}: a poll response table does not have the expected columns "
                    f"(expected {prefix} followed by at least one question).\n"
                    f"{_header_diff(prefix, r)}"
                )
    if tables == 0:
        raise PipelineError(f"{path.name}: no poll response table found.")
    return {"response_tables": tables}


def process_poll(path: Path, schema: dict, dest: Path) -> dict:
    info = validate_poll(path, schema)
    drop = set(schema["poll"]["drop_columns"])
    out, in_table, drop_idx, removed, responses = [], False, [], 0, 0
    for row in _read_rows(path):
        if not any(c.strip() for c in row):
            in_table = False
        elif _is_response_header(row):
            in_table = True
            drop_idx = sorted((i for i, h in enumerate(row) if h in drop), reverse=True)
        elif in_table:
            responses += 1
        if in_table:
            for i in drop_idx:
                if i < len(row):
                    del row[i]
                    removed += 1
        out.append(row)
    _write_rows(dest, out)
    info.update({"responses": responses, "cells_removed": removed, "columns_removed": sorted(drop)})
    return info
