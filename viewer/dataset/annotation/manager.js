// Select independent dataset comparisons across date folders; preserve imported judgments.
'use strict';
const $=id=>document.getElementById(id);
const annotationTypeFilterKey='finarch-annotation-type-filters-v1';
function initialTypeFilters(){
 try{const values=JSON.parse(sessionStorage.getItem(annotationTypeFilterKey));if(Array.isArray(values)&&values.every(value=>Number.isInteger(value)&&value>=0&&value<7))return new Set(values);}catch{}
 return new Set([0,1,2,3,4,5,6]);
}
const annotationState={view:null,groupId:new URLSearchParams(location.search).get('group'),caseName:null,type:0,typeFilters:initialTypeFilters(),hideSuccess:false,comparisons:[],filter:'ALL',sourceType:'ALL',search:'',included:null,busy:false,notes:new Set(),texts:new Set(),evidence:null,g02:null,evidenceSequence:0,loadSequence:0};
const annotationLabels={APPROVED:'통과',REJECTED:'실패',PENDING:'유보'};
const annotationClasses={APPROVED:'accept',REJECTED:'reject',PENDING:'pending'};
const annotationFlags={FORMAT:['형식 오류','red'],CONTENT:['본문 다름','red'],DISAGREE:['불일치','red'],REJECTED:['실패','red'],PENDING:['유보','yellow'],MISSING:['미입력','gray'],NOTE:['주석','blue']};
const annotationRules={FILL_HEADER_ANNOTATOR:'파일 상단의 평가자 이름 보완',NORMALIZE_LEGACY_EA_LABEL:'현재 EA 유형 label로 보완',NORMALIZE_DECISION:'판정 표기 통일',FILL_EMPTY_COMMENT:'빈 주석 보완',FILL_KNOWN_TYPE_LABEL:'유형 label 보완',COUNT_ACTUAL_RECORDS:'실제 항목 수로 n 보정',REMOVE_TRAILING_COMMAS:'문자열 밖의 마지막 쉼표 제거',REMOVE_UTF8_BOM:'UTF-8 BOM 제거',REMOVE_JSON_FENCE:'JSON 코드 블록 제거'};
function node(tag,className='',text=''){const element=document.createElement(tag);element.className=className;element.textContent=text;return element;}
function action(text,fn,className=''){const element=node('button',className,text);element.type='button';element.onclick=fn;return element;}
function group(){return annotationState.view?.groups.find(value=>value.id===annotationState.groupId)||null;}
function currentCase(){return group()?.cases.find(value=>value.case===annotationState.caseName)||null;}
function flag(value){const [text,cls]=annotationFlags[value];return node('span','flag '+cls,text);}
function percent(value){return value==null?'—':(100*value).toFixed(1)+'%';}
function rowIsSuccessful(row){
 const cells=Object.values(row.cells);
 return cells.length>0&&!row.flags.some(flag=>['FORMAT','CONTENT','MISSING'].includes(flag))&&cells.every(cell=>cell.confirmed&&!cell.missing&&cell.decision==='APPROVED'&&!cell.issues.length);
}
function caseIsSuccessful(item){return item.rows.length===7&&item.rows.every(rowIsSuccessful);}
function isTypeVisible(index,item=currentCase()){return annotationState.typeFilters.has(index)&&!!item?.rows[index]&&(!annotationState.hideSuccess||!rowIsSuccessful(item.rows[index]));}
function visibleTypeIndices(item=currentCase()){return [...annotationState.typeFilters].sort((a,b)=>a-b).filter(index=>isTypeVisible(index,item));}
function updateMetricSelection(){for(const [index,button] of [...$('metrics').children].entries()){const visible=isTypeVisible(index);button.disabled=!visible;button.classList.toggle('selected',visible&&index===annotationState.type);}}
function matchesCase(item,filter=annotationState.filter,search=annotationState.search){
 if(!matchesManagerReview(item))return false;
 if(annotationState.sourceType!=='ALL'&&(item.source_type||'UNKNOWN')!==annotationState.sourceType)return false;
 const terms=search.trim().toLowerCase(),number=terms.replace(/\D/g,'');
 if(terms&&!item.case.toLowerCase().includes(terms)&&!(number&&Number(item.case.replace(/\D/g,''))===Number(number)))return false;
 if(filter==='ALL')return true;
 if(filter==='ALL_SUCCESS')return caseIsSuccessful(item);
 if(filter==='NOT_ALL_SUCCESS')return !caseIsSuccessful(item);
 if(filter==='ERROR')return item.flags.includes('FORMAT')||item.flags.includes('CONTENT');
 if(filter==='FLAGGED')return item.flags.includes('REJECTED')||item.flags.includes('PENDING');
 if(filter==='APPROVED')return item.rows.some(row=>Object.values(row.cells).some(cell=>cell.confirmed&&cell.decision==='APPROVED'&&!cell.issues.length));
 return item.flags.includes(filter);
}
function visibleCases(){return (group()?.cases||[]).filter(item=>matchesCase(item));}
function renderSourceTypes(){
 const active=group(),options=active?.source_types||[],select=$('source-type');select.replaceChildren();
 const all=node('option','','전체 Source type · '+(active?.cases.length||0).toLocaleString());all.value='ALL';select.append(all);
 for(const value of options){const option=node('option','',value.label+' · '+value.count.toLocaleString());option.value=value.value;select.append(option);}
 if(annotationState.sourceType!=='ALL'&&!options.some(value=>value.value===annotationState.sourceType))annotationState.sourceType='ALL';
 select.value=annotationState.sourceType;
}
function keepVisibleCase(){
 const items=visibleCases();if(!items.some(value=>value.case===annotationState.caseName)){annotationState.caseName=(items.find(value=>value.flags.includes('DISAGREE'))||items[0])?.case||null;annotationState.evidence=null;}
}
function status(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
function fileStatus(){const view=annotationState.view,errors=view.files.filter(file=>file.issues.length).length,repairs=view.files.reduce((sum,file)=>sum+file.repairs,0);status(view.path+' · '+view.files.length+'개 파일 · 형식 보완 '+repairs.toLocaleString()+'건'+(errors?' · 오류 파일 '+errors+'개':''),!!errors);}
function setBusy(busy){annotationState.busy=busy;for(const id of ['refresh','import','date','comparison-choice','files','export','review-export'])$(id).disabled=busy;$('export').disabled=busy||!group();$('review-export').disabled=busy||!group();renderManagerEditor();}
async function request(url,body){
 const response=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
 if(!response.ok){let message='파일을 읽지 못했습니다.';try{message=(await response.json()).error||message;}catch{message='파일을 읽지 못했습니다. HTTP '+response.status;}throw Error(message);}
 return response.json();
}
function renderComparisonChoices(){
 const select=$('comparison-choice'),active=group(),choices=[...annotationState.comparisons];
 if(active&&!choices.some(choice=>choice.date===annotationState.view.date&&choice.group===active.id))choices.push({date:annotationState.view.date,group:active.id,dataset_label:active.dataset_label,cases:active.cases.length,reviewers:active.reviewers});
 select.replaceChildren();for(const choice of choices){const option=node('option','',choice.dataset_label+' · '+choice.date+' · '+choice.reviewers.length+'명 / '+choice.cases.toLocaleString()+'문항');option.value=choice.date+':'+choice.group;select.append(option);}
 select.value=active?annotationState.view.date+':'+active.id:'';
 const badge=$('dataset-context');badge.textContent=active?.dataset_label||'비교 자료 선택';badge.dataset.dataset=active?.dataset_label?.startsWith('TAT-QA')?'tatqa':'finance';
}
async function loadCatalog(){try{annotationState.comparisons=(await request('/api/annotation/catalog')).comparisons;renderComparisonChoices();}catch(error){status(error.message,true);}}
function selectComparison(value){
 const choice=annotationState.comparisons.find(item=>item.date+':'+item.group===value);if(!choice)return;
 annotationState.included=null;annotationState.groupId=choice.group;annotationState.caseName=null;annotationState.sourceType='ALL';annotationState.search='';annotationState.evidence=null;annotationState.g02=null;$('search').value='';$('date').value=choice.date;load(true);
}
function applyView(view){
 annotationState.view=view;
 if(!view.groups.some(value=>value.id===annotationState.groupId))annotationState.groupId=view.groups.find(value=>!value.run)?.id||view.groups[0]?.id||null;
 const active=group();
 if(annotationState.typeFilters.size&&!annotationState.typeFilters.has(annotationState.type))annotationState.type=Math.min(...annotationState.typeFilters);
 renderSourceTypes();keepVisibleCase();
 $('date').replaceChildren();for(const date of [...new Set([view.date,...view.dates])]){const option=node('option','',date);option.value=date;$('date').append(option);}$('date').value=view.date;
 const url=new URL(location.href);url.searchParams.set('date',view.date);if(active)url.searchParams.set('group',active.id);else url.searchParams.delete('group');history.replaceState(null,'',url);
 fileStatus();
 render();loadEvidence();
}
async function load(refresh=false){
 const sequence=++annotationState.loadSequence;setBusy(true);
 try{
  const date=$('date').value||new URLSearchParams(location.search).get('date');
  if(refresh){const value=await request('/api/annotation/refresh',{date:date||annotationState.view?.date});if(sequence===annotationState.loadSequence){annotationState.included=null;applyView(value);await loadCatalog();}}
  else{const query=new URLSearchParams();if(date)query.set('date',date);if(annotationState.included!==null){if(!annotationState.included.size)query.append('file','');else for(const id of annotationState.included)query.append('file',id);}const value=await request('/api/annotation?'+query);if(sequence===annotationState.loadSequence)applyView(value);}
 }catch(error){if(sequence===annotationState.loadSequence)status(error.message,true);}finally{if(sequence===annotationState.loadSequence)setBusy(false);}
}
function render(){
 const active=group(),files=annotationState.view.files;
 renderComparisonChoices();
 renderSourceTypes();keepVisibleCase();
 $('scope-label').hidden=annotationState.view.groups.length<=1;$('scope').replaceChildren();
 for(const value of annotationState.view.groups){const option=node('option','',value.run?value.run+' · '+value.round+' · 배포본 '+value.package_id?.slice(0,8):'실행 정보 없음 · annotator / labels');option.value=value.id;$('scope').append(option);}$('scope').value=active?.id||'';
 const totals=$('totals');totals.replaceChildren();
 for(const [count,title,cls] of [[active?.reviewers.length||0,'명',''],[active?.cases.length||0,'문항',''],[active?.totals.DISAGREE||0,'건 불일치','total-alert'],[active?.flagged_entries||0,'건 실패·유보','total-alert'],[active?.totals.MISSING||0,'건 미입력','total-missing']]){
  const item=node('span',cls);item.append(node('strong','',count.toLocaleString()),document.createTextNode(title));totals.append(item);
 }
 totals.append(node('span','scope-hint',active?.run?active.run+' · '+active.round:'동일한 추가·삭제 본문끼리 비교 · 실행 정보 미기록'));
 $('metrics').replaceChildren();
 for(const [index,type] of annotationState.view.types.entries()){
  const visible=isTypeVisible(index),metric=active?.metrics[index],button=action('',()=>selectType(index),'metric'+(visible&&index===annotationState.type?' selected':''));button.disabled=!visible;
  button.setAttribute('aria-label',type.title+' 카파 '+(metric?.kappa==null?'계산 불가':metric.kappa.toFixed(3)));
  const denominator=node('small','metric-denominator',metric?metric.included.toLocaleString()+'/'+metric.total.toLocaleString():'0/0');denominator.title='공통 평가 문항 / 전체 문항';
  button.append(node('span','metric-title',type.title),node('span','metric-value'+(metric?.kappa<0?' negative':''),'κ '+(metric?.kappa==null?'—':metric.kappa.toFixed(3))),node('small','',metric?.agreement==null?'공통 판정 없음':'일치 '+percent(metric.agreement)),denominator);
  button.title=(metric?.method||'κ')+' · '+(metric?.reason||'공통 저장 판정 기준')+' · 공통 '+(metric?.included||0)+' / 전체 '+(metric?.total||0)+'문항 · 제외 '+(metric?.excluded||0)+'문항';$('metrics').append(button);
 }
 renderManagerFilters();renderList();renderCase();$('export').disabled=!active;
 if(files.some(file=>file.error))$('empty').textContent='입력 파일에서 형식 오류를 확인해 주세요.';
}
function renderList(){
 const items=visibleCases(),list=$('cases');list.replaceChildren();$('list-count').textContent=items.length.toLocaleString()+' / '+(group()?.cases.length||0).toLocaleString()+'문항';
 $('next-issue').disabled=!items.some(item=>item.flags.includes('DISAGREE'));
 if(!items.length){list.append(node('p','list-empty','조건에 맞는 문제가 없습니다.'));return;}
 for(const item of items){
  const important=item.flags.some(value=>['DISAGREE','FORMAT','CONTENT','REJECTED'].includes(value)),button=action('',()=>selectCase(item.case),'case-link'+(item.case===annotationState.caseName?' selected':'')+(important?' flagged':''));
  const name=node('span','case-name',item.case);appendManagerListMark(name,item);if(item.flags.includes('NOTE')){const note=node('span','case-note',' ✎');note.title='평가자 주석 있음';name.append(note);}button.append(name);const dots=node('span','case-dots');
  for(const row of item.rows){let cls='';if(row.flags.includes('FORMAT')||row.flags.includes('CONTENT'))cls='error';else if(row.flags.includes('DISAGREE'))cls='disagree';else if(row.flags.includes('REJECTED'))cls='reject';else if(row.flags.includes('PENDING'))cls='pending';else if(!row.flags.includes('MISSING'))cls='accept';const dot=node('i','dot '+cls);dot.title=row.title+' · '+(row.flags.map(value=>annotationFlags[value][0]).join(' / ')||'통과 일치');dots.append(dot);}
  button.append(dots);button.setAttribute('aria-current',String(item.case===annotationState.caseName));list.append(button);
  button.dataset.case=item.case;
 }
 list.querySelector('.selected')?.scrollIntoView({block:'nearest'});
}
function updateCaseSelection(){
 const list=$('cases'),previous=list.querySelector('.selected');
 previous?.classList.remove('selected');previous?.setAttribute('aria-current','false');
 const selected=list.querySelector('[data-case="'+annotationState.caseName+'"]');
 selected?.classList.add('selected');selected?.setAttribute('aria-current','true');selected?.scrollIntoView({block:'nearest'});
}
function renderContent(container,row){
 const cacheKey=annotationState.caseName+'|'+row.variant,expanded=annotationState.texts.has(cacheKey);
 const fallback=annotationState.evidence?.generation?.[row.variant];
 if(!row.content.length&&!fallback){container.append(node('span','content-empty','추가·삭제 본문 미기록'));return;}
 const layout=node('div','content-layout'),preview=node('div','content-preview'+(expanded?'':' collapsed'));layout.append(preview);container.append(layout);
 const toggle=action(expanded?'접기':'전체',()=>{if(expanded)annotationState.texts.delete(cacheKey);else annotationState.texts.add(cacheKey);renderCase();},'text-button content-toggle');toggle.setAttribute('aria-label',row.title+' 본문 '+(expanded?'접기':'전체 보기'));toggle.setAttribute('aria-expanded',String(expanded));
 if(!row.content.length&&fallback){const text=node('p','edit-text source-text',fallback);preview.append(node('span','edit-tag edit-add','저장 본문'),text);layout.append(toggle);return;}
 for(const entry of row.content){
  if(row.content.length>1)preview.append(node('p','content-owner',entry.reviewer+'의 본문'));
  for(const [text,label,cls] of [[entry.inserted,'추가','edit-add'],[entry.removed,'삭제','edit-remove']]){
   if(!text)continue;const paragraph=node('p','edit-text'+(cls==='edit-remove'?' removed-text':''));paragraph.append(node('span','edit-tag '+cls,label),node('span','source-text',text));preview.append(paragraph);
  }
  if(!entry.inserted&&!entry.removed)preview.append(node('span','content-empty','추가·삭제 내용 없음'));
 }
 if(row.content.some(entry=>entry.inserted||entry.removed))layout.append(toggle);
}
function renderTypeFilters(item){
 const container=$('type-filters'),focused=container.contains(document.activeElement)?document.activeElement.dataset.filter:null;container.replaceChildren();container.hidden=!item;
 if(!item)return;
 for(const [index,title] of [[null,'전체'],['ISSUES','성공외'],...item.rows.map((row,index)=>[index,row.title])]){
  if(index==='ISSUES'){const label=node('label','type-filter'+(annotationState.hideSuccess?' selected':'')),check=node('input');label.dataset.filter='ISSUES';check.type='checkbox';check.checked=annotationState.hideSuccess;check.dataset.filter='ISSUES';check.setAttribute('aria-label','유형 필터 · 성공외');check.setAttribute('aria-controls','comparison');label.title='성공한 유형을 제외하고 실패·유보·오류·미입력 유형 표시';check.onchange=()=>{annotationState.hideSuccess=check.checked;renderCase();};label.append(check,node('span','',title));container.append(label);continue;}
  const selected=index===null?annotationState.typeFilters.size===item.rows.length:annotationState.typeFilters.has(index),label=node('label','type-filter'+(selected?' selected':'')),check=node('input');check.type='checkbox';check.checked=selected;
  check.dataset.filter=index===null?'ALL':String(index);check.setAttribute('aria-label','유형 필터 · '+title);check.setAttribute('aria-controls','comparison');if(index===null)check.indeterminate=annotationState.typeFilters.size>0&&!selected;check.onchange=()=>setTypeFilter(index,check.checked);
  label.title=index===null?'7개 유형 전체 체크 / 해제':title+' 표시 / 숨기기';label.append(check,node('span','',title));container.append(label);
 }
 if(focused!==null)container.querySelector('[data-filter="'+focused+'"]')?.focus({preventScroll:true});
}
function renderCase(){
 const active=group(),item=currentCase(),table=$('comparison'),head=table.querySelector('thead'),body=table.querySelector('tbody');head.replaceChildren();body.replaceChildren();$('question').hidden=true;
 const indices=visibleTypeIndices(item);if(indices.length&&!indices.includes(annotationState.type))annotationState.type=indices[0];updateMetricSelection();
 renderManagerSummary(item);renderTypeFilters(item);
 $('empty').hidden=!!item;table.hidden=!item;
 if(!item){$('case-title').textContent='Annotation 결과';$('case-summary').textContent='';$('empty').textContent=active?.cases.length?'조건에 맞는 문제가 없습니다.':annotationState.view.files.length?'비교할 평가 기록이 없습니다. 입력 파일을 확인해 주세요.':'이 날짜 폴더에 JSON을 넣거나 JSON 추가를 눌러 주세요.';$('previous').disabled=true;$('next').disabled=true;return;}
 const filteredRows=item.rows.filter((row,index)=>isTypeVisible(index,item)),typeTitle=filteredRows.length+' / '+item.rows.length+'유형';
 $('case-title').textContent=item.case;$('case-summary').textContent=(item.source_type&&item.source_type!=='UNKNOWN'?item.source_type:'출처 미확인')+' · '+active.reviewers.join(' · ')+' · '+typeTitle+(item.flags.includes('DISAGREE')?' · 문항 판정 불일치 '+item.rows.filter(row=>row.flags.includes('DISAGREE')).length+'건':'');
 table.setAttribute('aria-label',filteredRows.map(row=>row.title).join(' · ')+' 유형과 모든 평가자 판정·주석 비교');table.hidden=!filteredRows.length;$('empty').hidden=!!filteredRows.length;if(!filteredRows.length)$('empty').textContent=annotationState.hideSuccess&&annotationState.typeFilters.size?'선택한 유형은 모두 성공입니다.':'표시할 유형을 체크해 주세요.';
 $('case-summary').title=item.source_reference?.source_id||item.source_reference?.dataset||'저장된 원본 출처를 확인할 수 없습니다.';
 if(annotationState.evidence?.question){$('question').textContent='Q  '+annotationState.evidence.question;$('question').hidden=false;}
 const headings=node('tr');headings.append(node('th','type-column','유형 · 상태'),node('th','content-column','추가 · 삭제 내용'));
 for(const reviewer of active.reviewers){const heading=node('th','reviewer-column',reviewer);heading.style.width=(40/active.reviewers.length)+'%';heading.append(node('small','','판정 · 주석'));headings.append(heading);}head.append(headings);
 table.style.minWidth=Math.max(800,active.reviewers.length*400)+'px';
 for(const [index,row] of item.rows.entries()){
  if(!isTypeVisible(index,item))continue;
  const tr=node('tr',(index===annotationState.type?'selected ':'')+(row.flags.includes('DISAGREE')?'row-disagree ':'')+(row.flags.includes('FORMAT')||row.flags.includes('CONTENT')?'row-error':''));tr.dataset.type=String(index);
  const title=node('th');title.setAttribute('scope','row');const toolbar=node('div','type-toolbar'),controls=node('div','type-actions');toolbar.append(action(row.title,()=>selectType(index),'type-button'),controls);const badges=node('div','flags');for(const value of row.flags)badges.append(flag(value));if(!badges.children.length)badges.append(node('span','flag gray','통과 일치'));controls.append(badges);title.append(toolbar);
  const links=annotationState.g02,link=links?.group===active.id&&links.case===item.case?links.links[row.variant]:null;
  if(link?.status==='AVAILABLE'){
   const jump=node('a','g02-link','G02 ↗');jump.href=link.href;jump.target='_blank';jump.rel='noopener';jump.setAttribute('aria-label',row.title+' G02 전체 문장 보기 (새 탭)');
   jump.title=link.run+' · '+link.origin_round+' · 원본과 perturbed 전체 본문 (새 탭)';controls.append(jump);
  }else{
   const jump=node('button','g02-link',link?'G02 ?':'G02 …');jump.type='button';jump.disabled=true;jump.setAttribute('aria-label',row.title+' '+(link?'G02 전체 문장 미확인':'G02 전체 문장 확인 중'));jump.title=link?.reason||'저장된 생성 문장과 실행·차수를 대조하고 있습니다.';controls.append(jump);
  }
  appendManagerNotes(title,row,null);tr.append(title);
  const content=node('td');renderContent(content,row);tr.append(content);
  for(const reviewer of active.reviewers){
   const cell=row.cells[reviewer],cls=annotationClasses[cell.decision]||'',td=node('td','cell '+cls+(row.flags.includes('DISAGREE')?' disagree':''));
   const decision=cell.issues.length?'형식 오류':cell.missing?(cell.decision?'작성 중 · '+annotationLabels[cell.decision]:'미입력'):annotationLabels[cell.decision];
   const rating=node('div','reviewer-toolbar');rating.append(node('span','decision '+(cell.issues.length?'invalid':cell.missing?'':cls),decision));td.append(rating);
   if(cell.issues.length)rating.append(action('오류 보기',()=>showCellIssue(reviewer,row,cell),'text-button'));
   if(cell.comment){const key=item.case+'|'+row.variant,expanded=annotationState.notes.has(key),comment=node('div','comment'+(expanded?'':' collapsed'),cell.comment);td.append(comment);const toggle=action(expanded?'접기':'주석 전체',()=>toggleNotes(index),'text-button');toggle.setAttribute('aria-expanded',String(expanded));rating.append(toggle);}
   else td.append(node('span','empty-note','주석 없음'));
   appendManagerNotes(td,row,reviewer);tr.append(td);
  }
  body.append(tr);
 }
 const items=visibleCases(),at=items.findIndex(value=>value.case===item.case);$('previous').disabled=at<=0;$('next').disabled=at<0||at>=items.length-1;
}
function selectCase(name){if(name===annotationState.caseName||!group()?.cases.some(item=>item.case===name))return;annotationState.caseName=name;annotationState.evidence=null;updateCaseSelection();renderCase();loadEvidence();}
function selectType(index){
 if(index===annotationState.type||!isTypeVisible(index))return;
 annotationState.type=index;
 for(const [at,button] of [...$('metrics').children].entries())button.classList.toggle('selected',at===index);
 for(const row of $('comparison').querySelectorAll('tbody tr'))row.classList.toggle('selected',Number(row.dataset.type)===index);
 renderManagerSummary(currentCase());
 $('comparison').querySelector('[data-type="'+index+'"]')?.scrollIntoView({block:'nearest'});
}
function moveType(direction){const indices=visibleTypeIndices(),at=indices.indexOf(annotationState.type);if(!indices.length)return;selectType(indices[Math.max(0,Math.min(indices.length-1,at+direction))]);}
function setTypeFilter(index,checked){if(index===null)annotationState.typeFilters=new Set(checked?annotationState.view.types.map((value,index)=>index):[]);else if(checked)annotationState.typeFilters.add(index);else annotationState.typeFilters.delete(index);if(annotationState.typeFilters.size&&!annotationState.typeFilters.has(annotationState.type))annotationState.type=Math.min(...annotationState.typeFilters);try{sessionStorage.setItem(annotationTypeFilterKey,JSON.stringify([...annotationState.typeFilters].sort((a,b)=>a-b)));}catch{}render();}
function moveCase(direction){const items=visibleCases(),at=items.findIndex(item=>item.case===annotationState.caseName),next=items[at+direction];if(next)selectCase(next.case);}
function nextDisagreement(){const all=visibleCases(),items=all.filter(item=>item.flags.includes('DISAGREE'));if(!items.length)return;const at=all.findIndex(item=>item.case===annotationState.caseName),next=items.find(item=>all.indexOf(item)>at)||items[0];selectCase(next.case);}
function toggleNotes(index=annotationState.type){const item=currentCase();if(!item)return;const key=item.case+'|'+item.rows[index].variant;if(annotationState.notes.has(key))annotationState.notes.delete(key);else annotationState.notes.add(key);renderCase();}
function setFilter(value){annotationState.filter=value;$('filter').value=value;const items=visibleCases();if(!items.some(item=>item.case===annotationState.caseName))annotationState.caseName=items[0]?.case||null;annotationState.evidence=null;renderList();renderCase();loadEvidence();}
function setSourceType(value){annotationState.sourceType=value;keepVisibleCase();renderList();renderCase();loadEvidence();}
async function loadEvidence(){
 const active=group(),caseName=annotationState.caseName,sequence=++annotationState.evidenceSequence;
 annotationState.g02=null;
 if(!active||!caseName)return;
 renderCase();
 const query=new URLSearchParams({date:annotationState.view.date,group:active.id,case:caseName});
 if(annotationState.included!==null){if(!annotationState.included.size)query.append('file','');else for(const id of annotationState.included)query.append('file',id);}
 const tasks=[request('/api/annotation/g02?'+query).then(data=>{
  if(sequence===annotationState.evidenceSequence){annotationState.g02=data;if((globalThis.FinarchI18n?.originalText($('status'))||$('status').textContent).startsWith('G02 연결을 확인하지 못했습니다.'))fileStatus();renderCase();}
 }).catch(error=>{
  if(sequence!==annotationState.evidenceSequence)return;
  annotationState.g02={group:active.id,case:caseName,links:Object.fromEntries(annotationState.view.types.map(type=>[type.variant,{status:'UNAVAILABLE',reason:error.message}]))};renderCase();status('G02 연결을 확인하지 못했습니다. '+error.message,true);
 })];
 if(active.run)tasks.push(request('/api/annotation/evidence?'+new URLSearchParams({run:active.run,case:caseName,round:active.round})).then(data=>{
  if(sequence!==annotationState.evidenceSequence)return;
  const record=data.runs[0],artifacts=record.artifacts||{},original=artifacts['data.json']||artifacts['01-source/01-receive-input/01-input.json']||{};
  const generation={};for(const type of annotationState.view.types){const observation=record.generation?.[type.variant+'/02-generate-text/04-observation.json']||record.generation?.[type.variant+'/run.json']?.observation;if(typeof observation?.context==='string')generation[type.variant]=observation.context;}
  annotationState.evidence={question:original.question,generation};renderCase();
 }).catch(error=>{if(sequence===annotationState.evidenceSequence)status('저장된 본문을 읽지 못했습니다. 평가 JSON의 판정과 주석은 표시합니다. '+error.message,true);}));
 await Promise.allSettled(tasks);
}
function openG02(){const jump=$('comparison').querySelector('[data-type="'+annotationState.type+'"] a.g02-link');if(jump)jump.click();}
function dialog(title){const element=$('dialog');$('dialog-title').textContent=title;$('dialog-body').replaceChildren();if(!element.open)element.showModal();$('close-dialog').focus();return $('dialog-body');}
function download(name,value){const blob=value instanceof Blob?value:new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=node('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
async function readFile(file,kind){const query=new URLSearchParams({date:annotationState.view.date,id:file.id,kind});if(kind==='original'){const response=await fetch('/api/annotation/file?'+query);if(!response.ok)throw Error('원본 파일을 읽지 못했습니다.');return response.blob();}return request('/api/annotation/file?'+query);}
function showFiles(){
 const body=dialog('입력 파일 · 원본과 형식 보완');body.append(node('p','dialog-note',annotationState.view.path),node('p','dialog-note','같은 평가자의 여러 파일은 한 사람으로 계산합니다. 서로 다른 판정이 중복되면 오류로 표시합니다. 체크로 비교할 파일을 선택할 수 있습니다.'));
 for(const file of annotationState.view.files){
  const card=node('section','file-card'+(file.issues.length?' error':'')),label=node('label'),check=node('input');check.type='checkbox';check.checked=file.included;
  check.onchange=async()=>{if(annotationState.included===null)annotationState.included=new Set(annotationState.view.files.filter(value=>value.included).map(value=>value.id));if(check.checked)annotationState.included.add(file.id);else annotationState.included.delete(file.id);await load();};
  label.append(check,node('span','file-name',file.filename));card.append(label,node('p','file-summary',(file.reviewer||'이름 미기록')+' · '+file.records.toLocaleString()+'항목 · 형식 보완 '+file.repairs.toLocaleString()+'건 · 오류 '+file.issues.length+'건'));
  const buttons=node('div','file-actions');
  for(const [title,kind] of [['보완 JSON 저장','repaired'],['원본 JSON 저장','original'],['보완 내역','log']]){const button=action(title,async()=>{try{const value=await readFile(file,kind);if(kind==='log')showLog(value);else download((kind==='repaired'?'normalized-':'')+file.filename,value);}catch(error){status(error.message,true);}});if(file.error&&kind==='repaired')button.disabled=true;buttons.append(button);}card.append(buttons);
  if(file.issues.length)card.append(node('p','comment',file.issues.slice(0,5).map(issue=>issue.message).join('\n')));body.append(card);
 }
}
function showLog(value){const body=dialog('형식 보완 내역 · '+value.filename),counts={};for(const change of value.changes)counts[change.rule]=(counts[change.rule]||0)+1;body.append(node('p','dialog-note','원본 SHA-256: '+value.sha256));for(const [rule,count] of Object.entries(counts))body.append(node('p','',(annotationRules[rule]||rule)+' · '+count.toLocaleString()+'건'));body.append(action('전체 내역 JSON 저장',()=>download('repair-log-'+annotationState.view.date+'.json',value)),node('pre','',JSON.stringify(value,null,2)));}
function showCellIssue(reviewer,row,cell){const body=dialog(annotationState.caseName+' · '+row.title+' · '+reviewer);body.append(node('p','dialog-note','형식이 모호한 항목은 카파 계산에서 제외합니다.'),node('pre','',JSON.stringify(cell,null,2)),action('입력 파일 보기',showFiles));}
function exportResults(){const active=group();if(!active)return;download('annotation-'+annotationState.view.date+'-'+active.id+'.json',{format:'finarch-annotation-summary-v1',date:annotationState.view.date,scope:{run:active.run,round:active.round,package_id:active.package_id},reviewers:active.reviewers,files:annotationState.view.files.filter(file=>active.file_ids.includes(file.id)),metrics:active.metrics,totals:active.totals,flagged_entries:active.flagged_entries,cases:active.cases,manager_reviews:active.manager_reviews,manager_revision:annotationState.view.manager_revision,generated_at:annotationState.view.generated_at});status('유형별 κ와 문항별 판정·평가자 주석·관리자 기록의 JSON 저장을 시작했습니다.');}
function showMetricHelp(){const body=dialog('유형별 κ 계산 기준');for(const text of ['파일을 입력하거나 새로고침하면 7개 유형을 각각 다시 계산합니다. 화면의 문제 필터는 κ의 계산 범위를 바꾸지 않습니다.','2명은 Cohen κ, 3명 이상은 Fleiss κ를 사용합니다. κ = (관측 일치율 − 우연 일치율) / (1 − 우연 일치율)입니다.','같은 문제·유형에 모든 평가자의 저장 판정이 있어야 합니다. 미입력·작성 중·형식 오류·본문이 다른 항목은 제외합니다. 서로 다른 실행·차수·배포본도 따로 계산합니다.','통과·실패·유보의 3개 범주를 사용합니다. 유보와 미입력은 구별합니다. 단일 범주만 있거나 공통 판정이 없으면 κ는 —로 표시합니다.','일치율은 공통 문항의 평가자 쌍끼리 일치한 비율입니다. 3명 이상에서는 전원 일치율과 다를 수 있습니다. 결과 JSON에 관측·우연·전원 일치율과 분모를 함께 기록합니다.'])body.append(node('p','dialog-note',text));const link=node('a','','계산식 출처 · statsmodels');link.href='https://www.statsmodels.org/stable/_modules/statsmodels/stats/inter_rater.html';link.target='_blank';link.rel='noopener';body.append(link);}
function showHelp(){const body=dialog('기존 단축키로 빠르게 확인하기'),grid=node('div','shortcut-grid');for(const [title,lines] of [['문제 이동',['Q / E 또는 ← / → : 이전 / 다음 문제','V : 다음 판정 불일치','검색 + Enter : 문제 번호로 이동']],['유형·본문',['A / D : 이전 / 다음 유형','B : 다음 유형','A/D·B는 체크한 유형 안에서 이동하며 체크 상태는 유지','G : 현재 유형의 G02 전체 문장 (새 탭)','W / S : 위 / 아래로 스크롤','N : 현재 유형 주석 펼치기 / 접기']],['관리자 주석',['R : 본문 하단의 현재 유형 주석 입력창','2 : 재검토 요청 · 3 : 평가 이유 문의 → 저장 버튼','2·3은 주석 없이 저장 가능 · Enter로 저장','4 : 문항 수정 필요 → 입력창 · 내용 필수','Ctrl/⌘ + Enter : 주석 저장','유형·문제를 이동해도 작성 중인 주석은 해당 유형에 유지','X : 비교 결과 JSON 저장','? : 단축키 안내']]]){const part=node('section','shortcut-group');part.append(node('h3','',title));for(const line of lines)part.append(node('p','',line));grid.append(part);}body.append(grid,node('p','dialog-note','문자 키는 한글 자판에서도 같은 위치로 작동합니다. 입력 중에는 숫자·문자 이동 키가 주석으로 입력되며 Ctrl/⌘ + Enter만 저장합니다. 평가자의 판정과 주석은 이 화면에서 변경하지 않습니다.'));}
function handleShortcut(event){
 if(event.defaultPrevented||event.isComposing||event.repeat||event.ctrlKey||event.metaKey||event.altKey||$('dialog').open)return;
 if(event.target.closest?.('input:not([type=checkbox]),textarea,select,[contenteditable="true"],[role="textbox"]'))return;
 const key=/^Key[A-Z]$/.test(event.code||'')?event.code.slice(3).toLowerCase():event.key.toLowerCase();
 const number=/^(?:Numpad|Digit)([234])$/.exec(event.code||'')?.[1]||(/^[234]$/.test(event.key)?event.key:null);
 let handled=true;
 if(key==='q'||event.key==='ArrowLeft')moveCase(-1);else if(key==='e'||event.key==='ArrowRight')moveCase(1);
 else if(key==='a')moveType(-1);else if(key==='d'||key==='b')moveType(1);
 else if(key==='v')nextDisagreement();else if(key==='n')toggleNotes();else if(key==='g')openG02();else if(key==='r')focusManagerNote();else if(key==='x')exportResults();
 else if(key==='w'||key==='s')window.scrollBy({top:(key==='w'?-1:1)*innerHeight*.5,behavior:'smooth'});
 else if(number)setManagerKind(managerKindShortcuts[number]);else if(event.key==='?')showHelp();else handled=false;
 if(handled){event.preventDefault();event.stopImmediatePropagation();}
}
document.addEventListener('DOMContentLoaded',async()=>{
 $('refresh').onclick=()=>load(true);$('import').onclick=()=>$('file-input').click();$('files').onclick=showFiles;$('export').onclick=exportResults;$('help').onclick=showHelp;$('metric-help').onclick=showMetricHelp;
 initManagerEditor();$('review-export').onclick=showManagerExport;
 $('dialog').addEventListener('close',()=>{const previous=annotationState.caseName;keepVisibleCase();renderList();renderCase();if(previous!==annotationState.caseName)loadEvidence();});
 $('close-dialog').onclick=()=>$('dialog').close();$('dialog').onclick=event=>{if(event.target===$('dialog')){const rect=$('dialog').getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)$('dialog').close();}};
 $('date').onchange=()=>{annotationState.included=null;annotationState.groupId=null;annotationState.caseName=null;annotationState.sourceType='ALL';annotationState.search='';$('search').value='';load(true);};
 $('scope').onchange=()=>{annotationState.groupId=$('scope').value;annotationState.caseName=group()?.cases[0]?.case||null;annotationState.evidence=null;const url=new URL(location.href);url.searchParams.set('group',annotationState.groupId);history.replaceState(null,'',url);render();loadEvidence();};
 $('comparison-choice').onchange=()=>selectComparison($('comparison-choice').value);
 $('filter').onchange=()=>setFilter($('filter').value);
 $('source-type').onchange=()=>setSourceType($('source-type').value);
 $('search').oninput=()=>{annotationState.search=$('search').value;renderList();};$('search').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();const item=visibleCases()[0];if(item){selectCase(item.case);$('search').blur();}}event.stopPropagation();};
 $('previous').onclick=()=>moveCase(-1);$('next').onclick=()=>moveCase(1);$('next-issue').onclick=nextDisagreement;
 $('file-input').onchange=async()=>{const files=[...$('file-input').files];if(!files.length)return;setBusy(true);try{const payload=[];for(const file of files)payload.push({name:file.name,text:await file.text()});annotationState.included=null;applyView(await request('/api/annotation/import',{date:annotationState.view.date,files:payload}));await loadCatalog();}catch(error){status(error.message,true);}finally{$('file-input').value='';setBusy(false);}};
 document.addEventListener('keydown',handleShortcut,true);
 await load();if(annotationState.view)await load(true);else await loadCatalog();
});
