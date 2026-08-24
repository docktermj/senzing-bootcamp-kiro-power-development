#!/usr/bin/env python3
"""Test-record tooling — the record-based tagging gate (R6).

    testrecord.py emit  --version <semver> --out docs/test-records/<version>.md
                        [--checklist docs/test-checklist.md]
                        [--template-release <semver>] [--maintainer NAME]
                        [--date YYYY-MM-DD] [--validation-status STATUS]

    testrecord.py check --record docs/test-records/<version>.md
                        --version <semver> [--checklist docs/test-checklist.md]
                        [--report <path.json>]

JSON goes to stdout; human-readable narration goes to stderr, the same split the
rest of the engine uses, so the release procedure reads a record's verdict as
data rather than by scraping prose.

Two directions, one grammar
---------------------------
`emit` reads `docs/test-checklist.md` as the checklist **definition** and writes
a record skeleton for one version: the version under test, the resolved
Template_Release, the Maintainer, the date, the `ValidationReport` status, one
row per defined step, and one row per per-platform cell *(R6 AC2, AC6, AC12)*.
`check` reads a record back and computes the gate. The two are deliberately the
same module: the file `emit` writes is a file `check` parses, so a Maintainer
never fills in a shape the gate cannot read.

The gate *(R6 AC2, AC3, AC12)*
------------------------------
`tagAllowed` is true only when every defined step carries a recorded `pass` for
the **exact** version under test. Each of these yields false, and each is
reported as its own `E_CHECKLIST_INCOMPLETE` finding naming what is missing:

- a defined step with no row in the record at all (`missing-step`);
- a step whose outcome is blank or `_unrecorded_` (`blank-outcome`);
- a step whose outcome is an explicit `fail` (`fail`);
- a step whose outcome is neither `pass` nor `fail` — "not tested", "same as
  Linux", a note where an outcome belongs (`unrecognized-outcome`);
- one of the nine per-platform cells blank (`blank-platform-cell`) or absent
  (`missing-platform-cell`);
- a record naming a version other than the version under test
  (`version-mismatch`).

`tagAllowed` is **derived** from that finding list being empty, never assigned,
so no code path can hand out permission by omission. An unreadable or empty
record is therefore closed, not open.

Steps 2, 10, and 15 record three outcomes each — one per Supported_Platform —
and the nine cells are the record of truth for those three steps: the step's own
outcome is *derived* as a pass only when all three of its cells pass. Step 16 is
the checklist's human-facing restatement of that matrix check; the gate performs
it mechanically over the nine cells, so a step 16 recorded `pass` beside a blank
cell does not open the gate. Step 6's activation cells are part of the checklist
*definition* — they say what to try — so step 6 records one rolled-up outcome
and its cells get no record slots.

How the checklist definition is parsed
--------------------------------------
Exactly the grammar `docs/test-checklist.md` documents in its own "How this file
is parsed" section, which is a contract between that file and this one:

- one step per `## Step <N> — <title>` heading, `<N>` running 1..17 strictly
  increasing with no gaps and no repeats, and no other level-2 heading
  beginning with `Step`;
- each step block carries top-level list items opening with a bold label:
  `**Verifies:**`, optional `**Preconditions:**`, `**Do:**`, `**Pass:**`,
  `**Fail:**`, optional `**Activation cells:**` (step 6 only), optional
  `**Platform cells:**` (steps 2, 10, 15 only), `**Outcome:**`;
- a cell is identified by a backticked `` `<step>.<key>` ``, the platform keys
  being `linux`, `macos`, and `windows`;
- cell tables are nested under their field label and so are indented, so a
  table row is read with its leading whitespace stripped; a row's first column
  is the cell id and its last column is the recording slot;
- `_unrecorded_` marks an empty recording slot and counts as a fail.

How a record is parsed
----------------------
Header facts are `- **Label:** value` list items — `Version under test`,
`Template_Release`, `Maintainer`, `Date`, `ValidationReport status`. Outcomes
live in Markdown tables, read by *column name* rather than by position, so a
Maintainer may widen or reorder columns without breaking the gate. A table whose
header names `Step` records steps; a table whose header names `Cell` records
platform cells. Values are read with surrounding backticks stripped, and
`_unrecorded_` reads as blank. A step or cell appearing twice is an ambiguous
record and raises rather than resolving silently.

The checklist also offers a hand-copy route — copy `docs/test-checklist.md` and
fill it in — so a step's own `- **Outcome:**` slot inside a `## Step <N>` block is
read as that step's outcome too. A step recorded in a step table keeps the
table's row, so the two routes never contend for one step.

Round-tripping *(Property 23)*
------------------------------
`parse_record(render_record(...))` recovers the identical set of per-step
outcomes, including the shapes that block tagging: a step left out stays left
out, a blank outcome stays blank, and a per-platform cell stays keyed to its own
platform. That is what keeps the recorded per-step outcomes reviewable for the
tagged release *(R6 AC6)* rather than merely summarized by a verdict.

Nothing here reads the clock or the environment: a record renders from its
inputs alone, so two runs over the same inputs produce byte-identical Markdown.

Exit codes: 0 when tagging is allowed (`check`) or the record was written
(`emit`), 1 when tagging is blocked or an input document cannot be read, 2 on
CLI misuse (argparse).
"""

from __future__ import annotations

import argparse
import collections.abc
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    # The catalog code this module reports.
    "E_CHECKLIST_INCOMPLETE",
    # Record vocabulary.
    "OUTCOME_FAIL",
    "OUTCOME_PASS",
    "RECORD_FORMAT_VERSION",
    "UNRECORDED",
    # Facts from the requirements and the design.
    "CHECKLIST_STEP_COUNT",
    "DEFAULT_CHECKLIST",
    "MATRIX_STEP",
    "PER_PLATFORM_STEPS",
    "PLATFORM_LABELS",
    "RECORDS_DIRECTORY",
    "SUPPORTED_PLATFORMS",
    # Field labels of the checklist grammar.
    "FIELD_ACTIVATION_CELLS",
    "FIELD_DO",
    "FIELD_FAIL",
    "FIELD_OUTCOME",
    "FIELD_PASS",
    "FIELD_PLATFORM_CELLS",
    "FIELD_PRECONDITIONS",
    "FIELD_VERIFIES",
    "REQUIRED_FIELDS",
    # The checklist definition.
    "ChecklistCell",
    "ChecklistDefinition",
    "ChecklistError",
    "ChecklistStep",
    "default_definition",
    "parse_checklist",
    "read_checklist",
    # The record.
    "CellOutcome",
    "RecordError",
    "StepOutcome",
    "TestRecord",
    "parse_record",
    "read_record",
    "render_record",
    "write_record",
    # The gate, and the shapes of incompleteness it reports.
    "Finding",
    "REASON_BLANK_CELL",
    "REASON_BLANK_OUTCOME",
    "REASON_FAIL",
    "REASON_MISSING_CELL",
    "REASON_MISSING_STEP",
    "REASON_UNRECOGNIZED",
    "REASON_VERSION_MISMATCH",
    "TestRecordReport",
    "evaluate",
    "evaluate_outcomes",
    # CLI.
    "build_parser",
    "main",
]


