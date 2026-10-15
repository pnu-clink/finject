function renderPreparationCorrection(panel,row){
 const a=row.run.artifacts,sample=a['data.json']||row.sample;
  const audits=Object.entries(a).filter(([path])=>/^02-review-and-correct\/\d+-round\/01-LLM-audit-original\/03-result\.json$/.test(path)).sort(([a],[b])=>a.localeCompare(b));
  renderSavedAudit(panel,a['02-review-and-correct/accepted-audit.json']||audits.at(-1)?.[1],'원본 검토 결과');
  const comparison=a['data-comparison.json'];
  if(comparison&&!sameJson(comparison.reference_qca,comparison.current_qca))renderWorkingComparison(panel,row);
  else panel.append(el('p','small','보정 사항 없음 · 비교 대상이 없습니다.'));
  const failures=Object.entries(a).filter(([path,value])=>/^02-review-and-correct\/[^/]+\/01-LLM-audit-original\/03-result\.json$/.test(path)&&value?.status==='FAIL');
  if(failures.length){
   const section=el('section','box');section.append(el('h3','','문장 검사 실패 · 원문과 함께 검토'));
   for(const [path,audit] of failures){
    section.append(el('p','banner',path.split('/')[1]+' · '+(audit.reason||'검사 실패')));
    for(const finding of audit.findings||[])if(finding.judgment==='FAIL')section.append(el('p','',finding.criterion+' · '+finding.reason));
   }
   const source=a['01-source/01-receive-input/01-input.json']||row.sample;
   section.append(el('p','small','아래는 수신 원문입니다. 보정본이 있으면 위의 변경 전후 비교도 함께 확인하십시오.'));
   section.append(box('Q · 원문 질문',source?.question??'질문 기록 없음'));
   const answer=source?.reference_answer;const scale=source?.answer_metadata?.scale;
   section.append(box('A · 원본 정답 · 골드',answer==null?'정답 기록 없음':String(answer)+(scale?' · 단위: '+scale:'')));
   const current=a['data.json'];
   if(current&&current.reference_answer!==answer)section.append(box('현재 작업용 정답',String(current.reference_answer??'정답 기록 없음')+(current.answer_metadata?.scale?' · 단위: '+current.answer_metadata.scale:'')));
   section.append(box('C · 원문 본문 · 표 포함',source?.context??'본문 기록 없음'));
   panel.append(section);
  }
  return;
}
