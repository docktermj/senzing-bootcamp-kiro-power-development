# Module 6, Phase A: Build Loading Program (steps 1–4a)

Follow the ground rules. `🛑`/`⛔` are internal control directives, never render them; signal
a stop by ending the turn on the single 👉 question and waiting. All loading, redo, and query
code comes from the MCP tools (`generate_scaffold` / `sdk_guide`), never hand-written.

## Before Loading: pre-load checks

Complete these three checks before starting step 1.

### Conditional workflow, check Phase 3 status

Read `config/data_sources.yaml` and check `test_load_status` per source:

- **`complete`**, Phase 3 was done in Module 5. Acknowledge: "You already test-loaded this
  source during Data Quality, Mapping, and Transformation (Phase 3) and saw [entity_count] entities. Data processing builds on that with
  production-quality loading, error handling, progress tracking, throughput optimization, redo
  processing, and incremental strategies." Skip the basic test-load step and go straight to the
  production loading workflow.
- **`skipped` or missing**, note that a brief test load is **owed** for that source, and say so:
  "You skipped the sandbox test load in Data Quality, Mapping, and Transformation, so we'll do a
  quick one before the full load." ⛔ **Do not run it here.** Phase B step 5 runs it, and it
  cannot run any earlier: it needs the loading program, which step 3 builds from the volume tier
  captured at step 1, and the registered `DATA_SOURCE` codes, which step 4a creates — without
  which the load fails with `SENZ2207`, the exact error step 4a exists to prevent.

**Phase 3 results integration:** if `test_load_status` is `complete` for multiple sources, use
`test_entity_count` to estimate total volume and plan resource allocation, use Phase 3 quality
assessments to inform load order (higher quality → stronger baseline), and note any issues
found during Phase 3 that may affect orchestration.

### Pre-load data freshness check (advisory only)

If the bootcamper is using CORD sample data (downloaded via `get_sample_data`), remind them to
confirm their data files haven't changed since download. This is advisory only, never block
loading. If they are using their own data, skip silently. (This Power ships no CORD-freshness
helper; compare against `config/cord_metadata.yaml` and give the reminder inline.)

### Anti-pattern check

Call `search_docs(query="loading", category="anti_patterns", version="current")`. Key pitfalls:
bulk-loading issues, threading problems, redo processing, load-order dependencies.

## 1. Assess production record volume

Present this pinned question verbatim (INV-056), including the explanation — the explanation is
what stops the bootcamper answering with the bootcamp's record count instead of their real target:

> 👉 **In production — not in this bootcamp — how many records do you expect to load? Reply with a number:**
>
> This is about the system you're ultimately building, **not** the dataset we're working with here.
> It changes the loading program's *architecture*: a demo loader and a fifty-million-record loader
> are genuinely different programs (single-threaded vs. thread-pooled, batching, checkpoint/resume,
> throughput instrumentation, queue-based distribution). Answer for your real target volume even if
> it dwarfs the bootcamp dataset. This program is yours to take home.
>
> 1. 500 or fewer — demo/evaluation
> 2. More than 500, up to 500,000 — small production
> 3. More than 500,000, up to 10,000,000 — medium production
> 4. More than 10,000,000 — large production
>
> Not sure yet? Give your best estimate — we'll build for that, and it can be revisited.

⛔ Never substitute the bootcamp's own record count into this question — reference it dynamically or
not at all, or the pinned wording goes stale the moment the dataset changes.

*(Internal: end the turn on this question and wait.)*

