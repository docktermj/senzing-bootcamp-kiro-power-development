# Test_Checklist — the manual gate before a Bootcamp_Power release is tagged

Seventeen ordered steps, each with one observable pass/fail outcome *(R6 AC1)*. A Maintainer
works them against a built `powers/senzing-bootcamp/` before tagging, records an outcome for
every step, and commits the record. The recorded file, together with a `passed` validation
report for that exact version, is the tagging gate *(R6 AC2, AC3)*.

Everything here is manual on purpose. Kiro skill activation, Power installation, hook loading,
MCP behavior in a live session, and per-platform operation are external-system behaviors with no
programmatic harness — so they are verified by a person and written down. Steps 9–11 exist to
turn the design's unverified assumptions **A1–A4** into recorded facts, so each release reduces
the uncertainty the next one inherits.

An `_unrecorded_` outcome is a **fail**, not a blank. That applies to whole steps and to the
nine per-platform cells alike *(R6 AC3, AC12)*.

Step numbers are stable across releases. A step is never renumbered to make room; a new step is
appended and the record format version changes with it.

## How to record a run

Generate the record skeleton for the version under test with
`tools/bootcamp-transform/testrecord.py` (see its `--help`), or copy this file to
`docs/test-records/<version>.md` by hand. Either way the record must name the version under
test, the resolved Template_Release, the Maintainer, the date, and the `status` of the
validation report from step 1, then carry one recorded outcome per step and one per platform
cell. Commit it — the per-step outcomes stay reviewable for the tagged release *(R6 AC6)*.

Tagging is allowed only when the record names the exact version under test, every one of the 17
steps carries a recorded `pass`, and all nine platform cells carry a recorded `pass`. A missing
step, a blank outcome, a blank platform cell, an explicit fail, or a version mismatch each
blocks tagging with `E_CHECKLIST_INCOMPLETE` *(R6 AC2, AC3, AC12)*.

## How this file is parsed

This document is read by machine as well as by a person:
`tools/bootcamp-transform/testrecord.py` reads it as the checklist *definition* and emits
`docs/test-records/<version>.md` from it, and `tools/bootcamp-transform/tests/test_structure.py`
asserts its shape. The structure below is therefore a contract, not a layout preference.

- One step per `## Step <N> — <title>` heading. `<N>` runs from 1 to 17, strictly increasing,
  no gaps and no repeats. There are exactly 17 such headings and no other heading level 2
  begins with `Step`.
- Each step block carries the fields below as top-level list items, in this order, each opening
  with a bold label:

  | Field | Present on | Meaning |
  |---|---|---|
  | `**Verifies:**` | every step | the acceptance criteria and assumptions the step discharges |
  | `**Preconditions:**` | steps that need one | the state the workspace or session must be in first |
  | `**Do:**` | every step | the actions, as a numbered list |
  | `**Pass:**` | every step | the single observable condition that counts as a pass |
  | `**Fail:**` | every step | what a fail looks like, stated so it cannot be argued away |
  | `**Activation cells:**` | step 6 only | one row per skill in the Bootcamp_Power inventory |
  | `**Platform cells:**` | steps 2, 10, 15 only | one row per Supported_Platform |
  | `**Outcome:**` | every step | the recording slot for the step |

- A cell is identified by `` `<step>.<key>` ``. The platform keys are `linux`, `macos`, and
  `windows`, giving the nine cells `2.linux` … `15.windows`. The step 6 keys are skill names.
- Cell tables are nested under their field label and therefore indented; a parser strips leading
  whitespace from a table row. Each row's first column is the backticked cell ID and its last
  column is the recording slot.
- `_unrecorded_` marks an empty recording slot and counts as a fail.
- Steps 2, 10, and 15 record three outcomes each — one per platform cell — and their step-level
  `**Outcome:**` is a pass only when all three cells are a pass. Every other step records one
  outcome. Step 6's activation cells are part of its definition, not separate record slots: they
  say what to try, and step 6 records one rolled-up outcome.

---

## Step 1 — Validation reports `passed` for the exact version being tagged

- **Verifies:** R13 AC5, R6 AC2
- **Do:**
  1. Write down the version being prepared. Every later step and the record itself refer to
     this one version.
  2. Run the Schema_Validator against the built tree with `--tag <version>`, `--source` set to
     the extracted Template_Release it was built from, and
     `--report docs/test-records/<version>-validation.json`.
  3. Read `status`, `tagAllowed`, and the version the report names.
- **Pass:** `status` is `passed`, `tagAllowed` is true, and the report names exactly the version
  being tagged.
