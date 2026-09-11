export function drawHarbor(canvas, repaired, granted) {
  const c = canvas.getContext('2d');
  c.clearRect(0,0,880,250);
  c.fillStyle='#0c2226'; c.fillRect(0,0,880,250);
  for(let i=0;i<50;i++){c.fillStyle=i%2?'#b3cda7':'#476f69';c.fillRect((i*149)%870,15+(i*47)%110,2,2);}
  c.fillStyle='#d8dfb1';c.beginPath();c.arc(730,45,19,0,Math.PI*2);c.fill();
  c.fillStyle='#164047';c.fillRect(0,155,880,95);
  for(let i=0;i<24;i++){c.strokeStyle='#28575b';c.beginPath();c.moveTo((i*123)%880,168+(i*29)%75);c.lineTo((i*123)%880+40,168+(i*29)%75);c.stroke();}
  c.fillStyle='#3b5143';c.fillRect(90,154,420,12);
  c.fillRect(120,164,10,60);c.fillRect(370,164,10,70);
  c.fillStyle='#172f2e';c.fillRect(185,80,80,75);c.fillStyle='#436853';c.beginPath();c.moveTo(170,80);c.lineTo(225,40);c.lineTo(280,80);c.fill();
  c.fillStyle=repaired?'#f2dc85':'#556247'; c.fillRect(223,105,19,26);
  if(repaired){c.fillStyle='#c9d98522';c.beginPath();c.arc(232,119,67,0,Math.PI*2);c.fill();}
  c.fillStyle='#bed3b3';c.beginPath();c.arc(327,127,8,0,Math.PI*2);c.fill();c.fillRect(320,135,14,19);
  const bx=granted?650:485;c.fillStyle='#ad8b60';c.beginPath();c.moveTo(bx,183);c.lineTo(bx+110,183);c.lineTo(bx+80,202);c.lineTo(bx+25,202);c.fill();
  c.strokeStyle='#ceb997';c.beginPath();c.moveTo(bx+50,183);c.lineTo(bx+50,118);c.stroke();
  c.fillStyle='#cee0bc';c.beginPath();c.moveTo(bx+53,123);c.lineTo(bx+90,177);c.lineTo(bx+53,177);c.fill();
}
