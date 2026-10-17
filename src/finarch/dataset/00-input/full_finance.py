"""Prepare the complete pinned distribution; inspect source ASTs without execution."""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path

adapters = __import__('finarch.dataset.00-input.adapters', fromlist=['*'])
sha256 = __import__('finarch.dataset.00-input.build', fromlist=['sha256']).sha256
write_json = __import__('finarch.dataset.00-input.build', fromlist=['write_json']).write_json
from finarch.shared.reference import load_raw
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.validation import validate
from finarch.dataset.shared.calculation.python_graph import FUNCTIONS


SYNTAX_LABELS = {
    'for_loop': 'for loop',
    'while_loop': 'while loop',
    'block_if': 'Block if/else',
    'comprehension': 'List/set/dictionary comprehensions and generator expressions',
    'non_math_import': 'Imports other than math',
    'unsupported_numeric_call': 'Numeric/aggregation calls unsupported by the graph',
    'helper_function': 'Additional/nested function definitions',
}


def inspect_code(code):
    """Inventory syntax, not a prediction of fresh LLM POT failures."""
    tree = ast.parse(code)
    nodes = list(ast.walk(tree))
    flags = set()
    for tag, kinds in (
        ('for_loop', (ast.For, ast.AsyncFor)), ('while_loop', (ast.While,)),
        ('block_if', (ast.If,)),
        ('comprehension', (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)),
    ):
        if any(isinstance(n, kinds) for n in nodes): flags.add(tag)
    imports = [n for n in nodes if isinstance(n, (ast.Import, ast.ImportFrom))]
    if any((any(x.name != 'math' for x in n.names) if isinstance(n, ast.Import)
            else n.module != 'math' or n.level) for n in imports): flags.add('non_math_import')
    functions = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))]
    if len(functions) > 1 or any(isinstance(n, ast.Lambda) for n in functions): flags.add('helper_function')
    aliases = {}
    for n in imports:
        if isinstance(n, ast.ImportFrom) and n.module == 'math':
            aliases.update({x.asname or x.name: 'math.' + x.name for x in n.names})
        elif isinstance(n, ast.Import):
            aliases.update({x.asname or x.name: x.name for x in n.names})
    numeric_builtins = {'sum','len','range','abs','min','max','round','pow','int','float',
                        'sorted','zip','enumerate','Decimal','Fraction'}
    calls = set()
    for n in nodes:
        if not isinstance(n, ast.Call): continue
        name = ast.unparse(n.func)
        first, dot, rest = name.partition('.')
        name = aliases.get(first, first) + (dot + rest if dot else '')
        if (name.startswith('math.') or name in numeric_builtins) and name not in FUNCTIONS:
            calls.add(name)
    if calls: flags.add('unsupported_numeric_call')
    return {'patterns': sorted(flags), 'unsupported_numeric_calls': sorted(calls),
            'has_function_wrapper': bool(functions),
            'has_conditional_expression': any(isinstance(n, ast.IfExp) for n in nodes),
            'has_indexed_input': any(isinstance(n, ast.Subscript) for n in nodes)}


def empty_context(text):
    """Recognize blank text and serialized empty JSON containers as absent C."""
    text = text.strip()
    if not text:
        return True
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return False
    return value is None or (isinstance(value, (list, dict, str)) and not value)


