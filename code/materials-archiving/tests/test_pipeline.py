"""End-to-end tests on invented data. Run from the repository root:

    python -m unittest discover -s code/materials-archiving/tests -v

Needs pandoc on the PATH (the .docx fixtures are built with it).
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import archive  # noqa: E402
from archiving import flagging, redaction, zoom  # noqa: E402
from archiving.common import PipelineError, load_config  # noqa: E402

TOPIC = "Test Community Monthly Meetup - May 2031"
FMT = "%m/%d/%Y %I:%M:%S %p"

COMMS_MD = """# Email invitation

Dear \\<\\<name\\>\\>,

Register: [Register here](https://us99web.zoom.us/meeting/register/FAKEFAKEFAKE)

**Speaker**

- **[Alex Speaker](https://www.example-uni.ac.uk/people/alex)**, Community Manager

**Host**

- **[Sam Host](https://www.rcmcooperative.com/team/sam/)**, Trainer

Questions: contact Pat (pat@rcmcooperative.com) or Jo (jo@elsewhere.org).

Mail-merge link: [the Cooperative](https://x-dot-yamm-track.appspot.com/TOKENTOKENTOKEN)

Unlisted page: https://unlisted.example.net/page
"""

BRIEFING_MD = """**Date:** 1st May 2031

Zoom link: https://us99web.zoom.us/w/12345678901?tk=FAKETOKEN&pwd=FAKEPWD

Zoom host key - the host key: 987654

Live notes: https://cryptpad.fr/code/#/2/code/edit/FAKEEDITKEY/

Slides: https://zenodo.org/records/123456

| Time | Activity |
| --- | --- |
| 0-2 mins | Welcome |
"""

NOTES_MD = """# Notes

<media-tag src="https://files.cryptpad.fr/blob/00/FAKEBLOB" data-crypto-key="cryptpad:FAKEKEY"></media-tag>

Live notes: https://cryptpad.fr/code/#/2/code/edit/FAKEEDITKEY/

## Attendees

- Ada Fakename / she/her / Org A / ada@fake-a.org / @adafake
- Bo Fakename / he/him / Org B / bo@fake-b.ac.uk
- Pat Staff / she/her / Co-op / pat@rcmcooperative.com

## Notes

Discussion of the guide at https://www.markdownguide.org/getting-started/
"""

PARTICIPANT_COLUMNS = [
    "Topic", "Type", "ID", "Host name", "Host email", "Start time", "End time", "Participants",
    "Duration (minutes)", "Total participant minutes", "Department", "Group", "Source", "Unique viewers",
    "Max concurrent views", "Creation time", "Name (original name)", "Email", "Join time", "Leave time",
    "Duration (minutes)", "Guest", "Recording disclaimer response", "In waiting room",
]


def meeting_cols(topic, mid, start, end):
    return [topic, "Meeting", mid, "Shared Host", "host@shared-host.example", start, end, "9", "60", "120",
            "", "", "Zoom", "-", "", "09/01/2031 10:00:00 AM"]


def participant_rows():
    main = meeting_cols(TOPIC, "111 1111 1111", "05/01/2031 12:50:00 PM", "05/01/2031 02:00:00 PM")
    other = meeting_cols("Some Other Group Cafe", "222 2222 2222", "05/01/2031 02:05:00 PM", "05/01/2031 03:00:00 PM")
    rows = [
        # Ada: waiting room, then two sessions
        main + ["Ada Fakename", "ada@fake-a.org", "05/01/2031 12:58:00 PM", "05/01/2031 12:59:00 PM", "1", "Yes", "No Response", "Yes"],
        main + ["Ada F (she/her)", "ADA@fake-a.org", "05/01/2031 12:59:00 PM", "05/01/2031 01:20:00 PM", "21", "Yes", "OK", "No"],
        main + ["Ada Fakename", "ada@fake-a.org", "05/01/2031 01:20:00 PM", "05/01/2031 01:55:00 PM", "35", "Yes", "No Response", "No"],
        # Bo: one session
        main + ["Bo Fakename", "bo@fake-b.ac.uk", "05/01/2031 01:01:00 PM", "05/01/2031 01:58:00 PM", "57", "No", "No Response", "No"],
        other + ["Cy Elsewhere", "cy@other-group.example", "05/01/2031 02:06:00 PM", "05/01/2031 02:50:00 PM", "44", "Yes", "No Response", "No"],
    ]
    return rows


def write_csv(path: Path, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


POLL_ROWS = [
    ["Overview"],
    ["Generate Time", "Meeting Topic", "Meeting/Webinar ID", "Actual Start Time"],
    ["05/01/2031 05:00:00 PM", TOPIC, "11111111111", "05/01/2031 12:50:00 PM"],
    [],
    ["Launched Polls"],
    ["#", "Poll Name", "Questions", "Responses"],
    ["1", "Feedback", "2", "2"],
    [],
    ["Feedback"],
    ["#", "User Name", "Email Address", "Submitted Date and Time", "Q one", "Q two"],
    ["1", "Ada Fakename", "ada@fake-a.org", "05/01/2031 01:58:00 PM", "5", "4", "", "", ""],
    ["2", "Bo Fakename", "bo@fake-b.ac.uk", "05/01/2031 01:59:00 PM", "3", "3", "", "", ""],
    [],
]


def run_cli(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = archive.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


def make_inputs(directory: Path) -> None:
    for name, text in (("comms-copy", COMMS_MD), ("facilitators-briefing", BRIEFING_MD)):
        md = directory / f"{name}.md"
        md.write_text(text, encoding="utf-8")
        subprocess.run(["pandoc", str(md), "-o", str(directory / f"{name}.docx")], check=True)
        md.unlink()
    (directory / "RCM-Monthly-Meet-up-narratives.md").write_text(NOTES_MD, encoding="utf-8")
    write_csv(directory / "meetinglistdetails_fake.csv", [PARTICIPANT_COLUMNS] + participant_rows())
    write_csv(directory / "poll_fake.csv", POLL_ROWS)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        # <repo>/private/materials-203105 holds the inputs; <repo>/docs must already exist.
        self.repo = Path(tempfile.mkdtemp())
        self.tmp = self.repo / "private" / "materials-203105"
        self.out = self.repo / "docs" / "materials-203105"
        self.tmp.mkdir(parents=True)
        (self.repo / "docs").mkdir()
        make_inputs(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def prepare(self, **kw):
        return run_cli("prepare", "--input-dir", self.tmp, "--topic", kw.get("topic", TOPIC))

    def review_text(self, name):
        return (self.tmp / "review" / name).read_text(encoding="utf-8")

    # --- inputs and format checks ---------------------------------------------------------

    def test_check_passes_and_writes_nothing(self):
        code, out, err = run_cli("check", "--input-dir", self.tmp, "--topic", TOPIC)
        self.assertEqual(code, 0, err)
        self.assertFalse((self.tmp / "review").exists())
        self.assertFalse(self.out.exists())

    def test_missing_input_stops_with_checklist(self):
        (self.tmp / "poll_fake.csv").unlink()
        code, out, err = run_cli("check", "--input-dir", self.tmp, "--topic", TOPIC)
        self.assertEqual(code, 1)
        self.assertIn("MISSING", out)
        self.assertIn("Zoom poll export", out)

    def test_wrong_topic_lists_topics_found(self):
        code, out, err = run_cli("check", "--input-dir", self.tmp, "--topic", "Nope")
        self.assertEqual(code, 1)
        self.assertIn(TOPIC, err)
        self.assertIn("Some Other Group Cafe", err)

    def test_changed_zoom_format_is_detected(self):
        header = list(PARTICIPANT_COLUMNS)
        header[17] = "E-mail"
        write_csv(self.tmp / "meetinglistdetails_fake.csv", [header] + participant_rows())
        code, out, err = run_cli("check", "--input-dir", self.tmp, "--topic", TOPIC)
        self.assertEqual(code, 1)
        self.assertIn("expected 'Email', found 'E-mail'", err)

    def test_changed_poll_format_is_detected(self):
        rows = [list(r) for r in POLL_ROWS]
        rows[9][1] = "Name"
        write_csv(self.tmp / "poll_fake.csv", rows)
        code, out, err = run_cli("check", "--input-dir", self.tmp, "--topic", TOPIC)
        self.assertEqual(code, 1)
        self.assertIn("poll", err.lower())

    # --- flagging -------------------------------------------------------------------------

    def test_flags_follow_the_rules(self):
        self.assertEqual(self.prepare()[0], 0)
        comms = self.review_text("comms-copy.review.md")
        self.assertIn("<redact>https://us99web.zoom.us/meeting/register/FAKEFAKEFAKE</redact>", comms)
        self.assertIn("<redact>https://x-dot-yamm-track.appspot.com/TOKENTOKENTOKEN</redact>", comms)
        self.assertIn("<redact>jo@elsewhere.org</redact>", comms)
        self.assertIn("<redact>https://unlisted.example.net/page</redact>", comms)
        # allowed: speaker's and host's pages (by position), own domain email
        self.assertNotIn("<redact>https://www.example-uni.ac.uk", comms)
        self.assertNotIn("<redact>https://www.rcmcooperative.com", comms)
        self.assertNotIn("<redact>pat@rcmcooperative.com", comms)

        briefing = self.review_text("facilitators-briefing.review.md")
        self.assertIn("<redact>987654</redact>", briefing)
        self.assertIn("<redact>https://cryptpad.fr/code/#/2/code/edit/FAKEEDITKEY/</redact>", briefing)
        self.assertNotIn("<redact>https://zenodo.org", briefing)
        self.assertIn("| Time", briefing)  # table is a pipe table, not HTML
        self.assertNotIn("<table", briefing)

        notes = self.review_text("collab-notes.review.md")
        self.assertIn('<redact><media-tag src="https://files.cryptpad.fr/blob/00/FAKEBLOB"', notes)
        self.assertIn("<redact>ada@fake-a.org</redact>", notes)
        self.assertIn("@adafake", notes)
        self.assertNotIn("<redact>@adafake", notes)
        self.assertNotIn("<redact>https://www.markdownguide.org", notes)

    def test_speaker_host_rule_is_by_position_not_domain(self):
        text = "**Speaker**\n\n- [X](https://brand-new-university.example/x)\n\nElsewhere: https://brand-new-university.example/y\n"
        config = load_config()
        found = flagging.find_findings(text, config, "comms")
        self.assertEqual([f.text(text) for f in found], ["https://brand-new-university.example/y"])
        found_notes = flagging.find_findings(text, config, "notes")
        self.assertEqual(len(found_notes), 2)

    def test_existing_redact_tags_are_not_wrapped_twice(self):
        text = "Link <redact>https://us99web.zoom.us/x</redact> and https://us99web.zoom.us/y"
        found = flagging.find_findings(text, load_config(), "comms")
        self.assertEqual(len(found), 1)

    def test_prepare_will_not_overwrite_edits(self):
        self.assertEqual(self.prepare()[0], 0)
        code, out, err = self.prepare()
        self.assertEqual(code, 1)
        self.assertIn("--force", err)

    # --- zoom -----------------------------------------------------------------------------

    def test_participants_one_row_per_person_with_uuids(self):
        self.assertEqual(self.prepare()[0], 0)
        with open(self.tmp / "review" / "zoom-participants.csv", newline="") as handle:
            rows = list(csv.reader(handle))
        header, body = rows[0], rows[1:]
        self.assertEqual(len(body), 2)  # Ada (3 sessions merged) and Bo; other meeting dropped
        self.assertNotIn("Email", header)
        self.assertNotIn("Name (original name)", header)
        self.assertNotIn("In waiting room", header)
        by_sessions = {r[-1] for r in body}
        self.assertEqual(by_sessions, {"3", "1"})
        ada = next(r for r in body if r[-1] == "3")
        self.assertEqual(ada[header.index("Join time")], "05/01/2031 12:58:00 PM")
        self.assertEqual(ada[header.index("Leave time")], "05/01/2031 01:55:00 PM")
        self.assertEqual(ada[[i for i, h in enumerate(header) if h == "Duration (minutes)"][-1]], "57")
        self.assertEqual(ada[header.index("Recording disclaimer response")], "OK")
        text = (self.tmp / "review" / "zoom-participants.csv").read_text()
        for secret in ("ada@", "Ada", "bo@", "Bo Fake", "Elsewhere", "Cafe"):
            self.assertNotIn(secret, text)

    def test_poll_name_and_email_removed(self):
        self.assertEqual(self.prepare()[0], 0)
        text = (self.tmp / "review" / "zoom-poll.csv").read_text()
        self.assertNotIn("@", text)
        self.assertNotIn("Fakename", text)
        self.assertIn("#,Submitted Date and Time,Q one,Q two", text)
        self.assertIn(TOPIC, text)  # overview section untouched

    # --- apply ----------------------------------------------------------------------------

    # --- folder conventions ---------------------------------------------------------------

    def test_month_option_uses_private_and_docs_folders(self):
        import os
        before = os.getcwd()
        os.chdir(self.repo)
        try:
            code, out, err = run_cli("prepare", "--month", "203105", "--topic", TOPIC)
            self.assertEqual(code, 0, err)
            code, out, err = run_cli("apply", "--month", "203105", "--accept-residual")
            self.assertEqual(code, 0, err)
        finally:
            os.chdir(before)
        self.assertTrue((self.repo / "docs" / "materials-203105" / "comms-copy.md").is_file())
        self.assertFalse((self.repo / "docs" / "materials-203105" / "review").exists())
        self.assertTrue((self.repo / "private" / "materials-203105" / "review" / "manifest.json").is_file())

    def test_missing_input_folder_says_how_to_create_it(self):
        import os
        before = os.getcwd()
        os.chdir(self.repo)
        try:
            code, out, err = run_cli("check", "--month", "203106", "--topic", TOPIC)
        finally:
            os.chdir(before)
        self.assertEqual(code, 1)
        self.assertIn("mkdir -p private/materials-203106", err)

    def test_docs_folder_must_already_exist(self):
        (self.repo / "docs").rmdir()
        code, out, err = run_cli("check", "--input-dir", self.tmp, "--topic", TOPIC)
        self.assertEqual(code, 1)
        self.assertIn("docs", err)
        self.assertIn("already exist", err)

    def test_folder_month_must_match_the_meeting_date(self):
        wrong = self.repo / "private" / "materials-203106"
        self.tmp.rename(wrong)
        code, out, err = run_cli("check", "--input-dir", wrong, "--topic", TOPIC)
        self.assertEqual(code, 1)
        self.assertIn("materials-203105", err)

    def test_folder_must_follow_the_naming_convention(self):
        odd = self.repo / "private" / "may-meetup"
        self.tmp.rename(odd)
        code, out, err = run_cli("check", "--input-dir", odd, "--topic", TOPIC)
        self.assertEqual(code, 1)
        self.assertIn("materials-YYYYMM", err)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_private_folder_must_be_git_ignored(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        code, out, err = run_cli("check", "--input-dir", self.tmp, "--topic", TOPIC)
        self.assertEqual(code, 1)
        self.assertIn(".gitignore", err)
        (self.repo / ".gitignore").write_text("private/\n")
        code, out, err = run_cli("check", "--input-dir", self.tmp, "--topic", TOPIC)
        self.assertEqual(code, 0, err)
        self.assertIn("excluded by .gitignore", out)

    def test_apply_replaces_with_placeholder_and_keeps_links_readable(self):
        self.prepare()
        code, out, err = run_cli("apply", "--input-dir", self.tmp, "--accept-residual")
        self.assertEqual(code, 0, err)
        archive_dir = self.out
        names = sorted(p.name for p in archive_dir.iterdir())
        self.assertEqual(names, [
            "collab-notes.md", "comms-copy.md", "facilitators-briefing.md",
            "processing-log.md", "zoom-participants.csv", "zoom-poll.csv",
        ])
        comms = (archive_dir / "comms-copy.md").read_text()
        self.assertNotIn("<redact>", comms)
        self.assertNotIn("</redact>", comms)
        self.assertNotIn("zoom.us", comms)
        self.assertIn("`<redacted>`", comms)
        self.assertIn("Register here (`<redacted>`)", comms)
        self.assertIn("pat@rcmcooperative.com", comms)
        briefing = (archive_dir / "facilitators-briefing.md").read_text()
        self.assertIn("host key: `<redacted>`", briefing)
        self.assertNotIn("987654", briefing)

    def test_log_and_manifest_hold_no_personal_data(self):
        self.prepare()
        run_cli("apply", "--input-dir", self.tmp, "--accept-residual")
        blob = (self.out / "processing-log.md").read_text()
        blob += (self.tmp / "review" / "manifest.json").read_text()
        for secret in ("ada@", "Ada", "bo@", "987654", "zoom.us", "FAKE", "elsewhere.org", "cy@"):
            self.assertNotIn(secret, blob)

    def test_unremoved_always_flag_item_blocks_even_with_accept(self):
        self.prepare()
        path = self.tmp / "review" / "facilitators-briefing.review.md"
        text = path.read_text().replace("<redact>987654</redact>", "987654")
        path.write_text(text)
        code, out, err = run_cli("apply", "--input-dir", self.tmp, "--accept-residual")
        self.assertEqual(code, 1)
        self.assertIn("must be redacted", err)
        self.assertFalse((self.out).exists())

    def test_deliberately_visible_unlisted_item_needs_confirmation(self):
        self.prepare()
        path = self.tmp / "review" / "comms-copy.review.md"
        path.write_text(path.read_text().replace(
            "<redact>https://unlisted.example.net/page</redact>", "https://unlisted.example.net/page"))
        code, out, err = run_cli("apply", "--input-dir", self.tmp)
        self.assertEqual(code, 1)
        self.assertIn("--accept-residual", err)
        code, out, err = run_cli("apply", "--input-dir", self.tmp, "--accept-residual")
        self.assertEqual(code, 0, err)
        self.assertIn("https://unlisted.example.net/page",
                      (self.out / "comms-copy.md").read_text())

    def test_human_added_redaction_is_applied(self):
        self.prepare()
        path = self.tmp / "review" / "collab-notes.review.md"
        path.write_text(path.read_text().replace("Discussion of the guide", "<redact>Discussion of the guide</redact>"))
        run_cli("apply", "--input-dir", self.tmp, "--accept-residual")
        self.assertNotIn("Discussion of the guide",
                         (self.out / "collab-notes.md").read_text())

    def test_unbalanced_tags_stop_the_run(self):
        self.prepare()
        path = self.tmp / "review" / "collab-notes.review.md"
        path.write_text(path.read_text().replace("</redact>", "", 1))
        code, out, err = run_cli("apply", "--input-dir", self.tmp, "--accept-residual")
        self.assertEqual(code, 1)
        self.assertIn("redact", err)
        self.assertFalse((self.out).exists())

    def test_apply_will_not_overwrite_archive(self):
        self.prepare()
        run_cli("apply", "--input-dir", self.tmp, "--accept-residual")
        code, out, err = run_cli("apply", "--input-dir", self.tmp, "--accept-residual")
        self.assertEqual(code, 1)
        self.assertIn("--force", err)

    def test_email_allowance_can_be_switched_off_for_a_heading(self):
        config = load_config()
        config["redaction"]["emails"]["exempt_headings"] = ["Attendees"]
        text = NOTES_MD
        found = [f.text(text) for f in flagging.find_findings(text, config, "notes")]
        self.assertIn("pat@rcmcooperative.com", found)

    def test_placeholder_inside_link_is_readable(self):
        text, n = redaction.apply_redactions("See \\[the form\\](<redact>https://x.example/y</redact>) now.", "`<redacted>`")
        self.assertEqual(text, "See the form (`<redacted>`) now.")
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
