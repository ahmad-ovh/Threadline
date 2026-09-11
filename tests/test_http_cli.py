import copy
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from threadline.store import Store
from threadline.scanner import Scanner,Tracker
from threadline.server import LocalServer
from threadline.exporter import render_export
from test_core import graph

ROOT=Path(__file__).resolve().parents[1]

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name)/'store';self.root=Path(self.tmp.name)/'source';self.root.mkdir();(self.root/'main.py').write_text('def hello():\n    return 1\n')
        self.store=Store(self.home);self.store.register('local','Local',str(self.root));self.tracker=Tracker(self.store);self.tracker.scan('local');self.server=LocalServer(self.store,self.tracker,0);self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start();self.url=self.server.url;self.token=self.server.token
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tracker.stop();self.tmp.cleanup()
    def req(self,path,body=None,auth=True,headers=None,raw=None):
        heads={}
        if auth:heads['Authorization']='Bearer '+self.token
        if body is not None:heads['Content-Type']='application/json'
        heads.update(headers or {})
        data=raw if raw is not None else json.dumps(body).encode() if body is not None else None
        request=Request(self.url+path,data=data,headers=heads)
        try:response=urlopen(request,timeout=5)
        except HTTPError as exc:response=exc
        with response:return response.status,dict(response.headers),response.read()
    def test_health_without_credentials(self):
        status,headers,body=self.req('/api/health',auth=False);self.assertEqual(status,200);self.assertTrue(json.loads(body)['localOnly'])
    def test_read_requires_session(self):self.assertEqual(self.req('/api/projects',auth=False)[0],401)
    def test_valid_bearer_reads_data(self):self.assertEqual(self.req('/api/projects')[0],200)
    def test_wrong_bearer_rejected(self):self.assertEqual(self.req('/api/projects',headers={'Authorization':'Bearer incorrect'})[0],401)
    def test_untrusted_host_rejected(self):self.assertEqual(self.req('/api/projects',headers={'Host':'attacker.invalid'})[0],403)
    def test_cross_origin_reads_rejected(self):self.assertEqual(self.req('/api/projects',headers={'Origin':'https://attacker.invalid'})[0],403)
    def test_null_origin_rejected(self):self.assertEqual(self.req('/api/projects',headers={'Origin':'null'})[0],403)
    def test_cross_site_fetch_rejected(self):self.assertEqual(self.req('/api/projects',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
    def test_same_origin_is_allowed(self):self.assertEqual(self.req('/api/projects',headers={'Origin':self.url})[0],200)
    def test_auth_cookie_is_httponly_and_lax(self):
        status,headers,_=self.req('/api/session',{});self.assertEqual(status,200);cookie=headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Lax',cookie)
        self.assertEqual(self.req('/api/projects',auth=False,headers={'Cookie':cookie.split(';')[0]})[0],200)
    def test_query_token_authorized(self):
        self.assertEqual(self.req('/api/projects?token='+self.token,auth=False)[0],200)
    def test_html_never_embeds_local_token(self):
        status,_,body=self.req('/',auth=False);self.assertEqual(status,200);self.assertNotIn(self.token.encode(),body)
    def test_path_traversal_rejected(self):self.assertEqual(self.req('/%2e%2e/run.py')[0],404)
    def test_source_read_is_snapshot_scoped(self):
        status,_,body=self.req('/api/projects/local/source?path=main.py&revision=1');self.assertEqual(status,200);self.assertIn('def hello',json.loads(body)['text'])
        self.assertEqual(self.req('/api/projects/local/source?path=../../etc/passwd')[0],404)
    def test_user_project_not_served_as_executable_demo(self):self.assertEqual(self.req('/demo/local/main.py')[0],400)
    def test_scan_noop(self):
        status,_,body=self.req('/api/projects/local/scan',{});self.assertEqual(status,200);self.assertFalse(json.loads(body)['changed']);self.assertEqual(self.store.head('local'),1)
    def test_checkpoint_endpoint_preserves_revision(self):
        status,_,body=self.req('/api/projects/local/checkpoint',{'name':'Milestone'});self.assertEqual(status,201);self.assertEqual(json.loads(body)['revision'],1);self.assertEqual(self.store.head('local'),1)
    def test_reject_non_json_write(self):self.assertEqual(self.req('/api/projects/local/scan',raw=b'{}',headers={'Content-Type':'text/plain'})[0],400)
    def test_reject_malformed_json(self):self.assertEqual(self.req('/api/projects/local/scan',raw=b'{',headers={'Content-Type':'application/json'})[0],400)
    def test_reject_remote_registration_of_local_root(self):self.assertEqual(self.req('/api/projects',{'id':'private','name':'Private','mode':'filesystem','root':'/etc'})[0],400)
    def test_external_publisher_end_to_end_and_conflict(self):
        self.assertEqual(self.req('/api/projects',{'id':'sample','name':'Sample'})[0],201)
        body={'snapshot':graph(),'expectedRevision':0,'eventId':'first','summary':'Agent publication'}
        self.assertEqual(self.req('/api/projects/sample/publish',body)[0],201)
        status,_,reply=self.req('/api/projects/sample/publish',body);self.assertTrue(json.loads(reply)['duplicate'])
        body['eventId']='second';body['snapshot']['nodes'][1]['label']='Other'
        self.assertEqual(self.req('/api/projects/sample/publish',body)[0],409)
    def test_filesystem_graph_has_single_writer(self):
        body={'snapshot':graph('local'),'expectedRevision':1,'eventId':'bad','summary':'Race'}
        self.assertEqual(self.req('/api/projects/local/publish',body)[0],400)
    def test_sse_reports_initial_and_changed_head(self):
        request=Request(self.url+'/api/stream',headers={'Authorization':'Bearer '+self.token})
        with urlopen(request,timeout=5) as response:
            self.assertIn('text/event-stream',response.headers['Content-Type'])
            def state():
                while True:
                    line=response.readline().decode()
                    if not line:raise AssertionError('SSE stream ended before state')
                    if line.startswith('data: '):return json.loads(line[6:])
            first=state();self.assertEqual(first['projects'][0]['revision'],1)
            (self.root/'main.py').write_text('def hello():\n    return 2\n');self.tracker.scan('local')
            second=state();self.assertEqual(second['projects'][0]['revision'],2)
    def test_sse_reconnect_gets_current_head_not_stale_cache(self):
        (self.root/'main.py').write_text('x=2\n');self.tracker.scan('local')
        request=Request(self.url+'/api/stream',headers={'Authorization':'Bearer '+self.token,'Last-Event-ID':'old-cursor'})
        with urlopen(request,timeout=5) as response:
            while True:
                line=response.readline().decode()
                if line.startswith('data: '):self.assertEqual(json.loads(line[6:])['projects'][0]['revision'],2);break
    def test_export_uses_attachment_and_no_source_text(self):
        status,headers,body=self.req('/api/projects/local/export');self.assertEqual(status,200);self.assertIn('attachment',headers['Content-Disposition']);self.assertNotIn('def hello',body.decode())
    def test_snapshot_export_escapes_script_payload(self):
        g=graph();g['nodes'][1]['label']='</script><script>window.INJECTED=true</script>';self.store.register('sample','Sample',mode='published');self.store.publish(g,expected=0,event_id='x',summary='Test');html=render_export(self.store.export('sample'));self.assertIn('\\u003c/script',html);self.assertNotIn('"label": "</script>',html)

    def test_filesystem_graph_accepts_workbuddy_patch(self):
        patch={'upsertNodes':[{'id':'file:service.py','kind':'file','label':'service.py','path':'service.py'}],'upsertEdges':[]}
        status,_,reply=self.req('/api/projects/local/patch',{'patch':patch,'summary':'WorkBuddy added service'})
        self.assertEqual(status,201)
        res=json.loads(reply)
        self.assertEqual(res['revision'],2)
        self.assertTrue(res['changed'])

class CLITests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name)/'home'
    def tearDown(self):self.tmp.cleanup()
    def run_cli(self,*args):return subprocess.run([sys.executable,str(ROOT/'run.py'),'--home',str(self.home),*args],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    def test_doctor_no_dependencies(self):
        r=self.run_cli('doctor');self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['runtimeDependencies'],[])
    def test_complete_add_context_checkpoint_export(self):
        root=Path(self.tmp.name)/'game';root.mkdir();(root/'memory.py').write_text('def remember():\n    return True\n')
        self.assertEqual(self.run_cli('add',str(root),'--id','game').returncode,0)
        result=self.run_cli('context','game','--query','remember');self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(result.stdout)['nodes'])
        self.assertEqual(self.run_cli('checkpoint','game','First milestone').returncode,0)
        out=Path(self.tmp.name)/'snapshot.html';r=self.run_cli('export','game','--format','html','--out',str(out));self.assertEqual(r.returncode,0,r.stderr);self.assertIn('threadline-data',out.read_text(encoding='utf-8'))
    def test_cli_reports_machine_readable_error(self):
        r=self.run_cli('snapshot','absent');self.assertEqual(r.returncode,2);self.assertIn('error',json.loads(r.stderr))
    def test_feature_cli_updates_real_manifest(self):
        root=Path(self.tmp.name)/'game';root.mkdir();(root/'memory.py').write_text('x=1');self.run_cli('add',str(root),'--id','game')
        r=self.run_cli('feature','game','--id','memory','--name','Memory','--files','memory.py','--description','Remembered state');self.assertEqual(r.returncode,0,r.stderr);self.assertTrue((root/'.threadline/features.json').exists())
    def test_cli_patch_with_inline_json_on_filesystem_project(self):
        root=Path(self.tmp.name)/'game';root.mkdir();(root/'app.py').write_text('pass\n')
        self.run_cli('add',str(root),'--id','game')
        patch=json.dumps({'upsertNodes':[{'id':'file:helper.py','kind':'file','label':'helper.py','path':'helper.py'}],'upsertEdges':[{'id':'e1','source':'file:app.py','target':'file:helper.py','kind':'imports'}]})
        r=self.run_cli('patch','game','--json',patch,'--summary','WorkBuddy added helper')
        self.assertEqual(r.returncode,0,r.stderr)
        res=json.loads(r.stdout)
        self.assertEqual(res['revision'],2)
        self.assertTrue(res['changed'])

if __name__=='__main__':unittest.main()
