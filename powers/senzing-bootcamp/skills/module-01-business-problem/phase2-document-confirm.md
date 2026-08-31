# Module 1, Phase 2: Document and Confirm (steps 9–17)

Continues from Phase 1. Follow the ground rules; `🛑`/`⛔` are internal directives.

## 9. Encourage visual explanations

⛔ **Branch on scenario provenance first — never ask a bootcamper for diagrams of a scenario the
bootcamp invented.** The provenance is the Phase 1 Step 4a outcome: whether the Business Case Offer
was accepted. That is the same decision Step 11's generated-scenario branch acts on; do not
introduce a second mechanism (INV-220). (Step 11 persists it as the `> 🤖 Bootcamp-generated business case`
marker in `docs/business_problem.md`, but that file does not exist yet at this step — on a resumed
session where it does, the marker is the authoritative form of the same signal.)

### 9a. Bootcamper-described case (offer declined, or their own data)

Invite the bootcamper to share any diagrams. Ask this single, pinned 👉 question, verbatim
(INV-056), and end the turn on it:

👉 **Do you have any diagrams of your data architecture and flows you'd like to share?**

It has exactly one meaning each (INV-008): "yes" means they will share diagrams (data
architecture, data flows, or example records); "no" alone means proceed with the scenario as
described. Do NOT fold the "proceed" branch into the question — no "or"-joined choices
(INV-009/INV-051). If they share an image containing placeholders like `[variable]`, ask what
each represents.

### 9b. Generated scenario (Business Case Offer accepted)

Do **not** ask the question — there are no diagrams to share, because the bootcamp authored the
scenario minutes ago. Generate them instead, and announce rather than offer (no yes/no gate):

Write `docs/data_architecture.md` containing two diagrams built from the accepted scenario:

- **Data architecture** — the generated data sources, the Senzing engine, and the datastore.
- **Data flow** — raw → mapped / Senzing-ready → loaded → resolved → queried.

Then say in one line that you created it and what it shows.

**Format: Mermaid fenced blocks in Markdown**, never binary images. That keeps the artifact
diffable, offline (INV-091), viewable without a headless browser, and identical on every platform.

⛔ **Do not embed the Mermaid source into `docs/bootcamp_recap.md`.** `../bootcamp-onboarding/scripts/generate_recap_pdf.py`
renders headings, bullets, `**Label:**` lines, plain text, and `![alt](path)` images — it has **no**
fenced-code handling, so a Mermaid block would reach the PDF as literal backticked text. Reference
the file by path in the recap instead (see below).

Name the real generated sources, but keep the engine and datastore generic — the programming
language and database are not chosen until later modules, so do not assume either here. Never
invent CORD names or record counts; use only what MCP returned in Step 4b.

**Reference it from the problem statement** when Step 11 writes `docs/business_problem.md`, so the
diagrams are discoverable rather than incidental (Step 11's generated-scenario branch carries the
instruction).

**List it in the end-of-module summary** (INV-032) under **Files produced**, as
`docs/data_architecture.md` described as the data architecture and data flow diagrams for the
generated scenario, and in this module's recap section, so the bootcamper knows it exists.

**Checkpoint:** write step 9 (record which branch ran, and the diagram path when 9b applies).

## 10. Identify the scenario

Categorize as Customer 360, Fraud Detection, Data Migration, Compliance, Marketing, etc. If a
pattern was selected, it's already identified. **Checkpoint:** write step 10.

## 10a. Software integration and deployment target

Now that the scenario is identified — and **before** the problem-statement artifacts are written
in Step 11 — capture two forward-looking attributes of the business problem so they flow straight
into the problem statement and the graduation production project (INV-097). Ask each as its own
pinned 👉 question (INV-056), one per turn (INV-251).

⛔ **Hold every answer and write `config/bootcamp_preferences.yaml` ONCE, at this step's
checkpoint.** Do not persist after each question. This step asks two questions — three turns when
the integration answer is "yes" and the follow-up fires — so writing per answer means two or three
diffs to the same file inside one step, which is precisely the one-write-per-gate pattern INV-058
exists to prevent. That invariant names Bootcamp preparation's setup writes specifically, so this is
a scope gap rather than a violation of it; the reasoning transfers unchanged, because it is the same
file, the same bootcamper-visible write noise, and the questions are consecutive turns in a single
numbered step. Hold `integration_targets` and `deployment_target` (plus `cloud_provider` when it
applies), then write them together below.

First, software integration:

👉 **Will your entity-resolution results need to interface with other software (CRM, search engine, data warehouse, API gateway, downstream app)?**

