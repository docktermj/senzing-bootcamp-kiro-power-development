"""Structural / lint tests — facts about this repository, not behaviors.

Design Testing Strategy, layer 3. These are single-execution checks: they assert
claims that are true of the checked-in repository itself, so generated input buys
nothing. Behavioral coverage of the same requirements lives in
`test_properties.py` (the engine's logic) and `test_units.py` (specific examples).

Sections below are grouped by the task that owns them, so later tasks extend the
file by appending to their own section rather than editing another's:

1. Contract single-sourcing (R3 AC1) ....................... task 3.4
2. Engine layout at the declared paths (R14 AC2) ........... task 3.4
3. Line-ending normalization (R16 AC8) ..................... task 3.4
4. Invariant_Discount_Register exclusions (R15 AC6) ........ task 3.4
5. Hook definitions (R7 AC5, AC9, AC12; D2) ................ task 11.7
6. Maintainer tooling placement (R3 AC1, R14 AC2) .......... task 12.4
7. Test_Checklist shape (R6 AC1, AC4, AC5, AC12, AC13) ..... task 13.4
8. Upstream-release watch workflow (R5 AC1) ................ task 17.1
9. Committed Test_Checklist record (R6 AC2, AC3, AC6) ...... task 16.1
10. Assumption-dependent values are single-sourced (R3 AC4)  task 16.2
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Sequence

import pytest
import yaml
from jsonschema import Draft202012Validator

from agent_plugins_schemas import AGENT_PLUGINS_VERSION, PLUGIN_SCHEMA, PLUGIN_SCHEMA_ID
from conftest import REPO_ROOT
from strategies import CHECKLIST_STEP_COUNT as GENERATOR_CHECKLIST_STEP_COUNT
from strategies import HONORED_INVARIANT, HOOK_SCRIPT_NAMES, MAX_DESCRIPTION_LENGTH
from strategies import PER_PLATFORM_STEPS as GENERATOR_PER_PLATFORM_STEPS
from strategies import SUPPORTED_PLATFORMS as GENERATOR_SUPPORTED_PLATFORMS
from strategies import TRIGGER_PHRASES
from testrecord import (
    CHECKLIST_STEP_COUNT,
    DEFAULT_CHECKLIST,
    E_CHECKLIST_INCOMPLETE,
    FIELD_ACTIVATION_CELLS,
    FIELD_DO,
    FIELD_OUTCOME,
    FIELD_PRECONDITIONS,
    FIELD_VERIFIES,
    MATRIX_STEP,
    OUTCOME_PASS,
    PER_PLATFORM_STEPS,
    PLATFORM_LABELS,
    REASON_BLANK_CELL,
    REASON_BLANK_OUTCOME,
    REASON_MISSING_CELL,
    REASON_MISSING_STEP,
    REASON_VERSION_MISMATCH,
    RECORD_FORMAT_VERSION,
    RECORDS_DIRECTORY,
    REQUIRED_FIELDS,
    SUPPORTED_PLATFORMS,
    UNRECORDED,
    ChecklistDefinition,
    ChecklistError,
    ChecklistStep,
    RecordError,
    evaluate,
    parse_record,
    read_checklist,
    read_record,
    render_record,
)

# Aliased under a leading underscore: pytest collects any module-level name
# beginning with `Test` as a test class, and these are the record tooling's
# dataclasses, not tests.
from testrecord import TestRecord as _TestRecord
from testrecord import TestRecordReport as _TestRecordReport
from transform import (
    EXTENSION_NAMESPACE,
    LICENSE_FILENAME,
    MANIFEST_FILENAME,
    PLUGIN_MANIFEST_DEST,
    POWER_LICENSE,
    SKILL_ENTRY_POINT,
    SKILL_REQUIRED_FIELDS,
    TEMPLATE_RELEASE_FIELD,
    license_identifier,
    split_frontmatter,
)

# ---------------------------------------------------------------------------
# Declared paths and repository-walk policy
# ---------------------------------------------------------------------------

#: Artifact B's engine directory, per the design's repository layout (R14 AC2).
ENGINE_DIR = "tools/bootcamp-transform"

#: THE Transformation_Contract. One file, one location (R3 AC1).
CONTRACT_PATH = f"{ENGINE_DIR}/contract.yaml"

#: The five engine scripts the design's repository layout declares, each at
#: `tools/bootcamp-transform/<name>`.
ENGINE_SCRIPTS = (
    "resolve_release.py",  # Version_Resolver (R1)
    "transform.py",  # deterministic transform engine (R3)
    "reconcile.py",  # three-way reconciliation (R5)
    "validate.py",  # Schema_Validator (R13, R8, R11, R12, R2)
    "testrecord.py",  # Test_Checklist record tooling (R6)
)

#: Engine scripts a later task still has to write. The existence check below
#: covers all five declared names — narrowing it would let the design's claim go
#: unasserted — and marks these as expected failures until their task lands.
#: To flip one on, delete its entry here; nothing else changes.
PENDING_ENGINE_SCRIPTS = {
    "reconcile.py": "task 10.1 implements the Reconciler",
    "validate.py": "task 8.1 implements the Schema_Validator",
}

#: Directories that hold no committed source: version control and tool caches.
_SKIPPED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".hypothesis",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "node_modules",
    }
)

#: Machine-readable formats a duplicated rule set could hide in.
_DATA_SUFFIXES = frozenset({".yaml", ".yml", ".json"})

#: Top-level keys that make a document a transformation rule set. Any one of
#: them outside `contract.yaml` is a second copy of rules the engine could read.
CONTRACT_MARKER_KEYS = frozenset(
    {"contractVersion", "substitutionSets", "invariantDiscounts", "rules"}
)

#: The one marker a generated `.build-manifest.json` is allowed to carry, and only
#: there. A Build_Manifest records `contractVersion` as *provenance* — which
#: contract produced this tree — per the design's Build_Manifest data model. It
#: carries no rule, no substitution set, and no discount, and nothing reads it as a
#: contract, so it is not a second copy of the rules. Every other marker still
#: fails there: a manifest that grew a `rules` list would be exactly the
#: duplication this sweep is for.
_MANIFEST_PROVENANCE_KEYS = frozenset({"contractVersion"})

#: A YAML rule entry (`- id: skill-onboarding`) or a bare rule-set key, matched
#: line-anchored. Either shape appearing in an engine source file means the rule
#: set was transcribed into code instead of read from the contract (R3 AC4).
_EMBEDDED_RULE_SET = re.compile(
    r"^\s*(?:-\s*id:\s*\S|(?:rules|substitutionSets|invariantDiscounts):\s*$)",
    re.MULTILINE,
)


def _relative(path: Path) -> str:
    """POSIX repo-relative path, so assertion messages read the same anywhere."""
    return path.relative_to(REPO_ROOT).as_posix()


def _walk_repo() -> Iterator[Path]:
    """Every committed file in the repository, caches and `.git` excluded."""
    stack = [REPO_ROOT]
    while stack:
        for entry in sorted(stack.pop().iterdir()):
            if entry.name in _SKIPPED_DIRS:
                continue
            if entry.is_dir():
                stack.append(entry)
            elif entry.is_file():
                yield entry


def _load_contract() -> dict[str, Any]:
    """Parse the one contract. Its absence is a failure, not a skip."""
    contract_file = REPO_ROOT / CONTRACT_PATH
    assert contract_file.is_file(), f"{CONTRACT_PATH} is missing"
    document = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{CONTRACT_PATH} is not a YAML mapping"
    return document


def _load_data_document(path: Path) -> Any:
    """Parse a data file, or return `None` when it does not parse.

    A malformed document is a different failure with a different owner — hook
    JSON parseability is task 11.7 — so this check does not also report it.
    """
    try:
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError):
        return None


def _contract_rules() -> list[dict[str, Any]]:
    rules = _load_contract().get("rules")
    assert isinstance(rules, list), f"{CONTRACT_PATH} declares no `rules` list"
    return [rule for rule in rules if isinstance(rule, dict)]


# ===========================================================================
# 1. Contract single-sourcing (R3 AC1) — task 3.4
# ===========================================================================


def test_exactly_one_contract_file_exists_in_the_repository():
    """One shared source of mapping rules, at the declared path (R3 AC1)."""
    found = sorted(
        _relative(path)
        for path in _walk_repo()
        if path.stem == "contract" and path.suffix in {".yaml", ".yml"}
    )
    assert found == [CONTRACT_PATH], (
        "the Transformation_Contract must exist exactly once, at "
        f"{CONTRACT_PATH}; found {found}"
    )


def test_no_other_data_file_declares_a_transformation_rule_set():
    """No second machine-readable copy of the rules exists (R3 AC1, AC4).

    Both maintainer skills reference the one contract; that reference is checked
    by task 12.4. What this asserts is the other half: there is nothing else for
    them to reference.
    """
    duplicates: dict[str, list[str]] = {}
    for path in _walk_repo():
        if path.suffix not in _DATA_SUFFIXES or _relative(path) == CONTRACT_PATH:
            continue
        document = _load_data_document(path)
        if not isinstance(document, dict):
            continue
        markers = CONTRACT_MARKER_KEYS
        if path.name == MANIFEST_FILENAME:
            markers = markers - _MANIFEST_PROVENANCE_KEYS
        shared = sorted(markers.intersection(document))
        if shared:
            duplicates[_relative(path)] = shared
    assert duplicates == {}, (
        "these files duplicate Transformation_Contract sections that must live "
        f"only in {CONTRACT_PATH}: {duplicates}"
    )


def test_no_engine_source_file_embeds_the_rule_set():
    """The engine reads the rules; it does not restate them (R3 AC4).

    Scoped to the engine's own sources: the contract is data the engine loads,
    so a rule entry appearing in Python or in a Jinja template would be a second
    place a rule change has to be made.
    """
    engine_root = REPO_ROOT / ENGINE_DIR
    offenders = []
    for path in sorted(engine_root.rglob("*")):
        relative = _relative(path)
        if not path.is_file() or relative == CONTRACT_PATH:
            continue
        if path.suffix not in {".py", ".j2"} or f"{ENGINE_DIR}/tests/" in relative:
            continue
        match = _EMBEDDED_RULE_SET.search(path.read_text(encoding="utf-8"))
        if match:
            offenders.append(f"{relative}: {match.group(0).strip()!r}")
    assert offenders == [], (
        "transformation rules must be read from the contract, not transcribed "
        f"into engine sources: {offenders}"
    )


def test_contract_declares_each_rule_exactly_once():
    """A rule id or source pattern declared twice is a rule set forked in place."""
    ids = [rule.get("id") for rule in _contract_rules()]
    duplicate_ids = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
    assert duplicate_ids == [], f"duplicate rule ids in {CONTRACT_PATH}: {duplicate_ids}"

    sources = [rule["source"] for rule in _contract_rules() if "source" in rule]
    duplicate_sources = sorted({s for s in sources if sources.count(s) > 1})
    assert duplicate_sources == [], (
        f"duplicate rule source patterns in {CONTRACT_PATH}: {duplicate_sources}"
    )


# ===========================================================================
# 2. Engine layout at the declared paths (R14 AC2) — task 3.4
# ===========================================================================


@pytest.mark.parametrize(
    "script",
    [
        pytest.param(
            script,
            marks=(
                [
                    pytest.mark.xfail(
                        reason=PENDING_ENGINE_SCRIPTS[script],
                        strict=False,
                    )
                ]
                if script in PENDING_ENGINE_SCRIPTS
                else []
            ),
        )
        for script in ENGINE_SCRIPTS
    ],
)
def test_declared_engine_script_exists_at_its_declared_path(script):
    """All five engine scripts live under `tools/bootcamp-transform/` (R14 AC2)."""
    path = REPO_ROOT / ENGINE_DIR / script
    assert path.is_file(), f"{ENGINE_DIR}/{script} is missing"
    assert path.read_text(encoding="utf-8").strip(), f"{ENGINE_DIR}/{script} is empty"


def test_the_contract_sits_beside_the_engine_scripts():
    """The engine and the contract it executes ship together (R14 AC2)."""
    assert (REPO_ROOT / CONTRACT_PATH).is_file()
    assert (REPO_ROOT / ENGINE_DIR / "templates").is_dir(), (
        f"{ENGINE_DIR}/templates/ holds the plugin.json, mcp.json, and hook "
        "templates the generate rules render"
    )


# ===========================================================================
# 3. Line-ending normalization (R16 AC8) — task 3.4
# ===========================================================================

GITATTRIBUTES_PATH = ".gitattributes"

#: Paths whose bytes the transform must preserve exactly (R10 AC3), so no
#: line-ending normalization may touch them. `binary` and `-text` both opt a
#: pattern out; `binary` additionally marks it as non-diffable.
UNNORMALIZED_PATTERNS = {"*.png": {"binary", "-text"}, "*.min.js": {"binary", "-text"}}


def _gitattributes_lines() -> list[str]:
    path = REPO_ROOT / GITATTRIBUTES_PATH
    assert path.is_file(), (
        f"{GITATTRIBUTES_PATH} must exist at the repository root: it is where "
        "line-ending normalization is declared (R16 AC8)"
    )
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_gitattributes_declares_lf_line_endings_for_every_checkout():
    """LF survives checkout on every Supported_Platform (R16 AC8).

    Without this, a Windows checkout rewrites text files to CRLF, changing bytes
    the Build_Manifest already hashed and failing every file (R16 AC9).
    """
    lines = _gitattributes_lines()
    normalization = [line for line in lines if line.split()[0] == "*"]
    assert normalization, (
        f"{GITATTRIBUTES_PATH} declares no repository-wide normalization rule"
    )
    assert any("eol=lf" in line for line in normalization), (
        f"the repository-wide rule in {GITATTRIBUTES_PATH} must declare eol=lf; "
        f"found {normalization}"
    )


def test_gitattributes_excludes_binary_and_minified_assets_from_normalization():
    """Byte-for-byte assets are opted out of text conversion (R16 AC8, R10 AC3)."""
    attributes = {line.split()[0]: set(line.split()[1:]) for line in _gitattributes_lines()}
    for pattern, accepted in UNNORMALIZED_PATTERNS.items():
        assert pattern in attributes, (
            f"{GITATTRIBUTES_PATH} must exclude {pattern} from normalization"
        )
        assert attributes[pattern] & accepted, (
            f"{pattern} must be declared with one of {sorted(accepted)} so no "
            f"line-ending transform touches its bytes; found {sorted(attributes[pattern])}"
        )


def test_contract_declares_lf_output_and_points_at_the_committed_gitattributes():
    """The contract is where the normalization policy is declared (R16 AC8)."""
    output = _load_contract().get("output")
    assert isinstance(output, dict), f"{CONTRACT_PATH} declares no `output` section"
    assert output.get("lineEndings") == "lf", (
        "the engine must write LF unconditionally; "
        f"`output.lineEndings` is {output.get('lineEndings')!r}"
    )
    declared = output.get("gitattributes")
    assert declared == GITATTRIBUTES_PATH, (
        f"`output.gitattributes` must name the committed {GITATTRIBUTES_PATH}; "
        f"found {declared!r}"
    )
    assert (REPO_ROOT / declared).is_file(), (
        f"`output.gitattributes` names {declared}, which does not exist"
    )


# ===========================================================================
# 4. Invariant_Discount_Register exclusions (R15 AC6) — task 3.4
# ===========================================================================

#: The near-miss spellings `discount_register()` emits (strategies.py):
#: `inv-052` and `INV-052 ` are the honored invariant under another spelling;
#: `INV-52` is a distinct identifier that reads like it.
NEAR_MISS_SPELLINGS = (
    HONORED_INVARIANT.lower(),
    f"{HONORED_INVARIANT} ",
    "INV-52",
)


def _normalize_invariant_id(raw: object) -> str:
    """Fold case and strip all whitespace, so spelling cannot smuggle an id in."""
    return "".join(str(raw).split()).upper()


def _checked_in_discount_register() -> list[dict[str, Any]]:
    register = _load_contract().get("invariantDiscounts")
    assert isinstance(register, list), (
        f"{CONTRACT_PATH} must declare `invariantDiscounts` as a list "
        "(an empty list means nothing is discounted)"
    )
    return register


def test_invariant_discount_register_excludes_the_honored_invariant():
    """`INV-052` is honored under R16, so it is never discounted (R15 AC6)."""
    target = _normalize_invariant_id(HONORED_INVARIANT)
    offenders = [
        entry.get("invariant")
        for entry in _checked_in_discount_register()
        if isinstance(entry, dict)
        and _normalize_invariant_id(entry.get("invariant")) == target
    ]
    assert offenders == [], (
        f"{HONORED_INVARIANT} must not appear in the Invariant_Discount_Register: "
        "its no-shell-dependency guarantee is preserved by install-time absolute-path "
        "interpreter resolution (R16 AC3, AC4), not discounted. An entry here is "
        f"E_HONORED_INVARIANT_DISCOUNTED and blocks tagging. Found {offenders}"
    )


@pytest.mark.parametrize("spelling", NEAR_MISS_SPELLINGS)
def test_invariant_discount_register_excludes_near_miss_spellings(spelling):
    """A different spelling of `INV-052` is still an `INV-052` entry (R15 AC6).

    `INV-52` is a genuinely different identifier rather than a spelling of the
    honored one; in the checked-in register it can only be a typo for it, so it
    is guarded here. Should a real `INV-52` ever need discounting, this guard is
    the place that decision gets recorded.
    """
    target = _normalize_invariant_id(spelling)
    offenders = [
        entry.get("invariant")
        for entry in _checked_in_discount_register()
        if isinstance(entry, dict)
        and _normalize_invariant_id(entry.get("invariant")) == target
    ]
    assert offenders == [], (
        f"the Invariant_Discount_Register contains {offenders}, which reads as "
        f"the honored invariant {HONORED_INVARIANT} spelled {spelling!r}"
    )

# ===========================================================================
# 5. Hook definitions (R7 AC5, AC9, AC12; D2) — task 11.7
# ===========================================================================
#
# The definitions are authored **once**, at the path below, and the contract's
# `kiro-hooks` rule carries a two-element `dest`: the Tier 2 skill asset
# directory the Hook_Installer reads, and the Tier 3 `dev.kiro/hooks/` directory
# shipped for forward compatibility. A built Power does not exist in this
# repository yet (task 14.1 produces it), and there is deliberately no second
# authored copy, so "the same definition set exists at Tier 2 and Tier 3" is
# asserted **structurally** rather than by diffing two on-disk directories:
#
#   * the contract's `kiro-hooks` rule declares both destinations (test G),
#   * the coverage map's `placement` block declares the same two, tier-labeled,
#     and marks the definitions `authoredOnce` (test H),
#   * no second authored source tree exists for the Tier 3 destination, so the
#     two cannot drift apart at the source (test G), and
#   * every event's `hookDefinitions` names each file at both destinations, with
#     the destination path built from the matching contract `dest` (test I).
#
# The shipped constants (`senzing-bootcamp-` prefix, the two placeholders, the
# shell-construct set, the definition glob) are read by **importing the
# Hook_Installer itself** rather than by restating them here or lifting them
# from the coverage map. That way these tests assert what the installer would
# actually write, which is what R7 AC9 and R16 AC5 are about.

#: Authored `kiro-owned` content root. `transform.py` materializes each rule's
#: `dest` from `<this>/<dest>`, which is why the authored hook directory below
#: mirrors the Tier 2 destination exactly.
KIRO_OWNED_TEMPLATE_ROOT = f"{ENGINE_DIR}/templates/kiro-owned"

#: The contract rule that places the hook definitions (R7 AC5, AC12).
HOOK_RULE_ID = "kiro-hooks"

#: Its two destinations, in contract order: Tier 2 then Tier 3.
TIER2_HOOK_DEST = "skills/bootcamp-onboarding/assets/kiro-hooks/"
TIER3_HOOK_DEST = "dev.kiro/hooks/"
HOOK_DESTS_BY_TIER = {2: TIER2_HOOK_DEST, 3: TIER3_HOOK_DEST}

#: Where the definitions are authored, and the coverage map that describes them.
HOOK_ASSETS_DIR = f"{KIRO_OWNED_TEMPLATE_ROOT}/{TIER2_HOOK_DEST.rstrip('/')}"
COVERAGE_MAP_FILENAME = "hook-parity-coverage.json"
COVERAGE_MAP_PATH = f"{HOOK_ASSETS_DIR}/{COVERAGE_MAP_FILENAME}"

#: The Hook_Installer (task 11.4), imported below for its shipped constants.
INSTALLER_PATH = (
    f"{KIRO_OWNED_TEMPLATE_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py"
)

#: Every Kiro trigger a hook definition may name. A `trigger` outside this set
#: never fires, so the hook would be inert while appearing installed.
KIRO_TRIGGERS = frozenset(
    {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "PreTaskExec",
        "PostTaskExec",
        "PostFileSave",
        "PostFileCreate",
        "PostFileDelete",
        "Stop",
    }
)

#: The design's per-hook parity table, keyed by coverage-map event id:
#: (template event, script). Five rows have a Kiro trigger equivalent; the two
#: below have none, and carry a documented parity gap instead (R7 AC13).
TEMPLATE_HOOK_EVENTS = {
    "session-start": ("SessionStart", "session-start.py"),
    "feedback-capture": ("UserPromptSubmit", "feedback-capture.py"),
    "checkpoint-tick": ("UserPromptSubmit", "checkpoint-tick.py"),
    "write-gate": ("PreToolUse", "write-gate.py"),
    "stop-nudge": ("Stop", "stop-nudge.py"),
    "precompact-recap": ("PreCompact", "precompact-recap.py"),
    "session-end": ("SessionEnd", "session-end.py"),
}

#: Template events Kiro provides no trigger for, so no definition ships at any
#: tier and Tier 1 carries the behavior alone.
EVENTS_WITHOUT_KIRO_TRIGGER = frozenset({"precompact-recap", "session-end"})

#: The shipped definitions, one per template event that has a Kiro equivalent.
SHIPPED_HOOK_FILENAMES = tuple(
    sorted(
        f"senzing-bootcamp-{event}.json"
        for event in TEMPLATE_HOOK_EVENTS
        if event not in EVENTS_WITHOUT_KIRO_TRIGGER
    )
)

#: Interpreter names that must never reach a Hook_Command_String (R16 AC2, AC3).
#: Compared against each token's basename, not searched for in the raw string:
#: `.py` ends every script name, so a bare substring scan for `py` self-reports.
INTERPRETER_BASENAMES = frozenset(
    {
        "python",
        "python3",
        "py",
        "pythonw",
        "python.exe",
        "python3.exe",
        "py.exe",
        "pythonw.exe",
    }
)

#: `python`, `python3`, `python3.exe` as a whole word. `<ABSOLUTE_PYTHON>` does
#: not match: the `_` before `PYTHON` is a word character, so there is no
#: boundary there — the placeholder is not an interpreter name.
_INTERPRETER_WORD = re.compile(r"\bpython\d*(?:\.exe)?\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _installer() -> Any:
    """Import the Hook_Installer as a module and hand back its namespace.

    Loaded by path because it ships inside `templates/kiro-owned/` rather than
    on `sys.path`. It must be registered in `sys.modules` *before*
    `exec_module`: the module declares `from __future__ import annotations` and
    a `@dataclass`, and `dataclasses` resolves the stringized annotations
    through `sys.modules[cls.__module__]`.
    """
    path = REPO_ROOT / INSTALLER_PATH
    assert path.is_file(), f"the Hook_Installer is missing from {INSTALLER_PATH}"
    spec = importlib.util.spec_from_file_location("senzing_bootcamp_install_hooks", path)
    assert spec is not None and spec.loader is not None, f"cannot load {INSTALLER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hook_assets_directory() -> Path:
    directory = REPO_ROOT / HOOK_ASSETS_DIR
    assert directory.is_dir(), (
        f"the hook definitions are authored at {HOOK_ASSETS_DIR}, which mirrors "
        f"the Tier 2 destination {TIER2_HOOK_DEST} of the contract's "
        f"'{HOOK_RULE_ID}' rule; the directory is missing"
    )
    return directory


def _parse_hook_json(filename: str) -> dict[str, Any]:
    """Parse one shipped definition, reporting a parse failure as a failure."""
    path = _hook_assets_directory() / filename
    assert path.is_file(), f"{HOOK_ASSETS_DIR}/{filename} is missing"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        pytest.fail(f"{HOOK_ASSETS_DIR}/{filename} is not valid JSON: {error}")
    assert isinstance(document, dict), (
        f"{HOOK_ASSETS_DIR}/{filename} must be a JSON object of the shape "
        '{"version": "v1", "hooks": [...]}'
    )
    return document


def _shipped_hooks(filename: str) -> list[dict[str, Any]]:
    """The `hooks` entries of one shipped definition."""
    hooks = _parse_hook_json(filename).get("hooks")
    assert isinstance(hooks, list) and hooks, (
        f"{HOOK_ASSETS_DIR}/{filename} carries no non-empty `hooks` list"
    )
    for index, hook in enumerate(hooks):
        assert isinstance(hook, dict), f"{filename}: hooks[{index}] is not a JSON object"
    return hooks


def _load_coverage_map() -> dict[str, Any]:
    path = REPO_ROOT / COVERAGE_MAP_PATH
    assert path.is_file(), f"{COVERAGE_MAP_PATH} is missing"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{COVERAGE_MAP_PATH} is not a JSON object"
    return document


def _coverage_events() -> dict[str, dict[str, Any]]:
    events = _load_coverage_map().get("events")
    assert isinstance(events, list) and events, (
        f"{COVERAGE_MAP_PATH} declares no non-empty `events` array"
    )
    by_id: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        assert isinstance(event, dict), (
            f"{COVERAGE_MAP_PATH}: events[{index}] is not an object"
        )
        event_id = event.get("id")
        assert isinstance(event_id, str) and event_id, (
            f"{COVERAGE_MAP_PATH}: events[{index}] has no `id`"
        )
        assert event_id not in by_id, (
            f"{COVERAGE_MAP_PATH} declares event id {event_id!r} twice; one event "
            "per template hook, so a duplicate hides one of them"
        )
        by_id[event_id] = event
    return by_id


def _hook_rule() -> dict[str, Any]:
    matches = [rule for rule in _contract_rules() if rule.get("id") == HOOK_RULE_ID]
    assert len(matches) == 1, (
        f"{CONTRACT_PATH} must declare exactly one '{HOOK_RULE_ID}' rule; found "
        f"{len(matches)}"
    )
    return matches[0]


def _hook_rule_dests() -> list[str]:
    dest = _hook_rule().get("dest")
    assert isinstance(dest, list), (
        f"the '{HOOK_RULE_ID}' rule must declare `dest` as a two-element list "
        f"(Tier 2 then Tier 3); found {dest!r}"
    )
    return dest


# --- Every hook JSON parses and names a valid Kiro trigger (R7 AC5) --------


@pytest.mark.parametrize("filename", SHIPPED_HOOK_FILENAMES)
def test_every_shipped_hook_definition_parses_in_the_kiro_hook_file_shape(filename):
    """Each definition is `{"version": "v1", "hooks": [...]}` (R7 AC5).

    A definition Kiro cannot parse is worse than an absent one: the Bootcamper
    consented to an install that then enforces nothing.
    """
    document = _parse_hook_json(filename)
    installer = _installer()
    assert document.get("version") == installer.HOOK_SCHEMA_VERSION, (
        f"{filename} declares version {document.get('version')!r}; the "
        f"Hook_Installer resolves {installer.HOOK_SCHEMA_VERSION!r} only"
    )
    for hook in _shipped_hooks(filename):
        assert isinstance(hook.get("name"), str) and hook["name"].strip(), (
            f"{filename}: a hook entry has no `name`"
        )
        action = hook.get("action")
        assert isinstance(action, dict), (
            f"{filename}: {hook['name']} has no `action` object"
        )
        assert action.get("type") == "command", (
            f"{filename}: {hook['name']} action type is {action.get('type')!r}; the "
            "Hook_Installer resolves command actions only"
        )
        assert isinstance(action.get("command"), str) and action["command"].strip(), (
            f"{filename}: {hook['name']} has no `action.command` string"
        )
        assert isinstance(hook.get("timeout"), int) and hook["timeout"] > 0, (
            f"{filename}: {hook['name']} must declare a positive `timeout`; found "
            f"{hook.get('timeout')!r}"
        )


@pytest.mark.parametrize("filename", SHIPPED_HOOK_FILENAMES)
def test_every_shipped_hook_names_a_valid_kiro_trigger(filename):
    """A `trigger` outside Kiro's set never fires (R7 AC5).

    The failure mode this catches is silent: Kiro ignores a trigger it does not
    know, so enforcement looks installed and is absent — exactly the outcome the
    three-tier strategy was written to avoid (D2).
    """
    for hook in _shipped_hooks(filename):
        trigger = hook.get("trigger")
        assert trigger in KIRO_TRIGGERS, (
            f"{filename}: {hook.get('name')} names trigger {trigger!r}, which is "
            f"not a Kiro trigger. Valid triggers: {sorted(KIRO_TRIGGERS)}"
        )


def test_the_coverage_map_declares_a_kiro_mechanism_matcher_for_every_shipped_matcher():
    """A shipped `matcher` is declared in the map, and nowhere else (R7 AC5).

    `write-gate` is the only definition that matches on tool name, and its name
    set is assumption A3 — verified per platform by Test_Checklist step 11. The
    map is where that set is written down, so the two must agree or the checklist
    would verify a pattern the hook does not carry.
    """
    events = _coverage_events()
    for event_id, event in events.items():
        mechanism = event.get("kiroMechanism") or {}
        declared = mechanism.get("matcher")
        for entry in event.get("hookDefinitions") or []:
            filename = entry.get("file")
            if entry.get("tier") != 2:
                continue
            for hook in _shipped_hooks(filename):
                shipped = hook.get("matcher")
                assert shipped == declared, (
                    f"{filename}: {hook.get('name')} declares matcher {shipped!r} "
                    f"but the coverage map declares {declared!r} for event "
                    f"{event_id!r}"
                )


# --- Every installed file name carries the namespace prefix (R7 AC9) ------


def test_the_hook_installer_writes_only_namespace_prefixed_filenames():
    """Every file the installer would write is attributable to the Power (R7 AC9).

    Asserted against the installer's own discovery, not a restated list: the
    glob it selects with, the prefix it enforces, and the files that glob finds
    in the authored directory.
    """
    installer = _installer()
    assets = _hook_assets_directory()

    assert installer.HOOK_FILENAME_PREFIX == "senzing-bootcamp-", (
        "the ownership boundary is the `senzing-bootcamp-` prefix; the installer "
        f"declares {installer.HOOK_FILENAME_PREFIX!r}"
    )
    pattern = installer.load_hook_definition_glob(assets)
    assert pattern.startswith(installer.HOOK_FILENAME_PREFIX), (
        f"the shipped hookDefinitionGlob {pattern!r} does not start with "
        f"{installer.HOOK_FILENAME_PREFIX!r}, so it could select a file the "
        "installer must not write"
    )

    discovered = [
        path.name for path in installer.discover_hook_definitions(assets, pattern)
    ]
    assert discovered == list(SHIPPED_HOOK_FILENAMES), (
        f"the installer would write {discovered} from {HOOK_ASSETS_DIR}; expected "
        f"one definition per template hook event with a Kiro equivalent: "
        f"{list(SHIPPED_HOOK_FILENAMES)}"
    )
    unprefixed = [
        name
        for name in discovered
        if not name.startswith(installer.HOOK_FILENAME_PREFIX)
    ]
    assert unprefixed == [], (
        f"these files would be written into the Workspace_Hooks_Directory without "
        f"the {installer.HOOK_FILENAME_PREFIX!r} prefix, making removal ambiguous "
        f"and a collision with the Bootcamper's own hooks possible: {unprefixed}"
    )


@pytest.mark.parametrize("filename", SHIPPED_HOOK_FILENAMES)
def test_every_shipped_hook_entry_name_carries_the_namespace_prefix(filename):
    """The hook *entries*, not just the files, are attributable (R7 AC9).

    Kiro lists hooks by entry name. An unprefixed entry inside a prefixed file
    reads as the Bootcamper's own hook, so removal by filename would delete
    something they cannot connect to this Power.
    """
    prefix = _installer().HOOK_FILENAME_PREFIX
    offenders = [
        hook.get("name")
        for hook in _shipped_hooks(filename)
        if not str(hook.get("name", "")).startswith(prefix)
    ]
    assert offenders == [], (
        f"{filename}: hook entries without the {prefix!r} prefix: {offenders}"
    )


def test_the_unprefixed_coverage_map_is_never_installed_as_a_hook():
    """The coverage map sits beside the definitions and is not one (R7 AC9).

    It is deliberately unprefixed. That is load-bearing: the prefix *is* the
    glob, so an accidental rename would install a coverage map as a hook.
    """
    installer = _installer()
    assets = _hook_assets_directory()
    assert (assets / COVERAGE_MAP_FILENAME).is_file(), f"{COVERAGE_MAP_PATH} is missing"
    assert not COVERAGE_MAP_FILENAME.startswith(installer.HOOK_FILENAME_PREFIX), (
        f"{COVERAGE_MAP_FILENAME} must not carry the "
        f"{installer.HOOK_FILENAME_PREFIX!r} prefix, or the definition glob would "
        "install it as a hook"
    )
    assert _load_coverage_map().get("isHookDefinition") is False, (
        f"{COVERAGE_MAP_PATH} must declare `isHookDefinition: false`"
    )

    pattern = installer.load_hook_definition_glob(assets)
    selected = [path.name for path in installer.discover_hook_definitions(assets, pattern)]
    assert COVERAGE_MAP_FILENAME not in selected, (
        f"the glob {pattern!r} selects {COVERAGE_MAP_FILENAME}, which is a "
        "coverage map, not a hook definition"
    )

    every_json = sorted(path.name for path in assets.glob("*.json"))
    assert every_json == sorted([*SHIPPED_HOOK_FILENAMES, COVERAGE_MAP_FILENAME]), (
        f"{HOOK_ASSETS_DIR} holds {every_json}; it must hold exactly the shipped "
        f"definitions plus {COVERAGE_MAP_FILENAME}. An extra JSON file here is "
        "either an uncatalogued hook or a second copy of the map"
    )


# --- Commands carry both placeholders and no interpreter name (R16 AC5) ---


@pytest.mark.parametrize("filename", SHIPPED_HOOK_FILENAMES)
def test_every_shipped_command_is_exactly_the_two_declared_placeholders(filename):
    """A shipped command is the placeholder pair and nothing else (R16 AC3, AC5).

    The expected string is built from the coverage map's declared
    `commandStringPolicy.shape`, so the map cannot document one shape while the
    assets carry another. Both placeholders are quoted, which is what makes the
    resolved output correct for a path containing a space (R16 AC4).
    """
    installer = _installer()
    policy = _load_coverage_map().get("commandStringPolicy")
    assert isinstance(policy, dict), f"{COVERAGE_MAP_PATH} declares no commandStringPolicy"
    shape = policy.get("shape")
    assert isinstance(shape, str) and "<script>.py" in shape, (
        f"commandStringPolicy.shape must spell the command with a <script>.py "
        f"placeholder; found {shape!r}"
    )
    assert sorted(policy.get("placeholders") or []) == sorted(
        [installer.PLACEHOLDER_INTERPRETER, installer.PLACEHOLDER_SCRIPTS_DIR]
    ), (
        "commandStringPolicy.placeholders must name exactly the two placeholders "
        f"the installer resolves; found {policy.get('placeholders')!r}"
    )

    for hook in _shipped_hooks(filename):
        command = hook["action"]["command"]
        tokens = installer.tokenize_command(command)
        assert len(tokens) == 2, (
            f"{filename}: {hook['name']} command must be an interpreter followed "
            f"by exactly one script path; it tokenizes to {tokens}"
        )
        assert tokens[0] == installer.PLACEHOLDER_INTERPRETER, (
            f"{filename}: {hook['name']} names {tokens[0]!r} in the interpreter "
            f"position; the shipped asset must name {installer.PLACEHOLDER_INTERPRETER} "
            "so the installer resolves an absolute path there (R16 AC3)"
        )
        script_prefix = installer.PLACEHOLDER_SCRIPTS_DIR + "/"
        assert tokens[1].startswith(script_prefix), (
            f"{filename}: {hook['name']} script path {tokens[1]!r} must begin with "
            f"{script_prefix!r}, or the installer cannot resolve it to the ported "
            "script set"
        )
        script = tokens[1][len(script_prefix) :]
        assert command == shape.replace("<script>.py", script), (
            f"{filename}: {hook['name']} command is {command!r}; the coverage map "
            f"declares the shape {shape!r}"
        )


@pytest.mark.parametrize("filename", SHIPPED_HOOK_FILENAMES)
def test_no_shipped_command_names_an_interpreter_or_a_shell_construct(filename):
    """No interpreter name, no shell construct, in any shipped command (R16 AC5).

    An interpreter name here would survive into the Workspace_Hooks_Directory
    and could resolve to nothing on Windows, or to a Store alias stub (R16 AC2).
    A shell construct would be a parser error under PowerShell 5.1 (INV-167).

    Both placeholders sit inside quoted spans, so the installer's own
    shell-construct scan already ignores their angle brackets — the coverage map's
    validator guidance about stripping the tokens first applies to a scan of the
    raw string, not to this one.
    """
    installer = _installer()
    for hook in _shipped_hooks(filename):
        command = hook["action"]["command"]
        constructs = installer.find_shell_constructs(command)
        assert constructs == (), (
            f"{filename}: {hook['name']} command carries unquoted shell "
            f"construct(s) {list(constructs)}: {command!r}"
        )
        for token in installer.tokenize_command(command):
            basename = re.split(r"[/\\]", token)[-1].lower()
            assert basename not in INTERPRETER_BASENAMES, (
                f"{filename}: {hook['name']} command names the interpreter {token!r}; "
                "only the placeholder may appear, resolved at install time"
            )
        found = _INTERPRETER_WORD.search(command)
        assert found is None, (
            f"{filename}: {hook['name']} command contains the interpreter name "
            f"{found.group(0)!r}: {command!r}"
        )
        assert "${PLUGIN_ROOT}" not in command, (
            f"{filename}: {hook['name']} command relies on ${{PLUGIN_ROOT}} "
            "expansion, which assumption A2 does not grant inside a command string"
        )


# --- The same definition set exists at Tier 2 and Tier 3 (R7 AC5, AC12) ---


def test_the_contract_hook_rule_declares_both_tier_destinations_from_one_source():
    """One authored source, two destinations, no second copy (R7 AC5, AC12).

    This is the structural form of "the same definition set exists at Tier 2 and
    Tier 3": `transform.py` mirrors a `dest` that ships no authored content of
    its own from the first `dest` that does, so a single authored directory
    materializes at both. Asserting the *absence* of a second authored tree is
    the half that keeps them from drifting.
    """
    rule = _hook_rule()
    assert rule.get("kind") == "kiro-owned", (
        f"the '{HOOK_RULE_ID}' rule is hand-authored content with no template "
        f"source; kind is {rule.get('kind')!r}"
    )
    assert rule.get("owner") == "kiro", (
        f"the '{HOOK_RULE_ID}' rule must be owned by kiro so reconciliation "
        f"preserves it; owner is {rule.get('owner')!r}"
    )
    assert _hook_rule_dests() == [TIER2_HOOK_DEST, TIER3_HOOK_DEST], (
        f"the '{HOOK_RULE_ID}' rule must place the definitions at the Tier 2 asset "
        f"directory and the Tier 3 {TIER3_HOOK_DEST} directory, in that order; "
        f"found {_hook_rule_dests()}"
    )

    authored = _hook_assets_directory()
    assert sorted(path.name for path in authored.glob("senzing-bootcamp-*.json")) == list(
        SHIPPED_HOOK_FILENAMES
    ), f"{HOOK_ASSETS_DIR} must hold the authored definition set"

    second_copy = REPO_ROOT / KIRO_OWNED_TEMPLATE_ROOT / TIER3_HOOK_DEST.rstrip("/")
    assert not second_copy.exists(), (
        f"{KIRO_OWNED_TEMPLATE_ROOT}/{TIER3_HOOK_DEST} must not exist: the "
        "definitions are authored once and mirrored to the Tier 3 destination by "
        "the engine. A second authored copy is a set that can drift"
    )


def test_the_coverage_map_placement_matches_the_contract_hook_rule():
    """The map's declared placement is the contract's, restated (R7 AC5, AC12)."""
    placement = _load_coverage_map().get("placement")
    assert isinstance(placement, dict), f"{COVERAGE_MAP_PATH} declares no `placement` block"
    assert placement.get("contractRuleId") == HOOK_RULE_ID, (
        f"placement.contractRuleId must name the rule that does the placing; "
        f"found {placement.get('contractRuleId')!r}"
    )
    assert placement.get("owner") == "kiro"
    assert placement.get("authoredOnce") is True, (
        "placement.authoredOnce must be true: one authored directory, materialized "
        "at both destinations"
    )
    assert placement.get("sourceDirectory") == f"{HOOK_ASSETS_DIR}/", (
        f"placement.sourceDirectory must name the authored directory "
        f"{HOOK_ASSETS_DIR}/; found {placement.get('sourceDirectory')!r}"
    )

    destinations = placement.get("destinations")
    assert isinstance(destinations, list), "placement.destinations must be a list"
    declared = [(entry.get("tier"), entry.get("path")) for entry in destinations]
    assert declared == [(2, TIER2_HOOK_DEST), (3, TIER3_HOOK_DEST)], (
        "placement.destinations must declare the contract's two dests, tier-labeled "
        f"and in contract order; found {declared}"
    )
    assert [path for _, path in declared] == _hook_rule_dests(), (
        f"placement.destinations disagrees with the '{HOOK_RULE_ID}' rule's dest: "
        f"{[path for _, path in declared]} vs {_hook_rule_dests()}"
    )


def test_every_shipped_definition_is_declared_at_both_tier_destinations():
    """Each definition is catalogued at Tier 2 and Tier 3 (R7 AC5, AC12).

    Tier 3 is inert today, so nothing about a running Kiro would notice a
    definition catalogued at one destination and not the other. The catalogue is
    the only place that gap would show.
    """
    claimed: dict[str, set[int]] = {}
    for event_id, event in _coverage_events().items():
        entries = event.get("hookDefinitions") or []
        if not entries:
            continue
        for entry in entries:
            filename = entry.get("file")
            tier = entry.get("tier")
            assert filename in SHIPPED_HOOK_FILENAMES, (
                f"event {event_id!r} names hook definition {filename!r}, which is "
                f"not a shipped definition: {list(SHIPPED_HOOK_FILENAMES)}"
            )
            assert tier in HOOK_DESTS_BY_TIER, (
                f"event {event_id!r} declares {filename} at tier {tier!r}; hook "
                f"definitions exist at tiers {sorted(HOOK_DESTS_BY_TIER)}"
            )
            expected = f"{HOOK_DESTS_BY_TIER[tier]}{filename}"
            assert entry.get("destination") == expected, (
                f"event {event_id!r}: the tier {tier} destination of {filename} must "
                f"be {expected}; found {entry.get('destination')!r}"
            )
            hook_names = [hook["name"] for hook in _shipped_hooks(filename)]
            assert entry.get("hookName") in hook_names, (
                f"event {event_id!r}: hookName {entry.get('hookName')!r} is not a "
                f"hook entry in {filename} ({hook_names})"
            )
            claimed.setdefault(filename, set()).add(tier)

    assert sorted(claimed) == list(SHIPPED_HOOK_FILENAMES), (
        f"every shipped definition must be claimed by an event; catalogued "
        f"{sorted(claimed)}, shipped {list(SHIPPED_HOOK_FILENAMES)}"
    )
    incomplete = {name: sorted(tiers) for name, tiers in claimed.items() if tiers != {2, 3}}
    assert incomplete == {}, (
        "each shipped definition must be declared at both the Tier 2 and the Tier 3 "
        f"destination; these are declared at only some: {incomplete}"
    )


# --- Every template hook event is in the coverage map (R7 AC5, AC12) ------


def test_every_template_hook_event_appears_in_the_coverage_map():
    """The map covers the design's parity table exactly, no more, no fewer."""
    events = _coverage_events()
    assert sorted(events) == sorted(TEMPLATE_HOOK_EVENTS), (
        f"{COVERAGE_MAP_PATH} must carry one event per row of the design's "
        f"per-hook parity table; declared {sorted(events)}, expected "
        f"{sorted(TEMPLATE_HOOK_EVENTS)}"
    )
    for event_id, (template_event, script) in TEMPLATE_HOOK_EVENTS.items():
        event = events[event_id]
        assert event.get("templateEvent") == template_event, (
            f"event {event_id!r} must map template event {template_event!r}; found "
            f"{event.get('templateEvent')!r}"
        )
        assert event.get("script") == script, (
            f"event {event_id!r} must name the template script {script!r}; found "
            f"{event.get('script')!r}"
        )


