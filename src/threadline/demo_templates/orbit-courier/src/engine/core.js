import { blocked } from '../world/map.js';
import { updateCargo } from './cargo.js';

export function createState() {
  return { x:0, y:0, energy:12, carrying:false, won:false, lost:false };
}
export function move(state, direction) {
  if (state.won || state.lost) return state;
  const vectors = { up:[0,-1], down:[0,1], left:[-1,0], right:[1,0] };
  const delta = vectors[direction];
  if (!delta) return state;
  const x = state.x + delta[0], y = state.y + delta[1];
  if (blocked(x,y)) return state;
  state.x=x;state.y=y;state.energy--;
  updateCargo(state);
  if (!state.energy && !state.won) state.lost=true;
  return state;
}
export function statusMessage(state) {
  if (state.won) return 'DELIVERY COMPLETE — The station received its cargo.';
  if (state.lost) return 'OUT OF ENERGY — Reset and choose a shorter route.';
  return state.carrying ? 'Cargo secured. Navigate to the green station.' : 'Find the gold cargo marker.';
}
