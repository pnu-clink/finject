// Read stored plans; verify display compaction without executing their Python or any models.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx=vm.createContext({console});
const shell=fs.readFileSync('viewer/dataset/shell.html','utf8');
vm.runInContext(shell.slice(shell.indexOf('function layoutLinkedGraph('),shell.indexOf('function drawLinkedGraph(')),ctx);
vm.runInContext(fs.readFileSync('viewer/dataset/evaluation/graph.js','utf8'),ctx);
const results=[];
function check(name,fn){fn();results.push(name);}
check('Final answers mark numeric differences; missing EA values never count as zero',()=>{
 const graph=(computed,state)=>({output:'answer',nodes:[{id:'answer',computed,evaluation:{state:state||'KNOWN'}}]});
 assert.equal(ctx.evaluationAnswerComparison(graph('-10.9'),graph('-30.9')).different,true);
 assert.equal(ctx.evaluationAnswerComparison(graph(0),graph('0')).different,false);
 assert.equal(ctx.evaluationAnswerComparison(graph(.1+.2),graph(.3)).different,false);
 for(const g of [graph(null),graph(''),graph('unavailable'),graph(10,'BLOCKED'),graph(10,'MISSING')])assert.equal(ctx.evaluationAnswerComparison(graph(10),g),null);
});
const base='reports/run/20260917-003/02-generation/01-round/test-0001/';
const types=['01-ic-value-before','03-ic-source-type-1','05-ic-relation','06-ea-earlier-input','07-ea-later-input'];
const plans=types.map(type=>JSON.parse(fs.readFileSync(base+type+'/01-perturbation/03-result.json','utf8')).plan);
check('Every input and operation survives assignment compaction',()=>{
 for(const plan of plans)for(const graph of [plan.original_graph,plan.graph]){
  const compact=ctx.evaluationCompactGraph(graph);
  assert(compact.nodes.length<graph.nodes.length);
  for(const node of graph.nodes){
   const mapped=compact.representatives.get(node.id),kept=compact.nodes.find(n=>n.id===mapped);
   assert(kept.sourceIds.includes(node.id));
   if(node.kind!=='variable')assert.equal(mapped,node.id);
   if(node.kind==='operation')assert.equal(JSON.stringify(kept.inputs),JSON.stringify(node.inputs.map(id=>compact.representatives.get(id))));
  }
  assert.equal(compact.nodes.find(n=>n.id===compact.output).computed,graph.nodes.find(n=>n.id===graph.output).computed);
 }
});
check('Input order and repeated operands remain ordered',()=>{
 const graph={output:'v',nodes:[{id:'f',kind:'fact',label:'f',inputs:[],value:'4',computed:'4'},{id:'o',kind:'operation',label:'-',operator:'-',inputs:['f','f'],computed:'0'},{id:'v',kind:'variable',label:'answer',inputs:['o'],computed:'0'}]};
 assert.equal(JSON.stringify(ctx.evaluationCompactGraph(graph).nodes.find(n=>n.id==='o').inputs),'["f","f"]');
});
check('Renumbered IC-relation facts merge by meaning, not AST node IDs',()=>{
 const plan=plans[2],model=ctx.evaluationMergeGraphs(ctx.evaluationCompactGraph(plan.original_graph),ctx.evaluationCompactGraph(plan.graph),plan.target);
 const operand=model.nodes.find(n=>n.fact_id==='other_2018');
 assert(operand.sides.includes('A')&&operand.sides.includes('B'));
 assert(model.nodes.some(n=>n.target&&n.sides.join('')==='B'&&n.kind==='operation'));
 assert.notEqual(model.outputs.A,model.outputs.B);
 for(const node of model.nodes)assert.equal(new Set(node.sides).size,node.sides.length);
});
check('EA missing values never become zero or the original value',()=>{
 const plan=plans[3],model=ctx.evaluationMergeGraphs(ctx.evaluationCompactGraph(plan.original_graph),ctx.evaluationCompactGraph(plan.graph),plan.target);
 const missing=model.nodes.find(n=>n.evaluation?.state==='MISSING');
 assert.equal(ctx.evaluationNodeValue(missing),'근거 없음');assert.equal(missing.computed,undefined);
 assert.equal(ctx.evaluationNodeValue(model.nodes.find(n=>n.id===model.outputs.B)),'계산 불가');
 assert(model.nodes.some(n=>n.target&&n.sides.join('')==='A'));
});
check('Different external provenance is not merged',()=>{
 const graph=id=>({nodes:[{id:'f',kind:'fact',label:'f',fact_id:'f',inputs:[],computed:'1',evidence_id:id}],output:'f'});
 const model=ctx.evaluationMergeGraphs(ctx.evaluationCompactGraph(graph('source-a')),ctx.evaluationCompactGraph(graph('source-b')),'f');
 assert.equal(model.nodes.length,2);
});
check('Control targets are retained and condition edges stay distinct',()=>{
 const graph={nodes:[{id:'c',kind:'control',label:'if',inputs:[],computed:'True'},{id:'f',kind:'fact',label:'f',inputs:[],computed:'1'},{id:'v',kind:'variable',label:'answer',inputs:['f'],computed:'1'}],output:'v',control_edges:[{from:'c',to:'v',kind:'control'}]};
 const compact=ctx.evaluationCompactGraph(graph);assert(compact.nodes.some(n=>n.id==='v'));
 const model=ctx.evaluationMergeGraphs(compact,null,null);assert.equal(model.edges.filter(e=>e.control).length,1);
 const layout=ctx.evaluationGraphLayout(model,450),edge=model.edges.find(e=>e.control);assert(layout.positions.get(edge.to).y>layout.positions.get(edge.from).y);
});
check('Long paths stay within 680 pixels and grow vertically',()=>{
 const nodes=Array.from({length:50},(_,i)=>({id:'n'+i,inputs:i?['n'+(i-1)]:[],kind:i?'operation':'fact',operator:'+',label:'node'+i,computed:String(i)}));
 const compact=ctx.evaluationCompactGraph({nodes,output:'n49'}),model=ctx.evaluationMergeGraphs(compact,null,null);
 for(const width of [300,450,2000]){
  const layout=ctx.evaluationGraphLayout(model,width);assert(layout.width<=680);assert(layout.height>4000);
  for(const at of layout.positions.values())assert(at.x>=0&&at.x+at.width<=layout.width);
 }
});
check('Presentation keeps every compact node and selects an orientation that fits the viewport',()=>{
 for(const plan of plans){
  const model=ctx.evaluationMergeGraphs(ctx.evaluationCompactGraph(plan.original_graph),ctx.evaluationCompactGraph(plan.graph),plan.target);
  for(const [width,height] of [[340,320],[650,500]]){
   const layout=ctx.evaluationGraphPresentation(model,width,height),scale=Math.min(width/layout.width,height/layout.height);
   assert.equal(layout.positions.size,model.nodes.length);assert(layout.width*scale<=width+.01);assert(layout.height*scale<=height+.01);
   for(const at of layout.positions.values())assert(at.x>=0&&at.y>=0&&at.x<layout.width&&at.y<layout.height);
  }
 }
});
check('Missing nodes and cycles fail explicitly, without modifying saved graphs',()=>{
 assert.throws(()=>ctx.evaluationCompactGraph({output:'x',nodes:[{id:'x',kind:'operation',inputs:['missing']}]}));
 assert.throws(()=>ctx.evaluationCompactGraph({output:'x',nodes:[{id:'x',kind:'variable',inputs:['y']},{id:'y',kind:'variable',inputs:['x']}]}));
 for(let i=0;i<plans.length;i++)assert.equal(JSON.stringify(plans[i]),JSON.stringify(JSON.parse(fs.readFileSync(base+types[i]+'/01-perturbation/03-result.json','utf8')).plan));
});
console.log(JSON.stringify({status:'PASS',checks:results.length,results,model_calls:0,production_writes:0},null,2));
