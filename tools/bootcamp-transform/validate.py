#!/usr/bin/env python3
"""Schema_Validator — the tagging gate (R13).

    validate.py --staging <dir> --tag <semver> --report <path.json>
                [--contract contract.yaml] [--source <resolved-release-tree>]

This module is the *harness*: the report model, the check registry, the runner
that collects every finding, and the gate. The individual checks register
themselves into the registry below; each one is an independent function over a
`ValidationContext` and adds nothing to this file's control flow.

Three design principles are load-bearing here, and each is realized in code
rather than left to a caller's discipline:

1. **Report everything, not the first thing.** `run_checks` runs *every*
   declared check and collects *every* finding before returning, so one run
   tells the Maintainer the full remaining work rather than the first item of
   it (*Property 15*).
2. **Fail closed.** A check that cannot reach a verdict records a **fail**, not
   a pass: a check that raises, a check that returns no result, a check the
   design declares but nothing has implemented, and a staging tree that cannot
   be read all land as failures. `tagAllowed` is derived, never assigned, so no
   code path can hand out permission by omission.
3. **Distinguish failure kinds.** `status` is three-valued. `failed` is a
   packaging problem; `incomplete` is a structurally valid artifact carrying
   residual Claude-specific references, which is a *content* problem *(R12
   AC4)*. Both block tagging *(R13 AC4)*, and the distinction survives into the
   report because they demand different Maintainer responses.

The gate is a biconditional, not a threshold: `tagAllowed` is true exactly when
every recorded result is a pass and `status == "passed"` *(R13 AC4, AC5)*. A
check result is itself derived from that check's findings — `pass` with no
findings, `fail` with any error-severity finding, `warn` with only
warning-severity ones — so a check cannot report a pass while carrying a
finding, and the biconditional holds by construction rather than by assertion.

Checks operate on a `PowerTree`: an in-memory, path-keyed view of the produced
Power. `PowerTree.from_directory` reads a staging tree; `PowerTree.from_mapping`
takes a dict a property test builds directly. Every check is therefore a pure
function of data, testable without a filesystem.

Exit codes: 0 when tagging is allowed, 1 when it is blocked (or the report
cannot be written), 2 on CLI misuse (argparse). The report is written on every
outcome — a blocked release is exactly when the Maintainer needs it.
"""

from __future__ import annotations

import argparse
import ast
import json
import posixpath
import re
import sys
import types
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import unquote

import yaml

from agent_plugins_schemas import (
    AGENT_PLUGINS_VERSION,
    MCP_SCHEMA_ID,
    PLUGIN_SCHEMA_ID,
    SCHEMAS_BY_ID,
)

# The Invariant_Discount_Register's key, its identifier field, and the fold from
# entries to the invariants they name are taken from the update path that already
# reads them rather than respelled here. The register the gate admits and the
# register the reconciliation report compares for text drift are the same section
# of the same contract (R15 AC10, AC11), so one rename must not be able to leave
# the two tools reading different documents.
from reconcile import (
    DISCOUNT_INVARIANT_FIELD,
    DISCOUNT_REGISTER_KEY,
    discount_invariant_ids,
)
from transform import (
    DEFAULT_CONTRACT,
    E_MISSING_ASSET,
    E_TRANSFORM_FAILED,
    E_WRITE_FAILED,
    EXTENSION_NAMESPACE,
    INVARIANT_CITATION,
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    MCP_SCHEMA_FIELD,
    MCP_SERVERS_FIELD,
    MCP_TRANSPORT_TYPE,
    OWNER_KIRO,
    OWNER_TEMPLATE,
    SCRIPT_SUFFIX,
    SENZING_MCP_URL,
    SENZING_SERVER_KEY,
    SKILL_METADATA_FIELD,
    SKILL_REQUIRED_FIELDS,
    SKILL_TEMPLATE_SKILL_FIELD,
    TEMPLATE_RELEASE_FIELD,
    VENDOR_SEGMENT,
    Contract,
    TransformError,
    enumerate_source,
    glob_matches,
    invariant_citations,
    load_contract,
    normalize_lf,
    sha256_hex,
    split_frontmatter,
    vendored_asset_references,
)

__all__ = [
    # Error and warning codes — the Schema_Validator subset of the catalog.
    "E_BARE_INTERPRETER",
    "E_BROKEN_IMPORT",
    "E_CHECK_UNEVALUATED",
    "E_FRONTMATTER_INVALID",
    "E_HASH_MISMATCH",
    "E_HONORED_INVARIANT_DISCOUNTED",
    "E_INCOMPLETE_DISCOUNT",
    "E_INVENTORY_MISMATCH",
    "E_MCP_INVALID",
    "E_PROGRESSION_MISMATCH",
    "E_MISSING_ASSET",
    "E_SCHEMA_INVALID",
    "E_SHELL_CONSTRUCT_IN_HOOK",
    "E_UNRESOLVED_REFERENCE",
    "E_VERSION_MISMATCH",
    "W_RESIDUAL_CLAUDE_REF",
    # Report vocabulary.
    "REPORT_VERSION",
    "RESULT_FAIL",
    "RESULT_PASS",
    "RESULT_WARN",
    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "STATUS_FAILED",
    "STATUS_INCOMPLETE",
    "STATUS_PASSED",
    # Report model.
    "Finding",
    "CheckResult",
    "ValidationReport",
    "fold_status",
    # Inputs the checks read.
    "PowerTree",
    "ValidationContext",
    "Unevaluable",
    "read_power_version",
    # Registry and runner.
    "BUILD_MANIFEST",
    "DECLARED_CHECKS",
    "MCP_MANIFEST",
    "PLUGIN_MANIFEST",
    "SKILL_MANIFEST",
    "SKILL_MD_GLOB",
    "Check",
    "check_order",
    "register_check",
    "registered_check",
    "registered_checks",
    "run_checks",
    "validate",
    "write_report",
    # The `plugin-schema` and `mcp-schema` checks (R4 AC2, AC3, R11, R13 AC1, AC2).
    "AGENT_PLUGINS_VERSION",
    "MANIFEST_SCHEMAS",
    "MCP_SCHEMA_FIELD",
    "MCP_SCHEMA_ID",
    "MCP_SERVERS_FIELD",
    "MCP_TRANSPORT_TYPE",
    "PLUGIN_SCHEMA_ID",
    "SENZING_MCP_URL",
    "SENZING_SERVER_KEY",
    "check_mcp_schema",
    "check_plugin_schema",
    "document_location",
    "json_pointer",
    "schema_findings",
    "schema_title",
    "schema_validator",
    "senzing_declaration_findings",
    # The `skill-frontmatter` check (R8 AC5, AC6, R13 AC3, AC4).
    "FRONTMATTER_RULES",
    "MAX_DESCRIPTION_LENGTH",
    "SKILL_REQUIRED_FIELDS",
    "TRIGGER_SOURCE_PRODUCED",
    "TRIGGER_SOURCE_TEMPLATE",
    "SkillFrontmatter",
    "check_skill_frontmatter",
    "declared_trigger_phrase",
    "frontmatter_findings",
    "skill_description_findings",
    "skill_directory_name",
    "skill_frontmatter_result",
    "skill_license_findings",
    "skill_name_findings",
    # The `cross-references` check (R8 AC3, AC4).
    "CROSS_REFERENCE_GLOB",
    "CROSS_REFERENCE_TARGET",
    "REFERENCE_ABSENT",
    "REFERENCE_DIRECTORY",
    "REFERENCE_ESCAPES_POWER",
    "REFERENCE_KINDS",
    "CrossReference",
    "blank_code_blocks",
    "check_cross_references",
    "cross_reference",
    "cross_reference_findings",
    "markdown_prose",
    "markdown_references",
    "reference_kind",
    "reference_path",
    "resolve_reference",
    # The `version-match` check (R2 AC3, AC4).
    "EXTENSIONS_FIELD",
    "EXTENSION_NAMESPACE",
    "POWER_VERSION_FIELD",
    "PROVENANCE_PATH",
    "TEMPLATE_RELEASE_FIELD",
    "VERSION_COMPARISONS",
    "VERSION_ROLES",
    "VERSION_ROLE_PROVENANCE",
    "VERSION_ROLE_STAMP",
    "VERSION_ROLE_TAG",
    "VersionComparison",
    "VersionStrings",
    "check_version_match",
    "version_comparisons",
    "version_match_result",
    "version_mismatch_findings",
    # The `residual-claude-refs` check (R10 AC2, R12 AC3, AC4, R15 AC8).
    "CLAUDE_ROOT_TOKEN",
    "DECLARED_CLAUDE_TERMS",
    "INVARIANT_CITATION",
    "RESIDUAL_CLIENT_NAME",
    "RESIDUAL_EFFORT_SETTING",
    "RESIDUAL_KINDS",
    "RESIDUAL_MODEL_GUIDANCE",
    "RESIDUAL_MODEL_NAME",
    "RESIDUAL_ROOT_TOKEN",
    "RESIDUAL_SUBSCRIPTION_PLAN",
    "RESIDUAL_TERM_SETS",
    "TERM_ORIGIN_DECLARED",
    "ClaudeTerm",
    "ResidualReference",
    "check_residual_claude_refs",
    "claude_terms",
    "contract_claude_terms",
    "document_text",
    "invariant_citations",
    "residual_claude_result",
    "residual_findings",
    "residual_references",
    # The `invariant-discounts` check (R15 AC4-AC6, AC11).
    "DISCOUNT_CONFLICTS_FIELD",
    "DISCOUNT_ENTRY_UNUSABLE",
    "DISCOUNT_FIELDS",
    "DISCOUNT_FIELD_ABSENT",
    "DISCOUNT_FIELD_BLANK",
    "DISCOUNT_FIELD_UNUSABLE",
    "DISCOUNT_HONORED_INVARIANT",
    "DISCOUNT_INVARIANT_FIELD",
    "DISCOUNT_KINDS",
    "DISCOUNT_REGISTER_KEY",
    "DISCOUNT_RESOLUTION_FIELD",
    "HONORED_INVARIANT",
    "DiscountEntry",
    "check_invariant_discounts",
    "declared_discounts",
    "discount_entries",
    "discount_invariant_ids",
    "discount_register_result",
    "honored_invariant_findings",
    "incomplete_discount_findings",
    "invariant_spelling",
    "names_honored_invariant",
    # The `hook-command-strings` check (R10 AC5, R16 AC3-AC6).
    "DEFAULT_HOOK_DEFINITION_GLOB",
    "HOOK_ASSETS_DIRECTORY",
    "HOOK_COVERAGE_MAP",
    "HOOK_DEFINITION_TARGET",
    "HOOK_FILENAME_PREFIX",
    "HOOK_INSTALLER_SCRIPT",
    "INSTALLER_PROBES",
    "ORIGIN_INSTALLED",
    "ORIGIN_SHIPPED",
    "SHELL_BUILTINS",
    "TIER3_HOOKS_DIRECTORY",
    "HookCommand",
    "HookCommandTools",
    "InstallerProbe",
    "check_hook_command_strings",
    "hook_command_findings",
    "hook_commands",
    "hook_definition_glob",
    "hook_definition_paths",
    "installer_findings",
    "is_absolute_command_path",
    "load_hook_command_tools",
    "load_installer_module",
    "names_bare_interpreter",
    "shell_builtin_named",
    "strip_command_placeholders",
    # The `manifest-hashes` check (R16 AC8, AC9).
    "DRIFT_ABSENT",
    "DRIFT_CONTENT",
    "DRIFT_LINE_ENDINGS",
    "DRIFT_UNRECORDED",
    "DRIFT_UNUSABLE_RECORD",
    "GITATTRIBUTES",
    "LINE_ENDING_DECLARATION",
    "MANIFEST_DRIFT_KINDS",
    "MANIFEST_UNRECORDED",
    "NORMALIZATION_EXEMPT_PATTERNS",
    "ManifestComparison",
    "ManifestDocument",
    "ManifestRecord",
    "check_manifest_hashes",
    "compare_manifest",
    "is_line_ending_rewrite",
    "normalization_exempt",
    # The `skill-inventory` check (R7 AC1, AC2, R9 AC1).
    "COMMAND_SOURCE_GLOB",
    "COMMAND_SUFFIX",
    "INVENTORY_COMMAND_DUPLICATE",
    "INVENTORY_COMMAND_MISSING",
    "INVENTORY_COMMAND_STALE",
    "INVENTORY_DOUBLE_CLAIM",
    "INVENTORY_DUPLICATE",
    "INVENTORY_KINDS",
    "INVENTORY_MISSING",
    "INVENTORY_RELOCATED",
    "INVENTORY_STALE",
    "INVENTORY_UNACCOUNTED",
    "SKILLS_DIRECTORY",
    "SKILL_INVENTORY_TARGET",
    "SKILL_METADATA_FIELD",
    "SKILL_TEMPLATE_SKILL_FIELD",
    "TEMPLATE_COMMAND_FIELD",
    "SkillProvenance",
    "check_skill_inventory",
    "command_bijection_findings",
    "command_claims",
    "command_names",
    "kiro_owned_skill_names",
    "port_claims",
    "ported_skill_names",
    "skill_bijection_findings",
    "skill_inventory",
    "skill_inventory_result",
    "skill_names",
    "skill_provenance",
    "source_prefix",
    # The `progression-order` check (R7 AC3).
    "MODULE_NAME",
    "PROGRESSION_FIRST_PHASE",
    "PROGRESSION_INTERSTITIAL_MISPLACED",
    "PROGRESSION_KINDS",
    "PROGRESSION_LAST_PHASE",
    "PROGRESSION_PHASES_MISDECLARED",
    "PROGRESSION_SECTION",
    "PROGRESSION_SEQUENCE_DIFFERS",
    "PROGRESSION_UNPLACEABLE",
    "ProgressionPhase",
    "check_progression_order",
    "interstitial_findings",
    "module_key",
    "phase_declaration_findings",
    "phase_index",
    "progression_key",
    "progression_phases",
    "progression_result",
    "progression_sequence",
    "sequence_findings",
    "unplaceable_findings",
    "unplaceable_skills",
    # The `script-imports` and `script-references` checks (R10 AC4, AC6).
    "ASSET_HOOK_SCRIPT",
    "ASSET_KINDS",
    "ASSET_MODULE",
    "ASSET_RELEASE_SHIPPED",
    "ASSET_VENDORED",
    "IMPORT_KINDS",
    "IMPORT_RELOCATED",
    "IMPORT_UNPORTED",
    "PACKAGE_MARKER",
    "POWER_ROOT_TOKEN",
    "SCRIPTS_DIR_PLACEHOLDER",
    "SCRIPT_GLOB",
    "SCRIPT_SOURCE_ROOT",
    "SCRIPT_SUFFIX",
    "SCRIPT_TARGET",
    "VENDOR_SEGMENT",
    "AssetReference",
    "ScriptImport",
    "asset_reference_path",
    "asset_reference_satisfied",
    "broken_import_findings",
    "check_script_imports",
    "check_script_references",
    "command_script_paths",
    "hook_script_references",
    "import_resolves",
    "missing_asset_findings",
    "module_providers",
    "ported_scripts_directory",
    "release_script_assets",
    "release_script_modules",
    "script_asset_references",
    "script_import_result",
    "script_imports",
    "script_paths",
    "script_reference_result",
    "supplied_paths",
    "vendored_asset_references",
    # CLI.
    "main",
]


# ---------------------------------------------------------------------------
# Error and warning codes — the Schema_Validator subset of the catalog
# ---------------------------------------------------------------------------
#
# The `E_`/`W_` prefix is not decoration: it is the severity, read back by
# `Finding.severity`. An `E_` finding fails its check and the run; a `W_`
# finding downgrades the run to `incomplete` without claiming the artifact is
# structurally broken. `E_MISSING_ASSET` is shared with the transform engine
# and imported rather than redeclared, so one condition keeps one code.

#: `plugin.json` or `mcp.json` fails its Agent Plugins schema (R13 AC1, AC2).
E_SCHEMA_INVALID = "E_SCHEMA_INVALID"
#: Senzing server missing, wrong URL, wrong type, or missing `$schema` (R11).
E_MCP_INVALID = "E_MCP_INVALID"
#: Missing/blank `name`, `description`, `license`; name/directory mismatch (R8 AC5).
E_FRONTMATTER_INVALID = "E_FRONTMATTER_INVALID"
#: A relative cross-reference between skills does not resolve (R8 AC4).
E_UNRESOLVED_REFERENCE = "E_UNRESOLVED_REFERENCE"
#: A same-directory module import between two ported scripts fails (R10 AC6).
E_BROKEN_IMPORT = "E_BROKEN_IMPORT"
#: Power version string differs from the resolved tag (R2 AC3, AC4).
E_VERSION_MISMATCH = "E_VERSION_MISMATCH"
#: An `invariantDiscounts` entry omits a required field (R15 AC5).
E_INCOMPLETE_DISCOUNT = "E_INCOMPLETE_DISCOUNT"
#: `INV-052` appears in the Invariant_Discount_Register (R15 AC6).
E_HONORED_INVARIANT_DISCOUNTED = "E_HONORED_INVARIANT_DISCOUNTED"
#: A Hook_Command_String carries a shell construct (R16 AC6).
E_SHELL_CONSTRUCT_IN_HOOK = "E_SHELL_CONSTRUCT_IN_HOOK"
#: A Hook_Command_String names a bare interpreter or leaves a path unquoted
#: (R16 AC3, AC4).
E_BARE_INTERPRETER = "E_BARE_INTERPRETER"
#: A checked-out file's hash differs from its Build_Manifest hash (R16 AC9).
E_HASH_MISMATCH = "E_HASH_MISMATCH"
#: The produced skill set is not in one-to-one correspondence with the resolved
#: release's skill directories or commands, or a skill carries neither a template
#: counterpart nor a `kiro-owned` declaration (R7 AC1, AC2, R9 AC1).
E_INVENTORY_MISMATCH = "E_INVENTORY_MISMATCH"
#: The ported bootcamp progression sequence is not the template's (R7 AC3).
E_PROGRESSION_MISMATCH = "E_PROGRESSION_MISMATCH"
#: A Claude-specific model reference survived the transformation (R12 AC3, AC4).
#: Warning severity: the artifact is structurally valid but content-incomplete.
W_RESIDUAL_CLAUDE_REF = "W_RESIDUAL_CLAUDE_REF"
#: No verdict could be obtained for a declared check. This is the fail-closed
#: code: it is recorded *instead of* a pass, never alongside one.
E_CHECK_UNEVALUATED = "E_CHECK_UNEVALUATED"


# ---------------------------------------------------------------------------
# Report vocabulary
# ---------------------------------------------------------------------------

#: `ValidationReport.reportVersion`. Bump only on an incompatible shape change.
REPORT_VERSION = 1

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

#: Per-check verdicts. `warn` exists so a residual-reference hit downgrades the
#: run without being reported as a structural failure; the checks R13 AC1-AC3
#: names emit only `E_` findings and are therefore only ever `pass` or `fail`.
RESULT_PASS = "pass"
RESULT_WARN = "warn"
RESULT_FAIL = "fail"

#: Overall outcomes. `incomplete` sits between the other two: structurally
#: valid, content-incomplete (R12 AC4). Both non-passed outcomes block tagging.
STATUS_PASSED = "passed"
STATUS_INCOMPLETE = "incomplete"
STATUS_FAILED = "failed"

EXIT_SUCCESS = 0
EXIT_BLOCKED = 1

#: Well-known paths inside a produced Power, relative to its root. The
#: Build_Manifest path is taken from the engine rather than respelled here: the
#: hash check compares against the file the engine writes, so one rename must
#: not be able to leave the validator looking at a path nothing produces.
PLUGIN_MANIFEST = "plugin.json"
MCP_MANIFEST = "mcp.json"
BUILD_MANIFEST = MANIFEST_FILENAME
SKILL_MANIFEST = "SKILL.md"
SKILL_MD_GLOB = "skills/*/SKILL.md"


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One thing wrong, named precisely enough to act on.

    Every requirement behind this validator asks for the *offending file* and
    the *violated rule* by name, so `target` and `message` are the payload and
    `code` is the catalog entry that says what response the Maintainer owes it.
    `location` carries a within-document position (a line number, a JSON
    pointer, a frontmatter key) for the checks that can supply one — R12 AC3
    requires the location as well as the document.

    `details` becomes extra keys in the serialized finding, so a consumer reads
    both sides of a mismatch as data rather than by parsing prose. Reserved
    keys (`code`, `severity`, `message`, `target`, `location`) win over
    `details` so the catalog code can never be shadowed.
    """

    code: str
    message: str
    target: str | None = None
    location: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        """`warning` for a `W_` code, `error` for everything else.

        Read from the code rather than stored beside it: one condition has one
        code, and the code already says whether the artifact is broken or
        merely incomplete.
        """
        return SEVERITY_WARNING if self.code.startswith("W_") else SEVERITY_ERROR

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.target is not None:
            payload["target"] = self.target
        if self.location is not None:
            payload["location"] = self.location
        for key, value in self.details.items():
            if key not in payload:
                payload[key] = value
        return payload


# ---------------------------------------------------------------------------
# Check results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    """One recorded result: a check id, what it looked at, and what it found.

    `result` is **derived** from `findings`, never supplied. That is what makes
    *Property 15*'s biconditional structural: a check cannot record a pass
    while carrying a finding, so "every recorded result is a pass" and "the
    report has no findings" are the same statement.

    `target` names the specific file a per-file check examined, so R13 AC3's
    "a result for *each* `SKILL.md` file" is one `CheckResult` per file rather
    than one aggregate. `extra` carries the per-check payload the design's
    report model shows — `unresolved`, `hits`, `mismatches`, `violations`,
    `powerVersion` — and is emitted between `result` and `findings`.
    """

    id: str
    target: str | None = None
    findings: tuple[Finding, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def result(self) -> str:
        if not self.findings:
            return RESULT_PASS
        if any(finding.severity == SEVERITY_ERROR for finding in self.findings):
            return RESULT_FAIL
        return RESULT_WARN

    @property
    def passed(self) -> bool:
        return self.result == RESULT_PASS

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"id": self.id}
        if self.target is not None:
            payload["target"] = self.target
        payload["result"] = self.result
        for key, value in self.extra.items():
            if key not in payload:
                payload[key] = value
        payload["findings"] = [finding.to_json() for finding in self.findings]
        return payload


def fold_status(results: Iterable[CheckResult]) -> str:
    """Fold recorded results into the three-valued overall status.

    An **empty** set of results folds to `failed`, not `passed`: a report that
    recorded nothing evaluated nothing, and permission to tag is never the
    default (design principle 1).
    """
    materialized = tuple(results)
    if not materialized:
        return STATUS_FAILED
    if any(result.result == RESULT_FAIL for result in materialized):
        return STATUS_FAILED
    if any(result.result == RESULT_WARN for result in materialized):
        return STATUS_INCOMPLETE
    return STATUS_PASSED


@dataclass(frozen=True)
class ValidationReport:
    """The one machine-readable artifact the release procedure reads.

    `status` and `tagAllowed` are both derived, so the gate cannot be set
    independently of the evidence: `tagAllowed` is true exactly when
    `status == "passed"`, which is true exactly when every recorded result is a
    pass *(R13 AC4, AC5)*.

    Nothing here reads the clock or the environment. The report is a function
    of the produced tree and the resolved tag alone, so two runs over identical
    input produce byte-identical JSON.
    """

    template_release: str
    power_version: str | None
    checks: tuple[CheckResult, ...]
    report_version: int = REPORT_VERSION

    @property
    def status(self) -> str:
        return fold_status(self.checks)

    @property
    def tag_allowed(self) -> bool:
        """The gate (R13 AC4, AC5). True only when `status == "passed"`."""
        return self.status == STATUS_PASSED

    @property
    def findings(self) -> tuple[Finding, ...]:
        """Every finding from every check, in check order."""
        return tuple(
            finding for check in self.checks for finding in check.findings
        )

    def findings_for(self, code: str) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.code == code)

    def results_for(self, check_id: str) -> tuple[CheckResult, ...]:
        return tuple(check for check in self.checks if check.id == check_id)

    def failed_check_ids(self) -> tuple[str, ...]:
        """Ids of checks with a non-passing result, first occurrence order."""
        seen: dict[str, None] = {}
        for check in self.checks:
            if not check.passed:
                seen.setdefault(check.id, None)
        return tuple(seen)

    def to_json(self) -> dict[str, Any]:
        return {
            "reportVersion": self.report_version,
            "templateRelease": self.template_release,
            "powerVersion": self.power_version,
            "status": self.status,
            "checks": [check.to_json() for check in self.checks],
            "tagAllowed": self.tag_allowed,
        }

    def summary(self) -> str:
        """One narration line: the counts a Maintainer reads first."""
        errors = sum(
            1 for finding in self.findings if finding.severity == SEVERITY_ERROR
        )
        warnings = len(self.findings) - errors
        return (
            f"{len(self.checks)} result(s) recorded, "
            f"{len(self.failed_check_ids())} check(s) not passing, "
            f"{errors} error(s), {warnings} warning(s): status {self.status}, "
            f"tagAllowed {str(self.tag_allowed).lower()}"
        )


# ---------------------------------------------------------------------------
# What a check reads
# ---------------------------------------------------------------------------


class Unevaluable(Exception):
    """A check cannot reach a verdict — an absent file, undecodable bytes, a
    malformed document, a missing input it needs.

    Raising this is how a check *declines* to answer; the runner turns it into
    a recorded fail. There is deliberately no way to decline into a pass.
    """

    def __init__(self, message: str, *, target: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.target = target


@dataclass(frozen=True)
class PowerTree:
    """A produced Power as data: POSIX relative path → bytes.

    Held in memory so every check is a pure function of a mapping. A property
    test builds one with `from_mapping` and never touches a filesystem; the CLI
    builds one with `from_directory` from the staging tree. Both produce the
    same thing, so a check has one code path.

    Reads fail loudly, by design: `read_text`, `read_json`, and `read_bytes`
    raise `Unevaluable` rather than returning a default, because a check that
    silently substitutes an empty document reaches a *wrong* verdict instead of
    no verdict.
    """

    files: Mapping[str, bytes]

    @classmethod
    def from_directory(cls, root: str | Path) -> PowerTree:
        """Read every file under `root`, sorted.

        Enumeration is delegated to the transform engine so the validator sees
        files in exactly the order the engine wrote them, and so path spelling
        (POSIX, relative, sorted) is defined in one place.
        """
        base = Path(root)
        contents: dict[str, bytes] = {}
        for entry in enumerate_source(base, ""):
            try:
                contents[entry.path] = entry.absolute.read_bytes()
            except OSError as error:
                raise TransformError(
                    E_TRANSFORM_FAILED,
                    f"cannot read produced file {entry.path}: {error}",
                    path=entry.path,
                ) from error
        return cls(files=contents)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | bytes]) -> PowerTree:
        """Build a tree from in-memory content, encoding text as UTF-8."""
        return cls(
            files={
                path: value.encode("utf-8") if isinstance(value, str) else value
                for path, value in mapping.items()
            }
        )

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(sorted(self.files))

    def __contains__(self, path: str) -> bool:
        return path in self.files

    def __len__(self) -> int:
        return len(self.files)

    def exists(self, path: str) -> bool:
        return path in self.files

    def is_directory(self, path: str) -> bool:
        """True when `path` names a directory some file in this tree sits under.

        A tree is path-keyed, so a directory exists exactly when something is in
        it; there are no empty directories to ask about. `""` and `"."` are the
        Power root, which exists when the tree carries anything at all.
        """
        if path in ("", "."):
            return bool(self.files)
        prefix = f"{path.rstrip('/')}/"
        return any(other.startswith(prefix) for other in self.files)

    def read_bytes(self, path: str) -> bytes:
        try:
            return self.files[path]
        except KeyError:
            raise Unevaluable(
                f"{path} is absent from the produced Power", target=path
            ) from None

    def read_text(self, path: str) -> str:
        raw = self.read_bytes(path)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise Unevaluable(
                f"{path} is not valid UTF-8 text: {error}", target=path
            ) from error

    def read_json(self, path: str) -> Any:
        text = self.read_text(path)
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise Unevaluable(
                f"{path} is not valid JSON: {error}", target=path
            ) from error

    def match(self, pattern: str) -> tuple[str, ...]:
        """Paths matching one contract-style POSIX glob, sorted.

        Uses the engine's glob matcher, where `*` does not cross `/`, so
        `skills/*/SKILL.md` cannot reach into `skills/x/references/`.
        """
        return tuple(path for path in self.paths if glob_matches(pattern, path))

    def skill_md_paths(self) -> tuple[str, ...]:
        """Every `skills/<name>/SKILL.md`, sorted — R13 AC3's unit of record."""
        return self.match(SKILL_MD_GLOB)


def read_power_version(tree: PowerTree) -> str | None:
    """The Power's stamped version, or `None` when it cannot be read.

    `None` is not a pass: the version-match check treats an unreadable version
    as a mismatch, and this exists so the report can still *state* what it saw
    at the top level while that check records the failure.
    """
    try:
        document = tree.read_json(PLUGIN_MANIFEST)
    except Unevaluable:
        return None
    if not isinstance(document, Mapping):
        return None
    version = document.get("version")
    return version if isinstance(version, str) else None


@dataclass(frozen=True)
class ValidationContext:
    """Everything the checks are allowed to read.

    `tree` is the produced Power, `tag` the resolved Template_Release. The two
    optional inputs are for the checks that compare the Power against something
    else: `contract` carries the Invariant_Discount_Register and the
    `kiro-owned` declarations, `source` is the resolved release tree that the
    skill-inventory bijection is measured against. A check that needs one and
    does not have it raises `Unevaluable` and so fails closed, rather than
    quietly reporting a pass it did not earn.
    """

    tree: PowerTree
    tag: str
    contract: Contract | None = None
    source: PowerTree | None = None
    staging: Path | None = None

    @property
    def power_version(self) -> str | None:
        return read_power_version(self.tree)

    def require_contract(self) -> Contract:
        if self.contract is None:
            raise Unevaluable(
                "the Transformation_Contract is required for this check but was "
                "not supplied"
            )
        return self.contract

    def require_source(self) -> PowerTree:
        if self.source is None:
            raise Unevaluable(
                "the resolved Template_Release tree is required for this check "
                "but was not supplied (pass --source)"
            )
        return self.source


# ---------------------------------------------------------------------------
# The check registry
# ---------------------------------------------------------------------------
#
# A check is a function `(ValidationContext) -> CheckResult | Iterable[...]`,
# registered by decorator. Adding a check is adding a function and a decorator;
# nothing in the runner, the report model, or the gate changes. Returning
# several results is how a per-file check records one result per file.

CheckFunction = Callable[[ValidationContext], "CheckResult | Iterable[CheckResult]"]


@dataclass(frozen=True)
class Check:
    """A registered check: its report id, its catalog code, its implementation.

    `code` is the catalog code this check raises, and it is normally also what
    the runner records when the check cannot be evaluated — an unreadable
    `plugin.json` is an `E_SCHEMA_INVALID` condition, not a new kind of fault.
    `target` is the default `CheckResult.target` for a whole-tree check, which
    is how the design's report shows `"target": "skills/**"`.

    `unevaluated_code` exists for the one check whose own code is a `W_`:
    `residual-claude-refs` raises `W_RESIDUAL_CLAUDE_REF`, and recording *that*
    for a check that could not run would report a scan the validator never
    performed as a content problem the artifact has — `incomplete` rather than
    `failed`. A check that reached no verdict is a fail (design principle 2), so
    such a check names an error code here and `failure_code` is what the runner
    records.
    """

    id: str
    code: str
    run: CheckFunction
    target: str | None = None
    requirement: str = ""
    unevaluated_code: str | None = None

    @property
    def failure_code(self) -> str:
        """The code recorded when no verdict could be obtained: an error, always."""
        return self.unevaluated_code or self.code


#: The checks the design's `ValidationReport` model declares, in report order.
#: Every one of these appears in every report: an entry with no registered
#: implementation records a fail, so an incompletely built validator blocks
#: tagging instead of silently thinning the gate. Checks registered under other
#: ids append after these, in registration order.
#:
#: The first nine are the ids the design's report example spells. The last four
#: are rows of the design's *check table* that its report example does not show —
#: the skill-inventory bijection, the progression order, the ported scripts'
#: module imports, and the scripts and assets those scripts and the hook
#: definitions reference — and they are declared here rather than left as extras
#: precisely because the difference matters: a declared id that nothing
#: implements records a fail, so the gate is explicit about owing these verdicts
#: instead of quietly omitting them.
DECLARED_CHECKS: tuple[str, ...] = (
    "plugin-schema",
    "mcp-schema",
    "skill-frontmatter",
    "cross-references",
    "version-match",
    "residual-claude-refs",
    "invariant-discounts",
    "hook-command-strings",
    "manifest-hashes",
    "skill-inventory",
    "progression-order",
    "script-imports",
    "script-references",
)

_REGISTRY: dict[str, Check] = {}


def register_check(
    check_id: str,
    *,
    code: str,
    target: str | None = None,
    requirement: str = "",
    unevaluated_code: str | None = None,
) -> Callable[[CheckFunction], CheckFunction]:
    """Register one check under `check_id`.

    The decorated function is returned unchanged, so it stays directly callable
    from a property test with a hand-built `ValidationContext`.

    `unevaluated_code` is supplied only by a check whose own `code` is a
    warning, so that failing closed stays a *fail*; see `Check`.
    """

    def decorator(function: CheckFunction) -> CheckFunction:
        if check_id in _REGISTRY:
            raise ValueError(f"check '{check_id}' is already registered")
        _REGISTRY[check_id] = Check(
            id=check_id,
            code=code,
            run=function,
            target=target,
            requirement=requirement,
            unevaluated_code=unevaluated_code,
        )
        return function

    return decorator


def registered_check(check_id: str) -> Check | None:
    return _REGISTRY.get(check_id)


