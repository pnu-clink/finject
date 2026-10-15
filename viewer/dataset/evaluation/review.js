const evaluationTypes=[['01-ic-value-before','IC-VALUE 앞'],['02-ic-value-after','IC-VALUE 뒤'],['03-ic-source-type-1','IC-SOURCE Type 1'],['04-ic-source-type-2','IC-SOURCE Type 2'],['05-ic-relation','IC-RELATION'],['06-ea-earlier-input','EA 01'],['07-ea-later-input','EA 02']];

function evaluationEvidence(row,variant){
 const files=row.run.generation||{},prefix=variant+'/',record=files[prefix+'run.json'];
 const original=files[prefix+'03-validation/04-comparison.json']?.reference||row.run.artifacts['data.json']||row.sample;
 const current=variant?(record?.observation||files[prefix+'02-generate-text/04-observation.json']||generationDiagnostic(record)):null;
 return {original,current,plan:variant?generationPlan(row,variant):null,record,
  patches:files[prefix+'02-generate-text/05-patches.json']||[],
  blocks:typeof current?.context==='string'?eaSentenceDiff(original.context||'',current.context):[]};
}

function evaluationTextClass(evidence,text){
 for(const patch of evidence.patches)for(const segment of patch.segments||[]){
  if(text.trim()&&segment.text?.includes(text.trim())){
   if(segment.kind==='SOURCE_A')return 'source-a-add';
   if(segment.kind==='SOURCE_B')return 'source-b-add';
  }
 }
 return 'diff-add';
}

function evaluationMarkedText(parent,evidence,value,baseClass='diff-add'){
 const segments=evidence.patches.flatMap(p=>p.segments||[]).filter(s=>['SOURCE_A','SOURCE_B'].includes(s.kind)&&s.text);
 let at=0;
 const hits=segments.map(segment=>({segment,start:value.indexOf(segment.text)})).filter(h=>h.start>=0).sort((a,b)=>a.start-b.start);
 for(const {segment,start} of hits){
  if(start<at)continue;if(start>at)parent.append(el('mark',baseClass,value.slice(at,start)));
  parent.append(el('mark',segment.kind==='SOURCE_A'?'source-a-add':'source-b-add',segment.text));at=start+segment.text.length;
 }
 if(at<value.length)parent.append(el('mark',baseClass,value.slice(at)));
}

function evaluationContext(parent,evidence,row,variant){
 const section=el('section','box evaluation-context'),head=el('div','splithead'),body=el('div','prose evaluation-context-prose');
 head.append(el('h3','','원문 맥락'),el('span','small','초록: 추가 · 취소선: 삭제 · 분홍/빨강: 출처'));
 section.append(head,body);parent.append(section);
 const blocks=evidence.blocks.length?evidence.blocks:[{kind:'equal',text:evidence.original.context||'원본 본문이 없습니다.'}];
 const hasChanges=blocks.some(b=>b.kind==='change');let full=!hasChanges;
 function draw(){
  body.replaceChildren();
  blocks.forEach((block,i)=>{
   if(block.kind==='change'){
    if(block.before)body.append(el('mark','diff-del',block.before));
    if(block.after)evaluationMarkedText(body,evidence,block.after);
    return;
   }
   const value=block.text,chars=Array.from(value),window=220;
   if(full||chars.length<=window*2+60){body.append(document.createTextNode(value));return;}
   const leading=i===0,trailing=i===blocks.length-1;
   const gap=button('… '+(chars.length-window*(leading||trailing?1:2))+'자 생략 · 펼치기',()=>{full=true;toggle.textContent='변경 주변만';draw();},'evaluation-context-gap');
   gap.setAttribute('data-i18n-ui','');
   if(!leading)body.append(document.createTextNode(chars.slice(0,window).join('')));
   body.append(gap);
   if(!trailing)body.append(document.createTextNode(chars.slice(-window).join('')));
  });
 }
 const toggle=button(full?'변경 주변만':'전체 보기',()=>{full=!full;toggle.textContent=full?'변경 주변만':'전체 보기';draw();});toggle.hidden=!hasChanges;head.append(toggle);draw();
 if(variant&&!evidence.current)section.append(el('p','small','저장된 생성 본문이 없어 원본만 표시합니다.'));
}

function evaluationProgress(){
 const batch=DATA.evaluation.batches.find(x=>x.batch.name===DATA.batch.name),type=window.preparationVariant||'ANSWER';
 const total=batch.cases.filter(c=>type==='ANSWER'||c.variants.includes(type)).length;
 const done=[...evaluationState.records.values()].filter(r=>r.run===batch.batch.name&&r.variant===type&&r.confirmed).length;
 return '판정 저장 '+done+' / '+total+' · '+(evaluationTypes.find(([key])=>key===type)?.[1]||'Preparation');
}

