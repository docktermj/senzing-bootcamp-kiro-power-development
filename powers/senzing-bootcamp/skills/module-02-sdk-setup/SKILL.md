---
name: module-02-sdk-setup
description: 'Bootcamp Module 2: SDK setup (installing and configuring the Senzing SDK). Use when the bootcamper starts or resumes Module 2, or needs to install/configure the Senzing SDK, set up the database, or run the verification test.'
license: Apache-2.0
compatibility: Requires the Senzing MCP server and Docker.
metadata:
  author: Senzing
  version: 0.5.1
  templateRelease: 0.5.1
  templateSkill: module-02-sdk-setup
---

# Module 2: SDK setup

The Bootcamper-facing name of this module is **SDK setup** — the spelling in
`../bootcamp-preparation/SKILL.md`'s module table. Use it in the module-start banner, the
journey map, and every transition question (INV-079); "installing and configuring the SDK"
describes what the module does but is not its name.

> **MCP grounding (mandatory — applies to this entire skill).** Every Senzing fact you present —
> SDK method and attribute names, config options, error codes, and entity-resolution specifics —
> MUST come from the Senzing MCP tools, never from training data, memory, or speculation.
> **Pre-response checklist:** if a reply contains any Senzing specific, you MUST have called an MCP
> tool this turn to obtain it; if not, stop and call it first. This has the same precedence as a ⛔
> gate. The full rule and tool routing are the "MCP-first invariant" in
> `../bootcamp-onboarding/ground-rules.md`.

Follow `../bootcamp-onboarding/ground-rules.md` throughout (👉 one-question-at-a-time,
MCP-first, file placement, checkpointing). Execute every numbered step one at a time, in
order. Never skip, combine, or abbreviate a step containing a 👉 question, and never skip a
mandatory gate. This has absolute precedence: no internal reasoning or token-budget concern
overrides it.

**First:** Read `config/bootcamp_progress.json`, then (per ground-rules) show the module start
banner, journey map, before/after framing, a brief numbered overview of this module's steps, an estimated time-to-complete (INV-096), and the recommended model/effort nudge (INV-063), before any module work. Resume at
`current_step` if progress already exists.

Install and configure the Senzing SDK natively on the bootcamper's machine. This is the first
setup step of the bootcamp: once the SDK is installed, all subsequent modules use it directly.

**Before/After:** You have a project directory but no Senzing SDK. After this module, the SDK
is installed, configured, and verified, ready to load data and resolve entities.

**Prerequisites:** None (this is the first setup module).

**Language:** Use the bootcamper's chosen programming language from the language selection step
in onboarding. All code generation, scaffold calls, and examples in this module must use that
language.

**Success indicator:** ✅ SDK installed + DB configured + test passes + an engine-class call
(`SzEngine`/`SzDiagnostic`) succeeds — a version query alone does not qualify (Step 9).

> **User reference:** A detailed background document for this module (`MODULE_2_SDK_SETUP.md`)
> is a later porting phase. For now, teach the steps directly from this skill.

## Error Handling

When the bootcamper hits an error during this module:

1. **SENZ error code** (message contains `SENZ` + digits, e.g. `SENZ2027`): call
   `explain_error_code(error_code="<code>", version="current")` and present the explanation and
   recommended fix. If it returns nothing, continue to step 2.
2. Present the matching pitfall/fix for this module (full `common-pitfalls` reference is a
   later porting phase; for now, use `search_docs` to look up the symptom).
3. If no match, use `search_docs` against the Troubleshooting-by-Symptom guidance and general
   pitfalls.

> The TypeScript from-source build has its own recovery branch (see Step 3). A mid-build
> compile failure is handled there, not by this generic SENZ-code path.

## Step 1: Check for Existing Installation (MUST DO FIRST)

Before doing anything else in this module, check if the Senzing SDK is already installed and
working. There is no reason to re-install it.

Run a language-appropriate import/version check for the bootcamper's chosen language. Use
`sdk_guide(topic='install', platform='<user_platform>', language='<chosen_language>', version='current')`
to get the correct verification command.

**Filesystem fallback (if the import check fails):** The import check fails for reasons that have
nothing to do with the SDK being absent — `PYTHONPATH` unset on Linux, `DYLD_LIBRARY_PATH` not
exported before the JVM starts on macOS, `CLASSPATH` unset on Windows — so before concluding
anything, check for the **platform's native library**. That is the artifact which must exist for the
SDK to work, and it is what `sdk_guide` names for each platform (**INV-001**: all three are
supported, so all three are listed):

| Platform | Native library — verify this exists |
|---|---|
| `linux_apt`, `linux_yum` | `/opt/senzing/er/lib/libSz.so` |
| `macos_arm` | `$(brew --prefix)/opt/senzing/er/lib/libSz.dylib` (never a hardcoded `/opt/homebrew`) |
| `windows` | `%SENZING_DIR%\lib\Sz.dll` — `SENZING_DIR` already points at the `er` subdirectory |
| `docker` | Not applicable — there is no host install to probe; the image tag is the version |

(Each path as `sdk_guide(topic='install', platform=…)` gives it under `post_install`/`env_vars`,
verified on MCP server 1.32.9, docs indexed 2026-08-11 20:52 UTC, 2026-08-13.)

If the library is present, report the SDK as installed, skip Steps 2 and 3 entirely, and proceed to
Step 4 verification.

⛔ **Only conclude "not installed" for a platform whose library you actually checked.** If the
platform is undetermined, or the check could not run, the result is **unknown** — say so and name
why (INV-163), then treat it as unknown rather than reporting an absent SDK. Concluding "not
installed" from a path that cannot exist on this platform is how a Bootcamper with a working install
gets sent to reinstall it, which is exactly what this step opens by forbidding.

**Reading the version once the library is found:** use the primary route — the language version
check, or `SzProduct.get_version()`, which returns `VERSION`, `BUILD_DATE`, `BUILD_NUMBER` and
`NATIVE_API_VERSION` (`search_docs`, server 1.32.9, 2026-08-13). Failing that, build metadata sits
in `szBuildVersion.json`: on Linux under `/opt/senzing/er/` (and also `/opt/senzing/data/`), and on
Windows in the **sibling** `data` directory, not under `%SENZING_DIR%` — see "Comparing the two
versions" in Step 1b. ⚠️ Those are **environment observations, not MCP-sourced facts** (Linux
observed 2026-08-13; the macOS location is unknown), so if the file is not where expected, read the
version through the SDK rather than concluding the SDK is missing.
<!-- MCP-NEGATIVE: search_docs(query='szBuildVersion.json build version file location') — no indexed document gives that file's path on any platform; all four hits are SzProduct.get_version()/engine_version SDK examples — owner: search_docs IS the corpus route for a documented file location, and the version fact the corpus does serve is the SDK's get_version() rather than a file, so the SDK route is where the reader must go (routing negative) — server 1.32.9, 2026-08-13 -->

**If the SDK is found and version is V4.0+:**

Tell the user: "Senzing SDK is already installed (version [X]). No need to reinstall, skipping
straight to configuration verification."

Then run **Step 1b** below to see whether a newer release is available, and offer it. A working
install is never replaced without the bootcamper saying so.

- **Skip the *installation* — Step 2, and Step 3's install commands.** Not Step 3 entirely: see the
  required stop below. What is redundant on an existing install is fetching and installing the SDK;
  nothing else in Step 3 is.
- **Still do Step 3's environment-script work** ("Create the project-local environment script"), then
  jump to Step 4 (verify installation) to confirm it works with the chosen language.
- If Step 4 passes, proceed to Step 5 (License), which confirms the built-in evaluation license
  without prompting (the License Key gate is in Module 4, per INV-093). After Step 5, proceed to
  Step 6 (create the project directory structure), then Step 7 (database).
- Mark Module 2 as complete once verification passes.

> **Required stops:** These steps are NEVER skipped, even when the SDK is already installed:
>
> - **Step 3's environment script** (`src/../bootcamp-onboarding/scripts/senzing-env.sh`, or `senzing-env.bat` on Windows):
>   ⛔ **the single most likely thing an existing install is missing.** Step 3 is titled "Install
>   Senzing SDK" and does **two** jobs — it installs the SDK *and* it writes the project-local script
>   that exports the library and Python paths. Only the first is redundant here. Skipping both leaves
>   the bootcamper with a healthy install and no environment, and every later module then fails at
>   import with `libSz.so: cannot open shared object file` — which reads as a broken install, in a
>   *later* module, far from this decision. Step 1's own fallback predicts exactly this state (it
>   exists because the import check can fail with `PYTHONPATH` unset on a working install), so
>   routing past the step that fixes it is the specific trap.
>   **Take the variable values from `sdk_guide(topic='install', platform=…, language=…)`** —
>   `install.platform.env_vars` carries them — rather than from an install transcript, because no
>   install ran (INV-080). Write the script with the **same** implementation the install path uses:
>   the zsh/bash path-resolution idiom, the fail-loudly root check, and the empty-value guard (see
>   "The env script MUST resolve its own path…" in Step 3). One implementation, not two.
> - **Step 4** (Verify Installation): confirms the SDK works with the chosen language.
> - **Step 5** (License): a brief, no-prompt confirmation that the built-in evaluation license is
>   active (the volume-gated License Key gate itself lives in Module 4, per INV-093).

**If the SDK is found but version is incompatible (<V4.0):**

Tell the user: "Senzing SDK found but it's version [X]. The bootcamp requires V4.0+. We'll need
to upgrade." Proceed with Steps 2-3 for the upgrade.

**If the SDK is NOT found:**

Tell the user: "Senzing SDK is not installed yet. Let's set it up, this is a one-time process."
Proceed with Step 2.

**Checkpoint:** write step 1 to `config/bootcamp_progress.json`.

## Step 1b: Offer an update when a newer release exists (V4.0+ installs only)

Step 1 compares the installed version against the **V4.0 floor**. That answers "is it new enough
to work", not "is it the newest available" — two different questions. Ask the second one too,
then **offer**. Never update silently, and never treat declining as a problem.

⛔ **Non-blocking, start to finish (INV-048).** A check that cannot run, a repository that is
unreachable, or an update that fails must warn and continue with the working install. This step
improves a working state; it is never a prerequisite for Module 2.

### The three platform families need three different mechanisms

⛔ **The package manager that installed Senzing is the authority on what is available** — not the
MCP server. `get_capabilities` reports `senzing_version` as the string `"current"`, not a number
(server 1.32.2, verified 2026-07-31), so it cannot answer this.

⛔ **Two kinds of command follow, and they have different owners. Do not treat them alike.**

- **Server-documented (on loan — re-read it, do not trust the copy below).** The *install* command
  comes from `sdk_guide(topic='install', platform='<platform>', language='<language>')`. Its live
  response is authoritative; the forms below are a dated illustration (server 1.32.2, verified
  2026-07-31) so you can see the shape without a round trip. If the response differs, **the
  response wins.**
