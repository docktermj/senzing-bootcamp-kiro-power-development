---
name: "dry-run"
description: "Dry-run the Senzing Bootcamp Kiro Power to find what only shows up when it runs, in three phases that get more expensive in order: phase 1 checks every Senzing MCP call the Power makes against the live server, phase 2 installs the hooks with the Power's own installer into a realistic scratch project and executes every one in Kiro's payload shape, and phase 3 walks the bootcamp with the maintainer answering as the bootcamper — in this workspace, and installed on the Kiro host. A phase that cannot run on Kiro is recorded as an advisory degradation, never as a pass. Findings are recorded as they appear, routed local or parent-bound with a reason, and filed as issues only with approval. Use when the maintainer says 'dry-run the senzing bootcamp power'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-power-development — as the open workspace, because the Power, its hook installer, the test records, and the dry-run helpers all live here. Needs Python 3.10+ and git; the live Senzing MCP server for phase 1; Kiro itself, with the Power installable from a local path, for phase 3's installed walk; and the maintainer present for phase 3. Phases past SDK setup need a real Senzing install, a database, and a license. `gh` with issue-write on this repository to file."
metadata:
  author: "Senzing"
  role: "Dry_Run"
  engine: "tools/bootcamp-transform/"
  script: "tools/bootcamp-transform/dry_run.py"
  parentDevelopmentRepository: "docktermj/senzing-bootcamp-claude-plugin-development"
---

# Dry-run the Senzing Bootcamp Power

The canonical family operation `dry-run` (FAMILY_WORKFLOW R4), Phase 3. Everything else in this
repository verifies the port **statically**: the contract matches every file, the schema
validates, the determinism gate rebuilds clean, the register accounts for every inherited
invariant. None of that observes the bootcamp **behaving**, and the whole point of this family is
that a bootcamper gets the same experience on Kiro as on Claude — a claim about runtime.

> Static analysis can only confirm the Power agrees **with itself**. It cannot see where it
> disagrees with the world — the MCP server's real schemas, the Kiro host, a rendered artifact,
> or a human answering questions.

This ports the parent's phases, not its file layout. The helpers are
[`tools/bootcamp-transform/dry_run.py`](../../../../tools/bootcamp-transform/dry_run.py).

| Phase | Checks the Power against | Needs |
|---|---|---|
| 1 — MCP call contracts | the **live** Senzing MCP server's schemas | the Senzing MCP server |
| 2 — Hooks and scripts | a real filesystem, the real installer, Kiro's payload shape | `python3` |
| 3a — Guided walk | the instructions, followed by Kiro's agent | **the maintainer** |
| 3b — Installed walk | the Kiro host: skill activation, hook firing, the Power as installed | **the maintainer**, Kiro |

Run them in order. They get more expensive in that order, and a failure in phase 1 — a module that
cannot make its MCP call — makes a phase 3 walk through that module meaningless.

## How it composes with the `Test_Checklist` (component G)

The checklist records the **host-mechanism** answers per release — does the installed hook fire,
which tool names reach the `PreToolUse` matcher, what stdin a hook receives. This skill exercises
the **bootcamp** on top of those answers. They compose: phase 2 runs the scripts in the payload
shape the checklist says Kiro sends, and phase 3b is where a host fact the checklist does not carry
yet gets noticed. ⛔ **A host-behavior fact a dry run discovers goes into the checklist**, as a new
step or a sharper pass condition in `docs/test-checklist.md`, not only into this run's record.

## Before you start

1. **Ask which phases to run** if the maintainer did not say. Present 1, 2, 3a, 3b, or all, as a
   numbered list; never read "dry-run the power" as "all". Phase 3 costs the maintainer's time.
2. **If phase 3 is among them, ask which module the analysis starts at** — list the stages from
   `bootcamp-preparation/SKILL.md`'s module table in order, numbered, and mark which this
   environment can reach. A walk that analyzes from the top exhausts its context in the opening
   modules every time; everything before the chosen module is walked with the analysis off.
