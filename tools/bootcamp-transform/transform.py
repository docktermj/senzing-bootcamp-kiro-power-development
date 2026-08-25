#!/usr/bin/env python3
"""Transform engine — executes the Transformation_Contract (R3).

    transform.py --contract contract.yaml --source <tree> --tag <semver>
                 --staging <dir> [--carry-forward <existing-power-dir>]
                 [--plan-only]

The engine is *data driven*: every mapping decision comes from `contract.yaml`,
never from code and never from an agent. That is what lets the create path and
the update path produce byte-for-byte identical output from identical input
(R3 AC2, AC3, AC5), because both paths run this same file over that same
contract.

Pipeline stages, in the order the design lays them out:

1. **Enumerate** every file under the source plugin root, sorted (this module).
2. **Match** each file to exactly one rule or one ignore entry; halt on
   unmatched with `E_UNMATCHED_FILE` (this module).
3. Apply the matched rule into `--staging`, never into the target.
4. Materialize `kiro-owned` files from `--carry-forward`, else from `templates/`.
5. Stamp the version and provenance.
6. Emit `.build-manifest.json`.

Stages 1, 2, 3, 4, 5, and 6 are implemented here; the remaining per-rule-kind
content transformation attaches at `render_output`, the one seam every rule kind's
bytes pass through. The `copy`, `substitute`, and `skill` kinds are complete
there: byte-for-byte fidelity, named-set rewriting, and named-set rewriting plus
additive Agent_Plugins_Format frontmatter adaptation respectively. The `generate`
kind is complete for both artifacts the contract generates: `plugin.json`, which
carries stage 5 — the version stamp and the provenance — and whose declared
license the Power's own `LICENSE` file backs byte-for-byte from this repository's
root, and `mcp.json`, which translates the template's `{"type": "http"}` Senzing
declaration into the Agent Plugins `streamable-http` form and adds `$schema`.

Determinism (R3 AC5): directory traversal is sorted, the enumerated file list is
sorted by its plugin-root-relative POSIX path, destinations are derived from that
same order, the manifest is sorted by output path, the JSON serializer is fixed
with an explicit key order, and nothing anywhere reads the clock or a run id. So
`(contract, source, tag)` alone determines every output byte, which is what makes
the create path and the update path produce identical trees.

**Matching completes before any output directory is touched**, so a source tree
containing an unmatched file produces no output tree at all (R3 AC6).

Content rewriting (R10 AC2, R12 AC2, R15 AC7)
---------------------------------------------
The only text rewriting performed is the named substitution sets, every one of
them defined in the contract and none of them written here: literal terms and
line-anchored regexes, applied in the order a rule lists its sets, one pass per
set. Nothing is heuristic and nothing is model generated, so a byte no set names
survives exactly as the template wrote it — inline `INV-NNN` invariant citations
included, which are content and are protected as such even when the cited
invariant is discounted.

Ported scripts (R10)
--------------------
Every ported script lands together under the single owning skill's `scripts/`
directory with its file name and its relative sub-structure preserved, which is
what keeps the template's same-directory module imports resolving; vendored assets
are `copy` rules and so are byte-for-byte at the same relative location. All of
that is contract data the stages above execute. The one behavior written here is
missing-asset detection: a ported script referencing a file under a `vendor/`
directory that the template source does not ship halts the run with
`E_MISSING_ASSET` naming the script and the asset, before anything is written.

Atomicity (R4 AC8, R5 AC7, R14 AC5)
-----------------------------------
Every write lands in `--staging`, never in the target. `write_staging` discards
the whole staging tree on any fault, so a failed run leaves no residue and
nothing partial anywhere. `swap_into_place` is the *only* function here that
touches the target, it is called by the orchestrating skill only after the
`Schema_Validator` passes, and it replaces the target by directory rename —
move-old-aside, move-new-in, delete-old — rolling the old tree back if the
move-new-in fails. The target is therefore byte-identical to its prior state
after any failure at any stage.

Containment (R14 AC1)
---------------------
`contained_path` is the sole path constructor for both reads and writes. It
refuses `..` segments, absolute and absolute-looking paths (POSIX, drive-letter,
and UNC spellings), and any path whose real location falls outside its root — so
a symlink cannot be followed out of the source tree and cannot be written
through inside the staging tree.

Line endings (R16 AC8, AC9)
---------------------------
Text output is written with LF unconditionally, matching the committed
`.gitattributes`, so a `Build_Manifest` hash still describes the file after a
checkout on any Supported_Platform. `copy` rules are exempt by design: their
guarantee is byte-for-byte fidelity, and rewriting one byte of a minified or
binary vendored asset corrupts it (R10 AC3).

Exit codes: 0 on success, 1 on any `TransformError` (JSON error document on
stdout), 2 on CLI misuse (argparse).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import yaml

__all__ = [
    # Error codes.
    "E_MISSING_ASSET",
    "E_TRANSFORM_FAILED",
    "E_UNMATCHED_FILE",
    "E_WRITE_FAILED",
    "TransformError",
    # Contract model.
    "Contract",
    "Rule",
    "Match",
    "RULE_KINDS",
    "OWNER_KIRO",
    "OWNER_TEMPLATE",
    "load_contract",
    # Enumeration and matching.
    "SourceFile",
    "PlannedFile",
    "IgnoredFile",
    "TransformPlan",
    "build_plan",
    "enumerate_source",
    "resolve_plugin_root",
    "glob_matches",
    # Destinations and containment.
    "PlannedOutput",
    "contained_path",
    "plan_destinations",
    # Named substitution sets.
    "INVARIANT_CITATION",
    "SUBSTITUTION_LITERAL",
    "SUBSTITUTION_REGEX",
    "Substitution",
    "SubstitutionSet",
    "apply_substitutions",
    "invariant_citations",
    "load_substitution_sets",
    "parse_substitution",
    "parse_substitution_set",
    "rule_substitution_sets",
    "substitute_content",
    # The `generate` rule kind, the version stamp, and the license.
    "EXTENSION_NAMESPACE",
    "GENERATED_CONTEXTS",
    "GENERATED_VERIFIERS",
    "LICENSE_FILENAME",
    "LICENSE_RULE",
    "MCP_MANIFEST_DEST",
    "MCP_SCHEMA_FIELD",
    "MCP_SCHEMA_URL",
    "MCP_SERVERS_FIELD",
    "MCP_TRANSPORT_TYPE",
    "PLUGIN_MANIFEST_DEST",
    "POWER_LICENSE",
    "REPOSITORY_LICENSE",
    "REPOSITORY_ROOT",
    "SENZING_MCP_URL",
    "SENZING_SERVER_KEY",
    "TEMPLATE_RELEASE_FIELD",
    "license_identifier",
    "mcp_document_context",
    "plugin_manifest_context",
    "render_generated",
    "render_generation_template",
    "render_license",
    "verify_mcp_document",
    "verify_plugin_manifest",
    # The `skill` rule kind.
    "FRONTMATTER_FENCE",
    "SKILL_COMPATIBILITY",
    "SKILL_ENTRY_POINT",
    "SKILL_LICENSE",
    "SKILL_METADATA_AUTHOR",
    "SKILL_METADATA_FIELD",
    "SKILL_REQUIRED_FIELDS",
    "SKILL_TEMPLATE_SKILL_FIELD",
    "adapt_skill_frontmatter",
    "render_frontmatter",
    "render_skill",
    "split_frontmatter",
    # Ported scripts and their vendored assets.
    "SCRIPT_SUFFIX",
    "VENDOR_SEGMENT",
    "MissingAsset",
    "find_missing_assets",
    "missing_vendored_assets",
    "vendored_asset_paths",
    "vendored_asset_references",
    # Staging output and the Build_Manifest.
    "BuildManifest",
    "ManifestEntry",
    "StagedOutput",
    "StagingResult",
    "MANIFEST_FILENAME",
    "MANIFEST_VERSION",
    "KIRO_OWNED_ROOT",
    "discard_staging",
    "normalize_lf",
    "render_output",
    "sha256_hex",
    "write_staging",
    # Atomic swap.
    "SwapResult",
    "swap_into_place",
    # CLI.
    "DEFAULT_CONTRACT",
    "ENGINE_ROOT",
    "main",
]


# ---------------------------------------------------------------------------
# Error codes — the Maintainer-facing catalog, engine subset
# ---------------------------------------------------------------------------

#: Source file matches no rule and no ignore entry (R3 AC6).
E_UNMATCHED_FILE = "E_UNMATCHED_FILE"
#: A ported script references a vendored asset absent from the source (R10 AC4).
E_MISSING_ASSET = "E_MISSING_ASSET"
#: Any other transform fault; staging is discarded and the target is untouched.
E_TRANSFORM_FAILED = "E_TRANSFORM_FAILED"
#: The target cannot be created or written (R14 AC5).
E_WRITE_FAILED = "E_WRITE_FAILED"


class TransformError(Exception):
    """A halting transform fault, carrying a catalog code and its details.

    `details` becomes extra top-level keys in the emitted JSON error document,
    so a caller reads the offending path or rule ids as data rather than by
    parsing the message.
    """

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_json(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message, **self.details}


# ---------------------------------------------------------------------------
# POSIX glob matching
# ---------------------------------------------------------------------------
#
# Contract `source` and `exclude` patterns, and `ignore` entries, are POSIX glob
# patterns relative to `template.pluginRoot`. `fnmatch` is unusable here because
# its `*` crosses `/`, which would make `scripts/*` swallow `scripts/vendor/x`
# and silently break the mutual exclusivity the contract is authored for.
# `PurePath.full_match` would do, but it lands in Python 3.13 and this project
# supports 3.10, so the translation is explicit:
#
#   `**` as a whole segment  zero or more path segments (`scripts/**/*.py`
#                            therefore matches `scripts/a.py` as well as
#                            `scripts/vendor/a.py`); as the final segment, the
#                            entire remainder of the path
#   `*`                      any run of characters within one segment
#   `?`                      one character within one segment
#   `[...]`                  a character class, `!` or `^` negating
#   anything else            literal
#
# A pattern ending in `/` is read as that directory's whole subtree, so
# `invariants/` and `invariants/**` mean the same thing.


def _translate_segment(segment: str) -> str:
    """Translate one glob path segment; nothing produced here matches `/`."""
    out: list[str] = []
    index = 0
    while index < len(segment):
        char = segment[index]
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[":
            close = index + 1
            if close < len(segment) and segment[close] in "!^":
                close += 1
            if close < len(segment) and segment[close] == "]":
                close += 1
            while close < len(segment) and segment[close] != "]":
                close += 1
            if close >= len(segment):
                # Unterminated class: the bracket is a literal, as in shells.
                out.append(re.escape(char))
            else:
                body = segment[index + 1 : close]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                index = close + 1
                continue
        else:
            out.append(re.escape(char))
        index += 1
    return "".join(out)


@lru_cache(maxsize=None)
def _compile_glob(pattern: str) -> re.Pattern[str]:
    normalized = pattern.strip()
    if normalized.endswith("/"):
        normalized += "**"
    segments = normalized.split("/")
    parts: list[str] = []
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if segment == "**":
            # A trailing `**` takes the remainder; an interior one consumes its
            # own trailing slash so zero segments is a match.
            parts.append(".*" if last else "(?:[^/]+/)*")
            continue
        parts.append(_translate_segment(segment))
        if not last:
            parts.append("/")
    return re.compile("".join(parts) + r"\Z")


def glob_matches(pattern: str, path: str) -> bool:
    """Match a contract glob against a plugin-root-relative POSIX path."""
    return _compile_glob(pattern).match(path) is not None


# ---------------------------------------------------------------------------
# Contract model
# ---------------------------------------------------------------------------

#: The six rule kinds the contract may declare.
RULE_KINDS = ("copy", "substitute", "skill", "generate", "kiro-owned", "ignore")

#: `owner` values recorded in the Build_Manifest. `kiro` drives update-time
#: preservation (R5 AC5); everything else defaults to `template`.
OWNER_TEMPLATE = "template"
OWNER_KIRO = "kiro"

#: Rule kinds that never carry a template `source` and so take no part in
#: matching: they exist only in the Power.
_SOURCELESS_KINDS = frozenset({"kiro-owned"})

#: The engine's own directory. A contract `template` path is relative to it, and
#: the two roots below are derived from it, so the engine's layout is stated once.
ENGINE_ROOT = Path(__file__).resolve().parent

DEFAULT_CONTRACT = ENGINE_ROOT / "contract.yaml"

#: Authored `kiro-owned` content, keyed by its Power-relative destination, used on
#: the create path when there is no `--carry-forward` tree to take it from.
KIRO_OWNED_ROOT = ENGINE_ROOT / "templates" / "kiro-owned"

#: This repository's root: `tools/bootcamp-transform/` sits two levels below it.
#: The only thing read from here is the root license (R14 AC3).
REPOSITORY_ROOT = ENGINE_ROOT.parent.parent

#: The Build_Manifest lives at the Power root and is not itself a manifest entry:
#: it cannot record its own hash.
MANIFEST_FILENAME = ".build-manifest.json"
MANIFEST_VERSION = 1


@dataclass(frozen=True)
class Rule:
    """One `rules` entry from the contract."""

    id: str
    kind: str
    source: str | None = None
    exclude: tuple[str, ...] = ()
    dest: tuple[str, ...] = ()
    substitutions: tuple[str, ...] = ()
    template: str | None = None
    owner: str = OWNER_TEMPLATE

    @property
    def claims_source(self) -> bool:
        """Whether this rule participates in source-file matching."""
        return self.source is not None

    @property
    def produces_output(self) -> bool:
        """`ignore` rules match deliberately and emit nothing."""
        return self.kind != "ignore"

    def matches(self, path: str) -> bool:
        """Whether `path` is claimed by this rule, honoring `exclude`."""
        if self.source is None or not glob_matches(self.source, path):
            return False
        return not any(glob_matches(pattern, path) for pattern in self.exclude)


@dataclass(frozen=True)
class Match:
    """How the contract disposes of one source path.

    `disposition` is `rule` (a rule claims it), `ignore` (an `ignore` pattern
    claims it), or `unmatched` (nothing claims it, which halts the run).
    """

    path: str
    disposition: str
    rule: Rule | None = None
    pattern: str | None = None


@dataclass(frozen=True)
class Contract:
    """The parsed Transformation_Contract.

    `raw` keeps the whole document so sections this stage does not interpret —
    `substitutionSets` entry shapes, `invariantDiscounts`, `output`, and any
    section a later contract version adds — remain available to the stages that
    own them, without this stage needing to know about them.
    """

    path: Path
    contract_version: int
    repository: str
    plugin_root: str
    rules: tuple[Rule, ...]
    ignore: tuple[str, ...]
    substitution_sets: Mapping[str, tuple[Mapping[str, Any], ...]]
    line_endings: str
    raw: Mapping[str, Any]
    skill_triggers: Mapping[str, str] = field(default_factory=dict)

    @property
    def matching_rules(self) -> tuple[Rule, ...]:
        return tuple(rule for rule in self.rules if rule.claims_source)

    @property
    def kiro_owned_rules(self) -> tuple[Rule, ...]:
        return tuple(rule for rule in self.rules if rule.owner == OWNER_KIRO)

    def rule(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(rule_id)

    def ignore_pattern_for(self, path: str) -> str | None:
        """The first `ignore` pattern claiming `path`, in declaration order."""
        for pattern in self.ignore:
            if glob_matches(pattern, path):
                return pattern
        return None

    def rules_for(self, path: str) -> tuple[Rule, ...]:
        """Every rule claiming `path`; the contract is authored to yield one."""
        return tuple(rule for rule in self.matching_rules if rule.matches(path))

    def classify(self, path: str) -> Match:
        """Dispose of one plugin-root-relative path.

        The `ignore` list is consulted first, deliberately: it exists so that
        content the Bootcamp_Power excludes on purpose — a template invariant
        registry in whichever directory a later release puts it, for instance —
        stays excluded even when a broad rule glob would otherwise sweep it up.

        A path claimed by two rules is a contract defect, not a source defect:
        the rules are authored mutually exclusive, so an overlap means one of
        them lost its `exclude`. Fail closed rather than pick a winner by
        declaration order, which would bury the defect in correct-looking output.
        """
        pattern = self.ignore_pattern_for(path)
        if pattern is not None:
            return Match(path=path, disposition="ignore", pattern=pattern)

        claimed = self.rules_for(path)
        if len(claimed) == 1:
            return Match(path=path, disposition="rule", rule=claimed[0])
        if not claimed:
            return Match(path=path, disposition="unmatched")
        raise TransformError(
            E_TRANSFORM_FAILED,
            "contract defect: template file is claimed by "
            f"{len(claimed)} rules ({', '.join(rule.id for rule in claimed)}): {path}",
            path=path,
            rules=[rule.id for rule in claimed],
        )


def _as_tuple(value: Any, *, field: str, rule_id: str) -> tuple[str, ...]:
    """Normalize a scalar-or-list contract field to a tuple of strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        for item in value:
            if not isinstance(item, str):
                raise TransformError(
                    E_TRANSFORM_FAILED,
                    f"contract defect: rule '{rule_id}' field '{field}' "
                    "must contain only strings",
                    ruleId=rule_id,
                )
        return tuple(value)
    raise TransformError(
        E_TRANSFORM_FAILED,
        f"contract defect: rule '{rule_id}' field '{field}' must be a string or a list",
        ruleId=rule_id,
    )


