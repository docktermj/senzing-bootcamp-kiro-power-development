---
name: "package-bootcamp"
description: "Package the bootcamp into one transferable zip archive under backups/packages/, with nothing sent anywhere. Use when the bootcamper says 'package the senzing bootcamp'."
license: "Apache-2.0"
compatibility: "No Senzing MCP server. The archive is written inside the project and transmitted nowhere."
metadata:
  author: "Senzing"
  owner: "kiro"
  templateCommand: "package-bootcamp"
---

# Package the bootcamp

The bootcamper wants to archive their bootcamp, move it to another machine, or hand the
results to someone else.

Follow the packaging workflow in
[`bootcamp-onboarding/packaging.md`](../bootcamp-onboarding/packaging.md): run the dry run
FIRST so the question quotes a measured size rather than an estimate, ask the one pinned
numbered 👉 question about what should travel, then write the archive with

```bash
python3 "${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/package_bootcamp.py" --profile <share|transfer>
```

Two profiles: `share` carries the results — recap PDF, keepsake documents, visualizations
and `production/`, with no database, no source data and no credentials. `transfer` adds
the revisit bundle, config and mappings, so the bootcamp can be resumed elsewhere.

**Run the dry run and ask the question even when the bootcamper already named a profile**
("package it for transfer"). The size and the exclusions are what they are consenting to,
and naming a profile is not consent for what leaves in the archive.

The archive is written **inside the project** and this Power transmits it nowhere: moving
it is the bootcamper's action. Report the path, size and digest from the script's own
output, name anything excluded that they might expect to find, and return the bootcamper
to exactly where they left off.

⚠️ **This is not the revisit bundle and does not replace it.** Graduation writes
`backups/revisit/` in place as a save point on this machine; this flow is what makes that
portable.

## Scope

This skill is the packaging entry point only. Every step above, including the pinned
question and the exclusion rules, is defined by `bootcamp-onboarding/packaging.md`; follow
that file rather than assembling an archive by hand.
