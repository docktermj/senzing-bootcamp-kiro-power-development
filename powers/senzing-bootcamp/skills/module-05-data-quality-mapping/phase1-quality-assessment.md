# Module 5, Phase 1: Quality Assessment (steps 1–7)

Verify data sources against the Entity Specification. Follow the ground rules. `🛑`/`⛔` are
internal directives: do not render them; signal a stop by ending the turn on the single 👉
question and waiting.

## 1. List the agreed-upon data sources

Recap what the bootcamper actually brought into this module. **`config/data_sources.yaml` is the
list** — Data collection registers every source it acquired there, with its counts and provenance.
Read `docs/business_problem.md` for the **why**: the business context that motivated each source,
which is what makes the recap worth reading.

⛔ **Do not take the source list from `docs/business_problem.md`.** That file records what was
*discussed* in Discover the Business Problem, before Data collection ran. `config/data_sources.yaml`
is the registry INV-203 gates: a source is recorded there only after its fetch returned 2xx **and**
its measured record count matched, so it is the only list that says what was actually collected. The two routinely differ —
Data collection is exactly where a bootcamper substitutes a CORD dataset for data they cannot share
— and this module processes what is in `data/raw/`, not what was once intended. Where the two lists
differ, say so in one line rather than silently preferring either: "we talked about X; what you
collected is Y."

**Checkpoint:** write step 1 to `config/bootcamp_progress.json`.

## 2. Confirm the source files are present

⛔ **Do not ask the bootcamper to place files here by default.** This module's prerequisite is
"Module 4 complete (data sources collected, files in `data/raw/`)" — Data collection is a required
module that runs immediately before this one, so asking for what it already fetched is a question
the bootcamp does not need to ask (INV-006/INV-012). Worse, a bootcamper who takes it literally may
re-fetch, which on a CORD source is a second download and a live rate-limit hazard
(`cord-download-rate-limit-is-saved-as-data`, INV-203).

**Verify instead.** For each source registered in `config/data_sources.yaml`:

- confirm its file exists at the recorded path under `data/raw/`;
- confirm its record count still matches the count recorded at collection (INV-203 wrote both);
- report what you found — one line per source, not a wall of output (INV-012).

**Ask only in the two cases where there is genuinely nothing to verify:**

- a source is registered but its file is **missing**; or
- the registry is **empty** — the bring-your-own-data path, which is real and supported: a
  bootcamper whose data cannot leave their machine reaches this module with nothing collected.

In either case, ask for what is missing in a single 👉 question, naming the forms that work:

- CSV files (first 10-20 rows)
- JSON samples
- Database schema with sample values
- Screenshots of data tables
- Text descriptions of fields and data types

**Checkpoint:** write step 2.

## 3. Understand the Senzing Generic Entity Specification

Call `download_resource(filename="senzing_entity_specification.md")` to **locate** the current
Senzing Generic Entity Specification.

⛔ **The response is a listing, not the document.** Verified on server **1.32.9, 2026-08-14**: the
call returns `mode: "url"` and a `resources` array whose entry carries `filename`, `size_bytes` and
a `url` — and **no content**. There is nothing in the response to "save", so a guide that writes the
response itself to the canonical path leaves Steps 4, 5, 5a and 6 reading attribute names out of a
file that has none — and because a file still exists at the expected path, the failure is silent.
`download_resource` is the third MCP tool with this shape; `ground-rules.md` → "Working examples"
states the rule once for all three (INV-234).

**Retrieve it in two steps:**

1. **Fetch the `url`** the response gave you, using the HTTP client idiomatic to this bootcamp's
   chosen language (INV-002) — not a hard-coded `curl`, which is not present on every supported
   platform (INV-001).
2. **Save the body** to the single canonical copy at
   `docs/reference/senzing_entity_specification.md` (do not create duplicate copies elsewhere), then
   **check the saved file's size against the response's `size_bytes`** before using it. On
   2026-08-14 that was **73,051 bytes**, and a fetched-then-saved copy matched it exactly. A
   truncated fetch, or a saved error page, is caught here in one comparison instead of surfacing in
   Step 4 as attribute names that are merely absent. (INV-228's count-check discipline, applied to a
   resource fetch rather than a dataset.)

⚠️ **If the URL fetch fails, `inline=true` is the sanctioned fallback for this tool — and for this
tool only.** `download_resource`'s declared schema carries `filename`, `filenames`, `inline` and
`version`, so INV-136 permits `inline` here, and the resource's own `on_failure` names it: *"Fallback:
call download_resource with this filename and inline=true."* Use it only **after** the URL fetch
fails — the parameter's own description says to try the default `inline=false` first — and expect it
to cost context, since the full 73 KB then arrives inside the response. This is the **opposite** of
the rule for `generate_scaffold` and `find_examples`, whose schemas do not declare `inline` at all,
so passing it there is a call that cannot work. The difference is not about the word `inline`; it is
about what each tool's schema declares (INV-136).