*(Internal: end the turn and wait.)* On **yes**, ask one follow-up on the next turn — "👉 **Which
systems do you expect to integrate with?**" — and **hold** the named systems (e.g. Elasticsearch,
Salesforce) as `integration_targets`. On **no**, hold `integration_targets: []`. Either way, do not
write yet.

Then, deployment target — a separate, pinned 👉 question (neutral lead + numbered list, INV-051).

**Reassure them first**, as a statement before the question: "We'll develop everything locally
first; deployment is addressed in the graduation production project and migration checklist." It
has to come before, per `../bootcamp-onboarding/ground-rules.md` → anything meant to inform the
answer precedes the 👉. Here it earns its place: it is what makes **4. Not sure yet** a comfortable
answer instead of a guess, and a bootcamper who does not yet know their target should not feel
pushed into naming one.

👉 **Where do you plan to deploy the final solution? Reply with a number:**

1. A cloud hyperscaler (AWS/Azure/GCP).
2. A container platform (Kubernetes/Docker Swarm).
3. Local / on-premises.
4. Not sure yet.

*(Internal: end the turn and wait.)*

**Now write both answers together**, in one update to `config/bootcamp_preferences.yaml`:
`integration_targets` (held above) and `deployment_target` (`aws`/`azure`/`gcp` — also
`cloud_provider`; `kubernetes`/`docker_swarm`; `local`/`on_premises`; or `undecided` for option 4).
One write for the whole step, per the batching rule above. **Checkpoint:** write step 10a.

## 11. Create the problem statement document

Save to `docs/business_problem.md` using this template:

```markdown
# Business Problem Statement

**Date**: [Current date]
**Project**: [Project name]
**Design Pattern**: [Pattern name if selected, or "Custom"]

## Problem Description
[One sentence]

## Use Case Category
[Customer 360 / Fraud Detection / Data Migration / Compliance / Marketing / Healthcare /
 Supply Chain / KYC / Insurance / Vendor MDM]

## Design Pattern Reference
[If a pattern was selected: Pattern, Standard Goal, Customizations]

## Data Sources
1. **[Source name]**: Type / ~Records / Entity type / Update frequency / Access
2. **[Source name]**: [same structure]

## Entity Types
[People / Organizations / Both / Other]

## Key Matching Criteria
- **[Attribute]** (High/Medium/Low priority): [why]

## Success Criteria
- [Measurable outcome 1..3]

## Desired Output
**Format**: [Master list / API / Reports / Export]  **Use case**: [One-time / Ongoing /
Real-time]  **Integration**: [Standalone / Integrated with [systems]]

## Integration Requirements
**Downstream systems** / **Integration method** / **Systems mentioned** (from `integration_targets` in `config/bootcamp_preferences.yaml`, captured in Phase 2 Step 10a — INV-097)

## Deployment Target
[If `deployment_target` present in preferences: Platform / Category (Cloud/Container/Local/
Undecided) / Note "development proceeds locally first; infrastructure is a production follow-up
covered by the graduation production project and migration checklist". If "not sure yet":
Platform "To be determined", Category "Undecided". If absent: "Not applicable: deployment target
not captured for this bootcamp."]

## Timeline
**Target completion** / **Key milestones**

## Notes
[Constraints, context]
```

**Generated scenario (Business Case Offer accepted):** produce the SAME artifacts a real case
would, plus:

- Insert the generated marker on its own line directly below the `# Business Problem Statement`
  title, exactly: `> 🤖 Bootcamp-generated business case`.
- Link the diagrams written in Step 9b so they are discoverable from the problem statement:
  `See [data architecture and data flow diagrams](data_architecture.md).` (Relative link — both
  files live in `docs/`.) If Step 9b did not run or the file is missing, omit the line rather than
  writing a dead link. This is a supplementary pointer, not a dependency: the statement still reads
  completely on its own, per the self-containment rule below.
- Record each distinct scenario source into `config/data_sources.yaml` (one entry per source).
- Keep `docs/business_problem.md` self-contained (problem, category, sources, success), not
  dependent on the registry.
- Never embed CORD names/counts from training data: retrieve via MCP (`get_sample_data`,
  `search_docs`) at runtime.

**If writing an artifact fails:** say WHICH artifact failed; do not report Module 1 complete
until the bootcamper is told. **If artifacts are later missing/unreadable:** tell the
bootcamper the generated data is unavailable and let them supply real data.

**Checkpoint:** write step 11.

## 12. Update README.md

Fill the `## Overview` and `## Business Problem` sections **created at project setup**
(`../bootcamp-onboarding/onboarding-flow.md` → "1. Project setup") with what was gathered;
mention the design pattern if one was selected.

**If `README.md` is absent, create it first** with those two headings and then fill them — a
resumed project whose setup predates this step, or one the bootcamper started by hand, will not
have it. Do not stall on the missing file, and do not report the step complete without writing it.

