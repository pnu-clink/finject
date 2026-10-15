function eaPlanView(p,r,plan,withGraph){
 const graph=plan.graphs.EA,binding=eventOf(r,plan.program_path),original=eventOf(r,'03-graph/04-save-graph/01-graph.json');
 p.append(el('h2','','EA · 입력값이 없는 계산 그래프'),el('p','banner','그래프 생성: 성공 · 이 계산 경로의 결과: 근거 부족으로 계산 불가. 원문 삭제는 계획이며, 역산·우회 및 EA 성립은 아직 미평가입니다.'));
 eaStage15Review(p,r);
 const table=el('table','events'),head=el('tr');['입력 근거','원본 계산용 값','EA 계산용 값'].forEach(t=>head.append(el('th','',t)));table.append(head);
 const originalFacts=eventOf(r,'02-calculation/02-prepare-code/03-program.json')?.facts||{};
 for(const [key,f] of Object.entries(originalFacts)){const tr=el('tr');if(key===plan.fact_id)tr.className='ea-missing-row';tr.append(el('td','',key),el('td','',f.value),el('td','',key===plan.fact_id?'삭제됨 · 근거 없음':binding?.facts[key]?.value));table.append(tr)}
 p.append(table,box('최종 결과 비교',`원본: ${r.run.final_answers?.graph?.computed??original?.nodes.find(n=>n.id===original.output)?.computed} / EA: 계산 불가 · ${plan.fact_id} 근거 없음`),el('p','small','붉은 점선 원: 값이 삭제된 입력 / 주황색: 그 값이 필요한 계산 / 초록·파랑: 남은 값. 숫자가 없는 노드에도 코드에서 읽은 연결은 유지됩니다.'));
 if(withGraph){const section=el('section','ea-graph');p.append(section);drawLinkedGraph(section,graph,binding.code,r.sample.context);}
 else {p.append(el('h3','','같은 Python 계산 코드 · 입력값은 별도 자료'),el('pre','',binding?.code||'코드 기록 없음'),el('p','small','계산 연결은 4번 그래프 변경에서 보실 수 있습니다. 위 코드의 fact 입력에는 삭제한 값이 없습니다.'))}
 jsonBox(p,'EA 계산 입력 · 코드·남은 값·삭제 키',binding);
 const deletion=el('div','box');deletion.append(el('h3','','원문에서 삭제할 대상 · 아직 계획'),el('p','',plan.fact_id+' → '+plan.deletion.before),marked(r.sample.context,[{start:plan.deletion.span[0],end:plan.deletion.span[1],before:plan.deletion.before,after:''}],'before'));p.append(deletion);
 jsonBox(p,'값이 없는 노드와 후속 계산 상태',graph);jsonBox(p,'EA 그래프 검사 기록',eventOf(r,`04-perturbation/variants/${r.label}/validation.json`));
}
