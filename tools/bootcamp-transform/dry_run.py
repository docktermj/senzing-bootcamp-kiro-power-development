#!/usr/bin/env python3
"""Dry-run helpers for the Senzing Bootcamp Kiro Power (maintainer tool).

    dry_run.py scaffold <dir> [--fresh | --seeded]   build a realistic scratch bootcamp project
    dry_run.py scaffold --explain [--fresh|--seeded] print the fixture map, write nothing
    dry_run.py calls                                 phase 1 worklist: every MCP call the Power makes
    dry_run.py negatives                             phase 1 worklist: dated MCP-NEGATIVE claims, oldest first
    dry_run.py hooks --project <dir>                 phase 2: install the hooks for real and run every one
    dry_run.py record --version <semver>             open docs/test-records/<version>-dry-run.md

The canonical family operation `dry-run` (FAMILY_WORKFLOW R4), ported from the parent's
`.claude/skills/dry-run/` — its phases, not its file layout. Phase 1 (MCP contracts) and
phase 3 (the conversational walk) are driven by the skill against the live Senzing MCP
server and a human; this file supplies their worklists and phase 2's executor.

Phase 2 runs the hooks the way a Bootcamper's workspace gets them: the Power's own
Hook_Installer writes them into the scratch project's `.kiro/hooks/`, and each installed
command string is tokenized with the installer's own `tokenize_command` and executed
without a shell (KINV-005, KINV-006). Every case is run in **two payload shapes**:

* `template` — the stdin shape the ported scripts were written against (the parent's
  hook contract). A failure here is a script defect, usually parent-bound.
* `kiro` — the shape Kiro is expected to send: Kiro's tool names and its tools'
  own parameter names (`fs_write`'s `path`, not `file_path`). Until the Test_Checklist
  records the payload Kiro actually delivers (step 11), this shape is an assumption,
  and a failure is reported as a **lead about the port**, not as a verdict.

Nothing here writes into this repository except `record`, and nothing writes outside a
scratch project except `record`. Bytecode caching is off.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Sequence  # noqa: E402

ENGINE_ROOT = Path(__file__).resolve().parent
REPO = ENGINE_ROOT.parent.parent
POWER = REPO / "powers" / "senzing-bootcamp"
INSTALLER = POWER / "skills" / "bootcamp-enforcement-setup" / "scripts" / "install_hooks.py"
RECORDS = REPO / "docs" / "test-records"
FEEDBACK_REL = "docs/feedback/SENZING_BOOTCAMP_POWER_FEEDBACK.md"
HOOK_TIMEOUT = 30

# ---------------------------------------------------------------------------
# scaffold — a mid-flight bootcamp project, because an empty one exercises only gating
# ---------------------------------------------------------------------------

DIRS = (
    "config", "data/raw", "data/mapping", "data/samples", "data/temp", "database",
    "docs/progress", "docs/feedback", "docs/visualizations", "docs/mapping", "logs",
    "src/transform", "src/load", "src/system_verification",
)

MODULES = [
    "entity_resolution_concepts", "business_problem", "sdk_setup", "system_verification",
    "truthset_visualization", "data_collection",
]
PROGRESS = {
    "current_module": "data_quality_mapping",
    "current_step": "11",
    "modules_completed": MODULES,
    "selected_modules": ["bootcamp_preparation", *MODULES, "data_quality_mapping",
                         "data_processing", "query_visualize_discover", "graduation"],
    # Names a container that does not exist -> the warn-and-continue path (INV-101).
    "docker_containers": [
        {"name": "bootcamp-dryrun-absent", "image": "postgres:16", "purpose": "repository"}
    ],
    "license_record_limit": 0,
    "step_history": {
        "data_quality_mapping": {"last_completed_step": "11",
                                 "updated_at": "2026-01-01T00:00:00-07:00"}
    },
}
PREFERENCES = ("path: core\nprogramming_language: Python\nname: Ada Lovelace\nos: Linux\n"
               "arch: x86_64\ngit_init: true\nverbosity:\n  preset: standard\n")
#: Exactly the preferences INV-133 makes honorable, so preparation must skip asking them.
SEEDED_PREFERENCES = ("path: core\nselected_modules:\n"
                      + "".join(f"  - {m}\n" for m in PROGRESS["selected_modules"])
                      + "verbosity:\n  preset: minimal\nprogramming_language: Java\n")
RECAP = """# Senzing Bootcamp Recap

