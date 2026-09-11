#!/usr/bin/env python3
"""Browser acceptance checks. Optional test dependency: Playwright + Chromium.

Normally runs through native localhost navigation. --bridge supports managed CI
browsers that block all URL navigation: the unchanged app still talks to the real
HTTP/SSE server through Playwright bindings. The report explicitly names this
transport limitation; native HTTP/SSE is independently tested in unittest.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import traceback
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from threadline.store import Store
from threadline.scanner import Tracker
from threadline.server import LocalServer,WEB
from threadline.demos import setup_demos
from threadline.exporter import render_export
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def inline_app(html):
    html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+(WEB/'style.css').read_text()+'</style>')
    for name in ('cytoscape.min.js','graph.js','map-view.js','app.js'):
        html=html.replace('<script src="'+name+'" defer></script>', '<script>'+(WEB/name).read_text().replace('</script','<\\/script')+'</script>')
    return html

def inline_game(root):
    """Only used with a network-blocked browser. Raw ES modules have separate Node tests."""
    done=set();pieces=[]
    def add(file):
        file=file.resolve()
        if file in done:return
        done.add(file)
        text=file.read_text()
        for m in re.finditer(r"^import .*?from ['\"](.+?)['\"];?",text,re.M):add(file.parent/m[1])
        text=re.sub(r'^import .*?;\s*$', '',text,flags=re.M)
        text=re.sub(r'^export ', '',text,flags=re.M)
        pieces.append(text)
    add(root/'src/ui/main.js')
    html=(root/'index.html').read_text().replace('<link rel="stylesheet" href="game.css">','<style>'+(root/'game.css').read_text()+'</style>')
    return html.replace('<script type="module" src="src/ui/main.js"></script>','<script>\n'+'\n'.join(pieces)+'\n</script>')

BRIDGE_JS='''<script>
window.fetch = async (url, options={}) => {
  const r = await window.__threadlineHttp(String(url), options);
  return new Response(r.body, {status:r.status,headers:{'Content-Type':r.type}});
};
window.EventSource = class {
  constructor(url){this.url=url;this.readyState=0;this.handlers={};this.closed=false;setTimeout(()=>this.pump(),0);}
  addEventListener(name,fn){this.handlers[name]=fn;}
  async pump(){if(this.closed)return;try{const data=await window.__threadlineSSE();if(this.closed)return;const first=this.readyState!==1;this.readyState=1;if(first)this.onopen?.();this.handlers.state?.({data:JSON.stringify(data)});}catch(e){this.readyState=0;this.onerror?.(e);}if(!this.closed)this.timer=setTimeout(()=>this.pump(),1100);}
  close(){this.closed=true;this.readyState=2;clearTimeout(this.timer);}
};
</script>'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bridge',action='store_true');ap.add_argument('--chromium',default='/usr/bin/chromium');ap.add_argument('--out',default=str(ROOT/'evidence'));args=ap.parse_args()
    out=Path(args.out);(out/'screenshots').mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];latency=[];mode='native localhost';started=time.monotonic();success=False;version='unknown'
    def passed(name):checks.append({'name':name,'passed':True});print('PASS',name,flush=True)
    temp=tempfile.TemporaryDirectory(prefix='threadline-v2-browser-');store=Store(Path(temp.name)/'state');setup_demos(store);tracker=Tracker(store,.25);server=LocalServer(store,tracker,0);tracker.start();thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.1},daemon=True);thread.start()
    def request(path,options=None):
        options=options or {};headers={'Authorization':'Bearer '+server.token,**options.get('headers',{})};body=options.get('body');raw=body.encode() if body is not None else None
        if not path.startswith('/'):path='/'+path
        req=Request(server.url+path,data=raw,headers=headers,method=options.get('method','GET'))
        try:r=urlopen(req,timeout=10)
        except HTTPError as exc:r=exc
        with r:return {'status':r.status,'body':r.read().decode(),'type':r.headers.get('Content-Type','application/json')}
    def sse():
        with urlopen(Request(server.url+'/api/stream',headers={'Authorization':'Bearer '+server.token}),timeout=10) as response:
            while True:
                line=response.readline().decode()
                if line.startswith('data: '):return json.loads(line[6:])
                if not line:raise RuntimeError('Stream closed')
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
            version=browser.version;context=browser.new_context(viewport={'width':1512,'height':982},device_scale_factor=1)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            bridge=args.bridge
            if not bridge:
                try:page.goto(server.launch_url,wait_until='domcontentloaded',timeout=15000)
                except Exception as exc:
                    if 'ERR_BLOCKED_BY_ADMINISTRATOR' not in str(exc):raise
                    bridge=True
            if bridge:
                mode='Chromium rendering + real HTTP/SSE via explicit browser bindings; native navigation blocked by managed policy'
                page.expose_function('__threadlineHttp',request);page.expose_function('__threadlineSSE',sse)
                page.set_content(inline_app((WEB/'index.html').read_text()).replace('<head>','<head>'+BRIDGE_JS,1),wait_until='domcontentloaded')
            def screenshot(name):
                page.mouse.move(6,80);page.wait_for_timeout(180);page.screenshot(path=str(out/'screenshots'/name),full_page=True)
            def click_node(ident):
                loc=page.locator('[data-node='+json.dumps(ident)+']');loc.wait_for(timeout=12000)
                box=loc.bounding_box();assert box,ident
                page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2);page.wait_for_timeout(350)
            def rev():return int(page.locator('html').get_attribute('data-revision'))
            def positions():return page.locator('.graph-node').evaluate_all('(ns)=>Object.fromEntries(ns.map(n=>[n.dataset.node,[+n.dataset.x,+n.dataset.y]]))')
            def wait_revision(old):page.wait_for_function('(r)=>+document.documentElement.dataset.revision>r',arg=old,timeout=15000)
            def overview():page.locator('#home-button').click();page.wait_for_timeout(250)
            page.wait_for_selector('.graph-node',timeout=15000);page.wait_for_function("document.getElementById('connection').textContent.includes('Live')")
            assert page.locator('.graph-node').count()==5
            assert page.evaluate('cytoscape.version')=='3.33.1';assert page.locator('#cy canvas').count()>=1
            assert page.locator('#sidebar, .tree-item, [data-tab]').count()==0
            passed('Graph-first canvas uses the real Cytoscape renderer; no tree or platform navigation')
            screenshot('01-live-architecture.png');root_positions=positions()
            click_node('module:src/narrative');assert page.locator('#scope-title').inner_text()=='narrative'
            assert page.locator('[data-node="file:src/narrative/dialogue.js"]').count()==1
            assert page.locator('.is-context').count()>=1
            passed('A single mouse click enters a component and preserves connected context')
            screenshot('02-explore-component.png')
            click_node('file:src/narrative/dialogue.js')
            page.wait_for_function("document.getElementById('source-code')?.textContent.includes('explainMemory')")
            assert 'r1' in page.locator('#source-version').inner_text()
            assert page.locator('#stage').bounding_box()['width']>page.locator('#inspector').bounding_box()['width']*2
            passed('Single-click source inspection uses retained code while the graph stays dominant')
            screenshot('03-source-understanding.png');page.locator('#drawer-close').click()
            # Actual filesystem updates. No button, mocked graph, manual scan or publisher call.
            root=Path(store.project('lantern-harbor')['root']);entry=root/'src/narrative/dialogue.js';original=entry.read_text()
            baseline=rev();coords=positions();transform=page.locator('#node-layer').get_attribute('style');t=time.monotonic()
            (root/'src/narrative/echo.js').write_text('export function echoMemory(memory) {\n  return memory.events.join(" | ");\n}\n')
            entry.write_text("import { echoMemory } from './echo.js';\n"+original)
            wait_revision(baseline);latency.append(round((time.monotonic()-t)*1000,1))
            page.wait_for_selector('[data-node="file:src/narrative/echo.js"].state-added')
            assert page.locator('[data-node="file:src/narrative/dialogue.js"].state-changed').count()==1
            now=positions();assert all(now[k]==v for k,v in coords.items() if k in now)
            assert page.locator('#node-layer').get_attribute('style')==transform
            assert '+1' in page.locator('#changes-summary').inner_text()
            passed('External file creation/import automatically reaches the UI; retained node positions and viewport do not move')
            screenshot('04-live-addition.png')
            cyexpr="document.getElementById('cy')._cyreg.cy"
            point=page.evaluate(f'''()=>{{const c={cyexpr};const e=c.edges().filter(e=>e.target().id()==='file:src/narrative/echo.js')[0];return e.renderedMidpoint();}}''')
            stage=page.locator('#cy').bounding_box();page.mouse.click(stage['x']+point['x'],stage['y']+point['y']);page.wait_for_timeout(180)
            assert 'WHY THESE COMPONENTS CONNECT' in page.locator('#inspector').inner_text()
            assert './echo.js' not in page.locator('#inspector').inner_text() or 'imports' in page.locator('#inspector').inner_text()
            assert 'src/narrative/dialogue.js:1' in page.locator('#inspector').inner_text()
            passed('Clicking an actual rendered edge reveals its source-location evidence')
            page.locator('#drawer-close').click();page.locator('#clear-changes').click()
            old=rev();t=time.monotonic();entry.write_text(original);(root/'src/narrative/echo.js').unlink();wait_revision(old);latency.append(round((time.monotonic()-t)*1000,1))
            page.wait_for_selector('[data-node="file:src/narrative/echo.js"].state-removed')
            assert not any(n['id']=='file:src/narrative/echo.js' for n in store.snapshot('lantern-harbor')['nodes'])
            passed('A real removal becomes a dashed ghost only in presentation, not in the stored current graph')
            screenshot('05-live-removal.png');click_node('file:src/narrative/echo.js')
            page.wait_for_function("document.getElementById('source-code').textContent.includes('echoMemory')")
            assert 'Removed from the current graph' in page.locator('#inspector').inner_text()
            passed('Removed nodes remain inspectable through their retained historical source')
            page.locator('#drawer-close').click();count=len(store.history('lantern-harbor'));page.locator('#clear-changes').click()
            assert page.locator('[data-node="file:src/narrative/echo.js"]').count()==0;assert len(store.history('lantern-harbor'))==count
            passed('Dismissing highlights clears visual ghosts without deleting atomic history')
            # Node drag uses real mouse interaction; it must not be mistaken for drill-in.
            a=page.locator('[data-node="file:src/narrative/dialogue.js"]').bounding_box();prev=positions()['file:src/narrative/dialogue.js']
            page.mouse.move(a['x']+a['width']/2,a['y']+40);page.mouse.down();page.mouse.move(a['x']+a['width']/2+60,a['y']+75,steps=12);page.mouse.up();page.wait_for_timeout(200)
            dragged=positions()['file:src/narrative/dialogue.js'];assert dragged!=prev
            old=rev();entry.write_text(original+'\n// A human or agent saved this source file.\n');wait_revision(old)
            assert positions()['file:src/narrative/dialogue.js']==dragged
            passed('Manual node arrangement survives subsequent live source edits')
            page.locator('#search-open').click();page.locator('#search-input').fill('canGrantPassage');page.locator('#search-input').press('Enter')
            page.wait_for_function("document.getElementById('drawer-title').textContent==='canGrantPassage'")
            assert page.locator('html').get_attribute('data-scope')=='module:src/domain'
            passed('Keyboard search jumps to the implementing scope and declaration')
            page.locator('#drawer-close').click();page.locator('#mode-features').click();click_node('feature:remembered-favors')
            assert page.locator('[data-node="file:src/narrative/dialogue.js"]').count()==1
            assert 'needs review' in page.locator('#inspector').inner_text()
            passed('Feature navigation stays source-linked and marks changed evidence stale')
            page.locator('#drawer-close').click();page.locator('#mode-modules').click()
            page.locator('#history-button').click();assert page.locator('.history-item').count()>=4
            page.locator('#checkpoint-button').click();page.locator('#checkpoint-name').fill('Live map proven');page.locator('#checkpoint-note').fill('Atomic changes retained');n=store.head('lantern-harbor');page.locator('#checkpoint-form button[type=submit]').click();page.wait_for_function("!document.getElementById('checkpoint-dialog').open")
            assert store.head('lantern-harbor')==n;assert any(c['name']=='Live map proven' for c in store.checkpoints('lantern-harbor'))
            passed('Checkpoints label existing revisions without adding architecture nodes or collapsing history')
            screenshot('06-history-beneath-the-map.png')
            page.locator('.history-item[data-revision="1"]').click();page.wait_for_function("document.documentElement.dataset.revision==='1'")
            assert 'Viewing revision 1' in page.locator('#revision-banner').inner_text()
            old=store.head('lantern-harbor');(root/'docs/observed.md').write_text('# Actual saved document\n');
            page.wait_for_function('(n)=>document.getElementById("revision-text").textContent.includes("r"+(n+1))',arg=old,timeout=15000)
            assert rev()==1;assert store.head('lantern-harbor')>old
            passed('History is read-only while background capture continues to advance HEAD')
            page.locator('#return-live').click();page.wait_for_function('(n)=>+document.documentElement.dataset.revision>n',arg=old)
            assert page.locator('#revision-banner').is_hidden();page.locator('#drawer-close').click()
            assert all(positions()[k]==v for k,v in root_positions.items());passed('Returning to live reconciles with persisted HEAD without corrupting per-scope geometry')
            assets={f.name:f.read_bytes() for f in WEB.iterdir() if f.is_file()}
            # New staged demo creates a real new component, connects it, then edits it.
            page.locator('#demo-change-button').click();baseline=rev();page.wait_for_selector('[data-node="module:src/journal"]',timeout=15000)
            assert (root/'src/journal/format.js').exists()
            page.wait_for_function("!document.getElementById('demo-change-button').disabled",timeout=20000)
            assert store.head('lantern-harbor')>=baseline+3
            assert page.locator('[data-node="module:src/journal"].state-added').count()==1
            assert any(e['source']=='file:src/narrative/dialogue.js' and e['target']=='file:src/journal/format.js' for e in store.snapshot('lantern-harbor')['edges'])
            passed('Watch-a-change performs three genuine staged file edits discovered by the ordinary watcher')
            screenshot('07-new-component-live.png')
            page.locator('#project-select').select_option('orbit-courier');page.wait_for_function("document.documentElement.dataset.project==='orbit-courier'")
            assert all(f.read_bytes()==assets[f.name] for f in WEB.iterdir() if f.is_file())
            passed('A second codebase reuses the identical installed viewer bytes')
            screenshot('08-second-codebase.png')
            page.locator('#demo-change-button').click();page.wait_for_selector('[data-node="module:src/navigation"]',timeout=15000)
            page.wait_for_function("!document.getElementById('demo-change-button').disabled",timeout=20000)
            assert (Path(store.project('orbit-courier')['root'])/'src/navigation/beacon.js').exists()
            passed('The same staged source-to-live-graph workflow operates on the second game')
            # HTTP publishing is a separate real path from filesystem observation.
            body={'id':'agent-project','name':'Agent-published architecture'}
            assert request('/api/projects',{'method':'POST','body':json.dumps(body),'headers':{'Content-Type':'application/json'}})['status']==201
            from threadline.model import now
            snap={'schemaVersion':'1.0','project':{'id':'agent-project','name':body['name']},'source':{'capturedAt':now(),'publisher':'acceptance-publisher','treeHash':'a'*64},'nodes':[{'id':'module:.','kind':'module','label':'.','path':'.'},{'id':'module:logic','kind':'module','label':'logic','path':'logic','parent':'module:.'},{'id':'file:logic/main.py','kind':'file','label':'main.py','path':'logic/main.py','parent':'module:logic'}],'edges':[]}
            data={'snapshot':snap,'expectedRevision':0,'eventId':'browser-agent-1','summary':'Agent created the logic module','actor':'test-coding-agent'}
            r=request('/api/projects/agent-project/publish',{'method':'POST','body':json.dumps(data),'headers':{'Content-Type':'application/json'}});assert r['status']==201,r
            passed('An authenticated external agent can publish structured graph data without generating frontend code')
            page.wait_for_selector('#project-select option[value="agent-project"]',state='attached',timeout=12000)
            page.locator('#project-select').select_option('agent-project');page.wait_for_selector('[data-node="module:logic"]')
            snap['source']['treeHash']='b'*64;snap['nodes'].extend([{'id':'module:memory','kind':'module','label':'memory','path':'memory','parent':'module:.'},{'id':'file:memory/store.py','kind':'file','label':'store.py','path':'memory/store.py','parent':'module:memory'}]);snap['edges'].append({'id':'agent-link','source':'file:logic/main.py','target':'file:memory/store.py','kind':'imports','evidence':[]})
            data.update({'snapshot':snap,'expectedRevision':1,'eventId':'browser-agent-2','summary':'Agent connected the new memory module'})
            r=request('/api/projects/agent-project/publish',{'method':'POST','body':json.dumps(data),'headers':{'Content-Type':'application/json'}});assert r['status']==201,r
            page.wait_for_selector('[data-node="module:memory"].state-added');assert 'Agent connected' in page.locator('#event-summary').inner_text()
            screenshot('10-agent-published-live.png');passed('An actual agent-published second revision changes the live graph in the unchanged viewer')
            page.locator('#project-select').select_option('orbit-courier');page.wait_for_function("document.documentElement.dataset.project==='orbit-courier'")

            # Direct source game logic, maintained from v1, still executes after the new refactor.
            for ident,expected,actions in [('lantern-harbor','PASSAGE GRANTED',['introduce','repair','request']),('orbit-courier','DELIVERY COMPLETE',['right','right','down','right','right','right','down','down','down'])]:
                game=context.new_page();game.on('pageerror',lambda e:errors.append(str(e)))
                if bridge:game.set_content(inline_game(Path(store.project(ident)['root'])),wait_until='domcontentloaded')
                else:game.goto(server.url+'/demo/'+ident+'/index.html',wait_until='domcontentloaded')
                for action in actions:game.locator(f'[data-{"action" if ident=="lantern-harbor" else "move"}="{action}"]').click()
                assert expected in game.locator('#outcome' if ident=='lantern-harbor' else '#status').inner_text();game.close();passed(ident+' still reaches its win state after the staged refactor')
            page.set_viewport_size({'width':390,'height':844});page.locator('#fit-button').click();page.wait_for_timeout(350)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            screenshot('09-compact-viewport.png');passed('Compact viewport keeps graph controls reachable without horizontal page overflow')
            page.set_viewport_size({'width':1512,'height':982});page.locator('#fit-button').click();page.wait_for_timeout(250)
            page.locator('[data-node="module:src/engine"]').focus();page.keyboard.press('Enter');assert page.locator('#scope-title').inner_text()=='engine'
            passed('Keyboard activation navigates nodes without a separate expand button')
            # Exercise the actual browser Save portable map path, not just the Python exporter.
            page.evaluate('''()=>{const original=URL.createObjectURL.bind(URL);URL.createObjectURL=(blob)=>{window.__savedMap=blob;return original(blob);};}''')
            page.locator('#more-button').click();page.locator('#export-button').click()
            page.wait_for_function('window.__savedMap instanceof Blob',timeout=12000)
            saved_html=page.evaluate('window.__savedMap.text()')
            saved_page=context.new_page();saved_page.on('pageerror',lambda e:errors.append(str(e)));saved_requests=[];saved_page.on('request',lambda r:saved_requests.append(r.url))
            saved_page.set_content(saved_html,wait_until='domcontentloaded');saved_page.wait_for_selector('.graph-node')
            assert 'read only' in saved_page.locator('#connection').inner_text();assert not saved_requests
            assert saved_page.evaluate('cytoscape.version')=='3.33.1';saved_page.close()
            passed('The actual Save portable map action embeds a working renderer without external resources')
            # Self-contained export: same bundled graph renderer, no network at all.
            export_page=context.new_page();export_page.on('pageerror',lambda e:errors.append(str(e)));requests=[];export_page.on('request',lambda r:requests.append(r.url))
            data=store.export('lantern-harbor');export_page.set_content(render_export(data),wait_until='domcontentloaded');export_page.wait_for_selector('.graph-node')
            assert 'read only' in export_page.locator('#connection').inner_text();assert not requests
            export_page.locator('#history-button').click();assert export_page.locator('#checkpoint-button').is_disabled()
            passed('Portable HTML uses the identical graph renderer, no external requests, and read-only history')
            malicious=store.export('lantern-harbor',history=False);next(n for n in malicious['snapshot']['nodes'] if n['kind']=='module' and n.get('path')!='.')['label']='</script><script>window.INJECTED=true</script>'
            export_page.set_content(render_export(malicious),wait_until='domcontentloaded');export_page.wait_for_selector('.graph-node');export_page.locator('#search-open').click();export_page.locator('#search-input').fill('script');assert export_page.evaluate('window.INJECTED') is None
            passed('Untrusted graph labels cannot execute script in graph, search, or portable export')
            assert not errors,errors;passed('No uncaught JavaScript page errors across the tested flows')
            success=True;context.close();browser.close()
    except Exception as exc:
        checks.append({'name':'Acceptance failure','passed':False,'error':str(exc)});traceback.print_exc()
        try:page.screenshot(path=str(out/'screenshots/failure.png'),full_page=True)
        except Exception:pass
    finally:
        server.shutdown();server.server_close();tracker.stop();thread.join(timeout=3)
        report={'success':success,'checks':checks,'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'browser':'Chromium '+version,'transport':mode,'durationSeconds':round(time.monotonic()-started,2),'javascriptErrors':errors,'observedFileToUiMs':latency,'limitations':['Native WorkBuddy account/import not exercised.','Only this container Chromium was executed.','Demo source edits are explicitly scripted; no live LLM call is claimed.','Graph data is structural evidence, not a complete call graph.']}
        (out/'browser-results.json').write_text(json.dumps(report,indent=2)+'\n');temp.cleanup()
    return 0 if success else 1

if __name__=='__main__':raise SystemExit(main())
