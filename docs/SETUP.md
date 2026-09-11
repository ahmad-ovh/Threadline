# Setup and receiving-team guide

## Requirements
Python 3.10 or later with `sqlite3`, a modern browser with Canvas, dialog, ResizeObserver and EventSource support, and a local filesystem. Git is optional: without it, content-derived identities still work but commit/branch fields are null. No account or API key is needed for the viewer or the included examples. An AI coding host is needed only for agent-driven interpretation and authoring.

## From the ZIP
Extract the entire directory. Run `python run.py demo`. Use `python3` on systems where that is the Python 3 command, or `py -3` on Windows. The included `start.sh` and `start.bat` launch the same command. Keep the terminal open. Opening `src/threadline/web/index.html` alone does not start tracking; use `preview.html` for the intentionally read-only fallback.

The server binds only to `127.0.0.1`. The printed URL includes a token in the fragment. The application exchanges it for an HttpOnly, SameSite=Strict local cookie and removes the fragment from browser history. Subsequent API calls and the SSE stream require the local session. Do not share the token or the private data directory.

If port 7331 is busy: `python run.py demo --port 7332`. The health endpoint is `http://127.0.0.1:7332/api/health` and reveals no project data.

## Install once
A prebuilt pure-Python wheel is included:

```sh
python -m pip install dist/threadline_workbench-2.0.0+threshold.1-py3-none-any.whl
threadline demo
```

There are no wheel runtime dependencies. There is no published PyPI package or public repository URL claimed by this release. To work directly from source, installation is optional; `python /path/to/threadline/run.py ...` is sufficient.

## Connect the actual THRESHOLD project

```sh
threadline add "/path/to/THRESHOLD" --id threshold --name THRESHOLD
threadline serve
```

No code import or engine conversion is required. The scanner inventories the chosen root. It does not launch Godot, import assets into an engine, execute Python files, or call the game backend. Godot literal resource paths and Python/FastAPI source can appear in the same graph; cross-runtime relationships not expressed as supported source references need honest, source-backed feature mappings or an external publisher.

To add a second codebase while the viewer is running, run another `threadline add ...` command using the same private home. The watcher discovers it. Select the new project in the unchanged viewer.

## Private store
The default is `~/.threadline`. Override it with `THREADLINE_HOME`, or use the global option **before** the subcommand:

```sh
threadline --home "/private/threadline-data" serve
```

The store contains `threadline.sqlite3`, SQLite WAL/SHM sidecars while running, `session.token`, and disposable example copies under `workspaces/`. It includes retained source text from indexed text files. Stop all Threadline processes before copying/removing the whole directory. Prefer a private local disk; network-filesystem locking has not been validated. Removing the store deletes its retained history. Checkpoints do not delete history.

## Scan exclusions
Always excluded: symlinked files/directories, hidden directories/files, dependency/build folders, common credential/key filename patterns, files over 1 MiB, and files beyond the 4,000-file observation cap. The feature manifest is a deliberately read metadata exception under `.threadline/features.json`.

In a Git repository with Git installed, tracked and non-ignored untracked files are discovered with `git ls-files --cached --others --exclude-standard`. Independent safety exclusions still apply to tracked secrets. Without Git, Threadline uses a filesystem walk: it does **not** claim a full implementation of Git ignore syntax.

Use `.threadlineignore` for additional exclusions: one relative glob or directory prefix per line; blank lines and `#` comments are allowed. Negated `!` rules and Git's full matching semantics are not implemented. Avoid mapping data you are not authorized to read. Filename exclusions cannot guarantee removal of credentials embedded in ordinary source code.

## Native WorkBuddy receiving test
Install Threadline once, then import the supplied Skill. Ask WorkBuddy to register an authorized example, query a feature, inspect its source, publish a reviewed mapping, and record a checkpoint after a real edit/test. A second teammate should perform the workflow using only the provided documentation, without the first author's private chat history. Record the actual WorkBuddy version and result; no native client execution was performed during this build.

## Stop / restart
Ctrl+C stops the foreground service. Restart with `threadline serve` using the same home to restore projects and history. The browser reconnects and reloads current revision heads; the event stream is not the durable history store. If the local session is lost, reopen the launch URL. To rotate a token, stop the service, remove only `session.token`, and restart; old cookies then stop authenticating.

## Public repository preparation
Review the MIT license and content. Publish the application source, schemas, Skill, examples, documentation and tests. Do not publish a private `~/.threadline` directory, snapshots of user repositories, credentials, or raw user source. `preview.html` and bundled evidence contain only the newly authored examples. Replace no source files merely to connect another project.
