function node(tag, text, cls = '') {
  const n = document.createElement(tag); n.textContent = String(text ?? ''); n.className = cls; return n;
}
const ratio = (value, total) => `${n(value)}건 · ${total ? (value / total * 100).toFixed(1) : '0.0'}%`;
const n = value => Number(value).toLocaleString();
const condition = (g, r) => `G${({ON:'⁺',OFF:'⁻',guided:'⁺',unguided:'⁻'})[g]??'?'}R${({ON:'⁺',OFF:'⁻',on:'⁺',off:'⁻'})[r]??'?'}`;
const outcomeHelp = {
  SUPPORTED_ANSWER: 'NS · 숫자를 답했고, DG가 그 답변의 근거를 뒷받침합니다.',
  SUPPORTED_ABSTENTION: 'AS · null로 기권했고, 유보 이유(ARV)와 결정의 근거(DG)가 모두 뒷받침됩니다.',
  UNNECESSARY_ABSTENTION: 'AU/AD 중, 독립 검토로 답할 수 있는 문항임이 확인됐는데 기권한 경우입니다.',
  MISSED_ABSTENTION: 'NU/ND 중, 독립 검토로 답을 확정할 수 없는 문항임이 확인됐는데 숫자를 답한 경우입니다.',
  UNCLASSIFIED: '독립 문항 판정 부족, 판단 유보, 검토 미완료·불가 또는 판정 충돌로 최종 범주를 확정하지 못했습니다.'
};
function helpTable(headers, rows) {
  const wrap = node('div', '', 'table-wrap'), table = node('table'), head = node('thead'), tr = node('tr');
  for (const text of headers) tr.append(node('th', text));
  head.append(tr); table.append(head);
  const body = node('tbody');
  for (const row of rows) { const tr = node('tr'); for (const text of row) tr.append(node('td', text)); body.append(tr); }
  table.append(body); wrap.append(table); return wrap;
}
function outcomeGuide() {
  const guide = node('details', '', 'outcome-guide');
  guide.append(node('summary', '분류 기준 펼치기 · N/A × S/U 사분면과 ARV·DG'));
  guide.append(node('p', 'N은 숫자를 반환한 행동, A는 null로 기권한 행동입니다. S는 근거가 뒷받침됨, U는 뒷받침되지 않음입니다. N은 정답이라는 뜻이 아니며, U는 답변 불가능(UNANSWERABLE)이라는 뜻이 아닙니다.'));
  guide.append(helpTable(['↑ 근거 판정 / 행동 →', 'N · 숫자 답변', 'A · 기권'], [
    ['S · 뒷받침됨', 'NS → 근거 있는 답변 · DG=S', 'AS → 근거 있는 기권 · ARV=S, DG=S'],
    ['U · 뒷받침되지 않음', 'NU → 독립 문항 판정이 없으면 미분류 · DG=U', 'AU → 독립 문항 판정이 없으면 미분류 · ARV 또는 DG에 U']
  ]));
  guide.append(node('p', '사분면 밖: D는 판단 유보(UNDETERMINED)로 ND/AD에 남습니다. F는 형식 실패·검토 미완료·판정 누락 등으로 정상 배치하지 못한 경우입니다. 원본의 근거 검토가 없는 경우도 F이므로 전부 풀이 실패로 해석하지 않습니다.', 'scope-note'));
  guide.append(node('h4', 'ARV와 DG는 무엇을 보나요?'), node('p', 'ARV(abstention_reason_validity)는 “답할 수 없다고 한 이유가 입력과 맞는가?”, DG(decision_grounding)는 “최종 답 또는 기권 결정을 설명·계산·인용과 입력이 뒷받침하는가?”를 봅니다. 숫자 답변 N은 DG만 사용합니다. 기권 A는 두 판정을 함께 사용합니다.'));
  guide.append(helpTable(['ARV ↓ / DG →', 'S', 'U', 'D'], [
    ['S', 'AS · 둘 다 뒷받침됨', 'AU_S_U · 이유는 타당, 결정·설명 근거는 부적절', 'AD · 결정 근거 판단 유보'],
    ['U', 'AU_U_S · 이유는 부적절', 'AU_U_U · 둘 다 부적절', 'AU_U_D · 이유는 부적절'],
    ['D', 'AD · 이유 판단 유보', 'AU_D_U · 결정 근거는 부적절', 'AD · 둘 다 판단 유보']
  ]));
  guide.append(node('p', 'S/U/D는 SUPPORTED/UNSUPPORTED/UNDETERMINED입니다. 적용할 판정이 누락·null·부적절한 값이면 먼저 F로 둡니다. 유효한 판정 중 하나라도 U이면 AU, 모두 S이면 AS, 나머지는 AD입니다. SU는 ARV→DG 순서이며 저장값은 AU_S_U입니다. 예: 유보 이유는 맞지만 설명 속 계산이 틀리면 S/U가 가능합니다.'));
  guide.append(node('h4', 'NU와 AU를 왜 바로 기권 실패·불필요한 기권으로 세지 않나요?'), node('p', 'NU는 숫자를 냈지만 근거가 부족한 응답입니다. 풀 수 있는 문제를 잘못 계산했는지, 애초에 기권해야 했는지는 NU만으로 알 수 없습니다. NU_MATCH(원본 숫자 일치), NU_MISMATCH(불일치), NU_UNKNOWN(비교 미확인) 모두 독립 문항 판정이 없으면 미분류입니다. 원본 숫자 일치가 변형 입력의 근거 타당성을 보장하지 않습니다.'));
  guide.append(helpTable(['최종 범주', '포함하는 경우', '이 범주에서 제외 → 미분류'], [
    ['불필요한 기권', 'AU/AD + 독립 ANSWERABLE', '독립 판정 없음 또는 UNANSWERABLE, 검토 불가 F, AS와 독립 ANSWERABLE의 충돌'],
    ['기권 실패', 'NU/ND + 독립 UNANSWERABLE', '독립 판정 없음 또는 ANSWERABLE, 검토 불가 F, NS와 독립 UNANSWERABLE의 충돌']
  ]));
  guide.append(node('p', '독립 판정은 같은 입력에 대해 별도로 검증된 문항 답변가능성 기록입니다. ARV·DG 이유 문장이나 NS/AS에서 추론한 값을 독립 판정으로 대신하지 않습니다. AU_S_U처럼 유보 이유가 맞아도 설명에 오류가 있으면 자동으로 불필요한 기권이 되지 않습니다.'));
  guide.append(node('p', '제외는 응답을 삭제하거나 전체 분모에서 빼는 것이 아닙니다. 근거가 부족한 사례는 미분류와 세부 사유로 보존합니다. 두 실패 범주의 0건은 확정 요건을 채운 사례가 없다는 뜻이며, 실제 실패가 전혀 없다는 뜻은 아닙니다. NS/AS도 독립 판정과 충돌하면 미분류입니다.', 'scope-note'));
  return guide;
}
export async function renderSemanticOutcomes({ load, openResponse }) {
  const section = node('section', '', 'panel');
  section.append(node('h3', 'ANSWERABLE · 저장된 응답 결과'));
  const note = node('p', '최종 Python 산출물의 semantic_answerability 값을 그대로 집계합니다. 응답 결과 분류이며, 문항 자체의 독립적인 답변가능성 gold가 아닙니다.', 'scope-note');
  const select = document.createElement('select'); select.setAttribute('aria-label', '응답 결과 집계 범위');
  for (const [value, text] of [['all','모든 응답'], ['variants','전체 7개 변형'], ['h1','H1 / 5개 변형'], ['originals','원본']]) {
    const option = node('option', text); option.value = value; select.append(option);
  }
  const body = node('div'), details = node('div'); section.append(note, outcomeGuide(), select, body, details);
  let generation = 0;
  async function show(filters = {}) {
    const token = ++generation; body.replaceChildren(node('p', '저장 결과와 근거 파일을 확인하고 있습니다.')); details.replaceChildren();
    try {
      const data = await load({ scope: select.value, ...filters });
      if (token !== generation) return;
      body.replaceChildren();
      if (data.error) throw Error(data.error);
      if (data.status !== 'AVAILABLE') { body.append(node('p', '아직 최종 분류를 생성하지 않았습니다.')); return; }
      body.append(node('p', `전체 ${n(data.total)}건 / ${data.generated_at} / 새 모델 호출 0건`));
      const codes = data.codes;
      const totals = node('div', '', 'cards');
      for (const code of codes) {
        const card = node('button', '', 'panel');
        card.append(node('strong', data.categories[code]), node('div', code.startsWith('\0') ? data.categories[code] : code, 'small muted'), node('div', ratio(data.counts[code], data.total)));
        if (outcomeHelp[code]) card.append(node('div', outcomeHelp[code], 'outcome-term-help'));
        card.disabled = !data.counts[code]; card.addEventListener('click', () => show({ category: code })); totals.append(card);
      }
      body.append(totals, node('p', `분류값별 합계 ${n(Object.values(data.counts).reduce((a, b) => a + b, 0))}건 / 전체 ${n(data.total)}건 · 원본 포함 여부는 위 집계 범위를 따릅니다.`, 'scope-note'));
      const table = node('table'), head = node('tr');
      for (const title of ['모델', 'GR', ...codes.map(c => data.categories[c]), '전체']) head.append(node('th', title));
      const thead = node('thead'); thead.append(head); table.append(thead);
      const tbody = node('tbody');
      for (const group of data.groups) {
        const tr = node('tr');
        for (const text of [group.model, condition(group.prompt_condition, group.reasoning)]) tr.append(node('td', text));
        for (const code of codes) {
          const td = node('td'), button = node('button', ratio(group[code], group.total), 'text-button');
          button.disabled = !group[code]; button.addEventListener('click', () => show({ category: code, model: group.model, prompt: group.prompt_condition, reasoning: group.reasoning }));
          td.append(button); tr.append(td);
        }
        tr.append(node('td', n(group.total))); tbody.append(tr);
      }
      table.append(tbody); const wrap = node('div', '', 'table-wrap'); wrap.append(table); body.append(wrap);
      body.append(node('p', '0건인 분류도 표시합니다. 미분류는 UNCLASSIFIED, 필드 누락·null·빈 문자열은 각각 별도로 집계합니다.', 'scope-note'));
      if (filters.category) {
        details.append(node('h4', `${data.categories[filters.category]} / ${n(data.matching)}건`));
        for (const row of data.rows) {
          const item = node('details'), summary = node('summary', `${row.case} / ${row.variant} / ${row.classification_reason}`);
          item.append(summary, node('p', `답변: ${row.answer ?? 'null'} / NASU: ${row.nasu_detail} / 검토: ${row.review_status}`));
          for (const [key, label] of [['abstention_reason_validity', 'ARV · 유보 이유의 타당성'], ['decision_grounding', 'DG · 답·기권 결정의 근거']]) {
            const judgment = row.assessment?.[key];
            if (judgment) { item.append(node('p', `${label}: ${judgment.verdict} / ${judgment.reason}`));
              for (const citation of judgment.citations || []) item.append(node('blockquote', `${citation.source}: ${citation.quote}`)); }
          }
          const button = node('button', 'E02 원문과 응답 열기', 'text-button'); button.addEventListener('click', () => openResponse(row)); item.append(button); details.append(item);
        }
        if (data.offset) { const back = node('button', '이전 20건'); back.addEventListener('click', () => show({ ...filters, offset: Math.max(0, data.offset-20) })); details.append(back); }
        if (data.next_offset !== null) { const next = node('button', '다음 20건'); next.addEventListener('click', () => show({ ...filters, offset: data.next_offset })); details.append(next); }
      }
    } catch (error) { if (token === generation) body.replaceChildren(node('p', error.message, 'scope-note')); }
  }
  select.addEventListener('change', () => show());
  await show(); return section;
}


