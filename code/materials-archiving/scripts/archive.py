#!/usr/bin/env python3
"""materials-archiving: prepare monthly meetup materials for public archiving.

Run from the repository root (Monthly-Meetups), for example:

  python code/materials-archiving/scripts/archive.py check   --month 202610 --topic "TOPIC"
  python code/materials-archiving/scripts/archive.py prepare --month 202610 --topic "TOPIC"
  (review and edit the files in private/materials-202610/review/)
  python code/materials-archiving/scripts/archive.py apply   --month 202610

Inputs are read from private/materials-YYYYMM/ (git-ignored), where the review files are also written.
The archive files are written to docs/materials-YYYYMM/, which is created if docs/ exists.
See HOW_TO_USE.md.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from archiving import convert, flagging, inputs, layout, redaction, report, zoom  # noqa: E402
from archiving.common import PipelineError, VERSION, load_config, sha256  # noqa: E402

STEMS = {
    "comms": "comms-copy",
    "briefing": "facilitators-briefing",
    "notes": "collab-notes",
}
ZOOM_NAMES = {"participants": "zoom-participants.csv", "poll": "zoom-poll.csv"}


def _explicit(args) -> dict:
    return {role: getattr(args, role, None) for role in inputs.ALL_ROLES}


def _check(args, config) -> tuple[Path, Path, dict, dict, dict]:
    input_dir, output_dir = layout.resolve_dirs(args.month, args.input_dir, args.output_dir)
    print(f"Input folder:  {input_dir}\nOutput folder: {output_dir}\n")
    print(layout.ensure_private_is_ignored(input_dir) + "\n")
    found = inputs.require_inputs(input_dir, _explicit(args))
    if any(p.suffix.lower() == ".docx" for p in found.values()):
        if not shutil.which("pandoc"):
            raise PipelineError("pandoc is not installed. Install it from https://pandoc.org/installing.html")
    pinfo = zoom.validate_participants(found["participants"], config["zoom"], args.topic)
    qinfo = zoom.validate_poll(found["poll"], config["zoom"])
    layout.check_month_matches(input_dir.name, pinfo["date"])
    print(
        f"\nZoom exports match the expected format.\n"
        f"  Meeting date {pinfo['date']}: {pinfo['rows_selected']} session rows for the topic, "
        f"{pinfo['rows_other_meetings']} rows from other meetings will be dropped.\n"
        f"  Poll response tables: {qinfo['response_tables']}"
    )
    return input_dir, output_dir, found, pinfo, qinfo


def cmd_check(args) -> None:
    config = load_config(args.config_dir)
    _check(args, config)
    print("\nAll checks passed. Nothing has been written.")


def cmd_prepare(args) -> None:
    config = load_config(args.config_dir)
    input_dir, output_dir, found, pinfo, _ = _check(args, config)
    review = input_dir / "review"

    targets = [review / f"{STEMS[r]}.review.md" for r in inputs.DOC_ROLES]
    targets += [review / n for n in ZOOM_NAMES.values()]
    targets += [review / "flag-report.md", review / "manifest.json"]
    existing = [t.name for t in targets if t.exists()]
    if existing and not args.force:
        raise PipelineError(
            f"These files already exist in {review}: {', '.join(existing)}.\n"
            "Running prepare again would overwrite any edits you have made. Use --force to replace them."
        )
    review.mkdir(exist_ok=True)

    manifest = {
        "version": VERSION,
        "topic": args.topic,
        "date": pinfo["date"],
        "inputs": {r: {"name": p.name, "sha256": sha256(p)} for r, p in found.items()},
        "docs": {},
    }
    entries = []
    for role in inputs.DOC_ROLES:
        text, cleanups, warnings = convert.load_material(found[role])
        findings = flagging.find_findings(text, config, role)
        review_name = f"{STEMS[role]}.review.md"
        (review / review_name).write_text(flagging.wrap_findings(text, findings), encoding="utf-8")
        manifest["docs"][role] = {
            "review_file": review_name,
            "flagged": len(findings),
            "by_kind": dict(Counter(f.kind for f in findings)),
            "cleanups": cleanups,
            "warnings": warnings,
        }
        entries.append({"role": role, "review_file": review_name, "text": text, "findings": findings})
        for w in warnings:
            print(f"  warning: {w}")

    (review / "flag-report.md").write_text(report.flag_report(entries), encoding="utf-8")
    manifest["participants"] = zoom.process_participants(
        found["participants"], config["zoom"], args.topic, review / ZOOM_NAMES["participants"]
    )
    manifest["poll"] = zoom.process_poll(found["poll"], config["zoom"], review / ZOOM_NAMES["poll"])
    (review / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nPrepared. Files are in {review}\n")
    for e in entries:
        print(f"  {e['review_file']:<36} {len(e['findings'])} items flagged")
    print(
        "\nNext:\n"
        "  1. Read review/flag-report.md, then edit the three *.review.md files.\n"
        "     Delete <redact> tags around anything that should stay; add them around anything else.\n"
        "  2. Look at review/zoom-participants.csv and review/zoom-poll.csv.\n"
        f"  3. Run the apply step. The archive files will be written to {output_dir}.\n"
        "The review folder holds unredacted material. Do not commit or share it."
    )


def _mask(value: str) -> str:
    return value[:6] + "…" if len(value) > 6 else "…"


def _verify_participants(path: Path, config: dict, expected_people: int) -> None:
    import csv
    rows = list(csv.reader(open(path, newline="", encoding="utf-8")))
    header, body = rows[0], rows[1:]
    if "Email" in header or config["zoom"]["participants"]["name_column"] in header:
        raise PipelineError(f"{path.name}: a name or email column is still present.")
    pid = header.index("Participant ID")
    ids = [r[pid] for r in body]
    for value in ids:
        uuid.UUID(value)
    if len(set(ids)) != len(ids):
        raise PipelineError(f"{path.name}: participant IDs are not unique.")
    if len(body) != expected_people:
        raise PipelineError(f"{path.name}: expected {expected_people} people, found {len(body)}.")
    host_ok = {i for i, h in enumerate(header) if h == "Host email"}
    for n, r in enumerate(body, start=2):
        for i, cell in enumerate(r):
            if "@" in cell and i not in host_ok:
                raise PipelineError(f"{path.name}, line {n}: an '@' remains in column '{header[i]}'.")


def _verify_poll(path: Path, config: dict) -> None:
    text = path.read_text(encoding="utf-8")
    if "@" in text:
        raise PipelineError(f"{path.name}: an '@' remains in the poll file.")
    for column in config["zoom"]["poll"]["drop_columns"]:
        if column in text:
            raise PipelineError(f"{path.name}: the column '{column}' is still present.")


def cmd_apply(args) -> None:
    config = load_config(args.config_dir)
    input_dir, archive = layout.resolve_dirs(args.month, args.input_dir, args.output_dir)
    review = input_dir / "review"
    manifest_path = review / "manifest.json"
    if not manifest_path.is_file():
        raise PipelineError(f"{manifest_path} not found. Run the prepare step first, from the same input folder.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    placeholder = config["redaction"]["placeholder"]
    date = manifest["date"]
    layout.check_month_matches(input_dir.name, date)

    outputs: dict[str, str] = {}
    apply_info = {"docs": {}}
    errors: list[str] = []

    for role in inputs.DOC_ROLES:
        name = manifest["docs"][role]["review_file"]
        path = review / name
        if not path.is_file():
            errors.append(f"{name}: not found in {review}.")
            continue
        text = path.read_text(encoding="utf-8")
        try:
            redaction.validate_tags(text, name)
        except PipelineError as err:
            errors.append(str(err))
            continue
        final, count = redaction.apply_redactions(text, placeholder)
        residual = redaction.residual_findings(final, config, role)
        blocking = [f for f in residual if f.blocking]
        optional = [f for f in residual if not f.blocking]
        for f in blocking:
            errors.append(
                f"{name}, line {f.line}: still visible and must be redacted ({f.reason}): {_mask(f.text(final))}"
            )
        if optional and not args.accept_residual:
            for f in optional:
                errors.append(
                    f"{name}, line {f.line}: left visible ({f.reason}): {_mask(f.text(final))}"
                )
        outputs[f"{STEMS[role]}.md"] = final
        apply_info["docs"][role] = {
            "redacted": count,
            "left_visible": len(optional) if args.accept_residual else 0,
        }

    p_path, q_path = review / ZOOM_NAMES["participants"], review / ZOOM_NAMES["poll"]
    for path in (p_path, q_path):
        if not path.is_file():
            errors.append(f"{path.name}: not found in {review}.")
    if p_path.is_file():
        try:
            _verify_participants(p_path, config, manifest["participants"]["people"])
        except (PipelineError, ValueError) as err:
            errors.append(str(err))
    if q_path.is_file():
        try:
            _verify_poll(q_path, config)
        except PipelineError as err:
            errors.append(str(err))

    if errors:
        listing = "\n".join(f"  - {e}" for e in errors)
        hint = ""
        if any("left visible" in e for e in errors):
            hint = ("\nIf these should stay visible, run again with --accept-residual. "
                    "Items marked 'must be redacted' cannot be accepted.")
        raise PipelineError(f"Nothing has been written. Please fix:\n{listing}{hint}")

    names = list(outputs) + [n for n in ZOOM_NAMES.values()] + ["processing-log.md"]
    clash = [n for n in names if (archive / n).exists()]
    if clash and not args.force:
        raise PipelineError(f"These files already exist in {archive}: {', '.join(clash)}. Use --force to replace them.")

    archive.mkdir(exist_ok=True)  # docs/ must already exist; only materials-YYYYMM is created
    for name, text in outputs.items():
        (archive / name).write_text(text, encoding="utf-8")
    (archive / "zoom-participants.csv").write_bytes(p_path.read_bytes())
    (archive / "zoom-poll.csv").write_bytes(q_path.read_bytes())
    (archive / "processing-log.md").write_text(report.processing_log(manifest, apply_info), encoding="utf-8")

    print(f"Archive files written to {archive}:\n")
    for n in sorted(names):
        print(f"  {n}")
    print("\nAll checks passed. Check the files once more, then add them to the archive.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archive.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config-dir", help="folder holding redaction.toml and zoom_schema.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, topic=True):
        where = p.add_mutually_exclusive_group(required=True)
        where.add_argument("--month", help="session year and month, YYYYMM: uses private/materials-YYYYMM "
                                           "(run from the repository root)")
        where.add_argument("--input-dir", help="input folder, normally private/materials-YYYYMM")
        p.add_argument("--output-dir", help="output folder; default is docs/materials-YYYYMM next to private/")
        if topic:
            p.add_argument("--topic", required=True,
                           help="meeting topic exactly as in the 'Topic' column of the Zoom participants CSV")
            for role in inputs.ALL_ROLES:
                p.add_argument(f"--{role}", help=f"file name for the {role} input, if it cannot be detected")

    p = sub.add_parser("check", help="check the inputs and Zoom formats; writes nothing")
    common(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("prepare", help="convert, flag redactions, anonymise Zoom files into review/")
    common(p)
    p.add_argument("--force", action="store_true", help="overwrite existing files in review/")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("apply", help="apply the reviewed redactions, verify, write docs/materials-YYYYMM")
    common(p, topic=False)
    p.add_argument("--accept-residual", action="store_true",
                   help="allow non-allowlisted URLs/emails you chose to leave visible")
    p.add_argument("--force", action="store_true", help="overwrite existing files in the output folder")
    p.set_defaults(func=cmd_apply)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except PipelineError as err:
        print(f"\nSTOPPED: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
