function renderGenerationText(panel,row,variant){
 panel.id='g02-full-context';panel.style.scrollMarginTop='155px';
 const a=row.run.generation||{},record=a[variant+'/run.json'],plan=generationPlan(row,variant);
  const comparison=a[variant+'/03-validation/04-comparison.json'];
  const current=record?.observation||a[variant+'/02-generate-text/04-observation.json']||generationDiagnostic(record);
  if(current?.diagnostic)panel.append(el('p','banner','생성 검사 실패 응답의 진단용 비교입니다. 저장된 편집 위치를 그대로 적용했으며, 통과한 수정본이 아닙니다.'));
  const original=comparison?.reference||row.run.artifacts['data.json']||row.sample;
  panel.append(box('질문 · Q',current?.question??original.question??row.sample.question));
  if(!current){const source=box('원본 본문',original.context);panel.append(source);highlightGenerationFacts(source.querySelector('.prose'),original.context,original.context,row.run.artifacts['03-calculation/02-prepare-code/03-program.json']);}
  if(current){const columns=el('div','cols'),left=box('원본 본문',original.context),right=el('div','box');right.append(el('h3','','생성 본문'));const prose=el('div','prose');for(const op of eaSentenceDiff(original.context,current.context)){if(op.kind==='equal')prose.append(document.createTextNode(op.text));else {if(op.before)prose.append(el('mark','diff-del',op.before));if(op.after)prose.append(el('mark','diff-add',op.after));}}if(plan?.axis==='IC_SOURCE'){
 const legend=el('div','legend');for(const [cls,label] of [['diff-add','초록 · IC-VALUE에서 추가한 문장'],['source-a-add','분홍 · A 출처'],['source-b-add','빨강 · B 출처']])legend.append(el('mark',cls,label));panel.append(legend);
 const input=a[variant+'/02-generate-text/01-input.json'],baseFolder=variant==='04-ic-source-type-2'?'02-ic-value-after':'01-ic-value-before';
 const basePatches=comparison?.value_dependency||a[baseFolder+'/02-generate-text/05-patches.json'];
 try{
  const segments=sourceComparisonSegments({...row,sample:original},{original_context:input.context,preview_context:current.context,patches:record?.patches||a[variant+'/02-generate-text/05-patches.json']||record?.generation_response?.patches,source_condition:variant==='04-ic-source-type-2'?'B_ONLY':'A_ONLY'},{original_context:original.context,patches:basePatches});
  prose.replaceChildren();for(const segment of segments){if(!segment.kind)prose.append(document.createTextNode(segment.text));else {const cls={VALUE:'diff-add',SOURCE_A:'source-a-add',SOURCE_B:'source-b-add'}[segment.kind];prose.append(el('mark',cls,segment.text));}}
 }catch(error){prose.replaceChildren(document.createTextNode(current.context));panel.append(el('p','small','색상 연결을 확인하지 못했습니다: '+error.message));}
 }right.append(prose);columns.append(left,right);panel.append(columns);
 const program=row.run.artifacts['03-calculation/02-prepare-code/03-program.json'];
 highlightGenerationFacts(left.querySelector('.prose')||left.lastElementChild,original.context,original.context,program);
 highlightGenerationFacts(prose,original.context,current.context,program);
 panel.append(el('p','small','근거 강조에 마우스를 올리면 Preparation 계산 근거 이름과 값이 표시됩니다. 변경·삭제된 근거는 원본 위치와 일치하지 않으므로 강조하지 않습니다.'));
 }
  if(current)renderGenerationTextDetails(panel,row,variant,original,current);
  if(record?.reason)panel.append(el('p','banner',record.reason));
 // Open an annotation link at the complete text once, after live artifacts render.
 if(current&&location.hash==='#g02-full-context'&&!window.annotationG02Shown){
  const query=new URLSearchParams(location.search);
  if(query.get('case')===row.sample.id&&query.get('variant')===variant)requestAnimationFrame(()=>{
   if(panel.isConnected&&!window.annotationG02Shown){window.annotationG02Shown=true;panel.scrollIntoView({block:'start',behavior:'instant'});}
  });
 }
}
