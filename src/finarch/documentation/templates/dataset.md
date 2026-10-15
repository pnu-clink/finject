# 데이터셋 제작 파이프라인

[상위: 전체 문서](../README.md)

금융 원문을 받아 풀이와 근거를 확인한 뒤, 값 충돌·출처 조건·관계 모순·근거 삭제를 반영한 문항을 만듭니다. **현재 작업은 이 제작 흐름과 단계별 사용자 요구를 정리하는 일**입니다. 실험 계획은 별도 영역에서 후속 정리합니다.

## 전체 그림

```mermaid
flowchart LR
 I["입력 준비: 원천·선정·Q/C/A"] --> P["Preparation: 원문 검토·계산·그래프·검증"]
 P --> B["진입 경계: 자동 상태·자료 해시 / 사람 판정 구별"]
 B --> G["Generation: 변경 계획·문장 생성·검증"]
 G --> R["결과 선정·고정·실험 전달 계약"]
 classDef detail fill:#fce4ec,stroke:#ad1457;
 class I,P,G,R detail;
 click I "00-input/README.md" "입력 상세"
 click P "01-preparation/README.md" "Preparation 상세"
 click G "02-generation/README.md" "Generation 상세"
 click R "03-release/README.md" "결과 전달 상세"
```

분홍색은 연결된 상세 문서가 있는 영역이며 구현 완료 표시가 아닙니다. 각 단계의 실제 Python/LLM·분기·실패 흐름은 아래 문서에서 확인합니다. 결과 전달은 요구 계약과 현재 구현 경계를 구별해 설명합니다.

|읽는 순서|영역|받는 것 → 만드는 것|
|---|---|---|
|1|[제작 공통 요구사항](00-requirements.md)|연구 목적·입력 경계·보존·호출·판정 원칙|
|2|[입력 준비](00-input/README.md)|원천 배포본 → 선정 Q/C/A·원천 대응·제외 로그|
|3|[Preparation](01-preparation/README.md)|Q/C/A → 검토된 문항·POT·그래프·검증·검토 자료|
|4|[Generation](02-generation/README.md)|원문·계산·그래프 → 7유형의 문장·검사·검토 자료|
|5|[결과 선정·전달](03-release/README.md)|제작 결과 → 선정 기준과 public/private 전달 경계|
|필요할 때|[공통 운영](90-operations/README.md)|차수·피드백·LLM 계약·산출물·뷰어|
|문제 검토|[단계별 확인 사항](99-open-issues.md)|요구·구현 차이, 미확인·미구현 범위|

## 현재를 읽는 기준

2026-09-23에 핵심 단계 모듈·runner·gate를 정적으로 대조했습니다. 문서 내 ‘구현 확인’은 코드 읽기 기준이며 신규 실행 검증을 뜻하지 않습니다. 실제 데이터셋의 품질과 수량은 해당 run의 자료로 확인해야 합니다.

특히 P07의 사람 판정과 현재 Generation 진입 코드, EA의 제한 역산과 전체 답변 불가능성은 구별합니다. [확인 사항](99-open-issues.md)을 해당 단계에 연결했습니다.

이전 순차 번호 문서는 [archive](../../archive/20260923-documentation-reorganization/README.md)에 원본 그대로 보존합니다. 일상적인 읽기는 이 문서에서 시작합니다. 이 README는 [템플릿](../../src/finarch/documentation/templates/dataset.md)으로 생성합니다.

## 폴더와 파일의 채번 기준

사용자 지정 기준은 run에 저장된 **진행 순서**입니다. `01-preparation/01-source`, `02-review`, `03-calculation`과 세부 스텝 이름은 실제 `reports/run/20260917-003/01-preparation/test-0001/01-round`를 대조했습니다. Generation은 같은 run의 `02-generation/01-round/test-0001/01-ic-value-before`를 대조했습니다.

- `01-dataset`, `02-experiments`는 문서 영역의 읽는 순서입니다.
- `00-input`은 run 진입 전 준비, `01-preparation`과 `02-generation`은 run의 phase 이름입니다.
- 단계 폴더는 실제 run 이름과 일치합니다. README 안의 세부 스텝은 실제 폴더·파일 이름을 함께 씁니다.
- `03-release`는 후속 전달 계약의 문서 순서이며 동일 이름의 run 단계가 구현됐다는 뜻은 아닙니다.
- `90-operations`, `99-open-issues.md`는 실행 단계가 아닌 공통 참조 영역입니다.
- README는 각 폴더의 입구이며 별도 작업 번호를 붙이지 않습니다. 나머지 설명 파일은 소속 폴더 안에서 번호를 붙입니다.
