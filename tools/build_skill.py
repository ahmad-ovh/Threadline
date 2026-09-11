#!/usr/bin/env python3
"""Build a configure-once Skill ZIP without changing committed source files."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--repo');p.add_argument('--ref',default='main');p.add_argument('--expected-commit');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.repo:
 u=urlsplit(a.repo)
 if u.scheme!='https' or not u.netloc or u.username or u.password or u.query or u.fragment:p.error('Use a credential-free HTTPS repository URL.')
if a.expected_commit and not re.fullmatch('[0-9a-fA-F]{40}|[0-9a-fA-F]{64}',a.expected_commit):p.error('Use a full Git commit SHA.')
config={'repository_url':a.repo,'ref':a.ref,'expected_commit':a.expected_commit,'instructions':'Clone only the user-approved repository/ref. Use local-source for offline setup. No native WorkBuddy certification is implied.'}
skill=ROOT/'skills/threadline';a.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED) as z:
 for f in sorted(skill.rglob('*')):
  if not f.is_file() or '__pycache__' in f.parts or f.suffix=='.pyc':continue
  rel=f.relative_to(skill)
  data=(json.dumps(config,indent=2)+'\n').encode() if rel.as_posix()=='references/installation.json' else f.read_bytes()
  z.writestr('threadline/'+rel.as_posix(),data)
print(json.dumps({'created':str(a.output),'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'repository_url':a.repo,'ref':a.ref,'expected_commit':a.expected_commit,'native_import_tested':False},indent=2))
