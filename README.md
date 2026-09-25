# loom-actions

[![CI PR](https://github.com/the-reacher-data/loom-actions/actions/workflows/ci-pr.yml/badge.svg)](https://github.com/the-reacher-data/loom-actions/actions/workflows/ci-pr.yml)
[![CI Main](https://github.com/the-reacher-data/loom-actions/actions/workflows/ci-main.yml/badge.svg?branch=master)](https://github.com/the-reacher-data/loom-actions/actions/workflows/ci-main.yml)
[![Pyright](https://img.shields.io/badge/Pyright-type%20checked-2b5b84?logo=microsoft&logoColor=white)](https://github.com/microsoft/pyright)
[![Ruff](https://img.shields.io/badge/Ruff-lint-111111?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff/)
![License](https://img.shields.io/github/license/the-reacher-data/loom-actions)

Reusable GitHub Actions for Python projects using Trunk-Based Development and Conventional Commits.

## Features

- Trunk-based release flow on `master`
- Semantic versioning from merged branch name, raised to a major by a commit that declares a break (`type!:` or a `BREAKING CHANGE:` footer)
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

## Reusable Workflows

| Workflow | Purpose |
|---|---|
| `.github/workflows/python-service-ci.yml` | CI for a Python service shipped as a container image: lint, tests, quality report, image build/smoke/scan, optional Codecov/SonarQube/Snyk, one `gate` check |
| `.github/workflows/release-on-label.yml` | Trunk-based release: tag, notes and GitHub Release when a pull request labelled `release` merges; building a distribution is opt-in |

### python-service-ci

```yaml
name: ci
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.event.pull_request.number || github.sha }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

permissions: {}

jobs:
  ci:
    permissions:
      contents: read
      pull-requests: write
    uses: the-reacher-data/loom-actions/.github/workflows/python-service-ci.yml@<sha> # vX.Y.Z
    with:
      python-version: "3.13"
      image-smoke-command: python -c "import app.main"
      sonar: true
      sonar-project-key: ${{ vars.SONAR_PROJECT_KEY }}
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

| Job | Runs | Blocks on |
|---|---|---|
| `lint` | always | `uv sync --locked`, ruff, ruff format, mypy (`typecheck`) |
| `test` | always | pytest failures, coverage under `coverage-threshold` |
| `report` | always | bandit at `fail-on-security`; posts the quality report to the PR and the job summary; uploads to Codecov when `codecov` |
| `sonar` | `sonar: true` | missing `SONAR_TOKEN` or `sonar-project-key`, scanner failure; neither with `sonar-blocking: false` |
| `dependencies` | `snyk: true` | missing `SNYK_TOKEN`, vulnerable locked runtime dependency (a scanner outage only warns) |
| `image` | `image: true` | build, `image-smoke-command`, fixable vulnerabilities at `image-scan-severity` |
| `branch` | pull requests | a branch name no `[tool.semantic_branch]` class matches, or a missing rules file |
| `gate` | always | any job above failed or was cancelled |

- Require only `ci / gate` in branch protection.
- Codecov, SonarQube and Snyk are off by default and need no secret while off. Secrets are
  passed explicitly (`secrets: inherit` does not cross organizations).
- The repository must commit `uv.lock`; every install runs with `--locked`.
- A pull request from a fork skips the secret-dependent jobs and the PR comment.
- Nothing is pushed or deployed. The image uses the `gha` layer cache (`scope=image`), shared
  by pull requests and the trunk, so a later publishing stage can reuse the tested layers.
- `sonar-blocking: false` makes Sonar informative: a scan that fails, or `sonar: true`
  without `SONAR_TOKEN` or `sonar-project-key`, leaves a notice and the `gate` ignores it.
  It is `true` by default, so a Sonar failure blocks as before.

#### A service in a monorepo

When the Python project lives in a subdirectory, with its own `pyproject.toml` and
`uv.lock`, pass `working-directory`:

```yaml
    with:
      python-version: "3.12"
      working-directory: apps/api
      semantic-branch-config: apps/api/pyproject.toml
      image-context: .
      dockerfile: Dockerfile
```

| Input | Default | Relative to | Used by |
|---|---|---|---|
| `working-directory` | `.` | repository root, no trailing slash | `uv sync`, ruff, mypy, pytest, bandit, the quality report and Snyk run there; `uv.lock` is read from it |
| `src-dir`, `test-dir` | `src`, `tests` | `working-directory` | mypy, pytest, the quality report, Sonar |
| `semantic-branch-config` | empty: `<working-directory>/pyproject.toml` | repository root | `branch` |
| `image-context`, `dockerfile` | `.`, `Dockerfile` | repository root | `image` |

- Sonar and Codecov run from the repository root, so a `sonar-project.properties` there is
  honoured; the sources, tests and reports they receive carry the `working-directory`
  prefix (`apps/api/src`, `apps/api/coverage.xml`).
- The paths inside `coverage.xml` are relative to the project, so a monorepo maps them for
  Codecov with `fixes` in its `codecov.yml`.
- With the defaults every path is the one used before, and the jobs are the same.
- [`examples/monorepo`](examples/monorepo) is a runnable caller: `make act-monorepo`.

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
| `test-results-dir` | path, or empty | empty |

### Reporting test results produced elsewhere

`test-results-dir` points at a directory already holding `junit.xml`, `coverage.json` and
`coverage.xml`. When it is set, the action reports those files instead of running pytest, and
fails if any of the three is missing. It exists for a pipeline that runs its tests in its own
job — split across several jobs, or under a resolution the caller controls — and wants one
report over the results rather than a second execution of the same suite.

The gate is unchanged: a failed test and coverage below the threshold still block, because
both are read from these files rather than from the exit code of a pytest this action ran.

### Lockfiles

When the repository contains a `uv.lock`, the tools run with `--frozen`, so the committed
resolution is what gets used.

> **Breaking for one case, shipped in v1.1.0.** A repository whose lockfile is **stale** used
> to be re-resolved silently and now **fails**. That is the intended behaviour — a run whose
> dependencies differ from the ones you committed is not reproducing anything — but it is a
> behavioural break, so a consumer upgrading to v1.1.0 should run `uv lock` and commit the
> result before pinning. A repository with no `uv.lock` at all is unaffected: `--frozen` is
> only added when the file exists.

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
make act-monorepo
```

`make act-monorepo` runs `python-service-ci` over [`examples/monorepo`](examples/monorepo).
act's artifact server only implements the protocol of `upload-artifact` and
`download-artifact` v4, so the target runs a throwaway copy of the checkout in which those
two pins are v4; every other step runs as on GitHub.

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
