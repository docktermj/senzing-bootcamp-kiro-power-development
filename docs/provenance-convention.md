# Provenance convention

*Issue #9, part A; names fixed by #26. Companion to `.github/workflows/verify-build-determinism.yml` (part H).*

The Bootcamp_Power is generated from a versioned release of the parent Claude plugin.
"Provenance" is the record of **which parent release, at which commit,** a committed Power was
built from. This document fixes the names of that fact and its single home, so it is recorded,
read, and compared in exactly one form.

## The names: `PARENT_VERSION` and `PARENT_COMMIT`

These are the family's names, the same in every Senzing Bootcamp development repository
(FAMILY_WORKFLOW component A):

- **`PARENT_VERSION`** — the pinned parent release: an exact, bare SemVer **tag** such as
  `0.6.1`. ⛔ Never `main`, never `HEAD`, never `v0.6.1` (R2): a port targets a tagged release,
  and a branch head is a moving target no other repository can check against.
- **`PARENT_COMMIT`** — the full, lowercase 40-hex SHA of the commit that tag named when the
  Power was built. It hardens the pin against a moved tag: a release retagged onto different
  content keeps its name and changes its commit.

### Why not `UPSTREAM_VERSION` / `UPSTREAM_COMMIT`

Before #26 the family had three names for this one fact: this repository's `templateRelease`,
the ChatGPT sibling's `UPSTREAM_VERSION` / `UPSTREAM_COMMIT`, and the parent's `PARENT_VERSION`.
The family settled on `PARENT_*`, and the rejection of `UPSTREAM_*` is not aesthetic:
**"upstream" already means something else here.** The Senzing MCP server is upstream of every
repository in the family, and `feedback-to-issues` and `dry-run` route confirmed server defects
"upstream" to Senzing through `submit_feedback` — a different destination from the parent
repository. A field named `UPSTREAM_VERSION` beside a workflow step that reports upstream to
Senzing is an ambiguity waiting to be resolved wrongly. The topology's vocabulary is
parent/child, so the provenance follows it.

The glossary term *Template_Release* — a release of the parent plugin, as the frozen
requirements under `.kiro/specs/` define it — is a concept, not a recorded field, and keeps its
name. `PARENT_VERSION` is the field that records **which** Template_Release a Power was built from.

## The one canonical location

The names are fixed; where they are stored is this host's choice. Here it is the produced
Power's own manifest, under the extensions namespace, mirrored in the build manifest:

- **`powers/senzing-bootcamp/plugin.json`** → `extensions` → `com.senzing.bootcamp`:
  - `templateRepository` — the parent repository the release came from
  - `PARENT_VERSION` — the pinned parent release tag
  - `PARENT_COMMIT` — the commit that tag named
  - `contractVersion` — the transformation contract version that produced the tree
- **`powers/senzing-bootcamp/.build-manifest.json`** — carries `PARENT_VERSION`,
  `PARENT_COMMIT`, and `contractVersion` again, so a Power whose `plugin.json` is mid-edit still
  has a provenance record.

The transform **writes** them and `verify_plugin_manifest` (in
`tools/bootcamp-transform/transform.py`) **enforces** the placement: the release must appear under
`extensions["com.senzing.bootcamp"].PARENT_VERSION`, a top-level `PARENT_VERSION` is rejected, and
`PARENT_COMMIT` must be the commit the build was given. The in-manifest location wins because
Agent Plugins validates the manifest, so provenance that rides inside it cannot rot into an
unread top-level file (KINV-002). Each ported skill's frontmatter `metadata.PARENT_VERSION`
records the same tag.

There is deliberately **no** top-level `PARENT_VERSION` or `PARENT_COMMIT` file, and none of the
rejected `UPSTREAM_*` names either. The determinism workflow fails if one appears.

## Who reads it

Every consumer reads the same location, in the same precedence (manifest first, build manifest
as fallback):

- **the build** writes it (`transform.py --tag <PARENT_VERSION> --commit <PARENT_COMMIT>`, with
  both taken from `resolve_release.py`'s record) and enforces it (`verify_plugin_manifest`);
- **`resolve_release.py`** resolves `PARENT_COMMIT` from the tag ref only — `git ls-remote` of
  `refs/tags/<tag>`, peeled, with the REST API as fallback — so a branch name cannot resolve;
- **`validate.py`**'s `version-match` check requires `PARENT_VERSION` to equal the Power version
  and the resolved tag, and a recorded `PARENT_COMMIT` to be a full 40-hex SHA;
- **`verify-build-determinism.yml`** reads both to know what to rebuild, rejects a non-tag
  `PARENT_VERSION` and a non-SHA `PARENT_COMMIT` by name, and fails when the tag now names a
  different commit;
- **`watch-upstream-release.yml`** reads `PARENT_VERSION` to decide whether a newer parent
  release exists;
- **`parity-check`**, **`update-bootcamp-power`**, and **`release`** read it to compute the
  parent delta, the update baseline, and the version sites a release must agree on.

## Reproducibility

`resolve_release.py` fetches only `refs/tags/<tag>` and verifies the fetched `HEAD` is that tag's
commit, and `verify-build-determinism.yml` rebuilds at the pinned tag and commit and fails on any
drift from the committed tree. Together these make "the committed Power is the deterministic
transform of release *N* at commit *C*" a continuously checked property. The gate excludes exactly
one file, `CHANGELOG.md`: it is the Power's own maintainer-appended update log (R5 AC8), written
outside the transform, so a create-equivalent rebuild never produces it.

## Records written before #26

Two committed artifacts predate the names and keep the old spelling, because they are evidence of
what a past run produced and are not rewritten: `docs/test-records/0.5.1-validation.json` and
`docs/test-records/0.5.3-validation.json`. The frozen archive under `.kiro/specs/` (KINV-014) also
uses the old field name. Nothing reads any of them for provenance.