def _parse_skill_triggers(value: Any) -> dict[str, str]:
    """Parse the contract's `skillTriggers` mapping, or `{}` when absent.

    Skill directory name to one sentence appended to that skill's `description`
    (R8 AC6). Absent is the normal case: a template skill whose description
    already states its trigger phrase needs no entry, because the adaptation
    preserves that description character-for-character.

    A blank key or a blank sentence is refused rather than skipped: both mean an
    entry the Maintainer authored and neither would have any effect, and an
    ineffective declaration is exactly the kind of defect this contract is
    single-sourced to make visible.
    """
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TransformError(
            E_TRANSFORM_FAILED,
            "contract defect: 'skillTriggers' must be a mapping of skill directory "
            "name to the sentence appended to that skill's description",
        )
    triggers: dict[str, str] = {}
    for name, sentence in value.items():
        if not isinstance(name, str) or not name.strip():
            raise TransformError(
                E_TRANSFORM_FAILED,
                "contract defect: 'skillTriggers' declares an entry whose skill "
                "name is blank",
            )
        if not isinstance(sentence, str) or not sentence.strip():
            raise TransformError(
                E_TRANSFORM_FAILED,
                f"contract defect: 'skillTriggers' entry '{name}' declares no "
                "sentence; the entry would append nothing",
                skill=name,
            )
        triggers[name] = sentence.strip()
    return triggers


def _parse_rule(entry: Any, *, index: int) -> Rule:
    if not isinstance(entry, Mapping):
        raise TransformError(
            E_TRANSFORM_FAILED, f"contract defect: rules[{index}] is not a mapping"
        )

    rule_id = entry.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise TransformError(
            E_TRANSFORM_FAILED, f"contract defect: rules[{index}] has no 'id'"
        )

    kind = entry.get("kind")
    if kind not in RULE_KINDS:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule_id}' has unknown kind {kind!r}; "
            f"expected one of {', '.join(RULE_KINDS)}",
            ruleId=rule_id,
        )

    source = entry.get("source")
    if source is not None and not isinstance(source, str):
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule_id}' field 'source' must be a string",
            ruleId=rule_id,
        )
    if source is None and kind not in _SOURCELESS_KINDS:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule_id}' of kind '{kind}' declares no 'source', "
            "so no template file can ever match it",
            ruleId=rule_id,
        )
    if source is not None and kind in _SOURCELESS_KINDS:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule_id}' is '{kind}' and therefore has no "
            "template source, but declares one",
            ruleId=rule_id,
        )

    owner = entry.get("owner", OWNER_KIRO if kind == "kiro-owned" else OWNER_TEMPLATE)
    if owner not in (OWNER_TEMPLATE, OWNER_KIRO):
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule_id}' field 'owner' must be "
            f"'{OWNER_TEMPLATE}' or '{OWNER_KIRO}'",
            ruleId=rule_id,
        )

    template = entry.get("template")
    if template is not None and not isinstance(template, str):
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule_id}' field 'template' must be a string",
            ruleId=rule_id,
        )

    return Rule(
        id=rule_id,
        kind=kind,
        source=source,
        exclude=_as_tuple(entry.get("exclude"), field="exclude", rule_id=rule_id),
        dest=_as_tuple(entry.get("dest"), field="dest", rule_id=rule_id),
        substitutions=_as_tuple(
            entry.get("substitutions"), field="substitutions", rule_id=rule_id
        ),
        template=template,
        owner=owner,
    )


def load_contract(path: str | os.PathLike[str] = DEFAULT_CONTRACT) -> Contract:
    """Load and structurally validate `contract.yaml`.

    Unknown top-level sections are preserved in `raw`, not rejected, so a
    contract carrying sections this stage does not read stays loadable.
    """
    contract_path = Path(path)
    try:
        text = contract_path.read_text(encoding="utf-8")
    except OSError as error:
        raise TransformError(
            E_TRANSFORM_FAILED, f"cannot read contract {contract_path}: {error}"
        ) from error

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise TransformError(
            E_TRANSFORM_FAILED, f"contract {contract_path} is not valid YAML: {error}"
        ) from error

    if not isinstance(document, Mapping):
        raise TransformError(
            E_TRANSFORM_FAILED, f"contract {contract_path} is not a mapping"
        )

    template = document.get("template") or {}
    if not isinstance(template, Mapping):
        raise TransformError(
            E_TRANSFORM_FAILED, "contract defect: 'template' is not a mapping"
        )

    plugin_root = template.get("pluginRoot")
    if not isinstance(plugin_root, str) or not plugin_root.strip():
        raise TransformError(
            E_TRANSFORM_FAILED,
            "contract defect: 'template.pluginRoot' is required; template sources "
            "are rooted at a subdirectory of the marketplace repository",
        )

    raw_rules = document.get("rules")
    if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes)):
        raise TransformError(
            E_TRANSFORM_FAILED, "contract defect: 'rules' is required and must be a list"
        )

    rules = tuple(
        _parse_rule(entry, index=index) for index, entry in enumerate(raw_rules)
    )
    seen: dict[str, int] = {}
    for rule in rules:
        if rule.id in seen:
            raise TransformError(
                E_TRANSFORM_FAILED,
                f"contract defect: duplicate rule id '{rule.id}'",
                ruleId=rule.id,
            )
        seen[rule.id] = 1

    ignore = _as_tuple(document.get("ignore"), field="ignore", rule_id="<ignore>")

    raw_sets = document.get("substitutionSets") or {}
    if not isinstance(raw_sets, Mapping):
        raise TransformError(
            E_TRANSFORM_FAILED, "contract defect: 'substitutionSets' is not a mapping"
        )
    substitution_sets = {
        name: tuple(entries or ()) for name, entries in raw_sets.items()
    }

    output = document.get("output") or {}
    line_endings = "lf"
    if isinstance(output, Mapping):
        line_endings = str(output.get("lineEndings", "lf")).lower()

    skill_triggers = _parse_skill_triggers(document.get("skillTriggers"))

    return Contract(
        path=contract_path,
        contract_version=int(document.get("contractVersion", 1)),
        repository=str(template.get("repository", "")),
        plugin_root=plugin_root.strip().strip("/"),
        rules=rules,
        ignore=ignore,
        substitution_sets=substitution_sets,
        line_endings=line_endings,
        raw=document,
        skill_triggers=skill_triggers,
    )


# ---------------------------------------------------------------------------
# Source enumeration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceFile:
    """One enumerated template file.

    `path` is relative to the plugin root, POSIX-separated, and is the spelling
    every rule glob, every ignore pattern, and every error message uses.
    `is_symlink` is recorded rather than resolved: the stage that writes output
    refuses to follow a link, so it needs to know one was seen.
    """

    path: str
    absolute: Path
    is_symlink: bool = False


def resolve_plugin_root(
    source: str | os.PathLike[str], plugin_root: str
) -> tuple[Path, bool]:
    """Resolve the directory that `plugin_root`-relative paths are relative to.

    The template is a marketplace repository, so the resolved release tree
    contains the plugin at `plugins/senzing-bootcamp/`. `--source` is normally
    that release tree (the `extractedTo` of a `ResolvedRelease`), so the plugin
    root is a subdirectory of it. When that subdirectory is absent, `--source`
    is taken to *be* the plugin root, which is what a caller handing over an
    already-rooted tree means.

    Returns the resolved directory and whether the nested form was used.
    """
    root = Path(source)
    if not root.exists():
        raise TransformError(
            E_TRANSFORM_FAILED, f"source tree does not exist: {root}", source=str(root)
        )
    if not root.is_dir():
        raise TransformError(
            E_TRANSFORM_FAILED, f"source tree is not a directory: {root}", source=str(root)
        )

    nested = root.joinpath(*plugin_root.split("/")) if plugin_root else root
    if nested.is_dir():
        return nested, True
    return root, False


def enumerate_source(
    source: str | os.PathLike[str], plugin_root: str = ""
) -> tuple[SourceFile, ...]:
    """Enumerate every file under the source plugin root, sorted.

    Iteration is sorted at every level and the result is sorted by relative
    path, so the file order this returns — and therefore the order in which
    later stages write output and record manifest entries — is a function of the
    tree's contents alone (R3 AC5).

    Directory symlinks are not descended into, so a link cannot inject content
    from outside the release tree; a symlink to a file is enumerated and flagged.
    """
    root, _ = resolve_plugin_root(source, plugin_root)
    files: list[SourceFile] = []
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        subdirectories.sort()
        filenames.sort()
        base = Path(directory)
        for name in filenames:
            absolute = base / name
            relative = absolute.relative_to(root).as_posix()
            files.append(
                SourceFile(
                    path=relative,
                    absolute=absolute,
                    is_symlink=absolute.is_symlink(),
                )
            )
    return tuple(sorted(files, key=lambda entry: entry.path))


# ---------------------------------------------------------------------------
# Planning: match every enumerated file to exactly one disposition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedFile:
    """A source file and the single rule that claims it."""

    source: SourceFile
    rule: Rule


@dataclass(frozen=True)
class IgnoredFile:
    """A source file claimed by an `ignore` pattern, and that pattern."""

    source: SourceFile
    pattern: str


@dataclass(frozen=True)
class TransformPlan:
    """The complete, ordered disposition of a source tree.

    A plan is the hand-off between matching and materialization: it names every
    source file, the rule that claims it, and the destinations that rule
    declares, in sorted order, with no filesystem side effect taken yet.
    """

    contract: Contract
    plugin_root_path: Path
    tag: str
    files: tuple[PlannedFile, ...]
    ignored: tuple[IgnoredFile, ...]
    staging: Path | None = None
    carry_forward: Path | None = None

    @property
    def outputs(self) -> tuple[PlannedFile, ...]:
        """Planned files whose rule emits something (all but `ignore` rules)."""
        return tuple(planned for planned in self.files if planned.rule.produces_output)

    @property
    def enumerated_count(self) -> int:
        return len(self.files) + len(self.ignored)

    def rule_ids(self) -> tuple[str, ...]:
        """Ids of the rules that claimed at least one file, in contract order."""
        claimed = {planned.rule.id for planned in self.files}
        return tuple(rule.id for rule in self.contract.rules if rule.id in claimed)

    def to_json(self) -> dict[str, Any]:
        return {
            "status": "planned",
            "contractVersion": self.contract.contract_version,
            "contract": str(self.contract.path),
            "templateRelease": self.tag,
            "pluginRoot": self.contract.plugin_root,
            "sourceRoot": str(self.plugin_root_path),
            "staging": str(self.staging) if self.staging is not None else None,
            "carryForward": (
                str(self.carry_forward) if self.carry_forward is not None else None
            ),
            "counts": {
                "enumerated": self.enumerated_count,
                "matched": len(self.files),
                "ignored": len(self.ignored),
                "outputs": len(self.outputs),
            },
            "unmatched": [],
            "files": [
                {
                    "path": planned.source.path,
                    "ruleId": planned.rule.id,
                    "kind": planned.rule.kind,
                    "owner": planned.rule.owner,
                    "dest": list(planned.rule.dest),
                    "isSymlink": planned.source.is_symlink,
                }
                for planned in self.files
            ],
            "ignored": [
                {"path": entry.source.path, "pattern": entry.pattern}
                for entry in self.ignored
            ],
        }


def _unmatched_error(unmatched: Sequence[str], plugin_root: str) -> TransformError:
    """Build the `E_UNMATCHED_FILE` fault, naming every unmatched path.

    Every offending path is named in the message as well as in `unmatched`, and
    the lexicographically first is in `path`. The Maintainer's next action is
    always the same — add a rule or an ignore entry — so the message says so:
    an unmatched file means genuinely new upstream content, which is exactly the
    early warning the ignore list exists to make meaningful.
    """
    listed = ", ".join(unmatched)
    if len(unmatched) == 1:
        message = f"no rule and no ignore entry matches template file: {listed}"
    else:
        message = (
            f"no rule and no ignore entry matches {len(unmatched)} template files: "
            f"{listed}"
        )
    return TransformError(
        E_UNMATCHED_FILE,
        f"{message}. Add a rule or an ignore entry to the contract.",
        path=unmatched[0],
        unmatched=list(unmatched),
        pluginRoot=plugin_root,
    )


def build_plan(
    contract: Contract,
    source: str | os.PathLike[str],
    *,
    tag: str,
    staging: str | os.PathLike[str] | None = None,
    carry_forward: str | os.PathLike[str] | None = None,
    files: Iterable[SourceFile] | None = None,
) -> TransformPlan:
    """Enumerate the source tree and match every file to one disposition.

    Raises `TransformError(E_UNMATCHED_FILE)` when any file matches neither a
    rule nor an ignore entry, before any output exists (R3 AC6). `files` lets a
    caller supply an already-enumerated set; it is enumerated here otherwise.
    """
    plugin_root_path, _ = resolve_plugin_root(source, contract.plugin_root)
    enumerated = (
        enumerate_source(source, contract.plugin_root)
        if files is None
        else tuple(sorted(files, key=lambda entry: entry.path))
    )

    planned: list[PlannedFile] = []
    ignored: list[IgnoredFile] = []
    unmatched: list[str] = []

    for entry in enumerated:
        match = contract.classify(entry.path)
        if match.disposition == "rule":
            assert match.rule is not None  # classify() guarantees it
            planned.append(PlannedFile(source=entry, rule=match.rule))
        elif match.disposition == "ignore":
            assert match.pattern is not None
            ignored.append(IgnoredFile(source=entry, pattern=match.pattern))
        else:
            unmatched.append(entry.path)

    if unmatched:
        raise _unmatched_error(unmatched, contract.plugin_root)

    return TransformPlan(
        contract=contract,
        plugin_root_path=plugin_root_path,
        tag=tag,
        files=tuple(planned),
        ignored=tuple(ignored),
        staging=Path(staging) if staging is not None else None,
        carry_forward=Path(carry_forward) if carry_forward is not None else None,
    )


# ---------------------------------------------------------------------------
# Write containment (R14 AC1, Property 7)
# ---------------------------------------------------------------------------
#
# One path constructor for every read and every write in this module. Refusing a
# path is cheap; discovering after the fact that a build wrote outside
# `powers/senzing-bootcamp/` is not, so the checks are structural rather than
# heuristic and they run before the path is ever handed to the filesystem.

#: Windows drive-letter prefix, which is absolute regardless of the host running
#: the transform. `os.path.isabs` on Linux calls `C:\Windows\...` relative, so a
#: source file literally named that would otherwise become a destination segment.
_DRIVE_LETTER = re.compile(r"\A[A-Za-z]:")

#: Path segments that are never a legitimate output component. `..` escapes, `.`
#: is a no-op spelling that defeats textual comparison, and the empty segment is
#: a doubled separator.
_REJECTED_SEGMENTS = frozenset({"", ".", ".."})


def contained_path(
    root: str | os.PathLike[str],
    relative: str,
    *,
    what: str = "path",
    code: str = E_TRANSFORM_FAILED,
    **details: Any,
) -> Path:
    """Join `relative` under `root`, refusing anything that escapes `root`.

    Three independent gates, because each catches what the others do not:

    1. **Absolute and absolute-looking spellings** are refused outright, in every
       flavor a template file name can carry — `/etc/passwd`, `C:\\Windows\\...`,
       and the UNC `\\\\server\\share\\...` — not only the flavor that happens to
       be absolute on the host running the build.
    2. **Segment inspection** refuses `..`, `.`, and empty segments, after
       normalizing backslashes to `/` so a Windows-style separator cannot smuggle
       a `..` past a POSIX-only split.
    3. **Real-location comparison** resolves symlinks on both sides and requires
       the result to sit under the real `root`, which is the only gate that
       catches a link. Nothing is followed out of `root`: a symlinked ancestor of
       `root` itself is fine, a symlink that leaves `root` is not.

    Raises `TransformError(code)` naming the offending path.
    """
    root_path = Path(root)
    text = str(relative)

    def refuse(reason: str) -> TransformError:
        return TransformError(
            code,
            f"refusing {what} that escapes {root_path}: {text!r} ({reason})",
            path=text,
            root=str(root_path),
            **details,
        )

    if not text.strip():
        raise refuse("empty path")
    if text.startswith("/") or text.startswith("\\") or _DRIVE_LETTER.match(text):
        raise refuse("absolute path")

    normalized = text.replace("\\", "/").rstrip("/")
    if not normalized:
        raise refuse("empty path")
    segments = normalized.split("/")
    for segment in segments:
        if segment in _REJECTED_SEGMENTS:
            raise refuse(f"illegal path segment {segment!r}")

    target = root_path.joinpath(*segments)
    real_root = Path(os.path.realpath(root_path))
    real_target = Path(os.path.realpath(target))
    if real_target != real_root and real_root not in real_target.parents:
        raise refuse("resolves outside the root")
    return target


