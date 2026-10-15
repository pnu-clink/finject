function graphChanges(p,r){
 if(r.axis==='EA'&&r.variant?.plan?.method==='missing-input-dag-v1'){eaPlanView(p,r,r.variant.plan,true);return;}
 const original=eventOf(r,'03-graph/04-save-graph/01-graph.json');
 const candidates=r.variant?[r.variant]:(eventOf(r,'04-perturbation/05-list-candidates/03-result.json')||[]);
 if(r.axis==='IC_RELATION'&&['explicit-positive-ratio-v1','scoped-operation-v1'].includes(r.variant?.plan?.method)){relationPlanView(p,r,r.variant.plan,true);return;}
 if(!candidates.length){p.append(el('div','empty','변경 그래프 미생성 — 현재 저장된 것은 원본 계산 그래프입니다. 변경 후보가 저장되면 이곳에서 선택하여 비교합니다.'));return;}
 const chooser=el('select');chooser.setAttribute('aria-label','그래프 변경 후보');for(const v of candidates){const o=el('option','',`${names[v.axis]||v.axis} · ${v.label}`);o.value=v.label;chooser.append(o)}if(candidates.length>1)p.append(chooser);const layout=el('div','toolbar');let horizontal=false,meeting=true;const converge=button('합쳐 보기',()=>setLayout('meeting'),'active'),vertical=button('위아래 보기',()=>setLayout(false)),side=button('좌우 보기',()=>setLayout(true));layout.append(converge,vertical,side);p.append(layout);const body=el('div');p.append(body);function setLayout(value){meeting=value==='meeting';horizontal=value===true;converge.classList.toggle('active',meeting);vertical.classList.toggle('active',!meeting&&!horizontal);side.classList.toggle('active',horizontal);show();}
 function show(){body.replaceChildren();const v=candidates.find(v=>v.label===chooser.value)||candidates[0],stored=v.plan||record(r,`04-perturbation/variants/${v.label}/D07-inject`),base=stored?.base_plan_ref?eventOf(r,stored.base_plan_ref):null,plan=stored?.base_plan_ref?{...base,...stored}:stored;if(stored?.base_plan_ref&&!base){body.append(el('div','banner','기준 A/B 계획을 읽지 못했습니다.'));return;}if(!plan){body.append(el('div','empty','변경 계획 기록이 없습니다.'));return;}
  if(plan.axis==='EA'&&plan.method==='missing-input-dag-v1'){eaPlanView(body,{...r,label:v.label},plan,true);return;}
  if(plan.perturb_position)body.append(el('p','banner',`IC-VALUE · ${plan.perturb_position==='before'?'앞':'뒤'} — 문장 생성 메뉴에서 위치를 비교합니다. 이 앞/뒤 쌍은 동일한 A/B 계산 그래프를 공유합니다.`));
  if(plan.answers){body.append(el('p','final-answer-summary',`조건별 계산 결과 · A를 따르면 ${plan.answers.A.computed} / B를 따르면 ${plan.answers.B.computed}`),el('p','small',(plan.answers.precision!=null?`소수 ${plan.answers.precision}자리 적용 · `:'저장된 계산값 · ')+'최종 문장 검사는 검증 메뉴에서 확인합니다.'));}
  if(plan.sources){
   body.append(el('h3','','두 값에 붙이는 출처 조건'),el('p','small','아래는 제작할 출처 설정입니다. 실제 원문에 있던 출처 사실이나 참·거짓 판정이 아닙니다. 숫자·계산식·그래프는 값 충돌 계획과 같습니다.'));
   const cards=el('div','cols');for(const side of ['A','B']){const source=plan.sources.find(s=>s.side===side),card=el('div','box source-card');card.append(el('h3','',`${side} 주장 · ${plan.value_pair[side==='A'?0:1]}`));if(source){card.append(el('strong','','원자료를 직접 확인한 출처'),el('p','','역할: 재무 분석 담당자'),el('p','','해당 거래 원자료에 접근하여 금액을 대조한 설정입니다.'),el('p','small','제작용 출처 설정이며 원문에 실제 존재하는 출처가 아닙니다.'));}else{card.append(el('strong','','출처 기재 없음'),el('p','','이 주장에는 출처 설명을 추가하지 않습니다. 낮은 신뢰도라는 뜻이 아닙니다.'));}cards.append(card)}body.append(cards);

  }
  const handoff=eventOf(r,`04-perturbation/variants/${v.label}/06-generation-input.json`);if(handoff){jsonBox(body,'문장 생성에 전달할 원문·변수·그래프·출처 연결',handoff);}
  const gs=plan.graphs,entries=Array.isArray(gs)?gs.map((g,i)=>[String(i+1),g]):gs?.nodes?[['변경 그래프',gs]]:Object.entries(gs||{});
  body.append(el('p','small','주황색: 직접 변경·추가·삭제된 요소 / 보라색: 해당 요소를 입력으로 받는 후속 경로 / 회색: 나머지. 경로 강조는 의존 관계이며, 값이 실제로 달라졌는지는 아래 표에서 따로 확인합니다.'));
  if(!entries.length)body.append(el('div','empty','변경 그래프 기록이 없습니다. 삭제 계획만 있는 경우 계산 결과를 만들지 않습니다.'));
  for(const [label,graph] of entries){if(!original?.nodes||!graph?.nodes){jsonBox(body,label,graph);continue;}if(JSON.stringify(graph)===JSON.stringify(original))continue;
   const valid=g=>{const seen=new Set();return g.nodes.every(n=>{const ok=!(n.inputs||[]).some(id=>!seen.has(id))&&!seen.has(n.id);seen.add(n.id);return ok})&&seen.has(g.output)};if(!valid(original)||!valid(graph)){body.append(el('div','banner','그래프 연결 기록이 불완전하여 비교를 그릴 수 없습니다.'));jsonBox(body,'확인할 그래프 기록',graph);continue;}
   const delta=graphDelta(original,graph),cols=el('div','comparison-stack'+(horizontal?' side-by-side':'')),left=el('div','box'),right=el('div','box');cols.append(left,right);const canvas=el('div');body.append(canvas);if(!meeting)canvas.append(cols);
   const detail=el('div','box');body.append(detail);const selected=[];
   function choose(id){for(const [key,node] of selected)node.classList.toggle('comparison-selected',key===id);const a=original.nodes.find(n=>n.id===id),b=graph.nodes.find(n=>n.id===id);detail.replaceChildren(el('h3','',a?.label||b?.label||id),box('A와 B의 값 · 두 근거를 각각 채택',`A: ${a?text(a.computed??a.value):'없음'} / B: ${b?text(b.computed??b.value):'삭제됨'}`));}
   if(meeting)drawMeeting(canvas,original,graph,delta,plan.answers,choose,selected);else{drawComparison(left,original,'원본 A',delta,choose,selected);drawComparison(right,graph,'변경 근거를 따르는 경로 B',delta,choose,selected);}
   const table=el('table','events'),head=el('tr');['요소','변경 구분','원본 값','변경 값'].forEach(t=>head.append(el('th','',t)));table.append(head);
   for(const id of delta.affected){const a=original.nodes.find(n=>n.id===id),b=graph.nodes.find(n=>n.id===id),tr=el('tr');tr.append(el('td','',a?.label||b?.label||id),el('td','',delta.changed.has(id)?'직접 변경':'후속 경로'),el('td','',a?text(a.computed??a.value):'없음'),el('td','',b?text(b.computed??b.value):'삭제됨'));table.append(tr)}body.append(el('p','small','값은 저장된 그래프의 계산값입니다. 자릿수 적용 전 값이며, 누락된 계산값을 화면에서 추정하지 않습니다.'),table);choose(graph.output);
  }
  jsonBox(body,'변경 요소·근거 A/B·출처 조건',plan);jsonBox(body,'변경 목표 검사',eventOf(r,`04-perturbation/variants/${v.label}/04-check-target/03-result.json`));
 }chooser.onchange=show;show();
}
