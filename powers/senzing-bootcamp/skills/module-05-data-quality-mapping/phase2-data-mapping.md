# Module 5, Phase 2: Data Mapping (steps 8–20)

Continues from Phase 1. Follow the ground rules; `🛑`/`⛔` are internal directives: do not
render them. Signal a stop by ending the turn on the single 👉 question and waiting.

**Iterative process:** Users can jump between steps. The goal is a working transformation
program, not strict sequence.

**Before starting:** Confirm which data source. Track multi-source progress (In Progress /
Complete / Pending).

**MCP-first invariant (this phase especially):** ALL JSON mappings and attribute names come
from the `mapping_workflow` MCP tool. NEVER hand-code or guess Senzing attribute names, and
never reuse mapping output from one source for another. Never guess SDK method signatures: use
`generate_scaffold` / `get_sdk_reference`.

## Skip fast-pathed sources

Before starting the mapping workflow for a source, check its registry entry in
`config/data_sources.yaml`. If `fast_pathed` is `true` and `mapping_status` is `complete`, skip
this source entirely: it has already been routed to Module 6. Proceed to the next unmapped
source.

## Mapping verbosity check (before starting the mapping workflow)

Read `config/bootcamp_preferences.yaml` and check the `mapping_verbosity` key.

- **If `mapping_verbosity` is `null` or absent:**

  👉 **Before we start mapping, which mode would you like? Reply with a number:**

  1. **Verbose mode** — I'll show each mapping step in detail: field detection, attribute selection rationale, transformation preview.
  2. **Concise mode** — I'll map quickly and show only the final mapped record and any warnings.

  *(Internal: end the turn on this question and wait.)* Persist their choice (`verbose` or
  `concise`) to `mapping_verbosity` in `config/bootcamp_preferences.yaml`.

  If the bootcamper skips or doesn't answer directly: default to `verbose`, persist it, and
  say: "Defaulting to verbose mode: say 'switch to concise' anytime if you want less detail."

- **If `mapping_verbosity` is already set to `verbose` or `concise`:** Say "Using your
  [verbose/concise] mapping preference from last time: say 'switch to [other]' if you'd prefer
  [less detail/more detail]" and proceed without waiting.

## Mid-mapping verbosity switch

If the bootcamper says "switch to verbose", "switch to concise", "more detail", "less detail",
or any natural variant indicating they want to change mapping verbosity:

1. Update `mapping_verbosity` in `config/bootcamp_preferences.yaml` to the requested mode.
2. Apply the new mode immediately to all subsequent presentation output.
3. Confirm briefly: "Switched to [verbose/concise] mode.": then continue without interruption.

## Mapping state checkpointing (applies to every step below)

`mapping_workflow` is stateful. Each call returns state that MUST be passed, unchanged, to the
next `mapping_workflow` call for that source: never alter or reconstruct it. After each step,
write a checkpoint to `config/mapping_state_[datasource].json`:

```json
{"data_source":"CUSTOMERS","source_file":"data/raw/customers.csv","current_step":3,"completed_steps":["profile","plan","map"],"decisions":{"entity_type":"PERSON","field_mappings":{"full_name":"NAME_FULL"}},"last_updated":"2026-04-14T10:30:00Z"}
```

On session resume: read the checkpoint, show the user where they left off, restart
`mapping_workflow`, fast-track through decided steps, and resume from the first incomplete step.
**Delete the checkpoint when mapping for that source is complete.**

When step-3 validation rejects a payload, append the **verbatim** returned text to a
`validation_rejections` array on the same checkpoint, and record `mapper_source` once the mapper
exists (`mapping_workflow` or `entity_specification`, with the reason when it is the latter):

```json
{"data_source":"NOMINO-RISK","current_step":3,"validation_rejections":["<raw rejection text, unedited>"],"mapper_source":"entity_specification","mapper_source_reason":"step-3 validation rejected twice with a truncated error naming no field"}
```

Keep the rejection text unedited — truncating or summarizing it destroys the only evidence the
upstream defect can be diagnosed from.

## File placement during the workflow

`mapping_workflow` downloads workflow resources and later produces output into a workspace
directory. Override any MCP-suggested `/tmp/` paths to project-local paths. Place files per the
ground-rules file-placement contract:

- Reusable resources at download time: transformation/workflow `.py` scripts → `src/`; the
  entity specification (`senzing_entity_specification.md`) → `docs/reference/`; other reference
  `.md` → `docs/`; config JSON → `config/`; data → `data/`.
- **Transient run artifacts stay in the workspace while the run is in progress:** the workflow
  reads and writes them for its own use. Do NOT relocate, delete, or redirect these mid-run:
  `profile_report.md`, `schema_hints.md`, `JOURNAL.md`, and generated JSONL output.
- **After the run for a source completes (after the iterate/finalize step), relocate the
  transient artifacts to their durable homes — and source-qualify the three mapping-phase
  Markdown filenames as you do:** `profile_report.md` → `docs/mapping/{source_name}_profile_report.md`,
  `schema_hints.md` → `docs/mapping/{source_name}_schema_hints.md`, `JOURNAL.md` →
  `docs/mapping/{source_name}_JOURNAL.md`. Mapping working data (`*_mapping_spec.json`, the
  per-source `{source}_sample.jsonl`, intermediate analyzer JSONL) → `data/mapping/`. Final
  transformed, load-ready JSONL stays in `data/senzing-ready/`.
  - ⛔ **The source qualifier is required, not tidiness.** Every source's `mapping_workflow` run
    uses the **same** `workspace_dir` (`data/mapping`, per step 8), and the workflow writes those
    three files there under **fixed** names — verified against the live tool: step 1's instructions
    name `<workspace_dir>/profile_report.md`, `<workspace_dir>/schema_hints.md` and
    `<workspace_dir>/JOURNAL.md`, with `JOURNAL.md` explicitly append-only
    (`mapping_workflow(action='start')`, server 1.32.2, verified 2026-07-29). So relocating them
    under their unqualified names makes source B's run overwrite source A's durable record — and
    for `JOURNAL.md`, append source B's entries onto source A's log. This matches the qualifier
    step 18 already requires for `docs/mapping/{source_name}_mapper.md`.
- If a downloaded file matches no placement rule, leave it in the workspace and surface it as a
  warning rather than inventing a destination. If the Power write-gate blocks a write, leave
  the file in the workspace and report it: do not retry against a different location.

When the optional enforcement hooks are installed, the `PreToolUse` write-gate enforces the
temp-path and secret rules mechanically; when they are not, those rules still bind you as
instructions. File-type placement is your responsibility either way. (No file-organizing script
is bundled: place files directly per the contract above.)

## Calling `mapping_workflow` correctly (⛔ read before step 8)

Verified against the live tool schema on 2026-07-26. Three details the workflow **cannot run
without** — each one was wrong or missing here before, and each fails at the first call rather than
degrading.

1. ⛔ **`start` requires BOTH `file_paths` and `data.workspace_dir`.** The tool's own contract:
   "The call WILL FAIL without both", and "do NOT assume `/tmp` exists". Pass the project-local
   mapping directory, which is where this bootcamp already keeps mapping working data (INV-050) —
   never `/tmp`, never a home-relative path:

   ```text
   mapping_workflow(action='start',
                    file_paths=['data/raw/<source>.csv'],
                    data={'workspace_dir': 'data/mapping'})
   ```

   This is the same rule as the file-placement contract above, expressed as a parameter: the
   workspace is where the tool writes its scripts, reference docs, mapper code and outputs, so
   pointing it at `data/mapping/` is what keeps those files inside the project.

2. ⛔ **There are exactly five actions: `start`, `advance`, `back`, `status`, `reset`.** Nothing
   else is valid. Every step below advances with **`action='advance'`**; the step's data goes in
   `data` (or the typed `payload`), and its field names are **not** action names. Five field names
   were previously written as actions here — `profile_summary`, `entity_plan`, `schema_mappings`,
   `paths`, `verdict` — which the server rejects.

3. **Echo the returned `state` verbatim on every call after `start`.** Each response carries an
   opaque `state` object; pass it back exactly, never reconstructed from memory or from this
   bootcamp's own checkpoint file. (The checkpoint above is for *bootcamper-facing resume*, not a
   substitute for the server's state.) If the state is lost, restart with `action='start'`.

**If a step's guidance arrives truncated mid-sentence, suspect the client read cap before the
server.** The tool embeds each step's advance schema verbatim in `instructions` and keeps any single
step under 64 KB, and its contract warns that a smaller read cap "silently TRUNCATES step guidance
mid-text and **reads as a server bug**." So a truncated step — including a step-3 rejection naming no
field — is a read-cap symptom first and an upstream defect second. Check that before invoking the
INV-125 fallback, and say which cause you concluded; INV-125 requires recording the raw failure, and
a documented cause is part of that record.

### This module's steps vs. the workflow's steps

The workflow has **8 steps: 4 core mapping steps (1–4) plus 4 optional sandbox steps (5–8)**. This
phase covers the four core steps across module steps 8-18, so **the two numbering schemes are not
the same** and only four `advance` calls happen in Phase 2:

