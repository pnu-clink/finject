"""Apply the reviewed Related Works and column definitions to a saved project."""
from pathlib import Path
import json
import re
import subprocess
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'reports/run/20261003-overleaf-related-works'
DRAFT=ROOT/'reports/run/20261003-paper-revision-draft'
OUT=RUN/'revised'
body=(RUN/'backup/revision-20261002-body.tex').read_text()
notes=json.loads((DRAFT/'content/table-column-notes.json').read_text())
review=json.loads((DRAFT/'paper-review.json').read_text())


def tex(text):
    text=re.sub(r'\[(@[^\]]+)\]',lambda m:r'\citep{'+','.join(x.strip().lstrip('@') for x in m[1].split(';'))+'}',text)
    text=text.replace('→',r'$\rightarrow$').replace('✓',r'$\checkmark$')
    return subprocess.run(['pandoc','-f','markdown+raw_tex','-t','latex','--wrap=none'],input=text,text=True,capture_output=True,check=True).stdout.strip()


def table_from_html(table,caption,label=None):
    rows=[]
    for row in table.find_all('tr'):
        cells=row.find_all(['th','td'],recursive=False)
        vals=[]
        for cell in cells:
            a=cell.find('a');value=cell.get_text(' ',strip=True)
            rendered=tex(value) if value else ''
            if a and a.get('href','').startswith('http'):rendered=r'\href{'+a['href']+'}{'+rendered+'}'
            if cell.name=='th':rendered=r'\textbf{'+rendered+'}'
            if value.startswith('FInject'):rendered=r'\textbf{'+rendered+'}'
            vals.append(rendered)
        if label and cells[0].get_text(' ', strip=True).startswith('FInject'):
            rows.append(r'\midrule')
        rows.append(' & '.join(vals)+r' \\')
    n=len(table.find('tr').find_all(['th','td'],recursive=False))-1
    cap=(r'\caption{'+caption+'}\n'+r'\label{'+label+'}') if label else r'\par\smallskip\noindent\textbf{'+caption+'}'
    return '\n'.join([r'\begin{table*}[tp]',r'\centering',r'\small',r'\setlength{\tabcolsep}{3pt}',r'\renewcommand{\arraystretch}{1.15}',r'\begin{tabularx}{\textwidth}{@{}p{0.24\textwidth}*{'+str(n)+r'}{>{\centering\arraybackslash}X}@{}}',r'\toprule',rows[0],r'\midrule',*rows[1:],r'\bottomrule',r'\end{tabularx}',cap])


def numbered_table(num):
    item=next(x for x in review if x['id']==f's2-{num}')
    table=BeautifulSoup(item['enhtml'],'html.parser').find('table')
    caption=['Construction and quality assurance features of financial datasets.','Evaluation scope of financial datasets.'][num-1]
    value=table_from_html(table,caption,f'tab:related-{num}')
    paragraphs=[]
    for start in range(0,len(notes[str(num)]),4):
        paragraphs.append('; '.join('**'+x['en']+'**: '+x['brief_en'] for x in notes[str(num)][start:start+4])+'.')
    value+='\n'+r'\begin{minipage}{\textwidth}\footnotesize\raggedright'+'\n'+tex('\n\n'.join(paragraphs))
    value+='\n\n'+tex('Detailed definitions and comparison criteria are provided in Appendix #. ✓ indicates an identified feature; blank cells do not establish its absence. The FInject row describes design coverage.')
    value+='\n'+r'\end{minipage}'+'\n'+r'\end{table*}'+'\n'
    return value


md=(DRAFT/'content/related-en.md').read_text()
parts=re.split(r'^### 2\.[12] .*\n',md,flags=re.M)
intro=re.sub(r'^## 2\. Related Works\s*','',parts[0])
dataset=parts[1]
dataset=re.sub(r'<small>(.*?)</small>',lambda m:'\\begin{small}\n'+m[1].replace('#',r'\#')+'\n\\end{small}',dataset,flags=re.S)
related='\n'.join([r'\section{Related Works}',numbered_table(1),tex(intro),r'\setcounter{subsection}{0}',r'\subsection{Dataset Research}',tex(dataset),
                     '% Flush Table 1 before Table 2 is introduced: one comparison table per page.',r'\FloatBarrier',numbered_table(2),r'\subsection{Evaluation Research}',tex(parts[2]),r'\FloatBarrier',''])
start=body.index(r'\section{Related Works}')
end=body.index(r'\setcounter{section}{2}',start)
body=body[:start]+related+'\n'+body[end:]

# Appendix material already present in the bilingual review draft.
app=next(x for x in review if x['id']=='s11')
tables=BeautifulSoup(app['enhtml'],'html.parser').find_all('table')
appendix=[r'\subsection*{Appendix \#: Supplementary comparisons and definitions}',
          tex('Appendix and supplementary table numbers are provisional. The comparison definitions below accompany Tables 1 and 2.')]
for i,table in enumerate(tables):
    caption='Table N'+('+1' if i else '')+'. '+['Construction features of non-financial datasets.','Evaluation scope of non-financial datasets.'][i]
    appendix.extend([r'\FloatBarrier',table_from_html(table,caption),r'\end{table*}',r'\FloatBarrier'])
appendix.append(r'\subsection*{Definitions and comparison criteria for Tables 1--2}')
for num,entries in notes.items():
    appendix.append(r'\subsubsection*{Table '+num+'}')
    for entry in entries:appendix.append(tex('**'+entry['en']+'.** '+entry['detail_en']))
appendix.append(r'\FloatBarrier')
body+='\n'+'\n\n'.join(appendix)+'\n'
# Separate adjacent tables in later sections as well as the two main comparisons.
index=0
def separate(match):
    global index
    index+=1
    prefix='\\clearpage\n' if index in [5,6,7,8,9] else ''
    return prefix+match[0]
body=re.sub(r'\\begin\{table\*\}',separate,body)
index=0
def page_label(match):
    global index
    index+=1
    return '\\label{tab:layout-'+str(index)+'}\n'+match[0]
body=re.sub(r'\\end\{table\*\}',page_label,body)
# Give the narrow headers enough space without reducing their font size.
body=body.replace(r'@{}p{0.24\textwidth}*{10}',r'@{}p{0.21\textwidth}*{10}')
body=body.replace('revision-taxonomy.pdf','Figure3-bh.png').replace('Orange panels add conflicting claims; the purple panel removes input evidence.', 'Conflict panels add conflicting claims; the absence panel removes input evidence.')
(OUT/'revision-20261002-body.tex').write_text(body)
(RUN/'related-works.tex').write_text(related)
(RUN/'appendix-comparison-definitions.tex').write_text('\n\n'.join(appendix)+'\n')
print('Prepared Related Works, two separated comparison tables, and existing review appendix content.')
