export const WIDTH = 6;
export const WALLS = [[1,2],[3,2],[4,2],[2,4]];
export const CARGO = [2,1];
export const STATION = [5,4];
export function blocked(x,y) {
  return x < 0 || y < 0 || x >= WIDTH || y >= WIDTH || WALLS.some(([a,b]) => a === x && b === y);
}