- **Plugin-owned (there is nothing to re-ask).** The **installed-version query** and the
  **available-version check** are ordinary package-manager commands. `sdk_guide` returns *install*
  commands and *presence* checks (`ls libSz.so`, `Test-Path Sz.dll`) — it documents **no version
  query and no update check on any of the four platforms** (verified 2026-07-31). So if you look
  for these in its response and do not find them, that is expected, not an error: use the ones
  below as given.

  ⚠️ **The plugin-owned commands are exercised on Linux only.** This plugin's own test suite runs
  on Linux, so the `brew` and `scoop` forms below are standard package-manager usage that no test
  here has ever executed. Treat their *output* as the thing to check, not their success: read what
  the command actually printed rather than assuming the version it reported, and on macOS obey the
  zero-exit-code warning further down without exception. This is the same discipline INV-163
  requires — say what you could not verify — applied to a command rather than a check.

⚠️ **On macOS and Windows the update command is plugin-owned too.** The server documents
`brew install --cask` and `scoop install`, never `brew upgrade --cask` or `scoop update` (checked
across `install_commands`, `gotchas` and `post_install` for both, re-confirmed 2026-08-13). Only on
apt and yum is the update command the same server-documented `install` command. That asymmetry is the
same coverage gap reported upstream on 2026-08-13 — the server documents installing, not updating.
<!-- Date corrected from 2026-07-31 on 2026-08-13: the earlier claim was unsubstantiated. A
     feature request WAS sent on 2026-07-31, but for the stdio-mode / private-deployment route — a
     different subject — and the two had been conflated, so 2026-08-13 is this gap's first report
     rather than a duplicate. Full evidence chain in the maintainer's development record. -->
<!-- MCP-NEGATIVE: sdk_guide(topic='install', platform='macos_arm') and the same call with platform='windows' — install_commands, gotchas and post_install carry no brew upgrade --cask and no scoop update — owner: sdk_guide(topic='install', platform=<that platform>) IS the route that would carry an update command for each package manager, and both document installing only (absence negative) — server 1.32.9, 2026-08-13 -->

**Linux, apt (`linux_apt`):**

<!-- MCP-NEGATIVE: sdk_guide(topic='install', platform='linux_apt') — install_commands, gotchas and post_install carry no dpkg-query and no apt-cache policy; it verifies with ls /opt/senzing/er/lib/libSz.so, an existence probe — owner: sdk_guide(topic='install', platform='linux_apt') IS the route that would carry an installed-version query for apt, and it documents installing and existence-verification only (absence negative) — server 1.32.9, 2026-08-13 -->

```bash
# plugin-owned — sdk_guide documents neither of these
dpkg-query -W -f='${Version}\n' senzingsdk-runtime   # installed, e.g. 4.3.3-26191
apt-cache policy senzingsdk-runtime                  # Candidate: is what the repo offers
# server-documented — re-read from sdk_guide; this form is a dated illustration
sudo apt install -y senzingsdk-runtime senzingsdk-setup   # takes the newest available
```

**Linux, yum/dnf (`linux_yum`):** *plugin-owned* —
`rpm -q --qf '%{VERSION}-%{RELEASE}\n' senzingsdk-runtime` for installed, and
`yum check-update senzingsdk-runtime` for available (**`dnf` on RHEL 8+/Fedora**).
*Server-documented* — `sudo yum install -y senzingsdk-runtime senzingsdk-setup` to update
(re-read it from `sdk_guide`; the form here is a dated illustration).

> ⚠️ **Do not use `direct_download` on yum.** `sdk_guide(platform='linux_yum')` returns a
> `direct_download` block, but its packages are **`.deb` files with `sudo apt install` commands**
> (verified 2026-07-31, server 1.32.2). They are wrong for an rpm system. `direct_download` is the
> apt/firewalled route only.

**macOS, Homebrew cask (`macos_arm`):**

<!-- MCP-NEGATIVE: sdk_guide(topic='install', platform='macos_arm') — no brew outdated, brew info or brew upgrade anywhere in the response; the brew commands it does carry are tap, trust, install --cask, uninstall --cask, untap, install/link libpq, and --prefix — owner: sdk_guide(topic='install', platform='macos_arm') IS the route that would carry a version-management command for the cask, and it carries none (absence negative) — server 1.32.9, 2026-08-13 -->

```bash
# ALL plugin-owned — sdk_guide documents no brew version-management command:
# never outdated, info or upgrade (checked across its whole response, 2026-08-13)
brew outdated --cask senzingsdk    # nothing printed = up to date
brew info --cask senzingsdk        # installed and latest versions
brew upgrade --cask senzingsdk     # takes the newest available
```

⛔ **A ZERO EXIT CODE FROM `brew` DOES NOT MEAN IT INSTALLED** (INV-218). If the EULA variable's name or
value is wrong the cask prints "No interactive terminal detected", purges the download, then
**still prints its Caveats block listing install paths** — so it reads as success while installing
nothing. After any macOS update, probe the artifact:

```bash
test -f "$(brew --prefix)/opt/senzing/er/lib/libSz.dylib" && ls "$(brew --prefix)/opt/senzing/data"/*TransRules.sz
```

Also on macOS: the tap must be trusted on Homebrew 6+ (`brew trust senzing/senzingsdk`), and
**`SENZING_ROOT` can move between versions** — re-export the env vars from
`sdk_guide(topic='install', platform='macos_arm')` after updating rather than assuming the old
paths still resolve.

**Windows, Scoop (`windows`):**

<!-- MCP-NEGATIVE: sdk_guide(topic='install', platform='windows') — no scoop status, scoop info or scoop update anywhere in the response; the scoop commands it does carry are bucket add, install, and config (for the EULA variable) — owner: sdk_guide(topic='install', platform='windows') IS the route that would carry a version-management command for Scoop, and it carries none (absence negative) — server 1.32.9, 2026-08-13 -->

```powershell
# plugin-owned — sdk_guide documents no scoop version-management command:
# never status, info or update (checked across its whole response, 2026-08-13)
scoop status                          # lists packages with updates available
scoop info senzingsdk/senzingsdk      # installed and latest versions
scoop update senzingsdk/senzingsdk    # takes the newest available
# server-documented — the presence probe sdk_guide gives under post_install
Test-Path "$env:SENZING_DIR\lib\Sz.dll"   # verify it actually installed
```

**Docker (`docker`):** there is nothing to update in place — the **image tag is the version**.
Offer to pull a newer tag and recreate the container instead, and do not run a package-manager
update inside it.

### Comparing the two versions

⚠️ **`szBuildVersion.json` and the package version differ by one character.** Step 1's filesystem
fallback reads `BUILD_VERSION` from that file, which uses a **dot** where every package manager
uses a **hyphen**:

| Source | Value |
|---|---|
| `dpkg-query` / `rpm -q` / `direct_download` filename | `4.3.3-26191` |
| `szBuildVersion.json` → `BUILD_VERSION` | `4.3.3.26191` |

Comparing those two raw strings reports a difference where none exists. **Prefer the package
manager's version string**; when only the JSON is available, normalize the separator before
comparing. (Observed on a real 4.3.3-26191 install, 2026-07-31 — an environment observation, not
an MCP-sourced fact.) On Windows that file is in the **sibling** `data` directory, not under
`%SENZING_DIR%`.

⛔ **If the available version cannot be determined, say the check was skipped and name why**
(INV-163). "No data" is never "up to date" — an unreachable repository, a missing package manager,
or an install that no package manager owns are all *unknown*, and reporting them as current is the
one outcome worse than not checking.

### The offer

Only when a newer version is genuinely available. **One 👉 question, its own turn** (INV-251), and
it ends the turn:

> 👉 **Senzing [available] is available and you have [installed] installed — would you like to
> update?** (reply no to keep your current version; or name a specific version)

- **On no:** one line — "Keeping [installed]." — then continue to Step 4. Nothing recorded as a
  failure, and **do not ask again** this session or the next (INV-006).
- **On yes:** update to the newest available using the platform command above.
- **On a named version:** on **apt**, use the versioned `direct_download` URL from
  `sdk_guide(topic='install', platform='linux_apt')` — the filenames carry the version and each
  has a `sha256`; **verify that checksum before installing**, and note the download needs
  `mcp.senzing.com` reachable with no inline fallback. ⛔ For **Homebrew casks and Scoop**, a
  version-exact install is **not documented by the server** — say so and offer the latest instead,
  rather than inventing a pin.

⛔ **Ask the EULA question before any package installs** — reuse the existing wording in Step 3
Phase 2 rather than writing a second copy. An update is an install.

⛔ **The EULA variable differs per platform, and a wrong one is silently ignored:**

| Platform | Variable | Value |
|---|---|---|
| `linux_apt`, `linux_yum` | `SENZING_ACCEPT_EULA` | `I_ACCEPT_THE_SENZING_EULA` |
| `macos_arm` | `HOMEBREW_SENZING_ACCEPT_EULA` | `i_accept_the_senzing_eula` (**lowercase**) |
| `windows` | `SENZING_ACCEPT_EULA` | `I_ACCEPT_THE_SENZING_EULA` |

(All three verified against `sdk_guide` on server 1.32.2, 2026-07-31.) Getting the name or value
wrong does not error — the install does nothing and reports success, which is why the
verification below is required rather than advisory.

### After updating

1. **Re-run Step 4** (verify installation). It is already a required stop; route through it.
2. **Probe the platform artifact** as shown above — exit 0 is not evidence (INV-218).
3. **If verification fails**, say so plainly, **name the version that was working**, and do
   **not** mark Module 2 complete. Reinstalling the previous version is the fallback; on apt its
   exact `.deb` is still addressable by filename.

⚠️ **Senzing documents no 4.x → 4.y update procedure.** `search_docs` returns only V3→V4 migration
material (`sz_dbupgrade`, `sz_configupgrade`, `sz_configtool`), and `sdk_guide` has no `upgrade`
topic (re-checked 2026-08-13). So whether a point release needs any schema or config step is
**undocumented, not known to be unnecessary**. Say that in the offer, and if the bootcamper already
has a populated repository, mention that the update touches the SDK and not their data — then let
them decide.
<!-- MCP-NEGATIVE: search_docs(query='upgrade Senzing SDK 4.3 to 4.4 procedure') plus get_capabilities' sdk_guide topic enum — no 4.x-to-4.y update procedure anywhere; all six hits are V3-to-V4 (sz_dbupgrade, sz_configupgrade, breaking-changes, Migration.md) and the topic list carries no upgrade entry — owner: search_docs IS the corpus route for a documented procedure and sdk_guide's own topic enum is the authority on its topics, so both routes that would carry it were asked and both are empty (absence negative) — server 1.32.9, 2026-08-13 -->

**Checkpoint:** record the outcome — `up-to-date`, `update-declined`, `updated-to-[version]`, or
`check-skipped-[reason]` — under step 1 in `config/bootcamp_progress.json`, so a resumed session
does not re-offer what was already declined.

## Step 2: Determine Platform

**Detect first, do not ask.** This gate is satisfied by *determining* the platform, not by asking
a question. Read `os`/`arch` from `config/bootcamp_preferences.yaml` (persisted during onboarding);
if absent, detect from the environment/system context (else run `uname`/`systeminfo`). State the
detected platform in one line and proceed — e.g. "Detected macOS on Apple Silicon; say so if that's
wrong." For macOS, also establish whether it is Apple Silicon (M1/M2/M3/M4) or Intel from the same
source.

**Fallback only** — when detection is genuinely unavailable or ambiguous, ask this pinned question
and wait:

👉 **Which operating system and processor architecture are you using? Reply with a number:**

