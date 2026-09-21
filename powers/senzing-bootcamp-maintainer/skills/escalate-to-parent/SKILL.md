---
name: "escalate-to-parent"
description: "File a curriculum-level problem found in this Kiro port as a GitHub issue against the parent Senzing bootcamp Claude plugin development repository, self-contained enough to act on without this repo and cross-referenced in both directions, so the parent fixes it canonically and parity brings the fix down. This is the only command that files issues into another repository. Use when the maintainer says 'escalate feedback to the parent'."
license: "Apache-2.0"
compatibility: "Requires this repository — docktermj/senzing-bootcamp-kiro-power-development — as the open workspace. Requires `gh` (or the GitHub REST API with a scoped token) authenticated with issue-write on both this repository and the parent development repository named in metadata, since the escalation is cross-referenced in both. Needs network access. Uses the Senzing MCP server to re-verify any Senzing fact before it is asserted upstream; when the finding is that the MCP server itself is wrong, that goes to Senzing via submit_feedback, not here. No transform and no build."
metadata:
  author: "Senzing"
  role: "Escalate_To_Parent"
  parentDevelopmentRepository: "docktermj/senzing-bootcamp-claude-plugin-development"
  ownsRepositoryBoundary: true
---

# Escalate feedback to the parent

Feedback from a Kiro bootcamp is one of two things:

- a **curriculum** problem — the bootcamp's content or behavior, which the parent owns.
  It belongs upstream, so the fix flows back down to every platform.
- a **port** problem — Kiro-specific (a hook, a substitution, a parity-tier decision,
  a packaging detail). It belongs here.

The child **escalates rather than fixes** curriculum problems: the parent fixes them
canonically, and `parity-check` brings the fix down. That round trip is the system
working as intended — it is what keeps every platform on one curriculum.

## This command owns the repository boundary

**`escalate-to-parent` is the only command that files a GitHub issue into another
repository.** Every other maintainer skill writes only inside this repository:
`create-bootcamp-power`, `update-bootcamp-power`, and `parity-check` never write
upstream, and `publish-bootcamp-power` writes to the public runtime repository through
its own publication contract, not as an issue. One owner means one place to audit
cross-repo traffic.

This is distinct from `submit_feedback`, the Senzing MCP call that reports a **server**
defect to Senzing: that is a different upstream (the MCP server operator, not the parent
plugin) reached by a different channel. A curriculum problem in the bootcamp content is
a parent **GitHub issue**; a wrong answer from the Senzing MCP server is a
`submit_feedback` report. Do not conflate them, and do not file a server defect here.

### The local feedback router triages; it never files upstream

The command that turns collected bootcamp feedback into local work — `feedback-to-issues`
in the issue-driven model, and today `feedback-to-specs` — MUST **triage before writing**:
classify each item as parent-bound or local, show that decision **per item** (never
silently), hand every parent-bound item to `escalate-to-parent`, and write local work
only for genuine port problems. It MUST NOT file into another repository itself, and MUST
NOT write local work for a parent-bound item. `escalate-to-parent` is the single hand-off
point that obligation routes to. (The issue-driven `feedback-to-issues` router does not
exist in this repository yet; this contract binds it when it lands. `feedback-to-specs`
routes to specs and reaches Senzing only through `submit_feedback`, so it already files no
cross-repo GitHub issue.)

## Steps

### 1. Confirm the item is curriculum, not port

State the discriminator and the verdict. A curriculum problem reproduces on the parent's
own bootcamp — it is about what the bootcamp teaches, asks, or does, independent of Kiro
packaging. A port problem exists only because of how this repository transforms the parent
(a hook that cannot block, a substitution, the manifest shape). Only a curriculum problem
is escalated; a port problem stays local and this command stops.

### 2. Re-verify every Senzing fact before asserting it upstream

Feedback is a snapshot; the Senzing MCP server is released independently. Before repeating
any Senzing fact in an upstream issue, re-ask the live server — a defect may already be
fixed, or a claim may have been wrong all along. If the finding is that the **server** is
wrong, it is not a curriculum problem: report it to Senzing with `submit_feedback` and do
not file it here. This mirrors the sourcing discipline the whole bootcamp follows: Senzing
facts come from the MCP server, never from memory.

### 3. File the parent issue — self-contained

`gh issue create -R docktermj/senzing-bootcamp-claude-plugin-development` (REST API with a
scoped token otherwise). The parent maintainer must be able to act on it **without opening
this repository**, so the body carries, in its own words: the bootcamper-facing symptom,
the module and step, the expected versus actual behavior, and why it is curriculum-level
rather than a Kiro packaging artifact. The link back to this repo is **provenance**, not a
substitute for context.

### 4. Cross-reference in both directions

A one-way link leaves the child with two open issues for one problem — its own escalation
and the parity issue for the parent's fix coming back. So:

- the **parent** issue body carries the originating **child issue URL**;
- the **child** escalation issue in this repository records the **parent issue URL/number**;
- the child escalation is left **discoverable** — labeled or marked as an escalation — so
  `parity-check` can list open escalations and, when the parent's fix arrives in a release,
  link or close the escalation instead of filing a duplicate parity issue for the same thing.

When the escalation originates from an already-filed local issue, cross-reference that one.
When it originates directly, create the local escalation record first, so the two-way link
and the `parity-check` handshake always have both ends.

## Rules

- **Pull, not push, everywhere except here.** This is the single command that writes to
  another repository; nothing else in the maintainer tooling does.
- **Only curriculum problems go upstream.** Port problems stay local; server defects go to
  Senzing via `submit_feedback`, not as a parent issue.
- **Self-contained upstream.** The parent issue stands on its own; the child link is
  provenance.
- **Both ends linked.** Every escalation is cross-referenced in both directions and left
  discoverable for `parity-check`.

## Who owns what

- **the local feedback router** (`feedback-to-issues`; today `feedback-to-specs`) — triages
  and hands parent-bound items here; files no cross-repo issue itself.
- **`escalate-to-parent`** — files the one upstream issue and records both ends of the link.
- **the parent** — fixes the curriculum problem canonically, in one place, for every platform.
- **`parity-check`** — brings the fix back down and reconciles it against the open escalation.