@pytest.mark.parametrize("event_id", sorted(TEMPLATE_HOOK_EVENTS))
def test_every_coverage_map_event_declares_a_mechanism_and_a_tier(event_id):
    """Each event names how it is delivered and at which tiers (R7 AC5, AC12).

    An event with no mechanism and no tier is a behavior nobody has decided how
    to deliver — the state the coverage map exists to make visible.
    """
    event = _coverage_events()[event_id]

    mechanism = event.get("kiroMechanism")
    assert isinstance(mechanism, dict), f"event {event_id!r} declares no kiroMechanism"
    assert mechanism.get("type") in {"trigger", "none"}, (
        f"event {event_id!r} declares mechanism type {mechanism.get('type')!r}; "
        "expected 'trigger' (a Kiro equivalent exists) or 'none' (it does not)"
    )
    assert isinstance(mechanism.get("canBlock"), bool), (
        f"event {event_id!r} must state whether its mechanism can block"
    )
    assert isinstance(mechanism.get("notes"), str) and mechanism["notes"].strip(), (
        f"event {event_id!r} must explain its mechanism in `notes`"
    )

    tiers = event.get("tiers")
    assert isinstance(tiers, list) and tiers, f"event {event_id!r} declares no tiers"
    assert set(tiers) <= {1, 2, 3}, f"event {event_id!r} declares unknown tiers: {tiers}"
    assert 1 in tiers, (
        f"event {event_id!r} must be delivered at Tier 1: every hook-enforced "
        "behavior is also a skill instruction, so the bootcamp is complete with "
        "zero hook definitions installed (R7 AC4), and Tier 3 is never a "
        "behavior's only delivery path (R7 AC12)"
    )

    assert "parityGap" in event, (
        f"event {event_id!r} must declare `parityGap`, null where parity is full"
    )
    instructions = event.get("skillInstructions")
    assert isinstance(instructions, list) and instructions, (
        f"event {event_id!r} declares no skillInstructions, so its Tier 1 delivery "
        "has no location"
    )


