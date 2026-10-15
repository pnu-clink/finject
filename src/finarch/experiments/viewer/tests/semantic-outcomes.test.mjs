import test from 'node:test';
import assert from 'node:assert/strict';
import { outcomePage, outcomeCategories } from '../semantic-outcomes.mjs';

test('five categories preserve rows and distinguish original/H1/source scopes', () => {
  const rows = [
    {variant:'EA_01', semantic_answerability:'SUPPORTED_ANSWER', model:'m', prompt_condition:'guided', reasoning:'on'},
    {variant:'EA_02', semantic_answerability:'UNCLASSIFIED', model:'m', prompt_condition:'guided', reasoning:'on'},
    {variant:'IC_SOURCE_A_ONLY', semantic_answerability:'SUPPORTED_ABSTENTION', model:'m', prompt_condition:'guided', reasoning:'on'},
    {variant:'ORIGINAL', semantic_answerability:'UNCLASSIFIED', model:'m', prompt_condition:'guided', reasoning:'on'}
  ];
  const count = chosen => ({total:chosen.length, ...Object.fromEntries(outcomeCategories.map(c => [c, chosen.filter(r=>r.semantic_answerability===c).length]))});
  const summary = {run:'test', categories:{}, groups:[], scopes:{all:count(rows), h1:count(rows.slice(0,2)), variants:count(rows.slice(0,3)), originals:count(rows.slice(3))}};
  assert.equal(outcomePage(summary, rows).total, 4);
  assert.equal(outcomePage(summary, rows, {scope:'variants'}).total, 3);
  assert.equal(outcomePage(summary, rows, {scope:'all'}).total, 4);
  assert.equal(outcomePage(summary, rows, {category:'UNCLASSIFIED'}).matching, 2);
  assert.equal(outcomePage(summary, rows, {scope:'originals'}).counts.UNCLASSIFIED, 1);
  assert.throws(()=>outcomePage(summary, rows, {scope:'bogus'}));
  assert.throws(()=>outcomePage(summary, rows, {category:'ANSWERABLE'}));
  assert.throws(()=>outcomePage(summary, rows, {offset:'-1'}));
  summary.scopes.all.total=1;
  assert.throws(()=>outcomePage(summary, rows), /counts/);
});


test('all raw values, missing, null and empty remain distinct with conserving totals', () => {
  const rows = [{}, {semantic_answerability:null}, {semantic_answerability:''},
    {semantic_answerability:'UNCLASSIFIED'}, {semantic_answerability:'NEW_VALUE'},
    {semantic_answerability:'NEW_VALUE'}, {semantic_answerability:false}];
  const result = outcomePage({ categories: {}, scopes: {}, groups: [] }, rows);
  assert.equal(result.total, 7);
  assert.equal(Object.values(result.counts).reduce((a,b)=>a+b,0), 7);
  assert.equal(result.counts.UNCLASSIFIED, 1);
  assert.equal(result.counts.NEW_VALUE, 2);
  assert.equal(result.counts['\0missing'], 1);
  assert.equal(result.counts['\0null'], 1);
  assert.equal(result.counts['\0empty'], 1);
  assert.equal(result.counts.SUPPORTED_ANSWER, 0);
  assert.equal(Object.values(result.groups[0]).filter(v=>typeof v==='number').reduce((a,b)=>a+b,0), 14);
  assert.equal(outcomePage({categories:{}}, rows, {category:'\0null'}).matching, 1);
});
