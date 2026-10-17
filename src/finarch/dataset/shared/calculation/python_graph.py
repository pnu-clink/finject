"""Extract a numeric straight-line DAG from the exact saved Python AST."""
import ast
import hashlib
import math
import operator
import statistics
from collections import Counter
traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
from finarch.dataset.shared.calculation.number_normalization import prepare_numeric_values
from finarch.dataset.shared.calculation.python_runtime import validate_facts

BINARY={ast.Add:'+',ast.Sub:'-',ast.Mult:'*',ast.Div:'/',ast.Pow:'**',ast.Mod:'%',ast.FloorDiv:'//'}
COMPARISONS={ast.Lt:'<',ast.LtE:'<=',ast.Gt:'>',ast.GtE:'>=',ast.Eq:'==',ast.NotEq:'!='}
def path_guard(value, condition):
    if not condition: raise ValueError('GRAPH_CONTROL_PATH_CHANGED:RECOMPILE_FROM_SAME_CODE')
    return value


def bounded_factorial(n):
    if type(n) is not int or not 0 <= n <= 200: raise ValueError('GRAPH_FACTORIAL_LIMIT')
    return math.factorial(n)


def bounded_comb(n, k):
    if type(n) is not int or type(k) is not int or not 0 <= k <= n <= 2000: raise ValueError('GRAPH_COMB_LIMIT')
    return math.comb(n,k)


FUNCTIONS={'min':min,'max':max,'round':round,'int':int,'float':float,'abs':abs,'pow':pow,
           'math.factorial':bounded_factorial,'math.comb':bounded_comb,
           'statistics.mean':lambda *values:statistics.mean(values),
           **{'math.'+name:getattr(math,name) for name in ('pow','sqrt','log','log10','exp','fabs','ceil','floor','erf')}}
OPERATIONS={'path_guard':path_guard,'if_else':lambda condition, yes, no:yes if condition else no,'<':operator.lt,'<=':operator.le,'>':operator.gt,'>=':operator.ge,'==':operator.eq,'!=':operator.ne,
            'sum':lambda start,*values:sum(values,start),
            'and':lambda a,b:a and b,'or':lambda a,b:a or b,'not':operator.not_, '+':operator.add,'-':operator.sub,'*':operator.mul,'/':operator.truediv,
            '**':operator.pow,'%':operator.mod,'//':operator.floordiv,'neg':operator.neg,'pos':operator.pos,**FUNCTIONS}
ARITY={'path_guard':(2,2),'math.factorial':(1,1),'math.comb':(2,2),'statistics.mean':(1,512),'if_else':(3,3),**{op:(2,2) for op in COMPARISONS.values()},'and':(2,2),'or':(2,2),'not':(1,1), '+':(2,2),'-':(2,2),'*':(2,2),'/':(2,2),'**':(2,2),'%':(2,2),'//':(2,2),
       'sum':(1,513),
       'min':(2,2000),'max':(2,2000),'neg':(1,1),'pos':(1,1),'round':(1,2),'int':(1,1),'float':(1,1),'abs':(1,1),'pow':(2,3),
       'math.pow':(2,2),'math.sqrt':(1,1),'math.log':(1,2),'math.log10':(1,1),'math.exp':(1,1),
       'math.fabs':(1,1),'math.ceil':(1,1),'math.floor':(1,1),'math.erf':(1,1)}


def checked_value(value):
    if type(value) not in (int,float,bool) or (type(value) is float and not math.isfinite(value)):raise ValueError('NONFINITE_GRAPH_VALUE')
    if type(value) is int and value.bit_length()>4096:raise ValueError('GRAPH_VALUE_TOO_LARGE')
    return value


