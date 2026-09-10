# Model & effort selection (maintainer notes)

This is a maintainer/developer reference — it does not ship as bootcamper-facing
content. It records which Power components can carry a model/effort setting, the
scope of those settings, and a best-value model evaluation for each skill, so the
analysis is not re-investigated.

**The headline:** in Kiro there is no per-skill model or effort override at all,
so the **session** model/effort is not merely the more reliable lever — it is the
only one. Everything the bootcamp does about model selection is therefore a
recommendation the bootcamper acts on, never a setting the Power applies.

## Which components can carry a model/effort setting

A model/effort setting only means anything for components that actually invoke
the model. `type: command` hooks and the scripts they run are deterministic
programs and never "run under a model."

| Component | Model? | Effort? | How / scope |
|---|:---:|:---:|---|
| Skills (`SKILL.md` frontmatter) | ❌ | ❌ | Kiro's supported frontmatter is `name`, `description`, `license`, `compatibility`, `metadata`. No model or effort key exists. |
| The session | ✅ | ✅ | Model selector in the chat input bar, with the **Effort** panel inside it (`low`/`medium`/`high`/`xhigh`/`max`). On the Kiro CLI, `/model` and `/effort`. Persists for the conversation. |
| Sub-agents (`.kiro/agents/`) | ✅ | ❌ | A `model` field in the agent config. There is no `effort` field; effort stays session-level. |
| Command hooks (`type: command`) | ❌ | ❌ | Deterministic program; not model-executed |
| Agent hooks (`type: agent`) | ➖ | ➖ | Appends a prompt to the current context; inherits the session model/effort |
| Scripts (run by hooks) | ❌ | ❌ | Not model-executed |

This Power ships skills, hook definitions, and scripts. It ships no slash
commands: Kiro has no Power-level slash commands, so each of the three
trigger phrases is a skill (`start-bootcamp`, `graduate-bootcamp`,
`bootcamp-feedback`) rather than a command document.

## There is no per-skill override to reach for (the load-bearing constraint)

⚠️ **This is the one place where this Power and the upstream template it was built
from differ in kind, not just in wording.** The template could put `model:` and
`effort:` in a skill's frontmatter — turn-scoped, and so nearly useless for an
interactive multi-turn skill, but present. Kiro's skill frontmatter has no such
key, so the question does not arise:

- Do not add `model:` or `effort:` to any `SKILL.md` in this Power. Kiro does not
  read them, and an unrecognized key is a silent no-op, not an error — which is
  the worst failure mode, because the file looks configured and is not.
- The template's escape hatch for sustained per-skill control (running the skill
  forked into a sub-agent that holds its own model) has no Kiro equivalent for a
  skill, and would be wrong here anyway: the bootcamp skills must converse with
  the bootcamper turn by turn, and a sub-agent's conversation is isolated.
- So the only lever is the **session** model/effort, and only the bootcamper can
  move it. That is exactly why the module-start nudge is a recommendation and a
  question rather than a setting the Power applies — see "Module-start commands"
  below. The guide never changes a dial itself.

## Model tiers (for "best value")

Approximate positioning (verify current pricing/availability before relying on
the numbers — see the staleness note below):

| Model | Tier | ~Price (in/out per MTok) | Adaptive thinking | Notes |
|---|---|---|:---:|---|
| Fable 5 | Top | ~$10 / ~$50 | Always on | Most capable; for long-running agents; slower; ~2× Opus cost |
| Opus 5 | High | ~$5 / ~$25 | Yes | Complex agentic coding default |
| Sonnet 5 | Mid | ~$3 / ~$15 | Yes | Speed/cost/capability sweet spot |
| Haiku 4.5 | Budget | ~$1 / ~$5 | **No** | Fastest; no adaptive thinking |

> **Point-in-time data — re-verify before relying on it.** Model names, IDs, and
> prices above are a snapshot, **last verified 2026-07-25** against the model
> provider's documentation. They go stale whenever a new model ships. Two known triggers:
> Sonnet 5's listed rate is its standard price — an introductory rate applies
> through 2026-08-31, so the effective cost is lower until then; and Opus 5 is
> priced identically to the model it replaced (Opus 4.8, at the same ~$5 / ~$25),
> which will not stay true across future releases. Re-verify names, IDs, and
> pricing against current provider documentation rather than trusting this table.

