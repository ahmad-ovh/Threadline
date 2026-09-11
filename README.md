# Threadline — Live Reactive Codebase Architecture Map

> **AI can build your software for you, but understanding what it built can be the hard part.**  
> Threadline turns your project into a living map, so you can see how it works, changes, and comes together as the AI builds.

Unlike traditional AI coding assistants that dump walls of text or generate throwaway dashboards per project, Threadline maintains **one fixed, local Cytoscape-powered visualizer** that connects to any project, maintains revision history in SQLite, and updates live via Server-Sent Events (SSE).

---

## Why Threadline?

When coding agents generate or refactor hundreds of lines of code across multiple files, developers face a cognitive bottleneck: **loss of architectural context**. 

Threadline bridges the gap between agent speed and human comprehension:

- **See what was built:** Understand relationships, imports, and component hierarchies at a glance.
- **Watch changes as they happen:** New nodes glow **green**, modified dependencies show in **amber**, and deletions appear as contextual ghosts.
- **Stable layout:** Drag nodes into positions that make sense to your mental model; Threadline preserves your layout across updates rather than reshuffling your view.
- **Scrub history:** A revision scrubber at the bottom lets you step backward and forward through every architectural change.
- **Zero bloat:** One fixed local viewer reused across all your codebases. No throwaway frontends, no external cloud dependencies, no accounts.

---

## The WorkBuddy-First Architecture

Threadline is built around a **WorkBuddy-first** paradigm:

```text
                 WORKBUDDY
                     │
                     │ performs development
                     ▼
              CURRENT PROJECT
                     │
                     │
              threadline Skill
                     │
                     │ communicates structural changes
                     ▼
                THREADLINE
                     │
                     │ renders live via SSE
                     ▼
               FIXED VIEWER
```

### Core Principle:
> **WorkBuddy codes. WorkBuddy reports. Threadline renders.**

Threadline does not depend on guessing what changed via filesystem scanning during live development. WorkBuddy already understands the architectural modifications it is making, and explicitly reports them through the `threadline` Skill.

- **Initial State:** Built-in scanner maps the starting project architecture (Revision 1).
- **Live Development:** WorkBuddy sends atomic, incremental graph updates (`patch`) as it creates modules, functions, classes, and relationships.
- **Fixed Viewer:** Cytoscape graph updates live via SSE without full-page reloads, preserving layout positions and camera state.
- **Milestones:** Named checkpoints record architectural milestones alongside revision history.

---

## Features & Capabilities

| Capability | Description |
|---|---|
| **Click-Into Exploration** | Single-click any component or module to enter its isolated sub-graph with connected dependencies in context. |
| **Source Understanding** | Click a file node to inspect its declarations, import relationships, and retained source code directly in the viewer. |
| **In-Place Visual Diffing** | Highlights live additions in green and edits in amber without moving existing elements on the canvas. |
| **Atomic Revision Timeline** | Rewind through prior architectural revisions beneath the live map; return to live HEAD with one click. |
| **Bounded Context Queries** | Agents query Threadline for local dependency neighborhoods (`threadline context`) to avoid token window exhaustion. |
| **Milestone Checkpoints** | Label significant architectural accomplishments with named checkpoints that persist in history. |
| **Portable HTML Export** | Export a fully self-contained, single-file interactive HTML graph with zero server or network requirements. |

---

## Quick Start (Zero Setup)

### Prerequisites:
- Python 3.10+ with standard SQLite.
- A modern web browser.
- No node, npm, external databases, cloud services, or API keys required.

### 1. Standalone / Local Run
```powershell
# Windows PowerShell:
py -3 run.py serve --project "C:\Path\To\Your\Project" --id myproj --name "My Project"
```
Or start the bundled interactive demonstration games:
```powershell
py -3 run.py demo
```

### 2. WorkBuddy Integration
Install the `threadline` Skill in WorkBuddy (Skills → Upload Skill → `dist/threadline.zip`).

In WorkBuddy chat, simply type:
```text
/threadline
```

WorkBuddy will automatically:
1. Detect your current workspace directory.
2. Initialize or connect the local Threadline runtime.
3. Perform the initial baseline scan (Revision 1).
4. Launch the fixed live browser viewer.
5. Report architectural updates live as you and WorkBuddy code.

---

## Deterministic Update Protocol

Threadline exposes a clean, scriptable CLI and loopback HTTP API for agents.

### Incremental Structural Patch:
```powershell
py -3 skills/threadline/scripts/threadline_cli.py patch myproj --json '{
  "operations": [
    {
      "op": "upsert_node",
      "node": {"id": "src/auth.py", "type": "file", "label": "auth.py", "parentId": "src"}
    },
    {
      "op": "upsert_edge",
      "edge": {"id": "routes-import-auth", "source": "src/routes.py", "target": "src/auth.py", "type": "imports"}
    }
  ],
  "summary": "Add authentication service and wire into routes"
}'
```

### Bounded Context Discovery:
```powershell
py -3 skills/threadline/scripts/threadline_cli.py context myproj --query "auth" --limit 15
```

### Checkpoints:
```powershell
py -3 skills/threadline/scripts/threadline_cli.py checkpoint myproj "v1.0 Milestone" --note "Authentication completed"
```

### Standalone Portable HTML Export:
```powershell
py -3 skills/threadline/scripts/threadline_cli.py export myproj --format html --out ./architecture-map.html
```
The exported HTML is completely self-contained, requiring no server or network connection to view.

---

## Security and Privacy

- **100% Local Loopback:** All API endpoints bind strictly to `127.0.0.1`.
- **Zero Cloud Transmission:** No source code, project metadata, or credentials leave your machine.
- **Session Authentication:** Authenticated with random local bearer tokens stored in `~/.threadline/session.token` with strict HttpOnly cookies.
- **Export Safety:** Portable exports retain architecture metadata and hashes, omitting raw source text bodies.

---

## Running Tests

```powershell
# Python unit tests
py -3 -m unittest discover -s tests -p "test_*.py"

# Node.js graph and UI layout tests
node tests/frontend.test.cjs
node tests/games.test.mjs
```

---

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See [LICENSE](LICENSE) for details.