@traced('python')
def evaluate(graph):
    # [DG02] docs/02-architecture.md#DG02 It checks the connection-circuits of the string storage graph and calculates them as a Python numerical type.
    nodes=graph['nodes'];by_id={n['id']:n for n in nodes}
    if len(nodes)!=len(by_id):raise ValueError('DUPLICATE_NODE_ID')
    expected=Counter((p,n['id'],i) for n in nodes for i,p in enumerate(n['inputs']))
    edges=Counter((e['from'],e['to'],e['input_index']) for e in graph['edges'])
    if expected!=edges:raise ValueError('GRAPH_EDGE_MISMATCH')
    # Validate even branches that Python short-circuiting does not evaluate.
    checked=set();checking=set()
    def check(key):
        if key in checking:raise ValueError('GRAPH_CYCLE')
        if key in checked:return
        if key not in by_id:raise ValueError('MISSING_INPUT_NODE')
        node=by_id[key]
        if node['kind']=='operation':
            op=node.get('operator')
            if op=='evidence':
                entry=graph.get('external_evidence',{}).get(node.get('evidence_id'))
                if not entry:raise ValueError('MISSING_EXTERNAL_EVIDENCE')
                lo=hi=len(entry['selectors'])
            else:
                if op not in OPERATIONS:raise ValueError('UNSUPPORTED_GRAPH_OPERATOR:'+str(op))
                lo,hi=ARITY[op]
            if not lo<=len(node['inputs'])<=hi:raise ValueError('INVALID_OPERATOR_ARITY')
        if node['kind'] in ('constant','fact') and node.get('value_type')=='bool' and node.get('value') not in ('True','False'):
            raise ValueError('INVALID_BOOLEAN_VALUE')
        checking.add(key)
        for parent in by_id[key]['inputs']:check(parent)
        checking.remove(key);checked.add(key)
    for key in by_id:check(key)
    values={};visiting=set()
    def visit(key):
        if key in values:return values[key]
        if key in visiting:raise ValueError('GRAPH_CYCLE')
        if key not in by_id:raise ValueError('MISSING_INPUT_NODE')
        visiting.add(key);n=by_id[key]
        if n['kind']=='operation' and n.get('operator')=='if_else':
            condition=visit(n['inputs'][0])
            value=visit(n['inputs'][1] if bool(condition) else n['inputs'][2])
            values[key]=checked_value(value);visiting.remove(key);return value
        lazy=n.get('operator') in ('and','or') and n['kind']=='operation'
        if lazy:
            if len(n['inputs'])!=2:raise ValueError('INVALID_OPERATOR_ARITY')
            first=visit(n['inputs'][0]);op=n['operator']
            value=visit(n['inputs'][1]) if (bool(first) if op=='and' else not bool(first)) else first
            values[key]=checked_value(value);visiting.remove(key);return value
        args=[visit(p) for p in n['inputs']]
        if n['kind'] in ('fact','constant'):
            if args:raise ValueError('LEAF_WITH_INPUTS')
            if n['value_type'] not in ('int','float','bool'):raise ValueError('INVALID_VALUE_TYPE')
            value=(n['value']=='True') if n['value_type']=='bool' else int(n['value']) if n['value_type']=='int' else float(n['value'])
        elif n['kind']=='variable':
            if len(args)!=1:raise ValueError('INVALID_VARIABLE_ARITY')
            value=args[0]
        elif n['kind']=='operation':
            op=n['operator']
            if op=='evidence':
                from finarch.dataset.shared.calculation.external_evidence import lookup
                value=lookup(graph['external_evidence'][n['evidence_id']],args)
                values[key]=checked_value(value);visiting.remove(key);return value
            if op not in OPERATIONS:raise ValueError('UNSUPPORTED_GRAPH_OPERATOR:'+op)
            lo,hi=ARITY[op]
            if not lo<=len(args)<=hi:raise ValueError('INVALID_OPERATOR_ARITY')
            if op in ('**','pow') and abs(args[1])>10000:raise ValueError('GRAPH_POWER_LIMIT')
            value=OPERATIONS[op](*args)
        else:raise ValueError('UNKNOWN_NODE_KIND')
        values[key]=checked_value(value);visiting.remove(key);return value
    # Validate the recorded control decisions before evaluating the selected
    # branch under changed inputs (which might otherwise divide by zero).
    for guard in graph.get('control_flow',{}).get('guards',[]):
        if not visit(guard):raise ValueError('GRAPH_CONTROL_PATH_CHANGED:RECOMPILE_FROM_SAME_CODE')
    for n in nodes:
        if n['kind']=='variable':visit(n['id'])
    visit(graph['output'])
    if graph['output'] not in values:raise ValueError('MISSING_OUTPUT')
    reachable=set()
    def ancestors(key):
        if key in reachable:return
        reachable.add(key)
        for p in by_id[key]['inputs']:ancestors(p)
    ancestors(graph['output'])
    if any(n['kind']=='fact' and n['id'] not in reachable for n in nodes):raise ValueError('FACT_NOT_CONNECTED_TO_ANSWER')
    for name,key in graph['variables'].items():
        if key not in by_id or by_id[key].get('variable')!=name:raise ValueError('INVALID_VARIABLE_MAP')
    return values[graph['output']],values


