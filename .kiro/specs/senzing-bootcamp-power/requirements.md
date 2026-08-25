# Requirements Document

## Introduction

This feature delivers a **Senzing Bootcamp Kiro Power** that reproduces, inside the Kiro IDE, the guided Senzing learning experience currently packaged as the [Senzing Bootcamp Claude Plugin](https://github.com/Senzing/senzing-bootcamp-claude-plugin). The Power is built in the Agent Plugins v1.0.0 format so that a **Bootcamper** can install it and progress through the same onboarding, module, and graduation flow.

The feature covers **two distinct artifacts**:

- **Artifact A — The Deliverable (Bootcamp_Power):** the installable Senzing Bootcamp Kiro Power that Bootcampers use. It lives in this repository at `powers/senzing-bootcamp/`.
- **Artifact B — The Maintainer Tooling:** the skills and scripts a **Maintainer** runs to (1) initially create the Bootcamp_Power from the template's latest versioned release and (2) propagate later template releases into the Bootcamp_Power. The two operations share a single-sourced **Transformation_Contract** so that create and update behavior cannot drift.

The Power maintains **behavioral parity** with the template: the same skills, triggers, MCP dependency, and hook-enforced behaviors, adapted to Kiro's plugin capabilities where a direct equivalent does not exist.

> **Decisions open to review:** The following were deferred by the user and are treated as current decisions but remain open for review during design:
> - **Hooks (RESOLVED — three-tier parity strategy):** design research settled this decision. Tier 1 expresses every hook-enforced behavior as skill instructions so the bootcamp works with no hooks installed; Tier 2 installs Kiro hook definitions into the Bootcamper's workspace `.kiro/hooks/` only with explicit consent, restoring mechanical enforcement; Tier 3 also places the same definitions under `dev.kiro/hooks/` for forward compatibility. The assumption that Kiro auto-loads hooks bundled under a Power's `dev.kiro/hooks/` directory is believed to be false today; the Test_Checklist verifies it empirically. Kiro provides no `PreCompact` or `SessionEnd` trigger and cannot block on `Stop`, so those behaviors are advisory instructions with a documented parity gap.
> - **Template invariants (RESOLVED):** Claude-authored template invariants are not normative for the Bootcamp_Power's packaging; where one would prevent correct Kiro construction it is discounted and the discount is recorded with its rationale. Where an invariant instead encodes a portability, security, or correctness guarantee, the guarantee is preserved and restated in Kiro's mechanisms rather than discounted — `INV-052` is that case. This is also why the invariant registry is not sourced from the template's development repository, leaving Requirement 1's release-only sourcing rule unaffected. Inline `INV-NNN` citations in ported prose are preserved verbatim.
> - **Cross-platform support (RESOLVED):** the Bootcamp_Power must operate on Linux, macOS, and Windows, mirroring the template's own platform commitment. Kiro's hook schema accepts only a single command string, so the template's shell-free exec-form invocation is preserved by resolving an absolute, quoted interpreter path at hook install time rather than relying on `python3` being present on PATH.
> - **Location:** the Bootcamp_Power lives in this repo at `powers/senzing-bootcamp/`; maintainer tooling also lives in this repo.
> - **Update trigger:** manual Maintainer-run for v1; an automated GitHub Action watching upstream releases is documented as a future enhancement.
> - **License:** Apache-2.0 (matches the template and this repository).

## Glossary

- **Bootcamp_Power**: The deliverable Senzing Bootcamp Kiro Power, packaged in Agent Plugins v1.0.0 format, installed and used by a Bootcamper. Located at `powers/senzing-bootcamp/`.
- **Template_Plugin**: The upstream Senzing Bootcamp Claude Plugin repository (`Senzing/senzing-bootcamp-claude-plugin`) that serves as the source of truth for bootcamp content.
- **Template_Release**: A specific versioned, tagged release of the Template_Plugin (for example, tag `0.5.1`), as opposed to the `main` branch HEAD.
- **Maintainer**: A person who runs the maintainer tooling to create or update the Bootcamp_Power.
- **Bootcamper**: An end user who installs and progresses through the Bootcamp_Power.
- **Create_Skill**: The maintainer skill that produces an initial Bootcamp_Power from a Template_Release.
- **Update_Skill**: The maintainer skill that propagates a newer Template_Release into an existing Bootcamp_Power.
- **Transformation_Contract**: A single, shared specification of the deterministic rules that map Template_Plugin files to Bootcamp_Power files. Both Create_Skill and Update_Skill consume this contract.
- **Version_Resolver**: The component that determines the latest Template_Release version.
- **Schema_Validator**: The component that checks produced files against Agent Plugins v1.0.0 schemas and skill frontmatter rules.
- **Test_Checklist**: The documented set of manual verification steps that a Maintainer performs before a release is tagged.
- **Hook_Installer**: The component of the Bootcamp_Power that, with explicit Bootcamper consent, writes Kiro hook definition files into the Bootcamper's workspace hooks directory and documents their removal.
- **Workspace_Hooks_Directory**: The Bootcamper workspace directory `.kiro/hooks/` from which Kiro loads hook definition files.
- **Senzing_MCP_Server**: The Senzing Model Context Protocol server at `https://mcp.senzing.com/mcp`, required for the bootcamp to function.
- **Agent_Plugins_Format**: The Agent Plugins v1.0.0 packaging format (`plugin.json` + `skills/` + `mcp.json` + reverse-domain client-extension directories such as `dev.kiro/`).
- **Plugin_Root_Token**: The Kiro plugin root path variable `${PLUGIN_ROOT}` used within the Bootcamp_Power in place of the template's `${CLAUDE_PLUGIN_ROOT}`.
- **Template_Invariant**: A numbered `INV-NNN` condition authored for the Template_Plugin. Template_Invariants are not normative for Bootcamp_Power packaging, except where a Template_Invariant expresses a portability or correctness guarantee, in which case the guarantee is preserved.
- **Invariant_Discount_Register**: A record held within the Transformation_Contract of each Template_Invariant discounted because honoring it would prevent correct construction of the Bootcamp_Power, together with the conflicting constraint and the resolution applied.
- **Supported_Platform**: An operating system on which the Bootcamp_Power must operate: Linux, macOS, or Windows.
- **Hook_Command_String**: The single command string that a Kiro hook `command` action carries, as written into a hook definition shipped or installed by the Bootcamp_Power.
- **Build_Manifest**: The record produced by the Transformation_Contract that lists each Bootcamp_Power output file together with the content hash of that file as written.

## Requirements

### Requirement 1: Resolve the latest versioned template release

**User Story:** As a Maintainer, I want the tooling to build from the latest versioned release of the template, so that the Bootcamp_Power reflects an intentional, tagged upstream version rather than in-progress work on `main`.

#### Acceptance Criteria

1. WHEN the Maintainer initiates an initial build, THE Version_Resolver SHALL determine the latest Template_Release as the published, non-draft, non-prerelease release carrying the highest semantic-version tag among the Template_Plugin published releases.
2. WHEN the Maintainer initiates an update build, THE Version_Resolver SHALL determine the latest Template_Release as the published, non-draft, non-prerelease release carrying the highest semantic-version tag among the Template_Plugin published releases.
3. THE Version_Resolver SHALL source template content from the resolved Template_Release tag and SHALL NOT source template content from the `main` branch HEAD.
4. IF the Template_Plugin has no published, non-draft, non-prerelease release, THEN THE Version_Resolver SHALL report an error indicating that no versioned release is available and SHALL halt the build without producing any build artifact.
5. WHEN the Version_Resolver resolves a Template_Release, THE Version_Resolver SHALL record the resolved Template_Release tag name so that later steps and generated artifacts can reference the exact resolved version.
6. IF the release-resolution query does not return a result within 30 seconds after 3 attempts, THEN THE Version_Resolver SHALL report an error indicating that release resolution failed (distinct from the no-release-available error) and SHALL halt the build without producing any build artifact.

### Requirement 2: Match the Power version to the template release version

**User Story:** As a Maintainer, I want the Bootcamp_Power version to equal the Template_Release version, so that a Bootcamper and Maintainer can tell at a glance which upstream release a given Power corresponds to.

#### Acceptance Criteria

1. WHEN the tooling produces a Bootcamp_Power from a resolved Template_Release, THE Create_Skill SHALL set the Bootcamp_Power version to a value that is character-for-character identical to the resolved Template_Release version string (e.g. resolved `0.5.1` yields Bootcamp_Power version `0.5.1`).
2. WHEN the tooling updates a Bootcamp_Power from a newer resolved Template_Release, THE Update_Skill SHALL set the Bootcamp_Power version to a value that is character-for-character identical to the newer resolved Template_Release version string.
3. IF, after a build, the Bootcamp_Power version string is not character-for-character identical to the resolved Template_Release version string, THEN THE Schema_Validator SHALL report a version-mismatch error that identifies both the Bootcamp_Power version and the resolved Template_Release version.
4. IF the Schema_Validator reports a version-mismatch error, THEN THE Schema_Validator SHALL prevent the release from being tagged and SHALL leave the existing Bootcamp_Power version and metadata unchanged.
5. WHEN the Create_Skill or the Update_Skill sets the Bootcamp_Power version, THE Bootcamp_Power SHALL record the corresponding resolved Template_Release version string in the Bootcamp_Power `plugin.json` `extensions` object under the reverse-domain namespace key `com.senzing.bootcamp` as the field `templateRelease`, and SHALL record that version string outside the fixed top-level field set defined by the Agent Plugins v1.0.0 plugin schema.

### Requirement 3: Single-sourced transformation contract

**User Story:** As a Maintainer, I want the create and update operations to use one shared set of transformation rules, so that the two operations never diverge in how they map the template to the Power.

#### Acceptance Criteria

1. THE Transformation_Contract SHALL define the mapping rules from Template_Plugin files to Bootcamp_Power files as a single shared source that is referenced, and not duplicated, by both the Create_Skill and the Update_Skill.
2. WHEN the Create_Skill transforms template content, THE Create_Skill SHALL apply the rules defined in the Transformation_Contract.
3. WHEN the Update_Skill transforms template content, THE Update_Skill SHALL apply the rules defined in the Transformation_Contract.
4. WHERE a transformation rule changes, THE Transformation_Contract SHALL be the only location requiring that change for both Create_Skill and Update_Skill to reflect it.
5. WHEN identical Template_Plugin content is provided to the Create_Skill and to the Update_Skill, THE Transformation_Contract SHALL produce byte-for-byte identical Bootcamp_Power output from both operations.
6. IF a Template_Plugin file provided to either the Create_Skill or the Update_Skill has no matching rule defined in the Transformation_Contract, THEN THE Transformation_Contract SHALL cause the operation to halt without producing Bootcamp_Power output for that file and SHALL return an error indication identifying the unmatched Template_Plugin file.

### Requirement 4: Initial creation of the Bootcamp Power

**User Story:** As a Maintainer, I want to generate an initial Bootcamp_Power from the latest template release, so that Bootcampers have an installable Power for that release.

#### Acceptance Criteria

1. WHEN the Maintainer runs the Create_Skill against a resolved Template_Release, THE Create_Skill SHALL produce a Bootcamp_Power at `powers/senzing-bootcamp/` in Agent_Plugins_Format that includes both a `plugin.json` file and an `mcp.json` file.
2. THE Create_Skill SHALL generate a `plugin.json` file for the Bootcamp_Power that conforms to the Agent Plugins v1.0.0 plugin schema.
3. THE Create_Skill SHALL generate an `mcp.json` file for the Bootcamp_Power that conforms to the Agent Plugins v1.0.0 MCP schema.
4. THE Create_Skill SHALL declare Apache-2.0 as the license of the Bootcamp_Power.
5. IF a Bootcamp_Power already exists at the target location when the Create_Skill runs, THEN THE Create_Skill SHALL report a conflict indicating the existing `powers/senzing-bootcamp/` location and SHALL require explicit Maintainer confirmation before modifying any existing content.
6. IF the Maintainer declines the overwrite confirmation, THEN THE Create_Skill SHALL terminate without modifying content at `powers/senzing-bootcamp/` and SHALL retain the existing Bootcamp_Power unchanged.
7. IF the Create_Skill runs against a Template_Release that cannot be resolved, THEN THE Create_Skill SHALL report an error indicating the Template_Release could not be resolved and SHALL NOT create or modify content at `powers/senzing-bootcamp/`.
8. IF generation of the Bootcamp_Power fails after partial content has been written, THEN THE Create_Skill SHALL report an error indicating the failure and SHALL NOT leave partially generated content at `powers/senzing-bootcamp/`.

### Requirement 5: Update propagation from a newer template release

**User Story:** As a Maintainer, I want to propagate a newer template release into the existing Bootcamp_Power, so that the Power stays current with low manual effort and preserves Kiro-specific adaptations.

#### Acceptance Criteria

1. WHEN the Maintainer runs the Update_Skill, THE Version_Resolver SHALL determine whether a Template_Release with a version identifier greater than the current Bootcamp_Power version identifier exists.
2. IF no Template_Release with a version identifier greater than the current Bootcamp_Power version exists, THEN THE Update_Skill SHALL report that the Bootcamp_Power is current and SHALL leave all Bootcamp_Power content unchanged.
3. WHEN a Template_Release with a version identifier greater than the current Bootcamp_Power version exists, THE Update_Skill SHALL re-run the Transformation_Contract against that Template_Release.
4. WHEN the Update_Skill produces updated content, THE Update_Skill SHALL present a reconciliation report that lists each added, modified, and removed item between the current Bootcamp_Power and the newly transformed content, and that lists each preserved Kiro-specific adaptation.
5. WHILE performing the update, THE Update_Skill SHALL preserve every Kiro-specific adaptation that has no corresponding item in the Template_Release, and SHALL leave those adaptations unchanged in the resulting Bootcamp_Power.
6. IF a Kiro-specific adaptation applies to an item that the newer Template_Release also changes, THEN THE Update_Skill SHALL retain the existing adaptation, SHALL flag the item as a conflict in the reconciliation report, and SHALL identify both the adaptation and the conflicting template change.
7. IF the re-run of the Transformation_Contract fails to complete, THEN THE Update_Skill SHALL leave the current Bootcamp_Power unchanged, SHALL make no changelog entry, and SHALL report a message indicating that the update did not complete.
8. WHEN the Update_Skill completes a successful update, THE Update_Skill SHALL record the change in a Bootcamp_Power changelog entry identifying the source Template_Release version identifier.

### Requirement 6: Manual testing gate before release

**User Story:** As a Maintainer, I want manual testing to be required and recorded before a release is published, so that a broken Bootcamp_Power is not tagged or distributed.

#### Acceptance Criteria

1. THE Test_Checklist SHALL define, as an ordered set of discrete steps each with an observable pass/fail outcome, the manual verification a Maintainer performs before tagging a Bootcamp_Power release, including local installation via the Kiro Powers "Add Custom Power" flow and running the Power in a fresh chat session (a chat session with no prior conversation history).
2. WHEN a Maintainer prepares a Bootcamp_Power release, THE Bootcamp_Power release process SHALL require recorded confirmation that every Test_Checklist step has a pass outcome before the release is tagged.
3. IF any Test_Checklist step does not have a recorded pass outcome, THEN THE Bootcamp_Power release process SHALL block tagging of the release.
4. THE Test_Checklist SHALL include a step that verifies the Bootcamp_Power establishes a connection to the Senzing_MCP_Server and that a Senzing_MCP_Server tool call returns a successful response.
5. THE Test_Checklist SHALL include a step that verifies, for each ported skill, that stating the skill's intended trigger phrase activates that skill.
6. WHEN a Maintainer records the outcome of a Test_Checklist step, THE Bootcamp_Power release process SHALL retain the recorded per-step outcomes so they can be reviewed for the tagged release.
7. THE Test_Checklist SHALL include a step that determines, by observing whether a hook definition bundled under the Bootcamp_Power `dev.kiro/hooks/` directory fires in an installed Power, whether Kiro loads hook definitions from that directory, and SHALL record the observed outcome.
8. THE Test_Checklist SHALL include a step that verifies each hook definition written into the Workspace_Hooks_Directory by the Hook_Installer fires on its declared trigger.
9. THE Test_Checklist SHALL include a step that runs the Hook_Installer twice against the same workspace and verifies that the second run leaves the Workspace_Hooks_Directory contents identical to the contents produced by the first run.
10. THE Test_Checklist SHALL include a step that follows the documented removal procedure and verifies that the procedure deletes exactly the files the Hook_Installer created and leaves every other Workspace_Hooks_Directory file unchanged.
11. THE Test_Checklist SHALL include a step that verifies the `PreToolUse` matcher pattern used by the shipped hook definitions matches the tool names Kiro reports for its file-write tools.
12. THE Test_Checklist SHALL require that the Bootcamp_Power installation step, the hook-firing verification step, and the ported-script execution step each be performed on every Supported_Platform, and SHALL record a per-platform outcome for each of those three steps.
13. THE Test_Checklist SHALL include a step that verifies a Hook_Command_String whose resolved interpreter path or resolved script path contains a space character invokes the ported script correctly.

### Requirement 7: Behavioral parity of the bootcamp experience

**User Story:** As a Bootcamper, I want the Kiro bootcamp to behave like the Claude bootcamp, so that I receive the same guided learning experience.

#### Acceptance Criteria

1. THE Bootcamp_Power SHALL provide exactly one ported bootcamp skill for each bootcamp skill directory present in the resolved Template_Release.
2. THE Bootcamp_Power SHALL NOT provide a ported bootcamp skill that has no corresponding bootcamp skill directory in the resolved Template_Release, WHERE command-derived skills are governed by Requirement 9 and client-adaptation skills are governed by the Requirement 7 hook-parity criteria.
3. WHEN a Bootcamper progresses through the bootcamp, THE Bootcamp_Power SHALL present its skills in the same order as the bootcamp progression sequence defined by the Template_Release, from onboarding through graduation.
4. THE Bootcamp_Power SHALL express every Template_Release hook-enforced behavior as an instruction within the skill that owns that behavior, so that a Bootcamper receives the complete bootcamp experience with zero hook definitions installed (Tier 1 baseline parity).
5. THE Bootcamp_Power SHALL ship a Kiro hook definition, as a skill asset, for each Template_Release hook-enforced behavior that has an equivalent Kiro trigger (Tier 2 mechanical enforcement).
6. WHEN the Bootcamper grants explicit consent to install hook definitions, THE Hook_Installer SHALL write the shipped Kiro hook definitions into the Workspace_Hooks_Directory, and SHALL write the interpreter path and the script path of each Hook_Command_String as required by Requirement 16.
7. WHEN the Hook_Installer requests Bootcamper consent, THE Hook_Installer SHALL present the full path of each file it will write and SHALL present those paths before writing any of those files.
8. WHEN the Hook_Installer runs against a Workspace_Hooks_Directory that already contains the shipped hook definitions, THE Hook_Installer SHALL leave the Workspace_Hooks_Directory contents identical to the contents produced by the preceding successful install.
9. THE Hook_Installer SHALL name each file it writes into the Workspace_Hooks_Directory with a `senzing-bootcamp-` filename prefix, so that every installed file is attributable to the Bootcamp_Power.
10. THE Bootcamp_Power SHALL document a removal step that deletes exactly the files the Hook_Installer created and SHALL leave every other Workspace_Hooks_Directory file unchanged.
11. IF the Bootcamper declines to install hook definitions, THEN THE Bootcamp_Power SHALL deliver the complete bootcamp experience through the Tier 1 skill instructions and SHALL write no file into the Workspace_Hooks_Directory.
12. THE Bootcamp_Power SHALL place the same Kiro hook definitions under the `dev.kiro/hooks/` directory for forward compatibility (Tier 3), and SHALL deliver every hook-enforced behavior through Tier 1 or Tier 2 independently of whether Kiro loads the `dev.kiro/hooks/` directory.
13. WHERE Kiro provides no trigger equivalent to a Template_Release hook trigger (Claude `PreCompact` and `SessionEnd`), THE Bootcamp_Power SHALL express that behavior as an advisory instruction within the owning skill and SHALL document the parity gap.
14. WHERE Kiro provides a trigger equivalent that cannot block an action (Kiro `Stop`), THE Bootcamp_Power SHALL express the corresponding Template_Release blocking behavior as an advisory instruction within the owning skill and SHALL document the parity gap.
15. THE Bootcamp_Power SHALL preserve, for each bootcamp skill, the learning objectives, instructional steps, and exercises defined by the corresponding Template_Release skill.

### Requirement 8: Skill mapping and preservation of cross-references

**User Story:** As a Maintainer, I want the ported skills to keep their directory layout and relative links, so that the heavily cross-referenced bootcamp content continues to resolve correctly.

#### Acceptance Criteria

1. WHEN porting a bootcamp skill, THE Create_Skill SHALL place the ported skill at `skills/<skill-name>/SKILL.md` within the Bootcamp_Power, where `<skill-name>` matches the source skill's directory name exactly.
2. THE Transformation_Contract SHALL preserve the source skill directory layout such that every relative cross-reference between skills points to the same target file location it referenced before transformation.
3. WHEN the Schema_Validator runs, THE Schema_Validator SHALL verify that every relative cross-reference between skills resolves to an existing file within the Bootcamp_Power.
4. IF a relative cross-reference between skills cannot be resolved to an existing file after transformation, THEN THE Schema_Validator SHALL report the unresolved reference identifying its source file and target path, and SHALL prevent the release from being tagged until zero unresolved references remain.
5. WHEN adapting a skill's frontmatter, THE Transformation_Contract SHALL populate the Agent_Plugins_Format fields name, description, and license, and SHALL reject frontmatter where any of these three fields is empty or absent.
6. THE Transformation_Contract SHALL adapt each skill's frontmatter so that the description field contains the source skill's trigger phrase.

### Requirement 9: Represent template commands as trigger-phrase skills

**User Story:** As a Bootcamper, I want to start, graduate, and give feedback through natural trigger phrases, so that I can use the bootcamp without plugin-level slash commands that Kiro does not support.

#### Acceptance Criteria

1. THE Bootcamp_Power SHALL represent each of the three Template_Release commands, start-bootcamp, graduate, and bootcamp-feedback, as exactly one corresponding skill, producing three command-derived skills in total.
2. THE Bootcamp_Power SHALL include exactly one trigger phrase in the description of each command-derived skill.
3. THE Bootcamp_Power SHALL ensure each command-derived skill's trigger phrase is distinct from the trigger phrases of the other command-derived skills, so that no single Bootcamper statement matches more than one command-derived skill.
4. WHEN a Bootcamper states the trigger phrase for a command-derived skill, THE Bootcamp_Power SHALL activate the corresponding skill.
5. IF a Bootcamper statement matches no command-derived skill trigger phrase, THEN THE Bootcamp_Power SHALL activate none of the command-derived skills.

### Requirement 10: Port scripts and rewrite root path token

**User Story:** As a Maintainer, I want template scripts ported and their path references rewritten, so that scripts run correctly from within the Bootcamp_Power.

#### Acceptance Criteria

1. THE Transformation_Contract SHALL place every ported template script together under the `scripts/` directory of a single owning skill at `skills/<owning-skill-name>/scripts/` within the Bootcamp_Power, so that a same-directory Python module import between two ported scripts resolves, and SHALL preserve each script's file name and relative sub-structure as they appeared under the template source.
2. WHERE a ported script contains one or more occurrences of the template root path token `${CLAUDE_PLUGIN_ROOT}`, THE Transformation_Contract SHALL rewrite every occurrence to the Plugin_Root_Token `${PLUGIN_ROOT}` such that zero occurrences of `${CLAUDE_PLUGIN_ROOT}` remain in the ported script.
3. THE Transformation_Contract SHALL preserve each vendored script asset required by a ported script (for example `d3.v7.min.js`) with byte-for-byte identical content to the template source and place it at the same relative location under `skills/<owning-skill-name>/scripts/`.
4. IF a ported script references a vendored asset that is absent from the template source, THEN THE Transformation_Contract SHALL halt the port for that script and produce an error indication identifying the referenced script and the missing vendored asset, and SHALL leave the destination `skills/<owning-skill-name>/scripts/` unchanged for that script.
5. WHERE a ported script was invoked by a template hook, THE Transformation_Contract SHALL rewire that script's invocation according to the three-tier hook parity strategy defined in Requirement 7, SHALL express the template's exec-form command and argument array as the single Hook_Command_String that the Kiro hook schema accepts, SHALL preserve the Template_Invariant `INV-052` guarantee that hook execution carries no shell dependency on any Supported_Platform by way of the install-time interpreter resolution required by Requirement 16, and SHALL NOT substitute a bare interpreter name for the resolved interpreter path.
6. IF ported scripts are placed such that a same-directory module import between two of those scripts no longer resolves, THEN THE Schema_Validator SHALL report the broken import identifying the importing script and the imported module name, and SHALL prevent the release from being tagged.

### Requirement 11: Mandatory Senzing MCP server dependency

**User Story:** As a Bootcamper, I want the Power to connect to the Senzing MCP server, so that the bootcamp exercises function against live Senzing capabilities.

#### Acceptance Criteria

1. THE Bootcamp_Power `mcp.json` SHALL declare the Senzing_MCP_Server with the URL exactly equal to `https://mcp.senzing.com/mcp` and the transport type exactly equal to `streamable-http`.
2. WHEN the Transformation_Contract translates the template MCP declaration to the Agent_Plugins_Format, THE Transformation_Contract SHALL include the `$schema` field, the URL `https://mcp.senzing.com/mcp`, and the transport type `streamable-http` in the output.
3. IF the Bootcamp_Power `mcp.json` does not declare the Senzing_MCP_Server, THEN THE Schema_Validator SHALL report an error indicating the missing mandatory dependency and SHALL prevent the release from being tagged, leaving the existing release tags unchanged.
4. IF the declared Senzing_MCP_Server URL is not exactly `https://mcp.senzing.com/mcp` or the transport type is not exactly `streamable-http`, THEN THE Schema_Validator SHALL report an error indicating the invalid value and SHALL prevent the release from being tagged, leaving the existing release tags unchanged.
5. IF the translated Agent_Plugins_Format output omits the `$schema` field, THEN THE Schema_Validator SHALL report an error indicating the missing `$schema` field and SHALL prevent the release from being tagged, leaving the existing release tags unchanged.

### Requirement 12: Port documentation and rewrite model guidance

**User Story:** As a Bootcamper, I want documentation and model guidance written for Kiro, so that guidance matches the environment I am using.

#### Acceptance Criteria

1. WHEN the transformation executes, THE Transformation_Contract SHALL port every template documentation example and reference asset into the Bootcamp_Power, retaining each as an embedded asset or an explicit reference link.
2. WHERE ported documentation contains Claude-specific model guidance (defined as any reference to a Claude subscription plan such as Claude Max, a Claude model name such as Sonnet, or a Claude effort setting), THE Transformation_Contract SHALL replace each such reference with the corresponding Kiro model name and Kiro effort setting.
3. IF ported documentation retains one or more Claude-specific model references after the transformation completes, THEN THE Schema_Validator SHALL report each residual reference, including its source document and location within that document, for Maintainer review.
4. IF one or more residual Claude-specific model references are reported, THEN THE Schema_Validator SHALL flag the transformation outcome as incomplete rather than successful.

### Requirement 13: Schema and frontmatter validation

**User Story:** As a Maintainer, I want produced files validated against the Agent Plugins format, so that the Bootcamp_Power installs and loads correctly in Kiro.

#### Acceptance Criteria

1. WHEN the Create_Skill or Update_Skill produces a Bootcamp_Power, THE Schema_Validator SHALL validate the `plugin.json` file against the Agent Plugins v1.0.0 plugin schema and SHALL record a pass or fail result for that file.
2. WHEN the Create_Skill or Update_Skill produces a Bootcamp_Power, THE Schema_Validator SHALL validate the `mcp.json` file against the Agent Plugins v1.0.0 MCP schema and SHALL record a pass or fail result for that file.
3. WHEN the Create_Skill or Update_Skill produces a Bootcamp_Power, THE Schema_Validator SHALL validate that each `SKILL.md` frontmatter satisfies the Agent_Plugins_Format skill frontmatter rules and SHALL record a pass or fail result for each `SKILL.md` file.
4. IF any produced file fails schema or frontmatter validation, THEN THE Schema_Validator SHALL report each failure identifying the offending file and the specific schema or frontmatter rule violated, SHALL leave the produced files unchanged, and SHALL prevent the release from being tagged.
5. WHEN all produced `plugin.json`, `mcp.json`, and `SKILL.md` files pass schema and frontmatter validation, THE Schema_Validator SHALL record an overall validation-passed result and SHALL permit the release to be tagged.

### Requirement 14: Artifact location and repository conventions

**User Story:** As a Maintainer, I want the Power and the tooling to live in known locations in this repository, so that the project structure is predictable.

#### Acceptance Criteria

1. WHEN the Create_Skill generates the Bootcamp_Power, THE Create_Skill SHALL write all Bootcamp_Power artifacts to the `powers/senzing-bootcamp/` directory within this repository. *(Open decision: Location.)*
2. THE maintainer tooling, comprising the Create_Skill, the Update_Skill, and the Transformation_Contract, SHALL reside within this repository. *(Open decision: Location.)*
3. THE Bootcamp_Power SHALL include an Apache-2.0 license declaration that matches the Apache-2.0 license declared at this repository's root.
4. IF the `powers/senzing-bootcamp/` directory does not exist WHEN the Create_Skill generates the Bootcamp_Power, THEN THE Create_Skill SHALL create the directory before writing the Bootcamp_Power artifacts. *(Open decision: Location.)*
5. IF the Create_Skill cannot create or write to the `powers/senzing-bootcamp/` directory, THEN THE Create_Skill SHALL abort the write operation, leave the repository contents unchanged, and report an error message indicating the write failure. *(Open decision: Location.)*

### Requirement 15: Kiro construction takes precedence over template invariants

**User Story:** As a Maintainer, I want correct Kiro and Agent Plugins construction to override any conflicting Claude-authored template invariant, while never discarding an invariant that encodes a portability or correctness guarantee, so that the Bootcamp_Power is built correctly without silently losing protections.

#### Acceptance Criteria

1. THE Transformation_Contract SHALL treat every Template_Invariant as non-normative with respect to Bootcamp_Power packaging, Bootcamp_Power structure, and Bootcamp_Power hook definition format.
2. WHERE honoring a Template_Invariant would conflict with the Agent Plugins v1.0.0 specification or with a documented Kiro mechanism, THE Transformation_Contract SHALL implement the construction that the specification or the mechanism requires and SHALL discount the conflicting Template_Invariant.
3. WHERE a Template_Invariant states a portability, security, or correctness guarantee using host-specific vocabulary, THE Transformation_Contract SHALL preserve that guarantee restated in terms of Kiro mechanisms and SHALL retain that Template_Invariant as honored.
4. WHEN the Transformation_Contract discounts a Template_Invariant, THE Transformation_Contract SHALL record an Invariant_Discount_Register entry identifying the Template_Invariant identifier, the conflicting Agent Plugins or Kiro constraint, and the resolution applied.
5. IF an Invariant_Discount_Register entry omits the Template_Invariant identifier, the conflicting constraint, or the resolution applied, THEN THE Schema_Validator SHALL report the incomplete entry and SHALL prevent the release from being tagged.
6. WHERE the no-shell-dependency guarantee of Template_Invariant `INV-052` is preserved under Requirement 16 rather than discounted, THE Invariant_Discount_Register SHALL exclude any entry for Template_Invariant `INV-052`.
7. THE Transformation_Contract SHALL preserve every inline `INV-NNN` citation appearing in ported bootcamp prose verbatim, including a citation of a discounted Template_Invariant.
8. THE Schema_Validator SHALL treat an inline `INV-NNN` citation in ported bootcamp prose as compliant content rather than as a residual Claude-specific reference under Requirement 12.
9. THE Bootcamp_Power SHALL satisfy every other requirement while excluding the Template_Plugin invariant registry, and THE Version_Resolver SHALL source every Template_Invariant definition it uses from the resolved Template_Release.
10. WHEN a Template_Release with a version identifier greater than the current Bootcamp_Power version identifier changes the text of a Template_Invariant recorded in the Invariant_Discount_Register, THE Update_Skill SHALL flag that Invariant_Discount_Register entry in the reconciliation report for Maintainer re-evaluation.
11. THE Invariant_Discount_Register SHALL reside within the Transformation_Contract, so that the Create_Skill and the Update_Skill apply an identical set of discounts.

### Requirement 16: Cross-platform operation

**User Story:** As a Bootcamper, I want the bootcamp to work on my operating system, whether that is Linux, macOS, or Windows, so that my platform does not exclude me.

#### Acceptance Criteria

1. THE Bootcamp_Power SHALL operate on each Supported_Platform.
2. WHERE the executable name `python3` is absent from the PATH of a Supported_Platform, THE Bootcamp_Power SHALL operate on that Supported_Platform.
3. WHEN the Hook_Installer writes a hook definition, THE Hook_Installer SHALL resolve the absolute filesystem path of the Python interpreter executing the Hook_Installer and SHALL write that absolute path into the Hook_Command_String in place of a bare interpreter name.
4. WHEN the Hook_Installer writes a Hook_Command_String, THE Hook_Installer SHALL quote the interpreter path and the script path such that a path containing a space character is invoked correctly on each Supported_Platform.
5. THE Bootcamp_Power SHALL restrict every Hook_Command_String to an interpreter path followed by script arguments, excluding any command-chaining operator, pipe, redirection operator, and shell builtin invocation.
6. IF a Hook_Command_String contains a command-chaining operator, a pipe, a redirection operator, or a shell builtin invocation, THEN THE Schema_Validator SHALL report the offending hook definition and the offending construct and SHALL prevent the release from being tagged.
7. WHERE a ported script requires a runtime other than the resolved Python interpreter, THE Bootcamp_Power SHALL treat that runtime as optional and SHALL continue operating with reduced capability while that runtime is absent.
8. THE Transformation_Contract SHALL declare, within this repository, line-ending normalization such that every ported Bootcamp_Power file retains LF line endings when this repository is checked out on each Supported_Platform.
9. IF a checked-out Bootcamp_Power file's content hash differs from the content hash recorded for that file in the Build_Manifest, THEN THE Schema_Validator SHALL report the mismatch identifying that file and SHALL prevent the release from being tagged.
