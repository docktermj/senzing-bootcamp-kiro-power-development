# Module 1, Phase 1: Discovery (steps 1–6)

Discovery and gap-filling. Follow the ground rules. `🛑`/`⛔` are internal directives: do not
render them; signal a stop by ending the turn on the single 👉 question and waiting.

## 1. Data privacy reminder (statement, no question — NON-YIELDING)

"Before we proceed, a quick reminder about data privacy. We'll be working with potentially
sensitive data. Please ensure you have permission to use it, and consider anonymizing any PII
for testing. We'll set up proper security measures as we go."

⛔ **This step is non-yielding: it does not get a turn of its own.** Present it in the same turn as
Step 2 and let Step 2's 👉 end that turn — a turn ending here would end with **zero** 👉, which
INV-225 forbids, and presenting it alone is not what "advance exactly one step at a time" asks for
(`../bootcamp-onboarding/ground-rules.md` → the 👉 protocol). This is also the step the post-nudge
sequence lands on: on **no** to the model/effort switch, the reply turn carries this reminder and
ends on Step 2's question.

**Checkpoint:** write step 1 — but as one write with Step 2's at the end of the shared turn, not two
writes inside it.

## 2. Offer the design pattern gallery (separate question)

👉 **Would you like to see examples of common business problems that entity resolution can solve?**

**Checkpoint:** write step 2.

## 3. If they want patterns

Present an entity-resolution design-pattern gallery over the recognized use-case categories, giving
for each: the problem it solves, the goal, typical data sources, business value. Fill those four from
**`search_docs` content returned on the turn the gallery is presented** — never from memory, and
never from an earlier turn's results. This is **presentation freshness**
(`../bootcamp-onboarding/ground-rules.md` → "MCP-first invariant"): the gallery carries an MCP
attribution line, and the attribution is only truthful for what a tool produced this turn. "Already
retrieved a few turns ago" does not satisfy it. (The full pattern gallery is a
later porting phase; that is why this step retrieves rather than reads from a shipped catalogue.)

⛔ **Query by SECTOR vocabulary, not by the category label.** This is the step's real work, and one
generic query is not it: the documentation's own words are industry terms, so "entity resolution use
cases" reaches about four categories and leaves the rest looking uncovered when they are not. Two
routes carry most of the material. Everything from here to the end of this step **is** the retrieval
strategy INV-212 requires — the vocabulary, the documents that hold the material, the queries that
return confidently wrong content, and what to do with a topic the searches do not reach:

- **Business value, for nearly every category** — `search_docs(query='total economic cost mismatched
  identity data by sector …')` returns `economic-cost-mismatched-identity-data.md`, whose
  *"Estimated Annual Cost of Mismatched Identity Records"* table quantifies ten sectors. Its
  appendix breaks several sectors into ER-attributable typologies. **Cite the figures as returned by
  `search_docs`, never from this file** — the numbers live in the document, so a revision changes
  them in one place.

  ⚠️ **Two of the ten rows are "All Sectors" rows, and one of them is the row most bootcamper
  scenarios actually need.** Lead with **`All Sectors: Cross-Industry Data Quality`** whenever the
  scenario has **no clear industry vertical** — generic duplication across internal systems, which is
  the common case — because it is the table's largest domain and was previously unnamed here, so the
  gallery's most reusable figure went unreached. The other is
  **`All Sectors: Marketing, Sales & CRM`**. The remaining eight rows are Government, Financial
  Services, Supply Chain & Procurement, Insurance, Rest of Economy *(indicative)*, Healthcare,
  Retail & E-Commerce, and Telecommunications. (Non-exhaustive as a guide to *which row to read* —
  the table is the authority on its own contents.)

  ⛔ **Sanctions & trade compliance is NOT a row — do not look for one.** It is a sub-line inside
  **Rest of Economy**, described in the document's *"Remaining Sectors"* section alongside state &
  local government and residual sectors, with full derivations in the appendix. Looking for it among
  the rows sends the guide hunting something that does not exist. (Row list, the two "All Sectors"
  rows and the Remaining-Sectors placement all re-verified live: `search_docs` on MCP server
  **1.32.9**, docs indexed 2026-08-11 20:52 UTC, **2026-08-14**. The document's own totals line reads
  "Expanded Estimate (all 10 sectors)", so "ten sectors" is right.)
