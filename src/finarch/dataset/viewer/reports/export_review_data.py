"""Export reference-format review data from any completed pipeline run."""
import argparse
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
from finarch.dataset.viewer.reports.completion_report import snapshot
TYPES = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['TYPES']).TYPES

NAMES=['ANSWER','IC-VALUE 앞','IC-VALUE 뒤','IC-SOURCE 타입 1','IC-SOURCE 타입 2','IC-RELATION','EA 01','EA 02']


def build(bundle, output=None):
    root=Path(bundle).resolve()
    report=snapshot(root)
    if report['status']!='COMPLETED':
        raise ValueError('GENERATION_NOT_FINISHED')
    latest=read(root/'02-generation/summary.json')['latest']
    selected=read(root/'input-selection.json')['cases']
    prep={r['case']:r for r in report['preparation']['rows']}
    grows={(r['case'],r['type']):r for r in report['generation']['rows']}
    matrix=[];attempts=[];details=[];exclusions=[]
    labels=['ANSWER']+[label for _,_,label in TYPES]
    def actual_count(cells):
        return sum(c['status'] not in ('NOT_RUN','NOT_EVALUATED') and not c.get('carried') for c in cells)
    for number,name in enumerate(selected,1):
        case=root/'01-preparation'/name
        result=read(case/'run.json')
        eligible=name in latest
        matrix.append([number,name,'ELIGIBLE' if eligible else 'EXCLUDED',result['status']]+[
            latest[name][str(i)]['status'] if eligible else 'EXCLUDED' for i in range(7)])
        attempts.append([actual_count(prep[name]['rounds'])]+[
            actual_count(grows[(name,label)]['rounds']) if eligible else 0 for _,_,label in TYPES])
        if not eligible:
            reason=result.get('reason','')
            stage=result.get('stopped_at') or ('02 문장 검사' if 'SOURCE_REVISION' in reason or 'ORIGINAL_AUDIT' in reason else '04 그래프' if 'GRAPH_' in reason or 'FACT_' in reason else '03 계산·정답 검증')
            exclusions.append([number,name,stage,reason,'원문·POT·검사 근거를 함께 검토합니다. 추가 실행은 하지 않았습니다.'])
    for index,(folder,axis,label) in enumerate(TYPES):
        for number,name in enumerate(selected,1):
            if name not in latest:continue
            item=latest[name][str(index)]
            if item['status']=='PASS':continue
            case=root/'01-preparation'/name
            sample=read(case/'data.json')
            request=item.get('generation_request',{})
            original=request.get('context',sample['context'])
            patches=item.get('generation_response',{}).get('patches',[])
            generated=item.get('observation',{}).get('context')
            kind='실제 생성문' if generated is not None else '생성문 미확인'
            excerpt='생성·검사 원기록을 확인하십시오.'
            if generated is None and patches:
                generated=original
                try:
                    end=len(original)
                    for p in sorted(patches,key=lambda p:p['start'],reverse=True):
                        a,b=p['start'],p['end']
                        if not 0<=a<=b<=end or original[a:b]!=p['before']:raise ValueError('INVALID_PATCH')
                        generated=generated[:a]+p['text']+generated[b:];end=a
                    kind='실패 응답의 진단용 적용본'
                except (ValueError,KeyError,TypeError):
                    generated=None
            if patches:
                p=patches[0]
                if isinstance(p.get('start'),int) and isinstance(p.get('end'),int):
                    excerpt=original[max(0,p['start']-70):p['start']]+'【'+str(p.get('text',''))+'】'+original[p['end']:p['end']+70]
            if generated is None:generated='적용된 생성문이 없습니다. 요청·원응답·실패 이유를 확인하십시오.'
            reason=item.get('reason','')
            stage='03 의미 검사' if item.get('audit') else item.get('restart','실행 기록 확인')
            category='의미 검사' if item.get('audit') else '생성·편집 검사' if stage=='02-generate-text' else '그래프 계획'
            path=root/item['path']
            def existing(*paths):
                return next((str(p) for p in paths if p.is_file()),'')
            details.append(dict(number=number,case=name,type=NAMES[index+1],label=label,
                rounds=[c['status'] for c in grows[(name,label)]['rounds']],stage=stage,category=category,
                reason=reason,cause=reason,fix='기록된 실패 이유와 해당 요청·응답을 대조해 검토합니다.',
                viewer=f'http://127.0.0.1:8893/?run={root.name}&case={name}&round={item["round"]}&variant={folder}',
                request_path=existing(path/'02-generate-text/01-input.json'),
                response_path=existing(path/'02-generate-text/01-request/03-result.json',path/'02-generate-text/02-place-paired-sentence.json'),
                verdict_path=existing(path/'03-validation/03-result.json',path/stage/'failure.json',path/'run.json'),
                instructions='실제 호출 폴더의 저장 프롬프트를 참조합니다. 현재 지침을 과거 적용 지침으로 간주하지 않습니다.',
                text_kind=kind,excerpt=excerpt,original=original,generated=generated,question=request.get('question',sample['question']),
                patches=patches,diffs=[{'start':b1,'end':b2} for tag,a1,a2,b1,b2 in SequenceMatcher(None,original,generated).get_opcodes() if tag!='equal'],
                source_path=str(case/'data.json')))
    data=dict(run=root.name,names=NAMES,labels=labels,matrix=matrix,attempts=attempts,details=details,exclusions=exclusions,
              groups=dict(Counter(d['category'] for d in details)),round_counts=[r['counts'] for r in report['generation']['rounds']],
              prep_rounds=report['preparation']['rounds'])
    target=Path(output) if output else root/'failure-review/review-data.json'
    write(target,data)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--output')
    args=parser.parse_args();print(build(args.run,args.output))
