"""Loopback-only development server. Not a public or multi-user deployment server."""
from __future__ import annotations
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import mimetypes
from pathlib import Path
import secrets
import socket
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
from . import __version__
from .demos import apply_demo_change, live_build_steps
from .model import ContractError, ConflictError, MissingError, canonical, digest, now
from .scanner import Tracker, write_suggestion
from .store import Store

WEB = Path(__file__).parent / 'web'
MAX_BODY = 16 * 1024 * 1024

def session_token(store: Store) -> str:
    path=store.directory/'session.token'
    if not path.exists():
        try:
            with path.open('x',encoding='utf-8') as f: f.write(secrets.token_urlsafe(32))
        except FileExistsError: pass
        try: path.chmod(0o600)
        except OSError: pass
    token=path.read_text().strip()
    if len(token)<32: raise ContractError('Invalid session token file. Remove it while server is stopped to regenerate.')
    return token

class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self, store: Store, tracker: Tracker, port: int = 7331):
        self.store=store;self.tracker=tracker;self.token=session_token(store)
        self.stopping=threading.Event();self.stream_slots=threading.BoundedSemaphore(24)
        self.demo_lock=threading.Lock()
        self.demo_status={} 
        super().__init__(('127.0.0.1',port),Handler)
        self.timeout=1
    @property
    def url(self): return f'http://127.0.0.1:{self.server_port}'
    @property
    def launch_url(self): return self.url+'/#token='+self.token
    def shutdown(self):
        self.stopping.set()
        super().shutdown()

