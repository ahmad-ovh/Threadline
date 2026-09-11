# Instructions for coding agents using Threadline

This repository is the reusable visualization application, not a canvas to regenerate for each project.

## The invariant
Install or locate this application once. For each authorized project, publish graph data or use its scanner. Do not copy/edit/regenerate `src/threadline/web/` merely to support a new repository. The data contract is in `schemas/graph.schema.json` and `docs/DATA_CONTRACT.md`.

## Workflow
1. Confirm the user-authorized repository root. `threadline projects` discovers existing registrations; do not blindly create duplicates.
2. Register and scan the root: `threadline add PATH --id ID`. Start `threadline serve` in a user-visible terminal/task. Do not claim the server is running until `/api/health` succeeds or the browser opens.
3. Use `threadline context ID --query TERM --limit 20` to locate a narrow neighborhood. Read source at its returned revision before editing.
4. Interpret features only after examining supporting source. Use `threadline feature ID --id FEATURE --name NAME --description TEXT --files PATHS` to create a reviewed mapping; it writes only the declared feature manifest, not viewer code. Never call a mapping a runtime proof.
5. Make the requested source changes using the user's normal development workflow. Report architectural additions or modifications via incremental `patch` events using the Skill CLI.
6. Re-check tests and source, update feature mappings only when reviewed, then make a named checkpoint. Never invent test results, commit identifiers, or extraction provenance.
7. Agents should report incremental structural changes using `patch` operations (`upsert_node`, `upsert_edge`, `remove_node`, `remove_edge`) with an informative summary and automatic or explicit expected revision.

## Privacy and safety
Do not export or publish project data without authorization. Graph labels, paths, descriptions and hashes can be sensitive even without source text. Never place the private store, session token, model keys, credentials, logs, or user source in this public application repository. Respect scan exclusions and `.threadlineignore`. Do not execute repository code merely to analyze it. Do not expose the local server to the internet.

## Graph viewer boundary
The primary experience is the live node graph. Single-click component navigation, source understanding, and in-place change visibility take precedence over additional tools. Do not add a persistent directory sidebar or rebuild the frontend per repository. Keep history and developer integration as supporting infrastructure.

## Development of Threadline itself
Run Python unit/integration tests and Node graph/game tests after changes.

## Distribution
Use `tools/connect.py` or the installable `threadline` Skill to acquire approved source and host locally. Never upload private stores or user source code. New runtime edits require intentional regeneration of `runtime-manifest.json`, a new tested version, and release/Skill rebuild. Ordinary per-project work should not modify the viewer.
