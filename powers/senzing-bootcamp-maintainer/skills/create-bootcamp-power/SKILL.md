---
name: "create-bootcamp-power"
description: "Build the Senzing Bootcamp Kiro Power at powers/senzing-bootcamp/ from the latest Senzing bootcamp Claude plugin release, by running the shared transformation engine and publishing its output only after validation passes. Use when the maintainer says 'create the senzing bootcamp power'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-powers-development — as the open workspace: every command below is a repo-relative path into tools/bootcamp-transform/, and the engine, the Transformation_Contract, and the target all live here. Needs Python 3.10+ with the dev extra installed (pyyaml, jsonschema, jinja2). Uses `gh` when it is on PATH and the GitHub REST API otherwise; GITHUB_TOKEN or GH_TOKEN is optional. No Senzing MCP server."
metadata:
  author: "Senzing"
  role: "Create_Skill"
  engine: "tools/bootcamp-transform/"
  contract: "tools/bootcamp-transform/contract.yaml"
---

# Create the Senzing Bootcamp Power

The Maintainer wants an initial `powers/senzing-bootcamp/` built from the latest
Template_Release *(R4 AC1, R14 AC1)*.

This skill is an **orchestrator and nothing else.** Every mapping rule, substitution,
generated manifest, and invariant discount lives in
[`tools/bootcamp-transform/contract.yaml`](../../../../tools/bootcamp-transform/contract.yaml),
and the engine beside it executes them *(R3 AC1, AC2)*. You run the steps below in order and
read their JSON. You do not decide what a file becomes.

Two rules that hold for the whole run:

- **No transformation logic here, and none by hand.** If output is wrong, the contract is
  wrong: change the rule or the substitution set and re-run. Hand-editing a produced file
  makes the create path and the update path disagree, which is exactly what single-sourcing
  the contract prevents *(R3 AC4, AC5)*.
- **Nothing reaches `powers/senzing-bootcamp/` until step 5.** Steps 1–4 read the release and
  write into a staging directory. That is what makes every failure before step 5 leave the
  repository as it was *(R4 AC7, AC8)*.

## Sequence

Resolve → pre-flight target check → transform → validate → atomic swap → report, then the
`Test_Checklist`.

Pick two scratch paths first and reuse them across the steps:

| Path | What it holds |
|---|---|
| `/tmp/senzing-bootcamp-build/` (any directory **outside** this repository) | the extracted release tree |
| `powers/.senzing-bootcamp.staging/` | the produced Power, before it is published |

The staging directory has to be a **sibling of the target**, because the swap in step 5 is a
directory rename and a rename cannot cross filesystems. It must also be absent or empty — the
engine refuses to write into a staging directory that already has content, which is what lets
it delete the whole tree on a failure without ever destroying something it did not create.
Never commit it: a successful run consumes it and a failed run discards it, so it exists only
mid-run.

## Step 1 — Resolve the release

```
python3 tools/bootcamp-transform/resolve_release.py --out /tmp/senzing-bootcamp-build
```

JSON on stdout, narration on stderr. Read `tag`, `extractedTo`, and `pluginRoot` from the JSON
rather than reconstructing them: `extractedTo` is the extracted repository root and the resolved
tag is used character-for-character everywhere downstream *(R1 AC5, R2)*.

The resolver picks the semver maximum among published, non-draft, non-prerelease releases with a
bare semver tag, and fetches the tree at `refs/tags/<tag>` — never `main`. Do not pass
`--min-version`: that flag belongs to the update path, and on the create path there is no current
version to compare against.

If the JSON carries an `error`, the command exited non-zero and **nothing was fetched**. Report
it and stop. Create or modify nothing at `powers/senzing-bootcamp/` *(R4 AC7)*.

