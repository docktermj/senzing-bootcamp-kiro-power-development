"""Publisher tests — the development-to-publication adaptation path.

The Publisher is small, but the thing it protects is not: it is the only step
between a built Power and a public repository, and its failure mode is silent.
Every rule it applies is a literal find/replace or a key excision, so a rule
stops applying the moment the build rewords the line it was written against —
and if that goes unreported, the next release publishes the reference the rule
existed to remove. That is not hypothetical: it is exactly how release 0.5.3
shipped a `later porting phase` aside, when a `catalogue`/`catalog` spelling
change took a Transformation_Contract substitution from applying to matching
nothing without failing anything.

So the tests here are weighted toward the negative cases. A test that the
Publisher rewrites a file it was told to rewrite is worth little; the tests that
matter are the ones proving it *refuses* when a rule has gone inert, when a
forbidden string survives, and when the manifest and the tree disagree.

Sections:
1. Byte-preserving JSON member excision ......... drop_pointer
2. Rules that match nothing are errors ......... E_RULE_INERT, E_SUBSTITUTION_UNAPPLIED
3. The forbidden-reference invariant ........... E_FORBIDDEN_REFERENCE
4. Manifest agreement .......................... E_MANIFEST_INCOMPLETE
5. Version pinning and Power shape ............. E_VERSION_MISMATCH, E_NOT_A_POWER
6. Publication is a swap ....................... publish()
7. The committed contract against the committed Power
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from publish import (
    E_FORBIDDEN_REFERENCE,
    E_MANIFEST_INCOMPLETE,
    E_NOT_A_POWER,
    E_RULE_INERT,
    E_SUBSTITUTION_UNAPPLIED,
    E_VERSION_MISMATCH,
    PublicationError,
    adapt_text,
    drop_pointer,
    forbidden_findings,
    load_contract,
    plan_publication,
    publish,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_CONTRACT = REPO_ROOT / "tools" / "bootcamp-transform" / "publication.yaml"
COMMITTED_POWER = REPO_ROOT / "powers" / "senzing-bootcamp"


# ===========================================================================
# Helpers
# ===========================================================================


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _minimal_power(root: Path, *, extensions: bool = True, extra: dict[str, str] | None = None) -> Path:
    """A Power with the shape the Publisher requires and nothing more.

    Hand-written rather than generated, because `plugin.json`'s *layout* is part
    of what the excision test asserts: `author` and `keywords` sit on one line
    each, exactly as the build's Jinja template renders them, and a serializer
    would not reproduce that.
    """
    root.mkdir(parents=True)
    plugin = """{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "senzing-bootcamp",
  "version": "0.5.3",
  "author": { "name": "Senzing", "url": "https://senzing.com" },
  "keywords": ["senzing", "entity-resolution"]"""
    if extensions:
        plugin += """,
  "extensions": {
    "com.senzing.bootcamp": {
      "templateRelease": "0.5.3"
    }
  }
}
"""
    else:
        plugin += "\n}\n"
    (root / "plugin.json").write_text(plugin, encoding="utf-8", newline="")
    (root / "mcp.json").write_text('{"$schema": "x", "mcpServers": {}}\n', encoding="utf-8", newline="")
    (root / "CHANGELOG.md").write_text("## 0.5.3\n", encoding="utf-8", newline="")
    (root / "note.md").write_text("built from tools/bootcamp-transform/contract.yaml\n", encoding="utf-8", newline="")
    for relative, body in (extra or {}).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8", newline="")

    recorded = ["plugin.json", "mcp.json", "note.md", *(extra or {})]
    manifest = {
        "manifestVersion": 1,
        "templateRelease": "0.5.3",
        "files": [
            {"path": name, "ruleId": "test", "owner": "template", "sha256": _digest(root / name)}
            for name in recorded
        ],
    }
    (root / ".build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline=""
    )
    return root


def _contract(**overrides) -> dict:
    contract = {
        "publicationContractVersion": 1,
        "publication": {"repository": "Senzing/x", "powerDirectory": "senzing-bootcamp"},
        "exclude": [{"path": "CHANGELOG.md", "reason": "maintainer record"}],
        "dropKeys": [{"path": "plugin.json", "pointer": "/extensions", "reason": "unread provenance"}],
        "substitutions": [
            {
                "id": "contract-path",
                "reason": "names a path only the build repository has",
                "find": "tools/bootcamp-transform/contract.yaml",
                "replace": "the transformation contract",
                "appliesTo": ["note.md"],
            }
        ],
        "forbidden": [{"needle": "tools/bootcamp-transform", "why": "development-repository path"}],
    }
    contract.update(overrides)
    return contract


# ===========================================================================
# 1. Byte-preserving JSON member excision
# ===========================================================================


def test_excision_removes_only_the_named_member_and_leaves_every_other_byte(tmp_path):
    """The build's hand-written layout survives; only `extensions` goes.

    This is the whole reason the excision is textual. A parse-and-reserialize
    would expand `author` and `keywords` onto multiple lines, and the published
    `plugin.json` would differ from the built one in lines that have nothing to
    do with the rule — each of them a digest change for a reviewer to explain.
    """
    power = _minimal_power(tmp_path / "power")
    original = (power / "plugin.json").read_text(encoding="utf-8")

    result, dropped = drop_pointer(original, "/extensions")

    assert dropped
    assert "extensions" not in result
    assert '"author": { "name": "Senzing", "url": "https://senzing.com" },' in result
    assert '"keywords": ["senzing", "entity-resolution"]' in result
    # The member before the excised one loses its trailing comma and keeps its line.
    assert result.endswith('"keywords": ["senzing", "entity-resolution"]\n}\n')
    assert json.loads(result) == {
        key: value for key, value in json.loads(original).items() if key != "extensions"
    }


def test_excision_reports_an_absent_member_rather_than_inventing_a_change():
    text = '{\n  "name": "x"\n}\n'
    result, dropped = drop_pointer(text, "/extensions")
    assert not dropped
    assert result == text


@pytest.mark.parametrize(
    "text,expected",
    [
        # Not the last member: the member and its comma go, and the line with them.
        ('{\n  "a": 1,\n  "gone": 2,\n  "b": 3\n}\n', {"a": 1, "b": 3}),
        # The last member: the comma joining it to the previous one goes too.
        ('{\n  "a": 1,\n  "gone": 2\n}\n', {"a": 1}),
        # The only member: the object is left empty and still parses.
        ('{\n  "gone": 2\n}\n', {}),
        # A nested value, so the brace counter has to do real work.
        ('{\n  "a": 1,\n  "gone": {"k": [1, {"j": 2}]},\n  "b": 3\n}\n', {"a": 1, "b": 3}),
    ],
)
def test_excision_handles_every_comma_position(text, expected):
    result, dropped = drop_pointer(text, "/gone")
    assert dropped
    assert json.loads(result) == expected


def test_excision_is_not_fooled_by_a_brace_or_the_key_name_inside_a_string():
    """A string value that contains braces, and the key's own name, is not markup."""
    text = '{\n  "a": "a } brace and the word gone",\n  "gone": {"k": "}"},\n  "b": 2\n}\n'
    result, dropped = drop_pointer(text, "/gone")
    assert dropped
    assert json.loads(result) == {"a": "a } brace and the word gone", "b": 2}