# ---------------------------------------------------------------------------
# Facts from the requirements and the design
# ---------------------------------------------------------------------------

#: The one catalog code this module reports: a `Test_Checklist` step lacks a
#: recorded pass, so tagging is blocked *(R6 AC3)*.
E_CHECKLIST_INCOMPLETE = "E_CHECKLIST_INCOMPLETE"

#: `Test_Checklist` shape. Step numbers are stable across releases: a step is
#: never renumbered, a new step is appended, and `RECORD_FORMAT_VERSION` changes
#: with it. `docs/test-checklist.md` is the definition and this is the shape it
#: is required to have, so a checklist that grew a step fails to parse here
#: rather than silently producing a record with a hole in it.
CHECKLIST_STEP_COUNT = 17

#: The three steps performed on every Supported_Platform, each recording a
#: per-platform outcome *(R6 AC12)*: installation, hook firing, ported scripts.
PER_PLATFORM_STEPS = (2, 10, 15)

#: The Supported_Platforms, in the order their cells are written *(R16 AC1)*.
SUPPORTED_PLATFORMS = ("linux", "macos", "windows")

#: How each platform key is spelled for a human reader.
PLATFORM_LABELS: Mapping[str, str] = {
    "linux": "Linux",
    "macos": "macOS",
    "windows": "Windows",
}

#: The step that asserts the nine-cell matrix is complete *(R6 AC12)*. The gate
#: checks the cells themselves, so this step's own outcome grants nothing.
MATRIX_STEP = 16

#: Bumped whenever the record's shape changes — appending a checklist step
#: changes it, which is how a record says which checklist it was written for.
RECORD_FORMAT_VERSION = 1

#: The repository root, resolved from this file rather than the working
#: directory, so a path written into a record is repo-relative wherever the
#: tooling was invoked from.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: The checklist definition, resolved relative to this file so the tooling works
#: from any working directory.
DEFAULT_CHECKLIST = _REPOSITORY_ROOT / "docs" / "test-checklist.md"

#: Where records live, for the narration that tells a Maintainer where to look.
RECORDS_DIRECTORY = "docs/test-records"


# ---------------------------------------------------------------------------
# Record vocabulary
# ---------------------------------------------------------------------------

OUTCOME_PASS = "pass"
OUTCOME_FAIL = "fail"

#: An empty recording slot, spelled so a blank cannot be mistaken for an
#: oversight in review: an `_unrecorded_` outcome is a fail, not a blank.
UNRECORDED = "_unrecorded_"

EXIT_SUCCESS = 0
EXIT_BLOCKED = 1


# ---------------------------------------------------------------------------
# The checklist grammar
# ---------------------------------------------------------------------------

FIELD_VERIFIES = "Verifies"
FIELD_PRECONDITIONS = "Preconditions"
FIELD_DO = "Do"
FIELD_PASS = "Pass"
FIELD_FAIL = "Fail"
FIELD_ACTIVATION_CELLS = "Activation cells"
FIELD_PLATFORM_CELLS = "Platform cells"
FIELD_OUTCOME = "Outcome"

#: Fields every step block must carry. `Preconditions`, `Activation cells`, and
#: `Platform cells` are present only on the steps that need them.
REQUIRED_FIELDS = (FIELD_VERIFIES, FIELD_DO, FIELD_PASS, FIELD_FAIL, FIELD_OUTCOME)

#: `## Step <N> — <title>`. An en dash or a hyphen is accepted in place of the
#: em dash so a typographic slip is not a parse failure.
_STEP_HEADING = re.compile(r"^##\s+Step\s+(\d+)\s*[\u2014\u2013-]\s*(\S.*?)\s*$")

#: Any level-2 heading that begins with `Step`, so one that does *not* parse as
#: a step heading is reported instead of skipped.
_STEP_HEADING_CANDIDATE = re.compile(r"^##\s+Step\b")

#: A heading of level 1 or 2, which is where a step block ends.
_BLOCK_BOUNDARY = re.compile(r"^#{1,2}\s")

#: A top-level field item: `- **Label:** value`, at column zero.
_FIELD_ITEM = re.compile(r"^-\s+\*\*(?P<label>[^*]+?):\*\*\s*(?P<value>.*)$")

#: A backticked cell id: `` `<step>.<key>` ``.
_CELL_ID = re.compile(r"^`(?P<step>\d+)\.(?P<key>[A-Za-z0-9][A-Za-z0-9._-]*)`$")

#: A table delimiter row: `|---|---|` in any of its spellings.
_DELIMITER_ROW = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+$")


class ChecklistError(ValueError):
    """`docs/test-checklist.md` does not satisfy the grammar it documents.

    Raised rather than worked around: the checklist is the definition every
    record is emitted from, so a definition this module cannot read would
    otherwise produce a record with a step silently missing — and a missing step
    is exactly what the gate is supposed to catch.
    """


class RecordError(ValueError):
    """A record cannot be read unambiguously — a duplicate step or cell row, a
    cell id naming no defined step, a table row whose columns do not line up.

    An ambiguous record is never resolved by picking one reading: the Maintainer
    is told which row is ambiguous so the committed file can be corrected.
    """


@dataclass(frozen=True)
class ChecklistCell:
    """One cell of a step's definition: its id, its key, its label, its slot.

    `slot` is the recording slot as the *definition* spells it, normally
    `_unrecorded_`. A platform cell's `key` is a Supported_Platform; a step 6
    activation cell's `key` is a skill name.
    """

    id: str
    key: str
    label: str
    slot: str

    @property
    def step(self) -> int:
        return int(self.id.split(".", 1)[0])


@dataclass(frozen=True)
class ChecklistStep:
    """One defined step: its number, its title, its fields, and its cells.

    `fields` keeps every field's raw Markdown in document order, so the record
    emitter can quote the definition without this module restating any of the
    checklist's prose.
    """

    number: int
    title: str
    fields: Mapping[str, str] = field(default_factory=dict)
    platform_cells: tuple[ChecklistCell, ...] = ()
    activation_cells: tuple[ChecklistCell, ...] = ()

    @property
    def verifies(self) -> str:
        return self.fields.get(FIELD_VERIFIES, "")

    @property
    def per_platform(self) -> bool:
        """Whether this step records one outcome per Supported_Platform."""
        return bool(self.platform_cells)

    @property
    def platforms(self) -> tuple[str, ...]:
        return tuple(cell.key for cell in self.platform_cells)

    def cell(self, key: str) -> ChecklistCell | None:
        for candidate in self.platform_cells:
            if candidate.key == key:
                return candidate
        return None


