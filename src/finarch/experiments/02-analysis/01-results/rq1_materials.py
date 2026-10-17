"""RQ1 submitted classifications, separate from semantic response judgments."""
from collections import Counter, defaultdict
from importlib import import_module
from pathlib import Path

store = import_module('finarch.experiments.90-operations.storage')
layout = import_module('finarch.experiments.90-operations.run_layout')
pairs = import_module('finarch.experiments.02-analysis.02-comparison.pair_outcomes')
OUTPUT = '02_analysis/01_results/rq1-materials'
CLASSIFICATIONS = {'ANSWERABLE', 'CONFLICT', 'INSUFFICIENT_EVIDENCE', 'UNRESOLVED', 'ABSTAIN'}


def inverse_reconstruction(_rows):
    """Reserved for an agreed reconstruction rubric; never infer from numeric match."""
    return None


def submitted(result, condition, expected):
    if not result or result.get('status') != 'VALID':
        return None, 'RESPONSE_UNAVAILABLE'
    value = (result.get('response') or {}).get('classification')
    if condition == 'unguided':
        return None, 'CLASSIFICATION_NOT_REQUESTED'
    if value not in CLASSIFICATIONS:
        return None, 'CLASSIFICATION_UNAVAILABLE'
    return value == expected, 'OBSERVED'


def aggregate(rows, metric):
    total = len(rows)
    counts = Counter(row['quadrant'] for row in rows if row['quadrant'] is not None)
    numerator = (sum(r['y'] is True for r in rows) if metric in ('OVS', 'OVS_all') else counts[1])
    labels = Counter(r['classification'] for r in rows if r['classification'] in CLASSIFICATIONS and r['y'] is not None)
    return {'N': total, 'numerator': numerator, 'denominator': total,
            'fraction': f'{numerator}/{total}', 'rate': numerator / total if total else None,
            'numerator_definition': 'SUBMITTED_CONFLICT' if metric.startswith('OVS') else 'BOTH_AXES_TRUE',
            'denominator_symbol': 'm' if metric == 'OVS' else 'N',
            'quadrants': {str(q): {'count': counts[q], 'denominator': total,
                'fraction': f'{counts[q]}/{total}', 'ratio_of_planned': counts[q] / total if total else None} for q in range(1, 5)},
            'unplaced': total-sum(counts.values()),
            'unplaced_reasons': dict(Counter(r['placement_status'] for r in rows if r['quadrant'] is None)),
            'classifications': dict(labels),
            'answerable_count': labels['ANSWERABLE'],
            'answerable_rate': labels['ANSWERABLE']/total if total else None,
            'response_ids': [r['response_id'] for r in rows]}


def parent_eligibility(meta, observations):
    """Only the saved provenance link selects the relevant value parent."""
    parents = meta.get('matched_value_parent_ids', [])
    if len(parents) != 1:
        return None, 'VALUE_PARENT_LINK_UNCONFIRMED', None
    parent = observations.get(parents[0])
    if not parent or parent['metric'] != 'OV' or parent['original_item_id'] != meta['original_item_id']:
        return None, 'VALUE_PARENT_NOT_PLANNED', parents[0]
    if parent['x'] is False or parent['y'] is False:
        return False, 'OV_NOT_BOTH_SUCCESSFUL', parents[0]
    if parent['x'] is True and parent['y'] is True:
        return True, 'OV_BOTH_SUCCESSFUL', parents[0]
    return None, 'OV_UNDETERMINED', parents[0]


