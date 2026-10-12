"""The Kiro invariants ledger is structurally sound, and its linter can fail.

Two halves. The first runs the linter against the committed ledger and porting
workflow and asserts it is release-clean. The second is the anti-vacuity half:
each synthetic fixture introduces exactly one defect and asserts the linter
reports it, so a linter that silently stopped checking would fail this test
rather than pass the first one for the wrong reason.
"""

from __future__ import annotations

import pytest

import check_invariants as ci


# --- The committed ledger is release-clean ---------------------------------


def _ledger_text() -> str:
    return (ci.REPO_ROOT / ci.LEDGER_PATH).read_text(encoding="utf-8")


def _workflow_text() -> str:
    return (ci.REPO_ROOT / ci.WORKFLOW_DOC_PATH).read_text(encoding="utf-8")


def test_committed_ledger_passes_every_check():
    assert ci.run(_ledger_text(), _workflow_text()) == []


def test_main_reports_clean_on_the_repository():
    assert ci.main() == 0


def test_ledger_actually_defines_invariants():
    # Anti-vacuity: the clean run above must be over a non-empty ledger, or it
    # is passing because there is nothing to check.
    assert len(ci.definitions(_ledger_text())) >= 1


# --- The linter catches each defect (anti-vacuity) -------------------------

_VALID = """## Index by subject

- **Group:** KINV-001, KINV-002

## Group

- **KINV-001** — The first thing MUST hold.
- **KINV-002** — The second thing MUST hold.
"""

_WORKFLOW = f"...the {ci.LEDGER_PATH} ledger is reviewed here...".format()


def test_valid_fixture_is_clean():
    assert ci.run(_VALID, _WORKFLOW) == []


def test_non_sequential_ids_fail():
    broken = _VALID.replace("**KINV-002**", "**KINV-003**").replace(
        "KINV-001, KINV-002", "KINV-001, KINV-003"
    )
    findings = ci.run(broken, _WORKFLOW)
    assert any("sequential" in f for f in findings)


def test_missing_must_phrasing_fails():
    broken = _VALID.replace(
        "The second thing MUST hold.", "The second thing is nice to have."
    )
    findings = ci.run(broken, _WORKFLOW)
    assert any("MUST/ALWAYS" in f for f in findings)


def test_unindexed_definition_fails():
    broken = _VALID.replace("- **Group:** KINV-001, KINV-002", "- **Group:** KINV-001")
    findings = ci.run(broken, _WORKFLOW)
    assert any("not in the subject index" in f for f in findings)


def test_index_naming_an_undefined_id_fails():
    broken = _VALID.replace(
        "- **Group:** KINV-001, KINV-002", "- **Group:** KINV-001, KINV-002, KINV-009"
    )
    findings = ci.run(broken, _WORKFLOW)
    assert any("not defined" in f for f in findings)


def test_workflow_without_ledger_reference_fails():
    findings = ci.run(_VALID, "a workflow doc that never names the ledger")
    assert any("dual-evaluation" in f for f in findings)


# --- Supersession uses the one syntax, bidirectionally (R12, #27) ----------

_PAIR = """## Index by subject

- **Group:** KINV-001, KINV-002

## Group

- **KINV-001** — The first thing MUST hold.
  - **Superseded by:** KINV-002 — the check moved to the installer
- **KINV-002** — The replacement MUST hold.
  - **Supersedes:** KINV-001
"""


def _supersession(text: str) -> list[str]:
    return ci.supersession_findings(text)


def test_a_well_formed_bidirectional_pair_is_clean():
    assert ci.run(_PAIR, _WORKFLOW) == []
    assert ci.statuses(_PAIR) == {1: ci.STATUS_SUPERSEDED, 2: ci.STATUS_ACTIVE}


def test_the_committed_ledger_has_only_the_two_statuses():
    assert set(ci.statuses(_ledger_text()).values()) <= {ci.STATUS_ACTIVE, ci.STATUS_SUPERSEDED}


