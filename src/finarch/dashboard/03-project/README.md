# 프로젝트 현황 조회 코드

[대시보드 실행 흐름](../../../../docs/03-dashboard/README.md) · [화면](../../../../viewer/dashboard/03-project/README.md)

|파일|역할|
|---|---|
|[monitor.py](monitor.py)|로컬 Codex 세션 DB와 저장된 문서·실행 상태를 읽어 현재 현황 JSON을 조립합니다. 기록을 수정하지 않습니다.|
|[session-map.json](session-map.json)|확인한 주요 세션 ID를 업무 묶음에 연결합니다. 부모·자식 관계의 근거로 사용하지 않습니다.|

`load_project_data()`는 프로젝트 경로와 Codex 기록 경로를 받아 세션, 실행, 미완료, 서버 상태를 반환합니다. 예를 들어 분석 run에 `BLOCKED`가 저장되어 있으면 해당 run의 `state.json`을 근거로 `차단` 항목을 만듭니다. 세션 DB가 없으면 세션을 0건으로 돌려주고 경고를 남깁니다. 화면의 실제 부모·자식은 `thread_spawn_edges`에 있는 생성 관계에서만 읽습니다. 조회 중 모델 호출이나 테스트 실행은 없습니다.
