---
name: populate-repo-template
description: Fills in template placeholder sections of an RCM Cooperative partner template README (adapted from The Turing Way reproducible project template) — Vision and Mission, About, About this Repository, Roadmap & Milestones, The Team, Contributing, Citing & Acknowledgement, Contact — using project documentation, and updates CONTRIBUTING.md and CODE_OF_CONDUCT.md with matching project partner and contact info. Use this whenever the user asks to fill out, complete, populate, or flesh out README template sections. Reads CLAUDE.md as the primary source, and reads ../team/people/team.csv for Team section contributor selection. For gaps neither source covers, asks the user directly — either to answer inline, or to paste a chat transcript/summary from elsewhere (e.g. a claude.ai conversation) for the skill to extract from. Never overwrites sections that already contain real content — flags them for review instead.
---


# Populate Repo Template

Fills template placeholder sections in a partner-template-style README using existing project documentation, without silently overwriting real content.
Also reviews and updates CONTRIBUTING.md with matching project partner and contact info gathered during the README process.

## Repo convention

This skill expects two sibling directories under the same parent folder: this project repo (e.g. `rcm-crm/`), and the `team` repo (rcmcooperative/team), cloned alongside it — not nested inside it.
Inside the `team` repo, the relevant file is at `people/team.csv`.
The expected path is `../team/people/team.csv` relative to the project repo root.
This file is the full, flat list of all cooperative members — not project-specific.
If this path doesn't resolve, fall back to asking the user directly rather than failing silently.

## Process

### 1. Identify the README and read it
Find `README.md` at the repo root.
Read it in full.

### 2. Classify every section as one of three types
- **Placeholder** — contains template instructional text (e.g. "Short phrase describing...", "Add a description here", `<Team member name>`, `<insert the repo's name>`, or other placeholders using `<...>` syntax, or near-empty headers with no real sentences under them).
This is the standard placeholder convention across all RCM Cooperative templates — treat `<...>` as the marker for "safe to fill."
These are safe to fill.
- **Filled** — contains real, specific sentences that clearly describe this actual project (not generic template language).
These must NOT be overwritten.
- **Partially filled** — mix of real content and leftover placeholder text in the same section.
Treat as Filled for safety — flag, don't auto-edit.