@traced('python')
def compile_structure(program, *, missing_facts=()):
    # [DG01] docs/02-architecture.md#DG01 Separates base, sum, mix, and variable from the same code AST without calling a new LLM.
    prepared,audit,rules=prepare_numeric_values(program)
    if audit['status']!='PASS':raise ValueError('NUMBER_NORMALIZATION_FAILED')
    facts=validate_facts(prepared,rules);code=program['code'];tree=ast.parse(code)
    from finarch.dataset.shared.calculation.external_evidence import resolve
    evidence_records=resolve(program)
    missing=set(missing_facts)
    if any(not isinstance(key,str) or not key for key in missing) or missing & set(facts):
        raise ValueError('INVALID_MISSING_FACTS')
    if len(list(ast.walk(tree)))>2000:raise ValueError('GRAPH_PROGRAM_TOO_COMPLEX')
    control_nodes=(ast.For,ast.While,ast.If,ast.FunctionDef,ast.List,ast.Tuple,ast.Dict,
                   ast.ListComp,ast.DictComp,ast.SetComp,ast.GeneratorExp,ast.Subscript,ast.AugAssign)
    assigned=[n.targets[0].id for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)]
    extended=any(isinstance(n,control_nodes) for n in ast.walk(tree)) or len(set(assigned))!=len(assigned) or any(
        isinstance(n,ast.Import) and any(a.name!='math' for a in n.names) or isinstance(n,ast.ImportFrom) and n.module!='math' for n in ast.walk(tree))
    if extended:
        if missing:raise ValueError('GRAPH_CONTROL_FLOW_MISSING_FACTS:NOT_EVALUATED')
        from finarch.dataset.shared.calculation.graph_control import compile_control
        return compile_control(program,facts,evidence_records),audit
    nodes=[];variables={};aliases={k:k for k in FUNCTIONS if '.' not in k};used=set()
    def add(kind,label,inputs=(),**fields):
        key=f'n{len(nodes):04d}';nodes.append({'id':key,'kind':kind,'label':label,'inputs':list(inputs),**fields});return key
    def expression(n):
        location={'code_line':n.lineno,'code_column':n.col_offset,'expression':ast.get_source_segment(code,n)}
        if isinstance(n,ast.IfExp):
            return add('operation','if / else',[expression(n.test),expression(n.body),expression(n.orelse)],operator='if_else',**location)
        if isinstance(n,ast.Name):
            if n.id not in variables:raise ValueError('UNBOUND_GRAPH_VARIABLE:'+n.id)
            return variables[n.id]
        if isinstance(n,ast.Constant) and type(n.value) in (int,float,bool):
            return add('constant',str(n.value),value=str(n.value),value_type=type(n.value).__name__,**location)
        if isinstance(n,ast.Compare) and all(type(op) in COMPARISONS for op in n.ops):
            left=expression(n.left);combined=None
            for op,right_expression in zip(n.ops,n.comparators):
                right=expression(right_expression);symbol=COMPARISONS[type(op)]
                part=add('operation',symbol,[left,right],operator=symbol,**location)
                combined=part if combined is None else add('operation','and',[combined,part],operator='and',**location)
                left=right
            return combined
        if isinstance(n,ast.BoolOp):
            op='and' if isinstance(n.op,ast.And) else 'or'
            combined=expression(n.values[0])
            for item in n.values[1:]:combined=add('operation',op,[combined,expression(item)],operator=op,**location)
            return combined
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.Not):
            return add('operation','not',[expression(n.operand)],operator='not',**location)
        if isinstance(n,ast.BinOp) and type(n.op) in BINARY:
            op=BINARY[type(n.op)];return add('operation',op,[expression(n.left),expression(n.right)],operator=op,**location)
        if isinstance(n,ast.UnaryOp) and type(n.op) in (ast.UAdd,ast.USub):
            op='pos' if isinstance(n.op,ast.UAdd) else 'neg';return add('operation',op,[expression(n.operand)],operator=op,**location)
        if isinstance(n,ast.Call) and not n.keywords:
            if isinstance(n.func,ast.Name) and n.func.id=='evidence':
                if not n.args or not isinstance(n.args[0],ast.Constant) or n.args[0].value not in evidence_records:
                    raise ValueError('INVALID_EVIDENCE_CALL')
                key=n.args[0].value
                return add('operation','external table lookup',[expression(x) for x in n.args[1:]],
                           operator='evidence',evidence_id=key,**location)
            if isinstance(n.func,ast.Name) and n.func.id=='fact':
                if len(n.args)!=1 or not isinstance(n.args[0],ast.Constant) or not isinstance(n.args[0].value,str) or n.args[0].value not in set(facts)|missing:raise ValueError('INVALID_FACT_CALL')
                key=n.args[0].value;used.add(key)
                if key in missing:
                    return add('fact',key,fact_id=key,availability='MISSING',**location)
                f=facts[key]
                return add('fact',key,fact_id=key,value=str(float(f['value'])),value_type='float',span=f['span'],text=f['text'],unit=f.get('unit'),**location)
            name=aliases.get(ast.unparse(n.func))
            if name in FUNCTIONS:return add('operation',name,[expression(x) for x in n.args],operator=name,**location)
        raise ValueError('GRAPH_UNSUPPORTED_SYNTAX:'+type(n).__name__+':line'+str(n.lineno))
    for stmt in tree.body:
        if isinstance(stmt,ast.Import):
            for item in stmt.names:
                if item.name!='math':raise ValueError('GRAPH_UNSUPPORTED_IMPORT:'+item.name)
                prefix=item.asname or item.name
                for name in FUNCTIONS:
                    if name.startswith('math.'):aliases[prefix+name[4:]]=name
            continue
        if isinstance(stmt,ast.ImportFrom) and stmt.module=='math' and stmt.level==0:
            for item in stmt.names:
                target='math.'+item.name
                if target not in FUNCTIONS:raise ValueError('GRAPH_UNSUPPORTED_IMPORT:'+item.name)
                aliases[item.asname or item.name]=target
            continue
        if not isinstance(stmt,ast.Assign) or len(stmt.targets)!=1 or not isinstance(stmt.targets[0],ast.Name):raise ValueError('GRAPH_REQUIRES_NAMED_STRAIGHT_LINE_ASSIGNMENTS')
        name=stmt.targets[0].id
        if name in variables or name in aliases or name in ('fact','evidence'):raise ValueError('GRAPH_REASSIGNMENT:'+name)
        parent=expression(stmt.value)
        variables[name]=add('variable',name,[parent],variable=name,code_line=stmt.lineno,expression=ast.get_source_segment(code,stmt.value))
    if 'answer' not in variables or used!=set(facts)|missing:raise ValueError('INCOMPLETE_GRAPH_FACTS_OR_ANSWER')
    graph={'format':'finarch-python-dag-v1','code_sha256':hashlib.sha256(code.encode()).hexdigest(),
           'numeric_semantics':'Python int/float/bool; short-circuit logical operations; intermediate float precision',
           'nodes':nodes,'variables':variables,'output':variables['answer'],
           'edges':[{'from':parent,'to':n['id'],'input_index':i} for n in nodes for i,parent in enumerate(n['inputs'])]}
    if evidence_records:graph['external_evidence']=evidence_records
    if missing:
        graph['format']='finarch-python-partial-dag-v1'
        graph['missing_facts']=sorted(missing)
    return graph,audit


