# How to use blog-recap

Turns the source material from an RCM Cooperative monthly meet-up (Zoom chat, collaborative notes, poll, registration report, speaker slides, invitation text) into a blog-style recap post.

It works in two phases:

1. **On your own computer, with no AI.** A deterministic Python pipeline anonymises the chat, digests the notes and poll, and counts registrations.
2. **In Claude Code.** Claude does the interpretive steps (the reviews and the draft) from the anonymised results only. You supply a few things only you know, read what Claude writes at each step, and correct it.

Do the phases in this order, every month.
Claude Code is not needed, and not mentioned, until Part 3.

| Part | What | When |
|---|---|---|
| 1. Check the set-up | `.gitignore`, team settings | once |
| 2. Prepare the material | archive the materials, add the Zoom exports, anonymise, review the chat's links | each month, before Claude |
| 3. Set up Claude Code | account, install, settings | once |
| 4. Write the post with Claude | open Claude Code, review, draft, review again | each month, after Part 2 |

---

## Part 1. Check the set-up (once)

The skill is already in the repo at `code/blog-recap/`.
It reuses the link-redaction rules of the materials-archiving skill, so that must be in the repo too, at `code/materials-archiving/`.

### 1. Keep private material out of git

Check that `private/` is in your `.gitignore`.
The raw chat and registration report contain names and email addresses and must never be committed.

### 2. Check the settings

`code/blog-recap/scripts/config.py` holds the settings for your team: nicknames to scrub from chats, team names allowed to appear in a post, and the website links.
They are set for RCM Cooperative.

---

## Part 2. Prepare the material (each month, before Claude)

All of this runs in your own terminal, from the repo root.
Nothing is sent anywhere.

### 1. Archive the meet-up materials

The briefing, the collaborative notes, the poll results, the invitation text and the speaker's slides are all made by the materials-archiving scripts.
**Run those first**: they are a required step before this one.
See [how to prepare these materials](../materials-archiving/HOW_TO_USE.md).

