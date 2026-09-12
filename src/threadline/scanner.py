"""Incremental, conservative reference extraction. Never executes repository code.

Python imports use the AST. JS/TS and Godot adapters extract literal references,
not call-graph or runtime proofs. The watcher is a polling observation boundary,
not a claim to capture keystrokes or every intermediate filesystem state.
"""
from __future__ import annotations
import ast
from dataclasses import dataclass
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import threading
import time
import uuid
from .model import (ContractError, ConflictError, MissingError, sha, digest, now, safe_relative, slug)
from .store import Store

SKIP_DIRS = {'.git','.hg','.svn','.threadline','node_modules','__pycache__','.venv','venv','env',
             'dist','build','target','coverage','.next','.godot','vendor','Library','Temp','obj','bin'}
SENSITIVE = ('.env*','*.pem','*.key','*.p12','*.pfx','*credentials*','*secrets*','id_rsa*','id_ed25519*')
TEXT_EXT = {'.py','.js','.mjs','.cjs','.jsx','.ts','.tsx','.gd','.tscn','.tres','.godot','.json',
            '.md','.txt','.yaml','.yml','.toml','.html','.css','.svg','.rs','.go','.java','.c','.h','.cpp','.cs','.sh'}
LANGUAGE = {'.py':'Python','.js':'JavaScript','.mjs':'JavaScript','.cjs':'JavaScript','.jsx':'JavaScript',
            '.ts':'TypeScript','.tsx':'TypeScript','.gd':'GDScript','.tscn':'Godot scene','.tres':'Godot resource',
            '.md':'Markdown','.json':'JSON','.html':'HTML','.css':'CSS','.godot':'Godot config'}
MAX_FILES = 4000
MAX_FILE_BYTES = 1024 * 1024

def edge_id(source: str, kind: str, target: str, discriminator: str = '') -> str:
    return 'edge:' + digest([source,kind,target,discriminator])[:24]

def edge(source: str, target: str, kind: str, evidence: list | None = None, **extra) -> dict:
    return {"id":edge_id(source,kind,target),"source":source,"target":target,"kind":kind,"evidence":evidence or [],**extra}

def js_tokens(text: str) -> list[tuple[str,str,int]]:
    # Lex just enough to distinguish strings and comments from literal import syntax.
    pattern = re.compile(r'(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(?P<template>`(?:\\.|[^`\\])*`)|(?P<id>[A-Za-z_$][\w$]*)|(?P<punct>.)')
    return [(m.lastgroup,m.group(),text.count('\n',0,m.start())+1) for m in pattern.finditer(text)
            if m.lastgroup not in ('space','comment','template')]

