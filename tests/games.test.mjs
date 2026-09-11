import test from 'node:test';
import assert from 'node:assert/strict';
import { createMemory, remember } from '../src/threadline/demo_templates/lantern-harbor/src/domain/memory.js';
import { canGrantPassage } from '../src/threadline/demo_templates/lantern-harbor/src/domain/rules.js';
import { respond } from '../src/threadline/demo_templates/lantern-harbor/src/narrative/dialogue.js';
import { createState, move, statusMessage } from '../src/threadline/demo_templates/orbit-courier/src/engine/core.js';

test('Lantern Harbor has a reachable complete outcome',()=>{const m=createMemory();assert(!canGrantPassage(m));respond(m,'introduce');respond(m,'repair');assert.match(respond(m,'request'),/Safe passage/);assert(m.granted);});
test('Lantern Harbor rejects requesting passage without required actions',()=>{const m=createMemory();respond(m,'request');assert(!m.granted);respond(m,'repair');respond(m,'request');assert(!m.granted);});
test('remembered actions are idempotent',()=>{const m=createMemory();remember(m,'repair');remember(m,'repair');assert.equal(m.trust,2);assert.equal(m.events.length,1);});
test('Lantern Harbor reset creates independent state',()=>{const m=createMemory();remember(m,'repair');const other=createMemory();assert.equal(other.trust,0);assert.equal(other.events.length,0);});
test('Orbit Courier has a reachable complete delivery',()=>{const s=createState();for(const d of ['right','right','down','right','right','right','down','down','down'])move(s,d);assert(s.won);assert(s.carrying);assert.equal(s.energy,3);assert.match(statusMessage(s),/DELIVERY COMPLETE/);});
test('blocked moves do not spend energy',()=>{const s=createState();move(s,'left');move(s,'up');assert.equal(s.energy,12);assert.equal(s.x,0);});
test('the station without cargo is not a win',()=>{const s=createState();for(const d of ['right','right','right','right','right','down','down','down','down'])move(s,d);assert(!s.carrying);assert(!s.won);});
test('exhaustion is a reachable losing condition',()=>{const s=createState();for(let i=0;i<6;i++){move(s,'right');move(s,'left');}assert(s.lost);assert.equal(s.energy,0);assert.match(statusMessage(s),/OUT OF ENERGY/);});
test('moves after a terminal outcome do not change state',()=>{const s=createState();s.won=true;const baseline=JSON.stringify(s);move(s,'right');assert.equal(JSON.stringify(s),baseline);});
