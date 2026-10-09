#!/usr/bin/env python3
"""Release — record that a Bootcamp_Power version exists: gates, CHANGELOG, commit, tag.

    release.py <version>                  # dry run: print the plan, write nothing
    release.py <version> --apply          # verify, write CHANGELOG.md, commit, tag
               [--repo <path>] [--allow-branch] [--message <subject>]

The canonical family operation `release` (FAMILY_WORKFLOW R4, R8), ported from the
parent's `.claude/skills/release/release.py` and adapted to how a Kiro Power gets its
version. It touches **this repository only**: it never pushes, never propagates, and
never writes into the publication repository. `propagate-to-public` is the next step,
and pushing the branch and the tag is the Maintainer's.

Why there is no bump here
-------------------------
In the parent, `release` chooses the next version and rewrites every file that
asserts it. Here the version is not a free choice: the Bootcamp_Power's version is
the Template_Release tag it was built from, by construction (R2 AC5), and the files
asserting it are generated output that the determinism gate requires to equal a
fresh transform. So the bump has already happened, in `update-bootcamp-power` or
`create-bootcamp-power`, and a hand-edit of any version site would fail CI.

What `release` owns instead is the half the parent's tool exists for: **the version,
the changelog entry and the tag move together or not at all.** It verifies that every
version site agrees on the version named, enforces the tagging gate (R6), writes the
repository's release log, and tags the commit that writes it.

What it does, as one unit
-------------------------
1. Refuses unless the working tree is clean and HEAD is on `main`.
2. Reads every site in `VERSION_SITES` and refuses unless each states the version
   named on the command line. The version is never inferred: a release is a decision.
3. Refuses unless the version is newer than every existing tag and is not one.
4. Enforces the tagging gate for exactly that version: the ValidationReport at
   `docs/test-records/<version>-validation.json` reads `passed` with `tagAllowed`
   true, and the Test_Checklist record at `docs/test-records/<version>.md` opens the
   gate `testrecord.py check` computes.
5. Writes `CHANGELOG.md` at the repository root — creating it, seeded from the tags
   that already exist, on the first release — and commits that file and only that
   file.
6. Tags **that commit**, annotated. The commit comes first: tag before committing and
   the tag names the commit *before* the changelog entry.

A failure after the commit rolls back to the recorded HEAD and deletes the tag, so a
release is never left half-made. There is no flag that performs part of a release.

Dry run is the default and `--apply` is what writes, because git tags are
repository-global and, once anyone has fetched one, cannot be taken back.

Outcomes
--------
Exit 0 on a dry run whose plan is releasable, or on a completed release. Exit 1 on any
refusal, with nothing written. Exit 2 on contradictory arguments.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

# Run as a script, this file's directory is sys.path[0]; under pytest, pyproject's
# `pythonpath` puts it there. Either way the sibling engine module imports directly.
import testrecord

ENGINE_ROOT = Path(__file__).resolve().parent
#: tools/bootcamp-transform/release.py -> repository root
DEFAULT_REPO = ENGINE_ROOT.parent.parent

#: A release tag belongs on the branch every reader of a tag takes it from. A tag made
#: on a feature branch can name a commit `main` never contains.
RELEASE_BRANCH = "main"

CHANGELOG_NAME = "CHANGELOG.md"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

POWER_DIR = "powers/senzing-bootcamp"
PLUGIN_REL = f"{POWER_DIR}/plugin.json"
MANIFEST_REL = f"{POWER_DIR}/.build-manifest.json"
RECORDS_DIR = "docs/test-records"
EXTENSION_NAMESPACE = "com.senzing.bootcamp"


class Refusal(Exception):
    """A precondition the Maintainer has to resolve; reported, never a crash."""


# ---------------------------------------------------------------------------
# git plumbing
# ---------------------------------------------------------------------------


def git(repo: Path, *args: str, check: bool = True) -> tuple[str, int]:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    if check and done.returncode != 0:
        raise Refusal(
            "git %s failed: %s" % (" ".join(args), (done.stderr or done.stdout).strip())
        )
    return done.stdout.strip(), done.returncode


def semver(text: str | None) -> tuple[int, int, int] | None:
    match = SEMVER.match((text or "").strip())
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def tags_in_order(repo: Path) -> list[str]:
    """Every bare-semver tag, sorted numerically — 0.10.0 after 0.9.0, not before."""
    out, _ = git(repo, "tag", "--list")
    parsed = [(semver(tag), tag) for tag in out.splitlines() if semver(tag)]
    return [tag for _, tag in sorted(parsed)]


# ---------------------------------------------------------------------------
# Version sites
# ---------------------------------------------------------------------------
#
# Every place that asserts the version of a Bootcamp_Power release. Each reader takes
# the version under test (the record files are named by it) and returns what the site
# states. Release reads them and never rewrites them: the first three are generated
# output under the determinism gate, and the last three are written by the tools that
# own them (`validate.py`, `testrecord.py emit`, and the Maintainer working the
# checklist).


def _json(repo: Path, relative: str) -> dict:
    path = repo / relative
    if not path.is_file():
        raise Refusal(f"{relative} is missing")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise Refusal(f"{relative} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise Refusal(f"{relative} is not a JSON object")
    return document


def _plugin_version(repo: Path, _version: str) -> str:
    return str(_json(repo, PLUGIN_REL).get("version", ""))


def _plugin_template_release(repo: Path, _version: str) -> str:
    extensions = _json(repo, PLUGIN_REL).get("extensions") or {}
    return str((extensions.get(EXTENSION_NAMESPACE) or {}).get("templateRelease", ""))


def _manifest_template_release(repo: Path, _version: str) -> str:
    return str(_json(repo, MANIFEST_REL).get("templateRelease", ""))


def _validation_power_version(repo: Path, version: str) -> str:
    return str(_json(repo, f"{RECORDS_DIR}/{version}-validation.json").get("powerVersion", ""))


def _validation_template_release(repo: Path, version: str) -> str:
    return str(_json(repo, f"{RECORDS_DIR}/{version}-validation.json").get("templateRelease", ""))


def _record_version(repo: Path, version: str) -> str:
    return _read_record(repo, version).version


@dataclass(frozen=True)
class VersionSite:
    where: str
    read: Callable[[Path, str], str]
    why: str


VERSION_SITES: tuple[VersionSite, ...] = (
    VersionSite(
        f"{PLUGIN_REL} version",
        _plugin_version,
        "the version Kiro reports for the installed Power",
    ),
    VersionSite(
        f'{PLUGIN_REL} extensions["{EXTENSION_NAMESPACE}"].templateRelease',
        _plugin_template_release,
        "the provenance the update path compares against (KINV-002)",
    ),
    VersionSite(
        f"{MANIFEST_REL} templateRelease",
        _manifest_template_release,
        "the release the determinism gate rebuilds",
    ),
    VersionSite(
        f"{RECORDS_DIR}/<version>-validation.json powerVersion",
        _validation_power_version,
        "the ValidationReport half of the tagging gate",
    ),
    VersionSite(
        f"{RECORDS_DIR}/<version>-validation.json templateRelease",
        _validation_template_release,
        "the release that ValidationReport was produced against",
    ),
    VersionSite(
        f"{RECORDS_DIR}/<version>.md Version under test",
        _record_version,
        "the Test_Checklist half of the tagging gate",
    ),
)


def read_sites(repo: Path, version: str) -> list[tuple[VersionSite, str | None, str]]:
    """Every site's value, or `None` plus the reason it could not be read.

    A site that cannot be read is collected rather than raised, so one refusal names
    every disagreement at once instead of only the first missing file.
    """
    values: list[tuple[VersionSite, str | None, str]] = []
    for site in VERSION_SITES:
        try:
            values.append((site, site.read(repo, version), ""))
        except Refusal as unreadable:
            values.append((site, None, str(unreadable).splitlines()[0]))
    return values


def check_sites(repo: Path, version: str) -> None:
    disagreeing = [
        f"  {site.where}: {problem}"
        if value is None
        else f"  {site.where} states {value or '(nothing)'!r} — {site.why}"
        for site, value, problem in read_sites(repo, version)
        if value != version
    ]
    if disagreeing:
        raise Refusal(
            f"not every version site states {version}; releasing now would tag a tree "
            "that disagrees with itself. The generated sites move only by "
            "update-bootcamp-power or create-bootcamp-power, never by hand:\n"
            + "\n".join(disagreeing)
        )


# ---------------------------------------------------------------------------
# The tagging gate (R6)
# ---------------------------------------------------------------------------


def _read_record(repo: Path, version: str) -> testrecord.TestRecord:
    path = repo / RECORDS_DIR / f"{version}.md"
    if not path.is_file():
        raise Refusal(
            f"{RECORDS_DIR}/{version}.md is missing; emit it with "
            f"`testrecord.py emit --version {version}` and record every step"
        )
    try:
        return testrecord.read_record(path)
    except (testrecord.ChecklistError, testrecord.RecordError) as error:
        raise Refusal(f"{RECORDS_DIR}/{version}.md cannot be read: {error}") from error


def check_gate(repo: Path, version: str) -> None:
    report = _json(repo, f"{RECORDS_DIR}/{version}-validation.json")
    if report.get("status") != "passed" or report.get("tagAllowed") is not True:
        raise Refusal(
            f"{RECORDS_DIR}/{version}-validation.json reads status "
            f"{report.get('status')!r}, tagAllowed {report.get('tagAllowed')!r}; the "
            "Schema_Validator has not permitted tagging this version"
        )

    record = _read_record(repo, version)
    verdict = testrecord.evaluate(record, version=version)
    if not verdict.tag_allowed:
        shown = [f"  {finding.label}: {finding.message}" for finding in verdict.findings[:10]]
        more = len(verdict.findings) - len(shown)
        raise Refusal(
            f"the Test_Checklist record {RECORDS_DIR}/{version}.md does not permit "
            f"tagging ({len(verdict.findings)} finding(s)). An unrecorded step or "
            "platform cell is a fail, not a blank:\n"
            + "\n".join(shown)
            + (f"\n  … and {more} more" if more > 0 else "")
        )


# ---------------------------------------------------------------------------
# CHANGELOG.md — the release log, one entry per tag
# ---------------------------------------------------------------------------

CHANGELOG_HEADER = """\
# Changelog

