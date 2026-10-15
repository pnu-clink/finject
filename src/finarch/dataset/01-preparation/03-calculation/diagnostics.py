"""Preserve and sandbox-run POT before provenance acceptance; never promote it."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from finarch.dataset.schemas.llm import Fact, LegacyProgramResponse
from finarch.dataset.schemas.validation import check_json, parse_json_object
from finarch.dataset.shared.calculation.python_runtime import execute
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult

DIRECTORY = '03-calculation/03-preserve-response-and-code'


class ExecutionFields(LegacyProgramResponse):
    # Empty facts are supported by POT v4; execution reports its own limitations.
    facts: list[Fact]


def preserve_and_execute(value, context, save, save_text, *, question=""):
    """Save exact source, validate execution fields, then use the existing sandbox."""
    save('01-response.json', value)
    if isinstance(value.get('code'), str):
        save_text('02-program.py', value['code'])
    save('03-context.json', {'context': context, 'question': question})
    save_text('README.md', Path(__file__).with_name('diagnostics-readme.md').read_text())
    try:
        fields = {key: value[key] for key in ExecutionFields.model_fields if key in value}
        checked = ExecutionFields.model_validate(fields, strict=True).model_dump()
        program = {**checked, 'facts': {f['id']: {k: v for k, v in f.items() if k != 'id'}
                                      for f in checked['facts']}, 'context': context, 'question': question}
        result = execute(program, save=lambda name, data: save('04-execution/' + name, data))
    except Exception as error:
        result = StepResult('FAIL', str(error), {'error_type': type(error).__name__})
    save('04-execution/result.json', asdict(result))
    provenance = check_json('01-preparation.03-calculation.pot.response', json.dumps(value))
    save('05-response-check.json', provenance)
    save('06-summary.json', {'diagnostic_only': True, 'accepted': False,
                            'execution': asdict(result), 'response_check': provenance})
    return result, provenance


def replay(raw_response, context_file, output):
    """Read saved responses without an API call; require a new output directory."""
    value = parse_json_object(Path(raw_response).read_text())
    if 'text' in value:
        value = parse_json_object(value['text'])
    context = json.loads(Path(context_file).read_text())['context']
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    def save_text(name, text):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as stream:
            stream.write(text)
    def save(name, data):
        save_text(name, json.dumps(data, ensure_ascii=False, indent=2))
    return preserve_and_execute(value, context, save, save_text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--response', required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    execution, provenance = replay(args.response, args.context, args.output)
    print(json.dumps({'execution': asdict(execution), 'response_check': provenance}, ensure_ascii=False))
