#!/usr/bin/env python3
"""A generated spec that claims the Senzing MCP server LACKS something must name the
route that would carry the fact.

WHY THIS TEST EXISTS, and why the rule cannot be left to attention. The tools you asked
and found empty are true statements about *those tools* and no evidence for the negative.
"`sdk_guide(topic='configure')` returns no license variable" is correct, and worthless as
support for "no license variable exists", because the variable lives in
`sdk_guide(topic='load', record_count=<above the limit>)`. In the sibling Claude plugin
repository that reasoning error became an invariant plus a guard enforcing it, with the
offline suite certifying both — and the second instance of it in a single session was
caught only because the author had made the first one hours earlier and went looking.

A spec is the **input** to implementation, so an absence concluded from the wrong route is
worse there than in shipped prose: it is believed and then built. Hence a mechanical gate.

WHAT IS IN SCOPE. Only specs `/feedback-to-specs` generated — identified by their own
`## Source` block carrying a `Feedback:` line, which is the marker the skill writes and
nothing else in `.kiro/specs/` has. Hand-authored specs are not held to a rule about
re-verifying feedback they never came from, and a discriminator read from the document
itself cannot drift out of step with a list kept somewhere else.

RUN: `python3 -m pytest --no-header -q` from the repository root. This directory is on
`testpaths` in `pyproject.toml`, so the gate runs with the rest of the suite — a gate
nothing runs is not a gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

#: Repository root: this file sits at `.kiro/skills/feedback-to-specs/tests/`.
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]

SPECS_ROOT = REPOSITORY_ROOT / ".kiro" / "specs"

#: The line a generated spec carries in its `## Source` block. Its presence is what puts a
#: document in scope; `Feedback:` is written by Step 7 and by nothing else.
_SOURCE_FEEDBACK_LINE = re.compile(r"^\s*[-*]\s*\*\*?Feedback:?\*\*?|^\s*[-*]\s*Feedback:", re.M)

#: The `MCP re-check` line, whose content this gate reads.
_MCP_RECHECK_LINE = re.compile(r"^\s*[-*]\s*(?:\*\*)?MCP re-check(?:\*\*)?:\s*(?P<body>.*)$", re.M)

#: The clause that substantiates an absence: the route that would CARRY the fact, and what
#: it returned. Matched case-insensitively so `Owner-checked:` also counts.
_OWNER_CHECKED = re.compile(r"owner-checked\s*:", re.I)

#: Wordings that assert the server does not have something. Deliberately a list of
#: *phrases* rather than a general negation detector: a false positive here blocks a
#: correct spec, and every phrase below is one this rule was actually written against.
_ABSENCE_PHRASES = (
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

#: The declaration that exempts a spec: with no Senzing fact there is no absence claim
#: about the server to substantiate.
_NO_SENZING_FACT = re.compile(r"n/?a\s*\(no senzing fact\)", re.I)


def generated_spec_documents() -> list[Path]:
    """Every `/feedback-to-specs`-generated spec document, sorted.

    A spec directory holds `bugfix.md` or `requirements.md`; both carry the `## Source`
    block, so both are read. `design.md` and `tasks.md` do not carry it and are skipped by
    the same discriminator rather than by a filename rule.
    """
    if not SPECS_ROOT.is_dir():
        return []
    return sorted(
        path
        for path in SPECS_ROOT.glob("*/*.md")
        if _SOURCE_FEEDBACK_LINE.search(path.read_text(encoding="utf-8", errors="replace"))
    )


def absence_claim_phrases(recheck_body: str) -> list[str]:
    """The absence phrases `recheck_body` uses, in the order listed. Pure."""
    lowered = recheck_body.lower()
    return [phrase for phrase in _ABSENCE_PHRASES if phrase in lowered]


def violation(text: str) -> str | None:
    """Why `text` breaks the rule, or None when it satisfies it. Pure.

    Four outcomes, and the order matters:

    * no `MCP re-check` line at all → a violation of its own. A generated spec must state
      what the live server said, even if only to record that it said nothing relevant.
    * the line declares `n/a (no Senzing fact)` → exempt, whatever else it says.
    * the line asserts an absence and carries `owner-checked:` → satisfied.
    * the line asserts an absence and does not → the violation this gate exists for.
    """
    match = _MCP_RECHECK_LINE.search(text)
    if match is None:
        return "carries no 'MCP re-check' line in its ## Source block"
    body = match.group("body")
    # The line may wrap; take it through to the next list item or blank line.
    #
    # `[1:]` is load-bearing. `$` under `re.MULTILINE` ends the match immediately BEFORE
    # the newline, so `tail` always opens with that newline and the first element of the
    # split is the empty string — which the blank-line test below would read as "the item
    # ended here", discarding every continuation line. That produced a false positive on a
    # wrapped `owner-checked:` clause, which is the expensive direction: it blocks a spec
    # that satisfies the rule.
    tail = text[match.end() :]
    for line in tail.split("\n")[1:]:
        stripped = line.strip()
        if not stripped or re.match(r"[-*]\s", stripped) or stripped.startswith("#"):
            break
        body += " " + stripped
    if _NO_SENZING_FACT.search(body):
        return None
    phrases = absence_claim_phrases(body)
    if not phrases:
        return None
    if _OWNER_CHECKED.search(body):
        return None
    return (
        f"asserts the server lacks something ({phrases!r}) without an 'owner-checked:' "
        "clause naming the route that would carry the fact"
    )


# ===========================================================================
# The gate, over the real tree
# ===========================================================================
def test_every_generated_spec_substantiates_its_absence_claims() -> None:
    """No generated spec concludes an absence from a route that does not own the fact."""
    offenders = {
        str(path.relative_to(REPOSITORY_ROOT)): reason
        for path in generated_spec_documents()
        if (reason := violation(path.read_text(encoding="utf-8"))) is not None
    }
    assert offenders == {}, (
        "generated spec(s) break the owner-checked rule:\n"
        + "\n".join(f"  {path}: {reason}" for path, reason in sorted(offenders.items()))
        + "\n\nThe tools you asked and found empty are true statements about THOSE tools "
        "and no evidence for the negative. Name the route that would CARRY the fact and "
        "what it returned, on the 'MCP re-check' line:\n"
        "  owner-checked: sdk_guide(topic='load', record_count=<above the limit>) — returns it\n"
        "See .kiro/skills/feedback-to-specs/spec-template.md."
    )


def test_the_gate_has_something_to_say_about_the_tree_it_scans() -> None:
    """The scan is wired to the real specs directory, whether or not any spec is in scope.

    A vacuous pass is legitimate — before the first triage run there are no generated
    specs — but a vacuous pass caused by a wrong path is not, and the two are
    indistinguishable from the result alone. So the path is asserted, not the count.
    """
    assert SPECS_ROOT.is_dir(), f"{SPECS_ROOT} does not exist; the gate is scanning nothing"
    assert (SPECS_ROOT / "senzing-bootcamp-power").is_dir(), (
        "the repository's own spec is missing, so SPECS_ROOT is resolving somewhere "
        f"unexpected: {SPECS_ROOT}"
    )


def test_hand_authored_specs_are_out_of_scope() -> None:
    """This repository's own spec is not held to a rule about feedback it never came from."""
    own = SPECS_ROOT / "senzing-bootcamp-power" / "requirements.md"
    assert own.is_file()
    assert own not in generated_spec_documents()


