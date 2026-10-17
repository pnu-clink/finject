"""Prepare all local TAT-QA arithmetic questions without context-only deduplication."""
import json
from pathlib import Path
from hashlib import sha256
from importlib import import_module
from finarch.dataset.schemas.validation import validate
from finarch.dataset.schemas.registry import describe
from finarch.shared.reference import load_raw

def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    spec=next(s for s in json.loads(Path('config/source-catalog.json').read_text())['sources'] if s['adapter']=='tatqa')
    source=(Path('config')/spec['path']).resolve();raw=source.read_bytes()
    assert sha256(raw).hexdigest()==spec['sha256'],'SOURCE_HASH_MISMATCH'
    provenance={k:spec[k] for k in ('name','sha256','url','commit')}
    adapter=import_module('finarch.dataset.00-input.adapters').tatqa
    samples=[];providers={};excluded=[];seen=set()
    for index,record in enumerate(load_raw(raw)):
        for q in record['questions']:
            if q['answer_type']!='arithmetic':
                excluded.append({'question_id':q['uid'],'reason':'NOT_ARITHMETIC','answer_type':q['answer_type']});continue
            sample=adapter(record,q,provenance)
            pair=(sample['question'],sample['context'])
            if pair in seen:
                excluded.append({'question_id':q['uid'],'reason':'DUPLICATE_QUESTION_AND_CONTEXT'});continue
            seen.add(pair)
            ordered={'id':f'test-{len(samples)+1:04d}','raw_id':sample['raw_id'],'question':sample['question'],'context':sample['context']}
            ordered.update(sample);samples.append(ordered)
            providers[sample['raw_id']]={'source':spec['name'],'record_index':index,'record':record,'question_id':q['uid']}
    validate('01-preparation.01-source.prepared-input',samples)
    def write(name,value):
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    write('input.json',samples);write('provider-records.json',providers);write('selection-log.json',excluded)
    manifest={'families':len(samples),'sources':[{**provenance,'path':str(source)}],'ids':[{'id':s['id'],'raw_id':s['raw_id']} for s in samples],'input_schema':{k:v for k,v in describe('01-preparation.01-source.prepared-input').items() if k!='schema'},'input_file_sha256':sha256((output/'input.json').read_bytes()).hexdigest(),'provider_file_sha256':sha256((output/'provider-records.json').read_bytes()).hexdigest(),'selection_policy':'All arithmetic questions; exact question/context duplicates removed; different questions sharing context retained.','exclusions':excluded}
    write('selection-manifest.json',manifest)
    write('preparation-result.json',{'status':'PASS','manifest_sha256':sha256((output/'selection-manifest.json').read_bytes()).hexdigest(),'model_calls':0})
    (output/'README.md').write_text(f'# TAT-QA full math input\n\nSources: {source}\nTarget {len(samples)}Questions, excluded {len(excluded)}Questions. Both non-surgical and question-and-type are excluding the same translations.\n\nThe input.json → selection-manifest.json→ selection-log.json sequence is verified. provider-records.json is the source preservation data. This step is the input integrity verification and the meaning verification is performed in Preparation.\n')
    return output/'input.json'

if __name__=='__main__':
    import sys
    print(prepare(sys.argv[1]))
