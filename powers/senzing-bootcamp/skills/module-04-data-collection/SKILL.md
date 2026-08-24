---
name: module-04-data-collection
description: 'Bootcamp Module 4: Data collection (identifying and collecting data sources). Use when the bootcamper starts or resumes Module 4, or needs to gather source data into data/raw/.'
license: Apache-2.0
compatibility: Requires the Senzing MCP server and Docker.
metadata:
  author: Senzing
  version: 0.5.1
  templateRelease: 0.5.1
  templateSkill: module-04-data-collection
---

# Module 4: Data collection

The Bootcamper-facing name of this module is **Data collection** — the spelling in
`../bootcamp-preparation/SKILL.md`'s module table. Use it in the module-start banner, the
journey map, and every transition question (INV-079); "identifying and collecting data
sources" describes what the module does but is not its name.

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
absolute precedence as a mandatory gate.

⚠️ **On the generated-scenario path this module has exactly one 👉 question** — Step 9's module
transition. Steps 1-8b are all **non-yielding** there, so they run in order inside the turn that ends
on that question: "one at a time" is a rule about order and completeness, not about turns. Three
branches produce the run, and each is correct in its own right:

- **Step 2's marker/provenance guard** skips the provision question entirely and generates the files
  — the Bootcamper already chose this in Discover the Business Problem, so asking again re-litigates
  a settled decision.
- **Step 8a's volume-skip** passes without a question when the collected total is inside the license
  limit, which that step calls the common case.
- **Step 8b** says nothing when the loadable total is below its threshold.

