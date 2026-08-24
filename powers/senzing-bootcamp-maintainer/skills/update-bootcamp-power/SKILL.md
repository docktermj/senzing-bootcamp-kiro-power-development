---
name: "update-bootcamp-power"
description: "Move the existing Senzing Bootcamp Kiro Power at powers/senzing-bootcamp/ to a newer Senzing bootcamp Claude plugin release, by re-running the shared transformation engine, reconciling the result against the Power so every Kiro-specific adaptation is preserved, and publishing only after validation passes. Use when the maintainer says 'update the senzing bootcamp power'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-powers-development — as the open workspace: every command below is a repo-relative path into tools/bootcamp-transform/, and the engine, the Transformation_Contract, the existing Power, and the target all live here. Requires a Power already present at powers/senzing-bootcamp/, with its .build-manifest.json, as the baseline the reconciliation compares against. Needs Python 3.10+ with the dev extra installed (pyyaml, jsonschema, jinja2). Uses `gh` when it is on PATH and the GitHub REST API otherwise; GITHUB_TOKEN or GH_TOKEN is optional. No Senzing MCP server."
metadata:
  author: "Senzing"
  role: "Update_Skill"
  engine: "tools/bootcamp-transform/"
  contract: "tools/bootcamp-transform/contract.yaml"
---

# Update the Senzing Bootcamp Power

The Maintainer wants the existing `powers/senzing-bootcamp/` moved to a newer
Template_Release, keeping every Kiro-specific adaptation it has accumulated *(R5)*.

This skill is an **orchestrator and nothing else.** Every mapping rule, substitution,
generated manifest, and invariant discount lives in
[`tools/bootcamp-transform/contract.yaml`](../../../../tools/bootcamp-transform/contract.yaml)
— the same contract `create-bootcamp-power` invokes, referenced here and not restated, so the
two paths cannot drift *(R3 AC1, AC3)*. You run the steps below in order and read their JSON.
You do not decide what a file becomes, and you do not decide what survives.

Three rules that hold for the whole run:

- **No transformation logic here, and none by hand.** If output is wrong, the contract is
  wrong: change the rule or the substitution set and re-run. The same input through the
  create path and this path produces the same bytes *(R3 AC5)*, and a hand-edit is what
  breaks that.
- **Nothing reaches `powers/senzing-bootcamp/` until the swap.** Steps 1–7 read the Power and
  write into a staging directory. That is what makes every failure before the swap leave the
  Power byte-identical to its prior state *(R5 AC7)*.
- **The changelog entry is staged, never written into the Power.** It rides the swap. So a
  transform or validation failure discards it along with everything else and no entry exists
  anywhere *(R5 AC7, AC8)*.

## Sequence

Read the current state → resolve a newer release → fetch the release the Power was built from
→ transform with carry-forward → reconcile, apply, and stage the changelog entry → present the
reconciliation report → validate → atomic swap → report, then the `Test_Checklist`.

Pick two scratch paths first and reuse them across the steps:

| Path | What it holds |
|---|---|
| `/tmp/senzing-bootcamp-build/` (any directory **outside** this repository) | both extracted release trees, the current one and the newer one |
| `powers/.senzing-bootcamp.staging/` | the reconciled Power, before it is published |

The staging directory has to be a **sibling of the target**, because the swap is a directory
rename and a rename cannot cross filesystems. It must also be absent or empty — the engine
refuses to write into a staging directory that already has content, which is what lets it
delete the whole tree on a failure without ever destroying something it did not create. Never
commit it: a successful run consumes it and a failed run discards it, so it exists only
mid-run.

## Step 1 — Read what the Power is now

The update is a comparison, so it starts by reading the two documents that say where the Power
stands:

```
python3 -c "
import json
from pathlib import Path
power = Path('powers/senzing-bootcamp')
plugin = json.loads((power / 'plugin.json').read_text(encoding='utf-8'))
manifest = json.loads((power / '.build-manifest.json').read_text(encoding='utf-8'))
print(json.dumps({
    'version': plugin.get('version'),
    'templateRelease': plugin.get('extensions', {}).get('com.senzing.bootcamp', {}).get('templateRelease'),
    'manifestTemplateRelease': manifest.get('templateRelease'),
    'manifestFiles': len(manifest.get('files', [])),
}, indent=2))
"
```

