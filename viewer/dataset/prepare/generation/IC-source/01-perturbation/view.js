function renderSourcePerturbation(panel,row,variant){
 const intent=generationPlan(row,variant)?.intent;
 if(intent){panel.append(box('출처 배정',intent.source_condition==='A_ONLY'?'Type 1 · 원래 A 주장에 출처 부여':'Type 2 · 추가 B 주장에 출처 부여',{ui:true}),el('p','small','한쪽에 출처 설명을 붙이는 제작 조건입니다. 출처 기재가 없는 쪽을 거짓이나 낮은 신뢰로 단정하지 않습니다.'));}
 renderGenerationGraphs(panel,row,variant);
}
