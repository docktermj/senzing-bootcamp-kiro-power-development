# Module 6, Phase D: Validation (steps 21–28)

Continues from Phase B (single source) or Phase C (multi-source). Follow the ground rules;
`🛑`/`⛔` are internal control directives. Entity queries use SDK code generated via
`generate_scaffold` / `get_sdk_reference`, never direct SQL against `database/G2C.db`. Counts
and stats come from `reporting_guide` — **name the topic**: `topic='evaluation'` for the
single-pass export statistics this phase needs, `topic='export'` for extraction patterns.

⚠️ **`topic='reports'` is not this bootcamp's route.** Its SQL targets an analytical data mart
(`sz_dm_entity`, `sz_dm_record`, `sz_dm_relation`, `sz_dm_report`) that the bootcamp never builds —
the tool says so itself, in that response's own schema notes: *"These tables are NOT part of the
Senzing SDK and do NOT exist out of the box. They must be created and maintained by a separate data
mart replication pipeline that YOU build and operate"* (verified on MCP server 1.32.2, 2026-07-30).
It is the production-reporting answer, not the evaluation one, so asking for it here returns
well-formed SQL that cannot run against a single-database SQLite workspace. If you are already
looking at that response, the usable subset is its `Validation:` patterns, which run against
**exported entity JSON** rather than the data mart.

## Single-source validation (always)

## 21. Validate match accuracy

Review the entity resolution results:

- Query a sample of known records (SDK method `get_entity_by_record_id`) to check how they
  resolved
- Look for expected matches, are records that should match resolving to the same entity?
- Look for false positives, are unrelated records being incorrectly merged?
- Look for false negatives, are records that should match resolving to separate entities?
- If match accuracy is poor, revisit data quality (Module 5) or mapping before proceeding

Use `generate_scaffold(language='<chosen_language>', workflow='query', version='current')` to
generate SDK code that retrieves sample entities for review. Use
`get_sdk_reference(topic='functions', filter='why_entities', version='current')` to explain why
records matched. (There is no direct entity-query MCP tool, entity lookup and why-matched are
done through generated SDK code.)

**Checkpoint:** write step 21.

## 22. Run basic UAT for single-source

Validate that the loaded data meets business expectations:

- Verify record counts, does the number of loaded records match expectations? (Use
  `reporting_guide(topic='evaluation', language='<chosen_language>')` for counts — not `topic='reports'`; see the header note.)
- Spot-check entity resolution, pick 5–10 known entities and confirm they resolved correctly
- Document any issues found in `docs/uat_results.md`
- If critical issues are found, fix and reload before proceeding

**Checkpoint:** write step 22.

## Cross-source validation (conditional, 2+ sources loaded)

Only present steps 23–27 when the bootcamper has loaded 2 or more data sources. For
single-source bootcampers, skip directly to step 28 (Document results).

## 23. Validate cross-source results

Validate: record counts match expectations, cross-source entities exist, no unexpected data
loss, error logs clean. Use `reporting_guide(topic='graph', language='<chosen_language>', version='current')` for
network-graph patterns.

⛔ **Before treating a low or zero cross-source entity count as a finding about the data, read how
the data was selected.** If Module 4 reduced any source, `config/data_sources.yaml` records the
sampling method and the reason for it. A **random** slice of 2+ sources removes cross-source overlap
by construction — one bootcamp got zero cross-source matches from a load reporting 1,147 records,
no errors, redo drained and 94–100% quality — so a near-zero count there is an artifact of the
sample, not a property of the sources, and the remedy is an overlap-preserving re-sample (Module 4
→ "Sampling rule"), not a mapping change. Say which it is; never report "Senzing found no
cross-source matches" without checking this first.

Sample 15–25 entities that contain records from multiple data sources and verify they represent
the same real-world person or organization. Check cross-source matches and spot-check
single-source entities to confirm no cross-source matches were missed.

