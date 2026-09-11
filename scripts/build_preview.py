#!/usr/bin/env python3
"""Rebuild public read-only examples from real, disposable source observations."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from threadline.store import Store
from threadline.scanner import Scanner,write_feature
from threadline.demos import setup_demos,live_build_steps
from threadline.exporter import render_export


def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='threadline-preview-') as tmp:
        store=Store(Path(tmp)/'private');setup_demos(store)
        for pid in ('lantern-harbor','orbit-courier'):
            # Record actual staged edits into the durable store; this is a recorded
            # example export, not claimed to be a live watcher/model session.
            source=Path(store.project(pid)['root'])
            for step in live_build_steps(store,pid):
                path=source/step['path'];path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(step['text'],encoding='utf-8')
                Scanner(store,pid).scan(step['summary'],actor='scripted-example')
            store.checkpoint(pid,'Reusable component extracted','Real scripted source change, not a live model call.')
        # Re-review one actual interpretation against its updated source hashes.
        pid='lantern-harbor';project=store.project(pid)
        write_feature(Path(project['root']),'remembered-favors','Remembered favors',
                      ['src/domain/memory.js','src/narrative/dialogue.js','src/journal/format.js'],
                      'Earlier interactions are recorded in memory; dialogue reads them through the extracted journal formatter. This is a source interpretation, not runtime instrumentation.',
                      'example-author')
        Scanner(store,pid).scan('Reviewed the remembered-favors mapping against updated source',actor='example-author')
        store.checkpoint(pid,'Memory feature reviewed','Reviewed source links; underlying revisions remain intact.')
        bundles=[store.export(pid) for pid in ('lantern-harbor','orbit-courier')]
        for bundle in bundles:
            pid=bundle['snapshot']['project']['id']
            (root/'examples'/f'{pid}.threadline.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
        (root/'preview.html').write_text(render_export({'format':'threadline-workspace','bundles':bundles}),encoding='utf-8')
        print(json.dumps({'preview':'preview.html','projects':[{ 'id':b['snapshot']['project']['id'],'revision':b['snapshot']['revision'],'nodes':len(b['snapshot']['nodes'])} for b in bundles],'sourceTextIncluded':False}))

if __name__=='__main__':main()
