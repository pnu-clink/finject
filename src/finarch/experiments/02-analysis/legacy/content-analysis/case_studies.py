"""Evidence-linked case notes for the completed exp-003; not population scoring."""
import json
from pathlib import PurePosixPath
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text

CASES = [
('gemini-2.5-flash','8de02d0540cdc6c46b1987792dbb5e04','채점기 오류: 통화기호 앞 음수 부호',
 '문맥의 2015년 1,136과 2014년 1,171을 빼면 -35입니다. 응답은 -$35 million으로 계산·방향이 맞습니다. 기존 추출기가 35로 읽은 것이 잘못이었습니다. 부호 추출을 수정한 후 숫자 일치로 정정했습니다.'),
('gemini-2.5-flash','44fed44f1912214d55ec6bc2ba89905a','형식 실패지만 정답 숫자와 일치',
 '문맥의 57,299 + 565,609 = 622,908이며 원천 정답도 622908입니다. answer가 문자열이 아니라 JSON 숫자여서 형식 실패했습니다. 계산 실패와 구별해야 합니다. 단위 없는 응답이라는 별도 한계는 남습니다.'),
('gemini-2.5-flash','6f898b79010dffa1f6d3b65e6b3526f7','근거 배열 대신 문자열 반환',
 '2014년 1,171 - 2013년 1,701 = -530입니다. answer와 설명은 이 계산을 제시하지만 evidence가 문자열 한 개로 반환되어 배열 스키마를 위반했습니다. 정답 계산과 반환 형식은 별개입니다.'),
('gemini-2.5-flash-lite','2f71f10a3053b293c75755b05b0c4404','정답 숫자이나 문자열 계약 위반',
 '같은 test-0056에서 -530을 숫자 타입으로 반환했습니다. 숫자 자체는 정답과 일치합니다. 이 응답을 형식 오류라는 이유만으로 풀이 오답으로 취급하면 안 됩니다.'),
('gemini-2.5-flash','3d1f2619331bb7e18b8dc05e9f4b53ac','연도 때문에 자동 숫자 비교에서 빠짐',
 '문맥의 유리한 변동 13 + 24 + 49 = 86이며 정답도 86입니다. answer가 2011과 86을 함께 포함해 두 숫자가 추출되므로 기존 보수적 숫자 비교는 미평가로 남깁니다. 이는 답변 오류가 아니라 추출기 적용 범위의 한계입니다.'),
('gemini-2.5-flash-lite','f5182838f857cd8b7aeb6208f9918fcb','원문 숫자 오독과 답·설명 불일치',
 '문맥 Domesticstate 값은 57299인데 설명에서 5729.9로 읽었습니다. 설명은 571339로 반올림한다고 쓰지만 answer는 1038708입니다. 실제 합계는 622908입니다. 숫자 오독과 응답 내부 불일치가 함께 확인되는 내용 실패 사례입니다. 같은 모델 on 응답은 622,908을 반환했지만 이 한 사례만으로 추론 설정의 일반 효과를 단정하지 않습니다.'),
('gemini-2.5-flash-lite','170ee87531372539970b51d65ef57629','지정 소수 자릿수에서 계산 결과 불일치',
 '5.3 / 17.7 = 약 0.299435이므로 세 자리 반올림은 0.299입니다. 응답 0.300은 지정 정밀도와 다릅니다. 올바른 두 입력을 인용했어도 최종 수치 정확성이 보장되지 않는 사례입니다.'),
('gemini-2.5-flash','927bb8b05ec01ad387e3fca870cfc5f1','충돌을 설명했으나 null로 형식 실패',
 'IC-value-after P1/on에서 원래 저가 5.99와 추가 저가 6.589의 충돌을 설명했습니다. 8.4-5.99=2.41과 8.4-6.589=1.811 두 결과를 제시하고 하나를 확정하지 않았습니다. 그러나 answer=null로 문자열 계약을 위반하여 기존 유보 탐지에서도 제외됐습니다. 이 사례는 충돌 인지와 형식 성공이 별개임을 보여 줍니다.'),
('gemini-2.5-flash-lite','96431b1a3d638ac9692188ff1f66e2a3','근거 부족 설명이 있는 null 응답',
 'EA-01 P1/on에서 비용 총액이 제공되지 않아 연평균을 계산할 수 없다고 설명하고 answer=null을 반환했습니다. 유보 의도는 설명에서 관찰되지만 기존 answer-only 집계에는 반영되지 않습니다. 다른 경로로 복원이 가능한지까지 독립 검증하지 않았으므로 유보 정답 판정으로 확대하지 않습니다.'),
('gemini-2.5-flash','bbb673eec1f95713cec9712a275a51d2','설명 재시작·문자열 파손 뒤 출력 잘림',
 '최종 출력에 답과 설명을 반복 시작하는 조각 및 문법이 깨진 문자열이 보입니다. 제공자 종료 사유는 MAX_TOKENS이며 JSON은 완성되지 않았습니다. 저장된 출력 토큰 6031, 추론 토큰 1262입니다. 단순히 사고가 어려웠다는 추측 대신 실제 출력 파손과 종료 사유를 기록합니다.'),
('gemini-2.5-flash-lite','db917fb07245996cc29a9503610e2228','반복된 줄바꿈으로 출력 잘림',
 'evidence 문자열 뒤로 대량의 이스케이프 줄바꿈이 이어지고 출력이 끝납니다. 출력 토큰 7923, 추론 토큰 253이며 MAX_TOKENS입니다. 답의 시작 부분은 존재해도 완성된 JSON이 아니므로 정상 응답으로 복구하지 않았습니다.'),
]


def build(root):
    if root.name != '20260920-exp-003':
        return
    public={x['item_id']:x for x in rows(root/'01-input/public.jsonl')}
    private={x['item_id']:x for x in rows(root/'01-input/private.jsonl')}
    allrows={m:{x['trial_id']:x for x in rows(root/m/'03-results/results.jsonl')} for m in {x[0] for x in CASES}}
    out=['# 대표 응답 11건의 근거 대조', '', '빈도 추정을 위한 무작위 표본이 아니라 서로 다른 실패·미평가 원인을 설명하는 사례입니다. 각 사례는 실제 입력·원응답에 연결됩니다. 전수 의미 채점은 아닙니다.', '']
    for i,(model,trial,title,note) in enumerate(CASES,1):
        row=allrows[model][trial];result=read(root/row['result_path']);response=result.get('response')
        out += [f'## {i}. {title}', '', f"{model} · {row['case']} · {row['variant']} · {row['prompt_condition']}/{row['reasoning']} · {row['status']}", '', note, '',
                f"[호출 JSON]({row['call_path']}) · [원응답]({PurePosixPath(row['result_path']).parent}/raw-response.json) · [검사 기록]({row['result_path']})", '',
                '**질문**: '+public[row['item_id']]['question'],
                '**원문 정답**: '+private[row['item_id']]['reference']['reference_answer']+' (변형 문제의 유보 정답으로 사용하지 않음)', '',
                '```json',json.dumps(response,ensure_ascii=False,indent=2) if response is not None else '(JSON 미완성: 위 원응답 링크 참조)', '```', '',
                '<details><summary>실제 전달한 컨텍스트</summary>', '', public[row['item_id']]['context'], '', '</details>', '']
    # Markdown only: no HTML disclosure elements.
    out=[x.replace('<details><summary>실제 전달한 컨텍스트</summary>','**실제 전달한 컨텍스트**').replace('</details>','') for x in out]
    write_text(root/'CASE-STUDIES.md','\n'.join(out))
