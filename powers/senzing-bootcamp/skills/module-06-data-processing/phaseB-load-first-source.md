# Module 6, Phase B: Load First Source (steps 5–11)

Continues from Phase A. Follow the ground rules; `🛑`/`⛔` are internal control directives.
Loading and redo code comes from the MCP tools (`generate_scaffold` / `sdk_guide`), never
hand-written. Back up `database/G2C.db` before loading. The `DATA_SOURCE` codes in this data
were registered in Phase A (step 4a), so the load runs against a config that already knows them
(the loader's generic `SENZ2207` handling remains a fallback).

## 5. Test with sample data (if Phase 3 was skipped)

If the bootcamper did not complete Phase 3 in Module 5, run the loading program on a small
subset first:

- Start with 10–100 records
- Verify the program connects to the engine
- Check that records are being added successfully
- Observe any errors or warnings

**On success, set `test_load_status: complete` for that source in `config/data_sources.yaml`.**
Phase A's pre-load check reads this field to decide whether a test load is owed, so a run that
is not recorded is a run that Phase A will ask for again on a resumed session.

⛔ **This is the earliest point the test load can run, which is why it lives here and not in
Phase A's pre-load checks.** It needs two things Phase A produces: the loading program itself,
built at step 3 from the volume tier captured at step 1, and the registered `DATA_SOURCE` codes
from step 4a — without which the load fails with `SENZ2207` (*"Data source code [{0}] does not
exist"*, `explain_error_code('SENZ2207')`, server 1.32.9, 2026-08-14), the exact error step 4a
exists to prevent. Do not move it earlier, and do not add a second copy upstream.

If Phase 3 was completed, skip this step, the test load already verified basic loading. Proceed
directly to production loading.

**Checkpoint:** write step 5.

## 6. Observe entity resolution in real time

As records load, Senzing resolves entities automatically:

- Watch the console output for resolution activity
- Note how entities are being formed
- See how new records match or create entities
- This gives immediate feedback on data quality and matching behavior

**Checkpoint:** write step 6.

## 7. Load the full dataset

Run the program on the complete data source with production-quality monitoring:

- Monitor progress and throughput performance
- Watch for error-rate trends (increasing errors may indicate data issues)
- Note loading statistics (time, throughput, error rate)
- If errors exceed 5%, pause and investigate before continuing

**License capacity before loading.** Before warning that the load will stop at the built-in
evaluation limit (a licensing error at the cap), read `license_record_limit` from
`config/bootcamp_progress.json` (the Module 4 license gate at Step 8a persists it after a custom
license is configured) and drive the decision from that effective limit, never a remembered or
hardcoded figure:

- **`0` (no cap), or ≥ the dataset size**, the active license permits the full load: omit the
  evaluation-capacity warning and proceed.
- **Positive and below the dataset size**, the dataset genuinely exceeds the cap: the single
  License Key gate (Module 4, Step 8a) already offered to expand capacity — restate that a larger
  license lets the full load proceed, as a choice, not a wall; do not force downsizing.
- **Absent or null** — ⛔ **"never asked", not "no custom license": measure before warning.** (INV-244) This
  is the same branch, and the same trap, as Phase A's — `license_record_limit` is written only by
  Module 4's volume-gated Step 8a, so its absence says nothing about the installed license. Measure
  it exactly as Phase A's absent branch instructs (Module 4 Step 8a's procedure:
  `SzProduct.get_license()`, confirm the shape, parse `recordLimit`), persist it, and re-enter
  these three branches with the measured value — a license reporting `recordLimit: 0` then lands on
  the first branch and the warning is correctly omitted. If Phase A already measured and persisted
  it, this branch is not reached.
  - **Only if the measurement fails** does the evaluation-capacity warning apply. Say it is an
    assumption, and confirm the current capacity figure and the exact over-limit error code and
    behavior from the Senzing MCP server at request time. If no figure is returned, say it is
    currently unavailable rather than restating a remembered one.

**Data source registry.** On success, update `load_status` to `loaded` and `record_count` to the
actual loaded count in `config/data_sources.yaml`. On failure, set `load_status` to `failed` and
add an `issues` entry describing the error. Update `updated_at` either way.

⛔ **Reconcile the loaded count against this source's own input *before* writing it — the value you
are about to overwrite is the baseline.** (INV-243) `record_count` already holds the count Data
collection **measured in the collected file**, alongside `expected_record_count` (what the provider
stated), recorded there precisely "so the two can be compared here and re-checked later". Compare
the loader's success count against that existing `record_count` first, and record the outcome under
`validation_checks` as `load_count_matches_source` — the same auditable idiom Data collection
already uses for `record_count_matches_expected`, so the comparison lives in the registry rather
than only in the turn that ran it.

⛔ **If the two disagree, write the discrepancy rather than the count** (INV-245): leave the
existing `record_count` in place, set `load_status` to `failed`, record **both** figures in the
`issues` entry, and do not present the loaded count as a result. Overwriting on a mismatch is the
worst outcome available — it destroys the input baseline and files a partial load as a complete
one, after which nothing downstream can tell the difference. This is the point where the figure
enters durable state: `phaseC` step 12 reads it straight back out and presents it to the
bootcamper, and Phase D writes it into `docs/loading_strategy.md`, so a number that was never
checked here is never checked at all — it simply acquires the authority of having been written
down. Reporting the aggregate alone does not discharge this: the failure mode this exists for
produces figures that are plausible and sum correctly.

**⚠️ SQLite performance note — only when the volume question is still open.** On SQLite with
single-threaded loading, entity resolution gets progressively slower as the database grows.

⛔ **Check first whether this was already decided, and say nothing if it was.** Read the
`sqlite_volume_prompt` marker in `config/bootcamp_preferences.yaml` (Phase A's pre-load check) and
the Module 4 Step 8b load decision. If either records a choice for this same load — `proceed`,
`sample`, or a database switch — **honor it silently and load what it says**. Two gates already put
this to the bootcamper; re-opening it here would be a third ask on a settled question (INV-006) and
would push a dataset smaller than the one they chose, which is exactly what leaves Modules 6 and 7
under-demonstrating cross-source resolution (INV-150).

Only when **no** decision is recorded and the database is SQLite may you suggest starting smaller:
"Let's start with the first 1,000 records so we can see results quickly. Once we validate the
results here, we can load the full dataset, or switch to PostgreSQL for better performance with
larger volumes (a production follow-up; see the graduation migration checklist)." Record the
resulting choice in `sqlite_volume_prompt` so the question stays asked once.

**Checkpoint:** write step 7.

## 8. Save and document the loading program

- Save in `src/load/` with a clear name (e.g. `src/load/load_customer_db.[ext]`); all loading
  programs live in `src/load/`
- Document how to run it (command line, configuration)
- Note any prerequisites or dependencies
- Keep it for future reloads or updates

**Checkpoint:** write step 8.

## 9. Process redo records

After loading completes, drain the redo queue. Redo records are deferred re-evaluations that
refine the entity resolution graph, without processing them, results are incomplete.

Use `generate_scaffold(language='<chosen_language>', workflow='redo', version='current')` for the
redo processing pattern. The loading program (or a separate script) should sequentially process
all pending redos until the queue is empty. If the generated redo scaffold uses `/tmp/`,
`ExampleEnvironment`, or any path outside the working directory, override the database path to
`database/G2C.db`.

⛔ **The bootcamp needs a batch drain that terminates. Check the returned snippet before running
it.** The MCP redo templates target *streaming ingest*, where never stopping is the point: the
observed `sdk_guide(topic='redo')` answer prints "pausing for 30 seconds" on an empty queue and
loops forever. Run that unmodified after a batch load and the session simply hangs — no error, no
output, indistinguishable from slow work, which is the worst shape a failure can take here.

If the snippet loops on an empty queue, adapt it: keep its structure and concurrency, and replace
the sleep-and-continue with a break. The shape the batch step needs, stated language-agnostically
(INV-002):

1. Fetch the next redo record.
2. If none was returned, the queue is empty — exit the loop.
3. Otherwise process it, and repeat.

**The fetch's return value is the loop sentinel.** ⛔ Do **not** poll a redo-*count* method as the
loop condition: it is a full table scan per call, so the drain becomes O(n²) — and because
processing a redo record generates more redo records, the loop runs longer than the initial count
suggests (a backlog of 384 took 400 processed calls in the reported session). Confirm the method
names for the chosen binding from MCP (INV-080/INV-132), and confirm the anti-pattern itself via
`search_docs(query="redo", category="anti_patterns")` rather than trusting this note.

Report the terminal condition: how many redo records were processed, and that the queue reached
empty. A drain that finishes silently cannot be told from one still running.

Include a code comment explaining that in production, redos are typically handled by an
always-running redo processor that wakes, checks for pending redos, processes them, and sleeps
when the queue is empty — that is the **streaming** pattern, and it is deliberately *not* what this
batch step runs. Naming the difference is what stops the non-terminating template looking like the
correct answer.

Tell the bootcamper: "Processing the redo queue now. This refines entity resolution, without
it, some matches would be incomplete."

**Checkpoint:** write step 9.

## 10. Incremental loading strategy

Discuss incremental loading as a production concern distinct from the initial bulk load:

- **Full reload** (what we just did): load all records every time. Simple but slow for large
  datasets.
- **Incremental load** (production pattern): track which records are new or changed since the
  last load; load only deltas. Requires a change-detection mechanism (timestamps, sequence
  numbers, change data capture).
- **Upsert pattern:** use `add_record` with the same `RECORD_ID` to update existing records.
  Senzing re-evaluates entity resolution automatically.
- Help the bootcamper understand when each strategy applies and document the choice in
  `docs/loading_strategy.md`.

**Checkpoint:** write step 10.

## 11. Mark first data source as loaded

Once loading and redo processing are complete, mark this data source as loaded in
`config/data_sources.yaml`.

**Checkpoint:** write step 11.

**Next:** if the bootcamper has 2 or more data sources with `mapping_status: complete`, proceed
to Phase C (`phaseC-multi-source.md`). If only ONE data source, skip Phase C and go directly to
Phase D (`phaseD-validation.md`).
