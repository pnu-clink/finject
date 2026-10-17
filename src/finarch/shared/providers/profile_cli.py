"""Run one schema-checked role using a named project Codex argv profile."""
import argparse
import json
import sys
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Also supports: .venv/bin/python src/finarch/shared/providers/profile_cli.py luna-none ...
if __package__ in (None, ''):
    sys.path.insert(0, str((Path(__file__).resolve().parent / '../../..').resolve()))

cli = __import__('finarch.shared.providers.cli', fromlist=['*'])
from finarch.shared.providers.profiles import DEFAULT, ROOT
Journal = __import__('finarch.shared.run_logging.logging', fromlist=['Journal']).Journal
from finarch.dataset.schemas.registry import require_llm_schema
from finarch.dataset.schemas.validation import parse_json, validate

README = '# Codex profile execution: {profile}\n\nStatus: {status}. Dry-run/mock checks do not verify live model support.\n\nReading order: `profile-plan.json` (profile, final command, response schema) →\n`02-calculation/profile-call/` or `05-text/profile-call/`, then `01-input.json` (prompt for an actual call) → `02-raw-response/cli-execution.json` (original CLI output and timing) →\n`02-raw-response.json` → `03-result/schema-check.json` → `run.json`.\n`events.jsonl` uses the existing stage-log format. Dry runs contain no actual response or execution artifacts. Select run `{batch}` in the viewer to inspect stage logs or sequential records. Format PASS does not establish semantic PASS or human approval. No retry is performed.\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', nargs='?')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--profiles', type=Path, default=DEFAULT)
    parser.add_argument('--config', type=Path, default=ROOT/'config/llm.json')
    parser.add_argument('--role', choices=['01-preparation.03-calculation.pot','02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation','dtt.answer'], default='dtt.answer')
    parser.add_argument('--input', type=Path, help='Role request JSON; omitted means JSON from stdin')
    parser.add_argument('--prompt-file', type=Path, help='Optional instruction text replacing the role prompt')
    parser.add_argument('--dry-run', action='store_true', help='No CLI inspection or subprocess/model call')
    parser.add_argument('--output', type=Path, help='New output directory; existing directories refused')
    args = parser.parse_args(argv)
    if args.list:
        for key, item in tomllib.loads(args.profiles.read_text()).get('profiles', {}).items():
            print(key + ': ' + json.dumps(item.get('argv'), ensure_ascii=False))
        return 0
    if not args.profile:
        parser.error('profile ID required; use --list')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    output = args.output or ROOT/'reports/run'/('profile-'+stamp)/'test-0001'
    output.mkdir(parents=True, exist_ok=False)
    journal = Journal(output, output.name)
    call_dir = ('02-calculation' if args.role == '01-preparation.03-calculation.pot' else '05-text') + '/profile-call/'
    def save(name, value):
        if name not in ('run.json', 'profile-plan.json', 'profile-failure.json'):
            name = call_dir + name
        (output/name).parent.mkdir(parents=True, exist_ok=True)
        with (output/name).open('x', encoding='utf-8') as f:
            f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        journal.artifact(name)
    status, reason = 'FAIL', 'NOT_STARTED'
    try:
        with journal.activate(), journal.span('profile_cli.execute', stage={'01-preparation.03-calculation.pot':'02-calculation','02-generation.02-generate-text.realization':'05-text','shared.01-02.02-03.review-and-validation':'05-text','dtt.answer':'05-text'}[args.role], role=args.role) as outcome:
            settings = cli.read_settings(args.config, args.role, profile_id=args.profile, profiles_path=args.profiles.resolve())
            definition = require_llm_schema(args.role)
            require_llm_schema(args.role, 'request')
            payload = parse_json(args.input.read_bytes() if args.input else sys.stdin.read())
            validate(args.role+'.request', payload)
            instruction = args.prompt_file.read_text() if args.prompt_file else None
            if instruction is not None and not instruction.strip():
                raise ValueError('EMPTY_PROMPT_FILE')
            resolved_instruction, prompt_selection = cli.prepare_instruction(args.role, payload, instruction)
            # Placeholders clearly describe temporary paths; no executable lookup in dry-run.
            command = cli.build_command(settings, 'codex', Path('/CALL_TEMP'), Path('/CALL_TEMP/01-input/response-schema.json'), Path('/CALL_TEMP/policy.json'), Path('/CALL_TEMP/tool-events.jsonl'))
            save('profile-plan.json', {'profile':settings['profile'], 'role':args.role, 'argv':command,
                 'dry_run':args.dry_run, 'temporary_paths':'/CALL_TEMP is replaced at execution',
                 'input':payload, 'instruction_override':instruction, 'response_schema':definition,
                 'prompt':resolved_instruction+'\nInput:\n'+json.dumps(payload, ensure_ascii=False),
                 'prompt_selection':prompt_selection,
                 'execution_enabled':settings['execution_enabled'], 'automatic_retries':0})
            if args.dry_run:
                status, reason = 'DRY_RUN', 'Input/schema/profile validated; no CLI or model called'
            else:
                result = cli.call(args.config, args.role, payload, save=save, profile_id=args.profile,
                                  profiles_path=args.profiles.resolve(), instruction=instruction)
                status, reason = result.status, result.reason
            outcome.update(status=status, reason=reason)
    except Exception as error:
        reason = str(error)
        save('profile-failure.json', {'status':'FAIL','reason':reason,'error_type':type(error).__name__})
    finally:
        save('run.json', {'status':status,'reason':reason,'profile_id':args.profile,'events':journal.events,
                         'summary':journal.summary(), 'dry_run':args.dry_run})
        (output/'README.md').write_text(README.format(profile=args.profile,status=status,batch=output.parent.name))
    print(json.dumps({'status':status,'reason':reason,'output':str(output.resolve())},ensure_ascii=False))
    return 0 if status in ('PASS','DRY_RUN') else 1


if __name__ == '__main__':
    raise SystemExit(main())
