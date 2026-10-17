"""Apply the approved Section 3 structure to the bilingual review and TeX copy."""
from pathlib import Path
import base64, copy, json, re, shutil, subprocess
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'reports/run/20261003-construction-revision'
REVIEW=ROOT/'reports/run/20261003-paper-revision-draft'
VIS=Path('/Users/wooix/.codex/visualizations/2026/10/02/01a0fb53-72f4-7ca1-9765-8977e7c0b21f')
BASE=RUN/'backup/revision-20261002-body.tex'
def convert(s, source='markdown', target='html'):
    return subprocess.run(['pandoc','-f',source,'-t',target,'--wrap=none','--biblatex'],input=s,text=True,capture_output=True,check=True).stdout

def figure(path, number, label, caption):
    uri='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    return f'<figure id="{label}"><img src="{uri}" alt="{caption}" loading="lazy"><figcaption>Figure {number}. {caption}</figcaption></figure>'

def apply_review(sections):
    baseline=json.loads((RUN/'backup/paper-review.json').read_text())
    old={x['id']:x for x in baseline}
    new=[]
    for lang in ['en','ko']:
        md=(RUN/f'content/construction-{lang}.md').read_text()
        parts=re.split(r'^### (.+)$',md,flags=re.M)
        for i in range(1,len(parts),2):
            n=(i+1)//2
            if lang=='en':
                new.append(dict(id=f's3-{n}',en=parts[i],ko='',enhtml='',kohtml='',state='revised',olden=old[{1:'s3-1',2:'s3-2',3:'s3-2',4:'s3-3',5:'s3-5'}[n]]['enhtml'],oldko=old[{1:'s3-1',2:'s3-2',3:'s3-2',4:'s3-3',5:'s3-5'}[n]]['kohtml'],level=1))
            item=new[n-1];item[lang]=parts[i]
            h=convert(parts[i+1])
            h=re.sub(r'<span class="citation"[^>]*>.*?</span>', '<a href="#ref-finance_reasoning">Tang et al., 2025</a>; <a href="#ref-tatqa">Zhu et al., 2021</a>',h,flags=re.S)
            item[lang+'html']=h
    for lang in ['en','ko']:
        cap=('Dataset Construction prepares and generates evidence variants; Model Evaluation records responses and analyzes answer-or-abstain decisions.' if lang=='en' else 'Dataset Construction prepares the originals and generates the base variations, while Model Evaluation collects the responses and analyzes the responses.')
        new[0][lang+'html']+=figure(ROOT/'paper/asset/pipeline-overview-v3-abstract.png',2,'fig:revision-1',cap)
        cap=('Four categories and seven variants connect conflicting claims and independent evidence deletions to the same original.' if lang=='en' else 'The four-category-seven variation links claims that conflict with the same source to independent base deletions.')
        new[2][lang+'html']+=figure(ROOT/'paper/asset/Figure3-bh.png',3,'fig:revision-2',cap)
    appendix=[]
    head=dict(id='s11-pipeline',en='Appendix #. Framework workflow',ko='Appendix #. Detailed flow of framework',enhtml='',kohtml='',state='revised',olden='',oldko='',level=1)
    for lang in ['en','ko']:
        cap=('The complete FInject workflow: Preparation, Generation, Evaluation, and Analysis.' if lang=='en' else 'The whole flow of FInject that leads to Preparation, Generation, Evaluation, Analysis.')
        head[lang+'html']=figure(ROOT/'paper/asset/pipeline-overview-v3.png',4,'fig:pipeline-full',cap)
    appendix.append(head)
    for num,(name,oldid) in enumerate([('Preparation','s3-3'),('Generation','s3-4'),('Evaluation','s3-5'),('Analysis','s3-6')],1):
        item=dict(id=f's11-pipeline-{num}',en=f'Appendix #.{num} {name}',ko=f'Appendix #.{num} {name}',enhtml='',kohtml='',state='revised',olden='',oldko='',level=1)
        for lang in ['en','ko']:
            d=BeautifulSoup(old[oldid][lang+'html'],'html.parser')
            for f in d.find_all('figure'):
                if 'revision-5' not in f.get('id',''):f.decompose()
                else:
                    c=f.find('figcaption')
                    if c:c.string=re.sub('^(Figure|\uadf8\ub9bc)\\s*6',r'\1 5',c.get_text())
            h=str(d)
            # The former cropped panels are replaced by the complete workflow figure.
            h=re.sub('(Figure|\uadf8\ub9bc)\\s*[478](?!\\d)',r'\1 4',h)
            h=h.replace('fig:revision-3','fig:pipeline-full').replace('fig:revision-4','fig:pipeline-full').replace('fig:revision-6','fig:pipeline-full').replace('fig:revision-7','fig:pipeline-full')
            if num==1:
                h+=('<p>The recorded runs use <code>gpt-5.6-sol</code> with medium reasoning effort for Python solution authoring and <code>gpt-5.6-luna</code> with max reasoning effort for review, text generation, and verification. These settings describe dataset construction, not target-model evaluation.</p>' if lang=='en' else '<p>In the stored build execution, the Python root is used to create the <code>gpt-5.6-sol</code>(reasoning effort: medium), to review, to create, to verify, to test, to test. <code>gpt-5.6-luna</code>(reasoning effort: max) is used to set the data set and distinguish it from the evaluation set of the target model.</p>')
            if num==2 and lang=='ko':
                h+=figure(ROOT/'reports/run/20261003-overleaf-related-works/revised/revision-graph-example.png',5,'fig:revision-5','2017Annual assets 19,201and 2016Annual assets 23,280The original answer to this is:4,079It is. 2017The property of the pig 21,121.1And if you add the sentence that you\'re going to present as a conditioned candidate,2,159The original table and the additional sentence are together so candidate B is not considered the only correct answer. This screen is a production example and maintains an underrated status.')
            if num==2:
                tax=BeautifulSoup(old['s3-2'][lang+'html'],'html.parser')
                for f in tax.find_all('figure'):f.decompose()
                h+=str(tax)
            item[lang+'html']=h
        appendix.append(item)
    out=[]
    for x in sections:
        x=copy.deepcopy(x)
        if x['id'].startswith('s3-'):
            if x['id']=='s3-1':out.extend(new)
            continue
        for key in ['enhtml','kohtml']:
            x[key]=x[key].replace('1,637','1,817').replace('1,080','1,260')
            x[key]=x[key].replace('Figure 6','Figure 5').replace('\uadf8\ub9bc 6','Painting 5')
        if x['id']=='s3':x['state']='revised'
        if x['id']=='s11':
            shell=copy.deepcopy(x);shell['enhtml']='';shell['kohtml']=''
            out.append(shell);out.extend(appendix)
            x['id']='s11-comparisons';x['en']='Appendix #. Supplementary comparisons';x['ko']='Appendix #. Complementary comparison';x['level']=1
        if x['id'].startswith('s11-pipeline') or x['id']=='s11-comparisons':
            # Only retained comparisons are appended below; repeated overlays must not duplicate sections.
            if x['id']!='s11-comparisons':continue
        out.append(x)
    # Use the preserved original section list for future rebuilds; overlays are applied once per build.
    return out

