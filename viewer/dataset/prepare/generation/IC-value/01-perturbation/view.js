function renderValuePerturbation(panel,row,variant){
 const plan=generationPlan(row,variant),intent=plan?.intent;
 if(intent?.value_pair)panel.append(box('값 주장 A / B',`${intent.value_pair[0]} / ${intent.value_pair[1]}`),box('삽입 위치',intent.perturb_position==='before'?'원래 주장 앞':'원래 주장 뒤',{ui:true}));
 renderGenerationGraphs(panel,row,variant);
}
