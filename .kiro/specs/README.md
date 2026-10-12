# `.kiro/specs/` — a frozen, read-only archive

⛔ **Nothing here is the live plan, and nothing new may be written here** (KINV-014).

`senzing-bootcamp-power/` holds the original requirements, design and task list this port was
built from. It is kept because the code still cites it: `R<n> AC<m>` references throughout
`tools/bootcamp-transform/` and the maintainer skills point at `requirements.md`, and deleting the
file would leave every one of those citations pointing at nothing. Read it for **why** the
transformation engine is shaped the way it is. Do not read it for what to build next.

Work is tracked as **GitHub issues** in
[docktermj/senzing-bootcamp-kiro-power-development](https://github.com/docktermj/senzing-bootcamp-kiro-power-development/issues),
family-wide (FAMILY_WORKFLOW R5). The spec-writing router `feedback-to-specs` was retired in #25;
`feedback-to-issues` and `implement-github-issue` replace it. The task list's checkboxes record
what was done when the spec was closed and are not maintained.

The frozen set is pinned by name in
`tools/bootcamp-transform/tests/test_specs_are_frozen.py`, which fails on any file added,
removed, or renamed under this directory and on any operation in this repository that names a
spec file as something it writes. Correcting a typo in a frozen file is allowed; changing what a
requirement says is not — record that as an issue and, if it establishes a guarantee, a `KINV`.
