"""Composites a caller pins by SHA must pin what they run in turn.

A caller's SHA pin on ``quality-report`` or ``setup-uv`` means nothing while
those composites resolve ``setup-python`` and ``setup-uv`` through a floating
tag, so every ``uses`` in them names a full commit SHA.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ACTIONS = Path(__file__).parents[2] / "actions"
PINNED = re.compile(r"^[^@]+@[0-9a-f]{40}$")
COMPOSITES = ("python/quality-report", "core/setup-uv")


def _uses(composite: str) -> list[str]:
    action = cast(
        dict[str, Any],
        yaml.safe_load((ACTIONS / composite / "action.yml").read_text(encoding="utf-8")),
    )
    return [step["uses"] for step in action["runs"]["steps"] if "uses" in step]


@pytest.mark.parametrize("composite", COMPOSITES)
def test_every_action_a_composite_runs_is_pinned_by_sha(composite: str) -> None:
    uses = _uses(composite)
    assert uses, f"{composite} runs no action"
    assert [ref for ref in uses if not PINNED.match(ref)] == []
