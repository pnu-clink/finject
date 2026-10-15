"""Allocate date-sequence run directories in Korea time under one filesystem lock."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import fcntl
import json
import re


def allocate_run(runs_root, *, now=None):
    root=Path(runs_root);root.mkdir(parents=True,exist_ok=True)
    day=(now or datetime.now(ZoneInfo('Asia/Seoul'))).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d')
    with (root/'.run-sequence.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        counter=root/'.run-sequence.json'
        counts=json.loads(counter.read_text()) if counter.exists() else {}
        pattern=re.compile(re.escape(day)+r'-(\d{3})$')
        existing=[int(m[1]) for p in root.iterdir() if (m:=pattern.fullmatch(p.name))]
        number=max([counts.get(day,0),*existing])+1
        if number>999:raise ValueError('Daily three-digit run sequence exhausted')
        result=root/f'{day}-{number:03d}'
        result.mkdir()
        counts[day]=number
        temp=counter.with_suffix('.tmp');temp.write_text(json.dumps(counts,sort_keys=True)+'\n');temp.replace(counter)
        return result