@dataclass(frozen=True)
class ChecklistDefinition:
    """The parsed `Test_Checklist`: the steps a record has to account for."""

    steps: tuple[ChecklistStep, ...]
    source: str | None = None

    @property
    def step_numbers(self) -> tuple[int, ...]:
        return tuple(step.number for step in self.steps)

    @property
    def platform_steps(self) -> tuple[int, ...]:
        return tuple(step.number for step in self.steps if step.per_platform)

    @property
    def platform_cell_ids(self) -> tuple[str, ...]:
        """Every per-platform cell id, in step then platform order."""
        return tuple(
            cell.id for step in self.steps for cell in step.platform_cells
        )

    def step(self, number: int) -> ChecklistStep | None:
        for candidate in self.steps:
            if candidate.number == number:
                return candidate
        return None


def default_definition() -> ChecklistDefinition:
    """The declared checklist shape, built without reading any file.

    The definition parsed from `docs/test-checklist.md` is the real one; this is
    the shape that file is required to have, and exists so the gate can be
    computed — and property-tested — without a document on disk.
    """
    steps: list[ChecklistStep] = []
    for number in range(1, CHECKLIST_STEP_COUNT + 1):
        cells: tuple[ChecklistCell, ...] = ()
        if number in PER_PLATFORM_STEPS:
            cells = tuple(
                ChecklistCell(
                    id=f"{number}.{platform}",
                    key=platform,
                    label=PLATFORM_LABELS[platform],
                    slot=UNRECORDED,
                )
                for platform in SUPPORTED_PLATFORMS
            )
        steps.append(
            ChecklistStep(number=number, title=f"Step {number}", platform_cells=cells)
        )
    return ChecklistDefinition(steps=tuple(steps))


# ---------------------------------------------------------------------------
# Reading Markdown: lines, tables, and cell values
# ---------------------------------------------------------------------------


def _lines(text: str) -> list[str]:
    """Document lines with line endings normalized, so CRLF parses like LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _unescape_cell(value: str) -> str:
    """Undo the pipe escaping a table cell needs."""
    return value.replace("\\|", "|").strip()


def _split_row(row: str) -> list[str]:
    """The cells of one table row, outer pipes dropped, each stripped.

    Rows nested under a field label are indented, so leading whitespace is
    stripped first. An escaped pipe (`\\|`) is content, not a column boundary.
    """
    stripped = row.strip()
    body = stripped[1:-1] if stripped.endswith("|") else stripped[1:]
    parts = re.split(r"(?<!\\)\|", body)
    return [_unescape_cell(part) for part in parts]


def _is_table_row(line: str) -> bool:
    return line.strip().startswith("|")


@dataclass(frozen=True)
class _Table:
    """One Markdown table: its header names and its data rows."""

    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def column(self, *names: str) -> int | None:
        """The index of the first header matching any of `names`, or `None`."""
        normalized = [header.strip().lower() for header in self.headers]
        for name in names:
            if name in normalized:
                return normalized.index(name)
        return None

    def value(self, row: Sequence[str], index: int | None) -> str:
        if index is None or index >= len(row):
            return ""
        return row[index]


def _tables(lines: Iterable[str]) -> list[_Table]:
    """Every Markdown table in `lines`, in document order.

    A table is a run of consecutive rows: a header, a delimiter, then data. A
    run with no delimiter row is prose that happens to start with a pipe and is
    not read as a table.
    """
    tables: list[_Table] = []
    run: list[str] = []

    def flush() -> None:
        if len(run) >= 2 and _DELIMITER_ROW.match(run[1].strip()):
            headers = tuple(_split_row(run[0]))
            rows = tuple(tuple(_split_row(row)) for row in run[2:])
            tables.append(_Table(headers=headers, rows=rows))
        run.clear()

    for line in lines:
        if _is_table_row(line):
            run.append(line)
        else:
            flush()
    flush()
    return tables


def _strip_code_span(value: str) -> str:
    """A value with one layer of surrounding backticks removed."""
    text = value.strip()
    if len(text) >= 2 and text.startswith("`") and text.endswith("`"):
        return text[1:-1].strip()
    return text


def _recorded_value(value: str) -> str:
    """A recording slot read as data: `` `_unrecorded_` `` and blank both read
    as the empty string, which is the shape the gate calls unrecorded."""
    text = _strip_code_span(value)
    if text.lower() == UNRECORDED:
        return ""
    return text


def _outcome_value(value: str) -> str:
    """A recorded outcome, case-folded. Blank means unrecorded."""
    return _recorded_value(value).lower()


# ---------------------------------------------------------------------------
# Parsing the checklist definition
# ---------------------------------------------------------------------------


def _step_blocks(lines: Sequence[str]) -> list[tuple[int, str, list[str]]]:
    """`(number, title, body)` for each `## Step <N> — <title>` block."""
    blocks: list[tuple[int, str, list[str]]] = []
    current: tuple[int, str, list[str]] | None = None
    for line in lines:
        heading = _STEP_HEADING.match(line)
        if heading is not None:
            current = (int(heading.group(1)), heading.group(2).strip(), [])
            blocks.append(current)
            continue
        if _STEP_HEADING_CANDIDATE.match(line):
            raise ChecklistError(
                f"a level-2 heading begins with Step but is not a step heading: "
                f"{line.strip()!r}; the grammar is `## Step <N> — <title>`"
            )
        if _BLOCK_BOUNDARY.match(line):
            current = None
            continue
        if current is not None:
            current[2].append(line)
    return blocks


def _step_fields(number: int, body: Sequence[str]) -> dict[str, list[str]]:
    """A step block's fields: label → its lines, the label line included.

    Everything indented below a field item belongs to that field, which is what
    makes a nested cell table part of the field it sits under.
    """
    fields: dict[str, list[str]] = {}
    label: str | None = None
    for line in body:
        item = _FIELD_ITEM.match(line)
        if item is not None:
            label = item.group("label").strip()
            if label in fields:
                raise ChecklistError(
                    f"step {number} declares the field {label!r} twice"
                )
            fields[label] = [item.group("value").strip()]
            continue
        if label is not None:
            fields[label].append(line)
    return fields


def _cells_from_field(
    number: int, label: str, lines: Sequence[str]
) -> tuple[ChecklistCell, ...]:
    """The cells of one cell table, read from the field's nested table."""
    tables = _tables(lines)
    if not tables:
        raise ChecklistError(
            f"step {number} declares {label!r} but carries no cell table under it"
        )
    if len(tables) > 1:
        raise ChecklistError(
            f"step {number} carries {len(tables)} tables under {label!r}; a cell "
            "field carries exactly one"
        )
    table = tables[0]
    cells: list[ChecklistCell] = []
    seen: set[str] = set()
    for row in table.rows:
        if len(row) < 2:
            raise ChecklistError(
                f"step {number} has a {label!r} row with fewer than two columns: "
                f"{list(row)!r}"
            )
        identifier = _CELL_ID.match(row[0].strip())
        if identifier is None:
            raise ChecklistError(
                f"step {number} has a {label!r} row whose first column is not a "
                f"backticked `<step>.<key>` cell id: {row[0]!r}"
            )
        if int(identifier.group("step")) != number:
            raise ChecklistError(
                f"step {number} carries the cell {row[0]!r}, which names another "
                "step; a cell id's step is the step it is defined under"
            )
        key = identifier.group("key")
        if key in seen:
            raise ChecklistError(f"step {number} declares the cell {key!r} twice")
        seen.add(key)
        cells.append(
            ChecklistCell(
                id=f"{number}.{key}",
                key=key,
                label=PLATFORM_LABELS.get(key, key),
                slot=_strip_code_span(row[-1]),
            )
        )
    return tuple(cells)