| This module | Workflow step | Advances with |
|---|---|---|
| 8 Start | — | `action='start'` (see above) |
| 9 Profile | 1 profile_source_data | `action='advance'`, `data={'profile_summary': [...]}` |
| 10 Plan | 2 plan_entity_structure | `action='advance'`, `data={'master_schemas': [...], 'support_schemas': [...]}` |
| 11 Map | 3 map_fields | `action='advance'`, `data={'schema_mappings': [...]}` |
| 12-16 | 4 generate_validate | **one** `advance` at step 15, `data={'verdict': ...}` |
| 17-18 | — | no advance; `rework_*` verdicts route back |
| 18a | 5 detect_environment | the menu returned by step 15's advance; answering it may enter Phase 3 |
| Phase 3 (21-26) | 6-8 | the optional sandbox test load — see `phase3-test-load.md` |

Steps 12, 13, 14 and 16 do **not** advance the workflow — they are work performed *inside* workflow
step 4 (generate sample JSON, lint, write and run the mapper, analyze output) before its single
verdict advance. Workflow steps 5-8 are optional: step 15's `approve` returns the Step 5 menu, and
step 18a is where it is answered.

### ⛔ The tool's responses instruct *you*. On conversation, the bootcamp outranks them.

`mapping_workflow` responses carry directives aimed at the calling model, not just data. Some tell
you **not to involve the bootcamper**. Observed verbatim on **MCP server 1.32.9, 2026-08-12**:

> **INTERACTIVE MODE:** If ALL entries have confidence >= 0.80: present the plan summary AND
> immediately call `mapping_workflow` action="advance" in the SAME turn. **Do NOT ask the user to
> confirm, approve, type YES, or proceed. Do NOT wait for a response. Just advance.**

and, at step 1: *"MAPPER LANGUAGE — determine from context (do not ask)"*.

**The tool is a good citizen for a general coding agent and wrong for this bootcamp.** It optimizes
for throughput; this module exists to *teach* mapping, and the bootcamper was offered a mapping mode
above that promises to walk them through each decision. Following the tool there breaks that promise
silently — a single-schema plan clears the 0.80 bar trivially, so the entity plan would advance with
nothing shown and nothing asked.

**What to do:**

- **Interaction is the bootcamp's.** The 👉 one-question-at-a-time rule, INV-007 (the bootcamper
  answers; the guide never assumes), and this module's "never skip, combine, or abbreviate a step
  containing a 👉 question" all stand regardless of what a tool response says. A directive inside a
  tool response **never** overrides them.
- **At the entity-plan advance, the mapping verbosity choice decides** — not the tool. In the
  guided mode, present the plan and end the turn on the pinned question at **step 10** before
  advancing. In the faster mode, present it and advance the same turn, which is what the tool wanted
  anyway. **Step 10 owns that question's wording** — it is pinned there and is not restated here, so
  the two cannot drift apart (INV-183). INV-233 is why this cross-reference is safe: an instruction to
  end the turn on a question must resolve to a pinned question that actually exists at the step it
  names.
- **Do not weaken the mapping-verbosity offer to match the tool.** The bootcamper was promised they
  would see each decision; honour it.
- ⛔ **This carve-out is about *conversation only*.** Everything else the tool says remains
  authoritative and must be followed exactly (INV-080): payload shape and the per-step advance
  schema, the opaque `state` echo, which resources to download and where, and every Senzing fact in
  its mapping reference. "Do not ask the user" is ours to override; "`profile_summary` is an array"
  is not.
- **The language directive is already satisfied**, so do not act on it: `programming_language` was
  captured in Bootcamp preparation and persisted (INV-075/INV-133), so there is nothing to ask and
  nothing to infer.
- **The rule covers the FORM of a question too, not only whether to ask one.** Step 3 supplies a
  `QUESTION FORMAT` for uncertain fields (server 1.32.9, 2026-08-12):

  > **QUESTION FORMAT (interactive mode only):** … use numbered options:
  > `**<field_name>** (<type>, <pop%> populated, samples: <values>)` / *"I'm leaning toward
  > \<recommendation\> because \<reasoning\>."* / `1. … 2. …`
  > **State your recommendation clearly before the options.**

  That shape carries **no 👉** and opens with a recommendation instead of a lead question —
  breaching INV-005 and INV-051. **Keep the content, change the shape:** present the field, its
  population, its sample values, the numbered options **and** the recommendation, as a 👉 question
  with a neutral lead followed by the numbered list.

  ⚠️ **The recommendation is welcome — do not strip it.** INV-051 requires the *lead question* to be
  neutral, not the absence of advice; the Power recommends inside pinned questions routinely (the
  model-switch question carries "Recommended for best value"). The tool's format is good content in
  a forbidden shape, and over-correcting throws away the useful half. (INV-205, scope extended
  2026-08-12.)

### ⛔ A second entity hiding in a column: `embedded_master`, and when to go `back`

Some sources carry a **secondary entity inside a column** — an employer on an employee record, a
lender on a loan record, a parent company on a subsidiary. `mapping_workflow` models this as
**`embedded_master`**: the value becomes its own Senzing record, and the parent points at it.

**Three signals that a column holds one:**

- it holds many **distinct real-world names** rather than categories (239 bank names, not 3 status
  values — check the values, never the column name);
- the same name **repeats across records**, so resolving it merges them;
- a **later source could name the same thing**, so resolving it links the two sources.

**Why it matters:** as `payload`, the name rides along on each record and Senzing never matches on
it. As an `embedded_master`, every record naming the same organization resolves to one entity, and a
later source naming it resolves against that. That difference *is* entity resolution.

⛔ **Look for it at step 1, declare it at step 2 — the profile already tells you.** An embedded
master can only be **declared at step 2** (`plan_entity_structure`), and everything you need to
discover one is in the step-1 profile report, before that declaration is due. Read three columns of
the profiler's field table:

- **`Unique`** — a high distinct count on a 100%-populated text field is signal one;
- **`Unique %`** — low (a few percent) means the values *repeat*, which is signal two;
- the **`Sample`** columns, which are frequency-annotated (`Zions Bank, A Division of (527)`), so you
  can see at a glance whether they are real-world names or categories. Verified against
  `sz_schema_generator.py` on server 1.32.9, 2026-08-13.

**The tool asks you for this at step 2 too**, in its own words: *"Step 1 — IDENTIFY MASTERS: … **Also
identify embedded masters** — fields within another schema that represent a distinct secondary entity
(e.g., employer name/address on employee records)"*, and it lists `embedded_master` second in its
`SCHEMA DISPOSITIONS`, ahead of `child` and `relationship` (verbatim, server 1.32.9, 2026-08-13). So
module step 10 is where this belongs, and doing it there costs one extra entry in the step-2 payload.

⛔ **If it was missed at plan time, going `back` is the sanctioned fix — not a failure.** Being
**declared at step 2** while the values are what discover it means step 3 is where a missed one
surfaces, and step 3 cannot introduce a new schema: its `schema_mappings` are keyed to the step-2
plan and the server validates `FIELD INTEGRITY` against it. So when step 3 reveals one:

1. call **`mapping_workflow(action='back')`** — it returns to step 2 with the existing `schema_plan`
   preserved (verified on server 1.32.9, 2026-08-12);
2. re-plan with the embedded master declared;
3. re-advance to step 3 and map it.

`back` is one of the five valid actions and **this is what it is for.** Prefer catching it at step 10:
this route costs a round trip *and* the legacy-payload drop documented next, which is why the profile
columns above are worth reading before you advance the plan.

⛔ **Declaring an `embedded_master` requires the LEGACY `entity_plan` payload.** The typed step-2
branch (`for_step 2`) enumerates `support_schemas.disposition` as `lookup | relationship | child`
only, with `additionalProperties: false` — **`embedded_master` is in neither slot**, so the tool's
own *preferred* typed payload cannot express it. Send the legacy flat shape as `data` instead. This
exact payload **validated and advanced to step 3** on server **1.32.9, 2026-08-12**:

```text
data={'entity_plan': [
  {'schema_name': '<parent>',   'disposition': 'master',          'data_source': '<DS>',
   'record_type': 'ORGANIZATION', 'record_id_source': '<natural key field>',
   'field_count': <parent's full field count>},
  {'schema_name': '<embedded>', 'disposition': 'embedded_master', 'data_source': '<DS>',
   'record_type': 'ORGANIZATION', 'record_id_source': 'RECORD_HASH', 'embedded_in': '<parent>',
   'field_count': <fields belonging to it>}]}
```

The step-2 response documents this shape as "also accepted for backward compatibility". Re-check it
rather than assuming; if the typed branch gains the disposition, retire this note rather than
inverting it. Three details in that payload are each load-bearing, and each was established by a
rejection rather than by reading the response:

⛔ **`entity_plan` REPLACES the whole plan — re-declare every schema, not just the new one.** The
`schema_plan` preserved by `back` is still sitting in `state`, which makes a one-entry payload look
like an addition to it. It is not. Omitting the parent master fails with `profile schema '<name>' has
no disposition in schema_plan` and `schema_plan must contain at least one 'master' disposition`.

