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
check(()=>{elements.none.click();assert.equal(elements.rows.children.length,1);assert.match(elements.rows.textContent,/조건에 맞는 항목이 없습니다/)});
check(()=>{elements.all.click();assert.equal(elements.rows.children.length,9)});
check(()=>{const cb=elements.filters.querySelectorAll('input').find(n=>n.dataset.field==='axis'&&n.value==='IC_SOURCE');cb.checked=false;cb.onchange();assert.equal(elements.rows.children.length,5)});
check(()=>{elements.search.value='EA';elements.search.oninput();assert.equal(elements.rows.children.length,1)});
check(()=>{elements.detail.querySelectorAll('button').find(b=>b.textContent==='4 그래프 변경').click();assert.match(elements.detail.textContent,/원가 근거 삭제/)});
check(()=>{elements.detail.querySelectorAll('button').find(b=>b.textContent==='5 문장과 답변').click();assert.match(elements.detail.textContent,/아직 응답 기록이 없습니다/);assert.match(elements.detail.textContent,/매출원가는 80/)});
check(()=>{elements.detail.querySelectorAll('button').find(b=>b.textContent==='6 사람 판정').click();assert.equal(elements.detail.querySelectorAll('button').find(b=>b.textContent==='승인 기록').disabled,true)});
check(()=>{elements.search.value='';elements.all.click();elements.detail.querySelectorAll('button').find(b=>b.textContent==='2 계산과 정답').click();assert.match(elements.detail.textContent,/100\/3/)});
check(()=>{const value=vm.runInContext(`marked('😀가나다',[{start:2,end:3,text:'X'}],'after').textContent`,context);assert.equal(value,'😀가X다')});
check(()=>{const value=vm.runInContext(`marked('😀가나다',[{start:2,end:3,text:'X'}],'before').textContent`,context);assert.equal(value,'😀가나다')});
check(()=>assert.equal(alerts.length,0));
console.log(JSON.stringify({checks,passed:checks,browser_rendered:false,scope:'Offline filter/tab/Unicode logic only'}));
