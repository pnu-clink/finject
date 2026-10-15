function renderGenerationReview(panel,row,variant){
 renderEAInverseReview(panel,row,variant);
 const a=row.run.generation||{};
  const review=a[variant+'/05-human-review/01-result.json'];
  if(review){panel.append(el('h2','','최종 생성 결과 · 사람 검토'),badge(review.automatic_status));panel.append(el('p','small','자동 검사 결과이며 사람 판정은 별도입니다.'));}
  if(review){
   const saved=a[variant+'/05-human-review/02-record-decision/decision.json']||{},reviewer=el('input'),reason=el('textarea'),message=el('p','small');
   const defaultDecision=reviewDefaultDecision(row,variant);
   reviewer.placeholder='검토자';reviewer.value=saved.reviewer||'user';reason.placeholder='판정 이유';reason.value=saved.reason||'';panel.append(el('p','',saved.decision||defaultDecision),reviewer,reason);
 let selectedDecision=saved.decision||defaultDecision;
 updateReviewTabColor(panel,selectedDecision);
 const choices=el('div','review-checklist');
 for(const [value,title] of [['APPROVED','Accept 승인 (1 key)'],['REJECTED','Reject 제외 (2 key)'],['PENDING','Pending 검토 대기 (3 key)']]){
 const label=el('label','check'),input=el('input');input.type='radio';input.name='generation-review-decision';input.value=value;input.dataset.reviewChoice=value;input.setAttribute('aria-keyshortcuts',({APPROVED:'1',REJECTED:'2',PENDING:'3'})[value]);input.checked=value===selectedDecision;input.onchange=()=>{selectedDecision=value;updateReviewTabColor(panel,selectedDecision);update();};label.append(input,el('span','',title));choices.append(label);
 }panel.append(choices);
   const checks={},actions=[];
   const checklist=el('div','review-checklist');
   for(const [key,title] of [['01-perturbation','01 그래프 변경 확인'],['02-generate-text','02 문장 생성 확인'],['03-validation','03 검증 결과 확인']]){
    const label=el('label','check'),input=el('input');input.type='checkbox';input.checked=stageFailureEntries(row,variant,key).length?false:saved.checklist?.[key]??(key==='02-review-and-correct'?saved.checklist?.['02-audit-meaning']:undefined)??true;checks[key]=input;label.append(input,el('span','',title));checklist.append(label);
   }panel.append(checklist);
   const update=()=>actions.forEach(([b,d])=>b.disabled=!DATA.live||!reviewer.value.trim()||(selectedDecision!=='APPROVED'&&!reason.value.trim())||(selectedDecision==='APPROVED'&&(!Object.values(checks).every(c=>c.checked))));
   reason.oninput=reviewer.oninput=update;Object.values(checks).forEach(c=>c.onchange=update);panel.append(el('p','small','승인은 이유 없이 저장할 수 있습니다. 거절·대기는 이유가 필수입니다.'));
   {
    const b=button('판정 저장 (x key)',async()=>{const decision=selectedDecision;b.disabled=true;try{const response=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run:DATA.batch.name,round:row.run.generation_origins?.[variant]||DATA.batch.round,case:row.sample.id,variant,review:{decision,checklist:Object.fromEntries(Object.entries(checks).map(([k,v])=>[k,v.checked])),reviewer:reviewer.value,reason:reason.value,snapshot_sha256:row.run.generation_snapshots?.[variant]}})});const result=await response.json();if(!response.ok)throw Error(result.error);window.loadDetailCase?.(row.sample.id,true);}catch(error){message.textContent=error.message;}finally{update();}});actions.push([b]);update();panel.append(b);
   }panel.append(message);
   appendBulkReview(panel,row,()=>({decision:selectedDecision,reviewer:reviewer.value,reason:reason.value,checklist:Object.fromEntries(Object.entries(checks).map(([key,input])=>[key,input.checked]))}));
  }

}
