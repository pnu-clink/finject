// Saved provenance only: no approval, recheck, analysis, or model-call action.
function renderQualityScope(report){
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();
 $('count').textContent=report.summary.records+'건 · 읽기 전용 품질 보고서';
 const target=$('detail'),header=el('section','panel');
 header.append(el('h2','','감사 범위 · 승인 출처 · 독립 검토'));
 header.append(el('p','','세 검증축 PASS와 사용자 지시 일괄 승인은 독립 문항 검토가 아닙니다. 선택한 근거에서 별도 독립 검토 기록을 가져오지 않았다는 뜻이며, 실제 세상에서 검토가 없었다고 단정하지 않습니다. EA 전체 판정과 새 복원 반례를 별도로 표시합니다.'));
 for(const [key,label] of [['records','전체'],['three_audit_axes_pass','3축 모두 PASS'],['bulk_at_user_direction','사용자 지시 일괄 승인'],['independent_not_reviewed','독립 검토 기록 없음'],['ea_full_not_evaluated','EA 전체 미평가'],['qi01_counterexamples_linked','QI01 반례 연결']]){
  const item=el('div','metric');item.append(el('span','small',label),el('strong','',String(report.summary[key]??0)));$('metrics').append(item);
 }
 const query=$('search').value.trim().toLowerCase();
 if(report.related_reports.QI01){const a=el('a','','QI01 원래 검사 결과 열기');a.href='/?run='+encodeURIComponent(report.related_reports.QI01.path.split('/').at(-2));header.append(a);}
 target.append(header);
 const wrapper=el('div','panel');wrapper.style.overflowX='auto';const table=el('table'),head=el('tr');table.style.whiteSpace='pre-line';
 for(const name of ['문항 / 유형','감사 3축·범위','승인 경로','독립 검토','EA 전체 / 제한 복원','근거 / 보류 이유'])head.append(el('th','',name));
 const thead=el('thead');thead.append(head);table.append(thead);const tbody=el('tbody');
 for(const record of report.records){
  if(query&&!JSON.stringify([record.id,record.approval.method,record.bounded_recovery_status]).toLowerCase().includes(query))continue;
  const row=el('tr');row.append(el('td','',record.id));
  row.append(el('td','',record.audit.findings.map(f=>f.criterion+': '+f.judgment).join('\n')+'\n'+record.audit.scope+' · '+record.audit.model+' / '+record.audit.effort));
  row.append(el('td','',record.approval.method+'\n'+(record.approval.reviewer||'출처 미확인')+'\n'+(record.approval.recorded_at||'')));
  row.append(el('td','',record.independent_review.status));
  row.append(el('td','',(record.audit.full_EA_verdict||'해당 기록 없음')+' / '+(record.bounded_recovery_status||'별도 검사 없음')));
  const evidence=el('td');
  for(const [key,label] of [['generation','생성·계획'],['audit','감사'],['audit_raw','원응답'],['audit_profile','당시 프로필'],['decision','승인'],['decision_history','승인 이력'],['bounded_recovery','QI01 복원 근거']]){
   const ref=record.references[key];if(!ref)continue;const a=el('a','',label+' ');
   a.href='/api/quality-source?name='+encodeURIComponent(report.run_id)+'&path='+encodeURIComponent(ref.path);
   a.target='_blank';a.rel='noopener';a.title=ref.path+'\nSHA256 '+ref.sha256;evidence.append(a);
  }
  evidence.append(el('p','small',record.skip_reasons.length?record.skip_reasons.join('; '):'근거 기록 완료 · 독립 의미 판정 아님'));
  row.append(evidence);tbody.append(row);
 }
 table.append(tbody);wrapper.append(table);target.append(wrapper);
}
