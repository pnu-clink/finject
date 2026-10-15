const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');
new Function(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
const files={},ctx=vm.createContext({eventOf:(_,path)=>files[path],realizationStage:()=> 'source'});
vm.runInContext(html.slice(html.indexOf('function sourceComparisonSegments('),html.indexOf('function sourceComparisonText(')),ctx);
const row={sample:{context:'Original value 80,000.'}};
const added='Added value 90,000. ';
files['source/01-receive-input/04-source-binding.json']={generation_ref:'value'};
files['value/03-result.json']={original_context:row.sample.context,patches:[{start:0,end:0,before:'',text:added}]};
for(const [side,at] of [['A',added.length],['B',0]]){
 const base=added+row.sample.context,source='Attribution: ',final=base.slice(0,at)+source+base.slice(at);
 const preview={original_context:base,preview_context:final,source_condition:side+'_ONLY',patches:[{start:at,end:at,before:'',text:source}]};
 const segments=ctx.sourceComparisonSegments(row,preview);
 assert.equal(segments.map(s=>s.text).join(''),final);
 assert.equal(segments.filter(s=>s.kind==='VALUE').map(s=>s.text).join(''),added);
 assert.equal(segments.filter(s=>s.kind==='SOURCE_'+side).map(s=>s.text).join(''),source);
 assert.equal(segments.filter(s=>!s.kind).map(s=>s.text).join(''),row.sample.context);
 const kinds=segments.map(s=>s.kind);
 assert.ok(side==='A'?kinds.indexOf('VALUE')<kinds.indexOf('SOURCE_A'):kinds.indexOf('SOURCE_B')<kinds.indexOf('VALUE'));
 delete preview.source_condition;row.variant={plan:{source_condition:side+'_ONLY'}};
 assert.equal(ctx.sourceComparisonSegments(row,preview).filter(s=>s.kind==='SOURCE_'+side).map(s=>s.text).join(''),source);
 preview.preview_context+='changed';assert.throws(()=>ctx.sourceComparisonSegments(row,preview));
}
console.log('Original text, inherited value additions and independent A/B attribution remain distinct.');
