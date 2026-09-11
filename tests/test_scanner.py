import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from threadline.store import Store
from threadline.scanner import Scanner, Tracker, write_feature, analyze, MAX_FILE_BYTES
from threadline.model import ContractError

class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'game';self.root.mkdir();self.store=Store(Path(self.tmp.name)/'state');self.store.register('game','Game',str(self.root));self.scanner=Scanner(self.store,'game')
    def tearDown(self):self.tmp.cleanup()
    def put(self,path,text):
        file=self.root/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text,encoding='utf-8',newline='\n');return file
    def graph(self):self.scanner.scan();return self.store.snapshot('game')
    def test_python_ast_import(self):
        self.put('game/__init__.py','');self.put('game/main.py','from .memory import remember\n');self.put('game/memory.py','def remember():\n    return True\n');g=self.graph();refs=[e for e in g['edges'] if e['kind']=='imports'];self.assertEqual(len(refs),1);self.assertEqual(refs[0]['target'],'file:game/memory.py');self.assertEqual(refs[0]['evidence'][0]['status'],'observed')
    def test_python_src_package(self):
        self.put('src/pkg/__init__.py','');self.put('src/pkg/logic.py','x=1\n');self.put('main.py','from pkg import logic\n');g=self.graph();self.assertTrue(any(e['target']=='file:src/pkg/logic.py' for e in g['edges']))
    def test_python_class_member_symbols(self):
        self.put('model.py','class NPC:\n    def speak(self):\n        pass\n');g=self.graph();self.assertTrue(any(n['id']=='symbol:model.py#NPC.speak' for n in g['nodes']))
    def test_python_parse_error_visible(self):
        self.put('bad.py','def missing(:\n');g=self.graph();self.assertTrue(any('parse failed' in d['message'] for d in g['diagnostics']));self.assertTrue(any(n['path']=='bad.py' for n in g['nodes']))
    def test_js_comments_and_strings_do_not_invent_imports(self):
        self.put('main.js',"// import x from './bad.js';\nconst text = \"import y from './bad.js'\";\nimport {x} from './good.js';\n")
        self.put('good.js','export const x = 1;');self.put('bad.js','export const y = 2;');g=self.graph();imports=[e for e in g['edges'] if e['kind']=='imports'];self.assertEqual(len(imports),1);self.assertEqual(imports[0]['target'],'file:good.js');self.assertEqual(imports[0]['evidence'][0]['status'],'lexical')
    def test_js_dynamic_literal_import(self):
        self.put('main.js',"const module = import('./logic.js');");self.put('logic.js','export const x = 1;');g=self.graph();self.assertEqual(len([e for e in g['edges'] if e['kind']=='imports']),1)
    def test_ts_js_extension_resolution(self):
        self.put('main.ts',"import {x} from './logic.js';");self.put('logic.ts','export const x:number = 1;');g=self.graph();self.assertTrue(any(e['target']=='file:logic.ts' and e['kind']=='imports' for e in g['edges']))
    def test_unresolved_is_not_a_fake_local_node(self):
        self.put('main.js',"import x from 'react';\nimport y from './missing.js';");g=self.graph();self.assertEqual(len(g['unresolved']),2);self.assertFalse(any(e['kind']=='imports' for e in g['edges']))
    def test_godot_resources(self):
        self.put('scripts/actor.gd','extends Node2D\nconst Data = preload("res://scripts/memory.gd")\nfunc speak():\n    pass\n');self.put('scripts/memory.gd','extends RefCounted\n');self.put('main.tscn','[ext_resource type="Script" path="res://scripts/actor.gd" id="1"]\n');g=self.graph();refs=[e for e in g['edges'] if e['kind']=='references'];self.assertEqual(len(refs),2)
    def test_html_resources(self):
        self.put('index.html','<script src="main.js"></script><link rel="stylesheet" href="style.css">');self.put('main.js','');self.put('style.css','body{}');g=self.graph();self.assertEqual(len([e for e in g['edges'] if e['kind']=='references']),2)
    def test_secret_and_build_exclusions(self):
        for p in ('.env','private.key','secrets.json','node_modules/pkg/a.js','.git/config','build/b.js'):self.put(p,'SHOULD NOT INDEX')
        self.put('ok.py','x=1');g=self.graph();paths={n.get('path') for n in g['nodes']};self.assertIn('ok.py',paths);self.assertNotIn('.env',paths);self.assertEqual(len([n for n in g['nodes'] if n['kind']=='file']),1)
    @unittest.skipUnless(hasattr(os,'symlink'),'symlinks unavailable')
    def test_symlink_does_not_escape_root(self):
        outside=Path(self.tmp.name)/'outside.py';outside.write_text('PRIVATE')
        try:(self.root/'leak.py').symlink_to(outside)
        except OSError:self.skipTest('symlink permission unavailable')
        self.put('ok.py','x=1');g=self.graph();self.assertFalse(any(n.get('path')=='leak.py' for n in g['nodes']))
    def test_large_file_reports_partial_coverage(self):
        self.put('big.js','x'*(MAX_FILE_BYTES+1));g=self.graph();self.assertTrue(any('1 MiB' in d['message'] for d in g['diagnostics']))
    def test_incremental_scan_reuses_analysis(self):
        self.put('a.py','a=1');self.put('b.py','b=2');self.scanner.scan();r=self.scanner.scan();self.assertEqual(r['scanStats']['filesRead'],0);self.assertFalse(r['changed']);self.put('a.py','a=3');r=self.scanner.scan();self.assertEqual(r['scanStats']['filesRead'],1);self.assertTrue(r['changed'])
    def test_deletion_has_tombstone_in_delta(self):
        self.put('a.py','a=1');self.scanner.scan();(self.root/'a.py').unlink();r=self.scanner.scan();self.assertTrue(any(n['id']=='file:a.py' for n in r['delta']['nodes']['removed']))
    def test_retains_historical_text_after_delete(self):
        self.put('a.py','x=1\n');self.scanner.scan();(self.root/'a.py').unlink();self.scanner.scan();self.assertEqual(self.store.source('game','a.py',1)['text'],'x=1\n')
    def test_feature_becomes_stale_on_source_change(self):
        self.put('memory.py','x=1');write_feature(self.root,'memory','Memory',['memory.py'],'Remembered state');g=self.graph();self.assertEqual(next(n for n in g['nodes'] if n['kind']=='feature')['status'],'interpretation');self.put('memory.py','x=2');g=self.graph();self.assertEqual(next(n for n in g['nodes'] if n['kind']=='feature')['status'],'stale')
    def test_feature_review_reanchors_hash(self):
        self.put('memory.py','x=1');write_feature(self.root,'memory','Memory',['memory.py'],'State');self.scanner.scan();self.put('memory.py','x=2');self.scanner.scan();write_feature(self.root,'memory','Memory',['memory.py'],'State reviewed');g=self.graph();self.assertEqual(next(n for n in g['nodes'] if n['kind']=='feature')['status'],'interpretation')
    def test_missing_feature_source_is_stale_without_dangling_edge(self):
        self.put('a.py','x=1');write_feature(self.root,'a','A',['a.py'],'A');self.scanner.scan();(self.root/'a.py').unlink();g=self.graph();self.assertEqual(next(n for n in g['nodes'] if n['kind']=='feature')['status'],'stale');self.assertFalse(any(e['kind']=='implements' for e in g['edges']))
    def test_invalid_manifest_does_not_overwrite_last_good_graph(self):
        self.put('a.py','x=1');self.scanner.scan();self.put('.threadline/features.json','not json');self.assertRaises(ContractError,self.scanner.scan);self.assertEqual(self.store.head('game'),1)
    def test_ignore_file(self):
        self.put('a.py','x=1');self.put('generated/b.py','x=2');self.put('.threadlineignore','generated/\n');g=self.graph();self.assertFalse(any(n.get('path')=='generated/b.py' for n in g['nodes']))
    @unittest.skipUnless(shutil.which('git'),'Git is optional')
    def test_gitignore_and_commit_provenance(self):
        creationflags = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        subprocess.run(['git','init','-q',str(self.root)],check=True,creationflags=creationflags);self.put('.gitignore','ignored.py\n');self.put('ignored.py','private');self.put('a.py','x=1')
        subprocess.run(['git','-C',str(self.root),'add','.'],check=True,creationflags=creationflags);subprocess.run(['git','-C',str(self.root),'-c','user.name=Test','-c','user.email=test@example.invalid','-c','commit.gpgsign=false','commit','-qm','baseline'],check=True,creationflags=creationflags)
        g=self.graph();self.assertIsNotNone(g['source']['commit']);self.assertFalse(g['source']['dirty']);self.assertFalse(any(n.get('path')=='ignored.py' for n in g['nodes']));self.put('a.py','x=2');g2=self.graph();self.assertTrue(g2['source']['dirty']);self.assertEqual(g2['source']['commit'],g['source']['commit']);self.assertNotEqual(g2['source']['treeHash'],g['source']['treeHash'])
    def test_live_watcher_captures_an_edit(self):
        self.put('a.py','x=1');self.scanner.scan();tracker=Tracker(self.store,.25);tracker.start()
        try:
            self.put('a.py','x=2');deadline=time.monotonic()+5
            while self.store.head('game')<2 and time.monotonic()<deadline:time.sleep(.05)
            self.assertEqual(self.store.head('game'),2)
        finally:tracker.stop()
    def test_watcher_error_reports_stale_not_silent_success(self):
        self.put('a.py','x=1');self.scanner.scan();self.put('.threadline/features.json','bad');tracker=Tracker(self.store,.25)
        self.assertRaises(ContractError,tracker.scan,'game');self.assertFalse(tracker.status['game']['ok']);self.assertEqual(self.store.head('game'),1)

if __name__=='__main__':unittest.main()
