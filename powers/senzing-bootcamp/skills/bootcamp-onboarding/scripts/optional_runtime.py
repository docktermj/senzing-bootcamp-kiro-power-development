#!/usr/bin/env python3
"""Optional_Runtime guard — only the resolved Python interpreter is required.

Kiro-owned. No Template_Plugin source. The contract's `optional-runtime-guard`
rule materializes this single file *into the ported script directory*, beside
`docker_lifecycle.py` and `recap_checkpoint.py`, so any script in that directory
reaches it through the same-directory import that already joins them —
``import optional_runtime`` — on Linux, macOS, and Windows alike.

    optional_runtime.py            # report host capability, always exit 0
    optional_runtime.py --json     # the same report as JSON on stdout

The rule
--------
The bootcamp requires exactly one runtime: the Python interpreter that is running
this script. Every other runtime is **optional** — a container CLI for the SDK
modules, a browser for the truth-set visualization screenshots. When an optional
runtime is absent the behavior is always the same three steps: **say what is
unavailable, say what still works, and return success** *(R16 AC7)*. Reduced
capability is a normal state of this bootcamp, not an error state.

Why this is a wrapper and not a patch
-------------------------------------
The ported scripts of Template_Release 0.5.1 already degrade exactly that way,
and nothing here rewrites them:

* `docker_lifecycle.py` resolves the recorded runtime's CLI through
  `shutil.which` and returns None when it is absent, so `stop_started_containers`
  skips the entry, `_container_state` answers ``unknown``, and `resume_summary`
  reports "the `docker` CLI is not available here" and offers help. Every
  subprocess call is wrapped, so an erroring CLI is also a skip, never a raise.
* The two scripts that use it, `session-start.py` (the `SessionStart` hook) and
  `session-end.py` (inert in Kiro; runnable by hand), end with an unconditional
  ``sys.exit(0)``. A missing container runtime therefore cannot block a trigger or
  wedge a session.
* No hook script touches a browser at all. `senzing_viz_server.py` serves the
  visualization over HTTP for the Bootcamper to open; it never launches a
  browser. `capture_screenshots.py` — agent-invoked, never a hook — tries
  Playwright, Selenium, headless Chrome/Chromium/Edge, and wkhtmltoimage, and
  when it finds none it prints every location it searched and says to keep the
  HTML link instead.

So the guard is *declared*, not injected: no substitution set touches a ported
script body, which is what keeps the port byte-faithful and the inline `INV-NNN`
citations intact. This module supplies the shared helper a script can import when
it needs one — now or in a later Template_Release — and gives the agent and the
Bootcamper one command that reports host capability and cannot fail.

Exit status, and the one number that matters
--------------------------------------------
`main` returns 0 always. In Kiro, exit status **2** from a `PreToolUse`,
`UserPromptSubmit`, or `PreTaskExec` hook *blocks* the action. A missing optional
runtime must never be spelled that way: an absent container CLI would then block
every turn of a session rather than reducing one module's capability. Hence
`EXIT_REDUCED_CAPABILITY = 0`, and `EXIT_BLOCK` recorded here only to name the
value this module never returns.

Detection is deliberately conservative
--------------------------------------
`shutil.which` plus an import probe answers "is it on PATH here", which is not
the whole answer for a browser: `capture_screenshots.py` also searches the
Windows standard install locations and the registry, so it can succeed where this
probe reports nothing. The wording below says PATH, and points at the owning
script as the authority, so this report can never contradict the one the script
itself prints (**INV-122**: the reported reason must be the actual one).

Pure Python 3 standard library, no third-party dependency, no shell
(**INV-052**, **INV-001**, **INV-002**).

Requirements: 16.7.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from typing import Sequence

__all__ = [
    "EXIT_BLOCK",
    "EXIT_REDUCED_CAPABILITY",
    "OPTIONAL_RUNTIMES",
    "REQUIRED_RUNTIME",
    "OptionalRuntime",
    "RuntimeStatus",
    "available",
    "find_runtime",
    "importable",
    "main",
    "missing",
    "report",
    "statuses",
    "which",
]

#: The status a script returns when an optional runtime is absent: success. The
#: capability is reduced; the run is not a failure *(R16 AC7)*.
EXIT_REDUCED_CAPABILITY = 0

#: Kiro's blocking status, named so it is unmistakable and never returned from
#: here. A hook that exits 2 on `PreToolUse`, `UserPromptSubmit`, or
#: `PreTaskExec` blocks the action it was called about.
EXIT_BLOCK = 2

#: The one runtime the bootcamp requires. It is whatever interpreter is executing
#: this file, which is why nothing probes for it: it is present by construction.
REQUIRED_RUNTIME = "the Python interpreter running this script"


@dataclass(frozen=True)
class OptionalRuntime:
    """One optional runtime, and the reduced-capability path when it is absent.

    `commands` are executable names looked up on PATH; `modules` are importable
    Python packages that provide the same capability. Either one present means
    the capability is available.
    """

    key: str
    label: str
    commands: tuple[str, ...]
    modules: tuple[str, ...]
    needed_for: str
    without_it: str
    authority: str = ""

    def probe_targets(self) -> tuple[str, ...]:
        """Everything this runtime is looked for under, for a readable report."""
        return self.commands + self.modules


@dataclass(frozen=True)
class RuntimeStatus:
    """The answer for one optional runtime: found or not, and where."""

    runtime: OptionalRuntime
    found: str | None

    @property
    def available(self) -> bool:
        return self.found is not None

    def sentence(self) -> str:
        """One line a guide can say out loud, unchanged."""
        if self.available:
            return f"{self.runtime.label}: available ({self.found}) — {self.runtime.needed_for}."
        line = (
            f"{self.runtime.label}: not available on PATH — {self.runtime.needed_for}. "
            f"{self.runtime.without_it}"
        )
        if self.runtime.authority:
            return f"{line} {self.runtime.authority}"
        return line

    def to_json(self) -> dict[str, object]:
        return {
            "runtime": self.runtime.key,
            "label": self.runtime.label,
            "available": self.available,
            "found": self.found,
            "searched": list(self.runtime.probe_targets()),
            "neededFor": self.runtime.needed_for,
            "withoutIt": self.runtime.without_it,
        }


#: The optional runtimes this bootcamp can want. A closed set: a runtime nobody
#: has exercised gets no guidance here, and no code path reaches for it.
OPTIONAL_RUNTIMES: tuple[OptionalRuntime, ...] = (
    OptionalRuntime(
        key="container",
        label="A container runtime",
        # The same closed set `docker_lifecycle.py` dispatches on, in its order:
        # Docker, Podman, and Apple's `container` CLI on macOS Apple Silicon.
        commands=("docker", "podman", "container"),
        modules=(),
        needed_for="the SDK setup and data-loading modules run Senzing in a container",
        without_it=(
            "The prose walkthrough of those modules still runs end to end, and the "
            "concepts, data-quality, and mapping work needs no container at all. Say "
            "which module needs one before it is reached, and offer to help install it."
        ),
        authority=(
            "Containers the bootcamp already started are reported by "
            "`docker_lifecycle.py`, which names the CLI that started each one."
        ),
    ),
    OptionalRuntime(
        key="browser",
        label="A browser or headless capture backend",
        commands=(
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "chrome",
            "microsoft-edge",
            "msedge",
            "wkhtmltoimage",
        ),
        modules=("playwright", "selenium"),
        needed_for=(
            "screenshots of the truth-set visualization are captured headlessly for "
            "the recap"
        ),
        without_it=(
            "The visualization itself is unaffected: the server runs under Python and "
            "serves its URL, which the bootcamper opens in whatever browser they have. "
            "Keep the HTML link in the recap in place of the images."
        ),
        authority=(
            "`capture_screenshots.py` performs the authoritative search — PATH plus "
            "the standard Windows install locations and the registry — and reports "
            "exactly where it looked, so trust its report over this one."
        ),
    ),
)


def which(command: str) -> str | None:
    """`shutil.which`, but it never raises. None means "do not act"."""
    try:
        return shutil.which(command)
    except (OSError, ValueError):
        return None


def importable(module: str) -> bool:
    """True when `module` can be imported, without importing it. Never raises."""
    try:
        import importlib.util

        return importlib.util.find_spec(module) is not None
    except (ImportError, AttributeError, ValueError, OSError):
        return False


def find_runtime(runtime: OptionalRuntime) -> str | None:
    """Where `runtime` was found, or None. Never raises, never runs anything."""
    for command in runtime.commands:
        found = which(command)
        if found:
            return found
    for module in runtime.modules:
        if importable(module):
            return f"python module {module}"
    return None


def available(key: str) -> bool:
    """True when the optional runtime named `key` is usable here.

    An unknown key is False: nothing acts on a runtime this module does not
    declare, which is the same closed-set discipline `docker_lifecycle.py` keeps.
    """
    for runtime in OPTIONAL_RUNTIMES:
        if runtime.key == key:
            return find_runtime(runtime) is not None
    return False


def statuses() -> tuple[RuntimeStatus, ...]:
    """One `RuntimeStatus` per declared optional runtime, in declared order."""
    return tuple(
        RuntimeStatus(runtime=runtime, found=find_runtime(runtime))
        for runtime in OPTIONAL_RUNTIMES
    )


def missing() -> tuple[str, ...]:
    """Keys of the optional runtimes that are absent, in declared order."""
    return tuple(status.runtime.key for status in statuses() if not status.available)


def report(results: Sequence[RuntimeStatus] | None = None) -> str:
    """The plain-language capability report, for stderr or for the transcript.

    Names what is unavailable and what still works. It always ends by stating
    that the bootcamp continues, because that is the part a Bootcamper needs to
    hear and the part a guide most often leaves out.
    """
    results = tuple(statuses() if results is None else results)
    lines = [f"Required: {REQUIRED_RUNTIME} — present."]
    lines.extend(status.sentence() for status in results)
    absent = [status for status in results if not status.available]
    if absent:
        lines.append(
            "Reduced capability, not a failure: the bootcamp continues. Say what is "
            "unavailable once, offer help installing it, and move on."
        )
    else:
        lines.append("Every optional runtime is available here. Nothing is reduced.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Report host capability. Returns `EXIT_REDUCED_CAPABILITY` — always.

    There is no failure exit from this command by design. A caller that treats a
    non-zero status as "stop the session" must never be handed one for a missing
    optional runtime, and a hook that forwarded a 2 here would block a turn.
    """
    parser = argparse.ArgumentParser(
        prog="optional_runtime.py",
        description=(
            "Report which optional runtimes are available. Only the Python "
            "interpreter running this script is required; everything else is "
            "optional and its absence reduces capability without failing."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON on stdout instead of text on stderr",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    results = statuses()
    if args.json:
        json.dump(
            {
                "required": REQUIRED_RUNTIME,
                "optional": [status.to_json() for status in results],
                "missing": [
                    status.runtime.key for status in results if not status.available
                ],
                "exitCode": EXIT_REDUCED_CAPABILITY,
            },
            sys.stdout,
            indent=2,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    else:
        sys.stderr.write(report(results) + "\n")
    return EXIT_REDUCED_CAPABILITY


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
