"""Build a completed run's five-sheet review workbook without model calls."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def build(bundle):
    from finarch.dataset.viewer.reports.export_review_data import build as export
    from finarch.dataset.viewer.reports.finalize_failure_workbook import main as finalize
    root=Path(bundle).resolve()
    runtime=Path(os.environ.get('FINARCH_NODE_RUNTIME',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node')))
    node=runtime/'bin/node';modules=runtime/'node_modules'
    if not node.is_file() or not (modules/'@oai/artifact-tool').exists():
        raise RuntimeError('Spreadsheet runtime unavailable; set FINARCH_NODE_RUNTIME')
    data=export(root)
    destination=data.parent/(root.name.rsplit('-',1)[-1]+'-failure-review.xlsx')
    with tempfile.TemporaryDirectory(prefix='finarch-review-') as tmp:
        script=Path(tmp)/'build.mjs'
        shutil.copy2(Path(__file__).with_name('review-workbook.mjs'),script)
        (Path(tmp)/'node_modules').symlink_to(modules,target_is_directory=True)
        with (data.parent/'export.log').open('w') as log:
            subprocess.run([str(node),str(script),str(data),str(destination)],stdout=log,stderr=subprocess.STDOUT,check=True)
    finalize(str(root))
    template=Path(__file__).with_name('review-workbook-readme.md').read_text()
    (data.parent/'README.md').write_text(template.format(run=root.name,filename=destination.name,count=len(json.loads(data.read_text())['matrix'])))
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    print(build(parser.parse_args().run))
