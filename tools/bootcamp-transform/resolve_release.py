#!/usr/bin/env python3
"""Version_Resolver — resolve the latest versioned Template_Release (R1).

    resolve_release.py [--repo Senzing/senzing-bootcamp-claude-plugin]
                       [--min-version <semver>]   # update path: only newer than this
                       --out <dir>                # where to extract the source tree

JSON goes to stdout; human-readable narration goes to stderr. The maintainer
skills read the JSON, so agent behavior stays out of the deterministic path.

Behavior
--------
1. List releases via ``gh release list --repo <repo> --json
   tagName,isDraft,isPrerelease,publishedAt``, falling back to the GitHub REST
   API when ``gh`` is unavailable.
2. Keep only published, ``isDraft == false``, ``isPrerelease == false`` records
   whose ``tagName`` parses as **bare semver** — no ``v`` prefix *(R1 AC1, AC2)*.
3. Select the **semver maximum**: not the lexicographic maximum (``0.10.0`` beats
   ``0.9.0``) and not the most recently published release.
4. Fetch the source tree **at the resolved tag** — ``git clone --depth 1
   --branch <tag>`` with verification that HEAD is that tag's commit, or a
   tarball of ``refs/tags/<tag>``. Never ``main`` *(R1 AC3)*.
5. Emit a ``ResolvedRelease`` record so every later step and generated artifact
   references the exact resolved tag *(R1 AC5)*.

Outcomes
--------
============================================ ==================== ====
Condition                                    ``error``            exit
============================================ ==================== ====
Resolved                                     (absent)             0
Zero releases survive the filter             ``E_NO_RELEASE``     1
No result within 30 s after 3 attempts       ``E_RESOLVE_FAILED`` 1
Resolved max <= ``--min-version``            ``E_ALREADY_CURRENT`` 0
============================================ ==================== ====

Both failure codes exit non-zero and produce **no** build artifact — nothing is
fetched and nothing is written. ``E_ALREADY_CURRENT`` is informational rather
than an error *(R5 AC2)*: it exits zero, reports the current state, and
deliberately skips the fetch so that no tree is materialized for a build that
must not happen. It shares the failure record's ``error``/``message``/``attempts``
shape so one field lookup tells a caller which of the four outcomes occurred.

Testability
-----------
Release filtering and selection are pure functions over the record shape ``gh``
returns (``eligible_releases``, ``select_release``, ``is_newer``), so the
property tests drive them with generated release lists and no network. `resolve`
takes optional ``lister``/``fetcher``/``clock``/``sleeper`` injections for the
same reason.

Invariant sourcing
------------------
`read_invariant_text` is the only sanctioned reader of Template_Invariant text:
it reads from the resolved release tree and refuses any path outside it, so no
invariant definition can be sourced from the template's development repository
*(R15 AC9)*.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

__all__ = [
    # Error and outcome codes.
    "E_ALREADY_CURRENT",
    "E_NO_RELEASE",
    "E_RESOLVE_FAILED",
    "ResolutionError",
    # Budget facts from R1 AC6.
    "MAX_ATTEMPTS",
    "RESOLUTION_BUDGET_SECONDS",
    # Defaults.
    "DEFAULT_PLUGIN_ROOT",
    "DEFAULT_REPO",
    # Pure selection logic (Property 1).
    "eligible_releases",
    "is_eligible",
    "is_newer",
    "is_published",
    "parse_semver",
    "select_release",
    "semver_string",
    "source_ref",
    # Record construction.
    "already_current_payload",
    "resolved_release",
    # Orchestration and CLI.
    "fetch_source_tree",
    "list_releases",
    "main",
    "resolve",
    # Resolved-tree readers.
    "read_invariant_text",
    "release_tree_root",
    "template_source_root",
]


# ---------------------------------------------------------------------------
# Facts from the requirements and the design
# ---------------------------------------------------------------------------

#: Fallbacks for the two `template` facts the Transformation_Contract owns. The
#: contract is the single source (R3 AC1); these apply only when it cannot be
#: read, so the resolver still runs standalone.
DEFAULT_REPO = "Senzing/senzing-bootcamp-claude-plugin"
DEFAULT_PLUGIN_ROOT = "plugins/senzing-bootcamp"

#: The Transformation_Contract, resolved relative to this file so the resolver
#: works from any working directory.
CONTRACT_PATH = Path(__file__).resolve().parent / "contract.yaml"

#: R1 AC6: no result within 30 s after 3 attempts is E_RESOLVE_FAILED. The
#: budget spans the attempts; each attempt receives an equal share of whatever
#: remains, so three attempts always fit inside the 30 s.
MAX_ATTEMPTS = 3
RESOLUTION_BUDGET_SECONDS = 30.0
RETRY_BACKOFF_SECONDS = 0.5

#: The fields the design's release query requests, in the design's order.
GH_JSON_FIELDS = "tagName,isDraft,isPrerelease,publishedAt"
GH_RELEASE_LIMIT = 200
REST_PAGE_SIZE = 100
REST_MAX_PAGES = 5

#: Outcome codes from the maintainer-facing error catalog.
E_NO_RELEASE = "E_NO_RELEASE"
E_RESOLVE_FAILED = "E_RESOLVE_FAILED"
E_ALREADY_CURRENT = "E_ALREADY_CURRENT"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

#: Bare semver, no `v` prefix, as the template tags its releases. Leading zeros
#: are accepted and normalized by parsing, so `0.05.1` and `0.5.1` denote the
#: same version while remaining distinct strings (R2 AC1 stamps the string).
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

#: `owner/name`, validated before it reaches an argv or a URL.
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


class ResolutionError(RuntimeError):
    """A halting resolver outcome: `E_NO_RELEASE` or `E_RESOLVE_FAILED`.

    Both halt the build and produce no artifact *(R1 AC4, AC6)*. `attempts`
    counts the attempts made by the phase named in `message`.
    """

    def __init__(self, code: str, message: str, attempts: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.attempts = attempts

    def payload(self) -> dict[str, Any]:
        """The design's failure record."""
        return {"error": self.code, "message": self.message, "attempts": self.attempts}