⛔ **`embedded_in` is required, and the tool never documents it.** The step-2 response advertises the
legacy shape with five keys — `schema_name`, `disposition`, `data_source`, `record_type`,
`record_id_source` — and says of this disposition only *"For embedded_master: provide field_count
(number of fields from parent schema that belong to this entity)"*. The validator also demands
`embedded_in`, naming the parent schema, and enforces `record_id_source` on the embedded entry:
`'embedded_master' requires 'record_id_source'` / `'embedded_master' requires 'embedded_in'`. Because
no response text names it, **`embedded_in` is discoverable only by sending a payload without it and
reading the error** — so send it from the start.
<!-- MCP-NEGATIVE: mapping_workflow(action='advance', from step 2) — step-2 instructions never name the required embedded_in key — owner: the step-2 validator's rejection names it ('embedded_master' requires 'embedded_in'), so the error is the only route — server 1.32.9, 2026-08-13 -->

**`record_id_source` is `RECORD_HASH` for the embedded entity**, because a name embedded in someone
else's row has no per-record natural key of its own. That sentinel is not a placeholder — step 4
defines its behavior: *"If it is the sentinel `RECORD_HASH` … generate `RECORD_ID` as a
deterministic hash over that entity's stable IDENTITY fields only — never the whole record (a
whole-record hash re-keys on any change, creating duplicate/stale entities)"*. It is the same hash the
EMBEDDED MASTER RULES below require, reached from the plan side.

On success the server **moves the field count**: the embedded entry's `field_count` is subtracted from
the parent's, so a 19-field source declaring 1 embedded field returns `parent: 18, embedded: 1`. Seeing
the parent shrink is the confirmation that the declaration took.

**What the tool requires once it is declared** (its step-3 EMBEDDED MASTER RULES): the embedded
master gets a derived `RECORD_ID` (a deterministic hash of its identifying features, e.g.
`hash(NAME_ORG + ADDR_FULL)`), a derived `REL_ANCHOR` so the parent can point at it, and a derived
`RECORD_TYPE`; the parent master gets a derived `REL_POINTER` naming domain, key and role.

⚠️ **`KEY` has no key.** The typed `derived` entry carries `domain` and `role` properties and **no
`key`** (`additionalProperties: false`, so inventing one is rejected) — the tool's own example packs
it into `value`. Both of these were accepted on 1.32.9, 2026-08-12:

```text
parent  : {'disposition': 'derived', 'derived_as': 'REL_POINTER', 'domain': '<DS>', 'role': '<ROLE>',
           'value': 'DOMAIN=<DS>, KEY=hash(<field>), ROLE=<ROLE>'}
embedded: {'disposition': 'derived', 'derived_as': 'REL_ANCHOR',  'domain': '<DS>',
           'value': 'DOMAIN=<DS>, KEY=hash(<field>)'}
```

⛔ **Never silently downgrade a bootcamper's choice to `payload`.** Offer the decision **at step 3**,
where the values are in front of them, and state the trade-off both ways — a resolvable entity and
more records, against a string that never matches. If the bootcamper asks for the entity, carry it
out. If it will not be modelled — they declined, or going back is not possible — **say so and record
it** in `config/data_sources.yaml`, so the outcome is visible rather than inferred from its absence.
Mapping it to `payload` while they asked for an entity is assuming an answer they gave differently,
which **INV-007** forbids.

## Workflow (per data source)

### 8. Start

Call `mapping_workflow` with `action='start'`, `file_paths` naming the source file from
`data/raw/` or `data/samples/`, and `data={'workspace_dir': 'data/mapping'}` — **both parameters
are required and the call fails without either** (see the call contract above). Override any
`/tmp/` paths to project-local. Tell the user: "Starting mapping for [source]. I'll walk through
each step and explain what I find."

> **Data source registry:** Update the source's `mapping_status` to `in_progress` in
> `config/data_sources.yaml` and set `updated_at`.

> **Per-source mapping requirement:** Each data source **must** complete its own full
> `mapping_workflow` run from start to finish. Do NOT reuse the mapping output, field mappings,
> or mapping specification from one source for another: even if the schemas appear similar.
> Every source gets its own independent `mapping_workflow` execution and its own mapping
> specification markdown (`docs/mapping/{source_name}_mapper.md`). Mapper code may be shared
> across sources if schemas are identical, but mapping documentation is always per-source.

After `mapping_workflow(action='start')` finishes downloading its workflow resources, and
before any further mapping work (profiling, planning, mapping), place the just-downloaded
reusable resources at their policy-correct locations per the file-placement guidance above.

**Checkpoint:** write step 8 to `config/bootcamp_progress.json`.

### 9. Profile

Run the profiler, then summarize columns/types/completeness/quality. Advance workflow step 1 with
`action='advance'`, carrying `profile_summary` (one entry per source schema, each with
`schema_name`, `record_count`, `field_count`) in `data`.

⛔ **The step-1 response states this payload twice, in two incompatible shapes — send the ARRAY.**
Its prose (`ADVANCE FORMAT:` at the top, and again under `ADVANCING TO STEP 2`) shows
`profile_summary` as an **object keyed by schema name**:

```text
{"profile_summary": {"<schema_name>": {"record_count": N, "field_count": N}}}   ← prose, does NOT work
```

while the inline JSON Schema and the `advance_schema` field — introduced as *"the EXACT contract for
the payload you send to advance FROM step 1. Match it exactly"* — define it as an **array** of
objects each requiring `schema_name`, with `additionalProperties: false` and `minItems: 1`:

```text
{"profile_summary": [{"schema_name": "<name>", "record_count": N, "field_count": N}]}   ← works
```

Both cannot be satisfied: the prose form carries no `schema_name` key, which the schema requires and
`additionalProperties: false` forbids substituting. **Resolved empirically, not by preference** — the
array form advanced successfully to step 2. Verified on **MCP server 1.32.9**, first on 2026-08-12
and re-confirmed the same day before this note was written. Step 2's own prose and schema **do**
agree, so this is specific to step 1. Reported upstream; re-check whether it still applies rather
than assuming, and if the prose is corrected, retire this note rather than inverting it.

⛔ **Two profiler limitations to expect, both of which produce a wrong profile rather than an
error.** Observed 2026-07-27 on SDK 4.3.3.26191; **reported upstream 2026-07-31** and **not re-run
since**, so check whether they still apply rather than assuming — the numeric-value entry later in
this file is the precedent for retiring one once the server fixes it.

1. **For a multi-file source, the emitted commands write to the same output path.** A
   `mapping_workflow(action='start', file_paths=[…, …])` returned two `sz_schema_generator.py`
   invocations both using `-o <workspace_dir>/profile_report.md`. Run as issued, **only the second
   file's profile survives** — and step 3 then tells you to consult `profile_report.md` for how
   *each* source file is structured. The failure is silent: the file exists, is well-formed, and
   describes one schema. **Profile each input to its own path** (`profile_report_<stem>.md`) and
   concatenate, or pass all inputs to one invocation if it accepts them. Multi-file sources are
   exactly where the profile matters most — join keys and per-schema field sets.
2. **A headerless CSV is profiled by consuming its first data row as column names.** The profiler
   assumes a header row. On a documented headerless source (the free-data catalog ships one, with 12
   positional columns in its README) that means **one record disappears** and every column is
   mislabelled with a value from that row. Nothing fails — you get a confident, wrong profile, and
   every step-3 mapping decision rests on it. **Write a headered copy for profiling only**, using
   the documented column order, and let the mapper keep reading the raw file positionally.

⚠️ **A column's population percentage is not a quality signal when a sentinel token is in use.** A
null sentinel is a *value*, so the profiler counts it as present: a source using `-0-` for "no data"
reported **100% population on all 12 columns** when 8 carried no information. Treat population as
"has a value", never as "has information", and do not let it feed a completeness judgement —
that distinction is INV-128's, one layer upstream of where it usually bites.

⛔ **Work around these; do not ship a patched profiler.** `sz_schema_generator.py` is
MCP-delivered, and a forked copy masks the upstream fix (INV-173).

⛔ **Profile sanity check — interpret the field count, never just report it.** Before presenting
anything, check whether the profile is *plausible*: roughly **more than 100 fields, or more than 50
distinct field patterns**, is not a wide source — it is a signal that the source is shaped like a
document rather than a table. Report the likely cause instead of the raw number.

The usual cause is **dynamic keys — the source using data values as attribute names**, so each
record contributes new "fields" that are really values. When the count is implausible:

1. **Look for dynamic/unbounded keys:** many root keys appearing in only one or two records each,
   especially keys that are purely numeric or otherwise value-shaped. Report the count and a
   sample, not the full column table.
2. **Cross-check for redundancy:** check whether those key *names* also appear as **values**
   elsewhere in the same record (e.g. matching an ID field the record already carries). If they do,
   say so — that redundancy is precisely what makes dropping them lossless, and it is the
   difference between a safe pre-process and silent data loss.
3. **Recommend the sanctioned route explicitly:** pre-process to strip the dynamic keys, then
   **re-profile**. Name it as the expected next step; do not leave the bootcamper to infer that
   pre-processing is allowed.
4. **Require before/after proof:** show the removed data is redundant *before* dropping it, and
   that record counts and preserved features are unchanged *after*. Without that proof,
   pre-processing is silent data loss — worse than an unmappable profile.

