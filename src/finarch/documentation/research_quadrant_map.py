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
    return f'{100*n/d:.1f}%' if d else 'Not evaluated'


def rate(n, d):
    return f'{pct(n,d)} · {n:,}/{d:,}' if d else 'No comparison'


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
            'EA numbers answer   '+counts_text(d,EA,c,'numeric'),
            'IC is empty   '+counts_text(d,IC,c,'null'),
            'The original numbers match.   '+rate(o['original_results'].get('MATCH',0),o['planned']),
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
    add('M01','EA numbers and response rates','RESPONSE_PATTERNS','stored_aggregate',
        'The answer rate is the percentage of the numbers that are read from the saved answer, including the number of form failures, and not the recovery success rate.1/02is a case that wears each other\'s inputs.',
        lambda d:[[f'{v}   {counts_text(d,[v],c,"numeric")}' for v in EA]+['Two EAs combined.   '+counts_text(d,EA,c,'numeric')] for c in CONDITIONS],
        ['matrix.numeric','matrix.planned'])
    add('M02','IC is zero.','RESPONSE_PATTERNS','stored_aggregate',
        'VALUE two conditions;SOURCE two conditions;RELATION of 5It\'s the items type sum. It doesn\'t read the null increment as the correct collision detection increment.',
        lambda d:[['IC 5Type   '+counts_text(d,IC,c,'null'), 'VALUE Two conditions   '+counts_text(d,IC[:2],c,'null'), 'RELATION   '+counts_text(d,[IC[-1]],c,'null')] for c in CONDITIONS],
        ['matrix.null','matrix.planned'])
    add('M03','The original foil matches the figure','ORIGINAL_VARIANT','stored_aggregate',
        'It\'s a match to the original reference numbers, and it doesn\'t guarantee the meaningful completeness of the explanatory-personally-based data.',
        lambda d:[[f'{k}   {rate(d["matrix"][("ORIGINAL",*c)]["original_results"].get(k,0),557)}' for k in ['MATCH','MISMATCH','UNEVALUATED']] for c in CONDITIONS],
        ['matrix.original_results'])
    add('M04','Form failure: lack of response','RESPONSE_PATTERNS','stored_aggregate',
        'Failure and failure are not left out of the denominator. Numbers/null and form states are different observation axes.',
        lambda d:[[f'Failure to form. Failure in action.   {sum(x["planned"]-x["format_valid"] for x in selected(d,["ORIGINAL"]+IC+EA,c)):,}/4,456',
                   f'Answer subset   {sum(x["planned"]-x["collected"] for x in selected(d,["ORIGINAL"]+IC+EA,c)):,}/4,456',
                   f'EA format is valid   {sum(x["format_valid"] for x in selected(d,EA,c)):,}/1,114'] for c in CONDITIONS],
        ['matrix.statuses','matrix.collected','matrix.format_valid'])
    add('M05','The position of the claimed forward and back and the candidate B figure','VARIANT_BEHAVIOR','stored_aggregate',
        'We compare the numerical units corresponding to the same B-clause in BEFORE and AFTER, and the numerical matching alone doesn\'t confirm that the basis was actually used.',
        lambda d:[[f'B is ahead.   {rate(*candidates(d,IC[0],c,"B"))}', f'Follow B.   {rate(*candidates(d,IC[1],c,"B"))}', 'The position corresponds to the original A/Added B'] for c in CONDITIONS],
        ['matrix.numeric_candidate_choices','paired_groups.VALUE_POSITION'])
    for fid,title,parent,child,side in [('M06','Source Additional A · Parent comparison',IC[0],IC[2],'A'),('M07','Source Additional B. Comparison with parents',IC[1],IC[3],'B')]:
        add(fid,title,'VARIANT_BEHAVIOR','stored_aggregate',
            'It\'s a multi-step creation that adds a source to a validated VALUE parent, and each parent maintains the sequence, but both SOURCEs attach a source to the back claim.',
            lambda d,p=parent,ch=child,s=side:[[f'Before the source. {s} Match   {rate(*candidates(d,p,c,s))}',f'After the source {s} Match   {rate(*candidates(d,ch,c,s))}', 'Responding to each parent\'s values'] for c in CONDITIONS],
            ['matrix.numeric_candidate_choices','paired_groups.SOURCE_'+side])
    add('M08','Relationship conflict and empty answers','VARIANT_BEHAVIOR','stored_aggregate',
        'A is the number matching of the original candidate, and B is the number of the modification candidate, so we\'ll check separately for the description and the approximation of whether the formula was actually applied.',
        lambda d:[[f'A matches   {rate(*candidates(d,IC[-1],c,"A"))}',f'B matches   {rate(*candidates(d,IC[-1],c,"B"))}', 'Empty answer   '+counts_text(d,[IC[-1]],c,'null')] for c in CONDITIONS],
        ['matrix.numeric_candidate_choices','matrix.null'])
    add('M09','The relationship between the EA response and the original number','VARIANT_BEHAVIOR','stored_aggregate',
        'The original number unit is not a success recovery.4I read it in case.',
        lambda d:[[f'{v} The original number.   {rate(*candidates(d,v,c,"ORIGINAL_VALUE"))}' for v in EA]+['Whether or not the restoration is successful is not to be judged by this number.'] for c in CONDITIONS],
        ['matrix.numeric_candidate_choices.ORIGINAL_VALUE'])
    def groups(d):
        out=[]
        for c in CONDITIONS:
            lines=[]
            for verdict in ['MATCH','MISMATCH','UNEVALUATED']:
                g=next(x for x in d['comparison']['original_groups'] if (x['prompt_condition'],x['reasoning'])==c and x['baseline_result']==verdict)
                lines.append(f'{verdict} Original forces and transformation numbers {rate(g["numeric"],g["planned"])}')
            out.append(lines)
        return out
    add('M10','Original time-varying reaction','ORIGINAL_VARIANT','stored_aggregate',
        'It\'s a group divided by the original number of the same conditions. 7It\'s not just a numerical response to a transformation of the sum, it\'s not an accuracy of detection, and it\'s a group composition that varies with the conditions.',groups,
        ['original_groups.baseline_result','original_groups.numeric','original_groups.planned'])
    def classification(d,field,variants):
        return [['Classification of output','null classification is a detection failure or','Answer: Explanation: Comparison by circle'] if c[0]=='unguided' else
                [field+'   '+rate(sum(x['classifications'].get(field,0) for x in selected(d,variants,c)),sum(x['planned'] for x in selected(d,variants,c))),
                 'Classification tag returned by model','Independent meaning, or correct judgment.'] for c in CONDITIONS]
    add('M11','The CONFLICT classification of ICs','RESPONSE_PATTERNS','stored_aggregate',
        'It only requires a classification of the guided, not a direct comparison of the unguided and the classification frequency.',lambda d:classification(d,'CONFLICT',IC),['matrix.classifications'])
    add('M12','The INSUFFICIENT_EVIDENCE of the EA is classified','RESPONSE_PATTERNS','stored_aggregate',
        'ANSWERABLE CONFLICT INSUFFICIENT_EVIDENCE UNRESOLVED ABSTAIN The entire distribution connects to the source set of feature-map.json.',lambda d:classification(d,'INSUFFICIENT_EVIDENCE',EA),['matrix.classifications'])
    def transitions(d):
        result=[['The baseline conditions of the two comparisons','Right: Change the only guide','Up: Change the inference settings only']]
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
            result.append([('The reasoning is OFF→ON' if axis=='REASONING' else 'Unguided→Guided')+' · EA counterparts',f'The answer is empty.   {rate(nt,total)}',f'Number → Answer is not   {rate(tn,total)}'])
        return result
    add('M13','The same case is not true.','CONDITION_EFFECTS','stored_aggregate',
        'The whole object-fail pair is stored in paired_groups. The ideal is Guided fixed OFF→ON and not a check of the interaction of the two factors.',transitions,['paired_groups.choice_transitions','paired_groups.comparable_pairs'])
    qualitative=[
        ('M14','The explicit inverse of EA','VARIANT_BEHAVIOR',['reverse_calculation'],'The inverse of the equation is the example shown in the description. The valid recovery success rate is not aggregated.'),
        ('M15','The rest of EA\'s information.','VARIANT_BEHAVIOR',['retained_information','alternative_route','alternative_calculation'],'We\'ll read the rest of the answers, we\'ll review the rest of it, we\'re going to look at the rest of that information, we\'ve looked at other computational pathways, and we\'re not going to estimate the path by the original numbers.'),
        ('M16','Family and friends 0 Processing and non-supplementing','VARIANT_BEHAVIOR',['assumption','zero_assumption','unsupported_assumption','unsupported_guessing','zero_imputation'],'This is a citation that\'s connected to the storage interpretation, and it doesn\'t change the frequency of the tag to the occurrence rate.'),
        ('M17','Conflict explanation: conditional calculation and final answer','RESPONSE_ELEMENTS',['conditional_calculation','conditional_answer','answer_explanation_mismatch','conflict_acknowledged'],'We read the conditional calculations, the collision descriptions, and the connections to the final answer, not the hidden thought process or the total inconsistency rate.'),
        ('M18','Answer: explanation: complexity of the human basis','RESPONSE_ELEMENTS',['answer_explanation_mismatch','evidence_mismatch','citation_mismatch','inconsistency'],'The actual inconsistency is determined by reading the entire response, distinguishing the interpretation from the direct quotation.'),
        ('M19','Mathematics, Stage, Half-lift, and the interpretation of heat','RESPONSE_ELEMENTS',['arithmetic_error','unit_mismatch','rounding','wrong_year','wrong_row','sign_error'],'This is an example of how to apply a relational model to the difference between returning a number.'),
        ('M20','The half-life and the singularity','COUNTEREXAMPLES',['counterexample','contrary_case'],'It preserves the main direction and the different cases, and the four conditions of the same original are not independent repetitions.'),
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
                cells.append(['The occurrence rate · dominant quadrant not aggregated', 'For comparison '+found['case']+' · '+found['variant'],found['observation_id']] if found else
                             ['Examples of these terms are quotes.','It doesn\'t mean there\'s no phenomenon.','Conditionally occurrence rate not aggregated.'])
            refs[d['run']]=model_refs
            return cells
        add(fid,title,category,'qualitative_example',note+' The tag is attached to an observation note that covers several conditions together, and the citations in each can are for a corresponding comparison, not an indication that the phenomenon occurred in that can, and may include the opposite case.',examples,['interpretations.tags','interpretations.excerpts','responses.response'],{'example_links':refs})
    for fid,title,note,fields in [
        ('M21','External knowledge dependence','The current implementation has the function of dividing the external knowledge of the original, but the two comparisons you choose don\'t have a statistic. Used=false is not unnecessary proof.',['original_external_knowledge']),
        ('M22','Depth of calculation:','Now, the two Analysis sets don\'t have a depth-to-measurement comparison, so we need to define the connection between the computational structure first.',['proposed_structure_covariates']),
        ('M23','Stability of independent repetition','Both executions are repeat_comparison_available=false. They don\'t change the difference between the four conditions into independent repetitions of the same condition.',['repeat_comparison_available']),
    ]:
        add(fid,title,'UNAVAILABLE_OR_PROPOSED','not_measured',note,
            lambda d:[['There\'s no reason to place theft on the divide.','Not aggregated from the current selection data.','0 Or not reading it without effect.'] for _ in CONDITIONS],fields)
    return catalog


def esc(s):return html.escape(str(s),quote=True)


def svg_figure(slug,title,model,cells,footer,highlights=None):
    # Categorical axes: the location within each cell carries no quantitative meaning.
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" id="{slug}" viewBox="0 0 1280 800" role="img" aria-labelledby="{slug}-title {slug}-desc">',
           f'<title id="{slug}-title">{esc(title)} · {esc(model)}</title>',
           f'<desc id="{slug}-desc\x22>Unuided Solving on the left, Criteria-Guided Solving to the right, Reasoning OFF at the bottom, ON at the top. {esc(footer)}</desc>',
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
    md=['# Analysis feature quadrants map','', '**In order of reading:** Full map → the opposite direction of each model of the EA → M01–M23 Item by item map → case and not aggregated item.','',
        'The cross-axis is Unguided Solving → Criteria-Guided Solving, the cross-axes are Reasoning OFF → ON. The position or color in the can is not the statistical effect size.','',
        '**Scope:** The data stored in the Luna Haiku Analysis visualizes two executions, not the results of the paper, the adoption of the conclusion, or the execution of a new experimental model.','',
        '**The denominator is:** Original 557The EA is the 2Differentiation x 557 = 1,114Yeah, IC is the 5Differentiation x 557 = 2,785The variations and conditions of the same original are not independent samples.','',
        '**The mark:** The difference between the storage statistics / related citation instances / not aggregated ·representations. The increase in numerical responses, the increase in fairness, and the increase in meaningful accuracy differ from each other.','', '## 1A full map of your conditions.','']
    intro='<h1>Analysis feature quadrant map</h1><p>Line: Judgment guidance or not · Line: Reasoning OFF / ON</p><p>It\'s a technical observation of two stored executions, not a result, a conclusion, and a new experiment.</p>'
    for name,d in data.items():
        slug='overview-'+name.lower()
        rd,gd=metric_delta(d,EA,'numeric')
        foot=f'Changes to EA\x27s OFF→ON: Unguided {rd[0]:+.1f}%p · Guided {rd[1]:+.1f}%p. Figure/null contains a failure field; not a correct answer.'
        heads=({'Luna':['Most of the numbers in ICs are answers.','EA response increase · Original match increase','EA is the most common of the four conditions.','IC is the increase in the empty answer. EA is the increase of the number.'],
                'Haiku':['The EA number is the most of the four conditions.','Increase in original match · EA number decrease','The most common of the four conditions is failure to form.','Increase in IC blank response · decrease in EA numbers']}[name])
        cells=[c+[heads[i]] for i,c in enumerate(main_cells(d))]
        s=svg_figure(slug,'The response patterns that are highlighted in your condition',name,cells,foot,[3])
        sections.append(f'<section id="{slug}-section">{s}<p>{esc(d["run"])}</p></section>')
        md += [f'### {name}',f'![{name} The full map of the four conditions.{slug}.svg)','']
        rd,gd=metric_delta(d,EA,'numeric')
        md += [f'EA figures change the response rate OFF→ON: **Unguided {rd[0]:+.1f}%p / Guided {rd[1]:+.1f}%p**Changes to the guide add: OFF {gd[0]:+.1f}%p / ON {gd[1]:+.1f}%p.','']
    md += ['Luna has higher EA response rates in the top two quarters, and Haiku has higher EA responses in the bottom two quarters. So if you use Reasoning ON, the EA response rate will be higher, so it doesn\'t show the same quality as all models.','',
           'Haiku is a form failure. 1,198Dry and cut off power. 5So we have to look at the response field and the form validity together.4The Failure of the Law, M1.3Silver represents the corresponding pair that is valid in both formats.','',
           '## 2All the analytical items have a colour arrangement.','',
           'The comparison of the current data on the map','|---|---|---|']
    statuses={'stored_aggregate':'Saved aggregates','qualitative_example':'Quoted cases \xb7 strength not aggregated','not_measured':'Not aggregated / proposed'}
    for f in catalog:md.append(f'|{f["id"]} {f["title_ko"]}|{f["category"]}|{statuses[f["status"]]}|')
    for f in catalog:
        md += ['',f'## {f["id"]}. {f["title_ko"]}','',f'**The state of the evidence: {statuses[f["status"]]}**',f['note_ko'],'']
        body=[f'<details id="{f["id"]}"><summary>{f["id"]} · {esc(f["title_ko"])} <small>{statuses[f["status"]]}</small></summary><p>{esc(f["note_ko"])}</p>']
        for name,d in data.items():
            slug=f['id'].lower()+'-'+name.lower()
            s=svg_figure(slug,f['id']+' · '+f['title_ko'],name,f['models'][name]['cells'],statuses[f['status']]+' · '+d['run']+' · Location is a condition, not an intuition or sensitivity of the effect.')
            body.append(s);md += [f'![{f["id"]} {name} · {f["title_ko"]}](figures/{slug}.svg)','']
            if f.get('example_links'):
                for idx,ref in enumerate(f['example_links'].get(d['run'],[])):
                    if not ref:continue
                    quote=ref['quote']
                    body.append(f'<div class="evidence"><b>{esc(name+" · "+LABELS[idx]+" · "+ref["observation_id"])}</b><p>{esc(ref["observation_ko"])}</p><blockquote>{esc(quote)}</blockquote><p>{esc(ref["limitation_ko"])}</p><code>{esc(ref["response_id"])}</code></div>')
                    md += [f'**Examples of quotes {name} / {LABELS[idx]} / {ref["observation_id"]}**',ref['observation_ko'],f'Raw response quote: {quote}',f'The limits of interpretation: {ref["limitation_ko"]}',f'Answer ID: `{ref["response_id"]}`','']
        body.append('</details>');sections.append(''.join(body))
    md += ['## 3Analysis linking categories and maps','',
           'Analysis of the categories and the map','|---|---|',
           '♬ 1 Full response rate M 01–M04, M11–M12|','And then I\'m going to have to go back to the original and the modification.3, M09–M10|','3 conditions, model effect, M, the full map of each model.1–M13The cross-sectional comparison, M13The answer is',
           'Four types of selection.5–M09, M14–M16|','5 Ans: Distribution, explanation, neighborhood relations M11–M12, M17–M19|','Six half-hours. Special case of the M2.0EA direction is two different models',
           'Study 7 Interpretation of the map: Observation, Alternative Explanation, Linking the boundaries, independent additional effects or not duplicating it into new conclusions.','',
           'External knowledge is M2.1So, the computational structure suggests M2.2So, independent repeats are M2.3These were not forced to be placed in the current strength-confirmed compartment.','',
           '## 4The raw materials and the reproduction range.','',
           'This document uses only examples of accurate citations of existing interpretations, showing the sums and ratios already stored on comparisons.json. There are no new model calls, meaningful answer trials, verification of probability or analysis pipeline executions.','',
           '[Mapping the whole thing, case ID](feature-map.json) • [Full summary of the results]](source-snapshot.json) • [Reading order]](README.md)','']
    for name,d in data.items():
        md += [f'[{name} I\x27m going to run experiments.{d["run"]}/02_analysis/02_comparison/comparisons.json)',f'[{name} I\x27m going to run experiments.{d["run"]}/02_analysis/01_results/responses.jsonl)',f'[{name} I\x27m going to try to run the experiment.{d["run"]}/02_analysis/02_comparison/interpretations.jsonl)','']
    style='''body{margin:0;background:#f5f6f4;color:#23322e;font:17px/1.8 system-ui,sans-serif}main{max-width:1280px;margin:auto;padding:28px}h1{font-size:30px}p,li,blockquote{font-size:17px}svg{display:block;width:100%;height:auto;background:white}section,details{border:1px solid #dce3dd;margin:24px 0;background:white;padding:20px;border-radius:6px}summary{cursor:pointer;font-weight:650;font-size:21px}small{font-size:15px;color:#52685f}nav{display:flex;flex-wrap:wrap;gap:12px}a{color:#245b4e}blockquote{border-left:3px solid #276754;padding-left:18px}code{overflow-wrap:anywhere}.evidence{margin:24px 0;border-top:1px solid #dce3dd} @media(max-width:700px){main{padding:12px}section,details{padding:12px}summary{font-size:18px}svg{min-width:760px}section,details{overflow:auto}} @media print{details{display:block}summary{break-after:avoid}svg{break-inside:avoid}}'''
    nav='<nav>'+''.join(f'<a href="#{f["id"]}">{f["id"]} {esc(f["title_ko"])}</a>' for f in catalog)+'</nav>'
    content='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Analysis feature quadrant map</title><style>'+style+'</style></head><body><main>'+intro+nav+''.join(sections)+'</main></body></html>'
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
    entry={'id':RUN_ID,'title':'2026-09-28 · Analysis of the square map · Luna; Haiku and 23items'}
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
