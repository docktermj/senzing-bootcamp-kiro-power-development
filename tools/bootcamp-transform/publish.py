#!/usr/bin/env python3
"""Publisher — adapt a built Bootcamp_Power for the publication repository.

    publish.py --power powers/senzing-bootcamp
               --target <checkout of Senzing/senzing-bootcamp-kiro-power>
               [--contract tools/bootcamp-transform/publication.yaml]
               [--expect-version <semver>]
               [--report <file>]
               [--check]     # decide and report; write nothing anywhere

JSON goes to stdout; human-readable narration goes to stderr. The publish skill
reads the JSON, so agent behavior stays out of the deterministic path — the same
split ``resolve_release.py`` and ``transform.py`` use.

What it is for
--------------
The Power is built in this repository and consumed in another one, and those are
not the same artifact. Three differences are real and permanent:

* the maintainer's ``CHANGELOG.md``, which R5 AC8 requires the update path to
  write here and which has no audience there;
* ``plugin.json``'s ``extensions`` block, which the Agent Plugins spec permits,
  the build correctly emits, and the publication repository removed in 0.5.1 and
  now fails on;
* two provenance notes whose subject — this repository's authored template tree —
  a reader of the publication repository cannot open.

Every one of them is declared in the Publication_Contract at
``publication.yaml``. This script executes that file and nothing else: no
adaptation is hardcoded here, for the same reason no substitution is hardcoded in
``transform.py``. An adaptation with one home survives the next release; an
adaptation applied by hand at release time does not.

The property that makes it safe to run again
--------------------------------------------
Every declared rule must match something. A rule whose needle is absent from a
file it declares is reported as ``E_SUBSTITUTION_UNAPPLIED`` (or
``E_RULE_INERT`` for an ``exclude`` or ``dropKeys`` rule) and the publication
stops. This is the whole point: the dangerous failure is not a rule that breaks,
it is a rule that quietly stops applying because the build changed the line it
was written against, so the next release ships the leak the rule existed to
prevent. Matching nothing is therefore an error and not a no-op.

The ``forbidden`` scan then checks the same invariant a second time, from the
other end and independently of the rules: no string naming this repository
survives anywhere in the published tree. A rule that stops covering its case
fails there too, so the invariant does not rest on the rule list being complete.

Manifest handling
-----------------
Adapting a file changes its bytes, so ``.build-manifest.json`` is recomputed for
exactly the entries this script rewrote, and entries for excluded paths are
dropped. Every other field, key order included, is preserved. The staged tree is
then checked both ways — no recorded file missing, no unrecorded file present —
because that is the check the publication repository's own
``validate_power.py`` runs, and finding out here is cheaper than finding out in
CI.

Recomputing a digest is normally the wrong move, and
``.github/tools/refresh_build_manifest.py`` in the publication repository says so
at length: drift usually means someone hand-edited build output that the next
rebuild will silently revert. The justification here is that these edits are not
corrections to the build. They are differences between two repositories that
both keep their current jobs, so there is no upstream edit that would make them
unnecessary. ``--report`` prints that justification rule by rule, which is what
the publication pull request needs to say.

Publication is a swap
---------------------
The adapted tree is staged as a sibling of the target directory and moved into
place by rename, so the target is either wholly its old self or wholly its new
self. Nothing is written outside ``<target>/<powerDirectory>``: the publication
repository's root files — its README, its CHANGELOG, its workflows — are its
own, and this script does not touch them.

Outcomes
--------
=========================================== ============================== ====
Condition                                   ``error``                      exit
=========================================== ============================== ====
Published (or, with ``--check``, would be)  (absent)                       0
``--check`` and something would change      (absent, ``wouldChange``)      1
Power root is not a Power                   ``E_NOT_A_POWER``              2
Target is not a publication checkout        ``E_NOT_A_PUBLICATION``        2
``--expect-version`` /= plugin.json         ``E_VERSION_MISMATCH``         1
A substitution matched nothing              ``E_SUBSTITUTION_UNAPPLIED``   1
An exclude/dropKeys rule matched nothing    ``E_RULE_INERT``               1
A forbidden string survives                 ``E_FORBIDDEN_REFERENCE``      1
Manifest and staged tree disagree           ``E_MANIFEST_INCOMPLETE``      1
=========================================== ============================== ====

Every failure leaves the target untouched. The staging directory is removed on
the way out whether the run succeeded or not, so a failed publication leaves no
partial tree behind for the next one to trip over.

Testability
-----------
``adapt_text``, ``drop_pointer``, ``forbidden_findings`` and ``plan_publication``
are pure over their inputs, so the tests drive them with in-memory trees and no
filesystem. ``publish`` takes the staging root as an argument for the same
reason.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "E_FORBIDDEN_REFERENCE",
    "E_MANIFEST_INCOMPLETE",
    "E_NOT_A_POWER",
    "E_NOT_A_PUBLICATION",
    "E_RULE_INERT",
    "E_SUBSTITUTION_UNAPPLIED",
    "E_VERSION_MISMATCH",
    "PublicationError",
    "Adaptation",
    "PublicationPlan",
    "adapt_text",
    "drop_pointer",
    "forbidden_findings",
    "load_contract",
    "plan_publication",
    "publish",
    "build_parser",
    "main",
]

E_FORBIDDEN_REFERENCE = "E_FORBIDDEN_REFERENCE"
E_MANIFEST_INCOMPLETE = "E_MANIFEST_INCOMPLETE"
E_NOT_A_POWER = "E_NOT_A_POWER"
E_NOT_A_PUBLICATION = "E_NOT_A_PUBLICATION"
E_RULE_INERT = "E_RULE_INERT"
E_SUBSTITUTION_UNAPPLIED = "E_SUBSTITUTION_UNAPPLIED"
E_VERSION_MISMATCH = "E_VERSION_MISMATCH"

MANIFEST_FILENAME = ".build-manifest.json"

# Files a build leaves behind that are never part of a Power. Kept in step with
# ``shipped_files`` in the publication repository's validate_power.py, which
# excludes the same directory for the same reason.
NEVER_PUBLISHED_PARTS = frozenset({"__pycache__"})

DEFAULT_CONTRACT = Path(__file__).resolve().parent / "publication.yaml"


class PublicationError(Exception):
    """A refusal that carries its machine-readable code and JSON payload."""

    def __init__(self, code: str, message: str, *, findings: Sequence[str] = (), exit_code: int = 1):
        super().__init__(message)
        self.code = code
        self.message = message
        self.findings = list(findings)
        self.exit_code = exit_code

    def payload(self) -> dict:
        return {
            "reportVersion": 1,
            "error": self.code,
            "message": self.message,
            "findings": self.findings,
        }


@dataclass
class Adaptation:
    """One applied rule, as the report records it."""

    kind: str
    ruleId: str
    path: str
    reason: str
    detail: str = ""

    def to_json(self) -> dict:
        return {
            "kind": self.kind,
            "ruleId": self.ruleId,
            "path": self.path,
            "reason": " ".join(self.reason.split()),
            "detail": self.detail,
        }


@dataclass
class PublicationPlan:
    """Everything a run decided, whether or not it wrote anything."""

    powerVersion: str
    templateRelease: str
    publicationRepository: str
    powerDirectory: str
    adaptations: list[Adaptation] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    digestsRecomputed: list[str] = field(default_factory=list)
    manifestEntriesDropped: list[str] = field(default_factory=list)
    scannedForForbidden: int = 0
    undecodableSkipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "reportVersion": 1,
            "powerVersion": self.powerVersion,
            "templateRelease": self.templateRelease,
            "publicationRepository": self.publicationRepository,
            "powerDirectory": self.powerDirectory,
            "adaptations": [item.to_json() for item in self.adaptations],
            "excluded": self.excluded,
            "digestsRecomputed": self.digestsRecomputed,
            "manifestEntriesDropped": self.manifestEntriesDropped,
            "scannedForForbidden": self.scannedForForbidden,
            "undecodableSkipped": self.undecodableSkipped,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def adapt_text(body: str, find: str, replace: str) -> tuple[str, int]:
    """Replace every occurrence of ``find``, and say how many there were.

    A literal replacement, never a regular expression: the needles are prose and
    JSON fragments, and a regex would turn a stray ``.`` or ``(`` in either into
    a silent mismatch or a wrong match.
    """
    count = body.count(find)
    if count == 0:
        return body, 0
    return body.replace(find, replace), count


def _end_of_json_value(text: str, start: int) -> int:
    """The index just past the JSON value that begins at or after ``start``.

    String-aware, so a brace or bracket inside a string literal does not move
    the depth counter, and escape-aware, so an escaped quote does not end a
    string early.
    """
    index = start
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    if index >= len(text):
        raise ValueError("no value at that position")

    first = text[index]

    if first in "{[":
        depth = 0
        in_string = False
        escaped = False
        while index < len(text):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char in "{[":
                depth += 1
            elif char in "}]":
                depth -= 1
                if depth == 0:
                    return index + 1
            index += 1
        raise ValueError("unterminated object or array")

    if first == '"':
        index += 1
        escaped = False
        while index < len(text):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                return index + 1
            index += 1
        raise ValueError("unterminated string")

    # A number, or true/false/null.
    while index < len(text) and text[index] not in ",}] \t\r\n":
        index += 1
    return index


def _root_members(text: str) -> list[tuple[str, int, int]]:
    """``(key, key_start, value_end)`` for every member of the root object."""
    index = text.index("{") + 1
    members: list[tuple[str, int, int]] = []
    while index < len(text):
        char = text[index]
        if char in " \t\r\n,":
            index += 1
            continue
        if char == "}":
            break
        if char != '"':
            raise ValueError(f"unexpected character {char!r} at offset {index}")
        key_end = _end_of_json_value(text, index)
        key = json.loads(text[index:key_end])
        colon = key_end
        while colon < len(text) and text[colon] in " \t\r\n":
            colon += 1
        if colon >= len(text) or text[colon] != ":":
            raise ValueError(f"member {key!r} is not followed by ':'")
        value_end = _end_of_json_value(text, colon + 1)
        members.append((key, index, value_end))
        index = value_end
    return members


def drop_pointer(text: str, pointer: str) -> tuple[str, bool]:
    """Excise a root-level member from JSON **text**, preserving every other byte.

    A parse-and-reserialize would be shorter and wrong. ``plugin.json`` is
    rendered from a Jinja template with a hand-written layout — ``author`` and
    ``keywords`` each on a single line — and ``json.dumps(indent=2)`` expands
    both. The published file would then differ from the built one in dozens of
    lines that have nothing to do with the rule, and every one of those lines
    would be a digest change to review. So the edit is textual, and the result
    is parsed and compared against the document-minus-the-pointer to prove the
    excision did exactly what the rule says.

    Only a single root-level key is supported. A deeper pointer raises rather
    than silently doing something adjacent: no rule needs one, and inventing
    semantics for a case with no caller is how a tool acquires behavior nobody
    asked for.
    """
    if not pointer.startswith("/"):
        raise ValueError(f"pointer must start with '/': {pointer!r}")

    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]
    if len(tokens) != 1 or not tokens[0]:
        raise ValueError(f"only a single root-level key is supported, not {pointer!r}")
    key = tokens[0]

    document = json.loads(text)
    if not isinstance(document, dict) or key not in document:
        return text, False

    expected = {name: value for name, value in document.items() if name != key}

    located = [member for member in _root_members(text) if member[0] == key]
    if len(located) != 1:
        raise ValueError(f"expected exactly one root member {key!r}, found {len(located)}")
    _, key_start, value_end = located[0]

    # Is there a comma before the member, after it, or both?
    before = key_start - 1
    while before >= 0 and text[before] in " \t\r\n":
        before -= 1
    preceding_comma = before >= 0 and text[before] == ","

    after = value_end
    while after < len(text) and text[after] in " \t\r\n":
        after += 1
    following_comma = after < len(text) and text[after] == ","

    start, end = key_start, value_end

    def consume_line_terminator(at: int) -> int:
        if text[at : at + 2] == "\r\n":
            return at + 2
        if at < len(text) and text[at] == "\n":
            return at + 1
        return at

    def extend_to_line_start(at: int) -> int:
        line_start = text.rfind("\n", 0, at) + 1
        return line_start if text[line_start:at].strip() == "" else at

    if following_comma:
        # Not the last member: take the member, its comma, and — when the member
        # had its lines to itself — the whole line it sat on.
        end = after + 1
        if (moved := extend_to_line_start(key_start)) != key_start:
            start = moved
            end = consume_line_terminator(end)
    elif preceding_comma:
        # The last member: take the comma that joined it to the previous one and
        # stop at the end of the value, so the newline that terminated the member
        # stays behind and the closing brace keeps its own line.
        start = before
    else:
        # The only member: the object is left empty.
        if (moved := extend_to_line_start(key_start)) != key_start:
            start = moved
            end = consume_line_terminator(end)

    result = text[:start] + text[end:]

    reparsed = json.loads(result)
    if reparsed != expected:
        raise ValueError(
            f"excising {pointer!r} changed more than that member; refusing the edit"
        )
    return result, True


def forbidden_findings(relative: str, body: str, forbidden: Sequence[dict], exempt: Sequence[str]) -> list[str]:
    """Every forbidden needle present in one file's text, as reportable lines."""
    findings: list[str] = []
    for rule in forbidden:
        needle = rule["needle"]
        if needle in exempt:
            continue
        if needle not in body:
            continue
        for number, line in enumerate(body.splitlines(), start=1):
            if needle in line:
                why = " ".join(str(rule.get("why", "")).split())
                findings.append(f"{relative}:{number}: {needle!r} — {why}")
    return findings


def shipped_files(root: Path) -> list[Path]:
    """Every file in a Power, relative to its root, in stable order."""
    return sorted(
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and not NEVER_PUBLISHED_PARTS & set(path.parts)
    )


def load_contract(path: Path) -> dict:
    """Read the Publication_Contract.

    PyYAML is the repository's pinned parser and the Transformation_Contract's
    reader, so the two contracts are read the same way.
    """
    import yaml

    with path.open(encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)

    if not isinstance(contract, dict):
        raise PublicationError(
            E_NOT_A_PUBLICATION, f"{path}: is not a mapping", exit_code=2
        )
    for key in ("publicationContractVersion", "publication", "forbidden"):
        if key not in contract:
            raise PublicationError(
                E_NOT_A_PUBLICATION, f"{path}: required key {key!r} is absent", exit_code=2
            )
    return contract


# ---------------------------------------------------------------------------
# Planning and staging
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, document: Any) -> None:
    """Write JSON the way the build writes it: two-space indent, single LF."""
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")


