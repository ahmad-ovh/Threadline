#!/usr/bin/env python3
"""Convenience entry point; identical behavior to the installable Skill helper."""
from pathlib import Path
import runpy,sys
folder=Path(__file__).resolve().parents[1]/'skills/threadline/scripts'
sys.path.insert(0,str(folder))
runpy.run_path(str(folder/'threadline_connect.py'),run_name='__main__')