- **Problem, goal and typical sources** — the Senzing use-cases page (Customer 360, Fraud
  Detection), the USCIS fraud case study, the MDM integration FAQ (Vendor MDM: free resolution vs
  forced separation via a Trusted ID), and the non-person-entity-types FAQ (asset, claim and
  vehicle linking).

⛔ **Two category names are homonym traps that return confidently WRONG content, not nothing** —
which is worse, because a wrong-looking result invites a re-query and a plausible one does not:

- **Supply Chain** — BM25 matches "chains" and the software sense; see the measured example at
  `phase2-document-confirm.md` → Step 14. Query the sector line instead.
- **Data Migration** — returns the **V3→V4 SDK migration** (`sz_dbupgrade`, `sz_configupgrade`,
  the Java/Python migration guides), which has nothing to do with a business use case. This is the
  one recognized category with no business-use-case material; treat it as unreached below rather
  than presenting SDK-upgrade steps as a pattern.

**When a query misses, re-query with the documentation's own vocabulary before concluding the
material is uncovered.** The rule and the reason it matters are stated in full at
[`../module-00-entity-resolution-concepts/concepts.md`](../module-00-entity-resolution-concepts/concepts.md)
→ "Hard rule: facts come from MCP, not memory". Do not restate that reasoning here — follow it.

⛔ **A bare link stub is not content.** The use-cases page returns several categories as nothing but
`[Read More](/risk-fraud-detection)`. A stub is the shape most likely to be mistaken for coverage;
it supplies none of the four attributes.

⛔ **Never fill a category's detail from training data (INV-080).** For any category the searches do
not reach, name it as available and say you can look it up on request — do not invent its problem,
goal, sources or value. The gallery presents the categories the searches actually reached; it does
not promise all ten, and a short sourced gallery plus an honest offer is the correct outcome, not a
failure of this step. Fabricated detail here is especially costly because the attribution line below
then presents it as Senzing-sourced.

Because this content is MCP-sourced, make that visible so the bootcamper can trust it is real,
not fabricated: add a brief inline attribution to the gallery — e.g. a one-line "*Sourced from
Senzing docs via the MCP server.*" note (or a per-item "(via Senzing docs)") — per the
visible-attribution convention in `../bootcamp-onboarding/ground-rules.md`. Keep it lightweight,
honor verbosity (suppress it at the `minimal` preset), and attribute to the MCP server only what
an MCP tool actually produced.

👉 **Do any of these patterns match your situation?**

If they pick one, use it as a template (pre-fill source types, suggest matching criteria,
adapt to their context). If none fit, they can accept the Business Case Offer in Step 4.

**Checkpoint:** write step 3.

## 4. Discovery prompt: three selectable paths

First state a one-line recommendation (a statement, not part of the lead question; honor
verbosity — suppress it at the `minimal` preset), then present the neutral lead question and the
numbered choices, ending the turn on the 👉:

For the most relevant bootcamp, I recommend describing your own business problem if you have one —
you'll work through *your* real data. If you don't, I can generate a realistic scenario instead.

👉 **How would you like to define the business problem? Reply with a number:**

1. **Describe a real business case** — tell me about the problem you're solving: what data you
   have, where it comes from, and what success looks like.
2. **Adopt a design pattern** (if you picked one in Step 3) — how does it apply: what data, from
   where, and what does success look like?
3. **I don't have my own data — generate a scenario for me** — I'll create a realistic,
   multi-source scenario so you can complete the full bootcamp (the Business Case Offer).

