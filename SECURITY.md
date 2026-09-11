# Security and privacy boundary

Threadline 2.0 is a **local single-user development tool**, not a hardened public service. Its HTTP server binds to `127.0.0.1` only. Do not reverse-proxy, tunnel or expose it to a LAN/internet. Python's `http.server` documentation explicitly does not recommend that server as a public production service.

## Protections implemented and tested

- Private session token; authenticated project API; HttpOnly/SameSite local session cookie; host/origin/fetch-site checks.
- No cross-origin API access and no third-party runtime assets, telemetry or model calls.
- Filesystem registration through local CLI, not arbitrary remote browser paths.
- Relative-path validation, traversal rejection, symlink exclusions, eligible-file size/count limits.
- Sensitive filenames, hidden/dependency/build directories and Git ignored files are excluded by default; `.threadlineignore` supports additional restrictions.
- Graph/patch semantic validation, optimistic concurrency, duplicate-request handling and atomic database writes.
- Source treated as text, not executable instructions; escaped graph labels and exported data.
- Only the specifically bundled games have runnable routes; user projects are not automatically executed or web-served.

## Limits you must understand

The private database retains eligible indexed source text and history so that earlier graph evidence can be inspected. It is **not encrypted**. Anyone with sufficient access to your OS account/files can read it. Exported JSON/HTML omits source-text blobs, but still reveals names, paths, relationships, summaries and version identities. Review outputs before public sharing.

Filename-based exclusions are not a secret scanner. A secret embedded in an ordinary `game.py` or `README.md` may be retained. Configure the project boundary and exclusions BEFORE registration. There is no per-project secure-erasure UI in this prototype; a private home is the simplest isolation unit. Stop the process before deleting a disposable home. Never delete a user's chosen home without permission.

Published graphs can contain inaccurate claims even when structurally valid. External data does not become verified merely because its author labels it observed. Evidence and reviewed hashes are provenance aids, not a semantic proof or access-control system. The host agent must independently inspect current source before changes.

Atomic observation is a stable scanned batch, not an OS-wide transactional filesystem capture or every intermediate keystroke. Concurrent writers can cause a rejected/retried scan; known failures surface in viewer health.

Checkpoints do not prune history. Disk use grows over time; automatic retention/compaction is not implemented. Existing database owners can modify history outside the application; it is not cryptographically signed or tamper-evident.

The native API checks were exercised over loopback. Browser DOM behavior was tested with a clearly documented transport bridge because the managed test browser blocks URL navigation; this is not a browser security audit or penetration test. See `TEST_REPORT.md`.

## Before a public release

Review code, assets and licenses, choose the real repository owner and security-reporting channel, and publish a supported-version policy. No public repository or contact has been fabricated in this archive. Remove unneeded example history before distributing private project exports. Never commit `session.token`, SQLite databases, logs containing authenticated launch links, or personal source data.


## Managed installation handoff

The Skill's new helper can fetch and execute the **user-approved** viewer repository/ref. First execution requires `--trust-source`. This is real local code execution, not a safe preview of arbitrary remote code. Use a full expected viewer commit when configuring the Skill; verify the owner/release. Runtime-manifest checks detect changes relative to the selected source, but do not independently establish that its author is trustworthy.

Code lives in `~/.threadline-tools/releases/` and connection metadata in `~/.threadline-tools/connection.json`; private source/history and the token-bearing local launch file live in `~/.threadline/`. Keep both outside the inspected root. Do not share the profile, local launch files, tokens or SQL stores. No credential-bearing clone URL is accepted and no automatic public tunnel is configured. Stop requests address the managed run ID rather than killing a guessed PID.

A native coding host may reap background processes or deny local execution. Record that limitation and use a user-approved foreground terminal; never claim the background/native path passed if it did not. Neither helper invokes email/contact tools nor publishes code to GitHub.
