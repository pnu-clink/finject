"""Export current prompt previews from saved requests; never call a model."""
import argparse
import json
from pathlib import Path
FILES = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['FILES']).FILES
describe_prompt = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['describe_prompt']).describe_prompt
from finarch.dataset.shared.review.audit_prompts import FILES as AUDIT_FILES, describe_prompt as describe_audit_prompt
from finarch.shared.providers.cli import prepare_instruction
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.validation import validate

README = '''# {title} · Verify before calling

State: PREVIEW_ONLY. Call the actual model 0Chapter: No change in the existing text, appeal or judgment.

In order of reading:
1. `summary.json`: Type file; description and verified condition list.
2. `prompt-previews/`: Current instructions and stored problem inputs combined with transmission **The scheduled** Professional, responsive scheme.
3. `checks.log`: Local selection; CLI boundary; presence editing; viewer inspection record.

Viewer: http://127.0.0.1:8893/?run={run}&case={case}&tab=dtt
Select the type 5The next day `{button}`I'm reading the current instructions.
The prompt input popup you used is the past record of the existing correction or judgment.
If you edit the current file, the current instruction pop-up changes, but the same as in this preview copy.

We've only done a formatting and linking test, and the actual production quality and cost time of the new guidelines are underestimated.
The model, the reference setting, the auto-review, the source editing range hasn't changed with this change.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--role', choices=('02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation'), default='02-generation.02-generate-text.realization')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    target = args.output/'prompt-previews'; target.mkdir()
    rows = []
    audit = args.role == 'shared.01-02.02-03.review-and-validation'
    files, selector = (AUDIT_FILES, describe_audit_prompt) if audit else (FILES, describe_prompt)
    pattern = '*/latest-audit.json' if audit else '*/latest-realization.json'
    for pointer in sorted((args.case/'05-text').glob(pattern)):
        stage = json.loads(pointer.read_text())['stage']
        source = args.case/stage/'01-input.json'
        request = json.loads(source.read_text())
        validate(args.role+'.request', request)
        instruction, definition = prepare_instruction(args.role, request)
        preview = {'status':'PREVIEW_ONLY', 'model_calls':0, 'source_request':str(source),
                   'prompt':instruction+'\nInput:\n'+json.dumps(request, ensure_ascii=False),
                   'prompt_selection':definition, 'response_schema':describe(args.role+'.response')}
        (target/(pointer.parent.name+'.json')).write_text(json.dumps(preview, ensure_ascii=False, indent=2)+'\n')
        rows.append({'label':pointer.parent.name, 'axis':request['axis'],
                     'slots':len(request['intent'].get('authorized_edit_slots',[])) if audit else len(request['edit_slots']),
                     'prompt_sha256':definition['sha256'], 'status':'INPUT_VALID_PREVIEW_ONLY'})
    summary = {'status':'PREVIEW_ONLY', 'model_calls':0, 'cases':rows,
               'role':args.role, 'types':[selector(axis) for axis in files]}
    (args.output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    (args.output/'README.md').write_text(README.format(run=args.case.parent.name, case=args.case.name,
        title='17\ubc88 \uc720\ud615\ubcc4 \uac80\uc99d \uc9c0\uce68' if audit else '16\ubc88 \uc720\ud615\ubcc4 \ubb38\uc7a5 \uc0dd\uc131 \uc9c0\uce68',
        button='\ud604\uc7ac \uc720\ud615 \uac80\uc99d \uc9c0\uce68 \ubcf4\uae30 · \ubbf8\ud638\ucd9c' if audit else '\ud604\uc7ac \uc720\ud615 \uc9c0\uce68 \ubcf4\uae30 · \ubbf8\ud638\ucd9c'))
    print(json.dumps({'status':'PREVIEW_ONLY', 'conditions':len(rows), 'types':len(files), 'model_calls':0}))


if __name__ == '__main__': main()
