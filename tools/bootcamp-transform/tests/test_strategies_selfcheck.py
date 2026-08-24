"""Scaffolding check: every edge case the design lists is actually emitted.

`strategies.py` is a dependency of nearly every property test, so a generator
that quietly stopped producing its listed edge case would weaken those tests
without failing any of them. This file draws from each *named* case and asserts
the characteristic that names it — that `release_list()["empty"]` really is
empty, that `interpreter_path()` really puts a `>` inside a directory name.

This is a scaffolding check, not a property test: the design's 100-example
floor applies to the 25 correctness properties, and these draws are cheap
confirmations of generator coverage rather than statements about the system, so
they run a handful of examples each.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import strategies as gen

_EXAMPLES = 15


def _run(strategy: st.SearchStrategy[Any], predicate: Callable[[Any], bool]) -> None:
    @settings(
        max_examples=_EXAMPLES,
        deadline=None,
        database=None,
        print_blob=False,
        suppress_health_check=list(HealthCheck),
    )
    @given(strategy)
    def check(value: Any) -> None:
        assert predicate(value), repr(value)

    check()


def _cases(
    strategies: Mapping[str, st.SearchStrategy[Any]],
    predicates: Mapping[str, Callable[[Any], bool]],
) -> list[tuple[str, st.SearchStrategy[Any], Callable[[Any], bool]]]:
    """Pair each named case with its predicate, failing on any case with none."""
    assert set(strategies) == set(predicates), (
        f"unchecked cases: {sorted(set(strategies) ^ set(predicates))}"
    )
    return [(name, strategies[name], predicates[name]) for name in sorted(strategies)]


def _fenced_lines(text: str) -> list[str]:
    inside, fenced = False, []
    for line in text.splitlines():
        if line.startswith("```"):
            inside = not inside
            continue
        if inside:
            fenced.append(line)
    return fenced


def _contains_phrase(text: str) -> bool:
    return any(phrase in text for phrase in gen.TRIGGER_PHRASES.values())


def _eligible_max(records: list[dict[str, Any]]) -> str | None:
    eligible = [
        record["tagName"]
        for record in records
        if not record["isDraft"] and not record["isPrerelease"]
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda tag: tuple(int(part) for part in tag.split(".")))


# ---------------------------------------------------------------------------
# 1. release_list()
# ---------------------------------------------------------------------------

_RELEASE_LIST_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "empty": lambda records: records == [],
    "all_draft": lambda records: bool(records)
    and all(record["isDraft"] for record in records),
    "all_prerelease": lambda records: bool(records)
    and all(record["isPrerelease"] for record in records),
    "semver_vs_lexicographic": lambda records: {r["tagName"] for r in records}
    == {"0.9.0", "0.10.0"}
    and _eligible_max(records) == "0.10.0",
    "duplicate_tags": lambda records: len(records) == 2
    and len({r["tagName"] for r in records}) == 1,
    "zero_padded": lambda records: {r["tagName"] for r in records}
    == {"0.5.1", "0.05.1"},
    "higher_tag_ineligible": lambda records: _eligible_max(records) == "0.5.1",
    "mixed": lambda records: isinstance(records, list),
}


@pytest.mark.parametrize(
    "name,strategy,predicate",
    _cases(gen.RELEASE_LIST_CASES, _RELEASE_LIST_PREDICATES),
)
def test_release_list_cases(name, strategy, predicate):
    _run(strategy, predicate)


# ---------------------------------------------------------------------------
# 2. template_tree()
# ---------------------------------------------------------------------------

_KNOWN_PREFIXES = ("skills/", "scripts/", "docs/")


def _has_unmatched_path(tree: Mapping[str, gen.TreeEntry]) -> bool:
    return any(
        not path.startswith(_KNOWN_PREFIXES) and path not in gen.IGNORED_TEMPLATE_PATHS
        for path in tree
    )


def _is_absolute_looking(path: str) -> bool:
    return path.startswith(("/", "\\\\")) or re.match(r"^[A-Za-z]:[\\/]", path) is not None


_TEMPLATE_TREE_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "wellformed": lambda tree: bool(tree) and not _has_unmatched_path(tree),
    "unmatched_path": _has_unmatched_path,
    "nested_vendor": lambda tree: any(
        path.startswith("scripts/vendor/") and path.count("/") > 2 for path in tree
    ),
    "binary_asset": lambda tree: any(
        entry.kind == "binary" and path.endswith(".png") for path, entry in tree.items()
    ),
    "empty_file": lambda tree: any(
        entry.kind == "empty" and entry.content == b"" for entry in tree.values()
    ),
    "unicode_filename": lambda tree: any(not path.isascii() for path in tree),
    "dotdot_segment": lambda tree: any(".." in path.split("/") for path in tree),
    "absolute_looking_path": lambda tree: any(
        _is_absolute_looking(path) for path in tree
    ),
    "symlink": lambda tree: any(
        entry.kind == "symlink" and entry.target for entry in tree.values()
    ),
}


@pytest.mark.parametrize(
    "name,strategy,predicate",
    _cases(gen.TEMPLATE_TREE_CASES, _TEMPLATE_TREE_PREDICATES),
)
def test_template_tree_cases(name, strategy, predicate):
    _run(strategy, predicate)


# ---------------------------------------------------------------------------
# 3. skill_tree()
# ---------------------------------------------------------------------------

_SKILL_TREE_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "parent_links": lambda case: any(
        reference.target.startswith("../") for reference in case.references
    ),
    "broken_links": lambda case: case.broken != (),
    "self_links": lambda case: any(
        reference.target == "SKILL.md" and reference.resolves
        for reference in case.references
    ),
    "references_links": lambda case: any(
        reference.target.startswith("references/") for reference in case.references
    ),
    "module_03b_names": lambda case: any(
        re.search(r"module-\d\db-", path) for path in case.files
    ),
    "mixed": lambda case: len(case.references) == 4,
    "no_links": lambda case: case.references == (),
}


@pytest.mark.parametrize(
    "name,strategy,predicate", _cases(gen.SKILL_TREE_CASES, _SKILL_TREE_PREDICATES)
)
def test_skill_tree_cases(name, strategy, predicate):
    _run(strategy, predicate)


def test_skill_tree_resolution_flags_match_the_file_set():
    def resolved_consistently(case: gen.SkillTreeCase) -> bool:
        import posixpath

        for reference in case.references:
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(reference.source), reference.target)
            )
            if reference.resolves != (target in case.files):
                return False
        return True

    _run(gen.skill_tree(), resolved_consistently)


# ---------------------------------------------------------------------------
# 4. frontmatter()
# ---------------------------------------------------------------------------


def _required_values(case: gen.FrontmatterCase) -> list[Any]:
    return [case.fields[key] for key in ("name", "description", "license") if key in case.fields]


_FRONTMATTER_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "valid": lambda case: case.valid
    and case.fields["name"] == case.directory
    and case.trigger_phrase in case.fields["description"]
    and len(case.fields["description"]) <= gen.MAX_DESCRIPTION_LENGTH
    and case.fields["license"].strip() != "",
    "missing_key": lambda case: len(_required_values(case)) == 2,
    "empty_string": lambda case: any(value == "" for value in _required_values(case)),
    "whitespace_only": lambda case: any(
        value != "" and value.strip() == "" for value in _required_values(case)
    ),
    "long_description": lambda case: len(case.fields["description"])
    > gen.MAX_DESCRIPTION_LENGTH,
    "name_directory_mismatch": lambda case: case.fields["name"] != case.directory,
}


@pytest.mark.parametrize(
    "name,strategy,predicate", _cases(gen.FRONTMATTER_CASES, _FRONTMATTER_PREDICATES)
)
def test_frontmatter_cases(name, strategy, predicate):
    _run(strategy, predicate)


def test_frontmatter_text_round_trips_through_yaml():
    def round_trips(case: gen.FrontmatterCase) -> bool:
        body = case.text.split("---\n")[1]
        return yaml.safe_load(body) == case.fields

    _run(gen.frontmatter(), round_trips)


# ---------------------------------------------------------------------------
# 5. file_content()
# ---------------------------------------------------------------------------

_FILE_CONTENT_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "zero_occurrences": lambda case: case.total_occurrences == 0,
    "one_occurrence": lambda case: 1 in case.occurrences.values(),
    "many_occurrences": lambda case: case.total_occurrences >= 3,
    "adjacent_tokens": lambda case: any(
        substitution.find * 2 in case.text for substitution in case.substitutions
    ),
    "tokens_in_code_fence": lambda case: any(
        substitution.find in line
        for line in _fenced_lines(case.text)
        for substitution in case.substitutions
    ),
    "invariant_references": lambda case: "INV-" in case.text,
}


@pytest.mark.parametrize(
    "name,strategy,predicate", _cases(gen.FILE_CONTENT_CASES, _FILE_CONTENT_PREDICATES)
)
def test_file_content_cases(name, strategy, predicate):
    _run(strategy, predicate)


def test_file_content_counts_match_the_text():
    def counts_match(case: gen.FileContentCase) -> bool:
        return all(
            case.text.count(find) == count for find, count in case.occurrences.items()
        )

    _run(gen.file_content(), counts_match)


# ---------------------------------------------------------------------------
# 6. mcp_document()
# ---------------------------------------------------------------------------


def _senzing_server(case: gen.McpDocumentCase) -> Mapping[str, Any]:
    return case.document.get("mcpServers", {}).get("senzing", {})


_MCP_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "valid": lambda case: case.valid
    and case.document["$schema"] == gen.MCP_SCHEMA_URL
    and _senzing_server(case)["url"] == gen.SENZING_MCP_URL
    and _senzing_server(case)["type"] == gen.MCP_TRANSPORT_TYPE,
    "near_miss_url": lambda case: _senzing_server(case)["url"] != gen.SENZING_MCP_URL,
    "wrong_type": lambda case: _senzing_server(case)["type"] != gen.MCP_TRANSPORT_TYPE,
    "missing_schema": lambda case: "$schema" not in case.document,
    "missing_senzing_server": lambda case: "senzing" not in case.document["mcpServers"],
    "multiple_defects": lambda case: len(case.defects) >= 2,
}


@pytest.mark.parametrize(
    "name,strategy,predicate", _cases(gen.MCP_DOCUMENT_CASES, _MCP_PREDICATES)
)
def test_mcp_document_cases(name, strategy, predicate):
    _run(strategy, predicate)


def test_mcp_near_miss_urls_cover_scheme_slash_and_host():
    """The three near-miss shapes the design names are all in the pool."""
    urls = list(gen.NEAR_MISS_MCP_URLS.values())
    assert any(url.startswith("http://") for url in urls)
    assert any(url.endswith("/mcp/") for url in urls)
    assert any("senzing.io" in url or "senzing.com/mcp" == url.split("//")[1] for url in urls)
    assert gen.SENZING_MCP_URL not in urls


# ---------------------------------------------------------------------------
# 7. statement()
# ---------------------------------------------------------------------------

_STATEMENT_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "exact_phrase": lambda text: text in gen.TRIGGER_PHRASES.values(),
    "phrase_in_longer_text": _contains_phrase,
    "case_variant": lambda text: not _contains_phrase(text)
    and _contains_phrase(text.lower()),
    "overlapping_fragments": lambda text: not _contains_phrase(text)
    and "senzing" in text,
    "near_miss": lambda text: not _contains_phrase(text),
    "unrelated": lambda text: not _contains_phrase(text),
    "free_text": lambda text: isinstance(text, str),
}


@pytest.mark.parametrize(
    "name,strategy,predicate", _cases(gen.STATEMENT_CASES, _STATEMENT_PREDICATES)
)
def test_statement_cases(name, strategy, predicate):
    _run(strategy, predicate)


def test_trigger_phrases_are_lexically_disjoint():
    phrases = list(gen.TRIGGER_PHRASES.values())
    for phrase in phrases:
        others = [other for other in phrases if other != phrase]
        assert not any(phrase in other for other in others), phrase


# ---------------------------------------------------------------------------
# 8. failure_point()
# ---------------------------------------------------------------------------

_FAILURE_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "mid_write": lambda point: point.stage == "mid-write",
    "post_write_pre_validate": lambda point: point.stage == "post-write-pre-validate",
    "mid_swap": lambda point: point.stage == "mid-swap",
    "permission_denied": lambda point: point.kind == "permission-denied"
    and point.expected_error == "E_WRITE_FAILED",
    "path_is_a_file": lambda point: point.kind == "path-is-a-file"
    and point.expected_error == "E_WRITE_FAILED",
}


@pytest.mark.parametrize(
    "name,strategy,predicate", _cases(gen.FAILURE_POINT_CASES, _FAILURE_PREDICATES)
)
def test_failure_point_cases(name, strategy, predicate):
    _run(strategy, predicate)


# ---------------------------------------------------------------------------
# 9. reconcile_triple()
# ---------------------------------------------------------------------------


def _intents(triple: gen.ReconcileTriple) -> set[str]:
    return set(triple.intents.values())


_RECONCILE_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "all_intents": lambda triple: _intents(triple) == set(gen.RECONCILE_INTENTS),
    "divergence_combinations": lambda triple: _intents(triple)
    == {
        "unchanged",
        "upstream-change",
        "local-edit-only",
        "local-edit-and-upstream-change",
    },
    "additions": lambda triple: "added" in _intents(triple)
    and all(
        path in triple.staging and path not in triple.previous
        for path, intent in triple.intents.items()
        if intent == "added"
    ),
    "removals": lambda triple: "removed" in _intents(triple)
    and all(
        path not in triple.staging and path in triple.previous
        for path, intent in triple.intents.items()
        if intent == "removed"
    ),
    "kiro_owned": lambda triple: any(
        entry["owner"] == "kiro" for entry in triple.manifest["files"]
    ),
    "empty": lambda triple: triple.paths == (),
    "mixed": lambda triple: _intents(triple) <= set(gen.RECONCILE_INTENTS),
}


@pytest.mark.parametrize(
    "name,strategy,predicate",
    _cases(gen.RECONCILE_TRIPLE_CASES, _RECONCILE_PREDICATES),
)
def test_reconcile_triple_cases(name, strategy, predicate):
    _run(strategy, predicate)


def test_reconcile_manifest_hashes_describe_the_previous_content():
    import hashlib

    def hashes_match(triple: gen.ReconcileTriple) -> bool:
        for entry in triple.manifest["files"]:
            expected = hashlib.sha256(
                triple.previous[entry["path"]].encode("utf-8")
            ).hexdigest()
            if entry["sha256"] != expected:
                return False
        return True

    _run(gen.reconcile_triple(), hashes_match)


# ---------------------------------------------------------------------------
# 10. outcome_set()
# ---------------------------------------------------------------------------


def _platform_cells(record: gen.OutcomeSet) -> list[str]:
    return [
        outcome
        for step in gen.PER_PLATFORM_STEPS
        if isinstance(record.outcomes.get(step), dict)
        for outcome in record.outcomes[step].values()
    ]


_OUTCOME_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "complete_pass": lambda record: record.tag_allowed
    and len(record.outcomes) == gen.CHECKLIST_STEP_COUNT
    and _platform_cells(record) == ["pass"] * 9
    and record.record_version == record.version,
    "missing_step": lambda record: len(record.outcomes)
    == gen.CHECKLIST_STEP_COUNT - 1
    and not record.tag_allowed,
    "blank_outcome": lambda record: any(
        outcome == ""
        for value in record.outcomes.values()
        for outcome in (value.values() if isinstance(value, dict) else [value])
    )
    and not record.tag_allowed,
    "explicit_fail": lambda record: any(
        outcome == "fail"
        for value in record.outcomes.values()
        for outcome in (value.values() if isinstance(value, dict) else [value])
    )
    and not record.tag_allowed,
    "version_mismatch": lambda record: record.record_version != record.version
    and not record.tag_allowed,
    "blank_platform_cell": lambda record: "" in _platform_cells(record)
    and not record.tag_allowed,
}


@pytest.mark.parametrize(
    "name,strategy,predicate", _cases(gen.OUTCOME_SET_CASES, _OUTCOME_PREDICATES)
)
def test_outcome_set_cases(name, strategy, predicate):
    _run(strategy, predicate)


# ---------------------------------------------------------------------------
# 11. interpreter_path()
# ---------------------------------------------------------------------------

_INTERPRETER_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "posix": lambda case: case.interpreter.startswith("/")
    and case.script.startswith("/"),
    "windows_drive_letter": lambda case: re.match(r"^[A-Z]:\\", case.interpreter)
    is not None
    and re.match(r"^[A-Z]:\\", case.script) is not None,
    "unc_prefix": lambda case: case.interpreter.startswith("\\\\")
    and case.script.startswith("\\\\"),
    "single_space": lambda case: " " in case.script and "  " not in case.script,
    "repeated_spaces": lambda case: "  " in case.script,
    "trailing_space": lambda case: any(
        component.endswith(" ")
        for component in re.split(r"[\\/]", case.script)
        if component
    ),
    "embedded_quote": lambda case: '"' in case.script,
    "shell_operator_chars": lambda case: any(
        char in case.script for char in "&|;>"
    ),
    "all_shell_operator_chars": lambda case: all(
        char in case.script for char in "&|;>"
    ),
}


@pytest.mark.parametrize(
    "name,strategy,predicate",
    _cases(gen.INTERPRETER_PATH_CASES, _INTERPRETER_PREDICATES),
)
def test_interpreter_path_cases(name, strategy, predicate):
    _run(strategy, predicate)


def test_interpreter_paths_are_absolute_and_name_a_python_script():
    def shaped(case: gen.InterpreterPathCase) -> bool:
        absolute = case.interpreter.startswith(("/", "\\\\")) or re.match(
            r"^[A-Z]:\\", case.interpreter
        )
        return bool(absolute) and case.script.endswith(".py")

    _run(gen.interpreter_path(), shaped)


def test_interpreter_path_flavors_cover_all_three_shapes():
    """The adversarial cases draw from every path shape, not just POSIX."""
    assert set(gen.PATH_FLAVORS) == {"posix", "windows-drive", "unc"}
    for case_name in ("single_space", "repeated_spaces", "trailing_space", "embedded_quote"):
        _run(
            gen.INTERPRETER_PATH_CASES[case_name],
            lambda case: case.flavor in gen.PATH_FLAVORS,
        )


# ---------------------------------------------------------------------------
# 12. discount_register()
# ---------------------------------------------------------------------------


def _identifiers(case: gen.DiscountRegisterCase) -> list[str]:
    return [entry.get("invariant", "") for entry in case.entries]


_DISCOUNT_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "empty": lambda case: case.entries == () and case.valid,
    "valid": lambda case: case.valid
    and all(
        entry.get(key, "").strip()
        for entry in case.entries
        for key in ("invariant", "conflictsWith", "resolution")
    )
    and gen.HONORED_INVARIANT not in _identifiers(case),
    "missing_field": lambda case: any(
        any(key not in entry for key in ("invariant", "conflictsWith", "resolution"))
        for entry in case.entries
    )
    and not case.valid,
    "empty_field": lambda case: any(
        value == "" for entry in case.entries for value in entry.values()
    )
    and not case.valid,
    "whitespace_field": lambda case: any(
        value != "" and value.strip() == ""
        for entry in case.entries
        for value in entry.values()
    )
    and not case.valid,
    "inv_052": lambda case: gen.HONORED_INVARIANT in _identifiers(case)
    and not case.valid,
    "inv_052_lowercase": lambda case: _identifiers(case) == ["inv-052"]
    and case.near_miss == "inv-052",
    "inv_052_trailing_space": lambda case: _identifiers(case) == ["INV-052 "]
    and case.near_miss == "INV-052 ",
    "inv_52_distinct": lambda case: _identifiers(case) == ["INV-52"]
    and case.near_miss == "INV-52"
    and case.valid,
}


@pytest.mark.parametrize(
    "name,strategy,predicate",
    _cases(gen.DISCOUNT_REGISTER_CASES, _DISCOUNT_PREDICATES),
)
def test_discount_register_cases(name, strategy, predicate):
    _run(strategy, predicate)


# ---------------------------------------------------------------------------
# 13. inv_prose()
# ---------------------------------------------------------------------------

_INV_PROSE_PREDICATES: Mapping[str, Callable[[Any], bool]] = {
    "zero_citations": lambda case: case.citation_count == 0,
    "one_citation": lambda case: case.citation_count == 1,
    "many_citations": lambda case: case.citation_count >= 2,
    "discounted_citations": lambda case: any(
        citation in gen.DISCOUNTED_INVARIANTS for citation in case.citations
    ),
    "citations_in_code_fence": lambda case: any(
        "INV-" in line for line in _fenced_lines(case.text)
    ),
    "citation_adjacent_to_residual": lambda case: case.citation_count >= 1
    and case.residual_claude_refs != ()
    and all(residual in case.text for residual in case.residual_claude_refs),
}


@pytest.mark.parametrize(
    "name,strategy,predicate", _cases(gen.INV_PROSE_CASES, _INV_PROSE_PREDICATES)
)
def test_inv_prose_cases(name, strategy, predicate):
    _run(strategy, predicate)


def test_inv_prose_citations_are_extracted_from_the_text():
    def extracted(case: gen.InvProseCase) -> bool:
        return list(case.citations) == re.findall(r"INV-\d{2,3}", case.text)

    _run(gen.inv_prose(), extracted)


# ---------------------------------------------------------------------------
# All thirteen generators exist, draw, and expose their cases
# ---------------------------------------------------------------------------

_GENERATORS = {
    "release_list": (gen.release_list, gen.RELEASE_LIST_CASES),
    "template_tree": (gen.template_tree, gen.TEMPLATE_TREE_CASES),
    "skill_tree": (gen.skill_tree, gen.SKILL_TREE_CASES),
    "frontmatter": (gen.frontmatter, gen.FRONTMATTER_CASES),
    "file_content": (gen.file_content, gen.FILE_CONTENT_CASES),
    "mcp_document": (gen.mcp_document, gen.MCP_DOCUMENT_CASES),
    "statement": (gen.statement, gen.STATEMENT_CASES),
    "failure_point": (gen.failure_point, gen.FAILURE_POINT_CASES),
    "reconcile_triple": (gen.reconcile_triple, gen.RECONCILE_TRIPLE_CASES),
    "outcome_set": (gen.outcome_set, gen.OUTCOME_SET_CASES),
    "interpreter_path": (gen.interpreter_path, gen.INTERPRETER_PATH_CASES),
    "discount_register": (gen.discount_register, gen.DISCOUNT_REGISTER_CASES),
    "inv_prose": (gen.inv_prose, gen.INV_PROSE_CASES),
}


def test_the_design_names_thirteen_generators_and_all_thirteen_exist():
    assert len(_GENERATORS) == 13
    assert set(_GENERATORS) <= set(gen.__all__)


@pytest.mark.parametrize("name", sorted(_GENERATORS))
def test_each_generator_draws(name):
    factory, cases = _GENERATORS[name]
    assert cases, f"{name} exposes no named edge cases"
    _run(factory(), lambda value: value is not None or value == [])
