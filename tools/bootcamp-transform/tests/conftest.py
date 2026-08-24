"""Shared pytest and Hypothesis configuration for the bootcamp transform engine.

The design fixes 100 examples as the *floor* for every property test
(Testing Strategy, layer 1). The `bootcamp` profile registered here supplies
that floor as the default; an individual property test may raise it with its own
`@settings(max_examples=...)`, but nothing lowers it.

`HYPOTHESIS_MAX_EXAMPLES` can raise the floor for a long soak run
(`HYPOTHESIS_MAX_EXAMPLES=1000 pytest --no-header -q`); a value below the floor
is ignored rather than honored.
"""

from __future__ import annotations

import os
from pathlib import Path

from hypothesis import HealthCheck, settings

#: The design's minimum example count per property test.
MAX_EXAMPLES_FLOOR = 100

#: Repository root, resolved from this file rather than the current directory so
#: tests locate committed artifacts no matter where pytest is invoked from.
REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_max_examples() -> int:
    """Return the effective example count: the floor, or higher if requested."""
    requested = os.environ.get("HYPOTHESIS_MAX_EXAMPLES")
    if not requested:
        return MAX_EXAMPLES_FLOOR
    try:
        return max(MAX_EXAMPLES_FLOOR, int(requested))
    except ValueError:
        return MAX_EXAMPLES_FLOOR


settings.register_profile(
    "bootcamp",
    max_examples=_resolve_max_examples(),
    # Several properties build real directory trees and swap them, so wall-clock
    # time per example is not a correctness signal.
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    print_blob=True,
)

settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "bootcamp"))
