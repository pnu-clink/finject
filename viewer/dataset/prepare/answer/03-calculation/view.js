function renderPreparationCalculation(panel,row){
 const a=row.run.artifacts,sample=a['data.json']||row.sample;
 const knowledgePath=['03-calculation/03-preserve-response-and-code/01-response.json','03-calculation/02-prepare-code/01-response.json'].find(path=>a[path]);
 if(knowledgePath){
  const knowledge=a[knowledgePath].external_knowledge_requirements;
  panel.append(filePathLabel(stageFilePath(row,null,knowledgePath)));
  if(knowledge)jsonBox(panel,'외부지식 요구 문구·태그·공식 정의',knowledge);
  else panel.append(el('p','small','이전 POT 응답: 외부지식 요구 문구·공식 정의 필드가 기록되지 않았습니다.'));
 }

 const recheck=a['03-calculation/00-condition-recheck/01-result.json'];
 if(recheck?.status==='PASS')panel.append(el('p','banner',`조건 인용·스키마 재검증 통과 · Python ${recheck.python_exact_value} / 그래프 ${recheck.graph_exact_value} · 변수 ${recheck.checked_variables}개 일치. 원응답과 기존 실패 기록은 유지됩니다.`));
  if(a['03-calculation/02-prepare-code/external-evidence.json']?.applies_to)panel.append(el('p','banner','아래 외부 근거는 새 검토 후보에 연결됩니다. 기존 POT는 보존돼 있으며, 새 코드와 그래프는 04에서 확인합니다.'));
  renderExternalEvidence(panel,a['03-calculation/02-prepare-code/external-evidence.json']?.records);
  const artifacts={...a};
  for(const [path,value] of Object.entries(a))if(path.startsWith('03-calculation/'))artifacts[path.replace('03-calculation/','02-calculation/')]=value;
  const correction=a['run.json']?.correction_ref;
  const correctedExecution=correction&&a[correction+'/05-execute-and-compare/03-result.json'];
  artifacts['02-calculation/P02-execute']=correctedExecution||a['03-calculation/03-execute-python/03-result.json'];
  if(correctedExecution)artifacts['02-calculation/03-execute-python/03-result.json']=correctedExecution;
  const initial=a['03-calculation/04-compare-answer/00-initial-comparison.json'];
  if(initial){
   const summary=el('section','box');summary.style.border='2px solid #c62828';summary.style.background='#fff1f1';
   summary.append(el('h3','','최초 POT 정답 불일치'),el('p','',`최초 계산값 ${initial.computed} ↔ 원본 골드 ${initial.gold}`));
   if(correctedExecution)summary.append(el('p','','아래는 보정 검토 후 채택한 코드와 작업용 정답입니다. 최초 코드·골드·불일치 기록은 보존되어 있습니다.'));
   jsonBox(summary,'최초 생성 POT 코드',a['03-calculation/01-LLM-generate-code/03-result.json']?.data?.code);panel.append(summary);
  }
  artifacts['02-calculation/02-prepare-code/03-program.json'] ||= a['03-calculation/01-LLM-generate-code/03-result.json']?.data;
  artifacts['02-calculation/04-compare-answer/01-comparison.json'] ||= a['03-calculation/04-compare-answer/00-initial-comparison.json'];
  artifacts['run.json']=a['run.json']||{};
  if(!artifacts['02-calculation/02-prepare-code/03-program.json']){
   const info=answerRevision(row);
   panel.append(box(info.revision?`수정정답 (원본: ${info.original})`:'원본 정답 · 골드',String(info.current??sample.reference_answer??'정답 기록 없음')));
  }
  pot(panel,{...row,sample,run:{...row.run,artifacts}});
  return;
}
