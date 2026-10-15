"""Apply the reviewed wording locally; never connect to Overleaf."""
from pathlib import Path
import copy
import json
import re
import subprocess
from bs4 import BeautifulSoup
import sync_paper_revision as sync

ROOT = sync.ROOT
CONTENT = ROOT/'paper/local-preview-content/review-applied'
RUN = ROOT/'reports/run/20261003-review-applied'
BACKUP = RUN/'backup'


def convert(text, source='markdown', target='html'):
    return subprocess.run(['pandoc','-f',source,'-t',target,'--wrap=none','--biblatex'],input=text,text=True,capture_output=True,check=True).stdout


def blocks(lang):
    parts = re.split(r'<!-- SECTION:([^ ]+) -->', (CONTENT/f'{lang}.md').read_text())
    return dict(zip(parts[1::2], parts[2::2]))


def html_text(md):
    doc = BeautifulSoup(convert(md), 'html.parser')
    for span in doc.select('[data-cites]'):
        keys = span['data-cites'].split()
        new = BeautifulSoup('('+ '; '.join(citations[k] for k in keys)+')','html.parser')
        span.replace_with(new)
    return str(doc)


def tex_text(md):
    text = convert(md, target='latex').replace(r'\autocite',r'\citep')
    for n,label in [(1,'fig:abstention-intro'),(2,'fig:revision-1'),(3,'fig:revision-2'),(4,'fig:pipeline-full'),(5,'fig:revision-5')]:
        text = text.replace(f'Figure {n}', 'Figure~\\ref{'+label+'}')
    return text


original = json.loads((BACKUP/'paper-review.json').read_text())
citations = {}
for item in original:
    for a in BeautifulSoup(item['enhtml'],'html.parser').select('a[href^="#ref-"]'):
        citations.setdefault(a['href'][5:], str(a))
# Existing bibliography supplies citation labels when a section has not used a key yet.
bib = json.loads(subprocess.run(['pandoc','-f','biblatex','-t','csljson',str(sync.LOCAL/'references.bib')],capture_output=True,text=True,check=True).stdout)
for b in bib:
    names=b.get('author',[]);author=names[0].get('family',names[0].get('literal',b['id'])) if names else b['id']
    year=b.get('issued',{}).get('date-parts',[['n.d.']])[0][0]
    citations.setdefault(b['id'],f'<a href="#ref-{b["id"]}">{author} et al., {year}</a>')

EN = blocks('en'); KO = blocks('ko')
sections = copy.deepcopy(original)
for item in sections:
    sid=item['id']
    if sid not in EN: continue
    item['state']='revised'
    for lang,content in [('en',EN),('ko',KO)]:
        item['old'+lang]=item[lang+'html']
        doc=BeautifulSoup(item[lang+'html'],'html.parser')
        figures=''.join(str(f) for f in doc.find_all('figure'))
        item[lang+'html']=(figures if sid=='s1' else '')+html_text(content[sid])+(figures if sid!='s1' else '')

