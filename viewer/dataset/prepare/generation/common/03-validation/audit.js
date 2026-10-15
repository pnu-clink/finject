function semanticAuditPanel(p,r){
 const card=el('section','box semantic-audit');card.append(el('h2','','02-audit-meaning · 완성 문장 의미 검사'));p.append(card);
 const controls=el('div','toolbar');controls.append(currentAuditPromptButton(r));card.append(controls);
 const a=auditRecord(r);if(!a){card.append(el('p','','미실행 · 최종 문장에 대한 실제 감사 결과가 아직 없습니다.'));return;}
 const auditCalls=llmCallRecords(r,'dtt.audit').filter(call=>call.dir===a.stage+'/');
 if(auditCalls.length){card.classList.add('llm-edited-area');controls.prepend(el('strong','llm-chip','LLM 작업 · 의미 검사'));controls.append(button('검증 Request · Response 원문 보기',()=>{const {dialog,body}=showSchemaDialog('의미 검사 · 실제 요청과 응답','이 판정에 연결된 당시 호출 기록입니다. 현재 검증 지침과 구분합니다.');markAuditFailure(dialog,a);auditCalls.forEach(call=>renderRawExchange(body,call));jsonBox(body,'실제 검증 입력',a.request);auditCalls.forEach((call,i)=>renderLlmCall(body,r,call,i+1));}));
  card.append(el('h3','','02-audit-meaning 검증 LLM · 실제 응답 (실패 이유 포함)'));
  for(const call of auditCalls){const pre=el('pre','json-scroll',typeof call.raw?.text==='string'?call.raw.text:'저장된 모델 원응답이 없습니다.');pre.style.whiteSpace='pre-wrap';pre.style.overflowWrap='anywhere';card.append(pre);}
 }
 markAuditFailure(card,a);const report=a.report;card.append(el('p','small',report.audit_version===3?'새 기준 · 세 가지 의미 판단': '이전 8항목 검사 기록 · 새 기준으로 재검사한 결과가 아닙니다.'));if(report.model)card.append(el('p','small',`실행 모델: ${report.model} · 추론: ${report.effort??'기존 로그 참조'}`));card.append(el('p',a.stale||report.status==='FAIL'?'banner':'small',auditStatus(r)));
 if(report.failure_kind==='AUDIT_RESPONSE_INVALID'||(report.reason&&!report.findings?.length))card.append(el('p','banner','감사 응답 검사에서 중단됐습니다. 본문의 의미가 잘못됐다고 판정한 결과는 아닙니다.'));
 for(const error of report.response_errors||[])card.append(box(error.criterion+' · '+error.code,error.quote||'해당 항목의 적용 여부를 잘못 응답했습니다.'));
 if(a.stale)card.append(el('p','','아래 기록은 이전 본문에 대한 검사입니다. 현재 본문이 통과한 것으로 사용하지 않습니다.'));
 const meanings={CONFLICT:'상충 주장 존재',MISSING_TARGET_EVIDENCE:'선택한 입력값의 근거 없음',ANSWERABLE:'답변 가능한 원문',RESOLVED:'문맥상 해소 근거 존재',MIXED:'여러 상태가 섞임',UNKNOWN:'판정 불가'};
 if(!a.stale&&report.status==='FAIL'){const failure=el('div','failure-banner');for(const item of auditFailureItems(report,a.request))appendFailureEvidence(failure,item);card.append(failure);}
 if(report.audit_version!==3)card.append(box('실제 문장에서 관찰한 상태',meanings[report.observed_state]||report.observed_state),box('관찰 설명 · 실패 사유와 별도',report.state_reason||'관찰 설명 없음'));
 const labels={unintended_change:'허용하지 않은 의미 변화 없음',preservation:'원문·질문 보존',planned_change:'의도한 변경',scope:'대상·기간·단위',source_assignment:'출처 배정',unplanned_content:'계획 밖 숫자·힌트',readability:'문장 자연스러움',explicit_resolution:'정정·해소 표현',ea_consistency:'EA 삭제·일관성'};
 const table=el('table','events');const head=el('tr');for(const t of ['검사 항목','판정',report.audit_version===3?'실패·보류 이유':'이유와 실제 문장 근거'])head.append(el('th','',t));table.append(head);
 for(const f of report.findings||[]){const tr=el('tr'),reason=el('td','',f.reason||'—');for(const e of f.evidence||[])reason.append(el('blockquote','prose',(e.field==='original_context'?'원문':e.field==='question'?'질문':'최종 본문')+' · '+e.quote));tr.append(el('td','',labels[f.criterion]||f.criterion),el('td',f.judgment==='FAIL'?'bad':'',({PASS:'통과',FAIL:'실패',UNKNOWN:'판정 불가',NOT_APPLICABLE:'해당 없음'}[f.judgment]||f.judgment)),reason);table.append(tr);}if(report.audit_version===3)card.append(table);else{const previous=el('details');previous.append(el('summary','','이전 8항목 검사 상세 보기'),table);card.append(previous);}
 card.append(el('p','small',report.audit_version===3?'Python은 편집 보존·숫자 규칙·응답 스키마와 세 항목을 확인합니다. 의미 판단은 LLM 결과이며, 역산·우회 및 EA 전체 답변 불가능 증명은 보류입니다. 사람 승인은 별도입니다.':'이전 기준의 단일 모델 검사입니다. 인용문·스키마·8개 항목 및 관찰 상태를 당시 기준으로 보존합니다. 사람 승인은 별도입니다.'));
 jsonBox(card,'감사 결과·본문 버전 연결',report);jsonBox(card,'감사에 실제로 전달한 내용',a.request);
}
