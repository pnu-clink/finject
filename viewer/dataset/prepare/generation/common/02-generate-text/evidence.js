function realizationEvidence(parent,r,generated){
 if(!generated)return;
 parent.classList.add('llm-edited-area');
 const selectedStage=realizationStage(r),selectedRef=eventOf(r,selectedStage+'/03-result/metadata.json')?.realization_call_ref;
 const selectedCalls=llmCallRecords(r,'dtt.realize').filter(c=>c.dir===callSourceDir(selectedRef||selectedStage));
 const tools=el('div','toolbar');tools.append(el('strong','llm-chip','LLM 작업 · 저장된 생성 결과'),button('사용한 프롬프트·입력 보기',()=>{
  const {body}=showSchemaDialog('LLM 문장 생성 · 실제 요청과 응답','현재 표시한 수정본에 연결된 저장 기록입니다. 새 LLM 호출은 하지 않습니다.');
  const stage=realizationStage(r),ref=eventOf(r,stage+'/03-result/metadata.json')?.realization_call_ref;
  const calls=llmCallRecords(r,'dtt.realize').filter(c=>c.dir===callSourceDir(ref||stage));
  calls.forEach(call=>renderRawExchange(body,call));
  jsonBox(body,'문장 생성 입력 JSON · 수정 범위와 지시',eventOf(r,stage+'/01-input.json'));
  if(!calls.length)body.append(el('p','','이 수정본에 연결된 실제 호출 기록이 없습니다.'));
  calls.forEach((call,i)=>renderLlmCall(body,r,call,i+1));
 }));tools.append(currentRealizationPromptButton(r));parent.append(tools);
 parent.append(el('h4','','01-generate-text 생성 LLM · 실제 응답'),el('p','small','아래는 모델이 반환한 편집 응답 원문입니다. text가 빈 문자열이면 해당 위치를 삭제하라는 결과이며, 완성 본문은 Python이 이를 적용해 만듭니다. 실패 판정의 설명은 아래 02-audit-meaning 검증 LLM 응답에서 확인합니다.'));
 if(!selectedCalls.length)parent.append(el('p','small','연결된 생성 호출 기록이 없습니다.'));
 for(const call of selectedCalls){const pre=el('pre','json-scroll',typeof call.raw?.text==='string'?call.raw.text:'저장된 모델 원응답이 없습니다.');pre.style.whiteSpace='pre-wrap';pre.style.overflowWrap='anywhere';parent.append(pre);}
}