**Bootcamper:** Ada Lovelace
**Started:** 2026-01-01T09:00:00-07:00
**Programming language:** Python
**Path:** Core
**Plugin version:** 0.0.0-dryrun

---

## Data collection — 2026-01-01T11:00:00-07:00

### Information Shared

- CORD datasets and the Senzing Entity Specification.

### Questions & Responses

- **Q:** How would you like to provide the data for this source?
    - **R:** Option 2, a file path.

### Actions Taken

- Registered `data/raw/customers.csv` in `config/data_sources.yaml`.

### End-of-Module Summary

**What you accomplished:**

- Collected one source into `data/raw/`.

---
"""
#: An UNFINALIZED checkpoint: what the durability hooks leave and module completion clears.
CHECKPOINT = """<!-- RECAP-CHECKPOINT:START -->
## Data Quality, Mapping, and Transformation — in progress

### Information Shared

- A line with an em dash — an ellipsis … and a middle dot ·

### Questions & Responses

- **Q:** Which mapping mode would you like?
    - **R:** Verbose.

### Actions Taken

- Profiled `data/raw/customers.csv`.
<!-- RECAP-CHECKPOINT:END -->
"""
FEEDBACK = """# Senzing Bootcamp Power Feedback

## Your Feedback

## Improvement: A precious entry that must survive graduation untouched

**Date:** 2026-01-01
**Module:** Data collection
**Priority:** Medium
**Source:** bootcamper-reported
**Routing:** plugin — the banner did not appear
**Upstream:** not applicable

### What happened

