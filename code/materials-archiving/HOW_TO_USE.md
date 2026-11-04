# materials-archiving: how to use

Prepares one month's meetup materials for the public archive.
It converts the documents to markdown, flags what should be redacted for a person to review,
anonymises the two Zoom exports, then checks the result and writes the archive files.

All of the processing is deterministic code.
No AI model is involved in any step, so the same inputs always give the same outputs.
The only judgement is yours, in the review step.

## Where things go

`YYYYMM` is the year and month of the session, for example `202610` for October 2026.

| What | Where | In git? |
| --- | --- | --- |
| The five input files, and the `review/` folder the pipeline creates | `private/materials-YYYYMM/` | No: `private/` must be in `.gitignore` |
| The archive files | `docs/materials-YYYYMM/` | Yes: this is the public archive |

The pipeline creates `docs/materials-YYYYMM/` for you, but `docs/` must already exist.
It refuses to run if `private/` is not excluded by `.gitignore`,
because the input and `review/` folders hold unredacted material.

## What you need

- Python 3.11 or later (standard library only; nothing to install with pip).
- [pandoc](https://pandoc.org/installing.html) 3.1 or later, for `.docx` files.

The simplest way to get both is the conda environment in this folder:

```bash
conda env create -f code/materials-archiving/environment.yml
conda activate materials-archiving
```

Activate it before running any of the commands below.
If you already have Python 3.11+ and pandoc, you do not need it.

## Before you start: create the input folder and download the files

From the repository root (`Monthly-Meetups`), create the folder for the session.
This example is for October 2026:

```bash
mkdir -p private/materials-202610
```

Check that `.gitignore` contains the line `private/`.
Then download these five files into that folder.
Download Google Docs as `.docx` (File, Download) or as markdown; links are not supported.

| # | Input | Format |
| ---: | --- | --- |
| 1 | Comms copy: invitation email, Slack and LinkedIn text | `.docx` or `.md` |
| 2 | Facilitators briefing: links, agenda, roles | `.docx` or `.md` |
| 3 | Collab notes from the call | `.md` or `.docx` |
| 4 | Zoom participants export (the "meeting list details" report) | `.csv` |
| 5 | Zoom poll export | `.csv` |

You also need the **meeting topic exactly as it appears in the `Topic` column of the Zoom participants CSV**.
The participants export covers every meeting on the Zoom account,
and the topic is how the other meetings are removed.

Files are recognised automatically:
the Zoom files by their content, and the documents by their file names
(`comms`, `brief`, and `note` or `collab`; the notes can also be the one remaining `.md` file).
If a file cannot be recognised, name it with `--comms`, `--briefing`, `--notes`, `--participants` or `--poll`.

## The steps

Run everything from the repository root (`Monthly-Meetups`), not from inside the skill folder.
The commands assume the skill sits at `code/materials-archiving` in the repository.
If you keep it somewhere else, change that prefix in each command.

```bash
# 1. Optional dry run: checks the folders, the inputs and the Zoom formats; writes nothing
python code/materials-archiving/scripts/archive.py check \
  --month 202610 --topic "RCM Cooperative Monthly Meetup - October 2026"

# 2. Convert, flag and anonymise into private/materials-202610/review/
python code/materials-archiving/scripts/archive.py prepare \
  --month 202610 --topic "RCM Cooperative Monthly Meetup - October 2026"

# 3. Review by hand (see below)

# 4. Apply the redactions, verify, and write docs/materials-202610/
python code/materials-archiving/scripts/archive.py apply --month 202610
```

`prepare` runs the checks itself, so step 1 is only needed if you want to test the inputs first.
The folder name must match the meeting: if `materials-202610` does not match the date in the Zoom export, the run stops.
If your folders are elsewhere, use `--input-dir` (and `--output-dir`) in place of `--month`.

### Reviewing (step 3)

Open the three `*.review.md` files in `private/materials-202610/review/`,
with `flag-report.md` alongside as a list of what was flagged.

- Everything flagged is wrapped in `<redact>…</redact>`.
- **Keep the redaction:** leave the tags as they are.
- **Keep the text visible:** delete the two tags, leaving the text.
- **Redact something else:** wrap it in `<redact>…</redact>`. Tags must not be nested.

While you are in these files, also correct spellings and lightly tidy the notes,
for example fixing typos, stray formatting and broken line breaks.
The review files are the text that gets archived, so edit them directly.
Keep the changes light: do not rewrite what people said.
Leave the `<redact>` tags intact when you edit around them.

When you run `apply`, each tagged span is replaced by `` `<redacted>` ``.
If the span was the target of a link, the link is replaced by its text followed by `` (`<redacted>`) ``,
so the sentence still reads.

Also look at `zoom-participants.csv` and `zoom-poll.csv` in `review/`.
They are already anonymised and are copied to the archive unchanged by `apply`.

If you run `prepare` again it refuses to overwrite `review/`, so your edits are safe.
Use `--force` only when you want to start over.

## What you get

`docs/materials-202610/` holds six files, named without a date (the folder name carries the month):

- `comms-copy.md`
- `facilitators-briefing.md`
- `collab-notes.md`
- `zoom-participants.csv`: one row per person, from first join (waiting room included) to last leave
- `zoom-poll.csv`: responses without names or email addresses
- `processing-log.md`: counts of what was flagged, redacted and removed, with no personal data in it

`apply` will not overwrite files already in that folder unless you use `--force`.

## What gets flagged

The rule is *flag by default, allow by exception*.
Every URL and email address is flagged unless `config/redaction.toml` allows it.

- **Allowed URLs:** your own site and other standing resources listed in the config,
  plus, in the comms copy, the links in the list under the **Speaker** and **Host** headings.
  Those change every month, so they are allowed by position rather than by domain.
- **Always flagged, whatever else matches:** Zoom links, Google edit links, Slack invites, CryptPad,
  mail-merge tracking links, URLs carrying a token or password, Zoom host keys and passcodes,
  and CryptPad `media-tag` keys.
- **Allowed emails:** any `@rcmcooperative.com` address, in every document.
- **Not flagged:** GitHub handles and names (the notes keep names, as their privacy notice says).

Anything sensitive that matches none of these patterns, such as a remark that should not be public,
can only be caught by you in the review.

## What the checks stop

`check` and `prepare` stop if:

- the input folder is missing, is not named `materials-YYYYMM`, or its month does not match the Zoom export;
- `docs/` does not exist, or `private/` is not excluded by `.gitignore`;
- any of the five inputs is missing or ambiguous;
- a Zoom export does not match `config/zoom_schema.toml`
  (column names, order, date format, expected sections), in which case the differences are shown.
  That means Zoom has changed its format: check the file by hand, then update the schema file;
- the topic matches no rows in the participants export (the topics found are listed).

`apply` writes nothing unless all of these hold:

- every `<redact>` tag is balanced and none is nested;
- no always-flagged item is still visible (this cannot be overridden);
- no non-allowlisted URL or email is still visible,
  unless you confirm with `--accept-residual` that you left it visible on purpose;
- the participants file has no name or email column, unique IDs, and the expected number of people;
- the poll file has no `@` and no removed columns.

## Settings you may want to change

Both files are in `config/`.

- `redaction.toml`
  - `urls.allow`: standing URLs that stay visible.
  - `urls.always_flag`: patterns that are always flagged.
  - `emails.allow_domains`: domains whose addresses stay visible.
  - `emails.exempt_headings`: headings under which that allowance is switched off.
    Set it to `["Attendees"]` if the attendee list should never show any address.
    By default it is empty, so `@rcmcooperative.com` addresses in the attendee list stay visible.
  - `placeholder`: the text that replaces redactions.
- `zoom_schema.toml`
  - `participants.drop_columns`: extra columns to remove.
    By default the `Host name` and `Host email` columns stay, which shows a shared host account.
    Add them to hide it.
  - `poll.drop_columns`: poll columns to remove.

## Privacy notes

- `private/materials-YYYYMM/` holds **unredacted** material: the original files, and in `review/`
  the flagged text in `flag-report.md`. Never commit or share it.
- Only `docs/materials-YYYYMM/` is meant to be committed.
  Look through those files once more before you do.
- Participant IDs are random UUIDs and no key is kept, so they cannot be traced back to people.
- Join and leave times are kept to the second.
  In a small meeting these could identify someone to a person who also has the original Zoom export.
- A shared host login can appear as one participant when several people used it.
- Images embedded in `.docx` files are not carried over; the run warns you when there are any.

## Running the tests

```bash
python -m unittest discover -s code/materials-archiving/tests -v
```

The tests build their own invented documents and Zoom files, so they contain no real data.
