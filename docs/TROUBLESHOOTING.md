# Troubleshooting

| Symptom | Check and remedy |
|---|---|
| `python` not found | Use `python3` or `py -3`, or install Python 3.10+ from your approved source. `preview.html` remains read-only and requires no Python. |
| `No module named threadline` | Use `python run.py ...` from the extracted root, install the included wheel, or set `THREADLINE_ROOT` for the Skill wrapper. |
| Port already in use | Stop the old instance or run `demo --port 7332`. Do not kill unrelated processes. |
| Browser asks for a local session | Open the complete launch URL printed by the running service. Old cookies stop working after token rotation or when using a different store. |
| Wrong home or empty project list | All CLI invocations and the server must use the same `THREADLINE_HOME`/global `--home` argument. |
| Graph does not update | Keep `serve` running without `--no-watch`; verify the tracker status. A published-mode project expects an external producer, not filesystem scans. |
| Last scan failed / stale warning | Inspect the error. Invalid feature JSON, missing roots, changing files during capture or limits must be fixed; the previous graph remains rather than being silently replaced with an invented one. |
| Feature is stale | Read the changed source and verify its meaning, then explicitly review/update the mapping. Do not merely relabel it as current. |
| Feature source is missing | A file was deleted, renamed, excluded or beyond scan limits. Update the mapping honestly; a rename is currently add/delete, not automatic semantic matching. |
| Dependencies missing | Inspect `unresolved` and coverage. Aliases, computed imports, dynamic calls and unsupported languages are not silently inferred. Supply an honest custom publisher when needed. |
| Project too large | Exclude generated/assets directories with `.threadlineignore`. Review the 4,000-file/1 MiB-per-file capture cap and the 30-primary-node page and 8-connected-context-node projection cap. Use context queries for focused navigation. |
| Historical code differs from the disk | Expected: the source inspector uses the retained graph revision. Return to live for current source. A stale feature's expected hash is shown separately. |
| HTML export does not show source code | Intentional privacy boundary: exports omit source-text blobs. Use the original local store and source command. |
| Export does not cover all history | Export caps at 1,000 revisions and marks truncation. The local database retains earlier revisions. Export current-only when the browser's 64 MiB import cap is exceeded. |
| Revision conflict / HTTP 409 | Refresh HEAD. Recompute your patch against that revision. Retry the exact request with the same event ID only when checking whether a prior write succeeded. |
| “Scanner owns this project” | Do not race two producers. Use feature metadata for the scanner-owned graph or create a separate published-mode project. |
| Scripted demo change refused | It works only in the disposable bundled game copies. It cannot write arbitrary registered project code. |
| Demo changed but game looks old | Close/reopen the example game. The server sends no-store responses. New example features are a journal/beacon, not a change to every rule or visual. |
| WorkBuddy cannot import/run the Skill | Confirm the supported client, account and package route with the organizer. Check `SKILL.md` at the correct ZIP root and local Python/terminal access. Do not claim import success from the package merely existing. |
| Browser tests blocked by administrator policy | Run the suite on a normal development Chromium or use `--bridge` for transport-separated CI coverage. The report must disclose bridge mode. Do not modify enterprise browser policies. |

## Precautions
Do not expose this local Python HTTP service publicly. Do not upload the private database or session token to a public repository. A source filename filter is not a full secret scanner. Do not present the scripted example change as a live model response. Do not present the bundled examples as the actual THRESHOLD game.