- **Fail:** `status` is `failed` or `incomplete`; `tagAllowed` is false; the report names a
  different version; or the report predates the tree under test.
- **Outcome:** `_unrecorded_`

## Step 2 — Power installs locally via Kiro Powers → **Add Custom Power**

- **Verifies:** R6 AC1, AC12
- **Do:**
  1. On the platform whose cell you are filling, open Kiro → Powers → **Add Custom Power** and
     point it at the built `powers/senzing-bootcamp/` directory.
  2. Let the install complete without hand-editing anything in the Power.
  3. Open the installed Power and list its skills.
- **Pass:** the install completes with no error and the installed Power lists all 16 skills.
- **Fail:** any install error or schema complaint, a missing skill, or an install that only
  succeeded after a manual edit to the Power.
- **Platform cells:**

  | Cell | Platform | Outcome |
  |---|---|---|
  | `2.linux` | Linux | `_unrecorded_` |
  | `2.macos` | macOS | `_unrecorded_` |
  | `2.windows` | Windows | `_unrecorded_` |

- **Outcome:** recorded per platform in the three cells above; a pass only when all three are a
  pass.

## Step 3 — Power loads in a fresh chat session

- **Verifies:** R6 AC1
- **Preconditions:** step 2 passed on this platform.
- **Do:**
  1. Start a **new** chat session with no prior conversation history — not a continuation, not a
     resumed or compacted session.
  2. Before typing anything else, confirm the Power's skills and its MCP server are present in
     that session.
  3. State the `start-bootcamp` trigger phrase, "start the senzing bootcamp", and nothing else.
- **Pass:** the Power is loaded in that first session and `start-bootcamp` activates with no
  priming from any earlier session.
- **Fail:** skills appear only after a reload or a second session, or activation needs context
  established before this session began.
- **Outcome:** `_unrecorded_`

## Step 4 — The Senzing MCP server connects

- **Verifies:** R6 AC4, R11
- **Preconditions:** the fresh session from step 3.
- **Do:**
  1. Check the MCP server status for the declaration in the Power's `mcp.json` —
     `https://mcp.senzing.com/mcp`, type `streamable-http`.
  2. List the server's tools.
- **Pass:** the server reports connected and at least one tool is listed.
- **Fail:** a connection, transport, or authorization error; an unrecognized server type; or a
  connected server that lists no tools.
- **Outcome:** `_unrecorded_`

## Step 5 — A Senzing MCP tool call returns a successful response

- **Verifies:** R6 AC4
- **Preconditions:** step 4 passed in this session.
- **Do:**
  1. Call one Senzing MCP tool through the Power — the connectivity check that
     `bootcamp-preparation` names as its prerequisite is the natural choice.
  2. Record the tool name called and the shape of what came back.
- **Pass:** the call returns a successful response the skill can use — a result, not an error
  envelope.
- **Fail:** any error response, a timeout, or a response the calling skill cannot proceed on.
- **Outcome:** `_unrecorded_`

## Step 6 — Each skill in the inventory activates from its own trigger phrase

