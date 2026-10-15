"""Interpret assignments and arithmetic without exec/eval or arbitrary Python calls.

Facts must point to literal numeric spans in the original context. This checks
numeric correspondence, not the semantic identity of a financial quantity.
"""

traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
import ast
import re
from fractions import Fraction

StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult


OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
CONSTANTS = {Fraction(0), Fraction(1), Fraction(100), Fraction(1000), Fraction(1000000)}


@traced("python")
def exact(text):
    if isinstance(text, bool) or not isinstance(text, (str, int)):
        raise ValueError("EXACT_NUMBER_REQUIRED")
    if len(str(text)) > 256:
        raise ValueError("NUMBER_TOO_LONG")
    value = Fraction(text)
    if value.numerator.bit_length() > 4096 or value.denominator.bit_length() > 4096:
        raise ValueError("NUMBER_TOO_LARGE")
    return value


@traced("python")
def calculate(op, operands):
    if op == "+": value = operands[0] + operands[1]
    elif op == "-": value = operands[0] - operands[1]
    elif op == "*": value = operands[0] * operands[1]
    elif op == "/": value = operands[0] / operands[1]
    elif op == "neg": value = -operands[0]
    elif op == "pos": value = operands[0]
    else: raise ValueError("UNSUPPORTED_OPERATOR")
    return exact(str(value))


@traced("python")
def checked_facts(program):
    context, facts = program["context"], program["facts"]
    if not isinstance(context, str) or not isinstance(facts, dict) or not facts:
        raise ValueError("CONTEXT_AND_FACTS_REQUIRED")
    checked = {}
    for name, fact in facts.items():
        if not isinstance(name, str) or not name or not isinstance(fact, dict):
            raise ValueError("INVALID_FACT")
        start, end = fact["span"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(context):
            raise ValueError("INVALID_FACT_SPAN")
        text = context[start:end]
        if text != fact["text"] or not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?", text):
            raise ValueError("FACT_SPAN_NOT_A_NUMBER")
        value = exact(fact["value"])
        if value != exact(text.rstrip("%").replace(",", "")):
            raise ValueError("FACT_VALUE_DOES_NOT_MATCH_SOURCE")
        checked[name] = {"value": str(value), "text": text, "span": [start, end],
                         "unit": str(fact.get("unit", "unspecified"))}
    return checked


@traced("python")
def validated_tree(program):
    code = program["code"]
    if not isinstance(code, str) or len(code) > 20000:
        raise ValueError("PROGRAM_TOO_LONG_OR_INVALID")
    tree = ast.parse(code)
    if len(list(ast.walk(tree))) > 500:
        raise ValueError("PROGRAM_TOO_COMPLEX")
    facts = checked_facts(program)
    names, used, dependencies = set(), set(), {}
    @traced("python")
    def check(node):
        if isinstance(node, ast.Name):
            if node.id not in names: raise ValueError("UNBOUND_VARIABLE")
        elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if exact(ast.get_source_segment(code, node)) not in CONSTANTS:
                raise ValueError("UNGROUNDED_CONSTANT_USE_FACT")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "fact":
            if node.keywords or len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
                raise ValueError("FACT_CALL_REQUIRES_ONE_ID")
            key = node.args[0].value
            if not isinstance(key, str) or key not in facts: raise ValueError("UNKNOWN_FACT")
            used.add(key)
        elif isinstance(node, ast.BinOp) and type(node.op) in OPS:
            check(node.left); check(node.right)
        elif isinstance(node, ast.UnaryOp) and type(node.op) in (ast.USub, ast.UAdd):
            check(node.operand)
        else:
            raise ValueError(f"UNSUPPORTED_SYNTAX:{type(node).__name__}")
    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            raise ValueError("ONLY_SINGLE_VARIABLE_ASSIGNMENTS_ALLOWED")
        name = statement.targets[0].id
        if name in names or name == "fact" or name.startswith("_"):
            raise ValueError("REASSIGNMENT_OR_RESERVED_NAME")
        check(statement.value)
        contributing = set()
        for node in ast.walk(statement.value):
            if isinstance(node, ast.Name) and node.id in dependencies:
                contributing.update(dependencies[node.id])
            elif isinstance(node, ast.Call):
                contributing.add(node.args[0].value)
        dependencies[name] = contributing
        names.add(name)
    if "answer" not in names: raise ValueError("ANSWER_VARIABLE_REQUIRED")
    if used != set(facts): raise ValueError("UNUSED_FACTS")
    if dependencies["answer"] != set(facts): raise ValueError("FACTS_NOT_CONNECTED_TO_ANSWER")
    return tree, facts


@traced("python")
def compile_program(program):
    tree, facts = validated_tree(program)
    code = program["code"]
    nodes, names, used = [], {}, set()

    @traced("python")
    def add(kind, label, inputs=(), **fields):
        node_id = f"n{len(nodes)}"
        nodes.append({"id": node_id, "kind": kind, "label": label, "inputs": list(inputs), **fields})
        return node_id

    @traced("python")
    def expression(node):
        if isinstance(node, ast.Name):
            if node.id not in names: raise ValueError("UNBOUND_VARIABLE")
            return names[node.id]
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = exact(ast.get_source_segment(code, node))
            if value not in CONSTANTS: raise ValueError("UNGROUNDED_CONSTANT_USE_FACT")
            return add("constant", str(value), value=str(value))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "fact":
            if node.keywords or len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
                raise ValueError("FACT_CALL_REQUIRES_ONE_ID")
            key = node.args[0].value
            if not isinstance(key, str) or key not in facts: raise ValueError("UNKNOWN_FACT")
            used.add(key)
            return add("fact", key, fact_id=key, **facts[key])
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return add("operation", OPS[type(node.op)], (expression(node.left), expression(node.right)),
                       operator=OPS[type(node.op)])
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.USub, ast.UAdd):
            op = "neg" if isinstance(node.op, ast.USub) else "pos"
            return add("operation", op, (expression(node.operand),), operator=op)
        raise ValueError(f"UNSUPPORTED_SYNTAX:{type(node).__name__}")

    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            raise ValueError("ONLY_SINGLE_VARIABLE_ASSIGNMENTS_ALLOWED")
        name = statement.targets[0].id
        if name in names or name == "fact" or name.startswith("_"):
            raise ValueError("REASSIGNMENT_OR_RESERVED_NAME")
        names[name] = add("variable", name, (expression(statement.value),), variable=name)
    if "answer" not in names: raise ValueError("ANSWER_VARIABLE_REQUIRED")
    if used != set(facts): raise ValueError("UNUSED_FACTS")
    graph = {"nodes": nodes, "output": names["answer"], "variables": names,
             "edges": [{"from": parent, "to": node["id"]} for node in nodes for parent in node["inputs"]]}
    result, values = evaluate_graph(graph)
    for node in nodes: node["computed"] = str(values[node["id"]])
    return graph, result


