---
name: "graduate-bootcamp"
description: "Close out the Senzing bootcamp: generate the recap PDF and a production-ready project. Use when the bootcamper says 'graduate the senzing bootcamp'."
license: "Apache-2.0"
compatibility: "Requires the Senzing MCP server."
metadata:
  author: "Senzing"
  owner: "kiro"
  templateCommand: "graduate"
---

# Graduate the bootcamp

The bootcamper wants to finish the Senzing bootcamp and graduate.

Invoke the [`graduation`](../graduation/SKILL.md) skill and follow it: show the GRADUATION
banner, present the graduation preface (journey map, before/after, step overview, estimated
time), finalize `docs/bootcamp_recap.md` and render `docs/bootcamp_recap.pdf`, build the
`production/` project, create the revisit/resume bundle, then emit the guaranteed-recap
announcement and the single closing 👉 question ("Is there anything else you would like to
explore?").

Only after the bootcamper declines further exploration, render the terminal
`END OF SENZING BOOTCAMP` banner as the final output, exactly once (INV-057). Never show
that banner while exploration is still continuing, and never end graduation on the closing
question when the bootcamper has said they are done.

The bundled recap PDF generator is available at
`${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/generate_recap_pdf.py`; pass that path
when the graduation skill renders the PDF.

If no `config/bootcamp_progress.json` exists in the working directory, tell the bootcamper
there is no bootcamp to graduate and offer to start one — that is the `start-bootcamp` skill,
whose own trigger phrase is stated in its description.

## Scope

This skill is the graduation entry point only. Every step above is defined by the
`graduation` skill; hand control to it and let it drive.
