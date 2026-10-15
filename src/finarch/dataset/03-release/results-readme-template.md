# {run_name} · 취합된 제작 결과

읽는 순서: `manifest.json` → `00-input.json` → `01-...json`부터 `07-...json`까지. 원본 파일은 {count}행이며, 유형별 파일은 제외되지 않은 문항만 같은 원본 순서로 저장합니다. 파일별 행 수는 manifest에 있습니다. 행 위치 대신 `id`로 원본과 변형을 연결합니다.

**Export 기준:** {export_policy_note} 실험의 PASS·7유형 완성 조건은 별도입니다. 원래 생성 파일·판정·과거 차수는 변경하지 않습니다.

- `00-input.json`: 문항별 Preparation 입력과 현재 상태. `input`에는 private 기준 정답도 포함됩니다.
- 각 원본 행의 `external_knowledge`는 private 제작 분류입니다. `used=true`는 **최종 Preparation PASS**, 계산 그래프의 정답 경로에 실제 사용으로 기록된 외부 유형, 그리고 `05-verification`의 PASS·EXTERNAL·필요 유형이 모두 일치한 경우뿐입니다. `used_types`에는 일치한 `EXTERNAL_RULE`/`EXTERNAL_DATA`만 기록합니다. 그 밖은 `used=false`, `used_types=[]`이며, 이 `false`는 외부정보를 쓰지 않았다는 증명이 아니라 확정 조건 미충족을 뜻합니다. 이전 풀이의 사용 선언과 검증기의 필요 판정을 혼동하지 않습니다.
- `01`~`07`: 유형별 최종 저장 상태와 생성된 Q/C. `source`는 실제 생성 문장 파일, `result`는 유형의 차수 폴더입니다.
- 각 행의 `edit_provenance`: 원본 → 값 변경 → 출처 추가 순서, 단계별 원문 위치·치환 전후 문자열·색상 구분용 `segments`, Q/C 해시와 제작 비교 파일의 경로·해시입니다. 새 데이터 파일을 따로 만들지 않습니다.
- `status=PASS`: 자동 검사를 통과했습니다. 사람 승인이나 의미 정답 판정은 별도입니다.
- `status=FAIL` 또는 `NOT_EVALUATED`: 생성된 Q/C가 있을 때는 함께 보존합니다. 실험 입력에 자동 포함하지 않습니다.
- `status=NOT_RUN`: 해당 문항·유형의 생성 기록이 없습니다. 명시적으로 Reject되지 않은 준비 단계 미통과 문항도 목록에 남습니다.
- `manifest.json`: 각 파일의 행 수·상태 수·SHA-256, 외부사용 분류 건수와 원래 Generation 결과 보고서의 SHA-256입니다.
- `export-log.json`: 취합 시각·결과 수와 외부사용 분류의 실제 근거 경로·SHA-256을 기록합니다. Preparation data에 정답·precision 메타정보가 빠진 경우 같은 Q/C의 accepted-input에서만 보완하며 `reference_metadata_repairs`에 원천 해시와 보완 필드를 남깁니다. 원래 data.json은 변경하지 않습니다. 기존 결과에 변경 이력만 보강한 경우 `edit_provenance_revisions`에 전후 파일 해시·내용 보존 여부를 남깁니다. 과거 취합 결과에 외부사용 분류를 나중에 보완한 경우 `external_knowledge_revisions`에 시각·근거·전후 해시를 남기고 원래 `00-input.json` 바이트를 `revisions/`에 압축 보존합니다. 생성 당시부터 있던 분류로 간주하지 않습니다.

새 실험의 기본 설정은 이 폴더를 필수로 요구합니다. 해시·문항 순서·유형과 현재 실행 상태를 검사한 뒤, `PASS` 행의 Q/C와 원본의 precision으로 완성된 public 모델 입력을 만듭니다. 기준 정답·유형·제작 이력·`edit_provenance`·`external_knowledge`는 private 영역입니다. 이 분류를 실험의 Analysis로 전달할 때도 public Q/C·precision에는 넣지 않습니다. 과거 실험의 동결 입력을 재사용하는 별도 설정은 이 경로를 우회하므로 함께 켤 수 없습니다. 원본 실행 폴더의 파일은 그대로 보존합니다.

읽는 순서: 원본 행 → 같은 ID의 변형 → `edit_provenance.steps`. IC-source는 첫 단계의 IC-value 위치를 원본 C에서 읽고, 두 번째 단계의 출처 위치를 **값 문장이 추가된 C**에서 읽습니다. 위치는 유니코드 문자 단위의 `[start, end)`입니다. 두 단계를 같은 기준의 위치로 합치지 않습니다.

|변경 이력 상태|뜻과 뷰어 처리|
|---|---|
|VERIFIED|저장된 편집을 순서대로 적용하면 최종 Q/C와 일치. 값 문장은 초록, 출처 A는 분홍, 출처 B는 빨강으로 함께 표시|
|UNAVAILABLE|Q/C 또는 편집 기록이 없어 확인 불가. 변경 없음으로 표시하지 않음|
|MISMATCH|기준 원문·위치·전후 문자열·해시·복원 결과 불일치. 색상을 추측하지 않고 사유 표시|

`VERIFIED`는 편집 기록의 일치일 뿐, 문제·답변의 의미 정답이나 사람 승인이 아닙니다. 삭제한 문자열은 편집 기록으로만 보이고 실제 모델 입력 C에 다시 넣지 않습니다.

재생성 명령: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m finarch.dataset.03-release.export_run_results reports/run/{run_name}`

기존 Q/C·상태를 유지한 변경 이력 보강: 같은 명령에 `--edit-provenance-only`를 붙입니다.

기존 Q/C·상태·7유형 파일을 유지한 외부사용 분류 보완: 같은 명령에 `--external-knowledge-only`를 붙입니다. 이 작업은 저장된 제작 기록을 읽는 Python 처리이며 모델을 다시 호출하지 않습니다.
