// Display saved cause categories and original evidence, without model calls.
let failureReviewCategory = '';
let failureReviewSearch = '';
let failureReviewType = '';
const failureTypeOrder = ['IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY','IC_RELATION_01','EA_01','EA_02'];
const failureTypeCodes = {
 IC_VALUE_01_BEFORE:'IC-v1', IC_VALUE_01_AFTER:'IC-v2',
 IC_SOURCE_A_ONLY:'IC-s1', IC_SOURCE_B_ONLY:'IC-s2',
 IC_RELATION_01:'IC-r', EA_01:'EA-v1', EA_02:'EA-v2'
};
const failureTypeNames = {
 IC_VALUE_01_BEFORE:'앞쪽에 다른 값 주장 추가', IC_VALUE_01_AFTER:'뒤쪽에 다른 값 주장 추가',
 IC_SOURCE_A_ONLY:'원래 주장에 출처 부착', IC_SOURCE_B_ONLY:'추가 주장에 출처 부착',
 IC_RELATION_01:'서로 맞지 않는 관계 추가', EA_01:'첫 번째 필수값 삭제', EA_02:'두 번째 필수값 삭제'
};
function failureTypeLabel(type){
 return failureTypeCodes[type]?`${failureTypeCodes[type]} · ${failureTypeNames[type]}`:failureTypeNames[type]||type;
}
function renderFailureReviewFlow(report){
 const summary=report.summary;
 const excluded=Number(summary.preparation_failed),clean=Number(summary.clean_cases),nonclean=Number(summary.generation_nonclean_cases);
 const entered=clean+nonclean,source=entered+excluded,typeCount=failureTypeOrder.length;
 const typeResults=report.generation_types||[];
 const passed=typeResults.reduce((total,row)=>total+Number(row.PASS),0);
 const failed=typeResults.reduce((total,row)=>total+Number(row.FAIL),0);
 const notEvaluated=typeResults.reduce((total,row)=>total+Number(row.NOT_EVALUATED),0);
 const partialPassed=passed-clean*typeCount;
 if(typeResults.length!==typeCount||[excluded,clean,nonclean,passed,failed,notEvaluated,partialPassed].some(value=>!Number.isInteger(value)||value<0)
    ||passed+failed+notEvaluated!==entered*typeCount||partialPassed+failed+notEvaluated!==nonclean*typeCount
    ||failed!==summary.generation_failed||notEvaluated!==summary.generation_not_evaluated){
  return el('p','banner','저장된 문항 수와 유형별 결과 수가 맞지 않아 흐름 집계를 표시할 수 없습니다.');
 }
 const fmt=value=>value.toLocaleString('ko-KR');
 const stat=(value,label,kind)=>{const box=el('div','failure-flow-stat '+kind);box.append(el('strong','',fmt(value)),el('span','',label));return box;};
 const phase=(title,input,inputLabel,left,leftLabel,leftKind,right,rightLabel,rightKind)=>{
  const card=el('section','failure-flow-phase');card.append(el('h3','',title));
  const line=el('div','failure-flow-line'),branches=el('div','failure-flow-branches');
  branches.append(stat(left,leftLabel,leftKind),stat(right,rightLabel,rightKind));
  line.append(stat(input,inputLabel,'failure-flow-input'),el('span','failure-flow-arrow','→'),branches);card.append(line);
  return card;
 };
 const flow=el('div','failure-review-flow');
 flow.append(phase('Preparation · 문항 단위',source,'입력된 원문 문항',excluded,'Preparation에서 제외','failure-flow-excluded',entered,'통과 → Generation 입력','failure-flow-passed'));
 flow.append(el('div','failure-flow-connector','↓ 통과한 '+fmt(entered)+'문항이 Generation으로 이어집니다'));
 flow.append(phase('Generation · 문항 단위',entered,typeCount+'개 type씩 · 전체 '+fmt(entered*typeCount)+'개 결과',clean,typeCount+'개 type 모두 통과','failure-flow-passed',nonclean,'1개 이상 실패·미평가','failure-flow-pending'));
 const detail=el('section','failure-flow-types');
 detail.append(el('h3','',fmt(nonclean)+'문항 × '+typeCount+'개 type = '+fmt(nonclean*typeCount)+'개 유형별 결과'));
 const outcomes=el('div','failure-flow-type-counts');
 outcomes.append(stat(partialPassed,'통과한 type 결과','failure-flow-passed'),stat(failed,'실패한 type 결과','failure-flow-excluded'),stat(notEvaluated,'미평가 type 결과','failure-flow-pending'));
 detail.append(outcomes,el('p','failure-flow-explanation',fmt(failed)+'와 '+fmt(notEvaluated)+'은 문항 수가 아닌 유형별 결과 수입니다. 한 문항에서 여러 type이 실패할 수 있고, 같은 문항의 다른 type은 통과할 수도 있습니다.'));
 flow.append(detail,el('p','failure-flow-note','Preparation 입력 전에 제외된 문항은 '+fmt(source)+'문항에 포함되지 않습니다. 통과는 저장된 자동 검사 기준이며 사람의 의미 정답 판정이 아닙니다.'));
 return flow;
}
function renderFailureReviewDocument(markdown){
 const sections=['Preparation','Generation','종합'];
 if(sections.some(name=>!markdown.includes(`\n### ${name} 세부내역\n`)))return renderSurveyMarkdown(markdown);
 const content=el('div','failure-review-document');let cursor=0;
 for(const name of sections){
  const marker=`\n### ${name} 세부내역\n`;
  const start=markdown.indexOf(marker,cursor);
  content.append(renderSurveyMarkdown(markdown.slice(cursor,start)));
  const bodyStart=start+marker.length;
  const nextHeading=markdown.indexOf('\n## ',bodyStart);
  const end=nextHeading<0?markdown.length:nextHeading;
  const details=el('details','failure-review-details');
  const summary=el('summary','',`${name} 세부내역`);
  summary.onclick=event=>{event.preventDefault();details.open=!details.open;};
  details.append(summary,renderSurveyMarkdown(markdown.slice(bodyStart,end)));
  content.append(details);cursor=end;
 }
 if(cursor<markdown.length)content.append(renderSurveyMarkdown(markdown.slice(cursor)));
 return content;
}
function renderFailureReview(batch){
 const report=batch.failure_review;
 document.querySelector('.filter-panel').hidden=true;
 const asideTitle=document.querySelector('aside .sticky > h2');if(asideTitle)asideTitle.textContent='원인별 분류';
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();
 $('count').textContent='원인별 보기 · Preparation 제외 212문항 · Generation 일부 실패·미평가 758문항';
 $('notice').textContent='저장된 자동 검사 결과입니다. 개선안은 제안이며 원문·정답·제작 판정을 변경하지 않았습니다.';
 $('metrics').append(renderFailureReviewFlow(report));
 const overview=button('전체 설명·개선 순서',()=>{failureReviewCategory='';renderFailureReview(batch)},'row'+(!failureReviewCategory?' selected':''));$('rows').append(overview);
 for(const phase of ['Preparation','Generation']){
  $('rows').append(el('h3','',phase));
  for(const category of report.categories.filter(c=>c.phase===phase)){
   const item=button(`${category.title} · ${category.count}건`,()=>{failureReviewCategory=category.id;failureReviewSearch='';failureReviewType='';renderFailureReview(batch)},'row'+(failureReviewCategory===category.id?' selected':''));
   item.style.cssText='white-space:normal;line-height:1.5;padding:12px';$('rows').append(item);
  }
 }
 if(!failureReviewCategory){$('detail').append(renderFailureReviewDocument(batch.review_document));return;}
 const category=report.categories.find(c=>c.id===failureReviewCategory);if(!category)return;
 const intro=el('section','panel');intro.append(el('h2','',category.title),el('p','',`${category.phase} · ${category.count}건 · 원문 ${category.cases}개`));
 if(category.phase==='Generation')intro.append(el('p','small','전체 구간의 발생 type: '+failureTypeOrder.filter(type=>category.types[type]).map(type=>`${failureTypeCodes[type]} ${category.types[type]}`).join(' · ')));
 for(const [label,key] of [['왜 멈췄나요?','why'],['먼저 손볼 곳','owner'],['어떤 자료가 필요했나요?','supply'],['어떻게 개선하나요?','fix'],['실제 기록 예','example'],['판단 범위','confidence']]){
  intro.append(el('h3','',label),el('p','',category[key]));
 }
 $('detail').append(intro);
 const controls=el('section','panel');
 const search=el('input');search.type='search';search.placeholder='문항 번호로 찾기 (예: test-0012)';search.value=failureReviewSearch;search.setAttribute('aria-label','문항 번호 검색');search.style.minWidth='260px';
 const select=el('select');select.setAttribute('aria-label','생성 유형 선택');select.append(new Option('모든 유형',''));
 for(const type of Object.keys(category.types).sort((a,b)=>failureTypeOrder.indexOf(a)-failureTypeOrder.indexOf(b)))select.append(new Option(failureTypeLabel(type),type));select.value=failureReviewType;
 controls.append(search,select);const list=el('div');controls.append(list);$('detail').append(controls);
 const redraw=()=>{
  list.replaceChildren();const rows=report.rows.filter(r=>r.group===category.id&&(!failureReviewSearch||r.case.includes(failureReviewSearch))&&(!failureReviewType||r.type===failureReviewType));
  list.append(el('p','small',`${rows.length}건 · 근거 파일은 당시 원기록입니다. 영어 원문과 내부 분류 코드는 근거에서만 표시합니다.`));
  for(const row of rows){
   const card=el('details');card.style.cssText='padding:12px 0;border-bottom:1px solid #ddd';
   card.append(el('summary','',`${row.case} · ${failureTypeLabel(row.type)} · ${row.status==='NOT_EVALUATED'?'미평가':'실패'}`));
   const original=el('a','', '원래 실행의 문항 열기');original.href=`/?run=${encodeURIComponent(report.summary.source_run)}&case=${encodeURIComponent(row.case)}`;original.target='_blank';original.rel='noopener';card.append(original);
   const output=el('pre');output.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;max-height:650px;overflow:auto;font-size:12px';
   const evidence=el('div');
   for(const path of row.refs){
    const relative=path.split('/'+report.summary.source_run+'/')[1]||path;
    const btn=button(relative,async()=>{
     output.textContent='원기록을 읽고 있습니다.';
     try{const response=await fetch('/api/quality-source?name='+encodeURIComponent(batch.name)+'&path='+encodeURIComponent(path));if(!response.ok)throw new Error('근거 파일을 읽지 못했습니다: '+response.status);output.textContent=await response.text();}catch(error){output.textContent=error.message;}
    });btn.style.cssText='display:block;text-align:left;margin:6px 0;white-space:normal;overflow-wrap:anywhere';evidence.append(btn);
   }
   card.append(evidence,output);list.append(card);
  }
 };
 search.oninput=()=>{failureReviewSearch=search.value.trim();redraw()};select.onchange=()=>{failureReviewType=select.value;redraw()};redraw();
}
