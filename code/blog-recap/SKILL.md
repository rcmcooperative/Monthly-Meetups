---
name: blog-recap
description: Write the blog-style recap post for an RCM Cooperative monthly meet-up from its source material (Zoom chat, collaborative notes, poll, registration report, speaker slides, invitation text). Use when asked to write, draft or continue a meet-up recap or blog post for a given month.
---

# Meet-up recap blog

Turns one month's meet-up material into a recap post in the house structure (front matter, What happened, What worked well, Room to grow, Join us next time).
A deterministic Python pipeline does everything that does not need judgement.
You (Claude) do the interpretive steps, and the person reviews each one before you go on.

Run every command from the **repo root**, never from inside the skill folder.
`--month` is the meet-up's month as YYYYMM, for example `202610`.

## Folders

| Folder | Holds |
|---|---|
| `private/materials-YYYYMM/` | the raw Zoom chat and registration report. **Never read anything in `private/`.** |
| `docs/materials-YYYYMM/` | made by the materials-archiving scripts: `facilitators-briefing.md`, `collab-notes.md`, the poll CSV, `comms-copy.md`, the speaker's slides (PDF) |
| `project-management/communications/blog-YYYYMM/` | everything the pipeline and you make: the anonymised chat, the digests, `session-inputs.json`, `blog-links.md`, the draft `mm-recap-YYYYMM.md` |
| `project-management/communications/blog-YYYYMM/review/` | your reviews, for the person to read |

Everything you write goes in the blog folder, `project-management/communications/blog-YYYYMM/`.
Do not copy anything into the post except as described below.

## What you may read

You only work from anonymised material.
- **Never read anything in `private/`** (the raw chat and the registration report). Do not try to get round this with a shell command.
- **Never run `--prepare` yourself.** The person runs it in their own terminal before opening Claude Code.
- The anonymised chat has also been link-redacted: a `<redacted>` placeholder stands where a link or email was removed. Never try to recover one.
- Work from `notes-digest.md`, not `collab-notes.md`: the digest has the participant list and names removed.
- You may read: the files in the blog folder (`*_anonymised.txt`, `chat-digest.md`, `notes-digest.md`, `poll-digest.md`, `registration-digest.md`, the saved answers and your own files), and in `docs/materials-YYYYMM/` the briefing, `comms-copy.md` and the speaker's slides.

## Rules that apply throughout

- **Privacy.** No participant names, employers, places or personal career detail from the chat or notes. Never mention room numbers: write "in small groups" or "across the discussions". The only people named in the post are the host, the speaker and the authors, who are named publicly in the invitation. Never publish a CryptPad edit link or a Slack invite link. The digests still contain identifying detail, so the draft must come from your reviews, not from the digests directly.
- **Style.** UK English. One sentence per line in markdown (semantic line breaks). Flag anything the person must decide or check with `<mark>…</mark>`.
- **Review gates.** After each review file, tell the person where it is, say in one or two sentences what to look for, and wait for them to confirm or correct it before the next step. Print complete files when you change them, not snippets.
- **Choices.** When you offer options (excerpt, coverage sentence), always include a "write your own" option and use the person's wording exactly if they give it. Use the multiple-choice question tool if you have one.
- **Be honest about what is inferred.** Label anything you synthesised or added beyond the source material.

## Workflow

### 0. Check the material

Ask for the month if it was not given.
Check, without opening the raw files, that the files exist and say plainly what is missing:

- `docs/materials-YYYYMM/`: `facilitators-briefing.md`, the poll CSV (name contains "poll"), `comms-copy.md`, the speaker's slides
- `project-management/communications/blog-YYYYMM/`: the anonymised chat (`*_anonymised.txt`), `notes-digest.md` and `registration-digest.md`

If the anonymised chat or `notes-digest.md` is missing, stop.
Tell the person to run this in their own terminal, from the repo root, **before** (re)opening Claude Code, and to come back afterwards:

