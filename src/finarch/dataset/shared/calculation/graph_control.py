"""Bounded AST interpretation recording numeric dependencies, never executing source.

The DAG represents one concrete control path. Guard nodes reject changed inputs
which would choose another branch, iteration count, index or ordering.
"""
import ast
import hashlib
import math
from collections import ChainMap
from dataclasses import dataclass


@dataclass
class Number:
    key: str
    value: object


@dataclass
class Function:
    node: object
    closure: object


class Return(Exception):
    def __init__(self, value): self.value = value


class Break(Exception): pass
class Continue(Exception): pass


class Builder:
    MAX_NODES = 4000
    MAX_ITERATIONS = 512
    MAX_STEPS = 10000
    MAX_CALL_DEPTH = 16

    def __init__(self, program, facts, evidence):
        from finarch.dataset.shared.calculation.python_graph import FUNCTIONS, OPERATIONS
        self.program, self.facts, self.evidence = program, facts, evidence
        self.nodes, self.guards, self.events = [], [], []
        self.constants = {}
        self.used, self.active = set(), []
        self.env = ChainMap({})
        self.aliases = {name: name for name in FUNCTIONS if '.' not in name}
        self.operations = OPERATIONS
        self.steps = self.iterations = 0
        self.scope = []

    def fail(self, node, reason):
        raise ValueError('GRAPH_UNSUPPORTED_SYNTAX:' + reason + ':line' + str(getattr(node, 'lineno', 0)))

    def add(self, node, kind, label, computed, inputs=(), **extra):
        from finarch.dataset.shared.calculation.python_graph import checked_value
        checked_value(computed)
        if len(self.nodes) >= self.MAX_NODES: raise ValueError('GRAPH_EXPANSION_NODE_LIMIT')
        key = 'n' + str(len(self.nodes)).zfill(4)
        self.nodes.append(dict(id=key, kind=kind, label=label, inputs=[x.key for x in inputs],
            code_line=getattr(node, 'lineno', 0), code_column=getattr(node, 'col_offset', 0),
            expression=ast.get_source_segment(self.program['code'], node),
            expansion_scope=list(self.scope), **extra))
        return Number(key, computed)

    def constant(self, node, value, *, internal=False):
        if type(value) not in (bool, int, float): return value
        # Preserve types and signed floating zero; never coalesce source facts.
        key = (type(value).__name__, value.hex() if type(value) is float else str(value))
        location = {'line': getattr(node, 'lineno', 0), 'column': getattr(node, 'col_offset', 0),
                    'expression': ast.get_source_segment(self.program['code'], node), 'scope': list(self.scope)}
        if key not in self.constants:
            result = self.add(node, 'constant', str(value), value, value=str(value),
                              value_type=type(value).__name__, source_locations=[], control_internal=internal)
            self.constants[key] = (result, self.nodes[-1])
        result, record = self.constants[key]
        if not internal:
            if record.get('control_internal'):
                record.update(code_line=location['line'], code_column=location['column'],
                              expression=location['expression'], expansion_scope=location['scope'])
            record['control_internal'] = False
            if location not in record['source_locations']: record['source_locations'].append(location)
        return result

    def op(self, node, name, args):
        if not all(isinstance(x, Number) for x in args): self.fail(node, 'NON_NUMERIC_OPERAND')
        if name in ('pow', '**') and abs(args[1].value) > 10000: raise ValueError('GRAPH_POWER_LIMIT')
        value = self.operations[name](*(x.value for x in args))
        return self.add(node, 'operation', name, value, args, operator=name)

    def mark_internal(self, start):
        for item in self.nodes[start:]: item['control_internal'] = True

    def pin(self, node, value, reason, **details):
        if not isinstance(value, Number): self.fail(node, 'DYNAMIC_NON_NUMERIC_CONTROL')
        start = len(self.nodes)
        equal = self.op(node, '==', [value, self.constant(node, value.value, internal=True)])
        self.mark_internal(start)
        self.guards.append(equal)
        self.events.append({'line': node.lineno, 'kind': reason, 'observed': value.value,
                            'node': value.key, 'guard_node': equal.key,
                            'scope': list(self.scope), **details})
        return value.value

    def condition(self, node, value, **details):
        # Python truthiness; guard only truth value, not every numeric change.
        if not isinstance(value, Number): self.fail(node, 'CONTAINER_TRUTHINESS')
        result = value
        if type(value.value) is not bool:
            start = len(self.nodes)
            result = self.op(node, 'not', [self.op(node, 'not', [value])])
            self.mark_internal(start)
        return self.pin(node, result, 'condition', condition_node=value.key,
                        condition_expression=ast.get_source_segment(self.program['code'], node), **details)

    def control_links(self):
        # Presentation metadata only: never add control decisions to numeric inputs.
        links = []
        def calculation(node):
            return not node.get('control_internal') and node['kind'] in ('operation', 'variable')
        for index, event in enumerate(self.events):
            span = event.pop('_body_span', None)
            if span is None: continue
            start, end = span
            body = [node for node in self.nodes[start:end] if calculation(node)]
            body_ids = {node['id'] for node in body}
            targets = [node for node in body if not body_ids.intersection(node['inputs'])]
            target_kind = 'body'
            if not targets:
                targets = [next((node for node in self.nodes[end:] if calculation(node)), None)]
                target_kind = 'continuation'
            for target in targets:
                links.append({'from': event['condition_node'], 'to': target['id'] if target else None,
                              'event_index': index, 'target_kind': target_kind if target else 'end'})
        return links

    def sequence(self, node, value):
        if not isinstance(value, (list, tuple)) or len(value) > self.MAX_ITERATIONS:
            self.fail(node, 'BOUNDED_SEQUENCE_REQUIRED')
        return value

    def key(self, node, value):
        if isinstance(value, Number): return self.pin(node, value, 'index_or_key')
        if isinstance(value, tuple): return tuple(self.key(node, x) for x in value)
        if isinstance(value, str): return value
        self.fail(node, 'UNSUPPORTED_KEY')

    def bind(self, node, value, env):
        if isinstance(node, (ast.Tuple, ast.List)):
            values = self.sequence(node, value)
            if len(values) != len(node.elts): self.fail(node, 'UNPACKING_ARITY')
            for target, item in zip(node.elts, values): self.bind(target, item, env)
        elif isinstance(node, ast.Name):
            if node.id in ('fact', 'evidence') or node.id.startswith('__'): self.fail(node, 'RESERVED_NAME')
            if isinstance(value, Number):
                value = self.add(node, 'variable', node.id + (' · ' + '/'.join(self.scope) if self.scope else ''),
                                 value.value, [value], variable=node.id)
            env[node.id] = value
        else:
            # Mutating shared containers is deliberately outside this version.
            self.fail(node, 'MUTABLE_ASSIGNMENT')

    def expr(self, node, env):
        from finarch.dataset.shared.calculation.python_graph import BINARY, COMPARISONS
        self.steps += 1
        if self.steps > self.MAX_STEPS: raise ValueError('GRAPH_EXPANSION_STEP_LIMIT')
        if isinstance(node, ast.Constant): return self.constant(node, node.value)
        if isinstance(node, ast.Name):
            if node.id not in env: self.fail(node, 'UNBOUND:' + node.id)
            return env[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self.expr(x, env) for x in node.elts] if isinstance(node, ast.List) else tuple(self.expr(x, env) for x in node.elts)
        if isinstance(node, ast.Dict):
            return {self.key(node, self.expr(k, env)): self.expr(v, env) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.Subscript):
            container = self.expr(node.value, env)
            if isinstance(node.slice, ast.Slice): self.fail(node, 'SLICE')
            index = self.key(node, self.expr(node.slice, env))
            if not isinstance(container, (list, tuple, dict)): self.fail(node, 'INDEXED_CONTAINER')
            return container[index]
        if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            return self.op(node, BINARY[type(node.op)], [self.expr(node.left, env), self.expr(node.right, env)])
        if isinstance(node, ast.UnaryOp):
            name = {ast.UAdd:'pos', ast.USub:'neg', ast.Not:'not'}.get(type(node.op))
            if name: return self.op(node, name, [self.expr(node.operand, env)])
        if isinstance(node, ast.Compare):
            left = self.expr(node.left, env)
            for i, (symbol, right_node) in enumerate(zip(node.ops, node.comparators)):
                if type(symbol) not in COMPARISONS: self.fail(node, 'COMPARISON')
                right = self.expr(right_node, env)
                result = self.op(node, COMPARISONS[type(symbol)], [left, right])
                if i < len(node.ops)-1 and not self.condition(node, result): return result
                left = right
            return result
        if isinstance(node, ast.BoolOp):
            value = self.expr(node.values[0], env)
            for following in node.values[1:]:
                truth = self.condition(node, value)
                if truth != isinstance(node.op, ast.And): return value
                value = self.expr(following, env)
            return value
        if isinstance(node, ast.IfExp):
            yes = self.condition(node, self.expr(node.test, env))
            return self.expr(node.body if yes else node.orelse, env)
        if isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.DictComp)):
            result = {} if isinstance(node, ast.DictComp) else []
            local = env.new_child()
            def collect(index):
                if index == len(node.generators):
                    if isinstance(result, dict): result[self.key(node, self.expr(node.key, local))] = self.expr(node.value, local)
                    else: result.append(self.expr(node.elt, local))
                    return
                gen = node.generators[index]
                if gen.is_async: self.fail(node, 'ASYNC_COMPREHENSION')
                for number, value in enumerate(self.sequence(node, self.expr(gen.iter, local))):
                    self.tick(); self.bind(gen.target, value, local)
                    self.scope.append('comprehension:' + str(number+1))
                    try:
                        if all(self.condition(test, self.expr(test, local)) for test in gen.ifs): collect(index+1)
                    finally: self.scope.pop()
            collect(0)
            return result
        if isinstance(node, ast.Call): return self.call(node, env)
        self.fail(node, type(node).__name__)

    def call(self, node, env):
        from finarch.dataset.shared.calculation.python_graph import FUNCTIONS
        name = ast.unparse(node.func)
        name = self.aliases.get(name, name)
        # Arguments are evaluated left to right, once.
        args = [self.expr(x, env) for x in node.args]
        kwargs = {x.arg: self.expr(x.value, env) for x in node.keywords}
        if None in kwargs: self.fail(node, 'KEYWORD_UNPACKING')
        if name == 'fact' and not kwargs and len(args) == 1 and args[0] in self.facts:
            key = args[0]; self.used.add(key); f = self.facts[key]
            return self.add(node, 'fact', key, float(f['value']), fact_id=key, value=str(float(f['value'])),
                            value_type='float', span=f['span'], text=f['text'], unit=f.get('unit'))
        if name == 'evidence' and not kwargs and args and args[0] in self.evidence:
            from finarch.dataset.shared.calculation.external_evidence import lookup
            value = lookup(self.evidence[args[0]], [x.value for x in args[1:]])
            return self.add(node, 'operation', 'external table lookup', value, args[1:], operator='evidence', evidence_id=args[0])
        if name in ('min', 'max') and not kwargs:
            values = list(self.sequence(node, args[0])) if len(args) == 1 else args
            if not values: self.fail(node, 'EMPTY_AGGREGATE')
            result = values[0]
            for item in values[1:]: result = self.op(node, name, [result, item])
            return result
        if name == 'sum' and len(args) in (1,2) and not kwargs:
            start = args[1] if len(args)==2 else self.constant(node, 0)
            return self.op(node, 'sum', [start,*self.sequence(node,args[0])])
        if name == 'len' and len(args)==1 and not kwargs:
            if not isinstance(args[0], (list,tuple,dict)): self.fail(node, 'LEN_CONTAINER')
            return self.constant(node, len(args[0]))
        if name == 'range' and 1 <= len(args) <= 3 and not kwargs:
            values = [self.pin(node, x, 'range_bound') for x in args]
            if not all(type(x) is int for x in values): self.fail(node, 'RANGE_INTEGER_REQUIRED')
            seq = range(*values)
            if len(seq)>self.MAX_ITERATIONS: raise ValueError('GRAPH_EXPANSION_ITERATION_LIMIT')
            return [self.constant(node, x) for x in seq]
        if name == 'zip' and not kwargs:
            return list(zip(*(self.sequence(node, x) for x in args)))
        if name == 'enumerate' and len(args) in (1,2) and not kwargs:
            start = self.pin(node, args[1], 'enumerate_start') if len(args)==2 else 0
            return [(self.constant(node, i), value) for i,value in enumerate(self.sequence(node,args[0]),start)]
        if name == 'sorted' and len(args)==1 and set(kwargs) <= {'reverse'}:
            reverse = bool(self.pin(node, kwargs['reverse'], 'sort_reverse')) if kwargs else False
            values = self.sequence(node, args[0])
            if not all(isinstance(x,Number) for x in values): self.fail(node,'NUMERIC_SORT_ONLY')
            # Insertion sort records every comparison, including equal-value order.
            result=[]
            for value in values:
                pos=len(result)
                while pos and self.condition(node,self.op(node,'>' if reverse else '<',[value,result[pos-1]])): pos-=1
                result.insert(pos,value)
            return result
        if name == 'statistics.mean' and len(args)==1 and not kwargs:
            return self.op(node, name, list(self.sequence(node,args[0])))
        if name in FUNCTIONS and not kwargs: return self.op(node, name, args)
        if isinstance(node.func,ast.Name) and isinstance(env.get(node.func.id),Function):
            fn=env[node.func.id]; parameters=fn.node.args
            if parameters.posonlyargs or parameters.kwonlyargs or parameters.vararg or parameters.kwarg or parameters.defaults:
                self.fail(node,'FUNCTION_SIGNATURE')
            names=[x.arg for x in parameters.args]
            if len(args)>len(names) or set(kwargs)-set(names) or set(names[:len(args)]) & set(kwargs): self.fail(node,'FUNCTION_ARGUMENTS')
            bound=dict(zip(names,args));bound.update(kwargs)
            if set(bound)!=set(names): self.fail(node,'FUNCTION_ARGUMENTS')
            if id(fn) in self.active or len(self.active)>=self.MAX_CALL_DEPTH: raise ValueError('GRAPH_RECURSION_UNSUPPORTED')
            local=fn.closure.new_child(bound);self.active.append(id(fn));self.scope.append(fn.node.name+'@'+str(node.lineno))
            self.events.append({'line':node.lineno,'kind':'function_call','function':fn.node.name,'scope':list(self.scope)})
            try:
                try: self.block(fn.node.body,local)
                except Return as returned: return returned.value
            finally: self.active.pop();self.scope.pop()
            self.fail(node,'NUMERIC_RETURN_REQUIRED')
        self.fail(node,'CALL:'+name)

    def tick(self):
        self.iterations += 1
        if self.iterations > self.MAX_ITERATIONS: raise ValueError('GRAPH_EXPANSION_ITERATION_LIMIT')

    def block(self, statements, env):
        for node in statements:
            self.steps+=1
            if self.steps>self.MAX_STEPS: raise ValueError('GRAPH_EXPANSION_STEP_LIMIT')
            if isinstance(node,ast.Assign) and len(node.targets)==1: self.bind(node.targets[0],self.expr(node.value,env),env)
            elif isinstance(node,ast.AugAssign) and isinstance(node.target,ast.Name):
                from finarch.dataset.shared.calculation.python_graph import BINARY
                if type(node.op) not in BINARY: self.fail(node,'AUGMENTED_OPERATOR')
                self.bind(node.target,self.op(node,BINARY[type(node.op)],[env[node.target.id],self.expr(node.value,env)]),env)
            elif isinstance(node,ast.If):
                selected=self.condition(node.test,self.expr(node.test,env), control='if')
                decision=self.events[-1];start=len(self.nodes)
                self.events.append({'line':node.lineno,'kind':'if','selected':'then' if selected else 'else','scope':list(self.scope)})
                self.scope.append('if:'+str(node.lineno)+('T' if selected else 'F'))
                try: self.block(node.body if selected else node.orelse,env)
                finally:
                    decision['_body_span']=(start,len(self.nodes))
                    self.scope.pop()
            elif isinstance(node,(ast.For,ast.While)):
                values=iter(self.sequence(node,self.expr(node.iter,env))) if isinstance(node,ast.For) else None
                index=0;broken=False
                while True:
                    if values is not None:
                        try: value=next(values)
                        except StopIteration: break
                        self.bind(node.target,value,env)
                    else:
                        selected=self.condition(node.test,self.expr(node.test,env),
                                                control='while', iteration=index+1)
                        decision=self.events[-1];start=len(self.nodes)
                        if not selected:
                            decision['_body_span']=(start,start)
                            break
                    self.tick();index+=1;self.scope.append(type(node).__name__.lower()+':'+str(node.lineno)+'#'+str(index))
                    try:
                        try: self.block(node.body,env)
                        except Continue: pass
                        except Break: broken=True;break
                    finally:
                        if values is None: decision['_body_span']=(start,len(self.nodes))
                        self.scope.pop()
                self.events.append({'line':node.lineno,'kind':type(node).__name__.lower(),'iterations':index,'break':broken,'scope':list(self.scope)})
                if not broken:self.block(node.orelse,env)
            elif isinstance(node,ast.FunctionDef):
                if node.decorator_list: self.fail(node,'DECORATED_FUNCTION')
                env[node.name]=Function(node,env)
            elif isinstance(node,ast.Return): raise Return(self.expr(node.value,env))
            elif isinstance(node,ast.Break): raise Break()
            elif isinstance(node,ast.Continue): raise Continue()
            elif isinstance(node,(ast.Import,ast.ImportFrom)):
                from finarch.dataset.shared.calculation.python_graph import FUNCTIONS
                modules={'math','statistics'}
                if isinstance(node,ast.Import):
                    for alias in node.names:
                        if alias.name not in modules:self.fail(node,'IMPORT:'+alias.name)
                        for name in FUNCTIONS:
                            if name.startswith(alias.name+'.'):self.aliases[(alias.asname or alias.name)+name[len(alias.name):]]=name
                else:
                    if node.module not in modules or node.level:self.fail(node,'IMPORT:'+str(node.module))
                    for alias in node.names:
                        name=node.module+'.'+alias.name
                        if name not in FUNCTIONS:self.fail(node,'IMPORT:'+name)
                        self.aliases[alias.asname or alias.name]=name
            elif isinstance(node,ast.Pass) or (isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)):pass
            else:self.fail(node,type(node).__name__)

    def build(self):
        tree=ast.parse(self.program['code'])
        if len(list(ast.walk(tree)))>2000:raise ValueError('GRAPH_PROGRAM_TOO_COMPLEX')
        self.block(tree.body,self.env)
        answer=self.env.get('answer')
        if not isinstance(answer,Number) or self.used!=set(self.facts):raise ValueError('INCOMPLETE_GRAPH_FACTS_OR_ANSWER')
        # Guard results form a balanced AND tree to avoid a linear guard chain.
        internal_start=len(self.nodes)
        level=self.guards[:]
        anchor=tree.body[-1]
        while len(level)>1:
            level=[self.op(anchor,'and',level[i:i+2]) if i+1<len(level) else level[i] for i in range(0,len(level),2)]
        if level:
            guarded=self.op(anchor,'path_guard',[answer,level[0]])
            self.bind(ast.copy_location(ast.Name(id='answer',ctx=ast.Store()),anchor),guarded,self.env)
        self.mark_internal(internal_start)
        control_links=self.control_links()
        variables={k:v.key for k,v in self.env.maps[0].items() if isinstance(v,Number) and not k.startswith('_')}
        graph={'format':'finarch-python-dag-v1','code_sha256':hashlib.sha256(self.program['code'].encode()).hexdigest(),
               'numeric_semantics':'Python scalars; bounded concrete-path expansion with replay guards',
               'nodes':self.nodes,'variables':variables,'output':variables['answer'],
               'edges':[{'from':p,'to':n['id'],'input_index':i} for n in self.nodes for i,p in enumerate(n['inputs'])],
               'control_flow':{'mode':'concrete-path','events':self.events,'guards':[x.key for x in self.guards],
                               'links':control_links,
                               'display_output':answer.key,
                               'on_path_change':'RECOMPILE_FROM_SAME_CODE',
                               'limits':{'nodes':self.MAX_NODES,'iterations':self.MAX_ITERATIONS,'steps':self.MAX_STEPS,'call_depth':self.MAX_CALL_DEPTH}}}
        if self.evidence:graph['external_evidence']=self.evidence
        return graph


def compile_control(program,facts,evidence):
    return Builder(program,facts,evidence).build()
