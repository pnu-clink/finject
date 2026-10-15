function pot(p,r){
 if(r.axis==='EA'&&r.variant?.plan?.method==='missing-input-dag-v1'){eaPlanView(p,r,r.variant.plan,false);return;}
 p.append(el('h2','','코드·실행 결과·정답 비교'));
 p.append(box('질문 · Q',r.sample.question));
 const explain=reason=>String(reason||'원인 기록 없음').includes('ConversionSyntax')?'근거 값에 쉼표가 있어 실행기가 숫자로 읽지 못했습니다.':String(reason||'').includes("was never closed")?'생성된 코드의 괄호가 닫히지 않아 실행하지 못했습니다.':reason||'원인 기록 없음';
 const code=eventOf(r,'02-calculation/02-prepare-code/03-program.json'),execution=record(r,'02-calculation/P02-execute'),comparison=eventOf(r,'02-calculation/04-compare-answer/01-comparison.json')||record(r,'02-calculation/P03-gold'),run=eventOf(r,'run.json');
 if(!code){p.append(el('div','banner','POT 코드가 아직 생성되지 않았습니다. 중단 위치: '+(run.stopped_at||'종료 기록 없음')+' · 이유: '+(run.reason||'기록 없음')));jsonBox(p,'생성 요청과 오류',eventOf(r,'02-calculation/01-generate-code/05-validate-response/04-result.json'));p.append(box('원문 본문',r.sample.context));return}
 const diagnosis=eventOf(r,'02-calculation/source-diagnosis.json');
 if(diagnosis){const d=el('section','box source-diagnosis');d.append(el('h3','','이번 실패 원인과 수정안 확인'),el('p','',diagnosis.question_explanation),el('p','','모델에 전달한 숫자·위치는 서로 일치했습니다. 모델 응답에서 인용문에만 달러 기호가 추가됐고, 저장 코드는 이를 그대로 보존했습니다.'),el('pre','',diagnosis.source_table_excerpt));if(diagnosis.trial?.matches)d.append(el('p','','확인용 사본에서 인용문만 지정 위치와 맞췄더니, 같은 Python 코드로 '+diagnosis.trial.computed+'가 나와 정답과 일치했습니다. 원래 실패 기록과 생성 코드는 그대로입니다.'));jsonBox(d,'요청 → 모델 응답 → 저장 기록 비교와 확인 실행',diagnosis);p.append(d)}
 if(run.status==='FAIL'&&/^(02|03)-calculation(?:\/|$)/.test(run.stopped_at||'')){const warning=el('div','banner','이 문항은 중단됐습니다: '+explain(run.reason)+' · 코드 생성과 실행·정답 일치는 별개의 결과입니다.');const detail=errorSummary(run.reason);if(detail)warning.append(detail);p.append(warning)}
 p.append(el('p','small','색이 있는 원문 숫자, 변수 표, 코드 줄에 마우스를 올리거나 클릭하면 연결된 부분을 강조합니다. 색상은 근거와 코드의 참조 연결이며, 실행 성공은 아래 실제 결과에서 확인합니다.'));
 const facts=Array.isArray(code.facts)?Object.fromEntries(code.facts.map(f=>[f.id,f])):code.facts||{},ids=Object.keys(facts),colors=['#147d92','#9b51a0','#aa5c18','#237d42','#495dba','#a33e56'];
 function color(id){return colors[ids.indexOf(id)%colors.length]}
 function highlight(wanted){for(const node of p.querySelectorAll('[data-facts]'))node.classList.toggle('fact-active',JSON.parse(node.dataset.facts).some(id=>wanted.includes(id)))}
 function bind(node,linked){node.dataset.facts=JSON.stringify(linked);if(linked.length===1)node.style.setProperty('--fact-color',color(linked[0]));node.tabIndex=0;node.onmouseenter=()=>highlight(linked);node.onmouseleave=()=>highlight([]);node.onfocus=()=>highlight(linked);node.onblur=()=>highlight([]);node.onclick=()=>highlight(linked)}
 const source=el('div','box prose fact-source'),context=r.sample.context||'';let cursor=0;
 for(const [id,fact] of Object.entries(facts).sort((a,b)=>a[1].span?.[0]-b[1].span?.[0])){const [start,end]=fact.span||[];if(!Number.isInteger(start)||!Number.isInteger(end)||start<cursor||end<=start||end>Array.from(context).length)continue;const actual=sliceText(context,start,end);source.append(document.createTextNode(sliceText(context,cursor,start)));const mark=el('button','fact-mark',actual);mark.style.setProperty('--fact-color',color(id));mark.title=id+' = '+fact.value+(actual!==fact.text?' · 모델 인용문과 불일치':'');mark.setAttribute('aria-label',id+' 원문 근거 '+actual);bind(mark,[id]);source.append(mark);cursor=end}source.append(document.createTextNode(sliceText(context,cursor)));p.append(el('h3','','모델이 지정한 원문 위치'),source);
 const formula=el('section','formula-comparison');formula.setAttribute('aria-label','계산 수식 · 근거 key와 값 대입');formula.append(el('h3','','계산 수식 · A. 원본식'));
 const formulaGraph=eventOf(r,'04-graph/04-save-graph/01-graph.json')||eventOf(r,'03-graph/04-save-graph/01-graph.json');
 try{
  if(!formulaGraph?.nodes)throw Error('저장된 계산 그래프가 없어 수식을 표시할 수 없습니다. 아래 Python 코드와 실행 오류를 확인하세요.');
  const lines=[false,true].map(numeric=>{
   const line=el('div','formula-line'+(numeric?' formula-numeric':''));
   line.append(document.createTextNode(numeric?'값 대입 = ':'최종 답 = '));
   for(const part of graphFormula(formulaGraph,{numeric})){
    const node=formulaGraph.nodes.find(n=>n.id===part.nodeId),span=el('span','',part.text);
    if(node?.fact_id&&ids.includes(node.fact_id)){span.style.color=color(node.fact_id);span.title=node.fact_id;bind(span,[node.fact_id]);}
    line.append(span);
   }
   return line;
  });formula.append(...lines);
 }catch(error){formula.append(el('p','small',error.message));}
 p.append(formula);
 // [VF03] Compare model citation with the actual slice; never label model text as original text.
 const table=el('table','fact-table'),head=el('tr');['근거 이름','모델이 적은 인용문','지정 위치에서 실제 읽힌 원문','검사에 사용한 인용문','글자 일치','계산용 값 · 단위','원문 위치'].forEach(t=>head.append(el('th','',t)));table.append(head);
 const sourceAudit=eventOf(r,'02-calculation/03-execute-python/02-number-normalization.json');
 for(const [id,fact] of Object.entries(facts)){const row=el('tr'),[start,end]=fact.span||[],valid=Number.isInteger(start)&&Number.isInteger(end)&&start>=0&&end>start&&end<=Array.from(context).length,actual=valid?sliceText(context,start,end):'위치 범위 오류',matches=valid&&actual===fact.text,repair=sourceAudit?.facts?.find(f=>f.fact_id===id),used=repair?.validated_source_text??fact.text,repaired=!!repair?.source_applied_rules?.length;row.style.borderLeft='4px solid '+color(id);const claimed=el('td',matches?'':'diff-remove',fact.text),located=el('td',matches?'':'diff-insert',actual);row.append(el('td','',id),claimed,located,el('td','',used),el('td','',valid&&actual===used?(repaired?'보정 후 일치':'일치'):'불일치'),el('td','',fact.value+' '+(fact.unit||'')),el('td','',(fact.span||[]).join('–')));bind(row,[id]);table.append(row)}p.append(el('h3','','원문 위치 검사 · 원래 인용문과 보정 결과'),table);
 // [NN04] docs/02-architecture.md#NN04 — 저장된 변환 전후 값과 순서별 규칙 기록을 표시한다.
 const normalization=eventOf(r,'02-calculation/03-execute-python/02-number-normalization.json');
 if(normalization){p.append(el('h3','','Python에 전달하기 전 숫자 변환'),el('p','small','원문과 생성 코드는 그대로 보존합니다. 등록된 규칙을 순서대로 적용한 계산용 값만 Python에 전달합니다.'));
 const converted=el('table','normalization-table'),heading=el('tr');['근거 이름','변환 전 값','Python에 전달한 값','적용 규칙 / 오류'].forEach(t=>heading.append(el('th','',t)));converted.append(heading);
 for(const fact of normalization.facts||[]){const row=el('tr');row.append(el('td','',fact.fact_id),el('td','',fact.original_value),el('td','',fact.python_value??'변환 실패'),el('td','',fact.error||(fact.applied_rules||[]).join(' → ')||'변경 없음'));bind(row,[fact.fact_id]);converted.append(row)}p.append(converted);jsonBox(p,'변환 규칙과 단계별 적용 내역',normalization)}
 // [PX02] Show and copy the same complete program; preserve links to the original body.
 const codeTitle=el('h3','','실행할 계산 부분');p.append(codeTitle);const listing=el('pre','pot-code'),standalone=r.run.standalone_program,fullCode=standalone?.code;let showFull=false;
 const actions=el('div','toolbar'),copyStatus=el('span','small');copyStatus.setAttribute('role','status');
 const copyButton=button('전체 코드 복사',async()=>{try{if(navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(fullCode);copyStatus.textContent='전체 코드 복사 완료';return}catch(error){}}const temporary=el('textarea');temporary.value=fullCode;temporary.style.position='fixed';temporary.style.opacity='0';p.append(temporary);temporary.select();const copied=document.execCommand('copy');temporary.remove();if(!copied)throw Error('copy unavailable');copyStatus.textContent='전체 코드 복사 완료'}catch(error){copyStatus.textContent='복사 권한이 없어 복사하지 못했습니다. 아래 코드를 직접 선택해 주세요.'}});copyButton.disabled=!fullCode;
 function drawCode(){codeTitle.textContent=showFull?'전체 Python 코드':'실행할 계산 부분';listing.replaceChildren();const displayed=showFull?fullCode:code.code,offset=showFull?standalone.original_start_line-1:0;displayed.split('\n').forEach((text,i)=>{const line=el('span','code-line'),linked=r.run.code_links?.[i+1-offset]||[];if(linked.length)line.style.borderLeftColor=color(linked[0]);line.append(el('span','code-no',i+1));const body=el('span');const inputLine=/^\s*\w+\s*=\s*fact\(/.test(text);if(!inputLine)line.classList.add('intermediate-calculation');for(const token of text.split(/(\b[A-Za-z_]\w*\b)/)){const span=el('span','',token);if(ids.includes(token)){span.style.color=color(token);bind(span,[token]);}body.append(span)}line.append(body);bind(line,linked);listing.append(line)})}
 const toggle=button(showFull?'실행할 계산 부분만 보기':'전체 실행 코드 보기',()=>{showFull=!showFull;toggle.textContent=showFull?'실행할 계산 부분만 보기':'전체 실행 코드 보기';drawCode()});toggle.disabled=!fullCode;
 actions.append(copyButton,toggle,copyStatus);p.append(actions,el('p','small',fullCode?'필요한 임포트·숫자 데이터·fact 함수·계산식·결과 출력을 모두 포함합니다. 복사해서 Python 3로 실행하면 됩니다. 원문 출처 검사는 이 계산 실행과 별도입니다.':'전체 코드 구성 실패: '+(standalone?.error||'기록 없음')),listing);drawCode();
 const layout=eventOf(r,'02-calculation/02-prepare-code/01-transformation.json');if(layout?.changes?.length){p.append(el('p','small','모델 생성 원본에서 숫자 상수를 변수로 분리한 실행 코드입니다. 수치와 연산 순서는 유지했습니다.'));jsonBox(p,'상수 변수화 내역',layout);jsonBox(p,'모델이 생성한 원래 코드',eventOf(r,'02-calculation/01-generate-code/05-validate-response/05-generated-program.json'))}
 const stepwise=eventOf(r,'02-calculation/02-prepare-code/02-check.json');
 if(stepwise){p.append(el('h3','','변수별 계산 단계'),el('p','small','저장된 코드의 대입 순서입니다. 계산 그래프 생성이나 의미 검토가 완료됐다는 뜻은 아닙니다.'));
 if(stepwise.status!=='PASS'&&eventOf(r,'02-calculation/04-compare-answer/02-disposition.json')?.disposition!=='EXCLUDED')p.append(el('div','banner','계산 단계 형식 보완 필요: 변수 이름 없이 수식에 남은 숫자 또는 중첩 연산이 있습니다. 정답 일치 여부와 별도로 확인합니다.'));
 const stages=el('table','stepwise-table'),header=el('tr');['코드 줄','변수 키','계산식 / 입력','실행에서 기록된 값'].forEach(t=>header.append(el('th','',t)));stages.append(header);
 for(const step of stepwise.steps||[]){const row=el('tr');row.append(el('td','',step.line),el('td','',step.variable),el('td','',step.expression),el('td','',execution?.trace?.[step.variable]??'실행값 기록 없음'));stages.append(row)}p.append(stages);jsonBox(p,'계산 단계 형식 검사 상세',stepwise)}
 const groundingReview=eventOf(r,'02-calculation/grounding-review.json');if(groundingReview){p.append(el('h3','','질문·단위·계산 가정 검토'),el('p','',groundingReview.finding));jsonBox(p,'원문 행·열과 검토 기록',groundingReview)}
 if(code.grounding)jsonBox(p,'모델이 설명한 근거와 계산 방법',code.grounding);
 const answerInfo=answerRevision(r);p.append(el('h3','',answerInfo.revision?'실제 실행 결과와 수정정답':'실제 실행 결과와 원본 정답'));const cols=el('div','cols');cols.append(box(comparison?'Python 최종 답 · 자릿수 적용':'Python 계산값 · 자릿수 미적용',comparison?.computed??execution?.exact_value??'실행 결과 없음',{ui:true}),box(answerInfo.revision?`수정정답 (원본: ${answerInfo.original})`:'원본 정답',answerInfo.revision?`${answerInfo.current} (${answerInfo.revision}차 수정)`:answerInfo.current,{ui:true}));if(comparison?.matches===false){cols.style.border='2px solid #c62828';cols.style.background='#fff1f1';cols.style.color='#9f1717';const mismatchHeading=el('strong','','정답 불일치 · POT 계산값과 골드가 다릅니다.');mismatchHeading.style.gridColumn='1 / -1';cols.prepend(mismatchHeading);}p.append(cols);
 if(comparison){p.append(el('p','small',`대조 정답 기준 소수 ${comparison.reference_precision}자리 · ${comparison.policy} · 중간 계산값은 유지합니다.`));jsonBox(p,'자릿수 적용 전 Python 결과',comparison.computed_value??execution?.exact_value??comparison.exact_value);p.append(badge(comparison.matches?'PASS':'FAIL'),el('p','',comparison.matches?'현재 비교 기준으로 정답이 일치합니다.':'현재 비교 기준으로 정답이 일치하지 않습니다.'));jsonBox(p,'비교에 사용한 값·자릿수·규칙',comparison)}else p.append(el('div','banner','정답 비교가 아직 완료되지 않았습니다.'));
 jsonBox(p,'실제 실행에서 기록한 변수 값',execution?.trace);jsonBox(p,'Python 실행 전체 기록',eventOf(r,'02-calculation/03-execute-python/03-result.json'));
}
