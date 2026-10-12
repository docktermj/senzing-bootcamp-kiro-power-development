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
5. Supersession is written in the family's one syntax (FAMILY_WORKFLOW R12, #27):
   a `- **Superseded by:** KINV-NNN — <why>` bullet on the superseded entry and a
   `- **Supersedes:** KINV-NNN` bullet on its successor, both required, each naming
   an identifier that exists. `- **Partly superseded by:** KINV-NNN — <what was
   replaced, what still stands>` records a replaced clause and leaves the entry
   active. Nothing else establishes supersession: any other mention of it inside a
   definition, or a strikethrough, is a finding. Markers name `KINV` identifiers
   only — an inherited `INV-NNN` is the disposition register's subject, never a
   supersession recorded here.

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


#: The three supersession markers, each a bullet of its own (R12). Exact spelling,
#: zero-padded identifier, and for the two forward markers a reason after an em dash.
_MARKER_LINE = re.compile(
    r"^\s*- \*\*(?P<kind>Superseded by|Supersedes|Partly superseded by):\*\* "
    r"(?P<id>KINV-(?P<num>\d{3}))(?: — (?P<why>\S.*?))?\s*$"
)
#: A line that is trying to be a marker — a bullet opening with one of the labels —
#: whether or not it is spelled correctly.
_MARKER_ATTEMPT = re.compile(
    r"^\s*[-*]\s*\*{0,2}\s*(?:partly\s+)?supersed(?:ed[\s_-]*by|es)\b", re.IGNORECASE
)
#: Supersession written any other way: the word in prose, or a strikethrough.
_INFORMAL = re.compile(r"supersed|~~", re.IGNORECASE)

STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
SUPERSEDED_BY = "Superseded by"
SUPERSEDES = "Supersedes"
PARTLY_SUPERSEDED_BY = "Partly superseded by"


_FENCE = re.compile(r"(?ms)^\s*```.*?^\s*```[^\n]*$")


def prose(text: str) -> str:
    """`text` with fenced code blocks blanked, line count preserved.

    The ledger documents its own syntax with examples, and an example definition or
    marker inside a fence is not an entry. Every reader goes through this.
    """
    return _FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def definition_blocks(text: str) -> list[tuple[int, str]]:
    """Every `(number, raw block)` — the definition text with its line structure kept,
    so the marker bullets nested under it can be read one line at a time."""
    text = prose(text)
    starts = list(_DEFINITION_START.finditer(text))
    blocks: list[tuple[int, str]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.start():end]
        heading = block.find("\n## ")
        if heading != -1:
            block = block[:heading]
        blocks.append((int(match.group(1)), block))
    return blocks


def markers(text: str) -> dict[int, list[tuple[str, int, str | None]]]:
    """Per definition, its well-formed markers as `(kind, target number, reason)`."""
    found: dict[int, list[tuple[str, int, str | None]]] = {}
    for number, block in definition_blocks(text):
        for line in block.splitlines()[1:]:
            match = _MARKER_LINE.match(line)
            if match:
                found.setdefault(number, []).append(
                    (match.group("kind"), int(match.group("num")), match.group("why"))
                )
    return found


def statuses(text: str) -> dict[int, str]:
    """Each definition's status: `superseded` exactly when it carries `Superseded by:`.

    There is no third status (R12). `Partly superseded by:` leaves an entry active
    and binding in full; only the replaced clause has a successor.
    """
    marks = markers(text)
    return {
        number: (
            STATUS_SUPERSEDED
            if any(kind == SUPERSEDED_BY for kind, _, _ in marks.get(number, []))
            else STATUS_ACTIVE
        )
        for number, _ in definition_blocks(text)
    }


