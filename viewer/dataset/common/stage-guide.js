// [VM01] Explain processing separately from saved results; previews never invent files.
function stageFiles(row,variant){return variant?(row.run.generation||{}):row.run.artifacts;}
function stageFilePath(row,variant,path){
 if(!variant)return row.run.path+'/'+(row.run.artifact_aliases?.[path]||path);
 const saved=stageFiles(row,variant)[variant+'/run.json']?.path;
 const base=saved?(saved.startsWith('/')?saved:'reports/run/'+DATA.batch.name+'/'+saved):'reports/run/'+DATA.batch.name+'/02-generation/'+(row.run.generation_origins?.[variant]||DATA.batch.round)+'/'+row.sample.id+'/'+variant;
 return base+'/'+path.slice(variant.length+1);
}
function stagePreview(parent,row,variant,paths,label){
 const files=stageFiles(row,variant),found=paths.filter(path=>Object.hasOwn(files,path));
 if(!found.length){parent.append(el('span','small stage-file-missing',label+' · 저장 기록 없음'));return;}
 const b=button(label+' · 미리보기',()=>{const {body}=showSchemaDialog(label,'선택한 실행에 저장된 실제 파일입니다.');for(const path of found){body.append(el('h4','',path),filePathLabel(stageFilePath(row,variant,path)),jsonViewer(files[path],path));}});
 b.dataset.previewPaths=JSON.stringify(found);parent.append(b);
}
function renderMenuGuide(parent,row,variant,stage){
 renderStageFailureNotice(parent,row,variant,stage);
 const spec=(variant?generationGuide(row,variant,stage):preparationGuide(stage))||{title:stage,steps:[[stage.includes('exception')?'오류 진단·피드백':'검증','저장된 입력·판정·피드백 참조를 확인합니다.']]},guide=el('section','stage-guide');
 guide.setAttribute('aria-label','이 단계에서 하는 일');guide.append(el('h2','',spec.title));
 const list=el('ol','stage-step-list'),files=stageFiles(row,variant),prefix=(variant?variant+'/':'')+stage+'/';
 for(const step of spec.steps){
  const item=el('li'),line=el('div',/\bLLM\b/.test(step[0])?'stage-llm-step':'');line.append(el('strong','',step[0]+' : '),document.createTextNode(step[1]));if(/\bLLM\b/.test(step[0]))appendFeedbackBadge(line,stageFeedbackState(row,variant,stage,step[0].split(' · ')[0]));item.append(line);
  if(!DATA.evaluation&&step[2]?.length){const links=el('div','toolbar stage-previews');for(const [label,patterns] of step[2]){const matches=Object.keys(files).filter(path=>path.startsWith(prefix)&&(!row.run.artifact_aliases?.[path]||!Object.hasOwn(files,row.run.artifact_aliases[path])||!row.run.artifact_aliases[path].startsWith(prefix))&&patterns.some(pattern=>typeof pattern==='string'?path===prefix+pattern:pattern.test(path.slice(prefix.length))));stagePreview(links,row,variant,matches,label);}item.append(links);}
  list.append(item);
 }
 guide.append(list,el('p','small','처리 방법을 설명하는 안내입니다. 실행·통과 여부는 아래의 저장 결과를 확인해 주세요.'));if(!DATA.evaluation&&!DATA.original&&spec.steps.some(step=>/\bLLM\b/.test(step[0]))){const callRow=variant?(stage==='02-generate-text'?generationCallSource(row,variant):generationRow(row,variant)):row;menuCallButton(guide,callRow,stage+'/');}parent.append(viewerDisclosure('stage-guide','이 단계에서 하는 일',guide));
}
function preparationGoldMismatch(row){
 const files=row.run.artifacts||{};
 for(const path of ['03-calculation/05-record-calculation-artifacts/02-comparison.json','03-calculation/04-compare-answer/01-comparison.json']){
  const value=files[path];if(value)return value.matches===false||value.normalized_matches===false?{path,value}:null;
 }
 return null;
}
function stageFailureEntries(row,variant,stage){
 const files=stageFiles(row,variant),prefix=(variant?variant+'/':'')+stage+'/',seen=new Set(),entries=[];
 for(const [path,value] of Object.entries(files||{})){
  if(!path.startsWith(prefix)||!value||value.status!=='FAIL')continue;
  const physical=stageFilePath(row,variant,path);
  if(seen.has(physical))continue;
  seen.add(physical);entries.push({path,physical,value});
 }
 const run=stageFiles(row,variant)?.[variant?variant+'/run.json':'run.json'];
 const mismatch=!variant&&stage==='03-calculation'?preparationGoldMismatch(row):null;
 if(mismatch&&!entries.some(e=>e.path===mismatch.path))entries.push({path:mismatch.path,physical:stageFilePath(row,null,mismatch.path),value:{...mismatch.value,reason:'GOLD_MISMATCH: Python 계산값과 골드 정답이 다릅니다.'}});
 if(!entries.length&&run?.status==='FAIL'&&run.stopped_at?.split('/')[0]===stage)
  entries.push({path:variant?variant+'/run.json':'run.json',physical:stageFilePath(row,variant,variant?variant+'/run.json':'run.json'),value:run});
 return entries;
}
function renderStageFailureNotice(parent,row,variant,stage){
 const entries=stageFailureEntries(row,variant,stage);
 if(!entries.length)return;
 const notice=el('section','failure-banner');notice.setAttribute('role','alert');notice.setAttribute('aria-label','현재 단계 오류와 원본 파일');
 notice.append(el('strong','',stage+' · 저장된 오류 기록'));
 for(const {path,physical,value} of entries){
  notice.append(el('p','',value.reason||value.data?.reason||'FAIL 판정 — 원본 기록을 확인하세요.'),filePathLabel(physical));
  notice.append(button('오류 원본 보기 · '+path,()=>{const {body}=showSchemaDialog('오류 원본',physical);body.append(jsonViewer(value,path));}));
 }
 parent.append(notice);
}
function renderStageFiles(panel,row,variant,stage){
 const artifacts=stageFiles(row,variant),prefix=(variant?variant+'/':'')+stage+'/',entries=Object.entries(artifacts).filter(([path])=>path.startsWith(prefix)&&(!row.run.artifact_aliases?.[path]||!Object.hasOwn(artifacts,row.run.artifact_aliases[path])||!row.run.artifact_aliases[path].startsWith(prefix)));
 panel.append(el('h2','','결과 파일'),el('p','small','폴더를 펼쳐 실제 입력·원응답·검사·결과를 확인합니다. 빨간 파일은 저장된 실패 판정입니다.'));
 if(!entries.length){panel.append(el('p','small','이 단계의 저장된 실행 기록이 없습니다.'));return;}
 const tree={};for(const [path,value] of entries){const parts=path.slice(prefix.length).split('/');let node=tree;for(const part of parts.slice(0,-1))node=node[part]??={};node[parts.at(-1)]={_file:true,value,path};}
 const failed=item=>item._file&&item.value?.status==='FAIL',contains=node=>Object.values(node).some(item=>item._file?failed(item):contains(item));
 function draw(parent,node){for(const [name,item] of Object.entries(node).sort(([a],[b])=>a.localeCompare(b))){
  if(!item._file){draw(standardTreeFolder(parent,name,contains(item)),item);continue;}
  const line=el('div','artifact-file-row'),path=stageFilePath(row,variant,item.path),b=button(name+(failed(item)?' · 실패':''),()=>{const {body}=showSchemaDialog(name,path);body.append(jsonViewer(item.value,name));});
  b.title=item.path;b.dataset.artifactPath=item.path;if(failed(item))b.classList.add('tab-failed');line.append(b,filePathLabel(path));if(failed(item))line.append(el('div','small',item.value.reason||item.value.data?.reason||'실패 판정이 기록된 파일입니다.'));parent.append(line);
 }}draw(variant?standardTreeFolder(panel,stage,contains(tree)):panel,tree);
 if(!variant&&stage==='01-source')renderPreparationSourceFiles(panel,row);
}
