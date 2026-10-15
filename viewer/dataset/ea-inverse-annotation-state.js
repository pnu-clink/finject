/* Human agreement records stay separate from the saved inverse review. */
(function(root){
'use strict';
const TYPES=['EA_01','EA_02'],DECISIONS=['accept','reject','pending'],FORMAT='finarch-ea-inverse-annotations-v1';
const clone=x=>x==null?x:JSON.parse(JSON.stringify(x));
function name(value){if(typeof value!=='string'||!value.trim()||value.trim().length>80||/[\x00-\x1f\x7f]/.test(value))throw Error('Annotator 이름을 1~80자로 입력해 주세요.');return value.trim().normalize('NFC');}
function shortcut(code){const match=/^(?:Digit|Numpad)([1-6])$/.exec(code);if(!match)return null;const n=Number(match[1])-1;return {type:TYPES[n%2],decision:DECISIONS[Math.floor(n/2)]};}
function matchFilters(c,filters){return c.items.every(v=>filters[v.type]==='all'||String(v.inverse_review.inverse_possible)===filters[v.type]);}
function create(data){
 const items=new Map(data.cases.flatMap(c=>c.items.map(v=>[c.id+':'+v.type,v]))),labels=new Map(),undo=[];
 let annotator='',index=0,type=0,filters={EA_01:'all',EA_02:'all'},visible=data.cases.map((_,i)=>i);
 const key=(kind=TYPES[type])=>data.cases[index].id+':'+kind;
 function setFilters(value){if(!value||TYPES.some(t=>!['all','true','false'].includes(value[t])))throw Error('역산 필터가 잘못되었습니다.');filters={EA_01:value.EA_01,EA_02:value.EA_02};visible=data.cases.flatMap((c,i)=>matchFilters(c,filters)?[i]:[]);if(visible.length&&!visible.includes(index))index=visible[0];}
 function start(value){annotator=name(value);labels.clear();undo.length=0;index=0;type=0;setFilters({EA_01:'all',EA_02:'all'});}
 function requireName(){if(!annotator)throw Error('이름을 입력하고 시작해 주세요.');}
 function choose(kind){if(!TYPES.includes(kind))throw Error('ER 유형을 확인해 주세요.');type=TYPES.indexOf(kind);}
 function decide(decision,kind=TYPES[type]){requireName();if(!DECISIONS.includes(decision))throw Error('잘못된 판정입니다.');if(!visible.length)throw Error('필터에 맞는 문항이 없습니다.');choose(kind);const k=key(),old=clone(labels.get(k));undo.push([k,old]);labels.set(k,{id:data.cases[index].id,type:kind,decision,comment:decision==='accept'?'':old?.comment||'',content_sha256:items.get(k).content_sha256,updated_at:new Date().toISOString()});return k;}
 function comment(value,kind=TYPES[type]){requireName();choose(kind);const record=labels.get(key());if(!record||record.decision==='accept')throw Error('Reject·Pending에만 댓글을 입력할 수 있습니다.');if(typeof value!=='string'||value.length>20000)throw Error('댓글은 20,000자 이내로 입력해 주세요.');record.comment=value;record.updated_at=new Date().toISOString();}
 function back(){requireName();const item=undo.pop();if(!item)return false;const [k,old]=item;if(old)labels.set(k,old);else labels.delete(k);const [id,kind]=k.split(':');index=data.cases.findIndex(c=>c.id===id);choose(kind);if(!visible.includes(index))setFilters({EA_01:'all',EA_02:'all'});return true;}
 function move(delta){if(!visible.length)return;const at=visible.indexOf(index);index=visible[Math.max(0,Math.min(visible.length-1,at+delta))];}
 function kind(delta){type=Math.max(0,Math.min(1,type+delta));}
 function jump(id){const found=data.cases.findIndex(c=>c.id===id);if(found<0)throw Error('id-0001~id-1354 범위로 이동해 주세요.');index=found;if(!visible.includes(index))setFilters({EA_01:'all',EA_02:'all'});}
 function nextUnreviewed(){const start=visible.indexOf(index);for(let d=1;d<=visible.length;d++){const i=visible[(start+d)%visible.length];if(!labels.has(data.cases[i].id+':'+TYPES[type])){index=i;return true;}}return false;}
 function counts(){const c={accept:0,reject:0,pending:0,unreviewed:data.items-labels.size,checked:labels.size};for(const v of labels.values())c[v.decision]++;return c;}
 function exported(){requireName();return {format:FORMAT,package_id:data.package_id,snapshot_sha256:data.snapshot_sha256,snapshot_file:data.snapshot_file,run:data.run,annotator,exported_at:new Date().toISOString(),n:data.n,items:data.items,counts:counts(),labels:[...labels.values()].sort((a,b)=>a.id.localeCompare(b.id)||a.type.localeCompare(b.type)),position:{id:data.cases[index].id,type:TYPES[type]},view:{filters:{...filters}},human_review_scope:'Agreement with the saved inverse_possible decision. Separate from production quality status.'};}
 function validate(value){
  if(!value||value.format!==FORMAT||value.package_id!==data.package_id||value.snapshot_sha256!==data.snapshot_sha256||value.run!==data.run||value.n!==data.n||value.items!==data.items)throw Error('이 HTML과 다른 결과 파일의 annotation입니다.');
  const who=name(value.annotator);if(!Array.isArray(value.labels)||value.labels.length>data.items)throw Error('Annotation 항목 수가 잘못되었습니다.');
  if(value.view&&(TYPES.some(t=>!['all','true','false'].includes(value.view.filters?.[t]))))throw Error('저장된 필터가 잘못되었습니다.');
  const seen=new Set(),checked=[];
  for(const entry of value.labels){if(!entry||typeof entry!=='object')throw Error('잘못된 annotation 항목입니다.');const k=entry.id+':'+entry.type,v=items.get(k);if(!v||seen.has(k)||entry.content_sha256!==v.content_sha256||!DECISIONS.includes(entry.decision)||typeof entry.comment!=='string'||entry.comment.length>20000||(entry.decision==='accept'&&entry.comment!==''))throw Error('중복·문항·판정·댓글·Q/C 해시를 확인해 주세요.');if(typeof entry.updated_at!=='string'||!Number.isFinite(Date.parse(entry.updated_at)))throw Error('저장 시각이 잘못되었습니다.');seen.add(k);checked.push({id:entry.id,type:entry.type,decision:entry.decision,comment:entry.comment,content_sha256:entry.content_sha256,updated_at:entry.updated_at});}
  return {annotator:who,labels:checked,position:value.position,filters:value.view?.filters};
 }
 function imported(value,{merge=false}={}){const checked=validate(value);if(merge&&annotator!==checked.annotator)throw Error('다른 annotator의 기록은 합칠 수 없습니다.');if(!merge)start(checked.annotator);let applied=0,kept=0;for(const v of checked.labels){const k=v.id+':'+v.type,old=labels.get(k);if(old&&Date.parse(old.updated_at)>=Date.parse(v.updated_at)&&(old.updated_at!==v.updated_at||old.decision!==v.decision||old.comment!==v.comment)){kept++;continue;}labels.set(k,clone(v));applied++;}undo.length=0;if(checked.position&&data.cases.some(c=>c.id===checked.position.id)&&TYPES.includes(checked.position.type)){jump(checked.position.id);choose(checked.position.type);}if(checked.filters)setFilters(checked.filters);return {applied,kept};}
 return {start,decide,comment,back,move,kind,choose,jump,setFilters,nextUnreviewed,counts,exported,validate,imported,labels,key,get annotator(){return annotator;},get index(){return index;},get type(){return TYPES[type];},get current(){return items.get(key());},get filters(){return {...filters};},get visible(){return [...visible];}};
}
const api={create,name,shortcut,matchFilters,TYPES,DECISIONS,FORMAT};root.EAAnnotation=api;if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
