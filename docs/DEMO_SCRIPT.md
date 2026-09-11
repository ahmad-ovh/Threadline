# The graph-first demonstration (2–3 minutes)

## Preparation

Run `python run.py --home /path/to/a/fresh/private/demo-store demo`. A fresh directory produces a known baseline without deleting anyone's existing history. Use a desktop viewport. Keep the source editor visible on a second screen if available. Neither game is THRESHOLD.

## 0:00 — the promise

“This is a live map of what is being built. We install the viewer once. The coding workflow supplies data, not a new frontend.”

Start on Architecture. The first thing the audience sees is the graph, not a menu of product features.

## 0:20 — understand one component

Click `narrative`, then `dialogue.js`. Read one declaration and its source. Click a reference to explain *why* two components are connected. Return with the breadcrumb.

“Folders are entry points into the implementation. Connections are backed by graph data and, where supplied, source evidence—not just arrows an AI drew.”

## 0:50 — watch code become structure

For the packaged demonstration, click **Watch a change**. Say explicitly: “This button performs a scripted refactor in the example; the watcher is real. On our own repository, these are the coding agent's ordinary file edits.”

Over about ten seconds the example creates `src/journal/format.js`, connects dialogue to it, and refines the formatter. The new component stays green through the change window. Existing components keep their positions. Click the new journal component and inspect its implementation.

For a genuine agent demonstration, replace the scripted step with a live agent editing the tracked repository. Do not relabel the example button as an AI call.

## 1:30 — history underneath, not all over the graph

Open the revision control at the lower left. Select a baseline revision, then return to live. Optionally name the moment with a checkpoint.

“Every accepted update remains here. But every edit is not a new permanent node in the architecture.”

## 1:55 — prove reusable installation

Switch to Orbit Courier. The same interface, graph projection, scanner, and history work there. The new example refactor creates a navigation component. You did not generate or edit the viewer to support the second game.

## Close

“The AI keeps building. The map keeps up. The developer can still understand the code.”

## Recovery and truthfulness

The application is local; a model is not required for the included demonstration. If live observation fails, preserve the last good graph and show the visible warning. `preview.html` is explicitly recorded, read-only data, not live capture. Do not present it as live. Source references are not complete runtime traces, and lexical adapters have stated limits.
