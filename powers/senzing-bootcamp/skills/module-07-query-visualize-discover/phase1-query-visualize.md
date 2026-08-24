# Module 7, Phase 1: Query and Visualize (steps 1–3c)

Follow the ground rules. `🛑`/`⛔` are internal directives, never render them; signal a stop by
ending the turn on the single 👉 question and waiting. On load, read
`config/bootcamp_progress.json` and resume from the first incomplete step; do not re-run
completed steps.

**No direct SQL (see SKILL.md):** all entity queries are generated SDK code
(`get_sdk_reference` + `sdk_guide` / `reporting_guide`); counts, stats, quality, and
visualization data come from `reporting_guide`. Never query `database/G2C.db` tables directly.

## 1. Define query requirements

**First action, before any bootcamper interaction in this step:** read
`docs/business_problem.md`.

**IF** `docs/business_problem.md` exists AND contains at least one success criterion or at
least one non-empty desired-output field:

- Derive between 1 and 10 query requirements from the success criteria and desired outputs in
  the document. Each derived requirement must reference the specific success criterion or
  desired output it addresses.
- Present them with this attribution: "Based on your business problem, here are
  the query requirements I've derived:"
- List each requirement with its source (e.g. "From your success criterion about [X]..." or
  "From your desired output format of [Y]...").

👉 **Is there anything you'd like to adjust?**

*(Internal: end the turn on this question and wait.)*

- **Accepts or modifies:** proceed with the confirmed requirements.
- **Rejects all derived requirements:** ask the fresh open-ended question below (the same 👉
  question as the ELSE branch), without referencing the rejected items.

**ELSE** (file missing, OR both success-criteria and desired-outputs sections are missing or
empty): ask the fresh open-ended question:

👉 **What questions do you need to answer with your data?**

*(Internal: end the turn and wait.)*

Common queries (guidance for both paths): find duplicates within a source; find cross-source
matches; search for specific entities; get an entity 360 view; retrieve and format resolved
entities.

**Checkpoint:** write step 1 to `config/bootcamp_progress.json`.

## 2. Create query programs

For each query type, create a program in `src/query/` using the bootcamper's chosen language.

Use `generate_scaffold` with `workflow='query'` and the chosen language. For entity-view
patterns (get/why/how), consult `reporting_guide(topic='entity_views', language='<lang>',
version='current')`. For network/path patterns, consult `reporting_guide(topic='graph',
language='<lang>', version='current')`.

**Flags:** when generated query code calls SDK methods that accept flags (`get_entity`,
`get_entity_by_record_id`, `search_by_attributes`, `how_entity`, `why_entities`, `why_records`,
`why_record_in_entity`, `find_network`, `find_path`), look up available flags via
`get_sdk_reference(topic='flags', filter='<method>')` and select the flags matching the
bootcamper's query intent. Explain the choice in one sentence: "I'm using [flag] so we can see
[what it provides]." For visualization-bound queries, include `SZ_INCLUDE_FEATURE_SCORES`
and/or `SZ_INCLUDE_MATCH_KEY_DETAILS`. ⚠️ **`SZ_INCLUDE_MATCH_KEY_DETAILS` `depends_on` a relations
flag and writes into `RELATED_ENTITIES[]`, so pass it only alongside one** — `SZ_ENTITY_INCLUDE_ALL_RELATIONS`
or one of its four members — and only for the methods that return related entities. Passed on its own
it is accepted and adds nothing, which reads as "no relationships in this data" rather than as a
missing flag (INV-179). It is **not** how a why response explains its match: see step 3a.
(`get_sdk_reference(topic='flags', filter='SZ_INCLUDE_MATCH_KEY_DETAILS')`, server 1.32.9, 2026-08-14.)

⚠️ **The server cautions that DEFAULT composites are not for production code — relay this when you
teach them.** Returned verbatim as the top-level `caution` field of
`get_sdk_reference(topic='flags', filter='find_network_by_entity_id', language='python')`, **MCP
server 1.32.9, 2026-08-12**:

> **PRODUCTION GUIDANCE:** `*_DEFAULT_FLAGS` composites are intended for getting started and
> exploration, not for production code. Their membership may change between Senzing versions, so
> code pinned to a DEFAULT flag can silently change what it returns after an upgrade — no error is
> raised. They also return more than most callers need, and unrequested data costs engine work and
> response size. In production, request exactly the flags whose output you consume (OR the specific
> `SZ_*` flags together) rather than relying on a DEFAULT composite.

**Both halves of that are true here, and the split is the point.** Starting from a DEFAULT composite
is the **right** thing for the bootcamp — the server's own wording calls it the getting-started and
exploration path, and it is how you see a full response before deciding which parts you need. The
code that **leaves with the Bootcamper** is different: graduation copies `src/query/**` into
`production/src/`, so an exploration-shaped flag choice becomes their production artifact verbatim.
Say that plainly when the composite table comes up, and note that the failure mode is **silent** —
after a Senzing upgrade the response changes shape with no error, so nothing in their code will
tell them. `production/MIGRATION_CHECKLIST.md` carries the corresponding action item.

⛔ **Do not rewrite this module's examples to enumerate flags.** The exploration path is endorsed by
the source that issues the caution, and turning a learning example into a production one trades a
readable lesson for noise — the INV-169 mistake of letting a correct approach look broken.

