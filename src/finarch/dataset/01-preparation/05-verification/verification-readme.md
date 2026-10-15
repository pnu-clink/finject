# 05-verification · 풀이 검증

읽는 순서: 01-artifacts.json → 02-execution-and-answer.json → 03-provenance-structure.json → 04-graph-consistency.json → 05-build-verification-request → 06-LLM-verify-semantics → 07-check-verification-response.json → 08-verdict.json.

artifact-refs.json은 검사에 사용한 파일 경로와 해시입니다. 06의 입력 폴더에서 feedback-ref.json과 rendered-prompt.json으로 실제 반영한 피드백을 확인합니다. 04-verdict.json은 기존 판독기와 호환되는 최종 판정 사본입니다.

Python 검사 실패는 LLM 통과로 덮어쓰지 않습니다. cohort는 INTERNAL/EXTERNAL/PENDING이며 사용한 외부 정보와 필요한 외부 정보는 구분합니다. 자동 검사 통과는 사람 승인이나 의미적 정확성의 증명이 아닙니다.

프로젝트 단일 Viewer에서 실행·문항·05-verification을 선택하여 확인합니다. 검사 실행 전의 파일이나 원응답은 소급 수정하지 않습니다.
