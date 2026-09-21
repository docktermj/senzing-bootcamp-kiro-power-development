#!/usr/bin/env python3
"""Structural linter for the Kiro port invariants ledger (`specs/INVARIANTS.md`).

    python3 specs/check_invariants.py

This is the Kiro analogue of the ChatGPT sibling's `check_port.py` ledger checks,
and it enforces the maintenance rules stated in `specs/INVARIANTS.md` itself:

1. `KINV-NNN` definitions are unique, sequential from 001, and append-only — the
   nth definition is `KINV-<n>`, so a gap, a duplicate, or a renumber fails.
2. Every definition is phrased as a testable MUST/ALWAYS condition.
3. Every definition appears exactly once in the "Index by subject" section, and
   the index names no identifier that is not defined.
4. The porting workflow doc (`update-bootcamp-power`) requires review of the
   ledger by naming its path, so the dual-evaluation step cannot silently drop
   the `KINV` half.

The check functions are pure over text so the test suite can drive them with
synthetic fixtures (a linter that only ever sees a valid ledger is a linter that
was never shown to catch anything). `main()` wires them to the committed files
and exits non-zero on any finding.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = "specs/INVARIANTS.md"
#: The porting workflow that owns the dual-evaluation review (must name the ledger).
WORKFLOW_DOC_PATH = "powers/senzing-bootcamp-maintainer/skills/update-bootcamp-power/SKILL.md"

#: The start of a ledger definition: `- **KINV-001** — `. The statement itself
#: runs from here to the next definition or the next level-2 heading, so a
#: definition that wraps across several lines is read whole rather than truncated
#: to its first physical line (which is how a `MUST` on line two would hide).
_DEFINITION_START = re.compile(r"(?m)^- \*\*KINV-(\d{3})\*\* — ")
#: An identifier reference anywhere (used to read the subject index).
_IDENTIFIER = re.compile(r"KINV-(\d{3})")
#: The "Index by subject" section: everything up to the next level-2 heading.
_INDEX_SECTION = re.compile(r"(?ms)^## Index by subject\n(.*?)(?=^## )")


def definitions(text: str) -> list[tuple[int, str]]:
    """Every `(number, statement)` defined in the ledger, in document order.

    The statement is the whole block from one definition marker to the next
    definition or the next section heading, with interior whitespace collapsed,
    so a MUST/ALWAYS that falls on a wrapped continuation line is still seen.
    """
    starts = list(_DEFINITION_START.finditer(text))
    result: list[tuple[int, str]] = []
    for index, match in enumerate(starts):
        begin = match.end()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[begin:end]
        heading = block.find("\n## ")
        if heading != -1:
            block = block[:heading]
        statement = " ".join(block.split())
        result.append((int(match.group(1)), statement))
    return result


def sequential_findings(defs: list[tuple[int, str]]) -> list[str]:
    """`KINV` ids must be unique, sequential from 1, and append-only."""
    ids = [number for number, _ in defs]
    if not ids:
        return ["no KINV-NNN definitions found; the ledger defines nothing to enforce"]
    expected = list(range(1, len(ids) + 1))
    if ids != expected:
        return [
            "KINV definitions must be unique, sequential from 001, and append-only; "
            f"found {ids}, expected {expected}"
        ]
    return []


def phrasing_findings(defs: list[tuple[int, str]]) -> list[str]:
    """Every definition is a testable MUST/ALWAYS condition."""
    findings: list[str] = []
    for number, statement in defs:
        padded = f" {statement} "
        if " MUST " not in padded and " ALWAYS " not in padded:
            findings.append(
                f"KINV-{number:03d} is not phrased as a testable MUST/ALWAYS condition"
            )
    return findings


def index_findings(text: str, defs: list[tuple[int, str]]) -> list[str]:
    """Every definition appears exactly once in the index; the index invents none."""
    match = _INDEX_SECTION.search(text)
    if match is None:
        return ["no '## Index by subject' section found"]
    indexed = [int(number) for number in _IDENTIFIER.findall(match.group(1))]
    defined = sorted(number for number, _ in defs)
    findings: list[str] = []
    duplicates = sorted({n for n in indexed if indexed.count(n) > 1})
    if duplicates:
        findings.append(
            "these KINV ids appear more than once in the subject index: "
            + ", ".join(f"KINV-{n:03d}" for n in duplicates)
        )
    missing = sorted(set(defined) - set(indexed))
    if missing:
        findings.append(
            "these KINV definitions are not in the subject index: "
            + ", ".join(f"KINV-{n:03d}" for n in missing)
        )
    unknown = sorted(set(indexed) - set(defined))
    if unknown:
        findings.append(
            "the subject index names KINV ids that are not defined: "
            + ", ".join(f"KINV-{n:03d}" for n in unknown)
        )
    return findings


def workflow_findings(workflow_text: str) -> list[str]:
    """The porting workflow doc must require review of the ledger by naming it."""
    if LEDGER_PATH not in workflow_text:
        return [
            f"{WORKFLOW_DOC_PATH} does not name {LEDGER_PATH}, so the dual-evaluation "
            "review does not require the KINV ledger to be checked"
        ]
    return []


def run(ledger_text: str, workflow_text: str) -> list[str]:
    """Every finding, over the ledger text and the workflow doc text."""
    defs = definitions(ledger_text)
    findings: list[str] = []
    findings += sequential_findings(defs)
    findings += phrasing_findings(defs)
    findings += index_findings(ledger_text, defs)
    findings += workflow_findings(workflow_text)
    return findings


def main() -> int:
    ledger = REPO_ROOT / LEDGER_PATH
    workflow = REPO_ROOT / WORKFLOW_DOC_PATH
    findings: list[str] = []
    if not ledger.is_file():
        findings.append(f"missing Kiro invariants ledger: {LEDGER_PATH}")
        ledger_text = ""
    else:
        ledger_text = ledger.read_text(encoding="utf-8")
    workflow_text = workflow.read_text(encoding="utf-8") if workflow.is_file() else ""
    if not workflow_text:
        findings.append(f"missing porting workflow doc: {WORKFLOW_DOC_PATH}")
    findings += run(ledger_text, workflow_text)
    for finding in findings:
        print(f"KINV ledger: {finding}", file=sys.stderr)
    if findings:
        print(f"{len(findings)} finding(s); the ledger is not release-clean", file=sys.stderr)
        return 1
    print(f"KINV ledger: {len(definitions(ledger_text))} invariant(s), all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
