// Display stored dataset survey results without experiment design documents.
let datasetSurveyDocument = '';

function isDatasetSurvey(batch){
 return batch?.summary?.kind==='DATASET_SURVEY';
}

// Render the survey's limited Markdown vocabulary using text nodes only.
function surveyInline(parent,text){
 const tokens=/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`/g;
 let offset=0;
 for(const match of text.matchAll(tokens)){
  parent.append(document.createTextNode(text.slice(offset,match.index)));
  const node=el(match[2]?'a':match[3]?'strong':'code','',match[1]||match[3]||match[4]);
  if(match[2]){node.href=match[2];node.target='_blank';node.rel='noopener noreferrer';}
  parent.append(node);offset=match.index+match[0].length;
 }
 parent.append(document.createTextNode(text.slice(offset)));
}

function renderSurveyMarkdown(text){
 const content=el('div','survey-document');content.style.cssText='line-height:1.8;overflow-wrap:anywhere';
 const lines=text.split('\n');let list=null;
 for(let index=0;index<lines.length;index++){
  const line=lines[index].trim();if(!line){list=null;continue;}
  if(line.startsWith('|')&&/^\|[\s:|\-]+\|$/.test((lines[index+1]||'').trim())){
   const wrap=el('div');wrap.style.overflowX='auto';const table=el('table');table.style.cssText='min-width:780px;width:100%;font-size:14px';
   const addRow=(raw,header)=>{const row=el('tr');for(const cell of raw.split('|').slice(1,-1)){const item=el(header?'th':'td');item.style.cssText='text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #dde5e7';surveyInline(item,cell.trim());row.append(item)}table.append(row)};
   addRow(line,true);index+=2;while(index<lines.length&&lines[index].trim().startsWith('|'))addRow(lines[index++].trim(),false);index--;wrap.append(table);content.append(wrap);list=null;continue;
  }
  const heading=line.match(/^(#{1,4})\s+(.+)$/),bullet=line.match(/^(-|\d+\.)\s+(.+)$/);
  if(heading){const node=el('h'+Math.min(4,heading[1].length+1));surveyInline(node,heading[2]);content.append(node);list=null;continue;}
  if(bullet){const tag=bullet[1]==='-'?'ul':'ol';if(!list||list.tagName.toLowerCase()!==tag){list=el(tag);content.append(list)}const item=el('li');surveyInline(item,bullet[2]);list.append(item);continue;}
  list=null;const paragraph=el('p');surveyInline(paragraph,line);content.append(paragraph);
 }
 return content;
}

function datasetSurveyView(active){
 document.body.classList.toggle('dataset-survey',active);
 const title=document.querySelector('aside .sticky > h2');
 if(title)title.textContent=active?'조사 문서':'검토할 문제';
}

function renderDatasetSurvey(batch){
 const parts=(batch.readme||'').split(/\n---\n\n## ([^\n]+)\n\n/);
 const documents=[];
 for(let index=1;index<parts.length;index+=2)documents.push({name:parts[index],text:parts[index+1]||''});
 if(!documents.some(document=>document.name===datasetSurveyDocument))datasetSurveyDocument=documents[0]?.name||'';
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();
 $('count').textContent=documents.length+'개 문서 · 원본 데이터셋 조사';
 $('notice').textContent='문서를 선택하면 저장된 조사 결과를 읽으실 수 있습니다. 공개 규모 확인과 정답 품질 검증은 구분합니다.';
 for(const document of documents){
  const item=button(document.name,()=>{datasetSurveyDocument=document.name;renderDatasetSurvey(batch)},'row'+(document.name===datasetSurveyDocument?' selected':''));
  item.style.overflowWrap='anywhere';item.setAttribute('aria-pressed',String(document.name===datasetSurveyDocument));$('rows').append(item);
 }
 const labels=[['candidates','조사 후보'],['count_verified','파일·API 수량 확인'],['documents','조사 문서']];
 for(const [key,label] of labels){
  const metric=el('div','metric');metric.append(el('span','small',label),el('strong','',String(batch.summary?.[key]??'기록 없음')));$('metrics').append(metric);
 }
 const intro=el('section','panel');intro.append(el('h2','',batch.summary.title||'금융 QA 데이터셋 조사'),el('p','',`${batch.summary.window_start}–${batch.summary.as_of} · 공개 1,000건 이상 선호, 최소 500건`));
 intro.append(el('p','small','표시 자료: 선택한 reports/run의 README · 수량·출처 기록: inspection.json / research-log.jsonl'));
 $('detail').append(intro);
 const selectedDocument=documents.find(document=>document.name===datasetSurveyDocument);
 const content=el('section','panel');content.append(el('h2','',selectedDocument?.name||'저장된 안내'));
 const text=selectedDocument?.text||batch.readme||'저장된 문서가 없습니다.';
 content.append(renderSurveyMarkdown(text));
 {const raw=el('details');raw.append(el('summary','','저장 원문 보기'),el('pre','dataset-survey-text',text));content.append(raw)}
 $('detail').append(content);
}
