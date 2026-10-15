"""Evidence-linked advice through the existing schema/transport boundary."""
from pathlib import Path
import json
from finarch.dataset.schemas.failure_interpretation import ROLE, TRANSLATION_ROLE
from finarch.shared.providers.cli import call

def validate_references(value, request):
    allowed = {a['id'] for a in request['artifacts']}
    for observation in value['observations']:
        if not set(observation['evidence_ids']) <= allowed:
            raise ValueError('UNKNOWN_ANALYSIS_EVIDENCE_ID')
    stages = ({'01-source','02-review','03-calculation','04-graph','05-verification','06-exception-handler','07-human-review'}
              if request['phase'] == 'preparation' else
              {'01-perturbation','02-generate-text','03-validation','04-exception-handler','05-human-review'})
    if value['target_step'] is not None and value['target_step'] not in stages:
        raise ValueError('INVALID_ANALYSIS_TARGET_STEP')

    plan = value['repair_plan']
    if not set(plan['evidence_ids']) <= allowed:
        raise ValueError('UNKNOWN_REPAIR_EVIDENCE_ID')
    editable = ({'02-review','03-calculation','04-graph','05-verification'} if request['phase']=='preparation'
                else {'01-perturbation','02-generate-text','03-validation'})
    if plan['action']=='HUMAN_REQUIRED':
        if plan['target_step'] is not None or not plan['required_information']:
            raise ValueError('HUMAN_PLAN_REQUIRES_INFORMATION')
    elif plan['target_step'] not in editable or plan['required_information']:
        raise ValueError('INVALID_REPAIR_TARGET')
    if plan['action']=='REVERIFY' and plan['target_step'] != ('05-verification' if request['phase']=='preparation' else '03-validation'):
        raise ValueError('INVALID_REVERIFY_TARGET')
    if value['target_step'] != plan['target_step']:
        raise ValueError('REPAIR_TARGET_MISMATCH')

def validate_translation(source, translated):
    fixed = lambda a: (a.get('repair_plan'), a['assessment'], a['target_step'], [(o['evidence_ids'], o['kind']) for o in a['observations']])
    if fixed(source) != fixed(translated) or len(source['limitations']) != len(translated['limitations']):
        raise ValueError('TRANSLATION_CHANGED_ANALYSIS_STRUCTURE')

def interpret(request, directory, config, profiles, *, model_call=None):
    """One analysis plus one optional display call; never retries or alters verdicts."""
    directory = Path(directory)
    model_call = model_call or call
    def invoke(role, payload, subdir):
        def save(name, value):
            path = directory/subdir/name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x') as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
        result = model_call(config, role, payload, save=save,
                            profile_id='luna-max-api', profiles_path=profiles)
        save('03-result.json', {'status':result.status,'reason':result.reason,'data':result.data})
        if result.status != 'PASS':
            raise ValueError(result.reason)
        return result.data
    analysis = invoke(ROLE, request, '01-LLM-interpret-failure')
    validate_references(analysis, request)
    output = {'status':'COMPLETED','analysis':analysis,'display_ko':None}
    try:
        translated = invoke(TRANSLATION_ROLE, {'source_language':'en','display_language':'ko','analysis':analysis},
                            '02-LLM-translate-display')
        validate_translation(analysis, translated)
        output['display_ko'] = translated
    except Exception as error:
        output.update(status='PARTIAL', translation_error=str(error))
    return output
