"""Name inline numeric constants without changing their values or operations."""
import ast
import copy
import hashlib
traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced


def review(code):
    tree=ast.parse(code); steps=[]; unnamed=[]; nested=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Assign):continue
        variable=ast.unparse(node.targets[0]); expression=node.value
        count=sum(isinstance(n,(ast.BinOp,ast.UnaryOp,ast.Call,ast.Compare,ast.BoolOp)) for n in ast.walk(expression))
        if count>1:nested.append(node.lineno)
        if not isinstance(expression,ast.Constant):
            for n in ast.walk(expression):
                if isinstance(n,ast.Constant) and type(n.value) in (int,float):
                    unnamed.append({'line':n.lineno,'variable':variable,'literal':ast.unparse(n)})
        steps.append({'line':node.lineno,'variable':variable,'expression':ast.unparse(expression),'operation_count':count})
    return {'status':'PASS' if not unnamed and not nested else 'FAIL','syntax':'PASS',
            'code_sha256':hashlib.sha256(code.encode()).hexdigest(),'steps':sorted(steps,key=lambda x:x['line']),
            'unnamed_numeric_constants':unnamed,'nested_operation_lines':nested,
            'scope':'Variable and calculation-step structure check; not a semantic correctness verdict.'}


def normalize_annotations(code):
    """Remove typing-only syntax while preserving assignment values and order."""
    tree=ast.parse(code);changes=[];body=[]
    expression_names=set()
    for stmt in tree.body:
        value=getattr(stmt,'value',None)
        if value is not None:expression_names.update(n.id for n in ast.walk(value) if isinstance(n,ast.Name))
    for stmt in tree.body:
        if isinstance(stmt,ast.ImportFrom) and stmt.module=='typing' and all((alias.asname or alias.name) not in expression_names for alias in stmt.names):
            changes.append({'line':stmt.lineno,'change':'remove_annotation_only_import'});continue
        if isinstance(stmt,ast.AnnAssign) and isinstance(stmt.target,ast.Name) and stmt.value is not None:
            changes.append({'line':stmt.lineno,'change':'remove_assignment_annotation'})
            stmt=ast.copy_location(ast.Assign(targets=[stmt.target],value=stmt.value),stmt)
        body.append(stmt)
    if not changes:return code,[]
    tree.body=body;ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n',changes


@traced('python')
def name_constants(program):
    # [PS01] docs/02-architecture.md#PS01 — 생성 원본은 보존하고 수식의 숫자만 고유 변수로 꺼낸다.
    result=copy.deepcopy(program);original_code=program['code'];code,annotation_changes=normalize_annotations(original_code);tree=ast.parse(code)
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    lines=code.splitlines(keepends=True); changes=[]
    # Only plain, single-line top-level assignments can be rewritten mechanically.
    for stmt in reversed(tree.body):
        if not isinstance(stmt,ast.Assign) or stmt.lineno!=stmt.end_lineno or not isinstance(stmt.targets[0],ast.Name):continue
        if isinstance(stmt.value,ast.Constant):continue
        literals=[n for n in ast.walk(stmt.value) if isinstance(n,ast.Constant) and type(n.value) in (int,float)]
        if not literals:continue
        replacements=[];definitions=[]
        for index,n in enumerate(sorted(literals,key=lambda x:x.col_offset),1):
            name=f'{stmt.targets[0].id}_constant_{index}'
            while name in names:name+='_'
            names.add(name);literal=ast.get_source_segment(code,n)
            definitions.append(f'{name} = {literal}\n')
            replacements.append((n.col_offset,n.end_col_offset,name))
            changes.append({'line':stmt.lineno,'variable':name,'literal':literal,'target':stmt.targets[0].id})
        line=lines[stmt.lineno-1].encode()
        for start,end,name in sorted(replacements,reverse=True):line=line[:start]+name.encode()+line[end:]
        lines[stmt.lineno-1]='# Extract expression constants into named variables\n'+''.join(definitions)+line.decode()
    result['code']=''.join(lines)
    # Rebind source lines after mechanical rewrites; keep the model original intact.
    assigned={}
    for node in ast.walk(ast.parse(result['code'])):
        if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Store):
            assigned.setdefault(node.id,set()).add(node.lineno)
    provenance_changes=[]
    for usage in result.get('source_usage',[]):
        old=list(usage['code_lines'])
        new=sorted({line for name in usage['output_variables'] for line in assigned.get(name,())})
        if not new:raise ValueError('PROVENANCE_VARIABLE_LOST_DURING_NORMALIZATION')
        usage['code_lines']=new
        if old!=new:provenance_changes.append({'id':usage['id'],'before':old,'after':new})
    return result,{'mode':'LOCAL_CONSTANT_NAMING','original_code_sha256':hashlib.sha256(original_code.encode()).hexdigest(),'annotation_changes':annotation_changes,'provenance_changes':provenance_changes,
        'changes':sorted(changes,key=lambda x:x['line']),'review':review(result['code'])}