def check_order() -> tuple[str, ...]:
    """Every check id a run records: the declared set, then the extras."""
    extra = tuple(
        check_id for check_id in _REGISTRY if check_id not in DECLARED_CHECKS
    )
    return DECLARED_CHECKS + extra


def registered_checks() -> tuple[Check, ...]:
    """Registered checks in report order; unimplemented ids are not included."""
    return tuple(
        _REGISTRY[check_id] for check_id in check_order() if check_id in _REGISTRY
    )


# ---------------------------------------------------------------------------
# The `plugin-schema` and `mcp-schema` checks (R4 AC2, AC3, R11, R13 AC1, AC2)
# ---------------------------------------------------------------------------
#
# Two files, two recorded results, two rule sets that do not overlap:
#
# * **Schema conformance** — `plugin.json` against the Agent Plugins v1.0.0
#   plugin schema, `mcp.json` against the MCP schema, reported under
#   `E_SCHEMA_INVALID` *(R13 AC1, AC2)*. This is a machine check against a
#   published document, so it is delegated to `jsonschema` rather than
#   paraphrased.
# * **Senzing exactness** — the `senzing` server declared, its `url` and `type`
#   exactly the two required strings, and `$schema` present, reported under
#   `E_MCP_INVALID` *(R11 AC1, AC3, AC4, AC5)*. The MCP schema cannot express
#   any of this: it permits any non-empty `url` string and any of three
#   transports, so a document declaring `sse` at `https://example.invalid/x`
#   conforms perfectly and is still the wrong Power.
#
# The two rule sets are deliberately both applied to `mcp.json`, and a single
# defect may therefore produce a finding under each code. `{"type": "http"}` is
# the case that shows why: the schema rejects it because `http` is not one of
# the three transports, and the exactness rule rejects it because R11 AC2
# requires the *translated* form. Those are different statements about the same
# byte, they cite different requirements, and collapsing them would lose one of
# the two. Both are error severity, so the verdict is a fail either way.
#
# **The schemas are vendored, not fetched.** `agent_plugins_schemas` carries the
# upstream bytes of both documents, pinned by digest, and the resolver built
# below refuses remote retrieval outright rather than merely not needing it. A
# gate that reached the network could block a correct release on a DNS failure,
# and — worse — an upstream edit to a hosted schema could change what the gate
# admits between two runs over identical bytes. See that module's docstring for
# provenance and for why re-expressing the constraints by hand was rejected.
#
# Everything below `schema_validator` is a pure function of a *parsed document*,
# so *Property 14* can drive the exactness rules straight from
# `strategies.mcp_document()` with no staging tree.

#: Which schema governs which produced manifest. One place, so a check cannot
#: end up validating one file against the other's schema.
MANIFEST_SCHEMAS: Mapping[str, str] = {
    PLUGIN_MANIFEST: PLUGIN_SCHEMA_ID,
    MCP_MANIFEST: MCP_SCHEMA_ID,
}

#: How much of a `jsonschema` message survives into a finding. The library
#: renders the offending instance inline, which for a whole-document `type`
#: failure is the whole document; the untrimmed text stays in `details`.
_MAX_RULE_DETAIL = 400

#: Keywords whose failure is a summary of sub-failures rather than a fault of
#: its own. Their branch-level reasons are carried in `details["branches"]`,
#: because "matches none of the three server forms" is not actionable on its own.
_COMPOSITE_KEYWORDS = frozenset({"oneOf", "anyOf", "allOf", "not", "if"})


def schema_title(schema_id: str) -> str:
    """The vendored schema's own `title`, used to name it in a message.

    Read from the schema rather than spelled here, so the phrase a finding uses
    is the phrase upstream chose and a refresh cannot leave the two apart.
    """
    schema = SCHEMAS_BY_ID.get(schema_id)
    title = schema.get("title") if isinstance(schema, Mapping) else None
    return title if isinstance(title, str) and title.strip() else schema_id


def json_pointer(path: Iterable[Any]) -> str:
    """An RFC 6901 pointer for a `jsonschema` error path (`""` at the root).

    Carried in `details` for a machine consumer; `document_location` is what a
    Maintainer reads.
    """
    parts = []
    for token in path:
        text = str(token)
        parts.append(text.replace("~", "~0").replace("/", "~1"))
    return "".join(f"/{part}" for part in parts)


def document_location(path: Iterable[Any]) -> str | None:
    """A `Finding.location` for a position inside a JSON document.

    `mcpServers.senzing.url`, `keywords[2]`, `$schema` — the spelling used
    elsewhere in this file. `None` at the document root, where the position adds
    nothing the `target` does not already say.
    """
    location = ""
    for token in path:
        if isinstance(token, int):
            location += f"[{token}]"
        elif location:
            location += f".{token}"
        else:
            location = str(token)
    return location or None


def schema_validator(schema_id: str) -> Any:
    """A `jsonschema` validator for one vendored schema, unable to fetch.

    Two things are established here rather than assumed. The reference store is
    seeded with both vendored schemas, and `resolve_remote` is overridden to
    raise: the MCP schema's `$ref`s are local `#/$defs/…` fragments that resolve
    from the store, so nothing *should* reach the network, and this makes it so
    that nothing *can* — a future schema carrying an external `$ref` fails loudly
    instead of quietly making the gate depend on connectivity.

    Raises `Unevaluable` when `jsonschema` is unavailable. That reports a
    validator problem through the artifact's result, which is the fail-closed
    rule this module is built on: an environment that cannot check conformance
    has not established conformance, so it must not permit a tag.
    """
    schema = SCHEMAS_BY_ID.get(schema_id)
    if schema is None:
        raise Unevaluable(
            f"no Agent Plugins v{AGENT_PLUGINS_VERSION} schema is vendored under "
            f"{schema_id!r}, so conformance to it cannot be established"
        )

    try:
        from jsonschema import Draft202012Validator, RefResolver
    except ImportError as error:  # pragma: no cover - dev dependency is pinned
        raise Unevaluable(
            "the 'jsonschema' package is not importable, so conformance to the "
            f"Agent Plugins v{AGENT_PLUGINS_VERSION} schemas cannot be checked "
            f"({error}); install the pinned dev dependencies"
        ) from error

    class OfflineResolver(RefResolver):  # type: ignore[misc, valid-type]
        """A resolver that treats a remote retrieval as a fault, not a fallback."""

        def resolve_remote(self, uri: str) -> Any:
            raise Unevaluable(
                f"validating against {schema_id!r} tried to retrieve {uri!r} over "
                "the network; the Agent Plugins schemas are vendored precisely so "
                "this gate does not depend on connectivity"
            )

    return Draft202012Validator(
        schema,
        resolver=OfflineResolver.from_schema(schema, store=dict(SCHEMAS_BY_ID)),
    )


#: Python type → the JSON type name a Maintainer reading `mcp.json` would use.
#: `bool` precedes `int` because it is a subclass of it.
_JSON_TYPE_NAMES: tuple[tuple[type | tuple[type, ...], str], ...] = (
    (bool, "a boolean"),
    ((int, float), "a number"),
    (str, "a string"),
    (list, "an array"),
    (Mapping, "an object"),
)


def _json_type_name(value: Any) -> str:
    """What `value` is, named in JSON's vocabulary rather than Python's.

    A finding about a JSON document that says `NoneType` is asking its reader to
    translate; `null` is the word that is actually in the file.
    """
    if value is None:
        return "null"
    for kinds, name in _JSON_TYPE_NAMES:
        if isinstance(value, kinds):
            return name
    return f"a {type(value).__name__}"


def _rule_detail(message: str) -> str:
    """One `jsonschema` message, trimmed to something a terminal can carry."""
    text = " ".join(message.split())
    if len(text) <= _MAX_RULE_DETAIL:
        return text
    return f"{text[:_MAX_RULE_DETAIL].rstrip()}…"


def _branch_records(error: Any) -> list[dict[str, Any]]:
    """The sub-reasons behind a composite keyword failure, sorted.

    A `oneOf` failure says only that no alternative matched; what a Maintainer
    needs is why each one was rejected. Sorted so the report is a function of
    the document alone.
    """
    records = [
        {
            "branch": (
                sub.schema_path[0] if sub.schema_path else None  # type: ignore[index]
            ),
            "rule": sub.validator,
            "location": document_location(sub.absolute_path),
            "message": _rule_detail(sub.message),
        }
        for sub in getattr(error, "context", None) or ()
    ]
    return sorted(
        records,
        key=lambda record: (
            str(record["branch"]),
            str(record["rule"]),
            str(record["location"]),
            record["message"],
        ),
    )


def _schema_finding(error: Any, *, target: str, schema_id: str, code: str) -> Finding:
    """One schema rule violation, named by file, position, and rule *(R13 AC4)*."""
    location = document_location(error.absolute_path)
    where = location or "the document root"
    branches = _branch_records(error)
    detail = _rule_detail(error.message)
    if error.validator in _COMPOSITE_KEYWORDS and branches:
        reasons = "; ".join(
            f"alternative {record['branch']} — {record['message']}"
            for record in branches
        )
        detail = f"{detail} ({_rule_detail(reasons)})"
    return Finding(
        code=code,
        message=(
            f"{target} violates the {schema_title(schema_id)} schema "
            f"(Agent Plugins v{AGENT_PLUGINS_VERSION}) at {where}: the "
            f"{error.validator!r} rule is not satisfied — {detail}"
        ),
        target=target,
        location=location,
        details={
            "rule": error.validator,
            "schema": schema_id,
            "pointer": json_pointer(error.absolute_path),
            "schemaPointer": json_pointer(error.absolute_schema_path),
            "detail": " ".join(error.message.split()),
            **({"branches": branches} if branches else {}),
        },
    )


def schema_findings(
    document: Any,
    schema_id: str,
    *,
    target: str,
    code: str = E_SCHEMA_INVALID,
) -> tuple[Finding, ...]:
    """Every way `document` fails the vendored schema `schema_id` *(R13 AC1, AC2)*.

    Pure over a parsed document. Every violation is reported, not the first, and
    the order is sorted by (position, rule, message) rather than left to the
    library's traversal, so two runs over one document produce one report.
    """
    validator = schema_validator(schema_id)
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: (
            json_pointer(error.absolute_path),
            str(error.validator),
            error.message,
        ),
    )
    return tuple(
        _schema_finding(error, target=target, schema_id=schema_id, code=code)
        for error in errors
    )


def senzing_declaration_findings(
    document: Any, *, target: str = MCP_MANIFEST
) -> tuple[Finding, ...]:
    """Every way `mcp.json` fails the Senzing declaration *(R11 AC1, AC3-AC5)*.

    Pure over a parsed document, and by **exact** string comparison throughout,
    because R11 AC4 makes a near miss a fault of the same standing as an
    absence: `http://` for `https://`, a trailing slash, `senzing.io` for
    `senzing.com`, `Senzing` for `senzing`, `http` or `streamable_http` for
    `streamable-http`. Each of those passes an eyeball and fails equality, which
    is the whole reason the requirement says "exactly".

    All four rules are evaluated in one pass, so a document with a wrong URL
    *and* a wrong transport *and* no `$schema` reports three findings rather than
    the first of them. The values compared against are imported from the
    transform engine, so the document's producer and its gate cannot disagree
    about what R11 fixes.
    """
    findings: list[Finding] = []

    if not isinstance(document, Mapping):
        return (
            Finding(
                code=E_MCP_INVALID,
                message=(
                    f"{target} is not a JSON object, so it declares no "
                    f"{SENZING_SERVER_KEY!r} server; the Senzing MCP server is a "
                    "mandatory dependency of the bootcamp"
                ),
                target=target,
                details={"server": SENZING_SERVER_KEY, "declared": None},
            ),
        )

    # R11 AC5. Presence only: the schema's own `const` decides whether a present
    # `$schema` names the right document, and reporting a wrong *value* here too
    # would put one defect under two codes for no added instruction.
    if MCP_SCHEMA_FIELD not in document:
        findings.append(
            Finding(
                code=E_MCP_INVALID,
                message=(
                    f"{target} omits the {MCP_SCHEMA_FIELD!r} field, so the "
                    f"translated Agent Plugins v{AGENT_PLUGINS_VERSION} output "
                    "declares no schema it conforms to; it must carry "
                    f"{MCP_SCHEMA_ID!r}"
                ),
                target=target,
                location=MCP_SCHEMA_FIELD,
                details={"field": MCP_SCHEMA_FIELD, "expected": MCP_SCHEMA_ID},
            )
        )

    servers = document.get(MCP_SERVERS_FIELD)
    # An empty stand-in when `mcpServers` is absent or is not an object, so the
    # two lookups below need no guard. `declared` still distinguishes the cases:
    # `None` means there is no `mcpServers` object to name servers in at all,
    # which is a different message from an object that names the wrong ones.
    server_map: Mapping[str, Any] = servers if isinstance(servers, Mapping) else {}
    declared = sorted(server_map) if isinstance(servers, Mapping) else None
    # Membership, not `.get() is not None`: a `"senzing": null` entry *is*
    # declared, and reporting it as an absent key would send a Maintainer looking
    # for a key that is right there.
    present = SENZING_SERVER_KEY in server_map
    server = server_map.get(SENZING_SERVER_KEY)

    # R11 AC3. The declared server names are reported because the near miss that
    # actually happens is a *key* one — `Senzing`, `senzing-mcp` — and a
    # Maintainer cannot see a case difference in a message that omits it.
    if not isinstance(server, Mapping):
        if present:
            # The key is there and its value is not a server object, so there is
            # no `url` and no `type` to compare. Saying "not declared" here would
            # be false and would send a Maintainer looking for a missing key.
            message = (
                f"{target} declares {SENZING_SERVER_KEY!r} under "
                f"{MCP_SERVERS_FIELD!r} as {_json_type_name(server)} rather than "
                "an object, so it declares no URL and no transport type for the "
                "Senzing MCP server"
            )
            location = f"{MCP_SERVERS_FIELD}.{SENZING_SERVER_KEY}"
        else:
            if declared is None:
                found = (
                    f"it carries no {MCP_SERVERS_FIELD!r} object at all"
                    if MCP_SERVERS_FIELD not in document
                    else (
                        f"its {MCP_SERVERS_FIELD!r} is "
                        f"{_json_type_name(servers)} rather than an object"
                    )
                )
            elif not declared:
                found = f"its {MCP_SERVERS_FIELD!r} object is empty"
            else:
                found = f"the server(s) it declares are {declared}"
            message = (
                f"{target} does not declare the {SENZING_SERVER_KEY!r} server "
                f"under {MCP_SERVERS_FIELD!r}: {found}. The Senzing MCP server is "
                "a mandatory dependency of the bootcamp, and the key is matched "
                "exactly"
            )
            location = MCP_SERVERS_FIELD
        findings.append(
            Finding(
                code=E_MCP_INVALID,
                message=message,
                target=target,
                location=location,
                details={
                    "server": SENZING_SERVER_KEY,
                    "declared": declared,
                    "expected": SENZING_SERVER_KEY,
                },
            )
        )
        return tuple(findings)

    # R11 AC1, AC4.
    url = server.get("url")
    if url != SENZING_MCP_URL:
        findings.append(
            Finding(
                code=E_MCP_INVALID,
                message=(
                    f"{target} declares the {SENZING_SERVER_KEY!r} server url as "
                    f"{url!r}; it must be exactly {SENZING_MCP_URL!r}. A differing "
                    "scheme, host, trailing slash, or path is a fault of the same "
                    "standing as an absent declaration"
                ),
                target=target,
                location=f"{MCP_SERVERS_FIELD}.{SENZING_SERVER_KEY}.url",
                details={
                    "server": SENZING_SERVER_KEY,
                    "field": "url",
                    "declared": url,
                    "expected": SENZING_MCP_URL,
                },
            )
        )

    # R11 AC1, AC2, AC4.
    transport = server.get("type")
    if transport != MCP_TRANSPORT_TYPE:
        findings.append(
            Finding(
                code=E_MCP_INVALID,
                message=(
                    f"{target} declares the {SENZING_SERVER_KEY!r} transport type "
                    f"as {transport!r}; it must be exactly {MCP_TRANSPORT_TYPE!r}. "
                    "The template's 'http' declaration is translated to that form, "
                    "never copied through"
                ),
                target=target,
                location=f"{MCP_SERVERS_FIELD}.{SENZING_SERVER_KEY}.type",
                details={
                    "server": SENZING_SERVER_KEY,
                    "field": "type",
                    "declared": transport,
                    "expected": MCP_TRANSPORT_TYPE,
                },
            )
        )

    return tuple(findings)


def _schema_violation_record(finding: Finding) -> dict[str, Any]:
    """The compact per-violation row these checks' `violations` array carries."""
    record: dict[str, Any] = {
        "code": finding.code,
        "location": finding.location,
        "rule": finding.details.get("rule", "senzing-exactness"),
    }
    for key in ("pointer", "field", "declared", "expected"):
        if key in finding.details:
            record[key] = finding.details[key]
    return record


@register_check(
    "plugin-schema",
    code=E_SCHEMA_INVALID,
    target=PLUGIN_MANIFEST,
    requirement="4.2, 13.1",
)
def check_plugin_schema(context: ValidationContext) -> CheckResult:
    """`plugin.json` conforms to the Agent Plugins plugin schema *(R13 AC1)*.

    One recorded result for the one file *(Property 15)*. An absent, non-UTF-8,
    or unparseable `plugin.json` raises `Unevaluable` through `read_json` and is
    recorded as an `E_SCHEMA_INVALID` fail: a Power with no readable manifest has
    not passed its schema, it has never been measured against it.

    `$schema` presence is covered by the schema itself, which requires the field
    and pins it to the v1.0.0 plugin schema URL with a `const`. Nothing is added
    on top of the schema here — `version` against the resolved tag is
    `version-match`, and the provenance under `extensions` is that check's too,
    so this result means exactly "conforms" and nothing more.
    """
    document = context.tree.read_json(PLUGIN_MANIFEST)
    findings = schema_findings(
        document, PLUGIN_SCHEMA_ID, target=PLUGIN_MANIFEST, code=E_SCHEMA_INVALID
    )
    return CheckResult(
        id="plugin-schema",
        target=PLUGIN_MANIFEST,
        findings=findings,
        extra={
            "schema": PLUGIN_SCHEMA_ID,
            "agentPluginsVersion": AGENT_PLUGINS_VERSION,
            "violations": [_schema_violation_record(finding) for finding in findings],
        },
    )


@register_check(
    "mcp-schema",
    code=E_MCP_INVALID,
    target=MCP_MANIFEST,
    requirement="4.3, 11.1, 11.2, 11.3, 11.4, 11.5, 13.2",
)
def check_mcp_schema(context: ValidationContext) -> CheckResult:
    """`mcp.json` conforms *and* declares Senzing exactly *(R11, R13 AC2)*.

    Both rule sets, one recorded result for the one file. Schema violations come
    back as `E_SCHEMA_INVALID`, the Senzing declaration rules as `E_MCP_INVALID`,
    and the result is a fail if either produced anything.

    Fails closed on an unreadable file under `E_MCP_INVALID` rather than
    `E_SCHEMA_INVALID`: of the two conditions an absent `mcp.json` satisfies,
    "the Senzing MCP server is not declared" is the more specific and the more
    consequential — it is the mandatory dependency the whole bootcamp rests on
    *(R11 AC3)*.
    """
    document = context.tree.read_json(MCP_MANIFEST)
    findings = schema_findings(
        document, MCP_SCHEMA_ID, target=MCP_MANIFEST, code=E_SCHEMA_INVALID
    ) + senzing_declaration_findings(document, target=MCP_MANIFEST)
    servers = document.get(MCP_SERVERS_FIELD) if isinstance(document, Mapping) else None
    return CheckResult(
        id="mcp-schema",
        target=MCP_MANIFEST,
        findings=findings,
        extra={
            "schema": MCP_SCHEMA_ID,
            "agentPluginsVersion": AGENT_PLUGINS_VERSION,
            "servers": sorted(servers) if isinstance(servers, Mapping) else None,
            "senzingUrl": SENZING_MCP_URL,
            "senzingType": MCP_TRANSPORT_TYPE,
            "violations": [_schema_violation_record(finding) for finding in findings],
        },
    )


# ---------------------------------------------------------------------------
# The `skill-frontmatter` check (R8 AC5, AC6, R13 AC3, AC4)
# ---------------------------------------------------------------------------
#
# R13 AC3 fixes the unit of record: **one result per `SKILL.md` file** — not one
# per defect, and not one aggregate for the skill set. A file carrying three
# defects is one recorded fail carrying three findings, and a Power with *n*
# skills produces exactly *n* results whatever any of them contains
# (*Property 13*).
#
# That shape has a consequence this code honors deliberately: a fault in *one*
# file must never abort the sweep. Every per-file read and parse failure is
# therefore caught and recorded against the file it belongs to rather than
# raised, and `Unevaluable` escapes this check for exactly one condition — a
# Power carrying no `SKILL.md` at all, where there is nothing to record a result
# *for*.
#
# The rules, and what each is for:
#
# * **`name` present, a non-blank string, equal to the containing directory
#   name** *(R8 AC1, AC5)*. The directory name is the skill's identity: every
#   relative cross-reference in the corpus spells it, so a `name` that differs
#   from it names a skill that is not the one at that path.
# * **`description` present, a non-blank string, at most
#   `MAX_DESCRIPTION_LENGTH` characters, carrying the skill's declared trigger
#   phrase** *(R8 AC5, AC6)*. The description is what a skill activates on, so a
#   blank one is a skill nothing can reach and a truncated one is a skill that
#   activates unpredictably.
# * **`license` present and a non-blank string** *(R8 AC5)*.
#
# The three required fields are `SKILL_REQUIRED_FIELDS`, imported from the
# engine rather than respelled here: the engine refuses to *write* frontmatter
# missing one and this gate refuses to *ship* it, and a gate enforcing a
# different set than the writer targets is a gate that disagrees with its own
# pipeline.
#
# **The declared trigger phrase is read, never tabulated.** A phrase spelled in
# Python here would be a phrase no document declares, and the two spellings
# could drift without either being wrong on its own terms. So the phrase is
# taken from whichever document *declares* it:
#
# * For a **ported** skill that is the template source skill's description — the
#   `Use when ...` clause every template skill already carries. The engine
#   preserves the template `description` character-for-character, which is
#   exactly how the phrase reaches the Power, so comparing the produced
#   description against the phrase the *source* declared is R8 AC6 read
#   literally: a transformation that dropped or reworded the clause fails here.
#   This needs the resolved release tree (`--source`).
# * For a **`kiro-owned`** skill — the three command-derived skills and the
#   enforcement-setup skill, which the contract declares as content with no
#   template source — the produced `SKILL.md` *is* the declaring document, and
#   the rule that bites is that a description declaring no phrase at all fails.
#   The same fallback covers a run with no `--source`: the shape half of R8 AC6
#   still holds, and only the before/after comparison is unavailable.

#: The Agent_Plugins_Format ceiling on a skill `description`. A description is an
#: activation surface, not prose: past this length a client truncates it, and a
#: truncated description activates on something other than what was declared.
MAX_DESCRIPTION_LENGTH = 1024

#: Every value `Finding.details["rule"]` can carry here, in evaluation order.
#: This is the vocabulary a report consumer reads a frontmatter violation by, so
#: it is stated once as data rather than left implicit in the messages.
FRONTMATTER_RULES: tuple[str, ...] = (
    "frontmatter-readable",
    "frontmatter-present",
    "frontmatter-yaml",
    "frontmatter-mapping",
    "name-present",
    "name-non-blank",
    "name-matches-directory",
    "description-present",
    "description-non-blank",
    "description-max-length",
    "description-declares-trigger-phrase",
    "description-contains-trigger-phrase",
    "license-present",
    "license-non-blank",
)

#: The clause a skill description declares its trigger phrase in. Matched
#: case-insensitively and loosely (`Use when`, `Use this skill when`) because the
#: clause is authored prose in two corpora — the template's and this
#: repository's — and the declaration is what matters, not its wording.
_TRIGGER_CLAUSE = re.compile(r"\buse\s+(?:this\s+)?(?:skill\s+)?when\b", re.IGNORECASE)

#: A quoted span, straight or curly, single or double. The lookarounds keep an
#: apostrophe inside a word (`the bootcamper's`) from opening one, which is the
#: one way a possessive could otherwise be read as a declaration.
_QUOTED_PHRASE = re.compile(
    r"(?<!\w)[\"\u201c](?P<double>[^\"\u201d]+)[\"\u201d](?!\w)"
    r"|(?<!\w)['\u2018](?P<single>[^'\u2019]+)['\u2019](?!\w)"
)

_SENTENCE_END = re.compile(r"[.!?]")

#: Which tree the phrase the rules were applied with was declared in. Recorded
#: beside the path because the two trees spell a skill's path identically, so a
#: path alone does not say which document was read.
TRIGGER_SOURCE_TEMPLATE = "template-source"
TRIGGER_SOURCE_PRODUCED = "produced"


def skill_directory_name(path: str) -> str:
    """The skill directory a `skills/<name>/SKILL.md` path sits in.

    The containing directory rather than the path stem, because `name` is
    compared against the directory *(R8 AC1)* and every `SKILL.md` shares one
    stem.
    """
    segments = path.split("/")
    return segments[-2] if len(segments) >= 2 else ""


def _quoted_span(text: str) -> str | None:
    """The first non-blank quoted span in `text`, or `None`."""
    for match in _QUOTED_PHRASE.finditer(text):
        span = (match.group("double") or match.group("single") or "").strip()
        if span:
            return span
    return None


def declared_trigger_phrase(description: str | None) -> str | None:
    """The trigger phrase `description` declares, or `None` when it declares none.

    Three readings, most explicit first:

    1. a quoted span inside a `Use when ...` clause — the form the whole corpus
       uses, template (`Use when the user says "start the bootcamp"`) and
       `kiro-owned` (`Use when the bootcamper says 'start the senzing bootcamp'`)
       alike;
    2. the `Use when ...` clause itself up to the sentence end, for a
       description that states the condition without quoting a phrase;
    3. a quoted span anywhere in the description.

    The phrase comes back verbatim apart from surrounding whitespace, because it
    is used as a substring test against a description that is supposed to carry
    it character-for-character; normalizing it here would let the test pass for a
    description carrying something else.

    Deliberately generous, and for a reason: this is the *shape* half of R8 AC6,
    where the cost of reading an unusual clause too strictly is blocking a
    release over content the engine ported verbatim. The exact half is the
    comparison against what the source skill declared, which the check performs
    whenever the resolved release tree is available.
    """
    if not isinstance(description, str) or not description.strip():
        return None
    clause = _TRIGGER_CLAUSE.search(description)
    if clause is not None:
        remainder = description[clause.end() :]
        quoted = _quoted_span(remainder)
        if quoted is not None:
            return quoted
        end = _SENTENCE_END.search(remainder)
        stated = (remainder[: end.start()] if end is not None else remainder).strip()
        if stated:
            return stated
    return _quoted_span(description)


def _frontmatter_finding(
    message: str,
    *,
    target: str,
    rule: str,
    key: str | None = None,
    **details: Any,
) -> Finding:
    """One frontmatter rule violation, named by file, key, and rule *(R13 AC4)*."""
    return Finding(
        code=E_FRONTMATTER_INVALID,
        message=message,
        target=target,
        location="frontmatter" if key is None else f"frontmatter.{key}",
        details={"rule": rule, **details},
    )


@dataclass(frozen=True)
class SkillFrontmatter:
    """One produced `SKILL.md`'s frontmatter, as far as it could be read.

    `fields` is `None` when the document cannot yield a field mapping at all:
    undecodable bytes, no frontmatter block, unparseable YAML, or a block that is
    not a mapping. Each of those is *one* structural finding, carried in
    `findings`, and the per-field rules are then not applied on top — three
    "declares no name/description/license" findings for a document that declares
    no frontmatter are three restatements of one fault, and R13 AC4 asks for the
    rule that was violated, not for every rule that could not be reached.

    An *empty* block is a different case and yields `{}`: it declares fields, it
    declares none of them, and the per-field rules say so precisely.
    """

    path: str
    directory: str
    fields: Mapping[str, Any] | None = None
    findings: tuple[Finding, ...] = ()

    @property
    def readable(self) -> bool:
        """Whether the per-field rules can be applied to this document."""
        return self.fields is not None

    @property
    def description(self) -> str | None:
        """The declared `description`, or `None` when it is absent or not a string."""
        value = (self.fields or {}).get("description")
        return value if isinstance(value, str) else None

    @classmethod
    def read(cls, tree: PowerTree, path: str) -> SkillFrontmatter:
        """Read and parse one `SKILL.md`'s frontmatter, never raising.

        Every fault becomes a finding against `path`, because the sweep owes a
        result to every *other* `SKILL.md` too *(R13 AC3)*: a check that let one
        undecodable file abort it would record one fail where *n* results were
        due. Fence handling is the engine's `split_frontmatter`, so "what counts
        as a frontmatter block" is defined once for the writer and the gate.
        """
        directory = skill_directory_name(path)
        try:
            text = tree.read_text(path)
        except Unevaluable as error:
            return cls(
                path=path,
                directory=directory,
                findings=(
                    _frontmatter_finding(
                        f"{error.message}, so its frontmatter cannot be read and "
                        "none of the Agent Plugins skill fields can be established",
                        target=path,
                        rule="frontmatter-readable",
                    ),
                ),
            )

        block, _ = split_frontmatter(text)
        if block is None:
            return cls(
                path=path,
                directory=directory,
                findings=(
                    _frontmatter_finding(
                        f"{path} opens with no YAML frontmatter block, so it "
                        "declares none of the Agent Plugins fields "
                        f"{list(SKILL_REQUIRED_FIELDS)}; a skill whose entry point "
                        "declares no frontmatter has no name for Kiro to load it "
                        "under and no description for Kiro to activate it on",
                        target=path,
                        rule="frontmatter-present",
                    ),
                ),
            )

        try:
            document = yaml.safe_load(block)
        except yaml.YAMLError as error:
            return cls(
                path=path,
                directory=directory,
                findings=(
                    _frontmatter_finding(
                        f"{path} carries a frontmatter block that is not valid "
                        f"YAML, so its declared fields cannot be read: {error}",
                        target=path,
                        rule="frontmatter-yaml",
                    ),
                ),
            )

        if document is None:
            return cls(path=path, directory=directory, fields={})
        if not isinstance(document, Mapping):
            return cls(
                path=path,
                directory=directory,
                findings=(
                    _frontmatter_finding(
                        f"{path} carries a frontmatter block that is not a mapping "
                        f"of fields but a {_json_type_name(document)}, so it "
                        "declares no Agent Plugins skill fields at all",
                        target=path,
                        rule="frontmatter-mapping",
                        declaredType=_json_type_name(document),
                    ),
                ),
            )
        return cls(path=path, directory=directory, fields=dict(document))


def _required_string(
    fields: Mapping[str, Any], key: str, *, target: str
) -> tuple[str | None, tuple[Finding, ...]]:
    """One required field read as a non-blank string *(R8 AC5)*.

    Returns the value and no findings when the field is usable; `None` and one
    finding when it is absent, not a string, or blank. Whitespace counts as
    blank: a `description` of `"   "` is a description nothing can activate on,
    and YAML makes it easy to write by accident.
    """
    if key not in fields:
        return None, (
            _frontmatter_finding(
                f"{target} declares no '{key}'; the Agent Plugins skill fields "
                f"{list(SKILL_REQUIRED_FIELDS)} are each required and non-empty",
                target=target,
                rule=f"{key}-present",
                key=key,
            ),
        )

    value = fields[key]
    if not isinstance(value, str) or not value.strip():
        # `declaredType` only where it adds something: for a blank string it
        # would repeat what `declared` already shows.
        typed: dict[str, Any] = (
            {} if isinstance(value, str) else {"declaredType": _json_type_name(value)}
        )
        return None, (
            _frontmatter_finding(
                f"{target} declares '{key}' as {value!r}; the Agent Plugins skill "
                f"fields {list(SKILL_REQUIRED_FIELDS)} are each required to be a "
                "non-empty string, and a value that is only whitespace is empty",
                target=target,
                rule=f"{key}-non-blank",
                key=key,
                declared=value if isinstance(value, str) else None,
                **typed,
            ),
        )
    return value, ()


def skill_name_findings(
    fields: Mapping[str, Any], *, target: str, directory: str
) -> tuple[Finding, ...]:
    """`name` present, non-blank, and equal to the containing directory *(R8 AC1, AC5)*.

    A blank `name` reports as blank and not additionally as a mismatch: it is the
    more specific fault, and both have the same fix.
    """
    name, findings = _required_string(fields, "name", target=target)
    if name is None:
        return findings
    if name == directory:
        return ()
    return (
        _frontmatter_finding(
            f"{target} declares name {name!r} but sits in directory {directory!r}; "
            "the two must be equal, because the directory name is the skill's "
            "identity in every relative cross-reference the corpus spells and in "
            "the inventory the Power is measured against",
            target=target,
            rule="name-matches-directory",
            key="name",
            declared=name,
            expected=directory,
        ),
    )


