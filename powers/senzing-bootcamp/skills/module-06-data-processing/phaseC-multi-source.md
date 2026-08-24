# Module 6, Phase C: Multi-Source Orchestration (conditional, 2+ sources, steps 12–20)

Continues from Phase B. Follow the ground rules; `🛑`/`⛔` are internal control directives.
Orchestrator and redo code comes from the MCP tools, never hand-written.

**Conditional gate.** Read `config/data_sources.yaml` and count sources with `mapping_status:
complete`. If there is only ONE data source, skip Phase C entirely and proceed to Phase D
(`phaseD-validation.md`). Only present these steps when the bootcamper has 2 or more sources to
load.

## 12. Inventory all data sources

Read `config/data_sources.yaml` for `quality_score`, `mapping_status`, and `load_status` per
source. Enumerate every data source. For each: source name / DATA_SOURCE identifier, record
count, quality score, mapping status, loaded status. Present a summary table so the bootcamper
can review and confirm the list is complete.

⛔ **The `record_count` shown here is a figure presented to the bootcamper, so it carries the
reconciliation requirement with it.** (INV-243) Phase B reconciles each count against that
source's own input before writing it; a source whose count was never reconciled — one loaded
outside this bootcamp, or carried in from an earlier session — MUST be shown as unverified rather
than as a plain number (INV-245). A table is where an unchecked figure acquires the look of a
result, which is exactly the shape this rule exists for: the numbers are plausible, they sum, and
nothing about them invites a second look.

**Checkpoint:** write step 12.

## 13. Analyze dependencies

Explain the common dependency patterns: parent-child (load parents first), reference data first,
temporal ordering, or none. If a circular dependency is detected, explain that Senzing resolves
entities as records arrive, load the higher-quality source first.

**First, check the data's provenance.** Read the `provenance` field for each source being loaded
(step 12's inventory) in `config/data_sources.yaml` — the same field Module 5's fast-path uses. If
**every** such source is agent-generated (`provenance: cord` or `synthesized`), or
`docs/business_problem.md` carries the bootcamp-generated marker `> 🤖 Bootcamp-generated business
case`, the agent selected these sources itself and already knows there are no real load-order
dependencies between them. State that briefly (INV-012) and confirm rather than asking an open
question — pin the question verbatim (INV-056) and end the turn on it:

👉 **The generated sources have no load-order dependencies — shall I proceed with none?** (respond yes or no)

*(Internal: end the turn on this question and wait.)* On **yes**, record that there are none; on
**no**, ask the bootcamper to describe the dependencies they see and capture the dependency map.

Otherwise (some source being loaded is bootcamper-supplied — `provenance: own`/`free_data`/`unknown` —
and no generated marker is present), ask a single pinned 👉 question (INV-056) exactly as today and end the turn
on it:

👉 **Are there load-order dependencies between your data sources?**

*(Internal: end the turn on this question and wait.)* On **yes**, capture the dependency map; on
**no**, record that there are none.

Save the resulting dependency map (or the "no dependencies" record) to `docs/loading_strategy.md`.

**Checkpoint:** write step 13.

## 14. Determine load order

Use `quality_score` from `config/data_sources.yaml` to rank sources; update `load_status` as
loading progresses. Apply ordering heuristics (priority order): (1) reference before
transactional, (2) quality-first for a strong entity baseline, (3) attribute-density-first,
(4) volume-first when quality is similar. Present the recommended load order with reasons for
the bootcamper to review.

**Checkpoint:** write step 14.

## 15. Select loading strategy

**First, check the data's provenance** (as in step 13). If **every** source being loaded is
agent-generated (`provenance: cord`/`synthesized` in `config/data_sources.yaml`, or the
`> 🤖 Bootcamp-generated business case` marker is present in `docs/business_problem.md`), the agent
selected these sources and can recommend a strategy from what it knows: for the generated (typically
small) dataset, **Sequential** — safer, easy to debug, with no real gain from parallelism at this
scale. State that briefly (INV-012) and confirm rather than posing the open menu — pin the question
verbatim (INV-056) and end the turn on it:

👉 **I recommend the Sequential loading strategy for this generated dataset — shall I use it?** (respond yes or no)

*(Internal: end the turn on this question and wait.)* On **yes**, record Sequential; on **no**,
present the numbered menu below so the bootcamper chooses (INV-007).

Otherwise (some source being loaded is bootcamper-supplied — `provenance: own`/`free_data`/`unknown` —
and no generated marker is present), present the strategy choices as a neutral lead + numbered list (INV-051),
pinned verbatim (INV-056), and end the turn on the 👉 question:

👉 **Which loading strategy would you like? Reply with a number:**

1. **Sequential** — safer, easier to debug.
2. **Parallel** — faster, uses more resources.
3. **Hybrid** — sequential for dependent sources, parallel for independent.

*(Internal: end the turn on this question and wait.)*

**Checkpoint:** write step 15.

## 16. Pre-load validation checklist

Verify before orchestration: each source's load file exists at its registry `file_path`
(`data/senzing-ready/` for mapped sources; `data/raw/` for `fast_pathed: true` CORD /
already-Senzing-ready sources, which skipped mapping in Module 5) and is non-empty;
each source's DATA_SOURCE code is registered in the engine config (register any not yet
registered, idempotently — per Phase A step 4a; do not rely on Module 2's default config, which
predates data collection); RECORD_IDs unique within each source; a
database backup of `database/G2C.db` exists; sufficient disk space (~2x per source); the
Module 6 loading program works as a template. Fix failures before proceeding.

