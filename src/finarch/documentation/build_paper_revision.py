"""Build synchronized Korean/English review copies from saved manuscript sources."""
from pathlib import Path
import base64
import copy
import datetime
import hashlib
import html
import json
import re
import subprocess
from functools import lru_cache

from bs4 import BeautifulSoup
import fitz

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'reports/run/20261003-paper-revision-draft'
SRC = ROOT / 'reports/run/20261003-overleaf-introduction/evidence/final-source'
VIS = Path('/Users/wooix/.codex/visualizations/2026/10/02/01a0fb53-72f4-7ca1-9765-8977e7c0b21f')
OLD = ROOT / 'reports/run/20261002-abstention-paper-draft/PAPER-KO.md'


def pandoc(text, fmt):
    result = subprocess.run(['pandoc', '-f', fmt, '-t', 'html5', '--wrap=none'],
                            input=text, text=True, capture_output=True, check=True, cwd=SRC)
    return result.stdout


def soup(text):
    return BeautifulSoup(text, 'html.parser')


def split_sections(text, top, sub):
    result = []
    for node in soup(text).contents:
        if getattr(node, 'name', None) in [top, sub]:
            result.append({'title': node.get_text(' ', strip=True), 'level': 0 if node.name == top else 1, 'html': ''})
        elif result:
            result[-1]['html'] += str(node)
    return result


bib_json = subprocess.run(['pandoc', '-f', 'biblatex', '-t', 'csljson', str(SRC/'references.bib')],
                          text=True, capture_output=True, check=True)
BIB = {x['id']: x for x in json.loads(bib_json.stdout)}


def citation(keys):
    labels = []
    for key in keys:
        b = BIB[key]
        names = b.get('author', [])
        lead = names[0].get('family', names[0].get('literal', key)) if names else key
        suffix = ' et al.' if len(names) > 2 else (' & '+names[1]['family'] if len(names) == 2 else '')
        year = b.get('issued', {}).get('date-parts', [['n.d.']])[0][0]
        labels.append(f'<a href="#ref-{key}">{html.escape(str(lead+suffix))}, {year}</a>')
    return '(' + '; '.join(labels) + ')'


def resolve_citations(text):
    doc = soup(text)
    for c in doc.select('[data-cites]'):
        c.replace_with(soup(citation(c['data-cites'].split())))
    return str(doc)


@lru_cache(maxsize=32)
def image_uri(path):
    if path.name == 'Figure1.png':
        path = ROOT / 'paper/asset/Figure1-bh.png'
    if path.name == 'revision-overview.png':
        path = ROOT / 'paper/asset/pipeline-overview-v3-abstract.png'
    if path.name == 'revision-taxonomy.pdf':
        path = ROOT / 'paper/asset/Figure3-bh.png'
    path = path.resolve()
    if path.suffix == '.pdf':
        document = fitz.open(path)
        data = document[0].get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes('png')
        mime = 'image/png'
    else:
        data = path.read_bytes()
        mime = {'.png':'image/png', '.svg':'image/svg+xml', '.jpg':'image/jpeg'}[path.suffix]
    return f'data:{mime};base64,' + base64.b64encode(data).decode()


def prepare_html(text, base=SRC):
    text = text.replace('Orange panels add conflicting claims; the purple panel removes input evidence.', 'Conflict panels add conflicting claims; the absence panel removes input evidence.')
    text = text.replace('주황색 패널은 충돌하는 주장을 추가하고, 보라색 패널은 입력 근거를 삭제합니다.', '충돌 패널은 충돌하는 주장을 추가하고, 부재 패널은 입력 근거를 삭제합니다.')
    doc = soup(resolve_citations(text))
    for embedded in doc.find_all('embed'):
        im=doc.new_tag('img',src=embedded['src'],alt='Perturbation taxonomy')
        embedded.replace_with(im)
    for im in doc.find_all('img'):
        if not im.get('src', '').startswith('data:'):
            im['src'] = image_uri(base / im['src'])
        im.attrs.pop('style', None)
        im.attrs.pop('width', None)
        im.attrs.pop('height', None)
        im['loading'] = 'lazy'
    for tab in doc.find_all('table'):
        wrap = doc.new_tag('div', attrs={'class':'table-scroll', 'tabindex':'0'})
        tab.wrap(wrap)
        for row in tab.select('tr'):
            if 'FInject' in row.get_text() or 'Ours (design)' in row.get_text(): row['class'] = 'ours'
    return str(doc)


