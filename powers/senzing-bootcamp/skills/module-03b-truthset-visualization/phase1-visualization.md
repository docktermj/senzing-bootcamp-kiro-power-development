# Truth Set Visualization, Phase 1: Visualization (steps 1–2)

Follow `../bootcamp-onboarding/ground-rules.md`. `🛑`/`⛔` are internal directives, never
rendered; signal a stop by ending the turn on the single 👉 question and waiting.

**Purpose:** stand up an interactive visualization **web app** that shows the bootcamper a
resolved Senzing **Truth Set**, their "wow moment" with entity resolution. This module owns the
Truth Set end to end — System Verification does not acquire, load, or visualize it.

**Prerequisites:** the Senzing SDK is installed and initialized (Module 2) and the engine is
reachable, and System Verification has run immediately before. This module **acquires and loads the
Truth Set itself** (Step 1 below); it does NOT depend on System Verification having loaded any
data.

## Execution requirement (internal directive)

This module runs when the **Truth Set visualization** is selected — i.e. `truthset_visualization` is
in `selected_modules` (`config/bootcamp_preferences.yaml`). This is **always true in Core**; in
Customized it is true only if the bootcamper chose it (see `SKILL.md`). This phase file is loaded
only when the module is selected; when it is not selected the module does not run at all and System
Verification transitions straight to Data collection.

The visualization is MANDATORY here: it MUST be produced; you must NOT transition to the next module
until it exists and the bootcamper has been shown it. There is NO condition, threshold, or scenario
under which you may then skip it — no session-length, token-budget, redundancy, or time
rationalization is ever valid. Step 2 is unconditional, and this module's completion gate in
`phase2-close.md` re-checks that the visualization artifact exists and refuses to mark the module
complete if it does not (INV-077).

## Module start: Truth Set visualization (present at module start, before Step 1)

The Truth Set visualization is a **first-class, standalone module** (INV-086/INV-087) — so it opens
with the standard module-start apparatus (INV-079/INV-029–031, INV-063), exactly like any module start,
per `../bootcamp-onboarding/ground-rules.md`. Present it **once**, at the start of the module,
immediately before Step 1:

1. **Set `current_module`** to `truthset_visualization` in `config/bootcamp_progress.json` (a single
   quiet write, INV-058), so a resume mid-visualization re-opens the right module.
