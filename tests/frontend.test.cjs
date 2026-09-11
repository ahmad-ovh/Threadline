const test=require('node:test');const assert=require('node:assert/strict');
const G=require('../src/threadline/web/graph.js');
function graph(){return {schemaVersion:'1.0',project:{id:'test',name:'Test'},source:{treeHash:'x'},nodes:[
{id:'root',kind:'module',label:'.',path:'.'},
{id:'m:src',kind:'module',label:'src',path:'src',parent:'root'},
{id:'m:core',kind:'module',label:'core',path:'src/core',parent:'m:src'},
{id:'m:ui',kind:'module',label:'ui',path:'src/ui',parent:'m:src'},
{id:'f:a',kind:'file',label:'a.js',path:'src/core/a.js',parent:'m:core',hash:'old'},
{id:'f:b',kind:'file',label:'b.js',path:'src/core/b.js',parent:'m:core'},
{id:'f:c',kind:'file',label:'c.js',path:'src/ui/c.js',parent:'m:ui'},
{id:'s:a',kind:'symbol',label:'meaning',parent:'f:a',path:'src/core/a.js'},
{id:'feature:f',kind:'feature',label:'Remember',files:['src/core/a.js','src/ui/c.js'],status:'interpretation'}],edges:[
{id:'e1',source:'f:c',target:'f:a',kind:'imports',evidence:[]},
{id:'e2',source:'f:a',target:'f:b',kind:'imports',evidence:[]},
{id:'e3',source:'feature:f',target:'f:a',kind:'implements',evidence:[]},
{id:'e4',source:'feature:f',target:'f:c',kind:'implements',evidence:[]},
{id:'e5',source:'root',target:'m:src',kind:'contains'},
{id:'e6',source:'f:a',target:'s:a',kind:'declares'}]};}
const clone=g=>JSON.parse(JSON.stringify(g));
test('overview flattens empty source wrapper, never dumps every file',()=>{const g=graph(),v=G.project(g);assert.deepEqual(v.nodes.map(n=>n.id),['m:core','m:ui']);assert.equal(v.edges.length,1);assert.equal(g.nodes.length,9);});
test('single scope entry reveals its children and surrounding references',()=>{const v=G.project(graph(),{scope:'m:core'});assert(v.nodes.some(n=>n.id==='f:a'&&!n.context));assert(v.nodes.some(n=>n.id==='m:ui'&&n.context));assert(!v.nodes.some(n=>n.kind==='symbol'));assert.equal(v.edges.length,2);});
test('no separate expansion-state machinery is necessary',()=>{const v=G.frontier(graph(),'m:core');assert.deepEqual(v.map(n=>n.id),['f:a','f:b']);});
test('feature overview links interpretations to source modules',()=>{const v=G.project(graph(),{mode:'features'});assert.equal(v.nodes.length,3);assert.equal(v.edges.length,2);assert(v.edges.every(e=>e.semantic));});
test('feature entry reveals supporting files',()=>{const v=G.project(graph(),{mode:'features',scope:'feature:f'});assert(v.nodes.some(n=>n.id==='f:a'));assert(v.nodes.some(n=>n.id==='f:c'));});
test('root files group remains navigable',()=>{const g=graph();g.nodes.push({id:'entry',kind:'file',label:'index.html',path:'index.html',parent:'root'});assert(G.project(g).nodes.some(n=>n.id==='@rootfiles'));assert.deepEqual(G.frontier(g,'@rootfiles').map(n=>n.id),['entry']);});
test('publisher graphs do not require an invented conventional root',()=>{const g=graph();g.nodes=g.nodes.filter(n=>!['root','m:src'].includes(n.id));g.nodes.filter(n=>n.kind==='module').forEach(n=>delete n.parent);g.edges=g.edges.filter(e=>e.id!=='e5');assert.equal(G.project(g).nodes.length,2);});
test('changed source highlights its visible component',()=>{const a=graph(),b=clone(a);b.nodes.find(n=>n.id==='f:a').hash='new';const v=G.project(b,{before:a});assert.equal(v.nodes.find(n=>n.id==='m:core').state,'changed');assert.equal(v.nodes.find(n=>n.id==='m:core').counts.changed,1);});
test('new source is green inside its module',()=>{const a=graph(),b=clone(a);b.nodes.push({id:'f:d',kind:'file',label:'d.js',parent:'m:core'});assert.equal(G.project(b,{before:a,scope:'m:core'}).nodes.find(n=>n.id==='f:d').state,'added');});
test('removed files remain presentation ghosts, not persisted graph nodes',()=>{const a=graph(),b=clone(a);b.nodes=b.nodes.filter(n=>n.id!=='f:b');b.edges=b.edges.filter(e=>e.target!=='f:b');const v=G.project(b,{before:a,scope:'m:core'});assert.equal(v.nodes.find(n=>n.id==='f:b').state,'removed');assert(!b.nodes.some(n=>n.id==='f:b'));assert.equal(v.edges.find(e=>e.state==='removed').members[0].target,'f:b');});
test('removed modules can still reveal their former children',()=>{const a=graph(),b=clone(a);b.nodes=b.nodes.filter(n=>!['m:ui','f:c'].includes(n.id));b.edges=b.edges.filter(e=>!['f:c','m:ui'].includes(e.source)&&!['f:c','m:ui'].includes(e.target));const v=G.project(b,{before:a,scope:'m:ui'});assert.equal(v.nodes.find(n=>n.id==='f:c').state,'removed');});
test('dismissing visual changes clears ghosts but not source data',()=>{const a=graph(),b=clone(a);b.nodes=b.nodes.filter(n=>n.id!=='f:b');b.edges=b.edges.filter(e=>e.target!=='f:b');assert(!G.project(b,{scope:'m:core'}).nodes.some(n=>n.id==='f:b'));assert(a.nodes.some(n=>n.id==='f:b'));});
test('layout deterministic for cycles and disconnected modules',()=>{const g=graph();g.edges.push({id:'cycle',source:'f:a',target:'f:c',kind:'imports'});const v=G.project(g);assert.deepEqual(G.layout(v),G.layout(v));assert.equal(G.layout(v).size,2);});
test('new nodes do not move any retained node position',()=>{const a=graph(),pa=G.project(a,{scope:'m:core'}),positions=G.layout(pa),b=clone(a);b.nodes.push({id:'f:new',kind:'file',label:'new',parent:'m:core'});b.edges.push({id:'enew',source:'f:b',target:'f:new',kind:'imports'});const next=G.layout(G.project(b,{scope:'m:core'}),positions);for(const [id,pos] of positions)assert.deepEqual(next.get(id),pos);});
test('user-arranged positions survive graph revisions',()=>{const v=G.project(graph()),p=G.layout(v);p.set('m:core',{x:834,y:617});assert.deepEqual(G.layout(v,p).get('m:core'),{x:834,y:617});});
test('new layout does not overlap its node boxes',()=>{const v=G.project(graph(),{scope:'m:core'}),p=[...G.layout(v).values()];for(let i=0;i<p.length;i++)for(let j=i+1;j<p.length;j++)assert(Math.abs(p[i].x-p[j].x)>=G.W||Math.abs(p[i].y-p[j].y)>=G.H);});
test('revision and checkpoint metadata never becomes architecture nodes',()=>{const g=graph(),baseline=G.project(g).nodes.map(n=>n.id);for(let r=1;r<=100;r++){g.revision=r;g.checkpoints=[{revision:r}];assert.deepEqual(G.project(g).nodes.map(n=>n.id),baseline);}});
test('diff retains both old and new metadata and ignores object-key order',()=>{const a=graph(),b=clone(a);b.nodes[4].label='New';assert.equal(G.diff(a,b).nodes.changed[0].before.label,'a.js');const c=clone(a);c.nodes[4]=Object.fromEntries(Object.entries(c.nodes[4]).reverse());assert.equal(G.diff(a,c).nodes.changed.length,0);});
test('missing endpoints, duplicate IDs and cycles fail before render',()=>{let g=graph();g.edges[0].target='absent';assert.throws(()=>G.validate(g),/relationship/);g=graph();g.nodes.push(g.nodes[0]);assert.throws(()=>G.validate(g),/duplicate/);g=graph();g.nodes[0].parent='m:src';assert.throws(()=>G.validate(g),/cycle/);});
test('empty graph is safe',()=>{const g=graph();g.nodes=[];g.edges=[];assert.equal(G.layout(G.project(g)).size,0);});
test('large scope uses explicit, navigable pages',()=>{const g={...graph(),nodes:[],edges:[]};for(let i=0;i<130;i++)g.nodes.push({id:'m'+i,kind:'module',label:'m'+i});const a=G.project(g),b=G.project(g,{page:1});assert.equal(a.nodes.length,30);assert.equal(a.hidden,100);assert(!b.nodes.some(n=>a.nodes.some(m=>m.id===n.id)));});
test('source counts ignore incidental declaration and edge churn',()=>{const a=graph(),b=clone(a);b.nodes[4].hash='x';b.nodes[7].label='new declaration';const d=G.diff(a,b);assert.deepEqual(G.fileCounts(d),{added:0,changed:1,removed:0});});
test('symbol lookup resolves to its containing architecture scope',()=>{assert.equal(G.sourceScope(graph(),'s:a'),'m:core');});
test('file contents cannot invent an edge absent from the published graph',()=>{const g=graph();g.nodes[4].summary='Calls every module in the application.';assert.equal(G.project(g).edges.length,1);});
test('edge-only evidence updates do not falsely mark destination source edited',()=>{const a=graph(),b=clone(a);b.edges[0].evidence=[{path:'src/ui/c.js',line:7}];const v=G.project(b,{before:a});assert.equal(v.nodes.find(n=>n.id==='m:core').state,'');assert.equal(v.edges[0].state,'changed');});

test('feature overview also bounds connected context and reports omitted links',()=>{const g={schemaVersion:'1.0',project:{id:'t',name:'t'},nodes:[{id:'feature:f',kind:'feature',label:'Cross-cutting'}],edges:[]};for(let i=0;i<40;i++){g.nodes.push({id:'m'+i,kind:'module',label:'component'+i},{id:'f'+i,kind:'file',label:'file'+i,parent:'m'+i});g.edges.push({id:'e'+i,kind:'implements',source:'feature:f',target:'f'+i});}const v=G.project(g,{mode:'features'});assert.equal(v.nodes.length,9);assert.equal(v.hiddenRelations,32);});
