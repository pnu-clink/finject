# viewer-exp 인계 기록

2026-09-20 · 사용자가 지정한 **“실험 파이프라인 설계 인계”** 작업에서 구현 인계를 받았습니다.
인계 작업 ID: `01a0b9ae-8110-7a22-bdf3-fb2b7b854c8b`.

## 이번 구현의 기준

- 최신 사용자 지정 경로는 `viewer/experiments`입니다. 이전 `exp-viewer/` 제안을 대체합니다.
- 기존 data viewer의 실행 선택 → 문항 목록 → 필터 → 상세 패널 구조를 참고하며 전체 테마는 브라운입니다.
- 실험 데이터 읽기 범위는 `reports/experiments-run`입니다. 제작 결과·원천 자료·private.source에 적힌 외부 경로를 따라가지 않습니다.
- 여섯 화면: 전체 결과, 조건별 비교, 문항 비교, 실패 분석, 비용·실행, 보고서·이력.
- 화면 비교 키는 같은 실행 안의 `case + variant + prompt_condition + reasoning`입니다. 모델마다 다른 trial_id를 직접 연결하지 않습니다.
- 원문은 Unguided Solving × Reasoning OFF/Reasoning ON, 변형은 Unguided Solving/Criteria-Guided Solving × Reasoning OFF/Reasoning ON입니다. 유형은 원본, IC-value 앞/뒤, IC-source 앞/뒤, IC-relation, EA-01/02 순서입니다.
- 형식 실패의 본문도 호출 JSON 및 원기록에서 읽습니다. V2, 평면 V3, V4 answer_meta를 원래 형태와 함께 표시합니다.
- reference 정답은 분석자용입니다. 변형의 정답으로 재사용하지 않으며, scale을 곱하거나 숫자를 다시 추출해 채점하지 않습니다.
- 비용의 null, 미평가, 미실행을 0이나 성공으로 바꾸지 않습니다. 입력 중 캐시, 출력 중 추론 토큰을 중복 합산하지 않습니다.
- 의미 점수, 쓰기 가능한 사람 채점, 실행 간 자동 통합 비교, 새 모델 호출은 이번 범위에 포함되지 않습니다.

## 확인한 현행 자료

1. [호출 폴더와 필드](../../docs/02-experiments/README.md)
2. [응답 계약](../../docs/02-experiments/README.md)
3. [로컬 Luna 실행](../../docs/02-experiments/README.md)
4. [기존 화면 설계](../../docs/02-experiments/README.md) — 과거 경로·이동 전 상태는 이력입니다.
5. exp-001~004의 실제 state/summary/plan/public/private/results/calls/analysis 파일.

최신 완료 실행 exp-004는 Luna V4, 3,000응답입니다. exp-003은 Gemini 두 모델의 V2, 6,000응답입니다.
exp-002는 미호출 대체 실행, exp-001은 인증 차단을 포함한 불완전 실행입니다. 최초 확인 값과 파일 보존 해시는 [검증 기록](../../log/viewer-experiments-v1/verification.json)에 있습니다.

## 구현 선택

별도 Node 표준 라이브러리 서버를 같은 폴더에 두었습니다. 새 의존성 설치가 필요 없으며 기존 Python 실험 실행기와 제작 뷰어를 호출하지 않습니다.
현재 구현의 책임·흐름·한계는 [구현 안내](../../docs/02-experiments/README.md)를 따릅니다.
