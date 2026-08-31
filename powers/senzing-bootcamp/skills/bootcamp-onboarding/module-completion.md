# Module Completion (run at the end of every module)

Every module skill runs this process at its end, immediately **before** its
transition 👉 question. It does three things, in this fixed order:

1. Update progress state.
2. Append this module's recap section to `docs/bootcamp_recap.md` (the recap
   the bootcamper keeps).
3. Present the end-of-module summary to the bootcamper.

Then the module asks its single transition question. Follow `ground-rules.md`
throughout: `🛑`/`⛔` are internal, never rendered; one 👉 question ends the turn.

This is the module-completion routine every module closes with. It is deliberately lightweight and non-blocking. If any write fails, name what failed, do not claim the module is complete, and let the bootcamper decide how to proceed.

## Step 1: Update progress state

In `config/bootcamp_progress.json`, apply all of the following as a **single** batched write (one
diff, not one write per field), done quietly (INV-012 — see `ground-rules.md`):

- Add this module's **name token** (e.g. `system_verification`, `truthset_visualization`, `data_collection`) to `modules_completed` — never a catalog number, so graduation's name-based reconcile matches (INV-085). Idempotent: do not duplicate. Each module records its own single name token at its own close — System verification and the separate Truth Set visualization module each record themselves (INV-086/INV-087).
- Set `current_module` to the next module in `selected_modules` (or leave it on this module if the bootcamper has not yet chosen to advance).
- Set top-level `current_step` to `null`.
- Under `step_history["<module>"]`, set `{ "last_completed_step": "<final step>", "updated_at": "<ISO 8601>" }`.

## Step 2: Append the recap section

The recap is the single accumulating record that becomes the graduation recap
PDF. Append one section per completed module. Do **not** rewrite existing
sections: append only.

### 2a. Create the recap on first module completion

⛔ **This substep is UNCONDITIONAL at any module whose append finds no file — every module runs it,
no module is exempt from it, and no citation elsewhere may narrow Step 2 in a way that omits it.**
Nothing else creates the recap header: not the onboarding preface, not Bootcamp preparation (which
is recap-exempt by INV-092 and writes only the two `config/` files). So whichever module happens to
append first owns the creation, and which module that is depends on the path — Entity Resolution
Concepts on a Core run, Discover the Business Problem on a Customized run that drops it. A module
that cites "Step 2 (2b/2c)" and skips 2a appends a `## ` section to a file with no preamble, and the
missing header is not discovered until graduation, on the keepsake: the certificate prints a
placeholder name, and graduation's completion-date insertion and `**Plugin version:**` amendment
have no line to anchor to.

If `docs/bootcamp_recap.md` does not exist, create `docs/` and write this header
(read `name` from `config/bootcamp_preferences.yaml`; default to `Bootcamper`;
the plugin version from the plugin manifest, resolved as `onboarding-flow.md` step 0 specifies
(⛔ never by searching the filesystem for a `plugin.json` — INV-252), or "Unknown"; and
also include the chosen programming language and path (Core/Customized) when present):

```markdown
# Senzing Bootcamp Recap

**Bootcamper:** {name}
**Started:** {ISO 8601 timestamp with timezone offset}
**Programming language:** {language}
**Path:** {path}
**Plugin version:** {plugin version}

---
```

The **Run environment** provenance lines (operating system + architecture, Python version,
language runtime, Senzing SDK, database) are added to this header at graduation, where they are
current — see `../graduation/SKILL.md`. They are recorded in the recap only, never shown in the
bootcamp output (INV-012).

### 2b. Append this module's section

Append the section below at the end of the file, in module-completion order — the order the
bootcamper actually experienced the modules; never re-sort by catalog number. Use the module
**name** (from the module skills / `../bootcamp-onboarding/onboarding-flow.md` overview), not a
catalog number. Gather the content from what actually happened in this module, from the
bootcamper's point of view:

```markdown
## {Name} — {ISO 8601 timestamp}

### Information Shared
- {key concepts, explanations, and reference material presented this module}

### Questions & Responses
- **Q:** {question you asked}
    - **R:** {the bootcamper's answer}

### Actions Taken
- {files created or modified, code generated, commands run, decisions made}

### End-of-Module Summary
**What you accomplished:**
- {plain-language accomplishment 1}
- {accomplishment 2}

**Files produced:**
- `{path}` — {what it is}

**Why it matters:** {1-2 sentences tying this module's output to the bootcamper's goal}
**Bootcamper's takeaway:** {the bootcamper's stated takeaway — omit this whole line if the bootcamper gave no takeaway; never write "N/A"}

---
```

