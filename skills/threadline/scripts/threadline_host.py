#!/usr/bin/env python3
"""Private lifecycle wrapper around the unchanged Threadline server/scanner.

A scoped stop request is consumed by this actual process; the client never
kills a potentially reused PID. This is local hosting, not public deployment.
"""
from pathlib import Path
import argparse,json,os,sys,threading,time
from threadline_connect import private_write,core_manifest,stamp,read_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--home',type=Path,required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--interval',type=float,required=True);p.add_argument('--run-id',required=True);a=p.parse_args()
    root=a.runtime.resolve();home=a.home.resolve();core_manifest(root)
    sys.path.insert(0,str(root/'src'))
    from threadline.store import Store
    from threadline.scanner import Tracker
    from threadline.server import LocalServer
    from threadline import __version__
    store=Store(home);tracker=Tracker(store,a.interval);server=LocalServer(store,tracker,a.port)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.2},daemon=True)
    record={'run_id':a.run_id,'pid':os.getpid(),'runtime_root':str(root),'home':str(home),'url':server.url,'version':__version__,'started_at':stamp()}
    private_write(home/'managed-host.json',record)
    tracker.start();thread.start()
    print(json.dumps({'event':'viewer-ready','version':__version__,'url':server.url,'watching':True}),flush=True)
    try:
        while thread.is_alive():
            request=read_json(home/'stop-request.json',{})
            if request.get('run_id')==a.run_id:break
            time.sleep(.3)
    except KeyboardInterrupt:pass
    finally:
        server.shutdown();tracker.stop();server.server_close();thread.join(timeout=3)
        if read_json(home/'managed-host.json',{}).get('run_id')==a.run_id:(home/'managed-host.json').unlink(missing_ok=True)
        if read_json(home/'stop-request.json',{}).get('run_id')==a.run_id:(home/'stop-request.json').unlink(missing_ok=True)
        print(json.dumps({'event':'viewer-stopped','history_deleted':False}),flush=True)
if __name__=='__main__':main()
