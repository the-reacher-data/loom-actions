"""Unit tests for the notes a release ships.

This module had none, which is why the tag-on-HEAD defect fixed in its sibling
survived here: a release re-run for an already tagged commit read its own tag as
the previous release, saw an empty range, and refused.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "actions" / "release" / "plan-release" / "src"))

from build_release_notes import (  # noqa: E402
    ReleaseNotesError,
    build_release_notes,
    latest_release_tag,
    release_entries,
    render_release_notes,
)


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repository), *arguments), check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init", "--initial-branch=master")
    _git(repository, "config", "user.email", "release@example.com")
    _git(repository, "config", "user.name", "Release")
    _commit(repository, "chore: initial")
    return repository


def _commit(repository: Path, message: str) -> str:
    (repository / message.replace(":", "_").replace(" ", "_")).write_text("x", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


class TestLatestReleaseTag:
    def test_reads_the_highest_tag_by_version_not_by_string(self, tmp_path: Path) -> None:
        repository = _repository(tmp_path)
        _git(repository, "tag", "v1.9.9")
        _commit(repository, "fix: one")
        _git(repository, "tag", "v1.9.10")
        _commit(repository, "fix: two")

        assert latest_release_tag(repository) == "v1.9.10"

    def test_ignores_a_tag_on_the_commit_being_released(self, tmp_path: Path) -> None:
        repository = _repository(tmp_path)
        _git(repository, "tag", "v1.10.0")
        _commit(repository, "feat: one")
        _git(repository, "tag", "v1.11.0")

        assert latest_release_tag(repository) == "v1.10.0"

    def test_returns_none_without_a_release_tag(self, tmp_path: Path) -> None:
        repository = _repository(tmp_path)

        assert latest_release_tag(repository) is None

    def test_ignores_a_tag_that_is_not_a_release(self, tmp_path: Path) -> None:
        repository = _repository(tmp_path)
        _git(repository, "tag", "v1.10.0")
        _commit(repository, "fix: one")
        _git(repository, "tag", "nightly-2026-09-07")
        _commit(repository, "fix: two")

        assert latest_release_tag(repository) == "v1.10.0"


class TestReleaseEntries:
    def test_lists_every_commit_since_the_last_tag(self, tmp_path: Path) -> None:
        repository = _repository(tmp_path)
        _git(repository, "tag", "v1.10.0")
        _commit(repository, "feat: one")
        _commit(repository, "fix: two")

        entries = release_entries(repository, "v1.10.0")

        assert entries == ("fix: two", "feat: one")

    def test_lists_the_whole_history_without_a_tag(self, tmp_path: Path) -> None:
        repository = _repository(tmp_path)
        _commit(repository, "feat: one")

        assert release_entries(repository, None) == ("feat: one", "chore: initial")


class TestRenderReleaseNotes:
    def test_names_the_range_the_release_ships(self) -> None:
        rendered = render_release_notes("1.11.0", "v1.10.0", ("feat: one",))

        assert "# 🚀 Release 1.11.0" in rendered
        assert "Changes since v1.10.0:" in rendered
        assert "- feat: one" in rendered

    def test_refuses_a_release_that_ships_nothing(self) -> None:
        with pytest.raises(ReleaseNotesError, match="nothing to release"):
            render_release_notes("1.11.0", "v1.10.0", ())


class TestBuildReleaseNotes:
    def test_a_rerun_for_a_tagged_commit_still_writes_its_notes(self, tmp_path: Path) -> None:
        repository = _repository(tmp_path)
        _git(repository, "tag", "v1.10.0")
        _commit(repository, "feat: one")
        _git(repository, "tag", "v1.11.0")

        notes = build_release_notes(repository, "1.11.0")

        assert "Changes since v1.10.0:" in notes
        assert "- feat: one" in notes
