# Abstention 중심 한국어 논문 초안 1–5장

사용자가 지정한 목차에 따라 2026-10-02 회의 방향을 반영한 한국어 원고입니다. [영문 대응본](PAPER-EN.md)도 제공합니다. 기존 원고를 내용 근거로 사용했으며, 기존 Overleaf 원고를 백업한 뒤 영문 수정본을 반영했습니다. [백업·반영 기록](../20261002-overleaf-abstention-update/README.md)에서 확인할 수 있습니다.

## 읽는 순서와 파일 역할

1. [PAPER-KO.md](PAPER-KO.md): Abstract → Related Works → Benchmark Construction → Release Sampling and Human Verification → Task and Metrics 순서의 본문입니다. 3.1–3.6과 그림 1–6을 유지했습니다. RQ1은 답변·기권, RQ2는 근거 변화에 따른 응답 변화입니다.
2. [SOURCE-MAP.md](SOURCE-MAP.md): 회의·원고·저장 자료의 대응, 수정 채택과 보류 이유, 미확정 수치와 부록 범위를 확인합니다.
3. [evidence/sources.json](evidence/sources.json): 읽은 자료와 그림의 SHA-256 및 원본 표시 영역입니다. [annotation-snapshot.json](evidence/annotation-snapshot.json)은 기존 부분 중첩 주석 통계의 읽기 스냅샷입니다.
4. [verification.json](verification.json), [events.jsonl](events.jsonl): 문서 연결·목차·그림·원본 보존과 뷰어 확인 기록입니다. 모델 성능 검증 기록이 아닙니다.

## 공통 연구 뷰어

[공통 연구 뷰어](http://127.0.0.1:8896/viewer/research/)에서 **2026-10-02 · Abstention 중심 논문 · 사용자 목차 1–5장**을 선택합니다. 뷰어는 이 폴더의 [RESEARCH-DIRECTION.md](RESEARCH-DIRECTION.md)를 통해 실제 PAPER-KO.md를 읽습니다. 이 파일은 본문을 가리키는 심볼릭 링크이므로 수정본이 따로 갈라지지 않습니다. 화면의 HTML 내보내기로 그림을 포함한 독립 사본을 저장할 수 있습니다. 결과 폴더에 별도 뷰어 HTML은 만들지 않습니다.

## 확인이 남은 항목

표 1의 비교 항목 3–5는 **PoT·풀이 실행 → 계산 그래프 → LLM 문장 생성**입니다. 규칙·템플릿 구조는 계산 그래프와 별도 열로 남겼으며, 체크의 의미와 연구별 근거는 [표 1 근거](evidence/TABLE-1-POT-GRAPH.md)에 있습니다. [영문 확인 기록](../20261002-abstention-paper-en/verification.json)에서 두 언어의 최신 구조·표를 대조합니다.

- 저장된 자동 검사 통과는 1,080개이며, 요청에 적힌 1,050개와 연결되는 추가 선정 기록은 미확인입니다.
- 최종 공개 표본의 독립 주석 일치율·κ는 확인란으로 남겼습니다. 기존 314개 공통 표본 집계를 전체 결과로 옮기지 않았습니다.
- 정확한 제작 모델 식별자, 부록 A–C와 실측 결과 문장은 후속 집필 항목입니다. 지표 정의는 이번 집필안이지 새 채점 구현의 완료 보고가 아닙니다.
- 파일 저장·에이전트의 화면 확인과 사용자의 원고 검토 완료는 구분합니다.

이 README는 src/finarch/documentation/templates/research/abstention-paper-draft-readme.md에서 자동 생성합니다. 새 모델 호출과 실험 실행은 없습니다.