def parse_checklist(text: str, *, source: str | None = None) -> ChecklistDefinition:
    """Parse `docs/test-checklist.md` into the definition a record is emitted from.

    Implements the grammar that file documents, and enforces the shape the
    requirements fix: `CHECKLIST_STEP_COUNT` steps numbered 1..N with no gaps and
    no repeats, `Platform cells` on exactly `PER_PLATFORM_STEPS` carrying exactly
    the Supported_Platforms, and `Activation cells` on no step that records per
    platform. Anything else raises `ChecklistError` *(R6 AC1, AC12)*.
    """
    lines = _lines(text)
    blocks = _step_blocks(lines)
    if not blocks:
        raise ChecklistError(
            "no `## Step <N> — <title>` heading found: this is not a Test_Checklist"
        )

    steps: list[ChecklistStep] = []
    for number, title, body in blocks:
        fields = _step_fields(number, body)
        missing = [name for name in REQUIRED_FIELDS if name not in fields]
        if missing:
            raise ChecklistError(
                f"step {number} is missing the required field(s) "
                f"{', '.join(missing)}"
            )
        platform_cells: tuple[ChecklistCell, ...] = ()
        activation_cells: tuple[ChecklistCell, ...] = ()
        if FIELD_PLATFORM_CELLS in fields:
            platform_cells = _cells_from_field(
                number, FIELD_PLATFORM_CELLS, fields[FIELD_PLATFORM_CELLS]
            )
        if FIELD_ACTIVATION_CELLS in fields:
            activation_cells = _cells_from_field(
                number, FIELD_ACTIVATION_CELLS, fields[FIELD_ACTIVATION_CELLS]
            )
        steps.append(
            ChecklistStep(
                number=number,
                title=title,
                fields={
                    label: "\n".join(text).strip()
                    for label, text in fields.items()
                },
                platform_cells=platform_cells,
                activation_cells=activation_cells,
            )
        )

    _require_declared_shape(steps)
    return ChecklistDefinition(steps=tuple(steps), source=source)


def _require_declared_shape(steps: Sequence[ChecklistStep]) -> None:
    """Enforce the numbering and the per-platform matrix the requirements fix."""
    numbers = [step.number for step in steps]
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        raise ChecklistError(
            f"step headings must run 1..{len(numbers)} strictly increasing with no "
            f"gaps and no repeats; found {numbers}"
        )
    if len(numbers) != CHECKLIST_STEP_COUNT:
        raise ChecklistError(
            f"the Test_Checklist defines {len(numbers)} steps but "
            f"CHECKLIST_STEP_COUNT is {CHECKLIST_STEP_COUNT}; a checklist that "
            "grew a step also changes RECORD_FORMAT_VERSION"
        )

    if MATRIX_STEP not in numbers:
        raise ChecklistError(
            f"the Test_Checklist defines no step {MATRIX_STEP}, which is the step "
            "that asserts the nine-cell per-platform matrix is complete"
        )

    per_platform = tuple(step.number for step in steps if step.per_platform)
    if per_platform != tuple(PER_PLATFORM_STEPS):
        raise ChecklistError(
            f"steps {list(PER_PLATFORM_STEPS)} record one outcome per "
            f"Supported_Platform; found platform cells on {list(per_platform)}"
        )
    for step in steps:
        if step.per_platform and step.platforms != tuple(SUPPORTED_PLATFORMS):
            raise ChecklistError(
                f"step {step.number} must carry one cell per Supported_Platform "
                f"{list(SUPPORTED_PLATFORMS)}; found {list(step.platforms)}"
            )
        if step.activation_cells and step.per_platform:
            raise ChecklistError(
                f"step {step.number} carries both activation cells and platform "
                "cells; activation cells are part of a step's definition, not "
                "separate record slots"
            )


def read_checklist(path: str | Path = DEFAULT_CHECKLIST) -> ChecklistDefinition:
    """Parse the checklist definition at `path`."""
    location = Path(path)
    return parse_checklist(
        location.read_text(encoding="utf-8"), source=location.as_posix()
    )


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CellOutcome:
    """One recorded per-platform cell: its id, its platform, its outcome."""

    id: str
    step: int
    platform: str
    outcome: str
    notes: str = ""

    @property
    def recorded_pass(self) -> bool:
        return self.outcome == OUTCOME_PASS

    def to_json(self) -> dict[str, Any]:
        return {
            "cell": self.id,
            "step": self.step,
            "platform": self.platform,
            "outcome": self.outcome or None,
            "notes": self.notes or None,
        }


@dataclass(frozen=True)
class StepOutcome:
    """One recorded step: its number, its outcome, its notes, its cells.

    For a per-platform step the cells are the record of truth and `outcome` is
    **derived** from them — a pass only when all three are a pass — so a rolled
    up pass cannot be recorded over a blank cell.
    """

    step: int
    outcome: str = ""
    notes: str = ""
    cells: tuple[CellOutcome, ...] = ()

    @property
    def per_platform(self) -> bool:
        return bool(self.cells)

    @property
    def rolled_up(self) -> str:
        """The step's effective outcome: derived for a per-platform step."""
        if not self.per_platform:
            return self.outcome
        outcomes = {cell.outcome for cell in self.cells}
        if outcomes == {OUTCOME_PASS}:
            return OUTCOME_PASS
        if OUTCOME_FAIL in outcomes:
            return OUTCOME_FAIL
        return ""

    @property
    def recorded_pass(self) -> bool:
        return self.rolled_up == OUTCOME_PASS

    def cell(self, platform: str) -> CellOutcome | None:
        for candidate in self.cells:
            if candidate.platform == platform:
                return candidate
        return None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "step": self.step,
            "outcome": self.rolled_up or None,
            "notes": self.notes or None,
        }
        if self.per_platform:
            payload["cells"] = {
                cell.platform: cell.outcome or None for cell in self.cells
            }
        return payload


