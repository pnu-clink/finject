# {run} · 생성 데이터 단일 취합본

`dataset.jsonl`은 **한 줄에 원문 1개와 7유형**을 담은 데이터 파일입니다. 원문·변형의 실제 question/context, 원본 정답·정밀도·단위·출처, 자동 검사 상태와 제작 판정이 포함되어 `reports/run` 없이 읽을 수 있습니다. 이는 연구용 제작 기록이며 대상 모델에 그대로 입력하지 않습니다.

|항목|개수|
|---|---:|
|전체 문항|{cases}|
|7유형 슬롯|{variant_slots}|
|실제 Q/C가 저장된 변형|{saved_variants}|
|기존 7유형 통과·Reject 없음 기준 충족|{production_eligible_cases}|
|제작 Reject가 있는 문항|{production_rejected_cases}|
|평가자 annotation 연결 항목|{annotated_items}|
|평가자 미검토 항목|{unreviewed_items}|

## 읽는 순서

1. `manifest.json`: 전체 취합 정책·기존 선정 정책·개수·원천 해시·annotation 상태.
2. `dataset.jsonl`: `source_input`은 준비 원천, `original`은 최종 Preparation 입력, `variants`는 정해진 순서의 7유형입니다. 각각 실제 Q/C와 내용 해시를 포함합니다. 미생성 유형은 Q/C가 null이고 NOT_RUN이며, 정답을 임의로 만들지 않습니다. 변형의 정답은 원문 정답과 같다고 가정하지 않습니다.
3. `dataset.schema.json`: 문항·유형·판정 구조. `events.jsonl`: 취합 시각·개수·LLM 호출 0 기록.
4. [공통 뷰어](http://127.0.0.1:8893/?run={run}): 해당 실행의 **생성 데이터 합본** 버튼에서 저장 파일의 원문·7유형·상태를 확인하고 다운로드합니다. 별도 결과 HTML을 만들지 않습니다.

## 실패·Reject·미검토

전체 취합은 실패·미평가·Reject까지 보존합니다. `production_selection.eligible`만 기존 **Preparation PASS + 7유형 전부 PASS + 명시적 Reject 없음**을 표시합니다. 기존 평가자 HTML과 `results/`의 선정 규칙은 바꾸지 않습니다.

`automatic_validation`은 자동 검사, `production_review`는 제작 판정입니다. `annotation.status=UNREVIEWED`와 빈 ratings는 별도 평가자의 판정을 연결하지 않은 상태이며 Accept가 아닙니다. 자동 PASS도 의미 정답이나 사람 승인을 뜻하지 않습니다.

최종 human annotation 통과 목록과 대조하여 반영한 변형은 `annotation={{"ratings": [], "status": "PASS"}}`로 표시할 수 있습니다. 이 형식은 통과 상태만 제공하며 평가자별 상세 결과는 담지 않습니다. 해당 목록 밖 문항과 원문의 annotation은 변경하지 않습니다. 자동 취합의 기본 annotation은 계속 UNREVIEWED입니다.

## 이후 annotation 연결

`annotation.schema.json`의 rating 구조에 따라 format이 `finarch-generated-annotations-v1`인 JSON의 `ratings` 목록을 준비합니다. 각 rating에는 `item_id`, `content_sha256`, `reviewer`, `decision`(APPROVED/REJECTED/PENDING), `confirmed`, `comment`, `updated_at`을 기록합니다. ID와 Q/C 해시가 모두 일치해야 연결합니다. 여러 평가자의 이견을 그대로 저장하며 임의로 최종 판정을 만들지 않습니다. 기존 평가자 HTML JSON은 내용 연결 근거 없이 ID만으로 강제 Import하지 않습니다.

```shell
# 현재 산출물을 읽어 취합합니다. 생성·API 호출은 없습니다.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.03-release.publication.consolidate \
  --run reports/run/{run}
# annotation을 연결할 때는 --annotations PATH_TO_RATINGS_JSON과
# --output PATH_TO_NEW_ARCHIVE_DIRECTORY를 추가합니다. 기존 합본은 덮어쓰지 않습니다.
```

Generation 정상 전체 실행은 모든 차수·검토 자료·리포트 저장 후 자동으로 취합합니다. 부분 단계 실행·실패 해석·실패 재검토만 실행한 경우에는 자동 취합하지 않습니다. 이 README는 `src/finarch/documentation/templates/generated-dataset.md`에서 생성했습니다.
