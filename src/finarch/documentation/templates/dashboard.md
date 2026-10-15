# 프로젝트·실험 대시보드

프로젝트의 세션·남은 일·저장 실행을 먼저 보고, 필요하면 실험 숫자와 문항으로 내려갑니다. 화면은 `viewer/dashboard`의 한 서버(8895)에서 열며 실행 폴더마다 HTML을 만들지 않습니다.

1. [03-project](03-project/README.md): **프로젝트 현황**. 왼쪽의 전체 세션 신호 목록과 오른쪽의 진행 단계·우선 확인 항목·작업 중 세션·저장 실행을 한 화면에서 봅니다. 세션과 실제 부모·자식 상세는 팝업에서 엽니다.
2. [01-overview](01-overview/README.md): **실험 종합 현황**. 등록된 exp-006 자료의 주요 수치, 응답 시각과 시간, 조건별 분포를 봅니다.
3. [02-explorer](02-explorer/README.md): **문항 분석**. 같은 자료에서 질문·본문·응답과 조건별 차이를 확인합니다.
4. [운영과 실제 파일 흐름](../../docs/03-dashboard/README.md): 각 숫자와 관계를 어디서 읽는지 확인합니다.

프로젝트 루트에서 실행합니다.

```sh
./viewer/dashboard/start.command
```

[프로젝트 현황 열기](http://127.0.0.1:8895/dashboard/03-project/) · [실험 종합 현황](http://127.0.0.1:8895/dashboard/01-overview/) · [문항 분석](http://127.0.0.1:8895/dashboard/02-explorer/)

프로젝트 현황은 **로컬 Codex 세션 기록**과 이 프로젝트의 **저장된 실행·문서**를 읽습니다. 왼쪽의 업무별 묶음은 화면 분류이며 `↳` 숫자와 부모·자식 팝업만 실제 생성 기록에 근거합니다. 세션의 색 점은 작업 중·막힘 연결·미완료 연결·대기를 뜻합니다. 세션 팝업의 최근 요청은 사용자 메시지 요약이고, 관련 미완료는 문서·실행 상태에서 별도로 읽은 항목입니다. `작업 중`은 Codex 대화 턴 상태이며 모델 요청이 돌고 있다는 뜻이 아닙니다. 브라우저가 열려 있으면 1분마다 갱신하고 `새로 읽기`로 즉시 확인할 수 있습니다. 다른 호스트의 Codex 세션이나 아직 저장되지 않은 일은 빠질 수 있으므로 화면의 범위·시각·원문 링크를 함께 봅니다.

실험 숫자 두 화면은 exp-006 기준선입니다. 사용자 표시에는 **Unguided Solving / Criteria-Guided Solving**, **Reasoning OFF / Reasoning ON**을 사용합니다. 조건이 다른 실행을 성능 하나로 합산하지 않으며 형식 통과·숫자 일치·인용 존재를 의미 정답으로 해석하지 않습니다. [common.css](common.css)는 이 두 숫자 화면의 공통 틀이고 프로젝트 화면은 별도 반응형 스타일을 사용합니다. 이 서버는 자료를 읽기만 하며 모델 호출이나 원점수 재평가를 하지 않습니다.

[프로젝트 현황 제작·확인 기록](../../reports/run/20260929-project-dashboard/README.md)과 기존 숫자 화면의 [검사 기록](../../reports/run/20260923-experiment-improvement/04-validation/dashboard-checks.json)을 구분해 읽습니다. 이 README는 `src/finarch/documentation/templates/dashboard.md`에서 생성합니다.