`version` is the Power's current version identifier and the floor the resolver compares
against in step 2 *(R5 AC1)*. `templateRelease` is the release it was built from, and by
construction the two are the same string *(R2 AC5)*. `.build-manifest.json` is the baseline the
reconciliation needs: it records the hash of every file **as the engine wrote it**, which is
the only witness of what was generated as opposed to what is on disk now.

Two conditions stop the run here, before anything is fetched:

- **No Power, or no `.build-manifest.json`.** There is nothing to update and no baseline to
  reconcile against. Report the path and say that `create-bootcamp-power` is the skill for an
  initial build. Do not fall back to a create: this skill preserves local content and that one
  replaces the directory wholesale.
- **`version` and `templateRelease` disagree.** The Power does not describe a single release,
  so "newer than the current version" has two answers. Report both values and stop; the
  Schema_Validator's version-match check is the same fault, and it is fixed by rebuilding, not
  by updating.

## Step 2 — Resolve, and only if there is something newer

```
python3 tools/bootcamp-transform/resolve_release.py \
  --min-version <version from step 1> \
  --out /tmp/senzing-bootcamp-build
```

`--min-version` is what makes this the update path: the resolver picks the semver maximum among
published, non-draft, non-prerelease releases with a bare semver tag, and fetches the tree at
`refs/tags/<tag>` — never `main` — **only** when that maximum is greater than the version you
pass *(R5 AC1)*. It takes a bare semver string, which is exactly what step 1 read.

Read `tag`, `extractedTo`, and `pluginRoot` from the JSON rather than reconstructing them, and
carry the resolved tag character-for-character everywhere downstream *(R1 AC5, R2)*.

Three outcomes, and they are not all errors:

| JSON `error` | Exit | What it means | What to do |
|---|---|---|---|
| *(none)* | 0 | a newer Template_Release exists and its tree is extracted at `extractedTo` | proceed to step 3 *(R5 AC1)* |
| `E_ALREADY_CURRENT` | **0** | the resolved maximum is not greater than the current version | the Power is current. Report it and stop |
| `E_NO_RELEASE` | 1 | upstream has no published, non-draft, non-prerelease, semver-tagged release | report upstream's state; nothing to update from |
| `E_RESOLVE_FAILED` | 1 | no result within 30 s across 3 attempts | report; retry, and check network or GitHub auth |

`E_ALREADY_CURRENT` is informational, which is why it exits zero and carries no `extractedTo`:
nothing was fetched, because nothing is going to be built. Report the resolved `tag` alongside
the Power's version and **change nothing** — no staging, no transform, no changelog entry, not
one byte of `powers/senzing-bootcamp/` *(R5 AC2)*. Do not treat it as a failure in the summary;
"already current" is a successful answer to the question that was asked.

On either failure code nothing was fetched and the Power is untouched. Report the code and
message as given, and stop.

## Step 3 — Fetch the release the Power was built from

The reconciliation answers one question no file hash can: is a recorded invariant discount still
about the invariant it was written against? That needs **both** release trees, so materialize
the older one beside the newer one:

```
python3 -c "
import json, sys
sys.path.insert(0, 'tools/bootcamp-transform')
from resolve_release import RESOLUTION_BUDGET_SECONDS, contract_template, fetch_source_tree
repository, _ = contract_template()
tree = fetch_source_tree(repository, sys.argv[1], sys.argv[2], timeout=RESOLUTION_BUDGET_SECONDS)
print(json.dumps({'repository': repository, 'tag': sys.argv[1], 'extractedTo': str(tree)}, indent=2))
" <templateRelease from step 1> /tmp/senzing-bootcamp-build
```

The repository comes from the contract's `template` block, so this step invents no upstream
location. Only the tag ref is requested, and the tree lands at
`/tmp/senzing-bootcamp-build/bootcamp-src-<tag>/`.

This step is the one step that may fail without stopping the run. If the older release is gone
upstream or the fetch does not complete, **say so** — the drift comparison will not run, and an
empty flag list then means "not compared" rather than "nothing drifted". Omit both tree
arguments in step 5 in that case; the reconciler narrates the same caveat when it is given one
tree and not the other. Everything else about the update proceeds unaffected.

