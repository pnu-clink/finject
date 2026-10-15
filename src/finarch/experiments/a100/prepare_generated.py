"""Freeze six Qwen evaluations from the two portable generated archives."""
import importlib
import json
from pathlib import Path

mod = lambda name: importlib.import_module('finarch.experiments.' + name)
store = mod('90-operations.storage')
prepare = mod('01-evaluation.01-preparation.prepare').prepare
MODELS = [('Qwen/Qwen3-8B','b968826d9c46dd6066d109eabc6255188de91218'),
          ('Qwen/Qwen3-14B','40c069824f4251a91eefaf281ebe4c544efd3e18'),
          ('Qwen/Qwen3.8-27B','1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0')]


def main():
    audit = store.PROJECT/'reports/run/20261003-a100-generated-evaluation'
    index = audit/'evaluation-plan.json'
    existing = store.read(index, {})
    for entry in existing.get('runs', []):
        store.verify(store.PROJECT/'reports/experiments-run'/entry['run_id'])
    analysis = mod('02-analysis.configuration').read(store.PROJECT/'reports/experiments-run/20261003-exp-004-tatqa-luna')
    runs = existing.get('runs', [])
    for model, revision in MODELS:
        key = model.split('/')[-1].lower()
        for dataset, name, count in [('20261003-003','tatqa',291), ('20261003-concat-002','financereasoning',1260)]:
            if any(r['model'] == model and r['dataset'] == dataset for r in runs):
                continue
            root = store.allocate(store.PROJECT/'reports/experiments-run', label='a100-'+name+'-'+key.replace('.', '-'))
            config = {'evaluation': {'dataset': {'generated_path':'data/generated/'+dataset,
                'count':count,'require_all_variants_pass':True,'require_external_knowledge':True},
                'schedule':{'concurrency':16},'models':[{'key':key,'model':model,'revision':revision,
                'transport':'vllm_local','output_limits':{'off':8192,'on':8192}}],
                'reasoning_modes':['off','on'],'seed':20261003,'output_root':'reports/experiments-run',
                'response_contract':'FinancialAnswerV7'}, 'analysis':analysis}
            prepare(config,reserved_root=root)
            runtime={'tensor_parallel_size':4,'dtype':'bfloat16','max_num_seqs':32,
                'max_num_batched_tokens':8192,'gpu_memory_utilization':0.90,'max_model_len':40960,
                'prefix_caching':False,'chunked_prefill':True,'client_concurrency':16,
                'sampling':{'off':{'temperature':0.7,'top_p':0.8},'on':{'temperature':0.6,'top_p':0.95}},
                'top_k':20,'min_p':0,'seed':20261003,'served_model':model,
                'status':'REQUIRES_TOKEN_AND_ENGINE_PREFLIGHT'}
            relative='01_evaluation/01_preparation/a100-runtime.json'
            store.write(root/relative,runtime)
            manifest=store.read(root/'manifest.json');manifest[relative]=store.file_hash(root/relative)
            store.write(root/'manifest.json',manifest)
            runs.append({'run_id':root.name,'model':model,'revision':revision,'model_key':key,
                         'dataset':dataset,'originals':count,'requests':count*32})
            store.write(index,{'status':'PREPARING','runs':runs,'new_model_calls':0})
            print(json.dumps(runs[-1]),flush=True)
    store.write(index,{'status':'PREPARED','runs':runs,'requests':sum(r['requests'] for r in runs),
                      'new_model_calls':0,'incremental_api_charge_usd':0,'gpu_infrastructure_cost':'UNKNOWN'})


if __name__=='__main__': main()
