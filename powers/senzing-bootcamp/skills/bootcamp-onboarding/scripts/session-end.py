#!/usr/bin/env python3
"""Preserve the in-progress recap and stop bootcamp containers at session close-out.

⛔ INERT IN KIRO — NO HOOK INVOKES THIS SCRIPT. Kiro provides no session-end trigger,
so no hook definition names it at any tier. Both behaviors are delivered as
instructions instead: see `senzing-bootcamp-tier1-session-lifecycle.md` (session
close-out) and `senzing-bootcamp-tier1-recap-folding.md` (folding). Nothing stops a
bootcamp container automatically in Kiro; the guide stops it — stop, never remove.

It is kept, unchanged and runnable, because it is the reference for what close-out
does, and because the guide MAY run it to perform both steps in one command at a
close-out point. Running it is never required.

When a bootcamp is active, fold the in-progress module recap checkpoint into
docs/bootcamp_recap.md so quitting mid-module never loses that module's narrative
(deterministic, idempotent, append-only — see recap_checkpoint.py), and stop any
container the bootcamp started so it does not linger after exit, using the runtime
CLI recorded with it (``<runtime> stop``, never remove, so it can be restarted on
resume — see docker_lifecycle.py, INV-101). Silent and non-blocking: it emits no
output, and every container step is optional and warns-and-continues when that
runtime's CLI is absent or errors.

Cross-platform: invoked in exec form (``python3 <path>``) so no shell is required on
any platform (INV-052). Python is already a hard bootcamp dependency.
"""
import sys

import docker_lifecycle
import recap_checkpoint

if recap_checkpoint.bootcamp_active():
    recap_checkpoint.fold_checkpoint()
    docker_lifecycle.stop_started_containers()

sys.exit(0)
