/* Threadline 2 · one stable viewer, fed by observed or agent-published graph data. */
(function(){
function start(){
'use strict';
const $=id=>document.getElementById(id),G=ThreadlineGraph;
const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=v=>{try{return new Date(v).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});}catch{return '';}};
const S={pid:null,projects:[],graph:null,before:null,history:[],checkpoints:[],nextBefore:null,mode:'modules',scope:'@root',page:0,trail:[],cache:new Map(),projection:null,revision:null,head:0,drawer:null,selection:null,bundles:null,offline:false,stream:null,connected:false,watching:false,tracker:{},ticket:0,loading:false,dirty:false,sourceTicket:0,searchResults:[],searchIndex:0,building:false};
let toastTimer;
function toast(msg){$('toast').textContent=msg;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4300);}
function announce(msg){$('announcer').textContent=msg;}
function error(msg){$('error-banner').textContent=msg;$('error-banner').hidden=!msg;}
function caught(fn){return async(...args)=>{try{return await fn(...args);}catch(e){toast(e.message||String(e));}};}
const projectInfo=()=>S.projects.find(p=>p.id===S.pid)||{};
const bundle=()=>S.bundles?.find(b=>b.snapshot.project.id===S.pid);
const route=(action,query='')=>`/api/projects/${encodeURIComponent(S.pid)}/${action}${query?'?'+query:''}`;
function getStoredToken(){try{return localStorage.getItem('threadline_token')||'';}catch{return '';}}
function setStoredToken(token){try{if(token)localStorage.setItem('threadline_token',token);else localStorage.removeItem('threadline_token');}catch{}}
function getStoredProject(){try{return localStorage.getItem('threadline_project')||'';}catch{return '';}}
function setStoredProject(pid){try{if(pid)localStorage.setItem('threadline_project',pid);else localStorage.removeItem('threadline_project');}catch{}}
function getUrlProject(){
 try{
  const sp=new URLSearchParams(location.search);
  if(sp.has('project'))return sp.get('project')||'';
  const hp=new URLSearchParams(location.hash.slice(1));
  if(hp.has('project'))return hp.get('project')||'';
 }catch{}
 return '';
}
function updateUrlProject(pid,push=false){
 try{
  const u=new URL(location.href);
  if(pid)u.searchParams.set('project',pid);
  else u.searchParams.delete('project');
  const target=u.pathname+u.search+u.hash;
  if(push)history.pushState(null,'',target);
  else history.replaceState(null,'',target);
 }catch{}
}
function updateProjectDot(){
 const dot=document.querySelector('.project-dot');
 if(!dot)return;
 const p=projectInfo();
 dot.className='project-dot'+(p.demo?' demo':p.mode==='published'?' published':S.watching?' live':'');
 dot.title=p.name?(p.name+(p.demo?' (Example)':p.revision?' (r'+p.revision+')':'')):'';
}
function updateTitle(){
 const p=projectInfo();
 document.title=(p.name?p.name+' · ':'')+'Threadline Live Map';
}
async function api(url,body,headers={}){
 const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),15000);
 const token=getStoredToken(),authHeader=token?{'Authorization':'Bearer '+token}:{};
 try{const r=await fetch(url,{method:body!==undefined?'POST':'GET',credentials:'same-origin',headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...authHeader,...headers},body:body!==undefined?JSON.stringify(body):undefined,signal:ctl.signal});const data=await r.json();if(!r.ok){if(r.status===401){setStoredToken(null);if(!$('auth-dialog').open)$('auth-dialog').showModal();}throw Error(data.error||`Request failed (${r.status})`);}return data;}finally{clearTimeout(timer);}
}
const map=new ThreadlineMap({container:$('cy'),layer:$('node-layer'),onNode:onNode,onEdge:showEdge,onBackground:()=>map.select(null),onZoom:z=>$('zoom-label').textContent=Math.round(z*100)+'%',onPositions:positions=>{const key=cacheKey();S.cache.set(key,{positions,viewport:map.viewport()});}});
function cacheKey(){return [S.pid,S.mode,S.scope,S.page].join('|');}
function remember(){if(S.projection)S.cache.set(cacheKey(),{positions:new Map(map.positions),viewport:map.viewport()});}
function resetScope(){S.scope='@root';S.page=0;S.trail=[];closeDrawer();}
function connection(){
 const status=S.tracker[S.pid];let label='Reconnecting',cls='offline';
 if(S.offline)label='Snapshot · read only';else if(status&&!status.ok){label='Scan needs attention';cls='error';}
 else if(S.connected){label=projectInfo().mode==='published'?'Live · publishing':S.watching?'Live · watching':'Connected · manual';cls='';}
 $('connection').className='connection '+cls;$('connection').innerHTML='<i></i>'+h(label);$('connection').title=status?.error||'An accepted observation is one consistent source batch, not every keystroke.';
 $('event-activity').className='activity-dot '+(S.building?'busy':S.offline?'offline':cls==='error'?'error':'');
 if(status&&!status.ok&&!S.offline)error('The latest scan failed. This is the last good map: '+status.error);else if($('error-banner').textContent.startsWith('The latest scan failed.'))error('');
 updateProjectDot();
}
function updateProjectPicker(){
 const sel=$('project-select');
 if(!S.projects.length){sel.innerHTML='<option value="">No codebase connected</option>';return;}
 const workspaces=S.projects.filter(p=>!p.demo);
 const demos=S.projects.filter(p=>p.demo);
 const opt=p=>`<option value="${h(p.id)}">${h(p.name)}${p.revision?' (r'+p.revision+')':''}</option>`;
 let html='';
 if(workspaces.length&&demos.length){
  html=`<optgroup label="Projects">${workspaces.map(opt).join('')}</optgroup><optgroup label="Examples">${demos.map(opt).join('')}</optgroup>`;
 }else{
  html=S.projects.map(opt).join('');
 }
 sel.innerHTML=html;
 if(S.pid)sel.value=S.pid;
}
async function selectProject(pid,{navigation=true,syncUrl=true,pushHistory=false}={}){
 if(!pid)return;remember();S.pid=pid;setStoredProject(pid);if(syncUrl)updateUrlProject(pid,pushHistory);
 S.ticket++;S.head=0;S.graph=null;S.before=null;S.revision=null;S.mode='modules';S.building=false;resetScope();error('');
 $('project-select').value=pid;updateProjectDot();updateTitle();
 const p=projectInfo();$('demo-change-button').disabled=false;$('demo-change-button').hidden=S.offline||!p.demo;$('play-button').hidden=S.offline||!p.demo;
 await loadGraph({navigation});
}
async function listProjects(){
 const data=await api('/api/projects');S.projects=data.projects;S.watching=data.watching;S.tracker=data.tracker||{};
 updateProjectPicker();
 const urlPid=getUrlProject(),storedPid=getStoredProject();let chosen=null;
 if(urlPid&&S.projects.some(p=>p.id===urlPid))chosen=urlPid;
 else if(storedPid&&S.projects.some(p=>p.id===storedPid))chosen=storedPid;
 else if(S.projects.length)chosen=S.projects[0].id;
 if(chosen)await selectProject(chosen,{navigation:true,syncUrl:chosen===urlPid});
 else{S.pid=null;drawEmpty();}
}
async function loadGraph({navigation=false,revision=S.revision}={}){
 if(!S.pid)return;const ticket=++S.ticket,pid=S.pid;S.loading=true;
 try{
  let graph,events,checkpoints,nextBefore=null;
  if(S.offline){const b=bundle();graph=revision?(b.snapshots?.[revision]||(b.snapshot.revision===revision?b.snapshot:null)):b.snapshot;if(!graph)throw Error('This revision was not included in the exported map.');events=b.history||[];checkpoints=b.checkpoints||[];}
  else{const r=await Promise.all([api(route('snapshot',revision?'revision='+revision:'')),api(route('history')),api(route('checkpoints'))]);graph=r[0];events=r[1].events;nextBefore=r[1].nextBefore;checkpoints=r[2].checkpoints;}
  G.validate(graph);if(ticket!==S.ticket||pid!==S.pid)return;
  const changed=S.graph?.project.id===pid&&graph.revision!==S.graph.revision;
  if(revision!==S.revision||navigation){S.before=null;if(revision&&revision>1){try{S.before=S.offline?bundle().snapshots?.[revision-1]||null:await api(route('snapshot','revision='+(revision-1)));}catch{S.before=null;}}}
  else if(changed&&!S.before)S.before=S.graph;
  if(ticket!==S.ticket||pid!==S.pid)return;
  S.graph=graph;S.revision=revision;S.history=events;S.checkpoints=checkpoints;S.nextBefore=nextBefore;S.head=Math.max(S.head,events[0]?.revision||graph.revision,projectInfo().revision||0);
  if(S.scope!=='@root'&&S.scope!=='@rootfiles'&&!graph.nodes.some(n=>n.id===S.scope)&&!S.before?.nodes.some(n=>n.id===S.scope))resetScope();
  if(!navigation)remember();draw(navigation);connection();
  if(changed&&!navigation){const c=G.fileCounts(S.projection.delta);announce(`Revision ${graph.revision}. ${c.added} files added, ${c.changed} changed, ${c.removed} removed.`);}
  if(S.drawer==='history')showHistory();else if(S.drawer==='changes')showChanges();else if(S.drawer==='node'&&S.selection){const sel=G.index(S.graph).nodes.get(S.selection)||G.index(S.before||{nodes:[]}).nodes.get(S.selection);if(sel)showNode(sel);else closeDrawer();}
 }catch(e){if(ticket===S.ticket){error(e.message);drawEmpty();}}
 finally{if(ticket===S.ticket){S.loading=false;if(S.dirty&&!S.revision){S.dirty=false;loadGraph();}}}
}
function navigationLabel(id){if(id==='@root')return S.mode==='features'?'Features':'Architecture';if(id==='@rootfiles')return 'Entry & assets';const n=S.graph?.nodes.find(n=>n.id===id)||S.before?.nodes.find(n=>n.id===id);return n?G.label(n):id;}
function go(scope,{push=true,page=0}={}){
 remember();if(push&&scope!==S.scope)S.trail.push({scope:S.scope,page:S.page});S.scope=scope;S.page=page;closeDrawer();draw(true);announce('Exploring '+navigationLabel(scope));
}
function back(){const prev=S.trail.pop();go(prev?.scope||'@root',{push:false,page:prev?.page||0});}
function onNode(n){if(!n)return;if((n.kind==='module'||n.kind==='feature')){go(n.id);if(n.kind==='feature')showNode(n.base);}else showNode(n.base);}
function draw(navigation=false){
 if(!S.graph)return drawEmpty();
 const saved=S.cache.get(cacheKey());S.projection=G.project(S.graph,{scope:S.scope,mode:S.mode,before:S.before,page:S.page});
 if(!S.projection.nodes.length&&S.page){S.page=0;return draw(true);}
 const positions=G.layout(S.projection,saved?.positions||new Map());map.render(S.projection,positions,{fit:navigation&&!saved});if(navigation&&saved)map.restore(saved.viewport);
 S.cache.set(cacheKey(),{positions,viewport:map.viewport()});
 const g=S.graph,p=projectInfo(),v=S.projection;updateProjectDot();updateTitle();
 document.documentElement.dataset.revision=String(g.revision||0);document.documentElement.dataset.project=S.pid;document.documentElement.dataset.scope=S.scope;
 $('scope-title').textContent=navigationLabel(S.scope);$('scope-count').textContent=String(v.total);
 $('scope-caption').textContent=S.scope==='@root'?(S.mode==='features'?'Follow a behavior to the code behind it.':'A live map of what is being built.'):(S.scope.startsWith('feature:')?'Supporting implementation · dashed cards keep the surrounding architecture in view.':'Inside '+navigationLabel(S.scope)+' · connected components stay in context.');
 if(v.hiddenRelations)$('scope-caption').textContent+=' '+v.hiddenRelations+' other relationships outside this view.';
 $('breadcrumbs').innerHTML='';const crumbs=[...S.trail.map(t=>t.scope),S.scope].filter((x,i,a)=>a.indexOf(x)===i);if(crumbs[0]!=='@root')crumbs.unshift('@root');for(const [i,id] of crumbs.entries()){if(i){const s=document.createElement('span');s.textContent='/';$('breadcrumbs').append(s);}const b=document.createElement('button');b.textContent=id==='@root'?g.project.name:navigationLabel(id);b.onclick=()=>{S.trail=S.trail.slice(0,Math.max(0,S.trail.findIndex(t=>t.scope===id)));go(id,{push:false});};$('breadcrumbs').append(b);}
 $('back-button').disabled=S.scope==='@root';
 for(const mode of ['modules','features']){$('mode-'+mode).classList.toggle('active',S.mode===mode);$('mode-'+mode).setAttribute('aria-pressed',String(S.mode===mode));}
 $('graph-empty').hidden=!!v.nodes.length;if(!v.nodes.length){$('graph-empty').querySelector('h2').textContent=S.mode==='features'?'Give the architecture a purpose.':'This component is empty.';$('graph-empty').querySelector('p').textContent=S.mode==='features'?'Your agent can map named features to their supporting source through the supplied Skill. The structural map works without those interpretations.':'Changes to the underlying codebase will appear here automatically.';$('empty-connect').textContent=S.mode==='features'?'How agents publish':'Connection guide';}
 $('demo-change-button').hidden=S.offline||!p.demo||!!S.revision;$('play-button').hidden=S.offline||!p.demo;
 $('revision-banner').hidden=!S.revision;$('revision-text').textContent=`Viewing revision ${S.revision} · retained graph. Latest is r${S.head}.`;$('return-live').textContent=S.offline?'Return to latest snapshot →':'Return to live →';
 $('page-controls').hidden=v.total<=v.limit;$('page-label').textContent=`${S.page*v.limit+1}–${Math.min(v.total,(S.page+1)*v.limit)} of ${v.total} · ${v.hidden} outside this page`;$('previous-page').disabled=!S.page;$('next-page').disabled=(S.page+1)*v.limit>=v.total;
 $('graph-hint').innerHTML=S.scope==='@root'?'<span class="hint-dot"></span>Click a component to explore <span>·</span> Drag to arrange':'<span class="hint-dot"></span>Click a file to read its source <span>·</span> Dashed cards are connected context';
 statusbar();
}
function statusbar(){
 if(!S.graph)return;const delta=S.projection?.delta,c=G.fileCounts(delta),event=S.history.find(e=>e.revision===S.graph.revision),total=c.added+c.changed+c.removed;const any=delta&&['nodes','edges'].some(k=>['added','changed','removed'].some(t=>delta[k][t].length));
 $('revision-id').textContent='r'+S.graph.revision;$('revision-id').title='Each accepted update is retained atomically.';
 let summary=event?.summary||'Source graph ready';if(event?.actor==='watcher'&&total){summary=`Source updated · ${total} file${total===1?'':'s'} ${total===1?'has':'have'} changed`;}
 $('event-summary').textContent=summary;$('event-summary').title=`${event?.actor||'publisher'} · ${event?.created?time(event.created):''} · ${S.graph.source?.coverage||''}`;
 $('changes-button').title=S.before?'Net changes since r'+S.before.revision+'. Dismiss highlights to begin a new change window.':'';$('changes-button').hidden=!any;$('change-legend').hidden=!any;$('changes-summary').innerHTML=total?`<span class="added">+${c.added}</span><span class="changed">~${c.changed}</span><span class="removed">−${c.removed}</span>`:'Graph updated';
 $('source-identity').textContent=(S.graph.source?.commit?.slice(0,7)||'working tree')+' / '+(S.graph.source?.treeHash?.slice(0,8)||'published');
 $('source-identity').title='Source state identity. Source references are not runtime proof.';
}
function drawEmpty(){
 S.projection={nodes:[],edges:[]};map.render(S.projection,new Map());$('graph-empty').hidden=false;
 const p=projectInfo();
 $('scope-title').textContent=p.name||'Your code, connected.';
 $('scope-count').textContent='0';
 $('scope-caption').textContent=p.id?'Waiting for first source observation…':'A stable viewer. A living codebase.';
 connection();updateProjectDot();updateTitle();
}
function drawer(title,kicker,type){S.drawer=type;$('inspector').hidden=false;$('drawer-title').textContent=title;$('drawer-kicker').textContent=kicker;$('drawer-body').innerHTML='';return $('drawer-body');}
function closeDrawer(){S.drawer=null;S.selection=null;S.sourceTicket++;$('inspector').hidden=true;map.select(null);}
function para(parent,text,cls=''){const p=document.createElement('p');p.textContent=text;if(cls)p.className=cls;parent.append(p);return p;}
function section(parent,title){const d=document.createElement('span');d.className='section-label';d.textContent=title;parent.append(d);}
function row(parent,title,subtitle,action,extra=''){const b=document.createElement('button');b.className='detail-row '+extra;b.innerHTML=`<strong>${h(title)}</strong>${subtitle?'<small>'+h(subtitle)+'</small>':''}`;b.onclick=caught(action);parent.append(b);return b;}
function showNode(n,line=null){
 if(!n)return;S.selection=n.id;map.select(n.id);const b=drawer(n.label,n.kind==='suggestion'?'AI PIPELINE SUGGESTION':n.kind==='feature'?'FEATURE INTERPRETATION':n.kind==='symbol'?'DECLARATION':'IMPLEMENTATION','node');S.selection=n.id;
 const idx=G.index(S.graph),prev=S.before?G.index(S.before):null,deleted=!idx.nodes.has(n.id),sourceGraph=deleted?S.before:S.graph;
 if(n.kind==='suggestion'){
  para(b,n.summary||'Proposed pipeline enhancement to improve development flow.');
  para(b,'This is a proposed idea connected to your system architecture. You can prompt WorkBuddy to implement it directly.','notice');
  if(n.rationale){
   section(b,'SYSTEM IMPROVEMENT & ALIGNMENT');
   para(b,n.rationale);
  }
  if(n.target){
   section(b,'TARGET ARCHITECTURE COMPONENT');
   const targetNode=sourceGraph.nodes.find(x=>x.id===n.target);
   row(b,targetNode?G.label(targetNode):n.target,targetNode?('Jump to '+(targetNode.path||targetNode.id)):'Target component in architecture',()=>{
    if(targetNode){
     const sc=G.sourceScope(S.graph,targetNode.id);
     if(sc&&sc!==S.scope)go(sc);
     requestAnimationFrame(()=>showNode(targetNode));
    }
   });
  }
  if(n.prompt){
   section(b,'PROMPT WORKBUDDY');
   para(b,'Copy this prompt and send it to WorkBuddy to build this feature:');
   const pre=document.createElement('pre');
   pre.className='prompt-preview';
   pre.textContent=n.prompt;
   b.append(pre);
   const copyBtn=document.createElement('button');
   copyBtn.className='primary-button copy-prompt-btn';
   copyBtn.innerHTML='<span>📋</span> Copy Prompt for WorkBuddy';
   copyBtn.onclick=async()=>{
    const ok=await copy(n.prompt);
    if(ok){
     copyBtn.classList.add('copied');
     copyBtn.innerHTML='<span>✓</span> Copied to Clipboard!';
     toast('WorkBuddy prompt copied to clipboard!');
     setTimeout(()=>{
      copyBtn.classList.remove('copied');
      copyBtn.innerHTML='<span>📋</span> Copy Prompt for WorkBuddy';
     },2200);
    }
   };
   b.append(copyBtn);
  }
  return;
 }
 if(n.kind==='feature'){
  para(b,n.summary||'A named feature linked to source by the publishing agent.');if(n.status==='stale')para(b,'Source changed. This interpretation needs review; it has not been automatically verified.','notice');else para(b,'Agent-authored interpretation, supported by source links—not proof of runtime behavior.');
  section(b,'SUPPORTING IMPLEMENTATION');for(const path of n.files||[]){const f=sourceGraph.nodes.find(f=>f.path===path&&['file','document'].includes(f.kind));row(b,path,f?'Open the recorded implementation':'Source path is no longer indexed',()=>{if(f)openFromAnywhere(f);else toast('This source path is not present in the graph.');});}return;
 }
 if(n.kind==='module'){para(b,'This component groups '+(S.projection?.nodes.find(v=>v.id===n.id)?.fileCount||0)+' indexed source files. Relationships are aggregated from their actual graph edges.');return;}
 requestAnimationFrame(()=>map.reveal(n.kind==='symbol'?n.parent:n.id));
 let file=n;if(n.kind==='symbol'){file=(idx.nodes.get(n.parent)||prev?.nodes.get(n.parent)||n);line=n.line;}
 const path=document.createElement('span');path.className='source-path';path.textContent=file.path||'';b.append(path);
 if(deleted)para(b,`Removed from the current graph. Showing the retained source at revision ${sourceGraph.revision}.`,'notice');
 const tags=document.createElement('div');tags.className='tag-row';tags.innerHTML=[file.language,file.lines?file.lines+' lines':null,file.analysis].filter(Boolean).map(v=>'<span class="tag">'+h(v)+'</span>').join('');b.append(tags);
 const description=file.summary|| (file.analysis==='file-only'?'This file is inventoried. Its internal dependencies are not parsed by the current adapter.':'Declarations and supported literal references are extracted from this file. Select a relationship to inspect the source evidence.');para(b,description);
 const syms=sourceGraph.nodes.filter(x=>x.parent===file.id&&x.kind==='symbol');if(syms.length){section(b,'DECLARATIONS · '+syms.length);for(const s of syms.slice(0,12))row(b,s.label,`${s.symbolType||'declaration'} · line ${s.line||'–'}`,()=>showNode(s,s.line));if(syms.length>12)para(b,`${syms.length-12} more declarations are available through search.`);}
 const links=sourceGraph.edges.filter(e=>!['contains','declares','implements'].includes(e.kind)&&(e.source===file.id||e.target===file.id));if(links.length){section(b,'CONNECTED SOURCE');for(const e of links.slice(0,10)){const out=e.source===file.id,target=(idx.nodes.get(out?e.target:e.source)||prev?.nodes.get(out?e.target:e.source));if(target)row(b,target.path||target.label,(out?'Uses':'Used by')+' · '+e.kind,()=>openFromAnywhere(target));}if(links.length>10)para(b,`${links.length-10} additional source relationships are present.`);}
 const tools=document.createElement('div');tools.className='source-toolbar';tools.innerHTML=`<span id="source-version">RETAINED SOURCE · r${sourceGraph.revision}</span><button id="copy-path">Copy path</button>`;b.append(tools);$('copy-path').onclick=caught(()=>copy(file.path||''));
 const pre=document.createElement('pre');pre.className='source-code';pre.id='source-code';pre.textContent=S.offline?'Source text is not embedded in this portable map. Match this path and source hash in your repository.':'Loading retained source…';b.append(pre);
 if(!S.offline){const ticket=++S.sourceTicket,pid=S.pid;api(route('source','path='+encodeURIComponent(file.path||'')+'&revision='+sourceGraph.revision)).then(data=>{if(ticket!==S.sourceTicket||pid!==S.pid||!pre.isConnected)return;if(!data.available){pre.textContent=data.reason||'This publisher did not retain source text.';return;}const text=data.text||'';const lines=text.split('\n'),cap=700;pre.innerHTML=lines.slice(0,cap).map((t,i)=>`<div class="code-line${i+1===line?' mark':''}"><i>${i+1}</i><span>${h(t)||' '}</span></div>`).join('');if(lines.length>cap)pre.append(document.createTextNode(`\n${lines.length-cap} further lines omitted in this panel. Use the source CLI for the complete retained file.`));if(line){const mark=pre.querySelector('.mark');mark?.scrollIntoView({block:'nearest'});}}).catch(e=>{if(pre.isConnected)pre.textContent=e.message;});}
}
function openFromAnywhere(n){
 const scope=G.sourceScope(S.graph,n.id);const prevScope=scope==='@root'&&S.before?G.sourceScope(S.before,n.id):scope;
 if(prevScope!==S.scope){go(prevScope);}
 // Paging is presentation only; search must still reveal a file beyond the first page.
 const all=G.frontier(S.graph,S.scope,S.mode);const target=n.kind==='symbol'?n.parent:n.id,i=all.findIndex(x=>x.id===target);if(i>=0&&Math.floor(i/30)!==S.page){S.page=Math.floor(i/30);draw(true);}
 showNode(n);map.select(n.kind==='symbol'?n.parent:n.id);
}
function showEdge(e){
 const isSug=e.kinds.includes('suggests');
 const b=drawer(isSug?'Pipeline suggestion link':e.members.length===1?'One source relationship':e.members.length+' source relationships',isSug?'AI SUGGESTION CONNECTION':'WHY THESE COMPONENTS CONNECT','edge');const idx=S.projection.index;
 para(isSug?'This dashed link connects a proposed AI development pipeline improvement to its target architecture component. Click the suggestion to inspect its rationale and copy its WorkBuddy prompt.':e.semantic?'These links are agent-authored feature interpretations. Follow the evidence to assess them.':'The arrow points from the referencing component to the component it uses. This is structural evidence, not a runtime execution trace.');
 for(const rel of e.members.slice(0,40)){
  const a=idx.nodes.get(rel.source),z=idx.nodes.get(rel.target);const block=document.createElement('div');block.className='detail-row';block.innerHTML=`<span class="relation-tag">${h(rel.kind)}${e.state==='removed'?' · REMOVED':''}</span><strong>${h(a?.label||rel.source)} → ${h(z?.label||rel.target)}</strong>`;b.append(block);
  if(rel.kind==='suggests'&&a){row(b,'Inspect '+a.label,'View rationale and copy WorkBuddy prompt',()=>showNode(a));}
  for(const ev of rel.evidence||[]){const file=idx.nodes.get('file:'+ev.path)||[...idx.nodes.values()].find(n=>n.path===ev.path&&['file','document'].includes(n.kind));row(b,ev.path+(ev.line?':'+ev.line:''),(ev.method||'source reference')+' · '+(ev.status||'unverified'),()=>{if(file){openFromAnywhere(file);if(ev.line)showNode(file,ev.line);}else toast('The supporting file is not indexed in this revision.');});}
  if(!(rel.evidence||[]).length&&rel.kind!=='suggests')para(b,'No source-location evidence was supplied for this relationship.');
 }
 if(e.members.length>40)para(b,`${e.members.length-40} more relationships are retained in the graph data.`);
}
function showChanges(){
 const b=drawer('What changed','CURRENT CHANGE WINDOW','changes'),d=S.projection?.delta;if(!d){para(b,'No highlighted changes. Every accepted revision is still available in history.');return;}
 para(b,`Net changes from revision ${S.before?.revision} to ${S.graph.revision}. Highlights remain until dismissed; individual updates are still in history. They do not infer authorship.`);
 let count=0;for(const [key,state,verb] of [['added','added','Added'],['changed','changed','Changed'],['removed','removed','Removed']])for(const item of d.nodes[key]){const n=item.after||item;if(!['file','document'].includes(n.kind))continue;count++;row(b,n.path||n.label,verb+' · '+(n.language||n.kind),()=>openFromAnywhere(n),'changed-item '+state);}
 if(!count)para(b,'Only graph relationships, annotations, or declarations changed. No file inventory/hash change was reported.');
 const links=d.edges.added.length+d.edges.changed.length+d.edges.removed.length;para(b,`${links} underlying graph-edge changes retained. Structural containment and declaration edges stay out of the primary architecture view.`);
}
function showHistory(){
 const b=drawer('Under the surface','ATOMIC HISTORY','history');para(b,'A clean map above; every accepted revision underneath. Click a revision to inspect it without stopping live capture.');
 const btn=document.createElement('button');btn.id='checkpoint-button';btn.className='drawer-button';btn.textContent='+ Name this moment';btn.disabled=S.offline||!!S.revision;btn.onclick=()=>{$('checkpoint-name').value='';$('checkpoint-note').value='';$('checkpoint-dialog').showModal();};b.append(btn);
 for(const e of S.history){const item=document.createElement('button');item.className='history-item'+(S.graph.revision===e.revision?' active':'');item.dataset.revision=String(e.revision);const checkpoints=S.checkpoints.filter(c=>c.revision===e.revision);item.innerHTML=`<div class="history-top"><span>r${e.revision}${e.revision===S.head?' · LATEST':''}</span><span>${h(time(e.created))}</span></div><span class="history-summary">${h(e.summary)}</span><span class="history-actor">${h(e.actor)} · ${h(e.kind)}</span>${checkpoints.map(c=>'<span class="history-checkpoint">◇ '+h(c.name)+'</span>').join('')}`;item.onclick=()=>loadGraph({revision:e.revision,navigation:true});b.append(item);}
 if(S.nextBefore&&!S.offline){const more=document.createElement('button');more.className='drawer-button';more.textContent='Load earlier revisions';more.onclick=caught(async()=>{const r=await api(route('history','before='+S.nextBefore));S.history.push(...r.events);S.nextBefore=r.nextBefore;showHistory();});b.append(more);}
 if(S.offline&&bundle().historyTruncated)para(b,'This export contains only part of the retained history.');
}
function showSearch(){if(!$('search-dialog').open)$('search-dialog').showModal();$('search-input').value='';S.searchIndex=0;renderSearch();$('search-input').focus();}
function renderSearch(){const q=$('search-input').value.trim().toLowerCase();if(!S.graph)return;
 S.searchResults=S.graph.nodes.filter(n=>n.path!=='.'&&(n.label+' '+(n.path||'')+' '+(n.summary||'')).toLowerCase().includes(q)).sort((a,b)=>Number(a.kind==='symbol')-Number(b.kind==='symbol')||Number(!a.label.toLowerCase().startsWith(q))-Number(!b.label.toLowerCase().startsWith(q))||a.label.localeCompare(b.label)).slice(0,50);S.searchIndex=Math.min(S.searchIndex,Math.max(0,S.searchResults.length-1));
 $('search-results').innerHTML=S.searchResults.map((n,i)=>`<button class="search-result${i===S.searchIndex?' active':''}" data-result="${i}"><span class="result-kind">${h(n.kind)}</span><span><strong>${h(n.label)}</strong><small>${h(n.path||n.summary||n.kind)}</small></span></button>`).join('')||'<p class="empty-note" style="padding:14px">No matching indexed source. Try another name or path.</p>';
 $('search-results').querySelectorAll('[data-result]').forEach(b=>b.onclick=()=>chooseResult(Number(b.dataset.result)));
}
function chooseResult(i){const n=S.searchResults[i];if(!n)return;$('search-dialog').close();if(n.kind==='module'||n.kind==='feature'||n.kind==='suggestion'){if(n.kind!=='suggestion')go(n.id);showNode(n);}else openFromAnywhere(n);}
async function copy(text){let ok=false;if(navigator.clipboard&&navigator.clipboard.writeText){try{await navigator.clipboard.writeText(text);ok=true;}catch(_){}}if(!ok){try{const ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.opacity='0';document.body.append(ta);ta.select();ok=document.execCommand('copy');ta.remove();}catch(_){}}if(ok)toast('Copied.');else toast('Clipboard is unavailable here.');return ok;}
function help(kind='connect'){
 $('help-title').textContent=kind==='about'?'A map, not another platform.':'Keep a live map beside your agent.';
 if(kind==='about')$('help-body').innerHTML='<p>Threadline is a fixed viewer for a changing codebase. Click a component to enter it. Click a source file or relationship to understand its implementation. Drag nodes to arrange them; updates preserve your layout.</p><p><strong>Green</strong> marks additions; <strong>amber</strong> marks modifications; <strong>rose dashed</strong> nodes retain the context of removals. Dismissing highlights never deletes history.</p><p>Structural references are source-backed where the adapter supplies evidence. Feature mappings are interpretations and become stale when their supporting source changes. Neither proves runtime behavior.</p><p>There is no model inside this viewer. Human edits and agent edits use the same observation pipeline. Attribution is publisher-supplied; a filesystem watcher cannot reliably identify the author.</p><p>Threadline 2.0 · Cytoscape.js 3.33.1 · local-first · no external runtime requests.</p>';
 else $('help-body').innerHTML='<p>Run from the extracted project. The local watcher follows saved source changes while your coding agent works. No project-specific frontend is generated.</p><pre>python run.py add "/path/to/codebase" --id my-project\npython run.py serve</pre><p>For the two included examples:</p><pre>python run.py demo</pre><p>Your agent can use <code>skills/threadline</code> to publish semantic mappings or the schema/CLI to publish a graph. Keep this window open alongside the agent.</p><p>Navigation: <strong>click</strong> a module to enter; click a file to read; <strong>/</strong> to find; <strong>F</strong> to fit; <strong>Backspace</strong> to go up. History lives in the revision control at the bottom left.</p><p>Source stays in the local store. Publicly sharing the viewer does not publish your repository.</p>';
 $('help-dialog').showModal();
}
async function runExample(){
 if(S.building)return;S.building=true;const pid=S.pid;$('demo-change-button').disabled=true;$('demo-change-button').innerHTML='<span>◌</span> Editing example… <small>SCRIPTED</small>';connection();
 // This is explicitly a scripted source edit, not a pretend AI response. The server
 // validates the disposable example root before writing. Normal source edits need no button.
 try{await api(route('demo-build'),{});toast('Scripted build started. Real files are changing; the watcher supplies the graph.');}
 catch(e){toast(e.message);}
 finally{setTimeout(()=>{if(S.pid===pid){S.building=false;$('demo-change-button').disabled=false;$('demo-change-button').innerHTML='<span>▷</span> Watch a change <small>EXAMPLE</small>';connection();}},11000);}
}
async function saveExport(){const data=S.offline?bundle():await api(route('export'));let html;
 const files=['style.css','cytoscape.min.js','graph.js','map-view.js','app.js'];
 if(S.offline){ // Already self-contained: preserve the original document and replace only its data.
  toast('This is already a portable map. Keep the original HTML file, or use the CLI export for another revision.');return;
 }
 const [shell,...texts]=await Promise.all([fetch('index.html').then(r=>r.text()),...files.map(f=>fetch(f).then(r=>r.text()))]);html=shell.replace('<link rel="stylesheet" href="style.css">',()=>'<style>'+texts[0]+'</style>');
 const payload=JSON.stringify(data).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');html=html.replace('<script src="cytoscape.min.js" defer></script>',()=>'<script id="threadline-data" type="application/json">'+payload+'</script><script>'+texts[1].replace(/<\/script/gi,'<\\/script')+'</script>');for(let i=2;i<files.length;i++)html=html.replace('<script src="'+files[i]+'" defer></script>',()=>'<script>'+texts[i].replace(/<\/script/gi,'<\\/script')+'</script>');
 const blob=new Blob([html],{type:'text/html;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=S.pid+'-live-map.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);toast('Portable, read-only map saved. Source text and local credentials are not included.');
}
function openBundle(data){
 const bundles=data.format==='threadline-workspace'?data.bundles:data.snapshot?[data]:[{format:'threadline-bundle',snapshot:data,history:[],checkpoints:[]}];if(!Array.isArray(bundles)||!bundles.length)throw Error('No snapshots in this data file.');for(const b of bundles){G.validate(b.snapshot);for(const g of Object.values(b.snapshots||{}))G.validate(g);}
 const ids=new Set();for(const b of bundles){if(ids.has(b.snapshot.project.id))throw Error('Duplicate project IDs.');ids.add(b.snapshot.project.id);}
 S.ticket++;S.stream?.close();S.stream=null;S.connected=false;S.offline=true;S.bundles=bundles;S.projects=bundles.map(b=>({...b.snapshot.project,revision:b.snapshot.revision,mode:'published'}));
 updateProjectPicker();
 const urlPid=getUrlProject(),storedPid=getStoredProject();let targetPid=null;
 if(urlPid&&S.projects.some(p=>p.id===urlPid))targetPid=urlPid;
 else if(storedPid&&S.projects.some(p=>p.id===storedPid))targetPid=storedPid;
 else targetPid=S.projects[0].id;
 selectProject(targetPid,{navigation:true});
}
let refreshingProjects=false;
function stateUpdate(data){
 if(data.projects?.some(p=>!S.projects.some(old=>old.id===p.id))&&!refreshingProjects){
  refreshingProjects=true;api('/api/projects').then(r=>{
   const current=S.pid;S.projects=r.projects;updateProjectPicker();
   const urlPid=getUrlProject();
   if(urlPid&&S.projects.some(p=>p.id===urlPid)&&urlPid!==current){
    selectProject(urlPid,{navigation:true});
   }else if(current&&S.projects.some(p=>p.id===current)){
    $('project-select').value=current;
   }else if(S.projects.length){
    selectProject(S.projects[0].id,{navigation:true});
   }
  }).catch(e=>error(e.message)).finally(()=>refreshingProjects=false);
 }

 S.connected=true;S.tracker=data.tracker||{};S.watching=data.watching;connection();const p=data.projects?.find(p=>p.id===S.pid);if(!p)return;
 const job=data.demo?.[S.pid];if(job){S.building=job.running;$('demo-change-button').disabled=!!job.running;$('demo-change-button').innerHTML=job.running?'<span>◌</span> Editing example… <small>SCRIPTED</small>':'<span>▷</span> Watch a change <small>EXAMPLE</small>';if(job.running){$('event-summary').textContent=job.phase+' · scripted';}if(job.error)error(job.error);}S.head=p.revision;const local=projectInfo();local.revision=p.revision;
 if(S.revision){$('revision-text').textContent=`Viewing revision ${S.revision} · retained graph. Latest is r${S.head}.`;return;}
 if(p.revision!==S.graph?.revision){if(S.loading)S.dirty=true;else loadGraph();}
 else if(p.checkpointCount!==undefined&&p.checkpointCount!==S.checkpoints.length&&!S.loading)loadGraph();
 // Reconnect reconciles with persisted HEAD rather than an ephemeral event queue.
}
function connectStream(){
 S.stream?.close();if(S.offline)return;const token=getStoredToken();const url='/api/stream'+(token?'?token='+encodeURIComponent(token):'');const es=new EventSource(url);S.stream=es;es.onopen=()=>{S.connected=true;connection();};es.onerror=()=>{S.connected=false;connection();};es.addEventListener('state',e=>{try{stateUpdate(JSON.parse(e.data));}catch(exc){error('Live update could not be read: '+exc.message);}});
}
async function authenticate(token){setStoredToken(token);await api('/api/session',{},{'Authorization':'Bearer '+token});try{history.replaceState(null,'',location.pathname+location.search);}catch{}$('auth-dialog').close();await listProjects();connectStream();}
function wire(){
 const onProjectChange=caught(async()=>{
  const val=$('project-select').value;
  if(val&&val!==S.pid)await selectProject(val,{navigation:true,syncUrl:true,pushHistory:true});
 });
 $('project-select').onchange=onProjectChange;
 $('project-select').oninput=onProjectChange;
 window.addEventListener('popstate',()=>{
  const urlPid=getUrlProject();
  if(urlPid&&urlPid!==S.pid&&S.projects.some(p=>p.id===urlPid)){
   selectProject(urlPid,{navigation:true,syncUrl:false});
  }
 });
 $('home-button').onclick=e=>{e.preventDefault();S.trail=[];go('@root',{push:false});};$('back-button').onclick=back;$('zoom-in').onclick=()=>map.zoom(1.2);$('zoom-out').onclick=()=>map.zoom(1/1.2);$('fit-button').onclick=$('zoom-label').onclick=()=>map.fit();
 for(const m of ['modules','features'])$('mode-'+m).onclick=()=>{remember();S.mode=m;resetScope();draw(true);};
 $('previous-page').onclick=()=>go(S.scope,{push:false,page:S.page-1});$('next-page').onclick=()=>go(S.scope,{push:false,page:S.page+1});
 $('drawer-close').onclick=closeDrawer;$('history-button').onclick=()=>S.drawer==='history'?closeDrawer():showHistory();$('changes-button').onclick=showChanges;
 $('clear-changes').onclick=()=>{S.before=null;remember();draw();if(S.drawer==='changes')showChanges();};
 $('return-live').onclick=()=>loadGraph({revision:null,navigation:true});
 $('search-open').onclick=showSearch;$('search-input').oninput=()=>{S.searchIndex=0;renderSearch();};$('search-dialog').querySelector('form').onsubmit=e=>{e.preventDefault();if(e.submitter?.classList.contains('key-button'))$('search-dialog').close();else chooseResult(S.searchIndex);};
 $('search-input').onkeydown=e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();S.searchIndex=Math.max(0,Math.min(S.searchResults.length-1,S.searchIndex+(e.key==='ArrowDown'?1:-1)));renderSearch();$('search-results').querySelector('.active')?.scrollIntoView({block:'nearest'});}if(e.key==='Enter'){e.preventDefault();chooseResult(S.searchIndex);}};
 $('more-menu').addEventListener('click',()=>{$('more-menu').hidden=true;$('more-button').setAttribute('aria-expanded','false');});
 $('more-button').onclick=e=>{e.stopPropagation();$('more-menu').hidden=!$('more-menu').hidden;$('more-button').setAttribute('aria-expanded',String(!$('more-menu').hidden));};document.addEventListener('click',e=>{if(!e.target.closest('#more-menu')&&e.target.id!=='more-button')$('more-menu').hidden=true;});
 $('connect-button').onclick=$('empty-connect').onclick=()=>help('connect');$('about-button').onclick=()=>help('about');$('help-close').onclick=()=>$('help-dialog').close();$('demo-change-button').onclick=runExample;
 $('play-button').onclick=()=>window.open('/demo/'+encodeURIComponent(S.pid)+'/index.html','_blank','noopener');
 $('checkpoint-close').onclick=()=>$('checkpoint-dialog').close();$('checkpoint-form').onsubmit=caught(async e=>{e.preventDefault();await api(route('checkpoint'),{name:$('checkpoint-name').value,note:$('checkpoint-note').value,revision:S.graph.revision});$('checkpoint-dialog').close();await loadGraph();toast('Checkpoint saved. All atomic changes are still retained.');});
 $('auth-form').onsubmit=async e=>{e.preventDefault();try{await authenticate($('auth-token').value.trim());}catch(exc){$('auth-error').textContent=exc.message;}};
 $('import-button').onclick=()=>$('import-file').click();$('import-file').onchange=caught(async()=>{const f=$('import-file').files[0];if(!f)return;if(f.size>64*1024*1024)throw Error('Graph data import is limited to 64 MiB.');openBundle(JSON.parse(await f.text()));$('import-file').value='';});$('export-button').onclick=caught(saveExport);
 document.addEventListener('keydown',e=>{if(document.querySelector('dialog[open]')||/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))return;if(e.key==='/'||(e.key.toLowerCase()==='k'&&(e.metaKey||e.ctrlKey))){e.preventDefault();showSearch();}else if(e.key.toLowerCase()==='f'&&!e.metaKey&&!e.ctrlKey){e.preventDefault();map.fit();}else if(e.key==='Backspace'){e.preventDefault();if(S.scope!=='@root')back();}else if(e.key==='Escape'){closeDrawer();$('more-menu').hidden=true;}});
 window.addEventListener('beforeunload',()=>S.stream?.close());
}
async function boot(){wire();try{const embedded=$('threadline-data');if(embedded){openBundle(JSON.parse(embedded.textContent));return;}const hashToken=new URLSearchParams(location.hash.slice(1)).get('token');const token=hashToken||getStoredToken();if(token)await authenticate(token);else{await listProjects();connectStream();}}catch(e){error(e.message);drawEmpty();}
 // Fallback reconciles a dropped event channel; it does not replace the genuine SSE stream.
 setInterval(async()=>{if(S.offline||S.loading||!S.pid)return;try{const r=await api('/api/projects');stateUpdate(r);}catch{if(!S.stream||S.stream.readyState!==1){S.connected=false;connection();}}},7000);
}
boot();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
