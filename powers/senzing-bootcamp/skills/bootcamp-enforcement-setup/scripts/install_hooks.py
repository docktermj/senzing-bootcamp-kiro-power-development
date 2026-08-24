#!/usr/bin/env python3
"""Hook_Installer — Tier 2 of the three-tier hook parity strategy.

Reads the Kiro hook definitions the Bootcamp_Power ships as assets, resolves the
two placeholders they carry into quoted absolute paths, and — **only with explicit
Bootcamper consent** — writes them into the Workspace_Hooks_Directory
(``.kiro/hooks/`` in the Bootcamper's workspace).

    install_hooks.py plan                        # disclose, write nothing
    install_hooks.py install --consent granted   # disclose, then write
    install_hooks.py install --consent declined  # write nothing, state the loss
    install_hooks.py status                      # compare installed vs shipped
    install_hooks.py remove  --consent granted   # delete exactly what it wrote

JSON goes to stdout, human narration to stderr — the same split the transform
engine uses. Both channels carry the full path of every file, so a caller reading
either one sees the disclosure.

Why this script lives in the Power and runs as Python
-----------------------------------------------------
The interpreter that will run the hooks is the interpreter that resolves them.
``sys.executable`` is read from *this* process, so the path written into every
Hook_Command_String is by construction an interpreter that exists and can run
the ported scripts — no probing, no fallback chain, no PATH lookup *(R16 AC3)*.
That matters most on Windows, where ``python3`` is frequently absent from PATH
and, where it does resolve, may hit a Microsoft Store App Execution Alias stub
that opens the Store instead of running the script *(R16 AC2)*. Because no
generated command ever names a bare ``python3``, ``python``, or ``py``, that stub
is unreachable.

This is how Template_Invariant ``INV-052`` is **honored rather than discounted**:
its exec-form wording (``command`` + ``args``) cannot be reproduced under Kiro's
single-command-string hook schema, but its stated guarantee — hook execution has
no shell dependency on Linux, macOS, or Windows — survives intact, because both
the interpreter path and the script path are absolute and quoted before the
string is ever written *(R10 AC5, R16 AC4, AC5)*.

Quoting
-------
Every emitted token is wrapped in double quotes, unconditionally, so a path
containing a space is passed as a single argument *(R16 AC4)*. A run of
backslashes is doubled only where it precedes a quote or the closing quote —
the ``CommandLineToArgvW`` rule, which leaves ``C:\\Users\\Bob Smith\\python.exe``
byte-intact on Windows while still round-tripping through POSIX quote removal.
`tokenize_command` is the documented inverse: for every path shape, the emitted
string tokenizes back to exactly ``[interpreter, script]``.

One honest limit: a *POSIX* path containing a literal backslash cannot be spelled
unambiguously in a single string that must also be Windows-correct, because POSIX
double quotes treat ``\\`` as an escape and Windows does not. The Windows reading
is chosen, since a backslash in a path is the Windows norm and a POSIX rarity.

Where ``<ABSOLUTE_SCRIPTS_DIR>`` points, and the A4 fallback
------------------------------------------------------------
Assumption **A4** is that a Power's ``skills/*/scripts/`` files are materialized
on disk at a stable absolute path after install. While it holds, the scripts
directory placeholder resolves to the Power's own ported script set and the only
thing written into the workspace is hook JSON. If it does not hold, a hook naming
that path does not warn — it silently never fires — so this installer also
implements the design's fallback: copy the ported script set into the
Workspace_Hooks_Directory, alongside the hook definitions, and resolve
``<ABSOLUTE_SCRIPTS_DIR>`` to that copy.

Which behavior applies is **not decided here**. It is read from the
``scriptsDirectoryStrategy`` field of ``hook-parity-coverage.json``, which the
Transformation_Contract's ``scripts-dir-strategy`` substitution set fills as the
map is materialized — the same single-point-of-change arrangement that puts the
``PreToolUse`` matcher regex in one contract value. So flipping the fallback on
after the Test_Checklist step 10 observation is a one-line contract edit plus a
rebuild, with no edit to this file and no edit to a hook asset *(R3 AC4)*. This
module owns the vocabulary (`SCRIPTS_DIR_STRATEGIES`) and the copy directory name
(`WORKSPACE_SCRIPTS_DIRECTORY_NAME`); the contract owns the choice.

The fallback changes nothing else about the installer's contract. Every copied
path is disclosed before a byte is written *(R7 AC7)*, the copy is byte-compared
and so idempotent *(R7 AC8)*, it lands under a ``senzing-bootcamp-`` prefixed
directory inside ``.kiro/hooks/`` *(R7 AC9)*, removal deletes exactly it and
nothing else *(R7 AC10)*, and the command strings stay absolute, quoted, and
shell-free *(R16 AC3-AC5)*.

Idempotence and repair
----------------------
Content is a pure function of (shipped definition, resolved interpreter, resolved
scripts directory), so a second run leaves ``.kiro/hooks/`` byte-identical to the
first run's result and produces no duplicate hook entry *(R7 AC8)*. A file that
already matches is reported ``unchanged`` and not rewritten. Re-running
re-resolves **both** paths from scratch, which is the documented repair after a
Power upgrade, a Python upgrade, or a removed virtualenv.

Ownership boundary
------------------
Every filename written carries the ``senzing-bootcamp-`` prefix *(R7 AC9)*, and
removal deletes exactly the prefixed files, leaving every other workspace hook
file untouched *(R7 AC10)*. The coverage map ``hook-parity-coverage.json`` sits
in the same asset directory and is deliberately *not* prefixed, so the shipped
``hookDefinitionGlob`` never installs it as a hook.

Requirements: 7.6, 7.7, 7.8, 7.9, 7.10, 7.11, 10.5, 16.2, 16.3, 16.4, 16.5.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    # Error codes.
    "E_CONSENT_REQUIRED",
    "E_HOOK_ASSETS_MISSING",
    "E_HOOK_DEFINITION_INVALID",
    "E_INTERPRETER_UNRESOLVED",
    "E_SCRIPTS_DIR_MISSING",
    "E_SCRIPTS_DIR_STRATEGY_INVALID",
    "E_SCRIPT_MISSING",
    "E_SHELL_CONSTRUCT",
    "E_UNPREFIXED_FILENAME",
    "E_UNRESOLVED_PLACEHOLDER",
    "E_WRITE_FAILED",
    "InstallerError",
    # Contract constants.
    "ADVISORY_WITHOUT_TIER2",
    "COVERAGE_MAP_FILENAME",
    "DEFAULT_HOOK_DEFINITION_GLOB",
    "HOOK_FILENAME_PREFIX",
    "HOOK_SCHEMA_VERSION",
    "PLACEHOLDER_INTERPRETER",
    "PLACEHOLDER_SCRIPTS_DIR",
    "PLACEHOLDER_SCRIPTS_DIR_STRATEGY",
    "SCRIPTS_DIR_STRATEGIES",
    "SCRIPTS_DIR_STRATEGY_FIELD",
    "SCRIPTS_DIR_STRATEGY_IN_POWER",
    "SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY",
    "SCRIPTS_RELATIVE_PATH",
    "SHELL_CONSTRUCTS",
    "TIER1_INSTRUCTION_FILES",
    "WORKSPACE_HOOKS_RELATIVE_PATH",
    "WORKSPACE_SCRIPTS_DIRECTORY_NAME",
    # Command-string construction and inspection.
    "quote_argument",
    "tokenize_command",
    "unquoted_remainder",
    "find_shell_constructs",
    "build_command",
    "resolve_command",
    # Path resolution.
    "discover_power_root",
    "resolve_hook_assets_directory",
    "resolve_interpreter",
    "resolve_scripts_directory",
    "resolve_workspace_hooks_directory",
    "resolve_workspace_scripts_directory",
    # Planning and application.
    "PlannedWrite",
    "PlannedCopy",
    "PlannedRemoval",
    "InstallPlan",
    "build_install_plan",
    "build_removal_plan",
    "apply_plan",
    "disclosure_text",
    "decline_text",
    "load_hook_definition_glob",
    "load_scripts_directory_strategy",
    "discover_hook_definitions",
    "discover_portable_scripts",
    "main",
]


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

#: The shipped hook asset directory is absent or holds no hook definition.
E_HOOK_ASSETS_MISSING = "E_HOOK_ASSETS_MISSING"
#: The ported script directory is absent, so a written hook could never fire.
E_SCRIPTS_DIR_MISSING = "E_SCRIPTS_DIR_MISSING"
#: A shipped definition names a script the ported set does not contain.
E_SCRIPT_MISSING = "E_SCRIPT_MISSING"
#: A shipped definition is not the ``{"version":"v1","hooks":[...]}`` shape.
E_HOOK_DEFINITION_INVALID = "E_HOOK_DEFINITION_INVALID"
#: The coverage map selects a scripts-directory strategy this installer has no
#: implementation for, so where ``<ABSOLUTE_SCRIPTS_DIR>`` should point is
#: undefined. Fail closed rather than guess: guessing wrong writes hooks that
#: never fire.
E_SCRIPTS_DIR_STRATEGY_INVALID = "E_SCRIPTS_DIR_STRATEGY_INVALID"
#: ``sys.executable`` yielded nothing usable as an absolute interpreter path.
E_INTERPRETER_UNRESOLVED = "E_INTERPRETER_UNRESOLVED"
#: A placeholder survived into a command string that was about to be written.
E_UNRESOLVED_PLACEHOLDER = "E_UNRESOLVED_PLACEHOLDER"
#: A generated command string carries a shell construct outside a quoted span.
E_SHELL_CONSTRUCT = "E_SHELL_CONSTRUCT"
#: A file about to be written lacks the ``senzing-bootcamp-`` prefix.
E_UNPREFIXED_FILENAME = "E_UNPREFIXED_FILENAME"
#: Consent was neither granted nor declined where a write was requested.
E_CONSENT_REQUIRED = "E_CONSENT_REQUIRED"
#: The Workspace_Hooks_Directory cannot be created or written.
E_WRITE_FAILED = "E_WRITE_FAILED"


class InstallerError(Exception):
    """A halting installer fault, carrying a catalog code and its details."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_json(self) -> dict[str, Any]:
        return {"status": "error", "error": self.code, "message": self.message, **self.details}


# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

#: Every file this installer writes starts with this (R7 AC9). It is also the
#: ownership boundary removal uses (R7 AC10).
HOOK_FILENAME_PREFIX = "senzing-bootcamp-"

#: Fallback for the glob the coverage map declares. Reading it from the map
#: single-sources the pattern; this constant is the value the map is expected to
#: carry, used only when the map is absent.
DEFAULT_HOOK_DEFINITION_GLOB = "senzing-bootcamp-*.json"

#: Sits beside the definitions and is deliberately unprefixed, so the glob above
#: cannot pick it up and install a coverage map as a hook.
COVERAGE_MAP_FILENAME = "hook-parity-coverage.json"

#: The two placeholders a shipped definition carries. Nothing else is resolved.
PLACEHOLDER_INTERPRETER = "<ABSOLUTE_PYTHON>"
PLACEHOLDER_SCRIPTS_DIR = "<ABSOLUTE_SCRIPTS_DIR>"

#: The coverage-map field carrying the A4 strategy, and the placeholder the
#: contract's ``scripts-dir-strategy`` set fills in as the map is materialized.
#: An unresolved placeholder means this installer is being read straight out of
#: the authoring tree rather than out of a built Power, so the default applies.
SCRIPTS_DIR_STRATEGY_FIELD = "scriptsDirectoryStrategy"
PLACEHOLDER_SCRIPTS_DIR_STRATEGY = "<SCRIPTS_DIR_STRATEGY>"

#: ``<ABSOLUTE_SCRIPTS_DIR>`` resolves to the Power's own ported script set.
#: Correct while assumption A4 holds.
SCRIPTS_DIR_STRATEGY_IN_POWER = "in-power"
#: The A4 fallback: the ported script set is copied into the
#: Workspace_Hooks_Directory and ``<ABSOLUTE_SCRIPTS_DIR>`` resolves to that copy,
#: so a hook's script path does not depend on the Power's install layout.
SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY = "workspace-copy"

#: The vocabulary. This module owns it; the contract picks from it.
SCRIPTS_DIR_STRATEGIES = (
    SCRIPTS_DIR_STRATEGY_IN_POWER,
    SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY,
)

#: Applied when the map carries no strategy at all, or still carries the
#: unresolved placeholder. Deliberately the non-copying one: writing files into a
#: workspace is the consequential choice, so it is never the one made by default.
DEFAULT_SCRIPTS_DIR_STRATEGY = SCRIPTS_DIR_STRATEGY_IN_POWER

#: Where the fallback puts its copy, relative to the Workspace_Hooks_Directory —
#: literally alongside the hook JSON. Prefixed, so the whole copy sits inside this
#: Power's ownership boundary and removal deletes exactly it (R7 AC9, AC10).
WORKSPACE_SCRIPTS_DIRECTORY_NAME = HOOK_FILENAME_PREFIX + "scripts"

#: Never copied: bytecode caches are byproducts of *running* a script, they carry
#: the interpreter's version in their name, and they are regenerated on demand.
_SCRIPT_COPY_SKIPPED_DIRS = frozenset({"__pycache__"})
_SCRIPT_COPY_SKIPPED_SUFFIXES = (".pyc", ".pyo")

#: Kiro hook file schema version.
HOOK_SCHEMA_VERSION = "v1"

#: Power-root-relative locations, as POSIX strings.
HOOK_ASSETS_RELATIVE_PATH = "skills/bootcamp-onboarding/assets/kiro-hooks"
SCRIPTS_RELATIVE_PATH = "skills/bootcamp-onboarding/scripts"

#: Workspace-relative location of the Workspace_Hooks_Directory.
WORKSPACE_HOOKS_RELATIVE_PATH = ".kiro/hooks"

#: Longest-first, so ``&&`` is reported as itself rather than as two ``&``.
SHELL_CONSTRUCTS = (
    "&&",
    "||",
    ">>",
    "<<",
    "$(",
    "${",
    ";",
    "|",
    ">",
    "<",
    "&",
    "`",
    "\n",
    "\r",
)

#: What a decline costs, stated plainly rather than left implied (R7 AC11).
#: Each entry is (protection, what it becomes, the Tier 1 rule that carries it).
ADVISORY_WITHOUT_TIER2 = (
    (
        "write-location gate",
        "advisory — nothing mechanically blocks a write that lands outside the "
        "bootcamper's project (INV-200)",
        "SENZING-BOOTCAMP-TIER1:write-location",
    ),
    (
        "secret gate",
        "advisory — nothing mechanically blocks a write that carries a credential, "
        "key, token, or password (INV-109)",
        "SENZING-BOOTCAMP-TIER1:secrets",
    ),
)

#: Power-root-relative Tier 1 instruction files, matching the coverage map's
#: ``tier1InstructionFiles`` exactly. Named on both the consent and the decline
#: path, because Tier 1 delivery depends on these files being read (R7 AC4, AC11).
TIER1_INSTRUCTION_FILES = (
    "skills/bootcamp-onboarding/assets/kiro-hooks/tier1-instructions/senzing-bootcamp-tier1-ground-rules.md",
    "skills/bootcamp-onboarding/assets/kiro-hooks/tier1-instructions/senzing-bootcamp-tier1-session-lifecycle.md",
    "skills/bootcamp-onboarding/assets/kiro-hooks/tier1-instructions/senzing-bootcamp-tier1-recap-folding.md",
)

CONSENT_GRANTED = "granted"
CONSENT_DECLINED = "declined"


# ---------------------------------------------------------------------------
# Command-string construction
# ---------------------------------------------------------------------------


def quote_argument(value: str) -> str:
    """Wrap one argument in double quotes, unconditionally (R16 AC4).

    Unconditionally, not "when it contains a space": a path that needs quoting
    and a path that does not are then spelled the same way, so the shipped
    assertion "both placeholders quoted" stays true of the resolved output and a
    reader cannot mistake an unquoted token for a deliberate shell construct.

    Backslash handling follows ``CommandLineToArgvW``: a run of backslashes is
    doubled only where it precedes a quote or the closing quote, and is left
    alone everywhere else. That keeps a Windows path byte-intact — ``C:\\Users``
    stays ``C:\\Users``, never ``C:\\\\Users`` — while still terminating the
    quoted span correctly for a path that ends in a separator.
    """
    out: list[str] = ['"']
    backslashes = 0
    for char in value:
        if char == "\\":
            backslashes += 1
            continue
        if char == '"':
            # Double the run, then escape the quote itself.
            out.append("\\" * (backslashes * 2 + 1))
            out.append('"')
        else:
            out.append("\\" * backslashes)
            out.append(char)
        backslashes = 0
    # A trailing run would otherwise escape the closing quote.
    out.append("\\" * (backslashes * 2))
    out.append('"')
    return "".join(out)


