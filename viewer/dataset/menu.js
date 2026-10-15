function preserveReviewScroll(action){
 const x=window.scrollX,y=window.scrollY;
 action();
 const restore=()=>{window.scrollTo({left:x,top:y,behavior:'instant'});window.dispatchEvent(new Event('scroll'));};
 restore();requestAnimationFrame(restore);
}
let floatingReviewCleanup=null;
function mountFloatingReview(selection,gen,controls){
 if(floatingReviewCleanup)floatingReviewCleanup();
 const bar=el('nav','floating-type-bar');bar.setAttribute('aria-label','현재 유형 및 유형 이동');
 for(const source of gen.querySelectorAll('[data-variant-path]')){
  const copy=globalThis.FinarchI18n?.clone(source)||source.cloneNode(true);copy.onclick=()=>source.click();bar.append(copy);
 }
 const stageLine=el('div','floating-stage-line');
 for(const source of selection.querySelectorAll('.preparation-stage-tabs button')){const copy=globalThis.FinarchI18n?.clone(source)||source.cloneNode(true);copy.onclick=()=>source.click();stageLine.append(copy);}
 bar.append(stageLine);
 document.body.append(bar);
 let frame=0;
 const update=()=>{
  frame=0;
  if(!selection.isConnected){floatingReviewCleanup?.();return;}
  const bounds=selection.getBoundingClientRect();
  const left=Math.max(8,bounds.left),width=Math.max(0,Math.min(innerWidth-8,bounds.right)-left);
  controls.style.left=left+'px';controls.style.width=width+'px';
  bar.style.left=left+'px';bar.style.width=width+'px';
  bar.hidden=gen.getBoundingClientRect().bottom>0;
 };
 const schedule=()=>{if(!frame)frame=requestAnimationFrame(update)};
 window.addEventListener('scroll',schedule,true);window.addEventListener('resize',schedule);
 floatingReviewCleanup=()=>{
  window.removeEventListener('scroll',schedule,true);window.removeEventListener('resize',schedule);
  if(frame)cancelAnimationFrame(frame);bar.remove();floatingReviewCleanup=null;
 };
 schedule();
}
function reviewNavigateType(direction){
 const buttons=[...document.querySelectorAll('#detail [data-type-navigation]')];
 const target=buttons.find(b=>b.dataset.typeNavigation===String(direction));
 if(target&&!target.disabled)target.click();
}
document.addEventListener('keydown',event=>{
 if(DATA.evaluation)return;
 if(event.defaultPrevented||event.isComposing||event.ctrlKey||event.metaKey||event.altKey||document.querySelector('dialog[open]'))return;
 if(event.target.closest?.('input:not([type=radio]):not([type=checkbox]),textarea,select,[contenteditable="true"],[role="textbox"]'))return;
 const key=/^Key[A-Z]$/.test(event.code||'')?event.code.slice(3).toLowerCase():event.key.toLowerCase();
 if(!['w','s','a','d','b','z','c','x','q','e','1','2','3','v'].includes(key))return;
 if(!document.querySelector('#detail .problem-selection'))return;
 event.preventDefault();
 if(event.repeat&&['x','q','e','1','2','3','v'].includes(key))return;
 if(key==='v'){
  if(DATA.evaluation)evaluationSetView('review',false);
  if(window.preparationVariant)window.generationStage='05-human-review';
  else window.preparationStage='07-human-review';
  render();document.querySelector('#detail .review-content-anchor')?.scrollIntoView({block:'start',behavior:'smooth'});return;
 }
 if(key==='q'||key==='e'){
  const groups=groupProblems(filtered()),current=rows.find(r=>r.id===selected);
  const index=groups.findIndex(group=>group.some(r=>r.run.path===current?.run.path));
  const group=groups[index+(key==='q'?-1:1)];if(!group)return;
  const next=group.find(r=>r.axis==='ANSWER')||group[0];
  if(window.preparationVariant){window.preparationVariant='01-ic-value-before';window.generationStage='01-perturbation';}
  selected=next.id;render();return;
 }
 if(key==='z'||key==='c'){
  const buttons=[...document.querySelectorAll('#detail .preparation-stage-tabs button')];
  const index=buttons.findIndex(b=>b.classList.contains('active'));
  const target=buttons[index+(key==='z'?-1:1)];if(target&&!target.disabled)target.click();return;
 }
 if(['1','2','3'].includes(key)){
  const value={'1':'APPROVED','2':'REJECTED','3':'PENDING'}[key];
  const choice=document.querySelector('#detail input[data-review-choice="'+value+'"]');
  if(choice&&!choice.disabled)choice.click();return;
 }
 if(key==='x'){
  const save=[...document.querySelectorAll('#detail button')].find(b=>(globalThis.FinarchI18n?.originalText(b)||b.textContent).trim()===((event.key==='X'||event.shiftKey)?'전체 판정 저장 (X)':'판정 저장 (x key)'));
  if(save&&!save.disabled)save.click();return;
 }
 if(key==='a'||key==='d'||key==='b'){reviewNavigateType(key==='a'?-1:1);return;}
 document.querySelector(key==='w'?'#detail .problem-selection':'#detail .review-content-anchor')?.scrollIntoView({block:'start',behavior:'smooth'});
});
function confirmFailedRecheck(run,phase,count){
 return new Promise(resolve=>{
  const dialog=el('dialog','recheck-confirm'),title=el('h2','','실패건 재검토를 진행할까요?');
  title.id='recheck-confirm-title';dialog.setAttribute('aria-labelledby',title.id);
  dialog.append(title,el('p','',run+' · '+(phase==='preparation'?'Preparation':'Generation')+' · 현재 실패 '+count+'건'),el('p','banner','LLM을 다시 호출하므로 API 사용 비용이 발생합니다. 정말 진행하시겠습니까?'));
  let settled=false;
  const finish=value=>{if(settled)return;settled=true;dialog.close();dialog.remove();resolve(value)};
  const no=button('No · 취소',()=>finish(false)),yes=button('Yes · 재검토 시작',()=>finish(true));
  no.type=yes.type='button';no.autofocus=true;const actions=el('div','toolbar');actions.append(no,yes);dialog.append(actions);
  dialog.addEventListener('cancel',e=>{e.preventDefault();finish(false)});
  dialog.addEventListener('close',()=>finish(false));
  document.body.append(dialog);dialog.showModal();no.focus();
 });
}
function failedRecheckButton(phase){
 const state=DATA.batch?.rechecks||{}, count=state[phase]||0;
 const b=button('실패건 재검토'+(count?' ('+count+')':''),async()=>{
  b.disabled=true;
  const run=DATA.batch.name;
  if(!await confirmFailedRecheck(run,phase,count)){b.disabled=!count||!!DATA.batch?.rechecks?.busy;return;}
  try{const response=await fetch('/api/recheck',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run,phase})});const data=await response.json();if(!response.ok)throw new Error(data.error||'재검토 요청 실패');location.reload();}
  catch(error){alert(error.message);b.disabled=false;}
 },'recheck-button recheck-'+phase);
 b.disabled=!count||!!state.busy;
 b.title=state.busy?'재검토 진행 중':`현재 실행의 ${count}개 실패 항목만 재검토합니다. API 사용 비용이 발생합니다.`;
 return b;
}
function reviewDefaultDecision(row,variant){
 const status=variant?row.run.generation?.[variant+'/05-human-review/01-result.json']?.automatic_status:row.run.artifacts['run.json']?.status||row.status;
 return ['FAIL','ERROR'].includes(status)?'REJECTED':!variant&&status==='PASS'&&!row.run.approval_blocker?'APPROVED':'PENDING';
}
function updateReviewTabColor(panel,decision){
 const tab=panel.closest('#detail')?.querySelector('.preparation-stage-tabs [data-human-review]');
 if(!tab)return;
 tab.classList.remove('review-approved','review-rejected','review-pending','tab-failed');
 tab.classList.add('review-'+({APPROVED:'approved',REJECTED:'rejected'}[decision]||'pending'));
 tab.dataset.reviewDecision=decision;
}
function renderPreparationDetail(root,row){
 const refresh=()=>{root.replaceChildren();renderPreparationDetail(root,row)};
 if(row.run.artifacts['run.json']?.stop_after==='pot')root.append(el('div','banner','POT까지 실행하도록 지정된 문항입니다. 실제 실행·검사 여부는 아래 저장 기록을 확인하십시오.'));
 const countsContent=el('div');
 if(row.run.round)countsContent.append(el('p','small',`Preparation 실제 차수: ${row.run.round}${row.run.carried_round?' · 선택 차수에는 재실행하지 않아 이전 결과를 표시합니다.':''}`));
 const progress=DATA.batch?.execution_progress;
 if(progress){
  const box=el('section','panel'),finished=progress.status==='COMPLETED',summary=DATA.batch.summary;
  const prepCount=summary?.processed??progress.processed_cases,planned=summary?.planned??progress.planned_cases;
  const phase=progress.phase==='PREPARATION_REPAIR'?`Preparation ${progress.round||''}차 보완`:progress.phase;
  const generation=finished&&Number.isFinite(progress.passed_types)?` · Generation 통과 ${progress.passed_types} · 실패 ${progress.failed_types}`:progress.phase==='GENERATION'&&progress.round?` · Generation ${progress.round} ${progress.completed_types_this_round??0}개 유형 처리`:'';
  box.style.cssText='padding:5px 8px;margin:5px 0;font-size:11px';box.style.borderColor=progress.status==='RUNNING'?'#16826c':'#687e91';
  box.append(el('h3','',progress.status==='RUNNING'?'● 작업 진행 중':progress.status==='ERROR'?'실행 오류':'실행 완료'),el('p','',`${phase} · Preparation ${prepCount}/${planned}건${generation}`),el('p','small','프로세스 갱신: '+progress.heartbeat_at));
  if(progress.reason)box.append(el('p','',progress.reason));root.append(box);
 }
 finalGenerationCounts(countsContent);
 pipelineRoundSummary(countsContent);
 const overview=el('div','viewer-group preparation-overview');overview.append(viewerDisclosure('preparation-round','Preparation 차수 안내',countsContent));root.append(overview);
 if(!DATA.evaluation&&!DATA.original)renderFailureAnalysisOverview(root);
 const excluded=DATA.batch?.preparation_failure_report;
 if(excluded){const box=el('details');box.append(el('summary','',`Preparation 최초 실패 ${excluded.excluded_count}건 · 원인과 수정 방향`));for(const [name,count] of Object.entries(excluded.groups))box.append(el('p','',`${name}: ${count}건`));for(const item of excluded.cases){const detail=el('details');detail.append(el('summary','',item.case+' · '+item.group),el('p','',item.question),el('p','',item.error_code),el('p','',item.observed_issue),el('p','',item.proposed_resolution));const link=el('a','','이 문항 열기');link.href='?run='+encodeURIComponent(DATA.batch.name)+'&case='+encodeURIComponent(item.case);detail.append(link);box.append(detail);}box.append(el('p','small','최초 실패 분석입니다. 보완 후 판정은 아래 보완 결과와 각 문항의 현재 단계에서 확인합니다. 최초 원응답과 판정은 보존됩니다.'));root.append(box);}
 const repairs=DATA.batch?.preparation_repair_results;
 if(repairs){const box=el('details');box.append(el('summary','',`Preparation 보완 1회 · ${repairs.processed}/${repairs.planned}건 · 상세`));const table=el('table','repair-result-table');const head=el('tr');['문항','최초 실패','보완 결과','현재 사유'].forEach(x=>head.append(el('th','',x)));table.append(head);for(const item of repairs.results){const tr=el('tr');[item.input_id,item.previous_failure,item.status,item.reason].forEach(x=>tr.append(el('td','',String(x||''))));tr.style.color=item.status==='PASS'?'#126849':'#ae2323';table.append(tr);}box.append(table,el('p','small','통과 문항은 Generation으로 이어집니다. 실패 원응답·이전 판정은 repair-history/01-original에 보존합니다.'));root.append(box);}
 if(!('preparationVariant' in window)){const requested=new URLSearchParams(location.search).get('variant');window.preparationVariant=/^(01-ic-value-before|02-ic-value-after|03-ic-source-type-1|04-ic-source-type-2|05-ic-relation|06-ea-earlier-input|07-ea-later-input)$/.test(requested||'')?requested:null;}
 const variant=window.preparationVariant||null,artifacts=variant?(row.run.generation||{}):row.run.artifacts;
 const selection=el('div','viewer-group problem-selection');selection.setAttribute('aria-label','문제 및 단계 선택');root.append(selection);
 const issueCount=(row.status==='FAIL'?1:0)+(DATA.batch?.generation_overview||[]).filter(x=>x.case===row.sample.id&&x.record?.status==='FAIL').length;const identity=el('div');identity.style.cssText='display:flex;gap:12px;align-items:center;margin:10px 0;font-weight:700';const errors=el('span','','오류 '+issueCount+'개');errors.style.color='#b42318';errors.title='Preparation 실패 1건과 Generation 유형별 실패 수의 합계';identity.append(el('span','','문제번호 '+row.sample.id),el('span','small','선택 차수 '+(DATA.batch?.round||row.run.requested_round||row.run.round||'기록 없음')),errors);selection.append(identity);const external=externalKnowledgeModel(row);if(external.tags.length){selection.classList.add('external-knowledge-case');identity.append(el('strong','external-knowledge-heading',external.tags.join(' / ')));}const confirmed=row.run.external_knowledge;if(confirmed&&typeof confirmed.used==='boolean'){const badge=el('span','consolidated-knowledge '+(confirmed.used?'confirmed':'unconfirmed'),confirmed.used?'취합 외부사용 확인 · '+(confirmed.used_types||[]).join(' / '):'취합 외부사용 조건 미충족');badge.title='최종 취합 결과 기준입니다. 미충족은 외부정보를 쓰지 않았다는 증명이 아닙니다.';identity.append(badge);}
 const prep=el('div','panel'),gen=el('div','panel');prep.append(el('h3','','Preparation'),button('ANSWER',()=>{window.preparationVariant=null;render()},!variant?'active':''));gen.append(el('h3','','Generation'));prep.classList.add('phase-preparation');gen.classList.add('phase-generation');if(!DATA.evaluation&&!DATA.original)prep.append(failureAnalysisButton('preparation'),failedRecheckButton('preparation'));
 const types=[['01-ic-value-before','IC-VALUE 앞'],['02-ic-value-after','IC-VALUE 뒤'],['03-ic-source-type-1','IC-SOURCE Type 1'],['04-ic-source-type-2','IC-SOURCE Type 2'],['05-ic-relation','IC-RELATION'],['06-ea-earlier-input','EA 01'],['07-ea-later-input','EA 02']];
 for(const [path,label] of types){const files=Object.entries(row.run.generation||{}).filter(([key])=>key.startsWith(path+'/')),exists=files.length>0,failed=files.some(([,value])=>['FAIL','ERROR'].includes(value?.status));const b=button(label,()=>preserveReviewScroll(()=>{window.preparationVariant=path;render()}),(variant===path?'active ':'')+(failed?'tab-failed':''));b.dataset.variantPath=path;b.disabled=!exists;b.title=exists?'저장된 실행 기록 보기':DATA.original?'내보내기 제외: 최종 실패·미완료 또는 저장 기록 없음':'저장된 실행 기록이 없습니다.';gen.append(b)}
 if(!DATA.evaluation&&!DATA.original)gen.append(failureAnalysisButton('generation'),failedRecheckButton('generation'));
 if(DATA.batch?.interruption)prep.append(el('p','banner','Preparation 중단됨 · '+DATA.batch.interruption.reason));
 if(DATA.batch?.generation_interruption)gen.append(el('p','banner','Generation 중단됨 · '+DATA.batch.generation_interruption.reason));
 const gate=DATA.batch?.review_gate;gen.append(el('p','small',DATA.batch?.execution_progress?(gate?.allow_generation?'위임한 Preparation 점검 완료 · 통과 문항을 Generation에서 사용합니다.':'위임한 Preparation 점검 진행 중 · 전체 처리 후 통과 문항을 자동으로 넘깁니다.'):(gate?.allow_generation?'전체 사람 검토 완료 · 승인 문항을 생성 입력으로 사용할 수 있습니다.':'전체 원본의 사람 검토 완료 전입니다. 저장된 생성 기록이 있으면 열람할 수 있습니다.')));const groups=el('div','pipeline-groups');groups.style.cssText='display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;align-items:start';for(const group of [prep,gen]){group.style.cssText='margin:0 0 10px;padding:10px';group.querySelector('h3').style.cssText='margin:0 0 6px;font-size:14px';}groups.append(prep,gen);selection.append(groups);
 const stages=variant?[['01-perturbation','그래프 변경'],['02-generate-text','문장 생성'],['03-validation','검증'],['04-exception-handler','오류 진단·피드백'],['05-human-review','사람 검토']]:[['01-source','원문 비교'],['02-review','원본 검토'],['03-calculation','계산과 정답'],['04-graph','계산 그래프'],['05-verification','계산 검증'],['06-exception-handler','오류 진단·피드백'],['07-human-review','사람 검토']];
 const requestedStage=((variant?window.generationStage:window.preparationStage)||new URLSearchParams(location.search).get('stage'))?.replace(/^02-(audit-meaning|review-and-correct)$/, '02-review'),selectedStage=stages.some(([path])=>path===requestedStage)?requestedStage:(variant?'01-perturbation':row.run.artifacts['run.json']?.stop_after==='pot'?'03-calculation':'02-review'),prefix=(variant?variant+'/':'')+selectedStage+'/',nav=el('nav','tabs preparation-stage-tabs'),panel=el('div','panel');
 for(const [path,title] of stages){const failed=stageFailureEntries(row,variant,path).length>0;const reviewState=path.endsWith('human-review')?(artifacts[(variant?variant+'/':'')+path+'/02-record-decision/decision.json']?.decision||reviewDefaultDecision(row,variant)):null;const reviewClass=reviewState?' review-'+({APPROVED:'approved',REJECTED:'rejected'}[reviewState]||'pending'):'';const stageButton=button(path+' · '+title,()=>preserveReviewScroll(()=>{if(DATA.evaluation)evaluationSetView('stages',false);if(variant)window.generationStage=path;else window.preparationStage=path;refresh()}),(path===selectedStage?'active ':'')+(failed?'tab-failed':'')+reviewClass);if(reviewState){stageButton.dataset.humanReview='true';stageButton.dataset.reviewDecision=reviewState;stageButton.classList.remove('tab-failed');}appendFeedbackBadge(stageButton,stageFeedbackState(row,variant,path));nav.append(stageButton)}selection.append(nav);if(!DATA.evaluation)selection.append(el('p','small','초록: feedback을 포함해 호출 / 회색: 이전 산출물 재사용 · 전송 기록 불충분: 피드백 전달 미확인'));root.append(panel);

 const available=types.filter(([path])=>Object.keys(row.run.generation||{}).some(key=>key.startsWith(path+'/')));
 const position=available.findIndex(([path])=>path===variant);
 const controls=el('nav','review-navigation');controls.setAttribute('aria-label','이전·다음 유형 이동');
 for(const direction of [-1,1]){
  const target=variant?available[position+direction]:(direction===1?available[0]:null);
  const move=button(direction===-1?'←':'→',()=>{
   if(!target)return;
   preserveReviewScroll(()=>{window.preparationVariant=target[0];render();});
  });
  move.dataset.typeNavigation=String(direction);move.disabled=!target;
  move.setAttribute('aria-label',direction===-1?'이전 유형':'다음 유형');
  move.title=target?target[1]:'이동할 유형이 없습니다.';
  controls.append(move);
  
 }
 panel.append(controls);
 mountFloatingReview(selection,gen,controls);
 if(DATA.evaluation&&evaluationState.view==='review'){renderEvaluationCase(panel,row,variant);return;}
 renderMenuGuide(panel,row,variant,selectedStage);
 const anchor=el('div','review-content-anchor');panel.append(anchor);
 renderSelectedFailureAnalysis(panel,row,variant,selectedStage);
 const content=el('section','stage-content');content.setAttribute('aria-label','비교·검토 화면');panel.append(content);
 if(!variant){renderPreparationContent(content,row,selectedStage);decorateExternalKnowledge(content,row);}else renderGenerationContent(content,row,variant,selectedStage);
 if(DATA.evaluation)return;
 const files=el('section','stage-artifacts');files.setAttribute('aria-label','단계 결과 파일');panel.append(files);renderStageFiles(files,row,variant,selectedStage);

}

