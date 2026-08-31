---
name: graduation
description: 'Bootcamp graduation: generate the recap PDF and a production-ready project. Use when the bootcamper finishes the last module (Module 7) and accepts the graduation offer, or says "graduate", "run graduation", or "finish the bootcamp".'
license: Apache-2.0
compatibility: Requires the Senzing MCP server and Docker.
metadata:
  author: Senzing
  version: 0.5.1
  templateRelease: 0.5.1
  templateSkill: graduation
---

# Bootcamp graduation

> **MCP grounding (mandatory — applies to this entire skill).** Every Senzing fact you present —
> SDK method and attribute names, config options, error codes, and entity-resolution specifics —
> MUST come from the Senzing MCP tools, never from training data, memory, or speculation.
> **Pre-response checklist:** if a reply contains any Senzing specific, you MUST have called an MCP
> tool this turn to obtain it; if not, stop and call it first. This has the same precedence as a ⛔
> gate. The full rule and tool routing are the "MCP-first invariant" in
> `../bootcamp-onboarding/ground-rules.md`.

Bootcamp graduation turns a completed bootcamp into two things the bootcamper keeps: a
professional **recap PDF** and a clean **`production/` project** they can
build on. Bootcamp graduation is the required, terminal module of the bootcamp. Load this
skill when the bootcamper accepts the graduation offer after the last module
(Module 7), or asks to "graduate" / "run graduation".

Follow `../bootcamp-onboarding/ground-rules.md` throughout: `🛑`/`⛔` are internal
directives (never rendered); one 👉 question ends each yielding turn; keep all
files project-relative; all Markdown goes under `docs/`, all code under `src/`.

Bootcamp graduation is non-blocking: every artifact step warns-and-continues on failure,
and the recap guarantee at the end always produces a valid PDF. Steps that create
the `production/` project ask for confirmation before large or destructive
actions.

Bootcamp graduation is the terminal bookend module. Like every module it opens with the module-start
apparatus — journey map, before/after framing, a step overview, and an estimated time — adapted to
a terminal module (INV-102; see "Bootcamp graduation preface" below), then the model/effort nudge. Because no
next-module transition applies, it shows no `✅ Module complete` line and no transition question,
and it ends on the terminal END OF SENZING BOOTCAMP banner (INV-057). (Bootcamp graduation is NOT
apparatus-exempt — contrast the exemptions for Bootcamp preparation (INV-075) and Module 0
(INV-078).)

## Bootcamp graduation banner (show first, exactly once)

Display this banner verbatim as the FIRST output of graduation, before any step.
It bookends the bootcamp: the WELCOME banner marked the start, this marks the
finish. Show it at most once per graduation.

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎓🎓🎓  BOOTCAMP GRADUATION  🎓🎓🎓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Bootcamp graduation preface (after the banner, before the model/effort prompt)

Like every module, graduation opens with the module-start apparatus (INV-029–032), adapted to a
terminal module — no next-module transition. Present these in order, right after the banner and
before the model/effort prompt. First read `config/bootcamp_preferences.yaml` (`selected_modules`)
and `config/bootcamp_progress.json` (`modules_completed`) to render the journey map. Honor the
active verbosity preset (INV-011/INV-012): suppress the explanatory parts under `minimal`, keep
them to one line under `concise`. Refer to modules by name, never number (INV-079).

1. **Journey map.** List the selected modules by name, every one marked ✅ (all experienced), with
   **Bootcamp graduation** marked 🔄 as the current, final stage — nothing ⬜ after it.
2. **Before / After.** Before: every module is complete and your data is resolved, but your work
   still lives in the bootcamp workspace. After: you keep two things — a professional recap PDF
   (`docs/bootcamp_recap.pdf`) and a clean, production-ready `production/` project to build on.
3. **What we'll do.** A brief numbered overview of graduation's steps: (1) note anything that
   tripped us up this session, so the bootcamp itself improves, (2) normalize the `docs/`
   Markdown and render the recap PDF keepsake, (3) build the `production/` project, (4) create a
   silent revisit/resume bundle — a database backup plus a return guide — so you can come back
   later (INV-094), and (5) close with the END OF SENZING BOOTCAMP banner.
4. **Estimated time.** Give an honest, range-based estimate caveated per INV-096 — e.g.
   "⏱️ Roughly 5–15 minutes, depending on your workstation, the database backup size, and PDF
   rendering speed." If no meaningful estimate is possible, say "hard to estimate" rather than
   inventing a number. Suppress under `minimal`; one line under `concise`.

Bootcamp graduation is terminal, so it has no "what's next / next module" line and no `✅ Module complete`
transition — it ends on the END OF SENZING BOOTCAMP banner (INV-057). What the bootcamper carries
forward is the recap PDF and the `production/` project.

## Best-value model/effort prompt

After the preface, surface the best-value model/effort before the heavier graduation work.
Bootcamp graduation is correctness-critical: **Opus 5 + high effort**.

⛔ **This is unconditional — no preference to read, no mode to choose (INV-137).** There is no
`model_guidance` key; do not read one, and do not honor a stale one left in an old preferences file.

⛔ **Whether to ask is decided the same way as at any module start** — compare graduation's
recommendation against **what the bootcamper is running right now**, not against the previous
stage's recommendation (`../bootcamp-onboarding/ground-rules.md` → "Module start banners and
transitions"). Bootcamp graduation shares its recommendation with Query, Visualize and Discover, so a
bootcamper arriving on Opus 5 at high effort is **already there**: give them the one-line statement
and go straight into Step 1. Do not assume graduation is always a step up — it is not, and asking a
bootcamper to switch to the model they are already running is the pointless question INV-006 and
INV-012 forbid. Name only the dial that differs — **including in the answer hint**, where `{dial}`
resolves to "model", "effort", or "model and effort" to match the stem — and when the recommendation
sits *below* their current setting, say so in the question itself.

When it **does** differ, end this turn with a single 👉 yes/no question — its own turn, not combined
with another 👉:

On the **Kiro CLI**, pin the switch question verbatim:

> 👉 **Would you like to switch to Opus 5 in the model picker and high in the effort picker for graduation?** (Recommended for best value; reply no to keep your current {dial}.)

In **Kiro, Kiro on the web, or the Kiro IDE** (or an unknown interface), pin
the intent-based equivalent (INV-098), naming the one interface the bootcamper is on — "in your
Kiro surface" only when it cannot be determined (INV-158):

> 👉 **Would you like to switch to Opus 5 at high reasoning effort for graduation?** (Recommended for best value; set it with the model and effort controls in {Kiro | Kiro on the web | the Kiro IDE}; reply no to keep your current {dial}.)

The switch question ends this turn. **On yes, read what the dial is actually set to before you
compose the reply** (INV-236) — the question hands the bootcamper a command, so many will run it in
the same turn as their yes, which is the natural response to being shown a command rather than an
edge case. Three shapes, decided by the live setting rather than by the yes alone:

1. **The dial is not yet set** — preface the reply turn with a one-line statement telling the
   bootcamper how to make the change (run the `/model`/`/effort` commands in the Kiro CLI, or
   use the model and reasoning-effort controls in Kiro / Kiro on the web / the Kiro
   IDE), then end the turn on this pinned confirmation gate (its question verbatim,
   INV-056/INV-069 — only the answer hint adapts) — do NOT start the graduation work yet:

   > 👉 **Are you done modifying the model and effort?** (Reply yes once you've set your model and effort; reply no if you need more time.)

   Run the Pre-checks and the first graduation step on the turn **after** the bootcamper confirms; if
   they need more time, acknowledge and wait, then continue — do not re-ask this gate (ask-once,
   INV-006).

2. **The dial is already at the recommended value** — acknowledge it rather than instructing it
   ("You're on `/effort high` already: that's graduation's recommendation."), then run the Pre-checks
   and the first step **in the same turn**, with no confirmation gate. Nothing is left to confirm
   (INV-006/INV-012).

3. **The dial is already at a different value** — state what is in force and leave it there:
   "You're on `/effort xhigh`; graduation recommends `high`, and running higher is fine — it simply
   costs more, nothing else." Then run the Pre-checks and the first step in the same turn. ⛔ **Never
   re-instruct the recommended command once the bootcamper has set a different value** — they
   answered with an action, and the table is a recommended floor, not a ceiling.

In a non-CLI interface, shapes 2 and 3 name the **setting** rather than a command — "you're already
on Opus 5 at high reasoning effort" (INV-158).

On **no**, continue straight into the graduation work the same reply turn: run the Pre-checks and
proceed to the first step, ending that turn on its own 👉 question.

⛔ The confirmation gate follows a **yes that still needs one** — shape 1 above — and nothing else.
Never after a decline; never when no switch question was asked because the recommendation already
matched; and never in shapes 2 and 3, where the bootcamper has already set the dial and the gate
would ask what the transcript has answered. In all of those cases the one-line statement is followed
straight by the Pre-checks and the first step, in the same turn. You never change the session
yourself; only the bootcamper can, which is why the switch is offered as a question rather than
performed. See `../../docs/model-selection.md`.

## Pre-checks

Gather context before any step. Do this silently.

1. **Read preferences:** load `config/bootcamp_preferences.yaml` and extract, **by these exact key
   names**:

   | Key | Written by | Notes |
   |---|---|---|
   | `name` | Bootcamp preparation (detected, never asked — INV-134) | the certificate name; see pre-check 4 |
   | `programming_language` | Bootcamp preparation (INV-133) | **not** `language` |
   | `database_type` | SDK setup Step 7 | `sqlite` or `postgresql`, lowercase; **not** `database` |
   | `path` | Bootcamp preparation | `core`/`customized`; older sessions may store this as `track` |
   | `selected_modules` | Bootcamp preparation | drives the journey map (INV-076) |
   | `integration_targets` | Module 1 Phase 2 Step 10a (INV-097) | absent is normal — see pre-check 1a |
   | `deployment_target` / `cloud_provider` | Module 1 Phase 2 Step 10a (INV-097) | absent is normal — see pre-check 1a |

   The data-source registry is **`config/data_sources.yaml`**, its own file (INV-050) — not a
   preferences key.

   ⛔ **Use the names in that table verbatim.** They are the names the writing modules actually
   write, and a reader that invents its own is indistinguishable from a bootcamper who never
   answered: SDK setup says so in its own words — *"a different key name is the same failure as no
   key at all"*. Until 2026-07-29 this step read `language`, `database` and `data_sources`, which
   nothing has ever written, so every consumer below silently got nothing.

   **1a — what the Module 1 answers are for (INV-097).** `integration_targets` and
   `deployment_target`/`cloud_provider` are the bootcamper's own answers to two pinned 👉 questions
   asked in Module 1 Phase 2 Step 10a — what the resolved results must talk to, and where this is
   going to run. Bootcamp graduation is the only place they can still change anything, because the
   `production/` project **is** the thing being deployed: Step 3 stamps them into the container and
   environment templates, Step 4 into the README and the migration checklist's Deployment section,
   Step 5 into the graduation report.

   ⛔ **Never ask for them here.** They are asked once, in Module 1 (INV-006/INV-097), and Module 1
   may not even have run under a Customized path (INV-076) — so **absent is normal, silent, and
   changes nothing**: every step below states its no-value behavior, and each simply stays generic.
   An empty value is the same as absent.
2. **Read progress:** load `config/bootcamp_progress.json` and extract `modules_completed`.
3. **Fallback — and distinguish a missing file from a missing key.** They are different failures
   and only one is the bootcamper's business:
   - **A file is missing or unparseable** → tell the bootcamper, then ask for the programming
     language and database type with one 👉 question at a time; use sensible defaults for the rest
     (path unknown, data sources none).
   - **A file is present but a key is absent** → do **not** announce it and do **not** ask. An
     absent `database_type` means SDK setup Step 7 did not record the choice — a **Power defect**,
     not a bootcamper outcome — so note it internally so it surfaces in the Step 0 retrospective,
     exactly as Data collection does for the same key
     (`../module-04-data-collection/SKILL.md` → the SQLite volume warning), and carry on with the
     value indeterminate. `integration_targets` and `deployment_target` are the exception: absent is
     **normal** and silent (see 1a).

   Either way graduation continues — nothing here blocks (INV-048).
4. **Check the name is certificate-quality (INV-113).** `name` is auto-detected during Bootcamp
   preparation and never asked (INV-134), so it can be absent or unsuitable. **The governing test is
   the whole test:** treat it as **unusable** when it is missing, empty/whitespace, or **clearly not
   a person's display name**. The cases below are *examples* of that test, not an exhaustive list —
   a value that is plainly not a display name is unusable even if it matches none of them:

   - a known system/service account (`root`, `ubuntu`, `ec2-user`, `admin`, `runner`);
   - a value containing no letters;
   - an email address or `@handle`;
   - **a bare single-token handle** — one lowercase word with no space, e.g. `docktermj`, `jsmith42`,
     `mdockter`. This holds whether or not it matches the OS username: a handle is a handle either
     way, and requiring it to equal the OS username let one through onto a certificate.
   - **a name the recap PDF cannot print** — one written in a script the generator's built-in fonts
     do not carry (Chinese, Japanese, Korean, Cyrillic, Arabic, Hebrew, Greek, Devanagari, Thai …).
     The PDF is set in Latin-1 core fonts, so those characters are dropped rather than rendered, and
     `generate_recap_pdf.py` warns on stderr naming them (INV-143 forbids printing them as `?`, which
     it used to). Do **not** transliterate the name yourself — how it should be spelled in Latin
     script is the bootcamper's decision, which is exactly what the question below asks. Ask it, and
     record their answer; if they decline, the certificate reads "Bootcamper" and graduation
     continues (INV-048).

   Be conservative in the other direction: a plausible real name must **never** trigger the
   question, because asking someone their name right after correctly detecting it is its own defect
   (INV-006). A value containing a space and normal capitalization ("Ada Lovelace") is a display
   name; a single lowercase token is not.

   When it is unusable, ask this once, pinned verbatim (INV-056), **before** Step 1 renders the PDF:

   > 👉 **What name would you like printed on your Certificate of Completion?**

   Persist the answer **in both places**, or the certificate prints the value you just rejected:

   1. As `name` in `config/bootcamp_preferences.yaml`, so a re-render or a resumed session never
      asks again (INV-006). The generator reads this **first** for the certificate — it is the
      Bootcamper's answer, and it outranks anything detected earlier (INV-170).
   2. As the recap's `**Bootcamper:**` preamble line in `docs/bootcamp_recap.md`, written by
      **module-completion Step 2a, at the first module that appends a recap section** (INV-226 —
      a citation naming substeps MUST NOT omit the one that creates the artifact) — Entity
      Resolution Concepts when it is selected, otherwise Discover the Business Problem — from the
      `name` detected during Bootcamp preparation. (⚠️ Bootcamp preparation itself writes **no**
      recap: it is apparatus-exempt (INV-092) and writes only the two `config/` files. It detects
      the name; it does not put it in the recap.) Leaving the line unamended means
      the recap a reader opens still shows the rejected handle, and any re-render driven from the
      recap alone reproduces it. Amending a preamble meta line is not a rewrite of a completed
      module section, so the append-only rule (INV-085) does not forbid it.

      ⛔ **If the `**Bootcamper:**` line is absent, WRITE it — do not assume an edit target.** A
      recap whose header was never created has no line to amend, and passing over the amend without
      saying so is how the certificate ends up printing a placeholder. Write the full preamble if
      none exists,
      per `../bootcamp-onboarding/module-completion.md` Step 2a, above the first `## ` section; and
      note the recovery, because a header written at graduation means some module skipped 2a and
      that is worth knowing.

   ⛔ **Both, not either.** Preferences alone once printed `docktermj` on a signed certificate at
   exit 0 with 99% content retention and no warning, because the generator read only the recap line
   — the pre-check asked the question, the Bootcamper answered, and the answer was discarded
   (INV-065). The generator now prefers preferences and prints a `NOTE:` on stderr when the two
   disagree; treat that note as work still to do, not as confirmation.

   If the bootcamper declines or gives nothing usable, continue
   — graduation is non-blocking and the generator still renders a certificate, warning on stderr
   that it used the "Bootcamper" placeholder. **Never print a rejected system-account value** on the
   certificate or into the recap (INV-065); ask, and use the answer.

## Step 0: Session retrospective (self-observed feedback)

Run this **before** Step 1 renders the recap PDF. Every feedback entry the Power has ever
collected exists because the *bootcamper* noticed something and said so. That sensor is blind to
the most valuable class of defect: **the kind that looks like it worked** — a wrong field name that
renders blank, a tool that behaves differently than documented, a workaround you applied so
smoothly nobody registered it as friction. This step is the Power's second sensor, and it does not
depend on the bootcamper noticing anything.

Review **this session** for four categories:

- **False starts** — an approach you began and abandoned.
- **Errors** — commands, compiles, or tool calls that failed and had to be retried differently.
- **Course corrections** — a stated plan or hypothesis that measurement disproved.
- **Learnings** — anything you discovered about the environment, the SDK, or the MCP tools that is
  not in the Power's documentation.

⛔ **The inclusion test is recurrence, not embarrassment: "would this happen to another
bootcamper?"** A one-off typo is noise. A documented tool that behaves differently than documented
is signal — file it. Do not soften a finding to look better, and do not manufacture findings to
look thorough; if the session genuinely produced none, write nothing and say so in one line.

⛔ **Sweep for these three; do not rely on remembering them.** The four categories above are
recalled from the session, and by graduation the session may have crossed one or more compaction
boundaries — so the most valuable findings are exactly the ones least likely to still be in context.
Go and look at what the project now contains:

1. **Withdrawn or changed mappings.** Compare the mapping you finished with against what you first
   proposed — `docs/data_source_evaluation.md`, the mapper code under `src/`, and the match-key
   audit's outcome in Data processing. A field you routed to payload after the audit, or a feature
   you stopped mapping two sources onto, is a reversal worth filing.
2. **Corrected scoring or accuracy code** you wrote, including any correction that *lowered* a
   number you had already reported. That one matters most: it means an earlier figure was wrong and
   something may have been decided on it.
3. **Abandoned proposals** — a change you recommended and then dropped after checking the Entity
   Specification or the MCP reference. Cheap when it happens, invisible afterwards.

**Do not re-file what is already there.** `ground-rules.md` → "Reversed decisions: file them when
they happen" means some of these are already in the file from during the run. Read the existing
entries first and skip any finding already recorded; add to an entry only if you now have evidence
it lacked.

For each finding, append a `## Improvement:` entry to
`docs/feedback/SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md` using the **exact template** in
`../bootcamp-onboarding/feedback.md` Step 3 (append only — never rewrite the file), with:

- **`Source:` `self-observed (assistant retrospective)`** — not `bootcamper-reported` (INV-116).
  A maintainer must be able to tell the two apart; they deserve different weight.
- **`Module:`** the module where the friction occurred, even though you are filing at graduation.
- **`Routing:`** the Step 2b triage verdict (`plugin` | `mcp-server` | `both` | `host` | `unclear`, INV-248) with its
  one-line reason. Retrospective findings skew toward MCP-server issues — a tool behaving differently
  than documented is exactly the defect class a bootcamper cannot report — so triage each one rather
  than defaulting it to `plugin`.
- **`Upstream:`** for an `mcp-server`/`both` verdict, offer the forward **once** per
  `../bootcamp-onboarding/feedback.md` Step 3c: show the exact message, strip anything identifying
  (INV-065), and send only on a yes. Batch the offer — one question covering all such findings, not
  one per finding, so the retrospective stays a single non-blocking step. On decline or failure,
  record it and continue; every entry is saved locally regardless (INV-015).
- The same **Context when reported** block, describing what *you* hit rather than what the
  bootcamper saw.

Then **verify it landed**: re-read the file and confirm each entry is present, exactly as
`../bootcamp-onboarding/feedback.md` Step 3b requires. An unwritten retrospective is worse than
none, because nobody is watching for it.

Constraints:

- **Non-blocking.** A retrospective that fails, finds nothing, or cannot review the session must
  never hold up graduation. Report and continue.
- **Not a gate.** Announce it in one line — "📝 Filed N self-observed notes to
  `docs/feedback/SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md`." — and continue in the same turn. This is
  not a 👉 question, and the bootcamper is never asked to author or approve it.
- **No feedback-flow banners.** The entry/exit banners in `../bootcamp-onboarding/feedback.md`
  mark the boundary of the *bootcamper-driven* feedback flow (INV-074). This is a graduation step,
  not that flow — do not present them.
- **PII boundary.** Same rule as the recap (INV-065): no hostname, username, IP address, or other
  personal/host identifier. OS/architecture, plugin version, and model/effort are diagnostic
  context and are permitted — the line is personal/host identifiers, not environment facts.

## Step 1: Finalize the recap and render the recap PDF

The recap is the crown-jewel deliverable. Produce it before the `production/`
project so the recap PDF always exists.

A finished-recap sample ships with the Power at
`${PLUGIN_ROOT}/docs/examples/bootcamp_recap.example.pdf` (skill-relative
fallback: `../../docs/examples/bootcamp_recap.example.pdf`). You may point the
bootcamper to it so they see what theirs is about to look like — a non-blocking
statement, never a 👉 question or gate, and it adds no turn.

### 1a. Reconcile the recap

Confirm `docs/bootcamp_recap.md` has a name-based `## {Module name}` section for **every** module
in `modules_completed` — match by module **name**, not a catalog number. Iterate the full
`modules_completed` list in its recorded (experienced) order and, for any completed module with no
matching section, append one now from the module's artifacts and progress data, following
`../bootcamp-onboarding/module-completion.md` (append only, never rewrite existing sections, never
re-sort into catalog order). The module flow records each module it completes — including
`entity_resolution_concepts` (Module 0, when it ran — INV-092) and both `system_verification` and
`truthset_visualization` when the Truth Set visualization ran (each self-recording with its own
`modules_completed` entry and recap section, INV-086/INV-087/INV-092) —
so this reconcile is normally a **no-op**; its job is to **recover** a section missing because a
module was interrupted before its completion step ran (e.g. synthesize a missing
`truthset_visualization` section from its artifacts). If `docs/bootcamp_recap.md` does not exist at
all, reconstruct it from `config/bootcamp_progress.json` and the files each module produced.

**Backfill the End-of-Module Summary blocks (before rendering).** Every module section's
**End-of-Module Summary** must carry three labeled blocks — `**What you accomplished:**`,
`**Files produced:**`, `**Why it matters:**` (INV-103; the "Bootcamper's takeaway" line stays
optional). Check each section and add any that is absent, drawn from that module's own recorded
content: **Actions Taken** and the section's own prose say what was accomplished, the paths it names
(plus the files the module actually produced) give **Files produced**, and the module's purpose in
`../bootcamp-onboarding/onboarding-flow.md` gives **Why it matters**. Where the summary is already
there as an unlabeled paragraph, keep the paragraph and add the labeled blocks — adding the labels a
subsection was always required to carry is not a prose rewrite (INV-085), and the run this was
found in had summaries whose three blocks were simply absent.

**Write each block in its required shape.** `**What you accomplished:**` and `**Files produced:**`
are **lists**: put the label on its own line and one bullet per accomplishment, and one bullet per
file with a short "— what it is" gloss. `**Why it matters:**` is **prose**: it stays inline after its
label. This is the shape `../bootcamp-onboarding/module-completion.md` prescribes and the shape
`${PLUGIN_ROOT}/docs/examples/bootcamp_recap.example.md` (skill-relative fallback:
`../../docs/examples/bootcamp_recap.example.md`, INV-252) shows. It is not cosmetic: the PDF renders bullets as
bullets and inline text as one wrapped paragraph, so a list written inline — the comma-joined run of
paths being the usual way it happens — reaches the keepsake as a paragraph and cannot be recovered
later. The shape chosen here is the shape the bootcamper keeps.

⛔ **Never invent content to fill a label.** If a module's own record does not support a block, write
what is true — "(no files — {reason})" for a module that produced none — or leave that one block out
and let the generator mark it "(not recorded)". A keepsake that overstates what the bootcamper did is
worse than one that shows a gap (INV-065's principle: never fabricate to fill a field). Like every
graduation step this is non-blocking: warn and continue.

`--check` (Step 1b) reports these gaps per module, so run it after this backfill and re-render if it
still finds any — the PDF renders every absent block as "(not recorded)" rather than dropping it, so
a gap is visible on the page but should not survive to the bootcamper's copy.

**Stamp the completion date.** Ensure the recap header carries a `**Completed:** {today's date, ISO
8601}` line (add it directly under the `**Started:**` line if absent; leave an existing one intact).
This is the date the Certificate of Completion shows (INV-100), distinct from `**Started:**` — so a
bootcamp spanning multiple days shows the graduation date, not the start date. The renderer prefers
this `Completed` date and falls back to `Started` when it is absent.

**Record the run environment (recap-only).** Ensure the recap header carries the plugin version and
a run-environment provenance block, so the keepsake records which plugin version produced the run
and the hardware/software it ran on. Add these header meta lines (in the preamble, above the first
`## ` section) when absent, idempotently — leave existing lines intact:

- `**Plugin version:**` — from the plugin manifest (should already be present from the recap
  header; add it here if the header predates that field). Resolve the manifest exactly as
  `../bootcamp-onboarding/onboarding-flow.md` step 0 specifies —
  `${PLUGIN_ROOT}/plugin.json`, else
  `<this-skill-dir>/../../plugin.json`, else "Unknown" — and ⛔ never by searching
  the filesystem, which on a machine carrying two Power checkouts records the wrong version in
  the keepsake (INV-252). Record the version only, never the path it resolved from: an absolute
  path carries a username and this block is PII-free (INV-065).
- `**Operating system:**` — OS + architecture, reused from the detected/persisted values in
  `config/bootcamp_preferences.yaml` (INV-061), e.g. `Ubuntu 24.04 (x86_64)`.
- `**Python version:**` — the `python3 --version` of the environment.
- `**Language runtime:**` — the bootcamper's chosen-language runtime and version (for a Python
  bootcamp, the same Python).
- `**Senzing SDK:**` — the Senzing SDK/engine version, obtained from the Senzing MCP tools (INV-080),
  never guessed; "Unknown" if unavailable.
- `**Database:**` — the database backend (e.g. SQLite, or PostgreSQL when chosen).

The renderer renders `Plugin version` on the cover and the `Operating system` / `Python version` /
`Language runtime` / `Senzing SDK` / `Database` lines as a distinct **Run environment** block (use
exactly those key names so the renderer groups them). This block is written to `docs/bootcamp_recap.md`
and the PDF only — it is **never** shown in the bootcamp output (INV-012) — and MUST NOT contain a
hostname, username, IP address, or any other personal/host identifier (INV-065). Like every
graduation step it warns-and-continues: if a value cannot be gathered, record "Unknown" and proceed.

If an in-progress recap checkpoint at `docs/progress/recap_checkpoint.md` still holds a
**narrative** (a module interrupted before completion), fold its content into that module's
`## {Module name}` section (append only), then remove the
`<!-- RECAP-CHECKPOINT:START -->` … `<!-- RECAP-CHECKPOINT:END -->` block from
`docs/bootcamp_recap.md` and clear the checkpoint. This ensures the recap carries any
narrative captured from an interrupted module and the PDF renders clean, completed
sections.

⚠️ **The file existing is not evidence a module was interrupted.** `checkpoint-tick.py`
creates it as an empty scaffold of HTML comments while the bootcamp runs, so the normal
state at graduation is "present and unfilled". Fold only when there is real content
**between** the `START` and `END` markers; a scaffold-only checkpoint is nothing to fold
and nothing to report.

**Backfill orphaned screenshots (before rendering).** Scan `docs/visualizations/*.png`. For any PNG
**not already referenced** by an `![...](...)` image line in `docs/bootcamp_recap.md`, embed it into
the matching `## {Module name}` section's **Actions Taken** — **all** of them, not a "best" few: each
capture is a distinct tab (INV-122), so a count cap deletes unique content, and this backfill is the
safety net for captures whose embed step was missed. Map each PNG to
its module by the visualization it came from: match the PNG's base name against the `<name>.html`
referenced in a module's recap section (e.g. `truthset_verification-*` → Truth Set visualization;
`results_visualization-*` (Module 7's single interactive visualization app),
`due_diligence_results-*`, or any other `<name>-*` → the module whose section references
`<name>.html` (older recaps may carry `multi_source_results-*` from before the consolidation; the
general `<name>-*` rule still maps them)). If a PNG matches no section, place it in the nearest preceding module section. This
is a **safety net** for captures whose embed step was skipped mid-bootcamp
(`../bootcamp-onboarding/module-completion.md` makes the embed a required step, but this guarantees
the recap PDF still shows captured screenshots if one was missed). Append-only and **idempotent** —
never rewrite a completed section's prose (INV-085), never add a reference that already exists, and
skip any image that is missing or unreadable (INV-048). Like every graduation step it is
non-blocking: if it is uncertain, warn and continue — never block the PDF on a screenshot.

Captures are named `<name>-<tab-slug>.png` (see
`../module-03b-truthset-visualization/visualization-api-reference.md` → "Tab identifiers and
deep-linking"), so the **tab slug gives the caption**: use the tab's display name rather than
inventing a description. A backfilled caption must never assert content that was not confirmed by
opening the image.

One tab needs more than its slug. A **Search / Probe** capture taken from the static snapshot has an
inert search box (the snapshot has no engine), and a bare "Search / Probe" caption on an empty search
box implies a result set that was never captured — the defect INV-123 forbids. When the image opened
shows an empty or inactive search state, say so in the caption. This matters here and not only at
capture time because a backfill runs precisely when the capture step's own caption never happened.

⛔ **Insert in the app's tab order, not in filename-discovery order.** That same tab table's row
order is the embedding order. Backfilling by directory scan is what produced a recap whose images
ran Entity Graph → Cross-Source → Search/Probe → Merge Statistics → Match Keys → Feature Scores —
append order, against an app whose tabs run left to right in a different sequence. Ordering the
image lines within a section is not a prose rewrite: the append-only rule (INV-085) protects the
section's **narrative**, and these lines are the backfill's own output.

**Verify the screenshots the recap actually carries (warn, never block).** Three checks, each
best-effort and each non-blocking (INV-048) — the backfill above only maps PNGs that *exist*, so
none of these are covered by it:

1. **A visualization section carrying fewer images than were captured.** For each completed module
   whose recap section references a `docs/visualizations/*.html` artifact, compare the count of
   `![...](...)` lines in that section against how many tabs were actually captured for it. Warn on
   any **shortfall**, not only on zero.

   Get the captured count from an external source, never from the recap:
   - **Preferred — the capture manifest.** `capture_screenshots.py` writes
     `docs/visualizations/<name>-tabs.json` recording `captured` (one entry per PNG written),
     `not_present`, `not_applicable` and `failed`. A `not_applicable` tab is **not** a shortfall:
     the app suppresses a tab whose data does not exist (Cross-Source with one data source,
     Match Keys and Feature Scores with no multi-record entities), so it was never on screen and
     is correctly absent from the recap. `generate_recap_pdf.py --check` already reads it and fails on a
     shortfall, naming the missing tab slugs; if `--check` reported
     `SKIPPED: tab-coverage check`, no manifest was found and this check has **not** run — say so
     rather than treating it as passed (INV-163).
   - **Fallback — the PNGs on disk.** Count `docs/visualizations/<name>-*.png` for that
     visualization's base name and compare against the section's image lines.

   ⛔ **Do not use the generator's `embedded N of M images` figure for this.** Its denominator is
   the count of `![](…)` links in the recap it is measuring, so a section that embedded four of six
   captured tabs reports `embedded 4 of 4 images` — a perfect score against an incomplete set. It
   answers "did every link render", never "did every tab arrive". A prior session cited
   `embedded 12 of 12` to a Bootcamper as proof the screenshots were complete while they were
   asking about exactly this; it was right only by luck of the input.

   Zero remains the worst case and is still covered: it shipped a Truth Set visualization section
   with no screenshots at all — no PNG existed, so the backfill found nothing to backfill and said
   nothing.
2. **Duplicate images within one section.** If two embedded images in the same section are
   byte-identical, or have identical pixel dimensions and were written within the same second, warn:
   that is the signature of capturing one tab repeatedly rather than one image per tab.
3. **Captions that cannot be checked.** If an embedded filename carries no recognized tab slug, warn
   that its caption cannot be verified against a tab and should be confirmed by opening the image.

**Normalize the Markdown (once, before rendering).** Now — after reconcile and **before** the
Step 1b render — make a single best-effort CommonMark pass over `docs/*.md`, including
`docs/bootcamp_recap.md`. Scope it to top-level `docs/*.md` only: **never recurse into
`docs/feedback/`, and never rewrite, empty, or delete the bootcamper's feedback file**
(`docs/feedback/SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md` must survive graduation intact — INV-015).
During the bootcamp these files were written plain (see
`../bootcamp-onboarding/ground-rules.md` → "Markdown files"); this is where they get prettified.
**Run the bundled normalizer** rather than reformatting by hand — it enforces the house rules and,
more importantly, enforces the content guard below in code:

```bash
python3 "${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/normalize_docs_markdown.py"
# or, if PLUGIN_ROOT is unset: python3 <this-skill-dir>/../bootcamp-onboarding/scripts/normalize_docs_markdown.py
```

It applies blank lines around headings (MD022), fenced blocks (MD031) and lists (MD032); a language
on every fenced block (MD040); and `**Label:**` colon spacing (a space after the colon, none
before). It globs top-level `docs/*.md` only and never recurses, so the feedback file is
structurally out of reach.

⛔ **The pass is purely cosmetic, and that is checked, not assumed.** It must never reorder, remove,
or rewrite the prose of a completed `## {Module name}` section, nor drop any of its four subsections
(Information Shared, Questions & Responses, Actions Taken, End-of-Module Summary). The normalizer
fingerprints each file's non-whitespace content line by line before and after and **restores the
original** if the result does not carry every source line forward — the one permitted change being an
opening fence gaining an info string. This matters because the pass runs *immediately before* the
render: a cosmetic step that dropped prose would produce a valid, prettier, **shorter** recap, and the
generator's content-retention figure (INV-110) is computed against the normalized file, so it would
report success against already-damaged input.

If the normalizer reports a file left as written, that is a normalizer bug — say so and continue with
the file unformatted; never hand-edit the prose to make formatting pass. Like every graduation step
this is non-blocking: if it fails or is unavailable, warn, leave the content as written, and continue
— a formatting issue is never a reason to skip the PDF.

### 1b. Render the PDF

Generate `docs/bootcamp_recap.pdf` with the bundled generator. It always produces
a valid PDF (a professionally designed one when `fpdf2` is installed, a plainer
stdlib-rendered one otherwise), so a missing `fpdf2` is never a reason to skip.

**Prefer the professionally designed renderer.** Before rendering, check whether
`fpdf2` is importable (`python3 -c "import fpdf"`). If it is not, offer to install it
so the designed renderer is used (a cover page, a table of contents with page
numbers, color-coded per-module sections, and page footers — INV-048, the recap PDF
should look professional). Install it **robustly**, never with a bare `pip`:

- **Prefer a project-local virtualenv.** This sidesteps PEP 668
  "externally-managed-environment" Python (common on macOS/Homebrew and many Linux
  distros) and never touches the global/system Python:

  ```bash
  python3 -m venv data/temp/recap-venv
  # Linux/macOS:
  data/temp/recap-venv/bin/python -m pip install fpdf2
  # Windows:
  data\temp\recap-venv\Scripts\python -m pip install fpdf2
  ```

  Then run the generator with **that venv's** Python (below) so it imports `fpdf2`.
- **Never call bare `pip`** — a stale shim on PATH may point at a deleted
  interpreter. Always go through an explicit interpreter: `python3 -m pip` (or
  `py -3 -m pip` on Windows). `--user` / `--break-system-packages` are last-resort
  opt-ins only, never the default.
- **Degrade gracefully.** If the bootcamper declines, or venv creation / the install
  fails (offline, no `ensurepip`, etc.), proceed with the stdlib fallback — it still
  produces a valid, complete PDF, so this never blocks graduation.

(Rasterizing pages to PNG to check the layout is **not** a maintainer-only aid — it is part of
verifying the render, below. `poppler`'s `pdftoppm` is the tool to reach for; `pymupdf` also works
where it happens to be installed. Neither is required — but a check that does not run MUST be
reported as skipped rather than degrading silently, per "Say what you could not verify" below.)

Locate and run the bundled script (it ships with this Power). Use the venv's Python
if you created one above; otherwise `python3`:

```bash
# fpdf2 already importable, or using the stdlib fallback:
python3 "${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/generate_recap_pdf.py"
# Or, when you installed fpdf2 into the project-local venv above:
data/temp/recap-venv/bin/python "${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/generate_recap_pdf.py"
```

If `${PLUGIN_ROOT}` is not set in the current context, resolve the script
relative to this skill's directory instead (this skill lives at
`skills/graduation/`, so the generator is two levels up under `../bootcamp-onboarding/scripts/`):

```bash
python3 <this-skill-dir>/../bootcamp-onboarding/scripts/generate_recap_pdf.py
```

The script reads `docs/bootcamp_recap.md` and writes `docs/bootcamp_recap.pdf`.

- **Success** is a `PDF generated:` line on stdout with exit 0. Only then tell the bootcamper: "📄 Recap PDF generated at `docs/bootcamp_recap.pdf`." Never claim success without that line. That line also reports how much of the recap reached the PDF (e.g. `rendered 25201 of 25467 source characters (99%)`); if it is well below 100%, content is being dropped — check the recap's structure before handing the PDF over. When the recap references screenshots it additionally reports `embedded N of M images` — **read this, and do not treat the retention figure as covering it.** Retention counts characters, so a PDF that lost every screenshot still reports ~99%; `embedded 0 of 6` is the only line that says so. Any shortfall means an image path did not resolve, and the generator names each one on stderr as `skipped image (not found): …` with the directories it searched.
- **Image paths in the recap are relative to `docs/bootcamp_recap.md`, and the generator resolves them that way.** Write them exactly as Step 1a says — `![alt](visualizations/<file>.png)` — which is what a Markdown reader of the recap needs, and what the PDF now needs too. Do **not** "fix" a path to `docs/visualizations/...` to suit the PDF: that breaks the Markdown recap (it resolves to `docs/docs/...`) and is no longer necessary. Equally, do not `cd docs` before rendering to make images appear; if images are missing, the path or the file is wrong, not the working directory.
- **`WARNING: … some sections are incomplete` with exit 0** means the recap was recognizable but a section is missing a subsection. The PDF was still written and is still valid — backfill per 1a and re-render if you can, but this never blocks graduation.
- **`ERROR: refusing to render …` with a non-zero exit means NO PDF was written.** The generator refuses when the input is not a bootcamp recap (no `## {Module name}` sections, or no section carrying its `### ` subsections) or when most of the content would be dropped — because an empty-looking-but-valid PDF is worse than none. Do **not** announce a PDF. Say plainly that the recap PDF could not be generated and why, then fix the cause: confirm `docs/bootcamp_recap.md` really is the recap (not some other Markdown file) and that its sections carry the four subsections, then re-render. If it cannot be fixed, fall back to the inline render below — never leave graduation with the bootcamper believing a PDF exists when it does not.
- **Content check (optional, non-blocking):** run the script with `--check --expect-modules "<semicolon-separated display names of the modules reconciled in Step 1a>"` — this confirms each present section carries the four required subsections, that every **End-of-Module Summary** carries its three labeled blocks (What you accomplished / Files produced / Why it matters — backfill per 1a if it reports any missing), flags any `![](…)` image target that resolves to no file (reported as `embedded image not found: …`, so a lost screenshot surfaces here rather than in the finished PDF), **and** flags any completed module missing its section entirely. Separate the names with **semicolons**, not commas, since some names contain commas (e.g. "Query, Visualize and Discover" and "Data Quality, Mapping, and Transformation" — the latter contains two). (The names are the same ones Step 1a ensured have sections, so pass them directly; whole-module presence is primarily guaranteed by that reconcile.) If it reports gaps, backfill per 1a and re-render. A gap never blocks graduation.
- **If the bundled script cannot be located or run:** do not stop. Generate the PDF inline instead: parse `docs/bootcamp_recap.md` and render a cover page plus one page per module (each with Information Shared, Questions & Responses, Actions Taken, End-of-Module Summary) using `fpdf2` if importable, else a minimal valid PDF. The recap Markdown at `docs/bootcamp_recap.md` is always the source of truth, so content is never lost.

⛔ **Verify the artifact, not the exit code.** A `PDF generated:` line, a zero exit, and a high
retention percentage are all necessary and all demonstrably insufficient: in one session four separate
steps reported success while producing wrong output — three screenshots of the same tab with two
invented captions, a certificate footer whose glyphs were sliced in half by the page border, an entire
match-key table drawn off the page, and bullet lists whose item boundaries were invisible. None raised
an error and two reached a signed keepsake. The retention figure *cannot* catch off-page content,
because the text is in the content stream and merely positioned outside the page box.

So inspect the rendered artifact. Each check below is **best-effort and non-blocking** — run what the
toolchain supports, warn on what it finds, and never block graduation on a verification step
(INV-048, INV-052/INV-066). None of these is a 👉 question; this is agent-side apparatus, not
bootcamper-facing output (INV-012).

- **Rasterize before trusting text extraction.** `pdftoppm -r 100 -png -f N -l N <pdf> <prefix>` the
  certificate page and any page whose layout changed, and **look at the image**. Text extraction
  reports a border-clipped string as present and correct; only the raster shows the glyphs cut in
  half.
- **Probe positively for content you know is there.** `pdftotext` the output and grep for a
  distinctive string from the source — a table header, a match-key pattern, the cover subtitle in
  full. A count of **0** is the finding. This is the only check that catches content rendered outside
  the page box.
- **Count unique image XObjects, not `/Subtype /Image` occurrences.** References are counted more than
  once, so the naive grep reported 12 for 10 images. Reach for these in order, and use the first
  available: (1) the generator's own `embedded N of M images` line, which needs no tool at all and is
  the count the renderer actually achieved; (2) **Pillow**, which `fpdf2` already pulls in — so when
  you created the project-local venv above it is *already importable in that same interpreter*, and
  opening the embedded images there gives an honest count and their dimensions with **no new
  dependency**; (3) `pdfimages -list <pdf>` where poppler exists; (4) the `/Subtype /Image` grep,
  **which overcounts** — if you fall back to it, label the number as approximate and say so.
- ⛔ **`embedded N of M images` measures references, not tab coverage — never cite it as evidence
  that every tab is present.** Its denominator is the number of `![](…)` links in the recap being
  rendered, so it is derived from the same file as its numerator: if only four of six captured tabs
  were ever embedded, the line reads `embedded 4 of 4 images`. It is structurally incapable of
  detecting the very incompleteness a Bootcamper asking "are all the tabs here?" is describing, and
  a prior session cited `embedded 12 of 12` as proof of completeness while being asked exactly that
  — correct by luck of the input, not by measurement. The count that *can* answer it is the
  generator's separate `N of M captured tabs reached the recap`, whose denominator comes from
  `capture_screenshots.py`'s `<name>-tabs.json` manifest; when `--check` prints
  `SKIPPED: tab-coverage check`, no manifest was found and the question is **unanswered** rather
  than answered yes (INV-163).
- **Open every captured PNG before writing its caption** (INV-123, and
  `../bootcamp-onboarding/module-completion.md` → "Capturing visualization screenshots").
- **Re-run `--check --expect-modules "…"` after every render**, semicolon-separated — two module
  display names contain commas.
- **When you replace text, confirm both directions:** the new string is present **and** the old one is
  gone. Decompress the content streams rather than assuming the replacement landed.

⚠️ **A caution learned the hard way:** verify your verification. A regex-based content-stream reader
using strict `zlib.decompress` silently drops any stream whose slice is off by a few bytes, which
looks exactly like a lost page. Cross-check a suspicious "missing content" result with a second,
independent tool (`pdftotext`) before concluding the artifact is broken — the reader is the likelier
culprit.

**Toolchain these assume, and what it looks like per platform.** Every check above is doable with
plain headless Chrome and poppler, which is why nothing here — or in the screenshot capture path — is
designed around a heavier dependency. Probe for a tool before using it and skip the check when it is
missing; **never install one to satisfy a verification step** (INV-129) — that includes poppler, so do
not offer `scoop install poppler` / `brew install poppler` / `apt install poppler-utils` to make a
check pass.

- **Linux:** poppler is usually present (`pdftoppm` / `pdftotext` / `pdfinfo` / `pdfimages`),
  so the full check set normally runs. One field machine had `fpdf2`, headless Chrome and poppler, and
  did **not** have Playwright, Selenium, or PyMuPDF.
- **macOS: poppler is NOT part of the base system.** macOS ships none of the four binaries, and you
  **must never install them** to make a check pass (INV-129) — they arrive only via an explicit
  `brew install poppler`, which a Bootcamper has no reason to have run.
  Observed 2026-07-31 on macOS 26.5.2 (Apple Silicon) **with Homebrew installed and in active use for
  the Senzing SDK itself**: all four absent, poppler not installed as a formula. Do **not** group
  macOS with Linux here — the habitual pairing for Unix-like tooling is wrong for poppler, which is a
  Linux distribution package rather than a macOS system component.
- **Windows: poppler is typically absent.** On one Windows 11 workstation only `pdftotext` resolved —
  `pdftoppm`, `pdfinfo` and `pdfimages` were all missing. That is the normal Windows case, not a
  broken setup.
- **So the missing-poppler path is the expected case on both macOS and Windows**, and it removes
  exactly the two checks text extraction cannot substitute for: the page raster and the honest image
  count.

  ⚠️ **Do not fall back on `pdftotext` without probing for it.** On Windows it was the one binary
  that resolved, so earlier guidance said to "keep the positive `pdftotext` probe" — on macOS it is
  missing along with the other three, so that advice is not actionable there. Probe, then use it or
  record it as skipped.

  What needs **no** new dependency on either platform, so the reduced set is actionable rather than
  merely reduced:

  - **Pillow**, which `fpdf2` already requires (`fpdf2` 2.8.5 declares `Pillow>=8.3.2` — verified
    2026-07-31), so when you created the project-local venv above it is *already importable in that
    same interpreter*. This is the honest image count and their dimensions.
  - **The generator's own success line**, which needs no tool at all: `embedded N of M images` is the
    count the renderer achieved, and `N of M captured tabs reached the recap` is the coverage figure.
    Keep them distinct — the first cannot answer the coverage question (see the ⛔ above), and the
    second is absent when no capture manifest exists.

  **Report the page raster as not verified** — do not imply the layout was checked (INV-163).

⛔ **Say what you could not verify.** Any check skipped for a missing tool MUST be recorded as skipped,
naming the check and the tool, and the closing announcement MUST state which verification steps did
not run. "Verified" that silently means "verified except for the two strongest checks" is the same
class of overstatement this section exists to prevent: a keepsake whose layout nobody could inspect is
acceptable, one described as verified when its layout was never inspected is not. A skipped check
still never blocks graduation (INV-048, INV-052/INV-066), and this stays agent-side apparatus rather
than bootcamper-facing output (INV-012).

⚠️ **Spend a reduced check set on what only it can catch.** When tools are missing, prioritize: the
positive `pdftotext` content probe (the only check that catches content positioned outside the page
box) and the image count (which catches silently-dropped screenshots — the failure that shipped a
recap with 2 images where 8 were expected, detectable *only* by counting). The page raster is the one
genuinely tool-gated check; its absence is the thing to announce.

## Step 2: Build the production project

If `production/` already exists, pin this 👉 question verbatim (neutral lead + numbered list):

👉 **`production/` already exists — how should I proceed? Reply with a number:**

1. **Overwrite** — replace the existing `production/` contents.
2. **Merge** — keep existing files and add or update the generated ones.
3. **Abort** — leave `production/` untouched and skip to the graduation report.

Wait for the answer. On abort, skip to the graduation report noting the abort.

Create `production/` and copy production-relevant files (skip any source that
does not exist; on a copy failure, log and continue):

| Source | Destination | Notes |
|--------|-------------|-------|
| `src/transform/**` | `production/src/transform/` | Mapping/transform code |
| `src/load/**` | `production/src/load/` | Loading code |
| `src/query/**` | `production/src/query/` | Query/discovery code |
| `src/utils/**` | `production/src/utils/` | Shared helpers |
| `data/senzing-ready/**` | `production/data/senzing-ready/` | Senzing-ready data |
| `requirements.txt` / `pom.xml` / `Cargo.toml` / `package.json` / `*.csproj` | `production/` | Dependency manifest |

⛔ **Every destination above keeps the source's path relative to the project root, and
`data/senzing-ready/` in particular.** (INV-186) The code in `src/load/**` is copied **verbatim** and reads its
input from `data/senzing-ready/` (INV-084 — `../module-06-data-processing/phaseA-build-loading.md`
step "Mapped sources"), so flattening the data to `production/data/` hands the bootcamper a project
whose loader points at a directory that does not exist. Copy the tree, do not rewrite the code: the
loader is theirs, and a path edited by graduation is a change they never saw made.

Create `production/database/.gitkeep` as an empty placeholder (never copy the
eval database itself).

**Exclude (never copy):** `config/bootcamp_progress.json`,
`config/bootcamp_preferences.yaml`, `docs/bootcamp_recap.md`, `data/samples/`,
`data/raw/`, `logs/`, `backups/`, and `docs/feedback/`.

⛔ **`data/raw/` is excluded, so a CORD fast-pathed source's input is not carried over.** A
fast-pathed source loads straight from `data/raw/` with no mapping (INV-040/INV-041), so its loader
arrives in `production/` with no input file — deliberately, since raw source data is the
bootcamper's to place, not graduation's to copy. Name each such source in the Step 5 graduation
report's **files-excluded** table and in `production/README.md` → Configuration, saying where its
input has to be supplied (INV-187). An excluded input the handover never mentions is indistinguishable from a
broken project.

Present a short, one-line statement of what was copied, what was excluded, and the directories
created, then continue directly to Step 3 — generate the production configuration files
automatically. Do not gate this behind a 👉 question (one fewer low-stakes confirmation).

## Step 3: Production configuration files

Generate these in `production/`, parameterized by `programming_language` and `database_type` from
pre-checks. Use placeholder values only, never real secrets:

- **`.env.example`:** `SENZING_ENGINE_CONFIGURATION_JSON`, `SENZING_LICENSE_FILE`, `DATABASE_URL`,
  `LOG_LEVEL` with safe example values and comments. ⛔ **The license variable is
  `SENZING_LICENSE_FILE`, never `SENZING_LICENSE_PATH`** (INV-208) — the latter is a confabulation that shipped
  here for a time and no MCP tool returns it. The correct spelling comes from
  `sdk_guide(topic='load', language=…, record_count=<above the default limit>)`, whose
  `compatibility_notes` name it; confirm it there rather than from memory (INV-080; a sourcing floor),
  since wrong environment-variable names are on the server's own confabulation list and this file is
  one the bootcamper carries into production, where an unread variable fails as a capacity error far
  from its cause. Also show the `PIPELINE` alternative as a comment — `LICENSEFILE` (a `.lic` path) or
  `LICENSESTRINGBASE64` (an inline key) inside the `SENZING_ENGINE_CONFIGURATION_JSON` value, matching
  Data collection's wiring — so both supported routes are visible.
- **`docker-compose.yml`:** SQLite (single service + volume mount) or PostgreSQL (app + db service with a health check), per `database_type`.

**Where `deployment_target`/`cloud_provider` is known, say so in both files** (INV-097): a header
comment naming the intended target — e.g. `# Target: AWS (ECS/Fargate)`, `# Target: Kubernetes`,
`# Target: on-premises` — and, in `.env.example`, a comment on the values that platform will supply
differently (a managed-database `DATABASE_URL`, a secret-manager reference instead of a literal).
⛔ Stay declarative: name the target and stop. Do **not** invent provider-specific resources,
credentials, ARNs, or account identifiers — placeholder values only, as above, and a wrong
infrastructure guess in a handed-over project is worse than a generic one. When the value is absent
the files are exactly as they were before this paragraph.

- **`.gitignore`:** language-appropriate, always including `.env`, `.env.production`, `*.db`, `*.sqlite`, `__pycache__/`, `node_modules/`, `target/`, `bin/`, `obj/`, `build/`, `dist/`, `*.log`.

## Step 4: Production README and migration checklist

- **`production/README.md`:** parameterized by `programming_language`, `database_type`, and the data sources from `config/data_sources.yaml`. Use no bootcamp language (no "bootcamp", "module", "track", or "bootcamper"). Sections: Project Overview, Prerequisites, Installation, Configuration, Usage, Project Structure. Show it to the bootcamper and apply any requested revisions.
  - **Where `integration_targets` is known** (INV-097), name those systems in **Project Overview** as what the resolved entities are meant to feed, and in **Configuration** as the integration points a reader will need to wire up — the resolved data exists to reach them, so a README that never mentions them describes half the job. Absent → omit; never write "none" or a placeholder.
- **`production/MIGRATION_CHECKLIST.md`:** `- [ ]` checkboxes under six sections (Database, Security, Licensing, Performance, Data, Deployment). Because the bootcamp does not include dedicated performance/security/monitoring/deployment modules, add a note at the top: "⚠️ Some production topics (performance, security, monitoring, deployment) are not covered in depth during the bootcamp: complete these items before deploying," and mark those items with ⚠️.
  - **The Performance section MUST carry the DEFAULT-flags item** — ⚠️ *"Replace `*_DEFAULT_FLAGS`
    composites in `production/src/` with the explicit `SZ_*` flags whose output your code actually
    consumes."* Give the reason, because it is what makes the item non-obvious: the server states
    that DEFAULT composites are for getting started and exploration rather than production, that
    their **membership may change between Senzing versions**, and that pinned code can therefore
    *"silently change what it returns after an upgrade — no error is raised"*; they also over-fetch,
    costing engine work and response size (`get_sdk_reference(topic='flags', …)` top-level
    `caution`, MCP server 1.32.9, 2026-08-12). This matters here specifically because `src/query/**`
    is copied into `production/src/` verbatim, so the bootcamp's exploration-shaped flag choice
    becomes their shipped code. The bootcamp is right to teach the composites
    (`../module-07-query-visualize-discover/phase1-query-visualize.md` relays the same caution) —
    this checklist is where the production correction belongs.
  - **The Deployment section is where `deployment_target`/`cloud_provider` lands** (INV-097): name the stated target in its heading or first item, and make its checkboxes the ones that target actually needs (a cloud target → managed database, secret storage, image registry, network egress to nothing external; Kubernetes → manifests/Helm, resource limits, liveness probes; on-premises → host provisioning, backup schedule). ⛔ Still ⚠️-marked and still not covered in depth by the bootcamp — naming the target makes the list *relevant*, not authoritative, and it must not read as a deployment guide the bootcamp did not give. Absent → the generic six-section list exactly as before.

Write every `production/*.md` deliverable — this README, the migration checklist, and the
Step 5 `GRADUATION_REPORT.md` — as **plain, functional Markdown**, exactly as the bootcamp's own
docs were written (`../bootcamp-onboarding/ground-rules.md` → "Markdown files"). Do **not**
hand-format them to the house rules: **Step 5a runs the normalizer over `production/`** and does it
in code, with a content guard. Structure still matters and is not deferred — the sections listed
above, the `- [ ]` checkboxes, and the tables are content, not formatting.

## Step 5: Graduation report

Always generate `production/GRADUATION_REPORT.md`, even if earlier steps had
errors. Include: completion timestamp, bootcamp path (Core/Customized) and the modules completed,
`programming_language`, `database_type`, a files-generated table, a files-excluded table, and
next steps (fill in secrets, obtain a production license, work through the
checklist, configure CI/CD, test with production data). Record the Module 1 answers too when
present — the intended `deployment_target`/`cloud_provider` and the `integration_targets`
(INV-097) — so the handover states what the project was aimed at; omit either line when absent.
If any step failed, add a
"⚠️ Issues Encountered" section naming what failed and what was skipped.

## Step 5a: Normalize the production Markdown (once, after the files exist)

`production/` now holds its Markdown deliverables, written plain. Make the same single
best-effort CommonMark pass over them that Step 1a made over `docs/*.md` — INV-060 requires the
pass over **both** sets, and the `production/` half is why this step exists:

```bash
python3 "${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/normalize_docs_markdown.py" --docs-dir production
# or, if PLUGIN_ROOT is unset: python3 <this-skill-dir>/../bootcamp-onboarding/scripts/normalize_docs_markdown.py --docs-dir production
```

It applies the same rules as in Step 1a and globs top-level `production/*.md` only, never
recursing — so nothing under `production/src/`, `production/config/` or a copied `docs/` subtree is
touched.

⛔ **Same content guard, same non-blocking contract as Step 1a.** The normalizer fingerprints each
file's non-whitespace content before and after and **restores the original** if any source line
would be lost, so a cosmetic pass can never silently shorten a handover document. If it reports a
file left as written, that is a normalizer bug — say so and continue with the file unformatted;
never hand-edit prose to make formatting pass. If the script fails or is unavailable, warn, leave
the content as written, and continue (INV-048).

⛔ **Run it after Step 5, not before.** `production/` does not exist at Step 1a and its Markdown is
not finished until `GRADUATION_REPORT.md` is written, so an earlier pass would normalize nothing —
which is precisely how this half of INV-060 went unbuilt from 2026-07-16 to 2026-07-29.

`docs/REVISIT_BOOTCAMP.md` is written later still (Step 6c) and so is covered by **neither** pass;
Step 6c states its own formatting rule.

## Step 5b: Render the two keepsake documents as styled PDFs

The bootcamp already treats "rendered as a styled PDF" as the signal that a document is a
keepsake rather than a working file. Two more qualify, and the renderer that makes them is
already bundled:

- **`docs/business_problem.md`** — the document a stakeholder is most likely to be shown.
- **`docs/data_source_evaluation.md`** — the engine-verified readiness findings and the
  unmapped-field audit with its rejected-field rationale; the reference a team returns to when
  someone asks "why wasn't field X mapped?".

Render each with the bundled general renderer, resolved the same way as every other bundled
script and never as a bare `../bootcamp-onboarding/scripts/…` path (INV-185):

```bash
python3 "${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/generate_document_pdf.py" \
    --input docs/business_problem.md --output docs/business_problem.pdf \
    --require-sections "<this document's own H2 headings, semicolon-separated>" \
    --subtitle "The problem this bootcamp set out to solve"
# or, if PLUGIN_ROOT is unset: python3 <this-skill-dir>/../bootcamp-onboarding/scripts/generate_document_pdf.py …
```

⛔ **Pass `--subtitle`.** The cover's subtitle defaults to the discoveries line, "What Senzing
found in your data" — true of the discoveries document and wrong on either of these. It is the
one part of the layout engine that is not document-agnostic, and it is the first thing a
stakeholder reads. For `data_source_evaluation.md`, something like "How ready your sources were,
and what was left unmapped".

⛔ **Read each document's actual H2 headings and pass those.** Bootcampers word these documents
differently, so there is no fixed list to hard-code — which is the whole reason the renderer took
a `--require-sections` parameter instead of a constant. Omitting the flag applies the *discoveries*
defaults and the document is refused; `--no-section-check` is the fallback when a document has no
stable headings, and it is weaker, because the section check is what catches a document that
silently lost its structure.

⚠️ **Neither flag relaxes the content-retention floor** (INV-110). If a render is refused for
retention rather than sections, the document genuinely would not survive the pass — say so and
leave it unrendered rather than reaching for `--no-section-check`.

⛔ **Verify each PDF, do not trust the `PDF generated:` line** (INV-129). Two positive probes per
file, both required:

1. **Extract text from the written file** and confirm real content appears — fpdf2 compresses its
   content streams, so decompress before searching, or a raw byte search reports a false negative.
2. **Count pages** (`/Type /Page` objects, or `pdfinfo` where poppler exists — which on macOS and
   Windows it usually does not; see Step 1b). At least one, and a one-page PDF from a multi-section
   document is a signal to look at the text probe again rather than to pass it.

A zero exit and a plausibly-sized file are both necessary and neither is sufficient.

**Non-blocking, like every graduation step** (INV-048): if a document is absent, refused, or fails
verification, warn on stderr, say which PDF was not produced, and continue. Name the ones that
succeeded in the closing summary alongside the recap PDF; never turn a failure into a 👉 question
or a to-do for the bootcamper.

Character handling is unchanged from the discoveries path — the renderer reports any character it
had to drop (INV-143/INV-159). This step must not become a route that bypasses that report: if it
names dropped characters, repeat them in the warning rather than only in the PDF.

## Step 6: Save the revisit/resume bundle

Silently preserve everything a returning bootcamper needs to pick the bootcamp back up — so
"graduated" becomes a genuine save point. Like every graduation step this is **non-blocking**
(warn-and-continue on any failure) and administrative in spirit (no narration beyond a short
closing summary). The bundle lives **outside `production/`**, under the reserved top-level
`backups/revisit/` directory, so Step 2's "never copy the eval database into `production/`" rule
is preserved (INV-094).

If `backups/revisit/` already exists from a prior graduation, pin this 👉 question verbatim before
overwriting it (neutral lead + numbered list, INV-051/INV-056); otherwise create it silently:

👉 **A revisit bundle already exists — how should I proceed? Reply with a number:**

1. **Overwrite** — replace the previous revisit bundle.
2. **Keep** — leave the existing bundle untouched and skip this step.

### 6a. Database backup

Back up the resolved repository so it can be restored later. Read **`database_type`**
(`sqlite`/`postgresql`) from pre-checks and the connection from `config/engine_config.json`.
⛔ When `database_type` is indeterminate, **do not guess a branch** — determine the engine from
`config/engine_config.json`'s connection string instead (and note the missing key per pre-check 3).
Picking the wrong branch here means either no backup or `pg_dump` against a SQLite file, and the
backup is the whole point of the bundle — INV-094 requires exactly one of the two branches below to
have run.

- **SQLite:** copy the repository file into `backups/revisit/database/` (e.g.
  `cp database/G2C.db backups/revisit/database/G2C.db`).
- **PostgreSQL:** run `pg_dump` of the Senzing database to
  `backups/revisit/database/senzing.dump`. When the database runs in a Docker container, dump
  through the container (e.g.
  `docker exec <container> pg_dump -U <user> -d <db> -Fc > backups/revisit/database/senzing.dump`).
  Confirm the exact user / database / container from `config/engine_config.json` (and the recorded
  container, when container-lifecycle tracking is present); never invent credentials.

Record the exact **restore** command in the return guide (Step 6c): SQLite = copy the file back to
`database/`; PostgreSQL = `pg_restore` (or `psql <` for a plain dump) into a fresh database. If the
backup cannot be produced (tool missing, database unreachable), warn and continue — the rest of the
bundle still saves.

### 6b. RESUME_STATE manifest

Snapshot the resume-critical state into `backups/revisit/state/` (copy each if it exists):
`config/bootcamp_progress.json`, `config/bootcamp_preferences.yaml`, `config/data_sources.yaml`,
`config/engine_config.json`, `config/license.json`, and `docs/mapping/`. Then write
`backups/revisit/RESUME_STATE.json` — a manifest indexing what was saved: the bootcamp path and
`modules_completed`, `programming_language` and `database_type` (the pre-check key names), the
business problem and data
sources, the relative path of each snapshotted file, the database backup path and its restore
command, the recap PDF (`docs/bootcamp_recap.pdf`), and any visualization snapshots under
`docs/visualizations/`. Use only project-relative paths.

### 6c. Return guide

Write `docs/REVISIT_BOOTCAMP.md` (Markdown under `docs/`, per INV-017). ⛔ **This is the one
deliverable you do hand-format** to the house rules (MD022/MD031/MD032 blank lines, MD040 fenced-block
languages, `**Label:**` colon spacing): it is written *after* both normalization passes — Step 1a's
over `docs/*.md` and Step 5a's over `production/*.md` — so no pass will reach it. Re-running Step 1a
here is deliberately **not** the answer: it would re-touch `docs/bootcamp_recap.md`, which the recap
PDF was already rendered from in Step 1b, leaving the keepsake and its source subtly out of step.
Cover:

- **Quick start when you return** — a short command list at the very top (re-source the env, restore
  the database, re-init the engine, re-run a query and the visualization).
- **What you accomplished** — per completed module, drawn from the recap.
- **Your business problem and data sources** — from `docs/business_problem.md` /
  `config/data_sources.yaml`.
- **Restore the database** — the exact SQLite copy-back or PostgreSQL `pg_restore` / `psql` command
  recorded in Step 6a.
- **Re-initialize and re-run** — how to re-source `src/scripts/senzing-env.sh` (if present) and
  re-init the engine, then re-run the loader, queries, and visualization.
- **License** — where the license lives (`licenses/g2.lic` when custom, else the built-in
  evaluation license) and any expiry.
- **Where things are** — point at `backups/revisit/` (state + database backup), the recap PDF, and
  `docs/visualizations/`.

Then present a one-line summary of what the bundle saved and where, and continue to Step 7.

## Step 7: Feedback reminder

If `docs/feedback/SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md` exists and contains at
least one real feedback entry, remind the bootcamper it is there and offer to
help them share it (see `../bootcamp-onboarding/feedback.md`). Do not send email
or open issues automatically: wait for explicit confirmation. Otherwise, add one
line: "Say \"bootcamp feedback\" anytime if you'd like to share your experience."

## Mandatory closing step: guaranteed recap and announcement

This runs exactly once, after the report, before graduation is reported finished.

1. **Guarantee the recap PDF exists.** Confirm `docs/bootcamp_recap.pdf` exists and is non-empty. If it is missing, re-run Step 1b (or the inline fallback) once so a valid PDF exists before you announce it. Never announce an artifact you have not confirmed exists at its path.
2. **Emit one closing announcement** naming only the artifacts confirmed to exist. State that the recap PDF at `docs/bootcamp_recap.pdf` opens with a summary page and then walks through every completed module, capturing that module's Information Shared, Questions & Responses, Actions Taken, and End-of-Module Summary, and that the source lives at `docs/bootcamp_recap.md`. Name the `production/` project and its `GRADUATION_REPORT.md` and `MIGRATION_CHECKLIST.md`. Frame the PDF as a keepsake to revisit and share with their team.

   **Also name the two keepsake documents Step 5b rendered — each only if it exists:**
   `docs/business_problem.pdf` (the problem this bootcamp set out to solve — the document a
   stakeholder is most likely to be shown) and `docs/data_source_evaluation.pdf` (how ready each
   source was and what was left unmapped — the reference for "why wasn't field X mapped?"). Step 5b
   is **non-blocking**, so either can legitimately be absent: an absent or refused PDF is simply not
   named, by item 1's rule that you never announce an artifact you have not confirmed exists
   (INV-048). This step is the **only** place these two reach the bootcamper — graduation is
   terminal, so a PDF unnamed here is one they never learn they have.

   **If any Step 1b verification check was skipped for a missing tool, say so here in one plain sentence** — name what was not checked, not the tool names. On Windows this is the common case (poppler is typically absent, so the page raster could not run). One sentence is enough: *"One note: I verified the PDF's contents but couldn't check its page layout on this machine, so if anything looks visually off, tell me and I'll re-render."* Never describe the keepsake as verified when a check did not run — and never turn this into a 👉 question or a to-do for the bootcamper.

Example (list only what exists):

> 🎓 **Here's your bootcamp recap.** Your complete recap is at `docs/bootcamp_recap.pdf`: a shareable PDF that opens with a summary and then walks through every module you completed, capturing the Information Shared, Questions & Responses, Actions Taken, and End-of-Module Summary for each. Your production project is ready in `production/`: start with `production/GRADUATION_REPORT.md` and work through `production/MIGRATION_CHECKLIST.md`. Two more keepsakes are alongside the recap: `docs/business_problem.pdf`, the problem you set out to solve, and `docs/data_source_evaluation.pdf`, how ready your sources were and what was left unmapped.

3. **End on the single closing question (INV-251).** The announcement carries no 👉. After it, end the graduation turn with exactly one 👉 question:

> 👉 **Is there anything else you would like to explore?**

Then stop and wait. This is the single closing question for the whole bootcamp.

4. **Terminal banner — only after the bootcamper declines.** Handle the reply to the closing question:

   - **Wants to keep exploring** (asks a question, names a topic, or otherwise continues): help them, then offer the closing question again when they are ready. Do **not** show the terminal banner yet — it must never pre-empt continued exploration.
   - **Declines** ("no", "I'm done", "that's all", "nothing else"): the bootcamp is complete. Do these two things, in order:
     1. **Stand down the Stop-hook nudge, silently.** Set a top-level `bootcamp_complete: true` key in `config/bootcamp_preferences.yaml` (a single minimal edit; do not narrate it). The `Stop` hook (`../bootcamp-onboarding/scripts/stop-nudge.py`) reads this key and will not nudge for a closing 👉 question once the bootcamp is over — so the terminal banner, which ends the turn with no 👉, is not re-opened.
     2. **Render the terminal banner, verbatim, exactly once** as the final output. It bookends the WELCOME banner that opened the bootcamp (start) and the GRADUATION banner (finish) with a clear end-of-bootcamp marker. No 👉 question follows it; the turn simply ends.

     ```text
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     🎓🎓🎓  END OF SENZING BOOTCAMP  🎓🎓🎓
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     ```

     Show this banner at most **once** per bootcamp, and never while exploration is still continuing.