For a protocol-heavy (⛔ gates, INV-056 pinned wording, one-👉-per-turn),
MCP-first teaching Power, Haiku's lack of adaptive thinking is a real risk of
gate/format slips, and Fable's premium buys little the workloads here need.

## Per-skill best-value evaluation

Best value = the capability the workload needs, at the lowest tier that meets it.

**Re-assessed 2026-07-26.** The original 2026-07-16 evaluation was never re-read against the modules
as they later became, and two rows had gone stale under them. Rows whose value changed are marked
**↑**.

| Skill | Workload | Best value | Rationale |
|---|---|:---:|---|
| `bootcamp-onboarding` | Gated preface, exact-wording gates, preference capture | Sonnet 5, medium | Protocol adherence needs adaptive thinking + strong instruction-following; no heavy code → Opus overkill, Haiku risky |
| `bootcamp-preparation` | Setup preferences: verbosity, language, Core-vs-Customized path, module selection | Sonnet 5, medium | Same workload class as onboarding — pinned questions and recorded answers, no code. The choices steer every later module, so instruction-following matters more than raw capability |
| `module-00-entity-resolution-concepts` | Concepts teaching, Q&A, knowledge check | Sonnet 5, medium | Conversational teaching, no code |
| `module-01-business-problem` | Discovery conversation, document the problem | Sonnet 5, medium | Conversation-led, light technical |
| `module-02-sdk-setup` | Cross-platform install, license/engine/DB config, build-from-source recovery | Opus 5, high | Largest skill, most error-prone, platform-specific; install/config errors are high-cost |
| `module-03-system-verification` | Verify end-to-end, write and run the first real SDK code, report | Sonnet 5, **high** ↑ | Not "run / check / report": it writes the first working SDK code against the installed engine, and the 2026-07-26 export-flag defect was filed against this module. Sonnet fits the volume; the reasoning load justifies high effort |
| `module-03b-truthset-visualization` | **Build** a visualization server in the chosen language, load Truth Set, visualize | **Opus 5, high** ↑ | Rated "mostly run / render" before INV-090 made the module *generate* the server: tab ids and deep-linking (INV-124), script-payload escaping (INV-106), offline vendoring (INV-091), brand tokens (INV-081). The largest code-generation artifact before graduation, and historically the most defect-prone |
| `module-04-data-collection` | Gather sources into `data/raw/` | Sonnet 5, medium | Data wrangling + light code; genuinely the lightest technical module |
| `module-05-data-quality-mapping` | Quality scoring + mapping to the Entity Spec via `mapping_workflow` | Opus 5, high | Mapping correctness drives resolution quality — the technical crux |
| `module-06-data-processing` | Load mapped data (SDK), validate, redo drain, export | **Opus 5, high** ↑ | Was "Sonnet 5 (Opus if bespoke load code)" — a conditional the module-start nudge cannot resolve or pin (INV-056). Its failures are the silent kind: export flag families yielding rows with only `ENTITY_ID`, a redo drain that never terminates, the threading cutover |
| `module-07-query-visualize-discover` | Query SDK code, build the results app, discovery, deliverable | **Opus 5, high** ↑ | Was the lightest setting in the table, and is where the silent-wrongness defects land: three of the 2026-07-26 self-observed entries plus INV-115's originating incident. Wrong field names render blank instead of raising — the failure mode least tolerant of a speed-tuned setting |
| `graduation` | Recap reconcile, PDF, production project (code/config/docs), report | Opus 5, high | Crown-jewel deliverable; production code/config correctness matters most |

