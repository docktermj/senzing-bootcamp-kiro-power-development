"""Unit tests — specific examples and edge cases the properties do not carry.

Design Testing Strategy, layer 2. The property tests in `test_properties.py`
carry input coverage; this file covers the named examples the design lists as
uncovered by them, plus the edge cases that only make sense as one concrete
scenario.

Sections below are ordered by the task that owns them, so later tasks extend the
file by appending to their own section rather than editing another's:

1. Resolver timeout and error distinctness (R1 AC4, AC6) ....... task 2.3
2. License, provenance, and MCP translation (R4 AC4,
   R11 AC2, R14 AC3) .......................................... task 7.3
3. Invariant discount drift flagging (R15 AC10) ................ task 10.6
4. Optional-runtime absence (R16 AC7) .......................... task 11.9
5. Create/update orchestration edge cases (R4 AC5, AC6,
   R14 AC4, AC5) .............................................. task 12.5
6. The changelog is unrecorded, and only the changelog (R5 AC8,
   R16 AC9) ................................................... blocker 1
7. Naming a release instead of taking the maximum (R1 AC1, AC3,
   AC5) ....................................................... --tag
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from resolve_release import (
    E_NO_RELEASE,
    E_RESOLVE_FAILED,
    MAX_ATTEMPTS,
    RESOLUTION_BUDGET_SECONDS,
    ResolutionError,
    resolve,
)

# ===========================================================================
# 1. Resolver timeout and error distinctness (task 2.3) — R1 AC4, AC6
# ===========================================================================
#
# R1 AC6 fixes two numbers: 3 attempts and a 30 s budget. Both are simulated
# rather than waited out — `resolve()` takes `lister`, `fetcher`, `clock`, and
# `sleeper` injections, so these tests need no network and no wall clock, and a
# fully hanging query costs nothing to run.
#
# The design's `_Budget` gives each attempt `remaining / attempts_left`, so a
# query that hangs through its entire share still leaves room for the attempts
# after it: 10 s + 9.75 s + 9.25 s of attempts plus 2 x 0.5 s of backoff is
# exactly the 30 s budget, with 3 attempts made.


class FakeClock:
    """A monotonic clock that advances only when something spends time.

    Passed as `resolve(clock=...)`, so "the 30 s budget" is a fact about the
    simulated timeline rather than about how long pytest ran.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        assert seconds >= 0.0, "a monotonic clock never moves backward"
        self.now += seconds


class FakeSleeper:
    """A `sleeper` that spends its duration on the fake clock instead of waiting."""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.durations: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.durations.append(seconds)
        self._clock.advance(seconds)

    @property
    def total(self) -> float:
        return sum(self.durations)


class HangingLister:
    """A release query that never returns: each attempt burns its whole share.

    This is the R1 AC6 condition — "the release-resolution query does not return
    a result" — expressed as the timeout a real `gh` or HTTP call would raise
    once its per-attempt timeout elapsed.
    """

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.timeouts: list[float] = []

    def __call__(self, timeout: float) -> list[Mapping[str, Any]]:
        self.timeouts.append(timeout)
        self._clock.advance(timeout)
        raise TimeoutError(f"the release query did not return within {timeout:g}s")

    @property
    def attempts(self) -> int:
        return len(self.timeouts)


class SequenceLister:
    """A release query that hangs for the first `hangs` attempts, then returns."""

    def __init__(self, clock: FakeClock, *, hangs: int, records: Sequence[Mapping[str, Any]]) -> None:
        self._clock = clock
        self._hangs = hangs
        self._records = list(records)
        self.timeouts: list[float] = []

    def __call__(self, timeout: float) -> list[Mapping[str, Any]]:
        self.timeouts.append(timeout)
        if len(self.timeouts) <= self._hangs:
            self._clock.advance(timeout)
            raise TimeoutError(f"the release query did not return within {timeout:g}s")
        return list(self._records)

    @property
    def attempts(self) -> int:
        return len(self.timeouts)


class CountingFetcher:
    """A `fetcher` that records every call and materializes `tree` when asked.

    Both failure paths must produce no build artifact *(R1 AC4, AC6)*, so the
    assertion is `calls == 0` — not merely that the output directory ended up
    empty, which a fetch that failed cleanly would also satisfy.
    """

    def __init__(self, tree: Path | None = None) -> None:
        self._tree = tree
        self.calls = 0

    def __call__(self, timeout: float) -> Path:
        self.calls += 1
        if self._tree is None:  # pragma: no cover - asserted never to happen
            raise AssertionError("a failure path fetched a source tree")
        self._tree.mkdir(parents=True, exist_ok=True)
        return self._tree


#: Releases that come back from a query that *did* return, yet leave nothing
#: selectable: a draft and a prerelease. This is the R1 AC4 condition, and it is
#: what makes `E_NO_RELEASE` observably a different situation from a query that
#: never answered at all.
NO_ELIGIBLE_RELEASES: tuple[Mapping[str, Any], ...] = (
    {
        "tagName": "0.6.0",
        "isDraft": True,
        "isPrerelease": False,
        "publishedAt": "2025-01-02T00:00:00Z",
    },
    {
        "tagName": "0.5.2",
        "isDraft": False,
        "isPrerelease": True,
        "publishedAt": "2025-01-01T00:00:00Z",
    },
)

#: One selectable release, for the "the query eventually answered" case.
ELIGIBLE_RELEASES: tuple[Mapping[str, Any], ...] = (
    {
        "tagName": "0.5.1",
        "isDraft": False,
        "isPrerelease": False,
        "publishedAt": "2025-01-01T00:00:00Z",
    },
)


def _hanging_resolve(out_dir: Path) -> tuple[ResolutionError, HangingLister, CountingFetcher, FakeClock, FakeSleeper]:
    """Run `resolve` against a query that never returns *(R1 AC6)*."""
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    lister = HangingLister(clock)
    fetcher = CountingFetcher()
    with pytest.raises(ResolutionError) as raised:
        resolve(
            out_dir=out_dir,
            repository="Senzing/senzing-bootcamp-claude-plugin",
            lister=lister,
            fetcher=fetcher,
            clock=clock,
            sleeper=sleeper,
        )
    return raised.value, lister, fetcher, clock, sleeper


def _no_release_resolve(out_dir: Path) -> tuple[ResolutionError, SequenceLister, CountingFetcher]:
    """Run `resolve` against a query that returns with nothing eligible *(R1 AC4)*."""
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    lister = SequenceLister(clock, hangs=0, records=NO_ELIGIBLE_RELEASES)
    fetcher = CountingFetcher()
    with pytest.raises(ResolutionError) as raised:
        resolve(
            out_dir=out_dir,
            repository="Senzing/senzing-bootcamp-claude-plugin",
            lister=lister,
            fetcher=fetcher,
            clock=clock,
            sleeper=sleeper,
        )
    return raised.value, lister, fetcher


def test_hanging_query_makes_exactly_max_attempts(tmp_path: Path) -> None:
    """A query that never returns is attempted 3 times — not 2, not 4 *(R1 AC6)*."""
    error, lister, _fetcher, _clock, sleeper = _hanging_resolve(tmp_path)

    assert MAX_ATTEMPTS == 3, "R1 AC6 fixes the attempt count at 3"
    assert lister.attempts == MAX_ATTEMPTS
    # The reported count is the count actually made, so a Maintainer reading the
    # failure record sees the real number rather than the configured maximum.
    assert error.attempts == MAX_ATTEMPTS
    # Backoff sits *between* attempts, never after the last one.
    assert len(sleeper.durations) == MAX_ATTEMPTS - 1


def test_hanging_query_reports_resolve_failed(tmp_path: Path) -> None:
    """Attempt exhaustion is `E_RESOLVE_FAILED`, and says so *(R1 AC6)*."""
    error, _lister, _fetcher, _clock, _sleeper = _hanging_resolve(tmp_path)

    assert error.code == E_RESOLVE_FAILED
    assert "release resolution failed" in error.message
    payload = error.payload()
    assert payload["error"] == E_RESOLVE_FAILED
    assert payload["attempts"] == MAX_ATTEMPTS


def test_resolution_honors_the_thirty_second_budget(tmp_path: Path) -> None:
    """Three hanging attempts plus backoff fit inside 30 s *(R1 AC6)*.

    The budget is a ceiling on the whole resolution, not a per-attempt timeout,
    so the assertion is on the total simulated elapsed time. Each attempt still
    has to receive a usable share — a budget honored by handing out zero-second
    timeouts would satisfy the ceiling while making the retries meaningless.
    """
    error, lister, _fetcher, clock, sleeper = _hanging_resolve(tmp_path)

    assert RESOLUTION_BUDGET_SECONDS == 30.0, "R1 AC6 fixes the budget at 30 s"
    assert clock.now <= RESOLUTION_BUDGET_SECONDS + 1e-9, (
        f"resolution consumed {clock.now:g}s of the "
        f"{RESOLUTION_BUDGET_SECONDS:g}s budget"
    )
    # Every attempt got a positive share, and the shares plus the backoff are
    # what consumed the budget.
    assert len(lister.timeouts) == MAX_ATTEMPTS
    assert all(share > 0 for share in lister.timeouts)
    assert sum(lister.timeouts) + sleeper.total == pytest.approx(clock.now)
    assert error.code == E_RESOLVE_FAILED


def test_a_query_that_returns_on_the_final_attempt_resolves(tmp_path: Path) -> None:
    """The 3-attempt ceiling is a retry allowance, not a guaranteed failure.

    Two hanging attempts followed by an answer resolves normally and still fits
    the budget, which is what distinguishes "attempted 3 times" from "failed
    after 3 attempts" *(R1 AC6)*.
    """
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    lister = SequenceLister(clock, hangs=MAX_ATTEMPTS - 1, records=ELIGIBLE_RELEASES)
    fetcher = CountingFetcher(tmp_path / "bootcamp-src-0.5.1")

    record = resolve(
        out_dir=tmp_path,
        repository="Senzing/senzing-bootcamp-claude-plugin",
        lister=lister,
        fetcher=fetcher,
        clock=clock,
        sleeper=sleeper,
    )

    assert "error" not in record
    assert record["tag"] == "0.5.1"
    assert record["attempts"] == MAX_ATTEMPTS
    assert lister.attempts == MAX_ATTEMPTS
    assert fetcher.calls == 1
    assert clock.now <= RESOLUTION_BUDGET_SECONDS + 1e-9


def test_no_eligible_release_reports_no_release_on_the_first_attempt(
    tmp_path: Path,
) -> None:
    """A query that answers with nothing selectable is `E_NO_RELEASE` *(R1 AC4)*.

    It is reported after one attempt: retrying a question that was answered
    would not change the answer.
    """
    error, lister, _fetcher = _no_release_resolve(tmp_path)

    assert error.code == E_NO_RELEASE
    assert "no versioned release is available" in error.message
    assert lister.attempts == 1
    assert error.attempts == 1


def test_resolve_failed_and_no_release_are_distinct_codes_from_distinct_conditions(
    tmp_path: Path,
) -> None:
    """The two halting outcomes are separable, not one error wearing two names.

    R1 AC6 requires the resolution failure to be *distinct from* the
    no-release-available error, because the Maintainer response differs: retry
    versus wait for upstream to publish a release. The only difference between
    the two runs below is whether the query returned.
    """
    assert E_RESOLVE_FAILED != E_NO_RELEASE

    timed_out, _lister, _fetcher, _clock, _sleeper = _hanging_resolve(
        tmp_path / "timeout"
    )
    no_release, _lister2, _fetcher2 = _no_release_resolve(tmp_path / "no-release")

    assert timed_out.code == E_RESOLVE_FAILED
    assert no_release.code == E_NO_RELEASE
    assert timed_out.code != no_release.code
    assert timed_out.message != no_release.message
    # One field lookup separates them for a caller reading the JSON record.
    assert timed_out.payload()["error"] != no_release.payload()["error"]
    # And the attempt counts separate the conditions themselves: exhausted
    # retries versus a single answered query.
    assert timed_out.attempts == MAX_ATTEMPTS
    assert no_release.attempts == 1


