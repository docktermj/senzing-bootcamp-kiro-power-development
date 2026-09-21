---
name: implement-github-issue
description: 'Implement a tracked GitHub issue in this repository end to end: read the issue, work on a new branch, route every fix to the source that produces the shipped file, run the tests, and open a pull request that closes the issue. For a parity issue it advances the pinned parent-release provenance by running the update path. Use when the maintainer says "implement github issue <number>" or names an issue to work. Maintainer tool for developing this repository — not part of the bootcamper experience and never ported into the Power.'
license: 'Apache-2.0'
---

# Implement a GitHub issue

This is a **maintainer** tool for developing the Senzing Bootcamp Kiro Power. Given a
GitHub issue in this repository, it carries the issue from *reported* to
*pull-request-open*: read the issue, implement it on a branch, verify, and open a PR that
closes it. It is the generic runner that `parity-check` (#6) and `escalate-to-parent` (#5)
forward-reference — the sibling of `feedback-to-issues`, which *files* issues this skill
then *implements*.

## Invocation

`/implement-github-issue <number>` — or a full issue URL. Anything after the command arrives
as `$ARGUMENTS`; treat a number or issue URL as the issue to work, and anything else as
scoping notes. Empty means ask which issue.

## ⛔ The constraint that shapes every change

**`powers/senzing-bootcamp/` is generated output. Never hand-edit it.** It is produced from
an upstream Template_Release by `tools/bootcamp-transform/` according to `contract.yaml`, and
the determinism gate (`.github/workflows/verify-build-determinism.yml`) asserts the committed
tree is a byte-identical rebuild of its pinned release. A change made there is deleted by the
next rebuild and rejected by CI before then. Every fix has exactly one real home — find it
from evidence, not from where the symptom appeared.

## Step 1: Read the issue

`gh issue view <number> --repo docktermj/senzing-bootcamp-kiro-power-development` (REST API
otherwise). Extract the acceptance criteria, the scope, and any cross-referenced issues or
PRs. If the issue is a parity issue filed by `parity-check`, note the **target parent
release** it names — Step 4 depends on it. If the issue is unclear enough that you would be
guessing at acceptance, say so and stop rather than implement the wrong thing.

## Step 2: Understand before changing

Read the code and docs the issue touches before proposing an edit. For a fix whose symptom
appears in a shipped file, look that path up in `powers/senzing-bootcamp/.build-manifest.json`
— its `ruleId`/`owner`/`sourcePath` triple names the producing home exactly:

- `owner: template` → the substitution sets its rule declares in `contract.yaml`, and the
  upstream file at `sourcePath`;
- `owner: kiro` → the authored file under `tools/bootcamp-transform/templates/kiro-owned/`;
- a generated manifest (`plugin.json`, `mcp.json`) → the `.j2` template plus its verifier in
  `transform.py`.

Engine behavior lives in `tools/bootcamp-transform/*.py`; host-native guarantees live in the
`KINV` ledger (`specs/INVARIANTS.md`); the disposition of an inherited `INV-NNN` lives in the
`invariantDiscounts` register in `contract.yaml`. `docs/porting-framework.md` maps all nine
components to their homes.

## Step 3: Work on a new branch, never main

Create a branch off `main` — the repository's convention is `<issue-number>-<owner>-<n>`
(for example `17-docktermj-1`). Never commit to `main`, never force-push, never skip hooks.
Make the change in the producing home Step 2 identified, matching the surrounding style, and
keep the change scoped to the issue.

## Step 4: A parity issue is implemented by running the update path

For a parity issue — "bring the port level with parent release *X*" — the implementation is
**not** a hand edit. Run the update path (`update-bootcamp-power`) to release *X*: it
re-runs the transform, reconciles, and **rewrites the in-manifest provenance**
(`extensions["com.senzing.bootcamp"].templateRelease`, mirrored in `.build-manifest.json`) to
*X*. That is how the pinned parent release advances when the parity issue closes — the sense
`parity-check` (#6) intends. There is no `PARENT_VERSION` file to write; provenance is the
in-manifest block (`docs/provenance-convention.md`, #9). A non-parity issue changes no
provenance. If implementing brings down a parent fix that resolves an open escalation
(`escalate-to-parent`, #5), link or close that escalation rather than leaving a duplicate.

## Step 5: Verify

- Run the suite: `python3 -m pytest -m "not integration" -q`. The `integration` marker
  reaches the network and the real upstream repository; run it only when the issue needs it.
- For any change in a `contract`, `kiro-owned`, or `engine` home, confirm the change is
  **reproducible**: a fresh build of the pinned release reproduces the committed Power, which
  is what the determinism gate checks. A change that only holds when hand-applied is not done.
- Fix failures before opening the PR; do not open a PR over a red suite.

## Step 6: Capture any durable Kiro-native guarantee

If the work establishes a rule that must stay true of the Kiro port — a new packaging
guarantee, a hook-parity decision, an interaction-gap contract — account for it against the
`KINV` ledger (`specs/INVARIANTS.md`), by exactly one of: a `KINV` **registered** (added with
the next unused id and indexed in the same change, per that file's maintenance rules), or a
plain statement in the PR that the work **establishes no Kiro-native invariant**. Silence is
not an option. This is the parent's invariant-capture discipline, scoped to what this repo
owns; `INV-NNN` remain the parent's and are never minted here.

## Step 7: Open the PR that closes the issue

Push the branch and open a PR whose body states what changed, why, how it was verified, and
any deviation from the issue as written. End the body with `Closes #<number>` so the merge
closes the issue. Keep the subject in the repository's convention (`#<number> <summary>`).
Do not merge; the maintainer reviews and merges.

## What this skill does not do

- It does not file issues — `feedback-to-issues` does that, and `escalate-to-parent` is the
  only skill that writes an issue into another repository.
- It does not hand-edit `powers/senzing-bootcamp/`, and it does not merge its own PR.
