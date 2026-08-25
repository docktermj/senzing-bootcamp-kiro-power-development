"""Integration tests — the real template release, the real Power, the live server.

Design Testing Strategy, layer 4. Everything here touches the network, the real
upstream repository, or a real subprocess, so iteration count buys nothing: each
test runs 1–3 concrete examples rather than generated input. The properties in
`test_properties.py` carry input coverage for the same logic; these tests
establish that the logic is wired to the real artifacts.

Every test in this file carries the `integration` marker through the module-level
`pytestmark`, so the project's default command — `pytest --no-header -q -m "not
integration"` — excludes the whole file and stays offline.

Run them deliberately:

    pytest --no-header -q -m integration

Sections below are ordered by the task that owns them:

1. Real release resolution (R1 AC1, AC3) ................... task 14.2
2. End-to-end build from the real release (R13 AC5) ........ task 14.2
3. Golden tree and manifest hashes (R3 AC5, R16 AC9) ....... task 14.2
4. Live Senzing MCP tool call (R6 AC4) ..................... task 14.2
5. Hook command with `python3` absent from PATH (R16 AC2) ... task 14.2
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import pytest

from conftest import REPO_ROOT
from resolve_release import (
    E_NO_RELEASE,
    E_RESOLVE_FAILED,
    RESOLUTION_BUDGET_SECONDS,
    contract_template,
    fetch_source_tree,
    parse_semver,
    source_ref,
)
from strategies import SENZING_MCP_URL, TEMPLATE_PLUGIN_ROOT
from transform import MANIFEST_FILENAME, SKILL_ENTRY_POINT

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Facts about the deliverable these tests exercise
# ---------------------------------------------------------------------------

#: The engine scripts, invoked as CLIs so the tests exercise what a Maintainer runs.
ENGINE = REPO_ROOT / "tools" / "bootcamp-transform"

#: The committed deliverable (task 14.1) and the golden tree of section 3.
COMMITTED_POWER = REPO_ROOT / "powers" / "senzing-bootcamp"

#: The upstream template. Read from the contract rather than restated, so the
#: contract stays the single source; the constant below is the assertion that the
#: contract still names the repository the requirements name (R1).
EXPECTED_TEMPLATE_REPOSITORY = "Senzing/senzing-bootcamp-claude-plugin"
TEMPLATE_REPOSITORY, CONTRACT_PLUGIN_ROOT = contract_template()

#: The 16-skill inventory: 12 ported bootcamp skills plus 4 `kiro-owned` ones
#: (3 command-derived + `bootcamp-enforcement-setup`).
SKILL_COUNT = 16
PORTED_SKILL_COUNT = 12
KIRO_OWNED_SKILL_COUNT = SKILL_COUNT - PORTED_SKILL_COUNT

#: The Hook_Installer, inside the Power rather than on `sys.path`.
INSTALLER_RELATIVE_PATH = Path(
    "skills/bootcamp-enforcement-setup/scripts/install_hooks.py"
)
HOOK_FILENAME_GLOB = "senzing-bootcamp-*.json"
WORKSPACE_HOOKS_RELATIVE_PATH = Path(".kiro/hooks")

#: A resolve + transform + validate run costs seconds; the ceiling only exists so
#: a hung network call fails the test instead of hanging the suite.
ENGINE_TIMEOUT_SECONDS = 300
HOOK_TIMEOUT_SECONDS = 60
MCP_TIMEOUT_SECONDS = 60

#: The MCP revision this client speaks, and the tool the server's own instructions
#: say to call first. `get_capabilities` takes no arguments and carries no data.
MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_TOOL = "get_capabilities"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tail(text: str, lines: int = 15) -> str:
    """The last few lines of a stderr narration, for a failure message."""
    kept = [line for line in text.splitlines() if line.strip()][-lines:]
    return "\n".join(kept)


@dataclass(frozen=True)
class _Run:
    """One engine invocation: its status, its stdout JSON, and its narration."""

    status: int
    payload: Any
    stderr: str

    @property
    def code(self) -> str | None:
        """The error code an engine failure reports on stdout, if any."""
        if isinstance(self.payload, Mapping):
            value = self.payload.get("code")
            return str(value) if value is not None else None
        return None


def _run(argv: list[str], *, cwd: Path, timeout: float, **kwargs: Any) -> _Run:
    """Run `argv` with no shell, decoding the JSON document on stdout."""
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    environment.update(kwargs.pop("env", {}))
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=environment,
        **kwargs,
    )
    payload: Any = None
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
    return _Run(completed.returncode, payload, completed.stderr)


def _engine(script: str, *arguments: str) -> _Run:
    """Invoke one engine CLI the way the maintainer skills invoke it."""
    return _run(
        [sys.executable, str(ENGINE / script), *arguments],
        cwd=REPO_ROOT,
        timeout=ENGINE_TIMEOUT_SECONDS,
    )


def _skip_unreachable(reason: str) -> None:
    """Skip, naming the test, because the network is absent rather than wrong.

    A connectivity failure is not evidence about the Power, so it is reported as
    "not exercised" rather than as a defect. Anything the server *answers* — a
    non-200 status, a JSON-RPC error, an unexpected document — fails instead.
    """
    pytest.skip(f"not exercised: {reason}")


def _recorded_template_release() -> str:
    """The Template_Release the committed Power records in its Build_Manifest."""
    manifest_path = COMMITTED_POWER / MANIFEST_FILENAME
    assert manifest_path.is_file(), (
        f"{manifest_path.relative_to(REPO_ROOT)} is missing; the committed Power "
        "is the baseline these tests build against (task 14.1)"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tag = str(manifest["templateRelease"])
    assert parse_semver(tag) is not None, (
        f"the committed Build_Manifest records templateRelease {tag!r}, which is "
        "not a bare semver tag"
    )
    return tag


def _tree_contents(root: Path) -> dict[str, bytes]:
    """Every file under `root`, keyed by its POSIX-spelled relative path."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _skill_owners(manifest: Mapping[str, Any]) -> dict[str, str]:
    """Each skill's owner, read off its `SKILL.md` entry in the Build_Manifest.

    The `SKILL.md` entry, not any file under the skill: `bootcamp-onboarding` is a
    ported skill that also carries `kiro-owned` Tier 2 hook assets, so counting
    owners across all files would put it in both buckets.
    """
    owners: dict[str, str] = {}
    for entry in manifest["files"]:
        path = str(entry["path"])
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "skills" and parts[2] == SKILL_ENTRY_POINT:
            owners[parts[1]] = str(entry["owner"])
    return owners


