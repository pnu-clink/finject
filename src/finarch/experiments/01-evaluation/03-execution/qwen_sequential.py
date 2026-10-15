"""Sequential frozen Q/C evaluation against a ready OpenAI-compatible server."""
import argparse
import hashlib
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
schedule_lock = __import__('finarch.dataset.90-operations.schedule_lock', fromlist=['schedule_lock']).schedule_lock

def run(root, endpoint):
    root=Path(root);dataset=root/'dataset.json';items=json.loads(dataset.read_text())
    with schedule_lock(root):
        write(root/'config.json',{'model':'qwen-27b','endpoint':endpoint,'concurrency':1,'temperature':0,'max_tokens':4096,'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),'expected_requests':len(items)})
        while True:
            write(root/'progress.json',{'status':'WAITING_FOR_SERVER','planned':len(items)})
            try:
                with urllib.request.urlopen(endpoint+'/models',timeout=10) as r:models=json.load(r)
                if any(x['id']=='qwen-27b' for x in models['data']):break
            except Exception:pass
            time.sleep(10)
        results=[]
        for number,item in enumerate(items,1):
            target=root/'responses'/f'{number:04d}.json'
            if target.exists():results.append(json.loads(target.read_text()));continue
            payload={'model':'qwen-27b','temperature':0,'max_tokens':4096,'messages':[{'role':'system','content':'Answer the question using the provided context. If conflicting information prevents a unique answer, explain the conflict. If necessary information is missing, state what is missing. Provide your final answer clearly.'},{'role':'user','content':'Question:\n'+item['question']+'\n\nContext:\n'+item['context']}]}
            schema={'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}
            payload['response_format']={'type':'json_schema','json_schema':{'name':'answer','strict':True,'schema':schema}}
            write(root/'requests'/f'{number:04d}.json',payload)
            start=time.monotonic()
            try:
                req=urllib.request.Request(endpoint+'/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=900) as r:response=json.load(r)
                write(root/'raw-responses'/f'{number:04d}.json',response)
                answer=json.loads(response['choices'][0]['message']['content'])
                if set(answer)!={'answer'} or not isinstance(answer['answer'],str):raise ValueError('INVALID_ANSWER_SCHEMA')
                result={'id':item['id'],'type':item['type'],'status':'COMPLETED','response':response}
            except Exception as error:result={'id':item['id'],'type':item['type'],'status':'ERROR','error':str(error)}
            result['elapsed_seconds']=time.monotonic()-start;write(target,result);results.append(result)
            write(root/'progress.json',{'status':'RUNNING','planned':len(items),'completed':number,'errors':sum(x['status']=='ERROR' for x in results)})
        counts=Counter(x['status'] for x in results);usage=Counter()
        for x in results:usage.update({k:v for k,v in x.get('response',{}).get('usage',{}).items() if isinstance(v,int)})
        summary={'status':'COMPLETED','counts':dict(counts),'tokens':dict(usage),'by_type':{t:dict(Counter(x['status'] for x in results if x['type']==t)) for t in sorted({x['type'] for x in results})},'accuracy':None,'accuracy_note':'No validated perturbed-answer scoring contract; response completion is not correctness.'}
        write(root/'summary.json',summary);write(root/'progress.json',summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--endpoint',required=True);a=p.parse_args();run(a.root,a.endpoint)