**Classify and persist the tier.** Map the answer to a tier, `demo` (500 or fewer), `small`
(more than 500 up to 500,000), `medium` (more than 500,000 up to 10,000,000), `large` (more than
10,000,000). Each boundary value belongs to exactly one tier. **500 itself is `demo`**, and that is
deliberate: `sdk_guide` returns the single-threaded demo template at or below 500 (see "The cutover
is 500 records" below), so classifying exactly 500 as `small` would route the bootcamper to the
threaded-pattern instructions and then hand them a loader the tool itself labels "demo-only".
If the reply is a bare option number (1–4),
select that tier directly. If it is free text, parse the number and classify. If it is
unparseable, ask ONE clarifying follow-up presenting the four numbered tiers, then classify; if
still unparseable, default to `demo` and tell the bootcamper demo/evaluation was selected as
the default. Persist `production_volume` (`tier` and `raw_value`) to
`config/bootcamp_preferences.yaml` and checkpoint step 1 to `config/bootcamp_progress.json`.

(No answer-parsing or volume helper is bundled; apply the parsing and persistence logic inline.)

⛔ **Echo the consequence back before generating any code.** State the tier *and* the architecture
it selects, and invite a correction — a misread costs nothing to fix here and is expensive to
discover once the loader is written. For example: "Medium production, so I'll build a thread-pooled
loader with batching, checkpoint/resume, and throughput reporting — say the word if that volume
isn't right." For `demo`, name what they are getting and why: "Demo/evaluation, so a single-threaded
loader — simplest to read, and appropriate below the license limit. If your real target is larger,
tell me now and I'll build the threaded version instead."

**License framing (default + expansion paths).** After the tier is classified, present
licensing as a default the bootcamper already has, never as a hard cap:

- Frame the built-in evaluation license as the default they already have. Present the expansion
  paths — apply an existing license, request one through the external channel
  (<support@senzing.com>), and, when available, request one in-flow via the Senzing MCP server —
  before any mention of downsizing. Downsizing (sampling or a smaller subset) is one option
  among these, not the only path.
- Source the record capacity and validity period from a Senzing MCP tool — **from the server,
  not from this file** (a sourcing floor) — and present exactly what it returns. If a value is unavailable or the MCP server can't be reached,
  omit the figure and say it is currently unavailable, never substitute a remembered figure.
- Gate the in-flow path as Module 1 does: check `submit_feedback` availability via
  `get_capabilities` (wait up to 30s), and omit the in-flow path when it is unavailable, errors,
  or does not respond. If the bootcamper already has a license (`license` set in
  `config/bootcamp_preferences.yaml`), route them to the apply-an-existing-license path and omit
  the in-flow option. Refer to the Senzing MCP server by name only, never a URL.

**Checkpoint:** write step 1 to `config/bootcamp_progress.json`.

## 2. Identify the input data

Determine where each source's Senzing-formatted JSON records are — read the source's `file_path`
from `config/data_sources.yaml` rather than assuming a fixed directory:

- Mapped sources: transformation output from Module 5, in `data/senzing-ready/`
- Fast-pathed CORD / already-Senzing-ready sources (`fast_pathed: true`): the original file in
  `data/raw/`, which Module 5's fast-path kept as the source's `file_path` (no transformation)
- Direct Entity Specification-compliant data files; database query results or API responses

Update the source's `load_status` to `loading` in `config/data_sources.yaml` and set
`updated_at`.

**Checkpoint:** write step 2.

## 3. Create the production loading program

Help the bootcamper build a complete, production-quality loading program for this source. All
generated code must follow the coding standards for the chosen language. (No coding-standards
reference is bundled; apply clean-code conventions for the language.)

**Volume-aware scaffold.** Read `production_volume` from `config/bootcamp_preferences.yaml`.

⛔ **`record_count` is a parameter of `sdk_guide`, not of `generate_scaffold`.** `sdk_guide` is the
tool that *selects* the threaded or single-threaded template from the record count; passing
`record_count` to `generate_scaffold` does nothing, because that tool takes only `language`,
`workflow`, and `version` and returns the whole snippet list. Verify both signatures via
`get_capabilities` rather than trusting this note (a sourcing floor).

**The cutover is 500 records, from `sdk_guide`'s own `record_count` contract** (re-read on MCP
server 1.32.9, 2026-08-14) — `sdk_guide`'s own
contract for `record_count` states that at or below 500 it returns the single-threaded demo, and
above 500 (or when the count is omitted) it returns the threaded production pattern. A call at a
few thousand records returns the thread-pool template and labels the single-threaded alternative
"demo-only, single-threaded — do not use for production volumes (>500)". This matches
`search_docs(query="loading", category="anti_patterns")` → "Senzing Anti-Patterns: Architecture and
Performance" → **"Do Not Use Single-Threaded Loading"**, whose remedy is a thread pool of 2–8
workers per CPU core. Re-confirm the threshold from MCP at implementation time; do not carry this
number forward as a remembered fact.

