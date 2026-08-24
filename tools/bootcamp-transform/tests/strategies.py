"""Shared Hypothesis strategies for the bootcamp transform engine's property tests.

The design's Testing Strategy names thirteen generators and, for each, the
edge cases it must deliberately emit. This module implements exactly those
thirteen — `release_list`, `template_tree`, `skill_tree`, `frontmatter`,
`file_content`, `mcp_document`, `statement`, `failure_point`,
`reconcile_triple`, `outcome_set`, `interpreter_path`, `discount_register`,
`inv_prose` — and nothing else. It contains no assertions and no engine logic:
it is input only.

Shape of every generator
------------------------
Each generator is a thin `st.one_of` over a public dict of *named* edge cases,
for example `RELEASE_LIST_CASES`. Two consequences, both intentional:

1. Drawing from the composite generator reaches every listed edge case, so a
   property test that takes `release_list()` sees empty lists, all-draft lists,
   and the `0.10.0`-vs-`0.9.0` ordering trap without asking for them.
2. A property test that wants one specific edge case can target it directly
   (`RELEASE_LIST_CASES["zero_padded"]`) instead of filtering the composite.

Derived facts are computed, not asserted
----------------------------------------
Where a case carries metadata a test will compare against — occurrence counts,
whether a cross-reference resolves, the multiset of `INV-NNN` citations — that
metadata is **computed from the generated artifact** (`str.count`, path
normalization, a regex over the final text) rather than tracked while building
it. A generator that declared what it *intended* to build would hide the very
off-by-one it exists to find.

Where a case carries a *defect label* instead (`frontmatter`, `mcp_document`,
`outcome_set`, `discount_register`), the label names what was seeded, and the
empty tuple means "no defect". Tests assert the biconditional between the
validator's verdict and `defects == ()`; the labels themselves come from the
acceptance criteria, not from any implementation.

Paths are relative to the template plugin root (`plugins/senzing-bootcamp/`)
for `template_tree`, and to the Power root for everything else.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Mapping, Sequence

import yaml
from hypothesis import strategies as st

__all__ = [
    # Generators (the thirteen the design names).
    "release_list",
    "template_tree",
    "skill_tree",
    "frontmatter",
    "file_content",
    "mcp_document",
    "statement",
    "failure_point",
    "reconcile_triple",
    "outcome_set",
    "interpreter_path",
    "discount_register",
    "inv_prose",
    # Per-generator named edge cases.
    "RELEASE_LIST_CASES",
    "TEMPLATE_TREE_CASES",
    "SKILL_TREE_CASES",
    "FRONTMATTER_CASES",
    "FILE_CONTENT_CASES",
    "MCP_DOCUMENT_CASES",
    "STATEMENT_CASES",
    "FAILURE_POINT_CASES",
    "RECONCILE_TRIPLE_CASES",
    "OUTCOME_SET_CASES",
    "INTERPRETER_PATH_CASES",
    "DISCOUNT_REGISTER_CASES",
    "INV_PROSE_CASES",
    # Value types.
    "CrossReference",
    "DiscountRegisterCase",
    "FailurePoint",
    "FileContentCase",
    "FrontmatterCase",
    "InvProseCase",
    "InterpreterPathCase",
    "McpDocumentCase",
    "OutcomeSet",
    "ReconcileTriple",
    "SkillTreeCase",
    "Substitution",
    "TreeEntry",
    # Facts from the requirements and design that generators and tests share.
    "CHECKLIST_STEP_COUNT",
    "CLAUDE_MODEL_REFERENCES",
    "COMMAND_DERIVED_SKILLS",
    "DISCOUNTED_INVARIANTS",
    "HONORED_INVARIANT",
    "HOOK_SCRIPT_NAMES",
    "IGNORED_TEMPLATE_PATHS",
    "MAX_DESCRIPTION_LENGTH",
    "MCP_SCHEMA_URL",
    "MCP_TRANSPORT_TYPE",
    "NEAR_MISS_MCP_URLS",
    "PATH_FLAVORS",
    "PER_PLATFORM_STEPS",
    "RECONCILE_INTENTS",
    "SENZING_MCP_URL",
    "SUBSTITUTION_SETS",
    "SUPPORTED_PLATFORMS",
    "TEMPLATE_PLUGIN_ROOT",
    "TRIGGER_PHRASES",
]


# ---------------------------------------------------------------------------
# Facts from the requirements and the design
# ---------------------------------------------------------------------------

#: Template sources are rooted at a subdirectory, not the repository root.
TEMPLATE_PLUGIN_ROOT = "plugins/senzing-bootcamp"

#: Agent Plugins frontmatter caps a skill description (R8 AC5 / Property 13).
MAX_DESCRIPTION_LENGTH = 1024

#: The exact Senzing MCP declaration (R11 AC1).
SENZING_MCP_URL = "https://mcp.senzing.com/mcp"
MCP_TRANSPORT_TYPE = "streamable-http"
MCP_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

#: Command-derived skills and their lexically disjoint trigger phrases (R9).
TRIGGER_PHRASES: Mapping[str, str] = {
    "start-bootcamp": "start the senzing bootcamp",
    "graduate-bootcamp": "graduate the senzing bootcamp",
    "bootcamp-feedback": "give senzing bootcamp feedback",
}
COMMAND_DERIVED_SKILLS = tuple(TRIGGER_PHRASES)

#: `INV-052` is honored, not discounted, so it must never appear in the register
#: (R15 AC6). The others stand in for ordinary discountable invariants.
HONORED_INVARIANT = "INV-052"
DISCOUNTED_INVARIANTS = ("INV-072", "INV-113", "INV-201")

#: Claude-specific model guidance R12 AC2 requires rewritten: a subscription
#: plan, model names, and an effort setting.
#:
#: Every entry is Claude-*qualified*, which is what makes it Claude-specific: Kiro
#: serves the same model tiers and carries the same reasoning-effort dial, so a bare
#: `Sonnet 5` or a bare `reasoning effort` is Kiro guidance rather than a residual
#: reference. The qualified prose spelling and the Anthropic API id spelling are the
#: two forms no Kiro surface uses.
CLAUDE_MODEL_REFERENCES = (
    "Claude Max plan",
    "Claude Sonnet 5",
    "Claude Sonnet 4.5",
    "Claude reasoning effort",
)

#: Template paths deliberately matched and not ported (contract `ignore`).
IGNORED_TEMPLATE_PATHS = (
    ".claude-plugin/marketplace.json",
    ".github/workflows/release.yml",
    ".vscode/settings.json",
    "CHANGELOG.md",
    "hooks/hooks.json",
    "hooks/README.md",
)

#: Scripts a template hook invokes, and therefore names a Hook_Command_String.
HOOK_SCRIPT_NAMES = (
    "write-gate.py",
    "session-start.py",
    "feedback-capture.py",
    "checkpoint-tick.py",
    "stop-nudge.py",
)

#: Test_Checklist shape: 17 ordered steps, three of them recorded per platform.
CHECKLIST_STEP_COUNT = 17
PER_PLATFORM_STEPS = (2, 10, 15)
SUPPORTED_PLATFORMS = ("linux", "macos", "windows")

#: How a `reconcile_triple` path was constructed. A property test maps these to
#: the design's classification buckets; the generator does not classify.
RECONCILE_INTENTS = (
    "unchanged",
    "upstream-change",
    "local-edit-only",
    "local-edit-and-upstream-change",
    "added",
    "removed",
    "kiro-owned",
)


@dataclass(frozen=True)
class Substitution:
    """One `find`/`replace` pair from a named contract substitution set."""

    find: str
    replace: str
    literal: bool = True


#: The contract's named substitution sets, in the *shape* the contract declares
#: them and with stand-in replacement values rather than the contract's own. The
#: generators built from this table exercise the substitution engine's behavior
#: over set shapes; none of them asserts a contract value, so a stand-in keeps
#: every assumption-dependent value to a single home in `contract.yaml` — the
#: `tool-names` Kiro write-tool regex especially, which task 16.2 asserts appears
#: in exactly one place in this repository.
#:
#: Note that `manifest-path` contains one find term that is a suffix of another;
#: that overlap is real and the occurrence counts below reflect the text as
#: written, not as intended.
SUBSTITUTION_SETS: Mapping[str, tuple[Substitution, ...]] = {
    "plugin-root": (Substitution("${CLAUDE_PLUGIN_ROOT}", "${PLUGIN_ROOT}"),),
    "manifest-path": (
        Substitution("../.claude-plugin/plugin.json", "../plugin.json"),
        Substitution(".claude-plugin/plugin.json", "plugin.json"),
    ),
    "client-names": (
        Substitution("Claude Code", "Kiro"),
        Substitution("Claude Desktop", "Kiro"),
    ),
    "model-guidance": (
        Substitution("Claude Max plan", "<kiro-plan>"),
        Substitution("Claude Sonnet 5", "<kiro-model>"),
    ),
    "tool-names": (Substitution("Write|Edit", "<kiro-write-tools>"),),
    "script-paths": (Substitution("scripts/", "../bootcamp-onboarding/scripts/"),),
}


# ---------------------------------------------------------------------------
# Small shared building blocks
# ---------------------------------------------------------------------------

_SLUG_TAIL = "abcdefghijklmnopqrstuvwxyz0123456789-"
_WORDS = (
    "bootcamp",
    "entity",
    "resolution",
    "senzing",
    "module",
    "record",
    "truthset",
    "graph",
    "docker",
    "exercise",
)
_MINIFIED_ASSET = b"!function(t,n){}(this,function(){return{version:'7'}});"
_BINARY_ASSET = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\x00\x01"


def _one_of(cases: Mapping[str, st.SearchStrategy[Any]]) -> st.SearchStrategy[Any]:
    """Compose named edge cases into the generator the design names."""
    return st.one_of(*cases.values())


def _slug(min_size: int = 1, max_size: int = 8) -> st.SearchStrategy[str]:
    """Lowercase path-safe identifier: a letter, then letters/digits/hyphens."""
    return st.builds(
        lambda head, tail: (head + tail).rstrip("-"),
        st.sampled_from("abcdefghijklmnopqrstuvwxyz"),
        st.text(_SLUG_TAIL, min_size=min_size - 1, max_size=max_size - 1),
    )


def _sentence() -> st.SearchStrategy[str]:
    return st.lists(st.sampled_from(_WORDS), min_size=3, max_size=8).map(
        lambda words: " ".join(words) + "."
    )


def _prose(min_lines: int = 1, max_lines: int = 4) -> st.SearchStrategy[str]:
    return st.lists(_sentence(), min_size=min_lines, max_size=max_lines).map("\n".join)


def _utf8_bytes() -> st.SearchStrategy[bytes]:
    return _prose().map(lambda text: (text + "\n").encode("utf-8"))


def _script_bytes() -> st.SearchStrategy[bytes]:
    return st.builds(
        lambda module, note: (
            f"import {module}\n\n"
            f'ROOT = "${{CLAUDE_PLUGIN_ROOT}}"\n'
            f"# {note}\n"
        ).encode("utf-8"),
        _slug(),
        _sentence(),
    )


def semver_tag() -> st.SearchStrategy[str]:
    """Bare semver, no `v` prefix, as the template tags its releases."""
    return st.builds(
        lambda major, minor, patch: f"{major}.{minor}.{patch}",
        st.integers(min_value=0, max_value=12),
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=0, max_value=20),
    )


def _published_at() -> st.SearchStrategy[str]:
    """An ISO timestamp derived from an offset, so nothing reads the clock."""
    return st.integers(min_value=0, max_value=730).map(
        lambda offset: (date(2023, 1, 1) + timedelta(days=offset)).isoformat()
        + "T00:00:00Z"
    )


def _skill_dir_name() -> st.SearchStrategy[str]:
    """A bootcamp skill directory name, including `module-03b`-style names."""
    return st.one_of(
        st.sampled_from(("bootcamp-onboarding", "bootcamp-preparation", "graduation")),
        st.builds(
            lambda number, interstitial, topic: f"module-{number:02d}{interstitial}-{topic}",
            st.integers(min_value=0, max_value=7),
            st.sampled_from(("", "b")),
            _slug(),
        ),
    )


def _module_03b_name() -> st.SearchStrategy[str]:
    """A name of the interstitial shape the progression order depends on."""
    return st.builds(
        lambda number, topic: f"module-{number:02d}b-{topic}",
        st.integers(min_value=0, max_value=7),
        _slug(),
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 1. release_list() — lists of release records
# ---------------------------------------------------------------------------


def _release_record(
    tag: str,
    *,
    draft: bool = False,
    prerelease: bool = False,
    published: str = "2024-01-01T00:00:00Z",
) -> dict[str, Any]:
    """One record in the shape `gh release list --json ...` returns."""
    return {
        "tagName": tag,
        "isDraft": draft,
        "isPrerelease": prerelease,
        "publishedAt": published,
    }


def _release() -> st.SearchStrategy[dict[str, Any]]:
    return st.builds(
        _release_record,
        semver_tag(),
        draft=st.booleans(),
        prerelease=st.booleans(),
        published=_published_at(),
    )


def _all_flagged(flag: str) -> st.SearchStrategy[list[dict[str, Any]]]:
    """Every record ineligible for one reason, so the eligible subset is empty."""
    return st.lists(_release(), min_size=1, max_size=4).map(
        lambda records: [
            {
                **record,
                "isDraft": flag == "isDraft",
                "isPrerelease": flag == "isPrerelease",
            }
            for record in records
        ]
    )


def _semver_ordering_trap() -> list[dict[str, Any]]:
    """Publish dates run *against* semver order, so a resolver that sorts by
    date rather than by semver precedence picks `0.9.0` and fails (R1 AC1)."""
    return [
        _release_record("0.9.0", published="2024-06-01T00:00:00Z"),
        _release_record("0.10.0", published="2024-05-01T00:00:00Z"),
    ]


def _zero_padded_pair() -> list[dict[str, Any]]:
    """The same precedence under two spellings: `0.05.1` is not a distinct
    version from `0.5.1`, but it is a distinct string (R1 AC1, R2 AC1)."""
    return [
        _release_record("0.5.1", published="2024-03-01T00:00:00Z"),
        _release_record("0.05.1", published="2024-04-01T00:00:00Z"),
    ]


def _higher_tag_ineligible() -> list[dict[str, Any]]:
    """The highest tags are a draft and a prerelease; the eligible max is lower."""
    return [
        _release_record("0.6.0", draft=True, published="2024-07-01T00:00:00Z"),
        _release_record("0.5.9", prerelease=True, published="2024-07-02T00:00:00Z"),
        _release_record("0.5.1", published="2024-02-02T00:00:00Z"),
    ]


RELEASE_LIST_CASES: Mapping[str, st.SearchStrategy[list[dict[str, Any]]]] = {
    # No eligible release at all: E_NO_RELEASE with no selection (R1 AC4).
    "empty": st.builds(list),
    # Every release ineligible, one flag at a time.
    "all_draft": _all_flagged("isDraft"),
    "all_prerelease": _all_flagged("isPrerelease"),
    # 0.10.0 > 0.9.0 by semver, < by string comparison.
    "semver_vs_lexicographic": st.builds(_semver_ordering_trap).flatmap(st.permutations),
    # The same tag published twice.
    "duplicate_tags": st.builds(
        lambda tag: [
            _release_record(tag, published="2024-01-01T00:00:00Z"),
            _release_record(tag, published="2024-02-01T00:00:00Z"),
        ],
        semver_tag(),
    ),
    # 0.5.1 vs 0.05.1.
    "zero_padded": st.builds(_zero_padded_pair).flatmap(st.permutations),
    # A higher tag that is ineligible, beside a lower tag that is eligible.
    "higher_tag_ineligible": st.builds(_higher_tag_ineligible),
    # Unconstrained: any mix of tags and flags, including the empty list.
    "mixed": st.lists(_release(), max_size=6),
}


def release_list() -> st.SearchStrategy[list[dict[str, Any]]]:
    """Lists of template release records for the `Version_Resolver`.

    Edge cases: empty list, all-draft, all-prerelease, `0.10.0` vs `0.9.0`,
    duplicate tags, `0.5.1` vs `0.05.1`.
    """
    return _one_of(RELEASE_LIST_CASES)


# ---------------------------------------------------------------------------
# 2. template_tree() — synthetic template plugin trees
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TreeEntry:
    """One entry in a synthetic template tree.

    `kind` is `file`, `binary`, `empty`, or `symlink`. A symlink carries a
    `target` and no content; everything else carries bytes, because the
    transform's fidelity guarantees are about bytes, not about text.
    """

    kind: str
    content: bytes = b""
    target: str | None = None


def _entry_file() -> st.SearchStrategy[TreeEntry]:
    return _utf8_bytes().map(lambda content: TreeEntry("file", content))


@st.composite
def _base_template_tree(draw: Any) -> dict[str, TreeEntry]:
    """A tree every contract rule matches, before an edge case is added."""
    entries: dict[str, TreeEntry] = {}

    for name in draw(st.lists(_skill_dir_name(), min_size=1, max_size=3, unique=True)):
        entries[f"skills/{name}/SKILL.md"] = draw(_entry_file())
        for reference in draw(st.lists(_slug(), max_size=2, unique=True)):
            entries[f"skills/{name}/references/{reference}.md"] = draw(_entry_file())

    for script in draw(st.lists(_slug(), min_size=1, max_size=3, unique=True)):
        entries[f"scripts/{script}.py"] = TreeEntry("file", draw(_script_bytes()))
    entries["scripts/vendor/d3.v7.min.js"] = TreeEntry("binary", _MINIFIED_ASSET)

    for document in draw(st.lists(_slug(), max_size=2, unique=True)):
        entries[f"docs/{document}.md"] = draw(_entry_file())

    for ignored in IGNORED_TEMPLATE_PATHS:
        entries[ignored] = TreeEntry("file", b"{}\n")

    return entries


def _tree_with(
    extra: st.SearchStrategy[dict[str, TreeEntry]],
) -> st.SearchStrategy[dict[str, TreeEntry]]:
    return st.builds(
        lambda base, added: {**base, **added}, _base_template_tree(), extra
    )


#: Filenames outside ASCII, which a path-handling bug reaches before any rule.
_UNICODE_FILENAMES = ("données-café.md", "日本語.md", "naïve-Ñandú.md", "rocket-🚀.md")

#: Paths that try to leave the target root (Property 7).
_ESCAPING_PATHS = (
    "../outside-the-root.md",
    "skills/../../escape.md",
    "docs/../../../etc/passwd",
)
_ABSOLUTE_LOOKING_PATHS = (
    "/etc/passwd",
    "/tmp/absolute-looking.md",
    "C:\\Windows\\System32\\drivers\\etc\\hosts",
    "\\\\fileserver\\share\\absolute-looking.txt",
)

TEMPLATE_TREE_CASES: Mapping[str, st.SearchStrategy[dict[str, TreeEntry]]] = {
    # Every file matches a rule or the ignore list.
    "wellformed": _base_template_tree(),
    # Genuinely new upstream content: matched by no rule and no ignore entry,
    # which must halt the build with E_UNMATCHED_FILE (R3 AC6).
    "unmatched_path": _tree_with(
        st.one_of(
            _slug().map(lambda name: {f"newthing/{name}.md": TreeEntry("file", b"new\n")}),
            _slug().map(lambda name: {f"{name}.toml": TreeEntry("file", b"new = true\n")}),
            _slug().map(lambda name: {f"tools/{name}/notes.txt": TreeEntry("file", b"new\n")}),
        )
    ),
    # Vendored assets nested below scripts/vendor/.
    "nested_vendor": _tree_with(
        _slug().map(
            lambda name: {
                f"scripts/vendor/{name}/d3.v7.min.js": TreeEntry("binary", _MINIFIED_ASSET),
                f"scripts/vendor/{name}/nested/deeper/asset.js": TreeEntry(
                    "binary", _MINIFIED_ASSET
                ),
            }
        )
    ),
    # Bytes a substitution pass must not touch (R10 AC3).
    "binary_asset": _tree_with(
        _slug().map(
            lambda name: {
                f"docs/images/{name}.png": TreeEntry("binary", _BINARY_ASSET),
                f"scripts/vendor/{name}.min.js": TreeEntry("binary", _MINIFIED_ASSET),
            }
        )
    ),
    "empty_file": _tree_with(
        _slug().map(
            lambda name: {
                f"docs/{name}.md": TreeEntry("empty", b""),
                f"scripts/{name}.py": TreeEntry("empty", b""),
            }
        )
    ),
    "unicode_filename": _tree_with(
        st.sampled_from(_UNICODE_FILENAMES).map(
            lambda name: {f"docs/{name}": TreeEntry("file", "prose\n".encode("utf-8"))}
        )
    ),
    "dotdot_segment": _tree_with(
        st.sampled_from(_ESCAPING_PATHS).map(
            lambda path: {path: TreeEntry("file", b"escapes\n")}
        )
    ),
    "absolute_looking_path": _tree_with(
        st.sampled_from(_ABSOLUTE_LOOKING_PATHS).map(
            lambda path: {path: TreeEntry("file", b"escapes\n")}
        )
    ),
    # Symlinks: one pointing inside the tree, one pointing out of it.
    "symlink": _tree_with(
        _slug().map(
            lambda name: {
                f"docs/{name}-link.md": TreeEntry("symlink", target="../scripts/vendor/d3.v7.min.js"),
                f"skills/{name}-escape.md": TreeEntry("symlink", target="../../../../etc/passwd"),
            }
        )
    ),
}


def template_tree() -> st.SearchStrategy[dict[str, TreeEntry]]:
    """Synthetic template plugin trees, keyed by path below the plugin root.

    Edge cases: novel unmatched paths, nested `scripts/vendor/`, binary assets,
    empty files, unicode filenames, `..` segments, absolute-looking paths, and
    symlinks.
    """
    return _one_of(TEMPLATE_TREE_CASES)


# ---------------------------------------------------------------------------
# 3. skill_tree() — skill directories with cross-reference graphs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrossReference:
    """A relative markdown link, and whether it resolves within the tree.

    `resolves` is computed by normalizing `target` against `source`'s directory
    and testing membership in the generated file set — never declared.
    """

    source: str
    target: str
    resolves: bool


@dataclass
class SkillTreeCase:
    """Skill files keyed by Power-relative path, plus their link graph."""

    files: dict[str, str]
    references: tuple[CrossReference, ...]

    @property
    def broken(self) -> tuple[CrossReference, ...]:
        return tuple(ref for ref in self.references if not ref.resolves)


def _resolves(files: Mapping[str, str], source: str, target: str) -> bool:
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
    return resolved in files


@st.composite
def _skill_tree(
    draw: Any, link_kinds: Sequence[str], *, force_interstitial: bool = False
) -> SkillTreeCase:
    names = draw(st.lists(_skill_dir_name(), min_size=2, max_size=3, unique=True))
    if force_interstitial:
        interstitial = draw(_module_03b_name())
        if interstitial not in names:
            names[0] = interstitial

    files: dict[str, str] = {}
    references: dict[str, list[str]] = {}
    for name in names:
        files[f"skills/{name}/SKILL.md"] = draw(_prose()) + "\n"
        references[name] = draw(st.lists(_slug(), max_size=2, unique=True))
        for reference in references[name]:
            files[f"skills/{name}/references/{reference}.md"] = draw(_prose()) + "\n"

    links: list[tuple[str, str]] = []
    for kind in link_kinds:
        owner = draw(st.sampled_from(names))
        source = f"skills/{owner}/SKILL.md"
        if kind == "parent":
            other = draw(st.sampled_from([n for n in names if n != owner] or names))
            target = f"../{other}/SKILL.md"
        elif kind == "broken":
            target = f"../{draw(_slug())}-absent/SKILL.md"
        elif kind == "self":
            target = "SKILL.md"
        elif kind == "references":
            owned = references[owner]
            target = (
                f"references/{draw(st.sampled_from(owned))}.md"
                if owned
                else f"references/{draw(_slug())}-absent.md"
            )
        else:  # pragma: no cover - guarded by the case table below
            raise ValueError(f"unknown link kind: {kind}")
        links.append((source, target))

    for source, target in links:
        files[source] += f"See [the reference]({target}).\n"

    return SkillTreeCase(
        files=files,
        references=tuple(
            CrossReference(source, target, _resolves(files, source, target))
            for source, target in links
        ),
    )


SKILL_TREE_CASES: Mapping[str, st.SearchStrategy[SkillTreeCase]] = {
    "parent_links": _skill_tree(("parent",)),
    "broken_links": _skill_tree(("broken",)),
    "self_links": _skill_tree(("self",)),
    "references_links": _skill_tree(("references",)),
    "module_03b_names": _skill_tree(("parent", "references"), force_interstitial=True),
    "mixed": _skill_tree(("parent", "broken", "self", "references")),
    "no_links": _skill_tree(()),
}


def skill_tree() -> st.SearchStrategy[SkillTreeCase]:
    """Skill directories with cross-reference graphs.

    Edge cases: `../` links, broken links, self-links, links into
    `references/`, and `module-03b`-style names.
    """
    return _one_of(SKILL_TREE_CASES)


# ---------------------------------------------------------------------------
# 4. frontmatter() — YAML frontmatter blocks
# ---------------------------------------------------------------------------


@dataclass
class FrontmatterCase:
    """A rendered frontmatter block, its containing directory, and its defects.

    `defects` is empty exactly when the block satisfies R8 AC5/AC6: `name`
    present, non-blank, equal to `directory`; `description` present, non-blank,
    at most `MAX_DESCRIPTION_LENGTH` characters, containing `trigger_phrase`;
    `license` present and non-blank.
    """

    directory: str
    fields: dict[str, Any]
    text: str
    trigger_phrase: str
    defects: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.defects == ()


_FRONTMATTER_REQUIRED_KEYS = ("name", "description", "license")


def _render_frontmatter(fields: Mapping[str, Any]) -> str:
    body = yaml.safe_dump(
        dict(fields),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10**6,
    )
    return f"---\n{body}---\n"


def _frontmatter_case(
    directory: str,
    trigger_phrase: str,
    *,
    drop: str | None = None,
    value: tuple[str, str] | None = None,
    defects: tuple[str, ...] = (),
) -> FrontmatterCase:
    fields: dict[str, Any] = {
        "name": directory,
        "description": f"Work through {directory}. Use when the bootcamper says '{trigger_phrase}'.",
        "license": "Apache-2.0",
        "compatibility": "Requires the Senzing MCP server.",
    }
    if value is not None:
        fields[value[0]] = value[1]
    if drop is not None:
        fields.pop(drop)
    return FrontmatterCase(
        directory=directory,
        fields=fields,
        text=_render_frontmatter(fields),
        trigger_phrase=trigger_phrase,
        defects=defects,
    )


def _frontmatter_valid() -> st.SearchStrategy[FrontmatterCase]:
    return st.builds(_frontmatter_case, _skill_dir_name(), _sentence())


def _frontmatter_missing_key() -> st.SearchStrategy[FrontmatterCase]:
    return st.builds(
        lambda directory, phrase, key: _frontmatter_case(
            directory, phrase, drop=key, defects=(f"missing:{key}",)
        ),
        _skill_dir_name(),
        _sentence(),
        st.sampled_from(_FRONTMATTER_REQUIRED_KEYS),
    )


def _frontmatter_blank(kind: str, blank: st.SearchStrategy[str]) -> st.SearchStrategy[FrontmatterCase]:
    return st.builds(
        lambda directory, phrase, key, blank_value: _frontmatter_case(
            directory, phrase, value=(key, blank_value), defects=(f"{kind}:{key}",)
        ),
        _skill_dir_name(),
        _sentence(),
        st.sampled_from(_FRONTMATTER_REQUIRED_KEYS),
        blank,
    )


def _frontmatter_long_description() -> st.SearchStrategy[FrontmatterCase]:
    return st.builds(
        lambda directory, phrase, overflow: _frontmatter_case(
            directory,
            phrase,
            value=(
                "description",
                f"Use when the bootcamper says '{phrase}'. "
                + "long " * (((MAX_DESCRIPTION_LENGTH + overflow) // 5) + 1),
            ),
            defects=("description-too-long",),
        ),
        _skill_dir_name(),
        _sentence(),
        st.integers(min_value=1, max_value=64),
    )


def _frontmatter_name_mismatch() -> st.SearchStrategy[FrontmatterCase]:
    return st.builds(
        lambda directory, other, phrase: _frontmatter_case(
            directory,
            phrase,
            value=("name", other if other != directory else f"{other}-x"),
            defects=("name-directory-mismatch",),
        ),
        _skill_dir_name(),
        _skill_dir_name(),
        _sentence(),
    )


FRONTMATTER_CASES: Mapping[str, st.SearchStrategy[FrontmatterCase]] = {
    "valid": _frontmatter_valid(),
    "missing_key": _frontmatter_missing_key(),
    "empty_string": _frontmatter_blank("blank", st.just("")),
    "whitespace_only": _frontmatter_blank(
        "whitespace", st.sampled_from((" ", "   ", "\t", " \t "))
    ),
    "long_description": _frontmatter_long_description(),
    "name_directory_mismatch": _frontmatter_name_mismatch(),
}


def frontmatter() -> st.SearchStrategy[FrontmatterCase]:
    """YAML frontmatter blocks for `SKILL.md` files.

    Edge cases: missing keys, empty strings, whitespace-only values,
    descriptions longer than 1024 characters, and name/directory mismatches.
    """
    return _one_of(FRONTMATTER_CASES)


# ---------------------------------------------------------------------------
# 5. file_content() — text carrying substitution tokens
# ---------------------------------------------------------------------------


@dataclass
class FileContentCase:
    """Text, the substitution set that applies to it, and token counts.

    `occurrences` is `text.count(find)` per find term, computed after the text
    is assembled. Where two find terms in a set overlap, the shorter term's
    count includes its occurrences inside the longer one; that is the honest
    reading of the text and is what a substitution pass has to contend with.
    """

    text: str
    substitutions: tuple[Substitution, ...]
    occurrences: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.occurrences = {
            substitution.find: self.text.count(substitution.find)
            for substitution in self.substitutions
        }

    @property
    def total_occurrences(self) -> int:
        return sum(self.occurrences.values())


def _file_content(text: str, substitutions: tuple[Substitution, ...]) -> FileContentCase:
    return FileContentCase(text=text, substitutions=substitutions)


def _substitution_set() -> st.SearchStrategy[tuple[Substitution, ...]]:
    return st.sampled_from(list(SUBSTITUTION_SETS.values()))


def _content_zero() -> st.SearchStrategy[FileContentCase]:
    return st.builds(
        lambda prose, substitutions: _file_content(prose + "\n", substitutions),
        _prose(),
        _substitution_set(),
    )


def _content_with_tokens(count: int) -> st.SearchStrategy[FileContentCase]:
    return st.builds(
        lambda prose, substitutions, picks: _file_content(
            "\n".join(
                [prose]
                + [
                    f"Line {index}: {substitutions[pick % len(substitutions)].find} trails here."
                    for index, pick in enumerate(picks)
                ]
            )
            + "\n",
            substitutions,
        ),
        _prose(),
        _substitution_set(),
        st.lists(st.integers(min_value=0, max_value=8), min_size=count, max_size=count),
    )


def _content_many() -> st.SearchStrategy[FileContentCase]:
    return st.builds(
        lambda prose, substitutions, picks: _file_content(
            "\n".join(
                [prose]
                + [
                    f"{substitutions[pick % len(substitutions)].find} appears at {index}."
                    for index, pick in enumerate(picks)
                ]
            )
            + "\n",
            substitutions,
        ),
        _prose(),
        _substitution_set(),
        st.lists(st.integers(min_value=0, max_value=8), min_size=3, max_size=9),
    )


def _content_adjacent() -> st.SearchStrategy[FileContentCase]:
    return st.builds(
        lambda prose, substitutions, repeats: _file_content(
            prose + "\n" + substitutions[0].find * repeats + "\n",
            substitutions,
        ),
        _prose(),
        _substitution_set(),
        st.integers(min_value=2, max_value=4),
    )


def _content_in_code_fence() -> st.SearchStrategy[FileContentCase]:
    return st.builds(
        lambda prose, substitutions, language: _file_content(
            f"{prose}\n\n```{language}\n"
            f"value = \"{substitutions[0].find}\"\n"
            "```\n\n"
            f"Inline `{substitutions[-1].find}` too.\n",
            substitutions,
        ),
        _prose(),
        _substitution_set(),
        st.sampled_from(("python", "bash", "")),
    )


def _content_with_invariants() -> st.SearchStrategy[FileContentCase]:
    return st.builds(
        lambda prose, substitutions, invariant: _file_content(
            f"{prose}\nPer {invariant}, keep {substitutions[0].find} intact "
            f"and honor {HONORED_INVARIANT}.\n",
            substitutions,
        ),
        _prose(),
        _substitution_set(),
        st.sampled_from(DISCOUNTED_INVARIANTS),
    )


FILE_CONTENT_CASES: Mapping[str, st.SearchStrategy[FileContentCase]] = {
    "zero_occurrences": _content_zero(),
    "one_occurrence": _content_with_tokens(1),
    "many_occurrences": _content_many(),
    "adjacent_tokens": _content_adjacent(),
    "tokens_in_code_fence": _content_in_code_fence(),
    "invariant_references": _content_with_invariants(),
}


def file_content() -> st.SearchStrategy[FileContentCase]:
    """Text with substitution tokens, paired with the set that rewrites them.

    Edge cases: zero, one, and many occurrences; adjacent tokens; tokens inside
    code fences; and `INV-NNN` references that no substitution may touch.
    """
    return _one_of(FILE_CONTENT_CASES)


# ---------------------------------------------------------------------------
# 6. mcp_document() — mcp.json variants
# ---------------------------------------------------------------------------


@dataclass
class McpDocumentCase:
    """An `mcp.json` document and the defects seeded into it.

    `defects` is empty exactly when the document declares the `senzing` server
    with the exact URL and transport type and carries `$schema` (R11 AC1–AC5).
    """

    document: dict[str, Any]
    defects: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.defects == ()


def _valid_mcp_document() -> dict[str, Any]:
    return {
        "$schema": MCP_SCHEMA_URL,
        "mcpServers": {
            "senzing": {"type": MCP_TRANSPORT_TYPE, "url": SENZING_MCP_URL}
        },
    }


#: URLs that differ from the required one only in scheme, trailing slash, host,
#: or path — the shapes an eyeball check passes and an equality check catches.
NEAR_MISS_MCP_URLS: Mapping[str, str] = {
    "http-scheme": "http://mcp.senzing.com/mcp",
    "trailing-slash": "https://mcp.senzing.com/mcp/",
    "wrong-host": "https://mcp.senzing.io/mcp",
    "wrong-subdomain": "https://senzing.com/mcp",
    "wrong-path": "https://mcp.senzing.com/mcp/v1",
    "uppercase-host": "https://MCP.senzing.com/mcp",
}

#: Transport types that are not `streamable-http`, including the template's own
#: `http` form the contract has to translate (R11 AC2).
_WRONG_TYPES = ("http", "sse", "streamable_http", "stdio", "STREAMABLE-HTTP")


def _mcp_wrong_url() -> st.SearchStrategy[McpDocumentCase]:
    return st.sampled_from(sorted(NEAR_MISS_MCP_URLS.items())).map(
        lambda item: _mcp_mutated(url=item[1], defects=(f"url:{item[0]}",))
    )


def _mcp_mutated(
    *,
    url: str | None = None,
    transport: str | None = None,
    drop_schema: bool = False,
    server_key: str | None = None,
    defects: tuple[str, ...] = (),
) -> McpDocumentCase:
    document = _valid_mcp_document()
    server = document["mcpServers"].pop("senzing")
    if url is not None:
        server["url"] = url
    if transport is not None:
        server["type"] = transport
    document["mcpServers"][server_key or "senzing"] = server
    if drop_schema:
        document.pop("$schema")
    return McpDocumentCase(document=document, defects=defects)


MCP_DOCUMENT_CASES: Mapping[str, st.SearchStrategy[McpDocumentCase]] = {
    "valid": st.builds(lambda: McpDocumentCase(document=_valid_mcp_document())),
    "near_miss_url": _mcp_wrong_url(),
    "wrong_type": st.sampled_from(_WRONG_TYPES).map(
        lambda transport: _mcp_mutated(transport=transport, defects=("type",))
    ),
    "missing_schema": st.builds(
        lambda: _mcp_mutated(drop_schema=True, defects=("missing-schema",))
    ),
    "missing_senzing_server": st.sampled_from(("Senzing", "senzing-mcp", "entity")).map(
        lambda key: _mcp_mutated(server_key=key, defects=("missing-senzing-server",))
    ),
    "multiple_defects": st.builds(
        lambda url, transport: _mcp_mutated(
            url=url,
            transport=transport,
            drop_schema=True,
            defects=("url:near-miss", "type", "missing-schema"),
        ),
        st.sampled_from(sorted(NEAR_MISS_MCP_URLS.values())),
        st.sampled_from(_WRONG_TYPES),
    ),
}


def mcp_document() -> st.SearchStrategy[McpDocumentCase]:
    """`mcp.json` variants for the Senzing MCP exactness check.

    Edge cases: near-miss URLs (`http://`, trailing slash, wrong host), a wrong
    `type`, and a missing `$schema`.
    """
    return _one_of(MCP_DOCUMENT_CASES)


# ---------------------------------------------------------------------------
# 7. statement() — Bootcamper utterances
# ---------------------------------------------------------------------------

_PHRASES = tuple(TRIGGER_PHRASES.values())

#: Word windows drawn from the trigger phrases that stop short of containing
#: any complete phrase. A statement containing two *complete* phrases is
#: deliberately not generated: it would match two skills by construction and
#: say nothing about whether the phrases are disjoint, which is what Property 19
#: is about.
_OVERLAPPING_FRAGMENTS = (
    "the senzing bootcamp",
    "senzing bootcamp",
    "start the senzing",
    "graduate the senzing",
    "give senzing bootcamp",
    "the senzing bootcamp feedback",
)

#: Near misses: a word dropped, a word swapped, or the words reordered, so no
#: complete phrase survives as a substring.
_NEAR_MISSES = (
    "start the bootcamp",
    "start a senzing bootcamp",
    "graduate senzing bootcamp",
    "graduate from the senzing bootcamp",
    "give feedback on the senzing bootcamp",
    "senzing bootcamp feedback please",
)

_UNRELATED = (
    "what is entity resolution",
    "load the truth set into the docker container",
    "show me module three",
    "",
)


def _embedded_phrase() -> st.SearchStrategy[str]:
    return st.builds(
        lambda prefix, phrase, suffix: f"{prefix}{phrase}{suffix}",
        st.sampled_from(("", "hey kiro, ", "can you please ", "i would like to ")),
        st.sampled_from(_PHRASES),
        st.sampled_from(("", " now", " for me, thanks", " when you are ready")),
    )


STATEMENT_CASES: Mapping[str, st.SearchStrategy[str]] = {
    "exact_phrase": st.sampled_from(_PHRASES),
    "phrase_in_longer_text": _embedded_phrase(),
    "case_variant": st.sampled_from(_PHRASES).map(str.title),
    "overlapping_fragments": st.sampled_from(_OVERLAPPING_FRAGMENTS),
    "near_miss": st.sampled_from(_NEAR_MISSES),
    "unrelated": st.sampled_from(_UNRELATED),
    "free_text": _sentence(),
}


def statement() -> st.SearchStrategy[str]:
    """Bootcamper utterances tested against command trigger phrases.

    Edge cases: exact phrases, overlapping phrase fragments, near-misses, and
    phrases embedded as substrings of longer text.
    """
    return _one_of(STATEMENT_CASES)


# ---------------------------------------------------------------------------
# 8. failure_point() — fault-injection points
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FailurePoint:
    """Where to inject a fault, how it fails, and the code that must surface.

    `stage` is a point on the create/update path; `kind` is the fault's shape.
    `expected_error` is the catalog code the design assigns that combination:
    a write that cannot proceed is `E_WRITE_FAILED`, anything else on the
    transform path is `E_TRANSFORM_FAILED`.
    """

    stage: str
    kind: str
    expected_error: str


_FAILURE_STAGES = ("mid-write", "post-write-pre-validate", "mid-swap")
_WRITE_FAULTS = ("permission-denied", "path-is-a-file")


def _failure(stage: str, kind: str) -> FailurePoint:
    expected = "E_WRITE_FAILED" if kind in _WRITE_FAULTS else "E_TRANSFORM_FAILED"
    return FailurePoint(stage=stage, kind=kind, expected_error=expected)


FAILURE_POINT_CASES: Mapping[str, st.SearchStrategy[FailurePoint]] = {
    "mid_write": st.just(_failure("mid-write", "generic")),
    "post_write_pre_validate": st.just(_failure("post-write-pre-validate", "generic")),
    "mid_swap": st.just(_failure("mid-swap", "generic")),
    "permission_denied": st.sampled_from(_FAILURE_STAGES).map(
        lambda stage: _failure(stage, "permission-denied")
    ),
    "path_is_a_file": st.sampled_from(_FAILURE_STAGES).map(
        lambda stage: _failure(stage, "path-is-a-file")
    ),
}


def failure_point() -> st.SearchStrategy[FailurePoint]:
    """Fault-injection points for the atomicity property.

    Edge cases: mid-write, post-write pre-validate, mid-swap, permission
    denied, and path-is-a-file.
    """
    return _one_of(FAILURE_POINT_CASES)


# ---------------------------------------------------------------------------
# 9. reconcile_triple() — (previous manifest, on-disk Power, staging tree)
# ---------------------------------------------------------------------------


@dataclass
class ReconcileTriple:
    """The Reconciler's three inputs, plus how each path was constructed.

    `intents` names the construction — `local-edit-and-upstream-change`, say —
    not the bucket. Mapping an intent to a bucket is the design's
    classification table, which is what the property under test asserts.
    """

    manifest: dict[str, Any]
    previous: dict[str, str]
    on_disk: dict[str, str]
    staging: dict[str, str]
    intents: dict[str, str]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(
            sorted(set(self.previous) | set(self.on_disk) | set(self.staging))
        )


def _manifest_entry(path: str, content: str, owner: str) -> dict[str, Any]:
    return {
        "path": path,
        "ruleId": "command-skills" if owner == "kiro" else "skills-modules",
        "owner": owner,
        "sourcePath": None if owner == "kiro" else f"{TEMPLATE_PLUGIN_ROOT}/{path}",
        "sha256": _sha256(content),
    }


@st.composite
def _reconcile_triple(draw: Any, intents: Sequence[str]) -> ReconcileTriple:
    previous: dict[str, str] = {}
    on_disk: dict[str, str] = {}
    staging: dict[str, str] = {}
    manifest_files: list[dict[str, Any]] = []
    assigned: dict[str, str] = {}

    names = draw(
        st.lists(_slug(), min_size=len(intents), max_size=len(intents), unique=True)
    )
    for intent, name in zip(intents, names):
        path = f"skills/{name}/SKILL.md"
        base = draw(_prose()) + "\n"
        upstream = base + draw(_sentence()) + " (upstream)\n"
        local = base + draw(_sentence()) + " (local)\n"
        owner = "kiro" if intent == "kiro-owned" else "template"

        if intent == "unchanged":
            previous[path] = on_disk[path] = staging[path] = base
        elif intent == "upstream-change":
            previous[path] = on_disk[path] = base
            staging[path] = upstream
        elif intent == "local-edit-only":
            previous[path] = staging[path] = base
            on_disk[path] = local
        elif intent == "local-edit-and-upstream-change":
            previous[path] = base
            on_disk[path] = local
            staging[path] = upstream
        elif intent == "added":
            staging[path] = upstream
        elif intent == "removed":
            previous[path] = on_disk[path] = base
        elif intent == "kiro-owned":
            previous[path] = base
            on_disk[path] = draw(st.sampled_from((base, local)))
            staging[path] = base
        else:  # pragma: no cover - guarded by the case table below
            raise ValueError(f"unknown intent: {intent}")

        assigned[path] = intent
        if path in previous:
            manifest_files.append(_manifest_entry(path, previous[path], owner))

    return ReconcileTriple(
        manifest={
            "manifestVersion": 1,
            "templateRelease": draw(semver_tag()),
            "contractVersion": 1,
            "files": manifest_files,
        },
        previous=previous,
        on_disk=on_disk,
        staging=staging,
        intents=assigned,
    )


RECONCILE_TRIPLE_CASES: Mapping[str, st.SearchStrategy[ReconcileTriple]] = {
    # One path per intent: all four divergence combinations plus the rest.
    "all_intents": _reconcile_triple(RECONCILE_INTENTS),
    # The four prev/on-disk/staging divergence combinations on their own.
    "divergence_combinations": _reconcile_triple(
        (
            "unchanged",
            "upstream-change",
            "local-edit-only",
            "local-edit-and-upstream-change",
        )
    ),
    "additions": _reconcile_triple(("added", "added", "unchanged")),
    "removals": _reconcile_triple(("removed", "removed", "unchanged")),
    "kiro_owned": _reconcile_triple(("kiro-owned", "kiro-owned", "upstream-change")),
    "empty": _reconcile_triple(()),
    "mixed": st.lists(
        st.sampled_from(RECONCILE_INTENTS), min_size=1, max_size=7
    ).flatmap(_reconcile_triple),
}


def reconcile_triple() -> st.SearchStrategy[ReconcileTriple]:
    """Triples of (previous manifest, on-disk Power, staging tree).

    Edge cases: all four divergence combinations, additions, removals, and
    `kiro-owned` files.
    """
    return _one_of(RECONCILE_TRIPLE_CASES)


# ---------------------------------------------------------------------------
# 10. outcome_set() — Test_Checklist record outcomes
# ---------------------------------------------------------------------------


@dataclass
class OutcomeSet:
    """Recorded checklist outcomes for one version under test.

    `outcomes` maps a step number to `pass`/`fail`/`""`, except for the three
    per-platform steps, which map to one cell per Supported_Platform. A step
    absent from the mapping is a step with no recorded outcome at all.

    `defects` is empty exactly when the record gates tagging open: every one of
    the 17 steps recorded, every outcome a pass, all nine platform cells
    filled, and the record naming the version under test (R6 AC2, AC3, AC12).
    """

    version: str
    record_version: str
    outcomes: dict[int, Any]
    defects: tuple[str, ...] = ()

    @property
    def tag_allowed(self) -> bool:
        return self.defects == ()


def _complete_outcomes() -> dict[int, Any]:
    return {
        step: (
            {platform: "pass" for platform in SUPPORTED_PLATFORMS}
            if step in PER_PLATFORM_STEPS
            else "pass"
        )
        for step in range(1, CHECKLIST_STEP_COUNT + 1)
    }


def _outcome_set(
    version: str,
    *,
    record_version: str | None = None,
    mutate: Callable[[dict[int, Any]], tuple[str, ...]] | None = None,
) -> OutcomeSet:
    outcomes = _complete_outcomes()
    defects = mutate(outcomes) if mutate is not None else ()
    if record_version is not None and record_version != version:
        defects = defects + ("version-mismatch",)
    return OutcomeSet(
        version=version,
        record_version=record_version if record_version is not None else version,
        outcomes=outcomes,
        defects=defects,
    )


def _set_step(step: int, value: Any) -> Callable[[dict[int, Any]], tuple[str, ...]]:
    def mutate(outcomes: dict[int, Any]) -> tuple[str, ...]:
        if step in PER_PLATFORM_STEPS:
            outcomes[step] = {platform: value for platform in SUPPORTED_PLATFORMS}
        else:
            outcomes[step] = value
        label = "blank-outcome" if value == "" else "fail"
        return (f"{label}:{step}",)

    return mutate


def _drop_step(step: int) -> Callable[[dict[int, Any]], tuple[str, ...]]:
    def mutate(outcomes: dict[int, Any]) -> tuple[str, ...]:
        outcomes.pop(step, None)
        return (f"missing-step:{step}",)

    return mutate


def _blank_platform_cell(
    step: int, platform: str
) -> Callable[[dict[int, Any]], tuple[str, ...]]:
    def mutate(outcomes: dict[int, Any]) -> tuple[str, ...]:
        outcomes[step][platform] = ""
        return (f"blank-platform-cell:{step}:{platform}",)

    return mutate


_STEP_NUMBERS = st.integers(min_value=1, max_value=CHECKLIST_STEP_COUNT)


OUTCOME_SET_CASES: Mapping[str, st.SearchStrategy[OutcomeSet]] = {
    "complete_pass": st.builds(_outcome_set, semver_tag()),
    "missing_step": st.builds(
        lambda version, step: _outcome_set(version, mutate=_drop_step(step)),
        semver_tag(),
        _STEP_NUMBERS,
    ),
    "blank_outcome": st.builds(
        lambda version, step: _outcome_set(version, mutate=_set_step(step, "")),
        semver_tag(),
        _STEP_NUMBERS,
    ),
    "explicit_fail": st.builds(
        lambda version, step: _outcome_set(version, mutate=_set_step(step, "fail")),
        semver_tag(),
        _STEP_NUMBERS,
    ),
    "version_mismatch": st.builds(
        lambda version, other: _outcome_set(
            version, record_version=other if other != version else f"{other}-rc"
        ),
        semver_tag(),
        semver_tag(),
    ),
    "blank_platform_cell": st.builds(
        lambda version, step, platform: _outcome_set(
            version, mutate=_blank_platform_cell(step, platform)
        ),
        semver_tag(),
        st.sampled_from(PER_PLATFORM_STEPS),
        st.sampled_from(SUPPORTED_PLATFORMS),
    ),
}


def outcome_set() -> st.SearchStrategy[OutcomeSet]:
    """Test-record outcomes for the tagging gate.

    Edge cases: missing steps, blank outcomes, explicit fails, a version
    mismatch, and per-platform cells left blank.
    """
    return _one_of(OUTCOME_SET_CASES)


# ---------------------------------------------------------------------------
# 11. interpreter_path() — absolute interpreter and script paths
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InterpreterPathCase:
    """An absolute interpreter path and script path, plus what makes them hard.

    `flavor` is `posix`, `windows-drive`, or `unc`. `features` names the
    adversarial content in the directory component: spaces, a trailing space,
    an embedded quote, or a character a shell would read as an operator.
    """

    interpreter: str
    script: str
    flavor: str
    features: tuple[str, ...] = ()


#: Directory names that break naive command-string assembly. A trailing space
#: and an embedded quote sit on a directory component rather than at the end of
#: the path, so the script keeps its `.py` extension.
_HARD_DIRECTORY_NAMES: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "single_space": ("Bob Smith", ("space",)),
    "repeated_spaces": ("Bob  Smith", ("space", "repeated-spaces")),
    "trailing_space": ("Bob Smith ", ("space", "trailing-space")),
    "embedded_quote": ('Bob "Bo" Smith', ("space", "embedded-quote")),
    "ampersand": ("bob&alice", ("shell-char:&",)),
    "pipe": ("bob|alice", ("shell-char:|",)),
    "semicolon": ("bob;alice", ("shell-char:;",)),
    "redirect": ("bob>alice", ("shell-char:>",)),
    "all_shell_chars": ("a&b|c;d>e", ("shell-char:&", "shell-char:|", "shell-char:;", "shell-char:>")),
}

_PLAIN_DIRECTORY_NAMES = ("bob", "maintainer", "senzing", "workspace")
PATH_FLAVORS = ("posix", "windows-drive", "unc")


def _interpreter_case(
    flavor: str, directory: str, script_name: str, features: tuple[str, ...]
) -> InterpreterPathCase:
    scripts = "powers/senzing-bootcamp/skills/bootcamp-onboarding/scripts"
    if flavor == "posix":
        interpreter = f"/home/{directory}/.venv/bin/python3.12"
        script = f"/home/{directory}/{scripts}/{script_name}"
    elif flavor == "windows-drive":
        windows_scripts = scripts.replace("/", "\\")
        interpreter = (
            f"C:\\Users\\{directory}\\AppData\\Local\\Programs"
            "\\Python\\Python312\\python.exe"
        )
        script = f"C:\\Users\\{directory}\\{windows_scripts}\\{script_name}"
    elif flavor == "unc":
        windows_scripts = scripts.replace("/", "\\")
        interpreter = "\\\\build01\\tools\\Python312\\python.exe"
        script = f"\\\\build01\\{directory}\\{windows_scripts}\\{script_name}"
    else:  # pragma: no cover - guarded by the case table below
        raise ValueError(f"unknown flavor: {flavor}")
    return InterpreterPathCase(
        interpreter=interpreter, script=script, flavor=flavor, features=features
    )


def _paths(
    flavors: Sequence[str], directories: st.SearchStrategy[tuple[str, tuple[str, ...]]]
) -> st.SearchStrategy[InterpreterPathCase]:
    return st.builds(
        lambda flavor, directory, script_name: _interpreter_case(
            flavor, directory[0], script_name, directory[1]
        ),
        st.sampled_from(list(flavors)),
        directories,
        st.sampled_from(HOOK_SCRIPT_NAMES),
    )


_PLAIN_DIRECTORIES = st.sampled_from(_PLAIN_DIRECTORY_NAMES).map(
    lambda name: (name, ())
)


def _hard_directories(*keys: str) -> st.SearchStrategy[tuple[str, tuple[str, ...]]]:
    return st.sampled_from([_HARD_DIRECTORY_NAMES[key] for key in keys])


INTERPRETER_PATH_CASES: Mapping[str, st.SearchStrategy[InterpreterPathCase]] = {
    "posix": _paths(("posix",), _PLAIN_DIRECTORIES),
    "windows_drive_letter": _paths(("windows-drive",), _PLAIN_DIRECTORIES),
    "unc_prefix": _paths(("unc",), _PLAIN_DIRECTORIES),
    "single_space": _paths(PATH_FLAVORS, _hard_directories("single_space")),
    "repeated_spaces": _paths(PATH_FLAVORS, _hard_directories("repeated_spaces")),
    "trailing_space": _paths(PATH_FLAVORS, _hard_directories("trailing_space")),
    "embedded_quote": _paths(PATH_FLAVORS, _hard_directories("embedded_quote")),
    "shell_operator_chars": _paths(
        PATH_FLAVORS, _hard_directories("ampersand", "pipe", "semicolon", "redirect")
    ),
    "all_shell_operator_chars": _paths(PATH_FLAVORS, _hard_directories("all_shell_chars")),
}


def interpreter_path() -> st.SearchStrategy[InterpreterPathCase]:
    """Absolute interpreter and script paths for Hook_Command_String assembly.

    Edge cases: POSIX and Windows path shapes, drive letters, UNC prefixes,
    single and repeated spaces, a trailing space, an embedded quote, and
    directory names containing `&`, `|`, `;`, and `>`.
    """
    return _one_of(INTERPRETER_PATH_CASES)


# ---------------------------------------------------------------------------
# 12. discount_register() — invariantDiscounts lists
# ---------------------------------------------------------------------------


@dataclass
class DiscountRegisterCase:
    """An `invariantDiscounts` list and the defects seeded into it.

    `defects` is empty exactly when every entry carries a non-empty
    `invariant`, `conflictsWith`, and `resolution`, and no entry names the
    honored invariant `INV-052` (R15 AC5, AC6).

    Near-miss spellings are labeled rather than silently classified.
    `inv-052` and `INV-052 ` denote the honored invariant under a different
    spelling, so they carry the `inv-052` defect and a `near_miss` label;
    `INV-52` is a different identifier and carries only the label. A property
    test asserting normalization reads `near_miss`; one asserting the plain
    exclusion reads `defects`.
    """

    entries: tuple[dict[str, str], ...]
    defects: tuple[str, ...] = ()
    near_miss: str | None = None

    @property
    def valid(self) -> bool:
        return self.defects == ()


_DISCOUNT_FIELDS = ("invariant", "conflictsWith", "resolution")


def _discount_entry(identifier: str) -> dict[str, str]:
    return {
        "invariant": identifier,
        "conflictsWith": "Agent Plugins v1.0.0 single-command-string hook schema",
        "resolution": "install-time absolute-path resolution; nothing protected is lost",
    }


def _register(
    identifiers: Sequence[str],
    *,
    mutate: tuple[int, str, str | None] | None = None,
    defects: tuple[str, ...] = (),
    near_miss: str | None = None,
) -> DiscountRegisterCase:
    entries = [_discount_entry(identifier) for identifier in identifiers]
    if mutate is not None:
        index, key, value = mutate
        if value is None:
            entries[index].pop(key)
        else:
            entries[index][key] = value
    return DiscountRegisterCase(
        entries=tuple(entries), defects=defects, near_miss=near_miss
    )


def _identifiers(min_size: int = 1, max_size: int = 3) -> st.SearchStrategy[list[str]]:
    return st.lists(
        st.sampled_from(DISCOUNTED_INVARIANTS),
        min_size=min_size,
        max_size=max_size,
        unique=True,
    )


def _register_missing_field(kind: str) -> st.SearchStrategy[DiscountRegisterCase]:
    blanks: Mapping[str, st.SearchStrategy[str | None]] = {
        "missing-field": st.none(),
        "empty-field": st.just(""),
        "whitespace-field": st.sampled_from((" ", "   ", "\t")),
    }
    return st.builds(
        lambda identifiers, key, value: _register(
            identifiers,
            mutate=(len(identifiers) - 1, key, value),
            defects=(f"{kind}:{key}",),
        ),
        _identifiers(),
        st.sampled_from(_DISCOUNT_FIELDS),
        blanks[kind],
    )


DISCOUNT_REGISTER_CASES: Mapping[str, st.SearchStrategy[DiscountRegisterCase]] = {
    "empty": st.builds(lambda: DiscountRegisterCase(entries=())),
    "valid": _identifiers().map(lambda identifiers: _register(identifiers)),
    "missing_field": _register_missing_field("missing-field"),
    "empty_field": _register_missing_field("empty-field"),
    "whitespace_field": _register_missing_field("whitespace-field"),
    # INV-052 is honored, not discounted: its presence is E_HONORED_INVARIANT_DISCOUNTED.
    "inv_052": _identifiers(min_size=0, max_size=2).map(
        lambda identifiers: _register(
            list(identifiers) + [HONORED_INVARIANT], defects=("inv-052",)
        )
    ),
    "inv_052_lowercase": st.builds(
        lambda: _register(["inv-052"], defects=("inv-052",), near_miss="inv-052")
    ),
    "inv_052_trailing_space": st.builds(
        lambda: _register(["INV-052 "], defects=("inv-052",), near_miss="INV-052 ")
    ),
    # A different invariant number that reads like INV-052 and is not it.
    "inv_52_distinct": st.builds(lambda: _register(["INV-52"], near_miss="INV-52")),
}


def discount_register() -> st.SearchStrategy[DiscountRegisterCase]:
    """`invariantDiscounts` lists for the register completeness check.

    Edge cases: an empty list, a missing field, an empty-string field, a
    whitespace-only field, an `INV-052` entry, and the near-misses `inv-052`,
    `INV-52`, and `INV-052 `.
    """
    return _one_of(DISCOUNT_REGISTER_CASES)


# ---------------------------------------------------------------------------
# 13. inv_prose() — prose carrying INV-NNN citations
# ---------------------------------------------------------------------------

_CITATION_PATTERN = re.compile(r"INV-\d{2,3}")


@dataclass
class InvProseCase:
    """Ported prose, its `INV-NNN` citations, and its residual Claude refs.

    `citations` is every `INV-NNN` occurrence in document order, extracted from
    the finished text — a multiset, so a repeated citation counts twice, which
    is what the fidelity guarantee is about. `residual_claude_refs` names the
    genuine residual model references seeded into the same document; the
    citation exemption covers the citation token only, never these.
    """

    text: str
    residual_claude_refs: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    citations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.citations = tuple(_CITATION_PATTERN.findall(self.text))

    @property
    def citation_count(self) -> int:
        return len(self.citations)


def _inv_prose(
    text: str,
    *,
    residual: tuple[str, ...] = (),
    features: tuple[str, ...] = (),
) -> InvProseCase:
    return InvProseCase(text=text, residual_claude_refs=residual, features=features)


def _prose_zero() -> st.SearchStrategy[InvProseCase]:
    return _prose(2, 4).map(lambda text: _inv_prose(text + "\n"))


def _prose_one() -> st.SearchStrategy[InvProseCase]:
    return st.builds(
        lambda body, invariant: _inv_prose(f"{body}\nThis follows {invariant}.\n"),
        _prose(),
        st.sampled_from(DISCOUNTED_INVARIANTS + (HONORED_INVARIANT,)),
    )


def _prose_many() -> st.SearchStrategy[InvProseCase]:
    return st.builds(
        lambda body, invariants: _inv_prose(
            body
            + "\n"
            + "\n".join(
                f"- {invariant} applies at step {index}."
                for index, invariant in enumerate(invariants)
            )
            + "\n"
        ),
        _prose(),
        st.lists(
            st.sampled_from(DISCOUNTED_INVARIANTS + (HONORED_INVARIANT,)),
            min_size=2,
            max_size=6,
        ),
    )


def _prose_discounted() -> st.SearchStrategy[InvProseCase]:
    return st.builds(
        lambda body, invariant: _inv_prose(
            f"{body}\nThe register discounts {invariant}; the citation stays verbatim.\n",
            features=("discounted-citation",),
        ),
        _prose(),
        st.sampled_from(DISCOUNTED_INVARIANTS),
    )


def _prose_in_code_fence() -> st.SearchStrategy[InvProseCase]:
    return st.builds(
        lambda body, invariant, language: _inv_prose(
            f"{body}\n\n```{language}\n# {invariant}: keep this comment intact\n"
            f'GUARD = "{invariant}"\n```\n\nAnd inline `{invariant}` as well.\n',
            features=("citation-in-code-fence",),
        ),
        _prose(),
        st.sampled_from(DISCOUNTED_INVARIANTS + (HONORED_INVARIANT,)),
        st.sampled_from(("python", "text", "")),
    )


def _prose_adjacent_residual() -> st.SearchStrategy[InvProseCase]:
    return st.builds(
        lambda body, invariant, residual: _inv_prose(
            f"{body}\nPer {invariant}, run this exercise on the {residual} "
            f"before citing {invariant} again.\n",
            residual=(residual,),
            features=("citation-adjacent-residual",),
        ),
        _prose(),
        st.sampled_from(DISCOUNTED_INVARIANTS + (HONORED_INVARIANT,)),
        st.sampled_from(CLAUDE_MODEL_REFERENCES),
    )


INV_PROSE_CASES: Mapping[str, st.SearchStrategy[InvProseCase]] = {
    "zero_citations": _prose_zero(),
    "one_citation": _prose_one(),
    "many_citations": _prose_many(),
    "discounted_citations": _prose_discounted(),
    "citations_in_code_fence": _prose_in_code_fence(),
    "citation_adjacent_to_residual": _prose_adjacent_residual(),
}


def inv_prose() -> st.SearchStrategy[InvProseCase]:
    """Prose with inline `INV-NNN` citations.

    Edge cases: zero, one, and many citations; citations of discounted
    invariants; citations inside code fences; and a citation adjacent to a
    genuine residual Claude model name in the same document.
    """
    return _one_of(INV_PROSE_CASES)
