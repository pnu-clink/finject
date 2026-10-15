"""Isolated child: execute a saved Python program; read no reference answer."""
import contextlib
import io
import json
import math
import resource
import sys
from decimal import Decimal
from fractions import Fraction


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    payload=json.loads(open(sys.argv[1],encoding='utf-8').read())
    used=[]
    def fact(name):
        if name not in payload['facts']:raise ValueError('UNKNOWN_FACT')
        used.append(name)
        return float(payload['facts'][name]['value'])
    def evidence(name,*selectors):
        entry=payload.get('external_evidence',{}).get(name)
        if not entry:raise ValueError('UNKNOWN_EXTERNAL_EVIDENCE')
        if len(selectors)!=len(entry['selectors']):raise ValueError('EVIDENCE_SELECTOR_ARITY')
        rows=[r for r in entry['rows'] if r['keys']==list(selectors)]
        if len(rows)!=1:raise ValueError('EVIDENCE_SELECTION_NOT_SUPPORTED')
        return float(rows[0]['value'])
    namespace={'__name__':'__pot__','fact':fact,'evidence':evidence}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(payload['code'],'generated-program.py','exec'),namespace,namespace)
        value=namespace.get('answer')
        if isinstance(value,bool) or not isinstance(value,(int,float,Decimal,Fraction)):
            raise ValueError('NUMERIC_ANSWER_REQUIRED')
        if not math.isfinite(float(value)):raise ValueError('FINITE_ANSWER_REQUIRED')
        scalars={k:str(v) for k,v in namespace.items() if not k.startswith('_') and isinstance(v,(int,float,Decimal,Fraction))}
        print(json.dumps({'status':'PASS','value':str(value),'variables':scalars,'used_facts':sorted(set(used))},allow_nan=False))
    except Exception as error:
        print(json.dumps({'status':'FAIL','reason':type(error).__name__+': '+str(error),'used_facts':sorted(set(used))}))
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
