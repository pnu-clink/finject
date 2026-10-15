// Verify the read-only display projection against freshly generated sample graphs.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ctx=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../../../../viewer/dataset/reports/graph_syntax_samples.js'),'utf8'),ctx);
const shell=fs.readFileSync(path.join(__dirname,'../../../../viewer/dataset/shell.html'),'utf8');
vm.runInContext(shell.slice(shell.indexOf('function layoutLinkedGraph('),shell.indexOf('function drawLinkedGraph(')),ctx);
const report=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
for(const sample of report.samples){
 const graph=sample.graph,before=JSON.stringify(graph),view=ctx.controlGraphDisplay(graph),seen=new Set();
 assert.equal(JSON.stringify(graph),before,'The display must not mutate stored evidence');
 assert.equal(view.output,graph.control_flow?.display_output||graph.output);
 assert.equal(view.nodes.find(n=>n.id===view.output).computed,graph.nodes.find(n=>n.id===graph.output).computed);
 for(const node of view.nodes){
  assert(!node.control_internal);
  for(const id of node.inputs)assert(seen.has(id),'Visible inputs remain topologically connected');
  seen.add(node.id);
 }
 for(const edge of view.edges)assert(seen.has(edge.from)&&seen.has(edge.to));
 const layout=ctx.layoutLinkedGraph(view);
 for(const edge of view.control_edges||[]){
  assert(seen.has(edge.from)&&seen.has(edge.to));
  assert(layout.positions[edge.from].x<layout.positions[edge.to].x,'Control arrows run forward');
  assert(!view.edges.includes(edge),'Control links are separate from numeric operands');
 }
}
const graph=report.samples.find(s=>s.id==='while').graph,view=ctx.controlGraphDisplay(graph);
assert.equal(graph.control_flow.guards.length,4);
assert(!view.nodes.some(n=>['==','and','path_guard','not'].includes(n.operator)));
assert.deepEqual(Array.from(view.nodes.filter(n=>n.control_title).map(n=>n.label)),
 ['1회차 계속','2회차 계속','3회차 계속','4번째 조건에서 종료']);
const zeros=view.nodes.filter(n=>n.kind==='constant'&&n.value_type==='int'&&n.value==='0');
assert.equal(zeros.length,1);
assert.deepEqual(Array.from(ctx.graphSourceLines(zeros[0])),[4,5]);
assert.equal(view.control_edges.length,4);
const byId=new Map(view.nodes.map(node=>[node.id,node]));
assert.deepEqual(Array.from(view.control_edges.map(edge=>byId.get(edge.to).code_line)),[6,6,6,9]);
assert.deepEqual(Array.from(view.control_edges.map(edge=>ctx.graphControlLinkLabel(edge))),
 ['1회차 계속 → 선택된 계산','2회차 계속 → 선택된 계산','3회차 계속 → 선택된 계산','반복 종료 → 다음 계산']);
// User-authored equality operations must remain visible.
const equality={nodes:[{id:'a',kind:'constant',inputs:[]},{id:'b',kind:'operation',operator:'==',inputs:['a','a']}],
 edges:[{from:'a',to:'b',input_index:0},{from:'a',to:'b',input_index:1}],output:'b',variables:{answer:'b'},
 control_flow:{display_output:'b',events:[]}};
assert(ctx.controlGraphDisplay(equality).nodes.some(n=>n.operator==='=='));
const ended=JSON.parse(JSON.stringify(equality));
ended.control_flow.events=[{kind:'condition',control:'while',observed:false,line:3,iteration:1}];
ended.control_flow.links=[{from:'b',to:null,event_index:0,target_kind:'end'}];
const endView=ctx.controlGraphDisplay(ended),endLayout=ctx.layoutLinkedGraph(endView);
assert.equal(endView.nodes.find(n=>n.id==='control-end').kind,'control');
assert(endLayout.positions['control-end'].x>endLayout.positions.b.x);
assert.equal(endView.output,'b','The visual endpoint must not replace the numeric answer');
console.log('PASS: seven display projections, forward control links, per-iteration targets, loop exit, visual endpoint, shared zero, immutable records, user equality');