1. Linux (x86-64)
2. Linux (ARM64)
3. macOS (Apple Silicon)
4. macOS (Intel)
5. Windows (x86-64)

*(Internal: end the turn on this question and wait.)*

Then resolve the `sdk_guide` platform value using the rules below. Do NOT assume a native
install: several OS + language combinations require Docker. The MCP server is authoritative;
if uncertain, call `sdk_guide(topic='install')` with no platform to get the live decision tree.

**Platform options for `sdk_guide`:**

- `platform='linux_apt'`: Debian/Ubuntu/Mint (apt/dpkg)
- `platform='linux_yum'`: RHEL/Fedora/Amazon Linux (yum/dnf)
- `platform='macos_arm'`: macOS Apple Silicon (Homebrew cask)
- `platform='windows'`: Windows 10/11 (Scoop)
- `platform='docker'`: Platform-independent container; the fallback and the required path for
  several cases below

**Routing rules (apply in order):**

1. Chosen language is Python AND OS is macOS or Windows → **`platform='docker'`**. The Python
   SDK is only supported on Linux; on macOS/Windows it must run in a container.
2. macOS Intel → **`platform='docker'`**. There is no native Intel-Mac install: the Homebrew
   tap is Apple Silicon (ARM64) only.
3. macOS Apple Silicon (non-Python) → **`platform='macos_arm'`**. If the chosen language runs
   on the JVM (Java), also read "The launch environment" in Step 3 before the first run —
   installing the SDK is not the same as being able to launch against it.
4. Windows without Scoop (non-Python) → **`platform='docker'`**. With Scoop available →
   **`platform='windows'`**.
5. Linux → **`platform='linux_apt'`** or **`platform='linux_yum'`** based on the package
   manager.

When a learner lands on Docker because of these rules, briefly explain why (e.g., "The Senzing
Python SDK is Linux-only, so on macOS we'll run it in a container") so the redirect doesn't
feel arbitrary.

Use `sdk_guide` with `topic='install'`, the resolved `platform`, and the bootcamper's chosen
language as the `language` parameter to get current installation commands. The MCP server
always has the latest instructions.

**Checkpoint:** write step 2 to `config/bootcamp_progress.json`.

## Step 3: Install Senzing SDK

Follow the platform-specific instructions from `sdk_guide`. Installation has three phases.

**Before recommending any approach**, call `search_docs` with `category='anti_patterns'` to
check for known pitfalls on the user's platform.

**Phase 1: Install the SDK package (execute without stopping):**

For native installs (`linux_apt`, `linux_yum`, `macos_arm`, `windows`):

1. Add the Senzing package repository.
2. Install the Senzing SDK package.

For the `docker` path (Intel Mac, Python on macOS/Windows, or Windows without Scoop):

- **Do not use the pre-built `senzing/senzingsdk-tools` images.** They require PostgreSQL and
  do not support SQLite, which is the bootcamp default (Step 7). Instead, run a plain Linux
  container (e.g., `debian:bookworm-slim`) and follow the `linux_apt` steps inside it so SQLite
  keeps working.
- Mount the bootcamper's project directory into the container so all artifacts (database,
  config, source) land in the working directory, not inside an ephemeral container layer.
- Call `sdk_guide(topic='install', platform='docker', language='<chosen_language>')` for the
  current container commands and image names.
- Never drive interactive Senzing CLI tools (`sz_configtool`, `sz_explorer`): they require
  human input. Generate SDK code via `generate_scaffold` instead.
- Senzing publishes native ARM64 images, so no x86 emulation is needed on Apple Silicon.
- **Record the container for lifecycle tracking (INV-101).** When you start the container,
  give it a stable `--name` and append an entry to a `docker_containers` list in
  `config/bootcamp_progress.json` — at least its `name` and the `runtime` you actually used
  (`docker`, `podman`, or `container` for Apple's `container` CLI); also `image` and `purpose`
  when handy. **Record the runtime truthfully**: the hooks stop and report each container with
  the CLI named there, so a wrong value means a container is reported under a tool that never
  started it. An entry with no `runtime` is treated as `docker`. The `SessionEnd` hook stops
  recorded containers on exit (`<runtime> stop`, not remove) and `SessionStart` surfaces them on
  resume so they can be restarted or regenerated. (The list key stays `docker_containers` for
  compatibility with in-flight bootcamps, whatever runtime its entries name.)

**Phase 2: EULA acceptance (requires bootcamper input):**

The Senzing SDK requires EULA acceptance before use. Tell the bootcamper they can review it at
<https://senzing.com/end-user-license-agreement/>, then present the EULA question:

👉 **Do you accept the Senzing End User License Agreement (EULA)?** (respond yes or no)

*(Internal: end the turn on this question and wait. Do not proceed until the bootcamper
answers.)*

Once the bootcamper responds, act on their answer:

- **If they accept the EULA:** proceed to Phase 3 to install language-specific SDK bindings.
- **If they decline the EULA:** stop the installation. Explain: "The Senzing SDK cannot be used
  without EULA acceptance. The remaining installation steps and subsequent bootcamp modules
  require the SDK." Do not install language bindings and do not write the checkpoint. Stop here.

**Phase 3: Install language bindings (only after EULA acceptance):**

3. Install the language-specific SDK bindings — **from that ecosystem's package manager for Java
   (Maven/Gradle), C# (NuGet) and TypeScript, and NOT from a package manager at all for Python.**

   ⛔ **Python: there is nothing to install here, and `pip install senzing` is an error-severity
   anti-pattern.** (INV-222 — INV-066's pip rules govern the plugin's own tooling only.) The `senzing` and `senzing_core` packages **ship inside `senzingsdk-runtime`**,
   which the earlier phase already installed, so Python's Step 3 work is to make them importable —
   not to fetch them. Take the paths from the server, never from this file (INV-080):
   `sdk_guide(topic='install', platform='<platform>', language='python')` returns them in
   `install.platform.env_vars` (`PYTHONPATH`, and `LD_LIBRARY_PATH` for when the native library is
   not found automatically) and repeats the rule verbatim in `install.platform.gotchas[]`.
   `generate_scaffold(language='python', workflow=<any>)` carries the same rule as an
   `anti_patterns[]` entry at **`severity: error`**, for **every** workflow it scaffolds — quoted
   below because the wording is the argument (re-verified live, MCP server 1.32.9, 2026-08-14):

   > "The senzing and senzing-core Python packages ship with senzingsdk-runtime at
   > /opt/senzing/er/sdk/python. Set PYTHONPATH=/opt/senzing/er/sdk/python:$PYTHONPATH — do NOT pip
   > install them. The PyPI packages are for unsupported community projects only."

   ⛔ **Why this matters more than most wrong commands: it succeeds.** `pip install senzing` exits 0,
   so this module reports a clean install — and the PyPI packages then **shadow** the SDK-shipped
   ones on `sys.path`. The damage surfaces a module later, as System verification's SDK
   initialization failing with `libSz.so: cannot open shared object file`, which reads as an
   environment fault rather than as the install instruction that caused it. It is also a **version
   skew**: this module's version check reads the *engine's* version through the native library, so
   it reports a current install while the bindings actually imported are older. The plugin's own
   shipped example recap records this happening on a real run
   (`../../docs/examples/bootcamp_recap.example.md`).

   **Detection — run it, do not assume:**

   ```bash
   python3 -c "import senzing, sys; print(senzing.__file__)"
   ```

   If the path is **not** under the SDK's Python directory (`PYTHONPATH` as the server returned it),
   PyPI packages are shadowing the real ones. Remedy: uninstall them
   (`python3 -m pip uninstall -y senzing senzing_core`) **or** prepend the SDK path to `PYTHONPATH`
   so the shipped bindings win. Report which was done; do not leave both installed silently.

   ⚠️ **Platform asymmetry, stated deliberately.** The server's `platform_note` on
   `generate_scaffold(language='python', …)` is explicit (same server and date): the Python SDK is
   **only** supported on Linux, and "even if pip install appears to succeed, it is unsupported and
   may produce runtime errors" on macOS or Windows. So there is no macOS/Windows Python install to
   perform: the routes are another language (Java and C# official; Rust and TypeScript
   community-supported) or Docker/WSL2, which this module's platform routing already covers.

   For **Java, C# and TypeScript**, use that ecosystem's package manager as normal. ⚠️ The
   bare-`pip` prohibition still applies to the plugin's **own** tooling installs (`fpdf2`,
   Playwright — INV-066): always an explicit `python3 -m pip`, never a bare `pip`, and PEP 668
   handled with a project-local virtualenv. That rule is about *how* to run pip for the plugin's
   helpers; it never authorizes pip for the Senzing SDK, which is not a pip package at all.

**TypeScript/Node.js warning:** The TypeScript SDK (`sz-napi`) may require building from source
if prebuilt binaries are not available for the user's platform. This involves installing the
Rust toolchain, cloning `sz-rust-sdk` and `sz-rust-sdk-configtool` as Cargo dependencies, and
building the native addon with `napi-rs`. Warn the user upfront: "The TypeScript SDK setup is
more involved than other languages, it may require building native bindings from source, which
needs the Rust toolchain. If you'd prefer a faster setup, Java or C# typically have simpler
install paths." If they proceed with TypeScript, guide them through the full build sequence in
one go rather than letting them discover steps through trial and error.

**Windows-specific:** Building the TypeScript SDK from source on Windows requires Visual Studio
Build Tools (not the full IDE) with the "Desktop development with C++" workload. Install via
`winget install Microsoft.VisualStudio.2022.BuildTools` or download from
visualstudio.microsoft.com. The Rust toolchain installer (`rustup-init.exe`) will detect the
build tools automatically.

### Recovery: build-from-source failures (TypeScript)

> **Applies to the TypeScript from-source build only.** This branch handles a failure *during*
> the `sz-napi` from-source build described just above (the Rust toolchain / `napi-rs` /
> native-addon compile). It does not apply to other languages or to Senzing engine/runtime
> errors.

**1. Detection and routing.** If the from-source build exits non-zero, or reports a
native-addon, `node-gyp`, toolchain, or Node-version failure while compiling `sz-napi`, treat
it as a mid-build failure and enter **this** recovery branch. Do NOT fall through to the
module's generic Error Handling block (the `SENZ`-code → pitfalls → symptom path). That generic
path is tuned for Senzing engine/runtime errors and will not recognize a half-finished native
compile.