def clean_intro(lang):
    fn = 'finject-introduction-redline.html' if lang == 'en' else 'finject-introduction-ko-redline.html'
    doc = soup((RUN/'backup'/fn).read_text()).article
    for tag in doc.find_all('del'): tag.decompose()
    for tag in doc.find_all('ins'): tag.unwrap()
    for p in doc.find_all('p'):
        if not p.get_text(strip=True): p.decompose()
    return doc.decode_contents()


body = (SRC/'revision-20261002-body.tex').read_text()
body = body.replace(r'\input{sections/01-introduction}', '')
en_parts = split_sections(pandoc(body, 'latex'), 'h1', 'h2')
ko_parts = split_sections(pandoc(OLD.read_text(), 'markdown'), 'h2', 'h3')
by_ko = {re.match(r'[\d.]+', x['title']).group().rstrip('.'): x for x in ko_parts}

# Match the eight current PDF figures, including the newly inserted introduction.
figure_numbers = {'fig:abstention-intro': 1, **{f'fig:revision-{i}': i+1 for i in range(1, 8)}}
figures = {}
for part in en_parts:
    doc = soup(part['html'])
    for f in doc.find_all('figure'):
        n = figure_numbers[f['id']]
        panels={4:'figure-2-preparation.svg',5:'figure-3-generation.svg',7:'figure-5-evaluation.svg',8:'figure-6-analysis.svg'}
        if n in panels: f.img['src']=str(OLD.parent/'figures'/panels[n])
        f.figcaption.insert(0, f'Figure {n}. ')
        figures[n] = str(f)
        f.decompose()
    for a in doc.select('[data-reference]'):
        if a['data-reference'] in figure_numbers: a.string = str(figure_numbers[a['data-reference']])
    part['html'] = str(doc)

abstract_en = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', (SRC/'main.tex').read_text(), re.S).group(1).strip()
abstract_ko = '''금융 에이전트의 근거 없는 답변은 큰 손실로 이어질 수 있으므로, 계산 능력 외에 언제 답변하지 않아야 하는지 판단하는 능력이 중요하다. 최근 벤치마크는 에이전트의 의사결정 과정을 평가하는 방향으로 확장되고 있으며, 이에 따라 추론 과정과 답변·기권 선택을 함께 살펴볼 필요가 커지고 있다. 그러나 수치 정답 여부만으로는 금융 근거가 충돌하거나 불완전할 때 이러한 판단이 적절한지 확인하기 어렵다. 우리는 금융 수치 추론에서 적절한 기권에 초점을 둔 벤치마크 FInject를 제안한다. FInject는 실행 가능한 풀이와 계산 그래프를 이용해 참조 풀이 경로에 필요한 근거를 찾고, 정보 충돌을 추가하거나 필요한 근거를 제거하는 일곱 가지 통제된 변형을 구성한다. 우리는 모델이 답변과 기권을 적절히 선택하는지, 그리고 충돌·제거 조건에 따라 그 판단이 어떻게 달라지는지 평가한다. 판단 기준 안내와 reasoning 지시를 조합한 네 조건에서 답변, 설명, 인용 근거를 비교하여 정당한 기권과 단순히 더 자주 거부하는 행동을 구분한다. FInject는 수치 정답 여부를 넘어, 금융 에이전트가 근거가 충분할 때 답하고 확정적인 답을 뒷받침하지 못할 때 기권하는지를 평가한다. FInject는 데이터셋 제작·평가·분석을 위한 자동화된 프레임워크와 재사용 가능한 데이터셋을 제공한다.'''
caption_en = 'FInject evaluates answer-or-abstain decisions under conflicting or insufficient financial evidence through classification, reasons, and cited evidence.'
caption_ko = 'FInject는 금융 근거가 충돌하거나 부족할 때의 답변·기권 판단을 분류, 이유, 인용 근거와 함께 평가한다.'

