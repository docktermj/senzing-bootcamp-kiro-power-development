# Module 7, Phase 2a: Discover, Part A (steps 4a–4c)

Follow the ground rules. `🛑`/`⛔` are internal directives, never render them; signal a stop by
ending the turn on the single 👉 question and waiting. On load, read
`config/bootcamp_progress.json` and check which 4x sub-steps are already checkpointed under
`module_7_query.steps`. Resume from the first incomplete step; do not re-run completed
demonstrations.

Load this file when Phase 1 reaches step 4. When steps 4a–4c are complete, load
`phase2b-discover.md` for step 4d.

**No direct SQL and no fabricated methods (see SKILL.md):** every entity operation here
(`get_entity_by_record_id`, `why_records`, `why_entities`, `how_entity`) is generated SDK
code, source flags and signatures from `get_sdk_reference` and code patterns from
`reporting_guide(topic='entity_views', language='<chosen_language>')` / `sdk_guide`. These are SDK methods, not MCP
tools. Never query `database/G2C.db` tables directly.

## Step 4: Discover phase, advanced Senzing capabilities

The Discover phase introduces advanced Senzing capabilities using concrete examples from the
bootcamper's loaded data. It is opt-in, the bootcamper can decline or exit early at any
demonstration point.

### Introduction and opt-in

This opt-in is **independent of the visualization gate** in Phase 1 step 3c — ask it whether or
not the bootcamper chose additional visualizations there.

Present a brief introduction explaining what the Discover phase covers: why analysis
(understanding resolution decisions), how analysis (entity construction history), and
relationship networks (hidden connections). (Data-specific visualization suggestions are no
longer part of the Discover phase — they are offered at the Phase 1 step-3c visualization gate.)
Then ask whether to proceed.

👉 **Would you like to explore Senzing's advanced discover capabilities using examples from your own data?**

*(Internal: end the turn on this question and wait.)*

- **Declines:** write `discover_phase: "skipped"` to `config/bootcamp_progress.json` under
  `module_7_query` and return to `phase1-query-visualize.md` for the Query Completeness Gate.
- **Agrees:** write `discover_phase: "in_progress"` under `module_7_query` and continue to
  step 4a.

⛔ **Declining skips the walkthrough, not the findings.** This question governs whether the
bootcamper is *walked through* why/how/networks interactively. The data-discoveries deliverable
(`docs/bootcamp_data_discoveries.md` + `.pdf`) is produced on **every** path — including this
decline and both early exits below — at the convergence point in `phase1-query-visualize.md` →
"Data-discoveries deliverable". Do not present declining as giving up the findings, and do not
offer the deliverable as a consolation question; it is generated and announced either way. The two
halves have separate authorities: the interactive walkthrough is **offered** (INV-046 — a decline is
a requested skip), while `docs/bootcamp_data_discoveries.md`/`.pdf` is an **always-produced**
deliverable in INV-050's layout tree.

### Step 4a: Data pattern analysis

Analyze the bootcamper's loaded data to identify interesting entities for the Discover
demonstrations. Use the bootcamper's known record IDs (in `config/bootcamp_progress.json` under
the Module 5 loading results, or from the data sources in `config/data_sources.yaml`).

1. **Identify multi-record entities (3+ records):** iterate over the loaded record IDs and, via
   generated SDK code, call `get_entity_by_record_id(data_source, record_id)` for each. Collect
   entities where `record_count >= 3`. These are candidates for the How Analysis demonstration
   (step 4c). Track the entity IDs and record counts.
2. **Identify cross-source entities:** from the multi-record entities in step 1, filter for
   entities whose constituent records originate from two or more distinct data sources. These
   are candidates for the Why Analysis demonstration (step 4b). An entity qualifies if its
   records array contains entries with different `DATA_SOURCE` values.
