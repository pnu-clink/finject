# 회의록 기반 금융 충돌 논문 초안 · v0.10

2026-10-02 공동 검토용 Markdown 원고입니다. 교수님과 작성자의 대화와 후속 사용자 정정을 반영하고, 제작·Evaluation·Analysis의 현행 문서·구현·저장 자료와 선행 논문 원문을 확인했습니다. 기존 PAPER-KO.md는 집필 검토 대상이며 현행 사실의 기준으로 사용하지 않았습니다. 새 제작·실험·LLM 호출·구현 변경은 없고, 결과와 결론은 공란입니다. PDF는 공동 수정 이후 단계입니다.

## 읽는 순서

1. [한국어 원고](PAPER-KO.md): 1절의 세 기여, 2절의 용도별 문헌 비교, 3절의 RQ·SQ·가설을 먼저 봅니다. 3.3절은 중심 H1–H3을 먼저 나열하고 보조 HS1–HS4의 연결 RQ를 표시합니다. [H1·HS1 정리 기록](evidence/hypothesis-alignment-20261002.json)에서 변경 이유를 확인합니다. 제작·신뢰성·검토 지원은 4–5절, 통합 평가는 6절, 분석 결과를 채울 모델·설정별 문장 틀은 7절에 있습니다. 9절 결과와 10절 결론은 비어 있습니다.
2. [세 기여의 배치와 보고 틀](evidence/CONTRIBUTION-STRUCTURE.md): 일치율·κ의 역할, 금융·비금융 여섯 문헌 그룹, 모델 규모·원본 풀이·Guided·Reasoning의 결과 작성 틀을 읽습니다.
3. [비교표와 검토 지원 상세 표](evidence/comparison-tables.md): 금융 12개 데이터셋의 제작 표 1·평가 표 2는 본문 2.2·2.3절에, 비금융 10개 데이터셋의 표 C1·C2는 부록 C.1·C.2에 있습니다. 제작 9개 요소와 평가 10개 요소를 가로의 feature와 ○/빈칸으로 비교하며, 같은 본 연구(설계) 행을 각 표 마지막에 둡니다. 부록 C.3의 표 C3는 검토 지원에 ○가 있는 8편의 실제 도구·자료·검토 방식을 설명합니다. [표 이동 기록](evidence/table-placement-20261002.json)에서 이전·현재 위치와 보존 범위를 확인합니다.
4. [문헌 대조 근거](evidence/LITERATURE-COMPARISON.md): 서베이에서 원 논문으로 이어지는 경로, 원문 절·페이지, 판본·분류 이유를 확인합니다. [418개 셀 재검토](evidence/feature-audit-20261001/cell-audit.json)와 [읽은 페이지](evidence/feature-audit-20261001/audited-rows.json)를 함께 제공합니다. [행 데이터](evidence/COMPARISON-MATRIX.json), [용도별 그룹·원문 위치](evidence/BENCHMARK-PURPOSE-GROUPS.json), [PDF 목록·해시](evidence/literature/sources.json)를 함께 제공합니다.
5. [회의→원고 대응표](MEETING-TO-PAPER.md): 타임스탬프별 논점, 기존 원고의 수정 이유, 후속 정정과 채택·보류 판단을 확인합니다.
6. [그림 1](../../../paper/asset/pipeline-overview-v4-abstract.svg): 기존 흐름도를 재사용했으며 원고의 캡션에서 역할·주장 범위를 설명합니다. 새 그림 파일은 만들지 않았습니다.
7. [EA 구현 재확인](evidence/CURRENT-IMPLEMENTATION-NOTE.md): 별도 작업에서 갱신된 코드와 과거 실행 결과를 구분합니다. 코드 존재는 실행·의미 검증 완료가 아닙니다.
8. [주석 일치도 저장 집계 확인](evidence/annotation-agreement-source-note.json): 기존 두 주석자의 유형별 일치율·κ 집계와 입력 해시를 읽은 기록입니다. 재계산·새 주석·최종 논문 품질 승인 기록이 아닙니다.
9. [작업 로그](events.jsonl), [확인 기록](verification.json), [○/빈칸 표 확인](evidence/feature-table-verification.json): 집필 변경·자료 확인·원고 해시·뷰어 대조·검사 결과 예시를 추적합니다. 파일 저장과 사용자 직접 검토 완료는 별개입니다.
10. [연속 주석 시스템의 현행 근거](evidence/ANNOTATION-WORKFLOW.md): 본문 5.2절과 부록 D의 숫자키 판정·즉시 저장·자동 이동·재개 기능을 문서와 구현에 연결합니다. [파일·확인 범위](evidence/annotation-workflow-source-checks.json)와 [그림 D1의 별도 이미지](../../../outputs/evaluation-export-20260930/evaluation-screen.jpg)를 함께 제공합니다. 이미지는 기존 기능 확인용 화면이며 데이터셋의 품질 결과가 아닙니다.

