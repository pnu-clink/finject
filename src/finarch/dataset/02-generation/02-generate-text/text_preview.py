variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""Save an explicitly editorial preview for the verified first service-fee case."""
import json
import hashlib
from pathlib import Path
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
apply_patches = __import__('finarch.dataset.90-operations.staging', fromlist=['apply_patches']).apply_patches


def compose_relation(sample, plan, original_graph, programs):
    # [TP02] docs/02-architecture.md#TP02 — show the saved relation draft, not a generated response.
    raise ValueError('MANUAL_TEXT_PREVIEW_REMOVED: use an actual LLM response')


RELATION_PREVIEW_README = '''# IC-RELATION edit the phrase preview

Read in the following order: Plan-v2.json of active candidates (if not plan.json) → text-preview-v2. json → B/program.json and B/graph.json.

text-preview-v2.json is a review copy inserted into the location of the stored relationship phrase. It preserves the original, query, and observation amount, and records additional frameworks and code-graph connections. Compare the relationship application B to the original A.

This is the execution and case from the common viewer → IC-RELATION → 5 You select the sentence and the answer. In the font/minuscript comparison right below the font/relationship application, the additional sentence is green. The conditional calculation value is not the answer of a separate model.

Relationship and phrasing drafts were written by agents. 16And the final sentence is the creation of the 17The bar means check is a mismatch. It doesn't mean the whole job didn't use the LLM.2 And we have records of processing and production.
'''


def save_relation(case_dir, label='IC_RELATION_01'):
    case = Path(case_dir); root = f'{variant_root(label)}'
    ctx = RunContext.resume(case, {}, case.name)
    with ctx.trace.activate(), ctx.trace.span('text_preview.relation', stage='03-graph', step='TP02') as outcome:
        variants = json.loads((case/'04-perturbation/05-list-candidates/03-result.json').read_text())
        plan = next(v['plan'] for v in variants if v['label'] == label)
        for name, expected in plan['preserved_inputs_sha256'].items():
            if hashlib.sha256((case/name).read_bytes()).hexdigest() != expected:
                raise ValueError('RELATION_PREVIEW_INPUT_CHANGED:' + name)
        sample = json.loads((case/'00-data-preparation/01-select-input/01-input.json').read_text())
        graph = json.loads((case/'03-graph/04-save-graph/01-graph.json').read_text())
        programs = {key: json.loads((case/path).read_text())['code'] for key, path in
                    [('A', '02-calculation/02-prepare-code/03-program.json'), ('B', root+'/B/program.json')]}
        preview = compose_relation(sample, plan, graph, programs)
        ctx.save(root+'/05-text-input-preview.json', preview)
        ctx.save_text(root+'/05-text-input-preview.md', RELATION_PREVIEW_README)
        outcome.update(status='PASS', reason='RELATION_EDITORIAL_PREVIEW_SAVED')
        return preview


def compose(payload):
    # [TP01] docs/02-architecture.md#TP01 — preview only, never a model result.
    raise ValueError('MANUAL_TEXT_PREVIEW_REMOVED: use an actual LLM response')


def target_ids(payload):
    return payload['graph_binding']['original_node_ids']


def compose_ea(sample, plan, program):
    raise ValueError('MANUAL_TEXT_PREVIEW_REMOVED: use an actual LLM response')


def save_ea(case_dir, label='EA_01'):
    case = Path(case_dir); root = f'{variant_root(label)}'
    if Path(label).name != label or label in ('.', '..'):
        raise ValueError('INVALID_LABEL')
    ctx = RunContext.resume(case, {}, case.name)
    with ctx.trace.activate(), ctx.trace.span('text_preview.ea', stage='03-graph', step='TP03') as outcome:
        plan = json.loads((case/root/'plan.json').read_text())
        for name, expected in plan['preserved_inputs_sha256'].items():
            if hashlib.sha256((case/name).read_bytes()).hexdigest() != expected:
                raise ValueError('EA_PREVIEW_INPUT_CHANGED:' + name)
        sample = json.loads((case/'00-data-preparation/01-select-input/01-input.json').read_text())
        program = json.loads((case/'02-calculation/02-prepare-code/03-program.json').read_text())
        preview = compose_ea(sample, plan, program)
        ctx.save(root+'/05-text-input-preview.json', preview)
        ctx.save_text(root+'/context-tagged.txt', preview['intermediate']['context'])
        ctx.save_text(root+'/context-preview-v2.txt', preview['preview_context'])
        ctx.save_text(root+'/05-text-input-preview.md', '''# EA · Delete the tag to a natural sentence

The following is the order of reading: plan.json → text-preview-v2.json → context-tagged.txt → context-preview -v2.txt.
The middle text is saved in the plan.json, where the input amount is located, and then the deleted tag is used for the creation. The next draft of the revision is a copy that leaves the subject revenue item and removes the expression and the number that introduces the amount. The tag-delete guide is not put in the modified copy. The original file is saved. The other three amounts: query-calculation is the same, and the deleted position and the graph link is in text-preview-v2.json. 80,000 Removal and sale fees 45,000 It supports deletion, not the way to delete the derivative intermediate.

In common viewer, this run → test-0001 → EA → 5 Select the sentence and answer, and compare one sentence with the whole sentence → tag, and then compare it with the whole phrase → the whole sentence. 2In the bar, the entire task phrase, including the tag, 3In the bar, you'll only see the color of the changed phrase. 3I'm just copying the phrase. 8 You can read the entire file.

It is a preview where the agent has applied the first case editing set to Python, and there are no additional LLM calls for case creation. The preview file cache is not final text approval, validation checks, independent model responses completed. The lack of evidence indicating the results is the current state of the computational pathway.

This README is automatically generated from the template of the save function.3The "Delete Aesthetic" in the front graph guide is the original and final output criteria, and only this copy has deleted editing.
''')
        outcome.update(status='PASS', reason='EA_DELETION_PREVIEW_SAVED_NOT_FINAL_TEXT')
        return preview


def save(case_dir,label):
    case=Path(case_dir);root=f'{variant_root(label)}'
    ctx=RunContext.resume(case,{},case.name)
    with ctx.trace.activate(),ctx.trace.span('text_preview.save',stage='03-graph',step='TP01-text-preview') as outcome:
        payload=json.loads((case/root/'realization-input.json').read_text())
        preview=compose(payload)
        ctx.save(root+'/05-text-input-preview.json',preview)
        ctx.save_text(root+'/05-text-input-preview.md','This file is an edited preview of the first fee clause. It\'s not the final text or model answer created by the LLM. It preserves the value arguments in text-preview-v2.json, source A, source B, and the insertion location, query, source, microblog, graph connection. Common Viewer 5Compare it to the bar.\n')
        outcome.update(status='PASS',reason='EDITORIAL_PREVIEW_SAVED_NOT_FINAL_TEXT')
        return preview
