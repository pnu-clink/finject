// Match recorded original dataset identity independently of collection name or difficulty.
function originalSourceType(provenance){
 const sourceId=provenance?.source_id;
 if(typeof sourceId==='string')for(const [prefix,type] of [['CodeFinQA-','FinQA'],['CodeTAT-QA-','TAT-QA'],['FinanceMath-','FinanceMath'],['FinanceReasoning-','FinanceReasoning']])if(sourceId.startsWith(prefix))return type;
 return provenance?.dataset==='TAT-QA'?'TAT-QA':'출처 미확인';
}
