#!/usr/bin/env python3
"""Shared helper for the bootcamp recap-durability hooks.

The in-progress module recap lives at ``docs/progress/recap_checkpoint.md`` (see the
module-completion skill), authored by the guide and refreshed at each step boundary.
This module folds that checkpoint into ``docs/bootcamp_recap.md`` so an interrupted
module (quit / compaction / new session) never loses its in-progress narrative.

The fold is deterministic, idempotent, and append-only with respect to completed
``## {module}`` sections: it only ever replaces the marker-fenced checkpoint block,
never a finalized section. Pure Python 3 stdlib, no third-party dependency (INV-052).

``ensure_checkpoint()`` owns **creating** the file, so the path exists without
depending on the guide remembering to write it. It only ever lays down a scaffold of
HTML comments — the accumulating narrative is authored by the guide, because no hook
can write prose. A scaffold is therefore deliberately **not** foldable: folding one
would append an empty block to the recap and trip the renderer's
"recap still contains a RECAP-CHECKPOINT block" warning at graduation.

Every status this module reports goes to **stderr**, never stdout: two of its callers
are hooks whose stdout is a structured channel (``UserPromptSubmit`` returns JSON), so
a status line on stdout would corrupt the payload.

This is NOT a hook itself. It is imported by the PreCompact, SessionEnd, SessionStart
and UserPromptSubmit hook scripts, which run in exec form (``python3 <hook>.py``);
Python puts each hook script's own directory (this ``scripts/`` directory) on
``sys.path``, so ``import recap_checkpoint`` resolves here on Linux, macOS, and
Windows alike.
"""
import json
import os
import re
import sys

CHECKPOINT = os.path.join("docs", "progress", "recap_checkpoint.md")
RECAP = os.path.join("docs", "bootcamp_recap.md")
PROGRESS = os.path.join("config", "bootcamp_progress.json")
START = "<!-- RECAP-CHECKPOINT:START -->"
END = "<!-- RECAP-CHECKPOINT:END -->"

# Marks a checkpoint that exists but has not been filled in yet. Its suffix is
# deliberately neither START nor END: the renderer and this module are held to an
# identical START/END constant pair by tests/test_recap_pdf_guard.py, and the
# scaffold is ours alone.
SCAFFOLD = "<!-- RECAP-CHECKPOINT:SCAFFOLD -->"

# Any HTML comment that is not one of our three markers — i.e. the scaffold's
# guidance text. Stripped before folding so it never reaches the recap or the PDF.
_GUIDANCE = re.compile(
    r"<!--(?!\s*RECAP-CHECKPOINT:(?:START|END|SCAFFOLD)\s*-->).*?-->", re.S
)


def bootcamp_active():
    """True during an active bootcamp — one whose progress file RECORDS A MODULE.

    ⛔ Existence of the file is not enough, and testing it was a real defect. The
    onboarding preface creates `config/bootcamp_progress.json` **empty** during its silent
    project setup, and nothing writes a `current_module` until Bootcamp preparation's final
    consolidated write. That window spans the whole preface plus all of Bootcamp
    preparation — the Core/Customized gate, module selection, verbosity and the
    programming-language gate — so on the next session the `SessionStart` hook announced
    "a bootcamp is in progress … offer to resume from the last recorded module" on a
    project with no recorded module, telling the guide to do something impossible where
    the correct behavior was to run onboarding from the top.

    An empty progress file is therefore the **normal** state for that window, not a
    corruption: this returns False and every caller stays silent, which is what a fresh
    start looks like.

    Never raises — `current_module()` absorbs a missing, empty, malformed or
    non-object file (INV-048), and a hook must not break on one.
    """
    return current_module() is not None


def _report(message):
    """Say what happened, on stderr. A silent no-op is the failure mode here
    (INV-111): the checkpoint went missing for ten modules with no signal."""
    sys.stderr.write("recap-checkpoint: %s\n" % message)


