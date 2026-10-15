"""Read-only source diffs and static source-fact/code references for the viewer."""
import ast
from difflib import SequenceMatcher
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from finarch.dataset.shared.calculation.standalone import render_standalone
from finarch.shared.reference import Reference, compare

RAW_ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()/'data'/'raw'


@lru_cache(maxsize=8)
def source_file(path,modified,size,expected_hash):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_hash:raise ValueError('원천 파일 해시 불일치')
    return json.loads(raw)


def raw_record(artifacts):
    stored=artifacts.get('00-data-preparation/raw-record.json')
    if isinstance(stored,dict):return stored.get('record',stored)
    provenance=artifacts.get('00-data-preparation/02-record-source/01-provenance.json') or artifacts.get('00-data-preparation/comparison.json')
    if not provenance:raise ValueError('원천 파일 연결 기록 없음')
    source=provenance['source'];path=Path(source['path']).resolve()
    if not path.is_relative_to(RAW_ROOT.resolve()):raise ValueError('허용된 원천 폴더 밖의 경로')
    stat=path.stat();records=source_file(str(path),stat.st_mtime_ns,stat.st_size,source['sha256'])
    return records[provenance['record_index']]


def aligned_diff(left,right):
    """VD01: align inserted/deleted lines; retain exact text including whitespace."""
    a,b=left.splitlines(),right.splitlines();rows=[]
    for kind,i,j,k,l in SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        for offset in range(max(j-i,l-k)):
            ai=i+offset if i+offset<j else None;bi=k+offset if k+offset<l else None
            rows.append({'kind':kind,'left':a[ai] if ai is not None else None,
                         'right':b[bi] if bi is not None else None,
                         'left_line':ai+1 if ai is not None else None,
                         'right_line':bi+1 if bi is not None else None})
    return rows


def raw_context(record):
    if isinstance(record.get('context'),str):return record['context']
    # TAT-QA's raw paragraph text and raw table cells; no inferred/reworded content.
    paragraphs=[p['text'] for p in record.get('paragraphs',[]) if isinstance(p,dict) and 'text' in p]
    table=record.get('table',{}).get('table',[]) if isinstance(record.get('table'),dict) else []
    return '\n'.join(paragraphs+['\t'.join(map(str,row)) for row in table])


def code_links(code,facts):
    """VC01: static fact() calls and straight-line variable references, never execution claims."""
    tree=ast.parse(code);known=set(facts);references={};variables={}
    def deps(node):
        found=set()
        for child in ast.walk(node):
            if isinstance(child,ast.Call) and isinstance(child.func,ast.Name) and child.func.id=='fact' and child.args and isinstance(child.args[0],ast.Constant) and child.args[0].value in known:
                found.add(child.args[0].value)
            if isinstance(child,ast.Name) and isinstance(child.ctx,ast.Load):found.update(variables.get(child.id,set()))
        return found
    for statement in tree.body:
        if isinstance(statement,(ast.Assign,ast.AnnAssign)):
            ids=deps(statement.value);targets=statement.targets if isinstance(statement,ast.Assign) else [statement.target]
            for target in targets:
                for child in ast.walk(target):
                    if isinstance(child,ast.Name):variables[child.id]=ids.copy()
            for line in range(statement.lineno,statement.end_lineno+1):references[line]=sorted(ids)
    # Include literal fact calls inside functions/loops without inventing their dependencies.
    for child in ast.walk(tree):
        if isinstance(child,ast.Call) and isinstance(child.func,ast.Name) and child.func.id=='fact' and child.args and isinstance(child.args[0],ast.Constant) and child.args[0].value in known:
            references.setdefault(child.lineno,[])
            references[child.lineno]=sorted(set(references[child.lineno])|{child.args[0].value})
    return references


def enrich(artifacts):
    result={};sample=artifacts.get('00-data-preparation/01-select-input/01-input.json') or {}
    try:
        original=raw_record(artifacts)
        result['source_diff']={'raw':original,'input':sample,
           'record_rows':aligned_diff(json.dumps(original,ensure_ascii=False,indent=2),json.dumps(sample,ensure_ascii=False,indent=2)),
           'context_rows':aligned_diff(raw_context(original),sample.get('context','')),
           'context_note':'TAT-QA 원문은 문단·표 셀 텍스트를 줄바꿈·탭으로 이어 표시합니다. 전체 레코드 모드에는 모든 필드가 표시됩니다.'}
    except (OSError,ValueError,KeyError,IndexError,TypeError) as error:result['source_diff']={'error':str(error)}
    program=artifacts.get('02-calculation/02-prepare-code/03-program.json')
    if isinstance(program,dict):
        try:result['code_links']=code_links(program['code'],program.get('facts',{}))
        except (SyntaxError,TypeError,KeyError):result['code_links']={}
        try:result['standalone_program']=render_standalone(program,artifacts.get('02-calculation/03-execute-python/02-number-normalization.json'))
        except (ValueError,KeyError,TypeError) as error:result['standalone_program']={'error':str(error)}
    # [VF04] Apply the reference precision only to final answers, independently per engine.
    check=artifacts.get('03-graph/03-compare-calculation/04-comparison.json')
    if isinstance(check,dict):
        try:
            reference=Reference(**{key:sample[key] for key in
                ('reference_answer','reference_answer_type','reference_precision')})
            result['final_answers']={engine:compare(check[engine],reference)
                                     for engine in ('python','graph')}
        except (KeyError,ValueError,TypeError,ZeroDivisionError) as error:
            result['final_answers']={'error':str(error)}
    return result
