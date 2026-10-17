"""Synchronize the review draft and compile a local-only LaTeX preview."""
from pathlib import Path
import argparse
import base64
import copy
import datetime
import hashlib
import json
import re
import shutil
import subprocess

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
REVIEW = ROOT / 'reports/run/20261003-paper-revision-draft'
RUN = ROOT / 'reports/run/20261003-paper-local-sync'
LOCAL = ROOT / 'paper/local-preview'
DEPLOYED = ROOT / 'reports/run/20261003-construction-revision/revised'
VIS = Path('/Users/wooix/.codex/visualizations/2026/10/02/01a0fb53-72f4-7ca1-9765-8977e7c0b21f')
STATE = ROOT / 'paper/instructdion/MANUSCRIPT-STATE.json'


def state():
    s = json.loads(STATE.read_text())
    assert sum(s['sources'].values()) == s['originals']
    assert s['originals'] * (1 + s['variants_per_original']) == s['items_including_originals']
    assert s['items_including_originals'] * s['conditions'] == s['planned_response_slots_if_all_conditions']
    return s


def counts(text):
    s = state()
    replacements = {'1,817': f"{s['originals']:,}", '1,637': f"{s['originals']:,}",
                    '14,536': f"{s['items_including_originals']:,}",
                    '557': str(s['sources']['TAT-QA']), '58,144': f"{s['planned_response_slots_if_all_conditions']:,}"}
    for before, after in replacements.items():
        text = re.sub(r'(?<![\d,])' + re.escape(before) + r'(?![\d,])', after, text)
    return text


