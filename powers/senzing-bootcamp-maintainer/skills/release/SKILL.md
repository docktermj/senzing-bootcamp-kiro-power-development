---
name: "release"
description: "Release a version of the Senzing Bootcamp Kiro Power in this development repository: verify that every place asserting the version agrees, enforce the tagging gate (a passing ValidationReport and a fully recorded Test_Checklist for exactly that version), write the CHANGELOG.md entry, commit it, and create the annotated git tag — as one operation, with no path that moves one without the others. Touches this repository only; never pushes, and never writes to the public repository. Use when the maintainer says 'release the senzing bootcamp power'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-power-development — as the open workspace, on a clean `main`, because the version sites, the test records, and the release script all live here. Needs git and Python 3.10+. No network access, no `gh`, and no Senzing MCP server."
metadata:
  author: "Senzing"
  role: "Release_Skill"
  engine: "tools/bootcamp-transform/"
  script: "tools/bootcamp-transform/release.py"
---

# Release the Senzing Bootcamp Power

The Maintainer wants a tested version of `powers/senzing-bootcamp/` to **exist**: a tag in
this repository naming the commit that carries it, and a changelog entry written with that
tag. This is the canonical family operation `release`. The step after it is
[`propagate-to-public`](../propagate-to-public/SKILL.md), and pushing is the Maintainer's.

The work is done by
[`tools/bootcamp-transform/release.py`](../../../../tools/bootcamp-transform/release.py), not by
following steps here. The operation has to be all-or-nothing, and a procedure a model follows
step by step is a procedure that can stop after step two. In the script it is one call.

## What is different from the parent's `release`

The parent's `release` picks the next version and rewrites every file that states it. Here it
**cannot**, and must not try. A Kiro Power's version is the Template_Release tag it was built
from, by construction *(R2 AC5)*, and the files that state it are generated output: the
determinism gate requires them to equal a fresh transform, so a hand-bumped `plugin.json` fails
CI. The bump has already happened — in `update-bootcamp-power`, or `create-bootcamp-power` for
an initial build — by the time a release is possible.

So this `release` **verifies** the version sites instead of writing them, and keeps the half of
the parent's operation that matters: **the version, the changelog entry and the tag move
together, or nothing moves.**

## Run it

Dry run first. It is the default, and it writes nothing:

```
python3 tools/bootcamp-transform/release.py <version>
```

Show the Maintainer the output — the gate verdict, the `CHANGELOG.md` diff, and the three git
commands — and get approval on that, not on the intent. Then:

```
python3 tools/bootcamp-transform/release.py <version> --apply
```

⛔ **Never invent the version.** `<version>` is the Maintainer's decision, and it must equal the
version the built Power states; the script refuses a bare invocation and names the built
version so the question can be asked. A release is not a default.

## What it checks, and what it writes

It refuses, and changes nothing, unless all of these hold:

| Check | Why |
|---|---|
| the working tree is clean | the release commit carries the changelog entry and nothing else, and the tag must name a tree whose gate files are committed. **No override.** |
| HEAD is on `main` | a tag on a feature branch can name a commit `main` never contains. `--allow-branch` if you mean it |
| the version is newer than every tag, and not already one | re-pointing a tag rewrites what anyone who fetched it already has |
| every entry in `VERSION_SITES` states the version | `plugin.json` `version` and its `templateRelease` provenance, `.build-manifest.json`, and the validation report and test record for that version. A disagreement is fixed by rebuilding or re-emitting, never by hand |
| `docs/test-records/<version>-validation.json` reads `passed` with `tagAllowed` true | the Schema_Validator half of the tagging gate *(R13 AC5)* |
| `docs/test-records/<version>.md` permits tagging | the Test_Checklist half *(R6)*, computed exactly as `testrecord.py check` computes it. An `_unrecorded_` step or platform cell is a fail, not a blank |

Then, as one unit, it writes `CHANGELOG.md` at the repository root, commits that file alone, and
creates an annotated tag on **that** commit. On the first release it creates the file, seeded
from the tags that already exist and labeled as reconstructed. A failure after the commit rolls
back to the recorded HEAD and deletes the tag.

⛔ **The commit comes before the tag.** Tagging first names the commit *before* the changelog
entry. And there is deliberately no flag that performs part of a release — no "tag only", no
"changelog only" — because each one reintroduces the split this operation exists to prevent.

The root `CHANGELOG.md` is this repository's release log, one entry per tag. It is not the
Power's own `powers/senzing-bootcamp/CHANGELOG.md`, which the update path writes per update and
the Publication_Contract keeps out of the public repository. Neither is published.

## After it runs

Report the version, the commit and the tag, then name the next steps and stop:

1. Run the suite against the release commit: `python3 -m pytest -m "not integration" -q`.
2. [`propagate-to-public`](../propagate-to-public/SKILL.md), to mirror the Power into the public
   working tree for review.
3. Push the branch **and the tag**: `git push origin main <version>`. `git push` alone does not
   send tags, and an unpushed tag is invisible to everything that reads one.

Steps 2 and 3 are the Maintainer's to start. Do not run them as part of a release unless asked.

## Guardrails

- Never run `--apply` without showing the dry run first.
- **Never push** — not the branch, not the tag.
- Never hand-edit a version site, the changelog heading, or the tag to get past a refusal. Fix
  what the refusal names, at its home: rebuild for a generated site, re-run `validate.py` for
  the report, record the checklist for the record.
- A new file that starts asserting the Power's version belongs in `VERSION_SITES` in
  `release.py`, in the same change.
- If `tag.gpgsign` is set, git may prompt for a passphrase and an unattended run can block
  there. The script does not override a signing policy. Say so rather than retrying.

## Scope

This skill writes only this repository: `CHANGELOG.md`, one commit, one tag. It builds nothing,
validates no content, and never touches `Senzing/senzing-bootcamp-kiro-power`, whose tags the
Maintainer creates after publishing there.