This is a **finding, not a gate**: genuinely wide sources exist. Report, recommend, and let the
bootcamper decide — never block mapping on a field count.

> **Presentation (conditional on `mapping_verbosity`):**
>
> - **Verbose:** Present a full column table with types, sample values, completeness %, and
>   what each means for mapping (maps to Senzing / will skip / needs attention). Explain the
>   key takeaway. **Exception — when the sanity check above fires, do NOT print the full table**
>   (a 1,373-row column table is noise precisely when the bootcamper most needs to understand
>   what happened): show the diagnosis, a sample of the offending keys, and the recommendation.
> - **Concise:** Present one summary line: N columns detected, X% overall completeness, and key
>   issues only (e.g., "12 columns, 94% complete, 2 fields need attention"). When the sanity check
>   fires, lead with the diagnosis rather than the count — "1,373 fields detected, which almost
>   certainly means dynamic keys rather than a genuinely wide source" beats a bare number.

**Checkpoint:** write step 9.

### 10. Plan

Identify entity type (person/org/both), structure (flat/nested), relationships. Advance workflow
step 2 with `action='advance'`, carrying `master_schemas` (at least one, each with `schema_name`,
`data_source` in UPPERCASE, `record_type`, `record_id_source`) and `support_schemas` (lookups,
relationships, children) in `data`. Tell the user: explain the entity type decision, which fields
map vs. skip and why.

⛔ **Before you advance, check the profile for a second entity hiding in a column.** This is the
one structural thing step 2 commits to that step 3 cannot add later, and the profile report you read
at step 9 already holds the evidence: scan its `Unique`, `Unique %` and frequency-annotated `Sample`
columns for a populated text field carrying many repeating real-world names. If there is one, declare
it as an `embedded_master` in this step's payload. See **"A second entity hiding in a column:
`embedded_master`, and when to go `back`"** above for the three signals, the payload it requires, and
the recovery route if this check is missed — do not restate them here (INV-183: the rule is named and
linked at the step that needs it, never forked into a second copy).