**Checkpoint:** write step 16.

## 17. Create orchestrator program

Use `generate_scaffold(language='<chosen_language>', workflow='add_records', version='current')`
and `find_examples(query="multi-source")` for patterns. Override any `/tmp/` or
`ExampleEnvironment` paths to `database/G2C.db`. Save to `src/load/orchestrator.[ext]`.

Must handle: ordered loading with dependency enforcement, parallel execution if selected,
per-source progress/error tracking with error isolation, statistics aggregation, and a
completion summary.

⛔ **The loading scaffold's counters are process-global, so per-source tracking is not free — you
have to build it.** The loader `sdk_guide(topic='load')` returns is written as a standalone
`main()`, and its counters are process-wide state: in Java, `LoadViaFutures.java` declares
`private static int errorCount / successCount / retryCount` (and a `static` retry file besides);
the equivalent in other bindings is module-level or global state. That is correct for a program
that runs once and exits, and wrong the moment the orchestrator calls it once per source in the
same process — which is exactly what "the Module 6 loading program works as a template" (step 16)
invites. The counts then **accumulate**: each source reports every record loaded so far.
(`sdk_guide(topic='load', language='java', record_count=1000)`, server 1.32.9, 2026-08-14.)

⚠️ **This failure looks like data, not like a bug.** Observed on three sources of 10 / 10 / 8
records, the summary read 10, then 20, then 28 — plausible, monotonic, and summing to the correct
total, with the load itself entirely correct. A bootcamper reads it as "Summit Billing has 28
records". The same arithmetic conceals a real per-source failure: a source that loaded **0 of 8**
still shows a rising success count inherited from its predecessors. This is the silent-wrong-value
class `ground-rules.md` → "Defensive parsing" covers (INV-115), except that a wrong number is
worse than a blank, because nothing about it invites a second look.

Resolve it one of two ways, whichever suits the bootcamper's language (INV-002):

- **Scope the counters per source** — make them state the orchestrator owns, reset at each
  source's boundary, so the loader reports into a fresh tally each time; or
- **Run each source's load in its own process**, so the process-global state starts clean by
  construction. This also isolates a crash in one source's load, which the error-isolation
  requirement above already asks for.

⛔ **Reconcile the per-source figures before showing them.** (INV-243) Each source's reported count MUST
match that source's own input record count, and the per-source counts MUST sum to the aggregate.
Report the comparison, not just the totals; if they disagree, say so and stop rather than
printing a number that cannot be traced to an input file (INV-245) — a figure the run has
itself disproved must not appear as a result. A summary that cannot be reconciled against the
inputs is not a summary — and the accumulating-counter defect above passes every check that looks
only at the total.

**Production orchestration patterns to include:**

- **Retry with exponential backoff:** when a source fails to load, retry with increasing delays
  (1s, 2s, 4s, 8s) up to a configurable maximum. Log each retry attempt.
- **Partial success handling:** if some sources succeed and others fail, mark successful sources
  as loaded and report failed sources with error details. Do not roll back successful loads when
  one source fails.
- **Error isolation:** errors in one source's loading must not affect other sources. Each source
  loads in its own error boundary.
- **Orchestrator health monitoring:** track overall health, elapsed time, sources completed vs.
  remaining, error rate across all sources. Log periodic health summaries.

**Checkpoint:** write step 17.

## 18. Test orchestrator with sample data

Test the orchestrator with 10–100 records per source. Verify: sources load without errors,
dependencies respected, progress tracking works, error handling triggers correctly. Report the
sample-data test results and let the bootcamper know the orchestrator is ready for the full
dataset.

**Checkpoint:** write step 18.

## 19. Run full orchestration

Run on the complete dataset. Monitor per-source progress, error rates, overall completion, and
elapsed/estimated time. If slow, suggest reducing parallelism.

**⚠️ SQLite note:** if total records exceed 1,000, recommend loading a subset first to validate
cross-source matching, then load more or switch to PostgreSQL (a production follow-up; see the graduation migration checklist).

**Checkpoint:** write step 19.

## 20. Coordinated redo queue processing

Drain the redo queue, critical after multi-source loading for cross-source match refinement.
Use `generate_scaffold(language='<chosen_language>', workflow='redo', version='current')` and
override paths to `database/G2C.db`.

⛔ **Same batch-drain requirement as Phase B, step 9** (INV-151) — read it there rather than
re-deriving it.
In short: the MCP redo templates target streaming ingest and the observed one never terminates on an
empty queue, so check the returned snippet and, if it loops, replace the sleep-and-continue with a
break. The loop sentinel is the **fetch returning no record**, never a redo-count method (full table
scan per call, and processing redo generates more redo). Report the count processed and that the
queue reached empty.

**Production redo patterns:**

- Process redos after all sources are loaded (not between sources) to minimize redundant
  re-evaluations
- Monitor redo queue depth during processing, a growing queue may indicate data-quality issues —
  monitoring depth is not the same as using it as the loop condition, which the batch drain forbids
- Log redo processing statistics: total redos processed, duration, entities affected

Tell the bootcamper: "Processing the redo queue now. This refines cross-source entity resolution.
Without it, some matches between your sources would be incomplete."

**Checkpoint:** write step 20.

⛔ **Steps 17–20 ask nothing, so this turn does not end here** — the orchestration summary and its
record counts conclude something and read like an ending, which is precisely the trap
(`ground-rules.md` → "A results presentation is not a turn ending", INV-225). Continue into Phase D in the
same turn, up to its first 👉.

Proceed to Phase D (`phaseD-validation.md`).