def skill_description_findings(
    fields: Mapping[str, Any], *, target: str, trigger_phrase: str | None = None
) -> tuple[Finding, ...]:
    """`description` present, non-blank, bounded, carrying its phrase *(R8 AC5, AC6)*.

    `trigger_phrase` is the phrase the skill's *declaring* document states — the
    template source skill's, when the resolved release tree is available. Absent
    that, the produced description is the declaring document and its own
    declaration is read out of it, so what is enforced becomes "declares a
    trigger phrase" rather than "carries the source's".

    The length rule and the phrase rule are independent, so a description that is
    both too long and no longer carries its phrase reports both: two defects, two
    fixes.
    """
    description, absent = _required_string(fields, "description", target=target)
    if description is None:
        return absent

    findings: list[Finding] = []
    if len(description) > MAX_DESCRIPTION_LENGTH:
        findings.append(
            _frontmatter_finding(
                f"{target} declares a description of {len(description)} characters; "
                f"the Agent_Plugins_Format ceiling is {MAX_DESCRIPTION_LENGTH}, past "
                "which a client truncates it and the skill activates on something "
                "other than what was declared",
                target=target,
                rule="description-max-length",
                key="description",
                length=len(description),
                limit=MAX_DESCRIPTION_LENGTH,
            )
        )

    declared = trigger_phrase.strip() if isinstance(trigger_phrase, str) else None
    declared = declared or declared_trigger_phrase(description)
    if declared is None:
        findings.append(
            _frontmatter_finding(
                f"{target} declares a description that states no trigger phrase; "
                "R8 AC6 requires the description to carry the skill's trigger "
                "phrase, and a skill whose description names no phrase is a skill "
                "a Bootcamper has no stated way to activate",
                target=target,
                rule="description-declares-trigger-phrase",
                key="description",
                declared=description,
            )
        )
    elif declared not in description:
        findings.append(
            _frontmatter_finding(
                f"{target} declares a description that does not contain the trigger "
                f"phrase {declared!r} declared for this skill; the adaptation is "
                "additive, so the phrase the source skill stated has to survive it "
                "verbatim (R8 AC6)",
                target=target,
                rule="description-contains-trigger-phrase",
                key="description",
                declared=description,
                triggerPhrase=declared,
            )
        )
    return tuple(findings)


def skill_license_findings(
    fields: Mapping[str, Any], *, target: str
) -> tuple[Finding, ...]:
    """`license` present and non-blank *(R8 AC5)*.

    The engine supplies it, so a violation here means the template declared a
    blank one or the produced file was edited after the build.
    """
    _, findings = _required_string(fields, "license", target=target)
    return findings


def frontmatter_findings(
    fields: Mapping[str, Any],
    *,
    target: str,
    directory: str,
    trigger_phrase: str | None = None,
) -> tuple[Finding, ...]:
    """Every rule violation in one parsed frontmatter, in rule order.

    Pure: a mapping in, findings out, no filesystem and no tree. All three fields
    are examined whatever any of them reports, so one result names the whole of
    what a Maintainer has to fix in that file rather than the first item of it
    (design principle 1).
    """
    return (
        skill_name_findings(fields, target=target, directory=directory)
        + skill_description_findings(
            fields, target=target, trigger_phrase=trigger_phrase
        )
        + skill_license_findings(fields, target=target)
    )


def _source_trigger_phrase(
    context: ValidationContext, directory: str
) -> tuple[str | None, str | None]:
    """The phrase the *template* skill declares, and the document declaring it.

    `(None, None)` when there is no resolved release tree, when the release
    carries no skill of that name — every `kiro-owned` skill is that case by
    construction, the contract having declared it as content with no template
    source — or when the source description declares no phrase. The produced
    document is then the declaring one, which is what
    `skill_description_findings` falls back to.

    A source skill that cannot be read is not an error *here*: this check gates
    the produced Power, and the inventory bijection is what measures the Power
    against the release.
    """
    source = context.source
    if source is None:
        return None, None
    path = f"skills/{directory}/{SKILL_MANIFEST}"
    if not source.exists(path):
        return None, None
    phrase = declared_trigger_phrase(SkillFrontmatter.read(source, path).description)
    return (phrase, path) if phrase is not None else (None, None)


def _frontmatter_violation_record(finding: Finding) -> dict[str, Any]:
    """The compact per-violation row this check's `violations` array carries."""
    record: dict[str, Any] = {
        "code": finding.code,
        "location": finding.location,
        "rule": finding.details.get("rule", ""),
    }
    for key in ("expected", "declaredType", "length", "limit", "triggerPhrase"):
        if key in finding.details:
            record[key] = finding.details[key]
    return record


def skill_frontmatter_result(context: ValidationContext, path: str) -> CheckResult:
    """The one result R13 AC3 owes one `SKILL.md` file.

    `extra` states the phrase the rules were applied with and the document that
    declared it, so a Maintainer reading a containment failure can see which
    description the comparison was made against without re-deriving it.
    """
    frontmatter = SkillFrontmatter.read(context.tree, path)
    phrase, declared_in = _source_trigger_phrase(context, frontmatter.directory)

    findings = frontmatter.findings
    if frontmatter.readable:
        findings += frontmatter_findings(
            frontmatter.fields or {},
            target=path,
            directory=frontmatter.directory,
            trigger_phrase=phrase,
        )

    origin = TRIGGER_SOURCE_TEMPLATE if phrase is not None else None
    if phrase is None:
        phrase = declared_trigger_phrase(frontmatter.description)
        declared_in = path if phrase is not None else None
        origin = TRIGGER_SOURCE_PRODUCED if phrase is not None else None

    description = frontmatter.description
    return CheckResult(
        id="skill-frontmatter",
        target=path,
        findings=findings,
        extra={
            "skill": frontmatter.directory,
            "triggerPhrase": phrase,
            "triggerPhraseDeclaredIn": declared_in,
            "triggerPhraseOrigin": origin,
            "descriptionLength": None if description is None else len(description),
            "descriptionLimit": MAX_DESCRIPTION_LENGTH,
            "violations": [
                _frontmatter_violation_record(finding) for finding in findings
            ],
        },
    )


@register_check(
    "skill-frontmatter",
    code=E_FRONTMATTER_INVALID,
    target=SKILL_MD_GLOB,
    requirement="8.5, 8.6, 13.3, 13.4",
)
def check_skill_frontmatter(context: ValidationContext) -> tuple[CheckResult, ...]:
    """One recorded result per produced `SKILL.md` *(R13 AC3, Property 13)*.

    The sweep is over `skills/*/SKILL.md` in sorted order, so the results — and
    the findings within them — are a function of the produced tree alone. A
    `SKILL.md` nested deeper is a supporting document rather than a skill's entry
    point and carries no frontmatter contract, which is why the glob does not
    cross `/`.

    A Power with no skill entry point at all is the one condition that declines
    to a verdict: there is no file to record a result for, and recording *zero*
    results would let a Power with no skills satisfy "every recorded result is a
    pass".
    """
    paths = context.tree.skill_md_paths()
    if not paths:
        raise Unevaluable(
            f"the produced Power carries no {SKILL_MD_GLOB} file, so no skill "
            "frontmatter could be validated; a produced Bootcamp_Power ships the "
            "ported bootcamp skills and the kiro-owned ones the contract declares",
            target=SKILL_MD_GLOB,
        )
    return tuple(skill_frontmatter_result(context, path) for path in paths)


# ---------------------------------------------------------------------------
# The `cross-references` check (R8 AC3, AC4)
# ---------------------------------------------------------------------------
#
# The bootcamp corpus navigates itself: `../bootcamp-onboarding/ground-rules.md`,
# `../module-02-sdk-setup/SKILL.md`, `references/feedback.md`. Those links are
# *path arithmetic*, so they survive transformation only because the engine
# preserves the `skills/<name>/` layout verbatim — and "only because" is exactly
# why this check exists. A rule that renamed one skill directory, or flattened
# one `references/` subtree, would leave a hundred links pointing at nothing, and
# every one of them would still look like a link.
#
# So the check is deliberately arithmetic rather than clever: resolve each link
# against the directory of the document that spells it, normalize, and ask the
# produced tree whether a file is there. Three ways that can come out wrong, and
# each gets its own `kind` because each has a different fix:
#
# * `absent` — the resolved path names nothing. The usual cause is a target the
#   transformation did not port (a template `commands/` document, a repo-root
#   `README.md`), and the fix is either to port it or to drop the link.
# * `directory` — the resolved path names a directory some file sits under. R8
#   AC3 asks for an existing *file*, so this is reported rather than waved
#   through, and the message names a document inside the directory so the fix is
#   a one-token edit.
# * `escapes-power` — the link walks out of the Power root (`../../README.md`).
#   Whatever is up there is not shipped, so the reference cannot resolve *within
#   the Bootcamp_Power* however the checkout is arranged.
#
# **What is not a cross-reference** is as load-bearing as what is, because a
# false positive here blocks a correct release. Four exclusions, each for a
# stated reason: a target carrying a URI scheme or a protocol-relative prefix
# points outside the filesystem; a root-absolute target is not relative and its
# root is the client's, not the Power's; a bare `#anchor` names a position in the
# document already being read; and a target carrying a `${...}` or `{{...}}`
# placeholder is resolved by the client at load time — `${PLUGIN_ROOT}/scripts/x`
# is a *variable-rooted* reference, and `residual-claude-refs` is what has an
# opinion about which variable it names.
#
# Extraction is a Markdown reader's job done to a Markdown reader's standard, no
# further. Fenced code blocks and inline code spans are blanked first, so a link
# *shown as an example* is not read as a link; both are blanked in place, newline
# for newline, so a finding can still name the line the link sits on. Indented
# code blocks are deliberately **not** treated as code: in this corpus a
# four-space indent is nearly always list continuation carrying real links, and
# skipping those would trade false positives for false negatives on the far more
# common shape. A destination is found by its `](` marker rather than by matching
# a whole link, which is what lets a nested image link
# (`[![badge](a.png)](b.md)`) report both of its destinations instead of the
# outer one only; the cost is that a destination must *look* like a path — a
# separator or a file extension — so that `records[i](x)` in unfenced prose is
# not read as a link to `x`.
#
# Everything above the check is a pure function of text and paths, so
# *Property 12* drives extraction and resolution straight from
# `strategies.skill_tree()` with no staging tree. `resolve_reference` is
# deliberately the same two-line normalization the generator uses to decide
# whether a generated link resolves: if the gate and the generator computed
# "where does this point" differently, the property would be measuring the
# difference between two spellings rather than the behavior of the check.

#: Which documents are swept. The corpus's cross-references are Markdown links
#: between skill documents, so the sweep is every Markdown file anywhere under
#: `skills/` — a skill's entry point *and* the `references/` documents it links
#: to, since those cross-reference each other and their siblings too.
CROSS_REFERENCE_GLOB = "skills/**/*.md"

#: `CheckResult.target`: the subtree the check examined, as the design's report
#: model spells it.
CROSS_REFERENCE_TARGET = "skills/**"

#: `unresolved[].kind` — how a reference failed to resolve. The catalog code is
#: `E_UNRESOLVED_REFERENCE` for all three, because the gate's response is the
#: same; the kind is what says which edit fixes it, so it travels as data.
REFERENCE_ABSENT = "absent"
REFERENCE_DIRECTORY = "directory"
REFERENCE_ESCAPES_POWER = "escapes-power"

REFERENCE_KINDS: tuple[str, ...] = (
    REFERENCE_ABSENT,
    REFERENCE_DIRECTORY,
    REFERENCE_ESCAPES_POWER,
)

#: A link destination, found by its `](` marker: `<bracketed>` or bare, with an
#: optional title in quotes or parentheses. The link *text* is not matched at
#: all, so a destination nested inside another link's text is still found.
_LINK_DESTINATION = re.compile(
    r"\]\(\s*"
    r"(?:<(?P<angled>[^<>\n]*)>|(?P<bare>[^\s()]*))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^()]*\)))?"
    r"\s*\)"
)

#: A reference-style link definition: `[label]: ../elsewhere/doc.md "Title"`.
#: Up to three leading spaces, as CommonMark allows.
_LINK_DEFINITION = re.compile(
    r"^[ \t]{0,3}\[[^\[\]\n]+\]:[ \t]*"
    r"(?:<(?P<angled>[^<>\n]*)>|(?P<bare>[^\s]+))",
    re.MULTILINE,
)

#: An opening or closing code fence: three or more backticks or tildes.
_CODE_FENCE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})")

#: An inline code span, delimited by matched backtick runs. `(?!`)` keeps a run
#: of three from being closed by the first two of another three.
_CODE_SPAN = re.compile(r"(?P<ticks>`+).*?(?P=ticks)(?!`)", re.DOTALL)

#: A URI scheme (`https:`, `mailto:`, `file:`). A destination carrying one does
#: not name a path inside the Power.
_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

#: A client-resolved placeholder. `${PLUGIN_ROOT}/scripts/x` is not relative.
_LINK_PLACEHOLDER = re.compile(r"\$\{[^}]*\}|\{\{[^}]*\}\}")

#: A file extension on the last segment — one half of "looks like a path".
_PATH_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,8}$")


def _blank_span(match: re.Match[str]) -> str:
    """Blank a matched span, newline for newline, so line numbers survive."""
    return "".join("\n" if char == "\n" else " " for char in match.group(0))


def blank_code_blocks(text: str) -> str:
    """Blank every fenced code block, keeping the document's line structure.

    Line-for-line rather than by deletion, because a finding names the line a
    link sits on and a shorter document would name the wrong one. Closing rules
    follow CommonMark closely enough for this corpus: a fence closes on a line
    of the same character, at least as long, carrying nothing else.
    """
    lines = text.split("\n")
    blanked: list[str] = []
    fence: str | None = None
    for line in lines:
        if fence is None:
            opening = _CODE_FENCE.match(line)
            if opening is not None:
                fence = opening.group("fence")
                blanked.append("")
                continue
            blanked.append(line)
            continue
        stripped = line.strip()
        if len(stripped) >= len(fence) and set(stripped) == {fence[0]}:
            fence = None
        blanked.append("")
    return "\n".join(blanked)


def markdown_prose(text: str) -> str:
    """`text` with code blocks and code spans blanked, same length, same lines.

    What is left is the prose a reader would follow a link from. A link shown
    inside a code sample is documentation *about* a link and must not be
    resolved: it frequently names a path in the template repository, which the
    Power is not obliged to carry.
    """
    return _CODE_SPAN.sub(_blank_span, blank_code_blocks(text))


def _looks_like_path(candidate: str) -> bool:
    """True when `candidate` names a path rather than incidental prose.

    A separator or a file extension. This is the guard that keeps `records[i](x)`
    in unfenced prose from being read as a link to `x`, and every relative
    cross-reference in the corpus satisfies it: a link to another skill carries
    `/`, and a link within one carries `.md`.
    """
    return "/" in candidate or _PATH_EXTENSION.search(candidate) is not None


def reference_path(target: str) -> str | None:
    """The path a link destination names, or `None` when it names no path.

    `None` for every destination the exclusions above cover, and for a
    destination that is only a fragment or only a query. Otherwise the path with
    its `#fragment` and `?query` removed and its percent-escapes decoded, since
    `../module-03b-truthset%20visualization/SKILL.md` names a file with a space
    in it and the tree is keyed by the name, not by the encoding.
    """
    candidate = target.strip()
    if not candidate or candidate.startswith("#"):
        return None
    if candidate.startswith("/") or _URI_SCHEME.match(candidate) is not None:
        return None
    if _LINK_PLACEHOLDER.search(candidate) is not None:
        return None
    candidate = candidate.split("#", 1)[0].split("?", 1)[0]
    if not candidate or not _looks_like_path(candidate):
        return None
    candidate = unquote(candidate)
    # Decoding can produce a leading separator (`%2Fetc/passwd`), which is not a
    # relative reference however it was spelled.
    if not candidate.strip() or candidate.startswith("/"):
        return None
    return candidate


def resolve_reference(source: str, path: str) -> str:
    """Where `path`, spelled in `source`, points — root-relative and normalized.

    Two lines, and deliberately the same two the cross-reference generator uses
    to decide whether a generated link resolves: join against the *directory* of
    the document that spells the link, then normalize away `.` and `..`. A result
    of `..` or one beginning `../` is above the Power root, which
    `CrossReference.within_power` reads back.
    """
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), path))


@dataclass(frozen=True)
class CrossReference:
    """One relative Markdown link: where it is written, and where it points.

    `target` is the destination verbatim, because R8 AC4 asks for the target
    *path* as the document spells it — that is the string a Maintainer searches
    for. `path` is the same destination with its fragment, query, and
    percent-escapes resolved, and `resolved` is where that lands relative to the
    Power root. All three are carried: a finding that reported only the resolved
    path would name a string that appears nowhere in the file it is about.
    """

    source: str
    target: str
    path: str
    resolved: str
    line: int

    @property
    def within_power(self) -> bool:
        """False when the reference resolves above the Power root."""
        return self.resolved != ".." and not self.resolved.startswith("../")

    def details(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "path": self.path,
            "resolved": self.resolved,
            "line": self.line,
        }


def cross_reference(source: str, target: str, *, line: int) -> CrossReference | None:
    """One `CrossReference` for one destination, or `None` if it is not one.

    Pure, and the single place a destination becomes a reference, so the
    exclusions cannot be applied in one caller and forgotten in another.
    """
    path = reference_path(target)
    if path is None:
        return None
    return CrossReference(
        source=source,
        target=target,
        path=path,
        resolved=resolve_reference(source, path),
        line=line,
    )


def markdown_references(text: str, *, source: str) -> tuple[CrossReference, ...]:
    """Every relative cross-reference `text` spells, in document order.

    Sorted by (line, target) rather than left in the order two patterns happened
    to scan in, so the findings a document produces are a function of the
    document alone.
    """
    prose = markdown_prose(text)
    found: list[CrossReference] = []
    for pattern in (_LINK_DESTINATION, _LINK_DEFINITION):
        for match in pattern.finditer(prose):
            angled = match.group("angled")
            target = angled if angled is not None else (match.group("bare") or "")
            reference = cross_reference(
                source, target, line=prose.count("\n", 0, match.start()) + 1
            )
            if reference is not None:
                found.append(reference)
    return tuple(
        sorted(found, key=lambda reference: (reference.line, reference.target))
    )


def reference_kind(tree: PowerTree, reference: CrossReference) -> str | None:
    """How `reference` fails to resolve, or `None` when it resolves to a file.

    The whole of R8 AC3 in four lines: an existing file is the only pass, and the
    order of the tests is what makes each `kind` mean one thing.
    """
    if not reference.within_power:
        return REFERENCE_ESCAPES_POWER
    if tree.exists(reference.resolved):
        return None
    if tree.is_directory(reference.resolved):
        return REFERENCE_DIRECTORY
    return REFERENCE_ABSENT


def _unresolved_finding(
    tree: PowerTree, reference: CrossReference, kind: str
) -> Finding:
    """One broken link, naming its source file and its target path *(R8 AC4)*."""
    if kind == REFERENCE_ESCAPES_POWER:
        reason = (
            f"which resolves to {reference.resolved!r} — above the Power root. A "
            "relative cross-reference between skills has to resolve to an "
            "existing file *within* the Bootcamp_Power, and a link that walks out "
            "of it cannot, however the Power is checked out"
        )
    elif kind == REFERENCE_DIRECTORY:
        example = next(
            (
                path
                for path in tree.paths
                if path.startswith(f"{reference.resolved.rstrip('/')}/")
            ),
            None,
        )
        inside = f" (for example {example!r})" if example is not None else ""
        reason = (
            f"which resolves to {reference.resolved!r}, a directory rather than a "
            f"file; name the document inside it{inside}"
        )
    else:
        reason = (
            f"which resolves to {reference.resolved!r}; no such file exists in the "
            "produced Power. Either the target was never ported or the link was "
            "not adapted with it — the skill layout is preserved verbatim so that "
            "every relative cross-reference points to the same file it pointed to "
            "before transformation (R8 AC2)"
        )
    return Finding(
        code=E_UNRESOLVED_REFERENCE,
        message=(
            f"{reference.source} links to {reference.target!r} on line "
            f"{reference.line}, {reason}"
        ),
        target=reference.source,
        location=f"line {reference.line}",
        details={**reference.details(), "kind": kind},
    )


def cross_reference_findings(
    tree: PowerTree, references: Iterable[CrossReference]
) -> tuple[Finding, ...]:
    """One finding per unresolved reference, in the order they were read.

    Pure over a tree and a sequence of references. Every reference is examined —
    a document with four broken links reports four, not the first.
    """
    findings: list[Finding] = []
    for reference in references:
        kind = reference_kind(tree, reference)
        if kind is not None:
            findings.append(_unresolved_finding(tree, reference, kind))
    return tuple(findings)


def _unresolved_record(finding: Finding) -> dict[str, Any]:
    """The compact per-reference row this check's `unresolved` array carries."""
    return {
        "source": finding.details.get("source", finding.target),
        "target": finding.details.get("target"),
        "resolved": finding.details.get("resolved"),
        "line": finding.details.get("line"),
        "kind": finding.details.get("kind"),
    }


@register_check(
    "cross-references",
    code=E_UNRESOLVED_REFERENCE,
    target=CROSS_REFERENCE_TARGET,
    requirement="8.3, 8.4",
)
def check_cross_references(context: ValidationContext) -> CheckResult:
    """Every relative cross-reference resolves to a file in the Power *(R8 AC3)*.

    One recorded result for the subtree, carrying one finding per broken link
    naming its source file and its target path *(R8 AC4)*. Tagging is then
    blocked until zero remain by construction rather than by a separate rule: an
    error-severity finding makes this result a fail, a failing result makes the
    status `failed`, and `tagAllowed` is the biconditional over that.

    A document that cannot be decoded is recorded against itself and the sweep
    continues, because the other documents' links are still owed a verdict. A
    Power carrying no Markdown under `skills/` at all is the one condition that
    declines to answer: there is nothing to resolve, and recording a pass for it
    would let a Power with no skill content satisfy the gate.
    """
    tree = context.tree
    documents = tree.match(CROSS_REFERENCE_GLOB)
    if not documents:
        raise Unevaluable(
            f"the produced Power carries no {CROSS_REFERENCE_GLOB} document, so "
            "no relative cross-reference could be resolved; a produced "
            "Bootcamp_Power ships the ported bootcamp skills and the documents "
            "they link to",
            target=CROSS_REFERENCE_TARGET,
        )

    findings: list[Finding] = []
    references: list[CrossReference] = []
    unresolved = 0
    for path in documents:
        try:
            text = tree.read_text(path)
        except Unevaluable as error:
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=(
                        f"{error.message}, so the relative cross-references it "
                        "spells cannot be resolved"
                    ),
                    target=path,
                )
            )
            continue
        spelled = markdown_references(text, source=path)
        references.extend(spelled)
        broken = cross_reference_findings(tree, spelled)
        unresolved += len(broken)
        findings.extend(broken)

    return CheckResult(
        id="cross-references",
        target=CROSS_REFERENCE_TARGET,
        findings=tuple(findings),
        extra={
            "documentGlob": CROSS_REFERENCE_GLOB,
            "documents": len(documents),
            "references": len(references),
            "resolved": len(references) - unresolved,
            "unresolved": [
                _unresolved_record(finding)
                for finding in findings
                if finding.code == E_UNRESOLVED_REFERENCE
            ],
        },
    )


# ---------------------------------------------------------------------------
# The `version-match` check (R2 AC3, AC4)
# ---------------------------------------------------------------------------
#
# One number, written in three places, and the whole point of R2 is that whoever
# reads any one of them learns the same thing:
#
# * the **resolved tag** — the Template_Release this build was driven from. It
#   arrives as `--tag`, it is not part of the artifact, and it is the authority
#   the other two are measured against.
# * the **Power version** — `plugin.json` `version`, the string a client displays
#   *(R2 AC1, AC2)*.
# * the **recorded provenance** — `plugin.json`
#   `extensions["com.senzing.bootcamp"].templateRelease`, which says which
#   upstream release the content came from *(R2 AC5)*.
#
# The namespace key and the field name are imported from the engine rather than
# respelled here: the engine writes that path, this gate reads it, and a gate
# reading a path nothing writes would pass every Power ever built.
#
# **Two comparisons, both anchored on the Power version**, and that pair is the
# whole condition rather than an approximation of it: if the stamp equals the tag
# and the stamp equals the provenance, the provenance equals the tag by
# transitivity, so the two comparisons hold exactly when all three strings are
# identical. A third pair would only restate an inequality one of these two has
# already reported.
#
# **Character-for-character, never semver precedence** *(R2 AC3)*. `0.5.1` and
# `0.05.1` are the same version to a semver comparator and different strings to
# everything that matters here — a tag lookup, a changelog entry, a checkout, a
# Bootcamper matching a Power against a release page. So the comparison is `==`
# on `str`, and a value that is not a string at all (absent, `null`, a number) is
# a mismatch rather than something to coerce and then compare.
#
# **This check writes nothing**, which is the whole of R2 AC4's second half. The
# validator only reads the tree, so "leave the existing Bootcamp_Power version and
# metadata unchanged" needs no code to enforce: there is no path here that could
# change them. AC4's first half is equally structural — an error-severity finding
# makes this result a fail, a failing result makes the status `failed`, and
# `tagAllowed` is the biconditional over that.
#
# Everything below the registered check is a pure function of a parsed manifest
# and a tag — no `PowerTree`, no filesystem — because *Property 2* drives both
# directions from generated version strings.

#: The top-level `plugin.json` field carrying the Bootcamp_Power version (R2 AC1).
POWER_VERSION_FIELD = "version"

#: The `plugin.json` object custom namespaces sit under. Only the container is
#: named here; the namespace key and the field inside it come from the engine.
EXTENSIONS_FIELD = "extensions"

#: Where the provenance sits, as a path into the parsed manifest — outside the
#: plugin schema's fixed top-level field set, which is the half of R2 AC5 that
#: says *where* rather than *what*.
PROVENANCE_PATH: tuple[str, ...] = (
    EXTENSIONS_FIELD,
    EXTENSION_NAMESPACE,
    TEMPLATE_RELEASE_FIELD,
)

#: The three strings, named. These are the keys `extra` and `details` carry, so a
#: report consumer reads a mismatch by role rather than by position.
VERSION_ROLE_TAG = "resolvedTag"
VERSION_ROLE_STAMP = "powerVersion"
VERSION_ROLE_PROVENANCE = "templateRelease"

VERSION_ROLES: tuple[str, ...] = (
    VERSION_ROLE_TAG,
    VERSION_ROLE_STAMP,
    VERSION_ROLE_PROVENANCE,
)

#: The comparisons performed, in report order: the Power version against the
#: resolved tag, and the Power version against the recorded provenance. Stated as
#: data because their *conjunction* is the requirement, and that is easier to
#: read as a table than as two `if`s.
VERSION_COMPARISONS: tuple[tuple[str, str], ...] = (
    (VERSION_ROLE_STAMP, VERSION_ROLE_TAG),
    (VERSION_ROLE_STAMP, VERSION_ROLE_PROVENANCE),
)

#: How each role is named in a finding message. R2 AC3 asks the error to identify
#: both version strings, and a string is only identified if the reader can tell
#: which of the three it is.
_VERSION_ROLE_PHRASES: Mapping[str, str] = {
    VERSION_ROLE_TAG: "the resolved Template_Release tag",
    VERSION_ROLE_STAMP: (
        f"the Bootcamp_Power version ({PLUGIN_MANIFEST} '{POWER_VERSION_FIELD}')"
    ),
    VERSION_ROLE_PROVENANCE: (
        f"the recorded Template_Release provenance ({PLUGIN_MANIFEST} "
        f"'{document_location(PROVENANCE_PATH)}')"
    ),
}

#: Where each role sits in the manifest. The resolved tag has no path: it is an
#: input to the run, not a field of the artifact, which is what makes it the
#: authority rather than one more thing to be checked.
_VERSION_ROLE_PATHS: Mapping[str, tuple[str, ...]] = {
    VERSION_ROLE_TAG: (),
    VERSION_ROLE_STAMP: (POWER_VERSION_FIELD,),
    VERSION_ROLE_PROVENANCE: PROVENANCE_PATH,
}


def _version_spelled(value: Any) -> str:
    """How a version value is named in a message: quoted, or what it was instead."""
    if isinstance(value, str):
        return repr(value)
    if value is None:
        return "absent"
    return f"a non-string {type(value).__name__} ({value!r})"


@dataclass(frozen=True)
class VersionStrings:
    """The three version strings a run compares, exactly as they were found.

    Values are held **raw** — an absent field is `None`, a number stays a number —
    because R2 AC3 asks the finding to identify what the Power declares, and a
    value normalized on the way in is a value the message would misreport.
    """

    tag: str
    stamp: Any = None
    provenance: Any = None

    @classmethod
    def read(cls, document: Any, tag: str) -> VersionStrings:
        """Pull both recorded strings out of a parsed `plugin.json`.

        Total by design: a document that is not an object, one carrying no
        `extensions`, and one whose namespace key holds something other than an
        object all leave the corresponding value `None`, which the comparison then
        reports as a mismatch. Nothing here raises, so the check's only
        unevaluable condition is a manifest that cannot be parsed at all.
        """
        if not isinstance(document, Mapping):
            return cls(tag=tag)
        extensions = document.get(EXTENSIONS_FIELD)
        namespace = (
            extensions.get(EXTENSION_NAMESPACE)
            if isinstance(extensions, Mapping)
            else None
        )
        return cls(
            tag=tag,
            stamp=document.get(POWER_VERSION_FIELD),
            provenance=(
                namespace.get(TEMPLATE_RELEASE_FIELD)
                if isinstance(namespace, Mapping)
                else None
            ),
        )

    def value(self, role: str) -> Any:
        return {
            VERSION_ROLE_TAG: self.tag,
            VERSION_ROLE_STAMP: self.stamp,
            VERSION_ROLE_PROVENANCE: self.provenance,
        }[role]

    def details(self) -> dict[str, Any]:
        """All three strings by role, so one finding carries the whole picture."""
        return {role: self.value(role) for role in VERSION_ROLES}

    @property
    def matched(self) -> bool:
        """True exactly when all three strings are character-for-character equal."""
        return all(comparison.identical for comparison in version_comparisons(self))


@dataclass(frozen=True)
class VersionComparison:
    """One pair of version strings, compared character-for-character."""

    left: str
    right: str
    left_value: Any
    right_value: Any

    @property
    def identical(self) -> bool:
        """Both sides are strings, and are the same string.

        The `isinstance` guards are load-bearing rather than defensive: without
        them two absent fields would compare equal, and a manifest recording no
        version at all would report a match.
        """
        return (
            isinstance(self.left_value, str)
            and isinstance(self.right_value, str)
            and self.left_value == self.right_value
        )

    @property
    def location(self) -> str | None:
        """The manifest position a Maintainer edits to settle this pair.

        The right role's when it has one, the left's otherwise. For the
        stamp-against-provenance pair that is the provenance field, which is the
        useful answer: whenever the stamp is the string at fault, the
        stamp-against-tag comparison is already saying so.
        """
        return document_location(
            _VERSION_ROLE_PATHS[self.right] or _VERSION_ROLE_PATHS[self.left]
        )

    def details(self) -> dict[str, Any]:
        return {
            "compared": [self.left, self.right],
            "left": self.left_value,
            "right": self.right_value,
        }


def version_comparisons(versions: VersionStrings) -> tuple[VersionComparison, ...]:
    """The declared comparisons over `versions`, in report order."""
    return tuple(
        VersionComparison(
            left=left,
            right=right,
            left_value=versions.value(left),
            right_value=versions.value(right),
        )
        for left, right in VERSION_COMPARISONS
    )


def _version_mismatch_finding(
    versions: VersionStrings, comparison: VersionComparison
) -> Finding:
    """One mismatch, naming **both** strings *(R2 AC3)*.

    Both sides go into the message and all three go into `details`, so the
    Maintainer reads the disagreement without opening the manifest and a consumer
    reads it without parsing prose.
    """
    both_strings = isinstance(comparison.left_value, str) and isinstance(
        comparison.right_value, str
    )
    note = (
        " — the two are compared character-for-character, so a difference in "
        "leading zeros, whitespace, or a 'v' prefix is a mismatch even where "
        "semver precedence would call the strings equivalent"
        if both_strings
        else ""
    )
    return Finding(
        code=E_VERSION_MISMATCH,
        message=(
            f"{_VERSION_ROLE_PHRASES[comparison.left]} is "
            f"{_version_spelled(comparison.left_value)} and "
            f"{_VERSION_ROLE_PHRASES[comparison.right]} is "
            f"{_version_spelled(comparison.right_value)}; they are not "
            f"character-for-character identical{note}"
        ),
        target=PLUGIN_MANIFEST,
        location=comparison.location,
        details={**comparison.details(), **versions.details()},
    )


def version_mismatch_findings(versions: VersionStrings) -> tuple[Finding, ...]:
    """One finding per mismatching pair; none when all three strings agree.

    Every declared comparison is performed whatever an earlier one reported, so a
    Power agreeing with neither the tag nor its own provenance names both rather
    than the first (design principle 1).
    """
    return tuple(
        _version_mismatch_finding(versions, comparison)
        for comparison in version_comparisons(versions)
        if not comparison.identical
    )


def _version_mismatch_record(finding: Finding) -> dict[str, Any]:
    """The compact per-mismatch row this check's `mismatches` array carries."""
    return {
        "compared": finding.details.get("compared"),
        "left": finding.details.get("left"),
        "right": finding.details.get("right"),
        "location": finding.location,
    }


def version_match_result(document: Any, tag: str) -> CheckResult:
    """The recorded result for one parsed manifest and one resolved tag.

    Pure, and the whole of the check — `check_version_match` adds only the read.
    *Property 2* drives this function directly, in both directions, from generated
    version strings.
    """
    versions = VersionStrings.read(document, tag)
    findings = version_mismatch_findings(versions)
    return CheckResult(
        id="version-match",
        findings=findings,
        extra={
            "manifest": PLUGIN_MANIFEST,
            **versions.details(),
            "provenanceField": document_location(PROVENANCE_PATH),
            "compared": len(VERSION_COMPARISONS),
            "mismatches": [
                _version_mismatch_record(finding) for finding in findings
            ],
        },
    )


@register_check(
    "version-match",
    code=E_VERSION_MISMATCH,
    requirement="2.3, 2.4",
)
def check_version_match(context: ValidationContext) -> CheckResult:
    """The Power version is exactly the resolved tag *(R2 AC3, AC4)*.

    One recorded result for the one manifest, carrying one finding per mismatching
    pair. An absent, non-UTF-8, or unparseable `plugin.json` raises `Unevaluable`
    through `read_json` and is recorded as an `E_VERSION_MISMATCH` fail: a Power
    whose version cannot be read has not been shown to match the tag, which is why
    `read_power_version` may report `None` at the top of the report while this
    check records the failure.

    Nothing is written here. R2 AC4 asks that a mismatch leave the existing version
    and metadata unchanged, and that holds because this check — like every check —
    only reads the tree; preventing the tag is the derived `tagAllowed`, and the
    release procedure's refusal to tag without a passing report.
    """
    return version_match_result(context.tree.read_json(PLUGIN_MANIFEST), context.tag)