# ===========================================================================
# Negative tests: the gate is confirmed to FAIL on an injected regression
# ===========================================================================
#
# Every check in this file is negative-tested, because "passes on a clean tree" says
# nothing about whether it would catch the thing it was written for.

_SOURCE = """# Title

## Source

- Feedback: `docs/feedback/SENZING_BOOTCAMP_POWER_FEEDBACK_1.md` → "An entry" (2026-08-01)
- Entry id: `0123456789abcdef`
- MCP re-check: {recheck}
"""


@pytest.mark.parametrize(
    "recheck",
    [
        "server 1.32.2, 2026-08-30 — `sdk_guide(topic='configure')` returns no license variable",
        "server 1.32.2 — the server does not cover the response shape",
        "2026-08-30 — no MCP tool answers this",
        "server 1.32.2 — nothing surfaced for these flags",
    ],
)
def test_an_unsubstantiated_absence_claim_is_caught(recheck: str) -> None:
    """An absence claim with no `owner-checked:` clause must be reported."""
    reason = violation(_SOURCE.format(recheck=recheck))
    assert reason is not None, f"the gate missed an unsubstantiated absence: {recheck!r}"
    assert "owner-checked" in reason


@pytest.mark.parametrize(
    "recheck",
    [
        "server 1.32.2, 2026-08-30 — `sdk_guide(topic='configure')` returns no license "
        "variable; owner-checked: `sdk_guide(topic='load', record_count=600000)` — returns it",
        "server 1.32.2 — the server does not cover it. Owner-checked: "
        "`get_sdk_reference(topic='response_schemas', filter='get_entity')` — documents it",
        "n/a (no Senzing fact)",
        "server 1.32.2, 2026-08-30 — still reproduces",
        "unverified (MCP unreachable at triage time)",
    ],
)
def test_a_substantiated_or_exempt_recheck_passes(recheck: str) -> None:
    """The gate does not fire on a line that satisfies the rule or declares no Senzing fact."""
    assert violation(_SOURCE.format(recheck=recheck)) is None, recheck


def test_a_missing_mcp_recheck_line_is_caught() -> None:
    """A generated spec that never says what the server returned is itself a violation."""
    text = "# Title\n\n## Source\n\n- Feedback: `x.md` → \"An entry\" (2026-08-01)\n"
    reason = violation(text)
    assert reason is not None and "MCP re-check" in reason


def test_the_absence_claim_wrapped_onto_a_continuation_line_is_still_read() -> None:
    """A wrapped `MCP re-check` line cannot hide the clause, or its absence.

    The template's line is long and hard-wraps in practice, so reading only the first
    physical line would let a wrapped `owner-checked:` read as missing (a false positive)
    and a wrapped absence claim read as absent (a false negative). Both directions are
    asserted.
    """
    wrapped_ok = _SOURCE.format(
        recheck="server 1.32.2 — returns no license variable;\n  owner-checked: "
        "`sdk_guide(topic='load', record_count=600000)` — returns it"
    )
    assert violation(wrapped_ok) is None, "a wrapped owner-checked clause was not seen"

    wrapped_bad = _SOURCE.format(
        recheck="server 1.32.2 —\n  the server does not cover the response shape"
    )
    reason = violation(wrapped_bad)
    assert reason is not None, "a wrapped absence claim was not seen"
    assert "owner-checked" in reason


def test_the_scope_discriminator_is_the_feedback_line() -> None:
    """A document with no `Feedback:` line is out of scope even inside `.kiro/specs/`."""
    assert _SOURCE_FEEDBACK_LINE.search(_SOURCE.format(recheck="still reproduces"))
    assert not _SOURCE_FEEDBACK_LINE.search(
        "# Design Document\n\n## Overview\n\nNo source block here.\n"
    )
