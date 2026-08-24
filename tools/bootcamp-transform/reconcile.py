#!/usr/bin/env python3
"""Reconciler — three-way classification for the update path (R5).

    reconcile.py --power <existing-power-dir> --staging <fresh-staging-dir>
                 --to-release <semver> [--from-release <semver>]
                 [--manifest <path>] [--report <path.json>]
                 [--apply] [--changelog]

Three inputs, one verdict per path *(R5 AC4-AC6)*:

1. **previous** — the hashes recorded in the last successful build's
   `.build-manifest.json`. This is the only witness of what the engine
   *produced*, as opposed to what is on disk now.
2. **on-disk** — the current Power. Divergence from (1) means a human edited a
   generated file after the build.
3. **staging** — the tree the engine just transformed from the newer release.
   Divergence from (1) means upstream changed.

Comparing (2) and (3) against the same baseline (1) is what separates a local
adaptation from an upstream change, which a two-way diff cannot do: it sees one
difference and cannot say which side moved.

Classification is a pure function
---------------------------------
`classify` takes three data structures and returns one `Classification` per
path. It reads no filesystem, no clock, and no environment, so the property
test drives it entirely in memory and the CLI is a thin shell over it: read
three trees, classify, serialize. Every path in the union of the three inputs
lands in exactly one bucket, and the bucket is a total function of the three
hashes plus the recorded `owner` *(Property 20)*.

The design's classification table, verbatim in code order:

| prev vs on-disk | prev vs staging | bucket               | action       |
|-----------------|-----------------|----------------------|--------------|
| same            | same            | `unchanged`          | keep         |
| same            | differs         | `modified`           | take staging |
| differs         | same            | `preservedAdaptations` | keep on-disk |
| differs         | differs         | `conflicts`          | keep on-disk |
| absent from prev| present         | `added`              | take staging |
| present in prev | absent          | `removed`            | remove       |
| `owner` is kiro | n/a             | `preservedAdaptations` | keep on-disk |

Declared beats detected. A file the contract marks as Kiro-owned is a preserved
adaptation because it was *declared* one, whether or not its bytes moved; a
divergent `owner: template` file is preserved because divergence was *detected*.
The declared mechanism is authoritative, so it is tested first.

Rows the table leaves implicit
------------------------------
The table's two presence rows read on the assumption that presence and
divergence do not collide. They do, in four ways, and each resolves by the one
rule the design states without exception — **the reconciler never overwrites a
locally divergent file**, it preserves and reports:

* deleted locally, unchanged upstream → preserved (`local-delete-no-upstream-change`)
* deleted locally, changed upstream → conflict
* edited locally, dropped upstream → conflict (an upstream removal is an
  upstream change, so R5 AC6 applies rather than the plain `removed` row)
* present locally, absent from the manifest → preserved when upstream does not
  produce it (`local-only-no-template-source`), conflict when upstream produces
  it with different bytes

A conflict is never an error *(design error catalog)*. It retains the local
content, names both sides, and asks for a Maintainer's attention; it blocks
nothing. So this module has no failure exit for a conflict, only for an input it
cannot read.

`.build-manifest.json` itself is not classified: it records a build rather than
being part of one, it cannot record its own hash, and it is rewritten by every
build, so comparing it against itself is noise.

Classifying is advice; applying is what preserves
-------------------------------------------------
An `action` on a `Classification` is advice until something acts on it. The
update replaces the whole Power by directory rename *(R5 AC7)*, so a
`keep-on-disk` verdict that nobody materializes into the staging tree is a
preserved adaptation on paper and an overwritten one on disk. `apply_report`
closes that gap: it is the same shape as `classify` — data in, data out — and
turns one report plus the two trees into the **reconciled tree**, the exact
bytes the swap should publish *(R5 AC5, AC6)*:

| action         | reconciled bytes                                       |
|----------------|--------------------------------------------------------|
| `keep`         | on-disk (identical to staging by hash)                 |
| `take-staging` | staging                                                |
| `keep-on-disk` | on-disk — *including its absence*, so a local delete   |
|                | stays deleted                                          |
| `remove`       | absent                                                 |

`apply_to_staging` is the filesystem half: it edits the **staging** tree into
that shape and never touches the Power, so the atomic swap keeps its all-or-
nothing character and a failure part-way through leaves the Power byte-identical
*(R5 AC7)*. Applying twice changes nothing the first application did not already
do. Before returning, it re-reads what it wrote and checks the one rule this
module exists to keep: **no locally divergent file was overwritten**. A defect
there is `E_WRITE_FAILED`, because publishing a tree that lost an adaptation is
worse than not publishing at all.

The Build_Manifest is carried from staging **verbatim**, unclassified and
unedited, and this is deliberate. The manifest records what the engine
*produced*; rewriting it to describe the reconciled bytes would record a
preserved adaptation as engine output, and the next update would then see no
divergence and overwrite it. Carrying the engine's own hashes is what makes an
adaptation survive not just this update but every later one.

One comparison that is not about files
--------------------------------------
Reconciliation also answers a question no file hash can: is a recorded
*discount* still about the invariant it was written against? Each entry in the
contract's `invariantDiscounts` is a judgment about a specific Template_Invariant
text. When a newer release edits that text, the judgment is reopened rather than
carried forward, so the entry is flagged in `flaggedInvariantDiscounts` for
Maintainer re-evaluation *(R15 AC10)*. Flagging is a reported outcome, never an
error: identical text flags nothing, and a release pair that publishes no
invariant registry has nothing to compare, which is silence rather than failure.

Both texts are read from the **resolved release trees**, through
`resolve_release.read_invariant_text`, the only sanctioned reader — it is bounded
by the release tree and refuses any path that escapes it, so no invariant
definition can be sourced from the template's development repository *(R15 AC9)*.

Recording the update, without ever writing into the Power
---------------------------------------------------------
A successful update records itself in one `CHANGELOG.md` entry naming the
Template_Release it came from *(R5 AC8)*; a failed one records nothing and leaves
the Power unchanged *(R5 AC7)*. Both halves of that come from **where** the entry
is written, not from remembering to skip it: the entry is appended to the
**staged** `CHANGELOG.md`, which `apply_to_staging` has already seeded with the
Power's own changelog (the Power's `CHANGELOG.md` has no template source, so it
is a `local-only-no-template-source` preserved adaptation and is copied forward
verbatim). Nothing here touches the Power. The atomic swap publishes the entry
along with the rest of the tree, so any earlier failure discards staging and no
entry exists anywhere.

Ordering follows from that: reconcile, `apply_to_staging`, *then*
`record_update_in_staging`. Appending before applying would have the application
rewrite the staged changelog back to the Power's bytes — silently dropping the
entry — and would trip its preservation check besides.

Rendering is split from appending the same way classifying is split from
applying. `changelog_entry` is a pure function of one `ReconciliationReport` plus
two contract facts, so *Property 22* drives it in memory;
`append_changelog_entry` is a pure, strictly append-only text composition, so
"no other changelog content is altered" is a prefix relation rather than a
promise; and `record_update_in_staging` is the thin filesystem step that reads
the staged file, composes, and writes.

Scope
-----
This module owns the classification, the application of it, the invariant-text
drift comparison, the `ReconciliationReport` model, the changelog entry that
records a successful update, and the CLI. Deciding *whether* an update
succeeded — validation and the swap — belongs to the update orchestration.

Exit codes: 0 when reconciliation completed (with or without conflicts), 1 on a
fault reading an input, applying the result, or writing the report, 2 on CLI
misuse (argparse).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from resolve_release import read_invariant_text, release_tree_root
from transform import (
    DEFAULT_CONTRACT,
    E_TRANSFORM_FAILED,
    E_WRITE_FAILED,
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    OWNER_KIRO,
    OWNER_TEMPLATE,
    BuildManifest,
    ManifestEntry,
    TransformError,
    contained_path,
    enumerate_source,
    load_contract,
    sha256_hex,
)

__all__ = [
    # Buckets, reasons, actions.
    "BUCKETS",
    "BUCKET_ADDED",
    "BUCKET_CONFLICTS",
    "BUCKET_MODIFIED",
    "BUCKET_PRESERVED",
    "BUCKET_REMOVED",
    "BUCKET_UNCHANGED",
    "ACTION_KEEP",
    "ACTION_KEEP_ON_DISK",
    "ACTION_REMOVE",
    "ACTION_TAKE_STAGING",
    "ACTION_SOURCES",
    "SOURCE_ABSENT",
    "SOURCE_ON_DISK",
    "SOURCE_STAGING",
    "REASON_KIRO_OWNED",
    "REASON_LOCAL_DELETE",
    "REASON_LOCAL_EDIT",
    "REASON_LOCAL_ONLY",
    "CONFLICT_RESOLUTION",
    "UNCLASSIFIED_PATHS",
    # Inputs.
    "FileTree",
    "ManifestBaseline",
    # Report model.
    "Classification",
    "Conflict",
    "FlaggedDiscount",
    "PreservedAdaptation",
    "ReconciliationReport",
    "REPORT_VERSION",
    # Classification.
    "classify",
    "classify_path",
    "reconcile",
    "reconcile_directories",
    "union_paths",
    "write_report",
    # Invariant-text drift (R15 AC10).
    "DISCOUNT_REGISTER_KEY",
    "DRIFT_ACTION",
    "INVARIANT_REGISTRY_DIRECTORY",
    "INVARIANT_REGISTRY_FILENAME",
    "canonical_invariant_text",
    "contract_invariant_discounts",
    "discount_invariant_ids",
    "flag_invariant_drift",
    "flag_release_invariant_drift",
    "load_discount_register",
    "locate_invariant_registry",
    "normalize_invariant_id",
    "parse_invariant_registry",
    "read_release_invariants",
    # Application: making the verdict true.
    "Application",
    "FileResolution",
    "PreservationDefect",
    "apply_report",
    "apply_to_staging",
    "resolve_classification",
    # Changelog: recording a successful update (R5 AC7, AC8).
    "CHANGELOG_FILENAME",
    "CHANGELOG_TEMPLATE",
    "ChangelogRecord",
    "append_changelog_entry",
    "changelog_context",
    "changelog_entry",
    "changelog_provenance",
    "entry_recorded",
    "record_update_in_staging",
    "render_changelog_entry",
    # CLI.
    "build_parser",
    "main",
]


# ---------------------------------------------------------------------------
# Buckets, reasons, actions
# ---------------------------------------------------------------------------

#: The six buckets. Every classified path lands in exactly one (*Property 20*).
BUCKET_ADDED = "added"
BUCKET_MODIFIED = "modified"
BUCKET_REMOVED = "removed"
BUCKET_UNCHANGED = "unchanged"
BUCKET_PRESERVED = "preservedAdaptations"
BUCKET_CONFLICTS = "conflicts"

#: Report order, which is also the order the design's model lists them in.
BUCKETS: tuple[str, ...] = (
    BUCKET_ADDED,
    BUCKET_MODIFIED,
    BUCKET_REMOVED,
    BUCKET_UNCHANGED,
    BUCKET_PRESERVED,
    BUCKET_CONFLICTS,
)

#: What the update does with the file. `keep` and `keep-on-disk` differ in
#: intent, not in effect: `keep` means nothing moved, `keep-on-disk` means
#: something moved and the local side won.
ACTION_KEEP = "keep"
ACTION_TAKE_STAGING = "take-staging"
ACTION_KEEP_ON_DISK = "keep-on-disk"
ACTION_REMOVE = "remove"

#: Which tree an action's reconciled bytes come from. This table is the whole
#: of the application step's policy, which is why it is a table: the actions are
#: a closed set, so an action with no source here is a bug rather than a default.
SOURCE_ON_DISK = "on-disk"
SOURCE_STAGING = "staging"
SOURCE_ABSENT = "absent"

ACTION_SOURCES: Mapping[str, str] = {
    ACTION_KEEP: SOURCE_ON_DISK,
    ACTION_TAKE_STAGING: SOURCE_STAGING,
    ACTION_KEEP_ON_DISK: SOURCE_ON_DISK,
    ACTION_REMOVE: SOURCE_ABSENT,
}

#: Why a path is a preserved adaptation. The first two are the design's own
#: spellings; the second two name the presence/divergence collisions the
#: classification table leaves implicit.
REASON_KIRO_OWNED = "kiro-owned"
REASON_LOCAL_EDIT = "local-edit-no-upstream-change"
REASON_LOCAL_ONLY = "local-only-no-template-source"
REASON_LOCAL_DELETE = "local-delete-no-upstream-change"

#: Every conflict resolves the same way, because the rule admits no exception:
#: the local content stays and the Maintainer decides *(R5 AC6)*.
CONFLICT_RESOLUTION = "local version retained; maintainer action required"

#: Paths that take no part in reconciliation. The Build_Manifest records a
#: build; it is not part of one, and it cannot record its own hash.
UNCLASSIFIED_PATHS: frozenset[str] = frozenset({MANIFEST_FILENAME})

#: `ReconciliationReport` shape version. Bump only on an incompatible change.
REPORT_VERSION = 1


# ---------------------------------------------------------------------------
# Inputs: two file trees and one manifest baseline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileTree:
    """A tree of files as data: POSIX relative path → bytes.

    Declared here rather than reusing the Schema_Validator's `PowerTree` so the
    Reconciler does not depend on the validator: they are siblings in the
    pipeline, and a reconciliation is not a validation. Directory enumeration is
    still delegated to the transform engine, so path spelling — POSIX,
    relative, sorted — stays defined in exactly one place.

    Nothing here writes. `from_mapping` is what a property test builds, and both
    constructors produce the same thing, so classification has one code path.
    """

    files: Mapping[str, bytes]

    @classmethod
    def from_directory(cls, root: str | Path) -> FileTree:
        """Read every file under `root`, sorted.

        An unreadable file is a halting fault rather than an absence: treating
        it as absent would classify it as `removed` and quietly propose
        deleting content nobody looked at.
        """
        contents: dict[str, bytes] = {}
        for entry in enumerate_source(Path(root), ""):
            try:
                contents[entry.path] = entry.absolute.read_bytes()
            except OSError as error:
                raise TransformError(
                    E_TRANSFORM_FAILED,
                    f"cannot read {entry.path} under {root}: {error}",
                    path=entry.path,
                    root=str(root),
                ) from error
        return cls(files=contents)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | bytes]) -> FileTree:
        """Build a tree from in-memory content, encoding text as UTF-8."""
        return cls(
            files={
                path: value.encode("utf-8") if isinstance(value, str) else value
                for path, value in mapping.items()
            }
        )

    @classmethod
    def empty(cls) -> FileTree:
        return cls(files={})

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(sorted(self.files))

    def __contains__(self, path: str) -> bool:
        return path in self.files

    def __len__(self) -> int:
        return len(self.files)

    def read_bytes(self, path: str) -> bytes | None:
        return self.files.get(path)

    def sha256(self, path: str) -> str | None:
        """The hash of `path`'s bytes, or `None` when the path is absent.

        `None` is the absence marker throughout this module: it is what makes
        the presence rows and the divergence rows of the classification table
        one expression instead of two.
        """
        data = self.files.get(path)
        return None if data is None else sha256_hex(data)

    def hashes(self) -> dict[str, str]:
        return {path: sha256_hex(data) for path, data in sorted(self.files.items())}


@dataclass(frozen=True)
class ManifestBaseline:
    """The previous build's state, read from `.build-manifest.json`.

    Two things are wanted from the manifest and nothing else: the hash of each
    file **as written**, which is the baseline both other trees are compared
    against, and its `owner`, which is the declared-adaptation mechanism
    *(R5 AC5)*. Entries are keyed by output path and reuse the engine's
    `ManifestEntry`, so the manifest's shape is defined once.
    """

    entries: Mapping[str, ManifestEntry]
    template_release: str | None = None
    contract_version: int | None = None
    manifest_version: int = MANIFEST_VERSION

    @classmethod
    def empty(cls) -> ManifestBaseline:
        """No previous build: every on-disk file is untracked by construction."""
        return cls(entries={})

    @classmethod
    def from_json(cls, document: Any) -> ManifestBaseline:
        """Parse a `.build-manifest.json` document.

        Structural faults halt rather than degrade. A manifest that parses
        loosely would silently shrink the baseline, and a shrunken baseline
        misreads generated files as local adaptations — the exact confusion this
        module exists to remove.
        """
        if not isinstance(document, Mapping):
            raise TransformError(
                E_TRANSFORM_FAILED,
                f"{MANIFEST_FILENAME} is not a JSON object",
            )

        raw_files = document.get("files")
        if not isinstance(raw_files, Sequence) or isinstance(raw_files, (str, bytes)):
            raise TransformError(
                E_TRANSFORM_FAILED,
                f"{MANIFEST_FILENAME} declares no 'files' list",
            )

        entries: dict[str, ManifestEntry] = {}
        for index, raw in enumerate(raw_files):
            entry = _parse_manifest_entry(raw, index=index)
            if entry.path in entries:
                raise TransformError(
                    E_TRANSFORM_FAILED,
                    f"{MANIFEST_FILENAME} records '{entry.path}' twice; a path has "
                    "one recorded hash or the baseline is ambiguous",
                    path=entry.path,
                )
            entries[entry.path] = entry

        release = document.get("templateRelease")
        contract_version = document.get("contractVersion")
        return cls(
            entries=entries,
            template_release=release if isinstance(release, str) else None,
            contract_version=(
                contract_version if isinstance(contract_version, int) else None
            ),
            manifest_version=int(document.get("manifestVersion", MANIFEST_VERSION)),
        )

    @classmethod
    def from_manifest(cls, manifest: BuildManifest) -> ManifestBaseline:
        """Take the baseline straight from an in-process `BuildManifest`."""
        return cls.from_json(manifest.to_json())

    @classmethod
    def from_file(cls, path: str | Path) -> ManifestBaseline:
        target = Path(path)
        try:
            text = target.read_text(encoding="utf-8")
        except OSError as error:
            raise TransformError(
                E_TRANSFORM_FAILED,
                f"cannot read the previous build manifest {target}: {error}",
                path=str(target),
            ) from error
        try:
            document = json.loads(text)
        except json.JSONDecodeError as error:
            raise TransformError(
                E_TRANSFORM_FAILED,
                f"previous build manifest {target} is not valid JSON: {error}",
                path=str(target),
            ) from error
        return cls.from_json(document)

    @classmethod
    def from_directory(cls, power_root: str | Path) -> ManifestBaseline:
        """Read the manifest at the root of an existing Power."""
        return cls.from_file(Path(power_root) / MANIFEST_FILENAME)

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(sorted(self.entries))

    def __contains__(self, path: str) -> bool:
        return path in self.entries

    def __len__(self) -> int:
        return len(self.entries)

    def sha256(self, path: str) -> str | None:
        entry = self.entries.get(path)
        return None if entry is None else entry.sha256

    def owner(self, path: str) -> str | None:
        """The recorded owner, or `None` when the last build did not write it."""
        entry = self.entries.get(path)
        return None if entry is None else entry.owner

    def rule_id(self, path: str) -> str | None:
        entry = self.entries.get(path)
        return None if entry is None else entry.rule_id


def _parse_manifest_entry(raw: Any, *, index: int) -> ManifestEntry:
    if not isinstance(raw, Mapping):
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"{MANIFEST_FILENAME} files[{index}] is not an object",
        )

    path = raw.get("path")
    if not isinstance(path, str) or not path.strip():
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"{MANIFEST_FILENAME} files[{index}] has no 'path'",
        )

    digest = raw.get("sha256")
    if not isinstance(digest, str) or not digest.strip():
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"{MANIFEST_FILENAME} records no 'sha256' for '{path}'; without it "
            "there is no baseline to compare against",
            path=path,
        )

    owner = raw.get("owner", OWNER_TEMPLATE)
    if owner not in (OWNER_TEMPLATE, OWNER_KIRO):
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"{MANIFEST_FILENAME} records owner {owner!r} for '{path}'; expected "
            f"'{OWNER_TEMPLATE}' or '{OWNER_KIRO}'",
            path=path,
        )

    rule_id = raw.get("ruleId")
    source_path = raw.get("sourcePath")
    return ManifestEntry(
        path=path,
        rule_id=rule_id if isinstance(rule_id, str) else "",
        owner=owner,
        source_path=source_path if isinstance(source_path, str) else None,
        sha256=digest,
    )


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Classification:
    """One path's verdict, and the evidence it was reached from.

    The three hashes are carried rather than discarded so a report consumer can
    see *why* a path landed where it did without re-deriving it, and so a
    property test can check the verdict against the same evidence the classifier
    saw. `reason` is set for preserved adaptations, `conflict` for conflicts,
    and neither for the other four buckets.
    """

    path: str
    bucket: str
    action: str
    previous_sha256: str | None = None
    on_disk_sha256: str | None = None
    staging_sha256: str | None = None
    owner: str | None = None
    reason: str | None = None
    conflict: Conflict | None = None

    @property
    def locally_divergent(self) -> bool:
        """Whether the on-disk file differs from what the last build wrote.

        Absence counts as divergence: a file deleted after the build diverges
        from the build as surely as an edited one.
        """
        return self.previous_sha256 != self.on_disk_sha256

    @property
    def upstream_changed(self) -> bool:
        """Whether the new transform differs from what the last build wrote."""
        return self.previous_sha256 != self.staging_sha256

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "bucket": self.bucket,
            "action": self.action,
            "owner": self.owner,
            "previousSha256": self.previous_sha256,
            "onDiskSha256": self.on_disk_sha256,
            "stagingSha256": self.staging_sha256,
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class PreservedAdaptation:
    """One Kiro-specific adaptation left unchanged by the update *(R5 AC5)*."""

    path: str
    reason: str

    def to_json(self) -> dict[str, Any]:
        return {"path": self.path, "reason": self.reason}


@dataclass(frozen=True)
class Conflict:
    """A retained adaptation and the template change it collides with.

    R5 AC6 asks for *both* sides by name, so both are fields: `adaptation`
    describes what is being kept and `template_change` what is being declined.
    `resolution` is fixed, because the outcome never varies.
    """

    path: str
    adaptation: str
    template_change: str
    resolution: str = CONFLICT_RESOLUTION

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "adaptation": self.adaptation,
            "templateChange": self.template_change,
            "resolution": self.resolution,
        }


@dataclass(frozen=True)
class FlaggedDiscount:
    """An `Invariant_Discount_Register` entry reopened by upstream text drift.

    `invariant` names the entry, `reason` says what moved, and `action` says what
    the Maintainer owes it. Produced by `flag_invariant_drift` *(R15 AC10)*; a
    flag asks for re-evaluation and blocks nothing.
    """

    invariant: str
    reason: str
    action: str

    def to_json(self) -> dict[str, Any]:
        return {
            "invariant": self.invariant,
            "reason": self.reason,
            "action": self.action,
        }


@dataclass(frozen=True)
class ReconciliationReport:
    """What the Update_Skill presents to the Maintainer *(R5 AC4)*.

    The buckets are **derived** from `classifications`, never assigned: one
    classification per path, one bucket per classification, so "every path
    appears in exactly one bucket" holds by construction rather than by
    convention (*Property 20*). Every list is sorted by path, and nothing here
    reads the clock, so two runs over identical input serialize identically.
    """

    to_release: str
    from_release: str | None = None
    classifications: tuple[Classification, ...] = ()
    flagged_invariant_discounts: tuple[FlaggedDiscount, ...] = ()
    report_version: int = REPORT_VERSION

    def in_bucket(self, bucket: str) -> tuple[Classification, ...]:
        return tuple(
            entry
            for entry in sorted(self.classifications, key=lambda item: item.path)
            if entry.bucket == bucket
        )

    def paths_in(self, bucket: str) -> tuple[str, ...]:
        return tuple(entry.path for entry in self.in_bucket(bucket))

    def bucket_of(self, path: str) -> str | None:
        for entry in self.classifications:
            if entry.path == path:
                return entry.bucket
        return None

    def buckets(self) -> dict[str, tuple[str, ...]]:
        """Every bucket's paths, including the empty ones, in report order."""
        return {bucket: self.paths_in(bucket) for bucket in BUCKETS}

    @property
    def added(self) -> tuple[str, ...]:
        return self.paths_in(BUCKET_ADDED)

    @property
    def modified(self) -> tuple[str, ...]:
        return self.paths_in(BUCKET_MODIFIED)

    @property
    def removed(self) -> tuple[str, ...]:
        return self.paths_in(BUCKET_REMOVED)

    @property
    def unchanged(self) -> tuple[str, ...]:
        return self.paths_in(BUCKET_UNCHANGED)

    @property
    def preserved_adaptations(self) -> tuple[PreservedAdaptation, ...]:
        return tuple(
            PreservedAdaptation(path=entry.path, reason=entry.reason or "")
            for entry in self.in_bucket(BUCKET_PRESERVED)
        )

    @property
    def conflicts(self) -> tuple[Conflict, ...]:
        return tuple(
            entry.conflict
            for entry in self.in_bucket(BUCKET_CONFLICTS)
            if entry.conflict is not None
        )

    def to_json(self) -> dict[str, Any]:
        """The design's `ReconciliationReport` document.

        `unchanged` is carried alongside the design's listed fields: the
        classification is total over the union of the three inputs, so the
        bucket that means "nothing to do" has to be nameable too, or the report
        could not be read as a partition (*Property 20*).
        """
        return {
            "reportVersion": self.report_version,
            "fromRelease": self.from_release,
            "toRelease": self.to_release,
            "added": list(self.added),
            "modified": list(self.modified),
            "removed": list(self.removed),
            "unchanged": list(self.unchanged),
            "preservedAdaptations": [
                item.to_json() for item in self.preserved_adaptations
            ],
            "conflicts": [item.to_json() for item in self.conflicts],
            "flaggedInvariantDiscounts": [
                item.to_json() for item in self.flagged_invariant_discounts
            ],
        }

    def serialize(self) -> bytes:
        return (
            json.dumps(self.to_json(), indent=2, sort_keys=False, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")

    def summary(self) -> str:
        """One narration line: the counts a Maintainer reads first."""
        counts = ", ".join(
            f"{len(paths)} {bucket}" for bucket, paths in self.buckets().items()
        )
        return (
            f"{len(self.classifications)} path(s) classified: {counts}; "
            f"{len(self.flagged_invariant_discounts)} flagged discount(s)"
        )


# ---------------------------------------------------------------------------
# Invariant-text drift: reopening a discount whose subject moved (R15 AC10)
# ---------------------------------------------------------------------------
#
# A discount is a judgment about one Template_Invariant's text: *this* wording
# conflicts with *that* Kiro mechanism, so *this* construction is implemented
# instead. Change the wording and the judgment no longer has a subject. The
# register is therefore reviewed rather than merely carried: an entry whose
# invariant text moved between the two releases is flagged for Maintainer
# re-evaluation.
#
# The comparison is split so the reading and the deciding are separable:
# `read_release_invariants` is the only part that touches a filesystem, and
# `flag_invariant_drift` is a pure function of three data structures — the
# register, and one invariant-text mapping per release — so unit tests drive it
# in memory.
#
# What is deliberately *not* flagged:
#
# * identical text — a discount still about its subject needs no attention;
# * a release pair where either side publishes no invariant registry — release
#   0.5.1 ships none, the contract's `ignore` list carries defensive patterns
#   for whichever location a later release chooses, and nothing to compare is
#   silence rather than an error;
# * an invariant no registry on either side defines — again nothing to compare;
# * an incomplete register entry — a missing `invariant`, `conflictsWith`, or
#   `resolution` is the Schema_Validator's `E_INCOMPLETE_DISCOUNT` *(R15 AC5)*,
#   and reporting it here as drift would ask for the wrong response.


#: The register, and the one field of an entry this comparison reads, as
#: `contract.yaml` spells them *(R15 AC4)*. The other two fields —
#: `conflictsWith` and `resolution` — are the Maintainer's record of the
#: judgment; drift is about the invariant the entry names, so only that is read.
DISCOUNT_REGISTER_KEY = "invariantDiscounts"
DISCOUNT_INVARIANT_FIELD = "invariant"

#: Where a Template_Release may keep its invariant registry. These mirror the
#: contract's defensive `ignore` patterns — `INVARIANTS.md` at any depth, and
#: anything under a directory named `invariants` — so the registry is found in
#: whichever location a later release picks, and its absence is not an error.
INVARIANT_REGISTRY_FILENAME = "INVARIANTS.md"
INVARIANT_REGISTRY_DIRECTORY = "invariants"

#: A Template_Invariant identifier. The digit count is not fixed: `INV-52` and
#: `INV-052` are different identifiers, and both are citable.
_INVARIANT_ID = re.compile(r"INV-[0-9]+", re.IGNORECASE)

#: Markup that may carry an identifier at the head of a registry entry: an ATX
#: heading, a list bullet, a block quote, a table cell, a bold run, code ticks.
_ENTRY_LEAD = re.compile(r"^[\s#*+\->|`]*")

#: What a flag asks of the Maintainer. Fixed, because the response never varies:
#: the recorded resolution is re-read against the new text and either restated
#: or withdrawn. Nothing is decided here.
DRIFT_ACTION = (
    "maintainer re-evaluation required; the recorded resolution may no longer "
    "apply"
)

#: How a release is named in a reason when no tag was supplied.
_PREVIOUS_RELEASE_LABEL = "the previously resolved release"
_NEW_RELEASE_LABEL = "the newly resolved release"


def _release_label(release: str | None, fallback: str) -> str:
    return (
        release.strip()
        if isinstance(release, str) and release.strip()
        else fallback
    )


def normalize_invariant_id(identifier: Any) -> str:
    """One spelling of a Template_Invariant identifier: trimmed and upper case.

    `inv-052`, `INV-052 `, and `INV-052` are the same invariant under three
    spellings; `INV-52` is a different invariant that reads like it, and stays
    different here.
    """
    return identifier.strip().upper() if isinstance(identifier, str) else ""


def canonical_invariant_text(text: str) -> str:
    """One spelling of an invariant's text, so a repack is not read as an edit.

    Line endings are normalized to LF, trailing whitespace is dropped per line,
    and surrounding blank lines are stripped. Everything else — wording, order,
    punctuation, internal blank lines — is compared verbatim, because an edit to
    any of it is an edit to what the discount judged.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def contract_invariant_discounts(contract: Any) -> tuple[Mapping[str, Any], ...]:
    """The `Invariant_Discount_Register` entries, in register order.

    Accepts a `Contract` (reading its `raw` document), a raw contract document,
    or the register list itself, so a caller holding any of the three does not
    unwrap it first — and the transform engine's `Contract` needs no new field.
    A malformed or absent register reads as empty: its completeness is the
    Schema_Validator's gate *(R15 AC5)*, not this comparison's.
    """
    document: Any = getattr(contract, "raw", None)
    if document is None:
        document = contract
    register = (
        document.get(DISCOUNT_REGISTER_KEY, ())
        if isinstance(document, Mapping)
        else document
    )
    if register is None:
        return ()
    if isinstance(register, (str, bytes)) or not isinstance(register, Sequence):
        return ()
    return tuple(
        entry if isinstance(entry, Mapping) else {DISCOUNT_INVARIANT_FIELD: entry}
        for entry in register
        if isinstance(entry, (Mapping, str))
    )


def load_discount_register(
    contract: Any = None,
) -> tuple[Mapping[str, Any], ...]:
    """The register, from whatever the caller has: nothing, a path, or a document.

    `None` means the contract beside the engine, which is where the register
    lives so that create and update apply an identical discount set
    *(R15 AC11)*; a path means that contract file; anything else is taken as
    given by `contract_invariant_discounts`.
    """
    if contract is None:
        return contract_invariant_discounts(load_contract(DEFAULT_CONTRACT))
    if isinstance(contract, (str, os.PathLike)):
        return contract_invariant_discounts(load_contract(contract))
    return contract_invariant_discounts(contract)


def discount_invariant_ids(discounts: Iterable[Any]) -> tuple[str, ...]:
    """The invariant each register entry cites, normalized, in register order.

    Duplicates collapse — an invariant is compared once however many entries
    name it — and an entry citing nothing is skipped rather than flagged.
    """
    ids: list[str] = []
    for entry in discounts:
        raw = (
            entry.get(DISCOUNT_INVARIANT_FIELD)
            if isinstance(entry, Mapping)
            else entry
        )
        identifier = normalize_invariant_id(raw)
        if identifier and identifier not in ids:
            ids.append(identifier)
    return tuple(ids)


def _entry_id(line: str) -> str | None:
    """The identifier this line opens a registry entry for, if it opens one.

    An entry opens where an identifier is the line's first token, whatever
    markup carries it. A citation *inside* a sentence opens nothing, so prose
    that mentions an invariant is not mistaken for its definition.
    """
    match = _INVARIANT_ID.match(_ENTRY_LEAD.sub("", line))
    return None if match is None else normalize_invariant_id(match.group(0))


def parse_invariant_registry(
    text: str, *, default_id: Any = None
) -> dict[str, str]:
    """Split a registry document into invariant id → text. Pure.

    An entry runs from the line that opens it to the line before the next one
    opens; prose before the first entry is preamble and belongs to no
    invariant. Two entries for one identifier concatenate, so an edit to either
    occurrence is visible as drift.

    `default_id` names the invariant a one-per-file registry entry is about — an
    `invariants/INV-052.md` — and is used only when the body opens no entry of
    its own, so a bare definition file is still readable.
    """
    body = canonical_invariant_text(text)
    entries: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.split("\n"):
        opened = _entry_id(line)
        if opened is not None:
            current = opened
            entries.setdefault(current, [])
        if current is not None:
            entries[current].append(line)

    if not entries:
        identifier = normalize_invariant_id(default_id)
        return {identifier: body} if identifier and body else {}
    return {
        identifier: canonical_invariant_text("\n".join(lines))
        for identifier, lines in entries.items()
    }


def locate_invariant_registry(root: str | Path) -> tuple[str, ...]:
    """Every invariant registry file in a release tree, as relative POSIX paths.

    Release 0.5.1 ships none, and that is not an error: an absent registry is an
    empty tuple, and a comparison with nothing to compare flags nothing. Symlinks
    are not followed, in or out: the release tree bounds what may be read
    *(R15 AC9)*.
    """
    base = Path(root)
    if not base.is_dir():
        return ()
    found: set[str] = set()
    for candidate in base.rglob("*"):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        relative = candidate.relative_to(base)
        in_registry_directory = INVARIANT_REGISTRY_DIRECTORY in relative.parts[:-1]
        if candidate.name == INVARIANT_REGISTRY_FILENAME or in_registry_directory:
            found.add(relative.as_posix())
    return tuple(sorted(found))


def _resolved_record(release: Any) -> Mapping[str, Any]:
    """A resolved-release record, from the record itself or a tree path.

    Both forms end at the same reader, so a caller with only an extracted tree
    is bounded by exactly the same containment rule as one holding the full
    resolution record.
    """
    if isinstance(release, Mapping):
        return release
    return {"extractedTo": str(release)}


def read_release_invariants(release: Any) -> dict[str, str]:
    """Every Template_Invariant text a resolved release defines, keyed by id.

    `release` is a resolved-release record (as `resolve_release.resolve`
    returns) or the path of an extracted release tree. Text is read through
    `resolve_release.read_invariant_text`, the only sanctioned reader: bounded by
    the release tree, refusing any path that escapes it, so no definition can be
    sourced from the template's development repository *(R15 AC9)*.

    An unreadable or non-text file in a registry location defines nothing and is
    skipped: declining to reconcile over a binary asset that no discount cites
    would block an update for a file that says nothing about any invariant.
    """
    record = _resolved_record(release)
    texts: dict[str, str] = {}
    for relative in locate_invariant_registry(release_tree_root(record)):
        try:
            document = read_invariant_text(record, relative)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        stem_match = _INVARIANT_ID.search(Path(relative).stem)
        parsed = parse_invariant_registry(
            document,
            default_id=None if stem_match is None else stem_match.group(0),
        )
        for identifier, text in parsed.items():
            existing = texts.get(identifier)
            texts[identifier] = (
                text
                if existing is None
                else canonical_invariant_text(f"{existing}\n{text}")
            )
    return texts


def _drift_reason(
    previous: str | None,
    new: str | None,
    *,
    from_label: str,
    to_label: str,
) -> str | None:
    """Why this invariant's text reopens its discount, or `None` when it does not.

    Absence on one side counts as drift only when the other side defines the
    text: an invariant that appeared or disappeared between the two releases is
    as much a change to what the discount judged as a reworded one. Absence on
    both sides is nothing to compare.
    """
    if previous is None and new is None:
        return None
    if previous is None:
        return (
            f"text absent from the invariant registry of {from_label} is "
            f"defined in {to_label}"
        )
    if new is None:
        return (
            f"text present in {from_label} is absent from the invariant "
            f"registry of {to_label}"
        )
    if previous == new:
        return None
    return f"text changed between {from_label} and {to_label}"


def flag_invariant_drift(
    discounts: Iterable[Any],
    previous_invariants: Mapping[str, str],
    new_invariants: Mapping[str, str],
    *,
    from_release: str | None = None,
    to_release: str | None = None,
) -> tuple[FlaggedDiscount, ...]:
    """Flag every discount whose invariant text moved between two releases.

    Pure: three data structures in, one tuple of `FlaggedDiscount` out, ordered
    by invariant identifier so two runs over the same input serialize
    identically. Reads no filesystem, no clock, no environment.

    Either mapping being empty means that release publishes no invariant
    registry, so no text is comparable and nothing is flagged — the release-0.5.1
    case, and silence rather than an error.
    """
    if not previous_invariants or not new_invariants:
        return ()

    from_label = _release_label(from_release, _PREVIOUS_RELEASE_LABEL)
    to_label = _release_label(to_release, _NEW_RELEASE_LABEL)

    previous = {
        normalize_invariant_id(key): canonical_invariant_text(value)
        for key, value in previous_invariants.items()
    }
    new = {
        normalize_invariant_id(key): canonical_invariant_text(value)
        for key, value in new_invariants.items()
    }

    flagged: list[FlaggedDiscount] = []
    for identifier in discount_invariant_ids(discounts):
        reason = _drift_reason(
            previous.get(identifier),
            new.get(identifier),
            from_label=from_label,
            to_label=to_label,
        )
        if reason is not None:
            flagged.append(
                FlaggedDiscount(
                    invariant=identifier, reason=reason, action=DRIFT_ACTION
                )
            )
    return tuple(sorted(flagged, key=lambda item: item.invariant))


def flag_release_invariant_drift(
    discounts: Iterable[Any],
    from_release_tree: Any,
    to_release_tree: Any,
    *,
    from_release: str | None = None,
    to_release: str | None = None,
) -> tuple[FlaggedDiscount, ...]:
    """Read both release trees, then compare *(R15 AC9, AC10)*.

    The filesystem half of the drift comparison: it locates and reads, and
    `flag_invariant_drift` decides. Both trees are resolved releases; neither is
    the template's development repository.
    """
    return flag_invariant_drift(
        discounts,
        read_release_invariants(from_release_tree),
        read_release_invariants(to_release_tree),
        from_release=from_release,
        to_release=to_release,
    )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
#
# One function per row group of the design's table, all reached from
# `classify_path`, which is a total function of (previous hash, owner, on-disk
# hash, staging hash). `None` means absent, so the presence rows and the
# divergence rows share one expression.


def _conflict(path: str, adaptation: str, template_change: str) -> Conflict:
    return Conflict(
        path=path, adaptation=adaptation, template_change=template_change
    )


#: How much of a hash to quote. R5 AC6 asks the report to *identify* both sides,
#: and a Maintainer identifies a version by a prefix, then greps for it; a full
#: 64-hex digest in prose is identification nobody reads.
_DIGEST_PREFIX = 12


def _short(digest: str | None) -> str:
    """Name a version of a file: a hash prefix, or the fact of its absence."""
    return "absent" if digest is None else digest[:_DIGEST_PREFIX]


# Both sides of a conflict, named concretely *(R5 AC6)*. Each description says
# which file, which two versions of it, and which side moved — so the record
# stands on its own in the report, without the reader holding the hash columns
# in their head. The wording is fixed and derived only from the hashes, so two
# runs over the same input produce the same bytes.


def _local_edit(path: str, on_disk: str | None, previous: str | None) -> str:
    return (
        f"local edit to a generated file: on-disk content of '{path}' is "
        f"{_short(on_disk)}, which differs from {_short(previous)}, the hash the "
        "last build recorded for it"
    )


def _local_delete(path: str, previous: str | None) -> str:
    return (
        f"file deleted locally after the last successful build, which recorded "
        f"'{path}' as {_short(previous)}"
    )


def _local_untracked(path: str, on_disk: str | None) -> str:
    return (
        f"file present in the Power as '{path}' at {_short(on_disk)} but absent "
        "from the last build manifest, so it was not produced by the engine"
    )


def _upstream_change(path: str, staging: str | None, previous: str | None) -> str:
    return (
        f"the newer Template_Release transforms this file to different content: "
        f"'{path}' becomes {_short(staging)}, where the last build recorded "
        f"{_short(previous)}"
    )


def _upstream_removal(path: str, previous: str | None) -> str:
    return (
        f"the newer Template_Release no longer produces this file: '{path}' was "
        f"{_short(previous)} at the last build and is absent from the new transform"
    )


def _upstream_introduces(path: str, staging: str | None, on_disk: str | None) -> str:
    return (
        f"the newer Template_Release produces this path with different content: "
        f"'{path}' transforms to {_short(staging)} against the on-disk "
        f"{_short(on_disk)}"
    )


def classify_path(
    path: str,
    *,
    previous_sha256: str | None,
    on_disk_sha256: str | None,
    staging_sha256: str | None,
    owner: str | None = None,
) -> Classification:
    """Classify one path into exactly one bucket.

    Pure: three hashes and an owner in, one `Classification` out. Every branch
    below assigns a bucket and returns, so there is no path through this
    function that produces two verdicts or none.
    """
    common: dict[str, Any] = {
        "path": path,
        "previous_sha256": previous_sha256,
        "on_disk_sha256": on_disk_sha256,
        "staging_sha256": staging_sha256,
        "owner": owner,
    }

    # Declared adaptation. Authoritative and checked first: a `kiro-owned` file
    # is preserved because the contract says so, whatever its bytes did.
    if owner == OWNER_KIRO:
        if on_disk_sha256 is not None:
            return Classification(
                bucket=BUCKET_PRESERVED,
                action=ACTION_KEEP_ON_DISK,
                reason=REASON_KIRO_OWNED,
                **common,
            )
        # Declared, but not present to preserve: the authored content is being
        # materialized (added) or its rule is gone (removed).
        if staging_sha256 is not None:
            return Classification(
                bucket=BUCKET_ADDED, action=ACTION_TAKE_STAGING, **common
            )
        return Classification(bucket=BUCKET_REMOVED, action=ACTION_REMOVE, **common)

    # Untracked by the last build: there is no baseline, so nothing can be said
    # about which side moved — only about what exists.
    if previous_sha256 is None:
        if on_disk_sha256 is None:
            return Classification(
                bucket=BUCKET_ADDED, action=ACTION_TAKE_STAGING, **common
            )
        if staging_sha256 is None:
            return Classification(
                bucket=BUCKET_PRESERVED,
                action=ACTION_KEEP_ON_DISK,
                reason=REASON_LOCAL_ONLY,
                **common,
            )
        if staging_sha256 == on_disk_sha256:
            return Classification(
                bucket=BUCKET_ADDED, action=ACTION_TAKE_STAGING, **common
            )
        return Classification(
            bucket=BUCKET_CONFLICTS,
            action=ACTION_KEEP_ON_DISK,
            conflict=_conflict(
                path,
                _local_untracked(path, on_disk_sha256),
                _upstream_introduces(path, staging_sha256, on_disk_sha256),
            ),
            **common,
        )

    locally_divergent = on_disk_sha256 != previous_sha256
    upstream_changed = staging_sha256 != previous_sha256

    # Dropped upstream. A local edit makes the removal a collision, not a
    # removal: an upstream change that happens to be a deletion still meets a
    # retained adaptation, which is R5 AC6.
    if staging_sha256 is None:
        if not locally_divergent or on_disk_sha256 is None:
            return Classification(
                bucket=BUCKET_REMOVED, action=ACTION_REMOVE, **common
            )
        return Classification(
            bucket=BUCKET_CONFLICTS,
            action=ACTION_KEEP_ON_DISK,
            conflict=_conflict(
                path,
                _local_edit(path, on_disk_sha256, previous_sha256),
                _upstream_removal(path, previous_sha256),
            ),
            **common,
        )

    # Deleted locally, still produced upstream. The deletion is the local
    # divergence, so the same two rows apply as for an edit.
    if on_disk_sha256 is None:
        if upstream_changed:
            return Classification(
                bucket=BUCKET_CONFLICTS,
                action=ACTION_KEEP_ON_DISK,
                conflict=_conflict(
                    path,
                    _local_delete(path, previous_sha256),
                    _upstream_change(path, staging_sha256, previous_sha256),
                ),
                **common,
            )
        return Classification(
            bucket=BUCKET_PRESERVED,
            action=ACTION_KEEP_ON_DISK,
            reason=REASON_LOCAL_DELETE,
            **common,
        )

    # The table's four divergence rows.
    if not locally_divergent and not upstream_changed:
        return Classification(bucket=BUCKET_UNCHANGED, action=ACTION_KEEP, **common)
    if not locally_divergent:
        return Classification(
            bucket=BUCKET_MODIFIED, action=ACTION_TAKE_STAGING, **common
        )
    if not upstream_changed:
        return Classification(
            bucket=BUCKET_PRESERVED,
            action=ACTION_KEEP_ON_DISK,
            reason=REASON_LOCAL_EDIT,
            **common,
        )
    return Classification(
        bucket=BUCKET_CONFLICTS,
        action=ACTION_KEEP_ON_DISK,
        conflict=_conflict(
            path,
            _local_edit(path, on_disk_sha256, previous_sha256),
            _upstream_change(path, staging_sha256, previous_sha256),
        ),
        **common,
    )


def union_paths(
    previous: ManifestBaseline,
    on_disk: FileTree,
    staging: FileTree,
) -> tuple[str, ...]:
    """Every path any of the three inputs knows about, sorted.

    This is the domain *Property 20* quantifies over, minus the paths that take
    no part in reconciliation.
    """
    return tuple(
        sorted(
            (set(previous.paths) | set(on_disk.paths) | set(staging.paths))
            - UNCLASSIFIED_PATHS
        )
    )


def classify(
    previous: ManifestBaseline,
    on_disk: FileTree,
    staging: FileTree,
) -> tuple[Classification, ...]:
    """Classify every path in the union of the three inputs, sorted by path."""
    return tuple(
        classify_path(
            path,
            previous_sha256=previous.sha256(path),
            on_disk_sha256=on_disk.sha256(path),
            staging_sha256=staging.sha256(path),
            owner=previous.owner(path),
        )
        for path in union_paths(previous, on_disk, staging)
    )


def reconcile(
    previous: ManifestBaseline,
    on_disk: FileTree,
    staging: FileTree,
    *,
    to_release: str,
    from_release: str | None = None,
    flagged_invariant_discounts: Iterable[FlaggedDiscount] = (),
) -> ReconciliationReport:
    """Classify three inputs into one `ReconciliationReport`.

    `from_release` defaults to the release the previous manifest recorded, which
    is the only trustworthy statement of what the Power was built from.
    """
    return ReconciliationReport(
        to_release=to_release,
        from_release=(
            previous.template_release if from_release is None else from_release
        ),
        classifications=classify(previous, on_disk, staging),
        flagged_invariant_discounts=tuple(flagged_invariant_discounts),
    )


def reconcile_directories(
    power: str | Path,
    staging: str | Path,
    *,
    to_release: str,
    from_release: str | None = None,
    manifest: str | Path | None = None,
    contract: Any = None,
    from_release_tree: Any = None,
    to_release_tree: Any = None,
) -> ReconciliationReport:
    """Read the three inputs from disk and reconcile them.

    Read-only: classifying reports, it does not act. Acting on the verdict is
    `apply_to_staging`, which writes only inside the staging tree; publishing the
    result is the update orchestration's atomic swap, after the Schema_Validator
    passes.

    Given **both** release trees, the report also carries the invariant-text
    drift comparison *(R15 AC10)*: each `invariantDiscounts` entry's invariant is
    read from each resolved release and flagged when the text moved. One tree
    alone compares nothing — drift is a statement about two releases — and
    neither tree leaves `flaggedInvariantDiscounts` empty, exactly as before.
    `contract` names where the register is read from and defaults to the contract
    beside the engine, so create and update share one discount set *(R15 AC11)*.
    """
    baseline = ManifestBaseline.from_file(
        Path(manifest) if manifest is not None else Path(power) / MANIFEST_FILENAME
    )
    resolved_from = (
        baseline.template_release if from_release is None else from_release
    )

    flagged: tuple[FlaggedDiscount, ...] = ()
    if from_release_tree is not None and to_release_tree is not None:
        flagged = flag_release_invariant_drift(
            load_discount_register(contract),
            from_release_tree,
            to_release_tree,
            from_release=resolved_from,
            to_release=to_release,
        )

    return reconcile(
        baseline,
        FileTree.from_directory(power),
        FileTree.from_directory(staging),
        to_release=to_release,
        from_release=resolved_from,
        flagged_invariant_discounts=flagged,
    )


def write_report(report: ReconciliationReport, path: str | Path) -> Path:
    """Write the report as UTF-8 JSON with LF endings and a trailing newline."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(report.serialize())
    except OSError as error:
        raise TransformError(
            E_WRITE_FAILED,
            f"cannot write the reconciliation report to {target}: {error}",
            path=str(target),
        ) from error
    return target


# ---------------------------------------------------------------------------
# Application: making the verdict true
# ---------------------------------------------------------------------------
#
# `apply_report` is pure in the same way `classify` is — a report and two trees
# in, one reconciled tree out — so *Property 21* drives preservation entirely in
# memory, and `apply_to_staging` is a thin shell that writes what the pure
# function decided.


@dataclass(frozen=True)
class FileResolution:
    """Where one path's reconciled bytes come from, and what they are.

    Carries the bytes rather than a pointer to a tree so a resolution answers
    "what will be published here?" on its own, and carries `on_disk_sha256` and
    `locally_divergent` so the preservation rule can be *checked* against the
    same record that decided the outcome, not re-derived from a second source.
    """

    path: str
    bucket: str
    action: str
    source: str
    content: bytes | None = None
    on_disk_sha256: str | None = None
    locally_divergent: bool = False
    reason: str | None = None

    @property
    def sha256(self) -> str | None:
        """The hash of the reconciled bytes; `None` when the path is dropped."""
        return None if self.content is None else sha256_hex(self.content)

    @property
    def preserved(self) -> bool:
        """Whether the local side won this path *(R5 AC5, AC6)*."""
        return self.action == ACTION_KEEP_ON_DISK

    @property
    def present(self) -> bool:
        return self.content is not None

    @property
    def overwrites_local_divergence(self) -> bool:
        """Whether this resolution would replace locally divergent content.

        The rule the design states without exception, negated: a preserved path
        must reproduce the on-disk side exactly — *including its absence*, so a
        local delete is not undone — and no divergent file that exists on disk
        may be published with different bytes, whatever its bucket.
        """
        if self.preserved:
            return self.sha256 != self.on_disk_sha256
        if self.locally_divergent and self.on_disk_sha256 is not None:
            return self.sha256 != self.on_disk_sha256
        return False

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "bucket": self.bucket,
            "action": self.action,
            "source": self.source,
            "sha256": self.sha256,
            "preserved": self.preserved,
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class PreservationDefect:
    """A path the application would have overwritten. Always a fault.

    Distinct from a `Conflict`: a conflict is a reported outcome the Maintainer
    resolves, while a defect means the mechanism that retains local content
    failed, so the tree must not be published *(R5 AC5)*.
    """

    path: str
    detail: str

    def to_json(self) -> dict[str, Any]:
        return {"path": self.path, "detail": self.detail}


@dataclass(frozen=True)
class Application:
    """The reconciled tree: the exact bytes an update should publish.

    `tree` is what the atomic swap makes visible at the Power's path, and
    `resolutions` says, per path, which side it came from and why. Unclassified
    paths — the Build_Manifest — are listed in `carried`: they pass through from
    staging untouched, because the manifest records what the engine produced and
    editing it would erase the divergence that keeps an adaptation alive across
    the *next* update.
    """

    tree: FileTree
    resolutions: tuple[FileResolution, ...] = ()
    carried: tuple[str, ...] = ()

    def resolution_of(self, path: str) -> FileResolution | None:
        for resolution in self.resolutions:
            if resolution.path == path:
                return resolution
        return None

    def paths_with_action(self, action: str) -> tuple[str, ...]:
        return tuple(
            resolution.path
            for resolution in self.resolutions
            if resolution.action == action
        )

    @property
    def preserved_paths(self) -> tuple[str, ...]:
        """Every path whose local content the update keeps *(R5 AC5, AC6)*."""
        return tuple(
            resolution.path for resolution in self.resolutions if resolution.preserved
        )

    @property
    def taken_from_staging(self) -> tuple[str, ...]:
        return self.paths_with_action(ACTION_TAKE_STAGING)

    @property
    def dropped_paths(self) -> tuple[str, ...]:
        """Paths the reconciled tree does not contain: removed or kept deleted."""
        return tuple(
            resolution.path
            for resolution in self.resolutions
            if resolution.content is None
        )

    def defects(self) -> tuple[PreservationDefect, ...]:
        """Every path this application would overwrite. Empty is the invariant.

        Pure and total over `resolutions`, so a property test asserts the rule
        by asking for an empty tuple rather than by re-implementing the table.
        """
        return tuple(
            PreservationDefect(
                path=resolution.path,
                detail=(
                    f"{resolution.bucket}/{resolution.action} would publish "
                    f"{_short(resolution.sha256)} where the on-disk file is "
                    f"{_short(resolution.on_disk_sha256)}"
                ),
            )
            for resolution in self.resolutions
            if resolution.overwrites_local_divergence
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "resolutions": [item.to_json() for item in self.resolutions],
            "carried": list(self.carried),
            "preserved": list(self.preserved_paths),
            "dropped": list(self.dropped_paths),
            "defects": [item.to_json() for item in self.defects()],
        }

    def summary(self) -> str:
        return (
            f"{len(self.tree)} file(s) reconciled: "
            f"{len(self.preserved_paths)} preserved from disk, "
            f"{len(self.taken_from_staging)} taken from staging, "
            f"{len(self.dropped_paths)} dropped, "
            f"{len(self.carried)} carried unclassified"
        )


def resolve_classification(
    classification: Classification,
    on_disk: FileTree,
    staging: FileTree,
) -> FileResolution:
    """Turn one verdict into the bytes that verdict implies.

    The action alone decides which side is read (`ACTION_SOURCES`); nothing here
    re-examines the hashes, so the application cannot disagree with the
    classification it was handed.
    """
    source = ACTION_SOURCES.get(classification.action)
    if source is None:  # pragma: no cover - the actions are a closed set
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"no reconciled source is defined for action "
            f"{classification.action!r} on '{classification.path}'",
            path=classification.path,
        )

    if source == SOURCE_ON_DISK:
        content = on_disk.read_bytes(classification.path)
    elif source == SOURCE_STAGING:
        content = staging.read_bytes(classification.path)
    else:
        content = None

    return FileResolution(
        path=classification.path,
        bucket=classification.bucket,
        action=classification.action,
        source=source,
        content=content,
        on_disk_sha256=classification.on_disk_sha256,
        locally_divergent=classification.locally_divergent,
        reason=classification.reason,
    )


def apply_report(
    report: ReconciliationReport,
    on_disk: FileTree,
    staging: FileTree,
) -> Application:
    """Build the reconciled tree from a report and the two trees it classified.

    Pure: reads no filesystem, no clock, no environment. The result is a
    function of the report and the two trees alone, so the same inputs always
    produce the same tree and *Property 21* can be checked in memory.
    """
    resolutions = tuple(
        resolve_classification(classification, on_disk, staging)
        for classification in sorted(
            report.classifications, key=lambda item: item.path
        )
    )

    files: dict[str, bytes] = {
        resolution.path: resolution.content
        for resolution in resolutions
        if resolution.content is not None
    }

    # Unclassified paths pass through from staging verbatim. See the module
    # docstring: the manifest describes the build, not the reconciled result.
    carried: list[str] = []
    for path in sorted(UNCLASSIFIED_PATHS):
        data = staging.read_bytes(path)
        if data is not None:
            files[path] = data
            carried.append(path)

    return Application(
        tree=FileTree(files=files),
        resolutions=resolutions,
        carried=tuple(carried),
    )


def apply_to_staging(
    report: ReconciliationReport,
    power: str | Path,
    staging: str | Path,
    *,
    verify: bool = True,
) -> Application:
    """Edit the staging tree into the reconciled shape, then check the rule.

    Writes **only** under `staging`, which the engine owns and discards on
    failure; the Power at `power` is read-only here. The atomic swap that follows
    therefore keeps its all-or-nothing character, and a fault part-way through
    this call leaves the Power byte-identical to its prior state *(R5 AC7)*.

    Idempotent: a path is written only when its staged bytes already differ, so a
    second application performs no writes and changes nothing.

    With `verify` on (the default) the staging tree is re-read afterwards and
    every preserved path checked byte-for-byte against the Power. A mismatch is
    `E_WRITE_FAILED` — publishing a tree that dropped an adaptation is a worse
    outcome than not publishing.
    """
    staging_root = Path(staging)
    if not staging_root.is_dir():
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"staging tree is absent, nothing to reconcile into: {staging_root}",
            staging=str(staging_root),
        )

    on_disk_tree = FileTree.from_directory(power)
    staged_tree = FileTree.from_directory(staging_root)
    application = apply_report(report, on_disk_tree, staged_tree)

    defects = application.defects()
    if defects:
        raise TransformError(
            E_TRANSFORM_FAILED,
            "refusing to apply a reconciliation that would overwrite locally "
            "divergent content: "
            + "; ".join(f"{item.path}: {item.detail}" for item in defects),
            paths=[item.path for item in defects],
        )

    for path, data in sorted(application.tree.files.items()):
        if staged_tree.read_bytes(path) != data:
            _write_into_staging(staging_root, path, data)
    for path in staged_tree.paths:
        if path not in application.tree:
            _remove_from_staging(staging_root, path)
    _prune_empty_directories(staging_root)

    if verify:
        _verify_preservation(application, staging_root, on_disk_tree)
    return application


