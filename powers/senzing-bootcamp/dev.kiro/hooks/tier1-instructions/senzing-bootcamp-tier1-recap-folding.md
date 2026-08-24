# Tier 1 recap folding — the behavior Kiro has no `PreCompact` trigger for

Instructions to follow, not documentation to read out. Marker comments link the behavior to the
parity coverage map (`../hook-parity-coverage.json`).

The template folded the recap checkpoint into the durable recap from a `PreCompact` hook
(`precompact-recap.py`), immediately before context compaction discarded the material the
recap is built from. **Kiro provides no `PreCompact` trigger**, so there is no hook definition
for this behavior at any tier and it is delivered at Tier 1 *(R7 AC13)*.

As with every lifecycle behavior, the `config/bootcamp_progress.json` guard applies: outside a
bootcamp project, none of this applies.

---

## Fold the recap checkpoint at every close point

<!-- SENZING-BOOTCAMP-TIER1:recap-folding -->

Fold — merge the accumulated checkpoint entries into the durable recap, then leave the
checkpoint ready for the next stretch of work — at each of these points, without being asked:

- **At module completion**, as part of the module close phase, before moving to the next
  module.
- **At graduation**, before producing the final recap artifact, so the graduation recap covers
  every module rather than only the last one.
- **At session close-out** (see `senzing-bootcamp-tier1-session-lifecycle.md`), whenever the
  Bootcamper says they are stopping.
- **Whenever the conversation is about to be compacted or trimmed, if you are given any
  signal of it** — that is the moment the template's `PreCompact` hook covered.

What folding produces: an accurate, ordered record of what the Bootcamper covered, decided,
built, and struggled with, at a level of detail that survives losing the conversation. Never
invent recap content to fill a gap; a shorter true recap beats a complete-looking invented one.

## The residual gap, stated plainly

Folding is **not guaranteed at the exact pre-compaction moment**, because nothing fires there.
Two mechanisms bound the loss:

1. The per-turn `UserPromptSubmit` checkpoint tick keeps the checkpoint at most one turn behind
   and guarantees the checkpoint file exists (Tier 2 restores this mechanically; Tier 1 keeps
   it as an instruction).
2. The explicit fold points above put a fold at every boundary that matters to the Bootcamper.

So the worst case is one turn of unfolded recap material, not a lost module. That is the
documented parity gap for `PreCompact` *(R7 AC13)*, and it is why the checkpoint tick is
treated as load-bearing rather than as an optimization.

## Where this lands in the built Power

The design places recap folding in the ported prose at
`bootcamp-onboarding/module-completion.md` (module close) and
`graduation/SKILL.md` (final recap). Those ported files carry the instruction as bootcamp
prose. This file is the **Kiro-owned carrier** of the same instruction: present in the Power
whatever the resolved Template_Release contains, preserved verbatim across updates
(`owner: kiro`), and the location the parity coverage map declares for the `PreCompact`
behavior.
