// VS03: saved nested JSON/JSONL projection, source fidelity, and popup behavior.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');
new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
class Element {
 constructor(tag){this.tagName=tag;this.children=[];this.attributes={};this.style={};this.events={};this._text='';this.isConnected=true;}
 set textContent(v){this._text=String(v);this.children=[];}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
 prepend(...nodes){for(const n of nodes)n.parent=this;this.children.unshift(...nodes);}
 replaceChildren(...nodes){this._text='';this.children=[];this.append(...nodes);}
 setAttribute(k,v){this.attributes[k]=String(v);}
 addEventListener(k,fn){(this.events[k]??=[]).push(fn);}
 emit(k,event={}){for(const fn of this.events[k]||[])fn(event);}
 click(){if(!this.disabled)return this.onclick?.();}
 focus(){document.activeElement=this;}
 select(){copied=this.value;}
 showModal(){this.open=true;}
 close(){this.open=false;this.emit('close');}
 remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
 getBoundingClientRect(){return {left:20,right:400,top:20,bottom:500};}
}

let copied;
const document={createElement:tag=>new Element(tag),body:new Element('body'),activeElement:null};
const navigator={clipboard:{writeText:async value=>{copied=value;}}};
const ctx=vm.createContext({document,navigator});
vm.runInContext(html.slice(html.indexOf('const text='),html.indexOf('function box(')),ctx);
vm.runInContext(html.slice(html.indexOf('function showSchemaDialog('),html.indexOf('// [VL04]')),ctx);
const all=(root,fn)=>[root,...root.children.flatMap(n=>all(n,()=>true))].filter(fn);
const btn=(root,label)=>all(root,n=>n.tagName==='button'&&n.textContent===label)[0];
const klass=(root,name)=>all(root,n=>(n.className||'').split(' ').includes(name));
const render=raw=>{const root=new Element('div');ctx.renderHumanNode(root,ctx.humanDecode(raw));return root;};
const results=[];
async function check(name,fn){await fn();results.push(name);console.log('PASS '+name);}
(async()=>{
const fixture='reports/run/first-10-pot-validated-v3/test-0001/05-text/stage17-v3/counterexamples/wrong-period/audit/02-raw-response/cli-execution.json';
const raw=fs.readFileSync(fixture,'utf8');
await check('real CLI stdout unfolds seven events and eight findings, two FAIL',()=>{
 const root=render(raw);assert.equal(klass(root,'human-event').length,7);assert.equal(klass(root,'human-finding').length,8);assert.equal(klass(root,'human-finding-fail').length,2);
 assert.match(root.textContent,/실행 정보/);assert.match(root.textContent,/한국 시간/);assert.match(root.textContent,/의도한 변경/);assert.match(root.textContent,/대상·기간·단위/);assert.match(root.textContent,/In the past quarter/);
 const events=klass(root,'human-event');assert.equal(events[5].open,true);assert.equal(events[1].open,false);events[6].open=true;events[6].emit('toggle');assert.match(root.textContent,/8,861/);
 assert.equal(fs.readFileSync(fixture,'utf8'),raw);
});
await check('large integers, duplicate fields, exponent and false/null retain meaning',()=>{
 const decoded=ctx.humanDecode('{"n":90071992547409931234,"n":2,"e":1e+04,"ok":false,"elapsed_seconds":null}');
 assert.equal(decoded.children[0].value,'90071992547409931234');assert.equal(decoded.children[1].value,'2');
 const root=render('{"n":90071992547409931234,"n":2,"e":1e+04,"ok":false,"elapsed_seconds":null}');assert.match(root.textContent,/90071992547409931234/);assert.match(root.textContent,/1e\+04/);assert.match(root.textContent,/아니요/);assert.match(root.textContent,/값 없음/);assert.doesNotMatch(root.textContent,/null초/);
 const dup=render('{"findings":[{"criterion":"scope","judgment":"FAIL","evidence":[{"field":"context","quote":"one","quote":"two"}]}]}');assert.match(dup.textContent,/one/);assert.match(dup.textContent,/two/);
});
await check('escaped Unicode and multiline strings remain text, never executable HTML',()=>{
 const root=render(JSON.stringify({text:'한글 😀\n<img src=x onerror=alert(1)>',payload:JSON.stringify({text:'두 번째\n문장'})}));
 assert.match(root.textContent,/두 번째\n문장/);assert.match(root.textContent,/<img src=x onerror=alert\(1\)>/);assert.equal(all(root,n=>n.tagName==='img').length,0);
});
await check('malformed JSONL keeps raw lines in source order',()=>{
 const raw='bad first\n{"type":"turn.started"}\n\nBROKEN\n{"type":"turn.completed"}';const n=ctx.humanDecode(raw);assert.equal(n.kind,'jsonl');assert.equal(n.children.map(e=>e.line).join(','),'1,2,4,5');const root=render(raw);assert.match(root.textContent,/bad first/);assert.match(root.textContent,/BROKEN/);assert.equal(klass(root,'human-event').length,4);
});
await check('large lists page without omitting records; deep content falls back explicitly',()=>{
 const raw=JSON.stringify(Array.from({length:53},(_,i)=>({message:'entry-'+i})));const root=render(raw);assert.equal(klass(root,'human-array-item').length,25);btn(root,'다음 항목').click();assert.equal(klass(root,'human-array-item').length,25);btn(root,'다음 항목').click();assert.equal(klass(root,'human-array-item').length,3);assert.match(root.textContent,/entry-52/);
 const deep=ctx.humanDecode('['.repeat(100)+'0'+']'.repeat(100));let n=deep;while(n.children)n=n.children[0];assert.equal(n.kind,'text');assert.match(n.note,/한도/);
 const big=render('x'.repeat(2000001));assert.match(big.textContent,/처음 24,000자/);btn(big,'전체 2,000,001자 표시').click();assert.match(big.textContent,/x{24001}/);
});
await check('Humanize opens separate modal; original copy and Escape restore source view',async()=>{
 const source=ctx.jsonViewer(raw,'02-raw-response/cli-execution.json');document.body.append(source);const opener=btn(source,'Humanize');opener.focus();opener.click();const dialog=klass(document.body,'humanize-modal')[0];assert.equal(dialog.open,true);assert.equal(klass(dialog,'human-finding').length,8);
 await btn(dialog,'원본 복사').click();assert.equal(copied,raw);
 const original=all(dialog,n=>n.tagName==='details'&&n.children[0].textContent==='원본 그대로 보기')[0];original.open=true;original.emit('toggle');assert.equal(klass(original,'json-viewer').length,1);assert.equal(btn(original,'Humanize'),undefined);
 let prevented=false;dialog.emit('cancel',{preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(dialog.isConnected,false);assert.equal(document.activeElement,opener);assert.equal(source.isConnected,true);
});
console.log(results.length+' checks passed; no LLM calls');
})().catch(error=>{console.error(error);process.exitCode=1;});