def _write_into_staging(staging: Path, relative: str, data: bytes) -> None:
    """Write one contained file into staging, never through a symlink."""
    target = contained_path(
        staging, relative, what="reconciled file", code=E_WRITE_FAILED
    )
    walk = staging
    for segment in relative.split("/"):
        walk = walk / segment
        if walk.is_symlink():
            raise TransformError(
                E_WRITE_FAILED,
                f"refusing to write through the symlink {walk} while reconciling "
                f"{relative}",
                path=relative,
                staging=str(staging),
            )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    except OSError as error:
        raise TransformError(
            E_WRITE_FAILED,
            f"cannot write the reconciled file {relative}: {error}",
            path=relative,
            staging=str(staging),
        ) from error


def _remove_from_staging(staging: Path, relative: str) -> None:
    """Drop one staged file the reconciliation does not publish."""
    target = contained_path(
        staging, relative, what="reconciled file", code=E_WRITE_FAILED
    )
    try:
        if target.is_symlink() or target.exists():
            target.unlink()
    except OSError as error:
        raise TransformError(
            E_WRITE_FAILED,
            f"cannot drop the staged file {relative}: {error}",
            path=relative,
            staging=str(staging),
        ) from error


def _prune_empty_directories(staging: Path) -> None:
    """Remove directories the drops emptied, deepest first.

    An empty directory is not content, so failing to remove one is not a reason
    to abandon an otherwise correct tree; it is left in place and ignored.
    """
    directories = sorted(
        (
            item
            for item in staging.rglob("*")
            if item.is_dir() and not item.is_symlink()
        ),
        key=lambda item: len(item.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            if next(directory.iterdir(), None) is None:
                directory.rmdir()
        except OSError:  # pragma: no cover - cosmetic, never fatal
            continue


def _verify_preservation(
    application: Application, staging: Path, on_disk: FileTree
) -> None:
    """Re-read staging and confirm no locally divergent file was overwritten.

    Reads the tree back from disk rather than trusting the write, because the
    claim being made is about what the swap will publish, not about what this
    process intended to write.
    """
    written = FileTree.from_directory(staging)
    offenders: list[PreservationDefect] = []
    for resolution in application.resolutions:
        if not resolution.preserved:
            continue
        expected = on_disk.read_bytes(resolution.path)
        actual = written.read_bytes(resolution.path)
        if actual != expected:
            offenders.append(
                PreservationDefect(
                    path=resolution.path,
                    detail=(
                        f"staged as {_short(written.sha256(resolution.path))} but the "
                        f"Power holds {_short(on_disk.sha256(resolution.path))}"
                    ),
                )
            )
    if offenders:
        raise TransformError(
            E_WRITE_FAILED,
            "the reconciled staging tree does not preserve every adaptation "
            "byte-identically: "
            + "; ".join(f"{item.path}: {item.detail}" for item in offenders),
            staging=str(staging),
            paths=[item.path for item in offenders],
        )


# ---------------------------------------------------------------------------
# Changelog: recording a successful update (R5 AC7, AC8)
# ---------------------------------------------------------------------------
#
# Three layers, for the same reason classification has three: the part that
# decides, the part that composes text, and the part that touches a disk.
#
#   changelog_context        report + two contract facts -> render context. Pure.
#   render_changelog_entry   context -> entry text. Reads one template file.
#   append_changelog_entry   changelog + entry -> changelog. Pure, append-only.
#   record_update_in_staging the filesystem step: read staged, compose, write.
#
# What the entry says is the report's business and the template's; neither is
# restated here. The report supplies the tag, the release it came from, and the
# three path lists; `contract.yaml` supplies the template repository slug and the
# contract version; the template decides the prose. So a wording change is a
# template edit, and the code below has no opinion to keep in sync.
#
# Deliberately absent, and the template says so too: a date, a timestamp, and a
# run identifier. Re-rendering the same update yields byte-identical text
# *(R16 AC8, Property 4)*, which is also what makes the recorded-already check
# below meaningful.


#: The Bootcamp_Power's own changelog, at the Power root. It has no template
#: source — the template repository's root `CHANGELOG.md` is in the contract's
#: `ignore` list — so reconciliation classifies it `preservedAdaptations` with
#: reason `local-only-no-template-source` and the application copies it forward
#: verbatim. Appending to the staged copy is therefore appending to the Power's
#: changelog, one atomic swap later.
CHANGELOG_FILENAME = "CHANGELOG.md"

#: The one entry template, beside the engine that renders it *(task 3.3)*. Its
#: own header documents the render contract this module implements: strict
#: undefined names, a kept trailing newline, LF on write.
CHANGELOG_TEMPLATE = (
    Path(__file__).resolve().parent / "templates" / "changelog-entry.md.j2"
)

#: An entry heading as the template writes it — `## 0.6.0` — and as a hand-kept
#: changelog might, with the tag in code ticks. Anchored per line: a tag
#: mentioned in an entry's prose is not that entry's heading.
_ENTRY_HEADING = "^##[ \t]+`?{tag}`?[ \t]*$"


def changelog_provenance(contract: Any = None) -> tuple[str, int | None]:
    """The two contract facts an entry carries: template slug and contract version.

    Accepts what the rest of this module accepts — nothing (the contract beside
    the engine, which is where create and update both read it from), a path, a
    loaded `Contract`, or a raw contract document — so a caller holding any of
    them does not unwrap it first.

    An absent or empty `template.repository` halts: the entry links the release
    it names, and a link built from an empty slug would publish a broken
    provenance record rather than report a missing one.
    """
    repository: Any = None
    contract_version: Any = None

    if contract is None or isinstance(contract, (str, os.PathLike)):
        loaded = load_contract(DEFAULT_CONTRACT if contract is None else contract)
        repository, contract_version = loaded.repository, loaded.contract_version
    elif isinstance(contract, Mapping):
        template = contract.get("template")
        if isinstance(template, Mapping):
            repository = template.get("repository")
        contract_version = contract.get("contractVersion")
    else:
        repository = getattr(contract, "repository", None)
        contract_version = getattr(contract, "contract_version", None)

    if not isinstance(repository, str) or not repository.strip():
        raise TransformError(
            E_TRANSFORM_FAILED,
            "the changelog entry names the Template_Plugin it was generated "
            "from, and the contract declares no 'template.repository'",
        )

    return (
        repository.strip(),
        contract_version if isinstance(contract_version, int) else None,
    )


def changelog_context(
    report: ReconciliationReport,
    *,
    template_repository: str,
    contract_version: int | None = None,
) -> dict[str, Any]:
    """The render context for one update's entry. Pure.

    A total function of the report and the two contract facts: no filesystem, no
    clock, no environment. The path lists are handed over as the report grouped
    them — the template sorts them — and `previous_tag` is supplied only when the
    Power's prior release is known, which is what switches the entry's wording
    from "Generated from" to "Updated from … to …".

    An empty `to_release` halts. The one thing R5 AC8 asks of the entry is that
    it identify the source Template_Release, so an entry that cannot name one is
    not an entry worth appending.
    """
    tag = report.to_release.strip() if isinstance(report.to_release, str) else ""
    if not tag:
        raise TransformError(
            E_TRANSFORM_FAILED,
            "the changelog entry must identify the Template_Release it records, "
            "and this reconciliation carries no 'toRelease' tag",
        )

    context: dict[str, Any] = {
        "tag": tag,
        "template_repository": template_repository,
        "added": list(report.added),
        "modified": list(report.modified),
        "removed": list(report.removed),
    }
    if isinstance(report.from_release, str) and report.from_release.strip():
        context["previous_tag"] = report.from_release.strip()
    if contract_version is not None:
        context["contract_version"] = contract_version
    return context


def render_changelog_entry(
    context: Mapping[str, Any], *, template: str | Path = CHANGELOG_TEMPLATE
) -> str:
    """Render one entry from a context, per the template's own render contract.

    `StrictUndefined` is the whole point of rendering it this way: a context
    missing `tag` or `template_repository` raises here rather than publishing an
    entry with a hole in it. `keep_trailing_newline` keeps the single LF the
    template ends with, and autoescaping stays off because the output is
    Markdown — escaping would corrupt the backticks and links the template
    writes.

    Jinja is imported here rather than at module import so classifying,
    applying, and the report stay usable without the renderer's dependency: a
    missing renderer is then a legible failure of *this* step instead of an
    `ImportError` on a module that mostly does not need it.
    """
    template_path = Path(template)
    try:
        source = template_path.read_text(encoding="utf-8")
    except OSError as error:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"cannot read the changelog entry template {template_path}: {error}",
            path=str(template_path),
        ) from error

    try:
        import jinja2
    except ImportError as error:  # pragma: no cover - dev dependency is pinned
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"cannot render {template_path}: jinja2 is not installed",
            path=str(template_path),
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
            E_TRANSFORM_FAILED,
            f"cannot render the changelog entry from {template_path}: {error}",
            path=str(template_path),
        ) from error


