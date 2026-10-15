"""Measure pipeline wall time and concurrent calls without adding overlapping durations."""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from functools import wraps
import math
import os
from pathlib import Path
import threading
import time
import uuid

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
_refresh_lock = threading.Lock()
_last_refresh = {}
PRIMARY = ('integrity', 'numeric_comparison', 'result_collection', 'source_verification',
           'relationship_aggregation', 'comparison_request_preparation', 'comparison_models',
           'comparison_recovery', 'comparison_collection', 'research_request_preparation', 'research_models',
           'research_recovery', 'research_collection', 'publication', 'finding_grouping')
LABELS = {
    'pipeline_total': '전체 실행', 'evaluation_collection': '기존 Evaluation 수집',
    'analysis_total': 'Analysis 실행', 'integrity': '입력 무결성 확인',
    'numeric_comparison': '저장 응답의 숫자 비교', 'result_collection': 'A01 결과 취합',
    'source_verification': '재개 시 원자료 확인', 'relationship_aggregation': 'A02 관계 집계',
    'comparison_request_preparation': 'A02 분석 요청 구성', 'comparison_models': 'A02 모델 해석',
    'comparison_recovery': 'A02 실패 확인·대기·재시도',
    'comparison_collection': 'A02 해석 검사·취합', 'research_request_preparation': 'A03 연구 요청 구성',
    'research_models': 'A03 모델 해석', 'research_collection': 'A03 해석 검사·취합',
    'research_recovery': 'A03 실패 확인·대기·재시도',
    'publication': 'A03 최종 보고 생성', 'model_call': '개별 모델 호출',
    'finding_grouping': 'A04 D01 연구 발견 주제·조건 정리',
    'state_persistence': '분석 상태·결과 저장', 'codex_auth': 'Codex 인증 확인',
}


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def append(root, value):
    folder = Path(root) / '02_analysis'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'timing-events.jsonl').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(store.encoded(value).decode() + '\n')
        handle.flush()


@contextmanager
def measure(root, step, **metadata):
    """Preserve start/end pairs even when an operation fails or is interrupted."""
    identity = uuid.uuid4().hex
    started, monotonic = stamp(), time.perf_counter()
    fields = {'span_id': identity, 'step': step, 'pid': os.getpid(), **metadata}
    append(root, {**fields, 'event': 'START', 'started_at': started})
    refresh(root)
    outcome = {}
    try:
        yield outcome
    except BaseException as error:
        outcome.update(status='FAILED', error_type=type(error).__name__)
        raise
    finally:
        append(root, {**fields, 'event': 'END', 'started_at': started, 'ended_at': stamp(),
                      'elapsed_seconds': time.perf_counter() - monotonic,
                      'status': outcome.pop('status', 'COMPLETED'), **outcome})
        refresh(root, force=step in ('analysis_total', 'pipeline_total'))


def recorded(step):
    def decorate(function):
        @wraps(function)
        def execute(root, *args, **kwargs):
            with measure(root, step):
                return function(root, *args, **kwargs)
        return execute
    return decorate


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def occupied(intervals):
    """Union overlapping intervals; four simultaneous calls count as one wall interval."""
    total, end = 0.0, float('-inf')
    for left, right in sorted(intervals):
        total += max(0, right - max(left, end))
        end = max(end, right)
    return total


