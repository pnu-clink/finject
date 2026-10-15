# 100문항 신규 제작 · {run_name}

입력: [{input_name}]({input_link}/README.md). TAT-QA 10 · easy 20 · medium 30 · hard 40건을 TAT-QA 1 → easy 2 → medium 3 → hard 4 순으로 반복 배치합니다. 이전 100문항의 원천 ID와 같은 Q/C는 제외하며 기존 LLM 응답을 재사용하지 않습니다.

## 실행과 확인

Preparation 전체 → 통과 문항의 Generation 7유형 → 차수별 Excel 보고서 → results 취합 순서입니다. 최대 3차이며 자동 실패·미평가·제외 이유를 보존합니다. 실패 해석 및 대상 모델 Evaluation/Analysis는 이번 제작 실행에 포함하지 않습니다.

POT은 gpt-6.1-sol / medium, 원문 검토·문장 생성·검증·EA 역산·피드백은 gpt-6-luna / max입니다. 현재 일반 API 병렬 방식이며 API 동시 요청 상한은 200입니다. 실제 모델·effort·프롬프트·스키마·토큰은 개별 호출 기록으로 확인합니다. 초기 전체 진행 약 1,900호출, 예상 $8~15는 이전 100문항의 사용량 기반 추정이고 실제 청구액이나 최대 비용이 아닙니다.

새 API 호출의 대기시간은 기존 300초를 유지합니다. 실행 설정은 사용자 승인 없이 바꾸지 않습니다. 이번 실행의 일시 변경과 사용자 지시에 따른 원복은 [대기시간 원복 기록](runtime-adjustments/001-api-wait/README.md)에 보존했습니다. 원복 전에 전송된 일부 요청에는 전송 당시의 대기시간이 적용됩니다.

읽는 순서:

1. [선별 계획](selection-plan.json) 및 입력 selection-manifest.json: 대상·순서·출처·제외 근거.
2. [사전 확인](preflight.json): 스키마·현재 모델·프롬프트 해시·키 설정 확인. 유료 호출이 아닙니다.
3. [전체 상태](full-pipeline-status.json) → [실행 로그](pipeline.log) → [프로세스 정보](process.json).
4. [Preparation 상태](01-preparation/summary.json) → 문항별 run.json·01/02/03-round.
5. [Generation 상태](02-generation/summary.json) → 차수별 final-validator.json·문항별 7유형.
6. 완료 후 [최종 취합본](results/README.md): 00-input.json 및 유형별 01~07 JSON, manifest·제외 로그.
7. [API 사용량](api-usage/README.md): 실패·재시도 포함 호출·토큰·공개 단가 추정 비용. 응답과 사용량이 없는 호출은 미확인으로 표시합니다.

아직 생성되지 않은 파일은 실행 진행에 따라 생깁니다. 미평가·미완료는 PASS가 아닙니다. results의 자동 PASS와 사람 판정은 구별합니다. 명시적인 사람 Reject은 Export에서 제외합니다.

공통 뷰어: http://127.0.0.1:8893/?run={run_name}. 공통 화면에서 이 실행을 선택하며, run 폴더별 HTML을 만들지 않습니다. 원문·표 변환·계산 그래프·수정 관계 문장·EA 역산의 수치 강조와 계산식을 저장 자료로 확인합니다.
