"""Update local paper tables from the verified PASS cohort snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import html
from importlib import import_module
import json
from pathlib import Path
import re
import shutil
import subprocess

pool=import_module('finarch.experiments.02-analysis.01-results.final_cohort')
ROOT=pool.ROOT
OUTPUT=ROOT/'reports/analysis/20261008-finject-1354'
LOCAL=ROOT/'paper/local-preview'
REVIEW=ROOT/'reports/run/20261003-paper-revision-draft'
STATE=ROOT/'paper/instructdion/MANUSCRIPT-STATE.json'
VIS=Path('/Users/wooix/.codex/visualizations/2026/10/02/01a0fb53-72f4-7ca1-9765-8977e7c0b21f')


def pct(value):
    return 'N/A' if value is None else f'{value*100:.1f}'


def delta(value):
    return 'N/A' if value is None else f'{value:+.1f}'


def num(value):
    return f'{value:,}'


def condition(g, r):
    signs={'ON':'⁺','OFF':'⁻'}
    return 'G'+signs[g]+'R'+signs[r]


def combine_conditions(headers, rows):
    if 'G' not in headers or 'R' not in headers:
        return headers, rows
    i=headers.index('G')
    assert headers[i+1]=='R'
    return (headers[:i]+['GR']+headers[i+2:],
            [row[:i]+[condition(row[i],row[i+1])]+row[i+2:] for row in rows])


def html_cell(value):
    if re.fullmatch(r'G[⁺⁻]R[⁺⁻]',str(value)):
        return 'G<sup>'+('+' if value[1]=='⁺' else '−')+'</sup>R<sup>'+('+' if value[3]=='⁺' else '−')+'</sup>'
    return html.escape(str(value))


def protocol_condition_labels(content):
    def table(match):
        block=match.group(0)
        if not re.search(r'>(Unguided|Guided) / (ON|OFF)</td>',block):return block
        block=re.sub(r'(<td\b[^>]*>)(Unguided|Guided) / (ON|OFF)(</td>)',
                     lambda m:m[1]+html_cell(condition('ON' if m[2]=='Guided' else 'OFF',m[3]))+m[4],block)
        block=re.sub(r'(<td\b[^>]*>)(ON|OFF)(</td>)',
                     lambda m:m[1]+'R<sup>'+('+' if m[2]=='ON' else '−')+'</sup>'+m[3],block)
        return block.replace('Condition</strong>','GR</strong>').replace('>조건<','>GR<')
    return re.sub(r'<table\b.*?</table>',table,content,flags=re.S)


def protocol_markdown_labels(content):
    def row(match):
        cells=match.group(0).split('|')
        if len(cells)!=5:return match.group(0)
        source=re.fullmatch(r'(Unguided|Guided) / (ON|OFF)',cells[1].strip())
        if not source or cells[3].strip()!=source[2]:return match.group(0)
        cells[1]=' '+html_cell(condition('ON' if source[1]=='Guided' else 'OFF',source[2]))+' '
        cells[3]=' R<sup>'+('+' if source[2]=='ON' else '−')+'</sup> '
        return '|'.join(cells)
    return re.sub(r'^\|[^\n]*\b(?:Unguided|Guided) / (?:ON|OFF)[^\n]*$',row,content,flags=re.M)


def html_table(headers, rows, caption, identity):
    headers,rows=combine_conditions(headers,rows)
    return '<table id="'+identity+'"><caption>'+caption+'</caption><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html_cell(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'


def latex(value):
    if re.fullmatch(r'G[⁺⁻]R[⁺⁻]',str(value)):
        return '$G^{'+('+' if value[1]=='⁺' else '-')+'}R^{'+('+' if value[3]=='⁺' else '-')+'}$'
    return str(value).replace('_',r'\_').replace('%',r'\%').replace('&',r'\&')


def detail_table(headers, rows, caption):
    headers,rows=combine_conditions(headers,rows)
    spec='l'+'r'*(len(headers)-1)
    text=r'\begin{table*}[!ht]\centering\begingroup\scriptsize\setlength{\tabcolsep}{2.5pt}'+'\n'
    text+=r'\begin{tabular}{'+spec+'}\n'+r'\toprule'+'\n'
    text+=' & '.join(latex(x) for x in headers)+r' \\'+'\n'+r'\midrule'+'\n'
    text+='\n'.join(' & '.join(latex(x) for x in row)+r' \\' for row in rows)
    text+='\n'+r'\bottomrule\end{tabular}\endgroup\caption{'+caption+r'}\end{table*}'+'\n'
    return text


def summary_table(s, kind):
    models=s['models'][:5]
    width=3 if kind==1 else 4
    total=1+5*width
    font=r'\footnotesize' if kind==1 else r'\fontsize{6.5}{8}\selectfont'
    text=r'\begin{table*}[!ht]\centering\begingroup'+font+r'\setlength{\tabcolsep}{1pt}\renewcommand{\arraystretch}{1.15}'+'\n'
    if kind==3:
        text+=r'\resizebox{\textwidth}{!}{\begin{tabular}{@{}c*{5}{'+'r'*width+'}@{}}\n'
    else:
        text+=r'\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}c*{5}{'+'r'*width+'}@{}}\n'
    text+=r'\toprule'+'\n'
    text+=' & '+' & '.join(r'\multicolumn{'+str(width)+'}{c}{'+m+'}' for m in models)+r' \\'+'\n'
    for i in range(5): text+=r'\cmidrule(lr){'+str(2+i*width)+'-'+str(1+(i+1)*width)+'}'
    metric_headers=['O*','N(n)','A(n)'] if kind==1 else ['O','C','I',r'$\Delta_{C-I}$'] if kind==2 else [r'AS$_1$/n',r'Retain$_1$',r'AS$_2$/n',r'Retain$_2$']
    text+='\nGR & '+' & '.join(metric_headers*5)+r' \\'+'\n'+r'\midrule'+'\n'
    for g,r in [('OFF','OFF'),('OFF','ON'),('ON','OFF'),('ON','ON')]:
        cells=[latex(condition(g,r))]
        for model in models:
            entry=next(x for x in s['rq'+str(kind)] if (x['model'],x['G'],x['R'])==(model,g,r))
            if kind==1:
                for rate,den in [(entry['O'],entry['resolved']),(entry['N'],entry['NS']+entry['NU']),(entry['A'],entry['AS']+entry['AU'])]:
                    cells.append(r'\shortstack[r]{'+pct(rate)+r'\\{\scriptsize ('+num(den)+')}}')
            elif kind==2:
                cells.extend([pct(entry['O']),pct(entry['C']['O']),pct(entry['I']['O']),delta(entry['delta_pp'])])
            else:
                for pair in (1,2):
                    x=next(x for x in s['rq3'] if (x['model'],x['G'],x['R'],x['pair'])==(model,g,r,pair))
                    cells.extend([num(x['before'])+'/'+num(x['n']),r'\shortstack[r]{'+num(x['retained'])+'/'+num(x['before'])+r'\\{\scriptsize '+pct(x['retention'])+r'\%}}' if x['before'] else 'N/A'])
        text+=' & '.join(cells)+r' \\'+'\n'+r'\addlinespace[3pt]'+'\n'
    captions={1:'Response support on the pooled FInject human-PASS cohort. Each model and G/R condition has 6,770 planned responses from five variants of 1,354 originals.',
              2:'Original numerical correctness and variant support in the pooled FInject cohort. O is original numerical accuracy; C and I are variant support rates in the original-correct and original-incorrect groups. Differences are percentage points.',
              3:'Supported abstention before source attribution and retention afterward in the pooled FInject cohort. Each model, condition, and pair has 1,354 planned pairs.'}
    notes={1:r'O*=(NS+AS)/(NS+NU+AS+AU); N=NS/(NS+NU); A=AS/(AS+AU). Values are percentages; parentheses give resolved denominators. ND/AD and unavailable reviews remain in planned counts. Appendix A reports coverage and all-planned NS/AS shares.',
           2:r'C/I use S/(S+U) with S=NS+AS and U=NU+AU, restricted to the corresponding original group. Unknown original outcomes remain separate. Appendix B reports group counts, numerators, denominators and exclusions.',
           3:r'Pair 1: IC-v before $\rightarrow$ IC-s A; Pair 2: IC-v after $\rightarrow$ IC-s B. AS Before uses pairs resolved on both sides. Retain gives AS-to-AS / previous AS and its percentage. N/A denotes no previous AS. Appendix C reports excluded pairs and transitions.'}
    end_table=r'\end{tabular}}' if kind==3 else r'\end{tabular*}'
    text+=r'\bottomrule'+end_table+r'\endgroup\caption{'+captions[kind]+r'}\label{tab:finject-rq'+str(kind)+r'}'+'\n'
    text+=r'\begin{minipage}{\textwidth}\scriptsize G: Guidance; R: Reasoning; $+$: enabled; $-$: disabled. '+notes[kind]+r' All available A02 assessments use \texttt{gpt-6.1-sol / low}. Gemini has no valid selected responses or completed A02; its rates are unavailable.\end{minipage}\end{table*}'+'\n'
    return text


def write_tables(s):
    supplement=''
    for kind in (1,2,3):
        fragment=summary_table(s,kind)
        (LOCAL/f'final-cohort-rq{kind}.tex').write_text(fragment)
        if kind==1:
            head=['Model','G','R','Plan','Reviewed','D','F','NS/Plan','AS/Plan']
            rows=[[r['model'],r['G'],r['R'],num(r['planned']),num(r['reviewed']),num(r['D']),num(r['F']),pct(r['NS_share']),pct(r['AS_share'])] for r in s['rq1']]
            cap='RQ1 coverage for the fixed FInject cohort. Reviewed includes S/U/D assessments. NS/Plan and AS/Plan are percentages of all 6,770 planned responses.'
        elif kind==2:
            head=['Model','G','R','C/I/?','C S/n','I S/n','C D/F','I D/F']
            rows=[[r['model'],r['G'],r['R'],'/'.join(num(r['originals'][c]) for c in ('CORRECT','INCORRECT','UNKNOWN')),num(r['C']['S'])+'/'+num(r['C']['resolved']),num(r['I']['S'])+'/'+num(r['I']['resolved']),num(r['C']['D'])+'/'+num(r['C']['F']),num(r['I']['D'])+'/'+num(r['I']['F'])] for r in s['rq2']]
            cap='RQ2 group counts and support denominators. C/I/? denote original numerical match, mismatch, and unknown. A valid original null belongs to numerical mismatch. Group assignments do not assess explanation quality.'
        else:
            head=['Model','G','R','Pair','n/Plan','Before','After','Retain','New','D/F']
            rows=[[r['model'],r['G'],r['R'],r['pair'],num(r['n'])+'/'+num(r['planned']),num(r['before']),num(r['after']),num(r['retained']),num(r['new']),num(r['excluded'].get('D',0))+'/'+num(r['excluded'].get('F',0))] for r in s['rq3']]
            cap='RQ3 resolved pairs, AS counts and exclusions in FInject. Retain counts AS-to-AS; New counts transitions from a non-AS outcome to AS among resolved pairs.'
        detail=''
        # Split the appendix into bounded tables to avoid overflow across pages.
        for start in range(0,len(rows),24): detail+=detail_table(head,rows[start:start+24],cap)
        appendix=chr(64+kind)
        supplement+=r'\clearpage\subsection*{FInject result supplement '+appendix+'}\n'+detail
        standalone='% FInject PASS snapshot: '+s['generated_at']+'; no new model calls.\n% Source: reports/analysis/20261008-finject-1354/summary.json\n'
        standalone+=r'\documentclass[11pt,a4paper]{article}\usepackage[margin=2.5cm]{geometry}\usepackage{times}\usepackage[T1]{fontenc}\usepackage{booktabs,array,amsmath,graphicx}\usepackage[hidelinks]{hyperref}\pagestyle{empty}\begin{document}'+'\n'
        standalone+=fragment+r'\clearpage\section*{Appendix '+appendix+'. FInject pooled counts}\n'+detail+r'\end{document}'+'\n'
        (LOCAL/f'rq{kind}-table.tex').write_text(standalone)
    (LOCAL/'final-cohort-appendices.tex').write_text(supplement)


def update_review(s):
    path=REVIEW/'paper-review.json';original=path.read_bytes();sections=json.loads(original)
    for section in sections:
        for lang in ('en','ko'):
            prior=section.get(lang+'html','');updated=protocol_condition_labels(prior)
            if prior!=updated:
                section[lang+'html']=updated;section['state']='revised'
    main=s['models'][:5]
    rates=[[r['model'],r['G'],r['R'],pct(r['O']),num(r['resolved']),pct(r['N']),pct(r['A']),pct(r['NS_share']),pct(r['AS_share']),num(r['D']),num(r['F'])] for r in s['rq1'] if r['model'] in main]
    cohorts=[[r['model'],r['G'],r['R'],num(r['originals']['CORRECT']),num(r['originals']['INCORRECT']),num(r['originals']['UNKNOWN']),pct(r['C']['O']),f"{r['C']['S']:,}/{r['C']['resolved']:,}",pct(r['I']['O']),f"{r['I']['S']:,}/{r['I']['resolved']:,}",delta(r['delta_pp'])] for r in s['rq2'] if r['model'] in main]
    pairs=[[r['model'],r['G'],r['R'],r['pair'],num(r['n']),num(r['before']),num(r['after']),num(r['retained']),num(r['new']),pct(r['retention']),num(r['excluded'].get('D',0)),num(r['excluded'].get('F',0))] for r in s['rq3'] if r['model'] in main]
    coverage=[[r['model'],r['G'],r['R'],num(r['planned']),num(r['reviewed']),num(r['D']),num(r['F']),pct(r['NS_share']),pct(r['AS_share'])] for r in s['rq1']]
    tables={
        'en':html_table(['Model','G','R','O* %','Resolved n','N %','A %','NS/Plan %','AS/Plan %','D','F'],rates,'Response support in FInject; planned n=6,770 per condition.','tab:finject-rq1')+
             html_table(['Model','G','R','Correct','Incorrect','Unknown','C %','C S/n','I %','I S/n','C-I pp'],cohorts,'Original numerical groups and variant support in FInject.','tab:finject-rq2')+
             html_table(['Model','G','R','Pair','Resolved n','Before AS','After AS','Retained','New','Retention %','Excluded D','Excluded F'],pairs,'IC-v to IC-s supported abstention retention; planned n=1,354 per pair.','tab:finject-rq3'),
        'ko':html_table(['모델','G','R','전체 지원 O* %','판정 분모','숫자 지원 N %','기권 지원 A %','NS/계획 %','AS/계획 %','D','F'],rates,'FInject 응답 지원 비율: 조건당 계획 6,770건.','tab:finject-rq1')+
             html_table(['모델','G','R','원본 정답','오답','미확인','정답 집단 C %','C S/분모','오답 집단 I %','I S/분모','차이 %p'],cohorts,'FInject 원본 숫자 정답/오답 집단의 변형 지원.','tab:finject-rq2')+
             html_table(['모델','G','R','쌍','판정된 쌍','이전 AS','이후 AS','유지','새 AS','유지율 %','제외 D','제외 F'],pairs,'IC-v→IC-s의 지원 기권 유지: 조건·쌍당 계획 1,354건.','tab:finject-rq3')}
    intros={
        'en': '<p>We reaggregate existing Evaluation and latest A02 records for the 1,354 FInject families whose seven variants passed human review. FinanceReasoning contributes 1,071 families and TAT-QA contributes 283. Source identifiers link the final items to frozen experimental inputs; their questions and contexts match exactly. We sum response counts before calculating rates, with each family receiving equal weight.</p><p>The support comparison uses five variants per family, giving 6,770 planned responses in each G/R condition. O*=(NS+AS)/(NS+NU+AS+AU), N=NS/(NS+NU), and A=AS/(AS+AU). NS/Plan and AS/Plan retain all planned responses in their denominators. D denotes unresolved judgments and F unavailable or incomplete reviews. RQ2 conditions on original numerical match or mismatch; unknown outcomes stay separate. RQ3 uses two IC-v to IC-s pairs, with 1,354 planned pairs each and both support judgments resolved for the retention denominator.</p>',
        'ko': '<p>7개 변형이 모두 human PASS인 FInject 1,354개 문항군에 대해 기존 Evaluation과 최신 A02 저장 기록을 재집계했습니다. FinanceReasoning 1,071개와 TAT-QA 283개를 포함합니다. 최종 ID를 원천 문항 및 동결 실험 입력에 연결했으며 질문·본문이 모두 일치합니다. 각 문항군에 같은 가중치를 주고 건수를 합산한 뒤 비율을 계산합니다.</p><p>지원 비율 비교에는 문항군당 5개 변형을 사용하므로 G/R 조건마다 계획 6,770건입니다. O*=(NS+AS)/(NS+NU+AS+AU), N=NS/(NS+NU), A=AS/(AS+AU)입니다. NS/계획·AS/계획에는 모든 계획 응답을 포함합니다. D는 판단 유보, F는 검토 불가·미완료입니다. RQ2는 원본 숫자 일치/불일치 집단을 비교하며 미확인은 별도로 남깁니다. RQ3의 IC-v→IC-s 두 쌍은 각각 계획 1,354건이며, 유지율에는 양쪽 지원 판정이 확정된 쌍을 사용합니다.</p>'}
    endings={
        'en':'<p>Five models have available A02 evidence across all four conditions, with response failures and unresolved judgments retained in coverage counts. Gemini has no valid selected responses: its stored R-ON records include batch, format and truncation failures and uncollected requests, while R-OFF was not configured. Its A02 support rates are unavailable. No model was called for this reaggregation. Saved runs retain the legacy classification contract described in the evaluation appendix; this reaggregation does not establish alignment with the revised collection contract or independent answerability gold.</p>',
        'ko':'<p>5개 모델은 네 조건에 대해 A02 근거 기록이 있으며, 응답 실패와 판단 유보를 검토 범위에 보존했습니다. Gemini의 선택 문항에는 유효 응답이 없습니다. 기존 R-ON 기록은 배치 오류·형식 실패·잘린 출력·미수집 요청을 포함하며 R-OFF는 미설정입니다. Gemini의 A02 지원 비율은 미확인입니다. 이번 재집계의 새 모델 호출은 0건입니다. 저장 run의 이전 classification 계약은 평가 부록에 명시된 차이를 유지합니다. 재집계 완료가 수정된 수집 계약의 정합성이나 독립적인 답변가능성 gold를 확정하지 않습니다.</p>'}
    record=next((x for x in sections if x['id']=='s4-5'),None)
    if record is None:
        record={'id':'s4-5','en':'4.5 Saved Results for the Final FInject Cohort','ko':'4.5 최종 FInject 코호트의 저장 결과','enhtml':'','kohtml':'','olden':'','oldko':'','state':'revised','level':1}
        sections.insert(next(i for i,x in enumerate(sections) if x['id']=='s5'),record)
    for lang in ('en','ko'):
        if record[lang+'html'] and not record.get('old'+lang):record['old'+lang]=record[lang+'html']
        record[lang+'html']=intros[lang]+tables[lang]+endings[lang];record['state']='revised'
        section=next(x for x in sections if x['id']=='s4')
        if not section.get('old'+lang):section['old'+lang]=section[lang+'html']
        note=('Review note: Section 4 uses the revised output contract. Saved runs retain an earlier classification contract, as documented in the evaluation appendix. Section 4.5 reports completed reaggregation of the final human-PASS cohort from these saved records; collection-contract alignment remains pending.' if lang=='en' else '검토 메모: 4장은 수정된 응답 계약을 사용합니다. 저장 run은 평가 부록에 기록한 이전 classification 계약을 유지합니다. 4.5절은 이 저장 기록을 최종 human PASS 코호트로 재집계한 결과이며, 수정된 수집 계약과의 정합성은 아직 미확인입니다.')
        section[lang+'html']=re.sub(r'<aside\b.*?</aside>','<aside class="pending" role="note" data-verification-status="CONTRACT_ALIGNMENT_PENDING">'+note+'</aside>',section[lang+'html'],count=1,flags=re.S);section['state']='revised'
    appendix=next((x for x in sections if x['id']=='s11-pooled-results'),None)
    previous_coverage={lang:appendix.get(lang+'html','') if appendix else '' for lang in ('en','ko')}
    if appendix is None:
        appendix={'id':'s11-pooled-results','en':'Appendix #. Final-Cohort Response Coverage','ko':'Appendix #. 최종 코호트 응답 검토 범위','enhtml':'','kohtml':'','olden':'','oldko':'','state':'revised','level':1}
        sections.insert(next(i for i,x in enumerate(sections) if x['id']=='s11-rubric'),appendix)
    appendix['enhtml']=html_table(['Model','G','R','Planned','Reviewed','D','F','NS/Plan %','AS/Plan %'],coverage,'Final FInject cohort; main five variants. Reviewed includes resolved and undetermined assessments.','tab:finject-coverage')+endings['en']
    appendix['kohtml']=html_table(['모델','G','R','계획','검토 완료','D','F','NS/계획 %','AS/계획 %'],coverage,'최종 FInject의 주요 5개 변형. 검토 완료는 확정 및 판단 유보 판정을 포함합니다.','tab:finject-coverage')+endings['ko']
    conclusion=next(x for x in sections if x['id']=='conclusion')
    conclusion_notes={
        'en':'Provisional conclusion: Section 4.5 now reports reaggregated saved results for the final FInject cohort of 1,354 originals. These findings remain based on LLM-judge assessments; collection-contract alignment and independent human validation of the model assessments remain pending.',
        'ko':'임시 결론: 4.5절에는 최종 FInject 원본 1,354개 기준으로 재집계한 저장 결과를 반영했다. 아래 해석은 LLM 판정에 기반하며, 수정된 수집 계약과의 정합성 및 모델 응답 판정의 독립적인 사람 검증은 아직 미확인이다.'}
    prior_notes={}
    for lang in ('en','ko'):
        note=re.search(r'<p class="pending" role="note">(.*?)</p>',conclusion[lang+'html'],flags=re.S)
        if note:
            prior_notes[lang]=html.unescape(note.group(1))
            if not conclusion.get('old'+lang):conclusion['old'+lang]=conclusion[lang+'html']
            conclusion[lang+'html']=conclusion[lang+'html'][:note.start(1)]+conclusion_notes[lang]+conclusion[lang+'html'][note.end(1):]
    conclusion['state']='revised'
    backup=REVIEW/'backup/20261008-finject-pooled-results';backup.mkdir(parents=True,exist_ok=True)
    for p in [path,REVIEW/'PAPER-EN.md',REVIEW/'PAPER-KO.md',STATE,LOCAL/'main.tex',LOCAL/'revision-20261002-body.tex',*[LOCAL/f'rq{k}-table.tex' for k in (1,2,3)]]:
        if p.exists() and not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
    assert path.read_bytes()==original, 'USER_EDIT_DURING_UPDATE'
    pool.dump(path,sections)
    template=(ROOT/'src/finarch/documentation/templates/research/paper-revision.html').read_text()
    for lang,name in [('en','finject-introduction-redline.html'),('ko','finject-introduction-ko-redline.html')]:
        payload=json.dumps(sections,ensure_ascii=False).replace('</','<\\/')
        (VIS/name).write_text(template.replace('__DEFAULT_LANG__',lang).replace('__DOCUMENT_DATA__',payload))
        chunk='\n\n'.join(('### ' if x['level'] else '## ')+x[lang]+'\n\n'+subprocess.run(['pandoc','-f','html','-t','gfm','--wrap=none'],input=x[lang+'html'],text=True,capture_output=True,check=True).stdout for x in sections if x['id'].startswith('s4'))
        mdpath=REVIEW/f'PAPER-{lang.upper()}.md';md=mdpath.read_text()
        md=protocol_markdown_labels(md)
        md=re.sub(r'## 4\..*?(?=## 5\.)',lambda m:chunk+'\n\n',md,count=1,flags=re.S)
        coverage_md=subprocess.run(['pandoc','-f','html','-t','gfm','--wrap=none'],input=appendix[lang+'html'],text=True,capture_output=True,check=True).stdout
        marker='### '+appendix[lang]
        if marker not in md: md=md.replace('### '+next(x for x in sections if x['id']=='s11-rubric')[lang],marker+'\n\n'+coverage_md+'\n\n### '+next(x for x in sections if x['id']=='s11-rubric')[lang])
        elif previous_coverage[lang]:
            prior_coverage_md=subprocess.run(['pandoc','-f','html','-t','gfm','--wrap=none'],input=previous_coverage[lang],text=True,capture_output=True,check=True).stdout
            assert prior_coverage_md in md, 'USER_EDITED_COVERAGE_MARKDOWN'
            md=md.replace(prior_coverage_md,coverage_md,1)
        if lang in prior_notes:md=md.replace(prior_notes[lang],conclusion_notes[lang],1)
        mdpath.write_text(md)
    state=json.loads(STATE.read_text());state['chapter4']['final_cohort_results']='Reaggregated from saved Evaluation and latest A02 records for 1354 human-PASS families; source/final/frozen input equality verified; zero new calls.'
    state['chapter4']['results_snapshot']=str(OUTPUT.relative_to(ROOT));state['chapter4']['collection_contract_alignment']='PENDING_LEGACY_RUN_CONTRACT'
    state['chapter4']['support_rates_available_models']=main;state['chapter4']['unavailable_model']='Gemini 3.5 Flash Lite: no valid selected responses; A02 not run; R-OFF not configured.'
    state['chapter4']['reaggregated_at']=s['generated_at'];pool.dump(STATE,state)
    return sections


def local_protocol(sections):
    text=''
    for item in sections:
        if item['id']=='s3-4' or item['id'].startswith('s4'):
            if item['id']=='s4-5':
                text+=r'\subsection{Saved Results for the Final FInject Cohort}'+'\n'+r'\input{final-cohort-results-intro}'+'\n'
                for kind in (1,2,3):text+=r'\input{final-cohort-rq'+str(kind)+'}\n'
                text+=r'\input{final-cohort-results-note}'+'\n';continue
            heading=item['en'].split(' ',1)[1]
            text+=(r'\section{' if item['id']=='s4' else r'\subsection{')+heading+'}\n'
            text+=subprocess.run(['pandoc','-f','html','-t','latex','--wrap=none'],input=item['enhtml'],text=True,capture_output=True,check=True).stdout+'\n'
    text=text.replace('κ',r'\ensuremath{\kappa}').replace('×',r'\ensuremath{\times}')
    # Review-page anchors are not labels in the local multi-file manuscript.
    text=re.sub(r'\\hyperref\[s11-[^\]]+\]\{([^{}]+)\}',r'\1',text)
    text=text.replace('\\[\n\\begin{aligned}',r'\begingroup\small'+'\n\\[\n\\begin{aligned}',1)
    text=text.replace('\\end{aligned}\n\\]', '\\end{aligned}\n\\]\n'+r'\endgroup',1)
    (LOCAL/'final-cohort-protocol.tex').write_text(text)
    item=next(x for x in sections if x['id']=='s4-5')
    intro=item['enhtml'].split('<table',1)[0]
    note=item['enhtml'][item['enhtml'].rfind('</table>')+8:]
    for name,content in [('intro',intro),('note',note)]:
        (LOCAL/f'final-cohort-results-{name}.tex').write_text(subprocess.run(['pandoc','-f','html','-t','latex','--wrap=none'],input=content,text=True,capture_output=True,check=True).stdout)
    body=LOCAL/'revision-20261002-body.tex';current=body.read_text()
    if r'\input{final-cohort-protocol}' not in current:
        start=current.index(r'\section{Release Sampling and Human Verification}')
        stop=current.index(r'\setcounter{section}{4}',start)
        current=current[:start]+r'\input{final-cohort-protocol}'+'\n\n'+current[stop:]
        current=current.replace(r'\section{Task and Metrics}',r'\section{Task and Metrics}'+'\n'+r'\noindent\textit{Earlier proposal retained for review. Section 4 describes the current protocol and saved-run results; the following RQ/F1 proposal is not a report of completed evaluation.}'+'\n',1)
        body.write_text(current)
    if r'\input{final-cohort-appendices}' not in body.read_text():
        body.write_text(body.read_text()+'\n'+r'\input{final-cohort-appendices}'+'\n')
    # Retain pre-selection provenance counts and update their obsolete status note.
    body.write_text(body.read_text().replace(
        'Final human-annotation counts, exclusions, and agreement remain to be reported.',
        'Final human selection retains 1,354 families (1,071 FinanceReasoning and 283 TAT-QA), with 9,478 variants; 197 candidate families are excluded. Section 3.4 reports the selection rule and agreement before selection.'))
    body_text=body.read_text()
    def protocol_row(match):
        assert match[2]==match[4]
        return latex(condition('ON' if match[1]=='Guided' else 'OFF',match[2]))+match[3]+'$R^{'+('+' if match[4]=='ON' else '-')+'}$'+match[5]
    updated=re.sub(r'^(Unguided|Guided) / (ON|OFF)( & [^\n]* & )(ON|OFF)( \\\\)$',protocol_row,body_text,flags=re.M)
    if updated!=body_text:
        updated=updated.replace(r'\textbf{Condition} & \textbf{Decision guidance}',r'\textbf{GR} & \textbf{Decision guidance}',1)
        body.write_text(updated)
    main=LOCAL/'main.tex';main_text=main.read_text()
    final_count='The final FInject dataset contains 1,354 originals and 9,478 variants that pass human review.'
    if final_count not in main_text:
        main.write_text(main_text.replace('We evaluate whether models',final_count+' We evaluate whether models',1))


def main():
    s=json.loads((OUTPUT/'summary.json').read_text())
    manifest=json.loads((OUTPUT/'manifest.json').read_text())
    assert sha256((OUTPUT/'summary.json').read_bytes()).hexdigest()==manifest['outputs']['summary.json']
    sections=update_review(s)
    write_tables(s)
    local_protocol(sections)
    files=[REVIEW/'paper-review.json',REVIEW/'PAPER-EN.md',REVIEW/'PAPER-KO.md',STATE,
           LOCAL/'main.tex',LOCAL/'revision-20261002-body.tex',LOCAL/'final-cohort-protocol.tex',
           LOCAL/'final-cohort-results-intro.tex',LOCAL/'final-cohort-results-note.tex',LOCAL/'final-cohort-appendices.tex',
           *[LOCAL/f'rq{k}-table.tex' for k in (1,2,3)],*[LOCAL/f'final-cohort-rq{k}.tex' for k in (1,2,3)]]
    pool.dump(OUTPUT/'publication.json',{'updated_at':datetime.now(timezone.utc).isoformat(),'overleaf_modified':False,
        'source_summary_sha256':manifest['outputs']['summary.json'],'files':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files}})
    print(json.dumps({'paper_updated':True,'source_families':1354,'new_model_calls':0,'overleaf_modified':False}))


if __name__=='__main__':main()