Rules for the four subsections (all four must be present for every module: the
graduation PDF renders exactly these four labeled sections per module):

- **Information Shared** and **Actions Taken** carry real content from this module, never placeholders.
- **Questions & Responses:** each substantive 👉 question you asked this module, paired with the bootcamper's actual answer, in ask order. If a module asked no substantive questions, write `- {none this module}`.
- **End-of-Module Summary:** the same What you accomplished / Files produced / Why it matters shown in the bootcamper-facing epilog (Step 3), persisted here as the permanent keepsake record (this subsection replaced the former Journal — INV-103); the **Bootcamper's takeaway** line is optional — include it only when the bootcamper gave a genuine takeaway, otherwise omit the line entirely (never write "N/A").
  - ⛔ **Write all three as labeled blocks — `**What you accomplished:**`, `**Files produced:**`, `**Why it matters:**` — never as one prose paragraph.** The three labels are what the recap PDF renders and what `--check` validates (INV-103); a summary written as flowing prose satisfies the *heading* and loses all three blocks. The renderer now prints any absent block as "(not recorded)" in the keepsake rather than letting it disappear, so an unlabeled summary is visible on the page — but a bootcamper's PDF should never carry that marker. Blocks with no content still get their label: "(no files — conceptual primer)" under **Files produced** is a real answer; silence is not.
  - ⛔ **The shape of each block is required too, not just its label.** (INV-176) `**What you accomplished:**` and `**Files produced:**` are **lists** — label on its own line, then one bullet per accomplishment, and one bullet per file with a short "— what it is" gloss, exactly as the template above shows. `**Why it matters:**` is **prose** and stays inline after its label. The PDF renders bullets as bullets and inline text as one wrapped paragraph, so a list written inline — most often as a comma-joined run of paths — arrives in the keepsake as a paragraph, and nothing downstream can turn it back into a list: `--check` validates the label, not the shape. Write the shape you want the bootcamper to keep.
- **Visualization screenshots:** when this module produced a visualization, capture is best-effort (see "Capturing visualization screenshots" below) — but **when a capture succeeds, embedding every screenshot it produced is required**, not optional, and no count cap applies (INV-146): add them all to this module's **Actions Taken** as Markdown images — `![caption](visualizations/<name>-<tab-slug>.png)` — in the same turn the capture ran, in the app's tab order. ⛔ **Each image goes on a line of its own, with nothing before it — not as a `- ` bullet, even though Actions Taken is otherwise a bulleted list.** (INV-242) Write it like this, directly beneath the bullets:

  ```markdown
  ### Actions Taken
  - Captured the results visualization (3 tabs) and embedded each below.

  ![Entity Graph — 12 resolved entities from 3 sources](visualizations/results_visualization-entity-graph.png)
  ```

  Its own line is the block form every Markdown renderer treats as an image, and it is the form the recap generator is written against. The generator also tolerates a leading `- `, so recaps already written as bullets still render — but write the canonical form: the tolerance exists to rescue past recaps, not as a second supported style. ⛔ **The path is relative to `docs/bootcamp_recap.md`, the file you are writing into — so it is `visualizations/…`, never `docs/visualizations/…`** (INV-161). The recap lives in `docs/`, so a `docs/`-prefixed path resolves to `docs/docs/…` and matches nothing: it breaks the Markdown recap for a human reader *and* drops the image from the PDF. Write the one path that is correct for both; never adjust it to suit the renderer, and never `cd` to make it resolve. The graduation PDF embeds local images and **reports** every one it drops — naming it on stderr and printing an `embedded N of M images` count (INV-162) — so an absent screenshot never breaks the recap PDF but is never silent either, and graduation backfills any capture whose embed was missed.

⛔ **Whenever a module step produces a bootcamper-facing artifact — a PDF, a PNG, an HTML
visualization — verify the artifact itself, not the exit code.** A zero exit, a written file, and a
self-reported metric are all necessary and none is sufficient: a capture helper exited 0 having
written three images of the same tab; a generator reported "content retained: 98%" with an entire
table drawn off the page. Neither raised an error.

