# RQ1 사분면 분석 자료 저장·검사 기록

## 목적과 범위

2026-10-03 사용자 요청으로 네 사분면 전체를 RQ1 분석 틀로 정리하고 docs의 A02 아래에 저장했습니다. 모델 호출·실험 실행·재채점·뷰어 결과 기능 구현은 수행하지 않습니다.

## 파일 역할과 읽는 순서

1. [RQ1 분석 자료](../../docs/02-experiments/02_analysis/02_comparison/01-rq1-pair-outcomes.md): 분석 목적, 사분면·유형·조건, 실패와 분모, null/classification, 의미 판정 및 뷰어 요구사항.
2. [A02 README](../../docs/02-experiments/02_analysis/02_comparison/README.md), [Analysis README](../../docs/02-experiments/02_analysis/README.md): 새 자료를 찾는 읽기 입구. 대응 단계 템플릿에서 생성합니다.
3. [events.jsonl](events.jsonl): 저장·검사 실행 이력과 변경 문서 해시.
4. [validation.json](validation.json): 이 작업의 링크·템플릿·색인·뷰어 문서 응답 확인 및 전체 문서 검사 결과. 의미 채점이나 사용자 화면 검토 결과와 구별합니다.

이 README는 [템플릿](../../src/finarch/documentation/templates/rq1-pair-outcomes-log.md)에서 생성합니다.

## 문서 뷰어

[공통 문서 뷰어에서 RQ1 자료 읽기](http://127.0.0.1:8893/?run=20260927-experiment-documentation&doc=docs%2F02-experiments%2F02_analysis%2F02_comparison%2F01-rq1-pair-outcomes.md). 기존 문서 run의 색인에서 새 자료를 선택합니다. 결과 폴더별 HTML을 생성하지 않습니다. E01/E02의 사분면 기능은 요구사항으로만 기록했습니다.

## 검사

`PYTHONPATH=src .venv/bin/python -B src/finarch/documentation/manage.py refresh`와 `validate`로 README·문서 색인·링크·보관 해시를 확인합니다. 전체 검사에 기존 오류가 있으면 이 문서의 확인 결과와 구분해 validation.json에 기록합니다. 실제 검사 결과는 해당 파일을 기준으로 읽습니다.