def normalize_sections(sections):
    sections = copy.deepcopy(sections)
    figmap = state()['figures']
    legacy = {f'fig:revision-{i}': 'fig:pipeline-full' for i in [3, 4, 6, 7]}
    for item in sections:
        before = {lang: item[lang+'html'] for lang in ['en', 'ko']}
        if item['id'] == 's5-2':
            item['en'] = '5.2 RQ2: How do model responses change when evidence conflicts or is removed?'
            item['ko'] = '5.2 RQ2: How does the model respond when the evidence collides or is removed?'
        for lang in ['en', 'ko']:
            key = lang+'html'
            count_doc = BeautifulSoup(item[key], 'html.parser')
            for node in list(count_doc.find_all(string=True)):
                if not node.find_parent(['script','style']):
                    node.replace_with(counts(str(node)))
            text = str(count_doc)
            if item['id'] == 's1':
                text = text.replace('source problems from FinanceReasoning,', 'source problems from FinanceReasoning and TAT-QA,')
                text = text.replace('FinanceReasoning\uc758 \uc6d0\ucc9c \ubb38\ud56d', 'Source phrase from FinanceReasoning and TAT-QA')
                text = text.replace('1,551 answerable', 'answerable').replace('\ub2f5\ubcc0 \uac00\ub2a5\ud55c 1,551\uac1c\uc758', 'Answerable').replace('Answerable 1,551items', 'Answerable')
            if item['id'] == 's3-2':
                text = re.sub(r'We use <strong>.*?</strong>\.', 'We draw seed problems from FinanceReasoning and TAT-QA. Appendix # reports source counts before human annotation; the final release size may change after annotation.', text, count=1)
                text = re.sub('<strong>FinanceReasoning.*?</strong>\ub97c \uc0ac\uc6a9\ud55c\ub2e4\\.', 'FinanceReasoning\uacfc TAT-QA\uc5d0\uc11c \uc6d0\ubcf8 \ubb38\uc81c\ub97c \uc120\uc815\ud55c\ub2e4. human annotation \uc804 \uc6d0\ucc9c\ubcc4 \uc218\ub7c9\uc740 Appendix #\uc5d0 \uae30\ub85d\ud558\uba70, \uc0ac\ub78c \uac80\uc99d \ud6c4 \ucd5c\uc885 \uacf5\uac1c \uc218\ub7c9\uc740 \ub2ec\ub77c\uc9c8 \uc218 \uc788\ub2e4.', text, count=1)
            if item['id'] == 's3-3':
                text = re.sub(r'Including one original.*?separately in Section 4\.', 'Each family contains one original and seven variants. Appendix # records counts before human annotation; Section 4 describes human verification.', text, flags=re.S)
                text = re.sub('\uc6d0\ubcf8 1\uac1c\uc640 \ubcc0\ud615 7\uac1c\ub97c \ud569\uccd0.*?\ubcc4\ub3c4\ub85c \ub2e4\ub8ec\ub2e4\\.', '\uac01 \ubb38\ud56d\uad70\uc740 \uc6d0\ubcf8 1\uac1c\uc640 \ubcc0\ud615 7\uac1c\ub85c \uad6c\uc131\ub41c\ub2e4. human annotation \uc804 \uc218\ub7c9\uc740 Appendix #\uc5d0 \uae30\ub85d\ud558\uace0, \uc0ac\ub78c \uac80\uc99d\uc740 4\uc7a5\uc5d0\uc11c \ub2e4\ub8ec\ub2e4.', text, flags=re.S)
            doc = BeautifulSoup(text, 'html.parser')
            if item['id'] == 's4':
                for table in list(doc.find_all('table')):
                    if 'Selection stage' in table.get_text() or '\uc120\uc815 \ub2e8\uacc4' in table.get_text(): table.decompose()
                for p in list(doc.find_all('p')):
                    if re.search(r'2,238|1,050|1,551|,238|,080', p.get_text()): p.decompose()
                    elif p.get_text(strip=True) in ['Release sampling stages', '\uacf5\uac1c \ud45c\ubcf8 \uc120\uc815 \ub2e8\uacc4']: p.decompose()
                if not doc.find(id='cohort-status'):
                    p = doc.new_tag('p', id='cohort-status')
                    p.string = ('Appendix # records the collection size before human annotation. Human annotation may change the final release size. We will report the final cohort, exclusions, and completed review coverage after annotation.' if lang == 'en' else 'In Appendix #, the human annotation records the amount prior to the person\'s verification. The final disclosure amount may vary during the verification process. The final inclusion, exclusion, and judgement completion range are reported separately after verification.')
                    doc.insert(0, p)
            for a in doc.select('a[data-reference], a[href*="fig:"]'):
                target = a.get('data-reference') or a.get('href', '').lstrip('#')
                target = legacy.get(target, target)
                if target in figmap:
                    a['data-reference'] = target; a['href'] = '#'+target
                    a.string = str(figmap[target])
            for fig in doc.find_all('figure'):
                fid = fig.get('id')
                assets = {'fig:abstention-intro': ROOT/'paper/asset/Figure1-bh.png',
                          'fig:revision-1': ROOT/'paper/asset/pipeline-overview-v3-abstract.png',
                          'fig:revision-2': ROOT/'paper/asset/Figure3-bh.png',
                          'fig:pipeline-full': ROOT/'paper/asset/pipeline-overview-v3.png',
                          'fig:revision-5': DEPLOYED/'revision-graph-example.png'}
                if fid in assets and fig.img:
                    fig.img['src'] = 'data:image/png;base64,'+base64.b64encode(assets[fid].read_bytes()).decode()
                if fid == 'fig:pipeline-full' and fig.img:
                    # Hide the image's obsolete built-in caption at layout time.
                    # Preserve the source PNG; the document owns the figure number.
                    fig.img['style'] = 'clip-path:inset(0 0 4% 0)'
                if fid in figmap and fig.figcaption:
                    old = fig.figcaption.get_text(' ', strip=True)
                    fig.figcaption.string = re.sub('^(?:Figure|\uadf8\ub9bc)\\s*\\d+\\.?\\s*', f'Figure {figmap[fid]}. ', old)
            # Existing Korean prose contains plain references rather than linked labels.
            if lang == 'ko':
                targets = {'s5-1': 5, 's11-pipeline-1': 4, 's11-pipeline-2': 4, 's11-pipeline-3': 4, 's11-pipeline-4': 4}
                for node in list(doc.find_all(string=True)):
                    if node.find_parent(['figcaption', 'a', 'script']):
                        continue
                    value = str(node)
                    if item['id'] in targets:
                        value = re.sub('(\uadf8\ub9bc|Figure)\\s+[4-8](?!\\d)', lambda m: m[1]+' '+str(targets[item['id']]), value)
                    node.replace_with(value)
            item[key] = str(doc)
        if any(item[lang+'html'] != before[lang] for lang in ['en', 'ko']):
            for lang in ['en', 'ko']:
                if not item.get('old'+lang): item['old'+lang] = before[lang]
            item['state'] = 'revised'
    if not any(x['id']=='s11-counts' for x in sections):
        sections.insert(next(i for i,x in enumerate(sections) if x['id']=='s11')+1, dict(id='s11-counts',en='Appendix #. Counts before human annotation',ko='Appendix #. Human annotation before quantity',enhtml='',kohtml='',olden='',oldko='',state='revised',level=1))
    item = next(x for x in sections if x['id']=='s11-counts')
    for lang in ['en','ko']:
        md = (ROOT/f'paper/local-preview-content/counts-{lang}.md').read_text()
        item[lang+'html'] = subprocess.run(['pandoc','-f','markdown','-t','html','--wrap=none'],input=md,text=True,capture_output=True,check=True).stdout
    return sections


