---
name: "production-readiness-audit"
description: "Audit the shipped Senzing Bootcamp Kiro Power at powers/senzing-bootcamp/ for production readiness: a static review of the Power as one body of instructions for consistency, coherence, completeness and concision, checked against both invariant records — the inherited INV-NNN through the disposition register, and the Kiro-native KINV-NNN ledger — in both directions. Shows a parent-bound or local verdict for every finding with its reason, hands parent-bound findings to escalate-to-parent, and files local findings as deduplicated GitHub issues in this repository. The static gate between the mechanical checks and the recorded host-behavior checklist; it fixes nothing unasked. Use when the maintainer says 'audit the senzing bootcamp power for production readiness'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-power-development — as the open workspace, because the Power, its build manifest, both invariant records, and the lead generators all live here. Needs git and Python 3.10+ with the dev extra installed (pyyaml). Needs `gh` with read access to the parent development repository, to resolve INV citations against the pinned release, and issue-write on this repository to file. The Senzing MCP server only when a finding asserts a Senzing fact."
metadata:
  author: "Senzing"
  role: "Production_Readiness_Audit"
  engine: "tools/bootcamp-transform/"
  script: "tools/bootcamp-transform/audit.py"
  parentDevelopmentRepository: "docktermj/senzing-bootcamp-claude-plugin-development"
---

# Audit the Senzing Bootcamp Power for production readiness

The canonical family operation `production-readiness-audit` (FAMILY_WORKFLOW R4), Phase 3. It
asks whether `powers/senzing-bootcamp/` **as a body of instructions** holds together: a rule
stated in one module and contradicted in another, a step that names what to select without naming
the route, a promise made in onboarding and never kept, a skill referenced by a name nothing ships.

⚠️ **A clean transform and a clean checklist do not imply a coherent Power.** The
Schema_Validator is mechanical and the `Test_Checklist` is a fixed list of host questions; neither
reads the curriculum as a whole. That is the gap this fills, and it is why every audit the parent
has run against a fully green suite still found real defects.

This is a port of the parent's audit, not of its file layout. The lead generators are
[`tools/bootcamp-transform/audit.py`](../../../../tools/bootcamp-transform/audit.py), adapted from
the parent's `conformance.py` to read the Power a bootcamper installs and to split every hit by the
build's own record of where the file comes from.

## Where it sits

| | Asks | Home |
|---|---|---|
| Component E — mechanical port checks | did the **transform** produce a well-formed Power? | `validate.py` |
| **this skill** | does the Power **agree with itself and with its rulesets**? | `audit.py` + reading |
| Component G — recorded `Test_Checklist` | does the Power **behave** on Kiro, per platform? | `docs/test-checklist.md` |
| `release` | may this version be tagged? | gates on E and G |

Run it after `validate.py` passes and before the checklist is worked: a coherence defect found
here costs one fix, and found during manual testing it costs a re-test on three platforms.

⛔ **The conversational invariants are out of static scope, and the report MUST say so.** One 👉
question per turn (INV-251; on Kiro advisory only, KINV-011), asked-once, no unrequested skips, and
every gate ordering govern what the model does in a live turn. Reading cannot establish them. Route
them to the `Test_Checklist` and to `dry-run`. A report that lets them pass silently is a false
clean bill of health.

## Two halves, two routes (R6)

Every finding is about content ported from the parent or content authored here, and the two go to
different places. The build records which is which: each file's `owner` in
`powers/senzing-bootcamp/.build-manifest.json`, which every `audit.py` view prints.

- **Parent-bound** — `owner: template` content whose defect reproduces in the parent: the
  curriculum, a Senzing fact, parent-owned behavior, a rule the parent should register in its
  `INV-NNN` namespace. ⚠️ **A wording or coherence defect in ported curriculum prose is
  parent-bound even though the audit found it here**, or it gets fixed in one port and three keep
  it. Hand it to [`escalate-to-parent`](../escalate-to-parent/SKILL.md), which stays the only path
  that writes to another repository.
- **Local** — anything this repository produces: `owner: kiro` files, the generated manifests,
  and inside template files the text a Kiro substitution set wrote (a Kiro mechanism name, a hook
  description, a skill trigger). Find the home from the manifest triple — `contract.yaml`, the
  authored tree under `tools/bootcamp-transform/templates/kiro-owned/`, or the engine — never
  `powers/senzing-bootcamp/`, which is generated output.
- **Both** — a parent defect the port also mangled gets an escalation **and** a local issue for
  the part the port owns, cross-referenced.

## Step 1 — Establish the baseline

