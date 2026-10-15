function previewSourceLinks(parent,r,preview){
 const source=preview.status==='GENERATED'?realizationStage(r)+'/03-result.json':[`04-perturbation/variants/${r.label}/05-text-input-preview.json`,`04-perturbation/variants/${r.label}/text-preview.json`].find(path=>eventOf(r,path));
 const card=el('section','box');card.append(el('h3','','표시 문장과 실패 응답 · 출처 확인'),el('p','small llm-path','현재 비교 문장: '+r.run.path+'/'+source));
 card.append(button('현재 비교 문장의 원본 파일 보기',()=>{const {body}=showSchemaDialog('현재 비교 문장 출처',r.run.path+'/'+source);body.append(jsonViewer(eventOf(r,source),source));}));
 const fail=realizationFailure(r);
 if(fail){const path=fail.stage+'/realize/02-raw-response.json',raw=eventOf(r,path),call=llmCallRecords(r,'dtt.realize').find(c=>c.dir===fail.stage+'/');
 card.append(el('p','banner','위 문장은 계획 미리보기입니다. 아래 실패 응답과 다른 자료이며, 실패 응답이 위 본문에 적용된 것은 아닙니다.'),el('p','small llm-path','실패 원응답: '+r.run.path+'/'+path));
 card.append(button('실패한 실제 LLM 응답 원문 보기',()=>{const {dialog,body}=showSchemaDialog('실패한 생성 응답 · 원문',r.run.path+'/'+path);dialog.classList.add('llm-failed');body.append(el('strong','failure-status','Python 생성 검사 실패 · '+fail.reason));if(call)renderRawExchange(body,call);else body.append(el('pre','json-scroll',raw?.text??'이 단계에는 모델 원응답이 없습니다.'));jsonBox(body,'실패 기록',fail.record);}));}
 parent.append(card);
}
