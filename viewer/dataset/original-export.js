// Reuse the production renderer with a bounded cache of embedded final cases.
async function showOriginalExport(){
 const run=DATA.batch?.name;
 if(!run)return;
 const view={lang:globalThis.FinarchI18n?.language||'en',case:rows.find(r=>r.id===selected)?.sample.id,
  variant:window.preparationVariant||null,preparationStage:window.preparationStage,generationStage:window.generationStage};
 const {body}=showSchemaDialog('원본 Export',run+'의 최종 통과 결과를 기존 제작 뷰어 형태로 내보냅니다. 선택 차수·화면 필터와 무관하며 실패·미완료와 과거 차수의 상세 이력은 제외합니다.');
 const status=el('p','','Python·수식·그래프와 최종 단계 자료를 모으고 있습니다…');body.append(status);
 try{
  const response=await fetch('/api/original-export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run,view})});
  const html=await response.text();
  if(!response.ok){
   let message;try{message=JSON.parse(html).error;}catch{}
   throw Error(message||`원본 Export 요청 실패 (HTTP ${response.status}). 데이터셋 뷰어 서버를 새 코드로 재시작하고 화면을 새로고침해 주세요.`);
  }
  if(!response.headers.get('Content-Type')?.startsWith('text/html')||!html.includes('window.FINARCH_ORIGINAL=true;'))throw Error('원본 HTML 응답을 받지 못했습니다. 데이터셋 뷰어 서버와 실행 기록을 확인해 주세요.');
  evaluationDownload(run+'-원본.html',html,'text/html;charset=utf-8');
  status.textContent='HTML 다운로드를 시작했습니다. 이 파일 하나로 원본 뷰어를 열 수 있습니다.';
 }catch(error){status.textContent=error.message;}
}
const originalCache=new Map();let originalSequence=0,originalLoading=null;
async function originalLoadCase(caseName){
 const entry=DATA.original?.cases.find(x=>x.case===caseName);
 if(!entry||originalLoading===caseName)return;
 const sequence=++originalSequence;originalLoading=caseName;
 $('batch-status').textContent=caseName+' · HTML 내장 자료를 읽고 있습니다…';
 try{
  let detail=originalCache.get(caseName);
  if(!detail){
   if(typeof DecompressionStream==='undefined')throw Error('압축 해제를 지원하는 최신 Chrome, Edge 또는 Safari에서 열어 주세요.');
   const compressed=Uint8Array.from(atob($(entry.blob).textContent),c=>c.charCodeAt(0));
   const raw=await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
   detail=JSON.parse(raw);
  }
  if(sequence!==originalSequence)return;
  originalCache.delete(caseName);originalCache.set(caseName,detail);
  while(originalCache.size>2)originalCache.delete(originalCache.keys().next().value);
  DATA.runs=originalSummaries.map(run=>run.case_path===detail.case_path?detail:run);
  loadRows();selected=rows.find(row=>row.sample.id===caseName)?.id;
  if(window.preparationVariant&&!entry.variants.includes(window.preparationVariant))window.preparationVariant=null;
  originalLoading=null;render();
  $('batch-status').textContent=DATA.batch.name+' · '+caseName+' · 최종 결과 / HTML 내장 자료';
 }catch(error){if(sequence!==originalSequence)return;originalLoading=null;$('batch-status').textContent=error.message;}
}
let originalSummaries=[];
document.addEventListener('DOMContentLoaded',()=>{
 if(!DATA.original){if(DATA.live)document.querySelector('header').append(button('원본 Export',showOriginalExport));return;}
 const pkg=DATA.original,initial=pkg.initial_view||{};originalSummaries=DATA.runs;
 document.title=pkg.run+' · 원본 뷰어';
 if(initial.lang)globalThis.FinarchI18n?.setLanguage(initial.lang,{persist:false});
 window.preparationVariant=initial.variant||null;window.preparationStage=initial.preparationStage;window.generationStage=initial.generationStage;
 window.loadDetailCase=originalLoadCase;
 // Server-only actions cannot modify production from a portable result snapshot.
 for(const control of document.querySelectorAll('header a,#live-log-header,#live-log')){control.hidden=true;control.style.display='none';}
 $('connection-help').hidden=true;$('batch-controls').style.display='block';
 const select=$('batch-select');select.replaceChildren();const option=el('option','',pkg.run);option.value=pkg.run;select.append(option);select.disabled=true;
 const round=$('round-select');round.replaceChildren();const r=el('option','',pkg.round||'최종 결과');r.value=pkg.round||'';round.append(r);round.disabled=true;
 $('batch-info').replaceChildren(el('pre','',DATA.batch.readme||'최종 결과 자료'));
 const note=el('p','small',`원본 Export · 최종 Preparation ${pkg.cases.length}문항 · 실패·미완료 결과와 상세 재시도 이력 제외 · 서버 연결 없이 열람`);
 note.style.cssText='color:white;margin:0';document.querySelector('header').append(note);
 // All navigation stays within this snapshot, including case links in saved summaries.
 document.addEventListener('click',event=>{
  const link=event.target.closest?.('a[href]');if(!link)return;
  const url=new URL(link.href,location.href),caseName=url.searchParams.get('case');
  if(caseName&&pkg.cases.some(x=>x.case===caseName)){event.preventDefault();originalLoadCase(caseName);}
 });
 selected=rows.find(row=>row.sample.id===initial.case)?.id||rows[0]?.id;
 render();
});
