# Provenance convention

*Issue #9, part A. Companion to `.github/workflows/verify-build-determinism.yml` (part H).*

The Bootcamp_Power is generated from a versioned release of the parent Claude plugin.
"Provenance" is the record of **which parent release** a committed Power was built from.
This document fixes the single canonical spelling of that fact, so it is recorded, read,
and compared in exactly one form.

## The one canonical location

The pinned parent release lives in the produced Power's own manifest, under the extensions
namespace, and is mirrored in the build manifest:

- **`powers/senzing-bootcamp/plugin.json`** →
  `extensions` → `com.senzing.bootcamp`:
  - `templateRepository` — the parent repository the release came from
  - `templateRelease` — the pinned parent release, a bare SemVer tag (e.g. `0.5.3`)
  - `contractVersion` — the transformation contract version that produced the tree
- **`powers/senzing-bootcamp/.build-manifest.json`** — carries `templateRelease` and
  `contractVersion` again, so a Power whose `plugin.json` is mid-edit still has a provenance
  record.

This is not a new placement. The transform **writes** it and `verify_plugin_manifest` (in
`tools/bootcamp-transform/transform.py`) already **enforces** it: the release must appear under
`extensions["com.senzing.bootcamp"].templateRelease`, and a `templateRelease` field at the
manifest top level is rejected. The in-manifest location wins because Agent Plugins validates
the manifest, so provenance that rides inside it cannot silently rot into an unread top-level
file.

## No competing top-level file

There is deliberately **no** top-level `PARENT_VERSION`, `UPSTREAM_VERSION`, or
`UPSTREAM_COMMIT` file in this repository. The ChatGPT sibling records provenance in top-level
`UPSTREAM_VERSION` + `UPSTREAM_COMMIT` files, and issue #6 initially proposed a third name,
`PARENT_VERSION`. Three names for one fact is exactly what blocks cross-child uniformity, so
this repository keeps one: the in-manifest block above. The determinism workflow fails if a
competing top-level file appears.

## Who reads it

Every consumer reads the same location, in the same precedence (manifest first, build manifest
as fallback):

- **the build** writes it (`transform.py`) and enforces it (`verify_plugin_manifest`);
- **`watch-upstream-release.yml`** reads it to decide whether a newer parent release exists;
- **`verify-build-determinism.yml`** reads it to know which tag to rebuild at;
- **`/parity-check` (#6)** MUST read it to compute the parent delta — it MUST NOT introduce a
  `PARENT_VERSION` file. This supersedes the "read `PARENT_VERSION`" step in #6 as originally
  written.

## Reproducibility, and the commit SHA

The pin is by **release tag**. Reproducibility from that tag is guaranteed two ways:
`resolve_release.py` fetches the tag and verifies that the fetched `HEAD` is that tag's commit
(refusing a branch head), and `verify-build-determinism.yml` rebuilds at the pinned tag and
fails on any drift from the committed tree. Together these make "the committed Power is the
deterministic transform of release *N*" a continuously checked property. The gate excludes
exactly one file, `CHANGELOG.md`: it is the Power's own maintainer-appended update log
(R5 AC8), written outside the transform, so a create-equivalent rebuild never produces it.
Everything else — including this provenance block and `.build-manifest.json` — must match a
fresh transform byte for byte.

Recording the immutable 40-character parent **commit SHA** alongside the tag — as the ChatGPT
sibling's `UPSTREAM_COMMIT` does — would harden the pin against a moved tag. It is **not**
recorded today: the resolver's provenance is tag-based by design, threading a commit through
the transform and its property tests is a separate change, and the determinism gate already
closes the drift gap the commit would guard. Adding `templateCommit` to the extensions block is
the sanctioned way to strengthen this later; it belongs in the same block, never in a top-level
file.

## Cross-child direction

For uniformity across children (Kiro, ChatGPT, and future Copilot/Gemini ports), the agreed
direction is that every child names the same fact — the pinned parent release — in its
host-native manifest extensions rather than in a bare top-level file. The ChatGPT sibling's
convergence onto this shape is tracked in that repository, not here.