⛔ **A method's own default-flags composite is NOT `SZ_ENTITY_DEFAULT_FLAGS`, and may omit
sub-flags that one carries.** Before parsing an entity field out of a response, read the
composite's `composite_members` and confirm the flag that populates *that* field is in it.
Three confirmed cases, all of which apply when you pass **no** `flags` argument at all, because
these are the signature defaults (`get_sdk_reference(topic='flags', filter=…, language='python')`,
server 1.32.2, verified 2026-07-29; the `why_*` row re-verified 2026-07-31):

| Composite | Carries | Does **not** carry |
|---|---|---|
| `SZ_SEARCH_BY_ATTRIBUTES_ALL` (default for `search_by_attributes`) | `SZ_ENTITY_INCLUDE_RECORD_SUMMARY` | `SZ_ENTITY_INCLUDE_RECORD_DATA` |
| `SZ_FIND_NETWORK_DEFAULT_FLAGS` (default for `find_network_*`) | `SZ_ENTITY_INCLUDE_RECORD_SUMMARY` | `SZ_ENTITY_INCLUDE_RECORD_DATA` |
| `SZ_WHY_ENTITIES_DEFAULT_FLAGS` (`why_entities`) — **one flag, not a set** | `SZ_INCLUDE_FEATURE_SCORES` only | `SZ_ENTITY_INCLUDE_ENTITY_NAME`, and every other entity sub-flag |
| `SZ_ENTITY_DEFAULT_FLAGS` (`get_entity_*`) | **both** | — |

⚠️ **The `why_*` row is the one that costs you a field you did not ask about.**
`SZ_WHY_ENTITIES_DEFAULT_FLAGS` is documented as "the default recommended flags for
`why_entities`. Equivalent to: `SZ_INCLUDE_FEATURE_SCORES`" — a single flag, carrying no
entity-name flag at all, so **`ENTITY_NAME` comes back `null` while every analytical field
renders correctly**: match level, why key, ER rule, feature scores and buckets, CONFIRMATIONS
and DENIALS. That is the deceptive form of the half-populated row (INV-148) — the analysis is
complete and only the human-readable labels are missing, so it reads as unnamed data rather
than as a flags problem. OR the flag in explicitly:
`SZ_WHY_ENTITIES_DEFAULT_FLAGS | SZ_ENTITY_INCLUDE_ENTITY_NAME`
(`SZ_ENTITY_INCLUDE_ENTITY_NAME`'s `applies_to` includes `why_entities`, `why_records` and
`why_record_in_entity` — verified 2026-07-31). ⛔ **`SZ_INCLUDE_MATCH_KEY_DETAILS` was in this
expression and has been removed: it `depends_on` a relations flag and writes into
`RELATED_ENTITIES[]`, so on a why call it adds nothing.** The CONFIRMATIONS and DENIALS named
above are already there without it — they are part of `WHY_RESULTS[].MATCH_INFO.WHY_KEY_DETAILS`
(`get_sdk_reference(topic='response_schemas', filter='why_records')`, server 1.32.9,
2026-08-14). Adding a flag that changes nothing is how a wrong field name survives review. The same holds for
`SZ_WHY_RECORDS_DEFAULT_FLAGS` and `SZ_WHY_RECORD_IN_ENTITY_DEFAULT_FLAGS`, both documented
as equivalent to `SZ_INCLUDE_FEATURE_SCORES` (each **checked individually**, not inferred from
its sibling — INV-169).

⛔ **When `topic='flags'` returns a composite with NO `composite_members`, the check is not
unrunnable — you asked the wrong tool.** For all three `why_*` default composites
`get_sdk_reference(topic='flags', …)` returns only a one-line description, no
`composite_members` and no `response_paths`, with `applies_to` as the literal glob
`["why_entities*"]` and a `source_file` of the V3→V4 breaking-changes document rather than the
flags reference. The membership **is** documented — in the flags documentation, reachable with
`search_docs(query='SZ_WHY_ENTITIES_DEFAULT_FLAGS default recommended flags')`, which returns
the "Equivalent to:" line quoted above (source: `senzing.com/docs/flags/4/flags_why`). So:

1. Ask `topic='flags'` first — it is authoritative and structured.
2. If `composite_members` is absent, ask `search_docs` before concluding anything.
3. Corroborate with the method signature: the same response's `method_signatures` shows the
   binding's default, and for `why_entities` Python reads
   `flags: int = <SzEngineFlags.SZ_INCLUDE_FEATURE_SCORES: 67108864>` — independent
   confirmation that the composite is that one flag.
4. Only if **both** tools come back empty do you OR the needed sub-flags in explicitly and
   record what you could not confirm (INV-080/INV-149).

**"The server does not document X" is only ever "the tool I asked does not document X."**
An empty structured field is not an absent fact.

And the flag→field mapping that makes the consequence exact: `SZ_ENTITY_INCLUDE_RECORD_DATA` →
`RESOLVED_ENTITY.RECORDS[]`; `SZ_ENTITY_INCLUDE_RECORD_SUMMARY` → `RESOLVED_ENTITY.RECORD_SUMMARY[]`.
So a habit learned on `get_entity` ("the defaults give me records") is correct there and **wrong**
for search and network: `RECORDS[]` reads as an empty list, with a correct field name, and nothing
raises. To get it, OR the sub-flag in explicitly —
`SZ_SEARCH_BY_ATTRIBUTES_ALL | SZ_ENTITY_INCLUDE_RECORD_DATA`.

