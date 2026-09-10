---
name: "bootcamp-note"
description: "Capture a bootcamper's own idea, question, reminder or to-do, saved locally to docs/bootcamp_notes.md. Use when the bootcamper says 'take a senzing bootcamp note'."
license: "Apache-2.0"
compatibility: "No Senzing MCP server. A note is written to the project and sent nowhere."
metadata:
  author: "Senzing"
  owner: "kiro"
  templateCommand: "bootcamp-note"
---

# Bootcamp note

The bootcamper wants to capture a note of their own — an idea, question, reminder, to-do
or memo about **their** work, not feedback about the bootcamp.

Follow the bootcamp note workflow in
[`bootcamp-onboarding/notes.md`](../bootcamp-onboarding/notes.md): capture the time,
module and pending question silently, classify the note without asking, recite it for
approval, and APPEND (never overwrite) it to `docs/bootcamp_notes.md`, creating that file
with its header if it does not exist. Verify the entry landed on disk before telling them
it was saved. Any elaboration or context is stored under its own label, never merged into
their own words.

**If the bootcamper's statement already carries the note, that text is the note** — do not
ask what they would like to note. Ask only when they asked to record something without
saying what.

A note is never routed, never triaged, and never sent anywhere: it stays on their machine
and is folded into their recap at graduation. When finished, return the bootcamper to
exactly where they left off.

⛔ **A message that is both a note and a report about the bootcamp is feedback**, not a
note: it names the bootcamp as the thing at fault, so it belongs in the feedback flow
where a maintainer will see it. That precedence is stated in `notes.md`; follow it there
rather than deciding it here. The feedback flow is the `bootcamp-feedback` skill, whose
own trigger phrase is stated in its description.

## Scope

This skill is the note entry point only. The workflow itself is defined by
`bootcamp-onboarding/notes.md`; follow that file rather than improvising a capture format
here.
