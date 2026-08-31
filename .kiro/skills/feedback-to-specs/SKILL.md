---
name: feedback-to-specs
description: 'Analyze a Senzing Bootcamp Power feedback file and turn it into one or more Kiro specs under .kiro/specs/, re-verifying every Senzing fact against the live Senzing MCP server first, routing each fix to the place that actually produces the shipped file, reporting confirmed server-side defects upstream via submit_feedback, and archiving the processed file. Use when the maintainer wants to process SENZING_BOOTCAMP_POWER_FEEDBACK.md, triage bootcamper feedback, or generate specs from collected feedback. Maintainer tool for developing this repository — not part of the bootcamper experience and never ported into the Power.'
license: 'Apache-2.0'
---

# Feedback → Specs

This is a **maintainer** tool for developing the Senzing Bootcamp Kiro Power. It reads a
feedback file collected during a bootcamp, analyzes and triages each item against the
**source that produces the Power**, the **live Senzing MCP server** and the existing specs,
writes **one or more Kiro specs** into `.kiro/specs/`, and archives the processed file. It
does **not** implement the fixes — it turns raw feedback into actionable, deduplicated
specs a developer (or a follow-up session) can act on.

It is unrelated to the bootcamper-facing feedback flow
(`powers/senzing-bootcamp/skills/bootcamp-onboarding/feedback.md`), which only *captures*
feedback. This skill *consumes* what that flow captured.

**Feedback is a snapshot; the server is not.** Every entry records how Senzing and its MCP
server behaved on the day it was written, and the server is released independently of this
Power. So triage always re-asks the server before writing (Step 5): a defect may already be
fixed, a claim may have been wrong all along, or the server may now contradict guidance the
Power still ships. Where the current server is itself the defect, the finding goes back to
Senzing (Step 8).

## Invocation

`/feedback-to-specs` — or `/feedback-to-specs <path/to/feedback.md>` to name the file
explicitly instead of letting Step 1 resolve it.

Anything passed after the command arrives as: `$ARGUMENTS`

Treat it as a candidate path when it looks like one, and as scoping instructions otherwise
(for example "only the Module 5 entries"). Empty means resolve normally.

**Reaching the Senzing MCP server.** The tools Step 5 and Step 8 name — `get_capabilities`,
`get_sdk_reference`, `search_docs`, `explain_error_code`, `sdk_guide`, `reporting_guide`,
`find_examples`, `submit_feedback` — are served by the `senzing` MCP server that the
`senzing-bootcamp` Power declares in its `mcp.json`. This repository configures no MCP
server of its own, so they are available only while that Power is installed. If they are
not reachable, that is the "MCP unreachable" branch in Step 5, not a reason to guess.

## ⛔ The constraint that shapes every spec this skill writes

**`powers/senzing-bootcamp/` is generated output. Never propose editing it, and never edit
it.** It is produced from an upstream Template_Release by `tools/bootcamp-transform/`
according to `contract.yaml`, and
`test_the_committed_power_equals_a_fresh_build_of_its_recorded_release` asserts the
committed tree is byte-identical to a fresh build. A change made there is deleted by the
next rebuild and rejected by the suite before then.

Every fix therefore has exactly one real home, and the spec must name it — see
`## Fix routing` in `spec-template.md`:

`upstream-template` · `contract` · `kiro-owned` · `engine` · `mcp-server`

Find the home from evidence, not from where the symptom appeared: look the shipped path up
in `powers/senzing-bootcamp/.build-manifest.json`, whose entry for it carries `ruleId`,
`owner` (`template` or `kiro`) and `sourcePath`. That triple names the producing home
exactly. Quote it in the spec.

## Scope and guardrails

- **Write only under `.kiro/specs/` and `docs/feedback/`.** Never modify the Power, the
  contract, the engine, or the templates — generating specs is the deliverable, and
  implementing them is a separate, later step. Exactly three actions reach outside
  `.kiro/specs/`: the archive and ledger append (Step 9), renaming a duplicate candidate in
  place (Step 3), and the upstream notification in Step 8 — an MCP call, not a file write,
  gated on the maintainer's explicit yes. **Never edit the content of a feedback file**,
  archived or not; the archive is a record.
- **Never process the same entry twice.** Identity is per entry and content-addressed
  (Step 3). A file whose entries are all in the ledger is a duplicate: rename it, report it,
  write nothing. A file with some new entries is triaged for those entries only.