**If all you need is "which sources is this entity in?", you do not need to widen the flags at
all.** `RECORD_SUMMARY[]` carries `DATA_SOURCE` and `RECORD_COUNT` per source and is populated by
both defaults (`get_sdk_reference(topic='response_schemas', filter='search_by_attributes')`, server
1.32.2, verified 2026-07-29). Note the nesting differs per method, so read the schema rather than
assuming: search returns `RESOLVED_ENTITIES[].ENTITY.RESOLVED_ENTITY.RECORD_SUMMARY[]`, while
find_network returns `ENTITIES[].RESOLVED_ENTITY.RECORD_SUMMARY[]`.

⚠️ **The two server sources differ in coverage for `find_network` + `RECORDS[]`, so confirm before
relying on it.** `topic='flags'` lists `find_network_by_entity_id` in
`SZ_ENTITY_INCLUDE_RECORD_DATA`'s `applies_to`, but `find_network`'s own
`topic='response_schemas'` entry enumerates only `RECORD_SUMMARY[]` under
`ENTITIES[].RESOLVED_ENTITY` — it does not list `RECORDS[]` at all (both verified 2026-07-29,
server 1.32.2). That is two different questions answered by two different references, not a
contradiction to resolve from the outside: if you need per-record detail out of a network call,
OR the flag in and **dump one raw response to confirm the field arrived** before writing the
parser (INV-115).

⛔ **Response shapes (INV-115).** Flags are only half the lookup. Before writing any code that
*parses* a response, also call `get_sdk_reference(topic='response_schemas', filter='<method>')`
— **never infer field names from an example snippet.** Wrong field names do not raise: they
render as blank text, so the output looks like "Senzing found nothing" rather than a bug.
`response_schemas` documents **nested** paths, not merely the top-level shape — `MATCH_INFO` is
covered in full, down to `WHY_RESULTS[].MATCH_INFO.FEATURE_SCORES.NAME[].SCORE_BUCKET` (verified
on MCP server 1.32.2, 2026-07-30) — so look a suspect name up there first, then dump one raw
response to confirm what *this* installation returns before writing the parser.

**Defensive parsing.** A blank field has **three** possible causes, not two, and they need
different fixes:

1. **A wrong field name** — the most common, and what INV-115's lookup catches.
2. **A correct field name the flags in force do not populate** — the case the lookup does **not**
   catch, because the name is right. See the default-flags rule above.
3. **Genuinely absent data** — the last thing to conclude, never the first.

**The discriminator between 1 and 2:** if `response_schemas` confirms the path *and* a sibling
field from the same response object reads fine, suspect the **flags** before the data — reading
`RECORD_SUMMARY[]` correctly while `RECORDS[]` comes back empty is that signature exactly. Fix it
by OR-ing in the missing sub-flag, not by switching to a different field and not by re-verifying a
name that is already correct.

Verify against `response_schemas` or a dumped raw response before rendering. Never render a blank
value as though it were a real result — say "no value returned for X" so the failure is visible.

⛔ **This whole class fails silently: valid JSON, no exception, an empty list that looks like an
answer.** A bootcamper seeing no records concludes "the search found nothing useful" or "my data
lacks that field", not "the flags I passed do not populate the field I read". So when a query's
result is *empty rather than wrong*, re-check the three causes above before reporting the finding.

**CRITICAL, file placement:** if the generated scaffold uses `/tmp/`, `ExampleEnvironment`, or
any path outside the working directory, override the database path to `database/G2C.db` and
ensure all output files use project-relative paths. No files outside the working directory.

Example query programs (extension depends on chosen language):

- `find_duplicates`: find entities with multiple records.
- `search_entities`: search by name, email, phone.
- `customer_360`: get the complete customer view.
- `query_results`: retrieve and format resolved entities.

**Iterate over records, not entity IDs.** The caller knows the record IDs and data source codes
they loaded, they do NOT know entity IDs (those are internal to Senzing). Query programs
iterate over loaded records (from the input JSONL file or a record manifest) and use
`get_entity_by_record_id(data_source, record_id)` to look up each record's entity. Never
iterate over a guessed range of entity IDs.

⛔ **One file row is NOT one record: fold on `(data_source, record_id)` before you count.** A
Senzing record's identity is the pair the loader supplied —
`add_record(data_source_code, record_id, record_definition, flags)` — and re-sending the same pair
**replaces** the record rather than adding a second one: *"When a record with a unique key is sent
to Senzing that matches a record already loaded, the new record replaces the current one in Senzing
and doesn't contribute to the DSR count"* (`search_docs`, "Data Source Records (DSRs) Explained";
signature via `get_sdk_reference(topic='parameters', filter='add_record', language='python')`;
server 1.32.2, verified 2026-07-29).

So a mapped file may legitimately hold **more rows than distinct keys** — that is the normal
outcome when Module 5's mapping decision was to keep a source's verified duplicate rows rather
than pre-deduplicate them. Any program that walks a source's rows to associate them with resolved
entities MUST deduplicate by `(data_source, record_id)` **before** counting or grouping. This is a
key-fold, not a language idiom: use whatever set/map your chosen language provides.

**Why it matters, from a real run:** without the fold, `find_duplicates` counted physical rows as
constituent records and reported two entities as holding **23 and 15** records. Inspecting them
with `get_entity_by_entity_id` showed **2 each** — `add_record` had upserted the duplicates all
along. Both were flagged for manual over-matching review that was never warranted: a wasted review
cycle, and in a KYC context a wrong signal about which entities need analyst attention.

