// Saved multi-axis observations only; no analysis or mutations on GET.
function renderResponseScreen(report){
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();
 $('count').textContent=report.summary.records+'건 · QI06 읽기 전용 예비 선별';
 const target=$('detail'),header=el('section','panel');
 header.append(el('h2','','1차 응답 · 실행 상태와 독립 표현 표지'));
 header.append(el('p','','표현 검출은 의미 판정이 아닙니다. 전체 624건과 완료 응답 분모를 구분합니다. 잘림은 의미 미평가이며, 단위·정밀도·문장 추출이 불명확하면 A/B는 UNRESOLVED입니다.'));
 for(const [key,label] of [['records','전체'],['COMPLETE','완료'],['TRUNCATED','잘림'],['TRANSPORT_ERROR','전송오류'],['SCHEMA_ERROR','스키마오류'],['MISSING','누락'],['conflict_cue','충돌표현'],['reject_cue','유보표현'],['condition_cue','조건표현'],['manual_samples','제한 표본 검토'],['semantic_adjudicated','의미 확정'],['ab_resolved','A/B 확정']]){
  const box=el('div','metric');box.append(el('span','small',label),el('strong','',String(report.summary[key]??0)));$('metrics').append(box);
 }
 for(const [name,ref] of Object.entries(report.related_reports)){const a=el('a','',name+' 보고서 ');a.href='/?run='+encodeURIComponent(ref.path.split('/').at(-2));header.append(a);}
 header.append(el('p','small','원문/reference는 NOT_REVIEWED. QI01 복원 증거가 있는 3건만 변형 INVALID이며 나머지 EA는 UNKNOWN입니다. 조건부·복수 답과 범용 의미 parser는 보류했습니다.'));
 const samples=el('details');samples.append(el('summary','','실제 표본 검토와 제한'));samples.append(el('pre','',JSON.stringify({samples:report.manual_samples,limitations:report.limitations},null,2)));header.append(samples);target.append(header);
 const wrapper=el('div','panel');wrapper.style.overflowX='auto';const table=el('table');table.style.whiteSpace='pre-line';
 const head=el('tr');for(const name of ['문항','실행 / raw 종료','독립 cue / 인용 위치','숫자 추출 / A·B','의미 / 타당성','근거 / 생략 이유'])head.append(el('th','',name));
 const thead=el('thead');thead.append(head);table.append(thead);const tbody=el('tbody'),query=$('search').value.trim().toLowerCase();
 for(const r of report.records){
  if(query&&!JSON.stringify(r).toLowerCase().includes(query))continue;
  const row=el('tr');row.append(el('td','',r.id),el('td','',r.execution+' / '+(r.raw_finish_reason??'없음')+'\n'+r.execution_reason));
  row.append(el('td','',r.cues?Object.entries(r.cues).map(([k,v])=>k+': '+(v.length?v.map(c=>c.quote+' ['+c.start+','+c.end+')').join('; '):'표지 없음')).join('\n'):'NOT_EVALUATED'));
  row.append(el('td','',r.comparison.match+'\nA='+r.comparison.A+' / B='+r.comparison.B+'\n'+JSON.stringify(r.numeric_candidates)));
  row.append(el('td','',r.semantic_status+'\noriginal: '+r.validity.original+'\nperturbation: '+r.validity.perturbation+'\nreference: '+r.validity.reference));
  const cell=el('td');for(const [key,ref] of Object.entries(r.references)){
   const a=el('a','',key+' ');a.href='/api/quality-source?name='+encodeURIComponent(report.run_id)+'&path='+encodeURIComponent(ref.path);a.target='_blank';a.rel='noopener';a.title=ref.path+'\nSHA256 '+ref.sha256;cell.append(a);
  }
  cell.append(el('p','small',r.skip_reasons.join('; ')));const detail=el('details');detail.append(el('summary','','실제 answer'));detail.append(el('pre','',r.answer??'NOT_EVALUATED'));cell.append(detail);row.append(cell);tbody.append(row);
 }
 table.append(tbody);wrapper.append(table);target.append(wrapper);
}