@pytest.mark.parametrize("condition", ["timeout", "no-release"])
def test_neither_halting_outcome_produces_a_build_artifact(
    tmp_path: Path, condition: str
) -> None:
    """Both failures halt with nothing fetched and nothing written *(R1 AC4, AC6)*."""
    out_dir = tmp_path / condition
    out_dir.mkdir()

    if condition == "timeout":
        error, _lister, fetcher, _clock, _sleeper = _hanging_resolve(out_dir)
        expected = E_RESOLVE_FAILED
    else:
        error, _lister, fetcher = _no_release_resolve(out_dir)
        expected = E_NO_RELEASE

    assert error.code == expected
    assert fetcher.calls == 0, "a halting outcome fetched a source tree"
    assert list(out_dir.iterdir()) == [], "a halting outcome left output behind"

# ===========================================================================
# 2. License, provenance, and MCP translation (task 7.3)
#    — R4 AC4, R11 AC2, R14 AC3
# ===========================================================================
#
# Three claims about the two documents the contract *generates*, and none of them
# is a claim a property test can make: they are about **this** repository's
# license and **the** 0.5.1 template declaration, not about a generated family of
# inputs.
#
# Both documents are produced the way a build produces them — the real contract,
# the real `templates/*.j2`, `plan_destinations` choosing the destinations, and
# `render_output` choosing the bytes — so what is asserted below is what a Power
# would carry rather than what a template says in isolation. The source tree is
# two files: the two `generate` rules name two sources, and nothing else has to
# exist for those rules to fire.
#
# Nothing here touches the network. The 0.5.1 `.mcp.json` declaration is the
# fixture below, and the license comes off this repository's own root.

import json

from transform import (
    E_TRANSFORM_FAILED,
    EXTENSION_NAMESPACE,
    LICENSE_FILENAME,
    MCP_MANIFEST_DEST,
    MCP_SCHEMA_FIELD,
    MCP_SCHEMA_URL,
    MCP_TRANSPORT_TYPE,
    PLUGIN_MANIFEST_DEST,
    POWER_LICENSE,
    REPOSITORY_LICENSE,
    SENZING_MCP_URL,
    SENZING_SERVER_KEY,
    TEMPLATE_RELEASE_FIELD,
    TransformError,
    TransformPlan,
    build_plan,
    license_identifier,
    load_contract,
    plan_destinations,
    render_license,
    render_output,
    verify_mcp_document,
)

#: The resolved Template_Release these builds are against — the release the
#: design's template inventory was taken from.
GENERATED_TAG = "0.5.1"

#: The template source each `generate` rule supersedes.
TEMPLATE_MCP_SOURCE = ".mcp.json"
TEMPLATE_PLUGIN_SOURCE = ".claude-plugin/plugin.json"

#: The Senzing MCP declaration release 0.5.1 ships, as the design's template
#: inventory records it: transport `http`, and the URL the Power must carry
#: character-for-character. This is the *input* to the translation, so it is held
#: as the document itself rather than assembled from the engine's own constants —
#: a fixture built out of what the engine expects to produce could not disagree
#: with it, and disagreeing is the whole job of an input fixture.
TEMPLATE_TRANSPORT_TYPE = "http"
TEMPLATE_MCP_DOCUMENT = (
    "{\n"
    '  "mcpServers": {\n'
    '    "senzing": {\n'
    f'      "type": "{TEMPLATE_TRANSPORT_TYPE}",\n'
    f'      "url": "{SENZING_MCP_URL}",\n'
    '      "description": "Senzing entity resolution MCP server."\n'
    "    }\n"
    "  }\n"
    "}\n"
)

#: The template's own plugin manifest. It declares a *different* license and a
#: different name on purpose: `generate` supersedes its source entirely, so not
#: one of these bytes may reach the Power, and a fixture that agreed with the
#: expected output could not show that.
TEMPLATE_PLUGIN_LICENSE = "MIT"
TEMPLATE_PLUGIN_NAME = "senzing-bootcamp-claude"
TEMPLATE_PLUGIN_DOCUMENT = json.dumps(
    {
        "name": TEMPLATE_PLUGIN_NAME,
        "version": "0.4.9",
        "description": "Guided Senzing entity resolution bootcamp.",
        "license": TEMPLATE_PLUGIN_LICENSE,
    },
    indent=2,
)

#: A root license declaring something other than Apache-2.0. Only the heading
#: matters to `license_identifier`, which is what it reads.
FOREIGN_LICENSE_TEXT = (
    "MIT License\n"
    "\n"
    "Copyright (c) 2025 Senzing\n"
    "\n"
    "Permission is hereby granted, free of charge, to any person obtaining a\n"
    "copy of this software and associated documentation files.\n"
)

#: The generated documents plus the Power's own license — the outputs this
#: section is about. Everything else the plan produces is another task's subject.
_GENERATED_PATHS = (PLUGIN_MANIFEST_DEST, MCP_MANIFEST_DEST, LICENSE_FILENAME)


def _build_generated(
    tmp_path: Path, *, tag: str = GENERATED_TAG
) -> tuple[TransformPlan, dict[str, bytes]]:
    """Run the real contract over the two `generate` sources and render them.

    Returns the plan and the rendered bytes of `plugin.json`, `mcp.json`, and
    `LICENSE`, keyed by Power-relative path. Reading the origin bytes and handing
    them to `render_output` is what a build does; for a `generate` output they are
    read so the source is accounted for and then discarded.
    """
    contract = load_contract()
    source = tmp_path / "release"
    root = (
        source.joinpath(*contract.plugin_root.split("/"))
        if contract.plugin_root
        else source
    )
    for relative, text in (
        (TEMPLATE_MCP_SOURCE, TEMPLATE_MCP_DOCUMENT),
        (TEMPLATE_PLUGIN_SOURCE, TEMPLATE_PLUGIN_DOCUMENT),
    ):
        document = root / relative
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text(text, encoding="utf-8")

    plan = build_plan(contract, source, tag=tag)
    outputs, _unmaterialized = plan_destinations(plan)
    rendered = {
        output.path: render_output(output, output.origin.read_bytes(), plan)
        for output in outputs
        if output.path in _GENERATED_PATHS
    }
    assert set(rendered) == set(_GENERATED_PATHS), (
        "the build did not plan every generated document plus the Power's "
        f"license; it planned {sorted(rendered)}"
    )
    return plan, rendered


def test_the_power_declares_apache_2_0_and_ships_the_license_it_declares(
    tmp_path: Path,
) -> None:
    """`plugin.json.license` is Apache-2.0, and a `LICENSE` is there *(R4 AC4)*.

    Both halves, because either alone is a Power a Bootcamper cannot rely on: a
    declaration with no license text, or a license text nothing declares.
    """
    _plan, rendered = _build_generated(tmp_path)
    manifest = json.loads(rendered[PLUGIN_MANIFEST_DEST])

    assert manifest["license"] == "Apache-2.0" == POWER_LICENSE
    assert rendered[LICENSE_FILENAME].strip(), "the Power's LICENSE is empty"
    assert (
        license_identifier(rendered[LICENSE_FILENAME].decode("utf-8"))
        == manifest["license"]
    ), "the Power's LICENSE text is not the license its manifest declares"
    # The template declared something else, and none of it survived: the license
    # is a fact about the Power, not content ported from upstream.
    assert TEMPLATE_PLUGIN_LICENSE not in rendered[PLUGIN_MANIFEST_DEST].decode("utf-8")
    assert manifest["name"] != TEMPLATE_PLUGIN_NAME


def test_the_declared_license_is_the_one_this_repositorys_root_declares(
    tmp_path: Path,
) -> None:
    """One license text in this repository, and the Power carries it *(R14 AC3)*.

    Byte-for-byte rather than merely the same identifier: two Apache-2.0 texts
    that differ are still two licenses, and the Power's is a copy of the root's.
    """
    assert REPOSITORY_LICENSE.is_file(), (
        f"this repository has no root {LICENSE_FILENAME}, so the Power has "
        "nothing to match"
    )
    root_license = REPOSITORY_LICENSE.read_bytes()

    _plan, rendered = _build_generated(tmp_path)
    manifest = json.loads(rendered[PLUGIN_MANIFEST_DEST])

    assert license_identifier(root_license.decode("utf-8")) == POWER_LICENSE
    assert manifest["license"] == license_identifier(root_license.decode("utf-8"))
    assert rendered[LICENSE_FILENAME] == root_license


def test_a_root_license_declaring_another_identifier_halts_the_build() -> None:
    """The match is enforced, not restated *(R4 AC4, R14 AC3)*.

    Swap this repository's root license for a different one and the build stops,
    rather than shipping a Power whose `plugin.json` and whose `LICENSE`
    disagree. That is what makes the test above evidence instead of a tautology.
    """
    assert license_identifier(FOREIGN_LICENSE_TEXT) != POWER_LICENSE

    with pytest.raises(TransformError) as raised:
        render_license(FOREIGN_LICENSE_TEXT.encode("utf-8"))

    error = raised.value
    assert error.code == E_TRANSFORM_FAILED
    assert error.details["path"] == LICENSE_FILENAME
    assert error.details["declared"] == POWER_LICENSE
    assert error.details["found"] != POWER_LICENSE
    # The repository's own root license is accepted unchanged by the same call.
    assert render_license(REPOSITORY_LICENSE.read_bytes()) == REPOSITORY_LICENSE.read_bytes()


def test_the_real_0_5_1_declaration_is_translated_to_streamable_http(
    tmp_path: Path,
) -> None:
    """`{"type":"http"}` in, `{"type":"streamable-http"}` out *(R11 AC2)*.

    The template's URL survives character-for-character and its transport
    spelling does not survive at all, which is the translation R11 AC2 asks for:
    add `$schema`, keep the URL, rewrite the transport.
    """
    template = json.loads(TEMPLATE_MCP_DOCUMENT)["mcpServers"][SENZING_SERVER_KEY]
    assert template["type"] == TEMPLATE_TRANSPORT_TYPE, (
        "the fixture is not the 0.5.1 declaration"
    )

    _plan, rendered = _build_generated(tmp_path)
    text = rendered[MCP_MANIFEST_DEST].decode("utf-8")
    document = json.loads(text)
    server = document["mcpServers"][SENZING_SERVER_KEY]

    assert server["type"] == MCP_TRANSPORT_TYPE == "streamable-http"
    assert server["url"] == template["url"] == SENZING_MCP_URL
    assert document[MCP_SCHEMA_FIELD] == MCP_SCHEMA_URL
    # `streamable-http` is not `http`: the template's spelling reaches nothing,
    # and neither does the rest of the template's server entry.
    assert f'"{TEMPLATE_TRANSPORT_TYPE}"' not in text
    assert "description" not in server


def test_the_untranslated_template_declaration_would_not_pass(tmp_path: Path) -> None:
    """A Power carrying the template's own declaration is a fault *(R11 AC2)*.

    Two refusals, because the translation is two edits and each one is checked:
    the template document has no `$schema` *(R11 AC5)*, and the same document
    with a `$schema` added is still refused for its transport type *(R11 AC4)*.
    """
    plan, _rendered = _build_generated(tmp_path)

    with pytest.raises(TransformError) as missing_schema:
        verify_mcp_document(TEMPLATE_MCP_DOCUMENT.encode("utf-8"), plan)
    assert missing_schema.value.code == E_TRANSFORM_FAILED
    assert missing_schema.value.details["field"] == MCP_SCHEMA_FIELD

    half_translated = json.loads(TEMPLATE_MCP_DOCUMENT)
    half_translated[MCP_SCHEMA_FIELD] = MCP_SCHEMA_URL
    with pytest.raises(TransformError) as untranslated_transport:
        verify_mcp_document(json.dumps(half_translated).encode("utf-8"), plan)
    error = untranslated_transport.value
    assert error.code == E_TRANSFORM_FAILED
    assert error.details["path"] == MCP_MANIFEST_DEST
    assert error.details["declared"] == TEMPLATE_TRANSPORT_TYPE
    assert error.details["expected"] == MCP_TRANSPORT_TYPE


def test_the_resolved_tag_is_stamped_into_the_version_and_the_provenance(
    tmp_path: Path,
) -> None:
    """One tag, two places, character-for-character *(R2 AC1, AC2, AC5)*.

    The tag below carries a prerelease suffix a normalizer would be tempted to
    tidy, so "character-for-character" is observable rather than incidental. The
    provenance sits under `extensions["com.senzing.bootcamp"]` and nowhere else:
    the plugin schema's top-level field set is fixed, so a bare top-level
    `templateRelease` would record provenance where nothing reads it.
    """
    tag = "0.6.0-rc.1"
    _plan, rendered = _build_generated(tmp_path, tag=tag)
    manifest = json.loads(rendered[PLUGIN_MANIFEST_DEST])

    assert manifest["version"] == tag
    assert manifest["extensions"][EXTENSION_NAMESPACE][TEMPLATE_RELEASE_FIELD] == tag
    assert TEMPLATE_RELEASE_FIELD not in manifest
    # The template's own version is not the Power's.
    assert manifest["version"] != json.loads(TEMPLATE_PLUGIN_DOCUMENT)["version"]