1. **Confirm the suite is green**: `python3 -m pytest -m "not integration" -q`. A red suite means
   you are debugging, not auditing, and findings get attributed to the wrong cause.
2. **Confirm the build is valid** for the pinned release: `docs/test-records/<version>-validation.json`
   reads `passed`. Read the version from `powers/senzing-bootcamp/plugin.json`.
3. **Read what is already known**: open issues in this repository, and open escalations, so a run
   does not re-find a recorded defect:
   ```
   gh issue list --repo docktermj/senzing-bootcamp-kiro-power-development --state open --limit 100
   ```
4. **Run every lead generator**, then read the hits:
   ```
   python3 tools/bootcamp-transform/audit.py all
   python3 tools/bootcamp-transform/audit.py since
   ```
   `all` runs `rules`, `citations`, `references`, `enumerations`, `duplication` and `size`. `since`
   lists the hard-rule lines added since the newest release tag, which is the set this release is
   answerable for, and prints a `VERDICT` that is `clean` only when every added line cites an
   invariant, and `empty` when nothing was added.
   ⛔ **These are lead generators, not verdicts.** A run that reports their counts as findings has
   run a grep, not an audit.
5. **Record what this environment cannot reach** — a platform, the Senzing SDK, a headless
   browser, network access to the parent registry — so the report discloses rather than implies.

## Step 2 — Sweep the invariants, forward

Two records bind the Power, and both are swept:

- **Every `KINV-NNN`** in `specs/INVARIANTS.md` — few enough to sweep in full every run. For each,
  find **every** site it binds and check them all; the dominant failure is a rule applied to some
  of its sites. `enumerations` names the KINVs that list members, which rot fastest.
- **The inherited `INV-NNN`**, through the disposition register (`invariantDiscounts` in
  `contract.yaml`): an invariant the port honored must still hold in the Kiro rendering of the
  sites it binds, and a discounted one must still be discounted for the recorded reason. The full
  INV set is the parent's to sweep; scope the run deliberately — the INVs the generators put hits
  against, and those binding anything the diff since the last tag touched — and **say what you
  scoped it to**.

`citations` resolves every `INV-`/`KINV-` id the Power cites — INV ids against the parent's
`specs/INVARIANTS.md` at the pinned release, fetched read-only. It proves an id **exists**; only
reading proves it is the **right** one for the claim beside it. Offline, every INV id is reported
`UNVERIFIED` and the view says it is not clean (INV-308); pass `--parent-invariants <file>` instead.

## Step 3 — Sweep the invariants, reverse

Work the `rules --uncited` and `since` output. For each uncited hard rule, decide:

- **kiro-owned, a durable Kiro-native rule not in the ledger** → draft a `KINV-NNN`, get the
  maintainer's sign-off on the wording, and add it per `specs/INVARIANTS.md`'s own maintenance
  rules: next unused id, index entry in the same change, `specs/check_invariants.py` passing. Never
  record one they have not agreed to. Local.
- **a missing citation to a rule that exists** → the fix is the citation, at its home. Local if
  the text is authored here; parent-bound if it is ported prose.
- **template content stating a durable rule the parent never registered** → parent-bound. It is
  the parent's to register in its `INV-NNN` namespace; ⛔ never mint a `KINV` for it, because a
  KINV MUST NOT restate an upstream invariant.
- **not a durable rule** — local instruction or pedagogy. Out of scope; say so.

## Step 4 — Consistency and coherence

- **Every cross-reference points at the right thing** — sibling phase files, step numbers,
  invariant ids. `validate.py` proves links resolve; only reading proves they are right.
- **No file contradicts a sibling.** Read each skill's `SKILL.md` against its own phase files.
- **The Kiro rendering is coherent with itself.** A substitution set rewrites a term in one place
  and the prose around it still assumes the old one; a kiro-owned skill describes a hook tier or a
  trigger the shipped files no longer have. These are local, and the class to sweep for.
- **Order makes sense.** A gate cannot depend on something a later step produces.

## Step 5 — Completeness

- **Every referenced surface ships.** `references` names skill names nothing ships and every
  slash command the text invokes. A Kiro Power ships no slash commands: each template command is a
  trigger-phrase skill, and a `/name` in ported prose that the Kiro CLI does not provide either is a
  coherence defect — local when the substitution sets should have rewritten it.
- **Every hook-enforced behavior has its Tier 1 instruction** (KINV-008), and every behavior the
  parent binds to a trigger Kiro lacks is delivered by a Kiro mechanism (KINV-012). This is the
  port's mapping of the parent's hook checks; it is not dropped, it is restated against Kiro.
- **Every platform is covered** — Linux, macOS and Windows — and the untested half is disclosed
  rather than omitted.