*(Internal: end the turn on this 👉 choice and wait. Do NOT generate a scenario before the
bootcamper explicitly accepts option 3.)*

**Checkpoint:** write step 4.

### 4a. Business Case Offer: acceptance handling (branch)

- **Accepted:** generate a complete scenario in-session: a non-empty problem description,
  exactly one use-case category from the recognized set (Customer 360, Fraud Detection, Data
  Migration, Compliance, Marketing, Healthcare, Supply Chain, KYC, Insurance, Vendor MDM), and
  a non-empty definition of success. If a pattern was picked in Step 3, the category must match
  it. Decide CORD vs. synthetic data per Step 4b. **Validate invariants** before recording: at
  least two distinctly named data sources, each with ≥1 record; the data is
  mapping-complexity-rich (needs at least one transformation when mapped to the Senzing Entity
  Specification); the scenario is **quality-varied** — it promises missing and off-pattern values,
  spanning bands rather than being uniformly clean, which is what Data collection then generates and
  what makes the quality gate reachable (INV-239); category is in the recognized set; problem and
  success are non-empty. On
  success, record artifacts in Phase 2 Step 11 (write `docs/business_problem.md` with the
  generated marker, and each source into `config/data_sources.yaml`), then continue at Step 5.
- **Declined:** continue with their own description (Path 1/2); do not generate a scenario.
- **Generation failed / invariants violated:** tell the bootcamper it couldn't complete, fall
  back to their own description, no generated `docs/business_problem.md`.

*(The Kiro helper `business_case_offer.py` encodes these invariants; the script port is a later
phase: validate them directly for now.)*

**Checkpoint:** write step 4a.

### 4b. CORD sourcing for the generated scenario (via MCP)

Treat the Senzing MCP server as the ONLY source of CORD facts: never training data. Call
`get_sample_data` and/or `search_docs(query='CORD datasets: names, contents, and availability
for entity resolution scenarios')` to learn which datasets exist and what they contain. Present
values exactly as returned. Wait up to 30s; retry once.

⛔ **`truthset` is NOT eligible to back a generated scenario, for two independent reasons.**
It is the most inviting choice — smallest, already used elsewhere in the bootcamp, and its
description says it is for quickstarts — so rule it out explicitly rather than leaving it to
judgement:

1. **It is pre-mapped**, so it can never satisfy Step 4a's mapping-complexity invariant. The
   disqualifying word is the server's own: `get_capabilities` describes it as *"the Senzing demo
   truth set: CUSTOMERS, REFERENCE, WATCHLIST — small, **pre-mapped**, used in quickstarts"*
   (server 1.32.9, re-verified 2026-08-14). A scenario built on it passes every other check in
   this step and leaves Data Quality, Mapping, and Transformation with nothing to transform.
2. **Truth Set visualization already runs on it**, so a scenario backed by it collapses two
   modules onto one dataset.

**The eligible collections and what they are shaped like** — take the dataset names, source lists
and counts from `get_sample_data` at runtime, never from here (INV-080); this is a note about
*domain fit*, which the response does not judge for you (all four confirmed present on server
1.32.9, 2026-08-14):

| Dataset | Shaped like | Fit |
|---|---|---|
| `las-vegas` | risk, ownership and licensing data (the widest source set) | eligible |
| `london` | sanctions and corporate-registry data | eligible |
| `moscow` | sanctions and ownership data, non-Roman script | eligible |
| `truthset` | the pre-mapped demo truth set | **ineligible — see above** |

⚠️ **For the customer-facing categories, `synthesized` is the EXPECTED outcome, not a failure.**
The recognized set in Step 4a includes Customer 360, Marketing and Vendor MDM, and all three
eligible collections are risk / sanctions / ownership data — so for those categories no CORD
dataset fits, and synthesizing is the correct answer rather than giving up. Customer 360 is the
most likely pick of all, being the pattern gallery's most relatable entry. Say so to the
bootcamper in those terms; do not present it as a fallback, and do not stretch a sanctions
collection to cover a customer-360 problem in order to reach the `cord` branch.

