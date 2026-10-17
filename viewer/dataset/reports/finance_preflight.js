function renderFinancePreflight(report){
 document.querySelector('.filter-panel').hidden=true;
 $('metrics').replaceChildren();$('rows').replaceChildren();$('detail').replaceChildren();
 $('count').textContent=report.summary.selected+'건 · 입력 준비 완료 · LLM 미실행';
 const root=$('detail'),head=el('section','panel'),totals=report.summary,number=value=>Number(value).toLocaleString(globalThis.FinarchI18n?.language === 'ko' ? 'ko-KR' : 'en-US');
 head.append(el('h2','','FinanceReasoning 전체 Preparation 실행 전 정리'),el('p','',`${number(totals.total)}건 중 본문 없음 ${number(totals.empty_context)}건, boolean 정답 ${number(totals.boolean_answer)}건, Q·C 중복 ${number(totals.duplicate_qc)}건을 제외했습니다. 최종 ${number(totals.selected)}건입니다.`),el('p','small','원천 파일 보존 · 기존 LLM 응답 재사용 없음 · 새 API 호출 0회'));
 root.append(head);
 function table(parent,headers,rows){const t=el('table','events'),h=el('tr');for(const x of headers)h.append(el('th','',x));const th=el('thead');th.append(h);t.append(th);const b=el('tbody');for(const row of rows){const tr=el('tr');for(const x of row)tr.append(el('td','',x));b.append(tr);}t.append(b);parent.append(t);}
 const counts=el('section','panel');counts.append(el('h3','','최종 입력'));
 table(counts,['원천','전체','본문 없음','boolean','중복','최종'],Object.entries(report.counts).map(([n,r])=>[n,r.total,r.empty_context,r.boolean_answer,r.duplicate_qc,r.selected]));root.append(counts);
 const dup=el('section','panel');dup.append(el('h3','','Q·C 완전 중복 '+number(totals.duplicate_qc)+'건 제거'),el('p','small','아래 ID는 원본 ID입니다. 질문과 본문이 같고 정답도 같은 쌍에서 먼저 나온 문항을 남겼습니다.'));
 table(dup,['남긴 원본','제외한 원본','정답 일치'],report.exclusions.filter(r=>r.reason==='duplicate_qc').map(r=>[r.kept_raw_id,r.raw_id,r.same_answer?'같음':'다름']));root.append(dup);
 const syntax=el('section','panel');syntax.append(el('h3','','원본 Python 구문 조사'),el('p','','7종 · 중복 제외 '+report.syntax.unique_cases_with_patterns+'건. 새 POT의 실패 건수가 아닙니다. 원본 코드를 실행하지 않았습니다.'));
 for(const [key,count] of Object.entries(report.syntax.pattern_counts)){const d=el('details'),s=el('summary','',report.syntax_labels[key]+' · '+count+'건');d.append(s);const cases=report.syntax.cases.filter(r=>r.patterns.includes(key));table(d,['실행 ID','원본 ID','관련 호출'],cases.map(r=>[r.id,r.raw_id,r.unsupported_numeric_calls.join(', ')]));syntax.append(d);}root.append(syntax);
 const schedule=el('section','panel');schedule.append(el('h3','','동시 처리와 재개'),el('p','','API 최대 200건 고정 · CPU에 따른 증가 없음 · 같은 run은 단일 스케줄러 잠금'),el('p','','미완료 문항 ID → 이전 산출물 보관 → 동일 번호의 01-source부터 새 실행. 완료된 다른 문항은 유지합니다.'),el('p','small','200개 동시 worker / 총 250건의 로컬 파일·공통 로그 검사 통과. 실제 API 부하 검사는 아닙니다.'),el('pre','',report.input_directory));root.append(schedule);
}
