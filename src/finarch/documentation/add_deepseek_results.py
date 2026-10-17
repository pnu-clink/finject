"""Add the saved DeepSeek run to the paper, without model calls or run writes.

The aggregate command verifies the released inputs and preserves unavailable
assessments. Paper changes are staged separately from the working manuscript.
"""
from pathlib import Path
from importlib import import_module
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import copy
import csv
import hashlib
import json
import base64
import re

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = '20261009-exp-002-finject-deepseek-v4-1-flash-max'
RUN = ROOT / 'reports/experiments-run' / RUN_ID
BASE = ROOT / 'reports/analysis/20261008-finject-1354'
OUT = ROOT / 'reports/analysis/20261012-finject-deepseek-addition'
STAGE = ROOT / 'paper/asset/.build/deepseek-results-20261012'
LABEL = 'DeepSeek'
FULL_NAME = 'DeepSeek V4.1 Flash'
MODEL_ORDER = ['Luna','Haiku',LABEL,'Qwen3-8B','Qwen3-14B','Qwen3.8-27B']

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def lines(path):
    with Path(path).open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def aggregate():
    import numpy as np
    f = import_module('finarch.experiments.02-analysis.01-results.final_cohort')
    f.MODELS = ((LABEL, None, None),)
    recorded = read(RUN/'02_analysis/05_outcomes/summary.json')
    response_path = RUN/'02_analysis/05_outcomes/responses.jsonl'
    assert sha(response_path) == recorded['output_hashes']['responses.jsonl']
    source_paths = [BASE/'summary.json', response_path,
                    RUN/'02_analysis/05_outcomes/summary.json', RUN/'config.json',
                    RUN/'02_analysis/config.json', RUN/'02_analysis/02_comparison/state.json',
                    RUN/'02_analysis/02_comparison/response-assessment-summary.json',
                    ROOT/'data/final/finject-20261007/dataset.jsonl',
                    ROOT/'data/final/finject-20261007/EA_INVERSE_REVIEW.jsonl',
                    RUN/'00_input/public.jsonl']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    public = {r['item_id']: r for r in lines(RUN/'00_input/public.jsonl')}
    source_datasets = {}
    total_items = 0
    for family in lines(ROOT/'data/final/finject-20261007/dataset.jsonl'):
        source_datasets[family['id']] = family.get('source_dataset')
        for item in [family['original'], *family['variants']]:
            frozen = public[item['item_id']]
            assert all(item[k] == frozen[k] for k in ('question', 'context'))
            total_items += 1
    assert total_items == 10832 and len(public) == total_items
    rows = []
    for r in lines(response_path):
        compact = {k:v for k,v in r.items() if k not in ('assessment','independent_item_review')}
        rows.append(compact | {'model_label': LABEL, 'final_id': r['case'],
                              'final_item_id': r['item_id'], 'configured_condition': True})
    assert len(rows) == 43328
    assert {r['final_id'] for r in rows} == set(source_datasets)
    summary = f.aggregates(rows)
    assert Counter(r['nasu'] for r in rows) == Counter(recorded['scopes']['all']['nasu'])
    keys = {(r['final_id'],r['prompt_condition'],r['reasoning'],r['variant']):r for r in rows}
    ids = sorted(source_datasets)
    def category(r):
        if r['target_status'] != 'VALID': return 'X'
        if r['action'] == 'A': return 'A'
        if r['action'] == 'N' and r['original_reference_match'] is True: return 'M'
        if r['action'] == 'N' and r['original_reference_match'] is False: return 'W'
        return 'X'
    pairs = []
    for g, rr in f.CONDITIONS:
        for number, (before, after) in enumerate(f.PAIRS, 1):
            transitions, excluded = Counter(), Counter()
            for fid in ids:
                b=category(keys[(fid,g,rr,before)]); a=category(keys[(fid,g,rr,after)])
                (excluded if 'X' in (a,b) else transitions)[b+'->'+a] += 1
            n=sum(transitions.values())
            cb={c:sum(v for k,v in transitions.items() if k.startswith(c)) for c in 'MWA'}
            ca={c:sum(v for k,v in transitions.items() if k.endswith(c)) for c in 'MWA'}
            assert n + sum(excluded.values()) == 1354
            pairs.append(dict(model=LABEL,G=g,R=rr,pair=number,n=n,planned=1354,
                before=cb,after=ca,transitions=dict(transitions),excluded=dict(excluded),
                delta_pp={c:100*(ca[c]-cb[c])/n if n else None for c in 'MWA'}))
    flags={}
    for r in lines(ROOT/'data/final/finject-20261007/EA_INVERSE_REVIEW.jsonl'):
        for v in r['variants']:
            variant=v.get('variant') or v.get('type') or v['item_id'].rsplit(':',1)[1]
            flags[(r['id'],variant)]=v.get('inverse_possible')
    main_off={k[0:1]+k[3:]:r for k,r in keys.items() if k[1:3]==('unguided','off') and r['variant'] in f.MAIN}
    main_on={k[0:1]+k[3:]:r for k,r in keys.items() if k[1:3]==('unguided','on') and r['variant'] in f.MAIN}
    new=[k for k,r in main_on.items() if r['nasu']=='NS' and main_off[k]['nasu'] in ('NU','AS','AU')]
    ir=[k for k in new if k[1] in ('EA_01','EA_02')]
    eligible=[k for k,r in main_on.items() if k[1] in ('EA_01','EA_02') and r['nasu'] in f.RESOLVED and main_off[k]['nasu'] in ('NU','AS','AU')]
    strata={b:[k for k in eligible if flags.get(k) is b] for b in (True,False)}
    num={b:sum(main_on[k]['nasu']=='NS' for k in strata[b]) for b in (True,False)}
    clusters=defaultdict(lambda:np.zeros(4,dtype=int))
    for b in (True,False):
        idx=0 if b else 2
        for k in strata[b]:
            clusters[k[0]][idx]+=int(main_on[k]['nasu']=='NS')
            clusters[k[0]][idx+1]+=1
    arr=np.array([clusters[fid] for fid in sorted(clusters)])
    rng=np.random.default_rng(20261009)
    estimates=[]
    for _ in range(10000):
        t=arr[rng.integers(0,len(arr),len(arr))].sum(axis=0)
        if t[1] and t[3]: estimates.append(100*(t[0]/t[1]-t[2]/t[3]))
    assoc=dict(model=LABEL,inverse_new=num[True],inverse_eligible=len(strata[True]),
        noninverse_new=num[False],noninverse_eligible=len(strata[False]),
        delta_pp=100*(num[True]/len(strata[True])-num[False]/len(strata[False])),
        ci95_pp=np.percentile(estimates,[2.5,97.5]).tolist(),original_clusters=len(clusters),
        unknown_eligible=sum(flags.get(k) not in (True,False) for k in eligible),
        bootstrap_samples=10000,seed=20261009)
    inverse=dict(model=LABEL,NS_off=sum(r['nasu']=='NS' for r in main_off.values()),
        NS_on=sum(r['nasu']=='NS' for r in main_on.values()),new_NS_confirmed=len(new),new_NS_ER=len(ir),
        ER_share_new_NS=len(ir)/len(new),inverse_true=sum(flags.get(k) is True for k in ir),
        inverse_false=sum(flags.get(k) is False for k in ir),
        inverse_unknown=sum(flags.get(k) not in (True,False) for k in ir),
        new_NS_unresolved_baseline=sum(r['nasu']=='NS' and main_off[k]['nasu'] not in f.RESOLVED for k,r in main_on.items()))
    inverse['inverse_true_share_all_new_NS']=inverse['inverse_true']/len(new)
    ic=[]
    variants=[]
    for g, rr in f.CONDITIONS:
        identity={'model':LABEL,'G':'ON' if g=='guided' else 'OFF','R':rr.upper()}
        ic.append(identity|f.counts([r for r in rows if r['prompt_condition']==g and r['reasoning']==rr and r['variant'] in f.MAIN[:3]]))
        for v in f.MAIN:
            variants.append(identity|{'variant':v}|f.counts([r for r in rows if r['prompt_condition']==g and r['reasoning']==rr and r['variant']==v]))
    combined=read(BASE/'summary.json')
    for k in ('models','rq1','rq2','rq3','aggregates','scopes','coverage'):combined[k]+=summary[k]
    now=datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
    combined['generated_at']=now
    combined['additional_run']=RUN_ID
    combined['paper_models']=MODEL_ORDER
    combined['new_model_calls']=0
    review_state = read(RUN/'02_analysis/02_comparison/state.json')
    review_counts = Counter(r['review_status'] for r in rows if r['variant'] != 'ORIGINAL')
    assert sum(review_counts.values()) == 37912
    combined['runs'].append({'run':RUN_ID,'model_label':LABEL,'target_model':'deepseek/deepseek-v4.1-flash',
        'selected_families':1354,'stored_planned_responses':43328,
        'a02_state':f.compact_state(review_state)})
    rank={m:i for i,m in enumerate(MODEL_ORDER)}
    combined['models']=sorted(combined['models'],key=lambda m:rank.get(m,len(rank)))
    for k in ('rq1','rq2','rq3','aggregates','scopes','coverage','runs'):
        combined[k].sort(key=lambda r:rank.get(r.get('model',r.get('model_label')),len(rank)))
    for rel,digest in hashes.items():assert sha(ROOT/rel)==digest,rel
    OUT.mkdir(parents=True,exist_ok=True)
    write(OUT/'deepseek-summary.json',summary|{'source_pairs':pairs,'inverse':inverse,'association':assoc,
        'conflicts':ic,'variants':variants,'review_counts':dict(review_counts),
        'review_state':f.compact_state(review_state)})
    write(OUT/'summary.json',combined)
    write(OUT/'manifest.json',{'generated_at':now,'new_model_calls':0,'source_hashes':hashes,
        'base_snapshot':str(BASE.relative_to(ROOT)), 'added_run':RUN_ID,
        'verified':{'frozen_questions_contexts_equal_final':True,'all_43328_slots_preserved':True,
        'saved_outcome_hash_equal':True,'saved_nasu_counts_equal':True,'input_hashes_unchanged':True},
        'outputs':{n:sha(OUT/n) for n in ('summary.json','deepseek-summary.json')}})
    with (OUT/'responses.jsonl').open('w') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    template = ROOT/'src/finarch/documentation/templates/deepseek-results-addition.md'
    (OUT/'README.md').write_text(template.read_text().format(
        run_id=RUN_ID, valid=review_state['valid'],
        reviewed=review_counts['COMPLETED'], failed=review_counts['NOT_REVIEWABLE'],
        pending=review_counts['REVIEW_FAILED']))
    with (OUT/'execution.log').open('a') as log:
        log.write(json.dumps({'at':now,'event':'saved_results_verified_and_aggregated',
            'source_outcomes_sha256':hashes[str(response_path.relative_to(ROOT))],
            'planned_responses':43328,'assessment_counts':dict(review_counts),
            'new_model_calls':0},ensure_ascii=False)+'\n')
    print(json.dumps({'support':[{k:r[k] for k in ['G','R','NS','NU','AS','AU','D','F','N','A','O','resolved']} for r in summary['rq1']],
        'review_counts':dict(review_counts),'inverse':inverse,'association':assoc},ensure_ascii=False))

