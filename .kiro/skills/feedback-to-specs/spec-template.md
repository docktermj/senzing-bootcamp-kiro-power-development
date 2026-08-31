# Spec templates

A generated spec is a **Kiro spec directory**, not a single file. Create
`.kiro/specs/<kebab-case-title>/` holding four files, matching the shape this
repository and its sibling repositories already use:

| `specType` | Documents |
|---|---|
| `bugfix` | `.config.kiro`, `bugfix.md`, `design.md`, `tasks.md` |
| `feature` | `.config.kiro`, `requirements.md`, `design.md`, `tasks.md` |

Use `bugfix` when the Power does something wrong, `feature` when it does not yet do
something. Both carry the same `## Source` and `## Fix routing` blocks — those are what
make a spec traceable back to a bootcamper and forward to a place a change can land.

## `.config.kiro`

```json
{"specId": "<uuid4>", "workflowType": "requirements-first", "specType": "<bugfix|feature>"}
```

Generate a fresh `uuid4` per spec (`python3 -c "import uuid; print(uuid.uuid4())"`).
Never reuse another spec's `specId`.

## ⛔ `## Fix routing` — the block that does not exist in the Claude original

`powers/senzing-bootcamp/` is **generated output.** It is produced from an upstream
template release by `tools/bootcamp-transform/`, and
`test_the_committed_power_equals_a_fresh_build_of_its_recorded_release` asserts the
committed tree is byte-identical to a fresh build. A spec that says "edit
`powers/senzing-bootcamp/skills/…`" describes a change that the next rebuild deletes and
that the test suite rejects before then.

So every spec MUST name which of five homes its change belongs to, and there is exactly
one right answer per change:

| Home | When | What arrives, and how |
|---|---|---|
| `upstream-template` | the defect is in content the Power ports verbatim, and it is wrong for Claude too | a request to `Senzing/senzing-bootcamp-claude-plugin`; lands here on a future Template_Release |
| `contract` | ported content is right upstream but wrong **for Kiro** | a rule or substitution set in `tools/bootcamp-transform/contract.yaml`; lands by rebuild |
| `kiro-owned` | the content has no upstream counterpart, or its subject is Kiro itself | authored files under `tools/bootcamp-transform/templates/kiro-owned/`; lands by rebuild |
| `engine` | the transformation itself is wrong | `tools/bootcamp-transform/*.py`; lands by rebuild |
| `mcp-server` | the current Senzing MCP server is what is wrong | `submit_feedback` (Step 8); lands on a future server release |

A single entry can need two: a server defect the Power must also stop repeating is
`mcp-server` **and** `contract`. Say both.

⛔ **`powers/senzing-bootcamp/` is never a value.** If the change seems to belong there,
the real home is whichever of the five *produces* that file — find it in the
`.build-manifest.json` entry for the path (`ruleId` and `owner` name it exactly) and route
there instead.

## ⛔ Asserting the server LACKS something requires `owner-checked:`

Where a spec's diagnosis rests on absence — "returns no X", "does not cover", "no MCP tool
answers this" — the `MCP re-check` line MUST also carry
`owner-checked: <the route that would CARRY this fact> — <what it returned>`.

**The tools you asked and found empty are not evidence for the negative.** They are true
statements about those tools. "`sdk_guide(topic='configure')` returns no license variable"
is correct and worthless as support for "no license variable exists" — the variable lives
in `sdk_guide(topic='load', record_count=<above the limit>)`. Exempt: a line declaring
`n/a (no Senzing fact)`.

⚠️ Unlike the Claude repository, **no test enforces this clause here.** There is no
equivalent of its `test_spec_absence_claims_name_their_owner.py`. Until one exists the rule
rests on attention, which the Claude repo learned the hard way is not sufficient — so treat
a missing `owner-checked:` on an absence claim as a defect in the spec, and say so in the
Step 10 report rather than letting it pass.

---

## `bugfix.md`