configs={
  1:{'sid':'s2-1','cols':[0,2,3,4,5,7,8,9],
     'en':['Dataset','Review','PoT / exec.','Graph','LLM text','Edits','Auto.','Human'],
     'ko':['데이터셋','원천 검토','PoT / 실행','계산 그래프','LLM 문장','변형','자동 검사','사람 검증'],
     'groups_en':[('Source',1),('Construction',4),('Verification',2)],
     'groups_ko':[('원천',1),('제작',4),('검증',2)],
     'note_en':'Review: source-item checks. PoT/exec.: executable reference calculations. Graph: input–operation–answer dependencies. LLM text: generated questions, contexts, or edits. Edits: controlled changes. Auto./Human: automated checks or human review. Appendix # gives full definitions.',
     'note_ko':'원천 검토: 원본 문항 점검. PoT/실행: 실행 가능한 참조 계산. 계산 그래프: 입력·연산·답의 의존 관계. LLM 문장: 질문·문맥·변경 문장 생성. 변형: 통제된 변경. 자동 검사·사람 검증: 각 검증 방식. 세부 정의는 Appendix #에 둔다.'},
  2:{'sid':'s2-2','cols':[0,1,3,5,4,8,9],
     'en':['Dataset','Numerical QA','Conflict detection','Missing evidence','Abstention','Response support','Paired'],
     'ko':['데이터셋','수치 QA','충돌 탐지','정보 부족','기권','응답 뒷받침','대응 비교'],
     'groups_en':[('Tasks and evidence conditions',3),('Decision evaluation',3)],
     'groups_ko':[('과제·근거 조건',3),('결정 평가',3)],
     'note_en':'Numerical QA: numerical correctness. Conflict detection: contradictions or rule violations. Missing evidence: insufficient information. Abstention: abstaining when conflicting evidence prevents a supported answer. Response support: answer–explanation–evidence consistency. Paired: matched original–variant comparisons. Appendix # gives full definitions.',
     'note_ko':'수치 QA: 수치 정답. 충돌 탐지: 모순·규칙 위반 탐지. 정보 부족: 불충분한 정보 평가. 기권: 충돌로 답을 뒷받침할 수 없을 때의 기권. 응답 뒷받침: 답·설명·근거의 일치. 대응 비교: 연결된 원본·변형 비교. 세부 정의는 Appendix #에 둔다.'}}
matrices={}; full_tables={}
for number,cfg in configs.items():
    old=next(x for x in original if x['id']==cfg['sid'])
    new=next(x for x in sections if x['id']==cfg['sid'])
    full_tables[number]={}
    for lang in ['en','ko']:
        olddoc=BeautifulSoup(old[lang+'html'],'html.parser')
        table=olddoc.find('table');full_tables[number][lang]=str(table)
        rows=[r.find_all(['th','td'],recursive=False) for r in table.find_all('tr')]
        if lang=='en': matrices[number]=[[str(c) for c in row] for row in rows]
        doc=BeautifulSoup('<table class="grouped-comparison"><thead></thead><tbody></tbody></table>','html.parser')
        first=doc.new_tag('tr');cell=doc.new_tag('th',rowspan='2');cell.string=cfg[lang][0];first.append(cell)
        for label,span in cfg['groups_'+lang]:
            cell=doc.new_tag('th',colspan=str(span));cell.string=label;first.append(cell)
        doc.thead.append(first);second=doc.new_tag('tr')
        for label in cfg[lang][1:]:
            cell=doc.new_tag('th');cell.string=label;second.append(cell)
        doc.thead.append(second)
        for row in rows[1:]:
            tr=doc.new_tag('tr')
            for index in cfg['cols']: tr.append(copy.deepcopy(row[index]))
            if 'FInject' in tr.get_text():tr['class']='ours'
            doc.tbody.append(tr)
        title=('Construction and verification features.' if number==1 else 'Evaluation tasks and decisions.') if lang=='en' else ('제작·검증 요소.' if number==1 else '평가 과제와 결정.')
        note=cfg['note_'+lang]
        status=('✓: reported coverage; blank: not established, not proof of absence. FInject checks describe the evaluation or construction design, not completed human verification or measured superiority.' if lang=='en' else '✓는 보고된 범위이며 빈칸은 미확인으로 기능 부재를 뜻하지 않는다. FInject의 체크는 제작·평가 설계이며 사람 검증 완료나 품질 우위를 뜻하지 않는다.')
        new[lang+'html']+=f'<div class="comparison" id="tab:related-{number}"><p class="table-caption">'+('Table ' if lang=='en' else '표 ')+str(number)+'. '+title+'</p>'+str(doc)+'</div><p class="table-note">'+note+'</p><p class="table-note">'+status+'</p>'

def append_section(sid,en,ko,enhtml,kohtml):
    idx=next(i for i,x in enumerate(sections) if x['id']=='s11-comparisons')
    sections.insert(idx,dict(id=sid,en=en,ko=ko,enhtml=enhtml,kohtml=kohtml,state='revised',olden='',oldko='',level=1))