def test_a_forward_marker_without_its_back_link_fails():
    broken = _PAIR.replace("  - **Supersedes:** KINV-001\n", "")
    assert any("no '- **Supersedes:** KINV-001' back-link" in f for f in _supersession(broken))


def test_a_back_link_without_its_forward_marker_fails():
    broken = _PAIR.replace("  - **Superseded by:** KINV-002 — the check moved to the installer\n", "")
    assert any("carries no '- **Superseded by:** KINV-002" in f for f in _supersession(broken))


def test_a_marker_naming_an_undefined_identifier_fails():
    broken = _PAIR.replace("**Supersedes:** KINV-001", "**Supersedes:** KINV-009")
    assert any("KINV-009' names an identifier that is not defined" in f for f in _supersession(broken))
    broken = _PAIR.replace("**Superseded by:** KINV-002", "**Superseded by:** KINV-007")
    assert any("KINV-007' names an identifier that is not defined" in f for f in _supersession(broken))


@pytest.mark.parametrize(
    "bad",
    [
        "  - Superseded by: KINV-002 — no bold",
        "  - **Superseded by:** KINV-2 — not zero-padded",
        "  - **Superseded By:** KINV-002 — wrong case",
        "  - **Superseded by:** INV-052 — an inherited invariant",
        "  - **Superseded-by:** KINV-002 — hyphenated",
    ],
)
def test_a_malformed_marker_fails(bad: str):
    broken = _PAIR.replace("  - **Superseded by:** KINV-002 — the check moved to the installer", bad)
    assert any("malformed supersession marker" in f for f in _supersession(broken)), bad


@pytest.mark.parametrize(
    "prose",
    [
        "- **KINV-001** — The first thing MUST hold. Superseded by KINV-002.",
        "- **KINV-001** — ~~The first thing MUST hold.~~",
    ],
)
def test_supersession_written_any_other_way_fails(prose: str):
    broken = _PAIR.replace("- **KINV-001** — The first thing MUST hold.", prose)
    assert any("prose" in f for f in _supersession(broken)), prose


def test_supersession_on_a_continuation_line_fails():
    broken = _PAIR.replace(
        "- **KINV-001** — The first thing MUST hold.\n",
        "- **KINV-001** — The first thing MUST hold, until it was\n  superseded in the 0.7 release.\n",
    )
    assert any("outside a marker bullet" in f for f in _supersession(broken))


def test_a_marker_without_a_reason_fails():
    broken = _PAIR.replace(" — the check moved to the installer", "")
    assert any("gives no reason" in f for f in _supersession(broken))


def test_self_supersession_fails():
    broken = _PAIR.replace("**Superseded by:** KINV-002", "**Superseded by:** KINV-001")
    assert any("names itself" in f for f in _supersession(broken))


def test_partial_supersession_keeps_the_entry_active_and_needs_no_back_link():
    partial = _PAIR.replace(
        "  - **Superseded by:** KINV-002 — the check moved to the installer",
        "  - **Partly superseded by:** KINV-002 — the Windows clause; Linux and macOS still stand",
    ).replace("  - **Supersedes:** KINV-001\n", "")
    assert _supersession(partial) == []
    assert ci.statuses(partial)[1] == ci.STATUS_ACTIVE


def test_superseded_and_partly_superseded_together_fails():
    both = _PAIR.replace(
        "  - **Superseded by:** KINV-002 — the check moved to the installer\n",
        "  - **Superseded by:** KINV-002 — the check moved to the installer\n"
        "  - **Partly superseded by:** KINV-002 — also this\n",
    )
    assert any("no third status" in f for f in _supersession(both))


def test_a_fenced_example_is_not_an_entry():
    documented = "# Ledger\n\n```markdown\n- **KINV-011** — <old>\n  - **Superseded by:** KINV-024 — x\n```\n\n" + _VALID
    assert ci.run(documented, _WORKFLOW) == []
    assert [n for n, _ in ci.definitions(documented)] == [1, 2]
