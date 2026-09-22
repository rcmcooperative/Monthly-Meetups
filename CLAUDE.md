# CLAUDE.md — RCM Cooperative Project Template

## Working preferences (apply throughout this project)
- UK English spelling throughout.
- Brief, balanced responses — avoid large blocks of text, no sycophantic or superfluous language.
- Hold/go protocol: when given multiple pieces of information or files across turns, wait for explicit "go" before acting.
Don't process partial input.
- Default working format is markdown.
Pandoc is used to convert markdown to PDF for reports/dissemination.
- Prefer generalisable, reusable structures over one-off solutions.
Documentation is a deliberate, valued part of the process, not an afterthought.
- Prefer open-source over proprietary/big-tech tools.
Privacy-conscious, GDPR-aware — apply this by default to any project involving personal or community data.
- Prefer robust, well-architected solutions over quick manual workarounds (e.g. separate config profiles/aliases rather than editing a shared settings file each time).
- In documentation and markdown, start each new sentence on a separate line (semantic line breaks).
This makes diffs easier to read in version control.

## Project overview
<Short description of this specific project: what it is, who it's for, and how it relates to the RCM Cooperative's work.>

## Template conventions

**Placeholder syntax**: all placeholder text in this repo's template files uses `<...>` (angle brackets), not `[...]` or other syntax.
This is the standard convention across all RCM Cooperative templates.

**Populating this template**: this repo includes a Claude Code skill, `populate-repo-template`, which fills in the placeholder sections of README.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, and .all-contributorsrc using this CLAUDE.md as its primary source.
Run it via `/populate-repo-template` or by asking Claude Code to populate the template.

**Team data**: the skill expects the `team` repo (rcmcooperative/team) cloned as a sibling directory to this project repo, containing `people/team.csv` — the full, flat list of all cooperative members.
The skill reads this to let you select which people are on this project's team and who the primary contact is; it does not assume this itself.

**Code of Conduct**: if this project uses the RCM Cooperative's standard Code of Conduct, the skill will ask which three people should be named as contacts in Section 10.1, and populate that section only — the rest of the CoC is fixed content and should not be altered.
If this project uses a client's own existing policy instead, the skill will not modify CODE_OF_CONDUCT.md, and will instead add a signposting note to the client's policy.

## Local vs cloud model switching
Two fully separate Claude Code config profiles, so cloud and local never fight over the same settings file:

- **Cloud (default)**: `~/.claude/settings.json` — clean, no env overrides.
- **Local**: `~/.claude-local/settings.json` — for projects using a local model (e.g. Ollama/Qwen) instead of cloud, containing the relevant `env` block and model name.

**Aliases** (in `~/.zshrc`):
```bash
alias claude-cloud='claude --model claude-sonnet-4-6'
alias claude-local='CLAUDE_CONFIG_DIR=~/.claude-local claude'
```

Before starting work, check the active model/profile with `/status` inside the session.
Don't assume based on which alias you think you ran.

**Known gotcha**: an active conda environment can inject `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` via its activation scripts, silently routing a cloud session to a local model even with clean settings.json and no manually-set env vars.
If `/status` shows an unexpected base URL, run `conda deactivate` and check again before assuming a settings.json problem.

## Documentation & review process
<Note here where design/scope documentation for this project lives, whether the repo is private or public, and who reviews decisions before significant build work begins.>

## Project-specific architecture, decisions, or context
<Add sections here as needed for this specific project — resolved decisions, data model, feature scope, deferred items, ethical considerations, etc. Keep this file focused on what a new contributor or a future Claude Code session would need to know to work on this project correctly.>