def build_tex():
    dest=RUN/'revised'
    if not dest.exists():shutil.copytree(ROOT/'reports/run/20261003-overleaf-related-works/revised',dest)
    src=BASE.read_text()
    figures=re.findall(r'\\begin\{figure\*?\}.*?\\end\{figure\*?\}',src,re.S)
    getfig=lambda label:next(f for f in figures if '\\label{'+label+'}' in f)
    md=(RUN/'content/construction-en.md').read_text()
    tex=convert(md,target='latex')
    tex=tex.replace('\\subsection{3. Benchmark Construction}', '\\section{Benchmark Construction}')
    tex=re.sub(r'\\subsubsection\{3\.\d (.*?)\}',r'\\subsection{\1}',tex)
    tex=re.sub(r'\\label\{[^}]+\}', '',tex)
    tex=tex.replace('\\autocite','\\citep')
    tex=tex.replace('Figure 2',r'Figure~\ref{fig:revision-1}').replace('Figure 3',r'Figure~\ref{fig:revision-2}')
    # Declare the overview and taxonomy together to preserve their adjacent layout.
    pos=tex.index('FInject turns')
    tex=tex[:pos]+getfig('fig:revision-1')+'\n'+getfig('fig:revision-2')+'\n'+tex[pos:]
    a=src.index('\\setcounter{section}{2}');b=src.index('\\setcounter{section}{3}')
    body=src[:a]+'\\setcounter{section}{2}\n'+tex+'\n'+src[b:]
    details='\\clearpage\n\\twocolumn[{\n\\subsection*{Appendix \\#: Framework workflow}\nThe full workflow in Figure~\\ref{fig:pipeline-full} connects the four stages described below.\\par\n'
    details+=r'''\begin{minipage}{\textwidth}
\centering
\includegraphics[width=\textwidth]{revision-pipeline.png}
\captionsetup{hypcap=false}
\captionof{figure}{The complete FInject workflow connects Preparation and Generation for dataset construction with Evaluation and Analysis for model evaluation.}
\label{fig:pipeline-full}
\end{minipage}
\vspace{1em}
}]
'''
    for num,name in enumerate(['Preparation','Generation','Evaluation','Analysis']):
        start=src.index('\\subsection{'+name+'}')+len('\\subsection{'+name+'}')
        stop=src.index('\\setcounter{',start)
        t=src[start:stop]
        t=re.sub(r'\\begin\{figure\*?\}.*?\\end\{figure\*?\}',lambda m:m[0] if '\\label{fig:revision-5}' in m[0] else '',t,flags=re.S)
        for oldlabel in ['revision-3','revision-4','revision-6','revision-7']:t=t.replace('fig:'+oldlabel,'fig:pipeline-full')
        if name=='Preparation':t+='\nThe recorded construction runs use \\texttt{gpt-5.6-sol} with medium reasoning effort for Python solution authoring and \\texttt{gpt-5.6-luna} with max reasoning effort for review, text generation, and verification. These are construction settings, distinct from target-model evaluation.\n'
        if name=='Generation':
            ta=src.index('\\subsection{Perturbation Taxonomy}')+len('\\subsection{Perturbation Taxonomy}')
            tb=src.index('\\setcounter{subsection}{2}',ta)
            t+='\n'+src[ta:tb]
        if name=='Evaluation':t=t.replace('\\begin{table*}[!t]','\\FloatBarrier\n\\clearpage\n\\begin{table*}[!t]')
        details+=('\n\\FloatBarrier\n' if name=='Generation' else '\n')+'\\subsubsection*{'+name+'}\n'+t
    anchor='\\subsection*{Appendix \\#: Supplementary comparisons and definitions}'
    body=body.replace(anchor,details+'\n\\FloatBarrier\n'+anchor)
    body=body.replace('1,080','1,260')
    (dest/'revision-20261002-body.tex').write_text(body)
    intro=(RUN/'backup/01-introduction.tex').read_text().replace('1,637','1,817')
    (dest/'sections/01-introduction.tex').write_text(intro)
    shutil.copy2(ROOT/'paper/asset/pipeline-overview-v3.png',dest/'revision-pipeline.png')
    (RUN/'content/appendix-pipeline-en.tex').write_text(details)
    return dest