@dataclass(frozen=True)
class TestRecord:
    """A parsed `docs/test-records/<version>.md` *(R6 AC2, AC6)*.

    `version` is the version the record **names**, which the gate compares
    against the version under test rather than assuming they agree. `outcomes`
    is the per-step view the gate and the round-trip both work in: a step number
    maps to its outcome string, except for a per-platform step, which maps to one
    outcome per Supported_Platform. A step absent from the mapping is a step with
    no recorded outcome at all.
    """

    version: str = ""
    template_release: str = ""
    maintainer: str = ""
    date: str = ""
    validation_status: str = ""
    steps: tuple[StepOutcome, ...] = ()
    format_version: int = RECORD_FORMAT_VERSION
    source: str | None = None

    @property
    def outcomes(self) -> dict[int, Any]:
        """Recorded outcomes keyed by step, per-platform steps keyed by platform."""
        recorded: dict[int, Any] = {}
        for step in self.steps:
            if step.per_platform:
                recorded[step.step] = {
                    cell.platform: cell.outcome for cell in step.cells
                }
            else:
                recorded[step.step] = step.outcome
        return recorded

    @property
    def notes(self) -> dict[int, str]:
        return {step.step: step.notes for step in self.steps if step.notes}

    @property
    def cell_notes(self) -> dict[str, str]:
        return {
            cell.id: cell.notes
            for step in self.steps
            for cell in step.cells
            if cell.notes
        }

    def step(self, number: int) -> StepOutcome | None:
        for candidate in self.steps:
            if candidate.step == number:
                return candidate
        return None


def _header_facts(lines: Sequence[str]) -> dict[str, str]:
    """The record's `- **Label:** value` header items, keyed by normalized label."""
    facts: dict[str, str] = {}
    for line in lines:
        item = re.match(r"^\s*-\s+\*\*(?P<label>[^*]+?):\*\*\s*(?P<value>.*)$", line)
        if item is None:
            continue
        spelled = item.group("label").replace("_", " ")
        label = re.sub(r"\s+", " ", spelled).strip().lower()
        facts.setdefault(label, item.group("value").strip())
    return facts


def _fact(facts: Mapping[str, str], *labels: str) -> str:
    for label in labels:
        if label in facts:
            return _recorded_value(facts[label])
    return ""


def _platform_of(key: str) -> str:
    """A cell key read as a Supported_Platform, case-folded."""
    return key.strip().lower()


def parse_record(
    text: str,
    *,
    definition: ChecklistDefinition | None = None,
    source: str | None = None,
) -> TestRecord:
    """Parse a committed record back into recorded outcomes.

    Tables are read by column name, so `Step`/`Outcome`/`Notes` may sit in any
    order. A step or cell recorded twice raises `RecordError`: an ambiguous
    record is corrected, never guessed at. A blank or `_unrecorded_` outcome
    parses as the empty string, which is what the gate reads as unrecorded.
    """
    known = definition or default_definition()
    lines = _lines(text)
    facts = _header_facts(lines)

    step_outcomes: dict[int, tuple[str, str]] = {}
    cell_outcomes: dict[str, tuple[str, str]] = {}
    for table in _tables(lines):
        step_column = table.column("step", "step #", "#")
        cell_column = table.column("cell", "cell id")
        if cell_column is not None:
            _read_cell_rows(table, cell_column, cell_outcomes, known)
        elif step_column is not None:
            _read_step_rows(table, step_column, step_outcomes)
    _read_outcome_items(lines, step_outcomes)

    recorded_steps = set(step_outcomes) | {
        _cell_step(identifier) for identifier in cell_outcomes
    }
    steps: list[StepOutcome] = []
    for number in sorted(recorded_steps):
        outcome, notes = step_outcomes.get(number, ("", ""))
        cells = tuple(
            CellOutcome(
                id=identifier,
                step=number,
                platform=identifier.split(".", 1)[1],
                outcome=cell_outcomes[identifier][0],
                notes=cell_outcomes[identifier][1],
            )
            for identifier in _cell_ids_of(number, cell_outcomes)
        )
        steps.append(
            StepOutcome(step=number, outcome=outcome, notes=notes, cells=cells)
        )

    format_version = _fact(facts, "record format version")
    return TestRecord(
        version=_fact(facts, "version under test", "version"),
        template_release=_fact(facts, "template release"),
        maintainer=_fact(facts, "maintainer"),
        date=_fact(facts, "date"),
        validation_status=_fact(
            facts,
            "validationreport status",
            "validation report status",
            "validation status",
        ),
        steps=tuple(steps),
        format_version=int(format_version) if format_version.isdigit() else 0,
        source=source,
    )


def _cell_step(cell_id: str) -> int:
    return int(cell_id.split(".", 1)[0])


def _cell_ids_of(step: int, cells: Mapping[str, tuple[str, str]]) -> list[str]:
    """A step's cell ids, in Supported_Platform order, unknown keys last."""
    owned = [identifier for identifier in cells if _cell_step(identifier) == step]

    def position(identifier: str) -> tuple[int, str]:
        platform = identifier.split(".", 1)[1]
        if platform in SUPPORTED_PLATFORMS:
            return (SUPPORTED_PLATFORMS.index(platform), platform)
        return (len(SUPPORTED_PLATFORMS), platform)

    return sorted(owned, key=position)


def _read_step_rows(
    table: _Table, step_column: int, into: dict[int, tuple[str, str]]
) -> None:
    outcome_column = table.column("outcome", "result")
    notes_column = table.column("notes", "note", "evidence")
    for row in table.rows:
        identifier = _strip_code_span(table.value(row, step_column))
        if not identifier:
            continue
        if not identifier.isdigit():
            raise RecordError(
                f"a step row's first column is not a step number: {identifier!r}"
            )
        number = int(identifier)
        if number in into:
            raise RecordError(
                f"step {number} is recorded twice; a record carries one row per step"
            )
        into[number] = (
            _outcome_value(table.value(row, outcome_column)),
            _recorded_value(table.value(row, notes_column)),
        )


def _read_outcome_items(
    lines: Sequence[str], into: dict[int, tuple[str, str]]
) -> None:
    """Read `- **Outcome:** value` items inside `## Step <N>` blocks.

    This is the hand-copy route the checklist offers beside `emit`: a Maintainer
    who copies `docs/test-checklist.md` to `docs/test-records/<version>.md` and
    fills in each step's own `**Outcome:**` slot has recorded that step, and the
    gate reads it there. A step already recorded in a step table keeps the
    table's row, so the two routes never contend for the same step.
    """
    step: int | None = None
    for line in lines:
        heading = _STEP_HEADING.match(line)
        if heading is not None:
            step = int(heading.group(1))
            continue
        if _BLOCK_BOUNDARY.match(line):
            step = None
            continue
        if step is None or step in into:
            continue
        item = _FIELD_ITEM.match(line)
        if item is not None and item.group("label").strip() == FIELD_OUTCOME:
            into[step] = (_outcome_value(item.group("value")), "")