@pytest.mark.parametrize("event_id", sorted(TEMPLATE_HOOK_EVENTS))
def test_a_mechanism_with_a_trigger_ships_definitions_and_one_without_does_not(event_id):
    """Mechanism type and shipped definitions agree (R7 AC5, AC12, AC13).

    `PreCompact` and `SessionEnd` have no Kiro trigger, so they must ship no
    definition at any tier and must carry a documented gap. Everything else has a
    trigger, so it must ship one.
    """
    event = _coverage_events()[event_id]
    mechanism = event.get("kiroMechanism") or {}
    entries = event.get("hookDefinitions") or []

    if event_id in EVENTS_WITHOUT_KIRO_TRIGGER:
        assert mechanism.get("type") == "none", (
            f"event {event_id!r} has no Kiro trigger equivalent, so its mechanism "
            f"type must be 'none'; found {mechanism.get('type')!r}"
        )
        assert mechanism.get("trigger") is None, (
            f"event {event_id!r} must name no Kiro trigger; found "
            f"{mechanism.get('trigger')!r}"
        )
        assert entries == [], (
            f"event {event_id!r} must ship no hook definition, because nothing "
            f"would fire it; found {entries}"
        )
        assert event.get("tiers") == [1], (
            f"event {event_id!r} is delivered by Tier 1 alone; found "
            f"{event.get('tiers')}"
        )
        assert isinstance(event.get("parityGap"), dict), (
            f"event {event_id!r} must document its parity gap (R7 AC13); "
            f"parityGap is {event.get('parityGap')!r}"
        )
        return

    assert mechanism.get("type") == "trigger", (
        f"event {event_id!r} has a Kiro equivalent, so its mechanism type must be "
        f"'trigger'; found {mechanism.get('type')!r}"
    )
    assert mechanism.get("trigger") in KIRO_TRIGGERS, (
        f"event {event_id!r} names Kiro trigger {mechanism.get('trigger')!r}, which "
        f"is not a Kiro trigger. Valid triggers: {sorted(KIRO_TRIGGERS)}"
    )
    assert entries, f"event {event_id!r} has a Kiro trigger but ships no definition"

    triggers = {
        hook.get("trigger")
        for entry in entries
        for hook in _shipped_hooks(entry["file"])
    }
    assert triggers == {mechanism["trigger"]}, (
        f"event {event_id!r} declares Kiro trigger {mechanism['trigger']!r} but its "
        f"shipped definitions carry {sorted(triggers)}"
    )
    if mechanism.get("blockingRequired") and not mechanism.get("canBlock"):
        assert isinstance(event.get("parityGap"), dict), (
            f"event {event_id!r} needs to block and its Kiro mechanism cannot, so "
            "the partial parity must be documented (R7 AC14)"
        )


def test_the_generator_hook_script_names_match_the_events_that_ship_a_definition():
    """`strategies.HOOK_SCRIPT_NAMES` is the set that has a Kiro equivalent.

    The generator builds Hook_Command_Strings from these names. If the shipped
    set gained or lost a script, property coverage would silently target a script
    nothing ships.
    """
    with_definitions = {
        event["script"]
        for event in _coverage_events().values()
        if event.get("hookDefinitions")
    }
    assert set(HOOK_SCRIPT_NAMES) == with_definitions, (
        "strategies.HOOK_SCRIPT_NAMES must be exactly the template scripts a "
        f"shipped hook definition invokes; generator has {sorted(HOOK_SCRIPT_NAMES)}, "
        f"coverage map has {sorted(with_definitions)}"
    )

# ===========================================================================
# 6. Maintainer tooling placement (R3 AC1, R14 AC2) — task 12.4
# ===========================================================================
#
# Artifact B is two pieces in two places, and the split is deliberate: the engine
# is a repo-local build tool under `tools/`, while the two skills that drive it
# are packaged as an installable Power under `powers/`. Section 2 asserts the
# engine half. This section asserts the skill half, plus the claim that joins
# them — both skills reach the **same** contract, by reference.
#
# Section 1 already asserts the other half of R3 AC1: one contract file exists,
# no data file holds a second copy of the rules, and no engine source transcribes
# them. What is left for a skill to get wrong is naming a *different* path, or
# restating a rule inline so a contract edit no longer reaches this path — both
# checked below.
#
# Deliberately not asserted here: each skill links to `docs/test-checklist.md`,
# whose structure is task 13.4's to check. A blanket "every relative link
# resolves" test over these skills would quietly make that file's existence this
# task's fact.

#: Artifact B's skill half, per the design's repository layout (R14 AC2).
MAINTAINER_POWER_DIR = "powers/senzing-bootcamp-maintainer"
MAINTAINER_PLUGIN_PATH = f"{MAINTAINER_POWER_DIR}/plugin.json"
MAINTAINER_SKILLS_DIR = f"{MAINTAINER_POWER_DIR}/skills"

#: The Power's `name`, which is also the directory that contains its manifest.
MAINTAINER_POWER_NAME = MAINTAINER_POWER_DIR.rsplit("/", 1)[-1]

#: The maintainer skills, each at `<skills>/<name>/SKILL.md`, and the trigger
#: phrase the design declares for it. The phrase has to appear in the skill's
#: `description`: that is the text a Maintainer's statement is matched against, so
#: a description missing it is a skill with no way to be invoked (R8 AC6).
#:
#: `publish-bootcamp-power` is the third, and it is a different kind of skill from the
#: other two. They produce the Power; it moves an already-produced Power into
#: `Senzing/senzing-bootcamp-kiro-power`, where bootcampers install from. It therefore
#: drives `publication.yaml` rather than `contract.yaml`, which is why the contract-metadata
#: assertions below read the key out of each skill's own frontmatter instead of assuming one
#: shared value.
MAINTAINER_TRIGGER_PHRASES = {
    "create-bootcamp-power": "create the senzing bootcamp power",
    "update-bootcamp-power": "update the senzing bootcamp power",
    "publish-bootcamp-power": "publish the senzing bootcamp power",
}

#: The two skills that drive the Transformation_Contract. R3 AC1's single-sourcing is a
#: statement about *these* — create and update must not be able to diverge, because they
#: produce the same artifact from the same input. It is not a statement that every file in
#: the maintainer Power names `contract.yaml`.
TRANSFORMATION_SKILLS = ("create-bootcamp-power", "update-bootcamp-power")

#: The publication half: one skill, one contract, single-sourced the same way and for the
#: same reason. It is separate because the two contracts answer different questions — what a
#: template file becomes, versus what differs between this repository and the public one —
#: and collapsing them would put publication policy in the path of every rebuild.
PUBLICATION_SKILL = "publish-bootcamp-power"
PUBLICATION_CONTRACT_PATH = f"{ENGINE_DIR}/publication.yaml"

#: Where each maintainer skill records the contract it drives, under `metadata`.
SKILL_CONTRACT_METADATA_KEY = "contract"

#: A `contract.yaml` mention that carries a path, in prose or in a markdown link
#: target. Bare `contract.yaml` names no location and so is not checked.
_CONTRACT_MENTION = re.compile(r"[\w.\-/]*/contract\.ya?ml")

#: A markdown inline link target.
_MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _maintainer_skill_directory(skill: str) -> Path:
    return REPO_ROOT / MAINTAINER_SKILLS_DIR / skill


def _maintainer_skill_file(skill: str) -> Path:
    path = _maintainer_skill_directory(skill) / SKILL_ENTRY_POINT
    assert path.is_file(), f"{MAINTAINER_SKILLS_DIR}/{skill}/{SKILL_ENTRY_POINT} is missing"
    return path


@lru_cache(maxsize=None)
def _maintainer_skill_frontmatter(skill: str) -> dict[str, Any]:
    """The skill's YAML frontmatter as a mapping. No block is a failure."""
    block, _ = split_frontmatter(_maintainer_skill_file(skill).read_text(encoding="utf-8"))
    assert block is not None, (
        f"{MAINTAINER_SKILLS_DIR}/{skill}/{SKILL_ENTRY_POINT} carries no YAML "
        "frontmatter block, so Kiro has no name, description, or license for it"
    )
    document = yaml.safe_load(block)
    assert isinstance(document, dict), (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: frontmatter is not a YAML mapping"
    )
    return document


def _maintainer_plugin_manifest() -> dict[str, Any]:
    path = REPO_ROOT / MAINTAINER_PLUGIN_PATH
    assert path.is_file(), f"{MAINTAINER_PLUGIN_PATH} is missing"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{MAINTAINER_PLUGIN_PATH} is not a JSON object"
    return document


def _resolve_contract_mention(source: Path, mention: str) -> Path:
    """Where a mention points: file-relative when it is a `../` link, else repo-relative."""
    base = source.parent if mention.startswith(("./", "../")) else REPO_ROOT
    return (base / mention).resolve()


def _distinctive_rule_source_patterns() -> list[str]:
    """Contract rule `source` patterns distinctive enough to scan prose for.

    A glob or a dotfile path does not occur in English by accident, so finding one
    verbatim in a skill means a mapping rule was transcribed out of the contract.
    A source that is neither is skipped rather than reported: matching a plain
    word would fire on ordinary sentences and the check would stop meaning
    anything.
    """
    return sorted(
        {
            source
            for rule in _contract_rules()
            if isinstance(source := rule.get("source"), str)
            and ("*" in source or source.startswith("."))
        }
    )


# --- The skills exist where the design says they do (R14 AC2) --------------


@pytest.mark.parametrize("skill", sorted(MAINTAINER_TRIGGER_PHRASES))
def test_every_maintainer_skill_exists_at_its_declared_path(skill):
    """Each maintainer skill is at `<power>/skills/<name>/SKILL.md` (R14 AC2).

    The path is not incidental: Kiro discovers a Power's skills by directory, and
    the frontmatter rule that `name` equals the containing directory ties the
    declared identity to this location.
    """
    directory = _maintainer_skill_directory(skill)
    assert directory.is_dir(), f"{MAINTAINER_SKILLS_DIR}/{skill}/ is missing"
    entry_point = _maintainer_skill_file(skill)
    assert entry_point.read_text(encoding="utf-8").strip(), (
        f"{MAINTAINER_SKILLS_DIR}/{skill}/{SKILL_ENTRY_POINT} is empty"
    )


def test_the_maintainer_power_holds_its_manifest_and_exactly_the_declared_skills():
    """Artifact B's skill half is a manifest plus its declared skills, no more (R14 AC2).

    An extra skill directory here is maintainer tooling nothing declares, and a
    stray file in `skills/` is content Kiro would try to read as a skill.
    """
    assert (REPO_ROOT / MAINTAINER_PLUGIN_PATH).is_file(), (
        f"{MAINTAINER_PLUGIN_PATH} is missing, so the two skills are not packaged "
        "as an installable Power"
    )
    skills_root = REPO_ROOT / MAINTAINER_SKILLS_DIR
    assert skills_root.is_dir(), f"{MAINTAINER_SKILLS_DIR}/ is missing"
    entries = sorted(entry.name for entry in skills_root.iterdir())
    assert entries == sorted(MAINTAINER_TRIGGER_PHRASES), (
        f"{MAINTAINER_SKILLS_DIR}/ holds {entries}; the design declares exactly "
        f"{sorted(MAINTAINER_TRIGGER_PHRASES)}"
    )
    non_directories = [name for name in entries if not (skills_root / name).is_dir()]
    assert non_directories == [], (
        f"{MAINTAINER_SKILLS_DIR}/ must hold skill directories only; found "
        f"{non_directories}"
    )


# --- Both skills reference the one contract, and restate none of it (R3 AC1) ---


@pytest.mark.parametrize("skill", sorted(TRANSFORMATION_SKILLS))
def test_every_maintainer_skill_references_the_one_contract_at_the_declared_path(skill):
    """Each skill names, and links to, `tools/bootcamp-transform/contract.yaml` (R3 AC1).

    Three things together make the reference real rather than decorative: the
    frontmatter records the path a reader can act on, a markdown link resolves to
    the file that is actually on disk, and no mention anywhere in the skill names
    a different one. The last is what would otherwise let a second contract come
    into being unnoticed.
    """
    metadata = _maintainer_skill_frontmatter(skill).get("metadata")
    assert isinstance(metadata, dict), (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: frontmatter declares no `metadata` block"
    )
    assert metadata.get(SKILL_CONTRACT_METADATA_KEY) == CONTRACT_PATH, (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: "
        f"`metadata.{SKILL_CONTRACT_METADATA_KEY}` must name the one contract at "
        f"{CONTRACT_PATH}; found "
        f"{metadata.get(SKILL_CONTRACT_METADATA_KEY)!r}"
    )

    entry_point = _maintainer_skill_file(skill)
    text = entry_point.read_text(encoding="utf-8")
    contract_file = (REPO_ROOT / CONTRACT_PATH).resolve()

    linked = [
        target
        for target in _MARKDOWN_LINK.findall(text)
        if _CONTRACT_MENTION.fullmatch(target)
    ]
    assert linked, (
        f"{MAINTAINER_SKILLS_DIR}/{skill} must link to {CONTRACT_PATH}, so the "
        "rules it applies are one click away and are read there rather than here"
    )
    unresolved = [
        target
        for target in linked
        if _resolve_contract_mention(entry_point, target) != contract_file
    ]
    assert unresolved == [], (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: these contract links do not resolve to "
        f"{CONTRACT_PATH}: {unresolved}"
    )

    misdirected = sorted(
        {
            mention
            for mention in _CONTRACT_MENTION.findall(text)
            if _resolve_contract_mention(entry_point, mention) != contract_file
        }
    )
    assert misdirected == [], (
        f"{MAINTAINER_SKILLS_DIR}/{skill} mentions {misdirected}, which is not the "
        f"single shared contract at {CONTRACT_PATH}. Both maintainer skills must "
        "reach the same one, or create and update can diverge"
    )


