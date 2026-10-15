# 결과 선정·전달

[문서의 단계·요구·실행 흐름](../../../../docs/01-dataset/03-release/README.md) · [전체 소스 구조](../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[export_run_results.py](export_run_results.py)|현재 제작 결과를 유형별 JSON으로 취합합니다. `prepare_copy()`/`--prepared-output`은 이미 취합된 결과를 새 `data/prepared` 폴더에 해시 확인 후 복사하고 전달 manifest·로그·템플릿 README를 작성합니다. 원천 run은 보존합니다.|
|[concat_results.py](concat_results.py)|두 취합본의 해시·ID·Q/A를 확인하고 지정 출처 전체를 8파일에서 교체합니다. 전체 기록과 7유형 모두 PASS인 선정본·원천 run 지도·로그를 새 폴더에 저장하며 LLM을 호출하지 않습니다.|
|[export_policy.py](export_policy.py)|현재 차수의 사람 Reject·Exclude를 제외합니다. 원본은 전체, Generation은 해당 유형만 제외하며 자동 FAIL·Pending과 구별합니다.|
|[publication/consolidate.py](publication/consolidate.py)|전체 Generation 종료 후 data/generated에 실제 원문·7유형의 단일 JSONL·manifest·로그·README를 생성합니다. 실패·Reject 기록을 보존하고 기존 7유형 선정 조건을 표시합니다.|
|[publication/schema.py](publication/schema.py)|원문·7유형 구조와 내용 해시, 평가자 rating의 ID·내용 해시 연결을 검증합니다.|
|[edit_provenance.py](edit_provenance.py)|원본→VALUE→SOURCE 편집 복원과 현재 Q/C 해시를 확인합니다.|
|[external_knowledge.py](external_knowledge.py)|검증 통과·실제 사용·필요 조건이 맞는 외부정보 유형만 기록합니다.|
|[original_baseline.py](original_baseline.py)|Prepare original Q/C only; never execute a baseline or import its runner.|
|[response_screen.py](response_screen.py)|Explicit, immutable-input first-repeat screening. No provider calls.|
|[review_first_repeat.py](review_first_repeat.py)|Explicit v2 entry point. Import never reads or writes legacy review artifacts.|
|[source_pair_review.py](source_pair_review.py)|Match each frozen SOURCE to its saved VALUE dependency; no generation or API calls.|
