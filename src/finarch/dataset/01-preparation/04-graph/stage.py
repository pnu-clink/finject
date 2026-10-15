"""Ordered stage subjobs; artifact paths retain their existing contract."""
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
from finarch.dataset.shared.calculation.python_graph import compile_graph


def run(ctx, sample, program, result, report):
    pp01_read_calculation(ctx, program, result)
    compiled = pp02_build_graph(ctx, sample, program)
    graph = pp03_compare_calculation(ctx, compiled, result)
    provenance = pp03_attach_provenance(ctx, program, graph)
    pp04_trace_answer_dependencies(ctx, graph, provenance)
    pp05_save_graph(ctx, graph, report)

def pp01_read_calculation(ctx, program, result):
    ctx.save('04-graph/01-read-calculation/01-input.json', {'program': program, 'execution': result})


def pp02_build_graph(ctx, sample, program):
    def compile_payload(payload):
        graph, value, normalization = compile_graph(payload)
        return StepResult('PASS', 'Graph extracted from the executed program',
                          {'graph': graph, 'exact_value': str(value), 'normalization': normalization})
    compiled = ctx.invoke('04-graph', '02-build-graph', 'dag.compile',
                          {**program, 'context': sample['context'], 'question': sample['question']}, local=compile_payload)
    return compiled


def pp03_compare_calculation(ctx, compiled, result):
    graph = compiled['graph']
    values = {node['id']: node['computed'] for node in graph['nodes']}
    matches = compiled['exact_value'] == result['exact_value'] and all(
        result['trace'].get(name) == values[key] for name, key in graph['variables'].items())
    ctx.save('04-graph/02-build-graph/04-comparison.json', {'status': 'PASS' if matches else 'FAIL'})
    if not matches:
        raise ValueError('PYTHON_GRAPH_MISMATCH')
    return graph


def pp05_save_graph(ctx, graph, report):
    ctx.save('04-graph/05-save-graph/01-graph.json', graph)
    report.update(status='PASS', reason='AWAITING_HUMAN_REVIEW')


def pp03_attach_provenance(ctx, program, graph):
    usages = []
    for usage in program.get('source_usage', []):
        usages.append({**usage, 'graph_nodes': [graph['variables'][name]
                       for name in usage['output_variables'] if name in graph['variables']]})
    attach_node_sources(graph, usages)
    ctx.save('04-graph/03-attach-provenance/01-result.json', usages)
    return usages


def pp04_trace_answer_dependencies(ctx, graph, provenance):
    nodes = {node['id']: node for node in graph['nodes']}
    pending, visited = [graph['output']], set()
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        visited.add(node)
        pending.extend(nodes[node].get('inputs', []))
    used = [usage for usage in provenance if visited.intersection(usage['graph_nodes'])]
    result = {'output': graph['output'], 'ancestor_nodes': sorted(visited),
              'source_usage': used, 'calculation_input_sources': sorted({u['kind'] for u in used}),
              'classification': 'PENDING_VERIFICATION'}
    ctx.save('04-graph/04-trace-answer-dependencies/01-result.json', result)
    return result

pp04_save_graph = pp05_save_graph


def attach_node_sources(graph, usages):
    """Attach declared rules to their operations without relabeling input facts."""
    nodes = {node['id']: node for node in graph['nodes']}
    for usage in usages:
        if usage['kind'] not in ('EXTERNAL_RULE', 'EXTERNAL_DATA'):
            continue
        for name in usage['output_variables']:
            variable = nodes.get(graph['variables'].get(name))
            if not variable or variable.get('code_line') not in usage['code_lines']:
                continue
            pending = list(variable.get('inputs', []))
            while pending:
                node = nodes[pending.pop()]
                if node['kind'] != 'operation':
                    continue
                node['source_usage_ids'] = sorted(set(node.get('source_usage_ids', [])) | {usage['id']})
                node['evidence_types'] = sorted(set(node.get('evidence_types', [])) | {usage['kind']})
                pending.extend(node.get('inputs', []))
    graph['source_usage'] = usages
    return graph