sections = []
def add(sid, en, ko, enhtml, kohtml, state, olden='', oldko='', level=0):
    sections.append(dict(id=sid, en=en, ko=ko, enhtml=enhtml, kohtml=kohtml, state=state, olden=olden, oldko=oldko, level=level))

add('abstract','Abstract','Abstract',f'<p>{html.escape(abstract_en)}</p>',f'<p>{abstract_ko}</p>','settled')
intro_fig = '<figure id="fig:abstention-intro"><img src="Figure1.png" alt="Figure 1: answer-or-abstain decisions"/><figcaption>Figure 1. {}</figcaption></figure>'
add('s1','1. Introduction','1. Introduction',intro_fig.format(caption_en)+clean_intro('en'),intro_fig.format(caption_ko)+clean_intro('ko'),'settled')

new_en = split_sections(pandoc((RUN/'content/related-en.md').read_text(),'markdown'), 'h2','h3')
new_ko = split_sections(pandoc((RUN/'content/related-ko.md').read_text(),'markdown'), 'h2','h3')
old_en = en_parts[:3]
old_ko = [by_ko[x] for x in ['2','2.2','2.3']]
column_notes = json.loads((RUN/'content/table-column-notes.json').read_text())


def brief_column_notes(number, lang):
    entries=column_notes[str(number)]
    result=''
    for start in range(0,len(entries),4):
        definitions=[f'<strong>{html.escape(x[lang])}</strong>: {html.escape(x["brief_"+lang])}' for x in entries[start:start+4]]
        result+='<p class="table-note column-definitions">'+'; '.join(definitions)+'.</p>'
    label='Detailed definitions and comparison criteria are provided in ' if lang=='en' else '세부 정의와 비교 판정 기준은 '
    suffix='.' if lang=='en' else '을 참조한다.'
    return result+'<p class="table-note">'+label+'<a href="#appendix-table-definitions">Appendix #</a>'+suffix+'</p>'

# Keep both comparison matrices and their definitions from the current manuscript.
tables = []
for p in old_en:
    doc = soup(p['html'])
    for table in doc.find_all('table'):
        tables.append(str(table))
        table.decompose()
    p['html'] = str(doc)
ko_tables = []
for p in old_ko:
    doc = soup(p['html'])
    for table in doc.find_all('table'):
        ko_tables.append(str(table)); table.decompose()
    p['html'] = str(doc)
# Use the abstention-centered label for the financial comparison only.
for collection, lang in [(tables,'en'),(ko_tables,'ko')]:
    doc=soup(collection[1])
    for th in doc.find_all('th'):
        if th.get_text(' ',strip=True) in ['Confl. QA','Conflict QA']:
            th.clear();th.append('Abst. under conflicts' if lang=='en' else '충돌 상황 기권')
    collection[1]=str(doc)
# Keep the main comparison row label concise in both languages.
for collection in [tables, ko_tables]:
    for index in range(2):
        doc = soup(collection[index])
        for row in doc.find_all('tr'):
            cell = row.find(['th', 'td'])
            if cell and cell.get_text(' ', strip=True).startswith('FInject'):
                cell.clear(); cell.append('FInject')
        collection[index] = str(doc)