# ---------------------------------------------------------------------------
# Destinations: where each planned file is written
# ---------------------------------------------------------------------------
#
# A rule's `dest` is relative to the Power root. A `dest` ending in `/` is a
# directory and receives the source's sub-structure below the rule's own literal
# glob prefix, so `scripts/**/*.py` -> `skills/bootcamp-onboarding/scripts/`
# preserves `helpers/a.py` as `helpers/a.py` rather than flattening it. A `dest`
# not ending in `/` is a single file, which is how the `generate` rules name
# `plugin.json` and `mcp.json`.
#
# `{skillName}` expands to the source path segment that the rule's first wildcard
# segment matched, byte-identically, so `skills/<skill-name>/` matches the
# template exactly (R8 AC1).

#: Characters that make a glob segment non-literal.
_GLOB_METACHARACTERS = "*?["

#: The one `dest` placeholder the contract defines.
_SKILL_NAME_PLACEHOLDER = "{skillName}"


@lru_cache(maxsize=None)
def _wildcard_index(pattern: str) -> int | None:
    """Index of the first non-literal segment of a glob, or None if all literal."""
    for index, segment in enumerate(pattern.strip().strip("/").split("/")):
        if any(character in segment for character in _GLOB_METACHARACTERS):
            return index
    return None


@lru_cache(maxsize=None)
def _literal_segment_count(pattern: str) -> int:
    """How many leading segments of a glob are literal, and so are not output."""
    index = _wildcard_index(pattern)
    if index is not None:
        return index
    return len(pattern.strip().strip("/").split("/"))


def _skill_name(rule: Rule, path: str) -> str:
    """The source segment `{skillName}` stands for, taken verbatim (R8 AC1)."""
    index = _wildcard_index(rule.source or "")
    segments = path.split("/")
    if index is None or index >= len(segments):
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule.id}' dest uses {_SKILL_NAME_PLACEHOLDER} "
            f"but its source pattern has no wildcard segment to name: {path}",
            path=path,
            ruleId=rule.id,
        )
    return segments[index]


def _destination_paths(rule: Rule, path: str) -> tuple[str, ...]:
    """Every Power-relative output path one source file produces under one rule.

    A `dest` list means the same source is materialized at each listed location,
    so this returns one path per declared `dest`.
    """
    if not rule.dest:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule.id}' of kind '{rule.kind}' produces output "
            "but declares no 'dest'",
            ruleId=rule.id,
            path=path,
        )

    segments = path.split("/")
    outputs: list[str] = []
    for dest in rule.dest:
        keyed = _SKILL_NAME_PLACEHOLDER in dest
        expanded = (
            dest.replace(_SKILL_NAME_PLACEHOLDER, _skill_name(rule, path))
            if keyed
            else dest
        )
        if not dest.endswith("/"):
            # A file destination: the rule names the output outright.
            outputs.append(expanded)
            continue

        consumed = (
            _wildcard_index(rule.source or "") + 1  # type: ignore[operator]
            if keyed
            else _literal_segment_count(rule.source or "")
        )
        remainder = "/".join(segments[consumed:])
        if not remainder:
            raise TransformError(
                E_TRANSFORM_FAILED,
                f"contract defect: rule '{rule.id}' maps {path!r} onto the directory "
                f"dest {dest!r} with nothing left to name the file",
                ruleId=rule.id,
                path=path,
            )
        outputs.append(expanded.rstrip("/") + "/" + remainder)
    return tuple(outputs)


@dataclass(frozen=True)
class PlannedOutput:
    """One file the transform will write, and where its bytes come from.

    `path` is Power-root-relative and POSIX-separated: the spelling the
    Build_Manifest records and the checkout-drift check compares against.
    `source_path` is the manifest's provenance spelling — repository-root-relative
    within the template, so `plugins/senzing-bootcamp/...` — and is None for
    `kiro-owned` content, which has no template source (R5 AC5).
    """

    path: str
    rule: Rule
    origin: Path
    origin_root: Path
    source_path: str | None = None

    @property
    def owner(self) -> str:
        return self.rule.owner

    @property
    def byte_exact(self) -> bool:
        """`copy` rules are byte-for-byte, line endings included (R10 AC3)."""
        return self.rule.kind == "copy"


def _kiro_owned_entries(
    contract: Contract, rule: Rule, dest: str, base: Path
) -> tuple[tuple[str, Path], ...]:
    """Authored `kiro-owned` files for one `dest`, as (path below dest, origin).

    The relative path is kept separate from the `dest` so a `dest` that ships no
    authored content of its own can be mirrored from a sibling `dest` that does —
    which is exactly the `kiro-hooks` shape, where the Tier 2 skill asset
    directory holds the definitions and the Tier 3 `dev.kiro/hooks/` destination
    receives the same content.

    The contract's `ignore` list is consulted here as well as on the template
    side, against the Power-relative destination path — which, because the
    authored tree mirrors `dest`, is also the authored file's path below its
    base. That is what keeps a byproduct sitting in an authored directory (a
    `__pycache__/` a maintainer's test run left behind) out of the produced tree
    and out of the Build_Manifest, declaratively: the exclusion is a contract
    entry, so nothing in the engine names the byproduct.
    """
    root = contained_path(
        base, dest, what=f"kiro-owned source for rule '{rule.id}'", ruleId=rule.id
    )
    if not dest.endswith("/"):
        if not root.is_file() or contract.ignore_pattern_for(dest) is not None:
            return ()
        return (("", root),)
    if not root.is_dir():
        return ()

    prefix = dest.rstrip("/") + "/"
    entries: list[tuple[str, Path]] = []
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        subdirectories.sort()
        filenames.sort()
        for name in filenames:
            absolute = Path(directory) / name
            relative = absolute.relative_to(root).as_posix()
            if contract.ignore_pattern_for(prefix + relative) is not None:
                continue
            entries.append((relative, absolute))
    return tuple(sorted(entries, key=lambda entry: entry[0]))


def _kiro_owned_outputs(
    contract: Contract, bases: Sequence[Path]
) -> tuple[tuple[PlannedOutput, ...], tuple[str, ...]]:
    """Materialize every `kiro-owned` rule, in contract order, from `bases`.

    `bases` is consulted in order per destination, which is what makes the update
    path both preserving and current: `--carry-forward` comes first, so a
    Kiro-specific adaptation already in the Power is taken unchanged (R5 AC5),
    and `templates/kiro-owned/` comes second, so a destination the existing Power
    has never carried still materializes from the authored content.

    Returns the outputs and the `rule:dest` pairs that had no authored content in
    any base. An unmaterialized destination is *reported*, not fatal: the
    Schema_Validator owns the skill-inventory gate, and halting the engine here
    would make a missing authored asset indistinguishable from a contract defect.
    """
    outputs: list[PlannedOutput] = []
    unmaterialized: list[str] = []
    found: dict[str, tuple[tuple[tuple[str, Path], ...], Path | None]]

    for rule in contract.kiro_owned_rules:
        found = {}
        for dest in rule.dest:
            found[dest] = ((), None)
            for base in bases:
                entries = _kiro_owned_entries(contract, rule, dest, base)
                if entries:
                    found[dest] = (entries, base)
                    break

        # A `dest` shipping no content of its own mirrors the first `dest` that
        # does, which is the `kiro-hooks` shape: the Tier 2 skill asset directory
        # holds the definitions and Tier 3 `dev.kiro/hooks/` receives the same
        # content. Mirroring requires the same shape, so a file `dest` never
        # mirrors a directory.
        donor = next((dest for dest in rule.dest if found[dest][0]), None)

        for dest in rule.dest:
            entries, base = found[dest]
            if (
                not entries
                and donor is not None
                and dest.endswith("/") == donor.endswith("/")
            ):
                entries, base = found[donor]
            if not entries or base is None:
                unmaterialized.append(f"{rule.id}:{dest}")
                continue
            for relative, origin in entries:
                outputs.append(
                    PlannedOutput(
                        path=dest.rstrip("/") + ("/" + relative if relative else ""),
                        rule=rule,
                        origin=origin,
                        origin_root=base,
                        source_path=None,
                    )
                )
    return tuple(outputs), tuple(unmaterialized)


def plan_destinations(
    plan: TransformPlan,
) -> tuple[tuple[PlannedOutput, ...], tuple[str, ...]]:
    """Every output the plan produces, sorted by output path, plus any gaps.

    Three sources feed the output set: files the template supplies, in the plan's
    own sorted order; `kiro-owned` content, taken from `--carry-forward` first
    when it is given (the update path) and from `templates/kiro-owned/` otherwise
    (the create path); and the Power's own `LICENSE`, copied from this
    repository's root (R4 AC4, R14 AC3). All three read a fixed relative layout,
    so the create path and the update path produce the same tree from the same
    input (R3 AC5, R5 AC5).

    Two output paths that collide is a contract defect, never a source defect, so
    it fails closed naming both rules rather than letting one silently win.
    """
    contract = plan.contract
    outputs: list[PlannedOutput] = []

    for planned in plan.outputs:
        for path in _destination_paths(planned.rule, planned.source.path):
            outputs.append(
                PlannedOutput(
                    path=path,
                    rule=planned.rule,
                    origin=planned.source.absolute,
                    origin_root=plan.plugin_root_path,
                    source_path=f"{contract.plugin_root}/{planned.source.path}"
                    if contract.plugin_root
                    else planned.source.path,
                )
            )

    bases: list[Path] = []
    if plan.carry_forward is not None:
        bases.append(Path(plan.carry_forward))
    bases.append(KIRO_OWNED_ROOT)
    kiro_owned, unmaterialized = _kiro_owned_outputs(contract, bases)
    outputs.extend(kiro_owned)

    # The Power's own license, unless a contract rule already produces it. It is
    # a packaging fact of the Power rather than template content, so it is planned
    # for every build regardless of what the template ships (R4 AC4, R14 AC3).
    license_output = _license_output(outputs)
    if license_output is not None:
        outputs.append(license_output)

    claimed: dict[str, PlannedOutput] = {}
    for output in outputs:
        if output.path == MANIFEST_FILENAME:
            raise TransformError(
                E_TRANSFORM_FAILED,
                f"contract defect: rule '{output.rule.id}' would overwrite the "
                f"Build_Manifest at {MANIFEST_FILENAME}",
                path=output.path,
                ruleId=output.rule.id,
            )
        existing = claimed.get(output.path)
        if existing is not None:
            raise TransformError(
                E_TRANSFORM_FAILED,
                "contract defect: two rules produce the same output file "
                f"({existing.rule.id}, {output.rule.id}): {output.path}",
                path=output.path,
                rules=sorted({existing.rule.id, output.rule.id}),
            )
        claimed[output.path] = output

    return tuple(sorted(outputs, key=lambda output: output.path)), unmaterialized


# ---------------------------------------------------------------------------
# Named substitution sets (R10 AC2, R12 AC2, R15 AC7)
# ---------------------------------------------------------------------------
#
# Substitution is the only content rewriting the engine performs on ported text,
# and it is deliberately the dullest mechanism that does the job: literal strings
# and anchored regexes, every one of them read from the contract, applied in the
# order a rule lists its sets, one pass per set. Nothing here is heuristic and
# nothing is model generated, which is what makes two runs over the same input
# produce the same bytes (R3 AC5) and what leaves every byte no set names exactly
# as the template wrote it.
#
# Only two entry shapes are accepted, and an entry that is neither is a contract
# defect rather than a best-effort guess:
#
#   literal   a `find` term matched byte-for-byte, with `literal: true`
#   regex     a `pattern` anchored with `^` and `$`, with `regex: true`
#
# A regex entry is anchored *per line*: `^` matches at a line start and `$`
# before the line's newline, so such an entry rewrites a whole line and cannot
# wander across one. An unanchored pattern is refused. `replace` is literal in
# both shapes — no backreference, no template expansion — so what the contract
# writes is exactly what lands in the output.
#
# **One pass per set** is a correctness guarantee, not an optimization. A set
# whose replacement text contains its own find term would, on a second pass,
# rewrite the destination it just produced, and the output would then depend on
# how many passes ran instead of on the input alone.
#
# **Declared order decides overlaps.** Matches are taken left to right, and where
# two entries of one set could match at the same position the earlier-declared
# entry wins. That is what lets a set list the more specific of two overlapping
# find terms first and have it win, one term being a suffix of the other.
#
# **Inline `INV-NNN` citations are content** (R15 AC7). Ported bootcamp prose
# cites Template_Invariants by number, and such a citation is preserved verbatim —
# including a citation of an invariant the Invariant_Discount_Register discounts,
# because the discount is about packaging construction, not about what the prose
# is allowed to say. Two mechanisms hold that: a citation is matched ahead of
# every entry and handed back unchanged, so no entry can consume one; and the
# citation multiset is compared before and after, so a set that alters one at all
# fails the build closed rather than shipping mangled prose.

#: The two permitted entry shapes, named by the flag each one carries.
SUBSTITUTION_LITERAL = "literal"
SUBSTITUTION_REGEX = "regex"

#: Keys each shape permits. Anything else — a `flags` key, a misspelling — is a
#: defect: silently ignoring a key means silently ignoring the intent behind it.
_LITERAL_ENTRY_KEYS = frozenset({"find", "replace", SUBSTITUTION_LITERAL})
_REGEX_ENTRY_KEYS = frozenset({"pattern", "replace", SUBSTITUTION_REGEX})

#: Rule kinds whose content may be rewritten at all. `copy` is byte-for-byte by
#: definition (R10 AC3) and `ignore` produces no output at all, so a
#: `substitutions` list on one of them is an authoring mistake whose effect would
#: otherwise be silently nothing.
#:
#: `kiro-owned` is here because authored `kiro-owned` content is *authored*, not
#: ported, and an authored asset can still carry a value that has exactly one
#: home in the contract: the `kiro-hooks` rule declares `tool-names` so the
#: `PreToolUse` matcher regex (assumption A3) is a single contract value, and
#: `scripts-dir-strategy` so the <ABSOLUTE_SCRIPTS_DIR> resolution strategy
#: (assumption A4) is another. Both are one-line contract edits plus a rebuild
#: rather than a hand-patched asset (R3 AC4). A `kiro-owned` rule that declares
#: no set is still materialized byte-for-byte, which is every other one.
_SUBSTITUTING_KINDS = frozenset({"substitute", "skill", "generate", "kiro-owned"})

#: An inline Template_Invariant citation as ported prose spells it. The digit
#: count is not fixed: `INV-52` and `INV-052` are different identifiers, both are
#: citations, and both are protected.
_INVARIANT_CITATION_SOURCE = r"INV-[0-9]+"
INVARIANT_CITATION = re.compile(_INVARIANT_CITATION_SOURCE)

#: Group names in a set's combined pattern. The citation group is listed first,
#: so it wins every position it can match.
_CITATION_GROUP = "_citation"
_ENTRY_GROUP_PREFIX = "_entry"


@dataclass(frozen=True)
class Substitution:
    """One entry of a named substitution set, in one of the two permitted shapes.

    `find` carries the literal term for a `literal` entry and the anchored regex
    source for a `regex` entry; `replace` is literal in both cases. `set_name`
    and `index` exist so a fault names the offending entry by where it is
    written in the contract rather than by its text.
    """

    set_name: str
    index: int
    kind: str
    find: str
    replace: str

    @property
    def is_regex(self) -> bool:
        return self.kind == SUBSTITUTION_REGEX

    @property
    def alternative(self) -> str:
        """This entry as one alternative of its set's combined pattern.

        A literal term is escaped, so a `find` containing regex metacharacters
        matches those characters and nothing else.
        """
        return f"(?:{self.find})" if self.is_regex else re.escape(self.find)


@dataclass(frozen=True)
class SubstitutionSet:
    """One named set: its entries, in the order the contract lists them."""

    name: str
    entries: tuple[Substitution, ...]

    def apply(self, text: str) -> str:
        """Rewrite `text` in a single left-to-right pass over this set.

        Matches are non-overlapping and taken left to right; at a position where
        more than one entry could match, the earlier-declared entry wins. No
        replacement this set emits is examined again by this set, so an entry
        whose replacement contains its own find term cannot rewrite the
        destination it just produced.

        An inline `INV-NNN` citation is matched ahead of every entry and returned
        unchanged, so no entry consumes one (R15 AC7).
        """
        if not self.entries:
            return text
        return _combined_pattern(self.entries).sub(_rewriter(self.entries), text)


@lru_cache(maxsize=None)
def _combined_pattern(entries: tuple[Substitution, ...]) -> re.Pattern[str]:
    """One alternation over a whole set: the citation guard, then each entry.

    Python's alternation is first-match-wins at a given position, which is
    exactly "declared order decides overlaps", and `re.sub` never rescans what a
    replacement emitted, which is exactly "single pass per set". `re.MULTILINE`
    is what makes an anchored entry line-anchored.
    """
    parts = [f"(?P<{_CITATION_GROUP}>{_INVARIANT_CITATION_SOURCE})"]
    parts.extend(
        f"(?P<{_ENTRY_GROUP_PREFIX}{position}>{entry.alternative})"
        for position, entry in enumerate(entries)
    )
    return re.compile("|".join(parts), re.MULTILINE)


