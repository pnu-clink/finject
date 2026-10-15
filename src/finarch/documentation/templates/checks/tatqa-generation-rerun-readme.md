# {run_name} · TAT-QA Generation 재생성

`{source_run}`의 Preparation을 독립 복제하고 현행 프롬프트로 Generation 7유형을 새로 생성합니다. 원본 {input_count}문항 중 Preparation PASS {approved_count}문항 × 7유형 = {variant_count}건이 대상입니다. 기존 FAIL {rejected_count}문항의 실패 기록은 유지합니다. Preparation의 원응답·날짜는 이전 실행의 기록이며 신규 모델 호출은 없습니다.

## 실행 프로그램

```shell
PYTHONPATH=src .venv/bin/python -u -B -m finarch.dataset.02-generation.generate_schedule \
  --run reports/run/{run_name}
# 기존 scheduler로 변경 계획 → 문장 생성 → 검증 → 실패 피드백 → 사람 검토 자료를 처리합니다.

PYTHONPATH=src .venv/bin/python -u -B -m finarch.dataset.03-release.export_run_results \
  reports/run/{run_name}
# Generation 종료 후 최신 차수 결과를 유형별 JSON으로 취합합니다.
```

`start-generation.sh`는 이 두 프로그램을 차례로 호출합니다. 중단된 Generation을 재개할 때만 `start-generation.sh --resume`을 사용합니다. 새로운 Python 재생성 프로그램은 만들지 않습니다.

## 모델과 대상

실제 모델은 이전 요청과 동일한 **gpt-5.6-luna / max / API**입니다. run 안의 `hyperparameter.json`과 `codex-profiles.toml`에 정확한 버전을 지정했습니다. 문장 생성, 완성문 검증, EA 역산 검토, 오류 피드백에 동일한 모델을 사용합니다. API 동시 처리 200, 유형 동시 처리 5, 최대 3차, 출력 한도 32,768토큰, 총 토큰 예산 500,000입니다.

과거 Generation은 9,332회 호출했습니다. 저장된 토큰과 프로젝트 단가를 적용한 캐시 할인 없는 소계는 약 $27.64입니다. 이번에는 EA 역산 검토와 재시도를 고려해 약 10,000~12,000회, **$30~60**을 예상합니다. 추정 금액이며 실제 청구액이나 지출 한도가 아닙니다.

IC-RELATION의 추가 문장은 표의 마지막 행 뒤에 독립 문단으로 생성하는 현행 로직·프롬프트를 사용합니다. EA 역산 가능 여부는 근거와 함께 기록하며 그 여부만으로 실패시키지 않습니다. 기존 source run과 concat·annotation은 수정하지 않습니다.

## 재시작 전 보정 · 2026-10-03

첫 실행에서 발견한 입력 연결·숫자 표기 오류를 수정하고 해당 실행 자료를 `restart-history/001-reference-metadata-handoff/`에 보존했습니다. 작업 입력의 정답 메타데이터가 누락된 1건은 같은 ID·질문·본문의 accepted 입력에서 메모리로 보완합니다. IC-RELATION은 날짜 `December 28, 2018`을 숫자로 읽지 않고, `1,609,000` 같은 금액을 기존 등록 숫자 규칙으로 계산합니다. 원문·이전 Preparation·정답을 바꾸지 않습니다.

`reference-handoff-repair.json`에는 668건의 정답 연결 검사, `relation-numeric-repair.json`에는 668건·1,427개 입력 숫자 사전검사와 실제 오류 2건의 수정 후 계획을 기록했습니다. 유료 호출 없는 회귀 검사 22개가 통과했습니다. 최초 중단 시 저장된 사용량은 없으나 이미 시작한 호출의 청구가 없다는 의미는 아닙니다. 이후 실행은 기존 Generation scheduler로 처음부터 다시 진행합니다.

## 읽는 순서와 화면

1. `sequence-status.json`: 실행 중 / 취합 중 / 종료 상태.
2. `terminal.log`, `02-generation.log`, `03-export.log`: 기존 프로그램의 실제 출력과 오류.
3. `preparation-reuse.json`: 복제 파일 해시, Preparation PASS/FAIL 목록.
4. `model-preflight.json`, `authorization.json`, `prompt-code-snapshot.json`: 호출 전 모델·스키마·요청 범위와 소스 해시.
5. `02-generation/*-round/progress.json`, `02-generation/summary.json`: 차수별 처리와 최신 유형 판정.
6. 완료 후 `completion-report.json`, `phase-reports/generation/`, `results/00-input.json`과 01~07 유형별 JSON.

[공통 dataset viewer](http://127.0.0.1:8893/?run={run_name})에서 원문·Python·그래프·새 문장·검증 근거를 확인합니다. 자동 PASS와 사람 판정은 별개입니다. 최종 선정은 Preparation PASS + 최신 7유형 모두 자동 PASS + 명시적 Reject 없음이며 사람 Accept는 필수가 아닙니다.

README는 `documentation/templates/checks/tatqa-generation-rerun-readme.md`에서 생성합니다.
