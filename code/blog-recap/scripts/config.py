"""Shared settings for the meetup blog pipeline."""

# Nicknames that appear in chat messages but not in Zoom display names.
# Each is scrubbed to "[name]" in the anonymised chat. Edit as the team changes.
EXTRA_NAMES = ["Cass", "Ale"]

# Raw exports (the Zoom chat and registration report: names and email addresses)
# live here, relative to the repo root, one folder per meetup:
# private/materials-YYYYMM. Claude Code is denied access to all of private/.
PRIVATE_DIR = "private"
MATERIALS_PREFIX = "materials-"

# Everything the skill makes (anonymised chat, digests, saved answers, reviews and
# the draft post) goes in one folder per meetup, which Claude may read and write:
# project-management/communications/blog-YYYYMM
OUTPUT_DIR = "project-management/communications"
BLOG_PREFIX = "blog-"
# Claude's reviews are saved in blog-YYYYMM/review/
REVIEW_SUBDIR = "review"

# Published/archived material (e.g. the facilitators' briefing) lives here,
# in the same materials-YYYYMM folder naming.
DOCS_DIR = "docs"

# Fixed text for the "Join us next time" section: the same every month.
ISSUES_URL = "https://github.com/rcmcooperative/Monthly-Meetups/issues"
SUGGESTION_TEMPLATE = "Monthly Meetup Suggestion"

# Authors are credited by their file name in this folder of the website repo.
TEAM_DIR_URL = "https://github.com/rcmcooperative/rcmcooperative.github.io/tree/main/_team"

# Where header images for posts are added (a different repo from this one).
IMAGE_DIR_URL = "https://github.com/rcmcooperative/rcmcooperative.github.io/tree/main/assets/img/blog"

# Names that may appear in a post even though they are also in the registration
# report (the team). Hosts, speakers and authors are allowed automatically.
ALLOWED_NAMES = ["Emma Karoune", "Cassandra Gould van Praag", "Malvika Sharan"]

# Link and secret redaction reuses the rules of the materials-archiving skill, so the two
# cannot drift apart: one redaction.toml, one detector. Relative to the repo root.
ARCHIVING_DIR = "code/materials-archiving"

# Written to .claude/settings.json by `pipeline.py --setup-claude`: Claude Code's file tools
# are denied everything in private/ (the raw Zoom exports).
CLAUDE_SETTINGS = ".claude/settings.json"
CLAUDE_DENY_RULES = ["Read(./private/**)"]
