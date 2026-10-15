"""Explicit, immutable-input first-repeat screening. No provider calls."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from finarch.dataset.schemas.response_screen import ScreenRecord, ScreenReport
from finarch.dataset.shared.review.quality_scope import Snapshot

PROJECT = (Path(__file__).resolve().parent / '../../../..').resolve()
CUES = {
    'conflict': r'conflict\w*|contradict\w*|inconsisten\w*|discrepanc\w*|ambig\w*|different values',
    'reject': r'missing|insufficient|not provided|not specified|cannot|can\W*t|unable|impossible|does not (?:provide|specify)|not enough',
    'condition': r'\bif\b|assum\w*|depending|provided that|under the|however',
}
BARE = re.compile(r'\s*(?P<currency>[$€£])?(?P<number>[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?P<percent>%)?\s*')


def execution(raw, result):
    """Raw length takes precedence over null content, parse errors and result status."""
    if isinstance(raw, dict):
        try:
            choice = raw['choices'][0]
            finish = choice['finish_reason']
        except (KeyError, IndexError, TypeError):
            return 'SCHEMA_ERROR', 'RAW_ENVELOPE_INVALID', None, None, None
        content = choice.get('message', {}).get('content') if isinstance(choice.get('message'), dict) else None
        if finish == 'length':
            return 'TRUNCATED', 'RAW_FINISH_LENGTH', finish, content is None, None
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict) or set(parsed) != {'answer'} or not isinstance(parsed['answer'], str):
                raise ValueError('answer schema')
            if finish != 'stop':
                raise ValueError('unsupported finish')
        except (TypeError, ValueError):
            return 'SCHEMA_ERROR', 'RAW_ANSWER_OR_FINISH_INVALID', finish, content is None, None
        if result is None:
            return 'MISSING', 'RESULT_MISSING', finish, False, None
        if not isinstance(result, dict) or result.get('status') != 'COMPLETED' or result.get('answer') != parsed['answer']:
            return 'SCHEMA_ERROR', 'RAW_RESULT_MISMATCH', finish, False, None
        return 'COMPLETE', 'RAW_AND_RESULT_AGREE', finish, False, parsed['answer']
    if raw is not None:
        return 'SCHEMA_ERROR', 'RAW_JSON_INVALID', None, None, None
    error = result.get('error', '') if isinstance(result, dict) else ''
    if isinstance(error, str) and re.search(r'timeout|timed out|connection|connecterror|HTTPStatusError|server disconnected|network|http.*\b[45]\d\d\b', error, re.I):
        return 'TRANSPORT_ERROR', 'EXPLICIT_TRANSPORT_ERROR_WITHOUT_RAW', None, None, None
    return 'MISSING', 'RAW_MISSING_NO_TRANSPORT_EVIDENCE', None, None, None


def numbers(answer):
    """Only the entire bare answer is accepted; explanatory/conditional grammar is deferred."""
    match = BARE.fullmatch(answer)
    if not match or (match['currency'] and match['percent']):
        return []
    unit = {'$': 'USD', '€': 'EUR', '£': 'GBP'}.get(match['currency'])
    if match['percent']:
        unit = 'percent'
    value = match['number'].replace(',', '')
    return [{'quote': answer, 'start': 0, 'end': len(answer), 'value': value, 'unit': unit,
             'decimal_places': len(value.split('.')[1]) if '.' in value else 0, 'method': 'BARE_NUMBER'}]


def compare(candidates, A=None, B=None, unit=None, decimal_places=None):
    result = {'A': A, 'B': B, 'unit': unit, 'decimal_places': decimal_places,
              'match': 'UNRESOLVED', 'reason': 'ANSWER_UNIT_PRECISION_OR_REFERENCE_UNRESOLVED'}
    if len(candidates) != 1 or A is None or B is None or unit is None or decimal_places is None:
        return result
    number = candidates[0]
    if number['unit'] != unit or number['decimal_places'] != decimal_places:
        return result
    try:
        values = [Decimal(v) for v in (number['value'], A, B)]
        if not all(v.is_finite() for v in values):
            return result
        a, b = values[0] == values[1], values[0] == values[2]
    except InvalidOperation:
        return result
    result.update(match='BOTH' if a and b else 'A' if a else 'B' if b else 'NEITHER',
                  reason='EXACT_NUMBER_UNIT_AND_EXPLICIT_PRECISION_ONLY_NOT_SEMANTIC_CORRECTNESS')
    return result


def screen(item, raw, result, generation, quality, refs, skip=()):
    state, reason, finish, null, answer = execution(raw, result)
    skip = list(skip)
    if isinstance(result, dict) and (result.get('id') != item['id'] or result.get('repeat') != 1):
        skip.append('RESULT_ID_OR_REPEAT_MISMATCH')
        if state == 'COMPLETE':
            state, reason, answer = 'SCHEMA_ERROR', 'RESULT_ID_OR_REPEAT_MISMATCH', None
    plan = (generation or {}).get('plan', {})
    graph = plan.get('original_graph') or {}
    output = next((n for n in graph.get('nodes', []) if n['id'] == graph.get('output')), {})
    A = output.get('computed')
    B = (plan.get('execution') or {}).get('exact_value')
    # No unit inference from unrelated input facts or currency words in the context.
    unit = output.get('unit')
    precision = output.get('decimal_places')
    qc_match = (generation or {}).get('observation') == {k: item[k] for k in ('question', 'context')}
    if not qc_match:
        skip.append('GENERATION_QC_UNVERIFIED')
        A = B = unit = precision = None
    cues = {k: [{'quote': m.group(), 'start': m.start(), 'end': m.end()} for m in re.finditer(v, answer, re.I)]
            for k, v in CUES.items()} if answer is not None else None
    numeric = numbers(answer) if answer is not None else None
    candidates = ([k.upper() + '_CUE' for k, v in cues.items() if v] + (['BARE_NUMERIC_ANSWER'] if numeric else [])) if cues is not None else None
    recovery = quality.get('bounded_recovery_status') if qc_match else None
    validity = {'perturbation': 'INVALID' if recovery == 'RECOVERABLE' else 'UNKNOWN' if quality.get('axis') == 'EA' else 'NOT_REVIEWED',
                'reason': 'HASH_LINKED_QI01_RECOVERY_WITNESS' if recovery == 'RECOVERABLE' else 'NO_VALIDITY_INFERENCE_FROM_ANSWER_OR_APPROVAL'}
    comparison = compare(numeric or [], A, B, unit, precision)
    if comparison['match'] == 'UNRESOLVED':
        skip.append(comparison['reason'])
    return ScreenRecord(id=item['id'], case=item['id'].split('/')[0], variant=item['id'].split('/')[1],
        execution=state, execution_reason=reason, raw_finish_reason=finish, raw_content_is_null=null,
        answer=answer, cues=cues, behavior_candidates=candidates,
        semantic_status='NOT_REVIEWED' if state == 'COMPLETE' else 'NOT_EVALUATED', numeric_candidates=numeric,
        comparison=comparison, validity=validity, references=refs, skip_reasons=skip)


class InputSnapshot(Snapshot):
    def capture(self, path, *, parse=True):
        path = Path(path).resolve()
        relative = path.relative_to(self.project).as_posix()
        if not path.is_file():
            self.missing.add(relative)
            return None
        raw = path.read_bytes()
        ref = {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}
        if relative in self.references and self.references[relative] != ref:
            raise ValueError('SNAPSHOT_CHANGED:' + relative)
        self.references[relative] = ref
        if not parse:
            return raw
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return 'INVALID_JSON'


def build(source, output, quality_root, *, project=PROJECT, expected=624, samples=None):
    source, output, quality_root, project = [Path(p).resolve() for p in (source, output, quality_root, project)]
    for protected in (source, quality_root):
        if output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError('OUTPUT_MUST_BE_NEW_SEPARATE_RUN')
    output.relative_to(project)
    if output.exists():
        raise FileExistsError(output)
    snapshot = InputSnapshot(project)
    output.mkdir(parents=True)
    def save(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    def event(phase, **extra):
        with (output / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'phase': phase, 'step': 'QI06', 'model_calls': 0, **extra}) + '\n')
    event('START')
    try:
        experiment = source / '03-experiment/qwen-8b'
        dataset_path = experiment / 'dataset.json'
        frozen = snapshot.capture(dataset_path)
        if not isinstance(frozen, list) or len(frozen) != expected or len({r['id'] for r in frozen}) != expected:
            raise ValueError('FROZEN_DENOMINATOR_OR_ID_MISMATCH')
        quality_path = quality_root / 'quality_scope.json'
        quality_report = snapshot.capture(quality_path)
        quality = {r['id']: r for r in quality_report['records']}
        # Protect every existing quality-v1 artifact and every legacy first-review artifact.
        for p in sorted(quality_root.rglob('*')):
            if p.is_file(): snapshot.capture(p, parse=False)
        for name in ('first-review.json', 'first-review.csv', 'FIRST-REVIEW.md'):
            snapshot.capture(experiment / name, parse=False)
        records = []
        for n, item in enumerate(frozen, 1):
            root = experiment / '01-repeat' / f'{n:04d}'
            values = {k: snapshot.capture(root / filename) for k, filename in
                      [('raw', 'response.json'), ('result', 'result.json'), ('request', 'request.json')]}
            refs = {k: snapshot.ref(root / filename) for k, filename in
                    [('raw', 'response.json'), ('result', 'result.json'), ('request', 'request.json')] if snapshot.ref(root / filename)}
            refs['frozen_dataset'] = snapshot.ref(dataset_path)
            refs['quality_scope'] = snapshot.ref(quality_path)
            q = quality.get(item['id'], {})
            genref = q.get('references', {}).get('generation')
            generation = None
            skip = []
            if genref:
                generation = snapshot.capture(project / genref['path'])
                if snapshot.ref(project / genref['path']) != genref:
                    skip.append('GENERATION_HASH_MISMATCH')
                    generation = None
                else: refs['generation'] = genref
            recoveryref = q.get('references', {}).get('bounded_recovery')
            q = dict(q)
            if recoveryref:
                witness = snapshot.capture(project / recoveryref['path'])
                if snapshot.ref(project / recoveryref['path']) != recoveryref or not isinstance(witness, dict) or witness.get('status') != 'RECOVERABLE':
                    q['bounded_recovery_status'] = None
                    skip.append('RECOVERY_EVIDENCE_UNVERIFIED')
                else: refs['bounded_recovery'] = recoveryref
            else: q['bounded_recovery_status'] = None
            request = values['request']
            expected_user = 'Question:\n' + item['question'] + '\n\nContext:\n' + item['context']
            if not isinstance(request, dict) or not any(m.get('role') == 'user' and m.get('content') == expected_user for m in request.get('messages', [])):
                skip.append('REQUEST_FROZEN_QC_MISMATCH')
                generation = None
            records.append(screen(item, values['raw'], values['result'], generation, q, refs, skip))
        manual = snapshot.capture(samples) if samples else []
        if len(manual) > 10:
            raise ValueError('MANUAL_SAMPLE_LIMIT')
        if len({m['id'] for m in manual}) != len(manual):
            raise ValueError('DUPLICATE_MANUAL_SAMPLE')
        for m in manual:
            r = next(r for r in records if r.id == m['id'])
            if m['source'] != r.references['raw'].model_dump():
                raise ValueError('MANUAL_SAMPLE_HASH_MISMATCH')
            raw = snapshot.capture(project / m['source']['path'])
            content = raw['choices'][0]['message']['content']
            if m['quote'] and m['quote'] not in (r.answer or content or ''):
                raise ValueError('MANUAL_SAMPLE_QUOTE_MISMATCH')
        counts = dict(Counter(r.execution for r in records))
        summary = {'records': len(records), **{k: counts.get(k, 0) for k in ('COMPLETE','TRUNCATED','TRANSPORT_ERROR','SCHEMA_ERROR','MISSING')},
            'length_null_content': sum(r.execution == 'TRUNCATED' and r.raw_content_is_null is True for r in records),
            **{k + '_cue': sum(bool(r.cues and r.cues[k]) for r in records) for k in CUES},
            'coexisting_cues': sum(bool(r.cues) and sum(bool(v) for v in r.cues.values()) > 1 for r in records),
            'bare_numeric': sum(bool(r.numeric_candidates) for r in records),
            'ab_resolved': sum(r.comparison.match != 'UNRESOLVED' for r in records),
            'pair_analysis_eligible': 0, 'semantic_adjudicated': 0, 'manual_samples': len(manual),
            'known_invalid_perturbations': sum(r.validity.perturbation == 'INVALID' for r in records)}
        report = ScreenReport(run_id=output.name, source_run=source.name, created_at=datetime.now(timezone.utc).isoformat(),
            records=records, summary=summary, manual_samples=manual, related_reports={'QI05': snapshot.ref(quality_path), **quality_report.get('related_reports', {})},
            limitations=['Cue counts overlap; complete-response denominator is COMPLETE, execution denominator is records.',
                'Only bare numeric answers are extracted. Explicit final/conditional prose, multiple answers and generic semantic parsing are deferred.',
                'Missing explicit output unit or precision leaves A/B UNRESOLVED; no inference from gold, input units or approval.',
                'Pair analysis is not implemented; eligible pairs are not established (0), not evidence of no valid pairs.',
                'Manual samples check execution/cues/extraction only; semantic adjudicated count remains zero.',
                'Temperature-zero repetitions are not independent models. This report covers repeat 1 only.',
                'Truncated content and reasoning are never used as semantic answers.'])
        snapshot.verify()
        save('response_screen.json', report.model_dump())
        save('sidecar-schema.json', ScreenReport.model_json_schema())
        save('summary.json', {'workflow': 'response_screen', 'status': 'COMPLETE', **summary, 'model_calls': 0})
        save('manifest.json', {'snapshot_status': 'UNCHANGED', 'inputs': list(snapshot.references.values()), 'missing': sorted(snapshot.missing)})
        (output / 'README.md').write_text(Path(__file__).with_name('response-screen-readme-template.md').read_text().format(run_id=output.name, **summary))
        event('END', status='COMPLETE', **summary)
        return report
    except Exception as error:
        status = 'SNAPSHOT_CHANGED' if str(error).startswith('SNAPSHOT_CHANGED') else 'FAIL'
        save('failure.json', {'status': status, 'reason': str(error)})
        event('FAIL', status=status, reason=str(error))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--quality-root', required=True)
    parser.add_argument('--samples')
    args = parser.parse_args()
    report = build(args.source, args.output, args.quality_root, samples=args.samples)
    print(json.dumps(report.summary))

if __name__ == '__main__':
    main()
