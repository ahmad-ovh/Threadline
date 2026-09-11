#!/usr/bin/env python3
"""Invoke the fixed viewer; discover its authorized connection without UI generation."""
from pathlib import Path
import json,os,sys

def main():
    if sys.version_info<(3,10):
        print('Python 3.10+ is required.',file=sys.stderr);return 2
    profile_path=Path(os.environ.get('THREADLINE_INSTALL_ROOT',str(Path.home()/'.threadline-tools'))).expanduser()/'connection.json'
    profile={}
    try:
        if profile_path.is_file():profile=json.loads(profile_path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        print('Invalid local connection profile. Reconnect using threadline_connect.py.',file=sys.stderr);return 2
    root=os.environ.get('THREADLINE_ROOT') or profile.get('runtime_root')
    if not root:
        candidate=Path(__file__).resolve().parents[2]
        if (candidate/'src/threadline/cli.py').is_file():
            root=candidate
    if root:
        root=Path(root).expanduser().resolve()
        if not (root/'src/threadline/cli.py').is_file():
            print('THREADLINE_ROOT or the saved runtime root is invalid. Run connect; do not regenerate a frontend.',file=sys.stderr);return 2
        # Includes daily verification of the fixed installed renderer/core.
        from threadline_connect import core_manifest,SetupError
        try:core_manifest(root)
        except SetupError as exc:print(str(exc),file=sys.stderr);return 2
        sys.path.insert(0,str(root/'src'))
    try:from threadline.cli import main as run
    except ImportError:
        print('Connect once using threadline_connect.py, install the supplied wheel, or set THREADLINE_ROOT to the trusted application root.',file=sys.stderr);return 2
    args=sys.argv[1:]
    if not any(x=='--home' or x.startswith('--home=') for x in args) and not os.environ.get('THREADLINE_HOME') and profile.get('home'):
        args=['--home',profile['home'],*args]
    return run(args)
if __name__=='__main__':raise SystemExit(main())
