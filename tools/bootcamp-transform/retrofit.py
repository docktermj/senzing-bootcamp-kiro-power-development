#!/usr/bin/env python3
"""Retrofit — report how the public repository diverged from what was propagated.

    retrofit.py --public <checkout of Senzing/senzing-bootcamp-kiro-power>
                [--base <tag>]          # default: the public checkout's newest semver tag
                [--contract tools/bootcamp-transform/publication.yaml]
                [--diff-lines <n>]      # per-path diff budget in the report (default 80)

The canonical family operation `retrofit-from-public` (FAMILY_WORKFLOW R4, R6), the
inverse direction of `propagate-to-public`, ported from the parent's skill of the same
name. JSON goes to stdout; narration goes to stderr. The `retrofit-from-public` skill
reads the JSON, triages each item parent-bound or local, and files issues. This script
files nothing and decides nothing.

⛔ It writes nothing — into this repository, into the public checkout, or anywhere else
but a temporary directory it removes on every exit. Bytecode caching is switched off
before the sibling engine module is imported, so not even a `__pycache__/` lands here.
A change that arrives in a tree without an issue arrives without its reasoning, its
test run, and its invariant question; the parent applied retrofits directly once and
reversed that on purpose.

What it compares against
------------------------
Not this repository's current Power: work done here since the last propagation would
read as public edits. The baseline is **what was propagated**: the Power as committed at
the base tag, run through the Publication_Contract exactly as `propagate.py` runs it,
into a temporary directory. So a public checkout nobody edited reports nothing, and a
development self-reference the contract rewrites does not differ for that reason alone.

The default base is the public checkout's newest semver tag, which names the release it
last published. After a propagation is committed in public but before public is tagged,
that is still the previous release and the new one would read as public edits; name the
propagated tag with `--base` then.

The contract applied is the one in this checkout, not one recorded at the tag: the
Propagator did not exist when the earliest tags were cut. A base whose Power the current
contract refuses (an inert rule, a forbidden reference) aborts with the refusal, rather
than producing a baseline the release never had.

Only `<powerDirectory>/` is compared. Everything else in the public repository — its
README, CHANGELOG, workflows, `.github/` tooling — is public-owned and never propagated,
so a change there is not a divergence from this repository. The public commits since the
base are reported as context, each marked with whether it touched `<powerDirectory>/`.

What it reports per path
------------------------
`status` (`modified`, `only-in-public`, `absent-from-public`), the base build's manifest
triple (`ruleId`, `owner`, `sourcePath`) naming where the file is produced, whether the
contract adapts it at propagation, a `suggestedHome` with its reason, and a bounded
unified diff from the baseline to public for text files.

The suggested home is evidence, not the verdict. `owner: kiro` and generated manifests
are produced here, so their changes are local; `owner: template` content is ported from
the parent, so a change to it is presumptively parent-bound — but a template file is
also rewritten by Kiro substitution sets, and a change inside substituted text is local.
Only reading the diff against the source tells the two apart, which is the skill's step.

Outcomes
--------
Exit 0 with a report (whether or not anything diverged); 1 when no usable baseline can be
built; 2 when the public checkout is not one, or its `origin` is another repository.
"""

from __future__ import annotations

import sys

# Before any sibling import: a write-nothing operation does not leave bytecode behind.
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import difflib  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import tarfile  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Sequence  # noqa: E402

import propagate  # noqa: E402

ENGINE_ROOT = Path(__file__).resolve().parent
#: tools/bootcamp-transform/retrofit.py -> repository root
DEFAULT_REPO = ENGINE_ROOT.parent.parent
POWER_REL = "powers/senzing-bootcamp"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
DEFAULT_DIFF_LINES = 80

#: Documents the build generates from engine templates rather than porting.
GENERATED = {"plugin.json", "mcp.json", propagate.MANIFEST_FILENAME}


class RetrofitError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 1):
        super().__init__(message)
        self.code, self.message, self.exit_code = code, message, exit_code


