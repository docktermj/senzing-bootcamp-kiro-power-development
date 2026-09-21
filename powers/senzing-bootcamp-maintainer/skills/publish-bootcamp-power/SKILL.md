---
name: "publish-bootcamp-power"
description: "Publish the Senzing Bootcamp Kiro Power at powers/senzing-bootcamp/ to the public repository Senzing/senzing-bootcamp-kiro-power, by opening a version-update issue, migrating the built tree onto a review branch through the Publication_Contract, updating the public CHANGELOG, and opening a pull request that is deliberately left unmerged. Use when the maintainer says 'publish the senzing bootcamp power'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-power-development — as the open workspace, because the Power, the Publication_Contract, and the Publisher all live here. Requires a working `gh` authenticated against github.com with `repo` scope, and push access to Senzing/senzing-bootcamp-kiro-power. Needs Python 3.10+ with the dev extra installed (pyyaml); jsonschema additionally, to run the publication repository's own gate locally. Network access to github.com. No Senzing MCP server."
metadata:
  author: "Senzing"
  role: "Publish_Skill"
  engine: "tools/bootcamp-transform/"
  contract: "tools/bootcamp-transform/publication.yaml"
  publication: "Senzing/senzing-bootcamp-kiro-power"
---

# Publish the Senzing Bootcamp Power

The Maintainer wants the built `powers/senzing-bootcamp/` to reach bootcampers. Bootcampers
install from `Senzing/senzing-bootcamp-kiro-power`, so publishing means getting the tree onto a
branch there, in reviewable shape, with the public changelog updated — and **stopping before the
merge**.

This skill is an **orchestrator**. Every adaptation between the two repositories lives in
[`tools/bootcamp-transform/publication.yaml`](../../../../tools/bootcamp-transform/publication.yaml)
and the Publisher beside it executes them. You run the steps and read their JSON. You do not
decide what a file becomes, and you do not hand-edit the tree you are publishing.

Three rules hold for the whole run:

- ⛔ **You do not merge, and you do not tag.** The pull request exists so the Maintainer can
  install the branch and work the `Test_Checklist` against it. Merging is their call after that
  passes, and the release tag follows the merge. A skill that merges its own pull request has
  removed the only gate between a broken Power and every bootcamper.
- **Nothing is adapted by hand.** If the published tree is wrong, either the
  Publication_Contract is wrong or the build is. Fix the one that is, and re-run. A hand-edit
  to the published tree is reverted by the next publication and, worse, silently.
- **The publication repository's root is its own.** Its README, its workflows, its contributor
  documents, its `.github/` tooling — the Publisher never writes outside
  `senzing-bootcamp/`. Only steps 6 and 7 touch anything else there, and only two files.

## Sequence

Confirm the release → open the issue → branch → publish through the contract → run *their* gate →
public changelog → commit and push → pull request, unmerged.

Pick the scratch path first and reuse it:

| Path | What it holds |
|---|---|
| `/tmp/senzing-bootcamp-publication/` (any directory **outside** both repositories) | the checkout of the publication repository |

The checkout goes outside this repository so that nothing in it is ever mistaken for content of
this one — no nested `.git`, and no chance of committing their tree into our history.

## Step 1 — Establish that this version is publishable

Read the version being published from the built Power, and confirm the release gate for that
exact version:

```
python3 -c "import json;print(json.load(open('powers/senzing-bootcamp/plugin.json'))['version'])"
```

Then check three things about that version, and **report each one to the Maintainer before going
further**:

| What | Where | What blocks |
|---|---|---|
| Schema validation | `docs/test-records/<version>-validation.json` | `status` is not `passed`, or `tagAllowed` is false |
| Manual testing | `docs/test-records/<version>.md` | any step or platform cell still `_unrecorded_` |
| Tag agreement | `git tag --points-at HEAD` | the tree being published is not the tree the tag names |

⚠️ **An unrecorded `Test_Checklist` does not stop this skill, and it does stop the merge.** The
checklist is worked against an *installed* Power, and installing it is what the branch is for —
so on the first publication of a version the record is legitimately blank. Say so plainly in the
pull request (step 8 does), and never let the pull request imply the gate is satisfied when it is
not. What must not happen is a merge on a blank record, and that is why this skill does not merge.

