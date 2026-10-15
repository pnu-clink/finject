"""Current phase summaries and reproducible Excel exports, without model calls."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from finarch.dataset.viewer.reports.completion_report import snapshot, optional
from finarch.dataset.viewer.reports.token_charts import build as token_usage


def knowledge_sources(bundle, case):
    root=Path(bundle)/'01-preparation'/case
    marker=optional(root/'run.json',{})
    active=root/(marker.get('active_round') or '')
    for relative in ('03-calculation/05-record-calculation-artifacts/03-program.json',
                     '03-calculation/02-prepare-code/03-program.json'):
        program=optional(active/relative)
        if isinstance(program,dict):
            found=set(program.get('calculation_input_sources') or [])
            found.update(x.get('kind') for x in program.get('source_usage',[]) if isinstance(x,dict))
            return [x for x in ('IN_CONTEXT_DATA','EXTERNAL_DATA','EXTERNAL_RULE') if x in found]
    return []


def add_knowledge(bundle, data):
    cache={}
    for row in data['maps']+data['errors']:
        name=row['case']
        if name not in cache:cache[name]=knowledge_sources(bundle,name)
        row['knowledge_sources']=cache[name]
        row['knowledge']=' / '.join(cache[name]) or '미분류'
    return data


def build(bundle, phase='preparation'):
    if phase not in ('preparation','generation'):
        raise ValueError('INVALID_REPORT_PHASE')
    bundle=Path(bundle)
    report=snapshot(bundle)
    counts={};errors=[];maps=[]
    for row in report[phase]['rows']:
        sample=optional(bundle/'01-preparation'/row['case']/'01-round/data.json',{})
        if not (sample.get('provenance') or {}).get('name'):
            sample=optional(bundle/'01-preparation'/row['case']/'01-round/01-source/01-receive-input/01-input.json',{})
        category=(sample.get('provenance') or {}).get('name','종류 미기록') if phase=='preparation' else row['type']
        cells=[c for c in row['rounds'] if c['status']!='NOT_RUN']
        current=cells[-1] if cells else {'status':'NOT_RUN'}
        status=current['status']
        counts.setdefault(category,Counter())[status]+=1
        source=current.get('source')
        marker=optional(bundle/source,{}) if source else {}
        stage=marker.get('stopped_at') if phase=='preparation' else marker.get('restart')
        number=(stage or '').split('-')[0]
        allowed=[f'{i:02d}' for i in range(1,8 if phase=='preparation' else 5)]
        number=number if number in allowed else None
        maps.append({'case':row['case'],'category':category,'variant':row.get('variant'),
                     'status':status,'round':next((p for p in Path(source or '').parts if p.endswith('-round')),None),
                     'error_stage':number if status in ('FAIL','ERROR') else None,
                     'observed_stage':number,'handler_error':bool(marker.get('recovery',{}).get('handler_error')),
                     'source':source,'reason':current.get('reason','')})
        if status in ('FAIL','ERROR'):
            reason=str(current.get('reason') or '원인 기록 없음')
            clean=re.sub(r'^\w*(?:Error|Exception):\s*','',reason)
            code=re.match(r'[A-Za-z][A-Za-z0-9_]+(?=:|$)',clean)
            errors.append({'case':row['case'],'category':category,'code':code[0] if code else '상세 검사 실패',
                           'reason':reason,'source':current.get('source') or '', 'stage':number or 'UNKNOWN'})
    summary=[{'category':k,'total':sum(v.values()),**{s:v[s] for s in ('PASS','FAIL','NOT_EVALUATED','NOT_RUN')}} for k,v in sorted(counts.items())]
    usage=token_usage(bundle,phase)
    return add_knowledge(bundle, {'run':bundle.name,'phase':phase,'summary':summary,'errors':sorted(errors,key=lambda e:(e['case'],e['category'])),
            'maps':maps,'stage_columns':[f'{i:02d}' for i in range(1,8 if phase=='preparation' else 5)],
            'rounds':report[phase]['rounds'],'usage':usage,'generated_at':usage['generated_at'],'unit':'문항' if phase=='preparation' else '문항×유형'})


def source_signature(bundle, phase):
    import hashlib
    root=Path(bundle)/('01-preparation' if phase=='preparation' else '02-generation')
    pattern='test-*/*-round/run.json' if phase=='preparation' else '0*-round/test-*/*/run.json'
    digest=hashlib.sha256()
    for path in sorted(root.glob(pattern)):
        st=path.stat();digest.update(f'{path.relative_to(root)}:{st.st_size}:{st.st_mtime_ns}'.encode())
    return digest.hexdigest()


def view(bundle, phase):
    if phase not in ('preparation','generation'):raise ValueError('INVALID_REPORT_PHASE')
    path=Path(bundle)/'phase-reports'/phase/'data.json'
    saved=optional(path,{})
    if saved.get('source_signature')==source_signature(bundle,phase):return saved
    return build(bundle,phase)


def workbook(bundle,phase,data=None):
    bundle=Path(bundle).resolve();data=data if data is not None else build(bundle,phase)
    runtime=Path(os.environ.get('FINARCH_NODE_RUNTIME',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node')))
    folder=bundle/'phase-reports'/phase;folder.mkdir(parents=True,exist_ok=True)
    destination=folder/(phase+'-report.xlsx')
    with tempfile.TemporaryDirectory(prefix='finarch-phase-report-') as temp:
        temp=Path(temp);(temp/'node_modules').symlink_to(runtime/'node_modules',target_is_directory=True)
        shutil.copy2(Path(__file__).with_name('phase-workbook.mjs'),temp/'build.mjs')
        payload=temp/'data.json';payload.write_text(json.dumps(data,ensure_ascii=False))
        with (folder/'export.log').open('w') as log:
            subprocess.run([str(runtime/'bin/node'),str(temp/'build.mjs'),str(payload),str(folder)],stdout=log,stderr=subprocess.STDOUT,check=True)
        # The authoring API does not expose documented numeric axis bounds.
        # Preserve native editable charts and set the OOXML value-axis limits.
        corrected=temp/'bounded.xlsx'
        ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
        with zipfile.ZipFile(destination) as source, zipfile.ZipFile(corrected,'w',zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                raw=source.read(info.filename)
                if re.fullmatch(r'xl/(?:drawings/)?charts/chart\d+\.xml',info.filename):
                    tree=ET.fromstring(raw)
                    for axis in tree.findall('.//c:valAx',ns):
                        position=axis.find('c:axPos',ns)
                        if position is None or position.get('val') not in ('b','t'):continue
                        scaling=axis.find('c:scaling',ns)
                        if scaling is None:scaling=ET.SubElement(axis,'{'+ns['c']+'}scaling')
                        for tag,val in [('min',0),('max',max(2050,max((p[0] for s in data['usage']['series'] for p in s['points']),default=0)))]:
                            element=scaling.find('c:'+tag,ns)
                            if element is None:element=ET.SubElement(scaling,'{'+ns['c']+'}'+tag)
                            element.set('val',str(val))
                    raw=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
                target.writestr(info,raw)
        shutil.copy2(corrected,destination)
    data['source_signature']=source_signature(bundle,phase)
    (folder/'data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    (folder/'README.md').write_text(f"# {phase.title()} 결과 리포트\n\n실행 {bundle.name}. 집계 시각 {data['generated_at']}.\n\n{destination.name}의 종류별 요약 → 오류 지도 → 오류 상세 → 단계별 토큰 차트 순으로 읽습니다. 오류는 마지막 실행 차수 상태, 토큰은 모든 차수 실제 호출의 합계입니다. 입력+출력에 캐시·추론을 중복 가산하지 않습니다. 누락된 토큰은 0으로 취급하지 않습니다. 원본 경로는 오류 상세와 data.json에 있습니다. 오류 지도 상단의 통과율은 각 지식 구분의 통과/전체이며 미평가도 분모에 포함합니다. Generation 문항 유형 지도의 주황 탭은 주요 검토 화면이며, 7종 모두 통과한 행은 파란색, 오류 글씨는 빨간색입니다. 토큰 차트는 X축 문제번호, Y축 토큰 사용량입니다.\n\n공통 뷰어의 {phase.title()} 결과 리포트에서 최신 기록을 조회하고 Excel을 다시 생성할 수 있습니다. 모델 호출은 하지 않습니다.\n")
    return destination


def publish(bundle, phase):
    """Scheduler-owned final export. Reporting errors never rewrite production verdicts."""
    write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
    folder=Path(bundle)/'phase-reports'/phase
    try:
        path=workbook(bundle,phase)
        result={'status':'COMPLETED','path':str(path),'phase':phase}
    except Exception as error:
        result={'status':'ERROR','reason':f'{type(error).__name__}: {error}','phase':phase}
    write(folder/'status.json',result)
    return result