# ---------------------------------------------------------------------------
# Narration (stderr) — never stdout, which carries only the JSON record
# ---------------------------------------------------------------------------


def _narrate(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Pure selection logic (Property 1)
# ---------------------------------------------------------------------------


def parse_semver(tag: str) -> tuple[int, int, int] | None:
    """Return `(major, minor, patch)` for a bare semver tag, else `None`.

    Bare means exactly `MAJOR.MINOR.PATCH` with no `v` prefix, which is how the
    template tags its releases. A tag in any other shape is not a version this
    resolver can order, so it is excluded from selection rather than guessed at.
    """
    if not isinstance(tag, str):
        return None
    match = _SEMVER_RE.match(tag.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def semver_string(version: Sequence[int]) -> str:
    """The canonical spelling of a parsed version: `0.5.1`, never `0.05.1`."""
    major, minor, patch = version
    return f"{major}.{minor}.{patch}"


def is_published(record: Mapping[str, Any]) -> bool:
    """Whether GitHub reports this release as published.

    A record whose `publishedAt` is null or blank is a release GitHub has not
    published. A record that omits the key altogether did not report the field
    at all — the draft and prerelease flags then carry the filter, rather than a
    missing field silently excluding every release.
    """
    if "publishedAt" not in record:
        return True
    published_at = record["publishedAt"]
    return published_at is not None and str(published_at).strip() != ""


def is_eligible(record: Mapping[str, Any]) -> bool:
    """Whether a release record can be selected *(R1 AC1, AC2)*.

    Eligible means published, not a draft, not a prerelease, and carrying a tag
    that parses as bare semver.
    """
    if bool(record.get("isDraft", False)) or bool(record.get("isPrerelease", False)):
        return False
    if not is_published(record):
        return False
    return parse_semver(record.get("tagName", "")) is not None


def eligible_releases(
    records: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """The subset of `records` that `select_release` chooses among."""
    return [record for record in records if is_eligible(record)]


def select_release(
    records: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """The eligible release with the maximum tag by semver precedence.

    Not the lexicographic maximum (`0.10.0 > 0.9.0`) and not the most recently
    published release *(R1 AC1, AC2)*. Returns `None` when no record is
    eligible, which the caller reports as `E_NO_RELEASE` *(R1 AC4)*.

    Ties are broken deterministically and independently of input order: two
    spellings of one version (`0.5.1` and `0.05.1`) are the same version, so the
    canonical spelling wins, then the lexicographically smallest tag. The
    publish date is never consulted, not even as a tie-break.
    """
    eligible = eligible_releases(records)
    if not eligible:
        return None
    highest = max(parse_semver(record["tagName"]) for record in eligible)
    canonical = semver_string(highest)
    tied = [
        record for record in eligible if parse_semver(record["tagName"]) == highest
    ]
    return min(
        tied,
        key=lambda record: (
            0 if record["tagName"] == canonical else 1,
            record["tagName"],
        ),
    )


def source_ref(tag: str) -> str:
    """The tag ref for `tag`. A branch ref is never produced *(R1 AC3)*."""
    return f"refs/tags/{tag}"


def is_newer(tag: str, min_version: str) -> bool:
    """Whether `tag` is greater than `min_version` by semver precedence.

    This is the update path's "a newer Template_Release exists" predicate
    *(R5 AC1)*; its negation is `E_ALREADY_CURRENT` *(R5 AC2)*.
    """
    candidate = parse_semver(tag)
    floor = parse_semver(min_version)
    if candidate is None:
        raise ValueError(f"not a bare semver tag: {tag!r}")
    if floor is None:
        raise ValueError(f"not a bare semver version: {min_version!r}")
    return candidate > floor


# ---------------------------------------------------------------------------
# Output records
# ---------------------------------------------------------------------------


def resolved_release(
    repository: str,
    record: Mapping[str, Any],
    plugin_root: str,
    extracted_to: str | os.PathLike[str],
    attempts: int,
) -> dict[str, Any]:
    """The `ResolvedRelease` record, in the design's field order *(R1 AC5)*."""
    tag = record["tagName"]
    version = parse_semver(tag)
    if version is None:  # pragma: no cover - selection guarantees a parse
        raise ValueError(f"not a bare semver tag: {tag!r}")
    return {
        "repository": repository,
        "tag": tag,
        "semver": list(version),
        "isDraft": bool(record.get("isDraft", False)),
        "isPrerelease": bool(record.get("isPrerelease", False)),
        "sourceRef": source_ref(tag),
        "pluginRoot": plugin_root,
        "extractedTo": str(extracted_to),
        "attempts": attempts,
    }


def already_current_payload(
    repository: str, tag: str, min_version: str, attempts: int
) -> dict[str, Any]:
    """The informational `E_ALREADY_CURRENT` record *(R5 AC2)*.

    Carries the failure record's shape plus what the Update_Skill needs to
    report the current state, and deliberately omits `extractedTo`: nothing was
    fetched, because nothing is going to be built.
    """
    version = parse_semver(tag)
    return {
        "error": E_ALREADY_CURRENT,
        "message": (
            f"the Bootcamp_Power is current: the latest Template_Release {tag} "
            f"is not greater than {min_version}"
        ),
        "attempts": attempts,
        "repository": repository,
        "tag": tag,
        "semver": list(version) if version else None,
        "minVersion": min_version,
    }


# ---------------------------------------------------------------------------
# Resolved-tree readers — the release tree is the only source (R15 AC9)
# ---------------------------------------------------------------------------


def release_tree_root(resolved: Mapping[str, Any]) -> Path:
    """The extracted release tree root: the repository root at the resolved tag."""
    return Path(resolved["extractedTo"])


def template_source_root(resolved: Mapping[str, Any]) -> Path:
    """Where template sources begin: the plugin root inside the release tree.

    The template is a marketplace repository, so sources are rooted at
    `plugins/senzing-bootcamp`, not at the repository root.
    """
    return release_tree_root(resolved) / resolved["pluginRoot"]


def read_invariant_text(
    resolved: Mapping[str, Any], relative_path: str | os.PathLike[str]
) -> str:
    """Read Template_Invariant text from the resolved Template_Release *(R15 AC9)*.

    This is the only sanctioned reader of invariant text in the tooling. It is
    bounded by the resolved release tree and rejects any path that escapes it,
    so an invariant definition cannot be sourced from the template's development
    repository or from anywhere else on disk.
    """
    root = release_tree_root(resolved).resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(
            f"refusing to read Template_Invariant text outside the resolved "
            f"release tree: {os.fspath(relative_path)!r}"
        )
    return target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Attempt budget (R1 AC6)
# ---------------------------------------------------------------------------


@dataclass
class _Budget:
    """The 30 s resolution budget, shared by every remote phase of one run."""

    deadline: float
    clock: Callable[[], float]

    def remaining(self) -> float:
        return self.deadline - self.clock()


def _attempt_loop(
    operation: Callable[[float], Any],
    *,
    what: str,
    budget: _Budget,
    sleeper: Callable[[float], None],
) -> tuple[Any, int]:
    """Run `operation(timeout)` up to `MAX_ATTEMPTS` times inside the budget.

    Each attempt receives an equal share of the remaining budget, so three
    attempts fit inside 30 s even when every one of them hangs. Exhausting the
    attempts or the budget raises `E_RESOLVE_FAILED` carrying the number of
    attempts actually made *(R1 AC6)*.

    Any exception from `operation` is a retryable resolution fault: a `gh`
    failure, a timeout, an HTTP error, malformed JSON, and a failed extraction
    are all "the query did not return a result", and distinguishing them would
    not change the Maintainer's response.
    """
    attempts = 0
    last_error: BaseException | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        remaining = budget.remaining()
        if remaining <= 0:
            break
        attempts = attempt
        share = remaining / (MAX_ATTEMPTS - attempt + 1)
        try:
            return operation(share), attempts
        except ResolutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - see the docstring
            last_error = exc
            _narrate(
                f"attempt {attempt}/{MAX_ATTEMPTS} to {what} failed: "
                f"{type(exc).__name__}: {exc}"
            )
        if attempt < MAX_ATTEMPTS:
            backoff = min(RETRY_BACKOFF_SECONDS, max(budget.remaining(), 0.0))
            if backoff > 0:
                sleeper(backoff)

    detail = f": {last_error}" if last_error is not None else ""
    raise ResolutionError(
        E_RESOLVE_FAILED,
        f"release resolution failed: could not {what} within "
        f"{RESOLUTION_BUDGET_SECONDS:g}s after {attempts} attempt(s){detail}",
        attempts,
    )


# ---------------------------------------------------------------------------
# Listing releases: `gh` first, GitHub REST as the fallback
# ---------------------------------------------------------------------------


def _require_repo(repository: str) -> str:
    if not _REPO_RE.match(repository or ""):
        raise ValueError(f"not an owner/name repository: {repository!r}")
    return repository


def _run(argv: Sequence[str], *, timeout: float) -> str:
    """Run `argv` with no shell and return stdout, raising on failure."""
    completed = subprocess.run(  # noqa: S603 - argv list, never a shell string
        list(argv),
        capture_output=True,
        text=True,
        timeout=max(timeout, 0.0),
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip().splitlines()
        tail = stderr[-1] if stderr else "no stderr"
        raise RuntimeError(f"`{argv[0]}` exited {completed.returncode}: {tail}")
    return completed.stdout


def _github_request(url: str) -> urllib.request.Request:
    request = urllib.request.Request(url)  # noqa: S310 - https, host-validated below
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "senzing-bootcamp-version-resolver")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        # Sent only to api.github.com, and never narrated.
        request.add_header("Authorization", f"Bearer {token}")
    return request


def _read_url(url: str, *, timeout: float) -> bytes:
    if not url.startswith("https://"):  # pragma: no cover - constructed above
        raise ValueError(f"refusing a non-HTTPS request: {url!r}")
    with urllib.request.urlopen(  # noqa: S310 - https enforced above
        _github_request(url), timeout=max(timeout, 0.0)
    ) as response:
        return response.read()


def normalize_rest_release(record: Mapping[str, Any]) -> dict[str, Any]:
    """Map a GitHub REST release object onto the `gh release list` record shape."""
    return {
        "tagName": record.get("tag_name", ""),
        "isDraft": bool(record.get("draft", False)),
        "isPrerelease": bool(record.get("prerelease", False)),
        "publishedAt": record.get("published_at"),
    }


def _list_releases_gh(repository: str, *, timeout: float) -> list[dict[str, Any]]:
    stdout = _run(
        [
            "gh",
            "release",
            "list",
            "--repo",
            repository,
            "--json",
            GH_JSON_FIELDS,
            "--limit",
            str(GH_RELEASE_LIMIT),
        ],
        timeout=timeout,
    )
    records = json.loads(stdout or "[]")
    if not isinstance(records, list):
        raise ValueError("`gh release list` did not return a JSON array")
    return records


def _list_releases_rest(repository: str, *, timeout: float) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page in range(1, REST_MAX_PAGES + 1):
        url = (
            f"https://api.github.com/repos/{repository}/releases"
            f"?per_page={REST_PAGE_SIZE}&page={page}"
        )
        payload = json.loads(_read_url(url, timeout=timeout).decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError("the GitHub releases endpoint did not return an array")
        records.extend(normalize_rest_release(item) for item in payload)
        if len(payload) < REST_PAGE_SIZE:
            break
    return records


def list_releases(repository: str, *, timeout: float) -> list[dict[str, Any]]:
    """List releases in the `gh release list --json ...` record shape.

    Uses `gh` when it is on PATH and falls back to the GitHub REST API when it
    is not, or when it fails: an absent CLI must not look like an absent release.
    """
    _require_repo(repository)
    if shutil.which("gh"):
        try:
            return _list_releases_gh(repository, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - fall back, then narrate
            _narrate(f"`gh` could not list releases ({exc}); trying the REST API")
    return _list_releases_rest(repository, timeout=timeout)


# ---------------------------------------------------------------------------
# Fetching the source tree at the resolved tag — never `main` (R1 AC3)
# ---------------------------------------------------------------------------


def _clone_at_tag(
    repository: str, tag: str, target: Path, *, timeout: float
) -> Path:
    """Shallow-clone `repository` at `tag` and verify HEAD is that tag's commit."""
    _run(
        [
            "git",
            "-c",
            "advice.detachedHead=false",
            "clone",
            "--depth",
            "1",
            "--single-branch",
            "--branch",
            tag,
            f"https://github.com/{repository}.git",
            str(target),
        ],
        timeout=timeout,
    )
    head = _run(["git", "-C", str(target), "rev-parse", "HEAD"], timeout=timeout)
    tagged = _run(
        ["git", "-C", str(target), "rev-parse", f"{source_ref(tag)}^{{commit}}"],
        timeout=timeout,
    )
    if head.strip() != tagged.strip():
        raise RuntimeError(
            f"clone HEAD is not the commit of {source_ref(tag)}; refusing a "
            "tree that may be a branch head"
        )
    shutil.rmtree(target / ".git", ignore_errors=True)
    return target


def _safe_extract(tar: tarfile.TarFile, destination: Path) -> None:
    """Extract `tar` under `destination`, refusing members that escape it."""
    root = destination.resolve()
    for member in tar.getmembers():
        member_target = (root / member.name).resolve()
        if member_target != root and root not in member_target.parents:
            raise ValueError(f"tarball member escapes the destination: {member.name!r}")
        if member.issym() or member.islnk():
            link_target = (member_target.parent / member.linkname).resolve()
            if link_target != root and root not in link_target.parents:
                raise ValueError(f"tarball link escapes the destination: {member.name!r}")
    try:
        tar.extractall(destination, filter="data")  # noqa: S202 - checked above
    except TypeError:  # pragma: no cover - Python without extraction filters
        tar.extractall(destination)  # noqa: S202 - checked above


def _download_tarball(
    repository: str, tag: str, target: Path, *, timeout: float
) -> Path:
    """Download and extract the tarball of `refs/tags/<tag>`."""
    url = f"https://api.github.com/repos/{repository}/tarball/{source_ref(tag)}"
    payload = _read_url(url, timeout=timeout)
    staging = target.parent / f"{target.name}.tar"
    staging.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
        _safe_extract(tar, staging)
    entries = list(staging.iterdir())
    # A GitHub tarball wraps the repository in one `<owner>-<repo>-<sha>` directory;
    # the record's `extractedTo` must be the repository root itself so that
    # `pluginRoot` resolves beneath it.
    if len(entries) == 1 and entries[0].is_dir():
        os.replace(entries[0], target)
        shutil.rmtree(staging, ignore_errors=True)
    else:
        os.replace(staging, target)
    return target


def fetch_source_tree(
    repository: str,
    tag: str,
    out_dir: str | os.PathLike[str],
    *,
    timeout: float,
) -> Path:
    """Materialize the tree at `tag` under `out_dir` and return its root.

    The tree lands at `<out_dir>/bootcamp-src-<tag>`, built in a staging
    directory beside it and swapped into place only once complete, so an
    interrupted fetch never leaves a half-tree behind. Only the tag ref is ever
    requested: `main` is not reachable from either path *(R1 AC3)*.
    """
    _require_repo(repository)
    if parse_semver(tag) is None:
        raise ValueError(f"not a bare semver tag: {tag!r}")

    parent = Path(out_dir).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / f"bootcamp-src-{tag}"
    staging = Path(tempfile.mkdtemp(prefix=f".bootcamp-src-{tag}.", dir=parent))
    try:
        tree: Path | None = None
        if shutil.which("git"):
            try:
                tree = _clone_at_tag(
                    repository, tag, staging / "tree", timeout=timeout
                )
            except Exception as exc:  # noqa: BLE001 - fall back to the tarball
                _narrate(f"`git clone` at {source_ref(tag)} failed ({exc}); trying the tarball")
                shutil.rmtree(staging / "tree", ignore_errors=True)
        if tree is None:
            tree = _download_tarball(
                repository, tag, staging / "tree", timeout=timeout
            )
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(tree, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


# ---------------------------------------------------------------------------
# The Transformation_Contract's `template` facts
# ---------------------------------------------------------------------------


def contract_template(
    contract_path: str | os.PathLike[str] = CONTRACT_PATH,
) -> tuple[str, str]:
    """Return `(repository, pluginRoot)` from the contract, or the defaults.

    The contract is the single source for both facts, so they are read rather
    than restated here. An unreadable contract falls back to the module
    defaults instead of failing: the resolver has to run before a build.
    """
    try:
        import yaml  # imported lazily so importing this module needs no yaml

        data = yaml.safe_load(Path(contract_path).read_text(encoding="utf-8")) or {}
        template = data.get("template") or {}
        repository = str(template.get("repository") or DEFAULT_REPO)
        plugin_root = str(template.get("pluginRoot") or DEFAULT_PLUGIN_ROOT)
        _require_repo(repository)
        return repository, plugin_root
    except Exception:  # noqa: BLE001 - any read or parse fault takes the defaults
        return DEFAULT_REPO, DEFAULT_PLUGIN_ROOT


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def resolve(
    *,
    out_dir: str | os.PathLike[str],
    repository: str | None = None,
    min_version: str | None = None,
    plugin_root: str | None = None,
    lister: Callable[[float], Iterable[Mapping[str, Any]]] | None = None,
    fetcher: Callable[[float], Path] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Resolve the latest Template_Release and return the record to emit.

    Returns the `ResolvedRelease` record on success, or the informational
    `E_ALREADY_CURRENT` record when `min_version` is already at or above the
    resolved maximum *(R5 AC2)* — in which case nothing is fetched. Raises
    `ResolutionError` for `E_NO_RELEASE` and `E_RESOLVE_FAILED`, both of which
    halt the build with no artifact *(R1 AC4, AC6)*.

    `lister`, `fetcher`, `clock`, and `sleeper` exist so tests can drive the
    resolver without a network or a wall clock.
    """
    contract_repository, contract_plugin_root = contract_template()
    repository = _require_repo(repository or contract_repository)
    plugin_root = plugin_root or contract_plugin_root
    if min_version is not None and parse_semver(min_version) is None:
        raise ValueError(f"not a bare semver version: {min_version!r}")

    budget = _Budget(deadline=clock() + RESOLUTION_BUDGET_SECONDS, clock=clock)
    query = lister or (
        lambda timeout: list_releases(repository, timeout=timeout)
    )

    _narrate(f"listing releases of {repository}")
    records, attempts = _attempt_loop(
        query, what="list releases", budget=budget, sleeper=sleeper
    )
    records = list(records)
    eligible = eligible_releases(records)
    _narrate(
        f"{len(eligible)} of {len(records)} release(s) are published, non-draft, "
        "non-prerelease, and semver-tagged"
    )
    if not eligible:
        raise ResolutionError(
            E_NO_RELEASE,
            f"no versioned release is available: {repository} has no published, "
            "non-draft, non-prerelease release with a bare semver tag",
            attempts,
        )

    selected = select_release(eligible)
    if selected is None:  # pragma: no cover - eligible is non-empty here
        raise ResolutionError(
            E_NO_RELEASE, "no versioned release is available", attempts
        )
    tag = selected["tagName"]
    _narrate(f"resolved Template_Release {tag} ({source_ref(tag)})")

    if min_version is not None and not is_newer(tag, min_version):
        _narrate(
            f"{tag} is not greater than --min-version {min_version}; "
            f"reporting {E_ALREADY_CURRENT} and fetching nothing"
        )
        return already_current_payload(repository, tag, min_version, attempts)

    fetch = fetcher or (
        lambda timeout: fetch_source_tree(repository, tag, out_dir, timeout=timeout)
    )
    _narrate(f"fetching the source tree at {source_ref(tag)}")
    # `attempts` in the record counts the release-resolution query, which is what
    # R1 AC6 is worded against; a fetch that exhausts the budget raises with its
    # own count instead.
    extracted_to, _ = _attempt_loop(
        fetch,
        what=f"fetch the source tree at {source_ref(tag)}",
        budget=budget,
        sleeper=sleeper,
    )
    _narrate(f"extracted to {extracted_to}")

    return resolved_release(repository, selected, plugin_root, extracted_to, attempts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _semver_argument(value: str) -> str:
    if parse_semver(value) is None:
        raise argparse.ArgumentTypeError(
            f"expected a bare semver version with no 'v' prefix, got {value!r}"
        )
    return value


def _repo_argument(value: str) -> str:
    try:
        return _require_repo(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    default_repository, _ = contract_template()
    parser = argparse.ArgumentParser(
        prog="resolve_release.py",
        description=(
            "Resolve the latest published, non-draft, non-prerelease "
            "Template_Release by semver precedence and extract its source tree "
            "at that tag. JSON on stdout, narration on stderr."
        ),
    )
    parser.add_argument(
        "--repo",
        dest="repository",
        type=_repo_argument,
        default=default_repository,
        metavar="OWNER/NAME",
        help="template repository to resolve (default: %(default)s)",
    )
    parser.add_argument(
        "--min-version",
        dest="min_version",
        type=_semver_argument,
        default=None,
        metavar="SEMVER",
        help=(
            "update path: report E_ALREADY_CURRENT and fetch nothing unless the "
            "resolved maximum is greater than this bare semver version"
        ),
    )
    parser.add_argument(
        "--out",
        dest="out_dir",
        required=True,
        metavar="DIR",
        help="directory to extract the source tree into, as bootcamp-src-<tag>/",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Emit the record on stdout and return the process exit status."""
    args = build_parser().parse_args(argv)
    try:
        payload = resolve(
            out_dir=args.out_dir,
            repository=args.repository,
            min_version=args.min_version,
        )
    except ResolutionError as exc:
        print(json.dumps(exc.payload(), indent=2), flush=True)
        _narrate(f"{exc.code}: {exc.message}")
        return EXIT_FAILURE
    except ValueError as exc:
        _narrate(f"invalid input: {exc}")
        return EXIT_FAILURE

    print(json.dumps(payload, indent=2), flush=True)
    return EXIT_SUCCESS


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