- **Fitting CORD dataset returned** (one of the three eligible collections, matching the
  category's domain): back the scenario with it, provenance `cord`.
- **None fit** — including every case where the only apparent fit was `truthset`: synthetic data,
  provenance `synthesized`. Data collection generates the files for this provenance without asking
  again (`../module-04-data-collection/SKILL.md` → Step 2), so this branch is complete, not
  deferred.
- **Timeout/unreachable after one retry:** omit CORD facts, tell the bootcamper they're
  unavailable, use synthetic data (`synthesized`).

Either way the data must satisfy the Step 4a invariants.

**Checkpoint:** write step 4b.

## 5. Infer details from their response

Extract six categories: **A. Record types** (people/orgs/both); **B. Source count and names**;
**C. Problem category** (map to the recognized set); **D. Matching criteria** (attributes,
quality concerns); **E. Desired outcome** (format, frequency, integration); **F. Integration
targets** (specific software, pipeline mentions). Use "not yet determined" when unclear.

**Checkpoint:** write step 5.

### 5a. Record-count threshold check (compute-only — no license prompt here)

Compute the total record count across the mentioned sources and read `license_record_limit` from
`config/bootcamp_progress.json` (present only if a custom license was configured in a prior
session; normally absent at this point):

- **Present and > 0:** if the total exceeds it, the bootcamper will likely need a Senzing License
  Key — record `license_guidance_deferred: true` in `config/bootcamp_preferences.yaml`. Otherwise
  leave it unset. Either way, proceed to Step 6.
- **Present and = 0** (no cap): no license concern → proceed to Step 6.
- **Absent/null:** compare the total against the built-in evaluation capacity, confirmed via the
  Senzing MCP server (never a hardcoded figure). If the total exceeds it, record
  `license_guidance_deferred: true`; otherwise leave it unset. Either way, proceed to Step 6.

**The bootcamp does not ask about a Senzing License Key here.** The single, volume-gated License
Key prompt is presented once — at the start of Data collection (Module 4), after the actual data
volume is known and before any load — per INV-093. This step only records whether the anticipated
volume looks likely to exceed the limit, so Module 4's gate can pick it up (`license_guidance_deferred`).

**Checkpoint:** write step 5a to `config/bootcamp_progress.json`.

## 6. Confirm inferred details and fill gaps

Ask about only ONE undetermined item per turn; queue the rest for later turns. Don't re-ask
what they already covered.

### 6a. Present summary and confirm

"Based on what you've described: **Problem:** [...]; **Record types:** [...]; **Data sources:**
[...]; **Key attributes:** [...]; **Desired outcome:** [...]."

👉 **Does that summary capture your situation accurately?**

*(Internal: end the turn and wait.)* **Checkpoint:** write step 6a.

### 6b–6d. Ask only about "not yet determined" items, one per turn

- 6b (record types): 👉 **Which records are you working with? Reply with a number:** (1) people, (2) organizations, (3) both.
- 6c (source count): 👉 **How many distinct data sources will we work with?**
- 6d (desired outcome): 👉 **What does the end result look like? Reply with a number:** (1) a clean master list, (2) an API, (3) reports, (4) something else.

*(Internal: end each turn on its question and wait; checkpoint after each.)* When no
undetermined items remain, Phase 1 is complete — proceed to Phase 2 (load
`phase2-document-confirm.md`).

(The software-integration and deployment-target questions are asked in **Phase 2, Step 10a** — after
the scenario is identified and before the problem statement is written (INV-097) — not here in
Phase 1 and not in Bootcamp preparation. Their answers are persisted to
`config/bootcamp_preferences.yaml` (`integration_targets`, `deployment_target`/`cloud_provider`)
and read from there by the problem statement (Phase 2) and by graduation.)