def _rewriter(entries: tuple[Substitution, ...]) -> Callable[[re.Match[str]], str]:
    """The replacement callback for one set's combined pattern.

    A callback rather than a template string, so `replace` is used literally: a
    backslash or a `\\1` in contract text is output as written.
    """

    def rewrite(match: re.Match[str]) -> str:
        if match.group(_CITATION_GROUP) is not None:
            return match.group(0)
        for position, entry in enumerate(entries):
            if match.group(f"{_ENTRY_GROUP_PREFIX}{position}") is not None:
                return entry.replace
        return match.group(0)  # pragma: no cover - one group always participates

    return rewrite


def invariant_citations(text: str) -> tuple[str, ...]:
    """Every inline `INV-NNN` citation in `text`, in order of appearance."""
    return tuple(INVARIANT_CITATION.findall(text))


def _substitution_defect(message: str, **details: Any) -> TransformError:
    """A malformed substitution set is a contract defect: fail closed, name it."""
    return TransformError(E_TRANSFORM_FAILED, f"contract defect: {message}", **details)


def parse_substitution(entry: Any, *, set_name: str, index: int) -> Substitution:
    """Parse one entry of a named set, accepting only the two permitted shapes.

    Every gate here refuses something that would otherwise turn into output
    nobody asked for: an unrecognized key (an ignored intent), a missing shape
    flag (an entry whose kind is a guess), an unanchored pattern (an entry that
    can match anywhere on a line), a named capture group (a name that would
    collide with the engine's own groups and buy nothing, the replacement being
    literal), and a citation in either half of the entry (R15 AC7).
    """
    spelling = f"{set_name}[{index}]"
    if not isinstance(entry, Mapping):
        raise _substitution_defect(
            f"substitution {spelling} is not a mapping",
            substitutionSet=set_name,
        )

    keys = set(entry)
    if "find" in keys and "pattern" in keys:
        raise _substitution_defect(
            f"substitution {spelling} declares both 'find' and 'pattern'; an entry "
            "is either a literal or an anchored regex, never both",
            substitutionSet=set_name,
        )
    if "find" in keys:
        kind, permitted, term_key = SUBSTITUTION_LITERAL, _LITERAL_ENTRY_KEYS, "find"
    elif "pattern" in keys:
        kind, permitted, term_key = SUBSTITUTION_REGEX, _REGEX_ENTRY_KEYS, "pattern"
    else:
        raise _substitution_defect(
            f"substitution {spelling} declares neither 'find' nor 'pattern'; the "
            "permitted shapes are a literal 'find' term or an anchored 'pattern'",
            substitutionSet=set_name,
        )

    unknown = sorted(keys - permitted)
    if unknown:
        raise _substitution_defect(
            f"substitution {spelling} declares unknown key(s) {unknown}; a "
            f"{kind} entry carries only {sorted(permitted)}",
            substitutionSet=set_name,
        )
    if entry.get(kind) is not True:
        raise _substitution_defect(
            f"substitution {spelling} declares '{term_key}' and so must also "
            f"declare '{kind}: true'",
            substitutionSet=set_name,
        )

    term = entry.get(term_key)
    if not isinstance(term, str) or not term:
        raise _substitution_defect(
            f"substitution {spelling} field '{term_key}' must be a non-empty string",
            substitutionSet=set_name,
        )
    replace = entry.get("replace")
    if not isinstance(replace, str):
        raise _substitution_defect(
            f"substitution {spelling} must declare a literal 'replace' string "
            "(the empty string deletes the matched text)",
            substitutionSet=set_name,
        )

    for label, value in ((term_key, term), ("replace", replace)):
        cited = list(invariant_citations(value))
        if cited:
            raise _substitution_defect(
                f"substitution {spelling} names the invariant citation(s) {cited} "
                f"in its '{label}'; an inline INV-NNN citation in ported prose is "
                "content, including a citation of a discounted invariant, so no "
                "substitution set may target or write one",
                substitutionSet=set_name,
                citations=cited,
            )

    if kind == SUBSTITUTION_REGEX:
        if not term.startswith("^") or not term.endswith("$") or term.endswith("\\$"):
            raise _substitution_defect(
                f"substitution {spelling} pattern {term!r} is not anchored; an "
                "entry must be anchored with '^' and '$', which matches one whole "
                "line, and an unanchored regex is not a permitted entry shape",
                substitutionSet=set_name,
            )
        if "(?P<" in term:
            raise _substitution_defect(
                f"substitution {spelling} pattern {term!r} names a capture group; "
                "the replacement is literal, so a capture buys nothing and its "
                "name would collide with the engine's own groups",
                substitutionSet=set_name,
            )

    substitution = Substitution(
        set_name=set_name, index=index, kind=kind, find=term, replace=replace
    )
    try:
        re.compile(substitution.alternative, re.MULTILINE)
    except re.error as error:
        raise _substitution_defect(
            f"substitution {spelling} {term_key} {term!r} is not a usable "
            f"expression: {error}",
            substitutionSet=set_name,
        ) from error
    return substitution


def parse_substitution_set(name: Any, entries: Any) -> SubstitutionSet:
    """Parse one named set, keeping its entries in declared order."""
    if not isinstance(name, str) or not name.strip():
        raise _substitution_defect(
            f"substitution set name {name!r} must be a non-empty string"
        )
    if (
        entries is None
        or isinstance(entries, (str, bytes))
        or not isinstance(entries, Sequence)
    ):
        raise _substitution_defect(
            f"substitution set '{name}' must be a list of entries",
            substitutionSet=name,
        )
    parsed = tuple(
        parse_substitution(entry, set_name=name, index=index)
        for index, entry in enumerate(entries)
    )
    if not parsed:
        raise _substitution_defect(
            f"substitution set '{name}' declares no entries, so a rule naming it "
            "would rewrite nothing",
            substitutionSet=name,
        )
    return SubstitutionSet(name=name, entries=parsed)


def load_substitution_sets(contract: Contract) -> dict[str, SubstitutionSet]:
    """Every named set the contract declares, parsed and validated, keyed by name.

    The definitions come from the contract and from nowhere else: no substitution
    is written in this file, so a rewrite changes in one place (R3 AC4).
    """
    return {
        str(name): parse_substitution_set(name, entries)
        for name, entries in contract.substitution_sets.items()
    }


def rule_substitution_sets(
    contract: Contract, rule: Rule
) -> tuple[SubstitutionSet, ...]:
    """The sets one rule declares, in the order the *rule* lists them.

    The order is the rule's, not the contract's: sets are applied in the order
    written on the rule, so a later set sees what an earlier one produced. A name
    with no definition, a name listed twice (which would apply that set twice and
    defeat the single-pass guarantee), a `substitutions` list on a rule kind that
    rewrites nothing, and a `substitute` rule declaring no set at all are all
    contract defects.

    Every rule kind's content passes through here, `copy` included, so the
    kind-versus-`substitutions` coherence check below is what makes `copy`'s
    byte-for-byte guarantee structural: a `copy` rule cannot declare a set, so
    nothing can be applied to its bytes (R10 AC3).
    """
    if not rule.substitutions:
        if rule.kind == "substitute":
            # `substitute` *is* "copy, then apply the declared sets", so a rule of
            # that kind with no set rewrites nothing while still normalizing line
            # endings — which would silently mutate CR bytes in content the
            # contract never named, and corrupt a binary file outright. Content
            # nothing may touch belongs to a `copy` rule; this is an authoring
            # mistake, so name it rather than write the file.
            raise _substitution_defect(
                f"rule '{rule.id}' is 'substitute' — copy, then apply the named "
                "substitution sets — but declares none, so it would rewrite "
                "nothing while still normalizing the line endings of content no "
                "set names. Byte-for-byte content belongs to a 'copy' rule.",
                ruleId=rule.id,
            )
        return ()
    if rule.kind not in _SUBSTITUTING_KINDS:
        raise _substitution_defect(
            f"rule '{rule.id}' is '{rule.kind}' and its content is never rewritten, "
            f"but it declares the substitution set(s) {list(rule.substitutions)}",
            ruleId=rule.id,
        )

    available = load_substitution_sets(contract)
    ordered: list[SubstitutionSet] = []
    seen: set[str] = set()
    for name in rule.substitutions:
        if name in seen:
            raise _substitution_defect(
                f"rule '{rule.id}' declares the substitution set '{name}' twice; "
                "each declared set is applied exactly once",
                ruleId=rule.id,
                substitutionSet=name,
            )
        if name not in available:
            raise _substitution_defect(
                f"rule '{rule.id}' declares the substitution set '{name}', which the "
                f"contract does not define; defined sets are {sorted(available)}",
                ruleId=rule.id,
                substitutionSet=name,
            )
        seen.add(name)
        ordered.append(available[name])
    return tuple(ordered)


def _verify_citations_preserved(
    before: str,
    after: str,
    sets: Sequence[SubstitutionSet],
    *,
    what: str,
    **details: Any,
) -> None:
    """Refuse output whose `INV-NNN` citations differ from its source (R15 AC7).

    The per-set citation guard already stops an entry from consuming a citation.
    This is the guarantee behind that mechanism rather than a restatement of it:
    it compares the citation multiset across the whole ordered application, so a
    set that alters a citation by any route at all — spanning into one, or
    assembling one at a seam — halts the build instead of shipping mangled prose.
    """
    original = sorted(invariant_citations(before))
    rewritten = sorted(invariant_citations(after))
    if original == rewritten:
        return
    names = [subset.name for subset in sets]
    raise TransformError(
        E_TRANSFORM_FAILED,
        f"contract defect: substitution set(s) {names} altered an inline INV-NNN "
        f"invariant citation in {what}: {original} became {rewritten}. An inline "
        "citation in ported prose is content, including a citation of a discounted "
        "invariant, and no substitution set may touch one.",
        substitutionSets=names,
        citationsBefore=original,
        citationsAfter=rewritten,
        **details,
    )


def apply_substitutions(
    text: str,
    sets: Sequence[SubstitutionSet],
    *,
    what: str = "content",
    **details: Any,
) -> str:
    """Apply an ordered sequence of sets to `text`, one pass per set.

    Each set runs once over the result of the previous one, which is what
    "applied in declared order" means. `what` and `details` carry the file and
    rule under transformation into the fault path, so a citation fault reads as
    data rather than as prose.
    """
    result = text
    for subset in sets:
        result = subset.apply(result)
    _verify_citations_preserved(text, result, sets, what=what, **details)
    return result


def substitute_content(
    data: bytes,
    sets: Sequence[SubstitutionSet],
    *,
    what: str = "content",
    **details: Any,
) -> bytes:
    """Apply the ordered sets to UTF-8 text bytes.

    Substitution is a text operation, so content a rule sends through it has to
    be text. Bytes that are not UTF-8 reaching here means a rule that rewrites
    content claimed a binary file, which is a contract defect and is refused:
    guessing an encoding would corrupt the file quietly, and `copy` is the kind
    that exists for bytes nothing may touch (R10 AC3).
    """
    if not sets:
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: {what} declares substitution set(s) "
            f"{[subset.name for subset in sets]} but its content is not UTF-8 text, "
            f"so no substitution can be applied: {error}. Byte-for-byte content "
            "belongs to a 'copy' rule.",
            substitutionSets=[subset.name for subset in sets],
            **details,
        ) from error
    return apply_substitutions(text, sets, what=what, **details).encode("utf-8")


# ---------------------------------------------------------------------------
# The `skill` rule kind: layout preservation and additive frontmatter (R8)
# ---------------------------------------------------------------------------
#
# A `skill` rule is `substitute` plus one thing: the skill's `SKILL.md` entry
# point gets its YAML frontmatter adapted to the Agent_Plugins_Format. Everything
# else about the kind is layout, and the layout is deliberately *unchanged*.
#
# Layout: preserved verbatim (R8 AC1, AC2, Property 12)
# -----------------------------------------------------
# The ported skill lands at `skills/<skill-name>/SKILL.md` with `<skill-name>`
# byte-identical to the source directory name, and every other file the skill
# directory owns lands at its own source-relative path below that directory. That
# is the whole mechanism behind cross-reference preservation, and it is already
# implemented by `_destination_paths`: the contract's `dest` is a directory, so
# the remainder of the source path below the rule's glob prefix is carried
# through unchanged, and `{skillName}` expands to the source segment verbatim.
#
# **Sibling `.md` files are NOT relocated into `references/`.** In Template
# _Release 0.5.1 a skill's supporting documents sit directly in the skill
# directory — `skills/bootcamp-onboarding/ground-rules.md`,
# `skills/module-01-business-problem/phase1-discovery.md` — and no template skill
# has a `references/` subdirectory at all. Those files are cited across skills by
# relative link, `../bootcamp-onboarding/ground-rules.md` being the most heavily
# used one in the corpus. Moving them under `references/` would leave every one of
# those links pointing at a path that no longer exists, which is exactly what
# R8 AC2 forbids ("points to the same target file location it referenced before
# transformation") and what Property 12 measures (a cross-reference's
# root-relative resolved target is identical before and after). So the rule here
# is the one the design's research table states: preserve `skills/<name>/`
# verbatim so links resolve unchanged.
#
# A source skill that *does* own a `references/` subdirectory keeps it, at the
# same relative path, for the same reason — preservation is the rule, and the
# subdirectory is part of the layout being preserved.
#
# Frontmatter: additive, never subtractive (R8 AC5, AC6)
# -----------------------------------------------------
# Template frontmatter carries `name` and `description` and nothing else. Both are
# **preserved character-for-character**; `license`, `compatibility`, and
# `metadata` are added. Nothing is removed, reordered ahead of what the template
# wrote, or rewritten.
#
# Preservation is what satisfies R8 AC6. Every template skill's `description`
# already states the skill's trigger phrase as a "Use when ..." clause — for
# example `bootcamp-onboarding` carries *Use when the user says "start the
# bootcamp" ...* — so the adapted `description` contains the source skill's
# trigger phrase because it *is* the source description, not because this engine
# appended anything. That matters: no trigger phrase is declared anywhere in the
# contract, so appending one would mean inventing it in Python, and an invented
# trigger phrase is a phrase the Bootcamper was never told to say. If a phrase
# ever has to be appended, it belongs in the contract as per-skill data and this
# stage reads it from there.
#
# Substitution applies to the **body**, not to the frontmatter, which is what
# makes "preserved character-for-character" true rather than approximate. No
# frontmatter value in release 0.5.1 contains a term any declared set names, so
# the two readings agree on the current corpus; where they could diverge, the
# Schema_Validator's residual-reference check is the gate that notices.
#
# Rejection (R8 AC5)
# ------------------
# A frontmatter block whose `name`, `description`, or `license` would be empty or
# absent is refused, and the run halts with the file, the rule, and the offending
# fields named. `license` is supplied here and so is only ever refused when the
# template declared a blank one.
#
# A `SKILL.md` carrying **no frontmatter block at all** is a different case and is
# not halted on here. There is nothing to adapt and nothing this engine may
# fabricate: a synthesized `name` would not be the template's and a synthesized
# `description` would carry no trigger phrase, so both would produce a skill that
# looks valid and activates on nothing. The body is ported and the document is
# left frontmatter-less, which the Schema_Validator rejects with
# `E_FRONTMATTER_INVALID` — the error the design's catalog assigns to the
# validator, per file, blocking the tag. The engine ports; the validator gates.

#: A skill's entry-point document, per the Agent_Plugins_Format.
SKILL_ENTRY_POINT = "SKILL.md"

#: The YAML frontmatter delimiter, on its own line.
FRONTMATTER_FENCE = "---"

#: The three fields R8 AC5 requires present and non-blank in every adapted
#: frontmatter. `name` and `description` come from the template; `license` is
#: added here.
SKILL_REQUIRED_FIELDS = ("name", "description", "license")

#: Values the adaptation adds. These are the Bootcamp_Power's own packaging facts
#: rather than template->Power *mapping* decisions, which is why they sit here and
#: not in the contract: they are the same for every skill and for every release,
#: exactly as the design's adapted-frontmatter model states them. `version` and
#: `templateRelease` are not here — both are the resolved tag, which arrives with
#: the plan (R2 AC1).
SKILL_LICENSE = "Apache-2.0"
SKILL_COMPATIBILITY = "Requires the Senzing MCP server and Docker."
SKILL_METADATA_AUTHOR = "Senzing"

