# FinanceReasoning 데이터셋 제작 흐름 PNG

읽는 순서: [논문 그림 자산 PNG](../../../../paper/asset/dataset-pipeline-2238-to-1080.png) → `figure-data.json` → `figure-log.jsonl`입니다. PNG는 `paper/asset`에, 수량 근거와 생성 기록은 이 실행 폴더에 둡니다.

- [paper/asset/dataset-pipeline-2238-to-1080.png](../../../../paper/asset/dataset-pipeline-2238-to-1080.png): 원천 2,238건부터 7개 type 모두 자동 검사 PASS인 1,080문항까지의 좌→우 흐름입니다. Preparation 통과 문항 1,838건이 일곱 type으로 각각 확장되는 경로, 공통 검사, type별 최종 PASS/FAIL/미평가, 원문 ID별 AND/OR 합류를 본문에 표시합니다. 마지막 AND 상자에는 1,080문항의 난이도별 내역을 Easy 494 · Medium 513 · Hard 73으로 표시합니다. 아래 패널에는 원천 선정·Preparation·Generation의 단계별 최종 중단 수를 표시합니다.
- `figure-data.json`: 그림에 사용한 수량, 난이도별 선정/제외와 1,080 통과 내역, 최종 중단 위치, type별 판정, 원천 파일 SHA-256입니다.
- `figure-log.jsonl`: 저장 자료 읽기·수량 대조·PNG 생성 기록입니다.

숫자의 단위가 다릅니다. 2,238→2,050→1,838→1,080은 **원문 문항 수**이며, 12,866·11,199·1,664·3은 **문항×type 결과 수**입니다. 1,838개의 원문은 type마다 한 번씩 나타나므로 일곱 줄의 1,838을 더해 원문 수로 해석하면 안 됩니다. `AND`는 일곱 type 모두 PASS인 1,080문항(Easy 494 + Medium 513 + Hard 73), `OR`는 하나 이상 FAIL 또는 미평가인 758문항을 뜻합니다. 난이도는 원천 파일에 연결된 원문 ID에서 집계합니다. 단계 옆 `final stops`는 재시도 뒤 최종 중단 위치이고, 해당 단계에 들어온 전체 수나 재시도별 실패 횟수가 아닙니다. 1,080은 저장된 자동 검사 결과로, 사람의 의미 정답 판정이나 데이터셋 최종 배포 수량이 아닙니다.

그림은 `src/finarch/dataset/90-operations/analysis/pipeline_figure.py`가 저장된 원천 선정 manifest, 실행 phase report, 실패 분석 자료를 읽어 생성합니다. 원본 데이터·제작 상태를 바꾸거나 모델을 호출하지 않습니다. 보고서와 문항별 근거는 상위 [README](../README.md)를 따라 공통 뷰어에서 확인합니다.
