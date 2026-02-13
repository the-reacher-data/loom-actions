from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RUFF_JSON = """[
  {
    "code": "F401",
    "filename": "src/sample_pkg/module.py",
    "location": {"row": 3, "column": 1},
    "message": "`os` imported but unused"
  }
]
"""

PYRIGHT_JSON = """{
  "version": "1.1.350",
  "time": "0.1",
  "generalDiagnostics": [
    {
      "file": "src/sample_pkg/module.py",
      "severity": "error",
      "message": "Argument of type \\\"str\\\" cannot be assigned to parameter of type \\\"int\\\"",
      "range": {"start": {"line": 9, "character": 12}, "end": {"line": 9, "character": 16}},
      "rule": "reportArgumentType"
    },
    {
      "file": "src/sample_pkg/module.py",
      "severity": "warning",
      "message": "Type of \\\"x\\\" is unknown",
      "range": {"start": {"line": 2, "character": 0}, "end": {"line": 2, "character": 1}},
      "rule": "reportUnknownVariableType"
    }
  ],
  "summary": {
    "filesAnalyzed": 1,
    "errorCount": 1,
    "warningCount": 1,
    "informationCount": 0,
    "timeInSec": 0.1
  }
}
"""

JUNIT_XML = """<testsuites>
  <testsuite name=\"pytest\" tests=\"3\" failures=\"1\" errors=\"0\" skipped=\"1\">
    <testcase classname=\"tests.test_sample\" name=\"test_ok\" file=\"tests/test_sample.py\" />
    <testcase classname=\"tests.test_sample\" name=\"test_fail\" file=\"tests/test_sample.py\">
      <failure message=\"assert 1 == 2\">AssertionError: expected 2</failure>
    </testcase>
    <testcase classname=\"tests.test_sample\" name=\"test_skip\" file=\"tests/test_sample.py\">
      <skipped message=\"skip reason\" />
    </testcase>
  </testsuite>
</testsuites>
"""

COVERAGE_JSON = """{
  "meta": {"version": "7.6.0"},
  "totals": {"percent_covered": 66.67},
  "files": {
    "src/sample_pkg/module.py": {
      "summary": {"percent_covered": 55.0},
      "missing_lines": [10, 11, 12]
    },
    "src/sample_pkg/utils.py": {
      "summary": {"percent_covered": 95.0},
      "missing_lines": []
    }
  }
}
"""

BANDIT_JSON = """{
  "results": [
    {
      "filename": "src/sample_pkg/module.py",
      "line_number": 22,
      "issue_severity": "MEDIUM",
      "issue_confidence": "HIGH",
      "test_id": "B608",
      "test_name": "hardcoded_sql_expressions",
      "issue_text": "Possible SQL injection vector"
    }
  ]
}
"""

COMMAND_STATUS = """ruff\truff check src --output-format json\t1\tfail\truff.json
pyright\tpyright src --outputjson\t1\tfail\tpyright.json
pytest\tpytest tests --cov=src ...\t1\tfail\tjunit.xml,coverage.json,coverage.xml
bandit\tbandit -r src -f json -o bandit.json\t0\tpass\tbandit.json
"""


def _write_fixture_files(target_dir: Path) -> None:
    (target_dir / "ruff.json").write_text(RUFF_JSON, encoding="utf-8")
    (target_dir / "pyright.json").write_text(PYRIGHT_JSON, encoding="utf-8")
    (target_dir / "junit.xml").write_text(JUNIT_XML, encoding="utf-8")
    (target_dir / "coverage.json").write_text(COVERAGE_JSON, encoding="utf-8")
    (target_dir / "bandit.json").write_text(BANDIT_JSON, encoding="utf-8")
    (target_dir / "command_status.tsv").write_text(COMMAND_STATUS, encoding="utf-8")


def _run_builder(
    tmp_path: Path,
    fail_on_quality: str,
    fail_on_security: str,
    threshold: str,
) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    builder = repo_root / "actions/python/quality-report/src/builder.py"
    template = repo_root / "actions/python/quality-report/src/templates/report.md.j2"

    _write_fixture_files(tmp_path)

    outputs_file = tmp_path / "gh_outputs.txt"
    outputs_file.write_text("", encoding="utf-8")

    cmd = [
        sys.executable,
        str(builder),
        "--ruff",
        str(tmp_path / "ruff.json"),
        "--pyright",
        str(tmp_path / "pyright.json"),
        "--junit",
        str(tmp_path / "junit.xml"),
        "--coverage",
        str(tmp_path / "coverage.json"),
        "--bandit",
        str(tmp_path / "bandit.json"),
        "--commands",
        str(tmp_path / "command_status.tsv"),
        "--template",
        str(template),
        "--output",
        str(tmp_path / "quality_report.md"),
        "--summary",
        str(tmp_path / "quality_summary.json"),
        "--outputs",
        str(outputs_file),
        "--coverage-threshold",
        threshold,
        "--fail-on-quality",
        fail_on_quality,
        "--fail-on-security",
        fail_on_security,
    ]
    return subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=False)


def test_builder_blocks_when_quality_or_security_gate_fails(tmp_path: Path) -> None:
    result = _run_builder(
        tmp_path=tmp_path,
        fail_on_quality="any",
        fail_on_security="medium",
        threshold="80",
    )

    assert result.returncode == 1

    summary = json.loads((tmp_path / "quality_summary.json").read_text(encoding="utf-8"))
    assert summary["gates"]["quality_blocking"] is True
    assert summary["gates"]["security_blocking"] is True
    assert summary["summary"]["tests_failed"] == 1
    assert summary["summary"]["pyright_errors"] == 1
    assert summary["summary"]["coverage"] == 66.67

    report = (tmp_path / "quality_report.md").read_text(encoding="utf-8")
    assert "Failed tests" in report
    assert "Bandit findings" in report
    assert "Pyright diagnostics" in report


def test_builder_passes_when_fail_modes_are_none(tmp_path: Path) -> None:
    result = _run_builder(
        tmp_path=tmp_path,
        fail_on_quality="none",
        fail_on_security="none",
        threshold="80",
    )

    assert result.returncode == 0

    summary = json.loads((tmp_path / "quality_summary.json").read_text(encoding="utf-8"))
    assert summary["gates"]["blocking"] is False
    assert summary["summary"]["ruff_issues"] == 1
    assert summary["summary"]["bandit_issues"] == 1

    outputs_text = (tmp_path / "gh_outputs.txt").read_text(encoding="utf-8")
    assert "blocking=false" in outputs_text
    assert "coverage=66.67" in outputs_text
