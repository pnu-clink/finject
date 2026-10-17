"""Typeset the approved English manuscript without changing its research claims."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'reports/run/20261002-overleaf-abstention-update'
OUT = RUN / 'revised'
SOURCE = ROOT / 'reports/run/20261002-abstention-paper-draft/PAPER-EN.md'
BACKUP = RUN / 'backup/original-project'
OUT.mkdir(parents=True, exist_ok=True)
for name in ['acl.sty', 'acl_natbib.bst', 'references.bib', 'review-line-numbers.tex']:
    shutil.copy2(BACKUP / name, OUT / name)
shutil.copy2(BACKUP / 'main.tex', OUT / 'main-before-20261002.tex')
assets = {
    'revision-overview.png': ROOT / 'paper/asset/pipeline-overview-v3-abstract.png',
    'revision-pipeline.png': ROOT / 'paper/asset/pipeline-overview-v3.png',
    'revision-taxonomy.pdf': SOURCE.parent / 'figures/perturbation-taxonomy-one-column.pdf',
    'revision-graph-example.png': SOURCE.parent / 'figures/graph-perturbation-sample.png',
}
for name, path in assets.items():
    shutil.copy2(path, OUT / name)

keys = ['finqa', 'tatqa', 'finance_reasoning', 'finchain', 'tab_cqa', 'realfin',
        'finmaster', 'finauditing', 'fined', 'finrule', 'finrca', 'rfc',
        'contradoc', 'wikicontradict', 'magic', 'qacc']
bib = (OUT / 'references.bib').read_text()
urls = {}
for chunk in re.split(r'(?=^@)', bib, flags=re.M):
    match = re.match(r'@\w+\{([^,]+),', chunk)
    url = re.search(r'url\s*=\s*[{"]([^}"\n]+)', chunk)
    if match and url:
        urls[url.group(1)] = match.group(1)

def key_for(url):
    if url in urls:
        return urls[url]
    for old, key in urls.items():
        if 'arxiv.org' in url and re.search(r'\d{4}\.\d{4,5}', url).group() in old:
            return key
    raise ValueError(f'Unmapped source: {url}')

def tex(text, citations=True):
    text = text.replace('“\ubbf8\ud3c9\uac00” (“not evaluated”)', '“not evaluated” (shown in Korean)')
    text = text.replace('✓', r'$\checkmark$').replace('κ', r'$\kappa$')
    text = text.replace('→', r'$\rightarrow$').replace('−', '-')
    if citations:
        text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',
                      lambda m: r'\citep{' + key_for(m[2]) + '}', text)
    text = re.sub(r'\\citep\{([^}]+)\}(?:, \\citep\{([^}]+)\})+',
                  lambda m: r'\citep{' + ','.join(re.findall(r'\\citep\{([^}]+)\}', m[0])) + '}', text)
    result = subprocess.run(['pandoc', '-f', 'markdown+raw_tex', '-t', 'latex', '--wrap=none'],
                            input=text, text=True, capture_output=True, check=True).stdout.strip()
    return result

lines = SOURCE.read_text().splitlines()
abstract = lines[4]
body = []
i = 6
table_index = 0
pending_caption = None
trims = {3: '20 533 20 114', 4: '20 326 20 331',
         6: '26 49 799 589', 7: '1136 46 20 550'}
while i < len(lines):
    line = lines[i]
    if not line.strip():
        i += 1
        continue
    if line.startswith('## '):
        match = re.match(r'## (\d+)\. (.*)', line)
        body.append(r'\setcounter{section}{' + str(int(match[1])-1) + '}\n'
                    + r'\section{' + tex(match[2]) + '}')
        i += 1
        continue
    if line.startswith('### '):
        match = re.match(r'### (\d+)\.(\d+) (.*)', line)
        body.append(r'\setcounter{subsection}{' + str(int(match[2])-1) + '}\n'
                    + r'\subsection{' + tex(match[3]) + '}')
        i += 1
        continue
    if line.startswith('**Table '):
        pending_caption = re.sub(r'^\*\*Table \d+\. |\*\*$', '', line)
        i += 1
        continue
    if line.startswith('|'):
        rows = []
        while i < len(lines) and lines[i].startswith('|'):
            if not re.match(r'^\|[-:|]+\|$', lines[i]):
                rows.append([c.strip() for c in lines[i][1:-1].split('|')])
            i += 1
        table_index += 1
        cols = len(rows[0])
        numbered = pending_caption is not None
        # Only Tables 1--3 were numbered in the approved manuscript.
        # Other schema and metric matrices retain their unnumbered status.
        specs = {
            11: r'@{}p{0.24\textwidth}*{10}{>{\centering\arraybackslash}X}@{}',
            4: r'@{}>{\raggedright\arraybackslash}p{0.24\textwidth}*{3}{>{\raggedright\arraybackslash}X}@{}',
            3: r'@{}>{\raggedright\arraybackslash}p{0.22\textwidth}*{2}{>{\raggedright\arraybackslash}X}@{}',
        }
        if table_index == 2:
            rows[0] = ['Dataset', 'Num. QA', 'Fact.', 'Confl. detect.', 'Confl. QA',
                       'Insuff. evid.', 'Abst. metrics', 'Input recov.', 'Expl. consist.', 'Paired', 'Config.']
        rendered = []
        for j, row in enumerate(rows):
            cells = [tex(c, citations=False) for c in row]
            if j == 0:
                cells = [r'\textbf{' + c + '}' for c in cells]
            rendered.append(' & '.join(cells) + r' \\')
            if j == 0:
                rendered.append(r'\midrule')
        block = ['\\begin{table*}[!t]', r'\centering', r'\small',
                 r'\setlength{\tabcolsep}{3pt}', r'\renewcommand{\arraystretch}{1.15}',
                 r'\begin{tabularx}{\textwidth}{' + specs[cols] + '}', r'\toprule',
                 *rendered, r'\bottomrule', r'\end{tabularx}']
        if numbered:
            block.append(r'\caption{' + tex(pending_caption) + '}')
        block += [r'\end{table*}']
        body.append('\n'.join(block))
        pending_caption = None
        continue
    if line.startswith('!['):
        number = int(re.match(r'!\[Figure (\d+)', line)[1])
        i += 1
        while not lines[i].strip():
            i += 1
        caption = re.sub(r'^Figure \d+\. ', '', lines[i])
        if number in trims:
            opts = 'width=\\textwidth,trim={' + trims[number] + '},clip'
            file = 'revision-pipeline.png'
        elif number == 1:
            opts, file = 'width=\\textwidth', 'revision-overview.png'
        elif number == 2:
            opts, file = 'width=\\columnwidth', 'revision-taxonomy.pdf'
        else:
            opts, file = 'width=.80\\textwidth,height=.58\\textheight,keepaspectratio', 'revision-graph-example.png'
        environment = 'figure' if number == 2 else 'figure*'
        body.append('\n'.join([r'\begin{' + environment + '}[!t]', r'\centering',
                    r'\includegraphics[' + opts + ']{' + file + '}',
                    r'\caption{' + tex(caption) + '}',
                    r'\label{fig:revision-' + str(number) + '}', r'\end{' + environment + '}']))
        i += 1
        continue
    paragraph = [line]
    i += 1
    while i < len(lines) and lines[i].strip():
        paragraph.append(lines[i])
        i += 1
    body.append(tex('\n'.join(paragraph)))

body_text = '\n\n'.join(body) + '\n'
# Declare the requested floats earlier without reordering prose or table data.
# This places Table 2 on page 3 and Figures 3--4 on page 5 in this revision.
tables = list(re.finditer(r'\\begin\{table\*\}.*?\\end\{table\*\}', body_text, re.S))
table_two = tables[1]
table_text = table_two[0]
body_text = body_text[:table_two.start()] + body_text[table_two.end():]
anchor = r'\setcounter{subsection}{2}' + '\n' + r'\subsection{Evaluation Research}'
body_text = body_text.replace(anchor, '% Float declared early so Table 2 appears on page 3.\n' + table_text + '\n\n' + anchor)
panels = []
for number in (3, 4):
    panel = next(m for m in re.finditer(r'\\begin\{figure\*\}.*?\\end\{figure\*\}', body_text, re.S)
                 if f'\\label{{fig:revision-{number}}}' in m[0])
    panels.append(panel[0])
    body_text = body_text[:panel.start()] + body_text[panel.end():]
anchor = r'\setcounter{subsection}{1}' + '\n' + r'\subsection{Perturbation Taxonomy}'
body_text = body_text.replace(anchor, '% Figures 3 and 4 are declared together for page 5.\n' + '\n\n'.join(panels) + '\n\n' + anchor)
(OUT / 'revision-20261002-body.tex').write_text(body_text)
preamble = (BACKUP / 'main.tex').read_text().split(r'\title{')[0]
preamble = preamble.replace(r'\bigcirc', r'\checkmark')
preamble += r'''
% Source manuscript: PAPER-EN.md, revision 2026-10-02.
% Existing sections and appendices remain in the project as historical material.
\pdfimageresolution=72
\setlength{\emergencystretch}{1.5em}
\title{FInject: Evaluating Answering and Abstention\\in Financial Reasoning}
\author{Anonymous ACL submission}
\begin{document}
\maketitle
\begin{abstract}
'''
main = preamble + tex(abstract) + '\n' + r'''
\end{abstract}
\input{revision-20261002-body}
\FloatBarrier
\nocite{finqa,tatqa,finance_reasoning,finchain,tab_cqa,realfin,finmaster,finauditing,fined,finrule,finrca,rfc,contradoc,wikicontradict,magic,qacc}
\bibliography{references}
\end{document}
'''
(OUT / 'main.tex').write_text(main)
hashes = {str(p.relative_to(BACKUP)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(BACKUP.rglob('*')) if p.is_file()}
(RUN / 'backup/manifest.json').write_text(json.dumps(hashes, indent=2) + '\n')
with zipfile.ZipFile(RUN / 'backup/before-abstention-revision.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(BACKUP.rglob('*')):
        if p.is_file():
            z.write(p, p.relative_to(BACKUP))
(RUN / 'evidence/conversion.json').write_text(json.dumps({
    'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'tables': table_index, 'figures': 7, 'numbered_tables': 3,
    'existing_files_modified': ['main.tex'],
    'backup_project_url': 'https://www.overleaf.com/project/6abf59b2b7c19f047993cd1a',
    'figure_edits': 'Single-column vector taxonomy added; user-supplied graph screenshot replaced; pipeline viewports preserved.',
    'translation_adjustment': 'Korean screenshot status rendered in English in caption; image unchanged.',
}, indent=2) + '\n')
print(f'Prepared {OUT}; {table_index} tables and 7 figures.')
