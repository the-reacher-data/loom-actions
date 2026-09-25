"""Contract tests for the reusable repository security checks.

A committed secret, a vulnerable dependency and a failing extra check block;
CodeQL and dependency review, which need GitHub Advanced Security on a private
repository, leave a notice there instead of failing. The extra check runs the
caller's own command, so it gets no secret and no write permission.
"""

from __future__ import annotations

import json
import shutil
import string
import subprocess
from pathlib import Path
from typing import cast

import pytest
import workflow_steps as wf

NAME = "repo-security"
SCAN = "Scan the full history with gitleaks"
PRIVATE = "${{ github.event.repository.private }}"
PUBLIC = "${{ !github.event.repository.private }}"


class TestInputs:
    @pytest.mark.parametrize(
        ("name", "default"),
        [
            ("gitleaks-config", ""),
            ("codeql-languages", ""),
            ("dependency-review", True),
            ("dependency-review-severity", "high"),
            ("extra-check-command", ""),
            ("extra-check-python-version", ""),
            ("extra-check-node-version", ""),
        ],
    )
    def test_every_input_is_optional(self, name: str, default: object) -> None:
        declared = wf.call(NAME)["inputs"][name]
        assert declared["required"] is False
        assert declared["default"] == default

    def test_it_takes_no_secret(self) -> None:
        assert "secrets" not in wf.call(NAME)
        assert "secrets." not in json.dumps(wf.load(NAME))


class TestPermissions:
    @pytest.mark.parametrize(
        ("job", "permissions"),
        [
            ("gitleaks", {"contents": "read"}),
            ("codeql", {"contents": "read", "security-events": "write", "actions": "read"}),
            ("dependency-review", {"contents": "read", "pull-requests": "write"}),
            ("extra-check", {"contents": "read"}),
            ("gate", {}),
        ],
    )
    def test_each_job_gets_only_what_it_uses(self, job: str, permissions: dict[str, str]) -> None:
        assert wf.jobs(NAME)[job]["permissions"] == permissions


class TestGitleaks:
    def test_it_reads_the_full_history(self) -> None:
        checkout = wf.steps(NAME, "gitleaks")[0]
        assert checkout["with"]["fetch-depth"] == 0

    def test_the_image_is_pinned_by_digest(self) -> None:
        scan = wf.step(NAME, "gitleaks", SCAN)
        assert scan["env"]["GITLEAKS_IMAGE"].startswith("ghcr.io/gitleaks/gitleaks@sha256:")
        assert len(scan["env"]["GITLEAKS_IMAGE"].split("@sha256:")[1]) == 64
        assert scan["env"]["GITLEAKS_CONFIG"] == "${{ inputs.gitleaks-config }}"


class TestAdvancedSecurity:
    @pytest.mark.parametrize("job", ["codeql", "dependency-review"])
    def test_a_private_repository_gets_a_notice(self, job: str) -> None:
        notice = wf.steps(NAME, job)[0]
        assert notice["if"] == PRIVATE
        assert "::notice" in notice["run"]
        assert "exit" not in notice["run"]

    @pytest.mark.parametrize("job", ["codeql", "dependency-review"])
    def test_every_other_step_runs_only_in_public(self, job: str) -> None:
        for step in wf.steps(NAME, job)[1:]:
            assert step["if"] == PUBLIC, step.get("name")

    def test_codeql_needs_no_build(self) -> None:
        init = next(
            s for s in wf.steps(NAME, "codeql") if "codeql-action/init" in s.get("uses", "")
        )
        assert init["with"]["build-mode"] == "none"
        assert init["with"]["languages"] == "${{ inputs.codeql-languages }}"
        assert wf.jobs(NAME)["codeql"]["if"] == "${{ inputs.codeql-languages != '' }}"

    def test_the_codeql_actions_share_one_release(self) -> None:
        refs = {
            s["uses"].split("@")[1]
            for s in wf.steps(NAME, "codeql")
            if "codeql-action" in s.get("uses", "")
        }
        assert len(refs) == 1

    def test_dependency_review_blocks_at_the_severity(self) -> None:
        review = next(
            s
            for s in wf.steps(NAME, "dependency-review")
            if "dependency-review-action" in s.get("uses", "")
        )
        assert review["with"]["fail-on-severity"] == "${{ inputs.dependency-review-severity }}"
        assert "continue-on-error" not in review

    def test_dependency_review_runs_on_pull_requests_only(self) -> None:
        condition = cast(str, wf.jobs(NAME)["dependency-review"]["if"])
        assert "inputs.dependency-review" in condition
        assert "github.event_name == 'pull_request'" in condition