**2. Summarize before offering options.** Before presenting any options, state in plain
language which build stage failed and the single most likely cause, chosen from the known-cause
table below. Name the specific cause (for example, "the native addon failed to compile because
the C++ build toolchain is missing") rather than pasting the raw build log. If the failure
signal does not match any known cause, say so plainly ("this is an unrecognized build failure")
and still continue to the options: an unrecognized failure is never a dead end.

**3. Known-cause table.** Match the failure signal to one cause. The detailed per-cause fixes
live in a TypeScript "Common Environment Issues" reference (`lang-typescript.md`) that is a
later porting phase; until then, source the fixes from the Senzing MCP server (see item 5) and
the inline pointers here.

| Cause | Failure signal | Fix reference ("Common Environment Issues") |
|---|---|---|
| `NODE_VERSION` | `SyntaxError` on modern syntax, `ERR_UNSUPPORTED_ESM_URL_SCHEME`, Node.js older than 18 | "Node.js Version Conflicts" |
| `NATIVE_ADDON` | `gyp ERR! build error`, `Cannot find module '.../*.node'` | "Native Addon Build Failures (node-gyp)" |
| `TOOLCHAIN` | missing C++ compiler, missing Rust toolchain, or missing Visual Studio Build Tools | "Native Addon Build Failures (node-gyp)" plus the Windows note above in this Phase 3 |
| `MODULE_SYSTEM` | `ERR_REQUIRE_ESM`, `Cannot use import statement outside a module` | "ESM vs CommonJS Module Resolution" |
| `PKG_MANAGER` | `ERESOLVE unable to resolve dependency tree`, lockfile conflicts | "Package Manager Conflicts" |

**4. Offer targeted options.** After the summary, always offer, at minimum, these three:

- **Fix the common cause:** apply the fix for the matched cause (see sourcing in the next
  item), then retry.
- **Retry the build:** re-run the from-source build sequence.
- **Fallback path:** proceed without a successful from-source build (see item 6). One fallback
  is switching to a language with a simpler install path (Java or C# typically have simpler
  paths); another is any prebuilt/alternative install route the MCP server reports as available.

**5. Sourcing (no hardcoded URLs).** For the detailed fix steps, use the Senzing MCP server:
`sdk_guide(topic='install', platform='<user_platform>', language='typescript')` and
`search_docs(category='anti_patterns')`. Never paste external URLs into this recovery flow; all
external/toolchain knowledge comes from the MCP tools (and, once ported, the `lang-typescript.md`
reference). If an MCP tool is unavailable, the fallback path still applies, so guidance degrades
gracefully rather than dead-ending.

**6. Resume or continue Module 2.** Neither continuation requires deep toolchain debugging:

- **On a successful retry** (the build now succeeds), resume the normal sequence: continue
  Phase 3 (install the language bindings) and proceed to Step 4 (verify installation).
- **On the fallback path**, continue Module 2 without a successful from-source build: proceed to
  Step 4 verification using the prebuilt/alternative install (or the newly chosen language) so
  setup is never blocked on the from-source compile.

**7. Never a dead end.** There is always a way forward: retry after a fix, or the fallback path.
If a retry fails again, re-summarize against the known-cause table (re-classifying on the new
signal) and re-offer the options; do not silently loop on the same error. If every option has
genuinely been exhausted, do not re-run the same failing command: state the current blocker in
plain language and present the support / next-step options (for example, capture the failure
details for a support request via `search_docs`, or take the fallback path if not already
tried). This terminal state names the blocker and the next step rather than looping.

**🚨 NEVER modify the user's global shell configuration** (`~/.zshrc`, `~/.bashrc`,
`~/.profile`, PowerShell `$PROFILE`, etc.) to set Senzing environment variables — **INV-199**.
Instead, create a project-local environment script at `src/../bootcamp-onboarding/scripts/senzing-env.sh` (or the
platform equivalent for Windows) that sets `SENZING_ROOT`, library paths, and any other
Senzing-specific variables. Source this script before running bootcamp tasks. This keeps the
bootcamp self-contained and avoids side effects on the user's system.

⛔ **`sdk_guide` will tell you to persist to a shell profile. Do not act on it — say so instead.**
`sdk_guide(topic='install', platform='macos_arm', language='java')` returns *"DYLD_LIBRARY_PATH must
be set at the shell level before any JVM or Python launch. Add to `~/.zshrc` to persist"*
(re-verified on MCP server 1.32.8, 2026-08-11), and the Windows guidance is equivalent. That is
correct advice for a human operator configuring their own machine, and forbidden here: the bootcamp
does not edit the Bootcamper's home directory on their behalf. When you relay this guidance, state
that the bootcamp writes the project-local script instead and that persisting it globally is their
choice to make later, by hand. This is the likeliest way INV-199 gets breached, which is why it is
called out at the step rather than left to the ground rules (INV-183).

<a id="env-script-path-resolution"></a>

**The env script MUST resolve its own path in the platform's *default* shell, not only in bash.**
This is the canonical statement of the rule; other modules link here rather than restating it.
Because the documented pattern is to **source** the script into the bootcamper's interactive shell
(see the same-shell requirement below), the shell it has to work in is whatever that bootcamper's
shell actually is — and on macOS that is **zsh**, not bash. `${BASH_SOURCE[0]}` — the idiom anyone
reaching for self-location writes first — is a bash array and expands to **empty** under zsh. The
script then resolves the project root to the wrong directory and keeps going, so the failure lands
later and somewhere else. Branch on the shell:

```bash
# --- resolve this script's own location (bash and zsh) ------------------------
# ${BASH_SOURCE[0]} is bash-only and expands to EMPTY under zsh, macOS's default
# shell, so branch rather than assume bash. bash parses the zsh-only expansion in
# the untaken branch without complaint.
if [ -n "${ZSH_VERSION:-}" ]; then
  _sz_self=${(%):-%x}                # zsh: this file's own path
else
  _sz_self=${BASH_SOURCE[0]:-$0}     # bash: this file's own path
fi
_sz_root=$(cd -- "$(dirname -- "$_sz_self")/../.." && pwd)

# --- fail loudly, naming the path that was computed --------------------------
if [ ! -f "$_sz_root/config/engine_config.json" ]; then
  printf 'senzing-env.sh: resolved project root has no config/engine_config.json\n' >&2
  printf 'senzing-env.sh:   resolved root: %s\n' "$_sz_root" >&2
  printf 'senzing-env.sh:   this is a path-resolution fault, not your Senzing install\n' >&2
  unset _sz_self _sz_root
  return 1 2>/dev/null || exit 1
fi

# --- never export an empty configuration ------------------------------------
_sz_settings=$(cat -- "$_sz_root/config/engine_config.json")
if [ -z "$_sz_settings" ]; then
  printf 'senzing-env.sh: %s is empty — refusing to export an empty configuration\n' \
    "$_sz_root/config/engine_config.json" >&2
  unset _sz_self _sz_root _sz_settings
  return 1 2>/dev/null || exit 1
fi

export SENZING_PROJECT_ROOT="$_sz_root"
export SENZING_ENGINE_CONFIGURATION_JSON="$_sz_settings"
# Platform-specific exports (SENZING_ROOT, DYLD_LIBRARY_PATH / LD_LIBRARY_PATH, jar
# paths) go here — take them from sdk_guide(topic='install', platform=…), never from
# memory or from this file (INV-080).
unset _sz_self _sz_root _sz_settings
```

Three things in that block are the point, not decoration:

- **`return 1`, never `exit 1`.** A sourced script shares the bootcamper's shell, so `exit` closes
  their terminal and `set -e` leaks into their session. `return 1 2>/dev/null || exit 1` returns when
  sourced and still exits if someone runs the file directly.
- **The guard names the path it computed.** A wrong root that exports nothing produces an error many
  steps later that reads as a Senzing fault; a guard that prints the resolved root is diagnosable on
  sight (the same fail-loudly rule INV-111 applies to generators).
- **Refuse to export an empty value rather than exporting one.** Senzing's own official code snippets
  guard initialization with `if (settings == null)` — they test for **unset**, not empty — so an
  `export SENZING_ENGINE_CONFIGURATION_JSON=""` sails straight past that check and fails later,
  deeper, and less legibly than no export at all. (Verified against the MCP server: `search_docs` returns
  `senzing/code-snippets-v4` `java/snippets/information/GetVersion.java` and the C# equivalents doing
  exactly this; MCP server 1.32.1, 2026-07-28.)

**Windows keeps its own script.** `senzing-env.bat` has no such problem — `%~dp0` is the batch file's
own directory and is always available — and none of the zsh material applies there. Add the same
fail-loudly root check to the `.bat`, and confirm the Windows variable set via `sdk_guide`.

### The launch environment (JVM languages, and macOS generally)

Installing the SDK is not the same as being able to **launch** against it. These are
launch-environment problems, **not** Senzing misconfigurations — say so when one appears, so the
bootcamper does not go hunting through their engine config for a fault that is not there. Each
presents as an error far from its cause.

⛔ **Confirm the specifics for the bootcamper's platform via
`sdk_guide(topic='install', platform='<platform>', language='<language>')` — from the server,
not from this file** (a sourcing floor) — the
library path, the jar path, and the platform gotchas come from MCP, never from memory or from this
file (INV-080). What follows is the shape of the problem, not a substitute for that lookup.