With the register currently empty — `invariantDiscounts: []` in the contract — there is nothing
to compare and the flag list is legitimately empty. The step still runs, so the comparison is in
place the moment the register has an entry.

## Step 4 — Transform into staging, carrying the Power's Kiro-owned content forward

```
python3 tools/bootcamp-transform/transform.py \
  --source <extractedTo from step 2> \
  --tag <tag from step 2> \
  --staging powers/.senzing-bootcamp.staging \
  --carry-forward powers/senzing-bootcamp
```

`--carry-forward` is the update path's flag. It names the existing Power whose `kiro-owned`
content is carried into the new tree, taking the Power's copy ahead of the authored default
under `tools/bootcamp-transform/templates/kiro-owned/`, so an adaptation the contract declares
Kiro-owned survives the rebuild rather than being reset to the template's version *(R5 AC5)*.
Omit it and you have run the create path against a newer release.

`--contract` defaults to the contract beside the script, which is the single shared source both
maintainer skills invoke — pass it explicitly only to point at a copy for debugging. To see the
match plan against the newer release without writing anything at all, add `--plan-only` first;
it reports what every source file matched and writes nothing, not even to staging.

On success the JSON reports `"status": "staged"`, the counts (enumerated, matched, ignored,
outputs, written), the per-file `ruleId` and `owner` for everything written, and
`.build-manifest.json` recording the newer `templateRelease` and a SHA-256 per output.
Narration also lists any `unmaterialized` destination — a `kiro-owned` rule with no authored
content behind it. Read those warnings.

On any `error`, the staging tree was discarded and the Power was never opened.

| Code | What it means | What to do |
|---|---|---|
| `E_UNMATCHED_FILE` | a source file matches no rule and no `ignore` entry *(R3 AC6)* | genuinely new upstream content, and the most common thing a newer release brings: add a rule or an `ignore` entry to the contract, then re-run. Never route it by hand |
| `E_MISSING_ASSET` | a ported script references a vendored asset absent from the source | report the path it names; fix the contract's asset rules or raise it upstream |
| `E_WRITE_FAILED` | staging could not be created or written | report the path; the Power is unchanged |
| `E_TRANSFORM_FAILED` | any other halting fault | report the code and message as given |

Any of them ends the run the same way: the Power is unchanged, no changelog entry was made, and
the update did not complete *(R5 AC7)*. Say exactly that.

## Step 5 — Reconcile, apply the verdict, and stage the changelog entry

```
python3 tools/bootcamp-transform/reconcile.py \
  --power powers/senzing-bootcamp \
  --staging powers/.senzing-bootcamp.staging \
  --to-release <tag from step 2> \
  --from-release <templateRelease from step 1> \
  --from-release-tree <extractedTo from step 3> \
  --to-release-tree <extractedTo from step 2> \
  --report docs/test-records/<tag>-reconciliation.json \
  --apply \
  --changelog
```

Three inputs, one verdict per path: the previous manifest's hashes, the Power on disk, and the
freshly transformed staging tree. Comparing the second and third against the same baseline is
what separates a local adaptation from an upstream change — a two-way diff sees one difference
and cannot say which side moved.

The two flags are what make the report true rather than advisory, and both write **only** under
`--staging`:

- `--apply` materializes the verdict into the staging tree, so every preserved adaptation is
  carried with its on-disk bytes before the swap publishes them *(R5 AC5, AC6)*. Without it a
  `keep-on-disk` verdict is a preserved adaptation on paper and an overwritten one on disk,
  because the swap replaces the whole directory. It re-reads what it wrote and refuses to
  proceed if any locally divergent file was overwritten.
- `--changelog` appends this update's entry, naming `--to-release`, to the **staged**
  `CHANGELOG.md` *(R5 AC8)*. Pass it together with `--apply` and in this order — the
  application is what carries the Power's existing changelog into staging, so appending first
  would have the entry rewritten away. The entry is rendered from the reconciliation, carries
  no date or timestamp, and is appended: nothing already in the changelog is rewritten.