for i, sid in enumerate(['s2','s2-1','s2-2']):
    en = new_en[i]['html']; ko = new_ko[i]['html']
    if i:
        tab_id = f'table-{i}'
        title_en = ['','Construction and quality assurance features of financial datasets.','Evaluation scope of financial datasets.'][i]
        title_ko = ['','금융 데이터셋의 제작 및 품질 확인 요소.','금융 데이터셋의 평가 범위.'][i]
        en += f'<div id="{tab_id}" class="comparison"><p class="table-caption">Table {i}. {title_en}</p>'+tables[i-1]+'</div>'
        ko += f'<div id="{tab_id}" class="comparison"><p class="table-caption">표 {i}. {title_ko}</p>'+ko_tables[i-1]+'</div>'
        en += brief_column_notes(i,'en')
        ko += brief_column_notes(i,'ko')
        en += '<p class="table-note">✓: identified under the table definitions; blank: not established under those definitions, not proof of absence. The FInject row records design coverage. PoT / execution includes executable reference calculations; a checkmark does not necessarily mean PoT prompting. The calculation graph describes construction dependencies, not hidden model reasoning.</p>' if i == 1 else '<p class="table-note">✓ and blanks follow Table 1. Evaluation coverage does not imply identical correctness criteria or denominators. The FInject row records the evaluation design; input recovery and semantic consistency require corresponding reference judgments.</p>'
        ko += '<p class="table-note">✓는 표의 정의에 해당하는 사용을 확인한 경우이며, 빈칸은 해당 사용을 확인하지 못했다는 뜻으로 기능 부재를 증명하지 않습니다. FInject 행은 설계 범위입니다. PoT·풀이 실행의 ✓가 모두 PoT 프롬프팅을 뜻하지는 않습니다. 계산 그래프는 제작 과정의 의존 관계이며 모델 내부 추론이 아닙니다.</p>' if i == 1 else '<p class="table-note">✓와 빈칸의 의미는 표 1과 같습니다. 같은 열의 ✓가 동일한 정답 기준이나 분모를 뜻하지는 않습니다. FInject 행은 평가 설계이며, 역산 평가와 의미 정합성은 필요한 판정 근거가 있는 범위에 적용합니다.</p>'
    add(sid,new_en[i]['title'],new_ko[i]['title'],en,ko,'revised',old_en[i]['html'],old_ko[i]['html'],0 if i==0 else 1)

sec=2; sub=0
figure_at = {'3.1':[2], '3.2':[3], '3.3':[4], '3.4':[5,6], '3.5':[7], '3.6':[8]}
ko_titles={'6':'AI Usage','7':'Ethical Consideration','8':'Limitations','9':'Data','10':'Software','11':'Appendices'}
ko_tail={'6':'<p class="pending">[미작성 — PDF 원고에 본문이 없습니다.]</p>','7':'<p>우리는 잘하고 있다.</p><p class="pending">[기존 원고의 “We are good” 임시 문구입니다. 작성 필요.]</p>','8':'<p>우리 연구는…</p><p class="pending">[기존 원고의 “Our work is..” 임시 문구입니다. 작성 필요.]</p>','9':'<p class="pending">[미작성 — PDF 원고에 본문이 없습니다.]</p>','10':'<p class="pending">[미작성 — PDF 원고에 본문이 없습니다.]</p>','11':'<p class="pending">[PDF의 부록 본문은 미작성입니다. 아래 비교표는 프로젝트에 보관된 비금융 비교 자료를 검토용으로 가져왔으며, 최종 부록·표 번호는 미정입니다.]</p>'}
for part in en_parts[3:]:
    if part['level']==0: sec+=1;sub=0
    else: sub+=1
    num = str(sec)+(f'.{sub}' if sub else '')
    en = part['html']; ko_item=by_ko.get(num)
    ko = ko_item['html'] if ko_item else ko_tail[num]
    if sec>=6 and not soup(en).get_text(strip=True): en='<p class="pending">[Not yet written in the current PDF manuscript.]</p>'
    if num=='11': en='<p class="pending">[The PDF appendix is not yet written. The non-financial comparison tables below are imported from existing project material for review; final numbering remains pending.]</p>'
    for n in figure_at.get(num,[]): en += figures[n]
    # Korean sections use existing translations; update figure numbering to the current PDF.
    ko = re.sub(r'(그림|Figure) ([1-7])(?!\d)',lambda m:m[1]+' '+str(int(m[2])+1),ko)
    # Do not renumber the reference to the earlier manuscript's Figure 3.
    ko = ko.replace('기존 FInject 원고의 Figure 4','기존 FInject 원고의 Figure 3')
    kd=soup(ko)
    for image in list(kd.find_all('img')):
        original=image['src']
        if 'pipeline-overview-v3-abstract' in original: image['src']=str(SRC/'revision-overview.png')
        elif 'perturbation-taxonomy' in original: image['src']=str(SRC/'revision-taxonomy.pdf')
        elif 'graph-perturbation' in original: image['src']=str(SRC/'revision-graph-example.png')
        # Taxonomy appears in 3.1 in the old Korean draft; move it to its logical section below.
        parent=image.parent
        if parent.name=='p':
            caption_node=parent.find_next_sibling('p')
            fig=kd.new_tag('figure')
            match=re.search(r'(?:그림|Figure) (\d+)',image.get('alt',''))
            if match: fig['id']='fig:revision-'+str(int(match[1])-1)
            parent.replace_with(fig);fig.append(image)
            caption=kd.new_tag('figcaption')
            if caption_node and re.match(r'(?:그림|Figure) \d+',caption_node.get_text()):
                caption.string=caption_node.get_text();caption_node.decompose()
            else:caption.string=image.get('alt','')
            fig.append(caption)
    ko=str(kd)
    add('s'+num.replace('.','-'),num+'. '+part['title'] if not sub else num+' '+part['title'],
        ko_item['title'] if ko_item else num+'. '+ko_titles[num],en,ko,'carried',level=part['level'])