def summarize(events, *, now=None, is_alive=alive):
    now = now or datetime.now(timezone.utc)
    spans = {}
    for row in events:
        spans[row['span_id']] = {**spans.get(row['span_id'], {}), **row}
    groups = defaultdict(list)
    active = []
    for row in spans.values():
        if row['event'] == 'START':
            row['status'] = 'RUNNING' if is_alive(row['pid']) else 'INTERRUPTED'
            row['elapsed_seconds'] = (max(0, (now - datetime.fromisoformat(row['started_at'])).total_seconds())
                                      if row['status'] == 'RUNNING' else None)
            if row['status'] == 'RUNNING':
                active.append({k: row[k] for k in ('step', 'started_at', 'elapsed_seconds', 'stage', 'trial_id') if k in row})
        groups[(row['step'], row.get('stage'))].append(row)
    steps = []
    for (step, stage), rows in groups.items():
        finished = [r for r in rows if r['event'] == 'END']
        times = sorted(r['elapsed_seconds'] for r in finished)
        intervals = [(datetime.fromisoformat(r['started_at']).timestamp(),
                      datetime.fromisoformat(r['ended_at']).timestamp() if r.get('ended_at') else now.timestamp())
                     for r in rows if r['elapsed_seconds'] is not None]
        wall = occupied(intervals)
        running = [r for r in rows if r['status'] == 'RUNNING']
        steps.append({'step': step, 'stage': stage, 'label': LABELS.get(step, step),
            'attempts': len(rows), 'completed': len(finished), 'running': len(running),
            'interrupted': sum(r['status'] == 'INTERRUPTED' for r in rows),
            'statuses': dict(Counter(r['status'] for r in rows)),
            'result_statuses': dict(Counter(r['result_status'] for r in finished if r.get('result_status'))),
            'occupied_wall_seconds': wall, 'completed_call_seconds_sum': sum(times),
            'in_progress_call_seconds_sum': sum(r['elapsed_seconds'] for r in running),
            'p50_seconds': times[(len(times)-1)//2] if times else None,
            'p95_seconds': times[math.ceil(len(times)*.95)-1] if times else None,
            'max_seconds': times[-1] if times else None,
            'planned_requests': max((r.get('planned_requests', 0) for r in rows), default=0) or None})
    candidates = [r for r in steps if r['step'] in PRIMARY]
    denominator = sum(r['occupied_wall_seconds'] for r in candidates)
    ranked = sorted(candidates, key=lambda r: r['occupied_wall_seconds'], reverse=True)
    bottleneck = ({'step': ranked[0]['step'], 'label': ranked[0]['label'],
        'occupied_wall_seconds': ranked[0]['occupied_wall_seconds'],
        'share_of_measured_analysis_steps': ranked[0]['occupied_wall_seconds'] / denominator,
        'provisional': bool(active)} if ranked and denominator else None)
    return {'schema_version': 1, 'updated_at': now.isoformat(timespec='milliseconds'),
        'status': 'RUNNING' if active else 'INTERRUPTED' if any(r['interrupted'] for r in steps) else 'RECORDED',
        'steps': steps, 'active': active, 'bottleneck': bottleneck,
        'boundaries': ['Durations use a monotonic clock; timestamps use UTC.',
            'Parallel call seconds and nested steps are not added to stage wall time.',
            'Model call time includes CLI, network and provider processing; server queue and reasoning time are not separately observable.',
            'Unfinished calls have provisional elapsed time; interrupted spans without an end have unknown duration.',
            'Only instrumented invocations are measured; earlier collection and development time are excluded.']}


def refresh(root, *, force=False):
    root = Path(root)
    if not _refresh_lock.acquire(blocking=False):
        return
    try:
        current = time.monotonic()
        if not force and current - _last_refresh.get(str(root), float('-inf')) < 5:
            return
        folder = root / '02_analysis'
        path = folder / 'timing-events.jsonl'
        if not path.exists():
            return
        with path.open() as handle:
            fcntl.flock(handle, fcntl.LOCK_SH)
            import json
            events = [json.loads(line) for line in handle if line.strip()]
        value = summarize(events)
        store.write(folder / 'timing.json', value)
        table = '\n'.join(f"|{r['label']} {r['stage'] or ''}|{r['occupied_wall_seconds']:.2f}|{r['completed']}|{r['running']}|{r['p50_seconds']:.2f}|" if r['p50_seconds'] is not None else
                          f"|{r['label']} {r['stage'] or ''}|{r['occupied_wall_seconds']:.2f}|{r['completed']}|{r['running']}|미완료|"
                          for r in value['steps'])
        bottleneck = value['bottleneck']
        description = (f"{bottleneck['label']} · 측정된 Analysis 단계 시간의 {bottleneck['share_of_measured_analysis_steps']:.1%}"
                       if bottleneck else 'Analysis 단계 측정 전')
        template = (store.PROJECT / 'src/finarch/experiments/templates/analysis-timing.md').read_text()
        store.write_text(folder / 'timing.md', template.format(run=root.name, updated_at=value['updated_at'],
            status=value['status'], bottleneck=description, table=table))
        _last_refresh[str(root)] = current
    finally:
        _refresh_lock.release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    refresh(args.run, force=True)
