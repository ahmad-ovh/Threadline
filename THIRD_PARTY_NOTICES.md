# Third-party notices

Threadline-authored code and examples: GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later); see `LICENSE`.

## Cytoscape.js 3.33.1

Copyright (c) 2016-2025, The Cytoscape Consortium. MIT.

Full notice: `vendor/CYTOSCAPE-LICENSE.txt`, also shipped inside `src/threadline/web/CYTOSCAPE-LICENSE.txt` and the actual JavaScript bundle so portable HTML exports retain it.

Official source: https://github.com/cytoscape/cytoscape.js/tree/v3.33.1
Exact upstream license: https://raw.githubusercontent.com/cytoscape/cytoscape.js/v3.33.1/LICENSE
Documentation: https://js.cytoscape.org/

The local standalone ESM distribution was obtained from the installed Gradio frontend package, not from a fabricated copy of the library. Its single ESM export was rebound to `globalThis.cytoscape` inside a closure. Original and shipped hashes are recorded in `vendor/PROVENANCE.json`. No behavior was intentionally modified. The remaining viewer uses Threadline-authored code; no React Flow/Svelte Flow/Gradio UI framework is bundled.

Python's standard library and the recipient's browser are runtime prerequisites. Node, Playwright, Chromium, setuptools and test-only validation packages are development/test tools, not bundled application libraries. The optional wheel includes the same locally bundled renderer.

No third-party font files, stock artwork, cloud credentials or external game assets are distributed. The two games are original synthetic demonstration examples. WorkBuddy is a product integration target; Tencent product binaries are not redistributed.
