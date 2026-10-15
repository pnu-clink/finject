"""Read hash-verified offline EA snapshots for the shared dataset viewer."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import re

NAME = re.compile(r'EA_INVERSE_REVIEW\.OFFLINE-(\d{8}-\d{6})(?:-[a-zA-Z0-9-]+)?\.jsonl')


def catalog(project):
    records=[]
    for path in sorted((project/'reports/dataset-review').glob('*-ea-inverse-offline-*/summary.json')):
        if path.is_symlink():continue
        value=json.loads(path.read_text());result=project/value['result']
        if result.is_file() and not result.is_symlink():
            records.append({'run':result.parent.name,'file':result.name,'timestamp':value['timestamp'],
                            'items':value['items'],'new_true':value['new_true'],'new_false':value['new_false']})
    return {'snapshots':records}


def paths(project,run,name):
    if not re.fullmatch(r'[a-zA-Z0-9-]+',run) or not NAME.fullmatch(name):raise ValueError('INVALID_EA_SNAPSHOT')
    folder=project/'data/final'/run
    report=project/'reports/dataset-review'/f'{run}-ea-inverse-offline-{NAME.fullmatch(name)[1]}'
    if folder.is_symlink() or report.is_symlink():raise ValueError('SYMLINK_EA_SNAPSHOT')
    summary_path=report/'summary.json'
    if summary_path.is_symlink():raise ValueError('SYMLINK_EA_SUMMARY')
    summary=json.loads(summary_path.read_text());result=folder/name
    if summary['result']!=str(result.relative_to(project)):raise ValueError('UNREGISTERED_EA_SNAPSHOT')
    baseline=project/summary['backup'];comparison=report/'comparison.jsonl'
    for path in (result,baseline,comparison):
        if path.is_symlink() or not path.resolve().is_relative_to(project.resolve()):raise ValueError('INVALID_EA_FILE')
        raw=path.read_bytes();expected=summary['files'][str(path.relative_to(project))]['sha256']
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('EA_SNAPSHOT_HASH_MISMATCH')
    return summary,result,baseline,comparison


@lru_cache(maxsize=3)
def read_rows(path,stamp,size):
    return [json.loads(line) for line in Path(path).open()]


def view(project,run,name,case=None,kind=None):
    summary,result,baseline,comparison=paths(project,run,name)
    def read(path):
        s=path.stat();return read_rows(str(path),s.st_mtime_ns,s.st_size)
    if case is None:
        fields=('id','type','source_dataset','previous_status','previous_inverse_possible','new_status','new_inverse_possible','transition','decision_changed','newly_reviewed')
        return {'summary':summary,'items':[{k:x[k] for k in fields} for x in read(comparison)]}
    if not re.fullmatch(r'id-\d{4}',case) or kind not in ('EA_01','EA_02'):raise ValueError('INVALID_EA_CASE')
    new=next((x for x in read(result) if x['id']==case),None)
    old=next((x for x in read(baseline) if x['id']==case),None)
    if new is None or old is None:raise ValueError('UNKNOWN_EA_CASE')
    selected=next(x for x in new['variants'] if x['type']==kind)
    translation_path=project/'viewer/dataset/ea-inverse-ko.json'
    if translation_path.is_file():
        ko=json.loads(translation_path.read_text())
        if ko['snapshot_sha256']==summary['files'][str(result.relative_to(project))]['sha256']:
            ir=selected['review_record']['inverse_review']
            selected={**selected,'display_ko':{'reason':ko['reason'][ir['reason']],
                                            'missing_quantity':ko['missing_quantity'][ir['missing_quantity']]}}
    return {'id':case,'type':kind,'source_dataset':new['source_dataset'],
            'new':selected,
            'previous':next(x for x in old['variants'] if x['type']==kind)}
