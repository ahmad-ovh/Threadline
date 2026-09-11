#!/usr/bin/env python3
"""Unified release packager for Threadline.

Enforces strict dependency order:
1. Build distribution wheel into dist/ (*.whl)
2. Generate runtime-manifest.json (hashes core source, scripts, schemas)
3. Package Skill ZIP (dist/threadline.zip)
4. Optional handoff sync (if ../02_INSTALLABLE_SKILL exists)
5. Regenerate top-level MANIFEST.sha256 (hashes all release assets and artifacts)
6. Run tools/audit_public.py and scripts/verify_release.py in an isolated sandbox
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]

EXCLUDE_DIRS = {'.git', '__pycache__', 'build', '.venv'}
EXCLUDE_FILES = {'MANIFEST.sha256'}

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def clean_pycache(directory: Path):
    for p in list(directory.rglob('__pycache__')):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)

def build_wheel():
    print("[1/5] Building distribution wheel...", flush=True)
    dist_dir = ROOT / 'dist'
    dist_dir.mkdir(exist_ok=True)
    for old_whl in dist_dir.glob('*.whl'):
        old_whl.unlink(missing_ok=True)
    
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    cmd = [sys.executable, '-m', 'pip', 'wheel', '--no-deps', '-w', 'dist', '.']
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, creationflags=creationflags)
    if p.returncode != 0:
        print("Wheel build failed:\n" + p.stderr, file=sys.stderr)
        sys.exit(p.returncode)
    wheels = list(dist_dir.glob('*.whl'))
    if not wheels:
        print("No wheel produced in dist/", file=sys.stderr)
        sys.exit(1)
    print(f"  PASS Built wheel: {wheels[0].name}")

def update_runtime_manifest():
    print("[2/5] Generating runtime-manifest.json...", flush=True)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    cmd = [sys.executable, str(ROOT / 'tools' / 'runtime_manifest.py'), '--write']
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, creationflags=creationflags)
    if p.returncode != 0:
        print("Runtime manifest generation failed:\n" + p.stderr, file=sys.stderr)
        sys.exit(p.returncode)
    print("  PASS Updated runtime-manifest.json")

def build_skill_zip():
    print("[3/5] Packaging Skill ZIP...", flush=True)
    clean_pycache(ROOT / 'skills' / 'threadline')
    skill_dir = ROOT / 'skills' / 'threadline'
    zip_path = ROOT / 'dist' / 'threadline.zip'
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(skill_dir.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc') and not p.name.endswith('.pyo'):
                arcname = 'threadline/' + p.relative_to(skill_dir).as_posix()
                zf.write(p, arcname)
    
    print(f"  PASS Created {zip_path.relative_to(ROOT).as_posix()} ({len(zipfile.ZipFile(zip_path).namelist())} files)")

    handoff_skill = ROOT.parent / '02_INSTALLABLE_SKILL'
    if handoff_skill.is_dir():
        dest_zip = handoff_skill / 'threadline.zip'
        shutil.copy2(zip_path, dest_zip)
        scripts_dest = handoff_skill / 'threadline' / 'scripts'
        scripts_src = skill_dir / 'scripts'
        if scripts_dest.is_dir() and scripts_src.is_dir():
            for script in scripts_src.glob('*.py'):
                shutil.copy2(script, scripts_dest / script.name)
        print(f"  PASS Synced to {dest_zip.as_posix()}")

def update_manifest_sha256():
    print("[4/5] Regenerating top-level MANIFEST.sha256...", flush=True)
    entries = []
    for p in sorted(ROOT.rglob('*')):
        rel = p.relative_to(ROOT).as_posix()
        parts = rel.split('/')
        if any(x in EXCLUDE_DIRS or x.endswith('.egg-info') for x in parts):
            continue
        if rel in EXCLUDE_FILES or not p.is_file():
            continue
        digest = sha256_file(p)
        entries.append(f"{digest}  {rel}")
    
    manifest_path = ROOT / 'MANIFEST.sha256'
    manifest_path.write_text('\n'.join(entries) + '\n', encoding='utf-8')
    print(f"  PASS Recorded {len(entries)} verified entries in MANIFEST.sha256")

def verify_release():
    print("[5/5] Verifying complete release end-to-end...", flush=True)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    
    p_audit = subprocess.run([sys.executable, str(ROOT / 'tools' / 'audit_public.py')], cwd=ROOT, capture_output=True, text=True, creationflags=creationflags)
    if p_audit.returncode != 0:
        print("Audit public failed:\n" + p_audit.stdout + "\n" + p_audit.stderr, file=sys.stderr)
        sys.exit(p_audit.returncode)
    print("  PASS Public integrity and boundary audit")

    p_verify = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'verify_release.py')], cwd=ROOT, capture_output=True, text=True, creationflags=creationflags)
    if p_verify.returncode != 0:
        print("verify_release.py failed:\n" + p_verify.stdout + "\n" + p_verify.stderr, file=sys.stderr)
        sys.exit(p_verify.returncode)
    print(p_verify.stdout.strip())
    print("\nRelease package built, hashed, and verified successfully.")

def main():
    build_wheel()
    update_runtime_manifest()
    build_skill_zip()
    update_manifest_sha256()
    verify_release()

if __name__ == '__main__':
    main()
