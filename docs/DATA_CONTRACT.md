# Threadline data contract 1.0

The public contract belongs to the project, not to Tencent. `schemas/graph.schema.json` and `schemas/patch.schema.json` provide machine-readable shapes. The runtime also validates uniqueness, endpoint/parent existence, parent acyclicity, safe relative paths, hash formats and evidence ranges. Structural validation is not semantic proof of the publisher's claims.

## Snapshot

```json
{
  "schemaVersion": "1.0",
  "project": {"id": "my-game", "name": "My Game"},
  "source": {
    "treeHash": "producer-defined-source-state-identity",
    "commit": null,
    "branch": null,
    "dirty": true,
    "publisher": "my-analyzer"
  },
  "nodes": [
    {"id": "module:src", "kind": "module", "label": "src", "path": "src"},
    {"id": "file:src/game.js", "kind": "file", "label": "game.js", "path": "src/game.js", "parent": "module:src"}
  ],
  "edges": [
    {"id": "contains-game", "source": "module:src", "target": "file:src/game.js", "kind": "contains", "evidence": []}
  ]
}
```

Paths use relative POSIX separators. Absolute paths, `..`, backslashes, drive-letter roots and control characters are rejected. Use stable IDs across updates. The built-in scanner uses `module:PATH`, `file:PATH`, `symbol:PATH#QUALIFIED_NAME`, and `feature:ID`; external publishers may choose their own stable IDs. Labels are plain text, never executable HTML.

### Node kinds
`module`, `file`, `symbol`, `feature`, `document`.

Useful fields include `parent`, `path`, `hash` (SHA-256), `line`, `endLine`, `language`, `summary`, `evidence`, `status`, and `author`. Feature nodes can refer to several files through `implements` relationships; a feature is not merely a deeper folder.

### Relationship kinds
`contains`, `declares`, `imports`, `references`, `implements`, `documents`, `calls`, `depends_on`.

The built-in scanner does not emit a complete `calls` graph. Producers that publish stronger relationships must supply their own analysis and accurately label its limits. A relationship has an ID, existing source and target node IDs, a kind, and optional evidence.

### Evidence

```json
{
  "path": "src/game.js",
  "line": 3,
  "hash": "64 lowercase hexadecimal characters, when known",
  "method": "js-literal-reference",
  "status": "lexical",
  "reference": "./memory.js"
}
```

The hash placeholder above is explanatory, not valid literal data. `status` is one of `observed`, `lexical`, `interpretation`, `stale`, or `unverified`. `line` is one-based. A publisher must not claim that an inferred feature description is an observed runtime fact.

## Publishing through the CLI

```sh
threadline create custom-game --name "Custom analyzer game"
threadline publish custom-game snapshot.json --expected 0 --event-id init-001 --summary "Initial graph"
threadline patch custom-game patch.json --expected 1 --event-id change-002 --summary "Memory helper extracted"
```

The snapshot's `project.id` must equal the target ID. A filesystem-owned project cannot be raw-published into; use its feature manifest or a separate published project.

## Atomic patch

```json
{
  "upsertNodes": [
    {"id": "file:src/helper.js", "kind": "file", "label": "helper.js", "path": "src/helper.js", "parent": "module:src"}
  ],
  "removeNodes": [],
  "upsertEdges": [
    {"id": "helper-import", "source": "file:src/game.js", "target": "file:src/helper.js", "kind": "imports", "evidence": []}
  ],
  "removeEdges": [],
  "source": {"treeHash": "a-new-source-state", "commit": null, "publisher": "my-analyzer"}
}
```

Upserts replace the complete node/relationship object with that ID. Deletions are explicit. Remove incident edges and reparent/delete children in the **same batch** when removing a referenced node; dangling references reject the entire patch. Only the listed operations are supported; this is not RFC 6902 JSON Patch.

## Local HTTP
All project data requires the local bearer token or same-origin session cookie. The token is stored in the private home, never in graph data. The body cap is 16 MiB. Host/Origin checks and no cross-origin sharing are deliberate.

| Method and endpoint | Body / result |
|---|---|
| `GET /api/health` | Public local health/version only |
| `POST /api/session` | Bearer token → HttpOnly same-origin session |
| `GET /api/projects` | Projects, current revisions, watcher health |
| `POST /api/projects` | `{id,name,mode:"published"}`; filesystem registration is CLI-only |
| `GET /api/projects/ID/snapshot?revision=N` | Current or historical graph |
| `POST /api/projects/ID/publish` | `{snapshot,expectedRevision,eventId,summary,actor}` |
| `POST /api/projects/ID/patch` | `{patch,expectedRevision,eventId,summary,actor}` |
| `POST /api/projects/ID/scan` | Explicit filesystem scan; `{summary,force}` |
| `GET /api/projects/ID/history?limit=200&before=N` | Descending events; `nextBefore` for pagination |
| `GET /api/projects/ID/delta?revision=N` | Before/after objects for one revision |
| `GET /api/projects/ID/diff?from=N&to=M` | Graph difference across revisions; 0 means empty initial graph |
| `POST /api/projects/ID/checkpoint` | `{name,note,revision?}` |
| `GET /api/projects/ID/checkpoints` | Named milestones and ranges |
| `GET /api/projects/ID/source?path=P&revision=N` | Retained text for an indexed path at that graph revision |
| `GET /api/projects/ID/context?q=TEXT&node=ID&depth=1&limit=30` | Bounded navigation context |
| `GET /api/projects/ID/export?history=true` | Portable bundle without source-text blobs |
| `GET /api/stream` | SSE `state` events with current heads and tracker health |

Use `q` or `node` for context. A node-centered query includes a bounded undirected neighborhood; search matches labels, paths and descriptions. `depth` is capped at 3; `limit` at 200. `truncated` reports a capped result. This is a node count limit, not a measured token budget.

An external publish/patch requires `expectedRevision` and an `eventId` of your choice. Successful repeat delivery of the same request returns its original revision with `duplicate:true`. Same key with different content or a stale expected revision produces HTTP 409. Invalid graph/patch data returns 400 with no partial write. No-op publications return `changed:false`; only accepted structural/source changes create revisions.

The scanner and the browser are separate. A custom agent can use these endpoints without a WorkBuddy account and without changing the viewer. `scripts/publish_example.py` demonstrates the real protocol.

## Checkpoints and exports
Checkpoints name an existing revision and retain a start/end range. Multiple names may refer to the same revision. They never rewrite or delete history.

JSON bundles use `format:"threadline-bundle"`, `version:"1.0"`, `snapshot`, `history`, `checkpoints`, and optional `snapshots`/`deltas` keyed by revision. A workspace preview may use `format:"threadline-workspace"` with multiple bundles. The exporter includes at most the latest 1,000 revisions and sets `historyTruncated` when older revisions were omitted; the underlying store remains intact. Browser imports are capped at 64 MiB. Use `--no-history` for large graphs.

Graph exports contain relative paths, labels, summaries and hashes but no retained source bodies. Do not mistake “source-text-free” for “contains no sensitive information.”
