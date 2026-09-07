# 🚀 Release 1.2.0 ([#27](https://github.com/the-reacher-data/loom-actions/pull/27)) ([`70d2b11`](https://github.com/the-reacher-data/loom-actions/commit/70d2b11807373845aaed4d619872985922939927))


## ✨ Features
### release
- **release:** a reusable release for every trunk-based repository<br>
  > Merging a pull request that carries the release label publishes everything
  > merged since the last tag. The version is derived from the branches the range
  > ships, taking the highest part any of them asks for, so a batch holding a
  > feature never goes out as a patch.
  > Publishing to PyPI is opt-in and off by default. A repository that ships an
  > application, not a package, gets the tag, the notes and the GitHub release and
  > never builds a distribution — so it needs no index account, no trusted
  > publisher and no secret. Asking to publish without a package name fails
  > closed, because the built version could not then be checked against the tag.
  > The planner moves here from loom-py: a workflow reusable by other repositories
  > cannot read a script that lives in one of them.
  > Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  > Claude-Session: https://claude.ai/code/session_016xY1skW5S2PU9Fc3M7tfAW












# 🚀 Release 1.1.2 ([#25](https://github.com/the-reacher-data/loom-actions/pull/25)) ([`6260f7c`](https://github.com/the-reacher-data/loom-actions/commit/6260f7cf2774d652fc08246a6748c6e1dab646f5))



## 🐛 Fixes
### quality-report
- **quality-report:** adopt results that already sit in the workspace










# 🚀 Release 1.1.1 ([#23](https://github.com/the-reacher-data/loom-actions/pull/23)) ([`a0c0d6d`](https://github.com/the-reacher-data/loom-actions/commit/a0c0d6de35ff2a1acc62d4f857d5d63d1c08f4ef))



## 🐛 Fixes
### actions
- **actions:** pass every caller-supplied input through the environment










# 🚀 Release 1.1.0 ([#19](https://github.com/the-reacher-data/loom-actions/pull/19)) ([`90dbb02`](https://github.com/the-reacher-data/loom-actions/commit/90dbb0292cbf5ffe46975fe826ae8ac1732bb80e))


## ✨ Features
### quality-report
- **quality-report:** report test results produced elsewhere











# 🚀 Release 1.0.6 ([#20](https://github.com/the-reacher-data/loom-actions/pull/20)) ([`4af5799`](https://github.com/the-reacher-data/loom-actions/commit/4af57995f0565c02fb52dc355c6a02f94433f51c))



## 🐛 Fixes
### release
- **release:** pass the merged branch name through the environment










# 🚀 Release 1.0.5 ([#17](https://github.com/the-reacher-data/loom-actions/pull/17)) ([`b355b14`](https://github.com/the-reacher-data/loom-actions/commit/b355b14ed42098bc3d09d1aba1a71727a643358a))


## ✨ Features
### ai
- **ai:** pluggable MCP server authentication (#139)<br>
  > So a well-formed feat produced a changelog with a header and nothing under it.
  > The fallback now fires when no collected entry lands in a type the template
  > renders, not merely when the list is empty. A squash subject is always the PR
  > title; a squash body is free text anyone can write, and a single "Word: " line
  > was enough to swallow the release.
  > Verified by reverting the one-line condition: the new test fails against the
  > old behaviour and passes against the new one.
  > Claude-Session: https://claude.ai/code/session_01TLAapySqoC4wWTLxydLka3
  > Co-authored-by: Claude Fable 5 <noreply@anthropic.com>












# 🚀 Release 1.0.4 ([#14](https://github.com/the-reacher-data/loom-actions/pull/14)) ([`17779af`](https://github.com/the-reacher-data/loom-actions/commit/17779af7110d8f5f69c7cb5fa235f71825b42a9b))









## 🛠 Chores
- remove release badge from readme




# 🚀 Release 1.0.3 ([#12](https://github.com/the-reacher-data/loom-actions/pull/12)) ([`cfb2dc7`](https://github.com/the-reacher-data/loom-actions/commit/cfb2dc7c6c5c3a05a368449cd5890d07458eaa8d))









## 🛠 Chores
- normalize badges and auto-delete release branches
- label release PRs with target version
- simplify ruff and pyright section headers in report




# 🚀 Release 1.0.2 ([#10](https://github.com/the-reacher-data/loom-actions/pull/10)) ([`ea98554`](https://github.com/the-reacher-data/loom-actions/commit/ea985547d823e60b7e68b4c8f53510fc20013925))


## ✨ Features
- improve PR quality report UX layout








## 🛠 Chores
- refine workflow badges and no-background tooling icons




# 🚀 Release 1.0.1 ([#8](https://github.com/the-reacher-data/loom-actions/pull/8)) ([`63d6d1a`](https://github.com/the-reacher-data/loom-actions/commit/63d6d1aeb44e9a5c1f01d81e51bad3c1b40ba5b3))



## 🐛 Fixes
- use bot token for release PR chaining










# 🚀 Release 1.0.0 ([#6](https://github.com/the-reacher-data/loom-actions/pull/6)) ([`32cfe40`](https://github.com/the-reacher-data/loom-actions/commit/32cfe40037519e4ea44bbe6f9509d99ffbf311d7))


## ✨ Features
- standardize release docs and auto-merge release PR











# 🚀 Release 0.1.1 ([#4](https://github.com/the-reacher-data/loom-actions/pull/4)) ([`c476454`](https://github.com/the-reacher-data/loom-actions/commit/c4764540f51594199ec54bfdfd95edd4a87c2262))



## 🐛 Fixes
- trigger release for release-pr file-only merges
- trigger release from merged PR context<br>
  > --------
  > Co-authored-by: Administrador <administrador@MacBook-Pro-de-Administrador.local>