def changelog_entry(
    report: ReconciliationReport,
    *,
    contract: Any = None,
    template: str | Path = CHANGELOG_TEMPLATE,
) -> str:
    """One `ReconciliationReport` in, one entry's text out *(R5 AC8)*.

    The report → text function *Property 22* checks. It reads the contract and
    the template and nothing else, so two runs over the same report produce the
    same bytes, and the text it returns always names `report.to_release`.
    """
    repository, contract_version = changelog_provenance(contract)
    return render_changelog_entry(
        changelog_context(
            report,
            template_repository=repository,
            contract_version=contract_version,
        ),
        template=template,
    )


def entry_recorded(changelog: str, tag: str) -> bool:
    """Whether `changelog` already opens an entry for `tag`. Pure.

    Matches an entry *heading*, line-anchored, not a mention: an earlier entry
    that cites the tag in its prose has not recorded it. Used to keep a re-run
    from appending a second entry for a release the changelog already carries.
    """
    identifier = tag.strip()
    if not identifier:
        return False
    pattern = _ENTRY_HEADING.format(tag=re.escape(identifier))
    return re.search(pattern, changelog, re.MULTILINE) is not None


def append_changelog_entry(changelog: str, entry: str) -> str:
    """Append one entry to a changelog, adding bytes and rewriting none. Pure.

    The result always **starts with `changelog` verbatim**, which is how "no
    other changelog content is altered" *(Property 22)* is kept: there is no
    code path here that reflows, reorders, re-indents, or trims what is already
    written. The separator is chosen from what the existing text ends with, so
    exactly one blank line lands between the two — the template ends its entry at
    a single LF and leaves that separation to this function.

    A changelog that already ends in several blank lines keeps them all. Tidying
    the tail would mean rewriting bytes this function has no mandate to touch,
    and the cost is cosmetic.
    """
    text = entry if entry.endswith("\n") else f"{entry}\n"
    if not changelog:
        return text
    if changelog.endswith("\n\n"):
        return changelog + text
    if changelog.endswith("\n"):
        return f"{changelog}\n{text}"
    return f"{changelog}\n\n{text}"


