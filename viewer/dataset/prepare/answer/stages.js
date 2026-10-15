function preparationGuide(stage){
 const guides={
  '01-source':{title:'원본 자료를 읽고 Q·C·A 입력과 대조합니다.',steps:[
   ['01-receive-input · Python','질문·본문·정답과 type·precision을 받습니다.',[['입력',['01-receive-input/01-input.json']]]],
   ['02-record-source · Python','원천 파일과 문항 위치를 기록합니다.',[['출처',['02-record-source/01-provenance.json']]]],
   ['03-compare-source · Python','원본과 준비 입력의 차이를 확인합니다.',[['비교',['03-compare-source/01-result.json']]]]
  ]},
  '02-review':{title:'원본 문장과 조건을 검토합니다. 해당 단계 피드백이 있으면 같은 요청에 반영합니다.',steps:[
   ['01-read-input · Python','Q·C·A와 해당 단계 피드백 참조를 읽습니다.',[['입력',[/^01-read-input\//]]]],
   ['02-LLM-review-original · LLM','회사·기간·단위·자릿수와 문장 오류를 검토합니다.',[['요청·응답',[/^02-LLM-review-original\//]]]],
   ['03-record-result · Python','원본·보정본·변경 이유를 보존하고 미해결 문제를 handler에 전달합니다.',[['결과',[/^03-record-result\//,'accepted-input.json','accepted-audit.json']]]]
  ]},
  '03-calculation':{title:'POT 요청 → 코드 선저장 → Python 실행 → 산출물 기록 순서입니다.',steps:[
   ['01-build-pot-request · Python','Q·C와 출력 형식을 준비합니다. gold 값은 POT 요청에서 제외합니다.',[['요청',[/^01-build-pot-request\//]]]],
   ['02-LLM-generate-code · LLM','코드와 입력 근거·출처를 생성합니다.',[['전송·원응답',[/^02-LLM-generate-code\//,/^01-LLM-generate-code\//]]]],
   ['03-preserve-response-and-code · Python','실패해도 사용자가 볼 수 있도록 원응답과 코드를 보존합니다.',[['코드·보존 결과',[/^03-preserve-response-and-code\//,/^02-prepare-code\//]]]],
   ['04-execute-python · Python','기존 격리 실행으로 중간값과 최종 결과를 기록합니다.',[['실행',[/^04-execute-python\//,/^03-execute-python\//]]]],
   ['05-record-calculation-artifacts · Python','실행·구조 검사와 계산 산출물을 구분해 기록합니다.',[['산출물',[/^05-record-calculation-artifacts\//,/^04-compare-answer\//,'05-stage-output.json']]]]
  ]},
  '04-graph':{title:'Python의 입력·연산·출처에서 최종 답까지 계산 그래프를 구성합니다.',steps:[
   ['01-read-calculation · Python','코드와 실행 결과를 읽습니다.',[['입력',[/^01-read-calculation\//]]]],
   ['02-build-graph · Python','변수·연산·연결을 추출합니다.',[['그래프 구성',[/^02-build-graph\//]]]],
   ['03-attach-provenance · Python','문맥 근거·외부 공식·외부 수치를 연결합니다.',[['출처',[/^03-attach-provenance\//]]]],
   ['04-trace-answer-dependencies · Python','답에 실제 기여한 입력과 중간값을 추적합니다.',[['의존 관계',[/^04-trace-answer-dependencies\//]]]],
   ['05-save-graph · Python','계산 그래프와 비교 기록을 저장합니다.',[['그래프',[/^05-save-graph\//,/^04-save-graph\//,/^03-compare-calculation\//]]]]
  ]},
  '05-verification':{title:'Python 검사와 LLM 의미 검토를 구분하여 최종 판정합니다.',steps:[
   ['01-collect-artifacts · Python','산출물 참조와 해시를 수집합니다.',[['산출물',[/^01-collect-artifacts\//,'01-artifacts.json','artifact-refs.json']]]],
   ['02-check-execution-and-answer · Python','실행값과 gold를 대조합니다.',[['정답 비교',[/^02-check-execution-and-answer\//,'02-execution-and-answer.json']]]],
   ['03-check-provenance-structure · Python','인용 위치와 출처 연결을 검사합니다.',[['출처 검사',[/^03-check-provenance-structure\//,'03-provenance-structure.json']]]],
   ['04-check-graph-consistency · Python','코드와 그래프의 값을 비교합니다.',[['그래프 검사',[/^04-check-graph-consistency\//,'04-graph-consistency.json']]]],
   ['05-build-verification-request · Python','의미 검토 요청을 구성합니다.',[['요청',[/^05-build-verification-request\//]]]],
   ['06-LLM-verify-semantics · LLM','회사·기간·연산·단위·문맥 충분성을 검토합니다.',[['요청·응답',[/^06-LLM-verify-semantics\//]]]],
   ['07-check-verification-response · Python','응답 형식과 필수 항목을 검사합니다.',[['응답 검사',[/^07-check-verification-response\//,'07-check-verification-response.json']]]],
   ['08-record-verdict · Python','검사 결과를 종합하고 실패·불확실을 handler에 전달합니다.',[['판정',[/^08-record-verdict\//,'08-verdict.json','04-verdict.json']]]]
  ]},
  '06-exception-handler':{title:'실패 단계·근거를 수집하고 다음 차수의 대상 단계에 피드백을 연결합니다.',steps:[
   ['01-capture-exception · Python','어느 단계에서 어떤 오류가 발생했는지 기록합니다.',[['오류',[/^01-capture-exception\//]]]],
   ['02-build-feedback-request · Python','실패 입력·출력·로그 참조를 진단 요청으로 구성합니다.',[['요청',[/^02-build-feedback-request\//]]]],
   ['03-LLM-diagnose-and-feedback · LLM','문제 원인과 보완할 대상 단계·지시를 작성합니다.',[['진단',[/^03-LLM-diagnose-and-feedback\//]]]],
   ['04-route-retry · Python','다음 차수 피드백 원본과 소비 단계의 참조를 연결합니다.',[['재시도·피드백',[/^04-route-retry\//,/^feedback\/\d+-round\//]]]]
  ]},
  '07-human-review':{title:'사람이 계산과 분류 근거를 확인합니다. 자동 통과와 사람 승인은 별개입니다.',steps:[
   ['01-collect-review-package · Python','원문·코드·그래프·검증·피드백을 모읍니다.',[['검토 자료',[/^01-collect-review-package\//,/^01-collect-results\//]]]],
   ['02-review-calculation-and-classification · 사람','계산과 문맥/외부지식 분류를 검토합니다.',[['검토',[/^02-review-calculation-and-classification\//]]]],
   ['03-record-decision · 사람','승인·제외·대기와 이유를 기록합니다.',[['판정',[/^03-record-decision\//,/^02-record-decision\//]]]]
  ]}
 };
 return guides[stage==='02-review-and-correct'?'02-review':stage];
}