# Put the Korean taxonomy figure alongside its English counterpart.
overview_ko=next(x for x in sections if x['id']=='s3-1')
taxonomy_ko=next(x for x in sections if x['id']=='s3-2')
doc=soup(overview_ko['kohtml']); f=doc.find(id='fig:revision-2')
if f:
    taxonomy_ko['kohtml']+=str(f)
    f.decompose();overview_ko['kohtml']=str(doc)

# Ensure the Korean taxonomy panel uses the same reviewed figure as English.
taxonomy_ko = next(x for x in sections if x['id']=='s3-2')
if not soup(taxonomy_ko['kohtml']).find('figure'):
    figure_doc = soup(figures[3])
    figure_doc.find('figcaption').string = '그림 3. 부채비율 문제를 예로 든 네 범주와 일곱 변형. 충돌 패널은 충돌하는 주장을 추가하고, 부재 패널은 입력 근거를 삭제합니다. 각 IC-source 변형은 대응하는 부모 IC-value 문항과 비교합니다. 이 예시는 변형 유형을 설명하며, 평가가 완료된 벤치마크 문항을 뜻하지 않습니다.'
    figure_doc.find(['img', 'embed'])['src'] = str(ROOT/'paper/asset/Figure3-bh.png')
    taxonomy_ko['kohtml'] += str(figure_doc)

