# 문항 입력 접기·펼치기 변경 기록

## 읽는 순서

1. [실제 화면](http://127.0.0.1:8894/?run=20260920-exp-006&tab=case&case=test-0006)에서 **모델에 전달한 입력** 제목 줄을 누릅니다.
2. [화면 확인 로그](checks.json)에서 에이전트가 확인한 범위와 결과를 봅니다.
3. [뷰어 사용 안내](../../viewer/experiments/README.md)와 [책임 표·구현 흐름](../../docs/viewer-experiments.md)을 읽습니다.

## 변경 파일 역할

|파일|역할|
|---|---|
|[app.js](../../viewer/experiments/app.js)|입력 전체 접기·펼치기, 근거 선택 시 자동 펼침|
|[styles.css](../../viewer/experiments/styles.css)|제목 줄·방향 표시·기존 브라운 테마|
|[README 템플릿](../../viewer/experiments/templates/README.template.md)|사용 안내 생성 원본|
|[checks.json](checks.json)|실제 브라우저 조작 결과와 확인 시각|

처음에는 펼친 상태입니다. 제목 클릭 또는 Enter·Space로 조작할 수 있으며, 같은 상세의 **새로 읽기**는 접힌 상태를 유지합니다. 근거 선택은 입력을 펼쳐 기존 강조·안내를 보여 줍니다. 새로 내보내는 HTML에도 반영되며 기존에 내려받은 사본은 바뀌지 않습니다.

실험이나 모델 호출을 실행한 기록이 아닙니다. 에이전트의 확인은 사용자 검토 완료를 뜻하지 않습니다.

이 문서는 `src/finarch/experiments/viewer/templates/input-collapse-log-readme.template.md`에서 `scripts/build-readme.mjs`로 생성합니다.