If anything rewrites, empties or deletes this file, INV-067 is broken.
"""
MESSY_MARKDOWN = ("## Messy heading\ntext immediately after a heading, no blank line\n"
                  "- a list with no blank line before it\n```\nunlabelled fence\n```\n"
                  "**Label :** colon spacing is wrong\n")
#: Complete PIPELINE paths, so a script's config pre-flight passes and the SDK gate is the
#: one reached (linux_apt defaults; the parent re-asked them of sdk_guide on 2026-09-02).
PIPELINE = {"CONFIGPATH": "/etc/opt/senzing", "RESOURCEPATH": "/opt/senzing/er/resources",
            "SUPPORTPATH": "/opt/senzing/data"}

FIXTURES = [
    ("config/bootcamp_progress.json", {"mid"}, "mid-module, so every hook sees an active bootcamp"),
    ("config/bootcamp_progress.json", {"fresh", "seeded"}, "empty {}: onboarding runs from the top"),
    ("config/bootcamp_preferences.yaml", {"mid", "seeded"}, "saved preferences: honor-don't-ask (INV-133)"),
    ("config/bootcamp_preferences.yaml", {"fresh"}, "EMPTY: every question must be asked"),
    ("config/engine_config.json", {"mid"}, "COMPLETE PIPELINE: reaches the SDK gate, not the pre-flight"),
    ("config/engine_config_incomplete.json", {"mid", "fresh", "seeded"}, "empty PIPELINE: stops at the pre-flight"),
    ("docs/bootcamp_recap.md", {"mid"}, "a completed section with its subsections"),
    ("docs/progress/recap_checkpoint.md", {"mid"}, "an UNFINALIZED block: fold idempotency (INV-059)"),
    (FEEDBACK_REL, {"mid", "fresh", "seeded"}, "a precious entry nothing may rewrite (INV-067)"),
    ("docs/loading_strategy.md", {"mid"}, "messy Markdown for the normalizer"),
]


def explain(mode: str) -> None:
    print(f"Fixtures a {mode} project carries, and what each exercises:\n")
    for path, modes, why in FIXTURES:
        if mode in modes:
            print(f"  {path:44} {why}")
    absent = sorted({p for p, m, _ in FIXTURES if mode not in m} - {p for p, m, _ in FIXTURES if mode in m})
    if absent:
        print("\n  NOT in this mode (their paths are NOT exercised):")
        for path in absent:
            print(f"    {path}")


def scaffold(root: Path, mode: str) -> int:
    if root == REPO or REPO in root.parents:
        print(f"refusing: {root} is inside this repository; build the project outside it", file=sys.stderr)
        return 2
    temp_roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(), Path("/var/tmp")}
    if any(t == root or t in root.parents for t in temp_roots):
        print("refusing: the write gate blocks system-temp paths, and the Power's file-placement "
              "rules assume a real project directory. Use e.g. ~/senzing-bootcamp-dryrun", file=sys.stderr)
        return 2
    if root.exists():
        shutil.rmtree(root)
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)

    def put(rel: str, text: str) -> None:
        (root / rel).write_text(text, encoding="utf-8")

    put("config/engine_config_incomplete.json", json.dumps({"PIPELINE": {}}, indent=2) + "\n")
    put(FEEDBACK_REL, FEEDBACK)
    if mode == "mid":
        put("config/bootcamp_progress.json", json.dumps(PROGRESS, indent=2) + "\n")
        put("config/bootcamp_preferences.yaml", PREFERENCES)
        put("config/engine_config.json", json.dumps(
            {"PIPELINE": PIPELINE,
             "SQL": {"CONNECTION": f"sqlite3://na:na@{root / 'database' / 'G2C.db'}"}}, indent=2) + "\n")
        put("docs/bootcamp_recap.md", RECAP)
        put("docs/progress/recap_checkpoint.md", CHECKPOINT)
        put("docs/loading_strategy.md", MESSY_MARKDOWN)
    else:
        put("config/bootcamp_progress.json", "{}\n")
        put("config/bootcamp_preferences.yaml", SEEDED_PREFERENCES if mode == "seeded" else "")
    print(f"Built a {mode} project at {root}\n")
    explain(mode)
    print(f"\nClean up with: rm -rf {root}")
    return 0


# ---------------------------------------------------------------------------
# calls / negatives — phase 1 worklists. The live comparison is the skill's job.
# ---------------------------------------------------------------------------

def _manifest() -> dict:
    return json.loads((POWER / ".build-manifest.json").read_text(encoding="utf-8"))


def _owners() -> dict[str, str]:
    return {e["path"]: e.get("owner", "template") for e in _manifest().get("files", [])}


def _markdown() -> list[Path]:
    return sorted(p for p in POWER.rglob("*.md") if p.is_file() and p.name != "CHANGELOG.md")


#: A call written as code: `tool_name(` followed by a keyword argument or a close paren.
CALL = re.compile(r"`?\b([a-z][a-z0-9_]{2,})\((?=\s*(?:[a-z_]+\s*=|\)))")
LITERAL = re.compile(r"\b(action|topic|category|platform|workflow|language)\s*=\s*['\"]([A-Za-z0-9_\-]+)['\"]")


def calls() -> int:
    owners = _owners()
    tools: dict[str, dict] = {}
    for path in _markdown():
        rel = path.relative_to(POWER).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name in CALL.findall(line):
                entry = tools.setdefault(name, {"sites": [], "owners": set(), "literals": set()})
                entry["sites"].append(f"{rel}:{lineno}")
                entry["owners"].add(owners.get(rel, "unrecorded"))
                for key, value in LITERAL.findall(line):
                    entry["literals"].add(f"{key}={value}")
    print("== phase 1 worklist: every call the Power writes as code, with the literals it passes\n")
    print("   Compare each against the LIVE server's schema (get_capabilities lists the tools).")
    print("   A name the server does not have is either a non-MCP function or a defect; read the site.\n")
    for name in sorted(tools, key=lambda n: -len(tools[n]["sites"])):
        entry = tools[name]
        print(f"   {name:<26} {len(entry['sites']):4d} site(s)  [{', '.join(sorted(entry['owners']))}]  e.g. {entry['sites'][0]}")
        if entry["literals"]:
            print(f"   {'':<26} literals: {', '.join(sorted(entry['literals']))}")
    print(f"\n   {len(tools)} distinct call name(s). template sites -> a defect is parent-bound;"
          " kiro sites -> local.")
    return 0


NEGATIVE = re.compile(r"<!--\s*MCP-NEGATIVE:(.*?)-->", re.S)
STAMP = re.compile(r"server\s+(\d+\.\d+\.\d+)\s*,\s*(\d{4}-\d{2}-\d{2})")


def negatives() -> int:
    owners = _owners()
    rows = []
    for path in _markdown():
        rel = path.relative_to(POWER).as_posix()
        text = path.read_text(encoding="utf-8")
        for match in NEGATIVE.finditer(text):
            body = " ".join(match.group(1).split())
            lineno = text.count("\n", 0, match.start()) + 1
            stamps = STAMP.findall(body)
            version, date = (stamps[-1] if stamps else ("0.0.0", "undated"))
            rows.append((tuple(int(p) for p in version.split(".")), date, f"{rel}:{lineno}",
                         owners.get(rel, "unrecorded"), body))
    rows.sort()
    print("== phase 1 worklist: dated claims that an MCP tool does NOT contain something, oldest first\n")
    for version, date, where, owner, body in rows:
        print(f"   server {'.'.join(map(str, version)):<9} {date:<10} [{owner}] {where}")
        print(f"       {body[:160]}")
    print(f"\n   {len(rows)} marker(s). Re-ask each against the live server: claim false, claim true"
          " with rationale intact, or claim true with rationale stale — three outcomes, not two.")
    return 0


# ---------------------------------------------------------------------------
# hooks — phase 2, against the hooks a Bootcamper's workspace actually gets
# ---------------------------------------------------------------------------

def _installer():
    spec = importlib.util.spec_from_file_location("install_hooks", INSTALLER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["install_hooks"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@dataclass
class Case:
    script: str
    shape: str
    label: str
    payload: dict
    expect: str  # "block" (exit 2), "allow" (exit 0), "inject" (stdout), "silent" (no output)


def _write_cases(project: Path) -> list[Case]:
    home = Path.home()
    cases = []
    targets = [
        ("system temp", "/tmp/dryrun-evil.txt", "x", "block"),
        ("~/Downloads", str(home / "Downloads" / "dryrun.txt"), "x", "block"),
        ("../ escape", "../outside-the-project.txt", "x", "block"),
        ("PEM key in content", "notes.md", "-----BEGIN RSA PRIVATE KEY-----\nabc", "block"),
        ("project-relative", "docs/notes.md", "ordinary text", "allow"),
        ("in-project absolute", str(project / "src" / "load" / "x.py"), "print(1)", "allow"),
    ]
    for label, target, content, expect in targets:
        cases.append(Case("write-gate", "template", label,
                          {"tool_name": "Write", "tool_input": {"file_path": target, "content": content}}, expect))
        cases.append(Case("write-gate", "kiro", label,
                          {"tool_name": "fs_write", "tool_input": {"path": target, "text": content}}, expect))
    return cases


def _cases(project: Path) -> list[Case]:
    cases = _write_cases(project)
    feedback = "I have some feedback about the bootcamp: the banner did not appear"
    unrelated = "what is entity resolution?"
    for shape, key in (("template", "prompt"), ("kiro", "prompt")):
        cases.append(Case("feedback-capture", shape, "a feedback prompt", {key: feedback}, "inject"))
        cases.append(Case("feedback-capture", shape, "an unrelated prompt", {key: unrelated}, "silent"))
    cases.append(Case("stop-nudge", "template", "stop_hook_active is true",
                      {"stop_hook_active": True, "transcript_path": str(project / "nope.jsonl")}, "silent"))
    cases.append(Case("stop-nudge", "template", "an unreadable transcript",
                      {"stop_hook_active": False, "transcript_path": str(project / "nope.jsonl")}, "silent"))
    cases.append(Case("stop-nudge", "kiro", "no transcript field at all", {}, "silent"))
    return cases


def _run(tokens: Sequence[str], cwd: Path, payload: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(list(tokens), input=json.dumps(payload), cwd=str(cwd), capture_output=True,
                          text=True, timeout=HOOK_TIMEOUT, env=env)


def _verdict(case: Case, done: subprocess.CompletedProcess) -> bool:
    if "Traceback" in done.stderr:
        return False
    out = (done.stdout + done.stderr).strip()
    if case.expect == "block":
        return done.returncode == 2
    if case.expect == "allow":
        return done.returncode == 0
    if case.expect == "inject":
        return done.returncode == 0 and bool(done.stdout.strip())
    return done.returncode == 0 and not out


def hooks(project: Path) -> int:
    if not (project / "config" / "bootcamp_progress.json").is_file():
        print(f"refusing: {project} is not a scaffolded project (run `dry_run.py scaffold` first)", file=sys.stderr)
        return 2
    installer = _installer()
    install = subprocess.run(
        [sys.executable, "-B", str(INSTALLER), "install", "--consent", "granted", "--workspace", str(project),
         "--power-root", str(POWER), "--quiet"], capture_output=True, text=True)
    if install.returncode != 0:
        print(f"FAIL: the Hook_Installer refused: {install.stdout.strip()[:400]} {install.stderr.strip()[:400]}")
        return 1
    installed = sorted((project / ".kiro" / "hooks").glob("senzing-bootcamp-*.json"))
    entries = []
    for path in installed:
        for hook in json.loads(path.read_text(encoding="utf-8")).get("hooks", []):
            command = (hook.get("action") or {}).get("command")
            if command:
                tokens = installer.tokenize_command(command)
                script = Path(tokens[-1]).stem
                entries.append((hook.get("trigger"), hook.get("matcher"), script, tokens, command))
    print(f"== phase 2: {len(entries)} hook entr(ies) installed by the Power's own Hook_Installer into {project}/.kiro/hooks\n")
    results = []

    # 1. Gating: outside a bootcamp every hook is a silent no-op (KINV-007).
    with tempfile.TemporaryDirectory(prefix="dryrun-ungated-", dir=str(project.parent)) as ungated:
        for trigger, _matcher, script, tokens, _ in entries:
            payload = {"prompt": "hello", "tool_name": "fs_write", "tool_input": {"path": "/tmp/x"}}
            done = _run(tokens, Path(ungated), payload)
            ok = done.returncode == 0 and not (done.stdout + done.stderr).strip()
            results.append(("gating", script, "-", f"{trigger} outside a bootcamp is a silent no-op", ok,
                            done.returncode, (done.stdout + done.stderr).strip()[:100]))

    # 2. Behavior inside the bootcamp, in both payload shapes.
    by_script = {script: tokens for _t, _m, script, tokens, _ in entries}
    for case in _cases(project):
        tokens = by_script.get(case.script)
        if tokens is None:
            results.append(("behavior", case.script, case.shape, case.label, None, None, "not installed"))
            continue
        done = _run(tokens, project, case.payload)
        results.append(("behavior", case.script, case.shape, f"{case.label} -> {case.expect}",
                        _verdict(case, done), done.returncode, (done.stdout + done.stderr).strip()[:100]))

    # 3. Durability: the checkpoint tick and session start run repeatedly without breaking state.
    checkpoint = project / "docs" / "progress" / "recap_checkpoint.md"
    for script in ("checkpoint-tick", "session-start"):
        tokens = by_script.get(script)
        if tokens is None:
            continue
        codes = [_run(tokens, project, {"prompt": "next"}) for _ in range(3)]
        ok = all(c.returncode == 0 and "Traceback" not in c.stderr for c in codes)
        if checkpoint.is_file():
            ok = ok and checkpoint.read_text(encoding="utf-8").count("RECAP-CHECKPOINT:START") <= 1
        results.append(("durability", script, "-", "three runs: exit 0, at most one checkpoint block", ok,
                        codes[-1].returncode, (codes[-1].stdout + codes[-1].stderr).strip()[:100]))

    feedback_intact = (project / FEEDBACK_REL).read_text(encoding="utf-8") == FEEDBACK
    results.append(("integrity", "-", "-", f"{FEEDBACK_REL} byte-identical after every hook", feedback_intact,
                    None, ""))

    for group, script, shape, label, ok, code, detail in results:
        status = "UNTESTED" if ok is None else ("PASS" if ok else "FAIL")
        print(f"   {status:<8} {group:<10} {script:<17} {shape:<8} {label}"
              + (f"  [exit {code}]" if code is not None else ""))
        if ok is False and detail:
            print(f"   {'':<8} {'':<10} {detail}")
    failed = [r for r in results if r[4] is False]
    kiro_failed = [r for r in failed if r[2] == "kiro"]
    print(f"\n   {sum(1 for r in results if r[4])} pass, {len(failed)} fail, "
          f"{sum(1 for r in results if r[4] is None)} untested")
    if kiro_failed:
        print("   ⚠ The `kiro` shape is ASSUMED until the Test_Checklist records the payload Kiro")
        print("     delivers (step 11). Confirm it live before filing; a confirmed failure is local.")
    print("   ⛔ This executes the scripts as Kiro would; it does not prove Kiro FIRES them —")
    print("     that is the Test_Checklist (steps 10, 11) and phase 3's installed walk.")
    remove = subprocess.run([sys.executable, "-B", str(INSTALLER), "remove", "--consent", "granted",
                             "--workspace", str(project), "--power-root", str(POWER), "--quiet"],
                            capture_output=True, text=True)
    print(f"   hooks removed from the scratch project: {'yes' if remove.returncode == 0 else 'NO — remove by hand'}")
    return 0


# ---------------------------------------------------------------------------
# record — the run's durable evidence, opened at the first finding
# ---------------------------------------------------------------------------

RECORD_TEMPLATE = """# Dry run — Bootcamp_Power {version}

