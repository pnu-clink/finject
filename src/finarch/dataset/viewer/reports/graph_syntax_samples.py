"""Generate seven isolated Python/graph checks in the common viewer, without LLMs."""
import argparse
import hashlib
import json
from pathlib import Path
from finarch.dataset.shared.calculation.python_graph import compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute


SAMPLES = [
 ('for','for 반복문','입력 목록의 각 항목을 회차별로 펼쳐 누적값을 연결합니다.',
  (10,20,30),'Find the sum of the three supplied amounts.',
  'x=fact("x")\ny=fact("y")\nz=fact("z")\ntotal=0\nfor amount in [x,y,z]:\n    total += amount\nanswer=total'),
 ('while','while 반복문','각 반복의 조건·잔액·지급액을 펼치고 종료 조건도 기록합니다.',
  (30,10),'Pay down the balance x in installments y; find the total paid.',
  'x=fact("x")\ny=fact("y")\nremaining=x\ntotal=0\nwhile remaining>0:\n    paid=min(remaining,y)\n    total+=paid\n    remaining-=paid\nanswer=total'),
 ('if','블록형 if/else','조건과 선택 경로를 보존합니다. 실행되지 않은 경로는 계산 완료로 표시하지 않습니다.',
  (100,80),'Find the amount by which x exceeds y; return zero if it does not.',
  'x=fact("x")\ny=fact("y")\nif x>y:\n    excess=x-y\nelse:\n    excess=0\nanswer=excess'),
 ('comprehension','리스트·제너레이터 축약식','항목별 계산 후 합산합니다. 집합 반복과 변경 가능한 컨테이너 조작은 범위 밖입니다.',
  (10,20,30),'Find the sum of squared supplied amounts.',
  'x=fact("x")\ny=fact("y")\nz=fact("z")\nsquares=[value*value for value in [x,y,z]]\nanswer=sum(value for value in squares)'),
 ('module','math 외 모듈','허용 목록의 statistics.mean을 명시적 입력 연산으로 표현합니다. SciPy·NumPy 전체 지원을 뜻하지 않습니다.',
  (10,20,30),'Find the arithmetic mean of the three supplied amounts.',
  'from statistics import mean\nx=fact("x")\ny=fact("y")\nz=fact("z")\nanswer=mean([x,y,z])'),
 ('aggregate','수치·집계 호출','정렬 비교와 순번별 가중합, 항목 수 및 나눗셈을 연결합니다.',
  (10,20,30),'Sort the amounts ascending, multiply by ranks 1, 2, 3, and divide their sum by the item count.',
  'x=fact("x")\ny=fact("y")\nz=fact("z")\nordered=sorted([x,y,z])\nweighted=sum(value*(index+1) for index,value in enumerate(ordered))\nanswer=weighted/len(ordered)'),
 ('function','추가·중첩 함수','호출별 인자→내부 연산→반환값을 펼칩니다. 재귀·부작용은 허용하지 않습니다.',
  (10,),'For the supplied amount, sum twice and three times the amount.',
  'x=fact("x")\ndef outer(amount):\n    def scale(factor):\n        return amount*factor\n    return scale(2)+scale(3)\nanswer=outer(x)'),
]


def build(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    samples=[]
    for tag,title,policy,values,question,code in SAMPLES:
        names=['x','y','z'][:len(values)]
        context='; '.join(f'{name} = {value}' for name,value in zip(names,values))
        facts={}
        for name,value in zip(names,values):
            start=context.index(f'{name} = ')+len(name)+3
            facts[name]={'text':str(value),'value':str(value),'span':[start,start+len(str(value))],'unit':None}
        program={'code':code,'question':question,'context':context,'facts':facts}
        root=output/tag;root.mkdir()
        def save(name,data):(root/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))
        save('program.json',program)
        actual=execute(program,save=save)
        if actual.status!='PASS':raise ValueError(tag+':'+actual.reason)
        graph,value,_=compile_graph(program)
        computed={n['id']:n['computed'] for n in graph['nodes']}
        matched=str(value)==actual.data['exact_value'] and all(computed[key]==actual.data['trace'][name] for name,key in graph['variables'].items())
        save('execution.json',actual.data);save('graph.json',graph)
        check={'status':'PASS' if matched else 'FAIL','python':actual.data['exact_value'],'graph':str(value),
               'global_variables_compared':len(graph['variables']),'graph_nodes':len(graph['nodes']),
               'control_links':len(graph.get('control_flow',{}).get('links',[]))}
        save('comparison.json',check)
        if not matched:raise ValueError(tag+':PYTHON_GRAPH_MISMATCH')
        samples.append({'id':tag,'title':title,'policy':policy,'program':program,'graph':graph,'check':check})
    report={'format':'graph-syntax-samples-v1','run_id':output.name,'model_calls':0,'samples':samples,
            'status':'PASS','scope':'Seven illustrative engineering fixtures, not FinanceReasoning semantic validation'}
    (output/'graph-syntax-samples.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (output/'summary.json').write_text(json.dumps({'status':'LOCAL_CHECK_COMPLETE','families':7,'model_calls':0}))
    rows='\n'.join(f"|{s['title']}|{s['check']['python']}|{s['check']['graph']}|{s['check']['status']}|" for s in samples)
    template=Path(__file__).with_name('graph-syntax-samples-readme.md').read_text()
    (output/'README.md').write_text(template.replace('{rows}',rows))
    (output/'checks.jsonl').write_text(''.join(json.dumps({'sample':s['id'],**s['check']})+'\n' for s in samples))
    return report


def view(bundle):
    bundle=Path(bundle);report=json.loads((bundle/'graph-syntax-samples.json').read_text())
    data={'format':'fin-arch-viewer-v1','runs':[], 'batch':{'name':bundle.name,'rounds':[], 'round':None,
          'graph_syntax_samples':report,'readme':(bundle/'README.md').read_text()}}
    data['revision']=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(build(args.output)['status'])
