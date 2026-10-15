function renderPreparationReview(panel,row){
 const saved=row.run.artifacts['07-human-review/02-record-decision/decision.json']||{},reviewer=el('input'),reason=el('textarea'),message=el('p','small');
 const defaultDecision=reviewDefaultDecision(row,null);
 panel.append(el('h3','','원본 데이터 사용 여부 · 사람 판정'),el('p','',saved.decision||({APPROVED:'Accept · 승인',REJECTED:'Reject · 오류로 제외',PENDING:'Pending · 검토 대기'}[defaultDecision]+' 선택 · 저장 전')));
 const answerChange=answerRevision(row);if(answerChange.revision)panel.append(el('p','banner',`03 골드 수정 · 원본 ${answerChange.original} → 수정정답 ${answerChange.current} (${answerChange.revision}차 수정)`));
 const evidenceStage=row.run.artifacts['run.json']?.correction_ref||'03-calculation/05-resolve-mismatch';
 const evidence=row.run.artifacts[evidenceStage+'/03-LLM-review-evidence/01-request/03-result.json']?.data;
 if(evidence){panel.append(el('h4','','계산 불일치 검토'),el('p','',evidence.conclusion+' · '+evidence.reason));jsonBox(panel,'원문 인용과 검토 근거',evidence.evidence);}
 const note=row.run.artifacts['07-human-review/review-note.json'];if(note)panel.append(el('p','banner',note.reason));
 const correction=row.run.artifacts['run.json']?.correction_ref;if(correction)jsonBox(panel,'보정 근거와 변경 전후',row.run.artifacts[correction+'/04-apply-correction/01-result.json']);
 const checklist=el('div','review-checklist'),checks={};
 for(const [key,title] of [['02-review','02 원본 검토'],['03-calculation','03 계산·정답'],['04-graph','04 계산 그래프'],['05-verification','05 계산 검증']]){
  const label=el('label','check'),input=el('input');input.type='checkbox';input.checked=stageFailureEntries(row,null,key).length?false:saved.checklist?.[key]??(key==='02-review'?(saved.checklist?.['02-review-and-correct']??saved.checklist?.['02-audit-meaning']):undefined)??true;checks[key]=input;label.append(input,el('span','',title));checklist.append(label);
 }panel.append(checklist);
 reviewer.placeholder='검토자';reviewer.setAttribute('aria-label','검토자');reviewer.value=saved.reviewer||'user';reason.placeholder='판정 이유';reason.setAttribute('aria-label','판정 이유');reason.value='';panel.append(reviewer,reason);
 let selectedDecision=saved.decision||defaultDecision;
 updateReviewTabColor(panel,selectedDecision);
 const choices=el('div','review-checklist');
 for(const [value,title] of [['APPROVED','Accept 승인 (1 key)'],['REJECTED','Reject 제외 (2 key)'],['PENDING','Pending 검토 대기 (3 key)']]){
 const label=el('label','check'),input=el('input');input.type='radio';input.name='preparation-review-decision';input.value=value;input.dataset.reviewChoice=value;input.setAttribute('aria-keyshortcuts',({APPROVED:'1',REJECTED:'2',PENDING:'3'})[value]);input.checked=value===selectedDecision;input.onchange=()=>{selectedDecision=value;updateReviewTabColor(panel,selectedDecision);updateReviewButtons();};label.append(input,el('span','',title));choices.append(label);
 }panel.append(choices);
 const reviewButtons={};
 function updateReviewButtons(){reason.required=selectedDecision!=='APPROVED';reason.placeholder=reason.required?'판정 이유 (필수)':'판정 이유 (선택)';for(const b of Object.values(reviewButtons)){const value=selectedDecision;b.disabled=!DATA.live||!reviewer.value.trim()||(value==='APPROVED'?((row.run.carried_round&&row.run.round!==row.run.preparation_list?.active_round)||!Object.values(checks).every(x=>x.checked)):!reason.value.trim());}}
 {const b=button('판정 저장 (x key)',async()=>{const value=selectedDecision;
 b.disabled=true;try{const response=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run:DATA.batch.name,case:row.sample.id,round:row.run.round,review:{decision:value,reviewer:reviewer.value,reason:reason.value,snapshot_sha256:row.run.snapshot_sha256,checklist:Object.fromEntries(Object.entries(checks).map(([key,input])=>[key,input.checked]))}})});const result=await response.json();if(!response.ok)throw Error(result.error);message.textContent='판정을 저장했습니다. 최신 기록을 다시 읽습니다.';window.loadDetailCase?.(row.sample.id,true);}catch(error){message.textContent='저장하지 못했습니다: '+error.message;}finally{updateReviewButtons();}
 });reviewButtons.save=b;panel.append(b)}
 appendBulkReview(panel,row,()=>({decision:selectedDecision,reviewer:reviewer.value,reason:reason.value,checklist:Object.fromEntries(Object.entries(checks).map(([key,input])=>[key,input.checked]))}));
 reviewer.oninput=reason.oninput=updateReviewButtons;Object.values(checks).forEach(input=>input.onchange=updateReviewButtons);updateReviewButtons();
 panel.append(el('p','small','승인은 검토 항목 확인 후 이유 없이 가능합니다. 제외·검토 대기는 판정 이유가 필요합니다.'));
 if(row.run.approval_blocker)panel.append(el('p','small','자동 검사 오류 (Accept 판정과 별도로 유지됩니다): '+row.run.approval_blocker));panel.append(message);
}
