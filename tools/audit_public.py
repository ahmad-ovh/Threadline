#!/usr/bin/env python3
"""Check the upload boundary and runtime manifest. Not a universal secret scanner."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN={'session.token','connection.json','managed-host.json','managed-host.log','launch-url.txt','open-viewer.html','stop-request.json','THRESHOLD.bundle','Threadline-THRESHOLD-validation.zip','.env','.env.local','credentials.json','secrets.json'}
FONTS={'.ttf','.otf','.woff','.woff2','.eot','.ttc'}
errors=[];checked=0
for p in ROOT.rglob('*'):
    rel=p.relative_to(ROOT)
    if any(x in {'.git','__pycache__','build','.venv'} or x.endswith('.egg-info') for x in rel.parts):continue
    if p.is_symlink():errors.append(str(rel)+' is a symlink');continue
    if not p.is_file():continue
    checked+=1
    if p.name in FORBIDDEN or p.suffix in FONTS or p.suffix in {'.sqlite3','.sqlite','.db','.pem','.key','.bundle'}:errors.append(str(rel)+' must not be uploaded')
    if any(x in {'05_PRIVATE_VALIDATION','06_THRESHOLD_CHANGES','07_ORIGINALS_AND_REFERENCE'} for x in rel.parts):errors.append(str(rel)+' crosses the private boundary')
    if p.stat().st_size>90*1024*1024:errors.append(str(rel)+' is too large for this reviewed public package')
    if p.suffix in {'.zip','.whl'}:
        with zipfile.ZipFile(p) as z:
            if z.testzip():errors.append(str(rel)+' is corrupt')
            for n in z.namelist():
                if Path(n).name in FORBIDDEN or Path(n).suffix.lower() in FONTS:errors.append(str(rel)+' contains restricted '+n)
manifest=json.loads((ROOT/'runtime-manifest.json').read_text())
for rel,digest in manifest['files'].items():
    p=ROOT/rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:errors.append('Runtime manifest mismatch: '+rel)
print(json.dumps({'ok':not errors,'checked_files':checked,'runtime_version':manifest['version'],'errors':errors,'limitation':'Filename/archive boundaries and integrity only. Inspect inline secrets, ownership and license rights before publication; this is not an exhaustive secret detector.'},indent=2))
raise SystemExit(1 if errors else 0)