⛔ **This is path-dependent, not fixed — and that is the half most likely to catch you out.** On the
**bring-your-own-data** path, Step 2 *does* ask (the pinned "How would you like to provide the data
for this source?" question), so a guide who learned this module there will meet the run of nine
unexpectedly on a generated scenario. Check the provenance before assuming which shape you are in.

**Checkpoint consequence:** the non-yielding steps' checkpoints collapse into **one** write at the end
of the shared turn, carrying the **last completed step** — not nine writes inside it. If the turn stops
early, write what actually completed, so a resume lands on the right step rather than replaying work
or skipping it.

See `../bootcamp-onboarding/ground-rules.md` → the 👉 protocol, which defines the non-yielding step
and the single-write checkpoint that follows from it; it is stated once, there, and not restated here.

**First:** Read `config/bootcamp_progress.json`, then (per ground-rules) show the module start
banner, journey map, before/after framing, a brief numbered overview of this module's steps, an estimated time-to-complete (INV-096), and the recommended model/effort nudge (INV-063), before any module work. Read `current_step` and
resume at the right step.

> **User reference:** Detailed background for this module lives in the Kiro Power at
> `docs/modules/MODULE_4_DATA_COLLECTION.md` (the docs port is a later porting phase).

**Prerequisites:** ✅ Module 1 complete (business problem defined, data sources identified).
System verification is optional (a deselectable module); when selected it precedes Data
collection, but Data collection does not require it.

**Before/After:** You have a list of data sources on paper. After this module, the actual data
files are in your project (`data/raw/`), documented, and ready for quality evaluation.

**Purpose:** Collect the actual data files from each identified data source and store them in
the project for analysis and mapping.

**Success indicator:** ✅ Sources collected + files in `data/raw/` OR documented locations +
`docs/data_source_locations.md` created + data collection status tracked.

## Error handling

When the bootcamper hits an error during this module:

1. **SENZ error code** (message contains `SENZ` + digits, e.g. `SENZ2027`): call
   `explain_error_code(error_code="<code>", version="current")` and present the explanation and
   recommended fix. If it returns nothing, continue to step 2.
2. Present the matching pitfall/fix for this module (full `common-pitfalls` reference is a
   later porting phase; for now, use `search_docs` to look up the symptom, then check any
   cross-module troubleshooting once ported).

## License limit and dataset size (canonical framing)

By default, the bootcamper already has Senzing's **built-in evaluation license**: the capacity
that applies when no custom license is configured. Treat it as the default the session already
has, presented as a choice rather than a wall. Before any license-based capacity or sampling
decision, **read `license_record_limit` from `config/bootcamp_progress.json`** (Step 8a writes it
after a custom license is configured — but that gate is **volume-gated**, so an absent value means
it has not run, never that no custom license exists) and drive the decision from that effective
limit: never from a remembered or hardcoded figure:

- **Present and greater than 0** (custom license with a finite record cap): the effective limit
  is that value. Recommend sampling for license reasons only when the dataset total genuinely
  exceeds it.
- **Present and equal to 0** (custom license with no record cap): the license imposes no cap: do **not** recommend sampling for license reasons, and support loading the full dataset.
- **Absent or null** — ⛔ **this means "never measured", not "no custom license": measure it before
  deciding anything about capacity.** (INV-244) The field's only writer is Step 8a below, which is
  **volume-gated by design** — it fires only when the collected volume approaches the limit — so on
  a small dataset it never runs and the field is absent no matter which license is installed.
  Treating that silence as "no custom license" is what steers a bootcamper whose license has **no
  cap** toward a smaller dataset, here, in the module where the sampling decision is actually made.
  - **Measure it** by Step 8a's own procedure (sub-step 7 below): generate a scaffold calling
    `SzProduct.get_license()`, save the returned JSON, read it to confirm the shape before parsing
    (INV-115), and parse `recordLimit`. Follow that step rather than restating it.
    (`get_sdk_reference(topic='response_schemas', filter='get_license')`, server 1.32.9,
    2026-08-14, confirms the method in every binding — `SzProduct.getLicense() -> String`,
    `get_license() -> str`.)
  - **Persist it** as `license_record_limit` in `config/bootcamp_progress.json`, so this module's
    later steps, Module 6 and graduation all see a detected value instead of the same absence.
  - **Then re-enter the two branches above** with the measured value. `recordLimit: 0` lands on the
    no-cap branch and no sampling is recommended for license reasons.
  - **Only if the measurement fails** (no engine yet, SDK error) fall back to the **built-in
    evaluation license** the bootcamper already has by default, whose capacity is confirmed via the
    Senzing MCP server at request time (never a hardcoded or remembered figure) — and say plainly
    that it is an assumption, naming what could not be measured, rather than presenting it as the
    detected limit.

Whenever a dataset is: or might be: larger than the effective limit allows, present that as a
choice, not a wall. The bootcamper can keep their full dataset and expand capacity, or work
with a smaller slice, and downsizing is only ever one option among several, never the only path
forward.

- **Keep the full dataset and expand:** the single Senzing License Key gate (Step 8a below)
  handles this — apply an existing license, request one through the external channel, or (when
  available) request one in-flow via the Senzing MCP server (INV-093). The tool-availability
  checks, branching, and setup mechanics all live in Step 8a; do not duplicate that logic here.
- **Work with a smaller slice (optional):** sampling, a CORD subset, or a smaller substitute
  dataset — but **not a random slice** when more than one source is involved. See the sampling
  rule immediately below; it applies to every reduction in this module, whatever prompted it.

<a id="overlap-preserving-sampling"></a>

⛔ **Sampling rule — when 2+ sources are present, random selection destroys the signal entity
resolution exists to find.** This is the canonical statement; every other place that reduces a
dataset (the smaller-slice path later in this step, and the load-time branch in Step 8b) refers
here rather than restating it.

A random sample is the right instinct for **profiling** — it preserves each source's distributions —
and the wrong one for **entity resolution**, which needs the *same real-world entities to appear in
more than one source*. Cross-source overlap is usually a thin slice of two large sets, so random
slices of each share almost nothing. One bootcamp drew a random 300 records from each of five
sources: the load was flawless — 1,147 records, zero errors, redo drained, quality 94–100% — and
produced **zero cross-source matches** outside one pair that happened to be fully included. The
business problem returned no findings from a technically perfect pipeline. The overlap was real:
507 shared names across 21,284 × 63,193 candidates for the largest pair. Random selection simply
missed it.

**Every operational signal a bootcamper checks stays green**, which is what makes this dangerous —
records loaded, no errors, redo drained, quality scored well. It surfaces only in the cross-source
matrix, and only if someone compares it against what the business problem needed.

**So select for overlap, not for representativeness:**

1. Identify candidate join keys the sources share — a name, an identifier, an address — from the
   profiling already done in this module.
2. Select records that **participate in values appearing in 2+ sources** first, keeping each
   matched group whole: taking one side of a pair is as useless as taking neither.
3. Fill the remaining budget with other records so the sample still exercises singletons and
   non-matches.
4. Record the strategy and **why** it was chosen (sub-step below), so later modules can read it.

For a **single-source** dataset none of this applies — there is no cross-source overlap to
preserve, and first-N or random is fine. Say which case applies rather than assuming.

Sampling also stays available for **non-license** reasons: a very large or unwieldy file (for
example, >1GB) or faster iteration: independent of the effective limit. Retrieve any specific
record-capacity or validity figure from the Senzing MCP server at request time, exactly as the
Module 1 flow does. If the MCP server does not return a figure or cannot be reached, omit the
number and say the current value is unavailable from the MCP server: never restate a
remembered or hardcoded figure here.

## Workflow

`🛑`/`⛔` are internal control directives: never render them; signal a stop by ending the turn
on the single 👉 question and waiting.

### 1. Review identified data sources

Recap the data sources identified in Module 1. Review `docs/business_problem.md` for the
complete list.

**Checkpoint:** write step 1 to `config/bootcamp_progress.json`.

### 2. For each data source, collect the data

⛔ **First check whether Module 1 already answered this for this source — and if so, do NOT ask.**

**The signal is the MARKER; the provenance selects the ACTION.** Those are two different questions
and conflating them is what broke this guard. Read `docs/business_problem.md` for the
`🤖 Bootcamp-generated business case` marker: if it is present for this run, the Business Case Offer
generated the scenario (`../module-01-business-problem/phase1-discovery.md` Step 4, option 3: *"I
don't have my own data — generate a scenario for me"*) and the provision decision is **already
made** for every source in it. Then read the source's entry in `config/data_sources.yaml` for its
`provenance`, which decides only *what you do next*:

- **`provenance: cord`** → go straight to downloading that source, saying which source you are
  fetching and where it came from. A generated scenario is the multi-source case, so fetch under
  [CORD fetch integrity](#cord-fetch-integrity) — back-to-back source fetches are exactly what the
  download endpoint throttles, and a throttled response arrives looking like a very small file.
- **`provenance: synthesized`** → **generate the source files.** There is nothing to download: the
  Business Case Offer reaches this provenance precisely when **no CORD collection fits the chosen
  category**, which for the customer-facing categories is the normal outcome rather than the rare
  one. Write one file per source into `data/raw/` from the scenario already recorded in
  `docs/business_problem.md` and `config/data_sources.yaml` — the record counts, entity types and
  per-source quirks are all written there — and record the actual counts back into the registry.
  ⛔ **Ask nothing, recommend no CORD alternative, and do not enter the free-data hierarchy.** That
  hierarchy is for a Bootcamper who has *not* already decided; recommending CORD here recommends the
  option Module 1 evaluated and rejected for this category.
  ⛔ **Generate the mapping complexity the scenario promised** — Module 1 Step 4a's invariant
  required it, so the files must actually carry it: names split into components in one source and
  joined in another, addresses as free text where the scenario says so, per-campaign duplicates, and
  the deliberate inconsistencies across sources. Data Quality, Mapping, and Transformation has to
  have the work this scenario advertised; a clean, uniform generation makes the next module vacuous.

  ⛔ **Generate realistic quality gaps too, not only structural complexity (INV-239).** Everything in
  the list above is about **shape** — how a value is structured across sources. None of it is about
  **quality**, so a faithful generation produces files in which every field is populated and every
  value is uniformly formatted, which scores **100.0** and lands every source in the ≥80% band. That
  makes two of the three gating branches in Data Quality, Mapping, and Transformation unreachable on
  this path, and a Bootcamper who sees `100% ✅` three times reasonably concludes the quality step is
  a formality — in the module whose first phase is *Quality Assessment*. So the generated data must
  also carry:

  - **missing values in non-key fields**, at a rate that puts **at least one source in the 70-79%
    band** — a phone absent on roughly a third of its records, an address missing on a handful. That
    band is the one that opens the remediation conversation, so it has to be reachable.
  - **off-pattern values in at least one field per source** — a date in a second format among
    ISO ones, an unformatted phone among formatted ones, a lowercase state code — so
    `format_consistency` is genuinely below 100 and the "report the fields that drag it down"
    instruction has something to report.
  - **at least one source at ≥80%**, so the Bootcamper sees the **contrast** between a strong source
    and a weak one rather than a uniformly gappy dataset. The comparison is the teaching.
  - the structural complexity above, unchanged — the two are additive, not alternatives.

  **State the intent when you generate, not just the mechanics:** the gaps are there so the quality
  assessment has something to find. A generator that "helpfully" produces clean data defeats the
  module it is feeding.

  ⚠️ **Never put a gap in a record key.** `DATA_SOURCE` and `RECORD_ID` stay present and unique on
  every record: a missing key is a **load failure**, not a quality gap, and `duplicate_rate` is
  computed on that pair (INV-180), so a blank key would corrupt the measurement rather than lower it.
  The per-campaign duplicate pair required above keeps its **distinct** keys, exactly as today — the
  duplication is in the entity, never in the key.

  **Record the intended band per source** in `config/data_sources.yaml`, as `quality_intent` beside
  the source's other fields:

  ```yaml
  - name: MERIDIAN_CRM
    provenance: synthesized
    quality_intent:
      target_band: "70-79"        # one of: ">=80", "70-79", "<70"
      gaps: ["phone missing ~30% of records", "created_date in two formats"]
  ```

  This is what lets the next module state the contrast it is teaching, and it is what lets a later run
  tell a **generation** fault from a **scoring** fault — without it, a source that scores 100 is
  indistinguishable from a source that was meant to.

⚠️ **Both are bootcamp-generated, so both skip the question.** Reading `cord` as the only generated
provenance is what produced a provision question per source on a synthetic scenario — four
repetitions, on this walk, of a decision made in Module 1 — and then routed the answer into an
option that recommends CORD, which cannot resolve.

Asking anyway re-litigates a decision the Bootcamper already made, once per source: with a
six-source generated scenario that is six questions whose honest answer is *"you already told me
this in Module 1."* Option 5 restates that choice rather than asking anything new about *this*
source, so it is not a textually identical question — it escapes a literal INV-006 violation while
being exactly the repetition INV-006 exists to prevent.

Only when the source has **no** recorded provenance — the Bootcamper is bringing their own data —
ask how they want to provide it. Pin this question verbatim (INV-051), never joining the choices
with "or":

👉 **How would you like to provide the data for this source? Reply with a number:**

1. Upload a file.
2. Provide a URL or file path.
3. Connect to a database.
4. Use an API endpoint.
5. I don't have my own data — generate/synthesize it for me.

_(Internal: end the turn on this question and wait.)_

**If the bootcamper chose option 5** — or otherwise doesn't have their own data, or wants free
data to practice with — recommend CORD data as the primary alternative:

> "Senzing provides **CORD (Collections Of Relatable Data)**: curated, real-world-like
> datasets designed specifically for entity resolution evaluation. These are the best option
> for learning with realistic data patterns.
>
> I can pull CORD datasets (Las Vegas, London, Moscow) using the `get_sample_data` tool: these
> are ready-to-use Senzing JSONL files.
>
> Learn more about CORD: <https://senzing.com/senzing-ready-data-collections-cord/>"

Use `get_sample_data(dataset='list')` to show available CORD datasets. Present the fetch URL from
the response exactly as the tool gives it, and say **which** of the two you are presenting — they
are not interchangeable (both fields verified live, `get_sample_data(dataset='las-vegas',
source='GLEIF', limit=1)`, MCP server 1.32.9, 2026-08-12):

- **`download_url`** serves at most `download_url_max_records` records per request — **10,000** —
  and needs only `mcp.senzing.com` reachable.
- **`source_download_url`** is the complete uncapped file, and needs egress to **whatever host that
  URL actually names — read it from the response.** For the CORD collections that is `senzing.com`
  (`las-vegas/GLEIF` → `https://senzing.com/datasets/gleif-lasvegas.jsonl`, verified as above), but it
  is **not** a general rule: the Truth Set's `source_download_url` is on
  **`raw.githubusercontent.com`** (`.../Senzing/truth-sets/main/truthsets/demo/watchlist.jsonl`,
  verified on server 1.32.9, 2026-08-14). The MCP server's own instructions warn that allowing
  `mcp.senzing.com` does not cover GitHub content, so telling a firewalled Bootcamper to allow
  `senzing.com` would strand them on the Truth Set. Name the host from the URL in hand, per dataset.
  ⚠️ **And mind which `download_url` you are holding:** a `source='list'` response returns
  `available_sources[].download_url` pointing at the **origin** host, while a per-source response
  returns `citation.download_url` pointing at **`mcp.senzing.com`**. Same field name, different hosts
  (same server and date).

So `download_url` is **not** "the full file" for any source larger than the cap: of the 11
`las-vegas` sources **6 exceed it**, `EQUIFAX` alone having 72,799 records. Verified live —
`download_url` for `NOMINO-RISK`, whose MCP `record_count` is 14,119, returned exactly 10,000
records (server 1.32.9, 2026-08-12). When the Bootcamper needs a whole source, present
`source_download_url`; when egress is restricted to the MCP host, present `download_url` and say
plainly that it is a 10,000-record slice.

<a id="cord-fetch-integrity"></a>

**⛔ CORD fetch integrity — a throttled download is saved as the source's data.** The download
endpoint rate-limits, and the limit message comes back **as the response body**: 43 bytes of English
prose, `Rate limit exceeded. Try again in 1 second.`, written into the file you were saving. Verified
live on server 1.32.9, 2026-08-12 — fetching four sources of a generated `las-vegas` scenario back to
back, **two of the four** (`OPEN-OWNERSHIP`, `US-LABOR-VIOLATIONS`) came back throttled, each a
single-line file whose one line is prose. Likelihood rises with the number of sources, and
multi-source scenarios are the normal case.

The response **is** machine-readable: it carries HTTP **429** (verified in the same run). But a
downloader invoked the ordinary way will not tell you — `curl -sS -o <file> <url>` exits **0** and
writes the prose body, because no status check was asked for. Left uncaught, `data/raw/` holds a
one-line file that fails in Module 5's mapping or lands as a "1 record" quality assessment, and the
Bootcamper debugs their mapping for a fault created two modules earlier.

Three checks, all required, in this order. **This is the canonical statement; do not restate it
elsewhere.**

1. **Check the HTTP status of every fetch.** Anything outside 2xx is a **failed fetch** — never treat
   the body as data. Use whatever your chosen language offers: an HTTP client raises or exposes a
   status, `curl` must be asked (`--fail`, or `-w '%{http_code}'`), and PowerShell's
   `Invoke-WebRequest` already raises on non-2xx. On **429**, retry with a short backoff — the
   server's own message suggests one second — for a few attempts before reporting failure, and put a
   brief pause between sequential source fetches so the limit is not tripped at all. Verified live:
   the same four-source fetch that lost two sources returned **all four complete** when each request
   retried with a one-second backoff (server 1.32.9, 2026-08-12).

2. **Compare the record count against the count the server already gave you.** The authoritative
   figure is already in hand — `get_sample_data(dataset=…, source='list')` returns `record_count` per
   source. Count the records in the fetched file (a count, in whatever language the Bootcamper chose;
   this is not a shell idiom) and compare against the expected count **for the URL you used**:

   - fetched via **`source_download_url`** → expect exactly `record_count`;
   - fetched via **`download_url`** → expect `min(record_count, download_url_max_records)`, because
     the endpoint caps the response. Comparing a capped fetch against the full `record_count` would
     fail 6 of the 11 `las-vegas` sources for no reason.

   A mismatch is a **failed collection, not a warning**: re-fetch with the backoff from check 1, and
   if it persists, report it to the Bootcamper and leave the source uncollected rather than passing a
   short file downstream. Note that "plausible record count" is a judgement and does **not** catch
   this — one line is arguably plausible for a source whose size you never looked up.

3. **Never write an unverified fetch to `data/raw/` under the source's final name.** Fetch to a
   staging path inside the Bootcamper's project — `data/temp/<source>.jsonl`, the scratch directory
   INV-050 already provides — and move it to `data/raw/<source>.jsonl` only once checks 1 and 2 pass.
   Every path stays project-relative and never uses system temp (INV-200). A throttled response that
   never reaches the source's final name cannot be mistaken for its data by Module 5 or Module 6.

Record **both** counts in the source's `config/data_sources.yaml` entry — `record_count` (what you
counted) and `expected_record_count` (what the server stated) — and both checks under
`validation_checks` (`http_status_ok`, `record_count_matches_expected`), so the comparison stays
auditable instead of living only in the turn that ran it. (INV-243: a per-source figure is
reconciled against that source's own input before it is shown, and this registry entry is where
that reconciliation stays checkable — Module 6 Phase B compares its loaded count against the
`record_count` written here.)

**If the bootcamper declines CORD data** or needs something different, offer secondary options:

> "If CORD doesn't meet your needs, there are other options:
>
> - **Free raw data:** A curated collection of 35+ free data sources at
>   <https://github.com/docktermj/senzing-bootcamp-free-data>: these include raw samples
>   (great for practicing mapping) and pre-mapped files.
> - **Synthesized test data:** I can generate custom test data tailored to your specific
>   scenario."

⛔ **If they choose ICIJ Offshore Leaks from that catalog, tell them what it currently supports
before they map it.** Checked directly against `docktermj/senzing-bootcamp-free-data`,
`samples/raw/icij-offshore-leaks/`, on **2026-08-11** (first observed by a bootcamper 2026-07-27):

1. **The four sample files do not join.** `nodes-officers-sample.csv` covers `node_id`
   12000001-12000010, `nodes-entities-sample.csv` 10000001-10000010 and
   `nodes-addresses-sample.csv` 24000001-24000010, while `relationships-sample.csv` references
   pairs like 10002580 → 14106952. **Not one of its 10 rows has even a single endpoint present** in
   the node files, and every row is `rel_type=registered_address`, so no officer↔entity ownership
   link exists there even in principle. The files were sliced independently — the head of each —
   rather than from a connected subgraph, which in a graph export is almost guaranteed to be
   disjoint.
2. **So the disclosed-relationship exercise is unavailable from that file.** That exercise is the
   `REL_ANCHOR`/`REL_POINTER` family — `REL_ANCHOR_DOMAIN`/`REL_ANCHOR_KEY` on the record being
   pointed at, `REL_POINTER_DOMAIN`/`REL_POINTER_KEY`/`REL_POINTER_ROLE` on the record pointing at
   it (Senzing Entity Specification, *Feature: REL_ANCHOR* and *Feature: REL_POINTER*; confirmed via
   `search_docs(category='data_mapping')` against MCP server 1.32.8, docs index 2026-08-11). Mapping
   `relationships-sample.csv` anyway fails silently: the files parse, the mapping validates, the
   load succeeds, and nothing relates.
3. **The workable alternative on this source is `service_provider`**, populated on all 10 rows of
   `nodes-entities-sample.csv`. Every row carries the same value (`Mossack Fonseca`), so it yields
   one anchor with ten pointers — a real disclosed-relationship exercise, but not a varied
   relationship graph. Say that when you offer it, so the choice is made knowingly.
4. **`nodes-addresses-sample.csv` cannot be loaded as records.** Its `name` column is 0% populated
   (0 of 10): these are address nodes, not entities.
5. **Nothing else about the source is wrong** — the entity and officer files map and load normally.
   Do not call the sample broken; exactly one exercise is unavailable.

⛔ **Never re-slice, repair, or vendor this data into the bootcamp project.** Module 4 recommends the
catalog; it does not own it. A local copy creates a second, divergent dataset and hides the upstream
defect — the same reasoning INV-173 applies to forking an MCP-delivered validator. The fix belongs
in `senzing-bootcamp-free-data`, where the slice would be taken from a connected subgraph instead.
**This is an upstream condition, not a permanent fact: re-check the four files before repeating it,
and retire this note outright — do not amend it — once they join.**

Then proceed with the appropriate option:

**Option A: Bootcamper uploads files**

- Ask for data files (CSV, JSON, Excel, etc.).
- Files can be dragged into the chat or uploaded.
- Save uploaded files to `data/raw/[datasource_name].[extension]`.
- Example: `data/raw/customer_crm.csv`, `data/raw/vendor_api.json`.

**Option B: Bootcamper provides URL/location**

- Ask for the URL or file path where data resides.
- Document the location in `docs/data_source_locations.md`.
- If accessible, download/copy data to `data/raw/`.
- If not accessible (requires credentials, VPN, etc.), document the access method.

**Option C: Database connection**

- Ask for database connection details.
- Document the connection string (without passwords) in `docs/data_source_locations.md`.
- Store sample query results in `data/raw/[datasource_name]_sample.csv`.
- Document the query used to extract data.

**Option D: API endpoint**

- Ask for the API endpoint URL and authentication method.
- Document API details in `docs/data_source_locations.md`.
- Store a sample API response in `data/raw/[datasource_name]_sample.json`.
- Document the API call used.

**Handling different data formats:**

Not all data arrives as CSV. Common formats and how to handle them:

- **Excel (.xlsx):** Convert to CSV first. Most languages have libraries for this (e.g.,
  `openpyxl` for Python, Apache POI for Java). Save the CSV to `data/raw/`.
- **Parquet / Avro:** Use language-appropriate libraries to read and convert to CSV or JSON.
  These formats are common in data lake exports.
- **XML:** Parse and flatten to JSON or CSV. Use `find_examples(query='XML data loading')` for
  patterns.
- **Database exports (SQL dump):** Extract the relevant tables to CSV using the database's
  export tools.
- **API pagination:** If the API returns paginated results, document the pagination strategy
  and write a collection script in `src/../bootcamp-onboarding/scripts/` that fetches all pages and saves to
  `data/raw/`.
- **Real-time streams (Kafka, etc.):** For the bootcamp, capture a snapshot to a file. Document
  the stream details for production use (a production follow-up; see the graduation migration checklist).

For any non-CSV/JSON format, the goal is to get the data into a flat file in `data/raw/` that
Module 5 can evaluate.

> **Data Source Registry:** After collecting each data source file, record it in a registry at
> `config/data_sources.yaml` so later modules can track it. If the file doesn't exist, create
> it with `version: "1"` and an empty `sources:` mapping first. For each source set: `name`,
> `file_path`, `format`, `record_count` (the count you **measured** in the collected file; null only
> when no file was collected, e.g. a documented-location-only source), `expected_record_count` (the
> count the provider stated, so the two can be compared here and re-checked later (INV-243) — for CORD this is
> the MCP `record_count`, capped as [CORD fetch integrity](#cord-fetch-integrity) describes; null
> when no independent figure exists), `file_size_bytes`,
> `quality_score: null`, `mapping_status: pending`, `load_status: not_loaded`,
> `validation_status: pending`, `validation_checks: {}`, and `added_at` and
> `updated_at` to the current ISO 8601 timestamp. If an entry already exists for that
> DATA_SOURCE key, update it and set `updated_at`. _(The Kiro registry helpers are a later
> porting phase; write/update the YAML directly for now.)_
>
> `validation_status` (`pending` | `passed` | `failed`) and `validation_checks` (one key per check
> with its outcome) are written by the Data File Validation step below and read back by Step 7 —
> Step 7 cannot confirm what this entry never recorded, so both fields belong in the schema here.

> **Data File Validation:** After each file is saved to `data/raw/`, sanity-check it (readable,
> non-empty, expected format/encoding, and — wherever an independent expected count exists — a record
> count that **matches** it rather than one that merely looks plausible, per
> [CORD fetch integrity](#cord-fetch-integrity)) and update the registry with the
> results — set that source's `validation_status` to `passed` or `failed` and record each check's
> outcome under `validation_checks`, which is what Step 7 reads. Present the outcome to the bootcamper. If all checks pass, confirm the file is ready
> and move on to the next data source. If any check fails, show the failure details and
> remediation guidance, then help the bootcamper resolve the issue (re-upload, convert format,
> fix encoding, etc.) before proceeding. Re-check after each fix attempt until the file passes.
> _(The Kiro `validate_data_files.py` validator is a later porting phase; perform the checks
> directly for now.)_

> **CORD Metadata Capture:** If the bootcamper chose their own data instead of CORD data, skip
> this. Otherwise, after CORD data has been downloaded via `get_sample_data` and validated,
> capture a metadata snapshot (dataset name, file paths, a content hash or size/mtime) so
> Module 6 can detect if files changed between download and load time. Store it in
> `config/cord_metadata.yaml`. _(The Kiro `cord_metadata.py` helper is a later porting phase;
> record the snapshot directly for now.)_

> **CORD Provenance Recording:** After each data source file is collected and its registry
> entry created/updated in `config/data_sources.yaml`, set the `provenance` field based on the
> data origin:
>
> - `cord`: source obtained via the `get_sample_data` MCP tool
> - `own`: bootcamper's own data (uploaded, URL, database, or API)
> - `free_data`: data from the free-data GitHub repository
> - `synthesized`: generated test data
> - `unknown`: origin cannot be determined
>
> Set `updated_at` to the current ISO 8601 timestamp when writing provenance. A source with
> `provenance: unknown` is never eligible for the fast-path.

**Checkpoint:** write step 2 to `config/bootcamp_progress.json`.

### 3. Verify data was received

```bash
# Linux / macOS
ls -lh data/raw/
head -5 data/raw/customer_crm.csv
head -5 data/raw/vendor_api.json
```

```powershell
# Windows (PowerShell)
Get-ChildItem data\raw\ | Format-Table Name, Length
Get-Content data\raw\customer_crm.csv -TotalCount 5
Get-Content data\raw\vendor_api.json -TotalCount 5
```

**Checkpoint:** write step 3 to `config/bootcamp_progress.json`.

### 4. Document data source locations

**Data Collection Checklist:** Always create a structured checklist in the project — no question
(INV-012). Create `docs/data_collection_checklist.md` with a Data Inventory Table (one row per
data source) and a Validation Checklist, and guide the bootcamper to fill in one row per source
and complete the checklist before Module 5. Announce it as a produced file in the Step 9
end-of-module summary's "Files produced" list (INV-032). _(The Kiro
`templates/data_collection_checklist.md` port is a later porting phase; compose the checklist
directly for now.)_

Also create or update `docs/data_source_locations.md`:

````markdown
# Data Source Locations

## Data Source 1: Customer CRM

- **Type**: CSV file
- **Location**: `data/raw/customer_crm.csv`
- **Original Source**: Uploaded by user from local system
- **Last Updated**: 2025-01-17
- **Record Count**: ~50,000 records
- **Access Method**: One-time upload

## Data Source 2: Vendor API

- **Type**: JSON API
- **Location**: Sample data in `data/raw/vendor_api_sample.json`
- **Original Source**: https://api.vendor.com/v1/suppliers
- **Last Updated**: 2025-01-17
- **Record Count**: ~5,000 records
- **Access Method**: API call with Bearer token authentication
- **API Documentation**: https://api.vendor.com/docs
- **Sample API Call**:

  ```bash
  # Linux / macOS
  curl -H "Authorization: Bearer $API_TOKEN" \
       https://api.vendor.com/v1/suppliers?limit=100
  ```

  ```powershell
  # Windows (PowerShell)
  Invoke-RestMethod -Headers @{Authorization="Bearer $env:API_TOKEN"} `
    -Uri "https://api.vendor.com/v1/suppliers?limit=100"
  ```

## Data Source 3: Legacy Database

- **Type**: PostgreSQL database
- **Location**: Sample data in `data/raw/legacy_db_sample.csv`
- **Original Source**: postgresql://dbserver.company.com:5432/legacy_db
- **Last Updated**: 2025-01-17
- **Record Count**: ~200,000 records
- **Access Method**: Database query (requires VPN)
- **Sample Query**:

  ```sql
  SELECT customer_id, name, address, phone, email
  FROM customers
  WHERE active = true
  LIMIT 1000;
  ```
````

The SQL above documents the bootcamper's own external source system, not the Senzing database.
Never generate SQL against `database/G2C.db`.

**Checkpoint:** write step 4 to `config/bootcamp_progress.json`.

### 5. Handle sensitive data appropriately

- Remind the bootcamper about data privacy (the Kiro `security-privacy` steering reference is a
  later porting phase; use `search_docs` for Senzing's guidance in the meantime).
- If data contains PII, suggest anonymizing for testing.
- Ensure `.gitignore` excludes `data/raw/*` to prevent committing sensitive data.
- Document any data handling requirements in `docs/security_compliance.md`.

**Checkpoint:** write step 5 to `config/bootcamp_progress.json`.

### 6. Create sample files if needed

A smaller working file can be useful in two situations: a very large dataset (e.g., >1GB) that
is unwieldy to handle, or a dataset larger than the effective record limit allows. In **both**
cases sampling is one option, not a requirement.

If the dataset may exceed the effective record limit, apply the canonical framing at the top of
this module: **read `license_record_limit` from `config/bootcamp_progress.json`** and drive the
decision from that effective limit. When it is `0` (no cap) or greater than or equal to the
dataset size, do **not** recommend sampling for license reasons: support loading the full
dataset. When it is absent or null, fall back to the built-in evaluation capacity confirmed via
the Senzing MCP server. When the dataset genuinely exceeds the effective limit, the bootcamper
can keep their full dataset and expand capacity via the single License Key gate at Step 8a, or
work with a smaller slice. Do not steer them to a smaller substitute as the only path. The
License Key setup, its tool-availability checks, and any capacity figure all live in the Step 8a
gate (INV-093) and the Senzing MCP server.

**If the bootcamper chooses to work with a smaller slice:**

- Create smaller sample files (sampling, a CORD subset, or a smaller substitute dataset).
- Save samples to `data/samples/[datasource_name]_sample.[extension]`.
- **Select for cross-source overlap when 2+ sources are present** — see the
  [sampling rule](#overlap-preserving-sampling) earlier in this step. Do not choose a random slice
  by default.
- **Document the sampling method AND why it was chosen** in the data-source registry, not just the
  method name. "Random sample" alone is exactly what leaves Module 6 unable to tell a
  no-overlap-in-the-data finding from a no-overlap-in-the-sample artifact.
- Ensure the sample exercises what the **business problem** needs: for a cross-source problem that
  means shared entities, which is not the same as being statistically representative of each source.
  ⛔ A sample that is representative of every source individually can contain no cross-source matches
  at all — that is the defect the rule above exists to prevent.

**If the bootcamper chooses to keep the full dataset:** continue the collection workflow with
the complete files: there is no requirement to reduce the dataset.

**Checkpoint:** write step 6 to `config/bootcamp_progress.json`.

### 7. Verify data quality at a glance

Each file was already validated in step 2 and the results are stored in the registry. Review
`config/data_sources.yaml` and check the `validation_status` and `validation_checks` fields for
each data source entry. Confirm every source shows `validation_status: passed`. If any source
shows `validation_status: failed`, revisit that data source and resolve the failing checks
before proceeding.

**Checkpoint:** write step 7 to `config/bootcamp_progress.json`.

### 8. Update data source tracking

```markdown
Data Source Collection Status:

- ✅ Customer CRM - Collected (data/raw/customer_crm.csv)
- ✅ Vendor API - Sample collected (data/raw/vendor_api_sample.json)
- ⬜ Legacy Database - Pending (requires VPN access)
```

**Checkpoint:** write step 8 to `config/bootcamp_progress.json`.

### 8a. Senzing License Key gate (single, volume-gated — INV-093)

This is the bootcamp's **single** Senzing License Key prompt. It runs once, here — after all data
sources are collected (so the real volume is known) and before any load (Module 6). SDK setup
(Module 2) established only the built-in evaluation license without prompting; Module 1 recorded
whether the anticipated volume looked likely to exceed it (`license_guidance_deferred`). Decide now
from the actual collected total. Confirm every Senzing/SDK fact via the Senzing MCP server, never
training data.

1. **Read state and compute the total.** Read `license_record_limit` from
   `config/bootcamp_progress.json` and the `license` / `license_guidance_deferred` markers from
   `config/bootcamp_preferences.yaml`. Compute the collected total record count from
   `config/data_sources.yaml` (per the canonical framing at the top of this module). If the total
   cannot be computed, note the warning and proceed to Step 8b (non-blocking).

2. **Already-licensed guard (INV-006).** If a custom license is already configured (`license: custom`
   in `config/bootcamp_preferences.yaml`, or a `license_record_limit` reflecting a custom key),
   acknowledge it and skip to Step 8b — do not ask.

3. **Volume-skip (the common case).** If the collected total is at or below the effective limit — or
   the limit is `0` (unlimited) — the built-in evaluation license suffices. State that briefly and
   skip to Step 8b. **Do not ask for a License Key.**

4. **Only when the collected total exceeds the effective limit,** present the License-Key gate.
   First check the in-flow request option's availability: call `get_capabilities` on the Senzing MCP
   server to see whether `submit_feedback` is reported available (wait up to 30s). Present the
   four-option form when available, otherwise the three-option form; pin whichever you present
   verbatim (INV-056):

   Four-option form (when `submit_feedback` is available):

   👉 **Which best describes your Senzing License Key situation? Reply with a number:**

   1. Yes — a license file (`.lic`).
   2. Yes — a Base64-encoded license key.
   3. No — I'll obtain one another way (a license I get elsewhere, or Senzing support).
   4. No — request a free evaluation license now through the bootcamp.

   Three-option form (when `submit_feedback` is unavailable):

   👉 **Which best describes your Senzing License Key situation? Reply with a number:**

   1. Yes — a license file (`.lic`).
   2. Yes — a Base64-encoded license key.
   3. No — I need to obtain one.

   _(Internal: end the turn on this question and wait. Do not proceed until the bootcamper answers.)_

5. **Apply a Senzing License Key (options 1–2).** 🚨 Never ask the bootcamper to paste a license key
   into chat. Decode/place it to `licenses/g2.lic`:
   - **Base64 string** — Linux/macOS: `echo '<BASE64_STRING>' | base64 --decode > licenses/g2.lic`;
     Windows (PowerShell):
     `[System.Convert]::FromBase64String('<BASE64_STRING>') | Set-Content -Path licenses\g2.lic -AsByteStream`.
     Verify it is binary with `file licenses/g2.lic`.
   - **`.lic` file** — `cp /path/to/g2.lic licenses/g2.lic`.

   Then add `LICENSEFILE` to the engine config PIPELINE section
   (`"PIPELINE": { "LICENSEFILE": "licenses/g2.lic" }`) and record `license: custom` in
   `config/bootcamp_preferences.yaml`. Continue to sub-step 7 to detect the limit.

6. **Obtain a Senzing License Key (option 3, or option 4's in-flow request).** Consult the Senzing
   MCP server first: `search_docs(query='temporary evaluation license for a dataset larger than the
   default limit')` and present the returned guidance. Present the available paths as distinct,
   individually selectable options — the in-flow MCP request (sub-step 6a below), the external
   channel, and apply-an-existing-key (sub-step 5). Source the request channel's address and any
   capacity/validity figures from MCP at runtime rather than this file (they have changed before, and
   the eval and production channels differ), never a remembered figure. The bootcamp **continues on
   the built-in evaluation license** meanwhile, so the bootcamper is never blocked waiting for the
   email; the emailed Base64 key can be decoded and applied via sub-step 5 whenever it arrives, even
   in a later session. Record `license: evaluation` when no custom key is applied.

   ### 6a. The in-flow license request sends the Bootcamper's name and work email — gate it

   ⛔ **This is the only step in the entire bootcamp that transmits the Bootcamper's personal
   details off their machine, and it MUST NOT happen without their explicit yes.** The
   `submit_feedback` tool's `license_request` category **requires three values**: a first name, a
   **work** email address (personal domains are rejected), and **how they heard about Senzing**
   (`how_heard`). Only the last name is optional. It emails back a time- and volume-limited
   evaluation license.

   ⛔ **`how_heard` is required, and the schema does not say so** — it is documented in the
   property's own description, not in a `required` array, because `submit_feedback` has none: every
   property is nullable. A caller who checks only what the schema marks required will omit it. This
   is the INV-192 class (schema-optional, answer-mandatory) on the one call that sends the
   Bootcamper's personal details, so getting the field list wrong means asking them to consent to a
   payload that is not the payload (INV-135). Verified on **MCP server 1.32.9, 2026-08-12**, from
   two places in one session: the `how_heard` property reads *"How the requester heard about
   Senzing (required for license_request)"* against `lastname`'s *"(optional for
   license_request)"*, and `get_capabilities`' manifest lists *"firstname (required), lastname
   (optional), email (work email required …), and how_heard"*.

   ⛔ **Never state the license's duration — the server contradicts itself about it, so no figure
   is citable.** Verified on **MCP server 1.32.9, 2026-08-12**, both in one session:
   `submit_feedback`'s own tool description (via `get_capabilities`) says *"A **10-day**, 250K-record
   eval license is generated and emailed"*, while `sdk_guide(topic='install', platform='macos_arm',
   language='java')` offers *"a free **5-day** evaluation license (250K records)"* in the same
   paragraph that points at `submit_feedback` to request it. Two tools, one server, one session, two
   answers — so "source the figure from MCP at runtime" does **not** disambiguate here, and a
   duration written into this file would carry a real citation while having a coin-flip chance of
   being wrong. Say **time- and volume-limited** and let Senzing's email state the terms. Reported
   upstream as `category='bug'` on 2026-08-12 with the maintainer's approval; **retire this note
   outright — do not amend it — once the two tools agree.** The **500-record no-license cap** is
   unaffected and stays MCP-cited: today's `sdk_guide` response confirms it verbatim (*"Without a
   license, Senzing is limited to 500 Distinct Source Records (DSRs). Loading record 501 fails with
   SENZ9000|LIMIT"*).

   Those are the
   Bootcamper's personal details, not diagnostic context, so the bug-report rule that strips every
   identifier (INV-065, `../bootcamp-onboarding/feedback.md` Step 3c) cannot apply here — the call
   does not work without them. What carries over is the **consent discipline**, and it applies with
   more force, not less:

   1. **Confirm the current requirements from the tool itself** before asking for anything, so you
      request exactly the fields it needs and no more. Never collect a field "in case".
   2. **Ask for the values, one 👉 question per turn (INV-251)**, saying plainly that a work email is required
      and that a personal address will be rejected. Never put them in a config file, the recap, or
      the feedback file (INV-065) — hold them for the call alone.
   3. **Show the exact request, then ask permission**, pinned verbatim (INV-056), ending the turn on
      it. State what is sent, to whom, and what comes back:

      > 👉 **Send this evaluation-license request, including your name, work email, and how you heard about us, to Senzing? Reply with a number:**
      >
      > 1. **Yes, send it** — Senzing emails the license to that address.
      > 2. **No** — I'll get a license another way, or keep using the built-in evaluation license.

   4. **Send only on an explicit yes.** On anything else, record `license: evaluation`, continue,
      and do not re-ask (INV-006). Relay whatever the server returns verbatim.
   5. **A failure never blocks.** Report it in one line and continue on the built-in evaluation
      license.

   Declining costs the Bootcamper nothing: option 3's external channel and sub-step 5 remain open,
   and the bootcamp proceeds either way.

7. **Detect the active license's record limit (after a custom key is applied in sub-step 5).**
   Confirm the SDK facts via `sdk_guide(topic='configure', platform='<user_platform>',
language='<chosen_language>', version='current')` (`recordLimit`: `0` = unlimited, positive = the
   cap). Generate a scaffold that calls `SzProduct.get_license()`, save the returned JSON to
   `config/license.json` — `get_license` has **no** `response_schemas` entry (an empty `data` array
   is the expected result there, not a failed lookup), so read the saved JSON to confirm the shape
   before parsing it (INV-115) — parse `recordLimit`, and write `license_record_limit` into
   `config/bootcamp_progress.json`. Report the detected limit to the bootcamper (e.g. "Your license
   allows up to N records," or "no record cap (unlimited)" when `0`).

This gate is non-blocking on the obtain paths (the bootcamp proceeds on the evaluation license while
a key is pending). Once resolved — or when the volume was within the limit — clear
`license_guidance_deferred` and proceed to Step 8b.

**Checkpoint:** write step 8a to `config/bootcamp_progress.json`.

### 8b. SQLite load-time warning (collection-time heads-up)

This is a _time/performance_ heads-up, deliberately **distinct** from the license-capacity
sampling framing at the top of this module: it judges the Module 6 SQLite load time from the
**loadable** dataset and fires even when the effective license imposes no record cap. It is
**not a mandatory gate**: the bootcamper may always proceed on SQLite with the full dataset.
Run this once at the end of collection, immediately before the Step 9 transition. Every part is
non-blocking: any failure or indeterminate input continues the Module 4 flow.

⛔ **Judge the time from what will actually be LOADED, not from what was collected — the two differ
whenever Step 8a capped it, which is one step earlier in this same flow.** The "fires even when the
license imposes no cap" clause above is correct and stays: time is a separate concern from capacity.
Its mirror is what was missing — **when the license caps below the collected total, the collected
total is not what will be loaded, and a warning built from it describes work that cannot happen.**
On the walk that found this: 19,500 collected against a 500-record evaluation cap produced a warning
about a roughly half-hour load, for a load of about two minutes.

1. **Read the persisted inputs.** Read the registry from `config/data_sources.yaml` and
   `database_type` from `config/bootcamp_preferences.yaml` — the key Module 2 Step 7 writes when
   the engine is chosen, with the value `sqlite` or `postgresql`. Compute the collected total
   record count from the registry. If the registry cannot be read or parsed, treat the total as
   indeterminate: do not fail.
   - ⛔ **Also read Step 8a's outcome, which this step ran seconds after:** `license` in
     `config/bootcamp_preferences.yaml` and `license_record_limit` in
     `config/bootcamp_progress.json`. Then compute
     **`loadable = min(collected_total, effective_limit)`**, where the effective limit is
     `license_record_limit` when set, the built-in evaluation limit when `license: evaluation`, and
     **unbounded** when the limit is `0`. Treat an unreadable license state as unbounded — that
     reproduces today's behavior rather than inventing a cap.
   - ⛔ **If `database_type` is absent, say so rather than silently skipping the warning.** A
     missing key means Module 2 Step 7 did not record the choice, not that the engine is
     non-SQLite — and because step 2 below treats indeterminate inputs as "say nothing", an absent
     key makes this warning unable to fire **at all**, for any database or dataset size. That is a
     plugin defect, not a bootcamper outcome: note it internally so it surfaces in the recap, and
     fall back to the engine recorded by Module 2 in `config/bootcamp_progress.json` before giving
     up on the check.

2. **Decide whether to warn.** Warn only when the database is SQLite **and the LOADABLE total** is
   above the load-time threshold. Otherwise (loadable at or below the threshold, any non-SQLite
   engine, or indeterminate inputs) say nothing about load time and continue to the Step 9
   transition. A 19,500-record collection under a 500-record cap therefore says **nothing**, which
   is correct: 500 records is not a long load.
   - **Warn:** consult the **Senzing MCP server** at request time for the timing figures
     (expected throughput, throughput degradation, expected load duration, redo-phase
     duration). Any figure the server does not return, or that errors, stays unavailable: never
     substitute a remembered number. Present a load-time warning built from what the server
     returned, then end the turn on the question below and wait for the bootcamper's choice.
   - ⛔ **Ask `search_docs(query='hardware sizing capacity planning')` — the wording matters.**
     That query returns the **Hardware Sizing FAQ**, which is where the timing material lives:
     throughput per engine core, the three load phases (Phase 1 runs 10-100x faster than Phase 3,
     so a Phase-3 estimate is conservative), and worked load-time examples. `sdk_guide(topic='load',
     record_count=…)` returns the license note and the record-count threshold but **no timing
     figures at all**, so it is the wrong route for this. ⚠️ Nearby wordings do **not** find the FAQ
     — "hardware sizing capacity planning records per second load time" returns flag docs and code
     snippets instead — so use the query as written rather than paraphrasing it (verified on MCP
     server 1.32.9, docs indexed 2026-08-11 20:52 UTC, 2026-08-14).
     <!-- MCP-NEGATIVE: sdk_guide(topic='load', language='python', record_count=19500) — returns no load-duration or throughput figures — owner: search_docs(query='hardware sizing capacity planning') carries them, in the Hardware Sizing FAQ (routing negative — the fact exists, go there) — server 1.32.9, 2026-08-14 -->
   - ⛔ **State both numbers whenever they differ**, so the estimate is legible rather than
     mysterious: "19,500 collected, 500 loadable under the evaluation license — the load will take
     about N minutes." Suppressing the collected figure would be worse than the old behavior, not
     better.

   👉 **Loading all collected records into SQLite may take a while. How would you like to proceed? Reply with a number:**

   1. Load all records into SQLite.
   2. Sample down to a smaller record count.
   3. Switch to an alternative database like PostgreSQL.

   _(Internal: end the turn on this question and wait.)_

   ⛔ **Omit option 2 when the license already caps the load below the collected total.** "Sample
   down to a smaller record count" is the decision Step 8a just made — offering it again one step
   later is the INV-006 shape, and both remedies are the same action. Renumber the two remaining
   options (load it, or switch database) and say plainly that sampling is already in force under the
   license. When the license imposes no cap, present all three unchanged.

3. **Act on the choice.** Sampling is offered here as one option among proceeding and switching
   databases: not the only path.
   - **Load all collected records on SQLite:** first obtain an **explicit confirmation** that
     the bootcamper accepts the expected load time before continuing with the full dataset. Then
     record the decision (sub-step 4) and continue to Step 9.
   - **Sample down to a smaller record count:** ask which sampling strategy to use **before**
     creating the sample: offer first-N records, random-N records, and an
     entity-resolution-demonstrating strategy that preserves cross-source overlaps and known
     match clusters; also accept a bootcamper-described strategy. **Where 2+ sources are present,
     present the overlap-preserving strategy as the recommended one and say why the others lose
     cross-source matches — see the [sampling rule](#overlap-preserving-sampling) in Step 6, which
     is the canonical statement; do not restate it here.** Validate the target record
     count (a positive integer strictly less than the collected total) and re-ask until valid.
     Create the sample with the chosen strategy, write it under `data/samples/`, and document
     the strategy **and the reason for it** in a sample manifest. Then record the decision
     (sub-step 4).
   - **Switch to an alternative database (e.g. PostgreSQL):** route the bootcamper to the
     database-migration guide (the Kiro `docs/guides/DATABASE_MIGRATION.md` guide is a later
     porting phase). Do not inline or restate the migration steps here. Then record the decision
     (sub-step 4).

4. **Record the decision.** Write a load-decision marker capturing the choice
   (`proceed`, `sample`, or `switch_db`) keyed to the collected dataset identity, so the
   Module 6 SQLite heads-up does not redundantly re-ask about this same load.

Refer to the Senzing MCP server by name only (never a URL). Use only synthetic/persisted values
: never echo credentials or connection strings. _(The Kiro `volume_utils` and
`load_time_warning` helpers, and the shared marker/identity logic, are a later porting phase;
apply the behavior directly for now.)_

**Checkpoint:** write step 8b to `config/bootcamp_progress.json`.

### 9. Module completion and transition to Module 5

Run the standard **Module Completion** process in `../bootcamp-onboarding/module-completion.md`
(update progress, append the Module 4 recap section to `docs/bootcamp_recap.md`, and present the
end-of-module summary), then ask the single transition question:

"Great! Now that we have the data files, let's evaluate each one to see if it needs mapping or
if it's already in the right format for Senzing."

👉 **Are you ready to move on to the next module: {next module name}?**

**Checkpoint:** write step 9 to `config/bootcamp_progress.json`. On module completion set
`current_step` to `null`.

## Agent behavior

- Be patient with file uploads: they may take time.
- Provide clear instructions for each data source type.
- Help the bootcamper create sample files if full datasets are too large.
- Remind about data privacy and security.
- Verify files are accessible before proceeding.
- Document everything in `docs/data_source_locations.md`.
- **If the bootcamper doesn't have data or asks about free data sources** — and has **no
  bootcamp-generated scenario** (see the marker check in Step 2) — follow the data
  recommendation hierarchy: (1) recommend CORD data first via the `get_sample_data` MCP tool
  (Las Vegas, London, Moscow datasets) with reference to
  <https://senzing.com/senzing-ready-data-collections-cord/>; (2) if CORD is declined, recommend
  <https://github.com/docktermj/senzing-bootcamp-free-data> for raw samples and additional
  sources; (3) offer synthesized test data generation only as a last resort after CORD and
  free-data options are declined.

  ⚠️ **"Last resort" is scoped to that Bootcamper — the one arriving with no data and no scenario.**
  It is **not** a judgement on `provenance: synthesized`, which the Business Case Offer produces by
  design whenever no CORD collection fits the chosen category, and which Step 2 handles by generating
  the files without asking. Applying "last resort" there would re-open a settled decision and push
  CORD at a category Module 1 already ruled it out for.
- **If they pick ICIJ Offshore Leaks from the free-data catalog, give the dated caveat** stated in
  full at the secondary-options step above: as of **2026-08-11** its four sample files do not join —
  not one of the 10 rows in `relationships-sample.csv` has an endpoint present in the node files —
  so the disclosed-relationship (`REL_ANCHOR`/`REL_POINTER`) exercise is unavailable from that file;
  offer `service_provider` on `nodes-entities-sample.csv` as the workable alternative, and do not
  load `nodes-addresses-sample.csv` as records (`name` is 0% populated — address nodes, not
  entities). Everything else in the sample maps and loads normally, so do not call it broken. This
  is an upstream condition in `senzing-bootcamp-free-data`: re-check it rather than repeating it,
  and never re-slice or vendor the data here.