So open it: view the PNG, rasterize the PDF page, grep the extracted text for a distinctive string you
know must be there, load the HTML and confirm the tab renders. Describe the artifact from what it
actually shows, never from what the step was supposed to produce (INV-115's principle, applied to
artifacts rather than parsed fields). This is best-effort and never blocks a module — if the tool to
inspect it is absent, say the artifact could not be verified rather than implying it was.

Append the section as plain, functional Markdown. Do not spend effort on CommonMark
prettification here (blank-line rules, `**Label:**` colon spacing, fence info strings):
graduation runs one normalization pass over the recap before the PDF renders (see
`ground-rules.md` → "Markdown files" and `../graduation/SKILL.md`). What matters at this step is
that the `## {Name}` heading (name-based, no catalog number) and all four subsections are present and carry real content.

### 2c. Verify it landed

Re-read `docs/bootcamp_recap.md` and confirm a `## {Name}` heading for the
just-completed module is present. If it is missing (a lost write or session
boundary), append it again before continuing.

In the same read, confirm this module's **End-of-Module Summary** carries all three labeled blocks
(`**What you accomplished:**`, `**Files produced:**`, `**Why it matters:**`). If any is absent, add it
now, from what this module actually did — the Step 3 epilog you just showed the bootcamper is the
same content, so copy it rather than composing something new. (Module 0 is the one module that runs
this step without Step 3 — it is exempt from the bootcamper-facing summary, INV-078/INV-092 — so
there is no epilog to copy and the three blocks are composed here from what the primer covered.
"(no files — conceptual primer)" is the honest **Files produced** answer for it.) This is the
cheapest place to catch it:
the module's own work is still in context, whereas graduation has to reconstruct it from artifacts
weeks of session-time later. Never invent a file that was not produced; write
"(no files — {reason})" when there genuinely were none.

Only then display the one-line confirmation: `Recap updated: {Name}.`

(The recap PDF is not rendered per-module: it is rendered once at graduation by
`scripts/generate_recap_pdf.py`, which reads this file. See `../graduation/SKILL.md`.)

### 2d. Finalize the in-progress checkpoint

During the module you kept an in-progress recap at `docs/progress/recap_checkpoint.md`
(see `ground-rules.md` → "Progress and state"), and the Power's durability hooks may
have folded it into `docs/bootcamp_recap.md` as a `<!-- RECAP-CHECKPOINT:START -->` …
`<!-- RECAP-CHECKPOINT:END -->` block. Now that the finalized `## {Name}` section is
appended (2b), that block is superseded. Do two things:

- Remove any `<!-- RECAP-CHECKPOINT:START -->` … `<!-- RECAP-CHECKPOINT:END -->` block
  from `docs/bootcamp_recap.md` (the finalized section replaces it — this keeps the
  recap clean and never rewrites a completed `## {Name}` section).
- Clear `docs/progress/recap_checkpoint.md` (empty the file or delete it) so the next
  module starts a fresh checkpoint. Either is safe: `checkpoint-tick.py` lays a fresh
  empty scaffold back down on the next turn if you delete it, and an emptied file is
  treated as an unfilled scaffold — the fold hooks skip both rather than appending an
  empty block to the recap.

## Capturing visualization screenshots (optional)

Whenever a module generates a visualization (an HTML page under `docs/visualizations/`), capture a
few screenshots of it so the recap shows what the bootcamper actually built, not just a
link. This runs at the visualization step, right after the page exists, and is **non-blocking with
graceful degradation** — never a 👉 question, and never a reason to stall.

