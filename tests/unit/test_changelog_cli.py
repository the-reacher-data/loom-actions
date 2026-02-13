from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_changelog_cli_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = (
        repo_root / "actions/release/changelog-conventional-commit/src/cli.py"
    )
    spec = importlib.util.spec_from_file_location("changelog_cli", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_get_commit_squash_falls_back_to_subject_when_body_has_no_commit_list(
    monkeypatch,
) -> None:
    cli = _load_changelog_cli_module()

    def _fake_check_output(cmd, text=True):  # noqa: ARG001
        return "abc1234|abc1234abcdef|feat(core): add parser (#42)|"

    monkeypatch.setattr(cli.subprocess, "check_output", _fake_check_output)

    squash = cli.get_commit_squash()
    assert squash["sha"] == "abc1234"
    assert len(squash["commits"]) == 1
    assert squash["commits"][0]["subject"] == "feat(core): add parser"


def test_render_pr_mode_includes_stable_pr_files_link() -> None:
    cli = _load_changelog_cli_module()
    grouped = {
        "feat": {
            "(no scope)": [
                {
                    "title": "add parser",
                    "scope": "(no scope)",
                    "body": "",
                    "sha": "abc1234",
                    "sha_full": "abc1234abcdef",
                }
            ]
        }
    }

    markdown = cli.render(
        template_path=cli.DEFAULT_TEMPLATE,
        version="1.2.3",
        commits=grouped,
        repo_url="https://github.com/the-reacher-data/loom-actions",
        squash=None,
        is_unreleased=True,
        pr_number=42,
    )

    assert "/pull/42" in markdown
    assert "/pull/42/files" in markdown