def write_review(sections):
    (REVIEW/'paper-review.json').write_text(json.dumps(sections, ensure_ascii=False, indent=2)+'\n')
    template = (ROOT/'src/finarch/documentation/templates/research/paper-revision.html').read_text()
    for lang, name in [('en','finject-introduction-redline.html'), ('ko','finject-introduction-ko-redline.html')]:
        data = json.dumps(sections, ensure_ascii=False).replace('</', '<\\/')
        (VIS/name).write_text(template.replace('__DEFAULT_LANG__', lang).replace('__DOCUMENT_DATA__', data))
    assets = {'fig:abstention-intro': 'Figure1.png', 'fig:revision-1': 'revision-overview.png',
              'fig:revision-2': 'Figure3-bh.png', 'fig:pipeline-full': 'revision-pipeline.png',
              'fig:revision-5': 'revision-graph-example.png'}
    for lang in ['en', 'ko']:
        parts = []
        for item in sections:
            doc = BeautifulSoup(item[lang+'html'], 'html.parser')
            for fig in doc.find_all('figure'):
                if fig.get('id') in assets and fig.img: fig.img['src'] = str(LOCAL/assets[fig['id']])
            md = subprocess.run(['pandoc', '-f', 'html', '-t', 'gfm', '--wrap=none'], input=str(doc), text=True, capture_output=True, check=True).stdout
            parts.append(('### ' if item['level'] else '## ')+item[lang]+'\n\n'+md)
        (REVIEW/f'PAPER-{lang.upper()}.md').write_text('\n\n'.join(parts))


def refresh_references(sections):
    """Use the bibliography printed by the latest local build in both languages."""
    bbl = (LOCAL/'main.bbl').read_text()
    matches = list(re.finditer(r'\\bibitem\[.*?\]\{([^}]+)\}',bbl,re.S))
    refs=[]
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else bbl.index(r'\end{thebibliography}')
        content=bbl[m.end():end].replace(r'\newblock',' ')
        content=re.sub(r'\\href\s+',r'\\href ',content)
        html=subprocess.run(['pandoc','-f','latex','-t','html','--wrap=none'],input=content,text=True,capture_output=True,check=True).stdout
        refs.append('<div class="reference" id="ref-'+m[1]+'">'+html+'</div>')
    item=next(x for x in sections if x['id']=='references')
    for lang in ['en','ko']:
        if item[lang+'html']!=''.join(refs):
            item['old'+lang]=item[lang+'html'];item[lang+'html']=''.join(refs);item['state']='revised'
    return sections