- **Never invent feedback.** Every spec must trace to a real entry, by title and entry id.
  If an entry is too vague to spec, mark it *needs clarification* rather than guessing.
- **Re-verify every Senzing fact against the live MCP server before writing (Step 5).**
  Never carry a Senzing fact from a feedback entry into a spec without re-asking the server.
- **Deduplicate.** If an existing spec already covers an item, do not create a second one.
  Note it as already-tracked, and optionally enrich the existing spec.
- **Respect this repository's own rules.** A spec must not propose anything that violates
  `.kiro/specs/senzing-bootcamp-power/requirements.md` (R1–R16) or the engine's structural
  guards: no substitution may target or write an `INV-NNN` citation, none may name an
  interpreter or a Hook_Command_String placeholder, and content must hold on Linux, macOS
  and Windows. If feedback conflicts with one of those, say so in the spec instead of
  silently overriding it.

## Step 1: Locate and read the feedback file

Let the helper resolve it — the archive must never be re-processed, and that exclusion is
code rather than judgement:

```bash
python3 .kiro/skills/feedback-to-specs/feedback_ledger.py find
```

It looks for `SENZING_BOOTCAMP_POWER_FEEDBACK.md` at the repo root and under `docs/`,
skipping `docs/feedback/` (the archive) and any `*_DUPLICATE.md`.

⛔ **`SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md` is reserved for the Senzing Bootcamp Claude
plugin and is refused here, by name.** The two artifacts are developed in separate
repositories, and triaging a plugin's feedback into Kiro specs would route fixes to homes
(`contract`, `kiro-owned`, `engine`) that do not exist on that side. If the helper finds
that file it says so and stops — take it to the plugin's own development repository. Do not
work around this by renaming the file: the name is the only thing that says which artifact
the feedback is about.

An explicit path in `$ARGUMENTS` wins over the helper's answer. If the helper reports more
than one candidate and none was named, ask which to use. If it finds none, say so and stop.

Read the whole file.

## Step 2: Parse the feedback into discrete items

