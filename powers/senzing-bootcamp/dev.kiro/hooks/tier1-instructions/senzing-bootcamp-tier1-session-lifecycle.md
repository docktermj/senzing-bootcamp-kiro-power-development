# Tier 1 session lifecycle — resume, per-turn checkpoint, feedback watch, close-out

Instructions to follow, not documentation to read out. These are the session-lifecycle
behaviors the template drove from hooks, restated so they hold with **zero hook definitions
installed** *(R7 AC4)*. Marker comments link each behavior to the parity coverage map
(`../hook-parity-coverage.json`).

**One guard governs all of it.** Every ported hook script begins by looking for
`config/bootcamp_progress.json` in the workspace and exits without acting when it is absent.
That is what makes an installed hook set safe in unrelated Kiro sessions. The same guard
applies to you at Tier 1: **outside a bootcamp project, none of the behaviors below apply.**
Do not create `config/bootcamp_progress.json` to make them apply.

---

## Resume on session start

<!-- SENZING-BOOTCAMP-TIER1:resume-on-session-start -->

Template `SessionStart` → `session-start.py`. Kiro has a direct `SessionStart` equivalent, so
Tier 2 restores this mechanically; this is the baseline.

At the start of a bootcamp session, before doing anything else, read
`config/bootcamp_progress.json` and let its **contents** decide — not merely whether the file
exists:

- **No file** → start onboarding from the beginning.
- **A file recording no module** (empty, `{}`, malformed, or `current_module` null or blank)
  → also start onboarding from the beginning, and do it **silently**. This is the normal state
  between the preface's project setup and Bootcamp preparation's final write, not a corruption
  to report.
- **A file with a `current_module`** → resume there. State which module is being resumed and
  what was completed, then continue from that module's entry point.

Never restart a Bootcamper who has progress recorded, and never announce "no progress found"
at a Bootcamper who is simply between the two early writes.

## Per-turn recap checkpoint

<!-- SENZING-BOOTCAMP-TIER1:per-turn-checkpoint -->

Template `UserPromptSubmit` → `checkpoint-tick.py`. Kiro has a direct `UserPromptSubmit`
equivalent, so Tier 2 restores this mechanically; this is the baseline.

Keep the recap checkpoint current as the session runs, rather than reconstructing it at module
close:

- After each meaningful exchange, record what was covered, what was decided, and what the
  Bootcamper produced — in the checkpoint the recap tooling maintains, inside the project.
- Keep entries short and factual. The checkpoint is working state for the recap, not a
  transcript.
- This per-turn tick is also what bounds the loss from Kiro having no `PreCompact` trigger:
  the checkpoint is never more than one turn behind, so a compaction cannot discard more than
  one turn of recap material. See `senzing-bootcamp-tier1-recap-folding.md`.

## Feedback watch

<!-- SENZING-BOOTCAMP-TIER1:feedback-watch -->

Template `UserPromptSubmit` → `feedback-capture.py`. Kiro has a direct `UserPromptSubmit`
equivalent, so Tier 2 restores this mechanically; this is the baseline.

Watch every Bootcamper message for feedback about the bootcamp itself — confusion, a broken
step, a wrong instruction, a suggestion, praise:

- When you see it, follow the capture workflow in
  `bootcamp-onboarding/feedback.md` rather than improvising a format: gather the
  feedback one 👉 question at a time, triage whether the issue is in this Power or in the
  Senzing MCP server, and **APPEND** (never overwrite) a formatted entry to
  `docs/feedback/SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md`, creating that file with its header if
  it does not exist.
- Record every entry locally whatever the triage says. Only when the issue is in the **MCP
  server** may you additionally offer — once, showing the exact message first — to forward it
  through the MCP server's `submit_feedback` tool. Never send anything external without an
  explicit yes.
- Then return the Bootcamper to exactly where they left off. Feedback is an interruption, not
  a detour.
- The Power version recorded in a feedback entry comes from the Power's own `plugin.json`.

## Session close-out

<!-- SENZING-BOOTCAMP-TIER1:session-close-out -->

Template `SessionEnd` → `session-end.py`. **Kiro provides no `SessionEnd` trigger**, so this
behavior is Tier 1 only and its gap is documented *(R7 AC13)*. There is no hook definition for
it at any tier.

Because nothing fires automatically when a session ends, close out **explicitly** at the
points you control — when the Bootcamper says they are stopping, when a module closes, and
before any long pause:

1. Fold the recap checkpoint into the durable recap (see
   `senzing-bootcamp-tier1-recap-folding.md`).
2. Stop any container the bootcamp started — **stop, never remove** (INV-101; see
   `senzing-bootcamp-tier1-ground-rules.md`).
3. Write the Bootcamper's position to `config/bootcamp_progress.json` so the next session
   resumes correctly.
4. Say, in one short paragraph, what was completed, what is stopped-but-present, and what
   comes next.

The residual gap is timing, not content: an abrupt session end with no close-out leaves the
per-turn checkpoint as the recovery point instead of a folded recap. That is the loss the
per-turn tick above is sized to bound.
