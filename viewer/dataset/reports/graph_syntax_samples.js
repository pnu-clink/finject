function renderGraphSyntaxSamples(report){
 document.querySelector('.filter-panel').hidden=true;
 $('metrics').replaceChildren();$('rows').replaceChildren();$('detail').replaceChildren();
 $('count').textContent='7종 대표 사례 · Python/그래프 대조 · LLM 미실행';
 const id=new URL(location.href).searchParams.get('sample')||report.samples[0].id;
 const current=report.samples.find(s=>s.id===id)||report.samples[0];
 for(const s of report.samples)$('rows').append(button(s.title,()=>{const u=new URL(location.href);u.searchParams.set('sample',s.id);history.replaceState(null,'',u);renderGraphSyntaxSamples(report);},'row'+(s===current?' selected':'')));
 const panel=el('section','panel');panel.append(el('h2','','계산 그래프 · '+current.title),el('p','small','구문 확인용 예제입니다. 실제 데이터셋 통과 결과가 아닙니다. API 호출 0회.'),el('p','',current.policy),box('Python ↔ 그래프',current.check.python+' = '+current.check.graph+' · '+current.check.status+' · 전역 변수 '+current.check.global_variables_compared+'개 대조'),box('입력',current.program.context));
 $('detail').append(panel);
 if(report.integration_check_review){
  const review=report.integration_check_review,d=el('details','box');
  d.append(el('summary','','후속 통합검사 · '+review.tests_run+'개 통과 · API 호출 '+review.model_calls+'회'));
  d.append(el('p','small','검사 코드 정비 결과입니다. 실제 생성·판정 로직은 변경하지 않았습니다. 수정 전 오류 로그는 보존합니다.'));
  const table=el('table','events'),head=el('tr');
  ['검사','처리 내용'].forEach(value=>head.append(el('th','',value)));table.append(head);
  [['EA','필수 검사 기록, 복원 근거, 미평가 시 기존 판정 유지'],['IC-RELATION','임시 폴더·독립 검사 입력 구성, 최종 답이 같으면 후보 등록 차단'],['IC-SOURCE','모듈을 불러온 뒤 객체를 대상으로 검사하여 하이픈 문제 해소']].forEach(values=>{const row=el('tr');values.forEach(value=>row.append(el('td','',value)));table.append(row);});
  d.append(table);panel.append(d);
 }
 drawLinkedGraph(panel,current.graph,current.program.code,current.program.context);
}

function graphSourceLines(node){return [...new Set([node.code_line,...(node.source_locations||[]).map(location=>location.line)].filter(Boolean))];}

function controlConditionLabel(event){
 if(event.control==='while')return event.observed?event.iteration+'회차 계속':event.iteration+'번째 조건에서 종료';
 if(event.control==='if')return event.observed?'if 분기 선택':'else 분기 선택';
 return event.observed?'조건 참':'조건 거짓';
}

function graphControlLinkLabel(edge){
 const event=edge.event;
 const choice=event.control==='while'?(event.observed?`${event.iteration}회차 계속`:'반복 종료'):(event.observed?'if 선택':'else 선택');
 const target=edge.target_kind==='end'?'실행 종료':edge.target_kind==='body'?'선택된 계산':'다음 계산';
 return `${choice} → ${target}`;
}

