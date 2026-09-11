# Architecture: a fixed map over a changing codebase

```text
Authorized working tree             External coding agent
        │                             │ structured data
  cached scanner + watcher        authenticated publish / patch
        │                             │
        └──────── version-1 graph contract ───────┘
                         │ validation + optimistic revision check
                         ▼
               SQLite atomic revision store
            snapshots / deltas / source blobs / checkpoints
                         │ current HEAD invalidation (SSE)
                         ▼
                 fixed browser application
                   pure scope projection
                stable incremental placement
                   Cytoscape + HTML cards
                         │
                  explore → inspect → understand
```

## Separation

The server and scanner retain their version-1 interfaces. The renderer never scans source or asks a model to rebuild its UI. It consumes snapshots with IDs, parentage, relationships and evidence. `graph.js` projects those into the current scope; `map-view.js` renders them; `app.js` manages navigation and subscriptions. The Python tracker does not know the node-card design.

`Cytoscape.js` owns the interactive graph and its coordinate system. HTML overlays share those coordinates and provide accessible cards. Automatic layout is a Threadline projection/layout implementation, not a new dependency. All browser resources are vendored/local. The same files are used by every project and in read-only exports.

## Live correctness

The watcher polls authorized roots, caches unchanged analyses and publishes consistent observed batches. The database accepts the update atomically. SSE advertises current heads and health, not fragile in-memory graph-event history. The browser fetches a validated snapshot, computes its visual comparison, updates elements, and keeps the viewport and retained positions. If a stream is interrupted, the current database head remains authoritative and a reconciliation poll can catch up.

Source-batch observation does not preserve every keystroke. Revisions are graph/source observations, not necessarily Git commits; source identity retains base commit and working-tree hash. Captured text supports historical source inspection. Graph metadata and source retention can still contain private information.

## Progressive exploration

Root architecture groups modules and root entry files. Click a component to replace the frontier with its children and show relevant external dependencies. Internals never become a permanent list of every file. A feature switches to a labeled interpretation with actual supplied source links; it is not treated as a compiler-proven relationship.

A scope has explicit paging after 30 primary nodes and at most eight external context groups. The map does not pretend that unshown neighbors do not exist; scope captions expose additional relationships outside the current view. Cycles are condensed for rank assignment, not discarded from the graph.

## Change windows and history

`before` is a visual baseline held until dismissal/history navigation. A pure union adds removed baseline nodes temporarily for rendering. It never writes them back to the current source graph. Changed/added/removed classes can roll up to component cards. History and checkpoints open in a secondary drawer and do not affect the architecture node inventory.

The latest captured revision continues advancing during historical inspection; returning live fetches current HEAD. Source detail uses the requested revision and stored text, not live filesystem reads with stale line numbers.

## Example action

`POST /api/projects/{id}/demo-build` is limited to disposable bundled-example roots and requires an active watcher. It runs explicit staged file edits in a server thread. It does **not** create graph frames or explicitly scan; the ordinary observer supplies the data. It cannot mutate a separately registered user repository. It is labeled scripted, not AI. The two games are retained only as end-to-end workflow examples.

## Security and boundaries

Keep the service on loopback. Existing bearer/session authorization, origin/host checks, path boundaries, source/blob handling and conflict validation remain. No private source is automatically uploaded. Portable exports omit retained source blobs but can include sensitive metadata. No public multi-user hardening claim is made. See `SECURITY.md`, `DATA_CONTRACT.md`, `DESIGN.md` and `TEST_REPORT.md`.