# Import non-financial matrices as explicitly marked appendix material, not finished new research.
appendix=next(x for x in sections if x['id']=='s11')
for i,filename in enumerate(['nonfinancial-construction.tex','nonfinancial-evaluation.tex']):
    raw=(SRC/'tables'/filename).read_text().replace(r'\covered',r'\(\checkmark\)')
    raw=re.sub(r'\\head\{(.*?)\}',lambda m:m[1].replace('\\\\',' '),raw)
    rows=[]
    for line in raw.splitlines():
        if '&' not in line or 'AbstentionBench' in line:continue
        cells=[]
        for cell in line.rstrip().removesuffix(r'\\').split('&'):
            cell=cell.replace(r'\(\checkmark\)','✓')
            cell=re.sub(r'\\textbf\{([^}]+)\}',r'\1',cell)
            cells.append(html.escape(cell.strip()))
        ids={'ContraDoc':'contradoc','ConflictBank':'conflictbank','WikiContradict':'wikicontradict','MAGIC':'magic','HealthContradict':'healthcontradict','QACC':'qacc','WhoQA':'whoqa','Pinocchio':'pinocchio','Adversarial MWP':'adversarial_mwp'}
        if cells[0] in ids:
            entry=BIB[ids[cells[0]]];year=entry['issued']['date-parts'][0][0]
            cells[0]=f'<a href="{html.escape(entry.get("URL", ""))}">{cells[0]} ({year})</a>'
        elif cells[0]=='Ours (design)':cells[0]='FInject (2026; design)'
        tag='th' if not rows else 'td'
        rows.append('<tr>'+''.join(f'<{tag}>{c}</{tag}>' for c in cells)+'</tr>')
    title=['Construction features of non-financial datasets','Evaluation scope of non-financial datasets'][i]
    table='<table>'+''.join(rows)+'</table>'
    fragment=f'<div id="appendix-table-{i}"><h3>Table N{"+1" if i else ""}. {title}</h3>{table}</div>'
    appendix['enhtml']+=fragment
    korean_fragment=fragment.replace(title,['비금융 데이터셋의 제작 요소','비금융 데이터셋의 평가 범위'][i])
    columns={'Dataset':'데이터셋','Reuse':'기존 자료','Source check':'원천 검토','LLM':'LLM 생성','Rules':'규칙·구조','Run':'풀이 실행','Edit':'원본 변형','Auto':'자동 검사','Human':'사람 검토','Tools':'검토 지원','Calc.':'수치 풀이','Fact':'사실 판정','Find':'충돌 탐지','Conflict QA':'Conflict QA','Need':'근거 부족','Abst.':'기권 지표','Inv.':'역산 평가','Align':'설명 일치','Pair':'짝 비교','Setup':'풀이 설정'}
    for a,b in columns.items():korean_fragment=korean_fragment.replace('<th>'+a+'</th>','<th>'+b+'</th>')
    appendix['kohtml']+=korean_fragment

for lang in ['en','ko']:
    heading='Appendix #. Definitions and comparison criteria for Tables 1–2' if lang=='en' else 'Appendix #. 표 1·2의 항목 정의와 비교 판정 기준'
    detail=f'<div id="appendix-table-definitions"><h3>{heading}</h3>'
    for number,entries in column_notes.items():
        detail+=f'<h4>{"Table" if lang=="en" else "표"} {number}</h4><dl>'
        for entry in entries:
            detail+=f'<dt><strong>{html.escape(entry[lang])}</strong></dt><dd>{html.escape(entry["detail_"+lang])}</dd>'
        detail+='</dl>'
    appendix[lang+'html']+=detail+'</div>'

# Use the same sixteen bibliography entries printed by the compiled manuscript.
bbl=(ROOT/'reports/run/20261003-overleaf-introduction/revised/main.bbl').read_text()
matches=list(re.finditer(r'\\bibitem\[.*?\]\{([^}]+)\}',bbl,re.S))
references=[]
for i,m in enumerate(matches):
    content=bbl[m.end():matches[i+1].start() if i+1<len(matches) else bbl.index(r'\end{thebibliography}')]
    content=content.replace(r'\newblock',' ')
    content=re.sub(r'\\href\s+',r'\\href ',content)
    references.append(f'<div class="reference" id="ref-{m[1]}">{pandoc(content,"latex")}</div>')
refs=''.join(references)
add('references','References','References',refs,refs,'carried')

