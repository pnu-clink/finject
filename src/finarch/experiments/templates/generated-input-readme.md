# Generated 데이터 입력

입력: `{source}`. 제작 run을 열지 않고 manifest와 dataset.jsonl만 읽었습니다.
선정: 원문 {originals}개, 변형 {variants}개. API 호출 전 준비 자료입니다.

읽는 순서:

1. `selection.json`: 선정·제외 이유, 데이터 해시, annotation 정책, 분석 메타정보 누락.
2. `public.jsonl`: item_id와 질문·문맥·소수점 자릿수. 모델에는 item_id를 제외한 풀이 입력만 전달합니다.
3. `private.jsonl`: 정답·제작 판정·annotation·편집 내역·원본/변형 연결. solver에 보내지 않습니다.

분석 메타정보: **{analysis_status}**, 누락 기록 {gaps}건. 누락은 추측해서 채우지 않으며 후속 분석의 준비 완료를 뜻하지 않습니다.
미판정은 Accept가 아닙니다. 별도 annotation이 있는 데이터는 선택 정책 확정 전 준비를 차단합니다.
실제 파일은 실험 뷰어의 해당 실행 입력·문항 화면에서 확인합니다. 별도의 문서용 웹페이지는 만들지 않습니다.

## 사용법

프로젝트 루트에서 `PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline prepare --config config/experiments/config.toml`을 실행하면 설정의 generated_path에서 public/private와 요청을 함께 준비합니다. 모델 호출은 0건입니다. 같은 실험을 재개하려면 prepare를 반복하지 않고 run 루트 README의 `run --evaluation-only --run` 명령을 사용합니다.

선정·제외 이유와 분석 메타 누락은 `selection.json`에서 확인합니다. 합본의 제작 판정·정답·annotation을 public 모델 입력에 포함하지 않습니다.