def test_the_maintainer_manifest_and_both_skills_name_one_and_the_same_contract():
    """Every contract declaration in the Power collapses to one path (R3 AC1).

    Agreement is the point. Three declarations that agree are a reference; three
    that could disagree are the beginning of two rule sets.
    """
    extensions = _maintainer_plugin_manifest().get("extensions") or {}
    namespace = extensions.get(EXTENSION_NAMESPACE)
    assert isinstance(namespace, dict), (
        f"{MAINTAINER_PLUGIN_PATH} must record its extension data under the "
        f"reverse-domain namespace {EXTENSION_NAMESPACE!r}"
    )

    declared = {
        MAINTAINER_PLUGIN_PATH: namespace.get(SKILL_CONTRACT_METADATA_KEY),
        **{
            f"{MAINTAINER_SKILLS_DIR}/{skill}": (
                _maintainer_skill_frontmatter(skill).get("metadata") or {}
            ).get(SKILL_CONTRACT_METADATA_KEY)
            for skill in sorted(TRANSFORMATION_SKILLS)
        },
    }
    assert set(declared.values()) == {CONTRACT_PATH}, (
        "the maintainer Power must declare exactly one contract path, "
        f"{CONTRACT_PATH}; found {declared}"
    )
    assert (REPO_ROOT / CONTRACT_PATH).is_file(), (
        f"every maintainer declaration names {CONTRACT_PATH}, which does not exist"
    )


def test_the_publish_skill_names_the_one_publication_contract_and_the_manifest_agrees():
    """The publication half is single-sourced too, and at its own path.

    The same argument as R3 AC1, applied to the other contract: if the publication
    adaptations had more than one home, the set applied at release time and the set
    written down would drift, and the symptom would be a development-repository
    reference appearing in the public repository — which is the one thing
    `publication.yaml` exists to prevent.

    The manifest declares it under its own key rather than reusing `contract`, so the
    single-contract assertion above stays a statement about the transformation rules.
    """
    frontmatter = _maintainer_skill_frontmatter(PUBLICATION_SKILL)
    metadata = frontmatter.get("metadata")
    assert isinstance(metadata, dict), (
        f"{MAINTAINER_SKILLS_DIR}/{PUBLICATION_SKILL}: frontmatter declares no `metadata` block"
    )
    assert metadata.get(SKILL_CONTRACT_METADATA_KEY) == PUBLICATION_CONTRACT_PATH, (
        f"{MAINTAINER_SKILLS_DIR}/{PUBLICATION_SKILL}: "
        f"`metadata.{SKILL_CONTRACT_METADATA_KEY}` must name {PUBLICATION_CONTRACT_PATH}; "
        f"found {metadata.get(SKILL_CONTRACT_METADATA_KEY)!r}"
    )

    namespace = (_maintainer_plugin_manifest().get("extensions") or {}).get(EXTENSION_NAMESPACE)
    assert isinstance(namespace, dict)
    assert namespace.get("publicationContract") == PUBLICATION_CONTRACT_PATH, (
        f"{MAINTAINER_PLUGIN_PATH} must record `publicationContract` as "
        f"{PUBLICATION_CONTRACT_PATH}; found {namespace.get('publicationContract')!r}"
    )
    assert (REPO_ROOT / PUBLICATION_CONTRACT_PATH).is_file(), (
        f"the publish skill and the manifest both name {PUBLICATION_CONTRACT_PATH}, "
        "which does not exist"
    )

    # The skill links to the contract, so the adaptations are one click away and are
    # read there rather than paraphrased here.
    text = _maintainer_skill_file(PUBLICATION_SKILL).read_text(encoding="utf-8")
    assert "publication.yaml" in text, (
        f"{MAINTAINER_SKILLS_DIR}/{PUBLICATION_SKILL} must reference publication.yaml"
    )


@pytest.mark.parametrize("skill", sorted(MAINTAINER_TRIGGER_PHRASES))
def test_no_maintainer_skill_restates_the_transformation_rules(skill):
    """The skills reference the rules; they do not carry them (R3 AC1, AC4).

    Both halves of R3 AC1 have to hold for a rule change to be a one-place edit:
    the contract is single-sourced (section 1), and the consumers read it rather
    than paraphrase it. A rule entry or a source glob written into a skill is a
    second place the change has to be made — and the place most likely to be
    missed, because nothing executes it.
    """
    text = _maintainer_skill_file(skill).read_text(encoding="utf-8")

    embedded = _EMBEDDED_RULE_SET.search(text)
    assert embedded is None, (
        f"{MAINTAINER_SKILLS_DIR}/{skill} declares a transformation rule set "
        f"({embedded.group(0).strip()!r} at offset {embedded.start()}); the rules "
        f"live only in {CONTRACT_PATH}"
    )

    patterns = _distinctive_rule_source_patterns()
    assert patterns, (
        f"{CONTRACT_PATH} declares no glob or dotfile rule source, so this check "
        "would pass vacuously"
    )
    transcribed = [pattern for pattern in patterns if pattern in text]
    assert transcribed == [], (
        f"{MAINTAINER_SKILLS_DIR}/{skill} restates these contract rule source "
        f"patterns verbatim: {transcribed}. Name the rule by its id instead; the "
        "pattern itself is the contract's to change"
    )


# --- The Power is Agent Plugins v1.0.0, Apache-2.0 (R14 AC2, AC3) ----------


def test_the_maintainer_plugin_manifest_conforms_to_the_agent_plugins_plugin_schema():
    """`plugin.json` validates against the vendored v1.0.0 plugin schema (R14 AC2).

    Checked against the schema rather than a hand-written field list, for the same
    reason the Schema_Validator does: a paraphrase of the schema is a second
    authority that can drift from it. `name` is additionally required to equal the
    containing directory, which is what makes the Power's declared identity and
    its location the same fact.
    """
    document = _maintainer_plugin_manifest()
    errors = sorted(
        Draft202012Validator(PLUGIN_SCHEMA).iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )
    assert errors == [], (
        f"{MAINTAINER_PLUGIN_PATH} does not conform to Agent Plugins "
        f"{AGENT_PLUGINS_VERSION}: "
        + "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
    )
    assert document.get("$schema") == PLUGIN_SCHEMA_ID, (
        f"{MAINTAINER_PLUGIN_PATH} must declare the v{AGENT_PLUGINS_VERSION} plugin "
        f"schema {PLUGIN_SCHEMA_ID}; found {document.get('$schema')!r}"
    )
    assert document.get("name") == MAINTAINER_POWER_NAME, (
        f"{MAINTAINER_PLUGIN_PATH} declares name {document.get('name')!r}, which "
        f"must equal its containing directory {MAINTAINER_POWER_NAME!r}"
    )
    for field in ("version", "description"):
        value = document.get(field)
        assert isinstance(value, str) and value.strip(), (
            f"{MAINTAINER_PLUGIN_PATH} must declare a non-blank {field}; found "
            f"{value!r}"
        )


def test_the_maintainer_power_declares_apache_2_0_wherever_it_declares_a_license():
    """One license identifier, in the manifest, both skills, and at the root (R14 AC3).

    `POWER_LICENSE` is the single constant both artifacts declare, so this reads
    the repository's own `LICENSE` rather than the string `"Apache-2.0"`: a
    declaration the root license does not back is a claim, not a license.
    """
    declared = {
        MAINTAINER_PLUGIN_PATH: _maintainer_plugin_manifest().get("license"),
        **{
            f"{MAINTAINER_SKILLS_DIR}/{skill}": _maintainer_skill_frontmatter(skill).get(
                "license"
            )
            for skill in sorted(MAINTAINER_TRIGGER_PHRASES)
        },
    }
    assert set(declared.values()) == {POWER_LICENSE}, (
        f"every license declaration in the maintainer Power must be "
        f"{POWER_LICENSE!r}; found {declared}"
    )

    root_license = REPO_ROOT / LICENSE_FILENAME
    assert root_license.is_file(), (
        f"the repository root {LICENSE_FILENAME} is missing, so there is nothing "
        f"for the declared {POWER_LICENSE!r} to match"
    )
    identifier = license_identifier(root_license.read_text(encoding="utf-8"))
    assert identifier == POWER_LICENSE, (
        f"the maintainer Power declares {POWER_LICENSE!r} but the repository root "
        f"{LICENSE_FILENAME} declares {identifier!r}"
    )


# --- Frontmatter satisfies the rules the validator enforces (R8 AC5, AC6) ---


@pytest.mark.parametrize("skill", sorted(MAINTAINER_TRIGGER_PHRASES))
def test_every_maintainer_skill_frontmatter_satisfies_the_frontmatter_rules(skill):
    """`name`, `description`, `license`: present, non-blank, and correct (R8 AC5, AC6).

    The same four rules the Schema_Validator applies to every produced `SKILL.md`,
    applied here to the two hand-authored ones. Nothing in the pipeline generates
    these, so nothing else would catch a `name` that stopped matching its
    directory after a rename, or a description edited past the cap.
    """
    frontmatter = _maintainer_skill_frontmatter(skill)

    missing = [field for field in SKILL_REQUIRED_FIELDS if field not in frontmatter]
    assert missing == [], (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: frontmatter is missing {missing}; all of "
        f"{list(SKILL_REQUIRED_FIELDS)} are required"
    )
    blank = [
        field
        for field in SKILL_REQUIRED_FIELDS
        if not isinstance(frontmatter[field], str) or not frontmatter[field].strip()
    ]
    assert blank == [], (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: these frontmatter fields are blank or "
        f"not strings: {blank}"
    )

    assert frontmatter["name"] == skill, (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: frontmatter name is "
        f"{frontmatter['name']!r}; it must equal the containing directory {skill!r}"
    )

    description = frontmatter["description"]
    assert len(description) <= MAX_DESCRIPTION_LENGTH, (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: description is {len(description)} "
        f"characters, over the {MAX_DESCRIPTION_LENGTH}-character cap"
    )
    phrase = MAINTAINER_TRIGGER_PHRASES[skill]
    assert phrase in description, (
        f"{MAINTAINER_SKILLS_DIR}/{skill}: description must contain the declared "
        f"trigger phrase {phrase!r}, which is the only text a Maintainer's "
        f"statement is matched against; found {description!r}"
    )


def test_the_two_maintainer_trigger_phrases_stay_distinct():
    """Neither description carries the other skill's trigger phrase (R8 AC6).

    Create replaces `powers/senzing-bootcamp/` wholesale and update preserves
    every local adaptation, so a statement that matches both is the one ambiguity
    here that can cost work.
    """
    descriptions = {
        skill: _maintainer_skill_frontmatter(skill)["description"]
        for skill in sorted(MAINTAINER_TRIGGER_PHRASES)
    }
    crossed = {
        skill: other
        for skill, description in descriptions.items()
        for other, phrase in MAINTAINER_TRIGGER_PHRASES.items()
        if other != skill and phrase in description
    }
    assert crossed == {}, (
        "each maintainer skill's description must carry only its own trigger "
        f"phrase; these carry another skill's: {crossed}"
    )

# ===========================================================================
# 7. Test_Checklist shape (R6 AC1, AC4, AC5, AC12, AC13) — task 13.4
# ===========================================================================
#
# `docs/test-checklist.md` is read by a person *and* by a machine: `testrecord.py`
# parses it as the checklist **definition** and emits `docs/test-records/<version>.md`
# from it, and the checklist's own "How this file is parsed" section names this test
# file as the other reader. So these tests parse it with **that** parser rather than
# a second one written here. A private copy of the grammar could pass while the
# tooling that actually emits records failed on the same file — which is the whole
# failure mode worth catching, since a definition the tooling misreads produces a
# record with a hole in it, and a hole is what the gate exists to find.
#
# Already guaranteed by the parser, and therefore not restated below: the grammar
# itself, the required field set per step, `Platform cells` on exactly
# `PER_PLATFORM_STEPS` carrying exactly the `SUPPORTED_PLATFORMS`, and the
# 1..`CHECKLIST_STEP_COUNT` numbering. A `ChecklistError` from any of those is
# reported here as a failure of the *committed* file, which is what makes the
# parse itself the first test.
#
# What is left, and what this section asserts, is that the steps the parser accepts
# are the steps R6 requires: one step per fact the criteria name, exactly one each,
# each carrying a recording slot, with the 16-row activation inventory and the
# nine-cell platform matrix intact. A grammatically perfect checklist missing the
# fresh-session step is a gate that verifies less than R6 AC1 says it does.

#: The Test_Checklist definition, at the path the design's repository layout
#: declares for it (R6 AC1).
CHECKLIST_PATH = "docs/test-checklist.md"

#: Where the ported skill inventory comes from. The resolved Template_Release is
#: not present in this repository, so the ported half of the 16-row activation
#: table cannot be derived from it here: at release `0.5.1` it is nine module
#: skills (`00`…`07`, `module-03b` among them) plus `bootcamp-onboarding`,
#: `bootcamp-preparation`, and `graduation` — twelve in all (design D1). The
#: checklist says its rows *are* the inventory and are edited when a release
#: changes it (R7 AC1, AC2), so these two numbers are what "one row per skill"
#: means for the committed file; the four non-ported skills are derived from the
#: contract instead of counted here.
PORTED_MODULE_SKILL_COUNT = 9
PORTED_SKILL_COUNT = 12

#: A module row's cell key: `module-00` … `module-07`, `module-03b` among them.
#: The full directory name comes from the resolved Template_Release, which is why
#: the row carries the short key and the Maintainer records the resolved name.
_MODULE_CELL_KEY = re.compile(r"^module-\d{2}[a-z]?$")

#: A contract `dest` that creates a skill directory in the Power: exactly
#: `skills/<name>/`. Excludes the nested asset and script dests of the other
#: `kiro-owned` rules, which place content *inside* a skill rather than a skill.
_POWER_SKILL_DEST = re.compile(r"^skills/(?P<name>[^/]+)/$")

#: The trigger phrase a skill's own `description` quotes — the text the checklist
#: tells a Maintainer to state, and the only text a Bootcamper statement is
#: matched against (R8 AC6).
_QUOTED_TRIGGER_PHRASE = re.compile(r"says\s+'(?P<phrase>[^']+)'")

#: A `Do:` field's first numbered action. The checklist's parse contract says
#: `Do` is "the actions, as a numbered list"; a step whose actions are prose is
#: a step two Maintainers can perform differently.
_FIRST_NUMBERED_ACTION = re.compile(r"^\s*1\.\s+\S")

#: A requirement citation, as a `Verifies:` field spells one.
_REQUIREMENT_CITATION = re.compile(r"\bR\d+\b")

#: The steps R6 names, each keyed by the fact it must establish and matched
#: against the step's own **title** — the step's claim about itself. Each must be
#: claimed by exactly one step: two steps verifying one fact let a record pass
#: one and fail the other while the criterion reads as covered, and none means
#: the gate is silent about it.
#:
#: `per_platform` is the R6 AC12 half — the install step, the hook-firing step,
#: and the ported-script step each carry one cell per Supported_Platform, and no
#: other step does. `number` is pinned only where the tooling depends on the
#: number itself; everything else is located by what it verifies, because step
#: numbers are stable but they are not the point.
REQUIRED_STEPS: dict[str, dict[str, Any]] = {
    "add-custom-power": {
        "criterion": "R6 AC1, AC12",
        "title": re.compile(r"Add Custom Power", re.IGNORECASE),
        "phrases": ("Add Custom Power",),
        "per_platform": True,
        "number": None,
    },
    "fresh-chat-session": {
        "criterion": "R6 AC1",
        "title": re.compile(r"fresh chat session", re.IGNORECASE),
        # R6 AC1 defines a fresh session parenthetically, and the definition is
        # the whole content of the step: a resumed or compacted session would
        # pass a "new session" check while proving nothing about a first one.
        "phrases": ("no prior conversation history",),
        "per_platform": False,
        "number": None,
    },
    "mcp-connectivity": {
        "criterion": "R6 AC4",
        "title": re.compile(r"MCP server connects", re.IGNORECASE),
        "phrases": ("streamable-http",),
        "per_platform": False,
        "number": None,
    },
    "mcp-tool-call": {
        "criterion": "R6 AC4",
        "title": re.compile(
            r"MCP tool call returns a successful response", re.IGNORECASE
        ),
        "phrases": (),
        "per_platform": False,
        "number": None,
    },
    "skill-activation": {
        "criterion": "R6 AC5, R9 AC4",
        "title": re.compile(r"activates from its own trigger phrase", re.IGNORECASE),
        "phrases": (),
        "per_platform": False,
        "number": None,
    },
    "hook-firing": {
        "criterion": "R6 AC8, AC12",
        "title": re.compile(r"fires on its declared trigger", re.IGNORECASE),
        "phrases": (),
        "per_platform": True,
        "number": None,
    },
    "ported-scripts": {
        "criterion": "R6 AC12, R10",
        "title": re.compile(r"Every ported script runs", re.IGNORECASE),
        "phrases": ("${CLAUDE_PLUGIN_ROOT}",),
        "per_platform": True,
        "number": None,
    },
    "per-platform-matrix": {
        "criterion": "R6 AC12, R16 AC1",
        "title": re.compile(r"per-platform matrix", re.IGNORECASE),
        # The matrix step reads the nine cells back; it does not carry them, or
        # it would be a fourth per-platform step.
        "phrases": ("nine",),
        "per_platform": False,
        "number": MATRIX_STEP,
    },
    "space-in-path": {
        "criterion": "R6 AC13, R16 AC4",
        "title": re.compile(r"\bspace\b.*\bpath\b", re.IGNORECASE),
        # Quoting is the mechanism R16 AC4 requires, so the step has to look at
        # it rather than only at whether the hook happened to fire.
        "phrases": ("quoted",),
        "per_platform": False,
        "number": None,
    },
}


@lru_cache(maxsize=1)
def _checklist() -> ChecklistDefinition:
    """The committed Test_Checklist, parsed by the tooling that emits records.

    A parse failure is reported as a failure of `docs/test-checklist.md`, not of
    the parser: the file is the definition, and the grammar it fails is the one
    it documents in its own "How this file is parsed" section.
    """
    path = REPO_ROOT / CHECKLIST_PATH
    assert path.is_file(), (
        f"{CHECKLIST_PATH} is missing; it is the Test_Checklist definition every "
        "record is emitted from (R6 AC1)"
    )
    try:
        return read_checklist(path)
    except ChecklistError as error:
        pytest.fail(
            f"{CHECKLIST_PATH} does not satisfy the grammar it documents, so "
            f"testrecord.py cannot emit a record from it: {error}"
        )


def _step_text(step: ChecklistStep) -> str:
    """One step's whole authored text: its title and every field it carries."""
    return "\n".join([step.title, *step.fields.values()])


def _the_step(marker: str) -> ChecklistStep:
    """The one step whose title matches `REQUIRED_STEPS[marker]`."""
    declared = REQUIRED_STEPS[marker]
    pattern = declared["title"]
    matches = [step for step in _checklist().steps if pattern.search(step.title)]
    assert len(matches) == 1, (
        f"exactly one Test_Checklist step must verify {marker!r} "
        f"({declared['criterion']}); {len(matches)} step title(s) match "
        f"{pattern.pattern!r}: {[step.number for step in matches]}"
    )
    return matches[0]


def _activation_step() -> ChecklistStep:
    """The one step that carries activation cells (R6 AC5)."""
    steps = [step for step in _checklist().steps if step.activation_cells]
    assert len(steps) == 1, (
        "exactly one Test_Checklist step carries `Activation cells`, which are "
        "the per-skill trigger-phrase inventory R6 AC5 requires; found "
        f"{[step.number for step in steps]}"
    )
    return steps[0]


def _fixed_ported_skill_names() -> list[str]:
    """Ported skill directories the contract places at a fixed `dest`.

    The `skills-modules` rule places `skills/{skillName}/`, resolved from the
    Template_Release rather than written in the contract, so the module rows are
    checked by key shape and count instead of by name.
    """
    names = [
        dest.strip("/").rsplit("/", 1)[-1]
        for rule in _contract_rules()
        if rule.get("kind") == "skill"
        and isinstance(dest := rule.get("dest"), str)
        and "{" not in dest
    ]
    assert names, (
        f"{CONTRACT_PATH} declares no fixed-path `skill` rule, so the ported half "
        "of the activation inventory has nothing to be checked against"
    )
    return sorted(names)


def _kiro_owned_skill_names() -> list[str]:
    """The skill directories the contract creates with no template source.

    The command-derived skills *(R9 AC1)* and the client-adaptation skill that
    realizes the `Hook_Installer` *(R7 AC6)*: the skills the Bootcamp_Power carries
    beyond the ported inventory. Derived from the contract's `kiro-owned` dests,
    which is where they are declared — so a release that adds a command extends
    this set through the contract rather than through an edit here.
    """
    names: set[str] = set()
    for rule in _contract_rules():
        if rule.get("kind") != "kiro-owned":
            continue
        dest = rule.get("dest")
        candidates = [dest] if isinstance(dest, str) else dest or []
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            match = _POWER_SKILL_DEST.match(candidate)
            if match is not None:
                names.add(match.group("name"))
    return sorted(names)


