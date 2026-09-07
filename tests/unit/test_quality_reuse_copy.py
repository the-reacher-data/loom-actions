"""The step that adopts supplied test results must work in the workspace itself.

A caller whose junit and coverage files are already in the working directory
passes ``test-results-dir: "."``, and ``cp`` treats a file as its own
destination as an error. The loop is shell inside ``action.yml``, so these tests
extract it and run it rather than asserting on its text.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ACTION = Path(__file__).parents[2] / "actions" / "python" / "quality-report" / "action.yml"
ARTIFACTS = ("junit.xml", "coverage.json", "coverage.xml")


def _adopt_results_loop() -> str:
    """Return the shell loop that adopts supplied results, dedented from action.yml."""
    body = ACTION.read_text(encoding="utf-8")
    match = re.search(
        r"^(?P<indent>\s*)for artifact in junit\.xml coverage\.json coverage\.xml; do\n"
        r"(?P<body>.*?)^\s*done\n",
        body,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "action.yml has no loop adopting supplied results"
    indent = match.group("indent")
    lines = [line.removeprefix(indent) for line in match.group(0).splitlines()]
    return "\n".join(lines) + "\n"


def _run(results_dir: str, workspace: Path) -> subprocess.CompletedProcess[str]:
    script = f'set -euo pipefail\nTEST_RESULTS_DIR="{results_dir}"\n{_adopt_results_loop()}'
    return subprocess.run(
        ("bash", "-c", script), cwd=workspace, capture_output=True, text=True, check=False
    )


class TestAdoptSuppliedResults:
    def test_a_results_dir_of_dot_is_adopted_without_copying_onto_itself(
        self, tmp_path: Path
    ) -> None:
        for artifact in ARTIFACTS:
            (tmp_path / artifact).write_text("supplied", encoding="utf-8")

        completed = _run(".", tmp_path)

        assert completed.returncode == 0, completed.stderr
        assert "same file" not in completed.stderr
        for artifact in ARTIFACTS:
            assert (tmp_path / artifact).read_text(encoding="utf-8") == "supplied"

    def test_results_from_another_directory_are_copied_in(self, tmp_path: Path) -> None:
        source = tmp_path / "downloaded"
        source.mkdir()
        for artifact in ARTIFACTS:
            (source / artifact).write_text("downloaded", encoding="utf-8")

        completed = _run("downloaded", tmp_path)

        assert completed.returncode == 0, completed.stderr
        for artifact in ARTIFACTS:
            assert (tmp_path / artifact).read_text(encoding="utf-8") == "downloaded"

    def test_a_missing_artifact_fails_closed(self, tmp_path: Path) -> None:
        source = tmp_path / "downloaded"
        source.mkdir()
        (source / "junit.xml").write_text("downloaded", encoding="utf-8")

        completed = _run("downloaded", tmp_path)

        assert completed.returncode != 0
        assert "does not contain coverage.json" in completed.stdout