| Code | What it means | What to say |
|---|---|---|
| `E_NO_RELEASE` | upstream has no published, non-draft, non-prerelease, semver-tagged release | there is nothing to build from; this is upstream's state, not a fault to retry |
| `E_RESOLVE_FAILED` | no result within 30 s across 3 attempts | the query did not return; retry, and check network or GitHub auth |

The two are deliberately distinct because the Maintainer's response differs: wait for upstream
versus try again.

## Step 2 — Pre-flight the target, before anything is written

Look at `powers/senzing-bootcamp/` now, while nothing has been written and nothing is staged.

**Absent, or present and empty** → proceed to step 3. Do **not** create the directory here. It
is created at swap time and only then *(R14 AC4)*, so a run that fails in step 3 or 4 does not
leave an empty directory behind as evidence of a build that did not happen.

**Present and non-empty** → this is `E_TARGET_EXISTS`. Stop and report the conflict *(R4 AC5)*:

- Name the path exactly: `powers/senzing-bootcamp/`.
- Say what is already there. `powers/senzing-bootcamp/plugin.json` carries the current
  `version` and `extensions["com.senzing.bootcamp"].templateRelease`, and
  `powers/senzing-bootcamp/.build-manifest.json` carries the `templateRelease` of the last
  successful build. Report both against the tag resolved in step 1, so the Maintainer can see
  whether this would be a rebuild of the same release or a change of release.
- Say that a Power already exists, so `update-bootcamp-power` is very likely the skill they
  want: the update path reconciles, preserves every `owner: kiro` file and every local
  adaptation, and appends a changelog entry. **This** skill replaces the directory wholesale and
  preserves nothing that is not reproducible from the contract.
- Then end the turn with exactly one confirmation question, and **wait**. No transform, no
  staging, no touch of the target before the answer arrives.

On **decline**: emit `E_OVERWRITE_DECLINED` and terminate. The existing Power is retained
unchanged, byte for byte *(R4 AC6)*. Nothing was written, so there is nothing to undo.

On **explicit confirmation**: proceed to step 3. Anything short of an explicit yes is a decline.

## Step 3 — Transform into staging

```
python3 tools/bootcamp-transform/transform.py \
  --source <extractedTo from step 1> \
  --tag <tag from step 1> \
  --staging powers/.senzing-bootcamp.staging
```

`--contract` defaults to the contract beside the script, which is the single shared source both
maintainer skills invoke — pass it explicitly only to point at a copy for debugging. Do not pass
`--carry-forward`: it names the existing Power whose `kiro-owned` content the **update** path
carries forward. On the create path that content comes from
`tools/bootcamp-transform/templates/kiro-owned/`.

To see the match plan without writing anything at all, add `--plan-only` first. It reports what
every source file matched and writes nothing, not even to staging.

On success the JSON reports `"status": "staged"`, the counts (enumerated, matched, ignored,
outputs, written), the per-file `ruleId` and `owner` for everything written, and
`.build-manifest.json` recording the `templateRelease` and a SHA-256 per output. Narration also
lists any `unmaterialized` destination — a `kiro-owned` rule with no authored content behind it.
Read those warnings; a missing authored destination means a skill or asset set the contract
promised is simply not there.

On any `error`, the staging tree was discarded and the target was never opened.

| Code | What it means | What to do |
|---|---|---|
| `E_UNMATCHED_FILE` | a source file matches no rule and no `ignore` entry *(R3 AC6)* | genuinely new upstream content: add a rule or an `ignore` entry to the contract, then re-run. Never route it by hand |
| `E_MISSING_ASSET` | a ported script references a vendored asset absent from the source | report the path it names; fix the contract's asset rules or raise it upstream |
| `E_WRITE_FAILED` | staging could not be created or written | report the path; the repository is unchanged |
| `E_TRANSFORM_FAILED` | any other halting fault | report the code and message as given |

## Step 4 — Validate the staged tree

```
python3 tools/bootcamp-transform/validate.py \
  --staging powers/.senzing-bootcamp.staging \
  --tag <tag from step 1> \
  --source <extractedTo from step 1> \
  --report docs/test-records/<tag>-validation.json
```

