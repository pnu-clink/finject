# 기존 응답의 문제·개선 검토와 비교대조

새 [원본 R0/R1 짝·변형 4조건 분석](20260924-content-analysis/README.md)은 exp-007/008의 저장 결과를 원문 단위로 다시 집계하며 역전 문항과 의미 판정 미평가를 구분합니다. 논문용 결과의 단계는 [EX03 내용 분석](../../../../docs/02-experiments/03-content-analysis/README.md)에 연결했습니다.

이 폴더는 **기존 응답 진단 → 개선 전체 수집 → 같은 조건 반복 → 제한된 후속 확인**을 진행 순서대로 연결합니다. 현재 완료 범위는 [상위 보고서](../README.md)를 먼저 읽습니다. [최종 개선·반복 결과](20260923-exp-008/findings.md), [같은 요청 두 번의 비교](20260923-exp-007-008-repeat/README.md), [길이 제한 120회 확인](20260923-exp-008/bounded-output.md), [호출·비용 장부](continuation-cost-ledger.json)가 후속 산출물입니다.

아래는 **재실험 전에 완료한 기존 원응답 진단의 읽는 순서**입니다. [문제·개선 계획](../../../../docs/02-experiments/04-comparison/01-improvement-plan.md)과 [실제 검토 근거](intent-review-evidence.json)는 원문 7개에서 고른 응답 20개와 근거 파일 33개의 SHA-256을 연결합니다. 목적에 맞춰 고른 사례이므로 전체 오류율이나 새로운 의미 정답으로 사용하지 않습니다.

기존 응답 형식(파일 식별명 `FinancialAnswerMagnitudeV4`)은 exp-006에서 실제 응답을 받은 규약입니다. 변경해 둔 응답 형식(파일 식별명 `FinancialAnswerV6`; 이번 검토 시점의 새 성공 응답 0건)은 지시문·JSON 구조·Python 검사를 변경해 저장한 안입니다. 이 식별명의 숫자는 모델 버전이나 여섯 번째 실험을 뜻하지 않습니다. 변경 파일과 로컬 검사가 있다는 사실은 실제 응답의 개선 효과를 확인했다는 뜻이 아닙니다.

읽는 순서는 [문제·개선 계획](../../../../docs/02-experiments/04-comparison/01-improvement-plan.md) → [검토한 원응답과 해시](intent-review-evidence.json) → [비교 분석](analysis.md) → [계산한 비교표](contrasts.json) → `paired-observations.jsonl`입니다. 원문 100개에서 관련 7변형을 연결하며, 1,400개 P0/P1 쌍을 독립 원문으로 취급하지 않습니다.

재현 명령: `PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.comparison.research_contrasts --source reports/run/20260923-experiment-improvement/01-baseline --output reports/run/20260923-experiment-improvement/03-research`.

숫자/null 전환은 관찰 지표입니다. 의미 정답·유보 적절성·동일 조건 반복 안정성은 이 표가 판정하지 않습니다. 원문·원응답·기존 점수는 바꾸지 않습니다. 공통 뷰어의 `20260923-experiment-improvement`에서 읽습니다.

P0는 기본 풀이, P1은 충돌·정보 부족·질문의 출처 조건을 고려하도록 안내하는 비교입니다. 공통 JSON을 동일하게 제공하더라도 모델 행동에 주는 영향이 0이라는 보장은 없습니다. 기존 공통 지시문에 들어 있던 유보 안내와 status 삭제 후 관찰할 수 없어진 모순을 구별합니다. 조건부 결과나 근거 ID 같은 새 필드의 도입은 제안이며, 도입한다면 두 조건의 입력·스키마·검사를 함께 고정해 별도 변경 효과로 검토해야 합니다.

저장 자료의 분석·문서 생성 자체는 모델을 호출하지 않습니다. 실제 후속 호출 6,420회와 선행 exp-005의 3,000회는 [호출 장부](continuation-cost-ledger.json)에 분리되어 있습니다. API 요청 1회·성공 응답 0건은 exp-004의 과거 차단 이력이며 현재 수집 상태가 아닙니다. 두 번의 반복 관찰, 의미 판정 미평가, 독립 집단 일반화 미평가를 구별합니다.

이 README는 `src/finarch/experiments/02-analysis/legacy/comparison/research-review-template.md`에서 생성합니다.