#: Where a produced skill records which template skill directory it was ported
#: from. Named here rather than only spelled inline below because the
#: Schema_Validator *reads* this field to measure the skill-inventory bijection
#: (R7 AC1, AC2): the engine writes the provenance and the gate consumes it, so a
#: rename must move both at once or move neither.
SKILL_METADATA_FIELD = "metadata"
SKILL_TEMPLATE_SKILL_FIELD = "templateSkill"


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split a leading YAML frontmatter block from the document body.

    Returns `(block, body)`, with `block` None when the document opens with no
    frontmatter. `block` excludes both fences; `body` is everything after the
    closing fence, so `block is None or text == fenced(block) + body` and a
    document that is passed through unchanged is byte-identical.

    A fence is a line that is exactly `---`. An opening fence with no closing
    fence is not frontmatter — it is a thematic break in prose — and is left
    alone.
    """
    lines = text.split("\n")
    if not lines or lines[0] != FRONTMATTER_FENCE:
        return None, text
    for index in range(1, len(lines)):
        if lines[index] == FRONTMATTER_FENCE:
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return None, text


def render_frontmatter(fields: Mapping[str, Any]) -> str:
    """Serialize adapted frontmatter as a fenced YAML block.

    The emitter settings are pinned rather than defaulted, because each one is
    load-bearing: `sort_keys=False` keeps the declared field order (the
    template's fields first, in the order the template wrote them, then what the
    adaptation adds), `allow_unicode=True` writes the em dashes and emoji ported
    prose carries as themselves instead of as escapes, and the wide `width` keeps
    a long `description` on one line so the value a reader sees is the value the
    validator measures. All three are deterministic, so identical fields produce
    identical bytes (R3 AC5).

    Every value round-trips as the string it was: the emitter quotes any scalar
    whose plain spelling would read back as a number, a boolean, or a null, so a
    release tag lands as the characters it was resolved from rather than as a
    float (R2 AC1).
    """
    body = yaml.safe_dump(
        dict(fields),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10**6,
    )
    return f"{FRONTMATTER_FENCE}\n{body}{FRONTMATTER_FENCE}\n"


def _skill_directory(rule: Rule, path: str) -> str | None:
    """The skill directory `path` is the `SKILL.md` entry point of, or None.

    A skill rule's `dest` is the skill directory, so the entry point is
    `<dest>/SKILL.md` and nothing deeper: a `SKILL.md` nested below the skill
    root is a supporting document, not the skill's own frontmatter-bearing entry
    point, and is ported as ordinary content.

    `{skillName}` is matched as a single wildcard segment. It expands to exactly
    one source segment, so the segment *count* of a `dest` is the same expanded
    or not, and the expansion itself has already happened in `path` (R8 AC1).
    """
    suffix = "/" + SKILL_ENTRY_POINT
    if not path.endswith(suffix):
        return None
    parent = path[: -len(suffix)]
    actual = parent.split("/")
    for dest in rule.dest:
        if not dest.endswith("/"):
            continue
        declared = dest.rstrip("/").split("/")
        if len(declared) != len(actual):
            continue
        if all(
            segment == _SKILL_NAME_PLACEHOLDER or segment == seen
            for segment, seen in zip(declared, actual)
        ):
            return parent
    return None


def _frontmatter_defect(message: str, **details: Any) -> TransformError:
    """A frontmatter that cannot be adapted halts the run, naming the fields.

    `E_TRANSFORM_FAILED` rather than a code of its own: the catalog assigns
    `E_FRONTMATTER_INVALID` to the Schema_Validator, which reports one result per
    `SKILL.md` and blocks the tag, and the engine's share of the catalog is the
    single catch-all for a fault that discards staging and leaves the Power
    untouched.
    """
    return TransformError(E_TRANSFORM_FAILED, message, **details)


def _required_field(
    fields: Mapping[str, Any], key: str, *, path: str, rule_id: str
) -> str:
    """One required frontmatter field, refused when empty or absent (R8 AC5)."""
    if key not in fields:
        raise _frontmatter_defect(
            f"skill frontmatter for {path} declares no '{key}'; the "
            f"Agent Plugins fields {list(SKILL_REQUIRED_FIELDS)} are each required "
            "and non-empty, and the adaptation is additive, so a field the "
            "template does not carry cannot be invented here",
            path=path,
            ruleId=rule_id,
            field=key,
        )
    value = fields[key]
    if not isinstance(value, str) or not value.strip():
        raise _frontmatter_defect(
            f"skill frontmatter for {path} declares '{key}' as {value!r}; the "
            f"Agent Plugins fields {list(SKILL_REQUIRED_FIELDS)} are each required "
            "to be a non-empty string",
            path=path,
            ruleId=rule_id,
            field=key,
        )
    return value


def _parse_skill_frontmatter(
    block: str, *, path: str, rule_id: str
) -> dict[str, Any]:
    """Parse a skill's frontmatter block into its declared fields, in order.

    A block that is not a YAML mapping is refused rather than passed through: the
    leading fenced block of a skill's entry point *is* its frontmatter, so a
    block that does not parse as fields is a source document this engine cannot
    port into a valid skill.
    """
    try:
        document = yaml.safe_load(block)
    except yaml.YAMLError as error:
        raise _frontmatter_defect(
            f"skill frontmatter for {path} is not valid YAML: {error}",
            path=path,
            ruleId=rule_id,
        ) from error
    if document is None:
        return {}
    if not isinstance(document, Mapping):
        raise _frontmatter_defect(
            f"skill frontmatter for {path} is not a mapping of fields but a "
            f"{type(document).__name__}",
            path=path,
            ruleId=rule_id,
        )
    return dict(document)


def _decode_skill(data: bytes, *, path: str, rule_id: str) -> str:
    """Decode a skill document, LF-normalized, refusing content that is not text.

    A skill is prose with a YAML header, so bytes that are not UTF-8 reaching here
    means a `skill` rule claimed a binary file. Guessing an encoding would corrupt
    it quietly, so it is refused the same way the substitution path refuses one.
    """
    try:
        return normalize_lf(data).decode("utf-8")
    except UnicodeDecodeError as error:
        raise _frontmatter_defect(
            f"skill document {path} is not UTF-8 text, so its frontmatter cannot "
            f"be read and its body cannot be ported: {error}. Byte-for-byte "
            "content belongs to a 'copy' rule.",
            path=path,
            ruleId=rule_id,
        ) from error


def _with_declared_trigger(description: Any, sentence: str | None) -> Any:
    """`description` carrying the contract's declared trigger sentence (R8 AC6).

    Returns the description unchanged when the contract declares no sentence for
    the skill, when the description already contains it, or when the description
    is not a string — a non-string `description` is a frontmatter defect the
    required-field check reports with its own message rather than something to
    concatenate onto.

    Appending only what is absent is what makes the append idempotent, so the
    create path and the update path produce the same frontmatter and a rebuild
    produces the same bytes (R3 AC5).
    """
    if sentence is None or not isinstance(description, str):
        return description
    if sentence in description:
        return description
    stripped = description.rstrip()
    return f"{stripped} {sentence}" if stripped else sentence


def adapt_skill_frontmatter(
    fields: Mapping[str, Any],
    *,
    skill_name: str,
    tag: str,
    path: str,
    rule_id: str,
    trigger_sentence: str | None = None,
) -> dict[str, Any]:
    """Apply the additive Agent_Plugins_Format adaptation to one skill's fields.

    Additive in three specific senses, each one checkable against the result:

    * **Every template field survives, by value and by position.** The template's
      keys come first, in the order the template wrote them, carrying the values
      the template wrote. `name` is therefore the template's `name` and
      `description` is the template's `description` character-for-character, which
      is what carries the skill's trigger phrase into the Power (R8 AC6).
    * **Only absent keys are written.** `license`, `compatibility`, and
      `metadata` are added when the template does not declare them, and a
      template that does declare one keeps its own value. The same holds one level
      down inside `metadata`.
    * **`name`, `description`, and `license` are required in the result.** All
      three are checked after the merge, so the requirement is about the
      frontmatter that will be written rather than about the one that was read
      (R8 AC5).

    `version` and `templateRelease` are both the resolved Template_Release tag,
    used character-for-character (R2 AC1); `templateSkill` is the source skill
    directory name, which is `skill_name` because the destination preserves it
    byte-identically (R8 AC1).

    `trigger_sentence` is the one exception to "the template's `description`
    survives by value", and it is additive in the same sense the rest of this
    function is: the template's description is kept in full and the contract's
    declared sentence is appended after it. It is passed in rather than looked up
    here because the phrase is *contract data* — the engine may not invent a
    phrase the Bootcamper was never told to say. Almost every template skill
    already states its own phrase, so almost every call passes None.
    """
    adapted: dict[str, Any] = dict(fields)
    if "description" in adapted:
        adapted["description"] = _with_declared_trigger(
            adapted["description"], trigger_sentence
        )
    adapted.setdefault("license", SKILL_LICENSE)
    adapted.setdefault("compatibility", SKILL_COMPATIBILITY)

    declared_metadata = adapted.get(SKILL_METADATA_FIELD)
    if declared_metadata is not None and not isinstance(declared_metadata, Mapping):
        raise _frontmatter_defect(
            f"skill frontmatter for {path} declares 'metadata' as a "
            f"{type(declared_metadata).__name__}; it carries the provenance fields "
            "as a mapping",
            path=path,
            ruleId=rule_id,
            field="metadata",
        )
    metadata: dict[str, Any] = dict(declared_metadata or {})
    metadata.setdefault("author", SKILL_METADATA_AUTHOR)
    metadata.setdefault("version", tag)
    metadata.setdefault(TEMPLATE_RELEASE_FIELD, tag)
    metadata.setdefault(SKILL_TEMPLATE_SKILL_FIELD, skill_name)
    adapted[SKILL_METADATA_FIELD] = metadata

    for key in SKILL_REQUIRED_FIELDS:
        _required_field(adapted, key, path=path, rule_id=rule_id)
    return adapted


def render_skill(
    data: bytes,
    sets: Sequence[SubstitutionSet],
    *,
    skill_name: str,
    tag: str,
    path: str,
    rule_id: str,
    trigger_sentence: str | None = None,
) -> bytes:
    """Render one skill entry point: adapted frontmatter, then a ported body.

    The body passes through the same substitution path every ported document
    takes — the sets the rule declares, in declared order, one pass per set, over
    LF-normalized text — so the skill's learning objectives, instructional steps,
    and exercises reach the Bootcamper unchanged apart from those declared sets,
    inline `INV-NNN` citations included (R7 AC15, R15 AC7).

    A document with no frontmatter block is rendered as body alone, unchanged from
    what `substitute` would have produced. See this section's header for why that
    is not halted on here.
    """
    text = _decode_skill(data, path=path, rule_id=rule_id)
    block, body = split_frontmatter(text)
    ported = apply_substitutions(
        body, sets, what=f"output {path}", path=path, ruleId=rule_id
    )
    if block is None:
        return ported.encode("utf-8")

    adapted = adapt_skill_frontmatter(
        _parse_skill_frontmatter(block, path=path, rule_id=rule_id),
        skill_name=skill_name,
        tag=tag,
        path=path,
        rule_id=rule_id,
        trigger_sentence=trigger_sentence,
    )
    return (render_frontmatter(adapted) + ported).encode("utf-8")


# ---------------------------------------------------------------------------
# The `generate` rule kind: version stamping, provenance, and the license (R2, R4)
# ---------------------------------------------------------------------------
#
# A `generate` rule's output is **rendered**, not ported. Where such a rule names
# a template `source` — the `manifest` rule names `.claude-plugin/plugin.json` —
# that source file is matched so it is accounted for rather than reported as
# unrecognized content, and is then *superseded*: the rendered bytes replace it
# entirely, and not one byte of it reaches the Power. That is why the source is
# read and discarded here rather than never read: the read is what proves the
# matched file exists, and the discard is what the rule kind means.
#
# What is rendered, and from what
# ------------------------------
# The document body lives in `templates/*.j2`, named by the rule's own `template`
# field, and the engine supplies only the values a build cannot know statically.
# `GENERATED_CONTEXTS` maps a Power-relative output path to the function that
# builds its context, and `GENERATED_VERIFIERS` maps the same path to the check
# the rendered bytes must pass. Two small tables rather than one branch per
# artifact: adding an artifact is one entry in each, and an artifact with no entry
# in either falls through to the placeholder documented at `render_output`.
#
# Rendering follows the render contract each template's own header states, and
# the settings are pinned rather than defaulted because each one is load-bearing:
# `StrictUndefined` makes a missing context value raise instead of emitting an
# empty field (a silently empty `version` would defeat the version-match check,
# R2 AC3), `keep_trailing_newline` keeps the single LF the template ends with,
# autoescaping stays off because the output is JSON rather than HTML, and the
# result is written as LF bytes (R16 AC8). Nothing here reads a clock, an
# environment variable, or a run id, so the same `(contract, tag)` renders the
# same bytes (R3 AC5).
#
# Version stamping and provenance (R2 AC1, AC2, AC5)
# --------------------------------------------------
# The resolved tag arrives on the plan and is used **character-for-character**:
# it is passed through `| tojson` in the template, so a tag like `0.5.10` lands as
# the string it was resolved from rather than as a number that lost a digit. It is
# written twice — to the top-level `version`, which is what the Power's version
# *is*, and to `extensions["com.senzing.bootcamp"].templateRelease`, which is what
# the Power's version *came from*. The provenance sits under `extensions` because
# the Agent Plugins v1.0.0 plugin schema's top-level field set is closed, so a
# bare custom field would be reported and ignored (R2 AC5, design defect D3).
#
# `verify_plugin_manifest` re-reads the rendered document and checks all of that
# against the plan. That is deliberately a second opinion rather than an echo: the
# stamping itself is done by the template, so a template edit that dropped the
# `| tojson`, moved the provenance to the top level, or changed the declared
# license would otherwise ship silently and be caught — if at all — only by the
# Schema_Validator much later. Here it halts the build with nothing written.
#
# The Senzing MCP declaration (R4 AC3, R11)
# -----------------------------------------
# The Bootcamp_Power's `mcp.json` is the same rule kind doing the same thing to a
# different document: the `mcp` rule names the template's `.mcp.json` as its
# source, so that file is accounted for by a rule rather than reported as
# unrecognized content, and the rendered document supersedes it whole.
#
# What the rendering *is*, though, is a **translation**, and one with no moving
# parts (R11 AC2). The template declares the server as
# `{"type": "http", "url": "https://mcp.senzing.com/mcp"}`; Agent Plugins spells
# that transport `streamable-http` and expects a `$schema`. All three values —
# the schema URL, the transport type, and the server URL — are fixed by
# requirement rather than by the build (R11 AC1, AC5), so `mcp.json.j2` writes
# them as literals and `mcp_document_context` supplies **nothing**. An empty
# context is the point rather than an omission: a value the engine passed in is a
# value that could differ between two builds, and R11 AC4 makes a near miss — a
# `http://` scheme, a trailing slash, `type: http` — a release-blocking fault.
#
# `verify_mcp_document` then re-reads the rendered document and checks those
# three values by exact comparison, the same second-opinion arrangement
# `verify_plugin_manifest` is: the stamping is the template's, so a template edit
# that dropped the `$schema` line or reverted the transport to the template's
# `http` would otherwise reach the Schema_Validator at the earliest and a
# Bootcamper's failed MCP connection at the latest. Here it halts the build with
# nothing written. Unlike `plugin.json`, the `$schema` field is checked, because
# R11 AC5 makes its absence a named, release-blocking fault of *this* document.
#
# What is deliberately NOT checked, and why
# -----------------------------------------
# The superseded `.mcp.json`'s own content. A gate asserting the matched source
# still says `type: http` at that URL would catch upstream retargeting the Senzing
# server — real drift, since the values above are hardcoded against it — but it
# was weighed and declined on three grounds. First, R11 constrains the *output*
# and fixes these values by requirement, so an upstream edit does not change what
# the Power must declare. Second, most upstream edits to that file are benign —
# Claude also accepts `streamable-http`, and a reformat, a key reorder, or an
# added field changes nothing — so the gate's likeliest effect is blocking
# releases over changes that do not matter. Third, and decisively, `plugin.json`
# has the larger version of the same exposure and no such gate: `plugin.json.j2`
# hardcodes the name, description, author, and keywords that came from the
# template's own manifest. Gating one document and not the other would encode a
# distinction neither the requirements nor the design draws.
#
# FOLLOW-UP, and not this module's to make: template-side drift in a superseded
# document belongs in the Update_Skill's reconciliation report, which is where a
# Maintainer already reviews what a newer release changed (R5 AC4, AC6), and it
# belongs there as a contract-declared expectation rather than as an assertion
# hardcoded here — for both generated artifacts, on one mechanism.
#
# The license (R4 AC4, R14 AC3)
# -----------------------------
# The Power declares `Apache-2.0` and carries a `LICENSE` that matches the one at
# this repository's root. Both halves are needed: a declaration with no license
# file is a claim, and a license file the declaration disagrees with is worse than
# either alone.
#
# The declaration is a literal in `plugin.json.j2` — it is a packaging fact of the
# Power, the same for every release, so there is nothing for a build to compute —
# and `verify_plugin_manifest` checks it equals `POWER_LICENSE`. The file itself is
# **copied byte-for-byte from the repository root `LICENSE`**, which is what makes
# "matches the license declared at this repository's root" true by construction
# rather than by restatement: there is one license text in this repository, and
# the Power carries that one. `render_license` then checks the copied text really
# does declare the identifier the manifest declares, so a root license swapped for
# a different one halts the build instead of shipping a Power whose `plugin.json`
# and whose `LICENSE` disagree.
#
# The Power's `LICENSE` has no template source and no contract rule, so it is
# planned by the engine as a companion of the generated manifest and attributed to
# the synthetic `LICENSE_RULE`. It is skipped when a contract rule already claims
# the path, so declaring one later replaces this backstop rather than colliding
# with it. See the follow-up note at `LICENSE_RULE`.

#: Power-relative path of the generated Agent Plugins plugin manifest (R4 AC2).
PLUGIN_MANIFEST_DEST = "plugin.json"

#: Power-relative path of the generated Agent Plugins MCP manifest (R4 AC3).
MCP_MANIFEST_DEST = "mcp.json"

#: The Senzing_MCP_Server declaration, exactly as R11 AC1 fixes it. Held here as
#: well as in `mcp.json.j2` on purpose: the template writes the document and this
#: is what checks it, so the two agreeing is evidence rather than tautology.
SENZING_SERVER_KEY = "senzing"
SENZING_MCP_URL = "https://mcp.senzing.com/mcp"
MCP_TRANSPORT_TYPE = "streamable-http"

#: The Agent Plugins v1.0.0 MCP document's schema declaration (R4 AC3, R11 AC5).
MCP_SERVERS_FIELD = "mcpServers"
MCP_SCHEMA_FIELD = "$schema"
MCP_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

#: Reverse-domain namespace the Power's provenance is recorded under, outside the
#: plugin schema's fixed top-level field set (R2 AC5).
EXTENSION_NAMESPACE = "com.senzing.bootcamp"

#: The provenance field: the resolved Template_Release the Power was built from.
TEMPLATE_RELEASE_FIELD = "templateRelease"

#: The license identifier the Power declares, matching this repository's root
#: license (R4 AC4, R14 AC3). The same identifier adapted skill frontmatter
#: carries, which is why `SKILL_LICENSE` and this are one value.
POWER_LICENSE = SKILL_LICENSE

#: The Power's license file, and the repository root license it is copied from.
LICENSE_FILENAME = "LICENSE"
REPOSITORY_LICENSE = REPOSITORY_ROOT / LICENSE_FILENAME

#: Heading fragments that identify a license text as the identifier it declares.
#: Only Apache-2.0 is recognized, because it is the only identifier this Power may
#: declare: an unrecognized root license is a fault, not a new mapping to learn.
_LICENSE_HEADINGS: Mapping[str, tuple[str, ...]] = {
    "Apache-2.0": ("Apache License", "Version 2.0"),
}

#: The rule the Power's own `LICENSE` is attributed to in the Build_Manifest.
#: Synthetic — it comes from this engine rather than from the contract — because
#: the license is not a Template_Plugin to Power *mapping* decision: it has no
#: template source, and its content is a fact about this repository (R14 AC3).
#: `copy` because the guarantee is byte-for-byte fidelity to the root license, and
#: `owner: template` (the default) because it is engine-produced and so should be
#: refreshed from the root on every build rather than preserved from the previous
#: Power.
#:
#: FOLLOW-UP, needs a contract change this task may not make: express this as a
#: contract rule with the Power-relative destination `LICENSE`, so the license,
#: like every other output, is declared as data. `plan_destinations` already
#: yields to such a rule, so adding one removes this backstop with no code change.
LICENSE_RULE = Rule(id="license", kind="copy", dest=(LICENSE_FILENAME,))


def license_identifier(text: str) -> str | None:
    """The license identifier `text` declares, or None when unrecognized.

    Pure: text in, identifier out. Matched on the license's own heading rather
    than on a whole-text comparison, so a root license carrying a filled-in
    copyright line still identifies as what it is.
    """
    head = "\n".join(text.split("\n")[:20])
    for identifier, headings in _LICENSE_HEADINGS.items():
        if all(heading in head for heading in headings):
            return identifier
    return None


def render_license(data: bytes) -> bytes:
    """The Power's `LICENSE`: the repository root license, byte-for-byte.

    Byte-for-byte rather than normalized, because "matches the license declared
    at this repository's root" is a claim about the bytes and the root file is
    kept LF by the committed `.gitattributes` anyway (R16 AC8).

    Refuses a root license that does not declare `POWER_LICENSE`: the Power's
    `plugin.json` declares that identifier as a literal, so a mismatch here would
    ship a Power whose declaration and whose license file disagree (R4 AC4,
    R14 AC3).
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"the repository root {LICENSE_FILENAME} is not UTF-8 text, so the "
            f"license identifier it declares cannot be read: {error}",
            path=LICENSE_FILENAME,
            source=str(REPOSITORY_LICENSE),
        ) from error

    identifier = license_identifier(text)
    if identifier != POWER_LICENSE:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"the Bootcamp_Power declares the license {POWER_LICENSE!r}, but the "
            f"license at this repository's root ({REPOSITORY_LICENSE}) declares "
            f"{identifier!r}. The Power's license must match the repository "
            "root's, so nothing was written.",
            path=LICENSE_FILENAME,
            source=str(REPOSITORY_LICENSE),
            declared=POWER_LICENSE,
            found=identifier,
        )
    return data