## Step 6 — Concision

`size` and `duplication` print their own totals; read them off the run, never from here.
Byte-identical mirrors (the Tier 2 and Tier 3 hook trees) are skipped because they cannot drift.
Look for:

- **Repetition that has drifted.** A kiro-owned file repeating template text — `docs/model-selection.md`
  against `ground-rules.md` is the standing case — is the likeliest drift: the template copy moves
  by rebuild and the authored one does not.
- **A governing rule buried below the fold**, and **definition too thin**: Goldilocks cuts both ways.

⛔ **Never cut rationale to make something shorter.** Every "observed:" clause names a real
defect, and that narrative is what stops the rule being re-broken. The concision win is merging
duplicated statements and moving a rule to where it is used.

## Step 7 — Record every finding, then file

⛔ **Record each finding as you find it, before fixing anything** (INV-317): a fixed finding no
longer reproduces, and a run that fixes first leaves no evidence it existed. One record per root
cause, citing `file:line` in `powers/senzing-bootcamp/` and the producing home from the manifest.

1. **Show the verdict for every finding** — parent-bound, local, both, or needs clarification —
   with its reason. Never silently.
2. **Search before filing**, here and, read-only, in the parent:
   ```
   gh issue list --repo docktermj/senzing-bootcamp-kiro-power-development --state all --search "<subject>"
   gh issue list --repo docktermj/senzing-bootcamp-claude-plugin-development --state all --search "<subject>"
   ```
   A finding already filed, already escalated, or already fixed upstream at a newer release
   (`parity-check` brings it) gets no second record.
3. **Show each local issue's title and body and get a yes** (INV-314), then file it:
   ```
   gh issue create --repo docktermj/senzing-bootcamp-kiro-power-development \
     --title "<the defect, not the symptom>" --body-file <file outside the repository>
   ```
   The body carries the sites, the manifest triple naming the home, the verdict and its reason,
   and acceptance that the change reproduces on a fresh build. A finding resting on the Senzing
   MCP server **lacking** something carries the route asked and what it returned (INV-213).
   ⛔ Never apply the `unattended-ok` label to an issue you file (INV-318).
4. **Hand each parent-bound finding to `escalate-to-parent`**, with the sites and the reason it is
   curriculum-level. Do not file it here, and do not file it upstream from this skill.

⛔ **Do not end a run with an unrecorded finding.** Before reporting, confirm each one is a filed
issue or an escalation. A finding described only in the report is not recorded.

## Step 8 — Report

- **Lead with anything that breaks a documented path**, severity first.
- **Name the issue or escalation each finding was recorded in.**
- **State the verdict on each property separately** — consistent, coherent, complete, concise.
- **Say what you verified as correct**, briefly, and **what you scoped the sweep to**.
- ⛔ **State the coverage limits explicitly**: the conversational invariants, any platform or path
  this environment could not exercise, and any `UNVERIFIED` count `citations` reported.
- **Offer the `Test_Checklist`** as the next step; this skill is the gate before it.

## What the parent's audit has that this one restates or records

The parent's audit leans on its own repository: an implementation ledger in `specs/IMPLEMENTED.md`
that dates every audit, a `dry-run` coverage report, a citation verifier, an unattended issue loop,
and a stdlib-only test directory. None of those exist here, and none is dropped silently:

- **The audit ledger** → `since` takes its range from the newest release tag, because a release is
  what this audit gates; the run's findings are issues and escalations (INV-317's filed-issue
  branch). There is no unattended runner here, so INV-314's and INV-318's unattended branch never
  applies and every run is attended.
- **The citation verifier** → the `citations` view.
- **The `dry-run` coverage report** → not yet available in this repository; disclose it as a gap.
- **"Write a repo-level test, stdlib only" (INV-108)** → cannot be followed as written: this
  repository's suite runs under pytest with pinned dev dependencies. Recorded as a discount in the
  disposition register in `contract.yaml`, with what is preserved.

## Guardrails

- **Report before changing.** Present findings and let the maintainer choose what to fix; fix in
  place only when asked, and then at the producing home through `implement-github-issue`.
- **Never mark a property satisfied that you did not check.** An unexamined area is a disclosed gap.
- **The Senzing MCP server outranks the Power on every Senzing fact**, re-asked this session or not
  asserted. Most findings touch no Senzing fact — say so rather than implying a re-check happened.
- **`specs/INVARIANTS.md` is append-only**, and a KINV never restates an `INV-NNN` or a register
  entry.
- **Never write into `powers/senzing-bootcamp/`.** `audit.py` writes nothing anywhere.
