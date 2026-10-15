# Analysis feature 사분면 맵

## 읽는 순서

1. `RESEARCH-DIRECTION.md`: Luna·Haiku 전체 지도와 항목별 M01–M23 지도.
2. `feature-map.json`: 각 항목의 조건별 표시 내용, 저장 해석·실제 인용·응답 ID.
3. `source-snapshot.json`: 읽은 자료의 경로·해시·집계 작성 시각.
4. `events.jsonl`: 자료 제작 기록. 원본 실험 이벤트를 대신하지 않습니다.

## 뷰어와 그림

[연구자료 단일 화면](../../../viewer/research/index.html)에서 **Analysis 사분면 맵**을 선택합니다. `figures/`의 SVG는 기존 뷰어에 삽입하기 위한 그림입니다. 결과 폴더에 별도 뷰어 HTML을 만들지 않습니다.

[독립 HTML 자료](../../../outputs/research/20260928-analysis-quadrant-map/analysis-quadrant-map.html)는 두 전체 지도와 23개 항목을 포함합니다. 항목 제목을 눌러 지도를 펼칩니다. 원응답의 내용은 인용 상자, 저장된 분석자의 해석은 일반 문단으로 구별합니다.

## 관찰 범위

Luna `20260927-exp-007-luna`와 Haiku `20260927-exp-008-haiku`의 저장 Analysis를 시각화합니다. 네 조건은 독립 반복이 아닙니다. 정량 그림은 원래 전체 분모를 보존하며 수치/null 필드가 있는 형식 실패도 포함합니다. 형식 실패·미수집은 M04에서 별도로 읽고, 양쪽 형식 유효 대응쌍은 M13에서 읽습니다. null·CONFLICT·숫자 일치가 의미 정답을 뜻하지 않습니다.

M14–M20은 저장된 태그로 연결한 정확 인용 예시이며 발생률·분면 우세가 아닙니다. 사례 미선정은 현상 부재가 아닙니다. M21–M23은 미집계 또는 제안으로 남겼습니다. 논문 본문의 결과·결론, 실험·Analysis 구현과 원응답은 수정하지 않았습니다.

## 제작과 확인

이 README는 `src/finarch/documentation/templates/research/quadrant-map-readme.md`에서 생성합니다. 표시 자료 생성은 `src/finarch/documentation/research_quadrant_map.py`가 담당하며 Analysis 파이프라인을 실행하지 않습니다. 기존 집계의 비율 표시·정확 인용 연결만 수행합니다.

[확인 기록](../../../log/research-quadrant-map/20260928/README.md)에서 원자료 보존과 화면 검사를 구분해 읽습니다. 스타일은 기존 연구자료의 흰색·녹색과 system-ui 글꼴을 따릅니다.
