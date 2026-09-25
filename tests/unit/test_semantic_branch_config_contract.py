"""Both release composites accept the file their branch rules are read from.

``plan-release`` reads the rules from ``pyproject.toml`` unless told otherwise,
and passes the choice to both of its planner runs, so the plan an operator reads
and the version the action returns come from the same rules.
``versioning-branch-semantic`` already reads a ``config-file``, so an empty
``semantic-branch-config`` keeps reading the rules from it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

RELEASE = Path(__file__).parents[2] / "actions" / "release"
FLAG = '--semantic-branch-config "${SEMANTIC_BRANCH_CONFIG}"'


def _action(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        yaml.safe_load((RELEASE / name / "action.yml").read_text(encoding="utf-8")),
    )


def _step(name: str, step_id: str) -> dict[str, Any]:
    return next(step for step in _action(name)["runs"]["steps"] if step.get("id") == step_id)


def test_plan_release_reads_pyproject_unless_told_otherwise() -> None:
    declared = _action("plan-release")["inputs"]["semantic-branch-config"]
    assert declared["required"] is False
    assert declared["default"] == "pyproject.toml"


def test_both_planner_runs_read_the_same_rules() -> None:
    plan = _step("plan-release", "plan")
    run = cast(str, plan["run"])
    assert plan["env"]["SEMANTIC_BRANCH_CONFIG"] == "${{ inputs.semantic-branch-config }}"
    assert run.count("plan_release.py") == 2
    assert run.count(FLAG) == 2


def test_versioning_reads_the_rules_from_config_file_unless_told_otherwise() -> None:
    declared = _action("versioning-branch-semantic")["inputs"]["semantic-branch-config"]
    assert declared["required"] is False
    assert declared["default"] == ""


def test_versioning_passes_the_rules_file_to_the_cli() -> None:
    calc = _step("versioning-branch-semantic", "calc")
    assert calc["env"]["SEMANTIC_BRANCH_CONFIG"] == "${{ inputs.semantic-branch-config }}"
    assert FLAG in cast(str, calc["run"])