@traced("python")
def evaluate_graph(graph):
    values = {}
    for node in graph["nodes"]:
        node_id = node["id"]
        if node_id in values: raise ValueError("DUPLICATE_NODE")
        inputs = [values[parent] for parent in node["inputs"]]
        if node["kind"] in ("fact", "constant"):
            if inputs: raise ValueError("LEAF_WITH_INPUTS")
            value = exact(node["value"])
        elif node["kind"] == "variable":
            if len(inputs) != 1: raise ValueError("INVALID_VARIABLE_INPUT")
            value = inputs[0]
        elif node["kind"] == "operation":
            if len(inputs) != (1 if node["operator"] in ("neg", "pos") else 2):
                raise ValueError("INVALID_OPERATOR_ARITY")
            value = calculate(node["operator"], inputs)
        else: raise ValueError("UNKNOWN_NODE_KIND")
        values[node_id] = value
    return values[graph["output"]], values


@traced("python")
def interpret(program):
    """Separate AST evaluator; compilation/evaluation results are compared below."""
    tree, facts = validated_tree(program)
    code, env = program["code"], {}
    @traced("python")
    def walk(node):
        if isinstance(node, ast.Name): return env[node.id]
        if isinstance(node, ast.Constant): return exact(ast.get_source_segment(code, node))
        if isinstance(node, ast.Call): return exact(facts[node.args[0].value]["value"])
        if isinstance(node, ast.BinOp): return calculate(OPS[type(node.op)], [walk(node.left), walk(node.right)])
        if isinstance(node, ast.UnaryOp): return calculate("neg" if isinstance(node.op, ast.USub) else "pos", [walk(node.operand)])
        raise ValueError("UNSUPPORTED_EXPRESSION")
    # Interpret only; graph extraction occurs after the POT gold comparison.
    for statement in tree.body:
        env[statement.targets[0].id] = walk(statement.value)
    return env["answer"], {key: str(value) for key, value in env.items()}


@traced("python")
def mermaid(graph):
    lines = ["flowchart LR"]
    for node in graph["nodes"]:
        label = re.sub(r'[^\w .+*/=-]', '_', node["label"])
        lines.append(f'  {node["id"]}["{label} = {node["computed"]}"]')
    for edge in graph["edges"]: lines.append(f'  {edge["from"]} --> {edge["to"]}')
    return "\n".join(lines)


@traced("python")
def execute_handler(payload):
    # [P02-1] docs/02-architecture.md#P02-1 — validated_tree·checked_facts 후 interpret로 제한 사칙연산을 계산합니다.
    value, trace = interpret(payload)
    return StepResult("PASS", "Checked supported arithmetic and source numeric spans.",
                      {"exact_value": str(value), "trace": trace, "engine": "bounded-ast-v1"})


@traced("python")
def compile_handler(payload):
    # [D01-1] docs/02-architecture.md#D01-1 — compile_program·evaluate_graph로 그래프·정확값·상수 제외 노드 목록을 반환합니다.
    graph, value = compile_program(payload["program"])
    return StepResult("PASS", "Extracted calculation dependencies from the same code.",
                      {"dag": graph, "variables": [node["id"] for node in graph["nodes"]
                                                      if node["kind"] != "constant"],
                       "exact_value": str(value), "mermaid": mermaid(graph)})


@traced("python")
def local_handlers():
    # [DG04] docs/02-architecture.md#DG04 — 기본 경로는 실제 Python 실행과 현재 코드의 그래프 추출을 사용한다.
    from finarch.dataset.shared.calculation.python_runtime import execute
    from finarch.dataset.shared.calculation.python_graph import compile_handler as python_compile_handler
    return {"pot.execute": execute, "dag.compile": python_compile_handler}
