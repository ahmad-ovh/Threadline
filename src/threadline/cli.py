"""Install once. Publish data, not frontend code. All non-server commands emit JSON."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
import uuid
import webbrowser
from . import __version__
from .demos import setup_demos, apply_demo_change
from .exporter import render_export
from .model import ContractError, ConflictError, MissingError, canonical, digest, slug
from .scanner import Scanner, Tracker, write_feature, write_suggestion
from .server import LocalServer
from .store import Store


def load_json(path: str):
    try:
        text=sys.stdin.read() if path=='-' else Path(path).read_text(encoding='utf-8')
        return json.loads(text)
    except (ValueError,OSError) as exc: raise ContractError(f'Cannot read JSON: {exc}') from exc

def add_project(store,path,ident=None,name=None):
    root=Path(path).expanduser().resolve()
    ident=ident or (slug(root.name)[:55]+'-'+digest(str(root))[:6])
    return store.register(ident,name or root.name,str(root))

def parser():
    p=argparse.ArgumentParser(prog='threadline',description='One viewer. Living codebases. Local graph tracking without frontend regeneration.')
    p.add_argument('--version',action='version',version='Threadline '+__version__)
    p.add_argument('--home',default=os.environ.get('THREADLINE_HOME',str(Path.home()/'.threadline')),help='Private local store (or THREADLINE_HOME)')
    sub=p.add_subparsers(dest='command')
    for name in ('demo','serve'):
        s=sub.add_parser(name,help='Run the two playable examples' if name=='demo' else 'Serve registered projects and watch for changes')
        s.add_argument('--port',type=int,default=7331)
        s.add_argument('--no-browser',action='store_true')
        s.add_argument('--no-watch',action='store_true')
        s.add_argument('--interval',type=float,default=5.0)
        if name=='serve':
            s.add_argument('--project',help='Optional project directory to register and scan')
            s.add_argument('--id');s.add_argument('--name')
    s=sub.add_parser('add',help='Authorize/register a local root and capture its first graph')
    s.add_argument('path');s.add_argument('--id');s.add_argument('--name')
    s=sub.add_parser('create',help='Create a project owned by an external publisher')
    s.add_argument('project');s.add_argument('--name',required=True)
    sub.add_parser('projects',help='List registered projects')
    sub.add_parser('doctor',help='Check the runtime and local storage')
    s=sub.add_parser('scan',help='Capture a stable observed batch; cache unchanged file analysis')
    s.add_argument('project');s.add_argument('--summary',default='Agent requested source scan');s.add_argument('--force',action='store_true')
    s=sub.add_parser('watch',help='Observe registered filesystem projects without opening the viewer')
    s.add_argument('--interval',type=float,default=5.0)
    s=sub.add_parser('snapshot',help='Read a current or historical graph')
    s.add_argument('project');s.add_argument('--revision',type=int)
    for name in ('publish','patch'):
        s=sub.add_parser(name,help='Publish a validated snapshot or incremental patch')
        s.add_argument('project')
        s.add_argument('file',nargs='?',default=None,help='JSON file, or - for stdin')
        s.add_argument('--json',dest='json_data',help='Inline JSON string for snapshot or patch')
        s.add_argument('--expected',type=int,default=None,help='Expected revision (default: current HEAD)')
        s.add_argument('--event-id',default=None,help='Unique event ID (default: auto-generated)')
        s.add_argument('--summary',default=None,help='Summary of changes')
        s.add_argument('--actor',default='WorkBuddy',help='Actor reporting the change')
    s=sub.add_parser('checkpoint',help='Name a logical milestone without deleting atomic revisions')
    s.add_argument('project');s.add_argument('name');s.add_argument('--note',default='');s.add_argument('--revision',type=int)
    s=sub.add_parser('history',help='Read retained atomic revisions')
    s.add_argument('project');s.add_argument('--limit',type=int,default=100);s.add_argument('--before',type=int)
    s=sub.add_parser('diff',help='Compare two graph revisions')
    s.add_argument('project');s.add_argument('before',type=int);s.add_argument('after',type=int)
    s=sub.add_parser('context',help='Retrieve a bounded context neighborhood for an agent')
    s.add_argument('project');s.add_argument('--query',default='');s.add_argument('--node');s.add_argument('--depth',type=int,default=1)
    s.add_argument('--limit',type=int,default=30);s.add_argument('--revision',type=int)
    s=sub.add_parser('source',help='Read retained source text at an exact graph revision')
    s.add_argument('project');s.add_argument('path');s.add_argument('--revision',type=int)
    s=sub.add_parser('feature',help='Write/update a reviewed, source-hashed feature mapping; edits .threadline/features.json')
    s.add_argument('project');s.add_argument('--id',required=True);s.add_argument('--name',required=True)
    s.add_argument('--description',required=True);s.add_argument('--files',nargs='+',required=True);s.add_argument('--author',default='agent')
    s=sub.add_parser('suggest',help='Register/update an AI feature suggestion; edits .threadline/suggestions.json')
    s.add_argument('project');s.add_argument('--id',required=True);s.add_argument('--name',required=True)
    s.add_argument('--description',required=True);s.add_argument('--target',default='module:.')
    s.add_argument('--rationale',default='');s.add_argument('--prompt',default='');s.add_argument('--author',default='ai-pipeline')
    s=sub.add_parser('export',help='Export a source-text-free data bundle or self-contained HTML view')
    s.add_argument('project');s.add_argument('--out',required=True);s.add_argument('--format',choices=['json','html'],default='json');s.add_argument('--no-history',action='store_true')
    s=sub.add_parser('demo-change',help='Apply/revert a SCRIPTED code change only in a bundled demo copy')
    s.add_argument('project',choices=['lantern-harbor','orbit-courier'])
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    command=args.command or 'demo'
    # No arguments is the friendly demo entrypoint.
    if args.command is None:
        args=parser().parse_args(['--home',args.home,'demo'])
    try:
        store=Store(args.home)
        if command in ('demo','serve'):
            if command=='demo': setup_demos(store)
            elif args.project:
                project=add_project(store,args.project,args.id,args.name)
                Scanner(store,project['id']).scan('Project connected',actor='user')
            tracker=Tracker(store,args.interval)
            server=LocalServer(store,tracker,args.port)
            if not args.no_watch: tracker.start()
            print('\n  THREADLINE '+__version__+'  /  Local-first codebase workbench',file=sys.stderr)
            print('  Open: '+server.launch_url,file=sys.stderr)
            print('  Store: '+str(store.directory),file=sys.stderr)
            print('  Watcher: '+('paused' if args.no_watch else f'observing every {tracker.interval:g}s'),file=sys.stderr)
            print('  Ctrl+C to stop. No code is sent to a hosted service.\n',file=sys.stderr)
            if not args.no_browser:
                timer=threading.Timer(0.5,lambda:webbrowser.open(server.launch_url));timer.daemon=True;timer.start()
            try: server.serve_forever(poll_interval=0.3)
            except KeyboardInterrupt: pass
            finally:
                server.stopping.set();tracker.stop();server.server_close()
            return 0
        if command=='add':
            project=add_project(store,args.path,args.id,args.name)
            result={'project':project,'scan':Scanner(store,project['id']).scan('Project connected',actor='user')}
            result['scan'].pop('delta',None)
        elif command=='create': result=store.register(args.project,args.name,mode='published')
        elif command=='projects': result={'projects':store.projects()}
        elif command=='doctor':
            with store.connection() as db: integrity=db.execute('PRAGMA quick_check').fetchone()[0]
            result={'ok':integrity=='ok','version':__version__,'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,
                    'databaseCheck':integrity,'home':str(store.directory),'projects':len(store.projects()),
                    'runtimeDependencies':[],'notes':['Bind is loopback-only; do not expose this server to the internet.','Source blobs are retained locally for indexed text files; exports omit their bodies.']}
        elif command=='scan': result=Scanner(store,args.project).scan(args.summary,actor='coding-agent',force=args.force)
        elif command=='watch':
            tracker=Tracker(store,args.interval);tracker.start()
            print('Observing local projects. Ctrl+C to stop.',file=sys.stderr)
            try:
                while True: time.sleep(1)
            except KeyboardInterrupt: tracker.stop()
            return 0
        elif command=='snapshot': result=store.snapshot(args.project,args.revision)
        elif command in ('publish','patch'):
            project=store.project(args.project)
            if command=='publish' and project['mode']!='published':
                raise ContractError('Scanner owns this project. Use incremental patch or create a separate publisher-owned project.')
            if args.json_data:
                try: data=json.loads(args.json_data)
                except (ValueError,TypeError) as exc: raise ContractError(f'Invalid inline JSON: {exc}') from exc
            elif args.file:
                data=load_json(args.file)
            else:
                raise ContractError('Provide a JSON file or --json "<content>"')
            expected=store.head(args.project) if args.expected is None else args.expected
            event_id=args.event_id or f'wb-{uuid.uuid4().hex[:12]}'
            summary=args.summary or (f'Incremental {command} from {args.actor}' if command=='patch' else f'Published snapshot from {args.actor}')
            result=store.publish(data if command=='publish' else None,project_id=args.project,patch=data if command=='patch' else None,
                                 expected=expected,event_id=event_id,summary=summary,actor=args.actor,kind=command)
        elif command=='checkpoint': result=store.checkpoint(args.project,args.name,args.note,args.revision)
        elif command=='history': result={'events':store.history(args.project,args.limit,args.before),'checkpoints':store.checkpoints(args.project)}
        elif command=='diff': result=store.compare(args.project,args.before,args.after)
        elif command=='context': result=store.query(args.project,args.query,args.node,args.depth,args.limit,args.revision)
        elif command=='source': result=store.source(args.project,args.path,args.revision)
        elif command=='feature':
            project=store.project(args.project)
            if project['mode']!='filesystem': raise ContractError('Use graph publication for feature nodes in a publisher-owned project')
            path=write_feature(Path(project['root']),args.id,args.name,args.files,args.description,args.author)
            result={'manifest':str(path),'update':Scanner(store,args.project).scan('Feature mapping reviewed: '+args.name,actor=args.author)}
            result['update'].pop('delta',None)
        elif command=='suggest':
            project=store.project(args.project)
            if project['mode']!='filesystem': raise ContractError('Use graph publication for suggestion nodes in a publisher-owned project')
            path=write_suggestion(Path(project['root']),args.id,args.name,args.target,args.description,args.rationale,args.prompt,args.author)
            result={'manifest':str(path),'update':Scanner(store,args.project).scan('Feature suggestion added: '+args.name,actor=args.author)}
            result['update'].pop('delta',None)
        elif command=='export':
            bundle=store.export(args.project,not args.no_history)
            file=Path(args.out).expanduser().resolve();file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text(render_export(bundle) if args.format=='html' else json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
            result={'out':str(file),'format':args.format,'revision':bundle['snapshot']['revision'],'sourceTextIncluded':False,
                    'historyTruncated':bundle.get('historyTruncated',False)}
        elif command=='demo-change':
            result=apply_demo_change(store,args.project)
            result['update']=Scanner(store,args.project).scan(result['summary'],actor=result['actor']);result['update'].pop('delta',None)
        else: raise ContractError('Unknown command')
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
        return 0
    except (ContractError,ConflictError,MissingError,OSError,ValueError) as exc:
        print(json.dumps({'error':str(exc),'type':type(exc).__name__}),file=sys.stderr)
        return 2