3. **Open the run's record** — the durable home for every finding, and the release evidence that
   a phase ran or did not:
   ```
   python3 tools/bootcamp-transform/dry_run.py record --version <version from powers/senzing-bootcamp/plugin.json>
   ```
   It writes `docs/test-records/<version>-dry-run.md` and never overwrites one that exists.
4. **Record the environment's limits** in it: Kiro version and platform, the Senzing MCP server
   version (`get_capabilities` reports it), and whether the `senzing` package, `libSz.so`, `fpdf2`,
   `docker`, and a headless browser are present. Missing pieces are fine; silently skipping the
   paths that need them is not.
5. **Work outside the repository** for anything a bootcamper's project would hold —
   `$HOME/senzing-bootcamp-dryrun`, never under the repo and never under a system temp directory.

## Phase 1 — MCP call contracts

The Senzing MCP server is the Power's hard dependency and its entire factual foundation, so a wrong
tool name, a missing required parameter, or an invented enum value breaks a module outright.

1. **Load the schemas from the server, not from the Power's prose about them.** Call
   `get_capabilities` first: it returns the tool manifest, the suggested workflows, and the
   `common_confabulations` the server expects a model to make. Record the server version.
2. **Enumerate what the Power calls**:
   ```
   python3 tools/bootcamp-transform/dry_run.py calls
   ```
   For each name and literal: does the tool exist, is every **required** parameter named at the
   calling site, is every `action` / `topic` / `category` / `platform` / `workflow` value in the
   schema's enum? A name the server does not have is either a non-MCP function (an SDK method in a
   code sample) or a defect — read the site.
3. **Probe empirically where the Power makes a claim about the server.** Reading a schema catches a
   missing parameter; only a call catches a wrong claim.
4. **Re-ask every dated negative**, oldest first:
   ```
   python3 tools/bootcamp-transform/dry_run.py negatives
   ```
   Each is a claim that a tool does **not** contain something, with the server version and date it
   was last checked. A re-ask has three outcomes: the claim is false; the claim holds and its
   rationale reproduces; the claim holds and its rationale does not. All three are findings to
   record, and the third is the one a restamp would hide.
5. **Cross-check `common_confabulations`** against the Power.

⛔ **Never call `submit_feedback` to test it, and never call `download_resource` on anything
large.** Verify their schemas; do not invoke them.

Phase 1 findings are almost all **parent-bound**: the calls live in ported curriculum, and the
`calls` view marks every site `template`. A call the port itself wrote, or one a Kiro substitution
set rewrote, is local.

## Phase 2 — Hooks and scripts

```
python3 tools/bootcamp-transform/dry_run.py scaffold "$HOME/senzing-bootcamp-dryrun"
python3 tools/bootcamp-transform/dry_run.py hooks --project "$HOME/senzing-bootcamp-dryrun"
```

The scaffold is a **mid-flight** bootcamp — an active module, a recap with a completed section, an
unfinalized checkpoint block, a precious feedback entry, messy Markdown, a complete and an
incomplete engine config — because an empty project exercises only each hook's gating branch.
`--explain` prints what each fixture exercises without writing anything.

`hooks` installs the hooks **with the Power's own Hook_Installer**, so the command strings under
test are the ones a bootcamper's workspace gets, then executes every installed entry the way Kiro
does — the single command string tokenized and run without a shell (KINV-005, KINV-006):

- **gating** — outside a bootcamp every hook is a silent no-op (KINV-007);
- **behavior** — the write gate blocks system temp, `~/Downloads`, a `../` escape and a secret,
  and allows in-project writes; feedback capture injects on a feedback prompt and stays silent on
  an unrelated one; the stop nudge stays silent when it should;
- **durability** — the checkpoint and session hooks run three times without duplicating state;
- **integrity** — the precious feedback file is byte-identical afterwards.