# ---------------------------------------------------------------------------
# The `residual-claude-refs` check (R10 AC2, R12 AC3, AC4, R15 AC8)
# ---------------------------------------------------------------------------
#
# The transformation rewrites Claude-specific text through named substitution
# sets, and a substitution set only rewrites what it names. This check is the
# other half of that arrangement: it reads the *produced* tree and reports what
# the sets did not reach. Two rules, and they are separate rules rather than one
# with two spellings:
#
# * **The root path token.** Zero occurrences of `${CLAUDE_PLUGIN_ROOT}` may
#   remain in a ported file *(R10 AC2)*. That is a count, so the report states it
#   — `rootTokenOccurrences` — rather than leaving "zero" to be inferred from an
#   empty findings list.
# * **Claude-specific model references.** Every residual subscription plan, model
#   name, or effort setting is reported with its **source document and its
#   location within that document** *(R12 AC3)*, and any hit flags the outcome
#   `incomplete` rather than successful *(R12 AC4)*.
#
# **Severity is the whole of R12 AC4.** `W_RESIDUAL_CLAUDE_REF` is the catalog's
# one warning code: the produced Power is structurally valid — it packages,
# schema-validates, and loads — and what is wrong is its *content*. A warning
# makes this result a `warn`, a `warn` folds the run to `incomplete`, and
# `incomplete` is neither `passed` nor `failed` while still leaving `tagAllowed`
# false. Nothing here assigns a status; the severity of the code does it
# *(Property 9)*.
#
# **The `INV-NNN` exemption is scoped to the token, not to the document**
# *(R15 AC8)*. Ported prose cites Template_Invariants by number, the engine
# preserves each citation verbatim *(R15 AC7)*, and such a citation is compliant
# content — never a residual hit. The mechanism is the engine's own, deliberately:
# the citation is one alternative of a single combined pattern, listed *first*, so
# a scan consumes `INV-052` as an exemption and resumes immediately after it.
# What that buys is exactly the narrow scoping the requirement asks for — the
# exemption covers the six-or-so characters of the citation and nothing else, so a
# genuine `Sonnet 5` sitting in the same document, the same paragraph, or the same
# sentence as a citation is still reported. An exemption keyed on the *document*
# would have made a citation a licence to carry residual references.
#
# **The term catalog is patterns, single-sourced where the contract already
# carries the terms.** R12 AC2's categories are open-ended — "a Claude
# subscription plan such as Claude Max, a Claude model name such as Sonnet, or a
# Claude effort setting" — so a fixed table of the five strings release 0.5.1
# happens to use would report nothing when upstream writes `Opus 4.1`. The
# declared catalog is therefore one pattern per category, and
# `contract_claude_terms` folds in any literal `find` term from the contract's
# `plugin-root`, `client-names`, and `model-guidance` sets that those patterns do
# not already cover: adding a term to the contract extends the gate with no code
# change, and a term the patterns already catch is not duplicated into the
# catalog. A contract is not required — the declared patterns stand alone — which
# is what keeps this check a pure function of document text.
#
# **What is deliberately *not* a term:** the `.claude-plugin` path segment. The
# `manifest-path` set repoints it, and the Power's own hook-parity documentation
# discusses that rewrite by name in Kiro-authored content; making the segment a
# term would report that sentence as a defect on every run. A bare `Claude` is out
# for the same reason — the template repository is named
# `senzing-bootcamp-claude-plugin`, and the Power cites it as its provenance.
#
# **A model name and an effort level are Claude-specific only when Claude-*named*.**
# Kiro serves the same frontier models the template recommends and carries the same
# reasoning-effort dial: its model picker offers Opus, Sonnet, and Haiku tiers
# (https://kiro.dev/docs/models/available-models/) and reasoning effort is a
# documented Kiro setting with the same low/medium/high/xhigh/max levels
# (https://kiro.dev/docs/models/effort/). So `Opus 5, high reasoning effort` is
# *correct guidance for a Kiro Bootcamper*, and reporting it as a residual would
# demand the Power either name no model at all or name one through a placeholder
# nobody can select in the picker — R12 AC2 asks for the corresponding Kiro model
# name, and here that name is the same name.
#
# What stays a term is the Claude-*qualified* spelling, which no Kiro surface uses:
# the prose form (`Claude Opus 5`) and the Anthropic API id form (`claude-opus-5`),
# which a Kiro user never types because models are chosen from a picker. Effort
# keeps the same treatment — `Claude reasoning effort` — plus the two settings that
# are Claude-only vocabulary in any spelling, `extended thinking` and `ultrathink`.
# The categories stay open-ended within that: an unreleased `Claude Opus 9.9` and a
# `claude-fable-7` id are both caught by shape.
#
# **Nothing is skipped.** The sweep is every file in the produced tree, and a
# file whose bytes are not valid UTF-8 is decoded lossily rather than declined: a
# residual token hiding in a file the validator refused to read is precisely the
# hit that must not be missed, and the terms are ASCII, so a lossy decode finds
# them. Code fences are *not* blanked either — unlike `cross-references`, where a
# link shown as an example is not a link. A `${CLAUDE_PLUGIN_ROOT}` shown as an
# example in ported documentation is still a Claude-specific reference the
# Bootcamper would read and copy.
#
# Everything above the registered check is a pure function of text, so
# *Property 9* and *Property 25* drive the scan from generated documents with no
# staging tree.

#: The template root path token R10 AC2 requires rewritten to `${PLUGIN_ROOT}`.
CLAUDE_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"

#: `hits[].kind` — which rule a hit answers to. The catalog code is
#: `W_RESIDUAL_CLAUDE_REF` for all of them, because the Maintainer response is
#: the same; the kind says which term survived and therefore which substitution
#: set to look at, so it travels as data.
RESIDUAL_ROOT_TOKEN = "root-token"
RESIDUAL_CLIENT_NAME = "client-name"
RESIDUAL_SUBSCRIPTION_PLAN = "subscription-plan"
RESIDUAL_MODEL_NAME = "model-name"
RESIDUAL_EFFORT_SETTING = "effort-setting"
#: A term the contract names that the declared categories do not classify. The
#: honest kind for "the contract says rewrite this and it was not rewritten".
RESIDUAL_MODEL_GUIDANCE = "model-guidance"

RESIDUAL_KINDS: tuple[str, ...] = (
    RESIDUAL_ROOT_TOKEN,
    RESIDUAL_CLIENT_NAME,
    RESIDUAL_SUBSCRIPTION_PLAN,
    RESIDUAL_MODEL_NAME,
    RESIDUAL_EFFORT_SETTING,
    RESIDUAL_MODEL_GUIDANCE,
)

#: How each kind is named in a finding, and the rule it answers to. R12 AC3 asks
#: the report to name the reference; a Maintainer also needs to know which rewrite
#: was supposed to have handled it, so the remedy travels with the phrase.
_RESIDUAL_KIND_RULES: Mapping[str, tuple[str, str]] = {
    RESIDUAL_ROOT_TOKEN: (
        "the template root path token",
        "the 'plugin-root' substitution set rewrites every occurrence to "
        "${PLUGIN_ROOT}, so zero may remain in a ported file (R10 AC2)",
    ),
    RESIDUAL_CLIENT_NAME: (
        "a Claude client name",
        "the 'client-names' substitution set rewrites each one to 'Kiro' "
        "(R12 AC2)",
    ),
    RESIDUAL_SUBSCRIPTION_PLAN: (
        "a Claude subscription plan reference",
        "the 'model-guidance' substitution set replaces each Claude plan "
        "reference with its Kiro equivalent (R12 AC2)",
    ),
    RESIDUAL_MODEL_NAME: (
        "a Claude model name",
        "the 'model-guidance' substitution set replaces each Claude model name "
        "with the corresponding Kiro model name (R12 AC2)",
    ),
    RESIDUAL_EFFORT_SETTING: (
        "a Claude effort setting",
        "the 'model-guidance' substitution set replaces each Claude effort "
        "setting with the corresponding Kiro effort setting (R12 AC2)",
    ),
    RESIDUAL_MODEL_GUIDANCE: (
        "a Claude-specific reference the contract names",
        "the substitution set that declares this term did not reach this file "
        "(R12 AC2)",
    ),
}

#: Where a contract-declared term comes from when it is not read from a set.
TERM_ORIGIN_DECLARED = "declared"

#: The contract substitution sets whose literal `find` terms are, by
#: construction, exactly the strings that must not survive the port — so they are
#: read from the contract rather than restated here (R3 AC4). Each maps to the
#: kind a term of that set carries when the declared patterns do not classify it.
RESIDUAL_TERM_SETS: Mapping[str, str] = {
    "plugin-root": RESIDUAL_ROOT_TOKEN,
    "client-names": RESIDUAL_CLIENT_NAME,
    "model-guidance": RESIDUAL_MODEL_GUIDANCE,
}


@dataclass(frozen=True)
class ClaudeTerm:
    """One entry of the residual-reference catalog: a kind and a pattern.

    `name` is how the entry is *named* in a report — the literal term for a
    contract-derived entry, a category for a declared pattern — while the
    evidence a finding carries is always the text actually matched. `origin` says
    where the entry came from, so a hit on a contract term names the set that
    declared it.

    Frozen and string-valued so a catalog is hashable, which is what lets the
    combined pattern be compiled once per catalog rather than once per document.
    """

    kind: str
    name: str
    pattern: str
    origin: str = TERM_ORIGIN_DECLARED

    @property
    def from_contract(self) -> bool:
        return self.origin != TERM_ORIGIN_DECLARED


#: One pattern per category R12 AC2 names, plus R10 AC2's token. Each is written
#: to match the *shape* of a reference rather than a fixed string, because the
#: requirement's categories are open-ended and the point of the check is to catch
#: what no substitution set named. Word-bounded throughout, so `Claude Product`
#: is not a plan and `Sonnetize` is not a model.
DECLARED_CLAUDE_TERMS: tuple[ClaudeTerm, ...] = (
    ClaudeTerm(
        kind=RESIDUAL_ROOT_TOKEN,
        name=CLAUDE_ROOT_TOKEN,
        pattern=re.escape(CLAUDE_ROOT_TOKEN),
    ),
    ClaudeTerm(
        kind=RESIDUAL_CLIENT_NAME,
        name="Claude Code / Claude Desktop",
        pattern=r"\bClaude[ \t]+(?:Code|Desktop)\b",
    ),
    ClaudeTerm(
        kind=RESIDUAL_SUBSCRIPTION_PLAN,
        name="a Claude subscription plan",
        pattern=r"\bClaude[ \t]+(?:Max|Pro|Team|Enterprise|Free)\b(?:[ \t]+plan\b)?",
    ),
    ClaudeTerm(
        kind=RESIDUAL_MODEL_NAME,
        name="a Claude model name",
        pattern=(
            r"\bClaude[ \t]+(?:Sonnet|Opus|Haiku|Fable)\b"
            r"(?:[ \t]+[0-9]+(?:\.[0-9]+)*)?"
            r"|\bclaude-(?:sonnet|opus|haiku|fable)(?:-[0-9]+)*"
            r"(?![0-9A-Za-z_])"
        ),
    ),
    ClaudeTerm(
        kind=RESIDUAL_EFFORT_SETTING,
        name="a Claude effort setting",
        pattern=(
            r"\bClaude[ \t]+(?:thinking|reasoning)[ \t]+effort"
            r"(?:[ \t]*[:=]?[ \t]*"
            r"(?:none|minimal|low|medium|high|max(?:imum)?)\b)?"
            r"|\bextended[ \t]+thinking\b"
            r"|\bultrathink\b"
        ),
    ),
)

#: Group names in a catalog's combined pattern. The exemption group is listed
#: first, so a citation wins every position it can match (R15 AC8).
_EXEMPT_GROUP = "_citation"
_TERM_GROUP_PREFIX = "_term"


@lru_cache(maxsize=None)
def _term_pattern(terms: tuple[ClaudeTerm, ...]) -> re.Pattern[str]:
    """One alternation over a catalog: the citation exemption, then each term.

    The shape is the engine's `_combined_pattern`, and for the same two reasons.
    Python's alternation is first-match-wins at a position, which is what makes
    the exemption an exemption rather than a filter applied afterwards; and
    `finditer` produces non-overlapping matches left to right, so one residual
    reference produces exactly one hit however many patterns could describe it —
    which is the "exactly *k* findings" half of *Property 9*.

    Case-insensitive, because a lowercased `sonnet 5` in a ported code sample is
    the same content problem as the capitalized one, and no catalog term is a
    string whose meaning depends on its case.
    """
    parts = [f"(?P<{_EXEMPT_GROUP}>{INVARIANT_CITATION.pattern})"]
    parts.extend(
        f"(?P<{_TERM_GROUP_PREFIX}{position}>{term.pattern})"
        for position, term in enumerate(terms)
    )
    return re.compile("|".join(parts), re.IGNORECASE | re.MULTILINE)


@lru_cache(maxsize=None)
def _coverage_pattern(terms: tuple[ClaudeTerm, ...]) -> re.Pattern[str]:
    """`terms` as one unnamed alternation, for asking whether a term is covered."""
    return re.compile(
        "|".join(f"(?:{term.pattern})" for term in terms), re.IGNORECASE
    )


def contract_claude_terms(contract: Contract | None) -> tuple[ClaudeTerm, ...]:
    """Literal contract terms the declared patterns do not already catch.

    Read from `RESIDUAL_TERM_SETS`, in the order the contract declares them, so a
    term added to the contract extends this gate with no code change (R3 AC4). A
    term the declared patterns match *in full* is dropped rather than added: it is
    already caught, and carrying it twice would only make the catalog overstate
    what it knows.

    Total by design — a missing set, a non-mapping entry, and a `regex` entry
    (which names a line, not a term) are each skipped rather than raised on. The
    engine already refuses a malformed contract loudly; a gate that could not read
    one term is not a reason to stop scanning for the others.
    """
    if contract is None:
        return ()
    covered = _coverage_pattern(DECLARED_CLAUDE_TERMS)
    terms: list[ClaudeTerm] = []
    for set_name, kind in RESIDUAL_TERM_SETS.items():
        for entry in contract.substitution_sets.get(set_name) or ():
            if not isinstance(entry, Mapping):
                continue
            find = entry.get("find")
            if not isinstance(find, str) or not find.strip():
                continue
            if covered.fullmatch(find) is not None:
                continue
            terms.append(
                ClaudeTerm(
                    kind=kind,
                    name=find,
                    pattern=re.escape(find),
                    origin=set_name,
                )
            )
    return tuple(terms)


def claude_terms(contract: Contract | None = None) -> tuple[ClaudeTerm, ...]:
    """The catalog a scan uses: contract-derived terms first, then the patterns.

    Contract terms lead because they are literal and specific: where one overlaps
    a declared pattern at the same position, the hit should name the term the
    contract wrote. The declared patterns stand alone when no contract was
    supplied, so this check never fails closed for want of one — it reports what
    it can see, and sees strictly more with a contract in hand.
    """
    return contract_claude_terms(contract) + DECLARED_CLAUDE_TERMS


@dataclass(frozen=True)
class ResidualReference:
    """One residual Claude-specific reference: what it is, and exactly where.

    `source` and `location` together are R12 AC3's requirement — the document
    *and* the position within it — and `text` is the matched string verbatim,
    because that is what a Maintainer searches for. `term` and `kind` name the
    catalog entry that caught it, so the hit points at the substitution set that
    should have.
    """

    source: str
    kind: str
    term: str
    text: str
    line: int
    column: int
    offset: int
    origin: str = TERM_ORIGIN_DECLARED

    @property
    def location(self) -> str:
        """The within-document position, as `Finding.location` spells one.

        Line *and* column: a ported script or a minified asset can carry a very
        long line, and "line 1" would not be a location within such a document.
        """
        return f"line {self.line} column {self.column}"

    def details(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.kind,
            "term": self.term,
            "match": self.text,
            "line": self.line,
            "column": self.column,
            "offset": self.offset,
            "origin": self.origin,
        }


def document_text(tree: PowerTree, path: str) -> str:
    """`path`'s bytes as text, decoded lossily rather than declined.

    `PowerTree.read_text` raises on bytes that are not UTF-8, which is right for
    a check that has to *parse* a document and wrong for one that scans every
    file in the tree: declining would exempt exactly the files a residual token
    could hide in. Every catalog term is ASCII, so replacing undecodable bytes
    costs nothing a term needed.
    """
    return tree.read_bytes(path).decode("utf-8", errors="replace")


def residual_references(
    text: str, *, source: str, terms: Sequence[ClaudeTerm] | None = None
) -> tuple[ResidualReference, ...]:
    """Every residual Claude-specific reference in one document, in order.

    Pure, and the single place text becomes a hit. An inline `INV-NNN` citation
    is consumed by the exemption alternative and yields nothing, while the scan
    resumes at the character after it — so a citation exempts itself and never
    the reference beside it (R15 AC8).
    """
    catalog = DECLARED_CLAUDE_TERMS if terms is None else tuple(terms)
    if not catalog or not text:
        return ()
    found: list[ResidualReference] = []
    for match in _term_pattern(catalog).finditer(text):
        if match.group(_EXEMPT_GROUP) is not None:
            continue
        for position, term in enumerate(catalog):
            if match.group(f"{_TERM_GROUP_PREFIX}{position}") is None:
                continue
            start = match.start()
            found.append(
                ResidualReference(
                    source=source,
                    kind=term.kind,
                    term=term.name,
                    text=match.group(0),
                    line=text.count("\n", 0, start) + 1,
                    column=start - text.rfind("\n", 0, start),
                    offset=start,
                    origin=term.origin,
                )
            )
            break
    return tuple(found)


def _residual_finding(reference: ResidualReference) -> Finding:
    """One residual reference, naming its document and its location *(R12 AC3)*."""
    phrase, remedy = _RESIDUAL_KIND_RULES[reference.kind]
    declared = (
        f" declared by the '{reference.origin}' substitution set"
        if reference.origin != TERM_ORIGIN_DECLARED
        else ""
    )
    return Finding(
        code=W_RESIDUAL_CLAUDE_REF,
        message=(
            f"{reference.source} still carries {phrase}{declared}, "
            f"{reference.text!r}, at {reference.location}; {remedy}. The produced "
            "Power is structurally valid, so the transformation outcome is "
            "incomplete rather than failed, and tagging stays blocked until this "
            "is rewritten or the substitution set is extended to name it "
            "(R12 AC4)"
        ),
        target=reference.source,
        location=reference.location,
        details=reference.details(),
    )


def residual_findings(
    references: Iterable[ResidualReference],
) -> tuple[Finding, ...]:
    """One warning-severity finding per residual reference, in scan order.

    Every reference gets its own finding — a document carrying four residual
    model names reports four, not "this document has residual references"
    (design principle 1, and *Property 9*'s exact count).
    """
    return tuple(_residual_finding(reference) for reference in references)


def _residual_hit_record(reference: ResidualReference) -> dict[str, Any]:
    """The compact per-hit row this check's `hits` array carries."""
    return {
        "source": reference.source,
        "term": reference.term,
        "kind": reference.kind,
        "match": reference.text,
        "location": reference.location,
        "line": reference.line,
        "column": reference.column,
    }


def residual_claude_result(
    documents: Mapping[str, str], *, terms: Sequence[ClaudeTerm] | None = None
) -> CheckResult:
    """The recorded result for a mapping of document path → text.

    Pure, and the whole of the check — `check_residual_claude_refs` adds only the
    reads. Documents are swept in sorted path order so the findings a tree
    produces are a function of the tree alone.

    `rootTokenOccurrences` states R10 AC2's count outright, including the zero on
    a clean run: "zero occurrences remain" is a claim the report should make
    rather than one a reader has to infer from an empty findings list.
    `invariantCitations` counts the citations the sweep passed over, which is the
    evidence that preserved prose was read and left alone (R15 AC7, AC8).
    """
    catalog = DECLARED_CLAUDE_TERMS if terms is None else tuple(terms)
    references: list[ResidualReference] = []
    citations = 0
    for source in sorted(documents):
        text = documents[source]
        references.extend(residual_references(text, source=source, terms=catalog))
        citations += len(invariant_citations(text))

    counts = {
        kind: sum(1 for reference in references if reference.kind == kind)
        for kind in RESIDUAL_KINDS
    }
    return CheckResult(
        id="residual-claude-refs",
        findings=residual_findings(references),
        extra={
            "documents": len(documents),
            "terms": len(catalog),
            "contractTerms": sum(1 for term in catalog if term.from_contract),
            "invariantCitations": citations,
            "rootTokenOccurrences": counts[RESIDUAL_ROOT_TOKEN],
            "byKind": counts,
            "hits": [_residual_hit_record(reference) for reference in references],
        },
    )


@register_check(
    "residual-claude-refs",
    code=W_RESIDUAL_CLAUDE_REF,
    unevaluated_code=E_CHECK_UNEVALUATED,
    requirement="10.2, 12.3, 12.4, 15.8",
)
def check_residual_claude_refs(context: ValidationContext) -> CheckResult:
    """No Claude-specific reference survived the port *(R10 AC2, R12 AC3, AC4)*.

    One recorded result for the whole tree, carrying one warning-severity finding
    per residual reference with its source document and its location within that
    document. Any hit therefore folds the run to `incomplete` — structurally
    valid, content-incomplete — and leaves `tagAllowed` false, both by the
    severity of the code rather than by anything assigned here *(R12 AC4, R13
    AC4)*.

    The contract is used when supplied and not required: it contributes the
    literal terms the sets declare, and the declared patterns cover the
    categories on their own. An empty tree is the one condition that declines to
    answer — nothing was scanned, so nothing was shown clean, and a check that
    reached no verdict is a fail.
    """
    tree = context.tree
    if not tree.paths:
        raise Unevaluable(
            "the produced Power carries no file, so no ported content could be "
            "scanned for residual Claude-specific references"
        )
    documents = {path: document_text(tree, path) for path in tree.paths}
    return residual_claude_result(documents, terms=claude_terms(context.contract))


# ---------------------------------------------------------------------------
# The `invariant-discounts` check (R15 AC4-AC6, AC11)
# ---------------------------------------------------------------------------
#
# The template's `INV-NNN` invariants were authored for a Claude plugin. Where
# honoring one as written would prevent correct Kiro construction, the
# Kiro-correct construction wins and the conflicting invariant is *discounted*
# — and a discount is a judgment, so it is recorded: which invariant, what it
# conflicted with, and what was built instead *(R15 AC4)*. The record lives
# inside the contract, which is what makes the Create_Skill and the Update_Skill
# apply an identical discount set *(R15 AC11)*. This check is what keeps that
# record honest.
#
# Two conditions, two codes, and they are not two spellings of one rule:
#
# * **Completeness.** Every entry carries a non-empty `invariant`,
#   `conflictsWith`, and `resolution`. An entry omitting one of the three is
#   `E_INCOMPLETE_DISCOUNT`, and the finding names **both the entry and the
#   field** *(R15 AC5)*, because "entry 2 is incomplete" does not tell a
#   Maintainer what to write. A half-recorded discount is worse than no entry at
#   all: it reads as a reviewed decision while carrying nothing reviewable, and
#   the Update_Skill's drift comparison will carry it forward as though a
#   judgment had been made.
# * **The honored invariant.** `INV-052` may not appear in the register at all.
#   Its exec-form wording — a `command` plus an `args` array — cannot be
#   reproduced under Kiro's single-command-string hook schema, and stopping there
#   would read as a discount. But the invariant does not state a wording; it
#   states a *guarantee*: hook execution depends on no shell, on Linux, macOS, or
#   Windows alike. That guarantee is preserved, restated in a Kiro mechanism, by
#   install-time absolute-path interpreter resolution *(R16 AC3, AC4)* — which is
#   R15 AC3's "retain as honored" case rather than R15 AC2's "discount" case. An
#   entry for it is therefore wrong by construction and not merely redundant: it
#   records as abandoned a guarantee the Power actually keeps and the
#   `hook-command-strings` check enforces. Hence `E_HONORED_INVARIANT_DISCOUNTED`
#   *(R15 AC6)*.
#
# **Every offending entry is reported, and every offending field of it**, not the
# first of either (design principle 1). A register with two incomplete entries
# and an `INV-052` entry produces findings for all three in one run, so the
# report is the full remaining work.
#
# Spelling cannot smuggle an entry past the exclusion
# ---------------------------------------------------
# Identifiers are compared with whitespace folded out and case raised, so
# `inv-052`, `INV-052 `, and `INV-052` are one identifier under three spellings.
# `INV-52` is a **different invariant** that merely reads like it, and stays
# different: the digit count is part of the identifier, exactly as the
# reconciliation report's drift comparison reads it. That is why the fold is not
# a regex over `INV-0*52`.
#
# The fold here is deliberately one step stronger than the update path's
# `normalize_invariant_id`, which trims rather than collapsing interior
# whitespace. This is an *exclusion*: a false negative admits the one entry
# R15 AC6 forbids, while the only entry a false positive can reject is one
# spelling an identifier with a space inside it, which is wrong however it is
# read. The trimming fold is still what names an invariant in the report, so what
# the gate and the update path call "the same invariant" does not diverge.
#
# A bare string where a mapping belongs — `- INV-052` written as a plain list
# item — is read as an entry naming that invariant and omitting the other two
# fields. It is reported as incomplete *and* caught by the exclusion, which is
# the point: the shorthand is exactly how an `INV-052` entry would arrive without
# looking like one.
#
# Everything below the registered check is a pure function of the parsed register
# — a sequence of entry mappings, no `PowerTree` and no filesystem — because
# *Property 25* drives it in both directions from generated registers. The
# registered check adds only the contract read, and it reads the contract through
# `require_contract`, so a run launched without one **blocks the tag** rather than
# passing a register it never saw.

#: The two fields carrying the judgment. The third — `DISCOUNT_INVARIANT_FIELD`,
#: the identifier the entry is about — is imported, because the update path reads
#: that one too and one contract key has one spelling.
DISCOUNT_CONFLICTS_FIELD = "conflictsWith"
DISCOUNT_RESOLUTION_FIELD = "resolution"

#: All three fields R15 AC4 requires of an entry, in the order a finding reports
#: them: the invariant discounted, the constraint it conflicts with, and the
#: resolution applied.
DISCOUNT_FIELDS: tuple[str, ...] = (
    DISCOUNT_INVARIANT_FIELD,
    DISCOUNT_CONFLICTS_FIELD,
    DISCOUNT_RESOLUTION_FIELD,
)

#: The Template_Invariant that is honored rather than discounted *(R15 AC3, AC6,
#: R16 AC3, AC4)*. Named once, here, because it is the whole content of the
#: exclusion; a second spelling would be a second thing to keep in step.
HONORED_INVARIANT = "INV-052"

#: What went wrong, in `details["kind"]` and in the report's `incomplete` and
#: `disallowed` arrays. Distinguishing an absent field from a blank one is not
#: pedantry: `resolution: ""` is a Maintainer who started writing and stopped,
#: and a bare `resolution:` in YAML parses to nothing at all, which reads as the
#: omission it is.
DISCOUNT_ENTRY_UNUSABLE = "entry-unusable"
DISCOUNT_FIELD_ABSENT = "field-absent"
DISCOUNT_FIELD_BLANK = "field-blank"
DISCOUNT_FIELD_UNUSABLE = "field-unusable"
DISCOUNT_HONORED_INVARIANT = "honored-invariant"

DISCOUNT_KINDS: tuple[str, ...] = (
    DISCOUNT_ENTRY_UNUSABLE,
    DISCOUNT_FIELD_ABSENT,
    DISCOUNT_FIELD_BLANK,
    DISCOUNT_FIELD_UNUSABLE,
    DISCOUNT_HONORED_INVARIANT,
)

#: The three field names as a message spells them.
_DISCOUNT_FIELD_LIST = ", ".join(repr(name) for name in DISCOUNT_FIELDS)

#: How each field is named in a finding, so the message says what the Maintainer
#: has to write rather than only which key is missing.
_DISCOUNT_FIELD_PHRASES: Mapping[str, str] = {
    DISCOUNT_INVARIANT_FIELD: "the Template_Invariant identifier it discounts",
    DISCOUNT_CONFLICTS_FIELD: (
        "the Agent Plugins clause or Kiro mechanism it conflicts with"
    ),
    DISCOUNT_RESOLUTION_FIELD: (
        "the construction implemented instead, and why nothing protected is lost"
    ),
}

#: Why `INV-052` is not discountable, in one sentence, appended to every
#: exclusion finding. Fixed text, because the answer never varies with the entry:
#: the response is always to delete it, never to complete it.
_HONORED_RATIONALE = (
    f"{HONORED_INVARIANT} is honored, not discounted: its exec-form wording "
    "cannot be reproduced under Kiro's single-command-string hook schema, but "
    "the guarantee it states — hook execution depending on no shell on Linux, "
    "macOS, or Windows — is preserved by install-time absolute-path interpreter "
    "resolution (R16 AC3, AC4), so the invariant is retained as honored "
    "(R15 AC3) and no entry for it may appear in the register (R15 AC6); remove "
    "the entry rather than completing it"
)


def invariant_spelling(identifier: Any) -> str:
    """One spelling of an identifier, whitespace folded out and case raised.

    `inv-052`, `INV-052 `, and `INV- 052` all fold to `INV-052`: one invariant
    under several spellings. `INV-52` folds to `INV-52` and stays a *different*
    invariant, because the digit count is part of the identifier.

    Stronger than `normalize_invariant_id` only in collapsing interior
    whitespace, and used only where a missed match would *admit* something —
    see this section's header.
    """
    return "".join(identifier.split()).upper() if isinstance(identifier, str) else ""


def names_honored_invariant(identifier: Any) -> bool:
    """True when `identifier` is `INV-052` under any spelling of it."""
    return bool(identifier) and invariant_spelling(identifier) == invariant_spelling(
        HONORED_INVARIANT
    )


@dataclass(frozen=True)
class DiscountEntry:
    """One Invariant_Discount_Register entry, at its position in the register.

    `raw` is held **as parsed** — an absent field stays absent, a blank one stays
    blank, a bare string stays a string — because R15 AC5 asks the finding to name
    what the entry actually carries, and a value normalized on the way in is a
    value the message would misreport.
    """

    index: int
    raw: Any

    @property
    def is_mapping(self) -> bool:
        return isinstance(self.raw, Mapping)

    @property
    def invariant(self) -> Any:
        """The identifier this entry names, or `None` when it names none.

        A bare string entry names itself, which is how `- INV-052` written as a
        plain list item is still caught by the exclusion.
        """
        if self.is_mapping:
            return self.raw.get(DISCOUNT_INVARIANT_FIELD)
        return self.raw if isinstance(self.raw, str) else None

    @property
    def position(self) -> str:
        """Where the entry sits, as a message names it."""
        return f"{DISCOUNT_REGISTER_KEY} entry {self.index}"

    @property
    def label(self) -> str:
        """Position and identifier, so a completeness finding names both.

        The identifier is appended only when the entry carries a usable one:
        R15 AC5's own case is an entry omitting it, and `entry 2 (None)` names
        nothing a Maintainer can search for.
        """
        identifier = self.invariant
        named = (
            f" ({identifier!r})"
            if isinstance(identifier, str) and identifier.strip()
            else ""
        )
        return f"{self.position}{named}"

    def location(self, field: str | None = None) -> str | None:
        """Where in the contract this entry, or one field of it, sits."""
        path: tuple[Any, ...] = (DISCOUNT_REGISTER_KEY, self.index)
        return document_location(path + ((field,) if field else ()))

    def field_state(self, field: str) -> str | None:
        """What is wrong with one field, or `None` when nothing is.

        `None` for a value present, string, and non-blank after stripping — the
        whole of "non-empty" in R15 AC4. A key absent and a key present holding
        nothing are one condition, because a bare `resolution:` in YAML parses to
        `None` and reads as the omission it is.
        """
        if not self.is_mapping:
            return DISCOUNT_ENTRY_UNUSABLE
        value = self.raw.get(field)
        if field not in self.raw or value is None:
            return DISCOUNT_FIELD_ABSENT
        if not isinstance(value, str):
            return DISCOUNT_FIELD_UNUSABLE
        if not value.strip():
            return DISCOUNT_FIELD_BLANK
        return None

    @property
    def complete(self) -> bool:
        """Every required field present, a string, and non-blank *(R15 AC4)*."""
        return self.is_mapping and all(
            self.field_state(field) is None for field in DISCOUNT_FIELDS
        )


def discount_entries(register: Any) -> tuple[DiscountEntry, ...]:
    """The register as positioned entries, in register order.

    Total over anything list-shaped, and a non-mapping element is **kept** rather
    than dropped: an element this function discarded is an element no finding
    would ever name, which is how a malformed entry would pass. A register that is
    not list-shaped at all is `declared_discounts`' problem, not this one's.
    """
    if register is None:
        return ()
    if isinstance(register, (str, bytes)) or not isinstance(register, Sequence):
        return ()
    return tuple(
        DiscountEntry(index=index, raw=entry) for index, entry in enumerate(register)
    )


def _incomplete_finding(
    entry: DiscountEntry, message: str, *, kind: str, field: str | None = None
) -> Finding:
    return Finding(
        code=E_INCOMPLETE_DISCOUNT,
        message=message,
        location=entry.location(field),
        details={
            "kind": kind,
            "entry": entry.index,
            "field": field,
            DISCOUNT_INVARIANT_FIELD: entry.invariant,
        },
    )