def _license_output(outputs: Sequence[PlannedOutput]) -> PlannedOutput | None:
    """The Power's `LICENSE`, or None when a contract rule already produces it.

    Yielding to the contract is what keeps this a backstop rather than a second
    home for the decision: the day a rule declares the destination, that rule
    owns it and this returns nothing, with no collision and no code change.
    """
    if any(output.path == LICENSE_FILENAME for output in outputs):
        return None
    return PlannedOutput(
        path=LICENSE_FILENAME,
        rule=LICENSE_RULE,
        origin=REPOSITORY_LICENSE,
        origin_root=REPOSITORY_ROOT,
        source_path=None,
    )


def plugin_manifest_context(plan: TransformPlan) -> dict[str, Any]:
    """The render context for `plugin.json`, per that template's own contract.

    Three values, and nothing a build could hardcode instead: the resolved tag
    (written to `version` and to the provenance field, character-for-character),
    the Template_Plugin `owner/name` slug the template builds its URLs from, and
    the contract version that produced the Power.
    """
    repository = plan.contract.repository.strip()
    if not repository:
        raise TransformError(
            E_TRANSFORM_FAILED,
            "contract defect: 'template.repository' is empty, so the generated "
            f"{PLUGIN_MANIFEST_DEST} would carry a Template_Plugin URL naming no "
            "repository",
            path=PLUGIN_MANIFEST_DEST,
        )
    return {
        "tag": plan.tag,
        "template_repository": repository,
        "contract_version": plan.contract.contract_version,
    }


def mcp_document_context(plan: TransformPlan) -> dict[str, Any]:
    """The render context for `mcp.json`: empty, per that template's own contract.

    Nothing is parameterized because nothing varies. R11 fixes the schema URL,
    the transport type, and the server URL by requirement, identically for every
    release, so `mcp.json.j2` writes all three as literals and there is nothing
    for a build to supply. `plan` is accepted because the registry's builders
    share one signature, and is deliberately unread: a context builder that
    consulted the plan would make the document a function of the build, which is
    exactly what R11 AC1 and AC4 say it must not be.

    Returning `{}` rather than omitting the entry is what registers the artifact:
    a path with no entry falls through to the LF-normalized placeholder, so an
    absent builder would ship the *template's* declaration untranslated.
    """
    return {}


#: Context builders, keyed by Power-relative output path.
GENERATED_CONTEXTS: Mapping[str, Callable[[TransformPlan], dict[str, Any]]] = {
    PLUGIN_MANIFEST_DEST: plugin_manifest_context,
    MCP_MANIFEST_DEST: mcp_document_context,
}


def _generated_defect(message: str, *, path: str, **details: Any) -> TransformError:
    return TransformError(E_TRANSFORM_FAILED, message, path=path, **details)


def _parse_generated_json(data: bytes, *, path: str) -> Mapping[str, Any]:
    """Parse a rendered document, so it can be checked as data rather than text."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _generated_defect(
            f"the generated {path} is not valid UTF-8 JSON: {error}", path=path
        ) from error
    if not isinstance(document, Mapping):
        raise _generated_defect(
            f"the generated {path} is not a JSON object but a "
            f"{type(document).__name__}",
            path=path,
        )
    return document


def verify_plugin_manifest(data: bytes, plan: TransformPlan) -> None:
    """Check the rendered `plugin.json` against the plan (R2 AC1, AC2, AC5, R4 AC4).

    Four checks, each one a requirement rather than a style preference:

    * `version` is the resolved tag **character-for-character**, so the Power's
      version and the Template_Release it was built from cannot differ by a
      normalization (R2 AC1, AC2).
    * The provenance is recorded at
      `extensions["com.senzing.bootcamp"].templateRelease`, as the same tag
      (R2 AC5).
    * No `templateRelease` field sits at the top level, which is the half of
      R2 AC5 that says *outside* the schema's fixed top-level field set: a bare
      custom top-level field is reported and ignored by the schema, so a document
      carrying one is recording provenance where nothing reads it.
    * `license` is `POWER_LICENSE`, the identifier this repository's root license
      declares (R4 AC4, R14 AC3).
    """
    document = _parse_generated_json(data, path=PLUGIN_MANIFEST_DEST)

    version = document.get("version")
    if version != plan.tag:
        raise _generated_defect(
            f"the generated {PLUGIN_MANIFEST_DEST} declares version {version!r}, "
            f"which is not character-for-character the resolved Template_Release "
            f"tag {plan.tag!r}",
            path=PLUGIN_MANIFEST_DEST,
            version=version,
            templateRelease=plan.tag,
        )

    if TEMPLATE_RELEASE_FIELD in document:
        raise _generated_defect(
            f"the generated {PLUGIN_MANIFEST_DEST} records "
            f"'{TEMPLATE_RELEASE_FIELD}' as a top-level field; the Agent Plugins "
            "v1.0.0 plugin schema's top-level field set is fixed, so provenance "
            f"belongs under extensions[{EXTENSION_NAMESPACE!r}]",
            path=PLUGIN_MANIFEST_DEST,
        )

    extensions = document.get("extensions")
    namespace = (
        extensions.get(EXTENSION_NAMESPACE) if isinstance(extensions, Mapping) else None
    )
    if not isinstance(namespace, Mapping):
        raise _generated_defect(
            f"the generated {PLUGIN_MANIFEST_DEST} carries no "
            f"extensions[{EXTENSION_NAMESPACE!r}] object, so the resolved "
            "Template_Release is recorded nowhere",
            path=PLUGIN_MANIFEST_DEST,
        )

    recorded = namespace.get(TEMPLATE_RELEASE_FIELD)
    if recorded != plan.tag:
        raise _generated_defect(
            f"the generated {PLUGIN_MANIFEST_DEST} records "
            f"extensions[{EXTENSION_NAMESPACE!r}].{TEMPLATE_RELEASE_FIELD} as "
            f"{recorded!r}, which is not character-for-character the resolved "
            f"Template_Release tag {plan.tag!r}",
            path=PLUGIN_MANIFEST_DEST,
            recorded=recorded,
            templateRelease=plan.tag,
        )

    declared = document.get("license")
    if declared != POWER_LICENSE:
        raise _generated_defect(
            f"the generated {PLUGIN_MANIFEST_DEST} declares the license "
            f"{declared!r}; the Bootcamp_Power declares {POWER_LICENSE!r}, "
            "matching the license at this repository's root",
            path=PLUGIN_MANIFEST_DEST,
            declared=declared,
            expected=POWER_LICENSE,
        )


def verify_mcp_document(data: bytes, plan: TransformPlan) -> None:
    """Check the rendered `mcp.json` (R4 AC3, R11 AC1, AC2, AC3, AC5).

    Four checks, each one a requirement rather than a style preference, and each
    by **exact** comparison, because R11 AC4 makes a near miss a fault of the
    same standing as an absence — `http://` for `https://`, a trailing slash, a
    `senzing.com` host, `http` for `streamable-http`:

    * `$schema` is present, non-blank, and names the Agent Plugins v1.0.0 MCP
      schema, so the document declares what it conforms to (R11 AC2, AC5).
    * The `senzing` server is declared at all, which is the mandatory dependency
      the whole bootcamp rests on (R11 AC3).
    * Its `url` is exactly `https://mcp.senzing.com/mcp` (R11 AC1, AC4).
    * Its `type` is exactly `streamable-http` — the translated form, never the
      template's `http` (R11 AC1, AC2, AC4).

    `plan` is accepted because the registry's verifiers share one signature, and
    is deliberately unread: unlike `plugin.json`, nothing in this document comes
    from the resolved release, so there is nothing here to check against it.
    """
    document = _parse_generated_json(data, path=MCP_MANIFEST_DEST)

    schema = document.get(MCP_SCHEMA_FIELD)
    if not isinstance(schema, str) or not schema.strip():
        raise _generated_defect(
            f"the generated {MCP_MANIFEST_DEST} omits the '{MCP_SCHEMA_FIELD}' "
            "field, so the document declares no schema to conform to",
            path=MCP_MANIFEST_DEST,
            field=MCP_SCHEMA_FIELD,
        )
    if schema != MCP_SCHEMA_URL:
        raise _generated_defect(
            f"the generated {MCP_MANIFEST_DEST} declares "
            f"'{MCP_SCHEMA_FIELD}' as {schema!r}; the Bootcamp_Power is packaged "
            f"in Agent Plugins v1.0.0 format, whose MCP schema is "
            f"{MCP_SCHEMA_URL!r}",
            path=MCP_MANIFEST_DEST,
            field=MCP_SCHEMA_FIELD,
            declared=schema,
            expected=MCP_SCHEMA_URL,
        )

    servers = document.get(MCP_SERVERS_FIELD)
    server = (
        servers.get(SENZING_SERVER_KEY) if isinstance(servers, Mapping) else None
    )
    if not isinstance(server, Mapping):
        raise _generated_defect(
            f"the generated {MCP_MANIFEST_DEST} does not declare the "
            f"{SENZING_SERVER_KEY!r} server under '{MCP_SERVERS_FIELD}'; the "
            "Senzing MCP server is a mandatory dependency of the bootcamp",
            path=MCP_MANIFEST_DEST,
            server=SENZING_SERVER_KEY,
            declared=sorted(servers) if isinstance(servers, Mapping) else None,
        )

    url = server.get("url")
    if url != SENZING_MCP_URL:
        raise _generated_defect(
            f"the generated {MCP_MANIFEST_DEST} declares the "
            f"{SENZING_SERVER_KEY!r} server URL as {url!r}; it must be exactly "
            f"{SENZING_MCP_URL!r}",
            path=MCP_MANIFEST_DEST,
            server=SENZING_SERVER_KEY,
            declared=url,
            expected=SENZING_MCP_URL,
        )

    transport = server.get("type")
    if transport != MCP_TRANSPORT_TYPE:
        raise _generated_defect(
            f"the generated {MCP_MANIFEST_DEST} declares the "
            f"{SENZING_SERVER_KEY!r} transport type as {transport!r}; the "
            f"template's {'http'!r} declaration is translated to exactly "
            f"{MCP_TRANSPORT_TYPE!r}",
            path=MCP_MANIFEST_DEST,
            server=SENZING_SERVER_KEY,
            declared=transport,
            expected=MCP_TRANSPORT_TYPE,
        )


#: Post-render checks, keyed by Power-relative output path.
GENERATED_VERIFIERS: Mapping[str, Callable[[bytes, TransformPlan], None]] = {
    PLUGIN_MANIFEST_DEST: verify_plugin_manifest,
    MCP_MANIFEST_DEST: verify_mcp_document,
}


def _render_jinja(
    source: str, context: Mapping[str, Any], *, what: str, **details: Any
) -> str:
    """Render one template per the render contract every template header states.

    Jinja is imported here rather than at module import so matching, planning,
    and every ported rule kind stay usable without the renderer's dependency: a
    missing renderer is then a legible failure of *this* step rather than an
    `ImportError` on a module that mostly does not need it.
    """
    try:
        import jinja2
    except ImportError as error:  # pragma: no cover - dev dependency is pinned
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"cannot render {what}: jinja2 is not installed",
            **details,
        ) from error

    environment = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
        newline_sequence="\n",
        autoescape=False,
    )
    try:
        return environment.from_string(source).render(dict(context))
    except jinja2.TemplateError as error:
        raise TransformError(
            E_TRANSFORM_FAILED, f"cannot render {what}: {error}", **details
        ) from error


def render_generation_template(
    rule: Rule, path: str, context: Mapping[str, Any]
) -> bytes:
    """Render the template a `generate` rule names, as LF-terminated UTF-8 bytes.

    The template is resolved through `contained_path` under the engine directory,
    so a contract `template` field cannot read a file from outside the engine's
    own `templates/` tree (R14 AC1).
    """
    if not rule.template:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"contract defect: rule '{rule.id}' is 'generate' but declares no "
            f"'template', so there is nothing to render {path} from",
            ruleId=rule.id,
            path=path,
        )

    template_path = contained_path(
        ENGINE_ROOT,
        rule.template,
        what=f"generation template for rule '{rule.id}'",
        ruleId=rule.id,
        outputPath=path,
    )
    try:
        source = template_path.read_text(encoding="utf-8")
    except OSError as error:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"cannot read the generation template {template_path} for {path}: "
            f"{error}",
            ruleId=rule.id,
            path=path,
            template=str(template_path),
        ) from error

    rendered = _render_jinja(
        source,
        context,
        what=f"{path} from {template_path}",
        ruleId=rule.id,
        path=path,
        template=str(template_path),
    )
    return normalize_lf(rendered.encode("utf-8"))


def render_generated(output: PlannedOutput, data: bytes, plan: TransformPlan) -> bytes:
    """Produce one `generate` output's bytes, superseding its source entirely.

    `data` is the matched template document's content and is deliberately unused
    for an artifact with a generator: the rendered document replaces it whole, so
    not one of its bytes reaches the Power. Both artifacts the contract generates
    — `plugin.json` and `mcp.json` — have one; a path with no entry in
    `GENERATED_CONTEXTS` falls back to the placeholder documented at
    `render_output`, which is what a contract adding a third `generate` rule
    ahead of its generator would produce.
    """
    build = GENERATED_CONTEXTS.get(output.path)
    if build is None:
        return normalize_lf(data)

    rendered = render_generation_template(output.rule, output.path, build(plan))
    verify = GENERATED_VERIFIERS.get(output.path)
    if verify is not None:
        verify(rendered, plan)
    return rendered


# ---------------------------------------------------------------------------
# Content: line endings, hashing, and the per-rule-kind seam
# ---------------------------------------------------------------------------


def normalize_lf(data: bytes) -> bytes:
    """Rewrite CRLF and lone CR to LF (R16 AC8).

    Applied to every text output unconditionally, so the Build_Manifest hash
    describes the file as the committed `.gitattributes` keeps it on checkout on
    every Supported_Platform, and a Windows checkout cannot invalidate it
    (R16 AC9).
    """
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_hex(data: bytes) -> str:
    """The manifest's hash of a file **as written**, not as sourced."""
    return hashlib.sha256(data).hexdigest()