def supersession_findings(text: str) -> list[str]:
    """Supersession uses the one syntax, bidirectionally, between identifiers that exist."""
    findings: list[str] = []
    text = prose(text)
    blocks = definition_blocks(text)
    defined = {number for number, _ in blocks}
    marks: dict[int, list[tuple[str, int, str | None]]] = {}

    # Markers outside any definition belong to nothing.
    first = _DEFINITION_START.search(text)
    preamble_end = first.start() if first else len(text)
    for line in text[:preamble_end].splitlines():
        if _MARKER_LINE.match(line):
            findings.append(
                f"a supersession marker sits outside every KINV definition: {line.strip()!r}"
            )

    for number, block in blocks:
        name = f"KINV-{number:03d}"
        lines = block.splitlines()
        statement, rest = lines[0], lines[1:]
        if _INFORMAL.search(statement):
            findings.append(
                f"{name} states supersession in its prose; record it only as a "
                "'- **Superseded by:** KINV-NNN — <why>' / '- **Supersedes:** KINV-NNN' "
                "bullet pair (R12)"
            )
        for line in rest:
            match = _MARKER_LINE.match(line)
            if match is None:
                if _MARKER_ATTEMPT.match(line):
                    findings.append(
                        f"{name} carries a malformed supersession marker {line.strip()!r}; "
                        "the form is '- **Superseded by:** KINV-NNN — <why>', "
                        "'- **Supersedes:** KINV-NNN', or "
                        "'- **Partly superseded by:** KINV-NNN — <what was replaced>', with a "
                        "zero-padded KINV identifier — an inherited INV-NNN is the disposition "
                        "register's subject, never a supersession here"
                    )
                elif _INFORMAL.search(line):
                    findings.append(
                        f"{name} states supersession outside a marker bullet: {line.strip()!r} "
                        "(R12: nothing but the marker pair establishes supersession)"
                    )
                continue
            kind, target, why = match.group("kind"), int(match.group("num")), match.group("why")
            if kind in (SUPERSEDED_BY, PARTLY_SUPERSEDED_BY) and not why:
                findings.append(f"{name} '{kind}: KINV-{target:03d}' gives no reason after ' — '")
            if target == number:
                findings.append(f"{name} names itself in '{kind}:'")
            elif target not in defined:
                findings.append(
                    f"{name} '{kind}: KINV-{target:03d}' names an identifier that is not defined"
                )
            marks.setdefault(number, []).append((kind, target, why))

    for number, entries in marks.items():
        name = f"KINV-{number:03d}"
        kinds = [kind for kind, _, _ in entries]
        if kinds.count(SUPERSEDED_BY) > 1:
            findings.append(f"{name} carries more than one 'Superseded by:'; it has one successor")
        if SUPERSEDED_BY in kinds and PARTLY_SUPERSEDED_BY in kinds:
            findings.append(
                f"{name} is both superseded and partly superseded; there is no third status"
            )
        for kind, target, _ in entries:
            back = {(k, t) for k, t, _ in marks.get(target, [])}
            if kind == SUPERSEDED_BY and (SUPERSEDES, number) not in back and target in defined:
                findings.append(
                    f"{name} is 'Superseded by: KINV-{target:03d}', but KINV-{target:03d} carries "
                    f"no '- **Supersedes:** {name}' back-link; a one-directional record is "
                    "what produced six spellings in the parent"
                )
            if kind == SUPERSEDES and (SUPERSEDED_BY, number) not in back and target in defined:
                findings.append(
                    f"{name} 'Supersedes: KINV-{target:03d}', but KINV-{target:03d} carries no "
                    f"'- **Superseded by:** {name} — <why>' marker"
                )
    return findings


def definitions(text: str) -> list[tuple[int, str]]:
    """Every `(number, statement)` defined in the ledger, in document order.

    The statement is the whole block from one definition marker to the next
    definition or the next section heading, with interior whitespace collapsed,
    so a MUST/ALWAYS that falls on a wrapped continuation line is still seen.
    """
    text = prose(text)
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
    match = _INDEX_SECTION.search(prose(text))
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
    findings += supersession_findings(ledger_text)
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
    status = statuses(ledger_text)
    superseded = sum(1 for value in status.values() if value == STATUS_SUPERSEDED)
    print(
        f"KINV ledger: {len(definitions(ledger_text))} invariant(s) "
        f"({len(status) - superseded} active, {superseded} superseded), all checks passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
