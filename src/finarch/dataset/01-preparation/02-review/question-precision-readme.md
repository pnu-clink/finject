# 질문 자릿수 검사와 LLM 보정

Python은 gold·precision의 일치와 질문의 명시적 소수 자릿수를 확인하며, 질문을 먼저 변경하지 않습니다. 원래 Q·C·A와 reference_answer_type·reference_precision을 기존 감사에 전달합니다.

불일치가 있으면 기존 preparation.revise에 동일한 QCA·type·precision을 전달하여 질문 수정안을 받습니다. 최소 1회 보정 기회를 주며, 숫자·원문 위치 검사는 자릿수 변경만 허용합니다. 수정된 QCA를 재감사하고 통과 후 작업용 data.json과 원본 대비 비교를 저장합니다. POT 요청에는 gold를 추가하지 않습니다.

01-check.json은 Python 검사 근거입니다. 각 round의 02-LLM-revise-text 및 03-check-revision에서 원응답·수정 전후를 확인합니다. 공통 뷰어의 02-review-and-correct에서 해당 파일과 QCA diff를 조회합니다.