@lru_cache(maxsize=None)
def _kiro_owned_skill_frontmatter(skill: str) -> dict[str, Any]:
    """The authored frontmatter of one `kiro-owned` skill template."""
    path = REPO_ROOT / KIRO_OWNED_TEMPLATE_ROOT / "skills" / skill / SKILL_ENTRY_POINT
    assert path.is_file(), (
        f"{KIRO_OWNED_TEMPLATE_ROOT}/skills/{skill}/{SKILL_ENTRY_POINT} is missing, "
        "so the checklist names a skill the build does not author"
    )
    block, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    assert block is not None, (
        f"{KIRO_OWNED_TEMPLATE_ROOT}/skills/{skill}/{SKILL_ENTRY_POINT} carries no "
        "YAML frontmatter block, so it declares no trigger phrase"
    )
    document = yaml.safe_load(block)
    assert isinstance(document, dict), (
        f"{KIRO_OWNED_TEMPLATE_ROOT}/skills/{skill}: frontmatter is not a mapping"
    )
    return document


def _declared_trigger_phrase(skill: str) -> str:
    """The phrase a `kiro-owned` skill's own description quotes (R8 AC6)."""
    description = str(_kiro_owned_skill_frontmatter(skill).get("description", ""))
    match = _QUOTED_TRIGGER_PHRASE.search(description)
    assert match is not None, (
        f"{KIRO_OWNED_TEMPLATE_ROOT}/skills/{skill}: the description quotes no "
        f"trigger phrase, so Test_Checklist step {_activation_step().number} would "
        f"have nothing to state for it; found {description!r}"
    )
    return match.group("phrase")


def _activation_cell_row(step: ChecklistStep, key: str) -> str:
    """The authored table row for one activation cell, whitespace stripped."""
    marker = f"`{step.number}.{key}`"
    rows = [
        line.strip()
        for line in step.fields[FIELD_ACTIVATION_CELLS].splitlines()
        if marker in line
    ]
    assert len(rows) == 1, (
        f"step {step.number} must carry exactly one row for the cell {marker}; "
        f"found {len(rows)}"
    )
    return rows[0]


# --- The definition parses, and is numbered as records depend on (R6 AC1) ---


def test_the_test_checklist_parses_as_the_definition_records_are_emitted_from():
    """`docs/test-checklist.md` reads as a checklist definition (R6 AC1, AC2).

    The tooling resolves its own default from its own location, so this also
    pins that default to the path the design's repository layout declares: a
    checklist the tests read and the tooling does not would be two checklists.
    """
    definition = _checklist()
    assert definition.source == (REPO_ROOT / CHECKLIST_PATH).as_posix(), (
        f"the parsed definition reports source {definition.source!r}; it must be "
        f"the committed {CHECKLIST_PATH}"
    )
    assert DEFAULT_CHECKLIST == (REPO_ROOT / CHECKLIST_PATH), (
        f"testrecord.DEFAULT_CHECKLIST resolves to {DEFAULT_CHECKLIST}, not the "
        f"committed {CHECKLIST_PATH}; `emit` would read a different file than "
        "these tests assert the shape of"
    )


def test_the_checklist_steps_are_uniquely_numbered_and_strictly_ordered():
    """Steps run 1..17, once each, in order (R6 AC1).

    The parser rejects a gap, a repeat, or a step out of order, so this pins the
    committed file's numbering as the fact records depend on: a step number is
    the key a recorded outcome is filed under, and it is stable across releases
    precisely so an old record stays readable.
    """
    definition = _checklist()
    assert definition.step_numbers == tuple(range(1, CHECKLIST_STEP_COUNT + 1)), (
        f"{CHECKLIST_PATH} must define steps numbered 1..{CHECKLIST_STEP_COUNT}, "
        f"strictly increasing with no gaps and no repeats; found "
        f"{list(definition.step_numbers)}"
    )

    titles = [step.title for step in definition.steps]
    duplicates = sorted({title for title in titles if titles.count(title) > 1})
    assert duplicates == [], (
        f"{CHECKLIST_PATH} gives two steps the same title, so a Maintainer cannot "
        f"tell which one an outcome belongs to: {duplicates}"
    )
    blank = [step.number for step in definition.steps if not step.title.strip()]
    assert blank == [], f"these steps carry no title: {blank}"


def test_the_generator_and_the_tooling_agree_on_the_checklist_shape():
    """`strategies.py` generates outcomes for the shape the tooling parses.

    Property 23 generates recorded outcome sets from the generator's constants
    and evaluates them with the gate, which works from the parsed definition. If
    the two disagreed, the property would exercise a checklist that does not
    exist while this section asserted the one that does.
    """
    assert GENERATOR_CHECKLIST_STEP_COUNT == CHECKLIST_STEP_COUNT, (
        "strategies.CHECKLIST_STEP_COUNT is "
        f"{GENERATOR_CHECKLIST_STEP_COUNT} and testrecord.CHECKLIST_STEP_COUNT is "
        f"{CHECKLIST_STEP_COUNT}"
    )
    assert GENERATOR_PER_PLATFORM_STEPS == PER_PLATFORM_STEPS, (
        f"strategies.PER_PLATFORM_STEPS is {list(GENERATOR_PER_PLATFORM_STEPS)} and "
        f"testrecord.PER_PLATFORM_STEPS is {list(PER_PLATFORM_STEPS)}"
    )
    assert GENERATOR_SUPPORTED_PLATFORMS == SUPPORTED_PLATFORMS, (
        f"strategies.SUPPORTED_PLATFORMS is {list(GENERATOR_SUPPORTED_PLATFORMS)} "
        f"and testrecord.SUPPORTED_PLATFORMS is {list(SUPPORTED_PLATFORMS)}"
    )


# --- Every step declares one observable pass/fail outcome (R6 AC1) ---------


@pytest.mark.parametrize("number", range(1, CHECKLIST_STEP_COUNT + 1))
def test_every_checklist_step_declares_one_observable_pass_fail_outcome(number):
    """Each step states what it verifies, what to do, and how it is recorded (R6 AC1).

    "Discrete step with an observable pass/fail outcome" is four things
    together: it names the criteria it discharges, its actions are enumerated so
    two Maintainers perform the same step, `Pass` and `Fail` are *different*
    conditions, and there is a slot to record the result in. A step missing the
    last one cannot fail — and a step that cannot fail is not a gate.
    """
    step = _checklist().step(number)
    assert step is not None, f"{CHECKLIST_PATH} defines no step {number}"

    blank = [name for name in REQUIRED_FIELDS if not step.fields.get(name, "").strip()]
    assert blank == [], (
        f"step {number} carries these required fields blank: {blank}; all of "
        f"{list(REQUIRED_FIELDS)} must say something"
    )

    verifies = step.fields[FIELD_VERIFIES]
    assert _REQUIREMENT_CITATION.search(verifies), (
        f"step {number} must name the acceptance criteria it discharges; its "
        f"Verifies field reads {verifies!r}"
    )
    assert _FIRST_NUMBERED_ACTION.search(step.fields[FIELD_DO]), (
        f"step {number}'s Do field must be a numbered list of actions, so the "
        f"step is performed the same way twice; it reads {step.fields[FIELD_DO]!r}"
    )

    # The recording slot is the first line of the field; a step block runs to the
    # next heading, so trailing document furniture below it is not the slot.
    outcome = step.fields[FIELD_OUTCOME]
    slot = outcome.splitlines()[0].strip().strip("`")
    if step.per_platform:
        # The three cells are the record of truth for a per-platform step, and
        # the step's own outcome is derived from them, so it carries no slot of
        # its own — one recorded there would be a rolled-up pass over a blank
        # platform cell (R6 AC12).
        assert re.search(r"per platform", outcome, re.IGNORECASE), (
            f"step {number} records one outcome per Supported_Platform, so its "
            f"Outcome field must say so rather than carry a slot; it reads "
            f"{outcome!r}"
        )
        unrecorded = [
            cell.id for cell in step.platform_cells if cell.slot != UNRECORDED
        ]
        assert unrecorded == [], (
            f"step {number}'s platform cells must ship empty, spelled "
            f"{UNRECORDED!r}; these carry something else: {unrecorded}"
        )
    else:
        assert slot == UNRECORDED, (
            f"step {number} must ship an empty recording slot spelled "
            f"{UNRECORDED!r} — a blank is indistinguishable from an oversight in "
            f"review, and an unrecorded outcome is a fail; found {slot!r}"
        )


# --- Every step R6 names is present, exactly once --------------------------


@pytest.mark.parametrize("marker", sorted(REQUIRED_STEPS))
def test_every_step_the_requirements_name_is_present_exactly_once(marker):
    """One step per fact R6 requires, and one only (R6 AC1, AC4, AC5, AC12, AC13).

    Located by what each step verifies rather than by its number, because the
    criterion is about the verification: a renumbered checklist still satisfies
    R6, a checklist that dropped the space-in-path step does not.
    """
    declared = REQUIRED_STEPS[marker]
    step = _the_step(marker)

    if declared["number"] is not None:
        assert step.number == declared["number"], (
            f"the {marker!r} step must be step {declared['number']}, which the "
            f"record tooling refers to by number; found step {step.number}"
        )

    text = _step_text(step)
    missing = [phrase for phrase in declared["phrases"] if phrase not in text]
    assert missing == [], (
        f"step {step.number} ({marker}, {declared['criterion']}) must state "
        f"{missing}, without which the step does not verify what the criterion "
        "asks for"
    )

    assert step.per_platform == declared["per_platform"], (
        f"step {step.number} ({marker}) records "
        f"{'one outcome' if step.per_platform else 'no outcome'} per "
        f"Supported_Platform; {declared['criterion']} requires the opposite. The "
        f"three per-platform steps are {list(PER_PLATFORM_STEPS)} (R6 AC12)"
    )


def test_the_successful_tool_call_step_follows_the_connectivity_step():
    """R6 AC4's two halves are ordered, not merely both present (R6 AC4).

    A tool call cannot be attempted before the server connects, so the tool-call
    step names the connectivity step as its precondition. Without that, a record
    could carry a tool-call pass beside a connectivity fail and read as coherent.
    """
    connectivity = _the_step("mcp-connectivity")
    tool_call = _the_step("mcp-tool-call")
    assert connectivity.number < tool_call.number, (
        f"the connectivity step (step {connectivity.number}) must come before the "
        f"tool-call step (step {tool_call.number})"
    )
    preconditions = tool_call.fields.get(FIELD_PRECONDITIONS, "")
    assert re.search(rf"\bstep\s+{connectivity.number}\b", preconditions), (
        f"step {tool_call.number} must name step {connectivity.number} as its "
        f"precondition; its Preconditions field reads {preconditions!r}"
    )


# --- One activation row per skill in the inventory (R6 AC5) ----------------


def test_the_activation_step_carries_one_row_per_skill_in_the_inventory():
    """The activation table is the whole skill inventory, row for row (R6 AC5, R9 AC4).

    R6 AC5 is per-skill: a skill in the built Power with no row is a trigger
    phrase nobody stated, and the step would pass while that skill was never
    tried. The four non-ported skills are derived from the contract that creates
    them; the twelve ported rows come from the resolved Template_Release, so they
    are checked by count and by key shape — the module set is `module-00` through
    `module-07` with `module-03b` among them.
    """
    step = _activation_step()
    keys = [cell.key for cell in step.activation_cells]
    assert sorted(keys) == sorted(set(keys)), (
        f"step {step.number} names the same skill twice: "
        f"{sorted({key for key in keys if keys.count(key) > 1})}"
    )

    kiro_owned = _kiro_owned_skill_names()
    authored = sorted(
        path.parent.name
        for path in (REPO_ROOT / KIRO_OWNED_TEMPLATE_ROOT / "skills").glob(
            f"*/{SKILL_ENTRY_POINT}"
        )
    )
    assert kiro_owned == authored, (
        f"{CONTRACT_PATH} creates the skills {kiro_owned} with no template source, "
        f"but {KIRO_OWNED_TEMPLATE_ROOT}/skills/ authors {authored}; the checklist "
        "inventory is derived from the first, so the two must be the same set"
    )

    missing_kiro_owned = sorted(set(kiro_owned) - set(keys))
    assert missing_kiro_owned == [], (
        f"step {step.number} has no activation row for {missing_kiro_owned}, which "
        f"the contract creates as Bootcamp_Power skills; a skill in the Power with "
        "no row is a fail for this step"
    )

    ported = [key for key in keys if key not in set(kiro_owned)]
    assert len(ported) == PORTED_SKILL_COUNT, (
        f"step {step.number} carries {len(ported)} ported rows; the inventory at "
        f"the resolved Template_Release is {PORTED_SKILL_COUNT} ported bootcamp "
        f"skills: {ported}"
    )
    modules = [key for key in ported if _MODULE_CELL_KEY.match(key)]
    assert len(modules) == PORTED_MODULE_SKILL_COUNT, (
        f"step {step.number} carries {len(modules)} module rows; the resolved "
        f"Template_Release has {PORTED_MODULE_SKILL_COUNT}, `module-03b` among "
        f"them: {sorted(modules)}"
    )
    missing_fixed = sorted(set(_fixed_ported_skill_names()) - set(ported))
    assert missing_fixed == [], (
        f"step {step.number} has no activation row for {missing_fixed}, which the "
        f"contract ports at a fixed path"
    )

    inventory_size = len(keys)
    assert inventory_size == PORTED_SKILL_COUNT + len(kiro_owned), (
        f"step {step.number} carries {inventory_size} rows; the inventory is "
        f"{PORTED_SKILL_COUNT} ported skills plus the {len(kiro_owned)} the "
        f"contract creates"
    )
    install = _the_step("add-custom-power")
    assert f"{inventory_size} skills" in _step_text(install), (
        f"step {install.number} checks the installed Power's skill list against a "
        f"count, which must be the same inventory step {step.number} activates "
        f"row by row: {inventory_size} skills"
    )


def test_every_kiro_owned_activation_row_quotes_the_phrase_its_skill_declares():
    """Each non-ported row states the phrase its own skill quotes (R6 AC5, R8 AC6).

    A ported row deliberately says "the phrase its own description quotes": the
    text lives in the Template_Release, so writing it here would be a second copy
    that can go stale. The four `kiro-owned` skills are authored *in this
    repository*, so their phrases are checkable — and if a row quoted a phrase
    the skill's description does not, a Maintainer would state something that
    activates nothing and record a fail against a working skill.
    """
    step = _activation_step()
    mismatched: dict[str, str] = {}
    for skill in _kiro_owned_skill_names():
        phrase = _declared_trigger_phrase(skill)
        row = _activation_cell_row(step, skill)
        if phrase not in row:
            mismatched[skill] = f"row {row!r} does not quote {phrase!r}"
    assert mismatched == {}, (
        f"step {step.number} must quote each non-ported skill's own trigger "
        f"phrase, which is the text its description declares: {mismatched}"
    )

    command_derived = {
        skill: _declared_trigger_phrase(skill)
        for skill in _kiro_owned_skill_names()
        if skill in TRIGGER_PHRASES
    }
    assert command_derived == dict(TRIGGER_PHRASES), (
        "the command-derived skills' authored phrases must be the ones the "
        f"generator drives Property 17 with; authored {command_derived}, generator "
        f"{dict(TRIGGER_PHRASES)}"
    )


# --- The nine-cell per-platform matrix (R6 AC12) ---------------------------


def test_the_per_platform_matrix_is_nine_cells_on_the_three_declared_steps():
    """Three steps, three platforms, nine cells, none of them optional (R6 AC12).

    The cells are the record of truth: R6 AC12 requires a per-platform outcome
    for the install, hook-firing, and ported-script steps, and the gate reads the
    nine cells rather than the three steps so a platform cannot pass by omission.
    """
    definition = _checklist()
    assert definition.platform_steps == tuple(PER_PLATFORM_STEPS), (
        f"steps {list(PER_PLATFORM_STEPS)} record one outcome per "
        f"Supported_Platform; {CHECKLIST_PATH} carries platform cells on "
        f"{list(definition.platform_steps)}"
    )
    expected = tuple(
        f"{number}.{platform}"
        for number in PER_PLATFORM_STEPS
        for platform in SUPPORTED_PLATFORMS
    )
    assert definition.platform_cell_ids == expected, (
        f"the per-platform matrix is the nine cells {list(expected)}; "
        f"{CHECKLIST_PATH} declares {list(definition.platform_cell_ids)}"
    )


def test_the_matrix_step_reads_back_every_one_of_the_nine_cells():
    """Step 16 names all nine cells it checks (R6 AC12, R16 AC1).

    The gate performs this check mechanically over the cells, so step 16 grants
    nothing on its own. Its job is to make an unrecorded platform *visible* to
    the Maintainer before the gate blocks the tag — which it can only do if it
    names each cell rather than saying "check the matrix".
    """
    step = _the_step("per-platform-matrix")
    text = _step_text(step)
    missing = [
        cell_id for cell_id in _checklist().platform_cell_ids if cell_id not in text
    ]
    assert missing == [], (
        f"step {step.number} must name every platform cell it reads back; these "
        f"appear nowhere in it: {missing}"
    )


# ===========================================================================
# 8. Upstream-release watch workflow (R5 AC1) — task 17.1
# ===========================================================================
#
# `.github/workflows/watch-upstream-release.yml` is the one piece of CI the plan
# asks for, and its whole value depends on staying inside the boundary R5 AC1
# draws: v1 update is manual and Maintainer-run, so the workflow **detects and
# reports** a newer Template_Release and does not transform, does not commit, and
# does not open a PR. The reconciliation report needs a human decision and the
# manual Test_Checklist gates the release, so a bot cannot carry an update to a
# mergeable state anyway.
#
# Four claims are worth holding in place, because each one is a thing a later
# convenience edit would plausibly break:
#
# 1. It actually runs unattended, and can also be run on demand.
# 2. Every action is pinned to a commit, so a retagged floating ref cannot
#    change what executes with this repository's token.
# 3. It asks for the narrowest permissions that do the job — a widened token is
#    exactly how "detect and report" quietly becomes "commit and push".
# 4. Detection goes through the Version_Resolver, and both the current version
#    and the upstream repository are read rather than restated here. The
#    resolver owns semver comparison and the eligibility filter (R1); the
#    contract owns `template.repository` (R3 AC1). A copy of either in this file
#    is a second source that can drift.

WATCH_WORKFLOW_PATH = ".github/workflows/watch-upstream-release.yml"

#: `owner/repo@<sha>`, with the SHA a full 40-hex commit id. A tag or a branch in
#: the ref position is mutable by whoever owns the action.
_PINNED_ACTION = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w.-]+)*@[0-9a-f]{40}$")

#: The engine entry points this workflow must *not* invoke: running any of them
#: would make it perform the update R5 AC1 keeps manual.
_TRANSFORMING_SCRIPTS = ("transform.py", "validate.py", "reconcile.py")


def _watch_workflow() -> dict[str, Any]:
    """Parse the watch workflow. Its absence is a failure, not a skip."""
    path = REPO_ROOT / WATCH_WORKFLOW_PATH
    assert path.is_file(), f"{WATCH_WORKFLOW_PATH} is missing"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{WATCH_WORKFLOW_PATH} is not a YAML mapping"
    return document


def _watch_workflow_text() -> str:
    return (REPO_ROOT / WATCH_WORKFLOW_PATH).read_text(encoding="utf-8")


def _watch_workflow_steps() -> list[dict[str, Any]]:
    jobs = _watch_workflow().get("jobs") or {}
    return [step for job in jobs.values() for step in (job.get("steps") or [])]


# --- It runs unattended, and on demand (R5 AC1) ----------------------------


def test_the_upstream_watch_runs_on_a_schedule_and_on_demand():
    """A watch nobody has to remember to run, plus a manual entry point (R5 AC1).

    The schedule is the point: an upstream release the Maintainer never hears
    about is the failure this workflow exists to prevent. `workflow_dispatch` is
    what makes it testable and lets a Maintainer check before the Power exists,
    which is why the dispatch path takes a `min-version` override.
    """
    document = _watch_workflow()
    # PyYAML resolves the bare key `on` to the boolean True (YAML 1.1), so read
    # whichever key the parse produced rather than assuming the string.
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), (
        f"{WATCH_WORKFLOW_PATH} must declare its triggers as a mapping; got "
        f"{type(triggers).__name__}"
    )

    schedule = triggers.get("schedule")
    assert isinstance(schedule, list) and schedule, (
        f"{WATCH_WORKFLOW_PATH} must run on a schedule, so a newer "
        "Template_Release surfaces without anyone remembering to look"
    )
    assert all(entry.get("cron") for entry in schedule), (
        f"every schedule entry in {WATCH_WORKFLOW_PATH} needs a cron expression; "
        f"got {schedule}"
    )

    assert "workflow_dispatch" in triggers, (
        f"{WATCH_WORKFLOW_PATH} must stay manually dispatchable, so the watch can "
        "be exercised on demand rather than only on its schedule"
    )
    inputs = (triggers.get("workflow_dispatch") or {}).get("inputs") or {}
    assert "min-version" in inputs, (
        "the dispatch path takes a min-version override, which is what allows a "
        "check before a Bootcamp_Power records a Template_Release; "
        f"{WATCH_WORKFLOW_PATH} declares inputs {sorted(inputs)}"
    )


