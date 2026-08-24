---
name: module-05-data-quality-mapping
description: 'Bootcamp Module 5: Data Quality, Mapping, and Transformation. Use when the bootcamper starts or resumes Module 5, or needs to assess data quality and map records to the Senzing Entity Specification.'
license: Apache-2.0
compatibility: Requires the Senzing MCP server and Docker.
metadata:
  author: Senzing
  version: 0.5.1
  templateRelease: 0.5.1
  templateSkill: module-05-data-quality-mapping
---

# Module 5: Data Quality, Mapping, and Transformation

> **MCP grounding (mandatory — applies to this entire skill).** Every Senzing fact you present —
> SDK method and attribute names, config options, error codes, and entity-resolution specifics —
> MUST come from the Senzing MCP tools, never from training data, memory, or speculation.
> **Pre-response checklist:** if a reply contains any Senzing specific, you MUST have called an MCP
> tool this turn to obtain it; if not, stop and call it first. This has the same precedence as a ⛔
> gate. The full rule and tool routing are the "MCP-first invariant" in
> `../bootcamp-onboarding/ground-rules.md`.

Follow `../bootcamp-onboarding/ground-rules.md` throughout (👉 one-question-at-a-time,
MCP-first, file placement, checkpointing). Execute every numbered step one at a time, in
order. Never skip, combine, or abbreviate a step containing a 👉 question: this has the same
absolute precedence as a ⛔ mandatory gate, and no internal reasoning can override it.

**First:** Read `config/bootcamp_progress.json`, then (per ground-rules) show the module start
banner, journey map, before/after framing, a brief numbered overview of this module's steps, an estimated time-to-complete (INV-096), and the recommended model/effort nudge (INV-063), before any module work.

**Before/After:** You have raw data files but don't know if Senzing can use them directly.
After this module, each source is scored for quality, categorized, and transformed into
Senzing JSON: validated and ready to load.

**Prerequisites:** ✅ Module 4 complete (data sources collected, files in `data/raw/`).

**Success indicator:** ✅ Each data source evaluated (sources evaluated, mapped) +
transformation programs tested + output validated with quality >70%.

## Reference notes

- **Quality scoring methodology:** When a bootcamper asks how a score was calculated, what
  each dimension measures, or what a threshold means, explain it directly using the dimension
  definitions in Phase 1 (field completeness, format consistency, duplicate rate). The
  standalone `QUALITY_SCORING_METHODOLOGY` guide is a later porting phase; for now use
  `search_docs` for any Senzing-specific quality guidance.
  ⛔ Because the completeness helper is authored fresh each run until that guide is ported, use
  the **presence test defined in Phase 1 step 6** rather than writing one from scratch. Two traps
  it exists to close: never use a truthiness test (`if value:`) — `false` and `0` are present
  values — and never use key presence as coverage, which reports 100% for a field that is an
  empty array in every record. Both are INV-128, which is the statement of record for what counts
  as present and what counts as absent. When the guide is ported, implement presence exactly as Phase 1
  defines it and carry the caution into the ported methodology.
