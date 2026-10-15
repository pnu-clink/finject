function renderRelationPerturbation(panel,row,variant){
 const plan=generationPlan(row,variant),relation=plan?.intent?.relation;
 if(relation)panel.append(box('관계 대상',plan.target),box('원래 관측값',relation.target?.value),box('추가 관계',`${relation.operand?.value??'피연산자 미기록'} ${relation.operation==='multiply'?'×':relation.operation==='divide'?'÷':relation.operation} ${relation.factor??'계수 미기록'}`));
 if(!plan){renderGenerationGraphs(panel,row,variant);return;}
 const originalProgram=row.run.artifacts['03-calculation/02-prepare-code/03-program.json'];
 const entries=[['원본 계산',plan.original_graph,originalProgram],['관계 적용 계산',plan.graph,plan.program]];
 const formulas=el('div','relation-formulas'),controls=el('div','toolbar'),graphs=el('div','relation-graphs');
 panel.append(formulas,controls,graphs);
 const ids=[...new Set(entries.flatMap(([,graph])=>(graph?.nodes||[]).map(n=>n.fact_id).filter(Boolean)))],colors=['#147d92','#9b51a0','#aa5c18','#237d42','#495dba','#a33e56'];
 const cards=[];
 for(const [title,savedGraph,program] of entries){
  const formula=el('section','formula-comparison'),card=el('section','relation-graph-card');formula.append(el('h3','',title));formulas.append(formula);card.append(el('h3','',title));graphs.append(card);
  const graph=graphWithSourceUsage(savedGraph,program?.source_usage);
  if(!graph?.nodes){formula.append(el('p','small','저장된 그래프가 없습니다.'));continue;}
  try{for(const numeric of [false,true]){
   const line=el('div','formula-line'+(numeric?' formula-numeric':''));line.append(document.createTextNode(numeric?'값 대입 = ':'최종 답 = '));
   for(const part of graphFormula(graph,{numeric})){
    const span=el('span','graph-formula-token',part.text),node=graph.nodes.find(n=>n.id===part.nodeId);span.dataset.nodeId=part.nodeId;
    if(node?.fact_id){const color=colors[ids.indexOf(node.fact_id)%colors.length];span.style.color=color;span.style.setProperty('--fact-color',color);span.title=node.fact_id;}line.append(span);
   }formula.append(line);
  }}catch(error){formula.append(el('p','small','수식 표시 불가 · '+error.message));}
  // Each graph uses its own AST IDs, formula tokens and Python source bindings.
  drawLinkedGraph(card,graph,program?.code||'',row.sample.context,null,null,[...formula.querySelectorAll('.graph-formula-token')]);cards.push(card);
 }
 function layout(vertical){graphs.classList.toggle('relation-vertical',vertical);side.classList.toggle('active',!vertical);stack.classList.toggle('active',vertical);requestAnimationFrame(()=>{for(const card of cards){const fit=[...card.querySelectorAll('button')].find(b=>b.textContent==='전체 맞춤');fit?.click();}});}
 const side=button('좌우 보기',()=>layout(false),'active'),stack=button('위아래 보기',()=>layout(true));controls.append(side,stack);layout(false);
 jsonBox(panel,'관계 적용 후 실제 계산 결과',plan.execution);
}
