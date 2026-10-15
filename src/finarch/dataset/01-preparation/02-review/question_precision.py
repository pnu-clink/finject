"""Align explicit decimal-place instructions with the preserved gold precision."""
import copy
import re
from decimal import Decimal
from pathlib import Path

WORDS = {'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,
         'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,
         'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,
         'seventeen':17,'eighteen':18,'nineteen':19,'twenty':20}
NUMBER = r'(?:\d+|' + '|'.join(WORDS) + ')'
PATTERN = re.compile(r'\b(?:to|with|at|using)\s+(?:exactly\s+)?(?P<count>'+NUMBER+r')\s+decimal\s+places?\b',re.I)


def align(sample):
    """Change only the count token; never change context, gold, or rounding mode."""
    working=copy.deepcopy(sample)
    gold=Decimal(str(sample['reference_answer']))
    if not gold.is_finite():raise ValueError('NON_FINITE_REFERENCE')
    precision=max(0,-gold.as_tuple().exponent)
    if sample['reference_precision'] != precision:
        raise ValueError('REFERENCE_PRECISION_MISMATCH')
    question=sample['question'];edits=[]
    for match in PATTERN.finditer(question):
        token=match.group('count');count=WORDS[token.lower()] if token.lower() in WORDS else int(token)
        if count==precision:continue
        replacement=str(precision) if token.isdigit() else next((k for k,v in WORDS.items() if v==precision),str(precision))
        if token.istitle():replacement=replacement.capitalize()
        elif token.isupper():replacement=replacement.upper()
        edits.append({'field':'question','start':match.start('count'),'end':match.end('count'),
                      'before':token,'text':replacement,'reason':'Match the decimal places preserved in the reference answer.'})
        unit=re.search(r'places?$',match.group(),re.I)
        before=unit.group();after='place' if precision==1 else 'places'
        if before.lower()!=after:
            edits.append({'field':'question','start':match.start()+unit.start(),'end':match.end(),
                          'before':before,'text':after,'reason':'Keep singular/plural agreement with the updated decimal-place count.'})
    edits.sort(key=lambda item:item['start'])
    for edit in reversed(edits):
        a,b=edit['start'],edit['end'];working['question']=working['question'][:a]+edit['text']+working['question'][b:]
    return working, {'status':'PASS','reason':'QUESTION_PRECISION_ALIGNED' if edits else 'NO_DECIMAL_PLACE_CHANGE',
                     'reference_answer':sample['reference_answer'],'reference_precision':precision,
                     'before_question':question,'after_question':working['question'],'edits':edits,
                     'policy':'Only explicit decimal-place counts are aligned; significant figures and currency units are not inferred.',
                     'requires_semantic_audit':bool(edits)}


def run(ctx, sample):
    working,report=align(sample)
    stage='02-review-and-correct/00-question-precision'
    ctx.save(stage+'/01-input.json',{'question':sample['question'],'reference_answer':sample['reference_answer'],
                                   'reference_precision':sample['reference_precision']})
    ctx.save(stage+'/03-result.json',report)
    ctx.save_text(stage+'/README.md',Path(__file__).with_name('question-precision-readme.md').read_text())
    return working
