// Node provenance uses saved facts and external evidence; edges carry dependencies only.
function externalGraphNode(node,graph){return (node.evidence_types||[]).some(t=>['EXTERNAL_RULE','EXTERNAL_DATA'].includes(t))||['EXTERNAL_RULE','EXTERNAL_DATA'].includes(node.evidence_type)||!!node.evidence_id;}
function renderGraphEvidence(panel,graph){
 if(!graph)return;
 const section=el('section','box');section.setAttribute('aria-label','node 출처 확인 안내');
 section.append(el('h3','','node 출처와 계산 의존 관계'));
 section.append(el('p','small','Internal Context: IN_CONTEXT_DATA · External Context: EXTERNAL_RULE / EXTERNAL_DATA. 한 계산에서 함께 사용할 수 있습니다.'));
 section.append(el('p','small','입력 node의 원문 근거·외부 근거를 확인합니다. 중간값과 결과는 선행 node의 계산 관계를 따라 추적합니다. edge에는 별도의 출처 분류를 요구하지 않습니다.'));
 section.append(el('p','small','원: 문맥 입력 · 파란 사각형: 외부 규칙 · 빨간 사각형: 외부 데이터 · 육각형: 중간 계산결과 · 보라색 오각형: 변경된 노드. 모양만으로 근거의 타당성을 판정하지 않습니다. node를 선택해 저장된 근거와 코드를 확인하세요.'));
 panel.append(section);
}

function graphWithSourceUsage(graph,usages){
 if(!graph?.nodes)return graph;
 const result={...graph,nodes:graph.nodes.map(n=>({...n,evidence_types:[...(n.evidence_types||[])],source_usage_ids:[...(n.source_usage_ids||[])]}))},nodes=new Map(result.nodes.map(n=>[n.id,n]));
 for(const usage of usages||graph.source_usage||[]){
  if(!['EXTERNAL_RULE','EXTERNAL_DATA'].includes(usage.kind))continue;
  for(const name of usage.output_variables||[]){
   const variable=nodes.get(graph.variables?.[name]);if(!variable||!usage.code_lines?.includes(variable.code_line))continue;
   const pending=[...(variable.inputs||[])],seen=new Set();
   while(pending.length){const id=pending.pop();if(seen.has(id))continue;seen.add(id);const node=nodes.get(id);if(node?.kind!=='operation')continue;
    node.evidence_types=[...new Set([...node.evidence_types,usage.kind])];node.source_usage_ids=[...new Set([...node.source_usage_ids,usage.id])];pending.push(...node.inputs||[]);
   }
  }
 }
 return result;
}

function graphNodeShape(node,at,perturbed=false){
 const types=new Set([...(node.evidence_types||[]),node.evidence_type]);
 const kind=perturbed?'perturbed':types.has('EXTERNAL_DATA')?'data':types.has('EXTERNAL_RULE')?'rule':node.evidence_id?'data':node.kind==='fact'?'context':'intermediate';
 const polygon=kind==='perturbed'||kind==='intermediate',shape=document.createElementNS('http://www.w3.org/2000/svg',polygon?'polygon':kind==='context'?'circle':'rect');
 const attrs=polygon?{points:Array.from({length:kind==='perturbed'?5:6},(_,i)=>{const angle=-Math.PI/2+i*2*Math.PI/(kind==='perturbed'?5:6);return `${at.x+43*Math.cos(angle)},${at.y+43*Math.sin(angle)}`}).join(' ')}:kind==='context'?{cx:at.x,cy:at.y,r:43}:{x:at.x-43,y:at.y-43,width:86,height:86};
 Object.assign(attrs,{fill:{context:'#dff1e7',rule:'#dbeeff',data:'#ffe0e0',intermediate:'#f0f2f4',perturbed:'#e8d8ff'}[kind],stroke:{context:'#56866b',rule:'#2674b8',data:'#c43b3b',intermediate:'#81909c',perturbed:'#803dc1'}[kind],'stroke-width':2});
 for(const [key,value] of Object.entries(attrs))shape.setAttribute(key,value);shape.dataset.shapeKind=kind;return shape;
}
function renderGraphLegend(parent,{control=false}={}){
 const legend=el('div','graph-legend');legend.setAttribute('aria-label','계산 그래프 범례');
 for(const [kind,label] of [['context','IN_CONTEXT_DATA'],['rule','EXTERNAL_RULE'],['data','EXTERNAL_DATA'],['intermediate','중간 계산결과'],['perturbed','변경된 노드']]){
 const item=el('span','graph-legend-item'),svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 100 100');svg.setAttribute('width','28');svg.setAttribute('height','28');svg.setAttribute('aria-hidden','true');svg.append(graphNodeShape({kind:kind==='context'?'fact':'operation',evidence_type:kind==='rule'?'EXTERNAL_RULE':kind==='data'?'EXTERNAL_DATA':null},{x:50,y:50},kind==='perturbed'));item.append(svg,document.createTextNode(label));legend.append(item);
 }
 if(control)for(const [kind,label] of [['data','실선: 값 전달'],['control','보라색 점선: 실행 조건']]){
  const item=el('span','graph-legend-item'),line=el('span','graph-line-key'+(kind==='control'?' graph-line-control':''));
  line.setAttribute('aria-hidden','true');item.append(line,document.createTextNode(label));legend.append(item);
 }
 parent.append(legend);
}
