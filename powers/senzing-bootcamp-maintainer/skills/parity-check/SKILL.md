---
name: "parity-check"
description: "Compare the committed Senzing Bootcamp Kiro Power against a tagged release of the parent Senzing bootcamp Claude plugin and file GitHub issues in this repository describing the delta needed to reach parity — without running the transform and without writing to the parent. Use when the maintainer says 'check the senzing bootcamp power for parity'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-power-development — as the open workspace: the pinned parent release is read from the committed Power here, and the resolver lives in tools/bootcamp-transform/. Needs Python 3.10+ with the dev extra installed (pyyaml) to run resolve_release.py. Needs network access and `gh` authenticated with issue-write on this repository and read on the parent repositories; the GitHub REST API is the fallback when `gh` is absent. No Senzing MCP server."
metadata:
  author: "Senzing"
  role: "Parity_Check"
  parentDevelopmentRepository: "docktermj/senzing-bootcamp-claude-plugin-development"
  parentPublicRepository: "Senzing/senzing-bootcamp-claude-plugin"
---

# Check the Senzing Bootcamp Kiro Power for parity

This repository is a **child** of the Senzing bootcamp Claude plugin. Curriculum
features and fixes land in the parent first; this port brings them across, tests, and
publishes. `parity-check` is the **only** path for a parent-to-child change: it does
not pull anything directly — it **files GitHub issues here** describing the delta, so
every change is reviewable and tracked before it is applied.

## What this is, and what it is not

- It **detects and files**. It never runs the transform and never edits
  `powers/senzing-bootcamp/`. Applying a release is `update-bootcamp-power`'s job, and
  a parity issue's acceptance is that the port was brought level by running it.
- It is **pull, not push**: it writes issues into *this* repository only. It never
  writes to the parent. Filing upstream is the separate escalation path (issue #5);
  the two directions never live in one command.
- It is distinct from the `watch-upstream-release.yml` workflow, which only *notices*
  that a newer release exists and files one tracking issue. `parity-check` is the
  maintainer-run step that turns that into a reviewed, per-change delta.

## The pinned parent release comes from provenance

The release this port is currently level with is recorded in the committed Power, per
the provenance convention (`docs/provenance-convention.md`, issue #9). Read it — do
**not** introduce or read a `PARENT_VERSION` file; that earlier proposal is superseded
by the in-manifest block:

```
python3 - <<'PY'
import json, pathlib
power = pathlib.Path("powers/senzing-bootcamp")
plugin, manifest = power / "plugin.json", power / ".build-manifest.json"
pinned = ""
if plugin.is_file():
    ext = (json.loads(plugin.read_text()).get("extensions") or {}).get("com.senzing.bootcamp") or {}
    pinned = str(ext.get("templateRelease") or "").strip()
if not pinned and manifest.is_file():
    pinned = str(json.loads(manifest.read_text()).get("templateRelease") or "").strip()
print(pinned or "UNPINNED")
PY
```

If nothing is pinned, stop and report it: there is no baseline to compute a delta
against, and that is a defect in the committed Power, not a parity gap.

## Steps

### 1. Resolve the target parent release — a tag, never HEAD

A port must be level with a specific version; comparing against a branch head would
let a half-finished parent change propagate. Use the resolver, which only ever fetches
a published, non-draft, non-prerelease semver **tag**:

```
python3 tools/bootcamp-transform/resolve_release.py --min-version "<pinned>" --out "$TMPDIR/parent"
```

- `error: E_ALREADY_CURRENT` — the parent's latest release is not newer than the
  pinned one. **File nothing** and report that the port is at parity. This is the
  already-current outcome, and it is the resolver's tested predicate, not a judgment
  made here.
- A resolved record — its `tag` is the **target**. Everything from just above the
  pinned release up to and including the target is the delta to account for.

### 2. Characterize the delta from the parent, per release

For each parent release greater than the pinned one, up to the target, read what it
carries. Both parent repositories are in scope:

- `docktermj/senzing-bootcamp-claude-plugin-development` — the context, rationale, and
  tests behind each change (its release notes, its `CHANGELOG.md`, the issues and pull
  requests closed between the two tags).
- `Senzing/senzing-bootcamp-claude-plugin` — the runtime trim that actually ships, so
  the delta is described in terms of what a bootcamper receives.

Read release notes and the changelog with `gh release view <tag> --repo <parent>` and
`gh api`. Group the delta into coherent changes a maintainer can act on one at a time,
rather than one undifferentiated "update to <tag>" lump — a reviewable delta is the
whole point.

### 3. Check open escalations before filing

Before writing anything, list this repository's open issues that were escalated
upstream (issue #5's `escalate-to-parent` path, once it exists) and the parent issues
they map to. If a change in the delta is the parent's fix for something this repo
escalated, **link or close that escalation** rather than filing a duplicate parity
issue for the same thing — the round trip (escalate up, fix in the parent, bring the
fix down) is the system working, and it must not leave two open issues for one problem.
When no escalations exist yet, record that you checked and continue.

### 4. File one parity issue per coherent change

For each change, `gh issue create` in **this** repository with:

- **what** changed upstream and **why** (cite the parent issue or pull request URL, so
  the cross-reference exists in both directions);
- **which parent release** carries it, and the target tag the port must reach;
- **how to bring it across** — for most changes this is "run `update-bootcamp-power` to
  `<target>`", which re-runs the shared transform, reconciles, and rewrites the
  provenance block; a change that needs a Kiro-side adaptation (a hook, a substitution,
  a parity-tier decision) says so;
- **acceptance**: the Power is rebuilt to `<target>` and its recorded provenance shows
  `<target>`.

Closing a parity issue therefore means the port was brought to that release through
`update-bootcamp-power`, which is what advances the pinned provenance — so the pinned
release and the closed parity issues stay in step by construction. (A future
`/implement-github-issue` runner may automate the close-to-advance link; the advance
itself is inherent to the update that the issue's acceptance requires.)

### 5. Bring MCP reductions down as parity issues too

When the Senzing MCP server absorbs a fact the plugin used to carry, the **parent**
runs its `delegate-to-mcp-server` step and the reduction lands in a parent release.
File that reduction as a parity issue here like any other delta. Children deliberately
do **not** get a `delegate-to-mcp-server` command: Senzing facts are reasoned about in
one place, the parent, and reach this port only through parity.

## Rules

- Compare against a tagged parent release, never HEAD (step 1).
- Pull, not push: file issues **here** only; never write to the parent.
- Provenance is the single source of the pinned release (issue #9); never read or
  create a `PARENT_VERSION` file.
- An already-current repository files nothing.
- This skill runs the transform on nothing and edits `powers/senzing-bootcamp/` never;
  applying a release is `update-bootcamp-power`'s job.

## Who owns what

- **`parity-check`** — resolves the pinned and target releases, computes the delta, and
  files reviewable parity issues. It applies nothing.
- **`update-bootcamp-power`** — applies a release: re-runs the transform, reconciles,
  rewrites provenance. It is how a parity issue is discharged.
- **The maintainer** — decides which filed parity issues to implement, and in what
  order.
