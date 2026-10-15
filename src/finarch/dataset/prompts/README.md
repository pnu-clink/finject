# 프롬프트 안내

현재 고정 프롬프트는 `src/finarch/dataset/prompts/`에서 관리합니다. Python 코드는 `src/finarch/`에서 이 파일을 읽습니다. 제작 입력과 지침은 영어로 유지합니다.

- `01-preparation.02-review-and-correct`: 원본 검토와 보정.
- `01-preparation.03-calculation`: POT 생성, 독립 풀이 보충 지침, 정답 불일치 근거 검토.
- `02-generation.02-generate-text`: 공통 문장 생성 규칙과 유형별 지침.
- `02-generation.feedback`: 문항별 피드백을 만드는 지침.
- `shared.01-02.02-03`: Preparation 원본 검토와 Generation 검증의 공통 규칙 및 유형별 검증. ANSWER 전용 지침은 `01-preparation.02-review-and-correct.answer.md`.
- `shared.01.02`: 두 파이프라인의 공통 설명 지침.
- `shared.default-answer`: 공급자 코드의 기본 지침.
- `legacy`: 이전 통합 프롬프트 보존본. 현재 유형별 선택기는 사용하지 않습니다.

## 읽는 순서

이 안내 → 해당 단계 파일 → `migration.json`의 이전 위치·내용 해시. 유형별 호출은 common과 해당 유형 하나를 결합하고, 공급자에서 explanation 지침을 추가합니다. 런타임 요청 데이터·문항별 보완 내용은 기존 파이프라인에서 결합하며 과거 호출 원문은 이동하지 않습니다.

## 파일 목록

- [01-preparation.02-review-and-correct.answer.md](01-preparation.02-review-and-correct.answer.md)
- [01-preparation.02-review-and-correct.revision.md](01-preparation.02-review-and-correct.revision.md)
- [01-preparation.03-calculation.independent-solve.md](01-preparation.03-calculation.independent-solve.md)
- [01-preparation.03-calculation.pot.md](01-preparation.03-calculation.pot.md)
- [01-preparation.03-calculation.review-answer-evidence.md](01-preparation.03-calculation.review-answer-evidence.md)
- [01-preparation.03-calculation.source-revision.md](01-preparation.03-calculation.source-revision.md)
- [02-generation.02-generate-text.common.md](02-generation.02-generate-text.common.md)
- [02-generation.02-generate-text.ea.md](02-generation.02-generate-text.ea.md)
- [02-generation.02-generate-text.ic-relation.md](02-generation.02-generate-text.ic-relation.md)
- [02-generation.02-generate-text.ic-source.md](02-generation.02-generate-text.ic-source.md)
- [02-generation.02-generate-text.ic-value.md](02-generation.02-generate-text.ic-value.md)
- [02-generation.feedback.case-feedback.md](02-generation.feedback.case-feedback.md)
- [legacy.02-generation.02-generate-text.realization.md](legacy.02-generation.02-generate-text.realization.md)
- [legacy.shared.01-02.02-03.review-and-validation.md](legacy.shared.01-02.02-03.review-and-validation.md)
- [shared.01-02.02-03.review-and-validation.common.md](shared.01-02.02-03.review-and-validation.common.md)
- [shared.01-02.02-03.review-and-validation.ea.md](shared.01-02.02-03.review-and-validation.ea.md)
- [shared.01-02.02-03.review-and-validation.ic-relation.md](shared.01-02.02-03.review-and-validation.ic-relation.md)
- [shared.01-02.02-03.review-and-validation.ic-source.md](shared.01-02.02-03.review-and-validation.ic-source.md)
- [shared.01-02.02-03.review-and-validation.ic-value.md](shared.01-02.02-03.review-and-validation.ic-value.md)
- [shared.01.02.explanation.md](shared.01.02.explanation.md)
- [shared.default-answer.md](shared.default-answer.md)

## 확인 결과

[로컬 확인 기록](verification.json): 이동 해시, 유형 선택 9개, 역할 로딩 4개, Preparation 검사 10개, 실행 중 viewer의 현재 프롬프트 경로 확인 통과. 과거 프롬프트 테스트에는 실행 자료 누락 및 기존 공통 설명을 반영하지 않은 기대값으로 인한 실패가 남아 있습니다. LLM 호출은 하지 않았습니다.

## 2026-09-15 용도별 사전 검토

[검토 결과와 스키마 누락](../../../../docs/01-dataset/90-operations/02-model-calls.md). review·POT·verification·handler 및 Generation 검증 common의 역할 경계를 보완했습니다. 과거 migration/verification 기록은 당시 결과이며 이번 정적 검토나 실제 모델 검증으로 대체하지 않습니다.

- [Preparation 의미 검증](01-preparation.05-verification.semantic.md)
- [공통 오류 진단](shared.01-06.02-04.exception-handler.md)


## 공통 Q/C 해석 범위 (2026-09-16)

모든 실제 호출 프롬프트는 `shared.01.02.scope-boundary.md`로 시작합니다. 역할별 MD에 문구를 중복 복사하지 않고 `shared/providers/cli.py::prepare_instruction`이 역할·유형·override·feedback 결합 후 최상단에 붙입니다. API/CLI 전달 전 동일 조립 경로를 사용합니다. 프롬프트 parts의 첫 항목에 파일·본문·해시가 기록되므로 새 호출의 viewer 프롬프트 입력에서 확인할 수 있습니다. 과거 호출 기록은 변경하지 않습니다.

Q/C로 범위를 먼저 정하고 필요한 외부 공식·데이터만 보완합니다. 외부 상황을 먼저 상정해 Q/C를 확장하지 않습니다. 가정 선언만으로 정당화하지 않으며 실제 누락·모순 검사는 유지합니다. Generation의 명시된 변경 계획은 허용하지만 계획 밖 변경이나 의도된 충돌의 임의 보정은 금지합니다.

## 실패 해석 및 표시 번역

`shared.01-07.02-05.failure-interpretation.md`는 사람 검토용 영어 의견이며 생산 판정을 바꾸지 않습니다. `shared.01-07.02-05.display-translation.md`는 그 결과의 한국어 표시 번역 전용입니다. 요청/응답 schema_id는 같은 역할 이름에 `.request`/`.response`를 붙이며 JSON index에 등록합니다. [설계와 호출 범위](../../../../docs/01-dataset/90-operations/04-viewer.md).
# 2026-09-16 프롬프트 점검 결과

현재 선택 가능한 본문·공통·조건부/fallback 23개 중 20개를 정리했습니다. 문자 수 합계는 47,225 → 35,764자(24.3% 감소)입니다. 역할·Q/C 경계·출처·출력 계약은 유지하고 중복을 줄였습니다. 모델 행동 동등성 실험은 진행하지 않았습니다.

개별 파일 전후 길이, 보존 조건과 남은 보조 경로 불일치는 [점검 보고서](../../../../log/prompt-review-20260916/README.md)에 있습니다. 기존 run에 저장된 prompt/응답은 바꾸지 않습니다.