```markdown
# Bugfix Requirements Document

## Introduction

<What the bootcamper experienced, and what it cost them. Include the verbatim
error/output when the feedback provided one — it is the clearest repro signal.>

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN <condition> THEN the system <observable wrong behavior>, because <confirmed
    cause, citing file:line in the tree that PRODUCES the shipped file>.

### Expected Behavior (Correct)

2.1 WHEN <condition> THEN the system SHALL <observable correct behavior>.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN <adjacent condition> THEN the system SHALL CONTINUE TO <behavior that must
    not move>.

## Root cause

<The confirmed cause, grounded in code, citing `file:line`. Cite the SOURCE of the
shipped bytes — a contract rule, an authored kiro-owned file, an engine function, or the
upstream template path named in `.build-manifest.json` — not the generated file. If
unconfirmed, write "Unverified — needs investigation" and list what to check.>

<Where the item involves Senzing behavior, state what the LIVE MCP server returned at
triage time and how it bears on the cause: the tool and parameters, a quote of the
result, the server version and the date. Where the server and the feedback disagree,
give both with their conditions (flag set, SDK version, binding, platform) and say which
governs — never flatten them into one absolute. Mark anything the server cannot reach as
observation-only.>

## Fix routing

- **Home:** <upstream-template | contract | kiro-owned | engine | mcp-server> (one or two)
- **Why this home:** <one line — what would go wrong if it landed in another>
- **Arrives by:** <rebuild | future Template_Release | future server release>
- **Manifest evidence:** `<power-relative path>` → `ruleId: <id>`, `owner: <template|kiro>`

## Source

- Feedback: `<archived path>` → "<entry title>" (<date>, Module <n>; `Source: <bootcamper-reported | self-observed (assistant retrospective)>`)
- Entry id: `<16-hex>`
- Priority: <High | Medium | Low | pending>
- Routing verdict: <plugin | mcp-server | both | host | unclear>
- MCP re-check: <server version + date, and the outcome — still reproduces | fixed upstream | server now contradicts the Power | server does not cover it | n/a (no Senzing fact) | unverified (MCP unreachable). Name the tools called. For any absence claim, ALSO add `owner-checked: <route> — <result>`.>
- Upstream: <not applicable | already sent <date> (per the entry) | sent <date> via `submit_feedback` (`<category>`, anonymous) | declined by the maintainer>
- Related specs: <.kiro/specs/<name>/, or "none">
```

## `requirements.md`

```markdown
# Requirements Document

## Introduction

<What is missing, who noticed, and why it matters. Same Source/MCP grounding rules as
`bugfix.md`.>

## Requirements

### Requirement 1: <short title>

**User Story:** As a <Bootcamper | Maintainer>, I want <capability>, so that <outcome>.

#### Acceptance Criteria

1. WHEN <trigger> THEN THE <component> SHALL <observable outcome>.
2. IF <error condition> THEN THE <component> SHALL <observable response>.
3. THE <component> SHALL <invariant that must hold on Linux, macOS, and Windows>.

## Fix routing

<Same block as bugfix.md.>

## Source

<Same block as bugfix.md.>
```

Match this repository's existing EARS phrasing (`WHEN … THEN … SHALL`, `IF … THEN …
SHALL`, `WHERE … THE … SHALL`) — see `.kiro/specs/senzing-bootcamp-power/requirements.md`.

## `design.md`

```markdown
# Design Document

## Overview

<One paragraph: what changes, in which home, and what stays fixed.>

## Approach

<The change, concretely. For `contract`: the rule or substitution set, its entries, and
where it sits in the per-rule set order — ordering is load-bearing, since a set is one
left-to-right pass in which the earliest match wins. For `kiro-owned`: the authored file
and what supersedes the template's version. For `engine`: the function and its guard.>

## Constraints this must respect

- <Requirement ids from `.kiro/specs/senzing-bootcamp-power/requirements.md` this touches.>
- No substitution may target or write an `INV-NNN` citation, or name an interpreter or a
  Hook_Command_String placeholder. <Say how this design stays inside that, or "n/a".>
- The committed Power must remain byte-identical to a fresh build.

## Verification

<How the change is proven: the rebuild-and-diff, which tests cover it, and which
Test_Checklist step (if any) has to be re-run.>
```

## `tasks.md`

```markdown
# Implementation Plan

- [ ] 1. <First change, in its routed home>
  - <Concrete edit: file, rule id, entry>
  - _Requirements: <ids>_

- [ ] 2. Rebuild and prove the Power still matches a fresh build
  - `python3 tools/bootcamp-transform/transform.py --source <tree> --tag <tag> --staging powers/.senzing-bootcamp.staging`
  - Diff the staging tree against `powers/senzing-bootcamp/`; explain every difference
  - `python3 tools/bootcamp-transform/validate.py --staging powers/.senzing-bootcamp.staging --tag <tag> --source <tree> --report docs/test-records/<tag>-validation.json`
  - _Requirements: <ids>_

- [ ] 3. Run the suite
  - `python3 -m pytest --no-header -q`
  - _Requirements: <ids>_
```

Leave every box unchecked: this skill writes specs, it does not implement them.
