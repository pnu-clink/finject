# 한·영 전환 확인용 HTML

읽는 순서: 이 안내 → 확인용 HTML → [검사 결과](../../log/viewer-i18n-20261002/verification.json). 아래 HTML은 사용자가 요청한 Export 기능으로 만든 확인 자료이며, run마다 별도 뷰어를 생성하는 구조는 아닙니다.

|파일|자료·용도|
|---|---|
|[dataset-20261002-001-test-0005.html](dataset-20261002-001-test-0005.html)|실제 `20261002-001`의 test-0005 평가용 화면. 영어로 시작하며 상단 한국어/English로 전환합니다. 제작 서버 판정과 분리된 HTML입니다.|
|[experiments-20260926-exp-001.html](experiments-20260926-exp-001.html)|저장된 실험 한 문항·한 요청을 내보낸 HTML. 응답·Q/C·검사 자료를 서버 없이 읽으며 화면 언어를 바꿀 수 있습니다.|
|[annotation-fixture.html](annotation-fixture.html)|합성 UI 확인 자료. 한국어 질문·본문·주석이 화면 언어 전환으로 바뀌지 않는지 확인합니다. 실제 제작 결과가 아닙니다.|

파일을 브라우저로 열고 한국어/English를 누릅니다. 버튼·안내가 전환되어도 질문·본문·원응답·사용자 입력은 원문을 유지합니다. 번역이 저장된 설명만 한글/영어를 함께 제공합니다. 과거에 배포한 HTML은 다시 Export해야 합니다.

[Dataset 라이브 화면](http://127.0.0.1:8893/?run=20261002-001&case=test-0005&variant=01-ic-value-before&stage=05-human-review) · [Experiments 라이브 화면](http://127.0.0.1:8894/) · [동작·파일별 흐름](../../viewer/shared/README.md)

자동 검사와 라이브 UI 확인 범위는 위 검사 결과에 구별하여 기록합니다. 브라우저 도구의 `file://` 제한 때문에 파일 직접 실행의 시각적 확인은 미확인입니다.