Feedback is usually a series of `## Improvement: <title>` blocks with subsections
(**What Happened**, **Why It's a Problem**, **Suggested Fix**, **Context When Reported**),
plus **Date**, **Module**, **Priority** and **Source** lines. Handle free-form prose too —
bootcampers do not always follow the template.

For each item extract: `title`, `symptom` (with any verbatim error/output), `impact`,
`suggested_fix`, `priority`, `module`, `date`, `source`, and the **routing verdict** the
bootcamper-facing flow may already have recorded (`plugin` / `mcp-server` / `both` / `host`
/ `unclear`). Skip the file's scaffold headings.

**`Source:` — who noticed it.** Two values (absent means `bootcamper-reported`):

- **`bootcamper-reported`** — a human hit this and said so. Real, felt friction.
- **`self-observed (assistant retrospective)`** — the graduation retrospective filed it.
  These skew toward the defect class a bootcamper *cannot* report: silently-wrong output,
  undocumented environment gotchas, tools behaving differently than documented. A
  bootcamper never files "the field name was wrong so the section rendered empty," because
  on screen that looks like no data.

Do **not** treat self-observed items as lower priority by default — they are often more
severe precisely because nobody would otherwise catch them.

## Step 3: Check whether these entries have already been processed

Feedback files arrive from **multiple bootcampers at multiple times**, so the realistic
collision is not the identical file twice — it is a file that *overlaps* a previous one,
because a bootcamper's project accumulates entries during a run and a later copy carries
the earlier entries **plus** new ones. Identity is therefore per entry, content-addressed:

```bash
python3 .kiro/skills/feedback-to-specs/feedback_ledger.py check <candidate.md>
```

It prints every entry with its id and status, and exits **0** when some entries are new,
**3** when every entry has been processed, **1** on bad input. Act on the verdict:

- **NEW** → triage the whole file. Continue to Step 4.
- **PARTIAL** → **triage only the new entries.** Do not re-analyze the known ones; name
  them in the Step 10 report with the spec each previously produced, so the maintainer can
  see what was skipped and why. Continue to Step 4.
- **DUPLICATE** → **stop. Write no specs.** Run `feedback_ledger.py commit <candidate.md>`,
  which renames the file in place to `…_<unixtime>_DUPLICATE.md` — the unixtime of the
  archive it duplicates — and leaves the ledger untouched. Tell the maintainer plainly:
  this file is a duplicate, nothing was processed, here is the archive it duplicates and
  the specs those entries already produced. Skip to Step 10 and report only that.

Normalization is part of the identity, not a nicety: a file re-saved on Windows can gain a
UTF-8 BOM or CRLF endings, and PowerShell can double-encode it — all of which change bytes
while the content is the same. The helper strips the BOM, normalizes newlines, right-strips
lines and collapses blank runs before hashing. It does **not** touch case or interior
wording: a reworded entry is a new entry, which is correct — the maintainer should see a
revised report.

The ledger is `docs/feedback/PROCESSED.jsonl`, append-only, read last-wins, one object per
processed entry: `entry_id`, `title`, `archive`, `archive_unixtime`, `processed`, and
`disposition`. The disposition is what makes it worth keeping — it records **which spec each
entry produced**, or `already-tracked`, or `needs-clarification`, so an entry that
legitimately produced no spec is never re-triaged forever.

## Step 4: Load triage context (before writing anything)

- **Read `.kiro/specs/senzing-bootcamp-power/requirements.md`** — R1–R16 are the ruleset
  every spec must respect. Skim `design.md` for the decisions behind them.
- **List and skim every existing `.kiro/specs/*/`.** Record each spec's title and the
  problem it covers so you can deduplicate.
- **Read `tools/bootcamp-transform/contract.yaml`** — the rules, the substitution sets and
  their per-rule order, the `ignore` list, and the `invariantDiscounts` register. This is
  where most Kiro-specific fixes land, and a spec that proposes a rule which already exists
  under another name is worse than no spec.
- **Read `powers/senzing-bootcamp/.build-manifest.json`** — the path→`ruleId`/`owner`/
  `sourcePath` map that decides fix routing.

## Step 5: Re-verify every Senzing fact against the live MCP server

**Do this before analyzing and before writing.** The Senzing MCP server is versioned and
released independently of this Power, so an entry filed weeks ago describes a server that
may no longer behave that way. Three outcomes are all common, and each changes the spec:

- **Still reproduces** → the spec stands, now with a current citation instead of a stale
  field report.
- **Fixed upstream** → do **not** write a spec proposing a Power-side workaround for a
  defect the server no longer has. Record it resolved-upstream, and if the Power carries a
  workaround added for it, spec the *removal* instead.
- **The server now contradicts the Power** → the Power is what is wrong, and the spec's
  subject changes from "the server is broken" to "our guidance is stale".

Record the server version first — `get_capabilities` returns `server_info` — so every claim
can be dated and attributed. Then re-ask the tool that **owns** the fact:

| The entry claims something about… | Re-ask |
|---|---|
| an SDK method, its arguments, or its response shape | `get_sdk_reference(topic='parameters' \| 'response_schemas', filter='<method>', language='<binding>')` |
| a flag, what it applies to, or what it returns | `get_sdk_reference(topic='flags', filter='<FLAG_NAME>')` |
| an attribute or mapping rule | `search_docs(query='…', category='data_mapping')` |
| an error code or its symptom | `explain_error_code('<SENZnnnn>')` |
| export, reporting, evaluation or graph behavior | `reporting_guide(topic='…')` |
| install, configuration or platform paths | `sdk_guide(topic='install' \| 'configure', platform='…')` |
| an example file or repository | `find_examples(...)` |

Rules for this step:

- **Ask the tool that owns the fact, not `search_docs` for everything.** A flag's
  `applies_to` is authoritative in `topic='flags'`; prose found by search is not.
- **Quote what the server returned** into the spec rather than paraphrasing. A future
  reader must be able to tell your claim from the server's.
- **A single field observation does not outrank the server, and the server does not outrank
  a reproducible observation.** When they disagree, record both with their conditions —
  flag set, SDK version, binding, platform. Most "contradictions" are two different
  conditions, and a spec that flattens them into one absolute is its own defect.
- **Where the server cannot reach** (a field below the shape `response_schemas` documents,
  a value only a live engine returns), say so and mark the fact observation-only with its
  version and date — never launder it into an MCP-sourced claim.
- **If the MCP server is unreachable**, do not guess and do not fall back to training data:
  write the spec with the fact marked "unverified — MCP unreachable at triage time" and say
  so in the report, so it can be re-checked before implementation.

## Step 6: Analyze each item, and find the home of the fix

For every parsed item:

1. **Classify** it: bug / false-positive, UX or wording, missing feature, requirement gap,
   documentation, or unclear.
2. **Confirm the root cause in the producing source, not in the generated Power.** Start
   from the shipped path the symptom names, look it up in `.build-manifest.json`, then open
   whichever of these its `ruleId`/`owner` points at and verify the cause there, citing
   `file:line`:
   - `owner: template` → the substitution sets its rule declares in `contract.yaml`, and
     the upstream file at `sourcePath` in the extracted release tree.
   - `owner: kiro` → the authored file under `tools/bootcamp-transform/templates/kiro-owned/`.
   - a generated document (`plugin.json`, `mcp.json`) → the `.j2` template plus its
     verifier in `transform.py`.

   If you cannot confirm it, label the root cause "Unverified — needs investigation".
3. **Reconcile the source against what Step 5 returned.** Where the Power's text states a
   Senzing fact the server now answers differently, the Power is the defect — even when the
   entry blamed the server, and even when the claim was correct when written. Check both
   directions: text the server contradicts, *and* a workaround still carried for a defect
   the server has since fixed.
4. **Decide the routing verdict** — `plugin`, `mcp-server`, `both`, `host` or `unclear` —
   from what Step 5 established, not from what the entry guessed. ⛔ **`host` has no
   upstream channel and MUST NOT be sent:** `submit_feedback` reaches Senzing, which does
   not ship the Kiro harness, so Step 8 is skipped for it entirely. A `host` entry may
   still need a Power-side spec for the part the bootcamp does own — what it says when the
   bootcamper raises it, and how it recovers a question the host displaced.
5. **Decide the fix home** from the manifest evidence, and record the triple. If the change
   would have to be made in ported content that is correct for Claude, the home is
   `contract` (a Kiro adaptation), not `upstream-template`. If it is wrong for both, it is
   `upstream-template` — and then note whether a `contract` entry should carry the fix
   locally until the next release brings it.
6. **Deduplicate** against existing specs. Mark the item `already-tracked → .kiro/specs/<name>/`.
7. **Group**: merge items that share one root cause or one fix into a single spec; keep
   unrelated items separate. The number of specs per run is whatever the analysis warrants —
   one, several, or none.

## Step 7: Write the spec(s)

For each new spec, create `.kiro/specs/<kebab-case-title>/` using `spec-template.md` in
this skill's directory: `.config.kiro` (fresh `uuid4`), then `bugfix.md` **or**
`requirements.md`, plus `design.md` and `tasks.md`. Rules:

- **Pick a directory name that does not collide** with an existing spec.
- **Ground it in the producing source.** Root cause cites real `file:line` there; affected
  files list real paths in a home a change can land in.
- **Fill `## Fix routing` completely**, including the manifest evidence. A spec without it
  is not actionable, because the reader cannot tell whether the fix arrives by rebuild or
  by a future release.
- **Ground every Senzing fact in Step 5's result, with provenance** — the tool and
  parameters, the server version, the date. Where the entry and the server disagree, state
  both and which governs. Mark observation-only facts as such, and satisfy the
  `owner-checked:` rule for any absence claim.
- **Say when the current server changed the spec.** If re-verification narrowed, widened,
  redirected or canceled what the entry asked for, put that in the spec rather than
  silently writing the corrected version.
- **Make acceptance criteria observable and testable** in this repository's EARS phrasing,
  and always include one that the change holds on Linux, macOS and Windows. Include the
  rebuild-and-diff task: any change in a `contract`, `kiro-owned` or `engine` home is only
  proven when a fresh build reproduces the committed Power and `validate.py` passes.
- **Leave every task box unchecked.** This skill writes specs; it does not implement them.

For a minor item that does not warrant a spec, propose it to the maintainer and ask before
writing anything.

## Step 8: Notify Senzing when the defect is theirs

An item belongs upstream when Step 5 confirms the **current** server is what is wrong — a
wrong or unobtainable documented path, a flag whose `applies_to` contradicts the schema, a
missing response shape, guidance that produces code the SDK rejects. A Power-side spec and
an upstream report are not alternatives: file both when the Power also needs to stop
repeating the defect.

1. **Check the entry's `Upstream:` field first.** The bootcamper-facing flow may already
   have sent it, in which case do not re-file the same finding. A follow-up is worth
   sending only when you now have something the first submission lacked — that it still
   reproduces on a newer server version, or a confirmed field name/shape they can act on.
   Say that it is a follow-up.
2. **Draft it as a technical bug report Senzing can act on without context from this
   repository:** the tool and parameters called, what came back, what was expected, the
   contradiction (quote both sides), the server and SDK versions, the impact in one line,
   and a minimal reproduction.
3. **Strip everything identifying.** No bootcamper name, employer, email, paths from their
   machine, host names, dataset contents or record values. Describe data shape, never data.
4. **Show the maintainer the exact message and get an explicit yes before sending.** This
   is required by `submit_feedback` itself and is the only outward-facing action this skill
   takes; a decline costs nothing and the spec still stands. Then call
   `submit_feedback(category='bug', message='<the approved text>')` — `category='feature'`
   for a coverage gap that is a request rather than a defect.
5. **Record the outcome** in the report: sent (with date and category), declined, or
   already-filed. The submission is anonymous, so no reply is possible — if the finding
   needs a conversation, it needs another channel.

⛔ **Never send under `category='license_request'`.** That path takes personal details and
is for evaluation licenses only; a defect report there is both wrong and a PII leak.

## Step 9: Archive the processed file and record its entries

**Only after the specs are written (Step 7) and any upstream submission is settled
(Step 8).** If a run aborts before that, the candidate must still be exactly where it was —
an archived input with no specs to show for it is the one outcome worse than re-processing.

```bash
python3 .kiro/skills/feedback-to-specs/feedback_ledger.py commit <candidate.md> \
  --disposition "<entry title>=.kiro/specs/<name>/" \
  --disposition "<entry title>=already-tracked" \
  --disposition "<entry title>=needs-clarification"
```

This moves the file to `docs/feedback/SENZING_BOOTCAMP_POWER_FEEDBACK_<unixtime>.md` and
appends one ledger line per **newly processed** entry. Entries
already in the ledger are not re-recorded, and are reported as skipped.

- **Pass a `--disposition` for every entry you triaged.** Without it the ledger records
  `unrecorded`, the helper warns, and the ledger loses the thing that makes it useful — the
  link from an entry to the spec it produced. Use the title exactly as `check` printed it,
  or the `entry_id`.
- **The archive is committed to git**, deliberately: the candidate is transient, and the
  specs quote entries only in part. Bootcamper text therefore enters history permanently —
  usernames, workstation details, dataset names. Confirm with the maintainer before the
  first archive if that is not acceptable for this repository's visibility.
- **Never edit an archived file or a ledger line.** Both are the record of what was
  processed. The ledger is append-only and read last-wins, so a wrong or `unrecorded`
  disposition is corrected by *appending*:
  `feedback_ledger.py annotate <entry_id> "<disposition>"`. A correction to the *analysis*
  is a new spec, never a rewritten entry.

## Step 10: Report the triage

State the server version every re-check ran against, once, then a compact table:

| Feedback item | Classification | MCP re-check | Fix home | Action |
|---|---|---|---|---|
| <title> | bug | still reproduces | `contract` | New spec → `.kiro/specs/<name>/` |
| <title> | UX | server now contradicts the Power | `contract` | New spec → `.kiro/specs/<name>/` (subject redirected) |
| <title> | bug | fixed upstream | `mcp-server` | No spec — resolved on server <version> |
| <title> | feature | n/a (no Senzing fact) | `kiro-owned` | Already tracked → `.kiro/specs/<name>/` |
| <title> | unclear | not checked | — | Needs clarification |

**Name what was skipped as already-processed, and where the file went.** A PARTIAL run must
list the known entries with the spec each previously produced — otherwise the maintainer
cannot tell "we triaged 2 of 6" from "the file only had 2". Then give the archive path and
the ledger line count. For a DUPLICATE run this is the entire report: nothing was
processed, here is the `_DUPLICATE` filename, here is the archive it duplicates, and here
are the specs those entries already produced.

Then list the spec directories created, note anything left for clarification, report each
upstream submission's outcome, and offer next steps ("I can implement
`.kiro/specs/<name>/` next"). Do not start implementing unless asked.

**Call out anything the re-check changed**, and anything whose fix home turned out to be
`upstream-template` — the first is the highest-value output of a triage run, and the second
is the one class of fix that does not arrive by rebuild and so needs a decision about
whether to carry it in the contract meanwhile. Both are invisible if they only live in a
file the maintainer has not opened yet.