append_section('s11-rubric','Appendix #. Semantic review and model settings','Appendix #. 의미 판정과 모델 설정',html_text(EN['s11-rubric']),html_text(KO['s11-rubric']))
for lang in ['en','ko']:
    # Retain the detailed metric tables without crowding the main exposition.
    tables=''
    for sid,label in [('s5-1','RQ1'),('s5-2','RQ2')]:
        old=next(x for x in original if x['id']==sid)
        tab=BeautifulSoup(old[lang+'html'],'html.parser').find('table')
        tables+='<div class="comparison" id="app-metric-'+sid+'"><p class="table-caption">'+label+(' metric details' if lang=='en' else ' 세부 측정 항목')+'</p>'+str(tab)+'</div>'
    if lang=='en':metrics_en=tables
    else:metrics_ko=tables
append_section('s11-metrics','Appendix #. Metric definitions and analysis dimensions','Appendix #. 지표 정의와 분석 항목',metrics_en,metrics_ko)
for lang in ['en','ko']:
    text='<p>'+('These matrices preserve the full comparison columns from the preceding draft. Checkmarks do not establish matched data quality or completed human verification. Individual coverage claims still require source-level review.' if lang=='en' else '아래 표는 이전 초안의 전체 비교 열을 보존한다. 체크 수로 동일 기준의 품질 우위나 사람 검증 완료를 주장하지 않는다. 개별 비교 근거는 원문 수준에서 확인해야 한다.')+'</p>'
    for number in [1,2]:
        title=('Full construction comparison' if number==1 else 'Full evaluation comparison') if lang=='en' else ('제작 요소 전체 비교' if number==1 else '평가 범위 전체 비교')
        text+='<div class="comparison" id="app-full-table-'+str(number)+'"><p class="table-caption">'+title+'</p>'+full_tables[number][lang]+'</div>'
    if lang=='en':full_en=text
    else:full_ko=text
append_section('s11-full-tables','Appendix #. Full financial dataset comparisons','Appendix #. 금융 데이터셋 전체 비교',full_en,full_ko)

# Explicit pending notes replace misleading unfinished prose, without inventing disclosures.
pending={
 's6':('Author confirmation pending: specify the use of AI in manuscript preparation and distinguish it from the construction models in Section 3.1.','저자 확인 필요: 논문 작성에서의 AI 사용을 구체적으로 기록하고 3.1의 제작 모델과 구분해야 한다.'),
 's7':('Author confirmation pending: describe annotation consent and compensation, applicable data rights, and safeguards for possible misuse. Do not treat this draft as a completed ethics assessment.','저자 확인 필요: 주석 참여 동의·보상, 데이터 사용 권한, 오용 가능성에 대한 조치를 기록해야 한다. 이 초안은 윤리 검토 완료를 뜻하지 않는다.'),
 's9':('Release details pending: confirm final human-verified counts, source licenses, distribution permissions, and the released data fields.','공개 정보 확인 필요: 사람 검증 후 최종 수량, 원천 라이선스, 재배포 권한, 공개 필드를 확정해야 한다.'),
 's10':('Release details pending: document the code location, license, version, and instructions needed to reproduce construction and evaluation.','공개 정보 확인 필요: 코드 위치·라이선스·버전과 제작·평가 재현 방법을 기록해야 한다.')}
for sid,values in pending.items():
    item=next(x for x in sections if x['id']==sid);item['state']='revised'
    for lang,value in zip(['en','ko'],values):
        item['old'+lang]=item[lang+'html'];item[lang+'html']='<p class="pending">['+value+']</p>'
for item in sections:
    for lang in ['en','ko']:
        d=BeautifulSoup(item[lang+'html'],'html.parser')
        fig=d.find(id='fig:abstention-intro')
        if fig:
            fig.figcaption.string=('Figure 1. FInject evaluates whether models answer or abstain appropriately under conflicting evidence and support their decisions with reasons and evidence. Responses are illustrative.' if lang=='en' else 'Figure 1. FInject는 충돌 근거에서 모델이 적절히 답변·기권하고 이유와 근거로 결정을 뒷받침하는지 평가한다. 응답은 설명용 예시다.')
            item[lang+'html']=str(d)

