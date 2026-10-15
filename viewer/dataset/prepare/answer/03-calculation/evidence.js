function potGenerationEvidence(p,r){
 if(DATA.evaluation||DATA.original)return;
 const area=el('section','box llm-edited-area');area.append(el('strong','llm-chip','LLM 작업 · 원문에서 Python 코드 생성'),el('p','small','코드 생성은 LLM 작업이며, 코드 실행과 정답 대조는 Python 처리입니다. 재사용한 코드는 이전 생성 호출 기록을 표시합니다.'));
 area.append(button('사용한 프롬프트·입력 보기',async()=>{
  const {body}=showSchemaDialog('POT 코드 생성 · 실제 요청과 응답','저장된 생성 프롬프트·입력·모델 설정·응답을 확인합니다. 새 호출은 하지 않습니다.');
  const show=(row,title)=>{const calls=llmCallRecords(row,'pot.author');if(!calls.length)return 0;body.append(el('h3','',title));calls.forEach((call,i)=>{renderRawExchange(body,call);renderLlmCall(body,row,call,i+1);});return calls.length;};
  let count=show(r,'현재 실행의 생성 호출');
  if(eventOf(r,'replay-source.json')?.source_case){
   const pending=el('p','small','재사용한 코드의 이전 생성 기록을 읽고 있습니다.');body.append(pending);
   try{const history=await loadPotLogHistory(r.run,async name=>{const response=await fetch('/api/run?name='+encodeURIComponent(name),{cache:'no-store'});if(!response.ok)throw Error('이전 생성 기록 조회 실패');return response.json();});
    pending.remove();for(const entry of history)count+=show({...r,run:entry.run},'이전 생성 실행 · '+entry.run.path.split('/').at(-2));
   }catch(error){pending.textContent=error.message;}
  }
  if(!count)body.append(el('p','','연결된 LLM 생성 호출 기록을 찾지 못했습니다.'));
 }));p.append(area);
}
