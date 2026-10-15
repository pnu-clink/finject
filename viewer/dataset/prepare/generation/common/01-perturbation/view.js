function generationPlan(row,variant){const a=row.run.generation||{};return a[variant+'/run.json']?.plan||a[variant+'/01-perturbation/03-result.json']?.plan||a[variant+'/01-perturbation/01-inherited-plan.json']?.plan;}
function renderGenerationGraphs(panel,row,variant){
 const plan=generationPlan(row,variant);if(!plan){panel.append(el('p','small','변경 계획·그래프가 저장되지 않았습니다.'));return;}
 // Reuse the 012 comparison renderer with values from this run only.
 const original=plan.original_graph,changed=plan.graph;
 const originalValue=original?.nodes?.find(n=>n.id===original.output)?.computed;
 const changedValue=changed?.nodes?.find(n=>n.id===changed.output)?.computed;
 const adapted={axis:plan.axis,graphs:{B:changed},...plan.intent};
 if(originalValue!=null&&changedValue!=null)adapted.answers={A:{computed:originalValue},B:{computed:changedValue}};
 const planPath=displayedFilePath('변경 계획',plan);
 if(planPath)displayedFileSources.push({key:'변경 요소·근거 A/B·출처 조건',value:adapted,path:planPath+' · 표시용 재구성'});
 const legacy={...row,axis:plan.axis,label:plan.label,variant:{label:plan.label,axis:plan.axis,plan:adapted},run:{...row.run,artifacts:{...row.run.artifacts,'03-graph/04-save-graph/01-graph.json':original}}};
 if(plan.axis==='EA'){
  panel.append(el('h3','','원본 계산 그래프'));drawLinkedGraph(panel,original,row.run.artifacts['03-calculation/02-prepare-code/03-program.json']?.code||'',row.sample.context);
  panel.append(el('h3','','근거를 삭제한 계산 그래프'));if(changed)drawLinkedGraph(panel,changed,plan.program?.code||'',row.sample.context);
 }else graphChanges(panel,legacy);
 jsonBox(panel,'변경 계획과 계산 검사',plan.execution);jsonBox(panel,'실제 저장된 변경 계획',plan);
}