def _installer_module(path: Path) -> Any:
    """Import the Hook_Installer at `path` and hand back its namespace.

    Only its command-string tokenizer is used here — the installer itself runs as
    a subprocess. `path` is expected to be a *copy* of the Power, and bytecode
    writing is suppressed for the import, because a `__pycache__` directory beside
    the script is an extra file the Build_Manifest records no hash for.

    Registered in `sys.modules` before `exec_module` because the module stringizes
    its annotations and `dataclasses` resolves them through
    `sys.modules[cls.__module__]`.
    """
    assert path.is_file(), f"the Hook_Installer is missing from {path}"
    spec = importlib.util.spec_from_file_location(
        "senzing_bootcamp_install_hooks_integration", path
    )
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    written = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = written
    return module


def _hook_commands(hooks_directory: Path) -> list[tuple[Path, str, str]]:
    """Every `(definition, hook name, command)` in a Workspace_Hooks_Directory."""
    commands: list[tuple[Path, str, str]] = []
    for definition in sorted(hooks_directory.glob(HOOK_FILENAME_GLOB)):
        document = json.loads(definition.read_text(encoding="utf-8"))
        for hook in document["hooks"]:
            action = hook["action"]
            if action.get("type") != "command":
                continue
            commands.append((definition, str(hook["name"]), str(action["command"])))
    return commands


# ---------------------------------------------------------------------------
# JSON-RPC over the MCP streamable-http transport
# ---------------------------------------------------------------------------


def _decode_jsonrpc(raw: str) -> Mapping[str, Any]:
    """Decode one JSON-RPC response, whether sent as JSON or as an SSE stream.

    `streamable-http` lets the server answer either way for the same request, so
    both shapes are accepted rather than one being assumed.
    """
    body = raw.strip()
    assert body, "the Senzing MCP server returned an empty body"
    if body.startswith("{"):
        return json.loads(body)
    for line in body.splitlines():
        if line.startswith("data:"):
            candidate = json.loads(line[len("data:") :].strip())
            if isinstance(candidate, Mapping) and "id" in candidate:
                return candidate
    pytest.fail(f"no JSON-RPC response found in the MCP reply: {body[:400]!r}")


