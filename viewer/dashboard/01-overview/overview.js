/* Read-only wallboard for preserved experiment responses. No model requests. */
(() => {
  'use strict';
  const promptName = value => ({ P0: 'Unguided Solving', P1: 'Criteria-Guided Solving' })[value] || value || '미기록';
  const reasoningName = value => ({ off: 'Reasoning OFF', on: 'Reasoning ON' })[value] || value || '미기록';
  const API = '/api/dashboard/data';
  const VARIANTS = [
    ['ORIGINAL','원문','원문'], ['IC_VALUE_01_BEFORE','값 충돌 · 앞','값 충돌 앞'],
    ['IC_VALUE_01_AFTER','값 충돌 · 뒤','값 충돌 뒤'], ['IC_SOURCE_A_ONLY','출처 A','출처 A'],
    ['IC_SOURCE_B_ONLY','출처 B','출처 B'], ['IC_RELATION_01','관계 모순','관계 모순'],
    ['EA_01','근거 삭제 · 01','근거 삭제 01'], ['EA_02','근거 삭제 · 02','근거 삭제 02'],
  ];
  const frameStyle = getComputedStyle(document.documentElement);
  const COLORS = {P0:frameStyle.getPropertyValue('--blue').trim(),P1:frameStyle.getPropertyValue('--teal').trim(),fail:frameStyle.getPropertyValue('--red').trim(),muted:'#a5b4bf'};
  const TAGS = {quote:'EVIDENCE_NOT_EXACT_SUBSTRING',contradiction:'DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER'};
  const $ = id => document.getElementById(id);
  const num = v => typeof v === 'number' && Number.isFinite(v);
  const nf = new Intl.NumberFormat('ko-KR');
  const count = v => num(v) ? nf.format(v) : '—';
  const escape = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label = (v,short=false) => VARIANTS.find(x=>x[0]===v)?.[short?2:1] || v || '미확인';
  const pct = (a,b,d=1) => b>0 && num(a) ? `${(100*a/b).toFixed(d)}%` : '—';
  const hasTag = (r,t) => Array.isArray(r.tags) && r.tags.includes(t);
  const ended = r => num(r.timing?.ended_epoch_ms) ? r.timing.ended_epoch_ms : null;
  const latency = r => num(r.metrics?.elapsed_seconds) && r.metrics.elapsed_seconds>=0 ? r.metrics.elapsed_seconds : null;
  const failed = r => r.saved_status === 'INVALID_RESPONSE';
  const groupKey = r => [r.variant,r.prompt_condition,r.reasoning].join('|');
  const state = {data:null,rows:[],reason:'all',prompt:'all',variant:'all',status:'all',selectedIds:null,focusId:null,points:[],drag:null,sort:'ended',direction:1,page:0,pageSize:40,tableMode:'all',heatMetric:'format',contrastReason:'off',pending:false,lastFocus:null};
  const timeFmt = new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  const minuteFmt = new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  const dateFmt = new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  function time(v,minute=false) {return num(v)?(minute?minuteFmt:timeFmt).format(new Date(v)):'미확인';}
  function date(v) {const ms=typeof v==='string'?Date.parse(v):v;return num(ms)?dateFmt.format(new Date(ms))+' KST':'시각 미확인';}
  function quantile(values,q) {
    const a=values.filter(num).sort((x,y)=>x-y);
    if(!a.length)return null;
    const position=(a.length-1)*q, lower=Math.floor(position);
    return a[lower]+(a[Math.ceil(position)]-a[lower])*(position-lower);
  }
  function filterRows(rows,filters) {
    return rows.filter(r=>(filters.reason==='all'||r.reasoning===filters.reason)&&(filters.prompt==='all'||r.prompt_condition===filters.prompt)&&(filters.variant==='all'||r.variant===filters.variant)&&(filters.status==='all'||r.saved_status===filters.status));
  }
  function aggregate(rows) {
    const durations=rows.map(latency).filter(num),costs=rows.map(r=>r.metrics?.cost_estimate_usd).filter(num);
    return {n:rows.length,valid:rows.filter(r=>r.saved_status==='VALID').length,invalid:rows.filter(failed).length,nulls:rows.filter(r=>r.answer_is_null===true).length,nullUnknown:rows.filter(r=>typeof r.answer_is_null!=='boolean').length,quote:rows.filter(r=>hasTag(r,TAGS.quote)).length,contradiction:rows.filter(r=>hasTag(r,TAGS.contradiction)).length,p50:quantile(durations,.5),p95:quantile(durations,.95),latencyN:durations.length,cost:costs.length?costs.reduce((a,b)=>a+b,0):null,costN:costs.length};
  }
  function makeGroups(rows) {
    const groups=new Map();
    for(const row of rows){const key=groupKey(row);if(!groups.has(key))groups.set(key,{key,variant:row.variant,prompt_condition:row.prompt_condition,reasoning:row.reasoning,rows:[]});groups.get(key).rows.push(row);}
    return [...groups.values()].map(g=>({...g,...aggregate(g.rows)}));
  }
  function completionTraffic(rows) {
    const valid=rows.filter(r=>ended(r)!==null),times=valid.map(ended);
    if(!valid.length)return {buckets:[],n:0,missing:rows.length,start:null,end:null,spanSeconds:null,rate:null};
    const start=Math.min(...times),end=Math.max(...times),first=Math.floor(start/60000)*60000,last=Math.floor(end/60000)*60000;
    const bins=new Map();
    for(const r of valid){const m=Math.floor(ended(r)/60000)*60000;if(!bins.has(m))bins.set(m,{minute:m,n:0,invalid:0});const bin=bins.get(m);bin.n++;if(failed(r))bin.invalid++;}
    const buckets=[];
    // Zero buckets represent actual empty minutes inside the observed interval.
    if((last-first)/60000<2000){for(let m=first;m<=last;m+=60000)buckets.push(bins.get(m)||{minute:m,n:0,invalid:0});}
    else buckets.push(...[...bins.values()].sort((a,b)=>a.minute-b.minute));
    return {buckets,n:valid.length,missing:rows.length-valid.length,start,end,spanSeconds:(end-start)/1000,rate:end>start?valid.length/((end-start)/1000):null};
  }
  function pairedNull(rows,variant,reason) {
    const cases=new Map();
    for(const r of rows){if(r.variant!==variant||r.reasoning!==reason)continue;const key=r.case;if(!cases.has(key))cases.set(key,{});cases.get(key)[r.prompt_condition]=r;}
    const pairs=[...cases.values()].filter(p=>p.P0&&p.P1);
    const known=pairs.filter(p=>typeof p.P0.answer_is_null==='boolean'&&typeof p.P1.answer_is_null==='boolean');
    const p0=known.filter(p=>p.P0.answer_is_null===true).length,p1=known.filter(p=>p.P1.answer_is_null===true).length;
    return {n:known.length,pairs:pairs.length,unknown:pairs.length-known.length,p0,p1,delta:known.length?100*(p1-p0)/known.length:null};
  }
  function selectedRows(rows,ids,mode='all') {return rows.filter(r=>(!ids||ids.has(r.trial_id))&&(mode!=='fail'||failed(r)));}
  function selectInBox(points,box) {const left=Math.min(box.x0,box.x1),right=Math.max(box.x0,box.x1),top=Math.min(box.y0,box.y1),bottom=Math.max(box.y0,box.y1);return new Set(points.filter(p=>p.x>=left&&p.x<=right&&p.y>=top&&p.y<=bottom).map(p=>p.row.trial_id));}
  function explorerUrl(row=null) {
    const params=new URLSearchParams(),fields=row?{variant:row.variant,prompt:row.prompt_condition,reasoning:row.reasoning,trial:row.trial_id}:{variant:state.variant,prompt:state.prompt,reasoning:state.reason};
    for(const[k,v]of Object.entries(fields))if(v&&v!=='all')params.set(k,v);
    return '/dashboard/02-explorer/'+(params.size?'?'+params:'');
  }
  function reportUrl(doc) {return 'http://127.0.0.1:8893/?'+new URLSearchParams({run:'20260923-experiment-improvement',doc:'reports/run/20260923-experiment-improvement/'+doc});}
  function announce(text) {$('announcer').textContent=text;}
  function updateQuery() {const u=new URL(location.href);for(const[k,v]of Object.entries({reasoning:state.reason,prompt:state.prompt,variant:state.variant,status:state.status})){if(v==='all')u.searchParams.delete(k);else u.searchParams.set(k,v);}history.replaceState(null,'',u);}
  function applyFilters(fields) {
    Object.assign(state,fields);state.selectedIds=null;state.focusId=null;state.page=0;
    if(state.reason!=='all')state.contrastReason=state.reason;
    $('reason-filter').value=state.reason;$('prompt-filter').value=state.prompt;$('variant-filter').value=state.variant;$('status-filter').value=state.status;$('contrast-reason').value=state.contrastReason;
    updateQuery();render();
  }
  function renderKpis() {
    const a=aggregate(state.rows),n=a.n,total=state.data.rows.length;
    const cards=[
      ['저장 응답',count(n),'건',`${count(total)}건 중<br>${pct(n,total)}`,'blue'],
      ['형식 실패',n?count(a.invalid):'—','건',`${count(a.invalid)} / ${count(n)}<br>${pct(a.invalid,n)}`,'red'],
      ['응답 시간 P50',num(a.p50)?a.p50.toFixed(2):'—','초',`${count(a.latencyN)}건 관찰<br>중앙값`,'blue'],
      ['응답 시간 P95',num(a.p95)?a.p95.toFixed(2):'—','초',`${count(a.latencyN)}건 관찰<br>95백분위`,'blue'],
      ['숫자 답 없음',n?count(a.nulls):'—','건',`${count(a.nulls)} / ${count(n)}<br>${pct(a.nulls,n)}`,'teal'],
      ['토큰 비용 추정',num(a.cost)?'$'+a.cost.toFixed(2):'—','',`${count(a.costN)}건 합산<br>실청구 미확인`,''],
    ];
    $('kpis').innerHTML=cards.map(([title,value,unit,sub,color])=>`<article class="kpi ${color}" title="${escape(title)} · ${sub.replace(/<br>/g,' · ')}"><h2>${title}</h2><p class="number">${value}<small>${unit}</small></p><p class="sub">${sub}</p></article>`).join('');
    $('filter-count').innerHTML=`<strong>${count(n)}</strong> / ${count(total)}건`;
  }
  function renderStatus() {
    const a=aggregate(state.rows),other=a.n-a.valid-a.invalid,circ=2*Math.PI*37;
    const segments=[{n:a.valid,c:COLORS.P1},{n:a.invalid,c:COLORS.fail},{n:other,c:COLORS.muted}];let offset=0;
    $('status-donut').innerHTML=`<title>전체 ${count(a.n)}건: 형식 통과 ${count(a.valid)}, 실패 ${count(a.invalid)}, 기타 ${count(other)}</title><circle cx="53" cy="53" r="37" fill="none" stroke="#edf2f5" stroke-width="9"/>`+segments.filter(s=>s.n>0).map(s=>{const len=a.n?circ*s.n/a.n:0;const path=`<circle cx="53" cy="53" r="37" fill="none" stroke="${s.c}" stroke-width="9" stroke-dasharray="${len} ${circ-len}" stroke-dashoffset="${-offset}" transform="rotate(-90 53 53)"/>`;offset+=len;return path;}).join('')+`<text x="53" y="51" text-anchor="middle" fill="#415f75" font-size="17" font-weight="600">${a.n?pct(a.valid,a.n,1):'—'}</text><text x="53" y="65" text-anchor="middle" fill="#96a6b1" font-size="8">형식 통과</text>`;
    $('status-denominator').textContent=`분모 ${count(a.n)}건`;
    $('status-counts').innerHTML=`<p><i class="p1"></i>통과<strong>${count(a.valid)}</strong><small>${pct(a.valid,a.n)}</small></p><p><i class="fail"></i>실패<strong>${count(a.invalid)}</strong><small>${pct(a.invalid,a.n)}</small></p>${other?`<p>기타<strong>${count(other)}</strong><small>${pct(other,a.n)}</small></p>`:''}`;
    $('observation-counts').innerHTML=[['상태·값 모순',a.contradiction,'유보 상태 선언과 숫자 답이 함께 있는 응답'],['인용 문자 불일치',a.quote,'원응답 인용이 입력의 정확한 부분 문자열과 다른 응답'],['숫자 답 없음',a.nulls,'answer_is_null이 true인 응답']].map(([t,n,desc])=>`<div class="observation" title="${desc}: ${count(n)} / ${count(a.n)}건 · 관찰은 중복될 수 있음"><span>${t}</span><strong>${count(n)}</strong></div>`).join('');
    $('condition-bars').innerHTML=['P0','P1'].flatMap(p=>['off','on'].map(r=>{const rows=state.rows.filter(x=>x.prompt_condition===p&&x.reasoning===r),g=aggregate(rows);return `<button type="button" class="condition-bar" data-prompt="${p}" data-reason="${r}" title="${promptName(p)} · ${reasoningName(r)}: 통과 ${g.valid} / ${g.n}건, 형식 실패 ${g.invalid}건. 클릭하여 필터"><span>${promptName(p)}<br>${reasoningName(r)}</span><span class="condition-track"><i class="valid" style="width:${g.n?100*g.valid/g.n:0}%"></i><i class="invalid" style="width:${g.n?100*g.invalid/g.n:0}%"></i></span><span class="n">${count(g.valid)}/${count(g.n)}</span></button>`;})).join('');
  }
  function renderTraffic() {
    const t=completionTraffic(state.rows),svg=$('traffic-chart');
    $('traffic-rate').textContent=num(t.rate)?t.rate.toFixed(2):'—';
    $('traffic-rate').title=t.n?`${count(t.n)}건 ÷ 첫 완료~마지막 완료 ${t.spanSeconds.toFixed(0)}초. 실험 전체 벽시계 시간이 아닙니다.`:'유효 완료 시각 없음';
    if(!t.buckets.length){svg.innerHTML='<text x="125" y="65" text-anchor="middle" fill="#9daab4" font-size="11">완료 시각 없음</text>';$('traffic-meta').textContent=`유효 0 / ${count(state.rows.length)}건`;return;}
    const w=250,h=128,left=35,right=7,top=13,bottom=24,plotW=w-left-right,plotH=h-top-bottom,max=Math.max(...t.buckets.map(b=>b.n),1),step=plotW/t.buckets.length,bw=Math.max(1,step*.54);
    let out=`<title>완료 건수/분. ${t.buckets.map(b=>time(b.minute,true)+' '+b.n+'건').join(', ')}. 버킷 합계 ${t.n}건.</title>`;
    for(let i=0;i<=2;i++){const v=max*i/2,y=top+plotH-plotH*i/2;out+=`<line x1="${left}" y1="${y}" x2="${w-right}" y2="${y}" stroke="#e8eef2"/><text x="${left-5}" y="${y+3}" text-anchor="end" font-size="8" fill="#9aadb9">${Math.round(v)}</text>`;}
    t.buckets.forEach((b,i)=>{const x=left+step*i+(step-bw)/2,y=top+plotH-b.n/max*plotH,hh=b.n/max*plotH,fh=b.invalid/max*plotH;out+=`<rect x="${x}" y="${y}" width="${bw}" height="${hh}" rx="1" fill="#5a9dcb"><title>${time(b.minute,true)}: 완료 ${b.n}건 / 그중 형식 실패 ${b.invalid}건</title></rect><rect x="${x}" y="${top+plotH-fh}" width="${bw}" height="${fh}" fill="${COLORS.fail}"/>`;if(t.buckets.length<9||i%Math.ceil(t.buckets.length/5)===0)out+=`<text x="${x+bw/2}" y="${h-8}" text-anchor="middle" font-size="8" fill="#8fa2b0">${time(b.minute,true)}</text>`;});
    svg.innerHTML=out;
    $('traffic-meta').textContent=`${count(t.n)}건 · ${count(t.buckets.length)}분 버킷 · KST${t.missing?' · 시각 결측 '+count(t.missing):''}`;
  }
  function renderHeatmap() {
    const groups=new Map(makeGroups(state.rows).map(g=>[g.key,g]));
    let html='<span class="heat-col">유형</span>'+['P0','P1'].flatMap(p=>['off','on'].map(r=>`${promptName(p)}<br>${reasoningName(r)}`)).map(x=>`<span class="heat-col">${x}</span>`).join('');
    for(const[v,,short]of VARIANTS){html+=`<span class="heat-label">${short}</span>`;for(const p of ['P0','P1'])for(const r of ['off','on']){const g=groups.get([v,p,r].join('|')),value=g?(state.heatMetric==='null'?g.nulls:g.invalid):null,rate=g?value/g.n:null,observed=g&&state.heatMetric==='null'?g.n-g.nullUnknown:g?.n;const title=g?`${label(v)} / ${promptName(p)} / ${reasoningName(r)}: ${state.heatMetric==='null'?'숫자 없음':'형식 실패'} ${value} / ${g.n}건 (${pct(value,g.n)})${observed!==g.n?' · 관찰 미확인 '+(g.n-observed)+'건':''}`:`${label(v)} / ${promptName(p)} / ${reasoningName(r)}: ${v==='ORIGINAL'&&p==='P1'?'계획 없음':'선택 조건에 응답 없음'}`;const color=state.heatMetric==='null'?`rgba(15,154,141,${.07+.72*(rate||0)})`:`rgba(223,85,91,${.06+.8*(rate||0)})`;html+=`<button type="button" class="heat-cell${!g?' na':''}" ${!g?'disabled':''} data-variant="${v}" data-prompt="${p}" data-reason="${r}" title="${escape(title)}" aria-label="${escape(title)}" style="${g?'background:'+color+';color:'+(rate>.5?'#fff':'#547184'):''}">${g?(100*rate).toFixed(0)+'%':'—'}</button>`;}}
    $('heatmap').innerHTML=html;$('heat-scale').querySelector('i').style.background=state.heatMetric==='null'?'linear-gradient(90deg,#edf8f6,#0f9a8d)':'linear-gradient(90deg,#f9e9e9,#d7555d)';
  }
  function renderContrasts() {
    const reason=state.contrastReason;
    let complete=0;
    $('null-contrasts').innerHTML=VARIANTS.slice(1).map(([v,,short])=>{const p=pairedNull(state.rows,v,reason),x0=p.n?100*p.p0/p.n:0,x1=p.n?100*p.p1/p.n:0;complete+=p.n;const title=`${label(v)} / ${reasoningName(reason)}: ${p.n?`Unguided Solving ${p.p0}/${p.n} (${pct(p.p0,p.n)}), Criteria-Guided Solving ${p.p1}/${p.n} (${pct(p.p1,p.n)}), 변화 ${p.delta>0?'+':''}${p.delta.toFixed(1)}%p`:'선택 조건에 비교 가능한 두 풀이 조건의 쌍 없음'}`;return `<div class="null-row${p.n?'':' filtered'}" title="${escape(title)}"><button type="button" class="null-name" data-variant="${v}" aria-label="${escape(title)} · 이 유형 필터">${short}</button><div class="null-plot"><span class="null-line"></span>${p.n?`<span class="null-range" style="left:${Math.min(x0,x1)}%;width:${Math.abs(x1-x0)}%"></span><button type="button" class="null-dot" style="left:${x0}%" data-variant="${v}" data-prompt="P0" aria-label="${label(v)} Unguided Solving 숫자 없음 ${p.p0}/${p.n}건"></button><button type="button" class="null-dot p1" style="left:${x1}%" data-variant="${v}" data-prompt="P1" aria-label="${label(v)} Criteria-Guided Solving 숫자 없음 ${p.p1}/${p.n}건"></button>`:''}</div><span class="null-delta">${p.n?(p.delta>0?'+':'')+p.delta.toFixed(0):'—'}</span></div>`;}).join('');
    $('contrast-note').textContent=complete?`${reasoningName(reason)} · ${count(complete)}쌍 · 의미 적절성 미평가`:'두 풀이 조건이 모두 포함된 범위에서 비교';
  }
  function renderTable() {
    const rows=selectedRows(state.rows,state.selectedIds,state.tableMode),field=state.sort==='latency'?latency:ended;
    rows.sort((a,b)=>{const av=field(a),bv=field(b);if(av===null&&bv!==null)return 1;if(bv===null&&av!==null)return -1;return ((av??0)-(bv??0))*state.direction||a.trial_id.localeCompare(b.trial_id);});
    const pages=Math.max(1,Math.ceil(rows.length/state.pageSize));state.page=Math.min(Math.max(0,state.page),pages-1);
    const current=rows.slice(state.page*state.pageSize,(state.page+1)*state.pageSize);
    $('response-body').innerHTML=current.length?current.map(r=>`<tr data-trial="${r.trial_id}" class="${state.focusId===r.trial_id?'focused':''}"><td><button type="button" class="case-button" data-trial="${r.trial_id}" title="원응답과 질문 열기">${escape(r.case)}<small>${escape(label(r.variant,true))} · ${promptName(r.prompt_condition)} · ${reasoningName(r.reasoning)}</small></button></td><td>${time(ended(r))}</td><td>${latency(r)!==null?latency(r).toFixed(2):'—'}</td><td><span class="row-status${failed(r)?' failed':r.saved_status==='VALID'?'':' unknown'}" title="${escape(r.saved_status)}">${failed(r)?'실패':r.saved_status==='VALID'?'통과':'미확인'}</span></td><td><a href="${explorerUrl(r)}" aria-label="${escape(r.case)} ${escape(label(r.variant))} ${promptName(r.prompt_condition)} ${reasoningName(r.reasoning)} 문항 분석">↗</a></td></tr>`).join(''):'<tr><td colspan="5" class="empty-cell">선택한 조건에 응답이 없습니다.<br>영역 선택 해제 또는 필터 초기화를 이용하세요.</td></tr>';
    $('response-count').textContent=count(rows.length)+'건';$('page-label').textContent=`${state.page+1} / ${pages}`;$('prev-page').disabled=state.page===0;$('next-page').disabled=state.page>=pages-1;
    $('table-selection').textContent=`${state.selectedIds?'영역/점 '+count(state.selectedIds.size)+'건':'조건 전체'}${state.tableMode==='fail'?' · 형식 실패만':''}`;
    $('sort-ended').removeAttribute('aria-sort');$('sort-latency').removeAttribute('aria-sort');$('sort-'+state.sort).setAttribute('aria-sort',state.direction===1?'ascending':'descending');
    $('table-all').classList.toggle('active',state.tableMode==='all');$('table-fail').classList.toggle('active',state.tableMode==='fail');$('table-all').setAttribute('aria-pressed',state.tableMode==='all');$('table-fail').setAttribute('aria-pressed',state.tableMode==='fail');
    const focused=state.rows.find(r=>r.trial_id===state.focusId)||(state.selectedIds?.size===1?rows[0]:null);
    $('table-explorer').href=explorerUrl(focused);$('selected-explorer').href=explorerUrl(focused);
    $('clear-selection').disabled=!state.selectedIds;$('selection-status').textContent=state.selectedIds?`${count(state.selectedIds.size)} / ${count(state.rows.length)}건 선택 → 연결 표`:'점 클릭 / 영역 드래그 → 아래 응답 표';
  }
  function drawXview() {
    const canvas=$('xview'),box=$('xview-wrap').getBoundingClientRect(),w=box.width,h=box.height;
    if(w<1||h<1)return;
    const dpr=Math.min(window.devicePixelRatio||1,3);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    const valid=state.rows.filter(r=>ended(r)!==null&&latency(r)!==null),left=47,right=17,top=22,bottom=28,pw=Math.max(1,w-left-right),ph=Math.max(1,h-top-bottom);
    state.points=[];$('xview-empty').hidden=valid.length>0;$('xview-empty').textContent='선택 조건에 완료 시각과 응답 시간이 함께 있는 응답이 없습니다.';
    $('xview-meta').textContent=`시각·시간 유효 ${count(valid.length)} / ${count(state.rows.length)}건 · KST`;
    ctx.font=`9px ${frameStyle.fontFamily}`;ctx.fillStyle='#8ca1b0';ctx.textAlign='left';ctx.fillText('응답 시간 (초)',8,12);
    if(!valid.length)return;
    const ends=valid.map(ended),start=Math.min(...ends),finish=Math.max(...ends),xmin=start===finish?start-1000:start,xmax=start===finish?finish+1000:finish,maxLatency=Math.max(...valid.map(latency)),rawY=Math.max(maxLatency,1),magnitude=Math.pow(10,Math.floor(Math.log10(rawY))),ymax=Math.ceil(rawY/magnitude*2)/2*magnitude;
    ctx.lineWidth=1;
    for(let i=0;i<=4;i++){const y=top+ph-ph*i/4;ctx.strokeStyle='#e8eef2';ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right,y);ctx.stroke();ctx.textAlign='right';ctx.fillStyle='#90a3b0';ctx.fillText((ymax*i/4).toFixed(ymax<10?1:0),left-7,y+3);}
    const ticks=w<550?3:5;
    for(let i=0;i<ticks;i++){const x=left+pw*i/(ticks-1);ctx.strokeStyle='#f0f3f6';ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,h-bottom);ctx.stroke();ctx.textAlign=i===0?'left':i===ticks-1?'right':'center';ctx.fillStyle='#90a3b0';ctx.fillText(time(xmin+(xmax-xmin)*i/(ticks-1)),x,h-10);}
    state.points=valid.map(row=>({row,x:left+(ended(row)-xmin)/(xmax-xmin)*pw,y:top+ph-latency(row)/ymax*ph}));
    const ordered=[...state.points].sort((a,b)=>Number(failed(a.row))-Number(failed(b.row)));
    for(const p of ordered){const isSelected=!state.selectedIds||state.selectedIds.has(p.row.trial_id);ctx.globalAlpha=isSelected?(failed(p.row)?.87:.5):.1;ctx.fillStyle=failed(p.row)?COLORS.fail:COLORS[p.row.prompt_condition]||COLORS.muted;ctx.beginPath();ctx.arc(p.x,p.y,failed(p.row)?2:1.8,0,Math.PI*2);ctx.fill();}
    ctx.globalAlpha=1;
    const focus=state.points.find(p=>p.row.trial_id===state.focusId);if(focus){ctx.strokeStyle='#173f59';ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(focus.x,focus.y,5,0,Math.PI*2);ctx.stroke();}
    if(state.drag){const b=state.drag;ctx.fillStyle='#248bb719';ctx.strokeStyle='#288db7';ctx.lineWidth=1;ctx.setLineDash([4,3]);ctx.fillRect(b.x0,b.y0,b.x1-b.x0,b.y1-b.y0);ctx.strokeRect(b.x0,b.y0,b.x1-b.x0,b.y1-b.y0);ctx.setLineDash([]);}
    canvas.setAttribute('aria-label',`완료 시각과 응답 시간 산점도. ${valid.length}/${state.rows.length}건 표시. KST ${time(start)}~${time(finish)}. 좌우 방향키 탐색, Enter 선택. 모든 응답은 연결 표에서도 접근할 수 있습니다.`);
  }
  function setSelection(ids,focusId=null) {state.selectedIds=ids;state.focusId=focusId;state.page=0;renderTable();drawXview();announce(ids?`${ids.size}개 응답 선택. 아래 연결 표에 표시합니다.`:'선택을 해제했습니다.');}
  function nearestPoint(x,y,radius=9) {let nearest=null,distance=radius*radius;for(const p of state.points){const d=(p.x-x)**2+(p.y-y)**2;if(d<=distance){nearest=p;distance=d;}}return nearest;}
  function pointerPosition(e) {const b=$('xview').getBoundingClientRect();return{x:e.clientX-b.left,y:e.clientY-b.top};}
  function showTooltip(point,clientX,clientY) {
    const el=$('chart-tooltip');if(!point){el.hidden=true;return;}
    const r=point.row;el.innerHTML=`<strong>${escape(r.case)} · ${escape(label(r.variant))}</strong><span>${promptName(r.prompt_condition)} / ${reasoningName(r.reasoning)}</span><br>완료 ${time(ended(r))} KST · 응답 ${latency(r).toFixed(3)}초<br>${failed(r)?'형식 실패':r.saved_status==='VALID'?'형식 통과':'상태 미확인'} · ${r.answer_is_null===true?'숫자 없음':r.answer_is_null===false?'숫자 있음':'답 관찰 미확인'}<br><span>클릭하여 연결 표에서 응답 확인</span>`;el.hidden=false;el.style.left=Math.min(clientX+12,window.innerWidth-el.offsetWidth-10)+'px';el.style.top=Math.min(clientY+12,window.innerHeight-el.offsetHeight-10)+'px';
  }
  function renderSnapshot() {
    const d=state.data,e=d.execution||{},a=d.a100||{},originals=new Set(d.rows.map(r=>r.case)).size;
    $('run-label').textContent=d.run_id;$('run-facts').textContent=`${d.model||'모델 미확인'} · ${originals}원문 / ${new Set(d.rows.filter(r=>r.variant!=='ORIGINAL').map(r=>r.item_id)).size}변형`;
    const t=completionTraffic(d.rows);$('time-window').textContent=t.n?`${date(t.start).split(' ').slice(0,3).join(' ')} ${time(t.start)}–${time(t.end)} KST`:'완료 시각 미확인';
    const attempts=num(e.provider_request_attempts)?e.provider_request_attempts:e.experiment_request_attempts,success=e.successful_responses;
    $('execution-copy').textContent=`신규 실행 ${e.improved_run_id||'미확인'} · API 시도 ${count(attempts)} / 성공 ${count(success)} · ${e.phase==='API_CREDIT_BALANCE_EXHAUSTED'?'API 크레딧 부족':e.phase||'상태 미확인'} · 위 통계는 기존 수집본`;
    $('execution-copy').title=`저장 상태 ${date(e.updated_at)} · 변경 응답 형식의 개선 효과 미평가`;
    const recorded=Array.isArray(a.models)?a.models.reduce((n,m)=>n+(num(m.recorded)?m.recorded:0),0):null;
    $('a100-mini').textContent=`${count(recorded)} / ${count(a.planned)}`;$('a100-button').title=`${date(a.snapshot_at||a.updated_at)} 저장본 · 현재 상태 미조회`;
    $('source-note').textContent=`SOURCE ${d.source_run||d.run_id} · 읽은 시각 ${date(d.generated_at)}`;$('source-note').title=`${d.source_run||''} · API /api/dashboard/data · 저장 당시 기존 응답 형식 기준. 변경 응답 형식 효과 미평가.`;
    if(/^\d{8}-exp-\d{3,}$/.test(d.run_id||''))$('experiment-viewer-link').href=`http://127.0.0.1:8894/?run=${encodeURIComponent(d.run_id)}&tab=analysis`;
    $('baseline-report').href=reportUrl('01-baseline/analysis.md');$('execution-report').href=reportUrl('REPORT.md');
  }
  function render() {if(!state.data)return;state.rows=filterRows(state.data.rows,state);renderKpis();renderStatus();renderTraffic();renderHeatmap();renderContrasts();renderTable();drawXview();}
  function openDrawer(title,html) {state.lastFocus=document.activeElement;$('drawer-title').textContent=title;$('drawer-body').innerHTML=html;$('detail-drawer').hidden=false;$('drawer-backdrop').hidden=false;$('main').inert=true;document.querySelector('.app-header').inert=true;$('close-drawer').focus();}
  function closeDrawer() {$('detail-drawer').hidden=true;$('drawer-backdrop').hidden=true;$('main').inert=false;document.querySelector('.app-header').inert=false;state.lastFocus?.focus();}
  function openResponse(trial) {const r=state.rows.find(x=>x.trial_id===trial);if(!r)return;state.focusId=trial;drawXview();renderTable();openDrawer(`${r.case} · ${label(r.variant)}`,`<p class="response-status">${promptName(r.prompt_condition)} · ${reasoningName(r.reasoning)} · ${r.saved_status==='VALID'?'형식 통과':failed(r)?'형식 실패':'상태 미확인'}<br>완료 ${date(ended(r))} · 응답 ${latency(r)!==null?latency(r).toFixed(3):'미확인'}초</p><h3>입력 질문</h3><p>${escape(r.question_preview||'질문 미확인')}</p><h3>보존된 모델 응답</h3><pre>${escape(JSON.stringify(r.response,null,2)||'원응답 미관찰')}</pre><h3>기록된 관찰</h3><p>${r.answer_is_null===true?'숫자 답 없음':r.answer_is_null===false?'숫자 답 있음':'숫자 답 관찰 미확인'} · ${hasTag(r,TAGS.quote)?'인용 문자 불일치 있음':'인용 문자 불일치 태그 없음'}<br>의미 정답 및 유보 적절성은 이 화면에서 평가하지 않습니다.</p><p><a href="${explorerUrl(r)}">이 응답을 문항 분석에서 열기 ↗</a></p><p class="muted">${escape(r.raw_path)}<br>trial ${escape(r.trial_id)}</p>`);}
  function openHelp() {openDrawer('지표와 읽는 방법',`<h3>실시간 운영 화면이 아닌 저장 기록 조회입니다</h3><p>기존 100원문·700변형에 대한 3,000요청의 저장 결과입니다. 신규 실행의 API 시도·성공 수는 별도 상태 줄에 표시하며 기존 수집본 통계에 더하지 않습니다.</p><h3>X-View와 연결 표</h3><p>가로축은 실제 완료 시각(KST), 세로축은 저장된 응답 시간(초)입니다. 같은 초의 점이 겹칠 수 있습니다. 점 클릭 또는 영역 드래그로 아래 응답 표를 선택합니다. 키보드 좌우 방향키로 점을 탐색하고 Enter로 선택할 수 있습니다. 시각이나 응답 시간이 없는 행은 산점도에서만 빠지며 전체 분모와 표에 남습니다.</p><h3>트래픽 / 지연 시간</h3><p>막대는 절대 시각의 1분 버킷별 완료 건수입니다. 붉은 부분은 그중 형식 실패입니다. 평균 건/초는 유효 완료 건수 ÷ 첫 완료~마지막 완료 간격이며 전체 실험 소요 시간이 아닙니다. P50/P95는 관찰된 응답 시간을 정렬하여 (n−1)×백분위 위치를 선형보간합니다.</p><h3>형식과 의미를 구분합니다</h3><p>통과·실패는 저장 당시 <b>기존 응답 형식</b>의 검사 결과입니다. 상태·값 모순과 인용 문자 불일치는 원응답의 별도 관찰이며 서로 중복될 수 있습니다. 숫자 없음은 실제 관찰된 answer의 null 여부이고, 적절한 유보를 뜻하지 않습니다. <b>의미 정답·반복 안정성·변경 응답 형식의 개선 효과는 미평가</b>입니다.</p><h3>필터와 쌍 비교</h3><p>상단 필터는 모든 패널에 적용합니다. 산점도 선택과 표의 실패 버튼은 연결 표 범위만 바꿉니다. Unguided Solving → Criteria-Guided Solving 비교는 같은 원문·유형·추론의 두 응답 모두가 필터에 포함되고 null 여부가 관찰된 쌍에 한해 계산합니다. 쌍이 없으면 대시(—)로 표시합니다.</p><h3>분모와 비용</h3><p>비율은 필터에 해당하는 저장 요청 행을 분모로 유지합니다. 결측은 0으로 바꾸지 않습니다. 토큰 비용은 저장된 요청별 추정액 합이며 실제 청구액은 미확인입니다. A100은 별도의 1,080원문·7,560변형 집단이며 저장 당시 상태만 제공합니다.</p><p><a href="${reportUrl('01-baseline/analysis.md')}" target="_blank" rel="noopener">실제 관찰 근거 보고서 ↗</a></p>`);}
  function openA100() {const a=state.data?.a100;if(!a){openDrawer('A100 저장본','<p>저장된 요약이 없습니다.</p>');return;}const models=Array.isArray(a.models)?a.models:[],recorded=models.reduce((n,m)=>n+(num(m.recorded)?m.recorded:0),0);openDrawer('A100 · 별도 집단의 저장 요약',`<p class="muted">저장 시각 ${date(a.snapshot_at||a.updated_at)}<br>현재 원격 실행 상태는 조회하지 않았습니다.</p><p class="drawer-kpi">${count(recorded)} <small>/ ${count(a.planned)}</small></p><p>${count(a.originals)}원문 · ${count(a.variants)}변형. Luna 100원문 집단과 통계 분모를 합치지 않습니다.</p><table><thead><tr><th>모델</th><th>저장 / 계획</th><th>저장 당시</th></tr></thead><tbody>${models.map(m=>`<tr><td>${escape(m.key||m.model)}</td><td>${count(m.recorded)} / ${count(m.planned)}</td><td>${escape(({COMPLETED:'완료',RUNNING:'진행 중',NOT_EXECUTABLE:'실행 불가'})[m.status]||m.status||'미확인')}</td></tr>`).join('')}</tbody></table><p class="muted">저장 당시 RUNNING 표기는 현재 실행 중이라는 뜻이 아닙니다. 금융 모델 실행 가능 여부와 비교 집단은 별도 검토 대상입니다.</p>`);}
  async function loadData(refresh=false) {
    if(state.pending)return;state.pending=true;$('refresh').disabled=true;$('main').setAttribute('aria-busy','true');$('loading-state').hidden=false;$('error-state').hidden=true;
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),120000);
    try{const response=await fetch(API+(refresh?'?refresh=1':''),{cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();if(data.schema_version!==1||!Array.isArray(data.rows))throw new Error('지원하는 응답 목록 형식이 아닙니다.');state.data=data;state.selectedIds=null;state.focusId=null;state.page=0;renderSnapshot();render();announce(`${data.rows.length}개 저장 응답을 읽었습니다.`);}catch(error){$('error-copy').textContent=`${error.name==='AbortError'?'읽기 대기 시간을 초과했습니다.':error.message}\n보고서 서버와 실제 자료 경로를 확인한 뒤 다시 읽어 주세요.${state.data?' 기존 화면에는 마지막으로 읽은 자료가 남아 있습니다.':''}`;$('error-state').hidden=false;$('run-label').textContent=state.data?`${state.data.run_id} · 새로 읽기 실패`:'자료 연결 실패';}finally{clearTimeout(timeout);state.pending=false;$('refresh').disabled=false;$('main').setAttribute('aria-busy','false');$('loading-state').hidden=true;}
  }
  function init() {
    $('variant-filter').insertAdjacentHTML('beforeend',VARIANTS.map(([v,name])=>`<option value="${v}">${name}</option>`).join(''));
    const params=new URLSearchParams(location.search),allowed={reason:['all','off','on'],prompt:['all','P0','P1'],variant:['all',...VARIANTS.map(v=>v[0])],status:['all','VALID','INVALID_RESPONSE']};
    for(const[k,options]of Object.entries(allowed)){const value=params.get(k==='reason'?'reasoning':k);if(options.includes(value))state[k]=value;$(k+'-filter').value=state[k];$(k+'-filter').addEventListener('change',e=>applyFilters({[k]:e.target.value}));}
    if(state.reason!=='all')state.contrastReason=state.reason;$('contrast-reason').value=state.contrastReason;
    $('refresh').addEventListener('click',()=>loadData(true));$('retry').addEventListener('click',()=>loadData(true));$('reset').addEventListener('click',()=>{state.tableMode='all';state.contrastReason='off';applyFilters({reason:'all',prompt:'all',variant:'all',status:'all'});});
    $('clear-selection').addEventListener('click',()=>setSelection(null));$('heat-metric').addEventListener('change',e=>{state.heatMetric=e.target.value;renderHeatmap();});$('contrast-reason').addEventListener('change',e=>applyFilters({reason:e.target.value}));
    $('condition-bars').addEventListener('click',e=>{const b=e.target.closest('button[data-prompt]');if(b)applyFilters({prompt:b.dataset.prompt,reason:b.dataset.reason});});
    $('heatmap').addEventListener('click',e=>{const b=e.target.closest('button[data-variant]');if(b&&!b.disabled)applyFilters({variant:b.dataset.variant,prompt:b.dataset.prompt,reason:b.dataset.reason});});
    $('null-contrasts').addEventListener('click',e=>{const b=e.target.closest('button[data-variant]');if(b)applyFilters({variant:b.dataset.variant,...(b.dataset.prompt?{prompt:b.dataset.prompt}:{}),reason:state.contrastReason});});
    for(const mode of ['all','fail'])$('table-'+mode).addEventListener('click',()=>{state.tableMode=mode;state.page=0;renderTable();});
    document.querySelectorAll('[data-sort]').forEach(b=>b.addEventListener('click',()=>{if(state.sort===b.dataset.sort)state.direction*=-1;else{state.sort=b.dataset.sort;state.direction=1;}state.page=0;renderTable();}));
    $('prev-page').addEventListener('click',()=>{state.page--;renderTable();});$('next-page').addEventListener('click',()=>{state.page++;renderTable();});
    $('response-body').addEventListener('click',e=>{const b=e.target.closest('button[data-trial]');if(b)openResponse(b.dataset.trial);});$('response-body').addEventListener('focusin',e=>{const tr=e.target.closest('tr[data-trial]');if(tr){state.focusId=tr.dataset.trial;drawXview();}});
    $('help-button').addEventListener('click',openHelp);$('a100-button').addEventListener('click',openA100);$('close-drawer').addEventListener('click',closeDrawer);$('drawer-backdrop').addEventListener('click',closeDrawer);
    document.addEventListener('keydown',e=>{if($('detail-drawer').hidden)return;if(e.key==='Escape'){e.preventDefault();closeDrawer();}if(e.key==='Tab'){const items=[...$('detail-drawer').querySelectorAll('button,a[href],[tabindex="0"]')],first=items[0],last=items.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
    const canvas=$('xview');
    canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;const p=pointerPosition(e);state.drag={x0:p.x,y0:p.y,x1:p.x,y1:p.y};canvas.setPointerCapture(e.pointerId);$('chart-tooltip').hidden=true;});
    canvas.addEventListener('pointermove',e=>{const p=pointerPosition(e);if(state.drag){state.drag.x1=p.x;state.drag.y1=p.y;drawXview();}else showTooltip(nearestPoint(p.x,p.y),e.clientX,e.clientY);});
    canvas.addEventListener('pointerup',e=>{if(!state.drag)return;const p=pointerPosition(e),box={...state.drag,x1:p.x,y1:p.y};state.drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);if(Math.hypot(box.x1-box.x0,box.y1-box.y0)>5)setSelection(selectInBox(state.points,box));else{const hit=nearestPoint(p.x,p.y);if(hit)setSelection(new Set([hit.row.trial_id]),hit.row.trial_id);else drawXview();}});
    canvas.addEventListener('pointercancel',()=>{state.drag=null;drawXview();});canvas.addEventListener('pointerleave',()=>{$('chart-tooltip').hidden=true;});
    canvas.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Enter','Escape'].includes(e.key))return;e.preventDefault();if(e.key==='Escape'){setSelection(null);return;}const points=[...state.points].sort((a,b)=>ended(a.row)-ended(b.row)||a.row.trial_id.localeCompare(b.row.trial_id));if(!points.length)return;let index=points.findIndex(p=>p.row.trial_id===state.focusId);if(e.key==='Enter'){if(index<0)index=0;const row=points[index].row;setSelection(new Set([row.trial_id]),row.trial_id);return;}index=index<0?0:(index+(e.key==='ArrowRight'?1:-1)+points.length)%points.length;state.focusId=points[index].row.trial_id;const r=points[index].row;drawXview();announce(`${r.case} ${label(r.variant)} ${promptName(r.prompt_condition)} ${reasoningName(r.reasoning)}, 완료 ${time(ended(r))}, ${latency(r).toFixed(2)}초. Enter로 선택.`);});
    new ResizeObserver(()=>{if(state.data)drawXview();}).observe($('xview-wrap'));
    loadData();
  }
  init();
})();