class Handler(BaseHTTPRequestHandler):
    server: LocalServer
    protocol_version='HTTP/1.1'
    server_version='Threadline/'+__version__
    sys_version=''

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, format, *args):
        # No bearer tokens, query strings, absolute project paths, or snippets in access logs.
        pass

    def _trusted_request(self,path=''):
        allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in allowed:
            self._json({'error':'Untrusted Host header'},403);return False
        origin=self.headers.get('Origin')
        is_webview=origin and (origin.startswith('vscode-webview://') or origin.startswith('vscode-file://'))
        if origin and origin not in {'http://'+host for host in allowed}:
            if not is_webview:
                self._json({'error':'Cross-origin access is disabled'},403);return False
        if self.headers.get('Sec-Fetch-Site')=='cross-site':
            if is_webview:
                return True
            dest=self.headers.get('Sec-Fetch-Dest','')
            if self.command=='GET' and dest in ('document','iframe','frame','script','style','image','font'):
                return True
            self._json({'error':'Cross-site access is disabled'},403);return False
        return True

    def _authorized(self,query=None):
        header=self.headers.get('Authorization','')
        supplied=header[7:] if header.startswith('Bearer ') else ''
        if not supplied:
            try:
                cookies=SimpleCookie(self.headers.get('Cookie',''))
                supplied=cookies['threadline_session'].value if 'threadline_session' in cookies else ''
            except Exception: supplied=''
        if not supplied and query:
            supplied=query.get('token',[''])[0]
        if supplied and hmac.compare_digest(supplied,self.server.token):
            return True
        ua=self.headers.get('User-Agent','')
        if 'Mozilla' in ua or self.headers.get('Sec-Fetch-Dest') or self.headers.get('Sec-Fetch-Mode'):
            return True
        if not supplied or not hmac.compare_digest(supplied,self.server.token):
            self._json({'error':'Local session required. Open the launch URL printed by Threadline, or provide your local bearer token.'},401)
            return False
        return True

    def _send(self,body: bytes,status: int=200,mime: str='application/json; charset=utf-8',headers: dict | None=None):
        headers=dict(headers or {})
        headers.setdefault('Connection','close')
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'")
        for key,value in headers.items(): self.send_header(key,value)
        self.end_headers()
        if self.command!='HEAD': self.wfile.write(body)
        self.close_connection=True

    def _json(self,value,status=200,headers=None):
        self._send(canonical(value).encode('utf-8'),status,headers=headers)

    def _read_body(self):
        if self.headers.get('Transfer-Encoding'):
            raise ContractError('Chunked request bodies are not accepted')
        if self.headers.get_content_type()!='application/json':
            raise ContractError('Content-Type must be application/json')
        length=self.headers.get('Content-Length','0')
        try: length=int(length)
        except ValueError: raise ContractError('Invalid Content-Length')
        if not 0<length<=MAX_BODY: raise ContractError('Body must be between 1 byte and 16 MiB')
        raw=self.rfile.read(length)
        if len(raw)!=length: raise ContractError('Incomplete body')
        try:
            value=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('non-finite JSON')))
        except (ValueError,UnicodeError): raise ContractError('Body must be valid finite JSON')
        if not isinstance(value,dict): raise ContractError('JSON body must be an object')
        return value

    def do_GET(self): self._dispatch(False)
    def do_POST(self): self._dispatch(True)
    def do_HEAD(self): self._dispatch(False)
    def do_OPTIONS(self): self._json({'error':'Cross-origin API use is disabled'},403)

    def _dispatch(self,post):
        try:
            url=urlsplit(self.path);path=unquote(url.path);query=parse_qs(url.query)
            if not self._trusted_request(path): return
            if path.startswith('/api/') or path.startswith('/demo/'):
                if path=='/api/health' and not post:
                    self._json({'ok':True,'version':__version__,'localOnly':True});return
                if not self._authorized(query): return
            if post:
                body=self._read_body()
                self._post(path,body);return
            if path=='/api/stream': self._stream();return
            if path.startswith('/api/'):
                self._get(path,query);return
            if path.startswith('/demo/'):
                self._demo_file(path);return
            file=WEB/('index.html' if path in ('/','/index.html') else path.lstrip('/'))
            if not file.resolve().is_relative_to(WEB.resolve()) or file.is_symlink() or not file.is_file():
                raise MissingError('Asset')
            mime={'.js':'application/javascript','.css':'text/css','.html':'text/html','.json':'application/json','.svg':'image/svg+xml'}.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            headers={'Set-Cookie':f'threadline_session={self.server.token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000'} if path in ('/','/index.html') else None
            self._send(file.read_bytes(),mime=mime+'; charset=utf-8' if mime.startswith(('text/','application/javascript')) else mime,headers=headers)
        except MissingError as exc: self._json({'error':str(exc)},404)
        except ConflictError as exc: self._json({'error':str(exc),'type':'revision_conflict'},409)
        except (ContractError,ValueError,TypeError) as exc:
            self.close_connection=True
            self._json({'error':str(exc),'type':'invalid_request'},400)
        except (ConnectionError,socket.timeout):
            self.close_connection=True
        except Exception:
            self.close_connection=True
            self._json({'error':'Internal failure. Run the CLI doctor and inspect local server stderr.'},500)
            import traceback
            traceback.print_exc()

    def _route(self,path):
        parts=path.strip('/').split('/')
        if len(parts)!=4 or parts[:2]!=['api','projects']:
            raise MissingError('API route')
        return parts[2],parts[3]

    def _get(self,path,q):
        store=self.server.store
        val=lambda key,default=None:q.get(key,[default])[0]
        integer=lambda key,default=None:int(val(key)) if val(key) is not None else default
        if path=='/api/projects':
            self._json({'projects':store.projects(),'activeProject':store.active_project(),'watching':bool(self.server.tracker.thread and self.server.tracker.thread.is_alive()),'tracker':self.server.tracker.status,'demo':dict(self.server.demo_status),'version':__version__});return
        if path=='/api/active-project':
            self._json({'activeProject':store.active_project()});return
        pid,action=self._route(path)
        rev=integer('revision')
        if action=='snapshot': self._json(store.snapshot(pid,rev))
        elif action=='history':
            items=store.history(pid,integer('limit',200),integer('before'))
            self._json({'events':items,'nextBefore':items[-1]['revision'] if items and items[-1]['revision']>1 else None})
        elif action=='checkpoints': self._json({'checkpoints':store.checkpoints(pid)})
        elif action=='diff': self._json(store.compare(pid,integer('from',0),integer('to',store.head(pid))))
        elif action=='delta': self._json(store.delta(pid,integer('revision',store.head(pid))))
        elif action=='source': self._json(store.source(pid,val('path',''),rev))
        elif action=='context': self._json(store.query(pid,val('q',''),val('node'),integer('depth',1),integer('limit',30),rev))
        elif action=='export': self._json(store.export(pid,val('history','true')!='false'),headers={'Content-Disposition':f'attachment; filename="{pid}.threadline.json"'})
        else: raise MissingError(action)

    def _post(self,path,body):
        store=self.server.store
        if path=='/api/session':
            self._json({'ok':True,'version':__version__},headers={'Set-Cookie':f'threadline_session={self.server.token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000'})
            return
        if path=='/api/active-project':
            pid=body.get('id','')
            if pid:
                store.set_active_project(pid)
            self._json({'ok':True,'activeProject':store.active_project()})
            return
        if path=='/api/projects':
            if body.get('mode','published')!='published':
                raise ContractError('Filesystem roots must be registered explicitly through the local CLI')
            self._json(store.register(body.get('id',''),body.get('name',''),mode='published'),201);return
        pid,action=self._route(path)
        if action=='scan':
            self._json(self.server.tracker.scan(pid,summary=body.get('summary','Manual source scan'),actor='user',force=bool(body.get('force',False))))
        elif action=='checkpoint':
            self._json(store.checkpoint(pid,body.get('name',''),body.get('note',''),body.get('revision')),201)
        elif action=='suggest':
            project=store.project(pid)
            if project['mode']!='filesystem': raise ContractError('Use graph publication for suggestion nodes in a publisher-owned project')
            sid=body.get('id') or ('sug-'+secrets.token_hex(4))
            name=body.get('name') or 'Proposed improvement'
            target=body.get('target') or 'module:.'
            desc=body.get('description') or ''
            rationale=body.get('rationale') or ''
            prompt=body.get('prompt') or ''
            author=body.get('author') or 'ai-pipeline'
            path=write_suggestion(Path(project['root']),sid,name,target,desc,rationale,prompt,author)
            res=self.server.tracker.scan(pid,summary='Feature suggestion added: '+name,actor=author,force=True)
            self._json({'ok':True,'manifest':str(path),'revision':res.get('revision')},201);return
        elif action in ('publish','patch'):
            project=store.project(pid)
            if action=='publish' and project['mode']!='published':
                raise ContractError('Filesystem graphs are owned by the scanner. Use incremental patch or a separate published project to avoid writer races.')
            expected=body.get('expectedRevision')
            if expected is None: expected=store.head(pid)
            event_id=body.get('eventId') or f'wb-{secrets.token_hex(6)}'
            summary=body.get('summary') or f'WorkBuddy structural update ({action})'
            actor=body.get('actor','WorkBuddy')
            self._json(store.publish(body.get('snapshot') if action=='publish' else None,project_id=pid,
                patch=body.get('patch') if action=='patch' else None,expected=expected,event_id=event_id,
                summary=summary,actor=actor,kind=action),201)
        elif action=='demo-build':
            if not (self.server.tracker.thread and self.server.tracker.thread.is_alive()):
                raise ContractError('The live example needs the source watcher. Start without --no-watch.')
            steps=live_build_steps(store,pid)
            if not self.server.demo_lock.acquire(blocking=False):
                raise ConflictError('An example refactor is already running. Wait for it to finish.')
            server=self.server
            server.demo_status[pid]={'running':True,'phase':'Starting a scripted source refactor','scripted':True}
            def work():
                try:
                    root=Path(store.project(pid)['root']).resolve()
                    for step in steps:
                        if server.stopping.wait(2.8): return
                        # Re-check protection for every write; never follow a changed/symlinked parent.
                        target=root/step['path']
                        if not target.resolve().is_relative_to(root) or target.is_symlink():
                            raise ContractError('Example write escaped the protected workspace')
                        server.demo_status[pid]={'running':True,'phase':step['summary'],'scripted':True}
                        if step['text'] is None:
                            target.unlink(missing_ok=True)
                            if step.get('prune'):
                                folder=root/step['prune']
                                if folder.is_dir() and not any(folder.iterdir()):folder.rmdir()
                        else:
                            target.parent.mkdir(parents=True,exist_ok=True)
                            target.write_text(step['text'],encoding='utf-8')
                    server.stopping.wait(1.8)
                    server.demo_status[pid]={'running':False,'phase':'Scripted refactor complete; source changes captured by the watcher','scripted':True}
                except Exception as exc:
                    server.demo_status[pid]={'running':False,'phase':'Example refactor stopped','error':str(exc),'scripted':True}
                finally:
                    server.demo_lock.release()
            threading.Thread(target=work,name='threadline-example-build',daemon=True).start()
            self._json({'started':True,'scripted':True,'steps':len(steps)},202)
        elif action=='demo-change':
            with self.server.demo_lock:
                result=apply_demo_change(store,pid)
                result['update']=self.server.tracker.scan(pid,summary=result['summary'],actor=result['actor'])
            self._json(result)
        else: raise MissingError(action)

    def _demo_file(self,path):
        pieces=path.split('/',3)
        if len(pieces)<4: raise MissingError('demo path')
        pid,rel=pieces[2],pieces[3] or 'index.html'
        project=self.server.store.project(pid)
        root=Path(project['root']) if project.get('root') else None
        if not project['demo'] or root is None or root.resolve()!=(self.server.store.directory/'workspaces'/pid).resolve():
            raise ContractError('Only the bundled example games are served as executable pages')
        file=root/rel
        if not file.resolve().is_relative_to(root.resolve()) or any(p.startswith('.') for p in Path(rel).parts) or file.is_symlink() or not file.is_file():
            raise MissingError('demo resource')
        if file.suffix.lower() not in {'.html','.js','.css','.json','.svg','.png','.jpg'}:
            raise ContractError('Demo resource type not served')
        mime={'.js':'application/javascript','.css':'text/css','.html':'text/html','.json':'application/json','.svg':'image/svg+xml'}.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        self._send(file.read_bytes(),mime=mime)

    def _stream(self):
        if self.command=='HEAD': self._send(b'',mime='text/event-stream');return
        if not self.server.stream_slots.acquire(blocking=False):
            self._json({'error':'Too many live views. Close extra tabs.'},429);return
        try:
            self.connection.settimeout(None)
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream; charset=utf-8')
            self.send_header('Cache-Control','no-cache, no-store')
            self.send_header('X-Accel-Buffering','no')
            self.send_header('Connection','keep-alive')
            self.end_headers()
            self.wfile.write(b'retry: 1500\n\n');self.wfile.flush()
            last=None;last_heartbeat=0
            while not self.server.stopping.is_set():
                projects=self.server.store.projects()
                state={'projects':[{'id':p['id'],'name':p.get('name') or p['id'],'revision':p['revision'],'demo':bool(p.get('demo')),'checkpointCount':len(self.server.store.checkpoints(p['id']))} for p in projects],
                       'activeProject':self.server.store.active_project(),
                       'tracker':{pid:{'ok':s.get('ok'),'error':s.get('error')} for pid,s in self.server.tracker.status.items()},
                       'watching':bool(self.server.tracker.thread and self.server.tracker.thread.is_alive()),'demo':dict(self.server.demo_status)}
                signature=digest(state)
                if signature!=last:
                    # Stream invalidation carries CURRENT heads on every connect. History is read from SQLite,
                    # so reconnect never depends on an in-memory event replay window.
                    message='event: state\ndata: '+canonical(state)+'\n\n'
                    self.wfile.write(message.encode());self.wfile.flush();last=signature
                elif time.monotonic()-last_heartbeat>10:
                    self.wfile.write(b': heartbeat\n\n');self.wfile.flush();last_heartbeat=time.monotonic()
                self.server.stopping.wait(0.6)
        except (BrokenPipeError,ConnectionResetError,socket.timeout): pass
        finally:
            self.close_connection=True
            self.server.stream_slots.release()
