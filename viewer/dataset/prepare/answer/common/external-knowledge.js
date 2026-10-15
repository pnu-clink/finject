// Display saved POT requirements; do not infer formulas or alter production records.
function externalKnowledgeModel(row){
 const a=row.run.artifacts||{},path=['03-calculation/05-record-calculation-artifacts/03-program.json','03-calculation/02-prepare-code/03-program.json','02-calculation/02-prepare-code/03-program.json'].find(k=>a[k]);
 const program=a[path]||{},requirements=(program.external_knowledge_requirements||[]).filter(x=>['EXTERNAL_RULE','EXTERNAL_DATA'].includes(x.tag));
 const sources=new Set([...(row.run.preparation_list?.sources||[]),...(program.calculation_input_sources||[])]);
 for(const u of program.source_usage||[])sources.add(u.kind);
 return {program,requirements,tags:['EXTERNAL_RULE','EXTERNAL_DATA'].filter(k=>sources.has(k)),path:path?row.run.path+'/'+(row.run.artifact_aliases?.[path]||path):null};
}
function decorateExternalKnowledge(content,row){
 const model=externalKnowledgeModel(row);if(!model.tags.length)return;
 const info=el('section','box external-knowledge-info');info.setAttribute('aria-label','필요한 외부지식과 수식');info.append(el('h3','','필요한 외부지식 · '+model.tags.join(' / ')));
 if(model.path)info.append(filePathLabel(model.path));
 const triggers=[];
 for(const req of model.requirements){
  const card=el('div','external-knowledge-entry');card.append(el('strong','',req.tag),el('p','',req.definition));
  for(const t of req.triggers||[]){if(!t.quote)continue;triggers.push({...t,tag:req.tag});card.append(el('p','external-trigger-line',(t.origin==='QUESTION'?'Q':'C')+' · '+t.quote));}
  if(req.formula)card.append(el('div','external-formula','외부지식 수식 · '+req.formula));
  if(req.bindings?.length)card.append(el('p','small',req.bindings.map(b=>b.symbol+' = '+b.meaning).join(' / ')));
  if(req.data_requirements?.length)card.append(el('p','','필요한 외부 데이터 · '+req.data_requirements.join(' / ')));
  const source=(model.program.source_usage||[]).find(u=>u.id===req.source_usage_id);
  if(source)card.append(el('p','small','출처 · '+[source.source_title,source.source_url,source.acquisition].filter(Boolean).join(' · ')));
  info.append(card);
 }
 if(!model.requirements.length){
  info.append(el('p','','이 기록에는 외부지식 요구 문구·수식의 구조화 정보가 없습니다. 저장된 설명을 확인하세요.'));
  for(const u of model.program.source_usage||[])if(model.tags.includes(u.kind))info.append(el('p','',u.kind+' · '+(u.description||'')));
 }
 const formula=content.querySelector('.formula-comparison');if(formula)formula.before(info);else content.prepend(info);
 // Highlight only Q/C display containers whose full text equals the displayed source.
 const qc=[row.sample.question,row.sample.context].filter(x=>typeof x==='string');
 for(const area of content.querySelectorAll('.prose')){
  if(!qc.includes(area.textContent))continue;
  const origin=area.textContent===row.sample.question?'QUESTION':'CONTEXT';
  const matching=triggers.filter(t=>t.origin===origin);
  const walker=document.createTreeWalker(area,NodeFilter.SHOW_TEXT),nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
  for(const node of nodes){
   if(node.parentElement.closest('mark'))continue;
   const text=node.textContent,ranges=[];
   for(const t of matching){let i=0;while((i=text.indexOf(t.quote,i))!==-1){ranges.push({start:i,end:i+t.quote.length,tag:t.tag});i+=t.quote.length;}}
   ranges.sort((a,b)=>a.start-b.start||b.end-a.end);let cursor=0;const fragment=document.createDocumentFragment();
   for(const r of ranges){if(r.start<cursor)continue;fragment.append(document.createTextNode(text.slice(cursor,r.start)));const mark=el('mark','external-knowledge-mark',text.slice(r.start,r.end));mark.title=r.tag+' · 필요한 외부지식';fragment.append(mark);cursor=r.end;}
   if(cursor){fragment.append(document.createTextNode(text.slice(cursor)));node.replaceWith(fragment);}
  }
 }
}
