import { WIDTH, WALLS, CARGO, STATION } from '../world/map.js';
export function drawBoard(canvas, state) {
  const c=canvas.getContext('2d'), size=65, pad=20;
  c.clearRect(0,0,430,430);c.fillStyle='#17213b';c.fillRect(0,0,430,430);
  for(let y=0;y<WIDTH;y++)for(let x=0;x<WIDTH;x++){
    c.strokeStyle='#303e64';c.strokeRect(pad+x*size,pad+y*size,size-4,size-4);
  }
  for(const [x,y] of WALLS){c.fillStyle='#394763';c.fillRect(pad+x*size+8,pad+y*size+8,size-20,size-20);}
  c.fillStyle='#84c9a4';c.fillRect(pad+STATION[0]*size+10,pad+STATION[1]*size+10,40,40);
  if(!state.carrying){c.fillStyle='#e8c56d';c.fillRect(pad+CARGO[0]*size+21,pad+CARGO[1]*size+21,18,18);}
  const x=pad+state.x*size+30,y=pad+state.y*size+30;
  c.fillStyle='#c6c7fb';c.beginPath();c.moveTo(x,y-17);c.lineTo(x+15,y+15);c.lineTo(x,y+8);c.lineTo(x-15,y+15);c.closePath();c.fill();
}