# ===========================================================================
# 3. Invariant discount drift flagging (task 10.6) — R15 AC10
# ===========================================================================
#
# A discount is a judgment about one Template_Invariant's *text*: this wording
# conflicts with that Kiro mechanism, so this construction is implemented
# instead. Reword the invariant upstream and the judgment loses its subject, so
# the register entry is reopened — flagged in the reconciliation report for
# Maintainer re-evaluation rather than carried forward unexamined *(R15 AC10)*.
#
# The comparison is split, and so are these tests. `flag_invariant_drift` is
# pure: a register plus one `{invariant_id: text}` mapping per release in, a
# sorted tuple of `FlaggedDiscount` out, so most cases below run entirely in
# memory. `flag_release_invariant_drift` is the filesystem half — it locates and
# reads both mappings out of resolved release trees through the only sanctioned
# reader, which is bounded by the tree *(R15 AC9)* — so the last few cases build
# real release trees, in both registry shapes a release might publish.
#
# Flagging is a reported outcome and never an error. Identical text flags
# nothing, and a release pair with nothing to compare is silence rather than a
# failure: release 0.5.1 ships no invariant registry at all, and the checked-in
# `invariantDiscounts` register is empty, so "nothing to compare" is the
# situation the committed repository is actually in today.

import hashlib
import json

from reconcile import (
    DISCOUNT_REGISTER_KEY,
    DRIFT_ACTION,
    INVARIANT_REGISTRY_DIRECTORY,
    INVARIANT_REGISTRY_FILENAME,
    FlaggedDiscount,
    canonical_invariant_text,
    contract_invariant_discounts,
    flag_invariant_drift,
    flag_release_invariant_drift,
    locate_invariant_registry,
    normalize_invariant_id,
    read_release_invariants,
    reconcile_directories,
)
from strategies import DISCOUNTED_INVARIANTS, HONORED_INVARIANT
from transform import MANIFEST_FILENAME

#: One text per discountable invariant, as a release registry would define it.
#: The wording carries no meaning for this comparison — only its stability does.
#: No line opens with an `INV-NNN` token, so a one-per-file registry entry has to
#: be identified by its filename, which is the case the per-file tests exercise.
INVARIANT_TEXTS: Mapping[str, str] = {
    "INV-072": (
        "Hook definitions are declared by the plugin and never hand-written\n"
        "into a host configuration directory."
    ),
    "INV-113": (
        "Progress state is written to one file, and that file is the only\n"
        "record a resumed session reads."
    ),
    "INV-201": "Generated content is written under the plugin root, never above it.",
}

#: The invariant upstream reworded, and its new text. This is the R15 AC10 edit:
#: the guarantee still has a name, but the recorded resolution was written
#: against wording that no longer exists.
DRIFTED_INVARIANT = "INV-113"
EDITED_INVARIANT_TEXT = (
    "Progress state is written to one file per module, and a resumed session\n"
    "reads the newest of them."
)

#: A release pair, named. Supplying tags is what makes a reason legible to a
#: Maintainer — "text changed" is only actionable once it says between what.
FROM_RELEASE = "0.5.1"
TO_RELEASE = "0.6.0"


def _register(*identifiers: str) -> tuple[Mapping[str, Any], ...]:
    """An `Invariant_Discount_Register` naming `identifiers` *(R15 AC4)*.

    Complete entries — identifier, conflicting constraint, resolution — because
    an incomplete one is the Schema_Validator's `E_INCOMPLETE_DISCOUNT`
    *(R15 AC5)* rather than anything drift flagging should have an opinion about.
    """
    return tuple(
        {
            "invariant": identifier,
            "conflictsWith": "the Agent Plugins v1.0.0 hook definition format",
            "resolution": "the Kiro hook definition shape is written instead",
        }
        for identifier in identifiers
    )


def _edited(identifier: str = DRIFTED_INVARIANT) -> dict[str, str]:
    """`INVARIANT_TEXTS` with exactly one invariant reworded."""
    updated = dict(INVARIANT_TEXTS)
    updated[identifier] = EDITED_INVARIANT_TEXT
    return updated


def _registry_document(texts: Mapping[str, str]) -> str:
    """One `INVARIANTS.md` defining every text, with preamble prose.

    The preamble belongs to no invariant, so a registry that grows a foreword
    does not read as an edit to whichever invariant happens to be listed first.
    """
    lines = [
        "# Template invariants",
        "",
        "Prose before the first entry, which defines no invariant.",
        "",
    ]
    for identifier, text in texts.items():
        lines.extend([f"## {identifier}", "", text, ""])
    return "\n".join(lines) + "\n"


def _release_tree(
    root: Path, texts: Mapping[str, str], *, per_file: bool = False
) -> Path:
    """Write a release tree publishing `texts` as its invariant registry.

    `per_file` writes the `invariants/INV-NNN.md` shape instead of one shared
    `INVARIANTS.md`; empty `texts` writes no registry at all, which is what
    release 0.5.1 ships.
    """
    plugin = root / "plugins" / "senzing-bootcamp"
    plugin.mkdir(parents=True, exist_ok=True)
    (plugin / "README.md").write_text("Bootcamp plugin.\n", encoding="utf-8")
    if per_file:
        directory = root / INVARIANT_REGISTRY_DIRECTORY
        directory.mkdir(parents=True, exist_ok=True)
        for identifier, text in texts.items():
            (directory / f"{identifier}.md").write_text(
                f"{text}\n", encoding="utf-8"
            )
    elif texts:
        (root / INVARIANT_REGISTRY_FILENAME).write_text(
            _registry_document(texts), encoding="utf-8"
        )
    return root


def test_the_fixture_registry_defines_exactly_the_discountable_invariants() -> None:
    """The fixtures discount what may be discounted, and nothing else.

    `INV-052` is honored under R16 rather than discounted, so no register built
    here may name it *(R15 AC6)*.
    """
    assert tuple(INVARIANT_TEXTS) == DISCOUNTED_INVARIANTS
    assert HONORED_INVARIANT not in INVARIANT_TEXTS
    assert DRIFTED_INVARIANT in DISCOUNTED_INVARIANTS


def test_an_edited_invariant_text_flags_exactly_that_register_entry() -> None:
    """A newer release rewording one invariant flags one entry *(R15 AC10)*.

    Exactly that entry: the other two discounts still have their subjects, and
    flagging them would ask a Maintainer to re-read judgments nothing touched.
    """
    flagged = flag_invariant_drift(
        _register(*DISCOUNTED_INVARIANTS),
        INVARIANT_TEXTS,
        _edited(),
        from_release=FROM_RELEASE,
        to_release=TO_RELEASE,
    )

    assert [item.invariant for item in flagged] == [DRIFTED_INVARIANT]
    entry = flagged[0]
    assert entry.reason.strip(), "a flag with no reason asks for nothing"
    assert FROM_RELEASE in entry.reason and TO_RELEASE in entry.reason
    assert entry.action == DRIFT_ACTION
    assert entry.to_json() == {
        "invariant": DRIFTED_INVARIANT,
        "reason": entry.reason,
        "action": DRIFT_ACTION,
    }


def test_identical_invariant_text_produces_no_flag() -> None:
    """A discount still about its subject needs no attention *(R15 AC10)*."""
    assert (
        flag_invariant_drift(
            _register(*DISCOUNTED_INVARIANTS),
            INVARIANT_TEXTS,
            dict(INVARIANT_TEXTS),
            from_release=FROM_RELEASE,
            to_release=TO_RELEASE,
        )
        == ()
    )


def test_an_invariant_no_registry_defines_is_not_flagged() -> None:
    """A register entry neither release defines has nothing to compare.

    Both releases publish a registry here, and one invariant in it moved — so
    the silence is about this entry specifically, not about an inert comparison.
    """
    previous = {
        identifier: text
        for identifier, text in INVARIANT_TEXTS.items()
        if identifier != "INV-201"
    }
    new = dict(previous)
    new["INV-072"] = EDITED_INVARIANT_TEXT

    assert flag_invariant_drift(_register("INV-201"), previous, new) == ()
    both = flag_invariant_drift(_register("INV-201", "INV-072"), previous, new)
    assert [item.invariant for item in both] == ["INV-072"]


def test_an_empty_register_flags_nothing() -> None:
    """No recorded discount, no judgment to reopen — the committed state today."""
    changed = {identifier: EDITED_INVARIANT_TEXT for identifier in INVARIANT_TEXTS}

    assert flag_invariant_drift((), INVARIANT_TEXTS, changed) == ()
    assert contract_invariant_discounts({DISCOUNT_REGISTER_KEY: []}) == ()
    assert (
        flag_invariant_drift(
            contract_invariant_discounts({DISCOUNT_REGISTER_KEY: []}),
            INVARIANT_TEXTS,
            changed,
        )
        == ()
    )


@pytest.mark.parametrize("publishes", ["neither", "from-only", "to-only"])
def test_a_release_pair_missing_a_registry_flags_nothing(publishes: str) -> None:
    """Either side publishing no registry is silence, not failure *(R15 AC10)*.

    Release 0.5.1 ships no invariant registry, so this is the live case rather
    than a hypothetical one: with no text on one side there is nothing to
    compare, and nothing to compare cannot be evidence that something moved.
    """
    published = _edited()
    previous = INVARIANT_TEXTS if publishes == "from-only" else {}
    new = published if publishes == "to-only" else {}

    assert (
        flag_invariant_drift(
            _register(*DISCOUNTED_INVARIANTS),
            previous,
            new,
            from_release=FROM_RELEASE,
            to_release=TO_RELEASE,
        )
        == ()
    )


@pytest.mark.parametrize("missing", ["from", "to"])
def test_one_sided_absence_is_flagged_and_names_the_side_that_lacks_it(
    missing: str,
) -> None:
    """An invariant that appeared or disappeared moved what the discount judged.

    Both releases publish a registry, so absence on one side is a real
    difference between them rather than a release with nothing to say. The
    reason names which side lacks the text, because the Maintainer response
    differs: a withdrawn invariant retires its discount, a new one may need one.
    """
    complete = dict(INVARIANT_TEXTS)
    partial = {
        identifier: text
        for identifier, text in INVARIANT_TEXTS.items()
        if identifier != DRIFTED_INVARIANT
    }
    previous, new = (
        (partial, complete) if missing == "from" else (complete, partial)
    )

    flagged = flag_invariant_drift(
        _register(*DISCOUNTED_INVARIANTS),
        previous,
        new,
        from_release=FROM_RELEASE,
        to_release=TO_RELEASE,
    )

    assert [item.invariant for item in flagged] == [DRIFTED_INVARIANT]
    missing_label = FROM_RELEASE if missing == "from" else TO_RELEASE
    assert (
        f"absent from the invariant registry of {missing_label}"
        in flagged[0].reason
    )
    assert flagged[0].action == DRIFT_ACTION


def test_flags_are_sorted_by_invariant_and_repeat_identically() -> None:
    """Two runs over one input serialize the same bytes, in identifier order.

    The register below is in neither identifier order nor drift order, so the
    output order is the comparison's own rather than an accident of the input.
    """
    new = _edited("INV-201")
    new["INV-072"] = f"{INVARIANT_TEXTS['INV-072']}\nAn added sentence."
    register = _register("INV-201", "INV-113", "INV-072")

    flagged = flag_invariant_drift(register, INVARIANT_TEXTS, new)

    assert [item.invariant for item in flagged] == ["INV-072", "INV-201"]
    assert flagged == flag_invariant_drift(register, INVARIANT_TEXTS, new)


@pytest.mark.parametrize(
    "spelling, expected",
    [
        ("INV-072", ("INV-072",)),
        ("inv-072", ("INV-072",)),
        ("INV-072 ", ("INV-072",)),
        (" \tinv-072\n", ("INV-072",)),
        # A different invariant that reads like it: the digits are the identity.
        ("INV-72", ()),
    ],
)
def test_near_miss_identifier_spellings_normalize_as_documented(
    spelling: str, expected: tuple[str, ...]
) -> None:
    """Case and surrounding whitespace fold; digits do not.

    The registry key is spelled differently from the register entry on purpose:
    both sides of the lookup normalize, or an entry would match its own
    invariant only when two files agreed on capitalization.
    """
    flagged = flag_invariant_drift(
        _register(spelling),
        {"INV-072": INVARIANT_TEXTS["INV-072"]},
        {"inv-072 ": EDITED_INVARIANT_TEXT},
    )

    assert tuple(item.invariant for item in flagged) == expected


