const label = {VERIFIED:'일치 확인',INPUTS_VERIFIED:'입력 일치·결과 확인 중',MISMATCH:'불일치',FAILED:'오류',CHECKING:'확인 중',NOT_CHECKED:'확인 기록 없음'};
const element = (tag,text,cls) => {const node=document.createElement(tag);node.textContent=text;if(cls)node.className=cls;return node;};
const number = value => value == null ? '미기록' : Number(value).toLocaleString(globalThis.FinarchI18n?.language === 'ko' ? 'ko-KR' : 'en-US');
let busy=false;
async function refresh(){
 if(busy)return;busy=true;
 try{
  const response=await fetch('/api/sync',{cache:'no-store'});if(!response.ok)throw new Error(`동기화 기록 조회 실패 (${response.status})`);
  const data=await response.json();
  const status=document.getElementById('notice');status.replaceChildren(element('p', data.stale?'최근 동기화 확인이 3분 이상 지났거나 확인 기록이 없습니다.':`최근 확인: ${label[data.status]||data.status}`,data.stale||data.status==='FAILED'?'notice danger':'notice info'));
  if(data.error)status.append(element('p',data.error,'notice danger'));
  const cards=document.getElementById('summary');cards.replaceChildren();
  for(const [title,value] of [['전체 상태',label[data.status]||data.status],['공통 코드',label[data.code?.status]||'미확인'],['연결된 실험',Object.keys(data.runs||{}).length],['새 모델 호출',data.new_model_calls==null?'미기록':data.new_model_calls]]){const card=element('div','','sync-card');card.append(element('span',title,'muted'),element('strong',String(value)));cards.append(card);}
  const rows=document.getElementById('runs');rows.replaceChildren();
  for(const [run,value] of Object.entries(data.runs||{})){const state=value.outputs?.remote_state||{};const tr=element('tr','');const td=element('td','');const a=element('a',run);a.href=`/?run=${encodeURIComponent(run)}&tab=progress`;td.append(a);tr.append(td);for(const text of [label[value.inputs?.status]||'미확인',state.status||'미기록',`${number(state.completed??state.attempt_records)} / ${number(state.total)}`,number(value.outputs?.files),number(value.outputs?.new_files),value.outputs?.at?new Date(value.outputs.at).toLocaleTimeString(globalThis.FinarchI18n?.language === 'ko' ? 'ko-KR' : 'en-US'):'미기록'])tr.append(element('td',text));rows.append(tr);}
  const details=document.getElementById('details');details.replaceChildren();for(const [title,text] of [['서버',data.host||'미기록'],['공통 경로',data.remote_workspace||'미기록'],['코드 SHA-256',data.code?.release||'미기록'],['코드 파일',number(data.code?.files)]])details.append(element('dt',title),element('dd',text));
  const diffs=['missing','changed','extra'].filter(key=>data.code?.[key]?.length).map(key=>`${key}:\n${data.code[key].slice(0,30).join('\n')}`);document.getElementById('mismatch').textContent=diffs.join('\n\n')||'기록된 코드 불일치 없음';
  document.getElementById('updated').textContent=`동기화 기록: ${data.updated_at?new Date(data.updated_at).toLocaleString(globalThis.FinarchI18n?.language === 'ko' ? 'ko-KR' : 'en-US'):'없음'} · 화면 확인: ${new Date().toLocaleTimeString(globalThis.FinarchI18n?.language === 'ko' ? 'ko-KR' : 'en-US')}`;
 }catch(error){document.getElementById('notice').replaceChildren(element('p',error.message,'notice danger'));}finally{busy=false;}
}
document.getElementById('refresh').addEventListener('click',refresh);setInterval(refresh,10000);refresh();