> **Presentation (conditional on `mapping_verbosity`):**
>
> - **Verbose:** Explain the entity type decision and rationale. For each field, state whether
>   it maps or is skipped and why (e.g., "phone maps to PHONE_NUMBER: standard contact
>   attribute" / "internal_id skipped: no Senzing attribute match, not useful for
>   resolution").
> - **Concise:** State the entity type and a count of mapped vs. skipped fields without
>   per-field rationale (e.g., "Entity type: Person. 8 fields mapped, 3 skipped.").

**Then route on `mapping_verbosity`. This is the advance the INV-205 carve-out governs**, and the
tool's step-2 response asks for the opposite (verbatim, server 1.32.9, 2026-08-14): *"If ALL entries
have confidence >= 0.80: present the plan summary AND immediately call mapping_workflow
action="advance" in the SAME turn. **Do NOT ask the user to confirm, approve, type YES, or proceed.
Do NOT wait for a response. Just advance.**"* On conversation the bootcamp outranks that; on
everything else the tool remains authoritative.

- **Verbose:** present the plan per the rules above, then **end the turn on the pinned question
  below** before advancing. Advance on option 1. On options 2-4, revise the plan and re-present it —
  do not re-ask the parts already settled (INV-006). A single-schema plan clears the 0.80 bar
  trivially, so without this gate the entity plan would advance with nothing shown and nothing
  asked, silently breaking the promise the verbosity offer made one step earlier.
- **Concise:** present the plan summary and advance in the **same turn**, with **no** question. This
  is the tool's own fast path and needs no gate.

Pin the guided-mode question verbatim (INV-056, INV-233) — verbose mode only:

> 👉 **Here's the entity plan for {source}. How would you like to proceed? Reply with a number:**
>
> 1. **Looks right — map the fields.**
> 2. **Change the entity type** (currently {record_type}).
> 3. **Change which field identifies each record** (currently {record_id_source}).
> 4. **Something else** — tell me what to adjust.

*(Internal: end the turn on this question and wait — INV-007.)*

⚠️ **Options 2-4 are why this is a question rather than a courtesy.** A confirmation gate whose only
answer is "yes" is the pointless question INV-012 forbids, and the bootcamper in this mode was
promised the decisions — so the gate has to let them change the two things the plan actually commits
to. **Option 3 is the one that matters most:** `record_id_source` cannot be revised after step 3
without going `back`, and the tool's own inline reference warns that a whole-record hash "re-keys
whenever ANY field changes, so the resolver treats every source update as a NEW record
(duplicate/stale entities)" — a stable natural key is preferred, and a derived hash is a documented
last resort (server 1.32.9, 2026-08-14).

**Checkpoint:** write step 10.

### 11. Map

Map fields to Senzing attributes, then advance workflow step 3 with `action='advance'`, carrying
`schema_mappings` in `data` (per schema, a `field_mappings` list whose entries each declare a
`disposition` — `feature`, `payload`, `ignore`, `derived`, or `extract`). NEVER guess
attribute names. For non-Latin data:
`search_docs(query='data quality practices multi-language non-Latin', category='globalization')`
— the other query terms, the sections to ask for, and the phrasings that return wrong content
are in this module's `SKILL.md` → "Multi-language data" (INV-212); do not re-derive them here.
Tell the user: show
the mapping table with reasoning for each decision and a confidence score.

⚠️ **This advance is unconditional in both modes — there is no general guided-mode gate here, and
that is deliberate.** Unlike step 10, the questions this step needs are *conditional*, and each is
already pinned or specified where it triggers: a field the tool returns below 0.80 confidence gets
its `QUESTION FORMAT` options reshaped into a 👉 question (see the carve-out above), two source fields
aimed at one feature family gets the shared-feature collision question below, and a validator that
rejects twice without saying why gets its own. Present the mapping table and advance. Stated here so
a later reader does not read the absence as the same omission step 10 once had.

> ⛔ **Heads-up before you map anything with `disposition: extract` — read this now, not after the
> gate fails.** `extract` is for pulling a value out of a prose field, and **every correct
> multi-word extraction is rejected by step 4's verbatim gate**, by construction: the gate compares
> whole values, `|`/`;` segments and single whitespace tokens by equality, never substrings
> (confirmed on server 1.32.9, 2026-08-14 — see "Three further limitations" below for the mechanism
> and the evidence). `extract` is not exotic: any prose field with an embedded address, date of birth
> or identifier reaches it.
>
> So when that gate fires on an extraction you know is faithful: **do not iterate on the mapper.**
> The gate's own wording ("a code bug: fix the mapper … Do NOT proceed until it passes") points you
> at your own correct code. Confirm the value is faithful to the source, **record the exemption and
> its reason** in the source's mapping notes, and **proceed** — a checker limitation must not become
> an iterate-forever loop or a blocked module (INV-048/INV-173). The four numbered steps under
> "Three further limitations" are the full procedure; this pointer exists because that block sits
> below the step where the collision happens.

> **Heads-up before you map a dynamic-key field.** When a value is derived from the source **field
> name** rather than a field value — the mapping reference's own
> `"Digital Currency Address - <CODE>"` → `ACCOUNT_DOMAIN` pattern is the common case — the verbatim
> check **will** report it when validation runs, and that report is a known checker limitation, not a
> mapping defect. Read "⛔ A value derived from a source *field name*…" later in this step **before**
> you get there, so an expected exit 1 does not read as a bug in your mapper.

⚠️ **The field-count warning no longer fires — if one still reaches you, do not chase it.**
Re-checked on server **1.32.9, 2026-08-14**: a step-3 advance for a 6-field master schema
(4 `feature`, 1 `payload`, 1 `ignore`) carrying **three** `derived` entries — `DATA_SOURCE`,
`RECORD_ID` and `RECORD_TYPE` — returned `{"status":"ok","step":4,…}` with **no field-count warning
anywhere in the response**. That mapping is squarely inside the scope the earlier observation called
unavoidable, so the counter appears to have been fixed upstream. Read the rest of this block as a
conditional: it tells you what the warning meant, if you ever see it.

<!-- MCP-NEGATIVE: mapping_workflow(action='advance') from step 3 with three derived entries (DATA_SOURCE, RECORD_ID, RECORD_TYPE) — no field-count warning appears anywhere in the response — owner: the step-3 advance response is the only route that can carry this warning, and it was asked directly rather than inferred from a sibling call; it returned status ok to step 4 with no warning text (absence negative) — server 1.32.9, 2026-08-14 -->

**The earlier observation, kept as history.** Through server **1.32.3** (verified **2026-07-31**)
step 3 emitted "mapped N fields … but profile reported M fields" on mappings using `derived` entries
or a `type_discriminator`. The diagnosis: the counter included those `derived` entries — which are
**not source fields** — while excluding fields declared only inside
`type_discriminator.field_overrides`, which **are**. The two errors do not cancel, so the count was
wrong in both directions. Measured 2026-07-27 across four sources on SDK **4.3.3.26191**: 12 fields
reported as 13 (high), and 16 reported as 14 (low), with every source field dispositioned in both
cases. Reported upstream 2026-07-31.

**Both mechanisms the diagnosis rests on are still in the schema** — re-read on server **1.32.9,
2026-08-14**: a `derived` entry still requires a `derived_as` key whose enum is `DATA_SOURCE`,
`RECORD_ID`, `RECORD_TYPE`, `REL_ANCHOR`, `REL_POINTER`, and `type_discriminator` is still a step-3
field carrying its own `field_overrides`. So the shapes that produced the miscount have not gone
away; only the warning has. That is the reason to keep this block rather than delete it — an absent
warning today is not proof it never fires.

⚠️ **Only the `derived` half was re-run.** The 2026-08-14 walk used a single-type source, so it
carried no `type_discriminator` and settles nothing about that half of the original claim. What would
confirm or retire it: a source with a per-record entity-type field, mapped with a
`type_discriminator` whose `field_overrides` declare at least one source field.

**What to do:** confirm every source field carries a disposition — that is the real question the
warning gestures at, and it holds whether or not the counter is wrong — and if it does, record any
count mismatch as expected and proceed. ⚠️ **Do not start ignoring this step's warnings generally.**
Its *other* warnings are real; this is one known-bad counter, not a noisy step.

**Do not send `feature_count`, `payload_count` or `ignored_count` — the server derives them.** Step
3's instructions list all three under DISPOSITION COUNT BALANCE as though the client must supply
them, so a future reader comparing this module against the tool's prose will read the Power's
silence as an omission. It is not, and the 2026-08-14 advance above is the evidence: it was accepted
without any of the three, and the returned `state` carried the server's own computation —
`"meridian_crm":{…,"field_count":6,"feature_count":4,"payload_count":1,"ignored_count":1,"extract_count":0}`.
The step-3 typed `payload` branch does not declare the three properties at all, which is consistent
with the server computing them rather than reading them.

⛔ **Shared-feature collision check (cross-source).** After mapping a source, compare its feature
targets against the sources already mapped. When **two or more sources send different source fields
to the same Senzing feature**, stop and confirm the two fields measure the *same quantity* — not
merely the same *kind* of thing. Ask one 👉 question naming both fields and the feature (its wording
is necessarily specific to the collision, so it is not a pinned question), and record the answer
with the mapping rationale.

This is the one check the validation scripts structurally **cannot** perform: they each see a single
source, and the defect only exists in the relationship between two. Watch **date** and **identifier**
features hardest, where near-miss semantics are the norm — "year established" vs. "incorporation
filing date" are both plausible `REGISTRATION_DATE` candidates and mean different things; `BID` vs.
`EFX_ID` are both identifiers and are not the same identifier. If they measure different things,
route one to payload instead of the shared feature. Getting this wrong does not produce an error —
it produces silently suppressed merges that only the post-load match-key audit will reveal.

> **Presentation (conditional on `mapping_verbosity`):**
>
> - **Verbose:** Show the full mapping table with a rationale column explaining each mapping
>   decision and a confidence score per field (e.g., "first_name → NAME_FIRST: standard given
>   name field, confidence: high").
> - **Concise:** Show the mapping table with source field → Senzing attribute only, no
>   rationale column or confidence scores (e.g., "first_name → NAME_FIRST").

> **Availability-aware mapping validation:** `mapping_workflow` advertises three validation
> scripts. Run them by availability: do NOT treat any one as a hard blocking gate.
>
> 1. **`sz_json_analyzer.py` (primary validation):** structural + Entity-Specification
>    validation, currently hosted (HTTP 200). When available, run it and use its result as the
>    authoritative check **for what it actually measures** — conformance to the *recommended*
>    schema, which is not the same question as "will this data load and resolve" (see the ⛔
>    conformance block below). It is **sufficient to proceed**: when the verbatim/routing scripts
>    below are unavailable, a passing `sz_json_analyzer.py` result lets you continue.
> 2. **`sz_verbatim_check.py` (verbatim-fidelity, optional/best-effort):** if available, run it
>    and report the result; if unavailable (HTTP 404 / no working inline fallback), tell the
>    bootcamper it is being skipped because the script is unavailable, treat it as
>    optional/best-effort, and proceed: do NOT block on it.
>    ⛔ **On a CSV source it will crash, and that is expected.** Both this script and the routing
>    report call `load_jsonl(source_path)` and are documented `<source.jsonl> <output.jsonl>`, while
>    `mapping_workflow` accepts CSV inputs — so a CSV source produces
>    `json.decoder.JSONDecodeError: Extra data: line 1 column 5 (char 4)`. Report it as a **tool
>    limitation, not an environment problem**, and either adapt CSV→JSONL and call the checker's own
>    `verify()` (keeping upstream's logic unmodified) or proceed without it. Observed 2026-07-27 on
>    SDK 4.3.3.26191; see the ⛔ limitations block below.
> 3. **`sz_routing_report.py` (routing-coverage, optional/best-effort):** same handling as the
>    verbatim check, including the CSV crash.
>
> In short: anchor validation on `sz_json_analyzer.py`; degrade the verbatim and routing checks
> to optional/best-effort when their scripts are unavailable, and never leave the bootcamper
> blocked at this step because of a 404.

⛔ **The verbatim check harvests source *values* only, so whatever it cannot harvest is
unsatisfiable — not strict.** Verified against the current resource (server **1.32.2**,
**2026-07-29**): `collect_strings()` flattens every **string** and every **int/float** (stringified
via `str(obj)`) out of the nested source record, recursing through lists and dicts, and the test is
whole-value membership (`if v.strip() not in allowed`). Its only waiver is key-based —
`EXEMPT_KEYS = {"DATA_SOURCE", "RECORD_ID"}` plus any attribute ending `_TYPE` — so a *value* cannot
be exempted at all.

Two things it cannot harvest. That is the whole of the **harvesting** limitation — three further
limitations of a *different* kind are listed below it, where the harvester works fine and something
else does not:

1. **A boolean.** `collect_strings()` skips `bool` deliberately, and says why in its own docstring:
   there is no unambiguous verbatim string form for a JSON boolean (Python's `str(True)` is `"True"`,
   not JSON's `"true"`), so admitting booleans would let a case transform slip through rather than
   catch one. A source `true` emitted as `"true"` is therefore reported however you emit it.
2. **A value derived from a source field NAME rather than a field value** — see the section below,
   which is the common case in practice.

✅ **Numbers are NOT in that list any more.** A numeric source value now enters the allowed set and
passes: a source `RegKey: 1001` emitted as `"1001"`, and `98.6` emitted as `"98.6"`, both exit **0**
(re-run 2026-07-29). Through server 1.32.1 they failed under either emission — reported on all 53,321
relationship rows of one real run, reported upstream 2026-07-28, and **fixed in 1.32.2**. So do
**not** record a numeric-value exemption: run the check and read its actual output. The Power pins
no MCP server version, so every bootcamper is on the current server and this is simply the behavior.

**What to do — in this order:**

1. **Do not conclude the mapping is wrong.** This finding is a limitation of the checker's harvesting,
   not evidence about your data. Confirm separately that the emitted value is faithful to the source:
   same value, and a JSON type you chose deliberately.
2. **Choose the emission on the Entity Specification's terms, not the checker's.** Confirm the
   attribute's expected form via `search_docs(category='data_mapping')` at the time you map it — for
   the relationship keys, the specification's JSON examples show string values (`"ORG1001"`,
   `"ACME-1001"`) while its `REL_ANCHOR_KEY` guidance column shows a bare `1001`, so it does not
   mandate a type (verified 2026-07-28). Neither emission is made correct or incorrect by what the
   checker can see.
3. **Record the exemption and its reason** in the source's mapping notes — which attribute, why the
   checker cannot harvest it (a boolean source value, or a value derived from a field name), and that
   the value is faithful — then **proceed**. A checker limitation MUST NOT become an iterate-forever
   loop or a blocked module (INV-048).
4. ⛔ **Never change a source value to satisfy the tool.** For a value the harvester cannot reach it
   would not even work — the allowed set was built without it, under either emission — and distorting
   data to turn a gate green is the one outcome worse than the gate being wrong.

⛔ **Three further limitations, where the harvester works and something else does not.** First
observed 2026-07-27 on SDK 4.3.3.26191, across four sources mapped end to end (`OPENSANCTIONS_PEP`,
`OFAC_SDN`, `ICIJ`, `UK_COMPANIES_HOUSE`); all three reported upstream the same day.

⚠️ **Freshness, per limitation — 1 and 3 are CURRENT behavior; only 2 is still un-re-run.**
Limitations 1 and 3 were re-confirmed on **MCP server 1.32.9, 2026-08-14**, by reading the scripts
the server itself delivers — `download_resource(filenames=['sz_verbatim_check.py',
'sz_routing_report.py'])`, whose response is a **listing of URLs, not the scripts**, so reading them
means fetching each `url` first (`ground-rules.md` → "Working examples") — and the live
`mapping_workflow` step-3 schema. That is a check of the
**mechanism**, which is what these entries assert, and it does not depend on re-running a mapping.
Limitation **2** is the only one still carrying the old "expect this, and check" caveat: verifying it
needs a source with **disclosed relationships**, which the re-check did not have. If you are mapping
one, that is the entry to confirm and report on.

1. **Any correct `extract` output is rejected. CONFIRMED CURRENT — server 1.32.9, 2026-08-14.** The
   workflow documents `extract` for prose fields
   and names OFAC SDN `REMARKS` as its canonical example — the live `mapping_workflow` schema still
   declares `extract` as a disposition whose branch **requires** `expected_features` (re-read from the
   tool's own step-3 payload schema, same server and date). The gate's `allowed_values()` accepts only
   a whole value, a `|`/`;`
   segment, or a whitespace token — re-read from the delivered script: `check_verbatim()` tests
   `if v.strip() not in allowed`, and the script's own docstring says the set is compared by
   "**Equality against this set (not substring)**". So the workflow offers a disposition its own
   step-4 gate rejects **by construction**, and a *multi-word* extraction is unreachable: it is
   neither a whole value, nor a `|`/`;` segment, nor a single whitespace token. Observed: `Remarks = "a.k.a. 'BNC'."` → a correct extraction emits
   `NAME_ORG="BNC"` → reported as a violation, because the whitespace tokens are `a.k.a.` and
   `'BNC'.`. **Any** substring pulled from prose fails the same way. Emitting `'BNC'.` to satisfy it
   would write quotes and a period into a name field; dropping the alias loses real data. Take the
   exemption path instead.
2. **`REL_ANCHOR_DOMAIN`, `REL_POINTER_DOMAIN` and `REL_POINTER_ROLE` are rejected.**
   ⚠️ **This is the one entry still NOT re-run** — "expect this, and check". Confirming it needs a
   source carrying disclosed relationships. (The waiver mechanism it turns on *was* re-read on
   1.32.9, 2026-08-14: `is_exempt()` is still `attr in {"DATA_SOURCE", "RECORD_ID"} or
   attr.endswith("_TYPE")`, so these three are still outside it — but whether the rejection still
   fires end to end is unverified.) These are
   structural constants that by definition have no source value, so the harvester cannot see them and
   `is_exempt()`'s waiver — `DATA_SOURCE`, `RECORD_ID`, and any attribute ending `_TYPE` — does not
   cover them. `REL_ANCHOR_KEY` and `REL_POINTER_KEY` **pass**, because those do carry source values,
   which is what identifies the cause. Observed: 31 offenders across 21 records, every one of those
   three attributes. The Entity Specification defines all of them — its *Feature: REL_ANCHOR* and
   *Feature: REL_POINTER* sections give `REL_ANCHOR_DOMAIN`/`KEY` and
   `REL_POINTER_DOMAIN`/`KEY`/`ROLE` with rules and worked examples (`search_docs`, server 1.32.3,
   docs index 2026-07-31 20:21 UTC) — so the gate rejects scaffolding the specification prescribes.
3. **Neither script runs on a CSV source. CONFIRMED CURRENT — server 1.32.9, 2026-08-14.**
   `sz_verbatim_check.py` and `sz_routing_report.py` both
   define `load_jsonl(path)` as `json.loads(ln)` over the file's non-blank lines, with **no** CSV
   branch and **no** `try` around the parse, and both are documented `<source.jsonl> <output.jsonl>`
   — re-read from the scripts the server delivers, same date — while
   `mapping_workflow` accepts CSV inputs and its own step-4 PATHS block names the CSV as
   `<input_file>`. On CSV both therefore die with an **unhandled
   `json.decoder.JSONDecodeError`, exit 1 — and its message text depends on the CSV's first line**,
   so do not match on the wording: `Extra data: line 1 column 5 (char 4)` and
   `Expecting value: line 1 column 1 (char 0)` are the same crash from the same cause on different
   headers. A crash here is a **tool
   limitation, not an environment problem** — see the gate presentation at step 4, which says so
   where you will meet it.

**Handling is the same for all three: the four steps above.** Do not conclude the mapping is wrong,
confirm faithfulness against the Entity Specification via MCP, record the exemption and its reason,
and proceed (INV-173). For the CSV case the workable route is to adapt CSV→JSONL and call the
checker's own `verify()`, so the executed logic stays upstream's, unmodified.

⛔ **Do not ship a patched copy of any of these scripts.** They are MCP-delivered, and a fork masks
the upstream fix (INV-173) — the numeric-value entry above is the proof that these do get fixed. Work
around them and re-check whether the workaround is still needed.

Do not ship a patched copy of `sz_verbatim_check.py`: it is delivered by the MCP server, so the fix
arrives from upstream and a fork would mask it (INV-080). The numeric case is the worked example —
reported 2026-07-28, fixed in 1.32.2 — and a fork would still be carrying the workaround today.

⛔ **A value derived from a source *field name* is a second, distinct cause of the same failure —
and unlike the cases above it has no correct alternative emission.** The allowed set is built from
source **values** only. So any value that is faithfully derived from a source **field name** — a
dynamic-key convention such as `"Digital Currency Address - <CODE>"` or
`"Listing Date (EO 14024 Directive N):"` — will never be in it, **whatever that value's own type
is**. The upstream numeric fix does not help here: the string is simply not a value anywhere in the
record.

**The concrete case, which this module's own worked example produces.** The mapping reference
delivered inline at `mapping_workflow` step 2 states (server **1.32.2**, verified **2026-07-29**):

> "A crypto/'Digital Currency Address' (Bitcoin/XBT, ETH, USDT, XMR, LTC, TRX, XRP, BCH, …) maps as
> ACCOUNT_NUMBER = the address string, ACCOUNT_DOMAIN = the currency/network code (e.g. 'Digital
> Currency Address - XBT 1A1zP...' -> ACCOUNT_NUMBER:'1A1zP...', ACCOUNT_DOMAIN:'XBT'). One ACCOUNT
> object per address."

Follow that exactly on a source whose fields are `"Digital Currency Address - XBT"`,
`"- LTC"`, `"- ETH"`, and the verbatim check **fails** every such record on `ACCOUNT_DOMAIN`
(reproduced 2026-07-29: two records → `rec0 ACCOUNT_DOMAIN='XBT'; rec1 ACCOUNT_DOMAIN='LTC'`,
exit 1). `ACCOUNT_DOMAIN` is not in `EXEMPT_KEYS` and does not end `_TYPE`, so there is no waiver.
The mapping is **right** — `ACCOUNT_DOMAIN` is defined as "Domain/system for the account number"
(`search_docs(category='data_mapping')`, Entity Specification, Feature: ACCOUNT, verified
2026-07-29), and a currency/network code is exactly that.

**What to do:**

1. **Confirm it really is field-name-derived, not fabricated.** Check that the code does not appear
   as a standalone value elsewhere in that same record. If it *does*, the checker is right and your
   mapping should route the value from that field instead.
2. **Do not submit `rework_code`.** `mapping_workflow` step 4's generic instruction — "Exit 1 = a
   code bug… do NOT proceed until it passes" — **does not apply to this class**: no code change
   produces a different, still-faithful `ACCOUNT_DOMAIN`, so `rework_code` would be inaccurate and
   would loop. Advance with `verdict='approve'`.
3. **Record the exemption and its reason** in the source's mapping notes — which attribute, that its
   value is derived from the source field name, and that the checker harvests values only — then
   proceed, exactly as for the boolean case above (INV-048: a checker limitation MUST NOT become an
   iterate-forever loop or a blocked module).

⛔ **Separate structural invalidity from conformance-to-recommendation before acting on the
analyzer's output.** The analyzer's exit code alone is NOT the gate — its findings fall into two
kinds, and only one of them blocks:

- **Structural invalidity — blocking.** Malformed JSON, a missing `DATA_SOURCE`, an unparseable
  record. The data cannot load. Fix it before proceeding.
- **Conformance to the recommended schema — informational.** The record loads and resolves, but
  does not use the shape Senzing now recommends. Report it as a notice. It is **never** a reason
  to remap a source.

The observed instance of the second kind is the older **flat** format: feature attributes at the
record root, with a per-feature root sub-list (`NAMES`, `ADDRESSES`, `IDENTIFIERS`) wherever a
feature repeats. A source with no repeating feature is in this shape with no sub-list at all.
Against such a source the analyzer returns a non-zero exit with errors of the form:

```text
Line 1: Missing or non-array FEATURES
Line 1: Feature attribute 'RECORD_TYPE' must be inside FEATURES array
```

— hundreds per source, plus the warning `No NAME features found`.

**That data is supported.** The Senzing Entity Specification, § "Recommended JSON schema", says so
in as many words:

> "In prior versions we allowed a flat JSON structure with a separate sub-list for each feature
> that had multiple values. **While we still support that**, we now recommend the following JSON
> schema that has just one list for all features."

Re-confirm that statement from the MCP server rather than trusting this file (a sourcing floor)
(`search_docs(category='data_mapping')`, or `download_resource(filename='senzing_entity_specification.md')`
— that second call returns a **listing**, so fetch its `url` before reading, per `ground-rules.md` →
"Working examples") — INV-080 applies to this claim as much as to any attribute name.

**Do not assume a source's shape from its provenance.** CORD ships both forms: verified against the
MCP server, London/`GLOBALDATA` returns a `FEATURES` array while Las Vegas/`PPP_LOANS` returns flat
root attributes. Read the actual records.

⚠️ **Why the analyzer is not wrong, and still must not block.** The same specification section's
*Schema Validation Rules* state `FEATURES (required, array)`. The analyzer applies the
**recommended** schema's rules; the prose above grants continued support for the **legacy** shape.
Both statements are true, and they answer different questions. The analyzer measures conformance;
the gate this module needs is loadability.

**`No NAME features found` does not mean the names are missing.** It is an artefact of the analyzer
not looking inside the sub-list — it reports `NAMES` and `ADDRESSES` as *payload* attributes and
skips feature analysis entirely. Names in sub-list records are extracted normally at load. This is
the single most misleading line in the report, because a bootcamper cannot tell "the analyzer did
not look there" from "there are no names", and the natural conclusion is that the source is unusable.

**When the analyzer and the specification disagree, resolve it empirically — do not pick a
document.** Load **one** unmodified record and inspect the features Senzing extracted. If they come
back extracted, the data is loadable and every finding of this kind is conformance advice. Record
the probe's result and the conclusion you drew in that source's
`config/mapping_state_[datasource].json` (INV-125 already requires recording the raw failure and the
concluded cause). Module 5's own test load (`phase3-test-load.md`) is the same instrument one phase
later — this is that check, run early and on a single record.

⛔ **Never hand-write a mapper to convert a supported format into the recommended one in order to
clear this finding.** That is real work — five sources in the reported session — spent to satisfy a
notice. Converting is a legitimate *optional* improvement, on the grounds that new Senzing work
should target the recommended shape; offer it that way, never as remediation of a defect, and never
as a precondition for continuing.

⛔ **When `mapping_workflow`'s step-3 validation rejects the payload without an actionable
reason.** The block above handles a validator that is *unavailable*; this handles one that runs and
rejects unusably. Treat a rejection as **unactionable** when its text names no field and carries no
line or pointer the payload could be corrected against — a truncated error string is the observed
case.

1. **Bound the retry at two.** After two unactionable rejections for the same source, stop. A third
   attempt is guesswork with no convergence signal, and guessing costs the bootcamper more than the
   documented path saves.
2. **Capture the evidence first.** Before falling back, write the raw rejection text **verbatim**
   into that source's `config/mapping_state_[datasource].json` (a `validation_rejections` array).
   It is the only diagnostic the upstream fix has, and it is otherwise lost when the session ends.
3. **Ask, do not decide.** Present this pinned 👉 question (INV-051/INV-056, numbered, no "or"):

   👉 **The mapping validator rejected this source twice without saying why. How would you like to proceed? Reply with a number:**

   1. **Write the mapper against the Senzing Entity Specification** *(recommended)* — all three quality gates still run.
   2. **Try the mapping workflow once more** — it may succeed with a different payload.
   3. **Skip this source** — continue with the sources that mapped successfully.

   *(Internal: end the turn on this question and wait — INV-007.)*

4. **On option 1, the fallback is bounded, not a free hand.** State plainly what still holds:
   - Attribute names come from the Senzing Entity Specification in `docs/reference/` (see
     "Entity specification reference" below) — **never** from training data or memory. The
     "NEVER hand-code or guess Senzing attribute names" rule at the top of this phase is
     unchanged: reading the specification is not guessing (INV-080).
   - **All three quality gates still run**, with the same availability-aware handling as above.
   - The ⛔ cross-source shared-feature collision check still runs — it is cross-source, and the
     validator never performed it anyway.
   - The mapping is still only **structurally** validated; Data processing's match-key audit
     remains the semantic check (INV-117).
5. **Record how each mapper was produced.** Note the fallback and its reason in the source's
   mapping-state checkpoint and in its `docs/mapping/` write-up, so a reader of the deliverable can
   tell which sources went through `mapping_workflow` and which did not.

`mapping_workflow` remains the default and documented path. Never offer this fallback
preemptively — only after two unactionable rejections of the same source.

⛔ **These gates are structural, not semantic — say so; do not let green be mistaken for correct.**
Every check above validates **one source at a time** and asks whether the output is *well-formed*:
the analyzer checks structure against the Entity Specification, the verbatim check that values were
not altered, the routing report that fields reached a feature, the quality score completeness and
format. **None of them evaluates whether a field means what the feature means**, and none compares
how two sources populate the *same* feature. A mapping can pass all of them and still be wrong in
the way that matters most — telling Senzing two things conflict when they do not, which suppresses
legitimate merges.

Tell the bootcamper this plainly when reporting a passing result: the mapping is **structurally
valid**, and it is not **semantically validated** until data is loaded and the match keys are read.
Data processing's match-key audit is where that happens. A bootcamper who hears "all gates green"
and infers "the mapping is correct" has been misled by omission.

**Checkpoint:** write step 11.

### 12. Generate starter code

This step does **not** advance the workflow — generating the sample JSON and starter mapper is work
performed inside workflow step 4, which advances once at step 15 with its verdict (see the call
contract above). Tell the user: show a sample target JSON record so they see the output format.

> **Presentation (conditional on `mapping_verbosity`):**
>
> - **Verbose:** Show a sample target JSON record with annotations explaining the structure
>   (which fields became which Senzing attributes, how DATA_SOURCE and RECORD_ID are set, nested
>   vs. flat layout).
> - **Concise:** State the output file path and format only (e.g., "Output:
>   data/senzing-ready/customers.jsonl: one JSON record per line").

After `mapping_workflow` generates output files into the workspace, place them into the correct
project subdirectories per the file-placement guidance above (`.py` → `src/`, transformed JSONL
→ `data/senzing-ready/`, mapping docs → `docs/mapping/`, etc.). Do not regenerate a
`docs/README.md` index; nothing here maintains one.

**Checkpoint:** write step 12.

### 13. Build the transformation program

Use `generate_scaffold` or the mapping workflow output as the foundation. Handle: input
reading, field mapping, type conversion, cleansing, `DATA_SOURCE`/`RECORD_ID`, and error
handling. Save to `src/transform/transform_[name].[ext]`. Tell the user: the file path, what it
reads/writes, and what it handles.

⛔ **On Java, that `snake_case` filename and an idiomatic class name cannot both be `public`** —
declare the top-level class package-private and keep the prescribed path. Applies equally to the
`<name>_mapper.<ext>` the workflow's own step 4 asks for. The rule, its reason and the C# difference
are in `../bootcamp-onboarding/ground-rules.md` → "File placement" (INV-237); do not restate them
here.

**Keep JSON handling dependency-free.** This is usually the first Java the bootcamp generates, and
the bootcamp compiles with plain `javac` and never sets up Maven or Gradle — so the mapper must not
depend on an external JSON library (a scaffold importing `javax.json` will not compile as written).
Write the reader here so it needs only the standard library, and **reuse this same reader in later
modules** rather than re-deriving one per module: Data processing's loading program expects it. Full
rationale, and the rule that replacing the JSON library is safe while altering SDK calls is not, are
in `../module-02-sdk-setup/SKILL.md` → "The launch environment".

**Checkpoint:** write step 13.

### 14. Test

Run on 10-100 records from `data/samples/`. Validate with
`analyze_record(workspace_dir='data/mapping')` — ⛔ `workspace_dir` is a **required** parameter on
this tool as well, and it is where the analyzer script and its reports are written, so it takes the
same project-local mapping directory as the workflow. Tell the user: pass/fail, output file path,
sample record, any observations.

> **Presentation (conditional on `mapping_verbosity`):**
>
> - **Verbose:** Show pass/fail result, the output file path, a sample transformed record, and
>   any observations (warnings, skipped records, format issues).
> - **Concise:** Show pass/fail result and the output file path only (e.g., "✅ Pass: output:
>   data/senzing-ready/customers_sample.jsonl").

**Checkpoint:** write step 14.

### 15. Quality analysis

Run on 1000+ records. Evaluate feature distribution, coverage, quality scores. This is workflow
step 4's single advance: `action='advance'`, carrying `verdict` in `data` — `approve`,
`rework_mapping`, or `rework_code` — plus `output_path` and `records_output`. A `rework_*` verdict
is what routes step 17's iterate path. On `approve`, the response carries the workflow's Step 5
(`detect_environment`) menu; keep its `state` and handle that menu at **step 18a**, after this
source's mapper is written, reviewed and documented — not here. Tell the user: overall score, per-feature coverage with what
it means for matching, any issues found.

⚠️ **This advance is unconditional in both modes too, and for a different reason than step 11's.**
The `verdict` is not a preference the bootcamper holds — it is a QA judgement that follows from the
analyzer's own output (features at 0%, a short record count, a payload that should have been a
feature), so putting it to a vote would be asking them to ratify evidence they have just been shown.
Compute it, say which check decided it, and advance. The bootcamper's decision points here are the
pinned 👉 questions that follow — the visualization offer and the quality-gate branches — not the
verdict itself.

> **Presentation (conditional on `mapping_verbosity`):**
>
> - **Verbose:** Show the overall quality score, per-feature coverage breakdown with matching
>   implications (e.g., "NAME coverage 98%: strong for matching" / "ADDR coverage 42%: may
>   reduce match accuracy"), and all issues found with explanations.
> - **Concise:** Show the overall quality score, a count of mapped vs. unmapped fields, and
>   warnings only (e.g., "Quality: 85/100. 8 mapped, 3 unmapped. ⚠️ Low address coverage may
>   affect matching.").

**Offer visualization:** Pin the offer verbatim:

> 👉 **Would you like a web page showing the quality analysis (coverage charts and the field mapping summary)?**

If yes, generate a self-contained HTML page and save it to
`docs/visualizations/mapping_[name]_quality.html` (INV-070).

⛔ **Same four rules as the quality-assessment visual in `phase1-quality-assessment.md`** — this is a
bootcamper-facing visual deliverable too, and the reasons are identical: brand tokens from
`${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/brand_tokens.py` (INV-081; skill-relative fallback
`../bootcamp-onboarding/scripts/brand_tokens.py`, INV-252); **renders offline**, so no CDN or web font
— inline the vendored `${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/vendor/d3.v7.min.js` (skill-relative fallback
`../bootcamp-onboarding/scripts/vendor/d3.v7.min.js`, INV-252) if a chart library is needed (INV-081/INV-091);
every data-sourced string escaped for the context it lands in, including `<`/`>`/`&` as `\uXXXX`
inside any inline `<script>` payload (INV-106); and verify the rendered page rather than the exit
status (INV-129). The mapping summary carries **more** bootcamper-authored text than the phase 1
page — source field names, target attributes, sample values — so the escaping rule matters most here.
`ground-rules.md` → "Visual deliverables (Senzing brand)" and the visualization contract's
"Rendering contract" are the statements of record.

**Checkpoint:** write step 15.

### 16. Review

Confirm with the user: output format correct, quality acceptable, ready for production or needs
adjustment.

**Iterate vs. proceed decision gate:** After presenting quality results, guide the decision and
close the turn on one 👉 question:

- **Quality ≥80% and all critical fields mapped:**

  👉 **Quality looks strong. Ready to proceed to loading (Data processing)? Reply with a number:**

  1. Yes, proceed to loading.
  2. No, I'd like to iterate on something first.

- **Quality 70-79%:**

  👉 **Quality is acceptable. What would you like to do? Reply with a number:**

  1. Proceed to loading now.
  2. Iterate to improve [specific weak areas] first.

- **Quality <70%:**

  👉 **Quality needs improvement before loading will produce meaningful results. I'd recommend going back to address [specific issues]. What would you like to do? Reply with a number:**

  1. Iterate to improve the data.
  2. Proceed anyway, knowing results may be limited.

*(Internal: end the turn on the applicable question and wait.)*

**Checkpoint:** write step 16.

### 17. Iterate

If issues are found, go back to the relevant step. Retest after changes.

> **Data source registry:** Update the source's `mapping_status` to `complete` in
> `config/data_sources.yaml` and set `updated_at`. If a transformed file was created, update
> `file_path` to the `data/senzing-ready/` output.

**Checkpoint:** write step 17.

### 18. Save and document

- Program in `src/transform/`.
- Docs in `docs/mapping/mapping_[name].md` (field mappings, logic, quality, how to run).
- Sample output in `data/senzing-ready/[name]_sample.jsonl`.
- **Transformation lineage:** Create `docs/mapping/transformation_lineage_[name].md` for this
  data source, covering source file info, transformation program, output file info, field
  mappings, format changes, filters, quality improvements, and before/after record counts. (No
  lineage template is bundled; compose the document directly.)
- **Entity specification reference:** The Senzing entity specification reference lives only at
  `docs/reference/senzing_entity_specification.md`: a single canonical copy. Do NOT create a
  copy in the `docs/` root; if one exists there, remove it.
- **Per-source mapping specification:** Save a mapping specification markdown to
  `docs/mapping/{source_name}_mapper.md` for this data source. This file is always per-source,
  even when the transformation program is shared. Use this structure:

  ```markdown
  # Mapping Specification: {SOURCE_NAME}

  **Source file:** data/raw/{source_file}
  **Data source name:** {DATA_SOURCE}
  **Entity type:** Person / Organization / Both
  **Generated by:** mapping_workflow

  ## Field Mappings

  | Source Field | Senzing Attribute | Transformation | Notes |
  |---|---|---|---|
  | ... | ... | ... | ... |

  ## Mapping Decisions

  - [Key decisions made during mapping]

  ## Quality Notes

  - [Quality observations specific to this source]
  ```

**Checkpoint:** write step 18.

### 18a. Step 5 `detect_environment` menu handling (the optional-sandbox decision)

The `approve` verdict at step 15 advances workflow step 4, and the response to that advance carries
the workflow's **Step 5 (`detect_environment`)** with a four-option menu. Handle it **here**, once
this source's mapper is written, run, reviewed and documented (steps 12–18) — not at the moment the
response arrives.

⛔ **Why the placement matters.** This block previously sat under step 11 (Map), and
`phase3-test-load.md` pointed at step 11 as its entry. Both were wrong in the same direction:
choosing `test_load` there entered Phase 3 before the transformation program existed, so Phase 3's
step 22 had no "Phase 2 transformation output" to sample, and Phase 3's step 26 closes the module —
which would have skipped steps 12–18 entirely, including the transform code INV-042/INV-043 require
and step 19's mandatory per-source `docs/mapping/{source_name}_mapper.md` gate. Entering from 18a,
every prerequisite Phase 3 assumes is already on disk.

Do NOT stop at the menu: explain it and relay a recommendation so the bootcamper never hits a dead
end.

**`mapping_workflow` Steps 5–8 are optional sandbox validation** (Phase 3). They let you
trial-load the mapped source into a throwaway sandbox to preview entity resolution. They are
NOT the production load: the real load happens in **Data processing**. The four options are:

- **skip:** skip the per-source sandbox test load and move on. **Recommended when one or
  more unmapped sources remain.**
- **test_load:** run the optional sandbox test load (enters Phase 3) for this source.
- **load+resolve:** run the optional sandbox test load and resolve entities (enters Phase 3)
  for this source.
- **done:** finish the mapping workflow for this source without a sandbox test load.

**Multi-source continuation (recommended path):** When one or more unmapped sources remain,
recommend **skip**: the real load is deferred to Data processing, so a per-source sandbox test load
adds little here — and automatically continue to the next unmapped source (step 19) by starting its
own `mapping_workflow` run. Tell the bootcamper: "Steps 5–8 are an optional sandbox preview; since
you still have sources to map and the real load happens in Data processing, I'll skip the per-source
test load and move on to the next unmapped source."

**Explicit choice is preserved:** If the bootcamper explicitly chooses **test_load** or
**load+resolve**, follow that path into Phase 3 (`phase3-test-load.md`) unchanged. The real
production load still happens in Data processing regardless.

**Checkpoint:** write step 18a.

### 19. Repeat for remaining data sources

Each source gets its own transformation program and its own `mapping_workflow` run.

⛔ **Before starting the next source's `mapping_workflow(action='start')`, confirm this source's
`profile_report.md`, `schema_hints.md` and `JOURNAL.md` have already been relocated to
`docs/mapping/` under their source-qualified names** (`{source_name}_profile_report.md`,
`{source_name}_schema_hints.md`, `{source_name}_JOURNAL.md` — see "File placement during the
workflow"). This is INV-177: relocation under a source-qualified name happens **before** the next
source's run begins. Every source shares one `workspace_dir`, and the next run rewrites those three fixed
workspace filenames for its own profiling, so anything still sitting there under an unqualified
name is lost — silently, with no error.

> **Mandatory internal gate (do not render to the bootcamper):** BEFORE writing the module
> completion checkpoint, list ALL files in `data/senzing-ready/` and verify that EACH has a
> corresponding `docs/mapping/{source_name}_mapper.md`. If any are missing, create them NOW. Do
> NOT write the module completion checkpoint until all mapping specs exist. This is a hard
> requirement: the module is not complete without a per-source mapping specification for every
> transformed data source.

**Per-source completion checkpoint:** Before marking a source as complete, verify that
`docs/mapping/{source_name}_mapper.md` exists for that source. Do not proceed to the next source
or mark the current source done until its mapping specification markdown is saved. When all
sources are mapped, confirm every completed source has its own file. When a source's mapping is
complete, delete its `config/mapping_state_[datasource].json` checkpoint.

**Checkpoint:** write step 19.

### 20. Module completion and transition

Once all sources are mapped, **complete the module** — this is Module 5's completion site whenever
the optional Phase 3 was not taken. Run the standard **Module Completion** process in
`../bootcamp-onboarding/module-completion.md`: present the end-of-module summary (INV-032), append
the name-based Module 5 recap section to `docs/bootcamp_recap.md` (INV-085), show the
`✅ Module complete: Data Quality, Mapping, and Transformation` line (INV-079), and end the turn on the pinned
transition 👉 question naming the **next selected module** from `selected_modules` (INV-076 / INV-079):

👉 **Are you ready to move on to the next module: {next module name}?**

*(Internal: end the turn on this question and wait.)*

Do **not** choose the next module by re-checking SDK state — `selected_modules` already fixes the
order (SDK setup precedes Data Quality, Mapping, and Transformation; Data processing follows it). **Run Module
Completion exactly once:** if the bootcamper took Phase 3 and its step 26 already completed the
module (`data_quality_mapping` is already in `modules_completed`), skip completion here and present
only the transition.

**Checkpoint:** write step 20.
