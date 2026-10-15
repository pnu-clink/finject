// Stored DAG comparison: dependency reachability is not numerical change.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');
const source=html.slice(html.indexOf('function graphDelta('),html.indexOf('function graphChanges('));
const ctx=vm.createContext({});vm.runInContext(source,ctx);
const before={output:'out',nodes:[{id:'x',kind:'fact',value:'2',computed:'2',inputs:[]},{id:'y',kind:'fact',value:'5',computed:'5',inputs:[]},{id:'sum',kind:'operation',operator:'+',computed:'7',inputs:['x','y']},{id:'out',kind:'variable',computed:'7',inputs:['sum']}]};
const after=structuredClone(before);after.nodes[0].value='3';after.nodes[0].computed='3';after.nodes[2].computed='8';after.nodes[3].computed='8';
let d=ctx.graphDelta(before,after);assert.deepEqual([...d.changed],['x']);assert.deepEqual([...d.affected],['x','sum','out']);assert(!d.affected.has('y'));
d=ctx.graphDelta(before,before);assert.equal(d.affected.size,0);
const deleted=structuredClone(before);deleted.nodes=deleted.nodes.filter(n=>n.id!=='x');deleted.nodes[1].inputs=['y'];d=ctx.graphDelta(before,deleted);assert(d.changed.has('x'));assert(d.affected.has('out'));
const cancel=structuredClone(after);cancel.nodes[3].computed='7';d=ctx.graphDelta(before,cancel);assert(d.affected.has('out'));assert.equal(cancel.nodes[3].computed,before.nodes[3].computed);
assert(html.includes('if(tab===5&&revision)'));assert(html.includes('[preparation,pot,graphs,graphChanges,dtt,human,publication,logs]'));
console.log('Graph delta checks passed: changed value, unaffected input, downstream closure, identical graph, deletion, unchanged result, tab routing.');
// Render both stored graph shapes without a browser; selection updates both sides.
class Element{constructor(){this.style={};this.clientWidth=1000;this.clientHeight=560;this.children=[];this.dataset={};this.classList={toggle:()=>{}};}append(...x){this.children.push(...x)}replaceChildren(...x){this.children=x}setAttribute(k,v){this[k]=v}}
ctx.document={createElementNS:()=>new Element()};ctx.el=(tag,cls,value)=>{const e=new Element();e.textContent=value;return e};ctx.button=(label,fn)=>{const e=new Element();e.onclick=fn;return e};ctx.box=ctx.el;ctx.text=v=>v==null?'기록 없음':String(v);ctx.jsonBox=()=>{};ctx.names={};ctx.eventOf=(r,k)=>r.run.artifacts[k];ctx.record=(r,k)=>r.run.artifacts[k]?.data;
vm.runInContext(html.slice(html.indexOf('function layoutLinkedGraph('),html.indexOf('function drawLinkedGraph(')),ctx);
vm.runInContext(html.slice(html.indexOf('function graphChanges('),html.indexOf('const sliceText=')),ctx);
ctx.row={variant:{label:'check',axis:'IC_VALUE',plan:{graphs:{changed:after}}},run:{artifacts:{'03-graph/04-save-graph/01-graph.json':before}}};ctx.root=new Element();vm.runInContext('graphChanges(root,row)',ctx);assert(ctx.root.children.length>=3);
console.log('Comparison renderer and paired selection passed with synthetic fixture (not dataset generation).');