def test_identifier_normalization_folds_spelling_but_not_digit_count() -> None:
    """`inv-052`, `INV-052 `, and `INV-052` are one invariant; `INV-52` is not."""
    assert normalize_invariant_id("inv-052") == HONORED_INVARIANT
    assert normalize_invariant_id("INV-052 ") == HONORED_INVARIANT
    assert normalize_invariant_id("INV-52") != HONORED_INVARIANT
    assert normalize_invariant_id(None) == ""


def test_a_whitespace_or_line_ending_repack_is_not_read_as_an_edit() -> None:
    """A CRLF checkout or a trailing-space cleanup is not an upstream rewording.

    R16 AC8 normalizes line endings across platforms, so the same invariant text
    legitimately reaches disk in more than one encoding of the same characters.
    Flagging that would ask for re-evaluation of a judgment nothing touched.
    """
    original = INVARIANT_TEXTS[DRIFTED_INVARIANT]
    repacked = "\n\n" + original.replace("\n", "   \r\n") + "  \r\n\r\n"

    assert repacked != original
    assert canonical_invariant_text(repacked) == canonical_invariant_text(original)
    assert (
        flag_invariant_drift(
            _register(DRIFTED_INVARIANT),
            {DRIFTED_INVARIANT: original},
            {DRIFTED_INVARIANT: repacked},
        )
        == ()
    )


@pytest.mark.parametrize(
    "register",
    [
        (),
        ({},),
        ({"invariant": ""},),
        ({"invariant": "   "},),
        ({"invariant": None},),
        ("INV-072",),
        ({"invariant": "INV-072"},),
        ({"invariant": "INV-072"}, {"invariant": "inv-072"}),
        (None, 123, ["INV-072"], {"invariant": "INV-072"}),
    ],
)
def test_flagging_a_malformed_register_entry_never_raises(
    register: tuple[Any, ...]
) -> None:
    """Flagging reports; it never halts *(R15 AC10)*.

    A register entry missing its identifier is the Schema_Validator's gate
    *(R15 AC5)*, so raising here would report the wrong thing at the wrong time
    — and an update that cannot produce a reconciliation report is worse than
    one that reports one flag fewer. Duplicate entries collapse: an invariant is
    compared once however many entries name it.
    """
    flagged = flag_invariant_drift(register, INVARIANT_TEXTS, _edited("INV-072"))

    assert isinstance(flagged, tuple)
    assert all(isinstance(item, FlaggedDiscount) for item in flagged)
    assert all(item.invariant == "INV-072" for item in flagged)
    assert all(item.action == DRIFT_ACTION for item in flagged)
    assert len(flagged) == len({item.invariant for item in flagged})


def test_release_trees_sharing_a_registry_file_flag_only_the_edited_invariant(
    tmp_path: Path,
) -> None:
    """The filesystem half: locate, read, compare *(R15 AC9, AC10)*.

    Both texts come out of the resolved release trees through the sanctioned
    reader, never from the template's development repository. One tree is handed
    over as a path and one as a resolved-release record, because both forms end
    at the same bounded reader.
    """
    previous_tree = _release_tree(tmp_path / FROM_RELEASE, INVARIANT_TEXTS)
    new_tree = _release_tree(tmp_path / TO_RELEASE, _edited())
    unchanged_tree = _release_tree(tmp_path / "0.5.1-repackaged", INVARIANT_TEXTS)

    assert locate_invariant_registry(previous_tree) == (
        INVARIANT_REGISTRY_FILENAME,
    )
    assert tuple(read_release_invariants(previous_tree)) == DISCOUNTED_INVARIANTS

    flagged = flag_release_invariant_drift(
        _register(*DISCOUNTED_INVARIANTS),
        previous_tree,
        {"extractedTo": str(new_tree)},
        from_release=FROM_RELEASE,
        to_release=TO_RELEASE,
    )

    assert [item.invariant for item in flagged] == [DRIFTED_INVARIANT]
    assert flagged[0].action == DRIFT_ACTION
    # Same registry, written twice into two different trees: no flag.
    assert (
        flag_release_invariant_drift(
            _register(*DISCOUNTED_INVARIANTS),
            previous_tree,
            unchanged_tree,
            from_release=FROM_RELEASE,
            to_release=TO_RELEASE,
        )
        == ()
    )


@pytest.mark.parametrize("edited, expected", [(True, ("INV-072",)), (False, ())])
def test_a_per_file_registry_entry_is_read_and_compared(
    tmp_path: Path, edited: bool, expected: tuple[str, ...]
) -> None:
    """An `invariants/INV-072.md` is a registry too *(R15 AC9)*.

    The file body opens no entry of its own, so the invariant it defines is
    named by the filename. A later release is free to pick this shape over one
    shared `INVARIANTS.md`, and the comparison has to read either.
    """
    original = {"INV-072": INVARIANT_TEXTS["INV-072"]}
    previous_tree = _release_tree(tmp_path / "from", original, per_file=True)
    new_tree = _release_tree(
        tmp_path / "to",
        {"INV-072": EDITED_INVARIANT_TEXT if edited else original["INV-072"]},
        per_file=True,
    )

    assert locate_invariant_registry(previous_tree) == (
        f"{INVARIANT_REGISTRY_DIRECTORY}/INV-072.md",
    )
    assert tuple(read_release_invariants(previous_tree)) == ("INV-072",)

    flagged = flag_release_invariant_drift(
        _register("INV-072"),
        previous_tree,
        new_tree,
        from_release=FROM_RELEASE,
        to_release=TO_RELEASE,
    )

    assert tuple(item.invariant for item in flagged) == expected


def test_a_release_that_ships_no_registry_reads_and_flags_nothing(
    tmp_path: Path,
) -> None:
    """Release 0.5.1's actual shape: no registry, read from disk *(R15 AC10)*."""
    bare = _release_tree(tmp_path / FROM_RELEASE, {})
    published = _release_tree(tmp_path / TO_RELEASE, INVARIANT_TEXTS)
    register = _register(*DISCOUNTED_INVARIANTS)

    assert locate_invariant_registry(bare) == ()
    assert read_release_invariants(bare) == {}
    assert flag_release_invariant_drift(register, bare, published) == ()
    assert flag_release_invariant_drift(register, published, bare) == ()


