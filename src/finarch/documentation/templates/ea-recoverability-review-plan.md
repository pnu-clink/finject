# EA 역산 검토 추가 계획 · 조사 기록

작성일: {date}. 상태: **계획 작성 · 미구현**. LLM 호출 0회, API 과금 0, 신규 테스트 0회입니다.

읽는 순서는 다음과 같습니다.

1. [개선 계획](../../../docs/01-dataset/02-generation/03-validation/01-ea-recoverability-review-plan.md): 무엇을 추가하고, 어떤 정보로 판단하며, 어디에 저장할지.
2. [현행 G03](../../../docs/01-dataset/02-generation/03-validation/README.md): 현재 코드의 동작과 계획의 차이.
3. [evidence.json](evidence.json): 읽기 조사 결과, 코드·저장 파일의 경로와 SHA-256.
4. [events.jsonl](events.jsonl): 문서 작성·정적 확인 기록. 실제 제작 실행 로그가 아닙니다.
5. [manifest.json](manifest.json): 계획과 안내·조사 기록의 파일 hash.

[공용 문서 뷰어]({viewer_url})에서 이 계획과 현행 문서를 읽습니다. 계획 파일을 저장한 사실, 화면 확인, 사용자의 채택은 각각 구분합니다. 새 EA 판정 화면·schema·LLM 호출 경로는 구현하지 않았습니다.

문서 확인 결과는 [validation.json](validation.json)에 보존합니다. 이 검사는 파일·hash·링크·뷰어의 문서 읽기만 확인하며 역산 로직이나 데이터 의미를 검증한 것이 아닙니다.
