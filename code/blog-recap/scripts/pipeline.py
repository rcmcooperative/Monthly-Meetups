#!/usr/bin/env python3
"""Single entrypoint for the meetup blog pipeline.

Run from the repo root, in two parts.

1. Before opening Claude Code, in your own terminal (everything that touches names):

       python code/blog-recap/scripts/pipeline.py --month 202610 --prepare

2. In Claude Code, which only ever sees the anonymised results:

       python code/blog-recap/scripts/pipeline.py --month 202610 [flags]

``--month`` is the meetup's YYYYMM. It defaults to the current month, but a recap is
usually written the month after the meetup, so pass it explicitly.

Three folders are involved:

    private/materials-YYYYMM/                     raw Zoom chat and registration report
                                                  (names and emails; Claude Code is denied access)
    docs/materials-YYYYMM/                        the archived material (briefing, collaborative
                                                  notes, poll, invitation text, slides), made
                                                  by the materials-archiving scripts
    project-management/communications/blog-YYYYMM/  everything this pipeline makes: anonymised chat,
                                                  digests, saved answers, reviews, the draft post

Part 1: --prepare (deterministic Python only; the only stages that read names)
    1. anonymise-chat   Zoom chat export (private/) -> <name>_anonymised.review.txt in private/,
                        with every URL or email the redaction rules do not allow flagged in
                        <redact></redact> tags. The rules are those of materials-archiving.
                        You review the flags, then run --prepare --apply, which writes
                        <name>_anonymised.txt to the blog folder (the chat Claude is given).
    2. notes-digest     collab notes (docs/)        -> notes-digest.md
                        (participant list stripped first, names removed, exercises
                        and breakout rooms kept)
    3. registration-count  Zoom registration report (private/) -> registration-digest.md
                        (totals only: no registrant details are kept)
    Nothing is written to a digest if a name is found in it, and the run stops.

    python code/blog-recap/scripts/pipeline.py --month 202610 --prepare --apply
        applies the reviewed redactions. Tags are validated, replaced with a placeholder
        and the result re-checked: a blocking item (Zoom, Slack, CryptPad, credentials)
        left visible stops the run; so does any other URL or email, unless --accept-residual.

Part 2: the main run (Claude Code can run this: it never reads private/)
    1. session-inputs   what only the facilitator knows -> session-inputs.json
                        links (--register-url, --recording-url or 'none', --archive-url),
                        authors (--author, --external-author), and the next session's date,
                        time and theme, which it tries to read from the Zoom registration
                        page (otherwise --next-date, --next-time, --next-theme).
                        Saved, so each is asked for once; stops here if any is missing.
    2. chat-digest      anonymised chat + briefing -> chat-digest.md
                        (purpose, agenda, reactions, links shared)
    3. poll-digest      Zoom poll CSV (docs/) -> poll-digest.md
                        (responses, % at each Likert point per question)
    4. comms-copy       invitation text (docs/) -> host, speaker (names, links, roles) and
                        theme, added to session-inputs.json
    5. blog-links       -> blog-links.md (authors front matter, host and speaker sentence,
                        links, "Join us next time")
    It stops and says so if --prepare has not been run.

Once, before using Claude Code:

    python code/blog-recap/scripts/pipeline.py --setup-claude
        adds a deny rule for private/ to .claude/settings.json (created if missing,
        merged if it exists; existing settings are kept).

Checks, run after Claude has written the reviews and the draft:

    python code/blog-recap/scripts/pipeline.py --month 202610 --check
        every exercise task has a status row; the draft post has no leftover placeholders,
        room numbers, private links or registrant names (add --final once the header image
        and every highlight are resolved). It reads the raw registration report to look for
        registrant names, and never prints them.

The interpretive steps (reviewing the chat and the collaborative notes against
the event purpose and exercises) are done by Claude after the pipeline, reading
the digests. Reviews are saved in the blog folder's review/ subfolder.
See HOW_TO_USE.md and SKILL.md.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import anonymise_chat  # noqa: E402
import chat_digest  # noqa: E402
import check_draft  # noqa: E402
import claude_settings  # noqa: E402
import comms_copy  # noqa: E402
import config  # noqa: E402
import exercise_tasks  # noqa: E402
import link_redaction  # noqa: E402
import notes_digest  # noqa: E402
import poll_digest  # noqa: E402
import registration_count  # noqa: E402
import session_inputs  # noqa: E402

MONTH_RE = re.compile(r"^\d{6}$")
FILENAME_DATE_RE = re.compile(r"GMT(\d{6})\d{2}")


def blog_dir_for(month: str) -> Path:
    return Path.cwd() / config.OUTPUT_DIR / f"{config.BLOG_PREFIX}{month}"


def resolve_materials_dir(root: str, month: str) -> Path:
    base = Path.cwd() / root
    if not base.is_dir():
        raise SystemExit(
            f"ERROR: no '{root}/' folder in {Path.cwd()}. Run this from the repo root."
        )
    target = base / f"{config.MATERIALS_PREFIX}{month}"
    if not target.is_dir():
        existing = sorted(
            p.name for p in base.iterdir()
            if p.is_dir() and p.name.startswith(config.MATERIALS_PREFIX)
        )
        raise SystemExit(
            f"ERROR: {target} does not exist. "
            f"Available in {root}/: {', '.join(existing) or '(none)'}"
        )
    return target


def warn_on_month_mismatch(reports: list[anonymise_chat.Report], month: str) -> None:
    for report in reports:
        found = FILENAME_DATE_RE.search(report.source.name)
        if found and found.group(1) != month:
            print(
                f"WARNING: {report.source.name} looks like a {found.group(1)} "
                f"recording but is in the {month} folder.",
                file=sys.stderr,
            )


def run_review_checks(docs_dir: Path, month: str, final: bool) -> int:
    blog_dir = blog_dir_for(month)
    review_dir = blog_dir / config.REVIEW_SUBDIR
    status = 0

    print(f"Checking reviews in {review_dir.relative_to(Path.cwd())}")
    try:
        problems = exercise_tasks.run_check(docs_dir, review_dir)
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"  PROBLEM: {problem}")
    if not problems:
        print("  exercises-completion.md: every exercise task has a valid status row")
    status = max(status, 1 if problems else 0)

    private_dir = Path.cwd() / config.PRIVATE_DIR / f"{config.MATERIALS_PREFIX}{month}"
    result = check_draft.run(blog_dir, private_dir, month)
    if result is None:
        print(f"\nNo draft yet ({check_draft.draft_path(blog_dir, month).relative_to(Path.cwd())}); skipped")
        return status
    path, findings = result
    print(f"\nChecking draft {path.relative_to(Path.cwd())}")
    labels = {"problem": "PROBLEM", "todo": "TO DO", "image": "IMAGE"}
    for finding in findings:
        print(f"  {labels[finding.level]} (line {finding.line}): {finding.message}")
    if not findings:
        print("  no problems found")
    elif check_draft.exit_code(findings, final) == 0:
        print("  no blocking problems; to dos and the header image remain (use --final to require them)")
    code = max(status, check_draft.exit_code(findings, final))
    if final and code == 0:
        print(f"\nPassed. Before you commit, read everything in {blog_dir.relative_to(Path.cwd())}/ "
              "yourself: the anonymised chat, the digests, the reviews and the draft. "
              "The checks are a safety net, not a substitute.")
    return code


MISSING_HELP = (
    "Supply what is missing once; it is saved in the blog folder, in session-inputs.json.\n"
    "  --register-url URL    registration link for the next session\n"
    "  --recording-url URL   published call recording, or 'none' if not available yet\n"
    "  --archive-url URL     published materials archive\n"
    "  --author SLUG         author, as the file name in the website's _team folder without .md\n"
    f"                        (repeatable; see {config.TEAM_DIR_URL})\n"
    "  --external-author 'Name|https://link'\n"
    "                        author who is not on the team (repeatable)\n"
    "  --next-date / --next-time / --next-theme\n"
    "                        the next session's details, if they cannot be read from its\n"
    "                        registration page"
)

NOT_PREPARED_HELP = (
    "The anonymised material is missing. In your own terminal, before opening Claude Code, run:\n"
    "  python code/blog-recap/scripts/pipeline.py --month {month} --prepare\n"
    "then review the chat's flagged links and run:\n"
    "  python code/blog-recap/scripts/pipeline.py --month {month} --prepare --apply"
)


def prompt_for_link(key: str) -> str:
    labels = {
        "register_url": "Registration link for the next session",
        "recording_url": "Published call recording link (or 'none' if not available yet)",
        "archive_url": "Published materials archive link",
    }
    return input(f"{labels[key]}: ")


def prompt_for_authors() -> tuple[list[str], list[str]]:
    print(f"Authors are named as their file in the website's _team folder: {config.TEAM_DIR_URL}")
    team = input("Authors on the team, as file names without .md (comma separated): ")
    external = []
    print("Authors who are not on the team: enter 'Name|https://link', blank line to finish")
    while True:
        line = input("  external author: ").strip()
        if not line:
            break
        external.append(line)
    return [t for t in (x.strip() for x in team.split(",")) if t], external


def run_prepare(args, docs_dir: Path, private_dir: Path, blog_dir: Path) -> int:
    """The stages that read names. Run before opening Claude Code."""
    extra_names = config.EXTRA_NAMES + args.extra_name
    print(f"Raw material (read only by this step): {private_dir.relative_to(Path.cwd())}")
    print(f"Archived material: {docs_dir.relative_to(Path.cwd())}")
    print(f"Outputs: {blog_dir.relative_to(Path.cwd())}")

    try:
        rules = link_redaction.load()
    except link_redaction.RedactionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print("\n[1/3] anonymise-chat, then flag links for review")
    reports = []
    try:
        chats = anonymise_chat.find_chat_files(private_dir)
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for chat in chats:
        anonymised = private_dir / (chat.stem + anonymise_chat.OUTPUT_SUFFIX + chat.suffix)
        review = link_redaction.review_path(anonymised)
        if review.exists() and not args.force:
            print(f"  {review.name} already exists: kept, so your edits are safe (--force starts it again)")
            continue
        try:
            report = anonymise_chat.process_file(chat, extra_names, private_dir)
        except anonymise_chat.ChatFormatError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        print(report.summary())
        warn_on_month_mismatch([report], args.month)
        text = report.output.read_text(encoding="utf-8")
        report.output.unlink()  # the review file replaces it
        if not report.ok:
            print("Stopping: fix the leaks above before continuing.", file=sys.stderr)
            return 1
        flagged, findings = link_redaction.flag(text, rules)
        review.write_text(flagged, encoding="utf-8")
        flags = review.with_name(review.name.replace(".review.txt", "_link-flags.md"))
        flags.write_text(link_redaction.flag_report(findings, text, chat.name, rules), encoding="utf-8")
        blocking = sum(f.blocking for f in findings)
        print(f"  wrote {review.relative_to(Path.cwd())}")
        print(f"  links and emails flagged: {len(findings)} ({blocking} blocking: Zoom, Slack, CryptPad, "
              f"credentials); list in {flags.name}")
        reports.append(report)

    print("\n[2/3] notes-digest")
    try:
        output, stats = notes_digest.run(docs_dir, blog_dir, extra_names)
    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"  wrote {output.relative_to(Path.cwd())}")
    print(f"  participant list stripped ({stats['attendees']} names); rooms: {stats['rooms']}; "
          f"names replaced: {stats['names_replaced']}")
    if stats["leak_lines"]:
        print(f"  LEAK: name still present on digest lines {stats['leak_lines']}", file=sys.stderr)
        output.unlink(missing_ok=True)  # never leave a leaking file where Claude can read it
        print("Stopping. The leaking digest was deleted.", file=sys.stderr)
        return 1
    residual = link_redaction.residual_in(output.read_text(encoding="utf-8"), rules)
    if any(f.blocking for f in residual):
        output.unlink(missing_ok=True)
        lines = sorted({f.line for f in residual if f.blocking})
        print(f"  LEAK: a link or secret that must be redacted is in the notes (digest lines {lines}). "
              "Redact it in docs/ with the materials-archiving scripts. The digest was deleted.", file=sys.stderr)
        return 1
    others = sorted({f.line for f in residual})
    if others:
        print(f"  CHECK: URLs or emails not on the allowlist remain in the notes digest (lines {others}); "
              "they come from the archived notes: look at them before committing")

    print("\n[3/3] registration-count")
    try:
        registration = registration_count.run(private_dir, blog_dir)
    except (FileNotFoundError, registration_count.RegistrationFormatError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if registration is None:
        print(f"  no registration report in {private_dir.relative_to(Path.cwd())}; skipped")
    else:
        output, reg = registration
        print(f"  wrote {output.relative_to(Path.cwd())}")
        print(f"  registered: {reg.registrants} (approved {reg.approved}, cancelled {reg.cancelled})")
        if reg.stale:
            print("  CHECK: report was generated before the meeting; later registrations are missing")
        if not reg.consistent:
            print(f"  CHECK: summary says {reg.registrants} but {reg.listed} are listed", file=sys.stderr)

    print("\nThe raw chat and registration report stay in private/, which Claude Code is denied access to.")
    print("\nNext: review the chat's flagged links. In the review file(s) in "
          f"{private_dir.relative_to(Path.cwd())}/:")
    print("  leave a <redact> tag to redact it; delete the two tags to keep it visible;")
    print("  wrap anything else that should not be shared in <redact></redact>.")
    print("Then run the same command with --apply:")
    print(f"  python code/blog-recap/scripts/pipeline.py --month {args.month} --prepare --apply")
    return 0


def run_apply(args, private_dir: Path, blog_dir: Path) -> int:
    """Apply the reviewed redactions and write the chat Claude is given."""
    try:
        rules = link_redaction.load()
    except link_redaction.RedactionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    reviews = sorted(private_dir.glob(f"*{link_redaction.REVIEW_SUFFIX}.txt"))
    if not reviews:
        print(f"ERROR: no review file in {private_dir.relative_to(Path.cwd())}. "
              "Run --prepare first.", file=sys.stderr)
        return 2
    print(f"Applying redactions in {len(reviews)} review file(s)")
    results, failed = [], False
    for review in reviews:
        target = blog_dir / link_redaction.final_name(review)
        if target.exists() and not args.force:
            print(f"ERROR: {target.relative_to(Path.cwd())} already exists; use --force to replace it.",
                  file=sys.stderr)
            return 2
        try:
            final, count, problems = link_redaction.apply(
                review.read_text(encoding="utf-8"), review.name, rules, args.accept_residual)
        except rules.error as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        for problem in problems:
            print(f"  PROBLEM: {problem}", file=sys.stderr)
        failed = failed or bool(problems)
        results.append((target, final, count))
    if failed:
        print("Stopping: nothing was written. Fix the review file and run --apply again.", file=sys.stderr)
        return 1
    blog_dir.mkdir(parents=True, exist_ok=True)
    for target, final, count in results:
        target.write_text(final, encoding="utf-8")
        print(f"  wrote {target.relative_to(Path.cwd())} ({count} redactions)")
    print("\nRead the chat in the blog folder yourself, then you can open Claude Code.")
    return 0


def prepared(blog_dir: Path) -> bool:
    return bool(list(blog_dir.glob(f"*{anonymise_chat.OUTPUT_SUFFIX}.txt"))) and (
        blog_dir / notes_digest.DIGEST_NAME
    ).exists()


def run_main(args, docs_dir: Path, blog_dir: Path) -> int:
    """Everything that works from the anonymised material."""
    print(f"Working folder: {blog_dir.relative_to(Path.cwd())}")
    print(f"Archived material: {docs_dir.relative_to(Path.cwd())}")
    if not prepared(blog_dir):
        print("ERROR: " + NOT_PREPARED_HELP.format(month=args.month), file=sys.stderr)
        return 2

    print("\n[1/5] session-inputs")
    supplied = {
        "register_url": args.register_url,
        "recording_url": args.recording_url,
        "archive_url": args.archive_url,
    }
    ask = prompt_for_link if sys.stdin.isatty() else None
    try:
        _, link_warnings = session_inputs.collect_links(blog_dir, args.month, supplied, ask)
    except session_inputs.InputsError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print(MISSING_HELP, file=sys.stderr)
        return 2
    try:
        authors = session_inputs.collect_authors(
            blog_dir, args.author, args.external_author,
            prompt_for_authors if sys.stdin.isatty() else None,
        )["authors"]
    except session_inputs.InputsError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print(MISSING_HELP, file=sys.stderr)
        return 2
    print(f"  saved {session_inputs.inputs_path(blog_dir).relative_to(Path.cwd())}")
    print(f"  authors: {len(authors)} ({sum('team' in a for a in authors)} on the team)")
    for warning in link_warnings:
        print(f"  WARNING: {warning}", file=sys.stderr)
    next_supplied = {
        "next_date": args.next_date, "next_time": args.next_time,
        "next_theme": args.next_theme, "next_hosts": args.next_hosts,
    }
    try:
        details, next_notes = session_inputs.resolve_next_session(blog_dir, args.month, next_supplied)
    except session_inputs.InputsError as error:
        print(f"ERROR: could not get the next session's details: {error}", file=sys.stderr)
        print(MISSING_HELP, file=sys.stderr)
        return 2
    for key in ("next_theme", "next_date", "next_time"):
        print(f"  {key}: {details[key]}  [{details.get(key + '_source', '-')}]")
    for note in next_notes:
        print(f"  CHECK: {note}")

    print("\n[2/5] chat-digest")
    try:
        outputs = chat_digest.run(blog_dir, docs_dir)
    except (chat_digest.BriefingFormatError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for output in outputs:
        print(f"  wrote {output.relative_to(Path.cwd())}")

    print("\n[3/5] poll-digest")
    try:
        poll_result = poll_digest.run(docs_dir, blog_dir)
    except (FileNotFoundError, poll_digest.PollFormatError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if poll_result is None:
        print(f"  no poll CSV in {docs_dir.relative_to(Path.cwd())}; skipped")
    else:
        output, polls = poll_result
        print(f"  wrote {output.relative_to(Path.cwd())}")
        for poll in polls:
            print(f"  {poll.name}: {poll.responses} responses, {len(poll.questions)} questions")

    print("\n[4/5] comms-copy")
    try:
        comms = comms_copy.run(docs_dir, blog_dir, args.month)
    except (comms_copy.CommsCopyError, session_inputs.InputsError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if comms is None:
        print(f"  no {comms_copy.COMMS_NAME} in {docs_dir.relative_to(Path.cwd())}; skipped")
    else:
        found, comms_notes = comms
        print(f"  hosts: {len(found['hosts'])}; speakers: {len(found['speakers'])}; "
              f"theme: {found.get('theme', '(not found)')}")
        for note in comms_notes:
            print(f"  CHECK: {note}")

    print("\n[5/5] blog-links")
    try:
        links_file = session_inputs.write_blog_links(blog_dir, args.month)
    except session_inputs.InputsError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"  wrote {links_file.relative_to(Path.cwd())}")
    if not (blog_dir / registration_count.DIGEST_NAME).exists():
        print("  CHECK: no registration-digest.md, so the registered count is missing "
              "(add the registration report and run --prepare)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--month",
        default=datetime.date.today().strftime("%Y%m"),
        help="meetup month as YYYYMM (default: current month)",
    )
    parser.add_argument(
        "--setup-claude", action="store_true",
        help="once, before using Claude Code: add the deny rule that keeps it out of private/ "
             f"to {config.CLAUDE_SETTINGS} (created if missing, merged if it exists)",
    )
    parser.add_argument(
        "--prepare", action="store_true",
        help="run first, in your own terminal before opening Claude Code: anonymise the chat, "
             "strip the participant list from the notes and count registrations",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="with --prepare, after reviewing the chat's flagged links: apply the redactions and "
             "write the chat that Claude Code is given",
    )
    parser.add_argument(
        "--accept-residual", action="store_true",
        help="with --apply: accept URLs or emails left visible on purpose (blocking ones never pass)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="with --prepare: start the chat review file again, discarding your edits; "
             "with --apply: replace an existing anonymised chat",
    )
    parser.add_argument(
        "--extra-name", action="append", default=[],
        help="with --prepare: additional name/nickname to scrub (repeatable; adds to config.py)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="skip the stages and check what Claude has written: the exercise completion "
             "and the draft post",
    )
    parser.add_argument(
        "--final", action="store_true",
        help="with --check: also fail on highlights still in the draft and on the header "
             "image not yet filled in",
    )
    for flag, text in (
        ("--register-url", "registration link for the next session"),
        ("--recording-url", "published call recording, or 'none' if not available yet"),
        ("--archive-url", "published materials archive link"),
        ("--next-date", "next session date, if it cannot be read from the registration page"),
        ("--next-time", "next session time, if it cannot be read from the registration page"),
        ("--next-theme", "next session theme, if it cannot be read from the registration page"),
        ("--next-hosts", "next session hosts (optional; always supplied by hand)"),
    ):
        parser.add_argument(flag, help=text)
    parser.add_argument(
        "--author", action="append", default=[], metavar="SLUG",
        help="author as the file name in the website's _team folder, without .md (repeatable)",
    )
    parser.add_argument(
        "--external-author", action="append", default=[], metavar="'NAME|URL'",
        help="author who is not on the team, as 'Name|https://link' (repeatable)",
    )
    args = parser.parse_args(argv)
    if args.setup_claude:
        try:
            added = claude_settings.run()
        except claude_settings.SettingsError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        for rule in config.CLAUDE_DENY_RULES:
            print(f"  {'added' if rule in added else 'already present'}: deny {rule}")
        print(f"Settings in {config.CLAUDE_SETTINGS}. Claude Code's file tools can no longer read private/.")
        return 0
    if not MONTH_RE.match(args.month):
        parser.error("--month must be six digits, e.g. 202610")
    if args.apply and not args.prepare:
        parser.error("--apply goes with --prepare: --prepare --apply")
    if args.accept_residual and not args.apply:
        parser.error("--accept-residual goes with --prepare --apply")

    docs_dir = resolve_materials_dir(config.DOCS_DIR, args.month)
    if args.check:
        return run_review_checks(docs_dir, args.month, args.final)

    blog_dir = blog_dir_for(args.month)
    if args.prepare:
        private_dir = resolve_materials_dir(config.PRIVATE_DIR, args.month)
        if args.apply:
            return run_apply(args, private_dir, blog_dir)
        return run_prepare(args, docs_dir, private_dir, blog_dir)
    return run_main(args, docs_dir, blog_dir)


if __name__ == "__main__":
    sys.exit(main())
