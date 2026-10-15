"""Stage the authorized Korean evidence-centered manuscript from frozen saved results.

Reads the current review snapshot and the 20261008 response snapshot. It does not
change evaluation data or invoke models. --apply publishes the reviewed staged
Korean sections to the existing Draft, editor source, and compressed manuscript.
"""
from __future__ import annotations
import argparse
import base64
import collections
import copy
import datetime
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup
from finarch.documentation.draft_editor import DraftRepository, EMBEDDED

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'reports/run/20261003-paper-revision-draft'
WORK = ROOT / 'paper/asset/.build/v2-evidence-draft'
BUILD = WORK / 'build'
ASSETS = ROOT / 'paper/asset/figures/v2'
MODELS = ['Luna', 'Haiku', 'Qwen3-8B', 'Qwen3-14B', 'Qwen3.8-27B']
SUMMARY = ROOT / 'reports/analysis/20261008-finject-1354/summary.json'
RESPONSES = SUMMARY.with_name('responses.jsonl')
SNAPSHOT = BUILD / 'paper-review-before.json'

def h(text): return html.escape(str(text))
def p(text, id=None): return f'<p'+(f' id="{id}"' if id else '')+f'>{text}</p>'
def ref(id, label): return f'<a href="#{id}">{label}</a>'
def cite(id, name): return ref('ref-'+id, '('+name+')')
def section_ref(id, label): return ref(id, label)
def table(id, caption, headers, rows, wide=False):
    return f'<table id="{id}" data-table-number="0" data-caption-position="bottom" data-layout="{"two-column" if wide else "one-column"}" style="width:100%;min-width:0;table-layout:auto;"><caption>Table 0: {caption}</caption><thead><tr>'+''.join('<th>'+str(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
def img(id, name, caption, wide=False):
    path = WORK / 'output' / (name+'.png')
    src='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    return f'<figure id="{id}" data-figure-number="0" data-layout="{"two-column" if wide else "one-column"}" data-figure-file="paper/asset/figures/v2/{name}.pdf" data-pdf-placement="top"><img src="{src}" alt="{h(caption)}"/><figcaption>Figure 0: {caption}</figcaption></figure>'
def math(tex, id=None):
    # MathML carries both a native accessible rendering and the exact TeX source.
    import subprocess
    result=subprocess.run(['pandoc','-f','markdown','-t','html5','--mathml'],input='$$\n'+tex+'\n$$',text=True,capture_output=True,check=True).stdout
    return '<div class="equation"'+(f' id="{id}"' if id else '')+'>'+result+'</div>'

def source_pairs():
    types=['IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY']
    responses={}
    with RESPONSES.open() as file:
        for line in file:
            r=json.loads(line)
            if r.get('model_label') not in MODELS or r['variant'] not in types: continue
            key=(r['model_label'],r['prompt_condition'],r['reasoning'],r['final_id'],r['variant'])
            if key in responses: raise ValueError('Duplicate response key: '+str(key))
            if r['target_status']!='VALID': cat='X'
            elif r['action']=='A': cat='A'
            elif r['action']=='N' and r['original_reference_match'] is True: cat='M'
            elif r['action']=='N' and r['original_reference_match'] is False: cat='W'
            else: cat='X'
            responses[key]=cat
    ids=[f'id-{i:04}' for i in range(1,1355)]
    out=[]
    for model in MODELS:
        for g in ['unguided','guided']:
            for r in ['off','on']:
                for pair,(before,after) in enumerate([(types[0],types[2]),(types[1],types[3])],1):
                    counts=collections.Counter()
                    excluded=collections.Counter()
                    for fid in ids:
                        a=responses.get((model,g,r,fid,before),'X');b=responses.get((model,g,r,fid,after),'X')
                        if 'X' in (a,b): excluded[f'{a}->{b}']+=1
                        else: counts[a+'->'+b]+=1
                    n=sum(counts.values());assert n+sum(excluded.values())==1354
                    cb={c:sum(v for k,v in counts.items() if k.startswith(c)) for c in 'MWA'}
                    ca={c:sum(v for k,v in counts.items() if k.endswith(c)) for c in 'MWA'}
                    out.append(dict(model=model,G=g,R=r,pair=pair,n=n,planned=1354,excluded=dict(excluded),before=cb,after=ca,transitions=dict(counts),delta_pp={c:100*(ca[c]-cb[c])/n if n else None for c in 'MWA'}))
    return out

def build():
    sections=json.loads(SNAPSHOT.read_text()); previous=copy.deepcopy(sections)
    by={s['id']:s for s in sections}
    assets={}
    for s in sections:
        doc=BeautifulSoup(s['kohtml'],'html.parser')
        for t in doc.find_all(['figure','table'],id=True): assets[t['id']]=str(t)
    summary=json.loads(SUMMARY.read_text())
    q={(r['model'],r['G'],r['R']):r for r in summary['rq1'] if r['model'] in MODELS}
    pairs=source_pairs()
    evidence=dict(source=str(RESPONSES.relative_to(ROOT)),sha256=hashlib.sha256(RESPONSES.read_bytes()).hexdigest(),new_model_calls=0,scope='paired valid output categories; original_reference_match reused unchanged',pairs=pairs)
    (BUILD/'source-attribution-results.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    def put(sid,body,title=None):
        s=by[sid];s['kohtml']=body;s['oldko']='';s['state']='revised'
        if title is not None:s['ko']=title
    def asset(id):return assets[id]
    gr='G<sup>+</sup>R<sup>+</sup>'
    gm='G<sup>−</sup>'
    a3ref=ref('fig:revision-2','Figure 3')
    tab3=ref('tab:v2-support','Table 3')
    tab4=ref('tab:v2-reasoning','Table 4')
    tab5=ref('tab:v2-guidance','Table 5')
    tab6=ref('tab:v2-source','Table 6')
    app32=section_ref('s11-pipeline-2','Appendix 3.2')
    app42=section_ref('s11-nasu','Appendix 4.2')
    app44=section_ref('s11-pipeline-4','Appendix 4.4')
    put('abstract',p('금융에서 모델의 수치 답변과 기권은 모두 주어진 근거로 정당화되어야 한다. 모델이 이유를 제시하더라도 필요한 근거가 없거나 설명과 맞지 않으면 응답을 신뢰하기 어렵다. 우리는 근거 조건을 통제하여 답변과 기권을 평가하는 FInject와 재사용 가능한 제작·평가·분석 방법을 제안한다. 독립적인 Python 풀이와 계산 그래프로 근거의 계산 영향을 추적하고, 충돌 추가·출처 표기·근거 제거를 적용한 일곱 변형을 생성했다. 사람 검토를 거친 최종 데이터는 원본 1,354개와 변형 9,478개이며, 선정 전 후보에 대한 두 평가자의 일치율은 98.98%, Cohen의 κ는 0.619였다. 다섯 모델의 이유와 인용 근거를 LLM으로 판정한 결과, 이유·근거의 제출만으로 응답의 근거 지원이 보장되지는 않았다. Reasoning과 기권 안내는 근거 있는 응답을 늘렸지만 미지원 응답은 남았다. 또한 출처를 붙이는 주장에 따라 원본 정답과 일치하거나 불일치하는 수치 답변의 비중이 달라졌다. FInject는 답변 여부나 수치 정답을 넘어, 근거가 설명과 최종 판단을 뒷받침하는지 평가할 기반을 제공한다.'))
    intro=img('fig:abstention-intro','Figure1-v2-evidence','같은 질문에서 근거가 정당화하는 numeric-answer와 abstention. 최종 문항 id-0217의 표를 요약한 설명용 응답이며, 실제 모델 출력은 아니다. 원본에서는 34 + 11 = 45가 성립하지만, Apple의 2017년 값을 제거하면 남은 문맥으로 합계를 확정할 수 없다. 원문과 삭제 위치는 '+app32+'에 제시한다.')
    intro+=p('금융 의사결정에 쓰이는 대규모 언어 모델(LLM)은 답뿐 아니라 그 답을 정당화하는 근거를 제시해야 한다. 모델의 금융 지식과 계산 능력은 보고서를 해석하는 데 필요하지만, 특정 기업·기간의 값을 문맥의 확인 없이 대신할 수는 없다. 필요한 값이 없거나 근거끼리 충돌하면, 모델은 그 상태를 이유로 설명하고 기권할 수 있어야 한다 '+cite('realfin','Dai et al., 2026')+'.')
    intro+=p('이유를 설명한다고 해서 응답이 타당해지는 것은 아니다. LLM은 틀린 답을 그럴듯한 설명으로 정당화할 수 있으며, 제시한 설명이 실제 판단 과정을 반영하지 않을 수도 있다 '+cite('unfaithful-cot','Turpin et al., 2023')+'. 따라서 수치 답변인 <strong>numeric-answer</strong>와 기권인 <strong>abstention</strong> 모두에서, 문맥의 근거(<strong>evidence</strong>)가 모델의 설명(<strong>reason</strong>)과 최종 응답을 뒷받침하는지 확인해야 한다. 여기서 reason은 모델이 제시한 설명을 뜻하며 내부 추론 자체를 뜻하지 않는다.')
    intro+=p('예를 들어 두 기업의 매출 비중이 34%와 11%라면 합계 45%를 근거로 정당화할 수 있다. 필수값 하나를 지우고 남은 문맥으로도 복원할 수 없다면 같은 질문에 대한 기권을 정당화할 수 있다('+ref('fig:abstention-intro','Figure 1')+'). 반대로 누락값을 가정해 수치로 답하거나, 복원 가능한 근거가 있는데도 없다고 설명하면 이유를 갖춘 응답이라도 근거 지원에 실패한다.')
    intro+=p('기존 금융 QA는 문서 기반 수치 계산을 평가하고 '+cite('finqa','Chen et al., 2021')+' '+cite('tatqa','Zhu et al., 2021')+', 최근 연구는 필수 조건 누락과 기권 이유도 다룬다 '+cite('realfin','Dai et al., 2026')+'. FInject는 같은 질문의 계산 근거를 통제하여 원본과 일곱 변형을 연결하고, 모델이 제시한 이유·인용 근거와 최종 응답의 정합성을 함께 평가한다.')
    intro+=p('FInject는 FinanceReasoning과 TAT-QA에서 선정한 원본 1,354개와 변형 9,478개로 구성된다. 독립적인 Python 풀이와 계산 그래프는 변경할 근거와 그 계산 영향을 추적하며, 사람 검토자가 변형의 정합성을 검사한다. 입력 어댑터를 통해 다른 수치 QA에도 제작 절차를 재사용할 수 있다. 전체 과정은 '+ref('fig:pipeline-full','Figure A1')+'에 제시한다.')
    intro+=p('우리는 근거 있는 응답의 비중, 기권 안내·reasoning에 따른 변화, 출처 표기에 따른 응답 변화를 분석한다. 실험에서는 이유와 근거를 요구해도 미지원 응답이 남았으며, 수치 내용을 유지한 채 출처만 추가해도 답변과 기권의 분포가 달라졌다. 이는 응답의 결과와 함께 그 결과를 정당화하는 근거를 평가할 필요를 보여준다.')
    put('s1',intro)
    put('s2',p('금융 수치 QA의 제작 방식과 근거·기권 평가를 비교한다. 세부 비교표와 용어는 '+section_ref('s11-related','Appendix 2')+'에 제시한다.'))
    put('s2-1',p('FinQA는 금융 보고서의 질문과 풀이 프로그램을 제공하고 '+cite('finqa','Chen et al., 2021')+', TAT-QA는 표와 서술문을 결합한 수치 추론을 다룬다 '+cite('tatqa','Zhu et al., 2021')+'. FinanceReasoning은 금융 함수와 Python 풀이를 포함하고 '+cite('finance_reasoning','Tang et al., 2025')+', FinChain은 실행 가능한 계산 단계로 풀이를 검증한다 '+cite('finchain','Xie et al., 2026')+'. 이러한 자료는 수치 정답과 계산을 확인할 기반을 제공한다.')+p('FInject는 계산에 필요한 근거를 추적하여 같은 질문에 충돌·출처·누락 조건을 적용한다. 검증한 원본과 변형, 계산 영향과 변경 위치를 연결하므로, 근거 조건이 달라졌을 때 모델의 수치 답변과 기권을 비교할 수 있다('+ref('table-s11-full-tables-1','Table A1')+').'))
    put('s2-2',p('RealFin은 금융 문항에서 누락된 필수 조건의 식별과 부당한 답변의 거부를 평가한다 '+cite('realfin','Dai et al., 2026')+'. RefusalBench는 기권 탐지와 기권 사유 범주를 구분하며 '+cite('refusalbench','Muhamed et al., 2026')+', AgentAbstain은 수행과 기권이 필요한 에이전트 상황을 비교한다 '+cite('agentabstain','Liu et al., 2026')+'. 비금융 QA에서도 지식 충돌과 근거 부족에 대한 연구가 활발하다('+ref('table-s11-comparisons-2','Table A4')+').')+p('따라서 이유나 근거를 요구하는 것 자체가 FInject의 차별점은 아니다. FInject는 수치 계산에 연결된 근거를 통제하고, 인용한 근거와 계산·설명이 최종 numeric-answer 또는 abstention을 뒷받침하는지 판정한다. 이어 같은 문항의 응답을 연결해 설정과 출처 표기에 따른 차이를 분석한다('+ref('table-s11-full-tables-2','Table A2')+').'))
    put('s3',p('금융 계산은 같은 값을 여러 단계에서 사용하므로, 입력 근거의 변경이 최종 답에 미치는 영향을 추적해야 한다. 우리는 '+ref('fig:revision-1','Figure 2')+'의 과정으로 원본을 준비하고 변형을 생성·검증한다.')+p('<strong>Notation.</strong> <i>Q</i>는 질문, <i>C</i>는 원본 문맥이다. <i>C</i><sub>0</sub> = <i>C</i>이며, <i>C</i><sub>1</sub>, …, <i>C</i><sub>7</sub>은 '+a3ref+'에 정의한 일곱 변형 문맥이다. <i>Ans</i>는 원천 데이터셋이 제공한 원본의 수치 정답으로, 모델이 반환한 <code>answer</code>와 구분한다. 모든 변형은 같은 <i>Q</i>를 사용한다.','notation-common'))
    put('s3-1',p('FinanceReasoning '+cite('finance_reasoning','Tang et al., 2025')+'과 TAT-QA '+cite('tatqa','Zhu et al., 2021')+'에서 수치 정답을 제공하는 문항을 선정하고 중복을 제거한다. 입력 어댑터는 각 문항을 '+ref('notation-common','Notation')+'의 질문·문맥·원천 정답으로 맞춘다.')+p('<strong>독립 풀이와 계산 그래프.</strong> LLM은 정답을 보지 않고 질문과 문맥으로 Python 풀이를 작성한다. 실행값을 요구 단위·정밀도에 맞춰 원천 정답과 대조하고, 입력값·중간값·연산의 의존 관계를 방향성 비순환 그래프(DAG)로 기록한다. 그래프는 수치의 근거 위치와 다음 계산으로 전달되는 값을 연결한다. LLM과 사람은 이 연결을 이용해 변경 대상과 계산 영향을 검사한다('+section_ref('s11-pipeline-1','Appendix 3.1')+').')+asset('fig:revision-1'))
    put('s3-2',p('원본마다 '+a3ref+'의 일곱 문맥을 만든다. <strong>IC-v</strong>는 원본 주장을 유지한 채 같은 충돌 수치를 앞(f) 또는 뒤(b)에 추가한다. <strong>IC-s1</strong>은 IC-v,f의 원본 주장에, <strong>IC-s2</strong>는 IC-v,b의 추가 주장에 출처를 붙이며, 부모의 수치와 배치를 유지한다. <strong>IC-r</strong>는 명시값과 충돌하는 관계식을 추가한다. <strong>ER1·ER2</strong>는 서로 다른 필수 입력 근거를 원본에서 각각 삭제한다.')+img('fig:revision-2','Figure3-v2-seven-variants','같은 질문에 적용하는 일곱 근거 변형. 원본 id-0217의 표와 실제 변경을 문장으로 요약했다. 초록은 충돌 추가, 분홍은 출처 표기, 취소선은 삭제를 나타낸다. IC-s1과 IC-s2의 출처 문구는 축약했으며 전체 원문과 저장 유형의 대응은 '+app32+'에 제시한다.',True)+p('충돌 수치·관계식을 적용한 답이 원본과 달라지는지 실행으로 확인한 뒤, LLM이 변경을 문맥에 표현한다. ER은 삭제 후 남은 근거로 답을 복원할 가능성도 보존한다. 변경 위치와 부모 관계는 '+app32+'에 기록한다.'))
    put('s3-3',p('<strong>계산·문맥 검사.</strong> Python 실행과 그래프를 대조하고, 생성 문맥이 계획한 충돌·삭제를 구현하면서 질문과 비변경 정보를 유지하는지 검사한다. 항목·기간·단위가 일치하는지도 확인한다.')+p('<strong>IC.</strong> 양립할 수 없는 두 주장으로 하나의 수치 답을 정당화할 수 없는 경우를 <code>CONFLICT</code>로 정의한다. 출처 표기의 추가만으로 충돌값 자체가 사라지지는 않는다.')+p('<strong>ER.</strong> 삭제 후에도 남은 근거로 답을 복원할 수 있는지 별도로 검토한다. 제작에 사용한 풀이가 중단되었다는 사실만으로 문항 전체를 답변 불가능으로 판정하지 않는다. 역산 검토의 범위와 미확정 항목은 '+section_ref('s11-validation','Appendix 3.3')+'에 제시한다.'))
    put('s3-4',p('두 검토자는 검사 도구에서 원본·변형 문맥, 변경 위치와 계산 그래프를 대조해 의도한 변형의 구현과 추가 오류 여부를 판정한다. 선정 전 후보 변형의 일치율은 <strong>98.98%</strong>, 통합 Cohen의 <strong>κ = 0.619</strong>였다. 승인 편중으로 우연 일치율은 97.31%였으며 불일치 111건 중 96건은 IC-r에서 발생했다. 두 검토자가 일곱 변형을 모두 승인한 문항군만 선정하여 원본 <strong>1,354개</strong>와 변형 <strong>9,478개</strong>를 구성했다. 검사 도구와 판정 집계는 '+section_ref('s11-annotation','Appendix 3.4')+'에 제시한다.'))
    put('s4',p('우리는 모델이 제시한 이유와 인용 근거가 최종 응답을 뒷받침하는지 평가한다. 응답 수집, 근거 지원 판정, 대응 응답의 비교를 분리하며, 수치 정답 일치만으로 근거 지원을 확정하지 않는다.'))
    fields=table('table-s4-1-1','TargetOutput의 필드. 실제 저장 필드와 분류값의 대응은 '+section_ref('s11-pipeline-3','Appendix 4.1')+'.',['필드','의미'],[['<code>answer</code>','모델이 반환한 수치 답 또는 기권'],['<code>classification</code>','모델이 반환한 상황·기권 사유 분류'],['<code>reason</code>','모델이 제시한 설명'],['<code>evidence</code>','설명에 연결한 문맥의 인용 근거']])
    put('s4-1',p('<strong>Notation.</strong> <i>G</i><sup>+</sup>/<i>G</i><sup>−</sup>는 기권 기준 안내의 제공/미제공, <i>R</i><sup>+</sup>/<i>R</i><sup>−</sup>는 reasoning 설정의 활성화/비활성화다. <i>g</i>와 <i>r</i>은 각각 + 또는 −를 취한다. <strong>TargetLLM</strong>은 평가 대상 모델이며, <strong>TargetOutput</strong>은 '+ref('table-s4-1-1','Table 1')+'의 네 필드를 포함한다. 공통 입력 기호는 '+ref('notation-common','3장의 Notation')+'을 따른다.','notation-call')+fields+math(r'\operatorname{TargetLLM}(Q,C_i\mid G^g,R^r)\rightarrow\operatorname{TargetOutput}(\text{answer},\text{classification},\text{reason},\text{evidence}),','eq:target-call')+math(r'i\in\{0,\ldots,7\},\qquad g,r\in\{+,-\}.')+p('각 호출에는 같은 질문과 <strong>하나의 문맥</strong>, 응답 JSON schema를 입력한다. 원본과 일곱 변형은 각각 별도로 평가하며, 원천 정답·제작 코드·계산 그래프·검토 판정은 입력하지 않는다. 모든 조건에서 reason과 evidence를 요구하며, 실제 프롬프트와 모델별 설정은 '+section_ref('s11-prompts','Appendix P')+'와 '+section_ref('s11-experimental-settings','Appendix 6')+'에 제시한다.'),'4.1 Target Model Response Collection')
    put('s4-2',p('<strong>Notation.</strong> <strong>N</strong>은 numeric-answer, <strong>A</strong>는 abstention이며, <strong>S</strong>와 <strong>U</strong>는 각각 Supported와 Unsupported다. 두 기준을 결합한 <strong>NS·NU·AS·AU</strong>를 NASU 응답 분류로 부른다('+ref('table-s4-2-1','Table 2')+').','notation-nasu')+table('table-s4-2-1','응답 형태와 근거 지원의 결합.',['응답','Supported','Unsupported'],[['Numeric-answer','NS','NU'],['Abstention','AS','AU']])+p('<strong>Supported.</strong> 주어진 evidence가 모델이 제시한 reason과 최종 응답을 함께 뒷받침하는 경우다. NS에서는 인용한 값·관계와 계산이 제출한 수치를 정당화해야 한다. AS에서는 설명한 충돌·근거 부족이 실제로 답을 결정하지 못하게 해야 한다. 정답 일치, 충돌 선언, 인용의 존재만으로 판정하지 않는다.')+p('LLM 판정기는 응답과 입력을 대조한다. 적용 기준 중 미지원이 확인되면 U로 분류하고, 판정이 미확정이거나 응답·검토가 없으면 네 범주와 구분한다. 정보 누락은 존재하지 않는 문장의 인용을 요구하지 않고, 설명한 필수 조건과 남은 근거의 관계를 검토한다. 세부 판정 기준과 실제 사례는 '+app42+'에 제시한다.'))
    put('s4-3',p('<strong>Notation.</strong> 이후 비율에서 NS·NU·AS·AU는 '+ref('notation-nasu','4.2절 분류')+'의 응답 수다. <strong><i>T</i></strong>는 IC-v,f·IC-v,b·IC-r·ER1·ER2의 계획 응답 수로, 모델과 G/R 설정마다 1,354 × 5 = <strong>6,770</strong>이다. 미확정·미검토도 <i>T</i>에 남긴다. IC-s는 부모 IC-v와 별도로 비교한다.','notation-metrics')+p('<strong>지원율.</strong> numeric-answer에는 NS/(NS+NU), abstention에는 AS/(AS+AU)를 계산한다. 전체 문항에 대한 제공 비중은 NS/T와 AS/T로 보고한다. 전자는 해당 응답 중 근거가 뒷받침하는 비율이고, 후자는 전체 계획 문항 중 근거 있는 응답의 비중이다. 판정 완료 범위와 상세 분모는 '+section_ref('s11-metrics','Appendix 4.3')+'에 제시한다.'))
    put('s4-4',p('<strong>RQ1. 근거 조건이 달라질 때 numeric-answer와 abstention은 얼마나 Supported인가?</strong> 다섯 기본 변형에서 모델·설정별 지원율과 계획 문항 대비 비중을 비교한다.')+p('<strong>RQ2. 기권 기준 안내와 reasoning 설정은 Supported 응답을 어떻게 바꾸는가?</strong> 같은 모델·문항에서 G 또는 R을 고정하고 다른 조건을 비교한다. ER에서는 reasoning에 따라 새롭게 NS가 된 응답과 역산 가능성의 관계를, IC에서는 근거 있는 기권의 변화를 살핀다.')+p('<strong>RQ3. 어느 주장에 출처를 붙이느냐에 따라 수치 답변과 기권은 어떻게 달라지는가?</strong> IC-v,f→IC-s1과 IC-v,b→IC-s2를 각각 연결한다. 양쪽의 유효 응답을 가진 동일 대응쌍에서 원본 정답과 일치한 numeric-answer, 불일치한 numeric-answer, abstention의 비중 변화를 계산한다. 수치 불일치를 특정 충돌값의 채택으로, 모든 기권을 CONFLICT로 간주하지 않는다. 대응쌍의 포함 기준과 분모는 '+app44+'에 제시한다.'))
    put('s5',p('Luna, Haiku, Qwen3-8B, Qwen3-14B, Qwen3.8-27B의 저장 응답을 최종 FInject 문항군으로 모았다. 각 모델은 원본과 일곱 변형에 네 G/R 조건을 적용한다. 응답 지원 판정에는 GPT-6.1 Sol / low를 사용했다. 본문에는 핵심 비교를, '+section_ref('s11-pooled-results','Appendix 5')+'에는 전체 결과와 누락 범위를 제시한다.'))
    support=[];gain=[];icrows=[];variantrows=[]
    agg=collections.defaultdict(collections.Counter)
    for r in summary['aggregates']:
        if r['model'] in MODELS:
            agg[r['model'],r['G'],r['R'],r['variant']].update({k:r[k] for k in ['planned','NS','NU','AS','AU','D','F']})
    for model in MODELS:
        r=q[model,'ON','ON'];support.append([model,f'{100*r["N"]:.1f}',f'{100*r["A"]:.1f}',f'{100*r["resolved"]/r["planned"]:.1f}'])
        b=q[model,'OFF','OFF'];a=q[model,'OFF','ON'];gain.append([model,f'{100*(a["NS"]-b["NS"])/6770:+.1f}',f'{100*(a["AS"]-b["AS"])/6770:+.1f}'])
        rates=[]
        for G,R in [('OFF','OFF'),('OFF','ON'),('ON','OFF'),('ON','ON')]:
            c=sum((agg[model,G,R,v] for v in ['IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','IC_RELATION_01']),collections.Counter());assert c['planned']==4062
            rates.append(f'{100*c["AS"]/4062:.1f}')
        icrows.append([model,*rates])
        for v,label in [('IC_VALUE_01_BEFORE','IC-v,f'),('IC_VALUE_01_AFTER','IC-v,b'),('IC_RELATION_01','IC-r'),('EA_01','ER1'),('EA_02','ER2')]:
            a=agg[model,'ON','ON',v];assert a['planned']==1354
            variantrows.append([model,label,*[f'{a[k]:,}' for k in ['NS','NU','AS','AU','D','F']]])
    put('s5-1',p('기권 안내와 reasoning을 모두 사용한 '+gr+'에서도, numeric-answer의 지원율은 모델별 14.8–77.8%, abstention의 지원율은 85.8–98.9%였다('+tab3+'). 두 응답 모두 이유와 인용 근거를 제출하도록 요구했지만 미지원 판정이 남았다.')+table('tab:v2-support',gr+'의 응답 지원율(%). 판정 완료는 네 NASU 범주에 속한 응답/T. 전체 조건은 '+ref('tab:finject-rq1','Table A23')+'.',['모델','Numeric-answer 지원율','Abstention 지원율','판정 완료/T'],support)+p('수치가 원본 정답과 같아도 제출한 근거·계산이 그 값을 정당화하지 못할 수 있으며, 충돌을 찾아 기권한 응답에도 계산 오류가 섞일 수 있다. 반대로 ER에서 누락값을 남은 근거로 복원한 numeric-answer는 Supported일 수 있다. 실제 응답과 세부 판정은 '+app42+'에, 변형별 분류 건수는 '+ref('tab:v2-variant-counts','Table A0')+'에 제시한다.')+p('<strong>Finding 1. 이유와 인용의 제출은 evidence support를 보장하지 않는다.</strong> FInject에서는 numeric-answer와 abstention 모두에서 미지원 응답이 나타났다. 응답의 형태뿐 아니라 근거·계산·설명과 최종 판단의 정합성을 평가해야 이 차이를 구분할 수 있다.'),'5.1 RQ1: 근거가 뒷받침하는 답변과 기권')
    put('s5-2',p('<strong>Reasoning 설정.</strong> 기권 안내가 없는 '+gm+'에서 reasoning을 켜면 모든 모델의 NS/T가 증가했고, 증가 폭은 AS/T보다 컸다('+tab4+'). 새롭게 NS로 바뀐 응답의 92.4–95.7%는 ER이었다. 역산 가능 flag가 있는 문항에서 NS 전환이 더 잦았지만, 이 연관성만으로 모델이 실제 역산 과정을 사용했다고 단정할 수는 없다('+ref('table-s11-results-rq2-1','Table A25')+').')+table('tab:v2-reasoning',gm+'에서 R<sup>−</sup>→R<sup>+</sup>의 변화(%p). 전체 건수와 원본 정답률은 '+ref('tab:reasoning-gains-full','Table A24')+'.',['모델','Δ NS/T','Δ AS/T'],gain)+p('<strong>기권 안내와의 결합.</strong> 충돌 변형에서 '+gr+'는 모든 모델의 AS 비중이 가장 높았지만('+tab5+'), 근거가 뒷받침하지 않는 numeric-answer도 남았다. 실제 모델별 설정에서 Qwen의 R 전환은 sampling 설정도 함께 바꾸므로, 이를 reasoning만의 인과 효과로 해석하지 않는다('+section_ref('s11-experimental-settings','Appendix 6')+').')+table('tab:v2-guidance','충돌 변형의 AS 비중(%). 분모는 설정별 IC 세 유형 4,062개이며 미확정·미검토를 포함한다. 상세 건수는 '+ref('table-s11-results-rq2-2','Table A26')+'.',['모델','G−R−','G−R+','G+R−','G+R+'],icrows)+p('<strong>Finding 2. Reasoning 설정과 기권 안내는 서로 다른 근거 조건의 대응을 개선한다.</strong> Reasoning에 따른 새 NS는 주로 근거 제거 문항에서 나타났고, 충돌에서는 안내와 reasoning을 함께 제공한 설정의 AS 비중이 가장 높았다. 그러나 개선된 설정에도 미지원 응답이 남아, 설정의 제공만으로 evidence에 맞는 판단을 보장하지는 못했다.'),'5.2 RQ2: 안내·Reasoning과 근거 지원')
    mainpairs=[]
    for model in MODELS:
        ps=[r for r in pairs if r['model']==model and r['G']=='guided' and r['R']=='on'];p1,p2=ps
        mainpairs.append([model,f'{p1["delta_pp"]["M"]:+.1f}',f'{p2["delta_pp"]["W"]:+.1f}'])
    put('s5-3',p('IC-s1은 뒤쪽 원본 주장에, IC-s2는 뒤쪽 추가 주장에 출처를 붙인다. 각 변형을 출처가 없는 부모 IC-v와 비교하면 '+gr+'에서 다섯 모델 모두 IC-s1의 원본 정답 일치 비중과 IC-s2의 불일치 비중이 증가했다('+tab6+'). 두 대응 유형 모두 기권 비중은 감소했다.')+table('tab:v2-source',gr+'의 출처 추가 전후 변화(%p). 같은 유효 대응쌍이 분모다. 원본 일치·불일치는 저장된 수치 비교이며 근거 지원 판정과 구분한다. 전체 분포와 분모는 '+ref('tab:v2-source-outcomes','Table A0')+'.',['모델','IC-s1<br/>원본 일치 증가','IC-s2<br/>원본 불일치 증가'],mainpairs)+p('이 변화는 출처가 붙은 주장 쪽으로 수치 응답이 이동하는 경향과 일치한다. 다만 불일치에는 다른 계산 오류도 포함되므로 추가 수치의 정확한 채택률을 뜻하지 않는다. 다른 G/R 조건에는 반대 방향의 변화도 있으며, 출처 문구를 추가했다고 근거 자체가 더 참이 되었다고 해석하지 않는다('+section_ref('s11-results-rq4','Appendix 5.4')+').')+p('<strong>Finding 3. Evidence에 붙인 출처 정보만으로도 응답 분포가 달라진다.</strong> 수치와 계산 관계를 유지해도, 원본 또는 추가 주장 중 어느 쪽에 출처를 붙이느냐에 따라 원본 정답과의 일치 방향이 달라졌다. 따라서 근거 기반 평가에서는 수치 내용과 함께 그 근거가 어떻게 제시되는지도 고려해야 한다.'),'5.3 RQ3: 출처 표기와 응답 변화')
    put('s5-4','');by['s5-4']['hidden_ko']=True
    put('conclusion',p('우리는 금융 수치 QA에서 evidence가 모델의 reason과 numeric-answer 또는 abstention을 뒷받침하는지 평가하는 FInject를 제안했다. 실험에서는 이유와 근거를 요구하고 reasoning·기권 안내를 제공해도 미지원 응답이 남았으며, 출처 표기만으로 수치 답변과 기권의 분포가 달라졌다. 금융 모델의 응답을 평가할 때에는 최종 결과뿐 아니라 그 결과를 정당화하는 근거와 설명의 정합성을 함께 확인해야 한다.')+'<ul><li><strong>근거를 추적하는 제작 방법.</strong> 독립 Python 풀이, 계산 그래프, 통제된 변경과 사람 검토를 연결하며, 입력 어댑터로 다른 수치 QA에도 절차를 재사용한다.</li><li><strong>근거 조건을 통제한 데이터셋.</strong> 원본 1,354개와 일곱 변형 9,478개를 연결해 충돌·출처·누락에 대한 모델 대응을 비교한다.</li><li><strong>재사용 가능한 평가·분석 방법.</strong> 답변과 기권의 evidence support를 판정하고, 설정·출처 조건을 바꾼 대응 응답을 비교한다.</li></ul>','6. Conclusion')
    # Preserve all original result tables and move detailed main-text graphics to appendices.
    appendix_assets={
        's11-pipeline-2':['fig:perturbation-dag'],
        's11-nasu':['fig:arv-fav-cases'],
        's11-results-rq1':['table-s5-1-1','fig:abstention-support-share'],
        's11-results-rq2':['table-s5-2-original-reasoning','table-s5-2-1','table-s5-2-guidance-reasoning','fig:nasu-gr-bars','fig:gr-fixed-lines'],
        's11-results-rq3':['table-s5-3-1'],
        's11-results-rq4':['table-s5-4-1'],
    }
    # Discover the actual NS/AS figure ID rather than depending on a historical name.
    nsas=BeautifulSoup(next(s for s in previous if s['id']=='s4-2')['kohtml'],'html.parser').find('figure')
    appendix_assets['s11-nasu']=[nsas['id']]
    for sid,ids in appendix_assets.items():
        by[sid]['kohtml']+=''.join(asset(id) for id in ids)
        by[sid]['oldko']=''
    ex=json.loads((BUILD/'example.json').read_text())
    exact='<h4>문장형 그림의 원문과 변경 위치</h4>'+p('본문 Figure 1·Figure 3은 최종 <code>id-0217</code>을 사용한다. 원천은 FinanceReasoning-embedded의 <code>CodeTAT-QA-test-24</code>이며, 그림에서는 원본 표의 값을 문장으로 요약했다. 아래 자료가 실제 입력의 기준이다. 그림의 “verified by an analyst”는 추가한 긴 출처 문구의 요약이며 외부 검증 사실을 보증하지 않는다.')+p('<strong>질문.</strong> '+h(ex['original']['question']))+'<pre>'+h(ex['original']['context'])+'</pre>'
    vmap={v['type']:v for v in ex['variants']}
    ordered=[('C1','IC-v,f','IC_VALUE_01_BEFORE'),('C2','IC-v,b','IC_VALUE_01_AFTER'),('C3','IC-s1 (IC-s,f)','IC_SOURCE_A_ONLY'),('C4','IC-s2 (IC-s,b)','IC_SOURCE_B_ONLY'),('C5','IC-r','IC_RELATION_01'),('C6','ER1','EA_01'),('C7','ER2','EA_02')]
    rows=[]
    for ci,label,typ in ordered:
        v=vmap[typ]; patches=v['metadata']['edit_provenance']['steps'][-1]['patches']
        edit=' '.join(x['text'].strip() if x['text'].strip() else '삭제: '+x['before'] for x in patches)
        rows.append([ci,label,'<code>'+typ+'</code>',h(edit)])
    exact+=table('tab:v2-variant-map','그림의 기호·유형과 실제 저장된 변경. C3/C4는 각각 C1/C2의 문맥에 마지막 출처 패치를 더한다.',['문맥','표시명','저장 유형','원문 변경'],rows,True)
    exact+=p('C1/C2는 Apple 34%와 37.4%의 순서만 달리하며, Huawei 11%와 질문은 유지한다. C3은 뒤쪽 원본 Apple 34%에, C4는 뒤쪽 추가 Apple 37.4%에 출처를 붙인다. 두 조건 모두 출처가 뒤쪽 주장에 붙으므로, 각 자식을 부모와 비교하며 두 자식의 차이를 순수한 위치 효과로 해석하지 않는다.')
    exact+=p('C6은 Apple의 2017년 값 34만, C7은 Huawei의 2017년 값 11만 원본에서 독립 삭제한다. 다른 해의 비중에는 2017년 값을 결정하는 관계가 없고, 합계나 추가 조건도 주어지지 않는다. 따라서 이 예시의 합계는 삭제 후 유일하게 정해지지 않는다. 설명용 Supported 응답은 이 문맥의 성질을 보여주며, 모든 ER의 답변 불가능성이나 실제 모델 판정을 대표하지 않는다.')
    by['s11-pipeline-2']['kohtml']=exact+by['s11-pipeline-2']['kohtml']
    by['s11-validation']['kohtml']+=p('<strong>역산 검토의 미확정 범위.</strong> ER의 누락값을 남은 문맥에서 복원할 수 있는지에 대한 전체 사람 주석 집계는 아직 확정되지 않았다. 제작 승인과 응답의 Supported 판정은 독립적인 문항별 답변 가능성 gold를 대신하지 않는다. 본문의 NS/AS 통계는 저장된 응답 판정에 근거하며, 역산 flag는 기록된 부분집합의 연관성 분석에만 사용한다.')
    by['s11-pipeline-3']['kohtml']=p('<strong>논문 표기와 저장 필드.</strong> TargetOutput의 <code>reason</code>은 원응답의 <code>explanation</code>을 가리킨다. <code>answer</code>는 모델 출력, <i>Ans</i>는 원천 정답이다. <code>answer=null</code>은 기권을 나타내며, 분류 필드가 비어 있다는 것과 다르다. 실제 Guided 계약의 분류값에는 <code>ANSWERABLE</code>과 <code>ABSTAIN</code>도 포함되며, Unguided는 <code>classification=null</code>로 분류를 요구하지 않는다. 기존 원응답은 이 계약 그대로 보존한다. 본문 분류는 수치 답변과 기권을 응답의 <code>answer</code>로 구분한다.')+by['s11-pipeline-3']['kohtml']
    by['s11-nasu']['kohtml']=p('<strong>Notation.</strong> <i>y</i>는 모델 응답이다. <code>Numeric(y)</code>와 <code>Abstain(y)</code>은 수치 답변과 기권을 뜻한다. <strong>FAV</strong>(Final Answer Validity)는 응답 전체, <strong>ARV</strong>(Abstention Reason Validity)는 기권 이유의 타당성 판정이다. 두 판정은 각각 Supported, Unsupported, Undetermined를 반환한다. 다음 식의 NS·AS는 응답 집합이며 집계에서는 그 건수를 사용한다.')+math(r'\begin{aligned}\mathrm{NS}&=\{y\mid\operatorname{Numeric}(y)\land\operatorname{FAV}(y)=\mathrm{Supported}\},\\\mathrm{AS}&=\{y\mid\operatorname{Abstain}(y)\land\operatorname{ARV}(y)=\mathrm{Supported}\land\operatorname{FAV}(y)=\mathrm{Supported}\}.\end{aligned}','eq:app-nasu')+p('본문의 Supported/Unsupported는 아래 상세 판정의 요약이다. 용어를 단순화하기 위해 저장된 판정 기준이나 혼합 판정을 바꾸지 않는다. 수치 답변의 ARV는 적용하지 않으며, 기권은 두 판정을 모두 충족해야 AS다.')+by['s11-nasu']['kohtml']
    # Replace the over-broad paired-analysis prose with exactly the available analysis.
    keep_tables=''.join(asset(id) for id in ['table-s4-4-1','table-s11-pipeline-4-1'])
    put('s11-pipeline-4',p('<strong>설정 비교.</strong> 같은 모델과 최종 원본 ID·변형 유형을 기준으로 G/R 설정을 연결한다. NS/T·AS/T는 미확정·미검토를 포함한 같은 계획 수를 사용한다. 변화는 반올림 전 비율의 차이를 %p로 보고한다.')+asset('table-s4-4-1')+p('<strong>출처 비교의 응답 범주.</strong> 모델·G/R 조건·최종 원본 ID를 고정하여 <code>IC_VALUE_01_BEFORE</code>와 <code>IC_SOURCE_A_ONLY</code>, <code>IC_VALUE_01_AFTER</code>와 <code>IC_SOURCE_B_ONLY</code>를 각각 연결한다. <code>target_status=VALID</code>이고 양쪽에서 응답 범주를 결정할 수 있는 쌍만 포함한다. 각 유형의 계획 쌍은 1,354개이며 유효 대응쌍 수를 <i>n</i>으로 둔다. 부모와 자식의 세 범주 비중은 같은 <i>n</i>을 분모로 계산한다.')+p('수치 응답은 저장된 <code>original_reference_match</code>의 참/거짓으로 원본 일치/불일치를 구분한다. 기권은 <code>action=A</code>로 구분한다. 새 반올림·단위 규칙이나 충돌 후보값 비교를 도입하지 않는다. 판정 LLM의 검토 완료 여부는 이 출력 범주 비교의 포함 조건이 아니므로, 아래 Supported 유지율과 분모가 다를 수 있다.')+p('원본 불일치는 주입값을 정확히 채택했다는 뜻이 아니며, 기권은 CONFLICT만을 뜻하지 않는다. 어느 주장을 실제 계산에 사용했는지와 출처를 어떻게 해석했는지는 별도의 reason·evidence 분석이 필요하다. 본문 RQ3은 관측된 출력 분포의 변화만 보고한다.')+p('<strong>보충: 원본 정답 집단과 Supported 유지율.</strong> 원본 정답 일치 여부에 따른 집단 비교와 이전 AS의 유지·이탈은 보충 분석으로 보존한다. 집단 비교는 각 집단의 (NS+AS)/(NS+NU+AS+AU)를 사용한다. AS 유지율은 양쪽 NASU가 확정된 대응쌍에서 기존 AS 중 AS로 남은 비율이며, 원래 AS가 없으면 N/A다. AS→NS를 근거 지원 실패로 세지 않는다.')+asset('table-s11-pipeline-4-1'))
    by['s11-results-rq1']['kohtml']+=table('tab:v2-variant-counts',gr+'의 변형별 응답 분류. 각 행의 계획 수는 1,354개다. D는 미확정, F는 미검토·검토 불가이며 네 분류와 구분한다.',['모델','변형','NS','NU','AS','AU','D','F'],variantrows,True)
    by['s11-results-rq1']['kohtml']=p('전체 조건의 지원율과 지원 비중을 보존한다. 응답 형태별 지원율은 판정이 확정된 해당 응답만 분모에 포함하고, NS/T·AS/T는 미확정·미검토도 계획 분모에 남긴다. 기권의 지원율이 높아도 AS/T가 낮을 수 있으므로 두 지표를 구분한다.')+by['s11-results-rq1']['kohtml']
    by['s11-results-rq3']['ko']='Appendix 5.3. 보충: 원본 풀이 성공과 변형 대응'
    by['s11-results-rq3']['kohtml']=p('원본 정답 일치 집단과 불일치 집단의 지원율 비교를 보충 결과로 제공한다. 이 집단 비교는 문항 간 연관성이며 인과관계를 뜻하지 않는다.')+by['s11-results-rq3']['kohtml']
    pairrows=[]
    for r in pairs:
        condition=('G+' if r['G']=='guided' else 'G−')+('R+' if r['R']=='on' else 'R−')
        fmt=lambda c:f'{r["before"][c]:,} → {r["after"][c]:,}'
        pairrows.append([r['model'],condition,'IC-s'+str(r['pair']),f'{r["n"]:,}',str(1354-r['n']),fmt('M'),fmt('W'),fmt('A')])
    source_table=table('tab:v2-source-outcomes','출처 추가 전후의 동일 대응쌍. 숫자는 IC-v→IC-s의 건수다. 각 전후 세 범주 합은 n이며, 비율은 각 건수/n이다. 제외는 양쪽 중 하나라도 유효 응답 범주를 얻지 못한 계획 쌍이다.',['모델','G/R','출처 유형','n','제외','원본 일치','원본 불일치','기권'],pairrows,True)
    by['s11-results-rq4']['ko']='Appendix 5.4. RQ3: 출처 표기와 응답 변화'
    by['s11-results-rq4']['kohtml']=p('출처가 뒤쪽 원본 주장에 붙는 IC-s1과 뒤쪽 추가 주장에 붙는 IC-s2를 각 부모와 비교했다. 원본 일치·불일치·기권은 저장된 모델 출력으로 결정하며, Supported 여부를 대신하지 않는다. '+gr+'의 공통 경향과 달리 다른 설정에서는 역방향 변화도 나타난다. 예를 들어 Luna의 G+R−에서는 IC-s1의 원본 일치 비중이 3.77%p 감소했다.')+source_table+'<h4>보충: 근거 있는 기권의 유지</h4>'+by['s11-results-rq4']['kohtml']
    # Qualify the related-work distinction without modifying the original comparison tables.
    by['s11-full-tables']['kohtml']=p('금융 데이터셋의 제작과 평가 범위를 비교한다. FInject는 계산에 쓰이는 근거의 변경 위치를 추적하고 원본·변형을 연결한다. RealFin은 누락 조건의 식별을 평가하므로 기권 여부만을 다루는 연구로 분류하지 않는다. 비교표의 선택된 특성만으로 이유·근거 평가의 최초성을 주장하지 않는다.')+by['s11-full-tables']['kohtml']
    by['s11-comparisons']['kohtml']=p('비금융 QA에서는 충돌·근거 부족·기권 사유에 대한 연구가 활발하다. RefusalBench는 기권 탐지와 사유 범주를 구분한다 '+cite('refusalbench','Muhamed et al., 2026')+'. FInject의 범위는 금융 수치 계산에 연결한 근거 변경과 응답 정합성 평가다.')+by['s11-comparisons']['kohtml']
    put('s8',p('FInject는 통제된 근거 변경을 이용한 금융 수치 QA를 다루며, 금융 자문이나 실제 거래 업무 전체를 대표하지 않는다. 합성 충돌·출처·삭제는 실제 문서 오류와 다를 수 있다. 계산 그래프는 제작에 사용한 풀이의 의존 관계이며 가능한 모든 복원 경로를 포함하지 않는다.')+p('응답 지원 여부는 LLM 판정에 의존한다. 데이터셋 제작에 대한 사람 검증은 응답 판정기의 정확도를 독립적으로 보장하지 않으며, ER의 전체 역산 가능성에 대한 사람 검토도 미확정이다. Unsupported를 모두 hallucination, 부적절한 기권 또는 답변 불가능 문항에 대한 답변으로 해석하지 않는다.')+p('모델이 제시한 reason은 내부 추론 과정과 다를 수 있다. R 설정 비교에는 모델별 sampling 변화도 포함되며, 누락·미검토 범위가 모델·조건마다 다르다. 출처 실험의 수치 일치·불일치만으로 특정 주장 채택을 확정하지 않고, 출처 문구를 실제 신뢰성 개선으로 간주하지 않는다. 두 출처 조건 모두 뒤쪽 주장에 표기를 더하므로 출처와 위치의 효과를 완전히 분리하지 못한다.'))
    refs=by['references']['kohtml']
    refs+='<div class="reference" id="ref-unfaithful-cot"><p>Miles Turpin, Julian Michael, Ethan Perez, and Samuel R. Bowman. 2023. <a href="https://proceedings.neurips.cc/paper_files/paper/2023/hash/ed3fea9033a80fea1376299fa7863f4a-Abstract-Conference.html">Language Models Don’t Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting</a>. Advances in Neural Information Processing Systems 36.</p></div>'
    refs+='<div class="reference" id="ref-refusalbench"><p>Aashiq Muhamed, Leonardo F. R. Ribeiro, Markus Dreyer, Virginia Smith, and Mona T. Diab. 2026. <a href="https://aclanthology.org/2026.eacl-long.321/">RefusalBench: Generative Evaluation of Selective Refusal in Grounded Language Models</a>. Proceedings of EACL (Volume 1: Long Papers), pages 6811–6856.</p></div>'
    put('references',refs)
    # Bring inherited appendix prose into the v2 scope without altering its data.
    by['abstract']['kohtml']=by['abstract']['kohtml'].replace('금융에서 모델의 수치 답변과 기권은','금융에서 대규모 언어 모델(LLM)의 수치 답변과 기권은')
    by['abstract']['kohtml']=by['abstract']['kohtml'].replace('또한 출처를 붙이는 주장에 따라','기권 안내와 reasoning을 함께 제공한 조건에서는 출처를 붙이는 주장에 따라')
    by['s1']['kohtml']=by['s1']['kohtml'].replace('같은 질문에서 근거가 정당화하는 numeric-answer와 abstention.','같은 질문에서 근거가 정당화하는 numeric-answer와 abstention. Supported는 근거가 설명과 최종 응답을 함께 뒷받침한다는 뜻이다.')
    doc=BeautifulSoup(by['s1']['kohtml'],'html.parser')
    figure=doc.find('figure').extract()
    paragraphs=doc.find_all('p',recursive=False)
    paragraphs[1].replace_with(BeautifulSoup(p('이유를 설명한다고 해서 응답이 타당해지는 것은 아니다. LLM은 틀린 답을 그럴듯한 설명으로 정당화할 수 있으며, 제시한 설명이 실제 판단 과정을 반영하지 않을 수도 있다 '+cite('unfaithful-cot','Turpin et al., 2023')+'. 따라서 주어진 근거가 설명과 최종 판단을 함께 뒷받침하는지 확인해야 한다.'),'html.parser'))
    notation=BeautifulSoup(p('<strong>Notation.</strong> <strong>evidence</strong>는 문맥의 인용 근거, <strong>reason</strong>은 모델이 제시한 설명이다. 모델의 수치 답변은 <strong>numeric-answer</strong>, 기권은 <strong>abstention</strong>으로 부른다. 근거가 설명과 최종 응답을 함께 뒷받침하면 <strong>Supported</strong>다. reason은 모델의 내부 추론 자체를 뜻하지 않는다.','notation-response'),'html.parser')
    paras=doc.find_all('p',recursive=False)
    paras[1].insert_after(notation)
    doc.find(id='notation-response').insert_after(figure)
    by['s1']['kohtml']=str(doc)
    by['s11-pipeline-2']['kohtml']=by['s11-pipeline-2']['kohtml'].replace('본문의 <a href="#fig:perturbation-dag">','아래의 <a href="#fig:perturbation-dag">')
    doc=BeautifulSoup(by['s11-pipeline-3']['kohtml'],'html.parser')
    for node in doc.find_all('p'):
        t=node.get_text(' ',strip=True)
        if t.startswith('TargetOutput의 항목.'):
            node.replace_with(BeautifulSoup(p('<strong>예시의 표시 규칙.</strong> 아래 저장 응답 예시에서는 네 필드만 보여준다. 수치 응답의 <code>ANSWERABLE</code>은 그림·예시에서만 <code>NOT_APPLICABLE</code>로 표시한다. 실제 실행의 모든 분류를 세 기권 범주로 변환하지 않으며, 수치 응답 여부와 기권 여부는 <code>answer</code>로 결정한다.'),'html.parser'))
        elif t.startswith('NOT_APPLICABLE의 구별.'):
            node.replace_with(BeautifulSoup(p('<strong>NOT_APPLICABLE의 구별.</strong> 예시에서 이 값은 수치 응답에 기권 사유를 적용하지 않는다는 표시다. 응답 판정의 ARV에도 같은 문자열이 쓰이지만, 이는 별도의 판정 필드다. 상세 기준은 '+app42+'에 제시한다.'),'html.parser'))
    by['s11-pipeline-3']['kohtml']=str(doc)
    by['s11-evaluation']['kohtml']=table('table-s11-pipeline-3-1','실제 실행의 classification 값. G−는 분류를 요청하지 않으며, 아래 값들은 모델의 자기 보고다.',['값','의미'],[['<code>ANSWERABLE</code>','G+: 하나의 수치 답이 정당화된다고 판단함'],['<code>CONFLICT</code>','G+: 관련 주장들이 충돌하고 해결 기준이 없음'],['<code>INSUFFICIENT_EVIDENCE</code>','G+: 필요한 값·관계가 없고 복원할 수 없음'],['<code>UNRESOLVED</code>','G+: 해석의 모호성이 결과를 바꿈'],['<code>ABSTAIN</code>','G+: 특정 입력 결함을 확정하지 못했으나 풀이를 마치거나 검증하지 못함'],['<code>null</code>','G−: 분류 미요청. 기권을 뜻하는 answer=null과 구분']],True)
    pooled=BeautifulSoup(by['s11-pooled-results']['kohtml'],'html.parser')
    for node in pooled.find_all('p'):
        if 'RQ3' in node.get_text() or 'RQ4' in node.get_text():
            node.replace_with(BeautifulSoup(p('기본 지원율은 다섯 변형의 계획 응답 6,770개를 사용한다. NS·AS의 건수와 분모는 '+ref('notation-metrics','본문 Notation')+'을 따른다. D는 미확정, F는 미검토·검토 불가다. 출처 비교는 각 유형의 계획 1,354쌍 중 유효 대응쌍을 사용하며, '+section_ref('s11-results-rq4','Appendix 5.4')+'의 출력 범주 비교와 보충 Supported 유지율은 포함 조건이 달라 분모도 다를 수 있다.'),'html.parser'))
    by['s11-pooled-results']['kohtml']=str(pooled)
    # Number the Korean assets by their actual display order. English content is preserved.
    numbers={};oldlabels={};main={'table':0,'figure':0};app={'table':0,'figure':0}
    for s in sections:
        if s.get('hidden_ko'): continue
        doc=BeautifulSoup(s['kohtml'],'html.parser')
        for t in doc.find_all(['table','figure'],id=True):
            kind=t.name;prefix='Table' if kind=='table' else 'Figure';cap=t.find('caption' if kind=='table' else 'figcaption')
            is_app=s['id'].startswith('s11');counter=app if is_app else main;counter[kind]+=1
            number=('A' if is_app else '')+str(counter[kind]);numbers[t['id']]=prefix+' '+number
            t['data-'+kind+'-number']=number
            if cap:
                if 'data-'+kind+'-number' in cap.attrs:cap['data-'+kind+'-number']=number
                text=cap.get_text(' ',strip=True);match=re.match(r'(?:Table|Figure)\s+A?\d+',text)
                if match:oldlabels[match[0]]=numbers[t['id']]
                # Preserve caption markup and links.
                for node in cap.find_all(string=True):
                    if re.match(r'^\s*(?:Table|Figure)\s+A?\d+',str(node)):
                        node.replace_with(re.sub(r'^\s*(?:Table|Figure)\s+A?\d+',numbers[t['id']],str(node),count=1));break
            if not is_app and not (kind=='figure' and t['id']=='fig:revision-2'):t['data-layout']='one-column'
        s['kohtml']=str(doc)
    numbers['tab:inverse-association']=numbers['table-s11-results-rq2-1']
    titles={s['id']:s['ko'] for s in sections}
    for s in sections:
        doc=BeautifulSoup(s['kohtml'],'html.parser')
        if s['id']=='s1':
            cap=doc.find('figure',id='fig:abstention-intro').find('figcaption')
            cap.clear();cap.append(BeautifulSoup('Figure 1: 근거가 numeric-answer와 abstention을 정당화하는 예시. 최종 id-0217을 사용한 설명용 응답이며 실제 모델 출력은 아니다. 원문과 삭제 위치는 '+app32+'.','html.parser'))
        if s['id']=='s3-2':
            cap=doc.find('figure',id='fig:revision-2').find('figcaption')
            cap.clear();cap.append(BeautifulSoup('Figure 3: 문장으로 나타낸 일곱 근거 변형(id-0217). 초록: 충돌 추가, 분홍: 출처 표기, 취소선: 삭제. 표와 출처 문구의 요약이며 원문은 '+app32+'.','html.parser'))
        for a in doc.select('a[href^="#"]'):
            dest=a['href'][1:]
            if dest in numbers:
                a.string=re.sub(r'(?:Table|Figure)\s+A?\d+|\bA\d+\b',lambda m:numbers[dest].split()[-1] if m[0].startswith('A') else numbers[dest],a.get_text(),count=1)
        if s['id']=='s11-results-rq4':
            for node in doc.find_all(string=True):
                if 'Table 8의 전체 버전' in str(node):
                    node.replace_with(str(node).replace('Table 8의 전체 버전','Table A38의 전체 버전'))
        if s['id']=='s11-prompts':
            for node in doc.find_all(string=True):
                if '개정 NOT_APPLICABLE 규약과 구분한다' in str(node):
                    node.replace_with(str(node).replace('아래 저장 원문은 ANSWERABLE / ABSTAIN / classification=null을 유지하며 개정 NOT_APPLICABLE 규약과 구분한다.','아래 원문은 실제 실행에 사용한 ANSWERABLE / ABSTAIN / classification=null을 유지한다. 저장 필드 explanation은 본문의 reason에 대응한다.'))
        if s['id']=='s11-pooled-results':
            for node in doc.find_all(string=True):
                if '이전 classification 계약을 유지한다' in str(node):
                    node.replace_with(str(node).replace('저장 실행에는 평가 부록에서 설명한 이전 classification 계약을 유지한다. 이 재집계가 수정된 수집 계약과의 정합성이나 독립적인 답변 가능성 gold를 확정하지는 않는다.','저장 실행의 classification과 explanation 필드를 그대로 사용하며, explanation은 본문의 reason에 대응한다. 응답 지원 판정과 독립적인 답변 가능성 gold는 구분한다.'))
        s['kohtml']=str(doc)
    # Check preservation of English, original detailed tables, and every anchor.
    assert all(s['enhtml']==o['enhtml'] and s['en']==o['en'] for s,o in zip(sections,previous))
    visible=[s for s in sections if not s.get('hidden_ko')]
    ids={s['id'] for s in visible};dupes=[]
    for s in visible:
        for t in BeautifulSoup(s['kohtml'],'html.parser').find_all(id=True):
            if t['id'] in ids:dupes.append(t['id'])
            ids.add(t['id'])
    broken=[]
    for s in visible:
        for a in BeautifulSoup(s['kohtml'],'html.parser').select('a[href^="#"]'):
            if a['href'][1:] not in ids:broken.append([s['id'],a['href'],a.get_text()])
    assert not dupes,dupes
    # Historical links are repaired in the final editorial pass, never silently dropped.
    for old in ['table-s5-1-1','table-s5-2-original-reasoning','table-s5-2-1','table-s5-2-guidance-reasoning','table-s5-3-1','table-s5-4-1']:
        new=next(BeautifulSoup(s['kohtml'],'html.parser').find('table',id=old) for s in sections if BeautifulSoup(s['kohtml'],'html.parser').find('table',id=old))
        before=BeautifulSoup(assets[old],'html.parser').find('table')
        assert [[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])] for tr in new.find_all('tr')]==[[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])] for tr in before.find_all('tr')],old
    (BUILD/'paper-review-v2-ko.json').write_text(json.dumps(sections,ensure_ascii=False,indent=2)+'\n')
    report=dict(main_assets=main,appendix_assets=app,broken_links=broken,duplicate_ids=dupes,English_unchanged=True,preserved_original_result_tables=6,notation_ids=['notation-common','notation-call','notation-nasu','notation-metrics'],source_pair_rows=len(pairs),asset_numbers=numbers)
    (BUILD/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='asset_numbers'},ensure_ascii=False))
    return sections

