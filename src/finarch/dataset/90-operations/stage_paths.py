"""Shared stage paths for artifact writers, readers, logs and viewer navigation."""
LABELS={'ANSWER':'00-original','IC_VALUE_01_BEFORE':'01-ic-value-before','IC_VALUE_01_AFTER':'02-ic-value-after','IC_SOURCE_A_ONLY':'03-ic-source-original','IC_SOURCE_B_ONLY':'04-ic-source-added','IC_RELATION_01':'05-ic-relation','EA_01':'06-ea-earlier-input','EA_02':'07-ea-later-input'}
PLANS={'IC_VALUE_01':'04-perturbation/01-plan-ic-value/03-check-calculation','IC_VALUE_01_BEFORE':'04-perturbation/01-plan-ic-value/04-plan-before-after/01-before','IC_VALUE_01_AFTER':'04-perturbation/01-plan-ic-value/04-plan-before-after/02-after','IC_SOURCE_A_ONLY':'04-perturbation/02-plan-ic-source/02-attribute-original-claim','IC_SOURCE_B_ONLY':'04-perturbation/02-plan-ic-source/03-attribute-added-claim','IC_RELATION_01':'04-perturbation/03-plan-ic-relation','EA_01':'04-perturbation/04-plan-ea/01-delete-earlier-input','EA_02':'04-perturbation/04-plan-ea/02-delete-later-input'}
def variant_root(label):
    if label in PLANS:return PLANS[label]
    for axis,folder in [('IC_VALUE','01-plan-ic-value'),('IC_SOURCE','02-plan-ic-source'),('IC_RELATION','03-plan-ic-relation'),('EA','04-plan-ea')]:
        if label==axis or label.startswith(axis+'-'):return '04-perturbation/'+folder+'/'+label.lower().replace('_','-')
    raise ValueError('Unknown perturbation label: '+label)
def candidate_root(label):return '08-records/02-file-index/'+LABELS[label]
def generation_root(label):return '05-text/01-generate-text/'+LABELS[label]
def audit_root(label):return '05-text/02-audit-meaning/'+LABELS[label]

def viewer_aliases(artifacts):
    """Read compatibility only; the disk tree and enumerated UI paths stay canonical."""
    read_aliases = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['read_aliases']).read_aliases
    aliases=read_aliases(artifacts)
    for label in LABELS:
        pairs=[(generation_root(label),'05-text/'+label+'/01-generate-text'),(audit_root(label),'05-text/'+label+'/03-audit-meaning'),(candidate_root(label),'05-text/'+label)]
        if label in PLANS:pairs.append((variant_root(label),'04-perturbation/variants/'+label))
        for physical,logical in pairs:
            for path in list(artifacts)+list(aliases):
                if path.startswith(physical+'/'):aliases[logical+path[len(physical):]]=aliases.get(path,path)
    PATHS = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['PATHS']).PATHS
    for logical,physical in PATHS.items():
        if physical in artifacts:aliases[logical]=physical
    return aliases