⛔ **The same call also returns a licensing verdict — and it is computed from the record count
alone.** `sdk_guide`'s own contract for `record_count` states that values above 500 "surface license
guidance (default Senzing license limit)". The tool has no way to know what license is installed, so
above the threshold it emits a `LICENSE REQUIRED` note prescribing an evaluation license or sampling
to the first 500 records — **whether or not any of that applies to this bootcamper**.

**Reconcile it against the license already detected before relaying or acting on it.** Read
`license_record_limit` from `config/bootcamp_progress.json` (Module 4's license gate, Step 8a,
persists it from `SzProduct.get_license()`) and apply the same effective-limit rule as
`phaseB-load-first-source.md`:

- **`0` (no cap), or ≥ the dataset size** — the note does not apply. **Suppress it entirely**: say
  nothing about licenses or sampling, take the returned code, and ignore the licensing prose. A
  warning the bootcamper cannot act on is noise (INV-012).
- **Positive and below the dataset size** — the note applies. The single License Key gate (Module 4,
  Step 8a) already offered to expand capacity; restate that as a choice, never force downsizing.
- **Absent or null** — ⛔ **this means "never asked", not "no custom license". Measure it, do not
  assume it.** (INV-244) The only writer of `license_record_limit` is Module 4's Step 8a gate, which is
  volume-gated by design: a bootcamper with a small dataset never triggers it, so the field is
  absent no matter what license is installed. Assuming the default here relays a 500-record note —
  and `sdk_guide`'s sampling prescription with it — to someone whose license may have no cap at
  all, which is the same harm named just above, reached through the branch that is taken far more
  often. It also contradicts a higher-precedence rule: a value you measured on this machine governs
  over generic guidance about that same value, and `ground-rules.md` names the license record limit
  explicitly (INV-012). It is one SDK call away.
  - **Measure it** by the procedure Module 4 Step 8a already defines — generate a scaffold calling
    `SzProduct.get_license()`, save the returned JSON, read it to confirm the shape before parsing
    (INV-115), and parse `recordLimit`. Follow that step rather than re-deriving it; the module
    already builds and runs SDK programs in the bootcamper's language, so this needs no new
    machinery. (`get_sdk_reference(topic='response_schemas', filter='getLicense')`, server 1.32.9,
    2026-08-14, confirms the method in every binding — `SzProduct.getLicense() -> String`,
    `get_license() -> str`.)
  - **Persist it** as `license_record_limit` in `config/bootcamp_progress.json`, so later steps,
    Phase B and graduation see a detected value instead of the same absence.
  - **Then re-enter these three branches** with the measured value. `recordLimit: 0` lands on the
    first branch and correctly suppresses the note.
  - **Only if the call fails** (no engine yet, SDK error) does the default-limit note apply — and
    say plainly that it is an assumption, naming what could not be measured, rather than presenting
    it as the detected limit.

Acting on the unreconciled note is not harmless: it sends a bootcamper with an unlimited license to
sample down to 500 records, and the shrunken dataset then under-demonstrates the cross-source
resolution that Modules 6 and 7 exist to show. Observed with `record_count=23152` against a license
reporting `recordLimit: 0`.

So only the `demo` tier — which is below the default license limit anyway — gets a single-threaded
loader. Every tier that represents a real production system gets the threaded pattern:

- **`small`, `medium`, or `large`:** call `sdk_guide(topic='load', language='<chosen_language>',
  record_count=<raw_value>)` for the threaded production pattern. Add a code comment stating the
  tier and the architecture recommendation (thread pool for small and medium; distributed /
  queue-based for large).
- **`demo`:** call `sdk_guide(topic='load', language='<chosen_language>', record_count=<raw_value>)`
  — the same call, with a count below the threshold, which returns the single-threaded demo
  template. Add a code comment stating the tier and that single-threaded loading is appropriate at
  demo scale **and is a documented anti-pattern above it**, so the bootcamper knows what to change
  if their volume grows.
