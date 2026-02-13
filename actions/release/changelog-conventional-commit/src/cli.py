#!/usr/bin/env python3
"""
CLI to generate changelogs from conventional commits.

Modes:
- pr: collect commits from PR branch (with SHA + link per commit)
- release: use squash commit body (single global SHA + list of messages)

Features:
- Group by type (feat, fix, docs, style, refactor, perf, test, chore, other)
- Sub-group by scope; uses "(no scope)" if absent
- SHA references and GitHub links in PR mode
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

HERE = Path(__file__).parent
DEFAULT_TEMPLATE = str(HERE / "templates" / "report.md.j2")


def _default_repo_url() -> str:
    """Build GitHub repository URL from environment variables."""
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip("/")
    return f"{server}/{repo}" if repo else server


def get_commits_pr(branch: str) -> list[dict[str, str]]:
    """Retrieve commits for a PR branch compared to origin/main."""
    base = subprocess.check_output(
        ["git", "merge-base", branch, "origin/main"], text=True
    ).strip()
    raw = subprocess.check_output(
        ["git", "log", f"{base}..HEAD", "--pretty=format:%h|%H|%s|%b---END---"],
        text=True,
    )

    commits: list[dict[str, str]] = []
    for chunk in raw.split("---END---"):
        chunk = chunk.strip()
        if not chunk:
            continue

        parts = chunk.split("|", 3)
        if len(parts) < 4:
            continue

        short, full, subject, body = parts
        subject = subject.strip()

        if subject.lower().startswith("wip:"):
            continue

        commits.append(
            {
                "sha": short,
                "sha_full": full,
                "subject": subject,
                "body": body.strip(),
            }
        )
    return commits


def get_commit_squash() -> dict[str, Any]:
    """
    Retrieve the squash commit (subject + body).

    Rules:
    - Lines starting with '* ' or '** ' or matching conventional commit pattern
      → treated as a new commit.
    - Lines starting with '-' → appended to the previous commit's body.
    """
    raw = subprocess.check_output(
        ["git", "log", "-1", "--pretty=format:%h|%H|%s|%b"], text=True
    ).strip()
    short, full, subject, body = raw.split("|", 3)

    commits: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    conv = re.compile(r"^\w+(\([^)]*\))?:\s+")
    for line in (line.strip() for line in body.splitlines()):
        if not line or line.lower().startswith("wip:"):
            continue

        if line.startswith("*") or line.startswith("**") or conv.match(line):
            if current:
                commits.append(current)

            cleaned = re.sub(r"^[*]+\s*", "", line)
            current = {"subject": cleaned, "body": ""}

        elif line.startswith("-") and current:
            detail = re.sub(r"^-\s*", "", line)
            current["body"] += ("\n" if current["body"] else "") + detail

        elif current:
            current["body"] += ("\n" if current["body"] else "") + line

    if current:
        commits.append(current)

    return {"sha": short, "sha_full": full, "subject": subject, "commits": commits}


def group_commits(
    commits: list[dict[str, str]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """
    Group commits by type and scope based on conventional commit format.

    Example commit subject:
        feat(api): add new endpoint
    """
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    pattern = re.compile(r"^(?P<type>\w+)(\((?P<scope>[^)]+)\))?:\s*(?P<desc>.+)$")

    for commit in commits:
        subject = commit["subject"]
        body = commit.get("body", "")

        match = pattern.match(subject)
        if match:
            commit_type = match.group("type")
            scope = match.group("scope") or "(no scope)"
            desc = match.group("desc").strip()
        else:
            commit_type = "other"
            scope = "(no scope)"
            desc = subject.strip()

        grouped[commit_type][scope].append(
            {
                "title": desc,
                "scope": scope,
                "body": body,
                "sha": commit.get("sha"),
                "sha_full": commit.get("sha_full"),
            }
        )
    return grouped


def render(
    template_path: str,
    version: str,
    commits: dict[str, dict[str, list[dict[str, Any]]]],
    repo_url: str,
    squash: dict[str, Any] | None,
    is_unreleased: bool,
    pr_number: int | None,
) -> str:
    """Render the changelog using Jinja2 template."""
    env = Environment(
        loader=FileSystemLoader(Path(template_path).parent),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(Path(template_path).name)
    return template.render(
        version=version,
        commits=commits,
        repo_url=repo_url,
        squash=squash,
        is_unreleased=is_unreleased,
        pr_number=pr_number,
    )


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Generate changelog from conventional commits"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["pr", "release"],
        help="Mode of changelog generation",
    )
    parser.add_argument("--branch", required=True, help="Branch name")
    parser.add_argument(
        "--version", required=False, help="Release version or UNRELEASED"
    )
    parser.add_argument(
        "--pr-number", required=False, help="PR number of the changelog"
    )
    parser.add_argument(
        "--template", default=DEFAULT_TEMPLATE, help="Path to Jinja2 template"
    )
    parser.add_argument("--output", required=True, help="Output markdown file path")
    parser.add_argument(
        "--repo-url", default=_default_repo_url(), help="Repository URL"
    )
    args = parser.parse_args()

    is_unreleased = str(args.version).upper() == "UNRELEASED"
    if args.mode == "pr":
        commits = get_commits_pr(args.branch)
        grouped = group_commits(commits)
        version = (
            args.version
            if not is_unreleased
            else f"Changelog preview for {args.branch} ({args.version})"
        )
        md = render(
            args.template,
            version,
            grouped,
            args.repo_url,
            squash=None,
            is_unreleased=is_unreleased,
            pr_number=None,
        )
    else:  # release mode
        squash = get_commit_squash()
        grouped = group_commits(squash["commits"])
        version = args.version
        md = render(
            args.template,
            version,
            grouped,
            args.repo_url,
            squash=squash,
            is_unreleased=is_unreleased,
            pr_number=args.pr_number,
        )
        changelog = Path("CHANGELOG.md")
        previous = changelog.read_text(encoding="utf-8") if changelog.exists() else ""
        changelog.write_text((md + "\n\n" + previous).rstrip() + "\n", encoding="utf-8")

    Path(args.output).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
