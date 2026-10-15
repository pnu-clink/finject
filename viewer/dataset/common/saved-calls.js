// [VM02] Read current CLI/API layouts without confusing a handler envelope with raw text.
function savedMenuCalls(row,scope,role){
 const a=row.run.artifacts,roles={'pot.author':['pot.author','01-preparation.03-calculation.pot'],'dtt.realize':['dtt.realize','02-generation.02-generate-text.realization'],'dtt.audit':['dtt.audit','shared.01-02.02-03.review-and-validation']};
 const prefixes=Array.isArray(scope)?scope:[scope];
 return Object.entries(a).filter(([path,value])=>prefixes.some(prefix=>path.startsWith(prefix))&&(!row.run.artifact_aliases?.[path]||!Object.hasOwn(a,row.run.artifact_aliases[path]))&&/\/01-input\.json$/.test(path)&&typeof value?.prompt==='string'&&(!role||(roles[role]||[role]).includes(value.role))).sort(([a],[b])=>a.localeCompare(b)).map(([path,cli])=>{
  const dir=path.slice(0,-'01-input.json'.length),read=name=>a[dir+name];
  return {role:role||cli.role,dir,requestPath:path,responsePath:dir+'02-raw-response.json',cli,
   model:read('01-input/model-request.json'),raw:read('02-raw-response.json'),definition:read('01-input/response-schema.json'),check:read('03-result/schema-check.json'),
   start:read('01-input/api-start.json')||read('01-input/cli-start.json'),transport:read('02-raw-response/api-execution.json')||read('02-raw-response/cli-execution.json'),usage:read('03-result/usage.json')};
 });
}
function menuCallButton(parent,row,scope,label){
 if(DATA.evaluation||DATA.original)return;
 parent.append(button(label||'사용한 프롬프트·입력 보기',()=>{
  const {body}=showSchemaDialog(label||'실제 요청과 응답','선택한 단계의 저장된 호출입니다. 원응답·검사 실패 기록을 함께 표시합니다.');
  const calls=savedMenuCalls(row,scope);if(!calls.length)body.append(el('p','small','이 단계에서 실제 전송 프롬프트가 저장된 호출을 찾지 못했습니다. 아래 결과 파일에서 준비 입력과 미실행 사유를 확인해 주세요.'));
  calls.forEach((call,i)=>{call.feedbackRow=row;
   const callHeading=el('h3','','LLM 호출 '+(i+1));appendFeedbackBadge(callHeading,callFeedbackEvidence(row,call).state);body.append(callHeading);renderRawExchange(body,call);renderLlmCall(body,row,call,i+1);
  });
 },'llm-call-button'));
}

function renderCallFeedback(parent,row,call){
 const evidence=callFeedbackEvidence(row,call),section=el('section','box feedback-details');
 section.append(el('h3','','적용한 feedback'));appendFeedbackBadge(section,evidence.state);
 if(evidence.state==='none')section.append(el('p','small','이 호출에서 적용한 피드백 기록이 없습니다.'));
 if(evidence.state==='unknown')section.append(el('p','small','참조 기록은 있지만 실제 전송 입력에 포함됐는지 확인할 수 없습니다.'));
 for(const source of evidence.sources){section.append(filePathLabel(source.path));if(source.content?.guidance)section.append(el('pre','',source.content.guidance));}
 if(evidence.ref){section.append(filePathLabel(row.run.path+'/'+evidence.refPath));jsonBox(section,'feedback.ref 원본 경로 · '+evidence.refPath,evidence.ref);}
 if(evidence.state==='used'){
  section.append(el('h4','','최종 전송 프롬프트에서 들어간 내용'));
  for(const source of evidence.applied)section.append(el('pre','feedback-sent-excerpt',source.content.guidance));
  section.append(filePathLabel(row.run.path+'/'+call.requestPath+' · request.instructions / prompt'));
 }
 parent.append(section);
}

function callFeedbackEvidence(row,call){
 const refPath=call.dir+'01-input/feedback-ref.json',ref=row.run.artifacts[refPath];
 const sources=row.run.feedback_sources?.[refPath]||[];
 const sent=call.cli?.request?.instructions??(call.cli?.transport==='cli'?call.cli?.prompt:null);
 const transmitted=!!(call.raw||call.transport);
 const applied=sources.filter(s=>s.hash_matches&&typeof s.content?.guidance==='string'&&s.content.guidance.trim()&&typeof sent==='string'&&sent.includes(s.content.guidance));
 const expected=(ref?.references||[]).filter(r=>r.applied!==false);
 const used=ref?.applied===true&&transmitted&&expected.length>0&&expected.every(r=>applied.some(s=>s.path===r.path));
 return {state:used?'used':ref?.applied||expected.length?'unknown':'none',ref,refPath,sources,applied,sent};
}
function stageFeedbackState(row,variant,stage,substep){
 const selected=variant?generationRow(row,variant):row;
 const reused=(selected.run.artifacts['run.json']?.reused_steps||[]).some(s=>s.replace('02-review-and-correct','02-review')===stage)||(!variant&&row.run.carried_round)||(variant&&row.run.generation_origins?.[variant]&&row.run.generation_origins[variant]!==DATA.batch.round);
 if(reused)return 'reused';
 const calls=savedMenuCalls(selected,stage+'/').filter(c=>!substep||c.dir.startsWith(stage+'/'+substep+'/'));
 const states=calls.map(c=>callFeedbackEvidence(selected,c).state);
 if(states.includes('used'))return 'used';
 if(states.includes('unknown'))return 'unknown';
 const prefix=stage+'/'+(substep?substep+'/':'');
 return Object.entries(selected.run.artifacts).some(([p,v])=>p.startsWith(prefix)&&p.endsWith('/feedback-ref.json')&&v?.applied)?'unknown':'none';
}
function appendFeedbackBadge(parent,state){
 const labels={used:'피드백 사용',reused:'이전 차수 재사용',unknown:'피드백 전달 미확인'};
 if(!labels[state])return;
 parent.append(el('span','feedback-badge feedback-'+state,labels[state]));
 if(state==='used')parent.classList.add('feedback-used-outline');
}
