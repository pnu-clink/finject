# 한글 논문 초안 · v0.27

2026-09-28. 제작·Evaluation·Analysis 문서, 관련 구현과 저장 자료를 대조한 방법 중심 원고입니다. v0.27은 데이터 제작의 전체 로직을 부록으로 확장하고 연구 뷰어의 글자 크기와 문단·표·캡션 표시를 수정했습니다. 분석 결과와 결론은 공란입니다. 데이터 제작·실험 구현 변경, 생성·평가·Analysis 실행, 모델 호출은 하지 않았습니다.

4.2절의 상세는 부록 B.2–B.9, 4.3절의 상세는 B.10–B.19에서 읽습니다. 새 부록은 현재 문서·코드와 저장 사례를 직접 대조한 설명이며 기존 PAPER-KO.md를 현행 사실의 기준으로 삼지 않았습니다.

2026-09-28 후속 문구 수정: RQ1·RQ2에 변형 유형·앞뒤 배치·prompt·Reasoning 조건을 사용자가 제공한 문장 그대로 명시했습니다. 본문·질문 대응표·가설 기록의 질문 문구를 맞췄으며, SQ와 가설 내용은 유지했습니다.

## 읽는 순서

1. [현재 상태](CURRENT-STATE.md): 구현·실행·계획·연구 제안의 구분과 확인 시점입니다.
2. [불일치와 수정 근거](REVISION-AUDIT.md): 기존 원고·그림 쟁점, IC-Source 다단계 생성, 보조 질문 누락과 본문·기록 불일치의 수정 근거입니다.
3. [논문 본문 3.3–3.5절](PAPER-KO.md): RQ1·RQ2와 H1·H2, SQ1–SQ6과 H3–H8을 연결해 읽습니다.
4. [연구 질문·가설 대응표](RQ-REVIEW.md): 맨 앞에 8개 질문·가설을 나열하고, 9절에 예상 방향·측정 항목·지지하지 않는 결과·남은 요건을 적었습니다.
5. [그림 안내](../../../paper/asset/README.md): v4 개요·상세 SVG와 과거 v3의 구분입니다.
6. [제작 전체 로직 부록](DATA-GENERATION-APPENDIX.md): 19개 소절의 입력·처리·분기·실패·재시도·미평가·전달 및 실제 저장 사례입니다. 이 파일은 본문 부록 B의 편집 원본이며 본문 삽입본과 동일성을 확인합니다.
7. [파일별 상세 순서도](DATA-GENERATION-FLOWS.md) → [부록 근거 장부](DATA-GENERATION-EVIDENCE.json): Python·LLM·사람 판정의 구분과 실제 파일·해시를 확인합니다.

## 변경 내용을 화면에서 확인

