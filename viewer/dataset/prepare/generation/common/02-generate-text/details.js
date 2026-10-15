function renderConditionalAnswers(panel,plan){
 const a=plan?.original_graph?.nodes?.find(n=>n.id===plan.original_graph.output)?.computed,b=plan?.graph?.nodes?.find(n=>n.id===plan.graph.output)?.computed;
 if(plan?.axis==='EA')return;
 if(a!=null&&b!=null)panel.append(box('각 근거를 따랐을 때의 계산 결과',`A: ${a} / B: ${b}`),el('p','small','저장된 두 계산 경로의 값입니다. 평가 모델이 제출한 답변이나 사람의 최종 판정이 아닙니다.'));
}
function renderGenerationTextDetails(panel,row,variant,original,current){
 const plan=generationPlan(row,variant),a=row.run.generation||{},patches=a[variant+'/02-generate-text/05-patches.json'];
 if(generationKind(variant)==='IC_VALUE'){renderValueTextDetails(panel,row,variant);return;}
 if(generationKind(variant)==='EA'){
  renderEaSentenceDiff(panel,original.context,current.context);
  for(const patch of patches||[])panel.append(box('삭제·변경한 원문',patch.before),box('대체 문구',patch.text||'삭제 · 대체 문구 없음',{ui:!patch.text}));
  return;
 }
 for(const patch of patches||[])panel.append(box(generationKind(variant)==='IC_SOURCE'?'출처를 반영한 문장':'추가한 관계 문장',patch.text));
 renderConditionalAnswers(panel,plan);
}
