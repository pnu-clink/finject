const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');
const ctx=vm.createContext({});vm.runInContext(html.slice(html.indexOf('function graphFormula('),html.indexOf('function relationFormulaComparison(')),ctx);
const root='reports/run/first-10-pot-validated-v3/test-0001';
const plan=JSON.parse(fs.readFileSync(root+'/04-perturbation/03-plan-ic-relation/plan.json'));
const review=[];
for(const key of ['A','B','C']){
 const graph=key==='A'?JSON.parse(fs.readFileSync(root+'/03-graph/04-save-graph/01-graph.json')):plan.graphs[key];
 const options={numeric:true,markedIds:plan.branches[key]?.relation_node_ids||[]};
 const tokens=ctx.graphFormula(graph,options),expression=tokens.map(t=>t.text).join('');
 assert(expression.startsWith('int(round('));
 if(key==='B')assert.equal(tokens.filter(t=>t.changed).map(t=>t.text).join(''),'(45000.0 * 2)');
 if(key==='C')assert.equal(tokens.filter(t=>t.changed).map(t=>t.text).join(''),'(80000.0 / 2)');
 review.push({branch:key,expression,stored_raw:plan.answers[key].raw});
}
// Grouping matters: 20 / (5 / 2) must not become (20 / 5) / 2.
const graph={output:'out',nodes:[{id:'a',kind:'constant',value:'20',inputs:[]},{id:'b',kind:'constant',value:'5',inputs:[]},{id:'c',kind:'constant',value:'2',inputs:[]},{id:'inner',kind:'operation',operator:'/',inputs:['b','c']},{id:'out',kind:'operation',operator:'/',inputs:['a','inner']}]};
assert.equal(ctx.graphFormula(graph,{numeric:true}).map(t=>t.text).join(''),'(20 / (5 / 2))');
graph.nodes[0].value='-2';graph.nodes[4].operator='**';graph.nodes[4].inputs=['a','c'];
assert.equal(ctx.graphFormula(graph,{numeric:true}).map(t=>t.text).join(''),'((-2) ** 2)');
graph.nodes[4].inputs=['out','c'];assert.throws(()=>ctx.graphFormula(graph),/\uc5f0\uacb0/);
console.log(JSON.stringify({checks:'stored branches, relation highlighting, parentheses, negative base, cycle rejection',review},null,2));
