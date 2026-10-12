"""#28 (R7): an escalated issue closes only when the fix is in the PINNED parent release.

The decision is pure (`classify`), with the one network question — "is this commit an
ancestor of that tag?" — injected, so every path is exercised offline. The paths that
must NOT close are the ones tested hardest: closing is the only irreversible action.
"""

from __future__ import annotations

import pytest

import escalations as e

PARENT = f"{e.PARENT_REPOSITORY}#112"
FIX = "a169bec72a359313498a711eb6793ae66cccdb24"
OTHER = "11821deea0259c696dd885ab3959190599dc8e9d"


def _contains(table: dict[tuple[str, str], bool]):
    return lambda commit, tag: table.get((commit, tag), False)


def _verdict(state, *, pinned="0.6.1", target=None, table=None, parent=PARENT):
    return e.classify(28, "t", parent, state, pinned=pinned, target=target,
                      contains=_contains(table or {}))


def test_closes_when_the_pinned_release_contains_the_fix():
    v = _verdict(e.ParentState("closed", "completed", (FIX,)), table={(FIX, "0.6.1"): True})
    assert v.verdict == e.ARRIVED and v.tag == "0.6.1"
    assert "0.6.1" in e.close_comment(v), "the closing comment names the tag"


def test_a_closed_parent_issue_alone_closes_nothing():
    """R2: closed in the parent but in no release this port reads."""
    v = _verdict(e.ParentState("closed", "completed", (FIX,)))
    assert v.verdict == e.PENDING_RELEASE


def test_a_fix_only_in_the_target_tag_waits_for_the_update_to_land():
    v = _verdict(e.ParentState("closed", "completed", (FIX,)), pinned="0.5.3", target="0.6.1",
                 table={(FIX, "0.6.1"): True})
    assert v.verdict == e.IN_TARGET and v.tag == "0.6.1"


def test_every_fix_commit_must_be_contained():
    state = e.ParentState("closed", "completed", (FIX, OTHER))
    assert _verdict(state, table={(FIX, "0.6.1"): True}).verdict == e.PENDING_RELEASE
    assert _verdict(state, table={(FIX, "0.6.1"): True, (OTHER, "0.6.1"): True}).verdict == e.ARRIVED


def test_an_open_parent_issue_is_pending():
    assert _verdict(e.ParentState("open", None)).verdict == e.PENDING


@pytest.mark.parametrize("reason", ["not_planned", "duplicate"])
def test_a_declined_parent_issue_surfaces_and_never_closes(reason):
    v = _verdict(e.ParentState("closed", reason, (FIX,)), table={(FIX, "0.6.1"): True})
    assert v.verdict == e.DECLINED, "even a contained commit must not close a declined escalation"
    assert "human" in v.reason


def test_completed_without_a_fix_commit_is_undetermined_not_closed():
    assert _verdict(e.ParentState("closed", "completed", ())).verdict == e.UNDETERMINED


def test_a_missing_marker_is_undetermined():
    assert _verdict(None, parent=None).verdict == e.UNDETERMINED


def test_every_verdict_is_one_of_the_declared_set():
    states = [None, e.ParentState("open", None), e.ParentState("closed", "not_planned"),
              e.ParentState("closed", "completed", ()), e.ParentState("closed", "completed", (FIX,))]
    for state in states:
        assert _verdict(state).verdict in e.VERDICTS


def test_the_marker_survives_reflow_and_names_the_parent():
    body = e.mark_comment(PARENT)
    match = e.MARKER.search(body.replace("\n", " "))
    assert match and f"{match.group('repo')}#{match.group('num')}" == PARENT


def test_the_mechanism_is_a_label():
    assert e.LABEL_AWAITING in e.LABELS and e.LABEL_DECISION in e.LABELS


@pytest.mark.parametrize("bad", ["main", "HEAD", "v0.6.1"])
def test_check_refuses_a_non_tag(bad, capsys):
    assert e.main(["check", "--pinned", bad]) == 2
    assert e.main(["check", "--pinned", "0.6.1", "--target", bad]) == 2