def analyze(path: str, text: str) -> dict:
    ext = PurePosixPath(path).suffix.lower()
    out = {'symbols':[], 'imports':[], 'diagnostics':[]}
    if ext == '.py':
        try:
            tree = ast.parse(text,filename=path)
        except SyntaxError as exc:
            out['diagnostics'].append({'path':path,'level':'warning','message':f'Python parse failed at line {exc.lineno}; imports/symbols omitted until fixed.'})
            return out
        def walk(body, prefix=''):
            for n in body:
                if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                    name = prefix+n.name
                    out['symbols'].append({'name':name,'line':n.lineno,'endLine':n.end_lineno or n.lineno,'type':'class' if isinstance(n,ast.ClassDef) else 'function','method':'python-ast'})
                    if isinstance(n,ast.ClassDef):
                        walk(n.body,name+'.')
        walk(tree.body)
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                for alias in node.names:
                    out['imports'].append({'spec':alias.name,'line':node.lineno,'method':'python-ast','status':'observed','level':0,'members':[]})
            elif isinstance(node,ast.ImportFrom):
                out['imports'].append({'spec':node.module or '', 'line':node.lineno,'method':'python-ast','status':'observed',
                                       'level':node.level,'members':[a.name for a in node.names]})
    elif ext in {'.js','.mjs','.cjs','.jsx','.ts','.tsx'}:
        toks = js_tokens(text)
        for i, (kind,value,line) in enumerate(toks):
            if kind != 'id': continue
            if value in ('import','export','require'):
                # import/export ... from 'literal'; import('literal'); require('literal'); side-effect import.
                selected = None
                if i+1 < len(toks) and toks[i+1][0]=='string' and value=='import':
                    selected=toks[i+1]
                elif i+2<len(toks) and toks[i+1][1]=='(' and toks[i+2][0]=='string' and value in ('import','require'):
                    selected=toks[i+2]
                else:
                    for j in range(i+1,min(len(toks)-1,i+80)):
                        if toks[j][1]==';' or toks[j][2]>line+12: break
                        if toks[j][1]=='from' and toks[j+1][0]=='string':
                            selected=toks[j+1]; break
                        if j>i+1 and toks[j][1] in ('import','export'): break
                if selected:
                    out['imports'].append({'spec':selected[1][1:-1], 'line':line, 'method':'js-literal-reference','status':'lexical'})
            if value in ('function','class') and i+1<len(toks) and toks[i+1][0]=='id':
                out['symbols'].append({'name':toks[i+1][1],'line':line,'endLine':line,'type':value,'method':'js-declaration-lexical'})
            if value in ('const','let') and i+2<len(toks) and toks[i+1][0]=='id' and toks[i+2][1]=='=':
                prev = toks[max(0,i-1)][1]
                following = [t[1] for t in toks[i+3:i+18]]
                if prev == 'export' or ('>' in following and '=' in following):
                    out['symbols'].append({'name':toks[i+1][1],'line':line,'endLine':line,'type':'binding','method':'js-declaration-lexical'})
    elif ext in {'.gd','.tscn','.tres','.godot'}:
        for num,line in enumerate(text.splitlines(),1):
            if line.lstrip().startswith(('#',';')): continue
            for match in re.finditer(r'(?:preload|load)\s*\(\s*[\'"]([^\'"]+)[\'"]|(?:path|extends)\s*(?:=\s*)?[\'"](res://[^\'"]+)[\'"]',line):
                out['imports'].append({'spec':match.group(1) or match.group(2),'line':num,'method':'godot-literal-resource','status':'lexical'})
            if ext=='.godot':
                for match in re.finditer(r"=\s*['\"]\*?(res://[^'\"]+)['\"]",line):
                    out['imports'].append({'spec':match[1],'line':num,'method':'godot-project-setting','status':'lexical'})
            elif ext=='.gd':
                for match in re.finditer(r"\bchange_scene_to_file\s*\(\s*['\"](res://[^'\"]+)['\"]",line):
                    out['imports'].append({'spec':match[1],'line':num,'method':'godot-scene-transition-literal','status':'lexical'})
            match = re.match(r'\s*(?:static\s+)?(func|class_name)\s+(\w+)',line)
            if match:
                out['symbols'].append({'name':match[2],'line':num,'endLine':num,'type':match[1],'method':'godot-declaration-lexical'})
    elif ext == '.html':
        for match in re.finditer(r'<(?:script|link)\b[^>]*?\b(?:src|href)\s*=\s*[\'"]([^\'"]+)[\'"]',text,re.I):
            out['imports'].append({'spec':match[1], 'line':text.count('\n',0,match.start())+1,'method':'html-resource-reference','status':'lexical'})
    return out

@dataclass
class CacheEntry:
    signature: tuple
    hash: str
    text: str | None
    analysis: dict
    size: int

