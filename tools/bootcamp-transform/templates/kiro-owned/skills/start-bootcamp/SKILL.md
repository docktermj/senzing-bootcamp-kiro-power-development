---
name: "start-bootcamp"
description: "Start or resume the Senzing entity-resolution bootcamp. Use when the bootcamper says 'start the senzing bootcamp'."
license: "Apache-2.0"
compatibility: "Requires the Senzing MCP server."
metadata:
  author: "Senzing"
  owner: "kiro"
  templateCommand: "start-bootcamp"
---

# Start the bootcamp

The bootcamper wants to begin the Senzing bootcamp.

Invoke the [`bootcamp-onboarding`](../bootcamp-onboarding/SKILL.md) skill and follow it.
Whether this is a resume is decided by what `config/bootcamp_progress.json` **contains**,
not by whether it exists — three cases:

- **No file** -> start onboarding from the beginning.
- **A file recording no module** (empty, `{}`, malformed, or `current_module` null/blank) ->
  also start onboarding from the beginning, and **silently**: this is the normal state between
  the preface's project setup and Bootcamp preparation's final write, not a corruption to report.
- **A file with a `current_module`** -> resume from that module.

## Scope

This skill is the entry point only. It holds no bootcamp content of its own: the onboarding
flow, ground rules, and module progression all live in `bootcamp-onboarding` and the skills it
directs you to. Hand control to that skill and let it drive.