@traced('python')
def compile_graph(program):
    # Numeric execution remains a separate step; EA uses the same AST builder.
    graph,audit=compile_structure(program)
    value,values=evaluate(graph)
    for n in graph['nodes']:n['computed']=str(values[n['id']]) if n['id'] in values else 'NOT_EVALUATED'
    return graph,value,audit


def compile_handler(payload):
    StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
    from finarch.dataset.shared.calculation.arithmetic import mermaid
    graph,value,audit=compile_graph(payload['program'])
    return StepResult('PASS','Graph extracted from the same Python code',{'dag':graph,'exact_value':str(value),
        'variables':[n['id'] for n in graph['nodes'] if n['kind']!='constant'],
        'mermaid':mermaid(graph),'normalization':audit})


@traced('python')
def load_graph(case_dir):
    """Stage 11 handoff: validate the immutable graph and its matching POT code."""
    import json
    from pathlib import Path
    from finarch.dataset.shared.calculation.validation_gate import load_eligible
    case=Path(case_dir);pot=load_eligible(case)
    check=json.loads((case/'03-graph/04-save-graph/03-disposition.json').read_text())
    raw=(case/'03-graph/04-save-graph/01-graph.json').read_bytes()
    if check.get('status')!='PASS' or check.get('allow_next_stage') is not True:raise ValueError('GRAPH_NOT_ELIGIBLE')
    if hashlib.sha256(raw).hexdigest()!=check['graph_sha256']:raise ValueError('ORIGINAL_GRAPH_CHANGED')
    graph=json.loads(raw)
    code_hash=hashlib.sha256(pot['program']['code'].encode()).hexdigest()
    if graph.get('code_sha256')!=code_hash or check['code_sha256']!=code_hash:raise ValueError('GRAPH_CODE_CHANGED')
    value,_=evaluate(graph)
    execution_path='02-calculation/03-execute-python/03-result.json'
    if (case/'02-calculation/latest-execution.json').exists():execution_path=json.loads((case/'02-calculation/latest-execution.json').read_text())['path']
    execution=json.loads((case/execution_path).read_text())['data']
    if str(value)!=execution['exact_value']:raise ValueError('PYTHON_GRAPH_MISMATCH')
    return graph
