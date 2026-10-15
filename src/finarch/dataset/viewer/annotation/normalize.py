"""Conservative, reversible repairs for the two observed annotator exports."""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

TYPES = (
    ('01-ic-value-before', 'IC_VALUE_01_BEFORE', 'IC-VALUE 앞'),
    ('02-ic-value-after', 'IC_VALUE_01_AFTER', 'IC-VALUE 뒤'),
    ('03-ic-source-type-1', 'IC_SOURCE_A_ONLY', 'IC-SOURCE Type 1'),
    ('04-ic-source-type-2', 'IC_SOURCE_B_ONLY', 'IC-SOURCE Type 2'),
    ('05-ic-relation', 'IC_RELATION_01', 'IC-RELATION'),
    ('06-ea-earlier-input', 'EA_01', 'EA 01'),
    ('07-ea-later-input', 'EA_02', 'EA 02'),
)
LABELS = {variant: label for variant, label, _ in TYPES}
VARIANTS = {variant for variant, _, _ in TYPES}
DECISIONS = ('APPROVED', 'REJECTED', 'PENDING')
ALIASES = {'accept': 'APPROVED', 'accepted': 'APPROVED', 'approve': 'APPROVED',
           'approved': 'APPROVED', 'pass': 'APPROVED', '통과': 'APPROVED',
           'reject': 'REJECTED', 'rejected': 'REJECTED', 'fail': 'REJECTED',
           '실패': 'REJECTED', 'pending': 'PENDING', 'hold': 'PENDING', '유보': 'PENDING'}
LEGACY_DECISIONS = {'APPROVED': 'accept', 'REJECTED': 'reject', 'PENDING': 'pending', None: None}
NORMALIZATION_VERSION = '20261007.1'
# The existing EA migration maps old 02/03 labels to current 01/02.
# Require the stable type path; never decrement arbitrary EA labels.
LEGACY_EA_LABELS = {'06-ea-earlier-input': 'EA_02', '07-ea-later-input': 'EA_03'}


def strip_trailing_commas(text):
    """Remove punctuation outside JSON strings; keep note text byte-for-byte."""
    output = []; quoted = False; escaped = False; removed = 0
    for index, char in enumerate(text):
        if not quoted and char == ',':
            following = index + 1
            while following < len(text) and text[following].isspace(): following += 1
            if following < len(text) and text[following] in ']}':
                removed += 1; continue
        output.append(char)
        if quoted:
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif char == '"': quoted = False
        elif char == '"': quoted = True
    return ''.join(output), removed


