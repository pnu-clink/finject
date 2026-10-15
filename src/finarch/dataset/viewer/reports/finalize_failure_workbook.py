"""Add native OOXML hyperlinks missing from the workbook authoring surface."""
import json
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from datetime import datetime

def main(run='20260910-012'):
    directory=(Path('reports/run')/run/'failure-review').resolve()
    stem=run.rsplit('-',1)[-1]+'-failure-review'
    data=json.loads((directory/'review-data.json').read_text())
    cases=len(data['matrix']);failures=len(data['details']);excluded=len(data['exclusions'])
    path=directory/(stem+'.xlsx')
    links=json.loads((directory/'hyperlinks.json').read_text())
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel='http://schemas.openxmlformats.org/package/2006/relationships'
    docrel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    ET.register_namespace('',ns);ET.register_namespace('r',docrel)
    with ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
    workbook=ET.fromstring(files['xl/workbook.xml'])
    sheets=workbook.find('{'+ns+'}sheets')
    for i,sheet in enumerate(sheets,1):
        items=[x for x in links if x['sheet']==sheet.attrib['name']]
        if not items:continue
        name=f'xl/worksheets/sheet{i}.xml';rname=f'xl/worksheets/_rels/sheet{i}.xml.rels'
        tree=ET.fromstring(files[name]);rels=ET.fromstring(files[rname]) if rname in files else ET.Element('{'+rel+'}Relationships')
        hyperlinks=ET.Element('{'+ns+'}hyperlinks')
        for j,item in enumerate(items):
            attrs={'ref':item['cell'],'display':item['label']}
            if item['url'].startswith('#'):attrs['location']=item['url'][1:]
            else:
                rid=f'reviewLink{j}';attrs['{'+docrel+'}id']=rid
                ET.SubElement(rels,'{'+rel+'}Relationship',{'Id':rid,'Type':docrel+'/hyperlink','Target':item['url'],'TargetMode':'External'})
            ET.SubElement(hyperlinks,'{'+ns+'}hyperlink',attrs)
        before={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','tableParts','extLst'}
        position=next((n for n,e in enumerate(tree) if e.tag.split('}')[-1] in before),len(tree))
        tree.insert(position,hyperlinks)
        files[name]=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
        files[rname]=ET.tostring(rels,encoding='utf-8',xml_declaration=True)
    temp=path.with_suffix('.tmp')
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for name,value in files.items():z.writestr(name,value)
    temp.replace(path)
    with ZipFile(path) as z:
        assert z.testzip() is None
        actual=sum(len(ET.fromstring(z.read(n)).findall('.//{'+ns+'}hyperlink')) for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'))
        assert actual==len(links)
    exported=Path('outputs')/stem/(stem+'.xlsx')
    exported.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,exported)
    RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs
    logs=RunLogs.for_case(directory.parent)
    logs.write('pipeline.log','review.export_failure_workbook',stage='failure-review',phase='END')
    logs.write('detail.log','review.export_failure_workbook',stage='failure-review',value={'artifact':str(path),'cases':cases,'failures':failures,'excluded':excluded,'hyperlinks':actual})
    (directory/'verification.json').write_text(json.dumps({'created_at':datetime.now().astimezone().isoformat(),'cases':cases,'failures':failures,'excluded_cases':excluded,'links_verified':actual,'xlsx_zip_valid':True},indent=2))
    print(path)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='20260910-012')
    main(parser.parse_args().run)