**Cross-check before you report.** Senzing's own resolved view is the authority on how many records
an entity has; the file is not. When a per-record count looks surprising, confirm it against
`get_entity_by_entity_id` (or `RECORD_SUMMARY[]`'s `RECORD_COUNT`) before presenting it as a
finding.

**Checkpoint:** write step 2.

## 3. Run exploratory queries

Execute the queries to understand results, using the run command for the chosen language.

**Checkpoint:** write step 3.

### 3a. Present query results and matching concepts

**If entity resolution found zero or very few matches:** this is a valid result, don't assume
something is broken. Tell the bootcamper: "Entity resolution found very few matches. This could
mean: (a) your records are genuinely distinct with no duplicates, (b) the matching criteria
need adjustment, perhaps key fields weren't mapped or data quality is too low, or (c) you're
working with a single source that has no internal duplicates. Let's investigate which one."
Check: are name/address/phone fields populated? Were they mapped correctly during Data Quality,
Mapping, and Transformation? Is the data-quality score above 70%? If the data genuinely has no
duplicates, that's a valid finding, document it.

**Matching-concepts reminder.** When presenting results, briefly remind the bootcamper of the
matching concepts introduced earlier in the bootcamp, a sentence or two each, not a full re-explanation:

- **Features:** the categories of identifying information (NAME, ADDRESS, PHONE, etc.) Senzing
  extracts and compares, and how to read match-key strings like `+NAME+ADDRESS+PHONE`.
- **Confidence scores:** numeric indicators of match strength reflecting how many features
  agreed (higher means more evidence), not absolute probabilities.
- **Cross-source connections:** matches between records from different data sources, revealing
  the same entity exists in multiple systems.

Adapt the reminders to the bootcamper's own data context, reference the feature types, scores,
and data sources present in their current results, not the earlier sample data. Then tell
them: "If you'd like a deeper refresher on how Senzing matching works, features, scoring, or
cross-source connections, just ask and I'll walk through it again."

When presenting results from `how_entity` or the `why_*` methods (`why_entities`,
`why_records`, `why_record_in_entity`), ensure the query was called with
`SZ_INCLUDE_FEATURE_SCORES` — the flag that carries the per-feature scoring detail these
presentations are built from (it applies to all four methods; `get_sdk_reference(topic='flags',
filter='why_records')`, server 1.32.9, 2026-08-14). If the query used default flags, note what
additional detail feature scores would add. ⛔ **For a why response the match-key breakdown is
read from `WHY_RESULTS[].MATCH_INFO.WHY_KEY_DETAILS`, not from a `MATCH_KEY_DETAILS` field and
not by adding `SZ_INCLUDE_MATCH_KEY_DETAILS`** — that flag targets `RELATED_ENTITIES[]` and needs
a relations flag, so on a why call it has nothing to attach to and a parser written for it renders
blank with no error (INV-179; see `phase2-discover.md` step 4b.3, which states this once).

**Checkpoint:** write step 3a.

⛔ **Steps 2–3a ask nothing, so this turn does not end here** — the business answers this step
presents are a results presentation, which reads as an ending and is not one (`ground-rules.md` →
"A results presentation is not a turn ending", INV-225). Continue into 3b/3c in the same turn, up to the
next 👉.

### 3b. Quality evaluation

Call **both** `reporting_guide` topics — they carry different halves and this step needs both
(verified live, **MCP server 1.32.9, 2026-08-12**):

- `reporting_guide(topic='quality', language='<chosen_language>', version='current')` — the
  **methodology**: precision/recall/F1 where a truth set exists, split/merge detection, and the
  review-queue criteria (possible matches, ambiguous matches, large entities, and "review features"
  — an entity carrying two different DOBs or SSNs).
- `reporting_guide(topic='evaluation', language='<chosen_language>', version='current')` — how to
  **interpret** what you found: the 4-Point ER Evaluation Framework (sanity check → over-matching →
  under-matching → match principles), the `MATCH_LEVEL_CODE` reference, and the evidence rule below.

⛔ **Do not reach for `search_docs` here.** This step used to add
`search_docs(query='entity resolution quality evaluation')` "for additional context". Run live on
server 1.32.9 (docs index 2026-08-11), that query returns the *Entity Resolution Buyer's Guide* →
"The Steps To Evaluating Entity Resolution" — a nine-step guide to evaluating an ER **vendor**
(deployment method, cloud vs on-prem, total cost of ownership), not to interpreting your results.
BM25 matched "evaluation" in the procurement sense. `reporting_guide` owns this material; ask it.
If a lookup here returns nothing relevant, re-query with the documentation's own vocabulary before
concluding the material is uncovered — [`concepts.md`](../module-00-entity-resolution-concepts/concepts.md)
states that rule in full; follow it rather than restating it here.

⛔ **Never state a quality verdict without showing the evidence for it.** Verbatim from
`reporting_guide(topic='evaluation', language='python')` (server 1.32.9, 2026-08-12), which calls
this its hallucination-prevention mechanism:

> CRITICAL: Every evaluation finding MUST be supported by specific evidence — actual records, entity
> IDs, and data values. … An LLM can easily generate plausible-sounding evaluation narratives without
> actually examining the data. **Bad:** *"The resolution quality looks good with reasonable
> compression rates."* **Good:** *"Entity 1042 contains 3 records from CUSTOMERS and 1 from VENDORS.
> Records CUST-001 (John Smith, 1985-03-15, 555-1234) and CUST-047 (J. Smith, 1985-03-15, 555-1234)
> correctly resolved via +NAME+DOB+PHONE. Record VEND-203 (Smith Consulting, 555-1234) merged via
> +PHONE only — this is suspicious and may be over-matching."*

**Both topics say the same thing about aggregates**, so the table below is where the review *starts*,
never where it ends. `topic='quality'`: *"Aggregate stats (entity count, compression ratio) hide
errors. Always sample and manually review specific entities — especially large entities, possible
matches, and ambiguous matches. Use `why_entities` to understand individual resolution decisions."*
`topic='evaluation'`: *"Never assess ER quality from aggregate statistics alone."*

Present a quality summary:

| Indicator | Value | Assessment |
|-----------|-------|------------|
| Entity-to-record ratio | [computed] | [interpretation] |
| Possible matches | [count] ([%] of entities) | [interpretation] |
| Cross-source match rate | [%] | [interpretation] |

**Quality assessment:**

- **Acceptable** (proceed): ratio is reasonable, possible matches < 5%, no split/merge signals.
- **Marginal** (review): possible matches 5–15%, or some split/merge signals detected.
- **Poor** (iterate): possible matches > 15%, clear split/merge patterns, or no matching
  occurring.

⛔ **Before stating any of the three verdicts, sample and show.** Pull two or three entities from
the larger size buckets and two or three pairs from the possible-match queue, retrieve them with
`why_entities` / `get_entity`, and show the Bootcamper the actual records: entity ID, how many
records, which sources, and the match key that joined them. This applies to **every** branch,
including the one that proceeds — a verdict with no records behind it is the "Bad" example above,
and **Acceptable** is the branch a Bootcamper is least likely to question.

Based on the assessment — evidence first, wording second:

- **Acceptable:** name what you examined, then proceed. "I looked at entities [IDs]: [n] records
  merged on [match keys], and each is the same [person/organization]. Possible matches are [x]% of
  entities. Quality looks good — let's proceed to visualizations."
- **Marginal:** "I see some potential issues. Here are the specific entities to review." (Show the
  sampled entities and pairs with their match keys, then ask whether to proceed or iterate.)
- **Poor:** "The results suggest mapping improvements would help." (Show the entities or possible-match
  pairs that demonstrate it — naming the match key pattern the near-misses share, since that is what
  points at the unmapped feature — then give recommendations and offer the Module 5 feedback loop.)

**Module 5 feedback loop (when quality is poor or the bootcamper requests iteration):**

Explain first, as a statement: their loaded data and query programs will be preserved; after
remapping, they'll reload the affected sources and re-evaluate here. Then end the turn on this
single question:

👉 **Would you like to return to the Data Quality, Mapping, and Transformation module to refine your data mapping?**

*(Internal: end the turn on this question and wait.)*

If accepted:

1. Note which data sources need remapping in `config/bootcamp_progress.json` under a
   `quality_iteration` key.
2. Set `current_module` to `data_quality_mapping` (Module 5's name token — `current_module` holds
   a name token, never a catalog number, per INV-086) and `current_step` to the Phase 2 start step.
3. Load `../module-05-data-quality-mapping/phase2-data-mapping.md` and begin at its Phase 2
   (step 8, "Start") for the source being refined.

**Checkpoint:** write step 3b.

### 3c. Visualization offer (single gate)

This module's results visualization is delivered as **one** interactive, tabbed app — the same
Truth-Set-style visualization built in the Truth Set module, now pointed at the bootcamper's own
resolved data. It is the single visualization artifact: the entity graph, merge statistics,
match-key frequency, feature scores, cross-source overlap heatmap, and search/probe views are all
**tabs** of this one app, not separate offers or static pages. The relationship-network view is a
**mode** of the Entity Graph tab and no-query merge browsing is a **button** on Search / Probe —
neither is a tab of its own, and there is no Results Dashboard tab (see the full tab set and the
de-duplication rules in
`../module-03b-truthset-visualization/visualization-api-reference.md`, which is the authority on
both).
This is also where Module 6's cross-source relationship view now lives — the Entity Graph tab
(including its "Show only entities with relationships" mode) and the Cross-Source tab replace the
former Module 6 `multi_source_results.html` static page (Module 6 no longer offers a
visualization). Offer it here, after the query results
(3a) and quality evaluation (3b) are in hand. The
Discover-phase opt-in in step 4 is asked **independently** of this decision and covers only the
why/how/network demonstrations — it is not gated on, or bundled with, the visualization choice.

Pin the offer verbatim:

> 👉 **Would you like an interactive visualization of your resolved data — entity graph with its relationship view, merge statistics, cross-source overlap, and match/feature analysis, all in one app?**

*(Internal: end the turn on this question and wait.)*

- **Declines:** skip the visualization and continue to "Next: Discover phase (step 4)". This
  question is itself the visualization offer for the Query Completeness Gate (one offer covers
  the entity graph and the results summary INV-046 asks for; both live inside the single app) —
  checkpoint `m7_visualizations` as `{"offered": true, "accepted": false}` under
  `module_7_query`.
- **Accepts:** build and present the app (below), then checkpoint `m7_visualizations` as
  `{"offered": true, "accepted": true, "artifact": "docs/visualizations/<file>.html"}`.

Build it modeled on the shipped Truth Set visualization server (`../bootcamp-onboarding/scripts/senzing_viz_server.py`)
and the `../module-03b-truthset-visualization/visualization-api-reference.md` contract, in the
bootcamper's chosen programming language (INV-090), pointed at the bootcamper's loaded data instead
of the Truth Set. It MUST:

- Serve/render every applicable tab from that contract — Entity Graph, Merge Statistics, Match
  Keys, Feature Scores, Cross-Source, and Search / Probe. That is the whole set: **six** tabs. Tabs
  whose data is absent are simply not shown (e.g. Cross-Source needs 2+ sources; Match Keys /
  Feature Scores need multi-record entities). Entity Graph carries the relationship subgraph as a
  **mode** (its "Show only entities with relationships" toggle), and Search / Probe carries the
  no-query merge browse as its "Show all merged entities" button. Do **not** produce separate static
  pages, and do **not** add a tab whose content is derivable from another tab's endpoint — the
  entity-size distribution is Merge Statistics, the cross-source entity-relationship view is Entity
  Graph, and there is no separate Results Dashboard, Relationship Network, or Record Merges tab.
- Honor the contract's **"Per-entity actions"** and **"Rendering contract"** sections in full:
  Records / Why? / How? on every entity surface, drill-down from every aggregate, plain-language
  Why?/How? with the raw JSON behind a twistie, and pre-verified search-hint chips.
- ⛔ **Search organizations with `NAME_ORG`, not `NAME_FULL` alone** — in the query program *and* in
  the visualization. Per the Senzing Entity Specification (Name > Feature: NAME — confirm via
  `search_docs`, do not take it from here), `NAME_ORG` is the organization name attribute while
  `NAME_FULL` is for a single-field name whose type is unknown; an organization name sent as
  `NAME_FULL` matches nothing **and raises no error**. Try `NAME_FULL`, then `NAME_ORG` when the
  first returns nothing (or send both and merge by `ENTITY_ID`) — and when the first *errors*, try
  `NAME_ORG` anyway rather than returning the error: a failed attribute is retried past, never
  treated as the end of the list, and an error is reported only once every attribute has been
  tried and none matched (INV-190). This module points at the
  bootcamper's own data, which is frequently half organizations: a search that quietly finds none of
  them reads as a failed load, not as a wrong query. Report an empty result as "nothing matched the
  attributes tried", naming them — never as "not in your data" (INV-115).
- **Mind the scale.** This module points the app at the bootcamper's real data, which is usually far
  larger than the Truth Set it was designed against — the graph label defaults are scale-aware
  (off above ~150 nodes) precisely because a default tuned to 84 entities produced an unreadable
  hairball at ~4,000. Re-check any other visual default at your actual entity count before
  presenting; the bootcamper cannot tell a bad default from bad data.
- Keep all generated code and output inside the working directory (`src/server/` for code, HTML →
  `docs/visualizations/`, other output → `docs/` or `data/`; never `/tmp/`); pull
  entity/relationship/report data through generated SDK code and `reporting_guide`, never direct
  SQL.
- Render offline with the vendored D3 asset inlined, no CDN (INV-091), and take palette/typography
  from `${PLUGIN_ROOT}/../bootcamp-onboarding/scripts/brand_tokens.py` (INV-081; skill-relative fallback
  `../../../bootcamp-onboarding/scripts/brand_tokens.py`, INV-252).
- Write a self-contained standalone HTML snapshot under `docs/visualizations/` (INV-070), passing
  the app **dataset wording that names the Bootcamper's own sources** — e.g. "your CUSTOMERS and
  REFERENCE data", built from `config/data_sources.yaml`. ⛔ Never let it default to neutral wording
  here, and never pass "the Senzing Truth Set": this app points at the Bootcamper's data, the
  snapshot is permanent, and a Truth Set label on their own data is a false claim in a keepsake
  (INV-172). The contract's "Snapshot" section is the statement of record.
  After generating it, capture screenshots for the recap per
  `../bootcamp-onboarding/module-completion.md` → "Capturing visualization screenshots" (skip
  silently with no headless capability, otherwise embed **every** captured tab in this module's
  recap, in the app's tab order — no count cap, INV-146).
  `{name}` = `results_visualization`. Capture **one image per tab** from the running server
  (`--url http://localhost:<port>`, with `--query` so Search / Probe shows real results) — not
  several shots of one tab — and derive every caption from the opened image and its tab label.
- ⛔ **If the visualization changes after the snapshot is written — a bootcamper request, a fix, a
  styling tweak — rebuild the snapshot and re-capture its screenshots.** The snapshot is the retained
  artifact and the one the recap embeds; the server is disposable. A change present only on the
  server leaves the keepsake showing a version the bootcamper asked to have changed, contradicting
  the recap prose that describes the change (see
  `../module-03b-truthset-visualization/phase1-visualization.md` → 2.4b, where the same omission
  shipped an eight-tab snapshot beside six-tab prose).

⛔ **The server stays running — screenshot capture must not stop it.** The API probes and the
screenshot pass above are agent-side verification, not the end of the interaction. Follow the
server-lifetime contract in `../module-03b-truthset-visualization/visualization-api-reference.md` →
"Server lifetime": verify with the server up, then hand it to the bootcamper:

- "Your visualization is running at `http://localhost:<port>`, open it in your browser and take
  your time — I'll leave it up."
- "A saved copy is at `docs/visualizations/results_visualization.html`. Every tab still works
  offline there, except **Why?**, **How?**, and live search — those need the running engine, so use
  them while the server is up."

Let them explore at their own pace, then continue through the Discover phase and the Query
Completeness Gate **with the server still running** — the Discover demonstrations pair naturally
with a live app to look at.

⛔ **Before stopping it, ask the teardown gate**, pinned verbatim (INV-056), and end the turn on it:

> 👉 **Ready for me to stop the visualization server?**

The gate names the server and **only** the server: unlike the Truth Set module, nothing here is
purged — the bootcamper's loaded data stays exactly where it is, and later modules and the recap
depend on it. Say so when asking, and mention that the saved snapshot keeps every tab except the
live `why`/`how`/`search`.

*(Internal: end the turn on this question and wait.)* On "no" or "not yet", leave it running, say so,
and wait for their go-ahead; do not re-ask on a loop. Never leave the bootcamper having to request a
restart for a server they never agreed to stop. If the module ends with the server still up, say
plainly that it is still running and how to stop it, rather than stopping it unasked.

⛔ **Stop it by the pid captured when it was started, never by a command-line pattern.** (INV-223.)
Capture the
handle at launch (`$!` in a POSIX shell, `$proc.Id` from PowerShell's `Start-Process … -PassThru`)
and record it in the `m7_visualizations` checkpoint below, with the port it bound; on teardown,
signal that pid and confirm the port is free before saying the server is stopped. `pkill -f <script name>` matches the invoking shell's own
command line and signals the caller, and this module's server is generated in the bootcamper's
chosen language (INV-090), so there is no script name to match on anyway. When the pid is missing,
find the listener by port (`lsof -ti:<port>`, or `Get-NetTCPConnection -LocalPort <port>`). Full rule:
`../module-03b-truthset-visualization/visualization-api-reference.md` → "Server lifetime" →
"Identifying the server process".

**Checkpoint:** write step 3c to `config/bootcamp_progress.json`, recording `m7_visualizations`
(offered/accepted, the artifact path, and — while the server is up — the port and pid it was started
on, e.g. `{"offered": true, "accepted": true, "artifact":
"docs/visualizations/results_visualization.html", "port": <port>, "pid": <pid>}`). The former per-visualization checkpoints
`m7_exploratory_queries` (entity graph) and `m7_findings_documented` (dashboard) are subsumed here.

## Next: Discover phase (step 4)

The Discover phase introduces advanced Senzing capabilities using concrete examples from the
bootcamper's loaded data. It is opt-in and **independent of the visualization decision above** —
ask it whether or not the bootcamper wanted additional visualizations. The bootcamper can decline
or exit early at any demonstration point.

- Load `phase2-discover.md` for steps 4a–4c (data pattern analysis, why analysis, how
  analysis).
- Then load `phase2b-discover.md` for step 4d (relationship networks) and Discover Phase
  Completion. (The former step 4e data-specific visualization suggestions are now tabs of the
  step-3c visualization app — Match Keys, Feature Scores, Cross-Source, and Entity Graph's
  relationship mode.)

Steps 4a–4d each checkpoint individually to `config/bootcamp_progress.json`. After the Discover
phase completes or is skipped, return here for the Query Completeness Gate.

## Success criteria

- ✅ Query programs created and tested.
- ✅ Visualization offered (the single interactive-visualization gate in step 3c was presented; the
  tabbed app — entity graph with its relationship view, merge statistics, match keys, feature
  scores, cross-source overlap, and search/probe — was built when accepted).
- ✅ Discover phase completed or explicitly skipped.

## Data-discoveries deliverable (produced on every path)

⛔ **Produce `docs/bootcamp_data_discoveries.md` and `.pdf` before the gate below, whether the
bootcamper accepted the Discover opt-in, declined it, or exited part-way.** Every branch of
`phase2-discover.md` returns here, which is why this lives at the convergence point rather than in
each branch.

The opt-in governs **the tutorial** — whether the bootcamper is walked through why/how/networks
interactively. It must not govern **the findings**, which are the payoff for every preceding module:
collection, mapping, loading, resolution. A bootcamper who declines a walkthrough at the end of a
long session should still leave knowing what Senzing found in *their* data. Generate and announce it
in one line (no yes/no gate).

Source every figure through generated SDK code and `reporting_guide` — never direct SQL against
`database/G2C.db`. Write these six sections; the generator checks for them by name:

1. **`## Headline numbers, interpreted`** — records loaded, entities resolved, merge count, and what
   those numbers *mean* here. Never bare counts.
2. **`## Merges and match keys`** — every merge with the match key that drove it, so each is
   explainable and auditable.
3. **`## Review queue`** — cross-source `POSSIBLY_SAME` / `AMBIGUOUS` pairs. This is the section with
   the most business value: each row is one human decision away from being acted on.
4. **`## Why and how: worked examples`** — from the bootcamper's own entities, including at least one
   **near-miss**. Why something did *not* merge teaches more than why something did. Label that
   example exactly `**Near-miss (the one that teaches more):**` — the generator gives this label its
   own line and an indented body, and keys on the label text, so the parenthetical is load-bearing:
   `**Near-miss:**` alone renders inline like any other label (INV-242).
5. **`## Relationship networks`** — multi-hop paths no single record states.
6. **`## What was not found, and why`** — ⛔ the section most likely to be dropped, and the one that
   changes how the whole document reads. State the measurement under the exact label
   `**Measurement:**` (e.g. how many names or identifiers the sources actually share) — the
   generator gives this label its own line and an indented body, and keys on the label text
   (INV-242) — and say explicitly which case applies: **the data had little overlap
   to find**, or **the pipeline underperformed**. Without it, a correct result on a
   low-overlap dataset reads as a weak one. If the match-key audit ran in Data processing, its
   suppressor findings belong here.

⛔ **Write it in Latin-script characters, and build diagrams from ASCII.** The PDF's built-in fonts
cover Latin-1 only, so any character outside it — Cyrillic, Greek, CJK, Arabic — is **dropped from
the page**, and box-drawing connectors (`│`, `▼`, `└`) go with it. So when an entity's primary name
is non-Latin, write the **verified** Latin-script name or alias the loaded data already carries for
it (GLEIF/OFAC/OPEN-SANCTIONS records routinely hold both) and say which you used; and draw ASCII
diagrams with `|` and `v`. ⛔ **Never transliterate or invent a name you have not confirmed in the
data** — a wrong name in a shared report is worse than an awkward one (INV-065's principle: never
fabricate to fill a field). The generator now reports every character it had to drop, naming them
and the first affected passage on stderr, so a slip is visible rather than silent — but it reports
the loss, it cannot undo it: the characters are gone from that PDF.

Then render the PDF with the bundled generator. ⛔ **It ships inside the plugin, not in the
bootcamp project** — resolve it the same way every other bundled script is resolved, and never as a
bare `../bootcamp-onboarding/scripts/…` path, which resolves against the project working directory where no top-level
`../bootcamp-onboarding/scripts/` exists (INV-050 puts the project's own utilities under `src/../bootcamp-onboarding/scripts/`):

```bash
python3 "${PLUGIN_ROOT}/../bootcamp-onboarding/scripts/generate_discoveries_pdf.py"
# or, if CLAUDE_PLUGIN_ROOT is unset: python3 <this-skill-dir>/../../../bootcamp-onboarding/scripts/generate_discoveries_pdf.py
```

That script is the discoveries **sibling** of the recap generator — do not point
`generate_recap_pdf.py` at this document, which parses recap-shaped module sections and would
produce a near-empty PDF. It uses `fpdf2` when importable and a stdlib renderer otherwise, so no
optional PDF dependency is required; and per INV-110 it refuses to write a PDF at all if the
document would lose most of its content, rather than reporting success over an empty deliverable.

⛔ **Verify the PDF carries the findings — a `PDF generated:` line is not verification** (INV-129).
Extract text from the written PDF and confirm real findings appear (fpdf2 compresses its content
streams, so decompress before searching). If extraction shows an empty or near-empty document, say
so and fix the Markdown rather than shipping it.

**Non-blocking.** If either file cannot be produced, report exactly what failed and continue — this
never blocks the gate below or graduation. Say plainly that the deliverable is missing, so its
absence is visible rather than silent.

**Announce both files** in the end-of-module summary's **Files produced** list (INV-032) and in this
module's recap section.

## Query Completeness Gate

Before wrapping up the module, confirm:

1. **Query programs created and tested?** At least one query program runs successfully
   against the resolved data.
2. **Visualization offered?** The step-3c visualization gate was presented (the single
   interactive-visualization question, which is the single offer covering every view in the app)
   — this counts as offered whether the bootcamper accepted or declined it.
3. **Discover phase status?** The Discover phase was either completed (all steps 4a–4d
   checkpointed) or explicitly skipped by the bootcamper.
4. **Data-discoveries deliverable produced?** `docs/bootcamp_data_discoveries.md` and `.pdf` exist
   and the PDF's extracted text carries the findings — or, if they could not be produced, the
   bootcamper was told why. Never silently absent.
5. **Ready to proceed?**

Module 7 is the **last content module before graduation** (required in every path). Once the gate
is satisfied, run the standard **Module Completion** process in
`../bootcamp-onboarding/module-completion.md` (update progress, append the Module 7 recap section
to `docs/bootcamp_recap.md`, and present the end-of-module summary). Because this is the last
content module, the completion process ends with the graduation offer rather than a next-module
transition:

👉 **Would you like to graduate now and generate your production project and recap?**

*(Internal: end the turn on this question and wait; keep this offer's wording identical to
`../bootcamp-onboarding/module-completion.md` → "Reaching graduation".)* On module completion, set
`current_step` to `null` per the ground rules.

- **Affirmative:** invoke the `graduation` skill (GRADUATION banner, recap PDF, and `production/`
  project). See `../graduation/SKILL.md`.
- **Wants to keep exploring first:** stay available for more queries, visualizations, or Discover
  work, and offer graduation again whenever they are ready.
- **Production-hardening:** graduation is the close-out for everyone. Production-hardening
  (performance, security, monitoring, deployment) is delivered through the graduation production
  project and migration checklist, not as separate numbered modules.

## Integration patterns

After running queries, the bootcamper may ask "how do I use these results in my application?"
Present these common integration patterns and help them choose:

| Pattern | Real-time | Complexity | Best for |
|---------|-----------|------------|----------|
| Batch Report | No | Low | Reports, analytics, data warehouse feeds |
| REST API | Yes | Medium | Web apps, microservices, customer lookup |
| Streaming / Event-Driven | Yes | High | Real-time fraud detection, alerts, Kafka integration |
| Database Sync | No | Medium | Data warehouses, BI tools, legacy system integration |
| Duplicate Detection | No | Low | Data quality initiatives, stewardship, cleanup projects |
| Watchlist Screening | Yes | Medium | Compliance (KYC/AML), risk management |

When the bootcamper asks about integration, use `find_examples(query='REST API')` or
`find_examples(query='batch report')` for implementation patterns, and `generate_scaffold` for
code generation. Always iterate over known record IDs (from loaded data) rather than guessing
entity IDs.

**Key implementation principle:** query programs iterate over loaded records using
`get_entity_by_record_id(data_source, record_id)`: never over a guessed range of entity IDs.
The caller knows the record IDs and data source codes they loaded; entity IDs are internal to
Senzing.

Present the integration options and help the bootcamper choose the pattern that fits their use
case: batch reports, a REST API, streaming events, database sync, or duplicate detection.