```bash
python code/blog-recap/scripts/pipeline.py --month YYYYMM --prepare
# review the flagged links in the chat's .review.txt file in private/, then:
python code/blog-recap/scripts/pipeline.py --month YYYYMM --prepare --apply
```

### 1. Ask for what only the person knows

Ask for these together, in one go:

1. the **registration link** for the next session
2. the **recording link**, or "none" if it is not published yet
3. the **materials archive link** (the GitHub folder for this month)
4. the **authors**, each as their file name in the website's `_team` folder without `.md`. Point the person to the folder: https://github.com/rcmcooperative/rcmcooperative.github.io/tree/main/_team. For an author who is not on the team, ask for a name and a link.

Run the pipeline with those as flags:

```bash
python code/blog-recap/scripts/pipeline.py --month YYYYMM \
  --register-url URL --recording-url URL_OR_none --archive-url URL \
  --author SLUG --author SLUG --external-author "Name|https://link"
```

The pipeline then tries to read the **next session's date, time and theme from its Zoom registration page**.
It respects the site's robots.txt and makes one request, so this often fails: that is expected.
If it stops with "could not get the next session's details":

1. Say what could not be read and why (the message says).
2. You may try your own web fetch tool on the registration link once. If it fails too, do not try other ways round it.
3. Ask the person for the missing date, time and theme. If the Zoom chat announced the next session, you can suggest those values as a starting point, but ask the person to confirm them. Never fill them in yourself.
4. Run the pipeline again with `--next-date`, `--next-time` and `--next-theme`. Everything is saved, so nothing else is asked twice.

If values were read from the page, show them to the person and ask them to confirm before going on.

### 2. Run the pipeline

The same command runs the five main stages (session inputs, chat digest, poll digest, comms copy, blog links); the anonymising stages already ran in `--prepare`.
Read the output.

- Stop and tell the person if any stage reports a **LEAK** or stops with an error.
- Relay every **CHECK** line (for example, a registration report generated before the meeting means the registered count may be too low).
- If a file such as the poll or registration report is missing, the stage says so and skips: tell the person.

### 3. Chat summary → `review/chat-summary.md`

Read `chat-digest.md` (made from the anonymised chat) against the event purpose in the briefing.
Cover: what the chat shows about the purpose (shared identity inside the community; legibility to outsiders), the most-reacted messages (keep the reaction counts: they show warmth, not headcount), calls to action, the links table with its handling column (public / private / check; links the redaction rules removed no longer appear, so say that some were redacted), and the fun moments.
Do not map the chat to the agenda.
Use participant labels or no names; never reproduce a CryptPad or Slack link.
End with flags for anything inferred.

### 4. Notes review → `review/notes-review.md`

First tell the person what you will look for in the collaborative notes and get a nod.
Then read `notes-digest.md` against the meeting purpose and the exercises described in the notes (this covers the breakout discussions).
Cover: how complete the notes are, the routes and themes across the groups, how the groups' notes differ, each exercise's outcome, how well the purpose was met, tensions and open questions, a cross-check with the chat, and candidate takeaways.
Rooms may be numbered in this review (it is not published), personal careers at theme level only.

### 5. Exercises completion → `review/exercises-completion.md`

The notes digest lists the exercise tasks, numbered (1, 1.1, 1.3.2 …).
Where the groups did not complete a task in the session, complete it here from the notes.
Write a table `| ID | Task | Status | Evidence |` with **one row per task ID** and a status that is exactly one of:

- `Done in session`
- `Partly done in session`
- `Not done in session (completed here)`

Then give the completed content for each task: for example, reflection answers drawn across groups, a draft collaborative story with a table showing which notes each sentence came from, the implications of emphasising different parts, and the audiences, labelling anything added beyond the notes.
State plainly that a story built here is a synthesis, not something the group wrote.
Highlight flags with `<mark>`.

Check it before showing the person:

```bash
python code/blog-recap/scripts/pipeline.py --month YYYYMM --check
```

### 6. Poll summary → `review/poll-summary.md`

