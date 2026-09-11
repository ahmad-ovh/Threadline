import { CARGO, STATION } from '../world/map.js';
export function updateCargo(state) {
  if (state.x === CARGO[0] && state.y === CARGO[1]) state.carrying = true;
  if (state.carrying && state.x === STATION[0] && state.y === STATION[1]) state.won = true;
  return state;
}
