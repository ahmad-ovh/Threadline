#!/usr/bin/env python3
"""Publish the documented synthetic example over the real local HTTP interface.

Start Threadline first. This client never creates a server or changes source code.
It sends data ONLY to a loopback HTTP URL and never prints the private token.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:7331")
    parser.add_argument("--home", default=os.environ.get("THREADLINE_HOME", str(Path.home()/".threadline")))
    parser.add_argument("--patch", action="store_true", help="Also publish the example atomic patch")
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username
            or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        parser.error("Use the actual Threadline loopback URL: http://127.0.0.1:PORT")
    base = args.url.rstrip("/")
    home = Path(args.home).expanduser()
    examples = Path(__file__).resolve().parent.parent / "examples"
    try:
        token = (home/"session.token").read_text(encoding="utf-8").strip()
        def request(path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(base+path, data=data, headers={"Authorization":"Bearer "+token, "Content-Type":"application/json"})
            # Do not inherit proxy settings for local project data.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=15) as response:
                return json.load(response)
        projects = request("/api/projects")["projects"]
        project = next((p for p in projects if p["id"] == "publisher-example"), None)
        if project is None:
            request("/api/projects", {"id":"publisher-example", "name":"External publisher example", "mode":"published"})
            revision = 0
        else:
            if project["mode"] != "published":
                raise ValueError("The example ID belongs to a filesystem project; no changes were sent")
            revision = project["revision"]
        snapshot = json.loads((examples/"publisher-snapshot.json").read_text())
        result = request("/api/projects/publisher-example/publish", {"snapshot":snapshot,"expectedRevision":revision,"eventId":str(uuid.uuid4()),"summary":"Published synthetic contract example","actor":"example HTTP publisher"})
        results = [result]
        if args.patch:
            patch = json.loads((examples/"publisher-patch.json").read_text())
            results.append(request("/api/projects/publisher-example/patch", {"patch":patch,"expectedRevision":result["revision"],"eventId":str(uuid.uuid4()),"summary":"Applied synthetic atomic patch","actor":"example HTTP publisher"}))
        print(json.dumps({"project":"publisher-example","results":results}, indent=2))
        return 0
    except urllib.error.HTTPError as exc:
        print("HTTP %s: %s" % (exc.code, exc.read().decode(errors="replace")), file=sys.stderr)
    except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
        print("Publication failed: "+str(exc), file=sys.stderr)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
