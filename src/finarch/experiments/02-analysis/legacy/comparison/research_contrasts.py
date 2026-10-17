"""Calculate descriptive paired contrasts from saved response observations."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

NAMES = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['NAMES']).NAMES
VARIANTS = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['VARIANTS']).VARIANTS
read_rows = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['read_rows']).read_rows
sha = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['sha']).sha


def build(source, output):
    source, output = Path(source), Path(output)
    rows = read_rows(source / 'rows.jsonl')
    selected = [row for row in rows if row['variant'] != 'ORIGINAL']
    keyed = {(r['case'], r['variant'], r['prompt_condition'], r['reasoning']): r for r in selected}
    if len(keyed) != len(selected):
        raise ValueError('DUPLICATE_CONDITION_KEY')
    cases = sorted({r['case'] for r in selected})
    contrasts, pairs = [], []
    for variant in VARIANTS[1:]:
        for reasoning in ('off', 'on'):
            changes = []
            for case in cases:
                p0 = keyed.get((case, variant, 'P0', reasoning))
                p1 = keyed.get((case, variant, 'P1', reasoning))
                if not p0 or not p1:
                    raise ValueError('PAIRED_CONDITION_MISSING')
                if p0['qc_sha256'] != p1['qc_sha256'] or p0['schema_sha256'] != p1['schema_sha256']:
                    raise ValueError('UNMATCHED_INPUT_OR_SCHEMA')
                observed = all(isinstance(p['response'], dict) and 'answer' in p['response']
                               and type(p['answer_is_null']) is bool for p in (p0, p1))
                row = {'case': case, 'variant': variant, 'reasoning': reasoning,
                       'observed': observed, 'p0_trial': p0['trial_id'], 'p1_trial': p1['trial_id'],
                       'p0_null': p0['answer_is_null'] if observed else None,
                       'p1_null': p1['answer_is_null'] if observed else None,
                       'p0_numeric': p0['signed_numeric_field'] is not None if observed else None,
                       'p1_numeric': p1['signed_numeric_field'] is not None if observed else None,
                       'delta': int(p1['answer_is_null']) - int(p0['answer_is_null']) if observed else None}
                pairs.append(row)
                changes.append(row)
            seen = [c for c in changes if c['observed']]
            n = len(changes)
            contrasts.append({'variant': variant, 'reasoning': reasoning, 'planned_pairs': n,
                'observed_pairs': len(seen), 'missing_pairs': n-len(seen),
                'p0_null': sum(c['p0_null'] for c in seen), 'p1_null': sum(c['p1_null'] for c in seen),
                'numeric_to_null': sum(c['p0_numeric'] and c['p1_null'] for c in seen),
                'null_to_numeric': sum(c['p0_null'] and c['p1_numeric'] for c in seen),
                'null_change_percentage_points': 100*sum(c['delta'] for c in seen)/n if len(seen)==n else None})
    per_case = defaultdict(dict)
    for p in pairs:
        per_case[(p['case'], p['variant'])][p['reasoning']] = p['delta']
    interactions = []
    for variant in VARIANTS[1:]:
        values = [v['on']-v['off'] for (case, kind),v in per_case.items()
                  if kind == variant and v.get('on') is not None and v.get('off') is not None]
        interactions.append({'variant': variant, 'originals': len(cases), 'observed_originals': len(values),
            'instruction_by_reasoning_null_interaction_pp': 100*sum(values)/len(cases) if len(values)==len(cases) else None})
    report = {'kind': 'DESCRIPTIVE_PAIRED_CONTRASTS', 'source_run': rows[0]['run_id'],
              'source_sha256': sha(source / 'rows.jsonl'), 'new_model_calls': 0,
              'source_contracts': dict(Counter(row.get('schema_title') or 'UNKNOWN' for row in rows)),
              'analysis_unit': 'ORIGINAL_CASE_CLUSTER_WITH_SEVEN_RELATED_VARIANTS',
              'interpretation': 'Null-field behavior under changed conditions; not semantic abstention accuracy or repeated-condition stability.',
              'planned_originals': len(cases), 'planned_variant_pairs_per_reasoning': len(cases)*7,
              'contrasts': contrasts, 'interactions': interactions,
              'hypothesis_test': 'NOT_PERFORMED_EXPLORATORY_NONRANDOM_DEVELOPMENT_COHORT'}
    output.mkdir(parents=True,exist_ok=True)
    (output/'contrasts.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'paired-observations.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in pairs))
    contracts = ', '.join(f'`{title}` {count}entries' for title, count in sorted(report['source_contracts'].items()))
    lines=['# Comparison of the prompt reference conditions of the stored Luna response','',
           f"Running `{report['source_run']}` · The original {report['planned_originals']}items · Response format {contracts}.The actual input is the execution and format recorded in rows.jsonl. This analysis does not perform new model calls or mean correct answering.",
           '', 'The effect of the guidance varies according to the logic setting.', '',
           'The same primitive variable-reference conditions connect P0 and P1. Observe the difference when the numerical field changes to null, and not fill in the appropriate notation. The form failure response is also included in the original denominator. Both the answers record the pair of observed and the unobserved pair in JSON, and if the pair of the type-reference schematics are not observed, the change rate is the same as the change rate. 0And that leaves us with a negative assessment.', '',
           'This is the first time that the number of digits is zero.',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for c in contrasts:
        delta=c['null_change_percentage_points']
        lines.append(f"|{NAMES[c['variant']]}|{c['reasoning']}|{c['planned_pairs']}|{c['p0_null']}|{c['p1_null']}|{c['numeric_to_null']}|{c['null_to_numeric']}|{delta:.1f}|" if delta is not None else f"|{NAMES[c['variant']]}|{c['reasoning']}|{c['planned_pairs']}I\x27m not going to say anything about the whole thing.")
    lines += ['', 'The difference in on-off effect of the internal effect is %p','|---|---:|---:|']
    for i in interactions:
        v=i['instruction_by_reasoning_null_interaction_pp']
        lines.append(f"|{NAMES[i['variant']]}|{i['originals']}|{v:.1f}|" if v is not None else f"|{NAMES[i['variant']]}|{i['originals']}| Not evaluated |")
    lines += ['', '#### interpretation and the next step', '',
      f"- **Adopted amendments:** We\x27re going to look at the guidance effects separately by the inference conditions, and we\x27re going into the differences between the two effects. {len(cases)}It\x27s technical statistics in the original, and it doesn\x27t confirm the effectiveness of recruitment or statistical relevance.",
      '- **Adopted:** We separate VALUE/SOURCE/RELATION from EA to see if the change in response to a collision and the change in deletion of essential information are the same direction.',
      '- **The reservation:** To claim null augmentation as an improvement in user intent response requires a review of the actual recovery potential of deleted information, in contrast to normal problem P1.',
      f"- **- What is it?** 7The set of analytical and subsequent uncertainty calculations is the set of independent source items that measure variation and conditional response. {len(cases)}items.",
      '', 'I put the paper on the plate and the rest of the verification.', '',
      'The information you need is a presentation of a sign or a picture.', '|---|---|---|',
      'The type of failure of the contract, the type of failure, the type and the type of performance of the contract.',
      'Internal x inference x variation x variation of the corresponding table and the primitive transition recording of the inter-process comparison is limited to a common observation pair of the same input; normal P1 additional contrast is also designated as the',
      'After the source is added, this null comparison table has no parent link verification.',
      'The current condition stability is not included in the P0/P1 comparison of a single collection, so check the actual byte model of the two collections for the same star repeat analysis.',
      'A1 is a model of finance versus a model of base.00Whether it is feasible and whether the time data and the financing model should be answered directly',
      '', 'The primitive P1 contrast addition is a candidate to verify excessive e-books, and the same condition repeats are a candidate for variability. It is not treated as if it were already included in this analysis, and new calls require no readiness, output, and cost records.',
      '', '## Generalization and development bias', '',
      f'So this comparison is {len(cases)}The source code is not considered a random sampling of the same sample. If you see the results of the same sampling and then revise the instruction-response format and then measure it again, the implementation differences are observations in the development material. If you change the instruction, form, and re-up policy together, they are not separated into any single effect. The final verification test of the paper should be separated into groups that have not yet been read after setting the criteria. The case or indicator selected now is not represented as a pre-registered indicator.', '']
    (output/'analysis.md').write_text('\n'.join(lines))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=build(args.source,args.output)
    print(json.dumps({'originals':result['planned_originals'],'paired_rows':sum(x['planned_pairs'] for x in result['contrasts']),'new_model_calls':0}))
