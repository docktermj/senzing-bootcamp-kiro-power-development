"""KINV-014: no operation in this repository writes a spec file, and `.kiro/specs/` is frozen.

Two halves, because either alone can be satisfied while the rule is broken:

* **The archive is pinned by name, in both directions.** A spec added under `.kiro/specs/`
  fails, and so does one removed or renamed: the engine and the skills cite
  `requirements.md` as `R<n> AC<m>`, so deleting a frozen file breaks no other test while
  destroying what those citations point at. No count is asserted anywhere; the set is.
* **No operation names a spec file as something it writes.** Every maintainer skill, the
  repository's own `.kiro/skills/`, and the engine scripts are swept for an instruction to
  create, write or generate under `.kiro/specs/`, and for the retired skill's name being
  invoked. Reading the archive, and citing it, stay allowed.

Negative-controlled below: each predicate is shown to fire on the defect it exists for.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SPECS = REPO / ".kiro" / "specs"

#: ⛔ The frozen set, by name. Changing it is a decision recorded in an issue, never a
#: side effect of a run: a new file here is exactly what KINV-014 forbids.
FROZEN = frozenset(
    {
        "README.md",
        "senzing-bootcamp-power/.config.kiro",
        "senzing-bootcamp-power/design.md",
        "senzing-bootcamp-power/requirements.md",
        "senzing-bootcamp-power/tasks.md",
        "senzing-bootcamp-power/tasks.meta.json",
    }
)

#: Where an operation's instructions or code live. The archive itself is not swept: it
#: describes the original build and is read-only.
OPERATION_ROOTS = (
    "powers/senzing-bootcamp-maintainer/skills",
    ".kiro/skills",
    "tools/bootcamp-transform",
)
OPERATION_SUFFIXES = (".md", ".py", ".yaml", ".yml", ".json")

#: An instruction to put a file under `.kiro/specs/`: a write verb, then the path, within a
#: short span on one line.
_WRITE_VERB = r"(?:creat\w*|writ\w*|generat\w*|add\w*|mkdir|open_?\w*|touch)"
WRITES_A_SPEC = re.compile(
    rf"\b{_WRITE_VERB}\b[^\n]{{0,60}}\.kiro/specs/|\.kiro/specs/[^\n]{{0,40}}\.(?:write_text|write|mkdir|open)\(",
    re.IGNORECASE,
)
#: The retired router, invoked: `/feedback-to-specs` or its script path.
INVOKES_RETIRED = re.compile(r"/feedback-to-specs\b|skills/feedback-to-specs/")

#: This file states the rule, and so spells both patterns by construction.
SELF = Path(__file__).resolve()


def archive_files() -> set[str]:
    return {
        path.relative_to(SPECS).as_posix()
        for path in SPECS.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def operation_files() -> list[Path]:
    found = []
    for root in OPERATION_ROOTS:
        for path in (REPO / root).rglob("*"):
            if (
                path.is_file()
                and path.suffix in OPERATION_SUFFIXES
                and "__pycache__" not in path.parts
                and path.resolve() != SELF
            ):
                found.append(path)
    return sorted(found)


def offending_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if WRITES_A_SPEC.search(line) or INVOKES_RETIRED.search(line)
    ]


def test_the_archive_is_exactly_the_frozen_set() -> None:
    present = archive_files()
    added, removed = sorted(present - FROZEN), sorted(FROZEN - present)
    assert not added and not removed, (
        "KINV-014: .kiro/specs/ is a frozen archive. "
        + (f"Added (no operation may write a spec): {added}. " if added else "")
        + (f"Removed (R-citations point at these): {removed}. " if removed else "")
        + "Work is tracked as GitHub issues."
    )


def test_the_archive_is_labelled_frozen() -> None:
    readme = (SPECS / "README.md").read_text(encoding="utf-8")
    assert "frozen" in readme.lower() and "KINV-014" in readme


def test_the_retired_router_is_gone() -> None:
    assert not (REPO / ".kiro" / "skills" / "feedback-to-specs").exists()


def test_no_operation_names_a_spec_file_as_something_it_writes() -> None:
    offenders = {
        path.relative_to(REPO).as_posix(): lines
        for path in operation_files()
        if (lines := offending_lines(path.read_text(encoding="utf-8", errors="replace")))
    }
    assert offenders == {}, (
        "KINV-014: these operations instruct or perform a write under .kiro/specs/, or "
        f"invoke the retired feedback-to-specs router: {offenders}"
    )


def test_the_sweep_reads_something() -> None:
    """A sweep over a wrong root passes vacuously; assert it reached the live skills."""
    names = {p.relative_to(REPO).as_posix() for p in operation_files()}
    assert ".kiro/skills/feedback-to-issues/SKILL.md" in names
    assert "powers/senzing-bootcamp-maintainer/skills/dry-run/SKILL.md" in names


# --- negative controls -----------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "For each new spec, create `.kiro/specs/<kebab-case-title>/` using the template.",
        "writes one or more Kiro specs into `.kiro/specs/`",
        "Path('.kiro/specs/x/requirements.md').write_text(body)",
        "Run `/feedback-to-specs` on the file.",
        "python3 .kiro/skills/feedback-to-specs/feedback_ledger.py find",
    ],
)
def test_a_spec_write_is_caught(line: str) -> None:
    assert offending_lines(line), line


@pytest.mark.parametrize(
    "line",
    [
        "Read `.kiro/specs/senzing-bootcamp-power/requirements.md` for R1–R16.",
        "`.kiro/` holds the spec documents; they are not read by any build step.",
        "the retired feedback-to-specs skill (#25)",
    ],
)
def test_reading_or_naming_the_archive_is_allowed(line: str) -> None:
    assert not offending_lines(line), line