def _stage(power: Path, staging: Path, excluded: Iterable[str]) -> None:
    """Copy the Power into ``staging``, minus the excluded paths."""
    skip = set(excluded)
    staging.mkdir(parents=True)
    for relative in shipped_files(power):
        if str(relative) in skip:
            continue
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        # copy2 so an executable bit on a shipped script survives publication.
        shutil.copy2(power / relative, destination)


def plan_publication(power: Path, staging: Path, contract: dict, expect_version: str | None) -> PublicationPlan:
    """Stage the Power, apply every declared rule, and verify the invariants.

    Raises ``PublicationError`` on the first refusal that makes the tree
    unpublishable, after collecting every finding of that kind so a run reports
    the whole problem rather than its first line.
    """
    manifest_path = power / MANIFEST_FILENAME
    plugin_path = power / "plugin.json"
    for required in (manifest_path, plugin_path, power / "mcp.json"):
        if not required.is_file():
            raise PublicationError(
                E_NOT_A_POWER,
                f"{power}: {required.name} is absent, so this is not a built Power",
                exit_code=2,
            )

    plugin = _read_json(plugin_path)
    manifest = _read_json(manifest_path)
    version = str(plugin.get("version", ""))
    template_release = str(manifest.get("templateRelease", ""))

    if expect_version is not None and version != expect_version:
        raise PublicationError(
            E_VERSION_MISMATCH,
            f"plugin.json declares version {version!r}, but --expect-version is {expect_version!r}",
        )

    publication = contract["publication"]
    plan = PublicationPlan(
        powerVersion=version,
        templateRelease=template_release,
        publicationRepository=str(publication["repository"]),
        powerDirectory=str(publication["powerDirectory"]),
    )

    # --- exclude ---------------------------------------------------------
    inert: list[str] = []
    for rule in contract.get("exclude") or []:
        relative = str(rule["path"])
        if not (power / relative).is_file():
            inert.append(f"exclude {relative!r}: no such file in the Power, so the rule is inert")
            continue
        plan.excluded.append(relative)
        plan.adaptations.append(
            Adaptation("exclude", relative, relative, str(rule.get("reason", "")))
        )

    _stage(power, staging, plan.excluded)

    # --- dropKeys --------------------------------------------------------
    for rule in contract.get("dropKeys") or []:
        relative = str(rule["path"])
        pointer = str(rule["pointer"])
        target = staging / relative
        if not target.is_file():
            inert.append(f"dropKeys {relative}{pointer}: no such file in the staged tree")
            continue
        body = target.read_text(encoding="utf-8")
        body, dropped = drop_pointer(body, pointer)
        if not dropped:
            inert.append(
                f"dropKeys {relative}{pointer}: pointer is absent, so the rule is inert"
            )
            continue
        target.write_text(body, encoding="utf-8", newline="")
        plan.adaptations.append(
            Adaptation("dropKeys", pointer, relative, str(rule.get("reason", "")), f"deleted {pointer}")
        )

    if inert:
        raise PublicationError(
            E_RULE_INERT,
            "a declared exclude/dropKeys rule matched nothing; the contract and the build "
            "have diverged, so publishing would silently drop an adaptation",
            findings=inert,
        )

    # --- substitutions ---------------------------------------------------
    unapplied: list[str] = []
    for rule in contract.get("substitutions") or []:
        rule_id = str(rule["id"])
        find = str(rule["find"])
        replace = str(rule["replace"])
        for relative in rule["appliesTo"]:
            relative = str(relative)
            target = staging / relative
            if not target.is_file():
                unapplied.append(f"{rule_id}: {relative} is not in the staged tree")
                continue
            body = target.read_text(encoding="utf-8")
            body, count = adapt_text(body, find, replace)
            if count == 0:
                unapplied.append(
                    f"{rule_id}: {relative} does not contain the declared find string"
                )
                continue
            target.write_text(body, encoding="utf-8", newline="")
            plan.adaptations.append(
                Adaptation(
                    "substitution",
                    rule_id,
                    relative,
                    str(rule.get("reason", "")),
                    f"{count} occurrence{'s' if count != 1 else ''} replaced",
                )
            )

    if unapplied:
        raise PublicationError(
            E_SUBSTITUTION_UNAPPLIED,
            "a declared substitution matched nothing; the build changed the text the rule "
            "was written against, so publishing would ship the reference the rule removes",
            findings=unapplied,
        )

    # --- manifest --------------------------------------------------------
    kept_entries = []
    for entry in manifest.get("files", []):
        relative = entry.get("path")
        if relative in plan.excluded:
            plan.manifestEntriesDropped.append(relative)
            continue
        target = staging / relative
        if not target.is_file():
            raise PublicationError(
                E_MANIFEST_INCOMPLETE,
                f"{relative}: recorded in the manifest but absent from the staged tree",
            )
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if entry.get("sha256") != digest:
            entry["sha256"] = digest
            plan.digestsRecomputed.append(relative)
        kept_entries.append(entry)
    manifest["files"] = kept_entries
    _write_json(staging / MANIFEST_FILENAME, manifest)

    recorded = {entry["path"] for entry in kept_entries}
    unrecorded = [
        str(relative)
        for relative in shipped_files(staging)
        if str(relative) != MANIFEST_FILENAME and str(relative) not in recorded
    ]
    if unrecorded:
        raise PublicationError(
            E_MANIFEST_INCOMPLETE,
            "the staged tree carries files the manifest does not record; the publication "
            "repository's manifest-drift check would fail on them",
            findings=[f"{relative}: present in the tree but not recorded in the manifest" for relative in unrecorded],
        )

    # --- forbidden -------------------------------------------------------
    allowlist = {
        str(item["path"]): [str(needle) for needle in (item.get("needles") or [])]
        for item in (contract.get("forbiddenAllowlist") or [])
    }
    forbidden = contract["forbidden"]
    leaks: list[str] = []
    for relative in shipped_files(staging):
        key = str(relative)
        try:
            body = (staging / relative).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # A binary asset: PNG, PDF, the vendored bundle. The manifest hashes
            # it and nothing here can read it as text, so say so in the report
            # rather than counting it as scanned.
            plan.undecodableSkipped.append(key)
            continue
        plan.scannedForForbidden += 1
        exempt = allowlist.get(key, [])
        if key in allowlist and not exempt:
            # An allowlist entry with no needles exempts nothing. It is a
            # reserved decision, not a hole, so the file is still scanned.
            pass
        leaks.extend(forbidden_findings(key, body, forbidden, exempt))

    if leaks:
        raise PublicationError(
            E_FORBIDDEN_REFERENCE,
            "the staged tree still names the development repository; the publication "
            "repository must not point a reader at a repository they cannot open",
            findings=leaks,
        )

    return plan


