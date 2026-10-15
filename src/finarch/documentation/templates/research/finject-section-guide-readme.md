# FInject 원논문 단원별 상세 해설

2026-09-26 · 비공개 투고 원고를 다시 읽기 위한 내부 학습자료입니다. 현재 작성 중인 논문과 분리했습니다.

원전은 [5쪽 PDF](</Users/wooix/workspace/논문/Finject_NAACL/2026_CIKM_FinanceBench (10).pdf>)입니다. 제목은 **FInject: Expanding Finance Reasoning Problems through Injection of Unanswerability**이며, 채택된 출판 논문으로 표시하지 않습니다. 본문의 주장과 해설자의 해석, 확인하지 못한 세부 사항을 구별합니다.

## 읽는 순서

|순서|자료|포함 내용|
|---|---|---|
|01|[전체 개요](chapters/01-overview.md)|초록·주장 구조·전체 숫자·읽는 방법|
|02|[서론과 관련 자원](chapters/02-introduction-related.md)|1·2절, 그림 1·2, 기여 4가지|
|03|[원문 선정과 여섯 변형](chapters/03-construction-taxonomy.md)|3.1–3.3절, 그림 3, 각 유형의 의미와 예외|
|04|[자동 검증과 사람 검수](chapters/04-validation-human.md)|3.4–3.5절, 검사식·표 1·3·4·표본 추출·보정|
|05|[과제와 평가 지표](chapters/05-tasks-metrics.md)|4절, 세 과제·지표의 뜻·분모·가상 계산 예시|
|06|[실험 결과](chapters/06-experiments.md)|5절 Q1–Q3, 표 2의 전체 모델·표 3·4·해석 한계|
|07|[결론과 참고문헌](chapters/07-conclusion-references.md)|6절·AI 사용 공개·범위·참고문헌 15개·재확인 목록|

각 장의 ‘한눈 정리’를 먼저 읽고 본문으로 들어가셔도 됩니다. 계산을 하는 일과 계산에 필요한 장부가 갖춰졌는지 검토하는 일을 구별하는 비유로 설명했습니다.

## 전체 지도

![단원별 지도](images/00-mindmap.svg)

<details>
<summary>단원별 핵심을 텍스트로 보기</summary>

- [01 전체 구조](chapters/01-overview.md): 계산과 답변 가능성 구별 · 원문·변형을 짝지어 평가 · 78 × 6 × 4 = 1,872
- [02 서론·관련 자원](chapters/02-introduction-related.md): 결측·충돌의 직관 · 제작 검증과 모델 평가 분리 · 데이터·유형·과제·품질
- [03 원문·여섯 유형](chapters/03-construction-taxonomy.md): 답에 필요한 근거 변경 · 결측 3유형·충돌 3유형 · 유형 형태 ≠ 답변 불가능
- [04 자동·사람 검증](chapters/04-validation-human.md): 구조 → 의미 → 사람 검수 · 같은 판정자의 두 축 PASS · 71 × 6 = 426
- [05 과제·지표](chapters/05-tasks-metrics.md): 유형 예측·이유 생성도 지원 · MCScore와 PairSucc 구별 · 원문 정답 AND 변형 유보
- [06 실험 Q1–Q3](chapters/06-experiments.md): Q1 과도한 답변·Q2 과잉 유보 · Q3 생성·검수 병목 · 평가 분모가 모델마다 다름
- [07 결론·문헌](chapters/07-conclusion-references.md): 결론과 AI 사용 공개 · 참고문헌 15개의 역할 · 영어·단일 문항·통제 실패

</details>

지도를 읽고 난 뒤에는 각 장의 제목만 보고 핵심 내용을 떠올려 보시면 됩니다. 설명하기 어려운 장부터 다시 읽으시면 됩니다.

## 한 화면에서 읽기

[공통 연구 자료 뷰어](http://127.0.0.1:8896/viewer/research/)에서 **FInject 원논문 단원별 상세 해설**을 선택하면 실제 통합본을 읽습니다. 뷰어는 본문·표 중심이며, SVG 도해는 단원 Markdown 또는 images/ 파일에서 확인하실 수 있습니다. 서버가 꺼져 있으면 저장소의 viewer/research/start.command를 실행합니다.

[통합 읽기본](RESEARCH-DIRECTION.md)은 단원 파일을 순서대로 합친 파생본입니다. 수정 기준은 chapters/이고, 통합본의 구성·해시는 verification.json으로 확인합니다. 결과 폴더에 별도 HTML 뷰어를 만들지 않았습니다.

## 검토 자료

- [단원·그림·표 대조 목록](COVERAGE.md): 초록부터 참고문헌까지 포함 여부를 확인합니다.
- [원전과 해시](sources.json): PDF와 추출본의 역할을 구별합니다.
- [검토 기록](REVIEW.md): 원고 내부의 불일치와 해설 수정 내역입니다.
- [검증 기록](verification.json), [작업 로그](events.jsonl): 파일·링크·그림 및 원고 보존 확인입니다.
- source/paper-layout.txt: 실제 PDF에서 위치를 보존해 추출한 확인용 텍스트입니다. 행 번호가 포함됩니다.

원고에는 별도 부록이 없으며, 본문이 보충자료로 안내한 세부 지표·파싱·스키마를 임의로 채우지 않았습니다. 공개 데이터 상태나 참고문헌의 출판 상태를 외부에서 재검증한 자료는 아닙니다. 새 실험과 모델 호출은 수행하지 않았습니다.

이 README는 src/finarch/documentation/templates/research/finject-section-guide-readme.md에서 생성합니다.