When uncertain whether something is a placeholder or real content, err toward treating it as Filled (flag, don't touch) rather than guessing.

### 3. Read primary source docs
Look for `CLAUDE.md` at the repo root first.
This is the primary source of project context — read it in full before asking the user anything.

For the Team section specifically, also look for `../team/people/team.csv`.
Read it if present, but do not assume who belongs to this project — see step 5a.

### 4. Map template sections to what the source docs can answer
Typical Turing Way partner-template sections and where they usually map:
- **Vision and Mission** → project overview section of CLAUDE.md
- **About** → project overview, architecture summary
- **About this Repository** → fixed template, see step 5b — do not freely generate this section
- **Roadmap & Milestones** → feature set, resolved/deferred decisions, v1 vs v1.1+ scope — output as a checklist, see step 5c
- **The Team** → selected subset of `../team/people/team.csv`, see step 5a
- **Contributing** → check for existing CONTRIBUTING.md / CODE_OF_CONDUCT.md files first; link to them rather than duplicating content
- **Citing & Acknowledgement** → check for existing LICENSE.md; also check CLAUDE.md for any mention of a prior/originating repository this project evolved from — see step 5d
- **Contact** → selected from the project team (see step 5a) — do not ask separately unless team.csv wasn't found
- **Checklist for setting up an online repository** → leave untouched entirely; this is for human review, not filled or checked by the skill

### 5. Draft content for Placeholder sections only

**5a. Team section — selection workflow**
These are two separate, sequential prompts.
Do not combine them into a single question — the second question depends on the answer to the first, and cannot be asked until the first is answered.

1. Read the full `../team/people/team.csv`.
2. Sort all entries alphabetically by first name.
3. Display the list to the user as a numbered list (one person per line).
4. Ask only this question, and wait for the reply before continuing: "Which numbers should be included in this project's team?"
5. Once the user replies, write the selected rows into a new local `team.csv` in this project repo (e.g. at the repo root or in a `project-management/` folder — ask the user if unclear which).
6. Use the selected rows' details (name, ORCID, GitHub username, role) to populate the README's Team section.
7. Re-display only the selected people, alphabetical by first name, numbered again (a fresh, shorter numbered list).
8. Now ask the second question, separately: "Which of these should be the primary contact for this project?"
9. Use that person's details to populate the README's Contact section.

If `../team/people/team.csv` isn't found, skip straight to asking the user directly for team member names/details, one question at a time, and separately ask who the primary contact is.

**5b. About this Repository — fixed template**
This section always uses the following template.
Do not generate freeform content for it.

First, check CLAUDE.md for the project name and any partner names.
Then explicitly confirm with the user before filling the template — do not assume CLAUDE.md is complete or guess at URLs:
"To complete the About this Repository section, please confirm: the project name, the name(s) of any partner organisations, and a URL for each partner (for linking). If this is an internal cooperative project with no external partners, let me know and I'll adjust the wording accordingly."

Fill only the bracketed placeholders using the confirmed answers.
If this is the cooperative's own internal project rather than a client collaboration, state that plainly rather than forcing a "partner" framing.

```markdown
This repository contains the documentation, research materials, and outputs for the <insert project name> project, a collaboration between <insert partner names> and [RCM Cooperative](http://rcmcooperative.com/).

This project follows open research principles to deliver FAIR and openly licensed materials. Publication of these materials supports transparency in this project, and reproducibility of similar work. All materials from the project are published as open as possible, as closed as necessary.
```

**5c. Roadmap & Milestones — checklist format**
Output as a markdown checklist, not prose or plain bullets:
```markdown
- [ ] Item one
- [ ] Item two
```
All items must be output unchecked (`- [ ]`), regardless of what CLAUDE.md indicates as resolved or in-progress.
Do not check any item off — checking items is for human review only, not something the skill determines.

**5d. Citing & Acknowledgement — prior repository check**
Scan CLAUDE.md for any statement that this project evolves from, is based on, or replaces an earlier repository or project (e.g. phrases like "evolves from", "prior MVP", "replaces the ... layer").
If found, include an acknowledgement of that prior repository in this section — name it and link to it — rather than leaving it uncited.
If CLAUDE.md gives no such indication, proceed to ask the user as normal (step 5e) rather than assuming there is or isn't a prior repository.

To get the citation for the prior repository, check both possible sources and cross-reference:
1. Look for a `CITATION.cff` file in the prior repository — this is the structured, primary source (standardised YAML fields: authors, title, doi, date-released, etc.).
2. Also look for a rendered "Citation" or "Citing" section in that repository's README.
3. If both exist and agree, use the citation with confidence.
4. If both exist and disagree, flag the discrepancy to the user rather than silently picking one — show both versions and ask which to use.
5. If only one source exists, use it, but note in the diff-preview that only one source was found (lower confidence, worth a sanity check).

**5e. Everything else**
Using CLAUDE.md first.
For anything CLAUDE.md doesn't cover (commonly: Contact, sometimes Citing), explicitly ask the user:
"I don't have information for [section] in CLAUDE.md. Do you have a chat transcript/summary I should pull this from, or should I ask you directly?"

If the user provides a transcript, extract only what's relevant to the specific gap — don't dump unrelated content into the README.

### 6. Present a diff-style summary before writing anything
Show the user, per section:
- **Placeholder → proposed content** (for sections being filled)
- **Filled → flagged, no change** (list section names only, so the user knows what was skipped and can update manually if needed)

Wait for explicit confirmation before writing to the actual README.md file.

### 7. Write only the confirmed/approved sections
Do not touch any section not explicitly listed as Placeholder in step 2, even if it seems related.

### 8. Review and update CONTRIBUTING.md
After the README is written, check `CONTRIBUTING.md` for placeholder or missing project partner names and contact info.
Reuse the same values already gathered in steps 5b (partner names) and 5a (primary contact) — do not re-ask the user for information already collected.
Apply the same classification logic as step 2: only fill genuine placeholders, flag anything that looks like real existing content rather than overwriting it.
Present a diff-style summary and wait for confirmation before writing, same as step 6.

### 9. Fill .all-contributorsrc and the all-contributors badge
If `.all-contributorsrc` exists and contains placeholder values (e.g. "<insert the repo's name>", "<insert the repo's owner/orgs>"), fill it using the actual git remote, not CLAUDE.md or user input:
1. Run `git remote -v` (or read `.git/config`) to get the GitHub remote URL.
2. Parse the URL to extract the org/owner (`projectOwner`) and repo name (`projectName`).
3. Update the two fields in `.all-contributorsrc` using these values.

Also check the README for the all-contributors badge block:
```markdown
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/github/all-contributors/<org>/<repo-name>?color=ee8449&style=flat-square)](#contributors)
<!-- ALL-CONTRIBUTORS-BADGE:END -->
```
If present with placeholder `<org>`/`<repo-name>`, fill using the same values parsed from the git remote in step 1 above — do not ask the user or re-derive separately.

Even though these values come from a verifiable source (git itself, not inference), include both changes in the diff-style summary from step 6 so the user can see exactly what was written before/alongside the rest of the confirmation.

### 10. CODE_OF_CONDUCT.md — RCM Cooperative CoC gate and contact selection
First, ask the user directly: "Is this project using the RCM Cooperative Code of Conduct?"

If **no**: do not fill or modify CODE_OF_CONDUCT.md at all.
Instead, ask the user for a link or reference to the client's own existing policy, and add a short signposting note in the README (e.g. in Contributing) pointing to it, rather than copying any RCM Cooperative CoC content into this repo.

If **yes**: the CoC body text (sections 1–9, 11–15) is fixed, cooperative-wide content and must not be altered — treat it as Filled, not Placeholder, per step 2.
Only Section 10.1 (the named contacts) is project-specific:
1. Re-use the team selection already made in step 5a if available, or read `../team/people/team.csv` directly if this section is being run independently.
2. Display the relevant people as a numbered list, alphabetical by first name.
3. Ask the user to select exactly three people to be named as contacts for this project's Code of Conduct.
4. Populate Section 10.1 with the three selected people's names and emails, using `<...>` placeholders as the fill target.

Present a diff-style summary and wait for confirmation before writing, same as step 6.

## Output format expectations
- UK English spelling
- Start each new sentence on a separate line (semantic line breaks) — makes diffs easier to read in version control
- Match the existing tone/register of the Turing Way template (plain, direct, not overly formal)
- Keep each section reasonably brief — this is a project README, not full documentation (full docs live elsewhere, e.g. `docs/`)
- Roadmap & Milestones specifically: markdown checklist format, not prose
- About this Repository specifically: use the fixed template exactly, only filling bracketed placeholders