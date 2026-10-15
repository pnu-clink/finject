"""Physical filenames follow the actual calculation-call sequence."""
POT = {
 'P01-author/01-input.json':'01-generate-code/01-receive-input/01-input.json',
 'P01-author/01-input/response-schema.json':'01-generate-code/02-prepare-request/01-handler-schema.json',
 '01-generate-code/llm/01-input/response-schema.json':'01-generate-code/02-prepare-request/02-response-schema.json',
 '01-generate-code/llm/01-input/request-schema.json':'01-generate-code/02-prepare-request/03-input-schema.json',
 '01-generate-code/llm/01-input/model-request.json':'01-generate-code/02-prepare-request/04-model-input.json',
 '01-generate-code/llm/01-input/cli-profile.json':'01-generate-code/02-prepare-request/05-cli-parameters.json',
 '01-generate-code/llm/01-input/cli-preflight.json':'01-generate-code/02-prepare-request/06-runtime-check.json',
 '01-generate-code/llm/01-input.json':'01-generate-code/03-LLM-call/01-request.json',
 '01-generate-code/llm/01-input/cli-start.json':'01-generate-code/03-LLM-call/02-start.json',
 '01-generate-code/llm/03-result/usage.json':'01-generate-code/04-receive-response/01-usage.json',
 '01-generate-code/llm/02-raw-response/cli-execution.json':'01-generate-code/04-receive-response/02-cli-execution.json',
 '01-generate-code/llm/02-raw-response/tool-events.json':'01-generate-code/04-receive-response/03-tool-events.json',
 '01-generate-code/llm/02-raw-response.json':'01-generate-code/04-receive-response/04-raw-response.json',
 '01-generate-code/llm/03-result/schema-check.json':'01-generate-code/05-validate-response/01-response-check.json',
 'P01-author/02-raw-response.json':'01-generate-code/05-validate-response/02-handler-response.json',
 'P01-author/03-result/schema-check.json':'01-generate-code/05-validate-response/03-handler-check.json',
 'P01-author/03-result.json':'01-generate-code/05-validate-response/04-result.json',
 'generated-original.json':'01-generate-code/05-validate-response/05-generated-program.json',
 'code-preparation.json':'02-prepare-code/01-transformation.json',
 'stepwise-review.json':'02-prepare-code/02-check.json',
 'program.json':'02-prepare-code/03-program.json',
 'program.txt':'02-prepare-code/04-program.txt',
 'P02-execute/01-input.json':'03-execute-python/01-input.json',
 'number-normalization.json':'03-execute-python/02-number-normalization.json',
 'P02-execute/03-result.json':'03-execute-python/03-result.json',
 'comparison.json':'04-compare-answer/01-comparison.json',
 'validation-status.json':'04-compare-answer/02-disposition.json',
 '01-generate-code/llm/03-result/failure.json':'01-generate-code/04-receive-response/05-call-failure.json',
}
for old,new in list(POT.items()):
    if old.startswith('P01-author/'):
        POT[old.replace('P01-author/','01-generate-code/',1)]=new
    elif old.startswith('P02-execute/'):
        POT[old.replace('P02-execute/','03-execute-python/',1)]=new
PATHS={'02-calculation/'+old:'02-calculation/'+new for old,new in POT.items()}

def ordered_path(relative):
    return PATHS.get(str(relative),str(relative))

def resolve_read(path):
    from pathlib import Path
    path=Path(path)
    if path.exists():return path
    s=path.as_posix()
    for old,new in PATHS.items():
        if s.endswith('/'+old):return Path(s[:-len(old)]+new)
    return path

# Every model call uses the same chronological lifecycle, including text/audit.
CALL_FILES = {
 '01-input.json':'03-LLM-call/01-request.json',
 '01-input/model-request.json':'02-prepare-request/01-model-input.json',
 '01-input/request-schema.json':'02-prepare-request/02-input-schema.json',
 '01-input/response-schema.json':'02-prepare-request/03-response-schema.json',
 '01-input/cli-profile.json':'02-prepare-request/04-cli-parameters.json',
 '01-input/cli-preflight.json':'02-prepare-request/05-runtime-check.json',
 '01-input/cli-start.json':'03-LLM-call/02-start.json',
 '02-raw-response.json':'04-receive-response/01-raw-response.json',
 '02-raw-response/cli-execution.json':'04-receive-response/02-cli-execution.json',
 '02-raw-response/tool-events.json':'04-receive-response/03-tool-events.json',
 '03-result/usage.json':'04-receive-response/04-usage.json',
 '03-result/failure.json':'04-receive-response/05-call-failure.json',
 '03-result/schema-check.json':'05-validate-response/01-response-check.json',
}
TEXT_FILES = {
 '01-input/source-binding.json':'01-receive-input/04-source-binding.json',
 '01-input.json':'01-receive-input/01-input.json',
 '01-input/check.json':'01-receive-input/02-binding-check.json',
 '02-pair-placement.json':'06-apply-result/01-pair-placement.json',
 '03-result/validation.json':'06-apply-result/02-edit-check.json',
 '03-result/patches.json':'06-apply-result/03-patches.json',
 '03-result.json':'06-apply-result/04-result.json',
 '03-result/metadata.json':'06-apply-result/05-metadata.json',
 '04-final-observation.json':'06-apply-result/06-final-observation.json',
 'context.txt':'06-apply-result/07-context.txt',
 '03-result/failure.json':'06-apply-result/08-failure.json',
}
HANDLER_FILES = {
 '01-input.json':'01-receive-input/03-handler-input.json',
 '01-input/response-schema.json':'02-prepare-request/06-handler-schema.json',
 '02-raw-response.json':'05-validate-response/02-handler-response.json',
 '03-result/schema-check.json':'05-validate-response/03-handler-check.json',
 '03-result.json':'05-validate-response/04-handler-result.json',
}

