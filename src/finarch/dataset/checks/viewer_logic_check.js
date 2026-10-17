/* Offline JS logic check with a small in-memory DOM substitute, NOT a browser
   rendering/accessibility test. No sockets, browser automation or dependencies. */
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
class Element {
  constructor(tag) { this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.value='';this._text=''; }
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=[...nodes];}
  setAttribute(k,v){this.attributes[k]=String(v);}
  querySelectorAll(selector){let out=[];for(const c of this.children){if(c.tagName===selector)out.push(c);out.push(...c.querySelectorAll(selector));}return out;}
  click(){if(!this.disabled&&this.onclick)this.onclick();}
}
const html=fs.readFileSync(process.argv[2],'utf8');
const payload=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script=html.match(/<script>([\s\S]*?)<\/script><\/body>/)[1];
const elements={};for(const id of ['data','filters','search','rows','detail','count','metrics','notice','all','none'])elements[id]=new Element('div');elements.data.textContent=payload;
const store=new Map(),alerts=[];
const document={getElementById:id=>elements[id],createElement:tag=>new Element(tag),createElementNS:(ns,tag)=>new Element(tag),createTextNode:text=>{let n=new Element('#text');n.textContent=text;return n},querySelectorAll:selector=>{assert.equal(selector,'#filters input');return elements.filters.querySelectorAll('input')}};
const context=vm.createContext({document,console,localStorage:{getItem:key=>store.get(key)||null,setItem:(k,v)=>store.set(k,v)},alert:t=>alerts.push(t),Blob,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},setTimeout:fn=>fn()});
vm.runInContext(script,context);
let checks=0;function check(fn){fn();checks++;}
check(()=>assert.equal(elements.rows.children.length,9));
check(()=>{elements.none.click();assert.equal(elements.rows.children.length,1);assert.match(elements.rows.textContent,/\uc870\uac74\uc5d0 \ub9de\ub294 \ud56d\ubaa9\uc774 \uc5c6\uc2b5\ub2c8\ub2e4/)});
check(()=>{elements.all.click();assert.equal(elements.rows.children.length,9)});
check(()=>{const cb=elements.filters.querySelectorAll('input').find(n=>n.dataset.field==='axis'&&n.value==='IC_SOURCE');cb.checked=false;cb.onchange();assert.equal(elements.rows.children.length,5)});
check(()=>{elements.search.value='EA';elements.search.oninput();assert.equal(elements.rows.children.length,1)});
check(()=>{elements.detail.querySelectorAll('button').find(b=>b.textContent==='4 \uadf8\ub798\ud504 \ubcc0\uacbd').click();assert.match(elements.detail.textContent,/\uc6d0\uac00 \uadfc\uac70 \uc0ad\uc81c/)});
check(()=>{elements.detail.querySelectorAll('button').find(b=>b.textContent==='5 \ubb38\uc7a5\uacfc \ub2f5\ubcc0').click();assert.match(elements.detail.textContent,/\uc544\uc9c1 \uc751\ub2f5 \uae30\ub85d\uc774 \uc5c6\uc2b5\ub2c8\ub2e4/);assert.match(elements.detail.textContent,/\ub9e4\ucd9c\uc6d0\uac00\ub294 80/)});
check(()=>{elements.detail.querySelectorAll('button').find(b=>b.textContent==='6 \uc0ac\ub78c \ud310\uc815').click();assert.equal(elements.detail.querySelectorAll('button').find(b=>b.textContent==='\uc2b9\uc778 \uae30\ub85d').disabled,true)});
check(()=>{elements.search.value='';elements.all.click();elements.detail.querySelectorAll('button').find(b=>b.textContent==='2 \uacc4\uc0b0\uacfc \uc815\ub2f5').click();assert.match(elements.detail.textContent,/100\/3/)});
check(()=>{const value=vm.runInContext(`marked('😀\uac00\ub098\ub2e4',[{start:2,end:3,text:'X'}],'after').textContent`,context);assert.equal(value,'😀\uac00X\ub2e4')});
check(()=>{const value=vm.runInContext(`marked('😀\uac00\ub098\ub2e4',[{start:2,end:3,text:'X'}],'before').textContent`,context);assert.equal(value,'😀\uac00\ub098\ub2e4')});
check(()=>assert.equal(alerts.length,0));
console.log(JSON.stringify({checks,passed:checks,browser_rendered:false,scope:'Offline filter/tab/Unicode logic only'}));