⛔ **Every behavior case runs in two payload shapes, and the difference is the point.** `template`
is the stdin the ported scripts were written against; `kiro` uses Kiro's tool names and its tools'
own parameter names. A `template` failure is a script defect, usually parent-bound. A `kiro`-only
failure is a **lead about the port**: the script and the host disagree about the payload, and the
fix is local. Until the checklist records the payload Kiro actually delivers (step 11), the `kiro`
shape is an assumption — confirm a `kiro` failure live before filing it, by capturing a real
payload in phase 3b.

Then drive the bundled scripts and **inspect the artifact, not the exit code**:
`normalize_docs_markdown.py` must leave the feedback file byte-identical; `generate_recap_pdf.py`
must report the renderer it used, and a fallback when the preferred renderer is installed is a
defect; `generate_discoveries_pdf.py` given junk writes no PDF; `generate_recap_video.py` turns a
missing image into a title card and refuses a `../` path; `senzing_viz_server.py --no-serve` fails
loudly without the SDK — and read **which** gate failed, exit 2 (config pre-flight) or exit 1 (SDK
load), because they look identical otherwise.

⛔ `hooks` executes the scripts as Kiro would; it does **not** prove Kiro fires them. Firing is the
checklist's steps 10 and 11, and phase 3b's installed walk.

## Phase 3 — The conversational walk

⛔ **The assistant must not play both roles.** The Power forbids fabricating a bootcamper's answer,
and an assistant that knows it is being graded on one-question-per-turn discipline will comply.
The maintainer answers, as themselves. If the maintainer is not available, phase 3 is `untested`.

Follow the skill files **as written**, not from memory. Everything before the chosen module is the
fast-forward — the same walk with the notes off, the maintainer still answering, no narration;
only a blocker is recorded there. From the chosen module on, keep two channels: the bootcamp output
exactly as a bootcamper would see it, then a collapsed, clearly ignorable test-notes block.

Watch, in rough order of how often they break: one 👉 question per turn ending the turn (INV-251 —
on Kiro advisory only, KINV-011); saved preferences honored and not re-asked (INV-133); nothing
asked twice; one consolidated config write in preparation; the apparatus exemptions for preparation
and the concepts module; stages named, never numbered, in anything the bootcamper reads; pinned
gate wording character for character; the model and effort nudge naming Kiro's pickers (KINV-013).
And the class unique to this phase: an instruction the guide is told it must follow and provably
cannot.

### 3a — The guided walk, in this workspace

Kiro's agent follows the Power's skill files from this repository, with the scratch project as the
bootcamper's project directory. It tests whether **the instructions** produce the right behavior on
Kiro's model and tools. Scaffold `--fresh` when the analysis starts at preparation (then a short
second walk with `--seeded`, so the honor-don't-ask path is tested in its active direction), or
`--seeded` when it starts later.

⚠️ **Recorded as `degraded`, always, for what it cannot reach:** no skill is activated by Kiro from
a trigger phrase, and no hook fires, because the Power is read rather than installed. Name both in
the record's phase table. They are what 3b exists for.

### 3b — The installed walk, on the Kiro host

The Power as a bootcamper gets it:

1. Scaffold `--fresh` or `--seeded` into a new directory and open it in Kiro as its own workspace.
2. Install the Power from its local path, `powers/senzing-bootcamp/`, through Kiro's Powers panel —
   the same route as checklist step 2.
3. Start a new chat and begin the bootcamp the way a bootcamper would. Accept the enforcement-setup
   offer, so the workspace hooks are installed by consent (KINV-009) and fire for real.
4. The maintainer drives that session **as the bootcamper**. Nothing analytical happens inside it:
   it is the system under test.
5. Back in this workspace, review what the session produced — the project's `config/`, `docs/`,
   recap, checkpoint and feedback files, `.kiro/hooks/`, and whatever the maintainer observed —
   against the same watch list. Capture one real `PreToolUse` payload if the write gate's `kiro`
   shape is still unconfirmed.