def render_output(output: PlannedOutput, data: bytes, plan: TransformPlan) -> bytes:
    """Produce the bytes for one output from its source bytes.

    This is the single seam every rule kind's content passes through, and the
    declared sets are resolved for **every** kind before anything branches, so a
    rule whose kind and `substitutions` disagree halts the build rather than
    having its declaration silently ignored.

    `copy` (R10 AC3, R12 AC1)
        Returns its source bytes, unmodified: no substitution, and no line-ending
        normalization either. Byte-for-byte is the whole point of the kind — one
        rewritten byte in `d3.v7.min.js` is a corrupted dependency and one in a
        PNG or a PDF is a corrupted asset — and it is structural rather than
        merely intended, because a `copy` rule cannot declare a substitution set
        (the resolution above refuses one) and nothing else here touches its
        bytes. This is the only kind exempt from R16 AC8.

    `substitute` (R10 AC2, R12 AC2)
        Copies, then applies exactly the sets the rule declares, in the rule's
        declared order, one pass per set, over LF-normalized text. Every other
        byte survives as the template wrote it: the sets are literal terms and
        line-anchored regexes read from the contract, so a byte no set names is
        not a candidate for rewriting, and inline `INV-NNN` citations are matched
        ahead of every entry and compared before and after (R15 AC7). A
        `substitute` rule declares at least one set, so its content is always
        text and normalizing its line endings can never corrupt a binary.

    `generate` (R2, R4 AC2, AC3, AC4, R11, R14 AC3)
        Rendered from the `templates/*.j2` document the rule names plus the
        resolved release, which **supersedes the matched source entirely** — the
        matched template document is read so it is accounted for and then
        discarded, and not one of its bytes reaches the Power. Both generated
        artifacts are complete. For `plugin.json`, the resolved tag is stamped
        character-for-character into `version` and into
        `extensions["com.senzing.bootcamp"].templateRelease`, and the declared
        license is checked against this repository's root license; the Power's own
        `LICENSE` is planned alongside it, copied byte-for-byte from the
        repository root. For `mcp.json`, the template's
        `{"type": "http", "url": "https://mcp.senzing.com/mcp"}` declaration is
        translated into the Agent Plugins `streamable-http` form with a `$schema`,
        every value of it a literal in the template because R11 fixes all three.
        Each rendered document is verified before it is written. See that
        section's header for the whole model.

    `skill` (R7 AC15, R8)
        `substitute` for every file a skill directory owns, plus additive
        Agent_Plugins_Format frontmatter adaptation on the skill's own `SKILL.md`
        entry point. The layout is untouched — the entry point lands at
        `skills/<skill-name>/SKILL.md` with the source directory name
        byte-identical, and every supporting document keeps its own
        source-relative path — which is what leaves the corpus's relative
        cross-references resolving to the same targets they resolved to before
        (R8 AC1, AC2). Frontmatter adaptation preserves the template's `name` and
        `description` character-for-character and adds `license`,
        `compatibility`, and `metadata`; an empty or absent `name`,
        `description`, or `license` halts the run (R8 AC5, AC6). See that
        section's header for the whole model, the reason sibling `.md` files stay
        where the template put them, and the reason a `SKILL.md` with no
        frontmatter at all is the Schema_Validator's to reject rather than this
        stage's.

    `kiro-owned` (R3 AC4, R5 AC5)
        Materialized from the authored tree — or from `--carry-forward` on the
        update path — with line endings normalized and, where the rule declares
        them, the named sets applied. Almost every `kiro-owned` rule declares
        none and is therefore byte-for-byte authored content. `kiro-hooks`
        declares two, and only because each carries a value that must have
        exactly one home in the contract: `tool-names` for the `PreToolUse`
        matcher (assumption A3) and `scripts-dir-strategy` for the
        <ABSOLUTE_SCRIPTS_DIR> resolution strategy (assumption A4). Correcting
        either after its Test_Checklist observation is then a one-line contract
        edit plus a rebuild, never an edit to an asset or to this file. No set
        names an interpreter or either Hook_Command_String placeholder, so a
        shipped `command` travels through unchanged and stays the
        Hook_Installer's to resolve (R7 AC6, R16 AC3, AC4).

    Every rule kind the contract declares is therefore complete here. The one
    remaining fallback is structural rather than pending: a `generate` rule whose
    output path no generator is registered for yields its source bytes with line
    endings normalized — a *placeholder* that keeps the staging tree structurally
    complete and hash-stable while being, by construction, unadapted content the
    Schema_Validator rejects.
    """
    sets = rule_substitution_sets(plan.contract, output.rule)
    if output.rule is LICENSE_RULE:
        return render_license(data)
    if output.byte_exact:
        # Unreachable with a non-empty `sets`: a `copy` rule declaring one is a
        # contract defect and already halted above.
        return data
    if output.rule.kind == "generate":
        return render_generated(output, data, plan)
    if output.rule.kind == "skill":
        skill_directory = _skill_directory(output.rule, output.path)
        if skill_directory is not None:
            skill_name = skill_directory.rsplit("/", 1)[-1]
            return render_skill(
                data,
                sets,
                skill_name=skill_name,
                tag=plan.tag,
                path=output.path,
                rule_id=output.rule.id,
                trigger_sentence=plan.contract.skill_triggers.get(skill_name),
            )
    return substitute_content(
        normalize_lf(data),
        sets,
        what=f"output {output.path}",
        path=output.path,
        ruleId=output.rule.id,
    )


def _read_origin_bytes(output: PlannedOutput) -> bytes:
    """Read one source file, refusing to follow a link out of its own root."""
    origin = contained_path(
        output.origin_root,
        output.origin.relative_to(output.origin_root).as_posix(),
        what="source file",
        ruleId=output.rule.id,
        outputPath=output.path,
    )
    if not origin.is_file():
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"source file for {output.path} is not a readable regular file: {origin}",
            path=output.path,
            ruleId=output.rule.id,
            source=str(origin),
        )
    try:
        return origin.read_bytes()
    except OSError as error:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"cannot read source file for {output.path}: {error}",
            path=output.path,
            ruleId=output.rule.id,
            source=str(origin),
        ) from error


# ---------------------------------------------------------------------------
# Ported scripts: co-location, vendored assets, and dangling references (R10)
# ---------------------------------------------------------------------------
#
# Almost all of R10 is contract data that the stages above already execute, and
# saying so is the point rather than an omission — a mapping decision written in
# Python would be a decision the Create_Skill and the Update_Skill could disagree
# about (R3 AC4):
#
# **Co-location (R10 AC1).** `scripts-owned` maps `scripts/**/*.py` onto the
# directory dest `skills/bootcamp-onboarding/scripts/`, so `_destination_paths`
# carries the remainder of each source path below the rule's literal glob prefix
# through unchanged: `scripts/recap_checkpoint.py` lands at
# `skills/bootcamp-onboarding/scripts/recap_checkpoint.py` and
# `scripts/helpers/a.py` at `.../scripts/helpers/a.py`. Every ported script
# therefore keeps its file name and its relative sub-structure, and the scripts
# that sat beside each other in the template still sit beside each other in the
# one owning skill — which is what keeps the template's same-directory module
# imports (`import recap_checkpoint`, `import docker_lifecycle`) resolving.
#
# **Vendored assets (R10 AC3).** `scripts-vendor` is a `copy` rule onto
# `skills/bootcamp-onboarding/scripts/vendor/`, so `render_output` returns its
# source bytes untouched — no substitution, no line-ending normalization — at the
# same relative location. `scripts-assets` does the same for the non-Python files
# that sit beside the scripts, `senzing_logo_light.png` among them.
#
# **The root path token and the manifest path (R10 AC2).** `scripts-owned`
# declares `plugin-root`, `manifest-path`, and `tool-names`, and the sets do the
# rewriting: `${CLAUDE_PLUGIN_ROOT}` becomes `${PLUGIN_ROOT}`, and
# `feedback-capture.py`'s `../.claude-plugin/plugin.json` becomes
# `../plugin.json` because `manifest-path` lists the parent-relative form first
# and the earlier-declared entry wins at a position both could match.
#
# Missing-asset detection (R10 AC4)
# ---------------------------------
# The one behavior here that is *not* contract data. A ported script that opens a
# file under a `vendor/` directory the template does not ship is a script that
# fails at runtime with a stack trace the Bootcamper cannot act on, so the build
# halts naming the script and the asset instead.
#
# Detection is deliberately narrow, and narrow in a direction that matters: only
# references *into a `vendor/` directory* are checked. Scripts name plenty of
# paths that do not exist yet and are not supposed to — the recap PDF they write,
# the screenshots they capture, the state files they create — so a general
# "every path a script names must exist" check would halt every build on content
# that is working exactly as intended. A `vendor/` path is different in kind:
# vendored content is third-party, checked in, and never produced at runtime, so
# a reference to one that the source lacks is unambiguously a broken port.
#
# Both spellings the corpus actually uses are recognized, which is what keeps the
# check from being vacuous:
#
#   path literal      `"vendor/d3.v7.min.js"`, `"${PLUGIN_ROOT}/scripts/vendor/…"`
#   joined segments   `os.path.join(here, "vendor", "d3.v7.min.js")`,
#                     `Path(__file__).parent / "vendor" / "d3.v7.min.js"`
#
# Release 0.5.1 uses only the second: `senzing_viz_server.py` inlines the
# vendored D3 through `os.path.join(..., "vendor", "d3.v7.min.js")`. A detector
# that read path literals alone would find zero references in the real template
# and would therefore guarantee nothing about it.
#
# Availability is judged against the **template source** (AC4's own wording), not
# against the staging tree: `scripts-vendor` is a `copy` rule that preserves the
# relative location, so the two agree, and asking the source keeps the check
# independent of write order. The destination side — every script and asset a
# *produced* Power references — is the Schema_Validator's exhaustive check, which
# reports per finding and blocks tagging.
#
# Every offending reference in the whole script set is collected before the fault
# is raised, so one run names all of them rather than making a Maintainer rebuild
# once per missing file. The run halts before any file is written, and
# `write_staging` discards the staging tree on the way out regardless, so the
# destination `scripts/` tree is unchanged (R10 AC4, R4 AC8).
#
# `vendored_asset_references`, `vendored_asset_paths`, and
# `missing_vendored_assets` are pure functions over text and path strings, with no
# filesystem and no plan involved, so the property tests can drive them in memory.

#: Suffix of a ported Python script, the file kind whose references are checked.
SCRIPT_SUFFIX = ".py"

#: The directory segment that marks third-party vendored content. A reference is
#: "vendored" exactly when its path crosses a segment spelled this way.
VENDOR_SEGMENT = "vendor"

#: One path segment as a script writes it. Deliberately excludes `/`, quotes, and
#: whitespace, so a match cannot run off the end of a path into the code after it.
_PATH_SEGMENT = r"[A-Za-z0-9_@+~.-]+"

#: A final segment that names a file rather than a directory: it carries an
#: extension. This is what stops `["vendor", "helpers"]` — a list of names, not a
#: path — from being read as a reference to a file.
_ASSET_FILENAME = rf"{_PATH_SEGMENT}\.[A-Za-z0-9]+"

#: A vendored asset written as one path literal. The leading lookbehind requires
#: `vendor` to start a path segment, so `vendored-D3` in a comment and a
#: `myvendor/` directory are both left alone; a `${PLUGIN_ROOT}/scripts/` prefix
#: falls outside the segment alphabet, so the match begins at `vendor/` and the
#: reference is already rooted where it is compared.
_VENDORED_PATH_LITERAL = re.compile(
    rf"(?<![A-Za-z0-9_@+~.-]){VENDOR_SEGMENT}/(?:{_PATH_SEGMENT}/)*{_ASSET_FILENAME}"
)

#: One quoted path segment, as `os.path.join` and the `/` operator take them.
_QUOTED_SEGMENT = r"""(?:'[^'\n]*'|"[^"\n]*")"""

#: What separates two segments of a joined path: an argument comma or a `/`.
_SEGMENT_JOIN = r"\s*[,/]\s*"

#: A vendored asset assembled from quoted segments rather than written as a path.
_VENDORED_SEGMENT_CHAIN = re.compile(
    rf"(?:'{VENDOR_SEGMENT}'|\"{VENDOR_SEGMENT}\")"
    rf"(?P<rest>(?:{_SEGMENT_JOIN}{_QUOTED_SEGMENT})+)"
)

_QUOTED_SEGMENT_PATTERN = re.compile(_QUOTED_SEGMENT)


def _chained_reference(segments: Sequence[str]) -> str | None:
    """The `vendor/`-rooted path a chain of quoted segments names, or None.

    The chain is read up to and including the first segment that names a file,
    because the segments after that one are the call's other arguments rather
    than more of the path: `os.path.join(base, "vendor", "d3.v7.min.js")` names
    `vendor/d3.v7.min.js` and nothing beyond it. A chain that never reaches a
    file name is not a reference to an asset — it is a list of directory names —
    and a segment that is not a path segment at all abandons the chain.
    """
    collected = [VENDOR_SEGMENT]
    for segment in segments:
        if re.fullmatch(_PATH_SEGMENT, segment) is None:
            return None
        collected.append(segment)
        if re.fullmatch(_ASSET_FILENAME, segment) is not None:
            return "/".join(collected)
    return None


def vendored_asset_references(text: str) -> tuple[str, ...]:
    """Every vendored asset `text` names, `vendor/`-rooted, in order of appearance.

    Pure: text in, path strings out. Each reference is returned in the one
    spelling that can be compared against a source tree — rooted at its `vendor/`
    segment, with whatever prefix the script wrote (`${PLUGIN_ROOT}/scripts/`, a
    `__file__`-relative directory, nothing at all) dropped, because that prefix
    is resolved at runtime and says nothing about which file is meant.

    Repeats collapse: a script naming the same asset three times has one broken
    reference to fix, not three.
    """
    found: list[tuple[int, str]] = []
    for match in _VENDORED_PATH_LITERAL.finditer(text):
        found.append((match.start(), match.group(0)))
    for match in _VENDORED_SEGMENT_CHAIN.finditer(text):
        segments = [
            piece
            for quoted in _QUOTED_SEGMENT_PATTERN.findall(match.group("rest"))
            for piece in quoted[1:-1].split("/")
        ]
        reference = _chained_reference(segments)
        if reference is not None:
            found.append((match.start(), reference))

    ordered: list[str] = []
    for _, reference in sorted(found):
        if reference not in ordered:
            ordered.append(reference)
    return tuple(ordered)


def vendored_asset_paths(available: Iterable[str]) -> frozenset[str]:
    """Every `vendor/`-rooted spelling that a set of source paths supplies.

    Pure: path strings in, path strings out. A source file at
    `scripts/vendor/d3.v7.min.js` supplies `vendor/d3.v7.min.js`, and one at
    `scripts/vendor/graph/asset.js` supplies `vendor/graph/asset.js` — the suffix
    beginning at the `vendor/` segment, which is the spelling a reference is
    reduced to. Matching is segment-aligned by construction, so `vendor/x.js`
    cannot be satisfied by a source file named `notvendor/x.js`.
    """
    supplied: set[str] = set()
    for path in available:
        segments = path.split("/")
        for index, segment in enumerate(segments):
            if segment == VENDOR_SEGMENT:
                supplied.add("/".join(segments[index:]))
    return frozenset(supplied)


def missing_vendored_assets(text: str, available: Iterable[str]) -> tuple[str, ...]:
    """The vendored assets `text` names that `available` does not supply (R10 AC4).

    Pure, and the whole of the detection rule: the references a script makes,
    minus the ones the source tree can satisfy, in order of appearance.
    """
    supplied = vendored_asset_paths(available)
    return tuple(
        reference
        for reference in vendored_asset_references(text)
        if reference not in supplied
    )


