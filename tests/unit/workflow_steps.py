"""Load a reusable workflow and run one of its ``run:`` steps as the runner does.

A contract test that only reads YAML proves a step exists; running the script
the workflow ships, with the ``env:`` the workflow gives it, proves what it does.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, cast

import yaml

WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"


def load(name: str) -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text("utf-8")))


def call(name: str) -> dict[str, Any]:
    workflow = load(name)
    return cast(dict[str, Any], workflow.get("on", workflow.get(True))["workflow_call"])


def jobs(name: str) -> dict[str, dict[str, Any]]:
    return cast(dict[str, dict[str, Any]], load(name)["jobs"])


def steps(name: str, job: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], jobs(name)[job].get("steps", []))


def step(name: str, job: str, title: str) -> dict[str, Any]:
    return next(s for s in steps(name, job) if s.get("name") == title)


def run(
    name: str,
    job: str,
    title: str,
    env: dict[str, str],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    """Run the step's script with ``bash -eo pipefail``, the runner's ``shell: bash``."""
    script = cwd / ".step.sh"
    script.write_text(cast(str, step(name, job, title)["run"]), encoding="utf-8")
    return subprocess.run(
        ("bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)),
        cwd=cwd,
        env={"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", str(cwd)), **env},
        capture_output=True,
        text=True,
        check=False,
    )