The durable record of a `dry-run` against this version: written as findings appear, before
anything is fixed (INV-317). A finding held only in conversation is not recorded.

- **Version under test:** `{version}`
- **Date:** `_unrecorded_`
- **Senzing MCP server version:** `_unrecorded_`
- **Kiro version / platform:** `_unrecorded_`

## Phases

A phase that did not run, or could not run on Kiro, says so here. It is never a pass.

| Phase | Status | Scope and limits |
|---|---|---|
| 1 — MCP call contracts | `untested` | |
| 2 — Hooks and scripts | `untested` | |
| 3a — Guided walk (this workspace) | `untested` | |
| 3b — Installed walk (Kiro host) | `untested` | |

Status is one of `run`, `partial`, `untested`, or `degraded: <the Kiro gap, and the KINV or
register entry that documents it>`.

## Findings

One entry per root cause. Lifecycle marker: `not filed`, `filed #<n>`, `escalated <url>`,
`already tracked #<n>`, `declined: <reason>`, or `sent upstream <date> <category>`.

<!-- ### <title>
- **Phase / site:** `powers/senzing-bootcamp/<path>:<line>`, home from the manifest triple
- **Verdict:** local | parent-bound | both | mcp-server — <reason>
- **Evidence:** <what was run or said, and what came back; MCP claims dated with the server version>
- **Marker:** not filed
-->

