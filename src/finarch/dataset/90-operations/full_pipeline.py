"""Chain the existing phase schedulers; phase schedulers retain file ownership."""
import argparse
import json
from importlib import import_module
from pathlib import Path
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True)
    p.add_argument('--resume-preparation', action='store_true')
    args=p.parse_args()
    bundle=Path(args.run).resolve()
    try:
        write(bundle/'full-pipeline-status.json',{'status':'RUNNING','phase':'preparation'})
        prep=import_module('finarch.dataset.01-preparation.prepare_schedule')
        PREPARATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['PREPARATION']).PREPARATION
        result=prep.run_selected(None,str(bundle/'config.json'),None,PREPARATION,bundle=bundle,
                                 resume=args.resume_preparation)
        print(json.dumps(result),flush=True)
        write(bundle/'full-pipeline-status.json',{'status':'RUNNING','phase':'generation'})
        result=import_module('finarch.dataset.02-generation.generate_schedule').run(bundle)
        print(json.dumps(result),flush=True)
        write(bundle/'full-pipeline-status.json',{'status':'COMPLETED','phase':'generation'})
    except Exception as e:
        write(bundle/'full-pipeline-status.json',{'status':'ERROR','reason':f'{type(e).__name__}: {e}'})
        raise

if __name__=='__main__':main()