def _read_cell_rows(
    table: _Table,
    cell_column: int,
    into: dict[str, tuple[str, str]],
    definition: ChecklistDefinition,
) -> None:
    outcome_column = table.column("outcome", "result")
    notes_column = table.column("notes", "note", "evidence")
    for row in table.rows:
        raw = table.value(row, cell_column).strip()
        if not raw:
            continue
        identifier = _CELL_ID.match(raw) or _CELL_ID.match(f"`{_strip_code_span(raw)}`")
        if identifier is None:
            raise RecordError(
                f"a cell row's first column is not a `<step>.<platform>` cell id: "
                f"{raw!r}"
            )
        step = int(identifier.group("step"))
        platform = _platform_of(identifier.group("key"))
        cell_id = f"{step}.{platform}"
        defined = definition.step(step)
        if defined is None:
            raise RecordError(
                f"the record carries cell {cell_id!r} but the checklist defines no "
                f"step {step}"
            )
        if not defined.per_platform:
            # Step 6's activation cells are part of the checklist's *definition*
            # — they say what to try — so they are not record slots: step 6
            # records one rolled-up outcome like any other step.
            continue
        if defined.cell(platform) is None:
            raise RecordError(
                f"the record carries cell {cell_id!r}, but step {step} records one "
                f"outcome per Supported_Platform {list(SUPPORTED_PLATFORMS)}"
            )
        if cell_id in into:
            raise RecordError(
                f"cell {cell_id!r} is recorded twice; a record carries one row per "
                "platform cell"
            )
        into[cell_id] = (
            _outcome_value(table.value(row, outcome_column)),
            _recorded_value(table.value(row, notes_column)),
        )


def read_record(
    path: str | Path, *, definition: ChecklistDefinition | None = None
) -> TestRecord:
    """Parse the record at `path`."""
    location = Path(path)
    return parse_record(
        location.read_text(encoding="utf-8"),
        definition=definition,
        source=location.as_posix(),
    )


# ---------------------------------------------------------------------------
# Rendering a record
# ---------------------------------------------------------------------------


def _escape_cell(value: str) -> str:
    """Text safe inside a table cell: pipes escaped, newlines folded away."""
    folded = " ".join(str(value).split())
    return folded.replace("|", "\\|")


def _slot(value: str) -> str:
    """How an outcome or a note is written into a record: a code span, or blank."""
    text = str(value).strip()
    return f"`{text}`" if text else f"`{UNRECORDED}`"


def _note_cell(value: str) -> str:
    return _escape_cell(value) if str(value).strip() else ""


def _checklist_reference(source: str | None) -> str:
    """How a record names the checklist it was emitted from: repo-relative.

    An absolute path would put one machine's directory layout into a committed
    artifact, so it is reduced to its repository-relative form, and to the bare
    file name when it lies outside the repository.
    """
    if not source:
        return ""
    location = Path(source)
    if not location.is_absolute():
        return location.as_posix()
    try:
        return location.resolve().relative_to(_REPOSITORY_ROOT).as_posix()
    except ValueError:
        return location.name


def _step_outcome_cell(step: ChecklistStep, recorded: Any) -> str:
    """The step table's outcome cell: derived for a per-platform step."""
    if step.per_platform:
        values = [
            str(recorded.get(platform, "")).strip().lower()
            for platform in step.platforms
        ]
        if values and all(value == OUTCOME_PASS for value in values):
            return _slot(OUTCOME_PASS)
        if OUTCOME_FAIL in values:
            return _slot(OUTCOME_FAIL)
        return _slot("")
    return _slot(str(recorded))


def render_record(
    definition: ChecklistDefinition,
    version: str,
    *,
    outcomes: Mapping[int, Any] | None = None,
    template_release: str = "",
    maintainer: str = "",
    date: str = "",
    validation_status: str = "",
    notes: Mapping[int, str] | None = None,
    cell_notes: Mapping[str, str] | None = None,
) -> str:
    """Render `docs/test-records/<version>.md` for one version under test.

    With no `outcomes`, this is the skeleton a Maintainer fills in: every defined
    step and every per-platform cell present and `_unrecorded_`, which the gate
    reads as closed. With `outcomes`, each step present in the mapping is
    rendered with what it records — a per-platform step keyed by platform — and
    each step *absent* from the mapping is left out of the record entirely,
    because a step nobody ran is not the same as a step recorded blank. That is
    what makes `parse_record(render_record(...))` recover the identical set of
    outcomes *(Property 23)*.

    Reads no clock: `date` is supplied, never defaulted to today, so a record's
    bytes are a function of its inputs.
    """
    recorded = dict(outcomes) if outcomes is not None else {
        step.number: (
            {platform: "" for platform in step.platforms} if step.per_platform else ""
        )
        for step in definition.steps
    }
    # A per-platform step records one outcome per platform. A caller handing one
    # bare outcome for such a step means it on every platform, so it is spread
    # across the cells rather than silently recorded nowhere.
    for step in definition.steps:
        value = recorded.get(step.number)
        if step.per_platform and value is not None:
            if not isinstance(value, collections.abc.Mapping):
                recorded[step.number] = {
                    platform: value for platform in step.platforms
                }
    step_notes = dict(notes or {})
    per_cell_notes = dict(cell_notes or {})
    included = [step for step in definition.steps if step.number in recorded]

    out: list[str] = []
    out.append(f"# Test_Checklist record — Bootcamp_Power {version}")
    out.append("")
    out.append(
        "Recorded outcomes for every step of the Test_Checklist, and for each"
    )
    out.append(
        "per-platform cell. Tagging is allowed only when every step below carries"
    )
    out.append(
        f"a recorded `{OUTCOME_PASS}` for exactly this version and no outcome is"
    )
    out.append(
        f"left `{UNRECORDED}`; anything else blocks tagging with"
    )
    out.append(
        f"`{E_CHECKLIST_INCOMPLETE}`. An `{UNRECORDED}` outcome is a fail, not a"
    )
    out.append("blank.")
    out.append("")
    out.append(f"- **Record format version:** `{RECORD_FORMAT_VERSION}`")
    out.append(f"- **Version under test:** {_slot(version)}")
    out.append(f"- **Template_Release:** {_slot(template_release)}")
    out.append(f"- **Maintainer:** {_slot(maintainer)}")
    out.append(f"- **Date:** {_slot(date)}")
    out.append(f"- **ValidationReport status:** {_slot(validation_status)}")
    reference = _checklist_reference(definition.source)
    if reference:
        out.append(f"- **Checklist:** `{reference}`")
    out.append("")
    out.append("## Recorded step outcomes")
    out.append("")
    out.append("| Step | Outcome | Notes | Step title |")
    out.append("|---|---|---|---|")
    for step in included:
        out.append(
            f"| `{step.number}` "
            f"| {_step_outcome_cell(step, recorded[step.number])} "
            f"| {_note_cell(step_notes.get(step.number, ''))} "
            f"| {_escape_cell(step.title)} |"
        )
    out.append("")
    out.append("## Recorded platform cells")
    out.append("")
    platform_steps = ", ".join(str(number) for number in definition.platform_steps)
    out.append("One outcome per Supported_Platform for each of steps")
    out.append(f"{platform_steps}, each produced by a run on that platform rather")
    out.append("than inferred from another. These cells are the record of truth for")
    out.append("those steps: the step above passes only when all of its cells pass.")
    out.append("")
    out.append("| Cell | Outcome | Notes | Platform |")
    out.append("|---|---|---|---|")
    for step in included:
        if not step.per_platform:
            continue
        cells = recorded[step.number]
        for cell in step.platform_cells:
            if cell.key not in cells:
                continue
            out.append(
                f"| `{cell.id}` "
                f"| {_slot(str(cells[cell.key]))} "
                f"| {_note_cell(per_cell_notes.get(cell.id, ''))} "
                f"| {_escape_cell(cell.label)} |"
            )
    out.append("")
    return "\n".join(out)


