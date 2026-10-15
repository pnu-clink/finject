function sourceComparisonSegments(r,preview,baseOverride){
 const binding=eventOf(r,realizationStage(r)+'/01-receive-input/04-source-binding.json');
 const base=baseOverride||(binding&&eventOf(r,binding.generation_ref+'/03-result.json'));
 if(!base||base.original_context!==r.sample.context)throw Error('IC-VALUE 기준 원문 연결을 확인할 수 없습니다.');
 const apply=(chars,patches,kind)=>{
  const sorted=[...patches].sort((a,b)=>a.start-b.start);let end=0;
  for(const patch of sorted){if(!Number.isInteger(patch.start)||!Number.isInteger(patch.end)||patch.start<end||patch.end<patch.start||patch.end>chars.length||chars.slice(patch.start,patch.end).map(c=>c.text).join('')!==patch.before)throw Error('저장된 편집 위치와 기준 본문이 일치하지 않습니다.');end=patch.end;}
  for(const patch of sorted.reverse()){
   const segments=patch.segments||[{kind,text:patch.text}];
   if(segments.map(s=>s.text).join('')!==patch.text)throw Error('편집 색상 구간과 실제 응답이 일치하지 않습니다.');
   chars.splice(patch.start,patch.end-patch.start,...segments.flatMap(s=>Array.from(s.text).map(text=>({text,kind:s.kind}))));
  }
  return chars;
 };
 let chars=apply(Array.from(r.sample.context).map(text=>({text,kind:null})),base.patches,'VALUE');
 if(chars.map(c=>c.text).join('')!==preview.original_context)throw Error('출처 입력과 IC-VALUE 결과가 일치하지 않습니다.');
 const condition=preview.source_condition??r.variant?.plan?.source_condition??r.condition;
 chars=apply(chars,preview.patches,condition==='A_ONLY'?'SOURCE_A':'SOURCE_B');
 if(chars.map(c=>c.text).join('')!==preview.preview_context)throw Error('편집 적용 결과와 저장된 최종 본문이 일치하지 않습니다.');
 const segments=[];
 for(const char of chars){const last=segments.at(-1);if(last&&last.kind===char.kind)last.text+=char.text;else segments.push({...char});}
 return segments;
}
