function renderPreparationGraph(panel,row){
 const a=row.run.artifacts,sample=a['data.json']||row.sample;
  panel.append(el('h2','','계산 그래프'));
  panel.append(box('질문 · Q',sample.question));
  const repair=a['graph-repair.json'];
  if(repair?.status==='PASS')panel.append(el('p','banner',`변환기 보완 검증 통과 · Python ${repair.python_exact_value} / 그래프 ${repair.graph_exact_value} · 변수 ${repair.checked_variables}개 일치. 기존 코드·정답은 그대로이며, 이전 실패는 이력에 보존하고, 사람 판정은 사용자가 저장한 값을 따릅니다.`));
  const diagnostic=a['04-graph/00-diagnostic/01-result.json'];
  if(diagnostic?.kind==='SAVED_CODE_GRAPH_RECHECK')panel.append(el('p','banner',`저장된 원본 코드로 그래프 재검증 통과 · Python ${diagnostic.python_exact_value} / 그래프 ${diagnostic.graph_exact_value} · 변수 ${diagnostic.checked_variables}개 일치. 기존 실패 기록과 사람 판정은 유지됩니다.`));
  const candidateValidation=a['04-graph/00-diagnostic/02-validation.json'];
  if(candidateValidation)panel.append(el('p','banner',candidateValidation.status==='PASS'?`새 후보 Python 검증 통과 · Python ${candidateValidation.python_value} / 그래프 ${candidateValidation.graph_value} / 골드 ${candidateValidation.gold} · 변수 ${candidateValidation.checked_variables}개 일치. 적용 가정은 사람 검토 대상입니다.`:'새 후보 Python 검증 실패 · '+candidateValidation.reason));
  const savedGraph=a['04-graph/04-save-graph/01-graph.json']||diagnostic?.graph,program=a['04-graph/04-save-graph/01-graph.json']?a['03-calculation/02-prepare-code/03-program.json']:diagnostic?.program;
  const graph=graphWithSourceUsage(savedGraph,program?.source_usage||a['04-graph/03-attach-provenance/01-result.json']);
  if(graph?.nodes){
   const formula=el('section','formula-comparison');formula.append(el('h3','','계산 수식 · A. 원본식'));
   try{
    const ids=[...new Set(graph.nodes.map(n=>n.fact_id).filter(Boolean))],colors=['#147d92','#9b51a0','#aa5c18','#237d42','#495dba','#a33e56'];
    for(const numeric of [false,true]){
     const line=el('div','formula-line'+(numeric?' formula-numeric':''));line.append(document.createTextNode(numeric?'값 대입 = ':'최종 답 = '));
     for(const part of graphFormula(graph,{numeric})){
      const span=el('span','graph-formula-token',part.text),node=graph.nodes.find(n=>n.id===part.nodeId);span.dataset.nodeId=part.nodeId;
      if(node?.fact_id){span.style.color=colors[ids.indexOf(node.fact_id)%colors.length];span.style.setProperty('--fact-color',colors[ids.indexOf(node.fact_id)%colors.length]);span.title=node.fact_id;}line.append(span);
     }formula.append(line);
    }
   }catch(error){formula.append(el('p','small',error.message));}
   panel.append(formula);
  }
  renderGraphEvidence(panel,graph);
  renderExternalEvidence(panel,graph?.external_evidence);
  if(!a['04-graph/04-save-graph/01-graph.json']&&diagnostic)panel.append(el('p','banner','진단용 POT 계산 그래프 · Python 실행과 일치하지만 정답·계산 가정이 승인된 결과는 아닙니다. 기존 실패·제외 판정을 유지합니다.'));
  const comparison=a['03-calculation/04-compare-answer/01-comparison.json']||a['03-calculation/04-compare-answer/00-initial-comparison.json'];
  const graphAnswer=comparison?{...comparison,originalGold:answerRevision(row).original}:undefined;
  if(graph?.format==='finarch-python-dag-v1'&&program?.code)drawLinkedGraph(panel,graph,program.code,sample.context,graphAnswer);
  else drawGraph(panel,graph,sample.context);
  const gold=box('원본 정답 · 골드',String(sample.reference_answer??'정답 기록 없음'),{ui:sample.reference_answer==null});
  const graphView=panel.querySelector('.graph');
  if(graphView)graphView.after(gold);else panel.append(gold);
  if(!graph)panel.append(box('원문 본문',sample.context??'본문 기록 없음'));
}
