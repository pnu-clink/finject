"""Apply reviewed English paragraphs and audit numbered Draft references."""
import copy
import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString
from finarch.documentation.draft_editor import DraftRepository, EMBEDDED


def normalize(sections):
    for lang in ('en', 'ko'):
        docs = [(s, BeautifulSoup(s[lang+'html'], 'html.parser')) for s in sections]
        targets = {}
        counts = {('main','figure'):0, ('main','table'):0, ('appendix','figure'):0, ('appendix','table'):0}
        for s,b in docs:
            area='appendix' if s['en'].startswith('Appendix') else 'main'
            for n in b.select('figure, table'):
                counts[area,n.name]+=1
                num=('A' if area=='appendix' else '')+str(counts[area,n.name])
                kind='Figure' if n.name=='figure' else 'Table'
                n['data-'+n.name+'-number']=num
                cap=n.find('figcaption' if n.name=='figure' else 'caption')
                if cap:
                    first=next((t for t in cap.find_all(string=True) if re.search('(?:Figure|Table|\uadf8\ub9bc|\ud45c)\\s*A?\\d+',str(t))),None)
                    if first:first.replace_with(re.sub('(?:Figure|Table|\uadf8\ub9bc|\ud45c)\\s*A?\\d+',kind+' '+num,str(first),count=1))
                for child in [n,*n.select('[id]')]:
                    if child.get('id'):targets[child['id']]=(kind,num)
                for parent in n.parents:
                    if parent.name=='[document]':break
                    if parent.get('id') and len(parent.select('figure, table'))==1:targets[parent['id']]=(kind,num)
        ids={s['id'] for s in sections}
        ids.update(n['id'] for _,b in docs for n in b.select('[id]'))
        for s,b in docs:
            for a in b.select('a[href^="#"]'):
                href=a['href'][1:]
                if href not in ids:raise ValueError(('Broken link',lang,s['id'],href))
                if href not in targets:continue
                kind,num=targets[href]
                # Replace full label even if an old number was split across nodes.
                text=a.get_text(' ',strip=True)
                if re.search('(?:Figure|Table|\uadf8\ub9bc|\ud45c)\\s*A?\\d+',text):
                    a.string=re.sub('(?:Figure|Table|\uadf8\ub9bc|\ud45c)\\s*A?\\d+',kind+' '+num,text)
            s[lang+'html']=str(b)
        print(lang,counts)


def main():
    repo=DraftRepository(); before=repo.source.read_text(); sections=json.loads(before)
    backup=repo.directory/'backup'/('bilingual-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    for p in [repo.source,repo.markdown,repo.directory/'PAPER-EN.md',repo.directory/'Draft compression.md',*repo.previews]:shutil.copy2(p,backup/p.name)
    original=copy.deepcopy(sections)
    patches=json.loads(Path('tmp/pdfs/english-sync.json').read_text())
    for s in sections:
        if s['id'] not in patches:continue
        doc=BeautifulSoup(s['enhtml'],'html.parser'); paragraphs=doc.find_all('p')
        for idx,html in patches[s['id']].items():
            p=paragraphs[int(idx)]
            if html is None:p.decompose();continue
            replacement=BeautifulSoup('<p>'+html+'</p>','html.parser').p
            replacement.attrs=copy.deepcopy(p.attrs)
            p.replace_with(replacement)
        s['enhtml']=str(doc)
    for s in sections:
        if s['id']=='s4-2':
            b=BeautifulSoup(s['kohtml'],'html.parser');p=b.find_all('p')[7]
            p.clear();p.append(BeautifulSoup('<strong>The scope of judgment.</strong> The misstatement distinguishes it from the NASU. Preserves the state of reason, use, inspection, and verifies the original citation. 4.3Calculate from the section: <a href="#table-s11-nasu-3">Appendix 4.2, Table A20</a>).','html.parser'))
            s['kohtml']=str(b)
        if s['id']=='s5-1':s['kohtml']=s['kohtml'].replace('\ubcc4\ub3c4 Figure A4\uc758 Haiku','Separate <a href="#fig:arv-fav-full-cases">Figure A5</a>Haiku of')
        if s['id']=='s5':s['kohtml']=s['kohtml'].replace('<a href="#s11-pipeline-3">Appendix P.5</a>','<a href="#s11-pipeline-3">Appendix 4.1</a>The analytical prompt: <a href="#prompts-analysis">Appendix P.5</a>')
        if s['id']=='s3-3':s['kohtml']=s['kohtml'].replace('**\ubb38\ub9e5\uac80\uc0ac**','<strong>Context testing.</strong>')
    normalize(sections)
    # Keep all non-prose data and the conclusion unchanged.
    for old,new in zip(original,sections):
        for lang in ('en','ko'):
            a=BeautifulSoup(old[lang+'html'],'html.parser');b=BeautifulSoup(new[lang+'html'],'html.parser')
            assert len(a.select('figure,table'))==len(b.select('figure,table'))
            assert [n.get('data-figure-file') for n in a.select('figure')]==[n.get('data-figure-file') for n in b.select('figure')]
            assert [[c.get_text() for c in t.select('td,th')] for t in a.select('table')]==[[c.get_text() for c in t.select('td,th')] for t in b.select('table')]
        if old['id']=='conclusion':assert old==new
    updates={repo.source:json.dumps(sections,ensure_ascii=False,indent=2)+'\n'}
    for lang,name in [('ko','PAPER-KO.md'),('en','PAPER-EN.md')]:
        path=repo.directory/name; previous=path.read_text()
        text='# FInject\n\n'
        for s in sections:
            text+=('### ' if s['level'] else '## ')+s[lang]+'\n\n'+repo.markdown_body(s[lang+'html'],previous)+'\n\n'
        updates[path]=text
    cp=repo.directory/'Draft compression.md'
    updates[cp]='# Draft compression\n\n'+''.join(('### ' if s['level'] else '## ')+s['ko']+'\n\n'+repo.markdown_body(s['kohtml'],cp.read_text())+'\n\n' for s in sections if re.fullmatch(r's[1-5](?:-\d+)?',s['id']))
    prior_compressed=cp.read_text()
    if '## 6. Conclusion' in prior_compressed:
        updates[cp]+=prior_compressed[prior_compressed.index('## 6. Conclusion'):]
    embedded=json.dumps(sections,ensure_ascii=False).replace('</script','<\\/script')
    for p in repo.previews:updates[p]=EMBEDDED.sub(lambda m:m[1]+embedded+m[3],p.read_text(),count=1)
    assert repo.source.read_text()==before,'Draft changed during synchronization'
    for p,text in updates.items():repo.atomic_write(p,text)
    print('Saved',len(updates),'files; backup',backup)

if __name__=='__main__':main()
