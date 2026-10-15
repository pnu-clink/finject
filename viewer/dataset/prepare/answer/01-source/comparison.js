function preparation(parent,r){
 const p=el('section','panel source-comparison-panel');p.style.cssText='border:1px solid #bdc9d4;border-radius:8px;padding:16px;margin:8px 0';parent.append(p);
 p.append(el('h2','','원천 자료와 준비된 입력의 차이'));
 const diff=r.run.source_diff;
 if(!diff||diff.error){p.append(el('div','banner','원천 비교 자료를 읽지 못했습니다: '+(diff?.error||'기록 없음')))}
 else{
  const artifacts=r.run.artifacts||{},inputKey=['01-source/01-receive-input/01-input.json','00-data-preparation/01-select-input/01-input.json'].find(key=>artifacts[key]);
  const raw=diff.raw||{},input=inputKey?artifacts[inputKey]:diff.input||{};
  const provenance=artifacts['01-source/02-record-source/01-provenance.json']||artifacts['00-data-preparation/02-record-source/01-provenance.json']||{};
  const rawPath=artifacts['00-data-preparation/raw-record.json']?r.run.path+'/00-data-preparation/raw-record.json#/record':provenance.source?.path+(provenance.record_index!=null?'#/'+provenance.record_index:'');
  const inputPath=inputKey?r.run.path+'/'+inputKey:'경로 기록 없음';

  const usedRaw=new Set(),usedInput=new Set();
  const field=(obj,keys,used)=>{for(const key of keys)if(Object.hasOwn(obj,key)){used.add(key);return [key,obj[key]];}return ['기록 없음',undefined];};
  const q=field(raw,['question','query'],usedRaw),c=field(raw,['context'],usedRaw),answer=field(raw,['gold','ground_truth','answer','reference_answer'],usedRaw);
  if(q[1]===undefined&&Array.isArray(raw.questions)){
   const selected=raw.questions.find(item=>'tatqa-'+item.uid===input.raw_id);
   if(selected){q.splice(0,2,'questions['+raw.questions.indexOf(selected)+'].question',selected.question);answer.splice(0,2,'questions['+raw.questions.indexOf(selected)+'].answer',selected.answer);}
  }
  if(c[1]===undefined){const parts={};for(const key of ['paragraphs','table'])if(Object.hasOwn(raw,key)){usedRaw.add(key);parts[key]=raw[key];}if(Object.keys(parts).length)c.splice(0,2,'원본 문단·표',parts);}
  const table=el('table','source-qca-diff');table.style.cssText='width:100%;table-layout:fixed;border-collapse:collapse';
  const heading=el('tr');
  for(const [title,path] of [['Raw',provenance.source?.path||artifacts['00-data-preparation/raw-record.json']?rawPath:'경로 기록 없음'],['input.json',inputPath]]){
   const th=el('th'),label=el('span','source-file-path',path);label.style.cssText='font-size:11px;font-weight:400;color:#788593;overflow-wrap:anywhere;margin-left:8px';th.append(el('strong','',title),label);heading.append(th);
  }table.append(heading);
  const cell=(fields)=>{const td=el('td');td.style.cssText='vertical-align:top;width:50%;padding:10px;border:1px solid #d5dde5;overflow-wrap:anywhere';for(const [key,value] of fields){td.append(el('strong','',key+':'),el('div','prose',value===undefined?'기록 없음':typeof value==='string'?value:JSON.stringify(value,null,2)));}return td;};
  const groups=[['Q',[q],[field(input,['question'],usedInput)]],['C',[c],[field(input,['context'],usedInput)]],['A',[answer],[field(input,['reference_answer'],usedInput),field(input,['reference_answer_type'],usedInput),field(input,['reference_precision'],usedInput)]]];
  for(const [name,left,right] of groups){const title=el('tr'),label=el('th','',name);label.colSpan=2;label.style.textAlign='left';title.append(label);const row=el('tr');row.append(cell(left),cell(right));table.append(title,row);}
  const extraRow=el('tr');
  for(const [obj,used,label,other] of [[raw,usedRaw,'raw 추가·상이 필드',input],[input,usedInput,'input.json 추가·상이 필드',raw]]){
   const td=el('td');td.style.verticalAlign='top';
   const entries=Object.entries(obj).filter(([key])=>!used.has(key));
   const details=el('details');details.style.cssText='border-top:2px solid #c62828;padding:8px';
   details.append(el('summary','',label+' · '+entries.length+'개'));
   for(const [key,value] of entries){const line=el('div');if(!Object.hasOwn(other,key)||JSON.stringify(other[key])!==JSON.stringify(value))line.style.borderLeft='3px solid #c62828';jsonBox(line,key,value);details.append(line);}
   td.append(details);extraRow.append(td);
  }table.append(extraRow);p.append(table);

 }
}
function renderPreparationSourceFiles(p,r){
 const diff=r.run.source_diff;
 const files=standardTreeFolder(p,'준비 단계에서 함께 만들어진 파일 보기');
 for(const [path,value] of Object.entries(r.run.artifacts)){if(path.startsWith('00-data-preparation/')||path==='README.md')standardTreeFile(files,path,value,r.run.path+'/'+(r.run.artifact_aliases?.[path]||path));}
 if(diff?.raw)standardTreeFile(files,'원천 레코드 전체',diff.raw,displayedFilePath('원천 레코드 전체',diff.raw));

}