@dataclass(frozen=True)
class MissingAsset:
    """One ported script's reference to a vendored asset the source does not ship.

    `path` is the referencing script's Power-relative output path and
    `source_path` its provenance spelling in the template, so the fault names the
    script the Maintainer has to look at in both the vocabularies they have.
    """

    path: str
    source_path: str | None
    asset: str

    def to_json(self) -> dict[str, Any]:
        return {"path": self.path, "sourcePath": self.source_path, "asset": self.asset}


def _is_ported_script(output: PlannedOutput) -> bool:
    """Whether `output` is a ported script whose asset references are checked.

    Template-sourced, rewritten rather than copied, and a Python module. A `copy`
    output is byte-for-byte third-party or binary content — a vendored script is
    not a *ported* script, and scanning a minified bundle for paths would report
    the bundle's own internals — and `kiro-owned` content has no template source
    to have referenced anything from.
    """
    return (
        output.source_path is not None
        and not output.byte_exact
        and output.path.endswith(SCRIPT_SUFFIX)
    )


def _source_asset_paths(plan: TransformPlan) -> tuple[str, ...]:
    """Every enumerated source path, matched and ignored alike, sorted.

    R10 AC4 asks whether an asset is absent *from the template source*, so the
    ignore list is included: a file the contract deliberately does not port is
    still a file the template ships, and reporting it as missing would name the
    wrong defect.
    """
    return tuple(
        sorted(
            [planned.source.path for planned in plan.files]
            + [entry.source.path for entry in plan.ignored]
        )
    )


def find_missing_assets(
    plan: TransformPlan, outputs: Sequence[PlannedOutput]
) -> tuple[MissingAsset, ...]:
    """Every ported script reference to a vendored asset the source lacks (R10 AC4).

    Scans the scripts **as ported** — the declared substitution sets already
    applied — because the reference that matters is the one the shipped script
    will resolve at runtime, and compares each against the template source.
    Returns them all, in output order, so one run reports every broken reference.
    """
    scripts = tuple(output for output in outputs if _is_ported_script(output))
    if not scripts:
        return ()

    supplied = vendored_asset_paths(_source_asset_paths(plan))
    missing: list[MissingAsset] = []
    for output in scripts:
        rendered = render_output(output, _read_origin_bytes(output), plan)
        # Detection is a scan, not output: a script whose bytes are not text is
        # already the Schema_Validator's to reject, and a replacement character
        # cannot fabricate a `vendor/` path, so scanning what decodes is strictly
        # better than skipping the file.
        text = rendered.decode("utf-8", errors="replace")
        for reference in vendored_asset_references(text):
            if reference not in supplied:
                missing.append(
                    MissingAsset(
                        path=output.path,
                        source_path=output.source_path,
                        asset=reference,
                    )
                )
    return tuple(missing)


def _missing_asset_error(missing: Sequence[MissingAsset]) -> TransformError:
    """Build the `E_MISSING_ASSET` fault, naming every script and every asset.

    The lexicographically first offender is in `path`/`asset` and all of them are
    in `missing`, so a caller reads one broken reference or the whole set without
    parsing prose — the same shape `E_UNMATCHED_FILE` uses. The Maintainer's next
    action is always one of two things, so the message says which two: the asset
    belongs in the template's `scripts/vendor/`, or the reference in the script is
    stale and upstream has to drop it.
    """
    first = missing[0]
    listed = ", ".join(f"{entry.path} -> {entry.asset}" for entry in missing)
    if len(missing) == 1:
        subject = (
            f"ported script {first.path} references the vendored asset "
            f"{first.asset!r}, which the template source does not ship"
        )
    else:
        subject = (
            f"{len(missing)} ported script references name a vendored asset the "
            f"template source does not ship: {listed}"
        )
    return TransformError(
        E_MISSING_ASSET,
        f"{subject}. Nothing was written: the port halts so the Power never ships "
        "a script that fails at runtime on a file that is not there. Either the "
        "asset belongs under the template's scripts/vendor/, or the reference is "
        "stale and upstream has to drop it.",
        path=first.path,
        sourcePath=first.source_path,
        asset=first.asset,
        missing=[entry.to_json() for entry in missing],
    )


# ---------------------------------------------------------------------------
# Staging output and the Build_Manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestEntry:
    """One `.build-manifest.json` `files` row."""

    path: str
    rule_id: str
    owner: str
    source_path: str | None
    sha256: str

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ruleId": self.rule_id,
            "owner": self.owner,
            "sourcePath": self.source_path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class BuildManifest:
    """The Build_Manifest: provenance plus the reconciliation and drift baseline.

    `owner` drives update-time preservation (R5 AC5); `sha256` is the hash of the
    file **as written**, which is what the checkout-drift check compares a
    checked-out file against (R16 AC9) and what conflict detection compares across
    builds (R5 AC6).

    The document carries no timestamp, no run id, and no absolute path, and
    `serialize` fixes the separators and the key order, so identical input yields
    an identical manifest byte-for-byte (R3 AC5).
    """

    template_release: str
    contract_version: int
    files: tuple[ManifestEntry, ...]
    manifest_version: int = MANIFEST_VERSION

    def to_json(self) -> dict[str, Any]:
        return {
            "manifestVersion": self.manifest_version,
            "templateRelease": self.template_release,
            "contractVersion": self.contract_version,
            "files": [entry.to_json() for entry in self.files],
        }

    def serialize(self) -> bytes:
        return (
            json.dumps(
                self.to_json(),
                indent=2,
                sort_keys=False,
                ensure_ascii=False,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")


@dataclass(frozen=True)
class StagedOutput:
    """One file written into staging, with the hash of the bytes as written."""

    path: str
    rule_id: str
    owner: str
    source_path: str | None
    sha256: str
    size: int

    def manifest_entry(self) -> ManifestEntry:
        return ManifestEntry(
            path=self.path,
            rule_id=self.rule_id,
            owner=self.owner,
            source_path=self.source_path,
            sha256=self.sha256,
        )


@dataclass(frozen=True)
class StagingResult:
    """A complete staging tree, ready for the Schema_Validator and then the swap."""

    plan: TransformPlan
    staging: Path
    outputs: tuple[StagedOutput, ...]
    manifest: BuildManifest
    unmaterialized: tuple[str, ...] = ()

    @property
    def manifest_path(self) -> Path:
        return self.staging / MANIFEST_FILENAME

    def to_json(self) -> dict[str, Any]:
        document = self.plan.to_json()
        document["status"] = "staged"
        document["counts"]["written"] = len(self.outputs)
        document["manifest"] = MANIFEST_FILENAME
        document["unmaterialized"] = list(self.unmaterialized)
        document["written"] = [
            {
                "path": output.path,
                "ruleId": output.rule_id,
                "owner": output.owner,
                "sourcePath": output.source_path,
                "sha256": output.sha256,
            }
            for output in self.outputs
        ]
        return document


def discard_staging(staging: str | os.PathLike[str]) -> None:
    """Remove a staging tree completely, leaving no residue (R4 AC8, R5 AC7).

    Best effort by design: it runs on the failure path, where a second exception
    would replace the fault the Maintainer needs to see with a cleanup detail.
    """
    shutil.rmtree(Path(staging), ignore_errors=True)


def _prepare_staging(staging: Path) -> None:
    """Claim an absent or empty staging directory, or refuse to touch it.

    Refusing a non-empty staging directory is what lets the failure path delete
    the whole tree without ever destroying content the engine did not create.
    """
    try:
        if staging.exists() or staging.is_symlink():
            if staging.is_symlink() or not staging.is_dir():
                raise TransformError(
                    E_WRITE_FAILED,
                    f"staging path exists and is not a directory: {staging}",
                    staging=str(staging),
                )
            if any(staging.iterdir()):
                raise TransformError(
                    E_WRITE_FAILED,
                    f"staging directory is not empty, refusing to write into it: "
                    f"{staging}",
                    staging=str(staging),
                )
            return
        staging.mkdir(parents=True)
    except OSError as error:
        raise TransformError(
            E_WRITE_FAILED,
            f"cannot create staging directory {staging}: {error}",
            staging=str(staging),
        ) from error


def _write_staged_file(staging: Path, relative: str, data: bytes) -> None:
    """Write one contained file into staging, never through a symlink."""
    target = contained_path(
        staging, relative, what="output file", code=E_TRANSFORM_FAILED
    )
    walk = staging
    for segment in relative.split("/"):
        walk = walk / segment
        if walk.is_symlink():
            raise TransformError(
                E_WRITE_FAILED,
                f"refusing to write through the symlink {walk} for output {relative}",
                path=relative,
                staging=str(staging),
            )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
    except OSError as error:
        raise TransformError(
            E_WRITE_FAILED,
            f"cannot write output {relative}: {error}",
            path=relative,
            staging=str(staging),
        ) from error


def write_staging(plan: TransformPlan) -> StagingResult:
    """Materialize the plan into `plan.staging` and emit the Build_Manifest.

    Nothing outside the staging directory is touched, so the target keeps its
    prior bytes no matter what happens here. On **any** fault the staging tree is
    discarded before the fault propagates, which is what leaves no residue behind
    a failed run (R4 AC8, R5 AC7).

    Iteration follows `plan_destinations`, which is sorted by output path, and the
    manifest records the files in that same order, so the manifest bytes are a
    function of the tree's content alone (R3 AC5).
    """
    if plan.staging is None:
        raise TransformError(
            E_TRANSFORM_FAILED, "no staging directory was given; nothing can be written"
        )

    staging = Path(plan.staging)
    _prepare_staging(staging)

    try:
        outputs, unmaterialized = plan_destinations(plan)

        # Before the first byte is written: a ported script naming a vendored
        # asset the template does not ship halts here, so the destination
        # `scripts/` tree is not merely rolled back but never touched (R10 AC4).
        missing = find_missing_assets(plan, outputs)
        if missing:
            raise _missing_asset_error(missing)

        staged: list[StagedOutput] = []
        for output in outputs:
            data = render_output(output, _read_origin_bytes(output), plan)
            _write_staged_file(staging, output.path, data)
            staged.append(
                StagedOutput(
                    path=output.path,
                    rule_id=output.rule.id,
                    owner=output.owner,
                    source_path=output.source_path,
                    sha256=sha256_hex(data),
                    size=len(data),
                )
            )

        manifest = BuildManifest(
            template_release=plan.tag,
            contract_version=plan.contract.contract_version,
            files=tuple(entry.manifest_entry() for entry in staged),
        )
        _write_staged_file(staging, MANIFEST_FILENAME, manifest.serialize())
    except BaseException:
        discard_staging(staging)
        raise

    return StagingResult(
        plan=plan,
        staging=staging,
        outputs=tuple(staged),
        manifest=manifest,
        unmaterialized=unmaterialized,
    )


# ---------------------------------------------------------------------------
# Atomic swap: the only code here that touches the target
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SwapResult:
    """Outcome of a completed swap."""

    target: Path
    replaced: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "status": "swapped",
            "target": str(self.target),
            "replaced": self.replaced,
        }


def swap_into_place(
    staging: str | os.PathLike[str], target: str | os.PathLike[str]
) -> SwapResult:
    """Replace `target` with `staging` by directory rename (R4 AC8, R5 AC7).

    Call this **only after the Schema_Validator passes**; nothing here validates,
    and this is the one function in the module that writes outside staging.

    Sequence: move-old-aside, move-new-in, delete-old. Each step is a rename, so
    the target is either wholly its old self or wholly its new self and no partial
    content is ever visible at the target path. If the move-new-in fails, the old
    tree is renamed back, which is why the old tree is *moved* aside rather than
    deleted.

    The target's parent is created when absent (R14 AC4). Anything that stops the
    swap — a permission denial, a parent or target that is a file, a staging
    directory on a different filesystem than the target, so the sibling
    requirement was not met — is `E_WRITE_FAILED` with the target unchanged
    (R14 AC5).

    This call **owns the staging tree**: it succeeds by consuming it and fails by
    discarding it, so a failed swap leaves neither a mutated target nor staging
    residue.
    """
    staging_path = Path(staging)
    target_path = Path(target)

    if not staging_path.is_dir():
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"staging tree is absent, nothing to swap into place: {staging_path}",
            staging=str(staging_path),
            target=str(target_path),
        )
    try:
        return _swap(staging_path, target_path)
    except TransformError:
        discard_staging(staging_path)
        raise


def _swap(staging_path: Path, target_path: Path) -> SwapResult:
    """The swap proper, with the staging tree already known to exist."""
    parent = target_path.parent
    if parent.exists() and not parent.is_dir():
        raise TransformError(
            E_WRITE_FAILED,
            f"cannot create the target directory: its parent is not a directory: "
            f"{parent}",
            target=str(target_path),
        )
    if target_path.is_symlink() or (target_path.exists() and not target_path.is_dir()):
        raise TransformError(
            E_WRITE_FAILED,
            f"target exists and is not a directory, refusing to replace it: "
            f"{target_path}",
            target=str(target_path),
        )

    replaced = target_path.is_dir()
    aside_root: Path | None = None
    aside: Path | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        if replaced:
            aside_root = Path(
                tempfile.mkdtemp(prefix=f".{target_path.name}.replaced-", dir=parent)
            )
            aside = aside_root / target_path.name
            os.rename(target_path, aside)
        os.rename(staging_path, target_path)
    except OSError as error:
        if aside is not None and aside.exists() and not target_path.exists():
            os.rename(aside, target_path)
        if aside_root is not None:
            shutil.rmtree(aside_root, ignore_errors=True)
        raise TransformError(
            E_WRITE_FAILED,
            f"cannot replace {target_path} with the staged tree {staging_path}: "
            f"{error}",
            target=str(target_path),
            staging=str(staging_path),
        ) from error

    if aside_root is not None:
        shutil.rmtree(aside_root, ignore_errors=True)
    return SwapResult(target=target_path, replaced=replaced)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _narrate(message: str) -> None:
    """Human-readable narration goes to stderr; stdout carries only JSON."""
    print(f"transform: {message}", file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transform.py",
        description=(
            "Execute the Transformation_Contract over a resolved Template_Release "
            "tree. JSON to stdout, narration to stderr."
        ),
    )
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_CONTRACT),
        help="path to contract.yaml (default: the contract beside this script)",
    )
    parser.add_argument(
        "--source",
        required=True,
        help=(
            "resolved release tree containing the plugin root, or the plugin root "
            "itself"
        ),
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="resolved Template_Release tag, used character-for-character",
    )
    parser.add_argument(
        "--staging",
        required=True,
        help="staging directory; output is built here, never in the target",
    )
    parser.add_argument(
        "--carry-forward",
        default=None,
        help=(
            "existing Power directory whose kiro-owned content is carried forward "
            "(update path); omitted on the create path"
        ),
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help=(
            "match and report without writing anything, not even to staging "
            "(the matching stage alone)"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.tag.strip():
        json.dump(
            TransformError(
                E_TRANSFORM_FAILED, "--tag must be a non-empty release tag"
            ).to_json(),
            sys.stdout,
            indent=2,
            sort_keys=False,
        )
        print(file=sys.stdout)
        return 1

    try:
        contract = load_contract(args.contract)
        _narrate(
            f"contract {contract.path} (contractVersion {contract.contract_version}, "
            f"{len(contract.rules)} rules, {len(contract.ignore)} ignore patterns)"
        )

        plugin_root_path, nested = resolve_plugin_root(args.source, contract.plugin_root)
        _narrate(
            f"source plugin root {plugin_root_path}"
            + ("" if nested else " (--source taken as the plugin root itself)")
        )

        plan = build_plan(
            contract,
            args.source,
            tag=args.tag,
            staging=args.staging,
            carry_forward=args.carry_forward,
        )
        _narrate(
            f"{plan.enumerated_count} files enumerated: {len(plan.files)} matched by "
            f"rules ({len(plan.outputs)} producing output), {len(plan.ignored)} ignored"
        )
        _narrate(f"rules claiming content: {', '.join(plan.rule_ids()) or 'none'}")

        if args.plan_only:
            json.dump(plan.to_json(), sys.stdout, indent=2, sort_keys=False)
            print(file=sys.stdout)
            return 0

        _narrate(
            "kiro-owned content from "
            + (
                f"--carry-forward {plan.carry_forward}, then {KIRO_OWNED_ROOT} "
                "(update path)"
                if plan.carry_forward is not None
                else f"{KIRO_OWNED_ROOT} (create path)"
            )
        )
        result = write_staging(plan)
    except TransformError as error:
        _narrate(f"{error.code}: {error.message}")
        json.dump(error.to_json(), sys.stdout, indent=2, sort_keys=False)
        print(file=sys.stdout)
        return 1

    _narrate(
        f"{len(result.outputs)} files written to {result.staging}, "
        f"{MANIFEST_FILENAME} emitted for templateRelease {plan.tag}"
    )
    for gap in result.unmaterialized:
        _narrate(f"warning: no authored kiro-owned content for {gap}; nothing written")
    _narrate(
        "the target is untouched: replace it with swap_into_place() only after the "
        "Schema_Validator passes"
    )
    json.dump(result.to_json(), sys.stdout, indent=2, sort_keys=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
