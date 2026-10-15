# FInject PASS 1,354 문항군의 실험 결과 취합

저장 결과 확인 시각: __GENERATED_AT__. 새 Evaluation/Analysis 모델 호출은 0건입니다.

## 범위와 읽는 순서

최종 `data/final/finject-20261007`의 FinanceReasoning 1,071개와 TAT-QA 283개를 하나의 FInject 코호트로 집계합니다. 7개 변형이 모두 human PASS인 문항군만 포함하며, 원본·gold·응답·판정은 수정하지 않습니다.

표의 조건은 `G⁺R⁺`, `G⁺R⁻`, `G⁻R⁺`, `G⁻R⁻`로 표시합니다. G는 Guidance, R은 Reasoning이며 `⁺`는 ON, `⁻`는 OFF입니다.

1. `summary.json`: 모델·G×R별 RQ1/RQ2/RQ3, 검토 범위, 원천 run 정보.
2. `selection.csv`: final ID → 원천 문제 ID와 파일 위치.
3. `responses.jsonl`: 모델·final ID·조건·변형별 저장 응답 결과와 최신 A02 근거 경로. 기존 run ID와 response ID를 보존합니다.
4. `manifest.json`: 입력 해시, 선택한 최신 attempt, 출력 해시와 검증 결과.
5. `execution.log`: 로컬 취합 순서와 완료 기록.
6. `rq-results.xlsx`: 조건별 비교, 사분면, 세부분류, 원본 정답/오답 집단과 IC-source 짝 비교.
7. `publication.json`: 이 집계를 반영한 로컬 논문·표의 위치와 해시.
8. `verification.json`: 최종 집계 대조, Excel 수식 검사, PDF 컴파일·표 배치 확인.

## 분모와 미완료

문항군 1,354개 × 원본 포함 8개 입력 × 4개 조건 = 모델당 계획 43,328건입니다. RQ1/RQ2는 IC-v 앞/뒤·IC-r·ER 앞/뒤의 5개 변형으로 조건당 6,770건입니다. RQ3는 IC-v→IC-s 두 쌍이며 각 조건·쌍당 계획 1,354건입니다.

지원 비율은 **건수를 합산한 뒤** 계산합니다. 전체 O=(NS+AS)/(NS+NU+AS+AU), 숫자 N=NS/(NS+NU), 기권 A=AS/(AS+AU)입니다. ND/AD는 판단 유보, F는 검토 불가·미완료입니다. 이 항목들도 계획 분모와 검토 범위에 남습니다. 분모 0은 N/A입니다. NS/계획·AS/계획도 별도로 제공합니다.

Gemini의 R-OFF 조건은 기존 실행 계획에 없었으므로 `CONDITION_NOT_RUN`으로 구분합니다. 저장된 R-ON 응답의 A02가 미실행이면 지원 비율은 미확인입니다. 원본은 A02 근거 검토 대상이 아니므로 원본 F를 풀이 실패로 세지 않습니다.

원본 정답/오답은 기존 숫자 reference와의 일치/불일치(유효한 null은 숫자 정답 불일치)입니다. 비교 미확인은 UNKNOWN으로 보존합니다. 이는 원본 설명의 의미적 타당성이나 변형의 독립적인 답변가능성 gold가 아닙니다. NS/AS/NU/AU도 LLM 응답 근거 판정입니다.

기존 experiments 뷰어의 ANSWERABLE 비교 화면에서 **FInject 최종 PASS**를 선택해 취합값을 확인하고, 원천 run에서 문항별 원응답과 판정을 확인합니다. 논문의 개정 초안과 `paper/local-preview/rq*-table.tex`는 같은 `summary.json`을 사용합니다.

[취합 결과 뷰어](http://127.0.0.1:8894/?run=20261003-exp-009-concat-002-luna&tab=answerable), [로컬 논문 PDF](../../../paper/local-preview/main.pdf), [합본 Excel](rq-results.xlsx)을 열어 확인할 수 있습니다. RQ1/RQ2/RQ3의 독립된 PDF는 `paper/local-preview/rq1-table.pdf`부터 `rq3-table.pdf`까지입니다. Overleaf에는 전송하지 않았습니다.

## 재현

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.experiments.02-analysis.01-results.final_cohort --output reports/analysis/<새 스냅샷 폴더>
```

기존 스냅샷 덮어쓰기는 거부합니다. source/final/frozen 입력, human PASS 집합, 최신 attempt, 입력 해시가 다르면 중단합니다. 실제 모델 호출이나 source run 취합 상태 변경은 수행하지 않습니다.