def main(review_only=False):
    sections=apply_review(json.loads((RUN/'backup/paper-review.json').read_text()))
    (REVIEW/'paper-review.json').write_text(json.dumps(sections,ensure_ascii=False,indent=2))
    template=(ROOT/'src/finarch/documentation/templates/research/paper-revision.html').read_text()
    for lang,name in [('en','finject-introduction-redline.html'),('ko','finject-introduction-ko-redline.html')]:
        (VIS/name).write_text(template.replace('__DEFAULT_LANG__',lang).replace('__DOCUMENT_DATA__',json.dumps(sections,ensure_ascii=False).replace('</','<\\/')))
    # Strip embedded image data before Markdown conversion; keep real asset paths.
    assets={'fig:revision-1':'paper/asset/pipeline-overview-v3-abstract.png','fig:revision-2':'paper/asset/Figure3-bh.png','fig:pipeline-full':'paper/asset/pipeline-overview-v3.png','fig:revision-5':'reports/run/20261003-construction-revision/revised/revision-graph-example.png','fig:abstention-intro':'paper/asset/Figure1-bh.png'}
    for lang in ['en','ko']:
        parts=[];app=[]
        for x in sections:
            d=BeautifulSoup(x[lang+'html'],'html.parser')
            for f in d.find_all('figure'):
                im=f.find('img')
                if im and f.get('id') in assets:im['src']=str(ROOT/assets[f['id']])
            md=convert(str(d),source='html',target='gfm')
            part=('### ' if x['level'] else '## ')+x[lang]+'\n\n'+md
            parts.append(part)
            if x['id'].startswith('s11-pipeline'):app.append(part)
        (REVIEW/f'PAPER-{lang.upper()}.md').write_text('\n\n'.join(parts))
        (RUN/f'content/appendix-{lang}.md').write_text('\n\n'.join(app))
    dest=RUN/'revised' if review_only else build_tex()
    print(json.dumps({'section_ids':[x['id'] for x in sections],'tex':str(dest/'revision-20261002-body.tex')},ensure_ascii=False))
if __name__=='__main__':main()