def local_sources(sections):
    if not LOCAL.exists():
        shutil.copytree(DEPLOYED, LOCAL, ignore=shutil.ignore_patterns('*.aux','*.bbl','*.blg','*.fdb_latexmk','*.fls','*.log','*.out','*.zip','main.pdf'))
    main = LOCAL/'main.tex'
    preamble = main.read_text()
    if r'\providecommand{\tightlist}' not in preamble:
        preamble = preamble.replace(r'\begin{document}', r'\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}'+'\n'+r'\begin{document}')
        main.write_text(preamble)
    for path in [LOCAL/'revision-20261002-body.tex', LOCAL/'sections/01-introduction.tex']:
        text = counts(path.read_text())
        text = text.replace('source problems from FinanceReasoning,', 'source problems from FinanceReasoning and TAT-QA,')
        text = text.replace('1,551 answerable', 'answerable')
        text = text.replace('RQ2: How do responses change when intermediate reasoning when numeric evidence change?', 'RQ2: How do model responses change when evidence conflicts or is removed?')
        text = text.replace(r'\includegraphics[width=\textwidth]{revision-pipeline.png}', r'\includegraphics[width=\textwidth,trim=0 35 0 0,clip]{revision-pipeline.png}')
        if path.name == 'revision-20261002-body.tex':
            text = re.sub(r'We use \\textbf\{.*?1,551 originals\}\.', 'We draw seed problems from FinanceReasoning and TAT-QA. Appendix # reports source counts before human annotation; the final release size may change after annotation.'.replace('#',r'\#'), text, count=1)
            text = re.sub(r'Including one original.*?separately in Section 4\.', lambda m:'Each family contains one original and seven variants. Appendix \\# records counts before human annotation; Section 4 describes human verification.', text, count=1, flags=re.S)
            start = text.index(r'\section{Release Sampling and Human Verification}')+len(r'\section{Release Sampling and Human Verification}')
            end = text.index('Human reviewers assess',start)
            text = text[:start]+'\n\nAppendix \\# records the collection size before human annotation. Human annotation may change the final release size. We will report the final cohort, exclusions, and completed review coverage after annotation.\n\n'+text[end:]
            md = (ROOT/'paper/local-preview-content/counts-en.md').read_text()
            extra = subprocess.run(['pandoc','-f','markdown','-t','latex','--wrap=none'],input=md,text=True,capture_output=True,check=True).stdout
            if r'\label{app:pre-human-counts}' not in text:
                marker = r'\subsection*{Appendix \#: Framework workflow}'
                insertion = text.rfind(r'\clearpage',0,text.index(marker))
                text = text[:insertion]+'\n\\subsection*{Appendix \\#: Counts before human annotation}\\label{app:pre-human-counts}\n'+extra+'\n'+text[insertion:]
            else:
                start = text.index(r'\label{app:pre-human-counts}')+len(r'\label{app:pre-human-counts}')
                end = text.index(r'\clearpage',start)
                text = text[:start]+'\n'+extra+'\n'+text[end:]
        # Match the captions in the current Revision Draft, preserving LaTeX labels.
        for item in sections:
            for fig in BeautifulSoup(item['enhtml'], 'html.parser').find_all('figure'):
                fid = fig.get('id')
                if not fid or not fig.figcaption: continue
                caption = re.sub(r'^Figure\s+\d+\.\s*', '', fig.figcaption.get_text(' ', strip=True))
                caption = subprocess.run(['pandoc','-f','markdown','-t','latex','--wrap=none'], input=caption, text=True, capture_output=True, check=True).stdout.strip()
                label_pos = text.find('\\label{'+fid+'}')
                if label_pos < 0: continue
                cap_pos = text.rfind('\\caption',0,label_pos)
                match = re.match(r'\\caption(?:of\{figure\})?\{',text[cap_pos:])
                if not match: continue
                start = cap_pos+match.end(); end = start; depth = 1
                while depth:
                    if text[end] == '{' and text[end-1] != '\\': depth += 1
                    if text[end] == '}' and text[end-1] != '\\': depth -= 1
                    end += 1
                text = text[:start]+caption+text[end-1:]
        path.write_text(text)
    for src, dest in [('Figure1-bh.png','Figure1.png'), ('Figure3-bh.png','Figure3-bh.png'), ('pipeline-overview-v3-abstract.png','revision-overview.png'), ('pipeline-overview-v3.png','revision-pipeline.png')]:
        shutil.copy2(ROOT/'paper/asset'/src, LOCAL/dest)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--build', action='store_true'); args = parser.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    backup = RUN/'backup'
    if not backup.exists():
        backup.mkdir()
        for path in [REVIEW/'paper-review.json', REVIEW/'PAPER-EN.md', REVIEW/'PAPER-KO.md', VIS/'finject-introduction-redline.html', VIS/'finject-introduction-ko-redline.html']:
            shutil.copy2(path, backup/path.name)
    sections = normalize_sections(json.loads((REVIEW/'paper-review.json').read_text()))
    local_sources(sections)
    write_review(sections)
    if args.build:
        result = subprocess.run(['latexmk','-pdf','-interaction=nonstopmode','-halt-on-error','main.tex'], cwd=LOCAL, text=True, capture_output=True)
        (RUN/'latexmk.log').write_text(result.stdout+'\n'+result.stderr)
        if result.returncode: raise RuntimeError('Local LaTeX compilation failed; see latexmk.log')
        sections=refresh_references(sections)
        write_review(sections)
    now = datetime.datetime.now().astimezone().isoformat()
    files = [STATE, REVIEW/'paper-review.json', REVIEW/'PAPER-EN.md', REVIEW/'PAPER-KO.md', LOCAL/'main.tex', LOCAL/'revision-20261002-body.tex', LOCAL/'sections/01-introduction.tex']
    if (LOCAL/'main.pdf').exists(): files.append(LOCAL/'main.pdf')
    manifest = {'updated_at': now, 'overleaf_modified': False, 'counts': state(), 'files': [{'path':str(p.relative_to(ROOT)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    (RUN/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    with (RUN/'events.jsonl').open('a') as f: f.write(json.dumps({'at':now,'event':'local_review_sync','compiled':args.build,'overleaf_modified':False})+'\n')
    print(json.dumps({'review':str(REVIEW/'paper-review.json'),'local_project':str(LOCAL),'compiled':args.build,'overleaf_modified':False}))


if __name__ == '__main__':
    main()