function renderEvaluationCase(panel,row,variant){
 panel.classList.add('evaluation-case');
 const evidence=evaluationEvidence(row,variant),{original,current,plan,record}=evidence;
 const progress=el('p','small evaluation-progress',evaluationProgress());panel.append(progress);
 const question=el('section','box evaluation-question');question.append(el('h3','','질문 · Q'),el('p','',current?.question??original.question??'질문 미기록'));
 const originalGraph=plan?.original_graph||row.run.artifacts['04-graph/05-save-graph/01-graph.json'],changedGraph=plan?.graph;
 const originalOutput=originalGraph?.nodes?.find(n=>n.id===originalGraph.output),changedOutput=changedGraph?.nodes?.find(n=>n.id===changedGraph.output);
 const results=el('p','small','원본 정답: '+(original.reference_answer??row.sample.reference_answer??'미기록'));
 if(originalOutput)results.append(document.createTextNode(' · 원본 계산 A: '+evaluationNodeValue(originalOutput)));
 if(changedOutput)results.append(document.createTextNode(' · '+(plan.axis==='EA'?'근거 삭제 후 B: ':'변경 근거 계산 B: ')+evaluationNodeValue(changedOutput)));
 question.append(results);panel.append(question);
 if(current?.diagnostic)panel.append(el('p','banner','생성 검사 실패 응답의 진단용 비교입니다. 통과한 수정본이 아닙니다.'));
 const failures=stageFailureEntries(row,variant,variant?'02-generate-text':'03-calculation');
 if(record?.status==='FAIL'||failures.length)panel.append(el('p','banner','저장된 자동 검사 실패 · '+(record?.reason||failures[0]?.reason||'단계별 보기에서 검사 근거를 확인하세요.')));
 const columns=el('div','evaluation-evidence-grid'),changes=el('section','box evaluation-changes'),graph=el('section','box evaluation-graph-card');
 changes.append(el('h3','',variant?'삽입·수정된 문장':'원본 본문'));graph.append(el('h3','','계산 그래프 · 간략 보기'));columns.append(changes,graph);panel.append(columns);
 const target=plan?.target||plan?.intent?.target,targetNode=originalGraph?.nodes?.find(n=>n.fact_id===target);
 const targetBox=el('div','evaluation-target'),targetMark=el('button',(plan?.axis==='EA'?'ea-deletion-target ':'')+'evaluation-target-button',
  target?(plan.axis==='EA'?'삭제 대상: ':'변경 대상: ')+target+' = '+(targetNode?evaluationNodeValue(targetNode):plan.intent?.target_original?.value??'값 미기록')+(targetNode?.unit?' '+targetNode.unit:''):'');
 if(target){targetBox.append(targetMark);changes.append(targetBox);}
 const edits=evidence.blocks.filter(b=>b.kind==='change');
 if(!variant)changes.append(el('div','prose evaluation-original',original.context||'원본 본문이 없습니다.'));
 else if(edits.length)edits.forEach((edit,i)=>{
  const card=el('section','evaluation-edit');card.append(el('h4','','변경 '+(i+1)+' · '+(edit.before.trim()&&edit.after.trim()?'문장 교체':edit.before.trim()?'삭제':'삽입')));
  if(edit.before.trim()){card.append(el('p','small','원문'),el('div','prose diff-del',edit.before));}
  if(edit.after){card.append(el('p','small','생성 문장'),el('div','prose '+evaluationTextClass(evidence,edit.after),edit.after));}
  changes.append(card);
 });
 else changes.append(el('p','small',current?'원본과 생성 본문 사이에 변경이 없습니다.':'저장된 생성 본문이 없습니다. 변경 문장을 추정하지 않습니다.'));
 if(plan?.intent?.relation){const relation=plan.intent.relation;changes.append(el('p','banner','추가 관계: '+(relation.operand?.value??'값 미기록')+' '+({multiply:'×',divide:'÷'}[relation.operation]||relation.operation)+' '+relation.factor));}
 if(plan?.intent?.perturb_position)changes.append(el('p','small','문장 배치: 원래 주장 '+(plan.intent.perturb_position==='before'?'앞':'뒤')));
 const program=row.run.artifacts['03-calculation/02-prepare-code/03-program.json'];
 evaluationDrawGraph(graph,graphWithSourceUsage(originalGraph,program?.source_usage),graphWithSourceUsage(changedGraph,plan?.program?.source_usage),target,
  active=>targetMark.classList.toggle('ea-deletion-active',active));
 if(target){targetMark.type='button';targetMark.onclick=()=>graph.dispatchEvent(new Event('evaluation-target'));targetMark.setAttribute('aria-label','변경·삭제 대상과 계산 그래프 연결');}
 if(variant)evaluationContext(panel,evidence,row,variant);
 const review=el('section','box evaluation-review');panel.append(review);renderEvaluationReview(review,row,variant);
}