`--from-release` defaults to the `templateRelease` recorded in the previous manifest; pass it
explicitly so the entry's "Updated from … to …" wording is not left to a default. Drop
`--from-release-tree` and `--to-release-tree` together if step 3 could not fetch the older tree.

Exit 0 means reconciliation completed — **with or without conflicts.** Exit 1 is a fault reading
an input, applying the result, or writing the report (`E_TRANSFORM_FAILED`, `E_WRITE_FAILED`):
discard staging as in step 7, leave the Power unchanged, and report that the update did not
complete *(R5 AC7)*.

## Step 6 — Present the reconciliation report

Show the Maintainer what this update does, from the JSON on stdout and at
`docs/test-records/<tag>-reconciliation.json`. Every path lands in exactly one bucket:

| Bucket | What it means | What the update does |
|---|---|---|
| `added` | present in the newer transform, absent from the last build | take staging |
| `modified` | upstream changed it, nobody edited it locally | take staging |
| `removed` | the last build produced it, the newer transform does not | remove, and list it |
| `unchanged` | neither side moved | keep |
| `preservedAdaptations` | a Kiro-specific adaptation with no counterpart upstream | keep the on-disk bytes *(R5 AC5)* |
| `conflicts` | a local edit **and** an upstream change to the same file | keep the on-disk bytes, name both sides *(R5 AC6)* |

List every added, modified, and removed path, and every preserved adaptation with its `reason`
*(R5 AC4)*. The reasons are worth reading aloud: `kiro-owned` is an adaptation the contract
**declares**, `local-edit-no-upstream-change` and `local-only-no-template-source` are ones the
reconciler **detected** as hash divergence from the last build.

For each conflict, state its `path`, the `adaptation` being kept, the `templateChange` being
declined, and the fixed `resolution` — local version retained, Maintainer action required
*(R5 AC6)*. **A conflict is a reported outcome, never an error.** It blocks nothing, changes no
exit code, and never costs the local content: the reconciler does not overwrite a locally
divergent file, because it cannot tell a deliberate adaptation from an accidental edit and so
can only ever flag. What the Maintainer owes it is a decision — promote the adaptation into the
contract as a rule, a substitution set, or a `kiro-owned` file, and the conflict does not
recur. Conflicts trend to zero as adaptations migrate into declarations.

Then present `flaggedInvariantDiscounts`, and present it even when it is empty *(R15 AC10)*.
Each entry names an `invariant` whose text changed between the two releases, the `reason` it
was flagged, and the `action`: Maintainer re-evaluation, because the recorded resolution may no
longer apply. A discount is a judgment about one specific invariant text — change the text and
the judgment has lost its subject, so it is reopened here rather than carried forward
unexamined. Surfacing it is this skill's whole job; deciding it is the Maintainer's, in the
contract's `invariantDiscounts` register. Like a conflict, a flag blocks nothing.

If step 3 did not fetch the older tree, say that the drift comparison did not run, so an empty
flag list means "not compared".

## Step 7 — Validate the staged tree

```
python3 tools/bootcamp-transform/validate.py \
  --staging powers/.senzing-bootcamp.staging \
  --tag <tag from step 2> \
  --source <extractedTo from step 2> \
  --report docs/test-records/<tag>-validation.json
```

Validate **after** the reconciliation has been applied, never before: the tree that gets checked
has to be the tree that gets published, adaptations and staged changelog entry included.

Pass `--source`: the checks that compare the produced Power against the release it was built
from — the skill-inventory bijection, the invariant-text comparisons — fail closed without it
rather than quietly passing.

The report is written pass or fail, and it is the machine-readable artifact the release
procedure reads. `tagAllowed` is derived, never assigned: it is true exactly when `status` is
`passed`, which is true exactly when every recorded check passed. Exit status is 0 only in that
case.

Three outcomes, and only the first continues:

- **`passed`** → proceed to step 8. This is the validation-passed result that permits tagging
  *(R13 AC5)*.
- **`failed`** → a structural fault. Stop.
- **`incomplete`** → structurally valid, content-incomplete: a residual Claude-specific model
  reference survived the transformation. Stop.

Both non-passing outcomes block tagging *(R13 AC4)*. Report every finding with its code,
document, and location, then discard staging:

