"""Property-based tests for the bootcamp transform engine's 25 correctness properties.

The design's Testing Strategy fixes this file as the single home for every
property-based test:

- **one property, one test** — each of the 25 correctness properties is
  implemented by exactly one test function;
- every test carries the design's tagging comment,
  ``# Feature: senzing-bootcamp-power, Property N: <title>``;
- every test carries ``@settings(max_examples=100)`` or higher, the floor the
  ``bootcamp`` Hypothesis profile in `conftest.py` also applies by default.

Inputs come from the shared generators in `strategies.py`; this file holds no
generators of its own beyond small local shapes a single property needs.

Layout
------
One banner-delimited section per property, ordered by property number. Each
section owns its imports' usage, its reference oracles, and its single test, so
a property can be read — or added — without touching another one.

Oracles, not restatements
-------------------------
Where a property needs to know the right answer, this file computes it
independently (an ASCII semver regex, an eligibility predicate written from the
acceptance criteria) rather than calling the function under test. A test that
asked the implementation what it expected would pass unconditionally.
"""

from __future__ import annotations

import errno
import hashlib
import itertools
import json
import os
import posixpath
import re
import shlex
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

import transform
from reconcile import (
    ACTION_KEEP,
    ACTION_KEEP_ON_DISK,
    ACTION_REMOVE,
    ACTION_SOURCES,
    ACTION_TAKE_STAGING,
    BUCKET_ADDED,
    BUCKET_CONFLICTS,
    BUCKET_MODIFIED,
    BUCKET_PRESERVED,
    BUCKET_REMOVED,
    BUCKET_UNCHANGED,
    BUCKETS,
    CHANGELOG_FILENAME,
    CONFLICT_RESOLUTION,
    REASON_KIRO_OWNED,
    REASON_LOCAL_DELETE,
    REASON_LOCAL_EDIT,
    REASON_LOCAL_ONLY,
    REPORT_VERSION as RECONCILE_REPORT_VERSION,
    SOURCE_ON_DISK,
    UNCLASSIFIED_PATHS,
    Classification,
    Conflict,
    FileTree,
    ManifestBaseline,
    ReconciliationReport,
    append_changelog_entry,
    apply_report,
    apply_to_staging,
    changelog_entry,
    changelog_provenance,
    classify,
    classify_path,
    entry_recorded,
    reconcile,
    reconcile_directories,
    record_update_in_staging,
    union_paths,
)
from resolve_release import (
    E_ALREADY_CURRENT,
    E_NO_RELEASE,
    ResolutionError,
    eligible_releases,
    is_newer,
    resolve,
    select_release,
)
from strategies import (
    CLAUDE_MODEL_REFERENCES,
    COMMAND_DERIVED_SKILLS,
    DISCOUNTED_INVARIANTS,
    DISCOUNT_REGISTER_CASES,
    FILE_CONTENT_CASES,
    FRONTMATTER_CASES,
    HONORED_INVARIANT,
    HOOK_SCRIPT_NAMES,
    IGNORED_TEMPLATE_PATHS,
    INTERPRETER_PATH_CASES,
    INV_PROSE_CASES,
    MAX_DESCRIPTION_LENGTH as GENERATOR_DESCRIPTION_LIMIT,
    MCP_DOCUMENT_CASES,
    NEAR_MISS_MCP_URLS,
    OUTCOME_SET_CASES,
    PATH_FLAVORS,
    RECONCILE_INTENTS,
    RECONCILE_TRIPLE_CASES,
    RELEASE_LIST_CASES,
    SKILL_TREE_CASES,
    STATEMENT_CASES,
    SUBSTITUTION_SETS,
    TEMPLATE_PLUGIN_ROOT,
    TEMPLATE_TREE_CASES,
    TRIGGER_PHRASES,
    DiscountRegisterCase,
    FailurePoint,
    FileContentCase,
    FrontmatterCase,
    InterpreterPathCase,
    InvProseCase,
    McpDocumentCase,
    OutcomeSet,
    ReconcileTriple,
    SkillTreeCase,
    Substitution,
    TreeEntry,
    discount_register,
    failure_point,
    file_content,
    frontmatter,
    interpreter_path,
    inv_prose,
    mcp_document,
    outcome_set,
    reconcile_triple,
    release_list,
    skill_tree,
    statement,
    template_tree,
)
from testrecord import (
    CHECKLIST_STEP_COUNT,
    DEFAULT_CHECKLIST,
    E_CHECKLIST_INCOMPLETE,
    MATRIX_STEP,
    OUTCOME_FAIL,
    OUTCOME_PASS,
    PER_PLATFORM_STEPS,
    REASON_BLANK_CELL,
    REASON_BLANK_OUTCOME,
    REASON_FAIL,
    REASON_MISSING_CELL,
    REASON_MISSING_STEP,
    REASON_UNRECOGNIZED,
    REASON_VERSION_MISMATCH,
    RECORDS_DIRECTORY,
    RECORD_FORMAT_VERSION,
    SUPPORTED_PLATFORMS,
    ChecklistDefinition,
    default_definition,
    evaluate,
    evaluate_outcomes,
    parse_record,
    read_checklist,
    read_record,
    render_record,
    write_record,
)
from transform import (
    DEFAULT_CONTRACT,
    E_MISSING_ASSET,
    E_TRANSFORM_FAILED,
    E_UNMATCHED_FILE,
    E_WRITE_FAILED,
    EXTENSION_NAMESPACE,
    INVARIANT_CITATION,
    KIRO_OWNED_ROOT,
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    OWNER_KIRO,
    OWNER_TEMPLATE,
    SCRIPT_SUFFIX,
    SKILL_METADATA_FIELD,
    TEMPLATE_RELEASE_FIELD,
    VENDOR_SEGMENT,
    Contract,
    StagingResult,
    TransformError,
    TransformPlan,
    build_plan,
    contained_path,
    discard_staging,
    enumerate_source,
    find_missing_assets,
    invariant_citations,
    load_contract,
    plan_destinations,
    plugin_manifest_context,
    sha256_hex,
    swap_into_place,
    verify_plugin_manifest,
    write_staging,
)
from validate import (
    ASSET_HOOK_SCRIPT,
    ASSET_KINDS,
    ASSET_MODULE,
    ASSET_RELEASE_SHIPPED,
    ASSET_VENDORED,
    BUILD_MANIFEST,
    CLAUDE_ROOT_TOKEN,
    CROSS_REFERENCE_GLOB,
    CROSS_REFERENCE_TARGET,
    DECLARED_CHECKS,
    DECLARED_CLAUDE_TERMS,
    DEFAULT_HOOK_DEFINITION_GLOB,
    DISCOUNT_CONFLICTS_FIELD,
    DISCOUNT_ENTRY_UNUSABLE,
    DISCOUNT_FIELDS,
    DISCOUNT_FIELD_ABSENT,
    DISCOUNT_FIELD_BLANK,
    DISCOUNT_FIELD_UNUSABLE,
    DISCOUNT_HONORED_INVARIANT,
    DISCOUNT_INVARIANT_FIELD,
    DISCOUNT_KINDS,
    DISCOUNT_REGISTER_KEY,
    DISCOUNT_RESOLUTION_FIELD,
    DRIFT_ABSENT,
    DRIFT_CONTENT,
    DRIFT_LINE_ENDINGS,
    DRIFT_UNRECORDED,
    DRIFT_UNUSABLE_RECORD,
    E_BARE_INTERPRETER,
    E_BROKEN_IMPORT,
    E_CHECK_UNEVALUATED,
    E_FRONTMATTER_INVALID,
    E_HASH_MISMATCH,
    E_HONORED_INVARIANT_DISCOUNTED,
    E_INCOMPLETE_DISCOUNT,
    E_INVENTORY_MISMATCH,
    E_MCP_INVALID,
    E_PROGRESSION_MISMATCH,
    E_SCHEMA_INVALID,
    E_SHELL_CONSTRUCT_IN_HOOK,
    E_UNRESOLVED_REFERENCE,
    E_VERSION_MISMATCH,
    EXTENSIONS_FIELD,
    FRONTMATTER_RULES,
    GITATTRIBUTES,
    HONORED_INVARIANT as GATE_HONORED_INVARIANT,
    HOOK_ASSETS_DIRECTORY,
    HOOK_COVERAGE_MAP,
    HOOK_DEFINITION_TARGET,
    HOOK_FILENAME_PREFIX,
    HOOK_INSTALLER_SCRIPT,
    IMPORT_KINDS,
    IMPORT_RELOCATED,
    IMPORT_UNPORTED,
    INSTALLER_PROBES,
    INVENTORY_COMMAND_DUPLICATE,
    INVENTORY_COMMAND_MISSING,
    INVENTORY_COMMAND_STALE,
    INVENTORY_DOUBLE_CLAIM,
    INVENTORY_DUPLICATE,
    INVENTORY_KINDS,
    INVENTORY_MISSING,
    INVENTORY_RELOCATED,
    INVENTORY_STALE,
    INVENTORY_UNACCOUNTED,
    LINE_ENDING_DECLARATION,
    MANIFEST_DRIFT_KINDS,
    MANIFEST_SCHEMAS,
    MANIFEST_UNRECORDED,
    MAX_DESCRIPTION_LENGTH,
    MCP_MANIFEST,
    MCP_SCHEMA_FIELD,
    MCP_SCHEMA_ID,
    MCP_SERVERS_FIELD,
    MCP_TRANSPORT_TYPE,
    MODULE_NAME,
    NORMALIZATION_EXEMPT_PATTERNS,
    ORIGIN_INSTALLED,
    ORIGIN_SHIPPED,
    PACKAGE_MARKER,
    PLUGIN_MANIFEST,
    PLUGIN_SCHEMA_ID,
    POWER_ROOT_TOKEN,
    POWER_VERSION_FIELD,
    PROGRESSION_FIRST_PHASE,
    PROGRESSION_INTERSTITIAL_MISPLACED,
    PROGRESSION_KINDS,
    PROGRESSION_LAST_PHASE,
    PROGRESSION_PHASES_MISDECLARED,
    PROGRESSION_SECTION,
    PROGRESSION_SEQUENCE_DIFFERS,
    PROGRESSION_UNPLACEABLE,
    PROVENANCE_PATH,
    REFERENCE_ABSENT,
    REFERENCE_DIRECTORY,
    REFERENCE_ESCAPES_POWER,
    REFERENCE_KINDS,
    REPORT_VERSION,
    RESIDUAL_CLIENT_NAME,
    RESIDUAL_EFFORT_SETTING,
    RESIDUAL_KINDS,
    RESIDUAL_MODEL_GUIDANCE,
    RESIDUAL_MODEL_NAME,
    RESIDUAL_ROOT_TOKEN,
    RESIDUAL_SUBSCRIPTION_PLAN,
    RESIDUAL_TERM_SETS,
    RESULT_FAIL,
    RESULT_PASS,
    RESULT_WARN,
    SCRIPTS_DIR_PLACEHOLDER,
    SCRIPT_GLOB,
    SCRIPT_TARGET,
    SENZING_MCP_URL,
    SENZING_SERVER_KEY,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SHELL_BUILTINS,
    SKILL_INVENTORY_TARGET,
    SKILL_MANIFEST,
    SKILL_MD_GLOB,
    SKILL_REQUIRED_FIELDS,
    SKILL_TEMPLATE_SKILL_FIELD,
    STATUS_FAILED,
    STATUS_INCOMPLETE,
    STATUS_PASSED,
    TEMPLATE_COMMAND_FIELD,
    TERM_ORIGIN_DECLARED,
    TIER3_HOOKS_DIRECTORY,
    TRIGGER_SOURCE_PRODUCED,
    TRIGGER_SOURCE_TEMPLATE,
    VERSION_COMPARISONS,
    VERSION_ROLE_PROVENANCE,
    VERSION_ROLE_STAMP,
    VERSION_ROLE_TAG,
    VERSION_ROLES,
    W_RESIDUAL_CLAUDE_REF,
    AssetReference,
    CheckResult,
    ClaudeTerm,
    DiscountEntry,
    Finding,
    HookCommand,
    HookCommandTools,
    PowerTree,
    ProgressionPhase,
    ResidualReference,
    ScriptImport,
    SkillFrontmatter,
    SkillProvenance,
    Unevaluable,
    ValidationContext,
    ValidationReport,
    VersionComparison,
    VersionStrings,
    asset_reference_path,
    asset_reference_satisfied,
    blank_code_blocks,
    broken_import_findings,
    check_cross_references,
    check_hook_command_strings,
    check_invariant_discounts,
    check_manifest_hashes,
    check_mcp_schema,
    check_order,
    check_progression_order,
    check_residual_claude_refs,
    check_script_imports,
    check_script_references,
    check_skill_frontmatter,
    check_skill_inventory,
    check_version_match,
    claude_terms,
    command_bijection_findings,
    command_claims,
    command_names,
    command_script_paths,
    compare_manifest,
    contract_claude_terms,
    cross_reference,
    cross_reference_findings,
    declared_discounts,
    declared_trigger_phrase,
    discount_entries,
    discount_register_result,
    document_text,
    fold_status,
    frontmatter_findings,
    honored_invariant_findings,
    hook_command_findings,
    hook_commands,
    hook_definition_glob,
    hook_definition_paths,
    hook_script_references,
    import_resolves,
    incomplete_discount_findings,
    installer_findings,
    interstitial_findings,
    invariant_spelling,
    is_absolute_command_path,
    is_line_ending_rewrite,
    kiro_owned_skill_names,
    load_hook_command_tools,
    markdown_prose,
    markdown_references,
    missing_asset_findings,
    module_key,
    module_providers,
    names_bare_interpreter,
    names_honored_invariant,
    normalization_exempt,
    phase_declaration_findings,
    phase_index,
    port_claims,
    ported_scripts_directory,
    ported_skill_names,
    progression_key,
    progression_phases,
    progression_result,
    progression_sequence,
    read_power_version,
    reference_kind,
    reference_path,
    registered_check,
    release_script_assets,
    release_script_modules,
    residual_claude_result,
    residual_findings,
    residual_references,
    resolve_reference,
    run_checks,
    schema_findings,
    script_asset_references,
    script_import_result,
    script_imports,
    script_paths,
    script_reference_result,
    senzing_declaration_findings,
    sequence_findings,
    shell_builtin_named,
    skill_bijection_findings,
    skill_description_findings,
    skill_directory_name,
    skill_frontmatter_result,
    skill_inventory,
    skill_inventory_result,
    skill_license_findings,
    skill_name_findings,
    skill_names,
    skill_provenance,
    source_prefix,
    strip_command_placeholders,
    supplied_paths,
    unplaceable_findings,
    unplaceable_skills,
    version_comparisons,
    version_match_result,
    version_mismatch_findings,
)


# ===========================================================================
# Property 1: Release selection is the semver-maximum of eligible releases
# ===========================================================================

#: Bare semver, no `v` prefix, matched independently of the resolver's own
#: pattern so the oracle below is a second opinion rather than an echo.
_BARE_SEMVER_RE = re.compile(r"\A(\d+)\.(\d+)\.(\d+)\Z", re.ASCII)

#: Fixed facts, passed explicitly so the resolver under test never has to guess
#: them and the assertions never depend on the contract's current values.
_REPOSITORY = "Senzing/senzing-bootcamp-claude-plugin"
_PLUGIN_ROOT = "plugins/senzing-bootcamp"


def _reference_version(tag: Any) -> tuple[int, ...] | None:
    """Parse `tag` as bare `MAJOR.MINOR.PATCH`, else `None` — the test's oracle."""
    if not isinstance(tag, str):
        return None
    match = _BARE_SEMVER_RE.match(tag.strip())
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _reference_eligible(record: Mapping[str, Any]) -> bool:
    """Whether a release record can be selected, written from R1 AC1 and AC2.

    Eligible means published, not a draft, not a prerelease, and semver-tagged.
    A record that omits `publishedAt` did not report the field at all, which is
    not the same as reporting an unpublished release.
    """
    if record.get("isDraft") or record.get("isPrerelease"):
        return False
    published_at = record.get("publishedAt", "unreported")
    if published_at is None or not str(published_at).strip():
        return False
    return _reference_version(record.get("tagName")) is not None


def _bare_semver() -> st.SearchStrategy[str]:
    """Current-Power version floors for the update path, in `release_list()`'s range.

    The ranges match the tags `release_list()` emits, so a generated floor lands
    below, at, and above the eligible maximum often enough to matter; the
    equality boundary is additionally asserted outright rather than left to luck.
    """
    return st.builds(
        lambda major, minor, patch: f"{major}.{minor}.{patch}",
        st.integers(min_value=0, max_value=12),
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=0, max_value=20),
    )


class _RecordedResolver:
    """`resolve` driven by injected records: no network, no clock, no filesystem.

    `fetches` counts source-tree fetch attempts, which is how the tests observe
    "halts the build without producing any build artifact" *(R1 AC4)*: a halting
    outcome must leave this at zero.
    """

    def __init__(self, records: list[Mapping[str, Any]]) -> None:
        self._records = list(records)
        self.fetches = 0

    def _fetch(self, timeout: float) -> Path:
        self.fetches += 1
        return Path("/nonexistent/bootcamp-src")

    def run(self, min_version: str | None = None) -> dict[str, Any]:
        return resolve(
            out_dir="/nonexistent",
            repository=_REPOSITORY,
            plugin_root=_PLUGIN_ROOT,
            min_version=min_version,
            lister=lambda timeout: self._records,
            fetcher=self._fetch,
            clock=lambda: 0.0,
            sleeper=lambda seconds: None,
        )


# Feature: senzing-bootcamp-power, Property 1: Release selection is the
# semver-maximum of eligible releases
#
# Validates: Requirements 1.1, 1.2, 1.3, 1.4, 5.1
@settings(max_examples=200)
@given(release_list(), _bare_semver())
def test_release_selection_is_the_semver_maximum_of_eligible_releases(
    records: list[Mapping[str, Any]], min_version: str
) -> None:
    eligible = [record for record in records if _reference_eligible(record)]

    # R1 AC1, AC2: the candidate set is the published, non-draft, non-prerelease,
    # semver-tagged subset — on both the initial-build and the update path.
    assert eligible_releases(records) == eligible

    if not eligible:
        # R1 AC4: no selection is emitted, the outcome is E_NO_RELEASE (never
        # E_RESOLVE_FAILED), and nothing is fetched, on either path.
        assert select_release(records) is None
        for floor in (None, min_version):
            resolver = _RecordedResolver(records)
            with pytest.raises(ResolutionError) as raised:
                resolver.run(min_version=floor)
            assert raised.value.code == E_NO_RELEASE
            assert resolver.fetches == 0
        return

    highest = max(_reference_version(record["tagName"]) for record in eligible)

    # R1 AC1, AC2: the selection is the semver maximum — not the lexicographic
    # maximum and not the most recently published release, both of which the
    # generator's cases deliberately point elsewhere.
    selected = select_release(records)
    assert selected in eligible
    assert _reference_version(selected["tagName"]) == highest

    # The maximum is a property of the set, not of the listing order.
    reselected = select_release(list(reversed(records)))
    assert reselected["tagName"] == selected["tagName"]

    resolver = _RecordedResolver(records)
    resolved = resolver.run()
    tag = resolved["tag"]
    assert _reference_version(tag) == highest
    assert resolved["semver"] == list(highest)
    assert "error" not in resolved
    assert resolver.fetches == 1

    # R1 AC3: content is sourced from the resolved tag ref. A branch ref — main
    # above all — is never emitted.
    assert resolved["sourceRef"] == f"refs/tags/{tag}"
    assert "refs/heads/" not in resolved["sourceRef"]
    assert resolved["sourceRef"] not in ("refs/heads/main", "main", "HEAD")

    # R5 AC1: "a newer Template_Release exists" is exactly "the eligible maximum
    # is greater than the current Power version by semver precedence". The
    # canonical spelling of that maximum is the equality boundary, so it is
    # checked outright alongside the generated floor.
    canonical = "{}.{}.{}".format(*highest)
    generated_is_newer = highest > _reference_version(min_version)
    assert is_newer(tag, min_version) is generated_is_newer
    assert is_newer(tag, canonical) is False

    for floor, newer in ((min_version, generated_is_newer), (canonical, False)):
        resolver = _RecordedResolver(records)
        outcome = resolver.run(min_version=floor)
        if newer:
            assert "error" not in outcome
            assert outcome["sourceRef"] == f"refs/tags/{tag}"
            assert resolver.fetches == 1
        else:
            assert outcome.get("error") == E_ALREADY_CURRENT
            assert outcome.get("tag") == tag
            assert resolver.fetches == 0


# ===========================================================================
# Property 2: Version stamp and provenance round trip
# ===========================================================================
#
# One number, written in three places, and R2 is the claim that whoever reads any
# one of them learns the same thing: the resolved tag the build was driven from,
# the `plugin.json` `version` a client displays *(R2 AC1, AC2)*, and the
# provenance at `extensions["com.senzing.bootcamp"].templateRelease` *(R2 AC5)*.
# "Round trip" is therefore two directions, and this property drives both,
# because each one's evidence is only worth what the other's blindness leaves it:
#
# - the **producer**: a real build over a generated tree stamps the resolved tag
#   into both positions character-for-character, and records the provenance
#   *outside* the plugin schema's fixed top-level field set *(R1 AC5, R2 AC1,
#   AC2, AC5)*;
# - the **gate**: the version-match check reports `E_VERSION_MISMATCH` naming
#   both strings on any character-level difference, and withholds permission to
#   tag *(R2 AC3, AC4)*.
#
# Why the schema's blindness is asserted, not assumed
# ---------------------------------------------------
# The vendored Agent Plugins v1.0.0 plugin schema declares `version` as
# `{"type": "string"}`. Any string conforms, so a Power stamped with a release it
# was never built from is schema-valid and requirement-invalid at the same time,
# and the version-match check is the *only* detector. That is asserted rather
# than assumed — the produced document with its `version` replaced by another
# spelling still conforms — so a clause that merely asked "was something
# reported?" cannot let schema conformance stand in for the check under test.
# The same schema is what makes R2 AC5's *outside* half checkable: its top-level
# field set is closed, so a bare top-level `templateRelease` is a conformance
# violation while the identical string under `extensions` is not.
#
# Why the template's own manifest declares the wrong version
# ----------------------------------------------------------
# `template_tree()` ships no `.claude-plugin/plugin.json`, and the `manifest`
# rule produces nothing without its source, so one is planted. It is planted
# declaring the version the Power must *not* carry, which is what makes the
# stamp's provenance observable rather than merely plausible: a stamp equal to
# the resolved tag cannot have been copied from the template, and an engine that
# passed the template's version through would fail here instead of agreeing with
# itself. The rendered document supersedes that file entirely, so nothing else
# about it matters.
#
# Character-for-character, never semver precedence
# ------------------------------------------------
# `0.5.1` and `0.05.1` are one version to a semver comparator and two different
# strings to a tag lookup, a changelog entry, a checkout, and a Bootcamper
# matching a Power against a release page. `release_list()`'s `zero_padded` case
# fixes exactly that pair, and `_zero_padded_twin` generalizes it to whatever tag
# a drawn release list resolves to, so every example carries the case R2 AC3
# turns on. The contrast is made explicit: the resolver's own comparator is asked
# — in both directions — and calls the two equivalent, and the gate still reports
# a mismatch.
#
# Exactly the violating set
# -------------------------
# The check performs two comparisons, both anchored on the Power version, and
# their conjunction is the requirement: stamp against tag, and stamp against
# provenance. So the reported set of pairs is compared against that set computed
# twice, independently:
#
# - `_reference_mismatches` reads the document at the positions the requirement
#   names, spelled as literals here, and applies `==` on `str`. It is an oracle,
#   not a restatement: it never asks the validator what it expected, and a
#   producer-side or gate-side rename cannot move both sides of the comparison at
#   once.
# - `_seeded_mismatches` reads the *construction* — which role holds which token
#   — and never looks at a value at all.
#
# Their equality is the biconditional, and the positions a mismatch is reported
# at (`version`, `extensions.com.senzing.bootcamp.templateRelease`) are literals
# too, because they are what a Maintainer reads to find the string at fault.
# Every shape puts something that is not a string somewhere, or the same string
# everywhere, so the two-absent-fields case — where a missing guard would let a
# Power recording no version at all report a match — is covered outright.
#
# Deliberately out of scope: *which* release is resolved is Property 1's, and
# what a blocked run leaves on the filesystem is Property 6's. R2 AC4's second
# half needs no clause of its own — the gate only reads, and the produced tree is
# asserted byte-identical after both runs over it.
#
# `_transformable`, `_materialized_release`, and `_read_tree` are shared with the
# sections below; Python resolves them when the test runs, so the sections stay
# in property order.

#: The `release_list()` case that fixes the two spellings of one version, and the
#: spellings it fixes. Drawn outright below as well as through `release_list()`,
#: so the pair is in every example rather than only in the examples that draw it.
_REQUIRED_RELEASE_LIST_CASES = frozenset({"zero_padded"})
_ZERO_PADDED_SPELLINGS = ("0.5.1", "0.05.1")

#: The Template_Plugin document the `manifest` rule supersedes, and that rule's
#: id. Planted in the generated tree, because a `generate` rule with no matched
#: source produces no output and there would be nothing to gate.
_TEMPLATE_MANIFEST_SOURCE = ".claude-plugin/plugin.json"
_MANIFEST_RULE_ID = "manifest"

#: The check this property drives.
_VERSION_CHECK_ID = "version-match"

#: Where the two recorded strings live, spelled as R2 spells them rather than
#: imported, and asserted equal to the engine's and the gate's own constants.
_VERSION_FIELD = "version"
_MANIFEST_EXTENSIONS_FIELD = "extensions"
_BOOTCAMP_NAMESPACE = "com.senzing.bootcamp"
_PROVENANCE_FIELD = "templateRelease"
_PROVENANCE_POSITION = (
    _MANIFEST_EXTENSIONS_FIELD,
    _BOOTCAMP_NAMESPACE,
    _PROVENANCE_FIELD,
)

#: The three strings by role, and the two comparisons performed over them, in
#: report order. Literals for the same reason as the positions above.
_ROLE_TAG = "resolvedTag"
_ROLE_STAMP = "powerVersion"
_ROLE_PROVENANCE = "templateRelease"
_ROLE_NAMES = (_ROLE_TAG, _ROLE_STAMP, _ROLE_PROVENANCE)
_COMPARED_PAIRS = (
    (_ROLE_STAMP, _ROLE_TAG),
    (_ROLE_STAMP, _ROLE_PROVENANCE),
)

#: The manifest position each mismatch must point at — what a Maintainer edits to
#: settle that pair. The stamp-against-tag pair points at the stamp because the
#: tag is an input to the run rather than a field of the artifact.
_STAMP_LOCATION = "version"
_PROVENANCE_LOCATION = "extensions.com.senzing.bootcamp.templateRelease"
_PAIR_LOCATIONS: Mapping[tuple[str, str], str] = {
    (_ROLE_STAMP, _ROLE_TAG): _STAMP_LOCATION,
    (_ROLE_STAMP, _ROLE_PROVENANCE): _PROVENANCE_LOCATION,
}

#: How one role's string is recorded. Only the first two put a string where the
#: gate reads; every other token leaves that position holding something that is
#: not a string, which R2 AC3 makes a mismatch rather than something to coerce
#: and then compare.
_HOLDS_THE_TAG = "the tag"
_HOLDS_THE_VARIANT = "the variant"
_FIELD_ABSENT = "no field"
_HOLDS_NULL = "a null"
_HOLDS_A_NUMBER = "a number"
_AT_THE_TOP_LEVEL = "at the top level"
_UNDER_ANOTHER_NAMESPACE = "under another namespace"
_NAMESPACE_NOT_AN_OBJECT = "a namespace that is not an object"
_NO_EXTENSIONS_OBJECT = "no extensions object"
_DOCUMENT_NOT_AN_OBJECT = "a document that is not an object"

#: The two tokens that record a string, and are therefore comparable at all.
_STRING_TOKENS = frozenset({_HOLDS_THE_TAG, _HOLDS_THE_VARIANT})

#: A version-shaped value that is not a version string. A manifest carrying it
#: declares no version at all, which is not the same as declaring a matching one.
_NUMERIC_VERSION = 0.51

#: A second reverse-domain namespace: a legal place for a client to keep its own
#: data, and not the place this provenance is read from.
_ANOTHER_NAMESPACE = "com.example.other"

#: A check that found nothing, standing in for the rest of a passing run. With it
#: in the report, a withheld tag can only have come from `version-match`.
_PASSING_PLUGIN_SCHEMA_SIBLING = CheckResult(id="plugin-schema", target=PLUGIN_MANIFEST)


@dataclass(frozen=True)
class _ManifestShape:
    """One `plugin.json` to gate, described by where each string is recorded.

    The shape is the construction rather than the values: `stamp` and
    `provenance` name tokens, and the tag and the variant are supplied per
    example. That is what lets `_seeded_mismatches` compute the expected
    mismatches without looking at a string, and so be independent of the oracle
    that reads the document.
    """

    name: str
    stamp: str
    provenance: str


#: Every way a manifest can record — or fail to record — the two strings. The
#: table covers all four possible outcomes over the two declared comparisons,
#: which the test asserts rather than assumes.
_MANIFEST_SHAPES = (
    _ManifestShape("agrees-everywhere", _HOLDS_THE_TAG, _HOLDS_THE_TAG),
    # The stamp is the odd one out, so *both* comparisons fail: a Power agreeing
    # with neither the tag nor its own provenance names both rather than the
    # first one found.
    _ManifestShape("stamp-is-the-variant", _HOLDS_THE_VARIANT, _HOLDS_THE_TAG),
    _ManifestShape("provenance-is-the-variant", _HOLDS_THE_TAG, _HOLDS_THE_VARIANT),
    # Self-consistent and wrong: the artifact agrees with itself and disagrees
    # with the release it was built from.
    _ManifestShape("both-are-the-variant", _HOLDS_THE_VARIANT, _HOLDS_THE_VARIANT),
    _ManifestShape("stamp-absent", _FIELD_ABSENT, _HOLDS_THE_TAG),
    _ManifestShape("stamp-is-null", _HOLDS_NULL, _HOLDS_THE_TAG),
    _ManifestShape("stamp-is-a-number", _HOLDS_A_NUMBER, _HOLDS_THE_TAG),
    _ManifestShape("provenance-absent", _HOLDS_THE_TAG, _FIELD_ABSENT),
    _ManifestShape("provenance-is-null", _HOLDS_THE_TAG, _HOLDS_NULL),
    # R2 AC5's *outside* half, from the other side: recorded at the top level is
    # recorded where nothing reads it.
    _ManifestShape("provenance-at-the-top-level", _HOLDS_THE_TAG, _AT_THE_TOP_LEVEL),
    _ManifestShape(
        "provenance-under-another-namespace", _HOLDS_THE_TAG, _UNDER_ANOTHER_NAMESPACE
    ),
    _ManifestShape(
        "namespace-is-not-an-object", _HOLDS_THE_TAG, _NAMESPACE_NOT_AN_OBJECT
    ),
    _ManifestShape("no-extensions-object", _HOLDS_THE_TAG, _NO_EXTENSIONS_OBJECT),
    # Neither string is recorded. Two positions holding nothing must not compare
    # equal, or a Power declaring no version at all would report a match.
    _ManifestShape("neither-is-recorded", _FIELD_ABSENT, _FIELD_ABSENT),
    _ManifestShape(
        "document-is-not-an-object", _DOCUMENT_NOT_AN_OBJECT, _DOCUMENT_NOT_AN_OBJECT
    ),
)


def _zero_padded_twin(tag: str) -> str:
    """`tag` with a leading zero on its minor component: same version, new string.

    The generalization of `release_list()`'s `zero_padded` case to whatever tag a
    drawn release list resolves to. Asserted against that case's literal pair in
    the test, so the two cannot drift apart.
    """
    major, minor, patch = tag.split(".")
    return f"{major}.0{minor}.{patch}"


def _template_manifest(version: str) -> TreeEntry:
    """A Template_Plugin `plugin.json` declaring `version` — the wrong string."""
    document = {"name": "senzing-bootcamp", _VERSION_FIELD: version}
    return TreeEntry("file", (json.dumps(document, indent=2) + "\n").encode("utf-8"))


def _value_at(document: Any, path: Sequence[str]) -> Any:
    """The value at `path`, or `None` where the path does not lead to one."""
    value: Any = document
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _built_manifest(shape: _ManifestShape, tag: str, variant: str) -> Any:
    """The parsed `plugin.json` `shape` describes, over one tag and one variant."""
    if shape.stamp == _DOCUMENT_NOT_AN_OBJECT:
        return [tag]

    recorded = {
        _HOLDS_THE_TAG: tag,
        _HOLDS_THE_VARIANT: variant,
        _HOLDS_NULL: None,
        _HOLDS_A_NUMBER: _NUMERIC_VERSION,
    }
    document: dict[str, Any] = {"name": "senzing-bootcamp"}
    if shape.stamp != _FIELD_ABSENT:
        document[_VERSION_FIELD] = recorded[shape.stamp]

    if shape.provenance in recorded:
        namespace: Any = {_PROVENANCE_FIELD: recorded[shape.provenance]}
    elif shape.provenance == _FIELD_ABSENT:
        namespace = {}
    elif shape.provenance == _AT_THE_TOP_LEVEL:
        document[_PROVENANCE_FIELD] = tag
        namespace = {}
    elif shape.provenance == _NAMESPACE_NOT_AN_OBJECT:
        namespace = tag
    elif shape.provenance == _UNDER_ANOTHER_NAMESPACE:
        document[_MANIFEST_EXTENSIONS_FIELD] = {
            _ANOTHER_NAMESPACE: {_PROVENANCE_FIELD: tag}
        }
        return document
    elif shape.provenance == _NO_EXTENSIONS_OBJECT:
        return document
    else:
        raise AssertionError(f"unhandled provenance token: {shape.provenance}")

    document[_MANIFEST_EXTENSIONS_FIELD] = {_BOOTCAMP_NAMESPACE: namespace}
    return document


def _seeded_mismatches(shape: _ManifestShape) -> frozenset[tuple[str, str]]:
    """The comparisons `shape` must fail, read off its construction.

    Decidable without looking at a value: the tag role always holds the tag, and
    two string tokens are the same string exactly when they are the same token —
    the test asserts the variant differs from the tag, which is what makes
    `_HOLDS_THE_VARIANT` against `_HOLDS_THE_TAG` a mismatch.
    """
    tokens = {
        _ROLE_TAG: _HOLDS_THE_TAG,
        _ROLE_STAMP: shape.stamp,
        _ROLE_PROVENANCE: shape.provenance,
    }
    return frozenset(
        (left, right)
        for left, right in _COMPARED_PAIRS
        if not (
            tokens[left] in _STRING_TOKENS
            and tokens[right] in _STRING_TOKENS
            and tokens[left] == tokens[right]
        )
    )


def _reference_mismatches(document: Any, tag: str) -> frozenset[tuple[str, str]]:
    """The same set, read out of the document at the positions R2 names.

    `==` on `str`, never semver precedence *(R2 AC3)*, and two positions holding
    no string are not equal: a manifest recording no version has not been shown
    to match the tag.
    """
    found = _reference_strings(document, tag)
    return frozenset(
        (left, right)
        for left, right in _COMPARED_PAIRS
        if not (
            isinstance(found[left], str)
            and isinstance(found[right], str)
            and found[left] == found[right]
        )
    )


def _reference_strings(document: Any, tag: str) -> dict[str, Any]:
    """The three strings by role, exactly as the document records them.

    Raw: an absent field is `None` and a number stays a number, because R2 AC3
    asks the finding to identify what the Power declares rather than a
    normalization of it.
    """
    return {
        _ROLE_TAG: tag,
        _ROLE_STAMP: _value_at(document, (_VERSION_FIELD,)),
        _ROLE_PROVENANCE: _value_at(document, _PROVENANCE_POSITION),
    }


def _spelled_version(value: Any) -> str:
    """The spelling of one value a finding's message must contain.

    `repr` for a value that is there — the quoted string, or the number a manifest
    recorded instead of one — and `absent` for one that is not. R2 AC3's
    "identifies both" is not met by a message a Maintainer cannot read the two
    strings out of.
    """
    return "absent" if value is None else repr(value)


def _plugin_conformance(document: Any) -> tuple[Any, ...]:
    """Schema violations of `document`, under the code the `plugin.json` check uses."""
    return schema_findings(
        document,
        MANIFEST_SCHEMAS[PLUGIN_MANIFEST],
        target=PLUGIN_MANIFEST,
        code=E_SCHEMA_INVALID,
    )


def _assert_gate_reports_exactly(
    document: Any, tag: str, required: frozenset[tuple[str, str]]
) -> CheckResult:
    """Drive the version-match gate over one manifest and one resolved tag.

    Asserts the reported mismatches are exactly `required` — no more, no fewer —
    that each finding names both strings it compared, and that the recorded result
    and the derived `tagAllowed` follow from that and nothing else. Returns the
    recorded result so a caller can make its own further claim about it.
    """
    before = deepcopy(document)
    found = _reference_strings(document, tag)
    matched = required == frozenset()

    versions = VersionStrings.read(document, tag)
    assert versions.tag == tag
    assert versions.details() == found
    for role, value in found.items():
        assert versions.value(role) == value
    assert versions.matched is matched
    if matched:
        # Two comparisons, three strings: stamp equals tag and stamp equals
        # provenance means provenance equals tag, which is why a third pair would
        # only restate an inequality one of these two already reported.
        assert found[_ROLE_PROVENANCE] == found[_ROLE_STAMP] == tag

    # Both declared comparisons are performed, in report order, whatever an
    # earlier one found.
    comparisons = version_comparisons(versions)
    assert tuple((pair.left, pair.right) for pair in comparisons) == _COMPARED_PAIRS
    for comparison in comparisons:
        assert isinstance(comparison, VersionComparison)
        pair = (comparison.left, comparison.right)
        assert comparison.left_value == found[comparison.left]
        assert comparison.right_value == found[comparison.right]
        assert comparison.identical is (pair not in required)
        assert comparison.location == _PAIR_LOCATIONS[pair]
        assert comparison.details() == {
            "compared": [comparison.left, comparison.right],
            "left": comparison.left_value,
            "right": comparison.right_value,
        }

    # R2 AC3: exactly the mismatching pairs, each reported once, in report order.
    findings = version_mismatch_findings(versions)
    reported = tuple(tuple(finding.details["compared"]) for finding in findings)
    assert len(set(reported)) == len(reported)
    assert frozenset(reported) == required
    assert reported == tuple(pair for pair in _COMPARED_PAIRS if pair in required)

    for finding in findings:
        pair = tuple(finding.details["compared"])
        assert finding.code == E_VERSION_MISMATCH
        assert finding.severity == SEVERITY_ERROR
        assert finding.target == PLUGIN_MANIFEST
        assert finding.location == _PAIR_LOCATIONS[pair]
        # R2 AC3: both strings, in the message as prose and in `details` as data,
        # each named by the role it plays so a reader can tell them apart.
        for role in pair:
            assert _spelled_version(found[role]) in finding.message
        assert finding.details["left"] == found[pair[0]]
        assert finding.details["right"] == found[pair[1]]
        assert {role: finding.details[role] for role in _ROLE_NAMES} == found
        payload = finding.to_json()
        assert payload["code"] == E_VERSION_MISMATCH
        assert payload["target"] == PLUGIN_MANIFEST
        assert payload["location"] == finding.location
        assert payload["severity"] == SEVERITY_ERROR

    result = version_match_result(document, tag)
    assert result.id == _VERSION_CHECK_ID
    assert result.findings == findings
    assert result.result == (RESULT_PASS if matched else RESULT_FAIL)
    assert result.passed is matched
    # The file examined and the position the provenance is read from, named in the
    # payload a Maintainer reads rather than left to the message.
    assert result.extra["manifest"] == PLUGIN_MANIFEST
    assert result.extra["provenanceField"] == _PROVENANCE_LOCATION
    assert {role: result.extra[role] for role in _ROLE_NAMES} == found
    assert result.extra["compared"] == len(_COMPARED_PAIRS)
    assert result.extra["mismatches"] == [
        {
            "compared": list(pair),
            "left": found[pair[0]],
            "right": found[pair[1]],
            "location": _PAIR_LOCATIONS[pair],
        }
        for pair in _COMPARED_PAIRS
        if pair in required
    ]

    # The same result after a JSON round trip, through the check's own reader: the
    # shape a produced `plugin.json` actually reaches the gate in.
    tree = PowerTree.from_mapping(
        {PLUGIN_MANIFEST: json.dumps(document, indent=2) + "\n"}
    )
    context = ValidationContext(tree=tree, tag=tag)
    recorded = check_version_match(context)
    # One recorded result for the one manifest, never several: the check adds only
    # the read to the pure function above.
    assert isinstance(recorded, CheckResult)
    assert recorded == result
    # A function of the tree and the tag alone, and it changes neither.
    assert check_version_match(context) == recorded
    assert version_match_result(document, tag) == result
    assert document == before

    # The stamp is stated at the top of the report whatever the check found, and
    # an unreadable one is `None` there rather than a pass.
    stamp = found[_ROLE_STAMP]
    assert read_power_version(tree) == (stamp if isinstance(stamp, str) else None)

    # R2 AC4: an error-severity finding makes the result a fail, a failing result
    # makes the status `failed`, and `tagAllowed` is the biconditional over that —
    # beside a sibling result that passed, so a withheld tag can only have come
    # from this check.
    report = ValidationReport(
        template_release=tag,
        power_version=read_power_version(tree),
        checks=(_PASSING_PLUGIN_SCHEMA_SIBLING, recorded),
    )
    assert _PASSING_PLUGIN_SCHEMA_SIBLING.passed
    assert report.status == (STATUS_PASSED if matched else STATUS_FAILED)
    assert report.tag_allowed is matched
    assert report.findings_for(E_VERSION_MISMATCH) == findings
    assert report.failed_check_ids() == (() if matched else (_VERSION_CHECK_ID,))
    return result


# Feature: senzing-bootcamp-power, Property 2: Version stamp and provenance
# round trip
#
# Validates: Requirements 1.5, 2.1, 2.2, 2.3, 2.4, 2.5
@settings(max_examples=100)
@given(template_tree(), release_list(), RELEASE_LIST_CASES["zero_padded"])
def test_version_stamp_and_provenance_round_trip(
    tree: Mapping[str, TreeEntry],
    records: list[Mapping[str, Any]],
    zero_padded: list[Mapping[str, Any]],
) -> None:
    # The generator case this property draws from, asserted rather than assumed.
    assert _REQUIRED_RELEASE_LIST_CASES <= set(RELEASE_LIST_CASES)

    # R2 AC1, AC5: the field names, the namespace key, and the roles the
    # requirement fixes are the ones the engine writes and the gate reads —
    # `validate` imports the namespace and the field from `transform`, so producer
    # and gate cannot disagree about where the provenance sits.
    assert POWER_VERSION_FIELD == _VERSION_FIELD
    assert EXTENSIONS_FIELD == _MANIFEST_EXTENSIONS_FIELD
    assert EXTENSION_NAMESPACE == _BOOTCAMP_NAMESPACE
    assert TEMPLATE_RELEASE_FIELD == _PROVENANCE_FIELD
    assert PROVENANCE_PATH == _PROVENANCE_POSITION
    assert (VERSION_ROLE_TAG, VERSION_ROLE_STAMP, VERSION_ROLE_PROVENANCE) == (
        _ROLE_TAG,
        _ROLE_STAMP,
        _ROLE_PROVENANCE,
    )
    assert VERSION_ROLES == _ROLE_NAMES
    assert VERSION_COMPARISONS == _COMPARED_PAIRS

    # R2 AC3, AC4: the gate this property drives, and the code it raises.
    registered = registered_check(_VERSION_CHECK_ID)
    assert registered is not None
    assert registered.code == E_VERSION_MISMATCH

    # --- The two spellings of one version ----------------------------------
    spellings = tuple(record["tagName"] for record in zero_padded)
    assert set(spellings) == set(_ZERO_PADDED_SPELLINGS)
    assert _zero_padded_twin(_ZERO_PADDED_SPELLINGS[0]) == _ZERO_PADDED_SPELLINGS[1]

    # R1 AC5: the resolved tag is the string the resolver recorded, and it is what
    # every artifact below is stamped from. *Which* release that is belongs to
    # Property 1; when the drawn list has no eligible release — also Property 1's
    # subject — the canonical zero-padded spelling stands in, so the producer
    # clause runs in every example.
    selected = select_release(records)
    tag = _ZERO_PADDED_SPELLINGS[0] if selected is None else selected["tagName"]
    twin = _zero_padded_twin(tag)

    # The case R2 AC3 turns on: the resolver's own comparator, asked both ways,
    # calls these two the same version, and they are still different strings.
    assert twin != tag
    assert is_newer(tag, twin) is False
    assert is_newer(twin, tag) is False

    # --- The producer: one real build, stamped from the resolved tag --------
    contract = load_contract()
    rule = contract.classify(_TEMPLATE_MANIFEST_SOURCE).rule
    assert rule is not None
    assert (rule.id, rule.kind, rule.dest) == (
        _MANIFEST_RULE_ID,
        "generate",
        (PLUGIN_MANIFEST,),
    )

    source_tree = {
        **_transformable(tree, contract),
        _TEMPLATE_MANIFEST_SOURCE: _template_manifest(twin),
    }

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source, _ = _materialized_release(root, source_tree, "release")
        staging = root / "staging"

        plan = build_plan(contract, source, tag=tag, staging=staging)
        # R1 AC5: the recorded tag reaches the render context as the identical
        # string — nothing normalizes it on the way in.
        assert plan.tag == tag
        assert plugin_manifest_context(plan)["tag"] == tag

        outputs, _ = plan_destinations(plan)
        stamped = [output for output in outputs if output.path == PLUGIN_MANIFEST]
        assert len(stamped) == 1
        assert stamped[0].rule.id == _MANIFEST_RULE_ID
        assert (
            stamped[0].source_path
            == f"{TEMPLATE_PLUGIN_ROOT}/{_TEMPLATE_MANIFEST_SOURCE}"
        )

        write_staging(plan)
        staged = _read_tree(staging)
        assert PLUGIN_MANIFEST in staged
        data = staged[PLUGIN_MANIFEST]
        document = json.loads(data.decode("utf-8"))

        # R2 AC1, AC2: the stamp is the resolved tag, character-for-character —
        # and it came from the resolved release rather than from the template,
        # whose own document declares the twin.
        assert document[_VERSION_FIELD] == tag
        template_document = json.loads(
            source_tree[_TEMPLATE_MANIFEST_SOURCE].content.decode("utf-8")
        )
        assert template_document[_VERSION_FIELD] == twin
        assert document[_VERSION_FIELD] != twin

        # R2 AC5: the same string, recorded under the reverse-domain namespace
        # key...
        assert _value_at(document, _PROVENANCE_POSITION) == tag
        # ...and outside the schema's fixed top-level field set, which really is
        # fixed: the produced document conforms, and the identical string added at
        # the top level does not.
        assert _plugin_conformance(document) == ()
        assert _PROVENANCE_FIELD not in document
        at_top_level = _plugin_conformance({**document, _PROVENANCE_FIELD: tag})
        assert any(
            finding.details.get("rule") == "additionalProperties"
            for finding in at_top_level
        )

        # The engine's own second opinion accepts what it rendered and refuses it
        # against any other tag, so the producer side is character-exact before
        # the gate ever sees the artifact. Returning at all is the acceptance: the
        # verifier's only other outcome is a raise.
        verify_plugin_manifest(data, plan)
        twin_plan = build_plan(
            contract, source, tag=twin, staging=root / "staging-twin"
        )
        with pytest.raises(TransformError) as raised:
            verify_plugin_manifest(data, twin_plan)
        assert raised.value.code == E_TRANSFORM_FAILED
        assert repr(tag) in raised.value.message
        assert repr(twin) in raised.value.message

        # --- The gate, over the Power that was just produced ---------------
        # The produced tree is what the gate reads, so the check is run over it as
        # well as over the parsed document: the result the artifact earns is the
        # result the assertions above are about.
        power = PowerTree.from_mapping(staged)
        assert read_power_version(power) == tag
        passing = _assert_gate_reports_exactly(document, tag, frozenset())
        assert check_version_match(ValidationContext(tree=power, tag=tag)) == passing
        assert passing.findings == ()

        # R2 AC3, AC4: the same Power against the zero-padded twin — the same
        # version by precedence, a different string — is a mismatch on the stamp
        # that withholds permission to tag.
        blocked = _assert_gate_reports_exactly(
            document, twin, frozenset({(_ROLE_STAMP, _ROLE_TAG)})
        )
        assert check_version_match(ValidationContext(tree=power, tag=twin)) == blocked
        assert len(blocked.findings) == 1

        # The plugin schema declares `version` as any string, so a Power stamped
        # with a release it was not built from conforms perfectly: this check is
        # the only thing between a Bootcamper and that Power.
        misstamped = {**document, _VERSION_FIELD: twin}
        assert _plugin_conformance(misstamped) == ()
        _assert_gate_reports_exactly(misstamped, tag, frozenset(_COMPARED_PAIRS))

        # R2 AC4: the gate only reads, so the produced tree — its version stamp
        # and its provenance among it — is byte-identical after every run above.
        assert _read_tree(staging) == staged

    # --- The gate, over every way a manifest can record the two strings ----
    # Non-vacuous by construction: the shapes cover all four outcomes over the
    # two declared comparisons, the agreeing one included.
    assert {_seeded_mismatches(shape) for shape in _MANIFEST_SHAPES} == {
        frozenset(),
        frozenset({(_ROLE_STAMP, _ROLE_TAG)}),
        frozenset({(_ROLE_STAMP, _ROLE_PROVENANCE)}),
        frozenset(_COMPARED_PAIRS),
    }

    # Pairs of version strings that are not character-for-character identical: the
    # generator's literal zero-padded pair, the resolved tag against its own twin,
    # a `v` prefix, and two distinct drawn tags where the list holds them.
    pairs = [spellings, (tag, twin), (tag, f"v{tag}")]
    drawn = tuple(dict.fromkeys(record["tagName"] for record in records))
    if len(drawn) >= 2:
        pairs.append((drawn[0], drawn[1]))

    for resolved, variant in pairs:
        assert resolved != variant
        for shape in _MANIFEST_SHAPES:
            built = _built_manifest(shape, resolved, variant)
            required = _seeded_mismatches(shape)
            # The two oracles agree — one read the construction, one read the
            # document — and the gate reports exactly what they name.
            assert _reference_mismatches(built, resolved) == required, shape.name
            _assert_gate_reports_exactly(built, resolved, required)

    # A Power whose `plugin.json` cannot be read has not been shown to match the
    # tag, so the check declines rather than passing: there is no path here to a
    # pass without a manifest to read.
    with pytest.raises(Unevaluable):
        check_version_match(
            ValidationContext(
                tree=PowerTree.from_mapping({MCP_MANIFEST: "{}\n"}), tag=tag
            )
        )


# ===========================================================================
# Property 3: Create and update produce identical output, and the contract is
# the only lever
# ===========================================================================
#
# R3 AC1 makes the contract single-sourced, AC2 and AC3 make both maintainer
# skills apply it, AC4 makes it the only place a rule change lives, and AC5 with
# R5 AC3 make the two paths agree byte-for-byte. That is one mechanism seen from
# five sides, and the mechanism is that **the two paths differ in exactly one
# argument**: the create path calls `build_plan` with no `carry_forward`, the
# update path passes the existing Power. The contract, the source tree, and the
# resolved tag are the same values on both. So the property is two claims, each
# about a difference:
#
# 1. **The difference the paths do have produces none in the output.** Build the
#    Power on the create path, publish it, then run the same contract over the
#    same source with `carry_forward` set to that Power — the update path, which
#    takes `kiro-owned` content from the Power rather than from
#    `templates/kiro-owned/` *(R5 AC5)* — and the two trees carry the identical
#    file set and identical bytes at every path, `.build-manifest.json` included
#    *(R3 AC5, R5 AC3)*. The manifest is the sharp part of that comparison: it
#    records a rule id, an owner, and a content hash per output, so two paths
#    that happened to agree on bytes while disposing of a file through different
#    rules would still differ here — which is how a byte comparison becomes
#    evidence that both paths executed the *same* contract *(R3 AC2, AC3)*.
#
# 2. **A difference in the contract produces the same difference in both.**
#    Mutate one rule and both paths' outputs change, change into the same tree,
#    and change only where that rule reaches, with `contract.yaml` the only input
#    that differed *(R3 AC4)*.
#
# Why the mutation is a `dest`
# ----------------------------
# Clause 2 is worthless if the mutation is a no-op — a test whose "the output
# changed" assertion can pass on an unchanged tree measures nothing — so the
# mutation has to bite on *every* generated tree. A `substitutions` list change
# does not: whether dropping `plugin-root` from `scripts-owned` shows up depends
# on whether the generated scripts happen to carry `${CLAUDE_PLUGIN_ROOT}`, and
# `template_tree()`'s `empty_file` case can leave a tree whose only script is
# empty. A `dest` change is observable from the output *path set* alone, so it
# bites on content that is always there: the at-least-one `scripts/*.py` and the
# `scripts/vendor/d3.v7.min.js` asset every generated tree carries, and the
# authored `kiro-owned` tree, which materializes whatever the template did or did
# not supply because it has no template source. The three mutations below are one
# per flavor of rule the engine has to move — a `substitute` rule's template
# output, a `copy` rule's byte-exact output, and a `kiro-owned` rule with no
# template source at all — because those three reach the output through
# different code and a lever that moved only one of them would be a false pass.
#
# The mutation is written to a **copy** of the contract in the example's
# temporary directory; `contract.yaml` is read and never written. "The contract
# was the only modified input" is then checked as three facts about the four
# runs rather than as a byte comparison of repository files across the test's own
# runtime — a comparison that would report a Maintainer editing `templates/` in
# another window as a transform defect: all four runs were handed the same source
# directory, byte-identical to its pre-run snapshot; all four carried the same
# resolved tag; and the two contracts differ in exactly one rule and in nothing
# else.
#
# `_materialized_release`, `_transformable`, `_read_tree`, `_staged_facts`,
# `_entries_outside`, and `_RESOLVED_TAG` are shared with the sections below;
# Python resolves them when the test runs, so the sections stay in property
# order.


@dataclass(frozen=True)
class _DestMutation:
    """One single-rule contract mutation: `rule_id`'s `dest` becomes `dests`.

    `old` is the single `dest` the rule declares in the committed contract,
    stated here rather than read from it: the test asserts the rule still
    declares exactly that, so a contract edit that moved the rule fails loudly
    instead of quietly turning the mutation into a no-op.
    """

    name: str
    rule_id: str
    old: str
    dests: tuple[str, ...]


#: The single-rule mutations, one per flavor of rule that reaches the output.
#: Every replacement directory name is longer than the 8 characters `_slug()`
#: emits, so no generated source path can collide with a relocated destination
#: and turn a mutation into a write conflict instead of a relocation.
_DEST_MUTATIONS = (
    # A `substitute` rule: ported scripts, rewritten text, always at least one.
    _DestMutation(
        name="relocate-ported-scripts",
        rule_id="scripts-owned",
        old="skills/bootcamp-onboarding/scripts/",
        dests=("skills/bootcamp-onboarding/ported-scripts/",),
    ),
    # A `copy` rule: the vendored asset, byte-for-byte, always present.
    _DestMutation(
        name="relocate-vendored-assets",
        rule_id="scripts-vendor",
        old="skills/bootcamp-onboarding/scripts/vendor/",
        dests=("skills/bootcamp-onboarding/scripts/vendored-third-party/",),
    ),
    # A `kiro-owned` rule, given a second destination: no template source, and
    # the added `dest` ships no authored content of its own, so it mirrors the
    # one that does — the same shape `kiro-hooks` uses for Tier 3.
    _DestMutation(
        name="mirror-enforcement-setup",
        rule_id="enforcement-setup-skill",
        old="skills/bootcamp-enforcement-setup/",
        dests=(
            "skills/bootcamp-enforcement-setup/",
            "dev.kiro/skills/bootcamp-enforcement-setup/",
        ),
    ),
)


def _mutated_contract(base: Contract, mutation: _DestMutation, path: Path) -> Contract:
    """Write `base`'s document with one rule's `dest` changed, and load the copy.

    A copy at `path`, produced from the parsed document rather than by editing
    text, so the only thing that can differ is the field named here.
    `contract.yaml` is not touched.
    """
    document = deepcopy(dict(base.raw))
    rules = [dict(entry) for entry in document["rules"]]
    mutated = [entry for entry in rules if entry["id"] == mutation.rule_id]
    assert len(mutated) == 1, mutation.rule_id
    mutated[0]["dest"] = list(mutation.dests)
    document["rules"] = rules
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=10**6),
        encoding="utf-8",
    )
    return load_contract(path)


def _differing_rule_ids(
    base: Mapping[str, Any], mutated: Mapping[str, Any]
) -> tuple[str, ...]:
    """Rule ids whose contract entry differs, asserting nothing else does.

    The claim behind R3 AC4 is that one rule changed and the rest of the
    contract — every other section, the rule set's membership, and its declared
    order — did not, so those are asserted here rather than left implied by the
    output comparison.
    """
    assert set(mutated) == set(base)
    for section in sorted(set(base) - {"rules"}):
        assert mutated[section] == base[section], section

    base_rules = {entry["id"]: entry for entry in base["rules"]}
    mutated_rules = {entry["id"]: entry for entry in mutated["rules"]}
    assert [entry["id"] for entry in mutated["rules"]] == list(base_rules)
    return tuple(
        rule_id
        for rule_id in base_rules
        if mutated_rules[rule_id] != base_rules[rule_id]
    )


def _paths_of_rule(result: StagingResult, rule_id: str) -> frozenset[str]:
    """Output paths one rule produced, read from the staged manifest rows."""
    return frozenset(
        output.path for output in result.outputs if output.rule_id == rule_id
    )


def _relocated(paths: Iterable[str], mutation: _DestMutation) -> frozenset[str]:
    """Where `mutation` says the rule's outputs land, computed here.

    Derived from the contract's own `dest` semantics — a directory `dest`
    receives the source's sub-structure below it — rather than read back from the
    plan, so a plan that relocated content somewhere else would fail here
    instead of agreeing with itself.
    """
    relocated: set[str] = set()
    for path in paths:
        assert path.startswith(mutation.old), path
        remainder = path[len(mutation.old) :]
        relocated.update(dest + remainder for dest in mutation.dests)
    return frozenset(relocated)


def _tree_difference(
    before: Mapping[str, bytes], after: Mapping[str, bytes]
) -> dict[str, tuple[str | None, str | None]]:
    """Every path whose bytes differ between two trees, both sides hashed.

    Hashed rather than carried as bytes so a failure reads as a list of changed
    paths instead of a wall of file contents; equality of the hash mapping is
    equality of the change.
    """
    return {
        path: (
            None if path not in before else sha256_hex(before[path]),
            None if path not in after else sha256_hex(after[path]),
        )
        for path in sorted(set(before) | set(after))
        if before.get(path) != after.get(path)
    }


def _kiro_owned_origins(plan: TransformPlan) -> frozenset[Path]:
    """The base each `kiro-owned` output's bytes are taken from.

    How the test observes that the update path really is the update path: on the
    create path this is `templates/kiro-owned/`, on the update path it is the
    Power being carried forward *(R5 AC5)*. Without it, an update run that
    silently ignored `carry_forward` would produce the identical tree clause 1
    asks for and the comparison would prove nothing.
    """
    outputs, _ = plan_destinations(plan)
    return frozenset(
        output.origin_root for output in outputs if output.owner == OWNER_KIRO
    )


# Feature: senzing-bootcamp-power, Property 3: Create and update produce
# identical output, and the contract is the only lever
#
# Validates: Requirements 3.2, 3.3, 3.4, 3.5, 5.3
@settings(max_examples=100)
@given(template_tree(), st.sampled_from(_DEST_MUTATIONS))
def test_create_and_update_produce_identical_output(
    tree: Mapping[str, TreeEntry], mutation: _DestMutation
) -> None:
    contract = load_contract()
    source_tree = _transformable(tree, contract)

    # The committed contract is what the mutation is stated against, and the
    # engine's default is the contract both maintainer skills invoke *(R3 AC1)*.
    assert contract.path == DEFAULT_CONTRACT
    assert contract.rule(mutation.rule_id).dest == (mutation.old,)

    # Non-vacuous by construction: every generated tree carries a SKILL.md, a
    # script, a vendored asset, and the ignored paths. Asserted rather than
    # assumed, so a generator change that emptied the input would fail here
    # instead of passing silently.
    assert len(source_tree) >= 4

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source, _ = _materialized_release(root, source_tree, "release")
        # A snapshot of the source tree, taken with the helper that records
        # symlinks rather than following them, since a generated tree may carry
        # one. Compared again after all four runs: the template content each run
        # read is the same content, so a difference between their outputs cannot
        # be attributed to it.
        source_before = _entries_outside(source)
        assert source_before

        power = root / "powers" / "senzing-bootcamp"

        # --- Clause 1a: the create path, then publish ----------------------
        create_staging = root / "staging-create"
        create_plan = build_plan(
            contract, source, tag=_RESOLVED_TAG, staging=create_staging
        )
        assert create_plan.carry_forward is None
        assert _kiro_owned_origins(create_plan) == {KIRO_OWNED_ROOT}
        create = write_staging(create_plan)
        create_tree = _read_tree(create_staging)

        # Both flavors of content are in the comparison ahead: files a template
        # rule produced, and `kiro-owned` files the template never supplied,
        # which are the only ones the two paths source differently *(R5 AC5)*.
        assert any(output.source_path is not None for output in create.outputs)
        assert any(output.owner == OWNER_KIRO for output in create.outputs)
        assert MANIFEST_FILENAME in create_tree

        swap_into_place(create_staging, power)
        assert _read_tree(power) == create_tree

        # --- Clause 1b: the update path over that Power --------------------
        # The same contract object, the same source directory, the same tag. The
        # one argument that differs is `carry_forward`.
        update_staging = root / "staging-update"
        update_plan = build_plan(
            contract,
            source,
            tag=_RESOLVED_TAG,
            staging=update_staging,
            carry_forward=power,
        )
        assert update_plan.carry_forward == power
        assert update_plan.contract is create_plan.contract
        assert update_plan.to_json()["contract"] == str(contract.path)
        # The update path genuinely took `kiro-owned` content from the Power.
        assert _kiro_owned_origins(update_plan) == {power}
        update = write_staging(update_plan)
        update_tree = _read_tree(update_staging)

        # R3 AC5, R5 AC3: the identical file set, and identical bytes at every
        # path — the Build_Manifest among them, so the rule id, the owner, and
        # the content hash recorded for each output agree too *(R3 AC2, AC3)*.
        assert set(update_tree) == set(create_tree)
        for path in sorted(create_tree):
            assert update_tree[path] == create_tree[path], path
        assert update_tree[MANIFEST_FILENAME] == create_tree[MANIFEST_FILENAME]
        assert (
            update.manifest.serialize()
            == create.manifest.serialize()
            == create_tree[MANIFEST_FILENAME]
        )
        assert _staged_facts(update) == _staged_facts(create)
        assert update.unmaterialized == create.unmaterialized
        # Publishing the update leaves the Power holding exactly those bytes.
        swap_into_place(update_staging, power)
        assert _read_tree(power) == create_tree

        # --- Clause 2: one mutated rule, in a copy of the contract ---------
        mutated_path = root / "contract-with-one-mutated-rule.yaml"
        mutated_contract = _mutated_contract(contract, mutation, mutated_path)

        # R3 AC4: exactly one rule differs, the difference is the declared one,
        # and it is a real change rather than the value already there.
        assert _differing_rule_ids(contract.raw, mutated_contract.raw) == (
            mutation.rule_id,
        )
        assert mutated_contract.rule(mutation.rule_id).dest == mutation.dests
        assert contract.rule(mutation.rule_id).dest != mutation.dests

        mutated_create_staging = root / "staging-create-mutated"
        mutated_create = write_staging(
            build_plan(
                mutated_contract,
                source,
                tag=_RESOLVED_TAG,
                staging=mutated_create_staging,
            )
        )
        mutated_create_tree = _read_tree(mutated_create_staging)

        # The update path a Maintainer actually has after a rule change: the
        # Power on disk was built by the previous contract.
        mutated_update_staging = root / "staging-update-mutated"
        mutated_update_plan = build_plan(
            mutated_contract,
            source,
            tag=_RESOLVED_TAG,
            staging=mutated_update_staging,
            carry_forward=power,
        )
        assert mutated_update_plan.to_json()["contract"] == str(mutated_path)
        mutated_update = write_staging(mutated_update_plan)
        mutated_update_tree = _read_tree(mutated_update_staging)

        # Both paths still agree with each other under the mutated contract.
        assert set(mutated_update_tree) == set(mutated_create_tree)
        for path in sorted(mutated_create_tree):
            assert mutated_update_tree[path] == mutated_create_tree[path], path
        assert _staged_facts(mutated_update) == _staged_facts(mutated_create)

        # R3 AC4: both paths changed, and changed identically.
        create_change = _tree_difference(create_tree, mutated_create_tree)
        update_change = _tree_difference(update_tree, mutated_update_tree)
        assert create_change == update_change

        # The change is the one the mutated rule declares, and it is not a no-op:
        # the rule produced output before the mutation and that output moved.
        before_paths = _paths_of_rule(create, mutation.rule_id)
        after_paths = _paths_of_rule(mutated_create, mutation.rule_id)
        assert before_paths, mutation.rule_id
        assert after_paths != before_paths
        assert after_paths == _relocated(before_paths, mutation)
        assert _paths_of_rule(mutated_update, mutation.rule_id) == after_paths
        assert set(create_change) - {MANIFEST_FILENAME}

        # ...and it reaches nothing else: every output no longer claimed by the
        # mutated rule is byte-identical on both sides of the mutation. The
        # manifest is excluded because it records the paths that moved, so it
        # changes by construction whenever the rule's outputs do.
        untouched_before = {
            path: data
            for path, data in create_tree.items()
            if path != MANIFEST_FILENAME and path not in before_paths
        }
        untouched_after = {
            path: data
            for path, data in mutated_create_tree.items()
            if path != MANIFEST_FILENAME and path not in after_paths
        }
        assert untouched_after == untouched_before

        # R3 AC4: the contract was the only input that differed. All four runs
        # were handed the same source tree — the same directory, byte-identical
        # to its pre-run snapshot — and the same resolved tag; the authored
        # `kiro-owned` tree they read is the one `KIRO_OWNED_ROOT` names, which
        # the origin checks above already established; and the mutated document
        # is a copy inside this example's temporary directory, so `contract.yaml`
        # was never a write target.
        assert _entries_outside(source) == source_before
        for plan in (
            create_plan,
            update_plan,
            mutated_create.plan,
            mutated_update_plan,
        ):
            assert plan.plugin_root_path == create_plan.plugin_root_path
            assert plan.tag == _RESOLVED_TAG
        assert mutated_path != contract.path
        assert mutated_path.parent == root


# ===========================================================================
# Property 4: Transformation is deterministic and idempotent
# ===========================================================================
#
# R3 AC5 is why the engine is data-driven code rather than prose an agent
# follows, so determinism is the guarantee everything else in Artifact B rests
# on: the create/update equivalence *(Property 3)*, the Build_Manifest hashes
# *(R16 AC9)*, and the golden-tree regression check all reduce to it. Four
# clauses, each aimed at a different way a build stops being a function of its
# input:
#
# 1. **Two runs agree.** The same `(contract, source, tag)` staged twice — in
#    different directories, at different wall-clock instants — yields the same
#    path set, the same bytes at every path, and a byte-identical
#    `.build-manifest.json`.
# 2. **Order does not matter.** The second run materializes its source tree in
#    reverse creation order and hands `build_plan` a *shuffled* enumeration, so
#    an output that depended on either the filesystem's iteration order or the
#    caller's would diverge here.
# 3. **A completed build is a fixed point.** Swapping a staged tree into place
#    and building the same input again — the update path, taking `kiro-owned`
#    content from the Power just written rather than from `templates/` —
#    reproduces that Power byte-for-byte, and swapping the result in leaves the
#    target unchanged. That is "transforming an already-transformed output
#    through the same contract leaves it unchanged" stated over the real
#    artifact rather than over a re-fed tree.
# 4. **Nothing volatile leaks.** Clause 1 catches any value that changes
#    between two instants microseconds apart; a clock read at day or second
#    granularity would survive it, so the volatile-token scan below covers that
#    separately, and the manifest's key set is pinned so a `generatedAt`- or
#    `runId`-shaped field cannot appear at all.
#
# Input trees are filtered to what the contract claims: an unmatched path halts
# the run with `E_UNMATCHED_FILE` and a halted run has no output tree to
# compare, which is Property 5's subject rather than this one's. The filter asks
# the contract, not Property 5's oracle — *which* files are ported is not this
# property's business, only that the same input yields the same bytes.
#
# `_materialize`, `_stays_inside_plugin_root`, and `_RESOLVED_TAG` are shared
# with Property 5's section below; Python resolves them when the test runs, so
# the sections stay in property order.

#: Token shapes a leaked clock or run identifier would take. Deliberately all
#: hyphen- or colon-bearing: a SHA-256 hex digest carries neither, so the
#: manifest's own hashes cannot trip these by coincidence, which a bare
#: digit-run pattern would do routinely.
_VOLATILE_PATTERNS: Mapping[str, re.Pattern[bytes]] = {
    "iso-date": re.compile(rb"\d{4}-\d{2}-\d{2}"),
    "clock-time": re.compile(rb"\d{2}:\d{2}:\d{2}"),
    "uuid": re.compile(
        rb"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        rb"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    ),
}

#: The Build_Manifest's complete key set, top level and per file. Pinned exactly:
#: a build stamp is the obvious thing to add to a manifest and the one thing that
#: would make every hash comparison a false "modified" *(R16 AC9)*.
_MANIFEST_KEYS = frozenset(
    {"manifestVersion", "templateRelease", "contractVersion", "files"}
)
_MANIFEST_FILE_KEYS = frozenset({"path", "ruleId", "owner", "sourcePath", "sha256"})


def _transformable(
    tree: Mapping[str, TreeEntry], contract: Contract
) -> dict[str, TreeEntry]:
    """The entries of `tree` a run can actually complete over.

    Two exclusions, both for the same reason — the excluded entry has no output
    to compare: a path that escapes the plugin root is never written there at
    all, and a path the contract claims with neither a rule nor an ignore entry
    halts the run before any output exists *(R3 AC6)*.
    """
    return {
        path: entry
        for path, entry in tree.items()
        if _stays_inside_plugin_root(path)
        and contract.classify(path).disposition != "unmatched"
    }


def _materialize_in_reverse(
    tree: Mapping[str, TreeEntry], plugin_root: Path
) -> tuple[str, ...]:
    """`_materialize`, writing in reverse order rather than sorted order.

    A variant rather than a parameter on the shared helper: sorted creation
    order is what every other property wants, and clause 2 needs the opposite
    to have any force. Directories therefore come into existence in a different
    sequence too, which is the part `os.walk`'s sorting has to absorb.
    """
    written: list[str] = []
    for path in sorted(tree, reverse=True):
        if not _stays_inside_plugin_root(path):
            continue
        entry = tree[path]
        absolute = plugin_root.joinpath(*path.split("/"))
        absolute.parent.mkdir(parents=True, exist_ok=True)
        if entry.kind == "symlink":
            assert entry.target is not None, path
            os.symlink(entry.target, absolute)
        else:
            absolute.write_bytes(entry.content)
        written.append(path)
    return tuple(sorted(written))


def _read_tree(root: Path) -> dict[str, bytes]:
    """Every regular file under `root`, keyed by relative POSIX path.

    The unit of comparison for clauses 1 and 3: a tree's identity is its path
    set plus the bytes at each path, so this reads bytes rather than hashes and
    compares them directly, and a symlink in a produced tree is a failure rather
    than something to follow.
    """
    contents: dict[str, bytes] = {}
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        subdirectories.sort()
        filenames.sort()
        for name in filenames:
            absolute = Path(directory) / name
            relative = absolute.relative_to(root).as_posix()
            assert not absolute.is_symlink(), relative
            contents[relative] = absolute.read_bytes()
    return contents


def _staged_facts(result: StagingResult) -> tuple[tuple[Any, ...], ...]:
    """The `StagingResult` rows, in the order the engine wrote them.

    Compared as a sequence, not a set: the write order is what the manifest
    order follows, and the manifest's bytes are only a function of the input if
    that order is too.
    """
    return tuple(
        (
            output.path,
            output.rule_id,
            output.owner,
            output.source_path,
            output.sha256,
            output.size,
        )
        for output in result.outputs
    )


@lru_cache(maxsize=4)
def _authored_corpus(contract_path: Path) -> bytes:
    """Bytes and relative paths of every non-template input the engine reads.

    The authored `kiro-owned` tree and the contract itself: content the engine
    materializes or reads values out of, so a volatile-shaped token appearing in
    an output *because a maintainer wrote it there* is accounted for rather than
    reported as a leak.
    """
    parts: list[bytes] = []
    for directory, subdirectories, filenames in os.walk(
        KIRO_OWNED_ROOT, followlinks=False
    ):
        subdirectories.sort()
        filenames.sort()
        for name in filenames:
            absolute = Path(directory) / name
            parts.append(absolute.relative_to(KIRO_OWNED_ROOT).as_posix().encode())
            parts.append(absolute.read_bytes())
    parts.append(Path(contract_path).read_bytes())
    return b"\n".join(parts)


def _input_corpus(tree: Mapping[str, TreeEntry], contract_path: Path) -> bytes:
    """Everything a produced byte is allowed to have come from.

    The source tree's contents, its path spellings (which the manifest records
    and destinations are built from), the authored `kiro-owned` content, the
    contract, and the resolved tag. A volatile-shaped token in an output that is
    absent from all of that came from somewhere else — a clock, a run
    identifier, an environment — which is exactly what R3 AC5 forbids.
    """
    parts: list[bytes] = [_authored_corpus(contract_path)]
    for path in sorted(tree):
        entry = tree[path]
        parts.append(path.encode("utf-8"))
        parts.append(entry.content)
        if entry.target is not None:
            parts.append(entry.target.encode("utf-8"))
    parts.append(_RESOLVED_TAG.encode("ascii"))
    return b"\n".join(parts)


def _volatile_tokens(data: bytes) -> tuple[tuple[str, bytes], ...]:
    """Every clock- or identifier-shaped token in `data`, with its shape's name."""
    return tuple(
        (kind, match.group(0))
        for kind, pattern in _VOLATILE_PATTERNS.items()
        for match in pattern.finditer(data)
    )


# Feature: senzing-bootcamp-power, Property 4: Transformation is deterministic
# and idempotent
#
# Validates: Requirements 3.5
@settings(max_examples=100)
@given(template_tree(), st.randoms(use_true_random=False))
def test_transformation_is_deterministic_and_idempotent(
    tree: Mapping[str, TreeEntry], shuffler: Any
) -> None:
    contract = load_contract()
    source_tree = _transformable(tree, contract)

    # Non-vacuous by construction: every generated tree carries a SKILL.md, a
    # script, a vendored asset, and the ignored paths, none of which the filter
    # above removes. Asserted rather than assumed, so a generator change that
    # emptied the input would fail here instead of passing silently.
    assert len(source_tree) >= 4

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        # --- Run 1: the create path, sorted enumeration --------------------
        first_source = root / "release"
        first_plugin_root = first_source.joinpath(*TEMPLATE_PLUGIN_ROOT.split("/"))
        first_plugin_root.mkdir(parents=True)
        assert _materialize(source_tree, first_plugin_root) == tuple(
            sorted(source_tree)
        )

        first_staging = root / "staging"
        first = write_staging(
            build_plan(
                contract, first_source, tag=_RESOLVED_TAG, staging=first_staging
            )
        )
        first_tree = _read_tree(first_staging)

        # The tree is a real one and the comparison ahead has both flavors of
        # content in it: files a template rule produced and `kiro-owned` files
        # the template never supplied *(R5 AC5)*.
        assert any(output.source_path is not None for output in first.outputs)
        assert any(output.owner == "kiro" for output in first.outputs)
        assert MANIFEST_FILENAME in first_tree
        assert [output.path for output in first.outputs] == sorted(
            path for path in first_tree if path != MANIFEST_FILENAME
        )

        # --- Run 2: same input, different location, reversed and shuffled ---
        second_source = root / "a-differently-named-release-directory"
        second_plugin_root = second_source.joinpath(*TEMPLATE_PLUGIN_ROOT.split("/"))
        second_plugin_root.mkdir(parents=True)
        assert _materialize_in_reverse(source_tree, second_plugin_root) == tuple(
            sorted(source_tree)
        )

        shuffled = list(enumerate_source(second_source, contract.plugin_root))
        shuffler.shuffle(shuffled)
        second_staging = root / "staging-for-the-second-run"
        second = write_staging(
            build_plan(
                contract,
                second_source,
                tag=_RESOLVED_TAG,
                staging=second_staging,
                files=shuffled,
            )
        )
        second_tree = _read_tree(second_staging)

        # --- Clause 1 and 2: the two runs are byte-identical ---------------
        assert set(second_tree) == set(first_tree)
        for path in sorted(first_tree):
            assert second_tree[path] == first_tree[path], path
        assert second_tree[MANIFEST_FILENAME] == first_tree[MANIFEST_FILENAME]
        assert (
            second.manifest.serialize()
            == first.manifest.serialize()
            == first_tree[MANIFEST_FILENAME]
        )
        assert _staged_facts(second) == _staged_facts(first)
        assert second.unmaterialized == first.unmaterialized

        # --- Clause 4: the manifest records content, never the run ---------
        manifest = json.loads(first_tree[MANIFEST_FILENAME])
        assert set(manifest) == _MANIFEST_KEYS
        assert manifest["templateRelease"] == _RESOLVED_TAG
        assert [row["path"] for row in manifest["files"]] == sorted(
            path for path in first_tree if path != MANIFEST_FILENAME
        )
        for row in manifest["files"]:
            assert set(row) == _MANIFEST_FILE_KEYS
            # The hash is of the file as written, which is what the drift check
            # compares a checked-out file against *(R16 AC9)*.
            assert row["sha256"] == sha256_hex(first_tree[row["path"]]), row["path"]

        corpus = _input_corpus(source_tree, contract.path)
        for path, data in sorted(first_tree.items()):
            for kind, token in _volatile_tokens(data):
                assert token in corpus, (path, kind, token)
            # No run-specific absolute path either: both runs' directories live
            # under this one, and neither may reach an output byte.
            assert temporary.encode("utf-8") not in data, path

        # --- Clause 3: a completed build is a fixed point ------------------
        target = root / "powers" / "senzing-bootcamp"
        swap_into_place(first_staging, target)
        assert not first_staging.exists()
        assert _read_tree(target) == first_tree

        # The update path: `kiro-owned` content now comes from the Power itself
        # rather than from `templates/kiro-owned/`, and the result has to be the
        # same Power.
        third_staging = root / "staging-for-the-third-run"
        third = write_staging(
            build_plan(
                contract,
                first_source,
                tag=_RESOLVED_TAG,
                staging=third_staging,
                carry_forward=target,
            )
        )
        assert _read_tree(third_staging) == first_tree
        assert _staged_facts(third) == _staged_facts(first)
        assert third.unmaterialized == first.unmaterialized
        # Nothing has touched the Power yet: staging is the only thing written.
        assert _read_tree(target) == first_tree

        swap_into_place(third_staging, target)
        assert not third_staging.exists()
        assert _read_tree(target) == first_tree


# ===========================================================================
# Property 5: The rule set totally covers the input, and nothing is silently
# dropped
# ===========================================================================
#
# Three clauses, and they need different amounts of machinery:
#
# 1. **Totality and uniqueness of the disposition** is a statement about paths,
#    not about files, so it is checked by classifying every generated path
#    string. That is deliberate: `template_tree()` emits `..` segments and
#    absolute-looking spellings, and a path like `docs/../../../etc/passwd`
#    written to disk lands *outside* the plugin root, where `os.walk` never
#    yields it back as a relative path. Classifying the strings covers those
#    paths honestly instead of losing them.
# 2. **Halting on an unmatched path** needs a real tree, because the claim is
#    about the *absence* of an output tree afterwards.
# 3. **Every documentation and reference asset reaching a mapped destination**
#    needs a real tree too, and is checked against destinations this file
#    derives itself.
#
# Only the entries whose paths stay inside the plugin root are materialized; the
# assertions over the tree are therefore stated against what was actually
# written, which the enumeration check below pins down first.

#: The release tag the plan is built for. Property 5 says nothing about version
#: stamping, so any resolved tag serves and this one is fixed.
_RESOLVED_TAG = "0.5.1"

#: Skill directories the Bootcamp_Power ports *(R7 AC1, AC2, R8)*. The numbered
#: modules are a name shape rather than a fixed list, `module-03b`-style
#: interstitials included.
_PORTED_SKILL_DIRS = frozenset(
    {"bootcamp-onboarding", "bootcamp-preparation", "graduation"}
)
_MODULE_SKILL_PREFIX = "module-"

#: Top-level template directories whose whole subtree the Power ports: scripts
#: and their sibling assets *(R10 AC1, AC3)*, documentation and its reference
#: assets *(R12 AC1)*.
_PORTED_SUBTREES = frozenset({"scripts", "docs"})

#: Template documents the generated Agent Plugins manifests supersede *(R4 AC2,
#: AC3, R11 AC1)*. They are claimed by a rule, so they are never reported as
#: unrecognized new content.
_SUPERSEDED_MANIFESTS = frozenset({".claude-plugin/plugin.json", ".mcp.json"})

#: How `Contract.classify` spells each reference disposition. `superseded` and
#: `port` are both "a rule claims this"; they differ only in whether that rule
#: emits anything.
_CLASSIFIED_AS = {
    "ignore": "ignore",
    "port": "rule",
    "superseded": "rule",
    "unmatched": "unmatched",
}

#: Windows drive-letter prefix. A template file *named* `C:\...` is absolute
#: regardless of the host running the transform, so it can never be written
#: inside the plugin root.
_DRIVE_LETTER_RE = re.compile(r"\A[A-Za-z]:")


def _is_ported_skill_dir(name: str) -> bool:
    return name in _PORTED_SKILL_DIRS or name.startswith(_MODULE_SKILL_PREFIX)


def _reference_disposition(path: str) -> str:
    """How the contract must dispose of `path`, written from the requirements.

    The test's oracle, and deliberately not a second copy of the contract's
    globs: it names the content shapes the acceptance criteria say the
    Bootcamp_Power carries — ported skills *(R7, R8)*, ported scripts and their
    assets *(R10)*, ported documentation and reference assets *(R12 AC1)*, the
    superseded command markdown *(R9 AC1)*, the superseded template manifests
    *(R4, R11)* — plus the paths matched and deliberately not ported. Anything
    else is genuinely new upstream content and must halt the run *(R3 AC6)*.

    Four outcomes: `ignore` (an ignore entry claims it), `port` (exactly one
    rule claims it and that rule emits output), `superseded` (exactly one rule
    claims it and emits nothing), `unmatched` (nothing claims it).
    """
    if path in IGNORED_TEMPLATE_PATHS:
        return "ignore"

    segments = path.split("/")
    if (
        segments[0] == "skills"
        and len(segments) >= 3
        and _is_ported_skill_dir(segments[1])
    ):
        return "port"
    if segments[0] in _PORTED_SUBTREES and len(segments) >= 2:
        return "port"
    if segments[0] == "commands" and len(segments) == 2 and path.endswith(".md"):
        return "superseded"
    if path in _SUPERSEDED_MANIFESTS:
        return "port"
    return "unmatched"


def _is_documentation_or_reference_asset(path: str) -> bool:
    """Whether `path` is a documentation example or a reference asset *(R12 AC1)*.

    Both flavors the template carries: everything under `docs/` — prose, the
    example recap PDF, the truth-set images — and the `references/` material a
    skill directory owns.
    """
    segments = path.split("/")
    if segments[0] == "docs" and len(segments) >= 2:
        return True
    return len(segments) >= 4 and segments[0] == "skills" and segments[2] == "references"


def _mapped_destination(path: str) -> str:
    """Where a documentation or reference asset is retained, derived here.

    R12 AC1 retains each asset as an embedded asset, and R8 AC1 keeps skill
    directory names byte-identical, so a documentation or reference asset keeps
    its own relative spelling in the Power. Computed rather than read back from
    the plan, so a plan that relocated an asset would fail rather than agree
    with itself.
    """
    return path


def _stays_inside_plugin_root(path: str) -> bool:
    """Whether writing `path` under the plugin root lands inside it.

    A path that escapes is not skipped because it is uninteresting — it is
    covered by clause 1 above, and its containment is Property 7's subject —
    but because `os.walk` over the plugin root cannot yield it back, so a tree
    containing one would not be the tree the assertions describe.
    """
    if path.startswith(("/", "\\")) or _DRIVE_LETTER_RE.match(path):
        return False
    return not any(
        segment in ("", ".", "..") for segment in path.replace("\\", "/").split("/")
    )


def _materialize(tree: Mapping[str, TreeEntry], plugin_root: Path) -> tuple[str, ...]:
    """Write the in-root entries of `tree` under `plugin_root`, sorted.

    Returns the paths actually written, which is what every tree-level
    assertion is stated against.
    """
    written: list[str] = []
    for path in sorted(tree):
        if not _stays_inside_plugin_root(path):
            continue
        entry = tree[path]
        absolute = plugin_root.joinpath(*path.split("/"))
        absolute.parent.mkdir(parents=True, exist_ok=True)
        if entry.kind == "symlink":
            assert entry.target is not None, path
            os.symlink(entry.target, absolute)
        else:
            absolute.write_bytes(entry.content)
        written.append(path)
    return tuple(written)


# Feature: senzing-bootcamp-power, Property 5: The rule set totally covers the
# input, and nothing is silently dropped
#
# Validates: Requirements 3.6, 12.1
@settings(max_examples=100)
@given(template_tree())
def test_total_rule_coverage(tree: Mapping[str, TreeEntry]) -> None:
    contract = load_contract()

    # --- Clause 1: one disposition per path, and a rule match is unique -----
    for path in tree:
        expected = _reference_disposition(path)
        match = contract.classify(path)
        assert match.disposition == _CLASSIFIED_AS[expected], path

        claimed = contract.rules_for(path)
        ignored_by = contract.ignore_pattern_for(path)

        # The rule set and the ignore set are authored disjoint, so no path is
        # disposed of twice and none needs a tie-break.
        assert not (claimed and ignored_by is not None), path

        if match.disposition == "rule":
            # "Matched by exactly one contract rule" — an overlap is a contract
            # defect, and picking a winner by declaration order would bury it.
            assert len(claimed) == 1, path
            assert match.rule is claimed[0]
        elif match.disposition == "ignore":
            assert ignored_by is not None
            assert match.pattern == ignored_by
        else:
            assert claimed == ()
            assert ignored_by is None

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "release"
        plugin_root = source.joinpath(*TEMPLATE_PLUGIN_ROOT.split("/"))
        plugin_root.mkdir(parents=True)
        staging = root / "staging"

        materialized = _materialize(tree, plugin_root)
        expected = {path: _reference_disposition(path) for path in materialized}
        unmatched = sorted(
            path for path, disposition in expected.items() if disposition == "unmatched"
        )

        # The tree on disk is the tree the rest of this test talks about.
        assert [
            entry.path for entry in enumerate_source(source, contract.plugin_root)
        ] == sorted(materialized)

        if unmatched:
            # --- Clause 2: halt, name the exact paths, produce no output ----
            with pytest.raises(TransformError) as raised:
                build_plan(contract, source, tag=_RESOLVED_TAG, staging=staging)

            error = raised.value
            assert error.code == E_UNMATCHED_FILE
            # R3 AC6: the error identifies the unmatched file — every one of
            # them, as data and in the message, not just the first.
            assert error.details["unmatched"] == unmatched
            assert error.details["path"] == unmatched[0]
            assert error.details["pluginRoot"] == contract.plugin_root
            for path in unmatched:
                assert path in error.message, path

            # No output tree at all, not merely none for the offending file:
            # matching completes before any output directory is touched.
            assert not staging.exists()
            assert sorted(entry.name for entry in root.iterdir()) == ["release"]
            return

        # --- Nothing silently dropped between enumeration and the plan ------
        plan = build_plan(contract, source, tag=_RESOLVED_TAG, staging=staging)
        matched = {planned.source.path for planned in plan.files}
        ignored = {entry.source.path for entry in plan.ignored}

        assert matched.isdisjoint(ignored)
        assert matched | ignored == set(materialized)
        assert plan.enumerated_count == len(materialized)
        assert ignored == {
            path for path, disposition in expected.items() if disposition == "ignore"
        }
        assert matched == {
            path
            for path, disposition in expected.items()
            if disposition in ("port", "superseded")
        }

        ported = {
            path for path, disposition in expected.items() if disposition == "port"
        }
        assert {planned.source.path for planned in plan.outputs} == ported

        # --- Nothing silently dropped between the plan and the staging tree --
        result = write_staging(plan)
        staged = {output.path for output in result.outputs}

        # Every ported source contributes at least one output carrying its own
        # provenance, so a matched file cannot vanish on the way to disk.
        assert {
            output.source_path
            for output in result.outputs
            if output.source_path is not None
        } == {f"{TEMPLATE_PLUGIN_ROOT}/{path}" for path in ported}

        # --- Clause 3: every documentation and reference asset is retained ---
        # R12 AC1's disjunction — an embedded asset *or* a named reference link
        # — reduces to the embedded branch here: the contract ports every
        # `docs/` and `references/` asset outright, and the generated documents
        # carry no links, so nothing is retained by mention alone.
        for path in sorted(ported):
            if not _is_documentation_or_reference_asset(path):
                continue
            destination = _mapped_destination(path)
            assert destination in staged, path
            assert (staging / destination).is_file(), path


# ===========================================================================
# Property 6: Failure leaves the target byte-identical
# ===========================================================================
#
# The property is a pair of absences, and absences are what a generated input set
# is good at breaking: after a halted run there is nothing new at the target and
# nothing left in staging. Both halves are checked against each of the two prior
# states the target can be in, because the two paths guarantee different things:
#
# * **The target does not exist** — the create path *(R4 AC7, AC8)*. "Byte-
#   identical to its prior state" reads as "still absent", so a run that left an
#   empty target directory, or a partially populated one, fails here.
# * **The target holds a prior Power** — the update path *(R5 AC2, AC7)*. The
#   prior Power is built from a *different* release tag than the faulted run's, so
#   the two trees differ in bytes and a single leaked write is visible rather than
#   coincidentally invisible. The faulted run takes that tree as its
#   `carry_forward`, which is what an update does, so the tree the run reads from
#   is also the tree it must not touch.
#
# Faults are injected by wrapping the engine's own seams — the staged-write
# helper, the file handle it opens, the rename the swap performs — never by
# editing the engine and never by the test mutating the target itself. Each seam
# is handed a *condition* (an `EACCES`, an `ENOTDIR`, an escaping destination, a
# missing staging tree) and the code that surfaces is the engine's own mapping of
# that condition, so the code assertion is a second opinion rather than an echo:
#
#   stage                    kind               injected at            code from
#   ---------------------------------------------------------------------------
#   mid-write                generic            escaping destination   containment
#   mid-write                permission-denied  the file handle        write mapping
#   mid-write                path-is-a-file     a planted real file    write mapping
#   post-write-pre-validate  any                the validator          the fault
#   mid-swap                 generic            an absent staging tree swap guard
#   mid-swap                 permission-denied  the move-new-in rename swap mapping
#   mid-swap                 path-is-a-file     the move-new-in rename swap mapping
#
# `post-write-pre-validate` is the one stage whose code is the injected fault's
# own, and unavoidably so: the engine has finished writing and has not been asked
# to swap, so the halting outcome there belongs to the `Schema_Validator`
# *(R13 AC4)*, not to this module. What that stage is really about is the pair of
# absences — the skill discards staging, and the swap never runs, which is what
# "the release cannot be tagged" looks like on disk *(R2 AC4)*.
#
# `_materialize`, `_transformable`, `_read_tree`, and `_RESOLVED_TAG` are shared
# with the sections above.

#: The release the prior Power on disk was built from. Deliberately different
#: from `_RESOLVED_TAG`, which the faulted run builds: the two trees therefore
#: differ in bytes — the `.build-manifest.json` records the release — so "the
#: target is byte-identical to its prior state" is a claim one leaked write breaks.
_PRIOR_TAG = "0.4.2"

#: The OSError each fault kind presents to the engine. Both are the errors the
#: filesystem itself raises for that condition — `EACCES` for a denied write,
#: `ENOTDIR` for a path component that is a regular file — so the engine reports
#: them through its own `except OSError`, and the catalog code is its choice.
_INJECTED_OS_ERROR: Mapping[str, Callable[[Any], OSError]] = {
    "permission-denied": lambda path: PermissionError(
        errno.EACCES, "Permission denied", str(path)
    ),
    "path-is-a-file": lambda path: NotADirectoryError(
        errno.ENOTDIR, "Not a directory", str(path)
    ),
}


class _Tripped:
    """Whether an injected fault actually fired.

    A fault that silently failed to fire would leave the run succeeding, and a
    test that only asserted "the target is unchanged" would pass for the wrong
    reason. Every seam-injected case asserts this.
    """

    def __init__(self) -> None:
        self.count = 0

    @property
    def fired(self) -> bool:
        return self.count > 0


class _Run:
    """What the driver observed on the way to the fault.

    `staged` is the complete staging tree for the stages that get that far, and
    `None` for a fault during the write itself.
    """

    def __init__(self) -> None:
        self.trip = _Tripped()
        self.staged: dict[str, bytes] | None = None


@contextmanager
def _patched(owner: Any, name: str, replacement: Any) -> Iterator[None]:
    """Swap one attribute for the duration of a block, then put it back.

    Used instead of the `monkeypatch` fixture because Hypothesis runs many
    examples inside one test function, and a fixture's teardown does not.
    """
    missing = object()
    previous = getattr(owner, name, missing)
    setattr(owner, name, replacement)
    try:
        yield
    finally:
        if previous is missing:
            delattr(owner, name)
        else:
            setattr(owner, name, previous)


def _first_missing_component(staging: Path, relative: str) -> Path | None:
    """The topmost directory `relative` needs under `staging` that is absent.

    Where a `path-is-a-file` condition can be created for real: a regular file
    written here is a path component the engine's own `mkdir` has to trip over.
    Its own parent exists by construction, so planting the file needs no mkdir of
    the test's own.
    """
    walk = staging
    for segment in relative.split("/")[:-1]:
        walk = walk / segment
        if not walk.exists():
            return walk
    return None


@contextmanager
def _mid_write_fault(point: FailurePoint, trip: _Tripped) -> Iterator[None]:
    """Inject `point` into the staging write, after a file is already on disk.

    Every kind fires on the second write or later, so what the failure path has
    to discard is a *partially populated* tree rather than an empty directory —
    which is the case R4 AC8 is written about.
    """
    if point.kind == "generic":
        real_write = transform._write_staged_file
        writes = 0

        def escaping_write(staging: Any, relative: str, data: bytes) -> None:
            nonlocal writes
            writes += 1
            if writes == 2:
                trip.count += 1
                # The engine's containment gate refuses this destination itself,
                # with `E_TRANSFORM_FAILED`; the test names no code.
                real_write(staging, f"../{relative}", data)
            real_write(staging, relative, data)

        with _patched(transform, "_write_staged_file", escaping_write):
            yield
        return

    if point.kind == "permission-denied":
        make_error = _INJECTED_OS_ERROR[point.kind]
        real_open = open
        opened = 0

        def failing_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal opened
            opened += 1
            if opened == 2:
                trip.count += 1
                raise make_error(file)
            return real_open(file, *args, **kwargs)

        # `transform` has no module-level `open` of its own, so this shadows the
        # builtin for that one module and is removed again on the way out. The
        # module opens a handle in exactly one place: the staged write.
        with _patched(transform, "open", failing_open):
            yield
        return

    real_write = transform._write_staged_file
    writes = 0

    def write_behind_a_file(staging: Any, relative: str, data: bytes) -> None:
        nonlocal writes
        if writes and not trip.fired:
            component = _first_missing_component(Path(staging), relative)
            if component is not None:
                trip.count += 1
                component.write_bytes(b"a regular file, not a directory\n")
        writes += 1
        real_write(staging, relative, data)

    with _patched(transform, "_write_staged_file", write_behind_a_file):
        yield


@contextmanager
def _mid_swap_fault(
    point: FailurePoint, staging: Path, trip: _Tripped
) -> Iterator[None]:
    """Fail the rename that moves the staged tree into the target.

    The swap is move-old-aside, move-new-in, delete-old, so the middle rename is
    the one fault that has already disturbed the target's directory entry: the
    engine has to rename the old tree back. Only that rename is failed — the
    move-aside and the rollback are delegated — which is what leaves the rollback
    observable rather than prevented.
    """
    make_error = _INJECTED_OS_ERROR[point.kind]
    real_rename = os.rename

    def failing_rename(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
        if Path(os.fspath(src)) == staging:
            trip.count += 1
            raise make_error(dst)
        return real_rename(src, dst, *args, **kwargs)

    with _patched(os, "rename", failing_rename):
        yield


def _fires_through_a_seam(point: FailurePoint) -> bool:
    """Whether `point`'s realization runs through a wrapped engine seam.

    Two do not, and neither can: a validator fault after staging is complete is
    the caller's own halting outcome, and a mid-swap `generic` fault is the
    *absence* of the staging tree, which the swap refuses before it does anything
    at all.
    """
    if point.stage == "mid-write":
        return True
    return point.stage == "mid-swap" and point.kind != "generic"


def _swap_asides(root: Path) -> tuple[str, ...]:
    """Move-aside directories a swap left behind, relative to `root`.

    A failed swap renames the old tree into a private sibling directory and has
    to remove it again, so one of these on disk is residue every bit as much as a
    surviving staging tree — and a nastier one, because it holds a whole Power.
    """
    return tuple(
        sorted(
            (Path(directory) / name).relative_to(root).as_posix()
            for directory, subdirectories, _ in os.walk(root)
            for name in subdirectories
            if ".replaced-" in name
        )
    )


def _run_to_the_fault(
    contract: Contract,
    source: Path,
    staging: Path,
    target: Path,
    carry_forward: Path | None,
    point: FailurePoint,
    run: _Run,
) -> None:
    """Drive one create or update run into `point`, in the skill's own sequence.

    Plan, write staging, validate, swap. `swap_into_place` is the only call here
    that touches the target and the earlier stages never reach it, which is the
    whole of the post-write-pre-validate claim. Raises the `TransformError` the
    run halts with; an injected fault that fails to halt the run is an
    `AssertionError` rather than a quiet pass.
    """
    plan = build_plan(
        contract,
        source,
        tag=_RESOLVED_TAG,
        staging=staging,
        carry_forward=carry_forward,
    )

    if point.stage == "mid-write":
        with _mid_write_fault(point, run.trip):
            write_staging(plan)
        raise AssertionError(f"the injected {point.stage} fault did not halt the run")

    # The write phase completes, so every stage below has a full tree available
    # to leak and a target it must leave alone.
    result = write_staging(plan)
    run.staged = _read_tree(staging)
    assert MANIFEST_FILENAME in run.staged
    assert [output.path for output in result.outputs] == sorted(
        path for path in run.staged if path != MANIFEST_FILENAME
    )

    if point.stage == "post-write-pre-validate":
        try:
            raise TransformError(
                point.expected_error,
                f"injected {point.kind} fault after the staging write, "
                "before validation",
                stage=point.stage,
                kind=point.kind,
            )
        finally:
            # What the skill does on any pre-swap fault, and all it does: the
            # staged tree goes, the target is never opened.
            discard_staging(staging)

    assert point.stage == "mid-swap", point.stage
    if point.kind == "generic":
        # The staging tree is gone by the time the swap is asked for — a second
        # fault after a discard, or a hand outside the run. The swap refuses with
        # `E_TRANSFORM_FAILED` before it touches anything.
        discard_staging(staging)
        swap_into_place(staging, target)
    else:
        with _mid_swap_fault(point, staging, run.trip):
            swap_into_place(staging, target)
    raise AssertionError(f"the injected {point.stage} fault did not halt the run")


# Feature: senzing-bootcamp-power, Property 6: Failure leaves the target
# byte-identical
#
# Validates: Requirements 2.4, 4.6, 4.7, 4.8, 5.2, 5.7, 13.4, 14.5
@settings(max_examples=100)
@given(template_tree(), failure_point())
def test_failure_leaves_the_target_byte_identical(
    tree: Mapping[str, TreeEntry], point: FailurePoint
) -> None:
    contract = load_contract()
    source_tree = _transformable(tree, contract)

    # Non-vacuous by construction, asserted rather than assumed: a generator
    # change that emptied the input would fail here instead of passing silently.
    assert len(source_tree) >= 4

    # The generator's codes are the engine's catalog codes, not a parallel
    # vocabulary that could drift from it.
    assert point.expected_error in (E_TRANSFORM_FAILED, E_WRITE_FAILED)

    for prior in ("absent", "prior-power"):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "release"
            plugin_root = source.joinpath(*TEMPLATE_PLUGIN_ROOT.split("/"))
            plugin_root.mkdir(parents=True)
            _materialize(source_tree, plugin_root)

            target = root / "powers" / "senzing-bootcamp"
            snapshot: dict[str, bytes] | None = None
            carry_forward: Path | None = None
            if prior == "prior-power":
                # A real prior Power, built and swapped in by the same engine, at
                # a different release than the run that is about to fail.
                seed = root / "seed-staging"
                swap_into_place(
                    write_staging(
                        build_plan(contract, source, tag=_PRIOR_TAG, staging=seed)
                    ).staging,
                    target,
                )
                snapshot = _read_tree(target)
                assert MANIFEST_FILENAME in snapshot
                carry_forward = target
            else:
                assert not target.exists()

            staging = root / "staging"
            run = _Run()
            with pytest.raises(TransformError) as raised:
                _run_to_the_fault(
                    contract, source, staging, target, carry_forward, point, run
                )

            # The catalog code the design assigns this stage and kind.
            assert raised.value.code == point.expected_error

            # The fault reached the seam it was aimed at, so the run halted for
            # the injected reason rather than an incidental one.
            if _fires_through_a_seam(point):
                assert run.trip.fired, point

            # No residue: not the staging tree, not the seed tree the swap
            # consumed, not a swap's move-aside tree holding a whole Power.
            assert not staging.exists()
            assert not (root / "seed-staging").exists()
            assert _swap_asides(root) == ()

            # The target is byte-identical to its prior state.
            if snapshot is None:
                # R4 AC7, AC8: still absent, not created-and-empty and not
                # partially populated.
                assert not target.exists()
            else:
                # R5 AC7, R13 AC4: the prior Power, unchanged, down to the bytes.
                assert _read_tree(target) == snapshot
                if run.staged is not None:
                    # And a complete tree that differs from it was ready to
                    # replace it, so "unchanged" is a fact about the run rather
                    # than about the two trees being the same tree.
                    assert run.staged != snapshot


# ===========================================================================
# Property 7: Writes are contained within the target directory
# ===========================================================================
#
# `contained_path` is the engine's sole path constructor for every read and every
# write, so containment is one function's guarantee rather than a discipline
# spread across call sites — and this property is therefore stated about that
# function directly as well as about a whole pipeline run. It has three gates,
# each catching what the others cannot, and each needing a different kind of
# input to exercise honestly:
#
# 1. **Absolute and absolute-looking spellings**, in every flavor a template file
#    name can carry — POSIX `/etc/passwd`, drive-letter `C:\Windows\...`, UNC
#    `\\server\share\...` — refused regardless of the host, because
#    `os.path.isabs` on Linux calls the latter two *relative*.
# 2. **Segment inspection**, refusing `..`, `.`, and empty segments after
#    normalizing `\` to `/` so a Windows separator cannot smuggle a `..` past a
#    POSIX-only split. `.` and `//` do not themselves escape; they are refused
#    because a spelling that normalizes defeats the textual comparison the gate
#    rests on, and no legitimate output ever needs one.
# 3. **Real-location comparison**, the only gate that catches a symlink, and so
#    the only one that needs a real filesystem underneath it.
#
# Why gates 1 and 2 are exercised on path *strings* rather than only through a
# run: a path like `docs/../../../etc/passwd` cannot arrive by enumeration at
# all. Materialize it and the file lands *outside* the plugin root, where
# `os.walk` never yields it back as a relative path — so the adversarial
# spellings `template_tree()` emits reach the engine only if a test hands them to
# the constructor itself. They are not hypothetical inputs: `docs/**` claims
# `docs/../../../etc/passwd`, so refusing it is this gate's job and nothing
# else's.
#
# Symlinks are the opposite case — they do survive enumeration — so they are
# exercised end to end, but only at a **rule-matched** path. The generator's own
# escaping link sits at `skills/<name>-escape.md`, which no rule claims, so a
# whole-pipeline run over it halts with `E_UNMATCHED_FILE` before containment is
# ever consulted. The links this test plants therefore sit where the contract
# claims them: `docs/`, a skill's `references/`, and `scripts/`.
#
# Every escaping link points at a **real file** outside the root, and the test
# asserts the link resolves to one, so a refusal is the gate's doing rather than
# an accident of a dangling link.
#
# The pipeline half runs twice: a create-path build that must succeed, whose
# every write is checked to land inside staging and then inside the target, and
# an update-path build over a tree carrying one escaping link, which must halt.
# Both are bracketed by a snapshot of everything under the temporary root that is
# *not* the source, the staging tree, or the target — with the spellings the
# generator's escaping paths actually aim at planted there as real files, so a
# leaked write shows up as a changed file and not merely as a new one.
#
# `_materialize`, `_transformable`, `_stays_inside_plugin_root`, `_read_tree`,
# and `_RESOLVED_TAG` are shared with the sections above.

#: Escaping spellings beyond the ones `template_tree()` emits, keyed by flavor so
#: the coverage guard below is a statement about flavors rather than a count.
_ESCAPING_SPELLINGS: Mapping[str, str] = {
    "posix-absolute": "/etc/passwd",
    "drive-letter": "C:\\Windows\\System32\\drivers\\etc\\hosts",
    "unc-share": "\\\\fileserver\\share\\absolute-looking.txt",
    "leading-dotdot": "../outside-the-root.md",
    "interior-dotdot": "skills/../../escape.md",
    "trailing-dotdot": "docs/images/..",
    "backslash-dotdot": "docs\\..\\..\\escape.md",
    "dot-segment": "docs/./sneaky.md",
    "empty-segment": "docs//sneaky.md",
    "empty-path": "",
    "whitespace-only": "   ",
}

#: The flavors the gate has to catch, named so deleting one from the table above
#: fails this property rather than quietly narrowing it.
_REQUIRED_ESCAPE_FLAVORS = frozenset(
    {
        "posix-absolute",
        "drive-letter",
        "unc-share",
        "leading-dotdot",
        "interior-dotdot",
        "backslash-dotdot",
        "dot-segment",
        "empty-segment",
    }
)

#: Real Bootcamp_Power output spellings, every one of which must be accepted. The
#: accept side matters as much as the refuse side: a gate that refused any of
#: these would refuse to build the Power at all, and a test that only checked
#: refusals would call that a pass.
_CONTAINED_SPELLINGS = (
    "plugin.json",
    "mcp.json",
    MANIFEST_FILENAME,
    "skills/bootcamp-onboarding/SKILL.md",
    "skills/bootcamp-onboarding/scripts/vendor/d3.v7.min.js",
    "skills/bootcamp-onboarding/assets/kiro-hooks/senzing-bootcamp-session-start.json",
    "dev.kiro/hooks/senzing-bootcamp-write-gate.json",
    "docs/images/truth-set.png",
    "docs/données-café.md",
)

#: Rule-matched locations an escaping link is planted at, one per rule kind that
#: reads a template file: `substitute` for `docs/` and `scripts/`, `skill` for a
#: skill's `references/`. A location no rule claims would halt the run with
#: `E_UNMATCHED_FILE` and never reach containment, which is the trap this
#: placement list exists to avoid.
_ESCAPING_LINK_PLACEMENTS = ("docs", "skill-references", "scripts")

#: How an escaping link names its target. Both leave the root, and neither is
#: caught by gate 1 or gate 2: the *link's own path* is an ordinary relative
#: spelling either way, so only the real-location comparison sees the escape.
_ESCAPING_LINK_TARGETS = ("absolute", "relative")

#: Basename of the planted link, and of the files planted outside the root.
_ESCAPING_LINK_STEM = "senzing-bootcamp-escape"

#: Where the generator's escaping spellings actually aim, relative to a root's
#: parent: `../outside-the-root.md`, `skills/../../escape.md`, and
#: `docs/../../../etc/passwd` all name one of these. Planted as real files so a
#: leaked write is a *changed* file rather than an unremarkable new one.
_ESCAPE_DESTINATIONS = ("outside-the-root.md", "escape.md", "passwd")


def _really_inside(path: Path, root: Path) -> bool:
    """Whether `path`'s real location is `root` itself or below it.

    Resolves links on both sides, which is what "no write escapes that root"
    means once a symlink is in the picture: the *spelling* of a written path is
    not the question, the file it lands on is.
    """
    real_root = Path(os.path.realpath(root))
    real_path = Path(os.path.realpath(path))
    return real_path == real_root or real_root in real_path.parents


def _refused(
    root: Path,
    relative: str,
    *,
    what: str = "path",
    code: str = E_TRANSFORM_FAILED,
) -> TransformError:
    """`contained_path` refuses `relative` under `root`, naming it. Returns the fault.

    The refusal has to be usable, not merely present: the catalog code is the
    caller's own — the staged write asks for `E_TRANSFORM_FAILED`, the reconciler
    for `E_WRITE_FAILED` — and the offending path is carried as data as well as in
    the message, so a Maintainer reads which path was refused rather than
    inferring it.
    """
    with pytest.raises(TransformError) as raised:
        contained_path(root, relative, what=what, code=code)
    error = raised.value
    assert error.code == code, relative
    assert error.details["path"] == relative
    assert error.details["root"] == str(root)
    assert what in error.message, relative
    assert repr(relative) in error.message, relative
    return error


def _escaping_link_source(placement: str, tree: Mapping[str, TreeEntry]) -> str:
    """Plugin-root-relative path the escaping link is planted at."""
    if placement == "docs":
        return f"docs/{_ESCAPING_LINK_STEM}.md"
    if placement == "scripts":
        return f"scripts/{_ESCAPING_LINK_STEM.replace('-', '_')}.py"
    assert placement == "skill-references", placement
    skills = sorted({path.split("/")[1] for path in tree if path.startswith("skills/")})
    assert skills, "every generated tree carries at least one skill directory"
    return f"skills/{skills[0]}/references/{_ESCAPING_LINK_STEM}.md"


def _escaping_link_target(flavor: str, link: Path, outside: Path) -> str:
    """The target text the planted link carries, in `flavor`'s spelling."""
    if flavor == "absolute":
        return str(outside)
    assert flavor == "relative", flavor
    return os.path.relpath(outside, link.parent)


def _entries_outside(root: Path, *inside: Path) -> dict[str, tuple[str, bytes]]:
    """Every filesystem entry under `root` that is not within one of `inside`.

    Directories, regular files with their bytes, and symlinks with their targets,
    so a leaked write is visible whether it created something, changed something
    already there, or replaced a file with a link. `inside` names the subtrees a
    run is *allowed* to change — the source it reads, its staging directory, the
    target it publishes — and those are pruned rather than compared.
    """
    pruned = frozenset(path.relative_to(root).as_posix() for path in inside)
    entries: dict[str, tuple[str, bytes]] = {}
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        here = Path(directory)
        prefix = here.relative_to(root).as_posix()
        base = "" if prefix == "." else f"{prefix}/"
        # Pruned before anything is recorded, so a subtree a run owns contributes
        # neither its own entry nor its contents.
        subdirectories[:] = sorted(
            name for name in subdirectories if f"{base}{name}" not in pruned
        )
        for name in subdirectories:
            entries[f"{base}{name}"] = ("dir", b"")
        for name in sorted(filenames):
            absolute = here / name
            if absolute.is_symlink():
                entries[f"{base}{name}"] = ("symlink", os.readlink(absolute).encode())
            else:
                entries[f"{base}{name}"] = ("file", absolute.read_bytes())
    return entries


def _materialized_release(
    root: Path, tree: Mapping[str, TreeEntry], name: str
) -> tuple[Path, Path]:
    """Write `tree` as a release directory under `root`, returning both roots."""
    source = root / name
    plugin_root = source.joinpath(*TEMPLATE_PLUGIN_ROOT.split("/"))
    plugin_root.mkdir(parents=True)
    _materialize(tree, plugin_root)
    return source, plugin_root


# Feature: senzing-bootcamp-power, Property 7: Writes are contained within the
# target directory
#
# Validates: Requirements 14.1
@settings(max_examples=100)
@given(
    template_tree(),
    st.one_of(
        TEMPLATE_TREE_CASES["dotdot_segment"],
        TEMPLATE_TREE_CASES["absolute_looking_path"],
    ),
    st.sampled_from(_ESCAPING_LINK_PLACEMENTS),
    st.sampled_from(_ESCAPING_LINK_TARGETS),
)
def test_writes_are_contained_within_the_target_directory(
    tree: Mapping[str, TreeEntry],
    adversarial: Mapping[str, TreeEntry],
    placement: str,
    link_target: str,
) -> None:
    contract = load_contract()
    source_tree = _transformable(tree, contract)

    # Non-vacuous by construction, asserted rather than assumed: a generator
    # change that emptied either input would fail here instead of passing.
    assert len(source_tree) >= 4
    assert _REQUIRED_ESCAPE_FLAVORS <= set(_ESCAPING_SPELLINGS)

    # The generator's own escaping spellings, which is what makes the gate half a
    # statement about generated input rather than about a fixed list.
    generated = tuple(
        sorted(path for path in adversarial if not _stays_inside_plugin_root(path))
    )
    assert generated, "the adversarial case contributed no escaping spelling"

    # --- Gates 1 and 2: path strings, no filesystem needed ------------------
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        outside = root / "outside"
        outside.mkdir()
        planted = outside / f"{_ESCAPING_LINK_STEM}.md"
        planted.write_bytes(b"a real file the engine may never read or write\n")

        power = root / "powers" / "senzing-bootcamp"
        power.mkdir(parents=True)

        for spelling in (*generated, *sorted(_ESCAPING_SPELLINGS.values())):
            _refused(power, spelling)
            # The caller's catalog code and label are carried, not overridden.
            _refused(power, spelling, what="reconciled file", code=E_WRITE_FAILED)

        for spelling in (*_CONTAINED_SPELLINGS, *sorted(source_tree)):
            resolved = contained_path(power, spelling, what="output file")
            assert resolved == power.joinpath(*spelling.split("/")), spelling
            assert _really_inside(resolved, power), spelling

        # --- Gate 3: the only gate a symlink meets --------------------------
        links = power / "docs"
        links.mkdir(parents=True, exist_ok=True)
        (links / "real.md").write_bytes(b"inside the root\n")
        os.symlink("real.md", links / "inside-link.md")
        os.symlink(planted, links / "escaping-link.md")
        os.symlink(outside, links / "escaping-dir")

        # A link that stays inside is a legitimate path: the gate is about where a
        # path really lands, not about links.
        inside_link = contained_path(power, "docs/inside-link.md")
        assert _really_inside(inside_link, power)
        assert inside_link.read_bytes() == b"inside the root\n"

        # A link out of the root is refused, as is a path *through* a linked
        # directory — the ancestor case no segment inspection can see.
        _refused(power, "docs/escaping-link.md")
        _refused(power, f"docs/escaping-dir/{_ESCAPING_LINK_STEM}.md")

        # Reaching the root itself through a link is not an escape: real
        # locations are compared, so a symlinked ancestor of the root is fine.
        entrance = root / "entrance"
        os.symlink(power, entrance)
        assert _really_inside(contained_path(entrance, "docs/real.md"), power)

    # --- A real pipeline run writes only inside its own roots ---------------
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        outside = root / "outside"
        outside.mkdir()
        for name in _ESCAPE_DESTINATIONS:
            (outside / name).write_bytes(b"untouched\n")
        planted = outside / f"{_ESCAPING_LINK_STEM}.md"
        planted.write_bytes(b"a real file the engine may never read or write\n")

        source, _ = _materialized_release(root, source_tree, "release")
        staging = root / "staging"
        target = root / "powers" / "senzing-bootcamp"
        # Created up front so the swap's own `mkdir` cannot make the target's
        # parent look like a leaked write, and so a stray write *into* the parent
        # still would.
        target.parent.mkdir(parents=True)

        before = _entries_outside(root, source, staging, target)
        assert before, "nothing was planted outside the roots to compare against"

        # --- The create path succeeds, and every write lands in staging -----
        result = write_staging(
            build_plan(contract, source, tag=_RESOLVED_TAG, staging=staging)
        )
        staged = _read_tree(staging)
        assert len(staged) > 1
        assert MANIFEST_FILENAME in staged
        assert [output.path for output in result.outputs] == sorted(
            path for path in staged if path != MANIFEST_FILENAME
        )
        for relative in sorted(staged):
            assert _really_inside(staging / relative, staging), relative
        assert _entries_outside(root, source, staging, target) == before

        # --- The swap publishes into the target, and nowhere else -----------
        swap_into_place(staging, target)
        published = _read_tree(target)
        assert published == staged
        for relative in sorted(published):
            assert _really_inside(target / relative, target), relative
        assert _entries_outside(root, source, staging, target) == before

        # --- The update path over a tree carrying one escaping link ---------
        faulted_source, faulted_plugin_root = _materialized_release(
            root, source_tree, "faulted-release"
        )
        placed = _escaping_link_source(placement, source_tree)
        # The trap the placement list exists to avoid: at a path no rule claims,
        # the run halts with E_UNMATCHED_FILE and containment is never reached.
        assert contract.classify(placed).disposition == "rule", placed

        link = faulted_plugin_root.joinpath(*placed.split("/"))
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(_escaping_link_target(link_target, link, planted), link)
        # Unguarded, this read would succeed: the link resolves to a real file
        # that really is outside the root.
        assert link.is_file()
        assert not _really_inside(link, faulted_plugin_root)

        faulted_staging = root / "faulted-staging"
        before_fault = _entries_outside(root, faulted_source, faulted_staging, target)

        with pytest.raises(TransformError) as raised:
            write_staging(
                build_plan(
                    contract,
                    faulted_source,
                    tag=_RESOLVED_TAG,
                    staging=faulted_staging,
                    carry_forward=target,
                )
            )
        error = raised.value

        # The refusal is containment's, and it names the offending path and the
        # root it escaped, as data.
        assert error.code == E_TRANSFORM_FAILED
        assert error.details["path"] == placed
        assert error.details["root"] == str(faulted_plugin_root)
        assert repr(placed) in error.message

        # Nothing was written outside the roots, no staging residue is left, and
        # the Power published above still holds exactly its own bytes.
        assert not faulted_staging.exists()
        assert (
            _entries_outside(root, faulted_source, faulted_staging, target)
            == before_fault
        )
        assert _read_tree(target) == published

# ===========================================================================
# Property 8: Declared substitutions leave zero residuals in corresponding
# positions
# ===========================================================================
#
# R10 AC2 and R12 AC2 both say the same thing about two different rewrites — the
# root path token, and Claude-specific model guidance — and both say it as an
# *absence*: after the port, zero occurrences of the term remain. An absence is
# the easy half to check and the easy half to check wrongly, because two honest
# readings of "zero occurrences" disagree on the generated sets:
#
# - `str.count(find) == 0` in the output. False for `script-paths`, whose
#   replacement `../bootcamp-onboarding/scripts/` *contains* its own find term
#   `scripts/`. Every occurrence was rewritten and the count is still nonzero.
# - "no occurrence survives" counted against the input. False for
#   `manifest-path`, whose two find terms nest: `.claude-plugin/plugin.json` is a
#   suffix of `../.claude-plugin/plugin.json`, so `str.count` of the shorter term
#   includes its occurrences *inside* the longer one, and the longer entry — the
#   earlier-declared one — consumes them.
#
# So the claim is stated positionally, which is what the design's title means by
# "in corresponding positions": every character of the result is either carried
# through from the source at a known index or emitted by a replacement, and **no
# occurrence of a declared find term in the result lies entirely in
# carried-through characters**. Under that reading `script-paths` passes honestly
# (its residual sits inside text a replacement emitted) and `manifest-path`
# passes honestly (the nested occurrence was consumed by the entry that spanned
# it), and neither one needs the claim weakened to accommodate it.
#
# The oracle
# ----------
# `_reference_pass` is a character scanner: at each position it tries the
# `INV-NNN` citation guard, then the set's entries in declared order, and
# otherwise copies one character. It is deliberately *not* a second spelling of
# the engine's combined alternation — the engine's ordering, single-pass, and
# citation-guard behavior are emergent properties of one `re.sub` over one
# pattern, and a test that rebuilt that pattern would be asking the
# implementation what it expected. The scanner also never looks at what it
# emitted, so `engine == scanner` *is* the single-pass claim: a pass that
# rescanned its own output could not match it.
#
# It carries a provenance list beside the text — an original index per surviving
# character, `None` per emitted one — through every pass of the fold, and that
# list is what makes the positional claim, "every byte no set names is
# unchanged", and the in-place preservation of citations checkable rather than
# rhetorical.
#
# What each clause catches
# ------------------------
# 1. **`result == fold.result`**, plus, at each rewrite, the replacement read off
#    the produced text at the mapped offset: the design's "contains the
#    corresponding `replace` term at each position where a `find` term occurred".
# 2. **A match count identity per pass**, checked against `str.count` over the
#    text that pass read, corrected for nested find terms. `str.count` is the
#    generator's own method for `FileContentCase.occurrences`, so the counts a
#    case carries are an independent oracle for how many rewrites a pass owes.
# 3. **The positional zero-residual claim** above, plus its crisp form — literal
#    `find not in result` — asserted outright for every set whose replacements
#    carry no find term, which is five of the six.
# 4. **Provenance totality**: surviving indices are strictly increasing, unique,
#    and hold the source's own characters, and for a single set they plus the
#    matched spans account for every byte of the input. A rewrite that moved,
#    duplicated, or dropped untargeted text fails here.
# 5. **Citations**, by multiset and in place: every `INV-NNN` citation in the
#    result occupies a contiguous run of carried-through source characters, so a
#    citation cannot be destroyed at one position and re-formed at a seam with
#    the multiset none the wiser. Counted with this file's own regex, and for the
#    discounted invariants and the honored one by name (R15 AC7): a discount is
#    about packaging construction, not about what ported prose may cite.
# 6. **Fixed point, both directions.** A second application changes nothing
#    exactly when no declared term survives in the result; where one does — the
#    `script-paths` shape — the twice-applied text is asserted *different* from
#    the engine's output, which is what makes clause 1's equality evidence of one
#    pass rather than a coincidence.
# 7. **Independence**: the same `(text, ordered sets)` through a different fault
#    label, different `details`, renamed sets, and the bytes route yields the
#    identical result, and no set at all yields the input unchanged.
#
# Scope, asserted rather than assumed: every set the strategies module mirrors is
# literal, so the scanner implements the literal shape only and refuses a
# `pattern` entry outright rather than quietly checking a narrower claim. One of
# those literals is `Write|Edit`, whose `|` must match a pipe and not an
# alternation, which is the engine's `re.escape` under test.
#
# One guarantee this property deliberately does *not* claim to pin: which entry
# wins a genuinely shared position. The only overlap the declared sets contain is
# `manifest-path`'s *suffix* nesting, and there the two declaration orders
# produce the same output — the shorter term cannot match where the longer one
# starts, so the longer one matches either way. Pinning the tie-break needs a
# prefix-nested pair, which no set declares; what this property pins about the
# overlap is the arithmetic (clause 2), which is where the honest count of a
# nested occurrence actually lives.
#
# `_engine_set` builds every applied set through the contract parser, so a set
# these tests apply is one a contract could declare — and the generated
# `Substitution` (a `find`/`replace` pair) never reaches a signature expecting
# `transform.Substitution` (a parsed entry, carrying its set name and index).
# Nothing here reads `contract.yaml`: the property is about the engine over
# declared sets, not about the values the committed contract currently declares.

#: An inline Template_Invariant citation, spelled independently of the engine's
#: own pattern. `re.ASCII` is what keeps `\d` to `[0-9]`.
_CITATION = re.compile(r"INV-\d+", re.ASCII)

#: The named `file_content()` cases this property relies on, so a generator
#: change that dropped one fails here instead of narrowing the property.
_REQUIRED_CONTENT_CASES = frozenset(
    {
        "zero_occurrences",
        "one_occurrence",
        "many_occurrences",
        "adjacent_tokens",
        "tokens_in_code_fence",
        "invariant_references",
    }
)

#: Cases guaranteed to carry at least one token, drawn alongside the composite so
#: the rewriting clauses are exercised deliberately rather than by luck.
_OCCUPIED_CONTENT_CASES = (
    "one_occurrence",
    "many_occurrences",
    "adjacent_tokens",
    "tokens_in_code_fence",
    "invariant_references",
)

#: Citation-bearing prose appended to a case's text: in a sentence, in a fenced
#: block, repeated within one fence, and inline in backticks. None carries a
#: brace or a find term, so the counts a case computed still describe the text
#: under test and `str.format` has nothing of its own to interpret.
_CITATION_DECORATIONS = (
    "\nPer {discounted}, this line is ported as written, and {honored} is honored.\n",
    "\n```python\n# {discounted}: a citation is content, fence or no fence.\n```\n",
    "\n```\n{discounted} {honored} {discounted}\n```\n",
    "\nInline `{honored}` beside {discounted} in one sentence.\n",
)

#: Regex metacharacters a literal find term may carry, which the engine has to
#: escape for the term to match itself and nothing else.
_METACHARACTERS = frozenset("$^{}[]()|*+?.\\-")


@dataclass(frozen=True)
class _Rewrite:
    """One match a reference pass consumed, in that pass's own coordinates."""

    set_name: str
    index: int
    find: str
    replace: str
    start: int
    output_start: int


@dataclass(frozen=True)
class _ReferencePass:
    """What one set's reference pass read, produced, and rewrote."""

    subset: transform.SubstitutionSet
    read: str
    produced: str
    rewrites: tuple[_Rewrite, ...]


@dataclass(frozen=True)
class _ReferenceFold:
    """The reference account of applying an ordered sequence of sets to a text.

    `origins` runs parallel to `result`: an index into `source` for a character
    carried through, `None` for a character a replacement emitted.
    """

    source: str
    result: str
    origins: tuple[int | None, ...]
    passes: tuple[_ReferencePass, ...]


def _engine_set(
    name: str, substitutions: Sequence[Substitution]
) -> transform.SubstitutionSet:
    """The engine's parsed set for a generated sequence of `find`/`replace` pairs."""
    entries = [
        {"find": item.find, "replace": item.replace, "literal": True}
        if item.literal
        else {"pattern": item.find, "replace": item.replace, "regex": True}
        for item in substitutions
    ]
    subset = transform.parse_substitution_set(name, entries)
    # Declared order is the set's order, and the parser kept it.
    assert tuple(entry.find for entry in subset.entries) == tuple(
        item.find for item in substitutions
    )
    assert tuple(entry.index for entry in subset.entries) == tuple(
        range(len(substitutions))
    )
    return subset


def _generated_set_name(substitutions: Sequence[Substitution]) -> str:
    """The contract name of a mirrored set, which a `FileContentCase` omits.

    The six mirrored sets are distinct, so the lookup is unambiguous; an
    ambiguous or absent one fails here rather than mislabeling a fault path.
    """
    names = [
        name
        for name, entries in SUBSTITUTION_SETS.items()
        if entries == tuple(substitutions)
    ]
    assert len(names) == 1, substitutions
    return names[0]


def _renamed(
    subset: transform.SubstitutionSet, name: str
) -> transform.SubstitutionSet:
    """The same entries under a different set name, which is fault-path data only."""
    return transform.SubstitutionSet(
        name=name,
        entries=tuple(
            transform.Substitution(
                set_name=name,
                index=entry.index,
                kind=entry.kind,
                find=entry.find,
                replace=entry.replace,
            )
            for entry in subset.entries
        ),
    )


def _self_overlapping(term: str) -> bool:
    """Whether `term` can overlap itself, which would make `str.count` the wrong oracle."""
    return any(term.startswith(term[index:]) for index in range(1, len(term)))


def _nested_occurrences(
    text: str, entries: Sequence[transform.Substitution]
) -> int:
    """Occurrences of one find term that lie inside an occurrence of another.

    The correction that turns a sum of `str.count` values into a match count:
    `manifest-path` declares one term that is a *suffix* of another, so every
    occurrence of the longer term carries one occurrence of the shorter, and the
    entry spanning the position consumes both. Suffix nesting is asserted rather
    than assumed — a prefix-nested pair would make which entry wins depend on
    declared order, and this arithmetic would be the wrong claim.
    """
    nested = 0
    for outer in entries:
        for inner in entries:
            if inner is outer or inner.find not in outer.find:
                continue
            assert inner.find != outer.find, outer.find
            assert outer.find.endswith(inner.find), (outer.find, inner.find)
            nested += text.count(outer.find) * outer.find.count(inner.find)
    return nested


def _winning_entry(
    text: str, position: int, entries: Sequence[transform.Substitution]
) -> transform.Substitution | None:
    """The entry that wins at `position`: the earliest-declared one that matches.

    Literal only. Every set the strategies module mirrors is literal, and a
    `pattern` entry reaching here would mean this scanner is checking a narrower
    claim than the property states, so it fails rather than passing quietly.
    """
    for entry in entries:
        assert entry.kind == transform.SUBSTITUTION_LITERAL, entry
        if text.startswith(entry.find, position):
            return entry
    return None


def _reference_pass(
    text: str, origins: Sequence[int | None], subset: transform.SubstitutionSet
) -> tuple[str, tuple[int | None, ...], tuple[_Rewrite, ...]]:
    """One left-to-right pass of `subset` over `text`, carrying provenance.

    A character scanner: the citation guard first, then the entries in declared
    order, otherwise copy one character and advance. Emitted text is never
    revisited, which is the single-pass guarantee written as a loop that cannot
    do otherwise.
    """
    pieces: list[str] = []
    carried: list[int | None] = []
    rewrites: list[_Rewrite] = []
    position = 0
    produced = 0
    while position < len(text):
        citation = _CITATION.match(text, position)
        if citation is not None:
            pieces.append(citation.group(0))
            carried.extend(origins[position : citation.end()])
            produced += citation.end() - position
            position = citation.end()
            continue
        entry = _winning_entry(text, position, subset.entries)
        if entry is None:
            pieces.append(text[position])
            carried.append(origins[position])
            produced += 1
            position += 1
            continue
        rewrites.append(
            _Rewrite(
                set_name=subset.name,
                index=entry.index,
                find=entry.find,
                replace=entry.replace,
                start=position,
                output_start=produced,
            )
        )
        pieces.append(entry.replace)
        carried.extend([None] * len(entry.replace))
        produced += len(entry.replace)
        position += len(entry.find)
    return "".join(pieces), tuple(carried), tuple(rewrites)


def _reference_fold(
    text: str, sets: Sequence[transform.SubstitutionSet]
) -> _ReferenceFold:
    """Fold the reference pass over `sets` in order, provenance and all."""
    origins: tuple[int | None, ...] = tuple(range(len(text)))
    current = text
    passes: list[_ReferencePass] = []
    for subset in sets:
        produced, origins, rewrites = _reference_pass(current, origins, subset)
        passes.append(
            _ReferencePass(
                subset=subset, read=current, produced=produced, rewrites=rewrites
            )
        )
        current = produced
    return _ReferenceFold(
        source=text, result=current, origins=origins, passes=tuple(passes)
    )


def _assert_no_residual_in_source_positions(
    text: str,
    sets: Sequence[transform.SubstitutionSet],
    *,
    what: str = "generated file content",
) -> _ReferenceFold:
    """Apply `sets` to `text` through the engine and check Property 8's clauses.

    Returns the reference account so a caller can state a per-case fact — an
    occurrence count the generator computed — against the pass this checked.
    """
    fold = _reference_fold(text, sets)
    result = transform.apply_substitutions(text, sets, what=what, ruleId="probe")
    entries = tuple(entry for subset in sets for entry in subset.entries)

    # --- Clause 1: the replacement stands where the find term stood ---------
    assert result == fold.result
    assert len(fold.origins) == len(result)
    for reference_pass in fold.passes:
        for rewrite in reference_pass.rewrites:
            assert reference_pass.read.startswith(rewrite.find, rewrite.start)
            assert reference_pass.produced.startswith(
                rewrite.replace, rewrite.output_start
            )

        # --- Clause 2: the pass owes one rewrite per occurrence -------------
        # `str.count` over the text this pass read, corrected for nesting, is the
        # generator's own method of counting occurrences. No generated find term
        # begins with a digit or contains `INV-`, so the citation guard can
        # neither suppress nor split a match; where one overlapped a citation
        # this identity would be the wrong claim and would say so here.
        occurrences = sum(
            reference_pass.read.count(entry.find)
            for entry in reference_pass.subset.entries
        )
        assert len(reference_pass.rewrites) == occurrences - _nested_occurrences(
            reference_pass.read, reference_pass.subset.entries
        )

    # --- Clause 3: zero residuals in the positions the terms occupied -------
    for entry in entries:
        start = result.find(entry.find)
        while start != -1:
            span = fold.origins[start : start + len(entry.find)]
            assert any(origin is None for origin in span), (
                entry.set_name,
                entry.find,
                start,
            )
            start = result.find(entry.find, start + 1)

    # Nothing to rewrite means nothing rewritten, and where no replacement
    # carries a find term the crisp reading of R10 AC2 and R12 AC2 holds
    # outright: zero occurrences of the term remain anywhere in the output.
    if not any(entry.find in text for entry in entries):
        assert result == text
    if not any(other.find in entry.replace for entry in entries for other in entries):
        for entry in entries:
            assert entry.find not in result, (entry.set_name, entry.find)

    # --- Clause 4: every byte no set names is unchanged ---------------------
    surviving = [origin for origin in fold.origins if origin is not None]
    assert surviving == sorted(surviving)
    assert len(set(surviving)) == len(surviving)
    assert "".join(text[origin] for origin in surviving) == "".join(
        character
        for character, origin in zip(result, fold.origins)
        if origin is not None
    )
    if len(fold.passes) == 1:
        # One set: the surviving bytes and the matched spans account for the
        # whole input, so nothing was dropped, duplicated, or moved.
        consumed = sum(len(rewrite.find) for rewrite in fold.passes[0].rewrites)
        assert len(surviving) + consumed == len(text)

    # --- Clause 5: citations, by multiset and in place ----------------------
    before = _CITATION.findall(text)
    after = _CITATION.findall(result)
    assert sorted(after) == sorted(before)
    assert tuple(before) == transform.invariant_citations(text)
    assert tuple(after) == transform.invariant_citations(result)
    for invariant in (HONORED_INVARIANT, *DISCOUNTED_INVARIANTS):
        assert after.count(invariant) == before.count(invariant), invariant
    carried = frozenset(surviving)
    for citation in _CITATION.finditer(text):
        assert set(range(citation.start(), citation.end())) <= carried
    for citation in _CITATION.finditer(result):
        span = fold.origins[citation.start() : citation.end()]
        sources = [origin for origin in span if origin is not None]
        assert len(sources) == len(span), citation.group(0)
        # Contiguous in the source too, so a citation cannot be destroyed at one
        # position and re-formed at a seam with the multiset none the wiser.
        assert sources == list(range(sources[0], sources[0] + len(sources)))

    # --- Clause 6: fixed point, both directions ----------------------------
    again = transform.apply_substitutions(result, sets, what=what)
    assert again == _reference_fold(result, sets).result
    if any(entry.find in result for entry in entries):
        # The only way a declared term survives is a replacement carrying one,
        # and every such residual sits in emitted text (clause 3). A second
        # application therefore rewrites again — and differs from the engine's
        # output, which is what makes clause 1's equality evidence of one pass.
        assert any(
            other.find in entry.replace for entry in entries for other in entries
        )
        assert again != result
    else:
        assert again == result

    # --- Clause 7: independent of everything but the text and the sets ------
    assert (
        transform.apply_substitutions(
            text, sets, what="a different label", ruleId="other", path="docs/other.md"
        )
        == result
    )
    assert (
        transform.apply_substitutions(
            text,
            tuple(
                _renamed(subset, f"renamed-{position}")
                for position, subset in enumerate(sets)
            ),
            what=what,
        )
        == result
    )
    assert transform.substitute_content(
        text.encode("utf-8"), sets, what=what
    ) == result.encode("utf-8")
    assert transform.substitute_content(text.encode("utf-8"), ()) == text.encode("utf-8")
    return fold


# Feature: senzing-bootcamp-power, Property 8: Declared substitutions leave zero
# residuals in corresponding positions
#
# Validates: Requirements 10.2, 12.2
@settings(max_examples=200)
@given(
    file_content(),
    st.one_of(*(FILE_CONTENT_CASES[name] for name in _OCCUPIED_CONTENT_CASES)),
    st.permutations(sorted(SUBSTITUTION_SETS)),
    st.sampled_from(_CITATION_DECORATIONS),
    st.sampled_from(DISCOUNTED_INVARIANTS),
)
def test_declared_substitutions_leave_zero_residuals_in_corresponding_positions(
    case: FileContentCase,
    occupied: FileContentCase,
    order: list[str],
    decoration: str,
    discounted: str,
) -> None:
    mirrored = tuple(
        item for entries in SUBSTITUTION_SETS.values() for item in entries
    )

    # Non-vacuous by construction, asserted rather than assumed: the generator's
    # named cases; an input that really carries a token; a find term whose regex
    # metacharacters the engine has to escape; a replacement carrying its own
    # find term; a nested find pair; and the literal-only scope the reference
    # scanner implements.
    assert _REQUIRED_CONTENT_CASES <= set(FILE_CONTENT_CASES)
    assert occupied.total_occurrences >= 1
    assert set(order) == set(SUBSTITUTION_SETS)
    assert all(item.literal for item in mirrored)
    assert any(_METACHARACTERS & set(item.find) for item in mirrored)
    assert any(
        item.find in other.replace
        for entries in SUBSTITUTION_SETS.values()
        for item in entries
        for other in entries
    )
    assert any(
        inner.find in outer.find and inner.find != outer.find
        for entries in SUBSTITUTION_SETS.values()
        for outer in entries
        for inner in entries
    )

    citations = decoration.format(discounted=discounted, honored=HONORED_INVARIANT)
    assert _CITATION.findall(citations)

    # The ordered sequence a rule declares, applied in the rule's order.
    ordered = tuple(_engine_set(name, SUBSTITUTION_SETS[name]) for name in order)

    for base in (case, occupied):
        own = _engine_set(_generated_set_name(base.substitutions), base.substitutions)
        assert not any(_self_overlapping(entry.find) for entry in own.entries)

        for text in (base.text, base.text + citations):
            # The decoration carries citations and no token, so the occurrence
            # counts the generator computed still describe the text under test.
            assert {
                entry.find: text.count(entry.find) for entry in own.entries
            } == base.occurrences

            # The design's statement, one declared set at a time.
            fold = _assert_no_residual_in_source_positions(text, (own,))
            assert len(fold.passes[0].rewrites) == base.total_occurrences - (
                _nested_occurrences(text, own.entries)
            )
            if base is occupied:
                assert fold.passes[0].rewrites

        # ...and under every declared set at once, in the drawn order.
        _assert_no_residual_in_source_positions(base.text + citations, ordered)

# ===========================================================================
# Property 9: Residual Claude-specific references are fully detected and
# downgrade the outcome
# ===========================================================================
#
# R12 AC3 and AC4 are one arrangement in two halves, and neither half is worth
# much alone. A gate that reported every residual reference and still let the run
# pass would tell a Maintainer about a content defect and then tag over it; a gate
# that downgraded the run while reporting "this Power carries residual references
# somewhere" would block the tag and leave nobody able to act. Both halves are
# therefore driven here over the same documents: exactly *k* findings, each naming
# its source document *and* its position within that document, and any hit at all
# folding the run to `incomplete` with `tagAllowed` false.
#
# Seeding, and why every base is ported first
# -------------------------------------------
# "Seeded with exactly *k* references" only means something if the documents carry
# no others, so every base below is either Kiro-authored prose or a *ported*
# document — `file_content()`'s text with its own declared substitution set
# applied, which is what the transform writes. The pre-port text is scanned too,
# and asserted to be reported whenever it carried a Claude-specific term at all:
# that is what makes the clean baseline the substitutions' doing rather than the
# scanner's blindness.
#
# Each seeded reference then goes on its own line, bounded by whitespace, and the
# construction records where it put it — source, line, column, and offset,
# computed from the lines it assembled rather than read off the finished text.
# `_coordinate` recomputes the same position from the document afterwards, so the
# two agree before either is compared against a finding.
#
# The oracle is R12 AC2's categories, not the validator's patterns
# ---------------------------------------------------------------
# `_SEED_TERMS` pairs a literal a ported document could still carry with the kind
# it belongs to: a subscription plan, a model name, an effort setting, the root
# path token R10 AC2 names, and the client names the port rewrites. It is written
# from the requirement, and asserted to cover every Claude-specific term the
# generators and the mirrored substitution sets can produce, so a term added
# upstream lands here rather than passing unnoticed. The *kind* is this property's
# reading; the catalog entry's `name` is the report's own vocabulary and is read
# from `DECLARED_CLAUDE_TERMS` rather than restated.
#
# Exactly k, in both directions
# -----------------------------
# The findings are compared as an ordered sequence against the oracle's
# references, so a scan that reported the first hit in a document and stopped, or
# recorded one aggregate verdict, or reported a line of prose that carries no
# reference, all fail here. Two documents in every example carry nothing to
# report — a clean manifest, and Kiro-authored prose naming
# `senzing-bootcamp-claude-plugin` and the `.claude-plugin/plugin.json` segment
# the port repoints — both of which say "claude" and neither of which is a
# Claude-specific *model* reference. The other direction is asserted by repair:
# rewriting exactly the reported references to their Kiro equivalents, and nothing
# else, takes the same documents to zero findings, `passed`, and `tagAllowed`
# true, with their `INV-NNN` citations untouched.
#
# Where a reference is allowed to hide
# ------------------------------------
# Three seeded documents are ordinary prose; one seeds inside a fenced code block,
# because a `${CLAUDE_PLUGIN_ROOT}` shown as an example is still a reference a
# Bootcamper would read and copy; and one is a file whose bytes are not valid
# UTF-8, because a residual token in a file the validator declined to read is
# exactly the hit that must not be missed. `read_text` is asserted to refuse that
# file and `document_text` to read it lossily, so "nothing is skipped" is checked
# rather than assumed.
#
# The three-way distinction
# -------------------------
# `incomplete` earns its place only by being neither of the other two, so the same
# result is folded three times: beside a passing sibling with its hits
# (`incomplete`), beside that sibling after the repair (`passed`), and beside a
# structural failure (`failed`). A warning neither masks an error nor is masked by
# one, and only `passed` opens the gate. Failing closed is a `fail` as well, which
# is why this check's `unevaluated_code` is an `E_` code and why an empty tree
# declines to answer instead of recording a clean sweep.
#
# Deliberately out of scope: how deep the `INV-NNN` exemption goes is Property
# 25's subject, and what the *engine* rewrites is Property 8's. What this section
# asserts about the exemption is the pair R15 AC8 turns on, which `inv_prose()`
# supplies in every example — a citation is not itself a hit, and a genuine
# residual reference sitting beside one in the same document is reported anyway.
#
# `_CITATION` and `_RESOLVED_TAG` are shared with the sections above.

#: R12 AC2's three categories, R10 AC2's root path token, and the client names the
#: `client-names` set rewrites — each as the literal a ported document would still
#: carry, paired with the kind that literal belongs to. Written from the
#: requirement rather than from the validator's patterns, and asserted below to
#: cover every Claude-specific term the generators can emit.
#:
#: Every model and effort literal is Claude-*qualified*, in the prose spelling or
#: the Anthropic API id spelling. That is the requirement's reading: Kiro offers the
#: same model tiers and the same reasoning-effort levels, so a bare `Sonnet 5` is
#: the Kiro guidance rather than a reference that survived the port.
_SEED_TERMS: Mapping[str, str] = {
    CLAUDE_ROOT_TOKEN: RESIDUAL_ROOT_TOKEN,
    "Claude Code": RESIDUAL_CLIENT_NAME,
    "Claude Desktop": RESIDUAL_CLIENT_NAME,
    "Claude Max plan": RESIDUAL_SUBSCRIPTION_PLAN,
    "Claude Sonnet 5": RESIDUAL_MODEL_NAME,
    "Claude Sonnet 4.5": RESIDUAL_MODEL_NAME,
    "claude-sonnet-5": RESIDUAL_MODEL_NAME,
    "Claude reasoning effort": RESIDUAL_EFFORT_SETTING,
    "ultrathink": RESIDUAL_EFFORT_SETTING,
}

#: What the transformation should have written instead, by kind. The repair clause
#: applies these; none of them is itself a term, which is why the repaired
#: documents are clean rather than merely different.
_KIRO_REWRITES: Mapping[str, str] = {
    RESIDUAL_ROOT_TOKEN: "${PLUGIN_ROOT}",
    RESIDUAL_CLIENT_NAME: "Kiro",
    RESIDUAL_SUBSCRIPTION_PLAN: "<kiro-plan>",
    RESIDUAL_MODEL_NAME: "<kiro-model>",
    RESIDUAL_EFFORT_SETTING: "<kiro-effort>",
}

#: The declared catalog entry per kind, for the `term` name a finding carries.
#: One entry per kind, asserted below rather than assumed.
_DECLARED_BY_KIND: Mapping[str, ClaudeTerm] = {
    term.kind: term for term in DECLARED_CLAUDE_TERMS
}

#: One seeded reference per line, in a sentence ported documentation could carry.
#: The prefix ends and the suffix begins with a space, so the seeded literal is
#: whitespace-bounded on both sides and the whole of it is the reference — nothing
#: here asks a word-bounded pattern to match across a seam.
_SEED_PREFIX = "Ported guidance still names the "
_SEED_SUFFIX = " here.\n"

#: A fenced block to seed inside. Code fences are not blanked by this check, and
#: the reason is R12 AC3's subject: an example is documentation too.
_FENCE_OPEN = "An example a Bootcamper would copy:\n\n```bash\n"
_FENCE_CLOSE = "```\n"

#: Bytes no UTF-8 decoder can read, and the text a lossy decode produces from
#: them. Spelled out rather than computed, so the decode is a claim this section
#: makes about `document_text` instead of a value it borrows from it.
_UNDECODABLE = b"\xff\xfe\x00\x01\n"
_UNDECODABLE_TEXT = "\ufffd\ufffd\x00\x01\n"

#: Kiro-authored prose naming the template repository and the manifest path the
#: port repoints. Both spellings carry "claude" and neither is a Claude-specific
#: model reference, so reporting either would make the Power's own provenance note
#: a defect on every run.
_PROVENANCE_NOTE = (
    "Ported from senzing-bootcamp-claude-plugin, where the manifest sat at "
    ".claude-plugin/plugin.json before the port repointed it to plugin.json.\n"
    "Kiro reads plugin.json from the Power root.\n"
)

#: A manifest with nothing to report, so the sweep is asserted to cover every file
#: in the tree rather than only the Markdown under `skills/`.
_CLEAN_MANIFEST = '{"version": "0.5.1"}\n'

#: The documents this property builds: ported prose, a ported skill body, a skill
#: body citing invariants, a fenced example, a binary asset, the provenance note,
#: and the manifest.
_PORTED_REFERENCE = "skills/bootcamp-onboarding/references/model-guidance.md"
_PROVENANCE_DOCUMENT = "skills/bootcamp-onboarding/references/provenance.md"
_PORTED_SKILL = "skills/bootcamp-onboarding/SKILL.md"
_CITING_SKILL = "skills/bootcamp-modeling/SKILL.md"
_PORTED_EXAMPLE = "skills/bootcamp-modeling/references/examples.md"
_PORTED_ASSET = "skills/bootcamp-onboarding/assets/diagram.png"

#: The `inv_prose()` cases this property relies on, so a generator change that
#: dropped one fails here instead of quietly narrowing the property.
_REQUIRED_PROSE_CASES = frozenset(
    {
        "zero_citations",
        "one_citation",
        "many_citations",
        "discounted_citations",
        "citations_in_code_fence",
        "citation_adjacent_to_residual",
    }
)

#: Results from a different check, so a status below can only have come from
#: `residual-claude-refs` — or, for the failing one, from an error beside it.
_CLEAN_SCHEMA_SIBLING = CheckResult(id="plugin-schema", target=PLUGIN_MANIFEST)
_BROKEN_SCHEMA_SIBLING = CheckResult(
    id="plugin-schema",
    target=PLUGIN_MANIFEST,
    findings=(
        Finding(
            code=E_SCHEMA_INVALID,
            message="the Build_Manifest is not a JSON object",
            target=PLUGIN_MANIFEST,
        ),
    ),
)


@dataclass(frozen=True)
class _Seeded:
    """One residual reference put into a document, and exactly where it went."""

    source: str
    term: str
    kind: str
    line: int
    column: int
    offset: int


def _coordinate(text: str, offset: int) -> tuple[int, int]:
    """`offset`'s one-based line and column — the convention a location spells.

    Recomputed from the finished document, so the coordinates the construction
    below recorded are checked against the text they describe before either is
    compared against a finding.
    """
    return text.count("\n", 0, offset) + 1, offset - text.rfind("\n", 0, offset)


def _spelled_as_a_reference(text: str, term: str) -> bool:
    """Whether `text` spells `term` as a word rather than inside one.

    R12 AC2's categories are references a Bootcamper would *read* — "the Claude
    Max plan", not the tail of a longer token — and the catalog is word-bounded
    for that reason: `Sonnetize` is not a model name and `Claude Product` is not a
    plan. `file_content()`'s `adjacent_tokens` case concatenates a term with
    itself, which spells neither copy as a word, so the non-vacuity clause below
    is gated on this reading of the requirement rather than on `in`.
    """
    delimited = rf"(?<![0-9A-Za-z_]){re.escape(term)}(?![0-9A-Za-z_])"
    return re.search(delimited, text) is not None


def _ported(case: FileContentCase) -> str:
    """`case.text` with its own declared substitution set applied, in order.

    The document the transform would write, computed with `str.replace` per entry
    rather than by calling the engine: Property 8 owns what the engine does with a
    declared set, and what this property needs from the port is a base whose
    Claude-specific terms are gone, so that every reference below is one it seeded
    deliberately.
    """
    text = case.text
    for substitution in case.substitutions:
        text = text.replace(substitution.find, substitution.replace)
    return text


def _seed(
    source: str, base: str, terms: Sequence[str]
) -> tuple[str, tuple[_Seeded, ...]]:
    """`base` with one seeded reference appended per entry of `terms`.

    One reference per line, and the coordinates are arithmetic over the lines this
    function assembled: the line is the base's line count plus the seed's
    position, and the column is the prefix's length plus one. Nothing is read back
    out of the produced text.
    """
    assert base.endswith("\n")
    text = base
    seeded: list[_Seeded] = []
    for position, term in enumerate(terms):
        seeded.append(
            _Seeded(
                source=source,
                term=term,
                kind=_SEED_TERMS[term],
                line=base.count("\n") + position + 1,
                column=len(_SEED_PREFIX) + 1,
                offset=len(text) + len(_SEED_PREFIX),
            )
        )
        text += f"{_SEED_PREFIX}{term}{_SEED_SUFFIX}"
    return text, tuple(seeded)


def _generated(source: str, base: str, terms: Sequence[str]) -> tuple[_Seeded, ...]:
    """The references `inv_prose()` seeded into `base`, at its coordinates.

    Located in the base rather than in the finished document, because a seeded
    line may repeat the same literal; appending lines cannot move an offset, so
    the coordinates hold for the assembled document too.
    """
    found: list[_Seeded] = []
    for term in terms:
        assert base.count(term) == 1
        offset = base.index(term)
        line, column = _coordinate(base, offset)
        found.append(
            _Seeded(
                source=source,
                term=term,
                kind=_SEED_TERMS[term],
                line=line,
                column=column,
                offset=offset,
            )
        )
    return tuple(found)


def _reference(seed: _Seeded) -> ResidualReference:
    """The reference a seeded hit must come back as.

    `kind` and the matched text are this property's; `term` is the catalog entry's
    name, which is report vocabulary rather than criterion, so it is read from the
    declared catalog instead of respelled.
    """
    return ResidualReference(
        source=seed.source,
        kind=seed.kind,
        term=_DECLARED_BY_KIND[seed.kind].name,
        text=seed.term,
        line=seed.line,
        column=seed.column,
        offset=seed.offset,
        origin=TERM_ORIGIN_DECLARED,
    )


def _rewritten(text: str, seeds: Sequence[_Seeded]) -> str:
    """`text` with every reference in `seeds` replaced by its Kiro equivalent.

    Right to left, from the oracle's own coordinates rather than from the
    findings, so the repair clause is not asking the check where to repair.
    """
    for seed in sorted(seeds, key=lambda seed: seed.offset, reverse=True):
        end = seed.offset + len(seed.term)
        assert text[seed.offset : end] == seed.term
        text = text[: seed.offset] + _KIRO_REWRITES[seed.kind] + text[end:]
    return text


def _assert_reports_exactly_the_seeded_references(
    documents: Mapping[str, str], seeded: Sequence[_Seeded]
) -> CheckResult:
    """Scan `documents` and check the result against `seeded`, and nothing else.

    One recorded result for the whole sweep, carrying one warning-severity finding
    per seeded reference — each naming its source document and its position within
    that document *(R12 AC3)* — and folding to `incomplete` with `tagAllowed`
    false exactly when there is one *(R12 AC4)*.
    """
    expected = tuple(
        _reference(seed)
        for seed in sorted(seeded, key=lambda seed: (seed.source, seed.offset))
    )

    # One document at a time first: the scan of a text is exactly that document's
    # references, in order — not a prefix of them, and nothing from the prose
    # around them.
    for source in sorted(documents):
        assert residual_references(documents[source], source=source) == tuple(
            reference for reference in expected if reference.source == source
        )

    result = residual_claude_result(documents)
    assert result.id == "residual-claude-refs"
    # A function of the documents alone: the same mapping twice, the same result.
    assert residual_claude_result(documents) == result
    assert result.findings == residual_findings(expected)
    assert len(result.findings) == len(seeded)

    for finding, reference in zip(result.findings, expected):
        assert finding.code == W_RESIDUAL_CLAUDE_REF
        assert finding.severity == SEVERITY_WARNING
        # R12 AC3: the source document, and the location within that document.
        assert finding.target == reference.source
        assert reference.location == f"line {reference.line} column {reference.column}"
        assert finding.location == reference.location
        assert reference.source in finding.message
        assert repr(reference.text) in finding.message
        assert reference.location in finding.message
        assert finding.details == reference.details()
        payload = finding.to_json()
        assert payload["code"] == W_RESIDUAL_CLAUDE_REF
        assert payload["severity"] == SEVERITY_WARNING
        assert payload["target"] == reference.source
        assert payload["location"] == reference.location
        assert payload["kind"] == reference.kind
        assert payload["match"] == reference.text

    # The recorded payload a Maintainer reads: what was swept, what the catalog
    # was, R10 AC2's count stated outright, and one compact row per hit.
    counts = {
        kind: sum(1 for reference in expected if reference.kind == kind)
        for kind in RESIDUAL_KINDS
    }
    assert result.extra["documents"] == len(documents)
    assert result.extra["terms"] == len(DECLARED_CLAUDE_TERMS)
    assert result.extra["contractTerms"] == 0
    assert result.extra["byKind"] == counts
    assert result.extra["rootTokenOccurrences"] == counts[RESIDUAL_ROOT_TOKEN]
    assert result.extra["invariantCitations"] == sum(
        len(_CITATION.findall(text)) for text in documents.values()
    )
    assert result.extra["hits"] == [
        {
            "source": reference.source,
            "term": reference.term,
            "kind": reference.kind,
            "match": reference.text,
            "location": reference.location,
            "line": reference.line,
            "column": reference.column,
        }
        for reference in expected
    ]

    # R12 AC4: one hit is enough to downgrade the outcome, and the downgrade is
    # the severity of the code rather than anything assigned here.
    clean = not seeded
    assert len({RESULT_PASS, RESULT_WARN, RESULT_FAIL}) == 3
    assert result.result == (RESULT_PASS if clean else RESULT_WARN)
    assert result.passed is clean
    assert fold_status((result,)) == (STATUS_PASSED if clean else STATUS_INCOMPLETE)

    report = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_CLEAN_SCHEMA_SIBLING, result),
    )
    assert _CLEAN_SCHEMA_SIBLING.passed
    assert report.status == (STATUS_PASSED if clean else STATUS_INCOMPLETE)
    assert report.tag_allowed is clean
    assert report.failed_check_ids() == (() if clean else ("residual-claude-refs",))
    assert report.findings_for(W_RESIDUAL_CLAUDE_REF) == result.findings

    # The three-way distinction, over one result: `incomplete` is neither of the
    # other two, and an error beside a warning is still `failed` — a structurally
    # broken Power is a different Maintainer response from a content-incomplete
    # one, and neither of them opens the gate.
    assert len({STATUS_PASSED, STATUS_INCOMPLETE, STATUS_FAILED}) == 3
    assert report.status != STATUS_FAILED
    broken = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_BROKEN_SCHEMA_SIBLING, result),
    )
    assert _BROKEN_SCHEMA_SIBLING.result == RESULT_FAIL
    assert broken.status == STATUS_FAILED
    assert not broken.tag_allowed
    return result


# Feature: senzing-bootcamp-power, Property 9: Residual Claude-specific
# references are fully detected and downgrade the outcome
#
# Validates: Requirements 12.3, 12.4
@settings(max_examples=100)
@given(
    file_content(),
    inv_prose(),
    INV_PROSE_CASES["citation_adjacent_to_residual"],
    st.lists(st.sampled_from(sorted(_SEED_TERMS)), max_size=6),
    st.permutations(sorted(_SEED_TERMS)),
)
def test_residual_claude_references_are_detected_and_downgrade_the_outcome(
    content: FileContentCase,
    prose: InvProseCase,
    adjacent: InvProseCase,
    drawn: list[str],
    every_kind: list[str],
) -> None:
    # The generator cases and the oracle's coverage, asserted rather than assumed:
    # every Claude-specific literal the generators and the mirrored substitution
    # sets can emit is a term this property knows the kind of.
    assert _REQUIRED_PROSE_CASES <= set(INV_PROSE_CASES)
    assert set(CLAUDE_MODEL_REFERENCES) <= set(_SEED_TERMS)
    assert {
        entry.find
        for name, entries in SUBSTITUTION_SETS.items()
        if name in RESIDUAL_TERM_SETS
        for entry in entries
    } <= set(_SEED_TERMS)
    assert set(_SEED_TERMS.values()) == set(_DECLARED_BY_KIND) == set(_KIRO_REWRITES)
    assert len(_DECLARED_BY_KIND) == len(DECLARED_CLAUDE_TERMS)
    assert set(_SEED_TERMS.values()) <= set(RESIDUAL_KINDS)
    # The one kind no declared pattern carries: it exists for a term the contract
    # names and the categories do not classify, so nothing here can produce it.
    assert RESIDUAL_MODEL_GUIDANCE not in set(_SEED_TERMS.values())
    assert all(term.origin == TERM_ORIGIN_DECLARED for term in DECLARED_CLAUDE_TERMS)
    assert all(not term.from_contract for term in DECLARED_CLAUDE_TERMS)
    assert adjacent.residual_claude_refs != () and adjacent.citations != ()

    # R12 AC3, AC4: the gate this property drives. Its own code is a warning, and
    # failing closed is deliberately *not* that code — nothing scanned is a fail,
    # not a content problem the artifact has.
    registered = registered_check("residual-claude-refs")
    assert registered is not None
    assert registered.code == W_RESIDUAL_CLAUDE_REF
    assert registered.failure_code == E_CHECK_UNEVALUATED
    assert Finding(code=registered.code, message="m").severity == SEVERITY_WARNING
    assert Finding(code=registered.failure_code, message="m").severity == SEVERITY_ERROR

    # --- The ported base carries nothing to report -------------------------
    base = _ported(content)
    if any(_spelled_as_a_reference(content.text, term) for term in _SEED_TERMS):
        # The same document before the port is reported, so the clean baseline is
        # the substitutions' doing rather than the scanner's blindness
        # *(R12 AC2, Property 8's guarantee read at this gate)*.
        assert residual_references(content.text, source=_PORTED_REFERENCE) != ()
    assert residual_references(base, source=_PORTED_REFERENCE) == ()
    assert residual_references(_PROVENANCE_NOTE, source=_PROVENANCE_DOCUMENT) == ()
    assert residual_references(_CLEAN_MANIFEST, source=PLUGIN_MANIFEST) == ()

    # --- Seed k references across the ported documents ---------------------
    bases = {
        _PORTED_REFERENCE: base,
        _PORTED_SKILL: prose.text,
        _CITING_SKILL: adjacent.text,
        _PORTED_EXAMPLE: _FENCE_OPEN,
    }
    order = tuple(bases)
    plan: dict[str, list[str]] = {source: [] for source in order}
    for position, term in enumerate([*every_kind, *drawn]):
        plan[order[position % len(order)]].append(term)

    documents: dict[str, str] = {
        PLUGIN_MANIFEST: _CLEAN_MANIFEST,
        _PROVENANCE_DOCUMENT: _PROVENANCE_NOTE,
    }
    seeded: list[_Seeded] = []
    for source, text in bases.items():
        produced, placed = _seed(source, text, plan[source])
        if source == _PORTED_EXAMPLE:
            # Closed after the seeds: appending cannot move an offset, and a
            # reference inside a fence is a reference all the same.
            produced += _FENCE_CLOSE
        documents[source] = produced
        seeded.extend(placed)

    # The references `inv_prose()` seeded itself, beside the citations it wrote.
    for source, case in ((_PORTED_SKILL, prose), (_CITING_SKILL, adjacent)):
        seeded.extend(_generated(source, bases[source], case.residual_claude_refs))

    # A reference in a file no decoder can read: swept, not skipped, because a
    # token hiding in an unreadable file is the hit that must not be missed.
    asset, asset_seeds = _seed(_PORTED_ASSET, _UNDECODABLE_TEXT, (CLAUDE_ROOT_TOKEN,))
    documents[_PORTED_ASSET] = asset
    seeded.extend(asset_seeds)

    # k, by construction, and every kind the declared catalog carries.
    assert len(seeded) == (
        len(every_kind)
        + len(drawn)
        + 1
        + len(prose.residual_claude_refs)
        + len(adjacent.residual_claude_refs)
    )
    assert {seed.kind for seed in seeded} == set(_DECLARED_BY_KIND)
    for seed in seeded:
        # The construction's coordinates and the coordinate convention agree, and
        # the literal really is at the offset the construction claims.
        text = documents[seed.source]
        assert _coordinate(text, seed.offset) == (seed.line, seed.column)
        assert text[seed.offset : seed.offset + len(seed.term)] == seed.term

    # --- Clause 1: exactly k findings, each placed in its document ---------
    result = _assert_reports_exactly_the_seeded_references(documents, seeded)
    assert {finding.target for finding in result.findings} == {
        seed.source for seed in seeded
    }
    assert PLUGIN_MANIFEST not in {finding.target for finding in result.findings}
    assert _PROVENANCE_DOCUMENT not in {finding.target for finding in result.findings}

    # --- Clause 2: the registered check reads the whole produced tree -------
    tail = asset[len(_UNDECODABLE_TEXT) :].encode("utf-8")
    tree = PowerTree.from_mapping(
        {
            **{path: text for path, text in documents.items() if path != _PORTED_ASSET},
            _PORTED_ASSET: _UNDECODABLE + tail,
        }
    )
    assert {path: document_text(tree, path) for path in tree.paths} == documents
    with pytest.raises(Unevaluable):
        # What a parsing check declines to read, this one reads lossily.
        tree.read_text(_PORTED_ASSET)
    assert claude_terms() == DECLARED_CLAUDE_TERMS
    context = ValidationContext(tree=tree, tag=_RESOLVED_TAG)
    assert check_residual_claude_refs(context) == result

    # A contract is used when supplied and never required: it contributes the
    # literal terms its sets declare, each naming the set it came from, and it
    # never blinds the scan. The committed contract adds none — every literal it
    # writes is already covered by a declared pattern.
    contract = load_contract()
    catalog = claude_terms(contract)
    extras = contract_claude_terms(contract)
    assert catalog == extras + DECLARED_CLAUDE_TERMS
    for term in extras:
        assert term.from_contract
        assert term.origin in RESIDUAL_TERM_SETS
        assert term.kind == RESIDUAL_TERM_SETS[term.origin]
    with_contract = check_residual_claude_refs(
        ValidationContext(tree=tree, tag=_RESOLVED_TAG, contract=contract)
    )
    assert with_contract == residual_claude_result(documents, terms=catalog)
    assert {(hit["source"], hit["location"]) for hit in result.extra["hits"]} <= {
        (hit["source"], hit["location"]) for hit in with_contract.extra["hits"]
    }

    # --- Clause 3: the citation exemption covers the citation, and only it ---
    reported = {
        (finding.target, finding.details["offset"]) for finding in result.findings
    }
    for source, case in ((_PORTED_SKILL, prose), (_CITING_SKILL, adjacent)):
        text = documents[source]
        # Two citation scanners, the generator's and this file's, one answer.
        assert tuple(_CITATION.findall(text)) == case.citations
        cited = {
            index
            for match in _CITATION.finditer(text)
            for index in range(match.start(), match.end())
        }
        assert not cited & {offset for target, offset in reported if target == source}
        for finding in result.findings:
            if finding.target == source:
                assert "INV-" not in finding.details["match"]
    # ...and the genuine reference beside a citation in the same document is
    # reported anyway, which is the case `inv_prose()` exists to put here.
    beside = _generated(_CITING_SKILL, adjacent.text, adjacent.residual_claude_refs)
    assert len(beside) >= 1
    assert {(seed.source, seed.offset) for seed in beside} <= reported

    # --- Clause 4: rewriting exactly the reported references flips it -------
    # The other direction of "exactly when": nothing else about the documents
    # changes, so the verdict flipped because the references are gone.
    repaired = {
        source: _rewritten(
            text, tuple(seed for seed in seeded if seed.source == source)
        )
        for source, text in documents.items()
    }
    assert repaired != documents
    for source, text in repaired.items():
        assert _CITATION.findall(text) == _CITATION.findall(documents[source])
    swept = _assert_reports_exactly_the_seeded_references(repaired, ())
    assert swept.findings == ()
    assert swept.extra["rootTokenOccurrences"] == 0
    assert swept.extra["invariantCitations"] == result.extra["invariantCitations"]

    # --- Clause 5: nothing scanned is not a clean sweep --------------------
    with pytest.raises(Unevaluable):
        check_residual_claude_refs(
            ValidationContext(tree=PowerTree.from_mapping({}), tag=_RESOLVED_TAG)
        )

# ===========================================================================
# Property 10: Ported content is faithful to its rule kind
# ===========================================================================
#
# R10 AC3 and R7 AC15 are one guarantee stated over two kinds of content: a
# vendored asset arrives byte-for-byte, and a skill's learning objectives,
# instructional steps, and exercises arrive as the template wrote them. What makes
# both true is a single mechanism — **the rule kind that claims a file decides
# what may happen to its bytes, and nothing else does** — so this property is
# about the dispatch in `render_output` rather than about any one rule:
#
# `copy`        the source bytes, unmodified. No substitution, and no line-ending
#               normalization either: it is the one kind exempt from R16 AC8.
# `substitute`  the source, LF-normalized, with exactly the sets the rule names
#               applied in the rule's own order, and nothing else.
# `skill`       `substitute` over the document body, plus additive frontmatter
#               adaptation on the skill's own entry point. The body is where
#               R7 AC15's content lives, so the body is where the claim is made.
#
# How the two halves are told apart
# ---------------------------------
# A byte-equality check on a `copy` output proves nothing unless those bytes are
# bytes a substituting rule *would* have changed — prose nobody was going to
# rewrite passes it for free. So the same probe content is planted twice: once
# under a `copy` rule and once under a `substitute` rule. It carries every literal
# find term the contract's sets declare, the one line the contract's single
# anchored-regex entry rewrites, CRLF and lone-CR bytes, and a tail that is not
# valid UTF-8 at all. The copy output must hold every bit of that verbatim; the
# substitute output must hold none of the terms and no CR byte, and could not have
# been produced at all from content that failed to decode. That contrast is the
# property.
#
# The oracle, and what it delegates
# ---------------------------------
# The function under test is `render_output` — the kind dispatch. The substitution
# *mechanism* it dispatches to is Property 8's subject, verified there against an
# independent character scanner, so this section composes that verified primitive
# instead of re-spelling its oracle: the expected bytes are `apply_substitutions`
# over the sets **this test resolved from the contract document**, by the rule's
# own names and in the rule's own order. A dispatch that applied the wrong sets,
# applied any set to a `copy` rule, skipped the LF normalization, or substituted a
# skill's frontmatter instead of its body fails that comparison. Property 8's
# scanner is deliberately literal-only, and the committed contract declares one
# anchored-regex entry, which is the second reason it is not reused here.
#
# Three clauses carry no engine function at all, so the property does not rest on
# that one composition:
#
# * **Identity.** A ported file whose content no declared entry can match is
#   byte-identical to its LF-normalized source. That is R7 AC15 for every line a
#   substitution does not touch, and one probe is planted specifically to keep the
#   clause non-vacuous on every generated tree.
# * **Zero residual.** For every declared literal term that no replacement
#   reintroduces, the ported output holds none — R10 AC2's crisp reading, checked
#   here on content that really carried the term.
# * **Citations.** The multiset of inline `INV-NNN` references in a ported body is
#   identical to its template source's, counted with this file's own regex and
#   compared per named invariant: the honored `INV-052` and the discounted ones
#   alike, because a discount is about packaging construction and not about what
#   ported prose may cite (R15 AC7).
#
# Deliberately out of scope: `generate` output is rendered rather than ported
# (Properties 2 and 14), `kiro-owned` content has no template source (Property 21),
# `ignore` emits nothing (Property 5), and whether an adapted frontmatter field set
# is *complete* is Property 13's. What is asserted about frontmatter here is only
# that the adaptation left the template's `name` and `description` as it found them
# while the body went through the declared sets.
#
# `_transformable`, `_materialized_release`, `_read_tree`, `_RESOLVED_TAG`, and
# `_CITATION` are shared with the sections above.

#: The rule kinds whose output is *ported* template content, and so the kinds this
#: property is about.
_PORTED_KINDS = ("copy", "substitute", "skill")

#: The Agent_Plugins_Format facts this section reads paths and documents by: a
#: skill's entry-point filename, and the YAML frontmatter fence on its own line.
#: Spelled here rather than imported, because "where the body begins" is what the
#: `skill` kind's claim is stated over.
_ENTRY_POINT = "SKILL.md"
_FENCE = "---"

#: The line the contract's one anchored-regex entry rewrites, spelled here as the
#: text it matches — indentation included, because the entry is pinned to release
#: 0.5.1's formatting of that line. Stated rather than derived: a regex is not a
#: string a probe can be generated from. The test asserts that every regex entry
#: the contract declares matches the probe, so an edit that left one unexercised
#: fails loudly instead of quietly narrowing the property.
_ANCHORED_MANIFEST_LINE = '        ".claude-plugin",'

#: Line endings a `copy` output must keep and a `substitute` output must lose.
_CR_PROBE = "a line ending in CRLF\r\nand a lone CR here\rcontinuing.\n"

#: The tail every `copy` probe ends with: a PNG signature, a NUL, and a byte pair
#: that is not valid UTF-8. Content a substituting rule could not decode at all,
#: which is what makes "a `copy` rule never decodes its source" observable.
_COPY_ONLY_TAIL = b"\x89PNG\r\n\x1a\n\x00\xff\xfe"

#: Ported prose that no declared set names, citations included — the identity
#: case. Asserted against the contract below, so a newly declared find term that
#: happened to occur here fails rather than silently emptying the clause.
_UNTOUCHED_PROBE = (
    "Ported prose that no declared set names.\n"
    "Per INV-072 and INV-052, a citation is content, not a rewrite target.\n"
)

#: An extra frontmatter field carrying two terms the skill rules' own sets declare.
#: Substitution reaches a skill's **body**, not its frontmatter, and with no
#: template frontmatter value in release 0.5.1 carrying a declared term that
#: distinction is unobservable on the real corpus — so it is made observable here.
#: A frontmatter this survives verbatim is a frontmatter no set was applied to.
_FRONTMATTER_PROBE_FIELD = "templateNote"
_FRONTMATTER_PROBE = "Written for Claude Code under ${CLAUDE_PLUGIN_ROOT}."

#: Probe destinations and the rule that must claim each, one per flavor of rule
#: the engine ports content through. The rule id is stated so a contract edit that
#: moved a probe from `copy` to `substitute` fails here rather than leaving this
#: property checking the wrong guarantee.
_COPY_PROBES: Mapping[str, str] = {
    "scripts/vendor/rule-kind-probe.min.js": "scripts-vendor",
    "scripts/rule-kind-probe.png": "scripts-assets",
    "docs/rule-kind-probe.png": "docs-assets",
}
_SUBSTITUTE_PROBES: Mapping[str, str] = {
    "scripts/rule-kind-probe.py": "scripts-owned",
    "docs/rule-kind-probe.md": "docs",
}

#: The identity probe's own destination, claimed by the same `docs` rule.
_UNTOUCHED_PROBE_PATH = "docs/rule-kind-untouched.md"

#: The supporting document planted in every generated skill directory, so the
#: `skill` kind's non-entry-point branch — ordinary `substitute` over a file the
#: skill owns — is exercised on every example rather than when the generator
#: happens to emit a `references/` file.
_SKILL_PROBE_NAME = "rule-kind-probe.md"

#: Every literal find term the contract's named sets declare, taken from the
#: shared mirror rather than restated here. The test checks the mirror against the
#: committed contract, so drift in either direction is reported.
_MIRRORED_TERMS = tuple(
    item for entries in SUBSTITUTION_SETS.values() for item in entries
)


def _declared_literal_terms() -> tuple[str, ...]:
    """Every literal `find` term the *committed contract* declares, in order.

    The probe is built from these as well as from the mirror, because the mirror
    is a fixture: it carries one representative entry per set so the generators
    have something to seed, while the contract carries every term the port
    actually rewrites — the model ids, the command pairs, the client surfaces. A
    probe missing one of those would leave that entry unexercised by this
    property, and the assertion below would report it rather than the probe
    quietly narrowing.

    Regex entries are not here: a pattern is not a string a probe can be
    generated from, so the one the contract declares is spelled as
    `_ANCHORED_MANIFEST_LINE`, and every regex entry is asserted against the
    probe by the test.
    """
    contract = load_contract()
    return tuple(
        entry.find
        for name, entries in contract.substitution_sets.items()
        for entry in transform.parse_substitution_set(name, entries).entries
        if not entry.is_regex
    )

#: `inv_prose()` cases guaranteed to carry at least one citation, drawn alongside
#: the composite so the citation clause is exercised deliberately, not by luck.
_CITED_PROSE_CASES = (
    "one_citation",
    "many_citations",
    "discounted_citations",
    "citations_in_code_fence",
    "citation_adjacent_to_residual",
)


def _lf(data: bytes) -> bytes:
    """CRLF and lone CR to LF: R16 AC8's normalization, written here.

    Two lines rather than a call into the engine, because "which kinds normalize
    line endings and which do not" is exactly what this property measures.
    """
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _fenced_block_end(text: str) -> int | None:
    """Index of the line closing a leading `---` fence, or None if there is none.

    Derived from the Agent_Plugins_Format's own definition — a document's
    frontmatter is its leading fenced block — rather than read from the engine's
    splitter. An opening fence with no closing fence is a thematic break in prose,
    not frontmatter.
    """
    lines = text.split("\n")
    if not lines or lines[0] != _FENCE:
        return None
    for index in range(1, len(lines)):
        if lines[index] == _FENCE:
            return index
    return None


def _body_after_frontmatter(text: str) -> str:
    """Everything after a leading fenced block, or the whole document."""
    end = _fenced_block_end(text)
    if end is None:
        return text
    return "\n".join(text.split("\n")[end + 1 :])


def _frontmatter_fields(text: str) -> Mapping[str, Any] | None:
    """The leading fenced block's fields, or None when the document has no block."""
    end = _fenced_block_end(text)
    if end is None:
        return None
    loaded = yaml.safe_load("\n".join(text.split("\n")[1:end]))
    assert isinstance(loaded, Mapping), text[:200]
    return loaded


def _is_skill_entry_point(path: str) -> bool:
    """Whether `path` is a skill's own entry point, `skills/<name>/SKILL.md`.

    R8 AC1 fixes that shape, so the test reads it off the path rather than asking
    the engine which of its outputs it decided to adapt frontmatter on. A
    `SKILL.md` nested deeper is a supporting document and is ported as ordinary
    content.
    """
    segments = path.split("/")
    return (
        len(segments) == 3
        and segments[0] == "skills"
        and segments[2] == _ENTRY_POINT
    )


def _declared_sets(
    contract: Contract, rule: transform.Rule
) -> tuple[transform.SubstitutionSet, ...]:
    """The substitution sets `rule` declares, resolved here from the contract.

    The rule's own `substitutions` list, in the rule's order, looked up in the
    contract's `substitutionSets` mapping and parsed through the entry-shape
    parser — the same primitive Property 8's section uses to turn contract data
    into applicable entries. The *selection* is what this property pins: the sets
    a kind applies are the ones its rule names, all of them, in that order, and no
    others.
    """
    assert len(set(rule.substitutions)) == len(rule.substitutions), rule.id
    resolved: list[transform.SubstitutionSet] = []
    for name in rule.substitutions:
        assert name in contract.substitution_sets, (rule.id, name)
        resolved.append(
            transform.parse_substitution_set(name, contract.substitution_sets[name])
        )
    return tuple(resolved)


@lru_cache(maxsize=None)
def _anchored(source: str) -> re.Pattern[str]:
    """One `regex` entry's pattern, line-anchored the way the contract reads it."""
    return re.compile(source, re.MULTILINE)


def _names_anything(text: str, entries: Iterable[transform.Substitution]) -> bool:
    """Whether any entry could match `text` at all — the identity clause's guard."""
    return any(
        _anchored(entry.find).search(text) is not None
        if entry.is_regex
        else entry.find in text
        for entry in entries
    )


def _literal_prefix(pattern: str) -> str:
    """The leading all-literal segments of a source glob, as a path prefix.

    What a directory `dest` stands in for: the contract carries the remainder of a
    source path below this prefix through unchanged, so this is where "the same
    relative location" (R10 AC3) is computed from — derived here rather than read
    back from the plan, so a plan that relocated an asset fails instead of
    agreeing with itself.
    """
    kept: list[str] = []
    for segment in pattern.strip("/").split("/"):
        if any(character in segment for character in "*?["):
            break
        kept.append(segment)
    return "/".join(kept)


def _frontmatter_block(fields: Mapping[str, Any]) -> str:
    """Serialize frontmatter fields as a fenced block — input, not an oracle.

    A drawn `frontmatter()` case plus one extra field, re-rendered rather than
    spliced into the case's own text so the block that reaches the engine is a
    block YAML round-trips.
    """
    body = yaml.safe_dump(
        dict(fields),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10**6,
    )
    return f"{_FENCE}\n{body}{_FENCE}\n"


def _expected_description(
    contract: Contract, output_path: str, declared: object
) -> object:
    """The `description` the adaptation should write for one skill entry point.

    The template's own value, plus the sentence the contract's `skillTriggers`
    declares for that skill when it declares one and the description does not
    already carry it. Computed from the committed contract rather than restated,
    so declaring a phrase for another skill needs no edit here.
    """
    name = output_path.split("/")[-2]
    sentence = contract.skill_triggers.get(name)
    if sentence is None or not isinstance(declared, str) or sentence in declared:
        return declared
    stripped = declared.rstrip()
    return f"{stripped} {sentence}" if stripped else sentence


def _probe_text(prose: str) -> str:
    """Probe content: every declared term, the anchored line, CR bytes, prose.

    "Every declared term" is the mirror's terms and the committed contract's,
    deduplicated with order preserved so the probe is a deterministic function of
    the two.
    """
    spellings: list[str] = []
    for find in [item.find for item in _MIRRORED_TERMS] + list(
        _declared_literal_terms()
    ):
        if find not in spellings:
            spellings.append(find)
    terms = "\n".join(
        f"probe {position}: {find} trails here."
        for position, find in enumerate(spellings)
    )
    return (
        "Rule-kind fidelity probe.\n"
        f"{terms}\n"
        f"{_ANCHORED_MANIFEST_LINE}\n"
        f"{_CR_PROBE}"
        f"{prose}"
    )


def _with_fidelity_probes(
    tree: Mapping[str, TreeEntry],
    *,
    header: str,
    skill_prose: str,
    prose: str,
) -> dict[str, TreeEntry]:
    """Plant the probes into a generated tree, one per rule flavor.

    The same probe *text* reaches a `copy` rule and a `substitute` rule, which is
    what lets the two kinds' outputs be compared against each other rather than
    each against itself. Skill entry points additionally get a frontmatter block
    prepended, so the body/frontmatter distinction the `skill` kind rests on is
    real on every example instead of only on the frontmatter-less documents
    `template_tree()` happens to emit.
    """
    planted = dict(tree)
    names = sorted(
        path.split("/")[1] for path in tree if _is_skill_entry_point(path)
    )
    assert names, sorted(tree)

    owned = _probe_text(skill_prose).encode("utf-8")
    shared = _probe_text(prose).encode("utf-8")
    for name in names:
        entry = tree[f"skills/{name}/{_ENTRY_POINT}"]
        planted[f"skills/{name}/{_ENTRY_POINT}"] = TreeEntry(
            "file", header.encode("utf-8") + entry.content + owned
        )
        planted[f"skills/{name}/{_SKILL_PROBE_NAME}"] = TreeEntry("file", owned)

    for path in _SUBSTITUTE_PROBES:
        planted[path] = TreeEntry("file", shared)
    planted[_UNTOUCHED_PROBE_PATH] = TreeEntry(
        "file", _UNTOUCHED_PROBE.encode("utf-8")
    )
    for path in _COPY_PROBES:
        planted[path] = TreeEntry("binary", shared + _COPY_ONLY_TAIL)
    return planted


# Feature: senzing-bootcamp-power, Property 10: Ported content is faithful to its
# rule kind
#
# Validates: Requirements 7.15, 10.3
@settings(max_examples=100)
@given(
    template_tree(),
    inv_prose(),
    st.one_of(*(INV_PROSE_CASES[name] for name in _CITED_PROSE_CASES)),
    FRONTMATTER_CASES["valid"],
)
def test_ported_content_is_faithful_to_its_rule_kind(
    tree: Mapping[str, TreeEntry],
    prose: InvProseCase,
    cited: InvProseCase,
    header: FrontmatterCase,
) -> None:
    contract = load_contract()

    # Non-vacuous by construction, asserted rather than assumed: prose that really
    # carries a citation, a frontmatter block the engine will accept, and the
    # generator cases this property draws from.
    assert set(_CITED_PROSE_CASES) <= set(INV_PROSE_CASES)
    assert cited.citations
    assert header.defects == ()
    assert _FRONTMATTER_PROBE_FIELD not in header.fields

    # The frontmatter that reaches the engine: the drawn valid case plus one field
    # carrying terms the skill rules declare, so "substitution reaches the body and
    # not the frontmatter" is a claim with something to stand on.
    block = _frontmatter_block(
        {**header.fields, _FRONTMATTER_PROBE_FIELD: _FRONTMATTER_PROBE}
    )
    assert _frontmatter_fields(block) == {
        **header.fields,
        _FRONTMATTER_PROBE_FIELD: _FRONTMATTER_PROBE,
    }

    source_tree = _with_fidelity_probes(
        _transformable(tree, contract),
        header=block,
        skill_prose=cited.text,
        prose=prose.text,
    )

    # Every probe is claimed by the rule — and the kind — it was planted for.
    for path, rule_id in _COPY_PROBES.items():
        claimed = contract.classify(path).rule
        assert claimed is not None and claimed.id == rule_id, path
        assert claimed.kind == "copy", path
    for path, rule_id in {
        **_SUBSTITUTE_PROBES,
        _UNTOUCHED_PROBE_PATH: "docs",
    }.items():
        claimed = contract.classify(path).rule
        assert claimed is not None and claimed.id == rule_id, path
        assert claimed.kind == "substitute", path

    # The probe carries every term the *committed contract* declares, in whichever
    # shape it declares it, and the identity probe carries none of them. Both are
    # checked against the contract rather than against the shared mirror, so a
    # newly declared entry cannot leave this property quietly narrower.
    probe = _probe_text(prose.text)
    for name, entries in contract.substitution_sets.items():
        for entry in transform.parse_substitution_set(name, entries).entries:
            if entry.is_regex:
                assert _anchored(entry.find).search(probe) is not None, (
                    name,
                    entry.find,
                )
            else:
                assert entry.find in probe, (name, entry.find)
            assert not _names_anything(_UNTOUCHED_PROBE, (entry,)), (name, entry.find)
    for item in _MIRRORED_TERMS:
        assert item.find in probe, item.find

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source, _ = _materialized_release(root, source_tree, "release")
        staging = root / "staging"

        plan = build_plan(contract, source, tag=_RESOLVED_TAG, staging=staging)
        result = write_staging(plan)
        outputs, _ = plan_destinations(plan)
        staged = _read_tree(staging)
        rows = {
            row["path"]: row
            for row in json.loads(staged[MANIFEST_FILENAME])["files"]
        }
        assert len(result.outputs) == len(outputs)

        ported: dict[str, int] = {kind: 0 for kind in _PORTED_KINDS}
        entry_points = 0
        identities = 0
        copied_probes: list[bytes] = []

        for output in outputs:
            kind = output.rule.kind
            if kind not in _PORTED_KINDS:
                continue
            ported[kind] += 1
            origin = output.origin.read_bytes()
            produced = staged[output.path]

            if kind == "copy":
                # --- Clause 1: `copy` is the source bytes, unmodified ---------
                # Structural, not merely intended: a `copy` rule cannot declare a
                # substitution set, so there is nothing to apply to its bytes.
                assert output.rule.substitutions == (), output.rule.id
                assert produced == origin, output.path
                # The Build_Manifest records the file as written, so byte-for-byte
                # is recorded byte-for-byte too (R16 AC9).
                assert rows[output.path]["sha256"] == sha256_hex(origin), output.path

                if output.source_path is None:
                    # The Power's own `LICENSE`: a synthetic `copy` rule with no
                    # template source and a file `dest`, so the location clause
                    # below does not apply to it (R14 AC3).
                    assert output.rule.source is None
                    continue

                # --- Clause 2: at the same relative location (R10 AC3) --------
                assert output.source_path.startswith(f"{TEMPLATE_PLUGIN_ROOT}/")
                relative = output.source_path[len(TEMPLATE_PLUGIN_ROOT) + 1 :]
                prefix = _literal_prefix(output.rule.source or "")
                assert relative.startswith(f"{prefix}/"), relative
                remainder = relative[len(prefix) + 1 :]
                assert output.path in tuple(
                    dest.rstrip("/") + "/" + remainder
                    for dest in output.rule.dest
                    if dest.endswith("/")
                ), (output.path, remainder)

                if relative in _COPY_PROBES:
                    copied_probes.append(produced)
                continue

            # --- Clauses 3 and 4: exactly the declared sets, and nothing else --
            sets = _declared_sets(contract, output.rule)
            assert sets, output.rule.id
            entries = tuple(entry for subset in sets for entry in subset.entries)

            text = _lf(origin).decode("utf-8")
            produced_text = produced.decode("utf-8")
            is_entry_point = kind == "skill" and _is_skill_entry_point(output.path)
            body = _body_after_frontmatter(text) if is_entry_point else text
            expected = transform.apply_substitutions(
                body, sets, what=f"Property 10 oracle for {output.path}"
            )

            if is_entry_point:
                entry_points += 1
                # `skill` is `substitute` over the body plus additive frontmatter
                # adaptation: the body is the source body with exactly the
                # declared sets applied, and the template's own `name` and
                # `description` come through as the adaptation found them.
                produced_body = _body_after_frontmatter(produced_text)
                assert produced_body == expected, output.path
                adapted = _frontmatter_fields(produced_text)
                declared = _frontmatter_fields(text)
                assert adapted is not None and declared is not None, output.path
                assert adapted["name"] == declared["name"], output.path
                # `description` comes through as the adaptation found it, plus the
                # one sentence the contract declares for this skill when it
                # declares one (R8 AC6). Additive either way: the template's
                # description is a prefix of the produced one, and the only thing
                # that may follow it is contract data.
                assert adapted["description"] == _expected_description(
                    contract, output.path, declared["description"]
                ), output.path
                # The frontmatter probe carries two terms this rule's sets name and
                # survives them, so the sets reached the body and stopped there.
                assert (
                    adapted[_FRONTMATTER_PROBE_FIELD] == _FRONTMATTER_PROBE
                ), output.path
                assert _names_anything(_FRONTMATTER_PROBE, entries), output.rule.id
            else:
                produced_body = produced_text
                assert produced_text == expected, output.path

                # Identity: content no declared entry can match is byte-identical
                # to its LF-normalized source (R7 AC15, R10 AC3 for text).
                if not _names_anything(text, entries):
                    assert produced == _lf(origin), output.path
                    identities += 1

            # Zero residual: every declared literal term that no replacement
            # reintroduces is gone from the ported output (R10 AC2's crisp
            # reading). `script-paths` is the one set whose replacement carries
            # its own find term, and it is skipped by that test rather than by
            # name.
            reintroduced = frozenset(
                entry.find
                for entry in entries
                if not entry.is_regex
                and any(entry.find in other.replace for other in entries)
            )
            for entry in entries:
                if entry.is_regex or entry.find in reintroduced:
                    continue
                assert entry.find not in produced_body, (output.rule.id, entry.find)

            # Citations: the multiset in a ported body is its source's, in the same
            # document order, and equal per named invariant — the honored INV-052
            # and the discounted ones alike (R15 AC7).
            before = _CITATION.findall(body)
            after = _CITATION.findall(produced_body)
            assert sorted(after) == sorted(before), output.path
            assert after == before, output.path
            for invariant in (HONORED_INVARIANT, *DISCOUNTED_INVARIANTS):
                assert after.count(invariant) == before.count(invariant), (
                    output.path,
                    invariant,
                )

        # --- The contrast: the same bytes under `copy` and under `substitute` ---
        # Every term the substituting probes had rewritten out of them above is
        # still here, verbatim; so are the CR bytes a `substitute` rule
        # normalizes; and so is a tail that is not UTF-8 at all, which no
        # substituting rule could have decoded.
        assert len(copied_probes) == len(_COPY_PROBES)
        for data in copied_probes:
            assert data.endswith(_COPY_ONLY_TAIL)
            assert b"\r\n" in data and b"\r" in data.replace(b"\r\n", b"")
            assert _ANCHORED_MANIFEST_LINE.encode("utf-8") in data
            for item in _MIRRORED_TERMS:
                assert item.find.encode("utf-8") in data, item.find

        # Every kind the property speaks about produced something to check, and
        # both of the `skill` kind's branches were taken.
        for kind in _PORTED_KINDS:
            assert ported[kind] >= 1, kind
        assert entry_points >= 1
        assert ported["skill"] > entry_points
        assert identities >= 1

# ===========================================================================
# Property 11: Script layout is preserved and dangling asset references are
# detected
# ===========================================================================
#
# R10 AC1 reads like a filing convention and is not one. The template's hook
# scripts import one another as same-directory Python modules — `import
# recap_checkpoint`, `import docker_lifecycle` — so the only placement that keeps
# them working is one directory holding all of them, which is why the contract
# maps the whole template `scripts/` tree onto a single owning skill's `scripts/`
# (design defect **D4**). The per-skill destination R10 AC1 originally required
# would have shipped a Power whose hooks fail at runtime with an ImportError, on
# a machine nobody tests. So the layout is the guarantee, and R10 AC6 is the gate
# that keeps it: both halves are driven here, over one tree, in that order.
#
# What "preserved" is measured as
# ------------------------------
# The engine ports a generated script tree, and each ported script's destination
# is computed from its *source* path rather than read back off the plan: the
# path below `scripts/` — file name and relative sub-structure alike — appended
# to the one root the contract declares. A plan that renamed a script, flattened
# `scripts/helpers/`, or split the set across two skills disagrees with that
# arithmetic instead of agreeing with itself. `ported_scripts_directory` reads
# that root from the contract, so where the set lands stays a contract edit
# (R3 AC4), and the root is asserted to be a single owning skill's `scripts/`.
#
# Then the gate, on what actually came out: every same-directory module import
# resolves, and every script and asset a ported script or a hook definition names
# exists in the produced Power.
#
# The failure D4 exists to prevent
# --------------------------------
# `module-not-colocated` is that failure, and it is the reason this property
# seeds placements the contract will not produce. Three of them, drawn one per
# example: a sibling skill's `scripts/` — the per-skill distribution R10 AC1 once
# required — a subdirectory *below* the owning root, which is under `scripts/`
# and still not same-directory, and the Power root. Each breaks an import that
# resolved in the template, and the finding names where the module landed.
# `module-unported` is the other way it fails: the release ships the module, the
# port dropped it, and nothing in the Power provides it.
#
# Both halves of R10 AC4
# ----------------------
# A dangling reference is caught twice, by design, and the two catches are not
# redundant. On the *source* side the transform halts before writing a byte: a
# ported script naming a vendored asset the template does not ship produces one
# finding per reference, naming the script and the asset, and the destination
# `scripts/` tree is never touched. On the *Power* side the validator answers the
# same question about what shipped, over four populations that must exist —
# vendored assets, Python modules, whatever the release ships beside its scripts,
# and the exact path a hook's command string resolves to. Seeding a script the
# engine would have halted on is how the second catch is shown to be a real gate
# rather than a restatement of the first.
#
# Exactly the violating set, and two oracles
# ------------------------------------------
# The findings are compared as a set against a criteria oracle written here —
# this section's own import scanner, its own provider map, its own reference
# reader, its own hook-command reader — and against the construction, which says
# which seed owes which finding. Neither oracle asks the validator what it
# expected, and every reference the validator extracts is re-judged here against
# the Power's paths, so a check that reported the first broken import in a script
# and stopped, or reported one aggregate verdict, or reported a reference that
# resolves, fails against both.
#
# The zero cases
# --------------
# A Power carrying no Python module declines a verdict on its imports, and a
# Power with neither a Python module nor a hook definition declines a verdict on
# its references, because a pass recorded over an empty script set would let a
# Power that ships no scripts satisfy the gate. So does a run with no contract:
# where a hook's script has to sit is declared there and nowhere else.
#
# Deliberately out of scope: whether a ported script's *bytes* are faithful is
# Property 10's, whether the `${CLAUDE_PLUGIN_ROOT}` rewrite left residuals is
# Properties 8 and 9's, and whether a Hook_Command_String is well formed at all
# is Property 22's — a malformed command string is one defect with one owner, and
# this gate deliberately does not report it a second time.

#: The two checks this property drives.
_IMPORT_CHECK_ID = "script-imports"
_REFERENCE_CHECK_ID = "script-references"

#: The template directory the ported script set comes from, and the skill that
#: owns it in the Power. Spelled here rather than imported: "one owning skill's
#: scripts/" is the claim, so the test states the shape it expects and reads the
#: contract's answer against it.
_TEMPLATE_SCRIPTS_ROOT = "scripts"
_POWER_SKILLS_ROOT = "skills"
_OWNING_SKILL_NAME = "bootcamp-onboarding"

#: The two mutually-importing modules the corpus is built around, and the
#: underscore in each name is load-bearing: `_slug()` draws no underscore, so a
#: drawn script can never collide with a planted one. Asserted below.
_IMPORTED_MODULE = "recap_checkpoint"
_SIBLING_MODULE = "docker_lifecycle"

#: The five hook-invoked scripts the shipped hook definitions name. Stated here
#: and asserted equal to what those definitions actually spell, so a hook edit
#: fails loudly instead of quietly leaving the reference half with nothing to
#: satisfy. Every name is longer than `_slug()`'s eight-character ceiling.
_HOOK_SCRIPT_STEMS = (
    "checkpoint-tick",
    "feedback-capture",
    "session-start",
    "stop-nudge",
    "write-gate",
)

#: The one whose absence the hook-reference seed creates.
_DROPPED_HOOK_SCRIPT = "session-start.py"

#: A ported script one level below `scripts/`, so "relative sub-structure below
#: `scripts/`" is exercised on every example rather than when the generator
#: happens to draw a nested path. It imports nothing: a module in a
#: subdirectory importing one beside the owning root is itself a broken import,
#: which is the seeded condition below and not the compliant baseline.
_NESTED_SCRIPT = "helpers/graph_layout.py"

#: The vendored asset the base tree ships and a ported script names, and the
#: non-Python asset that sits beside the scripts. Both are references the
#: compliant Power satisfies, which is what keeps the vendored and
#: release-shipped populations non-empty before anything is seeded.
_VENDORED_ASSET = "vendor/d3.v7.min.js"
_SCRIPT_SIDE_ASSET = "senzing_logo_light.png"

#: What the seeds name and the Power does not carry.
_ABSENT_VENDORED_ASSET = "vendor/absent-bundle.min.js"
_ABSENT_PYTHON_MODULE = "absent_helper.py"
_DANGLING_VENDOR_SCRIPT = "dangling_vendor.py"
_DANGLING_MODULE_SCRIPT = "dangling_module.py"

#: The source-side seed: two ported scripts, each naming a vendored asset the
#: template does not ship, at two depths. The transform halts on both.
_HALTING_REFERENCES: Mapping[str, str] = {
    "halted_first.py": "vendor/absent-first.min.js",
    "halted_second.py": "vendor/deeper/absent-second.min.js",
}

#: Where the relocation seed puts a module that belongs beside its importer.
#: A sibling skill's `scripts/`, a subdirectory below the owning root, and the
#: Power root — three placements, none of which the contract produces, each of
#: which breaks an import that resolved in the template.
_RELOCATION_DIRECTORIES = (
    f"{_POWER_SKILLS_ROOT}/bootcamp-preparation/{_TEMPLATE_SCRIPTS_ROOT}",
    f"{_POWER_SKILLS_ROOT}/{_OWNING_SKILL_NAME}/{_TEMPLATE_SCRIPTS_ROOT}/helpers",
    "",
)

#: One seeded defect each, labeled by the finding kind its construction owes.
_SEED_DANGLING_VENDORED = "a script naming a vendored asset the Power lacks"
_SEED_DANGLING_MODULE = "a script naming a Python module the Power lacks"
_SEED_DROPPED_ASSET = "a release-shipped asset the port dropped"
_SEED_DROPPED_HOOK_SCRIPT = "a hook-invoked script the port dropped"
_REFERENCE_SEED_LABELS = (
    _SEED_DANGLING_VENDORED,
    _SEED_DANGLING_MODULE,
    _SEED_DROPPED_ASSET,
    _SEED_DROPPED_HOOK_SCRIPT,
)

_SEED_MODULE_RELOCATED = "a module moved out of its importer's directory"
_SEED_MODULE_UNPORTED = "a module the release ships and the port dropped"
_IMPORT_SEED_LABELS = (_SEED_MODULE_RELOCATED, _SEED_MODULE_UNPORTED)

#: A passing result from another check, so a withheld tag below can only have
#: come from the check under test.
_PASSING_SCRIPT_SIBLING = CheckResult(id="plugin-schema", target=PLUGIN_MANIFEST)

#: An `import x` / `from x import y` statement, read line by line. Spelled
#: independently of the engine's reader, and deliberately without `ast`: the
#: planted and generated scripts carry no import inside a docstring or a comment,
#: so a lenient line scanner and a parser agree on them, and the agreement is
#: asserted per script rather than assumed.
_IMPORT_STATEMENT_LINE = re.compile(
    r"^[ \t]*(?:import|from)[ \t]+(?P<module>[A-Za-z_][A-Za-z0-9_.\-]*)", re.MULTILINE
)

#: One path segment, and a final segment naming a file rather than a directory.
#: This section's own spelling of what a reference looks like.
_REFERENCE_PATH_SEGMENT = r"[A-Za-z0-9_@+~.-]+"
_REFERENCE_FILE_NAME = rf"{_REFERENCE_PATH_SEGMENT}\.[A-Za-z0-9]+"

#: A vendored asset, rooted at its `vendor/` segment; the lookbehind is what
#: keeps `myvendor/` and the word "vendored" out.
_VENDOR_REFERENCE = re.compile(
    rf"(?<![A-Za-z0-9_@+~.-]){VENDOR_SEGMENT}/"
    rf"(?:{_REFERENCE_PATH_SEGMENT}/)*{_REFERENCE_FILE_NAME}"
)

#: A quoted path literal naming a file.
_QUOTED_REFERENCE = re.compile(
    rf"""(?P<quote>['"])"""
    rf"(?P<path>(?:{_REFERENCE_PATH_SEGMENT}/)*{_REFERENCE_FILE_NAME})"
    r"(?P=quote)"
)

#: The scripts-directory-relative path a Hook_Command_String names.
_HOOK_SCRIPT_ARGUMENT = re.compile(
    re.escape(SCRIPTS_DIR_PLACEHOLDER) + r"/(?P<script>[^\"'\s]+)"
)


@dataclass(frozen=True)
class _SpelledImport:
    """One module import a script spells, read by this section's own scanner."""

    script: str
    module: str
    line: int

    @property
    def directory(self) -> str:
        """The directory the import has to resolve in — the script's own."""
        return self.script.rpartition("/")[0]


def _spelled_imports(text: str, *, source: str) -> tuple[_SpelledImport, ...]:
    """Every module `text` imports, one entry per module, earliest line first.

    A module imported three times is one thing to fix, so repeats collapse the
    way the criterion does: onto the earliest line that names it.
    """
    earliest: dict[str, int] = {}
    for match in _IMPORT_STATEMENT_LINE.finditer(text):
        module = match.group("module").split(".")[0]
        line = text.count("\n", 0, match.start()) + 1
        earliest[module] = min(line, earliest.get(module, line))
    return tuple(
        sorted(
            (
                _SpelledImport(script=source, module=module, line=line)
                for module, line in earliest.items()
            ),
            key=lambda entry: (entry.line, entry.module),
        )
    )


def _provider_map(paths: Iterable[str]) -> Mapping[str, tuple[str, ...]]:
    """Module name → the directories that make it importable, sorted.

    The two importable spellings, written from the language rather than read from
    the validator: `<dir>/<name>.py` provides `<name>` in `<dir>`, and
    `<dir>/<name>/__init__.py` provides the package `<name>` in `<dir>`. A module
    at the tree root is provided in `""`.
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


def _segment_suffixes(paths: Iterable[str]) -> frozenset[str]:
    """Every segment-aligned suffix of every path — what a tree supplies.

    R10 AC4 asks whether the referenced file *exists in the produced Power*, and
    a script's own prefix (`here`, `${PLUGIN_ROOT}/scripts/`, nothing at all) is
    resolved at runtime, so a reference is satisfied by any file whose path ends
    with it. Segment-aligned by construction, so `vendor/x.js` is never satisfied
    by `notvendor/x.js`.
    """
    supplied: set[str] = set()
    for path in paths:
        segments = path.split("/")
        supplied.update("/".join(segments[index:]) for index in range(len(segments)))
    return frozenset(supplied)


def _crosses_vendor(spelling: str) -> bool:
    """Whether a spelling reaches into a `vendor/` directory."""
    return VENDOR_SEGMENT in spelling.split("/")


def _spelled_references(
    text: str, *, shipped: frozenset[str]
) -> frozenset[tuple[str, str]]:
    """The `(spelling, kind)` pairs `text` names that have to exist *(R10 AC4)*.

    Three populations, each for a stated reason: a vendored asset is third-party
    content that is checked in and never produced at runtime; a Python module is
    an input, because no ported script writes one; and whatever the resolved
    release ships beside its scripts is content the Power owes. A path literal
    that is none of those is a file the script creates, and is not a reference.

    One reference read at two depths is one file named once, so the longer,
    segment-aligned spelling wins.
    """
    found: dict[str, str] = {}
    for match in _VENDOR_REFERENCE.finditer(text):
        found.setdefault(match.group(0), ASSET_VENDORED)
    for match in _QUOTED_REFERENCE.finditer(text):
        spelling = match.group("path")
        if _crosses_vendor(spelling) or spelling in found:
            continue
        if spelling.endswith(SCRIPT_SUFFIX):
            found[spelling] = ASSET_MODULE
        elif spelling in shipped:
            found[spelling] = ASSET_RELEASE_SHIPPED
    return frozenset(
        (spelling, kind)
        for spelling, kind in found.items()
        if not any(
            other.endswith(f"/{spelling}") for other in found if other != spelling
        )
    )


def _hook_definitions(files: Mapping[str, bytes]) -> tuple[str, ...]:
    """Every hook definition in a produced Power, sorted.

    A JSON document carrying a `hooks` list, which is what a definition is; read
    that way rather than by filename so the unprefixed coverage map sitting in
    the same directory is not mistaken for one.
    """
    found: list[str] = []
    for path in sorted(files):
        if not path.endswith(".json"):
            continue
        try:
            document = json.loads(files[path].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(document, Mapping) and isinstance(document.get("hooks"), list):
            found.append(path)
    return tuple(found)


def _spelled_hook_references(
    document: Any, definition: str, scripts_directory: str
) -> tuple[tuple[str, str, str], ...]:
    """The `(hook, relative, required)` triples one definition's hooks name.

    The `Hook_Installer` resolves `<ABSOLUTE_SCRIPTS_DIR>` to the ported script
    directory, so a hook's script has to sit at exactly one path — which is why
    this reference is the one resolved exactly rather than by suffix. A hook
    whose action is not a command action carries no command string; a command
    action whose string is missing is a shape fault with another owner.
    """
    root = scripts_directory.strip("/")
    spelled: list[tuple[str, str, str]] = []
    for index, hook in enumerate(document["hooks"]):
        if not isinstance(hook, Mapping):
            continue
        action = hook.get("action")
        if not isinstance(action, Mapping) or action.get("type") != "command":
            continue
        command = action.get("command")
        if not isinstance(command, str):
            continue
        name = hook.get("name")
        hook_name = (
            name if isinstance(name, str) and name.strip() else f"hooks[{index}]"
        )
        relatives = tuple(
            match.group("script") for match in _HOOK_SCRIPT_ARGUMENT.finditer(command)
        )
        # The engine's reader is driven here rather than trusted: the paths it
        # pulls out of one command string are the paths this scanner found.
        assert command_script_paths(command) == relatives, definition
        spelled.extend(
            (hook_name, relative, f"{root}/{relative}" if root else relative)
            for relative in relatives
        )
    return tuple(spelled)


@lru_cache(maxsize=None)
def _authored_script_imports() -> frozenset[str]:
    """Every module the authored `kiro-owned` scripts import.

    Needed to keep the generated input honest rather than to make a claim. A
    drawn script named `os.py` lands beside the ported set and shadows the
    standard-library `os` the `Hook_Installer` imports from *another* directory —
    a real `module-not-colocated` condition the gate is right to report, and a
    generated-input artifact rather than the placement under test. Such a draw is
    excluded, and the exclusion is derived from the authored content rather than
    from a list of module names, so a new import cannot silently reintroduce it.
    """
    modules: set[str] = set()
    for path in sorted(KIRO_OWNED_ROOT.rglob(f"*{SCRIPT_SUFFIX}")):
        text = path.read_text(encoding="utf-8")
        modules.update(
            entry.module for entry in _spelled_imports(text, source=path.name)
        )
    return frozenset(modules)


def _without_shadowing_scripts(
    tree: Mapping[str, TreeEntry],
) -> dict[str, TreeEntry]:
    """`tree` without any drawn script that would shadow an authored import."""
    shadowing = _authored_script_imports()
    return {
        path: entry
        for path, entry in tree.items()
        if not (
            path.startswith(f"{_TEMPLATE_SCRIPTS_ROOT}/")
            and path.endswith(SCRIPT_SUFFIX)
            and path.rpartition("/")[2][: -len(SCRIPT_SUFFIX)] in shadowing
        )
    }


def _with_script_probes(tree: Mapping[str, TreeEntry]) -> dict[str, TreeEntry]:
    """Plant the corpus's script shape into a generated tree.

    Two modules that import each other, five hook-invoked scripts that import
    them, a module one level below `scripts/`, the vendored bundle, and the
    non-Python asset that sits beside the scripts. Every reference planted here
    is one the compliant Power satisfies, so the compliant baseline is a real
    pass over a non-empty reference set rather than a pass over nothing.
    """
    planted = dict(tree)
    planted[f"{_TEMPLATE_SCRIPTS_ROOT}/{_IMPORTED_MODULE}{SCRIPT_SUFFIX}"] = TreeEntry(
        "file",
        (
            f"import {_SIBLING_MODULE}\n"
            "import optional_runtime\n"
            f'BUNDLE = "{CLAUDE_ROOT_TOKEN}/{_TEMPLATE_SCRIPTS_ROOT}/'
            f'{_VENDORED_ASSET}"\n'
            f'LOGO = "{_SCRIPT_SIDE_ASSET}"\n'
            f'HELPER = "{_NESTED_SCRIPT}"\n'
        ).encode("utf-8"),
    )
    planted[f"{_TEMPLATE_SCRIPTS_ROOT}/{_SIBLING_MODULE}{SCRIPT_SUFFIX}"] = TreeEntry(
        "file", b"import shutil\n"
    )
    for stem in _HOOK_SCRIPT_STEMS:
        body = f"import {_IMPORTED_MODULE}\n"
        if f"{stem}{SCRIPT_SUFFIX}" == _DROPPED_HOOK_SCRIPT:
            body += f"import {_SIBLING_MODULE}\n"
        planted[f"{_TEMPLATE_SCRIPTS_ROOT}/{stem}{SCRIPT_SUFFIX}"] = TreeEntry(
            "file", body.encode("utf-8")
        )
    planted[f"{_TEMPLATE_SCRIPTS_ROOT}/{_NESTED_SCRIPT}"] = TreeEntry(
        "file", b'LAYOUT = "circle"\n'
    )
    planted[f"{_TEMPLATE_SCRIPTS_ROOT}/{_VENDORED_ASSET}"] = TreeEntry(
        "binary", b"!function(t,n){}(this,function(){return{version:'7'}});"
    )
    planted[f"{_TEMPLATE_SCRIPTS_ROOT}/{_SCRIPT_SIDE_ASSET}"] = TreeEntry(
        "binary", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\x00\x01"
    )
    return planted


def _seeded_reference_power(
    staged: Mapping[str, bytes], seeds: frozenset[str], *, scripts_directory: str
) -> tuple[dict[str, bytes], frozenset[tuple[str, str, str]]]:
    """A produced Power, and the `(origin, reference, kind)` triples it owes.

    Each seed perturbs exactly one reference and states what that owes, read off
    the label rather than off any value the validator computed. The first two
    seeds add a script the *engine* would have halted on, which is the point:
    the gate has to hold whether or not the halt did.
    """
    files = dict(staged)
    owed: set[tuple[str, str, str]] = set()

    if _SEED_DANGLING_VENDORED in seeds:
        origin = f"{scripts_directory}/{_DANGLING_VENDOR_SCRIPT}"
        files[origin] = f'BUNDLE = "{_ABSENT_VENDORED_ASSET}"\n'.encode("utf-8")
        owed.add((origin, _ABSENT_VENDORED_ASSET, ASSET_VENDORED))

    if _SEED_DANGLING_MODULE in seeds:
        origin = f"{scripts_directory}/{_DANGLING_MODULE_SCRIPT}"
        files[origin] = f'HELPER = "{_ABSENT_PYTHON_MODULE}"\n'.encode("utf-8")
        owed.add((origin, _ABSENT_PYTHON_MODULE, ASSET_MODULE))

    if _SEED_DROPPED_ASSET in seeds:
        # The release ships it beside its scripts and a ported script loads it;
        # the port lost it. Nothing else about the script changes.
        del files[f"{scripts_directory}/{_SCRIPT_SIDE_ASSET}"]
        owed.add(
            (
                f"{scripts_directory}/{_IMPORTED_MODULE}{SCRIPT_SUFFIX}",
                _SCRIPT_SIDE_ASSET,
                ASSET_RELEASE_SHIPPED,
            )
        )

    if _SEED_DROPPED_HOOK_SCRIPT in seeds:
        # Both tiers carry the same definition, so both installed hooks would
        # fire at a script that is not there, and both are owed.
        del files[f"{scripts_directory}/{_DROPPED_HOOK_SCRIPT}"]
        owed.update(
            (definition, _DROPPED_HOOK_SCRIPT, ASSET_HOOK_SCRIPT)
            for definition in _hook_definitions(staged)
            for _, relative, _ in _spelled_hook_references(
                json.loads(staged[definition].decode("utf-8")),
                definition,
                scripts_directory,
            )
            if relative == _DROPPED_HOOK_SCRIPT
        )

    return files, frozenset(owed)


def _seeded_import_power(
    staged: Mapping[str, bytes],
    seeds: frozenset[str],
    *,
    scripts_directory: str,
    relocation: str,
) -> tuple[dict[str, bytes], frozenset[tuple[str, str, str]]]:
    """A produced Power, and the `(script, module, kind)` triples it owes.

    `module-not-colocated` is D4's failure, seeded by moving a module out of its
    importers' directory and leaving it in the Power; `module-unported` is the
    other, seeded by dropping a module the release ships. The owed set is read
    off the importers this section planted that *survive* the seeds, so it names
    every one of them rather than the first, and the two seeds compose: a script
    the second one drops no longer owes what the first one broke.
    """
    files = dict(staged)
    owning = f"{scripts_directory}/{_IMPORTED_MODULE}{SCRIPT_SUFFIX}"
    hook_importers = tuple(
        f"{scripts_directory}/{stem}{SCRIPT_SUFFIX}" for stem in _HOOK_SCRIPT_STEMS
    )
    sibling_importers = (owning, f"{scripts_directory}/{_DROPPED_HOOK_SCRIPT}")

    if _SEED_MODULE_RELOCATED in seeds:
        moved = f"{_SIBLING_MODULE}{SCRIPT_SUFFIX}"
        files[f"{relocation}/{moved}" if relocation else moved] = files.pop(
            f"{scripts_directory}/{moved}"
        )
    if _SEED_MODULE_UNPORTED in seeds:
        del files[owning]

    owed: set[tuple[str, str, str]] = set()
    if _SEED_MODULE_RELOCATED in seeds:
        owed.update(
            (script, _SIBLING_MODULE, IMPORT_RELOCATED)
            for script in sibling_importers
            if script in files
        )
    if _SEED_MODULE_UNPORTED in seeds:
        owed.update(
            (script, _IMPORTED_MODULE, IMPORT_UNPORTED)
            for script in hook_importers
            if script in files
        )

    return files, frozenset(owed)


def _broken_import_oracle(
    files: Mapping[str, bytes], release: frozenset[str]
) -> Mapping[tuple[str, str], tuple[str, tuple[str, ...]]]:
    """Every import that does not resolve where its script sits *(R10 AC6)*.

    R10 AC6's criterion, written over this section's own scanner and provider
    map. An import with no evidence behind it — a standard-library or
    third-party module nothing in the Power and nothing in the release provides —
    is not a same-directory module import and is not a failure.
    """
    providers = _provider_map(files)
    broken: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {}
    for path in sorted(files):
        if not path.endswith(SCRIPT_SUFFIX):
            continue
        for entry in _spelled_imports(files[path].decode("utf-8"), source=path):
            elsewhere = providers.get(entry.module, ())
            if entry.directory in elsewhere:
                continue
            if elsewhere:
                broken[(entry.script, entry.module)] = (IMPORT_RELOCATED, elsewhere)
            elif entry.module in release:
                broken[(entry.script, entry.module)] = (IMPORT_UNPORTED, ())
    return broken


def _assert_finding_names_the_defect(finding: Finding, *, code: str) -> None:
    """One finding, checked to spell every name it carries as data.

    R10 AC4 and AC6 are acted on by adding a file or moving one, so a finding
    that does not name the script and the thing it named is not actionable: every
    name it carries as data is required in its prose too. The `kind` is the
    report's vocabulary rather than a name, so it travels as data only.
    """
    assert finding.code == code
    assert finding.severity == SEVERITY_ERROR
    assert finding.target
    for key, value in finding.details.items():
        if key == "kind":
            continue
        for name in value if isinstance(value, list) else [value]:
            if isinstance(name, str) and name:
                assert name in finding.message or repr(name) in finding.message, name
    payload = finding.to_json()
    assert payload["code"] == code
    assert payload["kind"] == finding.details["kind"]
    assert payload["target"] == finding.target
    assert payload["severity"] == SEVERITY_ERROR


def _assert_gate_follows(result: CheckResult, *, code: str) -> None:
    """The recorded result and the release gate follow from the findings alone."""
    clean = result.findings == ()
    assert result.result == (RESULT_PASS if clean else RESULT_FAIL)
    assert result.passed is clean
    report = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_PASSING_SCRIPT_SIBLING, result),
    )
    assert _PASSING_SCRIPT_SIBLING.passed
    assert report.status == (STATUS_PASSED if clean else STATUS_FAILED)
    assert report.tag_allowed is clean
    assert report.findings_for(code) == result.findings
    assert report.failed_check_ids() == (() if clean else (result.id,))


def _assert_reports_exactly_the_broken_imports(
    files: Mapping[str, bytes],
    *,
    release: frozenset[str],
    owed: frozenset[tuple[str, str, str]],
) -> CheckResult:
    """Run the import check over `files` and check the verdict *(R10 AC6)*.

    Asserts the reported broken imports are exactly `owed` — no more, no fewer,
    and not a prefix — that the criteria oracle independently agrees on that set,
    that every finding names the importing script and the imported module, and
    that the recorded result and the release gate follow from it and nothing else.
    """
    tree = PowerTree.from_mapping(files)
    scripts = tuple(sorted(path for path in files if path.endswith(SCRIPT_SUFFIX)))
    assert script_paths(tree) == scripts == tree.match(SCRIPT_GLOB)

    providers = _provider_map(files)
    assert module_providers(tree.paths) == providers

    spelled: list[ScriptImport] = []
    for path in scripts:
        text = tree.read_text(path)
        read = script_imports(text, source=path)
        scanned = _spelled_imports(text, source=path)
        # The parser's reading and this section's line scanner agree on every
        # script in the tree, which is what lets one stand in for the other.
        assert tuple((entry.module, entry.line) for entry in read) == tuple(
            (entry.module, entry.line) for entry in scanned
        )
        for entry, other in zip(read, scanned):
            assert isinstance(entry, ScriptImport)
            assert entry.script == path == other.script
            assert entry.directory == other.directory == posixpath.dirname(path)
            assert entry.details() == {
                "script": path,
                "module": entry.module,
                "directory": entry.directory,
                "line": entry.line,
            }
            assert import_resolves(entry, providers) is (
                entry.directory in providers.get(entry.module, ())
            )
        spelled.extend(read)

    broken = _broken_import_oracle(files, release)
    findings = broken_import_findings(spelled, providers, release)
    reported: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {}
    for finding in findings:
        _assert_finding_names_the_defect(finding, code=E_BROKEN_IMPORT)
        details = finding.details
        assert details["kind"] in IMPORT_KINDS
        assert finding.target == details["script"]
        assert finding.location == f"line {details['line']}"
        reported[(details["script"], details["module"])] = (
            details["kind"],
            tuple(details["providedBy"]),
        )

    # --- Exactly the violating set, from both oracles ----------------------
    assert reported == broken
    assert owed == {
        (script, module, kind)
        for (script, module), (kind, _) in broken.items()
    }
    # Not a prefix, and nothing reported twice.
    assert len(findings) == len(broken) == len(owed)

    result = script_import_result(tree, release_modules=sorted(release))
    assert result.id == _IMPORT_CHECK_ID
    assert result.target == SCRIPT_TARGET
    assert result.findings == findings
    # Pure over the tree and the release's module names: same inputs, same result.
    assert script_import_result(tree, release_modules=sorted(release)) == result
    assert result.extra["scriptGlob"] == SCRIPT_GLOB
    assert result.extra["scripts"] == len(scripts)
    assert result.extra["imports"] == len(spelled)
    assert result.extra["releaseModules"] == len(release)
    assert result.extra["broken"] == [
        {
            "script": finding.details["script"],
            "module": finding.details["module"],
            "line": finding.details["line"],
            "kind": finding.details["kind"],
            "providedBy": finding.details["providedBy"],
        }
        for finding in findings
    ]
    _assert_gate_follows(result, code=E_BROKEN_IMPORT)
    return result


def _assert_reports_exactly_the_dangling_references(
    files: Mapping[str, bytes],
    *,
    scripts_directory: str,
    shipped: frozenset[str],
    owed: frozenset[tuple[str, str, str]],
) -> CheckResult:
    """Run the reference check over `files` and check the verdict *(R10 AC4)*.

    Asserts the reported dangling references are exactly `owed` — no more, no
    fewer, and not a prefix. Every reference the sweep extracts is re-read here
    from the same text and re-judged here against the Power's own paths, so the
    reported set is measured against a second opinion on both what a reference is
    and whether the Power satisfies it.
    """
    tree = PowerTree.from_mapping(files)
    paths = frozenset(tree.paths)
    supplied = _segment_suffixes(paths)
    assert supplied_paths(tree.paths) == supplied

    definitions = _hook_definitions(files)
    references: list[AssetReference] = []
    for path in script_paths(tree):
        text = tree.read_text(path)
        read = script_asset_references(text, source=path, shipped=shipped)
        assert {(entry.spelling, entry.kind) for entry in read} == _spelled_references(
            text, shipped=shipped
        )
        for entry in read:
            assert isinstance(entry, AssetReference)
            assert entry.origin == path
            assert entry.required is None and entry.exact is False
        references.extend(read)
    for definition in definitions:
        document = tree.read_json(definition)
        read = hook_script_references(
            document, definition, scripts_directory=scripts_directory
        )
        assert tuple(
            (entry.subject, entry.spelling, entry.required) for entry in read
        ) == _spelled_hook_references(document, definition, scripts_directory)
        for entry in read:
            assert entry.origin == definition
            assert entry.kind == ASSET_HOOK_SCRIPT
            assert entry.exact is True
        references.extend(read)

    # --- This section's own verdict on every reference ---------------------
    dangling: set[tuple[str, str, str]] = set()
    for entry in references:
        assert entry.kind in ASSET_KINDS
        satisfied = (
            entry.required in paths
            if entry.required is not None
            else entry.spelling in supplied
        )
        assert (
            asset_reference_satisfied(entry, paths=paths, supplied=supplied)
            is satisfied
        )
        if not satisfied:
            dangling.add((entry.origin, entry.spelling, entry.kind))

    findings = missing_asset_findings(references, paths=paths, supplied=supplied)
    reported: set[tuple[str, str, str]] = set()
    for finding in findings:
        _assert_finding_names_the_defect(finding, code=E_MISSING_ASSET)
        details = finding.details
        assert finding.target == details["origin"]
        reported.add((details["origin"], details["reference"], details["kind"]))

    # --- Exactly the violating set, from both oracles ----------------------
    assert reported == dangling == owed
    # Not a prefix, and nothing reported twice.
    assert len(findings) == len(dangling)

    result = script_reference_result(
        tree, scripts_directory=scripts_directory, shipped=shipped
    )
    assert result.id == _REFERENCE_CHECK_ID
    assert result.target == SCRIPT_TARGET
    assert result.findings == findings
    assert (
        script_reference_result(
            tree, scripts_directory=scripts_directory, shipped=shipped
        )
        == result
    )
    assert result.extra["scriptGlob"] == SCRIPT_GLOB
    assert result.extra["scripts"] == len(script_paths(tree))
    assert result.extra["hookDefinitions"] == list(definitions)
    assert result.extra["scriptsDirectory"] == scripts_directory
    assert result.extra["references"] == len(references)
    assert result.extra["satisfied"] == len(references) - len(findings)
    assert result.extra["missing"] == [
        {
            "origin": finding.details["origin"],
            "reference": finding.details["reference"],
            "kind": finding.details["kind"],
            "hook": finding.details.get("hook"),
            "required": finding.details.get("required"),
            "line": finding.details.get("line"),
        }
        for finding in findings
    ]
    _assert_gate_follows(result, code=E_MISSING_ASSET)
    return result


def _assert_script_check_fails_closed(
    check_id: str,
    code: str,
    context: ValidationContext,
    *,
    missing: str,
) -> None:
    """A check that cannot reach a verdict declines, and the run records a fail.

    Raising is only half of failing closed: the recorded result has to be a fail
    and the tag has to stay withheld, or a run launched without what this check
    needs would pass a comparison it never made.
    """
    check = registered_check(check_id)
    assert check is not None
    with pytest.raises(Unevaluable) as raised:
        check.run(context)
    assert raised.value.message

    report = run_checks(context, checks=(check_id,))
    recorded = report.results_for(check_id)
    assert len(recorded) == 1
    assert recorded[0].result == RESULT_FAIL
    assert recorded[0].target == SCRIPT_TARGET
    assert len(recorded[0].findings) == 1
    assert recorded[0].findings[0].code == code
    assert recorded[0].findings[0].details["unevaluated"] is True
    assert report.status == STATUS_FAILED
    assert report.tag_allowed is False, missing


# Feature: senzing-bootcamp-power, Property 11: Script layout is preserved and
# dangling asset references are detected
#
# Validates: Requirements 10.1, 10.4, 10.6
@settings(max_examples=100)
@given(template_tree(), st.sampled_from(_RELOCATION_DIRECTORIES))
def test_script_layout_is_preserved_and_dangling_asset_references_are_detected(
    tree: Mapping[str, TreeEntry], relocation: str
) -> None:
    # The generator cases this property draws from, asserted rather than assumed.
    assert {"wellformed", "nested_vendor", "binary_asset", "empty_file"} <= set(
        TEMPLATE_TREE_CASES
    )

    # R10 AC4, AC6: the two gates this property drives, and the population each
    # records a verdict over — one result for the script set, not one per script.
    for check_id, code, requirement in (
        (_IMPORT_CHECK_ID, E_BROKEN_IMPORT, "10.6"),
        (_REFERENCE_CHECK_ID, E_MISSING_ASSET, "10.4"),
    ):
        registered = registered_check(check_id)
        assert registered is not None
        assert registered.code == registered.failure_code == code
        assert registered.target == SCRIPT_TARGET == SCRIPT_GLOB
        assert registered.requirement == requirement
    assert IMPORT_KINDS == (IMPORT_RELOCATED, IMPORT_UNPORTED)
    assert ASSET_KINDS == (
        ASSET_VENDORED,
        ASSET_MODULE,
        ASSET_RELEASE_SHIPPED,
        ASSET_HOOK_SCRIPT,
    )

    # The two shapes a reference is deliberately not resolved into, because where
    # each lands is decided somewhere this gate cannot see.
    assert asset_reference_path("/etc/passwd") is None
    assert asset_reference_path(f"../{_SCRIPT_SIDE_ASSET}") is None
    # The Plugin_Root_Token expands to the Power root, so a reference carrying it
    # is rooted there rather than at the referencing script's directory.
    assert (
        asset_reference_path(
            f"{POWER_ROOT_TOKEN}/{_TEMPLATE_SCRIPTS_ROOT}/{_NESTED_SCRIPT}"
        )
        == f"{_TEMPLATE_SCRIPTS_ROOT}/{_NESTED_SCRIPT}"
    )

    contract = load_contract()
    root = ported_scripts_directory(contract)
    # R10 AC1, read from the contract rather than spelled by the engine: one
    # owning skill's `scripts/`, and every rule that carries template script
    # content lands under it.
    assert root.split("/") == [
        _POWER_SKILLS_ROOT,
        _OWNING_SKILL_NAME,
        _TEMPLATE_SCRIPTS_ROOT,
    ]
    script_rules = tuple(
        rule
        for rule in contract.rules
        if rule.produces_output
        and rule.source is not None
        and rule.source.split("/")[0] == _TEMPLATE_SCRIPTS_ROOT
    )
    assert script_rules
    for rule in script_rules:
        for dest in rule.dest:
            assert dest.strip("/") == root or dest.startswith(f"{root}/"), rule.id

    transformable = _transformable(tree, contract)
    source_tree = _with_script_probes(_without_shadowing_scripts(transformable))
    planted = {
        f"{_TEMPLATE_SCRIPTS_ROOT}/{_IMPORTED_MODULE}{SCRIPT_SUFFIX}",
        f"{_TEMPLATE_SCRIPTS_ROOT}/{_SIBLING_MODULE}{SCRIPT_SUFFIX}",
        f"{_TEMPLATE_SCRIPTS_ROOT}/{_NESTED_SCRIPT}",
        *(
            f"{_TEMPLATE_SCRIPTS_ROOT}/{stem}{SCRIPT_SUFFIX}"
            for stem in _HOOK_SCRIPT_STEMS
        ),
    }

    def _drawn_script_modules(paths: Iterable[str]) -> frozenset[str]:
        return frozenset(
            path.rpartition("/")[2][: -len(SCRIPT_SUFFIX)]
            for path in paths
            if path.startswith(f"{_TEMPLATE_SCRIPTS_ROOT}/")
            and path.endswith(SCRIPT_SUFFIX)
        )

    # Non-vacuous by construction, asserted rather than assumed: every probe
    # reached the tree, no drawn script collides with one — `_slug()` draws no
    # underscore and stops at eight characters — and nothing is left that would
    # shadow an authored import from another directory.
    assert planted <= set(source_tree)
    assert not _drawn_script_modules(transformable) & _drawn_script_modules(planted)
    assert not _drawn_script_modules(source_tree) & _authored_script_imports()

    # The release evidence both checks read, derived here from the source tree.
    release_paths = tuple(
        f"{TEMPLATE_PLUGIN_ROOT}/{path}" for path in sorted(source_tree)
    )
    prefix = f"{TEMPLATE_PLUGIN_ROOT}/"
    release_scripts = tuple(
        path
        for path in release_paths
        if path.startswith(f"{prefix}{_TEMPLATE_SCRIPTS_ROOT}/")
    )
    assert not any(path.endswith(f"/{PACKAGE_MARKER}") for path in release_scripts)
    release_modules = frozenset(
        path.rpartition("/")[2][: -len(SCRIPT_SUFFIX)]
        for path in release_scripts
        if path.endswith(SCRIPT_SUFFIX)
    )
    shipped = _segment_suffixes(release_scripts)
    assert _SCRIPT_SIDE_ASSET in shipped
    assert {_IMPORTED_MODULE, _SIBLING_MODULE} <= release_modules

    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        source, plugin_root = _materialized_release(
            temporary_root, source_tree, "release"
        )
        staging = temporary_root / "staging"

        plan = build_plan(contract, source, tag=_RESOLVED_TAG, staging=staging)
        outputs, _ = plan_destinations(plan)
        write_staging(plan)
        staged = _read_tree(staging)

        # --- Clause 1: the layout is preserved (R10 AC1) -------------------
        # Each ported script's destination is computed from its source path, so a
        # rename, a flattened subdirectory, or a split set fails here.
        ported: dict[str, str] = {}
        for output in outputs:
            if output.source_path is None:
                continue
            assert output.source_path.startswith(prefix)
            relative = output.source_path[len(prefix) :]
            if not relative.startswith(f"{_TEMPLATE_SCRIPTS_ROOT}/"):
                assert not output.path.startswith(f"{root}/"), output.path
                continue
            below = relative[len(_TEMPLATE_SCRIPTS_ROOT) + 1 :]
            assert output.path == f"{root}/{below}"
            assert output.path in staged
            ported[below] = output.path
        assert set(ported) == {
            path[len(_TEMPLATE_SCRIPTS_ROOT) + 1 :]
            for path in source_tree
            if path.startswith(f"{_TEMPLATE_SCRIPTS_ROOT}/")
        }
        # Nothing else lands in the ported directory but Kiro-owned content the
        # contract declares to sit beside the scripts (the Optional_Runtime guard).
        for output in outputs:
            if output.path.startswith(f"{root}/") and output.source_path is None:
                assert output.owner == OWNER_KIRO, output.path

        # R10 AC1's operative clause: scripts that were siblings in the template
        # are siblings in the Power, which is what makes a same-directory module
        # import between two of them resolve at runtime.
        colocated = {
            f"{_IMPORTED_MODULE}{SCRIPT_SUFFIX}",
            f"{_SIBLING_MODULE}{SCRIPT_SUFFIX}",
            *(f"{stem}{SCRIPT_SUFFIX}" for stem in _HOOK_SCRIPT_STEMS),
        }
        assert {posixpath.dirname(ported[name]) for name in colocated} == {root}
        # And the relative sub-structure below `scripts/` is carried, not flattened.
        assert ported[_NESTED_SCRIPT] == f"{root}/{_NESTED_SCRIPT}"
        assert any("/" in below for below in ported)

        # The release evidence the derived helpers read is the evidence this
        # section derived, whichever of the two roots `--source` names.
        release = PowerTree.from_directory(source)
        bare = PowerTree.from_directory(plugin_root)
        assert release.paths == release_paths
        assert source_prefix(release, contract.plugin_root) == prefix
        assert source_prefix(bare, contract.plugin_root) == ""
        assert frozenset(release_script_modules(release, prefix=prefix)) == (
            release_modules
        )
        assert frozenset(release_script_modules(bare)) == release_modules
        assert release_script_assets(release, prefix=prefix) == shipped
        assert release_script_assets(bare) == _segment_suffixes(
            path[len(prefix) :] for path in release_scripts
        )

        # --- Clause 2: the produced Power reports nothing ------------------
        # A real pass over a non-empty reference set: the vendored bundle, the
        # asset beside the scripts, the module a script names, and the scripts the
        # hooks invoke are all referenced and all present.
        clean_imports = _assert_reports_exactly_the_broken_imports(
            staged, release=release_modules, owed=frozenset()
        )
        assert clean_imports.passed and clean_imports.findings == ()
        clean_references = _assert_reports_exactly_the_dangling_references(
            staged, scripts_directory=root, shipped=shipped, owed=frozenset()
        )
        assert clean_references.passed and clean_references.findings == ()
        assert clean_references.extra["satisfied"] == (
            clean_references.extra["references"]
        )

        power = PowerTree.from_mapping(staged)
        kinds = {
            entry.kind
            for path in script_paths(power)
            for entry in script_asset_references(
                power.read_text(path), source=path, shipped=shipped
            )
        }
        assert kinds == {ASSET_VENDORED, ASSET_MODULE, ASSET_RELEASE_SHIPPED}
        hook_definitions = _hook_definitions(staged)
        assert hook_definitions
        assert {
            relative
            for definition in hook_definitions
            for _, relative, _ in _spelled_hook_references(
                json.loads(staged[definition].decode("utf-8")), definition, root
            )
        } == {f"{stem}{SCRIPT_SUFFIX}" for stem in _HOOK_SCRIPT_STEMS}
        # The planted same-directory imports are real imports that really resolve,
        # so clause 2's pass is a statement about co-location and not about a
        # Power whose scripts import nothing.
        providers = module_providers(power.paths)
        for stem in _HOOK_SCRIPT_STEMS:
            script = f"{root}/{stem}{SCRIPT_SUFFIX}"
            spelled = script_imports(power.read_text(script), source=script)
            assert _IMPORTED_MODULE in {entry.module for entry in spelled}
            for entry in spelled:
                assert import_resolves(entry, providers), entry

        # --- Clause 3: each way a reference dangles, on its own ------------
        covered: set[str] = set()
        for label in _REFERENCE_SEED_LABELS:
            seeded, owed = _seeded_reference_power(
                staged, frozenset({label}), scripts_directory=root
            )
            assert owed, label
            result = _assert_reports_exactly_the_dangling_references(
                seeded, scripts_directory=root, shipped=shipped, owed=owed
            )
            assert not result.passed, label
            covered |= {kind for _, _, kind in owed}
        # Every kind the report vocabulary declares is reached by a seed of its
        # own, so none of them is a condition this property merely describes.
        assert covered == set(ASSET_KINDS)

        # All four at once: one run names the full remaining work rather than the
        # first thing it found.
        seeded, owed = _seeded_reference_power(
            staged, frozenset(_REFERENCE_SEED_LABELS), scripts_directory=root
        )
        every = _assert_reports_exactly_the_dangling_references(
            seeded, scripts_directory=root, shipped=shipped, owed=owed
        )
        assert {kind for _, _, kind in owed} == set(ASSET_KINDS)
        assert len(every.findings) == len(owed) > len(ASSET_KINDS)

        # --- Clause 4: each way an import breaks, on its own ---------------
        broken_kinds: set[str] = set()
        for label in _IMPORT_SEED_LABELS:
            seeded, owed = _seeded_import_power(
                staged,
                frozenset({label}),
                scripts_directory=root,
                relocation=relocation,
            )
            assert owed, label
            result = _assert_reports_exactly_the_broken_imports(
                seeded, release=release_modules, owed=owed
            )
            assert not result.passed, label
            broken_kinds |= {kind for _, _, kind in owed}
            if label == _SEED_MODULE_RELOCATED:
                # D4's failure, named: the module is somewhere else in the Power,
                # and the finding says where it landed so the repair is co-location.
                assert {
                    tuple(row["providedBy"]) for row in result.extra["broken"]
                } == {(relocation,)}
        assert broken_kinds == set(IMPORT_KINDS)

        seeded, owed = _seeded_import_power(
            staged,
            frozenset(_IMPORT_SEED_LABELS),
            scripts_directory=root,
            relocation=relocation,
        )
        both = _assert_reports_exactly_the_broken_imports(
            seeded, release=release_modules, owed=owed
        )
        assert {kind for _, _, kind in owed} == set(IMPORT_KINDS)
        assert len(both.findings) == len(owed) > len(IMPORT_KINDS)

        # --- Clause 5: the registered checks, over a release tree ----------
        relocated, _ = _seeded_import_power(
            staged,
            frozenset({_SEED_MODULE_RELOCATED}),
            scripts_directory=root,
            relocation=relocation,
        )
        dropped, _ = _seeded_reference_power(
            staged, frozenset({_SEED_DROPPED_HOOK_SCRIPT}), scripts_directory=root
        )
        for check_id, check, expected, files in (
            (_IMPORT_CHECK_ID, check_script_imports, True, staged),
            (_IMPORT_CHECK_ID, check_script_imports, False, relocated),
            (_REFERENCE_CHECK_ID, check_script_references, True, staged),
            (_REFERENCE_CHECK_ID, check_script_references, False, dropped),
        ):
            context = ValidationContext(
                tree=PowerTree.from_mapping(files),
                tag=_RESOLVED_TAG,
                contract=contract,
                source=release,
            )
            checked = check(context)
            assert checked.id == check_id
            assert checked.passed is expected
            # The same verdict from either spelling of `--source`, and the runner
            # records what the check returned.
            assert (
                check(
                    ValidationContext(
                        tree=context.tree,
                        tag=_RESOLVED_TAG,
                        contract=contract,
                        source=bare,
                    )
                )
                == checked
            )
            report = run_checks(context, checks=(check_id,))
            assert report.tag_allowed is expected
            assert report.results_for(check_id) == (checked,)

        # The import check does not need the release tree — a module that moved
        # within the Power is detectable from the Power alone — and says so by
        # reaching the same verdict without it.
        assert check_script_imports(
            ValidationContext(
                tree=PowerTree.from_mapping(relocated),
                tag=_RESOLVED_TAG,
                contract=contract,
            )
        ).findings == script_import_result(
            PowerTree.from_mapping(relocated)
        ).findings

        # --- Clause 6: the transform's own half of R10 AC4 -----------------
        # A ported script naming a vendored asset the template does not ship
        # halts the port, naming every such reference, before a byte is written.
        for name, asset in _HALTING_REFERENCES.items():
            plugin_root.joinpath(_TEMPLATE_SCRIPTS_ROOT, name).write_bytes(
                f'BUNDLE = "{asset}"\n'.encode("utf-8")
            )
        halted_staging = temporary_root / "halted"
        halted_plan = build_plan(
            contract, source, tag=_RESOLVED_TAG, staging=halted_staging
        )
        halted_outputs, _ = plan_destinations(halted_plan)
        owed_pairs = {
            (f"{root}/{name}", asset) for name, asset in _HALTING_REFERENCES.items()
        }
        assert {
            (entry.path, entry.asset)
            for entry in find_missing_assets(halted_plan, halted_outputs)
        } == owed_pairs
        with pytest.raises(TransformError) as halted:
            write_staging(halted_plan)
        assert halted.value.code == E_MISSING_ASSET
        payload = halted.value.to_json()
        assert {
            (row["path"], row["asset"]) for row in payload["missing"]
        } == owed_pairs
        assert len(payload["missing"]) == len(owed_pairs)
        for name, asset in _HALTING_REFERENCES.items():
            assert f"{root}/{name}" in payload["message"]
            assert asset in payload["message"]
        # Nothing was written, so the destination `scripts/` tree is not merely
        # rolled back but never touched.
        assert not halted_staging.exists()
        assert _read_tree(staging) == staged

    # --- Clause 7: no script, no hook, no contract — no verdict ------------
    bare_power = PowerTree.from_mapping({PLUGIN_MANIFEST: "{}\n"})
    assert script_paths(bare_power) == ()
    assert _hook_definitions({PLUGIN_MANIFEST: b"{}\n"}) == ()
    _assert_script_check_fails_closed(
        _IMPORT_CHECK_ID,
        E_BROKEN_IMPORT,
        ValidationContext(tree=bare_power, tag=_RESOLVED_TAG, contract=contract),
        missing="any Python module in the produced Power",
    )
    _assert_script_check_fails_closed(
        _REFERENCE_CHECK_ID,
        E_MISSING_ASSET,
        ValidationContext(tree=bare_power, tag=_RESOLVED_TAG, contract=contract),
        missing="any Python module or hook definition in the produced Power",
    )
    _assert_script_check_fails_closed(
        _REFERENCE_CHECK_ID,
        E_MISSING_ASSET,
        ValidationContext(
            tree=PowerTree.from_mapping(
                {f"{root}/{_IMPORTED_MODULE}{SCRIPT_SUFFIX}": "import sys\n"}
            ),
            tag=_RESOLVED_TAG,
        ),
        missing="the Transformation_Contract, which declares the ported script "
        "directory a hook's script path resolves against",
    )

# ===========================================================================
# Property 12: Cross-reference integrity survives transformation and is verified
# ===========================================================================
#
# The bootcamp corpus is held together by relative links — release 0.5.1 spells
# `../bootcamp-onboarding/ground-rules.md` alone fifty times — so R8 states the
# guarantee twice, once about the transform and once about the gate, and neither
# half is worth much without the other. A transform that relocated a skill
# directory would break links a gate then dutifully reports one at a time; a gate
# that resolved nothing would let a transform break every link in the corpus
# silently. Both halves are driven here, over one tree, in that order: the engine
# ports a generated skill tree *(R8 AC1, AC2)*, and the check is then run over the
# documents the engine actually produced *(R8 AC3, AC4)*.
#
# Survival, and what it is measured against
# -----------------------------------------
# `skills/<name>/SKILL.md` with `<name>` byte-identical is the *whole* mechanism:
# a relative link resolves against the directory of the document that spells it,
# so a layout preserved verbatim is a link graph preserved verbatim, and any
# relocation — a renamed directory, a `references/` level introduced below a
# skill root — moves targets without touching link text. The claim is therefore
# stated twice over the real staging tree. Once as destinations: every ported
# source lands at the identical Power-relative path, one output per source, with
# provenance back to the file it came from. Once as the graph itself: each link's
# root-relative resolved target, and whether that target is a file that exists,
# is compared before and after.
#
# Three readings of "where does this point"
# -----------------------------------------
# `_points_at` joins a destination against the directory of the document that
# spells it and normalizes, which is R8 AC2's "the same target file location"
# written out; `_unresolved_kind` then reads R8 AC3's only passing case — an
# existing file inside the Power — off that result. Those are this section's
# oracle. The generator computes the same answer independently for the links it
# seeds and carries it in `CrossReference.resolves`, and the validator computes it
# a third time. All three are asserted to agree, so no single spelling of the
# normalization can move both sides of a comparison at once. The `kind` a finding
# carries is the report's vocabulary rather than the criterion's, so it is checked
# against the three kinds `REFERENCE_KINDS` declares and not against prose.
#
# The five appended links, and why they are constructed
# ----------------------------------------------------
# `skill_tree()` seeds `../` links, self-links, links into `references/`, and
# broken links — every one of the broken ones naming a document inside the Power
# that was never ported. Two of the three ways a link can fail are therefore not
# in the generator's repertoire at all: a link onto a *directory*, and a link that
# walks *out* of the Power. So five more links are appended to one entry point,
# built from the drawn tree rather than sampled: two that resolve (a sibling skill
# and the document itself) and one of each failure kind. That makes both halves
# non-vacuous in every example — including the `no_links` case — and it is what
# turns "reports the broken links" into "reports *these three*, each under its own
# kind, from one document, beside whatever the generator seeded".
#
# Exactly the violating set, in both directions
# ---------------------------------------------
# The findings are compared as an ordered sequence against the oracle's set, so a
# check that reported the first broken link in a document and stopped, or reported
# one aggregate verdict, or reported a link that resolves, all fail here. The
# other direction of "exactly when" is asserted by *repair*: with the appended
# links removed and a document created at each remaining unresolved target, the
# same tree reports zero and the gate opens. Nothing else about the tree changes,
# so the verdict flipped because the links resolve and for no other reason.
#
# The zero case
# -------------
# A Power carrying no Markdown under `skills/` declines to a verdict rather than
# recording a pass, which is what stops "zero unresolved references" from being
# satisfiable by shipping no skill content at all.
#
# Deliberately out of scope: whether the ported prose around a link is faithful is
# Property 10's, whether a skill's frontmatter is well formed is Property 13's,
# and whether a ported script's module imports still resolve is Property 11's.

#: The generator's link shape, and the corpus's: a Markdown inline link whose
#: destination is a bare relative path. Matched on the `](` marker alone, without
#: reading the link text, so this scanner is a second opinion on what the swept
#: documents spell rather than a copy of the validator's patterns.
_MARKDOWN_LINK = re.compile(r"\]\(\s*(?P<target>[^()\s]*)\s*\)")

#: A skill directory the Power does not carry, and a directory above the Power
#: root. Neither is a name `skill_tree()` can generate, and both are asserted
#: unresolvable below rather than assumed to be.
_UNPORTED_SKILL_DIR = "unported-skill"
_OUTSIDE_THE_POWER = "outside-the-power"

#: A document created at a broken link's target by the repair clause. Prose only:
#: a repair that introduced links of its own would change the reference set it is
#: supposed to leave alone.
_PORTED_DOCUMENT = "The ported document this link names.\n"

#: The `skill_tree()` cases this property relies on, so a generator change that
#: dropped one fails here instead of quietly narrowing the property.
_REQUIRED_SKILL_TREE_CASES = frozenset(
    {
        "parent_links",
        "broken_links",
        "self_links",
        "references_links",
        "module_03b_names",
        "mixed",
        "no_links",
    }
)

#: A check that found nothing, standing in for the rest of a passing run. With it
#: in the report, a withheld tag can only have come from the check under test —
#: `cross-references` in Property 12 below, the register checks in Property 25.
#: Defined once here, at its first use, because a second module-level binding of
#: the same name would silently shadow this one for both readers.
_PASSING_SCHEMA_SIBLING = CheckResult(id="plugin-schema", target=PLUGIN_MANIFEST)


def _points_at(source: str, target: str) -> str:
    """Where `target`, spelled in `source`, points — root-relative, normalized.

    R8 AC2's "the same target file location" written out: a relative link is
    resolved against the directory of the document that spells it. This is the
    oracle every comparison below is stated against.
    """
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


@dataclass(frozen=True)
class _SpelledLink:
    """One relative link a swept document spells, and where it lands."""

    source: str
    target: str
    line: int

    @property
    def resolved(self) -> str:
        return _points_at(self.source, self.target)


def _link_line(target: str) -> str:
    """One appended link, in the sentence shape the generated corpus uses."""
    return f"See [the reference]({target}).\n"


def _swept_documents(files: Mapping[str, str]) -> tuple[str, ...]:
    """Every document a cross-reference between skills can be spelled in.

    Derived from R8 AC3's subject rather than from the check's own glob: a
    Markdown document anywhere under `skills/`, a skill's entry point and the
    documents it links to alike. The two are asserted equal below.
    """
    return tuple(
        sorted(
            path
            for path in files
            if path.startswith("skills/") and path.endswith(".md")
        )
    )


def _spelled_links(text: str, *, source: str) -> tuple[_SpelledLink, ...]:
    """Every link `text` spells, in the order it spells them."""
    return tuple(
        _SpelledLink(
            source=source,
            target=match.group("target"),
            line=text.count("\n", 0, match.start()) + 1,
        )
        for match in _MARKDOWN_LINK.finditer(text)
    )


def _link_graph(files: Mapping[str, str]) -> tuple[_SpelledLink, ...]:
    """The whole corpus's links, by document in path order then by line."""
    return tuple(
        link
        for path in _swept_documents(files)
        for link in _spelled_links(files[path], source=path)
    )


def _unresolved_kind(files: Mapping[str, str], link: _SpelledLink) -> str | None:
    """How `link` fails to resolve, or `None` when it resolves to a file.

    R8 AC3 admits exactly one passing case — an existing file within the
    Bootcamp_Power — so the three failures are what is left of it: a target above
    the Power root, a target that is a directory rather than a file, and a target
    nothing was ported to. The names are the report's; the verdict is the
    criterion's.
    """
    resolved = link.resolved
    if resolved == ".." or resolved.startswith("../"):
        return REFERENCE_ESCAPES_POWER
    if resolved in files:
        return None
    if any(path.startswith(f"{resolved.rstrip('/')}/") for path in files):
        return REFERENCE_DIRECTORY
    return REFERENCE_ABSENT


def _appended_targets(
    files: Mapping[str, str], source: str
) -> tuple[tuple[str, str | None], ...]:
    """Five destinations to append to `source`, each with the kind it must fail as.

    Built from the drawn tree, so every example carries a link of every kind
    through the transform and into the gate. `None` is "resolves"; the sibling
    skill directory the two directory-shaped destinations name exists because
    `skill_tree()` draws at least two skills.
    """
    own = posixpath.dirname(source)
    sibling = min(
        posixpath.basename(directory)
        for directory in {posixpath.dirname(path) for path in files}
        if directory != own and directory.count("/") == 1
    )
    return (
        (f"../{sibling}/{SKILL_MANIFEST}", None),
        (SKILL_MANIFEST, None),
        (f"../{_UNPORTED_SKILL_DIR}/{SKILL_MANIFEST}", REFERENCE_ABSENT),
        (f"../{sibling}", REFERENCE_DIRECTORY),
        (f"../../../{_OUTSIDE_THE_POWER}/{SKILL_MANIFEST}", REFERENCE_ESCAPES_POWER),
    )


def _assert_reports_exactly_the_broken_links(
    documents: Mapping[str, str],
) -> tuple[CheckResult, tuple[_SpelledLink, ...]]:
    """Run the `cross-references` check over `documents` and check the result.

    One recorded result for the subtree, carrying one finding per broken link and
    nothing else, each naming its source file and its target path *(R8 AC3, AC4)*.
    The `plugin.json` a produced Power carries is added here, so the swept set is
    asserted to be the Markdown under `skills/` rather than every file.

    Returns the result and the oracle's broken links, so each caller can then make
    its own higher-level claim about what came back.
    """
    files = {**documents, PLUGIN_MANIFEST: "{}\n"}
    swept = _swept_documents(files)
    graph = _link_graph(files)
    unresolved = tuple(
        link for link in graph if _unresolved_kind(files, link) is not None
    )

    tree = PowerTree.from_mapping(files)
    context = ValidationContext(tree=tree, tag=_RESOLVED_TAG)
    assert tree.match(CROSS_REFERENCE_GLOB) == swept
    assert PLUGIN_MANIFEST not in swept

    result = check_cross_references(context)
    assert result.id == "cross-references"
    assert result.target == CROSS_REFERENCE_TARGET
    # A function of the tree alone: the same context twice, the same result.
    assert check_cross_references(context) == result

    # R8 AC4: one finding per broken link, in document then line order, each
    # naming the file the link is written in and the path it names.
    assert len(result.findings) == len(unresolved)
    for finding, link in zip(result.findings, unresolved):
        kind = _unresolved_kind(files, link)
        assert kind in REFERENCE_KINDS
        assert finding.code == E_UNRESOLVED_REFERENCE
        assert finding.severity == SEVERITY_ERROR
        assert finding.target == link.source
        assert finding.location == f"line {link.line}"
        assert link.source in finding.message
        assert repr(link.target) in finding.message
        assert repr(link.resolved) in finding.message
        assert finding.details == {
            "source": link.source,
            "target": link.target,
            "path": link.target,
            "resolved": link.resolved,
            "line": link.line,
            "kind": kind,
        }
        payload = finding.to_json()
        assert payload["code"] == E_UNRESOLVED_REFERENCE
        assert payload["target"] == link.source
        assert payload["location"] == finding.location
        assert payload["kind"] == kind
        assert payload["severity"] == SEVERITY_ERROR

    # The sweep is its pure parts composed, document by document, and those parts
    # agree with the oracle on every link — not only on the broken ones.
    composed: list[Any] = []
    for path in swept:
        text = tree.read_text(path)
        # No fenced block and no code span in this corpus, so every link the
        # scanner above finds is a link the sweep sees too.
        assert markdown_prose(text) == text == blank_code_blocks(text)
        spelled = markdown_references(text, source=path)
        scanned = _spelled_links(text, source=path)
        assert tuple((ref.target, ref.line) for ref in spelled) == tuple(
            (link.target, link.line) for link in scanned
        )
        for reference, link in zip(spelled, scanned):
            kind = _unresolved_kind(files, link)
            assert reference_path(reference.target) == reference.path
            assert resolve_reference(path, reference.path) == reference.resolved
            assert reference.resolved == link.resolved
            assert (
                cross_reference(path, reference.target, line=reference.line)
                == reference
            )
            assert reference_kind(tree, reference) == kind
            assert reference.within_power is (kind != REFERENCE_ESCAPES_POWER)
        composed.extend(cross_reference_findings(tree, spelled))
    assert tuple(composed) == result.findings

    # The recorded payload a Maintainer reads: what was swept, what was resolved,
    # and one compact row per unresolved reference.
    assert result.extra["documentGlob"] == CROSS_REFERENCE_GLOB
    assert result.extra["documents"] == len(swept)
    assert result.extra["references"] == len(graph)
    assert result.extra["resolved"] == len(graph) - len(unresolved)
    assert result.extra["unresolved"] == [
        {
            "source": link.source,
            "target": link.target,
            "resolved": link.resolved,
            "line": link.line,
            "kind": _unresolved_kind(files, link),
        }
        for link in unresolved
    ]

    # R8 AC4: zero unresolved references is exactly the passing case, and the
    # release gate is the biconditional over it.
    clean = unresolved == ()
    assert result.result == (RESULT_PASS if clean else RESULT_FAIL)
    assert result.passed is clean
    report = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_PASSING_SCHEMA_SIBLING, result),
    )
    assert _PASSING_SCHEMA_SIBLING.passed
    assert report.status == (STATUS_PASSED if clean else STATUS_FAILED)
    assert report.tag_allowed is clean
    assert report.failed_check_ids() == (() if clean else ("cross-references",))
    assert report.findings_for(E_UNRESOLVED_REFERENCE) == result.findings
    return result, unresolved


# Feature: senzing-bootcamp-power, Property 12: Cross-reference integrity
# survives transformation and is verified
#
# Validates: Requirements 8.1, 8.2, 8.3, 8.4
@settings(max_examples=100)
@given(skill_tree())
def test_cross_reference_integrity_survives_transformation_and_is_verified(
    case: SkillTreeCase,
) -> None:
    # The generator cases this property draws from, asserted rather than assumed.
    assert _REQUIRED_SKILL_TREE_CASES <= set(SKILL_TREE_CASES)

    # R8 AC3, AC4: the gate this property drives, and the subtree it examines.
    registered = registered_check("cross-references")
    assert registered is not None
    assert registered.code == E_UNRESOLVED_REFERENCE
    assert registered.target == CROSS_REFERENCE_TARGET
    assert REFERENCE_KINDS == (
        REFERENCE_ABSENT,
        REFERENCE_DIRECTORY,
        REFERENCE_ESCAPES_POWER,
    )

    # --- The oracles agree on the generated tree ---------------------------
    generated = _link_graph(case.files)
    assert sorted((link.source, link.target) for link in generated) == sorted(
        (reference.source, reference.target) for reference in case.references
    )
    seeded = {
        (reference.source, reference.target): reference.resolves
        for reference in case.references
    }
    for link in generated:
        # The generator's computed verdict, this section's, and R8 AC3's only
        # passing case, all one answer.
        assert seeded[(link.source, link.target)] == (link.resolved in case.files)
        assert seeded[(link.source, link.target)] is (
            _unresolved_kind(case.files, link) is None
        )
    assert {(reference.source, reference.target) for reference in case.broken} == {
        (link.source, link.target)
        for link in generated
        if _unresolved_kind(case.files, link) is not None
    }

    # --- One link of every kind, appended to one entry point ---------------
    entry_point = min(
        path
        for path in case.files
        if path.count("/") == 2 and path.endswith(f"/{SKILL_MANIFEST}")
    )
    appended = _appended_targets(case.files, entry_point)
    suffix = "".join(_link_line(target) for target, _ in appended)
    seeded_files = {**case.files, entry_point: case.files[entry_point] + suffix}

    injected = _spelled_links(seeded_files[entry_point], source=entry_point)[
        -len(appended) :
    ]
    for link, (target, kind) in zip(injected, appended):
        # The construction is checked against the oracle, so an appended link
        # that failed differently than intended fails here rather than quietly
        # narrowing the clauses below.
        assert link.target == target
        assert _unresolved_kind(seeded_files, link) == kind
    injected_broken = tuple(
        link for link, (_, kind) in zip(injected, appended) if kind is not None
    )
    assert len(injected_broken) == len(REFERENCE_KINDS)

    # --- Clause 1: the layout, and therefore the graph, survives -----------
    contract = load_contract()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "release"
        plugin_root = source.joinpath(*TEMPLATE_PLUGIN_ROOT.split("/"))
        plugin_root.mkdir(parents=True)
        staging = root / "staging"

        for path, text in sorted(seeded_files.items()):
            absolute = plugin_root.joinpath(*path.split("/"))
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_bytes(text.encode("utf-8"))

        plan = build_plan(contract, source, tag=_RESOLVED_TAG, staging=staging)
        result = write_staging(plan)
        staged = _read_tree(staging)

        # R8 AC1: one output per ported source, at the identical Power-relative
        # path, each carrying provenance back to the file it came from. Computed
        # from the source paths rather than read off the plan, so a relocation
        # fails here instead of agreeing with itself.
        ported = {
            output.path: output.source_path
            for output in result.outputs
            if output.source_path is not None
        }
        assert ported == {
            path: f"{TEMPLATE_PLUGIN_ROOT}/{path}" for path in seeded_files
        }
        # Every skill directory name reaches `skills/<name>/SKILL.md` unchanged,
        # `module-03b`-style interstitials included.
        assert {
            skill_directory_name(path)
            for path in ported
            if path.count("/") == 2 and path.endswith(f"/{SKILL_MANIFEST}")
        } == {path.split("/")[1] for path in seeded_files}

        produced = {path: staged[path].decode("utf-8") for path in seeded_files}

        # R8 AC2: the same links, in the same documents, on the same lines,
        # resolving to the same root-relative targets — and each one a file
        # afterwards exactly when it was one before.
        before = _link_graph(seeded_files)
        after = _link_graph(produced)
        assert len(after) == len(before) >= len(appended)
        for source_link, produced_link in zip(before, after):
            assert produced_link == source_link
            assert produced_link.resolved == source_link.resolved
            assert (produced_link.resolved in produced) == (
                source_link.resolved in seeded_files
            )

    # --- Clause 2: the gate reports exactly the broken links ---------------
    checked, unresolved = _assert_reports_exactly_the_broken_links(produced)
    reported = {
        _SpelledLink(
            finding.details["source"],
            finding.details["target"],
            finding.details["line"],
        ): finding.details["kind"]
        for finding in checked.findings
    }
    assert set(reported) == set(unresolved)
    # Non-vacuous in every example: the appended links are each reported under
    # their own kind, the two that resolve are not reported at all, and the
    # generator's own broken links are reported beside them.
    for link, (_, kind) in zip(injected, appended):
        assert reported.get(link) == kind
    assert {reported[link] for link in injected_broken} == set(REFERENCE_KINDS)
    assert len(unresolved) == len(case.broken) + len(injected_broken)

    # --- Clause 3: resolving the links flips the verdict -------------------
    # The other direction of "exactly when". The appended links come off — a link
    # onto a directory and a link out of the Power are fixed by editing the link,
    # not by adding a file — and every remaining unresolved target names a
    # document inside the Power that was never ported, so porting it is the fix.
    assert produced[entry_point].endswith(suffix)
    unappended = {**produced, entry_point: produced[entry_point][: -len(suffix)]}
    missing = tuple(
        link
        for link in _link_graph(unappended)
        if _unresolved_kind(unappended, link) is not None
    )
    for link in missing:
        assert link.resolved.startswith("skills/") and link.resolved.endswith(".md")
    repaired, none_left = _assert_reports_exactly_the_broken_links(
        {**unappended, **{link.resolved: _PORTED_DOCUMENT for link in missing}}
    )
    assert none_left == ()
    assert repaired.passed and repaired.findings == ()
    assert repaired.extra["resolved"] == repaired.extra["references"]

    # --- Clause 4: no skill document at all declines to a verdict ----------
    # Otherwise "zero unresolved references" would be satisfiable by a Power that
    # ships no skill content to link between.
    with pytest.raises(Unevaluable):
        check_cross_references(
            ValidationContext(
                tree=PowerTree.from_mapping({PLUGIN_MANIFEST: "{}\n"}),
                tag=_RESOLVED_TAG,
            )
        )

# ===========================================================================
# Property 13: Skill frontmatter is complete, correct, and individually reported
# ===========================================================================
#
# Two claims in one property, and neither is worth much without the other. The
# first is about *one* file: frontmatter validation passes exactly when `name` is
# present, non-blank, and equal to its containing directory name; `description`
# is present, non-blank, at most 1024 characters, and carries that skill's
# declared trigger phrase; and `license` is present and non-blank *(R8 AC5, AC6)*.
# The second is about the *report*: a Power carrying *n* `SKILL.md` files yields
# exactly *n* frontmatter results, one per file, whatever any of them contains
# *(R13 AC3)*.
#
# Why "one result per file" is not bookkeeping
# --------------------------------------------
# It is the shape a Maintainer acts on, and there are three distinct ways to get
# it wrong that a test asking only "was something reported?" would pass over. A
# sweep that let one bad file abort it records one fail where *n* results were
# due, and the other *n-1* skills go unmeasured. An aggregate result says the
# skill set is broken without saying which skill. A result *per defect* inflates
# one file's three faults into three verdicts. So the assertions are counts and
# a per-path pairing: exactly one result per `SKILL.md`, each one's verdict
# matching that file's own validity, and no result for the deeper `SKILL.md` the
# glob must not reach.
#
# The findings *within* a result are compared as a **set**, not searched for a
# member, which is the other half of "complete": a validator that reported the
# first fault and stopped, or that skipped the `license` rules once `name`
# failed, produces a strict subset and fails here. Because `frontmatter()` seeds
# exactly one defect per case, a file carrying two or three is composed below
# from three draws, one per field — see `_merged_fields`.
#
# Two oracles, as with the MCP declaration
# ----------------------------------------
# `_reference_frontmatter_rules` computes the rules a field mapping must violate
# from R8 AC5 and AC6 directly, against literals spelled in this section. It is
# an oracle, not a restatement: it never asks the validator what it expected, and
# `_DESCRIPTION_LIMIT` is written out here so an edit on either side cannot move
# both sides of the comparison at once — the two constants that carry the ceiling
# in the validator and in the generator are asserted equal to it instead.
# `_labeled_frontmatter_rules` reads the same answer off the generator's defect
# labels. Their equality is the biconditional the strategies module documents,
# and a label this section does not describe raises rather than passing quietly.
#
# The trigger phrase, from whichever document declares it
# -------------------------------------------------------
# R8 AC6 is a claim about *two* documents: the produced description has to carry
# the phrase the template source skill declared. So both readings are driven. At
# the pure-rule level the phrase is an argument, which is how a phrase that the
# adaptation dropped is expressed without a filesystem. At the recorded-result
# level a source tree is supplied, and the phrase is read out of the *template*
# document — with the produced file's own declaration as the fallback for a
# `kiro-owned` skill or a run with no source tree, where the produced document is
# the declaring one. The dropped-phrase clause uses a phrase from
# `TRIGGER_PHRASES`, whose words the generator's own prose cannot spell, so the
# drop is a real drop and not a coincidence of two generated sentences.
#
# No staging tree
# ---------------
# Every rule here is a pure function of a parsed mapping, and the registered
# sweep runs over a `PowerTree.from_mapping`, so the whole property runs off
# `frontmatter()` with no transform run, no filesystem, and no tag that matters.
# The purity is asserted too: the mapping handed in comes back unmutated, and the
# same file twice yields the identical result.
#
# The zero case
# -------------
# "Exactly *n* results" must not be satisfiable by a Power with no skills, so the
# one condition that declines to a verdict is asserted directly: a tree carrying
# no `skills/*/SKILL.md` raises rather than recording zero passing results.
#
# Deliberately out of scope: the structural rules (`frontmatter-readable`,
# `frontmatter-yaml`, `frontmatter-mapping`) fire only for a document that cannot
# yield a field mapping at all, which is not something `frontmatter()` emits;
# whether the *engine* wrote the frontmatter it did is Property 10's; and whether
# a skill's relative links resolve is Property 12's.

#: The three fields R8 AC5 requires present and non-empty. Asserted equal to the
#: set the engine writes, which is how a writer and a gate targeting different
#: field sets would be caught.
_FRONTMATTER_FIELDS = ("name", "description", "license")

#: The Agent_Plugins_Format ceiling on a description, as R8 AC5 and the design's
#: Property 13 state it. Spelled here, and asserted equal to the engine's and the
#: generator's copies rather than imported from either.
_DESCRIPTION_LIMIT = 1024

#: The rules the per-field criteria can name. `Finding.details["rule"]` is the
#: vocabulary a report consumer reads a violation by, so the expectations below
#: are stated in it rather than by matching message prose.
_MISMATCH_RULE = "name-matches-directory"
_TOO_LONG_RULE = "description-max-length"
_CONTAINS_PHRASE_RULE = "description-contains-trigger-phrase"
_PER_FIELD_RULES = frozenset(
    {f"{key}-present" for key in _FRONTMATTER_FIELDS}
    | {f"{key}-non-blank" for key in _FRONTMATTER_FIELDS}
    | {_MISMATCH_RULE, _TOO_LONG_RULE, _CONTAINS_PHRASE_RULE}
)

#: The `frontmatter()` cases this property relies on, so a generator change that
#: dropped one fails here instead of quietly narrowing the property.
_REQUIRED_FRONTMATTER_CASES = frozenset(
    {
        "valid",
        "missing_key",
        "empty_string",
        "whitespace_only",
        "long_description",
        "name_directory_mismatch",
    }
)

#: How a seeded defect label names its rule. The two blank flavors are one rule —
#: whitespace is empty — and the key-carrying labels are read after their prefix.
_MISSING_DEFECT_PREFIX = "missing:"
_BLANK_DEFECT_PREFIXES = ("blank:", "whitespace:")
_DEFECT_RULES: Mapping[str, str] = {
    "description-too-long": _TOO_LONG_RULE,
    "name-directory-mismatch": _MISMATCH_RULE,
}

#: What sits under the frontmatter of a produced `SKILL.md`. No rule reads it; it
#: is here because a skill entry point with a body is the document shape the
#: fence splitter is handed in the pipeline.
_SKILL_BODY = "\n# Skill\n\nOne paragraph of instructional prose.\n"

#: A `SKILL.md` one directory too deep, carrying no frontmatter at all. It is a
#: supporting document rather than a skill's entry point, so the sweep must not
#: reach it — and if it did, its structural fault would change both the result
#: count and a verdict.
_NESTED_SKILL_DOCUMENT = "# Supporting document\n\nNo frontmatter block here.\n"

#: A passing result from a different check, so a withheld tag below can only have
#: come from `skill-frontmatter`.
_PASSING_MCP_SIBLING = CheckResult(id="mcp-schema", target=MCP_MANIFEST)


def _field_of(rule: str) -> str:
    """The frontmatter key a per-field rule is about, read off the rule name."""
    return rule.split("-", 1)[0]


def _rules_of(findings: Sequence[Any]) -> tuple[str, ...]:
    """The rule each finding names, in the order the findings were produced."""
    return tuple(finding.details["rule"] for finding in findings)


def _in_evaluation_order(rules: Iterable[str]) -> tuple[str, ...]:
    """`rules` in the engine's declared evaluation order, deduplicated.

    Comparing a finding sequence against this pins three things at once: the set
    of rules, the absence of a rule reported twice, and the order a Maintainer
    reads them in.
    """
    wanted = frozenset(rules)
    return tuple(rule for rule in FRONTMATTER_RULES if rule in wanted)


def _reference_string_rules(fields: Mapping[str, Any], key: str) -> frozenset[str]:
    """`key` present and a non-blank string, as R8 AC5 states it.

    Whitespace is empty: a `description` of `"   "` is a description nothing can
    activate on. The absent case and the blank case are separate rules because
    they are separate faults with the same fix.
    """
    if key not in fields:
        return frozenset({f"{key}-present"})
    value = fields[key]
    if not isinstance(value, str) or value.strip() == "":
        return frozenset({f"{key}-non-blank"})
    return frozenset()


def _reference_frontmatter_rules(
    fields: Mapping[str, Any], *, directory: str, trigger_phrase: str
) -> frozenset[str]:
    """The rules R8 AC5 and AC6 require reported for one field mapping.

    Written from the acceptance criteria against this section's literals, so it
    is a second opinion rather than an echo of the comparison under test.

    A field that is absent or blank hides the rules behind it: there is no name to
    compare against a directory and no description to measure or search, and
    reporting "declares no name" *and* "name does not match the directory" for one
    missing field is two restatements of one fault (R13 AC4 asks for the rule
    violated, not for every rule that could not be reached).
    """
    name_rules = _reference_string_rules(fields, "name")
    rules = set(name_rules)
    if not name_rules and fields["name"] != directory:
        rules.add(_MISMATCH_RULE)

    description_rules = _reference_string_rules(fields, "description")
    rules |= description_rules
    if not description_rules:
        description = fields["description"]
        # Independent rules: a description that is both too long and no longer
        # carries its phrase is two defects with two fixes.
        if len(description) > _DESCRIPTION_LIMIT:
            rules.add(_TOO_LONG_RULE)
        if trigger_phrase not in description:
            rules.add(_CONTAINS_PHRASE_RULE)

    return frozenset(rules | _reference_string_rules(fields, "license"))


def _labeled_rule(defect: str) -> str:
    """The rule one seeded defect label names.

    `_DEFECT_RULES` is indexed rather than searched, so a case seeding a label
    this section does not describe raises instead of being silently ignored.
    """
    if defect.startswith(_MISSING_DEFECT_PREFIX):
        return f"{defect[len(_MISSING_DEFECT_PREFIX):]}-present"
    for prefix in _BLANK_DEFECT_PREFIXES:
        if defect.startswith(prefix):
            return f"{defect[len(prefix):]}-non-blank"
    return _DEFECT_RULES[defect]


def _labeled_frontmatter_rules(case: FrontmatterCase) -> frozenset[str]:
    """The same rule set, read off the generator's defect labels instead."""
    return frozenset(_labeled_rule(defect) for defect in case.defects)


def _field_rules(case: FrontmatterCase, field: str) -> frozenset[str]:
    """The rules `case`'s labels name for one field alone."""
    return frozenset(
        rule for rule in _labeled_frontmatter_rules(case) if _field_of(rule) == field
    )


def _merged_fields(
    named: FrontmatterCase, described: FrontmatterCase, licensed: FrontmatterCase
) -> dict[str, Any]:
    """One field mapping carrying each case's state for one field.

    `frontmatter()` seeds one defect per case, so a file carrying two or three is
    not something it produces on its own — and a file with one fault per field is
    exactly what distinguishes "reports everything wrong here" from "reports the
    first thing wrong here". Each contributor supplies its own value for its own
    field, and drops the field where it dropped it.

    Which draw contributes which field is what keeps every label's meaning intact:
    the directory is the `name` contributor's, so its name state stays valid or
    mismatched as its label says, and the phrase is the `description`
    contributor's for the same reason.
    """
    return {
        key: case.fields[key]
        for case, key in (
            (named, "name"),
            (described, "description"),
            (licensed, "license"),
        )
        if key in case.fields
    }


def _skill_document(fields: Mapping[str, Any]) -> str:
    """A produced `SKILL.md`: `fields` rendered as frontmatter, over a body."""
    body = yaml.safe_dump(
        dict(fields),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10**6,
    )
    return f"---\n{body}---\n{_SKILL_BODY}"


def _source_skill_document(directory: str, phrase: str) -> str:
    """A *template* `SKILL.md` whose description declares `phrase`.

    The template's own clause shape. This is the declaring document on the ported
    path, so what R8 AC6 requires of the produced description is measured against
    the phrase stated here.
    """
    return (
        "---\n"
        f"name: {directory}\n"
        f'description: Work through {directory}. Use when the user says "{phrase}".\n'
        f"---\n{_SKILL_BODY}"
    )


def _assert_findings_name_the_violation(
    findings: Sequence[Any],
    *,
    expected: frozenset[str],
    path: str,
    fields: Mapping[str, Any],
    directory: str,
) -> None:
    """The findings are exactly `expected`, each naming its file, key, and rule.

    R13 AC4 asks for the offending file and the specific rule violated, so every
    finding is checked to carry the path, the frontmatter key as its location, and
    both sides of the comparison in `details` as data rather than only in prose.
    """
    rules = _rules_of(findings)
    assert rules == _in_evaluation_order(expected), (path, rules, sorted(expected))

    for finding, rule in zip(findings, rules):
        field = _field_of(rule)
        assert rule in FRONTMATTER_RULES, rule
        assert finding.code == E_FRONTMATTER_INVALID
        assert finding.severity == SEVERITY_ERROR
        assert finding.target == path
        assert finding.location == f"frontmatter.{field}"
        assert path in finding.message
        payload = finding.to_json()
        assert payload["code"] == E_FRONTMATTER_INVALID
        assert payload["location"] == finding.location
        assert payload["rule"] == rule
        assert payload["severity"] == SEVERITY_ERROR

        if rule.endswith("-present"):
            # R8 AC5: the field is absent, and the message says which.
            assert field not in fields
            assert repr(field) in finding.message
        elif rule.endswith("-non-blank"):
            value = fields[field]
            assert not isinstance(value, str) or value.strip() == ""
        elif rule == _MISMATCH_RULE:
            # R8 AC1, AC5: the declared identity and the one the path gives it.
            assert finding.details["declared"] == fields["name"]
            assert finding.details["expected"] == directory
            assert repr(fields["name"]) in finding.message
            assert repr(directory) in finding.message
        elif rule == _TOO_LONG_RULE:
            # R8 AC5: the length found and the ceiling it passed.
            assert finding.details["length"] == len(fields["description"])
            assert finding.details["limit"] == _DESCRIPTION_LIMIT
            assert finding.details["length"] > _DESCRIPTION_LIMIT
        elif rule == _CONTAINS_PHRASE_RULE:
            # R8 AC6: the phrase the description was supposed to carry.
            phrase = finding.details["triggerPhrase"]
            assert isinstance(phrase, str) and phrase.strip() == phrase and phrase
            assert phrase not in fields["description"]
            assert repr(phrase) in finding.message


# Feature: senzing-bootcamp-power, Property 13: Skill frontmatter is complete,
# correct, and individually reported
#
# Validates: Requirements 8.5, 8.6, 13.3
@settings(max_examples=200)
@given(
    frontmatter(),
    frontmatter(),
    frontmatter(),
    st.lists(frontmatter(), min_size=1, max_size=3),
    FRONTMATTER_CASES["valid"],
    st.sampled_from(tuple(TRIGGER_PHRASES.values())),
)
def test_skill_frontmatter_is_complete_correct_and_individually_reported(
    named: FrontmatterCase,
    described: FrontmatterCase,
    licensed: FrontmatterCase,
    siblings: list[FrontmatterCase],
    conforming: FrontmatterCase,
    source_phrase: str,
) -> None:
    # The generator cases this property draws from, asserted rather than assumed.
    assert _REQUIRED_FRONTMATTER_CASES <= set(FRONTMATTER_CASES)

    # R8 AC5: the gate enforces the field set the engine writes, and the ceiling
    # is one number on all three sides — the criterion's, the engine's, and the
    # generator's — rather than three that can drift apart.
    assert tuple(SKILL_REQUIRED_FIELDS) == _FRONTMATTER_FIELDS
    assert MAX_DESCRIPTION_LENGTH == _DESCRIPTION_LIMIT
    assert GENERATOR_DESCRIPTION_LIMIT == _DESCRIPTION_LIMIT
    assert _PER_FIELD_RULES <= set(FRONTMATTER_RULES)

    # R13 AC3: the unit of record is a skill's entry point, one directory deep.
    assert SKILL_MD_GLOB == f"skills/*/{SKILL_MANIFEST}"
    registered = registered_check("skill-frontmatter")
    assert registered is not None
    assert registered.code == E_FRONTMATTER_INVALID
    assert registered.target == SKILL_MD_GLOB

    # --- Clause 1: the per-field rules, over a parsed mapping ---------------
    for case in (named, described, licensed, conforming, *siblings):
        directory = case.directory
        path = f"skills/{directory}/{SKILL_MANIFEST}"
        # A copy the rules are handed, so mutation is detectable below.
        fields = deepcopy(dict(case.fields))

        # The two oracles agree, and passing is exactly the no-defect case.
        required = _reference_frontmatter_rules(
            case.fields, directory=directory, trigger_phrase=case.trigger_phrase
        )
        assert required == _labeled_frontmatter_rules(case)
        assert (required == frozenset()) is case.valid

        findings = frontmatter_findings(
            fields, target=path, directory=directory, trigger_phrase=case.trigger_phrase
        )
        _assert_findings_name_the_violation(
            findings,
            expected=required,
            path=path,
            fields=case.fields,
            directory=directory,
        )
        # R8 AC5, AC6: zero findings exactly for a conforming frontmatter.
        assert (findings == ()) is case.valid

        # Every field is examined whatever any of them reports, so one result
        # names the whole of what a Maintainer has to fix in that file.
        name_findings = skill_name_findings(fields, target=path, directory=directory)
        description_findings = skill_description_findings(
            fields, target=path, trigger_phrase=case.trigger_phrase
        )
        license_findings = skill_license_findings(fields, target=path)
        assert findings == name_findings + description_findings + license_findings
        for group, field in (
            (name_findings, "name"),
            (description_findings, "description"),
            (license_findings, "license"),
        ):
            assert {_field_of(rule) for rule in _rules_of(group)} <= {field}

        # Pure over the parsed mapping: nothing mutated, same answer twice.
        assert fields == case.fields
        assert (
            frontmatter_findings(
                fields,
                target=path,
                directory=directory,
                trigger_phrase=case.trigger_phrase,
            )
            == findings
        )

    # --- Clause 2: a file with a fault in more than one field ---------------
    directory = named.directory
    merged = _merged_fields(named, described, licensed)
    merged_path = f"skills/{directory}/{SKILL_MANIFEST}"
    merged_required = _reference_frontmatter_rules(
        merged, directory=directory, trigger_phrase=described.trigger_phrase
    )
    # Each contributor's label accounts for its own field, and for nothing else.
    assert merged_required == (
        _field_rules(named, "name")
        | _field_rules(described, "description")
        | _field_rules(licensed, "license")
    )
    merged_findings = frontmatter_findings(
        merged,
        target=merged_path,
        directory=directory,
        trigger_phrase=described.trigger_phrase,
    )
    # Every seeded defect is reported, not a prefix of them.
    _assert_findings_name_the_violation(
        merged_findings,
        expected=merged_required,
        path=merged_path,
        fields=merged,
        directory=directory,
    )
    assert len(merged_findings) == len(merged_required)

    # --- Clause 3: one recorded result per `SKILL.md` file ------------------
    files: dict[str, str] = {
        merged_path: _skill_document(merged),
        f"skills/{directory}/references/{SKILL_MANIFEST}": _NESTED_SKILL_DOCUMENT,
        PLUGIN_MANIFEST: "{}\n",
    }
    expected_rules: dict[str, frozenset[str]] = {merged_path: merged_required}
    expected_fields: dict[str, Mapping[str, Any]] = {merged_path: merged}
    for case in siblings:
        path = f"skills/{case.directory}/{SKILL_MANIFEST}"
        if path in files:
            continue
        # The generator's own rendering, so the tree carries the bytes it emits.
        files[path] = case.text + _SKILL_BODY
        expected_rules[path] = _labeled_frontmatter_rules(case)
        expected_fields[path] = dict(case.fields)

    tree = PowerTree.from_mapping(files)
    context = ValidationContext(tree=tree, tag=_RESOLVED_TAG)
    assert tree.skill_md_paths() == tuple(sorted(expected_rules))

    results = check_skill_frontmatter(context)
    # R13 AC3: exactly *n* results for *n* files, one each, in path order — and
    # the deeper `SKILL.md` is not one of them.
    assert len(results) == len(expected_rules)
    assert tuple(result.target for result in results) == tuple(sorted(expected_rules))
    assert len({result.target for result in results}) == len(results)

    for result in results:
        path = result.target
        fields = expected_fields[path]
        required = expected_rules[path]
        assert result.id == "skill-frontmatter"

        # R13 AC4: this file's own findings, however many, in one result.
        _assert_findings_name_the_violation(
            result.findings,
            expected=required,
            path=path,
            fields=fields,
            directory=skill_directory_name(path),
        )
        # The verdict is this file's own validity, not the sweep's.
        assert result.result == (RESULT_PASS if required == frozenset() else RESULT_FAIL)
        assert result.passed is (required == frozenset())

        # The rules were applied to the fields the file declares.
        read = SkillFrontmatter.read(tree, path)
        assert read.readable and read.findings == ()
        assert read.fields == fields
        assert read.directory == skill_directory_name(path)

        description = fields.get("description")
        assert result.extra["skill"] == skill_directory_name(path)
        assert result.extra["descriptionLimit"] == _DESCRIPTION_LIMIT
        assert result.extra["descriptionLength"] == (
            len(description) if isinstance(description, str) else None
        )
        assert len(result.extra["violations"]) == len(result.findings)
        # No source tree, so the produced document is the declaring one.
        assert result.extra["triggerPhraseOrigin"] in (None, TRIGGER_SOURCE_PRODUCED)
        # A function of the tree and the path alone.
        assert skill_frontmatter_result(context, path) == result

    report = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_PASSING_MCP_SIBLING, *results),
    )
    conforming_power = all(rules == frozenset() for rules in expected_rules.values())
    assert len(report.results_for("skill-frontmatter")) == len(expected_rules)
    assert report.findings_for(E_FRONTMATTER_INVALID) == tuple(
        finding for result in results for finding in result.findings
    )
    # R13 AC4, AC5: one defective `SKILL.md` withholds permission to tag, beside
    # a sibling result that passed.
    assert _PASSING_MCP_SIBLING.passed
    assert report.status == (STATUS_PASSED if conforming_power else STATUS_FAILED)
    assert report.tag_allowed is conforming_power
    assert report.failed_check_ids() == (
        () if conforming_power else ("skill-frontmatter",)
    )

    # --- Clause 4: no `SKILL.md` at all declines to a verdict ---------------
    # Otherwise "every recorded result is a pass" would be satisfiable by a Power
    # that ships no skills.
    with pytest.raises(Unevaluable):
        check_skill_frontmatter(
            ValidationContext(
                tree=PowerTree.from_mapping(
                    {
                        PLUGIN_MANIFEST: "{}\n",
                        f"skills/{directory}/references/{SKILL_MANIFEST}": (
                            _NESTED_SKILL_DOCUMENT
                        ),
                    }
                ),
                tag=_RESOLVED_TAG,
            )
        )

    # --- Clause 5: the phrase comes from the document that declared it ------
    conforming_path = f"skills/{conforming.directory}/{SKILL_MANIFEST}"
    assert conforming.valid and conforming.defects == ()
    # Non-vacuous by construction: the source phrase is one the produced
    # description does not spell, so its absence is a drop and not a collision.
    assert source_phrase not in conforming.fields["description"]
    assert _reference_frontmatter_rules(
        conforming.fields,
        directory=conforming.directory,
        trigger_phrase=source_phrase,
    ) == frozenset({_CONTAINS_PHRASE_RULE})

    produced = PowerTree.from_mapping({conforming_path: conforming.text + _SKILL_BODY})
    source = PowerTree.from_mapping(
        {conforming_path: _source_skill_document(conforming.directory, source_phrase)}
    )

    # R8 AC6 against the source skill: the adaptation is additive, so the phrase
    # the template stated has to survive it verbatim.
    measured = skill_frontmatter_result(
        ValidationContext(tree=produced, tag=_RESOLVED_TAG, source=source),
        conforming_path,
    )
    assert _rules_of(measured.findings) == (_CONTAINS_PHRASE_RULE,)
    assert measured.findings[0].details["triggerPhrase"] == source_phrase
    assert measured.extra["triggerPhrase"] == source_phrase
    assert measured.extra["triggerPhraseOrigin"] == TRIGGER_SOURCE_TEMPLATE
    assert measured.extra["triggerPhraseDeclaredIn"] == conforming_path
    assert measured.result == RESULT_FAIL

    # The contrast: the same produced file, measured against its own declaration,
    # passes. So the finding above came from the comparison and not from the file.
    alone = skill_frontmatter_result(
        ValidationContext(tree=produced, tag=_RESOLVED_TAG), conforming_path
    )
    assert alone.findings == () and alone.passed
    assert alone.extra["triggerPhrase"] == conforming.trigger_phrase
    assert alone.extra["triggerPhraseOrigin"] == TRIGGER_SOURCE_PRODUCED
    assert alone.extra["triggerPhraseDeclaredIn"] == conforming_path

# ===========================================================================
# Property 14: The Senzing MCP declaration is exact
# ===========================================================================
#
# The Senzing MCP server is the one dependency the whole bootcamp rests on, so
# R11 states it as an *equality*: the `senzing` server declared, its `url`
# exactly `https://mcp.senzing.com/mcp`, its `type` exactly `streamable-http`,
# and `$schema` present. R11 AC4 then makes a near miss a fault of the same
# standing as an absence. Two rule sets look at the one produced file — schema
# conformance against the vendored Agent Plugins v1.0.0 MCP schema, reported
# under `E_SCHEMA_INVALID` *(R4 AC3, R13 AC2)*, and the exactness rules,
# reported under `E_MCP_INVALID` *(R11 AC1, AC3-AC5)* — and both are checked
# here, because each one's evidence is only worth what the other's blindness
# leaves it.
#
# Why the schema's blindness is asserted, not assumed
# ---------------------------------------------------
# The vendored schema cannot express exactness: `url` is any non-empty string,
# and `streamable-http` and `sse` are both admitted transports. So
# `http://mcp.senzing.com/mcp` conforms *perfectly* and still points a
# Bootcamper at a plaintext endpoint, and `sse` at the right URL conforms and
# still declares the wrong transport. A property that only asked "was something
# reported?" would let a schema violation stand in for an exactness violation
# and would pass while the rules it is about did nothing. So the near-miss
# clauses assert the conformance rules produce **nothing** and the exactness
# rules produce the finding. If a schema refresh ever did start rejecting a near
# miss, that is a change in what the gate rests on and it surfaces here
# deliberately rather than silently making a clause vacuous.
#
# The claim is an equality, not an existence
# ------------------------------------------
# `senzing_declaration_findings` must report *exactly* the violating elements —
# no more, no fewer — so the set of `Finding.location`s it produces is compared
# against that set computed twice, independently:
#
# - `_reference_violations` reads the document and applies R11 AC1, AC3, AC4,
#   and AC5 against the literal strings the requirement fixes. It is an oracle,
#   not a restatement: it never asks the validator what it expected, and the
#   literals are spelled here so a producer-side rename cannot move both sides
#   of the comparison at once.
# - `_labeled_violations` reads the generator's defect labels. Equality between
#   the two is the biconditional the strategies module documents — the label
#   names what was seeded, the empty tuple means "no defect" — and it fails
#   loudly if a future case seeds a combination this mapping does not describe.
#
# The positions themselves (`mcpServers.senzing.url`, `$schema`) are literals
# too, because they are what a Maintainer reads to find the offending field:
# "the validator reported *something* somewhere" is not what R11 AC3-AC5 ask
# for. Each finding is then checked to name the offending field, the value it
# found, and the value R11 requires, in `details` as data and in the message as
# prose.
#
# No staging tree
# ---------------
# Both rule sets are pure functions of a *parsed document*, and the registered
# `mcp-schema` check runs over a `PowerTree.from_mapping`, so the recorded
# result and the release gate are exercised from `mcp_document()` directly —
# no transform run, no filesystem, no tag. The purity is also asserted: the
# same document twice yields the identical findings, and the call does not
# mutate what it was handed.
#
# The gate
# --------
# R11 AC3, AC4, and AC5 each end in "SHALL prevent the release from being
# tagged, leaving the existing release tags unchanged". `tagAllowed` is derived
# from the recorded results, so what this property pins is that a single
# defective `mcp.json` withholds permission *on its own*: the report carries a
# passing sibling result beside it, so a blocked tag can only have come from
# this check. That existing tags survive a blocked run is Property 6's subject —
# it is a claim about the filesystem, and nothing here reaches one.

#: The two strings R11 AC1 fixes and the schema id R11 AC5 requires, spelled as
#: the requirement spells them. Asserted equal to the values the engine and the
#: gate share, which is how a producer that emitted one URL and a gate that
#: demanded another would be caught (R11 AC2).
_REQUIRED_MCP_URL = "https://mcp.senzing.com/mcp"
_REQUIRED_MCP_TRANSPORT = "streamable-http"
_REQUIRED_MCP_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

#: The `senzing` server key, matched exactly: `Senzing` is a near miss.
_SENZING_KEY = "senzing"

#: Where a finding for each rule must point. These are the positions a
#: Maintainer reads, so they are stated rather than composed from the
#: validator's own constants.
_SCHEMA_FIELD_LOCATION = "$schema"
_SERVERS_LOCATION = "mcpServers"
_URL_LOCATION = "mcpServers.senzing.url"
_TYPE_LOCATION = "mcpServers.senzing.type"

#: A transport the vendored schema admits under its own `sse` branch. Named here
#: because it is the sharpest case for why the exactness rules exist: a document
#: declaring it is schema-valid and requirement-invalid at the same time.
_SCHEMA_ADMITTED_WRONG_TRANSPORT = "sse"

#: The `mcp_document()` cases this property relies on, so a generator change
#: that dropped one fails here instead of quietly narrowing the property.
_REQUIRED_MCP_CASES = frozenset(
    {
        "valid",
        "near_miss_url",
        "wrong_type",
        "missing_schema",
        "missing_senzing_server",
        "multiple_defects",
    }
)

#: Which position each seeded defect label must be reported at. URL labels carry
#: the near-miss name after the prefix (`url:http-scheme`), so they are matched
#: by prefix; every other label is exact, and an unknown one raises rather than
#: being silently ignored.
_URL_DEFECT_PREFIX = "url:"
_DEFECT_LOCATIONS: Mapping[str, str] = {
    "type": _TYPE_LOCATION,
    "missing-schema": _SCHEMA_FIELD_LOCATION,
    "missing-senzing-server": _SERVERS_LOCATION,
}

#: A check that found nothing, standing in for the rest of a passing run. With
#: it in the report, a withheld tag can only have come from `mcp-schema`.
_PASSING_SIBLING = CheckResult(id="plugin-schema", target=PLUGIN_MANIFEST)


def _reference_violations(document: Mapping[str, Any]) -> frozenset[str]:
    """The positions R11 requires a finding at, computed from the document.

    Written from R11 AC1, AC3, AC4, and AC5 against this section's literals, so
    it is a second opinion rather than an echo of the comparisons under test.

    A server that is not declared as an object hides the two value positions
    behind it: there is no URL and no transport type to compare, and reporting
    against positions that do not exist would send a Maintainer looking for
    fields rather than for the mandatory dependency *(R11 AC3)*.
    """
    violations: set[str] = set()
    if _SCHEMA_FIELD_LOCATION not in document:
        violations.add(_SCHEMA_FIELD_LOCATION)
    servers = document.get(_SERVERS_LOCATION)
    server = servers.get(_SENZING_KEY) if isinstance(servers, Mapping) else None
    if not isinstance(server, Mapping):
        violations.add(_SERVERS_LOCATION)
        return frozenset(violations)
    if server.get("url") != _REQUIRED_MCP_URL:
        violations.add(_URL_LOCATION)
    if server.get("type") != _REQUIRED_MCP_TRANSPORT:
        violations.add(_TYPE_LOCATION)
    return frozenset(violations)


def _labeled_violations(case: McpDocumentCase) -> frozenset[str]:
    """The same set, read off the generator's defect labels instead."""
    return frozenset(
        _URL_LOCATION
        if defect.startswith(_URL_DEFECT_PREFIX)
        else _DEFECT_LOCATIONS[defect]
        for defect in case.defects
    )


def _mcp_conformance(document: Any) -> tuple[Any, ...]:
    """Schema violations of `document`, under the code the `mcp.json` check uses."""
    return schema_findings(
        document, MCP_SCHEMA_ID, target=MCP_MANIFEST, code=E_SCHEMA_INVALID
    )


def _recorded_mcp_result(document: Mapping[str, Any]) -> CheckResult:
    """The registered `mcp-schema` result for one document, with no filesystem.

    Serialized and read back through the check's own reader, so the document the
    rules see is one that survived a JSON round trip — the shape a produced
    `mcp.json` actually reaches the gate in.
    """
    tree = PowerTree.from_mapping(
        {MCP_MANIFEST: json.dumps(document, indent=2, sort_keys=True) + "\n"}
    )
    return check_mcp_schema(ValidationContext(tree=tree, tag=_RESOLVED_TAG))


def _without_senzing_url(document: Mapping[str, Any]) -> dict[str, Any]:
    """`document` with the `senzing` server's `url` removed.

    Two documents equal under this differ in the URL and in nothing else, which
    is what makes a near miss a *near* miss rather than a different document.
    """
    stripped = deepcopy(dict(document))
    stripped[_SERVERS_LOCATION][_SENZING_KEY].pop("url", None)
    return stripped


# Feature: senzing-bootcamp-power, Property 14: The Senzing MCP declaration is
# exact
#
# Validates: Requirements 4.3, 11.1, 11.2, 11.3, 11.4, 11.5
@settings(max_examples=200)
@given(
    mcp_document(),
    MCP_DOCUMENT_CASES["valid"],
    MCP_DOCUMENT_CASES["near_miss_url"],
)
def test_the_senzing_mcp_declaration_is_exact(
    drawn: McpDocumentCase,
    conforming: McpDocumentCase,
    near_miss: McpDocumentCase,
) -> None:
    # The generator cases this property draws from, asserted rather than assumed.
    assert _REQUIRED_MCP_CASES <= set(MCP_DOCUMENT_CASES)

    # R11 AC1, AC2: the gate demands exactly the strings the requirement fixes,
    # and they are the same strings the transform engine emits — `validate`
    # imports them from `transform`, so producer and gate cannot disagree about
    # what "exactly" means.
    assert SENZING_MCP_URL == _REQUIRED_MCP_URL
    assert MCP_TRANSPORT_TYPE == _REQUIRED_MCP_TRANSPORT
    assert MCP_SCHEMA_ID == _REQUIRED_MCP_SCHEMA_ID
    assert SENZING_SERVER_KEY == _SENZING_KEY
    assert MCP_SERVERS_FIELD == _SERVERS_LOCATION
    assert MCP_SCHEMA_FIELD == _SCHEMA_FIELD_LOCATION

    # R4 AC3, R13 AC2: `mcp.json` is the file measured, and the MCP schema is
    # what it is measured against.
    assert MANIFEST_SCHEMAS[MCP_MANIFEST] == MCP_SCHEMA_ID
    registered = registered_check("mcp-schema")
    assert registered is not None
    assert registered.code == E_MCP_INVALID
    assert registered.target == MCP_MANIFEST

    # Non-vacuous by construction: the conforming draw really conforms, and the
    # near-miss draw is one URL away from it.
    assert conforming.valid and conforming.defects == ()
    assert len(near_miss.defects) == 1
    assert near_miss.defects[0].startswith(_URL_DEFECT_PREFIX)
    assert not near_miss.valid

    for case in (drawn, conforming, near_miss):
        # A copy the rules are handed, so mutation is detectable at the end.
        document = deepcopy(case.document)
        assert _SERVERS_LOCATION in case.document

        exactness = senzing_declaration_findings(document, target=MCP_MANIFEST)
        conformance = _mcp_conformance(document)
        required = _reference_violations(case.document)

        # --- Clause 1: exactly the violating elements, no more, no fewer -----
        # The two oracles agree, and the validator's positions are theirs.
        assert required == _labeled_violations(case)
        locations = tuple(finding.location for finding in exactness)
        assert len(set(locations)) == len(locations)
        assert frozenset(locations) == required
        # R11: zero findings exactly for a document that declares Senzing
        # exactly; at least one for every other document.
        assert (exactness == ()) is case.valid
        assert (required == frozenset()) is case.valid

        # --- Clause 2: each finding names the offending element --------------
        by_location = {finding.location: finding for finding in exactness}
        for location, finding in by_location.items():
            assert finding.code == E_MCP_INVALID
            assert finding.severity == SEVERITY_ERROR
            assert finding.target == MCP_MANIFEST
            assert MCP_MANIFEST in finding.message
            payload = finding.to_json()
            assert payload["code"] == E_MCP_INVALID
            assert payload["location"] == location
            assert payload["severity"] == SEVERITY_ERROR

        if _SCHEMA_FIELD_LOCATION in by_location:
            # R11 AC5: the omitted field, and the schema id it must carry.
            finding = by_location[_SCHEMA_FIELD_LOCATION]
            assert finding.details["field"] == _SCHEMA_FIELD_LOCATION
            assert finding.details["expected"] == _REQUIRED_MCP_SCHEMA_ID
            assert _SCHEMA_FIELD_LOCATION in finding.message

        if _SERVERS_LOCATION in by_location:
            # R11 AC3: the mandatory dependency, and the names actually declared
            # — a Maintainer cannot see a `Senzing`-for-`senzing` case
            # difference in a message that omits it.
            finding = by_location[_SERVERS_LOCATION]
            declared = sorted(case.document[_SERVERS_LOCATION])
            assert finding.details["server"] == _SENZING_KEY
            assert finding.details["expected"] == _SENZING_KEY
            assert finding.details["declared"] == declared
            for name in declared:
                assert name in finding.message, name

        server = case.document[_SERVERS_LOCATION].get(_SENZING_KEY)
        for location, field, expected in (
            (_URL_LOCATION, "url", _REQUIRED_MCP_URL),
            (_TYPE_LOCATION, "type", _REQUIRED_MCP_TRANSPORT),
        ):
            if location not in by_location:
                continue
            # R11 AC4: the invalid value, as found and as required.
            finding = by_location[location]
            assert finding.details["server"] == _SENZING_KEY
            assert finding.details["field"] == field
            assert finding.details["declared"] == server.get(field)
            assert finding.details["expected"] == expected
            assert repr(server.get(field)) in finding.message
            assert repr(expected) in finding.message

        # --- Clause 3: schema conformance, and what it cannot see ------------
        for finding in conformance:
            assert finding.code == E_SCHEMA_INVALID
            assert finding.severity == SEVERITY_ERROR
            assert finding.target == MCP_MANIFEST
            assert finding.details["schema"] == MCP_SCHEMA_ID
        if case.valid:
            # R4 AC3: the exactly-declaring document conforms, so a conforming
            # Power is reachable and clause 1's zero is not zero-by-rejection.
            assert conformance == ()
        if _SCHEMA_FIELD_LOCATION in required:
            # R11 AC5 has two independent detectors: `$schema` is a `required`
            # field of the MCP schema as well as an exactness rule.
            assert any(
                finding.details.get("rule") == "required" for finding in conformance
            )
        if required == {_TYPE_LOCATION} and (
            server.get("type") == _SCHEMA_ADMITTED_WRONG_TRANSPORT
        ):
            # The legacy transport at the right URL: schema-valid,
            # requirement-invalid, and the exactness rule is the only detector.
            assert conformance == ()
            assert len(exactness) == 1

        # --- Clause 4: the recorded result and the release gate --------------
        recorded = _recorded_mcp_result(case.document)
        assert recorded.id == "mcp-schema"
        assert recorded.target == MCP_MANIFEST
        assert recorded.findings == conformance + exactness
        assert recorded.result == (RESULT_PASS if case.valid else RESULT_FAIL)
        assert recorded.passed is case.valid
        assert recorded.extra["schema"] == MCP_SCHEMA_ID
        assert recorded.extra["senzingUrl"] == _REQUIRED_MCP_URL
        assert recorded.extra["senzingType"] == _REQUIRED_MCP_TRANSPORT
        assert recorded.extra["servers"] == sorted(case.document[_SERVERS_LOCATION])
        assert len(recorded.extra["violations"]) == len(recorded.findings)

        report = ValidationReport(
            template_release=_RESOLVED_TAG,
            power_version=_RESOLVED_TAG,
            checks=(_PASSING_SIBLING, recorded),
        )
        # R11 AC3, AC4, AC5: one defective `mcp.json` withholds permission to
        # tag, beside a sibling result that passed.
        assert _PASSING_SIBLING.passed
        assert report.status == (STATUS_PASSED if case.valid else STATUS_FAILED)
        assert report.tag_allowed is case.valid
        assert report.findings_for(E_MCP_INVALID) == exactness
        assert report.findings_for(E_SCHEMA_INVALID) == conformance
        assert report.failed_check_ids() == (() if case.valid else ("mcp-schema",))

        # --- Clause 5: pure over the parsed document ------------------------
        assert document == case.document
        assert senzing_declaration_findings(document, target=MCP_MANIFEST) == exactness
        assert _mcp_conformance(document) == conformance

    # --- The contrast: the schema admits every near miss --------------------
    # The near-miss draw differs from the conforming one in the `url` alone, and
    # it conforms: the schema's `url` is any non-empty string. So the finding
    # under `E_MCP_INVALID` is the only thing between a Bootcamper and the wrong
    # endpoint *(R11 AC4)*, and the exactness rules are not a second spelling of
    # the schema.
    assert _without_senzing_url(near_miss.document) == _without_senzing_url(
        conforming.document
    )
    near_miss_url = near_miss.document[_SERVERS_LOCATION][_SENZING_KEY]["url"]
    assert near_miss_url in tuple(NEAR_MISS_MCP_URLS.values())
    assert near_miss_url != _REQUIRED_MCP_URL
    assert _mcp_conformance(near_miss.document) == ()
    near_miss_findings = senzing_declaration_findings(
        near_miss.document, target=MCP_MANIFEST
    )
    assert len(near_miss_findings) == 1
    assert near_miss_findings[0].location == _URL_LOCATION
    assert near_miss_findings[0].details["declared"] == near_miss_url

# ===========================================================================
# Property 15: The validation report is complete and gates tagging
# biconditionally
# ===========================================================================
#
# This property is about the *report*, not about any one check. The other
# validator properties each pin one check's verdict; this one pins the three
# things a Maintainer relies on from the artifact those verdicts land in: that
# every produced file the requirements name is accounted for, that a defective
# Power has *all* of its defects listed rather than the first one, and that
# permission to tag is a biconditional over the recorded evidence rather than a
# judgment made beside it.
#
# A real Power, produced by the engine, that passes
# -------------------------------------------------
# The subject is a Bootcamp_Power the transform engine actually produced, from a
# Template_Release authored below, validated through the registered check set
# against the repository's own `contract.yaml`. Nothing is stubbed: all thirteen
# declared checks run, the `kiro-owned` content is the content the engine ships,
# and the base Power **passes** — `status: passed`, `tagAllowed: true`.
#
# That passing base is load-bearing twice over. It is the only way the
# biconditional's true side is reachable at all — a fixture that failed
# something would make "permission is granted exactly when nothing is wrong" an
# untestable half of a claim — and it is what makes every finding below
# attributable to a seeded defect rather than to the fixture.
#
# The release is authored rather than drawn from `template_tree()`, which
# generates random bytes for a `SKILL.md` and random imports for a script: right
# for the properties about *porting*, and incapable of producing a Power that
# passes frontmatter validation. What is drawn here is the **defect set** —
# which of the thirteen are seeded, and therefore how many. The build and each
# defect's isolated footprint are computed once and cached, so an example costs
# one validation run.
#
# One defect per check, and why they must not interact
# ---------------------------------------------------
# `_DEFECTS` carries one defect per declared check id, keyed by the check that
# owes the verdict, each with the code it must be reported under, the detail that
# must name the violated rule, and the file it must name. Eleven change the
# produced tree; two change the *contract*, because the register the
# `invariant-discounts` check reads and the progression declaration the
# `progression-order` check reads live there rather than in the Power.
#
# "Independent" is asserted, not assumed: measured alone, every defect's findings
# lie entirely within its own check. Two consequences of editing bytes at all are
# neutralized rather than left to leak, both in `_remanifest` — an edited file's
# Build_Manifest hash is recomputed and a deleted file's record is dropped — so
# the hash check's verdict stays a function of the one defect that is *about*
# hashes.
#
# Not a prefix, stated as an equality
# -----------------------------------
# "All *k*, not a prefix" is asserted three ways, weakest to strongest. Each
# seeded defect has a finding naming its file and its rule *(R13 AC4)*. The
# report's non-passing check ids are **exactly** the seeded ones, in report order,
# so a run that returned after the first failure — or that skipped the checks
# after it — is caught by identity rather than by a count. And the whole finding
# sequence equals the concatenation of the per-defect footprints: *k* defects
# produce the sum of what each produces alone, with nothing dropped and nothing
# invented.
#
# The gate
# --------
# `tagAllowed`, `status == "passed"`, "every recorded result is a pass", and "the
# report carries no finding" are asserted to be one statement, and then tied back
# to the input: permission is granted exactly when nothing was seeded *(R13 AC4,
# AC5)*. The three-valued fold rides along, because the drawn set decides which
# side of it a run lands on — the residual-reference defect is the catalog's one
# warning, so a run seeded with only that defect is `incomplete` and still
# blocked, while any error-severity defect makes it `failed`.
#
# Deliberately out of scope: whether an individual check reaches the *right*
# verdict is that check's own property, and this one assumes each does in order
# to measure what the report does with them. R13 AC4's "leave the produced files
# unchanged" is asserted here as the narrow thing it means for a validator — the
# run mutates nothing it read; that the *target directory* survives a failed
# build is Property 6's.

# ---------------------------------------------------------------------------
# The authored Template_Release
# ---------------------------------------------------------------------------

#: Where the template keeps the two documents the `generate` rules supersede.
_TEMPLATE_MANIFEST_PATH = ".claude-plugin/plugin.json"
_TEMPLATE_MCP_PATH = ".mcp.json"

#: The template's own MCP transport, which the `mcp` rule translates (R11 AC2).
_TEMPLATE_MCP_TRANSPORT = "http"

#: Ported skill directories. Two is the minimum the progression declaration's
#: endpoints need — it runs from `onboarding` through `graduation` — and the
#: engine adds the `kiro-owned` skills on top, so the produced Power carries
#: `SKILL.md` files of both origins and the per-file record covers both.
_PORTED_SKILLS = ("bootcamp-onboarding", "graduation")

#: A ported document no other check reads: where the residual reference goes.
_PORTED_OVERVIEW = "docs/overview.md"

#: A sibling document a ported skill links to, so the produced Power carries a
#: cross-reference that resolves before anything is seeded.
_LINKED_DOCUMENT = "skills/bootcamp-onboarding/feedback.md"

#: A `../<ported-skill>/<document>.md` link in an authored `kiro-owned` skill body.
#: Anchored on the `../` so a same-directory or absolute link is not matched, and
#: `<document>` admits no `/`, so only a document sitting *directly* beside a ported
#: `SKILL.md` is matched. That exclusion is load-bearing: a link into
#: `../bootcamp-onboarding/assets/kiro-hooks/…` names Tier 2 hook assets, which the
#: `kiro-hooks` rule already materializes, and adding them to the release as well
#: makes two rules claim one output path (`E_TRANSFORM_FAILED`).
_SIBLING_SKILL_LINK = re.compile(r"\]\(\.\./(?P<skill>[^/)]+)/(?P<document>[^/)]+\.md)\)")

#: A ported module, and the one ported hook script that imports it. The import
#: resolves in the base Power because both land in the same directory (R10 AC1);
#: dropping the module is what the `script-imports` defect does.
_HELPER_MODULE = "helper_module"
_IMPORTING_SCRIPT = "session-start.py"

#: The trigger-phrase clause R8 AC6 requires a description to carry.
_TRIGGER_CLAUSE = "Use when the bootcamper says"


def _json_bytes(document: Any) -> bytes:
    """`document` as the LF-terminated UTF-8 JSON the engine and gate read."""
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def _template_skill_document(name: str) -> bytes:
    """A template `SKILL.md` whose adaptation satisfies every frontmatter rule.

    `name` matches the containing directory *(R8 AC1, AC5)* and the description
    states a trigger phrase *(R8 AC6)*; the engine's additive adaptation supplies
    the `license` and the provenance `metadata` the produced file also needs.
    """
    return (
        "---\n"
        f'name: "{name}"\n'
        f'description: "The {name} phase of the bootcamp. '
        f"{_TRIGGER_CLAUSE} 'begin {name}'.\"\n"
        "---\n"
        "\n"
        f"# {name}\n"
        "\n"
        f"Prose the bootcamp ships. See [feedback](../{_PORTED_SKILLS[0]}/"
        f"{Path(_LINKED_DOCUMENT).name}).\n"
    ).encode("utf-8")


def _template_hook_script(name: str) -> bytes:
    """A template hook script — one of which imports the ported helper module."""
    lines = ['"""A ported hook script."""', ""]
    if name == _IMPORTING_SCRIPT:
        lines += [f"import {_HELPER_MODULE}", ""]
    return "\n".join([*lines, "EXIT = 0", ""]).encode("utf-8")


@lru_cache(maxsize=1)
def _declared_template_commands() -> tuple[str, ...]:
    """The template commands the Power's `kiro-owned` skills stand for.

    Read out of the shipped `kiro-owned` skill frontmatter rather than listed
    here. `skill-inventory` compares the produced command-derived skills against
    the release's commands as a bijection *(R9 AC1)*, so a command skill added
    upstream has to extend the release this fixture builds — and does, rather
    than failing this property for a reason it is not about.
    """
    commands: set[str] = set()
    for path in sorted(KIRO_OWNED_ROOT.glob(f"skills/*/{SKILL_MANIFEST}")):
        fields = _frontmatter_fields(path.read_text(encoding="utf-8")) or {}
        metadata = fields.get(SKILL_METADATA_FIELD)
        declared = (
            metadata.get(TEMPLATE_COMMAND_FIELD)
            if isinstance(metadata, Mapping)
            else None
        )
        if isinstance(declared, str) and declared:
            commands.add(declared)
    return tuple(sorted(commands))


@lru_cache(maxsize=1)
def _linked_sibling_documents() -> tuple[str, ...]:
    """Ported documents the authored `kiro-owned` skills link to, sorted.

    Read out of the authored skill bodies for the same reason
    `_declared_template_commands` reads their frontmatter: a command-derived skill
    is an *entry point* that hands off to a ported workflow document, so authoring
    one adds a cross-reference into `skills/<ported>/`. The release this fixture
    builds has to carry that document, or `cross-references` fails for a reason
    Property 15 is not about — as it did when release 0.5.3's `bootcamp-note` and
    `package-bootcamp` arrived, pointing at `notes.md` and `packaging.md`.

    Only links into a skill the fixture actually ports are returned; a link into
    some other skill would need that skill in `_PORTED_SKILLS` too, and silently
    inventing one here would hide that. A link to a ported skill's own `SKILL.md`
    is excluded because `_template_skill_document` already writes that file.
    """
    ported = set(_PORTED_SKILLS)
    documents: set[str] = set()
    for path in sorted(KIRO_OWNED_ROOT.glob(f"skills/*/{SKILL_MANIFEST}")):
        body = path.read_text(encoding="utf-8")
        for match in _SIBLING_SKILL_LINK.finditer(body):
            skill, document = match.group("skill"), match.group("document")
            if skill in ported and document != SKILL_MANIFEST:
                documents.add(f"skills/{skill}/{document}")
    return tuple(sorted(documents))


def _template_release() -> dict[str, bytes]:
    """A Template_Release the engine transforms into a Power that passes.

    Every entry is here because some check needs it: the two superseded manifests
    so `plugin.json` and `mcp.json` exist to be validated at all *(R4 AC1)*, the
    commands so the inventory bijection has a left-hand side, the sibling documents
    the `kiro-owned` skills link to so `cross-references` resolves, the hook
    scripts so the shipped hook definitions invoke something that exists, and the
    vendored asset so the `copy` rule has a subject.
    """
    files: dict[str, bytes] = {
        _TEMPLATE_MANIFEST_PATH: _json_bytes(
            {"name": "senzing-bootcamp", _VERSION_FIELD: _RESOLVED_TAG}
        ),
        _TEMPLATE_MCP_PATH: _json_bytes(
            {
                MCP_SERVERS_FIELD: {
                    SENZING_SERVER_KEY: {
                        "type": _TEMPLATE_MCP_TRANSPORT,
                        "url": SENZING_MCP_URL,
                    }
                }
            }
        ),
        _PORTED_OVERVIEW: b"# Overview\n\nWhat the bootcamp covers.\n",
        _LINKED_DOCUMENT: b"# Feedback\n\nHow to give it.\n",
        f"scripts/{_HELPER_MODULE}.py": b'"""A ported helper module."""\n\nEXIT = 0\n',
        "scripts/vendor/d3.v7.min.js": b"!function(){}();\n",
    }
    for name in _PORTED_SKILLS:
        files[f"skills/{name}/{SKILL_MANIFEST}"] = _template_skill_document(name)
    for command in _declared_template_commands():
        files[f"commands/{command}.md"] = f"# /{command}\n".encode("utf-8")
    for document in _linked_sibling_documents():
        files.setdefault(
            document,
            f"# {Path(document).stem}\n\nThe ported workflow a command skill "
            "hands off to.\n".encode("utf-8"),
        )
    for script in HOOK_SCRIPT_NAMES:
        files[f"scripts/{script}"] = _template_hook_script(script)
    return files


# ---------------------------------------------------------------------------
# The base Power, built once
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _BasePower:
    """The produced Power every example starts from, and its clean report."""

    power: Mapping[str, bytes]
    release: PowerTree
    contract: Contract
    report: ValidationReport
    unchanged: bool
    skill_manifests: tuple[str, ...]


def _validated(
    files: Mapping[str, bytes], contract: Contract, release: PowerTree
) -> tuple[ValidationReport, bool]:
    """Run every check over one Power, and report whether the run wrote to it.

    The tree is held in memory, which is not a shortcut: no check reads
    `ValidationContext.staging`, the `Hook_Installer` is loaded from the tree's
    own bytes rather than imported off disk, and a mapping is the only shape in
    which "identical before and after" is a comparison rather than a directory
    walk *(R13 AC4)*.
    """
    tree = PowerTree.from_mapping(files)
    before = dict(tree.files)
    report = run_checks(
        ValidationContext(
            tree=tree, tag=_RESOLVED_TAG, contract=contract, source=release
        )
    )
    return report, dict(tree.files) == before


@lru_cache(maxsize=1)
def _base_power() -> _BasePower:
    """Transform the authored release once, and validate what came out.

    Cached for the session because it is a constant: the release is authored, the
    contract is the repository's, and the engine is deterministic *(Property 4)*.
    The staging directory exists only long enough to be read back into memory, so
    nothing outlives the build.
    """
    contract = load_contract()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "release"
        plugin_root = source.joinpath(*TEMPLATE_PLUGIN_ROOT.split("/"))
        plugin_root.mkdir(parents=True)
        for path, content in sorted(_template_release().items()):
            absolute = plugin_root.joinpath(*path.split("/"))
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_bytes(content)
        staging = root / "staging"
        write_staging(
            build_plan(contract, source, tag=_RESOLVED_TAG, staging=staging)
        )
        power = PowerTree.from_directory(staging)
        release = PowerTree.from_directory(source)
    report, unchanged = _validated(power.files, contract, release)
    return _BasePower(
        power=dict(power.files),
        release=release,
        contract=contract,
        report=report,
        unchanged=unchanged,
        skill_manifests=power.skill_md_paths(),
    )


# ---------------------------------------------------------------------------
# The defect catalog: one per declared check
# ---------------------------------------------------------------------------

#: `plugin.json` field the schema declares as an array, given a string.
_PLUGIN_KEYWORDS_FIELD = "keywords"
_KEYWORDS_NOT_AN_ARRAY = "senzing"

#: A near miss the MCP schema admits and R11 AC1 forbids: the plaintext scheme.
_INSECURE_MCP_URL = "http://mcp.senzing.com/mcp"

#: A version string that is neither the resolved tag nor the recorded provenance.
_UNMATCHED_VERSION = "9.9.9"

#: A link target the Power does not carry, and the line that spells it.
_DANGLING_LINK_TARGET = "./nowhere.md"
_DANGLING_LINK = f"\nSee [the missing note]({_DANGLING_LINK_TARGET}).\n"

#: A Claude subscription plan reference the `model-guidance` set would have
#: rewritten (R12 AC2), reintroduced into ported prose.
_RESIDUAL_PLAN_REFERENCE = "Claude Max plan"

#: A chaining operator, and the tail that carries it into a command string.
_SHELL_CONSTRUCT = "&&"
_APPENDED_SHELL_TAIL = f" {_SHELL_CONSTRUCT} echo done"

#: Names nothing on either side declares.
_ABSENT_TEMPLATE_COMMAND = "no-such-command"
_ABSENT_HOOK_SCRIPT = "no-such-script.py"

#: Files the defects act on, all of them in the base Power. The two hook
#: definitions are the Tier 3 copies, so the Tier 2 assets the `Hook_Installer`
#: reads stay intact and a defect's footprint stays inside one check.
_HASH_DRIFT_TARGET = "LICENSE"
_SHELL_DEFECT_HOOK = "dev.kiro/hooks/senzing-bootcamp-write-gate.json"
_MISSING_SCRIPT_HOOK = "dev.kiro/hooks/senzing-bootcamp-stop-nudge.json"
_MISSING_SCRIPT_NAME = "stop-nudge.py"
_FRONTMATTER_DEFECT_TARGET = f"skills/{_PORTED_SKILLS[1]}/{SKILL_MANIFEST}"
_REFERENCE_DEFECT_TARGET = f"skills/{_PORTED_SKILLS[0]}/{SKILL_MANIFEST}"
_INVENTORY_DEFECT_TARGET = f"skills/start-bootcamp/{SKILL_MANIFEST}"
_PORTED_SCRIPTS = f"skills/{_PORTED_SKILLS[0]}/scripts"
_IMPORT_DEFECT_TARGET = f"{_PORTED_SCRIPTS}/{_IMPORTING_SCRIPT}"
_DROPPED_MODULE = f"{_PORTED_SCRIPTS}/{_HELPER_MODULE}.py"

#: Frontmatter lines rewritten by value rather than by literal text, because a
#: ported skill's adapted frontmatter and a `kiro-owned` skill's authored one
#: quote their scalars differently.
_LICENSE_LINE = re.compile(r"^(\s*)license:.*$", re.MULTILINE)
_TEMPLATE_COMMAND_LINE = re.compile(
    rf"^(\s*){TEMPLATE_COMMAND_FIELD}:.*$", re.MULTILINE
)


def _json_edit(
    path: str, edit: Callable[[Any], None]
) -> Callable[[dict[str, bytes]], None]:
    """An edit of one JSON document in the produced tree, re-serialized."""

    def apply(files: dict[str, bytes]) -> None:
        document = json.loads(files[path].decode("utf-8"))
        edit(document)
        files[path] = _json_bytes(document)

    return apply


def _text_edit(
    path: str, edit: Callable[[str], str]
) -> Callable[[dict[str, bytes]], None]:
    """An edit of one UTF-8 document in the produced tree."""

    def apply(files: dict[str, bytes]) -> None:
        files[path] = edit(files[path].decode("utf-8")).encode("utf-8")

    return apply


def _byte_edit(
    path: str, edit: Callable[[bytes], bytes]
) -> Callable[[dict[str, bytes]], None]:
    """An edit of one file's bytes, for a file nothing parses."""

    def apply(files: dict[str, bytes]) -> None:
        files[path] = edit(files[path])

    return apply


def _dropped(path: str) -> Callable[[dict[str, bytes]], None]:
    """Remove one file from the produced tree."""

    def apply(files: dict[str, bytes]) -> None:
        del files[path]

    return apply


def _hook_command_edit(
    path: str, edit: Callable[[str], str]
) -> Callable[[dict[str, bytes]], None]:
    """An edit of the first Hook_Command_String in one hook definition."""

    def rewrite(document: Any) -> None:
        action = document["hooks"][0]["action"]
        action["command"] = edit(action["command"])

    return _json_edit(path, rewrite)


def _with_blank_license(text: str) -> str:
    return _LICENSE_LINE.sub(r'\g<1>license: ""', text, count=1)


def _with_absent_template_command(text: str) -> str:
    return _TEMPLATE_COMMAND_LINE.sub(
        rf'\g<1>{TEMPLATE_COMMAND_FIELD}: "{_ABSENT_TEMPLATE_COMMAND}"', text, count=1
    )


def _discounting_the_honored_invariant(document: dict[str, Any]) -> None:
    """Put `INV-052` in the Invariant_Discount_Register, which forbids it."""
    document[DISCOUNT_REGISTER_KEY] = [
        {
            DISCOUNT_INVARIANT_FIELD: GATE_HONORED_INVARIANT,
            DISCOUNT_CONFLICTS_FIELD: "Kiro's single-command-string hook schema",
            DISCOUNT_RESOLUTION_FIELD: "discounted rather than honored",
        }
    ]


def _misdeclaring_the_progression(document: dict[str, Any]) -> None:
    """Reverse the progression phases, so neither endpoint is the declared one."""
    document[PROGRESSION_SECTION] = list(reversed(document[PROGRESSION_SECTION]))


@dataclass(frozen=True)
class _Defect:
    """One seeded defect, and what the report owes it.

    `code`, `rule_key`, `rule`, and `target` together are the finding a
    Maintainer has to be able to act on: the catalog code, the detail naming the
    violated rule, and the offending file *(R13 AC4)*. `edit` changes the
    produced tree; `contract_edit` changes the contract instead, for the two
    checks whose subject lives there. `stale` names a path whose Build_Manifest
    hash must be left as it was, which is how the one defect that is *about*
    hashes survives `_remanifest`.
    """

    code: str
    rule_key: str
    rule: Any
    target: str | None = None
    edit: Callable[[dict[str, bytes]], None] | None = None
    contract_edit: Callable[[dict[str, Any]], None] | None = None
    stale: tuple[str, ...] = ()


#: One defect per declared check, keyed by the check that owes the verdict and
#: ordered as the report is. Keeping the key *equal* to the check id is what lets
#: the test assert the catalog covers the declared set rather than a subset of it.
_DEFECTS: Mapping[str, _Defect] = {
    "plugin-schema": _Defect(
        code=E_SCHEMA_INVALID,
        rule_key="rule",
        rule="type",
        target=PLUGIN_MANIFEST,
        edit=_json_edit(
            PLUGIN_MANIFEST,
            lambda document: document.update(
                {_PLUGIN_KEYWORDS_FIELD: _KEYWORDS_NOT_AN_ARRAY}
            ),
        ),
    ),
    "mcp-schema": _Defect(
        code=E_MCP_INVALID,
        rule_key="declared",
        rule=_INSECURE_MCP_URL,
        target=MCP_MANIFEST,
        edit=_json_edit(
            MCP_MANIFEST,
            lambda document: document[MCP_SERVERS_FIELD][SENZING_SERVER_KEY].update(
                {"url": _INSECURE_MCP_URL}
            ),
        ),
    ),
    "skill-frontmatter": _Defect(
        code=E_FRONTMATTER_INVALID,
        rule_key="rule",
        rule="license-non-blank",
        target=_FRONTMATTER_DEFECT_TARGET,
        edit=_text_edit(_FRONTMATTER_DEFECT_TARGET, _with_blank_license),
    ),
    "cross-references": _Defect(
        code=E_UNRESOLVED_REFERENCE,
        rule_key="kind",
        rule=REFERENCE_ABSENT,
        target=_REFERENCE_DEFECT_TARGET,
        edit=_text_edit(_REFERENCE_DEFECT_TARGET, lambda text: text + _DANGLING_LINK),
    ),
    "version-match": _Defect(
        code=E_VERSION_MISMATCH,
        rule_key="compared",
        rule=list(VERSION_COMPARISONS[0]),
        target=PLUGIN_MANIFEST,
        edit=_json_edit(
            PLUGIN_MANIFEST,
            lambda document: document.update({_VERSION_FIELD: _UNMATCHED_VERSION}),
        ),
    ),
    "residual-claude-refs": _Defect(
        code=W_RESIDUAL_CLAUDE_REF,
        rule_key="kind",
        rule=RESIDUAL_SUBSCRIPTION_PLAN,
        target=_PORTED_OVERVIEW,
        edit=_text_edit(
            _PORTED_OVERVIEW,
            lambda text: f"{text}\nRun this on the {_RESIDUAL_PLAN_REFERENCE}.\n",
        ),
    ),
    "invariant-discounts": _Defect(
        code=E_HONORED_INVARIANT_DISCOUNTED,
        rule_key="kind",
        rule=DISCOUNT_HONORED_INVARIANT,
        contract_edit=_discounting_the_honored_invariant,
    ),
    "hook-command-strings": _Defect(
        code=E_SHELL_CONSTRUCT_IN_HOOK,
        rule_key="construct",
        rule=_SHELL_CONSTRUCT,
        target=_SHELL_DEFECT_HOOK,
        edit=_hook_command_edit(
            _SHELL_DEFECT_HOOK, lambda command: command + _APPENDED_SHELL_TAIL
        ),
    ),
    "manifest-hashes": _Defect(
        code=E_HASH_MISMATCH,
        rule_key="kind",
        rule=DRIFT_CONTENT,
        target=_HASH_DRIFT_TARGET,
        edit=_byte_edit(_HASH_DRIFT_TARGET, lambda data: data + b"\n"),
        stale=(_HASH_DRIFT_TARGET,),
    ),
    "skill-inventory": _Defect(
        code=E_INVENTORY_MISMATCH,
        rule_key="kind",
        rule=INVENTORY_COMMAND_STALE,
        target=_INVENTORY_DEFECT_TARGET,
        edit=_text_edit(_INVENTORY_DEFECT_TARGET, _with_absent_template_command),
    ),
    "progression-order": _Defect(
        code=E_PROGRESSION_MISMATCH,
        rule_key="kind",
        rule=PROGRESSION_PHASES_MISDECLARED,
        contract_edit=_misdeclaring_the_progression,
    ),
    "script-imports": _Defect(
        code=E_BROKEN_IMPORT,
        rule_key="kind",
        rule=IMPORT_UNPORTED,
        target=_IMPORT_DEFECT_TARGET,
        edit=_dropped(_DROPPED_MODULE),
    ),
    "script-references": _Defect(
        code=E_MISSING_ASSET,
        rule_key="kind",
        rule=ASSET_HOOK_SCRIPT,
        target=_MISSING_SCRIPT_HOOK,
        edit=_hook_command_edit(
            _MISSING_SCRIPT_HOOK,
            lambda command: command.replace(
                _MISSING_SCRIPT_NAME, _ABSENT_HOOK_SCRIPT
            ),
        ),
    ),
}

_DEFECT_IDS = tuple(_DEFECTS)

#: Every base-Power path a defect reads or writes. Asserted present, so a
#: renamed produced file fails as a missing fixture rather than as a defect that
#: quietly stopped being seeded.
_DEFECT_PATHS = (
    MANIFEST_FILENAME,
    PLUGIN_MANIFEST,
    MCP_MANIFEST,
    _HASH_DRIFT_TARGET,
    _PORTED_OVERVIEW,
    _LINKED_DOCUMENT,
    _FRONTMATTER_DEFECT_TARGET,
    _REFERENCE_DEFECT_TARGET,
    _INVENTORY_DEFECT_TARGET,
    _IMPORT_DEFECT_TARGET,
    _DROPPED_MODULE,
    _SHELL_DEFECT_HOOK,
    _MISSING_SCRIPT_HOOK,
)


def _remanifest(files: dict[str, bytes], stale: frozenset[str]) -> None:
    """Re-record the Build_Manifest over the seeded tree.

    Editing a file changes its hash, and twelve of the thirteen checks are
    indifferent to that while `manifest-hashes` is not. Rehashing here keeps that
    check's verdict a function of the defect that is about hashes: the path a
    defect deliberately leaves stale keeps its old hash, and a path a defect
    deleted loses its record rather than reading as absent *(R16 AC9)*.
    """
    document = json.loads(files[MANIFEST_FILENAME].decode("utf-8"))
    recorded = []
    for row in document["files"]:
        path = row["path"]
        if path not in files:
            continue
        if path not in stale:
            row["sha256"] = sha256_hex(files[path])
        recorded.append(row)
    document["files"] = recorded
    files[MANIFEST_FILENAME] = _json_bytes(document)


@lru_cache(maxsize=None)
def _contract_variant(names: tuple[str, ...]) -> Contract:
    """`contract.yaml` with the named defects' edits applied, loaded from a copy.

    Written out and read back rather than constructed in memory, so the sections
    the gate reads are ones that survived a YAML round trip — the shape a
    hand-edited contract reaches it in. `contract.yaml` itself is never touched.
    """
    document = deepcopy(dict(_base_power().contract.raw))
    for name in names:
        edit = _DEFECTS[name].contract_edit
        assert edit is not None, name
        edit(document)
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "contract.yaml"
        path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=10**6),
            encoding="utf-8",
        )
        return load_contract(path)


def _seeded_report(names: tuple[str, ...]) -> tuple[ValidationReport, bool]:
    """Validate the base Power with the named defects seeded into it."""
    base = _base_power()
    files = dict(base.power)
    stale: set[str] = set()
    contract_edits: list[str] = []
    for name in names:
        defect = _DEFECTS[name]
        if defect.edit is not None:
            defect.edit(files)
        if defect.contract_edit is not None:
            contract_edits.append(name)
        stale.update(defect.stale)
    _remanifest(files, frozenset(stale))
    contract = base.contract
    if contract_edits:
        # Sorted, so the same pair of contract defects in either drawn order is
        # one cached variant; the two edits touch different sections, so applying
        # them in either order builds the same document.
        contract = _contract_variant(tuple(sorted(contract_edits)))
    return _validated(files, contract, base.release)


def _footprint(report: ValidationReport) -> tuple[tuple[Any, ...], ...]:
    """Every finding as (check id, code, target, location), in report order."""
    return tuple(
        (check.id, finding.code, finding.target, finding.location)
        for check in report.checks
        for finding in check.findings
    )


@lru_cache(maxsize=None)
def _isolated(name: str) -> tuple[tuple[Any, ...], ...]:
    """The footprint one defect leaves when it is the only one seeded."""
    report, _ = _seeded_report((name,))
    return _footprint(report)


def _recorded_ids(report: ValidationReport) -> tuple[str, ...]:
    """The check ids the report records, in first-occurrence order."""
    seen: dict[str, None] = {}
    for check in report.checks:
        seen.setdefault(check.id, None)
    return tuple(seen)


def _assert_record_is_complete(
    report: ValidationReport, skill_manifests: Sequence[str]
) -> None:
    """Every produced file the requirements name has exactly one result.

    Asserted over a passing report and a defective one alike, because R13's
    "SHALL record a pass or fail result" is owed unconditionally: a report that
    thinned its record when something went wrong would be a report a Maintainer
    could not read the remaining work out of.
    """
    assert _recorded_ids(report) == check_order()
    for check in report.checks:
        assert check.result in (RESULT_PASS, RESULT_WARN, RESULT_FAIL)
        assert check.passed is (check.result == RESULT_PASS)

    # R13 AC1, AC2: one recorded pass-or-fail result for each manifest, naming it.
    for check_id, manifest in (
        ("plugin-schema", PLUGIN_MANIFEST),
        ("mcp-schema", MCP_MANIFEST),
    ):
        results = report.results_for(check_id)
        assert len(results) == 1
        assert results[0].target == manifest
        assert results[0].result in (RESULT_PASS, RESULT_FAIL)

    # R13 AC3: one per `SKILL.md`, one for every `SKILL.md`, in tree order.
    frontmatter = report.results_for("skill-frontmatter")
    assert tuple(result.target for result in frontmatter) == tuple(skill_manifests)
    for result in frontmatter:
        assert result.result in (RESULT_PASS, RESULT_FAIL)

    # Every other declared check records exactly one result, so the report's
    # length is the declared set plus one row per skill rather than a coincidence.
    for check_id in check_order():
        if check_id != "skill-frontmatter":
            assert len(report.results_for(check_id)) == 1, check_id
    assert len(report.checks) == len(check_order()) - 1 + len(skill_manifests)

    # The serialized artifact carries the same record and the same verdict.
    payload = report.to_json()
    assert payload["reportVersion"] == REPORT_VERSION
    assert payload["templateRelease"] == _RESOLVED_TAG
    assert len(payload["checks"]) == len(report.checks)
    assert payload["status"] == report.status
    assert payload["tagAllowed"] is report.tag_allowed
    assert [row["id"] for row in payload["checks"]] == [
        check.id for check in report.checks
    ]


# Feature: senzing-bootcamp-power, Property 15: The validation report is complete
# and gates tagging biconditionally
#
# Validates: Requirements 4.2, 13.1, 13.2, 13.4, 13.5
@settings(max_examples=100)
@given(st.lists(st.sampled_from(_DEFECT_IDS), unique=True))
def test_the_validation_report_is_complete_and_gates_tagging(
    seeded: list[str],
) -> None:
    base = _base_power()
    order = check_order()
    names = tuple(seeded)

    # The catalog owes a defect to every check the design declares, so "across
    # all implemented checks" is asserted rather than claimed: a fourteenth check
    # fails here until it has one too.
    assert order == DECLARED_CHECKS
    assert tuple(_DEFECTS) == DECLARED_CHECKS

    # Non-vacuous by construction: the base Power passes. That is what makes the
    # gate's true side reachable and every finding below attributable to a seed.
    assert base.report.status == STATUS_PASSED
    assert base.report.tag_allowed is True
    assert base.report.findings == ()
    assert base.unchanged
    assert base.skill_manifests == PowerTree.from_mapping(base.power).skill_md_paths()
    assert len(base.skill_manifests) > len(_PORTED_SKILLS)
    for path in _DEFECT_PATHS:
        assert path in base.power, path

    # R4 AC2, R13 AC1, AC2: the two manifests, and the schemas they answer to.
    for check_id, manifest, schema, code in (
        ("plugin-schema", PLUGIN_MANIFEST, PLUGIN_SCHEMA_ID, E_SCHEMA_INVALID),
        ("mcp-schema", MCP_MANIFEST, MCP_SCHEMA_ID, E_MCP_INVALID),
    ):
        registered = registered_check(check_id)
        assert registered is not None
        assert registered.target == manifest
        assert registered.code == code
        assert MANIFEST_SCHEMAS[manifest] == schema

    report, unchanged = _seeded_report(names)

    # --- Clause 1: one recorded result per produced file, defective or not ---
    for candidate in (base.report, report):
        _assert_record_is_complete(candidate, base.skill_manifests)

    # --- Clause 2: all k defects reported, not a prefix of them -------------
    footprints = {name: _isolated(name) for name in names}
    for name in names:
        defect = _DEFECTS[name]

        # Independence, asserted: measured alone, a defect's findings all belong
        # to the check that owes it. Without this the additivity below would be
        # arithmetic over overlapping sets.
        assert footprints[name] != (), name
        assert {row[0] for row in footprints[name]} == {name}, name

        # R13 AC4: the offending file and the violated rule, by name.
        reported = tuple(
            finding
            for check in report.checks
            if check.id == name
            for finding in check.findings
            if finding.code == defect.code
            and finding.target == defect.target
            and finding.details.get(defect.rule_key) == defect.rule
        )
        assert reported != (), name
        for finding in reported:
            assert finding.severity == (
                SEVERITY_WARNING
                if defect.code.startswith("W_")
                else SEVERITY_ERROR
            ), name
            if defect.target is not None:
                assert defect.target in finding.message, name
            payload = finding.to_json()
            assert payload["code"] == defect.code
            assert payload[defect.rule_key] == defect.rule
            assert payload.get("target") == defect.target
        assert any(not result.passed for result in report.results_for(name)), name

    # Exactly the seeded checks are not passing, in report order: a run that
    # returned after the first failure would name a prefix of this.
    assert report.failed_check_ids() == tuple(
        name for name in order if name in footprints
    )
    # And the whole finding sequence is the concatenation of what each defect
    # produces alone — nothing dropped, nothing invented.
    assert _footprint(report) == tuple(
        row for name in order if name in footprints for row in footprints[name]
    )
    assert len(report.findings) == sum(len(footprints[name]) for name in names)

    # R13 AC3 again, now per file: the one `SKILL.md` result that fails is the
    # one whose file was seeded, and the other n-1 still pass.
    assert tuple(
        result.target
        for result in report.results_for("skill-frontmatter")
        if not result.passed
    ) == (
        (_DEFECTS["skill-frontmatter"].target,)
        if "skill-frontmatter" in footprints
        else ()
    )

    # --- Clause 3: the gate is one statement, and it follows the evidence ---
    errors = tuple(
        finding for finding in report.findings if finding.severity == SEVERITY_ERROR
    )
    warnings = tuple(
        finding for finding in report.findings if finding.severity == SEVERITY_WARNING
    )
    assert len(errors) + len(warnings) == len(report.findings)

    # R13 AC4, AC5: four spellings of one biconditional, and then the input.
    assert report.tag_allowed is (report.status == STATUS_PASSED)
    assert report.tag_allowed is all(check.passed for check in report.checks)
    assert report.tag_allowed is (report.findings == ())
    assert report.tag_allowed is (names == ())

    # The three-valued fold behind it (R12 AC4): an error fails the run, a
    # warning alone downgrades it, and both withhold permission to tag.
    assert fold_status(report.checks) == report.status
    if names == ():
        assert report.status == STATUS_PASSED
    elif errors:
        assert report.status == STATUS_FAILED
    else:
        assert warnings != () and report.status == STATUS_INCOMPLETE

    # R13 AC4: validating reads the produced Power; it never writes to it.
    assert unchanged

# ===========================================================================
# Property 16: Skill and command inventories are bijections with the template
# ===========================================================================
#
# **No inventory count appears anywhere in this section**, and that omission is
# the property. The design's defect D1 records why: R7 AC1 once fixed the
# inventory at "eight modules ... 11 skills", release `0.5.1` carries nine
# modules and twelve skills, and a gate asserting a number would have been
# testing the wrong thing on the next release too. What R7 AC1 and AC2 ask for
# instead is a **correspondence** — one ported skill per template skill
# directory, and no ported skill without one — so both inventories are derived,
# one from the resolved release and one from the produced Power, and what is
# asserted is that they line up. Every template inventory below is whatever the
# drawn trees carry, and every claim about it is stated over that set.
#
# Three claims, and the third is not a name comparison
# ----------------------------------------------------
# * **R7 AC1, AC2** — exactly one produced skill stands for each template skill
#   directory, and none stands for a directory the release does not carry.
# * **R7 AC2's residue rule** — every remaining skill in the Power is declared
#   `kiro-owned` by the contract. The three command-derived skills answer to R9
#   and the client-adaptation skills to the hook-parity criteria, and both groups
#   are compliant *because* the contract declares them, not because the gate
#   overlooks them. That is what closes the inventory: a skill is a port, a
#   command stand-in, or an explicit declaration, and there is no fourth way for
#   one to exist.
# * **R9 AC1** — the command-derived skills are one-to-one with the template
#   commands. This one *cannot* be a set comparison, because the names differ by
#   design: the template command `graduate` is represented by the skill
#   `graduate-bootcamp`. The correspondence is declared per skill, and
#   one-to-one is a property of the declaration. The contrast is asserted
#   outright below — the two name sets are *unequal* on a compliant Power, and
#   the compliant Power reports nothing — so a gate that had compared names
#   would fail here rather than agree with itself.
#
# What stands for what is read off the artifacts
# ----------------------------------------------
# A produced skill declares its counterpart in its own frontmatter:
# `metadata.templateSkill` names the source skill directory it was ported from,
# `metadata.templateCommand` the template command it replaces. A skill that
# declares neither and whose directory name the release carries claims that
# directory by its path, which is the placement R8 AC1 fixes; the compliant
# construction below alternates between the two so both claim paths are
# exercised in every example, and the field names are asserted equal to the
# engine's own constants because the writer and the gate must rename together or
# not at all.
#
# Exactly the violating set, from two independent oracles
# ------------------------------------------------------
# Nine ways the correspondence can fail, and the gate owes all of them at once —
# a build that lost one skill and gained two undeclared ones is three findings,
# not the first one found. So each kind is seeded alone, and then all nine are
# seeded together, and the reported set of `(kind, target)` pairs is compared
# against that set computed twice, independently:
#
# * `_seeded_power` returns the pairs its own *construction* owes, read off the
#   seed labels and the role names it assigned — it never looks at a finding, a
#   declaration, or a message;
# * `_reference_correspondence_failures` reads the declarations back off the
#   produced inventory and applies R7 AC1, AC2, R8 AC1, and R9 AC1 as spelled
#   here, over this section's own literals.
#
# Their equality is the biconditional, and `len(findings)` is asserted against
# the size of that set, so a report carrying a prefix of the truth — or one
# finding twice — fails. Two of the seeds owe two pairs rather than one, and
# deliberately: a second directory standing for one template skill is *both* a
# duplicate port and a declaration that does not match its directory, and saying
# so is more honest than choosing a seed that hides one of them.
#
# Fail closed, three ways
# -----------------------
# The check measures the Power against the release it was built from and against
# the contract that declares what is Kiro's, so it cannot reach a verdict
# without either: a run launched with no `--source` and a run with no contract
# both **block the tag** rather than passing a check they never performed. The
# third condition matters as much: a release tree carrying no `skills/`
# directory would make every produced skill unaccounted for and, worse, would
# let a Power with no skills at all pass a bijection against nothing. All three
# are asserted at the check and at the runner, because raising is only half of
# failing closed — the recorded result has to be a fail.
#
# Deliberately out of scope: the *order* the ported skills are presented in is
# Property 17's, each skill's frontmatter is Property 13's, and whether a
# hostile release path can reach the gate at all is Property 7's — the engine
# halts such a tree long before validation, which is why `_drawn_skill_names`
# leaves a `..` segment out of the template inventory rather than inventing a
# produced skill for it.

#: The check this property drives, and the two roots the correspondence spans.
_INVENTORY_CHECK_ID = "skill-inventory"
_SKILLS_ROOT = "skills"
_COMMANDS_ROOT = "commands"
_COMMAND_SUFFIX = ".md"

#: Where a produced skill records its counterpart, spelled as the requirements
#: spell it and asserted equal to the engine's and the gate's own constants.
_METADATA_FIELD = "metadata"
_TEMPLATE_SKILL_KEY = "templateSkill"
_TEMPLATE_COMMAND_KEY = "templateCommand"

#: Three template commands, each with the skill that represents it.
#: `graduate` → `graduate-bootcamp` is the pair that makes the correspondence a
#: declaration rather than a name comparison.
#:
#: THREE, AND A SUBSET OF THE AUTHORED COMMAND SKILLS RATHER THAN ALL OF THEM. This
#: property seeds exactly three command failure modes — unrepresented, claimed
#: twice, and claiming both a skill and a command — and each needs one command of
#: its own, so three is a property of the seed set and not of the release. The
#: release's actual command set is derived elsewhere (`COMMAND_DERIVED_SKILLS`,
#: itself read off the authored skills), and a release that adds a command must not
#: have to add a fourth failure mode here to keep this property meaningful.
_COMMAND_SKILLS: Mapping[str, str] = {
    "start-bootcamp": "start-bootcamp",
    "graduate": "graduate-bootcamp",
    "bootcamp-feedback": "bootcamp-feedback",
}

#: Template skill directory names the seed roles fall back on when the drawn
#: trees supply fewer than the four the fully-seeded case needs. Shapes
#: `_skill_dir_name()` cannot draw, and asserted disjoint from what it drew.
_EXTRA_TEMPLATE_NAMES = (
    "template-only-alpha",
    "template-only-beta",
    "template-only-gamma",
    "template-only-delta",
)

#: The four template skill directories the seeds need to treat differently.
_ROLE_UNPORTED = "unported"
_ROLE_PORTED_TWICE = "ported twice"
_ROLE_RELOCATED = "ported elsewhere"
_ROLE_DOUBLE_CLAIM = "claimed twice over"
_SEED_ROLES = (
    _ROLE_UNPORTED,
    _ROLE_PORTED_TWICE,
    _ROLE_RELOCATED,
    _ROLE_DOUBLE_CLAIM,
)

#: A skill directory a later release adds. Not a name `_skill_dir_name()` draws
#: — the generator stops at `module-07` — so a release inventory can be grown by
#: one and shrunk by one below without colliding with what was drawn.
_UPSTREAM_ADDITION = "module-08-added-upstream"

#: Produced skill directories that exist only to carry a seeded defect, and a
#: command name the release does not declare. None is a name `_skill_dir_name()`
#: can draw or the contract declares, both asserted below.
_SECOND_PORT_DIR = "second-port-of-one-template-skill"
_RELOCATED_PORT_DIR = "port-under-another-name"
_STALE_PORT_DIR = "port-of-a-retired-skill"
_UNACCOUNTED_DIR = "skill-nothing-declares"
_SECOND_COMMAND_DIR = "second-skill-for-one-command"
_STALE_COMMAND_DIR = "skill-for-a-retired-command"
_ABSENT_COMMAND = "retired-command"

#: One seeded defect each, labeled by the kind its construction owes.
_SEED_UNPORTED = "a template skill nothing ported"
_SEED_PORTED_TWICE = "two skills for one template skill"
_SEED_RELOCATED = "a port under another directory name"
_SEED_STALE_SKILL = "a port of a skill the release dropped"
_SEED_UNACCOUNTED = "a skill with no counterpart and no declaration"
_SEED_DOUBLE_CLAIM = "a skill claiming a skill and a command"
_SEED_COMMAND_UNREPRESENTED = "a template command no skill represents"
_SEED_COMMAND_TWICE = "two skills for one template command"
_SEED_COMMAND_STALE = "a stand-in for a command the release dropped"

_SEED_LABELS = (
    _SEED_UNPORTED,
    _SEED_PORTED_TWICE,
    _SEED_RELOCATED,
    _SEED_STALE_SKILL,
    _SEED_UNACCOUNTED,
    _SEED_DOUBLE_CLAIM,
    _SEED_COMMAND_UNREPRESENTED,
    _SEED_COMMAND_TWICE,
    _SEED_COMMAND_STALE,
)

#: Which template command each seed takes over. Independent of one another, so
#: the fully-seeded case applies all three at once.
_UNREPRESENTED_COMMAND = "bootcamp-feedback"
_DUPLICATED_COMMAND = "start-bootcamp"
_DOUBLE_CLAIMED_COMMAND = "graduate"

#: A license every produced skill declares, so the documents the inventory is
#: read out of are the documents Property 13 would accept.
_SKILL_LICENSE = "Apache-2.0"

#: A passing result from another check, so a withheld tag below can only have
#: come from `skill-inventory`.
_PASSING_INVENTORY_SIBLING = CheckResult(
    id="plugin-schema", target=PLUGIN_MANIFEST
)


def _skill_directory(name: str) -> str:
    """The Power path a skill occupies, as a finding names it."""
    return f"{_SKILLS_ROOT}/{name}/"


def _skill_entry_point(name: str) -> str:
    """The produced skill's entry point, where its declaration is written."""
    return f"{_skill_directory(name)}{SKILL_MANIFEST}"


def _command_document(command: str) -> str:
    """The release-relative path of one template command document."""
    return f"{_COMMANDS_ROOT}/{command}{_COMMAND_SUFFIX}"


def _drawn_skill_names(paths: Iterable[str]) -> tuple[str, ...]:
    """The skill directory names a drawn tree carries, read off its paths.

    R7 AC1 counts *directories*, so a name is the first segment below `skills/`.
    A segment that is not a directory name — the `..` that
    `template_tree()`'s `skills/../../escape.md` case yields — is left out: the
    engine halts such a tree with `E_UNMATCHED_FILE` or a containment refusal
    long before validation *(Properties 5 and 7)*, so the inventory gate is
    never asked about one.
    """
    base = f"{_SKILLS_ROOT}/"
    names = set()
    for path in paths:
        if not path.startswith(base):
            continue
        remainder = path[len(base) :]
        if "/" not in remainder:
            continue
        head = remainder.split("/", 1)[0]
        if head and head not in (".", ".."):
            names.add(head)
    return tuple(sorted(names))


def _produced_document(
    directory: str,
    *,
    template_skill: str | None = None,
    template_command: str | None = None,
) -> str:
    """One produced `SKILL.md`, declaring the counterpart it is given.

    The frontmatter is rendered by Property 13's `_skill_document`, so what
    counts as a readable declaration is spelled once for both properties. A
    skill given neither counterpart declares no `metadata` at all, which is the
    shape whose claim rests on its path instead *(R8 AC1)*.
    """
    metadata: dict[str, str] = {}
    if template_skill is not None:
        metadata[_TEMPLATE_SKILL_KEY] = template_skill
    if template_command is not None:
        metadata[_TEMPLATE_COMMAND_KEY] = template_command

    phrase = TRIGGER_PHRASES.get(directory)
    described = f"Work through {directory}."
    if phrase is not None:
        described += f' Use when the user says "{phrase}".'
    fields: dict[str, Any] = {
        "name": directory,
        "description": described,
        "license": _SKILL_LICENSE,
    }
    if metadata:
        fields[_METADATA_FIELD] = metadata
    return _skill_document(fields)


def _release_tree(
    template_skills: Sequence[str], template_commands: Sequence[str], prefix: str
) -> PowerTree:
    """A resolved release tree carrying those skill directories and commands.

    `prefix` is how `--source` was given: `""` for the plugin root itself,
    `plugins/senzing-bootcamp/` for the marketplace repository root the release
    tarball actually unpacks to. Both are exercised, and the derived inventory
    must not depend on which one a Maintainer handed the validator.
    """
    files = {
        f"{prefix}{_skill_entry_point(name)}": f"# {name}\n"
        for name in template_skills
    }
    files.update(
        {
            f"{prefix}{_command_document(command)}": f"# /{command}\n"
            for command in template_commands
        }
    )
    return PowerTree.from_mapping(files)


def _seed_roles(template_skills: Sequence[str]) -> Mapping[str, str]:
    """Assign each seed role a template skill directory of its own.

    Four roles need four distinct directories — one unported, one ported twice,
    one ported under another name, and one claiming a command as well — and they
    have to be distinct because the seeds contradict each other on any name they
    shared. Drawn names take the roles first, so the seeded defects range over
    whatever the generators produce, `module-03b` shapes included.

    Only a seeded construction needs roles; a compliant one is built over any
    inventory at all, which is what lets the clauses below grow and shrink the
    release by one and still expect a pass.
    """
    assert len(template_skills) >= len(_SEED_ROLES)
    return dict(zip(_SEED_ROLES, template_skills))


def _seeded_power(
    template_skills: Sequence[str], seeds: frozenset[str]
) -> tuple[dict[str, str], frozenset[tuple[str, str]]]:
    """A produced Power, and the `(kind, target)` pairs its construction owes.

    The compliant Power is the whole bijection: one skill per template skill
    directory — half declaring their counterpart, half resting on their path —
    and one skill per template command, declaring the command it represents.
    Each seed then perturbs exactly one correspondence and states what that owes,
    read off the labels and the role assignment rather than off any value, which
    is what makes this oracle independent of `_reference_correspondence_failures`.
    """
    roles = _seed_roles(template_skills) if seeds else {}
    documents: dict[str, str] = {}
    owed: set[tuple[str, str]] = set()

    for index, name in enumerate(template_skills):
        if _SEED_UNPORTED in seeds and name == roles[_ROLE_UNPORTED]:
            # R7 AC1: the release carries it and nothing in the Power stands for
            # it — the shape an upstream module silently lost by a build takes.
            owed.add((INVENTORY_MISSING, _skill_directory(name)))
            continue
        if _SEED_RELOCATED in seeds and name == roles[_ROLE_RELOCATED]:
            # R8 AC1: the only skill standing for it sits under another name, so
            # the correspondence holds and the placement does not.
            documents[_skill_entry_point(_RELOCATED_PORT_DIR)] = _produced_document(
                _RELOCATED_PORT_DIR, template_skill=name
            )
            owed.add(
                (INVENTORY_RELOCATED, _skill_entry_point(_RELOCATED_PORT_DIR))
            )
            continue
        if _SEED_DOUBLE_CLAIM in seeds and name == roles[_ROLE_DOUBLE_CLAIM]:
            # Both counterparts declared by one skill. Its command's own
            # stand-in is not produced below, so the two correspondences stay
            # one-to-one and the double claim is the only thing wrong.
            documents[_skill_entry_point(name)] = _produced_document(
                name,
                template_skill=name,
                template_command=_DOUBLE_CLAIMED_COMMAND,
            )
            owed.add((INVENTORY_DOUBLE_CLAIM, _skill_entry_point(name)))
            continue
        # Compliant, by whichever of the two claim paths the index selects.
        documents[_skill_entry_point(name)] = _produced_document(
            name, template_skill=name if index % 2 == 0 else None
        )

    if _SEED_PORTED_TWICE in seeds:
        # Two pairs, and honestly so: a second directory standing for one
        # template skill is a duplicate port *and* a declaration that is not its
        # own directory name. A seed that owed only one would have to hide one.
        claimed = roles[_ROLE_PORTED_TWICE]
        documents[_skill_entry_point(_SECOND_PORT_DIR)] = _produced_document(
            _SECOND_PORT_DIR, template_skill=claimed
        )
        owed.add((INVENTORY_DUPLICATE, _skill_directory(claimed)))
        owed.add((INVENTORY_RELOCATED, _skill_entry_point(_SECOND_PORT_DIR)))

    if _SEED_STALE_SKILL in seeds:
        # An upstream rename, from the Power's side: the declaration names a
        # directory the resolved release no longer carries.
        documents[_skill_entry_point(_STALE_PORT_DIR)] = _produced_document(
            _STALE_PORT_DIR, template_skill=_STALE_PORT_DIR
        )
        owed.add((INVENTORY_STALE, _skill_entry_point(_STALE_PORT_DIR)))

    if _SEED_UNACCOUNTED in seeds:
        # R7 AC2's residue rule: no counterpart, no command, no declaration.
        documents[_skill_entry_point(_UNACCOUNTED_DIR)] = _produced_document(
            _UNACCOUNTED_DIR
        )
        owed.add((INVENTORY_UNACCOUNTED, _skill_directory(_UNACCOUNTED_DIR)))

    for command, skill in _COMMAND_SKILLS.items():
        if _SEED_COMMAND_UNREPRESENTED in seeds and command == _UNREPRESENTED_COMMAND:
            # R9 AC1: the release declares the command and nothing represents it.
            owed.add((INVENTORY_COMMAND_MISSING, _command_document(command)))
            continue
        if _SEED_DOUBLE_CLAIM in seeds and command == _DOUBLE_CLAIMED_COMMAND:
            continue
        documents[_skill_entry_point(skill)] = _produced_document(
            skill, template_command=command
        )

    if _SEED_COMMAND_TWICE in seeds:
        documents[_skill_entry_point(_SECOND_COMMAND_DIR)] = _produced_document(
            _SECOND_COMMAND_DIR, template_command=_DUPLICATED_COMMAND
        )
        claimants = sorted(
            (_SECOND_COMMAND_DIR, _COMMAND_SKILLS[_DUPLICATED_COMMAND])
        )
        owed.add((INVENTORY_COMMAND_DUPLICATE, _skill_directory(claimants[0])))

    if _SEED_COMMAND_STALE in seeds:
        documents[_skill_entry_point(_STALE_COMMAND_DIR)] = _produced_document(
            _STALE_COMMAND_DIR, template_command=_ABSENT_COMMAND
        )
        owed.add(
            (INVENTORY_COMMAND_STALE, _skill_entry_point(_STALE_COMMAND_DIR))
        )

    return documents, frozenset(owed)


def _reference_correspondence_failures(
    inventory: Sequence[SkillProvenance],
    template_skills: Sequence[str],
    template_commands: Sequence[str],
    kiro_owned: Sequence[str],
) -> frozenset[tuple[str, str]]:
    """The same pairs, derived from the criteria over the declarations as read.

    Written from R7 AC1, R7 AC2, R8 AC1, and R9 AC1 against this section's own
    literals, and it never asks the validator what it expected. A produced skill
    claims a template skill directory by declaring it, or — declaring nothing at
    all — by sitting at it, which is the placement R8 AC1 fixes.
    """
    release = set(template_skills)
    declared_commands = set(template_commands)
    owned = set(kiro_owned)

    claims: dict[str, str] = {}
    for skill in inventory:
        if skill.template_skill is not None:
            claims[skill.name] = skill.template_skill
        elif skill.template_command is None and skill.name in release:
            claims[skill.name] = skill.name
    commands = {
        skill.name: skill.template_command
        for skill in inventory
        if skill.template_command is not None
    }

    violations: set[tuple[str, str]] = set()

    # R7 AC1 — exactly one produced skill per template skill directory.
    for name in template_skills:
        standing = sorted(
            skill for skill, claimed in claims.items() if claimed == name
        )
        if not standing:
            violations.add((INVENTORY_MISSING, _skill_directory(name)))
        elif len(standing) > 1:
            violations.add((INVENTORY_DUPLICATE, _skill_directory(name)))

    for skill in inventory:
        claimed = claims.get(skill.name)
        if skill.template_skill is not None and skill.template_command is not None:
            violations.add((INVENTORY_DOUBLE_CLAIM, skill.path))
        if claimed is not None and claimed not in release:
            violations.add((INVENTORY_STALE, skill.path))
        if skill.template_skill is not None and skill.template_skill != skill.name:
            # R8 AC1 — the destination keeps the source directory name.
            violations.add((INVENTORY_RELOCATED, skill.path))
        if claimed is None and skill.name not in commands and skill.name not in owned:
            # R7 AC2 — a port, a command stand-in, or a declaration. Nothing else.
            violations.add((INVENTORY_UNACCOUNTED, _skill_directory(skill.name)))

    # R9 AC1 — one skill per template command, and no stand-in for a command the
    # release does not declare.
    for command in template_commands:
        standing = sorted(
            skill for skill, claimed in commands.items() if claimed == command
        )
        if not standing:
            violations.add((INVENTORY_COMMAND_MISSING, _command_document(command)))
        elif len(standing) > 1:
            violations.add(
                (INVENTORY_COMMAND_DUPLICATE, _skill_directory(standing[0]))
            )
    for name, command in commands.items():
        if command not in declared_commands:
            violations.add((INVENTORY_COMMAND_STALE, _skill_entry_point(name)))

    return frozenset(violations)


def _assert_finding_names_the_violation(finding: Finding) -> tuple[str, str]:
    """One correspondence failure, checked to name the thing at fault.

    Returns its `(kind, target)` pair. R7 and R9 are acted on by editing a
    contract, a frontmatter declaration, or a skill directory, so a finding that
    does not spell the name at issue is not actionable — every name it carries as
    data is required in its prose too.
    """
    kind = finding.details["kind"]
    assert kind in INVENTORY_KINDS, kind
    assert finding.code == E_INVENTORY_MISMATCH
    assert finding.severity == SEVERITY_ERROR
    assert finding.target

    named: list[str] = []
    for key, value in finding.details.items():
        if key == "kind":
            continue
        named.extend(value if isinstance(value, list) else [value])
    assert named, kind
    for name in named:
        assert isinstance(name, str)
        assert name in finding.message or repr(name) in finding.message, (kind, name)

    payload = finding.to_json()
    assert payload["code"] == E_INVENTORY_MISMATCH
    assert payload["kind"] == kind
    assert payload["target"] == finding.target
    assert payload["severity"] == SEVERITY_ERROR
    return kind, finding.target


def _assert_reports_exactly(
    documents: Mapping[str, str],
    *,
    owed: frozenset[tuple[str, str]],
    template_skills: Sequence[str],
    template_commands: Sequence[str],
    kiro_owned: Sequence[str],
) -> CheckResult:
    """Measure one produced Power against one release, and check the verdict.

    Asserts the reported correspondence failures are exactly `owed` — no more, no
    fewer, and not a prefix — that the two oracles agree on that set, that every
    finding names the thing at fault, and that the recorded result and the
    release gate follow from it and nothing else.
    """
    tree = PowerTree.from_mapping(documents)
    inventory = skill_inventory(tree)

    # The inventory is the Power's skill directories, and each entry carries the
    # declaration the construction wrote — so a read fault would fail here
    # rather than turning into a correspondence failure below.
    assert skill_names(tree) == tuple(
        sorted({path.split("/")[1] for path in documents})
    )
    assert tuple(skill.name for skill in inventory) == skill_names(tree)
    for skill in inventory:
        assert isinstance(skill, SkillProvenance)
        assert skill.readable
        assert skill.path == _skill_entry_point(skill.name)
        assert skill == skill_provenance(tree, skill.name)
        declared = yaml.safe_load(
            documents[skill.path].split("---\n")[1]
        ).get(_METADATA_FIELD, {})
        assert skill.template_skill == declared.get(_TEMPLATE_SKILL_KEY)
        assert skill.template_command == declared.get(_TEMPLATE_COMMAND_KEY)
        assert skill.declares_counterpart is bool(declared)

    findings = skill_bijection_findings(
        inventory, template_skills, kiro_owned
    ) + command_bijection_findings(inventory, template_commands)

    # --- Exactly the violating set, from both oracles ----------------------
    reported = tuple(
        _assert_finding_names_the_violation(finding) for finding in findings
    )
    assert frozenset(reported) == owed
    assert (
        _reference_correspondence_failures(
            inventory, template_skills, template_commands, kiro_owned
        )
        == owed
    )
    # Not a prefix, and nothing reported twice.
    assert len(reported) == len(owed)

    # --- The recorded result, and the gate over it -------------------------
    claims = port_claims(inventory, template_skills)
    commands = command_claims(inventory)
    result = skill_inventory_result(
        inventory, template_skills, template_commands, kiro_owned
    )
    assert result.id == _INVENTORY_CHECK_ID
    assert result.findings == findings
    # Pure over the four name collections: the same inputs twice, the same
    # result, whatever a filesystem or a clock is doing.
    assert (
        skill_inventory_result(
            inventory, template_skills, template_commands, kiro_owned
        )
        == result
    )

    clean = owed == frozenset()
    assert result.result == (RESULT_PASS if clean else RESULT_FAIL)
    assert result.passed is clean
    assert result.extra["templateSkills"] == list(template_skills)
    assert result.extra["portedSkills"] == sorted(claims)
    assert result.extra["portedSkills"] == list(
        ported_skill_names(inventory, template_skills)
    )
    assert result.extra["templateCommands"] == list(template_commands)
    assert result.extra["commandDerivedSkills"] == {
        name: commands[name] for name in sorted(commands)
    }
    assert result.extra["kiroOwnedSkills"] == list(kiro_owned)
    assert result.extra["powerSkills"] == [skill.name for skill in inventory]
    assert result.extra["mismatches"] == [
        {
            "kind": finding.details["kind"],
            "target": finding.target,
            **{
                key: value
                for key, value in finding.details.items()
                if key != "kind"
            },
        }
        for finding in findings
    ]

    report = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_PASSING_INVENTORY_SIBLING, result),
    )
    assert _PASSING_INVENTORY_SIBLING.passed
    assert report.status == (STATUS_PASSED if clean else STATUS_FAILED)
    assert report.tag_allowed is clean
    assert report.findings_for(E_INVENTORY_MISMATCH) == findings
    assert report.failed_check_ids() == (
        () if clean else (_INVENTORY_CHECK_ID,)
    )
    return result


def _assert_fails_closed(context: ValidationContext, *, missing: str) -> None:
    """A check that cannot reach a verdict declines, and the run records a fail.

    Raising is only half of failing closed: the recorded result has to be a fail
    and the tag has to stay withheld, or a run launched without the inputs this
    check needs would pass a comparison it never made.
    """
    with pytest.raises(Unevaluable) as raised:
        check_skill_inventory(context)
    assert raised.value.message

    report = run_checks(context, checks=(_INVENTORY_CHECK_ID,))
    recorded = report.results_for(_INVENTORY_CHECK_ID)
    assert len(recorded) == 1
    assert recorded[0].result == RESULT_FAIL
    assert recorded[0].target == SKILL_INVENTORY_TARGET
    assert len(recorded[0].findings) == 1
    finding = recorded[0].findings[0]
    assert finding.code == E_INVENTORY_MISMATCH
    assert finding.details["unevaluated"] is True
    assert report.status == STATUS_FAILED
    assert report.tag_allowed is False, missing


# Feature: senzing-bootcamp-power, Property 16: Skill and command inventories
# are bijections with the template
#
# Validates: Requirements 7.1, 7.2, 9.1
@settings(max_examples=100)
@given(skill_tree(), template_tree())
def test_skill_and_command_inventories_are_bijections_with_the_template(
    skills: SkillTreeCase, tree: Mapping[str, TreeEntry]
) -> None:
    # The generator cases this property draws from, asserted rather than assumed.
    assert {"module_03b_names", "mixed"} <= set(SKILL_TREE_CASES)
    assert {"wellformed", "dotdot_segment"} <= set(TEMPLATE_TREE_CASES)

    # R7 AC1, AC2, R9 AC1: the gate this property drives, and the unit it
    # records a verdict over — one correspondence over the skill set, not one
    # result per skill.
    registered = registered_check(_INVENTORY_CHECK_ID)
    assert registered is not None
    assert registered.code == E_INVENTORY_MISMATCH
    assert registered.target == SKILL_INVENTORY_TARGET == f"{_SKILLS_ROOT}/*"
    assert registered.failure_code == E_INVENTORY_MISMATCH
    assert len(INVENTORY_KINDS) == len(set(INVENTORY_KINDS))

    # The declarations the correspondence is read from, spelled as the
    # requirements spell them and equal to the writer's and the gate's own
    # constants — the engine writes `metadata.templateSkill`, so a rename that
    # moved one and not the other would fail here.
    assert SKILL_METADATA_FIELD == _METADATA_FIELD
    assert SKILL_TEMPLATE_SKILL_FIELD == _TEMPLATE_SKILL_KEY
    assert TEMPLATE_COMMAND_FIELD == _TEMPLATE_COMMAND_KEY

    contract = load_contract()
    kiro_owned = kiro_owned_skill_names(contract)
    # R9 AC1: the command set is the one the contract matches and deliberately
    # does not port, and the skills that represent it are declared Kiro-owned —
    # so the residue rule accounts for them by declaration, not by exception.
    assert contract.rule("commands-superseded").source == (
        f"{_COMMANDS_ROOT}/*{_COMMAND_SUFFIX}"
    )
    # A subset, not an equality: the seed set is three commands wide because there
    # are three command failure modes, while the release declares however many it
    # declares. What must hold is that every seeded claimant is a real authored
    # command-derived skill, so the produced documents this property builds are the
    # ones the Power actually ships.
    assert set(_COMMAND_SKILLS.values()) <= set(COMMAND_DERIVED_SKILLS)
    assert set(_COMMAND_SKILLS.values()) <= set(kiro_owned)
    template_commands = tuple(sorted(_COMMAND_SKILLS))
    assert set(_COMMAND_SKILLS) == {
        _UNREPRESENTED_COMMAND,
        _DUPLICATED_COMMAND,
        _DOUBLE_CLAIMED_COMMAND,
    }

    # --- The template inventory, derived from the drawn release -------------
    drawn = _drawn_skill_names(tuple(skills.files) + tuple(tree))
    pool = tuple(drawn) + tuple(
        name for name in _EXTRA_TEMPLATE_NAMES if name not in drawn
    )
    template_skills = tuple(sorted(pool))
    roles = _seed_roles(pool)

    seeded_directories = (
        _SECOND_PORT_DIR,
        _RELOCATED_PORT_DIR,
        _STALE_PORT_DIR,
        _UNACCOUNTED_DIR,
        _SECOND_COMMAND_DIR,
        _STALE_COMMAND_DIR,
    )
    # The seeded directories and the stale command are absent from the release
    # and undeclared by the contract, which is what makes each seed the defect
    # it is named for rather than a compliant skill under another name.
    assert not set(seeded_directories) & set(template_skills)
    assert not set(seeded_directories) & set(kiro_owned)
    assert _UNACCOUNTED_DIR not in _COMMAND_SKILLS.values()
    assert _ABSENT_COMMAND not in template_commands
    assert not set(_EXTRA_TEMPLATE_NAMES) & set(drawn)
    assert len(set(roles.values())) == len(_SEED_ROLES)

    # The release the Power is measured against, read the same way whichever of
    # the two roots `--source` names.
    assert TEMPLATE_PLUGIN_ROOT == contract.plugin_root
    prefixes = ("", f"{TEMPLATE_PLUGIN_ROOT}/")
    for prefix in prefixes:
        source = _release_tree(template_skills, template_commands, prefix)
        assert source_prefix(source, contract.plugin_root) == prefix
        assert skill_names(source, prefix=prefix) == template_skills
        assert command_names(source, prefix=prefix) == template_commands
    source = _release_tree(template_skills, template_commands, prefixes[1])

    # --- Clause 1: the compliant Power reports nothing ----------------------
    compliant, owed = _seeded_power(template_skills, frozenset())
    assert owed == frozenset()
    passing = _assert_reports_exactly(
        compliant,
        owed=owed,
        template_skills=template_skills,
        template_commands=template_commands,
        kiro_owned=kiro_owned,
    )
    inventory = skill_inventory(PowerTree.from_mapping(compliant))
    # The bijection, stated as the correspondence R7 AC1 asks for: every template
    # skill directory is stood for exactly once, and no number appears in the
    # claim — the inventory is whatever the drawn release carries.
    assert ported_skill_names(inventory, template_skills) == template_skills
    assert sorted(port_claims(inventory, template_skills).values()) == list(
        template_skills
    )
    assert set(command_claims(inventory).values()) == set(template_commands)
    # R9 AC1: a correspondence, not a name comparison. The two name sets differ —
    # `graduate` is represented by `graduate-bootcamp` — and the Power is still
    # one-to-one with the command set.
    assert set(command_claims(inventory)) != set(template_commands)
    assert _COMMAND_SKILLS[_DOUBLE_CLAIMED_COMMAND] != _DOUBLE_CLAIMED_COMMAND
    assert passing.passed and passing.findings == ()

    # Defect D1's point, as a claim rather than a comment: the inventory is
    # derived from the resolved release, so a release that adds a module and one
    # that drops one are both bijections with the Power built from them. A gate
    # holding a number — the eleven R7 AC1 once fixed — passes at most one of
    # these three inventories.
    assert _UPSTREAM_ADDITION not in template_skills
    grown = tuple(sorted(template_skills + (_UPSTREAM_ADDITION,)))
    shrunk = template_skills[1:]
    assert len(shrunk) < len(template_skills) < len(grown)
    for adjusted in (grown, shrunk):
        documents, owed = _seeded_power(adjusted, frozenset())
        assert owed == frozenset()
        _assert_reports_exactly(
            documents,
            owed=owed,
            template_skills=adjusted,
            template_commands=template_commands,
            kiro_owned=kiro_owned,
        )

    # --- Clause 2: each way the correspondence fails, on its own ------------
    covered: set[str] = set()
    for label in _SEED_LABELS:
        documents, owed = _seeded_power(template_skills, frozenset({label}))
        assert owed, label
        result = _assert_reports_exactly(
            documents,
            owed=owed,
            template_skills=template_skills,
            template_commands=template_commands,
            kiro_owned=kiro_owned,
        )
        assert not result.passed, label
        covered |= {kind for kind, _ in owed}

    # Non-vacuous in every example: every kind the report vocabulary declares is
    # reached by a seed of its own, so none of them is a condition this property
    # merely describes.
    assert covered == set(INVENTORY_KINDS)

    # --- Clause 3: all nine at once, reported together ---------------------
    every = frozenset(_SEED_LABELS)
    documents, owed = _seeded_power(template_skills, every)
    fully_seeded = _assert_reports_exactly(
        documents,
        owed=owed,
        template_skills=template_skills,
        template_commands=template_commands,
        kiro_owned=kiro_owned,
    )
    # One run names the full remaining work: every seeded kind, not the first
    # one found, and one finding per pair.
    assert {kind for kind, _ in owed} == set(INVENTORY_KINDS)
    assert len(fully_seeded.findings) == len(owed) >= len(INVENTORY_KINDS)
    assert not fully_seeded.passed

    # --- Clause 4: the registered check, over a release tree ---------------
    for tag_allowed, files in ((True, compliant), (False, documents)):
        context = ValidationContext(
            tree=PowerTree.from_mapping(files),
            tag=_RESOLVED_TAG,
            contract=contract,
            source=source,
        )
        checked = check_skill_inventory(context)
        assert checked.id == _INVENTORY_CHECK_ID
        assert checked.passed is tag_allowed
        assert checked == skill_inventory_result(
            skill_inventory(context.tree),
            template_skills,
            template_commands,
            kiro_owned,
        )
        # The same verdict from either spelling of `--source`, and the runner
        # fills in the target the report names.
        report = run_checks(context, checks=(_INVENTORY_CHECK_ID,))
        assert report.tag_allowed is tag_allowed
        assert report.results_for(_INVENTORY_CHECK_ID) == (
            CheckResult(
                id=checked.id,
                target=SKILL_INVENTORY_TARGET,
                findings=checked.findings,
                extra=checked.extra,
            ),
        )
        bare = ValidationContext(
            tree=context.tree,
            tag=_RESOLVED_TAG,
            contract=contract,
            source=_release_tree(template_skills, template_commands, prefixes[0]),
        )
        assert check_skill_inventory(bare) == checked

    # --- Clause 5: no release, no contract, no skills — no verdict ---------
    power = PowerTree.from_mapping(compliant)
    _assert_fails_closed(
        ValidationContext(tree=power, tag=_RESOLVED_TAG, contract=contract),
        missing="the resolved release tree (--source)",
    )
    _assert_fails_closed(
        ValidationContext(tree=power, tag=_RESOLVED_TAG, source=source),
        missing="the Transformation_Contract",
    )
    _assert_fails_closed(
        ValidationContext(
            tree=power,
            tag=_RESOLVED_TAG,
            contract=contract,
            source=PowerTree.from_mapping(
                {
                    f"{prefixes[1]}{_command_document(command)}": f"# /{command}\n"
                    for command in template_commands
                }
            ),
        ),
        missing="any skills/ directory in the release",
    )

# ===========================================================================
# Property 17: Bootcamp progression order is preserved
# ===========================================================================
#
# R7 AC3 asks for one thing and it is an *order*: the Power presents its skills
# in the template's progression sequence, from onboarding through graduation.
# That order is declared once, in the contract's `progression` section, as phases
# matched against skill directory *names* — so both sequences here are derived
# from the same declaration, the template's from the skill directories the drawn
# release carries and the Power's from the skills that stand for them, and what
# is asserted is that they agree element-for-element.
#
# **No inventory count and no skill list appears in this section**, for defect
# D1's reason: the phases describe the *shape* of the progression, and the
# inventory that fills them is whatever the resolved release carries. A release
# that adds a module needs no edit here, and that is asserted rather than
# assumed — the release inventory is grown by one and shrunk by one below, and
# both are still preserved orders.
#
# Four claims
# -----------
# * **element-for-element** — the ported sequence equals the template sequence at
#   every position, and the two ends of it are the two ends R7 AC3 names.
# * **the interstitial position** — `module-03b-…` sits between `module-03-…` and
#   `module-04-…`, where a sort over whole directory names would put it wherever
#   the topic slug happened to fall. `interstitial_findings` states that as a
#   claim about a *given* sequence, so it is driven below with deliberately
#   MISORDERED ones: over a sequence `progression_sequence` produced it can only
#   ever agree with the key that produced it, and that self-check is asserted
#   separately for what it is.
# * **a name no declared phase claims** is reported — on the release side *and*
#   on the Power's. Upstream adding a skill of a shape the progression does not
#   describe is then an early warning with a name in it rather than a skill
#   quietly ordered last.
# * **the declared phases begin at onboarding and end at graduation** — R7 AC3's
#   own wording read literally, and the clause that carries the weight the
#   comparison cannot. Both sequences come from one declaration, so a declaration
#   that puts graduation in the middle orders *both* sides wrongly in the same way
#   and they still compare equal. The seeded phase moves below do exactly that,
#   and the endpoint check is what fails them.
#
# The order this section expects, written independently
# ----------------------------------------------------
# `_reference_sequence` implements R7 AC3 and the contract's declared phases from
# scratch: first phase in declaration order, then the module's leading number
# *parsed as a number* so `module-10` follows `module-09`, then the interstitial
# suffix, then the name. It uses neither `progression_key` nor the engine's glob
# matcher — a phase pattern is a literal or a trailing `*`, the two shapes the
# declaration is asserted to hold, and a skill directory name carries no `/` — so
# it is a second opinion rather than an echo. Every claim about an order below is
# stated against it.
#
# Exactly the violating set, from two independent oracles
# ------------------------------------------------------
# Six ways the order can fail to be the template's, and the gate owes all of them
# at once. Each is seeded alone, then all six together, and the reported set of
# `(kind, subject)` pairs — the subject being the thing one finding is about: an
# endpoint, a duplicated phase id, a skill and the side it was found on, or the
# position two sequences first part company at — is compared against that set
# computed twice, independently:
#
# * `_seeded_progression` returns the pairs its own *construction* owes, read off
#   the seed labels and the phase it moved; it never looks at a finding;
# * `_reference_progression_failures` re-derives them from R7 AC3 over the phases
#   and the two name collections as given, using this section's own ordering
#   oracle.
#
# Their equality is the biconditional, and `len(findings)` is asserted against
# the size of that set, so a report carrying a prefix of the truth — or one
# finding twice — fails.
#
# Fail closed, three ways
# -----------------------
# The check compares the Power against the release it was built from, ordered by
# the phases the contract declares, so it cannot reach a verdict without the
# release tree, without the contract, or over a release tree carrying no
# `skills/` directory — the last of which would otherwise compare two empty
# sequences successfully. All three are asserted at the check *and* at the
# runner, because raising is only half of failing closed: the recorded result has
# to be a fail and the tag has to stay withheld.
#
# Deliberately out of scope: *which* skills exist is Property 16's bijection —
# a membership difference surfaces here as well, and the two checks answer
# different questions about it — and whether a Bootcamper's session actually
# activates the skills in this order is not mechanically observable from a tree,
# which is what Test_Checklist step 8 is for.

#: The check this property drives.
_PROGRESSION_CHECK_ID = "progression-order"

#: The phase ids the contract declares, in declared order, spelled here as R7
#: AC3 spells the bootcamp and asserted equal to the contract's own declaration.
_PROGRESSION_PHASE_IDS = ("onboarding", "preparation", "modules", "graduation")

#: The phase whose pattern claims the numbered modules — the one seeded twice
#: below, since duplicating it leaves both endpoints where R7 AC3 wants them.
_MODULES_PHASE = "modules"

#: The two sides `unplaceable_findings` names, as the report names them.
_TEMPLATE_ORIGIN = "resolved Template_Release"
_POWER_ORIGIN = "Bootcamp_Power"

#: The endpoint skills, added to every drawn inventory so the sequence under test
#: spans onboarding through graduation in every example rather than only when the
#: generators happen to draw both ends.
_ONBOARDING_SKILL = "bootcamp-onboarding"
_PREPARATION_SKILL = "bootcamp-preparation"
_GRADUATION_SKILL = "graduation"

#: Modules a later release adds. Numbers above what `_skill_dir_name()` draws, so
#: they widen the drawn inventory without colliding with it. One is unpadded, the
#: shape the validator's own examples name, and `module-9` beside `module-10` is
#: the pair a sort over names rather than over numbers gets backwards.
_UNPADDED_MODULE = "module-9-unpadded-later"
_DOUBLE_DIGIT_MODULE = "module-10-double-digit"
_LATER_MODULES = (
    "module-08-added-upstream",
    "module-08b-interstitial-upstream",
    _UNPADDED_MODULE,
    _DOUBLE_DIGIT_MODULE,
)

#: A bootcamp skill of a shape no declared phase claims: not a module, not one of
#: the three named directories. The name upstream would have to add for the
#: answer to be a new phase rather than a silently reordered bootcamp.
_UNCLAIMED_SKILL = "capstone-project"

#: R7 AC3's own example, verbatim: the interstitial and the two modules it sits
#: between. Named here because the misordering clause needs a sequence it can
#: state the right answer for, whatever the generators drew.
_BASE_MODULE = "module-03-sdk-setup"
_INTERSTITIAL_MODULE = "module-03b-truthset-visualization"
_NEXT_MODULE = "module-04-search-and-match"
_ORDERED_MODULES = (_BASE_MODULE, _INTERSTITIAL_MODULE, _NEXT_MODULE)

#: A module the drawn release does not carry, for the grown-inventory clause.
_UPSTREAM_MODULE = "module-11-added-upstream"

#: One seeded defect each, labeled by what its construction owes.
_SEED_FIRST_PHASE = "a declaration that does not begin at onboarding"
_SEED_LAST_PHASE = "a declaration that does not end at graduation"
_SEED_DUPLICATE_PHASE = "a phase id declared twice"
_SEED_RELEASE_UNPLACEABLE = "a release skill no declared phase claims"
_SEED_PORTED_UNPLACEABLE = "a ported skill no declared phase claims"
_SEED_SKILL_DROPPED = "a ported sequence one skill short"

_PROGRESSION_SEEDS = (
    _SEED_FIRST_PHASE,
    _SEED_LAST_PHASE,
    _SEED_DUPLICATE_PHASE,
    _SEED_RELEASE_UNPLACEABLE,
    _SEED_PORTED_UNPLACEABLE,
    _SEED_SKILL_DROPPED,
)

#: The seeds that perturb only the two name collections. The registered check
#: reads its phases from the committed contract, so these are the seeds a
#: contract-driven run can carry.
_CONTENT_SEEDS = frozenset(
    {_SEED_RELEASE_UNPLACEABLE, _SEED_PORTED_UNPLACEABLE, _SEED_SKILL_DROPPED}
)

#: A license every produced skill declares, so the documents the ported
#: inventory is read out of are documents Property 13 would accept.
_PROGRESSION_LICENSE = "Apache-2.0"

#: A passing result from another check, so a withheld tag below can only have
#: come from `progression-order`.
_PASSING_PROGRESSION_SIBLING = CheckResult(id="plugin-schema", target=PLUGIN_MANIFEST)

#: A numbered module directory name, matched independently of the validator's own
#: pattern so the ordering oracle below is a second opinion rather than an echo.
_MODULE_DIRECTORY_RE = re.compile(r"\Amodule-([0-9]+)([a-z]*)(?:-(.*))?\Z", re.ASCII)


def _reference_claims(pattern: str, name: str) -> bool:
    """Does one declared phase pattern claim `name`?

    A skill directory name carries no `/`, so a trailing `*` spans the whole
    remainder of it and every other declared pattern is a literal. Those are the
    only two shapes the declaration is allowed to take, which the test asserts of
    the contract before relying on this.
    """
    if pattern.endswith("*"):
        return name.startswith(pattern[:-1])
    return name == pattern


def _reference_phase(name: str, phases: Sequence[ProgressionPhase]) -> int | None:
    """The index of the first declared phase claiming `name`, or `None`."""
    for index, phase in enumerate(phases):
        if _reference_claims(phase.match, name):
            return index
    return None


def _reference_key(
    name: str, phases: Sequence[ProgressionPhase]
) -> tuple[int, int, str, str]:
    """`name`'s position in the progression, from R7 AC3 and the declaration.

    Phase in declaration order, then the module's leading number *as a number* so
    `module-10` follows `module-09`, then the interstitial suffix so `module-03b`
    follows `module-03`, then the name itself so the order is total. A non-module
    name has no number and takes `-1`, which places it ahead of the modules
    inside its own phase and has no effect across phases.
    """
    index = _reference_phase(name, phases)
    module = _MODULE_DIRECTORY_RE.match(name)
    number = int(module.group(1)) if module is not None else -1
    interstitial = module.group(2) if module is not None else ""
    return (len(phases) if index is None else index, number, interstitial, name)


def _reference_sequence(
    names: Iterable[str], phases: Sequence[ProgressionPhase]
) -> tuple[str, ...]:
    """`names` in progression order, with the names no phase claims left out.

    Leaving them out is what keeps one finding about an unknown skill shape from
    also becoming a sequence difference at every later position.
    """
    placed = [name for name in names if _reference_phase(name, phases) is not None]
    return tuple(sorted(placed, key=lambda name: _reference_key(name, phases)))


def _divergence_subject(
    ported: Sequence[str], template: Sequence[str]
) -> str:
    """Where two sequences first part company, and what each presents there.

    The subject of the one sequence finding R7 AC3 owes: a Maintainer acts on the
    first divergence, and a single dropped skill shifts every position after it.
    """
    for index in range(max(len(ported), len(template))):
        here = ported[index] if index < len(ported) else None
        there = template[index] if index < len(template) else None
        if here != there:
            return f"{index}|{here}|{there}"
    raise AssertionError("the two sequences do not diverge")


def _progression_subject(finding: Finding) -> str:
    """The thing one progression finding is about, as its own details name it."""
    details = finding.details
    kind = details["kind"]
    if kind == PROGRESSION_PHASES_MISDECLARED:
        if "duplicated" in details:
            return ",".join(details["duplicated"])
        return str(details["expected"])
    if kind == PROGRESSION_UNPLACEABLE:
        return f"{details['origin']}|{details['skill']}"
    if kind == PROGRESSION_SEQUENCE_DIFFERS:
        first = details["divergences"][0]
        return f"{first['index']}|{first['ported']}|{first['template']}"
    return f"{details['skill']}|{'before' if 'before' in details else 'after'}"


def _assert_progression_finding_shape(finding: Finding) -> str:
    """Every progression finding is an error under one declared kind."""
    kind = finding.details["kind"]
    assert kind in PROGRESSION_KINDS, kind
    assert finding.code == E_PROGRESSION_MISMATCH
    assert finding.severity == SEVERITY_ERROR
    assert finding.message

    payload = finding.to_json()
    assert payload["code"] == E_PROGRESSION_MISMATCH
    assert payload["kind"] == kind
    assert payload["severity"] == SEVERITY_ERROR
    assert payload.get("target") == finding.target
    return kind


def _assert_names_the_violation(finding: Finding, named: Sequence[str]) -> None:
    """R7 AC3 is acted on by editing a declaration or a skill directory, so a
    finding that does not spell the name at issue is not actionable."""
    assert named, finding.details["kind"]
    for name in named:
        assert isinstance(name, str)
        assert name in finding.message or repr(name) in finding.message, name


def _assert_result_finding(
    finding: Finding,
    *,
    phases: Sequence[ProgressionPhase],
    ported: Sequence[str],
    template: Sequence[str],
) -> tuple[str, str]:
    """One finding `progression_result` reported, checked to name its subject.

    Returns its `(kind, subject)` pair. A finding about one skill names that
    skill's directory as its target; a finding about the declaration or about the
    whole sequence names no single file, and the check's own `skills/*` target is
    what the report carries for it.
    """
    kind = _assert_progression_finding_shape(finding)

    if kind == PROGRESSION_PHASES_MISDECLARED:
        assert finding.target is None
        assert finding.details["declared"] == [phase.id for phase in phases]
        if "duplicated" in finding.details:
            _assert_names_the_violation(finding, finding.details["duplicated"])
        else:
            assert finding.details["expected"] in (
                PROGRESSION_FIRST_PHASE,
                PROGRESSION_LAST_PHASE,
            )
            _assert_names_the_violation(finding, (finding.details["expected"],))
    elif kind == PROGRESSION_UNPLACEABLE:
        skill = finding.details["skill"]
        origin = finding.details["origin"]
        assert finding.target == _skill_directory(skill)
        assert origin in (_TEMPLATE_ORIGIN, _POWER_ORIGIN)
        assert skill in (template if origin == _TEMPLATE_ORIGIN else ported)
        _assert_names_the_violation(finding, (skill, origin))
    elif kind == PROGRESSION_SEQUENCE_DIFFERS:
        ported_sequence = _reference_sequence(ported, phases)
        template_sequence = _reference_sequence(template, phases)
        assert finding.target is None
        assert finding.details["ported"] == list(ported_sequence)
        assert finding.details["template"] == list(template_sequence)
        # Every divergent position travels as data, not just the first: one run
        # names the full extent of the difference to a consumer that reads it.
        assert [record["index"] for record in finding.details["divergences"]] == [
            index
            for index in range(max(len(ported_sequence), len(template_sequence)))
            if (
                ported_sequence[index] if index < len(ported_sequence) else None
            )
            != (
                template_sequence[index]
                if index < len(template_sequence)
                else None
            )
        ]
        assert finding.details["index"] == finding.details["divergences"][0]["index"]
        _assert_names_the_violation(
            finding, tuple(ported_sequence) + tuple(template_sequence)
        )
    else:  # pragma: no cover - a derived sequence cannot misplace one
        raise AssertionError(f"{kind} is not reachable from a derived sequence")

    return kind, _progression_subject(finding)


def _reference_progression_failures(
    phases: Sequence[ProgressionPhase],
    ported: Sequence[str],
    template: Sequence[str],
) -> frozenset[tuple[str, str]]:
    """The violating set, re-derived from R7 AC3 over the phases as declared.

    Written from the acceptance criterion and this section's own ordering oracle,
    and it never asks the validator what it expected.
    """
    identifiers = [phase.id for phase in phases]
    failures: set[tuple[str, str]] = set()

    duplicated = sorted(
        {name for name in identifiers if identifiers.count(name) > 1}
    )
    if duplicated:
        failures.add((PROGRESSION_PHASES_MISDECLARED, ",".join(duplicated)))
    if identifiers[0] != PROGRESSION_FIRST_PHASE:
        failures.add((PROGRESSION_PHASES_MISDECLARED, PROGRESSION_FIRST_PHASE))
    if identifiers[-1] != PROGRESSION_LAST_PHASE:
        failures.add((PROGRESSION_PHASES_MISDECLARED, PROGRESSION_LAST_PHASE))

    for origin, names in ((_TEMPLATE_ORIGIN, template), (_POWER_ORIGIN, ported)):
        for name in sorted(set(names)):
            if _reference_phase(name, phases) is None:
                failures.add((PROGRESSION_UNPLACEABLE, f"{origin}|{name}"))

    ported_sequence = _reference_sequence(ported, phases)
    template_sequence = _reference_sequence(template, phases)
    if ported_sequence != template_sequence:
        failures.add(
            (
                PROGRESSION_SEQUENCE_DIFFERS,
                _divergence_subject(ported_sequence, template_sequence),
            )
        )

    return frozenset(failures)


def _seeded_progression(
    declared: Sequence[ProgressionPhase],
    release: Sequence[str],
    seeds: frozenset[str],
) -> tuple[
    tuple[ProgressionPhase, ...],
    tuple[str, ...],
    tuple[str, ...],
    frozenset[tuple[str, str]],
]:
    """A declaration, a release inventory, a ported one, and what they owe.

    The compliant construction is the whole of R7 AC3: the contract's phases as
    declared, and a Power that ports every skill directory the release carries.
    Each seed then perturbs one thing and states what that owes, read off the
    labels and the phase it moved rather than off any finding — which is what
    makes this oracle independent of `_reference_progression_failures`.

    The phase moves are the interesting half. Both sequences are derived from the
    declaration, so moving a phase reorders *both* of them identically and they
    still compare equal element-for-element; what fails such a declaration is the
    endpoint check, and nothing else would.
    """
    phases = list(declared)
    owed: set[tuple[str, str]] = set()

    if _SEED_DUPLICATE_PHASE in seeds:
        # A second phase under one id. The first claim places a name, so the
        # sequences are untouched and the declaration is the only thing wrong.
        index = next(
            position
            for position, phase in enumerate(phases)
            if phase.id == _MODULES_PHASE
        )
        phases.insert(index + 1, phases[index])
        owed.add((PROGRESSION_PHASES_MISDECLARED, _MODULES_PHASE))
    if _SEED_FIRST_PHASE in seeds:
        # Onboarding moved out of first position: the bootcamp no longer starts
        # where R7 AC3 says it starts.
        moved = phases.pop(
            next(
                position
                for position, phase in enumerate(phases)
                if phase.id == PROGRESSION_FIRST_PHASE
            )
        )
        phases.insert(len(phases) - 1, moved)
        owed.add((PROGRESSION_PHASES_MISDECLARED, PROGRESSION_FIRST_PHASE))
    if _SEED_LAST_PHASE in seeds:
        # Graduation in the middle, which is the declaration the comparison
        # cannot notice.
        moved = phases.pop(
            next(
                position
                for position, phase in enumerate(phases)
                if phase.id == PROGRESSION_LAST_PHASE
            )
        )
        phases.insert(1, moved)
        owed.add((PROGRESSION_PHASES_MISDECLARED, PROGRESSION_LAST_PHASE))

    template = list(release)
    ported = list(release)

    if _SEED_RELEASE_UNPLACEABLE in seeds:
        # Upstream added a skill of a shape the progression does not describe.
        template.append(_UNCLAIMED_SKILL)
        owed.add(
            (PROGRESSION_UNPLACEABLE, f"{_TEMPLATE_ORIGIN}|{_UNCLAIMED_SKILL}")
        )
    if _SEED_PORTED_UNPLACEABLE in seeds:
        # The same shape from the Power's side, reported in its own vocabulary.
        ported.append(_UNCLAIMED_SKILL)
        owed.add((PROGRESSION_UNPLACEABLE, f"{_POWER_ORIGIN}|{_UNCLAIMED_SKILL}"))
    if _SEED_SKILL_DROPPED in seeds:
        # The one way a *derived* sequence can differ from another derived the
        # same way: membership. Both sides are sorted by one key, so a permuted
        # inventory is not a difference and a missing skill is.
        dropped = _reference_sequence(template, phases)[-1]
        ported.remove(dropped)
        owed.add(
            (
                PROGRESSION_SEQUENCE_DIFFERS,
                _divergence_subject(
                    _reference_sequence(ported, phases),
                    _reference_sequence(template, phases),
                ),
            )
        )

    return (
        tuple(phases),
        tuple(sorted(template)),
        tuple(sorted(ported)),
        frozenset(owed),
    )


def _assert_progression_reports_exactly(
    phases: Sequence[ProgressionPhase],
    ported: Sequence[str],
    template: Sequence[str],
    *,
    owed: frozenset[tuple[str, str]],
) -> CheckResult:
    """Order one release and one ported inventory, and check the verdict.

    Asserts both sequences are the order R7 AC3 describes, that the reported
    failures are exactly `owed` — no more, no fewer, and not a prefix — that the
    two oracles agree on that set, that every finding names the thing at fault,
    and that the recorded result and the release gate follow from it and nothing
    else.
    """
    template_sequence = _reference_sequence(template, phases)
    ported_sequence = _reference_sequence(ported, phases)

    # Both sequences are the declared order, and the names no phase claims are
    # named rather than parked at one end of it.
    assert progression_sequence(template, phases) == template_sequence
    assert progression_sequence(ported, phases) == ported_sequence
    for names in (template, ported):
        assert unplaceable_skills(names, phases) == tuple(
            sorted(
                name
                for name in names
                if _reference_phase(name, phases) is None
            )
        )
        for name in names:
            assert phase_index(name, phases) == _reference_phase(name, phases)
            assert progression_key(name, phases) == _reference_key(name, phases)

    result = progression_result(phases, ported, template)
    findings = result.findings

    # --- Exactly the violating set, from both oracles ----------------------
    reported = tuple(
        _assert_result_finding(
            finding, phases=phases, ported=ported, template=template
        )
        for finding in findings
    )
    assert frozenset(reported) == owed
    assert _reference_progression_failures(phases, ported, template) == owed
    # Not a prefix, and nothing reported twice.
    assert len(reported) == len(owed)

    # R7 AC3's own clause, and the one finding that answers to it: the sequences
    # agree at every position exactly when nothing is reported about the order.
    differs = any(
        kind == PROGRESSION_SEQUENCE_DIFFERS for kind, _ in reported
    )
    assert (ported_sequence == template_sequence) is not differs
    if not differs:
        assert all(
            here == there
            for here, there in zip(ported_sequence, template_sequence, strict=True)
        )
    assert sequence_findings(ported_sequence, ported_sequence) == ()

    # The four sources of a progression finding, composed. The interstitial
    # clause contributes nothing over a sequence the key produced — that is the
    # self-check, and it is why the misordering clause drives it directly.
    assert findings == (
        phase_declaration_findings(phases)
        + unplaceable_findings(tuple(template), phases, origin=_TEMPLATE_ORIGIN)
        + unplaceable_findings(tuple(ported), phases, origin=_POWER_ORIGIN)
        + sequence_findings(ported_sequence, template_sequence)
    )
    assert interstitial_findings(ported_sequence) == ()
    assert interstitial_findings(template_sequence) == ()

    # --- The recorded result, and the gate over it -------------------------
    clean = owed == frozenset()
    assert result.id == _PROGRESSION_CHECK_ID
    assert result.result == (RESULT_PASS if clean else RESULT_FAIL)
    assert result.passed is clean
    # Pure over the declared phases and the two name collections: the same
    # inputs twice, the same result, whatever a filesystem or a clock is doing.
    assert progression_result(phases, ported, template) == result
    assert result.extra["phases"] == [
        {"id": phase.id, "match": phase.match} for phase in phases
    ]
    assert result.extra["templateSequence"] == list(template_sequence)
    assert result.extra["portedSequence"] == list(ported_sequence)
    assert result.extra["mismatches"] == [
        {
            "kind": finding.details["kind"],
            "target": finding.target,
            **{
                key: value
                for key, value in finding.details.items()
                if key != "kind"
            },
        }
        for finding in findings
    ]

    report = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_PASSING_PROGRESSION_SIBLING, result),
    )
    assert _PASSING_PROGRESSION_SIBLING.passed
    assert report.status == (STATUS_PASSED if clean else STATUS_FAILED)
    assert report.tag_allowed is clean
    assert report.findings_for(E_PROGRESSION_MISMATCH) == findings
    assert report.failed_check_ids() == (() if clean else (_PROGRESSION_CHECK_ID,))
    return result


def _progression_power(ported: Sequence[str]) -> PowerTree:
    """A produced Power whose skills declare the template skill each ports.

    The declaration is what `ported_skill_names` reads the bootcamp inventory
    from, so the ported sequence the check orders is derived from the artifacts
    rather than from a path convention this test asserts twice.
    """
    return PowerTree.from_mapping(
        {
            _skill_entry_point(name): _skill_document(
                {
                    "name": name,
                    "description": f"Work through {name}.",
                    "license": _PROGRESSION_LICENSE,
                    SKILL_METADATA_FIELD: {SKILL_TEMPLATE_SKILL_FIELD: name},
                }
            )
            for name in ported
        }
    )


def _progression_release(names: Sequence[str], prefix: str) -> PowerTree:
    """A resolved release tree carrying those skill directories.

    `prefix` is how `--source` was given: `""` for the plugin root itself, the
    marketplace path for the repository root a release tarball unpacks to. The
    derived template sequence must not depend on which one a Maintainer handed
    the validator.
    """
    return PowerTree.from_mapping(
        {f"{prefix}{_skill_entry_point(name)}": f"# {name}\n" for name in names}
    )


def _assert_progression_fails_closed(
    context: ValidationContext, *, missing: str
) -> None:
    """A check that cannot reach a verdict declines, and the run records a fail.

    Raising is only half of failing closed: the recorded result has to be a fail
    and the tag has to stay withheld, or a run launched without the inputs this
    check needs would pass a comparison it never made.
    """
    with pytest.raises(Unevaluable) as raised:
        check_progression_order(context)
    assert raised.value.message

    report = run_checks(context, checks=(_PROGRESSION_CHECK_ID,))
    recorded = report.results_for(_PROGRESSION_CHECK_ID)
    assert len(recorded) == 1
    assert recorded[0].result == RESULT_FAIL
    assert recorded[0].target == SKILL_INVENTORY_TARGET
    assert len(recorded[0].findings) == 1
    finding = recorded[0].findings[0]
    assert finding.code == E_PROGRESSION_MISMATCH
    assert finding.details["unevaluated"] is True
    assert report.status == STATUS_FAILED
    assert report.tag_allowed is False, missing


# Feature: senzing-bootcamp-power, Property 17: Bootcamp progression order is
# preserved
#
# Validates: Requirements 7.3
@settings(max_examples=100)
@given(skill_tree())
def test_bootcamp_progression_order_is_preserved(skills: SkillTreeCase) -> None:
    # The generator case R7 AC3 turns on, asserted rather than assumed: the
    # interstitial shape is drawn, not written into this test.
    assert {"module_03b_names", "mixed"} <= set(SKILL_TREE_CASES)

    # R7 AC3: the gate this property drives, and the unit it records a verdict
    # over — one order across the skill set, not one result per skill.
    registered = registered_check(_PROGRESSION_CHECK_ID)
    assert registered is not None
    assert registered.code == E_PROGRESSION_MISMATCH
    assert registered.target == SKILL_INVENTORY_TARGET == f"{_SKILLS_ROOT}/*"
    assert registered.failure_code == E_PROGRESSION_MISMATCH
    assert registered.requirement == "7.3"
    assert len(PROGRESSION_KINDS) == len(set(PROGRESSION_KINDS))

    # --- The order, declared once in the contract ---------------------------
    contract = load_contract()
    declared = progression_phases(contract)
    assert tuple(phase.id for phase in declared) == _PROGRESSION_PHASE_IDS
    assert declared[0].id == PROGRESSION_FIRST_PHASE == "onboarding"
    assert declared[-1].id == PROGRESSION_LAST_PHASE == "graduation"
    assert phase_declaration_findings(declared) == ()
    # Declared as data, in one place, and with no count and no skill list in it:
    # a phase is an id and a pattern, which is defect D1's resolution stated as
    # a claim about the declaration itself.
    raw = contract.raw[PROGRESSION_SECTION]
    assert [entry["id"] for entry in raw] == list(_PROGRESSION_PHASE_IDS)
    assert [entry["match"] for entry in raw] == [
        phase.match for phase in declared
    ]
    for entry in raw:
        assert set(entry) == {"id", "match"}
    # The two pattern shapes this section's ordering oracle handles, and the one
    # phase whose pattern claims a family rather than a single directory.
    for phase in declared:
        assert "/" not in phase.match
        assert "*" not in phase.match[:-1]
    assert [phase.id for phase in declared if phase.match.endswith("*")] == [
        _MODULES_PHASE
    ]

    # --- The release inventory, derived from what was drawn -----------------
    drawn = _drawn_skill_names(tuple(skills.files))
    release = tuple(
        sorted(
            set(drawn)
            | {_ONBOARDING_SKILL, _PREPARATION_SKILL, _GRADUATION_SKILL}
            | set(_LATER_MODULES)
        )
    )
    assert drawn
    assert set(drawn) <= set(release)
    for name in release:
        assert "/" not in name
        assert _reference_phase(name, declared) is not None
    # The name no phase claims is a name the release does not carry, which is
    # what makes the unplaceable seeds the defect they are named for.
    assert _UNCLAIMED_SKILL not in release
    assert _UPSTREAM_MODULE not in release
    assert _reference_phase(_UNCLAIMED_SKILL, declared) is None
    assert phase_index(_UNCLAIMED_SKILL, declared) is None

    # --- Clause 1: the preserved order reports nothing ----------------------
    phases, template, ported, owed = _seeded_progression(
        declared, release, frozenset()
    )
    assert phases == declared
    assert template == ported == release
    assert owed == frozenset()
    passing = _assert_progression_reports_exactly(
        phases, ported, template, owed=owed
    )
    assert passing.passed and passing.findings == ()

    # R7 AC3 read literally: onboarding through graduation, with every module in
    # between ordered by its number rather than by its name.
    sequence = progression_sequence(template, declared)
    assert sequence[0] == _ONBOARDING_SKILL
    assert sequence[1] == _PREPARATION_SKILL
    assert sequence[-1] == _GRADUATION_SKILL
    # The number is a number: `module-9` precedes `module-10`, which a sort over
    # directory names gets backwards, and an interstitial follows the module of
    # its own number rather than the next one.
    assert sequence.index(_UNPADDED_MODULE) < sequence.index(_DOUBLE_DIGIT_MODULE)
    assert _UNPADDED_MODULE > _DOUBLE_DIGIT_MODULE
    assert (
        sequence.index("module-08-added-upstream")
        < sequence.index("module-08b-interstitial-upstream")
        < sequence.index(_UNPADDED_MODULE)
    )

    # Defect D1's point, as a claim rather than a comment: the order is derived
    # from the resolved release, so a release that adds a module and one that
    # drops one are both preserved orders. Nothing here holds a count.
    grown = tuple(sorted(release + (_UPSTREAM_MODULE,)))
    shrunk = tuple(name for name in release if name != _LATER_MODULES[0])
    assert len(shrunk) < len(release) < len(grown)
    for adjusted in (grown, shrunk):
        _, adjusted_template, adjusted_ported, adjusted_owed = _seeded_progression(
            declared, adjusted, frozenset()
        )
        assert adjusted_owed == frozenset()
        _assert_progression_reports_exactly(
            declared, adjusted_ported, adjusted_template, owed=adjusted_owed
        )

    # --- Clause 2: the interstitial position, over a given sequence ---------
    # R7 AC3's own example. `module_key` is what places it, so the key is stated
    # first and the sort that follows from it second.
    assert module_key(_BASE_MODULE) == (3, "")
    assert module_key(_INTERSTITIAL_MODULE) == (3, "b")
    assert module_key(_NEXT_MODULE) == (4, "")
    assert (
        module_key(_BASE_MODULE)
        < module_key(_INTERSTITIAL_MODULE)
        < module_key(_NEXT_MODULE)
    )
    assert module_key(_ONBOARDING_SKILL) is None
    interstitial_match = MODULE_NAME.match(_INTERSTITIAL_MODULE)
    assert interstitial_match is not None
    assert interstitial_match.group("number", "interstitial", "topic") == (
        "03",
        "b",
        "truthset-visualization",
    )
    # Whatever order the three arrive in, `module-03b` lands between the two.
    for arrival in (_ORDERED_MODULES, tuple(reversed(_ORDERED_MODULES))):
        assert progression_sequence(arrival, declared) == _ORDERED_MODULES
        assert _reference_sequence(arrival, declared) == _ORDERED_MODULES
    assert interstitial_findings(_ORDERED_MODULES) == ()

    # Driven with deliberately misordered sequences, so the clause is a claim
    # about a position and not a restatement of the sort that produced it.
    misorderings = (
        (
            (_INTERSTITIAL_MODULE, _BASE_MODULE, _NEXT_MODULE),
            frozenset({f"{_INTERSTITIAL_MODULE}|before"}),
        ),
        (
            (_BASE_MODULE, _NEXT_MODULE, _INTERSTITIAL_MODULE),
            frozenset({f"{_INTERSTITIAL_MODULE}|after"}),
        ),
        (
            (_NEXT_MODULE, _INTERSTITIAL_MODULE, _BASE_MODULE),
            frozenset(
                {
                    f"{_INTERSTITIAL_MODULE}|before",
                    f"{_INTERSTITIAL_MODULE}|after",
                }
            ),
        ),
    )
    for misordered, subjects in misorderings:
        misplaced = interstitial_findings(misordered)
        assert len(misplaced) == len(subjects)
        for finding in misplaced:
            assert _assert_progression_finding_shape(finding) == (
                PROGRESSION_INTERSTITIAL_MISPLACED
            )
            assert finding.target == _skill_directory(_INTERSTITIAL_MODULE)
            assert finding.details["skill"] == _INTERSTITIAL_MODULE
            assert finding.details["interstitial"] == "b"
            _assert_names_the_violation(
                finding,
                (_INTERSTITIAL_MODULE,)
                + tuple(
                    value
                    for key, value in finding.details.items()
                    if key in ("before", "after")
                ),
            )
        assert {
            _progression_subject(finding) for finding in misplaced
        } == subjects

    # --- Clause 3: each way the order fails, on its own --------------------
    covered = {PROGRESSION_INTERSTITIAL_MISPLACED}
    for seed in _PROGRESSION_SEEDS:
        phases, template, ported, owed = _seeded_progression(
            declared, release, frozenset({seed})
        )
        assert owed, seed
        result = _assert_progression_reports_exactly(
            phases, ported, template, owed=owed
        )
        assert not result.passed, seed
        covered |= {kind for kind, _ in owed}

    # Non-vacuous in every example: every kind the report vocabulary declares is
    # reached, so none of them is a condition this property merely describes.
    assert covered == set(PROGRESSION_KINDS)

    # --- Clause 4: all six at once, reported together ----------------------
    every = frozenset(_PROGRESSION_SEEDS)
    phases, template, ported, owed = _seeded_progression(declared, release, every)
    fully_seeded = _assert_progression_reports_exactly(
        phases, ported, template, owed=owed
    )
    assert not fully_seeded.passed
    assert len(fully_seeded.findings) == len(owed) == len(every)
    assert {kind for kind, _ in owed} == set(PROGRESSION_KINDS) - {
        PROGRESSION_INTERSTITIAL_MISPLACED
    }
    # The moved phases are the point of the endpoint clause: both sequences are
    # derived from the one declaration, so they are ordered the same wrong way
    # and the comparison alone would have found nothing to say.
    assert [phase.id for phase in phases] != list(_PROGRESSION_PHASE_IDS)
    assert _reference_sequence(release, phases) != _reference_sequence(
        release, declared
    )
    assert progression_sequence(release, phases) == _reference_sequence(
        release, phases
    )

    # --- Clause 5: the registered check, over a release tree ---------------
    assert TEMPLATE_PLUGIN_ROOT == contract.plugin_root
    prefixes = ("", f"{TEMPLATE_PLUGIN_ROOT}/")
    seeded_phases, seeded_template, seeded_ported, seeded_owed = _seeded_progression(
        declared, release, _CONTENT_SEEDS
    )
    # A contract-driven run reads its phases from the contract, so these seeds
    # perturb the inventories only.
    assert seeded_phases == declared
    assert seeded_owed

    for tag_allowed, names, expected in (
        (True, (release, release), frozenset()),
        (False, (seeded_template, seeded_ported), seeded_owed),
    ):
        template_names, ported_names = names
        power = _progression_power(ported_names)
        source = _progression_release(template_names, prefixes[1])
        assert source_prefix(source, contract.plugin_root) == prefixes[1]
        assert skill_names(source, prefix=prefixes[1]) == tuple(
            sorted(template_names)
        )
        inventory = skill_inventory(power)
        assert ported_skill_names(inventory, template_names) == tuple(
            sorted(ported_names)
        )

        context = ValidationContext(
            tree=power, tag=_RESOLVED_TAG, contract=contract, source=source
        )
        checked = check_progression_order(context)
        assert checked.id == _PROGRESSION_CHECK_ID
        assert checked.passed is tag_allowed
        assert checked == progression_result(
            declared,
            ported_skill_names(inventory, template_names),
            skill_names(source, prefix=prefixes[1]),
        )
        assert _assert_progression_reports_exactly(
            declared,
            tuple(sorted(ported_names)),
            tuple(sorted(template_names)),
            owed=expected,
        ) == checked

        # The runner fills in the target the report names, and the gate follows
        # the recorded result.
        report = run_checks(context, checks=(_PROGRESSION_CHECK_ID,))
        assert report.tag_allowed is tag_allowed
        assert report.results_for(_PROGRESSION_CHECK_ID) == (
            CheckResult(
                id=checked.id,
                target=SKILL_INVENTORY_TARGET,
                findings=checked.findings,
                extra=checked.extra,
            ),
        )
        # The same verdict from either spelling of `--source`.
        bare = ValidationContext(
            tree=power,
            tag=_RESOLVED_TAG,
            contract=contract,
            source=_progression_release(template_names, prefixes[0]),
        )
        assert source_prefix(bare.source, contract.plugin_root) == prefixes[0]
        assert check_progression_order(bare) == checked

    # --- Clause 6: no release, no contract, no skills — no verdict ---------
    power = _progression_power(release)
    source = _progression_release(release, prefixes[1])
    _assert_progression_fails_closed(
        ValidationContext(tree=power, tag=_RESOLVED_TAG, contract=contract),
        missing="the resolved release tree (--source)",
    )
    _assert_progression_fails_closed(
        ValidationContext(tree=power, tag=_RESOLVED_TAG, source=source),
        missing="the Transformation_Contract, which declares the order",
    )
    _assert_progression_fails_closed(
        ValidationContext(
            tree=power,
            tag=_RESOLVED_TAG,
            contract=contract,
            source=PowerTree.from_mapping(
                {f"{prefixes[1]}docs/overview.md": "# overview\n"}
            ),
        ),
        missing="any skills/ directory in the release",
    )


# ===========================================================================
# Property 18: Every template hook behavior remains reachable
# ===========================================================================
#
# Seven template hook registrations carry the bootcamp's enforced behaviors, and
# Kiro reproduces none of them the way Claude does: five have an equivalent
# trigger, `Stop` has one that cannot block, and `PreCompact` and `SessionEnd`
# have no trigger at all. The three tiers exist so that none of that is a loss —
# Tier 1 states every behavior as an instruction, so the bootcamp is complete
# with zero hook definitions installed *(R7 AC4)*; Tier 2 restores mechanical
# enforcement wherever a trigger exists *(R7 AC5)*; Tier 3 bundles the same
# definitions under `dev.kiro/hooks/` on the chance Kiro one day loads them
# *(R7 AC12)*. What this property asserts is the thing the tiers are laid down
# for: once all three are in the produced Power, no behavior fell between them.
#
# What is already structural, and what is left over for here
# ----------------------------------------------------------
# The hook structural tests assert the coverage map's *shape*: one event per row
# of the design's parity table, a mechanism and a tier on each, a definition
# exactly where a trigger exists and none where it does not, a documented gap
# where parity is partial, a non-empty `skillInstructions` array everywhere. All
# of that is a claim the map makes about itself, and the one thing a map cannot
# check about itself is whether the behavior is really *there*: an entry naming a
# location and a marker is a promise about a file's contents, worth exactly what
# the file says. So this section reads every declared location **out of the
# produced Power** and requires the marker in it, reads every declared definition
# out of the produced Power and requires its command to run the behavior's
# script, and treats the map's `tiers` array as the claim under test rather than
# as the answer.
#
# The oracle, and why Tier 3 does not count
# -----------------------------------------
# `_hook_reach_delivery` returns the set of `(tier, path)` pairs by which the
# tree *actually* delivers a behavior. A definition delivers when it is present
# and one of its command strings names the behavior's script; an instruction
# delivers when its declared location is present and carries the behavior's
# marker. Coverage is that set being non-empty — and R7 AC12 is the stronger
# claim that it stays non-empty with the Tier 3 pairs struck out, which is
# asserted twice over: once by intersecting the tiers, and once by rebuilding the
# tree with `dev.kiro/hooks/` deleted outright and re-asking. That second form is
# the honest one, because assumption **A1** says a bundled hooks directory
# probably never loads at all, and a behavior delivered only there is a behavior
# the Bootcamper never receives.
#
# Two further reachability clauses ride along, both of them about a behavior
# arriving rather than a file existing:
#
# * **the script *(R10 AC5)*.** Every script a template hook invoked is named by
#   a generated hook command or by a declared instruction location. For
#   `precompact-recap.py` and `session-end.py` no command can name them, so the
#   instruction prose is the only place the ported script is reachable from, and
#   that is exactly where the rewiring rule sends it.
# * **the referrer *(R7 AC4)*.** An instruction file nobody is pointed at is not
#   delivered, whatever it contains. The map declares its expected referrers, and
#   each declared location has to be linked from one that exists in the Power —
#   resolved with the same Markdown reader Property 12 uses, not by substring.
#
# Non-vacuous, by construction
# ----------------------------
# "Covered" is the kind of claim that passes when the oracle cannot tell present
# from absent, so a drawn set of registrations is broken on every example, in one
# of three ways, and the resulting delivery sets are compared against a
# *predicted* delta rather than against a second run of the same code path:
#
# * **`drop-marker`** — strike the drawn behaviors' markers from the instruction
#   files, leaving the files themselves in place. Only those behaviors lose Tier
#   1, which is a fact about the markers being behavior-specific, asserted
#   separately.
# * **`delete-instruction-location`** — delete the declared locations. Every
#   behavior with a marker in a deleted file loses Tier 1, including behaviors
#   nobody broke on purpose, and the prediction says which.
# * **`tier3-only`** — strike the markers *and* delete the Tier 2 definitions,
#   leaving Tier 3 standing. This is R7 AC12's counterfactual: the behavior still
#   ships, in a directory that may never be read, and the Tier-3-only oracle has
#   to name it.
#
# In every case the mutated tree's delivery sets must equal the prediction
# exactly, and the two report oracles must name exactly the behaviors that lost
# everything and exactly the ones left at Tier 3 alone.
#
# Deliberately out of scope: whether a Hook_Command_String is absolute, quoted,
# and shell-free is Property 24's; whether the shipped definitions carry the
# right triggers, matchers, and filenames is structural; whether Kiro fires any
# of it — or loads `dev.kiro/hooks/` at all — is Test_Checklist steps 9 through
# 11. `_base_power()`'s produced tree is shared with the sections above.

#: The design's per-hook parity table, by coverage-map event id: (template event,
#: ported script). Spelled here because the draws below need the ids at
#: decoration time, and asserted against the shipped coverage map inside the
#: test — a registration the map dropped, or one it invented, fails there.
_HOOK_REACH_REGISTRATIONS: Mapping[str, tuple[str, str]] = {
    "session-start": ("SessionStart", "session-start.py"),
    "feedback-capture": ("UserPromptSubmit", "feedback-capture.py"),
    "checkpoint-tick": ("UserPromptSubmit", "checkpoint-tick.py"),
    "write-gate": ("PreToolUse", "write-gate.py"),
    "stop-nudge": ("Stop", "stop-nudge.py"),
    "precompact-recap": ("PreCompact", "precompact-recap.py"),
    "session-end": ("SessionEnd", "session-end.py"),
}
_HOOK_REACH_EVENT_IDS = tuple(_HOOK_REACH_REGISTRATIONS)

#: The vocabulary a Tier 1 marker is spelled in. Every declared marker has to
#: carry it, so a location and a plausible-looking string cannot pass for a
#: behavior this bootcamp states.
_HOOK_REACH_MARKER_PREFIX = "SENZING-BOOTCAMP-TIER1:"

#: The tiers, as the coverage map numbers them.
_HOOK_REACH_TIER1 = 1
_HOOK_REACH_TIER2 = 2
_HOOK_REACH_TIER3 = 3

#: The tiers that actually reach a Bootcamper *(R7 AC12)*. Tier 3 is deliberately
#: absent: A1 says a bundled `dev.kiro/hooks/` may never load, so a behavior
#: delivered there alone is a behavior that is gone.
_HOOK_REACH_DELIVERING_TIERS = frozenset({_HOOK_REACH_TIER1, _HOOK_REACH_TIER2})

#: The mechanism types the map may declare: a Kiro trigger exists, or it does not.
_HOOK_REACH_MECHANISM_TRIGGER = "trigger"
_HOOK_REACH_MECHANISM_NONE = "none"

#: Which requirement documents which kind of partial parity. No trigger at all is
#: R7 AC13's case; a trigger that cannot block what the template blocked is AC14's.
_HOOK_REACH_GAP_NO_TRIGGER = "7.13"
_HOOK_REACH_GAP_NO_BLOCKING = "7.14"

#: The three ways an example breaks the Power, one per way a behavior can stop
#: being reachable while every file still looks plausible.
_HOOK_REACH_DROP_MARKER = "drop-marker"
_HOOK_REACH_DELETE_LOCATION = "delete-instruction-location"
_HOOK_REACH_TIER3_ONLY = "tier3-only"
_HOOK_REACH_BREAKS = (
    _HOOK_REACH_DROP_MARKER,
    _HOOK_REACH_DELETE_LOCATION,
    _HOOK_REACH_TIER3_ONLY,
)


@dataclass(frozen=True)
class _HookInstructionClaim:
    """One `skillInstructions` entry: where a behavior is stated, and as what."""

    marker: str
    location: str
    advisory_only: bool


@dataclass(frozen=True)
class _HookBehaviorClaim:
    """One template hook registration, as the shipped coverage map declares it.

    Everything here is a claim. The delivery oracle below re-derives what the
    produced Power does about it from the Power's own bytes.
    """

    event_id: str
    template_event: str
    script: str
    mechanism_type: str
    trigger: str | None
    can_block: bool
    blocking_required: bool
    declared_tiers: tuple[int, ...]
    definitions: tuple[tuple[int, str], ...]
    instructions: tuple[_HookInstructionClaim, ...]
    parity_gap: Mapping[str, Any] | None

    @property
    def locations(self) -> frozenset[str]:
        return frozenset(claim.location for claim in self.instructions)


@lru_cache(maxsize=1)
def _hook_reach_power() -> PowerTree:
    """The produced Power, as the tree the coverage map's paths are relative to."""
    return PowerTree.from_mapping(dict(_base_power().power))


@lru_cache(maxsize=1)
def _hook_reach_map() -> Mapping[str, Any]:
    """The coverage map, read out of the produced Power rather than off disk.

    The map is a shipped asset: reading the authored copy would leave "the Power
    carries it" untested, and it is the shipped copy the Hook_Installer and the
    gate both single-source their definition glob from.
    """
    tree = _hook_reach_power()
    assert tree.exists(HOOK_COVERAGE_MAP), (
        f"the produced Power carries no {HOOK_COVERAGE_MAP}, so nothing declares "
        "where each template hook behavior is delivered"
    )
    document = tree.read_json(HOOK_COVERAGE_MAP)
    assert isinstance(document, Mapping), f"{HOOK_COVERAGE_MAP} is not a JSON object"
    return document


@lru_cache(maxsize=1)
def _hook_reach_behaviors() -> tuple[_HookBehaviorClaim, ...]:
    """Every declared registration, parsed into the shape the oracle reads."""
    events = _hook_reach_map().get("events")
    assert isinstance(events, list) and events, (
        f"{HOOK_COVERAGE_MAP} declares no non-empty `events` array"
    )
    behaviors: list[_HookBehaviorClaim] = []
    for event in events:
        assert isinstance(event, Mapping), (
            f"{HOOK_COVERAGE_MAP}: {event!r} is not an object"
        )
        mechanism = event.get("kiroMechanism")
        assert isinstance(mechanism, Mapping), (
            f"{HOOK_COVERAGE_MAP}: event {event.get('id')!r} declares no kiroMechanism"
        )
        definitions: list[tuple[int, str]] = []
        for entry in event.get("hookDefinitions") or ():
            assert isinstance(entry, Mapping), (
                f"{HOOK_COVERAGE_MAP}: event {event.get('id')!r} declares a "
                f"hookDefinitions entry that is not an object: {entry!r}"
            )
            definitions.append((entry["tier"], entry["destination"]))
        instructions: list[_HookInstructionClaim] = []
        for entry in event.get("skillInstructions") or ():
            assert isinstance(entry, Mapping), (
                f"{HOOK_COVERAGE_MAP}: event {event.get('id')!r} declares a "
                f"skillInstructions entry that is not an object: {entry!r}"
            )
            instructions.append(
                _HookInstructionClaim(
                    marker=entry.get("marker", ""),
                    location=entry.get("location", ""),
                    advisory_only=bool(entry.get("advisoryOnly")),
                )
            )
        gap = event.get("parityGap")
        behaviors.append(
            _HookBehaviorClaim(
                event_id=event.get("id", ""),
                template_event=event.get("templateEvent", ""),
                script=event.get("script", ""),
                mechanism_type=mechanism.get("type", ""),
                trigger=mechanism.get("trigger"),
                can_block=bool(mechanism.get("canBlock")),
                blocking_required=bool(mechanism.get("blockingRequired")),
                declared_tiers=tuple(event.get("tiers") or ()),
                definitions=tuple(sorted(definitions)),
                instructions=tuple(instructions),
                parity_gap=gap if isinstance(gap, Mapping) else None,
            )
        )
    return tuple(behaviors)


def _hook_reach_commands(tree: PowerTree, definition: str) -> tuple[str, ...]:
    """Every `action.command` string one definition in `tree` carries.

    An absent, unreadable, or command-less definition yields nothing rather than
    raising: this asks what the Power delivers, and a definition that cannot be
    read delivers nothing. Whether it is *well formed* is Property 24's question.
    """
    if not tree.exists(definition):
        return ()
    try:
        document = tree.read_json(definition)
    except Unevaluable:
        return ()
    hooks = document.get("hooks") if isinstance(document, Mapping) else None
    if not isinstance(hooks, list):
        return ()
    commands: list[str] = []
    for hook in hooks:
        action = hook.get("action") if isinstance(hook, Mapping) else None
        command = action.get("command") if isinstance(action, Mapping) else None
        if isinstance(command, str):
            commands.append(command)
    return tuple(commands)


def _hook_reach_command_runs(command: str, script: str) -> bool:
    """Whether `command` runs `script` — the script as a path's last component.

    Matched with its leading separator, so `session-end.py` is not found inside
    `no-session-end.py`, and independently of whether the scripts directory is
    still the shipped placeholder or an installer-resolved absolute path.
    """
    return f"/{script}" in command or f"\\{script}" in command


def _hook_reach_prose_names(text: str, script: str) -> bool:
    """Whether an instruction document names `script` at all.

    Prose spells a script as a bare code span rather than as a path, so this is
    the looser test of the two — which is the right one for R10 AC5's "referenced
    by a declared skill-instruction location".
    """
    return script in text


def _hook_reach_text(tree: PowerTree, path: str) -> str | None:
    """`path`'s text, or `None` when the Power does not carry readable text there."""
    if not tree.exists(path):
        return None
    try:
        return tree.read_text(path)
    except Unevaluable:
        return None


def _hook_reach_delivery(
    tree: PowerTree, behavior: _HookBehaviorClaim
) -> frozenset[tuple[int, str]]:
    """Every `(tier, path)` by which `tree` really delivers `behavior`.

    Derived from the tree's contents, never from the map's `tiers` array: a
    declared tier is the claim under test. A definition counts when it is present
    and one of its commands runs the behavior's script; an instruction counts
    when its declared location is present and carries the behavior's marker.
    """
    delivered: set[tuple[int, str]] = set()
    for tier, destination in behavior.definitions:
        if any(
            _hook_reach_command_runs(command, behavior.script)
            for command in _hook_reach_commands(tree, destination)
        ):
            delivered.add((tier, destination))
    for claim in behavior.instructions:
        text = _hook_reach_text(tree, claim.location)
        if text is not None and claim.marker and claim.marker in text:
            delivered.add((_HOOK_REACH_TIER1, claim.location))
    return frozenset(delivered)


def _hook_reach_deliveries(
    tree: PowerTree, behaviors: Sequence[_HookBehaviorClaim]
) -> dict[str, frozenset[tuple[int, str]]]:
    return {
        behavior.event_id: _hook_reach_delivery(tree, behavior)
        for behavior in behaviors
    }


def _hook_reach_uncovered(
    deliveries: Mapping[str, frozenset[tuple[int, str]]]
) -> tuple[str, ...]:
    """The behaviors nothing delivers — R7 AC4's violation, dropped outright."""
    return tuple(sorted(event for event, paths in deliveries.items() if not paths))


def _hook_reach_tier3_alone(
    deliveries: Mapping[str, frozenset[tuple[int, str]]]
) -> tuple[str, ...]:
    """The behaviors delivered at Tier 3 and nowhere else — R7 AC12's violation."""
    return tuple(
        sorted(
            event
            for event, paths in deliveries.items()
            if paths
            and not {tier for tier, _ in paths} & _HOOK_REACH_DELIVERING_TIERS
        )
    )


def _hook_reach_without_tier3(files: Mapping[str, bytes]) -> PowerTree:
    """The Power as a client that ignores bundled hook definitions sees it (A1)."""
    prefix = f"{TIER3_HOOKS_DIRECTORY}/"
    return PowerTree.from_mapping(
        {
            path: content
            for path, content in files.items()
            if not path.startswith(prefix)
        }
    )


def _hook_reach_referrers(tree: PowerTree, location: str) -> tuple[str, ...]:
    """The declared referrers in `tree` that link to `location`.

    Resolved with the gate's Markdown reader, so a path mentioned in prose or
    shown inside a code fence does not count as pointing at the file.
    """
    declared = (_hook_reach_map().get("tier1Activation") or {}).get("expectedReferrers")
    assert isinstance(declared, list) and declared, (
        f"{HOOK_COVERAGE_MAP} declares no `tier1Activation.expectedReferrers`, so "
        "nothing says how a Bootcamper is brought to the Tier 1 instructions"
    )
    linking: list[str] = []
    for referrer in declared:
        text = _hook_reach_text(tree, referrer)
        if text is None:
            continue
        if any(
            reference.resolved == location
            for reference in markdown_references(text, source=referrer)
        ):
            linking.append(referrer)
    return tuple(sorted(linking))


def _hook_reach_marker_stripped(
    files: Mapping[str, bytes], behaviors: Sequence[_HookBehaviorClaim]
) -> dict[str, bytes]:
    """`files` with the markers of `behaviors` struck out, files left in place."""
    mutated = dict(files)
    for behavior in behaviors:
        for claim in behavior.instructions:
            if claim.location in mutated:
                text = mutated[claim.location].decode("utf-8")
                mutated[claim.location] = text.replace(claim.marker, "").encode("utf-8")
    return mutated


def _hook_reach_locations_deleted(
    files: Mapping[str, bytes], behaviors: Sequence[_HookBehaviorClaim]
) -> tuple[dict[str, bytes], frozenset[str]]:
    """`files` with the declared locations of `behaviors` removed, and which."""
    deleted = frozenset(
        claim.location for behavior in behaviors for claim in behavior.instructions
    )
    return (
        {path: content for path, content in files.items() if path not in deleted},
        deleted,
    )


def _hook_reach_reduced_to_tier3(
    files: Mapping[str, bytes], behaviors: Sequence[_HookBehaviorClaim]
) -> dict[str, bytes]:
    """`files` with `behaviors` left standing at Tier 3 alone.

    Markers struck and Tier 2 definitions removed, so what survives is exactly
    the delivery path R7 AC12 forbids a behavior to depend on.
    """
    mutated = _hook_reach_marker_stripped(files, behaviors)
    for behavior in behaviors:
        for tier, destination in behavior.definitions:
            if tier != _HOOK_REACH_TIER3:
                mutated.pop(destination, None)
    return mutated


def _hook_reach_removed(
    before: Mapping[str, frozenset[tuple[int, str]]],
    after: Mapping[str, frozenset[tuple[int, str]]],
) -> dict[str, list[tuple[int, str]]]:
    """Which delivery paths `after` lost, per behavior — the readable delta."""
    return {
        event: sorted(paths - after[event])
        for event, paths in before.items()
        if paths - after[event]
    }


def _hook_reach_less(
    deliveries: Mapping[str, frozenset[tuple[int, str]]],
    lost: Callable[[str, int, str], bool],
) -> dict[str, frozenset[tuple[int, str]]]:
    """`deliveries` with every `(tier, path)` `lost` accounts for removed.

    The prediction a mutated tree is measured against. Written as a filter over
    the baseline rather than as a second delivery walk, so agreement is two
    computations agreeing rather than one repeated.
    """
    return {
        event: frozenset(
            (tier, path) for tier, path in paths if not lost(event, tier, path)
        )
        for event, paths in deliveries.items()
    }


# Feature: senzing-bootcamp-power, Property 18: Every template hook behavior
# remains reachable
#
# Validates: Requirements 7.4, 7.5, 7.12, 7.13, 7.14, 10.5
@settings(max_examples=100)
@given(
    st.sets(st.sampled_from(_HOOK_REACH_EVENT_IDS), min_size=1),
    st.sets(st.sampled_from(_HOOK_REACH_EVENT_IDS), min_size=1),
    st.sampled_from(_HOOK_REACH_BREAKS),
)
def test_every_template_hook_behavior_remains_reachable(
    registered: set[str], broken: set[str], break_kind: str
) -> None:
    tree = _hook_reach_power()
    behaviors = _hook_reach_behaviors()
    by_id = {behavior.event_id: behavior for behavior in behaviors}

    # --- Clause 0: the registrations, and the markers that stand for them ---
    assert sorted(by_id) == sorted(_HOOK_REACH_REGISTRATIONS), (
        f"{HOOK_COVERAGE_MAP} declares registrations {sorted(by_id)}; the design's "
        f"parity table has {sorted(_HOOK_REACH_REGISTRATIONS)}"
    )
    for event_id, (template_event, script) in _HOOK_REACH_REGISTRATIONS.items():
        assert (by_id[event_id].template_event, by_id[event_id].script) == (
            template_event,
            script,
        ), (
            f"registration {event_id!r} maps template "
            f"{by_id[event_id].template_event!r} → {by_id[event_id].script!r}; the "
            f"parity table has {template_event!r} → {script!r}"
        )
    # A marker is what makes an instruction location a *behavior's* location, so
    # it has to be spelled in the shared vocabulary and claimed by one behavior.
    claimed: dict[str, str] = {}
    for behavior in behaviors:
        for claim in behavior.instructions:
            assert claim.marker.startswith(_HOOK_REACH_MARKER_PREFIX), (
                f"registration {behavior.event_id!r} declares marker "
                f"{claim.marker!r}, which does not carry the Tier 1 marker prefix "
                f"{_HOOK_REACH_MARKER_PREFIX!r}"
            )
            assert claim.marker not in claimed, (
                f"marker {claim.marker!r} is claimed by both "
                f"{claimed.get(claim.marker)!r} and {behavior.event_id!r}; a marker "
                "shared by two behaviors cannot say which one a file carries"
            )
            claimed[claim.marker] = behavior.event_id
    # And the locations events point at are the files the map declares as the
    # Tier 1 instruction set — a location outside it is a file nobody maintains.
    declared_files = _hook_reach_map().get("tier1InstructionFiles")
    assert isinstance(declared_files, list) and declared_files, (
        f"{HOOK_COVERAGE_MAP} declares no `tier1InstructionFiles`"
    )
    pointed_at = {
        claim.location for behavior in behaviors for claim in behavior.instructions
    }
    assert pointed_at == set(declared_files), (
        f"the registrations point at {sorted(pointed_at)}; "
        f"{HOOK_COVERAGE_MAP} declares the Tier 1 instruction set as "
        f"{sorted(declared_files)}"
    )

    # --- The delivery oracle, over the whole Power ---------------------------
    deliveries = _hook_reach_deliveries(tree, behaviors)
    assert registered <= set(by_id), registered

    # --- Clause 1 (R7 AC4): every drawn registration reaches Tier 1 ---------
    for event_id in sorted(registered):
        behavior = by_id[event_id]
        tier1 = {
            path
            for tier, path in deliveries[event_id]
            if tier == _HOOK_REACH_TIER1
        }
        assert tier1, (
            f"registration {event_id!r} has no Tier 1 delivery: none of its "
            f"declared locations {sorted(behavior.locations)} exists in the "
            "produced Power carrying its marker, so the behavior is absent with "
            "zero hook definitions installed"
        )
        # Not "at least one location works": *every* declared claim has to,
        # because each marker stands for a distinct statement of the behavior and
        # a claim the content does not keep is a rule the Bootcamper never gets.
        for claim in behavior.instructions:
            text = _hook_reach_text(tree, claim.location)
            assert text is not None, (
                f"registration {event_id!r} states its behavior at "
                f"{claim.location}, which the produced Power does not carry as "
                "readable text"
            )
            assert text.count(claim.marker) == 1, (
                f"registration {event_id!r} declares marker {claim.marker!r} at "
                f"{claim.location}, which carries it {text.count(claim.marker)} "
                "times; exactly one occurrence is what makes the declaration point "
                "at one statement of the behavior"
            )
            # And the marker locates the behavior: no other declared instruction
            # file carries it, so the declaration names where the rule lives.
            elsewhere = tuple(
                sorted(
                    other
                    for other in pointed_at - {claim.location}
                    if claim.marker in (_hook_reach_text(tree, other) or "")
                )
            )
            assert elsewhere == (), (
                f"marker {claim.marker!r} is declared at {claim.location} and also "
                f"appears in {elsewhere}"
            )
        assert tier1 == behavior.locations, (
            f"registration {event_id!r} declares its behavior at "
            f"{sorted(behavior.locations)} and is delivered from {sorted(tier1)}"
        )
        assert _HOOK_REACH_TIER1 in behavior.declared_tiers, (
            f"registration {event_id!r} is delivered at Tier 1 but does not "
            f"declare it; declared tiers are {behavior.declared_tiers}"
        )

    # --- Clause 2 (R7 AC5, AC13): a trigger ships a definition, and only then -
    for event_id in sorted(registered):
        behavior = by_id[event_id]
        tier2 = {
            path
            for tier, path in deliveries[event_id]
            if tier == _HOOK_REACH_TIER2
        }
        tier3 = {
            path
            for tier, path in deliveries[event_id]
            if tier == _HOOK_REACH_TIER3
        }
        if behavior.mechanism_type == _HOOK_REACH_MECHANISM_TRIGGER:
            assert tier2, (
                f"registration {event_id!r} has Kiro trigger {behavior.trigger!r} "
                "and no Tier 2 delivery: no definition in "
                f"{HOOK_ASSETS_DIRECTORY} runs {behavior.script!r}, so consenting "
                "to the install would restore nothing"
            )
            assert tier3, (
                f"registration {event_id!r} ships a Tier 2 definition and no Tier 3 "
                f"copy under {TIER3_HOOKS_DIRECTORY}/ (R7 AC12)"
            )
            assert all(path.startswith(f"{HOOK_ASSETS_DIRECTORY}/") for path in tier2)
            assert all(path.startswith(f"{TIER3_HOOKS_DIRECTORY}/") for path in tier3)
        else:
            assert behavior.mechanism_type == _HOOK_REACH_MECHANISM_NONE, (
                f"registration {event_id!r} declares mechanism type "
                f"{behavior.mechanism_type!r}"
            )
            assert behavior.trigger is None
            assert not tier2 and not tier3, (
                f"registration {event_id!r} has no Kiro trigger, so nothing would "
                f"fire a definition; the Power delivers it at {sorted(tier2 | tier3)}"
            )
            assert behavior.declared_tiers == (_HOOK_REACH_TIER1,)

    # --- Clause 3 (R7 AC12): Tier 3 is never a behavior's only path ---------
    assert _hook_reach_tier3_alone(deliveries) == ()
    assert _hook_reach_uncovered(deliveries) == ()
    # The same claim the way A1 makes it real: with the bundled directory gone,
    # every behavior is still delivered. Asserted to be a non-empty deletion, so
    # a Power that stopped shipping Tier 3 cannot pass this vacuously.
    bundled = [
        path
        for path in _base_power().power
        if path.startswith(f"{TIER3_HOOKS_DIRECTORY}/")
    ]
    assert bundled, f"the produced Power bundles nothing under {TIER3_HOOKS_DIRECTORY}/"
    without_tier3 = _hook_reach_without_tier3(_base_power().power)
    surviving = _hook_reach_deliveries(without_tier3, behaviors)
    assert _hook_reach_uncovered(surviving) == (), (
        f"with {TIER3_HOOKS_DIRECTORY}/ ignored, "
        f"{_hook_reach_uncovered(surviving)} reach the Bootcamper by no path at all"
    )
    for event_id in sorted(registered):
        assert surviving[event_id] == {
            (tier, path)
            for tier, path in deliveries[event_id]
            if tier != _HOOK_REACH_TIER3
        }

    # --- Clause 4 (R7 AC13, AC14): partial parity is advisory and documented -
    for event_id in sorted(registered):
        behavior = by_id[event_id]
        if behavior.mechanism_type == _HOOK_REACH_MECHANISM_NONE:
            owed = _HOOK_REACH_GAP_NO_TRIGGER
        elif behavior.blocking_required and not behavior.can_block:
            owed = _HOOK_REACH_GAP_NO_BLOCKING
        else:
            continue
        gap = behavior.parity_gap
        assert gap is not None, (
            f"registration {event_id!r} has partial parity and documents no gap; "
            f"requirement {owed} asks for the behavior to be advisory *and* the "
            "gap recorded"
        )
        assert gap.get("requirement") == owed, (
            f"registration {event_id!r}'s gap cites requirement "
            f"{gap.get('requirement')!r}; the gap it has is {owed}'s"
        )
        assert str(gap.get("description", "")).strip(), (
            f"registration {event_id!r}'s parity gap carries no description"
        )
        assert str(gap.get("mitigation", "")).strip(), (
            f"registration {event_id!r}'s parity gap carries no mitigation, so "
            "nothing says what the Bootcamper receives instead"
        )
        assert all(claim.advisory_only for claim in behavior.instructions), (
            f"registration {event_id!r} cannot be enforced, so every Tier 1 "
            "instruction carrying it must be declared advisory"
        )

    # --- Clause 5 (R10 AC5): every hook script is still referenced ----------
    for event_id in sorted(registered):
        behavior = by_id[event_id]
        by_command = tuple(
            sorted(
                destination
                for _, destination in behavior.definitions
                if any(
                    _hook_reach_command_runs(command, behavior.script)
                    for command in _hook_reach_commands(tree, destination)
                )
            )
        )
        by_instruction = tuple(
            sorted(
                claim.location
                for claim in behavior.instructions
                if _hook_reach_prose_names(
                    _hook_reach_text(tree, claim.location) or "", behavior.script
                )
            )
        )
        assert by_command or by_instruction, (
            f"{behavior.script!r} was invoked by template hook "
            f"{behavior.template_event!r} and is named by no generated hook "
            "command and no declared instruction location, so the rewiring "
            "dropped it"
        )
        if behavior.mechanism_type == _HOOK_REACH_MECHANISM_NONE:
            assert by_instruction, (
                f"{behavior.script!r} has no Kiro trigger, so an instruction "
                "location is the only place it can be reached from"
            )

    # --- Clause 6 (R7 AC4): the instruction files are pointed at ------------
    for event_id in sorted(registered):
        for location in sorted(by_id[event_id].locations):
            assert _hook_reach_referrers(tree, location), (
                f"nothing in the produced Power links to {location}, so the Tier 1 "
                f"delivery of {event_id!r} depends on a file the Bootcamper is "
                "never brought to"
            )

    # --- Clause 7: the counterfactuals, so none of the above is vacuous -----
    hurt = tuple(by_id[event_id] for event_id in sorted(broken))
    if break_kind == _HOOK_REACH_DROP_MARKER:
        mutated = _hook_reach_marker_stripped(_base_power().power, hurt)
        predicted = _hook_reach_less(
            deliveries,
            lambda event, tier, _path: event in broken and tier == _HOOK_REACH_TIER1,
        )
    elif break_kind == _HOOK_REACH_DELETE_LOCATION:
        mutated, deleted = _hook_reach_locations_deleted(_base_power().power, hurt)
        predicted = _hook_reach_less(
            deliveries,
            lambda _event, tier, path: tier == _HOOK_REACH_TIER1 and path in deleted,
        )
    else:
        assert break_kind == _HOOK_REACH_TIER3_ONLY, break_kind
        mutated = _hook_reach_reduced_to_tier3(_base_power().power, hurt)
        predicted = _hook_reach_less(
            deliveries,
            lambda event, tier, _path: event in broken and tier != _HOOK_REACH_TIER3,
        )

    broken_deliveries = _hook_reach_deliveries(
        PowerTree.from_mapping(mutated), behaviors
    )
    assert broken_deliveries == predicted, (
        f"breaking {sorted(broken)} with {break_kind!r} was expected to remove "
        f"{_hook_reach_removed(deliveries, predicted)} and removed "
        f"{_hook_reach_removed(deliveries, broken_deliveries)}"
    )
    # The break has to *land*: every behavior aimed at loses the tiers it was
    # aimed at, and the two report oracles name exactly who is left where.
    for event_id in sorted(broken):
        assert not {
            tier
            for tier, _ in broken_deliveries[event_id]
            if tier == _HOOK_REACH_TIER1
        }, f"{break_kind!r} left {event_id!r} with a Tier 1 delivery"
        if break_kind == _HOOK_REACH_TIER3_ONLY:
            assert not broken_deliveries[event_id] & {
                (tier, path)
                for tier, path in deliveries[event_id]
                if tier != _HOOK_REACH_TIER3
            }
    assert set(_hook_reach_uncovered(broken_deliveries)) == {
        event for event, paths in predicted.items() if not paths
    }
    assert set(_hook_reach_tier3_alone(broken_deliveries)) == {
        event
        for event, paths in predicted.items()
        if paths and not {tier for tier, _ in paths} & _HOOK_REACH_DELIVERING_TIERS
    }
    if break_kind == _HOOK_REACH_TIER3_ONLY:
        # R7 AC12's own counterfactual: a behavior that still ships, in the one
        # directory that may never be read, is a behavior the oracle must name.
        stranded = {
            behavior.event_id
            for behavior in hurt
            if any(tier == _HOOK_REACH_TIER3 for tier, _ in deliveries[behavior.event_id])
        }
        assert set(_hook_reach_tier3_alone(broken_deliveries)) == stranded
        assert set(_hook_reach_uncovered(broken_deliveries)) == set(broken) - stranded


# ===========================================================================
# Property 19: A statement matches at most one command trigger phrase
# ===========================================================================
#
# Kiro decides which skill a statement activates, and that decision is not ours
# to test: 100 generated examples would buy 100 manual sessions, which is why the
# design sends real activation to Test_Checklist step 6. What *is* ours is the
# thing the decision is made from — three authored descriptions, each declaring
# one trigger phrase — and the claim R9 rests on is a lexical one about those
# three strings: whatever a Bootcamper says, at most one of them can be the
# phrase it carries *(R9 AC3)*, and a statement carrying none carries none
# *(R9 AC5)*.
#
# So the subject here is the authored `kiro-owned` corpus plus the gate's own
# `declared_trigger_phrase`, and the phrases are **read out of the shipped
# frontmatter** rather than spelled in Python. A phrase written here would be a
# phrase no skill declares, and it could drift from the authored one without
# either copy looking wrong on its own.
#
# The model, and why it is deliberately generous
# ----------------------------------------------
# A statement activates a skill when the skill's declared phrase occurs in the
# statement as a run of spoken words — `_activated`, matching on a whitespace-
# collapsed, casefolded word window, so `"Hey Kiro, start the senzing bootcamp
# now"` reaches the same skill the bare phrase does. Beside it runs a second,
# strictly looser construction, `_lexical_matches`, which ignores word boundaries
# entirely. Both are asserted to activate at most one skill, and the loose one is
# asserted to be a superset of the model: the at-most-one guarantee has to
# survive a client that matches more freely than we would, because how freely
# Kiro matches is not something this repository gets to choose.
#
# What the clauses are
# --------------------
# * **R9 AC2** — each command-derived description declares *exactly one* phrase:
#   one quoted span, that span being the phrase `declared_trigger_phrase` reads,
#   and no sibling's phrase anywhere else in the description. A description
#   carrying two phrases is a skill two different statements activate, which is
#   the same defect as two skills sharing one phrase seen from the other side.
# * **R9 AC3** — no declared phrase is a substring of another, which is what
#   makes at-most-one hold for every statement rather than for the ones tested.
# * **R9 AC5** — the near-miss and overlapping-fragment draws, the empty
#   statement, and the enforcement-setup skill's own phrase all activate nothing.
#   The last one is the case that matters most: `bootcamp-enforcement-setup` is
#   authored in this repository, declares a phrase, and is *not* command-derived,
#   so its phrase is a real statement a Bootcamper will make that must leave all
#   three command skills alone.
#
# Non-vacuous, by counterfactual
# ------------------------------
# "At most one" is the kind of claim that passes when nothing matches at all, so
# the exact, embedded, and title-cased draws are each asserted to activate
# *exactly* one, and that one to be the skill whose phrase they carry. And
# because the disjointness clause would also pass against a matcher that never
# reports a collision, two hypothetical fourth skills are folded in and the
# collision is required to appear — one phrase a substring of all three authored
# ones (`"senzing bootcamp"`), one phrase containing an authored one. In both
# directions the containment oracle names exactly the offending pairs and the
# statement now activates two skills, so the passing case above is a fact about
# the authored phrases rather than about the matcher.
#
# Deliberately out of scope: whether a description is well formed at all is
# Property 13's, whether the three command skills correspond one-to-one with the
# template's commands is Property 16's, and whether Kiro activates on any of this
# is checklist steps 6 and 7's.

#: Where a `kiro-owned` skill records the template command it stands for. A
#: skill declaring one is command-derived and answers to R9; a skill declaring
#: none — `bootcamp-enforcement-setup` — is a client adaptation and does not.
_COMMAND_DECLARATION = TEMPLATE_COMMAND_FIELD

#: A quoted span, straight or curly. The lookarounds keep a possessive
#: apostrophe (`the bootcamp's hooks`) from opening one, which is the only way
#: authored prose could otherwise be read as declaring a phrase. Written here
#: rather than imported: this is the oracle the gate's reader is checked against.
_QUOTED_SPAN = re.compile(
    r"(?<!\w)[\"\u201c](?P<double>[^\"\u201d]+)[\"\u201d](?!\w)"
    r"|(?<!\w)['\u2018](?P<single>[^'\u2019]+)['\u2019](?!\w)"
)

#: The counterfactual phrases, and the hypothetical skills that declare them.
#: The first is a substring of every authored phrase; the second is built in the
#: test around a drawn one, so it contains an authored phrase instead.
_OVERLAP_FRAGMENT = "senzing bootcamp"
_OVERLAP_SKILL = "hypothetical-fragment-skill"
_SUPERSTRING_SKILL = "hypothetical-superstring-skill"


def _normalized(text: str) -> str:
    """`text` as a client would compare it: casefolded, whitespace collapsed."""
    return " ".join(text.split()).casefold()


def _spoken_words(text: str) -> tuple[str, ...]:
    return tuple(_normalized(text).split(" ")) if _normalized(text) else ()


def _phrase_is_spoken(statement: str, phrase: str) -> bool:
    """Whether `phrase` occurs in `statement` as a contiguous run of words."""
    spoken = _spoken_words(statement)
    wanted = _spoken_words(phrase)
    if not wanted or len(wanted) > len(spoken):
        return False
    return any(
        spoken[start : start + len(wanted)] == wanted
        for start in range(len(spoken) - len(wanted) + 1)
    )


def _activated(statement: str, phrases: Mapping[str, str]) -> tuple[str, ...]:
    """The skills `statement` activates under the word-window model."""
    return tuple(
        sorted(
            skill
            for skill, phrase in phrases.items()
            if _phrase_is_spoken(statement, phrase)
        )
    )


def _lexical_matches(statement: str, phrases: Mapping[str, str]) -> tuple[str, ...]:
    """The skills a looser, word-boundary-blind matcher would reach."""
    normalized = _normalized(statement)
    return tuple(
        sorted(
            skill
            for skill, phrase in phrases.items()
            if _normalized(phrase) and _normalized(phrase) in normalized
        )
    )


def _containment_pairs(
    phrases: Mapping[str, str]
) -> tuple[tuple[str, str], ...]:
    """`(inner, outer)` for every phrase that is a substring of another's.

    R9 AC3 read as the lexical condition it is: an empty result is the guarantee
    that no statement can carry two declared phrases by carrying one.
    """
    return tuple(
        sorted(
            (inner, outer)
            for inner, outer in itertools.permutations(sorted(phrases), 2)
            if _normalized(phrases[inner]) in _normalized(phrases[outer])
        )
    )


def _quoted_spans(text: str) -> tuple[str, ...]:
    """Every quoted span in `text`, in order — the declarations it makes."""
    spans = []
    for match in _QUOTED_SPAN.finditer(text):
        span = (match.group("double") or match.group("single") or "").strip()
        if span:
            spans.append(span)
    return tuple(spans)


@lru_cache(maxsize=1)
def _authored_kiro_owned_skills() -> tuple[tuple[str, str, str | None], ...]:
    """`(skill, description, declared template command)` per authored skill.

    Read from `templates/kiro-owned/skills/*/SKILL.md`, which is where the
    command-derived skills are authored: `powers/senzing-bootcamp/` is generated
    output, and the engine materializes these files into it verbatim.
    """
    authored: list[tuple[str, str, str | None]] = []
    for path in sorted(KIRO_OWNED_ROOT.glob(f"skills/*/{SKILL_MANIFEST}")):
        fields = _frontmatter_fields(path.read_text(encoding="utf-8"))
        assert fields is not None, f"{path} carries no frontmatter block"
        description = fields.get("description")
        assert isinstance(description, str) and description.strip(), (
            f"{path} declares no description, so it declares no trigger phrase"
        )
        metadata = fields.get(SKILL_METADATA_FIELD)
        command = (
            metadata.get(_COMMAND_DECLARATION)
            if isinstance(metadata, Mapping)
            else None
        )
        authored.append(
            (
                path.parent.name,
                description,
                command if isinstance(command, str) and command else None,
            )
        )
    assert authored, f"{KIRO_OWNED_ROOT}/skills/ authors no SKILL.md"
    return tuple(authored)


def _authored_descriptions() -> Mapping[str, str]:
    return {
        skill: description
        for skill, description, _ in _authored_kiro_owned_skills()
    }


def _authored_command_phrases() -> Mapping[str, str]:
    """The phrase each command-derived skill declares, read off its description."""
    phrases: dict[str, str] = {}
    for skill, description, command in _authored_kiro_owned_skills():
        if command is None:
            continue
        phrase = declared_trigger_phrase(description)
        assert phrase, (
            f"{KIRO_OWNED_ROOT}/skills/{skill}: the description declares no "
            f"trigger phrase, so R9 AC2 has nothing to be exactly one of: "
            f"{description!r}"
        )
        phrases[skill] = phrase
    return phrases


def _authored_sibling_phrases() -> Mapping[str, str]:
    """The phrases the authored skills that are *not* command-derived declare."""
    phrases: dict[str, str] = {}
    for skill, description, command in _authored_kiro_owned_skills():
        if command is not None:
            continue
        phrase = declared_trigger_phrase(description)
        if phrase:
            phrases[skill] = phrase
    return phrases


# Feature: senzing-bootcamp-power, Property 19: A statement matches at most one
# command trigger phrase
#
# Validates: Requirements 9.2, 9.3, 9.5
@settings(max_examples=100)
@given(
    statement(),
    STATEMENT_CASES["exact_phrase"],
    STATEMENT_CASES["phrase_in_longer_text"],
    STATEMENT_CASES["case_variant"],
    STATEMENT_CASES["overlapping_fragments"],
    STATEMENT_CASES["near_miss"],
    STATEMENT_CASES["unrelated"],
)
def test_a_statement_matches_at_most_one_command_trigger_phrase(
    spoken: str,
    exact: str,
    embedded: str,
    title_cased: str,
    fragment: str,
    near_miss: str,
    unrelated: str,
) -> None:
    # The generator cases R9 turns on, asserted rather than assumed: the shapes
    # a phrase can be spoken in — and the shapes that only look like one — are
    # drawn, not written into this test.
    assert {
        "exact_phrase",
        "phrase_in_longer_text",
        "case_variant",
        "overlapping_fragments",
        "near_miss",
        "unrelated",
    } <= set(STATEMENT_CASES)

    # --- The declarations, read off the authored skills ---------------------
    phrases = _authored_command_phrases()
    assert sorted(phrases) == sorted(COMMAND_DERIVED_SKILLS), (
        f"{KIRO_OWNED_ROOT}/skills/ authors the command-derived skills "
        f"{sorted(phrases)}; R9 AC1's three are {sorted(COMMAND_DERIVED_SKILLS)}"
    )
    # The drawn statements are built from the generator's phrases, so they bear
    # on the authored artifact only while the two agree.
    assert phrases == dict(TRIGGER_PHRASES), (
        "the authored descriptions declare "
        f"{phrases}, and `statement()` speaks {dict(TRIGGER_PHRASES)}; the "
        "statements would otherwise be aimed at phrases no skill declares"
    )
    siblings = _authored_sibling_phrases()
    assert siblings, (
        f"{KIRO_OWNED_ROOT}/skills/ authors no non-command skill with a declared "
        "phrase, so R9 AC5's no-match case has no authored statement to be made "
        "of"
    )
    assert not set(siblings) & set(phrases)

    # --- Clause 1 (R9 AC2): exactly one phrase per description -------------
    descriptions = _authored_descriptions()
    for skill, phrase in phrases.items():
        description = descriptions[skill]
        assert _quoted_spans(description) == (phrase,), (
            f"{KIRO_OWNED_ROOT}/skills/{skill}: the description declares "
            f"{_quoted_spans(description)}; R9 AC2 allows exactly one phrase, "
            f"and the gate reads it as {phrase!r}"
        )
        assert declared_trigger_phrase(description) == phrase
        # And the description carries no *other* skill's phrase, in the clause
        # or out of it: the whole description is the activation surface.
        assert _lexical_matches(description, phrases) == (skill,), (
            f"{KIRO_OWNED_ROOT}/skills/{skill}: its description carries the "
            f"phrases of {_lexical_matches(description, phrases)}"
        )
    for skill, phrase in siblings.items():
        assert _lexical_matches(descriptions[skill], phrases) == (), (
            f"{KIRO_OWNED_ROOT}/skills/{skill} is not command-derived, yet its "
            "description carries a command-derived phrase"
        )
        assert phrase not in phrases.values()

    # --- Clause 2 (R9 AC3): no phrase is a substring of another -------------
    assert _containment_pairs(phrases) == ()

    # --- Clause 3 (R9 AC3): the drawn statement activates at most one -------
    activated = _activated(spoken, phrases)
    lexical = _lexical_matches(spoken, phrases)
    assert len(activated) <= 1, (
        f"{spoken!r} activates {activated}; R9 AC3 allows at most one"
    )
    # The same bound under a matcher that ignores word boundaries, which is the
    # bound lexical disjointness actually buys — and it can only reach more.
    assert len(lexical) <= 1, f"{spoken!r} matches {lexical} lexically"
    assert set(activated) <= set(lexical)

    # --- Clause 4: a phrase that is spoken activates exactly its own skill --
    for said in (exact, embedded, title_cased):
        matched = _activated(said, phrases)
        assert len(matched) == 1, (
            f"{said!r} carries a declared phrase and activates {matched}"
        )
        assert _phrase_is_spoken(said, phrases[matched[0]])
        assert _normalized(phrases[matched[0]]) in _normalized(said)

    # --- Clause 5 (R9 AC5): a statement carrying no phrase activates none ---
    for quiet in (fragment, near_miss, unrelated, "", *siblings.values()):
        assert _activated(quiet, phrases) == (), (
            f"{quiet!r} carries no declared trigger phrase, yet activates "
            f"{_activated(quiet, phrases)}"
        )
        assert _lexical_matches(quiet, phrases) == ()

    # --- Clause 6: the counterfactuals, so none of the above is vacuous ----
    # A fourth phrase that is a substring of all three authored ones: the
    # containment oracle names every pair, and the statement that activated one
    # skill now activates two.
    assert all(
        _OVERLAP_FRAGMENT in _normalized(phrase) for phrase in phrases.values()
    )
    assert _OVERLAP_SKILL not in phrases
    overlapping = {**phrases, _OVERLAP_SKILL: _OVERLAP_FRAGMENT}
    assert _containment_pairs(overlapping) == tuple(
        sorted((_OVERLAP_SKILL, skill) for skill in phrases)
    )
    assert len(_activated(exact, overlapping)) == 2
    assert _OVERLAP_SKILL in _activated(exact, overlapping)

    # And the other direction: a fourth phrase that *contains* an authored one.
    said_skill = _activated(exact, phrases)[0]
    superstring = {
        **phrases,
        _SUPERSTRING_SKILL: f"kindly {phrases[said_skill]} right now",
    }
    assert _containment_pairs(superstring) == ((said_skill, _SUPERSTRING_SKILL),)
    assert _activated(superstring[_SUPERSTRING_SKILL], superstring) == tuple(
        sorted((said_skill, _SUPERSTRING_SKILL))
    )


# ===========================================================================
# Property 20: Reconciliation classifies every path exactly once
# ===========================================================================
#
# An update owes one answer per path: which side moved? A two-way diff cannot
# give it — it sees that the Power and the fresh transform disagree and cannot
# say whether a Maintainer edited the file or the template did — so the
# Reconciler compares *both* against the same baseline, the hashes the last
# successful build recorded. The verdict is then a total function of three
# hashes plus the recorded owner, and this property is the claim that the
# function is total, single-valued, and the one the design's classification
# table describes.
#
# Three clauses, one property, because they are one statement: every path lands
# in exactly one bucket, the bucket is the table's, and a conflict names both
# sides.
#
# (a) Exactly once, over the union of the three inputs
# ---------------------------------------------------
# The domain is the union of the previous manifest, the on-disk Power, and the
# staging tree — not the intersection, and not the staging tree alone, because a
# path the transform stopped producing and a path only the Power carries are
# exactly the cases an update has to speak about *(R5 AC4)*. Membership is
# checked as a partition rather than as six independent lookups: the six bucket
# lists are concatenated, and the result has to contain every path in the union
# and no path twice. "At most one" and "at least one" fail differently — a
# double-listed path gives a Maintainer two contradictory verdicts, an unlisted
# one gives none — so both are asserted, in the model and again in the JSON
# document the Update_Skill presents.
#
# `.build-manifest.json` is the one path deliberately outside the domain: it
# records a build rather than being part of one, and it cannot record its own
# hash. So it is planted in all three inputs, with different content in each,
# and asserted to be classified nowhere *and* to perturb nothing else.
#
# (b) The bucket is the table's, read two independent ways
# ------------------------------------------------------
# The oracle is deliberately a different *construction* from the classifier it
# checks. The implementation is a chain of comparisons; the oracle is a lookup
# table keyed by **content shape** — one symbol per input, `-` for absence and
# A/B/C naming content classes in order of first appearance. `("A", "B", "A")`
# is "the last build wrote A, a local edit made it B, the new transform still
# produces A", which is the design table's third row. Fourteen shapes exist,
# they are enumerated here independently, and the table is asserted total over
# exactly that set — so a row nobody wrote is a failure rather than a `KeyError`
# waiting for the draw that finds it.
#
# The second reading comes from the generator. `reconcile_triple()` labels each
# path with *how it was constructed* — `local-edit-and-upstream-change`, say —
# and mapping a construction to a bucket is the design's table again, from the
# other direction: the first reading derives the bucket from hashes the
# classifier also saw, and this one from an intent the classifier never sees.
# Both have to agree with the verdict.
#
# The generator draws the seven constructions its intents name, which reach nine
# of the fourteen rows and none of the declared `owner: kiro` row. The remainder
# — a file deleted locally, a file edited locally and dropped upstream, a file
# present in the Power that no build produced — is seeded, one path per row and
# per owner, so every row is driven on every example rather than when a draw
# happens to produce it. Coverage is then asserted, not hoped for: every bucket,
# every action, every preservation reason, and every shape is reached.
#
# (c) A conflict names both sides, and nothing local is overwritten
# ---------------------------------------------------------------
# R5 AC6 asks for two things at once: retain the adaptation, and identify both
# it and the conflicting template change. The identification is checked by hash
# prefix rather than by wording — each side's description has to name the
# version of the file it is about, so a report that said "conflict" twice with
# the same sentence would fail — and the retention is checked as the rule the
# module exists to keep: **a locally divergent file is never overwritten and
# never deleted**. Staging is taken only where the local file is absent, already
# identical, or unmoved since the last build; a removal only where the local
# state is the build's own. That single assertion covers R5 AC5 and AC6 together
# and is what makes the classification safe to act on.

#: The release pair a reconciliation runs between. Classification never reads
#: either one — asserted below by driving the same three inputs with an
#: overridden `from_release` and comparing the classifications — so any tags
#: serve, and the design's own example pair is used.
_PREVIOUS_RELEASE = "0.5.0"
_TO_RELEASE = "0.5.1"

#: A tag `semver_tag()` cannot draw (its major stops at 12), so the explicit
#: `from_release` override is always a different string from the one the drawn
#: manifest records. Asserted distinct in the test rather than trusted.
_OVERRIDE_RELEASE = "13.0.0"

#: Absence, and the content classes a shape distinguishes. Three inputs, so
#: three classes are enough to name every way they can agree or differ.
_ABSENT = "-"
_CONTENT_LABELS = ("A", "B", "C")

#: One symbol per input: previous, on-disk, staging.
_Shape = tuple[str, str, str]

#: What a classification amounts to: a bucket, the action it carries, and the
#: reason a preserved adaptation was preserved (`None` for the other buckets).
_Verdict = tuple[str, str, str | None]

#: The `reconcile_triple()` cases this property relies on, so a generator change
#: that dropped one fails here instead of quietly narrowing the property.
_REQUIRED_TRIPLE_CASES = frozenset(
    {
        "all_intents",
        "divergence_combinations",
        "additions",
        "removals",
        "kiro_owned",
        "empty",
        "mixed",
    }
)

#: The design's classification table, plus the rows it leaves implicit, keyed by
#: content shape. Written as a table rather than as a chain of comparisons so
#: the oracle is a different construction from the classifier it checks.
_CLASSIFICATION_TABLE: Mapping[_Shape, _Verdict] = {
    # The four divergence rows, verbatim from the design's table.
    ("A", "A", "A"): (BUCKET_UNCHANGED, ACTION_KEEP, None),
    ("A", "A", "B"): (BUCKET_MODIFIED, ACTION_TAKE_STAGING, None),
    ("A", "B", "A"): (BUCKET_PRESERVED, ACTION_KEEP_ON_DISK, REASON_LOCAL_EDIT),
    ("A", "B", "C"): (BUCKET_CONFLICTS, ACTION_KEEP_ON_DISK, None),
    # A local edit and an upstream change that happen to agree is still both
    # sides having moved, so it is still a conflict: the baseline is what each
    # side is compared against, never the other side.
    ("A", "B", "B"): (BUCKET_CONFLICTS, ACTION_KEEP_ON_DISK, None),
    # The two presence rows: absent from the baseline, or dropped upstream.
    ("-", "-", "A"): (BUCKET_ADDED, ACTION_TAKE_STAGING, None),
    ("A", "A", "-"): (BUCKET_REMOVED, ACTION_REMOVE, None),
    # Deleted locally, still produced upstream. The deletion *is* the local
    # divergence, so the same two rows apply as for an edit.
    ("A", "-", "A"): (BUCKET_PRESERVED, ACTION_KEEP_ON_DISK, REASON_LOCAL_DELETE),
    ("A", "-", "B"): (BUCKET_CONFLICTS, ACTION_KEEP_ON_DISK, None),
    # Deleted locally and dropped upstream: both sides agree it is gone.
    ("A", "-", "-"): (BUCKET_REMOVED, ACTION_REMOVE, None),
    # Edited locally, dropped upstream. An upstream removal is an upstream
    # change, so R5 AC6 applies rather than the plain removal row.
    ("A", "B", "-"): (BUCKET_CONFLICTS, ACTION_KEEP_ON_DISK, None),
    # Present in the Power, absent from the manifest: nothing the engine
    # produced, so there is no baseline and only presence can be read.
    ("-", "A", "-"): (BUCKET_PRESERVED, ACTION_KEEP_ON_DISK, REASON_LOCAL_ONLY),
    ("-", "A", "A"): (BUCKET_ADDED, ACTION_TAKE_STAGING, None),
    ("-", "A", "B"): (BUCKET_CONFLICTS, ACTION_KEEP_ON_DISK, None),
}

#: Which action each bucket carries. The buckets say what happened, the actions
#: say what the update does about it, and a bucket never carries two actions —
#: which is what lets a Maintainer read the report as a plan.
_BUCKET_ACTIONS: Mapping[str, str] = {
    BUCKET_ADDED: ACTION_TAKE_STAGING,
    BUCKET_MODIFIED: ACTION_TAKE_STAGING,
    BUCKET_REMOVED: ACTION_REMOVE,
    BUCKET_UNCHANGED: ACTION_KEEP,
    BUCKET_PRESERVED: ACTION_KEEP_ON_DISK,
    BUCKET_CONFLICTS: ACTION_KEEP_ON_DISK,
}

#: Why a path is a preserved adaptation: declared by the contract, or detected
#: as a local edit, a local-only file, or a local deletion *(R5 AC5)*.
_PRESERVATION_REASONS = frozenset(
    {
        REASON_KIRO_OWNED,
        REASON_LOCAL_EDIT,
        REASON_LOCAL_ONLY,
        REASON_LOCAL_DELETE,
    }
)

#: How the generator's construction labels map to the design's buckets. This is
#: the second, independent reading of the table: it is derived from how a path
#: was built, which the classifier never sees, rather than from its hashes.
_INTENT_VERDICTS: Mapping[str, _Verdict] = {
    "unchanged": (BUCKET_UNCHANGED, ACTION_KEEP, None),
    "upstream-change": (BUCKET_MODIFIED, ACTION_TAKE_STAGING, None),
    "local-edit-only": (
        BUCKET_PRESERVED,
        ACTION_KEEP_ON_DISK,
        REASON_LOCAL_EDIT,
    ),
    "local-edit-and-upstream-change": (
        BUCKET_CONFLICTS,
        ACTION_KEEP_ON_DISK,
        None,
    ),
    "added": (BUCKET_ADDED, ACTION_TAKE_STAGING, None),
    "removed": (BUCKET_REMOVED, ACTION_REMOVE, None),
    "kiro-owned": (BUCKET_PRESERVED, ACTION_KEEP_ON_DISK, REASON_KIRO_OWNED),
}

#: How much of a hash counts as identifying a version of a file. The report
#: quotes a longer prefix; eight hex characters is the shortest a Maintainer
#: greps with, so requiring that much tests the identification without pinning
#: the report's wording to a length.
_IDENTIFYING_PREFIX = 8


def _canonically_labeled(labels: Sequence[str]) -> bool:
    """Whether content classes appear in order: A before B before C."""
    seen: list[str] = []
    for label in labels:
        if label in seen:
            continue
        if label != _CONTENT_LABELS[len(seen)]:
            return False
        seen.append(label)
    return True


@lru_cache(maxsize=None)
def _canonical_shapes() -> tuple[_Shape, ...]:
    """Every content shape three inputs can take, enumerated independently.

    At least one input present, with content classes labeled canonically, so two
    shapes differing only in the names of their classes are one shape. The
    classification table is asserted total over exactly this set, which is what
    makes "every path is classified" a claim about all inputs rather than about
    the ones a draw produced.
    """
    shapes: set[_Shape] = set()
    for presence in itertools.product((False, True), repeat=3):
        if not any(presence):
            continue
        slots = [index for index, present in enumerate(presence) if present]
        for labels in itertools.product(_CONTENT_LABELS, repeat=len(slots)):
            if not _canonically_labeled(labels):
                continue
            shape = [_ABSENT, _ABSENT, _ABSENT]
            for index, label in zip(slots, labels):
                shape[index] = label
            shapes.add((shape[0], shape[1], shape[2]))
    return tuple(sorted(shapes))


def _shape(
    previous: str | None, on_disk: str | None, staging: str | None
) -> _Shape:
    """The content shape of three hashes, `None` meaning absent."""
    labels: dict[str, str] = {}
    symbols: list[str] = []
    for digest in (previous, on_disk, staging):
        if digest is None:
            symbols.append(_ABSENT)
            continue
        if digest not in labels:
            labels[digest] = _CONTENT_LABELS[len(labels)]
        symbols.append(labels[digest])
    return (symbols[0], symbols[1], symbols[2])


def _declared_verdict(shape: _Shape) -> _Verdict:
    """The `owner: kiro` row, which precedes every content comparison.

    A declared adaptation is preserved because the contract says so, whatever
    its bytes did *(R5 AC5)*. With nothing on disk to keep there is nothing to
    preserve, so presence alone decides: the authored content is being
    materialized, or its rule is gone.
    """
    if shape[1] != _ABSENT:
        return (BUCKET_PRESERVED, ACTION_KEEP_ON_DISK, REASON_KIRO_OWNED)
    if shape[2] != _ABSENT:
        return (BUCKET_ADDED, ACTION_TAKE_STAGING, None)
    return (BUCKET_REMOVED, ACTION_REMOVE, None)


def _reference_verdict(
    *,
    previous: str | None,
    on_disk: str | None,
    staging: str | None,
    owner: str | None,
) -> _Verdict:
    """The bucket, action, and reason the design's table assigns."""
    shape = _shape(previous, on_disk, staging)
    if owner == OWNER_KIRO:
        return _declared_verdict(shape)
    return _CLASSIFICATION_TABLE[shape]


def _assert_conflict_identifies_both_sides(entry: Classification) -> Conflict:
    """R5 AC6: the retained adaptation and the declined template change.

    Each side has to name the version of the file it is about, which is checked
    by hash prefix rather than by wording — the local side is the content being
    kept, or the previous content when the local state is an absence; the
    upstream side is what the new transform produces, or the previous content
    when it produces nothing.
    """
    conflict = entry.conflict
    assert conflict is not None
    assert conflict.path == entry.path
    assert conflict.resolution == CONFLICT_RESOLUTION
    assert conflict.adaptation != conflict.template_change
    local = entry.on_disk_sha256 or entry.previous_sha256
    upstream = entry.staging_sha256 or entry.previous_sha256
    for side, digest in (
        (conflict.adaptation, local),
        (conflict.template_change, upstream),
    ):
        assert side.strip()
        assert entry.path in side
        assert digest is not None
        assert digest[:_IDENTIFYING_PREFIX] in side
    # The local content is what stays; a conflict is reported, not resolved.
    assert entry.action == ACTION_KEEP_ON_DISK
    assert ACTION_SOURCES[entry.action] == SOURCE_ON_DISK
    return conflict


def _assert_no_divergent_overwrite(entry: Classification) -> None:
    """The rule the Reconciler exists to keep *(R5 AC5, AC6)*.

    A locally divergent file is never overwritten and never deleted. Staging is
    taken only where the local file is absent, already byte-identical, or
    unmoved since the last build; a removal only where the local state is the
    build's own.
    """
    if entry.action == ACTION_TAKE_STAGING:
        assert (
            entry.on_disk_sha256 is None
            or entry.on_disk_sha256 == entry.staging_sha256
            or entry.on_disk_sha256 == entry.previous_sha256
        )
    if entry.action == ACTION_REMOVE:
        assert (
            entry.on_disk_sha256 is None
            or entry.on_disk_sha256 == entry.previous_sha256
        )
    if entry.action in (ACTION_KEEP, ACTION_KEEP_ON_DISK):
        assert ACTION_SOURCES[entry.action] == SOURCE_ON_DISK


def _assert_verdict(entry: Classification, *, owner: str | None) -> _Verdict:
    """One classification against the table: bucket, action, and reason."""
    expected = _reference_verdict(
        previous=entry.previous_sha256,
        on_disk=entry.on_disk_sha256,
        staging=entry.staging_sha256,
        owner=owner,
    )
    assert (entry.bucket, entry.action, entry.reason) == expected, entry.path
    assert entry.owner == owner
    assert entry.action == _BUCKET_ACTIONS[entry.bucket]

    # A reason belongs to a preserved adaptation and a conflict record to a
    # conflict; the other four buckets carry neither.
    if entry.bucket == BUCKET_PRESERVED:
        assert entry.reason in _PRESERVATION_REASONS
    else:
        assert entry.reason is None
    if entry.bucket == BUCKET_CONFLICTS:
        _assert_conflict_identifies_both_sides(entry)
    else:
        assert entry.conflict is None

    _assert_no_divergent_overwrite(entry)

    # Pure, and reachable on its own: three hashes and an owner produce this
    # verdict whether the classifier is driven per path or over a whole tree.
    assert (
        classify_path(
            entry.path,
            previous_sha256=entry.previous_sha256,
            on_disk_sha256=entry.on_disk_sha256,
            staging_sha256=entry.staging_sha256,
            owner=owner,
        )
        == entry
    )
    return expected


def _assert_partition(
    report: ReconciliationReport, expected: Iterable[str]
) -> dict[str, tuple[str, ...]]:
    """Every path in exactly one bucket, in the model and in the document."""
    paths = tuple(sorted(expected))
    buckets = report.buckets()
    assert tuple(buckets) == BUCKETS
    assert len(BUCKETS) == len(set(BUCKETS)) == 6

    placed = [path for bucket in BUCKETS for path in buckets[bucket]]
    assert len(placed) == len(set(placed))  # at most one bucket per path
    assert tuple(sorted(placed)) == paths  # and at least one
    assert len(report.classifications) == len(paths)
    for bucket, members in buckets.items():
        assert tuple(sorted(members)) == members
        for path in members:
            assert report.bucket_of(path) == bucket

    # The two typed views agree with the buckets they are derived from.
    assert (
        tuple(item.path for item in report.preserved_adaptations)
        == buckets[BUCKET_PRESERVED]
    )
    assert (
        tuple(item.path for item in report.conflicts) == buckets[BUCKET_CONFLICTS]
    )

    # The document the Update_Skill presents carries the same partition, with a
    # reason on every preserved adaptation and both sides on every conflict
    # *(R5 AC4, AC6)*.
    document = report.to_json()
    assert document["reportVersion"] == RECONCILE_REPORT_VERSION
    listed = {
        BUCKET_ADDED: tuple(document["added"]),
        BUCKET_MODIFIED: tuple(document["modified"]),
        BUCKET_REMOVED: tuple(document["removed"]),
        BUCKET_UNCHANGED: tuple(document["unchanged"]),
        BUCKET_PRESERVED: tuple(
            item["path"] for item in document["preservedAdaptations"]
        ),
        BUCKET_CONFLICTS: tuple(item["path"] for item in document["conflicts"]),
    }
    assert listed == dict(buckets)
    for item in document["preservedAdaptations"]:
        assert item["reason"] in _PRESERVATION_REASONS
    for item in document["conflicts"]:
        assert item["adaptation"].strip()
        assert item["templateChange"].strip()
        assert item["resolution"] == CONFLICT_RESOLUTION
    assert json.loads(report.serialize().decode("utf-8")) == document
    return buckets


@dataclass(frozen=True)
class _SeededPath:
    """One table row planted at a path, with the owner the manifest records."""

    path: str
    shape: _Shape
    owner: str | None


def _seeded_table_inputs(
    seed: str,
) -> tuple[ManifestBaseline, FileTree, FileTree, tuple[_SeededPath, ...]]:
    """One path per table row, and per owner, over drawn content.

    The generator draws the seven constructions its intents name; the table has
    fourteen rows, and the declared `owner: kiro` row applies to every row whose
    file the last build recorded. The remainder is seeded here so every row is
    driven on every example. A shape with no previous entry has no recorded
    owner to declare with, so it is built once rather than twice.
    """
    manifest_files: list[dict[str, Any]] = []
    on_disk: dict[str, str] = {}
    staging: dict[str, str] = {}
    planted: list[_SeededPath] = []

    for index, shape in enumerate(_canonical_shapes()):
        tracked = shape[0] != _ABSENT
        for owner in (OWNER_TEMPLATE, OWNER_KIRO):
            if owner == OWNER_KIRO and not tracked:
                continue
            path = f"skills/shape-{index:02d}-{owner}/SKILL.md"
            contents = {
                label: f"{seed}\nclass {label} of {path}\n"
                for label in _CONTENT_LABELS
            }
            previous, local, upstream = shape
            if tracked:
                manifest_files.append(
                    {
                        "path": path,
                        "ruleId": "skills-modules",
                        "owner": owner,
                        "sourcePath": (
                            None
                            if owner == OWNER_KIRO
                            else f"{TEMPLATE_PLUGIN_ROOT}/{path}"
                        ),
                        "sha256": sha256_hex(contents[previous].encode("utf-8")),
                    }
                )
            if local != _ABSENT:
                on_disk[path] = contents[local]
            if upstream != _ABSENT:
                staging[path] = contents[upstream]
            planted.append(
                _SeededPath(
                    path=path, shape=shape, owner=owner if tracked else None
                )
            )

    baseline = ManifestBaseline.from_json(
        {
            "manifestVersion": 1,
            "templateRelease": _PREVIOUS_RELEASE,
            "contractVersion": 1,
            "files": manifest_files,
        }
    )
    return (
        baseline,
        FileTree.from_mapping(on_disk),
        FileTree.from_mapping(staging),
        tuple(planted),
    )


# Feature: senzing-bootcamp-power, Property 20: Reconciliation classifies every
# path exactly once
#
# Validates: Requirements 5.4, 5.6
@settings(max_examples=100)
@given(reconcile_triple(), st.text(max_size=24))
def test_reconciliation_classifies_every_path_exactly_once(
    triple: ReconcileTriple,
    seed: str,
) -> None:
    # The generator cases and construction labels this property reads, asserted
    # rather than assumed.
    assert _REQUIRED_TRIPLE_CASES <= set(RECONCILE_TRIPLE_CASES)
    assert set(_INTENT_VERDICTS) == set(RECONCILE_INTENTS)

    # The oracle is total over the shapes three inputs can take, so no draw and
    # no seeded row can reach a case the table has no row for.
    assert set(_CLASSIFICATION_TABLE) == set(_canonical_shapes())
    assert len(_CLASSIFICATION_TABLE) == 14
    assert set(_BUCKET_ACTIONS) == set(BUCKETS)
    assert set(ACTION_SOURCES) == set(_BUCKET_ACTIONS.values())
    declared = _declared_verdict(("A", "A", "A"))
    assert _PRESERVATION_REASONS == {
        verdict[2]
        for verdict in (*_CLASSIFICATION_TABLE.values(), declared)
        if verdict[2] is not None
    }

    covered_buckets: set[str] = set()
    covered_actions: set[str] = set()
    covered_reasons: set[str] = set()

    # --- Clause 1: the drawn triple, classified exactly once ----------------
    baseline = ManifestBaseline.from_json(triple.manifest)
    on_disk = FileTree.from_mapping(triple.on_disk)
    staging = FileTree.from_mapping(triple.staging)
    report = reconcile(baseline, on_disk, staging, to_release=_TO_RELEASE)

    assert union_paths(baseline, on_disk, staging) == triple.paths
    assert tuple(entry.path for entry in report.classifications) == triple.paths
    assert report.classifications == classify(baseline, on_disk, staging)
    _assert_partition(report, triple.paths)

    for entry in report.classifications:
        owner = baseline.owner(entry.path)
        bucket, action, reason = _assert_verdict(entry, owner=owner)
        # The second reading: the bucket the generator's construction owes,
        # derived from an intent the classifier never sees.
        assert (bucket, action, reason) == _INTENT_VERDICTS[
            triple.intents[entry.path]
        ]
        covered_buckets.add(bucket)
        covered_actions.add(action)
        if reason is not None:
            covered_reasons.add(reason)

    # --- Clause 2: every table row, and the declared row over each ----------
    seeded_baseline, seeded_disk, seeded_staging, planted = _seeded_table_inputs(seed)
    seeded = reconcile(
        seeded_baseline,
        seeded_disk,
        seeded_staging,
        to_release=_TO_RELEASE,
    )
    _assert_partition(seeded, [item.path for item in planted])

    by_path = {entry.path: entry for entry in seeded.classifications}
    assert set(by_path) == {item.path for item in planted}
    covered_shapes: set[_Shape] = set()
    for item in planted:
        entry = by_path[item.path]
        # The row was planted as this shape and read as this shape: the seeding
        # and the classifier agree on what the inputs said.
        assert (
            _shape(
                entry.previous_sha256, entry.on_disk_sha256, entry.staging_sha256
            )
            == item.shape
        )
        bucket, action, reason = _assert_verdict(entry, owner=item.owner)
        covered_shapes.add(item.shape)
        covered_buckets.add(bucket)
        covered_actions.add(action)
        if reason is not None:
            covered_reasons.add(reason)

    # Non-vacuous in every example: every shape, every bucket, every action, and
    # every preservation reason is reached, so none of them is a case this
    # property merely describes.
    assert covered_shapes == set(_canonical_shapes())
    assert covered_buckets == set(BUCKETS)
    assert covered_actions == set(ACTION_SOURCES)
    assert covered_reasons == _PRESERVATION_REASONS

    # --- Clause 3: the Build_Manifest is not part of what it records --------
    assert UNCLASSIFIED_PATHS == frozenset({MANIFEST_FILENAME})
    noisy = ManifestBaseline.from_json(
        {
            **triple.manifest,
            "files": [
                *triple.manifest["files"],
                {
                    "path": MANIFEST_FILENAME,
                    "ruleId": "generate-manifest",
                    "owner": OWNER_TEMPLATE,
                    "sourcePath": None,
                    "sha256": sha256_hex(b'{"manifestVersion": 1}\n'),
                },
            ],
        }
    )
    noisy_disk = FileTree.from_mapping(
        {**triple.on_disk, MANIFEST_FILENAME: '{"onDisk": true}\n'}
    )
    noisy_staging = FileTree.from_mapping(
        {**triple.staging, MANIFEST_FILENAME: '{"staging": true}\n'}
    )
    assert MANIFEST_FILENAME not in union_paths(noisy, noisy_disk, noisy_staging)
    with_manifest = reconcile(
        noisy, noisy_disk, noisy_staging, to_release=_TO_RELEASE
    )
    assert with_manifest.bucket_of(MANIFEST_FILENAME) is None
    # Excluded, and inert: the three differing versions of it change no other
    # path's verdict.
    assert with_manifest.classifications == report.classifications
    _assert_partition(with_manifest, triple.paths)

    # --- Clause 4: the verdict is about the files, not about the releases ---
    assert report.to_release == _TO_RELEASE
    assert report.from_release == triple.manifest["templateRelease"]
    assert report.flagged_invariant_discounts == ()
    assert _OVERRIDE_RELEASE != baseline.template_release
    overridden = reconcile(
        baseline,
        on_disk,
        staging,
        to_release=_TO_RELEASE,
        from_release=_OVERRIDE_RELEASE,
    )
    assert overridden.from_release == _OVERRIDE_RELEASE
    assert overridden.classifications == report.classifications


# ===========================================================================
# Property 21: Kiro-specific adaptations survive an update byte-identically
# ===========================================================================
#
# Property 20 asks whether the Reconciler *says* the right thing about each
# path. This one asks whether the update *does* it, and the two can disagree.
# A verdict of `keep-on-disk` is advice until something materializes it, and the
# update publishes by renaming a whole staging tree over the Power — so an
# adaptation that was classified perfectly and never copied into staging is
# preserved on paper and gone from disk. No classification can detect that.
# Only bytes can. So this property compares bytes: the pre-update Power against
# the tree the swap actually published, path by path, and it asserts no bucket.
#
# The claim, from the design: after a successful update every `kiro-owned` file
# and every locally edited file whose template source did not change is
# byte-identical to its pre-update content, and every locally edited file whose
# template source *did* change retains its pre-update content anyway
# *(R5 AC5, AC6)*.
#
# What "byte-identical" has to mean here
# --------------------------------------
# Including an absence. A file a Maintainer deleted is a local divergence like
# any other, so "unchanged" means it stays deleted; an update that helpfully
# restored it would have overwritten a local decision. Absence is therefore a
# first-class expected value throughout — `None` in the tables below, a missing
# key in the published tree — rather than a case the assertions skip.
#
# Inputs: drawn constructions, plus every adaptation shape on every example
# --------------------------------------------------------------------------
# `reconcile_triple()` supplies the drawn half, and its construction labels are
# read directly: three of the seven put a Kiro-specific adaptation on disk and
# four do not, which is where the expected bytes come from — the local side for
# the first three, the freshly transformed side for the rest. The labels are
# partitioned explicitly, so a new generator intent fails here until someone
# decides which side of the claim it belongs on.
#
# The drawn half alone would leave the interesting shapes to chance and would
# never reach some of them at all, so eight adaptation shapes are seeded at
# fixed, realistic paths on every example, over drawn content: a `kiro-owned`
# hook definition the new release would have rewritten, a `kiro-owned` skill
# edited locally, a `kiro-owned` script edited on both sides, a ported skill
# edited locally, a ported skill edited locally *and* upstream, a ported skill
# edited locally and dropped upstream, a deleted reference file, and a
# `CHANGELOG.md` that no build ever produced. Four control paths are seeded
# beside them — one changed only upstream, one added, one removed, one untouched
# — because "everything was preserved" is also what a broken update that
# published nothing would report. Both directions are asserted: the adaptations
# keep their bytes, and the controls move.
#
# Four clauses
# ------------
# (1) The local side wins exactly where an adaptation is, and nowhere else. The
#     set of paths the application takes from disk is compared against the set
#     the constructions say are adaptations — equality, not containment, because
#     preserving a path that had no adaptation on it means the update silently
#     stopped propagating template changes.
#
# (2) Applying writes into staging and nothing else. The Power is read back
#     after the application and has to be byte-identical to its pre-update self,
#     which is what keeps the swap all-or-nothing and a failure part-way through
#     harmless *(R5 AC7)*. Applying the same verdict twice is asserted to leave
#     the staging tree exactly as the first application left it.
#
# (3) The published tree, byte for byte, after a real swap. Every adaptation
#     path equals its pre-update content, and where the new release produced
#     *different* content for one of them, the published bytes are asserted to
#     differ from that upstream content — the retention has to be visible as a
#     declined change, not inferred from a hash that happened to match.
#
# (4) The adaptation survives the *next* update too, which is the part that is
#     easy to get wrong. The Build_Manifest is carried from staging verbatim
#     rather than rewritten to describe the reconciled bytes, and that is what
#     keeps an adaptation alive: the published manifest still records what the
#     engine produced, so the following update sees the same divergence and
#     preserves again. Rewriting it would record the adaptation as engine output
#     and the next update would overwrite it — an update later, in a run nobody
#     connects to this one. So a second reconciliation is driven against the
#     published tree and the same adaptations are asserted to still hold their
#     original bytes.

#: The releases the two updates run between. Nothing in preservation reads a
#: release; these only have to be distinct and ordered.
_SURVIVAL_FROM_RELEASE = "0.5.0"
_SURVIVAL_TO_RELEASE = "0.5.1"
_SURVIVAL_NEXT_RELEASE = "0.6.0"

#: The generator constructions that leave a Kiro-specific adaptation on disk,
#: and those that do not. Partitioned rather than listed, so an added intent
#: cannot slip through as neither.
_SURVIVING_INTENTS = frozenset(
    {"local-edit-only", "local-edit-and-upstream-change", "kiro-owned"}
)
_MOVING_INTENTS = frozenset({"unchanged", "upstream-change", "added", "removed"})


@dataclass(frozen=True)
class _Adaptation:
    """One seeded path, described by construction rather than by bucket.

    `previous`, `on_disk`, and `staging` name content classes, with `None`
    meaning the path is absent from that input. `owner` is what the previous
    build recorded, or `None` when it recorded nothing.

    `survives` is the claim under test: `True` means the pre-update Power's
    content — including its absence — is what the update must publish, `False`
    means the freshly transformed content is.
    """

    name: str
    path: str
    owner: str | None
    previous: str | None
    on_disk: str | None
    staging: str | None
    survives: bool


#: Eight adaptation shapes and four controls, at paths a real Power carries. The
#: skill directory names are all longer than a drawn slug can be, so no seeded
#: path can collide with a drawn one — asserted in the test rather than trusted.
_SURVIVAL_ROWS: tuple[_Adaptation, ...] = (
    # --- Declared adaptations: `owner: kiro` ------------------------------
    # A hook definition the newer release would rewrite. Nothing moved locally,
    # so only the declaration stands between the adaptation and the upstream
    # content — which is exactly the case a detection-only reconciler loses.
    _Adaptation(
        name="kiro-declared-unmoved",
        path="dev.kiro/hooks/senzing-bootcamp-session-start.json",
        owner=OWNER_KIRO,
        previous="A",
        on_disk="A",
        staging="B",
        survives=True,
    ),
    # A command-derived skill edited after it was materialized.
    _Adaptation(
        name="kiro-declared-edited",
        path="skills/start-bootcamp/SKILL.md",
        owner=OWNER_KIRO,
        previous="A",
        on_disk="B",
        staging="A",
        survives=True,
    ),
    # The installer, edited locally and rewritten upstream: both sides moved and
    # the declaration still decides.
    _Adaptation(
        name="kiro-declared-edited-and-changed",
        path="skills/bootcamp-enforcement-setup/scripts/install_hooks.py",
        owner=OWNER_KIRO,
        previous="A",
        on_disk="B",
        staging="C",
        survives=True,
    ),
    # --- Detected adaptations: `owner: template`, locally divergent -------
    _Adaptation(
        name="local-edit-only",
        path="skills/bootcamp-onboarding/SKILL.md",
        owner=OWNER_TEMPLATE,
        previous="A",
        on_disk="B",
        staging="A",
        survives=True,
    ),
    _Adaptation(
        name="local-edit-and-upstream-change",
        path="skills/module-03b/SKILL.md",
        owner=OWNER_TEMPLATE,
        previous="A",
        on_disk="B",
        staging="C",
        survives=True,
    ),
    # Edited locally, dropped upstream. An upstream removal is an upstream
    # change, so the local content stays *(R5 AC6)*.
    _Adaptation(
        name="local-edit-and-upstream-removal",
        path="skills/module-07/SKILL.md",
        owner=OWNER_TEMPLATE,
        previous="A",
        on_disk="B",
        staging=None,
        survives=True,
    ),
    # Deleted locally. "Byte-identical" includes staying deleted.
    _Adaptation(
        name="local-delete",
        path="skills/module-02/references/local-notes.md",
        owner=OWNER_TEMPLATE,
        previous="A",
        on_disk=None,
        staging="A",
        survives=True,
    ),
    # The Power's own changelog: no template source, no manifest entry, and it
    # has to come through an update intact or R5 AC8 has nothing to append to.
    _Adaptation(
        name="local-only",
        path="CHANGELOG.md",
        owner=None,
        previous=None,
        on_disk="B",
        staging=None,
        survives=True,
    ),
    # --- Controls: the update is still an update --------------------------
    _Adaptation(
        name="upstream-change",
        path="skills/module-04/SKILL.md",
        owner=OWNER_TEMPLATE,
        previous="A",
        on_disk="A",
        staging="B",
        survives=False,
    ),
    _Adaptation(
        name="upstream-addition",
        path="skills/module-08/SKILL.md",
        owner=None,
        previous=None,
        on_disk=None,
        staging="B",
        survives=False,
    ),
    _Adaptation(
        name="upstream-removal",
        path="skills/module-legacy/SKILL.md",
        owner=OWNER_TEMPLATE,
        previous="A",
        on_disk="A",
        staging=None,
        survives=False,
    ),
    _Adaptation(
        name="untouched",
        path="skills/graduation/SKILL.md",
        owner=OWNER_TEMPLATE,
        previous="A",
        on_disk="A",
        staging="A",
        survives=False,
    ),
)

#: Seeded adaptations whose upstream side produces different content, so the
#: published bytes have to differ from the staged bytes and not merely match the
#: Power's by coincidence.
_SURVIVAL_DECLINED = frozenset(
    row.path
    for row in _SURVIVAL_ROWS
    if row.survives and row.staging is not None and row.staging != row.on_disk
)

#: Seeded controls whose bytes have to change, so "everything survived" cannot
#: be satisfied by an update that published the Power back to itself.
_SURVIVAL_MOVED = frozenset(
    row.path
    for row in _SURVIVAL_ROWS
    if not row.survives and row.staging != row.on_disk
)


def _survival_content(seed: str, path: str, label: str | None) -> bytes | None:
    """The bytes of one content class at one path, or `None` for an absence.

    Drawn text keeps the content out of the assertions' control; the path and
    the label keep two classes at one path, and one class at two paths, distinct.
    """
    if label is None:
        return None
    return f"{seed}\nclass {label} of {path}\n".encode("utf-8")


def _survival_manifest(
    files: Mapping[str, bytes], owners: Mapping[str, str], release: str
) -> bytes:
    """A `.build-manifest.json` describing exactly `files` and nothing else.

    The manifest is the *baseline*, so it describes what the build wrote rather
    than what is on disk now — that difference is what a local edit is. Written
    as bytes because clause 4 compares the published manifest against the staged
    one for byte equality, not for equivalent JSON.
    """
    document = {
        "manifestVersion": MANIFEST_VERSION,
        "templateRelease": release,
        "contractVersion": 1,
        "files": [
            {
                "path": path,
                "ruleId": (
                    "command-skills"
                    if owners.get(path, OWNER_TEMPLATE) == OWNER_KIRO
                    else "skills-modules"
                ),
                "owner": owners.get(path, OWNER_TEMPLATE),
                "sourcePath": (
                    None
                    if owners.get(path, OWNER_TEMPLATE) == OWNER_KIRO
                    else f"{TEMPLATE_PLUGIN_ROOT}/{path}"
                ),
                "sha256": sha256_hex(data),
            }
            for path, data in sorted(files.items())
        ],
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


@dataclass(frozen=True)
class _SurvivalInputs:
    """The three inputs as bytes, plus what the constructions say must publish.

    `adaptations` is the set of paths whose pre-update content has to survive,
    and `published` the content-bearing paths the update owes afterwards — both
    derived from construction labels, never from a classification.
    """

    previous: Mapping[str, bytes]
    on_disk: Mapping[str, bytes]
    staging: Mapping[str, bytes]
    owners: Mapping[str, str]
    adaptations: frozenset[str]
    published: Mapping[str, bytes]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(
            sorted(set(self.previous) | set(self.on_disk) | set(self.staging))
        )


def _survival_inputs(triple: ReconcileTriple, seed: str) -> _SurvivalInputs:
    """Merge the drawn triple with the seeded rows into one update's inputs."""
    previous: dict[str, bytes] = {}
    on_disk: dict[str, bytes] = {}
    staging: dict[str, bytes] = {}
    owners: dict[str, str] = {}
    adaptations: set[str] = set()
    published: dict[str, bytes] = {}

    drawn_owners = {
        entry["path"]: entry["owner"] for entry in triple.manifest["files"]
    }
    for path, intent in sorted(triple.intents.items()):
        owners[path] = drawn_owners.get(path, OWNER_TEMPLATE)
        for source, destination in (
            (triple.previous, previous),
            (triple.on_disk, on_disk),
            (triple.staging, staging),
        ):
            if path in source:
                destination[path] = source[path].encode("utf-8")
        survives = intent in _SURVIVING_INTENTS
        expected = on_disk.get(path) if survives else staging.get(path)
        if survives:
            adaptations.add(path)
        if expected is not None:
            published[path] = expected

    for row in _SURVIVAL_ROWS:
        owners[row.path] = row.owner or OWNER_TEMPLATE
        for label, destination in (
            (row.previous, previous),
            (row.on_disk, on_disk),
            (row.staging, staging),
        ):
            data = _survival_content(seed, row.path, label)
            if data is not None:
                destination[row.path] = data
        expected = (
            on_disk.get(row.path) if row.survives else staging.get(row.path)
        )
        if row.survives:
            adaptations.add(row.path)
        if expected is not None:
            published[row.path] = expected

    return _SurvivalInputs(
        previous=previous,
        on_disk=on_disk,
        staging=staging,
        owners=owners,
        adaptations=frozenset(adaptations),
        published=published,
    )


def _write_survival_tree(root: Path, files: Mapping[str, bytes]) -> Path:
    """Materialize a content mapping as a real directory tree."""
    root.mkdir(parents=True, exist_ok=True)
    for path, data in sorted(files.items()):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


# Feature: senzing-bootcamp-power, Property 21: Kiro-specific adaptations
# survive an update byte-identically
#
# Validates: Requirements 5.5, 5.6
@settings(max_examples=100)
@given(reconcile_triple(), st.text(max_size=24))
def test_kiro_adaptations_survive_an_update_byte_identically(
    triple: ReconcileTriple,
    seed: str,
) -> None:
    # The constructions this property reads its expectations from, asserted
    # rather than assumed: a new generator intent has to be placed on one side
    # of the claim, and the seeded rows have to stay a set of distinct paths.
    assert _SURVIVING_INTENTS | _MOVING_INTENTS == set(RECONCILE_INTENTS)
    assert not (_SURVIVING_INTENTS & _MOVING_INTENTS)
    seeded_paths = {row.path for row in _SURVIVAL_ROWS}
    assert len(seeded_paths) == len(_SURVIVAL_ROWS)
    assert len({row.name for row in _SURVIVAL_ROWS}) == len(_SURVIVAL_ROWS)
    assert seeded_paths.isdisjoint(triple.intents)
    # Non-vacuous by construction: adaptations whose upstream side moved, and
    # controls that have to move, are both present on every example.
    assert len(_SURVIVAL_DECLINED) >= 4
    assert len(_SURVIVAL_MOVED) >= 3

    inputs = _survival_inputs(triple, seed)
    assert _SURVIVAL_DECLINED | _SURVIVAL_MOVED <= set(inputs.paths)
    assert _SURVIVAL_DECLINED <= inputs.adaptations
    assert inputs.adaptations.isdisjoint(_SURVIVAL_MOVED)

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        power = root / "senzing-bootcamp"
        staging = root / "senzing-bootcamp.staging"

        previous_manifest = _survival_manifest(
            inputs.previous, inputs.owners, _SURVIVAL_FROM_RELEASE
        )
        staged_manifest = _survival_manifest(
            inputs.staging, inputs.owners, _SURVIVAL_TO_RELEASE
        )
        _write_survival_tree(
            power, {**inputs.on_disk, MANIFEST_FILENAME: previous_manifest}
        )
        _write_survival_tree(
            staging, {**inputs.staging, MANIFEST_FILENAME: staged_manifest}
        )

        # The pre-update Power: the bytes every later comparison is against.
        power_before = _read_tree(power)
        assert power_before == {
            **inputs.on_disk,
            MANIFEST_FILENAME: previous_manifest,
        }

        report = reconcile_directories(
            power, staging, to_release=_SURVIVAL_TO_RELEASE
        )
        assert report.to_release == _SURVIVAL_TO_RELEASE
        assert report.from_release == _SURVIVAL_FROM_RELEASE
        assert tuple(entry.path for entry in report.classifications) == inputs.paths

        # --- Clause 1: the local side wins exactly where an adaptation is ---
        pure = apply_report(
            report, FileTree.from_directory(power), FileTree.from_directory(staging)
        )
        assert pure.defects() == ()
        assert set(pure.preserved_paths) == inputs.adaptations
        assert pure.tree.files == {
            **inputs.published,
            MANIFEST_FILENAME: staged_manifest,
        }
        assert pure.carried == (MANIFEST_FILENAME,)

        # --- Clause 2: applying writes into staging, and only into staging ---
        application = apply_to_staging(report, power, staging)
        assert application.tree.files == pure.tree.files
        assert _read_tree(power) == power_before
        assert _read_tree(staging) == pure.tree.files

        staged_once = _read_tree(staging)
        assert apply_to_staging(report, power, staging).tree.files == pure.tree.files
        assert _read_tree(staging) == staged_once

        # --- Clause 3: the published tree, byte for byte --------------------
        swap_into_place(staging, power)
        published = _read_tree(power)
        assert published == {**inputs.published, MANIFEST_FILENAME: staged_manifest}

        declined: set[str] = set()
        for path in sorted(inputs.adaptations):
            # Byte-identical, absence included.
            assert published.get(path) == power_before.get(path), path
            upstream = inputs.staging.get(path)
            if upstream is not None and upstream != power_before.get(path):
                # The upstream content existed and was declined, visibly.
                assert published.get(path) != upstream, path
                declined.add(path)
        assert _SURVIVAL_DECLINED <= declined

        moved = {
            path
            for path in inputs.paths
            if path not in inputs.adaptations
            and published.get(path) != power_before.get(path)
        }
        assert _SURVIVAL_MOVED <= moved

        # The manifest is carried from staging verbatim, which is what clause 4
        # depends on: it describes what the engine produced, not what published.
        assert published[MANIFEST_FILENAME] == staged_manifest
        assert staged_manifest != previous_manifest

        # --- Clause 4: and it survives the next update too ------------------
        next_staging = root / "senzing-bootcamp.staging-next"
        _write_survival_tree(
            next_staging, {**inputs.staging, MANIFEST_FILENAME: staged_manifest}
        )
        second = reconcile_directories(
            power, next_staging, to_release=_SURVIVAL_NEXT_RELEASE
        )
        assert second.from_release == _SURVIVAL_TO_RELEASE
        again = apply_report(
            second,
            FileTree.from_directory(power),
            FileTree.from_directory(next_staging),
        )
        assert again.defects() == ()
        assert set(again.preserved_paths) == inputs.adaptations
        for path in sorted(inputs.adaptations):
            assert again.tree.read_bytes(path) == power_before.get(path), path


# ===========================================================================
# Property 22: A successful update records exactly one changelog entry naming
# its source release
# ===========================================================================
#
# R5 AC8 is one sentence carrying four separate ways to get an update's record
# wrong: appending nothing, appending twice, appending an entry that does not say
# which release it came from, and — from R5 AC7's side — appending anything at
# all after a *failed* update. All four are claims about one file, so they are
# one property.
#
# "Gains exactly one entry" is counted, and the count is a second opinion
# --------------------------------------------------------------------------
# The oracle is a level-2 ATX heading count written here, deliberately not the
# engine's `entry_recorded`: an entry is a `## <tag>` line, the `### Added`
# sections *inside* an entry are not entries, and a tag an earlier entry mentions
# in prose is not an entry either. The claim is then asserted as a **sequence**,
# `(*before, tag)`, which says in one line that the entry was appended rather
# than inserted, that the prior headings kept their order, and that none of them
# was rewritten into something else.
#
# "No other changelog content is altered" is a prefix relation
# -----------------------------------------------------------
# Not a diff and not a heading comparison: the composed text has to **start with
# the previous changelog verbatim**, and the only thing allowed between that
# prefix and the entry is blank-line separation — asserted as
# `set(inserted) <= {"\n"}`, so a reflow, a re-indent, or a trimmed tail fails
# here even when every heading survived. That is what makes the check mean
# something over the shapes a hand-kept changelog actually arrives in.
#
# Inputs: a drawn update, and every changelog shape on every example
# -----------------------------------------------------------------
# `reconcile_triple()` supplies the update — the report's path lists are what the
# entry's `### Added`/`### Changed`/`### Removed` sections are rendered from, and
# the manifest's drawn tag is the release the Power came from. The newer tag is
# derived from it by raising one semver component, and `is_newer` is asserted on
# every example so the update under test is always an update.
#
# The changelog it appends to is the part a draw would never cover, so ten shapes
# are built over drawn prose and driven through the pure clauses on every
# example: absent, empty, a header with no entries yet, one entry, two entries
# with a non-tag `## Unreleased` heading among them, no trailing newline,
# several trailing blank lines, CRLF endings, non-ASCII prose, and an earlier
# entry whose prose mentions the very tag this update records. One shape is
# sampled per example for the on-disk clauses, where a real update is run.
#
# Five clauses
# ------------
# (1) The entry, in memory: exactly one heading, that heading is the newer tag,
#     the text names the tag and the Template_Plugin it came from, and rendering
#     it twice yields identical text — no date, no timestamp, no run id — which
#     is what makes clause 4's already-recorded check meaningful.
#
# (2) Appending, over all ten shapes: prefix preserved, one heading gained,
#     nothing inserted but separation.
#
# (3) A failed update records nothing *(R5 AC7)*. The entry is appended to the
#     **staged** changelog, so discarding staging leaves the Power byte-identical
#     — asserted after the recording, not merely after the failure — and the
#     recorder is asserted to refuse a write aimed into the Power at all, which
#     is the structural reason the guarantee holds rather than a habit callers
#     have to keep.
#
# (4) A successful update records exactly one entry, and a retried one records no
#     second entry for the same release: the staged changelog is left
#     byte-identical and reported as already recorded.
#
# (5) The published tree, after a real swap: recording touched exactly one file.
#     Every other published path equals what the reconciliation resolved, and the
#     published changelog carries the prior content as its prefix.
#
# Deliberately out of scope: whether the Power's own changelog *survives* an
# update at all is Property 21's — it is a `local-only-no-template-source`
# preserved adaptation there — and whether the version the entry names matches
# the Power's stamped version is Property 3's.
#
# `_survival_manifest`, `_write_survival_tree`, and `_read_tree` are shared with
# the sections above.

#: Which semver component the newer tag raises. Any of the three yields a
#: strictly newer release; `is_newer` is asserted on every example rather than
#: this being trusted.
_BUMP_COMPONENTS = (0, 1, 2)

#: A heading a hand-kept changelog carries that is not a release tag. Used so a
#: multi-entry history needs no second tag that might collide with the one this
#: update records.
_UNRELEASED_HEADING = "Unreleased"

#: An entry heading, as this property counts them: a level-2 ATX heading, so
#: `# Changelog` and the `### Added` sections inside an entry are not entries.
_ENTRY_HEADING_RE = re.compile(r"^##[ \t]+(.+)$", re.MULTILINE)

#: The pre-update changelog shapes driven here. Named at module level so one can
#: be sampled for the on-disk clauses, and asserted equal to what
#: `_changelog_states` builds, so a shape added there is reachable from here.
_CHANGELOG_SHAPES = (
    "absent",
    "empty",
    "header-only",
    "one-entry",
    "two-entries",
    "no-trailing-newline",
    "trailing-blank-lines",
    "crlf",
    "non-ascii",
    "mentions-new-tag",
)


def _entry_headings(changelog: str) -> tuple[str, ...]:
    """Every entry heading's text, in order, unquoted and trimmed.

    Code ticks are stripped because a hand-kept changelog may write `` ## `0.5.1`
    `` where the template writes `## 0.5.1`, and a trailing CR because a CRLF
    changelog carries one inside the line the heading is on.
    """
    return tuple(
        match.group(1).strip().strip("`").strip()
        for match in _ENTRY_HEADING_RE.finditer(changelog)
    )


def _newer_tag(tag: str, component: int, step: int) -> str:
    """Raise one semver component of `tag` and zero the ones below it."""
    parts = [int(part) for part in tag.split(".")]
    parts[component] += step
    for index in range(component + 1, len(parts)):
        parts[index] = 0
    return ".".join(str(part) for part in parts)


@dataclass(frozen=True)
class _ChangelogState:
    """One pre-update `CHANGELOG.md` as bytes, or `None` for its absence.

    `headings` is **computed from the bytes** rather than tracked while building
    them, so a shape that does not render the history it meant to fails the
    clause-2 sequence check instead of quietly weakening it.
    """

    name: str
    data: bytes | None

    @property
    def text(self) -> str:
        return "" if self.data is None else self.data.decode("utf-8")

    @property
    def headings(self) -> tuple[str, ...]:
        return _entry_headings(self.text)


def _changelog_states(
    seed: str, from_tag: str, to_tag: str
) -> tuple[_ChangelogState, ...]:
    """The ten pre-update changelog shapes, over drawn prose.

    Every shape's existing headings are `from_tag` or a non-tag heading, never
    `to_tag`, so "gains exactly one entry" is a claim about the update rather
    than about the changelog it started from — asserted per shape in the test.
    The drawn note is never placed at the start of a line, so no draw can spell
    a heading this property would then have to count.
    """
    note = " ".join(seed.split()) or "kept by hand"
    header = "# Changelog\n\nAll notable changes to the Bootcamp_Power.\n"
    generated = (
        f"## {from_tag}\n\nGenerated from Template_Release `{from_tag}`. {note}\n"
    )
    unreleased = f"## {_UNRELEASED_HEADING}\n\n- {note}\n"
    history = f"{header}\n{generated}"
    return (
        # The first update of a Power that never carried a changelog.
        _ChangelogState("absent", None),
        _ChangelogState("empty", b""),
        # A header, and no entries recorded yet.
        _ChangelogState("header-only", header.encode("utf-8")),
        _ChangelogState("one-entry", history.encode("utf-8")),
        _ChangelogState(
            "two-entries", f"{header}\n{unreleased}\n{generated}".encode("utf-8")
        ),
        # Awkward tails: the separator is chosen from what the text ends with,
        # and no choice may rewrite the text it is appended to.
        _ChangelogState(
            "no-trailing-newline", history.rstrip("\n").encode("utf-8")
        ),
        _ChangelogState("trailing-blank-lines", f"{history}\n\n".encode("utf-8")),
        # CRLF, which the recorder decodes and re-encodes without translating.
        _ChangelogState("crlf", history.replace("\n", "\r\n").encode("utf-8")),
        # Non-ASCII prose, so the round trip through UTF-8 is exercised.
        _ChangelogState(
            "non-ascii",
            (
                f"{header}\n## {from_tag}\n\nDonnées café — naïve Ñandú. {note}\n"
            ).encode("utf-8"),
        ),
        # The tag this update records, mentioned in an earlier entry's prose. A
        # mention is not a record, so the update still owes exactly one entry.
        _ChangelogState(
            "mentions-new-tag",
            (
                f"{header}\n## {from_tag}\n\nSuperseded upstream by {to_tag}. "
                f"{note}\n"
            ).encode("utf-8"),
        ),
    )


# Feature: senzing-bootcamp-power, Property 22: A successful update records
# exactly one changelog entry naming its source release
#
# Validates: Requirements 5.8
@settings(max_examples=100)
@given(
    reconcile_triple(),
    st.text(max_size=24),
    st.sampled_from(_BUMP_COMPONENTS),
    st.integers(min_value=1, max_value=3),
    st.sampled_from(_CHANGELOG_SHAPES),
)
def test_a_successful_update_records_exactly_one_changelog_entry(
    triple: ReconcileTriple,
    seed: str,
    component: int,
    step: int,
    shape: str,
) -> None:
    from_tag = triple.manifest["templateRelease"]
    to_tag = _newer_tag(from_tag, component, step)
    # The update under test is always an update, and the tag it records is not
    # one the changelog shapes already carry.
    assert is_newer(to_tag, from_tag)

    states = _changelog_states(seed, from_tag, to_tag)
    assert tuple(state.name for state in states) == _CHANGELOG_SHAPES
    # Non-vacuous by construction: shapes with a history, shapes without one,
    # and an absent changelog are all driven on every example.
    assert any(state.data is None for state in states)
    assert any(state.data is not None and not state.headings for state in states)
    assert any(len(state.headings) >= 2 for state in states)

    repository, contract_version = changelog_provenance()
    assert repository.strip()
    assert contract_version is not None

    report = reconcile(
        ManifestBaseline.from_json(triple.manifest),
        FileTree.from_mapping(triple.on_disk),
        FileTree.from_mapping(triple.staging),
        to_release=to_tag,
    )
    assert report.from_release == from_tag
    assert report.to_release == to_tag

    # --- Clause 1: the entry, in memory -------------------------------------
    entry = changelog_entry(report)
    # Deterministic: no date, no timestamp, no run id, so re-recording the same
    # update cannot produce text that merely looks like a different entry.
    assert changelog_entry(report) == entry
    assert _entry_headings(entry) == (to_tag,)
    assert to_tag in entry
    assert repository in entry
    assert entry_recorded(entry, to_tag)
    # The release it came *from* is named in prose, which is not a record of it.
    assert from_tag in entry
    assert not entry_recorded(entry, from_tag)
    assert entry.endswith("\n")

    # --- Clause 2: appending, over every changelog shape --------------------
    for state in states:
        existing = state.text
        assert not entry_recorded(existing, to_tag), state.name

        after = append_changelog_entry(existing, entry)
        # Pure: the same two texts compose the same way every time.
        assert append_changelog_entry(existing, entry) == after, state.name
        # No other changelog content is altered — the prior text is the result's
        # prefix, byte for byte.
        assert after[: len(existing)] == existing, state.name
        # Exactly one entry gained, appended, prior headings in place.
        assert _entry_headings(after) == (*state.headings, to_tag), state.name
        assert entry_recorded(after, to_tag), state.name
        # And nothing was inserted but blank-line separation.
        inserted = after[len(existing) :]
        assert inserted.endswith(entry), state.name
        assert set(inserted[: len(inserted) - len(entry)]) <= {"\n"}, state.name

    chosen = next(state for state in states if state.name == shape)

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        power = root / "senzing-bootcamp"
        staging = root / "senzing-bootcamp.staging"

        owners = {item["path"]: item["owner"] for item in triple.manifest["files"]}
        previous_files = {
            path: text.encode("utf-8") for path, text in triple.previous.items()
        }
        on_disk_files = {
            path: text.encode("utf-8") for path, text in triple.on_disk.items()
        }
        staging_files = {
            path: text.encode("utf-8") for path, text in triple.staging.items()
        }
        power_files = {
            **on_disk_files,
            MANIFEST_FILENAME: _survival_manifest(
                previous_files, owners, from_tag
            ),
        }
        if chosen.data is not None:
            power_files[CHANGELOG_FILENAME] = chosen.data
        staged_files = {
            **staging_files,
            MANIFEST_FILENAME: _survival_manifest(staging_files, owners, to_tag),
        }
        _write_survival_tree(power, power_files)
        _write_survival_tree(staging, staged_files)

        power_before = _read_tree(power)
        assert power_before == power_files

        on_disk_report = reconcile_directories(power, staging, to_release=to_tag)
        assert on_disk_report.from_release == from_tag
        assert on_disk_report.to_release == to_tag
        # The Power's own changelog is a preserved adaptation, never an added,
        # modified, or removed path, so the entry the update records does not
        # depend on the changelog it is being appended to.
        assert changelog_entry(on_disk_report) == entry
        if chosen.data is None:
            assert on_disk_report.bucket_of(CHANGELOG_FILENAME) is None
        else:
            assert on_disk_report.bucket_of(CHANGELOG_FILENAME) == BUCKET_PRESERVED
            preserved = {
                item.path: item.reason
                for item in on_disk_report.preserved_adaptations
            }
            assert preserved[CHANGELOG_FILENAME] == REASON_LOCAL_ONLY

        # --- Clause 3: a failed update records nothing (R5 AC7) -------------
        doomed = root / "senzing-bootcamp.staging-doomed"
        _write_survival_tree(doomed, staged_files)
        apply_to_staging(on_disk_report, power, doomed)
        doomed_record = record_update_in_staging(
            on_disk_report, doomed, power=power
        )
        assert doomed_record.appended
        assert doomed_record.entry == entry
        # Recorded into staging, so the Power is untouched even now.
        assert _read_tree(power) == power_before
        discard_staging(doomed)
        assert not doomed.exists()
        assert _read_tree(power) == power_before

        # The structural reason that holds: a write aimed into the Power is
        # refused rather than performed.
        with pytest.raises(TransformError) as refused:
            record_update_in_staging(on_disk_report, power, power=power)
        assert refused.value.code == E_WRITE_FAILED
        assert _read_tree(power) == power_before

        # --- Clause 4: one entry per update, at most one per release --------
        application = apply_to_staging(on_disk_report, power, staging)
        record = record_update_in_staging(on_disk_report, staging, power=power)
        assert record.appended
        assert not record.already_recorded
        assert record.tag == to_tag
        assert record.entry == entry
        assert record.names_tag
        assert record.path is not None
        assert record.path.name == CHANGELOG_FILENAME
        assert record.text == append_changelog_entry(chosen.text, entry)

        staged_once = _read_tree(staging)
        retried = record_update_in_staging(on_disk_report, staging, power=power)
        assert not retried.appended
        assert retried.already_recorded
        assert retried.text == record.text
        assert _read_tree(staging) == staged_once

        # --- Clause 5: the published tree, after a real swap ----------------
        swap_into_place(staging, power)
        published = _read_tree(power)
        # Recording touched exactly one file: every other published path is what
        # the reconciliation resolved, unchanged by the changelog step.
        assert published == {
            **application.tree.files,
            CHANGELOG_FILENAME: record.text.encode("utf-8"),
        }

        after = published[CHANGELOG_FILENAME].decode("utf-8")
        assert after[: len(chosen.text)] == chosen.text
        assert _entry_headings(after) == (*chosen.headings, to_tag)
        assert entry_recorded(after, to_tag)
        assert to_tag in after


# ===========================================================================
# Property 23: The test record gates tagging and round-trips faithfully
# ===========================================================================
#
# R6 AC2 and AC3 are one gate stated twice, from opposite ends: tagging requires
# recorded confirmation that every `Test_Checklist` step passed, and any step
# without a recorded pass blocks it. R6 AC6 is what makes that gate mean anything
# a month later — the per-step outcomes are *retained*, so the evidence behind a
# tagged release stays reviewable. A gate whose evidence does not survive being
# written down and read back is not a gate, so the two halves are one property.
#
# Two halves, one property
# ------------------------
# The **round trip** is `render_record` → `write_record` → `read_record`: every
# per-step outcome recovered identically, the nine per-platform cells included,
# together with the notes and the header facts a reviewer reads first. The
# **gate** is `tagAllowed`, true exactly when every defined step has a recorded
# pass for the exact version under test. They meet in the third clause, where the
# verdict computed over the parsed *document* is asserted equal to the verdict
# computed over the bare mapping — which is the claim that committing a record
# neither loosens nor tightens the gate.
#
# The oracle is written from the criteria, not from the module
# -----------------------------------------------------------
# `_testrecord_expected_defects` walks the checklist definition and decides, per
# step and per platform cell, what R6 AC2 owes: a recorded `pass` and nothing
# else. A step absent from the mapping is a missing step; a blank is a fail, not
# a blank; a note in the outcome column is not an outcome. The reason *vocabulary*
# is imported — a shared spelling is not a shared judgment — but which steps are
# at fault is computed here, and asserted as **set equality** against the report:
# "the report names exactly the offending steps, no more and no fewer" fails
# equally on a missed step and on an invented one. The finding count is asserted
# equal to the label count as well, so one blank cell stays one finding rather
# than being reported twice.
#
# `outcome_set()`'s own `defects` field is a second opinion rather than the
# oracle: it is compared on the offending *steps* and on the verdict, because the
# generator labels a failed matrix step once while the gate — correctly — reports
# the platform cells that failed.
#
# The record is emitted from the committed checklist
# -------------------------------------------------
# `read_checklist(DEFAULT_CHECKLIST)` supplies the definition, so the property
# drives the artifact a Maintainer actually works, and its shape is asserted
# against `default_definition()` — the shape the requirements fix — so a
# checklist that grew or lost a step fails here instead of silently narrowing
# what "every defined step" covers.
#
# Five clauses
# ------------
# (1) The gate over a bare outcome mapping: exactly the expected defect labels,
#     one finding each, every finding carrying `E_CHECKLIST_INCOMPLETE`, and
#     `tagAllowed` agreeing with the generator.
#
# (2) The round trip, through a file: rendering twice is byte-identical (the
#     module reads no clock), and the record read back off disk recovers every
#     step outcome, every platform cell, the notes, and the header facts.
#
# (3) The document and the mapping gate identically, including the JSON a
#     Maintainer or a CI step consumes.
#
# (4) The skeleton `emit` writes — every step present, every outcome
#     `_unrecorded_` — blocks tagging on all 23 recording slots, which is R6 AC3
#     read literally: an unrecorded outcome is a fail.
#
# (5) A platform cell absent from the mapping is neither written nor invented on
#     the way back, and is reported for that platform rather than for the step as
#     a whole *(R6 AC12)*.
#
# Deliberately out of scope: whether the committed checklist *documents* the
# steps R6 AC1 and AC4 through AC13 require is structural, asserted over the
# committed file in `test_structure.py`; whether the Power actually works on three
# operating systems is what the nine cells record and generated input cannot
# establish; and the CLI's exit codes are unit-test territory.

#: The `outcome_set()` cases this property relies on, so a generator change that
#: dropped one fails here instead of quietly narrowing the property.
_TESTRECORD_REQUIRED_OUTCOME_CASES = frozenset(
    {
        "complete_pass",
        "missing_step",
        "blank_outcome",
        "explicit_fail",
        "version_mismatch",
        "blank_platform_cell",
    }
)


@dataclass(frozen=True)
class _TestRecordHeader:
    """The header facts a record carries beside its outcomes *(R6 AC6)*.

    Sampled rather than drawn: these are the fields a reviewer reads to know
    *which* run the evidence came from, and what makes them interesting is
    non-ASCII prose and a pipe character, not arbitrary text.
    """

    template_release: str
    maintainer: str
    date: str
    validation_status: str


_TESTRECORD_HEADERS = (
    _TestRecordHeader("0.9.1", "Bob Smith", "2025-03-04", "passed"),
    _TestRecordHeader("1.0.0", "José Núñez", "2024-11-30", "passed with warnings"),
    _TestRecordHeader("2.13.7", "Release Ops | Duty", "2025-01-01", "failed"),
)

#: Per-step notes rendered into the record, over the steps that carry evidence
#: worth a sentence. A pipe, a backslash, and non-ASCII prose are included
#: because a note travels through a Markdown table cell.
_TESTRECORD_NOTES = {
    1: "ValidationReport passed | no warnings",
    5: "every ported skill activated on its trigger phrase",
    10: "re-run after the PreToolUse matcher fix; café",
    17: "installed under C:\\Users\\Bob Smith\\.venv\\python.exe",
}

#: Per-cell notes, one per platform, so the nine-cell matrix round-trips with its
#: evidence attached rather than as bare outcomes.
_TESTRECORD_CELL_NOTES = {
    "2.linux": "Ubuntu 24.04 | Add Custom Power",
    "10.macos": "hook fired on its declared trigger",
    "15.windows": "ported script ran from a quoted path",
}


@lru_cache(maxsize=1)
def _testrecord_definition() -> ChecklistDefinition:
    """The committed `Test_Checklist`, parsed once."""
    return read_checklist(DEFAULT_CHECKLIST)


def _testrecord_step_defect(step: int, outcome: str) -> str | None:
    """The defect one step-level outcome earns, or `None` when it is a pass.

    Written from R6 AC2's words — a *recorded pass*, nothing else — so a blank is
    a defect rather than the absence of one, and text in the outcome column that
    is neither a pass nor a fail is a defect too: a note is not an outcome.
    """
    if outcome == OUTCOME_PASS:
        return None
    if not outcome:
        return f"{REASON_BLANK_OUTCOME}:{step}"
    if outcome == OUTCOME_FAIL:
        return f"{REASON_FAIL}:{step}"
    return f"{REASON_UNRECOGNIZED}:{step}"


def _testrecord_cell_defect(step: int, platform: str, outcome: str) -> str | None:
    """The defect one per-platform cell earns, or `None` when it is a pass.

    Same reading as a step's, named per platform: R6 AC12 asks for an outcome
    recorded *on* each Supported_Platform, so an unrun platform is a fail on that
    platform rather than a fault of the step as a whole.
    """
    if outcome == OUTCOME_PASS:
        return None
    if not outcome:
        return f"{REASON_BLANK_CELL}:{step}:{platform}"
    if outcome == OUTCOME_FAIL:
        return f"{REASON_FAIL}:{step}:{platform}"
    return f"{REASON_UNRECOGNIZED}:{step}:{platform}"


def _testrecord_expected_defects(
    definition: ChecklistDefinition,
    outcomes: Mapping[int, Any],
    *,
    version: str,
    record_version: str,
) -> frozenset[str]:
    """Every reason tagging is blocked, computed from the acceptance criteria.

    The gate's own labels are not consulted: this walks the *definition* — every
    step it defines, every platform cell those steps own — and applies R6 AC2's
    requirement to each. A record that names a different version gates nothing,
    which is the one defect that belongs to no step.
    """
    defects: set[str] = set()
    if record_version != version:
        defects.add(REASON_VERSION_MISMATCH)
    for step in definition.steps:
        if step.number not in outcomes:
            defects.add(f"{REASON_MISSING_STEP}:{step.number}")
            continue
        recorded = outcomes[step.number]
        if not step.per_platform:
            defect = _testrecord_step_defect(
                step.number, str(recorded).strip().lower()
            )
            if defect is not None:
                defects.add(defect)
            continue
        for cell in step.platform_cells:
            if cell.key not in recorded:
                defects.add(f"{REASON_MISSING_CELL}:{step.number}:{cell.key}")
                continue
            defect = _testrecord_cell_defect(
                step.number, cell.key, str(recorded[cell.key]).strip().lower()
            )
            if defect is not None:
                defects.add(defect)
    return frozenset(defects)


def _testrecord_offending_steps(defects: Iterable[str]) -> frozenset[int]:
    """The step numbers a set of defect labels names.

    The version mismatch names no step, so it drops out here — which is what lets
    the generator's one-label-per-failed-step accounting be compared against the
    gate's one-label-per-failed-cell accounting.
    """
    steps: set[int] = set()
    for label in defects:
        parts = label.split(":")
        if len(parts) >= 2 and parts[1].isdigit():
            steps.add(int(parts[1]))
    return frozenset(steps)


# Feature: senzing-bootcamp-power, Property 23: The test record gates tagging and
# round-trips faithfully
#
# Validates: Requirements 6.2, 6.3, 6.6
@settings(max_examples=100)
@given(outcome_set(), st.sampled_from(_TESTRECORD_HEADERS))
def test_the_test_record_gates_tagging_and_round_trips_faithfully(
    case: OutcomeSet,
    header: _TestRecordHeader,
) -> None:
    # The generator cases this property draws from, asserted rather than assumed.
    assert _TESTRECORD_REQUIRED_OUTCOME_CASES <= set(OUTCOME_SET_CASES)

    # The record is emitted from the committed checklist, and its shape is the
    # one the requirements fix rather than whatever the file currently says.
    definition = _testrecord_definition()
    declared = default_definition()
    assert definition.step_numbers == declared.step_numbers
    assert definition.step_numbers == tuple(range(1, CHECKLIST_STEP_COUNT + 1))
    assert definition.platform_steps == PER_PLATFORM_STEPS
    assert definition.platform_cell_ids == declared.platform_cell_ids
    assert len(definition.platform_cell_ids) == len(PER_PLATFORM_STEPS) * len(
        SUPPORTED_PLATFORMS
    )
    assert len(definition.platform_cell_ids) == 9
    # Step 16 asserts the matrix is complete, but it is not itself a per-platform
    # step: the nine cells are the record of truth, so its own outcome grants
    # nothing that the cells have not already established.
    assert MATRIX_STEP not in PER_PLATFORM_STEPS
    matrix = definition.step(MATRIX_STEP)
    assert matrix is not None
    assert not matrix.per_platform

    expected = _testrecord_expected_defects(
        definition,
        case.outcomes,
        version=case.version,
        record_version=case.record_version,
    )
    # The generator's own verdict is a second opinion: it agrees on whether
    # tagging is open, and on which steps are at fault.
    assert (expected == frozenset()) == case.tag_allowed
    assert _testrecord_offending_steps(expected) == _testrecord_offending_steps(
        case.defects
    )

    # --- Clause 1: the gate over a bare outcome mapping ---------------------
    report = evaluate_outcomes(
        case.outcomes,
        version=case.version,
        record_version=case.record_version,
        definition=definition,
    )
    assert set(report.defects) == expected
    # Exactly the offending steps, no more and no fewer, and no defect reported
    # twice — one blank cell is one finding.
    assert len(report.findings) == len(expected)
    assert report.tag_allowed == case.tag_allowed
    assert report.error == (None if case.tag_allowed else E_CHECKLIST_INCOMPLETE)
    for finding in report.findings:
        assert finding.code == E_CHECKLIST_INCOMPLETE
        assert finding.message.strip()
    assert bool(report.findings_for(REASON_VERSION_MISMATCH)) == (
        case.record_version != case.version
    )

    # --- Clause 2: the round trip, through a file ---------------------------
    # Notes travel only for the steps and cells the record includes: a step
    # nobody ran carries no evidence to retain.
    notes = {
        step: note
        for step, note in _TESTRECORD_NOTES.items()
        if step in case.outcomes
    }
    cell_notes = {
        cell: note
        for cell, note in _TESTRECORD_CELL_NOTES.items()
        if int(cell.split(".", 1)[0]) in case.outcomes
    }

    def render() -> str:
        return render_record(
            definition,
            case.record_version,
            outcomes=case.outcomes,
            template_release=header.template_release,
            maintainer=header.maintainer,
            date=header.date,
            validation_status=header.validation_status,
            notes=notes,
            cell_notes=cell_notes,
        )

    text = render()
    # Reads no clock: the same inputs render the same bytes, which is what makes
    # a committed record reproducible from its own header.
    assert render() == text

    with tempfile.TemporaryDirectory() as temporary:
        location = write_record(
            text,
            Path(temporary) / RECORDS_DIRECTORY / f"{case.record_version}.md",
        )
        assert location.read_bytes() == text.encode("utf-8")
        parsed = read_record(location, definition=definition)

        # Every per-step outcome recovered identically, per-platform steps
        # included as one outcome per Supported_Platform.
        assert parsed.outcomes == case.outcomes
        assert {step.step for step in parsed.steps} == set(case.outcomes)
        recovered_cells = {
            cell.id for step in parsed.steps for cell in step.cells
        }
        assert recovered_cells == {
            cell.id
            for step in definition.steps
            for cell in step.platform_cells
            if step.number in case.outcomes
        }
        if set(PER_PLATFORM_STEPS) <= set(case.outcomes):
            assert len(recovered_cells) == 9
        # The evidence a reviewer reads beside the outcomes (R6 AC6).
        assert parsed.notes == notes
        assert parsed.cell_notes == cell_notes
        assert parsed.version == case.record_version
        assert parsed.template_release == header.template_release
        assert parsed.maintainer == header.maintainer
        assert parsed.date == header.date
        assert parsed.validation_status == header.validation_status
        assert parsed.format_version == RECORD_FORMAT_VERSION

        # --- Clause 3: the document and the mapping gate identically -------
        document = evaluate(parsed, version=case.version, definition=definition)
        assert set(document.defects) == expected
        assert document.defects == report.defects
        assert document.tag_allowed == case.tag_allowed
        assert document.error == report.error

        payload = document.to_json()
        assert payload["tagAllowed"] is case.tag_allowed
        assert payload["version"] == case.version
        assert payload["recordedVersion"] == case.record_version
        assert payload["recordFormatVersion"] == RECORD_FORMAT_VERSION
        assert [step["step"] for step in payload["steps"]] == sorted(case.outcomes)
        assert len(payload["platformCells"]) == len(recovered_cells)
        assert {finding["code"] for finding in payload["findings"]} <= {
            E_CHECKLIST_INCOMPLETE
        }
        if case.tag_allowed:
            assert "error" not in payload
        else:
            assert payload["error"] == E_CHECKLIST_INCOMPLETE
        assert E_CHECKLIST_INCOMPLETE in document.summary()

    # --- Clause 4: the skeleton a Maintainer starts from is closed ----------
    skeleton = parse_record(
        render_record(definition, case.version), definition=definition
    )
    blank: dict[int, Any] = {
        step.number: (
            {cell.key: "" for cell in step.platform_cells}
            if step.per_platform
            else ""
        )
        for step in definition.steps
    }
    assert skeleton.outcomes == blank
    skeleton_report = evaluate(
        skeleton, version=case.version, definition=definition
    )
    assert not skeleton_report.tag_allowed
    assert set(skeleton_report.defects) == _testrecord_expected_defects(
        definition, blank, version=case.version, record_version=case.version
    )
    # Every recording slot blocks: 14 single-outcome steps and nine cells.
    assert len(skeleton_report.findings) == (
        CHECKLIST_STEP_COUNT - len(PER_PLATFORM_STEPS) + 9
    )

    # --- Clause 5: an absent platform cell ---------------------------------
    if set(PER_PLATFORM_STEPS) <= set(case.outcomes):
        thinned = deepcopy(case.outcomes)
        matrix_step = PER_PLATFORM_STEPS[0]
        unrun = SUPPORTED_PLATFORMS[-1]
        del thinned[matrix_step][unrun]
        thinned_parsed = parse_record(
            render_record(definition, case.version, outcomes=thinned),
            definition=definition,
        )
        # Neither written nor invented on the way back.
        assert thinned_parsed.outcomes == thinned
        assert unrun not in thinned_parsed.outcomes[matrix_step]
        thinned_report = evaluate(
            thinned_parsed, version=case.version, definition=definition
        )
        assert set(thinned_report.defects) == _testrecord_expected_defects(
            definition, thinned, version=case.version, record_version=case.version
        )
        assert (
            f"{REASON_MISSING_CELL}:{matrix_step}:{unrun}" in thinned_report.defects
        )
        assert not thinned_report.tag_allowed


# ===========================================================================
# Property 24: Every generated hook command is absolute, correctly quoted, and
# shell-free
# ===========================================================================
#
# Kiro's hook schema takes a single `command` **string**. The template bought its
# no-shell guarantee with an exec-form `command` + `args` pair, and that shape
# cannot be reproduced here — so `INV-052` is honored rather than discounted by
# re-establishing the guarantee *inside one string*: the interpreter named by an
# absolute path resolved at install time from `sys.executable`, both paths
# quoted, and nothing in the string a shell would read as an operator *(R10 AC5,
# R16 AC3, AC4, AC5)*. Everything R16 asks of a Hook_Command_String is therefore
# a claim about one string-manipulation step over paths, which is where quoting
# and bare-name bugs actually live, and which generated input reaches and a
# hand-written example does not.
#
# Two halves, one property
# ------------------------
# The construction half is what the `Hook_Installer` emits; the reporting half is
# what the `Schema_Validator` says about emitted strings and about the
# `Build_Manifest`. They are one property because R16 AC6 and AC9 are the
# *contrapositive* of AC3 through AC5 and AC8: the construction rules are only
# worth stating if a violation of them is reported, and the reports are only
# worth stating if a compliant Power produces none. So "exactly the violating
# command strings and exactly the hash-mismatched files — no more, no fewer" is
# asserted in both directions on every example, over a Power that is otherwise
# real: `_base_power()`'s produced tree, carrying the authored definitions at
# both tiers and the installer that resolves them.
#
# The reference implementation is imported, and the oracles are not
# ------------------------------------------------------------------
# The validator loads the installer *out of the Power under validation* rather
# than reimplementing its quoting, deliberately: the question "what would the
# installer write?" has exactly one authority. This section binds the same copy
# — so the property drives the code a Bootcamper runs — and then judges its
# output against oracles that owe it nothing:
#
# * **the drawn vector.** `tokenize_command(build_command(i, (s,)))` has to be
#   `(i, s)`, and the oracle is the pair `interpreter_path()` drew, not anything
#   the installer computed *(R16 AC4)*.
# * **`shlex`.** A third-party POSIX tokenizer, run on every command whose paths
#   carry no backslash, has to recover the same two-element vector. That is the
#   independent confirmation that the installer's tokenizer and its quoter are
#   not mutually wrong. Backslash-bearing paths are excluded because the
#   installer documents the honest limit — POSIX double quotes treat `\` as an
#   escape and Windows does not, and the Windows reading is chosen, a backslash
#   in a path being the Windows norm and a POSIX rarity.
# * **operator conservation.** For every character a shell reads as an operator,
#   the emitted string carries exactly as many as the two paths do between them.
#   That says what R16 AC5 means without a second scanner: the assembly step
#   introduced no operator of its own, so a directory named `a&b|c;d>e` is data.
# * **absoluteness, spelled out.** A POSIX root, a UNC prefix, or a drive letter
#   followed by a separator — judged for *some* Supported_Platform, because the
#   gate runs on one platform and the Power runs on three. `os.path.isabs` would
#   call `C:\Python312\python.exe` relative from Linux, so it is not used.
# * **the manifest classifier.** Recorded-and-equal, recorded-and-absent,
#   recorded-and-different, and present-but-unrecorded, computed here from
#   `hashlib` and this section's own LF normalizer against R16 AC9's own words.
#
# What is seeded, and why the counts are declared
# -----------------------------------------------
# The violating command strings are a table, one per way R16 AC5 and AC6 can be
# broken: a bare interpreter name, each chaining operator, a pipe, a redirection,
# a shell builtin in the command position, unquoted placeholders, and a command
# already resolved inside a *shipped* asset — which is a violation precisely
# because the asset must ship the placeholder the installer resolves. Each entry
# declares the codes it owes **and how many findings**, because R16 AC6 asks for
# the offending definition *and the offending construct*: a chained command that
# also fails to tokenize into two arguments owes both faults named, not the
# first one. A drawn subset is seeded per example, so exactness is asserted over
# arbitrary combinations rather than only over the all-at-once case.
#
# One seed lands at **Tier 2**, where the installer half decides. A shipped asset
# is not runnable, so scanning only its text would leave the quoting rule — the
# rule a space in `C:\Users\Bob Smith\` actually breaks — unchecked; the check
# resolves each Tier 2 string across a fixed probe table instead, and that seed
# is owed one finding per probe.
#
# Deliberately out of scope: whether the Power *operates* on every platform is an
# aggregate outcome across three real operating systems that generated input
# cannot establish *(R16 AC1)* — checklist step 16's nine-cell matrix and step
# 17's space-in-path install do that, and this property tests the construction
# logic that makes it hold. Whether a hook's script *exists* is Property 11's;
# whether every template hook behavior stays reachable is Property 18's; whether
# the shipped assets carry the right triggers and filenames is structural. And
# whether `INV-052` belongs in the discount register at all is Property 25's —
# this section is the guarantee that keeps it out.
#
# `_base_power()`, `_validated`'s produced tree, `_json_bytes`, `_RESOLVED_TAG`,
# `_PORTED_OVERVIEW`, and `_LINKED_DOCUMENT` are shared with the sections above.

#: The two checks this property drives, and the requirements each is registered
#: for. Spelled here and asserted against the registry, so a check renamed or
#: re-attributed fails here rather than leaving the property driving nothing.
_HOOK_CHECK_ID = "hook-command-strings"
_MANIFEST_CHECK_ID = "manifest-hashes"
_HOOK_CHECK_REQUIREMENT = "10.5, 16.3, 16.4, 16.5, 16.6"
_MANIFEST_CHECK_REQUIREMENT = "16.8, 16.9"

#: The interpreter placeholder a shipped asset carries. The scripts-directory
#: placeholder is imported from the gate; this one lives in the installer, so it
#: is spelled here and asserted equal to the installer's own constant.
_PYTHON_PLACEHOLDER = "<ABSOLUTE_PYTHON>"

#: The interpreter names R16 AC3 forbids outright. `python3` is frequently absent
#: from PATH on Windows, and where it resolves it may hit a Store alias stub, so
#: none of these may ever appear in the command position *(R16 AC2)*.
_BARE_INTERPRETER_NAMES = ("python3", "python", "py")

#: Every character a shell reads as an operator, as a superset of the characters
#: the installer's own construct list is spelled from. Used for the conservation
#: claim rather than for a scan, so being a superset is safe.
_SHELL_OPERATOR_CHARACTERS = "&|;<>$(){}`\n\r"

#: The `interpreter_path()` cases this property relies on, so a generator change
#: that dropped one fails here instead of quietly narrowing the property.
_REQUIRED_INTERPRETER_CASES = frozenset(
    {
        "posix",
        "windows_drive_letter",
        "unc_prefix",
        "single_space",
        "repeated_spaces",
        "trailing_space",
        "embedded_quote",
        "shell_operator_chars",
        "all_shell_operator_chars",
    }
)


def _shipped_command(script: str) -> str:
    """The one shape a shipped `action.command` is allowed to take.

    Both placeholders, both quoted, interpreter first — which is the whole of
    what an asset may carry, since it is deliberately not runnable until the
    installer resolves them.
    """
    return f'"{_PYTHON_PLACEHOLDER}" "{SCRIPTS_DIR_PLACEHOLDER}/{script}"'


def _absolute_on_some_platform(value: str) -> bool:
    """R16 AC3's "absolute filesystem path", written for three platforms at once.

    A POSIX root, a UNC prefix, or a drive letter followed by either separator.
    Deliberately not `os.path.isabs`, which answers for the one platform the gate
    happens to be running on.
    """
    if value.startswith("/") or value.startswith("\\\\"):
        return True
    return (
        len(value) >= 3
        and value[0].isascii()
        and value[0].isalpha()
        and value[1] == ":"
        and value[2] in "\\/"
    )


def _bare_command_name(value: str) -> bool:
    """True when `value` is a command name PATH would have to resolve.

    A token carrying either separator is a path, well formed or not; anything
    else is a name, and a name is what R16 AC3 forbids in the command position.
    """
    return bool(value) and "/" not in value and "\\" not in value


def _operator_census(text: str) -> dict[str, int]:
    """How many of each shell-operator character `text` carries."""
    return {char: text.count(char) for char in _SHELL_OPERATOR_CHARACTERS}


def _split_trailing_component(path: str) -> tuple[str, str]:
    """Split a path of either flavor into its directory and its last component."""
    index = max(path.rfind("/"), path.rfind("\\"))
    assert index > 0, path
    return path[:index], path[index + 1 :]


def _joined_spellings(directory: str, relative: str) -> frozenset[str]:
    """The two ways a platform spells `relative` inside `directory`.

    The installer joins with the running platform's separator, and the gate runs
    on one platform while the paths it resolves come from three. So the claim
    made here is the one that holds regardless: the resolved argument is the
    scripts directory and the script name joined by *a* directory separator —
    stated instead of recomputing `Path.joinpath`, which would echo the code
    under test.
    """
    return frozenset({f"{directory}/{relative}", f"{directory}\\{relative}"})


@dataclass(frozen=True)
class _HookDefect:
    """One Hook_Command_String that breaks R16, and what the gate owes it.

    `codes` is the catalog set the string earns and `findings` is how many
    findings it earns, because R16 AC6 asks for the offending construct as well
    as the offending definition: a chained command that also fails to tokenize
    into `[interpreter, script]` owes both faults named. `constructs` is the
    construct each `E_SHELL_CONSTRUCT_IN_HOOK` finding has to name.
    """

    label: str
    command: str
    codes: frozenset[str]
    findings: int
    constructs: tuple[str, ...] = ()

    @property
    def hook_name(self) -> str:
        return f"{HOOK_FILENAME_PREFIX}{self.label}"

    @property
    def definition(self) -> str:
        return f"{TIER3_HOOKS_DIRECTORY}/{self.hook_name}.json"

    @property
    def document(self) -> dict[str, Any]:
        return {
            "version": "v1",
            "hooks": [
                {
                    "name": self.hook_name,
                    "trigger": "UserPromptSubmit",
                    "action": {"type": "command", "command": self.command},
                }
            ],
        }


_BOTH_HOOK_CODES = frozenset({E_SHELL_CONSTRUCT_IN_HOOK, E_BARE_INTERPRETER})
_BARE_ONLY = frozenset({E_BARE_INTERPRETER})

#: A compliant shipped string, and the script every seed points at. The seeds are
#: about the *command*, so they all name a script the produced Power really
#: carries and vary nothing else.
_SEED_SCRIPT = "write-gate.py"
_COMPLIANT_COMMAND = _shipped_command(_SEED_SCRIPT)

#: One seed per way R16 AC5 and AC6 can be broken. A tail appended after a
#: correct command is the shape a hand-edited hook actually reaches the gate in:
#: the command still looks right and the string no longer is.
_SHIPPED_DEFECTS: tuple[_HookDefect, ...] = (
    # R16 AC3: a name PATH would have to resolve, where the placeholder belongs.
    _HookDefect(
        label="bare-interpreter",
        command=_COMPLIANT_COMMAND.replace(
            _PYTHON_PLACEHOLDER, _BARE_INTERPRETER_NAMES[0]
        ),
        codes=_BARE_ONLY,
        findings=1,
    ),
    # R16 AC5: the three chaining operators, a pipe, and a redirection. Each also
    # pushes the string past two arguments and leaves its tail unquoted, so each
    # owes three findings rather than one.
    _HookDefect(
        label="chained-command",
        command=f"{_COMPLIANT_COMMAND} && echo done",
        codes=_BOTH_HOOK_CODES,
        findings=3,
        constructs=("&&",),
    ),
    _HookDefect(
        label="alternated-command",
        command=f"{_COMPLIANT_COMMAND} || true",
        codes=_BOTH_HOOK_CODES,
        findings=3,
        constructs=("||",),
    ),
    _HookDefect(
        label="sequenced-command",
        command=f"{_COMPLIANT_COMMAND} ; ls",
        codes=_BOTH_HOOK_CODES,
        findings=3,
        constructs=(";",),
    ),
    _HookDefect(
        label="piped-command",
        command=f"{_COMPLIANT_COMMAND} | tee run.log",
        codes=_BOTH_HOOK_CODES,
        findings=3,
        constructs=("|",),
    ),
    _HookDefect(
        label="redirected-command",
        command=f"{_COMPLIANT_COMMAND} > run.log",
        codes=_BOTH_HOOK_CODES,
        findings=3,
        constructs=(">",),
    ),
    # R16 AC5's "shell builtin invocation": a bare builtin in the command
    # position, which is also not the placeholder, so it owes both codes.
    _HookDefect(
        label="shell-builtin",
        command='"echo" "bootcamp"',
        codes=_BOTH_HOOK_CODES,
        findings=2,
        constructs=("echo",),
    ),
    # R16 AC4: the placeholders are there and neither is quoted, so a resolved
    # path containing a space would split into two arguments.
    _HookDefect(
        label="unquoted-placeholders",
        command=f"{_PYTHON_PLACEHOLDER} {SCRIPTS_DIR_PLACEHOLDER}/{_SEED_SCRIPT}",
        codes=_BARE_ONLY,
        findings=1,
    ),
    # A *correct-looking* resolved command, shipped. Wrong because the asset must
    # carry the placeholder: a baked-in interpreter path is one machine's answer.
    _HookDefect(
        label="resolved-in-shipped-asset",
        command=f'"/usr/bin/python3.12" "/srv/power/scripts/{_SEED_SCRIPT}"',
        codes=_BARE_ONLY,
        findings=1,
    ),
)

#: The Tier 2 seed's label. Kept out of `_SHIPPED_DEFECTS` because it replaces an
#: *authored* definition rather than adding one, and because the installer half
#: multiplies its findings by the probe table.
_TIER2_DEFECT_LABEL = "tier2-bare-interpreter"

_DEFECT_LABELS = tuple(defect.label for defect in _SHIPPED_DEFECTS) + (
    _TIER2_DEFECT_LABEL,
)

#: Resolved-shape strings, driven straight through the scan with the installed
#: origin. A tree-scanned entry is always shipped, so these three branches —
#: a bare name, a path that is not absolute, and space-bearing paths left
#: unquoted — are only reachable this way, and they are the branches that decide
#: R16 AC3 and AC4 for what an install actually writes.
_INSTALLED_DEFECTS: tuple[_HookDefect, ...] = (
    _HookDefect(
        label="installed-bare-interpreter-name",
        command=f'"python3" "/srv/power/scripts/{_SEED_SCRIPT}"',
        codes=_BARE_ONLY,
        findings=1,
    ),
    _HookDefect(
        label="installed-relative-interpreter-path",
        command=f'"./python3" "/srv/power/scripts/{_SEED_SCRIPT}"',
        codes=_BARE_ONLY,
        findings=1,
    ),
    _HookDefect(
        label="installed-unquoted-space-bearing-paths",
        command=(
            "/home/Bob Smith/.venv/bin/python3.12 "
            f"/home/Bob Smith/power/scripts/{_SEED_SCRIPT}"
        ),
        codes=_BARE_ONLY,
        findings=2,
    ),
)


@dataclass(frozen=True)
class _Drift:
    """One way a checkout and the `Build_Manifest` can disagree *(R16 AC9)*.

    `kind` is the report's vocabulary for where to look and `code` is what blocks
    the tag: a row that cannot supply a baseline is `E_CHECK_UNEVALUATED` rather
    than a mismatch, because nothing was compared and claiming a difference would
    assert a measurement never made.
    """

    label: str
    path: str
    kind: str
    code: str = E_HASH_MISMATCH


#: One seed per drift kind the report declares. The paths are real produced
#: files, asserted present below, so a renamed output fails as a missing fixture
#: rather than as a seed that quietly stopped being seeded.
_DRIFTS: tuple[_Drift, ...] = (
    # Bytes differ and normalizing line endings does not recover the recorded
    # hash, so the content itself changed.
    _Drift(label="content", path="LICENSE", kind=DRIFT_CONTENT),
    # CRLF on checkout: undoing the rewrite *demonstrably* reproduces the
    # recorded hash, which is what lets the finding name the cause outright.
    _Drift(
        label="line-endings", path=_PORTED_OVERVIEW, kind=DRIFT_LINE_ENDINGS
    ),
    # The same rewrite on a path `.gitattributes` holds back from normalization.
    # Nothing was allowed to rewrite its line endings, so a line-ending
    # explanation would be false and this has to land as content drift.
    _Drift(
        label="exempt-content",
        path="skills/bootcamp-onboarding/scripts/vendor/d3.v7.min.js",
        kind=DRIFT_CONTENT,
    ),
    # Recorded and not in the tree: no content to hash, so the comparison cannot
    # come out equal.
    _Drift(label="absent", path=_LINKED_DOCUMENT, kind=DRIFT_ABSENT),
    # In the tree and not recorded: no recorded hash to be compared against.
    _Drift(
        label="unrecorded",
        path="skills/bootcamp-onboarding/references/checked-out-late.md",
        kind=DRIFT_UNRECORDED,
    ),
    # A row that records a path and no hash. Reported once, and not a second time
    # as unrecorded.
    _Drift(
        label="unusable-record",
        path=PLUGIN_MANIFEST,
        kind=DRIFT_UNUSABLE_RECORD,
        code=E_CHECK_UNEVALUATED,
    ),
)

_DRIFTS_BY_LABEL: Mapping[str, _Drift] = {drift.label: drift for drift in _DRIFTS}
_DRIFT_LABELS = tuple(_DRIFTS_BY_LABEL)

#: Content added for the `unrecorded` seed. Any bytes serve; a document is used
#: so the added path is one a real checkout could plausibly carry.
_LATE_CHECKOUT_CONTENT = b"# Checked out late\n\nNot in the manifest.\n"

#: A check that found nothing, standing in for the rest of a passing run. With it
#: in the report, a withheld tag can only have come from the check under test.
_PASSING_HOOK_SIBLING = CheckResult(id="plugin-schema", target=PLUGIN_MANIFEST)


@lru_cache(maxsize=1)
def _base_tree() -> PowerTree:
    """The produced Power as the gate reads it. Built once; nothing mutates it."""
    return PowerTree.from_mapping(dict(_base_power().power))


@lru_cache(maxsize=1)
def _installer_tools() -> HookCommandTools:
    """The command-string vocabulary of the produced Power's own installer copy.

    Bound from the Power's bytes, the way the gate binds it, so this property
    drives the code a Bootcamper's install would run rather than a second
    implementation of the same quoting rule.
    """
    return load_hook_command_tools(_base_tree())


@lru_cache(maxsize=1)
def _shipped_definitions() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The produced Power's hook definitions, split into Tier 2 and Tier 3.

    Read through the gate's own discovery so the population this property judges
    is the population the check judges, and returned as a pair because Tier 3
    being a *copy* — never a behavior's only delivery path — is part of what the
    clause below asserts.
    """
    found = hook_definition_paths(_base_tree(), hook_definition_glob(_base_tree()))
    return (
        tuple(path for path in found if path.startswith(f"{HOOK_ASSETS_DIRECTORY}/")),
        tuple(path for path in found if path.startswith(f"{TIER3_HOOKS_DIRECTORY}/")),
    )


def _sha256(data: bytes) -> str:
    """This section's own digest, so the comparison has an outside opinion."""
    return hashlib.sha256(data).hexdigest()


def _lf_normalized(data: bytes) -> bytes:
    """CRLF and lone CR rewritten to LF — the rewrite a checkout can perform."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _exempt_from_normalization(path: str) -> bool:
    """True when `.gitattributes` holds `path` back from line-ending rewriting.

    Written from the declaration's own patterns (`*.png binary`, `*.min.js
    -text`), matched at any depth the way a git attribute pattern without a slash
    is. These are the paths R10 AC3 requires byte-for-byte, so nothing normalizes
    them and a line-ending diagnosis for one of them would be wrong.
    """
    return any(
        path.split("/")[-1].endswith(pattern.lstrip("*"))
        for pattern in NORMALIZATION_EXEMPT_PATTERNS
    )


def _reference_drift(
    document: Mapping[str, Any], files: Mapping[str, bytes]
) -> frozenset[tuple[str, str]]:
    """Every `(path, kind)` R16 AC9 owes, computed from the manifest and the tree.

    This section's own classifier, written from the criterion's words against
    `hashlib` and `_lf_normalized`: recorded and equal is silence, recorded and
    absent has nothing to hash, recorded and different is a mismatch whose cause
    is line endings only when undoing the rewrite recovers the recorded hash, and
    present but unrecorded has no baseline. The manifest cannot record its own
    hash, so it is the one legitimate absence and nothing else is.
    """
    owed: set[tuple[str, str]] = set()
    recorded: dict[str, str] = {}
    for row in document["files"]:
        path = row["path"]
        digest = row.get("sha256")
        if not isinstance(digest, str) or not digest.strip():
            owed.add((path, DRIFT_UNUSABLE_RECORD))
            recorded[path] = ""
            continue
        recorded[path] = digest.strip().lower()

    for path, digest in recorded.items():
        if not digest:
            continue
        data = files.get(path)
        if data is None:
            owed.add((path, DRIFT_ABSENT))
            continue
        actual = _sha256(data)
        if actual == digest:
            continue
        rewritten = (
            not _exempt_from_normalization(path)
            and _sha256(_lf_normalized(data)) == digest
        )
        owed.add((path, DRIFT_LINE_ENDINGS if rewritten else DRIFT_CONTENT))

    for path in files:
        if path not in recorded and path not in MANIFEST_UNRECORDED:
            owed.add((path, DRIFT_UNRECORDED))
    return frozenset(owed)


def _tier2_definition(script: str) -> str:
    """Where the Tier 2 asset for `script` sits in the produced Power."""
    stem = script[: -len(SCRIPT_SUFFIX)]
    return f"{HOOK_ASSETS_DIRECTORY}/{HOOK_FILENAME_PREFIX}{stem}.json"


def _hook_command_of(files: Mapping[str, bytes], definition: str) -> tuple[str, str]:
    """The hook name and command string one definition's single hook declares."""
    document = json.loads(files[definition].decode("utf-8"))
    hooks = document["hooks"]
    assert len(hooks) == 1, definition
    return hooks[0]["name"], hooks[0]["action"]["command"]


def _with_command(files: dict[str, bytes], definition: str, command: str) -> None:
    """Replace one definition's command string, leaving everything else alone."""
    document = json.loads(files[definition].decode("utf-8"))
    document["hooks"][0]["action"]["command"] = command
    files[definition] = _json_bytes(document)


def _assert_the_installer_emits_a_portable_command(
    tools: HookCommandTools, interpreter: str, script: str
) -> str:
    """One assembled command, judged against every oracle but the installer's.

    R16 AC3, AC4 and AC5 in one place: the vector goes in, the string comes out,
    and the string has to name the absolute interpreter, tokenize back to exactly
    that vector, and carry no shell operator the paths did not already carry.
    """
    command = tools.build_command(interpreter, (script,))
    # Pure: the same vector assembles the same string every time, which is what
    # makes the installer's idempotence observable at all *(R7 AC8)*.
    assert tools.build_command(interpreter, (script,)) == command

    # R16 AC3: an absolute path, never a name PATH would resolve — and the gate
    # reads it the same way this section does.
    assert _absolute_on_some_platform(interpreter)
    assert is_absolute_command_path(interpreter) is True
    assert not _bare_command_name(interpreter)
    assert names_bare_interpreter(interpreter) is False
    assert interpreter not in _BARE_INTERPRETER_NAMES
    assert shell_builtin_named(interpreter) is None

    # R16 AC4: tokenizing recovers exactly `[interpreter, script]`, so neither a
    # space, a repeated space, a trailing space nor an embedded quote can split
    # either path. The oracle is the drawn pair.
    assert tools.tokenize_command(command) == (interpreter, script)

    # An outside tokenizer agrees, wherever a single string can be both POSIX-
    # and Windows-correct. A backslash cannot be, and the installer says so.
    if "\\" not in interpreter and "\\" not in script:
        assert shlex.split(command) == [interpreter, script]

    # R16 AC5: the assembly introduced no shell operator of its own, so every one
    # the string carries is a character of a path and is inside a quoted span.
    assert _operator_census(command) == {
        char: count + _operator_census(script)[char]
        for char, count in _operator_census(interpreter).items()
    }
    assert tools.find_shell_constructs(command) == ()
    assert tools.unquoted_remainder(command).strip() == ""
    return command


def _assert_reports_exactly_these(
    result: CheckResult,
    *,
    owed: frozenset[tuple[Any, ...]],
    observed: Callable[[Finding], tuple[Any, ...]],
    findings: int,
) -> None:
    """One recorded result, carrying exactly `owed` and exactly `findings` of them.

    Both halves of "no more, no fewer": the reported set equals the owed set, and
    the count matches, so a reader that named the first offender and stopped, or
    named one twice, fails here rather than passing on the set alone.
    """
    assert {observed(finding) for finding in result.findings} == owed
    assert len(result.findings) == findings


def _assert_gate_follows_from(result: CheckResult) -> None:
    """The recorded result and the release gate follow from the findings alone."""
    clean = result.findings == ()
    assert result.result == (RESULT_PASS if clean else RESULT_FAIL)
    assert result.passed is clean
    report = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_PASSING_HOOK_SIBLING, result),
    )
    assert _PASSING_HOOK_SIBLING.passed
    assert report.status == (STATUS_PASSED if clean else STATUS_FAILED)
    assert report.tag_allowed is clean
    assert report.failed_check_ids() == (() if clean else (result.id,))


def _assert_no_baseline_fails_closed(
    check_id: str, code: str, context: ValidationContext, *, missing: str
) -> None:
    """A check with nothing to compare against records a fail, not a pass.

    Raising is half of failing closed. The recorded result has to be a fail and
    the tag has to stay withheld, or a Power carrying no hook definition — or no
    `Build_Manifest` — would pass a comparison that never happened.
    """
    check = registered_check(check_id)
    assert check is not None
    with pytest.raises(Unevaluable) as raised:
        check.run(context)
    assert raised.value.message

    report = run_checks(context, checks=(check_id,))
    recorded = report.results_for(check_id)
    assert len(recorded) == 1
    assert recorded[0].result == RESULT_FAIL
    assert len(recorded[0].findings) == 1
    assert recorded[0].findings[0].code == code
    assert recorded[0].findings[0].details["unevaluated"] is True
    assert report.status == STATUS_FAILED
    assert report.tag_allowed is False, missing


# Feature: senzing-bootcamp-power, Property 24: Every generated hook command is
# absolute, correctly quoted, and shell-free
#
# Validates: Requirements 10.5, 16.3, 16.4, 16.5, 16.6
@settings(max_examples=100)
@given(
    interpreter_path(),
    st.sets(st.sampled_from(_DEFECT_LABELS)),
    st.sets(st.sampled_from(_DRIFT_LABELS)),
)
def test_every_generated_hook_command_is_absolute_quoted_and_shell_free(
    case: InterpreterPathCase,
    seeded_defects: set[str],
    seeded_drifts: set[str],
) -> None:
    # The generator cases this property draws from, asserted rather than assumed.
    assert _REQUIRED_INTERPRETER_CASES <= set(INTERPRETER_PATH_CASES)
    assert case.flavor in PATH_FLAVORS
    scripts_directory, script_name = _split_trailing_component(case.script)
    assert script_name in HOOK_SCRIPT_NAMES

    base = _base_power()
    tools = _installer_tools()
    # The placeholders this section spells are the installer's own, so a rename
    # on either side fails here rather than leaving the seeds testing nothing.
    assert tools.placeholder_interpreter == _PYTHON_PLACEHOLDER
    assert tools.placeholder_scripts_dir == SCRIPTS_DIR_PLACEHOLDER
    assert tools.hook_filename_prefix == HOOK_FILENAME_PREFIX
    assert tools.source == HOOK_INSTALLER_SCRIPT
    # This section's operator set covers the vocabulary the gate scans for.
    assert set("".join(tools.shell_constructs)) <= set(_SHELL_OPERATOR_CHARACTERS)
    assert set(_BARE_INTERPRETER_NAMES) & SHELL_BUILTINS == set()

    # Both checks are registered for the requirements this property validates.
    for check_id, requirement in (
        (_HOOK_CHECK_ID, _HOOK_CHECK_REQUIREMENT),
        (_MANIFEST_CHECK_ID, _MANIFEST_CHECK_REQUIREMENT),
    ):
        check = registered_check(check_id)
        assert check is not None
        assert check.requirement == requirement
        assert check_id in DECLARED_CHECKS
    assert registered_check(_HOOK_CHECK_ID).code == E_SHELL_CONSTRUCT_IN_HOOK
    assert registered_check(_MANIFEST_CHECK_ID).code == E_HASH_MISMATCH
    assert MANIFEST_DRIFT_KINDS == tuple(
        dict.fromkeys(drift.kind for drift in _DRIFTS)
    )

    # --- Clause 1: the command the installer assembles ----------------------
    command = _assert_the_installer_emits_a_portable_command(
        tools, case.interpreter, case.script
    )
    # Both paths quoted is a property of the whole string, not two spot checks:
    # outside the quoted spans there is nothing but the separator between them.
    assert command.startswith('"') and command.endswith('"')
    assert tools.unquoted_remainder(command) == " "

    # --- Clause 2: what an install would write from the shipped assets ------
    tier2, tier3 = _shipped_definitions()
    assert tier2
    # Tier 3 carries the same definition set, so neither tier is the only place a
    # command string is checked.
    assert tuple(path.rsplit("/", 1)[1] for path in tier2) == tuple(
        path.rsplit("/", 1)[1] for path in tier3
    )
    assert _tier2_definition(script_name) in tier2

    for definition in tier2:
        hook_name, shipped = _hook_command_of(base.power, definition)
        entry = HookCommand(
            definition=definition, hook_name=hook_name, index=0, command=shipped
        )
        assert entry.origin == ORIGIN_SHIPPED
        assert entry.resolved is False
        assert entry.location == "hooks[0].action.command"
        # The gate's own reader finds the same one command string, and finds
        # nothing wrong with the definition's shape on the way to it.
        found, shape = hook_commands(
            json.loads(base.power[definition].decode("utf-8")), definition
        )
        assert shape == ()
        assert found == (entry,)
        # The asset ships the two placeholders, both quoted, and nothing else, so
        # it is deliberately not runnable until the installer resolves them.
        shipped_tokens = tools.tokenize_command(shipped)
        assert len(shipped_tokens) == 2
        assert shipped_tokens[0] == _PYTHON_PLACEHOLDER
        declared_script = shipped_tokens[1].removeprefix(
            f"{SCRIPTS_DIR_PLACEHOLDER}/"
        )
        assert declared_script in HOOK_SCRIPT_NAMES
        assert shipped == _shipped_command(declared_script)
        # No interpreter name reaches the command position, at either tier.
        assert not any(token in _BARE_INTERPRETER_NAMES for token in shipped_tokens)
        assert base.power[definition] == base.power[
            f"{TIER3_HOOKS_DIRECTORY}/{definition.rsplit('/', 1)[1]}"
        ]
        # A shipped string is scanned with its placeholders removed, because they
        # are spelled with angle brackets a redirection scan would otherwise
        # report on every correct definition.
        assert tools.find_shell_constructs(
            strip_command_placeholders(tools, shipped)
        ) == ()
        assert hook_command_findings(tools, entry) == ()
        assert installer_findings(tools, entry) == ()

        # Resolved against the drawn paths, which is the install that matters.
        resolved, named = tools.resolve_command(
            shipped,
            interpreter=case.interpreter,
            scripts_directory=scripts_directory,
        )
        assert len(named) == 1
        assert named[0] in HOOK_SCRIPT_NAMES
        assert _PYTHON_PLACEHOLDER not in resolved
        assert SCRIPTS_DIR_PLACEHOLDER not in resolved
        tokens = tools.tokenize_command(resolved)
        assert len(tokens) == 2
        assert tokens[0] == case.interpreter
        assert tokens[1] in _joined_spellings(scripts_directory, named[0])
        assert _operator_census(resolved) == {
            char: count + _operator_census(tokens[1])[char]
            for char, count in _operator_census(case.interpreter).items()
        }
        assert tools.find_shell_constructs(resolved) == ()
        installed = HookCommand(
            definition=definition,
            hook_name=hook_name,
            index=0,
            command=resolved,
            origin=ORIGIN_INSTALLED,
            probe=case.flavor,
        )
        assert installed.resolved is True
        assert hook_command_findings(tools, installed) == ()

    # --- Clause 3: exactly the violating command strings --------------------
    # Every seed, every example, through the pure scan: one run has to name all
    # of them and each has to name its own construct. The shipped seeds are
    # scanned as an asset ships them; the installed seeds carry the resolved
    # origin, which is the only way the absolute-path branches are reachable.
    for defect, origin in itertools.chain(
        ((defect, ORIGIN_SHIPPED) for defect in _SHIPPED_DEFECTS),
        ((defect, ORIGIN_INSTALLED) for defect in _INSTALLED_DEFECTS),
    ):
        entry = HookCommand(
            definition=defect.definition,
            hook_name=defect.hook_name,
            index=0,
            command=defect.command,
            origin=origin,
        )
        found = hook_command_findings(tools, entry)
        assert {finding.code for finding in found} == defect.codes, defect.label
        assert len(found) == defect.findings, defect.label
        assert tuple(
            finding.details["construct"]
            for finding in found
            if finding.code == E_SHELL_CONSTRUCT_IN_HOOK
        ) == defect.constructs, defect.label
        for finding in found:
            # R16 AC6: the offending definition, the offending hook, and — where
            # there is one — the offending construct, all named.
            assert finding.severity == SEVERITY_ERROR
            assert finding.target == defect.definition
            assert finding.location == "hooks[0].action.command"
            assert defect.hook_name in finding.message
            assert defect.definition in finding.message
            assert finding.details["hook"] == defect.hook_name
            assert finding.details["origin"] == origin
            assert finding.details["command"] == defect.command
            payload = finding.to_json()
            assert payload["code"] == finding.code
            assert payload["target"] == defect.definition
        for construct in defect.constructs:
            assert any(
                repr(construct) in finding.message
                for finding in found
                if finding.code == E_SHELL_CONSTRUCT_IN_HOOK
            ), construct

    # A Tier 2 seed the installer cannot resolve is reported once per probe, so
    # the population that decides R16 AC3 and AC4 at runtime is not sampled.
    tier2_target = _tier2_definition(script_name)
    tier2_hook, _ = _hook_command_of(base.power, tier2_target)
    tier2_entry = HookCommand(
        definition=tier2_target,
        hook_name=tier2_hook,
        index=0,
        command=_SHIPPED_DEFECTS[0].command,
    )
    probe_findings = installer_findings(tools, tier2_entry)
    assert len(probe_findings) == len(INSTALLER_PROBES)
    assert {finding.code for finding in probe_findings} == _BARE_ONLY
    assert {finding.details["probe"] for finding in probe_findings} == {
        probe.label for probe in INSTALLER_PROBES
    }
    assert all(
        finding.details["origin"] == ORIGIN_INSTALLED for finding in probe_findings
    )
    # The fixed probe table and the generator agree on what "hard" means: every
    # probe resolves an absolute interpreter, and all three path flavors are in it.
    assert all(
        _absolute_on_some_platform(probe.interpreter)
        and _absolute_on_some_platform(probe.scripts_directory)
        for probe in INSTALLER_PROBES
    )
    assert {"posix", "windows-drive-letter", "unc-prefix"} <= {
        probe.label for probe in INSTALLER_PROBES
    }

    # The registered check, over the produced Power with the drawn seeds in it.
    seeded = dict(base.power)
    owed_commands: set[tuple[str, str, str]] = set()
    seeded_findings = 0
    for label in sorted(seeded_defects):
        if label == _TIER2_DEFECT_LABEL:
            _with_command(seeded, tier2_target, _SHIPPED_DEFECTS[0].command)
            owed_commands.add((tier2_target, tier2_hook, E_BARE_INTERPRETER))
            seeded_findings += 1 + len(INSTALLER_PROBES)
            continue
        defect = next(item for item in _SHIPPED_DEFECTS if item.label == label)
        seeded[defect.definition] = _json_bytes(defect.document)
        owed_commands.update(
            (defect.definition, defect.hook_name, code) for code in defect.codes
        )
        seeded_findings += defect.findings

    hook_result = check_hook_command_strings(
        ValidationContext(
            tree=PowerTree.from_mapping(seeded),
            tag=_RESOLVED_TAG,
            contract=base.contract,
        )
    )
    assert hook_result.id == _HOOK_CHECK_ID
    assert hook_result.target == HOOK_DEFINITION_TARGET
    _assert_reports_exactly_these(
        hook_result,
        owed=frozenset(owed_commands),
        observed=lambda finding: (
            finding.target,
            finding.details["hook"],
            finding.code,
        ),
        findings=seeded_findings,
    )
    # Nothing from a compliant definition: every reported definition is one a
    # seed put there.
    assert {finding.target for finding in hook_result.findings} == {
        definition for definition, _, _ in owed_commands
    }
    assert hook_result.extra["hookDefinitionGlob"] == DEFAULT_HOOK_DEFINITION_GLOB
    assert HOOK_COVERAGE_MAP not in hook_result.extra["definitions"]
    assert hook_result.extra["installerProbes"] == len(INSTALLER_PROBES)
    assert len(hook_result.extra["violations"]) == len(hook_result.findings)
    _assert_gate_follows_from(hook_result)

    # --- Clause 4: exactly the hash-mismatched files ------------------------
    for drift in _DRIFTS:
        if drift.kind == DRIFT_UNRECORDED:
            assert drift.path not in base.power, drift.path
        else:
            assert drift.path in base.power, drift.path

    drifted = dict(base.power)
    document = json.loads(drifted[BUILD_MANIFEST].decode("utf-8"))
    declared: set[tuple[str, str]] = set()
    for label in sorted(seeded_drifts):
        drift = _DRIFTS_BY_LABEL[label]
        declared.add((drift.path, drift.kind))
        if label == "content":
            drifted[drift.path] = drifted[drift.path] + b"\n"
        elif label in ("line-endings", "exempt-content"):
            drifted[drift.path] = drifted[drift.path].replace(b"\n", b"\r\n")
        elif label == "absent":
            del drifted[drift.path]
        elif label == "unrecorded":
            drifted[drift.path] = _LATE_CHECKOUT_CONTENT
        else:
            for row in document["files"]:
                if row["path"] == drift.path:
                    row["sha256"] = ""
            drifted[BUILD_MANIFEST] = _json_bytes(document)

    # Two oracles, and neither asks the gate what it expected: the seed table
    # declares what was planted, and the classifier reads the manifest and the
    # tree back.
    owed_files = _reference_drift(document, drifted)
    assert owed_files == frozenset(declared)

    comparison = compare_manifest(document, drifted)
    assert {
        (finding.target, finding.details["kind"]) for finding in comparison.findings
    } == owed_files
    assert len(comparison.findings) == len(owed_files)
    # Every recorded file present in the tree was hashed, and every one the seeds
    # left alone matched — so "no mismatches" is a verdict over the whole tree
    # rather than an omission, and the count says how many files it covers.
    present = {
        record.path
        for record in comparison.manifest.records
        if record.path in drifted
    }
    assert set(comparison.compared) == present
    assert set(comparison.matched) == present - {path for path, _ in owed_files}
    # The manifest a Maintainer is pointed back at names the release it recorded,
    # and every row says what produced its file.
    assert comparison.manifest.template_release == _RESOLVED_TAG
    assert comparison.manifest.manifest_version == MANIFEST_VERSION
    assert {record.owner for record in comparison.manifest.records} <= {
        OWNER_TEMPLATE,
        OWNER_KIRO,
    }

    manifest_result = check_manifest_hashes(
        ValidationContext(
            tree=PowerTree.from_mapping(drifted),
            tag=_RESOLVED_TAG,
            contract=base.contract,
        )
    )
    assert manifest_result.id == _MANIFEST_CHECK_ID
    _assert_reports_exactly_these(
        manifest_result,
        owed=frozenset(owed_files),
        observed=lambda finding: (finding.target, finding.details["kind"]),
        findings=len(owed_files),
    )
    for finding in manifest_result.findings:
        kind = finding.details["kind"]
        assert finding.code == _DRIFTS_BY_LABEL[
            next(item.label for item in _DRIFTS if item.path == finding.target)
        ].code
        assert finding.severity == SEVERITY_ERROR
        assert finding.target in {path for path, _ in owed_files}
        # R16 AC8: every mismatch points a Maintainer at the declaration whose
        # absence is the usual cause — except where that path is exempt from
        # normalization, which is the one case the explanation would be false.
        if kind in (DRIFT_CONTENT, DRIFT_LINE_ENDINGS, DRIFT_ABSENT):
            assert GITATTRIBUTES in finding.message
        if kind == DRIFT_LINE_ENDINGS:
            assert LINE_ENDING_DECLARATION in finding.message
            assert is_line_ending_rewrite(
                drifted[finding.target],
                finding.details["recordedSha256"],
                finding.target,
            )
        if kind == DRIFT_CONTENT and normalization_exempt(finding.target):
            assert _exempt_from_normalization(finding.target)
            assert not is_line_ending_rewrite(
                drifted[finding.target],
                finding.details["recordedSha256"],
                finding.target,
            )
    assert manifest_result.extra["manifest"] == BUILD_MANIFEST
    assert manifest_result.extra["matched"] == len(comparison.matched)
    assert len(manifest_result.extra["mismatches"]) == len(manifest_result.findings)
    _assert_gate_follows_from(manifest_result)

    # --- Clause 5: the produced Power passes both, and fails closed --------
    clean = run_checks(
        ValidationContext(
            tree=_base_tree(),
            tag=_RESOLVED_TAG,
            contract=base.contract,
            source=base.release,
        ),
        checks=(_HOOK_CHECK_ID, _MANIFEST_CHECK_ID),
    )
    assert [result.result for result in clean.checks] == [RESULT_PASS, RESULT_PASS]
    assert clean.findings == ()
    assert clean.status == STATUS_PASSED
    assert clean.tag_allowed is True
    # And the seeded run withholds the tag whenever either half found anything.
    assert fold_status((hook_result, manifest_result)) == (
        STATUS_PASSED
        if not hook_result.findings and not manifest_result.findings
        else STATUS_FAILED
    )

    stripped = {
        path: content
        for path, content in base.power.items()
        if path not in tier2 + tier3
    }
    assert HOOK_INSTALLER_SCRIPT in stripped
    _assert_no_baseline_fails_closed(
        _HOOK_CHECK_ID,
        E_SHELL_CONSTRUCT_IN_HOOK,
        ValidationContext(
            tree=PowerTree.from_mapping(stripped),
            tag=_RESOLVED_TAG,
            contract=base.contract,
        ),
        missing="any hook definition in the produced Power",
    )
    _assert_no_baseline_fails_closed(
        _MANIFEST_CHECK_ID,
        E_HASH_MISMATCH,
        ValidationContext(
            tree=PowerTree.from_mapping(
                {
                    path: content
                    for path, content in base.power.items()
                    if path != BUILD_MANIFEST
                }
            ),
            tag=_RESOLVED_TAG,
            contract=base.contract,
        ),
        missing="the Build_Manifest the produced Power records its hashes in",
    )


# ===========================================================================
# Property 25: The discount register is complete, excludes INV-052, and
# invariant citations survive untouched
# ===========================================================================
#
# R15 is where a *judgment* enters the pipeline. Everywhere else the contract
# declares a mechanical fact — this glob, that destination, these substitution
# sets — but a discount says "honoring this Template_Invariant as written would
# have prevented correct Kiro construction, so it was not honored". Nothing
# downstream can recompute that. All a gate can do is keep the record of the
# judgment honest and keep the prose that cites it intact, and those are exactly
# the three claims driven here, over one property because they are one
# arrangement: the register says what was given up, and the citations are what
# was not.
#
# (a) The register is complete
# ---------------------------
# Every entry carries a non-empty `invariant`, `conflictsWith`, and `resolution`
# *(R15 AC4)*, and an entry lacking one is reported **per entry and per missing
# field** *(R15 AC5)*. The per-field half is the load-bearing one: a Maintainer
# told "entry 2 is incomplete" writes one of the two fields that entry owes and
# runs the gate again. So the findings are compared against the set of
# `(entry, field, kind)` triples the register owes — no more, no fewer, and not a
# prefix — and a composite register carrying every flavor of defect at once is
# driven in a single run, because a register with four bad entries has to name
# four.
#
# (b) `INV-052` never appears, under any spelling
# ----------------------------------------------
# `INV-052` is **honored**, not discounted. Its exec-form wording cannot be
# reproduced under Kiro's single-command-string hook schema, but the invariant
# does not state a wording — it states a guarantee, that hook execution depends
# on no shell — and that guarantee is preserved, restated in a Kiro mechanism, by
# install-time absolute-path interpreter resolution *(R16 AC3, AC4)*. That is
# R15 AC3's "retain as honored" case rather than R15 AC2's "discount" case, so an
# entry for it is wrong by construction rather than merely redundant: it records
# as abandoned a protection the Power actually keeps *(R15 AC6)*.
#
# The exclusion therefore folds spelling — `inv-052`, `INV-052 `, and `INV- 052`
# are one invariant — while `INV-52` is a **different** invariant that stays
# perfectly valid in the register. Both directions are asserted, because an
# exclusion that over-folded would reject a legitimate discount and one that
# under-folded would admit the single entry R15 AC6 forbids. The fold is one step
# stronger than the update path's, which trims rather than collapsing interior
# whitespace, and the difference is visible in the report: the `discounted` array
# spells an identifier the way the drift comparison reads it, while the exclusion
# matches under the stronger fold. Both are stated here rather than left to agree
# by accident.
#
# (c) Citations survive, and are not residual references
# -----------------------------------------------------
# R15 AC7 and AC8 are the other side of the same coin. A discount is about
# *packaging construction*; it says nothing about what ported prose may cite. So a
# bootcamp module that explains why `INV-072` mattered still says `INV-072` after
# the port — the citation of a discounted invariant is preserved exactly like any
# other — and the residual-reference gate treats such a citation as compliant
# content rather than as a Claude-specific leftover *(R15 AC8)*.
#
# The preservation half runs the **real engine** over generated prose: probes are
# planted into a drawn template tree at destinations the contract claims with
# `substitute` and `skill` rules, the tree is ported, and the citation sequence of
# every ported text output is compared against its source's. One probe pairs a
# citation with a term a declared set really does rewrite, so "the citation
# survived" is measured across an edit that happened beside it rather than over
# text nothing touched.
#
# The exemption half is the sharper claim, and it is stated as a *difference*
# rather than as an absence. Masking every citation in a document changes nothing
# the scan reports — same kinds, same terms, same matched text — which says at
# once that a citation is never itself a hit and never shields the reference next
# to it. The seeded documents put the two together in every way that matters: a
# citation before a residual on one line, after it on another, both inside a code
# fence, and two citations on a line that also carries a genuine reference. And
# because "reports zero citations" would be satisfiable by a scanner that reported
# nothing at all, the same documents are asserted to report every genuine residual
# reference, in document order.
#
# The two oracles
# ---------------
# Each half of the register claim is computed twice, independently, and neither
# oracle asks the validator what it expected. `_reference_incomplete` and
# `_reference_disallowed` read the register and apply R15 AC4 and AC6 against this
# section's own literals and its own fold. `_labeled_incomplete` and
# `_labeled_disallowed` read `discount_register()`'s defect labels instead — the
# biconditional the strategies module documents, where the empty tuple means "no
# defect" — and a label this section does not describe raises rather than passing
# quietly.
#
# The committed register
# ---------------------
# The generated registers establish the rule; the checked-in `contract.yaml` is
# what actually ships. Its register is asserted to pass and to name no `INV-052`
# entry, so the two claims are made about the artifact and not only about
# generated input. Today it is the empty list — nothing is discounted — and that
# is a verdict rather than an absence, which is why a contract that lost the
# section fails closed instead of being read as a register that discounts nothing.
#
# Deliberately out of scope: whether an invariant "encodes a guarantee" or a
# packaging quirk is a reading judgment and belongs to design review *(R15 AC1,
# AC2, AC3)*; the no-shell guarantee INV-052 states is enforced by Property 24's
# command-string checks; flagging a discount whose subject was reworded upstream
# *(R15 AC10)* is mock-free unit-test territory because it is a comparison between
# two releases rather than a claim over generated input; and what the engine does
# with a declared substitution set is Property 8's.
#
# `_CITATION`, `_RESOLVED_TAG`, `_transformable`, `_materialized_release`,
# `_read_tree`, `_lf`, and `_is_skill_entry_point` are shared with the sections
# above.

#: The check this property drives, and the requirement pair it is registered for.
_DISCOUNT_CHECK_ID = "invariant-discounts"
_DISCOUNT_REQUIREMENT = "15.5, 15.6"

#: The contract key R15 AC11 keeps the register under, and the three fields
#: R15 AC4 requires of an entry, in the order a finding reports them. Spelled
#: here, and asserted equal to the gate's copies rather than imported from them.
_REGISTER_KEY = "invariantDiscounts"
_REQUIRED_ENTRY_FIELDS = ("invariant", "conflictsWith", "resolution")

#: The Template_Invariant R16 preserves rather than discounts *(R15 AC3, AC6)*.
_HONORED = "INV-052"

#: Spellings of the honored invariant the exclusion has to fold together. Interior
#: whitespace is in this list deliberately: a register line reading `INV- 052` is
#: the same judgment written carelessly, and admitting it would admit the entry
#: R15 AC6 forbids.
_HONORED_SPELLINGS = (
    "INV-052",
    "inv-052",
    "Inv-052",
    "INV-052 ",
    " INV-052",
    "INV- 052",
    "\tINV-052\n",
)

#: Identifiers that read like the honored one and are *different invariants*. The
#: digit count is part of an identifier, so each of these stays a legitimate
#: discount and rejecting one would lose a real judgment.
_DIFFERENT_INVARIANTS = ("INV-52", "INV-0052", "INV-152", "INV-05")

#: The `discount_register()` cases this property relies on, so a generator change
#: that dropped one fails here instead of quietly narrowing the property.
_REQUIRED_REGISTER_CASES = frozenset(
    {
        "empty",
        "valid",
        "missing_field",
        "empty_field",
        "whitespace_field",
        "inv_052",
        "inv_052_lowercase",
        "inv_052_trailing_space",
        "inv_52_distinct",
    }
)

#: The `inv_prose()` cases guaranteed to carry a citation and no residual
#: reference, so the "citations alone are compliant" clause is exercised
#: deliberately rather than when the draw happens to cooperate.
_CLEAN_CITED_PROSE_CASES = (
    "one_citation",
    "many_citations",
    "discounted_citations",
    "citations_in_code_fence",
)

#: How a seeded defect label names the finding kind it owes. The two blank flavors
#: are one kind — whitespace is empty — and the exclusion label is handled apart
#: because it is about an entry rather than a field.
_INV_052_LABEL = "inv-052"
_LABEL_KINDS: Mapping[str, str] = {
    "missing-field": DISCOUNT_FIELD_ABSENT,
    "empty-field": DISCOUNT_FIELD_BLANK,
    "whitespace-field": DISCOUNT_FIELD_BLANK,
}

#: Entries covering the two defect flavors `discount_register()` does not emit: an
#: element that is not a mapping at all, and a field present as something other
#: than a string. Both are shapes a hand-edited YAML register really produces — a
#: bare `- INV-072` list item, a `conflictsWith` written as a number — and an
#: element the reader dropped would be an element no finding could name.
_UNUSABLE_ENTRY_SEEDS: tuple[Any, ...] = (
    "INV-072",
    ["INV-113"],
)

#: One entry per remaining flavor, so every kind the report vocabulary declares is
#: reached on every example rather than when the draw supplies it.
_SEEDED_REGISTER_ENTRIES: tuple[Any, ...] = (
    # `conflictsWith` absent: the judgment names no constraint.
    {"invariant": "INV-072", "resolution": "absolute-path resolution at install"},
    # `resolution` present and blank once stripped.
    {
        "invariant": "INV-113",
        "conflictsWith": "Agent Plugins v1.0.0 hook schema",
        "resolution": "   ",
    },
    # `conflictsWith` present as a number: a value no message could quote as text.
    {"invariant": "INV-201", "conflictsWith": 42, "resolution": "rewritten as data"},
    # The honored invariant, under a folded spelling.
    {
        "invariant": "inv-052",
        "conflictsWith": "Agent Plugins v1.0.0 hook schema",
        "resolution": "should never have been recorded",
    },
    *_UNUSABLE_ENTRY_SEEDS,
)

#: Where the citation probes are planted in a drawn template tree. The first two
#: are claimed by `substitute` rules and the third by a `skill` rule, so both
#: kinds that port text are exercised; the rule ids are asserted below so a
#: contract edit that moved a probe fails here rather than leaving this property
#: measuring the wrong kind.
_PROSE_PROBE = "docs/inv-citation-prose.md"
_REWRITE_PROBE = "docs/inv-citation-rewrite.md"
_SKILL_PROBE_DOCUMENT = "inv-citation-adjacent.md"

#: A line pairing citations with a term a declared set really rewrites, so the
#: preservation claim is measured across an edit that landed beside a citation.
#: The term is read from the mirrored sets rather than spelled, and asserted to be
#: one the probe's own rule declares.
_REWRITTEN_TERM = SUBSTITUTION_SETS["model-guidance"][0].find
_REWRITE_PROBE_TEMPLATE = (
    "Per {citation}, the {term} reference is rewritten here.\n"
    "The rewrite lands beside {citation} and leaves it alone.\n"
)

#: Documents the exemption clause builds, and the citation each pairs with a
#: genuine residual reference: before it, after it, inside a code fence, and twice
#: on a line that also carries one. One `{residual}` per line, so the expected hit
#: sequence is the terms in the order the lines are assembled.
_EXEMPTION_LINES = (
    "Per {citation}, never name the {residual} in ported guidance.\n",
    "The {residual} appears before {citation} on this line.\n",
    "```text\n{citation}: the {residual} inside a fence is a reference too.\n```\n",
    "Both {citation} and {citation} apply, and so does the {residual}.\n",
)

#: What a masked citation is replaced by. Any string with no catalog term in it
#: serves; a non-empty one is used deliberately, because deleting a citation could
#: join the text on either side of it and manufacture a match that was never
#: there.
_CITATION_MASK = "<citation>"

#: Where the exemption documents sit. Ported bootcamp prose, because that is the
#: population R15 AC7 and AC8 are about.
_CITED_SKILL_DOCUMENT = "skills/bootcamp-modeling/SKILL.md"
_ADJACENT_DOCUMENT = "skills/bootcamp-modeling/references/invariants.md"
_EXEMPTION_DOCUMENT = "skills/bootcamp-modeling/references/exemption.md"

#: The passing sibling check this property's reports carry is
#: `_PASSING_SCHEMA_SIBLING`, defined once in Property 12's section above and
#: shared from there rather than rebound, which would shadow it for both readers.


def _named_invariant(entry: Any) -> Any:
    """The identifier an entry names, or `None` when it names none.

    A bare string entry names itself, which is how `- INV-052` written as a plain
    list item is still an entry the exclusion is about — the register is YAML a
    Maintainer edits, and that is a spelling they write.
    """
    if isinstance(entry, Mapping):
        return entry.get("invariant")
    return entry if isinstance(entry, str) else None


def _folded(identifier: Any) -> str:
    """One spelling of an identifier, whitespace collapsed out and case raised.

    This section's own fold, written for the *exclusion*: a missed match there
    admits the one entry R15 AC6 forbids, while the only entry an over-eager match
    can reject is one spelled to look like `INV-052`. The digit count survives, so
    `INV-52` folds to itself and stays a different invariant.
    """
    return "".join(identifier.split()).upper() if isinstance(identifier, str) else ""


def _trimmed(identifier: Any) -> str:
    """The weaker fold the reconciliation report reads an identifier under.

    Trimmed and raised, with interior whitespace left alone, which is what the
    `discounted` array spells. Deliberately not `_folded`: drift flagging compares
    an identifier against a release registry that writes it one way, and the
    exclusion above answers a different question.
    """
    return identifier.strip().upper() if isinstance(identifier, str) else ""


def _reference_field_state(entry: Any, field: str) -> str | None:
    """What R15 AC4 finds wrong with one field of one entry, or `None`.

    Written from the criterion's own words — the entry records the invariant, the
    conflicting constraint, and the resolution, and all three are mandatory and
    non-empty — against this section's field names, so it is a second opinion
    rather than an echo. A key absent and a key present holding nothing are one
    condition, because a bare `resolution:` in YAML parses to `None`.
    """
    if not isinstance(entry, Mapping):
        return DISCOUNT_ENTRY_UNUSABLE
    if field not in entry or entry[field] is None:
        return DISCOUNT_FIELD_ABSENT
    value = entry[field]
    if not isinstance(value, str):
        return DISCOUNT_FIELD_UNUSABLE
    if not value.strip():
        return DISCOUNT_FIELD_BLANK
    return None


def _reference_incomplete(register: Sequence[Any]) -> frozenset[tuple[int, Any, str]]:
    """Every `(entry, field, kind)` R15 AC4 requires and the register lacks.

    One triple per missing field, not one per entry *(R15 AC5)*. An element that
    is not a mapping owes a single triple naming no field: the position is the
    answer there, and naming a field would invent one.
    """
    owed: set[tuple[int, Any, str]] = set()
    for index, entry in enumerate(register):
        if not isinstance(entry, Mapping):
            owed.add((index, None, DISCOUNT_ENTRY_UNUSABLE))
            continue
        for field_name in _REQUIRED_ENTRY_FIELDS:
            state = _reference_field_state(entry, field_name)
            if state is not None:
                owed.add((index, field_name, state))
    return frozenset(owed)


def _reference_disallowed(register: Sequence[Any]) -> frozenset[int]:
    """Indices of entries naming `INV-052` under any spelling *(R15 AC6)*."""
    return frozenset(
        index
        for index, entry in enumerate(register)
        if _folded(_named_invariant(entry)) == _folded(_HONORED)
    )


def _reference_discounted(register: Sequence[Any]) -> tuple[str, ...]:
    """What the register does discount: identifiers trimmed, deduplicated, in order.

    An entry citing nothing contributes nothing rather than an empty string, and a
    second entry naming an invariant already listed collapses into the first.
    """
    listed: list[str] = []
    for entry in register:
        identifier = _trimmed(_named_invariant(entry))
        if identifier and identifier not in listed:
            listed.append(identifier)
    return tuple(listed)


def _labeled_incomplete(
    case: DiscountRegisterCase,
) -> frozenset[tuple[int, Any, str]]:
    """The same completeness set, read off the generator's defect labels instead.

    `discount_register()` mutates the register's **last** entry, so the label
    names the field and the position follows from the register's length.
    `_LABEL_KINDS` is indexed rather than searched: a case seeding a label this
    section does not describe raises instead of being silently ignored.
    """
    owed: set[tuple[int, Any, str]] = set()
    for defect in case.defects:
        if defect == _INV_052_LABEL:
            continue
        kind, _, field_name = defect.partition(":")
        owed.add((len(case.entries) - 1, field_name, _LABEL_KINDS[kind]))
    return frozenset(owed)


def _labeled_disallowed(case: DiscountRegisterCase) -> frozenset[int]:
    """The same exclusion set, read off the labels: the appended entry, or none."""
    if _INV_052_LABEL not in case.defects:
        return frozenset()
    return frozenset({len(case.entries) - 1})


def _entry_location(index: int, field: Any) -> str:
    """Where in the contract an entry, or one field of it, sits.

    The position a Maintainer reads to find the line, so it is spelled here rather
    than composed from the validator's own path builder.
    """
    position = f"{_REGISTER_KEY}[{index}]"
    return position if field is None else f"{position}.{field}"


def _complete_entry(identifier: Any) -> dict[str, Any]:
    """A register entry that records all three fields *(R15 AC4)*."""
    return {
        "invariant": identifier,
        "conflictsWith": "Agent Plugins v1.0.0 single-command-string hook schema",
        "resolution": "install-time absolute-path resolution; nothing is lost",
    }


def _assert_register_reports_exactly(
    register: Sequence[Any],
    *,
    incomplete: frozenset[tuple[int, Any, str]],
    disallowed: frozenset[int],
) -> CheckResult:
    """Check one register's result against `incomplete` and `disallowed`, and no more.

    One recorded result for the one register, carrying one finding per missing
    field *(R15 AC5)* and one per entry naming the honored invariant *(R15 AC6)*,
    each naming the entry and — where there is one — the field, and passing exactly
    when the register owes neither.
    """
    entries = discount_entries(register)
    assert entries == tuple(
        DiscountEntry(index=index, raw=entry) for index, entry in enumerate(register)
    )
    # Nothing is dropped on the way in: an element the reader discarded would be
    # an element no finding could ever name.
    assert [entry.raw for entry in entries] == list(register)
    assert [entry.complete for entry in entries] == [
        all(
            _reference_field_state(entry, field_name) is None
            for field_name in _REQUIRED_ENTRY_FIELDS
        )
        for entry in register
    ]

    incomplete_findings = incomplete_discount_findings(entries)
    disallowed_findings = honored_invariant_findings(entries)
    result = discount_register_result(register)
    assert result.id == _DISCOUNT_CHECK_ID
    assert result.target is None
    assert result.findings == incomplete_findings + disallowed_findings
    # A function of the register alone: the same register twice, the same result.
    assert discount_register_result(register) == result

    # Exactly the violating set, in both halves: no more, no fewer, and not a
    # prefix — a reader that reported the first bad entry and stopped fails here.
    assert {
        (finding.details["entry"], finding.details["field"], finding.details["kind"])
        for finding in incomplete_findings
    } == incomplete
    assert len(incomplete_findings) == len(incomplete)
    assert {finding.details["entry"] for finding in disallowed_findings} == disallowed
    assert len(disallowed_findings) == len(disallowed)

    for finding in incomplete_findings:
        index = finding.details["entry"]
        field_name = finding.details["field"]
        assert finding.code == E_INCOMPLETE_DISCOUNT
        assert finding.severity == SEVERITY_ERROR
        # R15 AC5: the entry, and the field it omits, both named.
        assert finding.location == _entry_location(index, field_name)
        assert f"{_REGISTER_KEY} entry {index}" in finding.message
        if field_name is not None:
            assert repr(field_name) in finding.message
            assert field_name in _REQUIRED_ENTRY_FIELDS
        else:
            assert finding.details["kind"] == DISCOUNT_ENTRY_UNUSABLE
        assert finding.details["invariant"] == _named_invariant(register[index])
        payload = finding.to_json()
        assert payload["code"] == E_INCOMPLETE_DISCOUNT
        assert payload["severity"] == SEVERITY_ERROR
        assert payload["location"] == finding.location
        assert payload["entry"] == index
        assert payload["field"] == field_name
        assert payload["kind"] == finding.details["kind"]

    for finding in disallowed_findings:
        index = finding.details["entry"]
        named = _named_invariant(register[index])
        assert finding.code == E_HONORED_INVARIANT_DISCOUNTED
        assert finding.severity == SEVERITY_ERROR
        assert finding.location == _entry_location(index, "invariant")
        # Reported as the register spells it, so the line can be found, with the
        # fold it matched under travelling as data beside it.
        assert repr(named) in finding.message
        assert _HONORED in finding.message
        assert finding.details["kind"] == DISCOUNT_HONORED_INVARIANT
        assert finding.details["invariant"] == named
        assert finding.details["normalized"] == _folded(named) == _folded(_HONORED)
        assert finding.details["honoredInvariant"] == _HONORED

    # The recorded payload a Maintainer reads: the register examined, the fields
    # required, what is discounted stated outright, and one compact row per
    # offender.
    assert result.extra["register"] == _REGISTER_KEY
    assert result.extra["entries"] == len(register)
    assert result.extra["requiredFields"] == list(_REQUIRED_ENTRY_FIELDS)
    assert result.extra["honoredInvariant"] == _HONORED
    assert result.extra["discounted"] == list(_reference_discounted(register))
    assert result.extra["incomplete"] == [
        {
            "entry": finding.details["entry"],
            "invariant": finding.details["invariant"],
            "field": finding.details["field"],
            "kind": finding.details["kind"],
            "location": finding.location,
        }
        for finding in incomplete_findings
    ]
    assert len(result.extra["disallowed"]) == len(disallowed_findings)

    # R15 AC5, AC6: the verdict is the register's own completeness, and either
    # fault is an error, so either one withholds permission to tag.
    clean = not incomplete and not disallowed
    assert result.result == (RESULT_PASS if clean else RESULT_FAIL)
    assert result.passed is clean
    assert fold_status((result,)) == (STATUS_PASSED if clean else STATUS_FAILED)
    return result


def _assert_discounts_fail_closed(context: ValidationContext, *, missing: str) -> None:
    """A run that was never shown a register records a fail, not a pass.

    Raising is only half of failing closed: the recorded result has to be a fail
    and the tag has to stay withheld, or a run launched without the contract the
    register lives in *(R15 AC11)* would pass a check it never made.
    """
    with pytest.raises(Unevaluable) as raised:
        check_invariant_discounts(context)
    assert raised.value.message

    report = run_checks(context, checks=(_DISCOUNT_CHECK_ID,))
    recorded = report.results_for(_DISCOUNT_CHECK_ID)
    assert len(recorded) == 1
    assert recorded[0].result == RESULT_FAIL
    assert len(recorded[0].findings) == 1
    finding = recorded[0].findings[0]
    assert finding.code == E_INCOMPLETE_DISCOUNT
    assert finding.details["unevaluated"] is True
    assert report.status == STATUS_FAILED
    assert report.tag_allowed is False, missing


def _contract_with_register(base: Contract, register: Any, path: Path) -> Contract:
    """Write `base`'s document with `register` as its register, and load the copy.

    A copy at `path`, produced from the parsed document rather than by editing
    text, so the only thing that can differ is the register — and the register the
    gate reads is one that survived a YAML round trip, which is the shape a
    hand-edited contract actually reaches it in. `contract.yaml` is not touched.
    """
    document = deepcopy(dict(base.raw))
    document[_REGISTER_KEY] = register
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=10**6),
        encoding="utf-8",
    )
    return load_contract(path)


def _exemption_document(citation: str) -> tuple[str, tuple[str, ...]]:
    """A document pairing `citation` with a genuine residual on every line.

    Returns the text and the residual references it carries in document order —
    one per line, which is what makes the expected hit sequence arithmetic over
    the lines rather than something read back out of the finished text.
    """
    text = "".join(
        template.format(citation=citation, residual=residual)
        for template, residual in zip(_EXEMPTION_LINES, CLAUDE_MODEL_REFERENCES)
    )
    return text, CLAUDE_MODEL_REFERENCES


def _residual_signature(text: str, source: str) -> tuple[tuple[str, str, str], ...]:
    """What a scan of `text` reports, with positions dropped.

    Kind, catalog term, and matched text per hit. Positions are left out on
    purpose: this is the shape compared across a masking edit, which moves every
    offset after the citation it replaced without changing what was found.
    """
    return tuple(
        (reference.kind, reference.term, reference.text)
        for reference in residual_references(text, source=source)
    )


def _assert_citations_are_never_reported(
    documents: Mapping[str, str], expected: Mapping[str, tuple[str, ...]]
) -> CheckResult:
    """Scan `documents`: zero citations reported, every genuine reference reported.

    `expected` names the residual references each document carries, in document
    order. Both halves of R15 AC8 are here — a citation is not a hit, and a
    citation does not shield the reference beside it — and the second is what keeps
    the first from being satisfiable by a scanner that reported nothing.
    """
    result = residual_claude_result(documents)
    assert result.id == "residual-claude-refs"
    assert residual_claude_result(documents) == result

    reported: list[ResidualReference] = []
    for source in sorted(documents):
        text = documents[source]
        references = residual_references(text, source=source)
        reported.extend(references)

        # Every genuine reference, in document order, and nothing else.
        assert tuple(reference.text for reference in references) == expected[source]

        # Two citation scanners — the engine's and this file's — one answer.
        citations = tuple(_CITATION.findall(text))
        assert invariant_citations(text) == citations
        assert tuple(INVARIANT_CITATION.findall(text)) == citations

        # No reported hit is a citation, and no reported hit overlaps one.
        cited = {
            index
            for match in _CITATION.finditer(text)
            for index in range(match.start(), match.end())
        }
        assert not cited & {reference.offset for reference in references}
        for reference in references:
            assert "INV-" not in reference.text

        # Citations are transparent to the scan: masking them changes nothing that
        # was found, which says at once that a citation is not a hit and that it
        # shields nothing.
        masked = _CITATION.sub(_CITATION_MASK, text)
        assert _CITATION.findall(masked) == []
        assert (masked != text) is bool(citations)
        assert _residual_signature(masked, source) == _residual_signature(text, source)

    # R15 AC8 in the recorded payload: the citations the sweep passed over are
    # counted outright, which is the evidence that preserved prose was read and
    # left alone.
    assert result.extra["invariantCitations"] == sum(
        len(_CITATION.findall(text)) for text in documents.values()
    )
    assert result.findings == residual_findings(reported)
    assert len(result.findings) == sum(len(terms) for terms in expected.values())
    for finding in result.findings:
        assert finding.code == W_RESIDUAL_CLAUDE_REF
        assert finding.severity == SEVERITY_WARNING
        assert "INV-" not in finding.details["match"]

    # The gate, beside a passing sibling so it can only have come from this check:
    # a document of nothing but citations is compliant content and tags, and one
    # genuine reference folds the run to `incomplete` and withholds permission.
    clean = not reported
    tree = PowerTree.from_mapping(documents)
    assert check_residual_claude_refs(
        ValidationContext(tree=tree, tag=_RESOLVED_TAG)
    ) == result
    report = ValidationReport(
        template_release=_RESOLVED_TAG,
        power_version=_RESOLVED_TAG,
        checks=(_PASSING_SCHEMA_SIBLING, result),
    )
    assert _PASSING_SCHEMA_SIBLING.passed
    assert report.status == (STATUS_PASSED if clean else STATUS_INCOMPLETE)
    assert report.tag_allowed is clean
    return result


def _with_citation_probes(
    tree: Mapping[str, TreeEntry], *, prose: str, rewritten: str, adjacent: str
) -> dict[str, TreeEntry]:
    """Plant the citation probes into a generated tree, one per porting kind.

    Two under `docs/`, claimed by a `substitute` rule, and one inside every skill
    directory the tree carries, claimed by a `skill` rule. None of them is a
    skill's entry point, so what is compared below is a ported *body* with no
    frontmatter adaptation in the way.
    """
    planted = dict(tree)
    names = sorted(path.split("/")[1] for path in tree if _is_skill_entry_point(path))
    assert names, sorted(tree)

    planted[_PROSE_PROBE] = TreeEntry("file", prose.encode("utf-8"))
    planted[_REWRITE_PROBE] = TreeEntry("file", rewritten.encode("utf-8"))
    for name in names:
        planted[f"skills/{name}/{_SKILL_PROBE_DOCUMENT}"] = TreeEntry(
            "file", adjacent.encode("utf-8")
        )
    return planted


# Feature: senzing-bootcamp-power, Property 25: The discount register is
# complete, excludes INV-052, and invariant citations survive untouched
#
# Validates: Requirements 15.4, 15.5, 15.6, 15.7, 15.8
@settings(max_examples=100)
@given(
    discount_register(),
    st.lists(discount_register(), min_size=1, max_size=3),
    inv_prose(),
    st.one_of(*(INV_PROSE_CASES[name] for name in _CLEAN_CITED_PROSE_CASES)),
    INV_PROSE_CASES["citation_adjacent_to_residual"],
    template_tree(),
)
def test_the_discount_register_is_complete_and_citations_survive_untouched(
    case: DiscountRegisterCase,
    composite: list[DiscountRegisterCase],
    prose: InvProseCase,
    cited: InvProseCase,
    adjacent: InvProseCase,
    tree: Mapping[str, TreeEntry],
) -> None:
    # The generator cases this property draws from, asserted rather than assumed.
    assert _REQUIRED_REGISTER_CASES <= set(DISCOUNT_REGISTER_CASES)
    assert set(_CLEAN_CITED_PROSE_CASES) <= set(INV_PROSE_CASES)
    assert cited.citations and cited.residual_claude_refs == ()
    assert adjacent.citations and adjacent.residual_claude_refs != ()
    assert len(_EXEMPTION_LINES) == len(CLAUDE_MODEL_REFERENCES)

    # One spelling of every fixed fact, on both sides: the register key, the three
    # mandatory fields, and the honored invariant. A gate demanding one field set
    # and an engine writing another would be caught here rather than by a
    # Maintainer reading a report about a key nothing declares.
    assert DISCOUNT_REGISTER_KEY == _REGISTER_KEY
    assert DISCOUNT_FIELDS == _REQUIRED_ENTRY_FIELDS
    assert (
        DISCOUNT_INVARIANT_FIELD,
        DISCOUNT_CONFLICTS_FIELD,
        DISCOUNT_RESOLUTION_FIELD,
    ) == _REQUIRED_ENTRY_FIELDS
    assert GATE_HONORED_INVARIANT == HONORED_INVARIANT == _HONORED
    assert _HONORED not in DISCOUNTED_INVARIANTS
    assert len(DISCOUNT_KINDS) == len(set(DISCOUNT_KINDS))

    # R15 AC5, AC6: the gate this property drives. Both faults are errors, so
    # either one blocks the tag, and failing closed is the same error code —
    # a register nobody showed the gate is not a register it approved.
    registered = registered_check(_DISCOUNT_CHECK_ID)
    assert registered is not None
    assert registered.code == E_INCOMPLETE_DISCOUNT
    assert registered.failure_code == E_INCOMPLETE_DISCOUNT
    assert registered.target is None
    assert registered.requirement == _DISCOUNT_REQUIREMENT
    for code in (E_INCOMPLETE_DISCOUNT, E_HONORED_INVARIANT_DISCOUNTED):
        assert Finding(code=code, message="m").severity == SEVERITY_ERROR

    # --- Clause 1: one drawn register, exactly the violating set -------------
    register = list(case.entries)
    incomplete = _reference_incomplete(register)
    disallowed = _reference_disallowed(register)
    # The two oracles agree, and passing is exactly the no-defect case.
    assert incomplete == _labeled_incomplete(case)
    assert disallowed == _labeled_disallowed(case)
    assert (not incomplete and not disallowed) is case.valid
    drawn = _assert_register_reports_exactly(
        register, incomplete=incomplete, disallowed=disallowed
    )
    assert drawn.passed is case.valid

    # The near-miss label and the fold answer the same question: a spelling of the
    # honored invariant is excluded, a different digit count is not.
    if case.near_miss is not None:
        assert (_INV_052_LABEL in case.defects) is (
            _folded(case.near_miss) == _folded(_HONORED)
        )
        assert names_honored_invariant(case.near_miss) is (
            _INV_052_LABEL in case.defects
        )

    # --- Clause 2: every offender in one run, over a composite register ------
    # `discount_register()` seeds one defect per case, so a register with four bad
    # entries is not something it produces on its own — and four bad entries is
    # exactly what distinguishes "names everything wrong" from "names the first
    # thing wrong".
    combined: list[Any] = list(_SEEDED_REGISTER_ENTRIES)
    combined_incomplete = set(_reference_incomplete(combined))
    combined_disallowed = set(_reference_disallowed(combined))
    for contributed in composite:
        offset = len(combined)
        combined.extend(contributed.entries)
        combined_incomplete |= {
            (index + offset, field_name, kind)
            for index, field_name, kind in _labeled_incomplete(contributed)
        }
        combined_disallowed |= {
            index + offset for index in _labeled_disallowed(contributed)
        }
    # The contributors' labels account for the drawn half, and this section's
    # criteria oracle for the whole: two independent readings of one register.
    assert _reference_incomplete(combined) == combined_incomplete
    assert _reference_disallowed(combined) == combined_disallowed

    every = _assert_register_reports_exactly(
        combined,
        incomplete=frozenset(combined_incomplete),
        disallowed=frozenset(combined_disallowed),
    )
    assert not every.passed
    assert len(every.findings) == len(combined_incomplete) + len(combined_disallowed)

    # Non-vacuous in every example: every kind the report vocabulary declares is
    # reached, so none of them is a condition this property merely describes.
    covered = {kind for _, _, kind in combined_incomplete}
    assert combined_disallowed
    covered.add(DISCOUNT_HONORED_INVARIANT)
    assert covered == set(DISCOUNT_KINDS)

    # --- Clause 3: the exclusion folds spelling and not digit count ----------
    for spelling in _HONORED_SPELLINGS:
        assert _folded(spelling) == _folded(_HONORED)
        assert invariant_spelling(spelling) == _folded(spelling)
        assert names_honored_invariant(spelling)
        # One entry, complete in every field, and still refused: completing the
        # record is never the answer here, deleting it is.
        seeded = [_complete_entry(spelling)]
        refused = _assert_register_reports_exactly(
            seeded, incomplete=frozenset(), disallowed=frozenset({0})
        )
        assert not refused.passed
        assert refused.extra["discounted"] == [_trimmed(spelling)]
        # ...and a bare list item naming it is caught as well, incomplete *and*
        # disallowed, because it records no judgment and names what may not be
        # discounted.
        _assert_register_reports_exactly(
            [spelling],
            incomplete=frozenset({(0, None, DISCOUNT_ENTRY_UNUSABLE)}),
            disallowed=frozenset({0}),
        )

    for different in _DIFFERENT_INVARIANTS:
        assert _folded(different) != _folded(_HONORED)
        assert invariant_spelling(different) == different.upper()
        assert not names_honored_invariant(different)
        # A different invariant, discounted completely: a legitimate judgment the
        # exclusion must leave alone.
        allowed = _assert_register_reports_exactly(
            [_complete_entry(different)],
            incomplete=frozenset(),
            disallowed=frozenset(),
        )
        assert allowed.passed and allowed.findings == ()
        assert allowed.extra["discounted"] == [different.upper()]

    # Nothing at all is not something to report: an empty register discounts
    # nothing, and says so outright rather than leaving a reader to infer it.
    empty = _assert_register_reports_exactly(
        [], incomplete=frozenset(), disallowed=frozenset()
    )
    assert empty.passed
    assert empty.extra["entries"] == 0
    assert empty.extra["discounted"] == []
    for absent in (None, "", "   "):
        assert not names_honored_invariant(absent)

    # --- Clause 4: the committed register, and the gate reading a contract ---
    contract = load_contract()
    assert _REGISTER_KEY in contract.raw
    committed = declared_discounts(contract)
    # What ships today: nothing is discounted, which is a verdict and not an
    # absence — INV-052's guarantee is preserved under R16 rather than given up.
    assert list(committed) == []
    shipped = _assert_register_reports_exactly(
        list(committed), incomplete=frozenset(), disallowed=frozenset()
    )
    assert shipped.passed and shipped.findings == ()
    assert _reference_disallowed(list(committed)) == frozenset()
    assert not any(
        names_honored_invariant(_named_invariant(entry)) for entry in committed
    )

    power = PowerTree.from_mapping({PLUGIN_MANIFEST: '{"version": "0.5.1"}\n'})
    assert check_invariant_discounts(
        ValidationContext(tree=power, tag=_RESOLVED_TAG, contract=contract)
    ) == shipped

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        # The drawn register, read from a contract document the loader produced.
        carrying = _contract_with_register(
            contract, register, root / "contract-with-drawn-register.yaml"
        )
        assert list(declared_discounts(carrying)) == register
        context = ValidationContext(
            tree=power, tag=_RESOLVED_TAG, contract=carrying
        )
        assert check_invariant_discounts(context) == drawn
        report = run_checks(context, checks=(_DISCOUNT_CHECK_ID,))
        assert report.results_for(_DISCOUNT_CHECK_ID) == (drawn,)
        assert report.tag_allowed is case.valid
        positioned = discount_entries(register)
        assert report.findings_for(
            E_INCOMPLETE_DISCOUNT
        ) == incomplete_discount_findings(positioned)
        assert report.findings_for(
            E_HONORED_INVARIANT_DISCOUNTED
        ) == honored_invariant_findings(positioned)

        # --- Clause 5: no register shown, no verdict reached ----------------
        # The register lives inside the contract *(R15 AC11)*, so a run without
        # one has not been shown a complete register. The two malformed
        # declarations swap the parsed document rather than a written file,
        # because what is under test is the declaration and `declared_discounts`
        # reads nothing else.
        lost = dict(contract.raw)
        lost.pop(_REGISTER_KEY)
        mistyped = {**contract.raw, _REGISTER_KEY: "INV-072"}
        _assert_discounts_fail_closed(
            ValidationContext(tree=power, tag=_RESOLVED_TAG),
            missing="the Transformation_Contract, which the register lives inside",
        )
        for variant, missing in (
            (lost, f"a '{_REGISTER_KEY}' section at all"),
            (mistyped, f"a list-shaped '{_REGISTER_KEY}' section"),
        ):
            altered = replace(contract, raw=variant)
            with pytest.raises(Unevaluable):
                declared_discounts(altered)
            _assert_discounts_fail_closed(
                ValidationContext(
                    tree=power, tag=_RESOLVED_TAG, contract=altered
                ),
                missing=missing,
            )

        # --- Clause 6: citations survive the real transformation ------------
        # R15 AC7, through the engine rather than around it: every ported text
        # output's citation sequence is its source's, and one probe carries a term
        # a declared set really rewrites so the claim is measured across an edit
        # that landed beside a citation.
        rewrite_probe = _REWRITE_PROBE_TEMPLATE.format(
            citation=DISCOUNTED_INVARIANTS[0], term=_REWRITTEN_TERM
        )
        source_tree = _with_citation_probes(
            _transformable(tree, contract),
            prose=prose.text,
            rewritten=rewrite_probe,
            adjacent=adjacent.text,
        )
        # Every probe is claimed by the kind it was planted for, and the rewrite
        # probe really carries a term the rule claiming it declares — so the
        # "survived an edit beside it" clause has something to stand on.
        skill_probes = sorted(
            path for path in source_tree if path.endswith(f"/{_SKILL_PROBE_DOCUMENT}")
        )
        assert skill_probes
        for path, kind in (
            (_PROSE_PROBE, "substitute"),
            (_REWRITE_PROBE, "substitute"),
            (skill_probes[0], "skill"),
        ):
            claimed = contract.classify(path).rule
            assert claimed is not None and claimed.kind == kind, path
            if path == _REWRITE_PROBE:
                assert "model-guidance" in claimed.substitutions, claimed.id
        assert _REWRITTEN_TERM in rewrite_probe
        assert len(_CITATION.findall(rewrite_probe)) == 2

        source, _ = _materialized_release(root, source_tree, "release")
        staging = root / "staging"
        plan = build_plan(contract, source, tag=_RESOLVED_TAG, staging=staging)
        write_staging(plan)
        outputs, _ = plan_destinations(plan)
        staged = _read_tree(staging)

        probes_checked = 0
        cited_probes = 0
        rewrites_beside_a_citation = 0
        for output in outputs:
            if output.rule.kind not in ("substitute", "skill"):
                continue
            if output.source_path is None:
                continue
            before = _lf(output.origin.read_bytes()).decode("utf-8")
            after = staged[output.path].decode("utf-8")

            # The multiset and the order, both: R15 AC7 says verbatim, so a
            # rewrite that moved a citation is a failure as much as one that
            # dropped it.
            before_citations = invariant_citations(before)
            after_citations = invariant_citations(after)
            assert after_citations == before_citations, output.path
            assert sorted(after_citations) == sorted(before_citations), output.path
            # Per named invariant, the honored one and the discounted ones alike:
            # a discount is about packaging construction, never about what ported
            # prose may cite.
            for invariant in (_HONORED, *DISCOUNTED_INVARIANTS):
                assert after.count(invariant) == before.count(invariant), (
                    output.path,
                    invariant,
                )

            relative = output.source_path[len(TEMPLATE_PLUGIN_ROOT) + 1 :]
            if relative in (_PROSE_PROBE, _REWRITE_PROBE) or relative.endswith(
                f"/{_SKILL_PROBE_DOCUMENT}"
            ):
                probes_checked += 1
                if before_citations:
                    cited_probes += 1
                if _REWRITTEN_TERM in before:
                    # The edit happened, and the citations either side of it did
                    # not move.
                    assert _REWRITTEN_TERM not in after, output.path
                    assert len(before_citations) == 2, output.path
                    rewrites_beside_a_citation += 1

        # Both docs probes and at least one skill probe were ported, every probe
        # that carried a citation kept it, and the rewrite really fired.
        assert probes_checked >= 3
        assert cited_probes >= 2
        assert rewrites_beside_a_citation >= 1

    # --- Clause 7: a citation is compliant content, and shields nothing ------
    exemption, exemption_residuals = _exemption_document(_HONORED)
    documents = {
        _CITED_SKILL_DOCUMENT: cited.text,
        _ADJACENT_DOCUMENT: adjacent.text,
        _EXEMPTION_DOCUMENT: exemption,
    }
    swept = _assert_citations_are_never_reported(
        documents,
        {
            _CITED_SKILL_DOCUMENT: (),
            _ADJACENT_DOCUMENT: adjacent.residual_claude_refs,
            _EXEMPTION_DOCUMENT: exemption_residuals,
        },
    )
    assert not swept.passed
    assert swept.extra["invariantCitations"] >= len(cited.citations)

    # R15 AC8 alone, with nothing else in the tree: prose that cites discounted
    # invariants — inside a code fence, twice on a line, however it is written — is
    # compliant content, and the run passes on it.
    citations_only = _assert_citations_are_never_reported(
        {_CITED_SKILL_DOCUMENT: cited.text}, {_CITED_SKILL_DOCUMENT: ()}
    )
    assert citations_only.passed and citations_only.findings == ()
    assert citations_only.extra["invariantCitations"] == len(cited.citations) > 0