What 3b establishes that nothing else does: that trigger phrases activate the right skills, that
installed hooks fire on Kiro's triggers, that a non-blocking `Stop` degrades as KINV-011 says, and
that the per-turn checkpoint bounds the recap loss as KINV-012 says.

⚠️ Where a part of 3b cannot run — the installed hooks never fire, a trigger Kiro does not provide,
a platform not available — record it as `degraded:` with the gap and the KINV or register entry
that documents it, and never as a pass. A gap no record documents is itself a finding.

## Findings

1. ⛔ **Record each finding in the run's record as you find it, before fixing anything**
   (INV-317). In phase 3, the moment an observation firms up — the walk stops when the maintainer
   stops it. A finding held only in conversation is not recorded.
2. **Route each one, with the reason** (R6). Look the shipped path up in
   `powers/senzing-bootcamp/.build-manifest.json` for its `ruleId` / `owner` / `sourcePath`:
   - **parent-bound** — the defect reproduces on the parent: curriculum, a Senzing fact, a ported
     script's own logic. Hand it to [`escalate-to-parent`](../escalate-to-parent/SKILL.md).
   - **local** — the port, the installer, a hook definition, a substitution, a Kiro mechanism, or a
     script that disagrees with Kiro's payload. File it here.
   - **both** — an escalation and a local issue, cross-referenced.
   - **mcp-server** — the live server is what is wrong, re-verified this session, with any absence
     claim naming the route asked and what it returned (INV-213).
3. **Search before filing**, here and read-only in the parent:
   `gh issue list --repo docktermj/senzing-bootcamp-kiro-power-development --state all --search "<terms>"`.
4. **File at the end of phase 1 or 2, or when a phase 3 walk pauses or ends — never mid-walk**: a
   filing question inside a bootcamp turn is a second 👉 and changes what is being tested. Show each
   title and body and get a yes, given out of character, one at a time (INV-314). Never apply
   `unattended-ok` (INV-318). Then replace the record's marker with the issue number.
5. **Upstream only for an `mcp-server` finding**, and only on an out-of-character yes:
   `submit_feedback` with everything identifying stripped, `category` `bug` or `feature`, never
   `license_request`. A yes given in character, while answering as the bootcamper, authorizes
   nothing.
6. **Fix the class, not the instance**, and only when asked — at the producing home through
   `implement-github-issue`, never in `powers/senzing-bootcamp/`. A test written for it joins the
   existing suite (see the INV-108 entry in the disposition register).

⛔ **Do not end a run with an unrecorded finding.** Before reporting, confirm every finding in the
record carries a marker other than a bare draft, or is explicitly `not filed` with the maintainer
told so.

## Report

- **Lead with anything that breaks a documented path**, severity first.
- **Name where each finding lives** — issue, escalation, or record marker — and which are open.
- **State each phase's status** from the record's table, including every `degraded:` and `untested`.
- **If phase 3 ran, name the module the analysis started at**, and that everything before it was
  walked rather than tested.
- **Say what you verified as correct**, briefly, so the next run need not re-check it.
- ⛔ **State the coverage limits explicitly**: the environment's missing pieces, and that a clean
  stretch of a walk is weaker evidence than a finding.

## Cleaning up

Remove the scratch projects (`rm -rf "$HOME/senzing-bootcamp-dryrun"`), uninstall the Power from the
3b workspace, and leave this repository with only the run's record and any intended changes.
⛔ **The scratch project is disposable; the record and the issues are the run's output.** Commit
the record with the release's other evidence, so `release` tags a version whose dry run is on file.

## Scope

This skill exercises the Power; it does not build, validate, release or propagate it. It writes only
the run's record in this repository and scratch projects outside it, and never files outside this
repository — parent-bound findings go through `escalate-to-parent`.
