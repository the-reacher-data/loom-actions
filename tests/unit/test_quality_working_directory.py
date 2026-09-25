"""``quality-report`` can run on a project that lives in a subdirectory.

A monorepo caller passes ``working-directory``: every check and the report run
there, so ``src-dir``, ``test-dir`` and ``test-results-dir`` are relative to it.
The report paths the action returns stay usable from the workspace root, and
with the default ``.`` they are exactly the paths it returned before.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ACTION = Path(__file__).parents[2] / "actions" / "python" / "quality-report" / "action.yml"


def _action() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(ACTION.read_text(encoding="utf-8")))


def _run_steps() -> list[dict[str, Any]]:
    return [step for step in _action()["runs"]["steps"] if "run" in step]


def _path_prefix_block() -> str:
    """Return the shell that computes the report path prefix, dedented."""
    build = next(step for step in _run_steps() if step.get("id") == "build")
    match = re.search(
        r"^PATH_PREFIX=\"\"\n.*?^echo \"path_prefix=.*?\n",
        cast(str, build["run"]),
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "the build step computes no path prefix"
    return match.group(0)


def _prefix(working_directory: str, tmp_path: Path) -> str:
    outputs = tmp_path / "outputs.txt"
    script = (
        "set -euo pipefail\n"
        f'WORKING_DIRECTORY="{working_directory}"\n'
        f'GITHUB_OUTPUT="{outputs}"\n'
        f"{_path_prefix_block()}"
    )
    completed = subprocess.run(("bash", "-c", script), capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    return outputs.read_text(encoding="utf-8").removeprefix("path_prefix=").removesuffix("\n")


def test_working_directory_is_optional_and_defaults_to_the_workspace() -> None:
    declared = _action()["inputs"]["working-directory"]
    assert declared["required"] is False
    assert declared["default"] == "."


def test_every_run_step_runs_in_the_working_directory() -> None:
    steps = _run_steps()
    assert steps
    assert all(step.get("working-directory") == "${{ inputs.working-directory }}" for step in steps)


@pytest.mark.parametrize("output", ["report-file", "summary-file"])
def test_report_paths_are_prefixed_by_the_working_directory(output: str) -> None:
    value = cast(str, _action()["outputs"][output]["value"])
    assert value.startswith("${{ steps.build.outputs.path_prefix }}")


@pytest.mark.parametrize("working_directory", [".", "./", ""])
def test_the_workspace_itself_adds_no_prefix(working_directory: str, tmp_path: Path) -> None:
    assert _prefix(working_directory, tmp_path) == ""


@pytest.mark.parametrize(
    "working_directory", ["examples/sample_project", "examples/sample_project/"]
)
def test_a_subdirectory_prefixes_the_report_paths(working_directory: str, tmp_path: Path) -> None:
    assert _prefix(working_directory, tmp_path) == "examples/sample_project/"