⛔ **Those two sections are the whole of this step.** Add no other sections here: the root
`README.md` is the only `.md` permitted at the project root (INV-017), so it is not a place to
park content that has a home under `docs/`. **Checkpoint:** write step 12.

## 13. Propose the solution approach

Explain how Senzing solves this and which modules are most relevant. If a pattern was selected,
reference how the bootcamp implements it.

- **If the problem involves search/lookup:** clarify the correct layering: Senzing first for
  entity resolution, THEN a search index (Elasticsearch/OpenSearch) over resolved entities.
  This prevents a common architecture mistake. There is no bundled `design-patterns`
  reference; use `search_docs` for specifics.
- **If integration targets were identified** (`integration_targets` in `config/bootcamp_preferences.yaml`, captured in Phase 2 Step 10a — INV-097): reference them and use `search_docs`
  for Senzing's guidance on integrating with those systems.

**Checkpoint:** write step 13.

## 14. Senzing value restatement

Before confirming, reinforce why Senzing ER is valuable for THIS problem. Tie the value to the
bootcamper's specific data, sources, and outcomes (not generic marketing). If integration targets
exist, explain how Senzing fits alongside them as a foundational layer.

**Retrieve the material with `search_docs(query='entity resolution business value')`.** Verified live
on **MCP server 1.32.9, docs index 2026-08-11, checked 2026-08-12**: it returns the *Entity Resolution
Buyer's Guide* ("Five Primary Business Use Cases", and its evaluation steps including Time To Value)
and *Agentic Entity Resolution* ("Why Agentic Entity Resolution Matters", whose Business Impact list
is broken out by use case). Read the bootcamper's use case **out of** those results.

⛔ **Do not append the use-case category to the query.** It is the token that breaks the search, not
a refinement of it. Measured on the same server and date: `value proposition Supply Chain` — the
phrasing this step used to prescribe — returns `senzing/libpostal`'s geodata *store-chains* scripts
and a `sz_spark` changelog's "CI / supply chain" heading, because BM25 matches **"chains"** and the
software sense of "supply chain"; the words "value proposition" contribute nothing. Appending the
category to the working query re-triggers it: `entity resolution business value supply chain` puts
that same libpostal script back at the top, outranking the real material. The category selects
*which part of the results to use*; it does not help retrieve them.

⛔ **If the result is empty or off-topic, re-query before concluding the material is uncovered.** Use
the use case's own business vocabulary — "supplier due diligence", "beneficial ownership",
"watchlist screening" — rather than an abstract phrase. This is the rule
[`../module-00-entity-resolution-concepts/concepts.md`](../module-00-entity-resolution-concepts/concepts.md)
states in full, including why the failure is dangerous: a query that misses looks exactly like
documentation that does not cover the topic, which makes a training-data fallback feel justified. Do
not restate that reasoning here — follow it.

**If nothing relevant comes back after re-querying, say less — do not invent value.** Tie the value
to what MCP *did* return earlier in this module: the data sources you actually found, their record
types and counts, and the mapping findings already in hand. Then say plainly that Senzing's
published material does not cover this use case specifically. Inventing value claims from memory is
forbidden (INV-080), and Senzing does not merchandise every category equally — a short, concrete,
sourced statement is the correct outcome, not a failure of the step.

**Checkpoint:** write step 14.

## 15. Get confirmation

👉 **Does this accurately capture your problem and approach?**

*(Internal: end the turn and wait.)* **Checkpoint:** write step 15.

## 16. Generate the stakeholder summary

Always produce `docs/stakeholder_summary_module1.md` — no gate, no 👉 question. It covers problem,
approach, data sources, key findings, next steps, and ROI considerations, filled with Module 1
context from `docs/business_problem.md`. (No stakeholder-summary template is bundled; compose
the summary directly.) Do not ask whether to create it; announce it
as a statement in the end-of-module summary (Step 17) — noting the file was created and where to
find it — via the module-completion "Files produced" list. **Checkpoint:** write step 16.

## 17. Module completion and transition to Module 2

Run the standard **Module Completion** process in
`../bootcamp-onboarding/module-completion.md` (update progress, append the Module 1 recap
section to `docs/bootcamp_recap.md`, and present the end-of-module summary), then ask the single
transition question.

After the business problem is defined, the next module in your selected sequence continues the
bootcamp:

👉 **Are you ready to move on to the next module: {next module name}?**

**Checkpoint:** write step 17. On module completion set `current_step` to `null`.

**Success indicator:** ✅ Clear problem statement + identified data sources + defined success
metrics + bootcamper confirmation + `docs/business_problem.md` created + Module 1 recap section
appended.
