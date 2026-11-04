---
name: materials-archiving
description: Prepare a monthly meetup's materials for public archiving. Use when the user wants to archive meetup materials, redact comms copy, facilitator briefings or collab notes, or anonymise Zoom participant and poll exports.
---

# materials-archiving

Prepares one month's RCM Cooperative meetup materials for the public archive.
All processing is done by the scripts in `scripts/`.
Your job is to collect the inputs, run the commands, and relay the output.
Do not summarise, interpret or edit the materials yourself.

Read `HOW_TO_USE.md` for the full description of the steps, the folders, the review conventions and the settings.

Inputs live in `private/materials-YYYYMM/` (git-ignored) and the archive is written to `docs/materials-YYYYMM/`.
`YYYYMM` is the year and month of the session, for example `202610`.

## 1. Ask for the inputs

Send this, then wait for the user to say "go". Do not act on partial input.

> Please create the input folder in the repository root and download all five files into it:
>
> ```bash
> mkdir -p private/materials-YYYYMM
> ```
>
> (`YYYYMM` is the year and month of the session, for example `202610`. `private/` must be in `.gitignore`.)
>
> 1. Comms copy (`.docx` or `.md`)
> 2. Facilitators briefing (`.docx` or `.md`)
> 3. Collab notes (`.md` or `.docx`)
> 4. Zoom participants export (`.csv`)
> 5. Zoom poll export (`.csv`)
>
> Google Docs should be downloaded first; links cannot be used.
> Then tell me the month (`YYYYMM`) and the **meeting topic exactly as it appears in the `Topic` column of the Zoom participants CSV**.
> That is how other meetings on the shared Zoom account are removed.
> Say if anything beyond Zoom links, email addresses and host keys should be redacted.

## 2. Prepare

Python 3.11+ and pandoc 3.1+ are needed.
`environment.yml` creates a conda environment with both (`conda env create -f code/materials-archiving/environment.yml`).
If a command fails because pandoc or Python is missing, tell the user to create and activate that environment.

Run from the repository root.

```bash
python code/materials-archiving/scripts/archive.py prepare --month <YYYYMM> --topic "<topic>"
```

If it stops, show the message and stop.
Do not work around it.
A wrong topic, a missing file, a folder that is not git-ignored or a changed Zoom format needs the user's decision.

## 3. Hand over for review

Tell the user the review files are in `private/materials-<YYYYMM>/review/` and what to do:
read `flag-report.md`, then edit the three `*.review.md` files.
They delete `<redact>` tags to keep text visible, and add tags to redact more.
They should also correct spellings and lightly tidy the notes while they are there.
Do not open, quote or summarise the review files in the conversation: they contain unredacted material.
Do not edit them unless the user asks.

## 4. Apply on confirmation

Only when the user confirms the review is finished:

```bash
python code/materials-archiving/scripts/archive.py apply --month <YYYYMM>
```

Add `--accept-residual` only if the user says they left an unlisted URL or email visible on purpose.
Items reported as "must be redacted" cannot be accepted: tell the user to redact them.

Report the files written to `docs/materials-<YYYYMM>/`, and nothing more.

## Settings and format changes

If a request means changing what is flagged, edit `config/redaction.toml`.
If Zoom has changed its export format, ask the user to confirm the new format before editing `config/zoom_schema.toml`.
