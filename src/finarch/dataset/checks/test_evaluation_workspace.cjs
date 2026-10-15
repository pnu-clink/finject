// Annotation navigation and persistence, without production writes or model calls.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const controls=new Map(),handlers=[],saved=new Map();let remembers=0;
const $=id=>{if(!controls.has(id))controls.set(id,{value:'',focus(){this.focused=true;}});return controls.get(id);};
const types=['01-ic-value-before','02-ic-value-after','03-ic-source-type-1','04-ic-source-type-2','05-ic-relation','06-ea-earlier-input','07-ea-later-input'];
const batch={batch:{name:'run'},cases:['test-0001','test-0002'].map(c=>({case:c,variants:types}))};
const ctx=vm.createContext({console,Map,Date,DATA:{batch:batch.batch,evaluation:{batches:[batch]}},window:{preparationVariant:types[0]},rows:batch.cases.map(c=>({id:c.case,sample:{id:c.case}})),selected:'test-0001',
 evaluationState:{reviewer:'Tester',records:saved,mode:'case',filter:'todo',autoNext:true,loading:null,status:{textContent:''}},
 evaluationRecordKey:(...args)=>JSON.stringify(args),evaluationRemember(){remembers++;},render(){},$,
 el(tag,className='',textContent=''){return {tag,className,textContent,children:[],setAttribute(){},append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},querySelector(){return this.children.find(x=>x.className?.split(' ').includes('selected'));},scrollIntoView(){},classList:{toggle(){}}};},document:{body:{append(){}},addEventListener:(event,fn,capture)=>handlers.push({event,fn,capture}),querySelector:()=>null},
});
ctx.button=(title,onclick,className='')=>Object.assign(ctx.el('button',className,title),{onclick});
ctx.window.scrollTo=()=>{};
vm.runInContext(fs.readFileSync('viewer/dataset/evaluation/review.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('viewer/dataset/evaluation/workspace.js','utf8'),ctx);
const checks=[];function check(name,fn){fn();checks.push(name);}
check('Case and type modes include exactly the recorded variants',()=>{
 assert.equal(ctx.evaluationEntries().length,14);assert.equal(ctx.evaluationEntries(batch,'type',types[4]).length,2);
 assert.equal(ctx.evaluationEntries({cases:[{case:'test-0003',variants:[]}]},'case')[0].variant,'ANSWER');
});
check('Choosing a judgment saves it immediately and advances to the next undecided type',()=>{
 $('evaluation-note').value='Review note';ctx.evaluationChoose('APPROVED');
 assert.equal(saved.get(JSON.stringify(['run','test-0001',types[0]])).comment,'Review note');
 assert.equal(ctx.window.preparationVariant,types[1]);assert.equal(ctx.evaluationCounts(ctx.evaluationEntries()).APPROVED,1);
 ctx.evaluationChoose('REJECTED');ctx.evaluationChoose('PENDING');assert.equal(ctx.window.preparationVariant,types[3]);
 assert.equal(ctx.evaluationCounts(ctx.evaluationEntries()).done,3);assert.equal(remembers,3);
});
check('Previous navigation excludes decided variants in the undecided filter; all permits revisiting',()=>{
 ctx.evaluationNavigate(-1);assert.equal(ctx.window.preparationVariant,types[3]);
 ctx.evaluationState.filter='all';
 ctx.evaluationNavigate(-1);assert.equal(ctx.window.preparationVariant,types[2]);
 ctx.evaluationNavigate(-1);assert.equal(ctx.window.preparationVariant,types[1]);
 ctx.evaluationState.autoNext=false;$('evaluation-note').value='Revised';ctx.evaluationChoose('APPROVED');assert.equal(ctx.window.preparationVariant,types[1]);
 assert.equal(saved.get(JSON.stringify(['run','test-0001',types[1]])).decision,'APPROVED');
});
check('Note edits remain attached to the correct case and type',()=>{
 ctx.evaluationDraftNote('Updated note');const record=saved.get(JSON.stringify(['run','test-0001',types[1]]));assert(record.confirmed);assert.equal(record.comment,'Updated note');
});
check('Problem navigation retains the type; type navigation retains the problem',()=>{
 ctx.evaluationNavigateProblem(1);assert.equal(ctx.selected,'test-0002');assert.equal(ctx.window.preparationVariant,types[1]);
 ctx.evaluationNavigateType(1);assert.equal(ctx.selected,'test-0002');assert.equal(ctx.window.preparationVariant,types[2]);
 ctx.evaluationNavigateProblem(-1);assert.equal(ctx.selected,'test-0001');assert.equal(ctx.window.preparationVariant,types[2]);
 ctx.evaluationNavigateType(-1);assert.equal(ctx.window.preparationVariant,types[1]);
 ctx.evaluationNavigateProblem(-1);assert.equal(ctx.selected,'test-0001');
});
check('Original view opens at the current case and type and returns without losing the draft or decision',()=>{
 const current=ctx.evaluationCurrent();$('evaluation-note').value='Draft before opening original';ctx.evaluationOpenOriginal();
 assert(ctx.evaluationState.original);assert.equal(ctx.evaluationState.view,'stages');assert.equal(ctx.window.generationStage,'01-perturbation');
 ctx.evaluationNavigateProblem(1);ctx.evaluationNavigateType(1);ctx.evaluationCloseOriginal();
 assert(!ctx.evaluationState.original);assert.equal(ctx.evaluationState.view,'review');assert.equal(ctx.evaluationCurrent().case,current.case);assert.equal(ctx.evaluationCurrent().variant,current.variant);
 const record=ctx.evaluationSaved(current.case,current.variant);assert(record.confirmed);assert.equal(record.comment,'Draft before opening original');
});
check('Auto advance wraps to an earlier undecided entry, but never overwrites another decision',()=>{
 const entries=ctx.evaluationEntries();const last=entries.at(-1),next=ctx.evaluationNextEntry(entries,last,'todo',true);assert.equal(next.case,'test-0001');assert.equal(next.variant,types[3]);
 assert(!ctx.evaluationNextEntry(entries,last,'all',true));
});
check('The evaluator name is required before saving a judgment',()=>{
 const before=saved.size;ctx.evaluationState.reviewer='';ctx.evaluationChoose('APPROVED');assert.equal(saved.size,before);assert($('evaluation-reviewer').focused);ctx.evaluationState.reviewer='Tester';
});
check('Numpad 1, 2 and 3 select pass, fail and hold; typing and key repeats are excluded',()=>{
 ctx.evaluationMountWorkspace();ctx.render=()=>{};const handler=handlers.find(h=>h.event==='keydown');assert(handler.capture);
 const event=code=>({code,key:'End',target:{closest:()=>null},preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;}});
 for(const [i,decision] of ['APPROVED','REJECTED','PENDING'].entries()){
  ctx.evaluationState.autoNext=false;const e=event('Numpad'+(i+1));handler.fn(e);assert(e.stopped);const current=ctx.evaluationCurrent();assert.equal(ctx.evaluationSaved(current.case,current.variant).decision,decision);
 }
 const repeat=event('Numpad1');repeat.repeat=true;handler.fn(repeat);const current=ctx.evaluationCurrent();assert.equal(ctx.evaluationSaved(current.case,current.variant).decision,'PENDING');
 const typing=event('Numpad1');typing.target.closest=()=>({});handler.fn(typing);assert(!typing.stopped);
});
check('Physical Q/E and A/D navigate problems and types even with a non-English keyboard layout',()=>{
 const handler=handlers.find(h=>h.event==='keydown');ctx.evaluationJump({case:'test-0001',variant:types[4]});
 const event=code=>({code,key:'ㅁ',target:{closest:()=>null},preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;}});
 for(const [code,expectedCase,expectedType] of [['KeyE','test-0002',types[4]],['KeyA','test-0002',types[3]],['KeyQ','test-0001',types[3]],['KeyD','test-0001',types[4]]]){
  const e=event(code);handler.fn(e);assert(e.stopped);assert.equal(ctx.selected,expectedCase);assert.equal(ctx.window.preparationVariant,expectedType);
 }
 const typing=event('KeyE');typing.target.closest=()=>({});handler.fn(typing);assert(!typing.stopped);assert.equal(ctx.selected,'test-0001');
 ctx.evaluationState.original=true;const before=saved.size;handler.fn(event('Numpad1'));assert.equal(saved.size,before);
});
check('Every filtered case renders beyond 160, with accurate fixed counts and no pagination controls',()=>{
 batch.cases=Array.from({length:220},(_,i)=>({case:'test-'+String(i+1).padStart(4,'0'),variants:types}));
 ctx.rows=batch.cases.map(c=>({id:c.case,sample:{id:c.case}}));ctx.selected='test-0001';ctx.window.preparationVariant=types[0];ctx.evaluationState.mode='case';ctx.evaluationState.search='';ctx.evaluationState.filter='all';saved.clear();
 const list=ctx.el('div');ctx.evaluationRenderCaseList(list);
 assert.equal(list.children.length,220);assert.equal(list.children.at(-1).children[0].textContent,'test-0220');
 assert.equal($('evaluation-list-count').textContent,'목록 220 / 220문항');assert(list.children.every(x=>!x.className.includes('evaluation-list-more')));
 for(const entry of batch.cases.slice(0,150))for(const variant of types)saved.set(JSON.stringify(['run',entry.case,variant]),{confirmed:true,decision:entry.case==='test-0005'&&variant===types[0]?'REJECTED':'APPROVED'});
 ctx.evaluationState.filter='todo';ctx.evaluationRenderCaseList(list);
 assert.equal(list.children.length,71);assert.equal($('evaluation-list-count').textContent,'목록 71 / 220문항 · 필터 일치 70문항');
 ctx.evaluationState.filter='APPROVED';ctx.evaluationRenderCaseList(list);assert.equal(list.children.length,150);
 ctx.evaluationState.filter='REJECTED';ctx.evaluationRenderCaseList(list);assert.equal(list.children.length,2);assert.equal($('evaluation-list-count').textContent,'목록 2 / 220문항 · 필터 일치 1문항');
 ctx.evaluationState.mode='type';ctx.evaluationState.filter='APPROVED';ctx.evaluationRenderCaseList(list);assert.equal(list.children.length,149);
 ctx.evaluationState.search='test-0220';ctx.evaluationState.filter='todo';ctx.evaluationRenderCaseList(list);assert.equal(list.children.length,1);assert.equal($('evaluation-list-count').textContent,'목록 1 / 220문항');
 ctx.evaluationState.search='test-9999';ctx.evaluationRenderCaseList(list);assert.equal(list.children.length,0);assert.equal($('evaluation-list-count').textContent,'목록 0 / 220문항');
});
check('Q/E and arrow navigation share status and search filtering, including an excluded current case',()=>{
 saved.clear();ctx.evaluationState.mode='case';ctx.evaluationState.filter='PENDING';ctx.evaluationState.search='';
 for(const [caseName,variant,decision] of [['test-0002',types[0],'APPROVED'],['test-0003',types[2],'PENDING'],['test-0005',types[2],'PENDING']])saved.set(JSON.stringify(['run',caseName,variant]),{confirmed:true,decision});
 ctx.evaluationJump({case:'test-0001',variant:types[0]});ctx.evaluationNavigateProblem(1);
 assert.equal(ctx.selected,'test-0003');assert.equal(ctx.window.preparationVariant,types[2]);
 ctx.evaluationNavigateProblem(1);assert.equal(ctx.selected,'test-0005');
 ctx.evaluationNavigateProblem(1);assert.equal(ctx.selected,'test-0005');
 ctx.evaluationNavigateProblem(-1);assert.equal(ctx.selected,'test-0003');
 ctx.evaluationState.search='test-0005';ctx.evaluationNavigateProblem(1);assert.equal(ctx.selected,'test-0005');
 ctx.evaluationNavigateProblem(-1);assert.equal(ctx.selected,'test-0005');
 ctx.evaluationState.search='';ctx.evaluationNavigate(-1);assert.equal(ctx.selected,'test-0003');
 ctx.evaluationState.mode='type';ctx.window.preparationVariant=types[0];ctx.evaluationNavigateProblem(1);assert.equal(ctx.selected,'test-0003');
});
check('v and Shift+V jump to confirmed hold/reject only, preserve filters, and ignore note typing',()=>{
 saved.clear();ctx.evaluationState.mode='case';ctx.evaluationState.filter='all';ctx.evaluationState.search='';
 for(const [caseName,variant,decision,confirmed] of [['test-0001',types[1],'PENDING',false],['test-0002',types[0],'APPROVED',true],['test-0003',types[2],'PENDING',true],['test-0005',types[4],'REJECTED',true]])saved.set(JSON.stringify(['run',caseName,variant]),{confirmed,decision});
 const handler=handlers.find(h=>h.event==='keydown');
 const event=(shift=false)=>({code:'KeyV',key:shift?'V':'v',shiftKey:shift,target:{closest:()=>null},preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;}});
 ctx.evaluationJump({case:'test-0001',variant:types[0]});handler.fn(event());assert.equal(ctx.selected,'test-0003');assert.equal(ctx.window.preparationVariant,types[2]);
 handler.fn(event());assert.equal(ctx.selected,'test-0005');assert.equal(ctx.window.preparationVariant,types[4]);
 handler.fn(event(true));assert.equal(ctx.selected,'test-0003');
 ctx.evaluationState.filter='PENDING';handler.fn(event());assert.equal(ctx.selected,'test-0003');assert.match(ctx.evaluationState.status.textContent,/다음/);
 ctx.evaluationState.filter='all';ctx.evaluationState.search='test-0003';handler.fn(event());assert.equal(ctx.selected,'test-0003');
 const typing=event();typing.target.closest=()=>({});handler.fn(typing);assert(!typing.stopped);
 ctx.evaluationState.search='';handler.fn({...event(),key:'ㅍ'});assert.equal(ctx.selected,'test-0005');
 handler.fn({...event(true),key:'ㅍ'});assert.equal(ctx.selected,'test-0003');
 handler.fn(event());assert.equal(ctx.selected,'test-0005');
 handler.fn({...event(),key:'V'});assert.equal(ctx.selected,'test-0003');
});
console.log(JSON.stringify({status:'PASS',checks:checks.length,results:checks,model_calls:0,production_writes:0},null,2));
