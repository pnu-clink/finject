// Offline evaluator state is separate from production decisions and artifacts.
/* @include evaluation/graph.js */
/* @include evaluation/review.js */
/* @include evaluation/workspace.js */
function evaluationDownload(name,value,type='application/json'){
 const url=URL.createObjectURL(new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type}));
 const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
}
function evaluationFilename(reviewer,run,draft=false,date=new Date()){
 const safe=s=>s.trim().replace(/[\\/:*?"<>|\x00-\x1f]/g,'_').slice(0,100);
 const day=String(date.getMonth()+1).padStart(2,'0')+String(date.getDate()).padStart(2,'0');
 return (draft?(globalThis.FinarchI18n?.translate('임시')||'임시')+'-':'')+safe(reviewer)+'-'+safe(run)+'-'+day+'.json';
}
function validateEvaluationImport(value,pkg){
 if(value?.format!=='finarch-evaluation-results-v1'||value.package_id!==pkg.id)throw Error('이 HTML에서 저장한 평가 파일이 아닙니다.');
 if(typeof value.reviewer!=='string'||!value.reviewer.trim()||value.reviewer.length>100)throw Error('평가자 이름이 올바르지 않습니다.');
 const batch=pkg.batches.find(x=>x.batch.name===value.run);if(!batch||!Array.isArray(value.evaluations))throw Error('실행 또는 평가 목록이 올바르지 않습니다.');
 const seen=new Set();
 if(value.evaluations.length>batch.cases.length*8)throw Error('평가 항목 수가 올바르지 않습니다.');
 for(const item of value.evaluations){
  if(!item||typeof item!=='object')throw Error('평가 항목이 올바르지 않습니다.');
  const entry=batch.cases.find(x=>x.case===item.case),key=item.case+'|'+item.variant;
  if(!entry||!(item.variant==='ANSWER'||entry.variants.includes(item.variant))||seen.has(key))throw Error('문항·유형이 없거나 중복되었습니다.');
  seen.add(key);
  if(![null,'APPROVED','REJECTED','PENDING'].includes(item.decision)||typeof item.comment!=='string'||item.comment.length>100000||typeof item.confirmed!=='boolean')throw Error('판정 또는 주석 형식이 올바르지 않습니다.');
  if(item.checklist!=null&&(typeof item.checklist!=='object'||Array.isArray(item.checklist)||Object.values(item.checklist).some(v=>typeof v!=='boolean')))throw Error('검토 항목 형식이 올바르지 않습니다.');
  if(item.confirmed&&!item.decision)throw Error('저장된 판정이 비어 있습니다.');
 }
 return value;
}
async function showEvaluationExport(){
 const {dialog,body}=showSchemaDialog('평가자용 HTML Export','문제·유형별 목차, 변경 문장·수식·계산 그래프, 판정과 주석을 한 화면에 모은 평가용 HTML을 만듭니다. 현재 문제·유형의 기존 상세 화면을 여는 원본 보기도 같은 파일에 포함합니다. LLM 호출 원문·첨부 이력·결과 파일 트리는 포함하지 않습니다.');
 const chosen=[],current=DATA.batch?.name;
 for(const option of $('batch-select').options){
  if(option.dataset.evaluationExportable!=='true')continue;
  const line=el('label','check'),check=el('input');check.type='checkbox';check.checked=option.value===current;
  line.append(check,el('span','',option.value+' · 7유형 전부 통과·Reject 없음'));body.append(line);chosen.push([option.value,check]);
 }
 const note=el('p','small','7유형 모두 자동 검증 PASS이며 어느 유형에도 Reject가 없는 문항만 7유형 묶음으로 내보냅니다. 한 유형이라도 실패·미평가·누락·Reject이면 문항 전체를 제외합니다. Accept는 필수가 아니며 미판정·Pending도 포함합니다. 화면 필터와 무관하며, 현재 실행은 선택 차수·다른 실행은 최신 차수를 사용합니다.'),status=el('p','',''),save=button('HTML 다운로드',async()=>{
  const runs=chosen.filter(([,check])=>check.checked).map(([name])=>name===current?{name,round:DATA.batch.round}:{name});
  if(!runs.length){status.textContent='내보낼 실행을 선택해 주세요.';return;}
  save.disabled=true;status.textContent='평가 화면을 모으고 있습니다. 문항이 많으면 몇 분 걸릴 수 있습니다.';
  try{
   const response=await fetch('/api/evaluation-export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({runs,view:{lang:globalThis.FinarchI18n?.language||'en',run:current,case:rows.find(r=>r.id===selected)?.sample.id,variant:window.preparationVariant||null,preparationStage:window.preparationStage,generationStage:window.generationStage,filters:Object.fromEntries(Object.entries(selections).map(([key,v])=>[key,[...v]])),includePrepFailed:$('include-prep-failed').checked}})});
   if(!response.ok){const error=await response.json();throw Error(error.error||'HTML 생성 실패');}
   const html=await response.text();evaluationDownload(runs.map(r=>r.name).join('+')+(globalThis.FinarchI18n?.language==='en'?'-evaluation.html':'-평가.html'),html,'text/html;charset=utf-8');status.textContent='HTML 다운로드를 시작했습니다. 이 파일 하나를 평가자에게 전달하세요.';
  }catch(error){status.textContent=error.message;}finally{save.disabled=false;}
 });body.append(note,save,status);
}
const evaluationState={reviewer:'',records:new Map(),sequence:0,status:null,view:'review'};
function evaluationSetView(view,redraw=true){
 evaluationState.view=view;
 document.body.classList.toggle('evaluation-review-mode',view==='review');
 for(const control of document.querySelectorAll('[data-evaluation-view]'))control.classList.toggle('active',control.dataset.evaluationView===view);
 if(redraw)render();
}
function evaluationRecordKey(run,caseName,variant){return JSON.stringify([run,caseName,variant||'ANSWER']);}
function evaluationDocument(run,draft){
 const batch=DATA.evaluation.batches.find(x=>x.batch.name===run);
 return {format:'finarch-evaluation-results-v1',package_id:DATA.evaluation.id,run,round:batch.batch.round,reviewer:evaluationState.reviewer.trim(),kind:draft?'draft':'final',saved_at:new Date().toISOString(),cases:batch.cases.map(x=>x.case),evaluations:[...evaluationState.records.values()].filter(x=>x.run===run).map(({run,...item})=>item)};
}
function evaluationRemember(){
 if(!evaluationState.reviewer.trim())return;
 try{localStorage.setItem('finarch-evaluation:'+DATA.evaluation.id+':'+DATA.batch.name+':'+evaluationState.reviewer.trim(),JSON.stringify(evaluationDocument(DATA.batch.name,true)));evaluationState.status.textContent='자동 저장됨 · 파일 보관은 임시 저장';}
 catch(error){evaluationState.status.textContent='브라우저 임시 저장을 사용할 수 없습니다. 임시 저장으로 JSON 파일을 내려받으세요.';}
}
function applyEvaluationImport(value){
 validateEvaluationImport(value,DATA.evaluation);
 for(const [key,item] of evaluationState.records)if(item.run===value.run)evaluationState.records.delete(key);
 for(const item of value.evaluations)evaluationState.records.set(evaluationRecordKey(value.run,item.case,item.variant),{run:value.run,case:item.case,variant:item.variant,decision:item.decision,comment:item.comment,checklist:item.checklist||{},confirmed:item.confirmed,updated_at:item.updated_at||value.saved_at});
 evaluationState.reviewer=value.reviewer;$('evaluation-reviewer').value=value.reviewer;evaluationSwitch(value.run);evaluationRemember();
}
function showEvaluationImport(){
 const {dialog,body}=showSchemaDialog('평가 Import','이 브라우저에 임시 저장한 기록을 선택하거나, 내려받은 JSON 파일을 선택하세요. 선택한 실행의 현재 평가를 가져온 기록으로 교체합니다.');
 const select=el('select'),empty=el('option','','저장된 기록 선택');select.setAttribute('aria-label','브라우저 임시 평가 기록');empty.value='';select.append(empty);
 try{for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(!key.startsWith('finarch-evaluation:'+DATA.evaluation.id+':'))continue;const value=JSON.parse(localStorage.getItem(key));const option=el('option','',value.reviewer+' · '+value.run+' · '+value.saved_at);option.value=key;select.append(option);}}catch{}
 const message=el('p','small'),apply=value=>{try{applyEvaluationImport(value);dialog.close();}catch(error){message.textContent=error.message;}};
 const file=el('input');file.type='file';file.accept='.json,application/json';file.setAttribute('aria-label','다른 위치의 평가 JSON 파일');file.onchange=async()=>{try{if(file.files[0])apply(JSON.parse(await file.files[0].text()));}catch(error){message.textContent='파일을 읽지 못했습니다: '+error.message;}};
 body.append(select,button('선택한 임시 기록 적용',()=>{try{if(select.value)apply(JSON.parse(localStorage.getItem(select.value)));}catch(error){message.textContent=error.message;}}),el('p','','다른 위치의 파일 선택'),file,message);
}
function renderEvaluationReview(panel,row,variant){
 const name=DATA.batch.name,key=evaluationRecordKey(name,row.sample.id,variant),saved=evaluationState.records.get(key);
 panel.append(el('h2','','평가자 판정 · '+(evaluationTypes.find(([path])=>path===variant)?.[1]||'Preparation')),el('p','small','이 평가는 배포된 HTML의 별도 평가 기록입니다. 원본 제작 결과를 변경하지 않습니다.'));
 if(!variant){
  const correction=row.run.artifacts['run.json']?.correction_ref;
  if(correction)jsonBox(panel,'보정 근거와 변경 전후',row.run.artifacts[correction+'/04-apply-correction/01-result.json']);
  const notice=row.run.artifacts['07-human-review/review-note.json'];if(notice)panel.append(el('p','banner',notice.reason));
 }
 const checks={},checklist=el('div','review-checklist');
 for(const [stage,title] of (variant?[['01-perturbation','01 그래프 변경 확인'],['02-generate-text','02 문장 생성 확인'],['03-validation','03 검증 결과 확인']]:[['02-review','02 원본 검토'],['03-calculation','03 계산·정답'],['04-graph','04 계산 그래프'],['05-verification','05 계산 검증']])){
  const label=el('label','check'),input=el('input');input.type='checkbox';input.checked=saved?.checklist?.[stage]??!stageFailureEntries(row,variant,stage).length;checks[stage]=input;label.append(input,el('span','',title));checklist.append(label);
 }
 panel.append(checklist);
 const note=el('textarea');note.setAttribute('aria-label','채점자 주석');note.placeholder='채점자 주석 / Reject·Pending 선택 시 이유 필수';note.value=saved?.comment||'';
 let decision=saved?.decision||null;
 const message=el('p','small'),choices=el('div','review-checklist');
 const remember=confirmed=>{evaluationState.records.set(key,{run:name,case:row.sample.id,variant:variant||'ANSWER',decision,comment:note.value,checklist:Object.fromEntries(Object.entries(checks).map(([k,v])=>[k,v.checked])),confirmed,updated_at:new Date().toISOString()});evaluationRemember();};
 const save=button('판정 저장 (x key)',()=>{if(!evaluationState.reviewer.trim()){message.textContent='상단에 평가자 이름을 입력해 주세요.';return;}if(!decision||(decision!=='APPROVED'&&!note.value.trim())||(decision==='APPROVED'&&!Object.values(checks).every(c=>c.checked))){message.textContent='판정·검토 항목과 필수 주석을 확인해 주세요.';return;}remember(true);render();});
 for(const [value,title] of [['APPROVED','Accept 승인 (1 key)'],['REJECTED','Reject 제외 (2 key)'],['PENDING','Pending 검토 대기 (3 key)']]){const label=el('label','check'),radio=el('input');radio.type='radio';radio.name='evaluation-decision';radio.dataset.reviewChoice=value;radio.value=value;radio.checked=value===decision;radio.onchange=()=>{decision=value;remember(false);};label.append(radio,el('span','',title));choices.append(label);}
 for(const input of Object.values(checks))input.onchange=()=>remember(false);
 note.oninput=()=>remember(false);panel.append(choices,note,save,message);
 const bulk=button('전체 판정 저장 (X)',()=>{if(!evaluationState.reviewer.trim()||!decision||(decision!=='APPROVED'&&!note.value.trim())||(decision==='APPROVED'&&!Object.values(checks).every(c=>c.checked))){message.textContent='평가자 이름·판정·필수 주석을 확인해 주세요.';return;}for(const v of Object.keys(row.run.generation_origins||{})){evaluationState.records.set(evaluationRecordKey(name,row.sample.id,v),{run:name,case:row.sample.id,variant:v,decision,comment:note.value,checklist:Object.fromEntries(Object.entries(checks).map(([k,v])=>[k,v.checked])),confirmed:true,updated_at:new Date().toISOString()});}evaluationRemember();render();});bulk.disabled=!Object.keys(row.run.generation_origins||{}).length;panel.append(bulk,el('p','small','전체 판정 저장은 이 문항에 포함된 Generation 유형에 동일한 판정과 주석을 적용합니다.'));
 if(saved)panel.append(el('p','small',saved.confirmed?'판정 저장됨':'작성 중 · 임시 저장됨'));
}
async function evaluationLoadCase(caseName){
 const pkg=DATA.evaluation,batch=pkg.batches.find(x=>x.batch.name===DATA.batch.name),entry=batch.cases.find(x=>x.case===caseName),sequence=++evaluationState.sequence;
 if(!entry)return;
 try{
  if(typeof DecompressionStream==='undefined')throw Error('압축 해제를 지원하는 최신 Chrome, Edge 또는 Safari에서 열어 주세요.');
  const compressed=Uint8Array.from(atob($(entry.blob).textContent),c=>c.charCodeAt(0));
  const raw=await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
  if(sequence!==evaluationState.sequence)return;
  const detail=JSON.parse(raw);DATA.runs=batch.runs.map(r=>r.artifacts['00-data-preparation/01-select-input/01-input.json']?.id===caseName?detail:r);
  loadRows();selected=rows.find(r=>r.sample.id===caseName)?.id;evaluationState.loading=null;render();$('batch-status').textContent=batch.batch.name+' · '+caseName+' · HTML 내장 자료';
 }catch(error){if(sequence!==evaluationState.sequence)return;evaluationState.loading=null;$('batch-status').textContent=error.message;if($('evaluation-main'))$('evaluation-main').replaceChildren(el('p','banner',error.message));}
}
function evaluationSwitch(name){
 const pkg=DATA.evaluation,batch=pkg.batches.find(x=>x.batch.name===name);if(!batch)return;
 const current=rows.find(r=>r.id===selected)?.sample.id;
 ++evaluationState.sequence;DATA={format:'fin-arch-viewer-v1',evaluation:pkg,live:false,batch:batch.batch,runs:batch.runs};
 $('batch-select').value=name;$('round-select').replaceChildren();const round=el('option','',batch.batch.round);round.value=batch.batch.round;$('round-select').append(round);$('round-select').disabled=true;
 $('search').value='';evaluationState.search='';evaluationState.loading=null;evaluationState.feedback='';loadRows();selected=(rows.find(r=>r.sample.id===current)||rows[0])?.id;render();
}
document.addEventListener('DOMContentLoaded',()=>{
 const header=document.querySelector('header');
 if(!DATA.evaluation){if(DATA.live){header.append(button('평가자용 HTML Export',showEvaluationExport));const manager=el('a','','Annotation 관리자');manager.href='/annotation/';manager.style.cssText='color:white;font-size:13px;white-space:nowrap';header.append(manager);}return;}
 decision=row=>{const record=evaluationState.records.get(evaluationRecordKey(DATA.batch.name,row.sample.id,window.preparationVariant));return {decision:record?.confirmed?({APPROVED:'APPROVE',REJECTED:'REJECT',PENDING:'PENDING'})[record.decision]:'PENDING'};};
 reviewDefaultDecision=(row,variant)=>evaluationState.records.get(evaluationRecordKey(DATA.batch.name,row.sample.id,variant))?.decision||'PENDING';
 const pkg=DATA.evaluation;document.title='데이터 평가 · '+pkg.batches.map(x=>x.batch.name).join(' / ');
 document.body.classList.add('evaluation-page');
 const headerSize=()=>{document.documentElement.style.setProperty('--evaluation-header-height',header.getBoundingClientRect().height+'px');requestAnimationFrame(()=>{if(!evaluationState.original)document.querySelector('.evaluation-chart-panel')?.dispatchEvent(new Event('evaluation-fit'));});};
 window.addEventListener('resize',headerSize);requestAnimationFrame(headerSize);
 const languageToolbar=header.querySelector('.viewer-language');
 header.replaceChildren(el('h1','','데이터 평가'));
 const label=el('label','','평가자 이름 '),reviewer=el('input');reviewer.id='evaluation-reviewer';reviewer.maxLength=100;reviewer.setAttribute('aria-label','평가자 이름');label.append(reviewer);header.append(label);
 evaluationState.status=el('span','small','임시 저장·결과 Export는 현재 선택한 실행의 평가를 저장합니다.');evaluationState.status.style.color='white';
 reviewer.oninput=()=>{evaluationState.reviewer=reviewer.value;evaluationRemember();};
 for(const [title,draft] of [['임시 저장',true],['결과 Export',false]])header.append(button(title,()=>{if(!evaluationState.reviewer.trim()){evaluationState.status.textContent='평가자 이름을 입력해 주세요.';reviewer.focus();return;}evaluationRemember();evaluationDownload(evaluationFilename(evaluationState.reviewer,DATA.batch.name,draft),evaluationDocument(DATA.batch.name,draft));evaluationState.status.textContent=DATA.batch.name+' · '+(draft?'임시':'결과')+' JSON 다운로드를 시작했습니다.';}));
 const returnButton=button('평가 화면으로 돌아가기',evaluationCloseOriginal);returnButton.id='evaluation-return';returnButton.hidden=true;
 header.append(button('Import',showEvaluationImport),returnButton,evaluationState.status);header.style.cssText+=';flex-wrap:wrap;gap:10px';
 $('batch-controls').style.display='block';$('batch-guide').hidden=true;$('live-log').hidden=true;$('connection-help').hidden=true;
 $('batch-select').replaceChildren();for(const batch of pkg.batches){const option=el('option','',batch.batch.name);option.value=batch.batch.name;$('batch-select').append(option);}
 $('batch-select').onchange=()=>evaluationSwitch($('batch-select').value);
 window.loadDetailCase=evaluationLoadCase;
 renderPreparationReview=(panel,row)=>evaluationRenderOriginalReview(panel,row,null);renderGenerationReview=evaluationRenderOriginalReview;
 appendSavedNavigationDecision=(parent,row)=>{const variant=window.preparationVariant||'ANSWER',record=evaluationState.records.get(evaluationRecordKey(DATA.batch.name,row.sample.id,variant));if(record?.confirmed)parent.append(el('span','',({APPROVED:'✅',REJECTED:'❌',PENDING:'🟡'})[record.decision]));};
 if(languageToolbar)header.append(languageToolbar);
 const initial=pkg.initial_view||{};if(initial.lang)globalThis.FinarchI18n?.setLanguage(initial.lang,{persist:false});window.preparationVariant=initial.variant||null;window.preparationStage=initial.preparationStage;window.generationStage=initial.generationStage;
 evaluationMountWorkspace();
 evaluationSwitch(pkg.batches.some(x=>x.batch.name===initial.run)?initial.run:pkg.batches[0].batch.name);
 if(initial.case&&rows.some(r=>r.sample.id===initial.case))selected=rows.find(r=>r.sample.id===initial.case).id;
 window.preparationVariant=initial.variant||window.preparationVariant;
 render();
});