def _entry_findings(entry: DiscountEntry) -> tuple[Finding, ...]:
    """Every field of one entry that R15 AC4 requires and the entry lacks.

    One finding per missing field, not one per entry: an entry recording only an
    identifier owes two fields, and a Maintainer told "incomplete" once would
    write one of them and run the gate again.
    """
    if not entry.is_mapping:
        return (
            _incomplete_finding(
                entry,
                f"{entry.position} is a non-mapping "
                f"{type(entry.raw).__name__} ({entry.raw!r}), so it carries none "
                f"of {_DISCOUNT_FIELD_LIST}; a discount records the invariant it "
                "discounts, the constraint it conflicts with, and the resolution "
                "applied, and R15 AC4 makes all three mandatory and non-empty "
                "(R15 AC5)",
                kind=DISCOUNT_ENTRY_UNUSABLE,
            ),
        )

    findings: list[Finding] = []
    for field_name in DISCOUNT_FIELDS:
        state = entry.field_state(field_name)
        if state is None:
            continue
        value = entry.raw.get(field_name)
        carried = {
            DISCOUNT_FIELD_ABSENT: f"omits {field_name!r}",
            DISCOUNT_FIELD_BLANK: (
                f"carries {field_name!r} as {value!r}, which is empty once "
                "surrounding whitespace is stripped"
            ),
            DISCOUNT_FIELD_UNUSABLE: (
                f"carries {field_name!r} as a non-string "
                f"{type(value).__name__} ({value!r})"
            ),
        }[state]
        findings.append(
            _incomplete_finding(
                entry,
                f"{entry.label} {carried}; that field records "
                f"{_DISCOUNT_FIELD_PHRASES[field_name]}, and R15 AC4 makes all "
                f"three of {_DISCOUNT_FIELD_LIST} mandatory and non-empty — an "
                "entry lacking one records a decision nothing can review "
                "(R15 AC5)",
                kind=state,
                field=field_name,
            )
        )
    return tuple(findings)


def incomplete_discount_findings(
    entries: Sequence[DiscountEntry],
) -> tuple[Finding, ...]:
    """One finding per missing field, over every entry in the register.

    Every entry is examined whatever an earlier one reported, so a register with
    three incomplete entries names three (design principle 1).
    """
    return tuple(finding for entry in entries for finding in _entry_findings(entry))


def honored_invariant_findings(
    entries: Sequence[DiscountEntry],
) -> tuple[Finding, ...]:
    """One finding per entry naming `INV-052`, under any spelling *(R15 AC6)*.

    The identifier is reported **as the register spells it** and the fold it
    matched under travels in `details`, so a Maintainer reading `'inv-052'` in the
    message can find the line and a consumer reading data sees why it matched.
    """
    return tuple(
        Finding(
            code=E_HONORED_INVARIANT_DISCOUNTED,
            message=(
                f"{entry.position} discounts {entry.invariant!r}, which is "
                f"{HONORED_INVARIANT}; {_HONORED_RATIONALE}"
            ),
            location=entry.location(DISCOUNT_INVARIANT_FIELD),
            details={
                "kind": DISCOUNT_HONORED_INVARIANT,
                "entry": entry.index,
                DISCOUNT_INVARIANT_FIELD: entry.invariant,
                "normalized": invariant_spelling(entry.invariant),
                "honoredInvariant": HONORED_INVARIANT,
            },
        )
        for entry in entries
        if names_honored_invariant(entry.invariant)
    )


def _discount_record(finding: Finding) -> dict[str, Any]:
    """The compact per-offender row the `incomplete` and `disallowed` arrays carry.

    `field` is `null` on a row about a whole entry rather than one field of it —
    an entry that is not a mapping at all, or an entry naming the honored
    invariant — because the position is the answer there and naming a field would
    invent one.
    """
    return {
        "entry": finding.details.get("entry"),
        DISCOUNT_INVARIANT_FIELD: finding.details.get(DISCOUNT_INVARIANT_FIELD),
        "field": finding.details.get("field"),
        "kind": finding.details.get("kind"),
        "location": finding.location,
    }


def discount_register_result(register: Any) -> CheckResult:
    """The recorded result for one parsed Invariant_Discount_Register.

    Pure, and the whole of the check — `check_invariant_discounts` adds only the
    contract read. `discounted` states what the register does discount — the
    invariants it names, folded and deduplicated exactly as the reconciliation
    report reads them — including the empty list on a clean run: "nothing is
    discounted" is a claim the report should make outright rather than one a
    reader infers from an empty findings list. *Property 25* drives this function
    directly, in both directions, from generated registers.
    """
    entries = discount_entries(register)
    incomplete = incomplete_discount_findings(entries)
    disallowed = honored_invariant_findings(entries)
    return CheckResult(
        id="invariant-discounts",
        findings=incomplete + disallowed,
        extra={
            "register": DISCOUNT_REGISTER_KEY,
            "entries": len(entries),
            "requiredFields": list(DISCOUNT_FIELDS),
            "honoredInvariant": HONORED_INVARIANT,
            "discounted": list(
                discount_invariant_ids(entry.raw for entry in entries)
            ),
            "incomplete": [_discount_record(finding) for finding in incomplete],
            "disallowed": [_discount_record(finding) for finding in disallowed],
        },
    )


def declared_discounts(contract: Contract) -> Any:
    """The register as the contract declares it, list-shaped or not at all.

    Raises `Unevaluable` on an absent or non-list declaration. A contract that
    lost the section therefore blocks the tag rather than being read as a register
    that discounts nothing — which is indistinguishable from the correct register
    this repository ships, and so would pass silently.

    An **empty** list, by contrast, is a verdict and not an absence: it says
    nothing is discounted, which is exactly what the checked-in contract declares
    *(R15 AC11)*.
    """
    if DISCOUNT_REGISTER_KEY not in contract.raw:
        raise Unevaluable(
            f"the contract at {contract.path} declares no "
            f"'{DISCOUNT_REGISTER_KEY}' section, so the Invariant_Discount_Register "
            "R15 AC11 keeps inside the contract is stated nowhere the gate can "
            "read it; declare it as an empty list where nothing is discounted"
        )
    declared = contract.raw[DISCOUNT_REGISTER_KEY]
    if (
        declared is None
        or isinstance(declared, (str, bytes))
        or not isinstance(declared, Sequence)
    ):
        raise Unevaluable(
            f"contract defect: '{DISCOUNT_REGISTER_KEY}' is a "
            f"{type(declared).__name__}, not a list of discount entries"
        )
    return declared


@register_check(
    "invariant-discounts",
    code=E_INCOMPLETE_DISCOUNT,
    requirement="15.5, 15.6",
)
def check_invariant_discounts(context: ValidationContext) -> CheckResult:
    """The discount register is complete and excludes `INV-052` *(R15 AC5, AC6)*.

    One recorded result for the one register, carrying one finding per missing
    field and one per entry naming the honored invariant — every offender in one
    run, so the report is the full remaining work.

    Fails closed without a contract: the register lives inside it *(R15 AC11)*,
    so a run given no contract has not been shown a complete register and records
    a fail rather than a pass it never earned.
    """
    return discount_register_result(declared_discounts(context.require_contract()))


# ---------------------------------------------------------------------------
# The `hook-command-strings` check (R10 AC5, R16 AC3-AC6)
# ---------------------------------------------------------------------------
#
# Kiro's hook schema takes a *single command string*, so the guarantee
# `INV-052` bought with an exec-form `command` + `args` pair has to be
# re-established inside one string: the interpreter named by an absolute path
# rather than a bare `python3`, both paths quoted, and nothing in the string a
# shell would read as an operator. This check is the enforcement half of that
# *(R16 AC6)*, and it looks at three populations:
#
# 1. the **Tier 2** assets under `skills/bootcamp-onboarding/assets/kiro-hooks/`,
#    which the `Hook_Installer` reads,
# 2. the **Tier 3** definitions under `dev.kiro/hooks/`, and
# 3. **what the installer would write** — every Tier 2 command string resolved
#    against a table of adversarial interpreter and script-directory paths.
#
# Population 3 is the one that matters at runtime: a shipped asset is not
# runnable, so checking only the shipped text would leave the quoting rule
# — the rule a space in `C:\Users\Bob Smith\` actually breaks — unchecked.
#
# **The reference implementation is imported from the Power under validation**
# (`skills/bootcamp-enforcement-setup/scripts/install_hooks.py`), not
# reimplemented here. Two reasons. First, the check must answer "what would the
# installer write?", and the only authority on that is the installer that
# ships; a second tokenizer in this file could agree with the specification and
# still disagree with the code a Bootcamper runs, which is precisely the drift
# the gate exists to catch. Second, one quoting rule with one implementation
# cannot develop two behaviors. The cost is that the check cannot detect a
# reference implementation that is *self-consistently* wrong, which is why the
# probe table below asserts an outcome the installer does not assert about
# itself: every emitted string must tokenize back to exactly the two-element
# vector `[interpreter, script]` for every path shape in the table. If the
# installer is absent or unloadable the check raises `Unevaluable` and fails
# closed, because a Power whose installer cannot be read is a Power whose hook
# command strings cannot be established.
#
# Everything below the loader is a pure function of in-memory data — a parsed
# document, a command string, a `HookCommandTools` — so *Property 24* can drive
# the scanning directly without a staging tree.

#: Where a produced Power keeps its hook definitions. Tier 2 is the asset
#: directory the `Hook_Installer` reads; Tier 3 is the bundled, inert copy.
HOOK_ASSETS_DIRECTORY = "skills/bootcamp-onboarding/assets/kiro-hooks"
TIER3_HOOKS_DIRECTORY = "dev.kiro/hooks"

#: The coverage map, which single-sources the glob that selects definitions. It
#: sits *in* the asset directory and is deliberately **not** prefixed, so it is
#: not a hook definition and must never be scanned as one.
HOOK_COVERAGE_MAP = f"{HOOK_ASSETS_DIRECTORY}/hook-parity-coverage.json"

#: The `Hook_Installer`, materialized into the Power. The reference
#: implementation this check imports.
HOOK_INSTALLER_SCRIPT = "skills/bootcamp-enforcement-setup/scripts/install_hooks.py"

#: Every hook file the Power owns carries this prefix (R7 AC9). Needed before
#: the installer is loaded, because it is what validates the declared glob.
HOOK_FILENAME_PREFIX = "senzing-bootcamp-"

#: Fallback for the glob the coverage map declares.
DEFAULT_HOOK_DEFINITION_GLOB = "senzing-bootcamp-*.json"

#: `CheckResult.target`: what the check examined, across both tiers.
HOOK_DEFINITION_TARGET = "**/senzing-bootcamp-*.json"

#: Where a command string came from. A shipped string still carries the two
#: placeholders; an installed one is fully resolved. The distinction changes
#: what the scans expect, so it travels with the string rather than being
#: inferred from its content.
ORIGIN_SHIPPED = "shipped"
ORIGIN_INSTALLED = "installed"

#: Shell builtins, matched case-insensitively against a **bare** name in the
#: command position only — an absolute path can never collide with one, so this
#: cannot fire on a resolved interpreter. Covers POSIX shells, `cmd.exe`, and
#: the PowerShell cmdlets that show up in a command string a human wrote by
#: hand. `SHELL_CONSTRUCTS` (from the installer) covers the operators; this
#: covers the *invocation* half of R16 AC5's "shell builtin invocation".
SHELL_BUILTINS = frozenset(
    {
        # POSIX / bash
        ".", ":", "alias", "bg", "bind", "break", "builtin", "cd", "command",
        "continue", "declare", "dirs", "disown", "echo", "enable", "eval",
        "exec", "exit", "export", "false", "fc", "fg", "getopts", "hash",
        "help", "history", "jobs", "let", "local", "logout", "popd", "printf",
        "pushd", "pwd", "read", "readonly", "return", "set", "shift", "shopt",
        "source", "suspend", "test", "times", "trap", "true", "type",
        "typeset", "ulimit", "umask", "unalias", "unset", "wait",
        # cmd.exe
        "assoc", "call", "chdir", "cls", "copy", "date", "del", "dir", "erase",
        "for", "goto", "if", "md", "mkdir", "move", "path", "pause", "prompt",
        "rd", "rem", "ren", "rename", "rmdir", "start", "time", "title", "ver",
        "verify", "vol",
        # PowerShell cmdlets that read as builtins to a hand-written string
        "foreach-object", "get-content", "invoke-expression", "out-file",
        "select-object", "set-location", "where-object", "write-host",
        "write-output",
    }
)

#: `C:\` and `Z:/` — recognized regardless of the platform the validator runs
#: on, because a Windows path must be judged absolute from Linux.
_DRIVE_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")

#: Module name the installer is loaded under. Fixed, so a second run rebinds
#: rather than accumulating modules.
_INSTALLER_MODULE_NAME = "_senzing_bootcamp_install_hooks_under_validation"

#: Names the check pulls out of the loaded installer.
_REQUIRED_INSTALLER_NAMES: tuple[str, ...] = (
    "InstallerError",
    "HOOK_FILENAME_PREFIX",
    "HOOK_SCHEMA_VERSION",
    "PLACEHOLDER_INTERPRETER",
    "PLACEHOLDER_SCRIPTS_DIR",
    "SHELL_CONSTRUCTS",
    "build_command",
    "find_shell_constructs",
    "quote_argument",
    "resolve_command",
    "tokenize_command",
    "unquoted_remainder",
)

#: Installer fault code → the catalog code this check reports it under. The
#: installer's vocabulary is finer than this check's two codes, so a definition
#: the installer rejects for shape lands under `E_BARE_INTERPRETER`: the
#: consequence is the same, no correctly resolved command can be written.
_INSTALLER_CODE_MAP: Mapping[str, str] = {
    "E_SHELL_CONSTRUCT": E_SHELL_CONSTRUCT_IN_HOOK,
}


def is_absolute_command_path(value: str) -> bool:
    """True when `value` is absolute on *some* Supported_Platform.

    `os.path.isabs` answers for the platform running the validator, which would
    call `C:\\Python312\\python.exe` relative when the gate runs on Linux — and
    the gate runs on one platform while the Power runs on three. So the three
    absolute shapes are recognized directly: a POSIX root, a UNC prefix, and a
    drive letter followed by a separator.
    """
    if not value:
        return False
    if value.startswith("/") or value.startswith("\\\\"):
        return True
    return _DRIVE_ABSOLUTE.match(value) is not None


def names_bare_interpreter(value: str) -> bool:
    """True when `value` is a bare command name rather than any kind of path.

    `python3`, `python`, `py`, `echo` — the shapes that need a PATH lookup, and
    on Windows the shapes that can reach a Microsoft Store alias stub *(R16
    AC2)*. A token carrying any separator is a path, well-formed or not.
    """
    if not value:
        return False
    if "/" in value or "\\" in value:
        return False
    return _DRIVE_ABSOLUTE.match(value) is None


def shell_builtin_named(token: str) -> str | None:
    """The shell builtin `token` invokes, or `None`.

    Only a bare name can be a builtin invocation: `/usr/bin/echo` is a program
    at an absolute path, which is exactly what this check wants to see.
    """
    if not names_bare_interpreter(token):
        return None
    name = token.strip()
    return name if name.casefold() in SHELL_BUILTINS else None


def load_installer_module(
    source: str, *, origin: str = HOOK_INSTALLER_SCRIPT
) -> types.ModuleType:
    """Load the `Hook_Installer` from its source text, without touching disk.

    The module is registered in `sys.modules` **before** its body runs. That is
    load-bearing rather than tidy: the installer declares dataclasses under
    `from __future__ import annotations`, and `dataclasses` resolves those
    string annotations through `sys.modules[cls.__module__]`, so a module that
    is not yet registered decorates its dataclasses against empty globals.
    """
    module = types.ModuleType(_INSTALLER_MODULE_NAME)
    module.__file__ = origin
    sys.modules[_INSTALLER_MODULE_NAME] = module
    try:
        exec(compile(source, origin, "exec"), module.__dict__)  # noqa: S102
    except Exception as error:  # noqa: BLE001 - reported, not raised onward
        sys.modules.pop(_INSTALLER_MODULE_NAME, None)
        raise Unevaluable(
            f"the Hook_Installer at {origin} cannot be loaded, so what it would "
            f"write into a Hook_Command_String cannot be established: "
            f"{type(error).__name__}: {error}",
            target=origin,
        ) from error
    return module


@dataclass(frozen=True)
class HookCommandTools:
    """The installer's command-string vocabulary, bound to one loaded copy.

    A record of callables rather than a module reference so a test can bind the
    template's own `install_hooks` module and drive every function below
    without a Power tree.
    """

    quote_argument: Callable[[str], str]
    tokenize_command: Callable[[str], tuple[str, ...]]
    unquoted_remainder: Callable[[str], str]
    find_shell_constructs: Callable[[str], tuple[str, ...]]
    build_command: Callable[..., str]
    resolve_command: Callable[..., tuple[str, tuple[str, ...]]]
    installer_error: type[BaseException]
    shell_constructs: tuple[str, ...]
    placeholder_interpreter: str
    placeholder_scripts_dir: str
    hook_schema_version: str
    hook_filename_prefix: str
    source: str = HOOK_INSTALLER_SCRIPT

    @classmethod
    def from_module(
        cls, module: Any, *, source: str = HOOK_INSTALLER_SCRIPT
    ) -> HookCommandTools:
        missing = [
            name for name in _REQUIRED_INSTALLER_NAMES if not hasattr(module, name)
        ]
        if missing:
            raise Unevaluable(
                f"the Hook_Installer at {source} does not export "
                f"{', '.join(missing)}, so its command-string construction "
                "cannot be validated",
                target=source,
            )
        return cls(
            quote_argument=module.quote_argument,
            tokenize_command=module.tokenize_command,
            unquoted_remainder=module.unquoted_remainder,
            find_shell_constructs=module.find_shell_constructs,
            build_command=module.build_command,
            resolve_command=module.resolve_command,
            installer_error=module.InstallerError,
            shell_constructs=tuple(module.SHELL_CONSTRUCTS),
            placeholder_interpreter=module.PLACEHOLDER_INTERPRETER,
            placeholder_scripts_dir=module.PLACEHOLDER_SCRIPTS_DIR,
            hook_schema_version=module.HOOK_SCHEMA_VERSION,
            hook_filename_prefix=module.HOOK_FILENAME_PREFIX,
            source=source,
        )


def load_hook_command_tools(tree: PowerTree) -> HookCommandTools:
    """Bind the command-string vocabulary of the Power's own installer copy."""
    return HookCommandTools.from_module(
        load_installer_module(tree.read_text(HOOK_INSTALLER_SCRIPT)),
        source=HOOK_INSTALLER_SCRIPT,
    )


@dataclass(frozen=True)
class InstallerProbe:
    """One (interpreter, scripts directory) pair the installer might resolve to.

    The table below is the adversarial half of "anything the `Hook_Installer`
    would write": the path shapes that break naive string assembly. It mirrors
    the generator cases `interpreter_path()` produces — POSIX, drive-letter and
    UNC shapes; single, repeated and trailing spaces; an embedded quote; and
    directory names carrying `&`, `|`, `;`, `>` — so the fixed table and the
    generated one agree on what "hard" means.
    """

    label: str
    interpreter: str
    scripts_directory: str


def _posix_probe(label: str, directory: str) -> InstallerProbe:
    return InstallerProbe(
        label=label,
        interpreter=f"/home/{directory}/.venv/bin/python3.12",
        scripts_directory=(
            f"/home/{directory}/powers/senzing-bootcamp/skills"
            "/bootcamp-onboarding/scripts"
        ),
    )


def _windows_probe(label: str, directory: str) -> InstallerProbe:
    return InstallerProbe(
        label=label,
        interpreter=(
            f"C:\\Users\\{directory}\\AppData\\Local\\Programs\\Python"
            "\\Python312\\python.exe"
        ),
        scripts_directory=(
            f"C:\\Users\\{directory}\\powers\\senzing-bootcamp\\skills"
            "\\bootcamp-onboarding\\scripts"
        ),
    )


#: Deliberately fixed and small: nine resolutions per shipped command string is
#: cheap, and every entry is a path shape a real Bootcamper can have.
INSTALLER_PROBES: tuple[InstallerProbe, ...] = (
    _posix_probe("posix", "bob"),
    _posix_probe("posix-single-space", "Bob Smith"),
    _posix_probe("posix-repeated-spaces", "Bob  Smith"),
    _posix_probe("posix-trailing-space", "Bob Smith "),
    _posix_probe("posix-embedded-quote", 'Bob "Bo" Smith'),
    _posix_probe("posix-shell-characters", "a&b|c;d>e"),
    _windows_probe("windows-drive-letter", "Bob Smith"),
    _windows_probe("windows-shell-characters", "a&b|c;d>e"),
    InstallerProbe(
        label="unc-prefix",
        interpreter="\\\\build01\\tools\\Python312\\python.exe",
        scripts_directory=(
            "\\\\build01\\Bob Smith\\powers\\senzing-bootcamp\\skills"
            "\\bootcamp-onboarding\\scripts"
        ),
    ),
)


@dataclass(frozen=True)
class HookCommand:
    """One Hook_Command_String, named by where it came from.

    R16 AC6 asks for "the offending hook definition and the offending
    construct", so the definition path, the hook name and the position travel
    with the string rather than being reconstructed when a finding is built.
    """

    definition: str
    hook_name: str
    index: int
    command: str
    origin: str = ORIGIN_SHIPPED
    probe: str | None = None

    @property
    def resolved(self) -> bool:
        return self.origin == ORIGIN_INSTALLED

    @property
    def location(self) -> str:
        return f"hooks[{self.index}].action.command"

    def details(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "hook": self.hook_name,
            "origin": self.origin,
            "command": self.command,
        }
        if self.probe is not None:
            payload["probe"] = self.probe
        return payload


def strip_command_placeholders(tools: HookCommandTools, command: str) -> str:
    """Remove the two placeholder tokens from an **unresolved** command string.

    The coverage map's `commandStringPolicy.validatorGuidance` asks for exactly
    this, and the reason is worth stating: the placeholders are spelled
    `<ABSOLUTE_PYTHON>` and `<ABSOLUTE_SCRIPTS_DIR>`, so a redirection scan over
    a shipped asset reports the angle brackets of the placeholders themselves —
    a false `<`/`>` on every correct definition. Removing them leaves the
    quotes and separators in place, so the scan still sees the real structure.
    A *resolved* command has no placeholders and is scanned in full.
    """
    for placeholder in (tools.placeholder_interpreter, tools.placeholder_scripts_dir):
        command = command.replace(placeholder, "")
    return command


def hook_command_findings(
    tools: HookCommandTools, entry: HookCommand
) -> tuple[Finding, ...]:
    """Every rule one Hook_Command_String violates, in one pass.

    Pure over `entry` and the bound reference implementation, and it reports
    *all* violations of one string rather than the first — a command that is
    both unquoted and chained names both faults.

    Four rules, each traceable: no shell construct outside a quoted span *(R16
    AC5, AC6)*; the string tokenizes to exactly `[interpreter, script]`, so no
    space in either path can split it; the interpreter is an absolute path — or,
    in a shipped asset, the placeholder the installer resolves — never a bare
    name *(R16 AC3)*; and nothing but separators sits outside a quoted span,
    which is "both paths quoted" stated as a property of the whole string
    rather than as two spot checks *(R16 AC4)*.
    """
    findings: list[Finding] = []
    base = entry.details()
    scanned = (
        entry.command
        if entry.resolved
        else strip_command_placeholders(tools, entry.command)
    )

    for construct in tools.find_shell_constructs(scanned):
        findings.append(
            Finding(
                code=E_SHELL_CONSTRUCT_IN_HOOK,
                message=(
                    f"hook {entry.hook_name!r} in {entry.definition} carries the "
                    f"shell construct {construct!r} outside a quoted span; a "
                    "Hook_Command_String is an interpreter path followed by "
                    "script arguments and nothing else"
                ),
                target=entry.definition,
                location=entry.location,
                details={**base, "construct": construct},
            )
        )

    tokens = tools.tokenize_command(entry.command)

    if tokens:
        builtin = shell_builtin_named(tokens[0])
        if builtin is not None:
            findings.append(
                Finding(
                    code=E_SHELL_CONSTRUCT_IN_HOOK,
                    message=(
                        f"hook {entry.hook_name!r} in {entry.definition} invokes "
                        f"the shell builtin {builtin!r} in the command position; "
                        "a Hook_Command_String may invoke only an interpreter at "
                        "an absolute path"
                    ),
                    target=entry.definition,
                    location=entry.location,
                    details={**base, "construct": builtin},
                )
            )

    if len(tokens) != 2:
        findings.append(
            Finding(
                code=E_BARE_INTERPRETER,
                message=(
                    f"hook {entry.hook_name!r} in {entry.definition} tokenizes to "
                    f"{len(tokens)} argument(s) rather than the two-element "
                    "vector [interpreter, script]; a path containing a space "
                    "that is not quoted splits into two arguments"
                ),
                target=entry.definition,
                location=entry.location,
                details={**base, "tokens": list(tokens)},
            )
        )

    remainder = tools.unquoted_remainder(entry.command)
    if remainder.strip():
        findings.append(
            Finding(
                code=E_BARE_INTERPRETER,
                message=(
                    f"hook {entry.hook_name!r} in {entry.definition} leaves "
                    f"{remainder.strip()!r} outside a quoted span; both the "
                    "interpreter path and the script path must be quoted so a "
                    "path containing a space is passed as one argument"
                ),
                target=entry.definition,
                location=entry.location,
                details={**base, "unquoted": remainder},
            )
        )

    if tokens:
        interpreter = tokens[0]
        if entry.resolved:
            if not is_absolute_command_path(interpreter):
                kind = (
                    "the bare interpreter name"
                    if names_bare_interpreter(interpreter)
                    else "the non-absolute path"
                )
                findings.append(
                    Finding(
                        code=E_BARE_INTERPRETER,
                        message=(
                            f"hook {entry.hook_name!r} in {entry.definition} names "
                            f"{kind} {interpreter!r} in the command position; the "
                            "interpreter must be an absolute filesystem path, "
                            "because python3 is frequently absent from PATH on "
                            "Windows and may resolve to a Store alias stub"
                        ),
                        target=entry.definition,
                        location=entry.location,
                        details={**base, "interpreter": interpreter},
                    )
                )
        elif interpreter != tools.placeholder_interpreter:
            findings.append(
                Finding(
                    code=E_BARE_INTERPRETER,
                    message=(
                        f"hook {entry.hook_name!r} in {entry.definition} names "
                        f"{interpreter!r} in the command position; a shipped hook "
                        f"definition must carry {tools.placeholder_interpreter} "
                        "there, so the interpreter is the absolute path the "
                        "Hook_Installer resolves at install time"
                    ),
                    target=entry.definition,
                    location=entry.location,
                    details={
                        **base,
                        "interpreter": interpreter,
                        "expected": tools.placeholder_interpreter,
                    },
                )
            )

    if len(tokens) == 2:
        reemitted = tools.build_command(tokens[0], (tokens[1],))
        recovered = tools.tokenize_command(reemitted)
        if recovered != tokens:
            findings.append(
                Finding(
                    code=E_BARE_INTERPRETER,
                    message=(
                        f"hook {entry.hook_name!r} in {entry.definition} carries "
                        "an argument vector whose quoting does not round-trip: "
                        f"{list(tokens)} re-emits as {reemitted!r}, which "
                        f"tokenizes to {list(recovered)}"
                    ),
                    target=entry.definition,
                    location=entry.location,
                    details={
                        **base,
                        "tokens": list(tokens),
                        "reemitted": reemitted,
                        "recovered": list(recovered),
                    },
                )
            )

    return tuple(findings)


def installer_findings(
    tools: HookCommandTools,
    entry: HookCommand,
    *,
    probes: Sequence[InstallerProbe] = INSTALLER_PROBES,
) -> tuple[Finding, ...]:
    """Scan what the `Hook_Installer` would write from one shipped definition.

    The shipped asset is not runnable, so this is where R16 AC3 and AC4 are
    actually decided: each probe resolves the definition the way an install
    would, and the resolved string is put through the same scans plus one the
    shipped string cannot support — that tokenizing it recovers *exactly* the
    interpreter and script path that went in.
    """
    findings: list[Finding] = []
    for probe in probes:
        try:
            command, scripts = tools.resolve_command(
                entry.command,
                interpreter=probe.interpreter,
                scripts_directory=probe.scripts_directory,
            )
        except tools.installer_error as error:  # type: ignore[misc]
            findings.append(
                Finding(
                    code=_INSTALLER_CODE_MAP.get(
                        getattr(error, "code", ""), E_BARE_INTERPRETER
                    ),
                    message=(
                        f"the Hook_Installer cannot write hook {entry.hook_name!r} "
                        f"from {entry.definition} for the {probe.label} interpreter "
                        f"path: {getattr(error, 'message', error)}"
                    ),
                    target=entry.definition,
                    location=entry.location,
                    details={
                        **entry.details(),
                        "origin": ORIGIN_INSTALLED,
                        "probe": probe.label,
                        "installerCode": getattr(error, "code", None),
                    },
                )
            )
            continue
        except Exception as error:  # noqa: BLE001 - one probe, not the check
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=(
                        f"resolving hook {entry.hook_name!r} from "
                        f"{entry.definition} for the {probe.label} interpreter "
                        f"path raised {type(error).__name__}: {error}, so what "
                        "the Hook_Installer would write cannot be established"
                    ),
                    target=entry.definition,
                    location=entry.location,
                    details={
                        **entry.details(),
                        "origin": ORIGIN_INSTALLED,
                        "probe": probe.label,
                    },
                )
            )
            continue

        installed = HookCommand(
            definition=entry.definition,
            hook_name=entry.hook_name,
            index=entry.index,
            command=command,
            origin=ORIGIN_INSTALLED,
            probe=probe.label,
        )
        findings.extend(hook_command_findings(tools, installed))

        # The argument vector the install *intended*, assembled the way the
        # installer assembles it, so the two agree by construction and the only
        # thing under test is whether quoting survives the round trip.
        expected = (probe.interpreter,) + tuple(
            str(Path(probe.scripts_directory).joinpath(*relative.split("/")))
            for relative in scripts
        )
        recovered = tools.tokenize_command(command)
        if recovered != expected:
            findings.append(
                Finding(
                    code=E_BARE_INTERPRETER,
                    message=(
                        f"the command the Hook_Installer would write for hook "
                        f"{entry.hook_name!r} from {entry.definition} with the "
                        f"{probe.label} interpreter path does not tokenize back "
                        f"to [interpreter, script]: expected {list(expected)}, "
                        f"recovered {list(recovered)}"
                    ),
                    target=entry.definition,
                    location=entry.location,
                    details={
                        **installed.details(),
                        "expected": list(expected),
                        "recovered": list(recovered),
                    },
                )
            )
    return tuple(findings)


def hook_definition_glob(tree: PowerTree) -> str:
    """The glob selecting hook definitions, read from the shipped coverage map.

    Single-sourced from `hook-parity-coverage.json` so the validator and the
    installer cannot disagree about which files in the asset directory are
    hooks. A declared glob is honored only when it carries the
    `senzing-bootcamp-` prefix — the same condition the installer enforces,
    and what keeps the unprefixed coverage map from being read as a hook
    definition. Anything else falls back to the default, which is the value the
    map is expected to carry.
    """
    if not tree.exists(HOOK_COVERAGE_MAP):
        return DEFAULT_HOOK_DEFINITION_GLOB
    try:
        document = tree.read_json(HOOK_COVERAGE_MAP)
    except Unevaluable:
        return DEFAULT_HOOK_DEFINITION_GLOB
    declared = (
        document.get("hookDefinitionGlob") if isinstance(document, Mapping) else None
    )
    if isinstance(declared, str) and declared.strip().startswith(HOOK_FILENAME_PREFIX):
        return declared.strip()
    return DEFAULT_HOOK_DEFINITION_GLOB


def _is_hook_definition(tree: PowerTree, path: str) -> bool:
    try:
        document = tree.read_json(path)
    except Unevaluable:
        return False
    return isinstance(document, Mapping) and "hooks" in document


def hook_definition_paths(tree: PowerTree, pattern: str) -> tuple[str, ...]:
    """Every hook definition in the produced Power, sorted.

    The two declared directories are taken on their filename alone, so a
    definition that is malformed still gets scanned rather than skipped for
    being unreadable. A prefixed JSON file *outside* them is included only when
    it actually carries a `hooks` key: a hook definition that escaped its
    directory must still be checked, but an unrelated prefixed document must not
    be reported as a broken hook.
    """
    declared = [
        path
        for directory in (HOOK_ASSETS_DIRECTORY, TIER3_HOOKS_DIRECTORY)
        for path in tree.match(f"{directory}/{pattern}")
    ]
    elsewhere = [
        path
        for path in tree.match(f"**/{pattern}")
        if path not in declared and _is_hook_definition(tree, path)
    ]
    return tuple(sorted(set(declared + elsewhere)))


def hook_commands(
    document: Any, definition: str
) -> tuple[tuple[HookCommand, ...], tuple[Finding, ...]]:
    """Split one parsed definition into its command strings, plus what it lacks.

    A hook whose action is not a `command` action carries no Hook_Command_String
    and is skipped rather than faulted — Kiro's schema also allows an `agent`
    action, and R16 constrains command strings only. A hook that *declares* a
    command action without a command string is a different matter: there is
    something to scan and it is not there, which is recorded as an
    unevaluated-for-this-hook fault rather than silently passed over.
    """
    if not isinstance(document, Mapping):
        return (), (
            Finding(
                code=E_CHECK_UNEVALUATED,
                message=(
                    f"{definition} is not a JSON object, so its "
                    "Hook_Command_Strings cannot be read"
                ),
                target=definition,
            ),
        )
    hooks = document.get("hooks")
    if not isinstance(hooks, list):
        return (), (
            Finding(
                code=E_CHECK_UNEVALUATED,
                message=(
                    f"{definition} carries no 'hooks' list, so its "
                    "Hook_Command_Strings cannot be read"
                ),
                target=definition,
                location="hooks",
            ),
        )

    entries: list[HookCommand] = []
    findings: list[Finding] = []
    for index, hook in enumerate(hooks):
        if not isinstance(hook, Mapping):
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=f"{definition} hooks[{index}] is not a JSON object",
                    target=definition,
                    location=f"hooks[{index}]",
                )
            )
            continue
        name = hook.get("name")
        hook_name = (
            name if isinstance(name, str) and name.strip() else f"hooks[{index}]"
        )
        action = hook.get("action")
        if not isinstance(action, Mapping):
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=(
                        f"hook {hook_name!r} in {definition} declares no 'action' "
                        "object, so it carries no Hook_Command_String to check"
                    ),
                    target=definition,
                    location=f"hooks[{index}].action",
                )
            )
            continue
        if action.get("type") != "command":
            continue
        command = action.get("command")
        if not isinstance(command, str):
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=(
                        f"hook {hook_name!r} in {definition} declares a command "
                        "action whose 'command' is not a string, so no "
                        "Hook_Command_String can be scanned"
                    ),
                    target=definition,
                    location=f"hooks[{index}].action.command",
                )
            )
            continue
        entries.append(
            HookCommand(
                definition=definition,
                hook_name=hook_name,
                index=index,
                command=command,
            )
        )
    return tuple(entries), tuple(findings)


