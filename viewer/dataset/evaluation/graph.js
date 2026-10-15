// Compact only assignment aliases. All stored inputs, operations and control links remain.
function evaluationCompactGraph(graph){
 if(!graph?.nodes?.length)return null;
 const byId=new Map(graph.nodes.map(n=>[n.id,n]));
 if(byId.size!==graph.nodes.length||!byId.has(graph.output))throw Error('노드 또는 최종 답 기록이 불완전합니다.');
 const controlled=new Set((graph.control_edges||[]).flatMap(e=>[e.from,e.to]));
 const representatives=new Map(),visiting=new Set();
 function resolve(id){
  if(representatives.has(id))return representatives.get(id);
  const node=byId.get(id);if(!node)throw Error('입력 노드 기록이 없습니다: '+id);
  if(visiting.has(id))throw Error('계산 연결에 순환이 있습니다.');
  visiting.add(id);
  for(const parent of node.inputs||[])resolve(parent);
  const alias=node.kind==='variable'&&node.inputs?.length===1&&!controlled.has(id);
  const result=alias?resolve(node.inputs[0]):id;
  visiting.delete(id);representatives.set(id,result);return result;
 }
 graph.nodes.forEach(n=>resolve(n.id));
 const nodes=graph.nodes.filter(n=>resolve(n.id)===n.id).map(n=>({...n,inputs:(n.inputs||[]).map(resolve),aliases:[],sourceIds:[],evidence_types:[...(n.evidence_types||[])]}));
 const compact=new Map(nodes.map(n=>[n.id,n]));
 for(const n of graph.nodes){
  const kept=compact.get(resolve(n.id));kept.sourceIds.push(n.id);
  if(n.kind==='variable')kept.aliases.push(n.label);
  kept.evidence_types=[...new Set([...kept.evidence_types,...(n.evidence_types||[]),...(n.evidence_type?[n.evidence_type]:[])])];
 }
 const output=resolve(graph.output);
 for(const n of nodes)n.displayLabel=n.id===output?'최종 답':n.aliases.at(-1)||n.label;
 return {...graph,nodes,output,representatives,originalCount:graph.nodes.length,
  control_edges:(graph.control_edges||[]).map(e=>({...e,from:resolve(e.from),to:resolve(e.to)}))};
}

// Share only semantically identical subtrees, never match renumbered ASTs by node ID.
function evaluationMergeGraphs(original,changed,target){
 const nodes=[],edges=[],bySignature=new Map(),links=new Map(),outputs={};
 const boundNames=new Set([target,...(original?.nodes.find(n=>n.fact_id===target)?.aliases||[])]);
 for(const [side,graph] of [['A',original],['B',changed]]){
  if(!graph)continue;
  const byId=new Map(graph.nodes.map(n=>[n.id,n])),mapped=new Map();
  function visit(id){
   if(mapped.has(id))return mapped.get(id);
   const n=byId.get(id),parents=n.inputs.map(visit);
   const signature=JSON.stringify([n.kind,n.fact_id||null,n.kind==='fact'?n.label:null,n.operator||null,
    n.value??null,n.computed??null,n.evaluation?.state||'KNOWN',n.unit||null,n.evidence_types,n.evidence_id||null,n.source_usage_ids||[],
    n.kind==='control'?[side,n.id,n.expression]:n.kind==='variable'?n.label:null,parents]);
   let merged=bySignature.get(signature);
   if(!merged){merged={...n,id:'ev'+nodes.length,inputs:parents,sides:[],references:[],target:false};nodes.push(merged);bySignature.set(signature,merged);}
   if(!merged.sides.includes(side))merged.sides.push(side);merged.references.push({side,node:n});
   merged.target||=!!target&&(n.fact_id===target||n.aliases.includes(target)||
    side==='B'&&n.aliases.some(name=>name.startsWith('perturbed_')&&boundNames.has(name.slice('perturbed_'.length))));
   mapped.set(id,merged.id);
   for(const from of parents)addEdge(from,merged.id,side,false);
   return merged.id;
  }
  graph.nodes.forEach(n=>visit(n.id));outputs[side]=visit(graph.output);
  for(const e of graph.control_edges)addEdge(visit(e.from),visit(e.to),side,true);
 }
 function addEdge(from,to,side,control){
  const key=JSON.stringify([from,to,control]);let edge=links.get(key);
  if(!edge){edge={from,to,control,sides:[]};links.set(key,edge);edges.push(edge);}
  if(!edge.sides.includes(side))edge.sides.push(side);
 }
 return {nodes,edges,outputs};
}