## Host-behavior facts to carry into the Test_Checklist

<!-- A fact about how Kiro behaves that the checklist does not record yet. -->
"""


def record(version: str) -> int:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        print(f"refusing: {version!r} is not MAJOR.MINOR.PATCH", file=sys.stderr)
        return 2
    path = RECORDS / f"{version}-dry-run.md"
    if path.exists():
        print(f"{path.relative_to(REPO)} already exists; append to it, never replace it")
        return 0
    path.write_text(RECORD_TEMPLATE.format(version=version), encoding="utf-8", newline="\n")
    print(f"opened {path.relative_to(REPO)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scaffold", help="build a realistic scratch bootcamp project")
    sc.add_argument("directory", nargs="?")
    sc.add_argument("--fresh", action="store_true")
    sc.add_argument("--seeded", action="store_true")
    sc.add_argument("--explain", action="store_true")
    sub.add_parser("calls", help="phase 1: every MCP call the Power writes as code")
    sub.add_parser("negatives", help="phase 1: dated MCP-NEGATIVE claims, oldest first")
    hk = sub.add_parser("hooks", help="phase 2: install and run every hook")
    hk.add_argument("--project", required=True)
    rc = sub.add_parser("record", help="open docs/test-records/<version>-dry-run.md")
    rc.add_argument("--version", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "scaffold":
        mode = "seeded" if args.seeded else "fresh" if args.fresh else "mid"
        if args.explain:
            explain(mode)
            return 0
        if not args.directory:
            parser.error("scaffold needs a directory (or --explain)")
        return scaffold(Path(args.directory).expanduser().resolve(), mode)
    if args.cmd == "calls":
        return calls()
    if args.cmd == "negatives":
        return negatives()
    if args.cmd == "hooks":
        return hooks(Path(args.project).expanduser().resolve())
    return record(args.version)


if __name__ == "__main__":
    sys.exit(main())