def ordered_path(relative):
    relative=str(relative)
    if relative in PATHS:return PATHS[relative]
    parts=relative.split('/')
    if len(parts)>=5 and parts[0]=='05-text' and parts[1] in ('01-generate-text','02-audit-meaning') and parts[2]!='00-run-summary':
        base='/'.join(parts[:4])+'/'
        suffix='/'.join(parts[4:])
        for prefix in ('realize/','audit/'):
            if suffix.startswith(prefix):return base+CALL_FILES.get(suffix[len(prefix):],suffix)
        for prefix in ('T01-realize/','T03-intent-audit/','03-LLM-call/'):
            if suffix.startswith(prefix):return base+HANDLER_FILES.get(suffix[len(prefix):],suffix)
        return base+TEXT_FILES.get(suffix,suffix)
    return relative

def resolve_read(path):
    from pathlib import Path
    path=Path(path)
    if path.exists():return path
    parts=path.parts
    for i,part in enumerate(parts):
        if part in ('02-calculation','05-text'):
            relative=Path(*parts[i:]).as_posix()
            mapped=ordered_path(relative)
            if mapped!=relative:return Path(*parts[:i])/mapped
    return path

def read_aliases(artifacts):
    aliases={}
    for physical in artifacts:
        parts=physical.split('/')
        if len(parts)>=5 and parts[0]=='05-text' and parts[2]!='00-run-summary':
            base='/'.join(parts[:4])+'/'
            for old,new in TEXT_FILES.items():
                if physical==base+new:aliases[base+old]=physical
            for prefix in ('realize/','audit/'):
                for old,new in CALL_FILES.items():
                    if physical==base+new:aliases[base+prefix+old]=physical
            for prefix in ('T01-realize/','T03-intent-audit/'):
                for old,new in HANDLER_FILES.items():
                    if physical==base+new:aliases[base+prefix+old]=physical
    return aliases

PLAN_FILES={
 'plan.json':'04-plan.json','branch-program.json':'02-program.json',
 'python-execution.json':'03-execution.json','number-normalization.json':'02-number-normalization.json',
 'calculation-input.json':'02-calculation-input.json','graph.json':'03-graph.json',
 'validation.json':'05-validation.json','previous-variants.json':'00-previous-candidates.json',
 '05-text-input-preview.json':'06-text-input-preview.json',
 '05-text-input-preview.md':'06-text-input-preview.md','06-generation-input.json':'07-generation-input.json',
 '04-deletion-check.json':'05-deletion-check.json',
 'not-generated.json':'08-not-generated.json',
}
_ordered_call_path=ordered_path
_call_read_aliases=read_aliases

def ordered_path(relative):
    relative=str(relative)
    if relative.startswith('04-perturbation/'):
        PLANS = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['PLANS']).PLANS
        for root in sorted(set(PLANS.values()),key=len,reverse=True):
            if relative.startswith(root+'/'):
                tail=relative[len(root)+1:]
                if tail in PLAN_FILES:return root+'/'+PLAN_FILES[tail]
    return _ordered_call_path(relative)

def resolve_read(path):
    from pathlib import Path
    path=Path(path)
    if path.exists():return path
    parts=path.parts
    for i,part in enumerate(parts):
        if part in ('02-calculation','04-perturbation','05-text'):
            relative=Path(*parts[i:]).as_posix();mapped=ordered_path(relative)
            if mapped!=relative:return Path(*parts[:i])/mapped
    return path

def read_aliases(artifacts):
    aliases=_call_read_aliases(artifacts)
    PLANS = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['PLANS']).PLANS
    for root in set(PLANS.values()):
        for old,new in PLAN_FILES.items():
            if root+'/'+new in artifacts:aliases[root+'/'+old]=root+'/'+new
    return aliases
