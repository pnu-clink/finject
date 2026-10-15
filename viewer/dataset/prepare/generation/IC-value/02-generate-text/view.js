function renderValueTextDetails(panel,row,variant){
 const a=row.run.generation||{},plan=generationPlan(row,variant),patches=a[variant+'/02-generate-text/05-patches.json'];
 const pair=a[variant+'/02-generate-text/02-place-paired-sentence.json'];
 if(pair)panel.append(el('p','small','동일 문장 재사용 · 앞 유형의 문장을 뒤 위치에 배치했습니다. 새 LLM 호출은 '+pair.new_model_calls+'회입니다.'));
 if(plan?.intent?.perturb_position)panel.append(box('문장 배치',plan.intent.perturb_position==='before'?'추가 B 주장 · 원래 A 주장':'원래 A 주장 · 추가 B 주장',{ui:true}));
 for(const patch of patches||[])panel.append(box('추가한 값 문장',patch.text));
 renderConditionalAnswers(panel,plan);
}