3. **Identify relationship clusters:** check the entity responses for disclosed relationship
   data. Entities with one or more disclosed relationships are candidates for the Relationship
   Network demonstration (step 4d). Use relationship flags when calling
   `get_entity_by_record_id` so the response includes relationship information (look up the
   flag names via `get_sdk_reference(topic='flags', filter='get_entity_by_record_id')`, and the
   response structure via `get_sdk_reference(topic='response_schemas',
   filter='get_entity_by_record_id')` before parsing it — INV-115).
4. **SDK flag usage:** explain your flag choices as you go. For example: "I'm using
   `get_entity_by_record_id` with relationship flags so we can see which entities connect to
   others. This helps me find good candidates for the relationship network demonstration."
5. **Present a summary:** "I found N large entities (3+ records), M cross-source matches
   (records from multiple data sources), and K relationship clusters in your data." List the
   most interesting candidates by entity ID with a brief reason (e.g. "Entity 1234 has 5
   records from 2 sources" or "Entity 5678 has 3 disclosed relationships").
6. **Graceful fallback for limited data:** if fewer than 2 multi-record entities exist,
   explain: "Your data has limited resolution results, most records resolved as singletons
   (one record per entity). This is common with small or homogeneous datasets." Adapt the
   remaining demonstrations to whatever entities are available. If only single-record entities
   exist, use them to demonstrate the SDK methods while explaining what richer data would show.
   Skip demonstrations that require unavailable patterns (e.g. skip relationship networks if no
   relationships exist) and note which steps are skipped and why.

**Checkpoint:** write step 4a to `config/bootcamp_progress.json` under
`module_7_query.steps.4a`, using this structure:
`{"status": "completed", "patterns_found": {"multi_record": N, "cross_source": M, "relationships": K}}`
where N, M, and K are the actual counts of multi-record entities, cross-source entities, and
relationship clusters found. Also set top-level `current_step` to `"4a"`.

### Step 4b: Why Analysis introduction

Demonstrate Why Analysis using a concrete cross-source entity identified in step 4a. This
teaches the bootcamper how Senzing explains its resolution decisions.

1. **Entity selection:** select a cross-source entity from step 4a, one whose records come
   from two or more distinct data sources. Use the specific record IDs to call `why_records`,
   or the entity IDs to call `why_entities`. Prefer `why_records` for the initial demonstration
   because it compares two specific source records, which is easier to follow. State what you
   are using: "I'll use Entity [ID], which contains records from [Source A] and [Source B] —
   let's see why Senzing decided these belong to the same real-world entity."
2. **SDK method introduction:** before generating the SDK call, briefly explain the two Why
   Analysis methods:
   - `why_records`: compares two specific source records and explains why they resolved
     together. Use when you know exactly which two records to compare.
   - `why_entities`: compares two resolved entities and explains why they are (or are not) the
     same. Use when investigating whether two entities should merge, or auditing a split.
3. **SDK flags and response shape:** generate the `why_records` (or `why_entities`) call,
   confirming flag names via `get_sdk_reference(topic='flags', filter='why_records')` and the
   response structure via `get_sdk_reference(topic='response_schemas', filter='why_records')`
   before writing anything that parses it (INV-115):
   - `SZ_INCLUDE_FEATURE_SCORES`: explain: "I'm using SZ_INCLUDE_FEATURE_SCORES so we can see
     the numeric similarity scores for each feature comparison. This tells us how closely each
     attribute matched between the two records." It is also what the method already defaults to:
     the server documents `SZ_WHY_RECORDS_DEFAULT_FLAGS` as equivalent to this flag alone
     (`get_sdk_reference(topic='flags', filter='why_records')`, server 1.32.9, 2026-08-14).
   - **The why-key breakdown is `WHY_KEY_DETAILS`.** It sits at
     `WHY_RESULTS[].MATCH_INFO.WHY_KEY_DETAILS` — an object whose `CONFIRMATIONS[]` entries each
     name the feature that contributed (`FTYPE_CODE`, `TOKEN`, `SOURCE`) with its `SCORE` and
     `SCORE_BUCKET`. That is the path to parse for step 5
     (`get_sdk_reference(topic='response_schemas', filter='why_records')`, server 1.32.9,
     2026-08-14).
   - ⛔ **Do not reach for `SZ_INCLUDE_MATCH_KEY_DETAILS` here.** The why methods accept it, but
     what it populates is a `MATCH_KEY_DETAILS` object on **each related entity**
     (`response_paths: RELATED_ENTITIES[]`), and it `depends_on` one of the relations flags — so
     it belongs to relationship inspection in step 4d, not to a why demonstration comparing two
     records. A parser written for `MATCH_KEY_DETAILS` in a why response finds nothing and
     renders blank, with no error: exactly the failure "Defensive parsing" in `ground-rules.md`
     exists for. This is INV-179's second cause of a blank field — a correct field name the
     flags in force do not populate — so confirm the flag that populates the field you intend
     to read, not merely that the name is spelled right.
     (`get_sdk_reference(topic='flags', filter='SZ_INCLUDE_MATCH_KEY_DETAILS')`,
     server 1.32.9, 2026-08-14.)
   - ⚠️ **Confirm each flag's type, not only its name.** Where a binding takes a *collection* of
     flags, a composite constant may not belong to that collection's element type, and must then
     be passed as its members instead — `get_sdk_reference` lists those under `composite_members`
     (`SZ_ENTITY_INCLUDE_ALL_RELATIONS` is the four relation flags; server 1.32.9, 2026-08-14).
     Confirm the argument type with `get_sdk_reference(topic='parameters', filter='why_records',
     language='<chosen_language>')` alongside the names (INV-002, INV-132). Observed 2026-08-14
     on Senzing SDK 4.3.4 (Java): `whyRecords` takes `Set<SzFlag>` while the composite is a
     `long` bitmask, which will not compile into that argument.
4. **Plain-language explanation of the output:** after receiving the response, explain it
   covering three aspects:
   - **Features that matched:** list which features (NAME, ADDRESS, DOB, PHONE, etc.) were
     compared and which matched. "The NAME and ADDRESS features both matched between these
     records."
   - **Feature scores:** for each comparison, explain the numeric similarity score. "The name
     comparison scored 95 out of 100, meaning the names are very similar but not identical —
     because one record has 'Robert Smith' and the other has 'Bob Smith'." Explain the range
     (higher = more similar).
   - **Matching principle:** explain which principle applied to each comparison, exact match
     (identical values), close match (very similar, like name variants), or likely match
     (similar enough to contribute). "The name matched on a 'close match' principle because
     'Robert' and 'Bob' are recognized name variants."
5. **Match-key breakdown:** present the why-key string from
   `WHY_RESULTS[].MATCH_INFO.WHY_KEY` (e.g. `+NAME+ADDRESS`) and break it down, using the
   `WHY_KEY_DETAILS` confirmations from step 3 to say which feature produced each component:
   - Each `+FEATURE` component is a feature type that contributed positively to the resolution.
   - Explain each in context: "The `+NAME` means the name features matched strongly enough to
     contribute. The `+ADDRESS` means the address features also matched. Together these two
     matching features were sufficient for Senzing to resolve these records."
   - If the match key contains `-FEATURE` components (negative contributions), explain those
     too: "A `-` prefix means that feature did NOT match, but the other matching features were
     strong enough to override it."
6. **Practical use cases:** explain when Why Analysis is useful in practice:
   - **Auditing decisions:** "When a stakeholder asks 'why did you merge these two customer
     records?', why analysis gives the exact answer with scores and matching principles."
   - **Debugging unexpected merges:** "If two records merged that shouldn't have, why analysis
     shows exactly which features caused it, helping you decide whether to adjust configuration
     or add a data fix."
   - **Compliance reporting:** "For regulated industries (KYC, AML, patient matching), why
     analysis provides the auditable evidence trail showing how each resolution decision was
     made."
7. **Transition:**

   👉 **What would you like to do next? Reply with a number:**

   1. Continue to the next demonstration — How Analysis (seeing how this entity was built step by step).
   2. Proceed to module completion.

   *(Internal: end the turn on this question and wait.)* If the bootcamper chooses to exit,
   write `discover_phase: "skipped"` to `config/bootcamp_progress.json` and return to
   `phase1-query-visualize.md` for the Query Completeness Gate.

**Checkpoint:** write step 4b under `module_7_query.steps.4b`, using
`{"status": "completed", "entity_demonstrated": <entity_id>}` where `<entity_id>` is the numeric
entity ID used in the Why Analysis demonstration. Also set top-level `current_step` to `"4b"`.

### Step 4c: How Analysis introduction

Demonstrate How Analysis using a concrete multi-record entity (3+ records) identified in step
4a. This teaches the bootcamper how Senzing constructs entities over time as records are added.

1. **Entity selection:** select a multi-record entity with 3+ records from step 4a. State which
   entity and why: "I'll use Entity [ID], which has [N] records, enough construction steps to
   see a meaningful history of how Senzing built this entity over time."
2. **SDK flag and response shape:** generate the `how_entity` call with the
   `SZ_INCLUDE_FEATURE_SCORES` flag (confirm via `get_sdk_reference(topic='flags',
   filter='how_entity_by_entity_id')`), and look up the response structure via
   `get_sdk_reference(topic='response_schemas', filter='how_entity_by_entity_id')` before
   parsing it (INV-115). Explain: "I'm using
   SZ_INCLUDE_FEATURE_SCORES so we can see the scoring at each construction step. This shows
   how closely features matched each time a new record was added."
3. **Chronological narrative presentation:** present the How Analysis output as a chronological
   narrative of the entity's construction history:
   - each step where a new record was added,
   - which features caused the merge at that step,
   - the feature scores at each step.

   Use a narrative format: "Step 1: Record A from [Source] was the first record, it
   established the entity. Step 2: Record B from [Source] was added because [features matched
   with scores]. Step 3: Record C from [Source] was added because [features matched with
   scores]." Walk through each step so the bootcamper can follow the entity's growth from a
   single record to its current multi-record state.
4. **Why-vs-How comparison:** explain the difference:
   - **Why Analysis:** compares two specific records or entities and explains the current
     resolution decision, "why are these together right now?"
   - **How Analysis:** shows the full construction history of one entity, the chronological
     sequence of merges as records were added.

   Analogy: "Why is like asking 'why are these two people in the same room?', How is like
   watching the security camera footage of everyone entering the room in order."
5. **Practical use cases:**
   - **Understanding entity growth over time:** "How analysis lets you see the timeline of an
     entity's construction, when each record was added and what triggered each merge."
   - **Investigating over-merging:** "If an entity has too many records merged into it, how
     analysis shows exactly where the chain of merges went wrong, which step introduced the
     problematic record."
   - **Data stewardship:** "When deciding whether to split an entity, how analysis shows the
     merge sequence so you can identify the weakest link in the chain and make an informed split
     decision."
6. **Transition:**

   👉 **What would you like to do next? Reply with a number:**

   1. Continue to the next demonstration — Relationship Networks (exploring how entities connect to each other).
   2. Proceed to module completion.

   *(Internal: end the turn on this question and wait.)* If the bootcamper chooses to exit,
   write `discover_phase: "skipped"` to `config/bootcamp_progress.json` and return to
   `phase1-query-visualize.md` for the Query Completeness Gate.

**Checkpoint:** write step 4c under `module_7_query.steps.4c`, using
`{"status": "completed", "entity_demonstrated": <entity_id>}` where `<entity_id>` is the numeric
entity ID used in the How Analysis demonstration. Also set top-level `current_step` to `"4c"`.

---

**Next:** load `phase2b-discover.md` for step 4d (relationship networks) and Discover Phase
Completion.
