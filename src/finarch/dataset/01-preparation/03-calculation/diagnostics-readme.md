# POT 실행·출처 검사 진단

검증 전 코드입니다. 다음 단계에 사용할 승인 산출물이 아닙니다.

읽는 순서: `01-response.json` 원응답 → `02-program.py` 추출한 원본 코드 → `03-context.json` 근거 확인용 본문 → `04-execution/result.json` 격리 실행 → `05-response-check.json` 출처를 포함한 응답 검사 → `06-summary.json` 두 결과 요약.

Python 코드는 `fact()` 등의 실행 환경을 사용하므로 직접 `python 02-program.py`로 실행하지 않습니다. 프로젝트 루트에서 다음 명령을 사용합니다. OUTPUT은 아직 없는 새 디렉터리로 지정합니다.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.03-calculation.diagnostics --response PATH/01-response.json --context PATH/03-context.json --output OUTPUT
```

기존 Python 실행기의 숫자·본문 대조, 외부 근거 카탈로그 확인 및 OS 격리를 유지합니다. 출처 연결 검사가 실패해도 격리 실행 결과를 보존합니다. 실행 성공은 출처·의미·gold 일치를 보장하지 않습니다. 기존 응답과 실패 판정은 덮어쓰지 않습니다. 공통 뷰어의 해당 문항 03-calculation에서 두 결과를 확인할 수 있습니다.