def _violation_record(finding: Finding) -> dict[str, Any]:
    """The compact per-violation row the report's `violations` array carries."""
    record: dict[str, Any] = {
        "definition": finding.target,
        "hook": finding.details.get("hook"),
        "origin": finding.details.get("origin", ORIGIN_SHIPPED),
        "code": finding.code,
    }
    for key in ("construct", "probe", "interpreter"):
        value = finding.details.get(key)
        if value is not None:
            record[key] = value
    return record


@register_check(
    "hook-command-strings",
    code=E_SHELL_CONSTRUCT_IN_HOOK,
    target=HOOK_DEFINITION_TARGET,
    requirement="10.5, 16.3, 16.4, 16.5, 16.6",
)
def check_hook_command_strings(context: ValidationContext) -> CheckResult:
    """Every Hook_Command_String is absolute, quoted, and shell-free.

    Scans the Tier 2 assets, the Tier 3 `dev.kiro/hooks/` copies, and — for the
    Tier 2 assets, which are the ones an install reads — every command string
    the `Hook_Installer` would write from them across the probe table.

    Fails closed in three ways: an unreadable installer, no hook definition at
    all, and an unreadable definition are each recorded rather than skipped. A
    Power with no hook definitions is not a Power whose command strings pass;
    it is a Power whose command strings were never established.
    """
    tree = context.tree
    tools = load_hook_command_tools(tree)
    pattern = hook_definition_glob(tree)
    definitions = hook_definition_paths(tree, pattern)
    if not definitions:
        raise Unevaluable(
            f"no hook definition matching {pattern!r} exists under "
            f"{HOOK_ASSETS_DIRECTORY}/ or {TIER3_HOOKS_DIRECTORY}/, so no "
            "Hook_Command_String could be checked",
            target=HOOK_DEFINITION_TARGET,
        )

    findings: list[Finding] = []
    entries: list[HookCommand] = []
    for path in definitions:
        try:
            document = tree.read_json(path)
        except Unevaluable as error:
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=(
                        f"{error.message}, so its Hook_Command_Strings cannot be "
                        "checked"
                    ),
                    target=path,
                )
            )
            continue
        found, shape = hook_commands(document, path)
        entries.extend(found)
        findings.extend(shape)

    tier2 = f"{HOOK_ASSETS_DIRECTORY}/"
    for entry in entries:
        findings.extend(hook_command_findings(tools, entry))
        if entry.definition.startswith(tier2):
            findings.extend(installer_findings(tools, entry))

    return CheckResult(
        id="hook-command-strings",
        target=HOOK_DEFINITION_TARGET,
        findings=tuple(findings),
        extra={
            "hookDefinitionGlob": pattern,
            "definitions": list(definitions),
            "commandStrings": len(entries),
            "installerProbes": len(INSTALLER_PROBES),
            "violations": [_violation_record(finding) for finding in findings],
        },
    )


# ---------------------------------------------------------------------------
# The `manifest-hashes` check (R16 AC8, AC9)
# ---------------------------------------------------------------------------
#
# The `Build_Manifest` records a SHA-256 of every file the engine wrote, hashed
# **as written**. This check re-hashes the tree in front of it and compares. It
# is not a second opinion on the transform — the engine already knows what it
# wrote — it is a check on what survived *checkout*, because git is the one
# participant in this pipeline that rewrites bytes on its own initiative.
#
# The failure it exists to catch has one usual cause, and the shape of that
# cause is why the diagnostic is worded the way it is. The engine writes LF
# unconditionally and the committed `.gitattributes` declares
# `* text=auto eol=lf`, so LF survives checkout on every Supported_Platform
# *(R16 AC8)*. Without that declaration a Windows checkout rewrites every text
# file to CRLF under `core.autocrlf`, changing its bytes and its hash — so the
# symptom is not one mismatched file but *every text file* mismatching at once.
# A Maintainer reading "content differs" file by file would go looking for a bad
# transform, so every mismatch message points at `.gitattributes`.
#
# The CRLF case is separated out rather than folded into a generic mismatch:
# when a file's bytes reproduce the recorded hash *after* line-ending
# normalization, the cause is established rather than guessed, and the finding
# says so outright. `.gitattributes` excludes `*.png` and `*.min.js` from
# normalization because R10 AC3 requires those byte-for-byte, so a mismatch on
# one of them can never be a line-ending rewrite and the message must not offer
# that explanation for it.
#
# Set drift is reported in **both** directions, because both are the same class
# of fault — the checkout and the manifest disagree about what the build
# produced — and neither can be established as harmless: a recorded file absent
# from the tree has no content to hash, and a file in the tree the manifest does
# not record has no recorded hash to be compared against. The one legitimate
# absence from the manifest is the manifest itself, which cannot record its own
# hash; it is excluded and nothing else is.
#
# `compare_manifest` is a pure function of a parsed manifest document and a
# path→bytes mapping, so a property test drives it with no filesystem at all.

#: The repository artifact every mismatch message points at *(R16 AC8)*, and the
#: declaration it must carry.
GITATTRIBUTES = ".gitattributes"
LINE_ENDING_DECLARATION = "* text=auto eol=lf"

#: The `.gitattributes` patterns held back from line-ending normalization
#: (`*.png binary`, `*.min.js -text`). Matched at any depth, the way a git
#: attribute pattern without a slash is. A mismatch on one of these is never a
#: line-ending rewrite: nothing was allowed to rewrite its line endings.
NORMALIZATION_EXEMPT_PATTERNS: tuple[str, ...] = ("*.png", "*.min.js")

#: Paths a produced Power carries that the `Build_Manifest` legitimately does
#: not record. Exactly one: the manifest cannot record its own hash.
MANIFEST_UNRECORDED: tuple[str, ...] = (BUILD_MANIFEST,)

#: `mismatches[].kind` — how a tree and a manifest disagreed. The catalog code
#: is the same for all of them, because the Maintainer response is the same;
#: the kind is what says where to look, so it travels as data.
DRIFT_CONTENT = "content"
DRIFT_LINE_ENDINGS = "line-endings"
DRIFT_ABSENT = "absent"
DRIFT_UNRECORDED = "unrecorded"
DRIFT_UNUSABLE_RECORD = "unusable-record"

MANIFEST_DRIFT_KINDS: tuple[str, ...] = (
    DRIFT_CONTENT,
    DRIFT_LINE_ENDINGS,
    DRIFT_ABSENT,
    DRIFT_UNRECORDED,
    DRIFT_UNUSABLE_RECORD,
)


def normalization_exempt(path: str) -> bool:
    """True when `.gitattributes` holds `path` back from line-ending rewriting.

    These are the paths R10 AC3 requires byte-for-byte identical to the template
    source — a vendored `d3.v7.min.js`, a logo `.png`. Nothing normalizes their
    line endings, on write or on checkout, so a line-ending explanation for a
    mismatch on one of them would be false.
    """
    return any(
        glob_matches(f"**/{pattern}", path)
        for pattern in NORMALIZATION_EXEMPT_PATTERNS
    )


def _digest(value: str) -> str:
    """One spelling of a hex digest, so case and padding are not a mismatch."""
    return value.strip().lower()


def is_line_ending_rewrite(data: bytes, recorded: str, path: str) -> bool:
    """True when `data` is the recorded content with its line endings rewritten.

    The test is constructive rather than heuristic: normalizing CRLF and lone CR
    back to LF — exactly what the engine did before hashing — has to reproduce
    the recorded hash. So this can only say "line endings" about a file where
    undoing the rewrite *demonstrably* recovers the recorded content.

    A file whose bytes carry no CR cannot have been rewritten, and a file
    `.gitattributes` exempts from normalization was never eligible for the
    rewrite; both answer False and land as content drift.
    """
    if normalization_exempt(path):
        return False
    normalized = normalize_lf(data)
    if normalized == data:
        return False
    return sha256_hex(normalized) == _digest(recorded)


@dataclass(frozen=True)
class ManifestRecord:
    """One `Build_Manifest` `files` row: a path and the hash of it as written.

    `rule_id` and `owner` are carried because they name *what produced* the
    file, which is the first thing a Maintainer wants after "which file" — a
    mismatch on a `kiro`-owned file is a different conversation from a mismatch
    on a rule's output.
    """

    path: str
    sha256: str
    rule_id: str = ""
    owner: str = OWNER_TEMPLATE
    source_path: str | None = None

    @property
    def digest(self) -> str:
        return _digest(self.sha256)

    def details(self) -> dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "owner": self.owner,
            "recordedSha256": self.digest,
        }


@dataclass(frozen=True)
class ManifestDocument:
    """A parsed `Build_Manifest`: the rows that can be compared, and the rest.

    A row that cannot state a path and a hash is not dropped and is not fatal to
    the whole check: it becomes a finding of its own and its path is remembered
    in `unusable`, so the file it names is neither compared against a hash that
    does not exist nor reported a second time as unrecorded. Every other row
    still gets compared, which is design principle 1 applied to the manifest
    itself — one run names all of the drift, not the first row of it.
    """

    records: tuple[ManifestRecord, ...] = ()
    unusable: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()
    template_release: str | None = None
    contract_version: int | None = None
    manifest_version: int = MANIFEST_VERSION

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(record.path for record in self.records)

    def __contains__(self, path: str) -> bool:
        return path in self.paths or path in self.unusable

    def record(self, path: str) -> ManifestRecord | None:
        for record in self.records:
            if record.path == path:
                return record
        return None

    @classmethod
    def from_json(
        cls, document: Any, *, manifest_path: str = BUILD_MANIFEST
    ) -> ManifestDocument:
        """Parse a `.build-manifest.json` document, failing closed on its shape.

        Three faults are whole-document and raise `Unevaluable`: a manifest that
        is not an object, one carrying a `manifestVersion` this check does not
        know how to read, and one with no `files` list. In each case there is no
        baseline at all, and a check with no baseline has established nothing —
        least of all a pass. A manifest recording *zero* files is the same
        situation wearing a valid shape, and is refused for the same reason: a
        produced Power has files, so an empty manifest means the comparison
        R16 AC9 asks for never happened.
        """
        if not isinstance(document, Mapping):
            raise Unevaluable(
                f"{manifest_path} is not a JSON object, so no recorded hash can "
                "be read from it",
                target=manifest_path,
            )

        declared_version = document.get("manifestVersion", MANIFEST_VERSION)
        if declared_version != MANIFEST_VERSION:
            raise Unevaluable(
                f"{manifest_path} declares manifestVersion {declared_version!r}; "
                f"this check reads manifestVersion {MANIFEST_VERSION}, so what "
                "its recorded hashes describe cannot be established",
                target=manifest_path,
            )

        raw_files = document.get("files")
        if not isinstance(raw_files, Sequence) or isinstance(raw_files, (str, bytes)):
            raise Unevaluable(
                f"{manifest_path} carries no 'files' list, so there is no "
                "recorded hash to compare the produced Power against",
                target=manifest_path,
            )

        records: list[ManifestRecord] = []
        unusable: list[str] = []
        findings: list[Finding] = []
        seen: dict[str, ManifestRecord] = {}

        for index, raw in enumerate(raw_files):
            location = f"files[{index}]"
            if not isinstance(raw, Mapping):
                findings.append(
                    _unusable_record_finding(
                        f"{manifest_path} {location} is not a JSON object, so the "
                        "file it records and the hash recorded for it cannot be "
                        "read",
                        target=manifest_path,
                        location=location,
                    )
                )
                continue

            path = raw.get("path")
            if not isinstance(path, str) or not path.strip():
                findings.append(
                    _unusable_record_finding(
                        f"{manifest_path} {location} records no 'path', so the "
                        "hash it carries cannot be attributed to a file",
                        target=manifest_path,
                        location=location,
                    )
                )
                continue
            path = path.strip()

            digest = raw.get("sha256")
            if not isinstance(digest, str) or not digest.strip():
                unusable.append(path)
                findings.append(
                    _unusable_record_finding(
                        f"{manifest_path} records no 'sha256' for {path!r}, so "
                        "that file's content cannot be compared against what the "
                        "build wrote",
                        target=path,
                        location=f"{location}.sha256",
                    )
                )
                continue

            rule_id = raw.get("ruleId")
            owner = raw.get("owner")
            source_path = raw.get("sourcePath")
            record = ManifestRecord(
                path=path,
                sha256=digest,
                rule_id=rule_id if isinstance(rule_id, str) else "",
                owner=owner if isinstance(owner, str) else OWNER_TEMPLATE,
                source_path=source_path if isinstance(source_path, str) else None,
            )

            previous = seen.get(path)
            if previous is not None:
                # Two rows for one path: whichever hash is compared, the other
                # is not, so the baseline for that file is ambiguous rather than
                # merely redundant. An identical repeat is still a manifest
                # defect, but it does not make the comparison ambiguous.
                if previous.digest != record.digest:
                    unusable.append(path)
                    findings.append(
                        _unusable_record_finding(
                            f"{manifest_path} records {path!r} twice with "
                            f"different hashes ({previous.digest} and "
                            f"{record.digest}), so which one the checkout is "
                            "supposed to match is undefined",
                            target=path,
                            location=location,
                        )
                    )
                continue

            seen[path] = record
            records.append(record)

        if not records and not unusable:
            raise Unevaluable(
                f"{manifest_path} records no file, so no content hash could be "
                "compared; a produced Power records every file it writes",
                target=manifest_path,
            )

        # A path whose row was unusable is not comparable, so it must not also
        # be reported as unrecorded when the tree is scanned.
        for path in unusable:
            records = [record for record in records if record.path != path]

        release = document.get("templateRelease")
        contract_version = document.get("contractVersion")
        return cls(
            records=tuple(records),
            unusable=tuple(sorted(set(unusable))),
            findings=tuple(findings),
            template_release=release if isinstance(release, str) else None,
            contract_version=(
                contract_version if isinstance(contract_version, int) else None
            ),
            manifest_version=MANIFEST_VERSION,
        )


def _unusable_record_finding(
    message: str, *, target: str, location: str
) -> Finding:
    """A manifest row that cannot supply a baseline. Not a pass, not a mismatch.

    `E_CHECK_UNEVALUATED` rather than `E_HASH_MISMATCH`, because nothing was
    compared: claiming a mismatch would assert a difference this check never
    measured. Error severity either way, so it blocks tagging.
    """
    return Finding(
        code=E_CHECK_UNEVALUATED,
        message=message,
        target=target,
        location=location,
        details={"kind": DRIFT_UNUSABLE_RECORD},
    )


def _line_ending_finding(record: ManifestRecord, actual: str) -> Finding:
    return Finding(
        code=E_HASH_MISMATCH,
        message=(
            f"{record.path} hashes to {actual} but the Build_Manifest records "
            f"{record.digest}; normalizing this file's line endings back to LF "
            f"reproduces the recorded hash, so its line endings were rewritten "
            f"after the build wrote them. That is a checkout "
            f"rewriting text: confirm {GITATTRIBUTES} declares "
            f"{LINE_ENDING_DECLARATION!r} and that it is in effect for this "
            "path, then check the file out again"
        ),
        target=record.path,
        details={
            **record.details(),
            "actualSha256": actual,
            "kind": DRIFT_LINE_ENDINGS,
        },
    )


def _content_finding(record: ManifestRecord, actual: str) -> Finding:
    if normalization_exempt(record.path):
        cause = (
            f"{GITATTRIBUTES} holds this path back from line-ending "
            f"normalization ({', '.join(NORMALIZATION_EXEMPT_PATTERNS)}), so "
            "this is not a rewritten line ending: the bytes themselves differ, "
            "and R10 AC3 requires them byte-for-byte identical to the template "
            "source"
        )
    else:
        cause = (
            "the usual cause of a hash mismatch is line-ending rewriting on "
            f"checkout, so confirm {GITATTRIBUTES} declares "
            f"{LINE_ENDING_DECLARATION!r} and is in effect here; normalizing "
            "this file's line endings does not reproduce the recorded hash, "
            "though, so its content differs beyond line endings"
        )
    return Finding(
        code=E_HASH_MISMATCH,
        message=(
            f"{record.path} hashes to {actual} but the Build_Manifest records "
            f"{record.digest}; {cause}"
        ),
        target=record.path,
        details={
            **record.details(),
            "actualSha256": actual,
            "kind": DRIFT_CONTENT,
        },
    )


def _absent_finding(record: ManifestRecord) -> Finding:
    return Finding(
        code=E_HASH_MISMATCH,
        message=(
            f"{record.path} is recorded in the Build_Manifest with hash "
            f"{record.digest} but is absent from the produced Power, so there is "
            "no content to hash and the comparison cannot come out equal; a file "
            "the build wrote and the checkout does not carry is drift between "
            f"the two, and a checkout that drops files is the same class of "
            f"fault as one that rewrites them (see {GITATTRIBUTES})"
        ),
        target=record.path,
        details={
            **record.details(),
            "actualSha256": None,
            "kind": DRIFT_ABSENT,
        },
    )


def _unrecorded_finding(path: str, actual: str) -> Finding:
    return Finding(
        code=E_HASH_MISMATCH,
        message=(
            f"{path} is present in the produced Power, hashing to {actual}, but "
            "the Build_Manifest records no hash for it, so its content cannot be "
            "compared against what the build wrote; the manifest records every "
            f"file a build writes except itself ({BUILD_MANIFEST}), so an "
            "unrecorded file is drift between the checkout and the manifest"
        ),
        target=path,
        details={
            "ruleId": None,
            "owner": None,
            "recordedSha256": None,
            "actualSha256": actual,
            "kind": DRIFT_UNRECORDED,
        },
    )


@dataclass(frozen=True)
class ManifestComparison:
    """What comparing one manifest against one file mapping established.

    `compared` and `matched` are carried, not just the failures: a report that
    says only "no mismatches" does not say how many files were actually hashed,
    and the difference between "42 files matched" and "nothing was compared"
    is the difference between a verdict and an omission.
    """

    manifest: ManifestDocument
    compared: tuple[str, ...] = ()
    matched: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()

    @property
    def drifted(self) -> tuple[str, ...]:
        """Every path a finding names, first occurrence order."""
        seen: dict[str, None] = {}
        for finding in self.findings:
            if finding.target is not None:
                seen.setdefault(finding.target, None)
        return tuple(seen)


def compare_manifest(
    document: Any,
    files: Mapping[str, bytes],
    *,
    manifest_path: str = BUILD_MANIFEST,
    unrecorded_allowed: Sequence[str] = MANIFEST_UNRECORDED,
) -> ManifestComparison:
    """Compare a `Build_Manifest` document against a path→bytes mapping.

    Pure: a parsed document and a mapping in, a comparison out, no filesystem
    and no clock. Every recorded file is examined and every unrecorded file is
    reported, in one pass — the manifest order first, then the tree's sorted
    remainder, so the finding order is a function of the inputs alone.
    """
    manifest = ManifestDocument.from_json(document, manifest_path=manifest_path)
    findings: list[Finding] = list(manifest.findings)
    compared: list[str] = []
    matched: list[str] = []

    for record in manifest.records:
        data = files.get(record.path)
        if data is None:
            findings.append(_absent_finding(record))
            continue
        compared.append(record.path)
        actual = sha256_hex(data)
        if actual == record.digest:
            matched.append(record.path)
        elif is_line_ending_rewrite(data, record.digest, record.path):
            findings.append(_line_ending_finding(record, actual))
        else:
            findings.append(_content_finding(record, actual))

    allowed = set(unrecorded_allowed)
    for path in sorted(files):
        if path in manifest or path in allowed:
            continue
        findings.append(_unrecorded_finding(path, sha256_hex(files[path])))

    return ManifestComparison(
        manifest=manifest,
        compared=tuple(compared),
        matched=tuple(matched),
        findings=tuple(findings),
    )


def _mismatch_record(finding: Finding) -> dict[str, Any]:
    """The compact per-mismatch row the report's `mismatches` array carries."""
    return {
        "path": finding.target,
        "kind": finding.details.get("kind", DRIFT_CONTENT),
        "code": finding.code,
        "recordedSha256": finding.details.get("recordedSha256"),
        "actualSha256": finding.details.get("actualSha256"),
    }


@register_check(
    "manifest-hashes",
    code=E_HASH_MISMATCH,
    requirement="16.8, 16.9",
)
def check_manifest_hashes(context: ValidationContext) -> CheckResult:
    """Every file's content hash equals the hash recorded for it *(R16 AC9)*.

    Reads the `Build_Manifest` out of the tree under validation and compares it
    against that same tree. An absent or unparseable manifest raises
    `Unevaluable` through `read_json`, so a Power carrying no baseline fails
    closed rather than passing for want of anything to compare against.
    """
    tree = context.tree
    comparison = compare_manifest(tree.read_json(BUILD_MANIFEST), tree.files)
    manifest = comparison.manifest
    return CheckResult(
        id="manifest-hashes",
        findings=comparison.findings,
        extra={
            "manifest": BUILD_MANIFEST,
            "templateRelease": manifest.template_release,
            "recorded": len(manifest.records),
            "compared": len(comparison.compared),
            "matched": len(comparison.matched),
            "treeFiles": len(tree),
            "mismatches": [
                _mismatch_record(finding) for finding in comparison.findings
            ],
        },
    )


# ---------------------------------------------------------------------------
# The `skill-inventory` and `progression-order` checks (R7 AC1-AC3, R9 AC1)
# ---------------------------------------------------------------------------
#
# **No inventory count appears anywhere in this section**, and that omission is
# the substance of it. The design's defect D1 records why: the original R7 AC1
# fixed the inventory at a number, the number disagreed with the release it was
# counting, and a gate checking a number would have been testing the wrong thing
# on the next release as well. What R7 AC1 and AC2 ask for instead is a
# **bijection** — one ported skill per template skill directory, and no ported
# skill without one — so both inventories are *derived*, one from the resolved
# release and one from the produced Power, and the check is that they correspond.
# A release that adds `module-08-…` needs no edit here; a release that drops a
# skill, or a build that silently loses one, fails by name.
#
# Both checks therefore measure the Power against the release it was built from,
# and neither can reach a verdict without it: `require_source` raises
# `Unevaluable`, which the runner records as a fail, so a run launched without
# `--source` **blocks the tag** rather than passing two checks it never
# performed. `require_contract` does the same for the `kiro-owned` declarations
# and the declared progression.
#
# What stands for what is read from the artifacts, not guessed from paths
# ------------------------------------------------------------------------
# Each produced skill *declares* its counterpart in its own frontmatter:
#
# * a **ported** skill carries `metadata.templateSkill`, written by the engine's
#   frontmatter adaptation and naming the source skill directory it came from —
#   which is why the field name is imported from the engine rather than respelled
#   here: the writer and the gate must rename together or not at all;
# * a **command-derived** skill carries `metadata.templateCommand`, naming the
#   template command it replaces. This one cannot be a name comparison: the
#   template command `graduate` becomes the skill `graduate-bootcamp` *(R9 AC1)*,
#   so the correspondence is a declaration, and one-to-one is a property of it;
# * every **remaining** skill must be declared `kiro-owned` by the contract. That
#   residue rule is R7 AC2's exclusivity clause as defects D1 and D5 resolved it:
#   the three command-derived skills answer to R9 and the enforcement-setup skill
#   to the hook-parity criteria, and both groups are compliant *because* the
#   contract says they exist only in the Power, not because the check overlooks
#   them.
#
# A ported skill's declaration is checked against its path as well as against the
# release, because R8 AC1 fixes the destination to the source directory name
# byte-identically: a skill sitting at `skills/module-3/` while declaring
# `module-03` names a template directory that exists, at a path the corpus's
# relative cross-references do not spell.
#
# Progression is an order over names, declared in the contract
# ------------------------------------------------------------
# R7 AC3 asks that the Power present its skills in the template's progression
# order, onboarding through graduation. The order itself is declared once, in the
# contract's `progression` section, as phases matched against skill directory
# *names* — so the same declaration derives both sequences, the template's from
# the release's skill directories and the Power's from the ported skills, and
# they are compared element-for-element. Two things in that arrangement carry
# weight rather than restating the sort:
#
# * a name **no phase claims** is a finding on either side, so an upstream skill
#   of a shape the declared progression does not describe stops the build with
#   its name rather than landing silently at one end of the sequence;
# * the declared phases must **begin at onboarding and end at graduation**, which
#   is R7 AC3's own wording read literally — a contract that declared graduation
#   in the middle is a contract defect this gate names.
#
# Within the module phase the order is by the module's leading number and then by
# its interstitial suffix, which is what puts `module-03b-truthset-visualization`
# between `module-03-…` and `module-04-…` instead of wherever a lexicographic
# sort would land it. `interstitial_findings` states that placement as a claim
# over a *given* sequence, so *Property 17* can drive it with a deliberately
# misordered one; over a sequence derived here it is a self-check of
# `progression_key`.
#
# What these checks do **not** establish: that a Bootcamper actually moves
# through the skills in this order in a live session. Kiro's activation is not
# mechanically observable from a tree, which is why Test_Checklist step 8 exists.
# What is checked here is the inventory and the order the Power *declares*.

#: The directory produced and template skills both live under.
SKILLS_DIRECTORY = "skills"

#: `CheckResult.target` for both checks: the skill directories, which are the unit
#: of record here — one bijection over the set, not one result per skill.
SKILL_INVENTORY_TARGET = "skills/*"

#: Where a produced skill records the *command* it replaces. Authored in the
#: `kiro-owned` command skill templates rather than written by the engine, hence
#: named here beside the engine's `templateSkill` rather than imported with it.
TEMPLATE_COMMAND_FIELD = "templateCommand"

#: The template commands, as a glob over the resolved release. The same set the
#: contract's `commands-superseded` rule matches and deliberately does not port:
#: Kiro has no plugin-level slash commands, so each command becomes a skill
#: instead (R9 AC1).
COMMAND_SOURCE_GLOB = "commands/*.md"
COMMAND_SUFFIX = ".md"

#: `mismatches[].kind` for the inventory check — the vocabulary a report consumer
#: reads a correspondence failure by, stated once as data.
INVENTORY_MISSING = "template-skill-unported"
INVENTORY_DUPLICATE = "template-skill-ported-twice"
INVENTORY_STALE = "declares-absent-template-skill"
INVENTORY_RELOCATED = "declaration-differs-from-directory"
INVENTORY_UNACCOUNTED = "skill-without-counterpart-or-declaration"
INVENTORY_COMMAND_MISSING = "template-command-unrepresented"
INVENTORY_COMMAND_DUPLICATE = "template-command-claimed-twice"
INVENTORY_COMMAND_STALE = "declares-absent-template-command"
INVENTORY_DOUBLE_CLAIM = "claims-both-a-skill-and-a-command"

INVENTORY_KINDS: tuple[str, ...] = (
    INVENTORY_MISSING,
    INVENTORY_DUPLICATE,
    INVENTORY_STALE,
    INVENTORY_RELOCATED,
    INVENTORY_UNACCOUNTED,
    INVENTORY_COMMAND_MISSING,
    INVENTORY_COMMAND_DUPLICATE,
    INVENTORY_COMMAND_STALE,
    INVENTORY_DOUBLE_CLAIM,
)

#: The contract section declaring the progression phases, and the two phase ids
#: R7 AC3 names as its endpoints.
PROGRESSION_SECTION = "progression"
PROGRESSION_FIRST_PHASE = "onboarding"
PROGRESSION_LAST_PHASE = "graduation"

#: `mismatches[].kind` for the progression check.
PROGRESSION_PHASES_MISDECLARED = "phases-misdeclared"
PROGRESSION_UNPLACEABLE = "skill-no-phase-claims"
PROGRESSION_SEQUENCE_DIFFERS = "sequence-differs"
PROGRESSION_INTERSTITIAL_MISPLACED = "interstitial-misplaced"

PROGRESSION_KINDS: tuple[str, ...] = (
    PROGRESSION_PHASES_MISDECLARED,
    PROGRESSION_UNPLACEABLE,
    PROGRESSION_SEQUENCE_DIFFERS,
    PROGRESSION_INTERSTITIAL_MISPLACED,
)

#: A numbered bootcamp module directory name: `module-03-sdk-setup`,
#: `module-03b-truthset-visualization`, `module-7`. The number and the
#: interstitial suffix are what order the module phase; the topic is free text and
#: takes no part in it.
MODULE_NAME = re.compile(
    r"^module-(?P<number>[0-9]+)(?P<interstitial>[a-z]*)(?:-(?P<topic>.*))?$"
)


def source_prefix(source: PowerTree, plugin_root: str) -> str:
    """The path prefix release-relative paths carry in `source`, `""` or `"<root>/"`.

    The template is a marketplace repository, so a resolved release tree normally
    holds the plugin under `plugins/senzing-bootcamp/`. `--source` may be given as
    either that repository root or the plugin root itself, and the engine already
    accepts both (`resolve_plugin_root`); this is the same rule over a path-keyed
    tree, so the validator reads the release from whichever of the two it was
    handed rather than reporting an empty template inventory for the other.
    """
    root = (plugin_root or "").strip("/")
    if root and any(path.startswith(f"{root}/") for path in source.paths):
        return f"{root}/"
    return ""


def skill_names(tree: PowerTree, *, prefix: str = "") -> tuple[str, ...]:
    """The skill directory names directly under `<prefix>skills/`, sorted.

    A *directory* is the unit R7 AC1 counts, so membership here is "something in
    the tree sits under it" rather than "it carries a `SKILL.md`". Measuring by
    entry point instead would leave a skill directory ported without one invisible
    to the bijection *and* to the frontmatter check, which records a result per
    `SKILL.md` and so cannot record one for an absent file.

    A file sitting directly under `skills/` names no skill and is skipped.
    """
    base = f"{prefix}{SKILLS_DIRECTORY}/"
    names = {
        remainder.split("/", 1)[0]
        for path in tree.paths
        if path.startswith(base)
        for remainder in (path[len(base) :],)
        if "/" in remainder and remainder.split("/", 1)[0]
    }
    return tuple(sorted(names))


def command_names(source: PowerTree, *, prefix: str = "") -> tuple[str, ...]:
    """The template command names in a resolved release, sorted.

    The stem of each `<prefix>commands/*.md`: `commands/graduate.md` declares the
    command `graduate`. Direct children only — the contract's glob semantics keep
    `*` from crossing `/` — because a command is one document, not a directory.
    """
    return tuple(
        sorted(
            path.rsplit("/", 1)[-1][: -len(COMMAND_SUFFIX)]
            for path in source.match(f"{prefix}{COMMAND_SOURCE_GLOB}")
        )
    )


def kiro_owned_skill_names(contract: Contract) -> tuple[str, ...]:
    """Skill names the contract declares as content with no template source.

    Read from the `kiro-owned` rules' destinations, so adding a Kiro-only skill is
    a contract edit and nothing more (R3 AC4). A destination that lands *inside* a
    skill directory (`skills/bootcamp-onboarding/scripts/optional_runtime.py`)
    names that skill too; it is a declaration about a file rather than about the
    whole skill, and it is deliberately not read as one — the skill it sits in is
    accounted for by the template bijection, and this set is only ever consulted
    for names the bijection did *not* account for.
    """
    base = f"{SKILLS_DIRECTORY}/"
    names: set[str] = set()
    for rule in contract.kiro_owned_rules:
        for destination in rule.dest:
            if not destination.startswith(base):
                continue
            remainder = destination[len(base) :].strip("/")
            if remainder:
                names.add(remainder.split("/", 1)[0])
    return tuple(sorted(names))


@dataclass(frozen=True)
class SkillProvenance:
    """One produced skill and the counterpart its frontmatter declares.

    `template_skill` and `template_command` are the declarations as read: a
    non-blank string or `None`. Nothing is inferred from the directory name here —
    the inference that *is* made (an unreadable declaration at a path the release
    also carries stands for that release skill) is made in `port_claims`, where it
    can be stated and reasoned about, rather than buried in a read.
    """

    name: str
    path: str
    template_skill: str | None = None
    template_command: str | None = None
    readable: bool = True

    @property
    def declares_counterpart(self) -> bool:
        return self.template_skill is not None or self.template_command is not None


def _declared_metadata(fields: Mapping[str, Any] | None, key: str) -> str | None:
    """One non-blank string from a skill's frontmatter `metadata`, or `None`."""
    metadata = (fields or {}).get(SKILL_METADATA_FIELD)
    if not isinstance(metadata, Mapping):
        return None
    value = metadata.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def skill_provenance(tree: PowerTree, name: str) -> SkillProvenance:
    """Read one produced skill's declared counterpart, never raising.

    Frontmatter reading is `SkillFrontmatter.read`, which turns every fault into a
    finding against the file rather than an exception, so one unreadable
    `SKILL.md` cannot abort a whole-inventory check. Its findings are *not*
    collected here: an unreadable entry point is `E_FRONTMATTER_INVALID` against
    that file, reported once by the check that owns it, and repeating it under an
    inventory code would report one defect as two.
    """
    path = f"{SKILLS_DIRECTORY}/{name}/{SKILL_MANIFEST}"
    frontmatter = SkillFrontmatter.read(tree, path)
    return SkillProvenance(
        name=name,
        path=path,
        template_skill=_declared_metadata(
            frontmatter.fields, SKILL_TEMPLATE_SKILL_FIELD
        ),
        template_command=_declared_metadata(frontmatter.fields, TEMPLATE_COMMAND_FIELD),
        readable=frontmatter.readable,
    )


