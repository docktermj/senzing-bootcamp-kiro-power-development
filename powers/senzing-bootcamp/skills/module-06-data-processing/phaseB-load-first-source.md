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
Phase A's pre-load checks (INV-089).** It needs two things Phase A produces: the loading program itself,
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

⛔ **(INV-297) The engine writes its own diagnostics to that console, and they are NOT per-record failures —
say which is which before the Bootcamper reads one.** This step and step 7 both point them at the
output, so they will see engine-level lines prefixed `ERR:` (they carry an `[szstatic:…]` thread
tag) sitting beside a loader summary that says **0 failed**, with nothing telling them the two are
different things. **The loader's own `failed` count and its error log are the authority on record
failures**; a line the engine wrote about its internal state is not one, and neither confirms nor
denies the other.

What to say when one appears: name it as engine output rather than a failed record, and point at
the reconciliation that settles it — records attempted equals records loaded, the redo queue
reached empty, and the error log is absent or empty. If those three hold, nothing was lost.

⚠️ **Do not explain what a specific engine message means unless a route serves it.**
`search_docs(query='resolved entity is out of sync expected got concurrent loading SQLite lock')`
returns **no document naming that message** — owner-checked: `search_docs` is the corpus route for a
documented engine message, and the nearest material it serves is the *"Enabling the Per-Entity
Feature Store & Advisory Locking in Senzing 4.4.0"* article, which states that on SQLite the engine
*"falls back to `LEASE` automatically"* with no advisory locks; so the message is uncovered by the
corpus rather than missed by the query (absence negative) — server **1.36.0**, 2026-09-02. An
`out of sync` line seen during a concurrent SQLite load is therefore reported as **an environment
observation**, with the SDK version and date, or not characterized at all (INV-080/INV-149) — never
as a Senzing fact and never as reassurance the Power cannot source.
<!-- MCP-NEGATIVE: search_docs(query='resolved entity is out of sync expected got concurrent loading SQLite lock') — no indexed document names the "Resolved entity … is out of sync" engine message — owner: search_docs IS the corpus route for a documented engine message and the nearest material it serves is the 4.4.0 advisory-locking article stating SQLite falls back to LEASE with no advisory locks, so the message is uncovered by the corpus rather than missed by the query (absence negative) — server 1.36.0, 2026-09-02 -->

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

⛔ **(INV-295) Read `license_record_limit_measured_at` alongside it, and treat a reading marked provisional —
or carrying no marker — as the absent case below.** SDK setup's Step 5a takes its reading before
Step 8 writes `CONFIGPATH`, so it cannot see a license installed at the system config path. A
provisional figure is a genuine measurement of an incomplete view, which is the one shape the
absent-versus-present split above cannot see on its own.

- **`0` (no cap), or ≥ the dataset size**, the active license permits the full load: omit the
  evaluation-capacity warning and proceed.
- **Positive and below the dataset size**, the dataset genuinely exceeds the cap: the single
  License Key gate (Module 4, Step 8a) already offered to expand capacity — restate that a larger
  license lets the full load proceed, as a choice, not a wall; do not force downsizing.

  ⛔ **Read `license_key_requested` from `config/bootcamp_progress.json` first, and say the license may
  already be here.** When it records a sent request, state plainly that the license is delivered **by
  email**, that it may already have arrived, and that it can be applied now — including in a later
  session. ⚠️ **Only when a request is outstanding.** `license: evaluation` is written both after a
  request was sent *and* when the Bootcamper **declined** to send one, so keying this reminder to it
  would tell someone who declined to go hunting for a license they never asked for. Absent
  `license_key_requested` → no reminder; say nothing about email.

  **The apply procedure already exists — point at it, do not restate it (INV-300).** Module 4 Step 8a
  **sub-step 5** decodes a Base64 key or copies a `.lic` to `licenses/g2.lic`, adds `LICENSEFILE` to
  the engine-config PIPELINE section, and records `license: custom`. ⛔ **Do not write a second copy
  of it here, and do not substitute a different mechanism.** A platform-specific procedure duplicated
  is a procedure that drifts, and the MCP server describes a *different* route
  (`SENZING_LICENSE_FILE`, or a license file in `etc/`) which is real but is **not** the one wired
  into this bootcamp's file layout — using it here would leave the engine config pointing at nothing.

  **Then re-measure and re-enter these branches.** After applying, re-read the license via
  `SzProduct.get_license()`, parse `recordLimit`, confirm it actually moved, and route again on the
  new value — a license reporting `0` lands on the first branch and the whole cap discussion
  dissolves. ⚠️ Do **not** state the evaluation license's size or duration from this file: those
  figures change between releases, so take them from a runtime lookup at the moment of use or say
  they are unavailable.

  End the turn on this single pinned question (INV-056), which replaces the improvised one — it is
  **one** 👉 (INV-251) and it is **not** a second License Key gate (INV-093: that decision was asked
  once, in Module 4, and is settled — this offers a *procedure* and a *status readout*, not the
  question again):

  > 👉 **Your dataset is larger than this license allows. How would you like to proceed? Reply with a number:**
  >
  > 1. **Load an overlap-preserving subset now** — keeps cross-source matches visible at this capacity.
  > 2. **Apply a license I have** — I'll walk you through it, then load everything.
  > 3. **Load the first records as they come** — simplest, but cross-source overlap may be lost.

  *(Internal: end the turn on this question and wait.)* On **2**, follow Step 8a sub-step 5, then
  re-measure and re-enter these branches. ⛔ **Option 2 stays on the list even when
  `license_key_requested` is absent** — a Bootcamper may hold a license the bootcamp never asked about,
  and it is the option this branch previously omitted entirely; what the `license_key_requested`
  marker gates is only the *"check your email, it may have arrived"* line above.
