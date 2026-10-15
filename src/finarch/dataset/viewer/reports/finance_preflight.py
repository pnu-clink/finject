"""Render the saved full-distribution inventory in the common viewer; no model calls."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write

full=importlib.import_module('finarch.dataset.00-input.full_finance')

def build(inputs, output):
    inputs,output=Path(inputs).resolve(),Path(output).resolve()
    manifest=json.loads((inputs/'selection-manifest.json').read_text())
    syntax=json.loads((inputs/'code-syntax-audit.json').read_text())
    output.mkdir(parents=True,exist_ok=True)
    report={'format':'finance-preflight-v1','run_id':output.name,'input_directory':str(inputs),
            'summary':manifest['totals'],'counts':manifest['counts'],'exclusions':manifest['exclusions'],
            'syntax':syntax,'syntax_labels':full.SYNTAX_LABELS,'model_calls':0,
            'concurrency':{'api':200,'mode':'fixed','unit':'cases per scheduler; HTTP requests also capped per process'},
            'references':{name:{'path':str(inputs/name),'sha256':hashlib.sha256((inputs/name).read_bytes()).hexdigest()}
                          for name in ('input.json','selection-manifest.json','selection-log.json','code-syntax-audit.json')}}
    write(output/'finance-preflight.json',report)
    write(output/'summary.json',{'status':'INPUTS_PREPARED','families':manifest['families'],'model_calls':0})
    duplicates=[x for x in manifest['exclusions'] if x['reason']=='duplicate_qc']
    count_rows='\n'.join(f"|{name}|{r['total']}|{r['empty_context']}|{r['boolean_answer']}|{r['duplicate_qc']}|{r['selected']}|" for name,r in manifest['counts'].items())
    duplicate_rows='\n'.join(f"|{r['kept_raw_id']}|{r['raw_id']}|같음|" for r in duplicates)
    syntax_rows='\n'.join(f"|{full.SYNTAX_LABELS[k]}|{n}|" for k,n in syntax['pattern_counts'].items())
    template=Path(__file__).with_name('finance-preflight-readme.md').read_text()
    (output/'README.md').write_text(template.replace('{count_rows}',count_rows)
        .replace('{duplicate_rows}',duplicate_rows).replace('{syntax_rows}',syntax_rows)
        .replace('{union}',str(syntax['unique_cases_with_patterns'])).replace('{input_directory}',str(inputs))
        .replace('{run_id}',output.name)
        .replace('{total}',str(manifest['totals']['total']))
        .replace('{empty_context}',str(manifest['totals']['empty_context']))
        .replace('{boolean_answer}',str(manifest['totals']['boolean_answer']))
        .replace('{duplicate_qc}',str(manifest['totals']['duplicate_qc']))
        .replace('{selected}',str(manifest['totals']['selected'])))
    return report

def view(bundle):
    bundle=Path(bundle)
    report=json.loads((bundle/'finance-preflight.json').read_text())
    if report.get('format')!='finance-preflight-v1':raise ValueError('INVALID_PREFLIGHT_REPORT')
    payload={'format':'fin-arch-viewer-v1','runs':[],
             'batch':{'name':bundle.name,'layout':'finance-preflight-v1','rounds':[],'round':None,
                      'finance_preflight':report,'summary':report['summary'],
                      'readme':(bundle/'README.md').read_text()}}
    payload['revision']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    return payload

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=build(args.inputs,args.output)
    print(json.dumps(result['summary']))