def apply():
    repo=DraftRepository(ROOT)
    sections=json.loads((BUILD/'paper-review-v2-ko.json').read_text())
    checkpoint=BUILD/'published-master.sha256'
    expected=checkpoint.read_text().strip() if checkpoint.exists() else hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
    if hashlib.sha256(repo.source.read_bytes()).hexdigest()!=expected:raise RuntimeError('Draft changed during authoring; merge the latest edits first.')
    before={repo.source:repo.source.read_text(),repo.markdown:repo.markdown.read_text(),RUN/'draft 압축.md':(RUN/'draft 압축.md').read_text()}
    for path in repo.previews:before[path]=path.read_text()
    embedded=json.dumps(sections,ensure_ascii=False).replace('</script','<\\/script')
    updates={repo.source:json.dumps(sections,ensure_ascii=False,indent=2)+'\n'}
    bodies=[]
    for s in sections:
        if s.get('hidden_ko'):continue
        content=BeautifulSoup(s['kohtml'],'html.parser')
        for figure in content.select('figure[data-figure-file]'):
            asset=figure['data-figure-file']
            if asset.startswith('paper/asset/figures/v2/') and figure.img:
                figure.img['src']='../../../'+str(Path(asset).with_suffix('.png'))
        body=repo.markdown_body(str(content),before[repo.markdown])
        bodies.append(('### ' if s['level'] else '## ')+s['ko']+'\n\n'+body+'\n\n')
    updates[repo.markdown]='# FInject · 한글 Draft v2\n\n'+''.join(bodies)
    updates[RUN/'draft 압축.md']='# Draft 압축 v2\n\n'+''.join(bodies)
    for path in repo.previews:
        content=EMBEDDED.sub(lambda m:m[1]+embedded+m[3],before[path],count=1)
        content=content.replace('Abstract → Appendices · 최신 로컬 PDF 기준','한글 v2 · evidence 중심 개정')
        content=content.replace('현재 로컬 영문 PDF의 본문, 그림·표와 부록을 반영한 한·영 Draft입니다.','한국어는 evidence 중심 v2 초안입니다. 영어와 로컬 PDF는 이전 원고이며 번역·조판 갱신 전입니다.')
        content=content.replace('동일한 섹션 자료로 한국어·영문 파일을 함께 생성합니다. 그림을 클릭하면 확대합니다. 참고문헌은 최신 로컬 PDF의 출력 항목과 함께 갱신합니다.','한국어 v2 본문과 편집기는 같은 원문을 사용합니다. 그림을 클릭하면 확대합니다. 영어와 PDF는 번역·조판 갱신 전입니다.')
        content=content.replace("section.className='paper-section'+(item.level?' subsection':'');","section.className='paper-section'+(item.level?' subsection':'')+(item.hidden_ko?' ko-hidden':'');")
        content=content.replace("a.className=item.level?'sub':'';","a.className=(item.level?'sub':'')+(item.hidden_ko?' ko-hidden':'');")
        content=content.replace('</style>','body[data-lang=ko]:not(.bilingual) .ko-hidden{display:none!important}.notation{border-left:3px solid #087b86;padding-left:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere} .equation{overflow-x:auto} figure[data-layout="two-column"] img{width:100%;max-height:none}\n</style>',1)
        updates[path]=content
    backup=RUN/'backup/editor/v2-evidence-first-draft'
    if backup.exists():backup=backup/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True,exist_ok=True)
    for path,content in before.items():
        if path.read_text()!=content:raise RuntimeError('Concurrent change: '+str(path))
        name=path.name
        (backup/name).write_text(content)
    for path,content in updates.items():repo.atomic_write(path,content)
    checkpoint.write_text(hashlib.sha256(repo.source.read_bytes()).hexdigest()+'\n')
    for file in (WORK/'output').glob('Figure*'):
        if file.suffix in ['.png','.svg','.pdf']:shutil.copy2(file,ASSETS/file.name)
        elif file.name.endswith('-r3.pptx'):shutil.copy2(file,ASSETS/file.name.replace('-r3.pptx','.pptx'))
    print('Published Korean Draft and compressed manuscript; English and PDF unchanged.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    if args.apply:apply()
    else:build()