- **Missing or unreadable:** call `sdk_guide(topic='load', language='<chosen_language>')` with no
  `record_count`. Omitting it yields the threaded pattern, which is the safe default — a loader that
  is threaded when it need not be merely does extra setup, while one that is single-threaded when it
  should not be is the anti-pattern above. Add a code comment saying no volume selection was found
  and that the production pattern was chosen by default.

Use `generate_scaffold(language='<chosen_language>', workflow='add_records', version='current')` to
see the full set of loading snippets alongside the selected one when it helps to compare.

Do not use inline examples, they may use outdated SDK patterns. Customize the scaffold with
the bootcamper's file path, data source name, and progress reporting. If the scaffold uses
`/tmp/`, `ExampleEnvironment`, or any path outside the working directory, override the database
path to `database/G2C.db` and keep all output files project-relative.

⛔ **Check the scaffold's imports before compiling, not after.** A scaffold may import a package
outside the language's standard library that the environment does not provide — the Java snippets,
for example, import `javax.json` (JSON-P), which plain `javac` does not supply and which this
bootcamp never installs a build tool to fetch. Verify against the actual install rather than
assuming, and resolve it **before** the compile, so the bootcamper never has to diagnose a raw
import error in code they were told was authoritative.

When you resolve it: **replacing the JSON library is safe; altering the SDK calls is not.** Keep
every Senzing method name, signature, and flag exactly as the scaffold has them — that fidelity is
the whole reason to use `generate_scaffold` — swap only the JSON handling (prefer the
dependency-free reader already used for the mappers), and record the substitution in the source
header so the take-home code shows what deviated and why. See
`../module-02-sdk-setup/SKILL.md` → "The launch environment".

The program must include production-quality features:

- **Robust error handling:** per-record error logging with record ID, error code, and message.
  Failed records go to `logs/loading_errors.json` without stopping the load.
- **Progress tracking with throughput reporting:** display progress every N records (e.g. every
  100 or 1000) showing records loaded, error count, elapsed time, and records/second.
- **Statistics reporting:** at completion, report total attempted, loaded, failed, duration,
  throughput, and error summary.
- SDK initialization, record-loading loop, and proper cleanup.

**Save the program** in `src/load/` with a clear name (e.g.
`src/load/load_customer_db.[ext]`).

**Checkpoint:** write step 3.

## 4. Use MCP tools for code generation

Call `generate_scaffold` with workflow `add_records` and the chosen language for version-correct
SDK code. Call `sdk_guide(topic='load', language='<chosen_language>', record_count=<raw_value>)`
for platform-specific loading
patterns — as in step 3, `record_count` belongs to `sdk_guide` and is what selects the threaded
versus single-threaded template.

**Checkpoint:** write step 4.

## 4a. Register the data source codes (before loading)

Register every `DATA_SOURCE` code present in the data about to be loaded into the Senzing
configuration **before** the Phase B load, so the first load does not fail with
`SENZ2207: Data source code [...] does not exist`. Senzing does not auto-create data source
codes — they must be registered in the active config first — and the default config seeded in
Module 2 (SDK setup) knows none of the bootcamper's codes, because the data was collected
afterward (Module 4). This mirrors the register-before-load step that System Verification and the
Truth Set visualization module already run.

1. **Determine the codes to register.** Collect the distinct `DATA_SOURCE` values present in the
   record(s) about to be loaded — from the Senzing-ready JSONL in `data/senzing-ready/` for mapped
   sources, and from the original file in `data/raw/` for `fast_pathed: true` CORD /
   already-Senzing-ready sources — cross-checked against the source's entry in
   `config/data_sources.yaml`. Never register a code that is not present in the data.
2. **Generate the registration code from the MCP server** (never hand-write it): call
   `sdk_guide(topic='configure')` (and `generate_scaffold` if it exposes a data-source
   registration workflow) in the language read from `programming_language` in
   `config/bootcamp_preferences.yaml` (never a hardcoded default). Save it to
   `src/load/register_data_sources.[ext]` (INV-018). The generated code MUST load the current
   default config, register each code from step 1, set the updated config as the new default, and
   be **idempotent** — a code already registered is treated as success, not an error, so re-runs
   and multi-source orchestration stay safe.