def _post_jsonrpc(
    document: Mapping[str, Any], *, session_id: str | None = None
) -> tuple[Mapping[str, Any] | None, Mapping[str, str]]:
    """POST one JSON-RPC document to the live Senzing MCP server.

    Returns `(response, headers)`; `response` is `None` for a notification the
    server acknowledges with no body. A transport failure skips — the network
    being down says nothing about the Power — while any answered-but-wrong reply
    is left to the caller to assert on.
    """
    request = urllib.request.Request(  # noqa: S310 - fixed https URL
        SENZING_MCP_URL,
        data=json.dumps(document).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            **({"Mcp-Session-Id": session_id} if session_id else {}),
        },
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - fixed https URL
            request, timeout=MCP_TIMEOUT_SECONDS
        ) as response:
            status = response.status
            headers = {key.lower(): value for key, value in response.headers.items()}
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:  # answered, and wrong
        pytest.fail(
            f"{SENZING_MCP_URL} answered {error.code} {error.reason} for "
            f"{document.get('method')!r}"
        )
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as error:
        _skip_unreachable(f"{SENZING_MCP_URL} is unreachable ({error})")

    assert status == 200, f"{SENZING_MCP_URL} answered HTTP {status}"
    if not raw.strip():
        return None, headers
    return _decode_jsonrpc(raw), headers


# ---------------------------------------------------------------------------
# Fixtures: the network is touched once per module, not once per test
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Build:
    """One end-to-end build: the tree it came from, and what the engine said."""

    tag: str
    source: Path
    staging: Path
    transform: Mapping[str, Any]
    report: Mapping[str, Any]
    validate_status: int

    @property
    def manifest(self) -> Mapping[str, Any]:
        return json.loads(
            (self.staging / MANIFEST_FILENAME).read_text(encoding="utf-8")
        )


