/* Cytoscape owns the graph; HTML cards are a light, accessible rendering overlay.
   Stable positions and the viewport are preserved across accepted source updates. */
(function(root){
'use strict';
const G=root.ThreadlineGraph;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons={module:'<path d="M2 4h4l2 2h6v8H2z"/>',file:'<path d="M4 2h5l3 3v9H4zM9 2v4h3M6 9h4M6 11h3"/>',feature:'<path d="m8 1 2 5 5 2-5 2-2 5-2-5-5-2 5-2z"/>',document:'<path d="M3 2h10v12H3zM5 5h6M5 8h6M5 11h4"/>',suggestion:'<path d="M8 1a5 5 0 0 0-3.5 8.5c.7.7 1.1 1.6 1.2 2.5h4.6c.1-.9.5-1.8 1.2-2.5A5 5 0 0 0 8 1zm-2 13h4M7 15h2"/>'};
function card(n){
 const type=n.kind==='suggestion'?'💡 AI SUGGESTION':n.context?'CONNECTED '+(n.kind==='module'?'MODULE':'FILE'):n.kind==='module'?'COMPONENT':n.kind==='feature'?'FEATURE · INTERPRETED':n.kind==='document'?'DOCUMENT':'SOURCE FILE';
 const icon='<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.15" aria-hidden="true">'+(icons[n.kind]||icons.file)+'</svg>';
 let status=n.kind==='suggestion'?'PROPOSED':n.state==='added'?'+ NEW':n.state==='changed'?'~ UPDATED':n.state==='removed'?'− REMOVED':n.stale?'REVIEW':'';
 let foot=n.kind==='suggestion'?'Pipeline suggestion · click for prompt':n.kind==='module'?`<b>${n.fileCount}</b> file${n.fileCount!==1?'s':''} · ${n.symbolCount} declaration${n.symbolCount!==1?'s':''}`:n.kind==='feature'?n.stale?'Source changed · review mapping':`${n.base.files?.length||0} source links`:`${esc(n.base.language||n.base.analysis||'source')} · ${esc(n.base.lines??'–')} lines`;
 let samples=n.sample||[];if(n.kind==='feature')samples=(n.base.files||[]).map(p=>p.split('/').pop()).slice(0,2);
 if(n.kind==='suggestion')samples=[n.base.target?('targets '+n.base.target.split(':').pop()):'pipeline idea'];
 return `<div class="node-top"><span class="node-type">${icon}${esc(type)}</span>${status?`<span class="node-state">${esc(status)}</span>`:''}</div><div class="node-title"><span>${esc(n.label)}</span></div><div class="node-path">${esc(n.kind==='suggestion'?(n.base.rationale||n.summary||'Proposed pipeline improvement'):n.kind==='feature'?(n.base.description||n.summary||'A feature-to-source interpretation'):n.path||'Project entry points')}</div><div class="node-preview">${samples.map(s=>`<span>${esc(s)}</span>`).join('')}</div><div class="node-footer"><span>${foot}</span><span class="arrow" aria-hidden="true">${n.kind==='suggestion'?'→':n.state==='removed'?'−':n.kind==='module'||n.kind==='feature'?'↗':'↗'}</span></div>`;
}
class GraphMap{
 constructor(options){
  this.o=options;this.layer=options.layer;this.cards=new Map();this.positions=new Map();this.projection=null;this.selected=null;this.frame=0;
  this.cy=cytoscape({container:options.container,elements:[],layout:{name:'preset'},minZoom:.12,maxZoom:2.2,boxSelectionEnabled:false,selectionType:'single',autounselectify:true,hideEdgesOnViewport:false,pixelRatio:Math.min(devicePixelRatio||1,2),style:[
   {selector:'node',style:{width:G.W,height:G.H,shape:'roundrectangle','background-color':'#1c2735','background-opacity':.01,'border-width':0,label:'','overlay-opacity':0}},
   {selector:'edge',style:{width:1.55,'line-color':'#506b8c','target-arrow-color':'#718cab','target-arrow-shape':'triangle','arrow-scale':.8,'curve-style':'bezier','control-point-step-size':55,'line-opacity':.8,'source-endpoint':'outside-to-node','target-endpoint':'outside-to-node',label:'data(caption)','font-size':10,'font-family':'system-ui','font-weight':400,color:'#8ba4c1','text-background-color':'#101419','text-background-opacity':1,'text-background-padding':5,'text-background-shape':'roundrectangle','text-rotation':'none','text-margin-y':-2,'overlay-opacity':0,'text-events':'yes'}},
   {selector:'edge.semantic',style:{'line-style':'dashed','line-color':'#8a7ba5','target-arrow-color':'#9685b9',color:'#ad9bc7'}},
   {selector:'edge.suggests',style:{'line-style':'dashed','line-color':'#6b829e','target-arrow-color':'#7d98b8','target-arrow-shape':'triangle','arrow-scale':.85,'width':1.6,color:'#8ea2bd'}},
   {selector:'edge.added',style:{'line-color':'#84c9a8','target-arrow-color':'#84c9a8',color:'#acd7bb',width:2}},
   {selector:'edge.changed',style:{'line-color':'#c3a16c','target-arrow-color':'#c3a16c',color:'#d4b481',width:2}},
   {selector:'edge.removed',style:{'line-color':'#b5767f','target-arrow-color':'#b5767f',color:'#c88d96','line-style':'dashed',width:1.5}},
   {selector:'edge.dimmed',style:{opacity:.15}},
   {selector:'edge.highlight',style:{width:2.2,'line-opacity':1,'line-color':'#a2beda','target-arrow-color':'#b7d2ee',color:'#c4d7eb','z-index':5}},
  ]});
  this.cy.on('tap','node',evt=>{const n=this.lookup(evt.target.id());if(n)this.o.onNode(n);});
  this.cy.on('tap','edge',evt=>{const e=this.projection?.edges.find(e=>e.id===evt.target.id());if(e)this.o.onEdge(e);});
  this.cy.on('tap',evt=>{if(evt.target===this.cy)this.o.onBackground?.();});
  this.cy.on('mouseover','node',evt=>this.highlight(evt.target.id()));this.cy.on('mouseout','node',()=>this.highlight(null));
  this.cy.on('mouseover','edge',evt=>evt.target.addClass('highlight'));this.cy.on('mouseout','edge',evt=>evt.target.removeClass('highlight'));
  this.cy.on('pan zoom render position',()=>this.schedule());
  this.cy.on('dragfree','node',evt=>{this.routeEdges();this.positions.set(evt.target.id(),{...evt.target.position()});this.o.onPositions?.(new Map(this.positions));});
  this.cy.on('zoom',()=>this.o.onZoom?.(this.cy.zoom()));
  this.observer=new ResizeObserver(()=>{this.cy.resize();this.schedule();});this.observer.observe(options.container);
 }
 lookup(id){return this.projection?.nodes.find(n=>n.id===id);}
 render(projection,positions,{fit=false}={}){
  this.projection=projection;this.positions=positions;const ids=new Set(projection.nodes.map(n=>n.id)),edgeIds=new Set(projection.edges.map(e=>e.id));
  this.cy.batch(()=>{
   this.cy.edges().forEach(e=>{if(!edgeIds.has(e.id()))e.remove();});this.cy.nodes().forEach(n=>{if(!ids.has(n.id()))n.remove();});
   for(const n of projection.nodes){let el=this.cy.getElementById(n.id);const pos=positions.get(n.id)||{x:0,y:0};if(!el.length){el=this.cy.add({group:'nodes',data:{id:n.id},position:{x:pos.x,y:pos.y}});}else el.position({x:pos.x,y:pos.y});if(n.state==='removed')el.ungrabify();else el.grabify();}
   for(const e of projection.edges){const caption=e.semantic?(e.kinds.includes('suggests')?'suggests':e.members.length===1?'maps to':e.members.length+' source links'):(e.members.length===1?e.kinds[0]:e.members.length+' references');let el=this.cy.getElementById(e.id);const data={id:e.id,source:e.source,target:e.target,caption};if(!el.length)el=this.cy.add({group:'edges',data});else el.data(data);el.classes([e.state,e.semantic?'semantic':'',e.kinds.includes('suggests')?'suggests':''].filter(Boolean).join(' '));}
  });
  for(const [id,c] of this.cards)if(!ids.has(id)){c.remove();this.cards.delete(id);}
  for(const n of projection.nodes){let c=this.cards.get(n.id),fresh=!c;if(!c){c=document.createElement('button');c.type='button';c.dataset.node=n.id;c.setAttribute('aria-label',n.kind==='module'||n.kind==='feature'?'Explore '+n.label:'Inspect '+n.label);c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();this.o.onNode(this.lookup(n.id));}});c.addEventListener('focus',()=>this.highlight(n.id));c.addEventListener('blur',()=>this.highlight(null));this.layer.append(c);this.cards.set(n.id,c);}
   c.className='graph-node node-'+n.kind+(n.context?' is-context':'')+(n.state?' state-'+n.state:'')+(n.stale?' is-stale':'')+(fresh?' is-new':'')+(this.selected===n.id?' is-selected':'');c.dataset.state=n.state;c.dataset.kind=n.kind;c.innerHTML=card(n);
  }
  this.routeEdges();this.schedule();if(fit)requestAnimationFrame(()=>this.fit(false));this.o.onZoom?.(this.cy.zoom());
 }
 routeEdges(){
  // Route long-span references around the intervening cards instead of through them.
  this.cy.batch(()=>{for(const edge of this.cy.edges()){
   const a=edge.source().position(),b=edge.target().position(),dx=b.x-a.x,dy=b.y-a.y;
   if(Math.abs(dx)>G.W*2.1){const bend=(Math.abs(dy)<G.H*1.1?-1:dy>0?1:-1)*Math.min(230,Math.abs(dx)*.25);edge.style({'curve-style':'unbundled-bezier','control-point-distances':String(bend)+' '+String(bend),'control-point-weights':'.30 .70'});}
   else if(Math.abs(dx)<G.W*.5&&Math.abs(dy)>G.H){edge.style({'curve-style':'unbundled-bezier','control-point-distances':110,'control-point-weights':'.5'});}
   else edge.style({'curve-style':'bezier','control-point-step-size':55});
  }});
 }
 schedule(){if(!this.frame)this.frame=requestAnimationFrame(()=>{this.frame=0;this.sync();});}
 sync(){const pan=this.cy.pan(),z=this.cy.zoom();this.layer.style.transform=`translate(${pan.x}px,${pan.y}px) scale(${z})`;for(const n of this.cy.nodes()){const c=this.cards.get(n.id());if(!c)continue;const p=n.position();c.style.left=(p.x-G.W/2)+'px';c.style.top=(p.y-G.H/2)+'px';c.dataset.x=String(p.x);c.dataset.y=String(p.y);}}
 highlight(id){const active=id?this.cy.getElementById(id):null;const related=active?.closedNeighborhood();for(const [nid,c] of this.cards){c.classList.toggle('is-hover',nid===id);c.classList.toggle('is-dim',!!id&&!related?.some(n=>n.id()===nid));}this.cy.edges().forEach(e=>{e.toggleClass('dimmed',!!id&&!related?.some(n=>n.id()===e.id()));e.toggleClass('highlight',!!id&&(e.source().id()===id||e.target().id()===id));});}
 select(id){this.selected=id;for(const [nid,c] of this.cards)c.classList.toggle('is-selected',nid===id);}
 fit(animate=true){if(!this.cy.nodes().length)return;this.cy.resize();const bb=this.cy.nodes().boundingBox({includeLabels:false}),w=this.cy.width(),h=this.cy.height();const top=166,bottom=110,pad=55;const z=Math.max(.12,Math.min(1.08,(w-pad*2)/Math.max(1,bb.w),(h-top-bottom)/Math.max(1,bb.h)));const pan={x:(w-bb.w*z)/2-bb.x1*z,y:top+(h-top-bottom-bb.h*z)/2-bb.y1*z};this.cy.stop();if(animate&&!matchMedia('(prefers-reduced-motion: reduce)').matches)this.cy.animate({zoom:z,pan},{duration:230});else{this.cy.zoom(z);this.cy.pan(pan);}this.schedule();}
 reveal(id){
  const n=this.cy.getElementById(id);if(!n.length)return;this.cy.resize();const p=n.renderedPosition(),z=this.cy.zoom(),w=this.cy.width(),h=this.cy.height();const halfX=G.W*z/2,halfY=G.H*z/2;
  const dx=p.x+halfX>w-24?w-24-(p.x+halfX):p.x-halfX<24?24-(p.x-halfX):0;
  const dy=p.y+halfY>h-92?h-92-(p.y+halfY):p.y-halfY<162?162-(p.y-halfY):0;
  if(dx||dy)this.cy.panBy({x:dx,y:dy});
 }
 zoom(factor){const pos={x:this.cy.width()/2,y:this.cy.height()/2};this.cy.zoom({level:this.cy.zoom()*factor,renderedPosition:pos});}
 viewport(){return {zoom:this.cy.zoom(),pan:{...this.cy.pan()}};}
 restore(v){if(v){this.cy.zoom(v.zoom);this.cy.pan({...v.pan});this.schedule();}}
 destroy(){this.observer.disconnect();this.cy.destroy();}
}
root.ThreadlineMap=GraphMap;
})(window);
