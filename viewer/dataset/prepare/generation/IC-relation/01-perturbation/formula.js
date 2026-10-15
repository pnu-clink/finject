function relationFormulaComparison(p,r,plan){
 const block=el('section','formula-comparison');block.setAttribute('aria-label','원본과 관계 적용 수식 비교');
 block.append(el('h3','','원본식 ↔ 관계 적용식 · 한 줄 비교'),el('p','formula-note','분홍: 관계 대상의 원래 관측값 · 주황: 관계를 적용해 도출한 항. 괄호와 함수는 실제 계산 순서대로 유지합니다.'));
 const aliases={service_fee_income:'서비스 수수료',commission_income:'판매 수수료',investment_gain_income:'투자 수익',other_noninterest_income:'기타 수익'};
 const labels={A:'A · 원본식',B:'B · 서비스 수수료를 판매 수수료 × 2로 계산',C:'C · 판매 수수료를 서비스 수수료 ÷ 2로 계산'};
 for(const key of ['A',...Object.keys(plan.branches)]){
  const graph=key==='A'?eventOf(r,'03-graph/04-save-graph/01-graph.json'):plan.graphs[key],row=el('div','formula-row');row.append(el('div','formula-key',labels[key]));
  try{for(const numeric of [false,true]){
   const line=el('div','formula-line'+(numeric?' formula-numeric':''));line.append(document.createTextNode((numeric?'값 대입: ':'최종 답 = ')));
   const tokens=graphFormula(graph,{numeric,aliases,markedIds:plan.branches[key]?.relation_node_ids||[],markedFacts:key==='A'?[plan.relation.left,plan.relation.right]:[]});
   for(const part of tokens){const span=el('span',part.changed?(key==='A'?'formula-original':'formula-added'):'',part.text);span.title='그래프 요소 '+part.nodeId;line.append(span)}
   line.append(el('strong','',' = '+plan.answers[key].computed));row.append(line);
  }}catch(error){row.append(el('p','banner',error.message))}
  block.append(row);
 }
 block.append(el('p','formula-note','int는 정수 변환, round는 저장된 코드의 반올림입니다. 위 결과는 기존 최종 자릿수 정책을 적용한 조건부 답입니다. 검토용으로 식을 펼친 것이며 실행용 단계별 Python 코드는 그대로입니다.'));p.append(block);
}