If the tree does not match the tag, say which is ahead. Publishing a tree that no tag names
breaks the version pairing both repositories exist to keep, and the fix is a decision about
tagging that belongs to the Maintainer, not to this skill.

## Step 2 — Open the version-update issue

Every branch in the publication repository is traceable to an issue, and the branch name carries
the issue number, so the issue comes first.

```
gh issue create --repo Senzing/senzing-bootcamp-kiro-power \
  --title "Update to <version>" \
  --body "<what the release brings, and where it came from>"
```

Read the issue number out of the URL it prints. That number is `<issue>` for the rest of the run.

The body is for a reader of the public repository. Say what the release changes for a bootcamper
and name the upstream template release it was built from — that reference is deliberate, and it
is the one thing about the build that a public reader legitimately needs, because it is how the
two projects stay synchronized. Do not describe this repository, its contract, or its tooling.

## Step 3 — Check out the publication repository and branch

```
gh repo clone Senzing/senzing-bootcamp-kiro-power /tmp/senzing-bootcamp-publication
git -C /tmp/senzing-bootcamp-publication switch --create <issue>-<github-username>-<n>
```

The branch name is `<issue>-<github-username>-<n>`:

- `<issue>` — the number from step 2.
- `<github-username>` — `gh api user --jq .login`. Not a guess, and not the git `user.name`,
  which is a display name and often has a space in it.
- `<n>` — a monotonically increasing counter, **scoped to the issue**, starting at 1. Take it
  from what already exists rather than from memory:

  ```
  git -C /tmp/senzing-bootcamp-publication branch --all --list "*<issue>-<github-username>-*"
  ```

  The next `<n>` is one above the highest already present, counting remote branches as present.
  A branch that exists and looks unused is still taken: reusing its name rewrites whatever is on
  it, and a stale branch is cheap while a lost one is not.

## Step 4 — Publish through the Publication_Contract

Dry run first. It writes nothing, anywhere:

```
python3 tools/bootcamp-transform/publish.py \
  --power powers/senzing-bootcamp \
  --target /tmp/senzing-bootcamp-publication \
  --expect-version <version> \
  --check
```

`--expect-version` is not optional in practice: publishing the wrong version is the one mistake
nothing downstream catches, because every gate afterwards checks the tree against *itself*.

Read the report. `adaptations` is the whole list of differences between the two repositories, each
with the reason it exists; `changedPaths` is what the branch will contain. Then run it for real by
dropping `--check`, and add `--report` so the reason for every adaptation is on disk for the pull
request:

```
python3 tools/bootcamp-transform/publish.py \
  --power powers/senzing-bootcamp \
  --target /tmp/senzing-bootcamp-publication \
  --expect-version <version> \
  --report /tmp/senzing-bootcamp-publication-report.json
```

### When it refuses

Every one of these leaves the target untouched. None of them is worked around here.

| Code | What it means | What to do |
|---|---|---|
| `E_SUBSTITUTION_UNAPPLIED` | a declared substitution matched nothing | the build reworded the line the rule was written against. Update the rule in `publication.yaml` to the text the build now emits |
| `E_RULE_INERT` | an `exclude` or `dropKeys` rule matched nothing | the build stopped emitting what the rule removes. Confirm that is intended, then retire the rule |
| `E_FORBIDDEN_REFERENCE` | the tree still names this repository | ⛔ **a content fix, not a publication fix.** The reference is in built output, so it comes from the template or from `contract.yaml`. Fix it there and rebuild |
| `E_MANIFEST_INCOMPLETE` | manifest and tree disagree | the build is inconsistent. Do not recompute digests to move past this; rebuild |
| `E_VERSION_MISMATCH` | `plugin.json` is not the version you named | one of the two is wrong. Find out which before touching either |

⛔ **`E_SUBSTITUTION_UNAPPLIED` and `E_RULE_INERT` are the codes that matter most, and they look
like pedantry.** A rule that matches nothing is not harmless: it is an adaptation that used to
happen and no longer does, and the only symptom is the thing it prevented reappearing. Release
0.5.3 shipped a `later porting phase` aside into bootcamp content in exactly this way — a
`catalogue`/`catalog` spelling change in the upstream template took a Transformation_Contract
substitution from applying to matching nothing, and nothing failed. Treat both codes as findings
about the build, never as noise to silence.

