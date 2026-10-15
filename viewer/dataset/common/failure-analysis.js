// Read-only interpretation is separate from pipeline and human verdicts.
const failureAnalysisRequests=new Map(),failureAnalysisNotices=new Map();
let failureAnalysisEvidenceSequence=0;
function failureAnalysisPhase(phase){return phase==='preparation'?'Preparation':'Generation';}
function failureAnalysisText(value){return value==null?'':typeof value==='string'?value:Array.isArray(value)?value.map(failureAnalysisText).join('\n'):JSON.stringify(value);}
function failureAnalysisJobs(phase){
 return (DATA.batch?.failure_analysis?.jobs||[]).filter(job=>job.phase===phase).slice().sort((a,b)=>
  String(b.created_at||b.id).localeCompare(String(a.created_at||a.id),undefined,{numeric:true}));
}
function failureAnalysisPending(run){
 const pending=failureAnalysisRequests.get(run),state=DATA.batch?.name===run?DATA.batch.failure_analysis:null;
 if(pending?.status==='accepted'&&(state?.busy||(state?.jobs||[]).some(job=>!pending.ids.includes(job.id)))){
  failureAnalysisRequests.delete(run);failureAnalysisNotices.delete(run);return null;
 }
 return pending;
}
function failureAnalysisNotice(run,message){
 failureAnalysisNotices.set(run,message);failureAnalysisSync();
 for(const node of document.querySelectorAll('.failure-analysis-overview'))if(node.dataset.run===run)node.querySelector('details').open=true;
}
function failureAnalysisSync(){
 const run=DATA.batch?.name,state=DATA.batch?.failure_analysis||{},pending=failureAnalysisPending(run);
 for(const node of document.querySelectorAll('.failure-analysis-button')){
  if(node.dataset.run!==run)continue;
  node.disabled=!state[node.dataset.phase]||!!state.busy||!!pending;
 }
 for(const node of document.querySelectorAll('.failure-analysis-notice')){
  if(node.dataset.run===run)node.textContent=failureAnalysisNotices.get(run)||'';
 }
}
function confirmFailureAnalysis(run,preview){
 return new Promise(resolve=>{
  const dialog=el('dialog','recheck-confirm failure-analysis failure-analysis-confirm failure-analysis-'+preview.phase),title=el('h2','','실패 해석을 시작할까요?');
  const costs=preview.cost_breakdown,money=value=>Number.isFinite(value)?'US$ '+value.toLocaleString('en-US',{maximumFractionDigits:6}):'미산정';
  const costRows=costs?[
   el('p','small','1회 기준: 입력 '+costs.input_token_budget.toLocaleString('en-US')+' + 출력 '+costs.output_token_budget.toLocaleString('en-US')+' = 총 '+costs.total_token_budget.toLocaleString('en-US')+'토큰'),
   el('p','small','백만 토큰당 입력 '+money(costs.input_per_million)+' / 출력 '+money(costs.output_per_million)+' · max는 토큰 단가를 낮추는 설정이 아닙니다.'),
   el('p','','실패 분석: '+money(costs.per_call_usd)+' × '+preview.analysis_calls+'건 = '+money(costs.analysis_usd)),
   el('p','','한국어 번역 별도: '+money(costs.per_call_usd)+' × '+preview.translation_calls+'건 = '+money(costs.translation_usd))
  ]:[];
  title.id='failure-analysis-confirm-title';dialog.setAttribute('aria-labelledby',title.id);
  dialog.append(title,el('p','',run+' · '+failureAnalysisPhase(preview.phase)+' 전체 최신 실패 '+preview.planned+'건'),
   el('p','small','선택 문항·유형·차수·화면 필터에 관계없이 이 실행 전체의 최신 실패를 해석합니다.'),
   el('p','','모델: '+preview.model+' · 추론: '+preview.effort),el('p','','최대 호출: '+preview.calls+'회'),
   el('p','small','대상마다 해석 1회 + 한국어 표시 번역 1회, 최대 2회 호출합니다. 번역 실패 시 원문 해석과 번역 오류를 표시합니다.'),
   ...costRows,
   el('p','',Number.isFinite(preview.estimated_cost_usd)?'보수적 예산 상한 추정: US$ '+preview.estimated_cost_usd.toLocaleString('en-US',{maximumFractionDigits:6}):'예산 상한 추정: 산정되지 않았습니다. 무료를 뜻하지 않습니다.'),
   el('p','small','통상 예상 청구액이나 실제 청구액이 아닙니다.'),el('p','small',preview.estimate_note||'실제 비용은 처리량에 따라 달라질 수 있습니다.'),
   el('p','small','동일한 미리보기의 완료 작업이 있으면 해당 기록을 반환하며 추가 유료 호출을 하지 않습니다.'),
   el('p','banner','API 사용 비용이 발생합니다. 해석은 검토 조언이며, 실제 PASS/FAIL이나 사람 판정을 바꾸지 않습니다.'));
  let settled=false;const opener=document.activeElement;
  const finish=value=>{if(settled)return;settled=true;dialog.close();dialog.remove();if(opener?.isConnected)opener.focus();resolve(value);};
  const no=button('No · 취소',()=>finish(false)),yes=button('Yes · 실패 해석 시작',()=>finish(true));
  no.type=yes.type='button';no.autofocus=true;const actions=el('div','toolbar');actions.append(no,yes);dialog.append(actions);
  dialog.addEventListener('cancel',event=>{event.preventDefault();finish(false);});dialog.addEventListener('close',()=>finish(false));
  document.body.append(dialog);dialog.showModal();no.focus();
 });
}
function failureAnalysisButton(phase){
 const run=DATA.batch?.name,state=DATA.batch?.failure_analysis||{},count=state[phase]||0;
 const b=button('실패 해석'+(count?' ('+count+')':''),async()=>{
  if(DATA.batch?.name!==run||failureAnalysisPending(run)||DATA.batch?.failure_analysis?.busy)return;
  const pending={phase,status:'preview',ids:(DATA.batch?.failure_analysis?.jobs||[]).map(job=>job.id)};
  failureAnalysisRequests.set(run,pending);failureAnalysisNotice(run,'호출량·비용을 확인하고 있습니다.');
  try{
   const response=await fetch('/api/failure-analysis/preview?name='+encodeURIComponent(run)+'&phase='+encodeURIComponent(phase),{cache:'no-store'});
   const preview=await response.json();if(!response.ok)throw Error(preview.error||'실패 해석 미리보기를 읽지 못했습니다.');
   if(DATA.batch?.name!==run)return;
   if(preview.phase!==phase||!preview.preview_id||preview.model!=='gpt-6-luna'||preview.effort!=='max'||!Number.isInteger(preview.planned)||preview.planned<0||!Number.isInteger(preview.calls)||preview.calls<0)throw Error('실패 해석의 모델·대상·호출량 정보를 확인할 수 없습니다.');
   if(!preview.planned){failureAnalysisNotice(run,'현재 실행에서 해석할 최신 실패가 없습니다.');return;}
   pending.status='confirm';failureAnalysisNotice(run,'실패 해석 시작 확인을 기다리고 있습니다.');
   if(!await confirmFailureAnalysis(run,preview)){failureAnalysisNotice(run,'실패 해석 요청을 취소했습니다.');return;}
   if(DATA.batch?.name!==run){failureAnalysisNotice(run,'선택 실행이 바뀌어 요청을 취소했습니다.');return;}
   pending.status='starting';failureAnalysisNotice(run,'실패 해석 시작을 요청하고 있습니다.');
   const started=await fetch('/api/failure-analysis',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run,phase,preview_id:preview.preview_id})});
   if(!started.ok){const data=await started.json();throw Error(data.error||'실패 해석 시작 요청이 실패했습니다.');}
   pending.status='accepted';
   const saved=await started.json();
   if(saved.phase===phase&&saved.id&&['COMPLETED','PARTIAL','ERROR','CANCELLED'].includes(saved.status)){
    pending.status='returned';
    failureAnalysisNotice(run,saved.status==='COMPLETED'&&pending.ids.includes(saved.id)?'같은 미리보기의 완료 작업 '+saved.id+'을 확인했습니다. 추가 유료 호출은 없습니다.':'작업 '+saved.id+' · '+failureAnalysisStatus(saved.status)+' · 저장된 결과를 확인해 주세요.');
   }else failureAnalysisNotice(run,'실패 해석 요청이 접수되었습니다. 실행 기록 갱신을 기다리고 있습니다.');
  }catch(error){failureAnalysisNotice(run,'실패 해석 요청 오류: '+error.message+' · 저장된 실행 기록을 확인한 뒤 다시 요청해 주세요.');}
  finally{if(pending.status!=='accepted')failureAnalysisRequests.delete(run);failureAnalysisSync();}
 },'failure-analysis-button recheck-'+phase);
 b.dataset.run=run||'';b.dataset.phase=phase;
 b.disabled=!run||!count||!!state.busy||!!failureAnalysisPending(run);
 b.title='현재 실행 전체의 '+failureAnalysisPhase(phase)+' 최신 실패를 해석합니다. 호출량·비용 확인 후 Yes에서 시작합니다.';
 return b;
}
function failureAnalysisStatus(status){
 return ({QUEUED:'해석 대기',RUNNING:'해석 중',COMPLETED:'해석 완료',PARTIAL:'일부 해석 완료',ERROR:'해석 오류',FAIL:'해석 실패',PASS:'해석 처리 완료',SKIPPED:'해석 제외',CANCELLED:'해석 취소'})[status]||status||'상태 기록 없음';
}
function failureAnalysisReviewLink(result,phase){
 const query=new URLSearchParams({run:DATA.batch.name,case:result.case,stage:phase==='preparation'?'07-human-review':'05-human-review'});
 if(phase==='generation'&&result.variant)query.set('variant',result.variant);
 const link=el('a','',result.case+(result.variant?' / '+result.variant:''));link.href='?'+query;return link;
}
function failureAnalysisArtifactLink(result,phase,artifact){
 // The server serves stage records, not arbitrary files. Link to their actual stage.
 const path=String(artifact.path||''),relative=/^(01-preparation|02-generation)\//.test(path)?path:path.split('reports/run/'+DATA.batch.name+'/')[1];
 if(!relative||relative.split('/').some(part=>part==='..')||!relative.split('/').includes(result.case))return null;
 const artifactPhase=relative.startsWith('01-preparation/')?'preparation':phase;
 const marker=artifactPhase==='generation'?result.variant+'/':result.case+'/',tail=relative.split(marker)[1];
 const stage=tail?.split('/').find(part=>/^\d{2}-(source|review|review-and-correct|calculation|graph|verification|exception-handler|human-review|perturbation|generate-text|validation)$/.test(part));
 if(!stage)return null;
 const query=new URLSearchParams({run:DATA.batch.name,case:result.case,stage});
 if(artifactPhase==='generation'&&result.variant)query.set('variant',result.variant);
 const round=relative.split('/').find(part=>/^\d+-round$/.test(part));if(round)query.set('round',round);
 const link=el('a','','근거가 저장된 단계·파일 목록 열기');link.href='?'+query;link.target='_blank';link.rel='noopener';return link;
}
function failureAnalysisArtifacts(job,result){
 const byId=new Map();
 for(const list of [job.artifacts,result.analysis?.artifacts,result.artifacts])for(const artifact of Array.isArray(list)?list:[]){if(artifact?.id)byId.set(artifact.id,artifact);}
 return [...byId.values()];
}
function failureAnalysisLocalized(tag,cls,ko,en){
 const node=el(tag,cls,ko);globalThis.FinarchI18n?.bindText(node,ko,en);return node;
}
function renderFailureAnalysisTable(parent,job,results=job.results||[]){
 if(!results.length){parent.append(el('p','small',['QUEUED','RUNNING'].includes(job.status)?'저장된 해석 결과를 기다리고 있습니다. 완료된 항목부터 표시합니다.':'저장된 해석 결과가 없습니다.'));return;}
 const scroll=el('div','failure-analysis-scroll'),table=el('table','failure-analysis-table'),head=el('tr');
 for(const label of ['문항','현재거절이유','실제확인내용','검토의견']){const th=el('th','',label);th.setAttribute('scope','col');head.append(th);}
 const thead=el('thead'),body=el('tbody');thead.append(head);table.append(thead,body);scroll.append(table);parent.append(scroll);
 for(const result of [...results].sort((a,b)=>String(a.case||'').localeCompare(String(b.case||''),'en',{numeric:true})||String(a.variant||'').localeCompare(String(b.variant||''),'en',{numeric:true})||String(a.round||'').localeCompare(String(b.round||''),'en',{numeric:true}))){
  const tr=el('tr'),identity=el('td'),rejection=el('td'),observations=el('td'),advice=el('td'),raw=result.analysis||{},display=result.display_ko||raw;
  const value=key=>display[key]??raw[key],artifacts=failureAnalysisArtifacts(job,result),ids=new Map(artifacts.map(artifact=>[artifact.id,'failure-evidence-'+(++failureAnalysisEvidenceSequence)]));
  identity.append(failureAnalysisReviewLink(result,job.phase),el('p','small','대상 차수: '+(result.round||'기록 없음')),el('p','small',failureAnalysisStatus(result.status)));
  if(result.stale)identity.append(el('span','failure-analysis-stale','이전 자료 기준 · 최신 결과와 다를 수 있음'));
  if(result.analysis&&!result.display_ko)identity.append(el('p','small','한국어 표시 없음 · 원문 해석'));
  const rejectionText=failureAnalysisText(value('rejection_summary'));
  rejection.append(rejectionText?failureAnalysisLocalized('p','',rejectionText,failureAnalysisText(raw.rejection_summary)||rejectionText):el('p','',result.error?'해석 오류로 거절 이유 요약 없음':'아직 저장되지 않았습니다.'));
  const list=el('ul');
  for(const [index,observation] of (value('observations')||[]).entries()){
   const item=el('li'),kind=({RECORDED:'기록 확인',INFERRED:'추론',FACT:'기록 확인',OBSERVATION:'관찰',INFERENCE:'추론',HYPOTHESIS:'가설'})[String(observation.kind||'').toUpperCase()]||observation.kind;
   item.append(failureAnalysisLocalized('p','',failureAnalysisText(observation.statement),failureAnalysisText(raw.observations?.[index]?.statement)||failureAnalysisText(observation.statement)));if(kind)item.append(el('span','small',kind+' · '));
   for(const evidenceId of observation.evidence_ids||raw.observations?.[index]?.evidence_ids||[]){
    const id=ids.get(evidenceId);if(id){const a=el('a','failure-analysis-evidence',evidenceId);a.href='#'+id;item.append(a);}else item.append(el('span','small',evidenceId+' · 연결 근거 없음'));
   }
   list.append(item);
  }
  observations.append(list.children.length?list:el('p','small','저장된 확인 내용이 없습니다.'));
  if(result.analysis){
   for(const [key,label] of [['assessment','검토 의견'],['rationale','판단 근거'],['recommended_action','권장 조치'],['target_step','대상 단계'],['limitations','해석의 한계']]){
    const text=failureAnalysisText(value(key));if(text){const line=el('p');line.append(el('span','',label+': '),failureAnalysisLocalized('span','',text,failureAnalysisText(raw[key])||text));advice.append(line);}
   }
  }else advice.append(el('p','small','완료된 해석이 없습니다.'));
  if(raw.repair_plan){const plan=el('details');plan.append(el('summary','','재검토 수정 계획 · '+raw.repair_plan.action));jsonBox(plan,'LLM 재검토 입력 · English',raw.repair_plan);advice.append(plan);}
  if(result.error)advice.append(el('p','banner','해석 오류: '+failureAnalysisText(result.error)));
  if(result.translation_error)advice.append(el('p','banner','한국어 표시 번역 오류: '+failureAnalysisText(result.translation_error)+' · 원문 해석을 확인해 주세요. 실제 판정은 변경되지 않습니다.'));
  if(artifacts.length){
   const files=el('details');files.append(el('summary','','해석에 사용한 근거 파일 '+artifacts.length+'개'));
   for(const artifact of artifacts){
    const file=el('div','failure-analysis-artifact');file.id=ids.get(artifact.id);file.append(el('strong','',artifact.id),filePathLabel(artifact.path||'경로 기록 없음'),el('p','small','SHA-256: '+(artifact.sha256||'기록 없음')));
    const link=failureAnalysisArtifactLink(result,job.phase,artifact);if(link)file.append(link);files.append(file);
   }
   // Reveal the linked evidence before following its fragment inside the disclosure.
   for(const anchor of observations.querySelectorAll('a'))anchor.addEventListener('click',()=>{files.open=true;});
   advice.append(files);
  }
  tr.append(identity,rejection,observations,advice);body.append(tr);
 }
}
function renderFailureAnalysisJob(parent,job,results){
 parent.append(el('p','small',job.id+' · '+failureAnalysisStatus(job.status)+' · '+(job.completed??0)+'/'+(job.planned??0)+'건'));
 if(['QUEUED','RUNNING','PARTIAL'].includes(job.status))parent.append(el('p','small','부분 결과입니다. 저장된 항목부터 표시하며 기존 실행 기록은 유지합니다.'));
 if(job.error)parent.append(el('p','banner','작업 오류: '+failureAnalysisText(job.error)));
 renderFailureAnalysisTable(parent,job,results);
 if(job.usage){
  const usage=job.usage,known=value=>value==null?'기록 없음':String(value);
  parent.append(el('p','small','저장된 사용량: 호출 '+known(usage.calls)+'회 · 총 토큰 '+known(usage.token_totals_known?.total_tokens)+' · 기록 확인분 API 환산 비용 '+(Number.isFinite(usage.estimated_cost_usd_known)?'US$ '+usage.estimated_cost_usd_known.toLocaleString('en-US',{maximumFractionDigits:6}):'산정되지 않음')+' (실제 청구액 아님)'));
  if(usage.missing_usage_calls||usage.missing_cost_calls)parent.append(el('p','small','사용량 누락 '+known(usage.missing_usage_calls)+'회 · 비용 산정 누락 '+known(usage.missing_cost_calls)+'회 · 알려진 기록만 합산합니다.'));
 }
}
function renderFailureAnalysisOverview(parent){
 const state=DATA.batch?.failure_analysis;if(!state)return;
 const run=DATA.batch.name,content=el('div'),notice=el('p','small failure-analysis-notice');failureAnalysisPending(run);
 content.append(el('p','small','이 실행 전체의 최신 실패 해석입니다. 문항·유형·차수·필터 선택과 무관합니다. 해석 시점의 거절 이유와 검토 조언이며 실제 PASS/FAIL·사람 판정을 바꾸지 않습니다.'));
 notice.dataset.run=run;notice.setAttribute('role','status');notice.textContent=failureAnalysisNotices.get(run)||'';content.append(notice);
 if(state.busy)content.append(el('p','small','실패 해석 작업이 진행 중입니다. 완료된 항목부터 자동 갱신됩니다.'));
 for(const phase of ['preparation','generation']){
  const section=el('section','failure-analysis failure-analysis-phase failure-analysis-'+phase),jobs=failureAnalysisJobs(phase),phaseContent=el('div');
  if(!jobs.length)phaseContent.append(el('p','small','저장된 실패 해석이 없습니다.'));else{
   phaseContent.append(el('h4','','최신 해석'));renderFailureAnalysisJob(phaseContent,jobs[0]);
   if(jobs.length>1){const history=el('div');for(const job of jobs.slice(1)){const saved=el('div');renderFailureAnalysisJob(saved,job);history.append(viewerDisclosure('failure-analysis-job:'+run+':'+phase+':'+job.id,job.id+' · 이전 해석 기록',saved,false));}phaseContent.append(viewerDisclosure('failure-analysis-history:'+run+':'+phase,'이전 해석 기록 '+(jobs.length-1)+'개',history,false));}
  }
  section.append(viewerDisclosure('failure-analysis-phase:'+run+':'+phase,failureAnalysisPhase(phase),phaseContent,true));
  content.append(section);
 }
 const area=el('div','viewer-group failure-analysis-overview');area.dataset.run=run;area.append(viewerDisclosure('failure-analysis:'+run,'실패 해석 · 검토 조언'+(state.busy?' · 진행 중':''),content,false));parent.append(area);
}
function renderSelectedFailureAnalysis(parent,row,variant,stage){
 if(stage!==(variant?'05-human-review':'07-human-review'))return;
 const phase=variant?'generation':'preparation',jobs=failureAnalysisJobs(phase),matches=jobs.map(job=>({job,results:(job.results||[]).filter(result=>result.case===row.sample.id&&(result.variant||null)===(variant||null))})).filter(item=>item.results.length);
 if(!matches.length)return;
 const section=el('section','failure-analysis failure-analysis-selected failure-analysis-'+phase);section.setAttribute('aria-label','선택 문항의 실패 해석');
 section.append(el('h3','','실패 해석 · 검토 조언'),el('p','small','해석 대상 차수와 근거를 확인해 주세요. 실제 PASS/FAIL·사람 판정은 기존 기록을 따릅니다.'));
 const latest=matches[0];if(latest.job!==jobs[0])section.append(el('p','failure-analysis-stale','이전 작업의 해석입니다. 최신 작업에 이 문항의 해석 결과가 아직 없거나 대상에서 제외되었습니다.'));
 renderFailureAnalysisJob(section,latest.job,latest.results);
 for(const item of matches.slice(1)){const content=el('div');renderFailureAnalysisJob(content,item.job,item.results);section.append(viewerDisclosure('failure-analysis-case:'+DATA.batch.name+':'+phase+':'+row.sample.id+':'+(variant||'ANSWER')+':'+item.job.id,item.job.id+' · 이전 해석 기록',content,false));}
 parent.append(section);
}
