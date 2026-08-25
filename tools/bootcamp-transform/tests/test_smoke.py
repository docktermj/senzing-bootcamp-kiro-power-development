"""Placeholder smoke test: the runner is green before any component exists.

This file verifies only that the scaffolding from task 1.1 is in place and that
the Hypothesis floor is active. The substantive structural assertions live in
`test_structure.py`.
"""

from __future__ import annotations

from hypothesis import settings

from conftest import MAX_EXAMPLES_FLOOR, REPO_ROOT

SCAFFOLD_DIRECTORIES = [
    "tools/bootcamp-transform",
    "tools/bootcamp-transform/tests",
    "tools/bootcamp-transform/templates",
    "tools/bootcamp-transform/templates/kiro-owned",
    "docs",
    "docs/test-records",
]


def test_scaffold_directories_exist():
    missing = [d for d in SCAFFOLD_DIRECTORIES if not (REPO_ROOT / d).is_dir()]
    assert missing == [], f"missing scaffold directories: {missing}"


def test_pyproject_declares_pinned_dev_dependencies():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for package in ("pytest", "hypothesis", "pyyaml", "jsonschema", "jinja2"):
        assert f'"{package}==' in pyproject, f"{package} is not pinned in pyproject.toml"


def test_hypothesis_profile_enforces_the_example_floor():
    assert settings().max_examples >= MAX_EXAMPLES_FLOOR
