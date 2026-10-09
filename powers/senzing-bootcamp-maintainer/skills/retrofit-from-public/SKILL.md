---
name: "retrofit-from-public"
description: "Report how the public repository Senzing/senzing-bootcamp-kiro-power diverged from the Senzing Bootcamp Kiro Power that was last propagated to it, triage every divergence as parent-bound or local and show the verdict with its reason, hand parent-bound items to escalate-to-parent, and file local items as GitHub issues in this repository after checking the tracker for duplicates. Writes nothing into this repository or the public one; filing is the deliverable, and implementing is implement-github-issue's job. The inverse direction of propagate-to-public. Use when the maintainer says 'retrofit the senzing bootcamp power from public'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-power-development — as the open workspace, because the tagged Power, the Publication_Contract, and the comparison script all live here. Requires an existing local checkout of Senzing/senzing-bootcamp-kiro-power whose origin is that repository; this skill never clones. Needs git, Python 3.10+ with the dev extra installed (pyyaml), and `gh` authenticated with issue-write on this repository to file. No Senzing MCP server for the comparison; parent-bound items re-verify Senzing facts through escalate-to-parent."
metadata:
  author: "Senzing"
  role: "Retrofit_From_Public"
  engine: "tools/bootcamp-transform/"
  contract: "tools/bootcamp-transform/publication.yaml"
  script: "tools/bootcamp-transform/retrofit.py"
  publication: "Senzing/senzing-bootcamp-kiro-power"
---

# Retrofit the Senzing Bootcamp Power from public

`propagate-to-public` stops at the public working tree, and the Maintainer publishes by hand.
So every edit made during public review — a typo fix, a pull-request correction, a slug repair —
lands **only** in `Senzing/senzing-bootcamp-kiro-power`, and the next propagation overwrites it.
This is the return path: the canonical family operation `retrofit-from-public`, the inverse of
[`propagate-to-public`](../propagate-to-public/SKILL.md).

The comparison is done by
[`tools/bootcamp-transform/retrofit.py`](../../../../tools/bootcamp-transform/retrofit.py). Take it
from there, never from a hand-run diff against this repository's Power: that reports every
change made here since the last propagation, and every development self-reference the
[`publication.yaml`](../../../../tools/bootcamp-transform/publication.yaml) rewrites, as a public
edit.

## ⛔ It writes nothing

Not into this repository, and not into the public checkout. The output of this skill is **GitHub
issues**, and for parent-bound items a hand-off to
[`escalate-to-parent`](../escalate-to-parent/SKILL.md). Bringing a change across is a separate,
later step through `implement-github-issue`. The parent applied retrofits directly once and
reversed that on purpose: a change that arrives in a tree without an issue arrives without its
reasoning, its test run, or its invariant question.

It also never pulls the public repository's own files — README, CHANGELOG, workflows, `.github/`
tooling, `.vscode/` — into this one. Those are public-owned and were never propagated, so a change
to them is not a divergence from here. The script compares only the Power directory.

## Step 1 — Find the public checkout

Ask for the path to the Maintainer's checkout of `Senzing/senzing-bootcamp-kiro-power` if they did
not give one, checked out at the commit whose changes they want considered. **Do not guess it, and
do not clone it.** The script refuses a target with no `.git`, or whose `origin` is another
repository.

## Step 2 — Compare against what was propagated

```
python3 tools/bootcamp-transform/retrofit.py --public <public checkout>
```

The baseline is the Power at a tag of **this** repository, run through the Publication_Contract
exactly as `propagate.py` runs it. By default that tag is the public checkout's newest semver tag,
the release it last published. The report's `base` and `baseChosenBy` say which.

⚠️ **After a propagation is committed in public but before public is tagged**, its newest tag is
still the previous release, and the new release reads as public edits. Name the propagated tag:

```
python3 tools/bootcamp-transform/retrofit.py --public <public checkout> --base <tag>
```

The script aborts, with nothing written, when the tag does not exist here or when the current
Publication_Contract refuses the Power at that tag. The second happens for releases cut before the
Propagator existed, and the answer is a later `--base`, not a forced comparison.

Report to the Maintainer: the base and how it was chosen, `publicHead`, the count of diverged
paths, `publicCommitsSinceBase` (each marked `touchesPower`), and anything in
`uncommittedInPowerDirectory` — a public edit nobody has committed yet is still an edit.

## Step 3 — Rule out what is not a public edit

Not every diverged path is a correction someone made in public. Before triaging an item, settle
which of these it is, and say so:

- **Already absorbed here.** The same fix is already in this repository, made after the base tag.
  Check the producing source — the authored `kiro-owned` file, `contract.yaml`, or the current
  Power — for the public text. This is common when a release was propagated from a commit later
  than its tag: public `0.5.3` carries the port-status rewording that landed here after tag
  `0.5.3`, so it diverges from the tag and is already done. Record it as *already absorbed*, with
  the commit that absorbed it, and file nothing.
- **A consequence of another item.** `.build-manifest.json` changes whenever a file it records
  changes. Fold it into the item that caused it rather than filing it separately.
- **A binary.** The report carries no diff for a PDF or image. Name it, and say what would
  establish whether it was regenerated or edited, rather than guessing.

## Step 4 — Triage every item, and show the verdict

Group the remaining divergence into **coherent changes** — one per thing a Maintainer would decide
about, not one per file. Then classify each, with the reason, for **every** item:

- **Parent-bound** — curriculum, content, a Senzing fact, or parent-owned behavior. Hand it to
  [`escalate-to-parent`](../escalate-to-parent/SKILL.md); do not file it here, and do not file it
  upstream from here. That skill stays the only path that writes to another repository.
- **Local** — Kiro packaging, hooks, lifecycle, host interaction, the release process, or the
  publication adaptations. File it here (step 6).
- **Needs clarification** — the diff does not show which. File nothing, and say what would settle it.

Each item's `owner`, `ruleId`, and `sourcePath` are the build's own record of where the file is
produced, and `suggestedHome` with its `reason` is the script's starting point. It is evidence,
not the verdict:

- `owner: kiro` and the generated documents are produced here, so their changes are local.
- `owner: template` is ported from the parent's `sourcePath`, so a change to it is presumptively
  parent-bound. But that same file is rewritten here by Kiro substitution sets, and a change inside
  substituted text — a Kiro mechanism name, a hook description, a slug — is local. Compare the diff
  against the upstream file at `sourcePath` to tell the two apart.
- `adaptedAtPropagation: true` means `publication.yaml` also rewrites the file. A change in
  rewritten text is a publication-contract change, and local.

⚠️ **A wording fix in shipped curriculum prose is parent-bound even though it was found in the Kiro
public repository.** Fixed only here, the correction lives in one port and the other three keep the
defect; fixed in the parent, `parity-check` brings it to every port.

An item can be both: a curriculum fix the port also mangled gets an escalation **and** a local
issue for the part the port owns, cross-referenced.

## Step 5 — Check the trackers before filing

⛔ Search before filing each item, and record what you searched:

```
gh issue list --repo docktermj/senzing-bootcamp-kiro-power-development --state all --search "<path or public commit subject>"
```

For a parent-bound item, also search the parent development repository, read-only, so
`escalate-to-parent` is not handed a duplicate:

```
gh issue list --repo docktermj/senzing-bootcamp-claude-plugin-development --state all --search "<the corrected text>"
```

An item already filed, or already absorbed, gets no second issue. The trackers are the record;
this skill keeps no ledger of its own.

## Step 6 — Show each issue, get a yes, then file

Show the Maintainer the per-item verdict table first, then each local issue's title and body, and
file only on approval. Filing is outward-facing and immediate: an issue can be closed afterwards
but never un-filed.

```
gh issue create --repo docktermj/senzing-bootcamp-kiro-power-development \
  --title "<what diverged, not the symptom>" --body-file <file outside both repositories>
```

Each local issue body carries:

- the public commit (subject and SHA) or, when uncommitted, that it is uncommitted;
- the base it was compared against, and every path affected, with its diff;
- the producing home — the `ruleId`/`owner`/`sourcePath` triple — so the fix lands at its single
  point of change, never in `powers/senzing-bootcamp/`;
- ⚠️ **the inverse publication rewrite as work still to do.** Text coming back from public carries
  the public form of anything `publication.yaml` rewrote; whoever implements the issue restores
  this repository's form by hand;
- acceptance: the change is made at its home, a fresh build reproduces it, and the next
  `propagate-to-public` shows no diff for these paths.

Hand each parent-bound item to `escalate-to-parent` with its diff, the public commit, and the
reason it is curriculum-level. Note the escalation in the report; that skill records both ends of
the cross-reference.

## Step 7 — Report

A compact table, one row per item: path or group, verdict and reason, and the action taken (local
issue URL, escalated, already filed, already absorbed, needs clarification). Name the base, the
public head, and anything the Maintainer still has to decide. Offer `implement-github-issue` for a
filed local issue; do not start implementing unless asked.

## Scope

This skill compares, triages, and files. It writes nothing into any working tree, never deletes or
adds a file, and never files outside this repository — parent-bound items go through
`escalate-to-parent`. Keep `retrofit.py` and `propagate.py` reading the same Publication_Contract:
the comparison is only honest while both directions agree on what propagation does.
