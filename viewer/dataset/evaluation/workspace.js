// The exported workspace is for annotation. It does not use production filters or decisions.
const evaluationJudgments={APPROVED:{label:'통과',className:'accept'},REJECTED:{label:'실패',className:'reject'},PENDING:{label:'유보',className:'pending'}};
function evaluationBatch(){return DATA.evaluation.batches.find(b=>b.batch.name===DATA.batch.name);}
function evaluationSaved(caseName,variant){return evaluationState.records.get(evaluationRecordKey(DATA.batch.name,caseName,variant));}
function evaluationEntries(batch=evaluationBatch(),mode=evaluationState.mode,type=window.preparationVariant){
 const result=[];
 for(const c of batch.cases){
  const types=evaluationTypes.filter(([v])=>c.variants.includes(v)).map(([v])=>v);
  // Preparation-only cases remain reviewable, without fabricating generation variants.
  for(const variant of types.length?types:['ANSWER'])if(mode!=='type'||variant===(type||'ANSWER'))result.push({case:c.case,variant});
 }
 return result;
}
function evaluationEntryKey(item){return item.case+'|'+item.variant;}
function evaluationMatches(item,filter=evaluationState.filter){
 const record=evaluationSaved(item.case,item.variant);
 return filter==='all'||(filter==='todo'?!record?.confirmed:record?.confirmed&&record.decision===filter);
}
function evaluationFilteredEntries(){
 const search=(evaluationState.search||'').trim().toLowerCase();
 return evaluationEntries().filter(item=>(!search||item.case.includes(search))&&evaluationMatches(item));
}
function evaluationNextEntry(entries,current,filter,advance=false){
 const at=entries.findIndex(e=>evaluationEntryKey(e)===evaluationEntryKey(current));
 if(advance&&filter==='todo')return [...entries.slice(at+1),...entries.slice(0,Math.max(0,at))].find(e=>evaluationMatches(e,filter));
 return entries.slice(at+1).find(e=>evaluationMatches(e,filter));
}
function evaluationCurrent(){
 const row=rows.find(r=>r.id===selected),variant=window.preparationVariant||'ANSWER';
 return row?{case:row.sample.id,variant}:null;
}
function evaluationJump(item){
 const row=rows.find(r=>r.sample.id===item?.case);if(!row)return;
 selected=row.id;window.preparationVariant=item.variant==='ANSWER'?null:item.variant;
 if(evaluationState.original)evaluationState.originalFocus=true;
 evaluationState.loading=null;render();
}
function evaluationNavigate(direction){
 const all=evaluationEntries(),current=evaluationCurrent();if(!current)return;
 const at=all.findIndex(e=>evaluationEntryKey(e)===evaluationEntryKey(current));if(at<0)return;
 const allowed=new Set(evaluationFilteredEntries().map(evaluationEntryKey));
 const next=(direction<0?all.slice(0,at).reverse():all.slice(at+1)).find(e=>allowed.has(evaluationEntryKey(e)));
 if(next)evaluationJump(next);
}
function evaluationNavigateProblem(direction){
 const current=evaluationCurrent();if(!current)return;
 const cases=evaluationBatch().cases,at=cases.findIndex(c=>c.case===current.case);if(at<0)return;
 const entries=evaluationFilteredEntries(),allowed=new Set(entries.map(e=>e.case));
 const next=(direction<0?cases.slice(0,at).reverse():cases.slice(at+1)).find(c=>allowed.has(c.case));if(!next)return;
 const matches=entries.filter(e=>e.case===next.case);
 evaluationJump(matches.find(e=>e.variant===current.variant)||matches[0]);
}
function evaluationNavigateReviewIssue(direction){
 const all=evaluationEntries(),current=evaluationCurrent();if(!current)return;
 const at=all.findIndex(e=>evaluationEntryKey(e)===evaluationEntryKey(current));if(at<0)return;
 const allowed=new Set(evaluationFilteredEntries().map(evaluationEntryKey));
 const next=(direction<0?all.slice(0,at).reverse():all.slice(at+1)).find(item=>{
  const saved=evaluationSaved(item.case,item.variant);
  return allowed.has(evaluationEntryKey(item))&&saved?.confirmed&&['PENDING','REJECTED'].includes(saved.decision);
 });
 if(next)evaluationJump(next);
 else if(evaluationState.status)evaluationState.status.textContent=direction<0?'필터된 목록에 이전 유보·실패 항목이 없습니다.':'필터된 목록에 다음 유보·실패 항목이 없습니다.';
}
function evaluationNavigateType(direction){
 const current=evaluationCurrent();if(!current)return;
 const entry=evaluationBatch().cases.find(c=>c.case===current.case);
 const types=evaluationTypes.filter(([v])=>entry?.variants.includes(v)).map(([v])=>v),at=types.indexOf(current.variant);
 const variant=types[at+direction];if(variant)evaluationJump({case:current.case,variant});
}
function evaluationOpenOriginal(){
 const current=evaluationCurrent();if(!current||evaluationState.loading)return;
 const note=$('evaluation-note');if(note&&note.value!==(evaluationSaved(current.case,current.variant)?.comment||''))evaluationDraftNote(note.value);
 evaluationState.originalReturn={run:DATA.batch.name,...current};evaluationState.original=true;evaluationState.originalFocus=true;evaluationState.view='stages';
 if(current.variant!=='ANSWER')window.generationStage='01-perturbation';else window.preparationStage='01-source';
 render();window.scrollTo({top:0,left:0});
}
function evaluationCloseOriginal(){
 const previous=evaluationState.originalReturn;evaluationState.original=false;evaluationState.originalFocus=false;evaluationState.view='review';
 if(previous&&previous.run!==DATA.batch.name)evaluationSwitch(previous.run);
 if(previous)evaluationJump(previous);else render();
 window.scrollTo({top:0,left:0});
}
function evaluationRenderOriginalReview(panel,row,variant){
 const saved=evaluationSaved(row.sample.id,variant||'ANSWER');
 panel.append(el('h2','','평가 기록'),el('p','',saved?.confirmed?evaluationJudgments[saved.decision].label:'미평가'));
 if(saved?.comment)panel.append(el('p','prose',saved.comment));
 panel.append(button('평가 화면으로 돌아가기',evaluationCloseOriginal),el('p','small','판정과 주석은 평가 화면에서 작성합니다.'));
}
function evaluationBullet(caseName,variant){
 const record=evaluationSaved(caseName,variant),judgment=record?.confirmed?evaluationJudgments[record.decision]:null;
 const dot=el('span','evaluation-bullet '+(judgment?.className||'undecided'),'●');
 dot.title=(evaluationTypes.find(([v])=>v===variant)?.[1]||'Preparation')+' · '+(judgment?.label||'미평가');
 dot.setAttribute('aria-label',dot.title);return dot;
}
function evaluationCounts(entries){
 const counts={APPROVED:0,REJECTED:0,PENDING:0,total:entries.length};
 for(const item of entries){const record=evaluationSaved(item.case,item.variant);if(record?.confirmed)counts[record.decision]++;}
 counts.done=counts.APPROVED+counts.REJECTED+counts.PENDING;return counts;
}
function evaluationCountText(counts){return counts.done+' / '+counts.total+' 완료 · 통과 '+counts.APPROVED+' · 실패 '+counts.REJECTED+' · 유보 '+counts.PENDING;}
function evaluationRenderSide(parent){
 parent.replaceChildren();
 const select=el('select');select.setAttribute('aria-label','평가 실행 선택');
 for(const batch of DATA.evaluation.batches){const option=el('option','',batch.batch.name);option.value=batch.batch.name;select.append(option);}select.value=DATA.batch.name;
 select.onchange=()=>evaluationSwitch(select.value);parent.append(select);
 const all=evaluationEntries(evaluationBatch(),'case'),count=evaluationCounts(all);
 parent.append(el('p','evaluation-overall',evaluationCountText(count)));
 const bar=el('div','evaluation-progress-bar');for(const d of Object.keys(evaluationJudgments)){const part=el('i',evaluationJudgments[d].className);part.style.width=(count.total?100*count[d]/count.total:0)+'%';bar.append(part);}parent.append(bar);
 const modes=el('div','evaluation-mode');for(const [mode,title] of [['case','문제별'],['type','유형별']])modes.append(button(title,()=>{evaluationState.mode=mode;render();},evaluationState.mode===mode?'active':''));parent.append(modes);
 const current=evaluationCurrent(),typeList=el('nav','evaluation-type-list');typeList.setAttribute('aria-label','IC-VALUE부터 EA 02 유형별 판정');
 const entry=evaluationBatch().cases.find(c=>c.case===current?.case);
 for(const [variant,title] of evaluationTypes){
  const items=all.filter(i=>i.variant===variant),counts=evaluationCounts(items);
  const available=evaluationState.mode==='case'?entry?.variants.includes(variant):items.length>0;
  const b=button('',()=>{
   if(evaluationState.mode==='case')evaluationJump({case:current.case,variant});
   else{window.preparationVariant=variant;const retained=items.find(i=>i.case===current?.case),first=items.find(i=>evaluationMatches(i))||items[0];evaluationJump(retained||first);}
  },'evaluation-type'+(current?.variant===variant?' selected':''));b.disabled=!available;
  b.append(evaluationState.mode==='case'?evaluationBullet(current.case,variant):el('span','evaluation-bullet undecided','●'),el('span','',title));
  if(evaluationState.mode==='case'){const saved=evaluationSaved(current.case,variant);b.append(el('small','',available?(saved?.confirmed?evaluationJudgments[saved.decision].label:'미평가'):'자료 없음'));}
  else b.append(el('small','',counts.done+'/'+counts.total),el('span','evaluation-type-counts',evaluationCountText(counts)));
  typeList.append(b);
 }
 if(entry&&!entry.variants.length){const prep=button('',()=>evaluationJump({case:entry.case,variant:'ANSWER'}),'evaluation-type selected');prep.append(evaluationBullet(entry.case,'ANSWER'),el('span','','Preparation'));typeList.append(prep);}
 parent.append(typeList);
 const filters=el('select');filters.setAttribute('aria-label','평가 상태 필터');for(const [value,title] of [['todo','미평가'],['all','전체'],['APPROVED','통과'],['REJECTED','실패'],['PENDING','유보']]){const option=el('option','',title);option.value=value;filters.append(option);}filters.value=evaluationState.filter;filters.onchange=()=>{evaluationState.filter=filters.value;render();};parent.append(filters);
 const search=el('input');search.type='search';search.placeholder='문제 번호 검색';search.setAttribute('aria-label','문제 번호 검색');search.value=evaluationState.search;
 search.oninput=()=>{evaluationState.search=search.value;evaluationRenderCaseList(list);};
 search.onkeydown=e=>{if(e.key!=='Enter')return;const digits=search.value.replace(/\D/g,''),candidate=evaluationBatch().cases.find(c=>c.case===search.value.trim()||digits&&Number(c.case.replace(/\D/g,''))===Number(digits));if(candidate){evaluationState.search='';const variants=evaluationEntries().filter(i=>i.case===candidate.case),item=variants.find(i=>!evaluationSaved(i.case,i.variant)?.confirmed)||variants[0];if(item)evaluationJump(item);document.activeElement?.blur();}e.stopPropagation();};
 const listCount=el('p','evaluation-list-count');listCount.id='evaluation-list-count';listCount.setAttribute('role','status');listCount.setAttribute('aria-live','polite');
 parent.append(search,listCount);const list=el('div','evaluation-case-list');list.id='evaluation-case-list';list.setAttribute('aria-label','문제 목차와 저장된 판정');parent.append(list);evaluationRenderCaseList(list);
 parent.append(el('p','evaluation-dot-legend','● 초록 통과 · ● 빨강 실패 · ● 노랑 유보'));
}
function evaluationRenderCaseList(list){
 list.replaceChildren();const current=evaluationCurrent(),all=evaluationEntries(),search=evaluationState.search.trim().toLowerCase();
 const items=evaluationFilteredEntries();
 // Keep the selected case visible after a decision, even in the undecided filter.
 const cases=[...new Set(items.map(i=>i.case))],matchedCount=cases.length;
 if(current&&!cases.includes(current.case)&&(!search||current.case.includes(search)))cases.push(current.case);cases.sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
 const count=$('evaluation-list-count');if(count)count.textContent='목록 '+cases.length+' / '+evaluationBatch().cases.length+'문항'+(cases.length!==matchedCount?' · 필터 일치 '+matchedCount+'문항':'');
 for(const caseName of cases){
  const entry=evaluationBatch().cases.find(c=>c.case===caseName),variants=entry.variants.length?evaluationTypes.filter(([v])=>entry.variants.includes(v)).map(([v])=>v):['ANSWER'];
  const b=button('',()=>{
   const candidates=all.filter(i=>i.case===caseName),item=candidates.find(i=>evaluationMatches(i))||candidates[0];evaluationJump(item);
  },'evaluation-case-link'+(current?.case===caseName?' selected':''));b.append(el('span','',caseName));
  const dots=el('span','evaluation-case-bullets');for(const variant of evaluationState.mode==='type'?[window.preparationVariant||'ANSWER']:variants)dots.append(evaluationBullet(caseName,variant));b.append(dots);list.append(b);
 }
 list.querySelector('.selected')?.scrollIntoView({block:'nearest'});
}
function evaluationGraphs(row,evidence){
 const original=evidence.plan?.original_graph||row.run.artifacts['04-graph/05-save-graph/01-graph.json'];
 const program=row.run.artifacts['03-calculation/02-prepare-code/03-program.json'];
 return {original:graphWithSourceUsage(original,program?.source_usage),changed:graphWithSourceUsage(evidence.plan?.graph,evidence.plan?.program?.source_usage)};
}
function evaluationFormulas(parent,graphs,target,selectNode){
 const section=el('section','evaluation-formulas');section.setAttribute('aria-label','원본과 변경 계산식');
 const facts=[...new Set([...(graphs.original?.nodes||[]),...(graphs.changed?.nodes||[])].filter(n=>n.kind==='fact').map(n=>n.fact_id))];
 const colors=['#147386','#8450a0','#9c3751','#327750','#4b58a2','#a26118'];
 let marked=[];try{marked=evaluationMergeGraphs(evaluationCompactGraph(graphs.original),evaluationCompactGraph(graphs.changed),target).nodes.filter(n=>n.target).flatMap(n=>n.references);}catch{}
 for(const [side,graph,label] of [['A',graphs.original,'원본 계산'],['B',graphs.changed,'변경 계산']]){
  if(!graph)continue;const line=el('div','evaluation-formula-row'),title=el('strong','',label),formula=el('div','evaluation-formula');
  const output=graph.nodes.find(n=>n.id===graph.output);title.append(el('span','', ' = '+evaluationNodeValue(output)));line.append(title,formula);
  function tokens(container,numeric){for(const token of graphFormula(graph,{numeric,markedFacts:target?[target]:[],markedIds:marked.filter(r=>r.side===side).flatMap(r=>r.node.sourceIds)})){
   const node=graph.nodes.find(n=>n.id===token.nodeId),span=el('span','graph-formula-token'+(token.changed?' evaluation-formula-changed':''),token.text);
   span.dataset.side=side;span.dataset.nodeId=token.nodeId;span.title=(node?.fact_id||node?.label||token.nodeId)+' = '+evaluationNodeValue(node||{});
   if(node?.kind==='fact'){span.style.setProperty('--fact-color',colors[facts.indexOf(node.fact_id)%colors.length]);span.style.color=colors[facts.indexOf(node.fact_id)%colors.length];}
   span.onmouseenter=()=>selectNode(side,token.nodeId,false);span.onmouseleave=()=>selectNode(null,null,false);span.onclick=()=>selectNode(side,token.nodeId,true);container.append(span);
  }}
  try{
   tokens(formula,false);const numeric=el('div','evaluation-formula-values');numeric.append(el('span','small','값 대입: '));
   if(graph.nodes.some(n=>n.kind==='fact'&&(n.evaluation?.state==='MISSING'||n.value==null)))numeric.append(el('span','small','삭제된 근거가 있어 계산할 수 없습니다.'));
   else tokens(numeric,true);formula.append(numeric);
  }catch(error){formula.append(el('span','small',error.message));}
  section.append(line);
 }
 parent.append(section);return section;
}
function evaluationRenderEvidence(main,row,variant){
 const evidence=evaluationEvidence(row,variant),graphs=evaluationGraphs(row,evidence),target=evidence.plan?.target||evidence.plan?.intent?.target;
 const heading=el('div','evaluation-heading'),title=el('h2','',row.sample.id+' · '+(evaluationTypes.find(([v])=>v===variant)?.[1]||'Preparation'));
 const saved=evaluationSaved(row.sample.id,variant||'ANSWER');heading.append(title,el('span','evaluation-decision-label '+(saved?.confirmed?evaluationJudgments[saved.decision].className:''),saved?.confirmed?evaluationJudgments[saved.decision].label:'미평가'));
 const originalButton=button('원본 보기',evaluationOpenOriginal,'evaluation-original-button');originalButton.title=row.sample.id+' · '+(evaluationTypes.find(([v])=>v===variant)?.[1]||'Preparation')+'의 기존 상세 화면';heading.append(originalButton);
 const question=el('div','evaluation-question');question.setAttribute('aria-label','질문');question.append(el('strong','evaluation-question-q','Q'),el('span','',evidence.current?.question??evidence.original.question??'질문 미기록'));
 main.append(heading,question);
 let selectGraph=()=>{};const formulas=evaluationFormulas(main,graphs,target,(...args)=>selectGraph(...args));
 const columns=el('div','evaluation-work-evidence'),text=el('section','evaluation-text-panel'),chart=el('section','evaluation-chart-panel');columns.append(text,chart);main.append(columns);
 text.append(el('h3','','변경 문장과 근거'));
 const targetNode=graphs.original?.nodes.find(n=>n.fact_id===target),targetButton=button(target?(evidence.plan?.axis==='EA'?'삭제 대상: ':'변경 대상: ')+target+' = '+evaluationNodeValue(targetNode||{}):'원본 문항',()=>chart.dispatchEvent(new Event('evaluation-target')),'evaluation-target-button');
 if(target)text.append(targetButton);
 const edits=evidence.blocks.filter(b=>b.kind==='change');
 for(const [index,edit] of edits.entries()){
  const section=el('div','evaluation-edit');section.append(el('h4','','변경 '+(index+1)+(edit.before.trim()&&edit.after.trim()?' · 교체':edit.before.trim()?' · 삭제':' · 추가')));
  if(edit.before.trim())section.append(el('div','prose diff-del',edit.before));
  if(edit.after.trim()){const added=el('div','prose');evaluationMarkedText(added,evidence,edit.after);section.append(added);}text.append(section);
 }
 if(!edits.length)text.append(el('p','small',variant?(evidence.current?'원본과 생성 본문 사이에 변경이 없습니다.':'생성 본문이 저장되어 있지 않습니다.'):'원문을 확인하고 판정해 주세요.'));
 if(evidence.plan?.intent?.relation){const r=evidence.plan.intent.relation;text.append(el('p','evaluation-relation','추가 관계: '+(r.operand?.value??'미기록')+' '+({multiply:'×',divide:'÷'}[r.operation]||r.operation)+' '+r.factor));}
 const fail=evidence.record?.status==='FAIL';if(fail)text.append(el('p','evaluation-warning','자동 검사 실패 · '+(evidence.record.reason||'저장된 검사 실패')));
 evaluationContext(text,evidence,row,variant);
 chart.append(el('h3','','계산 그래프 · A 원본 / B 변경'));
 const controller=evaluationDrawGraph(chart,graphs.original,graphs.changed,target,(active,refs)=>{
  targetButton.classList.toggle('ea-deletion-active',active);
  for(const edit of text.querySelectorAll('.evaluation-edit'))edit.classList.toggle('evaluation-edit-active',active);
  for(const token of formulas.querySelectorAll('[data-node-id]'))token.classList.toggle('graph-formula-active',refs?.some(ref=>ref.side===token.dataset.side&&ref.node.sourceIds.includes(token.dataset.nodeId))||false);
 });selectGraph=controller?.selectReference||(()=>{});
 for(const edit of text.querySelectorAll('.evaluation-edit'))edit.onclick=()=>chart.dispatchEvent(new Event('evaluation-target'));
}
function evaluationDraftNote(note){
 const current=evaluationCurrent();if(!current)return;
 const key=evaluationRecordKey(DATA.batch.name,current.case,current.variant),saved=evaluationState.records.get(key)||{};
 evaluationState.records.set(key,{...saved,run:DATA.batch.name,...current,decision:saved.decision||null,comment:note,checklist:saved.checklist||{},confirmed:saved.confirmed||false,updated_at:new Date().toISOString()});evaluationRemember();
}
function evaluationChoose(decision){
 if(!evaluationState.reviewer.trim()){evaluationState.status.textContent='판정을 저장하려면 평가자 이름을 입력해 주세요.';$('evaluation-reviewer').focus();return;}
 const current=evaluationCurrent();if(!current||evaluationState.loading)return;
 const key=evaluationRecordKey(DATA.batch.name,current.case,current.variant),saved=evaluationState.records.get(key)||{};
 evaluationState.records.set(key,{...saved,run:DATA.batch.name,...current,decision,comment:$('evaluation-note').value,checklist:saved.checklist||{},confirmed:true,updated_at:new Date().toISOString()});evaluationRemember();
 const next=evaluationState.autoNext?evaluationNextEntry(evaluationEntries(),current,evaluationState.filter,true):null;
 evaluationState.feedback=current.case+' · '+(evaluationTypes.find(([v])=>v===current.variant)?.[1]||'Preparation')+' '+evaluationJudgments[decision].label+' 저장됨';
 const counts=evaluationCounts(evaluationEntries(evaluationBatch(),'case'));if(counts.done===counts.total)evaluationState.feedback+=' · 이 실행의 평가를 모두 마쳤습니다.';
 if(next)evaluationJump(next);else render();
}
function evaluationRenderDecision(parent){
 parent.replaceChildren();const current=evaluationCurrent();if(!current)return;
 const saved=evaluationSaved(current.case,current.variant),note=el('textarea');note.id='evaluation-note';note.setAttribute('aria-label','평가 주석');note.placeholder='주석 (선택) · N으로 입력 · Enter로 저장 · Shift+Enter 줄바꿈';note.value=saved?.comment||'';
 note.oninput=()=>evaluationDraftNote(note.value);note.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();evaluationDraftNote(note.value);note.blur();evaluationState.status.textContent='주석 저장됨';}};
 const choices=el('div','evaluation-decisions');for(const [index,decision] of Object.keys(evaluationJudgments).entries()){
  const info=evaluationJudgments[decision],b=button(info.label+' ('+(index+1)+')',()=>evaluationChoose(decision),'evaluation-choice '+info.className+(saved?.confirmed&&saved.decision===decision?' chosen':''));b.setAttribute('aria-keyshortcuts',String(index+1));b.disabled=!!evaluationState.loading;choices.append(b);
 }
 const navigation=el('div','evaluation-decision-nav'),automatic=el('label',''),check=el('input');check.type='checkbox';check.checked=evaluationState.autoNext;check.onchange=()=>evaluationState.autoNext=check.checked;automatic.append(check,el('span','','판정 후 다음 미평가'));
 const previous=button('← 이전',()=>evaluationNavigate(-1)),next=button('다음 →',()=>evaluationNavigate(1));navigation.append(previous,next,automatic);
 parent.append(choices,note,navigation,el('p','evaluation-feedback',evaluationState.feedback||'1·2·3 판정 · Q/E 필터된 문제 이전·다음 · A/D 유형 이전·다음 · v 다음 유보·실패 / Shift+V 이전 · N 주석'));
}
function evaluationRenderWorkspace(){
 const side=$('evaluation-sidebar'),main=$('evaluation-main'),footer=$('evaluation-decision');if(!side||!main)return;
 document.body.classList.toggle('evaluation-original-view',!!evaluationState.original);
 const returnButton=$('evaluation-return');if(returnButton)returnButton.hidden=!evaluationState.original;
 if(evaluationState.original){
  const row=rows.find(r=>r.id===selected);renderDetail(row);
  if(row?.run.summary_only)evaluationState.loading=DATA.batch.name+'|'+row.sample.id;
  else if(evaluationState.originalFocus){evaluationState.originalFocus=false;requestAnimationFrame(()=>document.querySelector('#detail .problem-selection')?.scrollIntoView({block:'start'}));}
  return;
 }
 if(typeof floatingReviewCleanup==='function')floatingReviewCleanup();
 $('detail')?.replaceChildren();
 if(typeof indexDisplayedFiles==='function')indexDisplayedFiles(null);
 const entry=evaluationBatch().cases.find(c=>c.case===evaluationCurrent()?.case);
 if(entry&&!entry.variants.includes(window.preparationVariant))window.preparationVariant=entry.variants[0]||null;
 evaluationRenderSide(side);main.replaceChildren();const row=rows.find(r=>r.id===selected);
 if(!row){main.append(el('p','empty','포함된 평가 문항이 없습니다.'));footer.replaceChildren();return;}
 if(row.run.summary_only){
  const key=DATA.batch.name+'|'+row.sample.id;main.append(el('p','evaluation-loading',row.sample.id+' · 평가 자료를 읽고 있습니다.'));
  if(evaluationState.loading!==key){evaluationState.loading=key;evaluationLoadCase(row.sample.id);}evaluationRenderDecision(footer);return;
 }
 evaluationState.loading=null;evaluationRenderEvidence(main,row,window.preparationVariant);evaluationRenderDecision(footer);
}
function evaluationMountWorkspace(){
 Object.assign(evaluationState,{mode:'case',filter:'todo',search:'',autoNext:true,loading:null,feedback:'',original:false,originalFocus:false,originalReturn:null});
 const workspace=el('div','evaluation-workspace');workspace.id='evaluation-workspace';
 const side=el('aside','evaluation-sidebar');side.id='evaluation-sidebar';const main=el('main','evaluation-main');main.id='evaluation-main';const footer=el('section','evaluation-decision');footer.id='evaluation-decision';footer.setAttribute('aria-label','평가 판정과 주석');workspace.append(side,main,footer);document.body.append(workspace);
 render=evaluationRenderWorkspace;
 document.addEventListener('keydown',event=>{
  if(event.defaultPrevented||event.isComposing||event.ctrlKey||event.metaKey||event.altKey||document.querySelector('dialog[open]'))return;
  if(event.target.closest?.('input:not([type=checkbox]):not([type=radio]),textarea,select,[contenteditable="true"],[role="textbox"]'))return;
  const key=/^Key[A-Z]$/.test(event.code||'')?event.code.slice(3).toLowerCase():event.key.toLowerCase();
  if(['q','e','a','d'].includes(key)){event.preventDefault();event.stopImmediatePropagation();if(key==='q'||key==='e')evaluationNavigateProblem(key==='q'?-1:1);else evaluationNavigateType(key==='a'?-1:1);return;}
  if(key==='v'){event.preventDefault();event.stopImmediatePropagation();evaluationNavigateReviewIssue(event.shiftKey||event.key==='V'?-1:1);return;}
  if(evaluationState.original)return;
  const number=/^(?:Numpad|Digit)([123])$/.exec(event.code||'')?.[1]||(/^[123]$/.test(event.key)?event.key:null);
  if(number){event.preventDefault();event.stopImmediatePropagation();if(!event.repeat)evaluationChoose(['APPROVED','REJECTED','PENDING'][Number(number)-1]);return;}
  if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();event.stopImmediatePropagation();evaluationNavigate(event.key==='ArrowLeft'?-1:1);}
  if(event.code==='KeyN'||event.key.toLowerCase()==='n'){event.preventDefault();event.stopImmediatePropagation();$('evaluation-note')?.focus();}
 },true);
}
