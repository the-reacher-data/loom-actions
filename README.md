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
| `.github/workflows/node-ci.yml` | CI for npm workspaces: lint, type-check, tests with repository-relative lcov per workspace, build, Playwright end-to-end on Chromium, optional Codecov, one `gate` check |
| `.github/workflows/repo-security.yml` | gitleaks over the full history, CodeQL, dependency review and a command of the caller's with no secret, one `gate` check |
| `.github/workflows/pages.yml` | Builds a static site with a read-only token and uploads it as the Pages artifact; the caller deploys |
| `.github/workflows/image-release.yml` | Publishes a release image to GHCR and optionally Docker Hub: multi-arch, `X.Y.Z`/`X.Y`/`latest`, SBOM, provenance and an attestation |

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

### Monorepo callers

The four workflows below are small and independent, so a monorepo calls each one from its own
job, grants that job only the permissions the workflow needs, and requires one `gate` of its
own. `tests/fixtures/callers/` holds a complete example (`ci.yml`, `docs.yml`, `release.yml`)
that the unit tests check against every workflow it calls: each input and secret it passes is
declared, each required input is passed, and each job is granted what the called jobs request.

None of them sets `concurrency`; the caller does. No job that runs a command of the caller's
receives a secret or a write permission.

### node-ci

```yaml
  node:
    permissions:
      contents: read
    uses: the-reacher-data/loom-actions/.github/workflows/node-ci.yml@<sha> # vX.Y.Z
    with:
      node-version: "22"
      workspaces: "@acme/core acme-web"
      e2e-command: "npm run test:e2e -w @acme/core"
      e2e-workspace-dir: packages/core
      codecov: true
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

| Job | Runs | Blocks on |
|---|---|---|
| `workspaces` | always | no `package-lock.json`, a name that is not a workspace, two workspaces in directories with the same name |
| `lint` | always | `npm ci`, `lint-script` and `typecheck-script` in every workspace (a missing script fails) |
| `test` | once per workspace | `test-script` (a missing script fails), no lcov at `coverage-file` |
| `build` | `build-script` set | `build-script` where it exists |
| `e2e` | `e2e-command` set | `npx --no playwright install --with-deps chromium` in `e2e-workspace-dir`, then the command |
| `gate` | always | any job above failed or was cancelled |

- `workspaces` is a space-separated list of npm workspace names, resolved to their directories
  through `package-lock.json`; empty runs the scripts in the root project.
- The `SF:` paths of each lcov are rewritten relative to the repository root
  (`src/a.ts` in `packages/core` becomes `packages/core/src/a.ts`), stored as the artifact
  `coverage-<dir>` and, with `codecov: true`, uploaded with the flag `<dir>`: the basename of
  the workspace directory (`core`, `web`). The upload never fails the run.
- Playwright comes from the lockfile: `npx --no` refuses to download another version.

### repo-security

```yaml
  security:
    permissions:
      contents: read
      security-events: write
      pull-requests: write
      actions: read
    uses: the-reacher-data/loom-actions/.github/workflows/repo-security.yml@<sha> # vX.Y.Z
    with:
      gitleaks-config: .gitleaks.toml
      codeql-languages: "python,javascript-typescript"
      extra-check-command: "python3 scripts/check.py && node scripts/check.mjs"
      extra-check-python-version: "3.12"
      extra-check-node-version: "22"
```

| Job | Runs | Permissions | Blocks on |
|---|---|---|---|
| `gitleaks` | always | `contents: read` | a secret anywhere in the history (gitleaks 8.30.1, image pinned by digest; findings are redacted) |
| `codeql` | `codeql-languages` set | `contents: read`, `security-events: write`, `actions: read` | an analysis that fails; alerts land in code scanning (`build-mode: none`) |
| `dependency-review` | pull requests, `dependency-review: true` | `contents: read`, `pull-requests: write` | a new dependency vulnerable at `dependency-review-severity` (`high`) |
| `extra-check` | `extra-check-command` set | `contents: read` | a non-zero exit of the command |
| `gate` | always | none | any job above failed or was cancelled |

- In a private repository CodeQL and the dependency review need GitHub Advanced Security, so
  their jobs leave a notice and pass.
- `extra-check-command` runs with `bash -euo pipefail`, no secret and a checkout that keeps no
  token. `extra-check-python-version` installs uv and a virtualenv of that Python first on
  `PATH` (outside the workspace); `extra-check-node-version` installs Node.js.

### pages

```yaml
  docs:
    permissions:
      contents: read
    uses: the-reacher-data/loom-actions/.github/workflows/pages.yml@<sha> # vX.Y.Z
    with:
      deploy: true
      python-version: "3.12"
      build-command: "uv sync --locked && uv run --locked sphinx-build -W -b html docs docs/_build/html"
      output-dir: docs/_build/html

  deploy:
    needs: docs
    if: ${{ needs.docs.outputs.pages-artifact == 'true' }}
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1
```

- The workflow only builds, with `contents: read` and no secret, and fails when
  `output-dir/index.html` is missing. It never deploys: `pages: write` and `id-token: write`
  belong to the caller's deploy job, which runs none of the build's code.
- `deploy: true` uploads the site as the Pages artifact and sets the output
  `pages-artifact` to `true`; in a private repository it leaves a notice instead. With
  `deploy: false` (a pull request) it only builds.

### image-release

```yaml
  image:
    needs: release
    if: ${{ needs.release.result == 'success' && needs.release.outputs.version != '' }}
    permissions:
      contents: read
      packages: write
      id-token: write
      attestations: write
    uses: the-reacher-data/loom-actions/.github/workflows/image-release.yml@<sha> # vX.Y.Z
    with:
      version: ${{ needs.release.outputs.version }}
      ghcr-image: ghcr.io/acme/app
      dockerhub-image: acme/app
      platforms: "linux/amd64,linux/arm64"
    secrets:
      DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
      DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}
```

- It stops before anything else unless `version` matches `^[0-9]+\.[0-9]+\.[0-9]+$` and
  `ghcr-image` is a lowercase `ghcr.io/...` name, and when `dockerhub-image` is set without
  both Docker Hub secrets.
- It builds the tag `v<version>`, not the commit that started the run, and pushes `X.Y.Z`,
  `X.Y` and `latest` to GHCR and, optionally, Docker Hub, with the build args `VERSION`,
  `REVISION` (the tagged commit) and `CREATED`, an SBOM and `provenance: mode=max`. The layer
  cache is read from `python-service-ci` (`scope=image`).
- In a public repository the digest gets a build provenance attestation pushed to the
  registry (`gh attestation verify oci://ghcr.io/acme/app:X.Y.Z --repo <owner>/<repo>
  --signer-repo the-reacher-data/loom-actions`); in a private one, a notice. No storage record
  is created, so `artifact-metadata: write` is not needed.

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