def write_record(text: str, path: str | Path) -> Path:
    """Write a rendered record with LF endings, creating its directory.

    LF unconditionally, matching the committed `.gitattributes`, so the record a
    Maintainer commits reads the same on every Supported_Platform *(R16 AC8)*.
    """
    location = Path(path)
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(text, encoding="utf-8", newline="\n")
    return location


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

REASON_MISSING_STEP = "missing-step"
REASON_BLANK_OUTCOME = "blank-outcome"
REASON_FAIL = "fail"
REASON_UNRECOGNIZED = "unrecognized-outcome"
REASON_BLANK_CELL = "blank-platform-cell"
REASON_MISSING_CELL = "missing-platform-cell"
REASON_VERSION_MISMATCH = "version-mismatch"


@dataclass(frozen=True)
class Finding:
    """One reason tagging is blocked, named precisely enough to act on.

    Every finding carries `E_CHECKLIST_INCOMPLETE` — the catalog has one code for
    an incomplete checklist — and `reason` says which shape of incompleteness it
    is, so a Maintainer reads "step 10's macOS cell is blank" rather than a
    count.
    """

    reason: str
    message: str
    step: int | None = None
    cell: str | None = None
    code: str = E_CHECKLIST_INCOMPLETE

    @property
    def label(self) -> str:
        """A compact identifier: `blank-platform-cell:10:macos`."""
        parts = [self.reason]
        if self.step is not None:
            parts.append(str(self.step))
        if self.cell is not None:
            parts.append(self.cell.split(".", 1)[-1])
        return ":".join(parts)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "reason": self.reason,
            "message": self.message,
        }
        if self.step is not None:
            payload["step"] = self.step
        if self.cell is not None:
            payload["cell"] = self.cell
        return payload


@dataclass(frozen=True)
class TestRecordReport:
    """The gate's verdict over one record, and why *(R6 AC2, AC3, AC12)*.

    `tag_allowed` is derived from `findings` being empty, never assigned: a
    record that recorded nothing blocks tagging, and so does a record this
    module could not read. The per-step outcomes travel in the report as well as
    in the committed Markdown, so the evidence stays reviewable for the tagged
    release *(R6 AC6)*.
    """

    version: str
    record: TestRecord
    findings: tuple[Finding, ...]

    @property
    def tag_allowed(self) -> bool:
        """The gate. True only when nothing is missing, blank, or failed."""
        return not self.findings

    @property
    def error(self) -> str | None:
        return None if self.tag_allowed else E_CHECKLIST_INCOMPLETE

    @property
    def defects(self) -> tuple[str, ...]:
        """Every finding's compact label, in report order."""
        return tuple(finding.label for finding in self.findings)

    def findings_for(self, reason: str) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.reason == reason)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "recordFormatVersion": self.record.format_version,
            "version": self.version,
            "recordedVersion": self.record.version or None,
            "templateRelease": self.record.template_release or None,
            "maintainer": self.record.maintainer or None,
            "date": self.record.date or None,
            "validationStatus": self.record.validation_status or None,
            "steps": [step.to_json() for step in self.record.steps],
            "platformCells": [
                cell.to_json() for step in self.record.steps for cell in step.cells
            ],
            "findings": [finding.to_json() for finding in self.findings],
            "tagAllowed": self.tag_allowed,
        }
        if not self.tag_allowed:
            payload["error"] = E_CHECKLIST_INCOMPLETE
        if self.record.source is not None:
            payload["record"] = self.record.source
        return payload

    def summary(self) -> str:
        """One narration line: what a Maintainer reads first."""
        return (
            f"{len(self.record.steps)} step(s) recorded of "
            f"{CHECKLIST_STEP_COUNT}, {len(self.findings)} blocking "
            f"{E_CHECKLIST_INCOMPLETE} finding(s): tagAllowed "
            f"{str(self.tag_allowed).lower()}"
        )


def _outcome_finding(step: int, outcome: str) -> Finding | None:
    """The finding a step-level outcome earns, or `None` when it is a pass."""
    if outcome == OUTCOME_PASS:
        return None
    if not outcome:
        return Finding(
            REASON_BLANK_OUTCOME,
            f"step {step} has no recorded outcome; an {UNRECORDED} outcome is a "
            "fail, not a blank",
            step=step,
        )
    if outcome == OUTCOME_FAIL:
        return Finding(
            REASON_FAIL, f"step {step} is recorded as a fail", step=step
        )
    return Finding(
        REASON_UNRECOGNIZED,
        f"step {step} records {outcome!r}, which is neither {OUTCOME_PASS} nor "
        f"{OUTCOME_FAIL}; a note is not an outcome",
        step=step,
    )


def _cell_finding(
    cell_id: str, step: int, platform: str, outcome: str
) -> Finding | None:
    """The finding one per-platform cell earns, or `None` when it is a pass."""
    if outcome == OUTCOME_PASS:
        return None
    if not outcome:
        return Finding(
            REASON_BLANK_CELL,
            f"cell {cell_id} is {UNRECORDED}: {platform} was not run for step "
            f"{step}, and an unrecorded platform is a fail, not a blank",
            step=step,
            cell=cell_id,
        )
    if outcome == OUTCOME_FAIL:
        return Finding(
            REASON_FAIL,
            f"cell {cell_id} is recorded as a fail on {platform}",
            step=step,
            cell=cell_id,
        )
    return Finding(
        REASON_UNRECOGNIZED,
        f"cell {cell_id} records {outcome!r}, which is neither {OUTCOME_PASS} nor "
        f"{OUTCOME_FAIL}; a platform covered by a note is a fail",
        step=step,
        cell=cell_id,
    )


def evaluate(
    record: TestRecord,
    *,
    version: str,
    definition: ChecklistDefinition | None = None,
) -> TestRecordReport:
    """Compute the tagging gate for `record` against the version under test.

    Reports **every** reason tagging is blocked rather than the first one, so a
    Maintainer sees the whole remaining run in one pass. A per-platform step is
    judged by its nine-cell matrix and not separately at step level, so one blank
    cell is one finding rather than two. Step `MATRIX_STEP`'s own outcome is
    checked like any other step's, but it grants nothing: the matrix is verified
    against the cells themselves *(R6 AC12)*.
    """
    known = definition or default_definition()
    findings: list[Finding] = []

    if record.version != version:
        recorded = record.version or UNRECORDED
        findings.append(
            Finding(
                REASON_VERSION_MISMATCH,
                f"the record names version {recorded} but the version under test "
                f"is {version}; a record only gates the exact version it names",
            )
        )

    for step in known.steps:
        recorded_step = record.step(step.number)
        if recorded_step is None:
            findings.append(
                Finding(
                    REASON_MISSING_STEP,
                    f"step {step.number} has no row in the record: it was never "
                    "recorded",
                    step=step.number,
                )
            )
            continue
        if step.per_platform:
            for cell in step.platform_cells:
                recorded_cell = recorded_step.cell(cell.key)
                if recorded_cell is None:
                    findings.append(
                        Finding(
                            REASON_MISSING_CELL,
                            f"step {step.number} has no cell for {cell.label}; "
                            "each of the nine platform cells is recorded on its "
                            "own platform",
                            step=step.number,
                            cell=cell.id,
                        )
                    )
                    continue
                finding = _cell_finding(
                    cell.id, step.number, cell.label, recorded_cell.outcome
                )
                if finding is not None:
                    findings.append(finding)
            continue
        finding = _outcome_finding(step.number, recorded_step.outcome)
        if finding is not None:
            findings.append(finding)

    return TestRecordReport(
        version=version, record=record, findings=tuple(findings)
    )