This is validation work only — do **not** produce a visualization here. All results and
cross-source relationship visualization is offered once, in Module 7 (Query, Visualize and
Discover), where it is delivered as tabs of the single interactive app (Entity Graph — including
its relationship-subgraph mode — and Cross-Source) rather than a separate static page (INV-104). Module 6 no longer offers a
cross-source visualization, to avoid a duplicate/misplaced offer.

**Checkpoint:** write step 23.

## 24. Validate cross-source results quality

Use `reporting_guide(topic='evaluation', language='<chosen_language>', version='current')` for the 4-point ER evaluation
framework and `reporting_guide(topic='quality', language='<chosen_language>', version='current')` for precision/recall
metrics.

Validate: match accuracy (query known records via the generated SDK code / SDK method
`get_entity_by_record_id`), false positives (incorrect merges), false negatives (missed
matches), data completeness. If accuracy is poor, revisit Module 5 mapping.

**Checkpoint:** write step 24.

⛔ **Steps 21–24 ask nothing, so this turn does not end here** — validation results and evidence
tables are the output most likely to be mistaken for a turn ending, because they conclude something
(`ground-rules.md` → "A results presentation is not a turn ending", INV-225). Continue in the same turn to
the next step that actually asks.

## 25. Execute UAT with business users

**First, check whether there are real stakeholders.** Read `docs/business_problem.md`. If it carries
the bootcamp-generated marker `> 🤖 Bootcamp-generated business case` (the Business Case Offer was
accepted in Module 1), or otherwise records no real stakeholders, there are no business users to
involve — so **do not ask** the involvement question (INV-006/INV-012). State briefly that the
scenario is bootcamp-generated, so you will self-direct the UAT: spot-check 5–10 cross-source
entities and document findings in `docs/uat_results.md`, then proceed to step 26.

Otherwise (a real business problem with stakeholders), offer to involve business users — pin the
question verbatim:

👉 **Would you like to involve business users in testing the cross-source results?** (respond yes or no)

*(Internal: end the turn on this question and wait.)*

- **Yes:** share cross-source match examples, collect feedback, document in
  `docs/uat_results.md`.
- **No:** spot-check 5–10 cross-source entities and document findings in `docs/uat_results.md`.

**Checkpoint:** write step 25.

## 26. Get stakeholder sign-off

Create `docs/results_validation.md` with match-quality metrics (true/false positive/negative
rates) and business validation results (test cases passed, issues, resolution plan).

**Checkpoint:** write step 26.

## 27. Document validation results

Save all findings to `docs/results_validation.md`: total records loaded, entities created,
cross-source match rate, UAT results, stakeholder feedback/sign-off status. This becomes the
validation baseline before Module 7.

Update `docs/loading_strategy.md` with: final load order and rationale, per-source statistics,
cross-source match summary, issues and resolutions, recommendations for future loads.

⛔ **The per-source statistics written here are reconciled figures or they are labelled as
unreconciled — never bare numbers.** (INV-243/INV-245) This document outlives the session and is
read as the record of what was loaded, so an unchecked count written into it is the hardest of all
these sites to correct later: nothing downstream re-derives it, and by the time anyone doubts it
the load is long finished.

**Checkpoint:** write step 27.

## Document results and complete (always)

## 28. Document results

Record the validation findings:

- Save validation results to `docs/results_validation.md`
- Include: total records loaded, entities created, match rate, any issues found and their
  resolution
- This becomes the baseline for comparison

The **results dashboard** (entity counts, match statistics, and sample resolved entities) is offered
in the **Query, Visualize and Discover** module (Module 7, Step 3c — the consolidated visualization
gate), where all results visualization lives — Module 6 does not offer it, to avoid a duplicate
offer. Module 6 offers **no** visualization at all: the cross-source relationship view (step 23) is
also delivered in Module 7's single interactive app (its Entity Graph / Cross-Source / Relationship
Network tabs, INV-104), not as a separate Module 6 page.

**Checkpoint:** write step 28.

## Recovery from failed load

If loading fails partway through:

1. **Check what loaded**, query known RECORD_IDs (via generated SDK code) to see if they exist.
2. **Decide, wipe and restart vs. resume:**
   - **Wipe and restart:** restore from the `database/G2C.db` backup, fix the issue, re-run.
   - **Resume:** modify the loading program to skip already-loaded records.
3. **If the database is corrupted**, restore from backup. If no backup, delete
   `database/G2C.db` and re-run the Module 2 config.
4. **Common causes:** disk full, out of memory, invalid records, network timeout.

(The Kiro backup/restore helper `../bootcamp-onboarding/scripts/restore_project.py` is a later porting phase; restore
from your own `database/G2C.db` backup for now.)

### Multi-source recovery (Phase C)

If a source fails during orchestration, present three options:

1. **Skip and continue:** mark it failed, continue with remaining sources.
2. **Retry after fix:** pause, fix the issue, retry the failed source.
3. **Restore and restart:** restore from backup, fix, restart orchestration.

## Match-key audit (run before the iterate-vs-proceed gate)

Every mapping gate the bootcamp runs before this point is **static, single-source, and
structural** — the analyzer, the verbatim check, the routing report, the quality score. None of
them evaluates *meaning*. So a whole defect class survives them: two source fields that measure
different things mapped to the same Senzing feature.

(Those gates also have blind spots of their own, so a finding from one is not automatically a defect
in the mapping. The verbatim check in particular **harvests source *values* only**, so it reports any
emitted value it cannot harvest — a **boolean** source value, or a value derived from a source **field
name** rather than a field value — however that value was emitted (server 1.32.2, verified
2026-07-29). If a violation list came into this module unresolved for one of those reasons, it is a
checker limitation and not a mapping error; see
`../module-05-data-quality-mapping/phase2-data-mapping.md` → the verbatim-check block, which also
covers what to record. Numeric source values used to fail this way and **no longer do** — that was
fixed upstream in 1.32.2 — so do not carry forward a numeric exemption from an older run without
re-running the check.) Senzing is then told a conflict exists where
none does, and it **suppresses legitimate merges**. All gates green, matches quietly lost.

This is the reading that catches it. It also matches the Senzing reporting guidance directly —
`reporting_guide(topic='quality', language='<chosen_language>')`'s anti-patterns say *"Only checking aggregate statistics for
quality … Aggregate stats hide errors. Always sample and manually review specific entities"* —
which is exactly the gap the UAT percentages below leave open.