**The per-tab procedure below is for the tabbed visualization app** — the Truth Set app and the
Module 7 results app, which share the six-tab contract. A **single-page** HTML deliverable (Data
Quality, Mapping, and Transformation's quality and mapping pages) has no tabs: capture it as **one
image** with `--single`, and embed that one image. It writes `{name}.png` — no tab slug — so the
embed target is predictable:

```bash
python3 <helper> --html docs/visualizations/{name}.html --out-dir docs/visualizations \
    --name {name} --single
```

⛔ **`--single`, not "no `--tabs`".** An omitted `--tabs` does not mean "no tabs", it means **all
six** — so the helper requests six tabs the page does not have, skips each one and reports it
(INV-122, correct behavior), and writes nothing. That is how every single-page deliverable used to
miss the recap silently. `--single` and `--tabs` cannot be combined; the helper refuses both together
rather than guessing.

⚠️ If a page with no tab controls is captured **without** `--single`, the helper now detects that and
captures it as one image anyway, telling you to pass `--single` next time. Do not rely on that: a
tabbed app whose tab ids are merely misspelled still reports and skips, exactly as before, because
capturing the whole page there would name a file for a tab it does not show.

For the tabbed app, it is a **tabbed** artifact, so capture is **one image per tab** — never several
shots of one tab. Procedure (parameterized by the visualization's `{html}` file or live `{url}`, and
a short `{name}`):

1. Run the bundled helper. Prefer the **live app's `localhost` URL** while the server is still up,
   because that is the only way the Search / Probe tab can show real results; fall back to the
   standalone snapshot file when the server is already down:

   ```bash
   # live app (preferred while it is running)
   python3 <helper> --url http://localhost:{port} --out-dir docs/visualizations \
       --name {name} --tabs graph,stats,matchkeys,features,overlap,probe --query "{a name in the data}"

   # standalone snapshot (no server needed)
   python3 <helper> --html docs/visualizations/{html} --out-dir docs/visualizations \
       --name {name} --tabs graph,stats,matchkeys,features,overlap,probe
   ```

   Resolve `<helper>` as `${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/capture_screenshots.py` (command/hook
   context) or `../bootcamp-onboarding/scripts/capture_screenshots.py` relative to a module skill. It tries several
   headless backends (Playwright, Selenium, headless Chrome/Chromium, `wkhtmltoimage`) and never
   fetches a remote URL (offline — INV-091). Pass only tabs the app actually shows for this data —
   the helper reports any tab that produced no image on stderr rather than dropping it silently.
2. **If it exits non-zero** (exit 2 = nothing was captured): skip screenshots, keep the
   visualization's HTML link in the recap, and continue. Honor verbosity (say nothing at the
   `minimal` preset). **Read which of the three reasons it gave** — they are not interchangeable and
   only one is about a missing install: no requested tab exists in this app; **no browser was found**
   (the message names every location searched); or **a browser was found but every capture failed**
   (the message names it). In the last two cases do **not** install a browser or suggest installing
   one — capture is dependency-optional by contract (INV-122), and a Windows machine that carried
   both Edge and Chrome was once told no capability was available, which sent the reader to install
   software they already had.
3. **If it succeeds** it prints one `<png path>⇥<tab label>` line per capture, and each file is
   named `{name}-<tab-slug>.png`. ⚠️ **Open the Entity Graph image and check the nodes are spread,
   not bunched in one corner.** A graph tab whose force simulation was restarted or captured too
   early produces a valid PNG of an empty-looking graph at exit 0 — the helper gives animated tabs a
   longer settle budget and the app's `activate()` no longer redraws an already-active tab, but this
   is the one image where "it rendered" and "it is right" come apart, and INV-123 requires the
   caption to come from the opened image anyway. A graph PNG far smaller than its siblings is the
   tell. **Keep every captured tab** — and, **as a required step, in the
   same turn** — embed them all in **this module's recap `Actions Taken`** as
   `![caption](visualizations/{name}-<tab-slug>.png)` — relative to `docs/bootcamp_recap.md`, so
   **`visualizations/…`, never `docs/visualizations/…`** (INV-161; a `docs/`-prefixed path resolves
   to `docs/docs/…` and embeds nothing). Writing the image lines is not
   optional once a capture succeeded; record it at the step checkpoint. The graduation PDF embeds
   these local images and reports any it drops (INV-162), and graduation backfills any that
   were captured but never embedded (see `../graduation/SKILL.md` Step 1).

   ⛔ **Do not prune to a "best" few.** Capture is one image per tab (INV-122), so every file is
   already a distinct view — there is nothing redundant to remove, and a count cap can only delete
   unique content. Delete only a true duplicate: two images of the *same* tab, which per-tab capture
   should not produce. Judging which shots are worth keeping is what previously dropped Merge
   Statistics, Match Keys and Feature Scores from a six-tab app — the three *analytical* tabs, since
   any such judgement pulls toward the most visually striking. The recap then showed the same three
   tabs in both visualization sections and the app looked narrower than it was.

   ⛔ **Embed in the app's tab order, never in capture or append order.** The order is the row order
   of the tab table in
   `../module-03b-truthset-visualization/visualization-api-reference.md` → "Tab identifiers and
   deep-linking" — read it there rather than restating the list, so a tab change updates one file.
   A tab that produced no image is simply skipped; the rest keep their relative order. The recap is
   a walkthrough of the app, so a reader must be able to line the images up against the interface
   left to right.