# --- Every action is pinned to a commit, not a floating ref ----------------


def test_the_upstream_watch_pins_every_action_to_a_commit_sha():
    """A mutable ref is a third party's write access to this job (R5 AC1).

    `@v7` is a tag the action's owner can move. Pinning the commit means the
    bytes that run with this repository's token are the bytes that were
    reviewed, and an upgrade is a visible diff rather than a silent retag.
    """
    unpinned = [
        step.get("uses")
        for step in _watch_workflow_steps()
        if step.get("uses") and not _PINNED_ACTION.match(step["uses"])
    ]
    assert unpinned == [], (
        f"every `uses:` in {WATCH_WORKFLOW_PATH} must name a full 40-hex commit "
        f"SHA rather than a tag or a branch; these are on a mutable ref: {unpinned}"
    )


# --- The narrowest permissions that do the job -----------------------------


def test_the_upstream_watch_asks_for_the_narrowest_permissions():
    """Read the tree, write an issue, nothing else (R5 AC1).

    This is the mechanical half of "detect and report". The workflow cannot push
    a transform or open a PR it has no permission to open, so the token itself
    holds the R5 AC1 boundary even if the steps were later edited badly.
    """
    permissions = _watch_workflow().get("permissions")
    assert permissions == {"contents": "read", "issues": "write"}, (
        f"{WATCH_WORKFLOW_PATH} reads the committed version and files a tracking "
        "issue, so its token needs exactly contents: read and issues: write; "
        f"it asks for {permissions}"
    )


# --- Detection is the resolver's, and nothing is restated here -------------


def test_the_upstream_watch_detects_through_the_resolver_and_transforms_nothing():
    """Delegate the comparison, perform no update (R1, R3 AC1, R5 AC1).

    Three separate ways this could rot, all checked here: the workflow could
    grow its own version comparison instead of calling the resolver; it could
    start running the engine and become the automated update the requirements
    defer; or it could hardcode the current version or the upstream slug, either
    of which is a second source that drifts from the Power and the contract.
    """
    text = _watch_workflow_text()

    assert "resolve_release.py" in text and "--min-version" in text, (
        f"{WATCH_WORKFLOW_PATH} must detect by invoking `resolve_release.py "
        "--min-version <current>`, so semver comparison and the "
        "published/non-draft/non-prerelease filter stay in the Version_Resolver"
    )

    performing = [name for name in _TRANSFORMING_SCRIPTS if name in text]
    assert performing == [], (
        f"{WATCH_WORKFLOW_PATH} must detect and report only — R5 AC1 keeps the "
        f"update manual and Maintainer-run; it invokes {performing}"
    )

    # The version compared against is read from the Power's own provenance
    # (R2 AC5) with the Build_Manifest as the fallback, so a rebuild moves it.
    assert "templateRelease" in text, (
        f"{WATCH_WORKFLOW_PATH} must read the current Template_Release from the "
        "committed Power's recorded provenance rather than carrying a copy of it"
    )
    hardcoded = re.findall(r"--min-version[= ]+[\"']?\d+\.\d+\.\d+", text)
    assert hardcoded == [], (
        f"{WATCH_WORKFLOW_PATH} must pass the version it read, not a literal; "
        f"found {hardcoded}"
    )

    # `template.repository` is the contract's fact, and the resolver already
    # defaults to it, so naming the slug here would be the second copy.
    slug = _load_contract().get("template", {}).get("repository")
    assert slug and slug not in text, (
        f"{WATCH_WORKFLOW_PATH} must let the resolver read template.repository "
        f"from {CONTRACT_PATH} rather than naming {slug!r} itself"
    )


# ===========================================================================
# 9. Committed Test_Checklist record (R6 AC2, AC3, AC6, AC12) — task 16.1
# ===========================================================================
#
# The committed `powers/senzing-bootcamp/` is a release candidate, not a release:
# R6 AC2 says tagging waits on *recorded* confirmation that every Test_Checklist
# step passed, and executing the checklist happens in a live Kiro session on three
# platforms, which no test here can do. What this repository can carry is the file
# those outcomes get recorded into — emitted by `testrecord.py` from
# `docs/test-checklist.md`, so the Maintainer fills a shape the gate already
# parses rather than inventing one at tag time.
#
# So this section asserts two different things about that file:
#
# 1. **It exists and accounts for everything.** A record for the version the Power
#    itself declares, with all `CHECKLIST_STEP_COUNT` steps and all nine
#    per-platform cells present, and header facts that agree with the committed
#    Power and its validation report rather than restating them by hand.
# 2. **The gate over it is closed while outcomes are blank**, and closed for each
#    of the three shapes R6 AC3 and AC12 name — a bare skeleton, a record with any
#    one platform cell blank, and a record naming a version other than the one
#    being tagged. The all-pass control is asserted alongside each, because "the
#    gate is closed" is only evidence if something opens it.
#
# The gate's *general* behavior over arbitrary outcome sets is Property 23's job.
# These are the same claims narrowed to the committed artifact and the committed
# checklist, which is where a skeleton emitted from a drifted definition, or a
# record left for a version nobody is tagging, would actually show up.

#: The generated Bootcamp_Power and its manifest. The version under test is read
#: from there rather than written here: a record gates the version the Power says
#: it is *(R2 AC1)*, so a rebuilt Power at a newer tag needs its own record and
#: this section says so instead of silently checking the old one.
POWER_DIR = "powers/senzing-bootcamp"
POWER_PLUGIN_PATH = f"{POWER_DIR}/{PLUGIN_MANIFEST_DEST}"

#: The `ValidationReport` the record's header quotes, at the path checklist step 1
#: and the Create_Skill both write it to.
VALIDATION_REPORT_SUFFIX = "-validation.json"

#: The status step 1 requires of that report before anything else is worth
#: recording *(R13 AC4, AC5)*.
VALIDATION_STATUS_PASSED = "passed"