[공통 연구 뷰어](http://127.0.0.1:8896/viewer/research/#s14)에서 **2026-09-28 · 한글 논문 초안 v0.27 · 제작 전체 로직 부록**을 선택하고 목차의 ‘부록 B. 데이터 제작의 전체 처리 로직’을 읽습니다. 화면은 이 폴더의 RESEARCH-DIRECTION.md가 가리키는 실제 PAPER-KO.md를 읽습니다. 결과 폴더에 별도 뷰어를 만들지 않았습니다.

뷰어는 본문·제목·표·그림을 표시하고 그림을 포함한 HTML 내보내기를 제공합니다. 소절의 첫 문단을 별도로 확대하지 않으며 본문과 표는 데스크톱 17px, 모바일 16px입니다. 그림 제목과 상세 설명은 하나의 15px 캡션으로 표시합니다. 강조는 크기 대신 굵기로 구별합니다. [뷰어 사용 안내](../../../viewer/research/README.md)와 [확인 기록](../../../log/research-viewer/20260928-appendix-typography/README.md)을 참고합니다. SVG 원본 두 장은 보존했습니다.

## 기록 파일의 역할

|파일|역할|
|---|---|
|HYPOTHESES.json|8개 질문·가설의 정확한 문구, 측정 항목·반대 결과·자료 요건·탐색적 상태|
|IC-SOURCE-MULTISTEP.json|다단계 생성의 구현 근거와 Type 1/2 저장 사례의 부모 문맥·출처 제거 복원 대조|
|DATA-GENERATION-APPENDIX.md|본문 부록 B의 편집 원본. Preparation·Generation·전달의 전체 절차|
|DATA-GENERATION-FLOWS.md|실제 파일별 Mermaid 순서도 3개. 정상·실패·재시도·유형 의존 관계|
|DATA-GENERATION-EVIDENCE.json|부록의 현재 코드·문서·저장 사례 해시와 확인 범위|
|CURRENT-STATE.json|기존 제작·실험 산출물의 상태·수량·설정·입력 해시 스냅샷. 성능 분석 결과 아님|
|sources.json|직접 확인한 문서·구현·산출물과 읽은 범위·파일 해시·공개 참고문헌|
|events.jsonl|이 작업의 근거 확인·집필·그림·검사 순서 로그|
|verification.json|결과·결론 공란, 링크, 동결 지시문 일치, 구현 보존, 화면 확인 기록|
|rq-verification.json|두 중심 RQ·여섯 독립 SQ·가설 H1–H8의 대응, 회의/문서 근거, 문구 일치와 제안 상태의 기록|
|terminology-verification.json|사용자 표시명과 내부 식별자의 분리 확인|
|HISTORY-AND-EVIDENCE.md|과거 집필 이력. 최신 사실의 기준으로 사용하지 않음|
|archive/20260928-before-evidence-review/|개정 전 원고·근거 장부·검사 기록과 구현 해시 기준본|
|archive/20260928-before-supplementary-questions/|보조 질문 정리 전 실제 본문·검사 기록·목록 보관. 당시 v0.23 본문/v0.24 기록 불일치도 보존|
|archive/20260928-before-hypotheses/|가설 작성 전 v0.25 원고·검토·안내·검사 기록과 구현 해시 기준본|

변경 전 질문·가설 기록과 확인 기록은 [RQ 문구 수정 전 보관본](archive/20260928-before-rq-wording/manifest.json)에 보존했습니다.

## 확인 범위와 남은 판단

CURRENT-STATE의 제작·실험 상태는 2026-09-28 08:50–08:51 KST의 기록입니다. v0.27 부록의 추가 확인 시점과 범위는 DATA-GENERATION-EVIDENCE.json에 별도로 기록했습니다. 다른 작업의 Analysis 상태를 새로 확인한 것으로 표시하지 않습니다. 입력 동일성·파일 존재·출력 계약 통과를 의미 정답이나 연구 승인으로 확대하지 않습니다.

v0.26 원고·검사 기록과 표시 수정 전 뷰어는 [개정 전 보관 목록](archive/20260928-before-appendix-typography/manifest.json)에 연결되어 있습니다. v0.26의 질문·가설 파일은 그대로 유지하며 v0.27의 변경은 부록과 표시입니다.

이 README는 `src/finarch/documentation/templates/research/paper-draft-readme.md`에서 자동 복사 생성합니다. 본문·그림·해시·링크를 확인해도 **사용자 검토 완료를 뜻하지 않습니다.** 실제 검사 내역은 verification.json을 따릅니다.

이번 보완은 질문별 가설을 명시한 집필안입니다. H1–H8은 검증 완료 또는 사전 등록된 가설이 아닙니다. H2의 복원 예측은 저장 응답을 접한 뒤 구체화한 탐색 가설이며, H4의 품질 기준은 평가 전에 정해야 합니다. SQ4–SQ5의 자료 연결과 SQ6의 독립 반복 요건은 유지합니다. 금융 특화 모델 비교는 제외했고, IC-Source 다단계 생성 설명·그림·분석 결과와 결론 공란을 유지했습니다.