3. **Build the registration code if the language requires it** (compiled languages — Java, C#,
   Rust, TypeScript), using the same per-language build command as the loader.
4. **Execute it before the Phase B load.** On success, record the registered codes in
   `config/data_sources.yaml`. On failure, capture the output, call `explain_error_code` for any
   SENZ codes, and report with remediation; the loading program's generic SENZ handling remains a
   fallback.

In Phase C (multiple sources), register each additional source's code the same way before its
load — idempotently, so re-registering an existing code is a no-op.

**Checkpoint:** write step 4a to `config/bootcamp_progress.json`.

## SQLite volume pre-load check (stop-and-confirm heads-up, not a mandatory gate)

Run this once at the end of Phase A, immediately before the Phase B load begins. This is a
stop-and-confirm heads-up, NOT a mandatory gate, the bootcamper may always proceed on SQLite.

1. **Read inputs** from `config/bootcamp_preferences.yaml`: `production_volume.tier`,
   `production_volume.raw_value`, and `database_type` — the last is the key
   `../module-02-sdk-setup/SKILL.md` Step 7 writes when the engine is chosen, valued `sqlite` or
   `postgresql`. If any value is missing/unreadable, treat it as indeterminate, do not fail; fall
   back to the existing advisory behavior and continue to the load.
   - ⛔ **An absent `database_type` is a recording failure, not a non-SQLite answer.** Because
     step 3 prompts only when the database *is* SQLite, a missing key silently disables this
     heads-up entirely. Before treating it as indeterminate, fall back to the engine Module 2
     recorded in `config/bootcamp_progress.json`, and note the gap internally so it reaches the
     recap rather than vanishing.
2. **Decide whether it was already decided.** If a `sqlite_volume_prompt` marker in preferences
   is `decided: true` and its `tier`/`raw_value` match the current selection (or an applicable
   Module 4 SQLite load-time decision covers this same load), skip the prompt and proceed.
3. **Prompt only when it matters.** Present the prompt only when the database is SQLite AND it was
   not already decided AND the volume is production-scale for SQLite — that is, the tier is
   `medium` or `large`, **or** the tier is `small` with a `raw_value` above the SQLite guidance
   threshold. Source that threshold from MCP rather than from this file (a sourcing
   floor); `search_docs(query="loading",
   category="anti_patterns")` → "Do Not Use SQLite in Production" gives it as roughly 100,000
   records ("use SQLite only for quick local testing with small datasets"), well inside the
   `small` tier's span (above 500, up to 500,000), which is why the tier alone is not a sufficient
   trigger. For
   `demo`, a small-tier volume below that threshold, any non-SQLite engine, indeterminate inputs,
   or an already-recorded choice: say nothing new about volume/SQLite and proceed to the Phase B
   load.
4. **When prompting**, explain that SQLite entity resolution slows as the database grows, then end
   the turn on this pinned question (INV-056), verbatim — a neutral lead + numbered list (INV-051) —
   and wait (internal stop); do not start the load yet:

   👉 **Loading this data volume into SQLite may slow entity resolution as the database grows. How would you like to proceed? Reply with a number:**

   1. Proceed on SQLite.
   2. Migrate to PostgreSQL.

   *(Internal: end the turn on this question and wait.)* Then act on the choice:

   - **Proceed on SQLite:** record `sqlite_volume_prompt` = `{decided: true, choice: "proceed",
     tier, raw_value}` in preferences, then continue to the Phase B load. Do not re-present this
     prompt for the same load.
   - **Migrate to PostgreSQL:** record `sqlite_volume_prompt` = `{decided: true, choice:
     "migrate", tier, raw_value}` in preferences, then hand off to the database-migration
     guidance (PostgreSQL migration is a production follow-up; see the graduation migration checklist). Do not restate migration steps here.

*(Internal: when this heads-up fires, end the turn on the pinned question in item 4 and wait.)* Use
only synthetic/persisted values, never echo credentials or connection strings. (No volume,
preferences, load-time, or migration helper is bundled; apply the logic inline and refer to the
graduation migration checklist for PostgreSQL migration.)

Proceed to Phase B (`phaseB-load-first-source.md`).