**How to consult it: targeted lookup, never end to end.** The file is **73 KB**. Look up the
specific feature or attribute in question — grep for the attribute code, or open the single section
that covers it. Do **not** read it front to back. `mapping_workflow` says so itself, at both its
step 2 and step 3 (verbatim, server 1.32.9, 2026-08-14): *"Do NOT attempt to read it end-to-end —
that is unnecessary and will overflow limited context windows."* That overflow costs the Bootcamper
the rest of their session, not merely some tokens.

**The scope of its authority is this phase.** Within Phase 1 the specification is the reference for
attribute names, types and structures — Steps 4, 5, 5a and 6 all compare against it. From
`mapping_workflow` step 2 onward the workflow delivers its own **distilled inline mapping
reference** (the feature catalog, the identifier-classification workflow, and the exact attribute
keys), and *that* is the working reference for the mapping phase; the tool states the 73 KB file "is
available only as an optional deep-dive" for an edge case the inline reference does not cover. Phase
2 already cites the inline reference — relay this rather than leaving a guide holding two references
with no basis for preferring either.

⚠️ **Two copies on disk is expected, and is not a breach of the rule above.** `mapping_workflow`
step 1's own `resources` list writes `senzing_entity_specification.md` into the workflow's
`workspace_dir` — `data/mapping/`, per INV-136 — verified on server 1.32.9, 2026-08-14. That is the
tool's copy for the mapping phase; `docs/reference/senzing_entity_specification.md` is this phase's
canonical copy. The no-duplicates rule governs copies **the guide** makes; it is not violated by the
tool populating its own workspace. Do not delete either, and do not re-fetch to reconcile them.

**Checkpoint:** write step 3.

## 4. Compare each data source with the Entity Specification

Using the Entity Specification retrieved in Step 3 as the reference, compare each data source's
fields against the specification's attribute names. For each data source provided:

