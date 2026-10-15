"""Final successful results in the unchanged dataset UI, in one portable HTML."""
import base64
import copy
import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from finarch.dataset.viewer.evaluation_export import inline_json, keep_artifact, REQUIRED_VARIANTS


def keep_final_artifact(relative):
    """Keep displayed final evidence/code/graphs and saved decisions, not histories."""
    if relative in ('approved-input.json', '01-perturbation/01-input.json',
                    '03-validation/01-input.json', '03-validation/05-recovery-screen.json',
                    '03-validation/06-source-exact.json',
                    '03-validation/07-ea-inverse-review/latest.ref.json'):
        return True
    if re.fullmatch(r'03-validation/07-ea-inverse-review/attempt-\d+/(01-input/qc.json|03-result/(inverse-review|evidence-display-check).json)', relative):
        return True
    if relative in ('07-human-review/02-record-decision/decision.json',
                    '07-human-review/03-record-decision/decision.json',
                    '05-human-review/02-record-decision/decision.json',
                    '05-human-review/decision.json'):
        return True
    return keep_artifact(relative)


def final_generation_files(files, variants):
    """Retain only the linked final inverse annotation, not its older attempts."""
    selected = {k:v for k,v in files.items() if k.split('/')[0] in variants}
    for variant in variants:
        prefix = variant+'/'
        inverse = prefix+'03-validation/07-ea-inverse-review/'
        ref = ((selected.get(prefix+'run.json') or {}).get('inverse_review_ref') or
               (selected.get(prefix+'05-human-review/01-result.json') or {}).get('inverse_review_ref') or
               selected.get(inverse+'latest.ref.json') or {})
        report_path = prefix+ref.get('path', '')
        report = selected.get(report_path) or {}
        linked = {report_path, prefix+report.get('request_ref', ''),
                  prefix+report.get('evidence_display_check_ref', ''), inverse+'latest.ref.json'}
        selected = {k:v for k,v in selected.items() if not k.startswith(inverse) or k in linked}
    return selected


def build(root, name, initial_view=None):
    """Export one run's latest PASS results, regardless of active UI filters/round."""
    from finarch.dataset.viewer.server import batch_data, batch_path
    from finarch.dataset.viewer.assets import render
    bundle = batch_path(root, name)
    if not (bundle/'01-preparation').is_dir():
        raise ValueError('Preparation/Generation 실행을 선택해 주세요.')
    overview = batch_data(root, name, artifact_filter=keep_final_artifact, final_only=True)
    batch = copy.deepcopy(overview['batch'])
    selected_round = batch.get('round')
    summaries, entries, blobs = [], [], []
    signature = hashlib.sha256()
    passed = set()
    prefix = str(bundle.parent.resolve())+'/'
    candidates = overview['runs']
    for candidate in candidates:
        if candidate.get('artifacts', {}).get('run.json', {}).get('status') != 'PASS':
            continue
        case = Path(candidate.get('case_path', candidate['path'])).name
        detail = candidate if not candidate.get('summary_only') else batch_data(
            root, name, selected_round, case, detail_only=True,
            artifact_filter=keep_final_artifact, final_only=True)['runs'][0]
        if detail.get('artifacts', {}).get('run.json', {}).get('status') != 'PASS':
            continue
        variants = [v for v in REQUIRED_VARIANTS
                    if detail.get('generation', {}).get(v+'/run.json', {}).get('status') == 'PASS']
        detail['generation'] = final_generation_files(detail.get('generation', {}), variants)
        for field in ('generation_snapshots', 'generation_origins'):
            detail[field] = {k: v for k, v in detail.get(field, {}).items()
                             if k.split('/')[0] in variants}
        summary = copy.deepcopy(detail.pop('list_entry', None) or candidate)
        summary['summary_only'] = True
        summary['external_knowledge'] = detail.get('external_knowledge')
        raw = json.dumps(detail, ensure_ascii=False, separators=(',', ':')).replace(prefix, 'reports/run/')
        digest = hashlib.sha256(raw.encode()).hexdigest()
        signature.update((case+digest).encode())
        ident = 'original-case-'+str(len(entries))
        blobs.append(f'<script type="application/octet-stream" id="{ident}">{base64.b64encode(gzip.compress(raw.encode(),mtime=0)).decode()}</script>')
        summaries.append(json.loads(json.dumps(summary,ensure_ascii=False).replace(prefix,'reports/run/')))
        entries.append({'case':case, 'blob':ident, 'sha256':digest, 'variants':variants})
        passed.update((case, variant) for variant in variants)
    if not entries:
        raise ValueError('내보낼 최종 Preparation PASS 결과가 없습니다.')
    # Round aggregates remain recorded context; detailed files are final results only.
    batch['rounds'] = [selected_round] if selected_round else []
    batch['generation_overview'] = [r for r in batch.get('generation_overview', [])
                                    if (r['case'], r['path'].split('/')[0]) in passed]
    # These controls require the production server and are outside final-result export.
    for field in ('failure_analysis', 'rechecks', 'result_report', 'failure_workbook',
                  'generated_dataset', 'preparation_failure_report', 'preparation_repair_results',
                  'generation_feedback', 'round_reports'):
        batch.pop(field, None)
    package = {'format':'finarch-original-html-v1', 'id':signature.hexdigest(), 'run':name,
               'round':selected_round, 'created_at':datetime.now(timezone.utc).isoformat(),
               'selection':'LATEST_PREPARATION_PASS_AND_LATEST_VARIANT_PASS',
               'cases':entries, 'initial_view':initial_view or {},
               'excluded_preparation':len(candidates)-len(entries)}
    payload = {'format':'fin-arch-viewer-v1', 'live':False, 'original':package,
               'batch':batch, 'runs':summaries}
    html = render().replace('__FINARCH_DATA__', inline_json(payload)).replace(
        '<head>', '<head><script>window.FINARCH_ORIGINAL=true;</script>', 1)
    html = html.replace('<script id="data"', ''.join(blobs)+'<script id="data"', 1)
    body = html.encode('utf-8')
    return body, {'run':name, 'cases':len(entries), 'variants':len(passed), 'bytes':len(body)}
