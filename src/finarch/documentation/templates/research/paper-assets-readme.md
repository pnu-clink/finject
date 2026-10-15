# 논문 그림 자산

2026-09-28 작성한 현행 v4 SVG 두 장과 2026-09-29 추가한 데이터셋 강건성 PNG를 보관합니다. v4 SVG는 당시 문서·구현·실제 산출물에 근거해 작성했습니다. 본문의 분석 결과와 결론은 공란이며, 그림에는 방법과 기록의 경계만 나타냅니다.

## 현재 그림과 읽는 순서

1. [개요도](pipeline-overview-v4-abstract.svg): 제작 → Evaluation → Analysis, 공개 입력과 private 기록, 사람 판정의 구분입니다.
2. [상세도](pipeline-overview-v4.svg): 각 단계의 Python/LLM 처리, 공통 출력 계약·네 조건·원본 수치 비교·관계 해석을 읽습니다.
3. [수정 근거](../../reports/run/20260924-paper-draft/REVISION-AUDIT.md): M05–M08·M14–M15가 주요 그림 수정 근거입니다.

![v4 개요도](pipeline-overview-v4-abstract.svg)

![v4 상세도](pipeline-overview-v4.svg)

## 데이터셋 강건성 검토용 PNG

[원천 2,238건에서 자동 검사 7유형 모두 PASS인 1,080문항까지](dataset-pipeline-2238-to-1080.png)의 흐름을 왼쪽에서 오른쪽으로 읽습니다. 1,838문항이 일곱 유형으로 확장되고 각 유형의 검사 결과가 원문별 AND/OR로 다시 합쳐집니다. 마지막 AND 상자에는 1,080문항의 원천 난이도별 내역(Easy 494 · Medium 513 · Hard 73)을 표시합니다. 원천 수량·유형별 판정·생성 로그는 [실행 폴더 안내](../../reports/run/20260920-002-failure-review/pipeline-figure/README.md)에 있습니다. 이 PNG는 강건성 검토 자산이며 현재 원고의 v4 개요·상세도를 대체하거나 원고에 삽입한 상태를 뜻하지 않습니다.

![데이터셋 강건성 흐름](dataset-pipeline-2238-to-1080.png)

## 표기와 해석

- 청회색은 Dataset Construction, 옅은 갈색은 Model Evaluation & Analysis입니다. 실선은 주 처리 흐름, 점선은 별도 기록의 연결입니다.
- 실험 입력에는 Q/C와 정밀도가 포함됩니다. 정답·제작 코드·그래프·변형 메타는 풀이 입력에서 분리합니다.
- Human review는 별도 판정 기록입니다. 자동 통과 뒤 전수 사람 주석이 완료되었다는 뜻이 아닙니다.
- Unguided Solving / Criteria-Guided Solving × Reasoning OFF / Reasoning ON을 사용합니다. 두 풀이 조건 모두 공통 출력 계약을 따릅니다. 미지원 조건은 N/A입니다.
- IC-Source는 IC-Value 생성·검증 후 그 문맥에서 출처를 별도로 생성하는 다단계 방식입니다. 두 그림의 Generation에 VALUE → attribution을 표시했습니다. 이는 풀이 모델의 추론 단계 수를 뜻하지 않습니다.
- E04 숫자 참조 비교는 원본 대상입니다. A02의 후보값 일치·인용 해석과 의미 정답률은 다릅니다.
- 상세 그림은 처리 역할을 표시하며 실제 파일별 구현 순서도의 대체물이 아닙니다. 실패·재시도·미평가의 세부 분기는 연결된 현행 단계 문서를 따릅니다.

## 보존과 확인

이전 [v3 개요 PNG](pipeline-overview-v3-abstract.png)와 [v3 상세 PNG](pipeline-overview-v3.png)는 검토 대상 원본으로 보존했습니다. 현행 원고는 v4만 참조합니다. 과거 생성 프롬프트는 당시 이력입니다.

`asset-log.jsonl`은 그림의 작성·이동 방식, 근거와 해시를 기록합니다. v4 SVG는 XML과 브라우저 전체 화면으로, 강건성 PNG는 이미지와 실행 폴더의 수량 대조로 확인합니다. 검사 완료는 사용자 승인이나 연구 결과 확정을 뜻하지 않습니다.

이 README는 `src/finarch/documentation/templates/research/paper-assets-readme.md`에서 자동 복사 생성합니다.