@pytest.fixture(scope="module")
def scratch(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One scratch root for the module, so a fetched tree is fetched once."""
    return tmp_path_factory.mktemp("bootcamp-integration")


@pytest.fixture(scope="module")
def latest_release(scratch: Path) -> Mapping[str, Any]:
    """The `ResolvedRelease` record for the real latest upstream release."""
    result = _engine(
        "resolve_release.py",
        "--repo",
        TEMPLATE_REPOSITORY,
        "--out",
        str(scratch / "src"),
    )
    if result.status != 0:
        if result.code == E_RESOLVE_FAILED:
            _skip_unreachable(
                f"{TEMPLATE_REPOSITORY} could not be queried "
                f"({E_RESOLVE_FAILED}):\n{_tail(result.stderr)}"
            )
        assert result.code != E_NO_RELEASE, (
            f"{TEMPLATE_REPOSITORY} reports no published, non-draft, "
            f"non-prerelease, semver-tagged release:\n{_tail(result.stderr)}"
        )
        pytest.fail(
            f"resolve_release.py exited {result.status} "
            f"({result.code}):\n{_tail(result.stderr)}"
        )
    assert isinstance(result.payload, Mapping), "the resolver emitted no JSON record"
    return result.payload


@pytest.fixture(scope="module")
def recorded_release(
    scratch: Path, latest_release: Mapping[str, Any]
) -> tuple[str, Path]:
    """The release tree for the tag the committed Power records.

    Usually the latest release, in which case the already-fetched tree is reused.
    Between an upstream release and the Maintainer's update run they differ, and
    the golden tree must be rebuilt from the tag it was actually built from.
    """
    tag = _recorded_template_release()
    if str(latest_release["tag"]) == tag:
        return tag, Path(str(latest_release["extractedTo"]))
    try:
        tree = fetch_source_tree(
            TEMPLATE_REPOSITORY,
            tag,
            scratch / "src",
            timeout=RESOLUTION_BUDGET_SECONDS,
        )
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as error:
        _skip_unreachable(
            f"the source tree at {source_ref(tag)} could not be fetched ({error})"
        )
    return tag, tree


@pytest.fixture(scope="module")
def fresh_build(scratch: Path, recorded_release: tuple[str, Path]) -> _Build:
    """A full transform + validate run from the real release tree."""
    tag, source = recorded_release
    staging = scratch / f"build-{tag}"
    transform = _engine(
        "transform.py",
        "--source",
        str(source),
        "--tag",
        tag,
        "--staging",
        str(staging),
    )
    assert transform.status == 0, (
        f"transform.py exited {transform.status} ({transform.code}) building "
        f"{tag} from {source}:\n{_tail(transform.stderr)}"
    )
    assert isinstance(transform.payload, Mapping), "the transform emitted no JSON result"

    report_path = scratch / f"validation-{tag}.json"
    validate = _engine(
        "validate.py",
        "--staging",
        str(staging),
        "--tag",
        tag,
        "--report",
        str(report_path),
        "--source",
        str(source),
    )
    assert isinstance(validate.payload, Mapping), (
        f"validate.py emitted no ValidationReport:\n{_tail(validate.stderr)}"
    )
    return _Build(
        tag=tag,
        source=source,
        staging=staging,
        transform=transform.payload,
        report=validate.payload,
        validate_status=validate.status,
    )


def _failing_checks(report: Mapping[str, Any]) -> list[str]:
    """One line per non-passing check, for a failure message that says what broke."""
    lines: list[str] = []
    for check in report["checks"]:
        if check["result"] == "pass":
            continue
        target = f" [{check['target']}]" if check.get("target") else ""
        lines.append(f"{check['result']} {check['id']}{target}")
        lines.extend(
            f"    {finding['code']}: {finding['message']}"
            for finding in check.get("findings", ())
        )
    return lines


# ===========================================================================
# 1. Real release resolution — R1 AC1, AC3
# ===========================================================================


def test_the_real_latest_release_resolves_to_a_bare_semver_tag(
    latest_release: Mapping[str, Any],
) -> None:
    """The live resolution names a bare-semver tag ref, never a `v` prefix or `main`.

    The `v` prefix matters because the resolved tag is stamped into
    `plugin.json` character-for-character (R2 AC1): a `v0.5.1` tag would produce
    a version string the Agent Plugins schema rejects.
    """
    assert TEMPLATE_REPOSITORY == EXPECTED_TEMPLATE_REPOSITORY, (
        "contract.yaml's template.repository is the single source these tests "
        f"resolve from; it names {TEMPLATE_REPOSITORY!r}"
    )
    assert latest_release["repository"] == EXPECTED_TEMPLATE_REPOSITORY

    tag = str(latest_release["tag"])
    assert not tag.startswith(("v", "V")), (
        f"the resolved tag carries a v prefix: {tag!r}. Template_Release tags are "
        "bare semver"
    )
    assert parse_semver(tag) is not None, f"the resolved tag is not bare semver: {tag!r}"
    assert list(latest_release["semver"]) == list(parse_semver(tag))

    assert latest_release["isDraft"] is False
    assert latest_release["isPrerelease"] is False

    # R1 AC3: content comes from the tag, and `main` is not reachable from here.
    assert latest_release["sourceRef"] == f"refs/tags/{tag}"
    assert "main" not in str(latest_release["sourceRef"])

    tree = Path(str(latest_release["extractedTo"]))
    assert tree.is_dir(), f"the resolved tree is missing from {tree}"
    assert tree.name == f"bootcamp-src-{tag}"
    plugin_root = str(latest_release["pluginRoot"])
    assert plugin_root == TEMPLATE_PLUGIN_ROOT == CONTRACT_PLUGIN_ROOT
    assert (tree / plugin_root).is_dir(), (
        f"{plugin_root} is missing from the tree at {source_ref(tag)}; template "
        "sources are rooted at the plugin subdirectory, not the repository root"
    )


# ===========================================================================
# 2. End-to-end build from the real release — R13 AC5
# ===========================================================================


def test_the_end_to_end_build_produces_16_skills_and_passes_validation(
    fresh_build: _Build,
) -> None:
    """Resolve → transform → validate against the real release, with no fixtures.

    The build target is the Template_Release the committed Power records — `0.5.1`
    as of task 14.1 — read from the Build_Manifest rather than pinned here, so a
    later update run moves this test forward with the deliverable.
    """
    owners = _skill_owners(fresh_build.manifest)
    assert len(owners) == SKILL_COUNT, (
        f"the build produced {len(owners)} skills, expected {SKILL_COUNT} "
        f"({PORTED_SKILL_COUNT} ported + {KIRO_OWNED_SKILL_COUNT} kiro-owned): "
        f"{sorted(owners)}"
    )

    ported = sorted(name for name, owner in owners.items() if owner == "template")
    kiro_owned = sorted(name for name, owner in owners.items() if owner == "kiro")
    assert len(ported) == PORTED_SKILL_COUNT, (
        f"{len(ported)} skills are ported from the template, expected "
        f"{PORTED_SKILL_COUNT}: {ported}"
    )
    assert len(kiro_owned) == KIRO_OWNED_SKILL_COUNT, (
        f"{len(kiro_owned)} skills are kiro-owned, expected "
        f"{KIRO_OWNED_SKILL_COUNT}: {kiro_owned}"
    )

    # Every skill directory on disk is accounted for by the manifest.
    on_disk = sorted(
        path.name
        for path in (fresh_build.staging / "skills").iterdir()
        if (path / SKILL_ENTRY_POINT).is_file()
    )
    assert on_disk == sorted(owners), (
        "the skills on disk and the skills in the Build_Manifest disagree"
    )

    report = fresh_build.report
    assert report["status"] == "passed", (
        f"validation of the {fresh_build.tag} build is {report['status']!r}, not "
        "'passed':\n" + "\n".join(_failing_checks(report))
    )
    assert report["tagAllowed"] is True
    assert report["templateRelease"] == fresh_build.tag
    assert report["powerVersion"] == fresh_build.tag
    assert fresh_build.validate_status == 0, (
        "validate.py exited non-zero for a report it marked tagAllowed"
    )


# ===========================================================================
# 3. Golden tree and manifest hashes — R3 AC5, R16 AC9
# ===========================================================================


def test_the_committed_power_equals_a_fresh_build_of_its_recorded_release(
    fresh_build: _Build,
) -> None:
    """The standing regression check on determinism (Property 4) and on create/update
    equivalence (Property 3), against the real committed deliverable.

    A difference here means the committed tree and the engine have drifted apart:
    either the engine changed without a rebuild, or the tree was hand-edited.
    """
    committed = _tree_contents(COMMITTED_POWER)
    fresh = _tree_contents(fresh_build.staging)

    only_committed = sorted(set(committed) - set(fresh))
    only_fresh = sorted(set(fresh) - set(committed))
    assert not only_committed, (
        f"the committed Power carries {len(only_committed)} file(s) a fresh "
        f"{fresh_build.tag} build does not produce: {only_committed[:10]}. Files "
        "such as __pycache__ entries mean a ported script was run inside the "
        "committed tree; delete them and re-run"
    )
    assert not only_fresh, (
        f"a fresh {fresh_build.tag} build produces {len(only_fresh)} file(s) the "
        f"committed Power does not carry: {only_fresh[:10]}"
    )

    differing = sorted(path for path in committed if committed[path] != fresh[path])
    assert not differing, (
        f"{len(differing)} committed file(s) differ byte-for-byte from a fresh "
        f"{fresh_build.tag} build: {differing[:10]}"
    )


def test_the_committed_power_validates_against_its_own_build_manifest(
    scratch: Path, recorded_release: tuple[str, Path]
) -> None:
    """R16 AC9 against the real checkout: every hash still matches what was written.

    Run against `powers/senzing-bootcamp/` as checked out, so a line-ending
    rewrite or a stray file in the tree is caught here rather than at tag time.
    """
    tag, source = recorded_release
    report_path = scratch / "validation-committed.json"
    result = _engine(
        "validate.py",
        "--staging",
        str(COMMITTED_POWER),
        "--tag",
        tag,
        "--report",
        str(report_path),
        "--source",
        str(source),
    )
    assert isinstance(result.payload, Mapping), (
        f"validate.py emitted no ValidationReport:\n{_tail(result.stderr)}"
    )
    report = result.payload

    hash_checks = [
        check for check in report["checks"] if check["id"] == "manifest-hashes"
    ]
    assert hash_checks, "the validator recorded no Build_Manifest hash check"
    assert all(check["result"] == "pass" for check in hash_checks), (
        "the committed Power's content hashes disagree with its Build_Manifest:\n"
        + "\n".join(_failing_checks(report))
    )

    assert report["status"] == "passed", (
        f"the committed Power validates {report['status']!r}, not 'passed':\n"
        + "\n".join(_failing_checks(report))
    )
    assert report["tagAllowed"] is True
    assert result.status == 0


# ===========================================================================
# 4. Live Senzing MCP tool call — R6 AC4
# ===========================================================================


def test_a_live_senzing_mcp_tool_call_returns_a_successful_response() -> None:
    """The URL the Power declares answers a real initialize and a real tool call.

    Checklist step 5 covers this from inside an installed Power; this test covers
    the half that needs no Kiro session — that the declared endpoint is reachable
    and serves the tool the bootcamp calls.
    """
    initialize, headers = _post_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "senzing-bootcamp-power-integration-test",
                    "version": "0.0.0",
                },
            },
        }
    )
    assert isinstance(initialize, Mapping), "initialize returned no JSON-RPC response"
    assert "error" not in initialize, f"initialize failed: {initialize.get('error')}"
    result = initialize["result"]
    assert "tools" in result["capabilities"], (
        f"{SENZING_MCP_URL} advertises no tools capability: {result['capabilities']}"
    )

    # A stateful server hands back a session id and expects the notification; a
    # stateless one does neither. Both are valid streamable-http servers.
    session_id = headers.get("mcp-session-id")
    if session_id:
        _post_jsonrpc(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            session_id=session_id,
        )

    call, _ = _post_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": MCP_TOOL, "arguments": {}},
        },
        session_id=session_id,
    )
    assert isinstance(call, Mapping), f"{MCP_TOOL} returned no JSON-RPC response"
    assert "error" not in call, f"{MCP_TOOL} failed: {call.get('error')}"
    payload = call["result"]
    assert payload.get("isError") in (False, None), (
        f"{MCP_TOOL} reported a tool error: {payload}"
    )
    content: Iterable[Mapping[str, Any]] = payload["content"]
    texts = [str(block["text"]) for block in content if block.get("type") == "text"]
    assert texts and any(text.strip() for text in texts), (
        f"{MCP_TOOL} returned no text content: {payload}"
    )


# ===========================================================================
# 5. Hook command with `python3` absent from PATH — R16 AC2
# ===========================================================================


def test_a_generated_hook_command_runs_with_python3_absent_from_path(
    tmp_path: Path,
) -> None:
    """R16 AC2, end to end: install, empty the PATH, run what was written.

    The installer runs against a *copy* of the Power, not the committed tree:
    executing a ported script writes `__pycache__` beside it, and an extra file
    in the deliverable is a Build_Manifest hash mismatch (section 3).
    """
    power = tmp_path / "power"
    shutil.copytree(COMMITTED_POWER, power)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    install = _run(
        [
            sys.executable,
            str(power / INSTALLER_RELATIVE_PATH),
            "install",
            "--consent",
            "granted",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
        cwd=workspace,
        timeout=HOOK_TIMEOUT_SECONDS,
    )
    assert install.status == 0, (
        f"install_hooks.py exited {install.status} ({install.code}):"
        f"\n{_tail(install.stderr)}"
    )

    hooks_directory = workspace / WORKSPACE_HOOKS_RELATIVE_PATH
    commands = _hook_commands(hooks_directory)
    assert commands, f"the installer wrote no hook definition into {hooks_directory}"

    # A PATH with nothing on it: no `python3`, and no shell builtin either.
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    stripped_path = str(empty_path)
    for name in ("python3", "python", "py"):
        assert shutil.which(name, path=stripped_path) is None, (
            f"{name} is still resolvable on the stripped PATH, so this test would "
            "prove nothing"
        )

    tokenize = _installer_module(power / INSTALLER_RELATIVE_PATH).tokenize_command
    for definition, name, command in commands:
        argv = list(tokenize(command))
        assert len(argv) == 2, (
            f"{definition.name}:{name} does not tokenize to exactly "
            f"[interpreter, script]: {argv}"
        )
        interpreter, script = argv
        assert os.path.isabs(interpreter), (
            f"{definition.name}:{name} names a non-absolute interpreter "
            f"{interpreter!r}; it would not resolve without python3 on PATH"
        )
        assert Path(interpreter).is_file(), f"{interpreter} is not a file"
        assert Path(script).is_file(), f"{script} is not a file"

        # The hook scripts no-op with no `config/bootcamp_progress.json` present,
        # so a clean workspace exercises the invocation without side effects.
        completed = subprocess.run(  # noqa: S603 - tokenized argv, no shell
            argv,
            cwd=str(workspace),
            input="{}",
            capture_output=True,
            text=True,
            timeout=HOOK_TIMEOUT_SECONDS,
            env={
                **{
                    key: value
                    for key, value in os.environ.items()
                    if key not in {"PATH", "PYTHONPATH"}
                },
                "PATH": stripped_path,
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
        assert completed.returncode == 0, (
            f"{definition.name}:{name} exited {completed.returncode} with python3 "
            f"absent from PATH:\n{_tail(completed.stderr)}"
        )