**macOS + a JVM language (a first-class combination here: `macos_arm` plus Java or C#).**

- **The native library is found through the shell environment, not a JVM flag.** Per the MCP
  install guidance for `macos_arm`, `DYLD_LIBRARY_PATH` must be set **at the shell level before the
  JVM starts**, and `-Djava.library.path` **alone is insufficient**. This is the opposite of the
  natural guess — that a JVM flag can fix a JVM library-path error — which is what makes it cost
  time. A process cannot repair its own dynamic-linker search path after it has started, so the
  variable has to be in the environment of the shell that launches `java`.
- **That is why `senzing-env.sh` must be sourced in the same shell that launches the JVM** — not
  merely created. Because the global shell config is off-limits (the rule above), a **project-local
  launcher script** that sources the env script and then executes `java` in one step is the reliable
  pattern: it keeps "set the environment" and "start the JVM" inseparable, which is precisely what
  the requirement demands. Generate one and use it for every subsequent JVM invocation.
- **Do not pass flags through an unquoted variable.** `java $SENZING_JAVA_OPTS` does not word-split
  in zsh (macOS's default shell), so multiple flags arrive as a single argument. Write the flags
  explicitly in the launcher script.
- **Classpath:** the MCP install guidance's example is
  `java -cp "${SENZING_ROOT}/sdk/java/sz-sdk.jar:<your classes>" MyApp`. Note the SDK **jar** lives
  under `sdk/java/`, while the **native** library lives under `lib/` — two different paths for two
  different things, and confusing them produces a class-not-found or a library-not-found error
  depending on which you get wrong. Confirm both paths via `sdk_guide`.
- **If you see `.dylib`/`.so` "not found" errors, do not symlink or copy Senzing libraries.** Per
  the MCP anti-patterns, Senzing tries both extensions and may report one even when the other works;
  the real cause is usually a missing dependency or an unset `DYLD_LIBRARY_PATH`. Re-run the
  `sdk_guide` install lookup and follow its gotchas for the installed version.

**MCP Java scaffolds may need a JSON library the install does not provide.** The authoritative Java
snippets from `generate_scaffold` (e.g. `loading/LoadWithInfoViaFutures.java`) `import javax.json.*`
and call `Json.createReader(...)` to parse records and `WITH_INFO` responses. `javax.json` (JSON-P)
is an external dependency: it is **not** part of the Java SE standard library, and the bootcamp
compiles with plain `javac` and never sets up Maven or Gradle. So:

1. **Verify before compiling, not after.** When a scaffold imports a package outside the standard
   library, check whether the environment actually provides it (inspect the install's jars) and
   resolve it *then* — rather than surfacing a raw `javac` import error the bootcamper has to
   diagnose. Verify per install; do not assume it is present or absent.
2. **State the safety asymmetry plainly when it comes up — this is the line that matters.**
   Replacing the **JSON library** is safe. Altering the **SDK calls** is not. Without that, a
   bootcamper facing an import error may "fix" it by rewriting the Senzing calls, which is exactly
   the failure `generate_scaffold` exists to prevent.
3. **Prefer a dependency-free JSON reader** for the bootcamp's own generated Java, so the code
   compiles under plain `javac`. Reuse one reader across modules rather than re-deriving it.
4. **Record the deviation in the source header** — what was substituted and why — so the take-home
   code shows where it departs from the authoritative scaffold. Never silently strip the import.

**`timeout` is not available on a stock macOS shell** (it is GNU coreutils; `gtimeout` exists only
if the user installed them). This is not Java-specific — it affects **any** command you wrap in a
timeout on macOS. Use a background process plus a polling loop with a deadline instead, or skip the
timeout. Check before relying on it rather than assuming a Linux userland.

**Other platforms.** On **Linux**, the equivalent variable is `LD_LIBRARY_PATH` and the same
"set it in the launching shell" rule applies — confirm the specifics via `sdk_guide`. On
**Windows**, the DYLD/LD variables do not apply at all and the env script is a `.bat`; the
classpath separator is `;`, not `:`. The zsh word-splitting caveat is macOS/zsh-specific and the
`timeout` caveat is macOS-specific — **neither applies on Linux**, where both behave as expected.
Non-JVM languages need none of the JVM-specific items above.

**Checkpoint:** write step 3 to `config/bootcamp_progress.json`.

## Step 4: Verify Installation

⛔ **This step verifies the BINDING, not the engine.** What it can prove here is that the language
binding loads, the native library is found, and the SDK answers: the factory constructs and
`SzProduct.get_version()` returns a version. **Do not create an engine at this step.** An
engine-class call needs an engine configuration (Step 8) and a datastore holding a registered
default config (Steps 7 and 8a) — three to four steps away — so a script that initializes the engine
here **cannot succeed even on a perfectly healthy, current install**.

This module already says so at its own success indicator: *"an engine-class call
(`SzEngine`/`SzDiagnostic`) succeeds — a version query alone does not qualify (**Step 9**)"*. That is
**Step 9**'s bar, after the database and the seeded config exist. Step 4 must not duplicate it early.

⚠️ **What it looks like when the engine is attempted here** (measured live on a healthy install,
Senzing 4.3.4 build 4.3.4.26210, 2026-08-14): `SzProduct.get_version()` returns `4.3.4` **and** the
engine call fails with

```text
SzBadInputError - SENZ7426|Transliteration failed: No transliteration rules found!
Transliteration requires at least one module.
```

⛔ **`SENZ7426` and `SENZ7220` before Step 7 mean "not configured yet" — they are the EXPECTED
result, not a defect.** Do **not** send them through this module's `explain_error_code` → pitfalls
path here. Both that tool and `sdk_guide(topic='install', platform='macos_arm' | 'windows')` document
a **real** `SENZ7426` cause — a wrong `SUPPORTPATH` on those platforms — and Step 8 covers it
properly, with its conditions and its provenance. That is the right diagnosis *after* the
configuration steps have run, and the wrong one here: at Step 4 there is no engine configuration yet
by design, so the same code means only that Steps 7–8a are still ahead. Reading it as a path fault
sends a bootcamper with a healthy install hunting something that does not exist. If you see either
code before Step 7, continue to Step 5.

So Step 4 needs **one** `generate_scaffold` call:

- `generate_scaffold(language='<chosen_language>', workflow='information', version='current')` —
  the **version-print** half, which is what this step runs. This is where the version snippet lives
  (for Python, `information/get_version.py`, which calls `SzProduct.get_version()`).

The `workflow='initialize'` call is still needed — at **Step 8a** (its `configuration/` snippets seed
the default config) and **Step 9** (its factory-lifecycle snippets make the engine call), which is
where both already cite it. Nothing is lost by dropping it here; it was simply four steps early. The
two-workflow fact below is why it cannot be the source for a version check, and it stays recorded at
this step because this is where a reader would otherwise reach for it.

⛔ **`workflow='initialize'` alone cannot satisfy a version check.** Verified live on server 1.32.9,
2026-08-12 (re-confirmed 2026-08-14), for **Python and Java**: its snippets are factory/engine **lifecycle** plus
configuration helpers — abstract-factory / environment variants, engine priming, repository purge,
factory destroy, signal handling, and the `configuration/` entries that seed a default config and
register data sources — and **none of them prints the version**. That **absence** is the
load-bearing fact. The version snippet lives only under `workflow='information'`
(for Python, `information/get_version.py`), re-confirmed on the same server and date.

⛔ **Do not restate this as a snippet count or a single directory.** The inventory varies on two
axes at once: it has **widened over time** (Python gained the `configuration/` entries between
1.32.2 and 1.32.9), and it **differs per language** in count and in path (on 1.32.9, Python returns
snippets under `python/initialization/` and `python/configuration/`, Java a smaller set under
`java/snippets/…`). A count is therefore wrong somewhere the moment it is written, while the
conclusion above stays true — which is exactly how a correct ⛔ comes to look discredited by its own
evidence. Citing it alone leaves
the guide to invent the missing half from memory, which is exactly the training-data fallback
INV-080 forbids. (Step 8a already carries this warning for a different need, and Step 9 cites
`workflow='initialize'` correctly for its own — the lesson generalizes: **check what a workflow's
snippets actually contain before citing it for a specific need.**)

⛔ **`generate_scaffold` returns a **listing**, not code — you must fetch each file.** Its response
carries `file_path`, `source_url`, `raw_url`, `size_bytes` and `line_count` per snippet and **no
source text**, so there is nothing to "save" until you fetch it: follow the response's own
`access_steps` step 1 and fetch each `raw_url`
(`raw.githubusercontent.com/senzing/code-snippets-v4/...`), or clone the repo per step 2 if the
fetch is blocked. This differs from `sdk_guide`, which does inline a `code.code` string — do not
carry that expectation across.

⛔ **Never pass `inline=true` to `generate_scaffold`.** Its own `access_steps` step 3 advertises
that parameter as a "last resort", but the tool's **declared schema has no `inline` parameter at
all** — only `language`, `version` and `workflow` (both confirmed live, server 1.32.9,
2026-08-13).
<!-- MCP-NEGATIVE: generate_scaffold's declared schema — carries no inline parameter, only language, version and workflow, while the response's own access_steps step 3 advertises the undeclared inline=true — owner: the tool's declared schema as the server advertises it is the authority on what it accepts, and it was read directly rather than inferred from the response prose (routing negative — the schema is the route, the prose is not) — server 1.32.9, 2026-08-13 --> Passing it is not a fallback, it is a call that cannot work, and it teaches nothing
about why. This is INV-160's rule applied to a sibling tool: **an undeclared parameter MUST NOT be
adopted as the remedy even when the response's own prose advertises one.** Fetch the `raw_url`
instead — that path is confirmed working.

If verification fails, use `explain_error_code` for any SENZ error codes and `search_docs` for
troubleshooting.

**Checkpoint:** write step 4 to `config/bootcamp_progress.json`.

## Step 5: License (built-in evaluation license active)

> **Internal note:** this step does NOT prompt for a License Key. The single, volume-gated
> Senzing License Key prompt is presented once, at the start of Data collection (Module 4),
> per INV-093. SDK setup only confirms that the built-in evaluation license is active; the
> "License Key" reference notes below are kept for context.

> **License check order:** project-local `licenses/g2.lic` → the `SENZING_LICENSE_FILE` path → system
> CONFIGPATH → the built-in evaluation license.
>
> <!-- MCP-NEGATIVE: search_docs and sdk_guide(topic='install'|'configure') — neither names a license environment variable; exactly one route returns it — owner: sdk_guide(topic='load', language='python', record_count=1000) compatibility_notes name it verbatim, "place the license file at the path specified by SENZING_LICENSE_FILE or in the etc/ directory", re-asked and confirmed (routing negative — the name exists, go there) — server 1.32.9, 2026-08-13 -->
> ⛔ **The license environment variable is `SENZING_LICENSE_FILE`, and only ONE tool route returns
> it — do not go looking for it anywhere else.** (INV-208) It appears in the `compatibility_notes` of
> `sdk_guide(topic='load', language=…, record_count=<above the default limit>)`, which says a
> bootcamper with a license should "place the license file at the path specified by
> `SENZING_LICENSE_FILE` or in the `etc/` directory". Verified on server **1.32.9, 2026-08-13**, for
> `language='python', record_count=1000` and `language='java', record_count=600` — the note is
> language-independent and appears only when the count exceeds the limit.
>
> ⛔ **`SENZING_LICENSE_PATH` is a confabulation — never use that spelling.** No tool returns it, and
> it shipped in graduation's `.env.example` for a time. Wrong environment-variable names are on the
> MCP server's own `common_confabulations` list, so the spelling matters more than it looks.
>
> ⚠️ **Do not conclude from the wrong route that the variable does not exist.** The topics you would
> naturally try return nothing: `sdk_guide(topic='configure', language='python',
> platform='linux_apt')` returns exactly two env vars (`LD_LIBRARY_PATH`, `PYTHONPATH`),
> `sdk_guide(topic='install', platform='macos_arm')` shows license only as the `PIPELINE` keys
> `LICENSEFILE`/`LICENSESTRINGBASE64`, and `search_docs` returns no variable name at all (all three
> re-checked on 1.32.9, 2026-08-13). An earlier pass took that silence as proof of absence and wrote
> "there is no license-path environment variable" into this note — the INV-194 failure mode: one
> tool's empty field is not evidence the server lacks the fact. Ask the tool that owns it.
>
> A `PIPELINE` license key remains the other supported route — `LICENSEFILE` for a `.lic` path,
> `LICENSESTRINGBASE64` for an inline Base64 key — which is what Module 4 Step 8a wires.
> The record capacity **is** looked up, not written here (INV-080) — see below.

> **"Senzing License Key" vs. the EULA:** the **Senzing License Key** configured in this step is a
> *runtime-capacity* license (it sets how many records Senzing will resolve) — supplied as a `.lic`
> file or a Base64-encoded key, or the built-in evaluation license by default. It is distinct from
> the **Senzing End User License Agreement (EULA)** accepted during SDK install in Step 3. When
> this step says "License Key", it means the runtime license, never the EULA.

### 5a. Confirm the built-in evaluation license (no prompt)

**Already-licensed guard (check first).** Read `config/bootcamp_progress.json`. If a
`license_record_limit` field is present, a custom license has already been configured (its limit
was detected earlier, this session or a prior one). Acknowledge it: present the detected
`recordLimit` as the authoritative limit ("Your license allows up to N records," or "Your license
has no record cap (unlimited)" when it is `0`), and skip the evaluation-license note below. Do not
re-ask (INV-006). Confirm any SDK facts against the Senzing MCP server rather than training data.

Otherwise (only the built-in evaluation license is active), present this briefly — as a statement,
**not a question:**

⛔ **Fill `{record limit}` below from the MCP server before presenting this — the figure is not
written into this skill on purpose.** The route that answers it is `sdk_guide` with a
`record_count` above the default limit, whose `compatibility_notes` name the limit outright:

```text
sdk_guide(topic='load', language='<chosen_language>', platform='<user_platform>', record_count=1000)
```

<!-- MCP-NEGATIVE: search_docs(query='evaluation license record limit how many records without a license') — returns no figure, only EULA grant-of-license and DSR-pricing prose ("solely for up to the number of DSRs designated therein") — owner: sdk_guide(topic='load', record_count=<above the limit>) compatibility_notes give the number, "exceeds the default Senzing license limit of 500", and explain_error_code('SENZ9000') calls it the default 500-DSR free tier; both re-asked today (routing negative — the figure exists, go there) — server 1.32.9, 2026-08-13 -->
`search_docs` does **not** answer this — asked for the evaluation license's record limit it returns
EULA and pricing prose with no figure (re-checked 2026-08-13), which is why the tool is named here
rather than left as "a Senzing MCP tool". Present exactly what the server returns (waiting up to 30
seconds). If it returns no figure, drop the parenthetical entirely and say the current limit is
unavailable from the MCP server. Never substitute a hardcoded or remembered figure — the published
capacity has changed before, and a stale number here is a Senzing fact asserted from memory
(INV-080), in the one place the bootcamper is most likely to plan against it.

"Your Senzing SDK uses a **built-in evaluation license** automatically when no custom license is
present (limited to {record limit} records) — no license file needed. That's enough for the demo
modules that come next (System verification and Truth Set visualization), which run on small
synthetic and Truth Set data. If your **own** data later exceeds the evaluation limit, we'll set up a
Senzing License Key in the Data collection module, where your data volume is known. Nothing to do
here."

> **Where the License Key is handled now:** the interactive License-Key setup (asking whether the
> bootcamper has a key, decoding/placing a `.lic` or Base64 key, wiring `LICENSEFILE`, requesting an
> evaluation license via the MCP server or Senzing support, and detecting the record limit) is the
> single, volume-gated gate at the start of Data collection (Module 4, Step 8a), per INV-093. SDK
> setup no longer performs it.

**Checkpoint:** write step 5 to `config/bootcamp_progress.json`.

## Step 6: Create Project Directory Structure

Create the organized project layout that all subsequent modules use, following the file
placement layout in `../bootcamp-onboarding/ground-rules.md` (`src/`, `src/../bootcamp-onboarding/scripts/`, `data/`,
`database/`, `docs/`, `config/`, `licenses/`, `src/resources/`, `data/mapping/`, `data/temp/`).
(The full Kiro agent-instructions directory-creation script is a later porting phase; create
the layout directly per the ground-rules placement rules for now.)

After creation, inform the user: "I've set up the project directory structure. All files will
be organized properly throughout the bootcamp."

**Checkpoint:** write step 6 to `config/bootcamp_progress.json`.

## Step 7: Configure Database

Ask: 👉 **Which database would you like to use? Reply with a number:**

1. **SQLite** — recommended for learning and evaluation.
2. **PostgreSQL** — better for production; can run in a Docker container (recommended when Docker is available), a local install, or an existing server.

*(Internal: end the turn on this question and wait.)*

**For SQLite** (recommended for bootcamp):

⛔ **SQLite is not "no setup". The database file is not auto-created and its schema is not
auto-applied** — the same as PostgreSQL, and for the same reason. Skipping the schema does not fail
here; it fails at Step 9 with `SENZ1001|Critical Database Error '(14:unable to open database file)'`,
which reads as a path or permissions fault. There are **three rungs**, and only the third is
Step 8a's:

1. **Create the database directory:** `mkdir -p database` (Linux/macOS) or
   `New-Item -ItemType Directory -Force -Path database` (PowerShell).
2. **Apply the Senzing schema** to `database/G2C.db`. Get the schema file's path from
   `sdk_guide(topic='install', platform='<platform>')` rather than hardcoding it (INV-080) — it is
   returned in `install.platform.post_install[]`, and `install.engine_config_notes[]` states the
   requirement in words: the DB file is **not** auto-created, and the schema step is **required**
   when using `senzingsdk-setup`, which is what this module installs. (Re-verified live, MCP server
   1.32.9, 2026-08-14. The `senzingsdk-poc` package's `sz_create_project` would do all three rungs
   automatically — that is not what the bootcamp installs.)

   ⛔ **Apply it with Python, not the `sqlite3` CLI.** Windows is a supported platform (INV-001) and
   ships no `sqlite3` binary; Python 3 is already a hard bootcamp prerequisite, and its stdlib
   `sqlite3` module runs the same DDL identically on all three platforms:

   ```bash
   python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.executescript(open(sys.argv[2]).read()); c.commit(); c.close()" \
     database/G2C.db "<schema path from sdk_guide>"
   ```

   The server returns the CLI form (`sqlite3 <db> < <schema>.sql`) — treat that as the illustration
   of *what* to apply, not as the command to run.
3. **Seed the Senzing configuration** — that is Step 8a, below. Do not attempt it here.

⛔ **The `SQL.CONNECTION` path must be ABSOLUTE.** Written relative, the engine cannot open the
database **from any working directory, including the project root** — it fails with the same
`SENZ1001 (14: unable to open database file)`, so this is not something a `cd` fixes. The reason is
visible in the engine's own SQLite log: given `sqlite3://na:na@database/G2C.db` it tries to open
**`/G2C.db`** — the relative prefix is not resolved against the working directory, it is discarded
(observed on Senzing 4.3.4, 2026-08-14). Use the
absolute resolution of the project's `database/G2C.db`, with the `/` immediately after `@`:

```text
sqlite3://na:na@/absolute/path/to/<project>/database/G2C.db
```

This is INV-200-compatible, not in tension with it: the file still lives **inside the project** at
`database/G2C.db`; it is the connection *string* that carries that path's absolute form.

- **IMPORTANT:** Never use `/tmp/` or in-memory databases. If `generate_scaffold`,
  `ExampleEnvironment` or `sdk_guide` defaults to `/tmp/` (the server's own example path is
  `/tmp/sqlite/G2C.db`), override the path to `database/G2C.db` — **including in the schema command
  above**, not only in the connection string.

**How to tell where you are:** after rung 2, `create_engine()` still fails — with
`SENZ7220|No engine configuration registered in datastore`. That is the expected state and exactly
what Step 8a closes. `SENZ1001 (14: unable to open database file)` means rung 2 has **not** been
done; do not diagnose it as a permissions or path problem.

**For PostgreSQL** (production): first choose HOW to run it. Detect Docker availability
(`docker version`); when Docker is present, offer the container option **first and recommended** —
a real, production-style PostgreSQL with no system-wide install or admin rights, easy to tear down.
Pin this 👉 question verbatim (neutral lead + numbered list, INV-051/INV-056):

👉 **How would you like to run PostgreSQL? Reply with a number:**

1. **In a Docker container** — recommended when Docker is available; self-contained and production-style.
2. **Install PostgreSQL locally.**
3. **Use an existing PostgreSQL server.**
4. **Switch to SQLite** (the bootcamp default).

*(Internal: end the turn on this question and wait.)* When Docker is not available, omit option 1
and say so.

**MCP-first (INV-080):** confirm the current PostgreSQL connection-URL format, the schema-DDL path,
and the engine-config wiring from the Senzing MCP server at runtime — do not treat the values below
as authoritative. Use `search_docs(query='Senzing engine configuration PostgreSQL connection')` and
`search_docs(query='PostgreSQL schema DDL initialization', category='anti_patterns')`, and generate
the engine config with `sdk_guide(topic='configure', ...)` — never hand-construct
`SENZING_ENGINE_CONFIGURATION_JSON`.

**Option 1 — PostgreSQL in a Docker container:**

1. Generate a strong, project-specific database password **once** — it is baked into the
   project-local volume on first initialization, so reuse the same value everywhere below and
   never regenerate it on a later restart:

   ```bash
   python3 -c "import secrets; print(secrets.token_hex(16))"
   ```

   Then run an official `postgres` image with a stable `--name`, a **project-local volume** (data
   persists in the working directory, not an ephemeral layer), the generated password (never the
   guessable default `senzing`), and the port **bound to localhost only** (`127.0.0.1:`, so the
   database is not exposed on other network interfaces):

   ```bash
   docker run -d --name bootcamp-postgres \
     -e POSTGRES_USER=senzing -e POSTGRES_PASSWORD=<generated-password> -e POSTGRES_DB=G2 \
     -p 127.0.0.1:5432:5432 -v "$(pwd)/database/postgres:/var/lib/postgresql/data" postgres:16
   ```

   On a later resume, restart the existing container with `docker start bootcamp-postgres` (which
   preserves the baked-in password) rather than a fresh `docker run`.

2. Record the container for lifecycle tracking (INV-101): append it to `docker_containers` in
   `config/bootcamp_progress.json` — at least its `name` and the `runtime` you actually used
   (`docker`, or `podman` / `container` if that is what started it) — so the SessionEnd hook
   stops it on exit and SessionStart offers to restart it.
3. Wait until the server is ready (poll `docker exec bootcamp-postgres pg_isready`).
4. Apply the Senzing PostgreSQL schema DDL **before any SDK use** — the SDK does NOT auto-create it
   (unlike SQLite). MCP confirms the DDL ships with the SDK install at
   `/opt/senzing/er/resources/schema/szcore-schema-postgresql-create.sql`; apply it against the
   container:

   ```bash
   docker exec -i bootcamp-postgres psql -U senzing -d G2 \
     < /opt/senzing/er/resources/schema/szcore-schema-postgresql-create.sql
   ```

   Re-confirm the exact path via MCP; the Windows/macOS SDK install path differs (see the
   initialization anti-patterns doc).
5. Wire the connection into the engine config (Step 8): the `SQL.CONNECTION` URL is
   `postgresql://user:password@host:port/database` (MCP-confirmed), where `password` is the
   generated value from Step 1 (not the old `senzing` default). Generate the full engine config
   via `sdk_guide(topic='configure', ...)` and save it to `config/engine_config.json`.

**Option 2 — Install PostgreSQL locally:** install and start a local PostgreSQL server, create the
Senzing database, apply the schema DDL as above (`psql -f .../szcore-schema-postgresql-create.sql`),
then wire the `postgresql://` connection via `sdk_guide(topic='configure', ...)`.

**Option 3 — Use an existing PostgreSQL server:** obtain the host/port/database/credentials, apply
the schema DDL to that database, and wire the `postgresql://` connection as above. Managed cloud
PostgreSQL typically requires SSL (`PGSSLMODE=require`) — confirm via MCP.

**Option 4 — Switch to SQLite:** proceed with the SQLite setup above.

SQLite remains the default recommendation for pure evaluation; PostgreSQL (especially via Docker)
is the production-style path. INV-037 is satisfied by any of these paths.

⛔ **Record the choice where later modules read it.** Whichever option was taken, write the engine
to `config/bootcamp_preferences.yaml` under the key **`database_type`**, with the value
**`sqlite`** or **`postgresql`** (lowercase, exactly these two spellings):

```yaml
database_type: sqlite   # or: postgresql
```

This is the **only** step in the bootcamp that knows which engine was chosen, and two later steps
depend on the answer: Module 4 Step 8b's SQLite load-time warning and Module 6's
`phaseA-build-loading.md` heads-up both read `database_type` from that file by name. Without this
write, both reads find nothing, both fall through their "indeterminate → say nothing" branches, and
neither warning can **ever** fire — regardless of the database chosen or the dataset size. Do not
record it only in `config/bootcamp_progress.json`: nothing reads it from there, and a different key
name is the same failure as no key at all.

**Checkpoint:** write step 7 to `config/bootcamp_progress.json`.

## Step 8: Create Engine Configuration

**🚨 NEVER guess the engine-configuration VALUES.** `CONFIGPATH`, `RESOURCEPATH`, `SUPPORTPATH` and
the connection-string form all come from
`sdk_guide(topic='configure', platform='<user_platform>', language='<chosen_language>', version='current')`
— never from directory patterns or memory (INV-080). The correct paths vary by platform and
installation method, and guessing causes engine
initialization failures (e.g., SENZ2027 when SUPPORTPATH is wrong).

⛔ **`platform` is not optional here, even though the schema says it is.** `sdk_guide` declares
`platform` with `"default": null` ("Omit to get the platform decision tree"), so a call without it
**succeeds** — and returns no `environment` block at all: no `engine_config`, and no
`default_paths` either. Every value this step needs lives in that block, so the omission does not
raise an error, it just leaves you with the bootstrap code and nothing to configure. Pass the
bootcamper's platform. If the response has no `environment` key, that is what happened — re-issue
the call with `platform` rather than reconstructing the paths by hand.

MCP-NEGATIVE: sdk_guide(topic='configure', language='python') — returns no `environment` block, so neither `engine_config` nor `default_paths` — owner: sdk_guide(topic='configure', platform='linux_apt', language='python') IS the route that carries it and returned `environment.default_paths` plus `environment.engine_config` when asked (routing negative) — server 1.32.9, 2026-08-15

**Build the JSON from `environment.default_paths`, not from the `engine_config` blob.** That response
carries both — **provided `platform` was passed** (above). `default_paths` gives plain, correct
strings — `config_path`, `support_path`, `resource_path` — and assembling the document from them
yields valid JSON on the first try.

⛔ **The response's `engine_config` field must NOT be written to disk as-is. It needs two corrections,
not one:**

1. **It is not valid JSON.** Every brace in it is doubled (`{{` … `}}`), which is `str.format`'s
   escape for a literal brace — the server appears to return the template rather than the rendered
   result. `json.loads` on it raises `JSONDecodeError: Expecting property name enclosed in double
   quotes: line 1 column 2`. Observed on **MCP server 1.32.9, 2026-08-14** (both `topic='configure'`
   and `topic='install'` return the same doubled form), so a future reader can check whether it is
   still true. If it has been fixed upstream, the `default_paths` route above is still the more
   robust source and needs no change.
2. **Its `SQL.CONNECTION` is `/tmp/sqlite/G2C.db`**, which INV-200 forbids — override it to the
   absolute resolution of the project's `database/G2C.db` (see Step 7's SQLite branch).

⚠️ Fixing those two things is **not** the manual construction the 🚨 forbids. What is forbidden is
inventing the *values*; deriving the document from the values the server returned is exactly what
this step asks for. The distinction matters because the old wording ("use the exact JSON") could not
be obeyed at all: pasting it produced a config the SDK cannot parse, and repairing it looked like a
violation of the same sentence.

**What `SENZ2027` is actually telling you: the support data is not where the configuration points.**
Call `explain_error_code('SENZ2027')` first as always (INV-080) — it returns
`EAS_ERR_PLUGIN_INIT: Plugin initialization error`. The actionable detail is in the Senzing FAQ
(`search_docs`, verified 2026-07-30 on MCP server 1.32.2):

> **I get SENZ2027 Plugin initialization error GNR data files failed to load** — You are missing the
> senzingsdk-runtime data directory. The libraries are present but the GNR data files (in
> `resources/data/`) are not deployed.

So the code means *the libraries loaded and their data did not* — which is exactly what a wrong
SUPPORTPATH produces, and on Windows/Scoop exactly the sibling-directory case the `Test-Path` check
below fixes. Look for a misplaced data directory, not for a broken install.

⚠️ **Because those two can be present independently, a version query does not validate the engine.**
An `SzProduct` call can answer while the support data is absent, so "the SDK imports and reports its
version" is not evidence that an engine can initialize — see Step 9, which requires an engine-class
call for exactly this reason.

> **This masking is now MCP-confirmed on two platforms, and it has a concrete failure code.**
> `sdk_guide(topic='install', platform='windows')` states that building `SUPPORTPATH` as
> `%SENZING_DIR%\data` — which on Scoop resolves to a directory that does not exist — makes
> "every SzEngine/SzDiagnostic call … fail with `SENZ7426 EAS_ERR_XLITERATOR_FAILED` ('No
> transliteration rules found! Transliteration requires at least one module') **while SzProduct
> keeps working — so the install looks healthy**" (verified on MCP server 1.32.2, 2026-07-30).
>
> **The macOS cask has the same defect, and the server documents it in more detail.**
> `sdk_guide(topic='install', platform='macos_arm')` states that `SENZ7426` on
> `getEngine`/`getDiagnostic`/`addRecord` "means SUPPORTPATH is WRONG — it is NOT a broken
> install": the cask's own shipped `etc/sz_engine_config.ini` sets
> `SUPPORTPATH=${INSTALLPATH}/senzing/er/data`, **a directory that does not exist**, while the real
> support data (`address_datamodel`, `nomicon`, and the `*TransRules.sz` transliteration modules)
> lives one level up at `$(brew --prefix)/opt/senzing/data`. The server reports this confirmed
> end-to-end on cask 4.4.0.26206 and **reported against 4.3.3.26191, which ships the same wrong
> path** (verified on MCP server 1.32.3, 2026-07-31).
>
> ⛔ **Both tools state this now, and they agree** — re-verified on **MCP server 1.32.9,
> 2026-08-12**. `sdk_guide(topic='install', platform='macos_arm', language='java')` carries the
> gotcha above verbatim, and `explain_error_code('7426')` ranks *"SUPPORTPATH points at a directory
> with no transliteration modules … This is a configuration error, NOT a broken install"* as
> `common_causes[0]` with *"Check SUPPORTPATH FIRST"* as `resolution_steps[0]`, naming this same
> macOS cask case and pointing back at `sdk_guide topic='install'` for the platform detail. So relay
> either one. Keep `sdk_guide` cited for what it still owns — the paths, env vars and EULA variable
> — and note that the principle the earlier note rested on is unchanged: **ask the tool that owns
> the fact.** Only its example is obsolete, because these two coverages have since converged.
>
> ⚠️ `sdk_guide` gates this response on `language`: asked with `language='python'` for this platform
> it returns only the "Python is Linux-only" compatibility note and **no install detail at all**, so
> the gotcha above is invisible. Ask with a macOS-supported binding (Java or C#) to see it.
> (Observed 1.32.9, 2026-08-12.)
> <!-- MCP-NEGATIVE: sdk_guide(topic='install', platform='macos_arm', language='python') — returns no install detail, only the Linux-only note — owner: sdk_guide(topic='install', platform='macos_arm', language='python') compatibility_notes state the Python SDK is Linux-only — the absence IS the answer, not a gap — server 1.32.9, 2026-08-13 -->
>
> `SENZ7426` still fires at `getEngine()`, **before any record is submitted**, so "validate your
> input data" would send the reader to inspect something that does not yet exist — which is exactly
> why `explain_error_code` now ranks that cause last and conditions it on the engine having
> initialized successfully.

Use `sdk_guide` with `topic='configure'` to generate the correct engine configuration JSON for
the user's platform and database choice. Save the MCP-returned JSON directly to
`config/engine_config.json`; do not modify the paths.

**On Windows, verify SUPPORTPATH exists before saving the configuration:**

After receiving the MCP-returned JSON, check that the SUPPORTPATH directory actually exists on
the filesystem. This is a targeted path verification, not manual JSON construction: the
MCP-returned JSON remains the starting point.

1. Extract the SUPPORTPATH value from the MCP-returned configuration JSON.
2. Use `Test-Path` in PowerShell to confirm the SUPPORTPATH directory exists:

   ```powershell
   Test-Path -Path "$SENZING_DIR\data"
   ```

3. If `$SENZING_DIR\data` does not exist, check `$SENZING_DIR\..\data` (one level up from the
   `er` directory):

   ```powershell
   Test-Path -Path "$SENZING_DIR\..\data"
   ```

4. If the parent-level path exists, update SUPPORTPATH in the configuration JSON to use
   `$SENZING_DIR\..\data` before saving to `config/engine_config.json`.
5. If neither path exists, report the error clearly: "SUPPORTPATH directory not found at either
   `$SENZING_DIR\data` or `$SENZING_DIR\..\data`. Please verify your Senzing installation."

> **Why the Scoop layout differs:** The Windows Scoop package — Senzing's own bucket,
> `github.com/Senzing/scoop-senzingsdk`, which `sdk_guide(topic='install', platform='windows')`
> calls "the official Senzing Scoop bucket" (verified on MCP server 1.32.2, 2026-07-30) — places
> `SENZING_DIR`
> at the `er` subdirectory within the Scoop app folder (e.g.,
> `C:\Users\<user>\scoop\apps\senzing\current\er`). The `data` directory containing
> `g2SifterRules.ibm` and other GNR support files is at the Scoop app version root, one level
> above `er`, rather than inside it. This is why the fallback to `$SENZING_DIR\..\data` is
> needed for Scoop installs.

**This verification is about a *layout*, not a platform — run it wherever the support data can be a
sibling of `er` rather than a child.** That is currently **two** platforms, both documented by
`sdk_guide`: Windows/Scoop (above) and macOS/Homebrew.

**On macOS, the same check with the Homebrew paths:**

1. Confirm the `SUPPORTPATH` in the MCP-returned configuration exists —
   `test -d "$(brew --prefix)/opt/senzing/data"`, and that it holds the transliteration modules:
   `ls "$(brew --prefix)/opt/senzing/data"/*TransRules.sz`.
2. If it does not, the cask's own `etc/sz_engine_config.ini` is the likely source: it sets
   `SUPPORTPATH` to `${INSTALLPATH}/senzing/er/data`, which does not exist. **Do not use the shipped
   `.ini` as-is, and do not copy transliteration files around** — set `SUPPORTPATH` to
   `$(brew --prefix)/opt/senzing/data`, the `support_path` `sdk_guide` already returns.
3. If neither path exists, report both that were tried rather than guessing a third.

⚠️ **Linux was not re-checked for this layout** (verified 2026-07-31: `sdk_guide` was asked for
`macos_arm` and `windows` only). Use the MCP-returned paths on Linux without modification, and if a
Linux install ever produces `SENZ7426`, ask `sdk_guide(topic='install', platform='linux_apt' |
'linux_yum')` before assuming this case applies — do not widen it by inference.

**Checkpoint:** write step 8 to `config/bootcamp_progress.json`.

## Step 8a: Seed the default configuration (a freshly created datastore has none)

⛔ **A datastore you just schema-created has NO registered Senzing configuration, and the
data-source registration snippet assumes one exists.** Do this before Step 9 and before any
data-source registration.

⚠️ **"Schema-created" is true of BOTH database branches.** PostgreSQL applies
`szcore-schema-postgresql-create.sql` in Step 7; SQLite applies
`szcore-schema-sqlite-create.sql` there too (rung 2 of its three rungs). If you arrived here on the
SQLite branch without having applied the schema, this step cannot help — go back and apply it, or
`create_engine()` fails with `SENZ1001 (14: unable to open database file)` rather than the
`SENZ7220`/`SENZ7221` this step exists to fix.

`sdk_guide(topic='configure')`'s primary `RegisterDataSources` snippet opens by reading the default
config id and building a config **from** it. On an unseeded datastore there is nothing to read, and
the attempt fails with

```text
SENZ7221 EAS_ERR_NO_CONFIG_REGISTERED_FOR_DATA_ID
```

**The error now names its own remedy — call it and follow it.** `explain_error_code('SENZ7221')`
returns as its first cause *"No default config has EVER been registered on this datastore — it was
schema-created (e.g. via `szcore-schema-*-create.sql`) but never seeded"*, and as its first
resolution step *"Seed a default config first: `create_config_from_template()` (or
`create_config()`), then `set_default_config(config_json, comment)` — see `sdk_guide`
topic='configure'"* — which is exactly Step 8a below (verified on MCP server 1.32.2, 2026-07-30;
through 1.32.1 the entry was generic and this note warned you to disregard it). It also names two
further causes worth knowing: calling `create_config_from_config_id(0)` on the unseeded value, and
an engine pointed at a different datastore than the one you seeded. Seed first and it never arises.

**How to seed — take the code from MCP, do not hand-write it (INV-080):**

⛔ **`data_sources` is the switch that decides which snippet you get.** `sdk_guide(topic='configure')`
returns **one** primary `code` block, and which one depends on whether you passed `data_sources` —
the other becomes an entry in `alternatives`. Getting this backwards is why the seeding step is easy
to misread: you ask one way and look for the answer in the place the *other* call puts it. Verified
on MCP server 1.32.8, 2026-08-11, calling both ways in `language='python'`:

| Call | Primary `code.source_path` | In `alternatives` |
|---|---|---|
| `sdk_guide(topic='configure', language=…)` — **no** `data_sources` | `python/configuration/init_default_config.py` | `register_data_sources` |
| `sdk_guide(topic='configure', language=…, data_sources=[…])` | `python/configuration/register_data_sources.py` | `init_default_config` |

1. **Seed:** call `sdk_guide(topic='configure', language='<chosen_language>')` **without
   `data_sources`**. The **primary `code` block** is the seeding snippet — confirm
   `code.source_path` ends `configuration/init_default_config.py`. Its sequence: read the default
   config id → `create_config_from_template()` → `set_default_config(...)`, which registers the new
   config and makes it default.
2. **Register:** call it again **with** `data_sources=[…]`. Now the primary `code` block is the
   registration snippet (`configuration/register_data_sources.py`), and it has a config to build
   from.

⛔ **Locate the snippet by its `source_path`, never by its position in the response.** Both snippets
are always present; only which one is "primary" moves. A step that says "take the alternative" breaks
the moment the call's arguments change — which is exactly how this instruction went stale once
already.

**The tool now states this precondition itself — relay it rather than asserting it.** The
`data_sources` call carries a `compatibility_notes` entry (same verification, 1.32.8, 2026-08-11):

> "PRECONDITION: this snippet reads the CURRENT default config (`get_default_config_id()` ->
> `create_config_from_config_id()`) and replaces it — it assumes a default config is ALREADY
> registered. On a freshly schema-created datastore, `get_default_config_id()` returns 0 and
> `create_config_from_config_id(0)` raises SENZ7221 … call `sdk_guide(topic='configure', …)` WITHOUT
> `data_sources` first — that returns the `init_default_config` snippet"

Read `compatibility_notes` on each call and follow what it says; it is the authority on ordering here,
not this file. The seeding call's own note adds the step after: `env.reinitialize(config_id)` must
follow `set_default_config()` before loading records, using the id `set_default_config()` returned.

`generate_scaffold(language='<chosen_language>', workflow='initialize')` reaches the same code by
another route: alongside the factory-lifecycle snippets it returns the `configuration/` ones — for
Python, `init_default_config.py`, `register_data_sources.py`, `get_config_registry.py`,
`get_data_source_registry.py` (re-verified 1.32.9, 2026-08-12). The set is
**language-dependent** — Java returns `InitDefaultConfig.java` and `RegisterDataSources.java` and
not the two registry readers (same server and date) — so read what your language's response
actually lists rather than expecting these four. Either route is fine; `sdk_guide` is
preferred here because it also carries the `compatibility_notes` above, which `generate_scaffold`
does not. Step 9's connection test uses the factory-lifecycle snippets from the same response.

**Verify the seed before moving on:** confirm a default config id is now present. If it is not, stop
here and report it — a missing config surfaces at this step as one clear failure, or later as
`SENZ7221` several steps from its cause.

**Checkpoint:** write step 8a to `config/bootcamp_progress.json`.

## Step 9: Test Database Connection

Use `generate_scaffold(language='<chosen_language>', workflow='initialize', version='current')`
to get the current V4 initialization and connection test pattern, then use that MCP-generated
initialization code to verify the database connection works.

⛔ **The check MUST create and use an `SzEngine` (or `SzDiagnostic`) — not only `SzProduct`.** A
version query proves the library loaded; it does not prove the engine can initialize, because the
libraries and their support data can be present independently (see the `SENZ2027` note in Step 8).
So a configuration whose SUPPORTPATH is wrong can satisfy a version probe and fail at the first real
engine call, several steps later, where the cause is no longer obvious. Exercising an engine class
here is what moves that failure back to the step designed to catch it.

This constrains **which class the generated check touches**, not where the code comes from: keep
using `generate_scaffold(workflow='initialize')` and pick the snippet that creates an engine
(INV-080). Do not hand-write it.

Never generate direct SQL against `database/G2C.db`; all access goes through Senzing SDK
methods (per ground-rules).

**Checkpoint:** write step 9 to `config/bootcamp_progress.json`.

**Success indicator:** ✅ SDK installed + DB configured + test passes + **an `SzEngine`/`SzDiagnostic`
call succeeds** (not merely a version query).

## Success Criteria

- ✅ Senzing SDK installed natively.
- ✅ SDK imports/references work in the chosen language.
- ✅ Engine initializes without errors, proven by an `SzEngine`/`SzDiagnostic` call rather than a version query (Step 9).
- ✅ Database connection works.
- ✅ Project directory structure created.

## Agent Behavior

- Always check for an existing installation first: if the SDK is present and V4.0+, do NOT
  reinstall. Skip to verification.
- Do NOT offer alternatives: install the SDK natively (or via Docker where the routing rules
  require it).
- Use the `sdk_guide` MCP tool for current platform-specific instructions.
- Use `search_docs` with `category='anti_patterns'` before recommending approaches.
- **NEVER guess engine configuration values:** take `CONFIGPATH`, `RESOURCEPATH`, `SUPPORTPATH` and
  the connection-string form from
  `sdk_guide(topic='configure', platform='<user_platform>', language='<chosen_language>')`, and build
  the document from that response's `environment.default_paths` — **not** by pasting its
  `engine_config` field, whose braces are doubled and which does not parse (Step 8 states both
  corrections it needs, and its failure modes). Do not guess the paths
  (INV-080: config options come from the MCP tools, never from speculation). ⛔ **`platform` is not
  optional here** — Step 8 states this rule and what a platform-less response looks like, at the
  step that makes the call (INV-183).
- Recommend SQLite for evaluation, PostgreSQL for production.
- Always use `database/G2C.db` for SQLite (never `/tmp/sqlite`).
- Verify installation before proceeding to the next module.

## Troubleshooting

- Installation fails? Use `explain_error_code` for SENZ errors.
<!-- MCP-NEGATIVE-SCAN: not-a-tool-claim — "the datastore has no default configuration" is a fact
     about the Bootcamper's environment, not about an MCP tool's content, so it needs no marker. The
     tool claims in this bullet are POSITIVE (explain_error_code returns the cause and the seeding
     sequence) and are cited inline. Triaged 2026-08-13 from `coverage_reports.py unmarked`. -->
- **`SENZ7221 EAS_ERR_NO_CONFIG_REGISTERED_FOR_DATA_ID`? The datastore has no default configuration —
  seed one per Step 8a.** Call `explain_error_code('SENZ7221')` first as always (INV-080) and
  **follow what it returns**: its first cause is the never-seeded datastore and its first resolution
  step is the seeding sequence, the same one Step 8a takes from `sdk_guide(topic='configure')`
  (verified on MCP server 1.32.2, 2026-07-30). Its third step — check that
  `SENZING_ENGINE_CONFIGURATION_JSON`'s `SQL.CONNECTION` points at the datastore you actually seeded
  — is a real second possibility, not a distraction. This is the expected symptom on a freshly
  schema-created datastore whose config was never seeded, and it can appear several steps after the
  omission.
- **`Unable to get settings`, or an empty `SENZING_ENGINE_CONFIGURATION_JSON`? This is the env
  script's path resolution, not Senzing.** That message carries **no SENZ code** because it is not an
  engine error: it is the null-check in Senzing's own official snippets, which print
  `Unable to get settings.` and throw `IllegalArgumentException` / `ArgumentException` when
  `SENZING_ENGINE_CONFIGURATION_JSON` is unset. So do not send it through `explain_error_code` — there
  is no code to explain, and hunting through the engine config wastes the time. **First check whether
  the script exists at all** — on the existing-install path it is the artifact most likely to be
  missing, and asking whether an absent file was sourced sends the reader looking for the wrong
  fault. If `src/../bootcamp-onboarding/scripts/senzing-env.sh` (or `senzing-env.bat`) is not there, that **is** the
  finding: write it now per Step 3's environment-script work, with the values from
  `sdk_guide(topic='install', platform=…, language=…)`. Only if it does exist, check that it was
  **sourced** (not executed) in this shell, and that it resolved its own path
  under the shell in use — see [the env script's path resolution](#env-script-path-resolution). Under
  zsh, a `${BASH_SOURCE[0]}`-based script computes the wrong root and exports nothing.
  (Snippet guard verified via `search_docs`; MCP server 1.32.1, 2026-07-28.)
- Platform not supported? Use `search_docs` for alternative installation methods.
- Database errors? Confirm path requirements against the file placement rules in ground-rules
  (the Kiro `FILE_STORAGE_POLICY.md` reference is a later porting phase).
- Permission issues? Ensure you have admin/sudo access for installation.
- Missing dependencies? A Kiro preflight script (`preflight.py`) is a later porting phase; for
  now, verify prerequisites directly and use `search_docs` for platform requirements.

## Module completion and transition

Once the SDK is installed and verified, run the standard **Module Completion** process in
`../bootcamp-onboarding/module-completion.md` (update progress, append the Module 2 recap section
to `docs/bootcamp_recap.md`, and present the end-of-module summary), then ask the single
transition question.

The next module in your selected sequence continues the bootcamp — when it is System verification, it verifies the full setup end-to-end with synthetic records; the separate Truth Set visualization module, when selected, then visualizes the Senzing Truth Set:

👉 **Are you ready to move on to the next module: {next module name}?**

*(Internal: end the turn on this question and wait.)* On module completion set `current_step` to
`null`.
