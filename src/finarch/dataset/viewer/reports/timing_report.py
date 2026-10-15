"""Summarize observed intervals without double-counting nested or parallel calls."""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
save = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['save']).save
RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs


def read(path):
    try:return json.loads(path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return {}


def stamp(value):
    try:return datetime.fromisoformat(value).timestamp()
    except (TypeError,ValueError):return None


def local(value):
    return datetime.fromtimestamp(value).astimezone().isoformat(sep=' ',timespec='milliseconds') if value is not None else None


def union_seconds(intervals):
    total=0;start=end=None
    for a,b in sorted(intervals):
        if b<a:continue
        if start is None:start,end=a,b
        elif a<=end:end=max(end,b)
        else:total+=end-start;start,end=a,b
    return total+(end-start if start is not None else 0)


def call_count(event):
    # API usage events historically omitted api_requests and have cli_invocations=0.
    return event.get('api_requests') or event.get('cli_invocations') or (1 if event.get('provider') == 'openai' else 0)


def token_count(event, key):
    usage = event.get('reported_usage') or {}
    if key == 'cached_input_tokens':
        return usage.get(key) or (usage.get('input_tokens_details') or {}).get('cached_tokens') or 0
    return usage.get(key) or 0


def metrics(intervals,llm,usage,lifecycle=None):
    starts=[a for a,b in intervals];ends=[b for a,b in intervals]
    start=min(starts) if starts else None;end=max(ends) if ends else None
    lifecycle=lifecycle or {}
    exact=bool(lifecycle.get('ended_at') and lifecycle.get('measurement') in ('lifecycle_monotonic','recorded_phase_window'))
    if exact:start=stamp(lifecycle['started_at']);end=stamp(lifecycle['ended_at'])
    result={'started_at':local(start),'ended_at':local(end),
            'elapsed_seconds':lifecycle['elapsed_seconds'] if exact else (end-start if start is not None else None),
            'measurement':lifecycle.get('measurement') if exact else 'observed_event_window',
            'active_seconds':union_seconds(intervals),'llm_active_seconds':union_seconds(llm),
            'llm_call_seconds':sum(b-a for a,b in llm),'llm_timed_calls':len(llm),
            'llm_calls':sum(call_count(x) for x in usage),
            'reported_tokens':{key:sum(token_count(x, key) for x in usage)
                               for key in ('input_tokens','output_tokens','cached_input_tokens')},
            'billed_cost':None}
    return result


def build(root):
    root=Path(root);events=[];damaged=0
    for path in root.rglob('events.jsonl'):
        relative=path.relative_to(root).parts
        if not relative:continue
        if relative[0]=='01-preparation':
            record={}
            for parent in path.parents:
                if parent==root:break
                candidate=read(parent/'run.json')
                if candidate.get('input_id'):
                    record=candidate;break
            round_name=next((part for part in relative if part.endswith("-round")),None)
            number=int(round_name.split("-")[0]) if round_name else int(record.get("repair_attempt",0))+1
            group=f"Preparation / {number}차"
        elif relative[0]=='02-generation':
            group='Generation / '+next((part for part in relative if part.endswith('-round')),'중단 기록')
        elif relative[0].endswith('-round'):group=relative[0]
        else:continue
        with path.open() as stream:
            for line in stream:
                try:item=json.loads(line)
                except json.JSONDecodeError:damaged+=1;continue
                if item.get('phase') not in ('START','END','USAGE'):continue
                item['_round']=group
                item['_variant']=next((part for part in relative if part in ('01-ic-value-before','02-ic-value-after','03-ic-source-type-1','04-ic-source-type-2','05-ic-relation','06-ea-earlier-input','07-ea-later-input')), 'shared-feedback' if relative[0]=='02-generation' and 'feedback' in relative else None)
                stage=item.get('stage') or ''
                if stage in ('','.'):stage=relative[1] if len(relative)>1 and not relative[1].startswith('test-') else '08-records'
                step=item.get('step')
                if '/' not in stage and step:stage+='/'+step
                item['_section']='/'.join(stage.split('/')[:2])
                keep=('phase','call_id','started_at','ended_at','timestamp','function','provider','api_requests','cli_invocations','reported_usage','_round','_variant','_section')
                events.append({key:item[key] for key in keep if key in item})
    uses={e['call_id']:e for e in events if e.get('phase')=='USAGE' and call_count(e) and e.get('call_id')}
    intervals=[];llm=[];rounds=defaultdict(lambda:[[],[],[]]);sections=defaultdict(lambda:[[],[],[]]);seen=set();variants=defaultdict(lambda:[[],[],[]])
    for e in events:
        if e.get('phase')!='END':continue
        a=stamp(e.get('started_at'));b=stamp(e.get('ended_at') or e.get('timestamp'))
        if a is None or b is None or b<a:continue
        key=(e.get('call_id'),a,b)
        if key in seen:continue
        seen.add(key)
        pair=(a,b);intervals.append(pair)
        round_group=rounds[e['_round']];section_group=sections[(e['_round'],e['_section'])]
        round_group[0].append(pair);section_group[0].append(pair)
        if e.get("_variant"):variants[(e["_round"],e["_variant"])][0].append(pair)
        if e.get('function','').endswith('CLITransport.__call__') and e.get('call_id') in uses:
            llm.append(pair);round_group[1].append(pair);section_group[1].append(pair)
            if e.get("_variant"):variants[(e["_round"],e["_variant"])][1].append(pair)
    for e in uses.values():
        rounds[e['_round']][2].append(e);sections[(e['_round'],e['_section'])][2].append(e)
        if e.get('_variant'):variants[(e['_round'],e['_variant'])][2].append(e)
    starts={e.get('call_id') for e in events if e.get('phase')=='START' and e.get('function','').endswith('CLITransport.__call__') and e.get('call_id')}
    lifecycle=read(root/'timing.json')
    generation_lifecycle=read(root/'02-generation/timing.json')
    if generation_lifecycle and lifecycle.get('scope')=='preparation':
        start=stamp(lifecycle.get('started_at'));end=stamp(generation_lifecycle.get('ended_at'))
        if start is not None and end is not None:
            lifecycle={**lifecycle,'ended_at':generation_lifecycle['ended_at'],'elapsed_seconds':end-start,'measurement':'recorded_phase_window'}
        else:lifecycle={}
    total=metrics(intervals,llm,list(uses.values()),lifecycle)
    report={'calls_without_tokens':sum(not isinstance(e.get('reported_usage'),dict) for e in uses.values()),'started_calls':len(starts),'calls_without_usage':len(starts-set(uses)), 'run_id':root.name,'total':total,'rounds':[{'round':name,**metrics(*data,read(root/name/'timing.json'))} for name,data in sorted(rounds.items())],
            'sections':[{'round':name,'section':section,**metrics(*data)} for (name,section),data in sorted(sections.items())],
            'generation_types':[{'round':name,'variant':variant,**metrics(*data)} for (name,variant),data in sorted(variants.items())],
            'damaged_event_lines':damaged,'notes':[
                'Elapsed time is wall-clock duration. Historical runs without lifecycle records use the observed event window, excluding unrecorded startup or shutdown.',
                'LLM call time sums transport intervals for recorded API and CLI requests. It includes transport overhead and is not pure inference time.',
                'LLM active time merges overlapping calls. Summed call time can exceed elapsed time under parallel execution.',
                'Section windows and nested work overlap; do not add them to derive total elapsed time.',
                'Completion is process completion, not a claim that every generated candidate passed.' ]}
    save(root/'timing-report.json',report)
    template=Path(__file__).with_name('timing-readme.md').read_text()
    (root/'TIMING-README.md').write_text(template.format(run_id=root.name))
    logs=RunLogs.for_case(root)
    logs.write('cli.log','execution.timing_summary',phase='SUMMARY',value=total)
    logs.write('detail.log','execution.timing_report',phase='END',value={'artifact':str(root/'timing-report.json'),**report})
    print(json.dumps({'event':'SUMMARY','run_id':root.name,**total},ensure_ascii=False),flush=True)
    return report


if __name__=='__main__':
    import sys
    print(json.dumps(build(Path(sys.argv[1]))['total'],indent=2))
