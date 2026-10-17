"""Execute ordinary Python in an OS-constrained child, without passing gold."""
import json
import re
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
from finarch.shared.providers.isolation import python_profile, PYTHON_BINARY
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
from finarch.dataset.shared.calculation.number_normalization import prepare_numeric_values, normalize_number, load_rules


@traced()
def validate_facts(program, rules=None):
    if rules is None:rules=load_rules()[0]
    facts=program['facts']
    for name,fact in facts.items():
        field = 'question' if fact.get('origin') == 'QUESTION' else 'context'
        context = program.get(field)
        if not isinstance(context, str): raise ValueError('FACT_SOURCE_MISSING:'+field)
        start,end=fact['span']
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(context):
            raise ValueError('INVALID_FACT_SPAN:'+name)
        if context[start:end]!=fact['text']:raise ValueError('FACT_TEXT_MISMATCH:'+name)
        text=fact['text'].strip().replace('−','-')
        text=re.sub(r'^[\$£€¥]\s*','',text).rstrip('%').strip()
        text,_=normalize_number(text,rules)
        # Parentheses are preserved, never automatically interpreted as negative.
        if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)',text):
            raise ValueError('FACT_NUMERIC_TOKEN_REQUIRED:'+name)
        if Decimal(text)!=Decimal(fact['value']):raise ValueError('FACT_VALUE_MISMATCH:'+name)
    return facts


@traced()
def execute(program, *, save=None):
    # [NN03] docs/02-architecture.md#NN03 The application of the rules before the execution of the document and the counter-instruction in order.
    program,normalization,rules=prepare_numeric_values(program)
    if save:save('number-normalization.json',normalization)
    if normalization['status']!='PASS':
        return StepResult('FAIL','NUMBER_NORMALIZATION_FAILED',{'normalization':normalization})
    validate_facts(program,rules)
    from finarch.dataset.shared.calculation.external_evidence import resolve
    evidence_records=resolve(program)
    worker=Path(__file__).with_name('worker.py').resolve()
    with tempfile.TemporaryDirectory(prefix='finarch-python-') as directory:
        work=Path(directory).resolve();input_path=work/'program.json';out=work/'stdout.txt';err=work/'stderr.txt'
        # Deliberately omit context, question, gold and provider material.
        input_path.write_text(json.dumps({'code':program['code'],'facts':program['facts'],'external_evidence':evidence_records}))
        argv=['/usr/bin/sandbox-exec','-p',python_profile(input_path,worker,out,err),str(PYTHON_BINARY.resolve()),'-I','-S',str(worker),str(input_path)]
        with out.open('wb') as output,err.open('wb') as errors:
            process=subprocess.Popen(argv,stdout=output,stderr=errors,cwd=work,
                                     env={"PATH":"/usr/bin:/bin","LANG":"en_US.UTF-8"})
            started=time.monotonic();stopped=None
            try:
                while process.poll() is None:
                    if time.monotonic()-started>6:
                        stopped="PYTHON_TIMEOUT";break
                    memory=subprocess.run(['/bin/ps','-o','rss=','-p',str(process.pid)],capture_output=True,text=True,timeout=2)
                    if memory.stdout.strip().isdigit() and int(memory.stdout.strip())>262144:
                        stopped="PYTHON_MEMORY_LIMIT";break
                    time.sleep(0.02)
            finally:
                if process.poll() is None:process.kill()
                process.wait()
            if stopped:
                return StepResult('FAIL',stopped,{'stdout':out.read_text(errors='replace'),'stderr':err.read_text(errors='replace')})
        stdout,stderr=out.read_text(errors='replace'),err.read_text(errors='replace')
        try:result=json.loads(stdout)
        except ValueError:return StepResult('FAIL','PYTHON_PROCESS_FAILED',{'stdout':stdout,'stderr':stderr,'exit_code':process.returncode})
        if process.returncode or result.get('status')!='PASS':
            return StepResult('FAIL',result.get('reason','PYTHON_PROCESS_FAILED'),{**result,'stderr':stderr})
        if not result['used_facts'] and program['facts']:
            return StepResult('FAIL','ANSWER_NOT_USING_FACTS',result)
        if set(result['used_facts'])!=set(program['facts']):
            return StepResult('FAIL','UNUSED_FACTS',result)
        return StepResult('PASS','Python executed; numeric spans verified, semantic review separate.',
                          {'exact_value':result['value'],'trace':result['variables'],'used_facts':result['used_facts'],
                           'engine':'isolated-python-v1','stdout':stdout,'stderr':stderr})