1. **Read the match keys** from the loaded results using generated SDK code (never direct SQL
   against `database/G2C.db`). Per `get_sdk_reference(topic='response_schemas')` there are
   **two reads, and they need two different methods** — confirm both via MCP rather than from
   this file (a sourcing floor):

   | What | Where | How to obtain it |
   |---|---|---|
   | Per-record match keys | `RESOLVED_ENTITY.RECORDS[].MATCH_KEY` | a bulk export (`export_json_entity_report`) is fine |
   | Relationship match keys | `RELATED_ENTITIES[].MATCH_KEY` | the same export **when its rows carry `RELATED_ENTITIES`** — dump one row to check; otherwise **per-entity** `get_entity_by_entity_id` / `get_entity_by_record_id`, or `find_network_by_entity_id` |

   ⚠️ **Whether an export carries `RELATED_ENTITIES` depends on the flag set, not on the method — so
   dump one row and route on what you see.** Do not assume either answer:

   - `reporting_guide(topic='evaluation', language='<chosen_language>')` documents the export-with-defaults case directly
     (verified 2026-07-28): *"Use `export_json_entity_report` with `SZ_EXPORT_DEFAULT_FLAGS` … Each
     exported row is a JSON object containing `RESOLVED_ENTITY` … **and `RELATED_ENTITIES[]`** (with
     `ENTITY_ID`, `MATCH_LEVEL_CODE`, `MATCH_KEY`, `ERRULE_CODE`, `RECORD_SUMMARY[]`)"*, and its
     worked `export_with_stats` pattern computes relationship categories in a **single pass over the
     export**. A live run on SDK 4.3.3 with `SZ_EXPORT_DEFAULT_FLAGS` confirmed it: the first row's
     top-level keys were `[RESOLVED_ENTITY, RELATED_ENTITIES]`.
   - A different bootcamp session, on the same SDK version, assembled its flags from
     `SZ_ENTITY_INCLUDE_*` members and got rows with **no `RELATED_ENTITIES` key at all** and no
     error. Both observations are real; the flag set is the variable. Note that the
     relationship-detail flags (`SZ_ENTITY_INCLUDE_ALL_RELATIONS` and its members) do **not** list
     the export methods in their `applies_to`, which is why composing a flag set out of those alone
     is the case that comes back without relationships — but that does not make the export incapable,
     because `SZ_EXPORT_DEFAULT_FLAGS` is itself an export-family flag documented as matching *"the
     normal entity defaults"*, and those defaults include the relationship-inclusion members.

   **So: start from `SZ_EXPORT_DEFAULT_FLAGS`, dump one row, and read its top-level keys before you
   choose a reader.** `RELATED_ENTITIES` present → do both reads in one export pass.
   `RELATED_ENTITIES` absent → keep the per-record read on the export and use a per-entity reader
   (or `find_network_by_entity_id`) for the relationship half. Never write the audit as if the answer
   were settled in either direction (INV-115/INV-149: the dumped row is the authority).

   ⚠️ **If you do read relationships from the export, deduplicate.** Per
   `reporting_guide(topic='evaluation', language='<chosen_language>')`: *"Each relationship appears in BOTH entities'
   `RELATED_ENTITIES` — deduplicate by sorting `(min_id, max_id)` pairs and using a set."* Skipping
   this double-counts every relationship, which inflates a suppressor share rather than emptying it —
   a wrong number that still looks plausible. The same guidance notes export iteration is
   O(all entities): fine at bootcamp scale, and the reason the single-pass form is worth having
   instead of one call per entity.

   The two export flag families also do different jobs. `SZ_EXPORT_INCLUDE_*` selects **which
   entities** appear as rows (`..._POSSIBLY_SAME`, `..._DISCLOSED`, `..._ALL_HAVING_RELATIONSHIPS`
   — all row filters). It does **not** select what detail a row carries: an export flagged with
   only those succeeds and yields rows containing nothing but `ENTITY_ID`. The Senzing reporting
   guidance names this as an anti-pattern — *"Exporting without proper flags … Use
   `SZ_EXPORT_DEFAULT_FLAGS` or specify exactly which flags you need. Missing flags means missing
   data in your reports."* — so start from `SZ_EXPORT_DEFAULT_FLAGS` and add row filters, rather
   than OR-ing row filters alone.

   ⚠️ **Confirm a composite exists on *your* binding before using it.** `SZ_EXPORT_ALL_FLAGS` is
   documented for the export methods, but it comes from the Java SDK's flag enum and is **absent
   from the Python binding's `SzEngineFlags`** in 4.3.3 (`AttributeError`). Flag *names* are not
   uniformly available across bindings — introspect (`dir(SzEngineFlags)`) or confirm via MCP for
   the bootcamper's language instead of copying a name from cross-language documentation.

   A worked expression for a detail-carrying export in Python — start here rather than assembling
   row filters and hoping:

   ```python
   from senzing import SzEngineFlags

   # SZ_EXPORT_DEFAULT_FLAGS carries the per-entity detail; add row filters only to widen
   # WHICH entities appear. Re-confirm both names via MCP rather than from this file (INV-080; a sourcing floor) — this is a
   # worked example, not a substitute for the lookup.
   flags = (
       SzEngineFlags.SZ_EXPORT_DEFAULT_FLAGS
       | SzEngineFlags.SZ_EXPORT_INCLUDE_ALL_ENTITIES
   )
   handle = sz_engine.export_json_entity_report(flags)
   try:
       row = sz_engine.fetch_next(handle)   # dump this ONE row and read it before parsing
       print(row)
   finally:
       sz_engine.close_export_report(handle)   # close_export_report, not close_export
   ```

   Before parsing the whole reader output, **dump one raw row** and confirm the fields the parser
   expects are actually present (INV-115). This is the check that turns "4,587 rows exported
   successfully, all containing only `ENTITY_ID`" from a wasted validation pass into one line of
   output — and it is the same check that decides which reader the relationship half needs, above.
   Print the row's **top-level keys**, not just the row, so the `RELATED_ENTITIES` question is
   answered explicitly rather than by eyeballing a wall of JSON:

   ```python
   first = json.loads(row)
   print("top-level keys:", sorted(first))
   print("carries RELATED_ENTITIES:", "RELATED_ENTITIES" in first)
   ```

