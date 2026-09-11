---
name: threadline
display_name: Threadline 实时代码库地图
display_name_en: Threadline Live Codebase Map
description: AI can build your software for you, but understanding what it built can be the hard part. Threadline turns your project into a living map, so you can see how it works, changes, and comes together as the AI builds.
description_zh: AI 能帮你编写软件，但理解它构建了什么往往是最难的。Threadline 将你的项目变成一张活生生的代码库架构地图，让你在 AI 编写代码的同时，实时看清各组件如何连接、演进并协同工作。
description_en: AI can build your software for you, but understanding what it built can be the hard part. Threadline turns your project into a living map, so you can see how it works, changes, and comes together as the AI builds.
version: 2.1.0
author: Threadline contributors
triggers:
  - /threadline
user-invocable: true
---

# One viewer. The live map of what is being built.

> **AI can build your software for you, but understanding what it built can be the hard part.**  
> Threadline turns your project into a living map, so you can see how it works, changes, and comes together as the AI builds.

Use this Skill to connect your codebase to Threadline, maintain a live architecture graph as you write code, inspect revisions, navigate bounded context, and export self-contained architecture handoffs.

The **same fixed application** is reused across all projects. It does not create a new frontend for each task.

---

## 1. Core Architecture & Mental Model

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

- **WorkBuddy is the single interface, agent, and orchestrator.** WorkBuddy performs all coding and development tasks.
- **Threadline is the rendering and state engine.** It maintains graph state, SQLite revisions, and streams live updates via SSE to the fixed Cytoscape viewer.
- **The Core Invariant:**
  > **WorkBuddy codes. WorkBuddy reports. Threadline renders.**
- **Threadline does not notice. WorkBuddy reports.** Do not wait for or depend on a filesystem watcher for live synchronization. WorkBuddy already understands the structural modifications it makes, so WorkBuddy explicitly communicates meaningful architectural changes to Threadline.

---

## 2. Initial Invocation (`/threadline`)

When the user types `/threadline` or requests architecture tracking:

WorkBuddy executes:

```sh
python <SKILL_DIR>/scripts/threadline_connect.py connect
```

Or with explicit paths when needed:
```sh
python <SKILL_DIR>/scripts/threadline_connect.py connect --project "/path/to/project" --id project-id --name "Project Name"
```

### What WorkBuddy and Threadline do automatically:
1. **Detect Workspace:** Identifies the current project directory and assigns a clean lowercase project ID.
2. **Runtime Acquisition:** Locates or fetches the official Threadline runtime from `https://github.com/ahmad-ovh/Threadline.git` into `~/.threadline-tools/releases/`, validating hashes against `runtime-manifest.json`.
3. **Local Loopback Daemon:** Starts the private loopback server on `http://127.0.0.1:7331` (or reuses existing running instance).
4. **Initial Project Scan:** Runs the built-in Threadline scanner to establish the baseline architecture snapshot at Revision 1.
5. **Viewer Launch:** Opens the live browser viewer using `~/.threadline/open-viewer.html` without leaking bearer tokens.
6. **Confirmation:** Confirms to the user that Threadline is active, reporting the viewer link and project ID.

No manual cloning, no `.bat` running, no manual prompt copying, and no manual browser refreshing are needed.

---

## 3. Live Development: WorkBuddy Reports Structural Changes

After initialization, WorkBuddy explicitly communicates structural changes to Threadline using the Threadline update protocol.

### When to Update Threadline:
Communicate changes to Threadline whenever you:
- Create a new module, package, or directory
- Create a new file or component
- Define or modify a class or major function
- Delete or remove a component/file
- Move or rename a component
- Add, change, or remove imports/dependencies
- Change an architectural boundary or API contract
- Add or update a feature mapping

### When NOT to Update:
- **Do not update after every single line or character write.**
- Batch related changes into a single meaningful structural update (e.g. after creating a service and updating its callers).

---

## 4. The Threadline Update Protocol (`patch`)

To send an incremental architectural update, use `threadline_cli.py patch`:

```sh
python <SKILL_DIR>/scripts/threadline_cli.py patch <PROJECT_ID> --json '<PATCH_JSON>' --summary '<SUMMARY>'
```

Or write a temporary patch file and pass it:
```sh
python <SKILL_DIR>/scripts/threadline_cli.py patch <PROJECT_ID> patch.json --summary '<SUMMARY>'
```

