"""Versioned graph contract and semantic checks. No third-party runtime dependency."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = "1.0"
MAX_NODES = 20000
MAX_EDGES = 100000

class ContractError(ValueError):
    pass

class ConflictError(ValueError):
    pass

class MissingError(KeyError):
    pass

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def safe_relative(value: str) -> bool:
    return (isinstance(value, str) and bool(value) and len(value) <= 4096
            and "\\" not in value and not any(ord(c) < 32 for c in value)
            and not PurePosixPath(value).is_absolute()
            and ".." not in PurePosixPath(value).parts
            and not re.match(r"^[A-Za-z]:", value))

def slug(value: str) -> str:
    out = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-")[:64]
    return out or "project"

def require_string(value: Any, field: str, maximum: int = 10000, empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not empty) or len(value) > maximum:
        raise ContractError(f"{field} must be {'a' if empty else 'a nonempty'} string (max {maximum} characters)")
    return value

def validate_graph(graph: Any) -> dict:
    if not isinstance(graph, dict):
        raise ContractError("snapshot must be an object")
    if graph.get("schemaVersion") != SCHEMA_VERSION:
        raise ContractError(f"schemaVersion must be {SCHEMA_VERSION}")
    project = graph.get("project")
    if not isinstance(project, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", str(project.get("id", ""))):
        raise ContractError("project.id must be a lowercase slug, max 64 characters")
    require_string(project.get("name"), "project.name", 160)
    source = graph.get("source")
    if not isinstance(source, dict):
        raise ContractError("source must be an object")
    require_string(source.get("treeHash"), "source.treeHash", 200)
    if source.get("commit") is not None:
        require_string(source["commit"], "source.commit", 128)
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list) or len(nodes) > MAX_NODES:
        raise ContractError(f"nodes must be an array, max {MAX_NODES}")
    if not isinstance(edges, list) or len(edges) > MAX_EDGES:
        raise ContractError(f"edges must be an array, max {MAX_EDGES}")
    ids, edge_ids = set(), set()
    parents = {}
    kinds = {"module", "file", "symbol", "feature", "document", "suggestion"}
    for node in nodes:
        if not isinstance(node, dict):
            raise ContractError("node must be an object")
        nid = require_string(node.get("id"), "node.id", 4096)
        if nid in ids:
            raise ContractError(f"duplicate node: {nid}")
        ids.add(nid)
        if node.get("kind") not in kinds:
            raise ContractError(f"invalid node kind: {node.get('kind')}")
        require_string(node.get("label"), "node.label", 500)
        if "path" in node and not safe_relative(node["path"]):
            raise ContractError(f"unsafe relative path: {node['path']}")
        if node.get("parent"):
            parents[nid] = node["parent"]
        if "hash" in node and not re.fullmatch(r"[a-f0-9]{64}", str(node["hash"])):
            raise ContractError("node.hash must be a SHA-256 hex digest")
        if "line" in node and (type(node["line"]) is not int or node["line"] < 1):
            raise ContractError("node.line must be a positive integer")
        if "summary" in node:
            require_string(node["summary"], "node.summary", 10000, True)
        if "rationale" in node:
            require_string(node["rationale"], "node.rationale", 10000, True)
        if "target" in node:
            require_string(node["target"], "node.target", 4096, True)
        if "prompt" in node:
            require_string(node["prompt"], "node.prompt", 10000, True)
        _evidence(node.get("evidence", []))
    for nid, parent in parents.items():
        if parent not in ids:
            raise ContractError(f"missing parent {parent}")
        seen, cursor = {nid}, parent
        while cursor in parents:
            if cursor in seen:
                raise ContractError("parent cycle")
            seen.add(cursor)
            cursor = parents[cursor]
        if cursor == nid:
            raise ContractError("parent cycle")
    relations = {"contains", "declares", "imports", "references", "implements", "documents", "calls", "depends_on", "suggests"}
    for edge in edges:
        if not isinstance(edge, dict):
            raise ContractError("edge must be an object")
        eid = require_string(edge.get("id"), "edge.id", 4096)
        if eid in edge_ids:
            raise ContractError(f"duplicate edge: {eid}")
        edge_ids.add(eid)
        if edge.get("source") not in ids or edge.get("target") not in ids:
            raise ContractError(f"dangling edge: {eid}")
        if edge.get("kind") not in relations:
            raise ContractError(f"invalid relationship: {edge.get('kind')}")
        _evidence(edge.get("evidence", []))
    # Refuse non-JSON and non-finite values before entering the transaction.
    canonical(graph)
    result = copy.deepcopy(graph)
    result["nodes"].sort(key=lambda x: x["id"])
    result["edges"].sort(key=lambda x: x["id"])
    return result

def _evidence(evidence: Any) -> None:
    if not isinstance(evidence, list) or len(evidence) > 1000:
        raise ContractError("evidence must be an array, max 1000 entries")
    for item in evidence:
        if not isinstance(item, dict):
            raise ContractError("evidence entry must be an object")
        if "path" in item and not safe_relative(item["path"]):
            raise ContractError("unsafe evidence path")
        if "line" in item and (type(item["line"]) is not int or item["line"] < 1):
            raise ContractError("evidence.line must be positive")
        if "hash" in item and not re.fullmatch(r"[a-f0-9]{64}", str(item["hash"])):
            raise ContractError("evidence.hash must be SHA-256")
        if "method" in item:
            require_string(item["method"], "evidence.method", 200)
        if "status" in item and item["status"] not in {"observed", "lexical", "interpretation", "stale", "unverified"}:
            raise ContractError("invalid evidence.status")

def graph_fingerprint(graph: dict) -> str:
    clean = copy.deepcopy(graph)
    for field in ("capturedAt", "scanStats"):
        clean.get("source", {}).pop(field, None)
    clean.pop("revision", None)
    clean.pop("recordedAt", None)
    return digest(clean)

def graph_diff(before: dict | None, after: dict) -> dict:
    result = {}
    for group in ("nodes", "edges"):
        old = {n["id"]: n for n in (before or {}).get(group, [])}
        new = {n["id"]: n for n in after.get(group, [])}
        result[group] = {
            "added": [new[k] for k in sorted(new.keys() - old.keys())],
            "removed": [old[k] for k in sorted(old.keys() - new.keys())],
            "changed": [{"before": old[k], "after": new[k]} for k in sorted(old.keys() & new.keys()) if old[k] != new[k]],
        }
    return result

def apply_patch(graph: dict, patch: dict) -> dict:
    if not isinstance(patch, dict):
        raise ContractError("patch must be an object")
    out = copy.deepcopy(graph)
    for group, key in (("nodes", "Nodes"), ("edges", "Edges")):
        objects = {item["id"]: item for item in out[group]}
        removals, upserts = patch.get("remove" + key, []), patch.get("upsert" + key, [])
        if not isinstance(removals, list) or not isinstance(upserts, list):
            raise ContractError("patch operations must be arrays")
        if len({item.get('id') for item in upserts if isinstance(item, dict)}) != len(upserts):
            raise ContractError("patch upserts must have unique IDs")
        for ident in removals:
            if not isinstance(ident, str):
                raise ContractError("removed IDs must be strings")
            objects.pop(ident, None)
        for item in upserts:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ContractError("upsert must have an id")
            objects[item["id"]] = item
        out[group] = list(objects.values())
    if "source" in patch:
        out["source"] = patch["source"]
    return validate_graph(out)