Read `poll-digest.md`.
The poll is a Likert scale from 5 (strongly agree) to 1 (strongly disagree), the same each month.
Write **one or two sentences** giving the percentage at each sentiment, not the mean.
Say "agreed or strongly agreed" for the combined figure.

### 7. Wording options → `review/blog-options.md`

From the notes review, the slides and the chat summary, write three or four options for each of:

- `{{EXCERPT}}`: one short sentence for the blog listing
- `{{BLOG_COVERAGE}}`: the end of the sentence "This post summarises what we discussed …"

Add "write your own" as the last option for each.
Warn the person if an option promises something the post must then contain, or leans on a synthesis.
Ask them to choose, and use their choice or their own wording exactly.

### 8. Ask for the rest

Ask for anything still missing: the post **title**, the **publication date**, the **number who attended live** (from Zoom's participants report: it is not in the pipeline's files), and the **Slack joining instructions** (never the invite link from the chat).
Say that the registered count comes from the registration report and may be out of date if the report predates the meeting.

### 9. Draft the post → `project-management/communications/blog-YYYYMM/mm-recap-YYYYMM.md`

Start from `code/blog-recap/templates/blog-template.md`.
The template's notes comment lists where each placeholder comes from.
Fill the placeholders, then **delete the template notes comment and every guidance comment**.

- Front matter `authors:` and the host and speaker sentence come from `project-management/communications/blog-YYYYMM/blog-links.md`, already formatted and linked. Copy them as they are.
- **What happened** is a high-level account of the session. Pull its structure from the speaker's slides (introduction, exercises in order, the talk) and its substance from the chat summary and notes review. Open with the objectives from the briefing. Keep what the group did, found and drafted separate from what you synthesised.
- **Findings from the session** (a subheading under What happened) gives general findings or outcomes across the discussions, not a group-by-group account.
- **What worked well** uses the poll percentages. **Room to grow** is constructive and based on the poll, chat and notes.
- **Join us next time** uses the next session's details and links from `blog-links.md`. The closing paragraphs in the template are the team's own wording: keep them.
- Leave the header image placeholders (`{{IMAGE_SLUG}}`, `{{IMAGE_ALT}}`) for step 11.
- Keep a `<mark>` on anything unresolved.

Check it:

```bash
python code/blog-recap/scripts/pipeline.py --month YYYYMM --check
```

It fails on leftover placeholders, comments, room numbers, anonymisation labels, CryptPad or Slack invite links, and the name or email of any registrant who is not the host, speaker or an author.
Fix every PROBLEM.
Show the draft to the person and iterate until they are happy.

### 10. Resolve the highlights

Go through each `<mark>` with the person and remove it once resolved.

### 11. Last: the header image

Only now, when the person is ready to push the post to the website repo, ask for the **header image**:

- Ask them to choose an image, to be used as the header and the thumbnail.
- Tell them to add it to `assets/img/blog` in the website repo: https://github.com/rcmcooperative/rcmcooperative.github.io/tree/main/assets/img/blog. The file name follows the pattern `mm-YYYYMM-<short-description>.png`.
- Ask for the file name and for alt text describing the image.
- Fill `{{IMAGE_SLUG}}` and `{{IMAGE_ALT}}`, then run the check with `--final`, which also fails on any remaining highlight or image placeholder:

```bash
python code/blog-recap/scripts/pipeline.py --month YYYYMM --check --final
```

When it passes, tell the person the post is ready to copy into the website repo.
Also tell them to **read everything in the blog folder themselves before committing**: the anonymised chat, the digests, the reviews and the draft. Everything there is committed to the repo, and the checks are a safety net, not a substitute.
Do not push anything to the website repo yourself.

## If something goes wrong

- A stage stops with an error: read it, tell the person, and fix the cause (a missing file, a malformed chat export). Do not work round a LEAK: names must be removed before anything continues.
- The same question is never asked twice: answers are saved in `project-management/communications/blog-YYYYMM/session-inputs.json`. A flag on the command line replaces a saved value.
- To change the nicknames scrubbed from chats, the team names allowed in a post, or the website links, edit `code/blog-recap/scripts/config.py`.
