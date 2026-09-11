# WorkBuddy Integration Guide

## Overview

Threadline is integrated into **WorkBuddy** via the `threadline` Skill. In this architecture:
- **WorkBuddy codes. WorkBuddy reports. Threadline renders.**
- WorkBuddy is the single interface, agent, and orchestrator.
- Normal live updates do not depend on filesystem watching; WorkBuddy explicitly reports incremental architectural changes via the Threadline Skill (`patch`).
- Triggering `/threadline` automatically acquires/verifies the runtime, connects the current project, runs an initial deterministic scan, opens the Cytoscape viewer, and confirms readiness without manual setup.

## Package Contents
`skills/threadline/` is the installable Skill package directory (and packaged as `dist/threadline.zip`). It contains:
- `SKILL.md`: Skill definition and operational protocol for WorkBuddy.
- `scripts/threadline_connect.py`: Zero-friction workspace initialization and runtime manager.
- `scripts/threadline_cli.py`: Deterministic CLI wrapper for graph inspection, querying, patching, and checkpoints.
- `scripts/threadline_host.py`: Headless managed background server controller.
- `references/data-contract.md`: Schema definition for nodes, edges, features, and patch events.
- `references/installation.json`: Canonical GitHub repository coordinates (`https://github.com/ahmad-ovh/Threadline.git`).

## Installation in WorkBuddy
1. In WorkBuddy, navigate to **Skills** (专家·技能·连接器 → 技能 → 添加技能 → 上传技能).
2. Upload `dist/threadline.zip` (or point to the extracted `threadline/` directory).
3. The host environment requires Python 3.10+ and a local terminal with filesystem capability.

## How It Operates

### 1. Trigger & Setup
When the user types `/threadline` (or "initialize Threadline", "map this codebase"):
```powershell
py -3 skills/threadline/scripts/threadline_connect.py init --project .
```
This single command:
- Detects the current project directory and assigns a project ID.
- Automatically acquires or verifies the fixed Threadline runtime.
- Registers the project with Threadline and performs an initial deterministic scan.
- Spawns the local background viewer server (`127.0.0.1:8765`).
- Opens the viewer in the user's default browser.

### 2. Explicit Incremental Updates (`patch`)
When WorkBuddy modifies project architecture, it does not rely on imprecise file diffing. WorkBuddy directly patches the graph:
```powershell
py -3 skills/threadline/scripts/threadline_cli.py patch <project_id> --json '{
  "operations": [
    {"op": "upsert_node", "node": {"id": "src/auth.py", "type": "file", "label": "auth.py", "parentId": "src"}},
    {"op": "upsert_edge", "edge": {"id": "src/app.py->src/auth.py", "source": "src/app.py", "target": "src/auth.py", "type": "imports"}}
  ],
  "summary": "Add authentication module"
}'
```

### 3. Context & Architecture Queries
Before planning major refactors, WorkBuddy queries the graph for bounded architectural context:
```powershell
py -3 skills/threadline/scripts/threadline_cli.py context <project_id> --query "auth" --limit 15
```

### 4. Milestones & Checkpoints
When completing major milestones, WorkBuddy creates named checkpoints:
```powershell
py -3 skills/threadline/scripts/threadline_cli.py checkpoint <project_id> "Milestone Name" --note "Summary of changes"
```
