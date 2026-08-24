---
name: "bootcamp-enforcement-setup"
description: "Optionally install the Senzing bootcamp's Kiro enforcement hooks into this workspace, with disclosure and explicit consent. Use when the bootcamper says 'install the senzing bootcamp enforcement hooks'."
license: "Apache-2.0"
compatibility: "Runs on Linux, macOS, and Windows. Needs only the Python interpreter that runs the bootcamp scripts; no shell, and no Senzing MCP server."
metadata:
  author: "Senzing"
  owner: "kiro"
  tier: "2"
  role: "Hook_Installer"
  installer: "scripts/install_hooks.py"
---

# Bootcamp enforcement setup (Tier 2)

The bootcamp's rules are delivered in three tiers. **Tier 1 is always in force**: every rule a
template hook enforced mechanically is also written as an instruction, so the bootcamp is
complete and correct with zero hook definitions installed. This skill is **Tier 2**: it
optionally installs Kiro hook definitions into *this workspace* so two of those rules are
enforced mechanically instead of advisorily.

Installing is **optional and always the bootcamper's call.** It writes files into their
workspace, so nothing happens without disclosure first and an explicit yes.

## Read the Tier 1 rules either way

Whatever the bootcamper decides, these three files are the rule set you follow. Read them now,
before offering the install, and keep following them afterwards:

- [`senzing-bootcamp-tier1-ground-rules.md`](../bootcamp-onboarding/assets/kiro-hooks/tier1-instructions/senzing-bootcamp-tier1-ground-rules.md)
  — write location, secrets, containers stop-never-remove, one closing 👉 question
- [`senzing-bootcamp-tier1-session-lifecycle.md`](../bootcamp-onboarding/assets/kiro-hooks/tier1-instructions/senzing-bootcamp-tier1-session-lifecycle.md)
  — resume on session start, per-turn recap checkpoint, feedback watch, session close-out
- [`senzing-bootcamp-tier1-recap-folding.md`](../bootcamp-onboarding/assets/kiro-hooks/tier1-instructions/senzing-bootcamp-tier1-recap-folding.md)
  — folding the checkpoint into the durable recap

Installing hooks **backs** those rules; it never replaces them.

## What is being offered, in one paragraph the bootcamper can answer

Say this much and no more before asking:

- Two rules become mechanically enforced instead of advisory: **writes stay inside your
  project** (INV-200) and **no secret lands in a file the bootcamp writes** (INV-109). With
  hooks installed, an offending write is blocked rather than merely discouraged.
- Three more behaviors get automated: resume on session start, the per-turn recap checkpoint,
  and the feedback watch.
- It writes a small number of JSON files into `.kiro/hooks/` in their workspace. Every filename
  starts with `senzing-bootcamp-`, and removal is one command.
- Every hook script no-ops outside a bootcamp project: each one exits without acting when
  `config/bootcamp_progress.json` is absent, so an installed hook set never affects unrelated
  Kiro sessions.

## Run the installer — disclosure first, then consent

The installer is at `${PLUGIN_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py`.

**Run it with the same Python interpreter the bootcamp uses for its own scripts** — the project
virtualenv's interpreter if the bootcamper created one in module 02, otherwise whatever
interpreter the bootcamp has been running. This is not incidental: the installer writes the
absolute path of *the interpreter that ran it* into every hook command, so the interpreter you
choose here is the interpreter the hooks will use forever after. Never invoke it through a bare
`python3` on Windows.

### Step 1 — disclose

```
<python> ${PLUGIN_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py plan --workspace <project-root>
```

This writes nothing. It prints the **full path of every file it would write or delete**, the
resolved interpreter path, the resolved script directory, the exact command each hook will run,
and the list of other hook files in that directory it will leave untouched.

Show the bootcamper that list. Do not summarize the paths away — the point of this step is that
they see exactly what lands in their workspace before any of it does.

### Step 2 — ask, once

End the turn with exactly one 👉 question, along the lines of:

> 👉 Install these enforcement hooks into `.kiro/hooks/`?

Wait for the answer. Do not run step 3 on an assumption.

### Step 3 — record the answer

On yes:

```
<python> ${PLUGIN_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py install --consent granted --workspace <project-root>
```

On no:

```
<python> ${PLUGIN_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py install --consent declined --workspace <project-root>
```

The declined run writes nothing at all. Run it anyway rather than skipping it: it prints the
exact statement of which protections are now advisory, which is what the bootcamper needs to
hear, and it leaves a clear record of the answer.

Then continue the bootcamp from wherever the bootcamper was. This skill is a side trip, not a
gate — the bootcamp proceeds identically either way.

## If they decline

