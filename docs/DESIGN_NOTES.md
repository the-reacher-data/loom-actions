# Design notes

Decisions that are easier to re-litigate than to remember. Each one records what was
considered and why it was refused, so the next person does not rediscover it.

## Refused: moving tool execution out of `quality-report`

`quality-report` both runs the tools (ruff, pyright, pytest, bandit) and renders the report.
The cleaner factoring is to split those: `src/builder.py` already takes tool output as JSON,
so a caller could run the tools itself and this action would only render and gate.

It was refused. Consumers pinned to `v1.0.5` rely on the action running the tools, so the
split is a breaking change and would be a `v2.0.0` with a migration nobody asked for. The
`test-results-dir` input reaches the same result for a caller that wants it and costs every
other consumer nothing.

## Refused: wheels-only installs

The intent was to stop source builds on the runner. It cannot be done as stated. `uv` offers
a deny-list (`--no-build-package`) but no allow-list, so "no source builds except these" is
not expressible, and the packages that need one are real: `antlr4-python3-runtime` 4.9.3
ships no wheel and is a transitive requirement of `omegaconf`, and `pyspark` is distributed
as an sdist. A blanket ban would break any consumer whose graph contains either.

What is enforced instead is the lockfile: with `--frozen` the caller's committed resolution
is what gets installed, so what builds is what the caller reviewed and locked.

## What cannot be tested here

These are exercised by a real release and by nothing else. They are listed so nobody reads
their absence as coverage:

- publishing to PyPI;
- pushing an immutable version tag;
- moving the floating major tag;
- creating a GitHub Release;
- the merge event that a release label triggers, which needs a genuinely merged pull request.

Secret-dependent stages — Sonar, Snyk, TestPyPI — cannot run in a fixture pipeline that has
no tokens. When they are skipped they must **say so**, in the job summary and as an
annotation, never appear as a green check. A green tick nobody can act on is worse than a
missing one: it reports a scan that never happened.
