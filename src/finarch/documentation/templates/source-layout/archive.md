# 2026-09-24 소스 구조 변경 전 보관본

[현재 소스 구조](../../docs/01-dataset/90-operations/05-source-layout.md) · [이동 대응표](../../log/source-layout-20260924/migration.json)

`source-before.tar.gz`는 이동 직전 작업 파일의 원본 바이트이며, `manifest.json`은 원래 경로별 SHA-256입니다. Git의 과거 커밋이 아니라 당시 미커밋 변경도 포함한 실제 작업본입니다. 보고서·원천 데이터·실험 run은 이 보관본의 이동 대상이 아닙니다.

과거 보고서에 기록된 소스 경로와 해시가 일치할 때에만 `src/finarch/shared/source_archive.py`가 이 원본을 읽습니다. 현재 소스와 서로 바꾸어 제시하거나 과거 결과의 해시를 재작성하지 않습니다. 새 작업은 현재 `src/finarch`를 사용합니다.