// Display-only projection. The saved graph and evaluator retain every guard.
function controlGraphDisplay(graph){
 const output=graph.control_flow?.display_output;
 if(!output)return graph;
 const visible=graph.nodes.filter(node=>!node.control_internal),ids=new Set(visible.map(node=>node.id));
 if(!ids.has(output)||visible.some(node=>node.inputs.some(id=>!ids.has(id))))return graph;
 const conditions=new Map((graph.control_flow.events||[]).filter(e=>e.kind==='condition'&&e.control).map(e=>[e.condition_node,e]));
 const nodes=visible.map(node=>{
  const copy={...node,inputs:[...node.inputs]},event=conditions.get(node.id);
  if(event&&node.kind==='operation'&&['True','False'].includes(node.computed)){
   copy.label=controlConditionLabel(event);
   copy.control_title=event.control==='while'?'반복 조건':'분기 조건';
   copy.control_value=event.control==='while'?(event.observed?'계속':'종료'):(event.observed?'if':'else');
  }
  return copy;
 });
 const controlEdges=[];
 for(const link of graph.control_flow.links||[]){
  const event=graph.control_flow.events[link.event_index];
  if(!event||!ids.has(link.from)||(link.to&&!ids.has(link.to)))continue;
  const to=link.to||'control-end';
  if(!ids.has(to)){
   nodes.push({id:to,kind:'control',inputs:[],label:'실행 종료',computed:'—',code_line:event.line,
    control_title:'제어 흐름',control_value:'종료'});ids.add(to);
  }
  controlEdges.push({...link,to,event,kind:'control'});
 }
 const variables=Object.fromEntries(Object.entries(graph.variables||{}).filter(([name,id])=>name!=='answer'&&ids.has(id)));
 return {...graph,nodes,output,variables:{...variables,answer:output},
  control_edges:controlEdges,
  edges:graph.edges.filter(edge=>ids.has(edge.from)&&ids.has(edge.to))};
}

function renderGraphControlTrace(parent,graph){
 if(!graph.control_flow)return;
 parent.append(el('p','banner','실행 경로를 펼친 그래프 · 조건·반복·정렬 경로가 바뀌면 같은 코드로 그래프를 다시 생성해야 합니다.'));
 const d=el('details','small'),events=graph.control_flow.events||[];
 const byId=new Map(graph.nodes.map(node=>[node.id,node])),internal=graph.nodes.filter(node=>node.control_internal);
 const decisions=events.filter(event=>event.kind==='condition'&&event.control);
 if(decisions.length){
  const summary=el('div','box control-flow-summary');summary.append(el('h3','','반복·분기 흐름'));
  for(const loop of events.filter(event=>event.kind==='while')){
   const tests=decisions.filter(event=>event.control==='while'&&event.line===loop.line&&JSON.stringify(event.scope)===JSON.stringify(loop.scope));
   summary.append(el('p','small',loop.line+'행 · '+loop.iterations+'회 반복'+(loop.break?' · break로 종료':'')));
   summary.append(el('p','',tests.map(controlConditionLabel).join(' → ')));
  }
  for(const event of decisions.filter(event=>event.control==='if'))summary.append(el('p','small',event.line+'행 · '+event.condition_expression+' · '+controlConditionLabel(event)));
  parent.append(summary);
 }
 d.append(el('summary','','검사 상세 · 조건·반복·함수 호출 '+events.length+'개'+(internal.length?' / 내부 노드 '+internal.length+'개':'')));
 if(internal.length)d.append(el('p','small','조건 일치 비교와 내부 결합 노드는 저장·재계산에 유지하며, 기본 계산 그래프에서만 생략합니다.'));
 const t=el('table','events'),head=el('tr');['코드 행','종류','실제 선택·회차','호출·반복 위치'].forEach(s=>head.append(el('th','',s)));t.append(head);
 for(const e of events){const row=el('tr');[e.line,e.condition_expression||e.kind,e.kind==='condition'&&e.control?controlConditionLabel(e):e.iterations!=null?e.iterations+'회':e.selected??e.function??String(e.observed),(e.scope||[]).join(' → ')].forEach(s=>row.append(el('td','',s)));t.append(row);}
 d.append(t);
 if(internal.length){
  const table=el('table','events'),header=el('tr');['내부 노드','연산·구분','입력값','저장된 결과'].forEach(label=>header.append(el('th','',label)));table.append(header);
  for(const node of internal){const row=el('tr');[node.id,node.operator||node.kind,node.inputs.map(id=>id+' = '+(byId.get(id)?.computed??'미평가')).join(', '),node.computed??'미평가'].forEach(value=>row.append(el('td','',value)));table.append(row);}
  d.append(table);
 }
 parent.append(d);
}