@dataclass(frozen=True)
class ChangelogRecord:
    """What recording an update did, as data.

    `entry` is the rendered text, `text` the whole changelog afterwards, and
    `appended` says whether this call added the entry — false only when the
    staged changelog already carried a heading for the same tag, which is
    `already_recorded`. Both are reported rather than inferred so a caller
    narrating the run does not have to diff two strings to find out.
    """

    tag: str
    entry: str
    text: str
    appended: bool
    path: Path | None = None
    already_recorded: bool = False

    @property
    def names_tag(self) -> bool:
        """Whether the entry identifies its source Template_Release *(R5 AC8)*."""
        return bool(self.tag) and self.tag in self.entry

    def to_json(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "path": None if self.path is None else str(self.path),
            "appended": self.appended,
            "alreadyRecorded": self.already_recorded,
            "namesTag": self.names_tag,
        }

    def summary(self) -> str:
        if not self.appended:
            return (
                f"changelog already records {self.tag}; no entry appended"
            )
        return f"one changelog entry recorded for {self.tag}"


def _read_changelog(target: Path) -> str:
    """Read a changelog as text without translating a single byte.

    Bytes then decode, rather than `read_text`: universal newline translation
    would turn a CRLF the file carries into an LF on the way back out, which is
    an edit to content this step does not own. An absent file reads as empty —
    the first update of a Power that never had a changelog writes one.
    """
    if not target.exists():
        return ""
    try:
        data = target.read_bytes()
    except OSError as error:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"cannot read the staged changelog {target}: {error}",
            path=str(target),
        ) from error
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformError(
            E_TRANSFORM_FAILED,
            f"the staged changelog {target} is not valid UTF-8: {error}",
            path=str(target),
        ) from error