## 화면에서 검토

[공통 연구 뷰어](http://127.0.0.1:8896/viewer/research/)에서 **2026-10-01 · 회의록 기반 논문 MD 초안**을 선택합니다. 다른 작업의 자료가 첫 선택에 있을 수 있습니다. 이 실행의 RESEARCH-DIRECTION.md는 PAPER-KO.md를 가리키며, 공통 뷰어가 실제 저장 원문을 읽습니다. 실행 폴더별 별도 HTML은 만들지 않았습니다.

22개 논문의 제작·평가 절과 관련 부록을 다시 대조해 418개 셀을 검토하고 28개 포함 판정을 수정했습니다. 포함 항목에만 ○를 표시하며 나머지는 빈칸입니다. [재검토 기록](evidence/feature-audit-20261001/AUDIT.md)에 원문 위치·수정 이유·정의 경계를 남겼습니다.

## 이번 수정의 중심

- 3.3절에서 RQ1의 **H1: 주석자의 문항 판정 재현성**과 RQ2·SQ1의 **HS1: 모델의 원본 풀이와 변형 대응 관계**를 구분했습니다. 중심·보조 가설을 두 표로 정리하고 연결 질문·검토 단위를 표시했습니다. HS1은 원본 정답군과 오답군의 인식·대응 비율을 비교하는 방향 가설로 명확히 했습니다.
- 금융 제작·평가 비교표를 본문 2.2·2.3절의 표 1·2로 옮기고, 비금융 비교표는 부록 C.1·C.2의 표 C1·C2로 정리했습니다. 본문에는 비금융 표의 위치와 제작·평가 목적의 차이를 간략히 설명했습니다. 모든 ○/빈칸과 연구 행을 보존했습니다.
- 본 연구의 검토 지원 특징으로 **숫자키 1 Accept·2 Reject·3 유보 → 즉시 저장 → 다음 미평가 항목 표시**를 본문 5.2절에 적었습니다. 부록 D에는 많은 문항을 연속 검토하는 사용 절차·판정표·진행 상태·재개 기능과 실제 화면 이미지를 제시했습니다. 평가자용 HTML의 현재 기능을 확인했으며 구현을 변경하거나 새 판정을 입력하지 않았습니다.
- [검토 지원 조사 표](evidence/REVIEW-SUPPORT-COMPARISON.md)는 ○인 금융 5편·비금융 3편의 도구·화면·입력·검토 단위를 설명하며, 빈칸인 14편의 실제 품질 절차도 함께 적었습니다. [원문 확인 기록](evidence/review-support-source-checks.json)에 페이지·PDF 해시·확인 범위를 저장했습니다. 표 1·2의 기존 ○/빈칸은 바꾸지 않았습니다.
- 본문 5.2절과 부록 C.3을 연결했습니다. 지원 도구 제공, 독립 판정 일치, 시간·부담 감소를 구별하고 화면 제공 자체를 새로운 기여로 주장하지 않습니다.
- 5.2–5.3절은 주석 지원과 독립 판정 일치율·κ의 역할을 강조합니다. 높은 일치가 확인되면 판정 재현성의 핵심 근거로 사용하며, 실제 시간·부담 감소와는 구분합니다.
- 2.2–2.3절은 금융 4/4/4개의 세 그룹과 금융 비교표를 설명합니다. 비금융 4/3/3개의 세 그룹과 개별 비교표는 부록 C에 두었습니다. 공통 열 정의와 지원 상세 설명도 부록에서 확인합니다.
- 7.2–7.5절은 소형·대형 모델, 원본 정답·오답군, Guided·Reasoning·두 설정 결합의 차이와 유용성을 채울 문장 틀입니다. 아직 실제 결과 문장을 채우지 않았습니다.
- 데이터셋의 신뢰성과 사람 검토 지원, 금융 계산·근거 판단의 통합 평가, 문제 유형별 모델·설정 활용 분석을 세 기여와 본문 구성에 연결했습니다.
- 표의 가로에 개별 제작·평가 요소, 세로에 데이터셋을 놓고 셀은 ○/빈칸만 사용했습니다. 현행 원문 근거는 [문헌 대조](evidence/LITERATURE-COMPARISON.md)에 연결했습니다. [이전 세부 설명](evidence/comparison-details.md)은 수정 전 해석의 이력입니다.
- 생성 방식과 평가 범위를 두 표로 나누고 금융·비금융을 구분했습니다. 서베이는 출처를 찾는 지도이며, 각 행은 원 논문의 실제 방법·평가 절에 근거합니다.
- 프로그램·그래프·사람 검토·짝 비교·프롬프트 비교 각각을 최초 제안으로 주장하지 않습니다. 차이는 같은 금융 원본과 그 변형을 제작 근거부터 공동 평가까지 연결하는 단위로 설명합니다.
- 기존 벤치마크 전체의 상위집합을 주장하지 않습니다. 서로 다른 도메인의 관련 능력과 우리 금융 QA의 포함 범위를 구분합니다.

## 주장 경계

- 표의 ○는 정의한 요소의 포함입니다. 나머지는 빈칸으로 표시하며, 빈칸은 점수 0이나 연구 부재의 확정이 아닙니다. 본 연구(설계)의 ○는 실행·품질·성능 검증 완료가 아닙니다. 기존 세부 설명과 넓은 ✓/△ 분류는 evidence/comparison-details.md와 행 JSON에 보존했습니다.
- 계산 그래프는 제작자가 확인한 참조 계산 경로입니다. 대상 모델의 내부 사고 경로가 아닙니다.
- 원문·변경·계산·검토 자료 제공은 구현·저장 근거로 설명합니다. 유형별 일치율·κ의 기존 집계는 확인했으나, 최종 문항군·버전과 독립 판정 여부를 확인한 뒤 논문 품질 결과로 연결합니다. 일치율·κ만으로 의미 정답이나 실제 검토 부담 감소를 확정하지 않습니다.
- IC-source는 검증된 IC-value 문항에서 출처를 추가하는 다단계 생성입니다. 두 source 조건에는 배치·주장 내용 차이도 있어 출처만의 순수 효과로 해석하지 않습니다.
- 4.3절은 value → source → relation → EA 순서입니다. Relation은 같은 수량의 직접값과 관계식 선택·충돌 인식을, EA는 근거 부족 대응과 가능한 역산 발견을 살핍니다.
- SOURCE 정확 비교와 EA 제한 역산 검사는 실제 호출 경로·저장 예시를 확인했습니다. 의미 타당성이나 전체 답변 불가능성의 증명이 아닙니다. EA의 별도 LLM true/false 기록 경로는 집필 중 코드에서 재확인했습니다. 실제 새 모델 검토·주석 결과와 독립 타당성 검증은 확인하지 않았습니다.
- 형식 유효성·숫자 일치·인용 존재만으로 모델의 의미 성능이나 유용성을 결론 내리지 않습니다. 9절 결과·10절 결론은 공란입니다.

## 보존한 이력과 원천 근거

- [v0.9 가설 연결 정리 전 원고](revisions/PAPER-KO-v0.9-before-hypothesis-alignment.md), [당시 확인 기록](revisions/verification-v0.9-before-hypothesis-alignment.json): 중심 가설이 보조 질문 표 뒤의 문단에 있던 상태를 보존했습니다.

- [v0.8 금융 비교표 본문 이동 전 원고](revisions/PAPER-KO-v0.8-before-financial-tables-main.md), [당시 확인 기록](revisions/verification-v0.8-before-financial-tables-main.json): 비교표 네 개가 모두 부록에 있던 배치와 연속 주석 지원 설명을 보존했습니다.

- [v0.7 연속 주석 시스템 설명 추가 전 원고](revisions/PAPER-KO-v0.7-before-annotation-workflow.md), [당시 확인 기록](revisions/verification-v0.7-before-annotation-workflow.json): 선행연구 지원 상세 표와 본 연구의 기존 설명을 보존했습니다.

- [v0.6 검토 지원 상세 표 추가 전 원고](revisions/PAPER-KO-v0.6-before-review-support-details.md), [당시 확인 기록](revisions/verification-v0.6-before-review-support-details.json): 표 2의 금융·비금융 문구 정정까지 포함한 상태를 보존했습니다.

- [v0.5 기여·문헌 그룹 정리 전 원고](revisions/PAPER-KO-v0.5-before-contribution-clarification.md), [당시 확인 기록](revisions/verification-v0.5-before-contribution-clarification.json): 상세 표가 본문에 있던 상태와 이전 확인 범위를 보존했습니다.

- [v0.4 원문 재검토 전 원고](revisions/PAPER-KO-v0.4-before-feature-audit.md), [판정 데이터](revisions/COMPARISON-MATRIX-v0.4-before-feature-audit.json), [문헌 설명](revisions/LITERATURE-COMPARISON-v0.4-before-feature-audit.md): 이번 수정 전 상태입니다.

- [v0.3 기호 표 전 원고](revisions/PAPER-KO-v0.3-before-binary-feature-tables.md): 긴 셀 설명을 ○/빈칸 feature 표로 바꾸기 전 원고입니다. [이전 행 데이터](revisions/COMPARISON-MATRIX-before-binary-features.json)도 보존했습니다.
- [v0.1 구조 개정 전 원고](revisions/PAPER-KO-v0.1-before-contribution-rewrite.md): 세 기여 중심으로 재구성하기 전의 비교 대상입니다.
- [v0.3 EA 현황 재확인 전 원고](revisions/PAPER-KO-v0.3-before-ea-state-recheck.md): 계획 단계 설명을 코드 재확인으로 갱신하기 전 상태를 보존했습니다.
- [v0.2 비교표 확장 전 원고](revisions/PAPER-KO-v0.2-before-comparison-tables.md): 문헌 확장 전 초안을 보존했습니다.
- [이전 원고의 현황 확인](../20260924-paper-draft/CURRENT-STATE.md)과 [불일치 검토](../20260924-paper-draft/REVISION-AUDIT.md): 확인 시점이 적힌 과거 기록입니다.
- [2026-09-30 근거 스냅샷](../../../paper/20260930-naacl-finarch-draft/evidence/verified-repository-evidence.json): 원고 4.5절의 당시 구성 수 근거입니다. 이후 실행 상태 전체를 대신하지 않습니다.
- [제작 문서](../../../docs/01-dataset/README.md)와 [평가·분석 문서](../../../docs/02-experiments/README.md): 현재 요구·흐름을 읽는 기준입니다.

이 README는 src/finarch/documentation/templates/research/meeting-paper-draft-readme.md에서 생성했습니다. 저장된 PDF는 선행 논문을 읽기 위한 자료이며, 우리 원고의 최종 PDF를 제작한 것이 아닙니다.