That leaves these in `docs/materials-YYYYMM/` (`YYYYMM` is the meet-up's month, for example `202610`):

- `facilitators-briefing.md`
- `collab-notes.md`
- the poll results (`.csv`, name contains "poll")
- `comms-copy.md` (the invitation text, with the Speaker and Host lists)
- the speaker's slides (`.pdf`)

### 2. Add the two raw Zoom exports

These are not archived, because they contain names and email addresses.
Put them in `private/materials-YYYYMM/`:

| File | Name contains |
|---|---|
| the Zoom chat download (`.txt`) | "chat" |
| the Zoom registration report (`.csv`) | "registration" |

If you downloaded the registration report before the meeting, download it again afterwards: the registered count in the post comes from it.

### 3. Anonymise

The first time, create the conda environment.
The code only uses the Python standard library, so the environment is just Python 3.11 or later:

```bash
conda env create -f code/blog-recap/environment.yml
```

Then, from the repo root, each month:

```bash
conda activate blog-recap
python -m unittest discover -s code/blog-recap/tests   # first time only: check it works
python code/blog-recap/scripts/pipeline.py --month YYYYMM --prepare
```

This:

1. anonymises the Zoom chat and **flags every link and email address** that is not on the allowlist, writing a review file to `private/materials-YYYYMM/` (`..._anonymised.review.txt`, with a list of the flags beside it)
2. writes `notes-digest.md` to `project-management/communications/blog-YYYYMM/`: the collaborative notes with the participant list stripped first, then names removed
3. writes `registration-digest.md` there too: the number registered, totals only

The raw chat and registration report stay where they are, in `private/`.
If it reports a name still present in an output, it stops and deletes that output.
Add the name with `--extra-name "Nickname"` and run it again.
Add a nickname that always needs scrubbing to `config.py`.

### 4. Review the flagged links

Zoom chats hold CryptPad edit links, Slack invitations, Zoom links and personal pages.
The rules are the ones the materials-archiving scripts use: **flag by default, allow by exception**.
Zoom, Slack, CryptPad, Google edit links, tracking links and anything carrying a password or token are always flagged (blocking).
Every other link or email address is flagged unless it is on the allowlist (`code/materials-archiving/config/redaction.toml`).
Names are not link-redacted: they were already replaced when the chat was anonymised.

Open the review file in your editor.
Each flag is wrapped in `<redact>…</redact>`:

- leave the tags to redact it
- delete the two tags to keep the text visible (for a link that is public and useful)
- wrap anything else that should not be shared in `<redact></redact>`

Then apply the redactions:

```bash
python code/blog-recap/scripts/pipeline.py --month YYYYMM --prepare --apply
```

This checks the tags, replaces each one with `<redacted>`, and checks the result again.
It writes the chat Claude is given (`..._anonymised.txt`) to the blog folder, and only if the checks pass:

- a blocking link left visible always stops it
- any other link or email left visible stops it, unless you add `--accept-residual` to say it was on purpose

Running `--prepare` again keeps your review file, so your edits are safe; `--force` starts it again.

### 5. Read what will be shared

The chat Claude is given is **anonymised and link-redacted**, not just anonymised.
Anonymisation removes **names**, and the link rules remove links and secrets.
Neither removes what people said about themselves, such as a job or a career story in the notes or chat.
Read the files in `project-management/communications/blog-YYYYMM/` before going on, especially `notes-digest.md` if the group was small.

If you add or replace a chat or notes file later, run `--prepare` again, and `--apply` after reviewing it.

---

## Part 3. Set up Claude Code (once)

### 1. Get a Claude account and install Claude Code

Claude Code is Anthropic's command-line tool for working with Claude on your files.
It needs:

- **a Claude account on a paid plan** (Pro, Max, Team or Enterprise), or an Anthropic Console account with API credits. The free Claude.ai plan does not include Claude Code. Using Amazon Bedrock, Google Cloud or Microsoft Foundry also works.
- macOS 13+, Windows 10 (1809+) or a recent Linux (Ubuntu 20.04+, Debian 10+), 4 GB of RAM, and an internet connection.

Install it once (see the [official setup guide](https://code.claude.com/docs/en/setup) if anything has changed):

| System | Command |
|---|---|
| macOS, Linux, WSL | `curl -fsSL https://claude.ai/install.sh \| bash` |
| Windows PowerShell | `irm https://claude.ai/install.ps1 \| iex` |
| Homebrew | `brew install --cask claude-code` |
| WinGet | `winget install Anthropic.ClaudeCode` |

Check it with `claude --version`.
The first time you start it (`claude`, in Part 4), it opens a browser window for you to log in to your Claude account.

### 2. Make the skill visible to Claude Code

Claude Code finds skills in `.claude/skills/`, and loads the skill's instructions (`SKILL.md`) itself.
You do not need to read or run anything from that file: everything you need is in this guide.

From the repo root, link the skill into place:

```bash
mkdir -p .claude/skills
ln -s ../../code/blog-recap .claude/skills/blog-recap
```

On Windows, where links need extra permissions, copy the folder instead:

```powershell
mkdir .claude\skills
xcopy code\blog-recap .claude\skills\blog-recap /E /I
```

(A copy does not update when `code/blog-recap/` changes: copy it again after an update.)

### 3. Block Claude Code from `private/`

From the repo root, run:

```bash
python code/blog-recap/scripts/pipeline.py --setup-claude
```

This adds a deny rule for `private/` to `.claude/settings.json` in your repo.
It creates the file if it is missing, and if it exists it keeps your other settings and adds the rule once.
(If the file is not valid JSON it stops and changes nothing.)
The rule stops Claude Code's file tools reading anything in `private/`, where the raw exports are.

**This is a guardrail, not a hard wall.**
The rule blocks Claude's own file-reading tools.
As far as we know it does not stop a shell command run by Claude, such as `cat private/...`, and the skill's instructions are what tell Claude not to try.
If you need a guarantee, run Claude Code in a copy of the repo that has no `private/` folder (the draft check then cannot look for registrants' names, so run `--check` yourself in the real repo), or use Claude Code's sandbox settings.

### 4. Know what Claude is given

Anything Claude reads is sent to Anthropic to be processed, so Claude is only given anonymised material.
Check that this is allowed for your group's data rules.

| Claude reads | What it is |
|---|---|
| `*_anonymised.txt` and `chat-digest.md` | the chat with every name replaced by `Participant NN`, reactions counted, and links redacted unless allowed |
| `notes-digest.md` | the collaborative notes with the participant list, privacy notice and names removed |
| `poll-digest.md` | poll results as percentages, with no respondent details |
| `registration-digest.md` | the number registered, nothing else |
| `facilitators-briefing.md`, `comms-copy.md`, the slides | already public or written for the event |
| your answers (links, authors, title, dates) | typed by you |

Claude is told not to read the raw chat or the registration report in `private/`, and not to read `collab-notes.md`.
The archived notes keep their participant list, as the privacy notice on that document allows, but Claude works from the digest, which has it removed.

The draft check also fails on anything that looks like a participant's name or email in the post.

---

## Part 4. Write the post with Claude (each month, after Part 2)

### 1. Open Claude Code

From the repo root (not inside the skill folder), with the conda environment active:

```bash
conda activate blog-recap
claude
```

Log in with your Claude account if asked, then ask, for example:

> Write the recap blog for the October 2026 meet-up (202610).

Claude follows the skill from here.
If the prepared files are missing, it stops and tells you to run Part 2.

### 2. Answer the first questions

Claude asks for, all at once:

- the **registration link** for the next session
- the **recording link**, or "none" if it is not published yet
- the **materials archive link** (the GitHub folder for this month)
- the **authors**: each as their file name in the website's [`_team` folder](https://github.com/rcmcooperative/rcmcooperative.github.io/tree/main/_team), without `.md` (for example `emma-karoune`). For anyone not on the team, give a name and a link.

Claude then tries to read the next session's date, time and theme from its registration page.
Zoom often blocks this.
If it cannot, Claude asks you for the date, time and theme.
Your answers are saved, so you are never asked the same thing twice.

### 3. Read each review, and correct it

Claude runs the pipeline, then writes a series of reviews into `project-management/communications/blog-YYYYMM/review/`.
Open each file in your editor, read it, and tell Claude what to change.
Claude waits for you before moving on.

| Review | What to look for |
|---|---|
| `chat-summary.md` | does it reflect the tone of the session? Are the links handled correctly (public, private, check)? |
| `notes-review.md` | do the themes match what you remember? Is anything over-read from thin notes? |
| `exercises-completion.md` | where the groups did not finish an exercise, Claude completes it from the notes and labels it. Check these completions, and remember a story built this way is a synthesis, not the group's own words |
| `poll-summary.md` | one or two sentences, as percentages for each sentiment |
| `blog-options.md` | options for the excerpt and for the end of the sentence "This post summarises what we discussed …". Choose one, or write your own |

### 4. Fill the gaps

Claude asks for what is not in any file:

- the post **title** and **publication date**
- how many people **attended live** (from Zoom's participants report)
- the **Slack joining instructions** (never paste the invite link from the chat)

### 5. Review the draft

Claude writes the post to `project-management/communications/blog-YYYYMM/mm-recap-YYYYMM.md` and checks it.
The check fails on:

- placeholders not filled in, or template comments left in
- room numbers
- a CryptPad or Slack invite link
- the name or email of anyone who registered, apart from the host, speaker and authors

Anything Claude is unsure about is highlighted with `<mark>`.
Read the draft, ask for changes, and settle each highlight with Claude.

### 6. The header image

When you are ready to push the post to the website repo, Claude asks for the header image (used as the thumbnail too).

1. Choose an image.
2. Add it to [`assets/img/blog`](https://github.com/rcmcooperative/rcmcooperative.github.io/tree/main/assets/img/blog) in the website repo, named `mm-YYYYMM-<short-description>.png`.
3. Give Claude the file name and a short description of the image (alt text).

Claude then runs the final check.

### 7. Review everything before you commit

Everything in `project-management/communications/blog-YYYYMM/` is committed to the repo: the anonymised chat, the digests, Claude's reviews, your saved answers and the draft.
Before you commit, **read all of it yourself**, as if it were going public:

- no participant's name, employer or place, in the chat, the digests or the reviews
- no CryptPad edit link or Slack invite link
- nothing in the reviews you would not want colleagues to read (they mention room numbers and quote the groups' discussions)

Delete or edit anything that should not be shared.
The checks are a safety net, not a substitute for this read.

Then copy the post into the website repo yourself.
Claude does not push to it.

---

## Reference

### Folders

| Folder | Holds | In git? |
|---|---|---|
| `private/materials-YYYYMM/` | the raw Zoom chat and registration report, and the chat's link-review file and flag list (they hold the unredacted links); Claude is not allowed to read it | no |
| `docs/materials-YYYYMM/` | facilitators' briefing, collaborative notes, poll CSV, invitation text, speaker slides, made by the materials-archiving scripts | yes |
| `project-management/communications/blog-YYYYMM/` | the anonymised chat, the digests, `session-inputs.json` (your saved answers), `blog-links.md`, the draft post | yes, after your review |
| `project-management/communications/blog-YYYYMM/review/` | Claude's reviews, for you to read | yes, after your review |

### Running the pipeline and checks yourself

Always from the repo root.
To see every option:

```bash
python code/blog-recap/scripts/pipeline.py --month YYYYMM --help
```

To check the reviews and the draft:

```bash
python code/blog-recap/scripts/pipeline.py --month YYYYMM --check          # reviews and draft
python code/blog-recap/scripts/pipeline.py --month YYYYMM --check --final  # also highlights and image
```

To rerun the main pipeline after changing an input, run the same command Claude ran (without `--prepare`).
Saved answers are reused, and a flag such as `--author` or `--next-theme` replaces a saved one.

### Good to know

- **Privacy.** Names are removed from the chat and notes before Claude sees them, and the post never names participants, mentions room numbers or links to private notes. The check is a safety net: still read the draft with that in mind.
- **The registered count may be low** if the registration report was downloaded before the meeting. The pipeline warns you when that is the case.
- **Reaction counts** in the chat summary show warmth, not headcount.
- **If something stops with an error,** Claude reads it to you and fixes the cause. If it reports a name leak, nothing continues until that is fixed.
