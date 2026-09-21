# Kiro port invariants

This is the canonical list of invariants for the Senzing Bootcamp Kiro Power. They are
implementation-specific guarantees that MUST remain true when a versioned Senzing Bootcamp
Claude Plugin release is transformed into the Kiro Power.

The upstream curriculum's `INV-NNN` invariants remain authoritative for bootcamp content and
outcomes. This file does not copy or renumber them. It uses the separate permanent namespace
`KINV-NNN` for Kiro packaging, hook execution, interaction parity, and host-behavior guarantees
that have **no** upstream `INV-NNN` source.

## The boundary — two registers, two subjects, no overlap

This repository holds two invariant records, and they govern different things. Keeping them
apart is deliberate: the family forbids a rule having two homes (the parent's `INV-300`, the
no-fork discipline), so neither of these restates the other.

- **The Invariant_Discount_Register** — `invariantDiscounts` in
  `tools/bootcamp-transform/contract.yaml` — governs *inherited* invariants. For each upstream
  `INV-NNN` it records what the port did with it: honored as-is, preserved by restating the
  guarantee in a Kiro mechanism, or discounted (with a mandatory conflict + resolution). It is
  the audit that the curriculum's guarantees survived the port.
- **This file (`KINV-NNN`)** governs *Kiro-native* guarantees — properties that are true of the
  Kiro Power itself and correspond to no upstream `INV-NNN`, because Claude never had the
  question (a single-command-string hook schema, a non-blocking `Stop`, `${PLUGIN_ROOT}`, the
  Agent Plugins manifest location, model/effort pickers).

A `KINV-NNN` MUST NOT restate an upstream `INV-NNN` or an `invariantDiscounts` entry. Where a
`KINV` names an upstream invariant, it does so only to locate the parity gap it is about, never
to reproduce that invariant's content.

## Dual-evaluation

Every propagation of a newer Template_Release MUST evaluate **both** records:

1. Preserve the release's applicable `INV-NNN` behavior, via the Invariant_Discount_Register.
2. Preserve every `KINV-NNN` below while adapting that release to Kiro.

The `update-bootcamp-power` maintainer skill owns this review. A failed invariant on either
side is a release blocker, not advisory documentation.

## Maintaining this file

1. Never delete, reuse, or renumber an existing `KINV-NNN` identifier. Mark an obsolete
   invariant as superseded and name its replacement rather than removing it.
2. Edit an existing invariant only to clarify its wording without changing its meaning. Record
   a changed guarantee as a new invariant with the next unused identifier.
3. Add new invariants using the next unused, zero-padded identifier, and add that identifier to
   exactly one subject in the index below **in the same change**.
4. Phrase every invariant as one testable MUST or ALWAYS condition.
5. Keep the structural linter (`specs/check_invariants.py`) passing; extend it when a new
   invariant can be checked mechanically.
6. Treat a failed invariant as a release blocker, not as advisory documentation.

## Index by subject

- **Packaging shape:** KINV-001, KINV-002, KINV-003
- **Plugin-root token:** KINV-004
- **Hook execution and portability:** KINV-005, KINV-006, KINV-007
- **Hook parity tiers:** KINV-008, KINV-009, KINV-010
- **Interaction parity gaps:** KINV-011, KINV-012
- **Model and effort surface:** KINV-013

## Packaging shape

- **KINV-001** — The Bootcamp_Power MUST be packaged in Agent Plugins v1.0.0 format, with its
  `plugin.json` manifest at the Power root and never inside a `.claude-plugin/` directory.
- **KINV-002** — The resolved Template_Release version MUST be recorded under `plugin.json` at
  `extensions` → `com.senzing.bootcamp` → `templateRelease`, outside the fixed Agent Plugins
  top-level field set, so provenance survives schema validation rather than being dropped as an
  unknown top-level field.
- **KINV-003** — The Senzing MCP server MUST be declared in an `mcp.json` document at the Power
  root, with transport type `streamable-http` and a `$schema` field, translated from the
  template's `.mcp.json` `http` declaration; the produced Power MUST NOT carry a
  `.claude-plugin/.mcp.json`.

## Plugin-root token

- **KINV-004** — Every reference to the plugin root in the produced Power MUST use
  `${PLUGIN_ROOT}`; the Claude token `${CLAUDE_PLUGIN_ROOT}`, in either its expanded or bare
  spelling, MUST NOT survive into the produced Power.

## Hook execution and portability

- **KINV-005** — Every hook `command` MUST be a single command string naming an absolute,
  quoted interpreter path followed by an absolute, quoted script path, with the interpreter
  resolved at install time from the installing Python's own executable and never written as a
  bare interpreter name. This is how the Kiro single-command-string hook schema preserves the
  no-shell-dependency guarantee that the template obtains from its exec-form hooks.
- **KINV-006** — A hook command string MUST NOT contain a shell construct — command chaining
  (`&&`, `||`, `;`), a pipe, a redirection, or a shell builtin — so one command string parses
  and runs identically on Linux, macOS, and Windows PowerShell.
- **KINV-007** — Every installed hook MUST behave as a no-op when the Bootcamper's project has
  no `config/bootcamp_progress.json`, so installing enforcement never alters an unrelated Kiro
  session.

## Hook parity tiers

- **KINV-008** — Every hook-enforced behavior MUST also be delivered as skill instructions
  (Tier 1), so the complete bootcamp is usable with zero hook definitions installed; no
  behavior may reach the Bootcamper solely through the workspace hook install or the
  `dev.kiro/hooks/` directory.
- **KINV-009** — The workspace hook installer MUST write into the Bootcamper's `.kiro/hooks/`
  only with explicit consent, MUST disclose every path before writing any file, MUST be
  idempotent, MUST prefix every file it writes with `senzing-bootcamp-`, and MUST provide a
  documented removal that deletes exactly the files it created and no others.
- **KINV-010** — Hook definitions bundled under `dev.kiro/hooks/` (Tier 3) MUST NOT be a
  behavior's only delivery path; they ship for forward compatibility, and every behavior they
  carry MUST also reach the Bootcamper through Tier 1 or Tier 2, regardless of whether the host
  loads that directory.

## Interaction parity gaps

- **KINV-011** — Where the parent relies on a blocking hook whose Kiro equivalent trigger
  cannot block (Kiro `Stop`), the behavior MUST be delivered as an advisory skill instruction
  and the non-blocking limitation MUST be documented; the port MUST NOT claim mechanical
  enforcement of it. The one-question-per-turn closing rule is the standing case: enforced
  mechanically on Claude, advisory-only on Kiro.
- **KINV-012** — Behavior the parent binds to a Claude trigger that Kiro does not provide
  (`PreCompact`, `SessionEnd`) MUST be delivered by a Kiro-available mechanism — a per-turn
  `UserPromptSubmit` checkpoint plus explicit close-out steps in the owning skill — and the
  recap-fold loss window MUST be bounded to at most one turn.

## Model and effort surface

- **KINV-013** — Model and reasoning-effort guidance MUST be expressed as selections in Kiro's
  model and effort pickers, never as Claude slash-command pairs (`/model`, `/effort`); the
  recommended model and effort names are retained as written, because they are the Kiro
  equivalents.
