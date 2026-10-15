function answerRevision(row){
 const artifacts=row.run.artifacts,current=String(row.sample.reference_answer);
 const original=artifacts['01-source/01-receive-input/01-input.json']?.reference_answer??artifacts['reference-data.json']?.reference_answer??artifacts['data-comparison.json']?.reference_qca?.reference_answer??current;
 let previous=String(original),revision=0;
 const history=Object.entries(artifacts).filter(([path])=>/^data-history\/\d+-data\.json$/.test(path)).sort(([a],[b])=>a.localeCompare(b,undefined,{numeric:true}));
 for(const [,data] of [...history,['data.json',{reference_answer:current}]]){
  if(data?.reference_answer==null)continue;
  const value=String(data.reference_answer);if(value!==previous){revision++;previous=value;}
 }
 return {original:String(original),current,revision};
}
