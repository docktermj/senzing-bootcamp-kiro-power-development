"""#26: the pinned parent release is named PARENT_VERSION / PARENT_COMMIT, and nothing else.

Three halves, because each can hold while the rule is broken:

* **One spelling.** No file names the recorded provenance by a retired name — this
  repository's own `templateRelease`, or the sibling's `UPSTREAM_VERSION` /
  `UPSTREAM_COMMIT` — except the records that predate the rename and the documents that
  explain it, each exempt by name with its reason.
* **The committed Power carries both values, and they agree.** `PARENT_VERSION` is a bare
  release tag equal to the Power version; `PARENT_COMMIT` is a full 40-hex SHA; the
  manifest mirrors both.
* **The non-tag guard still fires (R2).** The determinism workflow's own guard step is
  executed against `main`, `HEAD`, a `v`-prefixed tag and an abbreviated SHA, and must
  fail on each — the step itself, not a re-implementation of it. The resolver and the
  transform refuse the same values at their own entry points.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

import resolve_release
import transform

REPO = Path(__file__).resolve().parents[3]
POWER = REPO / "powers" / "senzing-bootcamp"
WORKFLOW = REPO / ".github" / "workflows" / "verify-build-determinism.yml"
SELF = Path(__file__).resolve()

#: The retired spellings of the recorded field (camel, snake, constant, and the
#: never-adopted commit name the old doc proposed).
RETIRED_FIELD = re.compile(r"templateRelease|template_release|TEMPLATE_RELEASE|templateCommit")
#: The sibling's names, rejected because "upstream" already means the Senzing MCP server.
REJECTED_UPSTREAM = re.compile(r"UPSTREAM_(?:VERSION|COMMIT)")

#: Files allowed to keep a retired spelling, each with why.
RETIRED_FIELD_EXEMPT = {
    "docs/test-records/0.5.1-validation.json": "evidence of a past validation run; not rewritten",
    "docs/test-records/0.5.3-validation.json": "evidence of a past validation run; not rewritten",
    "docs/provenance-convention.md": "records the rename and the name it replaced",
}
RETIRED_FIELD_EXEMPT_PREFIXES = (".kiro/specs/",)  # the frozen archive (KINV-014)
#: Files allowed to name UPSTREAM_*: the doc explaining the rejection, and the gate
#: that refuses a top-level file of that name.
UPSTREAM_EXEMPT = {
    "docs/provenance-convention.md",
    ".github/workflows/verify-build-determinism.yml",
}


def tracked_text_files() -> list[tuple[str, str]]:
    listed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split()
    found = []
    for name in listed:
        path = REPO / name
        if not path.is_file() or path.resolve() == SELF:
            continue
        try:
            found.append((name, path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return found


def test_no_file_names_the_provenance_by_a_retired_field_name() -> None:
    offenders = sorted(
        name
        for name, text in tracked_text_files()
        if RETIRED_FIELD.search(text)
        and name not in RETIRED_FIELD_EXEMPT
        and not name.startswith(RETIRED_FIELD_EXEMPT_PREFIXES)
    )
    assert offenders == [], (
        "the pinned parent release is PARENT_VERSION / PARENT_COMMIT (#26); these files "
        f"still spell it the old way: {offenders}"
    )


def test_no_file_names_it_upstream() -> None:
    offenders = sorted(
        name
        for name, text in tracked_text_files()
        if REJECTED_UPSTREAM.search(text) and name not in UPSTREAM_EXEMPT
    )
    assert offenders == [], (
        "UPSTREAM_VERSION / UPSTREAM_COMMIT were rejected: 'upstream' already means the "
        f"Senzing MCP server (docs/provenance-convention.md). Found in: {offenders}"
    )


def test_the_exemptions_are_still_needed() -> None:
    """An exemption that no longer matches anything is dead weight; remove it."""
    texts = dict(tracked_text_files())
    for name in RETIRED_FIELD_EXEMPT:
        assert name in texts and RETIRED_FIELD.search(texts[name]), name
    for name in UPSTREAM_EXEMPT:
        assert name in texts and REJECTED_UPSTREAM.search(texts[name]), name


def test_the_committed_power_records_both_and_they_agree() -> None:
    plugin = json.loads((POWER / "plugin.json").read_text(encoding="utf-8"))
    manifest = json.loads((POWER / ".build-manifest.json").read_text(encoding="utf-8"))
    block = plugin["extensions"][transform.EXTENSION_NAMESPACE]
    version = block[transform.PARENT_VERSION_FIELD]
    commit = block[transform.PARENT_COMMIT_FIELD]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
    assert resolve_release.is_commit(commit), commit
    assert plugin["version"] == version
    assert manifest[transform.PARENT_VERSION_FIELD] == version
    assert manifest[transform.PARENT_COMMIT_FIELD] == commit
    assert transform.PARENT_VERSION_FIELD not in plugin, "no top-level provenance field"


# --- the non-tag guard (R2) ------------------------------------------------


def _guard_step() -> dict:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["rebuild-and-compare"]["steps"]
    matching = [step for step in steps if "exact release tag" in step.get("name", "")]
    assert len(matching) == 1, "the determinism workflow lost its PARENT_VERSION guard step"
    return matching[0]


def _run_guard(version: str, commit: str) -> int:
    step = _guard_step()
    env = dict(os.environ, PINNED_VERSION=version, PINNED_COMMIT=commit)
    return subprocess.run(
        ["bash", "-c", step["run"]], env=env, capture_output=True, text=True
    ).returncode


GOOD_SHA = "d3d99523f88957cd9dda2d29375892bf2c557663"


@pytest.mark.skipif(shutil.which("bash") is None, reason="the workflow step is bash")
def test_the_workflow_guard_accepts_a_tag_and_a_full_sha() -> None:
    assert _run_guard("0.6.1", GOOD_SHA) == 0


@pytest.mark.skipif(shutil.which("bash") is None, reason="the workflow step is bash")
@pytest.mark.parametrize(
    "version,commit",
    [
        ("main", GOOD_SHA),
        ("HEAD", GOOD_SHA),
        ("v0.6.1", GOOD_SHA),
        ("0.6", GOOD_SHA),
        ("", GOOD_SHA),
        ("0.6.1", "d3d9952"),
        ("0.6.1", "main"),
        ("0.6.1", GOOD_SHA.upper()),
        ("0.6.1", ""),
    ],
)
def test_the_workflow_guard_rejects_a_non_tag_or_a_non_sha(version: str, commit: str) -> None:
    assert _run_guard(version, commit) != 0, (version, commit)


def test_the_workflow_rebuilds_with_the_recorded_commit_and_checks_the_tag_did_not_move() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '--commit "$PINNED_COMMIT"' in text
    assert '"$resolved_commit" != "$PINNED_COMMIT"' in text


@pytest.mark.parametrize("bad", ["main", "HEAD", "v0.6.1", "0.6"])
def test_the_resolver_refuses_a_non_tag(bad: str) -> None:
    with pytest.raises(Exception):
        resolve_release._semver_argument(bad)
    with pytest.raises(ValueError):
        resolve_release.tag_commit("Senzing/senzing-bootcamp-claude-plugin", bad, timeout=1)


@pytest.mark.parametrize("bad", ["main", "d3d9952", GOOD_SHA.upper(), GOOD_SHA + "0"])
def test_the_resolver_record_and_the_transform_refuse_a_non_sha(bad: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_release.resolved_release(
            "Senzing/x", {"tagName": "0.6.1"}, "plugins/x", tmp_path, 1, commit=bad
        )
    with pytest.raises(transform.TransformError):
        transform.build_plan(transform.load_contract(), tmp_path, tag="0.6.1", parent_commit=bad)
