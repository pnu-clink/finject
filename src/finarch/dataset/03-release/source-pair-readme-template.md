# QI03 SOURCE/VALUE 별도 짝 보고 — {run_id}

실제 frozen SOURCE176건을 전부 분모에 남깁니다. SOURCE1은 같은 case VALUE-before, SOURCE2는 VALUE-after만 비교합니다. SOURCE1 대 SOURCE2의 단순 차이를 효과로 해석하지 않습니다. 새 API0입니다.

## 읽는 순서

1. `summary.json`: SOURCE1 86·SOURCE2 90의 전체/정확 매칭/제외/양쪽 완료/한쪽 이상 잘림/비교 가능한 cue 분모와 이유별 수.
2. `pair_manifest.json`: 모든176건의 dependency 경로·hash·정확 되돌리기 결과·A/B 원래/변경 정체성·실제 삽입 위치·양쪽 응답 상태/cue·제외 이유입니다.
3. `manifest.json`: 읽은 기존 frozen·생성·dependency·QI06 및 raw/result 입력 hash 불변 확인입니다.
4. `sidecar-schema.json`: 실제 보고서 JSON Schema입니다. LLM response schema가 아닙니다.
5. `events.jsonl`, `checks.txt`: 생성 단계와 fixture/실제자료/뷰어 검사입니다.

공통8892 viewer에서 `{run_id}`를 선택합니다. GET은 저장 JSON만 읽으며 source/base 원응답과 dependency·생성계획 hash 링크를 제공합니다. 브라우저 시각 확인은 메인 후속 확인입니다.

## 실제 계약과 제한

현행 `g02_generate_text.py`가 저장한 `02-generate-text/00-value-dependency.json`의 source 경로와 canonical observation_sha256을 그대로 검사했습니다. SOURCE의 generation_request C/Q가 base C/Q인지 확인하고, 허가된 단일 SOURCE_A/B insertion slot의 위치·before·element_ids와 saved patch를 대조했습니다. exact patch text를 정확한 offset에서만 제거하여 base C/Q와 완전 일치해야 MATCHED입니다. 정규식 문구 삭제·원본 보정·재생성은 하지 않습니다.

표 안의 출처는 TABLE_CELL이며 뒤 문장으로 취급하지 않습니다. 원래 A/변경 B 값은 claim의 앞/뒤 위치와 다릅니다. 출처별 SOURCE 계약·value_pair·target도 확인합니다.

일치하지 않는 쌍은 목록과 이유를 보존하되 cue 변화 집계에서 제외합니다. 일치하더라도 한쪽 잘림/누락이면 cue 비교를 하지 않습니다. 전체쌍·양쪽완료·cue비교가능의 분모를 구분하며 반복1만 다룹니다. 네 variant 공통 case 수는 목록 교집합이며 이 수로 자동 효과를 계산하지 않습니다.

QI06 의미와 A/B가 미확정이므로 의미효과 NOT_EVALUATED, A/B효과 UNRESOLVED입니다. lexical cue 변화는 충돌 이해·계산 정답·신뢰도 인과 효과가 아닙니다. 전수 judge·범용 parser·계약 수정·완전 교차 실험은 보류합니다.

## 실제 집계

```json
{summary}
```

## 재현

`PYTHONPATH=src .venv/bin/python -m finarch.dataset.03-release.source_pair_review --source reports/run/20260916-001 --quality-root reports/run/20260916-quality-v1 --screen-root reports/run/20260916-review-v2 --output reports/run/새로운-실행명`

기존 output을 거부합니다. 기존 생성·frozen·Qwen 결과를 쓰지 않고 새 보고서만 저장합니다.
