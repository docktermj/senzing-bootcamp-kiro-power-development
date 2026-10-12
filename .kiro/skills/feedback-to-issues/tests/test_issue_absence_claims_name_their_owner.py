"""The pre-filing gate holds the owner-checked rule, and fails on what it exists to catch.

Moved from the retired `feedback-to-specs` skill (#25) with the rule it tests: a
feedback-derived issue that claims the Senzing MCP server lacks something must name the
route that would carry the fact (the parent's INV-213). Every check is negative-tested,
because "passes on a clean body" says nothing about whether it would catch the defect.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parents[1] / "issue_body_check.py"
_spec = importlib.util.spec_from_file_location("issue_body_check", _MODULE)
check = importlib.util.module_from_spec(_spec)
sys.modules["issue_body_check"] = check
_spec.loader.exec_module(check)  # type: ignore[union-attr]

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
    reason = check.violation(_SOURCE.format(recheck=recheck))
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
    assert check.violation(_SOURCE.format(recheck=recheck)) is None, recheck


def test_a_missing_mcp_recheck_line_is_caught() -> None:
    text = "# Title\n\n## Source\n\n- Feedback: `x.md` → \"An entry\" (2026-08-01)\n"
    reason = check.violation(text)
    assert reason is not None and "MCP re-check" in reason


def test_the_absence_claim_wrapped_onto_a_continuation_line_is_still_read() -> None:
    """A wrapped line hides neither the clause nor its absence — both directions."""
    wrapped_ok = _SOURCE.format(
        recheck="server 1.32.2 — returns no license variable;\n  owner-checked: "
        "`sdk_guide(topic='load', record_count=600000)` — returns it"
    )
    assert check.violation(wrapped_ok) is None, "a wrapped owner-checked clause was not seen"
    wrapped_bad = _SOURCE.format(recheck="server 1.32.2 —\n  the server does not cover the response shape")
    reason = check.violation(wrapped_bad)
    assert reason is not None and "owner-checked" in reason


def test_the_scope_discriminator_is_the_feedback_line() -> None:
    assert check.in_scope(_SOURCE.format(recheck="still reproduces"))
    assert not check.in_scope("# A maintainer-authored issue\n\nNo source block here.\n")


def test_the_cli_exits_by_verdict(tmp_path: Path) -> None:
    good = tmp_path / "good.md"
    good.write_text(_SOURCE.format(recheck="n/a (no Senzing fact)"), encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text(_SOURCE.format(recheck="server 1.32.2 — returns no flag"), encoding="utf-8")
    other = tmp_path / "other.md"
    other.write_text("# no source block\n", encoding="utf-8")
    assert check.main([str(good), str(other)]) == 0
    assert check.main([str(good), str(bad)]) == 1
    assert check.main([str(tmp_path / "missing.md")]) == 2
