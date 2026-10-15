# 20261003-002 · CodeTAT-QA Generation 재생성

기존 `20261003-001-CodeTAT-QA-0917-002`의 Preparation 결과를 독립적으로 복제하고, 현행 프롬프트로 7유형 Generation 전체를 새로 실행합니다. 원본 288문항 중 Preparation PASS 279문항 × 7유형 = 1,953유형이 생성 대상입니다. Preparation FAIL 9문항은 기존 실패 근거를 유지하고 Generation에서 미실행으로 기록합니다. Preparation LLM 호출은 새로 하지 않습니다.

## 실행과 진행 확인

실제 시작 프로그램은 기존 `generate_schedule.py`입니다. 임시 relation scheduler나 별도 Python 재생성 프로그램은 사용하지 않습니다.

```shell
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.02-generation.generate_schedule \
  --run reports/run/20261003-002
```

정확한 모델은 `gpt-5.6-luna / max / api`입니다. hyperparameter·프로필은 이번 run 안의 파일을 사용합니다. API 실행의 실제 문항 동시 처리·API 동시 상한은 모두 200, 유형 동시 처리 5, 최대 3차이며 실패 후 재시도 여부는 기존 scheduler 기준을 따릅니다. 출력 토큰 한도는 32,768, 총 토큰 예산은 500,000입니다. Batch API로 변경하지 않습니다.

지난 CodeTAT-QA Generation 저장 사용량의 비용 소계는 약 $14였습니다. 이번 예상 $14~28은 같은 범위의 과거 사용량을 바탕으로 한 추정이며 실제 청구액이나 지출 한도가 아닙니다.

## 읽는 순서

1. [sequence-status.json](sequence-status.json): 실행·취합 단계와 종료 상태.
2. [terminal.log](terminal.log): 실제 시작 프로그램의 출력·오류.
3. [preparation-reuse.json](preparation-reuse.json): 복제 파일별 해시·기존 PASS/FAIL 목록.
4. [model-preflight.json](model-preflight.json), [authorization.json](authorization.json), [prompt-code-snapshot.json](prompt-code-snapshot.json): 실제 모델 선택·응답 스키마·승인 범위·코드 및 프롬프트 해시.
5. Generation 실행 후 `02-generation/*-round/progress.json`, `02-generation/summary.json`, `completion-report.json`, `phase-reports/generation/`에서 차수·문항·유형별 실제 결과를 확인합니다.
6. 최종 취합 후 `results/00-input.json`과 01~07 유형별 JSON을 같은 문항 ID로 연결합니다.

[공통 dataset viewer에서 이번 run 보기](http://127.0.0.1:8893/?run=20261003-002). 기존 원문·Python·계산 그래프와 이번에 새로 만든 문장·검증 근거를 같은 화면에서 확인합니다. 과거 Preparation 기록의 날짜·모델 응답은 복제한 원래 기록이며 신규 실행으로 집계하지 않습니다.

기존 CodeTAT-QA run과 `20261003-concat-001`, annotation·평가 HTML은 생성 중 변경하지 않습니다. 새 7유형 결과의 기계적 검사를 완료한 뒤 concat 반영·HTML export를 진행합니다. 선정 기준은 Preparation PASS + 최신 7유형 모두 자동 PASS + 명시적 Reject 없음이며 사람 Accept는 필요하지 않습니다. 7유형 모두 다시 생성하므로 기존 CodeTAT-QA annotation을 새 문장에 무조건 승계하지 않습니다.

## 상태의 의미

파일·해시·응답 스키마 검사는 기계적 확인입니다. 자동 PASS는 사람 승인이나 의미상 정답의 증명이 아닙니다. 완료 여부는 위 상태·원응답·최종 결과를 읽어 확인하며 이 README의 생성만으로 완료를 선언하지 않습니다. README는 documentation/templates에서 생성했습니다.

## 2026-10-03 입력 검사 오류 수정·재개

표 뒤의 독립 문단을 요구하는 빈 줄 두 개(`\n\n`)를 사전 작성 문장으로 오인하여 IC-RELATION 199유형이 API 호출 전에 차단됐습니다. 공백만 있는 접두사는 허용하고 문장 접두사는 계속 금지하도록 수정했습니다. 입력 정책 오류명은 원래대로 남깁니다. 해당 199유형의 요청을 로컬 재검증했고 관련 회귀 검사 16개가 통과했습니다. 추가로 실행한 기존 검사에는 현행 SOURCE 부모 자료·POT 부호 계약과 맞지 않는 fixture 오류 3개가 있어 전체 검사 통과로 보고하지 않습니다.

원래 오류와 handler 응답은 `02-generation/interrupted-attempts/input-policy-20261003/`에 보존했습니다. 기존 정상 PASS 607유형과 다른 원인의 FAIL 57유형은 유지합니다. 일반 통신 장애·문항 실패로 이번 코드 오류를 최종 집계하지 않도록 해당 199유형을 미완료 대상으로 돌리고 기존 scheduler의 재개 기능을 사용합니다. 새 계정 잔액을 조회한 것은 아니며, 당시 HTTP 오류 0개·API 정상 완료 사용량 기록 1,861개를 확인했습니다.

읽는 순서: [provider-error-repair.json](provider-error-repair.json) → 보관된 원래 오류 → `terminal.log` → 최신 차수 진행 상황.

```shell
./reports/run/20261003-002/start-generation.sh --resume
# 기존 generate_schedule.py --resume으로 완료 결과를 재사용하고 남은 유형을 실행합니다.
```
