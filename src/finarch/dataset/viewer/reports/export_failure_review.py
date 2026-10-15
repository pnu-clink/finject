"""Extract recorded failures for a workbook without changing production records."""
import json
import difflib
from pathlib import Path
from collections import Counter
from finarch.dataset.viewer.reports.comparison_report import outcomes, read
LABELS = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['LABELS']).LABELS
generation_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['generation_root']).generation_root
audit_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['audit_root']).audit_root
candidate_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['candidate_root']).candidate_root
resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read

ROOT=Path('reports/run/20260910-012').resolve()
DEST=ROOT/'failure-review'
NAMES=['ANSWER','IC-VALUE 앞','IC-VALUE 뒤','IC-SOURCE 타입 1','IC-SOURCE 타입 2','IC-RELATION','EA 01 (EA_01)','EA 02 (EA_02)']

def load(p):
    return read(resolve_read(p)) or {}

def locate(name,label,kind):
    for rn in ('03-round','02-round','01-round'):
        case=ROOT/rn/name
        if not case.exists():continue
        base=generation_root(label) if kind=='generation' else audit_root(label)
        stage=case/base/rn
        if (stage/'01-receive-input/01-input.json').exists():return stage
        pointer=load(case/candidate_root(label)/('latest-realization.json' if kind=='generation' else 'latest-audit.json'))
        if pointer:return case/pointer['stage']
    return None

def classify(name,label,reason,request,patches):
    if 'INSERTION_NEEDS_SEPARATOR' in reason:
        return ('삽입 경계 공백','편집 검사에서 삽입 끝과 다음 단어 사이 구분자가 없다고 판정했습니다. 아래 경계 발췌에서 실제 접합부를 확인합니다.','삽입 전후 문맥과 공백을 함께 전달하고, 응답의 시작·끝 공백을 보존합니다. 타입 2는 대상 수치 지침 불일치도 함께 수정해야 합니다.')
    if 'UNPLANNED_NUMERIC_CONTENT' in reason:
        return ('기존 연도 반복을 숫자 오류로 판정','삭제 대상 318,928은 제거됐습니다. 응답에서 기존 연도 2018·2019를 한 번씩 더 적어, 숫자 출현 횟수까지 동일해야 하는 Counter 검사에 실패했습니다. 새 수치 추가와 기존 연도 반복을 구분해야 합니다.','수치·연도 의미 보존과 단순 출현 횟수 조건을 분리해 검토합니다. 현재 규칙을 유지한다면 생성 지침에 기존 연도 중복을 피하도록 명시합니다.')
    if label.startswith('IC_SOURCE'):
        return ('출처 대상 주장 불일치','의미 검사는 출처가 추가 값 대신 원래 값에 붙었다고 기록했습니다. 생성 요청에는 뒤쪽 추가 주장과 원래 수치 지정이 함께 있어 지침 충돌을 확인해야 합니다.','출처 대상의 문장·수치·위치를 IC-VALUE 실제 결과에서 일치시킵니다. assigned claim과 selected quantity를 같은 주장으로 맞춘 뒤 새로 생성합니다.')
    if label=='ANSWER':
        return ('원문·질문 명확성','원본 ANSWER에 대한 감사 실패입니다. 생성 문장의 결함으로 집계하면 안 됩니다.','원천 표의 두 매출 항목과 질문의 지칭 대상을 대조하고 원문 품질 문제를 별도로 판단합니다. 정답에 맞춘 임의 수정은 하지 않습니다.')
    if name=='test-0070':
        return ('삭제 뒤 문장 단절','삭제 후 문장 연결과 금융 관계 표현이 불완전하다는 감사 기록입니다.','삭제 대상 수치는 복원하지 않으면서 남은 문장의 문법과 금융 관계를 보존하도록 생성 지침을 보완합니다.')
    if name=='test-0083':
        return ('삭제 뒤 표기 잔여물·판정 검토','감사 이유에는 남은 표기와 삭제된 수치의 이용 가능성 판단이 섞여 있습니다.','빈 수치 자리에 남은 $() 등을 정리하고, 연도 표기와 삭제된 금액을 구분해 감사 판정을 재검토합니다.')
    return ('감사 판정·이유 재검토','삭제 수치가 없다는 설명 또는 통과해야 한다는 설명과 FAIL이 함께 기록돼 있습니다. 생성 오류로 단정하지 않습니다.','원문·생성문·질문에서 삭제 수치의 잔존 여부를 확인하고, 수치를 묻는 질문 자체를 수치 잔존으로 오인했는지 검토합니다. 기존 판정은 보존합니다.')

