// Researcher private provenance view, never a model input payload.
function renderOriginalBaseline(report){
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();
 $('count').textContent=report.summary.originals+'개 원문 · baseline 준비 / 실행 보류';
 for(const [key,label] of [['originals','원문'],['variants','연결 변형'],['prepared','준비 완료'],['not_prepared','미완료'],['baseline_calls','baseline 호출'],['semantic_reviewed','의미 검토']]){
  const box=el('div','metric');box.append(el('span','small',label),el('strong','',String(report.summary[key])));$('metrics').append(box);
 }
 const target=$('detail'),header=el('section','panel');header.append(el('h2','','QI02 원문 baseline 입력 준비'));
 header.append(el('p','','연구자용 비공개 출처 화면입니다. public/dataset.json 및 public/requests에는 원문 Q/C만 담습니다. Qwen baseline은 실행하지 않았고, Luna-low 품질 검사는 이를 대체하지 않습니다.'));
 header.append(el('p','',report.status+' · FinanceReasoning '+report.summary.FinanceReasoning+' / TAT-QA '+report.summary.TAT_QA));
 header.append(el('p','',report.public_manifest+' · '+report.requests_directory+' · private/originals.json'));
 target.append(header);const panel=el('div','panel');panel.style.overflowX='auto';const table=el('table');table.style.whiteSpace='pre-line';const head=el('tr');
 for(const label of ['원문 / 차수','준비 / 의미 검토','파생 variant','private reference','근거 / 미완료 이유'])head.append(el('th','',label));
 const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody'),query=$('search').value.trim().toLowerCase();
 for(const r of report.records){
  if(query&&!JSON.stringify(r).toLowerCase().includes(query))continue;
  const row=el('tr');row.append(el('td','',r.id+' / '+r.approved_round+'\n'+r.source_dataset),el('td','',r.status+'\n'+r.semantic_review),el('td','',r.variants.join('\n')),el('td','',JSON.stringify(r.reference)));
  const cell=el('td');for(const key of ['working_input','source','request_template','approved_inputs']){
   const ref=r.references[key];if(!ref)continue;const a=el('a','',key+' ');a.href='/api/quality-source?name='+encodeURIComponent(report.run_id)+'&path='+encodeURIComponent(ref.path);a.target='_blank';a.rel='noopener';a.title=ref.path+'\nSHA256 '+ref.sha256;cell.append(a);
  }
  cell.append(el('p','small',r.skip_reasons.join('; ')||'hash·parent·차수·파생 Q/C 연결 확인'));row.append(cell);body.append(row);
 }
 table.append(body);panel.append(table);target.append(panel);
}
