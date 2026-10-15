// Actual saved requests/responses only; no invocation actions.
function renderQualityApiCheck(report){
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();$('count').textContent=report.summary.records+'건 · Luna low 실제 API';
 for(const [key,label] of [['generation_requests','실제 생성 호출'],['raw_responses','원응답'],['audit_pass','감사 PASS'],['ea_counterexamples_blocked','EA 반례 차단'],['automatic_retries','자동재시도'],['estimated_cost_usd','추정 USD']]){
  const box=el('div','metric');box.append(el('span','small',label),el('strong','',String(report.summary[key])));$('metrics').append(box);
 }
 const target=$('detail'),header=el('section','panel');header.append(el('h2','','Luna low 정규 감사 + 기존 EA local gate'));
 const model=report.model||report.records?.[0]?.usage?.model||'모델은 저장된 요청 파일에서 확인',effort=report.effort||'low';
 header.append(el('p','',model+' / '+effort+' · 4건 순차 · 감사 PASS와 최종 gate를 분리합니다. EA 복원반례는 LLM PASS여도 FAIL입니다. 가격 snapshot 추정이며 전체624 품질이나 Qwen baseline이 아닙니다.'));target.append(header);
 const table=el('table');table.style.whiteSpace='pre-line';const head=el('tr');for(const name of ['문항','감사 / 결합 상태','EA gate / 이유','wire / 토큰·비용','실제 prompt·schema·raw·결과'])head.append(el('th','',name));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody');
 const query=$('search').value.trim().toLowerCase();for(const r of report.records){if(query&&!JSON.stringify(r).toLowerCase().includes(query))continue;
  const row=el('tr');row.append(el('td','',r.id),el('td','',r.audit_status+' / '+r.combined_status),el('td','',(r.recovery_status||'EA 아님')+'\n'+(r.reason||'')),el('td','',(r.wire_luna_low_verified?'Luna low 확인':'미확인')+'\n'+JSON.stringify(r.usage?.tokens)+'\nUSD '+r.usage?.estimated_cost));
  const cell=el('td');for(const [key,ref] of Object.entries(r.artifacts||{})){const a=el('a','',key+' ');a.href='/api/quality-source?name='+encodeURIComponent(report.run_id)+'&path='+encodeURIComponent(ref.path);a.target='_blank';a.rel='noopener';a.title=ref.path+'\nSHA256 '+ref.sha256;cell.append(a);}row.append(cell);body.append(row);
 }
 table.append(body);const panel=el('div','panel');panel.style.overflowX='auto';panel.append(table);target.append(panel);
}
