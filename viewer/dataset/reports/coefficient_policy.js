// Read saved local programs and choices; no execute or model-call controls.
function renderCoefficientPolicy(report){
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();$('count').textContent=report.summary.records+'개 로컬 계획 · QI04';
 for(const [key,label] of [['records','계획'],['original_cases','실제 원문'],['seeds','seed'],['model_calls','모델 호출']]){
  const box=el('div','metric');box.append(el('span','small',label),el('strong','',String(report.summary[key])));$('metrics').append(box);
 }
 const target=$('detail'),header=el('section','panel');header.append(el('h2','','QI04 opt-in 계수 · 대상순서 유지'));
 header.append(el('p','','legacy 기본 보존. 지원 단위·명시된 질문 정밀도에서 최대2개 계수만 검사합니다. 실제 생성 문장·frozen624 재생성·API 호출은 없습니다.'));
 const limits=el('details');limits.append(el('summary','','범위·보류'));limits.append(el('pre','',report.limitations.join('\n')));header.append(limits);
 for(const ref of report.references){const a=el('a','',ref.path.split('/').at(-1)+' ');a.href='/api/quality-source?name='+encodeURIComponent(report.run_id)+'&path='+encodeURIComponent(ref.path);a.target='_blank';a.rel='noopener';a.title=ref.path+'\nSHA256 '+ref.sha256;header.append(a);}
 target.append(header);const panel=el('div','panel');panel.style.overflowX='auto';const table=el('table');table.style.whiteSpace='pre-line';const head=el('tr');
 for(const label of ['실제 fixture / seed','대상 / 계수','고정 정밀도 / 계산','선택·거절 / SHA256','program·graph'])head.append(el('th','',label));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody'),query=$('search').value.trim().toLowerCase();
 for(const r of report.records){if(query&&!JSON.stringify(r).toLowerCase().includes(query))continue;
  const row=el('tr');row.append(el('td','',r.id),el('td','',r.target+' × '+r.selection.selected_factor),el('td','',r.exact_value+'\n'+r.execution.engine),el('td','',JSON.stringify(r.selection,null,2)));
  const cell=el('td'),details=el('details');details.append(el('summary','','저장 프로그램·그래프'));details.append(el('pre','',JSON.stringify({program:r.program,graph:r.graph,intent:r.intent},null,2)));cell.append(details);row.append(cell);body.append(row);
 }
 table.append(body);panel.append(table);target.append(panel);
}
