// Navigation must preserve the complete list and update the active review target.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function element(dataset = {}) {
  const classes = new Set();
  return { dataset, attrs: {}, classes, scrolls: 0,
    classList: { add: key => classes.add(key), remove: key => classes.delete(key),
      toggle(key, enabled) { if (enabled) classes.add(key); else classes.delete(key); } },
    setAttribute(key, value) { this.attrs[key] = value; },
    scrollIntoView() { this.scrolls++; } };
}
const metrics = Array.from({ length: 7 }, () => element());
const rows = Array.from({ length: 7 }, (_, index) => element({ type: String(index) }));
const cases = ['test-0001', 'test-0002'].map(name => element({ case: name }));
cases[0].classes.add('selected');
const elements = { metrics: { children: metrics },
  comparison: { querySelectorAll: () => rows,
    querySelector: selector => rows.find(row => selector.includes('"' + row.dataset.type + '"')) },
  cases: { querySelector: selector => selector === '.selected'
    ? cases.find(item => item.classes.has('selected'))
    : cases.find(item => selector.includes('"' + item.dataset.case + '"')) }, filter: {}, search: {}, dialog: {open:false} };
const context = vm.createContext({ console, URLSearchParams, location: { search: '' }, sessionStorage: { getItem() { return null; } },
  document: { addEventListener() {}, getElementById: id => elements[id] } });
