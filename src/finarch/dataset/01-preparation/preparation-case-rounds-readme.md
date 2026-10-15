# Preparation 문항별 차수

읽는 순서: `run.json`의 active_round/rounds → 해당 `NN-round/README.md` → 01-source부터 단계 순서 → 오류가 있으면06-exception-handler → 다음 차수00-round-input/seed.json과 LLM작업01-input/feedback-ref.json, rendered-prompt.json.

각 차수는 별도 폴더이며 이전 산출물을 덮어쓰지 않습니다. 00-round-input/seed.json의 REUSED는 이전 차수에서 복제한 파일의 원경로·해시입니다. 복제와 신규 실행을 구분합니다. feedback 원본은 오류 차수의06-exception-handler/feedback/적용차수 아래에 있고 소비 단계는 ref를 저장합니다. 07-human-review의 PENDING은 승인이 아닙니다. 단일 viewer에서 run·문항·차수를 선택하십시오.
