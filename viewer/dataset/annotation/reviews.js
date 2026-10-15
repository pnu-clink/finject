// Manager decisions are independent of imported annotator ratings.
'use strict';
const managerKinds={CHECKED:['확인 완료','review-checked'],RECHECK:['재검토 요청','review-recheck'],WHY:['평가 이유 문의','review-why'],REPAIR:['문항 수정 필요','review-repair']};
const managerKindShortcuts={2:'RECHECK',3:'WHY',4:'REPAIR'};
const managerFilterNames={UNREVIEWED:'요청 없음',RECHECK:'재검토 요청',WHY:'평가 이유 문의',REPAIR:'문항 수정 필요',NOTE:'관리자 기록',CHECKED:'이전 확인 기록',STALE:'입력 변경'};
const managerFilters=new Set();
let managerSaving=false;
const managerDrafts=new Map();
function managerReview(item=currentCase()){return group()?.manager_reviews?.[item?.case]||{checked:false,note:'',entries:[]};}
function managerFlags(item){
 const review=managerReview(item),entries=review.entries.filter(entry=>!entry.stale),flags=[];
 if(review.checked||entries.some(entry=>entry.kind==='CHECKED'))flags.push('CHECKED');
 if(!entries.some(entry=>entry.kind!=='CHECKED')&&!(review.note&&!review.stale_note))flags.push('UNREVIEWED');
 flags.push(...new Set(entries.filter(entry=>entry.kind!=='CHECKED').map(entry=>entry.kind)));
 if((review.note&&!review.stale_note)||entries.length)flags.push('NOTE');
 if(review.stale_checked||review.stale_note||review.entries.some(entry=>entry.stale))flags.push('STALE');
 return flags;
}
function matchesManagerReview(item){return !managerFilters.size||managerFlags(item).some(flag=>managerFilters.has(flag));}
function renderManagerFilters(){
 const container=$('manager-filters');container.replaceChildren();const counts={};
 for(const item of group()?.cases||[])for(const flag of managerFlags(item))counts[flag]=(counts[flag]||0)+1;
 for(const [value,title] of Object.entries(managerFilterNames)){
  if(['CHECKED','STALE'].includes(value)&&!counts[value]&&!managerFilters.has(value))continue;
  const label=node('label','manager-filter'),check=node('input');check.type='checkbox';check.checked=managerFilters.has(value);check.setAttribute('aria-label','관리자 필터 · '+title);
  check.onchange=()=>{if(check.checked)managerFilters.add(value);else managerFilters.delete(value);keepVisibleCase();renderManagerFilters();renderList();renderCase();loadEvidence();};
  label.append(check,node('span','',title),node('small','',String(counts[value]||0)));container.append(label);
 }
 container.append(node('p','manager-filter-hint','체크한 종류를 함께 표시 · 미선택 시 전체'));
 $('review-export').disabled=annotationState.busy||!group();
}
function appendManagerListMark(name,item){
 const flags=managerFlags(item);if(flags.includes('REPAIR'))name.append(node('span','manager-list-mark review-repair',' !'));
 else if(flags.includes('RECHECK')||flags.includes('WHY'))name.append(node('span','manager-list-mark review-recheck',' ?'));
 else if(flags.includes('CHECKED'))name.append(node('span','manager-list-mark review-checked',' ✓'));
 name.title=flags.map(flag=>managerFilterNames[flag]).join(' · ');
}
function renderManagerSummary(item){
 const container=$('manager-summary');container.replaceChildren();container.hidden=!item;renderManagerEditor(item);
 if(!item)return;const review=managerReview(item);
 const checkedTypes=new Set(review.entries.filter(entry=>entry.kind==='CHECKED'&&!entry.stale).map(entry=>entry.variant));
 if(review.checked||checkedTypes.size)container.append(node('span','manager-badge review-checked',review.checked?'이전 문항 전체 확인 기록':'이전 유형 확인 '+checkedTypes.size));
 for(const kind of Object.values(managerKindShortcuts)){
  const count=review.entries.filter(entry=>entry.kind===kind&&!entry.stale).length;
  if(count)container.append(node('span','manager-badge '+managerKinds[kind][1],managerKinds[kind][0]+' '+count));
 }
 if(review.stale_checked||review.stale_note||review.entries.some(entry=>entry.stale))container.append(node('span','manager-badge review-repair','입력 변경 · 이전 기록 확인 필요'));
}
function appendManagerNotes(container,row,reviewer){
 const review=managerReview();
 for(const entry of review.entries.filter(value=>value.variant===row.variant&&value.reviewer===reviewer)){
  const card=node('div','manager-note '+managerKinds[entry.kind][1]+(entry.stale?' review-stale':''));
  card.append(node('strong','',managerKinds[entry.kind][0]+(entry.stale?' · 이전 입력':'')),node('p',entry.note?'annotation-note':'',entry.note||(entry.kind==='CHECKED'?'확인 완료':'주석 없음')));container.append(card);
 }
}
async function saveManagerReview(fields){
 if(managerSaving)throw Error('관리자 기록을 저장하고 있습니다.');
 const active=group(),date=annotationState.view.date;managerSaving=true;
 try{
  const result=await request('/api/annotation/manager-review',{date,group:active.id,case:annotationState.caseName,files:active.file_ids,revision:annotationState.view.manager_revision||0,...fields});
  if(annotationState.view.date===date){
   annotationState.view.manager_revision=result.revision;
   const target=annotationState.view.groups.find(value=>value.id===result.group);
   if(target){target.manager_reviews=result.cases;target.manager_recipients=result.recipients;}
   renderManagerFilters();keepVisibleCase();renderList();renderCase();
  }
  return result;
 }finally{managerSaving=false;renderManagerEditor();}
}
function managerTarget(item=currentCase()){
 const active=group(),row=item?.rows[annotationState.type];
 if(!active||!row||!isTypeVisible(annotationState.type,item))return null;
 return {item,active,row,key:[annotationState.view.date,active.id,item.case,row.variant].join('|')};
}
function managerDraft(target){
 if(!managerDrafts.has(target.key))managerDrafts.set(target.key,{kind:'RECHECK',reviewer:target.active.reviewers[0]||'',note:'',id:null,message:'',error:false});
 return managerDrafts.get(target.key);
}
function renderManagerEditor(item=currentCase()){
 const target=managerTarget(item),blocked=annotationState.busy||managerSaving||!target,form=$('manager-entry-form');if(!form)return;
 const draft=target?managerDraft(target):null;
 $('manager-target').textContent=target?target.item.case+' · '+target.row.title:'유형을 선택해 주세요.';
 $('manager-target').dataset.variant=target?.row.variant||'';
 for(const button of $('manager-kinds').querySelectorAll('button')){button.disabled=blocked;button.setAttribute('aria-pressed',String(button.dataset.kind===draft?.kind));}
 const recipient=$('manager-recipient'),names=target?.active.reviewers||[];
 if(JSON.stringify([...recipient.options].map(option=>option.value))!==JSON.stringify(names)){
  recipient.replaceChildren();for(const reviewer of names){const option=node('option','',reviewer);option.value=reviewer;recipient.append(option);}
 }
 if(draft&&!names.includes(draft.reviewer))draft.reviewer=names[0]||'';
 recipient.value=draft?.reviewer||'';recipient.disabled=blocked||!['RECHECK','WHY'].includes(draft?.kind);
 $('manager-recipient-field').hidden=!['RECHECK','WHY'].includes(draft?.kind);
 const text=$('manager-entry-note');if(text.value!==(draft?.note||''))text.value=draft?.note||'';text.disabled=blocked;text.required=!!target&&draft.kind==='REPAIR';
 text.placeholder=draft?.kind==='REPAIR'?'수정할 내용을 입력해 주세요 · Ctrl/⌘ + Enter로 저장':'주석 없음 · 필요하면 입력 · Ctrl/⌘ + Enter로 저장';
 text.setAttribute('aria-label',target?'관리자 주석 · '+target.item.case+' · '+target.row.title:'현재 유형의 관리자 주석');
 $('manager-save').disabled=blocked;$('manager-save').textContent=draft?.id?'주석 수정 저장':'주석 저장';
 $('manager-new').hidden=!draft?.id;$('manager-new').disabled=blocked;
 $('manager-message').textContent=draft?.message||'';$('manager-message').classList.toggle('error',!!draft?.error);
 renderManagerEntries(target);
}
function renderManagerEntries(target){
 const entries=$('manager-entries'),history=$('manager-history'),legacy=$('manager-legacy-note');entries.replaceChildren();legacy.replaceChildren();
 const review=target?managerReview(target.item):null,items=review?.entries.filter(value=>value.variant===target.row.variant)||[];
 history.hidden=!items.length&&!review?.note;$('manager-entry-count').textContent=String(items.length+(review?.note?1:0));
 if(review?.note)legacy.append(node('p','manager-case-note','이전 문항 전체 주석: '+review.note+(review.stale_note?' (이전 입력의 주석)':'')));
 if(!target)return;
 for(const entry of items){
  const [title,cls]=managerKinds[entry.kind],card=node('section','manager-entry-card '+cls);
  card.append(node('h3','',title+(entry.reviewer?' · '+entry.reviewer:'')),node('p','comment',entry.note||(entry.kind==='CHECKED'?'확인 완료':'주석 없음')));
  if(entry.stale)card.append(node('p','review-message error','입력 변경 · 현재 내용을 확인한 뒤 수정 저장해 주세요.'));
  const edit=action('수정',()=>{Object.assign(managerDraft(target),{id:entry.id,kind:entry.kind,reviewer:entry.reviewer||target.active.reviewers[0],note:entry.note,message:'',error:false});renderManagerEditor();focusManagerNote();});
  const remove=action('기록 제거',async()=>{const draft=managerDraft(target);try{await saveManagerReview({operation:'remove',case:target.item.case,id:entry.id});if(draft.id===entry.id)Object.assign(draft,{id:null,note:''});draft.message='주석을 목록에서 제거했습니다. 변경 이력에는 보존됩니다.';draft.error=false;}catch(error){draft.message=error.message;draft.error=true;}renderManagerEditor();});
  edit.disabled=remove.disabled=annotationState.busy||managerSaving;card.append(edit,remove);entries.append(card);
 }
}
function focusManagerNote(){
 if(!managerTarget()||annotationState.busy||managerSaving)return;
 $('manager-entry-note').focus({preventScroll:true});$('manager-entry-note').scrollIntoView({block:'nearest'});
}
function focusManagerSave(){
 if(!managerTarget()||annotationState.busy||managerSaving)return;
 $('manager-save').focus({preventScroll:true});$('manager-save').scrollIntoView({block:'nearest'});
}
function setManagerKind(kind){
 const target=managerTarget();if(!target||!Object.values(managerKindShortcuts).includes(kind)||managerSaving||annotationState.busy)return;
 Object.assign(managerDraft(target),{kind,message:'',error:false});renderManagerEditor();
 if(kind==='REPAIR')focusManagerNote();else focusManagerSave();
}
async function submitManagerNote(){
 const target=managerTarget();if(!target||annotationState.busy||managerSaving)return;
 const draft=managerDraft(target),fields={operation:'entry',case:target.item.case,id:draft.id,variant:target.row.variant,kind:draft.kind,reviewer:['RECHECK','WHY'].includes(draft.kind)?draft.reviewer:null,note:draft.note};
 if(fields.kind==='REPAIR'&&!fields.note.trim()){draft.message='수정할 내용을 입력해 주세요.';draft.error=true;renderManagerEditor();focusManagerNote();return;}
 try{
  const pending=saveManagerReview(fields);renderManagerEditor();await pending;
  Object.assign(draft,{id:null,note:'',message:target.item.case+' · '+target.row.title+' · '+managerKinds[fields.kind][0]+' 저장 완료',error:false});
 }catch(error){draft.message=error.message;draft.error=true;}
 renderManagerEditor();
}
function initManagerEditor(){
 const kinds=$('manager-kinds');kinds.replaceChildren();
 const shortNames={RECHECK:'재검토',WHY:'이유 문의',REPAIR:'문항 수정'};
 Object.entries(managerKindShortcuts).forEach(([number,kind])=>{const [title,cls]=managerKinds[kind],button=action('',()=>setManagerKind(kind),'manager-kind '+cls);button.dataset.kind=kind;button.append(node('kbd','',number),document.createTextNode(' '+shortNames[kind]));button.title=title;button.setAttribute('aria-label',number+' '+title);button.setAttribute('aria-pressed','false');kinds.append(button);});
 $('manager-entry-note').oninput=()=>{const target=managerTarget();if(target)managerDraft(target).note=$('manager-entry-note').value;};
 $('manager-recipient').onchange=()=>{const target=managerTarget();if(target)managerDraft(target).reviewer=$('manager-recipient').value;};
 $('manager-entry-form').onsubmit=event=>{event.preventDefault();submitManagerNote();};
 $('manager-entry-note').onkeydown=event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)&&!event.isComposing){event.preventDefault();submitManagerNote();}};
 $('manager-new').onclick=()=>{const target=managerTarget();if(target){Object.assign(managerDraft(target),{id:null,note:'',message:'',error:false});renderManagerEditor();focusManagerNote();}};
}
async function showManagerExport(){
 const active=group();if(!active)return;const body=dialog('관리자 주석 Export'),loading=node('p','dialog-note','저장된 관리자 주석을 읽고 있습니다.');body.append(loading);
 const query=new URLSearchParams({date:annotationState.view.date,group:active.id});for(const id of active.file_ids)query.append('file',id);
 try{
  const result=await request('/api/annotation/review-files?'+query);loading.remove();
  body.append(node('p','dialog-note','현재 비교 묶음의 평가자 문의·수정 요청을 독립 HTML로 내보냅니다. 평가자 이름이 파일명에 들어가며 본인 요청·주석·기존 평가·문제 전체 본문을 인터넷 없이 확인합니다. 목록 필터와 무관합니다.'));
  if(result.stale_entries)body.append(node('p','review-message error','입력이 변경된 이전 주석 '+result.stale_entries+'건은 제외합니다. 현재 입력에서 수정 저장해 주세요.'));
  if(!result.files.length){body.append(node('p','dialog-note','저장된 재검토 요청·평가 이유 문의·문항 수정 주석이 없습니다.'));return;}
  query.set('revision',String(result.revision));
  const zip=action('전체 ZIP 저장',async()=>{zip.disabled=true;try{const response=await fetch('/api/annotation/review-export?'+query);if(!response.ok)throw Error('관리자 기록이 변경되었거나 파일을 읽지 못했습니다. 내보내기를 다시 열어 주세요.');download('annotation-'+result.date+'-reviews.zip',await response.blob());status('평가자별 HTML과 문항 수정 HTML의 ZIP 저장을 시작했습니다.');}catch(error){status(error.message,true);}finally{zip.disabled=false;}},'primary');body.append(zip);
  for(const file of result.files){
   const card=node('section','file-card');card.append(node('h3','',file.filename),node('p','dialog-note',(file.reviewer||'문항 수정용')+' · '+file.count+'건'),action('HTML 저장',()=>download(file.filename,new Blob([file.html],{type:'text/html;charset=utf-8'}))));body.append(card);
  }
 }catch(error){loading.textContent=error.message;loading.classList.add('error');}
}