def _git(repo: Path, *args: str, binary: bool = False):
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if done.returncode != 0:
        raise RetrofitError(
            "E_GIT", f"git {' '.join(args)} in {repo} failed: "
            + done.stderr.decode("utf-8", "replace").strip()
        )
    return done.stdout if binary else done.stdout.decode("utf-8").strip()


def newest_semver_tag(repo: Path) -> str | None:
    tags = [t for t in _git(repo, "tag", "--list").splitlines() if SEMVER.match(t)]
    return max(tags, key=lambda t: tuple(int(p) for p in t.split("."))) if tags else None


def _digests(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        str(rel): hashlib.sha256((root / rel).read_bytes()).hexdigest()
        for rel in propagate.shipped_files(root)
    }


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return None


def _diff(rel: str, before: Path, after: Path, budget: int) -> list[str] | None:
    old, new = _text(before), _text(after)
    if (before.exists() and old is None) or (after.exists() and new is None):
        return None  # binary on either side: the hash is the whole comparison
    lines = list(
        difflib.unified_diff(
            (old or "").splitlines(), (new or "").splitlines(),
            fromfile=f"propagated/{rel}", tofile=f"public/{rel}", lineterm="", n=2,
        )
    )
    if len(lines) > budget:
        lines = lines[:budget] + [f"... ({len(lines) - budget} more diff lines)"]
    return lines


def suggested_home(rel: str, record: dict | None, adapted: bool) -> tuple[str, str]:
    """Where the change presumptively belongs, and why. Evidence, not the verdict."""
    if rel in GENERATED:
        return "local", "generated by the engine from its own template, not ported"
    if record is None:
        return "unclear", (
            "not produced by the base build; new public content belongs to whichever "
            "home would produce it, which the diff has to show"
        )
    if record.get("owner") == "kiro":
        return "local", f"kiro-owned content authored here (rule {record.get('ruleId')})"
    reason = (
        f"ported from the parent's {record.get('sourcePath')} (rule {record.get('ruleId')}); "
        "parent-bound unless the change sits in text a Kiro substitution set wrote"
    )
    if adapted:
        reason += ", and the Publication_Contract also rewrites this file at propagation"
    return "parent-bound", reason