```
python3 -c "
import sys
sys.path.insert(0, 'tools/bootcamp-transform')
from transform import discard_staging
discard_staging(sys.argv[1])
" powers/.senzing-bootcamp.staging
```

Now say what that leaves, because it is the whole point of staging: `powers/senzing-bootcamp/`
holds its prior bytes, every file of it; `CHANGELOG.md` gained nothing, because the entry was
staged and the staging tree is gone; and **the update did not complete** *(R5 AC7)*. The
reconciliation report is still on disk and still worth reading — it says what the update would
have done. Fix the contract and start again from step 1.

## Step 8 — Atomic swap

Only now, and only with `status: passed` in hand. This is the one step that writes outside
staging.

```
python3 -c "
import json, sys
sys.path.insert(0, 'tools/bootcamp-transform')
from transform import TransformError, swap_into_place
try:
    result = swap_into_place(sys.argv[1], sys.argv[2])
except TransformError as error:
    print(json.dumps(error.to_json(), indent=2))
    raise SystemExit(1)
print(json.dumps(result.to_json(), indent=2))
" powers/.senzing-bootcamp.staging powers/senzing-bootcamp
```

The swap is deliberately not a flag on `transform.py`. It is the only operation in the engine
that writes outside staging, so it is a separate call that cannot be reached by adding an
argument to the build.

It publishes by rename — move the old tree aside, move the new one in, delete the old. Every
step is a rename, so the Power is either wholly its old self or wholly its new self and no
partial content is ever visible there. On success the JSON reports `"status": "swapped"` and
`replaced` true; the staging directory is gone, consumed.

This is also the moment the changelog entry becomes real: exactly one new entry, naming the
newer resolved Template_Release tag, published with the tree it describes *(R5 AC8)*.

On `E_WRITE_FAILED` — a permission denial, a target that exists as a file, a staging directory
on a different filesystem than the target — abort and report the write failure. The old tree was
renamed back, the staging tree was discarded, the changelog gained nothing, and the update did
not complete *(R5 AC7)*.

## Step 9 — Report, then hand off to the Test_Checklist

State, plainly:

- the version the Power moved **from** and the resolved Template_Release tag it moved **to**;
- the reconciliation counts by bucket, every conflict, and every flagged invariant discount,
  each with the Maintainer action it is waiting on;
- that one changelog entry was appended to `powers/senzing-bootcamp/CHANGELOG.md` naming the
  new tag;
- the validation `status`, `tagAllowed`, and where both reports were written —
  `docs/test-records/<tag>-reconciliation.json` and `docs/test-records/<tag>-validation.json`;
- that both extracted release trees under your scratch directory can be deleted; they are
  outside the repository and nothing downstream reads them.

Then say the part that matters most, because an updated Power is not yet a releasable one:

> Updating the Power does not permit tagging it. The manual gate does.

Direct the Maintainer to [`docs/test-checklist.md`](../../../../docs/test-checklist.md): work its
17 ordered steps, copy it to `docs/test-records/<tag>.md`, record a pass or fail outcome for
every step — including the nine per-platform cells for steps 2, 10, and 15 across Linux, macOS,
and Windows — and commit that record. An unrecorded platform is a fail, not a blank. The
recorded file, together with the passing validation report from step 7 for that exact version,
is the tagging gate *(R6)*. A previous version's record does not carry over.

## Scope

This skill resolves, transforms, reconciles, validates, publishes, records one changelog entry,
and reports. It holds no bootcamp content, no mapping rules, and no classification logic of its
own — the three-way classification and the invariant-text comparison live in
`tools/bootcamp-transform/reconcile.py`, and what they operate on is declared in the contract.

What belongs elsewhere:

- **Mapping rules, substitutions, generated manifests, the `Invariant_Discount_Register`** — the
  contract, referenced at the same path the create skill uses so a rule change is made in one
  place and both paths reflect it *(R3 AC1, AC4)*.
- **The initial build** — `create-bootcamp-power`. It replaces the target wholesale, preserves
  no local edit, and writes no changelog entry.
- **Resolving a conflict, and deciding a flagged discount** — the Maintainer, in the contract.
  This skill surfaces both and decides neither.
- **Permission to tag** — the `Test_Checklist` record plus the passing validation report, not
  this run.