2. **Module-start banner (INV-079):** name only, no number —

   ```text
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   🚀🚀🚀  MODULE: TRUTH SET VISUALIZATION  🚀🚀🚀
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

3. **Journey map (INV-029):** refresh it with `truthset_visualization` now `🔄` current — `System
   verification` `✅`, the remaining `selected_modules` `⬜` upcoming.
4. **Before/After (INV-030):** *Before,* entity resolution is proven on synthetic data but unseen;
   *after,* the bootcamper has watched the Senzing Truth Set resolve in an interactive web app —
   their "wow moment".
5. **Step overview (INV-031):** briefly enumerate this module's steps — acquire the Truth Set →
   register the codes + load → build and serve the visualization → explore it → clean up.
6. **Estimated time (INV-096):** give an honest, range-based estimate (a handful of minutes,
   varying with Truth Set download and render speed), stated as "hard to estimate" if no meaningful
   figure is possible; suppress under the `minimal` verbosity preset, one line under `concise`.
7. **Model/effort (INV-063/INV-137/INV-138):** surface this module's recommended model/effort per
   `../bootcamp-onboarding/ground-rules.md` → "Best-value model/effort prompt", whose table is the
   authoritative source for the values. There is no `model_guidance` preference to read (INV-137).

   ⛔ **Do not pre-decide whether to ask — compare against what the bootcamper is running right
   now** (INV-138), not against the previous module's recommendation. This step used to assert the
   recommendation was "unchanged from System verification" and therefore a statement rather than a
   question; that became false when this module was re-rated to Opus 5 / high effort while System
   verification stayed on Sonnet 5, so a bootcamper who took the previous module's recommendation
   was never offered the switch for the module that *generates* the visualization server. Read the
   table, compare, and let the comparison decide: differing → the pinned 👉 switch question naming
   only the dial that differs; matching → the one-line statement.

Then proceed to Step 1 below. (Its end-of-module summary and `✅ Module complete: Truth Set
visualization` line are presented at this module's close — `phase2-close.md`.)

## Step 1: Acquire, register, and load the Truth Set (self-contained)

This module owns the Truth Set end to end — System Verification (Phase 1) no longer acquires or
loads it. Run these sub-steps **before** starting the web app, so the visualization always has
resolved Truth Set data to show. (Full source/fallback rationale is in `SKILL.md` → "Truth Set
source".)

### 1.1 Acquire the Truth Set (MCP-first, sanctioned fallback)

The Senzing MCP server is the primary and preferred source; it always takes precedence.

1. **Call `get_sample_data(dataset='list')`** — ⛔ `dataset` is a **required** parameter; the tool's
   own schema says a schema-respecting client cannot omit it, so a bare `get_sample_data()` fails
   and tells you nothing about availability (INV-136). Inspect `available_datasets` for a Truth Set
   entry. Classify:
   `available` = an entry whose name matches "truthset" (or `type: truthset`) with `available: true`;
   `unavailable` = no such entry — only the non-deterministic CORD collections are listed.

   Then **retrieve it with `dataset='truthset'`**: `source='list'` first for the data source codes and
   per-source record counts you will need in 1.2 and in the report, then the records themselves. Take
   the codes and counts from the response, never from this file (INV-080).

   > Verified on MCP server 1.32.2, 2026-07-30: `dataset='list'` returns **four** datasets — the three
   > CORD collections plus `truthset` (`available: true`) — and `dataset='truthset', source='list'`
   > returns the Truth Set's sources with their record counts. So the primary path normally succeeds;
   > treat the fallback below as genuinely exceptional rather than expected. Re-check rather than
   > trusting this note: the server ships independently of the Power.
2. **Available (primary path):** ⛔ **`get_sample_data(dataset='truthset', source='<CODE>')` returns
   a PREVIEW plus URLs — not the
   dataset.** Its `records` array is a sample (the response's `citation.note` says how many of how
   many), and saving it produces a file with a handful of records instead of the Truth Set's 159.
   That failure is silent: the graph renders, looks plausible, and misrepresents what Senzing did on
   the module the bootcamp treats as its showpiece. Verified on **MCP server 1.32.9, 2026-08-14**:
   `dataset='truthset', source='list'` returns `records: []` with `total_available: 159` and three
   sources; a per-source call returns a preview with `citation.note` reading *"Showing N of 17
   records (preview). To get more: download_url serves up to 10000 records per request and needs only
   mcp.senzing.com allowed; source_download_url is the complete uncapped file but requires egress to
   raw.githubusercontent.com."*

   So **download the records**, then verify the count:

   1. **Fetch each source from a URL in the response, never a hardcoded one.** Prefer
      `citation.download_url` (MCP-hosted; every Truth Set source is far below its
      `download_url_max_records` cap) and fall back to `citation.source_download_url`.
      ⚠️ **The two responses use the name `download_url` for different hosts** — a real trap:
      `source='list'` returns `available_sources[].download_url` pointing at
      **raw.githubusercontent.com**, while a per-source call returns `citation.download_url` pointing
      at **mcp.senzing.com**. Read the URL you actually intend to use rather than the field name
      (same server and date).
   2. ⛔ **Name the egress host from the URL you chose, per dataset.** `mcp.senzing.com` for the
      MCP-hosted download; for `source_download_url`, whatever host it carries — for the Truth Set
      that is **`raw.githubusercontent.com`**, *not* `senzing.com`. The MCP server's own instructions
      warn that allowing `mcp.senzing.com` does not cover GitHub content, so a firewalled bootcamper
      told to allow `senzing.com` would still fail here. (Module 4's sentence is CORD-specific; see
      `../module-04-data-collection/SKILL.md` → the download contract, which this step needs first
      because it runs before Module 4.)
   3. ⛔ **Retry with backoff on HTTP 429, and never write a non-JSON body into the file.** The
      MCP download endpoint is rate-limited, and back-to-back source fetches are exactly what trips
      it: the response is a 43-byte `Rate limit exceeded. Try again in 1 second.` served with **429**.
      `curl -sS -o file` writes that sentence **into `truthset_data.jsonl`** — `-sS` only silences the
      progress meter, and without `-f` a 4xx body is saved like any other — leaving one line of
      English prose in the middle of the dataset. Check the status before writing, or use `-f`/
      `--fail-with-body`, or fetch in a language whose client raises. Retrying with backoff recovers
      all three sources.
   4. ⛔ **Compare the written line count against the per-source `record_count` values from the
      `source='list'` call, and STOP on a mismatch.** (INV-228.) Expect exactly `record_count` from
      `source_download_url`, and `min(record_count, download_url_max_records)` from `download_url`
      (the same rule Module 4 states). This one check is what turns the whole class of under-fetch —
      preview-only, rate-limited, truncated — into a visible error instead of a sparse graph. Do not
      proceed to 1.2 on a mismatch: report the expected and actual counts per source and retry.

   Then save to `src/system_verification/truthset_data.jsonl` (overwrite, one JSON object per line),
   provenance `mcp_primary` (30-second timeout per fetch).
3. **Unavailable (fallback path):** fetch the demo Truth Set **DATA only** from the sanctioned
   fallback source — resolve source id `senzing_truthset_demo` from `config/fallback_sources.yaml`,
   never a raw URL — write `truthset_data.jsonl`, provenance `github_fallback`. (If the registry
   file is absent, treat the fallback as unavailable.)
4. **Both unavailable:** report both failures with remediation (verify MCP connectivity; verify
   the fallback is reachable; say "retry"). Then offer a clearly labeled **non-deterministic**
   CORD collection that exercises the visualization but has no ground-truth key:

   👉 **The Truth Set is unavailable. Would you like to visualize a non-deterministic CORD collection (Las Vegas, London, Moscow) instead?**

   *(Internal: end the turn on this question and wait.)* If declined, the visualization cannot be
   produced; record the block and tell the bootcamper how to retry.

Record the source provenance (`mcp_primary` / `github_fallback` / `cord_substitute`) and the
expected record count for the report.

### 1.2 Register the Truth Set data source codes and load

1. Collect the distinct `DATA_SOURCE` values present in `truthset_data.jsonl` (for the standard
   Truth Set: CUSTOMERS, REFERENCE, WATCHLIST; a CORD substitute uses whatever codes its records
   carry). Never register a code that is not present in the data.
2. Generate the registration code from the MCP server (`sdk_guide(topic='configure')`, and
   `generate_scaffold` if it exposes a registration workflow) in the language read from
   `programming_language` in `config/bootcamp_preferences.yaml` — register each code and set the
   updated config as the new default, **idempotently** — then load `truthset_data.jsonl` into the
   Senzing database (generate the loader via `generate_scaffold` / reuse the Module 3 Phase 1
   pipeline pattern; never direct SQL). Registering **before** the load upholds the "register
   before load" guarantee so the load never fails with `SENZ2207`.

Save the load artifacts under `src/system_verification/` — that is where INV-050's project layout
places them, and they are **this** module's artifacts even though they sit in a directory named for
another (INV-087 keeps the two modules separate). System Verification's own re-run cleanup is
required to leave them untouched, so nothing here is lost if that module runs again
(`../module-03-system-verification/phase1-verification.md` → Agent Rules, *Overwrite on re-run*).
Once the Truth Set is loaded, continue to Step 2 below to visualize it.

## Step 2: Build and run the visualization server in your chosen programming language

The Truth Set visualization is delivered by a web server **written in the Bootcamper's chosen
programming language** (`programming_language` in `config/bootcamp_preferences.yaml`) — like every
other deliverable in this bootcamp. The shipped `../bootcamp-onboarding/scripts/senzing_viz_server.py` is the **reference
model** for what to build, and `visualization-api-reference.md` (this skill directory) is the
authoritative API/response contract to implement. `senzing_viz_server.py` is **run directly only
when the chosen language is Python**; for any other language it is a model to read, never run.

Whatever the language, the server MUST reproduce the reference's behavior:

- Build the entity model from the loaded records — one `get_entity_by_record_id` call per record,
  requesting the default entity flags (which include all relations) so it never queries the
  database directly. Get the exact SDK method, flag, and attribute names from the Senzing MCP tools
  (`sdk_guide` / `get_sdk_reference` / `generate_scaffold`), never from training data (INV-080).
- Serve the JSON APIs — `/api/stats`, `/api/graph`, `/api/merges`, `/api/records`, `/api/search`,
  `/api/why`, `/api/how`, `/api/overlap`, `/api/matchkeys`, `/api/features` — with the exact
  response shapes in `visualization-api-reference.md`. That contract is the authority on the
  endpoint set: **`/api/dashboard` was removed** and MUST NOT be implemented (its counts and
  histogram duplicated `/api/stats`, which now also carries its one unique payload,
  `sample_entities`), while **`/api/records` is required** — it backs the Records action that every
  entity surface must offer.
- Serve the live D3 v7 page as a **single consolidated, tabbed app** (all tabs in 2.4), and write a
  self-contained standalone HTML snapshot.
- **Render offline (INV-091):** inline the vendored D3 at
  `${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/vendor/d3.v7.min.js` (skill-relative fallback:
  `../bootcamp-onboarding/scripts/vendor/d3.v7.min.js`, INV-252) into both
  the live page and the standalone snapshot; never fetch from a CDN. (D3 runs in the browser, so
  this holds regardless of the server's language.)
- **Use the Senzing brand (INV-081):** take the palette and typography from the shipped brand
  tokens (`${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/brand_tokens.py`, skill-relative fallback
  `../bootcamp-onboarding/scripts/brand_tokens.py` — INV-252; mirrored in `senzing_viz_server.py`). A non-Python server
  cannot import the Python module, so replicate the token **values** from the reference; never
  invent an ad-hoc palette. ⛔ **Assign data-source colors from the sources actually present in the
  data, never by lookup in a map keyed by expected source names** (INV-127) — the Truth Set happens
  to carry CUSTOMERS, REFERENCE and WATCHLIST, but a name-keyed map collapses every *other*
  bootcamper's sources to one fallback color, and this same server is re-pointed at their own data
  in Query, Visualize and Discover. The rule is specified in
  `visualization-api-reference.md` → "Rendering contract".
- **Map edges correctly:** expose `source`/`target` (from `source_entity_id`/`target_entity_id`)
  **before** `forceLink().links(...)`, preserving node `id`/`entity_id` — omitting this renders an
  empty graph.

Save the generated server and its assets under `src/server/` (INV-050). The Senzing native library
must be importable, so run everything with the project env sourced (the `src/scripts/senzing-env.sh`
/ `senzing-env.bat` created in Module 2): `source src/scripts/senzing-env.sh` on Linux/macOS, or
`src\scripts\senzing-env.bat` on Windows first.

### 2.1 Choose the path

Read `programming_language` from `config/bootcamp_preferences.yaml`:

- **Python** → the reference implementation *is* the server. Resolve `../bootcamp-onboarding/scripts/senzing_viz_server.py`
  (`${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/senzing_viz_server.py` in a command/hook context, else
  `../bootcamp-onboarding/scripts/senzing_viz_server.py` relative to this skill) and run it directly. This is the
  **only** path on which `senzing_viz_server.py` runs.
- **Any other language** → generate the server in that language per the contract above, modeled on
  `senzing_viz_server.py` + `visualization-api-reference.md`, saved under `src/server/`. Do **not**
  run `senzing_viz_server.py`. Generate code via the MCP tools and a generator per your language's
  conventions; never hand-write SDK calls or HTML+JS with file-write tooling.

### 2.2 Always produce the standalone snapshot first (the guarantee)

Before starting the live server, run your server in build-only / snapshot mode to (a) build the
entity model and (b) write a **self-contained standalone HTML snapshot** the Bootcamper keeps even
if they never open the live server. This is the artifact the completion gate checks, so the
visualization is guaranteed to exist (INV-077). Write it to
`docs/visualizations/truthset_verification.html` from `src/system_verification/truthset_data.jsonl`,
titled "Senzing Truth Set", and tell it what the data **is** so the retained snapshot says so
(INV-172). For Python, that is:

```bash
python3 <viz-server-path> \
  --records src/system_verification/truthset_data.jsonl \
  --title "Senzing Truth Set" \
  --dataset "the Senzing Truth Set" \
  --snapshot docs/visualizations/truthset_verification.html \
  --no-serve
```

⛔ **Title it after this module, never after System Verification.** The Truth Set belongs to this
module alone — System Verification uses synthetic records and does not visualize it (INV-082/INV-087)
— and the title ships permanently into the snapshot the Bootcamper keeps and the recap embeds. A
title naming the module that never touches the Truth Set misattributes their artifact.

⛔ **Pass the dataset wording; do not leave it to the default.** `--dataset` is what the snapshot's
Search / Probe note calls the data. Left empty it says the neutral "the loaded data" — correct but
vague, and this is the one module where the answer is certain: it is the Senzing Truth Set — the
dataset `get_capabilities` describes as "the Senzing demo truth set: CUSTOMERS, REFERENCE,
WATCHLIST", acquired here via `get_sample_data(dataset='truthset')` (server 1.32.2, verified
2026-07-29). Query, Visualize and Discover passes its own wording for the Bootcamper's data; neither
module may let the other's label reach its snapshot.

(The **filename** stays `truthset_verification.html`. Bootcamp graduation maps each screenshot to its module
by that base name (`../graduation/SKILL.md` → "Backfill orphaned screenshots") and recaps already
reference it, so renaming it would break that mapping for no Bootcamper-visible gain.)

For any other language, invoke your server's equivalent build-only/snapshot mode — writing the same
file, passing the same title and dataset wording, no server started. Confirm the file exists before continuing. If the build fails, do not
proceed to the live server: fix the underlying cause (regenerate faulty code from the MCP tools;
re-run SDK initialization from Module 2 / System Verification; check `config/engine_config.json`)
and retry until the snapshot is written — the module does not complete without it.

**Capture screenshots for the recap (optional, non-blocking).** Defer this until the live server is
running (2.3) and capture from **`--url http://localhost:<port>`** — substituting the port the
server was **actually started on** in 2.3, which is `8080` only when that port was free (INV-172).
Capturing from a port nothing is listening on exits 2 and loses every image for this module, and
those images cannot be re-taken after teardown. One image per tab, so the
Search / Probe tab shows real results — the standalone snapshot has no engine, so its search box is
inert. `{name}` = `truthset_verification`. Follow
`../bootcamp-onboarding/module-completion.md` → "Capturing visualization screenshots", including its
rule that every caption is derived from the opened image and its tab label, never from the plan.

If the server could not be started, fall back to `--html docs/visualizations/truthset_verification.html`
and either omit the Search / Probe tab or caption it as the inactive state. If no headless capability
is available it skips silently; otherwise **keep every captured tab and embed them all** in this
module's recap `Actions Taken`, in the app's tab order — capture is one image per tab (INV-122), so
there is nothing redundant to drop and a count cap can only delete unique content (INV-146). This is
never a 👉 question and never blocks the visualization.

⛔ Capture **before** the module's teardown and purge (`phase2-close.md` Step 4) — afterwards the
server is gone and the Truth Set data cannot be re-served, so a missed capture is permanent.

### 2.3 Start the live web app

Start the server as a background process you can stop later in Step 4 (Cleanup), serving the loaded
records on port 8080. For Python:

```bash
python3 <viz-server-path> \
  --records src/system_verification/truthset_data.jsonl \
  --title "Senzing Truth Set" \
  --dataset "the Senzing Truth Set" \
  --port 8080 &
VIZ_PID=$!
```

For any other language, start your server's equivalent. It should report a URL like
`http://localhost:8080`. If port 8080 is in use, use a different port and tell the Bootcamper the
chosen URL.

⛔ **Record the process id along with the port** — `$!` in a POSIX shell as above,
`$proc.Id` from `Start-Process … -PassThru` in PowerShell. It is the only unambiguous handle on the
server, and Step 4 has no other way to name what it must stop: the server may be written in any of
the five languages (INV-090), so there is no script name to match on, and matching one anyway
signals the shell doing the matching. The full rule, including the port-based fallback, is in
`visualization-api-reference.md` → "Server lifetime" → "Identifying the server process".

### 2.4 Verify the endpoints

The app serves the live page at `/` plus JSON APIs. Verify each (10-second timeout):

| Endpoint | Success criteria |
|----------|-----------------|
| `GET /api/stats` | HTTP 200; fields `records_total`, `entities_total`, `multi_record_entities`, `cross_source_entities`, `relationships_total`, `data_sources_total`, `histogram`, `bucket_entities` (per-bucket entity lists for the clickable histogram) |
| `GET /api/graph` | HTTP 200; `nodes` (each: `entity_id`, `entity_name`, `record_count`, `data_sources`, `records`) and `edges` (each: `source_entity_id`, `target_entity_id`, `match_key`, `relationship_type`) |
| `GET /api/merges` | HTTP 200; at least one multi-record entity (2+ records) |
| `GET /api/search?q=Robert Smith` | HTTP 200; `results` array with resolved entities, each carrying `match_key` and `resolution_rule` |
| `GET /api/why?entity_id=<id>` | HTTP 200; real `WHY_RESULTS` (or an `error` field) explaining why the entity's records resolved together |
| `GET /api/how?entity_id=<id>` | HTTP 200; real `HOW_RESULTS` (or an `error` field) explaining how the entity was constructed |
| `GET /api/records?entity_id=<id>` | HTTP 200; `entity_id`, `entity_name`, and a `records` array carrying each constituent record's `data_source`, `record_id`, and fields — backs the Records action on every entity surface |
| `GET /api/overlap` | HTTP 200; `sources` + square `matrix` of cross-source shared-entity counts |
| `GET /api/matchkeys` | HTTP 200; `match_keys` (most-frequent first) + `distinct` + `capped` |
| `GET /api/features` | HTTP 200; `features` (per-feature score-bucket counts), `sampled`, `multi_record_total`, `capped` |

⛔ **An empty visualization is a FAILED verification, never a passing one (INV-250).** This step
exists to show the bootcamper that Senzing works on their workstation, so a page that renders with
`entities_total` at zero has demonstrated the opposite. If `/api/stats` reports no entities — or the
graph opens empty — say so plainly, name the likely cause, and do **not** move on as though the
step passed. **The most common cause is a datastore connection that is not persistent and shareable
across processes (INV-231):** the loader writes to one place and this server reads another, so every
load reports success and nothing fails until this page comes up blank three modules later. The
connection-string rule and the scheme it forbids are in `ground-rules.md` → "Mandatory gates and
step order". Re-check the datastore before rebuilding the server.

The live page is a **single consolidated, tabbed app** — the one visualization artifact (no
separate static pages). All tabs are populated from these APIs; a tab whose data is absent is not
shown:

**Every entity shown with actions gets the same three buttons — Records / Why? / How? — with no
exceptions**, and **every aggregate view drills down** to the entities behind it. Those two rules,
the Why?/How? rendering contract, the graph label/legend rules, and the search-hint requirement are
specified in `visualization-api-reference.md` → "Per-entity actions" and "Rendering contract".
Build to that contract; the summaries below are the tab inventory, not the full requirements.

1. **Entity Graph** (default): D3 v7 force-directed graph of the full entity population. Nodes
   colored by data source (CUSTOMERS ember/orange, REFERENCE blue, WATCHLIST gold/amber), sized by
   record count, hover tooltip, click-to-detail modal with the three actions, zoom/pan, and a
   click-to-filter source legend generated from the data. Independent node-label and edge-label
   toggles, defaulting off above ~150 nodes with an on-screen note saying why. This is also the
   cross-source entity-relationship view (it subsumes the former `multi_source_results.html`).
   (Your server MUST perform the edge-key mapping, `source_entity_id`/`target_entity_id` →
   `source`/`target` before `forceLink` — per Step 2's intro; omitting it renders an empty graph.)

   It also carries a **"Show only entities with relationships"** toggle, shown only when
   `relationships_total > 0`. Switched on, the graph filters to the subgraph of entities that a
   relationship connects and styles edges by `relationship_type` (color **plus** line style), with
   a click-to-filter type legend built from the types actually present. Same label toggles and
   scale-aware defaults in both modes. This is a **mode of this tab, not a second tab** — both modes
   are served by the same `/api/graph` payload, so a standalone "Relationship Network" tab would be
   a duplicate (contract: "De-duplication (required)").
2. **Merge Statistics:** records-per-entity histogram (1 / 2 / 3 / 4+) — this **is** the entity-size
   distribution; the bars are **clickable** (backed by `bucket_entities`) and drill down to the
   entities in each bucket. Beneath it, the largest resolved entities from `sample_entities`. Both
   lists use the three actions. Headline counts live in the page summary strip and are **not**
   repeated here.
3. **Match Keys** (when multi-record entities exist): frequency of the match keys (feature
   combinations) that drove resolutions; **rows are clickable** (backed by `match_key_entities`) and
   drill down to the entities carrying that key.
4. **Feature Scores** (when multi-record entities exist): how tightly each feature agreed across
   resolved records, from a capped `why_records` sample; the tab always shows the sample size.
5. **Cross-Source** (when 2+ data sources): overlap heatmap of how many entities each pair of
   sources shares; **cells are clickable** (backed by `cell_entities`) and drill down to the
   entities in that cell.
6. **Search / Probe:** search by name; results show the resolved entity, its sources, and the
   match key / resolution rule that linked it, plus the three actions. Search tries `NAME_FULL` then
   `NAME_ORG` — organization names do **not** match under `NAME_FULL` and fail silently, so a
   `NAME_FULL`-only search finds no organizations at all (see the contract's `/api/search` section).
   Ships with pre-verified example-query chips that fill **and** run the search on click — *verified*
   meaning each was actually run and returned a hit, since a chip derived from a real entity can
   still find nothing — and a **"Show all merged entities"** button that lists every multi-record
   entity with no query — the no-query browse that the former Record Merges tab uniquely offered.
   This must work in the standalone snapshot too, so it reads the embedded `merges` payload rather
   than the live search.

Do **not** add a tab whose content is derivable from another tab's endpoint. In particular there is
**no "Results Dashboard" tab** — its counts and histogram duplicated `/api/stats`, and its unique
content (the largest resolved entities) is now `sample_entities`, rendered on Merge Statistics. The
entity-size distribution is Merge Statistics, and the cross-source entity-relationship view is
Entity Graph (per `visualization-api-reference.md` → "De-duplication").

### 2.4b Any change to the visualization means rebuilding the snapshot

⛔ **If the visualization's code changes for any reason after 2.2 — a bootcamper request, a bug fix,
a styling tweak — re-run the build-only snapshot step (2.2) and re-verify it. Do not stop at
re-verifying the live server.** (INV-130 — the retained snapshot MUST be rebuilt after **any**
post-build change, and re-verifying the live server is explicitly not a substitute.)

This is a numbered step, not a note, because the failure is silent and permanent. The snapshot is
the artifact the bootcamper keeps and the one embedded in the recap; the live server is torn down at
module close, and Step 4 then **purges the Truth Set records**, so after that point the snapshot
cannot be rebuilt at all — the data it needs is gone. A change that is not in the snapshot did not
happen as far as the bootcamper's permanent record is concerned.

It has happened: two design simplifications were implemented, verified on the live server, and
approved by the bootcamper, but the snapshot was never rebuilt. The keepsake shipped with the
eight-tab UI they had asked to change, contradicting the recap prose in the same section — a claim
and a screenshot that disagree.

After rebuilding, confirm the snapshot's tab set matches the running server's (Step 3's completion
check in `phase2-close.md` verifies this too) and re-capture any screenshots taken from the stale
copy.

### 2.5 Present it and give the guided tour

Tell the bootcamper the app is running and where the saved copy is:

- "Your visualization is running at `http://localhost:<port>`, open it in your browser."
  (Substitute the port actually in use — never a literal `8080` when 2.3 chose another, or this
  line sends the Bootcamper to a port nothing is listening on. INV-172.)
- "A saved copy is at `docs/visualizations/truthset_verification.html`, you can open that file
  any time, even after we stop the server. Every tab still works offline there, except **Why?**,
  **How?**, and live search — those need the running engine, so use them while the server is up."

Then deliver this guided tour as one message (no interactive pauses):

---

🗺️ **What you're looking at:**

- **Entity Graph:** each circle is a resolved entity. Multi-colored clusters and edges show
  records that Senzing linked across data sources, a customer who is also on the watchlist, for
  example. Edge labels (like `+NAME+ADDRESS`) are the match keys: the features Senzing used to
  link them.
- **Merge Statistics:** the histogram shows how many records collapsed into each entity, tall
  bars at 2/3/4+ are where Senzing found duplicates.
- **Search / Probe:** type a name (try "Robert Smith") to see the resolved entity and why it
  matched.
- **More tabs:** **Match Keys** and **Feature Scores** show what drove the resolutions;
  **Cross-Source** (with 2+ sources) maps where your sources overlap. On **Entity Graph**, the
  "Show only entities with relationships" toggle narrows the picture to just the entities that
  connect to something else. (Point these out briefly — one line — under `concise`/`minimal`
  verbosity, or skip the list.)

---

Take your time exploring the visualization — the server stays up.

👉 **Are you ready to continue?**

*(Internal: end the turn on this question and wait for the bootcamper to confirm they are done
exploring. Do not proceed to Phase 2 (the close) until they respond.)*

⛔ **This question does not authorize teardown.** It asks whether the bootcamper is ready to move on
in the module — nothing more. The server keeps running past it; stopping it and purging the data
require their own gate in Phase 2 Step 4 (see `visualization-api-reference.md` → "Server lifetime").
Never treat a yes here as consent to stop the server.

**On failure:** report the specific endpoint or step that failed and the fix:

- Port in use → pass a different `--port` and share the new URL.
- Engine/SDK error → re-run SDK initialization (Module 2 / System Verification); confirm `config/engine_config.json`.
- Snapshot not written → the model build failed; read stderr, fix the cause, and re-run 2.2.

**Checkpoint:** write to `config/bootcamp_progress.json`:

```json
{
  "truthset_visualization": {
    "checks": {
      "web_service": {"status": "passed|failed", "port": <port>, "pid": <pid>},
      "web_page": {"status": "passed|failed", "url": "http://localhost:<port>/",
                   "snapshot": "docs/visualizations/truthset_verification.html"}
    }
  }
}
```

**Success indicator:** ✅ The standalone snapshot exists at
`docs/visualizations/truthset_verification.html` AND the live app served its endpoints and
the entity-graph page.

## Fallback: guarantee the snapshot if the live server cannot run

If, after iterating with the MCP tools, the live server cannot be made to serve, you MUST still
produce the standalone snapshot (INV-077): generate a self-contained D3 v7 HTML snapshot — vendored
D3 inlined (INV-091), Senzing brand tokens applied (INV-081), edges mapped `source_entity_id`/
`target_entity_id` → `source`/`target` before `forceLink` — written to
`docs/visualizations/truthset_verification.html`, so the completion gate's guarantee holds. Produce
it with the chosen language's tooling (a generator, not direct HTML+JS file-writes). Only when the
chosen language is **Python** may you fall back to the bundled `senzing_viz_server.py`; for any
other language `senzing_viz_server.py` is never run. The full response schemas and the
search-enrichment specification are in `visualization-api-reference.md`.

When the bootcamper has finished exploring, load `phase2-close.md`.
