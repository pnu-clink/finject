function jsonContextDisplayCell(text, escaped){
 if(!escaped)return text;
 return text.replace(/<br data-cr>/g,'\r').replace(/<br>/g,'\n')
  .replace(/\\([\\|])/g,'$1').replace(/&(amp|lt|gt);/g,(_,name)=>({amp:'&',lt:'<',gt:'>'}[name]));
}

function renderJsonContextAdapter(report){
 document.querySelector('.filter-panel').hidden=true;
 $('metrics').replaceChildren();$('rows').replaceChildren();$('detail').replaceChildren();
 const query=$('search').value.trim().toLowerCase(),summary=report.summary;
 const visible=report.records.filter(r=>!query||[r.raw_id,r.question,r.original_context].join(' ').toLowerCase().includes(query));
 $('count').textContent=visible.length+' / '+summary.json_targets+'건 · JSON 표 변환 검사';
 const url=new URL(location.href),chosen=url.searchParams.get('jsonCase')||report.records[0]?.id;
 const current=visible.find(r=>r.id===chosen)||visible[0];
 for(const row of visible){
  $('rows').append(button(row.id+' · '+row.status,()=>{
   const next=new URL(location.href);next.searchParams.set('jsonCase',row.id);
   history.replaceState(null,'',next);renderJsonContextAdapter(report);
  },'row'+(row===current?' selected':'')+(row.status==='FAIL'?' row-error':'')));
 }
 const root=$('detail'),header=el('section','panel');
 header.append(el('h2','','JSON 본문 → 표 · 실제 원천 전체 검사'),
  el('p','',summary.json_targets+'건 중 변환 통과 '+summary.passed+'건 · 실패 '+summary.failed+'건 · API 호출 0회'),
  el('p','small','값·자료형·원문 위치·입력 스키마의 검사입니다. 풀이 정답이나 의미 타당성의 PASS가 아닙니다. 원천과 기존 실행 결과는 보존합니다.'),
  el('p','small','원천 '+summary.source_total+'건 · 빈 JSON 제외 '+summary.empty_json_context+'건 · 그 외 본문 '+summary.non_json_context+'건'));
 root.append(header);
 if(!current){root.append(el('p','','검색 조건에 맞는 문항이 없습니다.'));return;}
 const section=el('section','panel');
 section.append(el('h3','',current.id+' · '+current.status),box('질문 · Q',current.question),
  el('p','small',current.source_file+' · 원천 배열 위치 '+current.source_index));
 if(current.status!=='PASS'){section.append(box('변환 오류',current.reason));root.append(section);return;}
 const sample=current.sample,check=current.check;
 section.append(el('p','',check.tables+'개 표 · 원본 JSON 값 '+check.value_cells+'개 · '+check.checks.length+'종 검사 통과'));
 const cols=el('div','cols'),before=el('section','box'),after=el('section','box');
 before.append(el('h4','','원본 JSON · 원문 그대로'));
 const original=el('pre','',current.original_context);
 original.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;max-height:75vh;overflow:auto';
 before.append(original);after.append(el('h4','','변환된 표'));
 const blocks=[
  ...sample.source_content.paragraphs.map(p=>({position:p.context_span[0],paragraph:p})),
  ...sample.source_content.tables.map(t=>({position:Math.min(...t.cells.map(c=>c.context_span[0])),table:t}))
 ].sort((a,b)=>a.position-b.position);
 for(const block of blocks){
  if(block.paragraph){after.append(el('p','',jsonContextDisplayCell(block.paragraph.text,block.paragraph.json_source?.markdown_escaped)));continue;}
  const saved=block.table,wrapper=el('div',''),table=el('table','events');wrapper.style.overflowX='auto';
  saved.rows.forEach((row,i)=>{
   const tr=el('tr');
   row.forEach((text,j)=>{
    const source=saved.cells.find(c=>c.row===i&&c.column===j)?.json_source;
    tr.append(el(i===0?'th':'td','',jsonContextDisplayCell(text,source?.markdown_escaped)));
   });table.append(tr);
  });
  wrapper.append(table);after.append(wrapper);
 }
 cols.append(before,after);section.append(cols);
 const detail=el('details','box');detail.append(el('summary','','각 칸의 원문 위치·자료형'));
 const table=el('table','events'),head=el('tr');
 ['표 / 행 / 열','표시 내용','자료형','JSON 위치','원문 토큰 범위'].forEach(t=>head.append(el('th','',t)));table.append(head);
 for(const saved of sample.source_content.tables)for(const cell of saved.cells){
  const info=cell.json_source;if(!info)continue;const tr=el('tr');
  [saved.id+' / '+cell.row+' / '+cell.column,jsonContextDisplayCell(cell.text,info.markdown_escaped),
   info.value_type,info.pointer,info.source_span.join('–')].forEach(t=>tr.append(el('td','',t)));
  table.append(tr);
 }
 detail.append(table);section.append(detail);
 jsonBox(section,'실제 검사 기록',check,'reports/run/'+report.run_id+'/json-context-adapter-check.json');
 const text=el('details','box');text.append(el('summary','','PoT에 전달할 본문 문자열'),el('pre','',sample.context));section.append(text);
 root.append(section);
}
