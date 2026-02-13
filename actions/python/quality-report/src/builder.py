from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}
MAX_ITEMS = 50
MAX_PREVIEW_CHARS = 2000


@dataclass
class FailedTest:
    nodeid: str
    message: str


@dataclass
class CoverageFile:
    path: str
    percent: float
    missing_lines: list[int]


@dataclass
class BanditIssue:
    filename: str
    line_number: int
    severity: str
    confidence: str
    test_id: str
    test_name: str
    issue_text: str


@dataclass
class CommandResult:
    name: str
    command: str
    exit_code: int
    status: str


@dataclass
class Summary:
    ruff_issues: int
    pyright_errors: int
    pyright_warnings: int
    tests_total: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    coverage: float
    bandit_issues: int
    bandit_blocking: bool


def read_json(path: str) -> Any:
    p = Path(path)
    if not p.exists() or not p.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def parse_ruff(path: str) -> list[dict[str, Any]]:
    data = read_json(path)
    return data if isinstance(data, list) else []


def parse_pyright(path: str) -> tuple[int, int, list[dict[str, Any]]]:
    data = read_json(path)
    if not isinstance(data, dict):
        return 0, 0, []

    summary = data.get("summary", {}) or {}
    errors = int(summary.get("errorCount", 0) or 0)
    warnings = int(summary.get("warningCount", 0) or 0)
    diags = data.get("generalDiagnostics", []) or []

    normalized: list[dict[str, Any]] = []
    for d in diags[:MAX_ITEMS]:
        fr = d.get("file") or ""
        msg = d.get("message") or ""
        sev = d.get("severity") or ""
        rule = d.get("rule") or ""
        rng = d.get("range") or {}
        start = rng.get("start") or {}
        normalized.append(
            {
                "file": fr,
                "line": int(start.get("line", 0) or 0) + 1,
                "severity": sev,
                "rule": rule,
                "message": msg,
            }
        )
    return errors, warnings, normalized


def parse_junit(path: str) -> tuple[int, int, int, list[FailedTest]]:
    p = Path(path)
    if not p.exists():
        return 0, 0, 0, []

    root = ET.parse(p).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))

    tests = failures = skipped = 0
    failed_tests: list[FailedTest] = []

    for suite in suites:
        tests += int(suite.attrib.get("tests", 0) or 0)
        failures += int(suite.attrib.get("failures", 0) or 0) + int(
            suite.attrib.get("errors", 0) or 0
        )
        skipped += int(suite.attrib.get("skipped", 0) or 0)

        for case in suite.iter("testcase"):
            for node in list(case.findall("failure")) + list(case.findall("error")):
                file_ = case.attrib.get("file") or ""
                classname = case.attrib.get("classname") or ""
                name = case.attrib.get("name") or ""
                nodeid = f"{file_}::{name}" if file_ else f"{classname}::{name}"
                message = (node.attrib.get("message") or (node.text or "")).strip()
                failed_tests.append(FailedTest(nodeid=nodeid, message=message))

    return tests, failures, skipped, failed_tests[:MAX_ITEMS]


def parse_coverage(path: str) -> tuple[float, list[CoverageFile]]:
    data = read_json(path)
    if not isinstance(data, dict):
        return 0.0, []

    total = round(float((data.get("totals", {}) or {}).get("percent_covered", 0.0)), 2)
    files: list[CoverageFile] = []

    for fp, info in (data.get("files", {}) or {}).items():
        summary = info.get("summary", {}) or {}
        pct = round(float(summary.get("percent_covered", 0.0) or 0.0), 2)
        missing = info.get("missing_lines", []) or []
        files.append(CoverageFile(path=fp, percent=pct, missing_lines=missing))

    return total, files


def parse_bandit(path: str, fail_on: str) -> tuple[list[BanditIssue], bool]:
    data = read_json(path)
    if not isinstance(data, dict):
        return [], False

    issues: list[BanditIssue] = []
    for i in (data.get("results", []) or [])[:MAX_ITEMS]:
        issues.append(
            BanditIssue(
                filename=i.get("filename", ""),
                line_number=int(i.get("line_number", 0) or 0),
                severity=str(i.get("issue_severity", "LOW")),
                confidence=str(i.get("issue_confidence", "LOW")),
                test_id=i.get("test_id", ""),
                test_name=i.get("test_name", ""),
                issue_text=(i.get("issue_text", "") or "").strip(),
            )
        )

    threshold = SEVERITY_ORDER.get(fail_on, 0)
    blocking = (
        any(SEVERITY_ORDER.get(i.severity.lower(), 0) >= threshold for i in issues)
        if threshold > 0
        else False
    )
    return issues, blocking


def parse_command_results(path: str) -> list[CommandResult]:
    p = Path(path)
    if not p.exists() or not p.read_text(encoding="utf-8").strip():
        return []

    out: list[CommandResult] = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        parts = raw.split("\t", 4)
        if len(parts) < 4:
            continue
        name, command, exit_code, status = parts[:4]
        out.append(
            CommandResult(
                name=name,
                command=command,
                exit_code=int(exit_code),
                status=status,
            )
        )
    return out


