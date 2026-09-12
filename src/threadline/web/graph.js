/* Threadline 2: pure, source-independent graph projection and stable layout. MIT. */
(function(root){
'use strict';
const FILES=new Set(['file','document']), STRUCTURE=new Set(['contains','declares']);
const WRAPPERS=new Set(['src','source','lib','app']);
const W=252,H=156,GX=128,GY=64;
const cmp=(a,b)=>a.localeCompare(b,undefined,{numeric:true});
const stable=x=>{if(Array.isArray(x))return '['+x.map(stable).join(',')+']';if(x&&typeof x==='object')return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+stable(x[k])).join(',')+'}';return JSON.stringify(x);};
function validate(g){
 if(!g||g.schemaVersion!=='1.0'||!g.project||!Array.isArray(g.nodes)||!Array.isArray(g.edges))throw Error('Expected a Threadline schema 1.0 graph.');
 if(g.nodes.length>20000||g.edges.length>100000)throw Error('Graph exceeds the display safety limit.');
 const ids=new Set(),es=new Set(),parents=new Map();
 for(const n of g.nodes){if(!n||typeof n.id!=='string'||typeof n.label!=='string'||ids.has(n.id))throw Error('Missing or duplicate node ID.');ids.add(n.id);if(n.parent)parents.set(n.id,n.parent);}
 for(const [id,parent] of parents){if(!ids.has(parent))throw Error('Missing parent.');const seen=new Set([id]);let p=parent;while(p){if(seen.has(p))throw Error('Parent cycle.');seen.add(p);p=parents.get(p);}}
 for(const e of g.edges){if(!e||typeof e.id!=='string'||es.has(e.id)||!ids.has(e.source)||!ids.has(e.target))throw Error('Invalid relationship.');es.add(e.id);}
 return g;
}
function index(g){
 const nodes=new Map(g.nodes.map(n=>[n.id,n])),children=new Map();
 for(const n of g.nodes){const p=n.parent||'';if(!children.has(p))children.set(p,[]);children.get(p).push(n);}
 for(const v of children.values())v.sort((a,b)=>(a.kind==='module'?0:1)-(b.kind==='module'?0:1)||cmp(a.path||a.label,b.path||b.label));
 const descendants=id=>{const out=[],stack=[id],seen=new Set();while(stack.length){const p=stack.pop();if(seen.has(p))continue;seen.add(p);if(nodes.has(p))out.push(nodes.get(p));for(const n of children.get(p)||[])stack.push(n.id);}return out;};
 return {nodes,children,descendants};
}
function diff(before,after){const out={};for(const group of ['nodes','edges']){const a=new Map((before?.[group]||[]).map(n=>[n.id,n])),b=new Map(after[group].map(n=>[n.id,n]));out[group]={added:[...b.values()].filter(n=>!a.has(n.id)),removed:[...a.values()].filter(n=>!b.has(n.id)),changed:[...b.values()].filter(n=>a.has(n.id)&&stable(a.get(n.id))!==stable(n)).map(n=>({before:a.get(n.id),after:n}))};}return out;}
function changeMap(delta,group='nodes'){const m=new Map();if(!delta)return m;for(const n of delta[group].added)m.set(n.id,'added');for(const n of delta[group].removed)m.set(n.id,'removed');for(const n of delta[group].changed)m.set(n.after.id,'changed');return m;}
function overlay(graph,before){if(!before)return {graph,delta:null};const delta=diff(before,graph);return {graph:{...graph,nodes:[...graph.nodes,...delta.nodes.removed],edges:[...graph.edges,...delta.edges.removed]},delta};}
function label(n){if(n.id==='@rootfiles')return 'Entry & assets';if(n.kind==='module')return (n.path||n.label).split('/').pop()==='.'?'Project files':(n.path||n.label).split('/').pop();return n.label;}
function frontier(g,scope='@root',mode='modules'){
 const idx=index(g),{nodes,children}=idx;const rootNode=g.nodes.find(n=>n.kind==='module'&&(n.path==='.'||n.id==='module:.'));
 const rootId=rootNode?.id;
 const top=children.get(rootId||'')||[];
 const rootFiles=top.filter(n=>FILES.has(n.kind));
 const rootFilesNode={id:'@rootfiles',kind:'module',label:'Entry & assets',path:'.',synthetic:true,memberIds:rootFiles.map(n=>n.id)};
 if(scope==='@rootfiles')return rootFiles;
 if(mode==='features'&&scope==='@root')return g.nodes.filter(n=>n.kind==='feature'||n.kind==='suggestion').sort((a,b)=>(a.kind==='suggestion'?1:0)-(b.kind==='suggestion'?1:0)||cmp(a.label,b.label));
 const scoped=nodes.get(scope);
 if(scoped?.kind==='feature'){
   const ids=new Set(g.edges.filter(e=>e.source===scope&&e.kind==='implements').map(e=>e.target));
   for(const path of scoped.files||[])for(const n of g.nodes)if(n.path===path&&FILES.has(n.kind))ids.add(n.id);
   return [...ids].map(id=>nodes.get(id)).filter(Boolean).map(n=>n.kind==='symbol'&&nodes.has(n.parent)?nodes.get(n.parent):n).filter((n,i,a)=>a.findIndex(x=>x.id===n.id)===i).sort((a,b)=>cmp(a.path||a.label,b.path||b.label));
 }
 if(scoped)return (children.get(scope)||[]).filter(n=>n.kind!=='symbol'&&n.kind!=='feature'&&n.kind!=='suggestion');
 const out=[];
 function unwrap(n,depth=0){const ch=(children.get(n.id)||[]).filter(n=>n.kind!=='symbol'&&n.kind!=='suggestion');if(n.kind==='module'&&WRAPPERS.has(label(n))&&ch.length&&ch.every(x=>x.kind==='module')&&depth<4){ch.forEach(c=>unwrap(c,depth+1));}else out.push(n);}
 top.filter(n=>n.kind==='module').forEach(n=>unwrap(n));
 if(rootFiles.length)out.unshift(rootFilesNode);
 // A publisher can supply unparented files or modules, without a conventional root.
 if(!out.length)for(const n of g.nodes)if(!n.parent&&n.kind!=='feature'&&n.kind!=='suggestion'&&n.id!==rootId)out.push(n);
 return out;
}
function project(input,options={}){
 validate(input);const {graph:g,delta}=overlay(input,options.before),idx=index(g),{nodes,children,descendants}=idx;
 const changes=changeMap(delta),edgeChanges=changeMap(delta,'edges');
 const mode=options.mode||'modules',scope=options.scope||'@root',limit=options.limit||30,page=options.page||0;
 const all=frontier(g,scope,mode),display=all.slice(page*limit,(page+1)*limit),visible=new Map(),owner=new Map();
 function members(n){if(n.id==='@rootfiles')return n.memberIds.flatMap(id=>descendants(id));return descendants(n.id);}
 function add(n,context=false){if(visible.has(n.id))return;const mem=members(n),files=mem.filter(n=>FILES.has(n.kind)),syms=mem.filter(n=>n.kind==='symbol');
   const counts={added:0,changed:0,removed:0};for(const f of files){const change=changes.get(f.id);if(change)counts[change]++;}
   let state=changes.get(n.id)||'';if(!state&&Object.values(counts).some(Boolean))state='changed';
   const memberSet=new Set(mem.map(n=>n.id));const incoming=g.edges.filter(e=>!STRUCTURE.has(e.kind)&&memberSet.has(e.target)&&!memberSet.has(e.source)).length;
   const sample=(n.kind==='module'?files:syms).slice().sort((a,b)=>cmp(a.path||a.label,b.path||b.label)).slice(0,2).map(n=>n.label);
   visible.set(n.id,{id:n.id,label:label(n),path:n.path||'',kind:n.kind,base:n,context,members:mem.map(n=>n.id),fileCount:files.length,symbolCount:syms.length,counts,state,stale:n.status==='stale',sample,incoming,summary:n.summary||'',rationale:n.rationale||'',target:n.target||'',prompt:n.prompt||'',w:W,h:H});
   for(const m of mem)if(!owner.has(m.id))owner.set(m.id,n.id);
   if(!owner.has(n.id))owner.set(n.id,n.id);
 }
 display.forEach(n=>add(n));
 // Feature overview uses interpretation links to architectural modules, not a hairball of files.
 if(mode==='features'&&scope==='@root'){
   const fset=new Set(display.map(n=>n.id)),targets=new Set(g.edges.filter(e=>fset.has(e.source)&&e.kind==='implements').map(e=>e.target));
   const candidates=new Map();
   for(const id of targets){let n=nodes.get(id);if(!n)continue;if(n.kind==='symbol')n=nodes.get(n.parent)||n;const p=nodes.get(n.parent);
    const target=p?.path==='.'?{id:'@rootfiles',kind:'module',label:'Entry & assets',path:'.',memberIds:(children.get(p.id)||[]).filter(x=>FILES.has(x.kind)).map(x=>x.id)}:(p||n);
    const c=candidates.get(target.id)||{node:target,count:0};c.count++;candidates.set(target.id,c);
   }
   [...candidates.values()].sort((a,b)=>b.count-a.count||cmp(a.node.id,b.node.id)).slice(0,8).forEach(c=>add(c.node,true));
 }
 // Keep a few real external dependencies visible as context when drilling inside a component.
 if(scope!=='@root'){
   const candidates=new Map();
   for(const e of g.edges){if(STRUCTURE.has(e.kind)||e.kind==='implements')continue;const a=owner.has(e.source),b=owner.has(e.target);if(a===b)continue;
     let n=nodes.get(a?e.target:e.source);if(!n)continue;if(n.kind==='symbol')n=nodes.get(n.parent)||n;
     let parent=nodes.get(n.parent);if(parent?.kind==='module'&&parent.id!==scope){if(parent.path==='.')parent={id:'@rootfiles',kind:'module',label:'Entry & assets',path:'.',memberIds:(children.get(parent.id)||[]).filter(x=>FILES.has(x.kind)).map(x=>x.id)};n=parent;}
     if(visible.has(n.id)||n.id===scope)continue;const c=candidates.get(n.id)||{node:n,count:0};c.count++;candidates.set(n.id,c);
   }
   [...candidates.values()].sort((a,b)=>b.count-a.count||cmp(a.node.id,b.node.id)).slice(0,8).forEach(c=>add(c.node,true));
 }
 // Connect AI pipeline suggestions to visible nodes
 const rootId=g.nodes.find(n=>n.kind==='module'&&(n.path==='.'||n.id==='module:.'))?.id;
 const sugNodes=g.nodes.filter(n=>n.kind==='suggestion');
 for(const sug of sugNodes){
   const targetId=sug.target||'module:.';
   const targetInView=visible.has(targetId)||(scope==='@root'&&(!sug.target||sug.target==='module:.'||sug.target===rootId));
   const targetInScope=(scope!=='@root'&&(targetId===scope||descendants(scope).some(d=>d.id===targetId)));
   if(targetInView||targetInScope){
     add(sug,true);
   }
 }
 const links=new Map();let hiddenRelations=0;
 for(const e of g.edges){if(STRUCTURE.has(e.kind))continue;if(mode!=='features'&&scope==='@root'&&e.kind==='implements')continue;if(mode==='features'&&scope==='@root'&&e.kind!=='implements'&&e.kind!=='suggests')continue;
  const s=owner.get(e.source),t=owner.get(e.target);if(!s||!t){if(s||t)hiddenRelations++;continue;}if(s===t)continue;
  const state=edgeChanges.get(e.id)||'',semantic=e.kind==='implements'||e.kind==='suggests';const key=JSON.stringify([s,t,semantic,state==='removed']);
  if(!links.has(key))links.set(key,{id:'e:'+key,source:s,target:t,members:[],kinds:new Set(),state:'',semantic});const link=links.get(key);link.members.push(e);link.kinds.add(e.kind);if(state==='removed'||state==='added'||(!link.state&&state))link.state=state;
 }
 const edges=[...links.values()].map(e=>({...e,kinds:[...e.kinds]}));
 // Changed references are highlighted on the edges; they do not falsely claim
 // that an unchanged destination's implementation was edited.
 return {nodes:[...visible.values()],edges,links:edges,owner,total:all.length,page,limit,hidden:Math.max(0,all.length-display.length),hiddenRelations,delta,index:idx,scope,mode};
}
function layout(projection,previous=new Map()){
 const ns=projection.nodes,ids=ns.map(n=>n.id),adj=new Map(ids.map(id=>[id,[]]));for(const e of projection.edges)adj.get(e.source)?.push(e.target);
 // Strongly-connected components avoid falsely presenting cyclic code as a tree.
 let seq=0;const indices=new Map(),low=new Map(),stack=[],on=new Set(),components=[];
 function visit(id){indices.set(id,seq);low.set(id,seq++);stack.push(id);on.add(id);for(const next of adj.get(id)||[]){if(!indices.has(next)){visit(next);low.set(id,Math.min(low.get(id),low.get(next)));}else if(on.has(next))low.set(id,Math.min(low.get(id),indices.get(next)));}if(low.get(id)===indices.get(id)){const c=[];let n;do{n=stack.pop();on.delete(n);c.push(n);}while(n!==id);components.push(c.sort(cmp));}}
 ids.forEach(id=>{if(!indices.has(id))visit(id);});const component=new Map();components.forEach((c,i)=>c.forEach(id=>component.set(id,i)));
 const out=components.map(()=>new Set()),degrees=components.map(()=>0),rank=components.map(()=>0);
 for(const e of projection.edges){const a=component.get(e.source),b=component.get(e.target);if(a!==b&&!out[a].has(b)){out[a].add(b);degrees[b]++;}}
 const queue=degrees.map((d,i)=>d===0?i:-1).filter(i=>i>=0);while(queue.length){const a=queue.shift();for(const b of out[a]){rank[b]=Math.max(rank[b],rank[a]+1);if(--degrees[b]===0)queue.push(b);}}
 const columns=new Map();for(const n of ns){const r=rank[component.get(n.id)]||0;if(!columns.has(r))columns.set(r,[]);columns.get(r).push(n);}
 const neighbors=new Map(ids.map(id=>[id,[]]));for(const e of projection.edges){neighbors.get(e.source).push(e.target);neighbors.get(e.target).push(e.source);}
 // Barycentric ordering reduces crossing without a perpetual force simulation.
 const order=new Map();for(const col of columns.values()){col.sort((a,b)=>Number(a.context)-Number(b.context)||cmp(a.id,b.id));col.forEach((n,i)=>order.set(n.id,i));}
 for(let pass=0;pass<4;pass++)for(const [r,col] of [...columns].sort((a,b)=>pass%2?b[0]-a[0]:a[0]-b[0])){
  const score=n=>{const near=neighbors.get(n.id).filter(id=>rank[component.get(id)]!==r);return near.length?near.reduce((s,id)=>s+(order.get(id)||0),0)/near.length:(order.get(n.id)||0);};col.sort((a,b)=>score(a)-score(b)||cmp(a.id,b.id));col.forEach((n,i)=>order.set(n.id,i));
 }
 const ideal=new Map(),maxRows=Math.max(1,...[...columns.values()].map(a=>a.length));for(const [r,col] of columns)col.forEach((n,i)=>ideal.set(n.id,{x:r*(W+GX)+W/2,y:(maxRows-col.length)*(H+GY)/2+i*(H+GY)+H/2}));
 const positions=new Map(),placed=[];for(const n of ns)if(previous.has(n.id)){const p=previous.get(n.id);positions.set(n.id,{x:p.x,y:p.y});placed.push({x:p.x,y:p.y});}
 function free(p){return !placed.some(q=>Math.abs(q.x-p.x)<W+28&&Math.abs(q.y-p.y)<H+30);}
 for(const n of ns)if(!positions.has(n.id)){
  const best=ideal.get(n.id)||{x:0,y:0};let p=best;
  if(positions.size){const near=neighbors.get(n.id).map(id=>positions.get(id)).filter(Boolean);if(near.length&&!previous.size)p=best;}
  // Put a new component into a compact vacant shelf when its ideal rank would
  // push it far outside the existing map. Existing coordinates never change.
  if(previous.size&&placed.length){const old=[...previous.values()],xs=[...new Set(old.map(p=>p.x))],maxX=Math.max(...xs),minX=Math.min(...xs),maxY=Math.max(...old.map(p=>p.y));
   if(p.x>maxX+W/2||p.x<minX-W/2||p.y>maxY+H+GY/2){
    const shelves=xs.map(x=>({x,y:Math.max(...placed.filter(q=>Math.abs(q.x-x)<W).map(q=>q.y))+(H+GY)})).filter(free);
    shelves.sort((a,b)=>a.y-b.y+Math.abs(a.x-best.x)*.02-Math.abs(b.x-best.x)*.02);if(shelves.length)p=shelves[0];
   }
  }
  if(!free(p)){let found=false;for(let d=1;d<=ns.length+2&&!found;d++)for(const dy of [d,-d]){const trial={x:best.x,y:best.y+dy*(H+GY)};if(free(trial)){p=trial;found=true;break;}}}
  positions.set(n.id,p);placed.push(p);
 }
 return positions;
}
function fileCounts(delta){const out={added:0,changed:0,removed:0};if(delta)for(const key of Object.keys(out))out[key]=delta.nodes[key].filter(n=>FILES.has((n.after||n).kind)).length;return out;}
function sourceScope(graph,id){const idx=index(graph);let n=idx.nodes.get(id);if(!n)return '@root';if(n.kind==='suggestion')return '@root';if(n.kind==='module'||n.kind==='feature')return n.id;if(n.kind==='symbol')n=idx.nodes.get(n.parent)||n;const p=idx.nodes.get(n.parent);return p?.path==='.'?'@rootfiles':p?.id||'@root';}
const api={validate,index,diff,changeMap,overlay,label,frontier,project,layout,fileCounts,sourceScope,stable,W,H};root.ThreadlineGraph=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
