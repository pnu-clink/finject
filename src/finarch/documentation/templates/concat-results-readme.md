# {output_name} · 전체 합본

전체 {input_count}문항입니다. CodeTAT-QA {replaced_count}문항의 원문 입력과 7유형을 새 결과로 모두 교체했습니다. 자동 실패와 미실행을 포함하며 원천 실행의 행을 그대로 보존했습니다.

|파일|내용|
|---|---|
|[00-input.json](00-input.json)|원문 입력·정답·Preparation 상태·외부정보 사용 여부|
|[01-ic-value-before.json](01-ic-value-before.json)|IC-VALUE 앞|
|[02-ic-value-after.json](02-ic-value-after.json)|IC-VALUE 뒤|
|[03-ic-source-type-1.json](03-ic-source-type-1.json)|IC-SOURCE Type 1|
|[04-ic-source-type-2.json](04-ic-source-type-2.json)|IC-SOURCE Type 2|
|[05-ic-relation.json](05-ic-relation.json)|IC-RELATION|
|[06-ea-earlier-input.json](06-ea-earlier-input.json)|EA-01|
|[07-ea-later-input.json](07-ea-later-input.json)|EA-02|
|[manifest.json](manifest.json)|각 파일 수량·해시·문항별 원천 run|

실험에 사용할 7유형 전체 통과본은 [all-seven-pass](all-seven-pass/README.md)에 {after_all_seven_pass}문항을 같은 8파일 구조로 저장했습니다. 전체 합본은 성공·실패를 함께 보존합니다. 원래 pipeline 경로는 `manifest.json.row_source_runs[id]`의 run을 기준으로 해석합니다. 상위 run 폴더에 선택된 원천 문항의 Preparation·Generation 단계 기록을 함께 복제하여 기존 검증 화면을 사용합니다.