// Bounded width; deep paths continue downward instead of shrinking into a wide strip.
function evaluationGraphLayout(model,width=620){
 width=Math.max(260,Math.min(680,width));
 const columns=width>=560?3:width>=370?2:1,padding=16,gap=14,height=76,rowGap=34;
 const cardWidth=(width-padding*2-(columns-1)*gap)/columns,levels=new Map(),positions=new Map(),groups=[];
 const controlParents=new Map();
 for(const edge of model.edges)if(edge.control){if(!controlParents.has(edge.to))controlParents.set(edge.to,[]);controlParents.get(edge.to).push(edge.from);}
 const byId=new Map(model.nodes.map(n=>[n.id,n])),visiting=new Set();
 function depth(id){
  if(levels.has(id))return levels.get(id);
  if(visiting.has(id))throw Error('계산·조건 연결에 순환이 있습니다.');
  visiting.add(id);const node=byId.get(id);if(!node)throw Error('연결 노드가 없습니다.');
  const parents=[...node.inputs,...controlParents.get(id)||[]];
  const level=parents.length?1+Math.max(...parents.map(depth)):0;
  visiting.delete(id);levels.set(id,level);return level;
 }
 for(const n of model.nodes)(groups[depth(n.id)]??=[]).push(n);
 let y=padding;
 for(const group of groups){
  if(!group)continue;
  group.sort((a,b)=>Number(b.target)-Number(a.target)||a.sides.join('').localeCompare(b.sides.join('')));
  group.forEach((node,i)=>positions.set(node.id,{x:padding+(i%columns)*(cardWidth+gap),y:y+Math.floor(i/columns)*(height+rowGap),width:cardWidth,height}));
  y+=Math.ceil(group.length/columns)*(height+rowGap);
 }
 return {positions,width,height:Math.max(180,y-rowGap+padding)};
}