def skill_inventory(tree: PowerTree) -> tuple[SkillProvenance, ...]:
    """Every produced skill with its declared counterpart, in name order."""
    return tuple(skill_provenance(tree, name) for name in skill_names(tree))


def port_claims(
    inventory: Sequence[SkillProvenance], template_skills: Sequence[str]
) -> Mapping[str, str]:
    """Produced skill name → the template skill it stands for, for those that do.

    Two ways a produced skill claims a template skill, and the second exists for a
    specific reason:

    1. it **declares** one in `metadata.templateSkill`;
    2. it declares nothing and its **directory name is in the release**, which is
       the path R8 AC1 fixes.

    Reading (2) as a claim keeps a `SKILL.md` whose frontmatter cannot be read
    from being reported twice — once as an unported template skill and once as a
    skill with no counterpart — for what is one already-reported frontmatter
    fault. The claim is still checkable: it is measured against the release like
    any other.
    """
    release = set(template_skills)
    claims: dict[str, str] = {}
    for skill in inventory:
        if skill.template_skill is not None:
            claims[skill.name] = skill.template_skill
        elif skill.template_command is None and skill.name in release:
            claims[skill.name] = skill.name
    return claims


def ported_skill_names(
    inventory: Sequence[SkillProvenance], template_skills: Sequence[str]
) -> tuple[str, ...]:
    """The produced skills that stand for a template skill directory, sorted.

    This is the ported bootcamp inventory the progression sequence is ordered
    over: command-derived and `kiro-owned` skills are not part of the bootcamp
    progression and are not in it.
    """
    return tuple(sorted(port_claims(inventory, template_skills)))


def command_claims(inventory: Sequence[SkillProvenance]) -> Mapping[str, str]:
    """Produced skill name → the template command it declares, for those that do."""
    return {
        skill.name: skill.template_command
        for skill in inventory
        if skill.template_command is not None
    }


def _inventory_finding(
    message: str, *, kind: str, target: str, **details: Any
) -> Finding:
    """One correspondence failure, named by kind and by the thing at fault."""
    return Finding(
        code=E_INVENTORY_MISMATCH,
        message=message,
        target=target,
        details={"kind": kind, **details},
    )


def _skill_target(name: str) -> str:
    """The Power path a skill occupies, as a finding names it."""
    return f"{SKILLS_DIRECTORY}/{name}/"


def _inverse(claims: Mapping[str, str]) -> Mapping[str, tuple[str, ...]]:
    """Claimed counterpart → the claiming skills, sorted."""
    inverse: dict[str, list[str]] = {}
    for skill, claimed in claims.items():
        inverse.setdefault(claimed, []).append(skill)
    return {claimed: tuple(sorted(names)) for claimed, names in inverse.items()}


def skill_bijection_findings(
    inventory: Sequence[SkillProvenance],
    template_skills: Sequence[str],
    kiro_owned: Sequence[str],
) -> tuple[Finding, ...]:
    """Every way the skill inventory fails to be a bijection *(R7 AC1, AC2)*.

    Pure over three name collections and the declarations read off the produced
    skills, so *Property 16* drives it without a filesystem. Every condition is
    evaluated whatever an earlier one reported (design principle 1): a build that
    lost one skill and gained two undeclared ones reports all three.
    """
    claims = port_claims(inventory, template_skills)
    claimants = _inverse(claims)
    commands = command_claims(inventory)
    release = set(template_skills)
    declared_kiro_owned = set(kiro_owned)
    findings: list[Finding] = []

    # R7 AC1 — one ported skill for each template skill directory. Neither
    # direction of the failure is the other: nothing ported it, or two things did.
    for name in template_skills:
        standing = claimants.get(name, ())
        if not standing:
            findings.append(
                _inventory_finding(
                    f"the resolved Template_Release carries the bootcamp skill "
                    f"directory {SKILLS_DIRECTORY}/{name}/, and no skill in the "
                    "Power stands for it: no produced skill declares "
                    f"{SKILL_METADATA_FIELD}.{SKILL_TEMPLATE_SKILL_FIELD} "
                    f"{name!r} and none sits at {_skill_target(name)}",
                    kind=INVENTORY_MISSING,
                    target=_skill_target(name),
                    templateSkill=name,
                )
            )
        elif len(standing) > 1:
            findings.append(
                _inventory_finding(
                    f"{len(standing)} skills in the Power stand for the one "
                    f"template skill directory {SKILLS_DIRECTORY}/{name}/ "
                    f"({', '.join(standing)}); R7 AC1 provides exactly one",
                    kind=INVENTORY_DUPLICATE,
                    target=_skill_target(name),
                    templateSkill=name,
                    claimedBy=list(standing),
                )
            )

    for skill in inventory:
        claimed = claims.get(skill.name)

        # A skill cannot be both a port of a template skill and the stand-in for a
        # template command: the two groups are disjoint in R7 AC2 as D5 resolved
        # it, and a skill claiming both leaves neither correspondence one-to-one.
        if skill.template_skill is not None and skill.template_command is not None:
            findings.append(
                _inventory_finding(
                    f"{skill.path} declares both "
                    f"{SKILL_METADATA_FIELD}.{SKILL_TEMPLATE_SKILL_FIELD} "
                    f"{skill.template_skill!r} and "
                    f"{SKILL_METADATA_FIELD}.{TEMPLATE_COMMAND_FIELD} "
                    f"{skill.template_command!r}; a skill stands for a template "
                    "skill directory or for a template command, not for both",
                    kind=INVENTORY_DOUBLE_CLAIM,
                    target=skill.path,
                    templateSkill=skill.template_skill,
                    templateCommand=skill.template_command,
                )
            )

        # A declaration naming something the release does not carry. This is how an
        # upstream rename surfaces: the Power still declares the old name, and the
        # gate says so instead of shipping a skill that stands for nothing.
        if claimed is not None and claimed not in release:
            findings.append(
                _inventory_finding(
                    f"{skill.path} declares "
                    f"{SKILL_METADATA_FIELD}.{SKILL_TEMPLATE_SKILL_FIELD} "
                    f"{claimed!r}, and the resolved Template_Release carries no "
                    f"skill directory {SKILLS_DIRECTORY}/{claimed}/",
                    kind=INVENTORY_STALE,
                    target=skill.path,
                    declared=claimed,
                )
            )

        # R8 AC1 — the destination preserves the source directory name
        # byte-identically, so a declared counterpart that is not this directory
        # names a skill the corpus's relative cross-references do not spell.
        if skill.template_skill is not None and skill.template_skill != skill.name:
            findings.append(
                _inventory_finding(
                    f"{skill.path} sits in {_skill_target(skill.name)} and declares "
                    f"{SKILL_METADATA_FIELD}.{SKILL_TEMPLATE_SKILL_FIELD} "
                    f"{skill.template_skill!r}; a ported skill keeps its source "
                    "directory name byte-identically, so the two must be the same "
                    "string",
                    kind=INVENTORY_RELOCATED,
                    target=skill.path,
                    directory=skill.name,
                    declared=skill.template_skill,
                )
            )

        # R7 AC2 — the residue rule. A skill with no template counterpart is
        # compliant exactly when the contract says it exists only in the Power.
        if (
            claimed is None
            and skill.name not in commands
            and skill.name not in declared_kiro_owned
        ):
            findings.append(
                _inventory_finding(
                    f"the Power carries the skill {_skill_target(skill.name)}, which "
                    "stands for no template skill directory and no template "
                    f"command, and no contract rule declares it '{OWNER_KIRO}'-owned "
                    "content; every skill is a port, a command stand-in, or an "
                    "explicit Kiro-only declaration",
                    kind=INVENTORY_UNACCOUNTED,
                    target=_skill_target(skill.name),
                    skill=skill.name,
                )
            )

    return tuple(findings)


def command_bijection_findings(
    inventory: Sequence[SkillProvenance], template_commands: Sequence[str]
) -> tuple[Finding, ...]:
    """The command correspondence is one-to-one *(R9 AC1)*.

    A correspondence rather than a name comparison, because the names differ by
    design: the template command `graduate` is represented by the skill
    `graduate-bootcamp`. Both directions are checked — every template command
    represented exactly once, and every declaration naming a command the release
    carries — so neither an upstream command that gained no skill nor a skill
    standing for a command that no longer exists can pass.
    """
    claims = command_claims(inventory)
    claimants = _inverse(claims)
    declared = set(template_commands)
    findings: list[Finding] = []

    for command in template_commands:
        standing = claimants.get(command, ())
        if not standing:
            findings.append(
                _inventory_finding(
                    f"the resolved Template_Release declares the command "
                    f"{command!r} and no skill in the Power represents it; Kiro has "
                    "no plugin-level slash commands, so each template command is "
                    "represented by exactly one skill declaring "
                    f"{SKILL_METADATA_FIELD}.{TEMPLATE_COMMAND_FIELD} {command!r}",
                    kind=INVENTORY_COMMAND_MISSING,
                    target=f"{COMMAND_SOURCE_GLOB.rsplit('/', 1)[0]}/{command}"
                    f"{COMMAND_SUFFIX}",
                    templateCommand=command,
                )
            )
        elif len(standing) > 1:
            findings.append(
                _inventory_finding(
                    f"{len(standing)} skills in the Power represent the one template "
                    f"command {command!r} ({', '.join(standing)}); the "
                    "correspondence is one-to-one",
                    kind=INVENTORY_COMMAND_DUPLICATE,
                    target=_skill_target(standing[0]),
                    templateCommand=command,
                    claimedBy=list(standing),
                )
            )

    for name, command in sorted(claims.items()):
        if command not in declared:
            findings.append(
                _inventory_finding(
                    f"{_skill_target(name)}{SKILL_MANIFEST} declares "
                    f"{SKILL_METADATA_FIELD}.{TEMPLATE_COMMAND_FIELD} {command!r}, "
                    "and the resolved Template_Release declares no such command",
                    kind=INVENTORY_COMMAND_STALE,
                    target=f"{_skill_target(name)}{SKILL_MANIFEST}",
                    declared=command,
                )
            )

    return tuple(findings)


def _correspondence_record(finding: Finding) -> dict[str, Any]:
    """The compact per-failure row the inventory check's `mismatches` array carries."""
    return {
        "kind": finding.details.get("kind"),
        "target": finding.target,
        **{
            key: value
            for key, value in finding.details.items()
            if key != "kind"
        },
    }


def skill_inventory_result(
    inventory: Sequence[SkillProvenance],
    template_skills: Sequence[str],
    template_commands: Sequence[str],
    kiro_owned: Sequence[str],
) -> CheckResult:
    """The recorded result for one produced inventory against one release.

    Pure — name collections and read declarations in, a `CheckResult` out — and
    the whole of the check; `check_skill_inventory` adds only the reads.
    *Property 16* drives this directly.
    """
    findings = skill_bijection_findings(
        inventory, template_skills, kiro_owned
    ) + command_bijection_findings(inventory, template_commands)
    claims = port_claims(inventory, template_skills)
    commands = command_claims(inventory)
    return CheckResult(
        id="skill-inventory",
        findings=findings,
        extra={
            "templateSkills": list(template_skills),
            "portedSkills": sorted(claims),
            "templateCommands": list(template_commands),
            "commandDerivedSkills": {name: commands[name] for name in sorted(commands)},
            "kiroOwnedSkills": list(kiro_owned),
            "powerSkills": [skill.name for skill in inventory],
            "mismatches": [_correspondence_record(finding) for finding in findings],
        },
    )


@register_check(
    "skill-inventory",
    code=E_INVENTORY_MISMATCH,
    target=SKILL_INVENTORY_TARGET,
    requirement="7.1, 7.2, 9.1",
)
def check_skill_inventory(context: ValidationContext) -> CheckResult:
    """The skill and command inventories correspond to the release *(R7, R9 AC1)*.

    Fails closed on three conditions before any comparison is made: no resolved
    release tree (`require_source`), no contract to read the `kiro-owned`
    declarations from (`require_contract`), and a release tree carrying no
    `skills/` directory at all. The third matters as much as the first two — an
    empty template inventory would make every produced skill unaccounted for and,
    worse, would let a Power with no skills pass a bijection against nothing.
    """
    source = context.require_source()
    contract = context.require_contract()
    prefix = source_prefix(source, contract.plugin_root)
    template_skills = skill_names(source, prefix=prefix)
    if not template_skills:
        raise Unevaluable(
            "the resolved Template_Release tree carries no "
            f"{prefix}{SKILLS_DIRECTORY}/ directory, so the ported skill inventory "
            "has nothing to be a bijection with; check that --source names the "
            "extracted release"
        )
    return skill_inventory_result(
        skill_inventory(context.tree),
        template_skills,
        command_names(source, prefix=prefix),
        kiro_owned_skill_names(contract),
    )


@dataclass(frozen=True)
class ProgressionPhase:
    """One declared phase of the bootcamp progression.

    `match` is a contract glob over a skill directory *name*. A name carries no
    `/`, so the engine's matcher — where `*` does not cross `/` — spans the whole
    remainder of the name, and `module-*` claims every numbered module.
    """

    id: str
    match: str

    def claims(self, name: str) -> bool:
        return glob_matches(self.match, name)

    def to_json(self) -> dict[str, str]:
        return {"id": self.id, "match": self.match}


def progression_phases(contract: Contract) -> tuple[ProgressionPhase, ...]:
    """The declared progression phases, in declared order.

    Raises `Unevaluable` on an absent or malformed declaration, so a contract that
    does not say what the progression is blocks the tag instead of being read as
    an empty one — an empty phase list would place no skill and compare two empty
    sequences successfully.
    """
    declared = contract.raw.get(PROGRESSION_SECTION)
    if (
        not isinstance(declared, Sequence)
        or isinstance(declared, (str, bytes))
        or not declared
    ):
        raise Unevaluable(
            f"the contract at {contract.path} declares no non-empty "
            f"'{PROGRESSION_SECTION}' section, so the bootcamp progression order "
            "R7 AC3 preserves is stated nowhere the gate can read it"
        )
    phases: list[ProgressionPhase] = []
    for index, entry in enumerate(declared):
        if not isinstance(entry, Mapping):
            raise Unevaluable(
                f"contract defect: {PROGRESSION_SECTION}[{index}] is not a mapping "
                "of 'id' and 'match'"
            )
        identifier = entry.get("id")
        pattern = entry.get("match")
        if not isinstance(identifier, str) or not identifier.strip():
            raise Unevaluable(
                f"contract defect: {PROGRESSION_SECTION}[{index}] declares no 'id'"
            )
        if not isinstance(pattern, str) or not pattern.strip():
            raise Unevaluable(
                f"contract defect: {PROGRESSION_SECTION}[{index}] ('{identifier}') "
                "declares no 'match' pattern, so it claims no skill"
            )
        phases.append(
            ProgressionPhase(id=identifier.strip(), match=pattern.strip())
        )
    return tuple(phases)


def module_key(name: str) -> tuple[int, str] | None:
    """`(number, interstitial)` for a numbered module name, `None` for anything else.

    `module-03-sdk-setup` → `(3, "")`, `module-03b-truthset-visualization` →
    `(3, "b")`. The number is parsed rather than compared as text, so `module-10`
    follows `module-9` instead of preceding it, and the interstitial suffix orders
    after the bare module of the same number — which is the whole of "`module-03b`
    sits between `module-03` and `module-04`" *(R7 AC3)*.
    """
    match = MODULE_NAME.match(name)
    if match is None:
        return None
    return int(match.group("number")), match.group("interstitial")


def phase_index(name: str, phases: Sequence[ProgressionPhase]) -> int | None:
    """The index of the first phase claiming `name`, or `None` when none does."""
    for index, phase in enumerate(phases):
        if phase.claims(name):
            return index
    return None


def progression_key(
    name: str, phases: Sequence[ProgressionPhase]
) -> tuple[int, int, str, str]:
    """The sort key placing `name` in the progression.

    Phase first, then the module number, then the interstitial suffix, then the
    name itself so the order is total and therefore reproducible. A non-module
    name takes `-1` as its number, which keeps it ahead of the modules inside its
    own phase and has no effect across phases.
    """
    index = phase_index(name, phases)
    number, interstitial = module_key(name) or (-1, "")
    return (len(phases) if index is None else index, number, interstitial, name)


def progression_sequence(
    names: Iterable[str], phases: Sequence[ProgressionPhase]
) -> tuple[str, ...]:
    """`names` in progression order, onboarding through graduation.

    Names no phase claims are **excluded** rather than parked at one end:
    `unplaceable_skills` reports them by name, and carrying an unplaceable name
    into the sequence would turn one finding about an unknown skill shape into a
    sequence difference at every later position.
    """
    placed = [name for name in names if phase_index(name, phases) is not None]
    return tuple(sorted(placed, key=lambda name: progression_key(name, phases)))


def unplaceable_skills(
    names: Iterable[str], phases: Sequence[ProgressionPhase]
) -> tuple[str, ...]:
    """The names no declared phase claims, sorted."""
    return tuple(
        sorted(name for name in names if phase_index(name, phases) is None)
    )


def _progression_finding(
    message: str, *, kind: str, target: str | None = None, **details: Any
) -> Finding:
    return Finding(
        code=E_PROGRESSION_MISMATCH,
        message=message,
        target=target,
        details={"kind": kind, **details},
    )


def phase_declaration_findings(
    phases: Sequence[ProgressionPhase],
) -> tuple[Finding, ...]:
    """The declared phases run from onboarding to graduation, with distinct ids.

    R7 AC3 fixes the endpoints — "from onboarding through graduation" — so a
    declaration that ends somewhere else describes a different progression from
    the one the requirement is about, whatever the release contains. Checking the
    endpoints is what keeps the rest of this check from being a restatement of its
    own sort: the phase order is an input, and this is the part of it the
    requirement pins.
    """
    findings: list[Finding] = []
    identifiers = [phase.id for phase in phases]

    duplicates = sorted(
        {identifier for identifier in identifiers if identifiers.count(identifier) > 1}
    )
    if duplicates:
        findings.append(
            _progression_finding(
                f"the declared progression names {', '.join(duplicates)} more than "
                "once; a phase id names one position in the sequence",
                kind=PROGRESSION_PHASES_MISDECLARED,
                duplicated=duplicates,
                declared=identifiers,
            )
        )

    for position, expected in (
        (0, PROGRESSION_FIRST_PHASE),
        (-1, PROGRESSION_LAST_PHASE),
    ):
        if identifiers[position] != expected:
            findings.append(
                _progression_finding(
                    f"the declared progression's "
                    f"{'first' if position == 0 else 'last'} phase is "
                    f"{identifiers[position]!r}, not {expected!r}; the bootcamp runs "
                    f"from {PROGRESSION_FIRST_PHASE} through "
                    f"{PROGRESSION_LAST_PHASE}",
                    kind=PROGRESSION_PHASES_MISDECLARED,
                    expected=expected,
                    declared=identifiers,
                )
            )

    return tuple(findings)


def unplaceable_findings(
    names: Sequence[str], phases: Sequence[ProgressionPhase], *, origin: str
) -> tuple[Finding, ...]:
    """One finding per name no declared phase claims, in `origin`'s vocabulary.

    On the release side this is the early warning the derived inventory exists to
    give: upstream added a skill of a shape the progression does not describe, and
    the Maintainer adds a phase rather than discovering later that the skill was
    quietly ordered last.
    """
    return tuple(
        _progression_finding(
            f"the {origin} carries the bootcamp skill {name!r}, and no declared "
            f"'{PROGRESSION_SECTION}' phase claims it, so it has no position in the "
            f"progression; the declared phases are "
            f"{[phase.match for phase in phases]}",
            kind=PROGRESSION_UNPLACEABLE,
            target=_skill_target(name),
            skill=name,
            origin=origin,
        )
        for name in unplaceable_skills(names, phases)
    )


def sequence_findings(
    ported: Sequence[str], template: Sequence[str]
) -> tuple[Finding, ...]:
    """The two progression sequences agree element-for-element *(R7 AC3)*.

    One finding, not one per position: a single dropped skill shifts every later
    element, and a Maintainer reading fourteen findings about one omission learns
    less than one that names the first divergence and carries both sequences.
    Every divergent position is still in `details`, so nothing is lost to a
    consumer reading data rather than prose.
    """
    if tuple(ported) == tuple(template):
        return ()

    divergences = [
        {
            "index": index,
            "ported": ported[index] if index < len(ported) else None,
            "template": template[index] if index < len(template) else None,
        }
        for index in range(max(len(ported), len(template)))
        if (ported[index] if index < len(ported) else None)
        != (template[index] if index < len(template) else None)
    ]
    first = divergences[0]
    return (
        _progression_finding(
            "the ported bootcamp progression is not the template's: at position "
            f"{first['index']} the Power presents "
            f"{first['ported'] if first['ported'] is not None else 'nothing'} where "
            "the resolved Template_Release presents "
            f"{first['template'] if first['template'] is not None else 'nothing'} "
            f"(ported {list(ported)}, template {list(template)})",
            kind=PROGRESSION_SEQUENCE_DIFFERS,
            index=first["index"],
            divergences=divergences,
            ported=list(ported),
            template=list(template),
        ),
    )


def interstitial_findings(sequence: Sequence[str]) -> tuple[Finding, ...]:
    """Each interstitial module sits after its base module and before the next.

    `module-03b-truthset-visualization` between `module-03-…` and `module-04-…`,
    stated as a claim about a *given* sequence so *Property 17* can drive it with
    a misordered one. Over a sequence `progression_sequence` produced it is a
    self-check of `progression_key` — cheap, and the thing that would notice if
    the key ever stopped ordering interstitials the way R7 AC3 requires.
    """
    keys = {name: module_key(name) for name in sequence}
    positions = {name: index for index, name in enumerate(sequence)}
    findings: list[Finding] = []

    for name in sequence:
        key = keys[name]
        if key is None or not key[1]:
            continue
        number, suffix = key
        base = next(
            (other for other in sequence if keys[other] == (number, "")), None
        )
        later = [
            (other_key, other)
            for other in sequence
            for other_key in (keys[other],)
            if other_key is not None and other_key[0] > number
        ]
        following = min(later)[1] if later else None
        if base is not None and positions[base] > positions[name]:
            findings.append(
                _progression_finding(
                    f"the progression places the interstitial module {name!r} at "
                    f"position {positions[name]}, ahead of the module it follows, "
                    f"{base!r} at position {positions[base]}; an interstitial sits "
                    f"between module {number:02d} and module {number + 1:02d}",
                    kind=PROGRESSION_INTERSTITIAL_MISPLACED,
                    target=_skill_target(name),
                    skill=name,
                    interstitial=suffix,
                    before=base,
                )
            )
        if following is not None and positions[following] < positions[name]:
            findings.append(
                _progression_finding(
                    f"the progression places the interstitial module {name!r} at "
                    f"position {positions[name]}, after {following!r} at position "
                    f"{positions[following]}, which is a later module; an "
                    f"interstitial sits between module {number:02d} and module "
                    f"{number + 1:02d}",
                    kind=PROGRESSION_INTERSTITIAL_MISPLACED,
                    target=_skill_target(name),
                    skill=name,
                    interstitial=suffix,
                    after=following,
                )
            )

    return tuple(findings)


def progression_result(
    phases: Sequence[ProgressionPhase],
    ported: Sequence[str],
    template_skills: Sequence[str],
) -> CheckResult:
    """The recorded result for one ported inventory against one release's.

    Pure over the declared phases and two name collections, so *Property 17*
    drives it directly. A membership difference between the two inventories
    surfaces here as a sequence difference as well as in the `skill-inventory`
    result: the two checks answer different questions about it — which skill is
    missing, and where the progression breaks — and R7 AC3 asks for the sequences
    element-for-element rather than for the order of whatever both happen to
    carry.
    """
    template_sequence = progression_sequence(template_skills, phases)
    ported_sequence = progression_sequence(ported, phases)
    findings = (
        phase_declaration_findings(phases)
        + unplaceable_findings(
            tuple(template_skills), phases, origin="resolved Template_Release"
        )
        + unplaceable_findings(tuple(ported), phases, origin="Bootcamp_Power")
        + sequence_findings(ported_sequence, template_sequence)
        + interstitial_findings(ported_sequence)
    )
    return CheckResult(
        id="progression-order",
        findings=findings,
        extra={
            "phases": [phase.to_json() for phase in phases],
            "templateSequence": list(template_sequence),
            "portedSequence": list(ported_sequence),
            "mismatches": [_correspondence_record(finding) for finding in findings],
        },
    )


@register_check(
    "progression-order",
    code=E_PROGRESSION_MISMATCH,
    target=SKILL_INVENTORY_TARGET,
    requirement="7.3",
)
def check_progression_order(context: ValidationContext) -> CheckResult:
    """The ported progression is the template's, element-for-element *(R7 AC3)*.

    Both sequences are derived from the one declared phase order — the template's
    from the skill directories in the resolved release, the Power's from the
    skills that stand for them — so the order is stated once, in the contract,
    and the comparison is between two things that were ordered the same way.

    Fails closed without the release tree, without the contract, and on a release
    tree carrying no `skills/` directory, for the same reasons the inventory check
    does.
    """
    source = context.require_source()
    contract = context.require_contract()
    phases = progression_phases(contract)
    prefix = source_prefix(source, contract.plugin_root)
    template_skills = skill_names(source, prefix=prefix)
    if not template_skills:
        raise Unevaluable(
            "the resolved Template_Release tree carries no "
            f"{prefix}{SKILLS_DIRECTORY}/ directory, so the template progression "
            "sequence R7 AC3 preserves cannot be derived; check that --source "
            "names the extracted release"
        )
    return progression_result(
        phases,
        ported_skill_names(skill_inventory(context.tree), template_skills),
        template_skills,
    )


# ---------------------------------------------------------------------------
# The `script-imports` and `script-references` checks (R10 AC4, AC6)
# ---------------------------------------------------------------------------
#
# Two rows of the design's check table, two recorded results, and one fact
# underneath both: the template's hook scripts import one another as
# same-directory Python modules (`import recap_checkpoint`, `import
# docker_lifecycle`), which is why every ported script lands together under a
# single owning skill's `scripts/` directory rather than being distributed
# per-skill (design defect **D4**, R10 AC1). That placement is contract data the
# engine executes; what these two checks establish is that the arrangement still
# *works* in the produced Power:
#
# * `script-imports` — every same-directory module import between two ported
#   scripts resolves, and a broken one is reported naming the importing script
#   and the imported module name *(R10 AC6)*.
# * `script-references` — every script and vendored asset a ported script or a
#   hook definition names exists in the produced Power *(R10 AC4)*.
#
# Evidence, not a module list
# ---------------------------
# Nothing here carries a list of the corpus's modules, and that omission is what
# keeps the import check honest against a release that adds one. `import json`
# and `import recap_checkpoint` are the same two tokens to a reader; what
# separates them is that the artifacts *ship a file* named
# `recap_checkpoint.py` and ship nothing named `json.py`. So an import is judged
# to be a same-directory module import exactly when something provides that
# module — no standard-library list, no third-party allowlist, and no way for a
# new module to be silently skipped. Two ways that judgment comes out broken,
# and each names a different repair:
#
# * `module-not-colocated` — the module is provided **elsewhere in the Power**.
#   The scripts were split across directories, so an import that resolved in the
#   template does not resolve here; the finding names where the module landed.
#   This is precisely the failure D4 exists to prevent.
# * `module-unported` — the **resolved release** ships the module under its
#   `scripts/` tree and nothing in the Power provides it. The port dropped a
#   script the importing script will still ask for at runtime.
#
# Anything else a script imports is a runtime dependency this gate has no
# opinion about, and it says so by reporting nothing.
#
# What must exist — and what must not be required to
# -------------------------------------------------
# The reference half carries the opposite hazard. Ported scripts name plenty of
# paths that are *supposed* not to exist yet: the recap PDF they write, the
# screenshots they capture, the state files they create. A check reading "every
# path a script names must exist" would block every correct release, so exactly
# three populations are required to exist, each for a stated reason:
#
# * **vendored assets** (`vendor/d3.v7.min.js`) — third-party content that is
#   checked in and never produced at runtime, so a reference the Power cannot
#   satisfy is unambiguously a broken port. The spelling rule is the engine's
#   `vendored_asset_references`, imported rather than reimplemented: the
#   transform halts on the *source* side of R10 AC4 under the same code, and two
#   readers of one rule is how the two sides come to disagree about what a
#   reference is.
# * **Python modules** (`senzing_viz_server.py`) — no ported script writes a
#   `.py` file, so a named one is an input.
# * **whatever the resolved release ships beside its scripts**
#   (`senzing_logo_light.png`) — the template shipped it as script-side content,
#   so the produced Power owes it. This population is empty without `--source`,
#   which is the honest degradation: the other two still hold, and the release
#   side of the same condition already halted the transform.
#
# A **hook** reference is the one that is resolved exactly rather than by
# suffix: a shipped Hook_Command_String names `<ABSOLUTE_SCRIPTS_DIR>/<script>`,
# the `Hook_Installer` resolves that placeholder to the ported script directory,
# and so the script must sit at that one path. Where that directory is comes
# from the contract, which is where the mapping decision lives (R3 AC4) — a hook
# pointing into a directory the contract does not produce is a hook that can
# never fire, and it is reported here rather than discovered by a Bootcamper.
#
# Everything above the two check functions is a pure function of text, of path
# strings, or of a parsed JSON document, so *Property 11* drives extraction and
# resolution from generated trees with no staging directory involved.

#: A directory becomes an importable package through this file, which is the
#: second of the two spellings an import can resolve to.
PACKAGE_MARKER = "__init__.py"

#: Every Python module in the produced Power. Ported scripts, the `kiro-owned`
#: `optional_runtime.py` beside them, and the `Hook_Installer` alike: an import
#: that cannot resolve is the same defect whoever wrote the file.
SCRIPT_GLOB = f"**/*{SCRIPT_SUFFIX}"

#: `CheckResult.target` for both checks — the population the references and the
#: imports are read from. The reference check also reads the hook definitions,
#: which it lists in its own `hookDefinitions`.
SCRIPT_TARGET = SCRIPT_GLOB

#: The template directory the ported script set comes from, as the contract's
#: script rules spell it in their `source` patterns.
SCRIPT_SOURCE_ROOT = "scripts"

#: The Plugin_Root_Token a ported script writes after the `plugin-root`
#: substitution set has run (R10 AC2). A reference carrying it is rooted at the
#: Power root rather than at the referencing script's directory.
POWER_ROOT_TOKEN = "${PLUGIN_ROOT}"

#: The placeholder a shipped hook definition carries in place of the ported
#: script directory. The `Hook_Installer` declares it as
#: `PLACEHOLDER_SCRIPTS_DIR` and resolves it at install time; a definition
#: spelling it any other way is `hook-command-strings`'s to report, since the
#: installer's own `resolve_command` refuses to write such a string.
SCRIPTS_DIR_PLACEHOLDER = "<ABSOLUTE_SCRIPTS_DIR>"

#: `broken[].kind` — how a same-directory module import fails to resolve.
IMPORT_RELOCATED = "module-not-colocated"
IMPORT_UNPORTED = "module-unported"

IMPORT_KINDS: tuple[str, ...] = (IMPORT_RELOCATED, IMPORT_UNPORTED)

#: `missing[].kind` — *why* a reference was required to exist. The catalog code
#: is `E_MISSING_ASSET` for all four; the kind is what says which repair applies,
#: so it travels as data rather than as prose.
ASSET_VENDORED = "vendored-asset"
ASSET_MODULE = "python-module"
ASSET_RELEASE_SHIPPED = "release-shipped-asset"
ASSET_HOOK_SCRIPT = "hook-invoked-script"

ASSET_KINDS: tuple[str, ...] = (
    ASSET_VENDORED,
    ASSET_MODULE,
    ASSET_RELEASE_SHIPPED,
    ASSET_HOOK_SCRIPT,
)

#: An `import x` / `from x import y` statement, read from text a parser refused.
#: The module alphabet admits a hyphen, which no importable module name carries,
#: deliberately: this pattern reads a file `ast` could not parse, and a name that
#: cannot be imported is exactly the sort of thing such a file spells.
_IMPORT_STATEMENT = re.compile(
    r"^[ \t]*(?:import|from)[ \t]+(?P<module>[A-Za-z_][A-Za-z0-9_.\-]*)",
    re.MULTILINE,
)

#: One path segment as a script writes it, and a final segment that names a file
#: rather than a directory. The same shapes the engine's vendored-asset detector
#: uses, so the two halves of R10 AC4 read a path the same way.
_REFERENCE_SEGMENT = r"[A-Za-z0-9_@+~.-]+"
_REFERENCE_FILENAME = rf"{_REFERENCE_SEGMENT}\.[A-Za-z0-9]+"

#: A quoted path literal naming a file: `"senzing_logo_light.png"`,
#: `'helpers/tool.py'`, `"${PLUGIN_ROOT}/scripts/x.py"`.
_PATH_LITERAL = re.compile(
    rf"(?P<quote>['\"])(?P<path>(?:{re.escape(POWER_ROOT_TOKEN)}/)?"
    rf"(?:{_REFERENCE_SEGMENT}/)*{_REFERENCE_FILENAME})(?P=quote)"
)

#: One quoted segment, and a chain of them joined by an argument comma or a `/`:
#: `os.path.join(here, "helpers", "tool.py")`,
#: `Path(__file__).parent / "helpers" / "tool.py"`.
_QUOTED_REFERENCE_SEGMENT = r"""(?:'[^'\n]*'|"[^"\n]*")"""
_REFERENCE_SEGMENT_CHAIN = re.compile(
    rf"{_QUOTED_REFERENCE_SEGMENT}(?:\s*[,/]\s*{_QUOTED_REFERENCE_SEGMENT})+"
)
_QUOTED_REFERENCE_PATTERN = re.compile(_QUOTED_REFERENCE_SEGMENT)