# Synchronize local TeX prose while preserving figure positions and the two main table floats.
main=(BACKUP/'main.tex').read_text()
main=re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}',lambda m:'\\begin{abstract}\n'+tex_text(EN['abstract'])+'\\end{abstract}',main,flags=re.S)
main=main.replace(r'\bibliography{references}',r'\nocite{conflictbank,healthcontradict,whoqa,pinocchio,adversarial_mwp}'+'\n'+r'\bibliography{references}')
main=main.replace(r'\end{abstract}', r'\end{abstract}'+'\n'+r'\suppressfloats[t]')
(sync.LOCAL/'main.tex').write_text(main)
intro=(BACKUP/'01-introduction.tex').read_text();intro=intro[:intro.index('In real-world')]+tex_text(EN['s1'])
intro=intro.replace(r'\begin{figure}[!t]',r'\begin{figure}[t]')
(sync.LOCAL/'sections/01-introduction.tex').write_text(intro)
body=(BACKUP/'revision-20261002-body.tex').read_text()
old_float={i:next(m[0] for m in re.finditer(r'\\begin\{table\*\}.*?\\end\{table\*\}',body,re.S) if f'\\label{{tab:related-{i}}}' in m[0]) for i in [1,2]}
metric_floats=[m[0] for m in re.finditer(r'\\begin\{table\*\}.*?\\end\{table\*\}',body,re.S) if any('\\label{'+label+'}' in m[0] for label in ['tab:layout-6','tab:layout-7'])]

def table_tex(number):
    cfg=configs[number];n=len(cfg['cols']);lines=[]
    lines.append('\\begin{table*}[tp]\n\\centering\\small\n\\setlength{\\tabcolsep}{4pt}\n\\renewcommand{\\arraystretch}{1.15}\n\\begin{tabularx}{\\textwidth}{@{}p{0.24\\textwidth}*{'+str(n-1)+'}{>{\\centering\\arraybackslash}X}@{}}\n\\toprule')
    lines.append(' & '+' & '.join('\\multicolumn{'+str(span)+'}{c}{\\textbf{'+label+'}}' for label,span in cfg['groups_en'])+r' \\')
    col=2
    lines.append(' '.join('\\cmidrule(lr){'+str(start)+'-'+str(end)+'}' for start,end in [(2,2),(3,6),(7,8)] ) if number==1 else r'\cmidrule(lr){2-4}\cmidrule(lr){5-7}')
    lines.append(' & '.join('\\head{'+h.replace(' ','\\\\',1)+'}' if len(h)>10 else '\\textbf{'+h+'}' for h in cfg['en'])+r' \\'+ '\n\\midrule')
    for row in matrices[number][1:]:
        cells=[]
        for i in cfg['cols']:
            d=BeautifulSoup(row[i],'html.parser')
            if d.get_text(strip=True)=='✓':value=r'\(\checkmark\)'
            else:value=convert(str(d),'html','latex').strip()
            cells.append(value)
        if 'FInject' in cells[0]:lines.append(r'\midrule')
        lines.append(' & '.join(cells)+r' \\')
    lines+=['\\bottomrule\n\\end{tabularx}','\\caption{'+('Construction and verification features.' if number==1 else 'Evaluation tasks and decisions.')+'}\\label{tab:related-'+str(number)+'}',r'\begin{minipage}{\textwidth}\footnotesize\raggedright',tex_text(cfg['note_en']),tex_text('✓ indicates reported coverage; blank cells do not establish absence. FInject checks describe design coverage, not completed human verification or measured superiority.').replace('✓',r'\(\checkmark\)'),r'\end{minipage}',r'\end{table*}']
    return '\n'.join(lines)

