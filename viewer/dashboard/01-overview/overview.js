/* Read-only wallboard for preserved experiment responses. No model requests. */
(() => {
  'use strict';
  const promptName = value => ({ P0: 'Unguided Solving', P1: 'Criteria-Guided Solving' })[value] || value || 'Not recorded';
  const reasoningName = value => ({ off: 'Reasoning OFF', on: 'Reasoning ON' })[value] || value || 'Not recorded';
  const API = '/api/dashboard/data';
  const VARIANTS = [
    ['ORIGINAL','Source text','Source text'], ['IC_VALUE_01_BEFORE','Value collision · front','Before the collision.'],
    ['IC_VALUE_01_AFTER','The value of the collapse','After the value collapse.'], ['IC_SOURCE_A_ONLY','Sources A','Sources A'],
    ['IC_SOURCE_B_ONLY','Sources B','Sources B'], ['IC_RELATION_01','Relationship contradictions','Relationship contradictions'],
    ['EA_01','Delete the evidence 01','Delete the basis 01'], ['EA_02','Delete the evidence 02','Delete the basis 02'],
  ];
  const frameStyle = getComputedStyle(document.documentElement);
  const COLORS = {P0:frameStyle.getPropertyValue('--blue').trim(),P1:frameStyle.getPropertyValue('--teal').trim(),fail:frameStyle.getPropertyValue('--red').trim(),muted:'#a5b4bf'};
  const TAGS = {quote:'EVIDENCE_NOT_EXACT_SUBSTRING',contradiction:'DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER'};
  const $ = id => document.getElementById(id);
  const num = v => typeof v === 'number' && Number.isFinite(v);
  const nf = new Intl.NumberFormat('en-US');
  const count = v => num(v) ? nf.format(v) : '—';
  const escape = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label = (v,short=false) => VARIANTS.find(x=>x[0]===v)?.[short?2:1] || v || 'Unconfirmed';
  const pct = (a,b,d=1) => b>0 && num(a) ? `${(100*a/b).toFixed(d)}%` : '—';
  const hasTag = (r,t) => Array.isArray(r.tags) && r.tags.includes(t);
  const ended = r => num(r.timing?.ended_epoch_ms) ? r.timing.ended_epoch_ms : null;
  const latency = r => num(r.metrics?.elapsed_seconds) && r.metrics.elapsed_seconds>=0 ? r.metrics.elapsed_seconds : null;
  const failed = r => r.saved_status === 'INVALID_RESPONSE';
  const groupKey = r => [r.variant,r.prompt_condition,r.reasoning].join('|');
  const state = {data:null,rows:[],reason:'all',prompt:'all',variant:'all',status:'all',selectedIds:null,focusId:null,points:[],drag:null,sort:'ended',direction:1,page:0,pageSize:40,tableMode:'all',heatMetric:'format',contrastReason:'off',pending:false,lastFocus:null};
  const timeFmt = new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  const minuteFmt = new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  const dateFmt = new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  function time(v,minute=false) {return num(v)?(minute?minuteFmt:timeFmt).format(new Date(v)):'Unconfirmed';}
  function date(v) {const ms=typeof v==='string'?Date.parse(v):v;return num(ms)?dateFmt.format(new Date(ms))+' KST':'Visual uncertainty';}
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
      ['Save the response',count(n),'entries',`${count(total)}of<br>${pct(n,total)}`,'blue'],
      ['Format failed',n?count(a.invalid):'—','entries',`${count(a.invalid)} / ${count(n)}<br>${pct(a.invalid,n)}`,'red'],
      ['Response time P50',num(a.p50)?a.p50.toFixed(2):'—','Seconds.',`${count(a.latencyN)}observations<br>Median`,'blue'],
      ['Response time P95',num(a.p95)?a.p95.toFixed(2):'—','Seconds.',`${count(a.latencyN)}observations<br>95One hundredth of a second.`,'blue'],
      ['No numeric answer',n?count(a.nulls):'—','entries',`${count(a.nulls)} / ${count(n)}<br>${pct(a.nulls,n)}`,'teal'],
      ['Estimated cost of tokens',num(a.cost)?'$'+a.cost.toFixed(2):'—','',`${count(a.costN)}entries aggregated<br>Real request unknown`,''],
    ];
    $('kpis').innerHTML=cards.map(([title,value,unit,sub,color])=>`<article class="kpi ${color}" title="${escape(title)} · ${sub.replace(/<br>/g,' · ')}"><h2>${title}</h2><p class="number">${value}<small>${unit}</small></p><p class="sub">${sub}</p></article>`).join('');
    $('filter-count').innerHTML=`<strong>${count(n)}</strong> / ${count(total)}entries`;
  }
  function renderStatus() {
    const a=aggregate(state.rows),other=a.n-a.valid-a.invalid,circ=2*Math.PI*37;
    const segments=[{n:a.valid,c:COLORS.P1},{n:a.invalid,c:COLORS.fail},{n:other,c:COLORS.muted}];let offset=0;
    $('status-donut').innerHTML=`<title>All ${count(a.n)}The format is passed. ${count(a.valid)}Failure. ${count(a.invalid)}, other ${count(other)}</title><circle cx="53" cy="53" r="37" fill="none" stroke="#edf2f5" stroke-width="9"/>`+segments.filter(s=>s.n>0).map(s=>{const len=a.n?circ*s.n/a.n:0;const path=`<circle cx="53" cy="53" r="37" fill="none" stroke="${s.c}" stroke-width="9" stroke-dasharray="${len} ${circ-len}" stroke-dashoffset="${-offset}" transform="rotate(-90 53 53)"/>`;offset+=len;return path;}).join('')+`<text x="53" y="51" text-anchor="middle" fill="#415f75" font-size="17" font-weight="600">${a.n?pct(a.valid,a.n,1):'—'}</text><text x=\x2253\x22 y=\x2265\x22 text-anchor=\x22middle\x22 fill=\x22#96a6b1\x22 font-size=\x228\x22>Format valid</text>`;
    $('status-denominator').textContent=`Denominator ${count(a.n)}entries`;
    $('status-counts').innerHTML=`<p><i class=\x22p1\x22></i>Pass<strong>${count(a.valid)}</strong><small>${pct(a.valid,a.n)}</small></p><p><i class=\x22fail\x22></i>Fail<strong>${count(a.invalid)}</strong><small>${pct(a.invalid,a.n)}</small></p>${other?`<p>Guitar<strong>${count(other)}</strong><small>${pct(other,a.n)}</small></p>`:''}`;
    $('observation-counts').innerHTML=[['State: Value inconsistency',a.contradiction,'The answer with the statements of status and the numerical answer'],['The Citating Literacy',a.quote,'The exact part of the input string and other responses to the raw response quotation'],['No numeric answer',a.nulls,'Answer_is_null is true']].map(([t,n,desc])=>`<div class="observation" title="${desc}: ${count(n)} / ${count(a.n)}The observations can be overlaid\x22.<span>${t}</span><strong>${count(n)}</strong></div>`).join('');
    $('condition-bars').innerHTML=['P0','P1'].flatMap(p=>['off','on'].map(r=>{const rows=state.rows.filter(x=>x.prompt_condition===p&&x.reasoning===r),g=aggregate(rows);return `<button type="button" class="condition-bar" data-prompt="${p}" data-reason="${r}" title="${promptName(p)} · ${reasoningName(r)}Passing through: ${g.valid} / ${g.n}That\x27s a failure of form. ${g.invalid}Click on the filter.<span>${promptName(p)}<br>${reasoningName(r)}</span><span class="condition-track"><i class="valid" style="width:${g.n?100*g.valid/g.n:0}%"></i><i class="invalid" style="width:${g.n?100*g.invalid/g.n:0}%"></i></span><span class="n">${count(g.valid)}/${count(g.n)}</span></button>`;})).join('');
  }
  function renderTraffic() {
    const t=completionTraffic(state.rows),svg=$('traffic-chart');
    $('traffic-rate').textContent=num(t.rate)?t.rate.toFixed(2):'—';
    $('traffic-rate').title=t.n?`${count(t.n)}That\x27s ÷ first complete-- last complete. ${t.spanSeconds.toFixed(0)}Seconds. This is not the entire experimental time.`:'No expiration date in effect.';
    if(!t.buckets.length){svg.innerHTML='<text x=\x22125\x22 y=\x2265\x22 text-anchor=\x22middle\x22 fill=\x22#9daab4\x22 font-size=\x2211\x22>No time to finish.</text>';$('traffic-meta').textContent=`Valid 0 / ${count(state.rows.length)}entries`;return;}
    const w=250,h=128,left=35,right=7,top=13,bottom=24,plotW=w-left-right,plotH=h-top-bottom,max=Math.max(...t.buckets.map(b=>b.n),1),step=plotW/t.buckets.length,bw=Math.max(1,step*.54);
    let out=`<title>Finished drying/min. ${t.buckets.map(b=>time(b.minute,true)+' '+b.n+'entries').join(', ')}Bucket count. ${t.n}That one.</title>`;
    for(let i=0;i<=2;i++){const v=max*i/2,y=top+plotH-plotH*i/2;out+=`<line x1="${left}" y1="${y}" x2="${w-right}" y2="${y}" stroke="#e8eef2"/><text x="${left-5}" y="${y+3}" text-anchor="end" font-size="8" fill="#9aadb9">${Math.round(v)}</text>`;}
    t.buckets.forEach((b,i)=>{const x=left+step*i+(step-bw)/2,y=top+plotH-b.n/max*plotH,hh=b.n/max*plotH,fh=b.invalid/max*plotH;out+=`<rect x="${x}" y="${y}" width="${bw}" height="${hh}" rx="1" fill="#5a9dcb"><title>${time(b.minute,true)}Finished: ${b.n}That\x27s the one. ${b.invalid}entries</title></rect><rect x=\x22${x}" y="${top+plotH-fh}" width="${bw}" height="${fh}" fill="${COLORS.fail}"/>`;if(t.buckets.length<9||i%Math.ceil(t.buckets.length/5)===0)out+=`<text x="${x+bw/2}" y="${h-8}" text-anchor="middle" font-size="8" fill="#8fa2b0">${time(b.minute,true)}</text>`;});
    svg.innerHTML=out;
    $('traffic-meta').textContent=`${count(t.n)}entries · ${count(t.buckets.length)}The bucket${t.missing?' • Visual measurements '+count(t.missing):''}`;
  }
  function renderHeatmap() {
    const groups=new Map(makeGroups(state.rows).map(g=>[g.key,g]));
    let html='<span class=\x22heat-col\x22>Type</span>'+['P0','P1'].flatMap(p=>['off','on'].map(r=>`${promptName(p)}<br>${reasoningName(r)}`)).map(x=>`<span class="heat-col">${x}</span>`).join('');
    for(const[v,,short]of VARIANTS){html+=`<span class="heat-label">${short}</span>`;for(const p of ['P0','P1'])for(const r of ['off','on']){const g=groups.get([v,p,r].join('|')),value=g?(state.heatMetric==='null'?g.nulls:g.invalid):null,rate=g?value/g.n:null,observed=g&&state.heatMetric==='null'?g.n-g.nullUnknown:g?.n;const title=g?`${label(v)} / ${promptName(p)} / ${reasoningName(r)}: ${state.heatMetric==='null'?'No numbers.':'Format failed'} ${value} / ${g.n}What?${pct(value,g.n)})${observed!==g.n?' · Observation uncertain '+(g.n-observed)+'entries':''}`:`${label(v)} / ${promptName(p)} / ${reasoningName(r)}: ${v==='ORIGINAL'&&p==='P1'?'No plan.':'No response to the selection condition.'}`;const color=state.heatMetric==='null'?`rgba(15,154,141,${.07+.72*(rate||0)})`:`rgba(223,85,91,${.06+.8*(rate||0)})`;html+=`<button type="button" class="heat-cell${!g?' na':''}" ${!g?'disabled':''} data-variant="${v}" data-prompt="${p}" data-reason="${r}" title="${escape(title)}" aria-label="${escape(title)}" style="${g?'background:'+color+';color:'+(rate>.5?'#fff':'#547184'):''}">${g?(100*rate).toFixed(0)+'%':'—'}</button>`;}}
    $('heatmap').innerHTML=html;$('heat-scale').querySelector('i').style.background=state.heatMetric==='null'?'linear-gradient(90deg,#edf8f6,#0f9a8d)':'linear-gradient(90deg,#f9e9e9,#d7555d)';
  }
  function renderContrasts() {
    const reason=state.contrastReason;
    let complete=0;
    $('null-contrasts').innerHTML=VARIANTS.slice(1).map(([v,,short])=>{const p=pairedNull(state.rows,v,reason),x0=p.n?100*p.p0/p.n:0,x1=p.n?100*p.p1/p.n:0;complete+=p.n;const title=`${label(v)} / ${reasoningName(reason)}: ${p.n?`Unguided Solving ${p.p0}/${p.n} (${pct(p.p0,p.n)}), Criteria-Guided Solving ${p.p1}/${p.n} (${pct(p.p1,p.n)}), change ${p.delta>0?'+':''}${p.delta.toFixed(1)}%p`:'There are no pairs of two integers that can be compared to the choice of conditions.'}`;return `<div class="null-row${p.n?'':' filtered'}" title="${escape(title)}"><button type="button" class="null-name" data-variant="${v}" aria-label="${escape(title)} · This type of filter.${short}</button><div class="null-plot"><span class="null-line"></span>${p.n?`<span class="null-range" style="left:${Math.min(x0,x1)}%;width:${Math.abs(x1-x0)}%"></span><button type="button" class="null-dot" style="left:${x0}%" data-variant="${v}" data-prompt="P0" aria-label="${label(v)} No Unuided Solving numbers ${p.p0}/${p.n}entries\x22></button><button type=\x22button\x22 class=\x22null-dot p1\x22 style=\x22left:${x1}%" data-variant="${v}" data-prompt="P1" aria-label="${label(v)} No number of Criteria-Guided Solving ${p.p1}/${p.n}entries\x22></button>`:''}</div><span class="null-delta">${p.n?(p.delta>0?'+':'')+p.delta.toFixed(0):'—'}</span></div>`;}).join('');
    $('contrast-note').textContent=complete?`${reasoningName(reason)} · ${count(complete)}Dual · Meaning appropriateness underestimated`:'Comparison in the range that both of these set conditions are included';
  }
  function renderTable() {
    const rows=selectedRows(state.rows,state.selectedIds,state.tableMode),field=state.sort==='latency'?latency:ended;
    rows.sort((a,b)=>{const av=field(a),bv=field(b);if(av===null&&bv!==null)return 1;if(bv===null&&av!==null)return -1;return ((av??0)-(bv??0))*state.direction||a.trial_id.localeCompare(b.trial_id);});
    const pages=Math.max(1,Math.ceil(rows.length/state.pageSize));state.page=Math.min(Math.max(0,state.page),pages-1);
    const current=rows.slice(state.page*state.pageSize,(state.page+1)*state.pageSize);
    $('response-body').innerHTML=current.length?current.map(r=>`<tr data-trial="${r.trial_id}" class="${state.focusId===r.trial_id?'focused':''}"><td><button type="button" class="case-button" data-trial="${r.trial_id}\x22title=\x22 raw response and open question\x22>${escape(r.case)}<small>${escape(label(r.variant,true))} · ${promptName(r.prompt_condition)} · ${reasoningName(r.reasoning)}</small></button></td><td>${time(ended(r))}</td><td>${latency(r)!==null?latency(r).toFixed(2):'—'}</td><td><span class="row-status${failed(r)?' failed':r.saved_status==='VALID'?'':' unknown'}" title="${escape(r.saved_status)}">${failed(r)?'Fail':r.saved_status==='VALID'?'Pass':'Unconfirmed'}</span></td><td><a href="${explorerUrl(r)}" aria-label="${escape(r.case)} ${escape(label(r.variant))} ${promptName(r.prompt_condition)} ${reasoningName(r.reasoning)} The following is the list of words that can be used in the following case:</a></td></tr>`).join(''):'<tr><td colspan=\x225\x22 class=\x22empty-cell\x22>There\x27s no response to the chosen condition.<br>Use the area selection deactivation or filter initialization.</td></tr>';
    $('response-count').textContent=count(rows.length)+'entries';$('page-label').textContent=`${state.page+1} / ${pages}`;$('prev-page').disabled=state.page===0;$('next-page').disabled=state.page>=pages-1;
    $('table-selection').textContent=`${state.selectedIds?'Area/point '+count(state.selectedIds.size)+'entries':'The whole condition.'}${state.tableMode==='fail'?' • Failure to form':''}`;
    $('sort-ended').removeAttribute('aria-sort');$('sort-latency').removeAttribute('aria-sort');$('sort-'+state.sort).setAttribute('aria-sort',state.direction===1?'ascending':'descending');
    $('table-all').classList.toggle('active',state.tableMode==='all');$('table-fail').classList.toggle('active',state.tableMode==='fail');$('table-all').setAttribute('aria-pressed',state.tableMode==='all');$('table-fail').setAttribute('aria-pressed',state.tableMode==='fail');
    const focused=state.rows.find(r=>r.trial_id===state.focusId)||(state.selectedIds?.size===1?rows[0]:null);
    $('table-explorer').href=explorerUrl(focused);$('selected-explorer').href=explorerUrl(focused);
    $('clear-selection').disabled=!state.selectedIds;$('selection-status').textContent=state.selectedIds?`${count(state.selectedIds.size)} / ${count(state.rows.length)}It\x27s a select → link tab.`:'Click the dot/district drag → answer the table below';
  }
  function drawXview() {
    const canvas=$('xview'),box=$('xview-wrap').getBoundingClientRect(),w=box.width,h=box.height;
    if(w<1||h<1)return;
    const dpr=Math.min(window.devicePixelRatio||1,3);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    const valid=state.rows.filter(r=>ended(r)!==null&&latency(r)!==null),left=47,right=17,top=22,bottom=28,pw=Math.max(1,w-left-right),ph=Math.max(1,h-top-bottom);
    state.points=[];$('xview-empty').hidden=valid.length>0;$('xview-empty').textContent='There is no response to the selected condition with a completed view and response time.';
    $('xview-meta').textContent=`Time and time valid ${count(valid.length)} / ${count(state.rows.length)}The KST`;
    ctx.font=`9px ${frameStyle.fontFamily}`;ctx.fillStyle='#8ca1b0';ctx.textAlign='left';ctx.fillText('Response time (seconds)',8,12);
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
    canvas.setAttribute('aria-label',`The completion time and response time count. ${valid.length}/${state.rows.length}That\x27s the mark. ${time(start)}~${time(finish)}- Search for the left direction, enter. All responses are accessible from the link tab.`);
  }
  function setSelection(ids,focusId=null) {state.selectedIds=ids;state.focusId=focusId;state.page=0;renderTable();drawXview();announce(ids?`${ids.size}Choose the items response.`:'I\x27ve removed the choice.');}
  function nearestPoint(x,y,radius=9) {let nearest=null,distance=radius*radius;for(const p of state.points){const d=(p.x-x)**2+(p.y-y)**2;if(d<=distance){nearest=p;distance=d;}}return nearest;}
  function pointerPosition(e) {const b=$('xview').getBoundingClientRect();return{x:e.clientX-b.left,y:e.clientY-b.top};}
  function showTooltip(point,clientX,clientY) {
    const el=$('chart-tooltip');if(!point){el.hidden=true;return;}
    const r=point.row;el.innerHTML=`<strong>${escape(r.case)} · ${escape(label(r.variant))}</strong><span>${promptName(r.prompt_condition)} / ${reasoningName(r.reasoning)}</span><br>Complete ${time(ended(r))} KST · Answer ${latency(r).toFixed(3)}Seconds.<br>${failed(r)?'Format failed':r.saved_status==='VALID'?'Format valid':'Status unknown'} · ${r.answer_is_null===true?'No numbers.':r.answer_is_null===false?'There\x27s a number.':'Answer observation uncertain'}<br><span>Click on the link tab to confirm the response.</span>`;el.hidden=false;el.style.left=Math.min(clientX+12,window.innerWidth-el.offsetWidth-10)+'px';el.style.top=Math.min(clientY+12,window.innerHeight-el.offsetHeight-10)+'px';
  }
  function renderSnapshot() {
    const d=state.data,e=d.execution||{},a=d.a100||{},originals=new Set(d.rows.map(r=>r.case)).size;
    $('run-label').textContent=d.run_id;$('run-facts').textContent=`${d.model||'Model unidentified'} · ${originals}- The original. ${new Set(d.rows.filter(r=>r.variant!=='ORIGINAL').map(r=>r.item_id)).size}Variant`;
    const t=completionTraffic(d.rows);$('time-window').textContent=t.n?`${date(t.start).split(' ').slice(0,3).join(' ')} ${time(t.start)}–${time(t.end)} KST`:'Complete time unknown';
    const attempts=num(e.provider_request_attempts)?e.provider_request_attempts:e.experiment_request_attempts,success=e.successful_responses;
    $('execution-copy').textContent=`New run ${e.improved_run_id||'Unconfirmed'} · Trying the API ${count(attempts)} - Successful. ${count(success)} · ${e.phase==='API_CREDIT_BALANCE_EXHAUSTED'?'Lack of API credits':e.phase||'Status unknown'} · The above statistics are the existing collections`;
    $('execution-copy').title=`Storage status ${date(e.updated_at)} · Underestimate the improvement effect of changing response formats`;
    const recorded=Array.isArray(a.models)?a.models.reduce((n,m)=>n+(num(m.recorded)?m.recorded:0),0):null;
    $('a100-mini').textContent=`${count(recorded)} / ${count(a.planned)}`;$('a100-button').title=`${date(a.snapshot_at||a.updated_at)} The current state of the file`;
    $('source-note').textContent=`SOURCE ${d.source_run||d.run_id} • The view from the reading ${date(d.generated_at)}`;$('source-note').title=`${d.source_run||''} · API /api/dashboard/data · Standards of existing response formats at the time of storage. Underestimate the effect of changing response formats.`;
    if(/^\d{8}-exp-\d{3,}$/.test(d.run_id||''))$('experiment-viewer-link').href=`http://127.0.0.1:8894/?run=${encodeURIComponent(d.run_id)}&tab=analysis`;
    $('baseline-report').href=reportUrl('01-baseline/analysis.md');$('execution-report').href=reportUrl('REPORT.md');
  }
  function render() {if(!state.data)return;state.rows=filterRows(state.data.rows,state);renderKpis();renderStatus();renderTraffic();renderHeatmap();renderContrasts();renderTable();drawXview();}
  function openDrawer(title,html) {state.lastFocus=document.activeElement;$('drawer-title').textContent=title;$('drawer-body').innerHTML=html;$('detail-drawer').hidden=false;$('drawer-backdrop').hidden=false;$('main').inert=true;document.querySelector('.app-header').inert=true;$('close-drawer').focus();}
  function closeDrawer() {$('detail-drawer').hidden=true;$('drawer-backdrop').hidden=true;$('main').inert=false;document.querySelector('.app-header').inert=false;state.lastFocus?.focus();}
  function openResponse(trial) {const r=state.rows.find(x=>x.trial_id===trial);if(!r)return;state.focusId=trial;drawXview();renderTable();openDrawer(`${r.case} · ${label(r.variant)}`,`<p class="response-status">${promptName(r.prompt_condition)} · ${reasoningName(r.reasoning)} · ${r.saved_status==='VALID'?'Format valid':failed(r)?'Format failed':'Status unknown'}<br>Complete ${date(ended(r))} · Responding ${latency(r)!==null?latency(r).toFixed(3):'Unconfirmed'}Seconds.</p><h3>Input questions</h3><p>${escape(r.question_preview||'Questions unknown')}</p><h3>Reserved model response</h3><pre>${escape(JSON.stringify(r.response,null,2)||'Raw response subtraction')}</pre><h3>Recorded observations</h3><p>${r.answer_is_null===true?'No numeric answer':r.answer_is_null===false?'Numeric answer available':'Number answer observation uncertain'} · ${hasTag(r,TAGS.quote)?'There is a discrepancy in the quotation marks.':'No citation of the inconsistency tag'}<br>The meaning of the answer and the euphoric appropriateness are not evaluated on this screen.</p><p><a href=\x22${explorerUrl(r)}\x22> This answer opens in the case analysis</a></p><p class=\x22muted\x22>${escape(r.raw_path)}<br>trial ${escape(r.trial_id)}</p>`);}
  function openHelp() {openDrawer('How to Read and Mark',`<h3>It\x27s not a real-time operating screen, it\x27s a storage recording.</h3><p>Existing 100The original.700For the variants 3,000The result of the request is saved. The number of attempts and successes of the new execution API is shown in the status bar and is no longer in the existing collected copy statistics.</p><h3>X-View and the connection table</h3><p>The cross-section is the actual complete view (KST) and the zero-section the saved response time (s). The same second points can overlap. Click the dot or drag the area to select the response table below. You can search the point with the left-hand direction key on the keyboard and select Enter. The row without the view or response time is also missing only the score point, leaving the entire denominator and table.</p><h3>Traffic/delay time</h3><p>The rods are never visible. 1The red part is the formatting failure of the mean drying per second, the valid drying time ÷ the first completed to last completed interval, and not the entire time of the experiment.0/P95So the time of the observed response is sorted by n−1So we\x27re going to linearise the position of the centroid.</p><h3>It\x27s a distinction between form and meaning.</h3><p>Pass-failure when stored <b>The existing response format</b>It\x27s a test result of a separate observation of the raw response, which is a state-valued contradiction and a quotation letter inconsistency, and can be overridden by each other. <b>Meaning correct answer: inverse stability: improvement in the change response form</b>.</p><h3>Comparison of the filter and the pair</h3><p>The top filter applies to all panels. The score selection and the failure buttons in the table change only the range of the linked table. Unguided Solving → Criteria-Guided Solving compares both responses to the same primitive and typical statement to the filter and count to one pair where null or not is observed. If there are no pairs, it is denoted as a source items .</p><h3>denominator and cost</h3><p>The ratio keeps the file request line in the filter as the denominator. 0The token cost is the sum of the estimated amount of the requested data stored and the actual amount of the invoice is unknown.00The other 1,080The original.7,560It\x27s a modified group and it only provides a state at the time of storage.</p><p><a href=\x22${reportUrl('01-baseline/analysis.md')}\x22 target=\x22_blank\x22 rel=\x22noopener\x22>Real observation based report</a></p>`);}
  function openA100() {const a=state.data?.a100;if(!a){openDrawer('A100 Saved copy','<p>There\x27s no summary stored.</p>');return;}const models=Array.isArray(a.models)?a.models:[],recorded=models.reduce((n,m)=>n+(num(m.recorded)?m.recorded:0),0);openDrawer('A100 · Summary of the storage of star clusters',`<p class=\x22muted\x22>Storage time ${date(a.snapshot_at||a.updated_at)}<br>The current remote run is not monitored.</p><p class=\x22drawer-kpi\x22>${count(recorded)} <small>/ ${count(a.planned)}</small></p><p>${count(a.originals)}The original ${count(a.variants)}The moon. 100Do not combine source cohorts or their statistical denominators.</p><table><thead><tr><th>Model</th><th>Save / plan</th><th>When you store it</th></tr></thead><tbody>${models.map(m=>`<tr><td>${escape(m.key||m.model)}</td><td>${count(m.recorded)} / ${count(m.planned)}</td><td>${escape(({COMPLETED:'Complete',RUNNING:'In progress',NOT_EXECUTABLE:'Cannot run'})[m.status]||m.status||'Unconfirmed')}</td></tr>`).join('')}</tbody></table><p class=\x22muted\x22>RUNNING indicators at the time of storage are not running now, and the financial model\x27s feasibility and comparison groups are not being reviewed.</p>`);}
  async function loadData(refresh=false) {
    if(state.pending)return;state.pending=true;$('refresh').disabled=true;$('main').setAttribute('aria-busy','true');$('loading-state').hidden=false;$('error-state').hidden=true;
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),120000);
    try{const response=await fetch(API+(refresh?'?refresh=1':''),{cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();if(data.schema_version!==1||!Array.isArray(data.rows))throw new Error('It\x27s not a supported response list format.');state.data=data;state.selectedIds=null;state.focusId=null;state.page=0;renderSnapshot();render();announce(`${data.rows.length}I read the items storage response.`);}catch(error){$('error-copy').textContent=`${error.name==='AbortError'?'I\x27ve been over the waiting time to read.':error.message}\nCheck the report server and the actual data path, and read it again.${state.data?' The last reading on the screen is the last one left.':''}`;$('error-state').hidden=false;$('run-label').textContent=state.data?`${state.data.run_id} • Failure to read again`:'Failure to connect data';}finally{clearTimeout(timeout);state.pending=false;$('refresh').disabled=false;$('main').setAttribute('aria-busy','false');$('loading-state').hidden=true;}
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
    canvas.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Enter','Escape'].includes(e.key))return;e.preventDefault();if(e.key==='Escape'){setSelection(null);return;}const points=[...state.points].sort((a,b)=>ended(a.row)-ended(b.row)||a.row.trial_id.localeCompare(b.row.trial_id));if(!points.length)return;let index=points.findIndex(p=>p.row.trial_id===state.focusId);if(e.key==='Enter'){if(index<0)index=0;const row=points[index].row;setSelection(new Set([row.trial_id]),row.trial_id);return;}index=index<0?0:(index+(e.key==='ArrowRight'?1:-1)+points.length)%points.length;state.focusId=points[index].row.trial_id;const r=points[index].row;drawXview();announce(`${r.case} ${label(r.variant)} ${promptName(r.prompt_condition)} ${reasoningName(r.reasoning)}Finished. ${time(ended(r))}, ${latency(r).toFixed(2)}Second. Select Enter.`);});
    new ResizeObserver(()=>{if(state.data)drawXview();}).observe($('xview-wrap'));
    loadData();
  }
  init();
})();