// Save the current form decision to every generated type, with each saved snapshot.
function appendBulkReview(panel,row,readForm){
 const variants=['01-ic-value-before','02-ic-value-after','03-ic-source-type-1','04-ic-source-type-2','05-ic-relation','06-ea-earlier-input','07-ea-later-input'];
 const message=el('p','small');let running=false;
 const available=variants.every(v=>row.run.generation_snapshots?.[v]&&row.run.generation?.[v+'/05-human-review/01-result.json']);
 const save=button('전체 판정 저장 (X)',async()=>{
  if(running)return;
  const form=readForm();
  if(!form.reviewer.trim()||(form.decision!=='APPROVED'&&!form.reason.trim())||(form.decision==='APPROVED'&&!Object.values(form.checklist).every(Boolean))){message.textContent='검토자·필수 판정 이유·검토 항목을 확인해 주세요.';return;}
  running=true;save.disabled=true;const done=[];let failed='';
  // Capture run/case and form before awaiting; changing the UI must not change the targets.
  const run=DATA.batch.name,caseName=row.sample.id;
  try{
   for(const variant of variants){
    message.textContent=`전체 판정 저장 중 · ${done.length}/7`;
    const response=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run,case:caseName,variant,round:row.run.generation_origins?.[variant]||row.run.round,review:{...form,snapshot_sha256:row.run.generation_snapshots[variant]}})});
    const result=await response.json();if(!response.ok)throw Error(variant+' · '+(result.error||'저장 실패'));done.push(variant);
   }
  }catch(error){failed=error.message;}
  finally{running=false;message.textContent=failed?`${done.length}/7 저장됨 · 중단: ${failed} · 최신 자료를 다시 읽은 뒤 재시도해 주세요.`:'7개 유형의 판정을 모두 저장했습니다.';if(!failed)window.loadDetailCase?.(caseName,true);}
 });
 save.disabled=!DATA.live||!available;save.setAttribute('aria-keyshortcuts','Shift+X');
 panel.append(save,el('p','small','현재 선택한 판정·검토자·이유·확인 항목을 IC-VALUE 앞부터 EA 02까지 7개 유형에 동일하게 저장합니다. 기존 판정도 변경됩니다. Preparation 판정은 별도 저장합니다.'),message);
 if(!available)message.textContent='7개 유형의 검토 자료가 모두 저장된 문항에서 사용할 수 있습니다.';
}