def plots():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    s=read(OUT/'summary.json')
    models=MODEL_ORDER
    labels=['gpt-6-\nluna','claude-\nhaiku-4.5','deepseek-\n4.1-flash','Qwen3-\n8B','Qwen3-\n14B','Qwen3.8-\n27B']
    q={(r['model'],r['G'],r['R']):r for r in s['rq1']}
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none'})
    STAGE.mkdir(parents=True,exist_ok=True)
    names={}
    def save(fig,name):
        for ext in ('pdf','svg','png'):fig.savefig(STAGE/(name+'.'+ext),dpi=180)
        plt.close(fig)
    for suffix,sz,title in [('support',(11,4.75),'G⁻R⁺: Abstention support and AS\nshare across all items'),
                            ('reasoning',(12.5,374/72),'G⁻R⁻ → G⁻R⁺: larger gains in supported\nnumeric-answers in every model')]:
        fig,ax=plt.subplots(figsize=sz);fig.subplots_adjust(left=.11,right=.985,top=.72,bottom=.39)
        fig.text(.022,.985,title,va='top',fontsize=23,weight='bold')
        x=np.arange(6);width=.36
        if suffix=='support':
            a=[100*q[m,'OFF','ON']['A'] for m in models];b=[100*q[m,'OFF','ON']['AS_share'] for m in models]
            legend=['Support among abstentions: AS/(AS+AU)','Supported abstentions across all items: AS/T']
            ax.set_ylim(0,120);ax.set_yticks([0,50,100]);ax.set_ylabel('Percent (%)',fontsize=19)
        else:
            a=[100*(q[m,'OFF','ON']['NS_share']-q[m,'OFF','OFF']['NS_share']) for m in models]
            b=[100*(q[m,'OFF','ON']['AS_share']-q[m,'OFF','OFF']['AS_share']) for m in models]
            legend=['Δ NS/T: supported numeric-answers','Δ AS/T: supported abstentions']
            ax.set_ylim(0,18);ax.set_yticks([0,5,10,15]);ax.set_ylabel('Increase (%p)',fontsize=19)
        for xx,vals,color,lab in [(x-width/2,a,'#4c78a8',legend[0]),(x+width/2,b,'#e6a245',legend[1])]:
            bars=ax.bar(xx,vals,width,color=color,label=lab,zorder=3)
            for bar,v in zip(bars,vals):ax.text(bar.get_x()+width/2,v+(2 if suffix=='support' else .25),f'{v:.1f}' if suffix=='support' else f'+{v:.1f}',ha='center',fontsize=18)
        ax.set_xticks(x,labels,fontsize=17);ax.tick_params(axis='y',labelsize=17)
        ax.grid(axis='y',color='#e5e9ed',zorder=0);ax.spines[['top','right']].set_visible(False)
        ax.spines[['bottom','left']].set_color('#777777')
        fig.legend(loc='lower left',bbox_to_anchor=(.01,.0),fontsize=19,frameon=False,handlelength=1)
        name='FigureA7-v2-support-six-models' if suffix=='support' else 'FigureA8-v2-reasoning-six-models'
        save(fig,name);names['fig:abstention-support-share' if suffix=='support' else 'fig:nasu-gr-bars']=name
    fig,axes=plt.subplots(1,2,figsize=(4.5,1.6),sharey=True)
    fig.subplots_adjust(left=.13,right=.985,top=.80,bottom=.36,wspace=.30)
    colors=['#4c78a8','#e6a245','#c4473f','#54a24b','#b279a2','#8996a5']
    marks=['o','s','P','^','D','v']
    for ax,r,title in zip(axes,['OFF','ON'],['(a) R⁻ fixed','(b) R⁺ fixed']):
        for m,color,mark in zip(models,colors,marks):
            ax.plot([0,1],[q[m,'OFF',r]['AS_share']*100,q[m,'ON',r]['AS_share']*100],marker=mark,color=color,lw=.9,ms=3,label=('claude-haiku-4.5' if m=='Haiku' else m))
        ax.set_title(title,fontsize=9,weight='bold');ax.set_xticks([0,1],['G−','G+']);ax.set_ylim(0,100);ax.set_yticks([0,25,50,75,100]);ax.tick_params(labelsize=7)
        ax.grid(axis='y',color='#e5e9ed',lw=.5);ax.spines[['top','right']].set_visible(False)
        ax.spines[['bottom','left']].set_color('#aaaaaa')
    axes[0].set_ylabel('AS/T (%)',fontsize=8)
    handles,legend_labels=axes[0].get_legend_handles_labels()
    # Matplotlib fills legends by column, reorder handles for row-wise reading.
    legend_order=[0,3,1,4,2,5]
    fig.legend([handles[i] for i in legend_order],[legend_labels[i] for i in legend_order],
        loc='lower center',ncol=3,fontsize=6.2,frameon=False,handlelength=1.2,columnspacing=1)
    name='FigureA9-v2-guidance-six-models';save(fig,name);names['fig:gr-fixed-lines']=name
    write(STAGE/'plots.json',names)

