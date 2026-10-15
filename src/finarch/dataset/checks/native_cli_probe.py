"""Offline Codex protocol probe. Loopback responses only; never a real model."""
import json
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from finarch.shared.providers.cli import build_command, read_settings


def probe(config_path, action=None, role='01-preparation.03-calculation.pot'):
    requests=[]
    class Server(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=self.rfile.read(int(self.headers.get('Content-Length',0)))
            encoding=self.headers.get('Content-Encoding')
            if encoding=='zstd':
                from compression import zstd
                body=zstd.decompress(body)
            payload=json.loads(body)
            requests.append({'tools':[{k:t.get(k) for k in ('type','name')} for t in payload.get('tools',[])],
                             'authorization_header_present':bool(self.headers.get('Authorization')),
                             'tool_outputs':[v.get('output') for v in payload.get('input',[]) if v.get('type') in ('function_call_output','custom_tool_call_output')]})
            item={'id':'msg_local_probe','type':'message','role':'assistant','status':'completed',
                  'content':[{'type':'output_text','text':'{"ok":true}','annotations':[]}]}
            if action and len(requests)==1:
                if action=='apply_patch':
                    item={'id':'call_local_probe','call_id':'call_local_probe','type':'custom_tool_call','name':'apply_patch',
                          'input':'*** Begin Patch\n*** Add File: '+str(sentinel)+'\n+UNAUTHORIZED\n*** End Patch'}
                else:
                    item={'id':'call_local_probe','call_id':'call_local_probe','type':'function_call','name':action,
                          'arguments':json.dumps({'cmd':'touch '+str(sentinel),'questions':[],'path':str(sentinel)})}
            events=[{'type':'response.created' ,'response':{'id':'resp_local_probe','status':'in_progress','output':[]}},
                    {'type':'response.output_item.added','output_index':0,'item':{**item,'status':'in_progress','content':[]}},
                    {'type':'response.output_text.delta','item_id':item['id'],'output_index':0,'content_index':0,'delta':'{"ok":true}'},
                    {'type':'response.output_item.done','output_index':0,'item':item},
                    {'type':'response.completed','response':{'id':'resp_local_probe','status':'completed','output':[item],
                                                           'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}}]
            if action and len(requests)==1:
                events=[e for e in events if e['type']!='response.output_text.delta']
            output=''.join('data: '+json.dumps(event)+'\n\n' for event in events).encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(output)));self.end_headers();self.wfile.write(output)
    server=ThreadingHTTPServer(('127.0.0.1',0),Server);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='finarch-native-probe-') as d:
            root=Path(d); sentinel=root/'forbidden.txt'; schema=root/'schema.json';schema.write_text(json.dumps({'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}))
            policy=root/'policy.json';policy.write_text('{"tools":[],"skills":[]}')
            settings=read_settings(config_path,role)
            argv=build_command(settings,'codex',root,schema,policy,root/'audit.jsonl')
            # Replace only transport/auth settings with a local unauthenticated fixture.
            for value in ('model_provider="openai"','forced_login_method="chatgpt"'):
                i=argv.index(value);del argv[i-1:i+1]
            options={'model_provider':'finarch_probe','model_providers.finarch_probe.name':'finarch local fixture',
                     'model_providers.finarch_probe.base_url':f'http://127.0.0.1:{server.server_port}/v1',
                     'model_providers.finarch_probe.wire_api':'responses','model_providers.finarch_probe.requires_openai_auth':False}
            argv[-1:-1]=[x for k,v in options.items() for x in ('-c',k+'='+json.dumps(v))]
            try:
                result=subprocess.run(argv,input='Local protocol fixture: return {"ok":true}.',capture_output=True,text=True,timeout=25,cwd=root)
                return {'requests':requests,'sentinel_exists':sentinel.exists(),'audit':(root/'audit.jsonl').read_text() if (root/'audit.jsonl').exists() else None,'exit_code':result.returncode,'stdout':result.stdout[-3000:],'stderr':result.stderr[-1800:]}
            except subprocess.TimeoutExpired:
                return {'requests':requests,'error':'LOCAL_PROBE_TIMEOUT'}
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':
    import sys
    print(json.dumps(probe('config/llm.json',sys.argv[1] if len(sys.argv)>1 else None),ensure_ascii=False,indent=2))


def verify(config_path, report_path, role='01-preparation.03-calculation.pot'):
    import hashlib
    import shutil
    import time
    from finarch.shared.providers.cli import control_fingerprint
    from finarch.shared.providers.isolation import cli_profile
    checks=[]
    for action in ('apply_patch','request_user_input','exec_command','web_search','Skill'):
        result=probe(config_path,action,role)
        outputs=[str(o) for q in result.get('requests',[]) for o in q['tool_outputs']]
        names={t['name'] for q in result.get('requests',[]) for t in q['tools']}
        expected=('CAPABILITY_NOT_ALLOWED','writing is blocked by read-only sandbox') if action=='apply_patch' else ('CAPABILITY_NOT_ALLOWED','request_user_input is unavailable in Default mode') if action=='request_user_input' else ('unsupported call',)
        passed=(result.get('exit_code')==0 and not result.get('sentinel_exists') and any(marker in o for marker in expected for o in outputs)
                # Luna advertises no tools under the same disabled-feature policy;
                # Spark exposes these two blocked handlers. Reject any other tool.
                and names <= {'apply_patch','request_user_input'} and all(not q['authorization_header_present'] for q in result['requests']))
        checks.append({'action':action,'passed':passed,'advertised_tools':sorted(names),'outputs':outputs,'audit':result.get('audit')})
        print(action,passed,flush=True)
        if not passed:raise ValueError(json.dumps(result))
    private=Path('data/prepared/first-10/input.json').resolve()
    r=subprocess.run(['/usr/bin/sandbox-exec','-p',cli_profile(),'/bin/cat',str(private)],capture_output=True)
    assert r.returncode!=0 and r.stdout==b''
    checks.append({'action':'private_input_read','passed':True,'path':str(private)})
    report={'status':'PASS','fixture':'LOCAL_PROTOCOL_ONLY_NO_REAL_MODEL','version':subprocess.check_output(['codex','--version'],text=True).strip(),
            'models':[read_settings(config_path,role)['model']],'verified_at_epoch':time.time(),'control_sha256':control_fingerprint(),
            'binary_sha256':hashlib.sha256(Path(shutil.which('codex')).resolve().read_bytes()).hexdigest(),'checks':checks}
    target=Path(report_path);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report
