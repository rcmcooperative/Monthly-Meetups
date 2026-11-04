"""Find text that should be reviewed for redaction, and wrap it in <redact></redact>.

Flag by default, allow by exception: every URL and email address that the config does not
explicitly allow is flagged. Spans already wrapped in <redact> by a person are left alone.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s<>\"'\])]+")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
REDACT_SPAN_RE = re.compile(r"<redact>.*?</redact>", re.S)
HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.*?)[ \t#]*$", re.M)
TRAILING_PUNCTUATION = "*.,;:!?\\"


@dataclass
class Finding:
    start: int
    end: int
    kind: str      # "url", "email", "pattern"
    reason: str
    blocking: bool  # True for always-flag items that may never remain in an archived file
    line: int = 0

    def text(self, source: str) -> str:
        return source[self.start:self.end]


def _clean_url(match: re.Match) -> tuple[int, int, str]:
    url = match.group(0)
    stripped = url.rstrip(TRAILING_PUNCTUATION)
    return match.start(), match.start() + len(stripped), stripped


def _host_path_allowed(url: str, entries: list[str]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    for entry in entries:
        domain, _, prefix = entry.lower().partition("/")
        if host != domain and not host.endswith("." + domain):
            continue
        if not prefix:
            return True
        want = "/" + prefix.strip("/")
        if path.lower() == want or path.lower().startswith(want + "/"):
            return True
    return False


def role_allowed_urls(text: str, headings: list[str]) -> set[str]:
    """URLs in the bullet list directly under a heading such as "Speaker" or "Host"."""
    if not headings:
        return set()
    heading_line = re.compile(r"[#*\s_]*(?:" + "|".join(re.escape(h) for h in headings) + r")[*\s:_]*", re.I)
    lines = text.splitlines()
    allowed: set[str] = set()
    i = 0
    while i < len(lines):
        if lines[i].strip() and heading_line.fullmatch(lines[i]):
            j = i + 1
            while j < len(lines):
                s = lines[j].strip()
                if not s:
                    j += 1
                elif s.startswith(("- ", "* ")):
                    allowed.update(_clean_url(m)[2] for m in URL_RE.finditer(s))
                    j += 1
                else:
                    break
            i = j
        else:
            i += 1
    return allowed


def find_findings(text: str, config: dict, role: str) -> list[Finding]:
    rules = config["redaction"]
    existing = [(m.start(), m.end()) for m in REDACT_SPAN_RE.finditer(text)]
    candidates: list[Finding] = []

    # Patterns first: they are the widest and win any overlap.
    for pat in rules.get("patterns", []):
        group = pat.get("group", 0)
        for m in re.finditer(pat["regex"], text):
            s, e = m.span(group)
            if s >= 0:
                candidates.append(Finding(s, e, "pattern", pat["reason"], True))

    always = [re.compile(p, re.I) for p in rules["urls"].get("always_flag", [])]
    allow = rules["urls"].get("allow", [])
    role_ok = role_allowed_urls(text, rules["urls"].get("role_allow", {}).get(role, []))
    for m in URL_RE.finditer(text):
        s, e, url = _clean_url(m)
        hit = next((p.pattern for p in always if p.search(url)), None)
        if hit:
            candidates.append(Finding(s, e, "url", f"always-flag: URL matches {hit}", True))
        elif url in role_ok or _host_path_allowed(url, allow):
            continue
        else:
            candidates.append(Finding(s, e, "url", "URL is not on the allowlist", False))

    allow_domains = [d.lower() for d in rules["emails"].get("allow_domains", [])]
    exempt = {h.strip().lower() for h in rules["emails"].get("exempt_headings", [])}
    heading_starts = [m.start() for m in HEADING_RE.finditer(text)]
    heading_names = [m.group(1).strip().lower() for m in HEADING_RE.finditer(text)]
    for m in EMAIL_RE.finditer(text):
        domain = m.group(0).rsplit("@", 1)[1].lower()
        allowed = any(domain == d or domain.endswith("." + d) for d in allow_domains)
        if allowed:
            k = bisect.bisect_right(heading_starts, m.start()) - 1
            if k >= 0 and heading_names[k] in exempt:
                allowed = False
        if not allowed:
            candidates.append(Finding(m.start(), m.end(), "email", "email address", False))

    # Resolve overlaps (widest first) and skip anything a person has already wrapped.
    candidates.sort(key=lambda f: (f.start, -(f.end - f.start)))
    accepted: list[Finding] = []
    for f in candidates:
        if any(s <= f.start < e or s < f.end <= e for s, e in existing):
            continue
        if accepted and f.start < accepted[-1].end:
            continue
        accepted.append(f)

    line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
    for f in accepted:
        f.line = bisect.bisect_right(line_starts, f.start)
    return accepted


def wrap_findings(text: str, findings: list[Finding]) -> str:
    out, pos = [], 0
    for f in findings:
        out.append(text[pos:f.start])
        out.append(f"<redact>{text[f.start:f.end]}</redact>")
        pos = f.end
    out.append(text[pos:])
    return "".join(out)


def preview(value: str, limit: int = 60) -> str:
    value = value.replace("\n", " ")
    return value if len(value) <= limit else value[: limit - 1] + "…"