Every released version of the Senzing Bootcamp Kiro Power, newest first. Each version
is the Senzing Bootcamp Claude plugin Template_Release it was built from, and each
entry here has a git tag of the same name, created with it.

Written by `tools/bootcamp-transform/release.py`. Do not hand-edit an entry's heading:
the version, this file and the tag are written together on purpose. This is the
repository's release log; the Power's own `powers/senzing-bootcamp/CHANGELOG.md` is the
per-update reconciliation record the update path writes, and neither file reaches the
publication repository.
"""

#: Version-anchored, not positional: "entries below" would turn false the release after
#: seeding, when a prepended entry lands between the note and what it describes.
SEED_NOTE = (
    "> Entries **%s and earlier** were reconstructed from git history when this file was\n"
    "> first created. They were not authored at release time, so they list commit subjects\n"
    "> rather than curated release notes.\n"
)


def subjects_between(repo: Path, start: str | None, end: str) -> list[str]:
    """Commit subjects in (start, end], merges excluded — they carry no content."""
    span = end if start is None else f"{start}..{end}"
    out, _ = git(repo, "log", "--no-merges", "--format=%s", span)
    return [line.strip() for line in out.splitlines() if line.strip()]


def tag_date(repo: Path, ref: str) -> str:
    """The commit date of what `ref` names: the existing tags here are lightweight."""
    out, _ = git(repo, "log", "-1", "--format=%ad", "--date=short", f"{ref}^{{commit}}")
    return out


def entry(version: str, date: str, bullets: Sequence[str]) -> str:
    lines = [f"## [{version}] - {date}", ""]
    lines.extend(f"- {bullet}" for bullet in bullets)
    lines.append("")
    return "\n".join(lines)


def seed_changelog(repo: Path, tags: Sequence[str]) -> str:
    """One entry per existing tag, newest first; the earliest is not itemized."""
    blocks = []
    for index, tag in enumerate(tags):
        if index == 0:
            bullets = ["Earliest tagged release; history before this tag is not itemized."]
        else:
            bullets = subjects_between(repo, tags[index - 1], tag) or [
                f"No non-merge commits recorded between {tags[index - 1]} and {tag}."
            ]
        blocks.append(entry(tag, tag_date(repo, tag), bullets))
    blocks.reverse()
    if not blocks:
        return CHANGELOG_HEADER
    return CHANGELOG_HEADER + "\n" + (SEED_NOTE % tags[-1]) + "\n" + "\n".join(blocks)


def plan_changelog(
    repo: Path, version: str, today: str, tags: Sequence[str]
) -> tuple[str, str, str]:
    """(old_text, new_text, entry_text) for CHANGELOG.md, creating it if absent."""
    path = repo / CHANGELOG_NAME
    latest = tags[-1] if tags else None
    bullets = [
        f"Built from Senzing Bootcamp Claude plugin Template_Release {version}; "
        f"validation and Test_Checklist recorded under `{RECORDS_DIR}/{version}*`."
    ]
    bullets += subjects_between(repo, latest, "HEAD") or [
        f"No non-merge commits since {latest or 'the start of history'}."
    ]
    block = entry(version, today, bullets)
    if path.is_file():
        old_text = path.read_text(encoding="utf-8")
        base = old_text
    else:
        old_text = ""
        base = seed_changelog(repo, tags)
    head, separator, rest = base.partition("\n## ")
    if separator:
        new_text = head.rstrip("\n") + "\n\n" + block + "\n## " + rest
    else:
        new_text = base.rstrip("\n") + "\n\n" + block
    return old_text, new_text, block


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


def check_preconditions(repo: Path, allow_branch: bool) -> str:
    if not (repo / PLUGIN_REL).is_file():
        raise Refusal(
            f"{repo} does not look like the Kiro Power development repository: "
            f"{PLUGIN_REL} is missing. Refusing rather than releasing something else."
        )
    _, code = git(repo, "rev-parse", "--git-dir", check=False)
    if code != 0:
        raise Refusal(f"{repo} is not a git repository, so no tag can be created")
    dirty, _ = git(repo, "status", "--porcelain")
    if dirty:
        raise Refusal(
            "the working tree is dirty; refusing to release.\n"
            "The release commit must carry the changelog entry and nothing else, and the "
            "tag must name a tree whose gate files are committed. Commit or discard "
            "first:\n\n" + dirty
        )
    branch, _ = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != RELEASE_BRANCH and not allow_branch:
        raise Refusal(
            f"on branch {branch!r}, not {RELEASE_BRANCH!r}; refusing to tag.\n"
            f"A tag made here can name a commit {RELEASE_BRANCH} never contains. Merge "
            "first, or pass --allow-branch if you mean it."
        )
    return branch


def check_target(version: str, tags: Sequence[str]) -> None:
    if version in tags:
        raise Refusal(
            f"tag {version} already exists. Re-pointing a tag rewrites what anyone who "
            "fetched it already has; a new Template_Release is a new version."
        )
    if tags:
        newest = tags[-1]
        if semver(version) <= semver(newest):  # type: ignore[operator]
            raise Refusal(
                f"{version} does not advance past the newest tag {newest}; a release "
                "must be newer than every tag."
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DIFF_LINE_BUDGET = 60


def show_diff(relpath: str, old_text: str, new_text: str) -> None:
    lines = list(
        difflib.unified_diff(
            old_text.splitlines(True),
            new_text.splitlines(True),
            fromfile=f"a/{relpath}",
            tofile=f"b/{relpath}",
            n=1,
        )
    )
    if len(lines) > DIFF_LINE_BUDGET:
        elided = len(lines) - DIFF_LINE_BUDGET
        lines = lines[:DIFF_LINE_BUDGET] + [f"... ({elided} more diff lines)\n"]
    sys.stdout.write("".join(lines))
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the version sites and the tagging gate, write the CHANGELOG "
        "entry, commit and tag — as one operation. Dry run unless --apply is given."
    )
    parser.add_argument(
        "version",
        nargs="?",
        help="the version being released, which must equal the built Power's version",
    )
    parser.add_argument(
        "--apply", action="store_true", help="write, commit and tag (default: dry run)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="explicitly request the default: print the plan and change nothing",
    )
    parser.add_argument(
        "--repo",
        default=str(DEFAULT_REPO),
        help="repository to release (default: the repository this script lives in)",
    )
    parser.add_argument(
        "--allow-branch",
        action="store_true",
        help=f"tag from a branch other than {RELEASE_BRANCH}",
    )
    parser.add_argument(
        "--message", help="release commit subject (default: 'Release <version>')"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.apply and args.dry_run:
        print("refusing: --apply and --dry-run contradict each other", file=sys.stderr)
        return 2

    repo = Path(args.repo).resolve()
    try:
        branch = check_preconditions(repo, args.allow_branch)
        if not args.version:
            built = _plugin_version(repo, "")
            raise Refusal(
                f"name the version being released. The built Power states {built!r}; "
                "a release is a decision, so it is never inferred."
            )
        if semver(args.version) is None:
            raise Refusal(f"{args.version!r} is not a MAJOR.MINOR.PATCH version")
        version = args.version.strip()
        tags = tags_in_order(repo)
        check_target(version, tags)
        check_sites(repo, version)
        check_gate(repo, version)
        today = datetime.date.today().isoformat()
        changelog_old, changelog_new, block = plan_changelog(repo, version, today, tags)
        subject = args.message or f"Release {version}"
    except Refusal as refusal:
        print(f"refusing: {refusal}", file=sys.stderr)
        return 1

    print(f"Repository:   {repo}")
    print(f"Branch:       {branch}")
    print(f"Version:      {version}  (every version site agrees)")
    print(f"Newest tag:   {tags[-1] if tags else '(none)'}")
    print("Gate:         ValidationReport passed; Test_Checklist record permits tagging")
    print(
        "CHANGELOG:    "
        + (
            "prepend an entry"
            if changelog_old
            else f"CREATE, seeded from {len(tags)} existing tag(s)"
        )
    )
    print(f"Mode:         {'APPLY' if args.apply else 'dry run — nothing is written'}")
    print()
    show_diff(CHANGELOG_NAME, changelog_old, changelog_new)
    print("Then, as one unit:")
    print(f"  git add {CHANGELOG_NAME}")
    print(f"  git commit -m {subject!r}")
    print(f"  git tag -a {version} -m {subject!r}")
    print()

    if not args.apply:
        print("Dry run: nothing was written. Re-run with --apply to release.")
        return 0

    before, _ = git(repo, "rev-parse", "HEAD")
    try:
        (repo / CHANGELOG_NAME).write_text(changelog_new, encoding="utf-8", newline="\n")
        git(repo, "add", "--", CHANGELOG_NAME)
        git(repo, "commit", "--quiet", "-m", subject)
        git(repo, "tag", "-a", version, "-m", subject)
    except Refusal as refusal:
        # Roll all the way back rather than leave a half-release: a changelog entry
        # with no tag is the defect this operation exists to prevent. The tree was
        # verified clean above, so returning to the recorded commit discards only
        # what this run wrote.
        git(repo, "tag", "-d", version, check=False)
        git(repo, "reset", "--hard", before, check=False)
        print(
            f"refusing: {refusal}\n(rolled back to {before[:12]}; nothing was released)",
            file=sys.stderr,
        )
        return 1

    sha, _ = git(repo, "rev-parse", "HEAD")
    print(f"Released {version}")
    print(f"  commit {sha[:12]}  {subject}")
    print(f"  tag    {version} -> {sha[:12]}")
    print()
    print("Nothing was pushed. Next: propagate-to-public to mirror the Power into the")
    print("public working tree, then push this branch AND the tag (`git push` alone does")
    print("not send tags):")
    print(f"  git push origin {branch} {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
