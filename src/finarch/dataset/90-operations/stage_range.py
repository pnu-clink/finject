"""Validate explicit stage ranges and preserve superseded local artifacts."""
from pathlib import Path
from datetime import datetime, timezone
import shutil
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
resolve_review_path = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['resolve_review_path']).resolve_review_path

PREPARATION = ('01-source','02-review','03-calculation','04-graph','05-verification','07-human-review')
GENERATION = ('01-perturbation','02-generate-text','03-validation','05-human-review')

def select(stages, start=None, stop=None, only=None):
    if only and (start or stop):
        raise ValueError('ONLY_STAGE_CONFLICTS_WITH_RANGE')
    if stages == PREPARATION:
        start, stop, only = [('02-review' if x == '02-review-and-correct' else x) for x in (start, stop, only)]
    start, stop = (only, only) if only else (start or stages[0], stop or stages[-1])
    if start not in stages or stop not in stages or stages.index(start)>stages.index(stop):
        raise ValueError('INVALID_STAGE_RANGE')
    return stages[stages.index(start):stages.index(stop)+1]

def require(root, paths):
    values={}
    for path in paths:
        file=resolve_review_path(Path(root)/path)
        if not file.is_file():raise ValueError('PREREQUISITE_MISSING:'+str(file))
        values[path]=read(file)
    return values

def begin(root, stages, selected, case_id):
    RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
    root=Path(root)
    if not root.exists():return RunContext(root,{},case_id)
    if (root/'00-round-input/seed.json').is_file() and not (root/'run.json').exists():
        return RunContext(root,{},case_id,seeded=True)
    ctx=RunContext.resume(root,{},case_id)
    # Later artifacts become stale after an earlier step is rerun. Preserve them,
    # including human decisions, outside the active stage paths.
    names=list(stages[stages.index(selected[0]):])+['run.json']
    names.append('06-exception-handler' if stages==PREPARATION else '04-exception-handler')
    if stages==PREPARATION and stages.index(selected[0])<=1:
        names+=['data.json','02-audit-meaning']
    backup=root/'stage-history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    backup.mkdir(parents=True)
    for name in names:
        p=root/name
        if p.exists():shutil.move(str(p),str(backup/name))
    write(backup/'selection.json',{'selected':list(selected),'invalidated_from':selected[0]})
    return ctx

def finish(ctx, result, selected):
    result.update(selected_stages=list(selected),allow_next_stage=False)
    ctx.save('run.json',result)
    text='# Step by step execution results\n\nThe range of choice: '+', '.join(selected)+'\n\nState of play: '+result['status']+'\n\nEach step is checked in the order of the folder → run.json → events.jsonl. The previous results are saved to stage-history.\n'
    (ctx.root/'README.md').write_text(text)
    return result
