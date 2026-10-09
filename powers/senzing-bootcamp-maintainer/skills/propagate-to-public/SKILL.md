---
name: "propagate-to-public"
description: "Propagate the built Senzing Bootcamp Kiro Power at powers/senzing-bootcamp/ into an existing working tree of the public repository Senzing/senzing-bootcamp-kiro-power, through the Publication_Contract: mirror only what a bootcamper installs, rewrite development self-references, and stop at the working tree — no commit, no push, no branch, no pull request, no release, no issue. The Maintainer reviews the diff and publishes by hand. Use when the maintainer says 'propagate the senzing bootcamp power to public'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-power-development — as the open workspace, because the Power, the Publication_Contract, and the Propagator all live here. Requires an existing local checkout of Senzing/senzing-bootcamp-kiro-power whose origin is that repository; this skill never clones. Needs git and Python 3.10+ with the dev extra installed (pyyaml); jsonschema additionally, to run the public repository's own gate. No network access, no `gh`, and no Senzing MCP server."
metadata:
  author: "Senzing"
  role: "Propagate_Skill"
  engine: "tools/bootcamp-transform/"
  contract: "tools/bootcamp-transform/publication.yaml"
  publication: "Senzing/senzing-bootcamp-kiro-power"
---

# Propagate the Senzing Bootcamp Power to public

The Maintainer wants the built `powers/senzing-bootcamp/` in front of them as a reviewable diff
in the public repository's working tree. This is the canonical family operation
`propagate-to-public`, and it comes after [`release`](../release/SKILL.md).

Every difference between the two repositories lives in
[`tools/bootcamp-transform/publication.yaml`](../../../../tools/bootcamp-transform/publication.yaml),
and the Propagator beside it,
[`propagate.py`](../../../../tools/bootcamp-transform/propagate.py), executes them. You run it and
read its JSON. You do not decide what a file becomes, and you do not hand-edit the result.

## ⛔ Where this stops

At the public **working tree**. No commit, no push, no branch, no pull request, no release, no
tag, no issue, and no edit to the public repository's own files — its README, CHANGELOG,
workflows, `.github/` tooling, `.vscode/cspell.json`. The Propagator writes only inside
`senzing-bootcamp/` of the checkout.

That boundary is the point, not a missing feature. The diff the Maintainer reviews before
anything leaves this machine is the last gate before a bootcamper sees the change, and an
operation that pushed or opened the pull request itself would move that gate to after the push.
It would also make the public repository's history the product of a command rather than of a
decision. A public release is created after its version has been tested, and that is a human
judgment this skill cannot make.

## Step 1 — Find the public working tree

Ask for the path to the Maintainer's checkout of `Senzing/senzing-bootcamp-kiro-power` if they
did not give one. **Do not guess it, and do not clone it.** If there is no checkout, say so and
let the Maintainer create one; a clone made here is a write this operation does not make.

Ideally its working tree is clean, so the diff this produces is the whole diff. If it is not,
report `git -C <target> status --short` before going further.

## Step 2 — Confirm what is being propagated

```
python3 -c "import json;print(json.load(open('powers/senzing-bootcamp/plugin.json'))['version'])"
git tag --points-at HEAD
```

Propagating a tree no tag names breaks the version pairing between the two repositories. If HEAD
carries no tag for that version, say so: [`release`](../release/SKILL.md) is what makes a version
exist, and whether to propagate an unreleased tree anyway is the Maintainer's call.

## Step 3 — Propagate through the Publication_Contract

Dry run first. It writes nothing, anywhere:

```
python3 tools/bootcamp-transform/propagate.py \
  --power powers/senzing-bootcamp \
  --target <public working tree> \
  --expect-version <version> \
  --check
```

`--expect-version` is not optional in practice: propagating the wrong version is the one mistake
nothing downstream catches, because every later gate checks the tree against itself.

Read the report. `adaptations` is every difference between the two repositories, each with its
reason; `changedPaths` is what the working tree will show. Then drop `--check`, and keep the
report somewhere **outside** both repositories so the Maintainer has the reasons when they
publish:

```
python3 tools/bootcamp-transform/propagate.py \
  --power powers/senzing-bootcamp \
  --target <public working tree> \
  --expect-version <version> \
  --report /tmp/senzing-bootcamp-propagation-report.json
```

### When it refuses

Every refusal leaves the target untouched. None of them is worked around here.

| Code | What it means | What to do |
|---|---|---|
| `E_NOT_A_PUBLICATION` | the target has no `.git`, or its `origin` is not the public repository | the wrong path. Ask for the right one |
| `E_SUBSTITUTION_UNAPPLIED` | a declared substitution matched nothing | the build reworded the line the rule was written against. Update the rule in `publication.yaml` |
| `E_RULE_INERT` | an `exclude` or `dropKeys` rule matched nothing | the build stopped emitting what the rule removes. Confirm that is intended, then retire the rule |
| `E_FORBIDDEN_REFERENCE` | the tree still names this repository | ⛔ a content fix, not a propagation fix: the reference is in built output, so fix it in the template or `contract.yaml` and rebuild |
| `E_MANIFEST_INCOMPLETE` | manifest and tree disagree | the build is inconsistent. Rebuild; never recompute digests to get past it |
| `E_VERSION_MISMATCH` | `plugin.json` is not the version named | one of the two is wrong. Find out which before touching either |

⛔ **`E_SUBSTITUTION_UNAPPLIED` and `E_RULE_INERT` look like pedantry and are the codes that
matter most.** A rule that matches nothing is an adaptation that used to happen and silently no
longer does, and the only symptom is the thing it prevented reappearing.

## Step 4 — Run the public repository's own gate, read-only

```
cd <public working tree> && python3 -B .github/tools/validate_power.py senzing-bootcamp
```

Run it from their checkout, as their CI does, so the version you run is the version that will
judge the pull request.

`-B` keeps Python from writing bytecode into their tree. All of its checks must pass; it catches
what our validator does not. ⛔ A failure is a content defect, and the fix is upstream. Their
`refresh_build_manifest.py` exists and you are not running it: recomputing a digest to turn this
green removes the only thing reporting the defect.

## Step 5 — Report, and stop

Tell the Maintainer: the version, the adaptation count, `changedPaths`, the result of their
validator, and where the report is. Then point them at the diff:

```
git -C <public working tree> status --short
git -C <public working tree> diff --stat
```

Publishing is theirs, by hand, after review: committing `senzing-bootcamp/`, writing the public
root `CHANGELOG.md` for bootcampers, pushing, the pull request, and the public tag. Do none of
it unless the Maintainer explicitly asks, and if they do, treat it as a separate request rather
than as part of this skill.

## Scope

This skill mirrors a built, already-released Power into one directory of another repository's
working tree, and reports. It holds no adaptation logic — that is `publication.yaml` — and no
content rules, which are in `contract.yaml` one layer further back. It does not build and does
not release: `update-bootcamp-power` and [`release`](../release/SKILL.md) run before it.