⛔ **Every caption is derived from the capture, never from the plan.** Build it from the tab label
the helper printed (which matches the filename slug), and — before writing it — **open the image and
confirm it shows that tab**. Describe only what is visible in it.

A caption asserting content the image does not contain is a defect of the same class INV-115
forbids: it renders the unverified as verified, in a permanent artifact the bootcamper is
encouraged to share. It has happened — captions reading "Cross-source overlap and match-key
frequency tabs" and "Search/Probe with a verified example query chip" were written for two images
that both showed the Entity Graph, because the app *is* tabbed so the captures were assumed to be
tab-diverse. Never infer image content from the visualization contract.

If the Search / Probe tab was captured from the **static snapshot** rather than the live server, its
search box is inert (the snapshot has no engine), so **caption it explicitly as the empty/inactive
state** — never imply a result set that was not captured.

⛔ **Omitting the image is not an alternative.** INV-146 requires every screenshot the capture
produced to reach the recap, and permits deleting only a true duplicate of the same tab. Omitting
it here does not even lose it: graduation's orphaned-screenshot backfill embeds every PNG the recap
does not already reference, and it captions from the tab slug alone — so the omitted image returns
with a bare "Search / Probe" caption and **nothing saying the search box is inert**, which is the
one outcome this instruction exists to prevent (INV-123). The caption is the remedy; there is no
second option.

## Step 3: End-of-module summary (shown to the bootcamper)

Present a short, skimmable summary from the bootcamper's point of view. This is a
required outcome of every module (INV-032) — one completion line and one four-part summary per
module, at that module's own close. **Lead with the lightly-highlighted completion line** — a bold
line wrapped in a thin rule of `─` characters above and below (more visible than plain prose,
lighter than the module-start banner's `━━━`/emoji triplet) — then the summary details. Render the
completion line as shown (bold, no module number), the rest as a plain summary:

──────────────────────────────────────────
**✅ Module complete: {Module name}**
──────────────────────────────────────────

```text
What you accomplished:
- {plain-language accomplishment 1}
- {accomplishment 2}

Files produced:
- `{path}` — {what it is}
- `{path}` — {what it is}

Why it matters:
{1-2 sentences tying this module's output to the bootcamper's goal.}

What's next:
Next: {next module name in your selected sequence} — {one line on what it does}.
```

If the module produced no new files (rare), say so plainly rather than inventing
paths. Keep the list to what the bootcamper cares about; suppress internal
bookkeeping.

This same What you accomplished / Files produced / Why it matters content is persisted into the
recap's **End-of-Module Summary** subsection (Step 2b) — keep the two consistent. "What's next" is
chat-only and is **not** written to the recap.

## Step 4: Transition question

Return to the module and ask its single transition 👉 question — "Are you ready to move on to the
next module: {next module name}?" (fill {next module name} with the next module in
`selected_modules`; after the last content module, use the graduation offer below instead). Ask it
**once**, after the module's summary. That question ends the turn. Do not combine it with the
summary content above into multiple questions: the summary is statements, the transition is the one
👉 question.

## Reaching graduation (after the last content module)

When the module just completed is the **last content module before Bootcamp graduation in
`selected_modules`** — always **Query, Visualize and Discover** (Module 7), which is
required in every path — do Steps 1-3 as usual, then, instead of a next-module
transition, offer graduation (the mandatory terminal module):

👉 **Would you like to graduate now and generate your production project and recap?**

On an affirmative reply, invoke the `graduation` skill. If the bootcamper wants to
keep exploring first, stay available and offer graduation again whenever they are
ready. Bootcamp graduation is the required close-out module; its production project and
migration checklist deliver the production-hardening guidance (performance,
security, monitoring, deployment) for every bootcamper.
