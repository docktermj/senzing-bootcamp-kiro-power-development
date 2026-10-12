---
name: feedback-to-issues
description: 'Triage a collected Senzing Bootcamp Power feedback file into GitHub issues: re-verify every Senzing fact against the live MCP server, classify each item parent-bound or local and show the decision per item, hand parent-bound curriculum problems to escalate-to-parent, file local port problems as issues in this repository, report server defects to Senzing, and archive via the ledger. Use when the maintainer wants to process SENZING_BOOTCAMP_POWER_FEEDBACK.md, triage bootcamper feedback, or turn collected feedback into tracked issues. Maintainer tool for developing this repository — not part of the bootcamper experience and never ported into the Power.'
license: 'Apache-2.0'
---

# Feedback → Issues

This is a **maintainer** tool for developing the Senzing Bootcamp Kiro Power, and the **only**
front door for bootcamp feedback. It reads a collected feedback file, re-verifies each item against
the live Senzing MCP server, **triages** it, and routes it — filing local **GitHub issues** for port
problems and handing curriculum problems to `escalate-to-parent`. It does **not** implement
anything; `implement-github-issue` does that.

It is unrelated to the bootcamper-facing feedback flow
(`powers/senzing-bootcamp/skills/bootcamp-onboarding/feedback.md`), which only *captures* feedback.
This skill *consumes* what that flow captured.

⛔ **It writes no spec file** (KINV-014). Work is tracked as GitHub issues, family-wide (R5). The
spec-writing router that once shared this job, `feedback-to-specs`, was retired in #25; its ledger
and its absence-claim gate moved here.

## The boundary it honors

- **It never files into another repository.** `escalate-to-parent` is the single owner of
  cross-repo issue filing; parent-bound items are handed to it, not filed upstream from here.
- **It writes local issues only for genuine port problems**, and it shows the parent-bound /
  local / server decision **for every item**, never silently.
- **It writes only under `docs/feedback/`** — the archive and the ledger. Never the Power, the
  contract, the engine, or the templates. Never edit the content of a feedback file.

## Invocation

`/feedback-to-issues`, or `/feedback-to-issues <path/to/feedback.md>`. Anything after the command
arrives as `$ARGUMENTS`: a candidate path when it looks like one, scoping instructions otherwise.

## Steps

### 1. Locate and de-duplicate

Resolution and identity are code, not judgement:

```bash
python3 .kiro/skills/feedback-to-issues/feedback_ledger.py find
python3 .kiro/skills/feedback-to-issues/feedback_ledger.py check <candidate.md>
```

`find` resolves `SENZING_BOOTCAMP_POWER_FEEDBACK.md` at the repo root or under `docs/`, skipping
the archive and any `*_DUPLICATE.md`, and refuses `SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md` by name —
that file belongs to the Claude plugin's own repository. An explicit path in `$ARGUMENTS` wins.

`check` identifies entries by content hash after normalization (BOM, CRLF and blank runs do not
make an entry new; a reworded entry is new) and exits **0** when some are new, **3** when all were
processed, **1** on bad input:

- **NEW** → triage the whole file.
- **PARTIAL** → triage only the new entries, and name the known ones in the report with the issue
  each produced.
- **DUPLICATE** → stop, file nothing, run `commit` (which renames the file in place to
  `…_<unixtime>_DUPLICATE.md` and leaves the ledger untouched), and report only that.

### 2. Parse the entries

Parse the `## Improvement:` blocks into `title`, `symptom` (verbatim output included), `impact`,
`suggested_fix`, `priority`, `module`, `date`, `source`, and any routing verdict the
bootcamper-facing flow recorded (`plugin` / `mcp-server` / `both` / `host` / `unclear`). Handle
free-form prose too. Never invent feedback; an entry too vague to act on is *needs clarification*.

`Source: self-observed (assistant retrospective)` entries skew toward the defects a bootcamper
cannot report — silently wrong output, a tool behaving differently than documented. Do not rank
them lower by default.

### 3. Re-verify every Senzing fact against the live MCP server

Feedback is a snapshot; the server is released independently. Record the server version once
(`get_capabilities`), then re-ask the tool that **owns** each fact:

| The entry claims something about… | Re-ask |
|---|---|
| an SDK method, its arguments, or its response shape | `get_sdk_reference(topic='parameters' \| 'response_schemas', filter='<method>', language='<binding>')` |
| a flag, what it applies to, or what it returns | `get_sdk_reference(topic='flags', filter='<FLAG_NAME>')` |
| an attribute or mapping rule | `search_docs(query='…', category='data_mapping')` |
| an error code or its symptom | `explain_error_code('<SENZnnnn>')` |
| export, reporting, evaluation or graph behavior | `reporting_guide(topic='…')` |
| install, configuration or platform paths | `sdk_guide(topic='install' \| 'configure', platform='…')` |
| an example file or repository | `find_examples(...)` |

