#!/usr/bin/env python3
"""Create/check runtime integrity metadata. No network or credentials involved."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]

def files(root):
    result={}
    for name in ('run.py','pyproject.toml'):
        p=root/name;result[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ('src/threadline','skills/threadline/scripts','schemas'):
        for p in sorted((root/folder).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'):
                result[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();path=ROOT/'runtime-manifest.json'
    if a.write:
        version={};exec((ROOT/'src/threadline/__init__.py').read_text(),version)
        path.write_text(json.dumps({'version':version['__version__'],'scope':'Fixed renderer/core, direct-run entrypoint, package metadata, CLI helpers and graph schemas','files':files(ROOT)},indent=2)+'\n')
    expected=json.loads(path.read_text())['files'];actual=files(ROOT)
    if actual!=expected:raise SystemExit('Runtime integrity differs. Review changes and intentionally regenerate; do not hide unexpected edits.')
    print(json.dumps({'ok':True,'checked':len(expected),'version':json.loads(path.read_text())['version']}))
if __name__=='__main__':main()