- **Absent or null** — ⛔ **"never measured", not "no custom license": measure before warning.** (INV-244) This
  is the same branch, and the same trap, as Phase A's — **every step that writes
  `license_record_limit` writes only a MEASURED value**, so its absence says nothing about the
  installed license: SDK setup's Step 5a measures as soon as the SDK is verified and deliberately
  writes nothing when it cannot, and Module 4's **volume-gated** Step 8a fires only when the
  collected volume approaches the limit.
  ⚠️ **Do not reason from a count of writers**; that number has been stated wrongly twice. Measure
  it exactly as Phase A's absent branch instructs (Module 4 Step 8a's procedure:
  `SzProduct.get_license()`, confirm the shape, parse `recordLimit`), persist it, and re-enter
  these three branches with the measured value — a license reporting `recordLimit: 0` then lands on
  the first branch and the warning is correctly omitted. If Phase A already measured and persisted
  it, this branch is not reached.
  - **Only if the measurement fails** does the evaluation-capacity warning apply. Say it is an
    assumption, and confirm the current capacity figure and the exact over-limit error code and
    behavior from the Senzing MCP server at request time. If no figure is returned, say it is
    currently unavailable rather than restating a remembered one.

**Data source registry.** On success, update `load_status` to `loaded` in
`config/data_sources.yaml`. On failure, set `load_status` to `failed` and add an `issues` entry
describing the error. Update `updated_at` either way. ⛔ **Do not write the loaded count over
`record_count` — reconcile first, per the rule below, which decides both what `load_status` becomes
and where the loaded figure is recorded.**

⛔ **Reconcile the loaded count against this source's own input *before* writing it — the value you
are about to overwrite is the baseline.** (INV-243) `record_count` already holds the count Data
collection **measured in the collected file**, alongside `expected_record_count` (what the provider
stated), recorded there precisely "so the two can be compared here and re-checked later". Compare
the loader's success count against that existing `record_count` first, and record the outcome under
`validation_checks` as `load_count_matches_source` — the same auditable idiom Data collection
already uses for `record_count_matches_expected`, so the comparison lives in the registry rather
than only in the turn that ran it.

⛔ **If the two disagree, write the discrepancy rather than the count** (INV-245): leave the
existing `record_count` in place, record **both** figures, and do not present the loaded count as a
bare result. Overwriting on a mismatch is the worst outcome available — it destroys the input
baseline and files a partial load as a complete one, after which nothing downstream can tell the
difference. This is the point where the figure enters durable state: `phaseC` step 12 reads it
straight back out and presents it to the bootcamper, and Phase D writes it into
`docs/loading_strategy.md`, so a number that was never checked here is never checked at all — it
simply acquires the authority of having been written down. Reporting the aggregate alone does not
discharge this: the failure mode this exists for produces figures that are plausible and sum
correctly.

⛔ **A disagreement has THREE outcomes, not two. Do not collapse them.** INV-245 forbids presenting
a value that **failed its own verification check**; a delta the mapping specification *predicts* has
not failed verification — it is verified and reconciled, which is a different state from unverified.
Route on which of these it is:

| Outcome | `load_status` | What else to record |
|---|---|---|
| **Equal** | `loaded` | `validation_checks.load_count_matches_source: pass` |
| **Explained delta** — a named mapping artifact predicts it | `loaded` | both figures; `validation_checks.load_count_matches_source: expected_delta`; a `load_reconciliation` note naming the disposition **and the document that predicts it** |
| **Unexplained delta** | `failed` | both figures in the `issues` entry, exactly as above |

⛔ **The explained branch is reachable ONLY with a citation, never with an assertion.** The note must
name the mapping artifact that predicts the delta — the source's own mapping specification, or the
recorded disposition in `config/data_sources.yaml`. *"The mapping probably explains it"* is precisely
the failure INV-245 exists to prevent, and without the citation requirement this branch becomes a
universal escape hatch wearing the rule as a disguise. No citation → **unexplained** → `failed`.

⚠️ **This is not a hypothetical branch: the bootcamp teaches the mapping that reaches it.**
`embedded_master` is a disposition Module 5 teaches under its own heading, defined as *"the value
becomes its own Senzing record, and the parent points at it"* — a disposition whose definition is
"emit an additional record" **necessarily** makes the loaded count exceed the input count. One source
loaded **3,727** records against a measured `record_count` of **3,488**: 239 distinct lenders emitted
as embedded masters, exactly as that source's mapping specification prescribes, every input record
loaded, zero errors. Under a two-way rule the only compliant action was to file a completely
successful load as `failed`, and to write that into the Bootcamper's own loading strategy.

**The baseline stays immutable in all three branches** (INV-243) — the existing `record_count` is
never overwritten and the loaded figure is recorded beside it. That half of the rule is correct and
is not what changed.

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
