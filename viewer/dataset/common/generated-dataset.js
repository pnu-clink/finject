/* Read the published standalone dataset, separate from evaluator selection. */
async function showGeneratedDataset(){
 const run=DATA.batch.name,{body}=showSchemaDialog('생성 데이터 합본','원문과 7유형의 실제 저장 내용입니다. 실패·Reject도 보존하며 자동 검사와 평가자 판정을 구분합니다.');
 body.append(el('p','','합본을 읽는 중입니다…'));
 try{
  const response=await fetch('/api/generated?name='+encodeURIComponent(run));
  if(!response.ok)throw Error('HTTP '+response.status);
  const archive=await response.json();if(!body.isConnected)return;
  body.replaceChildren();const counts=archive.counts;
  body.append(el('p','',`전체 ${counts.cases}문항 · 7유형 통과·Reject 없음 ${counts.production_eligible_cases}문항 · 제작 Reject ${counts.production_rejected_cases}문항 · annotation ${archive.annotation_state}`));
  const download=el('a','','dataset.jsonl 다운로드');download.href='/api/generated-file?name='+encodeURIComponent(run);download.download=run+'-dataset.jsonl';body.append(download);
  const label=el('label','','문제번호 '),select=el('select');select.setAttribute('aria-label','합본 문항 선택');
  for(const id of archive.cases){const option=el('option','',id);option.value=id;select.append(option)}
  label.append(select);body.append(label);const area=el('section');body.append(area);
  function display(row){
   area.replaceChildren();if(!row){area.append(el('p','','저장된 문항이 없습니다.'));return;}
   area.append(el('p','',row.id+' · '+(row.production_selection.eligible?'7유형 통과·Reject 없음':'선정 조건 미충족')));
   for(const item of [row.original,...row.variants]){
    const block=el('details');block.open=item.type==='ORIGINAL';
    block.append(el('summary','',item.type+' · '+item.automatic_validation.status+' · '+(item.production_review.decision||'미판정')+' · '+item.annotation.status));
    if(item.automatic_validation.reason)block.append(el('p','small',item.automatic_validation.reason));
    if(item.production_review.record?.reason)block.append(el('p','small',item.production_review.record.reason));
    for(const key of ['question','context']){block.append(el('h4','',key));const text=el('pre','',item[key]??'NOT_RUN · Q/C 저장 없음');text.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;max-height:420px;overflow:auto';block.append(text)}
    const metadata=el('details');metadata.append(el('summary','','메타정보'),el('pre','',JSON.stringify(item.metadata,null,2)));block.append(metadata);area.append(block);
   }
  }
  let request=0;select.value=archive.case?.id||'';display(archive.case);
  select.onchange=async()=>{const current=++request;area.replaceChildren(el('p','','합본을 읽는 중입니다…'));
   try{const r=await fetch('/api/generated?name='+encodeURIComponent(run)+'&case='+encodeURIComponent(select.value));if(!r.ok)throw Error('HTTP '+r.status);const value=await r.json();if(current===request&&area.isConnected)display(value.case)}
   catch(error){if(current===request&&area.isConnected)area.replaceChildren(el('p','','합본을 읽지 못했습니다: '+error.message))}
  };
 }catch(error){if(body.isConnected)body.replaceChildren(el('p','','합본을 읽지 못했습니다: '+error.message))}
}
