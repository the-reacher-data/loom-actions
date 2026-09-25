"""Contract tests for the reusable Node CI.

A broken test, a broken lint or an end-to-end run without a browser must turn
the gate red, and each workspace's coverage must reach Codecov with paths a
reader of the repository can open.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
import workflow_steps as wf

NAME = "node-ci"
RESOLVE = "Resolve the workspaces"
PREFIX = "Prefix the lcov paths with the workspace directory"


class TestInputs:
    def test_node_version_is_required(self) -> None:
        assert wf.call(NAME)["inputs"]["node-version"]["required"] is True

    @pytest.mark.parametrize(
        ("name", "default"),
        [
            ("workspaces", ""),
            ("e2e-command", ""),
            ("e2e-workspace-dir", "."),
            ("codecov", False),
            ("test-script", "test:coverage"),
            ("coverage-file", "coverage/lcov.info"),
        ],
    )
    def test_optional_inputs_keep_their_defaults(self, name: str, default: object) -> None:
        declared = wf.call(NAME)["inputs"][name]
        assert declared["required"] is False
        assert declared["default"] == default

    def test_the_codecov_token_is_optional(self) -> None:
        secrets = wf.call(NAME)["secrets"]
        assert set(secrets) == {"CODECOV_TOKEN"}
        assert secrets["CODECOV_TOKEN"]["required"] is False


class TestJobs:
    def test_every_job_only_reads(self) -> None:
        for name, job in wf.jobs(NAME).items():
            if name != "gate":
                assert job["permissions"] == {"contents": "read"}, name

    def test_the_codecov_token_reaches_only_the_upload_and_its_check(self) -> None:
        holders = [
            (name, step.get("name") or step.get("uses", ""))
            for name in wf.jobs(NAME)
            for step in wf.steps(NAME, name)
            if "secrets.CODECOV_TOKEN" in json.dumps(step)
        ]
        assert [job for job, _ in holders] == ["test", "test"]
        check, upload = (title for _, title in holders)
        assert check == "Check the Codecov token"
        assert upload == "Upload coverage to Codecov"

    def test_the_codecov_upload_is_opt_in_and_never_blocks(self) -> None:
        upload = next(s for s in wf.steps(NAME, "test") if "codecov" in s.get("uses", ""))
        assert "inputs.codecov" in upload["if"]
        assert upload["with"]["fail_ci_if_error"] is False
        assert upload["with"]["flags"] == "${{ matrix.workspace.flag }}"
        assert upload["with"]["disable_search"] is True

    def test_the_tests_run_once_per_workspace(self) -> None:
        test = wf.jobs(NAME)["test"]
        assert test["needs"] == "workspaces"
        assert test["strategy"]["fail-fast"] is False
        assert "needs.workspaces.outputs.matrix" in test["strategy"]["matrix"]["workspace"]

    @pytest.mark.parametrize(("job", "script"), [("lint", "LINT_SCRIPT"), ("test", "TEST_SCRIPT")])
    def test_a_missing_lint_or_test_script_fails(self, job: str, script: str) -> None:
        scripts = [cast(str, s.get("run", "")) for s in wf.steps(NAME, job)]
        runs = [r for r in scripts if f'"${{{script}}}"' in r]
        assert runs
        assert all("--if-present" not in r for r in runs)

    def test_every_install_honours_the_lockfile(self) -> None:
        for name in wf.jobs(NAME):
            for step in wf.steps(NAME, name):
                for line in cast(str, step.get("run", "")).splitlines():
                    assert not re.match(r"\s*npm (install|i)\b", line), name
        installs = [
            name
            for name in wf.jobs(NAME)
            if any(
                re.match(r"\s*npm ci$", line)
                for s in wf.steps(NAME, name)
                for line in cast(str, s.get("run", "")).splitlines()
            )
        ]
        assert set(installs) == {"lint", "test", "build", "e2e"}


class TestEndToEnd:
    def test_it_runs_only_with_a_command(self) -> None:
        assert wf.jobs(NAME)["e2e"]["if"] == "${{ inputs.e2e-command != '' }}"

    def test_it_installs_chromium_before_the_command(self) -> None:
        titles = [s.get("name") for s in wf.steps(NAME, "e2e")]
        install = wf.step(NAME, "e2e", "Install Chromium")
        assert "npx --no playwright install --with-deps chromium" in install["run"]
        assert titles.index("Install Chromium") < titles.index("Run the end-to-end command")

    def test_the_command_comes_from_the_environment(self) -> None:
        run = wf.step(NAME, "e2e", "Run the end-to-end command")
        assert run["env"]["E2E_COMMAND"] == "${{ inputs.e2e-command }}"
        assert "continue-on-error" not in run


def _lock(root: Path, workspaces: dict[str, str]) -> None:
    packages: dict[str, dict[str, object]] = {"": {"name": "root"}}
    for name, directory in workspaces.items():
        packages[directory] = {"name": name, "version": "0.0.0"}
        packages[f"node_modules/{name}"] = {"resolved": directory, "link": True}
    lock = {"name": "root", "lockfileVersion": 3, "packages": packages}
    (root / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")


def _outputs(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines)


class TestResolveWorkspaces:
    def _resolve(self, tmp_path: Path, workspaces: str) -> tuple[int, str, dict[str, str]]:
        _lock(tmp_path, {"@acme/core": "packages/core", "acme-web": "apps/web"})
        output = tmp_path / "out.txt"
        output.touch()
        env = {"WORKSPACES": workspaces, "GITHUB_OUTPUT": str(output)}
        done = wf.run(NAME, "workspaces", RESOLVE, env, tmp_path)
        return done.returncode, done.stdout, _outputs(output)

    def test_each_workspace_gets_its_directory_and_a_flag(self, tmp_path: Path) -> None:
        code, _, outputs = self._resolve(tmp_path, "@acme/core acme-web")
        assert code == 0
        assert json.loads(outputs["matrix"]) == [
            {"name": "@acme/core", "dir": "packages/core", "flag": "core"},
            {"name": "acme-web", "dir": "apps/web", "flag": "web"},
        ]

    def test_no_workspace_means_the_root_project(self, tmp_path: Path) -> None:
        code, _, outputs = self._resolve(tmp_path, "  ")
        assert code == 0
        assert json.loads(outputs["matrix"]) == [{"name": "", "dir": ".", "flag": ""}]

    def test_an_unknown_workspace_fails(self, tmp_path: Path) -> None:
        code, stdout, _ = self._resolve(tmp_path, "@acme/core nope")
        assert code != 0
        assert "::error" in stdout
        assert "nope" in stdout

    def test_a_missing_lockfile_fails(self, tmp_path: Path) -> None:
        output = tmp_path / "out.txt"
        output.touch()
        done = wf.run(
            NAME, "workspaces", RESOLVE, {"WORKSPACES": "", "GITHUB_OUTPUT": str(output)}, tmp_path
        )
        assert done.returncode != 0
        assert "package-lock.json" in done.stdout


LCOV = """TN:
SF:src/a.ts
DA:1,1
end_of_record
SF:{root}/packages/core/src/b.ts
DA:1,0
end_of_record
SF:/elsewhere/c.ts
end_of_record
"""


class TestPrefixLcov:
    def _prefix(self, tmp_path: Path, directory: str, content: str | None) -> tuple[int, str]:
        lcov = tmp_path / directory / "coverage" / "lcov.info"
        lcov.parent.mkdir(parents=True, exist_ok=True)
        if content is not None:
            lcov.write_text(content.format(root=tmp_path), encoding="utf-8")
        env = {
            "WORKSPACE_DIR": directory,
            "COVERAGE_FILE": "coverage/lcov.info",
            "GITHUB_WORKSPACE": str(tmp_path),
        }
        done = wf.run(NAME, "test", PREFIX, env, tmp_path)
        text = lcov.read_text(encoding="utf-8") if lcov.exists() else ""
        return done.returncode, text + done.stdout

    def test_paths_become_relative_to_the_repository(self, tmp_path: Path) -> None:
        code, text = self._prefix(tmp_path, "packages/core", LCOV)
        assert code == 0
        sources = [line for line in text.splitlines() if line.startswith("SF:")]
        assert sources == [
            "SF:packages/core/src/a.ts",
            "SF:packages/core/src/b.ts",
            "SF:/elsewhere/c.ts",
        ]
        assert "DA:1,1" in text

    def test_the_root_project_keeps_its_paths(self, tmp_path: Path) -> None:
        code, text = self._prefix(tmp_path, ".", "SF:src/a.ts\nend_of_record\n")
        assert code == 0
        assert "SF:src/a.ts" in text.splitlines()

    def test_a_missing_report_fails(self, tmp_path: Path) -> None:
        code, text = self._prefix(tmp_path, "packages/core", None)
        assert code != 0
        assert "::error" in text