def _refuse_power_write(target: Path, power: str | Path) -> None:
    """Refuse a changelog write that would land inside the Power *(R5 AC7)*.

    The guarantee that a failed update makes no changelog entry rests entirely on
    the entry being staged rather than written into the Power, so a caller that
    passes the Power as its staging tree is stopped here instead of quietly
    editing the deliverable in place.
    """
    power_root = Path(power)
    resolved_target = target.resolve()
    resolved_power = power_root.resolve()
    if resolved_target == resolved_power or resolved_target.is_relative_to(
        resolved_power
    ):
        raise TransformError(
            E_WRITE_FAILED,
            f"refusing to write {target} inside the Bootcamp_Power at "
            f"{power_root}: a changelog entry is staged and published by the "
            "atomic swap, so that a failed update leaves the Power unchanged",
            path=str(target),
            power=str(power_root),
        )


def record_update_in_staging(
    report: ReconciliationReport,
    staging: str | Path,
    *,
    power: str | Path | None = None,
    contract: Any = None,
    template: str | Path = CHANGELOG_TEMPLATE,
    skip_if_recorded: bool = True,
) -> ChangelogRecord:
    """Append this update's entry to the **staged** changelog *(R5 AC7, AC8)*.

    Writes exactly one file, `<staging>/CHANGELOG.md`, through the same contained
    writer the application uses: nothing outside the staging tree, and never
    through a symlink. The Power is not written to at all — with `power` given it
    is checked against, not written to — so a failure here or anywhere later
    discards staging and leaves the Power and its changelog byte-identical
    *(R5 AC7)*.

    Call **after** `apply_to_staging`, which is what puts the Power's existing
    changelog into staging to be appended to; see the module docstring.

    Exactly one entry per call, and with `skip_if_recorded` on (the default) at
    most one per release: a staged changelog that already opens an entry for
    `report.to_release` is left byte-identical and reported as
    `already_recorded`, so a retried update cannot record the same release twice.
    """
    staging_root = Path(staging)
    if not staging_root.is_dir():
        raise TransformError(
            E_TRANSFORM_FAILED,
            "staging tree is absent, nothing to record a changelog entry into: "
            f"{staging_root}",
            staging=str(staging_root),
        )

    target = contained_path(
        staging_root, CHANGELOG_FILENAME, what="changelog", code=E_WRITE_FAILED
    )
    if power is not None:
        _refuse_power_write(target, power)

    entry = changelog_entry(report, contract=contract, template=template)
    tag = report.to_release.strip()
    existing = _read_changelog(target)

    if skip_if_recorded and entry_recorded(existing, tag):
        return ChangelogRecord(
            tag=tag,
            entry=entry,
            text=existing,
            appended=False,
            path=target,
            already_recorded=True,
        )

    text = append_changelog_entry(existing, entry)
    _write_into_staging(staging_root, CHANGELOG_FILENAME, text.encode("utf-8"))
    return ChangelogRecord(
        tag=tag, entry=entry, text=text, appended=True, path=target
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_FAILED = 1


def _narrate(message: str) -> None:
    """Human-readable narration goes to stderr; stdout carries only JSON."""
    print(f"reconcile: {message}", file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reconcile.py",
        description=(
            "Three-way reconciliation between the last build's manifest hashes, "
            "the current Bootcamp_Power, and a freshly transformed staging tree. "
            "Reports; changes nothing unless --apply is given, and then only "
            "inside the staging tree. JSON to stdout, narration to stderr."
        ),
    )
    parser.add_argument(
        "--power",
        required=True,
        help="the existing Bootcamp_Power directory (read-only)",
    )
    parser.add_argument(
        "--staging",
        required=True,
        help="the freshly transformed staging tree to compare against",
    )
    parser.add_argument(
        "--to-release",
        required=True,
        help="the newly resolved Template_Release tag being propagated",
    )
    parser.add_argument(
        "--from-release",
        default=None,
        help=(
            "the release the Power was built from (default: the templateRelease "
            "recorded in the previous build manifest)"
        ),
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "previous build manifest to use as the baseline "
            f"(default: <power>/{MANIFEST_FILENAME})"
        ),
    )
    parser.add_argument(
        "--from-release-tree",
        default=None,
        help=(
            "extracted tree of the release the Power was built from, read for "
            "the invariant-text drift comparison; needs --to-release-tree too"
        ),
    )
    parser.add_argument(
        "--to-release-tree",
        default=None,
        help=(
            "extracted tree of the newly resolved release, read for the "
            "invariant-text drift comparison; needs --from-release-tree too"
        ),
    )
    parser.add_argument(
        "--contract",
        default=None,
        help=(
            "path to contract.yaml, read for the Invariant_Discount_Register "
            "compared for text drift and for the template repository and "
            "contract version a changelog entry records (default: the contract "
            "beside this script)"
        ),
    )
    parser.add_argument(
        "--report",
        default=None,
        help="path the ReconciliationReport JSON is also written to",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "materialize the reconciled result into the staging tree, so every "
            "preserved adaptation carries its on-disk bytes byte-identically "
            "before the atomic swap; writes only under --staging, never the Power"
        ),
    )
    parser.add_argument(
        "--changelog",
        action="store_true",
        help=(
            "append this update's entry, naming --to-release, to the staged "
            f"{CHANGELOG_FILENAME}, so the atomic swap publishes exactly one new "
            "entry; writes only under --staging, so a failed update records "
            "nothing. Use with --apply, which seeds the staged changelog from "
            "the Power"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.to_release.strip():
        _narrate("--to-release must be a non-empty release tag")
        return EXIT_FAILED

    # Drift is a statement about two releases, so one tree compares nothing.
    # Said plainly rather than silently, because a Maintainer who passed one
    # would otherwise read an empty flag list as "no discount drifted".
    if (args.from_release_tree is None) != (args.to_release_tree is None):
        _narrate(
            "invariant-text drift needs both --from-release-tree and "
            "--to-release-tree; no discount was compared"
        )

    try:
        report = reconcile_directories(
            args.power,
            args.staging,
            to_release=args.to_release,
            from_release=args.from_release,
            manifest=args.manifest,
            contract=args.contract,
            from_release_tree=args.from_release_tree,
            to_release_tree=args.to_release_tree,
        )
    except TransformError as error:
        _narrate(f"{error.code}: {error.message}")
        json.dump(error.to_json(), sys.stdout, indent=2, sort_keys=False)
        print(file=sys.stdout)
        return EXIT_FAILED

    _narrate(
        f"{args.power} (from {report.from_release}) against {args.staging} "
        f"(to {report.to_release})"
    )
    for bucket, paths in report.buckets().items():
        for path in paths:
            _narrate(f"{bucket:>21}  {path}")
    for conflict in report.conflicts:
        _narrate(f"conflict {conflict.path}: {conflict.adaptation}")
        _narrate(f"         upstream: {conflict.template_change}")
        _narrate(f"         {conflict.resolution}")
    for flagged in report.flagged_invariant_discounts:
        _narrate(f"flagged discount {flagged.invariant}: {flagged.reason}")
        _narrate(f"                 {flagged.action}")
    _narrate(report.summary())

    if args.apply:
        try:
            application = apply_to_staging(report, args.power, args.staging)
        except TransformError as error:
            _narrate(f"{error.code}: {error.message}")
            json.dump(error.to_json(), sys.stdout, indent=2, sort_keys=False)
            print(file=sys.stdout)
            return EXIT_FAILED
        for path in application.preserved_paths:
            _narrate(f"preserved from disk  {path}")
        for path in application.dropped_paths:
            _narrate(f"dropped              {path}")
        _narrate(application.summary())

    # After --apply, deliberately: the application is what carries the Power's
    # existing changelog into staging, and appending first would have it rewritten
    # back to the Power's bytes.
    if args.changelog:
        if not args.apply:
            _narrate(
                f"--changelog without --apply: the staged {CHANGELOG_FILENAME} is "
                "seeded from the Power by --apply, so prior changelog content is "
                "not carried forward"
            )
        try:
            record = record_update_in_staging(
                report,
                args.staging,
                power=args.power,
                contract=args.contract,
            )
        except TransformError as error:
            _narrate(f"{error.code}: {error.message}")
            json.dump(error.to_json(), sys.stdout, indent=2, sort_keys=False)
            print(file=sys.stdout)
            return EXIT_FAILED
        _narrate(f"{record.summary()} ({record.path})")

    if args.report is not None:
        try:
            written = write_report(report, args.report)
        except TransformError as error:
            _narrate(f"{error.code}: {error.message}")
            json.dump(error.to_json(), sys.stdout, indent=2, sort_keys=False)
            print(file=sys.stdout)
            return EXIT_FAILED
        _narrate(f"report written to {written}")

    # A conflict is a reported outcome, not an error: it retains the local
    # content and asks for attention, so it never changes the exit code.
    json.dump(report.to_json(), sys.stdout, indent=2, sort_keys=False)
    print(file=sys.stdout)
    return EXIT_SUCCESS


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