2. **Tabulate the suppressors.** In a match key, `+` means the feature **contributed** to the match
   and `-` means it **detracted** (MCP-confirmed via `response_schemas` on
   `RESOLVED_ENTITY.RECORDS[].MATCH_KEY`). Count the features appearing with a leading `-`, ranked
   by frequency, and **separate single-source from cross-source** comparisons — the cross-source
   ones are where a mapping disagreement between two sources shows up.
3. ⛔ **An empty cross-source suppressor list is a plumbing failure until proven otherwise.**
   "No suppressors found" and "this reader cannot answer the question" render identically — a
   clean result — so never report the first without ruling out the second. Before making any
   "no cross-source suppressors" statement, prove the reader can see relationships at all:

   - Take one entity known to have a relationship (any entity with a `POSSIBLY_SAME` /
     `POSSIBLY_RELATED` link, or use the relationship count you already have from the load
     summary). If the loaded data genuinely has **zero** relationships, say that instead — the
     question does not arise.
   - Confirm the reader returns a **non-empty** `RELATED_ENTITIES` for it. When the reader is the
     export, the row dump in step 1 has already answered this for the whole pass — one check, not one
     per entity — so this costs nothing; it is still required, because a reader that sees the key but
     parses it under the wrong name fails exactly as silently.

   If that check fails, report **"the audit could not read relationship match keys"** and name the
   reason. Never render it as "no suppressors were found" (INV-115: a blank parsed field is a
   probable wrong reader before it is real absent data).

4. **Report a high-share cross-source suppressor as a FINDING, never a pass/fail.** If one feature
   is detracting on a large share of cross-source comparisons, say so plainly and ask the
   bootcamper to check whether the two sources' fields for that feature genuinely measure the same
   thing. ⛔ This must not become an automatic gate: a suppressor is often entirely legitimate (two
   records really do disagree), and a hard failure here would produce false alarms and train
   bootcampers to dismiss the signal — which would cost more than the check gains.
5. **Carry the outcome into the decision gate below**, alongside the UAT numbers. The audit has
   **three** outcomes, not two — finding, no finding, and could-not-measure — and the gate must be
   told which one it got.
6. **If a finding here causes a mapping to change or be withdrawn, file it as bootcamp feedback
   before moving on** — silently, per `../bootcamp-onboarding/ground-rules.md` → "Reversed decisions:
   file them when they happen". This is the first and most important of that rule's three triggers,
   and this is the step that fires it: the audit read the engine's own output and overturned a
   decision every static gate had passed. Filing it here rather than at graduation is the whole
   point — by then the reasoning may have been compacted away, leaving only the corrected mapping
   and no record of what was wrong with the original or how it was caught. No banner, no question,
   never blocking (INV-012/INV-048).

> **Worked example.** In one bootcamp, `EFX_YREST` ("year established") and `FilingDate`
> (incorporation filing date) were both mapped to `REGISTRATION_DATE`. A business usually operates
> before it incorporates, so the two disagreed on up to 676 records and `-REGISTRATION_DATE`
> appeared on nearly every cross-source match key. All five static gates passed; the quality score
> was 86.3%. Routing one field to payload instead — no other change — took cross-source merges from
> 1 to 4 and links from 160 to 170. The signal was there the whole time; nothing was reading it.

## Iterate vs. proceed decision gate