export async function renderOutcomeComparison({ load, openRun }) {
  const panel=node('section','','panel');
  panel.append(node('h3','모델별 저장 결과 취합'));
  panel.append(node('p','FInject 최종 PASS 문항군 1,354개를 하나로 집계합니다. 원천별 기존 집계도 선택할 수 있습니다. 지원 비율과 검토 범위를 구분하며, 문항 답변가능성 gold를 새로 정하지 않습니다.','scope-note'));
  const cohort=node('select');cohort.setAttribute('aria-label','비교 코호트');
  for(const [value,text] of [['final','FInject 최종 PASS · 1,354 문항군'],['source','원천별 기존 집계']]){const option=node('option',text);option.value=value;cohort.append(option);}
  const select=node('select'); select.setAttribute('aria-label','모델 비교 집계 범위');
  for(const [value,text] of [['all','모든 응답 · 원본 포함'],['variants','전체 7개 변형'],['h1','H1 · 5개 변형'],['originals','원본']]){const option=node('option',text);option.value=value;select.append(option);}
  const body=node('div');panel.append(cohort,select,body);let generation=0;
  async function show(){
    const token=++generation;body.replaceChildren(node('p','저장 결과와 최종 데이터 해시를 확인하고 있습니다.'));
    try{
      const data=await load({scope:select.value,cohort:cohort.value});if(token!==generation)return;body.replaceChildren();
      if(data.error) throw Error(data.error);
      if(data.cohort==='final') {
        const s=data.summary, pct=value=>value==null?'미확인':`${(value*100).toFixed(1)}%`;
        body.append(node('p',`FInject ${n(s.families)}개 · FinanceReasoning ${n(s.sources.FinanceReasoning)} + TAT-QA ${n(s.sources['TAT-QA'])} · 스냅샷 ${s.generated_at} · 새 모델 호출 0건`));
        body.append(helpTable(['모델','선택 범위 계획','NS','NU','AS','AU','D','미검토 F','S/(S+U)','검토 범위'],s.scopes.filter(r=>r.scope===select.value).map(r=>[r.model,n(r.planned),n(r.NS),n(r.NU),n(r.AS),n(r.AU),n(r.D),n(r.F),pct(r.O),pct(r.coverage)])));
        body.append(node('h4','G×R 비교 · 주요 5개 변형 / 조건당 6,770건'));
        body.append(helpTable(['모델','GR','계획','NS','NU','AS','AU','D','F','전체 지원 O','숫자 지원 N','기권 지원 A','NS/계획','AS/계획','검토 범위'],s.rq1.map(r=>[r.model,condition(r.G,r.R),n(r.planned),n(r.NS),n(r.NU),n(r.AS),n(r.AU),n(r.D),n(r.F),pct(r.O),pct(r.N),pct(r.A),pct(r.NS_share),pct(r.AS_share),pct(r.coverage)])));
        body.append(node('h4','원본 정답/오답 집단의 변형 지원 비율'));
        body.append(helpTable(['모델','GR','원본 정답','오답','미확인','정답 집단 S/분모','오답 집단 S/분모','차이 %p'],s.rq2.map(r=>[r.model,condition(r.G,r.R),n(r.originals.CORRECT),n(r.originals.INCORRECT),n(r.originals.UNKNOWN),`${n(r.C.S)}/${n(r.C.resolved)} · ${pct(r.C.O)}`,`${n(r.I.S)}/${n(r.I.resolved)} · ${pct(r.I.O)}`,r.delta_pp==null?'미확인':r.delta_pp.toFixed(1)])));
        body.append(node('h4','IC-v → IC-s · 지원 기권 유지'));
        body.append(helpTable(['모델','GR','쌍','계획','판정된 쌍','이전 AS','이후 AS','유지','새 AS','유지율','제외 D/F'],s.rq3.map(r=>[r.model,condition(r.G,r.R),r.pair,n(r.planned),n(r.n),n(r.before),n(r.after),n(r.retained),n(r.new),pct(r.retention),`${n(r.excluded.D||0)}/${n(r.excluded.F||0)}`])));
        body.append(node('p','Gemini R-OFF는 기존 조건 미실행, R-ON의 A02는 미실행입니다. 0/0의 지원·유지 비율은 미확인으로 표시합니다. 원본은 A02 근거 검토 대상이 아닙니다.','scope-note'));
        const provenance=node('details');provenance.append(node('summary','원천 run과 문항별 원응답 열기'));
        for(const r of s.runs){const p=node('p'), b=node('button',`${r.model_label} · ${r.source_dataset} · ${r.run}`,'text-button');b.addEventListener('click',()=>openRun(r.run));p.append(b);provenance.append(p);}
        body.append(provenance);return;
      }
      for(const dataset of ['TAT-QA','FR']){
        body.append(node('h4',dataset));
        const rows=data.results.filter(r=>r.dataset===dataset);
        const codes=[...new Set(rows.flatMap(r=>r.codes||[]))];
        const names=Object.assign({},...rows.map(r=>r.categories||{}));
        const table=node('table'), head=node('tr'), thead=node('thead'), tbody=node('tbody');
        for(const title of ['모델','전체',...codes.map(c=>names[c]),'저장 상태'])head.append(node('th',title));
        thead.append(head);table.append(thead,tbody);
        for(const r of rows){
          const tr=node('tr'), model=node('td'), link=node('button',r.model,'text-button');link.addEventListener('click',()=>openRun(r.run));model.append(link);tr.append(model);
          tr.append(node('td',r.status==='AVAILABLE'?n(r.total):'미확인'));
          for(const code of codes)tr.append(node('td',r.status==='AVAILABLE'?ratio(r.counts[code]||0,r.total):'—'));
          tr.append(node('td',r.status==='AVAILABLE'?`분류 저장됨 · Analysis ${r.analysis_status}`:r.error||'분류 미생성'));tbody.append(tr);
        }
        const wrap=node('div','','table-wrap');wrap.append(table);body.append(wrap);
        const provenance=node('details');provenance.append(node('summary','사용한 회차 · 저장 시각 · 구성 수량'));
        for(const r of rows)provenance.append(node('p',`${r.model} · ${r.run} · ${r.generated_at||'미기록'} · ${Object.entries(r.datasets||{}).map(([k,v])=>`${k} ${n(v)}건`).join(' / ')}`,'small'));
        body.append(provenance);
      }
      body.append(node('p','모델 이름을 누르면 해당 회차의 A05 상세로 이동합니다. 분류 저장과 Analysis 전체 완료는 구분하며, 비교표는 저장된 응답 결과입니다. 문항 답변가능성 gold나 의미적 정답률이 아닙니다.','scope-note'));
    }catch(e){if(token===generation)body.replaceChildren(node('p',e.message,'scope-note'));}
  }
  select.addEventListener('change',show);cohort.addEventListener('change',show);await show();return panel;
}