def evaluate_outcomes(
    outcomes: Mapping[int, Any],
    *,
    version: str,
    record_version: str | None = None,
    definition: ChecklistDefinition | None = None,
) -> TestRecordReport:
    """The gate over a bare outcome mapping, with no document in between.

    `outcomes` is the shape `TestRecord.outcomes` returns: a step number mapped
    to its outcome, or to one outcome per Supported_Platform for a per-platform
    step. `record_version` defaults to `version`, so a caller opts into the
    version-mismatch case explicitly.
    """
    known = definition or default_definition()
    steps: list[StepOutcome] = []
    for number in sorted(outcomes):
        value = outcomes[number]
        if isinstance(value, collections.abc.Mapping):
            steps.append(
                StepOutcome(
                    step=number,
                    cells=tuple(
                        CellOutcome(
                            id=f"{number}.{platform}",
                            step=number,
                            platform=platform,
                            outcome=str(cell_outcome).strip().lower(),
                        )
                        for platform, cell_outcome in value.items()
                    ),
                )
            )
        else:
            steps.append(
                StepOutcome(step=number, outcome=str(value).strip().lower())
            )
    record = TestRecord(
        version=version if record_version is None else record_version,
        steps=tuple(steps),
    )
    return evaluate(record, version=version, definition=known)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _narrate(message: str) -> None:
    """Human-readable narration goes to stderr; stdout carries only JSON."""
    print(f"testrecord: {message}", file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testrecord.py",
        description=(
            "Emit a Test_Checklist record from the checklist definition, and read "
            "a record back to compute the tagging gate. JSON to stdout, narration "
            "to stderr."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    def add_checklist(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--checklist",
            default=str(DEFAULT_CHECKLIST),
            metavar="PATH",
            help="the Test_Checklist definition to read (default: %(default)s)",
        )

    emit_parser = subparsers.add_parser(
        "emit",
        help=(
            "write a record for one version under test, with every step and "
            f"every platform cell present and {UNRECORDED}"
        ),
    )
    add_checklist(emit_parser)
    emit_parser.add_argument(
        "--version",
        required=True,
        metavar="SEMVER",
        help="the version under test, which the record names",
    )
    emit_parser.add_argument(
        "--out",
        required=True,
        metavar="PATH",
        help=f"where the record is written, normally {RECORDS_DIRECTORY}/<version>.md",
    )
    emit_parser.add_argument(
        "--template-release",
        default="",
        metavar="SEMVER",
        help="the resolved Template_Release the Power under test was built from",
    )
    emit_parser.add_argument(
        "--maintainer",
        default="",
        metavar="NAME",
        help="the Maintainer working the checklist",
    )
    emit_parser.add_argument(
        "--date",
        default="",
        metavar="YYYY-MM-DD",
        help="the date of the run; never defaulted from the clock",
    )
    emit_parser.add_argument(
        "--validation-status",
        default="",
        metavar="STATUS",
        help="the status of the ValidationReport from step 1",
    )

    check_parser = subparsers.add_parser(
        "check",
        help="read a record and report whether tagging is allowed",
    )
    add_checklist(check_parser)
    check_parser.add_argument(
        "--record",
        required=True,
        metavar="PATH",
        help="the committed record to read",
    )
    check_parser.add_argument(
        "--version",
        required=True,
        metavar="SEMVER",
        help="the version being tagged, which the record must name exactly",
    )
    check_parser.add_argument(
        "--report",
        default=None,
        metavar="PATH",
        help="path the verdict JSON is also written to",
    )
    return parser


def _load_definition(path: str) -> ChecklistDefinition:
    definition = read_checklist(path)
    _narrate(
        f"{path}: {len(definition.steps)} step(s), "
        f"{len(definition.platform_cell_ids)} platform cell(s)"
    )
    return definition


def _emit(args: argparse.Namespace) -> int:
    definition = _load_definition(args.checklist)
    text = render_record(
        definition,
        args.version,
        template_release=args.template_release,
        maintainer=args.maintainer,
        date=args.date,
        validation_status=args.validation_status,
    )
    written = write_record(text, args.out)
    _narrate(f"record written to {written.as_posix()}")

    # Read back what was written, so the emit path cannot produce a file this
    # same parser does not accept.
    report = evaluate(
        parse_record(text, definition=definition, source=written.as_posix()),
        version=args.version,
        definition=definition,
    )
    _narrate(report.summary())
    if report.tag_allowed:
        _narrate(
            "every outcome in the emitted record already reads as a pass; a "
            "skeleton is expected to gate tagging closed"
        )
    else:
        _narrate(
            f"the gate is closed until a Maintainer records an outcome for each "
            f"of the {len(definition.steps)} steps and each of the "
            f"{len(definition.platform_cell_ids)} platform cells"
        )
    json.dump(report.to_json(), sys.stdout, indent=2, sort_keys=False)
    print(file=sys.stdout)
    return EXIT_SUCCESS


def _check(args: argparse.Namespace) -> int:
    definition = _load_definition(args.checklist)
    record = read_record(args.record, definition=definition)
    report = evaluate(record, version=args.version, definition=definition)

    for finding in report.findings:
        _narrate(f"{finding.code} {finding.reason}: {finding.message}")
    _narrate(report.summary())

    payload = report.to_json()
    if args.report is not None:
        location = Path(args.report)
        location.parent.mkdir(parents=True, exist_ok=True)
        location.write_text(
            json.dumps(payload, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _narrate(f"verdict written to {location.as_posix()}")

    json.dump(payload, sys.stdout, indent=2, sort_keys=False)
    print(file=sys.stdout)
    return EXIT_SUCCESS if report.tag_allowed else EXIT_BLOCKED


def main(argv: Sequence[str] | None = None) -> int:
    """Run one subcommand and return the process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return EXIT_BLOCKED
    try:
        if args.command == "emit":
            return _emit(args)
        return _check(args)
    except (ChecklistError, RecordError) as error:
        _narrate(f"{type(error).__name__}: {error}")
        return EXIT_BLOCKED
    except OSError as error:
        _narrate(f"could not read or write a document: {error}")
        return EXIT_BLOCKED


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
