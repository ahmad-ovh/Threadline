# Product lock: the live map is the product

## Single workflow

An AI or a human edits code → an observer/publisher produces a valid graph revision → the fixed map updates in place → a developer enters a component and understands its implementation.

Everything in the main viewport exists to support that loop. No persistent file tree; no platform pages; no compulsory expansion button; no graph editor machinery masquerading as code understanding. Source/history are temporary supporting panels.

## Graph engine decision

Evaluated official React Flow layout guidance, Svelte Flow examples, and Cytoscape.js documentation. React Flow and Svelte Flow are credible node-interface frameworks, especially for editor-like applications. React Flow delegates automatic layout to other libraries. This prototype is a graph *explorer*, not a workflow editor; it does not need handles for drawing connections, edit palettes, framework scaffolding, or a build step for recipients.

Selected **Cytoscape.js 3.33.1**: actual node/edge model, graph element updates, canvas edge rendering, built-in pan/zoom/drag/hit testing. It is packaged locally with its MIT notice. HTML cards overlay the engine's node geometry for accessible text and flexible detail; they do not implement an independent fake graph. Cytoscape remains responsible for node hit testing, dragging, transforms, and edges.

The environment had no container package-network access. A genuine installed standalone Cytoscape 3.33.1 module was available inside the installed Gradio distribution. It was repackaged by replacing its single ESM export with a global binding and adding a closure/license. No Svelte/Gradio application code or font assets are included. `vendor/PROVENANCE.json` records source hashes and transformation. This is not a claim to bundle the latest Cytoscape release.

## What the map means

`graph.js` is a pure presentation adapter from the existing schema. Parentage determines the current exploration frontier. Simple source wrappers are flattened only when they contain nothing except submodules. File inventories become component summaries. Real imports/references aggregate across visible groups; internal containment/declaration edges remain in storage, not drawn everywhere.

Drill-in uses the immediate children plus a bounded set of externally connected components. Features use explicitly authored `implements` relationships and linked source paths; they are labeled interpretations. The viewer does not invent a graph edge from a prose summary.

Scopes use up to 30 primary nodes per page and up to eight relevant external context groups. Paging is explicit; omitted context is disclosed. This is progressive disclosure, not a claim to render every graph node simultaneously.

## Geometry is part of understanding

Initial placement condenses strongly connected components, assigns dependency ranks, and orders nodes within ranks. Cycles therefore do not recurse forever or become false trees. Long-span edges bend around intervening cards.

On an update, surviving positions are kept. New nodes use an unoccupied position, preferring a compact shelf when a new rank would extend the whole map unnecessarily. The current camera is not automatically reset. Manual arrangements are cached per project/perspective/scope/page for the browser session. All positions passed to the graph engine are cloned so its internal mutations cannot corrupt the saved geometry of a different scope. Browsing away/back is regression-tested.

Node clicking navigates; actual dragging rearranges without opening another scope. Source details pan only enough to keep the selected implementation in view. Hover emphasizes connected relationships. Node keyboard activation, search, breadcrumbs and back navigation provide alternatives to a mouse-only interface.

## Change windows versus atomic history

The first unseen accepted update establishes a visual baseline. Later revisions compare against it until the user dismisses highlights or navigates historical snapshots. A newly introduced module remains green while the agent refines it. The map is a **net comparison**, not a permanent log of every modification. The drawer identifies both endpoint revisions.

Removed objects are a temporary union with the baseline solely for rendering; they never reenter the current stored snapshot. They remain source-inspectable at the old revision. Created-then-deleted objects cancel from the net window but are still in atomic history. Checkpoints name persisted revisions without deleting events or inserting milestone nodes into the architecture.

## Deliberately not implemented

No embedded LLM, agent chat, code generation UI, runtime tracing, screenshots-to-code mapping, project management, multiplayer collaboration, cloud account integrations, MCP server, universal compiler frontend, or bespoke page per repository. The historical infrastructure, authenticated data publication, and two old playable games remain because they support the central workflow and reuse proof—not as competing product surfaces.

## Research references (official primary documentation)

Accessed September 11, 2026 (session research date; package timestamps reflect the execution environment):

- Cytoscape.js documentation: https://js.cytoscape.org/ — graph operations, events, element updates, layouts, styling, pan/zoom.
- Cytoscape 3.33.1 license: https://raw.githubusercontent.com/cytoscape/cytoscape.js/v3.33.1/LICENSE — exact bundled copyright and MIT permission.
- React Flow layout guidance: https://reactflow.dev/learn/layouting/layouting — external layout-engine choices and tradeoffs.
- Svelte Flow examples: https://svelteflow.dev/examples — alternative node-interface approach.

The sources establish library capabilities. Product selection, graph projections, geometry policies, and scope cuts are Threadline implementation decisions, not claims made by those libraries.