def render_report(template_path: str, output_path: str, context: dict[str, Any]) -> None:
    tmpl = Path(template_path)
    env = Environment(
        loader=FileSystemLoader(str(tmpl.parent)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(tmpl.name)
    Path(output_path).write_text(template.render(**context), encoding="utf-8")


def write_summary_json(path: str, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_outputs(
    outputs_path: str,
    summary: Summary,
    blocking: bool,
    report_file: str,
    summary_file: str,
) -> None:
    with Path(outputs_path).open("a", encoding="utf-8") as f:
        f.write(f"ruff_issues={summary.ruff_issues}\n")
        f.write(f"pyright_errors={summary.pyright_errors}\n")
        f.write(f"pyright_warnings={summary.pyright_warnings}\n")
        f.write(f"tests_failed={summary.tests_failed}\n")
        f.write(f"coverage={summary.coverage}\n")
        f.write(f"bandit_issues={summary.bandit_issues}\n")
        f.write(f"blocking={'true' if blocking else 'false'}\n")
        f.write(f"report_file={report_file}\n")
        f.write(f"summary_file={summary_file}\n")


def _short_preview(obj: Any) -> str:
    text = json.dumps(obj, ensure_ascii=False)
    if len(text) <= MAX_PREVIEW_CHARS:
        return text
    return text[:MAX_PREVIEW_CHARS] + "... [truncated]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build aggregated Python quality report")
    parser.add_argument("--ruff", required=True)
    parser.add_argument("--pyright", required=True)
    parser.add_argument("--junit", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--bandit", required=False, default="bandit.json")
    parser.add_argument("--commands", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--outputs", required=True)
    parser.add_argument("--coverage-threshold", type=float, default=80.0)
    parser.add_argument("--fail-on-quality", choices=["none", "any"], default="any")
    parser.add_argument(
        "--fail-on-security",
        choices=["none", "low", "medium", "high"],
        default="none",
    )
    args = parser.parse_args()

    ruff_findings = parse_ruff(args.ruff)
    pyright_errors, pyright_warnings, pyright_findings = parse_pyright(args.pyright)
    tests_total, tests_failed, tests_skipped, failed_tests = parse_junit(args.junit)
    tests_passed = max(tests_total - tests_failed - tests_skipped, 0)

    coverage, coverage_files = parse_coverage(args.coverage)
    below_threshold = sorted(
        [f for f in coverage_files if f.percent < args.coverage_threshold],
        key=lambda x: x.percent,
    )[:MAX_ITEMS]

    bandit_issues, bandit_blocking = parse_bandit(args.bandit, args.fail_on_security)
    command_results = parse_command_results(args.commands)
    command_failures = [
        c for c in command_results if c.name in {"ruff", "pyright", "pytest"} and c.status == "fail"
    ]

    summary = Summary(
        ruff_issues=len(ruff_findings),
        pyright_errors=pyright_errors,
        pyright_warnings=pyright_warnings,
        tests_total=tests_total,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        tests_skipped=tests_skipped,
        coverage=coverage,
        bandit_issues=len(bandit_issues),
        bandit_blocking=bandit_blocking,
    )

    quality_blocking = (
        args.fail_on_quality == "any"
        and (
            summary.ruff_issues > 0
            or summary.pyright_errors > 0
            or summary.tests_failed > 0
            or summary.coverage < args.coverage_threshold
            or len(command_failures) > 0
        )
    )
    blocking = quality_blocking or summary.bandit_blocking

    render_report(
        args.template,
        args.output,
        {
            "summary": summary,
            "coverage_threshold": args.coverage_threshold,
            "quality_blocking": quality_blocking,
            "security_blocking": summary.bandit_blocking,
            "blocking": blocking,
            "ruff_findings": ruff_findings[:MAX_ITEMS],
            "pyright_findings": pyright_findings,
            "failed_tests": failed_tests,
            "below_threshold": below_threshold,
            "bandit_issues": bandit_issues,
            "command_results": command_results,
        },
    )

    write_summary_json(
        args.summary,
        {
            "summary": asdict(summary),
            "gates": {
                "quality_blocking": quality_blocking,
                "security_blocking": summary.bandit_blocking,
                "blocking": blocking,
            },
            "checks": {
                "ruff": {
                    "issues": len(ruff_findings),
                    "sample": ruff_findings[:MAX_ITEMS],
                },
                "pyright": {
                    "errors": pyright_errors,
                    "warnings": pyright_warnings,
                    "diagnostics": pyright_findings,
                },
                "tests": {
                    "total": tests_total,
                    "passed": tests_passed,
                    "failed": tests_failed,
                    "skipped": tests_skipped,
                    "failures": [asdict(f) for f in failed_tests],
                },
                "coverage": {
                    "global": coverage,
                    "threshold": args.coverage_threshold,
                    "below_threshold": [asdict(f) for f in below_threshold],
                },
                "bandit": {
                    "issues": len(bandit_issues),
                    "blocking": bandit_blocking,
                    "findings": [asdict(i) for i in bandit_issues],
                },
            },
            "commands": [asdict(c) for c in command_results],
            "command_failures": [asdict(c) for c in command_failures],
            "raw_preview": {
                "ruff": _short_preview(ruff_findings[:10]),
                "pyright": _short_preview(pyright_findings[:10]),
                "failed_tests": _short_preview([asdict(f) for f in failed_tests[:10]]),
                "bandit": _short_preview([asdict(i) for i in bandit_issues[:10]]),
            },
        },
    )

    write_outputs(args.outputs, summary, blocking, args.output, args.summary)

    if blocking:
        sys.exit(1)


if __name__ == "__main__":
    main()