def test_a_symlinked_registry_is_not_followed_out_of_the_release_tree(
    tmp_path: Path,
) -> None:
    """The release tree bounds what may be read *(R15 AC9)*.

    A symlink is the one way a file inside the tree can name content outside it,
    so it is not followed: an invariant definition cannot arrive from anywhere
    but the resolved release.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / INVARIANT_REGISTRY_FILENAME).write_text(
        _registry_document({"INV-072": "Text from outside the release tree."}),
        encoding="utf-8",
    )
    tree = _release_tree(tmp_path / "release", {})
    try:
        (tree / INVARIANT_REGISTRY_FILENAME).symlink_to(
            outside / INVARIANT_REGISTRY_FILENAME
        )
    except (OSError, NotImplementedError):  # pragma: no cover - platform-dependent
        pytest.skip("this platform does not permit creating symlinks")

    assert locate_invariant_registry(tree) == ()
    assert read_release_invariants(tree) == {}


def _power_and_staging(tmp_path: Path) -> tuple[Path, Path]:
    """A Power and a staging tree that agree, with a manifest recording them.

    Nothing about the files moved, so the only thing the report can carry is the
    drift comparison — which is the point: flagging a discount is not a file
    classification, and it has to survive a reconciliation that found nothing
    else to say.
    """
    content = b"The bootcamp Power.\n"
    power = tmp_path / "power"
    staging = tmp_path / "staging"
    for root in (power, staging):
        root.mkdir()
        (root / "README.md").write_bytes(content)
    manifest = {
        "manifestVersion": 1,
        "templateRelease": FROM_RELEASE,
        "contractVersion": 1,
        "files": [
            {
                "path": "README.md",
                "ruleId": "docs",
                "owner": "template",
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
    }
    (power / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return power, staging


def test_the_reconciliation_report_carries_the_flagged_discount(
    tmp_path: Path,
) -> None:
    """The flag reaches the report a Maintainer reads *(R15 AC10)*.

    `flaggedInvariantDiscounts` is where re-evaluation is actually asked for, so
    the end-to-end path is checked once: register from the contract document,
    texts from the two resolved release trees, one entry in the serialized
    report. Given only one tree, there is no release pair and nothing is flagged.
    """
    power, staging = _power_and_staging(tmp_path)
    previous_tree = _release_tree(tmp_path / FROM_RELEASE, INVARIANT_TEXTS)
    new_tree = _release_tree(tmp_path / TO_RELEASE, _edited())
    contract = {DISCOUNT_REGISTER_KEY: list(_register(*DISCOUNTED_INVARIANTS))}

    report = reconcile_directories(
        power,
        staging,
        to_release=TO_RELEASE,
        contract=contract,
        from_release_tree=previous_tree,
        to_release_tree=new_tree,
    )

    assert report.unchanged == ("README.md",)
    assert report.conflicts == ()
    assert [item.invariant for item in report.flagged_invariant_discounts] == [
        DRIFTED_INVARIANT
    ]

    document = report.to_json()
    assert document["fromRelease"] == FROM_RELEASE
    assert document["toRelease"] == TO_RELEASE
    assert document["flaggedInvariantDiscounts"] == [
        {
            "invariant": DRIFTED_INVARIANT,
            "reason": report.flagged_invariant_discounts[0].reason,
            "action": DRIFT_ACTION,
        }
    ]
    assert FROM_RELEASE in document["flaggedInvariantDiscounts"][0]["reason"]
    assert TO_RELEASE in document["flaggedInvariantDiscounts"][0]["reason"]

    # Drift is a statement about two releases; one tree compares nothing.
    half = reconcile_directories(
        power,
        staging,
        to_release=TO_RELEASE,
        contract=contract,
        to_release_tree=new_tree,
    )
    assert half.flagged_invariant_discounts == ()
    assert half.unchanged == report.unchanged

# ===========================================================================
# 4. Optional-runtime absence (task 11.9) — R16 AC7
# ===========================================================================
#
# `INV-052` lets the bootcamp require exactly one runtime — the Python
# interpreter already running the script — and requires every other runtime to be
# optional with a graceful fallback. R16 AC7 says what "graceful" means here:
# continue operating with reduced capability while the runtime is absent. The
# `optional-runtime-guard` module is where that behavior is written down once,
# and its three steps are always the same: **say what is unavailable, say what
# still works, and return success**.
#
# Presence is not a useful axis for generated input — a runtime is there or it is
# not — so the design routes this to example-based unit tests with the runtime
# mocked absent, two cases: a container CLI (Docker for the SDK modules) and a
# browser (headless capture for the truth-set visualization), plus both at once.
#
# The mock is the host lookup, not the module: `which()` calls `shutil.which` at
# call time, so monkeypatching `shutil.which` removes a command from PATH for the
# duration of one test, and `importable` is patched directly to remove a Python
# module. Nothing here runs a container, a browser, or any subprocess.
#
# The number that matters is the exit status. In Kiro, exit **2** from a
# `PreToolUse`, `UserPromptSubmit`, or `PreTaskExec` hook *blocks* the action, so
# "does not block its trigger" is the assertion that a missing optional runtime
# is never spelled 2 — an absent container CLI must reduce one module's
# capability, not block every turn of a session. That is asserted on every path,
# in both output modes, including when the host lookup itself raises.

import importlib.util
import shutil
import sys
from functools import lru_cache

from conftest import REPO_ROOT

#: The guard, authored under `templates/kiro-owned/`. The contract's
#: `optional-runtime-guard` rule (`kind: kiro-owned`, `owner: kiro`) materializes
#: this one file into the ported script directory, beside `docker_lifecycle.py`,
#: so any script there reaches it by same-directory import on all three
#: platforms. It is loaded from the authored path because the built Power does
#: not exist in this repository yet.
OPTIONAL_RUNTIME_PATH = (
    "tools/bootcamp-transform/templates/kiro-owned/skills/bootcamp-onboarding"
    "/scripts/optional_runtime.py"
)

#: The two optional runtimes the design names, in declared order. Every case
#: below is built from these, and the test directly after this comment is what
#: keeps them the module's own set rather than a restatement of it.
CONTAINER_KEY = "container"
BROWSER_KEY = "browser"
OPTIONAL_RUNTIME_KEYS = (CONTAINER_KEY, BROWSER_KEY)

#: A key no runtime declares. It must answer "not available" rather than raise:
#: nothing acts on a runtime this module does not declare.
UNDECLARED_KEY = "kubernetes"

#: Where a mocked-present command claims to live. Any non-empty path will do —
#: `find_runtime` reports the location it found, it never executes it.
FAKE_BIN = "/fake/bin"


@lru_cache(maxsize=1)
def _optional_runtime() -> Any:
    """Import the Optional_Runtime guard as a module and hand back its namespace.

    Loaded by path because it ships inside `templates/kiro-owned/` rather than on
    `sys.path`. It must be registered in `sys.modules` *before* `exec_module`:
    the module declares `from __future__ import annotations` and a `@dataclass`,
    and `dataclasses` resolves the stringized annotations through
    `sys.modules[cls.__module__]`.
    """
    path = REPO_ROOT / OPTIONAL_RUNTIME_PATH
    assert path.is_file(), f"the Optional_Runtime guard is missing from {OPTIONAL_RUNTIME_PATH}"
    spec = importlib.util.spec_from_file_location("senzing_bootcamp_optional_runtime", path)
    assert spec is not None and spec.loader is not None, f"cannot load {OPTIONAL_RUNTIME_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _runtimes_by_key() -> Mapping[str, Any]:
    return {runtime.key: runtime for runtime in _optional_runtime().OPTIONAL_RUNTIMES}


def _fake_host(
    monkeypatch: pytest.MonkeyPatch,
    *,
    commands: Sequence[str] = (),
    modules: Sequence[str] = (),
) -> Any:
    """Mock the host: only `commands` are on PATH, only `modules` import.

    Both halves are the lookups the guard actually performs — `shutil.which` at
    call time, and the import probe — so a runtime is absent here for exactly the
    reason it would be absent on a real host that lacks it.
    """
    module = _optional_runtime()
    present_commands = frozenset(commands)
    present_modules = frozenset(modules)

    def fake_which(command: str, *_args: Any, **_kwargs: Any) -> str | None:
        return f"{FAKE_BIN}/{command}" if command in present_commands else None

    monkeypatch.setattr(shutil, "which", fake_which)
    monkeypatch.setattr(module, "importable", lambda name: name in present_modules)
    return module


def _host_with(monkeypatch: pytest.MonkeyPatch, present: Sequence[str]) -> Any:
    """A host carrying every way to satisfy the runtimes in `present`, and no other."""
    runtimes = _runtimes_by_key()
    return _fake_host(
        monkeypatch,
        commands=[command for key in present for command in runtimes[key].commands],
        modules=[module for key in present for module in runtimes[key].modules],
    )


def _absent_cases() -> list[Any]:
    """The three absence cases, named the way the requirement names them."""
    return [
        pytest.param((CONTAINER_KEY,), id="docker-absent"),
        pytest.param((BROWSER_KEY,), id="browser-absent"),
        pytest.param(OPTIONAL_RUNTIME_KEYS, id="both-absent"),
    ]


def _expected_missing(absent: Sequence[str]) -> tuple[str, ...]:
    """`missing()` answers in declared order, whatever order the case names."""
    return tuple(key for key in OPTIONAL_RUNTIME_KEYS if key in absent)


def _present(absent: Sequence[str]) -> tuple[str, ...]:
    return tuple(key for key in OPTIONAL_RUNTIME_KEYS if key not in absent)


def test_the_declared_optional_runtimes_are_the_ones_the_design_names() -> None:
    """A closed set of two: a container CLI and a browser *(R16 AC7)*.

    Every case below is parametrized over these keys, so this is what ties the
    parametrization to the module's own declaration — and what fails if a runtime
    is added without a case, or if the required runtime were ever declared
    optional.
    """
    module = _optional_runtime()
    runtimes = _runtimes_by_key()

    assert tuple(runtimes) == OPTIONAL_RUNTIME_KEYS
    assert UNDECLARED_KEY not in runtimes
    # Docker for the SDK modules; a headless capture backend for the recap.
    assert "docker" in runtimes[CONTAINER_KEY].commands
    assert "playwright" in runtimes[BROWSER_KEY].modules
    assert any(
        "chrom" in command for command in runtimes[BROWSER_KEY].commands
    ), "the browser runtime must look for a Chrome/Chromium binary on PATH"
    # The one required runtime is the interpreter running the script, so it is
    # never probed and never one of the optional keys.
    assert "Python" in module.REQUIRED_RUNTIME
    for runtime in runtimes.values():
        assert runtime.commands or runtime.modules, (
            f"{runtime.key} declares nothing to look for, so it can never be found"
        )
        assert runtime.needed_for.strip(), f"{runtime.key} does not say what it is needed for"
        assert runtime.without_it.strip(), f"{runtime.key} does not say what still works"


def test_reduced_capability_is_success_and_is_never_kiros_blocking_status() -> None:
    """0, not 2 *(R16 AC7)*.

    Exit 2 from a `PreToolUse`, `UserPromptSubmit`, or `PreTaskExec` hook blocks
    the action. Reduced capability is a normal state of this bootcamp, so it
    cannot share a status with "stop what the Bootcamper just asked for".
    """
    module = _optional_runtime()

    assert module.EXIT_REDUCED_CAPABILITY == 0
    assert module.EXIT_BLOCK == 2
    assert module.EXIT_REDUCED_CAPABILITY != module.EXIT_BLOCK


@pytest.mark.parametrize("absent", _absent_cases())
def test_an_absent_runtime_is_named_in_the_report_together_with_what_still_works(
    absent: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The report says what is unavailable and what still works *(R16 AC7)*.

    Both halves, because either alone is the wrong message: naming the absence
    without the fallback reads as a failure, and naming neither leaves a
    Bootcamper wondering why a module went quiet. The authoritative script is
    named too, so this report can never contradict the one that script prints.
    """
    module = _host_with(monkeypatch, _present(absent))
    runtimes = _runtimes_by_key()

    text = module.report()

    assert module.REQUIRED_RUNTIME in text, "the report must state what *is* present"
    for key in absent:
        runtime = runtimes[key]
        assert f"{runtime.label}: not available" in text
        assert runtime.needed_for in text, "an absence with no consequence asks nothing"
        assert runtime.without_it in text, "the report must name what still works"
        if runtime.authority:
            assert runtime.authority in text
    for key in _present(absent):
        assert f"{runtimes[key].label}: available" in text
    assert "Reduced capability" in text
    assert "the bootcamp continues" in text


