# 최근 1년 금융 QA 원본 데이터셋 조사

조사 기준일: {{AS_OF}} · 기간: {{WINDOW_START}}–{{AS_OF}} · 조사 목록 {{CANDIDATES}}개

이 안내서는 `src/finarch/dataset/00-input/dataset-survey-readme-template.md`에서 자동 생성했습니다. 공개 자료와 배포 파일을 조사한 결과이며, 데이터셋의 의미 정답률이나 제작 실험 결과를 뜻하지 않습니다. 목록에는 보류·현재 목적 제외 항목도 포함합니다. 현재 계산 방식과 근거 변형 적합성을 먼저 확인하고, QCA 필드 유무나 전체 규모만으로 채택하지 않습니다.

## 읽는 순서와 파일 역할

1. [05-calculation-fit.md](docs/05-calculation-fit.md): 현재 계산 방식으로 답할 수 있는지, 전체 규모와 수치 후보 규모가 어떻게 다른지 먼저 읽습니다. 실제 계산·근거 오류와 검증 한계를 확인합니다.
2. [06-training-overlap.md](docs/06-training-overlap.md): 2026-09-20 추가 조사입니다. 금융 모델 6계열·7체크포인트의 학습 출처와 현재 FinanceReasoning·TAT-QA 원문 대조 결과를 읽습니다. 원본 조사 기간은 바꾸지 않았습니다. [모델별 근거](model-training-provenance.json) · [비교 집계](model-overlap-inspection.json) · `model-overlap-*.jsonl`의 문항별 기록을 제공합니다.
3. [01-shortlist.md](docs/01-shortlist.md): 추천 순위, 공개 규모, 발표 시점, 언어와 논문 투고·게재처·Accept/Reject 상태를 비교합니다.
4. [02-candidate-details.md](docs/02-candidate-details.md): 데이터별 장점·한계·출처·이용 조건을 읽습니다.
5. [03-selection-notes.md](docs/03-selection-notes.md): 현재 연구에 맞는 선택과 채택 전에 확인할 점을 읽습니다.
6. [04-exclusions-and-method.md](docs/04-exclusions-and-method.md): 별도 제외·보류 자료를 01과 같은 컬럼으로 비교합니다. 학회·저널·Accept 상태와 공개 규모·언어·제외 근거를 확인합니다. [exclusions.json](exclusions.json)은 해당 자료의 메타데이터이며, [exclusion-inspection.json](exclusion-inspection.json)은 추가로 읽은 배포 파일의 수량 기록입니다.
7. [candidates.json](candidates.json), [inspection.json](inspection.json): 조사 메타데이터와 실제 파일·API에서 센 문항 수입니다. [publication-status.json](publication-status.json)은 공식 게재·저자 명시 Accept·미확인을 구분하고 탈락 제외 근거를 기록합니다.
8. [calculation-fit-inspection.json](calculation-fit-inspection.json): 수치 후보·제한된 연산 재계산 결과입니다. [숫자 표기 보완 로그](calculation-fit-normalization-log.json), [현재 코드 확인 기록](framework-source-inspection.json), [QCA·배포본 구조 확인](direct-qca-inspection.json)을 함께 읽습니다. `calculation-fit-*-rows.jsonl`은 문항별 원래 정답·계산값·확인 사유입니다.
9. [research-log.jsonl](research-log.jsonl), [manifest.json](manifest.json), `evidence/`: 조회 URL·시각·해시와 보존한 원본 자료입니다. `events.jsonl`은 조사·안내 문서 생성 기록입니다.
10. [checks.json](checks.json): 문서·출처 파일 무결성과 뷰어 확인 범위입니다. 사용자 검토 여부는 별도 기록입니다.

[공통 뷰어에서 조사 결과 열기](http://127.0.0.1:8893/?run={{RUN_ID}}) — 실행 목록에서 `{{RUN_ID}}`를 선택하고 왼쪽 문서를 누릅니다. 뷰어는 이 폴더의 현재 README와 summary를 읽습니다. 결과 폴더별 HTML은 생성하지 않습니다.

재생성 명령:

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.00-input.dataset_survey --run reports/run/{{RUN_ID}}
```

아래에는 위 여섯 문서의 저장 내용을 함께 넣었습니다.
{{DOCUMENTS}}
