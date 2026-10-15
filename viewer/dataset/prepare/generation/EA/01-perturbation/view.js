function renderEaPerturbation(panel,row,variant){
 const plan=generationPlan(row,variant);
 if(!plan){renderGenerationGraphs(panel,row,variant);return;}
 const deletion=plan.intent?.deletion,target=deletion?.fact_id||plan.target;
 const originalFact=plan.original_graph?.nodes?.find(n=>n.kind==='fact'&&n.fact_id===target);
 const evidence=el('section','box'),prose=el('div','prose'),mark=el('mark','ea-deletion-target');
 evidence.append(el('h3','','삭제할 근거'),prose);panel.append(evidence);
 const before=deletion?.before||'',start=originalFact?.span?.[0]-deletion?.span?.[0],end=originalFact?.span?.[1]-deletion?.span?.[0];
 // Offsets are Unicode character positions, just like the saved source spans.
 if(Number.isInteger(start)&&start>=0&&end>start&&end<=Array.from(before).length){
  prose.append(document.createTextNode(sliceText(before,0,start)));mark.textContent=sliceText(before,start,end);prose.append(mark,document.createTextNode(sliceText(before,end)));
 }else{prose.textContent=before||'저장된 삭제 근거가 없습니다.';mark.textContent=target||'삭제 대상 미기록';evidence.append(mark,el('p','small','원문에서 대상의 정확한 위치를 확인할 수 없어 입력 이름으로 표시합니다.'));}
 mark.tabIndex=0;mark.setAttribute('role','button');mark.setAttribute('aria-label','삭제 대상 '+target+' · 양쪽 그래프 연결');
 evidence.append(el('p','small','삭제 대상 입력: '+(target||'미기록')+' · 강조된 근거와 양쪽 노드에 마우스를 올리거나 클릭하면 함께 표시됩니다.'));
 panel.append(el('p','small','선택한 입력이 없을 때의 계산 연결입니다. 숫자 0으로 대체하지 않으며 원문 전체에서 답을 복원할 수 없는지까지 증명한 결과는 아닙니다.'));
 const controls=el('div','toolbar'),graphs=el('div','relation-graphs ea-graphs'),cards=[],targets=[];
 panel.append(controls,graphs);
 const originalProgram=row.run.artifacts['03-calculation/02-prepare-code/03-program.json'];
 for(const [title,saved,program] of [['원본 계산',plan.original_graph,originalProgram],['근거 삭제 후 계산',plan.graph,plan.program]]){
  const card=el('section','relation-graph-card');card.append(el('h3','',title));graphs.append(card);cards.push(card);
  if(!saved?.nodes){card.append(el('p','small','저장된 그래프가 없습니다.'));continue;}
  const graph=graphWithSourceUsage(saved,program?.source_usage);
  drawLinkedGraph(card,graph,program?.code||'',row.sample.context);
  const ids=new Set(graph.nodes.filter(n=>n.kind==='fact'&&n.fact_id===target).map(n=>n.id));
  const matches=[...card.querySelectorAll('.dag-node')].filter(n=>ids.has(n.dataset.nodeId));
  for(const node of matches){node.classList.add('ea-deletion-node');targets.push(node);}
  if(!matches.length)card.append(el('p','small','이 그래프에는 삭제 대상에 대응하는 저장된 노드가 없습니다.'));
 }
 let pinnedHighlight=false;
 function highlight(active){mark.classList.toggle('ea-deletion-active',active);targets.forEach(n=>n.classList.toggle('ea-deletion-active',active));}
 for(const element of [mark,...targets]){
  element.addEventListener('mouseenter',()=>highlight(true));element.addEventListener('mouseleave',()=>highlight(pinnedHighlight));
  element.addEventListener('focus',()=>highlight(true));element.addEventListener('blur',()=>highlight(pinnedHighlight));
  element.addEventListener('click',()=>{pinnedHighlight=true;highlight(true);if(element===mark)for(const node of targets)node.onclick?.();});
 }
 mark.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();mark.click();}};
 function layout(vertical){graphs.classList.toggle('relation-vertical',vertical);side.classList.toggle('active',!vertical);stack.classList.toggle('active',vertical);requestAnimationFrame(()=>cards.forEach(card=>[...card.querySelectorAll('button')].find(b=>b.textContent==='전체 맞춤')?.click()));}
 const side=button('좌우 보기',()=>layout(false),'active'),stack=button('위아래 보기',()=>layout(true));controls.append(side,stack);layout(false);
 jsonBox(panel,'변경 계획과 계산 검사',plan.execution);jsonBox(panel,'실제 저장된 변경 계획',plan);
}