Say plainly what changed, and nothing more dramatic than the truth:

- The **write-location gate** is advisory. Nothing mechanically blocks a write that lands
  outside their project.
- The **secret gate** is advisory. Nothing mechanically blocks a write carrying a credential,
  key, token, or password.
- Everything else is unaffected. The closing-👉-question rule, recap folding, and session
  close-out are advisory whether or not hooks are installed, because Kiro's `Stop` trigger
  cannot block and Kiro has no `PreCompact` or `SessionEnd` trigger at all.
- No file was written into `.kiro/hooks/`.

You are then the enforcement. Follow the three Tier 1 files listed above, and offer the install
again only if the bootcamper raises it.

## After a Power upgrade, a Python upgrade, or a removed virtualenv

Installed hooks name absolute paths, so any of those three events can leave a hook pointing at
an interpreter or a script directory that no longer exists. A hook in that state fails quietly
— it does not warn.

The repair is to re-run the install. Re-running re-resolves **both** paths from scratch:

```
<python> ${PLUGIN_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py install --consent granted --workspace <project-root>
```

Re-running is safe by construction. The content written is a pure function of the shipped
definition plus the two resolved paths, so a second run against an unchanged environment leaves
`.kiro/hooks/` byte-identical to the first run's result and creates no duplicate hook entry;
files that already match are reported `unchanged` and not rewritten.

To check the current state without changing anything:

```
<python> ${PLUGIN_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py status --workspace <project-root>
```

## Removal

Two steps, the same shape as the install — disclose, then confirm:

```
<python> ${PLUGIN_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py remove --workspace <project-root>
<python> ${PLUGIN_ROOT}/skills/bootcamp-enforcement-setup/scripts/install_hooks.py remove --consent granted --workspace <project-root>
```

The first run lists exactly the files that would be deleted and every file that would be left
alone. The second deletes them.

Removal is defined by the `senzing-bootcamp-` filename prefix and nothing else, so it deletes
exactly the files this Power created — including any left by an earlier Power version — and
leaves every other hook file in that directory unchanged. A bootcamper can also delete those
files by hand; the prefix is the whole contract.

Removing the hooks returns the bootcamp to Tier 1. It does not remove any bootcamp content or
progress.

## Reduced capability is normal

The installer needs only the Python interpreter running it. If an optional runtime is missing —
Docker for the SDK modules, a browser for the truth-set visualization — say what is unavailable,
say what the bootcamper can still do, and continue. Never wedge a session on a missing optional
runtime, and never treat a missing optional runtime as a reason to skip or force this install.

To find out what this host actually has, run the guard. It reports what is available and exits
successfully whatever it finds, so it is safe to run at any point:

```
<python> ${PLUGIN_ROOT}/skills/bootcamp-onboarding/scripts/optional_runtime.py
```

Add `--json` for the same answer as data. The full reduced-capability path — what still works
without a container runtime, and what still works without a browser — is the
`optional-runtime` rule in
[`senzing-bootcamp-tier1-ground-rules.md`](../bootcamp-onboarding/assets/kiro-hooks/tier1-instructions/senzing-bootcamp-tier1-ground-rules.md).
Follow it there rather than restating it here.

Two things worth being explicit about, because bootcampers ask:

- **This install is independent of every optional runtime.** The hooks it writes name the
  interpreter that ran the installer and nothing else. A workspace with no Docker installs the
  same hook set, byte for byte, as one with Docker.
- **Tier 1 does not degrade with the host.** A bootcamper with no container runtime still gets
  the complete rule set and the complete prose experience; what they lose is the container-backed
  exercises of the SDK modules, and the SDK setup module's own platform routing tells them
  whether a container is the required path for their operating system and language.

## Scope

This skill installs, inspects, and removes hook definitions. It holds no bootcamp content: the
rules live in the three Tier 1 files above and in the ported bootcamp prose. If the bootcamper
wants to start or resume the bootcamp, that is the `start-bootcamp` skill, whose trigger phrase
is stated in its own description.

## If the installer reports an error

It fails closed and writes nothing, so an error never leaves a half-installed hook set. The two
worth recognizing:

- `E_SCRIPTS_DIR_MISSING` or `E_SCRIPT_MISSING` — the ported script set is not where the
  installer expected it, so a hook would have pointed at a script that does not exist. Report
  the path it printed; do not work around it by hand-editing a hook file.
- `E_INTERPRETER_UNRESOLVED` — the interpreter running the installer has no usable absolute
  path. Re-run with a normal Python interpreter rather than an embedded or frozen one.

In every case, relay what it reported and stay on Tier 1. A missing enforcement hook costs
enforcement; a hand-patched hook file costs correctness.
