"""Contract tests for the reusable documentation build.

The workflow only builds: it runs the caller's command with a read-only token
and no secret, and with ``deploy`` it hands the site to a deploy job the caller
owns as the Pages artifact. Deploying needs ``pages: write`` and ``id-token``,
which a job running the caller's build command must never hold.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import workflow_steps as wf

NAME = "pages"
UPLOAD = "actions/upload-pages-artifact"


class TestInputs:
    @pytest.mark.parametrize("name", ["build-command", "output-dir"])
    def test_the_build_is_required(self, name: str) -> None:
        assert wf.call(NAME)["inputs"][name]["required"] is True

    @pytest.mark.parametrize(
        ("name", "default"),
        [("deploy", False), ("python-version", ""), ("node-version", "")],
    )
    def test_optional_inputs_keep_their_defaults(self, name: str, default: object) -> None:
        declared = wf.call(NAME)["inputs"][name]
        assert declared["required"] is False
        assert declared["default"] == default

    def test_it_takes_no_secret(self) -> None:
        assert "secrets" not in wf.call(NAME)
        assert "secrets." not in json.dumps(wf.load(NAME))

    def test_it_says_whether_it_uploaded_the_site(self) -> None:
        output = wf.call(NAME)["outputs"]["pages-artifact"]
        assert output["value"] == "${{ jobs.build.outputs.pages-artifact }}"


class TestItOnlyBuilds:
    def test_the_build_only_reads(self) -> None:
        assert list(wf.jobs(NAME)) == ["build"]
        assert wf.jobs(NAME)["build"]["permissions"] == {"contents": "read"}

    def test_nothing_is_deployed_here(self) -> None:
        assert "deploy-pages" not in json.dumps(wf.load(NAME))

    def test_the_artifact_is_uploaded_only_on_request_in_public(self) -> None:
        upload = next(s for s in wf.steps(NAME, "build") if UPLOAD in s.get("uses", ""))
        assert upload["if"] == "${{ inputs.deploy && !github.event.repository.private }}"
        assert upload["with"]["path"] == "${{ inputs.output-dir }}"

    def test_a_private_deploy_request_gets_a_notice(self) -> None:
        notice = wf.step(NAME, "build", "Skip the Pages artifact in a private repository")
        assert notice["if"] == "${{ inputs.deploy && github.event.repository.private }}"
        assert "::notice" in notice["run"]

    @pytest.mark.parametrize(
        ("action", "version"),
        [("astral-sh/setup-uv", "python-version"), ("actions/setup-node", "node-version")],
    )
    def test_each_toolchain_is_installed_on_request(self, action: str, version: str) -> None:
        setup = next(s for s in wf.steps(NAME, "build") if action in s.get("uses", ""))
        assert setup["if"] == f"${{{{ inputs.{version} != '' }}}}"


class TestBuildScripts:
    @pytest.mark.parametrize(("command", "code"), [("true", 0), ("exit 3", 3)])
    def test_the_build_exit_code_is_the_verdict(
        self, tmp_path: Path, command: str, code: int
    ) -> None:
        done = wf.run(NAME, "build", "Build the site", {"BUILD_COMMAND": command}, tmp_path)
        assert done.returncode == code

    def _check(self, tmp_path: Path, files: list[str]) -> int:
        site = tmp_path / "site"
        site.mkdir()
        for name in files:
            (site / name).write_text("x", encoding="utf-8")
        env = {"OUTPUT_DIR": "site", "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
        return wf.run(NAME, "build", "Require the built site", env, tmp_path).returncode

    def test_an_empty_site_fails(self, tmp_path: Path) -> None:
        assert self._check(tmp_path, []) != 0

    def test_a_site_without_an_index_fails(self, tmp_path: Path) -> None:
        assert self._check(tmp_path, ["page.html"]) != 0

    def test_a_site_with_an_index_passes(self, tmp_path: Path) -> None:
        assert self._check(tmp_path, ["index.html"]) == 0