- **Verifies:** R6 AC5, R9 AC4, R8 AC6
- **Do:**
  1. For each row below, read the skill's `description` in the **installed** Power and take the
     phrase it quotes — every skill states its own trigger phrase there ("Use when the
     bootcamper says '…'").
  2. In a fresh session, state that phrase and nothing else.
  3. Record which skill actually activated. For a module row, also record the resolved skill
     directory name from the Build_Manifest, since module directory names come from the
     resolved Template_Release rather than from this file.
- **Activation cells:**

  | Cell | Group | Skill | Trigger phrase | Activated? |
  |---|---|---|---|---|
  | `6.bootcamp-onboarding` | ported | `bootcamp-onboarding` | the phrase its own description quotes | `_unrecorded_` |
  | `6.bootcamp-preparation` | ported | `bootcamp-preparation` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-00` | ported | `module-00-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-01` | ported | `module-01-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-02` | ported | `module-02-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-03` | ported | `module-03-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-03b` | ported | `module-03b-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-04` | ported | `module-04-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-05` | ported | `module-05-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-06` | ported | `module-06-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.module-07` | ported | `module-07-…` | the phrase its own description quotes | `_unrecorded_` |
  | `6.graduation` | ported | `graduation` | the phrase its own description quotes | `_unrecorded_` |
  | `6.start-bootcamp` | command-derived | `start-bootcamp` | "start the senzing bootcamp" | `_unrecorded_` |
  | `6.graduate-bootcamp` | command-derived | `graduate-bootcamp` | "graduate the senzing bootcamp" | `_unrecorded_` |
  | `6.bootcamp-feedback` | command-derived | `bootcamp-feedback` | "give senzing bootcamp feedback" | `_unrecorded_` |
  | `6.bootcamp-enforcement-setup` | client-adaptation | `bootcamp-enforcement-setup` | "install the senzing bootcamp enforcement hooks" | `_unrecorded_` |

  Sixteen rows: 12 ported bootcamp skills, 3 command-derived, 1 client-adaptation. The rows
  **are** the inventory. If the resolved Template_Release carries a different set of bootcamp
  skill directories, add or remove rows so there is exactly one row per skill directory present
  in the built Power *(R7 AC1, AC2)* — a skill in the Power with no row is a fail for this step.
  At Template_Release `0.5.1` the nine module directories are `module-00-…` through
  `module-07-…` including `module-03b-truthset-visualization`.

- **Pass:** every row activates the skill it names, and no row activates a different bootcamp
  skill or two at once.
- **Fail:** any row that activates nothing, activates the wrong skill, activates more than one,
  or has no phrase to state because the skill's description quotes none.
- **Outcome:** `_unrecorded_`

## Step 7 — A statement matching no command trigger phrase activates no command-derived skill

- **Verifies:** R9 AC5
- **Do:**
  1. In a fresh session with the Power installed, say something bootcamp-adjacent that quotes
     none of the three command phrases — for example, "what does entity resolution mean?".
  2. Observe which skills, if any, activate.
- **Pass:** none of `start-bootcamp`, `graduate-bootcamp`, or `bootcamp-feedback` activates.
- **Fail:** any one of the three activates on a statement that does not state its phrase.
- **Outcome:** `_unrecorded_`

## Step 8 — Progression follows the template order: onboarding → module 00 → module 03b → graduation

- **Verifies:** R7 AC3
- **Do:**
  1. From a fresh session, start the bootcamp and work forward through onboarding into module
     00, noting each transition the Power offers.
  2. Continue to module 03b and confirm it arrives at its place in the sequence rather than
     early or late.
  3. Reach graduation and confirm it is offered last.
- **Pass:** the Power presents onboarding, module 00, module 03b, and graduation in the
  Template_Release's progression order, and never offers a later module before the one it
  follows.
- **Fail:** any reordering, a skipped stage, or a module offered out of sequence.
- **Outcome:** `_unrecorded_`

## Step 9 — A1 check: whether Kiro loads hook definitions bundled under `dev.kiro/hooks/`

- **Verifies:** R6 AC7, assumption A1
- **Preconditions:** the Power installed; the workspace `.kiro/hooks/` holding **no**
  `senzing-bootcamp-*.json` file — run the installer's `remove --consent granted` first if one
  is there.
- **Do:**
  1. Confirm the installed Power contains `dev.kiro/hooks/senzing-bootcamp-session-start.json`
     and that the workspace hooks directory contains none of the Power's files.
  2. Open a fresh session in a bootcamp project — one with `config/bootcamp_progress.json`
     present — which is the `SessionStart` trigger that bundled definition declares.
  3. Look for any trace that Kiro read it: the hook name in Kiro's hook output or logs, or an
     execution error naming the unresolved `<ABSOLUTE_PYTHON>` placeholder. The Tier 3 copies
     ship placeholders rather than resolved paths, so a bundled hook that fires fails loudly —
     which is exactly what makes this observable.
  4. Write the answer into the record as `fires` or `does-not-fire`, with the evidence quoted.
- **Pass:** the answer is determined and recorded with its evidence. **Either answer is a
  pass.** The design does not depend on A1 being true: Tier 2's consented workspace install
  carries enforcement, and Tier 3 is never the sole delivery path for any behavior
  *(R7 AC12)*.
- **Fail:** the observation is inconclusive, or no answer is recorded.
- **Outcome:** `_unrecorded_`

## Step 10 — A2 / A4 check: every hook the Hook_Installer wrote fires on its declared trigger

- **Verifies:** R6 AC8, AC12, assumptions A2 and A4
- **Preconditions:** on the platform whose cell you are filling, `bootcamp-enforcement-setup`
  run through to `install --consent granted` against a bootcamp project.
- **Do:**
  1. Exercise each installed definition's trigger and confirm its script actually ran:
     `senzing-bootcamp-session-start` on `SessionStart` (open a fresh session),
     `senzing-bootcamp-checkpoint-tick` on `UserPromptSubmit` (send any prompt),
     `senzing-bootcamp-feedback-capture` on `UserPromptSubmit` (the same prompt),
     `senzing-bootcamp-stop-nudge` on `Stop` (let a turn end), and
     `senzing-bootcamp-write-gate` on `PreToolUse` (request a benign in-project write).
  2. On any failure, determine which of the two causes it was and record it: a path in the
     `command` string that did not resolve because `${PLUGIN_ROOT}` does not expand there
     (**A2**), or a script path that is no longer where the installer resolved it (**A4**).
- **Pass:** all five hooks fire on their declared triggers and their scripts execute.
- **Fail:** any hook that does not fire, or that fires and cannot execute its command. Record
  which cause applied. Neither cause is fixed by hand-patching a hook file: **A2** is already
  absorbed — the installer resolves both paths itself and the shipped asset carries only
  placeholders — and **A4** is one contract value, the `scripts-dir-strategy` set in
  `tools/bootcamp-transform/contract.yaml`. Switching it to the workspace-copy strategy and
  rebuilding makes the installer copy the ported script set into the workspace alongside the
  hook JSON and point every command at that copy.
- **Platform cells:**

  | Cell | Platform | Outcome |
  |---|---|---|
  | `10.linux` | Linux | `_unrecorded_` |
  | `10.macos` | macOS | `_unrecorded_` |
  | `10.windows` | Windows | `_unrecorded_` |

- **Outcome:** recorded per platform in the three cells above; a pass only when all three are a
  pass.

## Step 11 — A3 check: the `PreToolUse` matcher matches Kiro's actual write-tool names

- **Verifies:** R6 AC11, assumption A3
- **Preconditions:** `senzing-bootcamp-write-gate` installed and firing (step 10).
- **Do:**
  1. Request writes that exercise each of Kiro's file-write paths: create a new file, edit an
     existing one, and append to one.
  2. Capture the tool name each `PreToolUse` invocation reports — it arrives in the hook's stdin
     payload, and the write-gate script records what it saw.
  3. Compare every captured name against the `matcher` the installed
     `senzing-bootcamp-write-gate` definition carries. That pattern is written down in exactly
     one place — the `tool-names` value in `tools/bootcamp-transform/contract.yaml` — so read it
     from there rather than from a copy quoted here.
- **Pass:** every write-tool name Kiro reports is matched by that pattern, and the captured
  names are written into the record verbatim.
- **Fail:** any write-tool name the pattern misses — a write path the gate cannot see. The fix
  is the single `tool-names` contract value plus a rebuild; never a hand-patched hook file.
- **Outcome:** `_unrecorded_`

## Step 12 — A second Hook_Installer run leaves the workspace hooks directory identical

- **Verifies:** R6 AC9, R7 AC8
- **Do:**
  1. Run `install --consent granted` against the workspace, then record the name and SHA-256 of
     every file in `.kiro/hooks/`.
  2. Run the identical command again, same workspace and same interpreter.
  3. Compare the file set and the hashes, and read the second run's per-file report.
- **Pass:** the same file set with identical hashes, no duplicated hook entry inside any file,
  and the second run reporting every file `unchanged`.
- **Fail:** any hash change, any added or duplicated file, any duplicated hook entry, or any
  file the second run rewrote.
- **Outcome:** `_unrecorded_`

## Step 13 — Disclosure precedes every write, and removal deletes exactly what was written

- **Verifies:** R6 AC10, R7 AC7, AC9, AC10
- **Do:**
  1. Put a decoy hook file that is not the Power's into `.kiro/hooks/` — say
     `my-own-hook.json` — and record its SHA-256.
  2. Run `plan`. Confirm it printed the full path of every file it would write, and that it
     wrote nothing.
  3. Run `install --consent granted`. Confirm the files written are exactly the paths `plan`
     disclosed, and that every one of their names starts with `senzing-bootcamp-`.
  4. Run `remove` with no consent flag. Confirm it lists exactly those files as deletions, lists
     the decoy among the files it will leave alone, and deletes nothing.
  5. Run `remove --consent granted`.
- **Pass:** the disclosed set and the written set are the same set, disclosure came before any
  write, after removal exactly the `senzing-bootcamp-` files are gone, and the decoy is still
  there with its original hash.
- **Fail:** any file written that was not disclosed first, any Power file left behind after
  removal, or any change to the decoy or to another workspace hook file.
- **Outcome:** `_unrecorded_`

## Step 14 — The write-gate blocks an out-of-project write and a secret-bearing write

- **Verifies:** R7 AC5, AC6
- **Preconditions:** hooks installed, and a bootcamp project active with
  `config/bootcamp_progress.json` present — the scripts no-op without it.
- **Do:**
  1. Ask for a write to a path outside the bootcamper's project, such as a file directly in the
     home directory.
  2. Ask for a write into an in-project file whose content carries a credential — an API key,
     token, or password value.
  3. Ask for an ordinary in-project write carrying no secret.
- **Pass:** both offending writes are blocked mechanically with the gate's reason surfaced, and
  the ordinary write proceeds.
- **Fail:** either offending write lands, or the gate also blocks the ordinary write.
- **Outcome:** `_unrecorded_`

## Step 15 — Every ported script runs without a `${CLAUDE_PLUGIN_ROOT}` or import error

- **Verifies:** R10, R6 AC12
- **Preconditions:** on the platform whose cell you are filling, the Power installed and the
  interpreter the installer resolved into the hook commands available.
- **Do:**
  1. With that interpreter, run every `.py` under the installed Power's
     `skills/bootcamp-onboarding/scripts/` — the hook scripts through their normal entry point,
     the rest with `--help` or an import check.
  2. Confirm the same-directory module imports between them resolve, `import recap_checkpoint`
     and `import docker_lifecycle` among them.
  3. Search the installed tree for `${CLAUDE_PLUGIN_ROOT}`. There must be no occurrence.
  4. Run `skills/bootcamp-onboarding/scripts/optional_runtime.py` and confirm a missing optional
     runtime — no container runtime, no browser — is reported and exits successfully rather than
     failing.
- **Pass:** every script runs or imports cleanly, no `ImportError` or `ModuleNotFoundError`, and
  no `${CLAUDE_PLUGIN_ROOT}` anywhere in the installed tree.
- **Fail:** any import error, any surviving `${CLAUDE_PLUGIN_ROOT}`, or any script that exits
  non-zero because an optional runtime is absent.
- **Platform cells:**

  | Cell | Platform | Outcome |
  |---|---|---|
  | `15.linux` | Linux | `_unrecorded_` |
  | `15.macos` | macOS | `_unrecorded_` |
  | `15.windows` | Windows | `_unrecorded_` |

- **Outcome:** recorded per platform in the three cells above; a pass only when all three are a
  pass.

## Step 16 — The per-platform matrix is complete: nine cells, none blank

- **Verifies:** R6 AC12, R16 AC1
- **Do:**
  1. Read back all nine platform cells: `2.linux`, `2.macos`, `2.windows`, `10.linux`,
     `10.macos`, `10.windows`, `15.linux`, `15.macos`, `15.windows`.
  2. Confirm each carries an outcome that was produced by a run **on that platform**, not
     inferred from another.
- **Pass:** all nine cells carry an explicitly recorded outcome.
- **Fail:** any cell left `_unrecorded_`; a platform covered by a note such as "not tested" or
  "same as Linux" instead of an outcome; or one platform's result copied into another's cell. An
  unrecorded platform is a fail, not a blank.
- **Outcome:** `_unrecorded_`

## Step 17 — A space in the resolved interpreter or script path still invokes the ported script

- **Verifies:** R6 AC13, R16 AC3, AC4
- **Do:**
  1. Install the Power under a path containing a space — `C:\Users\Bob Smith\bootcamp` on
     Windows, `/Users/bob smith/bootcamp` on macOS, `/home/bob/my bootcamp` on Linux — and
     where you can, use an interpreter whose absolute path also contains a space, such as a
     virtualenv created inside such a directory.
  2. Run `install --consent granted` from that interpreter.
  3. Open one written hook file and read its `command`: both the interpreter path and the script
     path must be quoted, the command must name no bare interpreter, and it must contain no
     chaining operator, pipe, redirection, or shell builtin.
  4. Fire that hook and confirm the script actually executed.
- **Pass:** the hook fires and its script runs, with both paths quoted in the command string.
- **Fail:** the script does not execute — a "can't open file" or "is not recognized" error is
  the usual shape — either path is unquoted, the command names a bare interpreter, or the
  installer reports `E_SHELL_CONSTRUCT` or the validator reports `E_BARE_INTERPRETER`.
- **Outcome:** `_unrecorded_`

---

## When a step fails

Fix the cause at its single point of change, then re-run the failed step and everything
downstream of it:

- a wrong matcher or substitution → the `tool-names` or other value in `contract.yaml`, then
  rebuild;
- a hook that will not fire or a path that will not resolve → `install_hooks.py`, which owns
  interpreter and script resolution, then reinstall;
- ported content or prose → the Transformation_Contract or the `kiro-owned` templates, never the
  generated output under `powers/senzing-bootcamp/`.

Two things are never the fix: editing a record so a fail reads as a pass, and hand-patching a
generated file. Both leave the next release with a checklist that verifies something the build
does not produce.