### Patch JSON Schema:
```json
{
  "upsertNodes": [
    {
      "id": "file:src/auth/service.ts",
      "kind": "file",
      "label": "service.ts",
      "path": "src/auth/service.ts",
      "parent": "module:src/auth"
    },
    {
      "id": "symbol:src/auth/service.ts#AuthService",
      "kind": "symbol",
      "label": "AuthService",
      "path": "src/auth/service.ts",
      "parent": "file:src/auth/service.ts"
    }
  ],
  "removeNodes": [],
  "upsertEdges": [
    {
      "id": "routes-imports-auth",
      "source": "file:src/api/routes.ts",
      "target": "file:src/auth/service.ts",
      "kind": "imports",
      "evidence": []
    }
  ],
  "removeEdges": [],
  "source": {
    "publisher": "WorkBuddy"
  }
}
```

### Node Kinds:
- `module`: directories / packages (`id: "module:src/auth"`, `parent: "module:src"`)
- `file`: source files (`id: "file:src/auth/service.ts"`, `parent: "module:src/auth"`)
- `symbol`: classes / functions / interfaces (`id: "symbol:src/auth/service.ts#AuthService"`, `parent: "file:src/auth/service.ts"`)
- `feature`: logical user-facing feature (`id: "feature:user-authentication"`)
- `document`: documentation files (`id: "file:docs/auth.md"`)

### Relationship Kinds:
- `contains`: module contains file, or file contains symbol
- `declares`: file declares class/function
- `imports`: file imports another file
- `calls`: symbol calls another symbol
- `depends_on`: module depends on another module
- `implements`: feature implements file/symbol
- `references`: file references asset/file

### Examples of Incremental Updates:

#### 1. Adding a new module and service:
```sh
python <SKILL_DIR>/scripts/threadline_cli.py patch myproj --json '{
  "upsertNodes": [
    {"id": "module:src/auth", "kind": "module", "label": "auth", "path": "src/auth", "parent": "module:src"},
    {"id": "file:src/auth/service.ts", "kind": "file", "label": "service.ts", "path": "src/auth/service.ts", "parent": "module:src/auth"}
  ],
  "upsertEdges": [
    {"id": "routes-import-auth", "source": "file:src/routes.ts", "target": "file:src/auth/service.ts", "kind": "imports"}
  ]
}' --summary "Add authentication module and service"
```

#### 2. Removing a deprecated component:
```sh
python <SKILL_DIR>/scripts/threadline_cli.py patch myproj --json '{
  "removeNodes": ["file:src/legacy/session.ts"],
  "removeEdges": ["routes-import-legacy-session"]
}' --summary "Remove legacy session handler"
```

---

## 5. Checkpoints, Context & History

### Labeling Milestones (Checkpoints):
After completing a feature or milestone, label a checkpoint:
```sh
python <SKILL_DIR>/scripts/threadline_cli.py checkpoint <PROJECT_ID> "Auth refactor complete" --note "Implemented JWT tokens and updated API routes"
```

### Context Queries for Development:
Query bounded graph context to discover related components before modifying code:
```sh
python <SKILL_DIR>/scripts/threadline_cli.py context <PROJECT_ID> --query "auth" --limit 15
```

### Inspecting History and Diffs:
```sh
python <SKILL_DIR>/scripts/threadline_cli.py history <PROJECT_ID> --limit 10
python <SKILL_DIR>/scripts/threadline_cli.py diff <PROJECT_ID> <PREVIOUS_REV> <CURRENT_REV>
```

### Full Reconciliation Scan:
If you need to reconcile the graph with all current files on disk (e.g. after a large git branch switch):
```sh
python <SKILL_DIR>/scripts/threadline_cli.py scan <PROJECT_ID> --summary "Reconcile project files"
```

---

## 6. Failure Handling & Resilience

Threadline is an observability and visualization layer. **A Threadline failure must never corrupt or block the user's actual project work.**

If a Threadline command fails:
1. **Detect & Log:** Check error output.
2. **Retry Once:** If transient, retry the command.
3. **Attempt Reconnect:** Run `python <SKILL_DIR>/scripts/threadline_connect.py connect` to re-establish the loopback connection.
4. **Preserve Code:** If Threadline remains unavailable, proceed with the user's coding request and preserve all file edits.
5. **Inform User:** Transparently inform the user:
   > "Project changes completed successfully. Threadline live update is temporarily unavailable and will sync when reconnected."

---

## 7. Handoff & Shutdown

### Export Portable Architecture Map:
Generates a standalone, offline HTML architecture map:
```sh
python <SKILL_DIR>/scripts/threadline_cli.py export <PROJECT_ID> --format html --out ./architecture-map.html
```

### Stop Threadline Server:
```sh
python <SKILL_DIR>/scripts/threadline_connect.py stop
```
Stopping the server preserves all SQLite history and revisions for future sessions.