@pytest.mark.parametrize("absent", _absent_cases())
def test_an_absent_runtime_is_reported_by_key_as_missing_and_unavailable(
    absent: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`missing()` and `available(key)` agree with the report *(R16 AC7)*.

    A script asks `available(key)` before it reaches for a runtime; the report is
    what the Bootcamper hears. They read the same host, so they cannot disagree.
    """
    module = _host_with(monkeypatch, _present(absent))
    expected = _expected_missing(absent)

    assert module.missing() == expected
    for key in absent:
        assert module.available(key) is False
    for key in _present(absent):
        assert module.available(key) is True
    # An undeclared runtime is "not available" rather than an error.
    assert module.available(UNDECLARED_KEY) is False

    results = module.statuses()
    assert tuple(status.runtime.key for status in results) == OPTIONAL_RUNTIME_KEYS
    assert tuple(status.runtime.key for status in results if not status.available) == expected
    for status in results:
        assert (status.found is None) is (status.runtime.key in absent)


@pytest.mark.parametrize("absent", _absent_cases())
def test_the_owning_command_returns_success_with_an_optional_runtime_absent(
    absent: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """It reports, it returns success, and it does not block its trigger *(R16 AC7)*.

    The status is the whole point: a hook that forwarded a 2 from here would
    block a turn of the session over a missing container CLI.
    """
    module = _host_with(monkeypatch, _present(absent))
    runtimes = _runtimes_by_key()

    status = module.main([])

    assert status == module.EXIT_REDUCED_CAPABILITY == 0
    assert status != module.EXIT_BLOCK, "a missing optional runtime blocked the trigger"
    captured = capsys.readouterr()
    assert captured.out == "", "the text report goes to stderr, leaving stdout clean"
    for key in absent:
        assert f"{runtimes[key].label}: not available" in captured.err
        assert runtimes[key].without_it in captured.err


@pytest.mark.parametrize("absent", _absent_cases())
def test_the_json_report_returns_success_and_names_the_missing_runtimes(
    absent: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--json` is the same answer, machine-readable, and still exit 0 *(R16 AC7)*.

    An agent reading this decides which module to reach for, so the payload has
    to carry the same two facts as the prose: what is unavailable, and what still
    works without it.
    """
    module = _host_with(monkeypatch, _present(absent))
    runtimes = _runtimes_by_key()

    status = module.main(["--json"])

    assert status == module.EXIT_REDUCED_CAPABILITY == 0
    assert status != module.EXIT_BLOCK
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["required"] == module.REQUIRED_RUNTIME
    assert payload["missing"] == list(_expected_missing(absent))
    assert payload["exitCode"] == module.EXIT_REDUCED_CAPABILITY
    entries = {entry["runtime"]: entry for entry in payload["optional"]}
    assert tuple(entries) == OPTIONAL_RUNTIME_KEYS
    for key, entry in entries.items():
        runtime = runtimes[key]
        assert entry["available"] is (key not in absent)
        assert entry["label"] == runtime.label
        assert entry["neededFor"] == runtime.needed_for
        assert entry["withoutIt"] == runtime.without_it
        assert entry["searched"] == list(runtime.commands + runtime.modules)
        if key in absent:
            assert entry["found"] is None
        else:
            assert entry["found"]


def test_a_host_with_every_optional_runtime_reports_nothing_reduced(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Full capability still returns 0, and says nothing is reduced *(R16 AC7)*.

    The counterpart to the absence cases: the report cannot be one that always
    announces a degradation, or "what is unavailable" would carry no information.
    """
    module = _host_with(monkeypatch, OPTIONAL_RUNTIME_KEYS)

    text = module.report()

    assert module.missing() == ()
    assert all(module.available(key) for key in OPTIONAL_RUNTIME_KEYS)
    assert "not available" not in text
    assert "Nothing is reduced" in text
    assert module.main([]) == module.EXIT_REDUCED_CAPABILITY
    assert module.main(["--json"]) == module.EXIT_REDUCED_CAPABILITY
    payload = json.loads(capsys.readouterr().out)
    assert payload["missing"] == []
    assert all(entry["available"] for entry in payload["optional"])
    assert payload["exitCode"] == module.EXIT_REDUCED_CAPABILITY


def test_a_browser_reached_through_a_python_module_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A capture backend counts whether it is a binary or an importable module.

    `capture_screenshots.py` tries Playwright and Selenium before any browser
    binary, so a host with Playwright installed and no Chrome on PATH has the
    capability. Reporting it absent would tell a Bootcamper to install something
    they do not need *(R16 AC7)*.
    """
    module = _fake_host(monkeypatch, commands=["docker"], modules=["playwright"])

    assert module.available(BROWSER_KEY) is True
    assert module.missing() == ()
    found = {status.runtime.key: status.found for status in module.statuses()}
    assert found[BROWSER_KEY] == "python module playwright"
    assert found[CONTAINER_KEY] == f"{FAKE_BIN}/docker"


@pytest.mark.parametrize("which_error", [OSError, ValueError])
def test_a_host_lookup_that_raises_reports_absence_instead_of_propagating(
    which_error: type[BaseException],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A broken PATH or import system is reduced capability, not a crash *(R16 AC7)*.

    `shutil.which` raises on some hosts (an unreadable PATH entry), and
    `find_spec` raises `ValueError` for a module whose parent package is in a
    half-initialized state. The guard documents that `which`, `importable`, and
    `find_runtime` never raise, and the reason is this requirement: a traceback
    out of a hook is a non-zero status, and a non-zero status is how a turn gets
    blocked.
    """
    module = _optional_runtime()

    def raising_which(command: str, *_args: Any, **_kwargs: Any) -> str | None:
        raise which_error(f"the host could not search PATH for {command}")

    def raising_find_spec(name: str, *_args: Any, **_kwargs: Any) -> Any:
        raise ValueError(f"{name}.__spec__ is not set")

    monkeypatch.setattr(shutil, "which", raising_which)
    monkeypatch.setattr(importlib.util, "find_spec", raising_find_spec)

    assert module.which("docker") is None
    assert module.importable("playwright") is False
    for runtime in module.OPTIONAL_RUNTIMES:
        assert module.find_runtime(runtime) is None
        assert module.available(runtime.key) is False
    assert module.missing() == OPTIONAL_RUNTIME_KEYS

    text = module.report()
    assert "Reduced capability" in text
    assert "the bootcamp continues" in text
    assert module.main([]) == module.EXIT_REDUCED_CAPABILITY
    assert module.main(["--json"]) == module.EXIT_REDUCED_CAPABILITY
    payload = json.loads(capsys.readouterr().out)
    assert payload["missing"] == list(OPTIONAL_RUNTIME_KEYS)
    assert payload["exitCode"] == module.EXIT_REDUCED_CAPABILITY

# ===========================================================================
# 5. Create/update orchestration edge cases (task 12.5)
#    — R4 AC5, AC6, R14 AC4, AC5
# ===========================================================================
#
# Both maintainer skills are orchestrators: they resolve, build into staging,
# validate, and then publish by one call. The claims below are about the three
# moments where the orchestration meets the target directory — a Power that is
# already there, a target that is not there yet, and a target that cannot be
# written — and every one of them is enforced by the engine rather than by the
# prose that invokes it. So these tests drive `write_staging`, `discard_staging`,
# and `swap_into_place` directly, in the order the skills call them.
#
# The one exception is the conflict *report*. A pre-flight look at the target and
# a question to the Maintainer is not engine behavior, so the first test checks
# the skill's own text and nothing else, and the tests after it carry the half
# that is enforceable: nothing reaches the target until the swap.
#
# The failure conditions here are real rather than injected. The property suite
# already covers a permission denial and a `path-is-a-file` fault as exceptions
# raised *out of* `os.rename`, which establishes what the engine does when a
# write fails; what these tests establish is that a genuinely unwritable
# directory and a genuine file-where-a-directory-belongs actually reach that
# path, with a real `EACCES` and a real `ENOTDIR` from the filesystem.
#
# Each build is a real one — the real contract over a real release tree, so the
# staged tree is the Power the skills would publish. The template documents below
# are the smallest input that produces one; their content is section 2's subject,
# not this section's.

import json
import os
from contextlib import contextmanager
from typing import Iterator

from transform import (
    E_WRITE_FAILED,
    MANIFEST_FILENAME,
    SENZING_MCP_URL,
    StagingResult,
    build_plan,
    discard_staging,
    load_contract,
    swap_into_place,
    write_staging,
)

#: The Power's published location, spelled the way R4 AC5 requires the conflict
#: to name it and R14 AC1 requires it to be written.
TARGET_RELATIVE = "powers/senzing-bootcamp"

#: The same location as the conflict report spells it: with the trailing slash,
#: because what is reported is a directory.
TARGET_REPORTED = f"{TARGET_RELATIVE}/"

#: The staging directory both maintainer skills use — a sibling of the target, so
#: the swap's rename never has to cross a filesystem boundary.
STAGING_RELATIVE = "powers/.senzing-bootcamp.staging"

#: The Create_Skill, whose pre-flight step is the only place the conflict report
#: exists.
CREATE_SKILL_PATH = (
    "powers/senzing-bootcamp-maintainer/skills/create-bootcamp-power/SKILL.md"
)

#: The release being built, and the release the Power already on disk was built
#: from. Two different tags, so "the target is unchanged" is observable in the
#: content and not only in the byte comparison.
BUILD_TAG = "0.5.1"
PRIOR_TAG = "0.5.0"

#: The two template sources a build needs in order to produce a tree at all: the
#: contract's `generate` rules for `plugin.json` and `mcp.json` name them. The
#: rest of the Power comes from `templates/kiro-owned/` and this repository's
#: root license, which every build plans regardless of what the template ships.
SOURCE_DOCUMENTS: Mapping[str, str] = {
    ".mcp.json": json.dumps(
        {"mcpServers": {"senzing": {"type": "http", "url": SENZING_MCP_URL}}},
        indent=2,
    )
    + "\n",
    ".claude-plugin/plugin.json": json.dumps(
        {
            "name": "senzing-bootcamp-claude",
            "version": "0.4.9",
            "description": "Guided Senzing entity resolution bootcamp.",
            "license": "MIT",
        },
        indent=2,
    )
    + "\n",
}


def _release_source(root: Path) -> Path:
    """A resolved release tree the contract can be executed over."""
    contract = load_contract()
    source = root / "release"
    plugin_root = (
        source.joinpath(*contract.plugin_root.split("/"))
        if contract.plugin_root
        else source
    )
    for relative, text in SOURCE_DOCUMENTS.items():
        document = plugin_root / relative
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text(text, encoding="utf-8")
    return source


def _build_into(staging: Path, source: Path, *, tag: str = BUILD_TAG) -> StagingResult:
    """Run the build the way both skills run it: into staging, and only there."""
    contract = load_contract()
    result = write_staging(build_plan(contract, source, tag=tag, staging=staging))
    assert len(result.outputs) > 1, "the build produced no tree to publish"
    assert result.manifest_path.is_file(), "the build emitted no Build_Manifest"
    return result


def _read_tree(root: Path) -> dict[str, bytes]:
    """Every file under `root`, keyed by its POSIX-relative path.

    Byte-for-byte, because "the same file names" and "unchanged" are different
    claims and R4 AC6 asks for the second one.
    """
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _existing_power(target: Path) -> dict[str, bytes]:
    """A Power already at the target, and its bytes. Returns the snapshot.

    Non-empty is what makes it a conflict *(R4 AC5)*, and the two documents the
    pre-flight step reads are the ones a Maintainer is shown: `plugin.json` for
    the current version, `.build-manifest.json` for the release of the last
    successful build. The skill file is there so the tree is more than the two
    documents the report quotes.
    """
    target.mkdir(parents=True)
    (target / "plugin.json").write_text(
        json.dumps(
            {
                "name": "senzing-bootcamp",
                "version": PRIOR_TAG,
                "license": "Apache-2.0",
                "extensions": {
                    EXTENSION_NAMESPACE: {TEMPLATE_RELEASE_FIELD: PRIOR_TAG}
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (target / MANIFEST_FILENAME).write_text(
        json.dumps({"manifestVersion": 1, "templateRelease": PRIOR_TAG, "files": []})
        + "\n",
        encoding="utf-8",
    )
    local = target / "skills" / "bootcamp-onboarding"
    local.mkdir(parents=True)
    (local / "SKILL.md").write_text(
        "---\nname: bootcamp-onboarding\n---\n\nA locally adapted skill.\n",
        encoding="utf-8",
    )
    snapshot = _read_tree(target)
    assert snapshot, "the existing Power is empty, so it is not a conflict"
    return snapshot


def _asides(parent: Path) -> tuple[str, ...]:
    """Move-aside directories a failed swap left behind.

    The swap renames an old tree into a private sibling before it moves the new
    one in, so one of these surviving is residue holding a whole Power — worse
    than a leftover staging tree, and invisible to a comparison of the target
    alone.
    """
    if not parent.is_dir():
        return ()
    return tuple(
        sorted(entry.name for entry in parent.iterdir() if ".replaced-" in entry.name)
    )


#: `chmod` denies root nothing, so the denial cases would pass there without
#: having denied anything.
_UNPRIVILEGED = getattr(os, "geteuid", lambda: -1)() != 0
requires_unprivileged = pytest.mark.skipif(
    not _UNPRIVILEGED,
    reason="chmod-based write denial does not apply to root",
)


@contextmanager
def _write_denied(directory: Path) -> Iterator[None]:
    """Deny writes to `directory` for the duration, then restore its mode.

    Restoring in a `finally` is not tidiness: pytest removes `tmp_path`, and a
    directory left unwritable fails a later run for a reason unrelated to
    anything under test.
    """
    original = directory.stat().st_mode
    os.chmod(directory, 0o500)
    try:
        if os.access(directory, os.W_OK):
            pytest.skip("this filesystem does not enforce chmod-based write denial")
        yield
    finally:
        os.chmod(directory, original)


# --- An existing Power: the conflict, and the decline (R4 AC5, AC6) --------


def test_the_conflict_report_names_the_target_and_precedes_every_write() -> None:
    """The conflict names `powers/senzing-bootcamp/`, and asks first *(R4 AC5)*.

    The pre-flight check is the one part of this orchestration with no engine
    behind it — a look at the target and a question — so what is checkable is
    the skill's own text: it names the path exactly, it names both outcomes, and
    the question comes before the first command that writes anything. The tests
    below carry the enforceable half.
    """
    text = (REPO_ROOT / CREATE_SKILL_PATH).read_text(encoding="utf-8")

    conflict = text.index("E_TARGET_EXISTS")
    declined = text.index("E_OVERWRITE_DECLINED")
    build = text.index(f"--staging {STAGING_RELATIVE}")
    swap = text.index("swap_into_place")

    assert TARGET_REPORTED in text[conflict:declined], (
        f"the conflict must name {TARGET_REPORTED} exactly, so a Maintainer reads "
        "which directory is already occupied"
    )
    assert conflict < declined < build < swap, (
        "the conflict and the decline must both come before the build and the "
        "swap; a confirmation asked after content is written is not a "
        "confirmation before modifying anything"
    )


def test_a_build_over_an_existing_power_writes_only_into_staging(
    tmp_path: Path,
) -> None:
    """Confirmation or not, the build reaches staging and not the target *(R4 AC5)*.

    This is what makes "requires explicit confirmation before modifying any
    existing content" true of the machinery rather than of the wording: the
    stages before the swap have no path to the target, so a run held at the
    confirmation question has nothing to roll back.
    """
    repository = tmp_path / "repository"
    target = repository / TARGET_RELATIVE
    staging = repository / STAGING_RELATIVE
    before = _existing_power(target)

    result = _build_into(staging, _release_source(tmp_path))
    staged = _read_tree(staging)

    assert _read_tree(target) == before, "the build modified the existing Power"
    assert MANIFEST_FILENAME in staged
    assert result.manifest.template_release == BUILD_TAG
    # The staged tree is a different release from the one on disk, and none of it
    # arrived: the target still records the release of its own last build.
    assert (
        json.loads(staged[MANIFEST_FILENAME])["templateRelease"] == BUILD_TAG
    )
    assert json.loads(before[MANIFEST_FILENAME])["templateRelease"] == PRIOR_TAG
    assert _asides(target.parent) == ()


def test_the_declined_overwrite_terminates_with_the_power_byte_identical(
    tmp_path: Path,
) -> None:
    """Declining discards staging and leaves the Power exactly as it was *(R4 AC6)*.

    A decline is a termination, not a rollback: the swap is simply never called,
    and discarding the staging tree removes the only thing the run created. The
    tree is compared byte-for-byte, and the target's parent is compared too — a
    Power that survived beside a leftover staging directory is not a repository
    left as it was found.
    """
    repository = tmp_path / "repository"
    target = repository / TARGET_RELATIVE
    staging = repository / STAGING_RELATIVE
    before = _existing_power(target)
    _build_into(staging, _release_source(tmp_path))

    discard_staging(staging)

    assert not staging.exists(), "the declined run left a staging tree behind"
    assert _read_tree(target) == before
    assert sorted(entry.name for entry in target.parent.iterdir()) == [target.name], (
        "the declined run left something beside the Power"
    )
    assert _asides(target.parent) == ()


# --- An absent target: created at swap time, and only then (R14 AC4) -------


@pytest.mark.parametrize("staging_at", ["sibling", "outside"])
def test_an_absent_target_directory_is_created_at_swap_time(
    tmp_path: Path, staging_at: str
) -> None:
    """Nothing exists at the target until the swap creates it *(R14 AC4)*.

    Both arrangements, because they observe different halves of the claim. With
    the staging directory a sibling — as both skills direct, so the rename cannot
    cross a filesystem — the parent necessarily exists and what is observable is
    that the target itself does not. With staging elsewhere, the parent is absent
    through the whole build and the swap creates it. Every path here is under one
    `tmp_path` and so on one filesystem either way, which is the only thing the
    sibling rule is about.
    """
    repository = tmp_path / "repository"
    target = repository / TARGET_RELATIVE
    staging = (
        repository / STAGING_RELATIVE
        if staging_at == "sibling"
        else tmp_path / "build" / "staging"
    )

    result = _build_into(staging, _release_source(tmp_path))
    staged = _read_tree(staging)

    assert not target.exists(), (
        "the target was created before the swap, so a build that failed here "
        "would leave an empty directory as evidence of a Power that was never "
        "published"
    )
    if staging_at == "outside":
        assert not target.parent.exists(), "the target's parent was created early"
    else:
        assert sorted(entry.name for entry in target.parent.iterdir()) == [
            staging.name
        ]

    swap = swap_into_place(staging, target)

    assert swap.replaced is False, "nothing was there to replace"
    assert swap.to_json()["status"] == "swapped"
    assert target.is_dir()
    assert _read_tree(target) == staged
    assert MANIFEST_FILENAME in staged
    assert [output.path for output in result.outputs] == sorted(
        path for path in staged if path != MANIFEST_FILENAME
    )
    assert not staging.exists(), "the swap consumes the staging tree"
    assert _asides(target.parent) == ()


# --- A target that cannot be written: E_WRITE_FAILED (R14 AC5) -------------


@pytest.mark.parametrize("where", ["target", "parent"])
def test_a_file_where_a_directory_belongs_is_a_write_failure(
    tmp_path: Path, where: str
) -> None:
    """A file at the target, or at its parent, is `E_WRITE_FAILED` *(R14 AC5)*.

    Two positions, because the swap has to look at both: it creates the parent
    when absent, so a file there is a directory it cannot create, and it replaces
    the target, so a file there is a directory it cannot replace. Neither is
    deleted to make room — a file the engine did not write is content it does not
    own — and the staging tree is discarded, leaving no residue either way.
    """
    repository = tmp_path / "repository"
    target = repository / TARGET_RELATIVE
    staging = tmp_path / "build" / "staging"
    _build_into(staging, _release_source(tmp_path))

    occupied = target if where == "target" else target.parent
    occupied.parent.mkdir(parents=True, exist_ok=True)
    occupied.write_bytes(b"a regular file, not a directory\n")
    before = occupied.read_bytes()

    with pytest.raises(TransformError) as raised:
        swap_into_place(staging, target)

    error = raised.value
    assert error.code == E_WRITE_FAILED
    assert error.details["target"] == str(target)
    assert "not a directory" in error.message
    assert error.to_json()["error"] == E_WRITE_FAILED
    assert occupied.is_file() and occupied.read_bytes() == before
    assert not staging.exists(), "the failed swap left a staging tree behind"
    assert _asides(repository) == ()


def test_a_staging_path_that_is_a_file_is_a_write_failure(tmp_path: Path) -> None:
    """A build refuses a staging path it cannot own *(R14 AC5)*.

    The refusal is what lets the failure path delete the whole staging tree
    without ever destroying content the engine did not create — so the file keeps
    its bytes, and the Power on disk is untouched because the build never got as
    far as producing anything.
    """
    repository = tmp_path / "repository"
    target = repository / TARGET_RELATIVE
    before = _existing_power(target)
    staging = repository / STAGING_RELATIVE
    staging.write_bytes(b"a regular file, not a staging directory\n")
    occupied = staging.read_bytes()

    with pytest.raises(TransformError) as raised:
        write_staging(
            build_plan(
                load_contract(),
                _release_source(tmp_path),
                tag=BUILD_TAG,
                staging=staging,
            )
        )

    error = raised.value
    assert error.code == E_WRITE_FAILED
    assert error.details["staging"] == str(staging)
    assert staging.is_file() and staging.read_bytes() == occupied
    assert _read_tree(target) == before


@requires_unprivileged
@pytest.mark.parametrize("prior", ["absent", "existing-power"])
def test_a_swap_into_an_unwritable_parent_is_a_write_failure(
    tmp_path: Path, prior: str
) -> None:
    """A real permission denial at the target is `E_WRITE_FAILED` *(R14 AC5)*.

    Both priors, because the swap denies differently in each: with nothing there
    it is the move-new-in that is refused, and with a Power there it is the
    move-old-aside — which is the more important of the two, since a denial
    partway through publishing is exactly the moment a Power could be lost. It is
    not: the tree that was there is still there, byte for byte, and no move-aside
    directory survives holding it.
    """
    repository = tmp_path / "repository"
    parent = repository / TARGET_RELATIVE.rsplit("/", 1)[0]
    target = repository / TARGET_RELATIVE
    parent.mkdir(parents=True)
    before = _existing_power(target) if prior == "existing-power" else {}
    # Built outside the denied directory, so the build itself is not what fails.
    staging = tmp_path / "build" / "staging"
    _build_into(staging, _release_source(tmp_path))

    with _write_denied(parent):
        with pytest.raises(TransformError) as raised:
            swap_into_place(staging, target)

        error = raised.value
        assert error.code == E_WRITE_FAILED
        assert error.details["target"] == str(target)
        assert error.details["staging"] == str(staging)
        assert _read_tree(target) == before
        assert (target.is_dir() is (prior == "existing-power"))
        assert _asides(parent) == ()

    assert not staging.exists(), "the failed swap left a staging tree behind"
    assert _read_tree(target) == before


@requires_unprivileged
def test_a_build_that_cannot_create_its_staging_directory_is_a_write_failure(
    tmp_path: Path,
) -> None:
    """A denial where staging would go halts the build *(R14 AC5)*.

    Staging is a sibling of the target, so a directory the Maintainer cannot
    write is a directory neither the build nor the swap can use — and the build
    is where that is discovered, before anything has been produced. The
    repository is left exactly as it was found.
    """
    repository = tmp_path / "repository"
    parent = repository / TARGET_RELATIVE.rsplit("/", 1)[0]
    target = repository / TARGET_RELATIVE
    parent.mkdir(parents=True)
    before = _existing_power(target)
    staging = repository / STAGING_RELATIVE
    source = _release_source(tmp_path)

    with _write_denied(parent):
        with pytest.raises(TransformError) as raised:
            write_staging(
                build_plan(load_contract(), source, tag=BUILD_TAG, staging=staging)
            )

        error = raised.value
        assert error.code == E_WRITE_FAILED
        assert error.details["staging"] == str(staging)
        assert not staging.exists()
        assert _read_tree(target) == before
        assert sorted(entry.name for entry in parent.iterdir()) == [target.name]


# ===========================================================================
# 6. The changelog is unrecorded, and only the changelog — R5 AC8, R16 AC9
# ===========================================================================

import json

from reconcile import CHANGELOG_FILENAME, apply_to_staging, reconcile_directories
from transform import MANIFEST_VERSION, OWNER_TEMPLATE, sha256_hex
from validate import (
    DRIFT_ABSENT,
    DRIFT_CONTENT,
    DRIFT_UNRECORDED,
    E_HASH_MISMATCH,
    MANIFEST_UNRECORDED,
    compare_manifest,
)

#
# Two requirements meet on one file and used to contradict each other. R5 AC8 has
# a successful update append one changelog entry naming its source
# Template_Release; `reconcile.record_update_in_staging` writes that entry into
# `<staging>/CHANGELOG.md` **after** `transform` has already emitted the
# Build_Manifest, and the reconciler carries that manifest forward verbatim. R16
# AC9 has the Schema_Validator report every file whose hash disagrees with the
# manifest — including, before this allowance, every file the manifest does not
# record at all. So the very file R5 AC8 requires made `manifest-hashes` fail, and
# the update path could not produce a report with `tagAllowed` true.
#
# The allowance is narrow on purpose, and both halves of "narrow" are tested here:
# the changelog is tolerated, and anything else unrecorded is still reported. A
# blanket "ignore unrecorded files" would have silently readmitted the drift the
# check exists to catch.
#
# These are unit tests rather than property cases because the subject is one named
# file and one boolean about it; `Property 24` already drives the hash comparison
# over generated trees.

#: A minimal Build_Manifest: one recorded file, so `compare_manifest` has both a
#: recorded side and a tree side to disagree about.
_RECORDED_PATH = "skills/bootcamp-onboarding/SKILL.md"
_RECORDED_BYTES = b"---\nname: bootcamp-onboarding\n---\n\n# Onboarding\n"


def _manifest_document(*records: Mapping[str, Any]) -> dict[str, Any]:
    """A Build_Manifest document in the shape `transform.BuildManifest` writes."""
    return {
        "manifestVersion": MANIFEST_VERSION,
        "templateRelease": BUILD_TAG,
        "contractVersion": 1,
        "files": list(records),
    }


def _write(path: Path, data: bytes) -> None:
    """Write `data` at `path`, creating the directories above it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    """Write `document` as UTF-8 JSON with LF endings, as the engine does."""
    _write(path, (json.dumps(document, indent=2) + "\n").encode("utf-8"))


def _recorded_manifest() -> dict[str, Any]:
    """A manifest recording exactly `_RECORDED_PATH`."""
    return _manifest_document(
        {
            "path": _RECORDED_PATH,
            "ruleId": "skill-onboarding",
            "owner": OWNER_TEMPLATE,
            "sourcePath": f"plugins/senzing-bootcamp/{_RECORDED_PATH}",
            "sha256": sha256_hex(_RECORDED_BYTES),
        }
    )


def test_the_changelog_and_the_manifest_are_the_two_files_a_manifest_never_records():
    """The allowance is exactly two names, and both are named by their writers.

    Spelled through the constants the writing modules export rather than as
    literals, so renaming either file cannot leave this allowance pointing at a
    path nothing produces.
    """
    assert MANIFEST_UNRECORDED == (MANIFEST_FILENAME, CHANGELOG_FILENAME)


def test_an_accumulated_changelog_is_not_reported_as_manifest_drift():
    """A Power carrying the entry R5 AC8 requires still passes `manifest-hashes`.

    The regression this file exists for: with the changelog reported as unrecorded
    drift, every update produced `E_HASH_MISMATCH` on `CHANGELOG.md`, the report
    read `failed`, and the update skill's own instructions were then to discard the
    staging tree — so no update could ever be published.

    Two entries, not one, because the accumulation is the point: the file's content
    is a function of the Power's history rather than of the release being built, and
    that is *why* no build can record a hash for it.
    """
    changelog = (
        b"## 0.5.3\n\nUpdated from Template_Release `0.5.1` to `0.5.3`.\n"
        b"\n## 0.5.4\n\nUpdated from Template_Release `0.5.3` to `0.5.4`.\n"
    )
    comparison = compare_manifest(
        _recorded_manifest(),
        {
            _RECORDED_PATH: _RECORDED_BYTES,
            CHANGELOG_FILENAME: changelog,
        },
    )
    assert comparison.findings == (), (
        "a Power carrying its accumulated changelog reports manifest drift: "
        + "; ".join(finding.message for finding in comparison.findings)
    )
    assert comparison.matched == (_RECORDED_PATH,)
    # Tolerated, not compared: there is no recorded hash to compare it against.
    assert CHANGELOG_FILENAME not in comparison.compared


def test_any_other_unrecorded_file_is_still_reported_as_drift():
    """The allowance did not become "ignore unrecorded files" *(R16 AC9)*.

    A stray file in the tree is the case the unrecorded check was written for — a
    ported script run in place leaving `__pycache__`, a hand-added document, a
    half-finished edit — and it stays a fail. The changelog beside it is tolerated
    in the same run, so the two rules are shown to be independent rather than one
    loosened rule.
    """
    stray = "skills/bootcamp-onboarding/scripts/notes.txt"
    comparison = compare_manifest(
        _recorded_manifest(),
        {
            _RECORDED_PATH: _RECORDED_BYTES,
            CHANGELOG_FILENAME: b"## 0.5.3\n",
            stray: b"scratch\n",
        },
    )
    assert [finding.target for finding in comparison.findings] == [stray]
    finding = comparison.findings[0]
    assert finding.code == E_HASH_MISMATCH
    assert finding.details["kind"] == DRIFT_UNRECORDED
    assert finding.details["actualSha256"] == sha256_hex(b"scratch\n")


def test_the_manifest_still_reports_a_recorded_file_that_changed_or_vanished():
    """Neither allowance weakened the comparison it was carved out of *(R16 AC9)*.

    The two failure modes the check owes a recorded file — different bytes, and
    absent altogether — are asserted in the presence of a changelog, so the
    allowance is shown not to short-circuit the loop it sits beside.
    """
    edited = compare_manifest(
        _recorded_manifest(),
        {_RECORDED_PATH: b"hand-edited\n", CHANGELOG_FILENAME: b"## 0.5.3\n"},
    )
    assert [finding.target for finding in edited.findings] == [_RECORDED_PATH]
    assert edited.findings[0].code == E_HASH_MISMATCH
    assert edited.findings[0].details["kind"] == DRIFT_CONTENT

    vanished = compare_manifest(
        _recorded_manifest(), {CHANGELOG_FILENAME: b"## 0.5.3\n"}
    )
    assert [finding.target for finding in vanished.findings] == [_RECORDED_PATH]
    assert vanished.findings[0].details["kind"] == DRIFT_ABSENT


def test_the_reconciler_preserves_an_unrecorded_changelog_across_an_update(
    tmp_path: Path,
) -> None:
    """The other half of the fix: leaving it unrecorded is what keeps the history.

    This is the classification the allowance depends on, asserted directly rather
    than reasoned about. With no manifest entry, the Power's changelog has no
    baseline, upstream produces none, and the reconciler's
    `local-only-no-template-source` row preserves it — so entry one survives to sit
    above entry two.

    Had the manifest recorded it, the same file would have matched `previous ==
    on-disk` with `staging` absent, which is the `removed` row: `apply` would delete
    the accumulated changelog and the next `--changelog` would append entry two to
    an empty file. That is the failure this test would catch.
    """
    power = tmp_path / "senzing-bootcamp"
    staging = tmp_path / ".senzing-bootcamp.staging"
    for directory in (power, staging):
        directory.mkdir()

    existing = b"## 0.5.3\n\nUpdated from Template_Release `0.5.1` to `0.5.3`.\n"
    _write(power / CHANGELOG_FILENAME, existing)
    _write(power / _RECORDED_PATH, _RECORDED_BYTES)
    _write(staging / _RECORDED_PATH, _RECORDED_BYTES)
    _write_json(power / MANIFEST_FILENAME, _recorded_manifest())
    _write_json(staging / MANIFEST_FILENAME, _recorded_manifest())

    report = reconcile_directories(power, staging, to_release="0.5.4")
    preserved = {item.path: item for item in report.preserved_adaptations}
    assert CHANGELOG_FILENAME in preserved, (
        "the changelog was not preserved; it landed in "
        f"{ {bucket: paths for bucket, paths in report.buckets().items() if CHANGELOG_FILENAME in paths} }"
    )
    assert preserved[CHANGELOG_FILENAME].reason == "local-only-no-template-source"

    apply_to_staging(report, power, staging)
    assert (staging / CHANGELOG_FILENAME).read_bytes() == existing, (
        "the Power's changelog did not survive into the staging tree, so the "
        "atomic swap would publish a Power that lost its history"
    )


# ===========================================================================
# 7. Naming a release instead of taking the maximum — R1 AC1, AC3, AC5
# ===========================================================================

from resolve_release import (
    E_TAG_NOT_FOUND,
    find_release,
    ineligibility_reason,
    is_eligible,
)

# `--tag` exists because the semver maximum is not always the release a
# Maintainer needs. Two situations make that concrete, and both had no answer
# before it:
#
#   * **Stepping.** Between two update runs upstream may publish more than one
#     release. Taking the maximum jumps over the ones in between, so those
#     Template_Releases can never have a matching Bootcamp_Power — which is the
#     version-pairing the whole repository exists to maintain.
#   * **Rebuilding.** Reproducing a past Power means building the release it came
#     from, which is by definition not the maximum any more.
#
# What must NOT change is everything else. `--tag` replaces the *selection* step
# and nothing else: the eligibility filter still applies, so naming a draft or a
# prerelease is refused rather than obeyed, and the fetch is still the tag ref, so
# a named build of a release is the same build that release would have produced
# when it was the maximum. These tests pin both halves — what it changes, and what
# it leaves alone.

#: A release list with a maximum, an older selectable release, and one record for
#: each way a release can be disqualified. The reasons are tested by name, so each
#: disqualifying flag needs a record that trips only that one.
NAMED_RELEASES: tuple[Mapping[str, Any], ...] = (
    {
        "tagName": "0.5.3",
        "isDraft": False,
        "isPrerelease": False,
        "publishedAt": "2025-03-01T00:00:00Z",
    },
    {
        "tagName": "0.5.1",
        "isDraft": False,
        "isPrerelease": False,
        "publishedAt": "2025-01-01T00:00:00Z",
    },
    {
        "tagName": "0.6.0",
        "isDraft": True,
        "isPrerelease": False,
        "publishedAt": "2025-04-01T00:00:00Z",
    },
    {
        "tagName": "0.5.4",
        "isDraft": False,
        "isPrerelease": True,
        "publishedAt": "2025-02-01T00:00:00Z",
    },
    {
        "tagName": "0.5.5",
        "isDraft": False,
        "isPrerelease": False,
        "publishedAt": None,
    },
    {
        "tagName": "v0.5.6",
        "isDraft": False,
        "isPrerelease": False,
        "publishedAt": "2025-02-15T00:00:00Z",
    },
)

#: The subset of `NAMED_RELEASES` a Maintainer may name, in list order.
SELECTABLE_TAGS = ("0.5.3", "0.5.1")


def _named_resolve(
    out_dir: Path,
    tag: str,
    *,
    records: Sequence[Mapping[str, Any]] = NAMED_RELEASES,
) -> tuple[dict[str, Any] | ResolutionError, CountingFetcher]:
    """Run `resolve(tag=...)`, returning either the record or the raised error."""
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    lister = SequenceLister(clock, hangs=0, records=records)
    fetcher = CountingFetcher(out_dir / f"bootcamp-src-{tag}")
    try:
        payload = resolve(
            out_dir=out_dir,
            repository="Senzing/senzing-bootcamp-claude-plugin",
            tag=tag,
            lister=lister,
            fetcher=fetcher,
            clock=clock,
            sleeper=sleeper,
        )
    except ResolutionError as error:
        return error, fetcher
    return payload, fetcher


def test_a_named_release_is_resolved_instead_of_the_maximum(tmp_path: Path) -> None:
    """`--tag` resolves the release asked for, not the newest one *(R1 AC1, AC5)*.

    `0.5.3` is the maximum in the list and `0.5.1` is named, so a resolver that
    quietly kept selecting the maximum would pass every other assertion here.
    """
    payload, fetcher = _named_resolve(tmp_path, "0.5.1")

    assert isinstance(payload, dict), f"resolve raised instead of resolving: {payload}"
    assert payload["tag"] == "0.5.1"
    assert payload["semver"] == [0, 5, 1]
    assert "error" not in payload
    # R1 AC3 is unchanged by naming: the tag ref, never a branch.
    assert payload["sourceRef"] == "refs/tags/0.5.1"
    assert fetcher.calls == 1


def test_naming_a_release_never_reports_already_current(tmp_path: Path) -> None:
    """Rebuilding what the Power already has is a decision, not a no-op *(R5 AC2)*.

    `E_ALREADY_CURRENT` answers "is there anything newer?", and naming a release
    does not ask it. Were the two paths to share that check, the older release a
    Maintainer named to reproduce a past Power would be refused as stale — the
    exact case `--tag` was added for.
    """
    payload, fetcher = _named_resolve(tmp_path, "0.5.1")

    assert isinstance(payload, dict)
    assert payload.get("error") is None
    assert fetcher.calls == 1, (
        "naming an older release fetched nothing, so it was treated as "
        "already-current rather than as a rebuild"
    )


def test_naming_an_absent_release_reports_tag_not_found(tmp_path: Path) -> None:
    """A tag upstream does not carry halts the build and lists what it does.

    The list is in the message because the realistic cause is a typo or a
    misremembered version, and a bare refusal leaves a Maintainer querying GitHub
    by hand to find that out.
    """
    error, fetcher = _named_resolve(tmp_path, "9.9.9")

    assert isinstance(error, ResolutionError), "an absent tag resolved successfully"
    assert error.code == E_TAG_NOT_FOUND
    assert "9.9.9" in error.message
    for tag in SELECTABLE_TAGS:
        assert tag in error.message, f"the refusal does not offer {tag}"
    # R1 AC4's rule, applied to this code as well: no artifact on a failure.
    assert fetcher.calls == 0
    assert error.payload()["error"] == E_TAG_NOT_FOUND


@pytest.mark.parametrize(
    ("tag", "reason"),
    [
        ("0.6.0", "is a draft"),
        ("0.5.4", "is a prerelease"),
        ("0.5.5", "is not published"),
    ],
)
def test_naming_an_ineligible_release_is_refused_with_its_reason(
    tmp_path: Path, tag: str, reason: str
) -> None:
    """Naming a release does not override the eligibility filter *(R1 AC1, AC2)*.

    R1 AC1 restricts what may be *sourced*, not merely what is *picked* when
    several are available, so an explicit `--tag` cannot opt into a draft. The
    reason travels in the message because "not found" would be misleading for a
    tag the Maintainer can plainly see on the releases page.
    """
    error, fetcher = _named_resolve(tmp_path, tag)

    assert isinstance(error, ResolutionError), f"{tag} was built despite being {reason}"
    assert error.code == E_TAG_NOT_FOUND
    assert reason in error.message, (
        f"the refusal of {tag} does not say it {reason}: {error.message}"
    )
    assert tag in error.message
    assert fetcher.calls == 0


def test_a_non_semver_tag_is_rejected_before_any_query(tmp_path: Path) -> None:
    """A `v` prefix is a `ValueError`, not a resolution outcome *(R2 AC1)*.

    The resolved tag is stamped into `plugin.json` character-for-character, so
    `v0.5.6` would produce a version string the Agent Plugins schema rejects. That
    is an input fault rather than a fact about upstream, and it is caught before a
    release is listed — which is also why `v0.5.6` sits in `NAMED_RELEASES` and is
    unreachable through `--tag` from either direction.
    """
    with pytest.raises(ValueError, match="bare semver"):
        resolve(
            out_dir=tmp_path,
            repository="Senzing/senzing-bootcamp-claude-plugin",
            tag="v0.5.6",
            lister=lambda timeout: list(NAMED_RELEASES),
            fetcher=CountingFetcher(),
        )


def test_naming_a_release_and_naming_a_floor_are_mutually_exclusive(
    tmp_path: Path,
) -> None:
    """Both together is refused rather than given a precedence.

    A precedence would make one of the two arguments silently ineffective, and the
    two ask different questions: a floor asks whether anything newer exists, a tag
    has already decided. The CLI enforces the same thing through an argparse
    mutually exclusive group, so this can only be reached programmatically.
    """
    with pytest.raises(ValueError, match="mutually exclusive"):
        resolve(
            out_dir=tmp_path,
            repository="Senzing/senzing-bootcamp-claude-plugin",
            min_version="0.5.1",
            tag="0.5.3",
            lister=lambda timeout: list(NAMED_RELEASES),
            fetcher=CountingFetcher(),
        )


def test_the_eligibility_rules_have_one_home():
    """`is_eligible` is `ineligibility_reason`'s boolean, record for record.

    The filter drops a record silently and `--tag` has to explain itself, so both
    read the same rules. Two copies would eventually refuse for one reason and
    report another — the failure mode this asserts away.
    """
    for record in NAMED_RELEASES:
        reason = ineligibility_reason(record)
        assert is_eligible(record) is (reason is None), (
            f"{record['tagName']}: is_eligible and ineligibility_reason disagree "
            f"({is_eligible(record)} vs {reason!r})"
        )
        if reason is not None:
            assert reason.strip() == reason and reason, "a reason must be readable"

    assert [
        record["tagName"] for record in NAMED_RELEASES if is_eligible(record)
    ] == list(SELECTABLE_TAGS)


def test_a_named_tag_is_matched_exactly_not_by_version_equality():
    """`find_release` matches the tag string, not the version it denotes.

    `0.05.1` and `0.5.1` parse to the same version and are different refs, and only
    the one upstream actually published can be fetched. Matching by version would
    resolve a tag that does not exist and fail later, at the clone.
    """
    records = [
        {
            "tagName": "0.05.1",
            "isDraft": False,
            "isPrerelease": False,
            "publishedAt": "2025-01-01T00:00:00Z",
        }
    ]
    assert find_release(records, "0.05.1") is records[0]
    assert find_release(records, "0.5.1") is None
    assert find_release([], "0.5.1") is None

    # An ineligible record is returned rather than filtered out: that is what lets
    # the refusal say "is a draft" instead of "no such release".
    draft = find_release(NAMED_RELEASES, "0.6.0")
    assert draft is not None and ineligibility_reason(draft) == "is a draft"