# Rebuild Related Works from the reviewed prose, retaining a barrier between its two tables.
a=body.index(r'\section{Related Works}');b=body.index(r'\setcounter{section}{2}',a)
related='\\section{Related Works}\n'+table_tex(1)+'\n'+tex_text(EN['s2'])+'\n\\subsection{Dataset Research}\n'+tex_text(EN['s2-1'])+'\n\\FloatBarrier\n'+table_tex(2)+'\n\\subsection{Evaluation Research}\n'+tex_text(EN['s2-2'])+'\n'
body=body[:a]+related+body[b:]
body=body.replace(r'\setcounter{section}{2}', '\\FloatBarrier\n'+r'\setcounter{section}{2}',1)
names={'s3-1':'Overview of FInject','s3-2':'Seed Problems','s3-3':'Perturbation Taxonomy','s3-4':'Dataset Construction','s3-5':'Model Evaluation'}
for sid,title in names.items():
    marker='\\subsection{'+title+'}';a=body.index(marker)+len(marker)
    m=re.search(r'\\(?:subsection\{|setcounter\{(?:subsection|section)\})',body[a:]);b=a+m.start()
    old=body[a:b];figs=''.join(re.findall(r'\\begin\{figure\*?\}.*?\\end\{figure\*?\}',old,re.S))
    body=body[:a]+'\n'+figs+'\n'+tex_text(EN[sid])+'\n'+body[b:]
a=body.index(r'\section{Task and Metrics}');b=body.index(r'\section{AI Usage}',a)
metrics='\\section{Task and Metrics}\n'+tex_text(EN['s5'])+'\n\\subsection{RQ1: Do models appropriately choose between answering and abstaining?}\n'+tex_text(EN['s5-1'])+'\n\\subsection{RQ2: How do model responses change when evidence conflicts or is removed?}\n'+tex_text(EN['s5-2'])+'\n'
body=body[:a]+metrics+body[b:]
tailnames=[('s6','AI Usage'),('s7','Ethical Consideration'),('s8','Limitations'),('s9','Data'),('s10','Software')]
for idx,(sid,title) in enumerate(tailnames):
    a=body.index('\\section{'+title+'}')+len('\\section{'+title+'}');b=body.index('\\section{',a)
    text=tex_text(EN[sid]) if sid in EN else tex_text('['+pending[sid][0]+']')
    body=body[:a]+'\n'+text+'\n'+body[b:]
marker=r'\subsection*{Appendix \#: Supplementary comparisons and definitions}'
extra='\\subsection*{Appendix \\#: Semantic review and model settings}\n'+tex_text(EN['s11-rubric'])
extra+='\n\\subsection*{Appendix \\#: Metric definitions and analysis dimensions}\n'
for t in metric_floats:extra+='\n\\FloatBarrier\n\\clearpage\n'+t+'\n'
extra+='\n\\FloatBarrier\n\\subsection*{Appendix \\#: Full financial dataset comparisons}\nThe following matrices preserve all columns from the preceding draft. They describe coverage, not matched quality or completed human verification.\n'
for i in [1,2]:
    t=old_float[i]
    t=re.sub(r'\\label\{[^}]+\}', '',t)
    t=t.replace('\\caption{','\\caption*{Appendix comparison: ')
    extra+='\n\\FloatBarrier\n\\clearpage\n'+t+'\n'
body=body.replace(marker,extra+'\n\\FloatBarrier\n'+marker)
(sync.LOCAL/'revision-20261002-body.tex').write_text(body)
sections=sync.normalize_sections(sections)
sync.local_sources(sections)
sync.write_review(sections)
(RUN/'applied-sections.json').write_text(json.dumps({'updated_sections':list(EN),'counts_source':str(sync.STATE.relative_to(ROOT)),'overleaf_modified':False,'semantic_rubric':'PROPOSED_NOT_EXECUTED','coverage_checks':'PRESERVED_NOT_REAUDITED'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'sections':len(sections),'prose_blocks_updated':len(EN),'overleaf_modified':False}))