def current_module():
    """The module name recorded in the progress file, or None if unavailable.

    Never raises: a malformed or partly-written progress file must not break a
    hook (INV-048)."""
    try:
        with open(PROGRESS, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("current_module")
    return value if isinstance(value, str) and value.strip() else None


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _strip_block(text):
    """Remove every checkpoint block (START..END) from recap text so a re-fold
    replaces the prior checkpoint instead of duplicating it. Completed
    ``## {module}`` sections carry no markers and are never touched."""
    while True:
        i = text.find(START)
        if i == -1:
            return text
        j = text.find(END, i)
        if j == -1:
            # Unterminated marker: drop from START to end of text.
            return text[:i].rstrip() + "\n"
        j += len(END)
        text = (text[:i].rstrip() + "\n\n" + text[j:].lstrip("\n")).strip() + "\n"


def _scaffold_text(module=None):
    """The empty checkpoint: guidance only, no narrative. All HTML comments, so
    nothing here can survive a fold into the recap."""
    name = module or "the current module"
    return "\n".join(
        (
            SCAFFOLD,
            "<!-- In-progress recap for %s." % name,
            "",
            "     Refresh this at each step boundary (not per sub-step -- INV-012) with the",
            "     module's accumulating Information Shared / Questions & Responses /",
            "     Actions Taken / End-of-Module Summary-so-far. Write the narrative BETWEEN",
            "     the START and END markers below.",
            "",
            "     This is what survives a quit, compaction, or new session mid-module: the",
            "     PreCompact, SessionEnd and SessionStart hooks fold it into",
            "     docs/bootcamp_recap.md. While it holds only this scaffold there is nothing",
            "     to fold, and each of those hooks will say so on stderr.",
            "",
            "     Finalized and cleared on module completion -- see module-completion.md",
            "     step 2d. -->",
            "",
            START,
            END,
            "",
        )
    )


def checkpoint_state():
    """One of ``"missing"``, ``"scaffold"``, or ``"filled"``.

    ``"scaffold"`` covers both a freshly created checkpoint and one the guide has
    emptied at module close, because neither has a narrative to fold.
    """
    text = _read(CHECKPOINT)
    if text is None:
        return "missing"
    body = _GUIDANCE.sub("", text)
    for marker in (SCAFFOLD, START, END):
        body = body.replace(marker, "")
    return "filled" if body.strip() else "scaffold"


def ensure_checkpoint(module=None):
    """Create ``docs/progress/recap_checkpoint.md`` if it is absent. Returns True
    if this call created it.

    This is the deterministic half: the guide authors the narrative, but it is no
    longer also responsible for the file existing. Never raises — a hook must not
    fail a turn over a scratch file (INV-048).
    """
    if os.path.exists(CHECKPOINT):
        return False
    try:
        parent = os.path.dirname(CHECKPOINT)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(CHECKPOINT, "w", encoding="utf-8") as fh:
            fh.write(_scaffold_text(module or current_module()))
    except OSError as exc:
        _report("could not create %s (%s) — the in-progress recap will not "
                "survive a compaction until it exists" % (CHECKPOINT, exc))
        return False
    _report("created %s (empty scaffold; the guide fills it at each step boundary)"
            % CHECKPOINT)
    return True


def fold_checkpoint():
    """Fold ``docs/progress/recap_checkpoint.md`` into ``docs/bootcamp_recap.md``.

    Returns True if a non-empty checkpoint was folded, else False. Safe to call
    repeatedly: it removes any prior checkpoint block before appending the current
    one, so folds never duplicate, and it creates ``docs/`` (and a minimal recap) if
    they do not yet exist.

    Every outcome is reported on stderr, including both no-ops (INV-111). A missing
    checkpoint and an unfilled one are different failures — the first means nothing
    ever created it, the second means the guide never wrote to it — and neither used
    to be distinguishable from a successful fold.
    """
    state = checkpoint_state()
    if state == "missing":
        _report("nothing to fold: %s does not exist, so this module's in-progress "
                "narrative was never checkpointed" % CHECKPOINT)
        return False
    if state == "scaffold":
        _report("nothing to fold: %s holds only the empty scaffold, so no "
                "in-progress narrative was written this module" % CHECKPOINT)
        return False

    checkpoint = _GUIDANCE.sub("", _read(CHECKPOINT) or "").replace(SCAFFOLD, "")
    block = checkpoint.strip()
    # Guarantee the block is fenced so a later fold can find and replace it.
    if START not in block:
        block = START + "\n" + block
    if END not in block:
        block = block + "\n" + END

    recap = _read(RECAP) or ""
    recap = _strip_block(recap)

    if recap.strip():
        merged = recap.rstrip() + "\n\n" + block + "\n"
    else:
        merged = block + "\n"

    try:
        parent = os.path.dirname(RECAP)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(RECAP, "w", encoding="utf-8") as fh:
            fh.write(merged)
    except OSError as exc:
        _report("FAILED to fold %s into %s (%s) — the in-progress narrative is "
                "still in the checkpoint, not the recap" % (CHECKPOINT, RECAP, exc))
        return False
    _report("folded %s into %s (%d characters)" % (CHECKPOINT, RECAP, len(block)))
    return True