def stage_paper():
    from bs4 import BeautifulSoup
    s=read(OUT/'deepseek-summary.json')
    source=ROOT/'reports/run/20261003-paper-revision-draft/paper-review.json'
    ss=read(source)
    assert not any(RUN_ID in section['enhtml'] for section in ss), 'DeepSeek is already published in the Draft'
    write(STAGE/'paper-review-before.json',ss)
    write(STAGE/'source-state.json',{'path':str(source.relative_to(ROOT)),'sha256':sha(source)})
    q={(r['G'],r['R']):r for r in s['rq1']};orig={(r['G'],r['R']):r for r in s['rq2']}
    pairs={(r['G'],r['R'],r['pair']):r for r in s['source_pairs']}
    retention={(r['G'],r['R'],r['pair']):r for r in s['rq3']}
    conflicts={(r['G'],r['R']):r for r in s['conflicts']}
    conditions=[('OFF','OFF'),('OFF','ON'),('ON','OFF'),('ON','ON')]
    inv=s['inverse'];assoc=s['association'];pnames=read(STAGE/'plots.json')
    pooled=read(OUT/'summary.json')
    model_names=MODEL_ORDER
    all_support={(r['model'],r['G'],r['R']):r for r in pooled['rq1']}
    def support_range(g,r,metric):
        values=[100*all_support[m,g,r][metric] for m in model_names]
        return f'{min(values):.1f}–{max(values):.1f}'
    def guidance_range(r):
        values=[100*(all_support[m,'ON',r]['AS_share']-all_support[m,'OFF',r]['AS_share'])
                for m in model_names if r=='ON' or m!='Luna']
        return f'{min(values):.1f}–{max(values):.1f}'
    group_comparisons=[r for r in pooled['rq2'] if r['model'] in model_names]
    positive=sum(r['delta_pp']>0 for r in group_comparisons)
    def pct(x):return 'N/A' if x is None else f'{100*x:.1f}'
    def signed(x):return 'N/A' if x is None else f'{x:+.1f}'.replace('-', '−')
    def frac(n,d):return f'{pct(n/d) if d else "N/A"}% ({n:,}/{d:,})'
    def gr(g,r):return 'G<sup>'+('+' if g=='ON' else '−')+'</sup>R<sup>'+('+' if r=='ON' else '−')+'</sup>'
    def row(doc,values):
        tr=doc.new_tag('tr');tr['data-result-run']=RUN_ID
        for v in values:
            td=doc.new_tag('td');td['style']='text-align:center;vertical-align:middle;white-space:nowrap;';td['data-nowrap']='true'
            for child in list(BeautifulSoup(str(v),'html.parser').contents):td.append(child.extract())
            tr.append(td)
        return tr
    def append(doc,tid,values):
        t=doc.find('table',id=tid)
        if t is None:return
        dest=t.find('tbody') or t
        following=next((r for r in dest.find_all('tr')
                        if r.find(['td','th']) and r.find(['td','th']).get_text(strip=True).startswith('Qwen')),None)
        for v in values:
            new=row(doc,v)
            if following:following.insert_before(new)
            else:dest.append(new)
    changed=[]
    for section in ss:
      before=copy.deepcopy(section)
      for lang in ('en','ko'):
        doc=BeautifulSoup(section[lang+'html'],'html.parser')
        for text in list(doc.find_all(string=True)):
            if text.find_parent(['table','figure','pre','code','script','style']):continue
            value=str(text)
            for a,b in [('five models','six models'),('five target models','six target models'),('Five models.','Six models.'),('Five target models','Six target models')]:value=value.replace(a,b)
            value=value.replace('85.8–98.9%',support_range('ON','ON','A')+'%')
            value=value.replace('79.5–98.1%',support_range('OFF','ON','A')+'%')
            if section['id']=='s5':
                value=value.replace('Luna, Haiku, Qwen3-8B','Luna, Haiku, DeepSeek, Qwen3-8B')
                value=value.replace('Luna·Haiku·Qwen3-8B','Luna·Haiku·DeepSeek·Qwen3-8B')
                value=value.replace('Luna, Haiku, Qwen3-8B','Luna, Haiku, DeepSeek, Qwen3-8B')
            if section['id']=='s11-results-rq2':
                value=value.replace('the October 8, 2026 paper-response snapshot','the October 8, 2026 snapshot for the existing models and the October 12 DeepSeek snapshot')
                value=value.replace('2026-10-08 \ub17c\ubb38 \uc751\ub2f5 \uc2a4\ub0c5\uc0f7','The existing model. 2026-10-08 And the answer is snapshots and DeepSeek. 2026-10-12 Snapshots.')
                value=value.replace('the October 8, 2026 stored paper results','the existing models’ October 8, 2026 results and DeepSeek’s October 12 results')
                value=value.replace('2026\ub144 10\uc6d4 8\uc77c \ub17c\ubb38\uc6a9 \uc800\uc7a5 \uacb0\uacfc\uc758','The existing model. 2026Shit. 10month 8And the results of the work and the DeepSeek 10month 12And the results of the work.')
                value=value.replace('0.4–5.3',guidance_range('OFF')).replace('34.1–54.0',guidance_range('ON'))
            if section['id']=='s11-results-rq3':
                value=value.replace('15 of 20',f'{positive} of {len(group_comparisons)}')
                value=value.replace('20\uac1c \ube44\uad50 \uc911 15\uac1c',f'{len(group_comparisons)}comparisons {positive}items')
            if section['id']=='s11-experimental-settings':
                value=value.replace('We disabled automatic retries in Evaluation.','We disabled automatic retries in Qwen Evaluation.').replace('Evaluation\uc758 \uc790\ub3d9 \uc7ac\uc2dc\ub3c4\ub294 \ube44\ud65c\uc131\ud654\ud588\ub2e4.','Automatic re-enabling of Qwen Evaluation has been disabled.')
            text.replace_with(value)
        on=q['ON','ON'];off=q['OFF','OFF'];reason=q['OFF','ON']
        append(doc,'tab:v2-support',[[LABEL,pct(on['N']),pct(on['A']),pct(on['resolved']/6770)]])
        append(doc,'tab:v2-reasoning',[[LABEL,signed(100*(reason['NS_share']-off['NS_share'])),signed(100*(reason['AS_share']-off['AS_share']))]])
        append(doc,'tab:v2-guidance',[[LABEL,*[pct(conflicts[c]['AS_share']) for c in conditions]]])
        append(doc,'tab:v2-source',[[LABEL,signed(pairs['guided','on',1]['delta_pp']['M']),signed(pairs['guided','on',2]['delta_pp']['W'])]])
        for tid in ['tab:v2-support','tab:v2-reasoning','tab:v2-guidance','tab:v2-source']:
            t=doc.find('table',id=tid)
            if t:t['data-pdf-row-spacing']='1.0'
        append(doc,'tab:finject-coverage',[[LABEL,gr(*c),'6,770',f'{q[c]["reviewed"]:,}',str(q[c]['D']),str(q[c]['F']),f'{pct(q[c]["NS_share"])}({q[c]["NS"]:,}/6,770)',f'{pct(q[c]["AS_share"])}({q[c]["AS"]:,}/6,770)'] for c in conditions])
        append(doc,'tab:finject-rq1',[[LABEL,gr(*c),pct(q[c]['O']),f'{q[c]["resolved"]:,}',f'{pct(q[c]["N"])} ({q[c]["NS"]:,} / {q[c]["NS"]+q[c]["NU"]:,})',f'{pct(q[c]["A"])} ({q[c]["AS"]:,} / {q[c]["AS"]+q[c]["AU"]:,})',f'{pct(q[c]["NS_share"])} ({q[c]["NS"]:,} / 6,770)',f'{pct(q[c]["AS_share"])} ({q[c]["AS"]:,} / 6,770)',str(q[c]['D']),str(q[c]['F'])] for c in conditions])
        vnames={'IC_VALUE_01_BEFORE':'IC-v,f','IC_VALUE_01_AFTER':'IC-v,b','IC_RELATION_01':'IC-r','EA_01':'IR-1','EA_02':'IR-2'}
        append(doc,'tab:v2-variant-counts',[[LABEL,vnames[r['variant']],*[f'{r[k]:,}' for k in ['NS','NU','AS','AU','D','F']]] for r in s['variants'] if (r['G'],r['R'])==('ON','ON')])
        gainrows=[]
        for r,rl in [('OFF','R⁻'),('ON','R⁺')]:
            a=q['OFF',r];o=orig['OFF',r]
            gainrows.append([LABEL if r=='OFF' else '',rl,frac(o['originals']['CORRECT'],1354),frac(a['NS'],6770),frac(a['AS'],6770)])
        gains=[100*(orig['OFF','ON']['O']-orig['OFF','OFF']['O']),100*(reason['NS_share']-off['NS_share']),100*(reason['AS_share']-off['AS_share'])]
        append(doc,'tab:reasoning-gains-full',gainrows+[['','Δ',*[signed(v) for v in gains]]])
        t=doc.find('table',id='tab:reasoning-gains-full')
        if t:t['data-pdf-row-spacing']='1.05'
        append(doc,'table-s5-2-original-reasoning',[[LABEL,f'{pct(orig["OFF","OFF"]["O"])} → {pct(orig["OFF","ON"]["O"])} ({signed(gains[0])})',f'{pct(off["NS_share"])} → {pct(reason["NS_share"])} ({signed(gains[1])})',f'{pct(off["AS_share"])} → {pct(reason["AS_share"])} ({signed(gains[2])})']])
        iv=[LABEL,f'{inv["NS_off"]:,} → {inv["NS_on"]:,}',str(inv['new_NS_confirmed']),f'{inv["new_NS_ER"]}/{inv["new_NS_confirmed"]}({pct(inv["ER_share_new_NS"])}%)',f'{inv["inverse_true"]}/{inv["new_NS_confirmed"]}({pct(inv["inverse_true_share_all_new_NS"])}%)']
        append(doc,'table-s5-2-1',[iv])
        append(doc,'table-s11-results-rq2-1',[iv+[f'{assoc["inverse_new"]}/{assoc["inverse_eligible"]} ({pct(assoc["inverse_new"]/assoc["inverse_eligible"])}%)',f'{assoc["noninverse_new"]}/{assoc["noninverse_eligible"]} ({pct(assoc["noninverse_new"]/assoc["noninverse_eligible"])}%)',signed(assoc['delta_pp']),f'[{assoc["ci95_pp"][0]:.1f}, {assoc["ci95_pp"][1]:.1f}]',str(assoc['unknown_eligible'])]])
        append(doc,'table-s11-results-rq2-2',[[LABEL,*[f'{conflicts[c]["AS"]:,}/4,062 ({100*conflicts[c]["AS_share"]:.2f}%)' for c in conditions],str(conflicts['ON','ON']['NU']),str(conflicts['ON','ON']['F'])]])
        append(doc,'table-s5-2-guidance-reasoning',[[LABEL,*[pct(q[c]['AS_share']) for c in conditions]]])
        append(doc,'tab:v2-source-outcomes',[[LABEL,gr('ON' if r['G']=='guided' else 'OFF',r['R'].upper()),f'IC-s{r["pair"]}',f'{r["n"]:,}',str(1354-r['n']),*[f'{r["before"][k]:,} → {r["after"][k]:,}' for k in 'MWA']] for r in s['source_pairs']])
        append(doc,'tab:finject-rq3',[[LABEL,gr(r['G'],r['R']),str(r['pair']),f'{r["n"]:,}',f'{r["before"]:,}',f'{r["after"]:,}',f'{r["retained"]:,}',str(r['new']),frac(r['retained'],r['before']),str(r['excluded'].get('D',0)),str(r['excluded'].get('F',0))] for r in s['rq3']])
        t=doc.find('table',id='tab:retention-complete')
        if t:
            for i,c in enumerate(conditions):
                a=retention[*c,1];b=retention[*c,2]
                rr=row(doc,([LABEL] if i==0 else [])+[gr(*c),f'{a["before"]:,}/{a["n"]:,}',frac(a['retained'],a['before']),f'{b["before"]:,}/{b["n"]:,}',frac(b['retained'],b['before'])])
                if i==0:rr.td['rowspan']='4'
                dest=t.find('tbody') or t
                following=next((r for r in dest.find_all('tr') if r.find('td') and r.td.get_text(strip=True).startswith('Qwen')),None)
                if following:following.insert_before(rr)
                else:dest.append(rr)
        append(doc,'tab:finject-rq2',[[LABEL,gr(*c),*[f'{orig[c]["originals"][k]:,}' for k in ['CORRECT','INCORRECT','UNKNOWN']],pct(orig[c]['C']['O']),f'{orig[c]["C"]["S"]:,}/{orig[c]["C"]["resolved"]:,}',pct(orig[c]['I']['O']),f'{orig[c]["I"]["S"]:,}/{orig[c]["I"]["resolved"]:,}',signed(orig[c]['delta_pp'])] for c in conditions])
        # Matrix tables retain their rows and receive a new model column group.
        for tid,kind in [('table-s5-1-1','support'),('table-s5-4-1','retention'),('table-s5-3-1','original')]:
            t=doc.find('table',id=tid)
            if not t:continue
            if kind!='original':t['data-layout']='two-column'
            trs=t.find_all('tr');header=doc.new_tag('th');header.string=LABEL;header['style']='text-align:center;'
            if kind!='original':header['colspan']='2'
            trs[0].append(header)
            if kind!='original':
                for label in (['N','A'] if kind=='support' else ['R1','R2']):
                    th=doc.new_tag('th');th.string=label;trs[1].append(th)
            for i,c in enumerate(conditions):
                if kind=='support':
                    nd=q[c]['NS']+q[c]['NU'];ad=q[c]['AS']+q[c]['AU']
                    vals=[]
                    for metric,d,other in [('N',nd,ad),('A',ad,nd)]:
                        den=f'({d:,})'
                        if d>other:den='<u>'+den+'</u>'
                        vals.append(f'<span style="display:block">{pct(q[c][metric])}</span><small style="display:block;font-size:10px;">{den}</small>')
                else:vals=([pct(retention[*c,p]['retention']) for p in [1,2]] if kind=='retention' else [signed(orig[c]['delta_pp'])])
                for cell in list(row(doc,vals).find_all('td',recursive=False)):trs[i+(1 if kind=='original' else 2)].append(cell.extract())
            # Put the new column group after Haiku, preserving all old cells.
            header.extract()
            first_qwen=next(c for c in trs[0].find_all('th',recursive=False) if c.get_text(strip=True).startswith('Qwen'))
            first_qwen.insert_before(header)
            width=1 if kind=='original' else 2
            prefix=len(trs[0].find_all('th',recursive=False))-6
            for ri,tr in enumerate(trs[1:]):
                cells=tr.find_all(['td','th'],recursive=False)
                insert_at=4 if kind!='original' and ri==0 else prefix+4
                if kind=='original':insert_at=prefix+2
                moving=cells[-width:]
                target=cells[insert_at]
                for cell in moving:target.insert_before(cell.extract())
        append(doc,'tab:api-generation',[[LABEL,'none','max','8,194–262,144']])
        if section['id']=='s11-experimental-settings':
            t=doc.find('table',id='tab:api-generation')
            msg=('We request DeepSeek V4.1 Flash through OrcaRouter with reasoning effort none or max. The run initially uses a 65,536-token output limit and later starts new requests at 8,194 tokens, doubling the limit after length truncation. Recorded final-attempt limits range from 8,194 to 262,144 tokens. We preserve failed outputs and all attempts.' if lang=='en' else 'DeepSeek V4.1 Flash calls the reasoning effort none or max through OrcaRouter. 65,536 tokens, and then the new request is 8,194 If you start with tokens and cut the length limit, you double the limit. 8,194–262,144 Tokens. Failed output and all attempts are preserved.')
            t.insert_after(BeautifulSoup('<p>'+msg+'</p>','html.parser'))
        if section['id']=='s11-pooled-results':
            c=s['review_counts']
            assert s['review_state']['valid']==1354 and c.get('REVIEW_FAILED',0)==0
            msg=(f'DeepSeek has assessment results for all 1,354 original families. Of 37,912 planned variant responses, {c["COMPLETED"]:,} have completed assessments and {c["NOT_REVIEWABLE"]:,} outputs are unreviewable. For the five base variants under G⁺R⁻, F contains {q["ON","OFF"]["F"]:,} invalid outputs. We retain these cases in the planned denominator. We preserve the October 8 snapshot for the existing models and use the October 12 snapshot for DeepSeek.' if lang=='en' else f'DeepSeek is the original. 1,354All items have analytical results. 37,912of {c["COMPLETED"]:,}The items has completed the assessment, and the output is {c["NOT_REVIEWABLE"]:,}items can\x27t review. In the five basic variations of G+R−, F is the output that doesn\x27t fit the form. {q["ON","OFF"]["F"]:,}This item is also left in the plan denominator. 10month 8Keeping up with the work snapshots, DeepSeek is 10month 12I use work snapshots.')
            doc.insert(0,BeautifulSoup('<p>'+msg+'</p>','html.parser'))
        for fid,name in pnames.items():
            figure=doc.find('figure',id=fid)
            if not figure:continue
            figure['data-figure-file']='paper/asset/figures/v2/'+name+'.pdf'
            figure['data-figure-sha256']=sha(STAGE/(name+'.pdf'))
            figure.img['src']='data:image/png;base64,'+base64.b64encode((STAGE/(name+'.png')).read_bytes()).decode()
        normalized=str(BeautifulSoup(before[lang+'html'],'html.parser'))
        if str(doc)!=normalized:section[lang+'html']=str(doc)
      if section!=before:changed.append(section['id'])
    write(STAGE/'paper-review.json',ss)
    write(STAGE/'changed-sections.json',changed)
    print('Staged',len(changed),'sections',changed)

