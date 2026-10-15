(() => {
  const panel = document.createElement('details');
  panel.id = 'experiments-panel';
  panel.style.cssText = 'margin:16px;padding:16px;border:2px solid #327365;border-radius:8px;background:#fff';
  const title = document.createElement('summary'); title.textContent = '실험 1·2 — 실행 보고서와 실제 응답'; panel.append(title);
  const controls = document.createElement('div'); controls.style.margin = '12px 0';
  const run = document.createElement('select'), model = document.createElement('select');
  const refresh = document.createElement('button'); refresh.textContent = '새로 읽기';
  controls.append(run, model, refresh); panel.append(controls);
  const status = document.createElement('p'), report = document.createElement('pre'), table = document.createElement('div');
  report.style.cssText = 'white-space:pre-wrap;max-height:420px;overflow:auto';
  const reportDetails = document.createElement('details'), reportTitle = document.createElement('summary');
  reportTitle.textContent = '취합 보고서 원문'; reportDetails.append(reportTitle, report);
  const previous = document.createElement('button'), next = document.createElement('button');
  previous.textContent = '이전 25건'; next.textContent = '다음 25건';
  panel.append(status, reportDetails, previous, next, table);
  document.querySelector('header')?.after(panel);
  let offset = 0, busy = false;
  async function get(url) { const r = await fetch(url); if (!r.ok) throw new Error('보고서를 읽지 못했습니다.'); return r.json(); }
  function option(select, value) { const o = document.createElement('option'); o.value = value; o.textContent = value; select.append(o); }
  async function load() {
    if (busy) return; busy = true;
    try {
      const all = await get('/api/experiments/runs'), selected = run.value;
      run.replaceChildren(); all.forEach(r => option(run, r.run_id)); if (all.some(r => r.run_id === selected)) run.value = selected;
      if (!run.value) { status.textContent = '아직 실험 실행 기록이 없습니다.'; return; }
      const result = await get('/api/experiments/run?name=' + encodeURIComponent(run.value));
      const currentModel = model.value; model.replaceChildren(); result.summary.models.forEach(m => option(model, m.model));
      if (result.summary.models.some(m => m.model === currentModel)) model.value = currentModel;
      const m = result.summary.models.find(m => m.model === model.value);
      status.textContent = `전체 ${result.summary.status} · ${result.summary.originals}원문 / ${result.summary.variants}변형 · ${m.model} ${m.provider_state?.status || ''}: ${JSON.stringify(m.statuses)} · 입력 ${m.input_tokens}, 출력 ${m.output_tokens_including_thinking}토큰 · 유료 Batch 추정 $${m.paid_batch_usage_cost_estimate_usd || 0} · 전체 API 환산 $${m.api_equivalent_usd} · 청구액 미확인`;
      report.textContent = result.report;
      const data = await get('/api/experiments/results?name=' + encodeURIComponent(run.value) + '&model=' + encodeURIComponent(model.value) + '&offset=' + offset);
      const expanded = new Set([...table.querySelectorAll('details[open]')].map(d => d.dataset.trialId));
      table.replaceChildren();
      for (const row of data.rows) {
        const d = document.createElement('details'), s = document.createElement('summary'), p = document.createElement('pre');
        d.dataset.trialId = row.trial_id; d.open = expanded.has(row.trial_id);
        const prompt = row.prompt_condition === 'P0' ? 'Unguided Solving' : row.prompt_condition === 'P1' ? 'Criteria-Guided Solving' : row.prompt_condition;
        const reasoning = row.reasoning === 'off' ? 'Reasoning OFF' : row.reasoning === 'on' ? 'Reasoning ON' : row.reasoning;
        s.textContent = `${row.case} / ${row.variant} / ${prompt} / ${reasoning} — ${row.status}`;
        p.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere'; p.textContent = JSON.stringify(row, null, 2);
        d.append(s, p); table.append(d);
      }
      previous.disabled = offset === 0; next.disabled = offset + 25 >= data.total;
    } catch (e) { status.textContent = e.message; } finally { busy = false; }
  }
  run.onchange = model.onchange = () => { offset = 0; load(); }; refresh.onclick = load;
  previous.onclick = () => { offset = Math.max(0, offset - 25); load(); }; next.onclick = () => { offset += 25; load(); };
  panel.ontoggle = () => { if (panel.open) load(); };
  if (new URLSearchParams(location.search).has('experiments')) { panel.open = true; load(); }
  setInterval(() => { if (panel.open && !document.hidden) load(); }, 15000);
})();
