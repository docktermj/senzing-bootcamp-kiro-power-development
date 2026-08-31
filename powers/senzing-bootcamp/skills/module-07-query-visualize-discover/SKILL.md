---
name: module-07-query-visualize-discover
description: 'Bootcamp Module 7: Query, Visualize and Discover. Use when the bootcamper starts or resumes Module 7, or needs to query resolved entities, visualize them, and explore results against the business problem.'
license: Apache-2.0
compatibility: Requires the Senzing MCP server and Docker.
metadata:
  author: Senzing
  version: 0.5.1
  templateRelease: 0.5.1
  templateSkill: module-07-query-visualize-discover
---

# Module 7: Query, Visualize and Discover

> **MCP grounding (mandatory — applies to this entire skill).** Every Senzing fact you present —
> SDK method and attribute names, config options, error codes, and entity-resolution specifics —
> MUST come from the Senzing MCP tools, never from training data, memory, or speculation.
> **Pre-response checklist:** if a reply contains any Senzing specific, you MUST have called an MCP
> tool this turn to obtain it; if not, stop and call it first. This has the same precedence as a ⛔
> gate. The full rule and tool routing are the "MCP-first invariant" in
> `../bootcamp-onboarding/ground-rules.md`.

Follow `../bootcamp-onboarding/ground-rules.md` throughout (👉 one-question-at-a-time,
MCP-first, no direct SQL, file placement, checkpointing). Execute every numbered step and
sub-step one at a time, in order. Never skip, combine, or abbreviate a step containing a 👉
question. This has the same absolute precedence as a ⛔ mandatory gate.

**First:** Read `config/bootcamp_progress.json`, then (per ground-rules) show the module start
banner, journey map, before/after framing, a brief numbered overview of this module's steps, an estimated time-to-complete (INV-096), and the recommended model/effort nudge (INV-063), before any module work.

**Before/After:** Your data is loaded and entities are resolved, but you haven't examined the
results yet. After this module you'll have query programs that answer your business questions,
visualizations of your resolved entities, and (optionally) a tour of Senzing's advanced
discover capabilities (why, how, relationship networks).

**Prerequisites:**

- ✅ Module 6 complete (all sources loaded, single or multi-source).
- ✅ No critical loading errors.

**Success indicator:** ✅ Query programs created and tested + queries answer the business
problem + the single interactive visualization app offered (the entity graph and every results
view are tabs within it) + Discover phase completed or explicitly skipped.

## No direct SQL (module-critical)

This module is all about examining resolved entities. NEVER generate direct SQL against the
Senzing database (`database/G2C.db`) or its internal tables (`RES_ENT`, `OBS_ENT`,
`DSRC_RECORD`, `LIB_FEAT`, `RES_REL`, etc.). Every entity operation goes through the SDK:

- **Search, get entity, why-matched, how-built, network, path** → generate SDK code via
  `get_sdk_reference` (flags, method signatures, **and response structures** — topics `flags`
  and `response_schemas`, narrowed with `filter='<method>'`) plus `sdk_guide` /
  `reporting_guide` (topic `entity_views` for get/why/how patterns, topic `graph` for
  network/path patterns). Look up the response shape **before** writing code that parses it
  (INV-115); a wrong field name renders blank rather than raising.
- **Counts, stats, quality, reporting and visualization data** → `reporting_guide` (topics
  `reports`, `quality`, `evaluation`, `dashboard`, `graph`).

⛔ **Do not treat these as MCP tools.** `search_by_attributes`, `get_entity`,
`why_entities`, `how_entity`, `why_records`, `find_network`, `find_path`, and
`get_entity_by_record_id` read like callable tools and are not. The current Senzing MCP server does
NOT expose direct entity-query tools. These are SDK **methods**: the agent generates SDK code
that calls them, sourcing flags and signatures from `get_sdk_reference` and code patterns from
`sdk_guide` / `reporting_guide`. Never fabricate SDK method names; always confirm via MCP.

## Error handling

When the bootcamper hits an error during this module:

1. **SENZ error code** (message contains `SENZ` + digits, e.g. `SENZ2027`): call
   `explain_error_code(error_code="<code>", version="current")` and present the explanation and
   recommended fix. If it returns nothing, continue to step 2.
2. Look up the symptom via `search_docs`, then present the matching fix. There is no bundled
   `common-pitfalls` reference or Troubleshooting-by-Symptom table.

## Phases

- **Phase 1: Query and Visualize** (steps 1–3c): `phase1-query-visualize.md`
- **Phase 2a: Discover, Part A** (steps 4a–4c): `phase2-discover.md`
- **Phase 2b: Discover, Part B** (step 4d): `phase2b-discover.md`

Read `current_step` from `config/bootcamp_progress.json` (an integer, or a sub-step string like
`"3b"` or `"4a"`) and resume at the right phase and sub-step. Do not re-run completed steps.
For the Discover phase, also check `module_7_query.steps.<key>` for which 4x sub-steps are
already checkpointed.

## Module position

Module 7 is the last content module before graduation, and it is **required in every path**
(INV-076). The Query Completeness Gate at the end of Phase 1 is this module's transition: once it is
satisfied, run module completion and offer graduation. Preserve that gate exactly.

⛔ **Bootcamp graduation always follows — there is no path that ends here.** It is a Required module
in both Core and Customized (`../bootcamp-preparation/SKILL.md` → module list), so never tell the
bootcamper this is where the bootcamp may stop. A bootcamper who wants to keep exploring before
graduating is welcome to; the offer is simply re-presented when they are ready (INV-014 permits only
*requested* skips, and graduation cannot be deselected). The retired A/B/C "track" model that once
allowed a short path ended here was superseded by the Core-vs-Customized path choice (INV-076
supersedes INV-025).