Route on the UAT / match-accuracy results, **and present the match-key audit outcome alongside
them** — the percentages alone cannot see a suppressor problem, so a bootcamper choosing between
iterating and proceeding needs both. A high-share cross-source suppressor is the strongest reason
to choose "iterate now" even when the numbers look acceptable.

State which of the audit's three outcomes applies; do **not** collapse the third into the second:

- **A finding** — name the suppressing feature and its share.
- **No finding** — the audit ran and found nothing of concern.
- **Could not measure** — the relationship half of the audit did not execute (step 3). Say so
  plainly rather than letting silence imply a clean result: a gate decided on an unmeasured number
  is worse than a gate told the measurement failed. This still does not block (INV-117) — it is a
  third finding that routes, not a new blocker.

- **UAT ≥90% and match accuracy ≥90%:** state "Results look strong." and proceed to the module
  transition question. **If the audit produced a finding, say so in the same breath** — strong
  numbers plus a suppressing feature is exactly the case this audit exists to surface, and the
  bootcamper should hear it before moving on.
- **UAT <80%:** state "Results need improvement — I recommend going back to Data Quality, Mapping, and Transformation
  to refine the mapping." and proceed to the transition question.
- **UAT 80–89%:** results are mixed, so ask the bootcamper to decide with a single pinned question
  (neutral lead + numbered list, INV-051):

  👉 **Most tests pass but there are gaps. What would you like to do? Reply with a number:**

  1. Iterate now to improve the results before moving on.
  2. Move forward to the next module.

  *(Internal: end the turn on this question and wait.)*

## Stakeholder summary

After validation, always produce a one-page executive summary — no question (INV-012) —
following the Module 6 guidance, and save it to `docs/stakeholder_summary_module6.md`. Announce
it as a produced file in the end-of-module summary's "Files produced" list (INV-032). (The Kiro
`templates/stakeholder_summary.md` port is a later phase; compose the summary directly for now.)

## Success criteria

- ✅ Loading program generated with production-quality error handling, progress tracking, and
  statistics
- ✅ At least one data source fully loaded with error rate < 1%
- ✅ Redo queue drained after loading
- ✅ Loading statistics documented in `docs/loading_strategy.md`
- ✅ Match accuracy reviewed (sample entities checked for false positives/negatives)
- ✅ Results validation documented in `docs/results_validation.md`
- ✅ Loading program saved in `src/load/`

**Additional criteria when 2+ sources loaded:**

- ✅ All sources loaded (or failures documented) with error rate < 1% per source
- ✅ Dependencies respected, cross-source matches reviewed
- ✅ Orchestrator program saved in `src/load/orchestrator.[ext]`
- ✅ Cross-source match accuracy validated
- ✅ UAT executed, results in `docs/uat_results.md`
- ✅ Stakeholder sign-off obtained

## Advanced reading

- After completing Module 6, ask about record updates, deletions, entity re-evaluation, and redo
  processing, use `search_docs` and `get_sdk_reference` for current guidance for production
  systems where source data changes over time.
- For production systems that receive ongoing data, ask about incremental loading patterns, use
  `search_docs` and `generate_scaffold` for current guidance on adding new records to an existing
  database, processing redo records after incremental loads, and monitoring pipeline health.

(The Kiro multi-source reference `data-processing-reference.md` and the user reference
`docs/modules/MODULE_6_DATA_PROCESSING.md` are later porting phases.)

## Module completion and transition to Module 7

Follow the Decision Gate above to frame readiness. When results are ready, run the standard
**Module Completion** process in `../bootcamp-onboarding/module-completion.md` (update progress,
append the Module 6 recap section to `docs/bootcamp_recap.md`, and present the end-of-module
summary), then close the module:

👉 **Are you ready to move on to the next module: {next module name}?**

*(Internal: end the turn on this question and wait.)* On completion, set `current_step` to
`null` in `config/bootcamp_progress.json` and, on an affirmative reply, produce the Module 7
start banner, journey map, before/after framing, and step overview per the ground rules.

**Success indicator:** ✅ All data sources loaded + redo records processed + no critical errors +
entity resolution results validated + results documented in `docs/results_validation.md`.