def build(root):
    root = Path(root).resolve()
    with store.locked(root/'.rq1-materials.lock'):
        store.verify(root)
        private_path = layout.inputs(root)/'private.jsonl'
        public_path = layout.inputs(root)/'public.jsonl'
        private = pairs.indexed(store.rows(private_path), ('item_id',))
        public = pairs.indexed(store.rows(public_path), ('item_id',))
        numeric_path = layout.validation(root)/'numeric-comparisons.jsonl'
        numeric = pairs.indexed(store.rows(numeric_path), ('model', 'trial_id'))
        paths = [private_path, public_path, numeric_path]
        hashes = {str(p.relative_to(root)): store.file_hash(p) for p in paths if p.exists()}
        records, selection = [], []
        for model in store.configuration(root)['models']:
            request_path = layout.requests(root, model['key'])
            result_path = layout.validation(root, model['key'])/'results.jsonl'
            for p in (request_path, result_path):
                if p.exists(): hashes[str(p.relative_to(root))] = store.file_hash(p)
            requests = store.rows(request_path)
            pairs.indexed(requests, ('trial_id',))
            expected = pairs.indexed(requests, ('item_id', 'prompt_condition', 'reasoning'))
            results = pairs.indexed(store.rows(result_path), ('trial_id',))
            planned_ids = {r['trial_id'] for r in requests}
            if any(k[0] not in planned_ids for k in results):
                raise ValueError('RQ1_UNPLANNED_RESPONSE')
            by_condition = defaultdict(dict)
            sources = []
            for req in requests:
                if req['variant'] == 'ORIGINAL': continue
                variant = req['variant']
                metric = ('OVS_all' if variant.startswith('IC_SOURCE') else 'OV' if variant.startswith('IC_VALUE')
                          else 'OR' if variant.startswith('IC_RELATION') else 'OE' if variant.startswith('EA_') else None)
                if metric is None: continue
                meta = private[(req['item_id'],)]
                original_id = meta['original_item_id']
                original = expected.get((original_id, req['prompt_condition'], req['reasoning']))
                baseline = results.get((original['trial_id'],)) if original else None
                result = results.get((req['trial_id'],))
                for definition, value in ((req, result), (original, baseline)):
                    if value and any(value.get(k) != definition[k] for k in ('item_id','variant','prompt_condition','reasoning','case')):
                        raise ValueError('RQ1_REQUEST_RESULT_LINK_MISMATCH')
                check = numeric.get((model['key'], original['trial_id'])) if original else None
                match = pairs.original_numeric(baseline, check)
                x = True if match == 'MATCH' else False if match == 'MISMATCH' else None
                condition = layout.prompt_condition(req['prompt_condition'])
                target = 'INSUFFICIENT_EVIDENCE' if metric == 'OE' else 'CONFLICT'
                y, observation = submitted(result, condition, target)
                q = pairs.quadrant(x,y)
                row = {'metric': metric, 'model': model['key'], 'source': private[(original_id,)].get('source', 'NOT_RECORDED'),
                    'variant': variant, 'case':req['case'], 'prompt_condition':condition,'reasoning':req['reasoning'],
                    'response_id':model['key']+':'+req['trial_id'], 'trial_id':req['trial_id'],
                    'item_id':req['item_id'], 'original_item_id':original_id,
                    'original_trial_id':original['trial_id'] if original else None,
                    'x':x, 'y':y, 'quadrant':q, 'target_classification':target,
                    'classification':((result or {}).get('response') or {}).get('classification'),
                    'response_status':(result or {}).get('status','NOT_COLLECTED'),
                    'observation_status':observation,
                    'placement_status':'PLACED' if q else 'ORIGINAL_UNASSESSED' if x is None else observation,
                    'result_path':(result or {}).get('result_path'),
                    'input_sha256':store.digest(public[(req['item_id'],)]),
                    'original_input_sha256':store.digest(public[(original_id,)])}
                records.append(row)
                by_condition[(condition,req['reasoning'])][req['item_id']] = row
                if metric == 'OVS_all': sources.append((meta,row))
            for meta, row in sources:
                eligible, reason, parent = parent_eligibility(meta, by_condition[(row['prompt_condition'],row['reasoning'])])
                selection.append({**{k:row[k] for k in ('response_id','model','source','variant','prompt_condition','reasoning')},
                    'eligible':eligible,'reason':reason,'parent_item_id':parent})
                if eligible:
                    records.append({**row,'metric':'OVS','value_parent_item_id':parent})
        groups = defaultdict(list)
        for row in records:
            groups[tuple(row[k] for k in ('metric','model','source','prompt_condition','reasoning','variant'))].append(row)
        summaries = [{**dict(zip(('metric','model','source','prompt_condition','reasoning','variant'),key)),**aggregate(rows,key[0])}
                     for key,rows in sorted(groups.items())]
        # Empty eligible cohorts still have an explicit zero denominator and eligibility coverage.
        cohorts = defaultdict(list)
        for row in selection:
            cohorts[tuple(row[k] for k in ('model','source','prompt_condition','reasoning','variant'))].append(row)
        for key, rows in cohorts.items():
            found = next((s for s in summaries if s['metric']=='OVS' and tuple(s[k] for k in ('model','source','prompt_condition','reasoning','variant'))==key),None)
            if found is None:
                found = {'metric':'OVS',**dict(zip(('model','source','prompt_condition','reasoning','variant'),key)),**aggregate([],'OVS')}
                summaries.append(found)
            found['cohort'] = {'planned_source_responses':len(rows),'eligible':sum(r['eligible'] is True for r in rows),
                              'excluded':sum(r['eligible'] is False for r in rows),'undetermined':sum(r['eligible'] is None for r in rows)}
        for relative, digest in hashes.items():
            if store.file_hash(root/relative)!=digest: raise ValueError('RQ1_SOURCE_CHANGED:'+relative)
        summary = {'schema_version':'RQ1MaterialsV1','run_id':root.name,'title':'RQ1 analysis data',
            'created_at':store.now(),'status':'AVAILABLE','new_model_calls':0,
            'basis':'SUBMITTED_CLASSIFICATION_NOT_SEMANTIC_SUCCESS','original_axis':'SAVED_NUMERIC_MATCH',
            'groups':summaries,'source_hashes':hashes,
            'inverse_reconstruction':{'status':'TBD','result':inverse_reconstruction(records)},
            'records_path':OUTPUT+'/records.jsonl','selection_path':OUTPUT+'/source-selection.jsonl'}
        folder = root/OUTPUT
        store.write_rows(folder/'records.jsonl',records)
        store.write_rows(folder/'source-selection.jsonl',selection)
        store.write(folder/'summary.json',summary)
        template = store.PROJECT/'src/finarch/experiments/templates/rq1-materials-readme.md'
        store.write_text(folder/'README.md',template.read_text().replace('{run_id}',root.name))
        store.event(root,'RQ1_MATERIALS_SAVED',groups=len(summaries),new_model_calls=0)
        return summary