Pass `--source`: the checks that compare the produced Power against the release it was built
from — the skill-inventory bijection, the invariant-text comparisons — fail closed without it
rather than quietly passing.

The report is written pass or fail, and it is the machine-readable artifact the release procedure
reads. `tagAllowed` is derived, never assigned: it is true exactly when `status` is `passed`,
which is true exactly when every recorded check passed. Exit status is 0 only in that case.

Three outcomes, and only the first continues:

- **`passed`** → proceed to step 5. This is the validation-passed result that permits tagging
  *(R13 AC5)*.
- **`failed`** → a structural fault. Stop.
- **`incomplete`** → structurally valid, content-incomplete: a residual Claude-specific model
  reference survived the transformation. Stop.

Both non-passing outcomes block tagging *(R13 AC4)* and both stop this run at exactly the same
place. Report every finding with its code, document, and location, then discard staging:

```
python3 -c "
import sys
sys.path.insert(0, 'tools/bootcamp-transform')
from transform import discard_staging
discard_staging(sys.argv[1])
" powers/.senzing-bootcamp.staging
```

`powers/senzing-bootcamp/` is untouched — absent if it was absent, and holding its prior bytes
if step 2 was confirmed *(R4 AC8)*. Fix the contract and start again from step 1.

## Step 5 — Atomic swap

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

It creates the target's parent when absent *(R14 AC4)* and publishes by rename — move any old
tree aside, move the new one in, delete the old. Every step is a rename, so the target is either
wholly its old self or wholly its new self and no partial content is ever visible there
*(R4 AC8)*. On success the JSON reports `"status": "swapped"` and whether an existing tree was
`replaced`; the staging directory is gone, consumed.

On `E_WRITE_FAILED` — a permission denial, a target that exists as a file, a staging directory on
a different filesystem than the target — abort and report the write failure. The old tree was
renamed back, the staging tree was discarded, and the repository is unchanged *(R14 AC5)*. No
partial content is left at `powers/senzing-bootcamp/` *(R4 AC8)*.

## Step 6 — Report, then hand off to the Test_Checklist

State, plainly:

- the resolved Template_Release tag and `sourceRef`;
- the target path, `powers/senzing-bootcamp/`, and whether an existing tree was replaced;
- the file counts from step 3 and any `unmaterialized` destinations;
- the validation `status`, `tagAllowed`, and where the report was written;
- that the extracted release tree under your scratch directory can be deleted; it is outside the
  repository and nothing downstream reads it.

Then say the part that matters most, because a built Power is not yet a releasable one:

> Building the Power does not permit tagging it. The manual gate does.

Direct the Maintainer to [`docs/test-checklist.md`](../../../../docs/test-checklist.md): work its
17 ordered steps, copy it to `docs/test-records/<tag>.md`, record a pass or fail outcome for every
step — including the nine per-platform cells for steps 2, 10, and 15 across Linux, macOS, and
Windows — and commit that record. An unrecorded platform is a fail, not a blank. The recorded
file, together with the passing validation report from step 4 for that exact version, is the
tagging gate *(R6)*.

## Scope

This skill resolves, transforms, validates, publishes, and reports. It holds no bootcamp
content, no mapping rules, and no reconciliation logic.

What belongs elsewhere:

- **Mapping rules, substitutions, generated manifests, invariant discounts** — the contract.
- **Reconciling a newer release into an existing Power, and the changelog entry that records it**
  — `update-bootcamp-power`. The create path writes no changelog entry and preserves no local
  edit.
- **Apache-2.0 in the produced Power's `plugin.json`, the Agent Plugins schemas, the Senzing MCP
  declaration** — generated by the contract's `manifest` and `mcp` rules and checked in step 4
  *(R4 AC2, AC3, AC4)*. If any of the three is wrong, the template or the contract is where it
  gets fixed.