def publish():
    """Publish the checked snapshot without replacing unrelated manuscript edits."""
    import re
    import shutil
    from bs4 import BeautifulSoup
    from finarch.documentation.draft_editor import DraftRepository, EMBEDDED
    repo=DraftRepository(ROOT)
    state=read(STAGE/'source-state.json')
    assert sha(repo.source)==state['sha256'], 'Draft changed, refresh staging before publishing'
    before=read(STAGE/'paper-review-before.json');sections=read(STAGE/'paper-review.json')
    old={s['id']:s for s in before};new={s['id']:s for s in sections}
    changed=read(STAGE/'changed-sections.json')
    text=(STAGE/'paper-review.json').read_text()
    assert sha(STAGE/'paper-review.json') in (STAGE/'latex/main.tex').read_text(), 'PDF source differs from staged Draft'
    updates={repo.source:text}
    def markdown_html(section,lang):
        doc=BeautifulSoup(section[lang+'html'],'html.parser')
        for fid,name in read(STAGE/'plots.json').items():
            f=doc.find('figure',id=fid)
            if f and f.img:f.img['src']='../../../paper/asset/figures/v2/'+name+'.png'
        return str(doc)
    for lang,name in [('en','PAPER-EN.md'),('ko','PAPER-KO.md'),('ko','Draft compression.md')]:
        path=repo.directory/name;prior=path.read_text();replacements=[]
        headings=copy.deepcopy(before)
        if lang=='en':
            for s in headings:
                s['ko']=s['en'];s['hidden_ko']=s.get('hidden_en',False)
        for sid in changed:
            start,body_start,end=repo.markdown_bounds(prior,headings,sid)
            body=repo.markdown_body(markdown_html(new[sid],lang),prior[body_start:end])
            heading=('### ' if new[sid]['level'] else '## ')+new[sid][lang]
            replacements.append((start,end,heading+'\n\n'+body+'\n\n'))
        result=prior
        for start,end,value in sorted(replacements,reverse=True):result=result[:start]+value+result[end:]
        updates[path]=result
    embedded=json.dumps(sections,ensure_ascii=False).replace('</script','<\\/script')
    for path in repo.previews:
        prior=path.read_text()
        assert len(EMBEDDED.findall(prior))==1,path
        updates[path]=EMBEDDED.sub(lambda m:m[1]+embedded+m[3],prior,count=1)
    # Refresh only current comparison sources, retaining all review decisions.
    for path in (repo.directory/'compare').glob('*-ko.json'):
        proposal=read(path);original=copy.deepcopy(proposal)
        sources=proposal.get('source_sections_sha256') or {proposal['section_id']:proposal['source_section_sha256']}
        for sid in changed:
            if sid not in sources or sources[sid]!=hashlib.sha256(old[sid]['kohtml'].encode()).hexdigest():continue
            ob=BeautifulSoup(old[sid]['kohtml'],'html.parser');nb=BeautifulSoup(new[sid]['kohtml'],'html.parser')
            ops=ob.find_all(['p','li']);nps=nb.find_all(['p','li'])
            assert len(ops)==len(nps), 'Comparison paragraph count changed: '+sid
            mapping={str(a):str(b) for a,b in zip(ops,nps) if str(a)!=str(b)}
            for p in proposal['paragraphs']:
                if p.get('section_id',proposal['section_id'])!=sid:continue
                for key in ['original_html','revised_html','edited_html','applied_html']:
                    if key not in p or not p[key]:continue
                    normalized=str(BeautifulSoup(p[key],'html.parser').find(p.get('block_tag','p')))
                    if normalized in mapping:p[key]=mapping[normalized]
                    else:
                        value=p[key].replace('\ub2e4\uc12f \ubaa8\ub378','Six models.')
                        value=value.replace('Luna·Haiku·Qwen3-8B','Luna·Haiku·DeepSeek·Qwen3-8B')
                        value=value.replace('Luna, Haiku, Qwen3-8B','Luna, Haiku, DeepSeek, Qwen3-8B')
                        value=value.replace('85.8–98.9%','85.8–99.0%').replace('79.5–98.1%','79.5–98.6%')
                        p[key]=value
            sources[sid]=hashlib.sha256(new[sid]['kohtml'].encode()).hexdigest()
        if proposal!=original:
            proposal['source_sections_sha256']=sources
            if proposal['section_id'] in sources:proposal['source_section_sha256']=sources[proposal['section_id']]
            proposal['updated_at']=datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
            updates[path]=json.dumps(proposal,ensure_ascii=False,indent=2)+'\n'
    prior={p:p.read_text() for p in updates}
    assert sha(repo.source)==state['sha256'], 'Draft changed during synchronization'
    for path,value in prior.items():assert path.read_text()==value,path
    stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d-%H%M%S')
    backup=repo.directory/'backup/editor'/('deepseek-results-'+stamp)
    backup.mkdir(parents=True,exist_ok=False)
    for path,value in prior.items():(backup/path.name).write_text(value)
    local=ROOT/'paper/local-draft-en';staged=STAGE/'latex'
    files=[p for p in staged.rglob('*') if p.is_file() and p.suffix in
           ('.tex','.pdf','.bib','.log','.aux','.out','.bbl','.blg','.fls','.fdb_latexmk','.xdv')]
    modified=[]
    for path in files:
        rel=path.relative_to(staged);dest=local/rel
        if dest.exists() and sha(path)==sha(dest):continue
        if dest.exists():
            saved=backup/'latex'/rel;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,saved)
        modified.append((path,dest))
    for path,value in updates.items():repo.atomic_write(path,value)
    for path,dest in modified:
        dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=dest.with_name(dest.name+'.deepseek-tmp');shutil.copy2(path,tmp);tmp.replace(dest)
    assert (local/'FInject-draft-en-v2.pdf').resolve()==local/'FInject-draft-en.pdf'
    with (OUT/'execution.log').open('a') as log:
        log.write(json.dumps({'at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
            'event':'draft_and_pdf_synchronized','draft_sha256':sha(repo.source),
            'pdf_sha256':sha(local/'FInject-draft-en.pdf'),'changed_sections':changed,
            'model_order':MODEL_ORDER,'new_model_calls':0},ensure_ascii=False)+'\n')
    print(json.dumps({'text_files':len(updates),'latex_files':len(modified),'backup':str(backup),
        'draft_sha256':sha(repo.source),'pdf_sha256':sha(local/'FInject-draft-en.pdf')},ensure_ascii=False))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['aggregate','plots','stage','publish'])
    args=parser.parse_args()
    {'aggregate':aggregate,'plots':plots,'stage':stage_paper,'publish':publish}[args.command]()
