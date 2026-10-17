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
     'ko':['The data set','Source reviews','PoT / run','Calculation graph','LLM phrases','Variant','Automated testing','Human verification.'],
     'groups_en':[('Source',1),('Construction',4),('Verification',2)],
     'groups_ko':[('The source.',1),('Production',4),('Validation',2)],
     'note_en':'Review: source-item checks. PoT/exec.: executable reference calculations. Graph: input–operation–answer dependencies. LLM text: generated questions, contexts, or edits. Edits: controlled changes. Auto./Human: automated checks or human review. Appendix # gives full definitions.',
     'note_ko':'Source review: original case checking. PoT/practice: executable reference calculation. Calculation graph: input; mixing; dependent relationship of answers. LLM phrase: question; context; change phrase creation. modification: controlled change. automatic check; person verification: each verification method. Detailed definition is set out in Appendix #.'},
  2:{'sid':'s2-2','cols':[0,1,3,5,4,8,9],
     'en':['Dataset','Numerical QA','Conflict detection','Missing evidence','Abstention','Response support','Paired'],
     'ko':['The data set','Number QA','The impact detector.','Lack of information','Abstention','Respond back up','Compare the correspondence'],
     'groups_en':[('Tasks and evidence conditions',3),('Decision evaluation',3)],
     'groups_ko':[('The task and the conditions',3),('The decision evaluation',3)],
     'note_en':'Numerical QA: numerical correctness. Conflict detection: contradictions or rule violations. Missing evidence: insufficient information. Abstention: abstaining when conflicting evidence prevents a supported answer. Response support: answer–explanation–evidence consistency. Paired: matched original–variant comparisons. Appendix # gives full definitions.',
     'note_ko':'Numerical QA: Numerical accuracy. Conflict detection: contradiction; rule violation detection. Information shortage: inadequate information assessment. Authority: Authority when no response can be backed up by a collision. Response backing: response; explanation; proximity matching. Corresponding comparison: linked source; variable comparison. Detailed definition is in Appendix #.'}}
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
        title=('Construction and verification features.' if number==1 else 'Evaluation tasks and decisions.') if lang=='en' else ('The manufacturing and verification element.' if number==1 else 'Assessment tasks and decisions.')
        note=cfg['note_'+lang]
        status=('✓: reported coverage; blank: not established, not proof of absence. FInject checks describe the evaluation or construction design, not completed human verification or measured superiority.' if lang=='en' else 'A check mark indicates reported scope; a blank means unverified, not an absent feature. FInject check marks describe its construction/evaluation design, not completed human validation or superior quality.')
        new[lang+'html']+=f'<div class="comparison" id="tab:related-{number}"><p class="table-caption">'+('Table ' if lang=='en' else 'Table ')+str(number)+'. '+title+'</p>'+str(doc)+'</div><p class="table-note">'+note+'</p><p class="table-note">'+status+'</p>'

def append_section(sid,en,ko,enhtml,kohtml):
    idx=next(i for i,x in enumerate(sections) if x['id']=='s11-comparisons')
    sections.insert(idx,dict(id=sid,en=en,ko=ko,enhtml=enhtml,kohtml=kohtml,state='revised',olden='',oldko='',level=1))

append_section('s11-rubric','Appendix #. Semantic review and model settings','Appendix #. Semantic assessment and model setting',html_text(EN['s11-rubric']),html_text(KO['s11-rubric']))
for lang in ['en','ko']:
    # Retain the detailed metric tables without crowding the main exposition.
    tables=''
    for sid,label in [('s5-1','RQ1'),('s5-2','RQ2')]:
        old=next(x for x in original if x['id']==sid)
        tab=BeautifulSoup(old[lang+'html'],'html.parser').find('table')
        tables+='<div class="comparison" id="app-metric-'+sid+'"><p class="table-caption">'+label+(' metric details' if lang=='en' else ' Detailed measurement items')+'</p>'+str(tab)+'</div>'
    if lang=='en':metrics_en=tables
    else:metrics_ko=tables
append_section('s11-metrics','Appendix #. Metric definitions and analysis dimensions','Appendix #. Indicator definition and analysis items',metrics_en,metrics_ko)
for lang in ['en','ko']:
    text='<p>'+('These matrices preserve the full comparison columns from the preceding draft. Checkmarks do not establish matched data quality or completed human verification. Individual coverage claims still require source-level review.' if lang=='en' else 'The table below preserves the entire comparison column of the previous draft. Check figures do not claim the same standard of quality excellence or human verification completion. Individual comparison bases should be verified at the original level.')+'</p>'
    for number in [1,2]:
        title=('Full construction comparison' if number==1 else 'Full evaluation comparison') if lang=='en' else ('Comparison of the total manufacturing elements' if number==1 else 'Comparison of the total scope of evaluation')
        text+='<div class="comparison" id="app-full-table-'+str(number)+'"><p class="table-caption">'+title+'</p>'+full_tables[number][lang]+'</div>'
    if lang=='en':full_en=text
    else:full_ko=text
append_section('s11-full-tables','Appendix #. Full financial dataset comparisons','Appendix #. Comparison of the financial data set as a whole',full_en,full_ko)

# Explicit pending notes replace misleading unfinished prose, without inventing disclosures.
pending={
 's6':('Author confirmation pending: specify the use of AI in manuscript preparation and distinguish it from the construction models in Section 3.1.','Author verification: specifically documenting the use of AI in writing articles, 3.1It\'s a different model than the production model.'),
 's7':('Author confirmation pending: describe annotation consent and compensation, applicable data rights, and safeguards for possible misuse. Do not treat this draft as a completed ethics assessment.','Author verification: The key participant must record the consent/confirmation, data usage permissions, and misuse possibilities. This draft does not imply completion of ethical review.'),
 's9':('Release details pending: confirm final human-verified counts, source licenses, distribution permissions, and the released data fields.','Public information verification is required: After verification of the person, the final quantity, source license, redistribution authorization, and public field must be confirmed.'),
 's10':('Release details pending: document the code location, license, version, and instructions needed to reproduce construction and evaluation.','Public information needs to be verified: code location, license version and production and evaluation reproduction methods must be recorded.')}
for sid,values in pending.items():
    item=next(x for x in sections if x['id']==sid);item['state']='revised'
    for lang,value in zip(['en','ko'],values):
        item['old'+lang]=item[lang+'html'];item[lang+'html']='<p class="pending">['+value+']</p>'
for item in sections:
    for lang in ['en','ko']:
        d=BeautifulSoup(item[lang+'html'],'html.parser')
        fig=d.find(id='fig:abstention-intro')
        if fig:
            fig.figcaption.string=('Figure 1. FInject evaluates whether models answer or abstain appropriately under conflicting evidence and support their decisions with reasons and evidence. Responses are illustrative.' if lang=='en' else 'Figure 1.FInject evaluates whether the model responds appropriately, authorizes, and supports a decision based on reason and reason.')
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
