from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "python-service-ci.yml"
PINNED = re.compile(r"^[^@]+@[0-9a-f]{40}$")
SCANNER_JOB_INPUT = {"sonar": "inputs.sonar", "dependencies": "inputs.snyk"}


def _workflow() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")))


def _call() -> dict[str, Any]:
    workflow = _workflow()
    return cast(dict[str, Any], workflow.get("on", workflow.get(True))["workflow_call"])


def _jobs() -> dict[str, dict[str, Any]]:
    return cast(dict[str, dict[str, Any]], _workflow()["jobs"])


def _steps(job: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], _jobs()[job].get("steps", []))


def _all_steps() -> list[tuple[str, dict[str, Any]]]:
    return [(name, step) for name in _jobs() for step in _steps(name)]


class TestScannersAreOptIn:
    @pytest.mark.parametrize("name", ["codecov", "sonar", "snyk"])
    def test_off_unless_the_caller_asks(self, name: str) -> None:
        declared = _call()["inputs"][name]
        assert declared["type"] == "boolean"
        assert declared["default"] is False
        assert declared["required"] is False

    @pytest.mark.parametrize("secret", ["CODECOV_TOKEN", "SONAR_TOKEN", "SNYK_TOKEN"])
    def test_no_secret_is_required(self, secret: str) -> None:
        assert _call()["secrets"][secret]["required"] is False

    @pytest.mark.parametrize(("job", "flag"), SCANNER_JOB_INPUT.items())
    def test_a_scanner_job_runs_only_when_turned_on(self, job: str, flag: str) -> None:
        assert flag in cast(str, _jobs()[job]["if"])

    def test_codecov_steps_run_only_when_turned_on(self) -> None:
        codecov = [s for s in _steps("report") if "codecov" in str(s.get("uses", "")).lower()]
        assert len(codecov) == 2
        assert all("inputs.codecov" in cast(str, s["if"]) for s in codecov)

    @pytest.mark.parametrize(
        ("job", "step", "scanner"),
        [
            ("sonar", "Require the SonarQube configuration", "sonarqube-scan-action"),
            ("dependencies", "Require the Snyk token", "snyk/actions/setup"),
        ],
    )
    def test_a_scanner_turned_on_without_its_secret_fails_first(
        self, job: str, step: str, scanner: str
    ) -> None:
        steps = _steps(job)
        guard = next(i for i, s in enumerate(steps) if s.get("name") == step)
        scan = next(i for i, s in enumerate(steps) if scanner in str(s.get("uses", "")))
        assert "if" not in steps[guard]
        assert "exit 1" in cast(str, steps[guard]["run"])
        assert guard < scan

    @pytest.mark.parametrize("job", SCANNER_JOB_INPUT)
    def test_a_fork_pull_request_skips_secret_scanners(self, job: str) -> None:
        assert "head.repo.full_name == github.repository" in cast(str, _jobs()[job]["if"])


class TestNothingIsPublished:
    def test_no_step_pushes_or_uploads_to_an_index(self) -> None:
        for job, step in _all_steps():
            uses = str(step.get("uses", ""))
            assert "pypi-publish" not in uses, job
            assert "aws-actions" not in uses, job
            assert step.get("with", {}).get("push") in (None, False), job

    def test_no_job_can_mint_a_cloud_identity(self) -> None:
        for name, job in _jobs().items():
            assert "id-token" not in job.get("permissions", {}), name


class TestSupplyChain:
    def test_every_action_is_pinned_by_commit(self) -> None:
        for job, step in _all_steps():
            if "uses" in step:
                assert PINNED.match(cast(str, step["uses"])), f"{job}: {step['uses']}"

    def test_no_expression_is_interpolated_into_a_script(self) -> None:
        for job, step in _all_steps():
            assert "${{" not in cast(str, step.get("run", "")), f"{job}: {step.get('name')}"

    def test_checkouts_do_not_persist_the_token(self) -> None:
        for job, step in _all_steps():
            if "actions/checkout" in str(step.get("uses", "")):
                assert step["with"]["persist-credentials"] is False, job

    def test_every_job_declares_its_permissions_and_a_timeout(self) -> None:
        for name, job in _jobs().items():
            assert "permissions" in job, name
            assert "timeout-minutes" in job, name

    def test_only_the_report_can_write(self) -> None:
        writers = {
            name
            for name, job in _jobs().items()
            if "write" in cast(dict[str, str], job["permissions"]).values()
        }
        assert writers == {"report"}

    def test_every_install_honours_the_lockfile(self) -> None:
        for job, step in _all_steps():
            for line in cast(str, step.get("run", "")).splitlines():
                command = line.strip()
                if re.match(r"uv (sync|run|export)\b", command):
                    assert "--locked" in command, f"{job}: {command}"


class TestGate:
    def test_the_gate_waits_for_every_other_job(self) -> None:
        gate = _jobs()["gate"]
        assert set(gate["needs"]) == set(_jobs()) - {"gate"}
        assert gate["if"] == "${{ always() }}"

    def test_a_failed_or_cancelled_job_fails_the_gate(self) -> None:
        script = cast(str, _steps("gate")[0]["run"])
        assert '"failure"' in script
        assert '"cancelled"' in script

    def test_the_report_blocks_only_on_security(self) -> None:
        quality = next(s for s in _steps("report") if s.get("id") == "quality")
        assert quality["with"]["fail-on-quality"] == "none"
        assert quality["with"]["test-results-dir"] == "."

    def test_the_coverage_gate_is_on_the_run_that_measured_it(self) -> None:
        run = next(s for s in _steps("test") if "pytest" in str(s.get("run", "")))
        assert "--cov-fail-under" in cast(str, run["run"])

    def test_the_comment_is_skipped_for_a_fork(self) -> None:
        comment = next(s for s in _steps("report") if "pr-comment-update" in str(s.get("uses")))
        assert "SAME_REPOSITORY == 'true'" in cast(str, comment["if"])
