#!/usr/bin/env python3
"""Verify the extracted manifest and test an offline wheel installation.

Requires Python with venv/pip support. No packages are downloaded. No WorkBuddy
account is used or claimed. All working data is disposable and kept outside the
application directory. Run from any working directory.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import venv
import zipfile


def main() -> int:
    root=Path(__file__).resolve().parents[1]
    manifest=root/'MANIFEST.sha256'
    if manifest.exists():
        for line in manifest.read_text(encoding='utf-8').splitlines():
            digest,name=line.split('  ',1)
            path=(root/name).resolve()
            if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Manifest verification failed: '+name)
        print('PASS every release file matches MANIFEST.sha256',flush=True)
    else:
        print('NOTE source checkout has no release manifest',flush=True)
    wheels=sorted((root/'dist').glob('threadline_workbench-*.whl'))
    if not wheels:raise RuntimeError('No wheel found in dist/')
    wheel=wheels[-1]
    with zipfile.ZipFile(wheel) as archive:
        if archive.testzip() is not None:raise RuntimeError('Damaged wheel')
        for name in ('threadline/web/app.js','threadline/web/cytoscape.min.js','threadline/web/map-view.js','threadline/web/CYTOSCAPE-LICENSE.txt','threadline/demo_templates/orbit-courier/src/engine/core.js','threadline/demo_templates/lantern-harbor/index.html'):
            if name not in archive.namelist():raise RuntimeError('Wheel missing '+name)
    with tempfile.TemporaryDirectory(prefix='threadline-receiver-') as tmp:
        base=Path(tmp);venv.EnvBuilder(with_pip=True).create(base/'venv')
        python=base/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        subprocess.run([str(python),'-m','pip','install','--no-index','--no-deps',str(wheel)],check=True,capture_output=True,text=True)
        print('PASS offline install into a new isolated environment',flush=True)
        env=dict(os.environ);env.pop('PYTHONPATH',None);env.pop('THREADLINE_ROOT',None)
        home=base/'private';log=base/'server.log'
        with log.open('w',encoding='utf-8') as output:
            proc=subprocess.Popen([str(python),'-m','threadline','--home',str(home),'demo','--no-browser','--port','0'],cwd=tmp,env=env,stdout=output,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+30;match=None
            while time.monotonic()<deadline:
                text=log.read_text(encoding='utf-8');match=re.search(r'Open: (http://127\.0\.0\.1:\d+)/#token=([^\s]+)',text)
                if match:break
                if proc.poll() is not None:raise RuntimeError('Installed app exited before becoming ready')
                time.sleep(.1)
            if not match:raise RuntimeError('Installed app did not become ready')
            url,token=match.groups();opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def get(path):
                request=urllib.request.Request(url+path,headers={'Authorization':'Bearer '+token})
                with opener.open(request,timeout=10) as response:return response.read()
            projects=json.loads(get('/api/projects'))['projects']
            if {p['id'] for p in projects}!={'lantern-harbor','orbit-courier'}:raise RuntimeError('Example registration failed')
            for p in projects:
                get('/demo/'+p['id']+'/index.html');get('/demo/'+p['id']+'/src/ui/main.js')
                if len(json.loads(get('/api/projects/'+p['id']+'/snapshot'))['nodes'])<10:raise RuntimeError('Empty game graph')
            assert b'Cytoscape' in get('/cytoscape.min.js')
            assert b'node-plane' in get('/')
            assert b'tree-item' not in get('/')
            print('PASS both game graphs and the complete graph-first renderer served from installed wheel',flush=True)
            source=home/'workspaces/lantern-harbor/src/domain/memory.js'
            source.write_text(source.read_text(encoding='utf-8')+'\n// receiver observation check\n',encoding='utf-8')
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                graph=json.loads(get('/api/projects/lantern-harbor/snapshot'))
                if graph['revision']>=2:break
                time.sleep(.2)
            if graph['revision']<2:raise RuntimeError('Source observer did not publish a new revision')
            print('PASS real source edit advances retained revision with unchanged viewer',flush=True)
            run=subprocess.run([str(python),str(root/'skills/threadline/scripts/threadline_cli.py'),'--home',str(home),'projects'],cwd=tmp,env=env,check=True,capture_output=True,text=True)
            if len(json.loads(run.stdout)['projects'])!=2:raise RuntimeError('Skill wrapper cannot invoke installed app')
            print('PASS Skill wrapper invokes the installed application',flush=True)
        finally:
            proc.terminate()
            try:proc.wait(5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    print('Done. This check does not exercise native browser or WorkBuddy account behavior.')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print('Release verification failed: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
