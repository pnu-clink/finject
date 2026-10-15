/* Exercise actual package navigation, persistence format and import isolation. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const {create,shortcut}=require('../../../../viewer/dataset/ea-inverse-annotation-state.js');
const data=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),s=create(data);
assert.equal(data.n,1354);assert.equal(data.items,2708);assert.equal(data.cases[0].id,'id-0001');assert.equal(data.cases.at(-1).id,'id-1354');
assert.throws(()=>s.decide('accept'));s.start('__QA__');s.jump('id-0956');s.kind(1);assert.equal(s.type,'EA_02');assert.equal(s.key(),'id-0956:EA_02');s.move(1);assert.equal(s.key(),'id-0957:EA_02');s.move(-1);s.kind(-1);assert.equal(s.key(),'id-0956:EA_01');
s.decide('reject');s.comment('Q/C 확인 필요');const saved=s.exported();s.decide('accept');assert.equal(s.labels.get(s.key()).comment,'');assert.throws(()=>s.comment('not allowed'));s.back();assert.equal(s.labels.get(s.key()).comment,'Q/C 확인 필요');
s.kind(1);assert.equal(s.labels.has(s.key()),false);s.decide('pending');const output=s.exported();assert.equal(output.counts.checked,2);assert.equal(output.counts.unreviewed,2706);assert.equal(output.counts.pending,1);
const resumed=create(data);resumed.imported(output);assert.equal(resumed.key(),s.key());assert.deepEqual(resumed.exported().labels,output.labels);assert.equal(resumed.annotator,'__QA__');
const before=JSON.stringify(resumed.exported().labels);for(const mutate of [v=>v.snapshot_sha256='bad',v=>v.labels.push(v.labels[0]),v=>v.labels[0].type='IC',v=>v.labels[0].content_sha256='bad',v=>v.labels[0].decision='VALID',v=>v.labels[0].updated_at='bad',v=>{v.labels[0].decision='accept';v.labels[0].comment='bad';}]){const v=structuredClone(output);mutate(v);assert.throws(()=>resumed.imported(v));assert.equal(JSON.stringify(resumed.exported().labels),before);}
resumed.jump('id-0001');resumed.move(-1);assert.equal(resumed.key(),'id-0001:EA_02');resumed.jump('id-1354');resumed.move(1);assert.equal(resumed.key(),'id-1354:EA_02');resumed.kind(1);assert.equal(resumed.type,'EA_02');
resumed.jump('id-0956');resumed.kind(-1);resumed.decide('accept');resumed.labels.get(resumed.key()).updated_at='2099-01-01T00:00:00.000Z';const merged=resumed.imported(saved,{merge:true});assert.equal(merged.kept,1);assert.equal(resumed.labels.get('id-0956:EA_01').decision,'accept');
const count=output.counts;assert.equal(count.accept+count.reject+count.pending+count.unreviewed,2708);assert.equal(data.cases.filter(c=>c.items.every(v=>v.display_ko.reason&&v.display_ko.missing_quantity)).length,1354);
console.log('PASS: full coverage, name gate, ID/type navigation, decisions/comments/undo, JSON round trip, atomic invalid import, latest-record merge, count conservation');
const pair=create(data);pair.start('__QA_PAIR__');pair.jump('id-0001');
for(let n=1;n<=6;n++){
 const expected={type:n%2?'EA_01':'EA_02',decision:['accept','reject','pending'][Math.floor((n-1)/2)]};
 assert.deepEqual(shortcut('Digit'+n),expected);assert.deepEqual(shortcut('Numpad'+n),expected);
 const other=expected.type==='EA_01'?'EA_02':'EA_01',before=JSON.stringify(pair.labels.get(pair.key(other)));
 pair.decide(expected.decision,expected.type);assert.equal(JSON.stringify(pair.labels.get(pair.key(other))),before);
 assert.equal(pair.labels.get(pair.key(expected.type)).decision,expected.decision);assert.equal(pair.index,0);
}
pair.comment('left comment','EA_01');pair.comment('right comment','EA_02');assert.equal(pair.labels.get('id-0001:EA_01').comment,'left comment');assert.equal(pair.labels.get('id-0001:EA_02').comment,'right comment');
pair.setFilters({EA_01:'true',EA_02:'all'});assert.equal(pair.visible.length,data.cases.filter(c=>c.items[0].inverse_review.inverse_possible).length);assert.equal(pair.visible.length,609);pair.move(1);assert.equal(data.cases[pair.index].items[0].inverse_review.inverse_possible,true);
pair.setFilters({EA_01:'true',EA_02:'false'});assert.ok(pair.visible.every(i=>data.cases[i].items[0].inverse_review.inverse_possible&&!data.cases[i].items[1].inverse_review.inverse_possible));const filtered=create(data);filtered.imported(pair.exported());assert.deepEqual(filtered.filters,pair.filters);assert.deepEqual(filtered.visible,pair.visible);assert.equal(filtered.exported().labels.length,2);
const old=structuredClone(output);delete old.view;const legacy=create(data);legacy.imported(old);assert.deepEqual(legacy.exported().labels,old.labels);assert.equal(legacy.visible.length,1354);
pair.jump('id-0001');assert.deepEqual(pair.filters,{EA_01:'all',EA_02:'all'});assert.equal(pair.counts().checked,2);assert.equal(pair.counts().unreviewed,2706);
for(const c of data.cases)for(const v of c.items)for(const r of v.removals)assert.equal(Array.from(c.original_context).slice(r.start,r.end).join(''),r.text);
console.log('PASS: 1/3/5 left and 2/4/6 right, independent comments, exact removal coordinates, combined inverse filters, filtered navigation, legacy JSON compatibility, filtered save round trip');
if(process.argv[3]){
 const html=fs.readFileSync(process.argv[3],'utf8');
 const embedded=JSON.parse(html.match(/<script id="package-data" type="application\/json">(.*?)<\/script>/s)[1]);
 const draft=JSON.parse(html.match(/<script id="annotation-draft" type="application\/json">(.*?)<\/script>/s)[1]);
 assert.deepEqual(embedded,data);assert.ok(draft.labels.length>0);assert.ok(draft.annotator.startsWith('__QA_'));
 const roundTrip=create(embedded);roundTrip.imported(draft);assert.deepEqual(roundTrip.exported().labels,draft.labels);assert.deepEqual(roundTrip.counts(),draft.counts);assert.deepEqual(roundTrip.exported().position,draft.position);
 assert.equal((html.match(/data-id="id-\d{4}"/g)||[]).length,1354);
 const link=html.match(/<a\b[^>]*\bid="html-download"[^>]*>/)[0];assert.ok(link.includes('hidden'));assert.ok(!/\bhref=/.test(link));
 assert.ok(draft.labels.some(v=>v.comment.includes('</script>')&&v.comment.includes('검증')));
 assert.ok(!/<(?:script|link|iframe|img)\b[^>]*(?:src|href)\s*=/i.test(html));
 console.log('PASS: actual exported HTML preserves all1354 cases, annotation name/labels/comments/position, Unicode and script-like text, clean download link, and no external assets');
}
