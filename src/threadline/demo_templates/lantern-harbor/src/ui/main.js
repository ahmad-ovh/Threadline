import { createMemory } from '../domain/memory.js';
import { respond, explainMemory } from '../narrative/dialogue.js';
import { drawHarbor } from './scene.js';

let memory = createMemory();
const text = (id, value) => { document.getElementById(id).textContent = value; };
function render(action = '') {
  text('dialogue', respond(memory, action));
  text('memory', explainMemory(memory));
  text('stats', `Trust ${memory.trust}/3 · ${memory.events.length} remembered events`);
  text('outcome', memory.granted ? 'PASSAGE GRANTED — You completed Lantern Harbor.' : '');
  document.getElementById('outcome').className = 'win';
  drawHarbor(document.getElementById('scene'), memory.repaired, memory.granted);
}
document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => render(button.dataset.action)));
document.getElementById('reset').addEventListener('click', () => { memory = createMemory(); render(); });
render();