class Scanner:
    def __init__(self, store: Store, project_id: str):
        self.store = store
        self.project_id = project_id
        self.cache: dict[str,CacheEntry] = {}
        self.lock = threading.RLock()
        self.last_stats: dict = {}
        self._git_cache: dict = {}

    def _git(self, root: Path, *args: str) -> bytes | None:
        try:
            extra = {}
            if os.name == 'nt':
                extra['creationflags'] = subprocess.CREATE_NO_WINDOW
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                extra['startupinfo'] = si
            result = subprocess.run(['git','-C',str(root),*args],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=8,check=False,**extra)
            return result.stdout if result.returncode==0 else None
        except (OSError,subprocess.TimeoutExpired): return None

    def _paths(self, root: Path) -> tuple[list[tuple[str,Path,tuple]],list[dict]]:
        warnings=[]
        listed = self._git(root,'ls-files','--cached','--others','--exclude-standard','-z','--','.')
        rules=[]
        ignore=root/'.threadlineignore'
        if ignore.is_file() and not ignore.is_symlink():
            rules=[line.strip() for line in ignore.read_text(errors='replace').splitlines() if line.strip() and not line.startswith('#')]
        if listed is not None:
            candidates=[root/os.fsdecode(x) for x in listed.split(b'\0') if x]
        else:
            candidates=[]
            for parent,dirs,files in os.walk(root,followlinks=False):
                dirs[:]=sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.') and not (Path(parent)/d).is_symlink())
                candidates.extend(Path(parent)/name for name in sorted(files))
        output=[]
        for file in sorted(set(candidates)):
            try:
                rel=file.relative_to(root).as_posix()
                if not safe_relative(rel) or file.is_symlink(): continue
                parts=PurePosixPath(rel).parts
                if any(p in SKIP_DIRS or p.startswith('.') for p in parts): continue
                if any(fnmatch.fnmatch(file.name.lower(),rule) for rule in SENSITIVE): continue
                if any(fnmatch.fnmatch(rel,rule) or rel.startswith(rule.rstrip('/')+'/') for rule in rules): continue
                # A nested directory symlink also must not escape or expose outside files.
                if any((root/Path(*parts[:i])).is_symlink() for i in range(1,len(parts))): continue
                if not file.resolve().is_relative_to(root): continue
                stat=file.stat()
                if not file.is_file(): continue
                if stat.st_size>MAX_FILE_BYTES:
                    warnings.append({'path':rel,'level':'warning','message':'File exceeds 1 MiB scan cap; not indexed.'}); continue
                output.append((rel,file,(stat.st_mtime_ns,stat.st_ctime_ns,stat.st_size)))
            except (OSError,ValueError): continue
            if len(output)>=MAX_FILES:
                warnings.append({'level':'warning','message':f'Scan cap of {MAX_FILES} files reached. Coverage is partial.'}); break
        return output,warnings

    def _features(self, root: Path) -> tuple[dict,str]:
        file=root/'.threadline'/'features.json'
        if not file.exists(): return {'features':[]},digest({})
        if file.is_symlink() or (root/'.threadline').is_symlink() or not file.resolve().is_relative_to(root):
            raise ContractError('Feature manifest must not be a symlink')
        if file.stat().st_size>MAX_FILE_BYTES:
            raise ContractError('Feature manifest too large')
        raw=file.read_bytes()
        try:
            manifest=json.loads(raw)
        except (ValueError,UnicodeError) as exc: raise ContractError(f'Invalid .threadline/features.json: {exc}') from exc
        if not isinstance(manifest,dict) or not isinstance(manifest.get('features'),list) or len(manifest['features'])>500:
            raise ContractError('Manifest must have a features array (max 500)')
        return manifest,sha(raw)

    def _default_suggestions(self) -> dict:
        return {'version': '1.0', 'suggestions': [
            {
                'id': 'pipeline-ci',
                'name': 'CI/CD & Test Automation',
                'target': 'module:.',
                'description': 'Automated regression test runner and continuous integration pipeline for code changes.',
                'rationale': 'Prevents syntax errors and regressions before merging agent-authored modifications, safeguarding system stability.',
                'prompt': 'Add an automated test and lint workflow (e.g. GitHub Actions or package.json test script) to verify build and test integrity.',
                'author': 'ai-pipeline',
                'status': 'proposed'
            },
            {
                'id': 'pipeline-telemetry',
                'name': 'Health & Error Diagnostics',
                'target': 'module:.',
                'description': 'Centralized error boundary handling, structured runtime logging, and health probe check.',
                'rationale': 'Captures actionable failure context and diagnostic logs so WorkBuddy can troubleshoot runtime issues without manual inspection.',
                'prompt': 'Implement structured diagnostic logging and a runtime health check endpoint to streamline error identification.',
                'author': 'ai-pipeline',
                'status': 'proposed'
            }
        ]}

    def _suggestions(self, root: Path) -> tuple[dict, str]:
        file = root / '.threadline' / 'suggestions.json'
        if not file.exists():
            defaults = self._default_suggestions()
            return defaults, digest(defaults)
        if file.is_symlink() or (root / '.threadline').is_symlink() or not file.resolve().is_relative_to(root):
            raise ContractError('Suggestions manifest must not be a symlink')
        if file.stat().st_size > MAX_FILE_BYTES:
            raise ContractError('Suggestions manifest too large')
        raw = file.read_bytes()
        try:
            manifest = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ContractError(f'Invalid .threadline/suggestions.json: {exc}') from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get('suggestions'), list) or len(manifest['suggestions']) > 500:
            raise ContractError('Manifest must have a suggestions array (max 500)')
        return manifest, sha(raw)

    def build(self, project: dict) -> tuple[dict,dict]:
        root=Path(project['root']).resolve()
        if not root.is_dir(): raise ContractError(f"Project root is unavailable: {root}")
        started=time.perf_counter()
        files,warnings=self._paths(root)
        manifest,manifest_hash=self._features(root)
        suggestions,suggestions_hash=self._suggestions(root)
        reads=0
        active={p for p,_,_ in files}
        self.cache={k:v for k,v in self.cache.items() if k in active}
        for rel,path,signature in files:
            cached=self.cache.get(rel)
            if cached and cached.signature==signature: continue
            try:
                raw=path.read_bytes()
                post=path.stat()
            except OSError as exc:
                raise ConflictError('Files changed while reading; retry scan') from exc
            if (post.st_mtime_ns,post.st_ctime_ns,post.st_size)!=signature:
                raise ConflictError('File changed while reading; retry scan')
            reads+=1
            text=None
            if path.suffix.lower() in TEXT_EXT or path.name.lower() in ('readme','license','dockerfile','makefile'):
                try: text=raw.decode('utf-8')
                except UnicodeError: pass
            if text is not None and '\x00' in text: text=None
            self.cache[rel]=CacheEntry(signature,sha(raw),text,analyze(rel,text) if text is not None else {'symbols':[],'imports':[],'diagnostics':[]},len(raw))
        # No mixed-time source claim: reject a batch changed during the observation window.
        after,_=self._paths(root)
        if [(r,s) for r,_,s in files] != [(r,s) for r,_,s in after]:
            raise ConflictError('Working tree moved during scan; retry scan')
        _,after_manifest_hash=self._features(root)
        if after_manifest_hash!=manifest_hash:
            raise ConflictError('Feature manifest moved during scan; retry scan')
        _,after_suggestions_hash=self._suggestions(root)
        if after_suggestions_hash!=suggestions_hash:
            raise ConflictError('Suggestions manifest moved during scan; retry scan')
        nodes={}; edges={}; blobs={}
        def put_edge(e):
            if e['id'] in edges:
                existing=edges[e['id']]['evidence']
                existing.extend(x for x in e['evidence'] if x not in existing)
            else: edges[e['id']]=e
        def module(directory):
            nid='module:'+directory
            if nid in nodes: return nid
            parent=PurePosixPath(directory).parent.as_posix() if directory!='.' else None
            nodes[nid]={'id':nid,'kind':'module','label':directory if directory!='.' else 'Project root','path':directory}
            if parent is not None:
                pid=module(parent)
                nodes[nid]['parent']=pid
                put_edge(edge(pid,nid,'contains'))
            return nid
        module('.')
        for path,entry in sorted(self.cache.items()):
            parent=module(PurePosixPath(path).parent.as_posix())
            ext=PurePosixPath(path).suffix.lower()
            nid='file:'+path
            nodes[nid]={'id':nid,'kind':'document' if ext in ('.md','.txt') else 'file','label':PurePosixPath(path).name,
                        'path':path,'parent':parent,'hash':entry.hash,'bytes':entry.size,'language':LANGUAGE.get(ext,ext.lstrip('.') or 'file'),
                        'lines':entry.text.count('\n')+1 if entry.text is not None else 0,
                        'analysis':'python-ast' if ext=='.py' else 'literal-references' if ext in ('.js','.mjs','.cjs','.jsx','.ts','.tsx','.gd','.tscn','.tres','.html') else 'file-only'}
            put_edge(edge(parent,nid,'contains'))
            if entry.text is not None:
                # Hash raw UTF-8 content; no line-ending conversion occurs.
                blobs[entry.hash]=entry.text
            for symbol in entry.analysis['symbols']:
                sid='symbol:'+path+'#'+symbol['name']
                if sid in nodes: continue
                proof={'path':path,'line':symbol['line'],'hash':entry.hash,'method':symbol['method'],'status':'observed' if symbol['method']=='python-ast' else 'lexical'}
                nodes[sid]={'id':sid,'kind':'symbol','label':symbol['name'],'parent':nid,'path':path,'line':symbol['line'],
                            'endLine':symbol['endLine'],'symbolType':symbol['type'],'evidence':[proof]}
                put_edge(edge(nid,sid,'declares',[proof]))
            warnings.extend(entry.analysis['diagnostics'])
        modules={}
        for p in self.cache:
            if p.endswith('.py'):
                name=p[:-3].replace('/','.')
                if name.endswith('.__init__'): name=name[:-9]
                modules[name]=p
                if name.startswith('src.'): modules[name[4:]]=p
        unresolved=[]
        # Godot res:// is anchored to the nearest project.godot, including
        # nested client projects in a backend/frontend repository.
        godot_roots=sorted({PurePosixPath(p).parent for p in self.cache if PurePosixPath(p).name=='project.godot'}, key=lambda p:len(p.parts), reverse=True)
        def resolve(path,ref):
            spec=ref['spec']; ext=PurePosixPath(path).suffix.lower()
            if ext=='.py':
                package=PurePosixPath(path).parent.as_posix().replace('/','.')
                if package=='.': package=''
                if ref.get('level',0):
                    bits=package.split('.') if package else []
                    if ref['level']>len(bits)+1: return []
                    base='.'.join(bits[:len(bits)-ref['level']+1])
                    name='.'.join(x for x in (base,spec) if x)
                else: name=spec
                found=[]
                if name in modules: found.append(modules[name])
                for member in ref.get('members',[]):
                    key='.'.join(x for x in (name,member) if x)
                    if key in modules: found.append(modules[key])
                if not found and '.' in name:
                    prefix=name
                    while '.' in prefix:
                        prefix=prefix.rsplit('.',1)[0]
                        if prefix in modules: found.append(modules[prefix]); break
                return sorted(set(found))
            if spec.startswith('res://'):
                owner=next((p for p in godot_roots if p==PurePosixPath('.') or p in PurePosixPath(path).parents), None)
                if owner is None: owner=PurePosixPath('.')
                target=(owner/spec[6:]).as_posix()
            elif spec.startswith(('./','../')) or ext=='.html':
                if re.match(r'(?:[a-z]+:|//)',spec,re.I): return []
                target=os.path.normpath(str(PurePosixPath(path).parent/spec.split('?')[0].split('#')[0])).replace('\\','/')
            else: return []
            if not safe_relative(target): return []
            candidates=[target]+[target+ext for ext in ('.js','.ts','.tsx','.jsx','.mjs','.py','.gd')]+[target+'/index'+ext for ext in ('.js','.ts','.tsx','.jsx')]
            # Common TS authoring convention: import './foo.js' resolves to foo.ts.
            if target.endswith('.js'): candidates.extend([target[:-3]+'.ts',target[:-3]+'.tsx'])
            return [next((c for c in candidates if c in self.cache),None)] if any(c in self.cache for c in candidates) else []
        for path,entry in sorted(self.cache.items()):
            for ref in entry.analysis['imports']:
                targets=resolve(path,ref)
                if not targets:
                    unresolved.append({'path':path,'line':ref['line'],'reference':ref['spec'],'reason':'External, unresolved, aliased, or outside scan coverage'})
                for target in targets:
                    proof={'path':path,'line':ref['line'],'hash':entry.hash,'method':ref['method'],'status':ref['status'],'reference':ref['spec']}
                    put_edge(edge('file:'+path,'file:'+target,'imports' if PurePosixPath(path).suffix in ('.py','.js','.mjs','.ts','.jsx','.tsx','.cjs') else 'references',[proof]))
        seen_features=set()
        for feature in manifest['features']:
            if not isinstance(feature,dict): raise ContractError('Each feature must be an object')
            fid=feature.get('id')
            if not isinstance(fid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',fid) or fid in seen_features:
                raise ContractError('Feature IDs must be unique simple identifiers')
            seen_features.add(fid)
            paths=feature.get('files',[])
            if not isinstance(paths,list) or not paths or any(not safe_relative(p) for p in paths):
                raise ContractError('Feature files must be nonempty safe relative paths')
            hashes=feature.get('reviewedHashes',{})
            if not isinstance(hashes,dict): raise ContractError('reviewedHashes must be an object')
            evidence=[]; stale=False; unverified=False
            for path in paths:
                current=self.cache.get(path)
                reviewed=hashes.get(path)
                status='stale' if current is None or (reviewed and reviewed!=current.hash) else 'interpretation' if reviewed else 'unverified'
                stale |= status=='stale'; unverified |= status=='unverified'
                proof={'path':path,'method':feature.get('author','human')+'-feature-mapping','status':status}
                if reviewed: proof['hash']=reviewed
                evidence.append(proof)
                if current:
                    put_edge(edge('feature:'+fid,'file:'+path,'implements',[proof]))
            nodes['feature:'+fid]={'id':'feature:'+fid,'kind':'feature','label':feature.get('name',fid),
                'summary':feature.get('description',''),'evidence':evidence,'status':'stale' if stale else 'unverified' if unverified else 'interpretation',
                'author':feature.get('author','human'),'files':paths,'note':'A source-linked interpretation, not proof of runtime behavior.'}
        seen_suggestions=set()
        for s in suggestions.get('suggestions',[]):
            if not isinstance(s,dict): raise ContractError('Each suggestion must be an object')
            sid=s.get('id')
            if not isinstance(sid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',sid) or sid in seen_suggestions:
                raise ContractError('Suggestion IDs must be unique simple identifiers')
            seen_suggestions.add(sid)
            target=s.get('target','module:.')
            if target not in nodes:
                if 'file:'+target in nodes: target='file:'+target
                elif 'module:'+target in nodes: target='module:'+target
            if target not in nodes:
                target='module:.' if 'module:.' in nodes else next((nid for nid in nodes if nodes[nid]['kind']=='module'),None)
            snid='suggestion:'+sid
            nodes[snid]={'id':snid,'kind':'suggestion','label':s.get('name',sid),
                         'summary':s.get('description',''),'rationale':s.get('rationale',''),
                         'target':target or 'module:.','prompt':s.get('prompt',''),
                         'author':s.get('author','ai-pipeline'),'status':s.get('status','proposed'),
                         'note':'Proposed AI pipeline feature. Click for implementation prompt.'}
            if target and target in nodes:
                put_edge(edge(snid,target,'suggests'))
        git_dir = root / '.git'
        git_mtime = 0
        if git_dir.is_dir():
            for gf in ('HEAD', 'index'):
                gp = git_dir / gf
                if gp.is_file():
                    try: git_mtime = max(git_mtime, gp.stat().st_mtime_ns)
                    except OSError: pass
        if reads == 0 and self._git_cache.get('valid') and self._git_cache.get('mtime') == git_mtime:
            commit = self._git_cache.get('commit')
            branch = self._git_cache.get('branch')
            status = self._git_cache.get('status')
        else:
            commit = self._git(root, 'rev-parse', 'HEAD')
            branch = self._git(root, 'symbolic-ref', '--short', 'HEAD')
            status = self._git(root, 'status', '--porcelain', '--untracked-files=normal', '--', '.')
            self._git_cache = {'mtime': git_mtime, 'commit': commit, 'branch': branch, 'status': status, 'valid': True}
        stats={'files':len(self.cache),'filesRead':reads,'cacheHits':len(self.cache)-reads,'durationMs':round((time.perf_counter()-started)*1000,2)}
        self.last_stats=stats
        graph={'schemaVersion':'1.0','project':{'id':project['id'],'name':project['name']},
               'source':{'treeHash':digest({'files':{p:c.hash for p,c in sorted(self.cache.items())},'features':manifest_hash,'suggestions':suggestions_hash}),
                   'commit':commit.decode().strip() if commit else None,'branch':branch.decode().strip() if branch else None,
                   'dirty':bool(status) if status is not None else None,'capturedAt':now(),'scanStats':stats,'publisher':'threadline-scanner',
                   'coverage':'Python AST imports; lexical JS/TS and Godot literal references; other files inventoried. No runtime or whole-program call graph.'},
               'nodes':list(nodes.values()),'edges':list(edges.values()),'diagnostics':warnings,'unresolved':unresolved[:1000]}
        return graph,blobs

    def scan(self, summary: str = 'Working tree observed', actor: str = 'watcher', force: bool = False) -> dict:
        with self.lock:
            if force: self.cache.clear()
            project=self.store.project(self.project_id)
            if project['mode']!='filesystem': raise ContractError('This is an external-publisher project; use publish/patch, not scan')
            for attempt in range(3):
                expected=self.store.head(self.project_id)
                try:
                    graph,blobs=self.build(project)
                    result=self.store.publish(graph,expected=expected,event_id=str(uuid.uuid4()),summary=summary,actor=actor,kind='scan',blobs=blobs)
                    result['scanStats']=self.last_stats
                    return result
                except ConflictError:
                    if attempt==2: raise
                    time.sleep(0.05)
            raise RuntimeError('scan retry exhausted')

class Tracker:
    def __init__(self, store: Store, interval: float = 5.0):
        self.store=store
        self.interval=max(0.25,interval)
        self.scanners: dict[str,Scanner]={}
        self.status: dict[str,dict]={}
        self.stop_event=threading.Event()
        self.thread=None
        self.lock=threading.Lock()

    def scan(self, project_id: str, **kwargs) -> dict:
        with self.lock:
            scanner=self.scanners.setdefault(project_id,Scanner(self.store,project_id))
        try:
            result=scanner.scan(**kwargs)
            self.status[project_id]={'ok':True,'checkedAt':now(),'stats':scanner.last_stats}
            return result
        except Exception as exc:
            self.status[project_id]={'ok':False,'checkedAt':now(),'error':str(exc)}
            raise

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear()
        def loop():
            while not self.stop_event.is_set():
                for project in self.store.projects():
                    if project['mode']=='filesystem':
                        try: self.scan(project['id'])
                        except Exception: pass # status carries the error; the UI must not claim current coverage.
                self.stop_event.wait(self.interval)
        self.thread=threading.Thread(target=loop,name='threadline-watcher',daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=10)

def write_feature(root: Path, ident: str, name: str, paths: list[str], description: str, author: str='agent') -> Path:
    root=root.resolve()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',ident): raise ContractError('Invalid feature ID')
    hashes={}
    for p in paths:
        if not safe_relative(p): raise ContractError('Unsafe feature path')
        file=root/p
        if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(root):
            raise ContractError(f'Feature source unavailable or unsafe: {p}')
        hashes[p]=sha(file.read_bytes())
    directory=root/'.threadline'
    if directory.is_symlink(): raise ContractError('Manifest directory is a symlink')
    directory.mkdir(exist_ok=True)
    path=directory/'features.json'
    if path.is_symlink(): raise ContractError('Manifest is a symlink')
    manifest=json.loads(path.read_text()) if path.exists() else {'version':'1.0','features':[]}
    item={'id':ident,'name':name,'description':description,'files':paths,'reviewedHashes':hashes,'author':author}
    manifest['features']=[f for f in manifest['features'] if f['id']!=ident]+[item]
    temporary=directory/('features-'+str(uuid.uuid4())+'.tmp')
    temporary.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(temporary,path)
    return path

def write_suggestion(root: Path, ident: str, name: str, target: str, description: str, rationale: str = '', prompt: str = '', author: str = 'ai-agent') -> Path:
    root = root.resolve()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', ident): raise ContractError('Invalid suggestion ID')
    directory = root / '.threadline'
    if directory.is_symlink(): raise ContractError('Manifest directory is a symlink')
    directory.mkdir(exist_ok=True)
    path = directory / 'suggestions.json'
    if path.is_symlink(): raise ContractError('Manifest is a symlink')
    manifest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'version':'1.0','suggestions':[]}
    item = {
        'id': ident,
        'name': name,
        'target': target,
        'description': description,
        'rationale': rationale,
        'prompt': prompt,
        'author': author,
        'status': 'proposed',
        'createdAt': now()
    }
    manifest['suggestions'] = [s for s in manifest.get('suggestions', []) if s.get('id') != ident] + [item]
    temporary = directory / ('suggestions-' + str(uuid.uuid4()) + '.tmp')
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)
    return path
