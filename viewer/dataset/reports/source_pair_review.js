// Exact saved pairing and lexical observations; not causal or semantic scoring.
function renderSourcePairReview(report){
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();$('count').textContent=report.summary.records+'개 SOURCE · 동일 case VALUE 짝';
 for(const [key,label] of [['total','전체 SOURCE'],['matched','정확 매칭'],['excluded','제외'],['both_complete','양쪽 완료'],['either_truncated','한쪽 이상 잘림'],['cue_comparable','cue 비교 가능']]){
  const box=el('div','metric');box.append(el('span','small',label),el('strong','',String(report.summary.overall[key])));$('metrics').append(box);
 }
 const target=$('detail'),header=el('section','panel');header.append(el('h2','','QI03 SOURCE1↔VALUE-before / SOURCE2↔VALUE-after'));
 header.append(el('p','','SOURCE1 대 SOURCE2의 직접 비교가 아닙니다. 의미 효과 NOT_EVALUATED · A/B 효과 UNRESOLVED. exact patch를 되돌려 base Q/C와 일치한 완료쌍의 cue만 예비 비교합니다.'));
 for(const k of ['SOURCE1','SOURCE2']){const c=report.summary[k];header.append(el('p','',k+': 전체 '+c.total+' / 정확 매칭 '+c.matched+' / 양쪽 완료 '+c.both_complete+' / 잘림 포함 '+c.either_truncated+' / cue 비교 '+c.cue_comparable));}
 const summary=el('details');summary.append(el('summary','','cue별 base→source 상태 집계'));summary.append(el('pre','',JSON.stringify(report.summary,null,2)));header.append(summary);target.append(header);
 const panel=el('div','panel');panel.style.overflowX='auto';const table=el('table');table.style.whiteSpace='pre-line';const head=el('tr');
 for(const label of ['동일 case 짝','정확 연결 / 제외 이유','A/B 정체성 / 실제 위치','응답 실행 상태 / cue','근거'])head.append(el('th','',label));
 const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody'),query=$('search').value.trim().toLowerCase();
 for(const r of report.records){
  if(query&&!JSON.stringify(r).toLowerCase().includes(query))continue;
  const row=el('tr');row.append(el('td','',r.source_id+'\n↔ '+r.base_id),el('td','',r.match_status+'\n'+r.reasons.join('; ')+'\ninverse='+r.inverse_matches_base));
  row.append(el('td','',JSON.stringify(r.value_identity)+'\n'+r.claim_location.layout+' / offset '+r.claim_location.insertion_offset_in_base+'\n'+(r.claim_location.line_quote??'')));
  row.append(el('td','',JSON.stringify(r.responses,null,2)+'\ncue: '+JSON.stringify(r.cue_comparison)+'\n'+r.semantic_effect+' / '+r.ab_effect));
  const cell=el('td');for(const key of ['dependency','source_generation','base_generation','source_raw','base_raw']){
   const ref=r.references[key];if(!ref)continue;const a=el('a','',key+' ');a.href='/api/quality-source?name='+encodeURIComponent(report.run_id)+'&path='+encodeURIComponent(ref.path);a.target='_blank';a.rel='noopener';a.title=ref.path+'\nSHA256 '+ref.sha256;cell.append(a);
  }
  row.append(cell);body.append(row);
 }
 table.append(body);panel.append(table);target.append(panel);
}
