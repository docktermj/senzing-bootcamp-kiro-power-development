# The Claude → Kiro porting framework

This repository generates the Senzing Bootcamp **Kiro Power** from a versioned release of
the parent Senzing bootcamp **Claude plugin**. This document is the **map** of how that
port works and where each part lives. It is deliberately an index, not a second copy: each
component below is stated in full in exactly one place, and this page **points** to that
place rather than restating it (the family forbids a rule having two homes — the parent's
`INV-300`). If this page and an artifact disagree, the artifact wins.

## Parent and children

- The **parent** — `docktermj/senzing-bootcamp-claude-plugin-development`, shipped as
  `Senzing/senzing-bootcamp-claude-plugin` — owns the curriculum and the `INV-NNN`
  invariants. It is the single place bootcamp content and outcomes are decided.
- This repository is a **child**: it *transforms* the parent into a Kiro Power. It never
  forks the curriculum.
- The **sibling children** port the same parent to other hosts —
  `docktermj/senzing-bootcamp-chatgpt-plugin-development` (Codex) today, Copilot and Gemini
  later. They converge on the same framework; each child's convergence is tracked in its own
  repository.

## The nine components, and where each lives

Each row is the canonical home of one component. Follow the link for the actual rules.

| | Component | Home |
|---|---|---|
| A | **Provenance** — the pinned parent release, recorded once and read everywhere | [`docs/provenance-convention.md`](./provenance-convention.md) → the in-manifest `extensions["com.senzing.bootcamp"]` block |
| B | **Declarative transformation contract** — every mapping rule as data; exhaustive matching with an unmatched-file early warning | [`tools/bootcamp-transform/contract.yaml`](../tools/bootcamp-transform/contract.yaml) |
| C | **Invariant-disposition register** — every upstream `INV-NNN` marked honored / preserved-restated / discounted, gated | the `invariantDiscounts` register (R15) in [`contract.yaml`](../tools/bootcamp-transform/contract.yaml) |
| D | **Host-native invariant namespace** — `KINV-NNN`, the guarantees true of the Kiro Power itself | [`specs/INVARIANTS.md`](../specs/INVARIANTS.md), linted by [`specs/check_invariants.py`](../specs/check_invariants.py) |
| E | **Mechanical port checks** — the tagging gate (schema, cross-reference, residual-reference, broken-import, …) | [`tools/bootcamp-transform/validate.py`](../tools/bootcamp-transform/validate.py) |
| F | **Three-way reconciliation** — detects local-edit vs upstream-change conflicts on update | [`tools/bootcamp-transform/reconcile.py`](../tools/bootcamp-transform/reconcile.py) against `powers/senzing-bootcamp/.build-manifest.json` |
| G | **Recorded Test_Checklist** — host-behavior assumptions verified and recorded per release | [`docs/test-checklist.md`](./test-checklist.md) + `docs/test-records/` |
| H | **CI determinism gate** — rebuilds at the pinned tag and fails on any drift | [`.github/workflows/verify-build-determinism.yml`](../.github/workflows/verify-build-determinism.yml) |
| I | **Cross-repo governance** — the parent↔child issue paths | [`parity-check`](../powers/senzing-bootcamp-maintainer/skills/parity-check/SKILL.md) (parent→child) and [`escalate-to-parent`](../powers/senzing-bootcamp-maintainer/skills/escalate-to-parent/SKILL.md) (child→parent) |

## Principles (identical across every child)

- The parent owns the curriculum and the `INV-NNN` invariants; children **transform, never fork**.
- `INV-NNN` are authoritative for content and outcomes and are **never copied or renumbered**
  into a child. The host-native namespace (D) covers only host packaging, lifecycle,
  interaction, and release, and does not restate the disposition register (C).
- Every propagation of a newer parent release evaluates **both** invariant records: preserve
  applicable `INV-NNN` (via C) and preserve every host-native invariant (D). This
  **dual-evaluation** is owned by the `update-bootcamp-power` skill; the boundary between the
  two records is stated in `specs/INVARIANTS.md` and in `contract.yaml`, not here.
- A failed invariant or check is a **release blocker**, not advisory documentation.
- Where Kiro lacks a mechanism the parent relies on — a non-blocking `Stop`, no `PreCompact`
  or `SessionEnd` — the guarantee **degrades to an advisory instruction and the gap is
  documented**, never silently dropped (see D's interaction-parity invariants).

## Extensibility — a Copilot or Gemini child

The nine components are host-agnostic. A new child **reuses unchanged** the engine (B), the
disposition register (C), reconciliation (F), and the governance skills (I). It **supplies
only** three host-specific things: its own host-native invariant prefix and ledger (D), its
substitution sets and host mechanisms in the contract (B), and its host-behavior checks
(E, G). The parent, and the `INV-NNN` it owns, do not change.

## Cross-repo status

Kiro's convergence onto this framework is tracked in issue #10 (this document is its durable
form). The ChatGPT sibling's convergence — the mirror-image gaps there — is tracked in that
repository's own tracking issue.
