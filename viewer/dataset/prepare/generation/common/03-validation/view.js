function renderGenerationValidation(panel,row,variant){
 renderEAInverseReview(panel,row,variant);
 const a=row.run.generation||{},report=a[variant+'/03-validation/03-result.json']||a[variant+'/run.json']?.audit;
 for(const [file,key,title] of [['05-recovery-screen.json','recovery_screen','기존 Python 제한 역산 · 참고'],['06-source-exact.json','source_exact','IC-SOURCE 출처 문구 제거 검사']]){
  const check=a[variant+'/03-validation/'+file]||a[variant+'/run.json']?.[key];
  if(check){const section=el('section','box');section.append(el('h2','',title),badge(check.status));section.append(el('p','small',check.reason||(check.unsupported_reasons||[]).join(' · ')));if(key==='recovery_screen')section.append(el('p','small',check.affects_quality_status===false?'기존 제한 계산의 참고 기록입니다. 복원 여부로 EA 판정을 바꾸지 않습니다. 미평가는 복원 불가가 아닙니다.':'과거 실행의 검사 기록입니다. 당시 판정은 그대로 보존합니다.'));jsonBox(section,'검사 근거 · '+file,check);panel.append(section);}
 }
 renderSavedAudit(panel,report,'완성 문장 의미 검사');menuCallButton(panel,generationRow(row,variant),'03-validation/','검증 Request · Response 원문 보기');
}
function eaInverseRecord(row,variant){
 const a=row.run.generation||{},base=variant+'/',state=a[base+'run.json']||{},review=a[base+'05-human-review/01-result.json']||{};
 const ref=state.inverse_review_ref||review.inverse_review_ref||a[base+'03-validation/07-ea-inverse-review/latest.ref.json'];
 if(!ref)return null;
 if(typeof ref.path!=='string'||!/^03-validation\/07-ea-inverse-review\/attempt-\d+\/03-result\/inverse-review\.json$/.test(ref.path))return {stale:true};
 const record=a[base+ref.path];if(!record)return {missing:true};
 const qc=a[base+record.request_ref],current=a[base+'02-generate-text/04-observation.json']||state.observation;
 const bound=qc&&current&&qc.question===current.question&&qc.context===current.context&&record.observation_sha256===ref.observation_sha256;
 return {record,qc,stale:!bound,display:a[base+record.evidence_display_check_ref]};
}
function appendInverseEvidence(parent,source,spans){
 const chars=Array.from(source),valid=spans.filter(p=>Number.isInteger(p.start)&&Number.isInteger(p.end)&&p.start>=0&&p.end>p.start&&p.end<=chars.length&&chars.slice(p.start,p.end).join('')===p.quote).sort((a,b)=>a.start-b.start||a.end-b.end);
 const merged=[];for(const p of valid){const last=merged[merged.length-1];if(last&&p.start<=last.end)last.end=Math.max(last.end,p.end);else merged.push({start:p.start,end:p.end});}
 let end=0;for(const p of merged){parent.append(document.createTextNode(chars.slice(end,p.start).join('')));parent.append(el('mark','ea-inverse-evidence',chars.slice(p.start,p.end).join('')));end=p.end;}parent.append(document.createTextNode(chars.slice(end).join('')));
}
function renderEAInverseReview(panel,row,variant){
 const data=eaInverseRecord(row,variant);if(!data)return;
 const section=el('section','box ea-inverse-review');section.append(el('h2','','EA 역산 검토 · LLM'));panel.append(section);
 section.append(el('p','small','역산 가능 여부를 분석용으로 기록합니다. true/false 어느 쪽도 EA 통과·실패를 변경하지 않습니다. Python은 식을 풀거나 의미를 재판정하지 않습니다.'));
 if(data.stale||data.missing){section.append(el('p','small',data.stale?'검토 Q/C와 현재 EA 문장이 달라 판정·하이라이트를 표시하지 않습니다.':'연결된 역산 검토 원본을 찾을 수 없습니다.'));return;}
 const record=data.record,annotation=record.inverse_review;
 section.append(el('p','small','실행 상태: '+record.status+' · 모델: '+(record.model?.model||record.model?.provider||'미기록')+' · 추론: '+(record.model?.effort||'미기록')));
 if(record.status!=='COMPLETED'||!annotation){section.append(el('p','small','역산 판정 없음 · '+(record.reason||record.status)+'. 호출·응답 실패는 false가 아닙니다.'));jsonBox(section,'역산 검토 실행 기록',record);return;}
 section.append(el('strong','inverse-judgment',annotation.inverse_possible?'역산 가능 · true':'역산 불가 · false'),el('p','','대상: '+annotation.missing_quantity),el('p','',annotation.reason));
 if(annotation.formula)section.append(el('h3','','복원식 · LLM 제안'),el('pre','ea-inverse-formula',annotation.formula));
 section.append(el('p','small','노란색: 남은 Q/C에서 실제 확인된 인용 근거. 식의 타당성은 사람이 확인합니다.'));
 const evidence=data.display?.resolved_evidence||[];
 for(const [field,title] of [['question','질문 · Q'],['context','삭제 후 본문 · C']]){section.append(el('h3','',title));const body=el('div','prose ea-inverse-observation');appendInverseEvidence(body,data.qc[field],evidence.filter(p=>p.field===field));section.append(body);}
 if(data.display?.status==='WARNING')section.append(el('p','small','일부 인용은 위치를 확인하지 못해 강조하지 않았습니다. LLM 원판정은 보존했습니다.'));
 jsonBox(section,'LLM 역산 원판정',record);if(data.display)jsonBox(section,'표시 좌표 검사',data.display);
}
function renderSavedAudit(parent,report,title){
 const section=el('section','box semantic-audit');section.append(el('h2','',title));parent.append(section);
 if(!report){section.append(el('p','small','저장된 검사 결과가 없습니다. 미실행·실패 여부는 아래 결과 파일에서 확인해 주세요.'));return;}
 section.append(badge(report.status),el('p','small','저장된 자동 검사 결과입니다. 사람 판정과 역산·우회 검증 완료를 뜻하지 않습니다.'));
 if(report.reason)section.append(el('p',report.status==='FAIL'?'banner':'small',report.reason));
 const table=el('table','events'),head=el('tr');for(const title of ['검사 항목','판정','이유·원문 근거'])head.append(el('th','',title));table.append(head);
 for(const finding of report.findings||[]){const tr=el('tr'),reason=el('td','',finding.reason||'—');for(const item of finding.evidence||[])reason.append(el('blockquote','prose',(humanLabels[item.field]||item.field)+' · '+item.quote));tr.append(el('td','',humanValues[finding.criterion]||finding.criterion),el('td',finding.judgment==='FAIL'?'bad':'',humanValues[finding.judgment]||finding.judgment),reason);table.append(tr);}
 section.append(table);jsonBox(section,'검사 원기록',report);
}