def build_baseline(repo: Path, tag: str, contract: dict, workdir: Path):
    """The propagated tree for `tag`, built under `workdir`, plus its manifest records."""
    try:
        _git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}")
    except RetrofitError as error:
        raise RetrofitError(
            "E_NO_BASELINE", f"this repository has no tag {tag!r}; pass --base <tag>"
        ) from error
    archive = _git(repo, "archive", "--format=tar", tag, POWER_REL, binary=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(workdir / "src", filter="data")
    power = workdir / "src" / POWER_REL
    staging = workdir / "propagated"
    try:
        plan = propagate.plan_publication(power, staging, contract, tag)
    except propagate.PublicationError as error:
        raise RetrofitError(
            "E_NO_BASELINE",
            f"the Publication_Contract refuses the Power at {tag} ({error.code}: "
            f"{error.message}); that is not a baseline the release had. Pass --base "
            "with the tag that was last propagated",
        ) from error
    manifest = json.loads((power / propagate.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    records = {entry["path"]: entry for entry in manifest.get("files", [])}
    adapted = {a.path for a in plan.adaptations if a.kind != "exclude"}
    return staging, records, adapted


def compare(repo: Path, public: Path, base: str | None, contract_path: Path, budget: int) -> dict:
    if not (public / ".git").exists():
        raise RetrofitError("E_NOT_A_PUBLICATION", f"{public}: has no .git", exit_code=2)
    contract = propagate.load_contract(contract_path)
    expected = str(contract["publication"]["repository"])
    actual = propagate.origin_slug(public)
    if actual is None or actual.lower() != expected.lower():
        raise RetrofitError(
            "E_NOT_A_PUBLICATION",
            f"{public}: its origin is {actual or 'not discoverable'}, not {expected}",
            exit_code=2,
        )
    power_dir = str(contract["publication"]["powerDirectory"])

    chosen = base or newest_semver_tag(public)
    how = "--base" if base else "the public checkout's newest semver tag"
    if not chosen:
        raise RetrofitError(
            "E_NO_BASELINE", "the public checkout has no semver tag; pass --base <tag>"
        )

    with tempfile.TemporaryDirectory(prefix="retrofit-") as tmp:
        baseline, records, adapted = build_baseline(repo, chosen, contract, Path(tmp))
        target = public / power_dir
        before, after = _digests(baseline), _digests(target)
        items = []
        for rel in sorted(set(before) | set(after)):
            if before.get(rel) == after.get(rel):
                continue
            status = (
                "modified" if rel in before and rel in after
                else "only-in-public" if rel in after
                else "absent-from-public"
            )
            record = records.get(rel)
            home, reason = suggested_home(rel, record, rel in adapted)
            items.append({
                "path": f"{power_dir}/{rel}",
                "status": status,
                "ruleId": (record or {}).get("ruleId"),
                "owner": (record or {}).get("owner"),
                "sourcePath": (record or {}).get("sourcePath"),
                "adaptedAtPropagation": rel in adapted,
                "suggestedHome": home,
                "reason": reason,
                "diff": _diff(rel, baseline / rel, target / rel, budget),
            })

    commits = []
    if _git(public, "tag", "--list", chosen):
        for line in _git(public, "log", "--format=%H%x09%s", f"{chosen}..HEAD").splitlines():
            sha, _, subject = line.partition("\t")
            touched = _git(public, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
            commits.append({
                "sha": sha[:12],
                "subject": subject,
                "touchesPower": any(p.startswith(power_dir + "/") for p in touched.splitlines()),
            })

    uncommitted = [
        line for line in _git(public, "status", "--porcelain").splitlines()
        if line[3:].startswith(power_dir + "/")
    ]
    return {
        "reportVersion": 1,
        "publicRepository": expected,
        "publicCheckout": str(public),
        "publicHead": _git(public, "rev-parse", "--short=12", "HEAD"),
        "base": chosen,
        "baseChosenBy": how,
        "powerDirectory": power_dir,
        "diverged": len(items),
        "items": items,
        "publicCommitsSinceBase": commits,
        "uncommittedInPowerDirectory": uncommitted,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--public", required=True, help="an existing checkout of the public repository")
    parser.add_argument("--base", help="the tag that was last propagated (default: public's newest semver tag)")
    parser.add_argument("--repo", default=str(DEFAULT_REPO), help="this development repository")
    parser.add_argument("--contract", default=str(propagate.DEFAULT_CONTRACT), help="the Publication_Contract")
    parser.add_argument("--diff-lines", type=int, default=DEFAULT_DIFF_LINES, help="per-path diff budget")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = compare(
            Path(args.repo).resolve(), Path(args.public).resolve(), args.base,
            Path(args.contract).resolve(), max(args.diff_lines, 0),
        )
    except (RetrofitError, propagate.PublicationError) as error:
        print(json.dumps({"reportVersion": 1, "error": error.code, "message": error.message}, indent=2))
        print(f"error: {error.message}", file=sys.stderr)
        return error.exit_code

    print(json.dumps(report, indent=2))
    print(
        f"compared {report['publicCheckout']}/{report['powerDirectory']} at "
        f"{report['publicHead']} against the propagated {report['base']} "
        f"({report['baseChosenBy']}): {report['diverged']} path(s) diverged, "
        f"{len(report['publicCommitsSinceBase'])} public commit(s) since the base. "
        "Nothing was written.",
        file=sys.stderr,
    )
    for item in report["items"]:
        print(f"  {item['status']:18} {item['suggestedHome']:12} {item['path']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
