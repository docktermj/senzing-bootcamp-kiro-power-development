"""The Kiro invariants ledger is structurally sound, and its linter can fail.

Two halves. The first runs the linter against the committed ledger and porting
workflow and asserts it is release-clean. The second is the anti-vacuity half:
each synthetic fixture introduces exactly one defect and asserts the linter
reports it, so a linter that silently stopped checking would fail this test
rather than pass the first one for the wrong reason.
"""

from __future__ import annotations

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