class TestExtraCheck:
    def test_it_runs_only_with_a_command(self) -> None:
        assert wf.jobs(NAME)["extra-check"]["if"] == "${{ inputs.extra-check-command != '' }}"

    @pytest.mark.parametrize(
        ("action", "version"),
        [
            ("astral-sh/setup-uv", "extra-check-python-version"),
            ("actions/setup-node", "extra-check-node-version"),
        ],
    )
    def test_each_toolchain_is_installed_on_request(self, action: str, version: str) -> None:
        setup = next(s for s in wf.steps(NAME, "extra-check") if action in s.get("uses", ""))
        assert setup["if"] == f"${{{{ inputs.{version} != '' }}}}"

    @pytest.mark.parametrize(("command", "code"), [("true", 0), ("exit 1", 1), ("false; true", 1)])
    def test_its_exit_code_is_the_verdict(self, tmp_path: Path, command: str, code: int) -> None:
        done = wf.run(
            NAME, "extra-check", "Run the extra check", {"EXTRA_CHECK_COMMAND": command}, tmp_path
        )
        assert done.returncode == code, done.stdout + done.stderr


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(("docker", "info"), capture_output=True, check=False).returncode == 0


def _git(repo: Path, *args: str) -> None:
    subprocess.run(("git", "-C", str(repo), *args), check=True, capture_output=True)


def _repository(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "settings.py").write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "x")
    return repo


@pytest.mark.skipif(not _docker_ready(), reason="docker is not available")
class TestGitleaksScan:
    """Runs the scan step itself; the fake token is built at run time, never committed."""

    TOKEN = "ghp_" + (string.ascii_letters + string.digits)[7:43]

    def _scan(self, repo: Path, config: str = "") -> subprocess.CompletedProcess[str]:
        env = dict(wf.step(NAME, "gitleaks", SCAN)["env"])
        env.update({"GITLEAKS_CONFIG": config, "GITHUB_WORKSPACE": str(repo)})
        return wf.run(NAME, "gitleaks", SCAN, env, repo)

    def test_a_committed_secret_fails(self, tmp_path: Path) -> None:
        done = self._scan(_repository(tmp_path, f'TOKEN = "{self.TOKEN}"\n'))
        assert done.returncode != 0, done.stdout + done.stderr
        assert "::error title=gitleaks found secrets" in done.stdout
        assert self.TOKEN not in done.stdout + done.stderr

    def test_the_configuration_given_is_used(self, tmp_path: Path) -> None:
        repo = _repository(tmp_path, f'TOKEN = "{self.TOKEN}"\n')
        (repo / "scan.toml").write_text(
            "[extend]\nuseDefault = true\n\n[allowlist]\npaths = ['''settings\\.py''']\n",
            encoding="utf-8",
        )
        done = self._scan(repo, "scan.toml")
        assert done.returncode == 0, done.stdout + done.stderr

    def test_a_missing_configuration_fails(self, tmp_path: Path) -> None:
        done = self._scan(_repository(tmp_path, "DEBUG = False\n"), "missing.toml")
        assert done.returncode != 0
        assert "::error title=gitleaks configuration is missing" in done.stdout

    def test_a_committed_ignore_file_is_honoured(self, tmp_path: Path) -> None:
        repo = _repository(tmp_path, f'TOKEN = "{self.TOKEN}"\n')
        head = subprocess.run(
            ("git", "-C", str(repo), "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        (repo / ".gitleaksignore").write_text(f"{head}:settings.py:github-pat:1\n", "utf-8")
        done = self._scan(repo)
        assert done.returncode == 0, done.stdout + done.stderr

    def test_a_clean_history_passes(self, tmp_path: Path) -> None:
        done = self._scan(_repository(tmp_path, "DEBUG = False\n"))
        assert done.returncode == 0, done.stdout + done.stderr