vm.runInContext(fs.readFileSync('viewer/dataset/annotation/manager.js', 'utf8'), context);
vm.runInContext(`
 annotationState.view={groups:[{id:'one',cases:[
   {case:'test-0001',flags:['DISAGREE'],rows:Array.from({length:7},()=>({flags:[],cells:{A:{decision:'APPROVED',confirmed:true,missing:false,issues:[]}}}))},
   {case:'test-0002',flags:['DISAGREE'],rows:Array.from({length:7},()=>({flags:[],cells:{A:{decision:'APPROVED',confirmed:true,missing:false,issues:[]}}}))}
 ]}]}; annotationState.groupId='one'; annotationState.caseName='test-0001';
 globalThis.calls={list:0,case:0,evidence:0,summary:0};
 render=()=>{throw Error('Full render during type navigation');};
 renderList=()=>calls.list++;
 renderCase=()=>calls.case++;
 loadEvidence=()=>calls.evidence++;
 renderManagerSummary=()=>calls.summary++;
 globalThis.originalMatchesCase=matchesCase;
 matchesCase=()=>true;matchesManagerReview=()=>true;
`, context);
let checks = 0;
function check(name, fn) { fn(); checks++; console.log('PASS: ' + name); }
check('Type navigation changes highlights and review target without rebuilding the list', () => {
  context.selectType(1);
  assert.equal(context.calls.list, 0); assert.equal(context.calls.case, 0); assert.equal(context.calls.summary, 1);
  assert(rows[1].classes.has('selected')); assert(metrics[1].classes.has('selected'));
  assert(!rows[0].classes.has('selected')); assert.equal(rows[1].scrolls, 1);
});
check('Repeated selection and filtered types do not rebuild or change the active target', () => {
  context.selectType(1);
  vm.runInContext('annotationState.typeFilters.delete(2)', context);
  context.selectType(2);
  assert.equal(context.calls.summary, 1); assert(rows[1].classes.has('selected'));
});
check('Case navigation preserves list nodes and fetches only the selected case evidence', () => {
  context.selectCase('test-0002');
  assert.equal(context.calls.list, 0); assert.equal(context.calls.case, 1); assert.equal(context.calls.evidence, 1);
  assert(cases[1].classes.has('selected')); assert(!cases[0].classes.has('selected'));
  assert.equal(cases[1].attrs['aria-current'], 'true'); assert.equal(cases[0].attrs['aria-current'], 'false');
});
check('Selecting the same or an absent case avoids duplicate evidence requests', () => {
  context.selectCase('test-0002'); context.selectCase('test-9999');
  assert.equal(context.calls.evidence, 1);
});
check('Next disagreement preserves controls and wraps within the existing filtered list', () => {
  vm.runInContext(`matchesCase=originalMatchesCase;annotationState.filter='DISAGREE';annotationState.search='test-000';annotationState.sourceType='TAT-QA';annotationState.typeFilters=new Set([0,1]);annotationState.hideSuccess=true;group().cases.forEach(item=>item.source_type='TAT-QA');`, context);
  elements.filter.value='DISAGREE';elements.search.value='test-000';
  context.nextDisagreement();
  assert.equal(context.calls.list, 0); assert.equal(elements.filter.value, 'DISAGREE'); assert.equal(elements.search.value, 'test-000');
  assert.equal(vm.runInContext('annotationState.filter',context),'DISAGREE');
  assert.equal(vm.runInContext('annotationState.search',context),'test-000');
  assert.equal(vm.runInContext('annotationState.sourceType',context),'TAT-QA');
  assert.equal(vm.runInContext('JSON.stringify([...annotationState.typeFilters])',context),'[0,1]');
  assert.equal(vm.runInContext('annotationState.hideSuccess',context),true);
  assert(cases[0].classes.has('selected'));
});
check('Physical V shortcut keeps the disagreement filter with a Korean key value', () => {
  let prevented=false,stopped=false;
  context.handleShortcut({code:'KeyV',key:'ㅍ',target:{closest:()=>null},preventDefault(){prevented=true;},stopImmediatePropagation(){stopped=true;}});
  assert.equal(context.currentCase().case,'test-0002');assert(prevented);assert(stopped);
  assert.equal(elements.filter.value,'DISAGREE');assert.equal(elements.search.value,'test-000');assert.equal(context.calls.list,0);
});
check('V respects Source type, search and manager filters instead of jumping to hidden cases', () => {
  vm.runInContext(`annotationState.caseName='test-0001';group().cases[1].source_type='FinanceReasoning';annotationState.search='';`,context);
  context.nextDisagreement();assert.equal(context.currentCase().case,'test-0001');
  vm.runInContext(`annotationState.sourceType='ALL';annotationState.search='test-0002';`,context);
  context.nextDisagreement();assert.equal(context.currentCase().case,'test-0002');
  assert.equal(vm.runInContext('annotationState.search',context),'test-0002');
  vm.runInContext(`annotationState.search='';matchesManagerReview=item=>item.case==='test-0002';`,context);
  context.nextDisagreement();assert.equal(context.currentCase().case,'test-0002');assert.equal(context.calls.list,0);
  vm.runInContext('matchesManagerReview=()=>true;',context);
});
check('No disagreement in the current filter leaves the filter and active case unchanged', () => {
  vm.runInContext(`annotationState.filter='REJECTED';annotationState.search='0002';`,context);
  elements.filter.value='REJECTED';elements.search.value='0002';
  const before={...context.calls};context.nextDisagreement();
  assert.equal(context.currentCase().case,'test-0002');assert.equal(elements.filter.value,'REJECTED');assert.equal(elements.search.value,'0002');
  assert.deepEqual({...context.calls},before);
  vm.runInContext(`annotationState.filter='ALL';annotationState.search='';annotationState.sourceType='ALL';annotationState.hideSuccess=false;`,context);
});
check('All-success and its complement partition complete seven-type cases', () => {
  vm.runInContext(`globalThis.successCase={case:'test-0003',flags:['NOTE'],rows:Array.from({length:7},()=>({flags:['NOTE'],cells:{A:{decision:'APPROVED',confirmed:true,missing:false,issues:[]},B:{decision:'APPROVED',confirmed:true,missing:false,issues:[]}}}))};`, context);
  assert(context.originalMatchesCase(context.successCase, 'ALL_SUCCESS', ''));
  assert(!context.originalMatchesCase(context.successCase, 'NOT_ALL_SUCCESS', ''));
  context.successCase.rows[6].cells.B.decision='PENDING';
  assert(!context.originalMatchesCase(context.successCase, 'ALL_SUCCESS', ''));
  assert(context.originalMatchesCase(context.successCase, 'NOT_ALL_SUCCESS', ''));
});
check('Missing, unconfirmed, rejected, and malformed success ratings remain outside success', () => {
  for (const changes of [{missing:true},{confirmed:false},{decision:'REJECTED'},{issues:['BAD']}]) {
    const row={flags:[],cells:{A:{decision:'APPROVED',confirmed:true,missing:false,issues:[],...changes}}};
    assert(!context.rowIsSuccessful(row));
  }
  assert(!context.rowIsSuccessful({flags:['CONTENT'],cells:{A:{decision:'APPROVED',confirmed:true,missing:false,issues:[]}}}));
});
check('Success exclusion restricts A/D and selection to the visible failed types', () => {
  vm.runInContext(`annotationState.typeFilters=new Set([0,1,2,3,4,5,6]);annotationState.hideSuccess=true;currentCase().rows[2].cells.A.decision='PENDING';currentCase().rows[5].cells.A.decision='REJECTED';annotationState.type=2;`,context);
  assert.equal(JSON.stringify(context.visibleTypeIndices()),'[2,5]');
  context.moveType(1);assert(rows[5].classes.has('selected'));
  const count=context.calls.summary;context.selectType(0);assert.equal(context.calls.summary,count);
  context.moveType(-1);assert(rows[2].classes.has('selected'));
});
console.log(JSON.stringify({ status: 'PASS', checks, model_calls: 0 }));
