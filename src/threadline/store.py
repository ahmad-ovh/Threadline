"""Durable snapshots + atomic graph deltas, separate from graph presentation."""
from __future__ import annotations
from contextlib import contextmanager
import copy
import json
from pathlib import Path
import sqlite3
import uuid
import zlib
from .model import (ContractError, ConflictError, MissingError, canonical, digest, now,
                    validate_graph, graph_diff, graph_fingerprint, apply_patch, require_string, sha)

class Store:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "threadline.sqlite3"
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, root TEXT, mode TEXT NOT NULL,
                    demo INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
                    event_id TEXT NOT NULL, parent INTEGER NOT NULL, created TEXT NOT NULL,
                    summary TEXT NOT NULL, actor TEXT NOT NULL, kind TEXT NOT NULL,
                    request_hash TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    snapshot BLOB NOT NULL, delta BLOB NOT NULL,
                    UNIQUE(project_id, revision), UNIQUE(project_id, event_id));
                CREATE TABLE IF NOT EXISTS receipts (project_id TEXT NOT NULL REFERENCES projects(id), event_id TEXT NOT NULL, request_hash TEXT NOT NULL, revision INTEGER NOT NULL, PRIMARY KEY(project_id,event_id));
                CREATE TABLE IF NOT EXISTS checkpoints (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                    project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
                    start_revision INTEGER NOT NULL, name TEXT NOT NULL, note TEXT NOT NULL,
                    created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS blobs (hash TEXT PRIMARY KEY, body BLOB NOT NULL);
                CREATE INDEX IF NOT EXISTS revision_project ON revisions(project_id, revision DESC);
            """)
            version = db.execute("SELECT value FROM settings WHERE key='database_version'").fetchone()
            if version is not None and version[0] != '1':
                raise ContractError("Unsupported database version. Back up the store before migration.")
            db.execute("INSERT OR IGNORE INTO settings VALUES('database_version','1')")
        try:
            self.path.chmod(0o600)
            self.directory.chmod(0o700)
        except OSError:
            pass

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        try:
            yield db
        finally:
            db.close()

    def register(self, project_id: str, name: str, root: str | None = None,
                 mode: str = "filesystem", demo: bool = False) -> dict:
        validate_graph({"schemaVersion":"1.0", "project":{"id":project_id,"name":name},
                        "source":{"treeHash":"unscanned"},"nodes":[],"edges":[]})
        if mode not in ("filesystem", "published"):
            raise ContractError("mode must be filesystem or published")
        if root is not None:
            path = Path(root).expanduser().resolve()
            if not path.is_dir():
                raise ContractError(f"Project directory does not exist: {path}")
            root = str(path)
        if mode == "filesystem" and not root:
            raise ContractError("filesystem project needs a root")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if existing:
                db.rollback()
                if existing['root'] != root or existing['mode'] != mode:
                    raise ConflictError("Project ID already belongs to another root or mode. Choose a new ID.")
                return dict(existing)
            db.execute("INSERT INTO projects VALUES(?,?,?,?,?,?)", (project_id,name,root,mode,int(demo),now()))
            db.commit()
        return self.project(project_id)

    def project(self, project_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not row:
                raise MissingError(project_id)
            return dict(row)

    def projects(self) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("""SELECT p.*, COALESCE((SELECT MAX(revision) FROM revisions r WHERE r.project_id=p.id),0) AS revision,
               (SELECT MAX(created) FROM revisions r WHERE r.project_id=p.id) AS updated
               FROM projects p ORDER BY created, id""").fetchall()
            return [dict(row) for row in rows]

    def head(self, project_id: str) -> int:
        with self.connection() as db:
            return db.execute("SELECT COALESCE(MAX(revision),0) FROM revisions WHERE project_id=?", (project_id,)).fetchone()[0]

    @staticmethod
    def _pack(obj: dict) -> bytes:
        return zlib.compress(canonical(obj).encode('utf-8'), 6)

    @staticmethod
    def _unpack(raw: bytes) -> dict:
        return json.loads(zlib.decompress(raw))

    def snapshot(self, project_id: str, revision: int | None = None) -> dict:
        self.project(project_id)
        with self.connection() as db:
            if revision is None:
                row = db.execute("SELECT snapshot,revision,created FROM revisions WHERE project_id=? ORDER BY revision DESC LIMIT 1", (project_id,)).fetchone()
            else:
                row = db.execute("SELECT snapshot,revision,created FROM revisions WHERE project_id=? AND revision=?", (project_id,revision)).fetchone()
            if not row:
                raise MissingError(f"No snapshot for {project_id} at {revision or 'HEAD'}")
            graph = self._unpack(row['snapshot'])
            graph['revision'] = row['revision']
            graph['recordedAt'] = row['created']
            return graph

    def publish(self, graph: dict | None, *, project_id: str | None = None, patch: dict | None = None,
                expected: int, event_id: str, summary: str, actor: str = "agent", kind: str = "publish",
                blobs: dict[str, str] | None = None) -> dict:
        if type(expected) is not int or expected < 0:
            raise ContractError("expectedRevision must be a nonnegative integer")
        require_string(event_id, "eventId", 200)
        require_string(summary, "summary", 2000)
        require_string(actor, "actor", 200)
        require_string(kind, "kind", 100)
        if graph is not None:
            graph = validate_graph(graph)
            graph.pop('revision',None); graph.pop('recordedAt',None)
            if project_id and project_id != graph['project']['id']:
                raise ContractError("Route project does not match snapshot project")
            project_id = graph['project']['id']
        if not project_id or ((graph is None) == (patch is None)):
            raise ContractError("Publish exactly one snapshot or patch, for a project")
        self.project(project_id)
        request_hash = digest({"graph":graph,"patch":patch,"expected":expected,"summary":summary,"actor":actor,"kind":kind})
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                # Idempotency is checked BEFORE the optimistic lock: a successful retry may have an old parent.
                seen = db.execute("SELECT revision,request_hash FROM receipts WHERE project_id=? AND event_id=?", (project_id,event_id)).fetchone()
                if seen:
                    if seen['request_hash'] != request_hash:
                        raise ConflictError("eventId reused with different content")
                    db.commit()
                    return {"revision":seen['revision'],"duplicate":True,"changed":False}
                last = db.execute("SELECT revision,snapshot,fingerprint FROM revisions WHERE project_id=? ORDER BY revision DESC LIMIT 1", (project_id,)).fetchone()
                head = last['revision'] if last else 0
                if expected != head:
                    raise ConflictError(f"Revision conflict: expected {expected}, current {head}. Refresh and retry.")
                old = self._unpack(last['snapshot']) if last else None
                if patch is not None:
                    if old is None:
                        raise ContractError("A patch requires an initial snapshot")
                    graph = apply_patch(old, patch)
                fingerprint = graph_fingerprint(graph)
                if last and fingerprint == last['fingerprint']:
                    if kind != 'scan':
                        db.execute('INSERT INTO receipts VALUES(?,?,?,?)',(project_id,event_id,request_hash,head))
                    db.commit()
                    return {"revision":head,"duplicate":False,"changed":False}
                revision = head + 1
                db.execute('INSERT INTO receipts VALUES(?,?,?,?)',(project_id,event_id,request_hash,revision))
                delta = graph_diff(old, graph)
                stamp = now()
                db.execute("""INSERT INTO revisions(project_id,revision,event_id,parent,created,summary,actor,kind,request_hash,fingerprint,snapshot,delta)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (project_id,revision,event_id,head,stamp,summary,actor,kind,request_hash,fingerprint,self._pack(graph),self._pack(delta)))
                for hash_value, text in (blobs or {}).items():
                    if sha(text.encode('utf-8')) != hash_value:
                        raise ContractError("Blob hash mismatch")
                    db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?)", (hash_value,zlib.compress(text.encode('utf-8'))))
                db.commit()
                return {"revision":revision,"duplicate":False,"changed":True,"delta":delta,"created":stamp}
            except BaseException:
                db.rollback()
                raise

    def history(self, project_id: str, limit: int = 200, before: int | None = None) -> list[dict]:
        self.project(project_id)
        limit = max(1,min(int(limit),1000))
        with self.connection() as db:
            rows = db.execute("""SELECT revision,event_id,parent,created,summary,actor,kind,delta
               FROM revisions WHERE project_id=? AND revision<? ORDER BY revision DESC LIMIT ?""",
               (project_id,before or 2**62,limit)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                delta = self._unpack(item.pop('delta'))
                item['counts'] = {group:{change:len(items) for change,items in changes.items()} for group,changes in delta.items()}
                result.append(item)
            return result

    def delta(self, project_id: str, revision: int) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT delta FROM revisions WHERE project_id=? AND revision=?", (project_id,revision)).fetchone()
            if not row:
                raise MissingError("revision")
            return self._unpack(row[0])

    def compare(self, project_id: str, before: int, after: int) -> dict:
        old = self.snapshot(project_id,before) if before else None
        new = self.snapshot(project_id,after)
        return graph_diff(old,new)

    def checkpoint(self, project_id: str, name: str, note: str = "", revision: int | None = None) -> dict:
        require_string(name,"checkpoint name",200)
        require_string(note,"checkpoint note",4000,True)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            head = db.execute("SELECT COALESCE(MAX(revision),0) FROM revisions WHERE project_id=?",(project_id,)).fetchone()[0]
            revision = head if revision is None else revision
            if type(revision) is not int or not 1 <= revision <= head:
                db.rollback(); raise ContractError("Checkpoint requires an existing revision")
            last = db.execute("SELECT COALESCE(MAX(revision),0) FROM checkpoints WHERE project_id=? AND revision<?",(project_id,revision)).fetchone()[0]
            item = {"id":str(uuid.uuid4()),"project_id":project_id,"revision":revision,"start_revision":last+1,"name":name,"note":note,"created":now()}
            db.execute("INSERT INTO checkpoints(id,project_id,revision,start_revision,name,note,created) VALUES(?,?,?,?,?,?,?)", tuple(item.values()))
            db.commit()
            return item

    def checkpoints(self, project_id: str) -> list[dict]:
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM checkpoints WHERE project_id=? ORDER BY revision DESC,seq DESC",(project_id,))]

    def source(self, project_id: str, path: str, revision: int | None = None) -> dict:
        graph = self.snapshot(project_id,revision)
        file = next((n for n in graph['nodes'] if n.get('path')==path and n['kind'] in ('file','document')),None)
        if not file or not file.get('hash'):
            raise MissingError("Source path is not present in the indexed snapshot")
        with self.connection() as db:
            row = db.execute("SELECT body FROM blobs WHERE hash=?",(file['hash'],)).fetchone()
        if not row:
            return {"path":path,"hash":file['hash'],"revision":graph['revision'],"available":False,"reason":"This publisher did not retain source text; consult the matching source revision."}
        return {"path":path,"hash":file['hash'],"revision":graph['revision'],"available":True,"text":zlib.decompress(row[0]).decode('utf-8')}

    def query(self, project_id: str, text: str = "", node_id: str | None = None,
              depth: int = 1, limit: int = 30, revision: int | None = None) -> dict:
        graph = self.snapshot(project_id,revision)
        limit = max(1,min(int(limit),200)); depth = max(0,min(int(depth),3))
        nodes = {n['id']:n for n in graph['nodes']}
        if node_id:
            if node_id not in nodes:
                raise MissingError(node_id)
            selected = {node_id}
        else:
            q = text.casefold()
            ranked = [n for n in graph['nodes'] if not q or q in (n['label']+' '+n.get('path','')+' '+n.get('summary','')).casefold()]
            ranked.sort(key=lambda n:(n['kind']!='feature',n['label'].casefold()!=q,n['id']))
            selected = {n['id'] for n in ranked[:limit]}
        adjacency = {}
        for e in graph['edges']:
            if e['kind'] in ('contains','declares'):
                continue
            adjacency.setdefault(e['source'],set()).add(e['target'])
            adjacency.setdefault(e['target'],set()).add(e['source'])
        truncated = False
        for _ in range(depth if node_id else 0):
            neighbors = set().union(*(adjacency.get(n,set()) for n in selected)) if selected else set()
            available = sorted(neighbors-selected)
            if len(selected)+len(available)>limit:
                truncated=True
            selected.update(available[:max(0,limit-len(selected))])
        if not node_id:
            truncated = len(ranked)>limit
        return {"schemaVersion":"1.0","project":graph['project'],"revision":graph['revision'],"source":graph['source'],
                "nodes":[nodes[n] for n in sorted(selected)],
                "edges":[e for e in graph['edges'] if e['source'] in selected and e['target'] in selected],
                "truncated":truncated,"warning":"Use source evidence at this revision before editing. Interpretations are not runtime proofs."}

    def export(self, project_id: str, history: bool = True) -> dict:
        graph = self.snapshot(project_id)
        result = {"format":"threadline-bundle","version":"1.0","snapshot":graph,"checkpoints":self.checkpoints(project_id),"history":[]}
        if history:
            events = self.history(project_id,1000)
            result['history'] = events
            result['snapshots'] = {str(e['revision']):self.snapshot(project_id,e['revision']) for e in events}
            result['deltas'] = {str(e['revision']):self.delta(project_id,e['revision']) for e in events}
            result['historyTruncated'] = len(events) < graph['revision']
        return result
