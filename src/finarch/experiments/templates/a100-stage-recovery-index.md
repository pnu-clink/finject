# Fin-o1 완료 자료 회수

`[vllm] gpu-2`가 확인한 완료 stage를 `experiments/pipeline.py recover-a100-stage`로 회수했습니다. 모든 원응답과 전달 파일의 해시를 확인했습니다.

|모델별 안내|수집 응답|원격 형식 통과|로컬 파일 해시 확인|
|---|---:|---:|---:|
$rows

원격 형식 통과는 정답 판정이 아닙니다. 각 모델 안내에서 동결 입력·프롬프트·스키마, 원응답·취합본·실행 기록·회수 기록을 읽습니다.

- [8B 회수 로그](recovery-8b.log)
- [14B 회수 로그](recovery-14b.log)
- Codex 파일 뷰어에서 이 문서와 모델별 README를 엽니다.
- 추가 모델 호출: 0건. Analysis는 실행하지 않았습니다.
- 실험 결과의 저장 위치는 `reports/experiments-run`입니다. 모델별 폴더에 동결 요청과 원응답을 보존합니다.

이 색인은 `experiments/pipeline.py report-a100-stages`가 템플릿에서 생성합니다.