@lru_cache(maxsize=1)
def _power_manifest() -> dict[str, Any]:
    """The committed Power's `plugin.json`, which names the version under test."""
    path = REPO_ROOT / POWER_PLUGIN_PATH
    assert path.is_file(), (
        f"{POWER_PLUGIN_PATH} is missing; the version a Test_Checklist record "
        "gates is the version the committed Power declares"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{POWER_PLUGIN_PATH} is not a JSON object"
    return document


def _version_under_test() -> str:
    """The Power's own version string, character for character *(R2 AC1)*."""
    version = str(_power_manifest().get("version", "")).strip()
    assert version, f"{POWER_PLUGIN_PATH} declares no `version`"
    return version


def _record_path() -> str:
    """`docs/test-records/<version>.md` for the committed Power *(R6 AC2)*."""
    return f"{RECORDS_DIRECTORY}/{_version_under_test()}.md"


def _validation_report_path() -> str:
    return f"{RECORDS_DIRECTORY}/{_version_under_test()}{VALIDATION_REPORT_SUFFIX}"


@lru_cache(maxsize=1)
def _committed_record() -> _TestRecord:
    """The committed record, parsed by the tooling that emitted it.

    A parse failure is reported as a failure of the record: it is the file the
    release procedure reads, so a record only this file's own reader accepted
    would gate nothing.
    """
    path = REPO_ROOT / _record_path()
    assert path.is_file(), (
        f"{_record_path()} is missing; R6 AC2 gates tagging on a recorded "
        f"confirmation for exactly version {_version_under_test()}, and the "
        "skeleton is what a Maintainer records into"
    )
    try:
        return read_record(path, definition=_checklist())
    except RecordError as error:
        pytest.fail(f"{_record_path()} cannot be read unambiguously: {error}")


def _all_pass_outcomes() -> dict[int, Any]:
    """Every defined step recorded as a pass, a per-platform step cell by cell."""
    return {
        step.number: (
            {platform: OUTCOME_PASS for platform in step.platforms}
            if step.per_platform
            else OUTCOME_PASS
        )
        for step in _checklist().steps
    }


def _gate(
    outcomes: dict[int, Any] | None,
    *,
    version: str | None = None,
    recorded_version: str | None = None,
) -> _TestRecordReport:
    """Render a record, read it back, and compute the gate over it.

    Deliberately routed through the document: `render_record` → `parse_record` →
    `evaluate` is what a Maintainer's committed file goes through, so a shape the
    emitter writes and the parser drops is caught here rather than assumed away.
    `outcomes` of `None` is the skeleton. `recorded_version` is what the record
    *names*, which defaults to the version being tagged.
    """
    definition = _checklist()
    under_test = _version_under_test() if version is None else version
    named = under_test if recorded_version is None else recorded_version
    text = render_record(definition, named, outcomes=outcomes)
    return evaluate(
        parse_record(text, definition=definition),
        version=under_test,
        definition=definition,
    )


# --- The record exists and accounts for every step and cell (R6 AC2, AC6) ---


def test_a_test_checklist_record_is_committed_for_the_power_version():
    """A record exists for exactly the version the Power declares (R6 AC2).

    Emitted from `docs/test-checklist.md` rather than hand-written, so the record
    and the checklist cannot disagree about what the steps are, and it carries the
    checklist reference and format version that say which definition it came from.
    """
    record = _committed_record()
    version = _version_under_test()
    assert record.version == version, (
        f"{_record_path()} names version {record.version!r} but the committed "
        f"Power declares {version!r}; a record only gates the version it names"
    )
    assert record.format_version == RECORD_FORMAT_VERSION, (
        f"{_record_path()} declares record format version "
        f"{record.format_version}, not {RECORD_FORMAT_VERSION}; the format "
        "version is how a record says which checklist shape it was written for"
    )
    text = (REPO_ROOT / _record_path()).read_text(encoding="utf-8")
    assert CHECKLIST_PATH in text, (
        f"{_record_path()} must name the checklist it was emitted from "
        f"({CHECKLIST_PATH}), so a reader can tell which definition its steps are"
    )


def test_the_committed_record_header_agrees_with_the_committed_power():
    """The header's facts are read from the build, not typed in (R2 AC5, R6 AC6).

    `Template_Release` is the Power's own recorded provenance and the
    `ValidationReport status` is the status of the report checklist step 1 reads,
    so a record cannot claim a release or a validation outcome the repository does
    not actually hold. `Maintainer` and `Date` are deliberately unfilled: they are
    facts about a run nobody has performed yet.
    """
    record = _committed_record()
    provenance = (_power_manifest().get("extensions") or {}).get(
        EXTENSION_NAMESPACE
    ) or {}
    expected_release = str(provenance.get(TEMPLATE_RELEASE_FIELD, "")).strip()
    assert expected_release, (
        f"{POWER_PLUGIN_PATH} records no "
        f"extensions[{EXTENSION_NAMESPACE!r}][{TEMPLATE_RELEASE_FIELD!r}], so the "
        "record has no provenance to agree with"
    )
    assert record.template_release == expected_release, (
        f"{_record_path()} names Template_Release {record.template_release!r} but "
        f"the Power records {expected_release!r} as its provenance"
    )

    report_path = REPO_ROOT / _validation_report_path()
    assert report_path.is_file(), (
        f"{_validation_report_path()} is missing; checklist step 1 reads the "
        "ValidationReport for this exact version, and the record quotes its status"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert record.validation_status == report.get("status"), (
        f"{_record_path()} quotes ValidationReport status "
        f"{record.validation_status!r}, but {_validation_report_path()} reports "
        f"{report.get('status')!r}"
    )
    assert record.validation_status == VALIDATION_STATUS_PASSED, (
        f"the committed Power's validation status is {record.validation_status!r}; "
        f"checklist step 1 requires {VALIDATION_STATUS_PASSED!r} before any other "
        "step is worth recording"
    )
    assert record.maintainer == "" and record.date == "", (
        f"{_record_path()} records Maintainer {record.maintainer!r} and Date "
        f"{record.date!r}; both belong to a run a Maintainer performs, and "
        "neither is emitted from the clock or the environment"
    )


def test_the_committed_record_carries_a_slot_for_every_checklist_step():
    """All 17 steps have a row, so nothing is missing rather than merely blank.

    A missing step and a blank outcome both block tagging, but only the blank one
    tells a Maintainer where to write: the point of the skeleton is that every
    step already has a place to be recorded (R6 AC2, AC6).
    """
    record = _committed_record()
    recorded = {step.step for step in record.steps}
    missing = sorted(set(_checklist().step_numbers) - recorded)
    assert missing == [], (
        f"{_record_path()} has no row for step(s) {missing}; the skeleton carries "
        f"all {CHECKLIST_STEP_COUNT} defined steps"
    )
    extra = sorted(recorded - set(_checklist().step_numbers))
    assert extra == [], (
        f"{_record_path()} records step(s) {extra}, which {CHECKLIST_PATH} does "
        "not define"
    )


def test_the_committed_record_carries_all_nine_per_platform_cells():
    """Steps 2, 10, and 15 each carry one cell per Supported_Platform (R6 AC12).

    Nine cells, each recorded from a run on its own platform. A step recorded
    once for "all platforms" is exactly what AC12 rules out, so the cells have to
    be present and separate before anyone can fill them.
    """
    record = _committed_record()
    expected = set(_checklist().platform_cell_ids)
    assert len(expected) == len(PER_PLATFORM_STEPS) * len(SUPPORTED_PLATFORMS)
    present = {cell.id for step in record.steps for cell in step.cells}
    assert present == expected, (
        f"{_record_path()} must carry exactly the nine per-platform cells "
        f"{sorted(expected)}; missing {sorted(expected - present)}, unexpected "
        f"{sorted(present - expected)}"
    )
    for number in PER_PLATFORM_STEPS:
        step = record.step(number)
        assert step is not None and step.per_platform, (
            f"step {number} records one outcome per Supported_Platform; "
            f"{_record_path()} carries no cells for it"
        )
        assert [cell.platform for cell in step.cells] == list(SUPPORTED_PLATFORMS), (
            f"step {number}'s cells must be "
            f"{list(SUPPORTED_PLATFORMS)}; found "
            f"{[cell.platform for cell in step.cells]}"
        )


def test_the_committed_record_is_written_with_lf_line_endings():
    """The record reads the same on every Supported_Platform (R16 AC8)."""
    raw = (REPO_ROOT / _record_path()).read_bytes()
    assert b"\r" not in raw, (
        f"{_record_path()} contains a carriage return; records are written LF-only "
        f"like every other committed artifact ({GITATTRIBUTES_PATH})"
    )
    assert raw.endswith(b"\n"), f"{_record_path()} does not end with a newline"


# --- The gate is closed while outcomes are blank (R6 AC3, AC12) -------------


def test_the_gate_over_the_committed_record_is_closed_until_every_step_passes():
    """Tagging is allowed exactly when the record is complete and all-pass (R6 AC3).

    Stated as the biconditional rather than as "the committed record is blank", so
    the assertion stays true as a Maintainer fills it in: while any outcome is
    unrecorded or failed the gate is closed and names what is missing, and it
    opens only once every step and every cell reads `pass`.
    """
    record = _committed_record()
    version = _version_under_test()
    report = evaluate(record, version=version, definition=_checklist())

    outstanding = sorted(
        cell.id
        for step in record.steps
        for cell in step.cells
        if cell.outcome != OUTCOME_PASS
    ) + sorted(
        str(step.step)
        for step in record.steps
        if not step.per_platform and step.outcome != OUTCOME_PASS
    )
    assert report.tag_allowed == (outstanding == []), (
        f"the gate over {_record_path()} reports tagAllowed "
        f"{report.tag_allowed} while these outcomes are not a recorded pass: "
        f"{outstanding}"
    )
    assert report.findings_for(REASON_VERSION_MISMATCH) == (), (
        f"{_record_path()} names version {record.version!r} and the Power "
        f"declares {version!r}; the gate should not be reporting a mismatch"
    )
    if outstanding:
        assert report.error == E_CHECKLIST_INCOMPLETE
        blocked = {
            finding.cell or str(finding.step) for finding in report.findings
        }
        assert set(outstanding) <= blocked, (
            f"the gate must name every outcome that is not a recorded pass; "
            f"{sorted(set(outstanding) - blocked)} is unrecorded in "
            f"{_record_path()} yet no finding names it"
        )


def test_the_emitted_skeleton_gates_tagging_closed():
    """A skeleton blocks tagging, and says so once per unrecorded slot (R6 AC3).

    Every one of the 17 steps and nine cells is reported, not the first: the
    record is a worklist, so a Maintainer reads the whole remaining run in one
    pass. The three per-platform steps are reported through their cells rather
    than twice, which is why the blank-outcome set excludes them.
    """
    report = _gate(None)
    assert not report.tag_allowed, (
        "a record with nothing recorded in it must never allow tagging; "
        f"{_record_path()} is emitted in exactly this shape"
    )
    assert report.error == E_CHECKLIST_INCOMPLETE

    blank_steps = {finding.step for finding in report.findings_for(REASON_BLANK_OUTCOME)}
    assert blank_steps == set(_checklist().step_numbers) - set(PER_PLATFORM_STEPS), (
        "every step that records one outcome must be reported blank; found "
        f"{sorted(blank_steps)}"
    )
    blank_cells = {finding.cell for finding in report.findings_for(REASON_BLANK_CELL)}
    assert blank_cells == set(_checklist().platform_cell_ids), (
        "each of the nine per-platform cells must be reported blank on its own; "
        f"found {sorted(blank_cells)}"
    )
    for reason in (REASON_MISSING_STEP, REASON_MISSING_CELL, REASON_VERSION_MISMATCH):
        assert report.findings_for(reason) == (), (
            f"a skeleton has a slot for everything and names the right version, so "
            f"it must report no {reason} finding; found "
            f"{[finding.label for finding in report.findings_for(reason)]}"
        )


def test_a_fully_recorded_all_pass_record_opens_the_gate():
    """The gate does open, so the closed cases above are evidence (R6 AC2, AC3).

    Also the round trip that matters for the skeleton: outcomes written into the
    emitted shape are read back as the same outcomes, so a Maintainer filling the
    committed file in place is filling a file the gate can already read.
    """
    report = _gate(_all_pass_outcomes())
    assert report.tag_allowed, (
        "a record with a recorded pass for every step and every platform cell "
        f"must allow tagging; the gate reported {list(report.defects)}"
    )
    assert report.error is None
    assert len(report.record.steps) == CHECKLIST_STEP_COUNT


@pytest.mark.parametrize("platform", SUPPORTED_PLATFORMS)
@pytest.mark.parametrize("step", PER_PLATFORM_STEPS)
def test_any_one_blank_platform_cell_closes_the_gate(step: int, platform: str):
    """One unrecorded platform blocks tagging on its own (R6 AC12, R16 AC1).

    An otherwise complete all-pass record with a single cell left blank: the gate
    closes and names that cell, because an unrecorded platform is a fail rather
    than a blank, and "it worked on Linux" is not a record for macOS or Windows.
    """
    outcomes = _all_pass_outcomes()
    outcomes[step] = dict(outcomes[step])
    outcomes[step][platform] = ""

    report = _gate(outcomes)
    assert not report.tag_allowed, (
        f"cell {step}.{platform} is unrecorded, so tagging must be blocked even "
        "though every other outcome is a pass"
    )
    assert report.error == E_CHECKLIST_INCOMPLETE
    assert [finding.label for finding in report.findings] == [
        f"{REASON_BLANK_CELL}:{step}:{platform}"
    ], (
        f"exactly one finding is owed — the blank {PLATFORM_LABELS[platform]} cell "
        f"of step {step} — and it names that cell; found "
        f"{[finding.label for finding in report.findings]}"
    )
    (finding,) = report.findings
    assert finding.cell == f"{step}.{platform}" and finding.step == step
    assert UNRECORDED in finding.message


def test_a_record_naming_another_version_closes_the_gate():
    """An all-pass record for a different version gates nothing (R6 AC2, R2 AC3).

    The record is evidence about the artifact it was produced against, so a
    complete run recorded for `0.5.1` cannot release `0.5.2`. The finding names
    both strings, because the useful correction is either re-running the checklist
    or tagging what was actually tested.
    """
    version = _version_under_test()
    other = f"{version}-untested"
    report = _gate(_all_pass_outcomes(), version=other, recorded_version=version)

    assert not report.tag_allowed, (
        f"a record naming {version} must not open the gate for {other}, however "
        "complete it is"
    )
    assert report.error == E_CHECKLIST_INCOMPLETE
    mismatch = report.findings_for(REASON_VERSION_MISMATCH)
    assert len(mismatch) == 1, (
        f"exactly one version-mismatch finding is owed; found "
        f"{[finding.label for finding in mismatch]}"
    )
    assert version in mismatch[0].message and other in mismatch[0].message, (
        "the finding must name the recorded version and the version under test, "
        f"so the correction is obvious; it reads {mismatch[0].message!r}"
    )
    assert report.findings == mismatch, (
        "every step is a recorded pass, so the mismatch is the only thing blocking "
        f"tagging; found {list(report.defects)}"
    )


# ===========================================================================
# 10. Assumption-dependent values are single-sourced (R3 AC4) — task 16.2
# ===========================================================================
#
# Three values in this repository depend on an assumption the design records as
# **unverified** (design, Unverified assumptions), and each is verified for the
# first time by a Maintainer running the `Test_Checklist` in a live Kiro session:
#
#   **A2** — `${PLUGIN_ROOT}` expands inside a Kiro hook `command` string.
#            Checklist step 10.
#   **A3** — Kiro's write-tool names are what a `PreToolUse` matcher must match.
#            Checklist step 11.
#   **A4** — a Power's `skills/*/scripts/` files are materialized at a stable
#            absolute path after install. Checklist step 10.
#
# So each one is a value that may well come back wrong, and what this section
# asserts is the property that makes coming back wrong cheap: **folding the
# observation in is one edit in one place, plus a rebuild.** Never a code edit,
# never a hand-patched asset, and never the same value corrected in two files
# that a later release can then let drift (R3 AC4).
#
# The three arrangements are different, because the three values are:
#
#   A3  The Kiro matcher regex is **one contract value** — the `replace` of the
#       single `tool-names` entry. The hook asset and the coverage map are
#       authored in the *template's* tool vocabulary and the contract rewrites
#       them as they are materialized, so the Kiro spelling exists in exactly one
#       authored file and reaches the Power only by rebuild.
#   A2  Interpreter and script-path resolution live **entirely inside
#       `install_hooks.py`**. Whatever the observation says, the shipped asset is
#       unaffected: it carries the two placeholders and the installer resolves
#       absolute quoted paths regardless. So there is nothing to fold in at all
#       — which is the strongest form of one-place, and what these tests pin.
#   A4  The fallback is implemented in the installer and **selected by a contract
#       flag**: the `scripts-dir-strategy` set fills the coverage map's
#       `scriptsDirectoryStrategy` field, and the installer reads it. Flipping to
#       the workspace copy is one contract line plus a rebuild.
#
# Two kinds of check appear below. Most are single-home sweeps over the authored
# tree. The last is behavioral, and deliberately so: "one line plus a rebuild"
# is only true if the flipped line actually changes where the hooks point, so the
# fallback is exercised end to end — plan, disclosure, install, second install,
# removal — with the contract-owned field as the *only* difference between the two
# runs. The installer's general command-string guarantees are Property 24's job;
# what is asserted here is that the flag is the whole of the difference.

#: Values a Bootcamper's install depends on that this repository must not spell
#: twice. Read from the contract and the installer rather than restated here:
#: a test that spells one of them would itself become a second home.
TOOL_NAMES_SET = "tool-names"
SCRIPTS_DIR_STRATEGY_SET = "scripts-dir-strategy"

#: Trees the single-home sweep does not read, with the reason each is exempt:
#:
#:   * `powers/senzing-bootcamp/` is **generated output** (task 14.1). Every
#:     occurrence there is derived from the contract by a rebuild, which is the
#:     mechanism these tests are about rather than a violation of it — and the
#:     golden-tree integration check is what holds it to a fresh build.
#:   * `.kiro/` holds the spec documents. `design.md` and `tasks.md` record the
#:     decision that the contract is the single home, and quote the value while
#:     doing so; they are not read by any build step, so a value there is
#:     documentation of the arrangement, not a second input to it.
_SWEEP_EXEMPT_PREFIXES = (f"{POWER_DIR}/", ".kiro/")

#: The built Power's two hook destinations, as repo-relative directories. The
#: derived half of the A3 and A4 claims is asserted against both, because Tier 3
#: is materialized from the same authored source and must carry the same values.
_BUILT_HOOK_DIRS = tuple(
    f"{POWER_DIR}/{dest.rstrip('/')}" for dest in HOOK_DESTS_BY_TIER.values()
)


def _substitution_sets() -> dict[str, Any]:
    sets = _load_contract().get("substitutionSets")
    assert isinstance(sets, dict), f"{CONTRACT_PATH} declares no `substitutionSets` map"
    return sets


def _substitution_set(name: str) -> list[dict[str, Any]]:
    """One named substitution set's entries, as declared (R3 AC1)."""
    sets = _substitution_sets()
    entries = sets.get(name)
    assert isinstance(entries, list) and entries, (
        f"{CONTRACT_PATH} declares no non-empty `{name}` substitution set; it is "
        "the single home of a value the Test_Checklist may correct"
    )
    for index, entry in enumerate(entries):
        assert isinstance(entry, dict), f"{name}[{index}] is not a mapping"
    return entries


def _sole_substitution(name: str) -> tuple[str, str]:
    """The `find` and `replace` of a set that must hold exactly one entry.

    "Exactly one" is the point: a second entry would be a second value to correct
    after the same observation, which is what R3 AC4 rules out.
    """
    entries = _substitution_set(name)
    assert len(entries) == 1, (
        f"the `{name}` set must hold exactly one entry, so correcting the value it "
        f"carries is a one-line edit; found {len(entries)}: {entries}"
    )
    (entry,) = entries
    assert entry.get("literal") is True, (
        f"the `{name}` entry must be a literal substitution, not a regex: an "
        f"anchored pattern would put part of the value in the pattern; found {entry}"
    )
    find, replace = entry.get("find"), entry.get("replace")
    assert isinstance(find, str) and find.strip(), f"{name}: `find` is empty: {entry}"
    assert isinstance(replace, str) and replace.strip(), (
        f"{name}: `replace` is empty: {entry}"
    )
    assert find != replace, (
        f"{name}: `find` and `replace` are both {find!r}, so the set rewrites "
        "nothing and the authored value is already the resolved one"
    )
    return find, replace


@lru_cache(maxsize=1)
def _authored_text_files() -> tuple[Path, ...]:
    """Every readable committed text file that a build step could read.

    Generated output and the spec documents are exempt for the reasons recorded
    at `_SWEEP_EXEMPT_PREFIXES`. A file that does not decode as UTF-8 is a binary
    asset and cannot spell a value, so it is skipped rather than reported.
    """
    found: list[Path] = []
    for path in _walk_repo():
        relative = _relative(path)
        if relative.startswith(_SWEEP_EXEMPT_PREFIXES):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found.append(path)
    return tuple(found)


def _authored_occurrences(value: str) -> dict[str, int]:
    """Repo-relative path → occurrence count, for every authored file spelling `value`."""
    counts: dict[str, int] = {}
    for path in _authored_text_files():
        count = path.read_text(encoding="utf-8").count(value)
        if count:
            counts[_relative(path)] = count
    return counts


def _json_string_sites(document: Any, pointer: str = "") -> Iterator[tuple[str, str]]:
    """Every string in a JSON document, with a JSON-pointer-ish path to it.

    Used to ask *where* a value appears in the coverage map rather than merely
    whether it does: the map documents the A4 vocabulary, so the question is
    whether any position other than the vocabulary listing **selects** a value.
    """
    if isinstance(document, str):
        yield pointer, document
    elif isinstance(document, dict):
        for key, value in document.items():
            yield from _json_string_sites(value, f"{pointer}/{key}")
    elif isinstance(document, list):
        for index, value in enumerate(document):
            yield from _json_string_sites(value, f"{pointer}/{index}")


def _shipped_kiro_owned_files() -> tuple[Path, ...]:
    """Every authored `kiro-owned` file the transform materializes into the Power.

    Bytecode caches are excluded because the contract's `ignore` list excludes
    them: a `.pyc` sitting beside the installer is a byproduct of importing it,
    it never ships, and it carries every string of the module it was compiled
    from — so counting one would report the installer twice.
    """
    return tuple(
        sorted(
            path
            for path in (REPO_ROOT / KIRO_OWNED_TEMPLATE_ROOT).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
        )
    )


def _built_hook_documents() -> dict[str, dict[str, Any]]:
    """Every hook definition in the built Power, keyed by repo-relative path."""
    documents: dict[str, dict[str, Any]] = {}
    for directory in _BUILT_HOOK_DIRS:
        root = REPO_ROOT / directory
        assert root.is_dir(), (
            f"{directory} is missing from the built Power; the contract's "
            f"'{HOOK_RULE_ID}' rule materializes the definitions at both tiers"
        )
        for filename in SHIPPED_HOOK_FILENAMES:
            path = root / filename
            assert path.is_file(), f"{directory}/{filename} is missing"
            documents[f"{directory}/{filename}"] = json.loads(
                path.read_text(encoding="utf-8")
            )
    return documents


def _built_coverage_maps() -> dict[str, str]:
    """The built Power's coverage maps, as text, keyed by repo-relative path."""
    maps: dict[str, str] = {}
    for directory in _BUILT_HOOK_DIRS:
        path = REPO_ROOT / directory / COVERAGE_MAP_FILENAME
        assert path.is_file(), f"{directory}/{COVERAGE_MAP_FILENAME} is missing"
        maps[f"{directory}/{COVERAGE_MAP_FILENAME}"] = path.read_text(encoding="utf-8")
    return maps


# --- A3: the Kiro write-tool matcher has exactly one home (R6 AC11) ---------


def test_the_kiro_write_tool_matcher_is_one_contract_value_and_nothing_else():
    """The Kiro matcher regex is spelled in exactly one authored place (R3 AC4).

    Assumption A3 is unverified: checklist step 11 captures the tool names a
    `PreToolUse` matcher actually sees, and the pattern may be wrong. Correcting
    it must be one line of `contract.yaml` plus a rebuild, so the pattern may
    appear in exactly one authored file, once — and this test reads it from that
    file rather than restating it, so the test cannot become the second home.
    """
    _, kiro_matcher = _sole_substitution(TOOL_NAMES_SET)
    occurrences = _authored_occurrences(kiro_matcher)
    assert occurrences == {CONTRACT_PATH: 1}, (
        f"the Kiro write-tool matcher {kiro_matcher!r} must be written down exactly "
        f"once, as the `{TOOL_NAMES_SET}` replacement in {CONTRACT_PATH}; found it "
        f"in {occurrences}. Every other place must carry the template's spelling "
        "and let the contract rewrite it, or a step 11 correction becomes an edit "
        "in two files"
    )


def test_the_authored_hook_assets_carry_the_template_matcher_not_the_kiro_one():
    """The assets are authored pre-substitution, in the template's vocabulary.

    This is the other half of the single-home claim: the shipped `PreToolUse`
    definition and the coverage map spell the matcher the *template* carries, and
    the `kiro-hooks` rule declares the `tool-names` set that rewrites it. So the
    Kiro spelling arrives by rebuild, and a hand-patched asset is not how a
    step 11 correction lands.
    """
    template_matcher, kiro_matcher = _sole_substitution(TOOL_NAMES_SET)

    declared = _hook_rule().get("substitutions") or []
    assert TOOL_NAMES_SET in declared, (
        f"the '{HOOK_RULE_ID}' rule must declare the `{TOOL_NAMES_SET}` set, or the "
        "authored matcher is never rewritten and the shipped hook matches the "
        f"template's tool names; it declares {declared}"
    )

    matchers = {
        f"{filename}:{hook['name']}": hook["matcher"]
        for filename in SHIPPED_HOOK_FILENAMES
        for hook in _shipped_hooks(filename)
        if "matcher" in hook
    }
    assert matchers, (
        "no shipped hook declares a `matcher`; the write gate matches on tool name, "
        "so one is owed"
    )
    assert set(matchers.values()) == {template_matcher}, (
        f"every authored matcher must be the template's {template_matcher!r}, which "
        f"the contract rewrites to {kiro_matcher!r} at build time; found {matchers}"
    )

    for event_id, event in _coverage_events().items():
        mechanism = event.get("kiroMechanism") or {}
        if "matcher" not in mechanism:
            continue
        assert mechanism["matcher"] == template_matcher, (
            f"{COVERAGE_MAP_PATH}: events[{event_id}].kiroMechanism.matcher is "
            f"{mechanism['matcher']!r}; the map is pre-substitution content like "
            f"the assets beside it, so it carries {template_matcher!r}"
        )
        template_names = event.get("templateMatcher")
        assert isinstance(template_names, list) and template_names, (
            f"{COVERAGE_MAP_PATH}: events[{event_id}] must record what the template "
            "matched as a list of tool names, so the record survives the rewrite"
        )
        assert "|".join(template_names) == template_matcher, (
            f"{COVERAGE_MAP_PATH}: events[{event_id}].templateMatcher "
            f"{template_names} does not join to the `{TOOL_NAMES_SET}` find value "
            f"{template_matcher!r}; one of the two is stale"
        )


def test_the_built_power_carries_the_matcher_the_contract_declares():
    """The rebuild is what puts the Kiro matcher in the Power (R3 AC4, R6 AC11).

    Asserted at both tiers, because Tier 2 and Tier 3 are materialized from the
    same authored source: a step 11 correction plus a rebuild has to move both,
    and a built tree still carrying the template's spelling means the rebuild was
    skipped.
    """
    template_matcher, kiro_matcher = _sole_substitution(TOOL_NAMES_SET)
    found: dict[str, str] = {}
    for path, document in _built_hook_documents().items():
        for hook in document.get("hooks") or []:
            if "matcher" in hook:
                found[f"{path}:{hook['name']}"] = hook["matcher"]
    assert found, f"no built hook definition under {list(_BUILT_HOOK_DIRS)} declares a matcher"
    assert set(found.values()) == {kiro_matcher}, (
        f"every built matcher must be the contract's {kiro_matcher!r}; found "
        f"{found}. A matcher reading {template_matcher!r} means the contract was "
        "changed without rebuilding the Power"
    )
    for path, text in _built_coverage_maps().items():
        assert kiro_matcher in text, (
            f"{path} does not carry the Kiro matcher {kiro_matcher!r}; the coverage "
            "map records the mechanism the built Power actually installs"
        )


# --- A2: interpreter and script-path resolution live in one file (R16 AC3) ---


def test_interpreter_resolution_lives_only_in_the_hook_installer():
    """One file reads the interpreter, so the A2 outcome changes no asset (R16 AC3).

    `sys.executable` is the interpreter path's single source, and it is read in
    the installer because the interpreter that will run the hooks is the
    interpreter that resolves them. Scoped to what actually ships inside the
    Power: a test helper reading `sys.executable` to launch a subprocess is not a
    second resolution site a Bootcamper's install depends on.
    """
    readers = sorted(
        _relative(path)
        for path in _shipped_kiro_owned_files()
        if path.suffix == ".py"
        and "sys.executable" in path.read_text(encoding="utf-8", errors="ignore")
    )
    assert readers == [INSTALLER_PATH], (
        "the interpreter path must be resolved in exactly one shipped file, "
        f"{INSTALLER_PATH}; found `sys.executable` in {readers}"
    )


def test_no_shipped_asset_other_than_the_installer_resolves_a_placeholder():
    """Resolution is the installer's job and only its job (R7 AC6, R16 AC3, AC4).

    Every shipped file that mentions a placeholder either *carries* it — the hook
    definitions and the coverage map that documents them — or *resolves* it, and
    only the installer does the second. Whatever checklist step 10 says about
    `${PLUGIN_ROOT}` expansion, no asset changes: the asset ships placeholders
    either way.
    """
    installer = _installer()
    placeholders = (installer.PLACEHOLDER_INTERPRETER, installer.PLACEHOLDER_SCRIPTS_DIR)
    carriers = {f"{HOOK_ASSETS_DIR}/{name}" for name in SHIPPED_HOOK_FILENAMES}
    carriers.add(COVERAGE_MAP_PATH)
    allowed = carriers | {INSTALLER_PATH}

    mentions = sorted(
        _relative(path)
        for path in _shipped_kiro_owned_files()
        if any(
            token in path.read_text(encoding="utf-8", errors="ignore")
            for token in placeholders
        )
    )
    unexpected = sorted(set(mentions) - allowed)
    assert unexpected == [], (
        f"these shipped files mention {list(placeholders)} but neither carry a "
        f"command string nor resolve one: {unexpected}. Resolution belongs to "
        f"{INSTALLER_PATH} alone"
    )
    missing = sorted(carriers - set(mentions))
    assert missing == [], (
        f"these shipped assets must carry the placeholders unresolved: {missing}"
    )


def test_no_substitution_set_can_reach_a_command_string():
    """No contract value names a placeholder or an interpreter (R16 AC3, AC5).

    The reason A2 costs nothing to get wrong: the build has no lever over a
    command string at all. If a set could rewrite a placeholder, the resolution
    decision would live in two places — the contract and the installer — and the
    shipped asset could ship an interpreter name.
    """
    installer = _installer()
    placeholders = (installer.PLACEHOLDER_INTERPRETER, installer.PLACEHOLDER_SCRIPTS_DIR)
    offenders: dict[str, list[str]] = {}
    for name, entries in _substitution_sets().items():
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            for field_name in ("find", "pattern", "replace"):
                value = entry.get(field_name)
                if not isinstance(value, str):
                    continue
                reasons = [
                    f"names {token}" for token in placeholders if token in value
                ]
                found = _INTERPRETER_WORD.search(value)
                if found:
                    reasons.append(f"names the interpreter {found.group(0)!r}")
                if reasons:
                    offenders[f"{name}[{index}].{field_name}"] = reasons
    assert offenders == {}, (
        "no substitution set may name a Hook_Command_String placeholder or an "
        f"interpreter: {offenders}. Both are resolved at install time by "
        f"{INSTALLER_PATH}, which is the whole of why assumption A2 changes no "
        "hook asset"
    )


def test_the_built_hook_commands_are_still_unresolved_placeholder_pairs():
    """A built command carries the placeholders, not a path (R16 AC3, AC5).

    The shipped asset is deliberately not runnable: it becomes runnable when the
    installer resolves it against the machine it is being installed on. A built
    command carrying an absolute path would mean the build resolved something it
    cannot know, and every install would inherit the build machine's interpreter.
    """
    installer = _installer()
    for path, document in _built_hook_documents().items():
        for hook in document.get("hooks") or []:
            command = hook["action"]["command"]
            tokens = installer.tokenize_command(command)
            assert tokens[:1] == (installer.PLACEHOLDER_INTERPRETER,), (
                f"{path}: {hook['name']} names {tokens[:1]} in the interpreter "
                f"position; a built asset carries {installer.PLACEHOLDER_INTERPRETER}"
            )
            assert tokens[1].startswith(installer.PLACEHOLDER_SCRIPTS_DIR + "/"), (
                f"{path}: {hook['name']} script path {tokens[1]!r} is already "
                "resolved; the installer resolves it at install time"
            )
            assert installer.find_shell_constructs(command) == (), (
                f"{path}: {hook['name']} command carries a shell construct"
            )


# --- A4: the scripts-directory strategy is one contract flag (R7 AC6) -------


def test_the_scripts_directory_strategy_is_selected_once_in_the_contract():
    """The A4 choice is one contract value the installer reads (R3 AC4, R7 AC6).

    `find` is the placeholder the authored coverage map carries and `replace` is
    the selection, which must be a strategy the installer actually implements —
    a value it cannot implement would install hooks pointing somewhere nobody
    chose, which is why the installer fails closed on one.
    """
    installer = _installer()
    placeholder, chosen = _sole_substitution(SCRIPTS_DIR_STRATEGY_SET)
    assert placeholder == installer.PLACEHOLDER_SCRIPTS_DIR_STRATEGY, (
        f"the `{SCRIPTS_DIR_STRATEGY_SET}` set must fill the placeholder the "
        f"installer expects, {installer.PLACEHOLDER_SCRIPTS_DIR_STRATEGY!r}; it "
        f"fills {placeholder!r}"
    )
    assert chosen in installer.SCRIPTS_DIR_STRATEGIES, (
        f"the contract selects strategy {chosen!r}, which {INSTALLER_PATH} does not "
        f"implement; implemented strategies are {list(installer.SCRIPTS_DIR_STRATEGIES)}"
    )
    declared = _hook_rule().get("substitutions") or []
    assert SCRIPTS_DIR_STRATEGY_SET in declared, (
        f"the '{HOOK_RULE_ID}' rule must declare the `{SCRIPTS_DIR_STRATEGY_SET}` "
        f"set, or the coverage map ships the unresolved placeholder; it declares "
        f"{declared}"
    )


def test_the_installer_implements_exactly_the_two_designed_strategies():
    """The vocabulary is the installer's, and it is the design's two (R7 AC6).

    A third strategy would be a third behavior with no contract value naming it
    and no checklist step observing it, so it fails here rather than shipping
    unreachable.
    """
    installer = _installer()
    assert set(installer.SCRIPTS_DIR_STRATEGIES) == {
        installer.SCRIPTS_DIR_STRATEGY_IN_POWER,
        installer.SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY,
    }, (
        "the installer must implement exactly the design's two A4 strategies; it "
        f"declares {list(installer.SCRIPTS_DIR_STRATEGIES)}"
    )
    assert installer.DEFAULT_SCRIPTS_DIR_STRATEGY == (
        installer.SCRIPTS_DIR_STRATEGY_IN_POWER
    ), (
        "the default must be the non-copying strategy: writing a copy of the "
        "script set into somebody's workspace is the consequential choice, so it "
        "is never the one made by a missing or unresolved coverage map"
    )
    assert installer.WORKSPACE_SCRIPTS_DIRECTORY_NAME.startswith(
        installer.HOOK_FILENAME_PREFIX
    ), (
        "the workspace copy directory must carry the "
        f"{installer.HOOK_FILENAME_PREFIX!r} prefix, or removal cannot delete "
        f"exactly what was written; it is "
        f"{installer.WORKSPACE_SCRIPTS_DIRECTORY_NAME!r} (R7 AC9, AC10)"
    )


def test_no_authored_asset_selects_a_scripts_directory_strategy():
    """The assets carry the placeholder and the vocabulary, never a choice (R3 AC4).

    The coverage map documents both strategies — that is what makes the flag
    readable — so the claim is not "the value appears once in the repository" but
    "exactly one position **selects** it". The map's effective field carries the
    placeholder, every other occurrence in the map sits in the vocabulary listing,
    and no file outside the contract, the installer, and the map mentions a
    strategy at all.
    """
    installer = _installer()
    _, chosen = _sole_substitution(SCRIPTS_DIR_STRATEGY_SET)
    coverage_map = _load_coverage_map()

    assert coverage_map.get(installer.SCRIPTS_DIR_STRATEGY_FIELD) == (
        installer.PLACEHOLDER_SCRIPTS_DIR_STRATEGY
    ), (
        f"{COVERAGE_MAP_PATH}.{installer.SCRIPTS_DIR_STRATEGY_FIELD} must be the "
        f"unresolved {installer.PLACEHOLDER_SCRIPTS_DIR_STRATEGY!r}; it reads "
        f"{coverage_map.get(installer.SCRIPTS_DIR_STRATEGY_FIELD)!r}, which is a "
        "second selection the contract does not own"
    )

    vocabulary = re.compile(r"^/scriptsDirectory/strategies/\d+/value$")
    selections = sorted(
        pointer
        for pointer, value in _json_string_sites(coverage_map)
        if value in installer.SCRIPTS_DIR_STRATEGIES and not vocabulary.match(pointer)
    )
    assert selections == [], (
        f"{COVERAGE_MAP_PATH} spells a strategy value outside its vocabulary "
        f"listing, at {selections}; only the contract selects"
    )

    # The four places a strategy value may legitimately be spelled, and the role
    # each one plays. Only the first selects; the other three describe.
    #
    #   contract        the selection (R3 AC4)
    #   installer       the vocabulary, and the two implementations
    #   coverage map    the documented pair, so the flag is readable
    #   checklist       the fold-in instruction: it tells the Maintainer which
    #                   value to write into the contract after step 10, and
    #                   nothing reads it. A value here that no longer matches the
    #                   installer's vocabulary is caught by the assertions above,
    #                   which read the vocabulary from the installer.
    allowed = {CONTRACT_PATH, INSTALLER_PATH, COVERAGE_MAP_PATH, CHECKLIST_PATH}
    mentions = set(_authored_occurrences(chosen)) | set(
        _authored_occurrences(installer.SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY)
    )
    unexpected = sorted(mentions - allowed)
    assert unexpected == [], (
        f"these authored files spell an A4 strategy value: {unexpected}. The "
        f"choice lives in {CONTRACT_PATH}, the vocabulary in {INSTALLER_PATH}, the "
        f"documented pair in {COVERAGE_MAP_PATH}, and the fold-in instruction in "
        f"{CHECKLIST_PATH}; nothing else"
    )


def test_the_built_power_carries_the_strategy_the_contract_selects():
    """The rebuild is what puts the A4 selection in the Power (R3 AC4, R7 AC6).

    The installer reads this field from the built Power, so a contract edit that
    was not followed by a rebuild leaves the installer resolving script paths the
    old way while the contract says otherwise.
    """
    installer = _installer()
    _, chosen = _sole_substitution(SCRIPTS_DIR_STRATEGY_SET)
    for path, text in _built_coverage_maps().items():
        document = json.loads(text)
        assert document.get(installer.SCRIPTS_DIR_STRATEGY_FIELD) == chosen, (
            f"{path}.{installer.SCRIPTS_DIR_STRATEGY_FIELD} reads "
            f"{document.get(installer.SCRIPTS_DIR_STRATEGY_FIELD)!r}; the contract "
            f"selects {chosen!r}. Re-run the build"
        )
        assert installer.PLACEHOLDER_SCRIPTS_DIR_STRATEGY not in text, (
            f"{path} still carries the unresolved placeholder "
            f"{installer.PLACEHOLDER_SCRIPTS_DIR_STRATEGY!r}"
        )


def _hook_assets_under_strategy(destination: Path, strategy: str) -> Path:
    """The built Power's hook assets, copied out with `strategy` substituted in.

    Exactly what a rebuild under a flipped contract line produces: the same
    definitions byte-for-byte, with the coverage map's one contract-owned field
    carrying the other value. Built from the *built* Power rather than the
    authored tree so the definitions are the resolved ones the installer reads.
    """
    installer = _installer()
    source = REPO_ROOT / POWER_DIR / installer.HOOK_ASSETS_RELATIVE_PATH
    assert source.is_dir(), f"the built Power has no hook assets at {source}"
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.iterdir()):
        if path.is_file():
            (destination / path.name).write_bytes(path.read_bytes())
    map_path = destination / COVERAGE_MAP_FILENAME
    document = json.loads(map_path.read_text(encoding="utf-8"))
    document[installer.SCRIPTS_DIR_STRATEGY_FIELD] = strategy
    map_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return destination


def test_the_two_strategy_asset_sets_differ_only_in_the_contract_owned_field(tmp_path):
    """Flipping the flag changes one field of one file, and nothing else (R3 AC4).

    The premise the behavioral test below rests on: the two builds it compares
    are the same assets with one value different, so any difference in the
    installer's plan is attributable to the flag rather than to a second edit.
    """
    installer = _installer()
    in_power = _hook_assets_under_strategy(
        tmp_path / "assets-default", installer.SCRIPTS_DIR_STRATEGY_IN_POWER
    )
    workspace_copy = _hook_assets_under_strategy(
        tmp_path / "assets-fallback", installer.SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY
    )

    names = sorted(path.name for path in in_power.iterdir())
    assert names == sorted(path.name for path in workspace_copy.iterdir())
    differing = [
        name
        for name in names
        if (in_power / name).read_bytes() != (workspace_copy / name).read_bytes()
    ]
    assert differing == [COVERAGE_MAP_FILENAME], (
        "the two asset sets must differ in the coverage map alone; they differ in "
        f"{differing}"
    )
    left = json.loads((in_power / COVERAGE_MAP_FILENAME).read_text(encoding="utf-8"))
    right = json.loads(
        (workspace_copy / COVERAGE_MAP_FILENAME).read_text(encoding="utf-8")
    )
    assert left.pop(installer.SCRIPTS_DIR_STRATEGY_FIELD) != right.pop(
        installer.SCRIPTS_DIR_STRATEGY_FIELD
    )
    assert left == right, (
        "the coverage maps must differ in "
        f"{installer.SCRIPTS_DIR_STRATEGY_FIELD} alone"
    )


def _script_token(installer: Any, command: str) -> str:
    tokens: Sequence[str] = installer.tokenize_command(command)
    assert len(tokens) == 2, f"expected [interpreter, script]; got {tokens}"
    return tokens[1]


@pytest.mark.parametrize(
    "strategy",
    ["SCRIPTS_DIR_STRATEGY_IN_POWER", "SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY"],
)
def test_the_contract_flag_alone_decides_where_hook_scripts_resolve(
    tmp_path, strategy: str
):
    """The flag is the whole of the difference, install through removal (R7 AC6-AC10).

    The A4 fallback earning its place depends on this: with the contract's one
    field flipped and nothing else touched, the installer resolves
    `<ABSOLUTE_SCRIPTS_DIR>` to a workspace copy it makes itself, and every other
    guarantee holds unchanged — every path disclosed before a byte is written
    *(AC7)*, a second run changing nothing *(AC8)*, everything written under the
    `senzing-bootcamp-` prefix *(AC9)*, and removal deleting exactly that and
    leaving another tool's hook file alone *(AC10)*.

    Parametrized by constant *name* rather than by value, so this test does not
    spell a strategy either.
    """
    installer = _installer()
    selected = getattr(installer, strategy)
    copying = selected == installer.SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY

    power_root = REPO_ROOT / POWER_DIR
    assets = _hook_assets_under_strategy(tmp_path / "assets", selected)
    workspace = tmp_path / "workspace"
    hooks_directory = workspace / installer.WORKSPACE_HOOKS_RELATIVE_PATH
    hooks_directory.mkdir(parents=True)
    foreign = hooks_directory / "other-tool.json"
    foreign.write_text('{"version": "v1", "hooks": []}\n', encoding="utf-8")

    plan = installer.build_install_plan(
        workspace=workspace, power_root=power_root, hook_assets=assets
    )

    # The flag was read, not guessed, and it is the one the assets carry.
    assert plan.scripts_directory_strategy == selected

    expected_scripts = (
        installer.resolve_workspace_scripts_directory(hooks_directory)
        if copying
        else installer.resolve_scripts_directory(power_root)
    )
    assert plan.scripts_directory == expected_scripts, (
        f"under {selected!r} the hook commands must name {expected_scripts}; the "
        f"plan resolved {plan.scripts_directory}"
    )
    assert plan.script_source_directory == installer.resolve_scripts_directory(
        power_root
    ), "the copy's source is always the Power's own ported script set"

    for write in plan.writes:
        for command in write.commands:
            script = _script_token(installer, command)
            assert script.startswith(str(expected_scripts)), (
                f"{write.destination.name}: command names {script!r}, which is not "
                f"under {expected_scripts}"
            )
        assert write.destination.name.startswith(installer.HOOK_FILENAME_PREFIX)

    assert bool(plan.copies) is copying, (
        f"under {selected!r} the plan must "
        f"{'copy the ported script set' if copying else 'copy nothing'}; it plans "
        f"{len(plan.copies)} copies"
    )
    for copy in plan.copies:
        assert copy.destination.is_relative_to(expected_scripts)
        assert copy.source.is_relative_to(plan.script_source_directory)

    # Disclosure first: every path, before a byte is written (R7 AC7).
    disclosure = installer.disclosure_text(plan)
    for path in plan.paths:
        assert str(path) in disclosure, f"{path} is written but not disclosed"
    assert str(foreign) in disclosure and foreign in plan.preserved
    assert not any(
        item.name.startswith(installer.HOOK_FILENAME_PREFIX)
        for item in hooks_directory.iterdir()
    ), "planning must write nothing"

    installer.apply_plan(plan)
    for write in plan.writes:
        assert write.destination.is_file()
    for copy in plan.copies:
        assert copy.destination.read_bytes() == copy.source.read_bytes()
    assert foreign.is_file(), "an unrelated workspace hook file must survive install"

    # Idempotent under either strategy (R7 AC8).
    again = installer.build_install_plan(
        workspace=workspace, power_root=power_root, hook_assets=assets
    )
    assert [write.state for write in again.writes] == ["unchanged"] * len(again.writes)
    assert [copy.state for copy in again.copies] == ["unchanged"] * len(again.copies)
    assert again.removals == (), (
        f"a second run plans removals {[str(r.destination) for r in again.removals]}"
    )

    # Removal deletes exactly what was written, copy included (R7 AC10).
    removal = installer.build_removal_plan(
        workspace=workspace, power_root=power_root, hook_assets=assets
    )
    removed = {item.destination for item in removal.removals}
    assert removed == set(plan.paths), (
        "removal must name exactly the files the install wrote; it names "
        f"{sorted(str(path) for path in removed ^ set(plan.paths))} differently"
    )
    assert foreign in removal.preserved
    installer.apply_plan(removal)
    survivors = sorted(path.name for path in hooks_directory.iterdir())
    assert survivors == [foreign.name], (
        f"removal must leave only files this Power never wrote; found {survivors}"
    )


# ===========================================================================
# This repository's own identity — the watch guard, and the five places
# that name it
# ===========================================================================
#
# THE WATCH WORKFLOW HAD NEVER RUN. Its job-level guard read
# `github.repository == 'docktermj/senzing-bootcamp-kiro-powers-development'` —
# *powers*, plural — while the repository is `senzing-bootcamp-kiro-power-development`,
# singular. The condition was therefore false on every scheduled run, silently and
# successfully, and two upstream Template_Releases came and went without an issue
# being filed. A guard exists to stop forks from filing issues about upstream; one
# naming a repository that does not exist stops everything.
#
# Nothing caught it, and the reason is worth stating because it shapes what this
# section asserts. All six declaring locations agreed *with each other* — the
# plural was copied consistently — so an internal-consistency check would have
# passed. What was missing was an anchor to reality. So there are two assertions
# here, and the second is the one that matters:
#
#   1. every place that names this repository names the same one;
#   2. that name is the repository this checkout actually is, read from git.
#
# The second degrades to a skip rather than a failure when git metadata is
# unavailable — a source tarball, an export, a vendored copy — because in that
# situation the test genuinely cannot know the answer, and a test that fails when
# it cannot know teaches people to ignore it. Wherever git *is* present, which is
# every developer checkout and every CI run, the anchor holds.

#: The workflow's job-level fork guard, and the slug inside it.
_REPOSITORY_GUARD = re.compile(
    r"github\.repository\s*==\s*'(?P<slug>[^']+)'"
)

#: A GitHub repository URL, as `homepage` and `repository` spell it.
_REPOSITORY_URL = re.compile(
    r"https://github\.com/(?P<slug>[\w.-]+/[\w.-]+?)(?:\.git)?/?$"
)

#: An `owner/name` slug appearing in prose, as the skills' `compatibility` field
#: spells it. Anchored on this repository's owner so the pattern cannot pick up
#: the *template* repository, which the same documents also name.
_THIS_OWNER = "docktermj"
_PROSE_SLUG = re.compile(rf"\b{_THIS_OWNER}/[\w.-]+")


def _git_repository_slug() -> str | None:
    """This checkout's `owner/name` per git, or `None` when git cannot say.

    `origin` covers both shapes a remote takes — `git@github.com:owner/name.git`
    and `https://github.com/owner/name` — because the SSH form is what a developer
    clones and the HTTPS form is what `actions/checkout` configures.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    url = completed.stdout.strip()
    if not url:
        return None
    if url.startswith("git@"):
        _, _, path = url.partition(":")
    else:
        match = _REPOSITORY_URL.match(url)
        path = match.group("slug") if match else ""
    slug = path.removesuffix(".git").strip("/")
    return slug or None


def _declared_repository_slugs() -> dict[str, str]:
    """Every place this repository names itself, keyed by where it says it."""
    declared: dict[str, str] = {}

    guard = _REPOSITORY_GUARD.search(_watch_workflow_text())
    assert guard is not None, (
        f"{WATCH_WORKFLOW_PATH} declares no `github.repository ==` guard, so a "
        "fork would file issues about upstream releases in its own tracker"
    )
    declared[f"{WATCH_WORKFLOW_PATH} job guard"] = guard.group("slug")

    manifest = _maintainer_plugin_manifest()
    for field in ("homepage", "repository"):
        value = str(manifest.get(field) or "")
        match = _REPOSITORY_URL.match(value)
        assert match is not None, (
            f"{MAINTAINER_PLUGIN_PATH} {field} is not a GitHub repository URL: "
            f"{value!r}"
        )
        declared[f"{MAINTAINER_PLUGIN_PATH} {field}"] = match.group("slug")

    namespace = (manifest.get("extensions") or {}).get(EXTENSION_NAMESPACE) or {}
    workspace = str(namespace.get("requiresWorkspace") or "")
    assert workspace, (
        f"{MAINTAINER_PLUGIN_PATH} must record the workspace its skills require "
        f'under extensions["{EXTENSION_NAMESPACE}"].requiresWorkspace'
    )
    declared[f"{MAINTAINER_PLUGIN_PATH} requiresWorkspace"] = workspace

    for skill in sorted(MAINTAINER_TRIGGER_PHRASES):
        path = f"{MAINTAINER_SKILLS_DIR}/{skill}/{SKILL_ENTRY_POINT}"
        compatibility = str(
            _maintainer_skill_frontmatter(skill).get("compatibility") or ""
        )
        found = _PROSE_SLUG.search(compatibility)
        assert found is not None, (
            f"{path} compatibility must name the workspace repository its commands "
            f"are relative to; it reads {compatibility!r}"
        )
        declared[f"{path} compatibility"] = found.group(0)

    return declared


def test_every_place_that_names_this_repository_names_the_same_one():
    """One repository, one spelling, across the guard, the manifest and the skills.

    The maintainer skills state the workspace their repo-relative commands require,
    the manifest states where the Power lives and what workspace it needs, and the
    workflow states which repository may file issues. All five are the same fact,
    so a rename that reaches four of them leaves the fifth pointing somewhere that
    does not exist.
    """
    declared = _declared_repository_slugs()
    distinct = sorted(set(declared.values()))
    assert len(distinct) == 1, (
        "this repository is named inconsistently: "
        + "; ".join(f"{where} says {slug!r}" for where, slug in sorted(declared.items()))
    )


def test_the_watch_guard_names_the_repository_this_checkout_actually_is():
    """The anchor to reality, and the assertion that was missing.

    Every internal copy agreeing is not enough — they all agreed on `…-powers-…`
    while the repository was `…-power-…`, and the guard was false on every
    scheduled run. Comparing against git is what makes a wrong name observable
    without waiting for an upstream release to go unreported.
    """
    actual = _git_repository_slug()
    if actual is None:
        pytest.skip(
            "no git remote is discoverable, so this checkout's own identity "
            "cannot be established here"
        )

    declared = _declared_repository_slugs()
    wrong = {
        where: slug for where, slug in declared.items() if slug != actual
    }
    assert not wrong, (
        f"git says this repository is {actual!r}, but "
        + "; ".join(f"{where} says {slug!r}" for where, slug in sorted(wrong.items()))
        + ". The watch workflow's guard is compared against `github.repository` at "
        "run time, so a wrong name there means the job is skipped on every "
        "scheduled run and no upstream release is ever reported"
    )


def test_the_distribution_name_matches_the_repository_name():
    """`pyproject.toml` names the distribution after the repository it lives in.

    Included because it carried the same plural, and because it is the one place
    the name appears without an `owner/` in front of it — so a fix that swept the
    slugs could leave this behind. A PEP 508 name cannot hold a `/`, so only the
    repository half is compared.
    """
    actual = _git_repository_slug()
    if actual is None:
        pytest.skip("no git remote is discoverable")

    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    name = str((pyproject.get("project") or {}).get("name") or "")
    assert name == actual.split("/", 1)[-1], (
        f"pyproject.toml names the distribution {name!r}; this repository is "
        f"{actual!r}"
    )
