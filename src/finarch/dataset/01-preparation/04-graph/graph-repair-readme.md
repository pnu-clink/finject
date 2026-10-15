# 계산 그래프 변환기 보완 검증

기존 POT와 정답을 변경하지 않고 Python을 재실행하여 그래프의 모든 변수와 최종값을 대조했습니다. LLM 호출은 없습니다.

읽는 순서: `01-read-calculation` 입력·Python 결과 → `02-build-graph` 변환 기록 → `03-compare-calculation` 일치 여부 → `04-save-graph` 표시할 그래프입니다. 공통 뷰어에서 해당 실행·문항의 Preparation **04 계산 그래프**를 선택하면 읽을 수 있습니다.

이전 그래프 실패 파일은 문항의 `graph-repair-history`에 보존합니다. `graph-repair.json`은 이번 보완 검증입니다. 재검증 통과 후 현재 `run.json`과 사람 검토용 자동 결과를 PASS로 갱신합니다. 이전 실패 결과와 배치 요약은 이력에 보존하고, 사용자가 저장한 사람 판정은 변경하지 않습니다. 완료 보고서·엑셀은 당시 실험의 기록입니다.