def publish(staging: Path, target_power: Path) -> None:
    """Move the staged tree into place by rename, then delete the old one."""
    target_power.parent.mkdir(parents=True, exist_ok=True)
    previous = target_power.with_name(target_power.name + ".previous")
    if previous.exists():
        shutil.rmtree(previous)
    if target_power.exists():
        target_power.rename(previous)
    staging.rename(target_power)
    if previous.exists():
        shutil.rmtree(previous)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--power", required=True, help="the built Power to publish")
    parser.add_argument("--target", required=True, help="a checkout of the publication repository")
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_CONTRACT),
        help=f"the Publication_Contract (default: {DEFAULT_CONTRACT.name})",
    )
    parser.add_argument(
        "--expect-version",
        help="refuse unless plugin.json declares this version; pass the tag being published",
    )
    parser.add_argument("--report", help="write the PublicationReport JSON here as well as to stdout")
    parser.add_argument(
        "--check",
        action="store_true",
        help="decide and report, write nothing; exit 1 if publishing would change the target",
    )
    return parser


def _tree_digest(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        str(relative): hashlib.sha256((root / relative).read_bytes()).hexdigest()
        for relative in shipped_files(root)
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)

    power = Path(arguments.power).resolve()
    target = Path(arguments.target).resolve()

    try:
        contract = load_contract(Path(arguments.contract).resolve())
    except PublicationError as error:
        print(json.dumps(error.payload(), indent=2), flush=True)
        print(f"error: {error.message}", file=sys.stderr)
        return error.exit_code

    if not (target / ".git").exists():
        payload = PublicationError(
            E_NOT_A_PUBLICATION,
            f"{target}: has no .git, so it is not a checkout of "
            f"{contract['publication']['repository']}",
            exit_code=2,
        )
        print(json.dumps(payload.payload(), indent=2), flush=True)
        print(f"error: {payload.message}", file=sys.stderr)
        return payload.exit_code

    target_power = target / str(contract["publication"]["powerDirectory"])
    # A sibling of the target, so the swap is a rename on one filesystem.
    staging = target_power.with_name(target_power.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)

    try:
        plan = plan_publication(power, staging, contract, arguments.expect_version)

        before = _tree_digest(target_power)
        after = _tree_digest(staging)
        changed = sorted(set(before) ^ set(after)) + sorted(
            path for path in set(before) & set(after) if before[path] != after[path]
        )

        payload = plan.to_json()
        payload["targetPower"] = str(target_power)
        payload["changedPaths"] = changed
        payload["wouldChange"] = bool(changed)
        payload["published"] = False

        if not arguments.check:
            publish(staging, target_power)
            payload["published"] = True

        report = json.dumps(payload, indent=2)
        print(report, flush=True)
        if arguments.report:
            Path(arguments.report).write_text(report + "\n", encoding="utf-8", newline="\n")

        for adaptation in plan.adaptations:
            print(f"  {adaptation.kind:13} {adaptation.path}  {adaptation.detail}", file=sys.stderr)
        print(
            f"\n{len(plan.adaptations)} adaptation(s); "
            f"{len(plan.digestsRecomputed)} digest(s) recomputed; "
            f"{plan.scannedForForbidden} file(s) scanned for development-repository references; "
            f"{len(changed)} path(s) differ from the target.",
            file=sys.stderr,
        )

        if arguments.check:
            print(
                "check only: nothing was written." if not changed else
                "check only: nothing was written, and publishing would change the target.",
                file=sys.stderr,
            )
            return 1 if changed else 0

        print(f"Published to {target_power}.", file=sys.stderr)
        return 0

    except PublicationError as error:
        print(json.dumps(error.payload(), indent=2), flush=True)
        print(f"error: {error.message}", file=sys.stderr)
        for finding in error.findings:
            print(f"  {finding}", file=sys.stderr)
        return error.exit_code
    finally:
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == "__main__":
    sys.exit(main())
