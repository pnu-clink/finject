"""Batch review boundary between preparation and variant generation."""
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path


REQUIRED = {
    'source': '01-source/01-receive-input/01-input.json',
    'working_input': 'data.json',
    'audit': '02-review-and-correct/accepted-audit.json',
    'program': '03-calculation/02-prepare-code/03-program.json',
    'comparison': '03-calculation/04-compare-answer/01-comparison.json',
    'graph': '04-graph/04-save-graph/01-graph.json',
}


def active_case_path(case):
    case=Path(case)
    marker=case/'run.json'
    if marker.is_file():
        info=json.loads(marker.read_text())
        name=info.get('active_round')
        if name:
            import re
            if not re.fullmatch(r'[0-9]+-round',name):raise ValueError('INVALID_ACTIVE_ROUND')
            return case/name
    return case


def resolve_review_path(path):
    """Read historical paths or the active immutable round without rewriting history."""
    path=Path(path)
    if path.exists():return path
    parts=path.parts
    for i,part in enumerate(parts):
        if part.startswith('test-'):
            case=Path(*parts[:i+1]);active=active_case_path(case)
            if active!=case:
                candidate=active/Path(*parts[i+1:])
                if candidate.exists():return candidate
                path=candidate
            break
    replacements={
      '02-review-and-correct/':'02-review/',
      '03-calculation/02-prepare-code/03-program.json':'03-calculation/05-record-calculation-artifacts/03-program.json',
      '03-calculation/04-compare-answer/01-comparison.json':'03-calculation/05-record-calculation-artifacts/02-comparison.json',
      '04-graph/04-save-graph/01-graph.json':'04-graph/05-save-graph/01-graph.json',
      '07-human-review/02-record-decision/':'07-human-review/03-record-decision/',
    }
    text=str(path)
    for old,new in replacements.items():text=text.replace(old,new)
    if Path(text).exists():return Path(text)
    legacy=Path(str(path).replace('02-review-and-correct/','02-audit-meaning/'))
    return legacy if legacy.exists() else path


def read(path):
    return json.loads(resolve_review_path(path).read_text())


def complete_reference(sample, accepted_path):
    """Restore recorded reference fields only when the accepted Q/C still matches."""
    fields = ('reference_answer', 'reference_answer_type', 'reference_precision')
    missing = [key for key in fields if key not in sample]
    if not missing:
        return sample, None
    accepted_path = resolve_review_path(accepted_path)
    accepted = read(accepted_path)
    if any(sample.get(k) != accepted.get(k) for k in ('id', 'question', 'context')):
        raise ValueError('ACCEPTED_INPUT_QC_MISMATCH:' + sample['id'])
    if any(k not in accepted or (k in sample and sample[k] != accepted[k]) for k in fields):
        raise ValueError('ACCEPTED_REFERENCE_MISMATCH:' + sample['id'])
    restored = {**sample, **{k: accepted[k] for k in missing}}
    if 'answer_metadata' not in restored and 'answer_metadata' in accepted:
        restored['answer_metadata'] = accepted['answer_metadata']
        missing.append('answer_metadata')
    return restored, {'fields': missing,
                      'source_sha256': hashlib.sha256(accepted_path.read_bytes()).hexdigest()}


