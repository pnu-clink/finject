function renderRawExchange(parent,call){
 const groups=el('div','llm-groups');
 for(const [title,path,text] of [
  ['Request · 실제 전송 프롬프트 원문',(call.requestPath||(call.dir||'')+'01-input.json')+' · prompt',call.cli?.prompt??call.model?.prompt],
  ['Response · 실제 모델 응답 원문',(call.responsePath||(call.dir||'')+'02-raw-response.json')+' · text',call.raw?.text]
 ]){
  const pane=el('section','llm-group');pane.append(el('h3','',title),el('p','small llm-path',path));
  if(title.startsWith('Request')&&call.feedbackRow)renderCallFeedback(pane,call.feedbackRow,call);
  if(typeof text==='string'){
   const status=el('span','small');status.setAttribute('role','status');
   pane.append(button('원문 복사',async()=>{try{await copyJsonText(text,pane);status.textContent='복사 완료';}catch(error){status.textContent=error.message;}}),status);
   if(title.startsWith('Response')){pane.append(jsonViewer(text,title));groups.append(pane);continue;}
   const pre=el('pre','json-scroll',text);pre.style.whiteSpace='pre-wrap';pre.style.overflowWrap='anywhere';pre.tabIndex=0;pre.setAttribute('aria-label',title);pane.append(pre);
  }else pane.append(el('p','banner','저장된 원문 기록이 없습니다.'));
  groups.append(pane);
 }
 parent.append(groups);
}
