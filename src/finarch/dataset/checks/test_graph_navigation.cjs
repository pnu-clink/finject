// Gesture controls: pointer anchoring, fit-sized panning, and ordinary input preservation.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8'),scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match=>match[1]);
for(const script of scripts)new vm.Script(script);
const code=scripts.find(script=>script.includes('function bindGraphNavigation('));
assert(code,'The viewer must contain the graph navigation implementation');
const ctx=vm.createContext({setTimeout:()=>{}});
vm.runInContext(code.slice(code.indexOf('function bindGraphNavigation('),code.indexOf('function graphNavigationHint(')),ctx);
ctx.bindGraphNavigation.keysReady=true;
function fixture(){
 const handlers={},classes=new Set();let scale=1,captured=null;
 const wrap={clientWidth:600,clientHeight:400,scrollLeft:0,scrollTop:0,tabIndex:-1,
  classList:{add:c=>classes.add(c),remove:c=>classes.delete(c)},setAttribute(){},
  addEventListener(type,fn){(handlers[type]??=[]).push(fn)},
  getBoundingClientRect:()=>({left:100,top:50}),
  setPointerCapture:id=>captured=id,hasPointerCapture:id=>captured===id,releasePointerCapture:()=>{captured=null}};
 const svg={style:{marginTop:'0'},getBoundingClientRect(){
  const xy=(this.style.transform||'translate(0px, 0px)').match(/-?[\d.]+/g).map(Number);
  return {left:100+xy[0]-wrap.scrollLeft,top:50+xy[1]+Number.parseFloat(this.style.marginTop)-wrap.scrollTop};
 }};
 const nav=ctx.bindGraphNavigation(wrap,svg,()=>scale,v=>{scale=Math.max(.1,Math.min(3,v));svg.style.marginTop=Math.max(0,(400-300*scale)/2)+'px'});
 function send(type,props={}){const e={pointerId:1,button:0,deltaMode:0,clientX:300,clientY:200,preventDefault(){this.prevented=true},stopPropagation(){},stopImmediatePropagation(){this.stopped=true},...props};for(const fn of handlers[type]||[])fn(e);return e;}
 return {wrap,svg,nav,send,classes,scale:()=>scale,captured:()=>captured};
}
let count=0;function check(fn){fn();count++;}
check(()=>{const f=fixture();assert.ok(!f.send('wheel',{deltaY:100}).prevented);assert.equal(f.scale(),1);});
check(()=>{const f=fixture(),before=f.svg.getBoundingClientRect();const x=(300-before.left)/f.scale(),y=(200-before.top)/f.scale();assert.ok(f.send('wheel',{metaKey:true,deltaY:-180}).prevented);const after=f.svg.getBoundingClientRect();assert.ok(f.scale()>1);assert.ok(Math.abs((300-after.left)/f.scale()-x)<1e-8);assert.ok(Math.abs((200-after.top)/f.scale()-y)<1e-8);});
check(()=>{const f=fixture();for(let i=0;i<30;i++)f.send('wheel',{metaKey:true,deltaY:-800});assert.equal(f.scale(),3);for(let i=0;i<40;i++)f.send('wheel',{metaKey:true,deltaY:800});assert.equal(f.scale(),.1);});
check(()=>{const f=fixture();f.send('pointerdown',{altKey:true});f.send('pointermove',{altKey:true,clientX:345,clientY:175});assert.equal(f.svg.style.transform,'translate(45px, -25px)');assert.ok(f.classes.has('graph-panning'));f.send('pointerup');assert.equal(f.captured(),null);assert.ok(f.send('click').stopped);assert.ok(!f.send('click').stopped);});
check(()=>{const f=fixture();f.send('pointerdown');f.send('pointermove',{clientX:390});assert.equal(f.svg.style.transform,undefined);assert.ok(!f.send('click').stopped);});
check(()=>{const f=fixture();f.send('pointerdown',{altKey:true});f.send('pointermove',{altKey:true,clientX:330});f.send('pointercancel');assert.equal(f.captured(),null);assert.ok(!f.classes.has('graph-panning'));f.nav.resetPan();assert.equal(f.svg.style.transform,'translate(0px, 0px)');assert.equal(f.wrap.scrollLeft,0);});
check(()=>{const f=fixture();f.send('pointerdown',{altKey:true});f.send('pointermove',{altKey:false,clientX:380});assert.equal(f.captured(),null);assert.equal(f.svg.style.transform,undefined);});
check(()=>{const f=fixture();f.send('pointerdown',{altKey:true});f.send('graph-pan-cancel');assert.equal(f.captured(),null);assert.ok(!f.send('click').stopped);});
console.log(`graph navigation: ${count} checks PASS; no browser/model calls`);
