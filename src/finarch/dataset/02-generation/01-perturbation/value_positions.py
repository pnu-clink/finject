variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""VP02: pair a fixed IC-VALUE statement before/after its anchored sentence."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
apply_patches = __import__('finarch.dataset.90-operations.staging', fromlist=['apply_patches']).apply_patches
from finarch.dataset.shared.calculation.python_graph import load_graph
check_base = __import__('finarch.dataset.02-generation.01-perturbation.source_plan', fromlist=['check_base']).check_base


def compose_pair(payload, sentence, pair_id):
    if payload.get('axis') != 'IC_VALUE' or payload.get('source_conditions'):
        raise ValueError('IC_VALUE_WITHOUT_SOURCE_CONDITIONS_REQUIRED')
    if not isinstance(sentence, str) or not sentence.strip() or sentence != sentence.strip():
        raise ValueError('NONEMPTY_TRIMMED_SENTENCE_REQUIRED')
    context = payload['original_context']; target = payload['target']
    a, b = target['original_span']; start, end = target['nearby_sentence']['span']
    if not (0 <= start <= a < b <= end <= len(context)) or context[a:b] != target['original_text'] or context[start:end] != target['nearby_sentence']['text']:
        raise ValueError('TARGET_SENTENCE_ANCHOR_MISMATCH')
    # [VP02.1] Trim only the anchor's outer whitespace; never alter original C.
    while start < end and context[start].isspace():
        start += 1
    while end > start and context[end-1].isspace():
        end -= 1
    pair = []
    separator = '\n' if '|' in context[start:end] else ' '
    for position, anchor, order in [('before', start, ['B', 'A']), ('after', end, ['A', 'B'])]:
        inserted = sentence + separator if position == 'before' else separator + sentence
        patch = {'start': anchor, 'end': anchor, 'before': '', 'text': inserted,
                 'segments': [{'kind': 'VALUE', 'text': inserted}],
                 'element_ids': payload['graph_binding']['original_node_ids'],
                 'purpose': 'Insert the same B claim ' + position + ' the target sentence'}
        edited = apply_patches(context, [patch])
        offset = anchor + (1 if position == 'after' else 0)
        target_offset = len(inserted) if position == 'before' else 0
        preview = {'axis': 'IC_VALUE', 'status': 'EDITORIAL_PREVIEW',
            'origin': 'Python placement of a supplied sentence; actual LLM provenance is attached by stage16',
            'final_text_status': 'NOT_RUN', 'semantic_status': 'NOT_EVALUATED', 'model_calls': 0,
            'pair_id': pair_id, 'perturb_position': position, 'claim_order': order,
            'perturb_sentence': sentence, 'perturb_sentence_span': [offset, offset + len(sentence)],
            'target_sentence': {'text': context[start:end], 'original_span': [start, end],
                                'preview_span': [start + target_offset, end + target_offset]},
            'original_context': context, 'preview_context': edited, 'question': payload['question'],
            'source_condition': None, 'patches': [patch], 'target': deepcopy(target),
            'conditional_answers': deepcopy(payload['conditional_answers']),
            'python': deepcopy(payload['python']), 'graph_binding': deepcopy(payload['graph_binding']),
            'next_steps': ['Review the before/after pair with the same inserted sentence, source context, and question.',
                           'Generate text, validate the response schema, and audit the final meaning.',
                           'Preserve pair_id, perturb_position, and claim_order as separate final metadata.']}
        if edited[:anchor] + edited[anchor + len(inserted):] != context:
            raise ValueError('ORIGINAL_CONTEXT_CHANGED')
        if edited[slice(*preview['target_sentence']['preview_span'])] != context[start:end]:
            raise ValueError('TARGET_SENTENCE_CHANGED')
        if edited[slice(*preview['perturb_sentence_span'])] != sentence:
            raise ValueError('PERTURB_SENTENCE_CHANGED')
        pair.append(preview)
    return pair


def first_case_sentence(payload):
    raise ValueError('MANUAL_TEXT_PREVIEW_REMOVED: use an actual LLM response')