def prepare(catalog_path, output, *, source_prefix=None, id_map=None, expected_count=None):
    """Exclude only empty C, boolean A and exact Q+C duplicates; keep original bytes."""
    catalog_path, output = Path(catalog_path).resolve(), Path(output).resolve()
    catalog = json.loads(catalog_path.read_text())
    specs = catalog['sources']
    if [s['name'] for s in specs] != ['finance-easy','finance-medium','finance-hard']:
        raise ValueError('FULL_FINANCE_REQUIRES_THREE_ORDERED_SOURCES')
    if source_prefix is not None and (not isinstance(source_prefix, str) or not source_prefix):
        raise ValueError('INVALID_SOURCE_PREFIX')
    prior_ids = {}
    if id_map:
        for sample in json.loads(Path(id_map).read_text()):
            if sample['raw_id'] in prior_ids or sample['id'] in prior_ids.values():
                raise ValueError('DUPLICATE_ID_MAP')
            prior_ids[sample['raw_id']] = sample['id']
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'preparation-start.json', {'status':'RUNNING','model_calls':0,
               'catalog_path':str(catalog_path), 'scope':'source-filtered-distribution' if source_prefix else 'complete-distribution',
               'source_prefix':source_prefix})
    samples, providers, sources, exclusions, syntax = [], {}, [], [], []
    seen, raw_ids = {}, set()
    counts = {}
    try:
        for spec in specs:
            path = Path(spec['path'])
            if not path.is_absolute(): path = catalog_path.parent/path
            content = path.read_bytes()
            if sha256(content) != spec['sha256']: raise ValueError('SOURCE_HASH_MISMATCH:'+spec['name'])
            provenance = {k:spec[k] for k in ('name','sha256','url','commit')}
            sources.append({**provenance,'path':str(path.resolve())})
            tally = Counter(total=0, source_filtered=0, empty_context=0, boolean_answer=0, duplicate_qc=0, selected=0)
            for index, record in enumerate(load_raw(content)):
                tally['total'] += 1
                if source_prefix and not record['source'].startswith(source_prefix):
                    tally['source_filtered'] += 1
                    continue
                raw_id = 'finance-'+record['question_id']
                if raw_id in raw_ids: raise ValueError('DUPLICATE_RAW_ID:'+raw_id)
                raw_ids.add(raw_id)
                identity = {'raw_id':raw_id,'source':spec['name'],'record_index':index,
                            'question_id':record['question_id']}
                if not isinstance(record['context'],str): raise ValueError('INVALID_CONTEXT')
                if not isinstance(record['question'],str) or not record['question'].strip():
                    raise ValueError('INVALID_QUESTION')
                if empty_context(record['context']): reason='empty_context'
                elif type(record['ground_truth']) is bool: reason='boolean_answer'
                elif (record['question'],record['context']) in seen: reason='duplicate_qc'
                else: reason=None
                if reason:
                    row={**identity,'reason':reason}
                    if reason=='duplicate_qc':
                        kept=seen[(record['question'],record['context'])]
                        row.update(kept_id=kept['id'], kept_raw_id=kept['raw_id'],
                                   same_answer=record['ground_truth']==kept['ground_truth'])
                    exclusions.append(row);tally[reason]+=1
                    continue
                if id_map and raw_id not in prior_ids:
                    raise ValueError('SOURCE_NOT_IN_ID_MAP:'+raw_id)
                sample={'id':prior_ids[raw_id] if id_map else f'test-{len(samples)+1:04d}',
                        **adapters.finance(record,provenance,distributed=True)}
                samples.append(sample);tally['selected']+=1
                seen[(record['question'],record['context'])]={**sample,'ground_truth':record['ground_truth']}
                providers[raw_id]={'source':spec['name'],'record_index':index,
                                  'record':record,'question_id':record['question_id']}
                syntax.append({'id':sample['id'],**identity,**inspect_code(record['python_solution'])})
            counts[spec['name']]=dict(tally)
        if expected_count is not None and len(samples) != expected_count:
            raise ValueError(f'EXPECTED_COUNT_MISMATCH:{len(samples)}:{expected_count}')
        validate('01-preparation.01-source.prepared-input',samples)
        write_json(output/'input.json',samples)
        write_json(output/'provider-records.json',providers)
        totals={k:sum(row[k] for row in counts.values()) for k in next(iter(counts.values()))}
        manifest={'format':'fin-arch-preparation-v1','families':len(samples),'model_calls':0,
                  'input_schema':{k:v for k,v in describe('01-preparation.01-source.prepared-input').items() if k!='schema'},
                  'counts':counts,'totals':totals,'sources':sources,'exclusions':exclusions,
                  'selection_policy':{'finance_scope':'source-filtered pinned FinanceReasoning distribution' if source_prefix else 'complete pinned FinanceReasoning distribution',
                      'source_prefix':source_prefix,
                      'id_map_path':str(Path(id_map).resolve()) if id_map else None,
                      'id_map_sha256':sha256(Path(id_map).read_bytes()) if id_map else None,
                      'exclude':['empty_context','boolean_answer','duplicate_qc'],
                      'empty_context_definition':'Blank text or serialized JSON null, empty string, array or object.',
                      'duplicate_key':['question','context'],'comparison':'exact Unicode strings',
                      'keep':'first in easy, medium, hard file order; then original record order',
                      'context_only_deduplication':False,'reuse_previous_llm_outputs':False},
                  'ids':[{'id':s['id'],'raw_id':s['raw_id']} for s in samples],
                  'input_file_sha256':sha256((output/'input.json').read_bytes()),
                  'provider_file_sha256':sha256((output/'provider-records.json').read_bytes())}
        write_json(output/'selection-manifest.json',manifest)
        audit={'scope':'retained raw python_solution ASTs, not newly generated POT',
               'model_calls':0,'programs_executed':0,'total':len(syntax),
               'pattern_counts':{k:sum(k in r['patterns'] for r in syntax) for k in SYNTAX_LABELS},
               'unique_cases_with_patterns':sum(bool(r['patterns']) for r in syntax),
               'function_wrappers':sum(r['has_function_wrapper'] for r in syntax),
               'conditional_expressions':sum(r['has_conditional_expression'] for r in syntax),
               'indexed_inputs':sum(r['has_indexed_input'] for r in syntax), 'cases':syntax,
               'limitations':['Counts overlap. Source function wrappers and table indexing need POT rewriting, not automatic rejection.',
                              'No old LLM output was used. This cannot measure fresh POT failure rates.']}
        write_json(output/'code-syntax-audit.json',audit)
        write_json(output/'selection-log.json',{'counts':counts,'totals':totals,'exclusions':exclusions})
        readme=Path(__file__).with_name('full-finance-readme.md').read_text()
        (output/'README.md').write_text(readme.format(count=len(samples), **totals))
        write_json(output/'preparation-result.json',{'status':'PASS','families':len(samples),
                   'model_calls':0,'manifest_sha256':sha256((output/'selection-manifest.json').read_bytes()),
                   'counts':counts,'totals':totals})
        return {'output':str(output),'totals':totals,'patterns':audit['pattern_counts'],
                'unique_cases_with_patterns':audit['unique_cases_with_patterns'],'model_calls':0}
    except Exception as error:
        write_json(output/'preparation-result.json',{'status':'FAIL','model_calls':0,
                   'reason':type(error).__name__+': '+str(error)})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--hyperparameter', help='Input selection settings: source prefix, ID map and expected count')
    args=parser.parse_args()
    selection = json.loads(Path(args.hyperparameter).read_text())['input'] if args.hyperparameter else {}
    print(json.dumps(prepare(args.catalog,args.output, source_prefix=selection.get('source_prefix'),
                            id_map=selection.get('id_map_path'), expected_count=selection.get('expected_count')),ensure_ascii=False))


if __name__=='__main__':main()
