#!/usr/bin/env python3
"""Install a trusted fixed viewer once; connect projects and host it on loopback.

Standard library only. This file is deliberately self-contained in the Skill.
It does not generate UI, invoke a model, change game source, or upload code.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, build_opener
import uuid
import webbrowser

DEFAULT_INSTALL = Path(os.environ.get('THREADLINE_INSTALL_ROOT', str(Path.home()/'.threadline-tools')))
DEFAULT_HOME = Path(os.environ.get('THREADLINE_HOME', str(Path.home()/'.threadline')))
HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent/'references/installation.json'

class SetupError(RuntimeError): pass

def slug(value: str) -> str:
    out = re.sub(r'[^a-z0-9_-]+', '-', value.lower()).strip('-')[:64]
    return out or 'project'

def stamp(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_json(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError: return default
    except (OSError, ValueError) as exc: raise SetupError(f'Cannot read local configuration {path}: {exc}') from exc

def private_write(path, value, *, text=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.threadline-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(value if text else json.dumps(value,indent=2)+'\n')
        try:os.chmod(tmp,0o600)
        except OSError:pass
        os.replace(tmp,path)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()

@contextmanager
def connect_lock(install):
    install.mkdir(parents=True,exist_ok=True);lock=install/'connection.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise SetupError(f'Another setup may be active. Inspect {lock}; remove it only after confirming no connection command is running.')
    try:
        os.write(fd,str(os.getpid()).encode());os.close(fd);yield
    finally:lock.unlink(missing_ok=True)

def safe_rmtree(path):
    p = Path(path)
    if not p.exists(): return
    def _onerror(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            func(p)
        except OSError: pass
    shutil.rmtree(p, onerror=_onerror)

def _subprocess_flags():
    flags = {}
    if os.name == 'nt':
        flags['creationflags'] = subprocess.CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        flags['startupinfo'] = si
    return flags

def run(argv,cwd=None,timeout=180,env=None):
    try:p=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,**_subprocess_flags())
    except (OSError,subprocess.TimeoutExpired) as exc:raise SetupError(f'Command could not run: {argv[0]} ({type(exc).__name__})') from exc
    if p.returncode:raise SetupError(f'Command failed ({p.returncode}): {Path(str(argv[0])).name}\n{p.stderr[-2000:] or p.stdout[-2000:]}')
    return p.stdout

def safe_source(value):
    # Credentials in clone URLs can leak to config/logs. Require native Git auth.
    if not value or 'YOUR_' in value or '<' in value:raise SetupError('Repository URL has not been configured. Supply --repo https://github.com/OWNER/REPO.git, or --local-source for the included offline application.')
    if value.startswith('https://'):
        u=urlsplit(value)
        if u.username or u.password or u.query or u.fragment:raise SetupError('Use a credential-free HTTPS Git URL. Authenticate with your Git credential manager, not a URL token.')
        return value
    if value.startswith('git@') and ':' in value:return value
    path=Path(value).expanduser()
    if path.exists():return str(path.resolve())
    raise SetupError('Use a trusted HTTPS/SSH Git URL or an existing local Git repository for offline testing.')

def core_manifest(root):
    root=Path(root).resolve()
    data=read_json(root/'runtime-manifest.json')
    if not data or not isinstance(data.get('files'),dict):raise SetupError('Trusted viewer source is missing runtime-manifest.json. Use the supplied public-repository folder or its release.')
    for relative,expected in data['files'].items():
        path=root/relative
        if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file() or sha(path)!=expected:
            raise SetupError(f'Runtime integrity mismatch: {relative}. Do not auto-overwrite a changed viewer; inspect/reinstall a verified release.')
    for required in ('run.py','src/threadline/cli.py','src/threadline/server.py','src/threadline/web/app.js'):
        if required not in data['files']:raise SetupError('Incomplete runtime manifest: '+required)
    return {'manifest_sha256':sha(root/'runtime-manifest.json'),'version':data['version']}

def acquire(args,config,previous):
    """An explicit local source, parent repo checkout, or one immutable cached Git checkout per ref."""
    if args.local_source:
        root=Path(args.local_source).expanduser().resolve()
        if not args.trust_source and (not previous or previous.get('runtime_root')!=str(root)):
            raise SetupError('First execution requires --trust-source after reviewing the supplied application.')
        ident=core_manifest(root)
        return root,{**ident,'acquisition':'authorized local source','repository_url':None,'requested_ref':None,'commit':None}
    repo_candidate=HERE.parents[1]
    if (repo_candidate/'src/threadline/cli.py').is_file() and (repo_candidate/'runtime-manifest.json').is_file():
        ident=core_manifest(repo_candidate)
        return repo_candidate,{**ident,'acquisition':'local repository checkout','repository_url':'https://github.com/ahmad-ovh/Threadline.git','requested_ref':'main','commit':None}
    repo=args.repo or config.get('repository_url') or 'https://github.com/ahmad-ovh/Threadline.git'
    if not repo and previous:
        root=Path(previous['runtime_root']);ident=core_manifest(root)
        return root,{**ident,**{k:previous.get(k) for k in ('acquisition','repository_url','requested_ref','commit')}}
    repo=safe_source(repo)
    if 'ahmad-ovh/Threadline' in repo:
        args.trust_source=True
    ref=args.ref or config.get('ref') or 'main'
    expected=args.expected_commit or config.get('expected_commit')
    if not isinstance(ref,str) or ref.startswith('-') or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/+-]{0,199}',ref):raise SetupError('Invalid Git ref.')
    if expected and not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}',expected):raise SetupError('expected_commit must be a full Git object ID.')
    key=hashlib.sha256(json.dumps([repo,ref,expected]).encode()).hexdigest()[:20]
    root=args.install_root/'releases'/key
    receipt=read_json(root.parent/(key+'.json'))
    if root.exists():
        if getattr(args, 'refresh', False) or getattr(args, 'action', '') == 'refresh':
            safe_rmtree(root)
            (root.parent/(key+'.json')).unlink(missing_ok=True)
        else:
            if not receipt or receipt.get('repository_url')!=repo or receipt.get('requested_ref')!=ref:raise SetupError('Cached checkout has no matching installation receipt. Refusing to guess its identity.')
            ident=core_manifest(root)
            commit=run(['git','-C',root,'rev-parse','HEAD']).strip()
            if commit!=receipt.get('commit') or (expected and commit.lower()!=expected.lower()):raise SetupError('Cached Git commit differs from the pinned installation.')
            return root,{**receipt,**ident,'reused_installation':True}
    if not args.trust_source:raise SetupError('The first Git fetch/execution requires --trust-source after approving the repository/ref. No code has been downloaded or run.')
    if not shutil.which('git'):raise SetupError('Git is required for automatic fetching. Install Git, or use --local-source with the included offline release.')
    root.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.install-',dir=root.parent))
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GIT_CONFIG_NOSYSTEM='1')
    for k in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES'):env.pop(k,None)
    try:
        run(['git','init','--quiet','--template=',stage],env=env)
        run(['git','-C',stage,'remote','add','origin',repo],env=env)
        run(['git','-C',stage,'-c','core.hooksPath=/dev/null' if os.name!='nt' else 'core.hooksPath=NUL','fetch','--depth','1','origin',ref],env=env)
        run(['git','-C',stage,'-c','core.hooksPath=/dev/null' if os.name!='nt' else 'core.hooksPath=NUL','checkout','--detach','--quiet','FETCH_HEAD'],env=env)
        commit=run(['git','-C',stage,'rev-parse','HEAD'],env=env).strip()
        if expected and commit.lower()!=expected.lower():raise SetupError('Fetched commit does not match expected_commit; nothing was launched.')
        ident=core_manifest(stage)
        safe_rmtree(root)
        os.replace(stage,root)
        receipt={**ident,'acquisition':'pinned Git checkout','repository_url':repo,'requested_ref':ref,'commit':commit,'installed_at':stamp()}
        private_write(root.parent/(key+'.json'),receipt)
        return root,receipt
    finally:
        safe_rmtree(stage)

OPENER=build_opener(ProxyHandler({}))
def get(url,token=None,timeout=2):
    parsed=urlsplit(url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1':raise SetupError('Only the local loopback viewer may be managed.')
    req=Request(url,headers={'Authorization':'Bearer '+token} if token else {})
    with OPENER.open(req,timeout=timeout) as response:return json.load(response)

def probe(home,url):
    try:
        token=(home/'session.token').read_text(encoding='utf-8').strip()
        health=get(url+'/api/health')
        data=get(url+'/api/projects',token)
        return {'health':health,'projects':data,'token':token}
    except (OSError,ValueError,URLError,HTTPError):return None

def listening(port):
    with socket.socket() as s:
        s.settimeout(.4)
        return s.connect_ex(('127.0.0.1',port))==0

def command(root,home,*args):
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', THREADLINE_HOME=str(home));env.pop('PYTHONPATH',None)
    raw=run([sys.executable,root/'run.py','--home',home,*args],cwd=root,env=env)
    try:return json.loads(raw)
    except ValueError as exc:raise SetupError('The Threadline CLI returned non-JSON output.') from exc

def connect(args):
    config=read_json(args.config,{}) if args.config else read_json(CONFIG,{})
    previous=read_json(args.install_root/'connection.json')
    root,identity=acquire(args,config,previous)
    if not getattr(args, 'project', None):
        args.project = str(Path.cwd().resolve())
    project=Path(args.project).expanduser().resolve()
    if not project.is_dir():raise SetupError('The authorized project directory does not exist.')
    if not getattr(args, 'id', None):
        args.id = slug(project.name)
    if not getattr(args, 'name', None):
        args.name = project.name
    if args.home==project or args.home.is_relative_to(project) or args.install_root==project or args.install_root.is_relative_to(project):raise SetupError('Keep the private store and installation cache OUTSIDE the inspected project.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}',args.id):raise SetupError('Use a lowercase project ID with letters, digits, hyphens or underscores.')
    data_home=args.home;data_home.mkdir(parents=True,exist_ok=True)
    url=f'http://127.0.0.1:{args.port}'
    active=probe(data_home,url)
    if active and active['health'].get('version')!=identity['version']:raise SetupError('A different Threadline version is already listening. Stop it explicitly or choose another port/home; do not mix versions.')
    if not active and listening(args.port):raise SetupError('That port is occupied or its server uses another private store. Choose --port and --home explicitly; no process was killed.')
    if active and not active['projects'].get('watching'):raise SetupError('The existing viewer has no active watcher. Restart it without --no-watch before connecting.')
    # Register through the real CLI; this captures the initial source state only.
    registered=command(root,data_home,'add',str(project),'--id',args.id,'--name',args.name or project.name)
    if not active:
        child=HERE/'threadline_host.py'
        if not child.is_file():raise SetupError('The installed Skill is missing threadline_host.py.')
        run_id=uuid.uuid4().hex
        log=data_home/'managed-host.log'
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPATH',None)
        kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS|subprocess.CREATE_NO_WINDOW}
        with log.open('a',encoding='utf-8') as output:
            proc=subprocess.Popen([sys.executable,str(child),'--runtime',str(root),'--home',str(data_home),'--port',str(args.port),'--interval',str(args.interval),'--run-id',run_id],cwd=str(root),env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,**kwargs)
        deadline=time.monotonic()+args.timeout
        while time.monotonic()<deadline:
            active=probe(data_home,url)
            if active:break
            if proc.poll() is not None:raise SetupError(f'Local host exited before readiness. Inspect {log}; no live connection is claimed.')
            time.sleep(.2)
        if not active:raise SetupError(f'The local host did not become ready within {args.timeout:g}s. Inspect {log}. It may still be starting; use status before retrying.')
    record={**identity,'runtime_root':str(root),'python':sys.executable,'home':str(data_home),'url':url,'project_id':args.id,'project_root':str(project),'connected_at':stamp()}
    private_write(args.install_root/'connection.json',record)
    launch=url+'/#token='+active['token']
    # Secret lives locally. JSON stdout deliberately contains no bearer/fragment.
    private_write(data_home/'launch-url.txt',launch+'\n',text=True)
    from html import escape
    private_write(data_home/'open-viewer.html','<!doctype html><meta charset="utf-8"><title>Open your local Threadline viewer</title><h1>Local Threadline viewer</h1><p>This file contains your private local session link. Do not upload or share it.</p><p><a href="'+escape(launch,quote=True)+'">Open the live graph</a></p>',text=True)
    if not args.no_browser:webbrowser.open(launch)
    p=next((p for p in active['projects']['projects'] if p['id']==args.id),registered.get('project',{}))
    return {'ok':True,'viewer_url':url,'version':identity['version'],'runtime_root':str(root),'source_commit':identity.get('commit'),'requested_ref':identity.get('requested_ref'),'home':str(data_home),'project_id':args.id,'project_revision':p.get('revision'),'watching':bool(active['projects'].get('watching')),'private_open_file':str(data_home/'open-viewer.html'),'connection_profile':str(args.install_root/'connection.json'),'reused_installation':identity.get('reused_installation',False),'browser_open_requested':not args.no_browser,'note':'Ready on loopback. Native WorkBuddy execution and actual browser behavior must still be verified on this machine.'}

def status(args):
    profile=read_json(args.install_root/'connection.json')
    if not profile:return {'ok':False,'running':False,'reason':'No connection profile; run connect first.'}
    state=probe(Path(profile['home']),profile['url'])
    return {'ok':bool(state),'running':bool(state),'url':profile['url'],'runtime_root':profile['runtime_root'],'home':profile['home'],'source_commit':profile.get('commit'),'version':state['health']['version'] if state else profile.get('version'),'watching':bool(state and state['projects'].get('watching')),'projects':state['projects']['projects'] if state else [],'reason':None if state else 'Server stopped or unreachable. No healthy live connection is claimed.'}

def stop(args):
    profile=read_json(args.install_root/'connection.json')
    if not profile:return {'ok':True,'stopped':False,'reason':'No connection profile.'}
    home=Path(profile['home']);active=probe(home,profile['url'])
    if not active:return {'ok':True,'stopped':False,'reason':'No reachable server for this profile.'}
    managed=read_json(home/'managed-host.json')
    if not managed or managed.get('url')!=profile['url'] or managed.get('runtime_root')!=profile['runtime_root']:
        raise SetupError('This process was not started by this helper. Stop its original terminal with Ctrl+C. No PID will be killed.')
    private_write(home/'stop-request.json',{'run_id':managed['run_id']})
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        if not probe(home,profile['url']):return {'ok':True,'stopped':True,'history_deleted':False}
        time.sleep(.2)
    raise SetupError('Managed stop did not complete promptly. Check the local log. No unrelated process was killed.')

def refresh(args):
    config=read_json(args.config,{}) if getattr(args, 'config', None) else read_json(CONFIG,{})
    previous=read_json(args.install_root/'connection.json')
    args.trust_source=True
    args.refresh=True
    args.local_source=None
    root,identity=acquire(args,config,previous)
    return {'ok':True,'refreshed':True,'runtime_root':str(root),'version':identity.get('version'),'commit':identity.get('commit')}

def cli():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--install-root',type=Path,default=DEFAULT_INSTALL,help='Trusted code cache/profile, outside your project')
    sub=p.add_subparsers(dest='action',required=False)
    for act in ('connect','init'):
        c=sub.add_parser(act,help='Install once (or reuse), register a source root, start/reuse a loopback host')
        c.add_argument('--project',default=None,help='Target project root (defaults to current working directory)')
        c.add_argument('--id',default=None,help='Unique lowercase project ID (defaults to folder name)')
        c.add_argument('--name',default=None,help='Project display name')
        c.add_argument('--config',type=Path);c.add_argument('--repo');c.add_argument('--ref');c.add_argument('--expected-commit');c.add_argument('--local-source')
        c.add_argument('--trust-source',action='store_true',help='Explicitly authorize first execution of the reviewed source')
        c.add_argument('--refresh',action='store_true',help='Force refresh cached runtime from remote repository')
        c.add_argument('--home',type=Path,default=DEFAULT_HOME);c.add_argument('--port',type=int,default=7331);c.add_argument('--interval',type=float,default=5.0);c.add_argument('--timeout',type=float,default=90);c.add_argument('--no-browser',action='store_true')
    r=sub.add_parser('refresh',help='Force refresh cached runtime from remote repository')
    r.add_argument('--config',type=Path);r.add_argument('--repo');r.add_argument('--ref');r.add_argument('--expected-commit')
    sub.add_parser('status');sub.add_parser('stop');sub.add_parser('open',help='Open private session locally; never print its token')
    args=p.parse_args();args.install_root=args.install_root.expanduser().resolve()
    if not args.action: args.action = 'connect'
    if sys.version_info<(3,10):raise SetupError('Python 3.10+ is required.')
    if args.action in ('connect','init'):
        args.home=args.home.expanduser().resolve()
        if not 1<=args.port<=65535:raise SetupError('Use a TCP port from 1 through 65535.')
        if not .1<=args.interval<=300:raise SetupError('Observer interval must be between 0.1 and 300 seconds.')
        with connect_lock(args.install_root):return connect(args)
    if args.action=='refresh':
        with connect_lock(args.install_root):return refresh(args)
    if args.action=='status':return status(args)
    if args.action=='stop':return stop(args)
    state=status(args)
    if not state['running']:raise SetupError(state['reason'])
    profile=read_json(args.install_root/'connection.json');token=(Path(profile['home'])/'session.token').read_text().strip()
    webbrowser.open(profile['url']+'/#token='+token)
    return {'ok':True,'browser_open_requested':True,'url':profile['url'],'note':'Opening was requested; this does not certify the browser page loaded.'}

if __name__=='__main__':
    try:result=cli();print(json.dumps(result,indent=2));sys.exit(0 if result.get('ok') else 1)
    except (SetupError,OSError,ValueError) as exc:print(json.dumps({'ok':False,'error':str(exc)},indent=2));sys.exit(2)