def tokenize_command(command: str) -> tuple[str, ...]:
    """Recover the argument vector from a command string.

    The documented inverse of `quote_argument`: for every path shape — POSIX,
    drive-lettered, UNC, space-bearing, quote-bearing, or carrying a character a
    shell would read as an operator — ``tokenize_command(build_command(...))``
    returns exactly the vector that went in.

    Also the parser used to read a *shipped* command string apart, so the
    placeholders are substituted per token rather than by string surgery on a
    quoted blob.
    """
    tokens: list[str] = []
    current: list[str] = []
    in_quotes = False
    started = False
    backslashes = 0

    for char in command:
        if char == "\\":
            backslashes += 1
            started = True
            continue
        if char == '"':
            current.append("\\" * (backslashes // 2))
            if backslashes % 2:
                current.append('"')
            else:
                in_quotes = not in_quotes
            backslashes = 0
            started = True
            continue
        current.append("\\" * backslashes)
        backslashes = 0
        if char in " \t" and not in_quotes:
            if started:
                tokens.append("".join(current))
                current = []
                started = False
            continue
        current.append(char)
        started = True

    current.append("\\" * backslashes)
    if started:
        tokens.append("".join(current))
    return tuple(tokens)


def unquoted_remainder(command: str) -> str:
    """Everything in `command` that sits outside a double-quoted span.

    A shell construct only *acts* when it is unquoted, so this is the string a
    shell-construct scan must look at. For output this installer generates the
    remainder is nothing but the single spaces between tokens.
    """
    out: list[str] = []
    in_quotes = False
    backslashes = 0
    for char in command:
        if char == "\\":
            backslashes += 1
            continue
        if char == '"':
            if backslashes % 2 == 0:
                in_quotes = not in_quotes
            backslashes = 0
            continue
        if not in_quotes:
            out.append("\\" * backslashes)
            out.append(char)
        backslashes = 0
    if not in_quotes:
        out.append("\\" * backslashes)
    return "".join(out)


def find_shell_constructs(command: str) -> tuple[str, ...]:
    """Shell constructs appearing unquoted in `command`, longest match first.

    Empty for every string this installer emits: each token is quoted, so a
    directory named ``a&b`` or ``a;b`` is data, never an operator (R16 AC5).
    """
    remainder = unquoted_remainder(command)
    found: list[str] = []
    index = 0
    while index < len(remainder):
        for construct in SHELL_CONSTRUCTS:
            if remainder.startswith(construct, index):
                if construct not in found:
                    found.append(construct)
                index += len(construct)
                break
        else:
            index += 1
    return tuple(found)


def build_command(interpreter: str, arguments: Sequence[str]) -> str:
    """An interpreter path followed by script arguments, and nothing else.

    Constructed by quoting a vector rather than by templating a string, so no
    unquoted token and no shell construct can appear by accident (R16 AC5).
    """
    return " ".join(quote_argument(token) for token in (interpreter, *arguments))


def resolve_command(
    shipped_command: str,
    *,
    interpreter: str,
    scripts_directory: str | os.PathLike[str],
) -> tuple[str, tuple[str, ...]]:
    """Resolve one shipped command string's two placeholders.

    Returns the resolved command string and the scripts-directory-relative
    script paths it names, so the caller can confirm each one exists before any
    hook pointing at it is written.

    The shipped string is tokenized first and re-quoted afterwards. Substituting
    inside the quoted blob would work by luck; substituting per token means the
    emitted string is well-formed by construction whatever the resolved paths
    contain.
    """
    tokens = tokenize_command(shipped_command)
    if not tokens:
        raise InstallerError(
            E_HOOK_DEFINITION_INVALID,
            "shipped hook command is empty; expected the interpreter placeholder "
            f"{PLACEHOLDER_INTERPRETER} followed by a script path",
            command=shipped_command,
        )
    if tokens[0] != PLACEHOLDER_INTERPRETER:
        raise InstallerError(
            E_HOOK_DEFINITION_INVALID,
            "shipped hook command must name the interpreter as exactly "
            f"{PLACEHOLDER_INTERPRETER} in the first position, so no interpreter "
            f"name can reach the Workspace_Hooks_Directory; found {tokens[0]!r}",
            command=shipped_command,
            token=tokens[0],
        )

    scripts_root = Path(scripts_directory)
    arguments: list[str] = []
    scripts: list[str] = []
    for token in tokens[1:]:
        if PLACEHOLDER_INTERPRETER in token:
            raise InstallerError(
                E_HOOK_DEFINITION_INVALID,
                f"shipped hook command repeats {PLACEHOLDER_INTERPRETER} in an "
                "argument position",
                command=shipped_command,
                token=token,
            )
        prefix = PLACEHOLDER_SCRIPTS_DIR + "/"
        if token.startswith(prefix):
            relative = token[len(prefix) :]
            if not relative or relative.startswith("/") or ".." in relative.split("/"):
                raise InstallerError(
                    E_HOOK_DEFINITION_INVALID,
                    "shipped hook command names a script path that does not stay "
                    f"inside the ported script set: {token!r}",
                    command=shipped_command,
                    token=token,
                )
            scripts.append(relative)
            arguments.append(str(scripts_root.joinpath(*relative.split("/"))))
            continue
        if PLACEHOLDER_SCRIPTS_DIR in token:
            raise InstallerError(
                E_HOOK_DEFINITION_INVALID,
                f"shipped hook command uses {PLACEHOLDER_SCRIPTS_DIR} in a shape "
                f"this installer does not resolve: {token!r}. Expected "
                f'"{PLACEHOLDER_SCRIPTS_DIR}/<script>.py".',
                command=shipped_command,
                token=token,
            )
        arguments.append(token)

    command = build_command(interpreter, arguments)

    for placeholder in (PLACEHOLDER_INTERPRETER, PLACEHOLDER_SCRIPTS_DIR):
        if placeholder in command:
            raise InstallerError(
                E_UNRESOLVED_PLACEHOLDER,
                f"resolved hook command still contains {placeholder}",
                command=command,
                placeholder=placeholder,
            )
    constructs = find_shell_constructs(command)
    if constructs:
        raise InstallerError(
            E_SHELL_CONSTRUCT,
            "resolved hook command carries an unquoted shell construct "
            f"({', '.join(repr(item) for item in constructs)})",
            command=command,
            constructs=list(constructs),
        )
    return command, tuple(scripts)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_interpreter() -> str:
    """The absolute filesystem path of the interpreter running this installer.

    ``sys.executable`` is normalized with `os.path.abspath`, **not**
    `Path.resolve`: resolving symlinks would walk a virtualenv's ``python`` back
    to the system interpreter and silently write the wrong environment into every
    hook. Normalization is enough for R16 AC3 — the result is absolute — and it
    preserves the environment the Bootcamper is actually running in.
    """
    raw = sys.executable
    if not raw or not raw.strip():
        raise InstallerError(
            E_INTERPRETER_UNRESOLVED,
            "sys.executable is empty, so no absolute interpreter path can be "
            "resolved. Re-run this installer with a normal Python interpreter "
            "rather than an embedded or frozen one.",
        )
    interpreter = os.path.abspath(raw)
    if not os.path.isabs(interpreter):
        raise InstallerError(
            E_INTERPRETER_UNRESOLVED,
            f"sys.executable did not resolve to an absolute path: {raw!r}",
            interpreter=raw,
        )
    if not os.path.isfile(interpreter):
        raise InstallerError(
            E_INTERPRETER_UNRESOLVED,
            f"resolved interpreter path is not a file: {interpreter}. A hook "
            "naming it could never run.",
            interpreter=interpreter,
        )
    return interpreter


def discover_power_root() -> Path:
    """The Bootcamp_Power root, derived from this script's own location.

    This file sits at ``skills/bootcamp-enforcement-setup/scripts/`` inside the
    Power, so the root is three levels up. Derived rather than configured,
    because the whole point of Tier 2 is that the installer knows where the
    ported script set actually landed without relying on ``${PLUGIN_ROOT}``
    expanding inside a command string (assumption A2).
    """
    return Path(__file__).resolve().parents[3]


def resolve_hook_assets_directory(power_root: str | os.PathLike[str]) -> Path:
    directory = Path(power_root).joinpath(*HOOK_ASSETS_RELATIVE_PATH.split("/"))
    if not directory.is_dir():
        raise InstallerError(
            E_HOOK_ASSETS_MISSING,
            f"shipped hook definitions are not at {directory}. Pass "
            "--hook-assets to point at the directory holding them.",
            hookAssets=str(directory),
        )
    return directory


def resolve_scripts_directory(power_root: str | os.PathLike[str]) -> Path:
    """The absolute directory of the ported script set (R10 AC1).

    Absent means fail closed: a hook whose script path does not resolve does not
    warn, it silently never fires, which is worse than no hook at all.
    """
    directory = Path(power_root).joinpath(*SCRIPTS_RELATIVE_PATH.split("/"))
    if not directory.is_dir():
        raise InstallerError(
            E_SCRIPTS_DIR_MISSING,
            f"the ported script set is not at {directory}, so no hook could "
            "find its script. Pass --scripts-dir to point at the directory "
            "holding the ported scripts.",
            scriptsDir=str(directory),
        )
    return directory.resolve()


def resolve_workspace_hooks_directory(workspace: str | os.PathLike[str]) -> Path:
    """The Workspace_Hooks_Directory for `workspace`, absolute, not created."""
    root = Path(workspace).expanduser()
    root = root if root.is_absolute() else Path(os.path.abspath(root))
    return root.joinpath(*WORKSPACE_HOOKS_RELATIVE_PATH.split("/"))


def resolve_workspace_scripts_directory(hooks_directory: str | os.PathLike[str]) -> Path:
    """Where the A4 fallback copies the ported script set, absolute, not created.

    Inside the Workspace_Hooks_Directory rather than beside it, because "alongside
    the hook JSON" is the point: one prefixed directory, in the one directory the
    Bootcamper already consented to, so disclosure, idempotence, and removal all
    keep working unchanged (R7 AC7-AC10).
    """
    return Path(hooks_directory) / WORKSPACE_SCRIPTS_DIRECTORY_NAME


def discover_portable_scripts(scripts_directory: str | os.PathLike[str]) -> tuple[str, ...]:
    """Every file of the ported script set, as sorted relative POSIX paths.

    The whole set, not only the scripts the hooks name: they import each other by
    same-directory module name (``import recap_checkpoint``,
    ``import docker_lifecycle``) and load vendored assets by relative path, so a
    copy of five files would be a copy that cannot run. Bytecode caches are left
    behind — they are byproducts, and copying one would put an interpreter-specific
    file into the workspace.
    """
    root = Path(scripts_directory)
    found: list[str] = []
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        subdirectories[:] = sorted(
            name for name in subdirectories if name not in _SCRIPT_COPY_SKIPPED_DIRS
        )
        for name in sorted(filenames):
            if name.endswith(_SCRIPT_COPY_SKIPPED_SUFFIXES):
                continue
            absolute = Path(directory) / name
            if not absolute.is_file():
                continue
            found.append(absolute.relative_to(root).as_posix())
    return tuple(sorted(found))


# ---------------------------------------------------------------------------
# Shipped definitions
# ---------------------------------------------------------------------------


def _read_coverage_map(hook_assets: str | os.PathLike[str]) -> Mapping[str, Any] | None:
    """The coverage map beside the definitions, or `None` when it is absent.

    Absent is tolerated — the prefix, not the map, is this installer's ownership
    boundary — but unreadable is not: a map that exists and cannot be parsed means
    the policy it carries is unknown, and guessing at policy is how a hook that
    never fires gets installed.
    """
    coverage_map = Path(hook_assets) / COVERAGE_MAP_FILENAME
    if not coverage_map.is_file():
        return None
    try:
        document = json.loads(coverage_map.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise InstallerError(
            E_HOOK_DEFINITION_INVALID,
            f"cannot read the hook parity coverage map {coverage_map}: {error}",
            coverageMap=str(coverage_map),
        ) from error
    return document if isinstance(document, Mapping) else None


def load_scripts_directory_strategy(hook_assets: str | os.PathLike[str]) -> str:
    """How ``<ABSOLUTE_SCRIPTS_DIR>`` is resolved, read from the coverage map.

    The A4 decision, and it is **read, never made here**: the
    Transformation_Contract's ``scripts-dir-strategy`` set fills the map's
    ``scriptsDirectoryStrategy`` field as the map is materialized, so the value has
    exactly one home and flipping the fallback on is a one-line contract edit plus
    a rebuild (R3 AC4). This module contributes the vocabulary and the two
    implementations, not the choice.

    A map that is absent, that declares nothing, or that still carries the
    unresolved placeholder yields `DEFAULT_SCRIPTS_DIR_STRATEGY` — the
    non-copying strategy, because writing files into somebody's workspace is not a
    thing to do by default. A map declaring a strategy this installer cannot
    implement is `E_SCRIPTS_DIR_STRATEGY_INVALID`: the field exists, it says
    something, and honoring it as though it said something else would install hooks
    pointing somewhere nobody chose.
    """
    document = _read_coverage_map(hook_assets)
    declared = document.get(SCRIPTS_DIR_STRATEGY_FIELD) if document is not None else None
    if not isinstance(declared, str) or not declared.strip():
        return DEFAULT_SCRIPTS_DIR_STRATEGY
    strategy = declared.strip()
    if strategy == PLACEHOLDER_SCRIPTS_DIR_STRATEGY:
        return DEFAULT_SCRIPTS_DIR_STRATEGY
    if strategy not in SCRIPTS_DIR_STRATEGIES:
        raise InstallerError(
            E_SCRIPTS_DIR_STRATEGY_INVALID,
            f"the hook parity coverage map selects {SCRIPTS_DIR_STRATEGY_FIELD} "
            f"{strategy!r}, which this installer has no implementation for. "
            f"Implemented strategies are {', '.join(SCRIPTS_DIR_STRATEGIES)}; the "
            "value comes from the Transformation_Contract's scripts-dir-strategy "
            "substitution set, so correct it there and rebuild.",
            coverageMap=str(Path(hook_assets) / COVERAGE_MAP_FILENAME),
            strategy=strategy,
            implemented=list(SCRIPTS_DIR_STRATEGIES),
        )
    return strategy


def load_hook_definition_glob(hook_assets: str | os.PathLike[str]) -> str:
    """The glob that selects hook definitions, read from the coverage map.

    Single-sourced from ``hook-parity-coverage.json`` so the installer and the
    map cannot disagree about which files in the asset directory are hooks. The
    glob must carry the ``senzing-bootcamp-`` prefix, which is what keeps the
    unprefixed coverage map out of the Workspace_Hooks_Directory.
    """
    coverage_map = Path(hook_assets) / COVERAGE_MAP_FILENAME
    pattern = DEFAULT_HOOK_DEFINITION_GLOB
    document = _read_coverage_map(hook_assets)
    if document is not None:
        declared = document.get("hookDefinitionGlob")
        if isinstance(declared, str) and declared.strip():
            pattern = declared.strip()
    if not pattern.startswith(HOOK_FILENAME_PREFIX):
        raise InstallerError(
            E_UNPREFIXED_FILENAME,
            f"hookDefinitionGlob {pattern!r} does not start with "
            f"{HOOK_FILENAME_PREFIX!r}. Every file written into the "
            "Workspace_Hooks_Directory must be attributable to this Power, and a "
            "glob without the prefix would also sweep up the coverage map.",
            glob=pattern,
            coverageMap=str(coverage_map),
        )
    return pattern


def discover_hook_definitions(
    hook_assets: str | os.PathLike[str], pattern: str
) -> tuple[Path, ...]:
    """Shipped definition files matching `pattern`, sorted by filename."""
    directory = Path(hook_assets)
    found = tuple(
        sorted(
            (path for path in directory.glob(pattern) if path.is_file()),
            key=lambda path: path.name,
        )
    )
    if not found:
        raise InstallerError(
            E_HOOK_ASSETS_MISSING,
            f"no shipped hook definition matches {pattern!r} in {directory}",
            hookAssets=str(directory),
            glob=pattern,
        )
    return found


def _validate_definition(document: Any, source: Path) -> tuple[str, ...]:
    """Check one shipped definition's shape; return its hook names."""

    def fail(message: str, **details: Any) -> InstallerError:
        return InstallerError(
            E_HOOK_DEFINITION_INVALID,
            f"{source.name}: {message}",
            definition=str(source),
            **details,
        )

    if not isinstance(document, Mapping):
        raise fail("hook definition is not a JSON object")
    version = document.get("version")
    if version != HOOK_SCHEMA_VERSION:
        raise fail(
            f"hook definition declares version {version!r}; expected "
            f"{HOOK_SCHEMA_VERSION!r}",
            version=version,
        )
    hooks = document.get("hooks")
    if not isinstance(hooks, list) or not hooks:
        raise fail("hook definition carries no 'hooks' list")

    names: list[str] = []
    for index, hook in enumerate(hooks):
        if not isinstance(hook, Mapping):
            raise fail(f"hooks[{index}] is not a JSON object")
        name = hook.get("name")
        if not isinstance(name, str) or not name.strip():
            raise fail(f"hooks[{index}] has no 'name'")
        if not name.startswith(HOOK_FILENAME_PREFIX):
            raise fail(
                f"hook name {name!r} does not start with {HOOK_FILENAME_PREFIX!r}, "
                "so the installed entry would not be attributable to this Power",
                hookName=name,
            )
        trigger = hook.get("trigger")
        if not isinstance(trigger, str) or not trigger.strip():
            raise fail(f"hook {name!r} declares no 'trigger'")
        action = hook.get("action")
        if not isinstance(action, Mapping):
            raise fail(f"hook {name!r} declares no 'action' object")
        if action.get("type") != "command":
            raise fail(
                f"hook {name!r} action type is {action.get('type')!r}; this "
                "installer resolves command actions only",
                hookName=name,
            )
        if not isinstance(action.get("command"), str):
            raise fail(f"hook {name!r} action has no 'command' string", hookName=name)
        names.append(name)
    return tuple(names)


def _serialize(document: Mapping[str, Any]) -> str:
    """Deterministic bytes: key order preserved, LF, one trailing newline.

    Determinism is what makes idempotence observable — a second run recomputes
    byte-identical content and therefore writes nothing (R7 AC8).
    """
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedWrite:
    """One file the installer will write, with the bytes it will contain."""

    source: Path
    destination: Path
    content: str
    hook_names: tuple[str, ...]
    scripts: tuple[str, ...]
    commands: tuple[str, ...]

    @property
    def state(self) -> str:
        """``create``, ``update``, or ``unchanged`` against what is on disk."""
        if not self.destination.exists():
            return "create"
        try:
            existing = self.destination.read_text(encoding="utf-8")
        except OSError:
            return "update"
        return "unchanged" if existing == self.content else "update"

    def to_json(self) -> dict[str, Any]:
        return {
            "path": str(self.destination),
            "source": str(self.source),
            "state": self.state,
            "hooks": list(self.hook_names),
            "scripts": list(self.scripts),
            "commands": list(self.commands),
        }


@dataclass(frozen=True)
class PlannedCopy:
    """One ported script file the A4 fallback will copy into the workspace.

    Bytes, not text: the ported set carries a minified vendored bundle and image
    assets beside its ``.py`` files, and a copy that re-encoded any of them would
    be a corrupted dependency.
    """

    source: Path
    destination: Path
    relative: str

    @property
    def state(self) -> str:
        """``create``, ``update``, or ``unchanged`` against what is on disk."""
        if not self.destination.exists():
            return "create"
        try:
            return (
                "unchanged"
                if self.destination.read_bytes() == self.source.read_bytes()
                else "update"
            )
        except OSError:
            return "update"

    def to_json(self) -> dict[str, Any]:
        return {
            "path": str(self.destination),
            "source": str(self.source),
            "relative": self.relative,
            "state": self.state,
        }


@dataclass(frozen=True)
class PlannedRemoval:
    """One file the installer will delete, and why it owns it."""

    destination: Path
    reason: str

    def to_json(self) -> dict[str, Any]:
        return {"path": str(self.destination), "reason": self.reason}


@dataclass(frozen=True)
class InstallPlan:
    """Everything the installer would do, computed before anything is written.

    A plan is what disclosure presents: it names every full path *before* a
    single byte is written, which is R7 AC7 held structurally rather than by
    remembering to print first.
    """

    action: str
    workspace: Path
    hooks_directory: Path
    power_root: Path
    hook_assets: Path
    scripts_directory: Path | None
    interpreter: str | None
    hook_definition_glob: str
    #: The A4 decision this plan was built under, read from the coverage map.
    scripts_directory_strategy: str = DEFAULT_SCRIPTS_DIR_STRATEGY
    #: Where the ported script set actually lives in the Power. Equal to
    #: `scripts_directory` under `in-power`; the copy's source under
    #: `workspace-copy`, where `scripts_directory` is the copy.
    script_source_directory: Path | None = None
    writes: tuple[PlannedWrite, ...] = ()
    copies: tuple[PlannedCopy, ...] = ()
    removals: tuple[PlannedRemoval, ...] = ()
    preserved: tuple[Path, ...] = field(default=())

    @property
    def paths(self) -> tuple[Path, ...]:
        """Every path this plan touches: writes, then copies, then removals."""
        return (
            tuple(write.destination for write in self.writes)
            + tuple(copy.destination for copy in self.copies)
            + tuple(removal.destination for removal in self.removals)
        )

    @property
    def touches_nothing(self) -> bool:
        return not self.writes and not self.copies and not self.removals

    def to_json(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "workspace": str(self.workspace),
            "hooksDirectory": str(self.hooks_directory),
            "powerRoot": str(self.power_root),
            "hookAssets": str(self.hook_assets),
            "scriptsDirectory": (
                str(self.scripts_directory) if self.scripts_directory else None
            ),
            "scriptsDirectoryStrategy": self.scripts_directory_strategy,
            "scriptSourceDirectory": (
                str(self.script_source_directory) if self.script_source_directory else None
            ),
            "interpreter": self.interpreter,
            "hookDefinitionGlob": self.hook_definition_glob,
            "filenamePrefix": HOOK_FILENAME_PREFIX,
            "writes": [write.to_json() for write in self.writes],
            "copies": [copy.to_json() for copy in self.copies],
            "removals": [removal.to_json() for removal in self.removals],
            "preserved": [str(path) for path in self.preserved],
            "tier1InstructionFiles": list(TIER1_INSTRUCTION_FILES),
        }


def _preserved_files(hooks_directory: Path, owned: Iterable[Path]) -> tuple[Path, ...]:
    """Workspace hook files this plan will not touch, for the disclosure.

    Listing them is the other half of the ownership claim: the Bootcamper sees
    both what changes and what demonstrably does not (R7 AC10).
    """
    if not hooks_directory.is_dir():
        return ()
    owned_names = {path.name for path in owned}
    return tuple(
        sorted(
            (
                path
                for path in hooks_directory.iterdir()
                if path.is_file() and path.name not in owned_names
            ),
            key=lambda path: path.name,
        )
    )


def build_install_plan(
    *,
    workspace: str | os.PathLike[str] | None = None,
    power_root: str | os.PathLike[str] | None = None,
    hook_assets: str | os.PathLike[str] | None = None,
    scripts_directory: str | os.PathLike[str] | None = None,
    interpreter: str | None = None,
    scripts_directory_strategy: str | None = None,
    prune_stale: bool = True,
) -> InstallPlan:
    """Compute the full install plan without touching the filesystem.

    Both paths are re-resolved from scratch on every call, which is why
    re-running is the documented repair after a Power upgrade, a Python upgrade,
    or a removed virtualenv: nothing is remembered from the previous install.

    `scripts_directory_strategy` overrides what the coverage map declares. It
    exists so the Test_Checklist step 10 observation can exercise the A4 fallback
    without rebuilding the Power, and not as a second home for the decision: the
    shipped behavior comes from the contract, through the map.
    """
    root = Path(power_root) if power_root is not None else discover_power_root()
    root = root if root.is_absolute() else Path(os.path.abspath(root))
    assets = (
        Path(os.path.abspath(hook_assets))
        if hook_assets is not None
        else resolve_hook_assets_directory(root)
    )
    if not assets.is_dir():
        raise InstallerError(
            E_HOOK_ASSETS_MISSING,
            f"shipped hook definitions are not at {assets}",
            hookAssets=str(assets),
        )
    script_source = (
        Path(os.path.abspath(scripts_directory))
        if scripts_directory is not None
        else resolve_scripts_directory(root)
    )
    if not script_source.is_dir():
        raise InstallerError(
            E_SCRIPTS_DIR_MISSING,
            f"the ported script set is not at {script_source}, so no hook could "
            "find its script",
            scriptsDir=str(script_source),
        )
    resolved_interpreter = interpreter if interpreter is not None else resolve_interpreter()

    hooks_directory = resolve_workspace_hooks_directory(
        workspace if workspace is not None else Path.cwd()
    )
    pattern = load_hook_definition_glob(assets)

    strategy = (
        scripts_directory_strategy.strip()
        if scripts_directory_strategy is not None
        else load_scripts_directory_strategy(assets)
    )
    if strategy not in SCRIPTS_DIR_STRATEGIES:
        raise InstallerError(
            E_SCRIPTS_DIR_STRATEGY_INVALID,
            f"{SCRIPTS_DIR_STRATEGY_FIELD} {strategy!r} has no implementation in "
            f"this installer; implemented strategies are "
            f"{', '.join(SCRIPTS_DIR_STRATEGIES)}",
            strategy=strategy,
            implemented=list(SCRIPTS_DIR_STRATEGIES),
        )

    # The A4 fork, and the only thing it changes is which absolute directory the
    # command strings name. Everything downstream of it — quoting, tokenization,
    # the shell-construct scan, the filename prefix, disclosure, idempotence — is
    # identical either way, which is what keeps flipping the strategy a contract
    # edit rather than a change of behavior anywhere else.
    copies: list[PlannedCopy] = []
    if strategy == SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY:
        scripts = resolve_workspace_scripts_directory(hooks_directory)
        copies = [
            PlannedCopy(
                source=script_source.joinpath(*relative.split("/")),
                destination=scripts.joinpath(*relative.split("/")),
                relative=relative,
            )
            for relative in discover_portable_scripts(script_source)
        ]
    else:
        scripts = script_source

    writes: list[PlannedWrite] = []
    missing_scripts: list[str] = []
    seen_hook_names: dict[str, Path] = {}

    for source in discover_hook_definitions(assets, pattern):
        if not source.name.startswith(HOOK_FILENAME_PREFIX):
            # Unreachable through the validated glob; asserted anyway, because
            # this is the single place the prefix guarantee is enforceable.
            raise InstallerError(
                E_UNPREFIXED_FILENAME,
                f"{source.name} would be written without the "
                f"{HOOK_FILENAME_PREFIX!r} prefix",
                definition=str(source),
            )
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise InstallerError(
                E_HOOK_DEFINITION_INVALID,
                f"cannot read shipped hook definition {source}: {error}",
                definition=str(source),
            ) from error

        hook_names = _validate_definition(document, source)
        for name in hook_names:
            previous = seen_hook_names.get(name)
            if previous is not None:
                raise InstallerError(
                    E_HOOK_DEFINITION_INVALID,
                    f"hook name {name!r} is declared by both {previous.name} and "
                    f"{source.name}; installing both would create a duplicate "
                    "hook entry",
                    hookName=name,
                    definitions=[str(previous), str(source)],
                )
            seen_hook_names[name] = source

        commands: list[str] = []
        scripts_named: list[str] = []
        for hook in document["hooks"]:
            command, named = resolve_command(
                hook["action"]["command"],
                interpreter=resolved_interpreter,
                scripts_directory=scripts,
            )
            hook["action"]["command"] = command
            commands.append(command)
            scripts_named.extend(named)

        # Checked against the Power's ported set, not against `scripts`: under
        # the A4 fallback `scripts` is a copy this run has not made yet, and the
        # question is whether the script exists to be copied.
        for relative in scripts_named:
            if not script_source.joinpath(*relative.split("/")).is_file():
                missing_scripts.append(f"{source.name} -> {relative}")

        writes.append(
            PlannedWrite(
                source=source,
                destination=hooks_directory / source.name,
                content=_serialize(document),
                hook_names=hook_names,
                scripts=tuple(scripts_named),
                commands=tuple(commands),
            )
        )

    if missing_scripts:
        raise InstallerError(
            E_SCRIPT_MISSING,
            "shipped hook definitions name scripts that are absent from the "
            f"ported script set at {script_source}: {', '.join(missing_scripts)}. A "
            "hook pointing at a missing script never fires and never says why, "
            "so nothing is written.",
            scriptsDir=str(script_source),
            missing=missing_scripts,
        )

    planned_names = {write.destination.name for write in writes}
    planned_copies = {copy.destination for copy in copies}
    removals: list[PlannedRemoval] = []
    if prune_stale and hooks_directory.is_dir():
        for path in sorted(
            hooks_directory.glob(f"{HOOK_FILENAME_PREFIX}*"), key=lambda item: item.name
        ):
            if path.is_file() and path.name not in planned_names:
                removals.append(
                    PlannedRemoval(
                        destination=path,
                        reason=(
                            "carries this Power's prefix but is not in the shipped "
                            "definition set — a leftover from an earlier Power version"
                        ),
                    )
                )
        # A workspace script copy left behind by a run under the other strategy.
        # It carries the prefix, so it is this Power's to clean up, and leaving it
        # would leave a stale second copy of the ported scripts in the workspace.
        stale_copy_root = resolve_workspace_scripts_directory(hooks_directory)
        if stale_copy_root.is_dir():
            for path in sorted(stale_copy_root.rglob("*")):
                if path.is_file() and path not in planned_copies:
                    removals.append(
                        PlannedRemoval(
                            destination=path,
                            reason=(
                                "sits in this Power's workspace script copy but is "
                                "not part of the ported set this Power ships"
                                if strategy == SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY
                                else "a workspace script copy from a run under the "
                                f"{SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY} strategy; "
                                f"this Power now resolves scripts "
                                f"{SCRIPTS_DIR_STRATEGY_IN_POWER}"
                            ),
                        )
                    )

    return InstallPlan(
        action="install",
        workspace=Path(os.path.abspath(workspace)) if workspace is not None else Path.cwd(),
        hooks_directory=hooks_directory,
        power_root=root,
        hook_assets=assets,
        scripts_directory=scripts,
        interpreter=resolved_interpreter,
        hook_definition_glob=pattern,
        scripts_directory_strategy=strategy,
        script_source_directory=script_source,
        writes=tuple(writes),
        copies=tuple(copies),
        removals=tuple(removals),
        preserved=_preserved_files(
            hooks_directory,
            [write.destination for write in writes]
            + [removal.destination for removal in removals],
        ),
    )


def build_removal_plan(
    *,
    workspace: str | os.PathLike[str] | None = None,
    power_root: str | os.PathLike[str] | None = None,
    hook_assets: str | os.PathLike[str] | None = None,
) -> InstallPlan:
    """The documented removal step: exactly the prefixed files, nothing else.

    Selection is by the ``senzing-bootcamp-`` prefix rather than by the shipped
    definition list, so a file installed by an *earlier* Power version is also
    removed. Every other workspace hook file is left unchanged and is listed
    under ``preserved`` so the Bootcamper can see that (R7 AC10).
    """
    root = Path(power_root) if power_root is not None else discover_power_root()
    root = root if root.is_absolute() else Path(os.path.abspath(root))
    try:
        assets = (
            Path(os.path.abspath(hook_assets))
            if hook_assets is not None
            else resolve_hook_assets_directory(root)
        )
        pattern = load_hook_definition_glob(assets)
    except InstallerError:
        # Removal must work even from a half-present Power: the prefix is the
        # ownership boundary, and it does not depend on the assets being readable.
        assets = root.joinpath(*HOOK_ASSETS_RELATIVE_PATH.split("/"))
        pattern = DEFAULT_HOOK_DEFINITION_GLOB

    hooks_directory = resolve_workspace_hooks_directory(
        workspace if workspace is not None else Path.cwd()
    )
    removals: list[PlannedRemoval] = []
    if hooks_directory.is_dir():
        for path in sorted(
            hooks_directory.glob(f"{HOOK_FILENAME_PREFIX}*"), key=lambda item: item.name
        ):
            if path.is_file():
                removals.append(
                    PlannedRemoval(
                        destination=path,
                        reason=f"written by this Power (prefix {HOOK_FILENAME_PREFIX})",
                    )
                )
        # The A4 fallback's script copy, if one was installed. Enumerated by
        # walking the prefixed directory rather than by asking the Power what it
        # ships, for the same reason the definitions are: removal is defined by the
        # ownership boundary, so it still works after a Power upgrade or against a
        # Power that is no longer there (R7 AC10).
        copy_root = resolve_workspace_scripts_directory(hooks_directory)
        if copy_root.is_dir():
            for path in sorted(copy_root.rglob("*")):
                if path.is_file():
                    removals.append(
                        PlannedRemoval(
                            destination=path,
                            reason=(
                                "written by this Power into its workspace script "
                                f"copy ({WORKSPACE_SCRIPTS_DIRECTORY_NAME}/)"
                            ),
                        )
                    )

    return InstallPlan(
        action="remove",
        workspace=Path(os.path.abspath(workspace)) if workspace is not None else Path.cwd(),
        hooks_directory=hooks_directory,
        power_root=root,
        hook_assets=assets,
        scripts_directory=None,
        interpreter=None,
        hook_definition_glob=pattern,
        removals=tuple(removals),
        preserved=_preserved_files(
            hooks_directory, [removal.destination for removal in removals]
        ),
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def apply_plan(plan: InstallPlan) -> dict[str, Any]:
    """Carry out `plan`. Call only after consent has been granted.

    Writes are ``os.replace``-based: content lands in a sibling temporary file
    and is renamed into place, so a Kiro session reading ``.kiro/hooks/`` never
    observes a half-written hook definition.
    """
    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    removed: list[str] = []
    copied: list[str] = []

    if plan.writes or plan.copies:
        try:
            plan.hooks_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise InstallerError(
                E_WRITE_FAILED,
                f"cannot create the Workspace_Hooks_Directory "
                f"{plan.hooks_directory}: {error}",
                hooksDirectory=str(plan.hooks_directory),
            ) from error

    for write in plan.writes:
        state = write.state
        if state == "unchanged":
            unchanged.append(str(write.destination))
            continue
        temporary = write.destination.with_name(write.destination.name + ".tmp")
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(write.content)
            os.replace(temporary, write.destination)
        except OSError as error:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise InstallerError(
                E_WRITE_FAILED,
                f"cannot write {write.destination}: {error}",
                path=str(write.destination),
            ) from error
        (created if state == "create" else updated).append(str(write.destination))

    # The A4 fallback's script copy. Byte-for-byte and byte-compared: the ported
    # set carries a minified vendored bundle and image assets beside its `.py`
    # files, and comparing bytes is also what makes the copy idempotent (R7 AC8).
    for copy in plan.copies:
        if copy.state == "unchanged":
            unchanged.append(str(copy.destination))
            continue
        temporary = copy.destination.with_name(copy.destination.name + ".tmp")
        try:
            copy.destination.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(copy.source.read_bytes())
            os.replace(temporary, copy.destination)
        except OSError as error:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise InstallerError(
                E_WRITE_FAILED,
                f"cannot copy {copy.source} to {copy.destination}: {error}",
                path=str(copy.destination),
                source=str(copy.source),
            ) from error
        copied.append(str(copy.destination))

    for removal in plan.removals:
        try:
            removal.destination.unlink()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise InstallerError(
                E_WRITE_FAILED,
                f"cannot remove {removal.destination}: {error}",
                path=str(removal.destination),
            ) from error
        removed.append(str(removal.destination))

    _prune_empty_script_copy_directories(plan)

    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "copied": copied,
        "removed": removed,
        "preserved": [str(path) for path in plan.preserved],
    }


def _prune_empty_script_copy_directories(plan: InstallPlan) -> None:
    """Drop directories the workspace script copy no longer needs.

    Removing files leaves the tree they sat in behind, and an empty
    ``senzing-bootcamp-scripts/`` in the workspace after a removal is a file the
    Bootcamper did not consent to keeping. Only directories under this Power's own
    prefixed root are considered, and only while they are empty, so nothing
    outside the ownership boundary can be reached.
    """
    root = resolve_workspace_scripts_directory(plan.hooks_directory)
    if not root.is_dir():
        return
    candidates = sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in (*candidates, root):
        try:
            directory.rmdir()
        except OSError:
            # Not empty, or not removable. Either way, leave it and carry on:
            # a sibling further along may still be empty.
            continue


# ---------------------------------------------------------------------------
# Human-readable output
# ---------------------------------------------------------------------------


def disclosure_text(plan: InstallPlan) -> str:
    """Full-path disclosure, presented before any file is written (R7 AC7)."""
    lines: list[str] = []
    if plan.action == "install":
        lines.append(
            "Senzing bootcamp — Tier 2 enforcement hooks, proposed workspace changes"
        )
        lines.append("")
        lines.append(f"  workspace          {plan.workspace}")
        lines.append(f"  hooks directory    {plan.hooks_directory}")
        lines.append(f"  interpreter        {plan.interpreter}")
        lines.append(f"  ported scripts     {plan.scripts_directory}")
        lines.append(f"  scripts resolved   {plan.scripts_directory_strategy}")
        if plan.scripts_directory_strategy == SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY:
            lines.append(f"  copied from        {plan.script_source_directory}")
        lines.append("")
        if plan.writes:
            lines.append(f"Files to write ({len(plan.writes)}):")
            for write in plan.writes:
                lines.append(f"  [{write.state:>9}] {write.destination}")
                for name, command in zip(write.hook_names, write.commands):
                    lines.append(f"              hook {name}")
                    lines.append(f"              runs {command}")
        else:
            lines.append("Files to write: none.")

        # Disclosed the same way and to the same standard as the definitions:
        # every full path, before a byte is written (R7 AC7).
        if plan.copies:
            lines.append("")
            lines.append(
                f"Ported scripts to copy ({len(plan.copies)}), because this Power "
                f"resolves hook script paths {SCRIPTS_DIR_STRATEGY_WORKSPACE_COPY}:"
            )
            for copy in plan.copies:
                lines.append(f"  [{copy.state:>9}] {copy.destination}")
    else:
        lines.append("Senzing bootcamp — Tier 2 enforcement hook removal")
        lines.append("")
        lines.append(f"  workspace          {plan.workspace}")
        lines.append(f"  hooks directory    {plan.hooks_directory}")
        lines.append("")

    if plan.removals:
        lines.append("")
        lines.append(f"Files to delete ({len(plan.removals)}):")
        for removal in plan.removals:
            lines.append(f"  [   delete] {removal.destination}")
            lines.append(f"              {removal.reason}")
    elif plan.action == "remove":
        lines.append("Files to delete: none. Nothing from this Power is installed.")

    lines.append("")
    if plan.preserved:
        lines.append(
            f"Left unchanged ({len(plan.preserved)} other hook file(s) in that "
            "directory):"
        )
        for path in plan.preserved:
            lines.append(f"  [ untouched] {path}")
    else:
        lines.append("No other hook file exists in that directory.")
    lines.append("")
    lines.append(
        f"Only files named {HOOK_FILENAME_PREFIX}* are ever written or deleted, so "
        "every change above is attributable to this Power and reversible with "
        "`install_hooks.py remove --consent granted`."
    )
    return "\n".join(lines)


def decline_text() -> str:
    """What declining costs, stated plainly, plus where Tier 1 lives (R7 AC11)."""
    lines = [
        "No file was written into the Workspace_Hooks_Directory.",
        "",
        "The bootcamp is complete and usable without these hooks. What changes is "
        "enforcement, not content — these protections become advisory:",
        "",
    ]
    for protection, effect, marker in ADVISORY_WITHOUT_TIER2:
        lines.append(f"  - {protection}: {effect}")
        lines.append(f"    Tier 1 rule: {marker}")
    lines.extend(
        [
            "",
            "The closing-👉-question rule, recap folding, and session close-out are "
            "advisory whether or not hooks are installed, so declining costs nothing "
            "there.",
            "",
            "Follow these Tier 1 instruction files for the full rule set:",
        ]
    )
    for path in TIER1_INSTRUCTION_FILES:
        lines.append(f"  - {path}")
    lines.extend(
        [
            "",
            "Consent can be granted later at any point: run "
            "`install_hooks.py install --consent granted`.",
        ]
    )
    return "\n".join(lines)


def status_report(plan: InstallPlan) -> dict[str, Any]:
    """Shipped-versus-installed comparison, with no side effect."""
    entries = [
        {
            "path": str(write.destination),
            "installed": write.destination.exists(),
            "state": write.state,
        }
        for write in plan.writes
    ]
    copies = [
        {
            "path": str(copy.destination),
            "installed": copy.destination.exists(),
            "state": copy.state,
        }
        for copy in plan.copies
    ]
    installed = sum(1 for entry in entries if entry["state"] == "unchanged")
    current_copies = sum(1 for entry in copies if entry["state"] == "unchanged")
    return {
        "hooks": entries,
        "scriptCopies": copies,
        "scriptsDirectoryStrategy": plan.scripts_directory_strategy,
        "stale": [removal.to_json() for removal in plan.removals],
        "preserved": [str(path) for path in plan.preserved],
        "inSync": (
            installed == len(entries)
            and current_copies == len(copies)
            and not plan.removals
        ),
        "installedCount": installed,
        "shippedCount": len(entries),
        "scriptCopyCurrentCount": current_copies,
        "scriptCopyCount": len(copies),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _narrate(message: str, *, quiet: bool) -> None:
    if not quiet:
        print(message, file=sys.stderr)


def _emit(document: Mapping[str, Any]) -> None:
    json.dump(document, sys.stdout, indent=2, sort_keys=False)
    print(file=sys.stdout)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install_hooks.py",
        description=(
            "Install, inspect, or remove the Senzing bootcamp's Tier 2 Kiro hook "
            "definitions. Nothing is written without explicit consent. JSON to "
            "stdout, narration to stderr."
        ),
    )
    parser.add_argument("--quiet", action="store_true", help="suppress stderr narration")

    subparsers = parser.add_subparsers(dest="command")

    def add_common(target: argparse.ArgumentParser) -> None:
        # SUPPRESS, not False: absent on the subcommand must not overwrite a
        # --quiet given before the subcommand.
        target.add_argument(
            "--quiet",
            action="store_true",
            default=argparse.SUPPRESS,
            help="suppress stderr narration",
        )
        target.add_argument(
            "--workspace",
            default=None,
            help="the bootcamper's workspace root (default: current directory)",
        )
        target.add_argument(
            "--power-root",
            default=None,
            help="Bootcamp_Power root (default: derived from this script's location)",
        )
        target.add_argument(
            "--hook-assets",
            default=None,
            help=f"directory holding the shipped definitions (default: "
            f"<power-root>/{HOOK_ASSETS_RELATIVE_PATH})",
        )

    def add_resolution(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--scripts-dir",
            default=None,
            help=f"absolute directory of the ported script set (default: "
            f"<power-root>/{SCRIPTS_RELATIVE_PATH})",
        )
        target.add_argument(
            "--scripts-dir-strategy",
            choices=SCRIPTS_DIR_STRATEGIES,
            default=None,
            help=(
                "override how <ABSOLUTE_SCRIPTS_DIR> is resolved. Default: whatever "
                f"the shipped coverage map's {SCRIPTS_DIR_STRATEGY_FIELD} says, which "
                "the Transformation_Contract fills in. Use this only to observe the "
                "A4 fallback without rebuilding the Power"
            ),
        )
        target.add_argument(
            "--keep-stale",
            action="store_true",
            help=(
                f"leave {HOOK_FILENAME_PREFIX}* files that are no longer shipped in "
                "place instead of planning their removal"
            ),
        )

    plan_parser = subparsers.add_parser(
        "plan", help="present every path that would change, and write nothing"
    )
    add_common(plan_parser)
    add_resolution(plan_parser)

    install_parser = subparsers.add_parser(
        "install", help="write the hook definitions, with consent"
    )
    add_common(install_parser)
    add_resolution(install_parser)
    install_parser.add_argument(
        "--consent",
        choices=(CONSENT_GRANTED, CONSENT_DECLINED),
        default=None,
        help=(
            "the bootcamper's explicit answer. Omitted means disclosure only: the "
            "paths are presented and nothing is written."
        ),
    )

    status_parser = subparsers.add_parser(
        "status", help="compare what is installed against what is shipped"
    )
    add_common(status_parser)
    add_resolution(status_parser)

    remove_parser = subparsers.add_parser(
        "remove",
        aliases=("uninstall",),
        help=f"delete exactly the {HOOK_FILENAME_PREFIX}* files, with consent",
    )
    add_common(remove_parser)
    remove_parser.add_argument(
        "--consent",
        choices=(CONSENT_GRANTED, CONSENT_DECLINED),
        default=None,
        help="omitted means disclosure only: the paths are presented, nothing is deleted",
    )

    return parser


def _install_plan_from_args(args: argparse.Namespace) -> InstallPlan:
    return build_install_plan(
        workspace=args.workspace,
        power_root=args.power_root,
        hook_assets=args.hook_assets,
        scripts_directory=args.scripts_dir,
        scripts_directory_strategy=args.scripts_dir_strategy,
        prune_stale=not args.keep_stale,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    # Disclosure is the safe default, so a bare invocation plans rather than writes.
    if not arguments or arguments[0].startswith("-"):
        known = {"plan", "install", "status", "remove", "uninstall"}
        if not any(item in known for item in arguments):
            arguments = ["plan", *arguments]
    args = parser.parse_args(arguments)
    quiet = bool(getattr(args, "quiet", False))
    command = args.command or "plan"

    try:
        if command in ("remove", "uninstall"):
            plan = build_removal_plan(
                workspace=args.workspace,
                power_root=args.power_root,
                hook_assets=args.hook_assets,
            )
            _narrate(disclosure_text(plan), quiet=quiet)
            if args.consent is None:
                _narrate(
                    "\nNothing deleted. Re-run with `--consent granted` to delete "
                    "exactly the files listed above.",
                    quiet=quiet,
                )
                _emit({"status": "awaiting-consent", **plan.to_json()})
                return 0
            if args.consent == CONSENT_DECLINED:
                _narrate("\nNothing deleted. The hooks stay installed.", quiet=quiet)
                _emit({"status": "declined", **plan.to_json()})
                return 0
            result = apply_plan(plan)
            _narrate(
                f"\nRemoved {len(result['removed'])} file(s). "
                f"{len(result['preserved'])} other hook file(s) left unchanged.",
                quiet=quiet,
            )
            _emit({"status": "removed", **plan.to_json(), "result": result})
            return 0

        plan = _install_plan_from_args(args)

        if command == "status":
            report = status_report(plan)
            _narrate(
                "Tier 2 enforcement hooks: "
                f"{report['installedCount']} of {report['shippedCount']} installed and "
                f"current in {plan.hooks_directory}"
                + (
                    f"; {report['scriptCopyCurrentCount']} of "
                    f"{report['scriptCopyCount']} copied script file(s) current"
                    if report["scriptCopyCount"]
                    else ""
                )
                + (f"; {len(report['stale'])} stale file(s)" if report["stale"] else ""),
                quiet=quiet,
            )
            _emit({"status": "status", **plan.to_json(), "report": report})
            return 0

        _narrate(disclosure_text(plan), quiet=quiet)

        if command == "plan" or args.consent is None:
            _narrate(
                "\nNothing written. Ask the bootcamper, then re-run with "
                "`--consent granted` or `--consent declined`.",
                quiet=quiet,
            )
            _emit({"status": "awaiting-consent", **plan.to_json()})
            return 0

        if args.consent == CONSENT_DECLINED:
            _narrate("\n" + decline_text(), quiet=quiet)
            _emit(
                {
                    "status": "declined",
                    **plan.to_json(),
                    "writes": [],
                    "removals": [],
                    "advisoryWithoutTier2": [
                        {"protection": protection, "effect": effect, "tier1Marker": marker}
                        for protection, effect, marker in ADVISORY_WITHOUT_TIER2
                    ],
                }
            )
            return 0

        result = apply_plan(plan)
        _narrate(
            f"\nWrote {len(result['created'])} new, updated {len(result['updated'])}, "
            f"left {len(result['unchanged'])} already current, copied "
            f"{len(result['copied'])} ported script file(s), removed "
            f"{len(result['removed'])} stale. "
            f"{len(result['preserved'])} other hook file(s) left unchanged.",
            quiet=quiet,
        )
        _emit({"status": "installed", **plan.to_json(), "result": result})
        return 0

    except InstallerError as error:
        _narrate(f"install_hooks: {error.code}: {error.message}", quiet=quiet)
        _emit(error.to_json())
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
