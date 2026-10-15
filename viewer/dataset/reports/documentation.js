// Read current pipeline documents and preserve archived source identity.
let pipelineDocumentPath='',pipelineArchiveDocument=null,pipelineDocumentRequest=0;
let pipelineMermaidLoader=null,pipelineDiagramNumber=0;
function pipelineDiagram(source,doc,batch){
 const wrap=el('div');wrap.style.cssText='overflow:auto;padding:12px 0';
 const picture=el('div','pipeline-mermaid',source);picture.id='pipeline-flow-'+(++pipelineDiagramNumber);wrap.append(picture);
 if(!pipelineMermaidLoader)pipelineMermaidLoader=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/documentation-mermaid.js';script.onload=()=>{window.mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral'});resolve(window.mermaid)};script.onerror=()=>reject(Error('로컬 흐름도 라이브러리를 읽지 못했습니다.'));document.head.append(script)});
 pipelineMermaidLoader.then(async renderer=>{if(picture.isConnected){try{await renderer.run({nodes:[picture]});for(const link of picture.querySelectorAll('a')){const target=link.getAttribute('href')||link.getAttribute('xlink:href');if(!target)continue;const resolved=pipelineDocumentLink(target,doc,batch);if(resolved.path){link.setAttribute('href','#');link.removeAttribute('xlink:href');link.onclick=event=>{event.preventDefault();openPipelineDocument(batch,resolved.path,resolved.fragment)}}else if(!/^https?:/.test(target)){link.removeAttribute('href');link.removeAttribute('xlink:href')}}}catch(error){picture.replaceChildren(el('p','pipeline-diagram-error','흐름도 표시 오류: 아래 원문을 확인해 주세요.'));}}}).catch(error=>{picture.replaceChildren(el('p','pipeline-diagram-error',error.message));});
 return wrap;
}
function pipelineDocumentLink(target,doc,batch){
 const url=new URL(target,'http://documentation.local/'+doc.original);
 const originalPath=decodeURIComponent(url.pathname.slice(1));
 const path=batch.documentation.aliases?.[originalPath]||originalPath;
 const catalog=batch.documentation.catalog;
 return {path:(catalog.find(item=>item.path===path)||catalog.find(item=>item.original===path))?.path,fragment:decodeURIComponent(url.hash.slice(1))};
}
function pipelineInline(parent,value,doc,batch){
 const tokens=/\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`/g;let offset=0;
 for(const match of value.matchAll(tokens)){
  parent.append(document.createTextNode(value.slice(offset,match.index)));
  if(match[2]){
   if(/^https?:\/\//.test(match[2])){const link=el('a','',match[1]);link.href=match[2];link.target='_blank';link.rel='noopener noreferrer';parent.append(link);}
   else{const resolved=pipelineDocumentLink(match[2],doc,batch);if(resolved.path){const link=el('a','',match[1]);link.href='#';link.onclick=event=>{event.preventDefault();openPipelineDocument(batch,resolved.path,resolved.fragment);};parent.append(link);}else{const label=el('span','',match[1]);label.title='로컬 파일: '+match[2];parent.append(label,el('code','', ' '+match[2]));}}
  }else parent.append(el(match[3]?'strong':'code','',match[3]||match[4]));
  offset=match.index+match[0].length;
 }
 parent.append(document.createTextNode(value.slice(offset)));
}
function pipelineMarkdown(doc,batch){
 const content=el('div');content.style.cssText='line-height:1.8;overflow-wrap:anywhere';
 const lines=doc.content.split('\n');let list=null;
 for(let index=0;index<lines.length;index++){
  const raw=lines[index],line=raw.trim();if(!line){list=null;continue;}
  if(line.startsWith('```')){const language=line.slice(3);let code=[];while(++index<lines.length&&!lines[index].startsWith('```'))code.push(lines[index]);const pre=el('pre','',code.join('\n'));pre.style.cssText='white-space:pre;overflow:auto;background:#f4f6f8;padding:16px;font-size:13px';if(language==='mermaid'){content.append(pipelineDiagram(code.join('\n'),doc,batch));const detail=el('details');detail.append(el('summary','','단계 흐름도 · Mermaid 원문'),pre);content.append(detail);}else content.append(pre);list=null;continue;}
  if(line.startsWith('|')&&/^\|[\s:|\-]+\|$/.test((lines[index+1]||'').trim())){
   const wrap=el('div');wrap.style.overflowX='auto';const table=el('table');table.style.cssText='min-width:640px;width:100%;font-size:14px';
   const row=(text,head)=>{const tr=el('tr');for(const cell of text.split('|').slice(1,-1)){const td=el(head?'th':'td');td.style.cssText='padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #dce4e6';pipelineInline(td,cell.trim(),doc,batch);tr.append(td)}table.append(tr)};
   row(line,true);index+=2;while(index<lines.length&&lines[index].trim().startsWith('|'))row(lines[index++].trim(),false);index--;wrap.append(table);content.append(wrap);list=null;continue;
  }
  const heading=line.match(/^(#{1,6})\s+(.+)$/),bullet=line.match(/^(-|\d+\.)\s+(.+)$/);
  if(heading){const node=el('h'+Math.min(5,heading[1].length+1));node.id='doc-'+heading[2].toLowerCase().replace(/[^\p{L}\p{N}_\- ]/gu,'').replaceAll(' ','-');pipelineInline(node,heading[2],doc,batch);content.append(node);list=null;continue;}
  if(bullet){const tag=bullet[1]==='-'?'ul':'ol';if(!list||list.tagName.toLowerCase()!==tag){list=el(tag);content.append(list)}const item=el('li');pipelineInline(item,bullet[2],doc,batch);list.append(item);continue;}
  list=null;const paragraph=el('p');pipelineInline(paragraph,line,doc,batch);content.append(paragraph);
 }
 return content;
}
async function openPipelineDocument(batch,path,fragment=''){
 path=batch.documentation.aliases?.[path]||path;
 const request=++pipelineDocumentRequest;pipelineDocumentPath=path;pipelineArchiveDocument=null;
 try{
  if(!batch.documentation.documents.some(doc=>doc.path===path)){
   const response=await fetch('/api/documentation?run='+encodeURIComponent(batch.name)+'&path='+encodeURIComponent(path));
   if(!response.ok)throw Error('문서 조회 실패: '+response.status);
   const doc=await response.json();if(request!==pipelineDocumentRequest||DATA.batch?.name!==batch.name)return;pipelineArchiveDocument=doc;
  }
  if(request!==pipelineDocumentRequest||DATA.batch?.name!==batch.name)return;
  const url=new URL(location.href);url.searchParams.set('doc',path);history.replaceState(null,'',url);renderPipelineDocumentation(batch);
  if(fragment)document.getElementById('doc-'+fragment)?.scrollIntoView({block:'start'});
 }catch(error){$('notice').textContent=error.message;}
}
function renderPipelineDocumentation(batch){
 datasetSurveyView(true);document.querySelector('aside .sticky > h2').textContent='파이프라인 문서';
 const data=batch.documentation;
 const requestedPath=new URLSearchParams(location.search).get('doc');
 const requested=data.aliases?.[requestedPath]||requestedPath;
 if(!pipelineDocumentPath){
  pipelineDocumentPath=data.documents.some(doc=>doc.path===requested)?requested:(data.entry_document||'docs/01-dataset/README.md');
  if(requested&&data.catalog.some(doc=>doc.path===requested)&&!data.documents.some(doc=>doc.path===requested)){openPipelineDocument(batch,requested);return;}
 }
 const doc=data.documents.find(doc=>doc.path===pipelineDocumentPath)||pipelineArchiveDocument||data.documents[0];
 $('rows').replaceChildren();$('metrics').replaceChildren();$('detail').replaceChildren();
 $('count').textContent=data.documents.length+'개 현행 문서 · 진행 순서';
 $('notice').textContent='전체 → 단계 폴더 → 세부 스텝 순서입니다. 현재 파일을 읽습니다. 코드 정적 확인과 실제 실행 검증을 구별합니다.';
 let previous='';for(const item of data.documents){const group=item.group||'overview';if(group!==previous){$('rows').append(el('h3','',group==='overview'?'전체·공통 기준':group));previous=group;}
  const b=button(item.title,()=>openPipelineDocument(batch,item.path),'row'+(item.path===doc.path?' selected':''));b.style.cssText='white-space:normal;overflow-wrap:anywhere';b.title=item.path;b.setAttribute('aria-pressed',String(item.path===doc.path));$('rows').append(b);}
 const nav=el('section','panel');nav.append(el('h2','',data.title));
 const navigation=data.navigation||[['문서 전체','docs/README.md'],['데이터셋','docs/01-dataset/README.md'],['실험','docs/02-experiments/README.md'],['00 입력','docs/01-dataset/00-input/README.md'],['01 Preparation','docs/01-dataset/01-preparation/README.md'],['02 Generation','docs/01-dataset/02-generation/README.md'],['03 전달 계약','docs/01-dataset/03-release/README.md'],['이관표','archive/20260923-documentation-reorganization/MIGRATION.md']];
 for(const [label,path] of navigation)nav.append(button(label,()=>openPipelineDocument(batch,path)));
 const contractLink=el('a','','응답 schema ↔ prompt 대조 ↗');contractLink.href='/contract';contractLink.target='_blank';contractLink.rel='noopener noreferrer';contractLink.style.cssText='display:inline-block;margin:8px 0;font-weight:700';nav.append(contractLink);
 nav.append(el('p','small',(data.validation?.archive_files===undefined?'':'보관 원본 '+data.validation.archive_files+'개 · ')+'파일/링크 검사 '+(data.validation?.status??'미검사')+' · 문서 읽기 기능의 모델 호출 0회'));
 $('detail').append(nav);
 const panel=el('section','panel');panel.append(el('p','small',doc.path));
 if(doc.archived)panel.append(el('p','', '보관 원본입니다. 이 문서의 현재·완료 표기는 작성 당시 이력이며 현행 기준과 구별합니다.'));
 panel.append(doc.format!=='md'?el('pre','dataset-survey-text',doc.content):pipelineMarkdown(doc,batch));
 const raw=el('details');raw.append(el('summary','','원본 Markdown/JSON · SHA-256 보기'),el('p','small',doc.sha256),el('pre','dataset-survey-text',doc.content));panel.append(raw);$('detail').append(panel);
}