def test_excision_refuses_a_pointer_deeper_than_the_root():
    """No rule needs one, so the tool does not guess at semantics for it."""
    with pytest.raises(ValueError, match="single root-level key"):
        drop_pointer('{\n  "a": {"b": 1}\n}\n', "/a/b")


# ===========================================================================
# 2. Rules that match nothing are errors
# ===========================================================================


def test_a_substitution_whose_find_string_is_gone_stops_the_publication(tmp_path):
    """The 0.5.3 `catalogue`/`catalog` failure, reproduced at the publication layer.

    A build reword takes the rule from applying to matching nothing. If that
    passed quietly the tree would publish with the reference still in it, which
    is the one outcome the forbidden list exists to prevent. So it is an error,
    and the error names the rule and the file.
    """
    power = _minimal_power(tmp_path / "power")
    (power / "note.md").write_text("built from tools/bootcamp-transform/contract.yml\n", encoding="utf-8", newline="")
    manifest = json.loads((power / ".build-manifest.json").read_text())
    for entry in manifest["files"]:
        if entry["path"] == "note.md":
            entry["sha256"] = _digest(power / "note.md")
    (power / ".build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="")

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", _contract(), None)

    assert caught.value.code == E_SUBSTITUTION_UNAPPLIED
    assert any("contract-path" in finding and "note.md" in finding for finding in caught.value.findings)


def test_a_substitution_naming_a_file_the_build_no_longer_ships_stops_the_publication(tmp_path):
    power = _minimal_power(tmp_path / "power")
    contract = _contract()
    contract["substitutions"][0]["appliesTo"] = ["note.md", "vanished.md"]

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", contract, None)

    assert caught.value.code == E_SUBSTITUTION_UNAPPLIED
    assert any("vanished.md" in finding for finding in caught.value.findings)


def test_an_exclude_rule_for_a_file_the_build_stopped_producing_stops_the_publication(tmp_path):
    """R5 AC8 requires the changelog. Its absence is a build regression, not a tidy tree."""
    power = _minimal_power(tmp_path / "power")
    (power / "CHANGELOG.md").unlink()

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", _contract(), None)

    assert caught.value.code == E_RULE_INERT
    assert any("CHANGELOG.md" in finding for finding in caught.value.findings)


def test_a_dropkeys_rule_whose_pointer_is_already_absent_stops_the_publication(tmp_path):
    """The end state is right, and the rule is still a lie about what it did.

    An inert rule left in place is indistinguishable from a rule that stopped
    working, so the contract is made to say what the build actually emits.
    """
    power = _minimal_power(tmp_path / "power", extensions=False)

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", _contract(), None)

    assert caught.value.code == E_RULE_INERT
    assert any("/extensions" in finding for finding in caught.value.findings)


# ===========================================================================
# 3. The forbidden-reference invariant
# ===========================================================================


def test_a_forbidden_string_no_rule_covers_stops_the_publication(tmp_path):
    """The invariant is checked from the other end, independently of the rules.

    This is the test that makes the rule list non-load-bearing for safety. A new
    release can introduce a development-repository reference in a file no
    substitution mentions, and the publication still refuses.
    """
    power = _minimal_power(
        tmp_path / "power",
        extra={"skills/new/SKILL.md": "see tools/bootcamp-transform/publication.yaml\n"},
    )

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", _contract(), None)

    assert caught.value.code == E_FORBIDDEN_REFERENCE
    assert any("skills/new/SKILL.md:1" in finding for finding in caught.value.findings)


def test_the_forbidden_scan_reports_a_line_number_for_every_hit():
    body = "clean\nnames tools/bootcamp-transform here\nclean\nand tools/bootcamp-transform again\n"
    findings = forbidden_findings("f.md", body, [{"needle": "tools/bootcamp-transform", "why": "dev path"}], [])
    assert [finding.split(":")[1] for finding in findings] == ["2", "4"]
    assert all("dev path" in finding for finding in findings)


def test_an_allowlist_with_no_needles_exempts_nothing(tmp_path):
    """A reserved decision is not a hole. The file is still scanned."""
    power = _minimal_power(tmp_path / "power")
    contract = _contract(forbiddenAllowlist=[{"path": "note.md", "needles": [], "reason": "reserved"}])
    contract["substitutions"] = []

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", contract, None)

    assert caught.value.code == E_FORBIDDEN_REFERENCE


def test_a_binary_asset_is_reported_as_unscanned_rather_than_counted_as_clean(tmp_path):
    """An unreadable file is not a passing file, and the report says which it was."""
    power = _minimal_power(tmp_path / "power", extra={"docs/logo.png": ""})
    (power / "docs" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe binary")
    manifest = json.loads((power / ".build-manifest.json").read_text())
    for entry in manifest["files"]:
        if entry["path"] == "docs/logo.png":
            entry["sha256"] = _digest(power / "docs" / "logo.png")
    (power / ".build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="")

    plan = plan_publication(power, tmp_path / "staging", _contract(), None)

    assert "docs/logo.png" in plan.undecodableSkipped
    assert plan.scannedForForbidden >= 1


# ===========================================================================
# 4. Manifest agreement
# ===========================================================================


def test_an_adapted_file_gets_its_digest_recomputed_and_nothing_else_does(tmp_path):
    power = _minimal_power(tmp_path / "power")

    plan = plan_publication(power, tmp_path / "staging", _contract(), None)

    assert sorted(plan.digestsRecomputed) == ["note.md", "plugin.json"]
    assert plan.excluded == ["CHANGELOG.md"]
    staged_manifest = json.loads((tmp_path / "staging" / ".build-manifest.json").read_text())
    for entry in staged_manifest["files"]:
        assert entry["sha256"] == _digest(tmp_path / "staging" / entry["path"])
    # Every field other than the digest survives, key order included.
    assert [entry["ruleId"] for entry in staged_manifest["files"]] == ["test"] * len(staged_manifest["files"])
    assert list(staged_manifest) == ["manifestVersion", "templateRelease", "files"]


def test_an_excluded_file_recorded_in_the_manifest_loses_its_entry_too(tmp_path):
    """Otherwise the publication repository's drift check reports it as missing."""
    power = _minimal_power(tmp_path / "power")
    manifest = json.loads((power / ".build-manifest.json").read_text())
    manifest["files"].append(
        {"path": "CHANGELOG.md", "ruleId": "changelog", "owner": "kiro", "sha256": _digest(power / "CHANGELOG.md")}
    )
    (power / ".build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="")

    plan = plan_publication(power, tmp_path / "staging", _contract(), None)

    assert plan.manifestEntriesDropped == ["CHANGELOG.md"]
    staged = json.loads((tmp_path / "staging" / ".build-manifest.json").read_text())
    assert "CHANGELOG.md" not in {entry["path"] for entry in staged["files"]}


def test_a_shipped_file_the_manifest_does_not_record_stops_the_publication(tmp_path):
    """The same check the publication repository runs, run before the PR is opened."""
    power = _minimal_power(tmp_path / "power")
    (power / "unrecorded.md").write_text("orphan\n", encoding="utf-8", newline="")

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", _contract(), None)

    assert caught.value.code == E_MANIFEST_INCOMPLETE
    assert any("unrecorded.md" in finding for finding in caught.value.findings)


# ===========================================================================
# 5. Version pinning and Power shape
# ===========================================================================


def test_the_expected_version_is_a_refusal_and_not_a_warning(tmp_path):
    """Publishing the wrong version is the one mistake nothing downstream catches."""
    power = _minimal_power(tmp_path / "power")

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", _contract(), "0.5.4")

    assert caught.value.code == E_VERSION_MISMATCH
    assert not (tmp_path / "staging").exists()


def test_a_directory_that_is_not_a_built_power_is_refused_before_anything_is_staged(tmp_path):
    power = tmp_path / "power"
    power.mkdir()
    (power / "plugin.json").write_text("{}\n", encoding="utf-8", newline="")

    with pytest.raises(PublicationError) as caught:
        plan_publication(power, tmp_path / "staging", _contract(), None)

    assert caught.value.code == E_NOT_A_POWER
    assert caught.value.exit_code == 2


# ===========================================================================
# 6. Publication is a swap
# ===========================================================================


def test_the_swap_replaces_the_target_wholly_and_touches_nothing_beside_it(tmp_path):
    """The publication repository's own root files are its own."""
    target = tmp_path / "publication"
    (target / "senzing-bootcamp").mkdir(parents=True)
    (target / "senzing-bootcamp" / "stale.md").write_text("old\n", encoding="utf-8", newline="")
    (target / "README.md").write_text("theirs\n", encoding="utf-8", newline="")
    (target / "CHANGELOG.md").write_text("theirs\n", encoding="utf-8", newline="")

    staging = target / "senzing-bootcamp.staging"
    staging.mkdir()
    (staging / "fresh.md").write_text("new\n", encoding="utf-8", newline="")

    publish(staging, target / "senzing-bootcamp")

    assert (target / "senzing-bootcamp" / "fresh.md").read_text() == "new\n"
    assert not (target / "senzing-bootcamp" / "stale.md").exists()
    assert (target / "README.md").read_text() == "theirs\n"
    assert (target / "CHANGELOG.md").read_text() == "theirs\n"
    assert not staging.exists()


def test_adapt_text_replaces_every_occurrence_and_counts_them():
    body, count = adapt_text("a X b X c", "X", "Y")
    assert (body, count) == ("a Y b Y c", 2)
    assert adapt_text("nothing here", "X", "Y") == ("nothing here", 0)


def test_adapt_text_is_literal_and_not_a_regular_expression():
    """The needles are prose and JSON fragments; a regex would mis-read both."""
    body, count = adapt_text("keep a.c", "a.c", "Z")
    assert (body, count) == ("keep Z", 1)
    assert adapt_text("keep abc", "a.c", "Z") == ("keep abc", 0)


# ===========================================================================
# 7. The committed contract against the committed Power
# ===========================================================================
#
# The tests above prove the machinery. These two prove the artifact: that the
# contract as committed still applies to the Power as committed. They are the
# ones that fail on the release where an adaptation goes stale, which is the
# release where it matters.


def test_the_committed_contract_applies_cleanly_to_the_committed_power(tmp_path):
    contract = load_contract(COMMITTED_CONTRACT)

    plan = plan_publication(COMMITTED_POWER, tmp_path / "staging", contract, None)

    assert plan.excluded == ["CHANGELOG.md"]
    assert {adaptation.kind for adaptation in plan.adaptations} == {"exclude", "dropKeys", "substitution"}
    # Every substitution rule applied to every file it declares.
    declared = sum(len(rule["appliesTo"]) for rule in contract["substitutions"])
    applied = [adaptation for adaptation in plan.adaptations if adaptation.kind == "substitution"]
    assert len(applied) == declared


def test_the_published_power_names_no_development_repository_path(tmp_path):
    """The invariant itself, over the real tree, stated as its own assertion."""
    contract = load_contract(COMMITTED_CONTRACT)
    staging = tmp_path / "staging"

    plan_publication(COMMITTED_POWER, staging, contract, None)

    needles = [rule["needle"] for rule in contract["forbidden"]]
    for path in staging.rglob("*"):
        if not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for needle in needles:
            assert needle not in body, f"{path.relative_to(staging)} names {needle!r}"


def test_the_committed_power_still_carries_what_every_rule_removes(tmp_path):
    """No rule is dead weight.

    If the build stops emitting something a rule removes, the rule must go too —
    and until it does, the tests say so here rather than the next release
    discovering it. `plan_publication` enforces this as E_RULE_INERT; this test
    states it about the committed pair directly, so the reason a rule exists is
    written down beside the rule.
    """
    contract = load_contract(COMMITTED_CONTRACT)

    for rule in contract["exclude"]:
        assert (COMMITTED_POWER / rule["path"]).is_file(), f"exclude {rule['path']} is inert"

    for rule in contract["dropKeys"]:
        document = json.loads((COMMITTED_POWER / rule["path"]).read_text(encoding="utf-8"))
        assert rule["pointer"].lstrip("/") in document, f"dropKeys {rule['pointer']} is inert"

    for rule in contract["substitutions"]:
        for relative in rule["appliesTo"]:
            body = (COMMITTED_POWER / relative).read_text(encoding="utf-8")
            assert rule["find"] in body, f"substitution {rule['id']} is inert in {relative}"
