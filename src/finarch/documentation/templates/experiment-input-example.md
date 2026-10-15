# 새 public/private 입력 예시 — 모델 호출 없음

[작업 기록](../README.md) · [E01 입력 분리](../../../../docs/02-experiments/01_evaluation/01_preparation/README.md) · [E02 요청](../../../../docs/02-experiments/01_evaluation/02_request/README.md)

저장된 dataset `20260917-002/results`에서 선정 조건을 충족한 원문 1개와 7변형을 읽어 **현재 준비 코드로 만든 자료**입니다. Luna의 P0/P1·추론 OFF/ON 조합으로 30개 요청을 준비했으며 대상 LLM 호출은 없습니다.

**풀이 LLM에 보내는 문제 데이터는 public의 질문(Q)·본문(C)·precision뿐입니다.** `item_id`는 제외합니다. 문항 연결·실험 조건·prompt·schema는 모델별 요청 manifest에서 확인합니다. 이전 예시의 `input-selection.json`은 제거하고 선정 경위를 기존 방식의 `events.jsonl`로 옮겼습니다.

|파일|역할|
|---|---|
|[public.jsonl](public.jsonl)|모델이 문제를 풀 때 사용할 Q/C와 `answer_format.decimal_places`. item_id는 연결용|
|[private.jsonl](private.jsonl)|응답 평가용 정답·유형·제작 근거·원문/변형 연결|
|[luna-api/01-requests/manifest.jsonl](luna-api/01-requests/manifest.jsonl)|실행 기준: 문항 연결·모델·P0/P1·추론 조건·prompt·schema·input. 30행, 고유 문항 8개|
|[events.jsonl](events.jsonl)|INPUT_SELECTION: 선정 순서·규칙·제외 사유·출처 확인. 실행 대상을 복원하는 별도 입력으로 쓰지 않음|
|[request-inputs.jsonl](request-inputs.jsonl)|public에서 item_id를 제외한 실제 전송 입력. private 참조 없음|
|[checks.json](checks.json)|8개 public/request 입력 일치·자릿수 포함·출처 파일 해시 보존 확인|

precision은 입력 분리 시 dataset 원자료에서 public에 담습니다. private의 reference_precision은 평가 참조로 유지하지만 요청 작성에서는 읽지 않습니다. public에 precision이 없으면 private로 보충하지 않고 준비를 중단합니다.

이 README는 템플릿에서 생성합니다. 상세 원자료 해시와 처리 수량은 checks에, 수행 이력은 상위 events에 남깁니다.
