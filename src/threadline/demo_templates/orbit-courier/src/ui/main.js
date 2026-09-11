import { createState, move, statusMessage } from '../engine/core.js';
import { drawBoard } from './board.js';
let state=createState();
function render(){
  document.getElementById('stats').textContent=`Energy ${state.energy}/12 · Cargo ${state.carrying?'ON BOARD':'NOT COLLECTED'}`;
  document.getElementById('status').textContent=statusMessage(state);
  drawBoard(document.getElementById('board'),state);
}
function step(direction){move(state,direction);render();}
document.querySelectorAll('[data-move]').forEach(b=>b.addEventListener('click',()=>step(b.dataset.move)));
document.getElementById('reset').addEventListener('click',()=>{state=createState();render();});
document.addEventListener('keydown',e=>{const key={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'}[e.key];if(key){e.preventDefault();step(key);}});
render();
