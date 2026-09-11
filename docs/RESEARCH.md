# Foundation research record

**Version 2 update:** the current graph-first product decision and graph-library evaluation are in [DESIGN.md](DESIGN.md). This document preserves the earlier technical/competition basis; it is not the version-2 UI specification.

Research date: 2026-09-10. This document separates supplied competition wording, published technical documentation and our design decisions. None of these sources proves that the application was imported in an actual WorkBuddy account.

## Original product foundation

**Threadline 1.0: one reusable, local-first viewer for living codebases.** It renders source-linked Modules/Features views from a stable contract. An independent publisher/scanner maintains current state, atomic observed revisions and named checkpoints. Source-backed relationships and agent-authored feature interpretations remain distinguishable. The interface never needs to be regenerated for each project.

Scope: one local developer, multiple authorized projects; source/data observation, not universal semantic or runtime analysis. Preserve the history instead of promoting events to architectural nodes. Keep features small and source-backed. Python standard library plus fixed browser assets avoids per-project frontend builds and hosted runtime dependencies.

## Source ledger

| Primary source | Publisher / date | What it supports | What it does NOT establish |
|---|---|---|---|
| Supplied Chinese global-finals briefing, pp10–14 | Tencent competition material; no separate publication date supplied | Production workbench derived from preliminary AI use; H5/ZIP; Skill/prompts + another-game runnable demo + docs; separate creative workbench also required | Approval of Threadline, native import steps, a verified THRESHOLD integration |
| https://open.workbuddy.cn/docs/skill | WorkBuddy official developer documentation; retrieved 2026-09-10 | Chinese Skill directory/YAML/resource pattern and host integration intent | Actual compatibility of the recipient's account/client; exact competition Workbench export |
| https://open.workbuddy.cn/en/docs/skill | WorkBuddy official English developer documentation; retrieved 2026-09-10 | Corroboration of Skill fields including bilingual descriptions, version and author | Authority over discrepant Chinese competition wording |
| https://docs.python.org/3/library/sqlite3.html | Python Software Foundation; current documentation retrieved 2026-09-10 | Standard-library SQLite connection, transactions and persistence mechanisms | That this code is a distributed database or encrypted store |
| https://docs.python.org/3/library/http.server.html | Python Software Foundation; retrieved 2026-09-10 | Local HTTP handler mechanism; explicit warning against production use | An internet-facing production security guarantee |
| https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events | MDN platform documentation; retrieved 2026-09-10 | Event stream syntax and browser connection/reconnection model | Durable event delivery; our SQLite history supplies durability separately |
| https://git-scm.com/docs/git-ls-files | Git official documentation; retrieved 2026-09-10 | Enumerating tracked/untracked files while respecting Git exclusions | A complete or atomic OS filesystem snapshot |
| https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html | Godot official documentation; retrieved 2026-09-10 | Resource paths and explicit load/preload concepts | Complete Godot runtime signal/call resolution or testing on THRESHOLD |

The Chinese Skill page was available through indexed excerpts during research; one later direct fetch returned a cache miss. English official field documentation was corroborative, not a replacement for the Chinese competition specification. Runtime library pages can move beyond the tested Python version; Threadline only uses APIs available from the declared Python 3.10 minimum.

## Engineering decisions, not Tencent rules

- SQLite transactions enforce all-or-nothing revision publication and optimistic concurrency. Each accepted revision retains a compressed graph and delta. It is append-only through this application, not tamper-proof against a user editing the database.
- SSE tells viewers the current heads; on reconnect they reconcile those heads. It is deliberately not the permanent history log.
- The publisher interface is CLI/JSON/HTTP, not an undocumented MCP implementation. The Skill operates a terminal tool supplied by its host.
- Static extraction handles a bounded set of references; feature descriptions remain explicit interpretations. Hash changes surface stale mappings.
- The sample games are original small JavaScript games authored for this release. They are not THRESHOLD and not historical competition entries.
- No LLM provider is embedded. An actual host agent can supply interpretation through the documented Skill/data interface. Built-in example changes are scripted and labeled.
- No claim of unique invention or measured token savings. Reusing the viewer avoids generating its frontend again; total agent cost requires a separately controlled comparison.

## Remaining external verification

Actual WorkBuddy import/terminal execution, recipient platform behavior and organizer acceptance need a receiver test. The full THRESHOLD repository was not supplied. Attach it through the local scanner and inspect its actual feature mappings rather than extrapolating from the examples. This package does not provide the separate creative workbench, a team-specific competition report, a recorded submission video or a public repository URL.
