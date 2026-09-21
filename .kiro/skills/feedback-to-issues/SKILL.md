---
name: feedback-to-issues
description: 'Triage a collected Senzing Bootcamp Power feedback file into GitHub issues: re-verify every Senzing fact against the live MCP server, classify each item parent-bound or local and show the decision per item, hand parent-bound curriculum problems to escalate-to-parent, file local port problems as issues in this repository, report server defects to Senzing, and archive via the shared ledger. Use when the maintainer wants to turn collected bootcamper feedback into tracked issues. Maintainer tool for developing this repository — not part of the bootcamper experience and never ported into the Power.'
license: 'Apache-2.0'
---

# Feedback → Issues

This is a **maintainer** tool for developing the Senzing Bootcamp Kiro Power, and the
**issue-driven front door** for bootcamp feedback. It reads a collected feedback file,
re-verifies each item against the live Senzing MCP server, **triages** it, and routes it —
filing local **GitHub issues** for port problems and handing curriculum problems to
`escalate-to-parent`. It does **not** implement anything; `implement-github-issue` does that.

## The boundary it honors

- **It never files into another repository.** `escalate-to-parent` is the single owner of
  cross-repo issue filing; parent-bound items are handed to it, not filed here or upstream by
  this skill.
- **It writes local issues only for genuine port problems**, and it shows the parent-bound /
  local / server decision **for every item**, never silently.

## Relationship to feedback-to-specs, and the shared ledger

`feedback-to-issues` and `feedback-to-specs` are two outputs of one triage. This skill files
tracked issues (the issue-driven model this framework uses); `feedback-to-specs` writes a full
spec under `.kiro/specs/` for a local item that warrants a design before implementation. They
consume the **same** feedback file (`docs/feedback/SENZING_BOOTCAMP_POWER_FEEDBACK.md`) and
share the **same** append-only ledger (`docs/feedback/PROCESSED.jsonl`) through
`feedback_ledger.py`, so an entry is processed **once** regardless of which router handled it.
Use this skill as the default front door; escalate a local item to `feedback-to-specs` when a
GitHub issue is too thin for the design it needs. Whether to consolidate the two into one
router is a maintainer decision, not made here.

## Steps

### 1. Locate and de-duplicate — reuse the shared ledger helper

Do not re-implement resolution or identity; the ledger is shared with `feedback-to-specs` so
the two never double-process an entry. Run the same helper it uses:

```bash
python3 .kiro/skills/feedback-to-specs/feedback_ledger.py find
python3 .kiro/skills/feedback-to-specs/feedback_ledger.py check <candidate.md>
```

`find` resolves `SENZING_BOOTCAMP_POWER_FEEDBACK.md` (skipping the archive and any
`*_DUPLICATE.md`) and refuses the plugin's `SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md` by name.
`check` reports each entry as NEW / PARTIAL / DUPLICATE. Act on the verdict exactly as
`feedback-to-specs` Step 3 describes: triage NEW/PARTIAL entries only, and on DUPLICATE stop,
`commit` the rename, and report. An explicit path in `$ARGUMENTS` wins over `find`.

### 2. Parse the entries

Parse the `## Improvement:` blocks into `title`, `symptom`, `impact`, `suggested_fix`,
`priority`, `module`, `date`, `source`, and any routing verdict the bootcamper-facing flow
recorded (`plugin` / `mcp-server` / `both` / `host` / `unclear`) — the same shape
`feedback-to-specs` Step 2 defines. Never invent feedback; an entry too vague to act on is
marked *needs clarification* rather than guessed.

### 3. Re-verify every Senzing fact against the live MCP server

Before asserting any Senzing fact in an issue, re-ask the tool that owns it, exactly as
`feedback-to-specs` Step 5 prescribes (that step's tool table and rules are the authority —
follow it rather than a second copy here). Record the server version once. The three outcomes
— still reproduces, fixed upstream, server now contradicts the Power — change what the issue
should say, and a fact the server cannot confirm is marked observation-only, never laundered
into an MCP-sourced claim. If the MCP server is unreachable, mark the fact unverified and say
so; do not fall back to training data.

### 4. Triage each item, and show the verdict

Confirm the root cause in the **producing source**, not the generated Power — look the shipped
path up in `powers/senzing-bootcamp/.build-manifest.json` for its `ruleId`/`owner`/`sourcePath`
home (`docs/porting-framework.md` maps the components). Then route, recording the decision for
every item:

- **Parent-bound (curriculum).** The problem is what the bootcamp teaches, asks, or does,
  independent of Kiro packaging — it reproduces on the parent. **Hand it to
  `escalate-to-parent`**, which files the upstream issue and records the two-way
  cross-reference. Do not file it locally and do not file it upstream from here.
- **Senzing server defect.** The current server is what is wrong. Report it to Senzing with
  `submit_feedback` (the discipline and consent gate are in `feedback-to-specs` Step 8) — a
  different upstream, not a GitHub issue and not cross-repo. A `host` verdict has no upstream
  channel and is never sent.
- **Local port problem.** The fix's home is `contract`, `kiro-owned`, or `engine`. **File a
  GitHub issue in this repository** (Step 5).
- **Unclear.** Mark *needs clarification*; file nothing.

An item can be both: a curriculum problem the port also repeats gets an escalation **and** a
local issue for the part the port owns, cross-referenced.

### 5. File the local issues

For each local port problem, `gh issue create --repo docktermj/senzing-bootcamp-kiro-power-development`
(REST API otherwise) with: the symptom, the module/step, the fix-home routing evidence (the
`.build-manifest.json` triple), the re-verified Senzing facts with provenance (tool, server
version, date), and observable acceptance including that any `contract`/`kiro-owned`/`engine`
change reproduces on a fresh build. These issues are what `implement-github-issue` later
implements. Never apply the fix here — this skill triages and files, it does not implement.

### 6. Archive and record dispositions in the shared ledger

Only after the issues are filed and any escalation and `submit_feedback` are settled:

```bash
python3 .kiro/skills/feedback-to-specs/feedback_ledger.py commit <candidate.md> \
  --disposition "<title>=<local issue URL>" \
  --disposition "<title>=escalated:<parent issue URL>" \
  --disposition "<title>=already-tracked" \
  --disposition "<title>=needs-clarification"
```

Pass a disposition for every triaged entry — the disposition is the durable link from an
entry to the issue (or escalation) it produced. The ledger is append-only and read
last-wins; correct a wrong disposition by appending (`annotate`), never by editing a line.

## Step 7: Report the triage

State the server version every re-check ran against, then a compact table — one row per item
with its classification, MCP re-check outcome, fix home, and the action taken (local issue URL,
`escalated → <parent URL>`, `submit_feedback` sent/declined, already-tracked, or needs
clarification). Name what was skipped as already-processed and where the file went. Call out
anything the re-check changed and any item whose home is `upstream-template`, since that is the
one class that does not arrive by rebuild. Offer to implement a filed local issue with
`implement-github-issue` next; do not start implementing unless asked.