- **Multi-language data:** If a source contains non-Latin characters (Chinese, Arabic,
  Cyrillic, etc.), retrieve current guidance on UTF-8 encoding, non-Latin character support,
  cross-script name matching, and multi-language data quality practices. Never answer from
  training data. ⛔ **Query with the filter and the sections below — a bare
  `search_docs(query="globalization")` does not reach this material** (INV-212). All four
  topics live in **one document**, the "Senzing Globalization Guide". This call reaches it and
  is verified (server 1.32.9, 2026-08-13) — swap the query for the terms in the row you need,
  and keep the filter either way:

  ```text
  search_docs(query='UTF-8 encoding non-Latin character support multi-language data quality', category='globalization')
  ```

  | What you need | Section to ask for |
  |---|---|
  | UTF-8 encoding, and what "supported language" means | "What languages does Senzing support?" |
  | Cross-script name matching | "Advanced personal name comparisons > Supported cultural groups" |
  | Which scripts are actually covered | "Advanced personal name comparisons > Additional Cultural Support" — a transliteration table (Indian, Indonesian, Japanese, Polish, Portuguese, East Slavic, Turkish, Yoruban, Generic). It also states Japanese **Kanji is treated as Chinese Hanzi** — a limitation worth telling the Bootcamper. |
  | Cross-script addresses, and the data-quality practice | "Enhanced address comparisons" and "Address matching examples > CJK+English cross-script matching" — native-to-native beats native-to-Romanized, and for non-CJK cross-script, Romanize via an address-hygiene product and supply **both** the native and Romanized forms. |

  ⛔ **Two phrasings return confidently wrong content, which is worse than returning
  nothing.** Bare `globalization` ranks the Rust SDK's `static GLOBAL_ENVIRONMENT`,
  `postgresql-performance-v4`'s "Global — more workers" (autovacuum tuning) and an MDM-Lite
  FAQ on "globally unique ID" among its top hits, and its best Guide hit is the bare title
  `# Senzing Globalization Guide` with no prose — a stub is not coverage. And the words "best
  practices" are their own trap: unfiltered, `query='multi-language data quality best
  practices'` returned **five of five** results as repo `docs/best-practices.md` template
  files (`senzingsdk-tools`, `scoop-senzingsdk`, `homebrew-senzingsdk`, `senzingapi-tools`,
  `senzingsdk-runtime`) about Markdown lint and Dockerfiles — **no globalization content at
  all**, two of them title-only stubs. With `category='globalization'` the on-topic rows come
  back first, but those same files remain in the set carrying the **highest**
  `relevance_score` (~89–92 against ~12–16), so never rank by score here. Seeing any of this
  is evidence you mis-queried, never that the documentation is thin. (Sections and all three
  traps verified live via `search_docs`, server 1.32.9, docs indexed 2026-08-11 20:52 UTC,
  2026-08-13.)
  <!-- MCP-NEGATIVE: search_docs(query='globalization') — returns no UTF-8 / supported-languages answer in its top hits, and its highest-ranked Guide hit is a title-only stub — owner: search_docs(query='UTF-8 encoding non-Latin character support multi-language data quality', category='globalization') returns it, as the "What languages does Senzing support?" section (routing negative — the material is served; the bare query misses it) — server 1.32.9, 2026-08-13 -->
  <!-- MCP-NEGATIVE: search_docs(query='multi-language data quality best practices') — returns no globalization content at all, all five hits being repo docs/best-practices.md template files about Markdown lint and Dockerfiles — owner: search_docs(query='data quality practices multi-language non-Latin', category='globalization') returns it, as "Address matching examples > CJK+English cross-script matching" (routing negative — the category filter is what recovers it) — server 1.32.9, 2026-08-13 -->

## Error handling

When the bootcamper hits an error during this module:

1. **SENZ error code** (message contains `SENZ` + digits, e.g. `SENZ2027`): call
   `explain_error_code(error_code="<code>", version="current")` and present the explanation and
   recommended fix. If it returns nothing, continue to step 2.
2. Present the matching pitfall/fix for this module (full `common-pitfalls` reference is a
   later porting phase; for now, use `search_docs` to look up the symptom).

Two `mapping_workflow` failure modes have their own handling in
`phase2-data-mapping.md`, both under "Availability-aware mapping validation" — do not improvise
either one:

- a **validation script is unavailable** (HTTP 404) → degrade that check to optional/best-effort
  and proceed;
- **step-3 validation rejects the payload with no actionable reason** (a truncated error naming no
  field) → capture the raw rejection to the source's checkpoint, stop after two attempts, and offer
  the pinned three-option question. Writing the mapper against the Entity Specification is a
  sanctioned outcome there, with all three quality gates still running.

## Phases

- **Phase 1: Quality Assessment** (steps 1–7): `phase1-quality-assessment.md`
  (includes a Senzing-readiness check and fast-path-to-loading offer for eligible sources).
- **Phase 2: Data Mapping** (steps 8–20): `phase2-data-mapping.md`.
- **Phase 3: Test Load and Validate (Optional)** (steps 21–26): `phase3-test-load.md`.

Read `current_step` from `config/bootcamp_progress.json` and resume at the right phase. During
mapping, also read any `config/mapping_state_[datasource].json` checkpoint to resume a
per-source `mapping_workflow` run where it left off.
