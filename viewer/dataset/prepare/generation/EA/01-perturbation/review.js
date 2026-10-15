function eaStage15Review(p,r){
 const review=eventOf(r,`04-perturbation/variants/${r.label}/04-deletion-check.json`);if(!review)return;
 const section=el('section','box');section.append(el('h3','','15번 EA · '+(review.status==='PASS'?'이번 범위 완료':'검사 실패')),
 el('p','',`입력 순서 ${review.selection.input_order}: ${eaInputName(review.selection.fact_id)} ${review.selection.original_value} 삭제 · 다른 입력 유지`),
 el('p','small',`${Object.values(review.checks).filter(Boolean).length}/${Object.keys(review.checks).length}개 검사 통과 · ${review.tests?'로컬 회귀 검사 '+review.tests.run+'개 '+(review.tests.passed?'통과':'실패'):'별도 회귀 검사 기록 없음'} · 역산·우회 보류 · ${eventOf(r,realizationStage(r)+'/03-result/metadata.json')?.stage16_status==='PASS'?'01-generate-text 문장 생성 완료 · '+auditStatus(r):'최종 문장·의미 검사는 01-generate-text / 02-audit-meaning'}`));
 jsonBox(section,'15번 검사 결과 · 직접 잔존·원본 보존·보류 항목',review);p.append(section);
}
