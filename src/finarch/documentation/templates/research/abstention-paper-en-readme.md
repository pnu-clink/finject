# Abstention 중심 영문 논문 초안 1–5장

한국어 초안의 목차·주장 범위·RQ·수치·미확정 표시를 유지한 영문 대응본입니다. 표 1은 사용자 후속 지시에 따라 PoT·풀이 실행 → 계산 그래프 → LLM 문장 생성의 비교 순서를 반영했습니다.

## 읽는 순서와 파일 역할

1. [PAPER-EN.md](PAPER-EN.md): 영문 본문입니다. 실제 원본은 [한·영 원고 폴더의 PAPER-EN.md](../20261002-abstention-paper-draft/PAPER-EN.md)이며 심볼릭 링크로 연결합니다.
2. [한국어 원고](../20261002-abstention-paper-draft/PAPER-KO.md): 절과 문단을 대응하여 읽을 수 있습니다.
3. [표 1 근거](../20261002-abstention-paper-draft/evidence/TABLE-1-POT-GRAPH.md): 실행 프로그램·계산 그래프·일반 구조 생성·LLM 문장 생성의 정의를 확인합니다.
4. [verification.json](verification.json), [events.jsonl](events.jsonl): 한·영 구조·표·그림·링크 및 뷰어 확인 기록입니다.

## 뷰어

[공통 연구 뷰어](http://127.0.0.1:8896/viewer/research/)에서 **2026-10-02 · Abstention paper · English · Sections 1–5**를 선택합니다. [RESEARCH-DIRECTION.md](RESEARCH-DIRECTION.md)는 영문 본문을 가리킵니다. 기존 공통 뷰어를 사용하며 실행 폴더에 별도 HTML 뷰어는 만들지 않습니다.

그림 1–7의 캡션은 영어로 작성했습니다. 한 단 Taxonomy가 Figure 2로 추가되었습니다. 사용자 제공 새 그래프 화면은 Figure 5이며, 화면의 한국어와 미평가 표시는 보존했습니다.

1,050개 선정 내역, 최종 독립 주석 일치율·κ, 정확한 제작 모델 식별자, 부록 A–C는 한국어와 동일하게 미확정입니다. 실측 결과·결론을 새로 만들지 않았습니다. 새 모델 호출·실험·외부 업로드는 없으며, 화면 확인과 사용자 최종 검토는 구별합니다.

이 README는 src/finarch/documentation/templates/research/abstention-paper-en-readme.md에서 생성합니다.