#: A client-resolved placeholder other than the Power root token. Such a
#: reference is assembled at runtime from something this check cannot see.
_REFERENCE_PLACEHOLDER = re.compile(r"\$\{[^}]*\}|\{\{[^}]*\}\}")


def script_paths(tree: PowerTree) -> tuple[str, ...]:
    """Every Python module in the produced Power, sorted."""
    return tree.match(SCRIPT_GLOB)


def module_providers(paths: Iterable[str]) -> Mapping[str, tuple[str, ...]]:
    """Module name → the directories that make it importable, sorted.

    The one place the two importable spellings are stated: `<dir>/<name>.py`
    provides `<name>` in `<dir>`, and `<dir>/<name>/__init__.py` provides the
    package `<name>` in `<dir>`. A module at the tree root is provided in `""`.

    Pure over path strings, so the same function derives what the produced Power
    provides and what the resolved release ships.
    """
    providers: dict[str, set[str]] = {}
    for path in paths:
        if not path.endswith(SCRIPT_SUFFIX):
            continue
        directory, _, filename = path.rpartition("/")
        if filename == PACKAGE_MARKER:
            parent, _, package = directory.rpartition("/")
            if package:
                providers.setdefault(package, set()).add(parent)
            continue
        providers.setdefault(filename[: -len(SCRIPT_SUFFIX)], set()).add(directory)
    return {
        module: tuple(sorted(directories))
        for module, directories in sorted(providers.items())
    }


def release_script_modules(
    source: PowerTree, *, prefix: str = ""
) -> tuple[str, ...]:
    """The module names the resolved release ships under its `scripts/` tree."""
    return tuple(
        module_providers(
            source.match(f"{prefix}{SCRIPT_SOURCE_ROOT}/**/*{SCRIPT_SUFFIX}")
        )
    )


def supplied_paths(paths: Iterable[str]) -> frozenset[str]:
    """Every segment-aligned suffix of every path in a tree.

    `skills/bootcamp-onboarding/scripts/vendor/d3.v7.min.js` supplies that path,
    `scripts/vendor/d3.v7.min.js`, `vendor/d3.v7.min.js`, and
    `d3.v7.min.js` — every spelling a script could name it by. This generalizes
    the engine's `vendored_asset_paths`, which is the same suffix set restricted
    to the ones beginning at a `vendor/` segment, and it is segment-aligned by
    construction, so `vendor/x.js` is never satisfied by `notvendor/x.js`.
    """
    supplied: set[str] = set()
    for path in paths:
        segments = path.split("/")
        for index in range(len(segments)):
            supplied.add("/".join(segments[index:]))
    return frozenset(supplied)


def release_script_assets(
    source: PowerTree, *, prefix: str = ""
) -> frozenset[str]:
    """Every spelling the resolved release ships beside its scripts.

    The evidence set for the third required population: a reference the template
    itself supplies as script-side content is content the produced Power owes,
    whatever its file kind.
    """
    return supplied_paths(source.match(f"{prefix}{SCRIPT_SOURCE_ROOT}/**"))


def ported_scripts_directory(contract: Contract) -> str:
    """The one Power directory the contract maps the template `scripts/` onto.

    Read from the contract's script rules rather than spelled here, so where the
    ported script set lands stays a contract edit and nothing more (R3 AC4). The
    rules that carry the vendored assets and the sibling non-Python assets land
    under the same root, so the root is the shortest of the declared
    destinations.

    Raises `Unevaluable` when the contract declares no script destination, or
    declares destinations that do not share one root — D4's co-location premise
    failing in the declaration itself, before a single file is written.
    """
    destinations = sorted(
        {
            destination.strip("/")
            for rule in contract.rules
            if rule.produces_output
            and rule.source is not None
            and rule.source.split("/")[0] == SCRIPT_SOURCE_ROOT
            for destination in rule.dest
        },
        key=lambda destination: (len(destination), destination),
    )
    if not destinations:
        raise Unevaluable(
            f"the contract at {contract.path} declares no rule mapping the "
            f"template '{SCRIPT_SOURCE_ROOT}/' tree onto the Power, so where a "
            "hook's script has to sit is stated nowhere the gate can read it"
        )
    root = destinations[0]
    scattered = [
        destination
        for destination in destinations[1:]
        if not destination.startswith(f"{root}/")
    ]
    if scattered:
        raise Unevaluable(
            f"the contract at {contract.path} maps the template "
            f"'{SCRIPT_SOURCE_ROOT}/' tree onto directories that do not share "
            f"one root ({', '.join([root, *scattered])}); every ported script "
            "belongs under a single owning skill's scripts/ directory so that "
            "the same-directory module imports between them resolve (R10 AC1)"
        )
    return root


def _release_prefix(context: ValidationContext) -> str:
    """The prefix release-relative paths carry in `context.source`.

    `--source` may name the marketplace repository root or the plugin root
    inside it, and the contract says which is which. Without a contract the
    prefix is empty, which reads a plugin-root tree correctly and reads a
    repository-root tree as shipping nothing — an empty evidence set, never a
    wrong one.
    """
    source = context.source
    if source is None:
        return ""
    contract = context.contract
    return source_prefix(source, contract.plugin_root if contract else "")


@dataclass(frozen=True)
class ScriptImport:
    """One module import a script spells: where it is written, and what it names.

    `module` is the *top-level* name, because that is the name that has to be
    importable from the script's own directory: `import a.b` needs `a` there,
    whatever `a` then contains.
    """

    script: str
    module: str
    line: int

    @property
    def directory(self) -> str:
        """The directory the import has to resolve in — the script's own."""
        return self.script.rpartition("/")[0]

    def details(self) -> dict[str, Any]:
        return {
            "script": self.script,
            "module": self.module,
            "directory": self.directory,
            "line": self.line,
        }


def script_imports(text: str, *, source: str) -> tuple[ScriptImport, ...]:
    """Every module `text` imports, in document order, one entry per module.

    Read with `ast` where the module parses, which is what keeps an `import`
    written inside a docstring or a comment from being counted as one. Where it
    does not parse — generated content, or a script upstream broke — the
    statements are read line by line instead of abandoned: a verdict from a
    lenient reader beats no verdict at all. Both paths yield `(module, line)`
    pairs, so everything below this function has one code path.

    A module imported three times is one thing to fix, so repeats collapse onto
    the earliest line that names it.
    """
    found: list[tuple[str, int]] = []
    try:
        parsed = ast.parse(text)
    except (SyntaxError, ValueError):
        found.extend(
            (
                match.group("module").split(".")[0],
                text.count("\n", 0, match.start()) + 1,
            )
            for match in _IMPORT_STATEMENT.finditer(text)
        )
    else:
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                found.extend(
                    (alias.name.split(".")[0], node.lineno) for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                # `level` counts the leading dots of a relative import. A ported
                # script directory is not a package, so a relative import never
                # names a sibling module and is not a same-directory import.
                if node.level == 0 and node.module:
                    found.append((node.module.split(".")[0], node.lineno))

    earliest: dict[str, int] = {}
    for module, line in found:
        if not module:
            continue
        earliest[module] = min(line, earliest.get(module, line))
    return tuple(
        sorted(
            (
                ScriptImport(script=source, module=module, line=line)
                for module, line in earliest.items()
            ),
            key=lambda entry: (entry.line, entry.module),
        )
    )


def import_resolves(
    entry: ScriptImport, provided: Mapping[str, Sequence[str]]
) -> bool:
    """Whether `entry` resolves from the importing script's own directory."""
    return entry.directory in tuple(provided.get(entry.module, ()))


def _broken_import_finding(
    entry: ScriptImport, kind: str, provided_by: Sequence[str]
) -> Finding:
    """One broken import, naming the importing script and the module *(AC6)*."""
    if kind == IMPORT_RELOCATED:
        where = ", ".join(
            f"{directory}/" if directory else "the Power root"
            for directory in provided_by
        )
        reason = (
            f"and {entry.module}{SCRIPT_SUFFIX} is in the produced Power at "
            f"{where} instead. Every ported script belongs together under one "
            "owning skill's scripts/ directory, because that co-location is "
            "what makes a same-directory module import between two of them "
            "resolve at runtime (R10 AC1)"
        )
    else:
        reason = (
            "and nothing in the produced Power provides it, although the "
            f"resolved Template_Release ships "
            f"{SCRIPT_SOURCE_ROOT}/{entry.module}{SCRIPT_SUFFIX}. The port "
            "dropped a script that another ported script imports"
        )
    return Finding(
        code=E_BROKEN_IMPORT,
        message=(
            f"{entry.script} imports the module {entry.module!r} on line "
            f"{entry.line}, {reason}"
        ),
        target=entry.script,
        location=f"line {entry.line}",
        details={
            **entry.details(),
            "kind": kind,
            "providedBy": list(provided_by),
        },
    )


def broken_import_findings(
    imports: Iterable[ScriptImport],
    provided: Mapping[str, Sequence[str]],
    shipped: Iterable[str] = (),
) -> tuple[Finding, ...]:
    """Every import that does not resolve where its script sits *(R10 AC6)*.

    Pure over the imports, what the produced Power provides, and what the
    release ships, so *Property 11* drives it from a generated placement without
    a filesystem. An import with no evidence behind it — a standard-library or
    third-party module — is not a same-directory module import and is passed
    over rather than reported.
    """
    release = frozenset(shipped)
    findings: list[Finding] = []
    for entry in imports:
        if import_resolves(entry, provided):
            continue
        elsewhere = tuple(provided.get(entry.module, ()))
        if elsewhere:
            findings.append(
                _broken_import_finding(entry, IMPORT_RELOCATED, elsewhere)
            )
        elif entry.module in release:
            findings.append(_broken_import_finding(entry, IMPORT_UNPORTED, ()))
    return tuple(findings)


def _broken_import_record(finding: Finding) -> dict[str, Any]:
    """The compact per-import row this check's `broken` array carries."""
    return {
        "script": finding.details.get("script", finding.target),
        "module": finding.details.get("module"),
        "line": finding.details.get("line"),
        "kind": finding.details.get("kind"),
        "providedBy": finding.details.get("providedBy", []),
    }


def script_import_result(
    tree: PowerTree, *, release_modules: Iterable[str] = ()
) -> CheckResult:
    """The recorded result for one produced Power's module imports.

    Pure over the tree and the release's module names, so *Property 11* drives
    it directly. A module whose bytes cannot be decoded is recorded against
    itself and the sweep continues: the other scripts' imports are still owed a
    verdict.
    """
    scripts = script_paths(tree)
    provided = module_providers(tree.paths)
    release = tuple(release_modules)
    findings: list[Finding] = []
    imports: list[ScriptImport] = []
    for path in scripts:
        try:
            text = tree.read_text(path)
        except Unevaluable as error:
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=(
                        f"{error.message}, so the module imports it spells "
                        "cannot be resolved"
                    ),
                    target=path,
                )
            )
            continue
        spelled = script_imports(text, source=path)
        imports.extend(spelled)
        findings.extend(broken_import_findings(spelled, provided, release))

    return CheckResult(
        id="script-imports",
        target=SCRIPT_TARGET,
        findings=tuple(findings),
        extra={
            "scriptGlob": SCRIPT_GLOB,
            "scripts": len(scripts),
            "imports": len(imports),
            "releaseModules": len(release),
            "broken": [
                _broken_import_record(finding)
                for finding in findings
                if finding.code == E_BROKEN_IMPORT
            ],
        },
    )


@register_check(
    "script-imports",
    code=E_BROKEN_IMPORT,
    target=SCRIPT_TARGET,
    requirement="10.6",
)
def check_script_imports(context: ValidationContext) -> CheckResult:
    """Every same-directory module import resolves *(R10 AC6)*.

    One recorded result for the script set, carrying one finding per broken
    import naming the importing script and the imported module name. Tagging is
    then blocked by construction rather than by a separate rule: an
    error-severity finding fails the result, a failing result makes the status
    `failed`, and `tagAllowed` is the biconditional over that.

    The resolved release tree sharpens the check where it is available — an
    import of a module the release ships and the Power lost is reported — but is
    not required for it: a module that moved within the Power is detectable from
    the Power alone. A Power carrying no Python module at all is the one
    condition that declines to answer, because a produced Bootcamp_Power ships
    the ported script set and recording a pass for an empty one would let a
    Power with no scripts satisfy the gate.
    """
    tree = context.tree
    if not script_paths(tree):
        raise Unevaluable(
            f"the produced Power carries no {SCRIPT_GLOB} file, so no ported "
            "script's module imports could be resolved; a produced "
            "Bootcamp_Power ships the ported script set under the owning "
            "skill's scripts/ directory (R10 AC1)",
            target=SCRIPT_TARGET,
        )
    source = context.source
    return script_import_result(
        tree,
        release_modules=(
            release_script_modules(source, prefix=_release_prefix(context))
            if source is not None
            else ()
        ),
    )


@dataclass(frozen=True)
class AssetReference:
    """One script or asset a ported script or a hook definition names.

    `spelling` is the path as this check compares it: rooted where the reference
    is rooted, with a `${PLUGIN_ROOT}/` prefix removed, because that token
    expands to the Power root. `required` carries the one exact Power path a
    reference has to occupy where the reference fixes one — a hook's script,
    which the `Hook_Installer` resolves against the ported script directory.
    `subject` is the hook name, so a finding can name the hook rather than only
    the file it sits in.
    """

    origin: str
    spelling: str
    kind: str
    line: int | None = None
    subject: str | None = None
    required: str | None = None

    @property
    def exact(self) -> bool:
        """Whether this reference names one path rather than a spelling."""
        return self.required is not None

    def details(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "origin": self.origin,
            "reference": self.spelling,
            "kind": self.kind,
        }
        if self.line is not None:
            payload["line"] = self.line
        if self.subject is not None:
            payload["hook"] = self.subject
        if self.required is not None:
            payload["required"] = self.required
        return payload


def asset_reference_path(literal: str) -> str | None:
    """The comparable spelling a path literal names, or `None` for none.

    `None` for the shapes this check deliberately does not resolve, each because
    where it lands is decided somewhere this check cannot see: a root-absolute
    path, a path carrying a client-resolved placeholder other than the Power
    root token, and a path walking up through `..` — which names a different file
    depending on where the script sits at runtime.
    """
    candidate = literal.strip()
    if not candidate:
        return None
    if candidate.startswith(f"{POWER_ROOT_TOKEN}/"):
        candidate = candidate[len(POWER_ROOT_TOKEN) + 1 :]
    if candidate.startswith("/") or _REFERENCE_PLACEHOLDER.search(candidate):
        return None
    segments = [
        segment for segment in candidate.split("/") if segment not in ("", ".")
    ]
    if not segments or ".." in segments:
        return None
    return "/".join(segments)


def _crosses_vendor(spelling: str) -> bool:
    """Whether a spelling reaches into a `vendor/` directory.

    Such a reference belongs to the vendored population, whose spelling rule is
    the engine's, so the general reader hands it over rather than reporting the
    same reference twice under two spellings.
    """
    return VENDOR_SEGMENT in spelling.split("/")


def _chain_spelling(chain: str) -> str | None:
    """The path a chain of quoted segments assembles, or `None`.

    The chain is read up to and including the first segment that names a file,
    because what follows is the call's other arguments rather than more of the
    path: `os.path.join(base, "helpers", "tool.py")` names `helpers/tool.py` and
    nothing beyond it.
    """
    collected: list[str] = []
    for quoted in _QUOTED_REFERENCE_PATTERN.findall(chain):
        for segment in quoted[1:-1].split("/"):
            if re.fullmatch(_REFERENCE_SEGMENT, segment) is None:
                return None
            collected.append(segment)
            if re.fullmatch(_REFERENCE_FILENAME, segment) is not None:
                return "/".join(collected)
    return None


def script_asset_references(
    text: str, *, source: str, shipped: Iterable[str] = ()
) -> tuple[AssetReference, ...]:
    """Every script and asset `text` names that has to exist *(R10 AC4)*.

    Pure: text and evidence in, references out. Three populations, in the order
    their reasons were stated above — the vendored assets the engine's reader
    finds, the Python modules a path literal names, and whatever the resolved
    release ships beside its scripts. A path literal that is none of those is a
    file the script creates or a path resolved elsewhere, and it is not returned.

    A chain of joined segments feeds only the release-shipped population, and
    deliberately: `f("mod", "x.py")` also looks like a joined path, so a chain is
    read as a reference only when the template actually ships what it assembles.

    Repeats collapse onto the earliest line naming them, and so does one
    reference read at two depths: `os.path.join(here, "vendor", "d3.v7.min.js")`
    is found by the vendored reader as `vendor/d3.v7.min.js` and by the literal
    reader as `d3.v7.min.js`, which is the same file named once. The longer,
    segment-aligned spelling wins, because it is the shape the reference
    actually has — one reference, one finding, one fix.
    """
    release = frozenset(shipped)
    found: dict[str, AssetReference] = {}

    def record(spelling: str, kind: str, line: int | None) -> None:
        existing = found.get(spelling)
        if existing is None or (
            line is not None
            and existing.line is not None
            and line < existing.line
        ):
            found[spelling] = AssetReference(
                origin=source, spelling=spelling, kind=kind, line=line
            )

    for spelling in vendored_asset_references(text):
        record(spelling, ASSET_VENDORED, None)

    for match in _PATH_LITERAL.finditer(text):
        literal = asset_reference_path(match.group("path"))
        if literal is None or _crosses_vendor(literal):
            continue
        line = text.count("\n", 0, match.start()) + 1
        if literal.endswith(SCRIPT_SUFFIX):
            record(literal, ASSET_MODULE, line)
        elif literal in release:
            record(literal, ASSET_RELEASE_SHIPPED, line)

    for match in _REFERENCE_SEGMENT_CHAIN.finditer(text):
        assembled = _chain_spelling(match.group(0))
        if assembled is None:
            continue
        chained = asset_reference_path(assembled)
        if chained is None or _crosses_vendor(chained):
            continue
        if chained in release:
            record(
                chained,
                ASSET_RELEASE_SHIPPED,
                text.count("\n", 0, match.start()) + 1,
            )

    spellings = set(found)
    return tuple(
        sorted(
            (
                reference
                for spelling, reference in found.items()
                if not any(
                    other.endswith(f"/{spelling}") for other in spellings - {spelling}
                )
            ),
            key=lambda reference: (
                reference.line if reference.line is not None else 0,
                reference.spelling,
            ),
        )
    )


def command_script_paths(
    command: str, *, placeholder: str = SCRIPTS_DIR_PLACEHOLDER
) -> tuple[str, ...]:
    """The scripts-directory-relative paths one command string names, in order.

    Pure over the command string. The shipped shape is
    `"<ABSOLUTE_PYTHON>" "<ABSOLUTE_SCRIPTS_DIR>/<script>.py"`, so a path runs
    from the placeholder's separator to the closing quote; whether the string is
    otherwise well formed is `hook-command-strings`'s verdict, not this one's.
    """
    return tuple(
        match.group("script")
        for match in _scripts_dir_pattern(placeholder).finditer(command)
    )


@lru_cache(maxsize=None)
def _scripts_dir_pattern(placeholder: str) -> re.Pattern[str]:
    return re.compile(re.escape(placeholder) + r"/(?P<script>[^\"'\s]+)")


def hook_script_references(
    document: Any,
    definition: str,
    *,
    scripts_directory: str,
    placeholder: str = SCRIPTS_DIR_PLACEHOLDER,
) -> tuple[AssetReference, ...]:
    """Every ported script the hooks in one definition invoke *(R10 AC4, AC5)*.

    Pure over a parsed definition and the directory the `Hook_Installer`
    resolves the placeholder to, so the reference is the exact path the written
    hook would run. The shape faults `hook_commands` reports are dropped here on
    purpose: a malformed command string is one defect with one owner, and
    repeating it under `E_MISSING_ASSET` would report it as two.
    """
    entries, _ = hook_commands(document, definition)
    root = scripts_directory.strip("/")
    return tuple(
        AssetReference(
            origin=definition,
            spelling=relative,
            kind=ASSET_HOOK_SCRIPT,
            subject=entry.hook_name,
            required=f"{root}/{relative}" if root else relative,
        )
        for entry in entries
        for relative in command_script_paths(entry.command, placeholder=placeholder)
    )


def asset_reference_satisfied(
    reference: AssetReference, *, paths: frozenset[str], supplied: frozenset[str]
) -> bool:
    """Whether the produced Power carries what `reference` names.

    An exact reference is satisfied by the one path it fixes. Everything else is
    satisfied by any file whose path *ends* with the spelling, segment-aligned,
    because R10 AC4 asks whether the referenced file exists in the produced
    Power and a script's own prefix (`here`, `${PLUGIN_ROOT}/scripts/`, nothing
    at all) is resolved at runtime. Where a module has to sit relative to its
    importer is `script-imports`' question, not this one's.
    """
    if reference.required is not None:
        return reference.required in paths
    return reference.spelling in supplied


def _missing_asset_finding(reference: AssetReference) -> Finding:
    """One dangling reference, naming the referencing file and the asset."""
    if reference.kind == ASSET_HOOK_SCRIPT:
        message = (
            f"hook {reference.subject!r} in {reference.origin} invokes the "
            f"ported script {reference.spelling!r}, which the produced Power "
            f"does not carry at {reference.required}; the Hook_Installer "
            f"resolves {SCRIPTS_DIR_PLACEHOLDER} to that directory, so the "
            "installed hook would fire at a script that is not there"
        )
        location: str | None = (
            f"hook {reference.subject}" if reference.subject else None
        )
    else:
        reasons = {
            ASSET_VENDORED: (
                "no file in the produced Power supplies it. Vendored content is "
                "third-party, checked in, and never produced at runtime, so a "
                "reference the Power cannot satisfy is a broken port: the asset "
                "belongs under the ported scripts' vendor/ directory (R10 AC3)"
            ),
            ASSET_MODULE: (
                "no file in the produced Power supplies it. A ported script "
                "never writes a Python module, so a named one is an input the "
                "Power has to ship"
            ),
            ASSET_RELEASE_SHIPPED: (
                "no file in the produced Power supplies it, although the "
                "resolved Template_Release ships it beside the template "
                "scripts. Every asset a ported script loads is preserved at the "
                "same relative location (R10 AC3)"
            ),
        }
        where = f" on line {reference.line}" if reference.line is not None else ""
        message = (
            f"{reference.origin} references {reference.spelling!r}{where}, and "
            f"{reasons[reference.kind]}"
        )
        location = f"line {reference.line}" if reference.line is not None else None
    return Finding(
        code=E_MISSING_ASSET,
        message=message,
        target=reference.origin,
        location=location,
        details=reference.details(),
    )


def missing_asset_findings(
    references: Iterable[AssetReference],
    *,
    paths: frozenset[str],
    supplied: frozenset[str],
) -> tuple[Finding, ...]:
    """One finding per reference the produced Power cannot satisfy *(AC4)*.

    Pure over the references and the two path collections, and every reference
    is examined: a script naming four absent assets reports four, not the first.
    """
    return tuple(
        _missing_asset_finding(reference)
        for reference in references
        if not asset_reference_satisfied(
            reference, paths=paths, supplied=supplied
        )
    )


def _missing_asset_record(finding: Finding) -> dict[str, Any]:
    """The compact per-reference row this check's `missing` array carries."""
    return {
        "origin": finding.details.get("origin", finding.target),
        "reference": finding.details.get("reference"),
        "kind": finding.details.get("kind"),
        "hook": finding.details.get("hook"),
        "required": finding.details.get("required"),
        "line": finding.details.get("line"),
    }


def script_reference_result(
    tree: PowerTree,
    *,
    scripts_directory: str,
    shipped: Iterable[str] = (),
) -> CheckResult:
    """The recorded result for one produced Power's script and asset references.

    Pure over the tree, the ported script directory, and the release's
    script-side spellings, so *Property 11* drives it directly. An unreadable
    script and an unreadable hook definition are each recorded against
    themselves and the sweep continues, because the rest of the references are
    still owed a verdict.
    """
    release = frozenset(shipped)
    paths = frozenset(tree.paths)
    supplied = supplied_paths(tree.paths)
    scripts = script_paths(tree)
    definitions = hook_definition_paths(tree, hook_definition_glob(tree))

    findings: list[Finding] = []
    references: list[AssetReference] = []
    for path in scripts:
        try:
            text = tree.read_text(path)
        except Unevaluable as error:
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=(
                        f"{error.message}, so the scripts and assets it "
                        "references cannot be resolved"
                    ),
                    target=path,
                )
            )
            continue
        references.extend(
            script_asset_references(text, source=path, shipped=release)
        )

    for definition in definitions:
        try:
            document = tree.read_json(definition)
        except Unevaluable as error:
            findings.append(
                Finding(
                    code=E_CHECK_UNEVALUATED,
                    message=(
                        f"{error.message}, so the ported script its hooks "
                        "invoke cannot be resolved"
                    ),
                    target=definition,
                )
            )
            continue
        references.extend(
            hook_script_references(
                document, definition, scripts_directory=scripts_directory
            )
        )

    dangling = missing_asset_findings(
        references, paths=paths, supplied=supplied
    )
    findings.extend(dangling)

    return CheckResult(
        id="script-references",
        target=SCRIPT_TARGET,
        findings=tuple(findings),
        extra={
            "scriptGlob": SCRIPT_GLOB,
            "scripts": len(scripts),
            "hookDefinitions": list(definitions),
            "scriptsDirectory": scripts_directory,
            "references": len(references),
            "satisfied": len(references) - len(dangling),
            "missing": [_missing_asset_record(finding) for finding in dangling],
        },
    )


@register_check(
    "script-references",
    code=E_MISSING_ASSET,
    target=SCRIPT_TARGET,
    requirement="10.4",
)
def check_script_references(context: ValidationContext) -> CheckResult:
    """Every referenced script and asset exists in the Power *(R10 AC4)*.

    Fails closed on two conditions before a reference is resolved: no contract,
    which is where the ported script directory a hook's script path resolves
    against is declared, and a Power carrying neither a Python module nor a hook
    definition, which is not a Power whose references pass but one whose
    references were never established.
    """
    contract = context.require_contract()
    scripts_directory = ported_scripts_directory(contract)
    tree = context.tree
    if not script_paths(tree) and not hook_definition_paths(
        tree, hook_definition_glob(tree)
    ):
        raise Unevaluable(
            f"the produced Power carries no {SCRIPT_GLOB} file and no hook "
            "definition, so no script or asset reference could be resolved",
            target=SCRIPT_TARGET,
        )
    source = context.source
    return script_reference_result(
        tree,
        scripts_directory=scripts_directory,
        shipped=(
            release_script_assets(source, prefix=_release_prefix(context))
            if source is not None
            else frozenset()
        ),
    )


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------


def _unevaluated(
    check_id: str, code: str, reason: str, *, target: str | None = None
) -> CheckResult:
    """The fail-closed result: no verdict was obtained, so this is a fail."""
    return CheckResult(
        id=check_id,
        target=target,
        findings=(
            Finding(
                code=code,
                message=f"check '{check_id}' could not be evaluated: {reason}",
                target=target,
                details={"unevaluated": True},
            ),
        ),
    )


def _run_one(check: Check, context: ValidationContext) -> tuple[CheckResult, ...]:
    """Run one check, converting any failure to answer into a recorded fail.

    The bare `except` is deliberate. A check that raises has not established a
    pass, and a validator that let an unexpected exception escape would abandon
    the remaining checks and report a prefix of the truth — breaking both
    "report everything" and "fail closed" at once.
    """
    try:
        produced = check.run(context)
    except Unevaluable as error:
        return (
            _unevaluated(
                check.id,
                check.failure_code,
                error.message,
                target=error.target or check.target,
            ),
        )
    except Exception as error:  # noqa: BLE001 - see the docstring
        return (
            _unevaluated(
                check.id,
                check.failure_code,
                f"{type(error).__name__}: {error}",
                target=check.target,
            ),
        )

    results = (produced,) if isinstance(produced, CheckResult) else tuple(produced)
    if not results:
        return (
            _unevaluated(
                check.id,
                check.failure_code,
                "the check produced no result",
                target=check.target,
            ),
        )

    mismatched = [result.id for result in results if result.id != check.id]
    if mismatched:
        return (
            _unevaluated(
                check.id,
                check.failure_code,
                f"the check recorded results under other ids ({', '.join(mismatched)})",
                target=check.target,
            ),
        )

    # A whole-tree check may leave `target` unset; fill in the registered one so
    # the report names what was examined.
    return tuple(
        result
        if result.target is not None or check.target is None
        else CheckResult(
            id=result.id,
            target=check.target,
            findings=result.findings,
            extra=result.extra,
        )
        for result in results
    )


def run_checks(
    context: ValidationContext, *, checks: Sequence[str] | None = None
) -> ValidationReport:
    """Run every check and collect every finding (*Property 15*).

    No early return, no short circuit: a failing check does not stop the run,
    so one report names the full remaining work. `checks` narrows the run to
    named ids — for a focused test, never for a release, since a narrowed run
    omits the checks it did not run and therefore cannot establish the gate.
    """
    results: list[CheckResult] = []
    for check_id in check_order() if checks is None else tuple(checks):
        check = _REGISTRY.get(check_id)
        if check is None:
            results.append(
                _unevaluated(
                    check_id,
                    E_CHECK_UNEVALUATED,
                    "the design declares this check but nothing implements it",
                )
            )
            continue
        results.extend(_run_one(check, context))

    return ValidationReport(
        template_release=context.tag,
        power_version=context.power_version,
        checks=tuple(results),
    )


def _unreadable_staging_report(tag: str, reason: str) -> ValidationReport:
    """Every declared check fails when the produced tree cannot even be read.

    A report is still emitted, because the Maintainer needs the reason and the
    release procedure needs a report that says `tagAllowed: false` rather than
    no report at all.
    """
    return ValidationReport(
        template_release=tag,
        power_version=None,
        checks=tuple(
            _unevaluated(check_id, E_CHECK_UNEVALUATED, reason)
            for check_id in check_order()
        ),
    )


def validate(
    staging: str | Path,
    tag: str,
    *,
    contract: Contract | None = None,
    source: str | Path | None = None,
) -> ValidationReport:
    """Validate a produced Power in `staging` against the resolved `tag`."""
    try:
        tree = PowerTree.from_directory(staging)
    except TransformError as error:
        return _unreadable_staging_report(
            tag, f"the produced Power at {staging} cannot be read: {error.message}"
        )

    source_tree: PowerTree | None = None
    if source is not None:
        try:
            source_tree = PowerTree.from_directory(source)
        except TransformError as error:
            # A missing source blocks only the checks that need it, via
            # `require_source`; it does not invalidate the rest of the run.
            _narrate(
                f"the resolved release tree at {source} cannot be read "
                f"({error.message}); checks needing it will fail closed"
            )

    context = ValidationContext(
        tree=tree,
        tag=tag,
        contract=contract,
        source=source_tree,
        staging=Path(staging),
    )
    return run_checks(context)


def write_report(report: ValidationReport, path: str | Path) -> Path:
    """Write the report as UTF-8 JSON with LF endings and a trailing newline.

    Serialization is fixed (two-space indent, insertion key order, LF) because
    the report is compared across runs and platforms; a serializer that varied
    would manufacture diffs the Build_Manifest check would then report.
    """
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(report.to_json(), indent=2, sort_keys=False) + "\n"
        target.write_text(text, encoding="utf-8", newline="\n")
    except OSError as error:
        raise TransformError(
            E_WRITE_FAILED,
            f"cannot write the validation report to {target}: {error}",
            path=str(target),
        ) from error
    return target


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _narrate(message: str) -> None:
    """Human-readable narration goes to stderr; stdout carries only JSON."""
    print(f"validate: {message}", file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description=(
            "Validate a produced Bootcamp_Power and emit the ValidationReport "
            "that gates tagging. JSON to stdout and to --report, narration to "
            "stderr. Exit 0 only when tagAllowed is true."
        ),
    )
    parser.add_argument(
        "--staging",
        required=True,
        help="the produced Power tree to validate (the staging directory)",
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="resolved Template_Release tag, compared character-for-character",
    )
    parser.add_argument(
        "--report",
        required=True,
        help="path the ValidationReport JSON is written to, pass or fail",
    )
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_CONTRACT),
        help=(
            "path to contract.yaml, source of the Invariant_Discount_Register "
            "and the kiro-owned declarations (default: the contract beside this "
            "script)"
        ),
    )
    parser.add_argument(
        "--source",
        default=None,
        help=(
            "resolved Template_Release tree, for the checks that compare the "
            "Power against the release it was built from"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.tag.strip():
        _narrate("--tag must be a non-empty release tag")
        return EXIT_BLOCKED

    contract: Contract | None = None
    try:
        contract = load_contract(args.contract)
        _narrate(
            f"contract {contract.path} (contractVersion {contract.contract_version})"
        )
    except TransformError as error:
        # Not fatal to the run: the checks that need the contract fail closed
        # through `require_contract`, and the rest still report.
        _narrate(
            f"{error.code}: {error.message}; checks needing the contract will "
            "fail closed"
        )

    report = validate(args.staging, args.tag, contract=contract, source=args.source)

    for check in report.checks:
        where = f" [{check.target}]" if check.target else ""
        _narrate(f"{check.result:>4}  {check.id}{where}")
        for finding in check.findings:
            _narrate(f"        {finding.code}: {finding.message}")
    _narrate(report.summary())

    try:
        written = write_report(report, args.report)
    except TransformError as error:
        _narrate(f"{error.code}: {error.message}")
        json.dump(error.to_json(), sys.stdout, indent=2, sort_keys=False)
        print(file=sys.stdout)
        return EXIT_BLOCKED
    _narrate(f"report written to {written}")

    json.dump(report.to_json(), sys.stdout, indent=2, sort_keys=False)
    print(file=sys.stdout)
    return EXIT_SUCCESS if report.tag_allowed else EXIT_BLOCKED


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
