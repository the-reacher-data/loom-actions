# loom-actions

[![CI PR](https://github.com/the-reacher-data/loom-actions/actions/workflows/ci-pr.yml/badge.svg)](https://github.com/the-reacher-data/loom-actions/actions/workflows/ci-pr.yml)
[![CI Main](https://github.com/the-reacher-data/loom-actions/actions/workflows/ci-main.yml/badge.svg?branch=master)](https://github.com/the-reacher-data/loom-actions/actions/workflows/ci-main.yml)
[![Release](https://github.com/the-reacher-data/loom-actions/actions/workflows/release.yml/badge.svg)](https://github.com/the-reacher-data/loom-actions/actions/workflows/release.yml)
[<img src="https://cdn.simpleicons.org/python/3776AB" alt="Pyright" height="20">](https://github.com/microsoft/pyright)
[<img src="https://cdn.simpleicons.org/ruff/000000" alt="Ruff" height="20">](https://docs.astral.sh/ruff/)
![License](https://img.shields.io/github/license/the-reacher-data/loom-actions)

Reusable GitHub Actions for Python projects using Trunk-Based Development and Conventional Commits.

## Features

- Trunk-based release flow on `master`
- Semantic versioning from merged branch name
- Changelog generation from Conventional Commits + PR preview comment
- Unified Python quality report in PRs (ruff + pyright + pytest/coverage + bandit)
- Local and CI test strategy (`make` + `act` + GitHub workflows)

## Actions Overview

| Category | Action | Description | Status |
|---|---|---|---|
| Core | `actions/core/pr-comment-update` | Create/update PR comment identified by hidden tags | ✅ Ready |
| Core | `actions/core/setup-uv` | Setup Python + uv toolchain | ✅ Ready |
| Release | `actions/release/versioning-branch-semantic` | Calculate semantic version based on branch rules | ✅ Ready |
| Release | `actions/release/changelog-conventional-commit` | Build changelog markdown from Conventional Commits | ✅ Ready |
| Python | `actions/python/quality-report` | Aggregated quality/security report and fail gates | ✅ Ready |

## Quality Budgets

Default budgets for `actions/python/quality-report`:

| Signal | Budget / Rule | Default | Blocking by default |
|---|---|---|---|
| Tests | `tests_failed == 0` | enforced via `fail-on-quality=any` | ✅ Yes |
| Coverage | `coverage >= coverage-threshold` | `80` | ✅ Yes |
| Ruff | `ruff_issues == 0` | enforced via `fail-on-quality=any` | ✅ Yes |
| Pyright | `pyright_errors == 0` | enforced via `fail-on-quality=any` | ✅ Yes |
| Security (Bandit) | Fail by severity threshold | `fail-on-security=high` | ✅ Yes (HIGH+) |
| Security execution | Run Bandit check | `include-security=true` | ✅ Yes |

Tunable inputs:

| Input | Allowed values | Default |
|---|---|---|
| `coverage-threshold` | `0-100` | `80` |
| `fail-on-quality` | `none`, `any` | `any` |
| `fail-on-security` | `none`, `low`, `medium`, `high` | `high` |
| `include-security` | `true`, `false` | `true` |

## Quick Start

### Use quality-report in a PR workflow

```yaml
name: quality
on:
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Quality report
        uses: the-reacher-data/loom-actions/actions/python/quality-report@v1
        with:
          src-dir: src
          test-dir: tests
          coverage-threshold: "80"
          fail-on-quality: "any"
          fail-on-security: "high"
          include-security: "true"
```

### Use release actions

```yaml
- name: Compute version
  id: version
  uses: the-reacher-data/loom-actions/actions/release/versioning-branch-semantic@v1
  with:
    branch: feature/my-change
    prerelease: "false"

- name: Generate changelog
  uses: the-reacher-data/loom-actions/actions/release/changelog-conventional-commit@v1
  with:
    mode: release
    branch: feature/my-change
    version: ${{ steps.version.outputs.version }}
    output: CHANGELOG_RELEASE.md
```

## Local Testing

```bash
make bootstrap
make test-unit
make test-builder-render
```

With `act`:

```bash
make act-unit
make act-smoke
```

## Repository Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci-pr.yml` | `pull_request` | Validate actions, publish changelog+quality PR comments, enforce gates |
| `ci-main.yml` | `push` on `master` | Mainline validation with stricter smoke checks |
| `release.yml` | `pull_request` `closed` on `master` | On merged PR: prepare release PR, auto-merge it, then publish tags/release when `release/*` is merged |
| `act-unit-builder.yml` | local/PR | Unit tests intended for `act` |
| `act-quality-smoke.yml` | local/PR | Composite action smoke run intended for `act` |

## Versioning and Consumption

- Trunk-based flow: merge to `master`, then release workflow creates tags.
- Tag strategy (standard for reusable GitHub Actions):
  - Immutable release tag: `vX.Y.Z` (for pinning exact versions)
  - Moving major tag: `vX` (updated on each compatible minor/patch release)
- Intended external consumption pattern:
  - `the-reacher-data/loom-actions/actions/python/quality-report@v1`
  - `the-reacher-data/loom-actions/actions/release/versioning-branch-semantic@v1`
- Keep major tags (`v1`, `v2`) stable and move them only on compatible releases.

## Repository Settings

- To allow automated release PRs to trigger downstream workflows (`ci-pr` and final `release` on `release/*` merge), add repository secret:
  - `RELEASE_BOT_TOKEN`: PAT/GitHub App token with `contents:write` and `pull_requests:write`.
- Keep `GITHUB_TOKEN` for standard workflow operations; `RELEASE_BOT_TOKEN` is used by the release automation steps that must emit new workflow events.