Considered and rejected, so they are not re-litigated: **Sonnet 5 / high for Truth Set
visualization** (cheaper, and the contract is explicit — but the module generates a complete app in
an unconstrained language; maintainer settled on Opus 5 / high, 2026-07-26); **`xhigh` for
graduation** (no evidence `high` is insufficient, and a third value on the dial adds a change point
and a vocabulary the rest of the table does not use); and **flattening the table to reduce prompts**
(the assignment should describe the work — prompt volume is a detection problem, solved by comparing
against the bootcamper's actual setting).

## Module-start commands (the nudge)

`ground-rules.md` → "Module start banners and transitions" surfaces this per-stage recommendation
at the start of each module (and `graduation/SKILL.md` at the graduation banner). Switching is
optional; the session-level model/effort persists for the conversation, and the guide never
changes it — only the bootcamper can, because there is no other lever.

**How it is surfaced is not configurable** (INV-137). The bootcamper is never asked, there is no
`model_guidance` preference, and the behavior depends only on whether the recommendation differs
from **what the bootcamper is currently running** — not from the previous stage's recommendation.
That distinction is the whole point: a bootcamper who runs Opus 5 / high throughout (a supported
choice, see below) was previously asked to "switch to Opus 5 / high" three times while already on
it. Where the current setting cannot be determined, fall back to the previous stage's value — **per
dial**, and only while it really cannot be read. Reasoning effort is not exposed by default, which is
not the same as unreadable: on the Kiro CLI an `/effort` invocation reports the resulting level
in the transcript, and the nudge's own switch flow asks the bootcamper to run exactly that command. So
once an `/effort` result is in the conversation the effort dial is determinable and the fallback must
not be used for it. (On Kiro, the web app and IDE extensions there is no such command, so
the dial may genuinely stay undeterminable; both paths are live.)

| At a module or graduation start | Behavior | Extra turns |
|---|---|---|
| The recommendation **differs** from the current setting — in **either** direction | A single 👉 switch question, its own turn, naming only the dial that differs — **in the answer hint too**, which resolves to "model", "effort", or "model and effort" rather than always saying "model"; on **yes**, the reply reads the dial first (INV-236) — if it is not yet set, a one-line run-commands statement then the pinned "Are you done modifying the model and effort?" gate before the first step; if the bootcamper has already set it (the question names a command, so this is common), the reply states what is in force, skips the gate, and the first step lands the same turn, never re-instructing a value they have already moved past; on **no**, the first step lands the same turn. A recommendation *below* the current setting is flagged as a step down **in the question**, stating it is a cost saving rather than a capability the module needs. | up to 2 |
| The recommendation **matches** what they are already running | A concise one-line statement — model and effort named as separate dials, either changeable at any time from the next message, and a recommendation *below* the current setting flagged explicitly so it never reads as advice to downgrade. | 0 |
| Effort is **above every row** in the table (`xhigh`, `max`) | Treated as satisfied: the one-line statement, naming the stage's recommendation and saying that running higher is fine. No question — the step-down clause would otherwise fire at every remaining module, and answering it cannot make it stop. Model has no equivalent case today only because Opus 5 is the top row. | 0 |

The pause is **symmetric**: downgrades ask exactly as upgrades do (maintainer decision, 2026-07-26).
Making a step down a statement instead of a question was considered — running heavier than
recommended is never harmful, only more expensive — and rejected: the choice is the bootcamper's in
both directions.

An earlier design made this a three-mode `model_guidance` preference (`advisory` / `off` /
`prompt`) chosen in Bootcamp preparation. That question and preference are **retired**: INV-137
supersedes INV-119 and INV-120 and restores the unconditional INV-063/INV-069 behavior. A stale
`model_guidance` key in an old preferences file is ignored, not honored. The confirmation gate
follows a **yes** to the switch and nothing else.

> **`ground-rules.md` is the authoritative copy of this table; the copy below is derived.**
> `ground-rules.md` is the file the guide actually loads at module start, so the operational values
> must live there — a nudge that first had to fetch this maintainer doc could silently misfire, and
> INV-063 mandates the nudge. Change `ground-rules.md` first, then mirror it here.
>
> The two are not kept in sync by hand: `tests/test_model_guidance_sync.py` asserts they are
> identical row for row, that no superseded model name or ID appears in any shipped or
> user-facing doc, and that this file carries a dated verification note (INV-114). Editing one
> table without the other fails the suite.

The nudge adapts to the Kiro surface in use (INV-098): the **Recommended** column is
interface-neutral; the **Where to set it in Kiro** column is the Kiro CLI equivalent. In Kiro,
Kiro on the web, or the Kiro IDE, the same model and reasoning effort are set via that
interface's model/effort controls rather than the slash commands. Each is named explicitly, because
the retired "the Kiro app" did not say which controls were meant (INV-158).

**One row per stage, in the order the bootcamp runs them** — so the next stage's recommendation can
be read off directly, and so no stage is ever missing a value to compare against. Each row names
exactly one model and one effort: a conditional cell cannot be pinned into a verbatim question
(INV-056) and gives the comparison two answers.

⚠️ **The effort values are a recommended floor for value, not a ceiling.** The table stops at `high`;
the dial continues to `xhigh` and `max`. Running above the table is in policy and simply costs more.
That matters to the nudge: an effort above **every** row is exempt from the comparison and produces a
statement rather than a question, because otherwise the step-down clause fires at every remaining
module and cannot be resolved by answering it. The exemption is confined to *above the whole table* —
step downs **within** it stay symmetric with step-ups, per the 2026-07-26 decision below.

Every stage the bootcamp can run has **exactly one** row here, including the apparatus-exempt setup
stages that present no nudge themselves — INV-140, so the INV-138 comparison always has a defined
value to compare against.

| Stage | Recommended | Where to set it in Kiro |
|---|---|---|
| Onboarding | Sonnet 5, medium effort | Sonnet 5 in the model picker · medium in the effort picker |
| Bootcamp preparation | Sonnet 5, medium effort | Sonnet 5 in the model picker · medium in the effort picker |
| Entity Resolution Concepts | Sonnet 5, medium effort | Sonnet 5 in the model picker · medium in the effort picker |
| Discover the Business Problem | Sonnet 5, medium effort | Sonnet 5 in the model picker · medium in the effort picker |
| SDK setup | Opus 5, high effort | Opus 5 in the model picker · high in the effort picker |
| System verification | Sonnet 5, high effort | Sonnet 5 in the model picker · high in the effort picker |
| Truth Set visualization | Opus 5, high effort | Opus 5 in the model picker · high in the effort picker |
| Data collection | Sonnet 5, medium effort | Sonnet 5 in the model picker · medium in the effort picker |
| Data Quality, Mapping, and Transformation | Opus 5, high effort | Opus 5 in the model picker · high in the effort picker |
| Data processing | Opus 5, high effort | Opus 5 in the model picker · high in the effort picker |
| Query, Visualize and Discover | Opus 5, high effort | Opus 5 in the model picker · high in the effort picker |
| Bootcamp graduation | Opus 5, high effort | Opus 5 in the model picker · high in the effort picker |

## Recommendation

There is no per-skill setting to realize the evaluation with, so it is realized
through the **session** model and effort, which only the bootcamper can set:

- **Value-optimized (the `README.md` default):** run the session on **Sonnet 5**,
  and switch the session up to **Opus 5** for the correctness-critical stretches —
  SDK setup, Truth Set visualization, and the whole back half from Data Quality,
  Mapping, and Transformation through graduation, which is flat at Opus 5 / high.
  Switch mid-session by picking Opus 5 in the model selector and back with
  Sonnet 5. **Haiku 4.5** is not recommended for any bootcamper-facing skill
  (protocol risk); **Fable 5** is not the value pick here.
- **Simplest (one model, no switching):** run the whole session on **Opus 5** at
  **high** effort. Zero-friction — one strong model for everything — at the cost
  of over-paying on the lighter conversational modules.

## Considered and rejected: a per-skill effort bump

The template could raise reasoning effort for the turn that *invokes* a heavy
skill (`graduation`, `module-02-sdk-setup`, `module-05-data-quality-mapping`) by
putting `effort:` in that skill's frontmatter. It was never wired there, because
turn-scoped effort implies a persistence the mechanism did not provide.

In Kiro the option does not exist to reject: skill frontmatter has no `effort`
key. This section is kept only so the idea is not re-proposed as though it were
available.

## Sources

- Skill frontmatter (the supported field set): <https://kiro.dev/docs/skills/>.
- Powers (component set, `plugin.json`, `mcp.json`): <https://kiro.dev/docs/powers/>.
- Hook triggers: <https://kiro.dev/docs/hooks/>.
- Reasoning effort and the model selector: <https://kiro.dev/docs/models/effort/>.
- Kiro CLI slash commands (`/model`, `/effort`, `/compact`):
  <https://kiro.dev/docs/reference/slash-commands/>.
- Sub-agent configuration (`model`, and the absence of `effort`):
  <https://kiro.dev/docs/custom-agents/configuration-reference/>.
- Model positioning/pricing: the model provider's current published pricing.