- Identify which fields map directly to attributes defined in the Entity Specification.
- Identify fields that need transformation (e.g., combining or splitting fields to match the
  specification's expected structure).
- Identify fields with non-standard names that correspond to attributes in the Entity
  Specification.
- Note any missing critical fields defined in the Entity Specification.
- Check if `DATA_SOURCE` and `RECORD_ID` are present or can be derived.

**Checkpoint:** write step 4.

## 5. Categorize each data source

(Using the Entity Specification retrieved in Step 3 as the source of truth for what constitutes
compliant attribute names.)

- **Entity Specification-compliant:** Data already uses attribute names and structures that
  match the Entity Specification. CORD sources (the already-Senzing-ready fast-path class) are
  **eligible to be considered** for the fast-path (Step 5a, offered only for `provenance: cord`);
  Step 5a decides, and it offers the skip only when the source is both structurally loadable
  **and** fully mapped (INV-198) — a CORD source carrying fields that resolve to no specification attribute
  goes through mapping like any other. Do not route a source past mapping from this
  categorization; that is Step 5a's call. Other compliant sources, including non-CORD data that
  looks Senzing-ready, continue to Phase 2, which confirms compliance and records lineage before
  loading.
- **Needs mapping:** Data uses different field names or structures than those defined in the
  Entity Specification. Continue to Phase 2 (data mapping).
- **Needs enrichment:** Data is missing critical attributes. Discuss with the user whether
  additional data sources can provide the missing information.

**Checkpoint:** write step 5.

## 5a. Senzing-readiness check and fast-path offer (CORD sources only)

For each source where `provenance` is `cord` in `config/data_sources.yaml` (that is, a source
obtained via the `get_sample_data` MCP tool in Module 4):

1. **Obtain the Senzing schema definition:** Reuse the Senzing Generic Entity Specification
   already retrieved in Step 3: do not download it again. From that same MCP-sourced
   specification, extract the list of required top-level structural indicators for a
   Senzing-loadable record (e.g., presence of a FEATURES array, DATA_SOURCE, RECORD_ID).

   ⛔ **Loadable is a wider test than "has a FEATURES array".** The same specification states that
   the older shape — "a flat JSON structure with a separate sub-list for each feature that had
   multiple values" — is **still supported**. Treat **both** forms as Senzing-ready:

   - the recommended **`FEATURES` array**; or
   - the legacy **flat structure**: feature attributes at the record root
     (`BUSINESS_NAME_ORG`, `RECORD_TYPE`, …), with a per-feature root sub-list (`NAMES`,
     `ADDRESSES`, `IDENTIFIERS`) wherever a feature repeats. A source with no repeating feature is
     in this shape with no sub-list at all — flat root attributes only.

   **CORD ships both, so neither may be assumed.** Verified live —
   `get_sample_data(dataset='london', source='GLOBALDATA')` returns a `FEATURES` array (with the
   raw source columns alongside it at the record root), while
   `get_sample_data(dataset='las-vegas', source='PPP_LOANS')` returns flat root attributes
   (`BUSINESS_NAME_ORG`, `RECORD_TYPE`, `BUSINESS_ADDR_*`) and no `FEATURES` array at all
   (MCP server 1.32.9, re-verified 2026-08-14). Requiring `FEATURES` alone classifies the legacy-shaped sources as not-ready and
   sends data that already loads and resolves through a mapping phase it does not need. Sample the
   actual records rather than assuming a dataset's shape, and confirm the still-supported statement
   from the specification you retrieved (INV-080), not from this file.

2. **Perform the structural check: will it load?** Examine up to 100 sample records from the
   source file. For each record, verify:

   - The record is valid JSON.
   - The record contains the structural indicators identified from the Entity Specification
     (top-level keys, array structures).
   - DATA_SOURCE and RECORD_ID are present or derivable.

   If ALL sampled records pass, classify as **structurally loadable**. If ANY sampled record
   fails, classify as not structurally loadable. (No readiness helper is bundled; perform the
   check directly against the sampled records.)

   ⛔ **This is the entry condition, not the fast-path condition.** Structurally loadable means the
   engine will accept the record; it does not mean every field in it has been decided about. Step 3
   below answers that second question, and the offer in step 5 is gated on **both**. Classifying a
   partially-mapped source as ready on this test alone is what let a source with eleven
   undispositioned columns skip the module (see step 3).

   **A stronger check, when the engine is available: ask Senzing how it reads the record.** The
   structural test above confirms the *shape*; it cannot tell you whether an attribute name will
   actually participate in matching. `getRecordPreview` returns Senzing's own interpretation of a
   record **without loading it**, which answers that directly — and it beats reading field names
   against the specification by eye. Obtain the call for the bootcamper's binding from MCP
   (`get_sdk_reference(topic='parameters', filter='getRecordPreview')`; the method name and argument
   types differ per binding — INV-132) rather than writing it from memory.

   ⛔ **Preview requires the record's `DATA_SOURCE` code to be registered first, even though it
   writes nothing.** This is counter-intuitive and it is why the check fails where it is most natural
   to run: registration belongs to the loading phase, so a readiness check reaching for preview
   before registration gets

   ```text
   SENZ2207|Data source code [<CODE>] does not exist
   ```

   The prerequisite is **not** documented on the method — **still true, re-verified 2026-08-11 on
   MCP server 1.32.8** (first observed 2026-07-30 on 1.32.2):
   `get_sdk_reference(topic='parameters', filter='getRecordPreview')` returns one signature per
   binding — `get_record_preview(record_definition: str, flags: int = …) -> str` in Python — with no
   mention of it.
   (The same call also returns `get_record`, which the filter matches too; that is a second
   *method*, not a second overload.) So the order is: register the source code(s) — taking the
   registration code from `sdk_guide(topic='configure')`, never hand-written (INV-080) — then preview.
   Registration is idempotent and the loading phase needs it anyway, so doing it here costs nothing.

   On `SENZ2207`, call `explain_error_code('SENZ2207')` first as always (INV-080): unlike some codes,
   its own resolution steps *do* name the fix — register the code, confirm the registered list, mind
   that codes are case-sensitive and conventionally UPPERCASE, and reinitialize afterwards — so do not
   restate them here, just follow them.

   **Optional and non-blocking.** If the engine is not available, or registration has not happened
   and you would rather not do it at this point, skip the preview and keep the structural check
   (INV-048). Say which check ran, so `senzing_loadable` never implies a stronger test than was
   performed. The prerequisite applies wherever a preview-based check is used, not only to the CORD
   sources this step covers.

3. **Perform the coverage check: is every field actually decided about?** Structurally loadable
   answers *will it load*. This answers *is there anything left to map* — and they are not the same
   question. Over the same sampled records, partition every root key into three sets:

   - **structural keys** — `DATA_SOURCE`, `RECORD_ID`, `RECORD_TYPE`, `FEATURES`, and the legacy
     per-feature root sub-lists (`NAMES`, `ADDRESSES`, `IDENTIFIERS`, …);
   - **specification attributes** — keys that resolve to an attribute in the Entity Specification
     you retrieved in Step 3 (the same copy step 1 above reuses — do not download it again);
   - **unrecognized keys** — everything else.

   ⛔ **Do not resolve the second set by exact string match against the attribute catalog.** A
   catalog attribute can arrive carrying a leading label, and an exact match reports it as
   unrecognized — which would route a genuinely fully-mapped source into mapping, the pointless work
   the fast-path exists to remove. This is not hypothetical: `get_sample_data(dataset='las-vegas',
   source='PPP_LOANS')` ships `BUSINESS_NAME_ORG` and `BUSINESS_ADDR_LINE1`/`CITY`/`STATE`/
   `POSTAL_CODE`, while the specification's catalog names the attributes `NAME_ORG` and
   `ADDR_LINE1`/`ADDR_CITY`/… (Entity Specification, *Feature: NAME*; and *Usage types and payload
   (optional attributes)*, which defines a usage type as "a short label that distinguishes multiple
   instances of the same feature on one entity" — both confirmed via
   `search_docs(category='data_mapping')`, MCP server 1.32.8, docs index 2026-08-11). Resolve each
   key against the specification you hold, and where a key is a catalog attribute carrying such a
   label, count it as a specification attribute. ⛔ The label **encoding** on a flat attribute name
   is an observed shape, not something the indexed specification states — so where you cannot
   resolve a key with confidence, treat it as unrecognized and let step 6 name it, or use the
   optional `getRecordPreview` check above to ask Senzing directly how it reads the record.

   **The threshold is a count, not a proportion: zero unrecognized keys, or no fast-path offer.**
   Recorded here with its reasoning, because it is a decision and not an obvious default:

   - **Why not a percentage.** A proportion has to be tuned against how wide the source happens to
     be. `PPP_LOANS` is 11 unrecognized of 19 keys and any threshold catches it; a source with one
     undecided column in thirty passes an 80%-coverage rule while still hiding a decision from the
     bootcamper. The number of columns nobody decided about is the thing that matters, and it does
     not get less important because the record is wide.
   - **Why `payload`-worthy columns are NOT excluded from the count.** They cannot be: from the
     record alone, a column the publisher deliberately kept as payload and a column nobody
     dispositioned look identical — both are a non-catalog key at the root, and even
     `getRecordPreview` only reports which features Senzing read, never what the publisher intended.
     So they are not counted as *unmapped*; they are counted as **undecided**, and they are routed
     to the step that decides them. `payload` is one of the five dispositions
     `mapping_workflow` step 3 assigns (`feature`, `payload`, `ignore`, `derived`, `extract` —
     confirmed against the live tool schema, MCP server 1.32.8, 2026-08-11), so a payload-heavy
     source loses nothing by going through mapping: mapping is where "this is payload" is actually
     recorded, rather than assumed by a gate that cannot see intent.
   - **Why this does not re-introduce pointless work.** A genuinely fully-mapped source — the
     `truthset` class the fast-path was built for — has zero unrecognized keys and still fast-paths
     with no extra question. Nothing changed for it.

4. **Record the result:** In `config/data_sources.yaml`, set the source's `senzing_loadable` and
   `fully_mapped` fields to `true` or `false`, record `unmapped_fields` as the sorted list of
   unrecognized keys (an empty list when `fully_mapped` is `true`), and update `updated_at`.

   *(These replace the single `senzing_ready` field, which recorded only the structural test while
   the offer was presented on it. On a resumed bootcamp whose registry still carries
   `senzing_ready`, read it as `senzing_loadable` and treat `fully_mapped` as unknown — re-run
   step 3 rather than inferring it, since the old field never measured coverage.)*

5. **If structurally loadable AND fully mapped: present the fast-path offer.** State the coverage
   figure, so skipping is an informed choice rather than a silent default:

   👉 **Your CORD source [SOURCE_NAME] is already in Senzing-loadable form, and all [N] of its fields resolve to the Senzing Entity Specification — there is nothing left to map. Would you like to skip the mapping phase and proceed directly to loading in the Data processing module?**

   *(The wording holds for both supported shapes — the structural check covers a `FEATURES` array
   and the still-supported per-feature sub-lists alike.)*

   *(Internal: end the turn on this question and wait.)*

   - **If confirmed:** Set `mapping_status: complete` and `fast_pathed: true` in the registry.
     Keep `file_path` pointing at the original `data/raw/` file. Record a data-lineage entry
     (see below). Route the source to Module 6.
   - **If declined:** Continue through the normal quality assessment and mapping workflow for
     this source.

6. **If structurally loadable but NOT fully mapped: route to mapping, and name the columns.** Do
   **not** present the fast-path offer — there is something to map, and the whole point of this
   module is doing it. Say so in one statement (no 👉 question; the routing is not a choice):

   > "[SOURCE_NAME] will load as-is, but [N] of its fields aren't Senzing Entity Specification
   > attributes — [list them] — so nothing has been decided about them yet. We'll map this one, and
   > those fields are the exercise: some will become features, some payload, some ignored."

   Name every unrecognized column. A count alone tells the bootcamper a decision exists without
   telling them what it is about. For `PPP_LOANS` those columns are `Business_Type`, `CD`,
   `DateApproved`, `JobsReported`, `Lender`, `Loan_Range`, `NAICS_Code`, `NonProfit`, `OwnedBy`,
   `OwnedByRaceEthnicity`, `OwnedByVeteran` — eleven real decisions the fast-path used to skip.

7. **If NOT structurally loadable or MCP unavailable:** Continue through the normal quality
   assessment and mapping workflow. Do NOT present the fast-path offer.

8. **Non-CORD sources:** Skip this step entirely. Never present the fast-path offer for sources
   with provenance other than `cord`.

9. **After every source has been classified: if ALL of them were fully pre-mapped, say so and
   offer mapping practice.** Never route the bootcamper past this module's core skill in silence —
   they came to learn mapping, and a run where every source fast-pathed teaches none of it. This
   fires only when no selected source reached step 6.

   > "Every source you selected was already fully mapped to the Senzing Entity Specification, so
   > the mapping exercise has nothing to work on. That's a real property of this data, not a
   > shortcut — but it does mean you'd finish the bootcamp without writing a mapping."

   👉 **Would you like to add a raw, unmapped source so you get the mapping practice? Reply with a number:**

   1. Yes — a raw variant of the same data.
   2. Yes — a raw sample from the free-data catalog (`https://github.com/docktermj/senzing-bootcamp-free-data`).
   3. No — continue without a mapping exercise.

   *(Internal: end the turn on this question and wait.)*

   - **Options 1-2:** return to Module 4's data-collection flow to acquire the source, register it
     with `provenance` other than `cord`, then run this module normally on it. Its caveats apply
     — for the free-data catalog, give the ICIJ note in Module 4 before recommending that sample.
   - **Option 3:** continue. Record the choice so graduation can state that no mapping was
     authored, rather than leaving the recap silent about it.

**Fast-path data-lineage entry:** Record a lineage entry ONLY for a source that was explicitly
fast-pathed (the bootcamper confirmed the offer above). Never record one for a source that went
through normal mapping or that was never offered the fast-path. Add the entry to the
`transformations` section of `docs/mapping/data_lineage.yaml`, keyed by the source's
DATA_SOURCE name. Because no transformation occurred, the entry records the original `data/raw/`
file as both input and output with equal record counts:

```yaml
transformations:
  CORD_LAS_VEGAS:
    source_file: data/raw/cord-las-vegas.jsonl
    transformation_script: null  # No transformation: fast-pathed
    output_file: data/raw/cord-las-vegas.jsonl  # Same file
    records_in: 8421
    records_out: 8421
    records_rejected: 0
    quality_score: null  # Quality assessment skipped
    fast_pathed: true
    fast_path_reason: "CORD source structurally loadable and fully mapped: no unrecognized fields"
```

**Invariants:** every fast-path lineage entry MUST satisfy: `source_file == output_file` (the
original `data/raw/` file, unchanged); `records_in == records_out`; `records_rejected: 0`;
`transformation_script: null`; `fast_pathed: true`.

**Non-blocking:** If writing the data-lineage entry fails, allow the fast-path to proceed
anyway: route the source to Module 6 and log the lineage failure so it can be retried later. A
lineage write failure MUST NOT block the fast-path.

**Checkpoint:** write step 5a.

## 6. Assess data quality and apply thresholds

For each data source, compute a quality score based on field completeness, format consistency,
and duplicate rate.

⛔ **Compute it this way — the number routes a gate banded to the percentage point, so two guides
must reach the same figure.** The bands below (≥80 / 70-79 / <70) were precise while the arithmetic
feeding them was never written down, which meant the score was reproducible only by accident:

```text
quality_score = 0.70 × completeness + 0.25 × format_consistency + 0.05 × (100 − duplicate_rate)
```

**Why duplicates barely count.** Completeness and format consistency are things the bootcamper can
act on before mapping — a missing field stays missing, a malformed date stays malformed. A high
duplicate rate is **not a defect to remediate**: resolving duplicate records is what Senzing is for,
and this module runs *before* it has had the chance. Weighting duplicates heavily would send a
bootcamper to "fix" the very condition that makes their data worth resolving. It stays in the score
at 0.05 so a pathological source still registers, and it is **reported in full** regardless of its
weight.

- **completeness (0-100)** — the mean, across records, of the share of **applicable** fields that
  are present in that record, using the presence test defined below and per-`RECORD_TYPE`
  applicability (INV-174).

  **Which fields count — stated positively, because a raw source is this module's central case.** A
  source field enters the denominator when **any** of these is true:

  - **Step 4 identified an Entity Specification counterpart for it.** Step 4 runs immediately before
    this one and does exactly that comparison, so the set is read off its output rather than
    re-derived here. On a raw source this is where the whole denominator comes from.
  - it is already **dispositioned in mapping** (`feature`, `payload`, `extract`); or
  - it is a **structural key** — `DATA_SOURCE`, `RECORD_ID`.

  ⚠️ **Step 5a uses "resolves to" in a narrower sense, and reading that sense here breaks the
  score.** Step 5a asks whether the **key itself** is a catalog attribute, allowing for a leading
  label (`BUSINESS_NAME_ORG` → `NAME_ORG`) — a question about an already-Senzing-ready source. This
  step asks whether a field **has a counterpart** — a question about a raw source, where no key is a
  catalog attribute yet. Same words, two different questions. Read Step 5a's sense here and a fully
  raw source has **zero** countable fields, so the number that gates this module is undefined on the
  module's most common input. Do not change Step 5a: it is correct for what it asks.

  **The exclusion stands, narrowed to what it is for.** A source column with **no** counterpart
  **and** no disposition stays out of the denominator — scoring a source down for work this module
  has not done yet is the false-alarm shape INV-174 records. What must **not** be excluded is a
  column whose counterpart Step 4 has just identified.

  **Worked example — a fully raw source, nothing dispositioned yet:**

  ```text
  full_name     -> NAME_FULL       counterpart identified at Step 4  -> counts
  phone         -> PHONE_NUMBER    counterpart identified at Step 4  -> counts
  created_date  -> (none)          no counterpart, no disposition    -> does NOT count

  denominator = 2 applicable fields per record (plus structural keys) — not 3, and not 0
  ```

  ⛔ **An empty denominator means completeness is UNDEFINED. Never report 0/0 as 0% (INV-238).** A
  source where no column has any counterpart and nothing is dispositioned yields 0/0. Say completeness
  is undefined, give the one-line reason, and route that source to **"Needs enrichment"** (Step 5's
  third category) instead of emitting a score. Reporting 0% instead computes
  `0.25 × format_consistency + 0.05 × (100 − duplicate_rate)`, which lands under 70 and routes the
  gate to "Recommend fixing before mapping" on **arithmetic rather than evidence** — a source with
  nothing to measure is not a source measured as bad, and the bootcamper would be sent to remediate a
  quality problem the number does not demonstrate.

  (On a real source this mattered: `PPP_LOANS` scored 100% on its 8 resolving fields and
  94.4% averaged over all 19 root keys.)

- **format_consistency (0-100)** — the share of populated values that match their field's dominant
  observed pattern (date shape, postal-code shape, casing of a coded value). Report the fields that
  drag it down; a single malformed field is more actionable than the aggregate.
- **duplicate_rate (0-100)** — the share of records whose `(DATA_SOURCE, RECORD_ID)` pair is not
  unique. ⛔ **Compute it on that pair, never on whole-row equality** (INV-180): re-sending the same
  pair *replaces* a record rather than adding one, so identical rows under distinct keys are two
  records and identical keys are one. Row-level duplicate counting measures something Senzing does
  not do.

**Worked example** — 1,000 records; applicable fields present on 96% of them on average; 3% of
populated values off-pattern; 10 records share a `RECORD_ID` with another (1%):

```text
0.70 × 96  +  0.25 × 97  +  0.05 × (100 − 1)   =  67.2 + 24.25 + 4.95  =  96.4  ->  ✅ (≥80)
```

Round to one decimal and state the three inputs alongside the total, so the bootcamper can see
which dimension moved it.

⛔ **Define "present" this way — do not re-invent it.** Completeness feeds the score that gates this
module, so the presence test is part of the measurement, not an implementation detail. A field value
is **present** unless it is:

- absent — the key is missing from the record — or `null`;
- an empty or whitespace-only string;
- an empty container (a list, dict, set or tuple of length 0);
- a container whose every element is itself empty by these rules (e.g. `[""]`, `[{}]`, `[null]`).

Everything else is present. Two consequences to get right:

- **`false`, `0` and `0.0` count as PRESENT.** They are values, not absences. A truthiness test
  (`if value:`) is wrong: it silently reports real data as missing.
- **Presence is a property of the VALUE, never of the key.** Testing "does the record have this
  field?" reports 100% coverage for a field that is an empty array in every record — which is
  exactly how one bootcamp reported `IDENTIFIER_LIST` coverage as **100%** when the true figure was
  **0%**, on the field family that supplies exclusive identifiers, feeding the number straight into
  the mapping decision.

⛔ **Sanity-check any 0% or 100% figure before it routes the gate.** A field family reporting
*exactly* full or *exactly* zero coverage across every record is the signature of a presence test
measuring the wrong thing. Print one sample value for that field and confirm the figure against it
before reporting. Treat a suspiciously uniform result as a probable measurement failure first and a
real finding second — the same discipline INV-115 applies to blank parsed SDK fields, applied here to
profiling.

⛔ **Measure completeness PER RECORD against the features that apply to that record's
`RECORD_TYPE` — never as one average per feature across the whole source.** A feature that does not
apply to a record is not missing data, and averaging it in penalizes the source for data that could
not exist.

This is not a corner case. Mixed person/organization sources are the norm in KYC, AML, sanctions
screening, vendor MDM and beneficial-ownership work — several of this bootcamp's headline use cases.
One sanctions list with **NAME and ADDRESS on 100% of records** scored **52% completeness / 69%
overall** — squarely in "recommend fixing before mapping" below — because person-oriented features
(DOB at 32%, and others like passport and gender) were averaged across a source where **71 of 110
records are ORGANIZATIONS**. Rescoring each record against the features applicable to its own type
gave **97%**. Trusting the first figure would have sent the bootcamper to remediate data with nothing
wrong with it.

**Derive applicability from the Entity Specification, not from a list in this file.** The
specification states the type in its own wording, so `search_docs(query='what features to map',
category='data_mapping')` answers it directly — read the feature's description and section heading:

| What the specification says | Applies to |
|---|---|
| `DOB` — "**Person** date of birth" | PERSON |
| `NATIONALITY` / `CITIZENSHIP` / `PLACE_OF_BIRTH` — "**Person** …" | PERSON |
| `NAME` (person) — "Personal names… `NAME_FIRST`, `NAME_LAST`" | PERSON |
| `REGISTRATION_DATE` / `REGISTRATION_COUNTRY` — section heading "**(organizations)**" | ORGANIZATION |
| `NAME` (organization) — "Organization legal or trade name… `NAME_ORG`" | ORGANIZATION |
| `ADDRESS`, `PHONE`, `EMAIL`, identifiers | either — do not exclude these |

(Verified against MCP server 1.32.2, 2026-07-30. Re-read it for the source you are assessing rather
than trusting this table — it is an illustration of *how the specification marks type*, not a
substitute for asking, and it is deliberately partial: features not listed here still have to be
checked the same way, INV-080.)

**Records with no `RECORD_TYPE`.** The specification calls `RECORD_TYPE` *"Recommended"*, not
required, and says to leave it blank when the type is unknown — so a record may legitimately have
none. Score those against the features that apply to **any** type, and **report how many records were
scored that way**. A source where most records carry no `RECORD_TYPE` is itself a finding worth
raising (it also forgoes the cross-type resolution protection the specification says `RECORD_TYPE`
provides), and it must not be hidden inside an aggregate.

⛔ **Extend the uniformity sanity-check above with this case: a low completeness score on a source
whose NAME and ADDRESS coverage is high is a probable applicability error, not a data problem.**
Check the record-type mix before reporting the score or routing anyone to remediation. The presence
rules above are unchanged — they decide whether a *value* is there; this decides whether the feature
belonged in the denominator at all.

Use these thresholds to guide the decision:

- **≥80% quality score** → Proceed to Phase 2 (mapping). Data quality is strong enough for
  meaningful entity resolution.
- **70-79% quality score** → Warn the user. Quality gaps exist: suggest specific fixes (fill
  nulls, standardize formats, deduplicate within source). Proceed to Phase 2 if the user
  accepts the risk, but document the quality gaps.
- **<70% quality score** → Strongly recommend fixing data quality before mapping. Entity
  resolution results will be poor. Help the user identify the biggest quality issues and create
  a remediation plan. Only proceed if the user explicitly chooses to continue.

**What this score does not measure.** It scores completeness, format consistency, and duplicate
rate — all *structural* properties of one source in isolation. It says nothing about whether a
field will be mapped to a feature that **means** the same thing, and nothing about how two sources
will interact once resolved. A source can score 86% and still carry a mapping that suppresses
legitimate merges. Present the number as "the data is clean enough to map", never as "the mapping
will be correct" — semantic correctness is only established after loading, by the match-key audit
in Data processing.

**If the field list itself looks implausible, this score is not yet meaningful.** The dynamic-key
sanity check (>~100 fields or >50 distinct field patterns — INV-118) runs on the `mapping_workflow`
profile in Phase 2 step 9, *after* this step, so on the first pass you will not have its verdict
here. Two consequences:

- **Now:** if the field list you compared against the Entity Specification in step 4 already looks
  implausibly wide, say so, treat this score as provisional, and expect step 9 to confirm it.
- **On return from Phase 2 step 9:** when that check trips, re-run this step after pre-processing
  and re-profiling rather than keeping the first score — a score averaged over hundreds of phantom
  fields is not meaningful, and it is this score that routes the gate below.

Present the assessment clearly:

```text
Data Quality Assessment:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Source: CUSTOMERS_CRM
  Field completeness:  82%  (name: 99%, phone: 75%, email: 68%)
  Format consistency:  90%
  Duplicate rate:       3%
  Overall quality:     78%  ⚠ Acceptable — some gaps (see below)

Source: VENDORS_LEGACY
  Field completeness:  45%  (name: 90%, phone: 20%, email: 15%)
  Format consistency:  55%
  Duplicate rate:      12%
  Overall quality:     42%  ⚠ Recommend fixing before mapping
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

⛔ **The status label MUST match the band above** — `✅` only at ≥80%, `⚠ Acceptable — some gaps`
at 70-79%, `⚠ Recommend fixing before mapping` below 70%. Derive the label from the computed score
rather than copying one from this example; a `✅` beside a 78% tells the bootcamper the gate said
"proceed" when it is about to ask them to choose.

> **Data source registry:** After computing the quality score, update the source's
> `quality_score` field in `config/data_sources.yaml` and set `updated_at`. If the score is
> below 70, add an `issues` list entry describing the quality concern.

**Checkpoint:** write step 6.

**Visualization checkpoint:** Offer a visual of the quality assessment (coverage bars per
source, per-field completeness). Pin the offer verbatim:

> 👉 **Would you like a visual of the quality assessment (coverage bars and per-field completeness)?**

If the bootcamper accepts, generate a self-contained HTML page and save it to
`docs/visualizations/` (INV-070). (No visualization guide is bundled; offer directly.)

⛔ **This page is a bootcamper-facing visual deliverable, so the four rules below bind it** — it is
saved, kept, and shareable, exactly like the Truth Set app's snapshot. See
`../bootcamp-onboarding/ground-rules.md` → "Visual deliverables (Senzing brand)" for the first two
and `../module-03b-truthset-visualization/visualization-api-reference.md` → "Rendering contract" for
the third; both are the statements of record, so read them rather than reconstructing the rules here.

1. **Brand tokens, not an ad hoc palette** (INV-081): take colors and typography from
   `${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/brand_tokens.py` (skill-relative fallback
   `../bootcamp-onboarding/scripts/brand_tokens.py`, INV-252), degrading gracefully if the module cannot be
   imported.
2. **Renders offline** (INV-081/INV-091): **no CDN, no web font, no remote script.** If you need a
   charting library, inline the vendored `${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/vendor/d3.v7.min.js`
   (skill-relative fallback `../bootcamp-onboarding/scripts/vendor/d3.v7.min.js`, INV-252); plain
   HTML/CSS bars need no library at all and are the better default here. A `<script src="https://…">`
   makes the page render blank on an air-gapped workstation — which Senzing evaluations frequently
   are — with no error anywhere.
3. **Escape every value that came from the data** (INV-106): field names, sample values and source
   names are the bootcamper's own strings. Escape them for the context they land in — HTML text,
   attribute, and, if you embed a JSON payload in an inline `<script>`, `<`, `>` and `&` as their
   `\uXXXX` escapes, since a value containing `</script>` otherwise breaks out of the script block in
   an artifact that gets kept and shared.
4. **Verify the rendered page, not the exit status** (INV-129): open it and confirm the bars and the
   per-field numbers actually drew. Best-effort and non-blocking, like every check in this module.

## 7. Summarize findings and save the evaluation report

Create `docs/data_source_evaluation.md`:

```markdown
# Data Source Evaluation Report

**Date:** [Current date]
**Project:** [Project name]

## Summary
- Total data sources: [count]
- Entity Specification-compliant: [count]
- Needs mapping: [count]
- Needs enrichment: [count]

## Data Source Details

### Data Source 1: [Name]
**Status:** [Entity Specification-compliant / Needs mapping / Needs enrichment]
**Location:** `data/raw/[filename]`
**Records:** ~[count]
**Fields:** [count] columns

**Evaluation:**
- [Field analysis]
- [Entity Specification compliance notes]

**Reason:** [Why it needs mapping or is compliant]

**Next step:** [Phase 2 (mapping) / Data processing (loading)]

### Data Source 2: [Name]
[Same structure]

## Mapping Priority
1. [Data source] - [Reason for priority]
2. [Data source] - [Reason for priority]
```

### Quality gate: iterate vs. proceed

After presenting the quality assessment, guide the user's decision.

**Where the score gates — 70-79% and below 70% — ask exactly one 👉 question to close the turn.**
At **≥80% there is no decision to make**: state the result and continue straight into Phase 2 in the
same turn, letting Phase 2's first step supply that turn's single 👉.

⛔ **Do not invent a gate question for the ≥80% branch.** "Your data is fine, shall we continue?" is
exactly the pointless question INV-012 forbids and INV-006 counts against the ask-once budget, and
improvising one breaches INV-056, which pins every gate question's wording precisely so it cannot
drift at runtime. The ≥80% branch is the common one for curated data — a CORD source routinely
scores there — so this is the path most runs take.

- **Quality ≥80%:** "Your data quality is strong. Let's continue to mapping." **(statement, no 👉;
  continue into Phase 2 this turn)**
- **Quality 70-79%:** "Your data quality is acceptable but has some gaps. You can continue to
  mapping now, or improve the weakest fields first."

  👉 **Your data quality is acceptable but has some gaps. What would you like to do? Reply with a number:**

  1. Improve the weakest fields first.
  2. Continue to mapping now.

- **Quality <70%:** "Your data quality needs attention before mapping will produce good
  results. I'd recommend focusing on [specific issues: e.g., filling missing phone numbers,
  standardizing address formats]."

  👉 **Your data quality needs attention before mapping will produce good results. What would you like to do? Reply with a number:**

  1. Work on improving the data first.
  2. Proceed anyway, knowing the results may be limited.

*(Internal: in the two gating branches, end the turn on the applicable question and wait. In the
≥80% branch no question applies — do not manufacture one; continue into Phase 2 this same turn and
end on its first 👉.)*

**Success indicator:** ✅ All data sources categorized + `docs/data_source_evaluation.md`
created.

**Checkpoint:** write step 7.