## Step 5 — Run the publication repository's own gate

The tree now has to satisfy *their* validator, not ours. Run it from their checkout, so the
version you run is the version their CI will run:

```
cd /tmp/senzing-bootcamp-publication && python3 .github/tools/validate_power.py senzing-bootcamp
```

All six checks must pass. This is the step that catches what our validator does not: their
`residual-upstream` check scans for port-status language and for upstream client names that our
`validate.py` residual catalog does not carry, and it reads the shipped PDF's extracted text
rather than only hashing it.

⛔ **A failure here is a content defect, and the fix is upstream.** Their
`.github/tools/refresh_build_manifest.py` exists and you are not running it: recomputing a digest
to make this go green leaves the defect in place and removes the only thing that was reporting
it. Fix `contract.yaml` or the template, rebuild the Power, and start this step again.

## Step 6 — Update the public CHANGELOG

`CHANGELOG.md` at the publication repository's root is the only content file this skill writes by
hand, and it is theirs, not ours. It follows Keep a Changelog, it is addressed to bootcampers, and
it is not the Power's own `CHANGELOG.md` — the Publication_Contract excludes that one for exactly
this reason.

Write a new `## [<version>] - <date>` section above the previous release, in their existing style,
and add the release-tag link definition at the foot beside the others. Describe what changes for
someone taking the bootcamp: new skills, changed behavior, fixes they would notice. Name the
upstream template release the version was built from. Say nothing about this repository, its
contract, its engine, or its tests.

Then check `.vscode/cspell.json`: their spellcheck workflow runs on every pull request, and a new
proper noun in your changelog entry fails it. Add the word rather than rewording around it.

## Step 7 — Commit and push

Stage deliberately. `git add -A` in a checkout you did not create is how an unrelated file
travels:

```
git -C /tmp/senzing-bootcamp-publication add senzing-bootcamp CHANGELOG.md
git -C /tmp/senzing-bootcamp-publication status --short
git -C /tmp/senzing-bootcamp-publication commit -m "#<issue> Update to <version>"
git -C /tmp/senzing-bootcamp-publication push --set-upstream origin <branch>
```

Read the `status --short` output before committing. Anything outside `senzing-bootcamp/`,
`CHANGELOG.md`, and `.vscode/cspell.json` does not belong in this commit.

The commit subject leads with `#<issue>`, which is the convention already in that repository's
history and what links the commit to the issue.

## Step 8 — Open the pull request, and leave it alone

```
gh pr create --repo Senzing/senzing-bootcamp-kiro-power \
  --base main --head <branch> \
  --title "#<issue> Update to <version>" \
  --body "<see below>"
```

The body has to carry four things, because they are what a reviewer cannot reconstruct:

1. **What moved**, in counts: files changed, skills added, the upstream release it came from.
2. **Every publication adaptation, with its reason.** Take them from the `--report` JSON. This is
   the justification their `refresh_build_manifest.py` asks for in the pull request — say, for
   each recomputed digest, why the change could not be made upstream.
3. **The state of the `Test_Checklist`** for this version, honestly. If it is unrecorded, say it
   is unrecorded and say that working it against this branch is what the branch is for.
4. **That the pull request is deliberately not merged**, and what has to happen before it is.

Then stop. Do not merge, do not enable auto-merge, do not tag, and do not close the issue.

Report to the Maintainer: the issue URL, the branch name, the pull request URL, the adaptation
count, the result of their validator, and anything from step 1 that is still outstanding.

## Scope

This skill resolves nothing, transforms nothing, and validates no content itself. It moves a
built, already-validated Power into the publication repository and opens it for review. It holds
no bootcamp content, no mapping rules, and no adaptation logic — those are in
`publication.yaml`, and the content rules are in `contract.yaml` one layer further back.

It does not build. If `powers/senzing-bootcamp/` is absent or stale, `create-bootcamp-power` and
`update-bootcamp-power` own that, and this skill runs after them.
