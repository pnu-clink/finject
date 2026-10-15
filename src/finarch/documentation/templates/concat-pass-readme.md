# {output_name} · 7유형 전체 통과본

**{after_all_seven_pass}문항**, 원문 + 7변형 = **{after_all_seven_pass}개의 8종 세트**입니다. `00-input.json`과 아래 7유형 파일은 같은 ID·순서·수량을 가지며 원문 Preparation과 모든 유형 상태가 PASS입니다.

|파일|내용|
|---|---|
|[00-input.json](00-input.json)|원문 Q/C/A·Preparation 상태·외부정보 사용 여부|
|[01-ic-value-before.json](01-ic-value-before.json)|IC-VALUE 앞|
|[02-ic-value-after.json](02-ic-value-after.json)|IC-VALUE 뒤|
|[03-ic-source-type-1.json](03-ic-source-type-1.json)|IC-SOURCE Type 1|
|[04-ic-source-type-2.json](04-ic-source-type-2.json)|IC-SOURCE Type 2|
|[05-ic-relation.json](05-ic-relation.json)|IC-RELATION|
|[06-ea-earlier-input.json](06-ea-earlier-input.json)|EA-01|
|[07-ea-later-input.json](07-ea-later-input.json)|EA-02|
|[manifest.json](manifest.json)|파일 수량·해시·문항별 원천 run|

기존 다른 출처 {unchanged_all_seven_pass}문항과 새 CodeTAT-QA {replacement_all_seven_pass}문항으로 구성됩니다. EA 역산 가능 여부는 선정 기준에 추가하지 않았습니다. 자동 PASS는 사람 승인이나 의미상 완전한 품질을 뜻하지 않습니다. 원래 pipeline 경로는 `manifest.json.row_source_runs[id]`의 run을 기준으로 해석합니다. [전체 기록](../README.md)과 [데이터셋 안내](../../README.md)는 별도로 보존했습니다.
