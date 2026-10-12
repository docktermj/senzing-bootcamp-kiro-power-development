#!/usr/bin/env python3
"""Pre-filing gate: a drafted issue that claims the Senzing MCP server LACKS something must
name the route that would carry the fact.

    python3 .kiro/skills/feedback-to-issues/issue_body_check.py <issue-body.md> [...]

Exit 0 when every body satisfies the rule, 1 when any does not, 2 on unreadable input.
`feedback-to-issues` runs it on every drafted body before `gh issue create`, so an
unsubstantiated absence claim never becomes the input to implementation.

WHY THE RULE CANNOT BE LEFT TO ATTENTION (the parent's INV-213, INV-194). The tools you
asked and found empty are true statements about *those tools* and no evidence for the
negative. "`sdk_guide(topic='configure')` returns no license variable" is correct, and
worthless as support for "no license variable exists", because the variable lives in
`sdk_guide(topic='load', record_count=<above the limit>)`. An issue is the input to
implementation, so an absence concluded from the wrong route is believed and then built.

WHAT IS IN SCOPE. A body drafted from feedback, identified by its `Feedback:` line in the
source block, which `feedback-to-issues` Step 5 writes. A body without one makes no claim
about re-verifying feedback and is not held to this rule.

This gate moved here from the retired `feedback-to-specs` skill (#25), where it scanned the
spec archive. Issues are not files in this repository, so the rule now runs on the drafted
body instead of on a committed tree. Standard library only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: The line a feedback-derived body carries in its source block.
SOURCE_FEEDBACK_LINE = re.compile(r"^\s*[-*]\s*\*\*?Feedback:?\*\*?|^\s*[-*]\s*Feedback:", re.M)

#: The `MCP re-check` line, whose content this gate reads.
_MCP_RECHECK_LINE = re.compile(r"^\s*[-*]\s*(?:\*\*)?MCP re-check(?:\*\*)?:\s*(?P<body>.*)$", re.M)

#: The clause that substantiates an absence: the route that would CARRY the fact, and what
#: it returned. Matched case-insensitively so `Owner-checked:` also counts.
_OWNER_CHECKED = re.compile(r"owner-checked\s*:", re.I)

#: Wordings that assert the server does not have something. A list of phrases rather than
#: a general negation detector: a false positive blocks a correct issue, and every phrase
#: below is one this rule was written against.
ABSENCE_PHRASES = (
    "does not cover",
    "doesn't cover",
    "does not carry",
    "does not document",
    "does not expose",
    "returns no",
    "returned no",
    "no mcp tool",
    "nothing surfaced",
    "not covered by",
    "no such flag",
    "no such field",
    "no such topic",
    "server lacks",
    "lacks it",
    "absent from the server",
)

#: The declaration that exempts a body: with no Senzing fact there is no absence claim.
_NO_SENZING_FACT = re.compile(r"n/?a\s*\(no senzing fact\)", re.I)


def in_scope(text: str) -> bool:
    """Whether `text` is a feedback-derived body, and so held to the rule."""
    return SOURCE_FEEDBACK_LINE.search(text) is not None


def absence_claim_phrases(recheck_body: str) -> list[str]:
    """The absence phrases `recheck_body` uses, in the order listed. Pure."""
    lowered = recheck_body.lower()
    return [phrase for phrase in ABSENCE_PHRASES if phrase in lowered]


def violation(text: str) -> str | None:
    """Why `text` breaks the rule, or None when it satisfies it. Pure.

    * no `MCP re-check` line → a violation of its own: a feedback-derived issue states what
      the live server said, even if only that it said nothing relevant;
    * the line declares `n/a (no Senzing fact)` → exempt;
    * an absence claim with `owner-checked:` → satisfied;
    * an absence claim without it → the violation this gate exists for.
    """
    match = _MCP_RECHECK_LINE.search(text)
    if match is None:
        return "carries no 'MCP re-check' line in its source block"
    body = match.group("body")
    # The line may wrap; read continuations through to the next list item or blank line.
    # `[1:]` is load-bearing: `$` under MULTILINE ends before the newline, so the first
    # split element is always empty and would otherwise read as "the item ended here".
    for line in text[match.end():].split("\n")[1:]:
        stripped = line.strip()
        if not stripped or re.match(r"[-*]\s", stripped) or stripped.startswith("#"):
            break
        body += " " + stripped
    if _NO_SENZING_FACT.search(body):
        return None
    phrases = absence_claim_phrases(body)
    if not phrases or _OWNER_CHECKED.search(body):
        return None
    return (
        f"asserts the server lacks something ({phrases!r}) without an 'owner-checked:' "
        "clause naming the route that would carry the fact"
    )


def main(argv: list[str] | None = None) -> int:
    paths = list(sys.argv[1:] if argv is None else argv)
    if not paths:
        print("usage: issue_body_check.py <issue-body.md> [...]", file=sys.stderr)
        return 2
    failed = 0
    for name in paths:
        try:
            text = Path(name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"{name}: unreadable: {error}", file=sys.stderr)
            return 2
        if not in_scope(text):
            print(f"{name}: out of scope (no Feedback: line); not checked")
            continue
        reason = violation(text)
        if reason is None:
            print(f"{name}: ok")
            continue
        failed += 1
        print(f"{name}: {reason}", file=sys.stderr)
    if failed:
        print(
            "Name the route that would CARRY the fact and what it returned, on the "
            "'MCP re-check' line, e.g.\n  owner-checked: sdk_guide(topic='load', "
            "record_count=<above the limit>) — returns it",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
