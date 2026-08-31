#!/usr/bin/env python3
"""Fold the in-progress recap before the conversation is compacted.

⛔ INERT IN KIRO — NO HOOK INVOKES THIS SCRIPT. Kiro provides no pre-compaction
trigger, so no hook definition names it at any tier. The behavior is delivered as an
instruction instead: see `senzing-bootcamp-tier1-recap-folding.md`, which tells the
guide to fold at module completion, at graduation, at session close-out, and whenever
it is given any signal that the conversation is about to be compacted. The per-turn
`checkpoint-tick.py` (`UserPromptSubmit`) is what bounds the residual loss to one turn.

It is kept, unchanged and runnable, because the logic below is the reference for what
folding means, and because it can be run by hand. Running it is never required.

Compaction summarizes the conversation, which can drop an in-progress module's recap
narrative even though the session continues. When a bootcamp is active this script:
  1. folds the current in-progress recap checkpoint into docs/bootcamp_recap.md
     (deterministic, idempotent, append-only — see recap_checkpoint.py), and
  2. emits a short reminder so the post-compaction guide keeps
     docs/progress/recap_checkpoint.md current at each step.

Non-blocking. Cross-platform: invoked in exec form (``python3 <path>``) so no shell
is required on any platform (INV-052).
"""
import sys

import recap_checkpoint

if recap_checkpoint.bootcamp_active():
    recap_checkpoint.fold_checkpoint()
    print(
        "A Senzing bootcamp is in progress. Keep the current module's in-progress "
        "recap saved to docs/progress/recap_checkpoint.md (append-only, refreshed at "
        "each step boundary) so no progress narrative is lost when context is summarized."
    )

sys.exit(0)