# Provide index targets for the captioned and unnumbered tables printed by the PDF.
table_labels={'s3-5':[('Evaluation conditions','평가 조건')], 's4':[('Release sampling stages','공개 표본 선정 단계'),('Table 3. Human-review agreement','표 3. 사람 검토 일치도')], 's5-1':[('RQ1 metrics','RQ1 측정 지표')], 's5-2':[('RQ2 analysis dimensions','RQ2 분석 항목')]}
for item in sections:
    if item['id'] not in table_labels:continue
    for lang in ['en','ko']:
        d=soup(item[lang+'html'])
        for i,table in enumerate(d.find_all('table')):
            wrap=d.new_tag('div',attrs={'class':'comparison','id':item['id']+'-table-'+str(i)})
            table.wrap(wrap)
            title=d.new_tag('p',attrs={'class':'table-caption'})
            title.string=table_labels[item['id']][i][0 if lang=='en' else 1]
            wrap.insert(0,title)
        item[lang+'html']=str(d)

# Normalize figures, local paths, and table emphasis without modifying source files.
for item in sections:
    for field in ['enhtml','kohtml','olden','oldko']:
        base=OLD.parent if (field.startswith('ko') or field=='oldko') and item['id']!='s1' else SRC
        item[field]=prepare_html(item[field],base)
    if item['id']=='s2':
        # Show the exact requested deletion without hiding it among earlier paragraphs.
        item['olden']='<p>Financial data informs decisions ranging from personal asset management to corporate reporting and national economic activity. Datasets for evaluating financial language models therefore need to address not only text comprehension but also numerical units and periods, computational relationships, and evidence supporting an answer.</p>'
        item['oldko']='<p>금융 데이터는 개인의 자산 관리부터 기업의 재무 보고와 국가의 경제 활동까지 폭넓은 판단에 사용된다. 따라서 금융 언어 모델을 평가하는 데이터셋은 문장에 대한 이해뿐 아니라, 수치의 단위와 기간, 계산 관계, 답을 뒷받침하는 근거를 함께 다뤄야 한다.</p>'

from revise_construction import apply_review
sections = apply_review(sections)

(RUN/'paper-review.json').write_text(json.dumps(sections,ensure_ascii=False,indent=2))

TEMPLATE=Path(__file__).with_name('templates')/'research/paper-revision.html'
template=TEMPLATE.read_text()
for lang,name in [('en','finject-introduction-redline.html'),('ko','finject-introduction-ko-redline.html')]:
    result=template.replace('__DEFAULT_LANG__',lang).replace('__DOCUMENT_DATA__',json.dumps(sections,ensure_ascii=False).replace('</','<\\/'))
    (VIS/name).write_text(result)

for lang in ['ko','en']:
    parts=[]
    for item in sections:
        parts.append(('### ' if item['level'] else '## ')+item[lang]+'\n')
        plain=subprocess.run(['pandoc','-f','html','-t','gfm','--wrap=none'],input=item[lang+'html'],text=True,capture_output=True,check=True).stdout
        # Keep image data in the review HTML, but use source paths for the shared Markdown viewer.
        all_assets={'Figure1.png':ROOT/'paper/asset/Figure1-bh.png'}
        for img in SRC.glob('revision-*.png'):all_assets[img.name]=img
        for img in (OLD.parent/'figures').glob('figure-*.svg'):all_assets[img.name]=img
        all_assets['revision-taxonomy.pdf']=ROOT/'paper/asset/Figure3-bh.png'
        for path in all_assets.values():
            if path.exists():plain=plain.replace(image_uri(path),str(path))
        parts.append(plain+'\n')
    (RUN/f'PAPER-{lang.upper()}.md').write_text('# FInject — '+('논문 검토 초안' if lang=='ko' else 'Paper Revision Draft')+'\n\n'+''.join(parts))

manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC/'main.tex',SRC/'revision-20261002-body.tex',SRC/'sections/01-introduction.tex',OLD,RUN/'content/related-ko.md',RUN/'content/related-en.md',RUN/'content/table-column-notes.json']}
(RUN/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'sections':len(sections),'bibliography_entries':len(references),'html_files':[str(VIS/x) for x in ['finject-introduction-redline.html','finject-introduction-ko-redline.html']]},ensure_ascii=False))
