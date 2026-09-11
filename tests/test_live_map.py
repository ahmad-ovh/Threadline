"""Version-2 refocus regression tests; no simulated frontend is used here."""
import json
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from threadline.demos import setup_demos,live_build_steps
from threadline.store import Store
from threadline.scanner import Scanner
from threadline.model import ContractError
from threadline.exporter import render_export
from threadline.server import WEB

class LiveMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'state');setup_demos(self.store)
    def tearDown(self):self.tmp.cleanup()
    def apply_steps(self,pid):
        root=Path(self.store.project(pid)['root']);steps=live_build_steps(self.store,pid)
        for step in steps:
            path=root/step['path']
            if step['text'] is None:
                path.unlink(missing_ok=True)
                if step.get('prune'):
                    folder=root/step['prune']
                    if folder.exists() and not any(folder.iterdir()):folder.rmdir()
            else:
                path.parent.mkdir(parents=True,exist_ok=True);path.write_text(step['text'],encoding='utf-8')
            Scanner(self.store,pid).scan(step['summary'],actor='explicit-test-refactor')
        return root
    def test_lantern_refactor_creates_a_real_component_and_reference(self):
        self.apply_steps('lantern-harbor');g=self.store.snapshot('lantern-harbor');self.assertEqual(g['revision'],4)
        self.assertTrue(any(n['id']=='module:src/journal' for n in g['nodes']))
        self.assertTrue(any(e['source']=='file:src/narrative/dialogue.js' and e['target']=='file:src/journal/format.js' for e in g['edges']))
    def test_refactor_reversal_removes_only_example_component_and_keeps_history(self):
        self.apply_steps('lantern-harbor');self.apply_steps('lantern-harbor');g=self.store.snapshot('lantern-harbor')
        self.assertFalse(any(n['id']=='module:src/journal' for n in g['nodes']));self.assertEqual(g['revision'],6)
        old=self.store.source('lantern-harbor','src/journal/format.js',4);self.assertTrue(old['available']);self.assertIn('numberedEvents',old['text']);self.assertEqual(len(self.store.history('lantern-harbor')),6)
    def test_orbit_refactor_is_independent_and_connects_to_world(self):
        self.apply_steps('orbit-courier');g=self.store.snapshot('orbit-courier')
        self.assertTrue(any(e['source']=='file:src/navigation/beacon.js' and e['target']=='file:src/world/map.js' for e in g['edges']))
        self.assertEqual(self.store.head('lantern-harbor'),1)
    def test_ordinary_repository_cannot_be_changed_by_demo(self):
        root=Path(self.tmp.name)/'real-source';root.mkdir();(root/'keep.txt').write_text('keep')
        self.store.register('real','Real',str(root))
        with self.assertRaises(ContractError):live_build_steps(self.store,'real')
        self.assertEqual((root/'keep.txt').read_text(),'keep')
    def test_missing_disposable_marker_blocks_writes(self):
        root=Path(self.store.project('lantern-harbor')['root']);(root/'.threadline-demo-marker').unlink()
        with self.assertRaises(ContractError):live_build_steps(self.store,'lantern-harbor')
    def test_export_embeds_real_graph_engine_and_its_license(self):
        html=render_export(self.store.export('lantern-harbor'))
        self.assertIn('Cytoscape Consortium',html);self.assertIn('3.33.1',html);self.assertIn('class GraphMap',html)
        class ExternalResources(HTMLParser):
            def __init__(self): super().__init__();self.found=[]
            def handle_starttag(self,tag,attrs):
                values=dict(attrs)
                if tag=='script' and values.get('src'):self.found.append(values['src'])
                if tag=='link' and values.get('rel')=='stylesheet':self.found.append(values.get('href'))
        parser=ExternalResources();parser.feed(html)
        self.assertEqual(parser.found,[])
    def test_export_contains_no_runtime_session_or_absolute_root(self):
        html=render_export(self.store.export('lantern-harbor'))
        self.assertNotIn(str(self.store.directory),html);self.assertNotIn('session.token',html)
    def test_primary_ui_has_no_tree_tabs_or_expand_control(self):
        html=(WEB/'index.html').read_text(encoding='utf-8');self.assertIn('id="cy"',html);self.assertIn('id="node-plane"',html)
        self.assertNotIn('tree-item',html);self.assertNotIn('data-tab=',html);self.assertNotIn('>Expand',html)
    def test_source_interpretations_go_stale_after_a_real_refactor(self):
        self.apply_steps('lantern-harbor');g=self.store.snapshot('lantern-harbor')
        feature=next(n for n in g['nodes'] if n['id']=='feature:remembered-favors');self.assertEqual(feature['status'],'stale')
    def test_node_bundle_does_not_call_a_model_or_fetch_from_cdn(self):
        html=(WEB/'index.html').read_text(encoding='utf-8');self.assertNotIn('https://',html)
        for script in ('app.js','graph.js','map-view.js'):
            source=(WEB/script).read_text(encoding='utf-8');self.assertNotIn('api.openai',source);self.assertNotIn('api.anthropic',source)

if __name__=='__main__':unittest.main()
