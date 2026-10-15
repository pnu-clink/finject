# 소스 영역·단계 정리 확인 기록

[소스 정의·파이프라인 대응](../../docs/01-dataset/90-operations/05-source-layout.md) → [세 서버 실행](../../viewer/README.md) → [검사 요약](verification.json) 순서로 읽습니다.

- `migration.json`: 이동 직전 파일 해시·이전/새 경로. 후속 단계 조정은 `final-layout.json`에 함께 기록합니다.
- `before-python.json`, `after-python.json`: 이동 전후 같은 오프라인 검사 결과. 외부 네트워크·모델 CLI를 차단합니다.
- `regression-comparison.json`: 기존 실패와 신규 실패를 구분한 비교.
- `dataset-js-comparison.json`: 같은 저장 자료로 실행한 데이터셋 화면 검사 전후 비교.
- `relocation-regressions.log`, `shared-tests.log`: 이동 경로·대시보드·공통 실행기·과거 소스 보존 검사.
- `experiment-viewer-tests.log`: 실험 뷰어의 저장 자료·정렬·키보드·Export·서버 실행 검사.
- `docs-validation.json`: 문서·README 템플릿·이전 보관본 해시 검사.
- `browser-checks.json`: 실제 서버·화면 확인.

이 작업은 소스 구조 변경이며 모델 호출·실험 재실행을 수행하지 않습니다. 과거 source 참조는 해시가 같은 [보관본](../../archive/20260924-source-layout/README.md)으로 검증합니다. 기존에 실패하던 검사까지 전체 통과했다고 보고하지 않습니다.
