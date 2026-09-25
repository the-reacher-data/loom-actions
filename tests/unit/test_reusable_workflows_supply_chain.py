"""Supply-chain rules every new reusable workflow keeps.

A caller pins these workflows by SHA; that pin only holds if every action they
run is pinned too, no input reaches a shell through an expression, the
checkout token is not left on disk, and each job asks for exactly the
permissions it uses.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"
REUSABLES = ("node-ci", "repo-security", "pages", "image-release")
PINNED = re.compile(r"^[^@]+@[0-9a-f]{40}$")
PINNED_IMAGE = re.compile(r"^docker://[^@]+@sha256:[0-9a-f]{64}$")


def _workflow(name: str) -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text("utf-8")))


def _jobs(name: str) -> dict[str, dict[str, Any]]:
    return cast(dict[str, dict[str, Any]], _workflow(name)["jobs"])


def _steps(name: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (job_name, step)
        for job_name, job in _jobs(name).items()
        for step in cast(list[dict[str, Any]], job.get("steps", []))
    ]


@pytest.mark.parametrize("name", REUSABLES)
class TestSupplyChain:
    def test_it_is_only_callable(self, name: str) -> None:
        workflow = _workflow(name)
        assert list(workflow.get("on", workflow.get(True))) == ["workflow_call"]

    def test_every_action_is_pinned_by_commit(self, name: str) -> None:
        for job, step in _steps(name):
            if "uses" in step:
                uses = cast(str, step["uses"])
                assert PINNED.match(uses) or PINNED_IMAGE.match(uses), f"{job}: {uses}"

    def test_every_action_names_its_version(self, name: str) -> None:
        text = (WORKFLOWS / f"{name}.yml").read_text("utf-8")
        for line in text.splitlines():
            if re.match(r"\s*(- )?uses: ", line):
                assert re.search(r"@\S+ # v\d+\.\d+\.\d+$", line), line.strip()

    def test_no_expression_is_interpolated_into_a_script(self, name: str) -> None:
        for job, step in _steps(name):
            assert "${{" not in cast(str, step.get("run", "")), f"{job}: {step.get('name')}"

    def test_checkouts_do_not_persist_the_token(self, name: str) -> None:
        checkouts = [s for _, s in _steps(name) if "actions/checkout" in str(s.get("uses", ""))]
        assert checkouts
        assert all(s["with"]["persist-credentials"] is False for s in checkouts)

    def test_every_job_declares_its_permissions_and_a_timeout(self, name: str) -> None:
        for job_name, job in _jobs(name).items():
            assert "permissions" in job, job_name
            assert "timeout-minutes" in job, job_name

    def test_the_concurrency_is_left_to_the_caller(self, name: str) -> None:
        assert "concurrency" not in _workflow(name)

    def test_every_run_uses_bash(self, name: str) -> None:
        assert _workflow(name)["defaults"]["run"]["shell"] == "bash"


@pytest.mark.parametrize("name", ("node-ci", "repo-security", "pages"))
def test_only_the_image_release_can_mint_an_identity(name: str) -> None:
    for job_name, job in _jobs(name).items():
        assert "id-token" not in job["permissions"], job_name
        assert "packages" not in job["permissions"], job_name


@pytest.mark.parametrize("name", ("pages", "image-release"))
def test_a_single_job_workflow_needs_no_gate(name: str) -> None:
    assert len(_jobs(name)) == 1


@pytest.mark.parametrize("name", ("node-ci", "repo-security"))
def test_every_gate_waits_for_every_other_job(name: str) -> None:
    jobs = _jobs(name)
    gate = jobs["gate"]
    assert set(gate["needs"]) == set(jobs) - {"gate"}
    assert gate["if"] == "${{ always() }}"
    assert gate["permissions"] == {}
    script = cast(str, gate["steps"][0]["run"])
    assert '"failure"' in script
    assert '"cancelled"' in script


CALLER_CODE = re.compile(r"\b(npm|npx)\b|bash -euo pipefail -c ")


@pytest.mark.parametrize("name", REUSABLES)
def test_no_job_that_runs_the_callers_code_sees_a_secret(name: str) -> None:
    for job_name, job in _jobs(name).items():
        runs = " ".join(str(step.get("run", "")) for step in job.get("steps", []))
        if CALLER_CODE.search(runs):
            assert "secrets." not in json.dumps(job), job_name
