# Tier 1 ground rules — the rules the hooks would have enforced

These are **instructions to follow, not documentation to read out**. They are the Tier 1
baseline of the three-tier hook parity strategy: every behavior a template hook enforced
mechanically is stated here as a rule, so the bootcamp is complete and correct with **zero
hook definitions installed** *(R7 AC4)*.

Tier 2 (the consented workspace hook install performed by `bootcamp-enforcement-setup`)
restores mechanical enforcement of the write-location and secret rules. It does not replace
these rules — it backs them. When no hooks are installed, enforcement is advisory and you are
the enforcement.

Each rule carries a marker comment. The markers are the machine-checkable link between the
parity coverage map (`../hook-parity-coverage.json`) and the instruction text, so no hook
behavior can be dropped silently.

---

## Write location — every write lands in the bootcamper's project

<!-- SENZING-BOOTCAMP-TIER1:write-location -->

Enforced mechanically by `write-gate.py` on `PreToolUse` when Tier 2 is installed; advisory
otherwise. Preserves **INV-200**.

- Every file the bootcamp creates or edits — progress state, recap notes, feedback,
  exercise code, data files, notebooks — is written **inside the bootcamper's project
  directory**, the workspace they opened to run the bootcamp.
- Never write into the installed Power directory. It is upgrade-managed: content written
  there is lost on the next Power version, and a Bootcamper cannot find it afterwards.
- Never write above the project root. No absolute paths outside the project, no `../`
  escapes, no home-directory dotfiles, no system or temp locations for anything the
  Bootcamper is expected to keep.
- The bootcamp's own state files are project-relative by definition:
  `config/bootcamp_progress.json`, the recap checkpoint, and
  `docs/feedback/SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md`.
- If a step seems to require writing outside the project, stop and ask before writing. A
  blocked write is a recoverable annoyance; a write into the wrong tree is silent data loss.

## Secrets — never into a file the bootcamp writes

<!-- SENZING-BOOTCAMP-TIER1:secrets -->

Enforced mechanically by `write-gate.py` on `PreToolUse` when Tier 2 is installed; advisory
otherwise. Preserves **INV-109**.

- No credential, API key, token, password, license key, or connection string carrying a
  password goes into any file the bootcamp creates — not into exercise code, not into a
  config file, not into a recap, a progress file, or a feedback entry.
- Secrets belong in the environment (an environment variable, or a local, git-ignored file
  the Bootcamper owns and edits themselves). Reference them by name in bootcamp content;
  never by value.
- Never echo a secret back into the transcript to "confirm" it, and never copy one from the
  Bootcamper's message into a file on their behalf.
- When an exercise needs a secret, describe the variable the Bootcamper must set and let
  them set it. Placeholders in committed content stay placeholders.

## Containers are stopped, never removed

<!-- SENZING-BOOTCAMP-TIER1:container-stop-not-remove -->

The template enforced this at `SessionEnd`. **Kiro has no `SessionEnd` trigger**, so this is
an advisory rule you apply at every close-out point *(R7 AC13)*. Preserves **INV-101**.

- Stop containers. Do not remove them. `docker stop <name>` — never `docker rm`, never
  `docker compose down`, and never anything carrying `-v` or `--volumes`.
- The Bootcamper's loaded records, resolved entities, and configuration live inside that
  container. Removing it discards hours of their work and forces a reload from module 02.
- The same rule applies when a container looks stale, misnamed, or duplicated. Report what
  you found and ask; do not clean up on their behalf.
- At the end of a working session, and at every module close, stop what you started and say
  plainly what is still stopped-but-present, so resuming is obvious.

## One closing 👉 question per turn — and never a second

<!-- SENZING-BOOTCAMP-TIER1:closing-question -->

The template enforced this with a **blocking** `Stop` hook (`stop-nudge.py`). **Kiro's `Stop`
trigger cannot block**, so this is a permanent, documented partial-parity gap and the rule is
advisory *(R7 AC14)*.

- End every bootcamp turn that expects a response with **exactly one** question, prefixed
  with 👉, on its own line, as the last thing in the turn.
- **Exactly one.** Ask one thing at a time. Do not stack two questions, do not append a
  second 👉 line, and do not re-ask a question the Bootcamper already answered.
- If a turn already ends with a 👉 question, that turn is finished. Duplicate closing
  questions are the single most common complaint about the bootcamp, so when in doubt, stay
  silent rather than adding one. Silence is the safe failure direction here; a doubled
  question is not.
- Turns that close a module, hand off to another skill, or simply report a result and need no
  answer take no 👉 question.
- This rule holds in every skill, in every module's close phase, and in graduation — not only
  in onboarding.

---

## Reduced capability is normal

<!-- SENZING-BOOTCAMP-TIER1:optional-runtime -->

Only the Python interpreter that runs the bootcamp scripts is required. Any other runtime —
Docker for the SDK modules, a browser for the truth-set visualization — is optional. When one
is missing, say what is unavailable, say what the Bootcamper can still do, and continue. Never
wedge a session on a missing optional runtime *(R16 AC7)*.

- **Check, don't guess, and don't guess late.** `optional_runtime.py` sits beside the other
  bootcamp scripts and reports what is available here, exiting successfully whatever it finds:
  `<python> ${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/optional_runtime.py`
  (add `--json` for the same answer as data). Run it before promising a capability rather than
  after failing at one. It cannot fail, so running it costs nothing.
- **No container runtime** — no `docker`, no `podman`, no Apple `container` CLI. The SDK setup
  module's own platform routing decides whether a container is the required path for this
  Bootcamper's operating system and language; where it is, say so plainly, offer to help install
  one, and keep moving through the module's prose. Everything that needs no engine of its own is
  untouched. Do not silently skip a module, and do not stall the session waiting for Docker.
- **No browser.** The truth-set visualization server needs only Python: it serves a URL the
  Bootcamper opens in whatever browser they already have. Only the *headless screenshot capture*
  needs a browser, and without one the recap keeps the HTML link in place of the images.
  `capture_screenshots.py` prints every location it searched — relay that, rather than guessing
  at a cause or telling them to install something they already have.
- **Say it once.** Name the missing runtime, name what still works, then continue. Repeating it
  every turn reads as a wall, and it is not one.
- **A missing optional runtime is never a block.** The bootcamp's scripts already work this way:
  they warn and continue, and the session-start and session-end scripts return success whatever
  the container CLI does. Do not "help" by treating a missing runtime as a failed step, and never
  let a hook exit 2 over one — exit 2 is Kiro's *block* status on `PreToolUse`,
  `UserPromptSubmit`, and `PreTaskExec`, so an absent Docker spelled that way would block every
  turn instead of reducing one module.

## Where these rules land in the built Power

The design's Tier 1 placement points at the ported bootcamp prose:
`bootcamp-onboarding/ground-rules.md` for the write-location, secret, container,
and closing-question rules, plus each module's close phase for the closing-question rule.
Those ported files carry the same rules as bootcamp prose. This file is the **Kiro-owned
carrier** of the same rules: it exists in the Power whatever the resolved Template_Release
contains, it is preserved verbatim across updates (`owner: kiro`), and it is the location the
parity coverage map declares and the reachability check verifies.
