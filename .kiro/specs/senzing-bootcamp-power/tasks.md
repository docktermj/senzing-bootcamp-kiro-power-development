# Implementation Plan: Senzing Bootcamp Power

## Overview

Two artifacts are built in one greenfield repository:

- **Artifact B (built by hand)** — the deterministic transformation pipeline at `tools/bootcamp-transform/` plus the maintainer skills at `powers/senzing-bootcamp-maintainer/`.
- **Artifact A (generated output)** — `powers/senzing-bootcamp/`, produced by *running* Artifact B against Template_Release `0.5.1` and committed as the deliverable.

Because Artifact A is generated, the plan builds the engine first, then runs it. The engine is assembled in dependency order — `Version_Resolver` → `Transformation_Contract` → transform engine → `Schema_Validator` → `Reconciler` — with each stage independently runnable and property-tested before the next stage depends on it. The maintainer skills that orchestrate the engine are authored only after the engine and the contract exist, and each validator check lands before the task that relies on it to gate. Hand-authored `kiro-owned` content (command-derived skills, the enforcement-setup skill, Kiro hook JSON) is authored under `tools/bootcamp-transform/templates/kiro-owned/`, because the design materializes `kiro-owned` rules from `templates/` on the create path and from `--carry-forward` on the update path.

**Language and stack:** Python 3 (matches the ported template scripts). Tests use pytest with [Hypothesis](https://hypothesis.readthedocs.io/) for property-based tests, minimum 100 examples per property.

**Hook command rule — non-negotiable, applies to every task that touches a hook definition.** `INV-052` is **honored, not discounted**: it states a portability guarantee (hook execution carries no shell dependency on Linux, macOS, or Windows), and that guarantee is preserved in Kiro's mechanisms. Kiro's hook schema accepts a single `command` string with no `args` array, so every `Hook_Command_String`:

- names a **quoted absolute interpreter path** resolved at install time from `sys.executable` — never a bare `python3`, `python`, or `py`;
- quotes the absolute script path as well, so a path containing a space is one argument;
- contains **no** command-chaining operator (`&&`, `||`, `;`), pipe, redirection (`>`, `<`, `>>`), or shell builtin invocation;
- carries only the `<ABSOLUTE_PYTHON>` and `<ABSOLUTE_SCRIPTS_DIR>` placeholders in shipped assets, resolved by the `Hook_Installer`.

The `Invariant_Discount_Register` in `contract.yaml` therefore contains **no `INV-052` entry**; an entry appearing there is the validator error `E_HONORED_INVARIANT_DISCOUNTED`.

**Property test conventions** (from design Testing Strategy):
- One property, one test. All **25** correctness properties implemented.
- All property tests live in the single file `tools/bootcamp-transform/tests/test_properties.py`.
- Every property test carries the design's tagging comment, `# Feature: senzing-bootcamp-power, Property N: <title>`, wrapped across lines as needed.
- Every property test carries `@settings(max_examples=100)` or higher.
- Because all 25 tests share one file, the dependency graph places every property task in its own wave.

## Tasks

- [x] 1. Project scaffolding and repository-level cross-platform artifacts

  - [x] 1.1 Create Python project scaffolding and a runnable test command
    - Create `pyproject.toml` at the repo root declaring the project and pinned dev dependencies: `pytest`, `hypothesis`, `pyyaml`, `jsonschema`, `jinja2`
    - Create `tools/bootcamp-transform/`, `tools/bootcamp-transform/tests/`, `tools/bootcamp-transform/templates/`, `tools/bootcamp-transform/templates/kiro-owned/`, `docs/`, `docs/test-records/`
    - Configure pytest (testpaths, single-run invocation `pytest --no-header -q`), and register a `hypothesis` profile with `max_examples=100` as the floor
    - Add a placeholder smoke test so the runner is verifiably green before any component exists
    - _Requirements: 14.2_

  - [x] 1.2 Commit the repository `.gitattributes` line-ending declaration
    - Author `.gitattributes` at the repository root with `* text=auto eol=lf`, `*.png binary`, and `*.min.js -text`
    - LF must survive checkout on every Supported_Platform, so a Windows checkout cannot rewrite bytes and invalidate `Build_Manifest` hashes
    - Binary and minified assets are excluded from normalization because the transform must keep them byte-for-byte identical to the template source
    - This is a committed repository artifact, not generated output — the contract references it rather than emitting it
    - _Requirements: 16.8_

  - [x] 1.3 Author the shared Hypothesis strategies in `tools/bootcamp-transform/tests/strategies.py`
    - Implement all 13 generators named in the design with their listed edge cases: `release_list()`, `template_tree()`, `skill_tree()`, `frontmatter()`, `file_content()`, `mcp_document()`, `statement()`, `failure_point()`, `reconcile_triple()`, `outcome_set()`, `interpreter_path()`, `discount_register()`, `inv_prose()`
    - `release_list()` must emit empty lists, all-draft, all-prerelease, `0.10.0` vs `0.9.0`, duplicate tags, and `0.5.1` vs `0.05.1`
    - `template_tree()` must emit novel unmatched paths, nested `scripts/vendor/`, binary assets, empty files, unicode filenames, `..` segments, absolute-looking paths, and symlinks
    - `frontmatter()` must emit missing keys, empty strings, whitespace-only values, >1024-char descriptions, and name/directory mismatches
    - `mcp_document()` must emit near-miss URLs (`http://`, trailing slash, wrong host), wrong `type`, and missing `$schema`
    - `outcome_set()` must emit missing steps, blank outcomes, explicit fails, version mismatch, and per-platform cells left blank
    - `interpreter_path()` must emit POSIX and Windows path shapes, drive letters, UNC prefixes, single and repeated spaces, a trailing space, an embedded quote, and directory names containing `&`, `|`, `;`, and `>`
    - `discount_register()` must emit an empty list, a missing field, an empty-string field, a whitespace-only field, an `INV-052` entry, and the near-misses `inv-052`, `INV-52`, and `INV-052 `
    - `inv_prose()` must emit zero, one, and many inline `INV-NNN` citations, citations of discounted invariants, citations inside code fences, and a citation adjacent to a genuine residual Claude model name in the same document
    - This module is a dependency of nearly every property test, so it is built before any of them
    - _Requirements: 1.1, 3.5, 3.6, 8.5, 11.1, 12.3, 15.5, 15.7, 16.4, 16.5_

- [x] 2. Implement the Version_Resolver

  - [x] 2.1 Implement `tools/bootcamp-transform/resolve_release.py`
    - CLI: `[--repo Senzing/senzing-bootcamp-claude-plugin] [--min-version <semver>] --out <dir>`; JSON to stdout, narration to stderr
    - List releases via `gh release list --json tagName,isDraft,isPrerelease,publishedAt`, with a GitHub REST fallback when `gh` is unavailable
    - Filter to published, `isDraft == false`, `isPrerelease == false`; parse tags as **bare semver with no `v` prefix**; select the semver maximum (not lexicographic, not by publish date)
    - Fetch the source tree at the resolved tag only (tarball or `git clone --depth 1 --branch <tag>`); never `main`
    - Emit the `ResolvedRelease` record exactly as modeled in the design, including `sourceRef`, `pluginRoot: plugins/senzing-bootcamp`, `extractedTo`, and `attempts`
    - Expose the resolved tree as the **only** source of Template_Invariant text the tooling reads, so no invariant definition is sourced from the template's development repository
    - Error codes: `E_NO_RELEASE`, `E_RESOLVE_FAILED` (3 attempts / 30 s budget), and the informational `E_ALREADY_CURRENT` when the resolved max is not greater than `--min-version`; both failure codes exit non-zero and produce no build artifact
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 15.9_

  - [x] 2.2 Write property test for release selection
    - **Property 1: Release selection is the semver-maximum of eligible releases**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 5.1**
    - Uses `release_list()`; asserts the tag-ref (never branch-ref) `sourceRef`, `E_NO_RELEASE` with no selection on an empty eligible subset, and the newer-release predicate on the update path

  - [x] 2.3 Write unit tests for resolver timeout and error distinctness in `tools/bootcamp-transform/tests/test_units.py`
    - Exactly 3 attempts, then `E_RESOLVE_FAILED`, verifiably distinct from `E_NO_RELEASE`
    - Resolution honors the 30 s budget per the design
    - _Requirements: 1.4, 1.6_

- [x] 3. Author the Transformation_Contract and generation templates

  - [x] 3.1 Author the rules, substitution sets, and ignore list in `tools/bootcamp-transform/contract.yaml`
    - `contractVersion: 1`; `template.repository` and `template.pluginRoot: plugins/senzing-bootcamp` (the template is a marketplace repo; sources are rooted at the subdirectory, not the repo root)
    - All six named substitution sets, literal-string or anchored-regex only, applied in declared order, single pass per set: `plugin-root`, `manifest-path`, `client-names`, `model-guidance`, `tool-names`, `script-paths`
    - **No substitution set may map an interpreter name to anything** — an interpreter name must never appear in generated output at all, so there is deliberately no `python3` rule
    - The `ignore` list: `.claude-plugin/marketplace.json`, `.github/**`, `.vscode/**`, root `CHANGELOG.md`, `hooks/hooks.json`, `hooks/README.md`, plus any Template_Plugin invariant registry file present in the release (the registry is maintainer-facing template development material, not bootcamp content)
    - All rules with the six rule kinds `copy`, `substitute`, `skill`, `generate`, `kiro-owned`, `ignore`, exactly as modeled in the design, including `scripts-owned` targeting the single owning skill `skills/bootcamp-onboarding/scripts/` and `scripts-vendor` as `copy`
    - `kiro-owned` rules for `kiro-hooks` (dest **both** `skills/bootcamp-onboarding/assets/kiro-hooks/` for Tier 2 and `dev.kiro/hooks/` for Tier 3), `command-skills`, and `enforcement-setup-skill`, each marked `owner: kiro`
    - This is the single shared source referenced — never duplicated — by both maintainer skills
    - _Requirements: 3.1, 3.4, 7.12, 10.1, 10.2, 10.3, 12.1, 12.2, 15.9_

  - [x] 3.2 Add the `invariantDiscounts` register and the `output.lineEndings` policy to `contract.yaml`
    - Add `invariantDiscounts: []` with the documented entry shape: `invariant`, `conflictsWith`, `resolution`, all three mandatory and non-empty
    - Document in-file that Template_Invariants are non-normative for Bootcamp_Power packaging, structure, and hook definition format; that a conflict with the Agent Plugins v1.0.0 spec or a documented Kiro mechanism is resolved in favor of the Kiro-correct construction with the invariant discounted and recorded here; and that an invariant stating a portability, security, or correctness guarantee is instead **preserved restated in Kiro mechanisms and retained as honored**
    - Record in-file that **`INV-052` is deliberately absent and must never be added**: its exec-form wording cannot be reproduced under Kiro's single-command-string hook schema, but its no-shell-dependency guarantee is preserved by install-time absolute-path interpreter resolution, so an `INV-052` entry here is the validator error `E_HONORED_INVARIANT_DISCOUNTED`
    - Add `output.lineEndings: lf` and `output.gitattributes: ".gitattributes"` referencing the committed repository artifact from task 1.2
    - The register lives inside the contract so the Create_Skill and the Update_Skill apply an identical discount set
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.6, 15.11, 16.8_

  - [x] 3.3 Author the generation templates under `tools/bootcamp-transform/templates/`
    - `plugin.json.j2` producing the exact document modeled in the design, with `$schema`, the fixed top-level field set, `license: "Apache-2.0"`, and provenance under `extensions["com.senzing.bootcamp"]` (`templateRepository`, `templateRelease`, `contractVersion`)
    - `mcp.json.j2` producing `$schema` plus the `senzing` server with `type: streamable-http` and `url: https://mcp.senzing.com/mcp`
    - `changelog-entry.md.j2` producing one entry naming the source Template_Release tag
    - Deterministic serialization: stable key ordering, LF endings, no timestamps or run IDs
    - Kiro hook JSON is **not** a generation template — it is `kiro-owned` content authored in task 11.3
    - _Requirements: 2.5, 4.2, 4.3, 4.4, 5.8, 11.1, 11.2, 14.3_

  - [x] 3.4 Write structural tests for contract single-sourcing and repository invariants in `tools/bootcamp-transform/tests/test_structure.py`
    - Exactly one `contract.yaml` exists; no duplicated rule set anywhere in the repo; all five engine scripts exist at their declared paths under `tools/bootcamp-transform/`
    - `.gitattributes` exists at the repository root and declares `eol=lf`, with binary and minified assets excluded from normalization
    - The checked-in `invariantDiscounts` list contains no `INV-052` entry, under any of the near-miss spellings
    - _Requirements: 3.1, 14.2, 15.6, 16.8_

- [x] 4. Implement the transform engine: rule matching, staging, and atomicity

  - [x] 4.1 Implement source enumeration and rule matching in `tools/bootcamp-transform/transform.py`
    - CLI: `--contract --source --tag --staging [--carry-forward <existing-power-dir>]`
    - Enumerate every file under the source plugin root with **sorted iteration**
    - Match each file to exactly one rule or an `ignore` entry; a file matching neither halts the run with `E_UNMATCHED_FILE` naming that exact path and produces no output tree
    - _Requirements: 3.2, 3.3, 3.6_

  - [x] 4.2 Write property test for total rule coverage
    - **Property 5: The rule set totally covers the input, and nothing is silently dropped**
    - **Validates: Requirements 3.6, 12.1**

  - [x] 4.3 Implement staging output, build manifest, atomic swap, and write containment in `transform.py`
    - All writes go to a sibling staging directory; the target is replaced only after validation passes, via move-old-aside → move-new-in → delete-old
    - Any failure discards staging and leaves `powers/senzing-bootcamp/` byte-identical to its prior state, with no staging residue
    - Emit `.build-manifest.json` per the design data model: `manifestVersion`, `templateRelease`, `contractVersion`, and per output file `path`, `ruleId`, `owner` (`template` | `kiro`), `sourcePath`, and the SHA-256 of the file **as written** — the hash the checkout-drift check compares against
    - Write LF line endings unconditionally, so the manifest hash matches a checkout governed by `.gitattributes`
    - Reject and never follow any path that escapes the target root, including `..` segments, absolute-looking paths, and symlinks
    - Materialize `kiro-owned` files from `--carry-forward` when present (update path), else from `templates/kiro-owned/` (create path)
    - Determinism: sorted iteration, no timestamps or run IDs in output content, fixed serializer with stable key ordering
    - Error codes `E_TRANSFORM_FAILED` and `E_WRITE_FAILED`
    - _Requirements: 3.5, 4.8, 5.5, 5.7, 14.1, 14.4, 14.5, 16.8, 16.9_

  - [x] 4.4 Write property test for transform determinism
    - **Property 4: Transformation is deterministic and idempotent**
    - **Validates: Requirements 3.5**

  - [x] 4.5 Write property test for failure atomicity
    - **Property 6: Failure leaves the target byte-identical**
    - **Validates: Requirements 2.4, 4.6, 4.7, 4.8, 5.2, 5.7, 13.4, 14.5**
    - Uses `failure_point()` to inject faults mid-write, post-write pre-validate, mid-swap, permission-denied, and path-is-a-file

  - [x] 4.6 Write property test for write containment
    - **Property 7: Writes are contained within the target directory**
    - **Validates: Requirements 14.1**

  - [x] 4.7 Write property test for create/update output equivalence
    - **Property 3: Create and update produce identical output, and the contract is the only lever**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5, 5.3**
    - Also asserts that a single-rule contract mutation changes both paths' outputs identically, with `contract.yaml` the only modified input

- [x] 5. Implement the transform engine: rule kinds and content fidelity

  - [x] 5.1 Implement the substitution engine and named substitution sets in `transform.py`
    - Literal-string and anchored-regex only, applied in declared order, single pass per set; no heuristic or model-generated rewriting
    - Load set definitions from `contract.yaml`; never hardcode a substitution in code
    - Inline `INV-NNN` citations in ported prose are content: no substitution set may touch them, including citations of discounted invariants
    - _Requirements: 10.2, 12.2, 15.7_

  - [x] 5.2 Write property test for substitution completeness
    - **Property 8: Declared substitutions leave zero residuals in corresponding positions**
    - **Validates: Requirements 10.2, 12.2**
    - Uses `file_content()`: zero, one, and many occurrences; adjacent tokens; tokens inside code fences

  - [x] 5.3 Implement the `copy` and `substitute` rule kinds in `transform.py`
    - `copy` produces byte-for-byte identical output, including binary and minified assets
    - `substitute` copies then applies only the declared sets, leaving all other bytes unchanged
    - Wire the `docs` rule so every template documentation example and reference asset lands at a mapped destination or is named by an explicit link in a ported document
    - _Requirements: 10.3, 12.1, 12.2_

  - [x] 5.4 Write property test for rule-kind fidelity
    - **Property 10: Ported content is faithful to its rule kind**
    - **Validates: Requirements 7.15, 10.3**
    - Includes the invariant-reference check: the multiset of `INV-NNN` references in a ported skill body is identical to its template source

  - [x] 5.5 Implement the `skill` rule kind in `transform.py`
    - Place each ported skill at `skills/<skill-name>/SKILL.md` with `<skill-name>` byte-identical to the source directory name
    - Parse template frontmatter (`name`, `description` only) and apply **additive** adaptation: preserve `name`, extend `description` with the skill's trigger phrase, add `license: "Apache-2.0"`, `compatibility`, and `metadata` (`author`, `version`, `templateRelease`, `templateSkill`)
    - Copy sibling `.md` files into `references/`, preserving the source layout so every relative cross-reference resolves to the same target
    - Preserve each skill's learning objectives, instructional steps, and exercises unchanged apart from the declared substitution sets
    - Reject frontmatter where `name`, `description`, or `license` would be empty or absent
    - _Requirements: 7.15, 8.1, 8.2, 8.5, 8.6_

  - [x] 5.6 Implement script porting, vendored assets, and missing-asset detection in `transform.py`
    - Port every `scripts/**/*.py` into the single owning skill `skills/bootcamp-onboarding/scripts/`, preserving each script's file name and relative sub-structure below `scripts/` byte-identically, so same-directory module imports (`import recap_checkpoint`, `import docker_lifecycle`) keep working
    - Copy `scripts/vendor/**` (including `d3.v7.min.js`) byte-for-byte to the same relative location
    - Apply the `plugin-root`, `manifest-path`, and `tool-names` sets to ported scripts; repoint `feedback-capture.py` from `../.claude-plugin/plugin.json` to `../plugin.json`
    - A script referencing a vendored asset absent from the source halts that port with `E_MISSING_ASSET` naming the script and the asset, leaving the destination `scripts/` tree unchanged
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement the `generate` rule kind for `plugin.json` and `mcp.json`

  - [x] 7.1 Implement `plugin.json` generation with version stamping and provenance in `transform.py`
    - Render `templates/plugin.json.j2` with `ResolvedRelease` data into the Power root, alongside `mcp.json`
    - Stamp `version` as the resolved tag **character-for-character**
    - Write provenance to `extensions["com.senzing.bootcamp"].templateRelease`, outside the schema's fixed top-level field set
    - Emit `license: "Apache-2.0"` and write the Power's `LICENSE` file matching the repository root license identifier
    - _Requirements: 2.1, 2.2, 2.5, 4.1, 4.2, 4.4, 14.3_

  - [x] 7.2 Implement `mcp.json` generation in `transform.py`
    - Translate the template's `{"type":"http","url":"https://mcp.senzing.com/mcp"}` to `{"type":"streamable-http", ...}` and add `$schema`
    - _Requirements: 4.1, 4.3, 11.1, 11.2_

  - [x] 7.3 Write unit tests for license, provenance, and MCP translation in `tests/test_units.py`
    - `plugin.json.license == "Apache-2.0"` and a `LICENSE` file is present
    - Power license identifier matches the repository root license
    - Template `{"type":"http"}` → `{"type":"streamable-http"}` on the real `0.5.1` document
    - _Requirements: 4.4, 11.2, 14.3_

- [x] 8. Implement the Schema_Validator

  - [x] 8.1 Implement `tools/bootcamp-transform/validate.py` core: report model and tagging gate
    - CLI: `--staging <dir> --tag <semver> --report <path.json>`
    - Run **all** checks and collect **every** finding before returning; never stop at the first failure
    - Emit the `ValidationReport` data model with `reportVersion`, `templateRelease`, `powerVersion`, `checks[]`, `status` ∈ {`passed`, `incomplete`, `failed`}, and `tagAllowed` true only when `status == "passed"`
    - Fail closed: a check that cannot be evaluated records a fail, not a pass
    - _Requirements: 13.1, 13.2, 13.4, 13.5_

  - [x] 8.2 Implement schema checks for `plugin.json` and `mcp.json`, plus Senzing MCP exactness, in `validate.py`
    - Validate `plugin.json` against the Agent Plugins v1.0.0 plugin schema and `mcp.json` against the MCP schema; record a pass/fail per file
    - Require `$schema` present; require the `senzing` server with `url` exactly `https://mcp.senzing.com/mcp` and `type` exactly `streamable-http`
    - Error codes `E_SCHEMA_INVALID` and `E_MCP_INVALID`; either blocks tagging and leaves existing release tags unchanged
    - _Requirements: 4.2, 4.3, 11.1, 11.3, 11.4, 11.5, 13.1, 13.2_

  - [x] 8.3 Write property test for the Senzing MCP declaration
    - **Property 14: The Senzing MCP declaration is exact**
    - **Validates: Requirements 4.3, 11.1, 11.2, 11.3, 11.4, 11.5**
    - Uses `mcp_document()` near-miss cases

  - [x] 8.4 Implement `SKILL.md` frontmatter validation in `validate.py`
    - Per file: `name` present, non-blank, equal to the containing directory name; `description` present, non-blank, ≤ 1024 chars, containing that skill's declared trigger phrase; `license` present and non-blank
    - Record exactly one frontmatter result per `SKILL.md` file; `E_FRONTMATTER_INVALID` blocks tagging
    - _Requirements: 8.5, 8.6, 13.3, 13.4_

  - [x] 8.5 Write property test for frontmatter validation
    - **Property 13: Skill frontmatter is complete, correct, and individually reported**
    - **Validates: Requirements 8.5, 8.6, 13.3**

  - [x] 8.6 Implement cross-reference resolution checking in `validate.py`
    - Verify every relative cross-reference between skills resolves to an existing file within the Power
    - Report one `E_UNRESOLVED_REFERENCE` finding per broken link naming its source file and target path; block tagging until zero remain
    - _Requirements: 8.3, 8.4_

  - [x] 8.7 Write property test for cross-reference integrity
    - **Property 12: Cross-reference integrity survives transformation and is verified**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    - Uses `skill_tree()`: `../` links, broken links, self-links, links into `references/`, `module-03b`-style names

  - [x] 8.8 Implement the version-match check in `validate.py`
    - Compare the Power version string character-for-character against the resolved tag and against `extensions["com.senzing.bootcamp"].templateRelease`
    - On mismatch emit `E_VERSION_MISMATCH` naming both strings, set `tagAllowed` false, and leave the existing version and metadata unchanged
    - _Requirements: 2.3, 2.4_

  - [x] 8.9 Write property test for version stamp and provenance
    - **Property 2: Version stamp and provenance round trip**
    - **Validates: Requirements 1.5, 2.1, 2.2, 2.3, 2.4, 2.5**

  - [x] 8.10 Implement the residual-Claude reference scan with the `INV-NNN` exemption in `validate.py`
    - Report zero residual `${CLAUDE_PLUGIN_ROOT}` occurrences in any ported file
    - Report every residual Claude-specific model reference (subscription plan, model name, effort setting) with its source document and location within that document, as `W_RESIDUAL_CLAUDE_REF`
    - Treat an inline `INV-NNN` citation as **compliant content**, never a residual hit — an exemption narrowly scoped to the citation token itself, so a Claude model or plan name adjacent to a citation in the same document is still reported
    - Any genuine hit sets `status: incomplete` — distinct from both `passed` and `failed` — and `tagAllowed` false
    - _Requirements: 10.2, 12.3, 12.4, 15.8_

  - [x] 8.11 Write property test for residual Claude reference detection
    - **Property 9: Residual Claude-specific references are fully detected and downgrade the outcome**
    - **Validates: Requirements 12.3, 12.4**

  - [x] 8.12 Implement inventory bijection and progression-order checks in `validate.py`
    - Assert the set of ported bootcamp skill names equals the set of template bootcamp skill directory names in the resolved release, and that every other skill in the Power carries a `kiro-owned` declaration in the contract
    - Assert the command-derived skill set is in one-to-one correspondence with the template command set
    - Assert the ported progression sequence equals the template progression sequence element-for-element, onboarding through graduation, including `module-03b` positioned between `module-03` and `module-04`
    - _Requirements: 7.1, 7.2, 7.3, 9.1_

  - [x] 8.13 Write property test for inventory bijections
    - **Property 16: Skill and command inventories are bijections with the template**
    - **Validates: Requirements 7.1, 7.2, 9.1**

  - [x] 8.14 Write property test for progression order
    - **Property 17: Bootcamp progression order is preserved**
    - **Validates: Requirements 7.3**

  - [x] 8.15 Implement the broken-import and asset-reference checks in `validate.py`
    - Verify every same-directory Python module import between two ported scripts resolves; report `E_BROKEN_IMPORT` naming the importing script and the imported module name, and block tagging
    - Verify every script and vendored asset referenced by a ported script or hook exists in the produced Power
    - _Requirements: 10.4, 10.6_

  - [x] 8.16 Write property test for script layout and dangling assets
    - **Property 11: Script layout is preserved and dangling asset references are detected**
    - **Validates: Requirements 10.1, 10.4, 10.6**

  - [x] 8.17 Implement the Invariant_Discount_Register checks in `validate.py`
    - `E_INCOMPLETE_DISCOUNT`: every `invariantDiscounts` entry carries a non-empty `invariant`, `conflictsWith`, and `resolution`; report the incomplete entry **and** the missing field, and block tagging
    - `E_HONORED_INVARIANT_DISCOUNTED`: `INV-052` must not appear in the register — it is honored, not discounted, because its no-shell-dependency guarantee is preserved by install-time absolute-path interpreter resolution; report the disallowed identifier and block tagging
    - Report every offending entry in one run, not the first
    - _Requirements: 15.5, 15.6_

  - [x] 8.18 Implement the Hook_Command_String checks in `validate.py`
    - `E_SHELL_CONSTRUCT_IN_HOOK`: no command string contains a chaining operator (`&&`, `||`, `;`), a pipe, a redirection operator (`>`, `<`, `>>`), or a shell builtin invocation; report the offending hook definition **and** the offending construct, and block tagging
    - `E_BARE_INTERPRETER`: every command string names an **absolute** interpreter path rather than a bare interpreter name, and quotes both the interpreter path and the script path; report the offending definition and block tagging
    - Tokenize each emitted string and assert it recovers exactly the two-element argument vector `[interpreter, script]`, so a space in either path cannot split
    - Scan Tier 2 assets, Tier 3 `dev.kiro/hooks/`, and anything the `Hook_Installer` would write
    - _Requirements: 10.5, 16.3, 16.4, 16.5, 16.6_

  - [x] 8.19 Implement the Build_Manifest hash check in `validate.py`
    - `E_HASH_MISMATCH`: every checked-out Bootcamp_Power file's content hash equals the hash recorded for that file in the `Build_Manifest`; report the file and both hashes, and block tagging
    - Include the diagnostic that the usual cause is line-ending rewriting on checkout, pointing at `.gitattributes`
    - _Requirements: 16.8, 16.9_

  - [x] 8.20 Write property test for the discount register and invariant citations
    - **Property 25: The discount register is complete, excludes INV-052, and invariant citations survive untouched**
    - **Validates: Requirements 15.4, 15.5, 15.6, 15.7, 15.8**
    - Uses `discount_register()` and `inv_prose()`; asserts the citation count is identical before and after transformation, and that the residual-reference check reports zero citations while still reporting every genuine residual reference in the same document

  - [x] 8.21 Write property test for report completeness and gating
    - **Property 15: The validation report is complete and gates tagging biconditionally**
    - **Validates: Requirements 4.2, 13.1, 13.2, 13.4, 13.5**
    - Seeds *k* independent defects across all implemented checks and asserts the findings cover all *k*, not a prefix

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement the Reconciler and changelog generation

  - [x] 10.1 Implement three-way classification in `tools/bootcamp-transform/reconcile.py`
    - Inputs: previous `.build-manifest.json` hashes, the current on-disk Power, and the fresh staging tree
    - Classify every path in the union of the three into exactly one bucket — `added`, `modified`, `removed`, `unchanged`, `preservedAdaptations`, `conflicts` — per the design's classification table
    - Emit the `ReconciliationReport` data model
    - _Requirements: 5.4_

  - [x] 10.2 Write property test for reconciliation classification
    - **Property 20: Reconciliation classifies every path exactly once**
    - **Validates: Requirements 5.4, 5.6**
    - Uses `reconcile_triple()` covering all four divergence combinations, additions, removals, and `kiro-owned` files

  - [x] 10.3 Implement adaptation preservation and conflict reporting in `reconcile.py`
    - Preserve every `owner: kiro` file and every locally divergent file byte-identically; **never overwrite a locally divergent file**
    - When a local edit and an upstream change collide, retain the local content and flag a conflict identifying both the preserved adaptation and the conflicting template change
    - Conflicts are reported outcomes, not errors; they never block the update
    - _Requirements: 5.5, 5.6_

  - [x] 10.4 Write property test for adaptation survival
    - **Property 21: Kiro-specific adaptations survive an update byte-identically**
    - **Validates: Requirements 5.5, 5.6**

  - [x] 10.5 Implement invariant-text drift flagging and the `flaggedInvariantDiscounts` report field in `reconcile.py`
    - For each entry in the contract's `invariantDiscounts`, compare that invariant's text between the previously resolved release and the newly resolved release, reading both from the resolved release trees rather than the template development repository
    - When the text changed, add a `flaggedInvariantDiscounts` entry to the `ReconciliationReport` carrying `invariant`, `reason`, and `action`, so a stale discount surfaces for Maintainer re-evaluation instead of being carried forward unexamined
    - Identical text does not flag; flagging is a reported outcome, not an error
    - _Requirements: 15.10_

  - [x] 10.6 Write unit tests for discount drift flagging in `tests/test_units.py`
    - A newer release that edits the text of an invariant recorded in the register flags exactly that entry
    - Identical invariant text produces no flag
    - _Requirements: 15.10_

  - [x] 10.7 Implement CHANGELOG entry generation for successful updates
    - On a successful update, render `templates/changelog-entry.md.j2` and append exactly one entry to `powers/senzing-bootcamp/CHANGELOG.md` whose text contains the newer resolved Template_Release tag, altering no other changelog content
    - On any failure, make no changelog entry and leave the Power unchanged
    - _Requirements: 5.7, 5.8_

  - [x] 10.8 Write property test for changelog recording
    - **Property 22: A successful update records exactly one changelog entry naming its source release**
    - **Validates: Requirements 5.8**

- [x] 11. Author the `kiro-owned` content (hand-authored, no template source)

  - [x] 11.1 Author the three command-derived skills under `tools/bootcamp-transform/templates/kiro-owned/skills/`
    - `start-bootcamp` (trigger "start the senzing bootcamp", delegates to `bootcamp-onboarding`), `graduate-bootcamp` (trigger "graduate the senzing bootcamp", delegates to `graduation`), `bootcamp-feedback` (trigger "give senzing bootcamp feedback", delegates to `bootcamp-onboarding/references/feedback.md`)
    - Each is a thin skill with exactly one declared trigger phrase in its description, and complete Agent Plugins frontmatter (`name` matching the directory, `description`, `license`)
    - Trigger phrases must be lexically disjoint: no phrase is a substring of another, so no single statement matches two, and a statement matching none activates none
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 11.2 Write property test for trigger-phrase exclusivity
    - **Property 19: A statement matches at most one command trigger phrase**
    - **Validates: Requirements 9.2, 9.3, 9.5**
    - Uses `statement()`: exact phrases, overlapping phrases, near-misses, phrases embedded in longer text

  - [x] 11.3 Author the Kiro hook JSON assets, the parity coverage map, and the Tier 1 instruction content
    - Author hook definitions for `SessionStart` (`session-start.py`), `UserPromptSubmit` (`feedback-capture.py`, `checkpoint-tick.py`), `PreToolUse` (`write-gate.py`, matcher `fs_write|str_replace|fs_append`), and advisory `Stop` (`stop-nudge.py`), each in the `{"version":"v1","hooks":[...]}` shape with a single-string `action.command`
    - Every shipped `action.command` contains **only** the `<ABSOLUTE_PYTHON>` and `<ABSOLUTE_SCRIPTS_DIR>` placeholders, both quoted, in the form `"<ABSOLUTE_PYTHON>" "<ABSOLUTE_SCRIPTS_DIR>/<script>.py"` — no interpreter name, no `${PLUGIN_ROOT}` token in the command position, and no chaining operator, pipe, redirection, or shell builtin. The shipped asset is deliberately not runnable until the installer resolves both placeholders
    - Place the same definitions at both Tier 2 (`skills/bootcamp-onboarding/assets/kiro-hooks/`) and Tier 3 (`dev.kiro/hooks/`) destinations per the contract's `kiro-hooks` rule, with Tier 3 never the sole delivery path for a behavior
    - Name every definition file with the `senzing-bootcamp-` prefix
    - Author a machine-readable coverage map declaring, for every template hook event, its Kiro mechanism, its tier, and — for events with no Kiro trigger (`PreCompact`, `SessionEnd`) or no blocking capability (`Stop`) — the skill-instruction location carrying the advisory behavior, its behavior marker, and the documented parity gap
    - Author the Tier 1 skill-instruction content those markers point at: write-location (INV-200), secrets (INV-109), and container stop-not-remove (INV-101) rules in `bootcamp-onboarding/references/ground-rules.md`; resume-on-session-start in `bootcamp-onboarding/SKILL.md`; recap folding in `module-completion.md` and `graduation/SKILL.md`; the closing-👉-question rule in `ground-rules.md` and each module close phase — so the complete bootcamp is delivered with zero hook definitions installed
    - Preserve every ported hook script's "no `config/bootcamp_progress.json` ⇒ no-op" guard so an installed hook set never affects unrelated Kiro sessions
    - _Requirements: 7.4, 7.5, 7.9, 7.12, 7.13, 7.14, 10.5, 16.5_

  - [x] 11.4 Author the `bootcamp-enforcement-setup` skill and its `install_hooks.py` installer
    - Author the skill under `templates/kiro-owned/skills/bootcamp-enforcement-setup/` with its installer script at `scripts/install_hooks.py`, so the interpreter that will run the hooks is the interpreter that resolves them
    - **Interpreter resolution:** read `sys.executable`, resolve it to an absolute filesystem path, and write that path into every `Hook_Command_String` in place of the `<ABSOLUTE_PYTHON>` placeholder — never a bare `python3`, `python`, or `py`, so the hooks work where `python3` is absent from PATH and can never hit a Store alias stub
    - **Script path resolution:** resolve `<ABSOLUTE_SCRIPTS_DIR>` to the absolute directory of the ported script set at install time rather than relying on `${PLUGIN_ROOT}` expansion inside a command string
    - **Quoting:** quote both resolved paths so a path containing a space is passed as a single argument on every Supported_Platform; emit nothing but interpreter path followed by script arguments
    - **Disclosure first:** present the full path of every file it will write into the `Workspace_Hooks_Directory` before writing any of them, and require explicit consent
    - **Idempotent:** a second run leaves `.kiro/hooks/` identical to the first run's result, with no duplicate hook entries; re-running re-resolves both paths from scratch, which is the documented repair after a Power upgrade, a Python upgrade, or a removed virtualenv
    - **Namespaced and removable:** every written filename carries the `senzing-bootcamp-` prefix, and the documented removal step deletes exactly those files and leaves every other workspace hook file unchanged
    - **Declining is supported:** state plainly which protections become advisory (write-location gate, secret gate), write no file into the `Workspace_Hooks_Directory`, and leave a working Tier 1 bootcamp
    - _Requirements: 7.6, 7.7, 7.8, 7.9, 7.10, 7.11, 10.5, 16.2, 16.3, 16.4, 16.5_

  - [x] 11.5 Write property test for generated hook command portability
    - **Property 24: Every generated hook command is absolute, correctly quoted, and shell-free**
    - **Validates: Requirements 10.5, 16.3, 16.4, 16.5, 16.6**
    - Uses `interpreter_path()`: POSIX and Windows shapes, drive letters, UNC prefixes, spaces, an embedded quote, and directory names containing `&`, `|`, `;`, `>`
    - Asserts the installer's generated string names the absolute interpreter, tokenizes back to exactly `[interpreter, script]`, and contains no shell construct; and that the validator reports exactly the violating command strings and exactly the hash-mismatched files — no more, no fewer

  - [x] 11.6 Write property test for hook behavior reachability
    - **Property 18: Every template hook behavior remains reachable**
    - **Validates: Requirements 7.4, 7.5, 7.12, 7.13, 7.14, 10.5**
    - Asserts every template hook event is covered by a generated Kiro hook definition or a declared skill-instruction location containing that behavior's marker, and that Tier 3 is never a behavior's only delivery path

  - [x] 11.7 Write structural tests for hook definitions in `tests/test_structure.py`
    - Every hook JSON parses and names a valid Kiro trigger (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreTaskExec`, `PostTaskExec`, `PostFileSave`, `PostFileCreate`, `PostFileDelete`, `Stop`)
    - Every file name the `Hook_Installer` would write carries the `senzing-bootcamp-` prefix
    - Every shipped `action.command` still carries both placeholders and no interpreter name, and the same definition set exists at the Tier 2 and Tier 3 destinations
    - Every template hook event appears in the parity coverage map with a mechanism and a tier
    - _Requirements: 7.5, 7.9, 7.12, 16.5_

  - [x] 11.8 Implement optional-runtime degradation for runtimes other than the resolved interpreter
    - Where a ported script needs a runtime other than the resolved Python interpreter (Docker for the SDK modules, a browser for the truth-set visualization), it reports what is unavailable, returns success, and never blocks its hook trigger or wedges a session
    - Declare the guard in the contract as a substitution set or a `kiro-owned` wrapper rather than hand-patching generated output
    - Document the reduced-capability path in `ground-rules.md` and in the enforcement-setup skill, so a Bootcamper without Docker still progresses through the Tier 1 experience
    - _Requirements: 16.7_

  - [x] 11.9 Write unit tests for optional-runtime absence in `tests/test_units.py`
    - With Docker mocked absent and with a browser mocked absent, the owning script reports what is unavailable, returns success, and does not block its trigger
    - _Requirements: 16.7_

- [x] 12. Build the maintainer Power

  - [x] 12.1 Create `powers/senzing-bootcamp-maintainer/plugin.json`
    - Agent Plugins v1.0.0 conformant, `license: "Apache-2.0"`
    - _Requirements: 14.2, 14.3_

  - [x] 12.2 Author `powers/senzing-bootcamp-maintainer/skills/create-bootcamp-power/SKILL.md`
    - Trigger phrase "create the senzing bootcamp power"; orchestrates resolve → pre-flight target check → transform → validate → atomic swap → report, then directs the Maintainer to the `Test_Checklist`
    - Applies the rules in `tools/bootcamp-transform/contract.yaml` by invoking the shared engine; contains no transformation logic of its own
    - Pre-flight: if `powers/senzing-bootcamp/` exists and is non-empty, report `E_TARGET_EXISTS` naming the path and require explicit confirmation before touching anything; on decline emit `E_OVERWRITE_DECLINED` and terminate with the Power unchanged
    - Create the target directory only at swap time; on write failure emit `E_WRITE_FAILED` with the repository unchanged; if the release cannot be resolved, create or modify nothing
    - Invoke `tools/bootcamp-transform/` by repo-relative path and read its JSON output; state in `compatibility` frontmatter that the skill requires this repository as the open workspace
    - _Requirements: 3.2, 4.1, 4.5, 4.6, 4.7, 4.8, 14.1, 14.2, 14.4, 14.5_

  - [x] 12.3 Author `powers/senzing-bootcamp-maintainer/skills/update-bootcamp-power/SKILL.md`
    - Trigger phrase "update the senzing bootcamp power"; orchestrates read current version + manifest → resolve newer → transform → reconcile → present the reconciliation report → validate → atomic swap → append the changelog entry
    - When no newer release exists, report that the Power is current and change nothing
    - Present the reconciliation report including `flaggedInvariantDiscounts`, so an invariant whose text changed upstream is surfaced for Maintainer re-evaluation
    - When the transform or validation fails, leave the Power unchanged, make no changelog entry, and report that the update did not complete
    - References the same `contract.yaml` path as the create skill; no duplicated rules
    - _Requirements: 3.1, 3.3, 5.1, 5.2, 5.3, 5.4, 5.7, 5.8, 15.10_

  - [x] 12.4 Write structural tests for maintainer tooling placement in `tests/test_structure.py`
    - Both maintainer skills exist at their declared paths and reference `tools/bootcamp-transform/contract.yaml`
    - _Requirements: 3.1, 14.2_

  - [x] 12.5 Write unit tests for create/update orchestration edge cases in `tests/test_units.py`
    - Existing-target conflict names `powers/senzing-bootcamp/` and writes nothing before confirmation; decline path terminates cleanly
    - Absent target directory is created at swap time
    - Permission-denied and path-is-a-file write failures produce `E_WRITE_FAILED`
    - _Requirements: 4.5, 4.6, 14.4, 14.5_

- [x] 13. Build the Test_Checklist and its record-based tagging gate

  - [x] 13.1 Author `docs/test-checklist.md`
    - All **17** ordered steps from the design, each uniquely numbered and declaring one observable pass/fail outcome
    - Steps 1–8: validation `passed` for the exact version; local install via Kiro Powers → **Add Custom Power**; load in a fresh chat session (no prior conversation history); Senzing MCP connection; a successful Senzing MCP tool call; per-skill trigger activation across the 16-skill inventory; a no-match statement activating no command-derived skill; progression order onboarding → 00 → 03b → graduation
    - Steps 9–11: the A1–A3 observations — whether a hook bundled under `dev.kiro/hooks/` fires with nothing installed, whether each hook the installer wrote fires on its declared trigger, and the actual Kiro write-tool names a `PreToolUse` matcher sees against the contract regex
    - Steps 12–13: installer run twice leaves `.kiro/hooks/` identical to the first run's result; the installer discloses every path before writing and the documented removal deletes exactly those files, leaving every other workspace hook file unchanged
    - Steps 14–15: write-gate blocks an out-of-project write and a secret-bearing write; every ported script runs without a `${CLAUDE_PLUGIN_ROOT}` or import error
    - **Step 16 — per-platform matrix complete:** steps 2, 10, and 15 each carry a separately recorded outcome for Linux, macOS, and Windows — nine cells, none blank, an unrecorded platform being a fail rather than a blank
    - **Step 17 — space in path:** a Hook_Command_String whose resolved interpreter path or resolved script path contains a space invokes the ported script correctly; install under a path such as `C:\Users\Bob Smith\…` or `/Users/bob smith/…` and fire the hook
    - _Requirements: 6.1, 6.4, 6.5, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13, 7.3, 9.4, 9.5, 16.1_

  - [x] 13.2 Implement the test-record tooling at `tools/bootcamp-transform/testrecord.py`
    - Write `docs/test-records/<version>.md` from the checklist definition: version under test, resolved Template_Release, Maintainer, date, `ValidationReport` status, one row per step with pass/fail and notes
    - Emit **three** outcome cells for steps 2, 10, and 15 — one per Supported_Platform — and treat step 16 as the assertion that all nine are filled
    - Parse a record back and compute `tagAllowed`: true only when every defined step has a recorded pass for the exact version under test; missing steps, blank outcomes, blank platform cells, and explicit failures all yield false, emitting `E_CHECKLIST_INCOMPLETE`
    - Retain per-step outcomes so they remain reviewable for the tagged release
    - _Requirements: 6.2, 6.3, 6.6, 6.12_

  - [x] 13.3 Write property test for the test-record gate
    - **Property 23: The test record gates tagging and round-trips faithfully**
    - **Validates: Requirements 6.2, 6.3, 6.6**
    - Uses `outcome_set()`: missing steps, blank outcomes, explicit fails, version mismatch, per-platform cells left blank

  - [x] 13.4 Write structural tests for the checklist in `tests/test_structure.py`
    - `docs/test-checklist.md` parses: steps uniquely numbered and ordered, each declaring a pass/fail outcome, with the Add-Custom-Power step and the fresh-session step present
    - Exactly one MCP-connectivity step; one activation step per skill in the inventory
    - The per-platform matrix step and the space-in-path step are both present
    - _Requirements: 6.1, 6.4, 6.5, 6.12, 6.13_

- [x] 14. Generate and commit the deliverable Bootcamp_Power

  - [x] 14.1 Run the full pipeline against the real Template_Release `0.5.1` and commit `powers/senzing-bootcamp/`
    - Execute resolve → transform → validate → atomic swap end to end; the validation report must be `passed` before the swap
    - Verify the committed result: 16 skills (12 ported + 3 command-derived + 1 enforcement-setup), `plugin.json` version `0.5.1` with provenance under `extensions`, `mcp.json` with the exact Senzing declaration, `LICENSE`, `.build-manifest.json`, ported scripts and `vendor/` under `skills/bootcamp-onboarding/scripts/`, ported `docs/`, Tier 2 hook assets, and the Tier 3 `dev.kiro/hooks/` copies
    - Confirm every committed file has LF endings and a `Build_Manifest` hash that matches a fresh checkout
    - Confirm no committed hook command contains an interpreter name or a shell construct — only the two placeholders
    - Resolve any `E_UNMATCHED_FILE` from the real tree by adding a rule or an `ignore` entry to `contract.yaml`, never by skipping the file in code
    - This committed tree is the baseline for the golden-tree regression check
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 7.1, 7.3, 7.12, 7.15, 8.1, 10.1, 10.3, 11.1, 12.1, 14.1, 14.3, 14.4, 16.8_

  - [x] 14.2 Write integration tests in `tools/bootcamp-transform/tests/test_integration.py`
    - Resolve the real latest release from `Senzing/senzing-bootcamp-claude-plugin`; assert a bare-semver tag with no `v` prefix
    - Full end-to-end build from the real `0.5.1` release; assert 16 skills, 12 of them ported, and a `passed` validation report
    - Golden-tree comparison: the committed `powers/senzing-bootcamp/` equals a fresh build from its recorded `templateRelease` — a standing regression check on Properties 3 and 4, and on the manifest hashes
    - One live call to `https://mcp.senzing.com/mcp` confirming a successful tool response
    - Run a generated Hook_Command_String in a subprocess with `python3` removed from `PATH`; the script still executes, because the command names an absolute interpreter
    - 1–3 examples each; these touch the network, so iteration count buys nothing
    - _Requirements: 1.1, 1.3, 3.5, 6.4, 13.5, 16.2, 16.9_

- [x] 15. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Wire the release gate and keep assumption-dependent values single-sourced

  - [x] 16.1 Generate the test-record skeleton for the committed release at `docs/test-records/0.5.1.md`
    - Run `testrecord.py` against `docs/test-checklist.md` to emit the record for version `0.5.1` with all 17 steps and the nine per-platform cells present and unfilled
    - Assert the gate is closed while cells are blank: `tagAllowed` is false for a skeleton, for a record with any blank platform cell, and for a record whose version does not match the version under test
    - Commit the skeleton so the Maintainer fills recorded outcomes into a file that the gate already parses
    - _Requirements: 6.2, 6.3, 6.6, 6.12, 6.13_

  - [x] 16.2 Make every assumption-dependent value a single point of change
    - Keep the `PreToolUse` matcher regex as one `tool-names` value in `contract.yaml`, so correcting it after the A3 observation is a one-line contract edit plus a rebuild — never a code edit
    - Keep interpreter and script resolution entirely inside `install_hooks.py`, so the A2 outcome changes no hook asset: the asset ships placeholders and the installer resolves absolute quoted paths regardless
    - Add the A4 fallback behind a contract flag: when the Power's `skills/*/scripts/` path is not stable, the installer copies the ported script set into the workspace alongside the hook JSON and resolves `<ABSOLUTE_SCRIPTS_DIR>` to that copy
    - Add a regression test asserting each of these values appears in exactly one place
    - _Requirements: 3.4, 6.11, 7.6, 16.3_

- [x] 17. Optional forward-looking work

  - [x] 17.1 Add a GitHub Action that watches upstream releases and opens an update PR
    - Deferred by the requirements as a future enhancement; v1 update is manual, Maintainer-run
    - Would invoke `resolve_release.py --min-version <current>` and report when a newer Template_Release exists
    - _Requirements: 5.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. All test tasks are marked optional per workflow convention; the property tests are the primary correctness evidence for Artifact B, so skipping them trades away the design's main verification layer.
- `powers/senzing-bootcamp/` is **generated output**, produced by task 14.1. Hand-authored `kiro-owned` content lives at `tools/bootcamp-transform/templates/kiro-owned/` and is materialized into the Power by the transform engine. Nothing in the plan hand-patches generated output; an adaptation is expressed as a contract rule, a substitution set, or a `kiro-owned` file.
- **`INV-052` is honored, not discounted.** Every Hook_Command_String names a quoted absolute interpreter path resolved at install time from `sys.executable`, quotes the absolute script path, and contains no chaining operator, pipe, redirection, or shell builtin. The `Invariant_Discount_Register` contains no `INV-052` entry, and `E_HONORED_INVARIANT_DISCOUNTED` blocks tagging if one appears. Inline `INV-NNN` citations in ported prose are preserved verbatim and are exempt from the residual-Claude-reference check.
- All **25** correctness properties are covered, one property per test, all in `tools/bootcamp-transform/tests/test_properties.py`: P1 (2.2), P2 (8.9), P3 (4.7), P4 (4.4), P5 (4.2), P6 (4.5), P7 (4.6), P8 (5.2), P9 (8.11), P10 (5.4), P11 (8.16), P12 (8.7), P13 (8.5), P14 (8.3), P15 (8.21), P16 (8.13), P17 (8.14), P18 (11.6), P19 (11.2), P20 (10.2), P21 (10.4), P22 (10.8), P23 (13.3), P24 (11.5), P25 (8.20).
- Because all property tests share one file, the dependency graph gives each property task its own wave. The same rule separates tasks that share `test_structure.py`, `test_units.py`, `transform.py`, `validate.py`, `reconcile.py`, and `contract.yaml`.
- The five validator checks added for the cross-platform and invariant-precedence criteria — `E_INCOMPLETE_DISCOUNT`, `E_HONORED_INVARIANT_DISCOUNTED` (8.17), `E_SHELL_CONSTRUCT_IN_HOOK`, `E_BARE_INTERPRETER` (8.18), and `E_HASH_MISMATCH` (8.19) — all land before task 14.1 builds the committed Power, so the deliverable cannot be produced without passing them.
- Executing the `Test_Checklist` in a live Kiro session is a Maintainer activity outside this plan: Kiro skill activation, Power installation, hook loading, MCP behavior, and per-platform operation have no programmatic harness. The plan delivers the checklist (13.1), the record tooling and its gate (13.2), the committed record skeleton (16.1), and the single-point-of-change paths for folding observed results back in (16.2).
- Checkpoints at tasks 6, 9, and 15 validate incrementally: after the transform engine, after the validator, and after the real Power is generated.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "3.1", "3.3", "11.1", "12.1"] },
    { "id": 2, "tasks": ["2.1", "3.2", "4.1", "8.1", "11.3"] },
    { "id": 3, "tasks": ["2.2", "3.4", "4.3", "11.4"] },
    { "id": 4, "tasks": ["2.3", "4.2", "5.1", "10.1", "11.7"] },
    { "id": 5, "tasks": ["4.4", "5.3", "10.3"] },
    { "id": 6, "tasks": ["4.5", "5.5", "10.5"] },
    { "id": 7, "tasks": ["4.6", "5.6", "10.6", "10.7"] },
    { "id": 8, "tasks": ["4.7", "7.1", "8.18", "11.8"] },
    { "id": 9, "tasks": ["5.2", "7.2", "8.19", "11.9"] },
    { "id": 10, "tasks": ["5.4", "7.3", "8.2"] },
    { "id": 11, "tasks": ["8.3", "8.4", "12.2"] },
    { "id": 12, "tasks": ["8.5", "8.6", "12.3"] },
    { "id": 13, "tasks": ["8.7", "8.8", "12.4", "13.1"] },
    { "id": 14, "tasks": ["8.9", "8.10", "12.5", "13.2"] },
    { "id": 15, "tasks": ["8.11", "8.12", "13.4"] },
    { "id": 16, "tasks": ["8.13", "8.15"] },
    { "id": 17, "tasks": ["8.14", "8.17"] },
    { "id": 18, "tasks": ["8.16"] },
    { "id": 19, "tasks": ["8.20"] },
    { "id": 20, "tasks": ["8.21"] },
    { "id": 21, "tasks": ["10.2"] },
    { "id": 22, "tasks": ["10.4"] },
    { "id": 23, "tasks": ["10.8"] },
    { "id": 24, "tasks": ["11.2"] },
    { "id": 25, "tasks": ["11.5"] },
    { "id": 26, "tasks": ["11.6"] },
    { "id": 27, "tasks": ["13.3"] },
    { "id": 28, "tasks": ["14.1", "17.1"] },
    { "id": 29, "tasks": ["14.2"] },
    { "id": 30, "tasks": ["16.1"] },
    { "id": 31, "tasks": ["16.2"] }
  ]
}
```