def generation_sample(case):
    """Load working text plus immutable accepted metadata without editing history."""
    case = Path(case)
    sample, repair = complete_reference(read(case/'data.json'),
                                        case/'02-review-and-correct/accepted-input.json')
    if repair:
        repair = {**repair, 'source': str(resolve_review_path(
            case/'02-review-and-correct/accepted-input.json').relative_to(case)),
            'original_data_unchanged': True}
    return sample, repair


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def snapshot(case):
    case = Path(case)
    files = {}
    active=active_case_path(case)
    if active!=case and read(active/'05-verification/08-record-verdict/01-result.json').get('status')!='PASS':
        raise ValueError('VERIFICATION_REQUIRED')
    for name, relative in REQUIRED.items():
        path = resolve_review_path(case / relative)
        if not path.is_file():
            raise ValueError('PREPARATION_ARTIFACT_MISSING:' + name)
        files[name] = {'path': str(path.relative_to(case)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if read(case / REQUIRED['audit']).get('status') != 'PASS':
        raise ValueError('ORIGINAL_AUDIT_NOT_PASSED')
    if read(case / REQUIRED['comparison']).get('matches') is not True:
        raise ValueError('CALCULATION_NOT_RESOLVED')
    _, repair = generation_sample(case)
    if repair:
        files['reference_metadata'] = {'path': repair['source'],
                                       'sha256': repair['source_sha256']}
    return files


def record_decision(case, decision, reviewer, reason='', checklist=None, *, allow_failed_review=False):
    case = Path(case)
    if decision not in ('APPROVED', 'REJECTED', 'PENDING'):
        raise ValueError('INVALID_PREPARATION_DECISION')
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('REVIEWER_REQUIRED')
    if not isinstance(reason,str):raise ValueError('INVALID_REVIEW_REASON')
    if decision in ('REJECTED','PENDING') and not reason.strip():raise ValueError('REVIEW_REASON_REQUIRED')
    if checklist is not None:
        if isinstance(checklist,dict): checklist={('02-review-and-correct' if k in ('02-audit-meaning','02-review') else k):v for k,v in checklist.items()}
        required={'02-review-and-correct','03-calculation','04-graph'}
        if not isinstance(checklist,dict) or set(checklist) not in (required,required|{'05-verification'}) or any(type(v) is not bool for v in checklist.values()):raise ValueError('INVALID_REVIEW_CHECKLIST')
        if decision=='APPROVED' and not all(checklist.values()):raise ValueError('REVIEW_CHECKLIST_INCOMPLETE')
    files, automatic_validation_error = {}, None
    if decision == 'APPROVED':
        try:
            files = snapshot(case)
        except (ValueError, OSError, KeyError) as error:
            if not allow_failed_review:
                raise
            # Human acceptance is recorded separately from the production gate.
            automatic_validation_error = str(error)
            for name, relative in REQUIRED.items():
                path = resolve_review_path(case / relative)
                if path.is_file():
                    files[name] = {'path': str(path.relative_to(case)),
                                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    value = {'decision': decision, 'reviewer': reviewer, 'reason': reason,
             'recorded_at': datetime.now().astimezone().isoformat(), 'files': files}
    if automatic_validation_error is not None:
        value['automatic_validation_error'] = automatic_validation_error
    if checklist is not None:value['checklist']=checklist
    directory = active_case_path(case) / ('07-human-review/03-record-decision' if active_case_path(case)!=case else '07-human-review/02-record-decision')
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'history.jsonl').open('a') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    write(directory / 'decision.json', value)
    return value


def evaluate(bundle, *, persist=False):
    bundle = Path(bundle)
    names = read(bundle / 'input-selection.json')['cases']
    if len(names) != len(set(names)):
        raise ValueError('DUPLICATE_SELECTED_CASE')
    approved, rejected, pending, invalid = [], [], [], []
    inputs = {}
    for name in names:
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('INVALID_CASE_ID')
        case = bundle / '01-preparation' / name
        # The case marker is the sole Preparation decision authority.
        # Historical human decisions remain evidence, never an entry gate.
        marker = case / 'run.json'
        status = read(marker).get('status') if marker.is_file() else None
        if status in ('FAIL', 'ERROR'):
            rejected.append(name)
        elif status == 'PASS':
            try:
                files = snapshot(case)
                approved.append(name)
                inputs[name] = {'case_path': str(case.relative_to(bundle)), 'files': files}
            except (ValueError, OSError, KeyError) as error:
                invalid.append({'case': name, 'reason': str(error)})
        else:
            pending.append(name)
    ready = bool(names) and not pending and not invalid
    report = {'status': 'READY' if ready else 'WAITING_FOR_REVIEW',
              'approved': approved, 'rejected': rejected, 'pending': pending,
              'invalid': invalid, 'allow_generation': ready,
              'approved_inputs': inputs if ready else {}}
    if persist:
        write(bundle / '01-preparation/review-gate.json', report)
    return report


def require_generation_inputs(bundle, *, persist=False):
    """Revalidate the entire batch and content hashes at each generation entry."""
    report = evaluate(bundle, persist=persist)
    if not report['allow_generation']:
        raise ValueError('PREPARATION_REVIEW_INCOMPLETE')
    if persist:
        write(Path(bundle) / '02-generation/approved-inputs.json', report['approved_inputs'])
    return report['approved_inputs']
