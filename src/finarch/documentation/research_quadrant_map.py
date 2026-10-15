"""Render existing Analysis snapshots as research discussion figures; no model calls."""
from pathlib import Path
import collections
import hashlib
import html
import json
import re
import textwrap
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = '20260928-analysis-quadrant-map'
RUN = ROOT / 'reports/run' / RUN_ID
OUT = ROOT / 'outputs/research' / RUN_ID
LOG = ROOT / 'log/research-quadrant-map/20260928'
MODELS = {'Luna': '20260927-exp-007-luna', 'Haiku': '20260927-exp-008-haiku'}
CONDITIONS = [('unguided', 'off'), ('unguided', 'on'), ('guided', 'off'), ('guided', 'on')]
LABELS = ['Unguided / OFF', 'Unguided / ON', 'Guided / OFF', 'Guided / ON']
EA = ['EA_01', 'EA_02']
IC = ['IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01']
SOURCES = {}


def read(path, lines=False):
    p = ROOT / path
    raw = p.read_bytes()
    SOURCES[str(p.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return [json.loads(x) for x in raw.splitlines() if x] if lines else json.loads(raw)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')


def json_write(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def pct(n, d):
    return f'{100*n/d:.1f}%' if d else '미평가'


def rate(n, d):
    return f'{pct(n,d)} · {n:,}/{d:,}' if d else '해당 비교 없음'


def load_data():
    data = {}
    for name, run_id in MODELS.items():
        base = f'reports/experiments-run/{run_id}/02_analysis'
        comp = read(base + '/02_comparison/comparisons.json')
        rows = read(base + '/01_results/responses.jsonl', True)
        notes = read(base + '/02_comparison/interpretations.jsonl', True)
        data[name] = dict(run=run_id, base=base, comparison=comp, rows=rows, notes=notes,
                          indexed={x['response_id']:x for x in rows},
                          matrix={(x['variant'],x['prompt_condition'],x['reasoning']):x for x in comp['matrix']})
        assert comp['response_rows_sha256'] == SOURCES[base + '/01_results/responses.jsonl']
        if (ROOT/base/'03_research/findings.json').exists():
            read(base+'/03_research/findings.json')
            read(base+'/03_research/rq-review.json')
    return data


def selected(d, variants, condition):
    return [d['matrix'][(v,*condition)] for v in variants]


def summed(d, variants, condition, key):
    return sum(x[key] for x in selected(d, variants, condition))


def numeric(d, variants, condition):
    return summed(d, variants, condition, 'numeric'), summed(d, variants, condition, 'planned')


def counts_text(d, variants, condition, key):
    return rate(summed(d, variants, condition, key), summed(d, variants, condition, 'planned'))


def candidates(d, variant, condition, kind):
    x = d['matrix'][(variant,*condition)]
    return x['numeric_candidate_choices'].get(kind,0), x['planned']


def main_cells(d):
    cells=[]
    for c in CONDITIONS:
        o=d['matrix'][('ORIGINAL',*c)]
        cells.append([
            'EA 수치 답변   '+counts_text(d,EA,c,'numeric'),
            'IC 빈 답(null)   '+counts_text(d,IC,c,'null'),
            '원본 수치 일치   '+rate(o['original_results'].get('MATCH',0),o['planned']),
        ])
    return cells


def metric_delta(d, variants, key):
    values = [100*summed(d,variants,c,key)/summed(d,variants,c,'planned') for c in CONDITIONS]
    return [values[1]-values[0],values[3]-values[2]], [values[2]-values[0],values[3]-values[1]]


def make_catalog(data):
    catalog=[]
    def add(fid,title,category,kind,note,producer,source,extra=None):
        item=dict(id=fid,title_ko=title,category=category,status=kind,note_ko=note,source_fields=source,
                  models={name:{'cells':producer(d)} for name,d in data.items()})
        if extra: item.update(extra)
        catalog.append(item)
    add('M01','EA 수치 답변율','RESPONSE_PATTERNS','stored_aggregate',
        '답변율은 저장된 answer에서 숫자가 읽힌 비율입니다. 형식 실패의 숫자도 포함하며 복원 성공률이 아닙니다. EA_01/02는 서로 다른 입력을 각각 지운 문항입니다.',
        lambda d:[[f'{v}   {counts_text(d,[v],c,"numeric")}' for v in EA]+['두 EA 합계   '+counts_text(d,EA,c,'numeric')] for c in CONDITIONS],
        ['matrix.numeric','matrix.planned'])
    add('M02','IC 빈 답(null) 비율','RESPONSE_PATTERNS','stored_aggregate',
        'VALUE 두 조건·SOURCE 두 조건·RELATION의 5개 유형 합계입니다. null 증가를 올바른 충돌 감지 증가로 읽지 않습니다.',
        lambda d:[['IC 5유형   '+counts_text(d,IC,c,'null'), 'VALUE 두 조건   '+counts_text(d,IC[:2],c,'null'), 'RELATION   '+counts_text(d,[IC[-1]],c,'null')] for c in CONDITIONS],
        ['matrix.null','matrix.planned'])
    add('M03','원본 풀이의 수치 일치','ORIGINAL_VARIANT','stored_aggregate',
        '원본 기준 숫자와의 일치입니다. 설명·인용 근거의 의미적 정합성까지 보증하지 않습니다.',
        lambda d:[[f'{k}   {rate(d["matrix"][("ORIGINAL",*c)]["original_results"].get(k,0),557)}' for k in ['MATCH','MISMATCH','UNEVALUATED']] for c in CONDITIONS],
        ['matrix.original_results'])
    add('M04','형식 실패·응답 누락','RESPONSE_PATTERNS','stored_aggregate',
        '실패와 누락을 분모에서 버리지 않습니다. 숫자/null과 형식 상태는 서로 다른 관찰축입니다.',
        lambda d:[[f'형식 실패·실행 실패   {sum(x["planned"]-x["format_valid"] for x in selected(d,["ORIGINAL"]+IC+EA,c)):,}/4,456',
                   f'응답 미수집   {sum(x["planned"]-x["collected"] for x in selected(d,["ORIGINAL"]+IC+EA,c)):,}/4,456',
                   f'EA 형식 유효   {sum(x["format_valid"] for x in selected(d,EA,c)):,}/1,114'] for c in CONDITIONS],
        ['matrix.statuses','matrix.collected','matrix.format_valid'])
    add('M05','주장 앞뒤 위치와 후보 B 수치','VARIANT_BEHAVIOR','stored_aggregate',
        'BEFORE와 AFTER에서 같은 B 주장에 대응하는 숫자 일치를 비교합니다. 숫자 일치만으로 그 근거를 실제로 사용했다고 확정하지 않습니다.',
        lambda d:[[f'B가 앞   {rate(*candidates(d,IC[0],c,"B"))}', f'B가 뒤   {rate(*candidates(d,IC[1],c,"B"))}', '원본 A / 추가 B의 위치 대응'] for c in CONDITIONS],
        ['matrix.numeric_candidate_choices','paired_groups.VALUE_POSITION'])
    for fid,title,parent,child,side in [('M06','출처 추가 A · 부모와 비교',IC[0],IC[2],'A'),('M07','출처 추가 B · 부모와 비교',IC[1],IC[3],'B')]:
        add(fid,title,'VARIANT_BEHAVIOR','stored_aggregate',
            '검증된 VALUE 부모에 출처를 추가한 다단계 생성입니다. 각 부모 안에서는 순서를 유지하지만 두 SOURCE 모두 뒤 주장에 출처가 붙습니다. 출처 표시는 사실 확인이 아닙니다.',
            lambda d,p=parent,ch=child,s=side:[[f'출처 전 {s} 일치   {rate(*candidates(d,p,c,s))}',f'출처 후 {s} 일치   {rate(*candidates(d,ch,c,s))}', '각자의 VALUE 부모에 대응'] for c in CONDITIONS],
            ['matrix.numeric_candidate_choices','paired_groups.SOURCE_'+side])
    add('M08','관계 충돌 · 후보값과 빈 답','VARIANT_BEHAVIOR','stored_aggregate',
        'A는 저장 원본 후보, B는 변형 후보의 숫자 일치입니다. 관계식을 실제 적용했는지는 설명·근거를 따로 확인합니다.',
        lambda d:[[f'A 일치   {rate(*candidates(d,IC[-1],c,"A"))}',f'B 일치   {rate(*candidates(d,IC[-1],c,"B"))}', '빈 답   '+counts_text(d,[IC[-1]],c,'null')] for c in CONDITIONS],
        ['matrix.numeric_candidate_choices','matrix.null'])
    add('M09','EA 답과 원본 숫자의 관계','VARIANT_BEHAVIOR','stored_aggregate',
        '원본 수치 일치는 복원 성공이 아닙니다. OTHER·NULL·실패를 보존하며 복원식과 근거는 M14에서 사례로 읽습니다.',
        lambda d:[[f'{v} 원본 숫자   {rate(*candidates(d,v,c,"ORIGINAL_VALUE"))}' for v in EA]+['복원 성공 여부는 이 숫자로 판단 불가'] for c in CONDITIONS],
        ['matrix.numeric_candidate_choices.ORIGINAL_VALUE'])
    def groups(d):
        out=[]
        for c in CONDITIONS:
            lines=[]
            for verdict in ['MATCH','MISMATCH','UNEVALUATED']:
                g=next(x for x in d['comparison']['original_groups'] if (x['prompt_condition'],x['reasoning'])==c and x['baseline_result']==verdict)
                lines.append(f'{verdict} 원본군 · 변형 수치 {rate(g["numeric"],g["planned"])}')
            out.append(lines)
        return out
    add('M10','원본 정오별 변형 반응','ORIGINAL_VARIANT','stored_aggregate',
        '동일 조건의 원본 정오로 나눈 집단입니다. 7변형 합계의 수치 응답일 뿐 감지 정확도가 아니며, 조건마다 집단 구성도 달라집니다.',groups,
        ['original_groups.baseline_result','original_groups.numeric','original_groups.planned'])
    def classification(d,field,variants):
        return [['분류 출력 미요구','null 분류는 감지 실패가 아님','답·설명·근거로 비교'] if c[0]=='unguided' else
                [field+'   '+rate(sum(x['classifications'].get(field,0) for x in selected(d,variants,c)),sum(x['planned'] for x in selected(d,variants,c))),
                 '모델이 반환한 분류 표지','독립적인 의미 정답 판정 아님'] for c in CONDITIONS]
    add('M11','IC의 CONFLICT 분류','RESPONSE_PATTERNS','stored_aggregate',
        'Guided에서만 분류를 요구합니다. Unguided와 분류 빈도를 직접 비교하지 않습니다.',lambda d:classification(d,'CONFLICT',IC),['matrix.classifications'])
    add('M12','EA의 INSUFFICIENT_EVIDENCE 분류','RESPONSE_PATTERNS','stored_aggregate',
        'ANSWERABLE·CONFLICT·INSUFFICIENT_EVIDENCE·UNRESOLVED·ABSTAIN 전체 분포는 feature-map.json의 원천 집계에 연결합니다. 분류 변화가 곧 개선은 아닙니다.',lambda d:classification(d,'INSUFFICIENT_EVIDENCE',EA),['matrix.classifications'])
    def transitions(d):
        result=[['두 비교의 기준 조건','오른쪽: 안내만 변경','위쪽: 추론 설정만 변경']]
        for c in CONDITIONS[1:]:
            axis='PROMPT' if c==('guided','off') else 'REASONING'
            fixed=c[0] if axis=='REASONING' else c[1]
            ps=[x for x in d['comparison']['paired_groups'] if x['axis']==axis and x['variant'] in EA and (x['prompt_condition'] if axis=='REASONING' else x['reasoning'])==fixed]
            total=sum(x['comparable_pairs'] for x in ps);nt=tn=0
            for x in ps:
                for key,n in x['choice_transitions'].items():
                    a,b=key.split(' → ')
                    if a=='NULL' and b in ('OTHER','ORIGINAL_VALUE','A','B','BOTH'):nt+=n
                    if b=='NULL' and a in ('OTHER','ORIGINAL_VALUE','A','B','BOTH'):tn+=n
            result.append([('추론 OFF→ON' if axis=='REASONING' else 'Unguided→Guided')+' · EA 대응쌍',f'빈 답→수치   {rate(nt,total)}',f'수치→빈 답   {rate(tn,total)}'])
        return result
    add('M13','같은 문항의 조건 간 전이','CONDITION_EFFECTS','stored_aggregate',
        '양쪽 형식 유효인 대응쌍의 전이입니다. 전체 대상·실패쌍은 paired_groups에 보존됩니다. 우상단은 Guided 고정 OFF→ON이며 두 요인의 상호작용 검정이 아닙니다.',transitions,['paired_groups.choice_transitions','paired_groups.comparable_pairs'])
    qualitative=[
        ('M14','EA의 명시적 역산·복원식','VARIANT_BEHAVIOR',['reverse_calculation'],'역산식이 설명에 나타난 사례입니다. 타당한 복원 성공률·조건별 우세는 미집계입니다.'),
        ('M15','EA의 남은 정보·대체 경로','VARIANT_BEHAVIOR',['retained_information','alternative_route','alternative_calculation'],'직접 남은 답 읽기·중복 정보·다른 계산 경로를 구분해 검토합니다. 원본 숫자 일치로 경로를 추정하지 않습니다.'),
        ('M16','가정·빈칸 0 처리·근거 없는 보충','VARIANT_BEHAVIOR',['assumption','zero_assumption','unsupported_assumption','unsupported_guessing','zero_imputation'],'저장 해석에 연결된 인용 예시입니다. 태그 빈도를 발생률로 바꾸지 않습니다.'),
        ('M17','충돌 설명·조건부 계산과 최종 답','RESPONSE_ELEMENTS',['conditional_calculation','conditional_answer','answer_explanation_mismatch','conflict_acknowledged'],'조건별 계산·충돌 설명과 최종 답의 연결을 읽습니다. 숨은 사고 과정이나 전체 불일치율을 뜻하지 않습니다.'),
        ('M18','답·설명·인용 근거의 정합성','RESPONSE_ELEMENTS',['answer_explanation_mismatch','evidence_mismatch','citation_mismatch','inconsistency'],'실제 불일치 여부는 연결된 전체 응답을 읽어 판단합니다. 해석 메모와 직접 인용을 구분합니다.'),
        ('M19','산술·단위·반올림·행과 열의 해석','RESPONSE_ELEMENTS',['arithmetic_error','unit_mismatch','rounding','wrong_year','wrong_row','sign_error'],'관계식 적용과 숫자 반환의 차이를 설명하는 사례 항목입니다. 정량적인 원인별 오류율은 없습니다.'),
        ('M20','반례와 특이 사례','COUNTEREXAMPLES',['counterexample','contrary_case'],'주된 방향과 다른 사례를 보존합니다. 같은 원본의 네 조건은 독립 반복이 아닙니다.'),
    ]
    for fid,title,category,tags,note in qualitative:
        refs={}
        def examples(d,tags=tags):
            cells=[];model_refs=[]
            for c in CONDITIONS:
                found=None
                for obs in d['notes']:
                    if not set(tags)&set(obs.get('tags',[])):continue
                    for ex in obs.get('excerpts',[]):
                        row=d['indexed'].get(ex['response_id'])
                        if row and (row['prompt_condition'],row['reasoning'])==c:
                            response=row.get('response') or {};field=response.get(ex['field'])
                            target='\n'.join(field) if isinstance(field,list) and all(isinstance(z,str) for z in field) else str(field)
                            if ex['quote'] not in target:continue
                            found=dict(observation_id=obs['id'],response_id=ex['response_id'],case=row['case'],variant=row['variant'],field=ex['field'],quote=ex['quote'],
                                       title_ko=obs.get('display_ko',{}).get('title',obs.get('title','')),
                                       observation_ko=obs.get('display_ko',{}).get('observation',obs.get('observation','')),
                                       limitation_ko=obs.get('display_ko',{}).get('limitation',obs.get('limitation','')))
                            break
                    if found:break
                model_refs.append(found)
                cells.append(['발생률·우세 분면 미집계', '대응 비교용 '+found['case']+' · '+found['variant'],found['observation_id']] if found else
                             ['이 조건의 인용 예시 미선정','현상이 없다는 뜻은 아님','조건별 발생률 미집계'])
            refs[d['run']]=model_refs
            return cells
        add(fid,title,category,'qualitative_example',note+' 태그는 여러 조건을 함께 다룬 관찰 메모에 붙습니다. 각 칸의 인용은 대응 비교용이며 해당 현상이 그 칸에서 발생했다는 표시가 아닙니다. 반대 사례도 포함될 수 있습니다.',examples,['interpretations.tags','interpretations.excerpts','responses.response'],{'example_links':refs})
    for fid,title,note,fields in [
        ('M21','외부 지식 의존성','현행 구현에는 원본 제작의 외부 지식 확인 여부를 나누는 기능이 있으나, 선택한 두 comparisons에는 집계가 없습니다. used=false는 불필요의 증명이 아닙니다.',['original_external_knowledge']),
        ('M22','계산 깊이·연산 수','연구 제안입니다. 현재 두 Analysis 집계에는 깊이·연산 수별 비교가 없습니다. 계산 구조의 정의와 연결을 먼저 정해야 합니다.',['proposed_structure_covariates']),
        ('M23','독립 반복의 안정성','두 실행 모두 repeat_comparison_available=false입니다. 네 조건 간 차이를 동일 조건의 독립 반복으로 바꾸지 않습니다.',['repeat_comparison_available']),
    ]:
        add(fid,title,'UNAVAILABLE_OR_PROPOSED','not_measured',note,
            lambda d:[['분면에 강도를 배치할 근거 없음','현재 선택 자료에서 미집계','0 또는 효과 없음으로 읽지 않음'] for _ in CONDITIONS],fields)
    return catalog


def esc(s):return html.escape(str(s),quote=True)


def svg_figure(slug,title,model,cells,footer,highlights=None):
    # Categorical axes: the location within each cell carries no quantitative meaning.
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" id="{slug}" viewBox="0 0 1280 800" role="img" aria-labelledby="{slug}-title {slug}-desc">',
           f'<title id="{slug}-title">{esc(title)} · {esc(model)}</title>',
           f'<desc id="{slug}-desc">왼쪽은 Unguided Solving, 오른쪽은 Criteria-Guided Solving, 아래는 Reasoning OFF, 위는 ON입니다. {esc(footer)}</desc>',
           '<defs><marker id="'+slug+'-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse"><path d="M0 0L8 4L0 8Z" fill="#52685f"/></marker></defs>',
           '<rect width="1280" height="800" fill="#ffffff"/>',
           '<g font-family="system-ui, -apple-system, sans-serif" fill="#23322e">']
    def text(x,y,s,size=20,weight=400,color='#23322e',anchor='start'):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(s)}</text>')
    text(40,48,title,28,650);text(1240,48,model,28,650,anchor='end')
    text(640,98,'Reasoning ON',20,600,anchor='middle')
    text(640,684,'Reasoning OFF',20,600,anchor='middle')
    text(320,712,'Unguided Solving',20,600,anchor='middle')
    text(964,712,'Criteria-Guided Solving',20,600,anchor='middle')
    parts.extend([f'<line x1="640" y1="656" x2="640" y2="112" stroke="#52685f" stroke-width="2" marker-end="url(#{slug}-arrow)"/>',
                  f'<line x1="56" y1="384" x2="1224" y2="384" stroke="#52685f" stroke-width="2" marker-end="url(#{slug}-arrow)"/>'])
    positions=[(72,424),(72,144),(696,424),(696,144)]
    for i,((x,y),lines) in enumerate(zip(positions,cells)):
        focal=bool(highlights and i in highlights)
        parts.append(f'<rect x="{x-16}" y="{y-28}" width="544" height="224" rx="6" fill="{"#f1f8f3" if focal else "#f8faf8"}" stroke="{"#276754" if focal else "#dce3dd"}"/>')
        text(x,y,LABELS[i],20,650,'#245b4e')
        yy=y+48
        for line in lines:
            if len(line)>50:
                for segment in textwrap.wrap(line,48):text(x,yy,segment,18);yy+=28
            else:text(x,yy,line,20);yy+=40
    parts.append('<line x1="40" y1="736" x2="1240" y2="736" stroke="#dce3dd"/>')
    for j,line in enumerate(textwrap.wrap(footer,88)[:2]):text(40,762+j*24,line,16,color='#52685f')
    parts.extend(['</g>','</svg>'])
    return ''.join(parts)


def build():
    for path in [RUN,OUT,LOG]:path.mkdir(parents=True,exist_ok=True)
    data=load_data();catalog=make_catalog(data)
    protected=[ROOT/'reports/run/20260924-paper-draft/PAPER-KO.md',ROOT/'viewer/research/index.html']
    for p in protected:SOURCES[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ['docs/02-experiments/02_analysis/02_comparison/README.md','docs/02-experiments/02_analysis/03_research/README.md','src/finarch/experiments/02-analysis/02-comparison/comparison.py','src/finarch/experiments/prompts/02-analysis.02-comparison.response-patterns.md']:
        SOURCES[p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    svg_files=[];sections=[]
    md=['# Analysis feature 사분면 맵','', '**읽는 순서:** 전체 지도 → EA의 모델별 반대 방향 → M01–M23 항목별 지도 → 사례와 미집계 항목.','',
        '가로축은 Unguided Solving → Criteria-Guided Solving, 세로축은 Reasoning OFF → ON입니다. 칸 안의 위치나 색은 통계적 효과 크기가 아닙니다.','',
        '**범위:** 저장된 Luna·Haiku Analysis 두 실행을 시각화한 토의 자료입니다. 논문의 결과·결론 채택이나 새 실험·분석 모델 실행이 아닙니다.','',
        '**분모:** 원본 557문항, EA는 2변형 × 557 = 1,114행, IC는 5변형 × 557 = 2,785행입니다. 같은 원본의 변형·조건은 독립 표본이 아닙니다.','',
        '**표시:** 저장 집계 / 관련 인용 사례 / 미집계·제안을 구분합니다. 숫자 응답 증가, 정당한 복원 증가, 의미적 정확도 증가는 서로 다릅니다.','', '## 1. 네 조건의 전체 지도','']
    intro='<h1>Analysis feature 사분면 맵</h1><p>가로: 판단 안내 여부 · 세로: Reasoning OFF / ON</p><p>저장된 두 실행의 기술적 관찰입니다. 결과·결론 채택 및 새 실험 실행이 아닙니다.</p>'
    for name,d in data.items():
        slug='overview-'+name.lower()
        rd,gd=metric_delta(d,EA,'numeric')
        foot=f'EA의 OFF→ON 변화: Unguided {rd[0]:+.1f}%p · Guided {rd[1]:+.1f}%p. 수치/null은 실패 필드 포함; 정답률 아님.'
        heads=({'Luna':['IC에 대부분 수치 답변','EA 답변 증가 · 원본 일치 증가','EA 빈 답이 네 조건 중 가장 많음','IC는 빈 답 증가 · EA는 수치 증가'],
                'Haiku':['EA 수치 답변이 네 조건 중 가장 많음','원본 일치 증가 · EA 수치 감소','형식 실패가 네 조건 중 가장 많음','IC 빈 답 증가 · EA 수치 감소']}[name])
        cells=[c+[heads[i]] for i,c in enumerate(main_cells(d))]
        s=svg_figure(slug,'네 조건에서 두드러지는 응답 양상',name,cells,foot,[3])
        sections.append(f'<section id="{slug}-section">{s}<p>{esc(d["run"])}</p></section>')
        md += [f'### {name}',f'![{name} 네 조건의 전체 지도](figures/{slug}.svg)','']
        rd,gd=metric_delta(d,EA,'numeric')
        md += [f'EA 수치 답변율의 OFF→ON 변화: **Unguided {rd[0]:+.1f}%p / Guided {rd[1]:+.1f}%p**. 안내 추가의 변화: OFF {gd[0]:+.1f}%p / ON {gd[1]:+.1f}%p.','']
    md += ['Luna는 위쪽 두 분면에서 EA 수치 답변율이 더 높고, Haiku는 아래쪽 두 분면에서 더 높습니다. 따라서 “Reasoning ON이면 EA 답변율이 높아진다”를 모든 모델의 공통 성질로 표시하지 않습니다.','',
           'Haiku에는 형식 실패 1,198건과 출력 잘림 5건이 있어 응답 필드와 형식 유효성을 함께 봐야 합니다. M04는 실패·누락, M13은 양쪽 형식 유효인 대응쌍을 표시합니다.','',
           '## 2. 모든 분석 항목의 배치 색인','',
           '|항목|지도에서 비교하는 것|현재 근거|','|---|---|---|']
    statuses={'stored_aggregate':'저장 집계','qualitative_example':'인용 사례 · 강도 미집계','not_measured':'미집계 / 제안'}
    for f in catalog:md.append(f'|{f["id"]} {f["title_ko"]}|{f["category"]}|{statuses[f["status"]]}|')
    for f in catalog:
        md += ['',f'## {f["id"]}. {f["title_ko"]}','',f'**근거 상태: {statuses[f["status"]]}**',f['note_ko'],'']
        body=[f'<details id="{f["id"]}"><summary>{f["id"]} · {esc(f["title_ko"])} <small>{statuses[f["status"]]}</small></summary><p>{esc(f["note_ko"])}</p>']
        for name,d in data.items():
            slug=f['id'].lower()+'-'+name.lower()
            s=svg_figure(slug,f['id']+' · '+f['title_ko'],name,f['models'][name]['cells'],statuses[f['status']]+' · '+d['run']+' · 위치는 조건만 표현하며 효과의 인과성·유의성을 뜻하지 않습니다.')
            body.append(s);md += [f'![{f["id"]} {name} · {f["title_ko"]}](figures/{slug}.svg)','']
            if f.get('example_links'):
                for idx,ref in enumerate(f['example_links'].get(d['run'],[])):
                    if not ref:continue
                    quote=ref['quote']
                    body.append(f'<div class="evidence"><b>{esc(name+" · "+LABELS[idx]+" · "+ref["observation_id"])}</b><p>{esc(ref["observation_ko"])}</p><blockquote>{esc(quote)}</blockquote><p>{esc(ref["limitation_ko"])}</p><code>{esc(ref["response_id"])}</code></div>')
                    md += [f'**인용 예시 — {name} / {LABELS[idx]} / {ref["observation_id"]}**',ref['observation_ko'],f'원응답 인용: {quote}',f'해석 한계: {ref["limitation_ko"]}',f'응답 ID: `{ref["response_id"]}`','']
        body.append('</details>');sections.append(''.join(body))
    md += ['## 3. Analysis 카테고리와 지도 연결','',
           '|Analysis 카테고리|지도 항목|','|---|---|',
           '|① 전체 응답 양상|M01–M04, M11–M12|','|② 원본과 변형|M03, M09–M10|','|③ 조건·모델 효과|모델별 전체 지도, M01–M13의 가로·세로 비교, M13의 대응 전이|',
           '|④ 유형별 선택·풀이 방식|M05–M09, M14–M16|','|⑤ 답·분류·설명·근거 관계|M11–M12, M17–M19|','|⑥ 반례·특이 사례|M20, EA 방향이 다른 두 모델|',
           '|⑦ 연구 해석|위 지도의 관찰·대안 설명·한계를 연결. 독립적인 추가 효과나 새 결론으로 중복 계산하지 않음|','',
           '외부 지식은 M21, 계산 구조 제안은 M22, 독립 반복은 M23에 표시했습니다. 이것들은 현재 강도가 확인된 분면에 억지로 배치하지 않았습니다.','',
           '## 4. 원자료와 재현 범위','',
           '이 문서는 comparisons.json에 이미 저장된 합계와 비율 표시, 기존 해석의 정확 인용 예시만 사용합니다. 새 모델 호출, 의미 정답 재판정, 유의성 검정 또는 Analysis 파이프라인 실행은 없습니다.','',
           '[전체 매핑·사례 ID](feature-map.json) · [자료 해시·시각](source-snapshot.json) · [읽는 순서](README.md)','']
    for name,d in data.items():
        md += [f'[{name} 저장 집계](../../experiments-run/{d["run"]}/02_analysis/02_comparison/comparisons.json)',f'[{name} 응답](../../experiments-run/{d["run"]}/02_analysis/01_results/responses.jsonl)',f'[{name} 저장 해석](../../experiments-run/{d["run"]}/02_analysis/02_comparison/interpretations.jsonl)','']
    style='''body{margin:0;background:#f5f6f4;color:#23322e;font:17px/1.8 system-ui,sans-serif}main{max-width:1280px;margin:auto;padding:28px}h1{font-size:30px}p,li,blockquote{font-size:17px}svg{display:block;width:100%;height:auto;background:white}section,details{border:1px solid #dce3dd;margin:24px 0;background:white;padding:20px;border-radius:6px}summary{cursor:pointer;font-weight:650;font-size:21px}small{font-size:15px;color:#52685f}nav{display:flex;flex-wrap:wrap;gap:12px}a{color:#245b4e}blockquote{border-left:3px solid #276754;padding-left:18px}code{overflow-wrap:anywhere}.evidence{margin:24px 0;border-top:1px solid #dce3dd} @media(max-width:700px){main{padding:12px}section,details{padding:12px}summary{font-size:18px}svg{min-width:760px}section,details{overflow:auto}} @media print{details{display:block}summary{break-after:avoid}svg{break-inside:avoid}}'''
    nav='<nav>'+''.join(f'<a href="#{f["id"]}">{f["id"]} {esc(f["title_ko"])}</a>' for f in catalog)+'</nav>'
    content='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Analysis feature 사분면 맵</title><style>'+style+'</style></head><body><main>'+intro+nav+''.join(sections)+'</main></body></html>'
    html_path=OUT/'analysis-quadrant-map.html';write(html_path,content)
    # Derive vector figures from the authored HTML for the existing Markdown viewer.
    for svg in re.findall(r'<svg\b.*?</svg>',content,re.S):
        slug=re.search(r'\bid="([^"]+)"',svg).group(1)
        path=RUN/'figures'/f'{slug}.svg';write(path,svg+'\n');svg_files.append(str(path.relative_to(ROOT)))
    write(RUN/'RESEARCH-DIRECTION.md','\n'.join(md)+'\n')
    json_write(RUN/'feature-map.json',{'schema_version':1,'conditions':[dict(prompt=p,reasoning=r) for p,r in CONDITIONS],
        'models':MODELS,'features':catalog,'snapshot_policy':'Existing aggregates and exact excerpts only; not a new Analysis run.',
        'classification_distributions':{n:[{k:v for k,v in m.items() if k!='response_ids'} for m in d['comparison']['matrix']] for n,d in data.items()}})
    json_write(RUN/'source-snapshot.json',{'created_at':datetime.now(timezone.utc).isoformat(),'sources':SOURCES,
        'aggregates_created_at':{name:d['comparison']['generated_at'] for name,d in data.items()},
        'model_calls':0,'experiment_execution':False,'analysis_pipeline_execution':False,
        'style_source':'viewer/research/index.html; system-ui fonts; project-scoped styling only',
        'selection':'Two stored Analysis snapshots with both comparisons and interpretations; not all project models.'})
    readme=(ROOT/'src/finarch/documentation/templates/research/quadrant-map-readme.md').read_text()
    write(RUN/'README.md',readme)
    entry={'id':RUN_ID,'title':'2026-09-28 · Analysis 사분면 맵 · Luna·Haiku와 23개 항목'}
    runs_path=ROOT/'viewer/research/runs.json';runs=json.loads(runs_path.read_text())
    before=LOG/'before-runs.json'
    if not before.exists():write(before,runs_path.read_text())
    json_write(runs_path,[entry]+[x for x in runs if x['id']!=RUN_ID])
    unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in SOURCES.items())
    assert unchanged
    verification={'feature_count':len(catalog),'svg_count':len(svg_files),'sources_unchanged':unchanged,
                  'quoted_examples':sum(bool(x) for f in catalog for refs in f.get('example_links',{}).values() for x in refs),
                  'new_model_calls':0,'viewer_code_unchanged':True,'paper_unchanged':True}
    json_write(LOG/'build-verification.json',verification)
    write(LOG/'README.md',(ROOT/'src/finarch/documentation/templates/research/quadrant-map-log-readme.md').read_text())
    write(RUN/'events.jsonl',json.dumps({'action':'render_existing_analysis_snapshots','time':datetime.now(timezone.utc).isoformat(),**verification})+'\n')
    print(json.dumps(verification))


if __name__=='__main__':build()