Three outcomes change what the issue says: **still reproduces**; **fixed upstream** (file no
workaround — and if the Power carries one, the issue is its removal); **the server now contradicts
the Power** (the Power is what is wrong). Quote what the server returned. Where the server cannot
reach a fact, mark it observation-only with its version and date. If the server is unreachable,
mark the fact unverified and say so; never fall back to training data.

⛔ **An absence claim names the route that would carry the fact** (the parent's INV-213): "tool X
returns no Y" is evidence about tool X, not that Y does not exist. Write it on the issue's
`MCP re-check` line as `owner-checked: <route> — <what it returned>`, or declare
`n/a (no Senzing fact)`. Step 5 checks this mechanically.

### 4. Triage each item, and show the verdict

Confirm the root cause in the **producing source**, not the generated Power — look the shipped path
up in `powers/senzing-bootcamp/.build-manifest.json` for its `ruleId` / `owner` / `sourcePath`
(`docs/porting-framework.md` maps the components). Then route, recording the decision for every item:

- **Parent-bound (curriculum).** What the bootcamp teaches, asks, or does, independent of Kiro
  packaging — it reproduces on the parent. **Hand it to `escalate-to-parent`.**
- **Senzing server defect.** The current server is what is wrong. Report it with `submit_feedback`
  (below). A `host` verdict has no upstream channel and is never sent.
- **Local port problem.** The home is `contract`, `kiro-owned`, or `engine`. File it here (Step 5).
- **Unclear.** *Needs clarification*; file nothing.

An item can be both: a curriculum problem the port also repeats gets an escalation **and** a local
issue for the part the port owns, cross-referenced. Deduplicate first:
`gh issue list --repo docktermj/senzing-bootcamp-kiro-power-development --state all --search "<terms>"`.

### 5. File the local issues

Draft each body to a file **outside** the repository with: the symptom, the module and step, the
manifest triple naming the home, a source block carrying `- Feedback: <archive path> → "<title>"`,
`- Entry id:` and `- MCP re-check:` lines, and observable acceptance including that any
`contract`/`kiro-owned`/`engine` change reproduces on a fresh build. Then gate it:

```bash
python3 .kiro/skills/feedback-to-issues/issue_body_check.py <body.md>
```

Exit 1 names the unsubstantiated absence claim; fix the body, not the gate. Show the maintainer the
title and body and get a yes, then
`gh issue create --repo docktermj/senzing-bootcamp-kiro-power-development --title "<…>" --body-file <body.md>`.
Never apply the fix here.

**Upstream, for a confirmed server defect:** draft a self-contained technical report — tool and
parameters, what came back, what was expected, server version, a minimal reproduction — with
everything identifying stripped (no name, employer, paths, host names, data values). Show the exact
message and get an explicit yes, then `submit_feedback(category='bug' | 'feature', message=…)`.
⛔ Never `category='license_request'`. Check the entry's `Upstream:` field first; do not re-send.

### 6. Archive and record dispositions

Only after the issues are filed and any escalation and upstream report are settled:

```bash
python3 .kiro/skills/feedback-to-issues/feedback_ledger.py commit <candidate.md> \
  --disposition "<title>=<local issue URL>" \
  --disposition "<title>=escalated:<parent issue URL>" \
  --disposition "<title>=already-tracked:<issue URL>" \
  --disposition "<title>=needs-clarification"
```

It moves the file to `docs/feedback/SENZING_BOOTCAMP_POWER_FEEDBACK_<unixtime>.md` and appends one
line per newly processed entry to `docs/feedback/PROCESSED.jsonl`. Pass a disposition for every
triaged entry. The ledger is append-only and read last-wins: correct a disposition with
`feedback_ledger.py annotate <entry_id> "<disposition>"`, never by editing a line. The archive is
committed, so bootcamper text enters history; confirm with the maintainer before the first archive.

### 7. Report the triage

State the server version, then one row per item: classification, MCP re-check outcome, fix home,
and the action (local issue URL, `escalated → <parent URL>`, `submit_feedback` sent/declined,
already-tracked, needs clarification). Name what was skipped as already processed and where the
file went. Call out anything the re-check changed. Offer `implement-github-issue` for a filed issue;
do not start implementing unless asked.
