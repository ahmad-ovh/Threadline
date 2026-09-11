"""Release adapters; these tests do not require a WorkBuddy account."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from threadline.store import Store
from threadline.scanner import Tracker
from threadline.server import LocalServer

ROOT=Path(__file__).resolve().parents[1]

class SkillTests(unittest.TestCase):
    def test_wrapper_runs_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,THREADLINE_ROOT=str(ROOT),THREADLINE_HOME=str(Path(tmp)/'private'))
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            run=subprocess.run([sys.executable,str(ROOT/'skills/threadline/scripts/threadline_cli.py'),'doctor'],cwd=tmp,env=env,capture_output=True,text=True,creationflags=creationflags)
            self.assertEqual(run.returncode,0,run.stderr);self.assertTrue(json.loads(run.stdout)['ok'])
    def test_wrapper_rejects_wrong_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,THREADLINE_ROOT=tmp)
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            run=subprocess.run([sys.executable,str(ROOT/'skills/threadline/scripts/threadline_cli.py'),'doctor'],env=env,capture_output=True,text=True,creationflags=creationflags)
            self.assertEqual(run.returncode,2);self.assertIn('THREADLINE_ROOT',run.stderr)
    def test_skill_has_documented_metadata_and_fixed_viewer_instruction(self):
        text=(ROOT/'skills/threadline/SKILL.md').read_text(encoding='utf-8')
        for key in ('description:','description_zh:','description_en:','version:','author:'):
            self.assertIn(key,text)
        self.assertIn('It does not create a new frontend',text)

class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'private');self.tracker=Tracker(self.store);self.server=LocalServer(self.store,self.tracker,0)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tracker.stop();self.tmp.cleanup()
    def invoke(self,*extra):
        return subprocess.run([sys.executable,str(ROOT/'scripts/publish_example.py'),'--url',self.server.url,'--home',str(self.store.directory),*extra],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    def test_external_publisher_snapshot_and_patch_against_real_api(self):
        run=self.invoke('--patch');self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(self.store.snapshot('publisher-example')['revision'],2)
        self.assertEqual(len(self.store.snapshot('publisher-example')['nodes']),3)
        self.assertNotIn(self.server.token,run.stdout+run.stderr)
    def test_example_can_read_current_head_and_run_again(self):
        self.assertEqual(self.invoke('--patch').returncode,0)
        again=self.invoke('--patch');self.assertEqual(again.returncode,0,again.stderr)
        self.assertEqual(self.store.snapshot('publisher-example')['revision'],4)
    def test_script_rejects_external_host_before_reading_token(self):
        run=subprocess.run([sys.executable,str(ROOT/'scripts/publish_example.py'),'--url','https://example.invalid'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.assertEqual(run.returncode,2);self.assertIn('loopback',run.stderr)
    def test_javascript_mime_does_not_depend_on_os_registry(self):
        with patch('threadline.server.mimetypes.guess_type',return_value=('text/plain',None)):
            with urlopen(self.server.url+'/app.js') as response:
                self.assertIn('application/javascript',response.headers['Content-Type'])
                self.assertIn(b'Threadline',response.read())
