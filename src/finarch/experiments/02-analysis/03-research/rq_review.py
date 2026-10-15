"""Validate an authored finding review and render traceable RQ reports; no model calls."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root):
    root = Path(root).resolve()
    folder = root / '02_analysis/03_research'
    review = json.loads((folder / 'rq-review.json').read_text())
    source = json.loads((folder / 'findings.json').read_text())
    findings = {f['id']: f for f in source['findings']}
    for rel, expected in review['source_sha256'].items():
        if digest(root / rel) != expected:
            raise ValueError('REVIEW_SOURCE_CHANGED:' + rel)
    groups = review['groups']
    group_ids = {g['id'] for g in groups}
    assigned = [f for g in groups for f in g['primary_finding_ids']]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(findings):
        raise ValueError('REVIEW_FINDING_COVERAGE_MISMATCH')
    for g in groups:
        if set(g['related_finding_ids']) - set(findings):
            raise ValueError('UNKNOWN_RELATED_FINDING')
    rows = review['finding_review']
    if len(rows) != len(findings) or {r['finding_id'] for r in rows} != set(findings):
        raise ValueError('REVIEW_AUDIT_COVERAGE_MISMATCH')
    owner = {f: g['id'] for g in groups for f in g['primary_finding_ids']}
    for r in rows:
        if r['primary_group'] != owner[r['finding_id']] or set(r['secondary_groups']) - group_ids:
            raise ValueError('REVIEW_GROUP_REFERENCE_MISMATCH')
    rq_lines = []
    for rq in review['research_questions']:
        rq_lines += [f"## {rq['id']} · {rq['text_ko']}", '', rq['assessment_ko'], '']
        for g in groups:
            if g['primary_rq'] != rq['id']:
                continue
            rq_lines += [f"### {g['id']} · {g['title_ko']}", '', g['claim_ko'], '',
                         '**근거와 비교 조건:** ' + g['evidence_ko'], '',
                         '**반례·다른 설명:** ' + g['alternatives_ko'], '',
                         '**말할 수 있는 범위:** ' + g['boundary_ko'], '',
                         '**주로 통합한 F:** ' + ', '.join(g['primary_finding_ids']), '',
                         '**함께 참조한 F:** ' + (', '.join(g['related_finding_ids']) or '없음'), '',
                         '**함께 관련된 RQ:** ' + (', '.join(g['secondary_rqs']) or '없음'), '']
    audit = ['# F001–F104 전체 검토 대응표', '', '각 F를 한 개 주 통합 그룹에 배정하고, 여러 주제를 가진 F는 보조 연결을 보존했습니다. 삭제된 F는 없습니다.', '',
             '|원본 F|원래 제목|주 그룹|보조 그룹|검토 판단|', '|---|---|---|---|---|']
    for r in rows:
        f = findings[r['finding_id']]
        audit.append('|'+ '|'.join([f['id'], f['display_ko']['title'].replace('|','/'), r['primary_group'], ', '.join(r['secondary_groups']) or '—', r['note_ko'].replace('|','/')])+'|')
    audit += ['', '## 원본 추적', '', '[원본 연구 발견](findings.md) · [원본 JSON](findings.json) · [검토 기준 데이터](rq-review.json)', '']
    template = Path(__file__).resolve().parents[2] / 'templates/rq-review.md'
    table = ['|통합 항목|주 RQ|주로 묶은 원본 F 수|', '|---|---|---|']
    table += [f"|{g['id']} {g['title_ko']}|{g['primary_rq']}|{len(g['primary_finding_ids'])}|" for g in groups]
    report = template.read_text().format(run=root.name, original_count=len(findings), group_count=len(groups), group_table='\n'.join(table), body='\n'.join(rq_lines), numerical_notes='\n'.join('- '+n for n in review['numerical_notes_ko']))
    (folder/'rq-review.md').write_text(report)
    (folder/'rq-review-audit.md').write_text('\n'.join(audit))
    readme_template = template.with_name('rq-review-readme.md')
    (folder/'rq-review-README.md').write_text(readme_template.read_text().format(run=root.name))
    validation = {'source_findings':len(findings), 'primary_assignments':len(assigned), 'groups':len(groups), 'all_findings_covered_once':True, 'source_hashes_verified':True, 'semantic_review':'CURRENT_CONVERSATION_EDITORIAL_REVIEW_NOT_INDEPENDENT_VALIDATION', 'new_external_model_calls':0}
    (folder/'rq-review-validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
    return validation


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True)
    print(json.dumps(build(p.parse_args().run),ensure_ascii=False))
