---
name: "bootcamp-feedback"
description: "Capture feedback about the Senzing bootcamp, saved locally to docs/feedback/. Use when the bootcamper says 'give senzing bootcamp feedback'."
license: "Apache-2.0"
compatibility: "Requires the Senzing MCP server for the optional server-side feedback forward."
metadata:
  author: "Senzing"
  owner: "kiro"
  templateCommand: "bootcamp-feedback"
---

# Bootcamp feedback

The bootcamper wants to give feedback about the bootcamp.

Follow the bootcamp feedback workflow in
[`bootcamp-onboarding/feedback.md`](../bootcamp-onboarding/feedback.md):
capture context silently, gather the feedback one 👉 question at a time, triage whether the
issue is in this Power or in the Senzing MCP server, and APPEND (never overwrite) a formatted
entry to `docs/feedback/SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md`, creating that file with its
header if it does not exist.

Every entry is recorded locally whatever the triage says. When the issue is in the **MCP
server**, additionally offer — once, showing the exact message first — to forward it via the
MCP server's `submit_feedback` tool, and never send anything external without that yes.

When finished, return the bootcamper to where they left off.

## Scope

This skill is the feedback entry point only. The workflow itself is defined by
`bootcamp-onboarding/feedback.md`; follow that file rather than improvising a
capture format here.
