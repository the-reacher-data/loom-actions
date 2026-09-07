# Publishing from a caller

`release-on-label.yml` plans the release, tags it, writes the notes and creates the
GitHub release. With `build-distribution: true` it also builds a distribution and
leaves it as the `distributions` artifact of the run.

It does **not** upload it, and cannot: PyPI's trusted publishing does not support
reusable workflows. The OIDC token minted for a reusable workflow names that workflow,
not the caller's, so PyPI answers

```
invalid-publisher: valid token, but no corresponding publisher
```

no matter how the trusted publisher is configured. Observed on loom-py's v1.11.0.

So the caller publishes, in its own workflow file, which is the file PyPI's trusted
publisher names:

```yaml
jobs:
  release:
    permissions:
      contents: write
    uses: the-reacher-data/loom-actions/.github/workflows/release-on-label.yml@<sha>
    with:
      build-distribution: true
      package-name: loom-kernel

  publish:
    needs: release
    if: ${{ needs.release.result == 'success' }}
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@<sha>
        with:
          name: distributions
          path: dist
      - uses: pypa/gh-action-pypi-publish@<sha>
```

The trusted publisher on PyPI names the **caller's** workflow file — `release.yml`, not
`release-on-label.yml`.

A repository that ships an application leaves `build-distribution` off and needs none of
this: it gets the tag, the notes and the GitHub release, and no index account.
