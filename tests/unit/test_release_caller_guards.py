"""A merge without the release label must not build an image or upload a package.

Without the label, every job of ``release-on-label`` is skipped: ``version`` is
empty and ``distribution-built`` is not ``true``, and the caller's ``release``
job need not read as failed or skipped. The caller of plan §5 therefore gates
the image on a version and the upload on ``distribution-built``, and these
tests pin both halves of that contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import workflow_steps as wf
import yaml

CALLER = Path(__file__).parents[1] / "fixtures" / "callers" / "release.yml"


def _caller_jobs() -> dict[str, dict[str, Any]]:
    return cast(dict[str, dict[str, Any]], yaml.safe_load(CALLER.read_text("utf-8"))["jobs"])


def test_the_image_needs_a_released_version() -> None:
    assert _caller_jobs()["image"]["if"] == (
        "${{ needs.release.result == 'success' && needs.release.outputs.version != '' }}"
    )


def test_the_upload_needs_a_built_distribution() -> None:
    publish = _caller_jobs()["publish"]
    assert publish["if"] == "${{ needs.release.outputs.distribution-built == 'true' }}"
    assert publish["permissions"] == {"id-token": "write"}
    assert publish["environment"] == "pypi"
    upload = next(s for s in publish["steps"] if "gh-action-pypi-publish" in s["uses"])
    assert upload["with"]["skip-existing"] is True


def test_a_skipped_release_releases_and_builds_nothing() -> None:
    """Both outputs come from jobs that the label decides: plan and build."""
    outputs = wf.call("release-on-label")["outputs"]
    assert outputs["version"]["value"] == "${{ jobs.plan.outputs.version }}"
    assert outputs["distribution-built"]["value"] == "${{ jobs.build.outputs.built == 'true' }}"
    jobs = wf.jobs("release-on-label")
    assert "release-label" in cast(str, jobs["plan"]["if"])
    assert jobs["build"]["needs"] == "plan"


def test_a_resumed_run_passes_its_commit() -> None:
    release = _caller_jobs()["release"]
    assert release["with"]["merge-sha"] == "${{ inputs.merge_sha || '' }}"
