"""Disconnect-safe, resumable frozen Q/C evaluation; standard library only."""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from collections import Counter

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2));temporary.replace(path)

def run(root,endpoint,concurrency,repeats,model="qwen-27b"):
    root=Path(root).resolve();data=root/'dataset.json';items=json.loads(data.read_text())
    with (root/'schedule.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        lock.seek(0);lock.truncate();json.dump({'pid':os.getpid(),'started_at':time.time()},lock);lock.flush()
        config={'model':model,'endpoint':endpoint,'concurrency':concurrency,'repeats':repeats,'temperature':0,'max_tokens':4096,'dataset_sha256':hashlib.sha256(data.read_bytes()).hexdigest(),'planned':len(items)*repeats}
        if (root/'config.json').exists() and json.loads((root/'config.json').read_text())!=config:raise ValueError('CONFIG_CHANGED')
        write(root/'config.json',config)
        results=[];started=time.time()
        def report(status):
            counts=Counter(x['status'] for x in results);tokens=Counter()
            for x in results:tokens.update({k:v for k,v in x.get('usage',{}).items() if isinstance(v,int)})
            summary={'status':status,'planned':config['planned'],'processed':len(results),'counts':dict(counts),'tokens':dict(tokens),'elapsed_seconds':time.time()-started,'updated_at':time.time(),'by_repeat':{str(r):dict(Counter(x['status'] for x in results if x['repeat']==r)) for r in range(1,repeats+1)},'by_type':{t:dict(Counter(x['status'] for x in results if x['type']==t)) for t in sorted({i['type'] for i in items})},'accuracy':None,'note':'Completion is not correctness. Repeats use temperature 0, not independent random samples.'}
            write(root/'progress.json',summary)
            if status=='COMPLETED':write(root/'summary.json',summary)
        def one(task):
            r,n,item=task;folder=root/f'{r:02d}-repeat'/f'{n:04d}'
            schema={'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}
            payload={'model':model,'temperature':0,'max_tokens':4096,'messages':[{'role':'system','content':'Answer the question using the provided context. If conflicting information prevents a unique answer, explain the conflict. If necessary information is missing, state what is missing. Provide your final answer clearly.'},{'role':'user','content':'Question:\n'+item['question']+'\n\nContext:\n'+item['context']}],'response_format':{'type':'json_schema','json_schema':{'name':'answer','strict':True,'schema':schema}}}
            write(folder/'request.json',payload);start=time.time();result={'id':item['id'],'type':item['type'],'repeat':r}
            try:
                req=urllib.request.Request(endpoint+'/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=900) as stream:raw=json.load(stream)
                write(folder/'response.json',raw);result['usage']=raw.get('usage',{});result['finish_reason']=raw['choices'][0]['finish_reason']
                answer=json.loads(raw['choices'][0]['message']['content'])
                if set(answer)!={'answer'} or not isinstance(answer['answer'],str):raise ValueError('INVALID_SCHEMA')
                if result['finish_reason']!='stop':raise ValueError('INCOMPLETE_RESPONSE')
                result.update(status='COMPLETED',answer=answer['answer'])
            except Exception as error:result.update(status='ERROR',error=str(error))
            result['elapsed_seconds']=time.time()-start;write(folder/'result.json',result);return result
        report('RUNNING')
        for r in range(1,repeats+1):
            pending=[]
            for n,item in enumerate(items,1):
                saved=root/f'{r:02d}-repeat'/f'{n:04d}'/'result.json'
                if saved.exists():results.append(json.loads(saved.read_text()))
                else:pending.append((r,n,item))
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                for result in pool.map(one,pending):results.append(result);report('RUNNING')
        report('COMPLETED')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--endpoint',required=True);p.add_argument('--concurrency',type=int,default=3);p.add_argument('--repeats',type=int,default=5);p.add_argument('--model',default='qwen-27b');a=p.parse_args();run(a.root,a.endpoint,a.concurrency,a.repeats,a.model)
