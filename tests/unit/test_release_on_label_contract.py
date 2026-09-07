"""Contract tests for the reusable workflow every trunk-based repository calls.

Publishing is opt-in: a repository that ships an application, not a package,
must get the tag, the notes and the GitHub release without ever building a
distribution or needing an index account.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "release-on-label.yml"
ACTION = Path(__file__).parents[2] / "actions" / "release" / "plan-release" / "action.yml"


def _workflow() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")))


def _inputs() -> dict[str, Any]:
    workflow = cast(dict[Any, Any], _workflow())
    triggers = cast(dict[str, Any], workflow.get("on", workflow.get(True)))
    return cast(dict[str, Any], triggers["workflow_call"]["inputs"])


def _job(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], cast(dict[str, Any], _workflow()["jobs"])[name])


def _steps(job: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], _job(job)["steps"])


class TestPublishingIsOptIn:
    def test_publishing_is_off_unless_the_caller_asks(self) -> None:
        publish = _inputs()["publish-to-pypi"]
        assert publish["type"] == "boolean"
        assert publish["default"] is False
        assert publish["required"] is False

    def test_nothing_is_built_when_publishing_is_off(self) -> None:
        assert _job("build")["if"] == "${{ inputs.publish-to-pypi }}"

    def test_the_upload_is_skipped_when_publishing_is_off(self) -> None:
        publish = [s for s in _steps("release") if "pypi-publish" in str(s.get("uses"))]
        assert len(publish) == 1
        assert publish[0]["if"] == "${{ inputs.publish-to-pypi }}"

    def test_a_caller_that_does_not_publish_still_gets_a_release(self) -> None:
        release = [s for s in _steps("release") if "action-gh-release" in str(s.get("uses"))]
        assert len(release) == 1
        assert "if" not in release[0]

    def test_publishing_without_a_package_name_fails_closed(self) -> None:
        guard = [s for s in _steps("plan") if s.get("name") == "Require a package name when publishing"]
        assert len(guard) == 1
        assert guard[0]["if"] == "${{ inputs.publish-to-pypi && inputs.package-name == '' }}"


class TestTrigger:
    def test_the_label_and_the_merge_are_both_required(self) -> None:
        condition = cast(str, _job("plan")["if"])
        assert "merged == true" in condition
        assert "labels.*.name, inputs.release-label)" in condition

    def test_the_release_commit_is_the_merge_commit(self) -> None:
        assert "pull_request.merge_commit_sha" in cast(str, _job("plan")["env"]["MERGE_SHA"])

    def test_a_caller_can_resume_a_halted_run_with_a_sha(self) -> None:
        assert _inputs()["merge-sha"]["default"] == ""
        assert "inputs.merge-sha != ''" in cast(str, _job("plan")["if"])


class TestSafety:
    def test_a_commit_outside_the_base_branch_is_refused(self) -> None:
        guard = [s for s in _steps("plan") if "merge-base --is-ancestor" in str(s.get("run"))]
        assert len(guard) == 1

    def test_the_tag_is_the_last_thing_the_plan_does(self) -> None:
        assert _steps("plan")[-1]["name"] == "Create the immutable version tag"

    def test_an_existing_tag_on_another_commit_refuses(self) -> None:
        tag = _steps("plan")[-1]
        assert "expected ${MERGE_SHA}" in cast(str, tag["run"])

    def test_the_build_reads_the_tag_with_its_history(self) -> None:
        checkout = _steps("build")[0]
        assert checkout["with"]["fetch-depth"] == 0
        assert "needs.plan.outputs.version" in cast(str, checkout["with"]["ref"])

    def test_publishing_uses_no_password(self) -> None:
        publish = [s for s in _steps("release") if "pypi-publish" in str(s.get("uses"))][0]
        assert "with" not in publish
        assert _job("release")["permissions"]["id-token"] == "write"

    def test_the_planner_takes_its_token_as_an_input(self) -> None:
        action = cast(dict[str, Any], yaml.safe_load(ACTION.read_text(encoding="utf-8")))
        assert action["inputs"]["github-token"]["required"] is True
