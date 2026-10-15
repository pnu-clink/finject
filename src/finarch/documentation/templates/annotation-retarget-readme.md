# {run} · 평가 Import 대상 변경

대상 HTML: `{html_path}`  
배포본 ID: `{package_id}` · 차수: `{round}` · {case_count}문항

기존 concat-001용 평가 파일을 이 HTML의 **Import**에서 읽을 수 있도록 수정했습니다. 원본 파일과 대상 HTML, 제작 데이터는 변경하지 않았습니다.

## 가져올 파일

- `{first_file}`
- `{second_file}`

평가자별로 별도 탭에서 해당 파일 하나를 Import하세요. 두 평가 파일을 같은 화면에 연속 Import하면 현재 실행의 판정이 나중에 가져온 평가자의 판정으로 교체됩니다.

## 변경한 내용

1. `package_id`: concat-001의 배포본 ID → 실제 대상 concat-002 HTML의 ID.
2. `run`: `20261003-concat-001` → `{run}`.
3. `cases`: 실제 HTML의 1,260문항 목록과 순서로 맞췄습니다. 미평가 문항인 `test-1111`은 빠지고 `test-0803`이 포함됩니다. 기존 1,000문항의 평가 목록은 그대로입니다.
4. `conversion`: 대상 HTML 경로·해시와 변경 근거를 기록했습니다. 차수 `03-round`는 유지했습니다.

각 평가자의 기존 1,000문항 × 7유형 = 7,000판정, 주석·체크 항목·추가/삭제 문장·확인 여부·평가 시각은 그대로입니다. 이전 HTML과 대상 HTML의 해당 문항 원본·변형·그래프·검증 자료를 비교했으며 run 경로 이동을 제외한 내용과 유형별 snapshot은 동일합니다. 재생성된 CodeTAT-QA 260문항에는 판정을 넣지 않았습니다. 기존 제외 기록은 concat-001 변환 폴더에 보존되어 있습니다.

## 확인 자료와 읽는 순서

1. 위 두 JSON: 실제 Import용 파일.
2. `validation.json`: 원본·수정본·대상 HTML 해시, 내용 보존 및 Import 검사 결과.
3. `terminal.log`: 변환·검사 실행 로그.
4. `target-package.json`: 실제 HTML의 배포본·문항·유형 정보.
5. `import-validator.cjs`: 대상 HTML의 실제 Import 검사 함수로 검증합니다.

```shell
node annotation/20261001/import-20261003-concat-002/import-validator.cjs
# 대상 HTML에서 추출한 실제 가져오기 검사로 두 JSON을 확인합니다.
```

뷰어는 위 대상 HTML을 그대로 사용합니다. JSON 수정으로 HTML의 차단 규칙을 우회하거나 제작 데이터의 판정을 바꾸지 않습니다. 실제 브라우저 Import 수행 여부는 `validation.json`에 별도로 기록합니다.