def parse_export(raw):
    changes = []
    text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
    if text.startswith('\ufeff'):
        text = text[1:]; changes.append({'path': '$', 'rule': 'REMOVE_UTF8_BOM'})
    fenced = re.fullmatch(r'\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*', text, re.I)
    if fenced:
        text = fenced[1]; changes.append({'path': '$', 'rule': 'REMOVE_JSON_FENCE'})
    cleaned, count = strip_trailing_commas(text)
    if count: changes.append({'path': '$', 'rule': 'REMOVE_TRAILING_COMMAS', 'count': count})
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Duplicate JSON object key: ' + key)
            result[key] = value
        return result
    value = json.loads(cleaned, object_pairs_hook=unique_object,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON number: ' + value)))
    return value, changes


def normalize(raw):
    value, changes = parse_export(raw)
    if not isinstance(value, dict): raise ValueError('Export must be a JSON object with annotator/reviewer and labels/evaluations.')
    repaired = deepcopy(value); issues = []; records = []
    def change(path, rule, before, after):
        if before != after or type(before) is not type(after):
            changes.append({'path': path, 'rule': rule, 'before': before, 'after': after})
    def issue(code, message, index=None, record=None):
        issues.append({'code': code, 'message': message, 'source_index': index,
                       'case': record.get('case') if record else None,
                       'variant': record.get('variant') if record else None})
    legacy = isinstance(value.get('labels'), list)
    field = 'labels' if legacy else 'evaluations'
    if not isinstance(value.get(field), list): raise ValueError('labels or evaluations must be an array.')
    if len(value[field]) > 100000: raise ValueError('Too many annotation records.')
    name_field = 'annotator' if legacy else 'reviewer'
    reviewer = value.get(name_field)
    if isinstance(reviewer, str):
        reviewer = reviewer.strip()
        change(name_field, 'TRIM_REVIEWER', value.get(name_field), reviewer)
        repaired[name_field] = reviewer
    if not isinstance(reviewer, str) or not reviewer or len(reviewer) > 100:
        reviewer = None; issue('REVIEWER_REQUIRED', '평가자 이름이 없거나 올바르지 않습니다.')
    if not legacy and value.get('format') != 'finarch-evaluation-results-v1':
        if value.get('format') is None:
            repaired['format'] = 'finarch-evaluation-results-v1'
            change('format', 'RESTORE_KNOWN_EXPORT_FORMAT', None, repaired['format'])
        else: issue('UNKNOWN_FORMAT', '지원하지 않는 평가 Export 형식입니다.')
    if legacy:
        if value.get('n') != len(value[field]):
            repaired['n'] = len(value[field]); change('n', 'COUNT_ACTUAL_RECORDS', value.get('n'), repaired['n'])
    else:
        for metadata in ('run', 'round', 'package_id'):
            if not isinstance(value.get(metadata), str) or not value[metadata]:
                issue('MISSING_' + metadata.upper(), '배포 JSON의 ' + metadata + ' 정보가 없습니다.')
        if not isinstance(value.get('cases'), list) or any(not isinstance(c, str) for c in value.get('cases', [])):
            issue('INVALID_CASE_SCOPE', '배포 문항 목록을 확인할 수 없습니다.')
    grouped = defaultdict(list)
    for index, item in enumerate(value[field]):
        path = f'{field}[{index}]'
        if not isinstance(item, dict): issue('INVALID_RECORD', '평가 항목이 객체가 아닙니다.', index); continue
        fixed = repaired[field][index]
        case = item.get('id' if legacy else 'case')
        variant = item.get('type' if legacy else 'variant')
        if isinstance(case, str):
            trimmed = case.strip(); change(path + '.case', 'TRIM_CASE', case, trimmed); case = trimmed
            fixed['id' if legacy else 'case'] = case
        if isinstance(variant, str):
            trimmed = variant.strip(); change(path + '.variant', 'TRIM_VARIANT', variant, trimmed); variant = trimmed
            fixed['type' if legacy else 'variant'] = variant
        record = {'case': case, 'variant': variant, 'decision': None, 'confirmed': False,
                  'comment': '', 'updated_at': item.get('timestamp' if legacy else 'updated_at'),
                  'source_index': index, 'issues': []}
        def row_issue(code, message):
            record['issues'].append(code); issue(code, message, index, record)
        if not isinstance(case, str) or not re.fullmatch(r'test-\d+', case): row_issue('INVALID_CASE', '문제 번호를 확인할 수 없습니다.')
        if not isinstance(variant, str) or variant not in VARIANTS and (legacy or variant != 'ANSWER'): row_issue('UNKNOWN_VARIANT', '7개 유형에 없는 항목입니다.')
        if not legacy and isinstance(value.get('cases'), list) and case not in value['cases']:
            row_issue('OUTSIDE_CASE_SCOPE', '배포 문항 목록에 없는 평가입니다.')
        if legacy:
            if not item.get('annotator') and reviewer:
                fixed['annotator'] = reviewer
                change(path + '.annotator', 'FILL_HEADER_ANNOTATOR', item.get('annotator'), reviewer)
            elif item.get('annotator') and item.get('annotator') != reviewer:
                row_issue('REVIEWER_MISMATCH', '항목의 평가자 이름이 파일 상단과 다릅니다.')
            expected = LABELS.get(variant) if isinstance(variant, str) else None
            if expected and not item.get('label'):
                fixed['label'] = expected; change(path + '.label', 'FILL_KNOWN_TYPE_LABEL', item.get('label'), expected)
            elif expected and item.get('label') == LEGACY_EA_LABELS.get(variant):
                fixed['label'] = expected
                change(path + '.label', 'NORMALIZE_LEGACY_EA_LABEL', item.get('label'), expected)
            elif expected and item.get('label') != expected:
                row_issue('TYPE_LABEL_MISMATCH', '유형과 label이 서로 다릅니다.')
        decision = item.get('decision')
        mapped = ALIASES.get(decision.strip().lower()) if isinstance(decision, str) else None
        if decision is not None and mapped is None: row_issue('UNKNOWN_DECISION', '판정을 통과·실패·유보 중 하나로 읽을 수 없습니다.')
        if mapped:
            fixed['decision'] = LEGACY_DECISIONS[mapped] if legacy else mapped
            change(path + '.decision', 'NORMALIZE_DECISION', decision, fixed['decision'])
        record['decision'] = mapped
        comment_field = 'note' if legacy else 'comment'
        comment = item.get(comment_field)
        if comment is None:
            comment = ''; fixed[comment_field] = comment
            change(path + '.' + comment_field, 'FILL_EMPTY_COMMENT', item.get(comment_field), comment)
        if not isinstance(comment, str): row_issue('INVALID_COMMENT', '주석이 문자열이 아닙니다.')
        else: record['comment'] = comment
        confirmed = bool(mapped) if legacy else item.get('confirmed')
        if not legacy and isinstance(confirmed, str) and confirmed.lower() in ('true', 'false'):
            converted = confirmed.lower() == 'true'; fixed['confirmed'] = converted
            change(path + '.confirmed', 'PARSE_EXPLICIT_BOOLEAN', confirmed, converted); confirmed = converted
        if not legacy and confirmed is None:
            confirmed = False; fixed['confirmed'] = False
            change(path + '.confirmed', 'KEEP_UNCONFIRMED_DRAFT', None, False)
            row_issue('MISSING_CONFIRMED', '저장 여부가 누락되어 저장된 판정으로 확인할 수 없습니다.')
        if type(confirmed) is not bool: row_issue('INVALID_CONFIRMED', '저장 여부가 true/false가 아닙니다.')
        elif confirmed and not mapped: row_issue('EMPTY_CONFIRMED_DECISION', '저장된 판정이 비어 있습니다.')
        else: record['confirmed'] = confirmed
        if legacy or 'inserted' in item or 'removed' in item:
            if legacy and 'inserted' not in item and 'removed' not in item:
                row_issue('CONTENT_NOT_RECORDED', '비교할 추가·삭제 본문이 모두 없습니다.')
            for content in ('inserted', 'removed'):
                text = item.get(content)
                if text is None:
                    text = ''; fixed[content] = text
                    change(path + '.' + content, 'FILL_EMPTY_EDIT_TEXT', item.get(content), text)
                if not isinstance(text, str): row_issue('INVALID_EDIT_TEXT', '추가·삭제 본문이 문자열이 아닙니다.'); text = ''
                record[content] = text
        checklist = item.get('checklist', {})
        if not isinstance(checklist, dict) or any(type(v) is not bool for v in checklist.values()):
            row_issue('INVALID_CHECKLIST', '체크 항목에 true/false가 아닌 값이 있습니다.')
        if isinstance(case, str) and isinstance(variant, str): grouped[(case, variant)].append(record)
        records.append(record)
    for same in grouped.values():
        if len(same) > 1:
            for record in same:
                record['issues'].append('DUPLICATE_RECORD')
                issue('DUPLICATE_RECORD', '같은 문제·유형이 중복되어 판정을 선택할 수 없습니다.', record['source_index'], record)
    return {'format': 'finarch-annotation-manager-v1', 'normalization_version': NORMALIZATION_VERSION,
            'normalization_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_format': 'finject-labels' if legacy else 'finarch-evaluation-results-v1',
            'reviewer': reviewer, 'run': value.get('run'),
            'round': value.get('round'),
            'package_id': value.get('package_id'), 'dataset': value.get('dataset'),
            'saved_at': value.get('exported_at' if legacy else 'saved_at'),
            'cases': sorted({r['case'] for r in records if isinstance(r['case'], str)}),
            'evaluations': records, 'changes': changes, 'issues': issues, 'repaired': repaired}