def main():
    DEST.mkdir(exist_ok=True)
    rounds=[outcomes(ROOT,f'{n:02d}-round') for n in (1,2,3)]
    final=rounds[-1]; details=[]; matrix=[]; exclusions=[]
    for n in range(1,101):
        name=f'test-{n:04d}'; pipe=final.get((name,'PIPELINE'))
        statuses=[final.get((name,l),{}).get('status','EXCLUDED' if pipe else 'NO_CONDITION') for l in LABELS]
        matrix.append([n,name,'EXCLUDED' if pipe else 'ELIGIBLE',*statuses])
        if pipe:
            reason=pipe['reason']
            action=('기존 제외 결정을 유지하고 정답 불일치 근거를 별도 검토합니다.' if 'GOLD_MISMATCH' in reason else '원본 코드·실패 로그에서 해당 예외와 입력 값을 확인하고 생성 오류와 실행기 지원 한계를 구분합니다.')
            exclusions.append([n,name,pipe['stage'],reason,action])
        for label in LABELS:
            v=final.get((name,label),{})
            if v.get('status')!='FAIL':continue
            gs=locate(name,label,'generation'); au=locate(name,label,'audit')
            source=load(ROOT/'01-round'/name/'00-data-preparation/01-select-input/01-input.json')
            request=load(gs/'01-receive-input/01-input.json') if gs else {}
            response=load(gs/'05-validate-response/02-handler-response.json') if gs else {}
            result=load(gs/'06-apply-result/04-result.json') if gs else {}
            patches=response.get('data',{}).get('patches',result.get('patches',[]))
            base=request.get('context',source.get('context',''))
            generated=result.get('preview_context')
            diagnostic=False
            if generated is None:
                generated=base
                for p in sorted(patches,key=lambda p:p['start'],reverse=True):
                    generated=generated[:p['start']]+p['text']+generated[p['end']:]
                diagnostic=bool(patches)
            excerpts=[]
            for p in patches:
                left=base[max(0,p['start']-110):p['start']]; right=base[p['end']:p['end']+110]
                excerpts.append(left+'【'+p['text']+'】'+right)
            if not excerpts:
                excerpts=[v['reason']]
            diffs=[]
            for tag,a,b,c,d in difflib.SequenceMatcher(None,source.get('context',''),generated,autojunk=False).get_opcodes():
                if tag!='equal':diffs.append({'before':source.get('context','')[a:b],'after':generated[c:d],'start':c,'end':d})
            category,cause,fix=classify(name,label,v['reason'],request,patches)
            evidence=resolve_read(gs/'03-result/failure.json') if v['stage']=='01-generate-text' else resolve_read(au/'03-result.json')
            assert evidence.is_file(),str(evidence)
            details.append({'case':name,'number':n,'label':label,'type':NAMES[list(LABELS).index(label)],'stage':v['stage'],
                'rounds':[r.get((name,label),{}).get('status','NOT_EVALUATED') for r in rounds],
                'reason':v['reason'],'category':category,'cause':cause,'fix':fix,'original':source.get('context',''),
                'question':source.get('question',''),'generated':generated,'excerpt':'\n\n'.join(excerpts),'patches':patches,'diffs':diffs,
                'instructions':'\n'.join(request.get('instructions',[])),'slots':request.get('edit_slots',[]),
                'text_kind':'실패 원응답을 그대로 적용한 진단용 본문' if diagnostic else ('원문 (ANSWER)' if label=='ANSWER' else '저장된 실제 생성 본문'),
                'source_path':str(ROOT/'01-round'/name/'00-data-preparation/01-select-input/01-input.json'),
                'request_path':str(gs/'03-LLM-call/01-request.json') if gs else '',
                'response_path':str(gs/'04-receive-response/01-raw-response.json') if gs else '',
                'verdict_path':str(evidence),
                'viewer':f'http://127.0.0.1:8893/?run={ROOT.name}&round=03-round&case={name}&variant={label}&tab=dtt'})
    details.sort(key=lambda d:(list(LABELS).index(d['label']),d['number']))
    counts={l:dict(Counter(v['status'] for (c,k),v in final.items() if k==l)) for l in LABELS}
    payload={'run':ROOT.name,'labels':list(LABELS),'names':NAMES,'matrix':matrix,'details':details,'exclusions':exclusions,'counts':counts,
        'round_counts':[dict(Counter(v['status'] for v in r.values())) for r in rounds],
        'groups':dict(Counter(d['category'] for d in details)),
        'scope':'Final recorded outcomes after up to three rounds; earlier passes are retained. FAIL is the recorded validator result, not an independent human verdict.'}
    assert len(matrix)==100 and len(details)==35 and len(exclusions)==26
    (DEST/'review-data.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    print(json.dumps({'counts':counts,'groups':payload['groups'],'failures':len(details),'excluded':len(exclusions)},ensure_ascii=False))

if __name__=='__main__':main()