def create(case_dir, base_label='IC_VALUE_01'):
    if Path(base_label).name != base_label or base_label in ('.', '..'):
        raise ValueError('INVALID_BASE_LABEL')
    case = Path(case_dir).resolve(); family = '03-graph/value-position-pair'
    if (case/family).exists():
        raise ValueError('POSITION_PAIR_ALREADY_EXISTS')
    ctx = RunContext.resume(case, {}, case.name)
    with ctx.trace.activate(), ctx.trace.span('value_positions.create', stage='03-graph', step='VP02', role='python') as outcome:
        ctx.save(family+'/01-input.json', {'base_label': base_label, 'positions': ['before', 'after'], 'model_calls': 0})
        try:
            load_graph(case)
            root = f'{variant_root(base_label)}'; ref = root+'/plan.json'
            read = lambda p: json.loads((case/p).read_text())
            base = read(ref); check_base(base)
            payload = read(root+'/06-generation-input.json'); sample = read('00-data-preparation/01-select-input/01-input.json')
            program = read('02-calculation/02-prepare-code/03-program.json')
            if payload['original_context'] != sample['context'] or payload['question'] != sample['question'] or payload['python']['code'] != program['code']:
                raise ValueError('BASE_REALIZATION_INPUT_CHANGED')
            if [payload['claims'][s]['value'] for s in ['A', 'B']] != base['value_pair'] or payload['conditional_answers'] != base['answers']:
                raise ValueError('BASE_CLAIMS_OR_ANSWERS_CHANGED')
            target = payload['target']; evidence = base['original_evidence']
            if (target['fact_id'] != base['fact_id'] or target['original_span'] != evidence['span']
                    or target['original_text'] != evidence['text'] or target['unit'] != evidence['unit']):
                raise ValueError('BASE_TARGET_CHANGED')
            index = case/'04-perturbation/05-list-candidates/03-result.json'; previous = json.loads(index.read_text())
            if not any(v['label'] == base_label and v['axis'] == 'IC_VALUE' for v in previous):
                raise ValueError('ACTIVE_BASE_VARIANT_REQUIRED')
            labels = [base_label+'_BEFORE', base_label+'_AFTER']
            if any(v['label'] in labels for v in previous):
                raise ValueError('POSITION_LABEL_ALREADY_EXISTS')
            pair_id = f'{case.parent.name}:{case.name}:{base_label}:position-v1'
            previews = compose_pair(payload, first_case_sentence(payload), pair_id)
            preserved = {p: hashlib.sha256((case/p).read_bytes()).hexdigest() for p in
                         [ref, root+'/06-generation-input.json', root+'/05-text-input-preview.json',
                          '00-data-preparation/01-select-input/01-input.json', '02-calculation/02-prepare-code/03-program.json', '03-graph/04-save-graph/01-graph.json']}
            variants = []
            for label, preview in zip(labels, previews):
                path = variant_root(label); pos = preview['perturb_position']
                metadata = {k: preview[k] for k in ['pair_id', 'perturb_position', 'claim_order']}
                plan = {'axis': 'IC_VALUE', 'base_plan_ref': ref, 'base_plan_sha256': preserved[ref],
                        **metadata, 'perturb_sentence': preview['perturb_sentence'],
                        'target_sentence': preview['target_sentence'],
                        'semantic_status': 'NOT_EVALUATED', 'final_text_status': 'NOT_RUN', 'model_calls': 0}
                handoff = deepcopy(payload)
                handoff.update(metadata, perturb_sentence=preview['perturb_sentence'],
                               placement={'anchor': preview['patches'][0]['start'], 'target_sentence': preview['target_sentence']})
                handoff['editing_rules'] += [f'Place the fixed B statement {pos} the anchored A sentence.',
                    'Keep the paired statement identical; change placement only. A remains the original claim and B the added claim even when B comes first.',
                    'The pair identifier and position are metadata, not text for the model to answer from.']
                ctx.save(path+'/plan.json', plan)
                ctx.save(path+'/05-text-input-preview.json', preview)
                ctx.save_text(path+'/context-preview.txt', preview['preview_context'])
                ctx.save(path+'/06-generation-input.json', handoff)
                ctx.save(path+'/realization-response-schema.json', read(root+'/realization-response-schema.json'))
                ctx.save_text(path+'/README.md', f'''# IC-VALUE · 대상 문장 {'앞' if pos == 'before' else '뒤'}

읽는 순서: plan.json → text-preview-v2.json → context-preview.txt → realization-input.json → realization-response-schema.json.
동일 B 문장을 대상 A 문장의 {pos}에 삽입한 사본입니다. 원문·질문·모든 원래 수치와 A/B 계산 결과를 보존합니다. 그래프는 {ref}를 참조하므로 두 조건에서 같습니다.
pair_id={pair_id}, perturb_position={pos}, claim_order={preview['claim_order']}를 저장합니다. A/B는 원래/추가 주장을 뜻하며 앞/뒤에 따라 이름을 바꾸지 않습니다. 최종 데이터에도 이 메타데이터를 전달할 계약이고, 모델 풀이용 context/question에는 넣지 않습니다.

공통 viewer에서 이 실행 → {case.name} → IC-VALUE · {'앞' if pos == 'before' else '뒤'} → 5 문장과 답변을 선택합니다. 초록색 B 문장의 위치가 바뀌며, 4번 계산 그래프는 같은 A/B 결과를 보여줍니다. 8 전체 기록에서 모든 파일을 확인합니다.
원본 IC-VALUE_01 자료와 IC-SOURCE·IC-RELATION·EA는 보존합니다. 문장은 검토용 초안이며 LLM 호출·최종 의미 검사·모델 선호 실험은 미실행입니다. 실제 호출 때 준비된 프롬프트와 응답 스키마를 전달하고 반환 응답을 검사하는 연결은 16번입니다.
이 안내는 저장 함수의 템플릿에서 생성합니다. events.jsonl에 VP02 시작·산출물·종료, value-position-pair에 원본 해시·쌍 검사·실패 및 이전 후보 목록을 보관합니다. 자동 재시도는 없습니다.
''')
                variants.append({'label': label, 'axis': 'IC_VALUE', **metadata, 'status': 'NOT_EVALUATED',
                                 'calculation_status': 'PASS', 'plan': plan, 'reason': 'Before/after placement copies; final text and meaning not evaluated'})
            checks = {'identical_perturb_sentence': previews[0]['perturb_sentence'] == previews[1]['perturb_sentence'],
                      'same_question': all(p['question'] == sample['question'] for p in previews),
                      'same_answers_and_code': all(p['conditional_answers'] == base['answers'] and p['python']['code'] == program['code'] for p in previews),
                      'distinct_contexts': previews[0]['preview_context'] != previews[1]['preview_context'],
                      'original_files_preserved': all(hashlib.sha256((case/p).read_bytes()).hexdigest() == h for p, h in preserved.items())}
            if not all(checks.values()):
                raise ValueError('POSITION_PAIR_CHECK_FAILED')
            # [VP02.2] Replace only the base display entry; preserve its artifacts and source references.
            ctx.save(family+'/previous-variants.json', previous)
            active = []
            for v in previous:
                active.extend(variants if v['label'] == base_label else [v])
            ctx.save(family+'/validation.json', {'status': 'PASS', 'checks': checks, 'pair_id': pair_id,
                'variants': labels, 'preserved_inputs_sha256': preserved, 'scope': 'editorial placement pair only', 'model_calls': 0})
            temporary = index.with_suffix('.tmp')
            temporary.write_text(json.dumps(active, ensure_ascii=False, indent=2)+'\n'); temporary.replace(index)
            ctx.trace.artifact('04-perturbation/05-list-candidates/03-result.json'); outcome.update(status='PASS', reason='IC_VALUE_POSITION_PAIR_SAVED')
            return {'status': 'PASS', 'variants': labels, 'pair_id': pair_id, 'model_calls': 0}
        except Exception as error:
            ctx.save(family+'/03-result/failure.json', {'status': 'FAIL', 'reason': str(error)})
            outcome.update(status='FAIL', reason=str(error)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('case_dir')
    args = parser.parse_args(); print(json.dumps(create(args.case_dir), ensure_ascii=False))