function evaluationNodeValue(node){
 const state=node.evaluation?.state||node.availability;
 return state==='MISSING'?'근거 없음':state==='BLOCKED'?'계산 불가':node.computed??node.value??'값 미기록';
}
function evaluationAnswerComparison(original,changed){
 const output=graph=>graph?.nodes?.find(n=>n.id===graph.output);
 const a=output(original),b=output(changed);
 const numeric=node=>{
  if(!node||['MISSING','BLOCKED'].includes(node.evaluation?.state||node.availability))return null;
  const value=node.computed??node.value;
  if(typeof value!=='number'&&(typeof value!=='string'||!value.trim()))return null;
  const parsed=Number(value);return Number.isFinite(parsed)?parsed:null;
 };
 const A=numeric(a),B=numeric(b);
 if(A===null||B===null)return null;
 return {A,B,different:Math.abs(A-B)>1e-12*Math.max(1,Math.abs(A),Math.abs(B))};
}
// Reuse the viewer's DAG layout and node shapes, with less space between nodes.
function evaluationGraphPresentation(model,availableWidth,availableHeight){
 const vertical=evaluationGraphLayout(model,availableWidth);
 const ordered=[...model.nodes].sort((a,b)=>vertical.positions.get(a.id).y-vertical.positions.get(b.id).y);
 const compact=layoutLinkedGraph({...model,control_edges:model.edges.filter(e=>e.control),nodes:ordered});
 const positions=new Map(Object.entries(compact.positions).map(([id,p])=>[id,{x:p.x*.58,y:p.y*.58}]));
 const horizontal={positions,width:Math.max(...[...positions.values()].map(p=>p.x+60)),height:Math.max(...[...positions.values()].map(p=>p.y+62)),orientation:'horizontal'};
 const upright={positions:new Map([...vertical.positions].map(([id,p])=>[id,{x:p.x+p.width/2,y:p.y+34}])),width:vertical.width,height:vertical.height,orientation:'vertical'};
 const score=layout=>Math.min(availableWidth/layout.width,availableHeight/layout.height);
 return score(horizontal)>=score(upright)?horizontal:upright;
}
function evaluationDrawGraph(parent,original,changed,target,onTarget){
 if(!original){parent.append(el('p','empty','저장된 계산 그래프가 없습니다.'));return;}
 let model;try{model=evaluationMergeGraphs(evaluationCompactGraph(original),evaluationCompactGraph(changed),target);}
 catch(error){parent.append(el('p','banner','간략 그래프를 표시하지 못했습니다: '+error.message));return;}
 const comparison=evaluationAnswerComparison(original,changed);
 if(comparison?.different){const note=el('p','evaluation-answer-mismatch');note.append(el('strong','','최종 답이 다릅니다.'),document.createTextNode(' A = '+comparison.A+' ≠ B = '+comparison.B));parent.append(note);}
 renderGraphLegend(parent,{control:model.edges.some(e=>e.control)});
 const wrap=el('div','evaluation-graph'),detail=el('div','evaluation-node-detail small','문장·수식·노드를 선택하면 같은 근거와 연결 계산이 강조됩니다.');
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
 svg.setAttribute('role','group');svg.setAttribute('aria-label','원본 A와 변경 B의 계산 그래프');
 const available=Math.min(680,parent.getBoundingClientRect().width||620);
 let layout;try{layout=evaluationGraphPresentation(model,available-20,Math.max(280,(parent.getBoundingClientRect().height||430)-120));}catch(error){parent.append(el('p','banner',error.message));return;}
 svg.setAttribute('viewBox',`0 0 ${layout.width} ${layout.height}`);svg.setAttribute('width',layout.width);svg.setAttribute('height',layout.height);
 const elements=new Map(),edgeElements=[],byId=new Map(model.nodes.map(n=>[n.id,n]));
 function shape(tag,attrs,text){const element=document.createElementNS(ns,tag);for(const [key,value] of Object.entries(attrs))element.setAttribute(key,value);if(text!=null)element.textContent=text;return element;}
 evaluationDrawGraph.sequence=(evaluationDrawGraph.sequence||0)+1;
 const defs=shape('defs',{}),markerId='evaluation-arrow-'+evaluationDrawGraph.sequence;
 const marker=shape('marker',{id:markerId,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto'});marker.append(shape('path',{d:'M0 0L10 5L0 10Z',fill:'context-stroke'}));defs.append(marker);svg.append(defs);
 for(const edge of model.edges){
  const a=layout.positions.get(edge.from),b=layout.positions.get(edge.to),horizontal=layout.orientation==='horizontal';
  const path=shape('path',{d:horizontal?`M${a.x+27} ${a.y} C${a.x+66} ${a.y} ${b.x-66} ${b.y} ${b.x-27} ${b.y}`:`M${a.x} ${a.y+27} C${a.x} ${a.y+66} ${b.x} ${b.y-66} ${b.x} ${b.y-27}`,
   class:'evaluation-edge'+(edge.control?' evaluation-control-edge':edge.sides.join('')==='B'?' evaluation-changed-edge':''),'marker-end':`url(#${markerId})`});
  path.append(shape('title',{},(edge.control?'실행 조건 · ':'값 전달 · ')+edge.sides.join('/')+' : '+edge.from+' → '+edge.to));svg.append(path);edgeElements.push([edge,path]);
 }
 let pinned=null;
 function select(id,pin=false){
  if(pin)pinned=id;
  const connected=new Set();function visit(key){if(connected.has(key))return;connected.add(key);byId.get(key)?.inputs.forEach(visit);}
  const node=byId.get(id),chosen=node?.target?model.nodes.filter(n=>n.target):node?[node]:[];chosen.forEach(n=>visit(n.id));
  for(const [key,element] of elements)element.classList.toggle('evaluation-node-active',connected.has(key));
  for(const [edge,element] of edgeElements)element.classList.toggle('evaluation-edge-active',connected.has(edge.from)&&connected.has(edge.to));
  detail.replaceChildren();
  for(const item of chosen)for(const ref of item.references){const n=ref.node;detail.append(el('p','',ref.side+' · '+n.displayLabel+' = '+evaluationNodeValue(n)+(n.unit?' '+n.unit:'')),el('p','prose',n.expression||n.text||n.label));}
  if(!chosen.length)detail.append(el('span','','문장·수식·노드를 선택하면 연결 계산이 강조됩니다.'));
  onTarget?.(!!node?.target,chosen.flatMap(n=>n.references));
 }
 const short=(value,length)=>{const chars=Array.from(String(value));return chars.length>length?chars.slice(0,length-1).join('')+'…':chars.join('');};
 for(const node of model.nodes){
  const at=layout.positions.get(node.id),state=node.evaluation?.state,output=Object.values(model.outputs).includes(node.id);
  const group=shape('g',{class:'evaluation-node'+(node.target?' evaluation-target-node':'')+(state==='MISSING'?' evaluation-missing-node':state==='BLOCKED'?' evaluation-blocked-node':''),tabindex:0,role:'button','aria-label':node.sides.join('/')+' · '+node.displayLabel+' = '+evaluationNodeValue(node)});
  group.dataset.nodeId=node.id;group.dataset.target=String(node.target);
  const icon=graphNodeShape(node,{x:0,y:0},node.target&&node.sides.includes('B'));
  icon.setAttribute('transform',`translate(${at.x} ${at.y}) scale(.62)`);icon.classList.add('evaluation-node-shape');group.append(icon);
  const value=evaluationNodeValue(node),display=/^-?\d+\.\d{7,}$/.test(String(value))?String(Number(Number(value).toPrecision(7))):value;
  group.append(shape('text',{x:at.x,y:at.y-8,'text-anchor':'middle',class:'evaluation-node-side'},node.sides.join('/')),
   shape('text',{x:at.x,y:at.y+8,'text-anchor':'middle',class:'evaluation-node-value'},short(display,10)),
   shape('text',{x:at.x,y:at.y+43,'text-anchor':'middle',class:'evaluation-node-label'},short(node.displayLabel,18)));
  if(output){group.classList.add('evaluation-output-node');if(comparison?.different){group.classList.add('evaluation-output-mismatch');group.append(shape('text',{x:at.x,y:at.y+59,'text-anchor':'middle',class:'evaluation-output-mismatch-label'},node.id===model.outputs.A?'≠ B':'≠ A'));}}
  group.append(shape('title',{},node.references.map(({side,node:n})=>side+' · '+n.displayLabel+' = '+evaluationNodeValue(n)+'\n'+(n.expression||n.text||'')+'\n노드 '+n.sourceIds.join(', ')).join('\n\n')));
  group.onmouseenter=()=>select(node.id);group.onmouseleave=()=>select(pinned);group.onfocus=group.onmouseenter;group.onblur=group.onmouseleave;
  group.onclick=()=>select(node.id,true);group.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(node.id,true);}};
  elements.set(node.id,group);svg.append(group);
 }
 wrap.append(svg);parent.append(wrap,detail);
 const controls=el('div','toolbar');let scale=1;
 function zoom(value){scale=Math.max(.04,Math.min(3,value));svg.style.width=layout.width*scale+'px';svg.style.height=layout.height*scale+'px';}
 const navigation=bindGraphNavigation(wrap,svg,()=>scale,zoom);
 function fit(){navigation.resetPan();zoom(Math.min((wrap.clientWidth||available)/layout.width,(wrap.clientHeight||350)/layout.height)*.94);}
 controls.append(graphEnlargeButton(controls,wrap,fit),button('−',()=>navigation.zoom(scale/1.2)),button('+',()=>navigation.zoom(scale*1.2)),button('전체 맞춤',fit));controls.children[1].setAttribute('aria-label','그래프 축소');controls.children[2].setAttribute('aria-label','그래프 확대');
 wrap.before(controls);requestAnimationFrame(fit);parent.addEventListener('evaluation-fit',fit);
 parent.addEventListener('evaluation-target',()=>{const match=model.nodes.find(n=>n.target&&n.sides.includes('B'))||model.nodes.find(n=>n.target);if(match)select(match.id,true);});
 return {selectReference(side,nodeId,pin=false){const node=side&&model.nodes.find(n=>n.references.some(ref=>ref.side===side&&ref.node.sourceIds.includes(nodeId)));select(node?.id||pinned,pin);}};
}
