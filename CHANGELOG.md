# 🚀 Release 1.2.3 ([#33](https://github.com/the-reacher-data/loom-actions/pull/33)) ([`facf1a8`](https://github.com/the-reacher-data/loom-actions/commit/facf1a8c5d86658099fcfa9205ea9aad5e55da33))



## 🐛 Fixes
### release
- **release:** let a commit's breaking marker raise the version










# 🚀 Release 1.2.2 ([#31](https://github.com/the-reacher-data/loom-actions/pull/31)) ([`e594096`](https://github.com/the-reacher-data/loom-actions/commit/e59409611f0de4ecffe889dd0c7734fb23d9bd09))



## 🐛 Fixes
### release
- **release:** let a re-run of a tagged release plan the same version<br>
  > Recovering a release that stopped after tagging was documented as a dispatch
  > with the merge SHA, and it could not work: the planner read the highest tag
  > reachable from that commit, which now included the tag the halted run had just
  > created, so the range was empty and the run refused with "nothing to release".
  > loom-py's v1.11.0 is in exactly that state — tagged and released, never
  > uploaded.
  > A tag pointing at the commit being released is not a release that preceded it,
  > so it is ignored when choosing the previous tag. The re-run then plans the same
  > version, finds the tag already pointing at the right commit, and carries on to
  > the upload.
  > Removing the guard turns two tests red. The empty-range refusal is now
  > unreachable through this path, so its test asserts what the code does instead:
  > a commit carrying the only tag is planned from the start of history.
  > Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  > Claude-Session: https://claude.ai/code/session_016xY1skW5S2PU9Fc3M7tfAW

- **release:** the same tag-on-HEAD defect, in the copy nobody tested<br>
  > An independent audit found the fix for the previous commit landed in one of two
  > places. build_release_notes.py has its own latest_release_tag, with the same
  > rule and the same bug: the action detaches at the released commit and runs it,
  > so a re-run for an already tagged commit read its own tag as the previous
  > release, saw an empty range, and refused. The next dispatch would have died in
  > the plan job, before the tag step, before the upload.
  > That module had no test file at all, which is why the bug survived a fix aimed
  > at itself. It has nine now, including the re-run.
  > The reusable workflow also called its own action at @master while callers pin
  > the workflow by SHA, so unreviewed action code reached a pinned release. It
  > tracks the floating major tag instead, and a test refuses master. A caller can
  > now read whether a distribution was built rather than inferring it from the
  > aggregate result of the called workflow.
  > Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  > Claude-Session: https://claude.ai/code/session_016xY1skW5S2PU9Fc3M7tfAW
  > --------
  > Co-authored-by: Claude Opus 5 <noreply@anthropic.com>











# 🚀 Release 1.2.1 ([#29](https://github.com/the-reacher-data/loom-actions/pull/29)) ([`eb68725`](https://github.com/the-reacher-data/loom-actions/commit/eb6872566d79eb09bae5b68ffa73362c407b0eea))



## 🐛 Fixes
### release
- **release:** leave the upload to the caller, which PyPI can recognise










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
