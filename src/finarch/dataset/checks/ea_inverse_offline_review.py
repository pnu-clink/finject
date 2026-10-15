"""No-network workbench for Q/C-only EA annotations supplied by the reviewing agent."""
from __future__ import annotations
import argparse
import ast
from collections import defaultdict
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[4]
STATE = PROJECT / 'tmp/ea-inverse-offline-current.json'

def state():
    return json.loads(STATE.read_text())

def rows():
    return [json.loads(s) for s in (PROJECT / state()['report_dir'] / 'qc-only.jsonl').open()]

def number(s):
    s = re.sub(r'<[^>]+>|\([^\d)]*\)|\[\d+\]', '', s).strip()
    if s in ('—', '–', '-', '$ -', '$—', '$–'):
        return Fraction(0)
    if not s or s in ('$', '()', '$()', '€', '£'):
        return None
    s = s.replace(',', '').replace('$', '').replace('€', '').replace('£', '').replace(' ', '')
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', s):
        return None
    return Fraction(s)

def table(c):
    result = []
    for line in c.splitlines():
        if '|' not in line or re.search(r'^\s*\|?\s*:?-{2,}', line):
            continue
        # Some inputs are string representations of a one-element table list.
        line = line.removeprefix("['").removesuffix("']")
        raw = line.strip()
        parts = raw.split('|')
        if raw.startswith('|'):
            parts = parts[1:]
            if raw.endswith('|'):
                parts = parts[:-1]
        cells = [s.strip() for s in parts]
        if len(cells) > 1:
            result.append({'label': cells[0], 'cells': cells[1:], 'line': line,
                           'values': [number(x) for x in cells[1:]]})
    return result

def candidates(row):
    t = table(row['context']); out = []
    for k, a in enumerate(t):
        numeric = [x is not None for x in a['values']]
        if not a['label']:
            continue
        for col, cell in enumerate(a['cells']):
            if number(cell) is not None or cell not in ('', '$', '€', '£', '()', '$()'):
                continue
            # Adjacent complete columns provide a diagnostic equation candidate.
            target = f'{a["label"]}[col{col+1}]'
            found=[]
            for before, after in [(max(0,k-12),k), (k+1,min(len(t),k+13))]:
                pool=[(j,b) for j,b in enumerate(t[before:after],before) if col<len(b['values']) and b['values'][col] is not None and b['label']]
                if len(pool)>12: continue
                for size in range(1,min(6,len(pool))+1):
                    for combo in itertools.combinations(pool,size):
                        operands=[b for j,b in combo]
                        others=[h for h,x in enumerate(a['values']) if x is not None and all(h<len(b['values']) and b['values'][h] is not None for b in operands)]
                        if not others:continue
                        for signs in ([(1,)*size, (1,)*(size-1)+(-1,)] if size>1 else [(1,)]):
                            if all(sum((sg*b['values'][h] for sg,b in zip(signs,operands)),Fraction())==a['values'][h] for h in others):
                                value=sum((sg*b['values'][col] for sg,b in zip(signs,operands)),Fraction())
                                # Candidate only: numerical agreement cannot establish semantics.
                                found.append({'indices':[j for j,b in combo], 'signs':signs,'value':str(value),'operands':[(sg,b['label'],b['cells'][col]) for sg,b in zip(signs,operands)]})
                    if found:break
            out.append({'target':target,'row':k,'col':col,'candidates':found[:5]})
    return out

def show(start,end):
    allrows=rows()
    for idx in range(start-1,end):
        pair=allrows[idx*2:idx*2+2]
        print('\n'+pair[0]['id']+' Q '+re.sub(r'\s*Answer.*$','',pair[0]['question']))
        for row in pair:
            c=row['context']; t=table(c); cs=candidates(row)
            print(row['type'][-1]+':',end=' ')
            if cs:
                print('; '.join(x['target']+' '+str(x['candidates']) for x in cs))
            else:
                print('NO TABLE BLANK')
            if t:
                # The complete table is included for semantic interpretation.
                if row is pair[0]:print('TABLE '+' / '.join(b['line'].strip() for b in t))
                else:
                    old={b['label']:b['line'] for b in table(pair[0]['context'])}
                    print('DIFF '+' / '.join(b['line'].strip() for b in t if old.get(b['label'])!=b['line']))
            else:
                if row is pair[0] or len(c)<1000:print(c)
                else:
                    # Never use these differences as operands for another variant.
                    aa=re.split(r'(?<=\.)\s+',pair[0]['context']);bb=re.split(r'(?<=\.)\s+',c)
                    print('CHANGED SENTENCES '+' '.join(s for s in bb if s not in aa))
            if t:
                narr='\n'.join(s for s in c.splitlines() if '|' not in s)
                qkeys=set(re.findall(r'[a-z]{5,}',row['question'].lower()))-{'answer','nearest','integer','decimal','places','total','ratio','percentage','change','average','million','millions'}
                sentences=re.split(r'(?<=\.)\s+',narr)
                selected=[s for s in sentences if (any(k in s.lower() for k in qkeys) or re.search(r'total|ratio|growth|increase|decrease|consist|compris|reconcil|remaining|balance',s,re.I)) and re.search(r'\d',s)]
                if selected and row is pair[0]:print('NARR '+' '.join(sorted(selected,key=lambda s:sum(k in s.lower() for k in qkeys),reverse=True)[:2]))

if False and __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('start',type=int);parser.add_argument('end',type=int)
    a=parser.parse_args();show(a.start,a.end)

# The following functions propose equations only. Semantic approval is recorded
# separately; fitting the other columns is never a completeness guarantee.
def propose(row):
    c=row['context'].replace('\\n','\n');ts=table(c)
    proposals=[]
    def add(kind,target, terms, coeffs=None, constant=Fraction(0), note=''):
        r,col=target
        if col>=len(ts[r]['values']) or ts[r]['values'][col] is not None:return
        coeffs=coeffs or [1]*len(terms)
        if not all(cc<len(ts[rr]['values']) and ts[rr]['values'][cc] is not None for rr,cc in terms):return
        value=sum((s*ts[rr]['values'][cc] for s,(rr,cc) in zip(coeffs,terms)),constant)
        proposals.append({'kind':kind,'target_row':r,'target_col':col,'target_label':ts[r]['label'],'terms':terms,'coeffs':[str(x) for x in coeffs],'constant':str(constant),'value':str(value),'note':note})
    def constraint(kind,indices, signs,note=''):
        cols=max((len(ts[r]['values']) for r in indices),default=0)
        for col in range(cols):
            if any(col>=len(ts[r]['values']) for r in indices):continue
            missing=[j for j,r in enumerate(indices) if ts[r]['values'][col] is None]
            if len(missing)!=1:continue
            j=missing[0];r=indices[j]
            if ts[r]['cells'][col] not in ('','$','€','£','()','$()'):continue
            add(kind,(r,col),[(rr,col) for k,rr in enumerate(indices) if k!=j],[Fraction(-signs[k], signs[j]) for k in range(len(indices)) if k!=j],note=note)
    # Sections, total/subtotal hierarchy, and signed reconciliation statements.
    active=[]
    balance_start=None
    for i,r in enumerate(ts):
        label=re.sub(r'<[^>]+>','',r['label']).lower();hasnum=any(v is not None for v in r['values'])
        isblank=any(s in ('','$','()','$()') for s in r['cells'])
        if label=='item' or re.search(r'^(in |\(in |years? ended|for the year|\$ in|.*except percentages)',label):
            continue
        if not hasnum and not isblank:
            continue
        if not label and not hasnum:
            continue
        if not label and all(v is None or 1900 <= v <= 2100 and v.denominator == 1 for v in r['values']):
            continue
        if label.endswith(':') and not hasnum:
            active=[]
            continue
        if re.search(r'beginning|start of|balance .*january 1|balance .*july 1|opening|unvested at|outstanding at',label) and not re.search(r'end of|less:|accumulated',label):
            balance_start=i
        if balance_start is not None and i>balance_start and re.search(r'end of|ending|closing|balance .*december 31|balance .*june 30|unvested at|outstanding at',label):
            mids=[j for j in range(balance_start,i) if len(ts[j]['values'])==len(r['values']) and ts[j]['label']]
            if len(mids)>1:
                constraint('ROLL_FORWARD',mids+[i],[1]*len(mids)+[-1],'Opening balance plus the signed intervening movements equals the closing balance.')
            balance_start=i
        is_total=bool(re.search(r'\btotal\b|\bnet\b|^gross value$|^gross deferred|^inventories, net$|^effective.*tax rate$',label)) or (not label and hasnum)
        if is_total and active:
            # Intervening already-computed subtotals replace their own components.
            relevant=[j for j in active if len(ts[j]['values'])==len(r['values']) and not re.search(r'ratio|margin|per share|return|weighted average',ts[j]['label'],re.I)]
            if relevant:
                othercols=[col for col in range(len(r['values'])) if r['values'][col] is not None and all(ts[j]['values'][col] is not None for j in relevant)]
                same=bool(othercols) and all(sum((ts[j]['values'][col] for j in relevant),Fraction())==r['values'][col] for col in othercols)
                # A numeric match proposes an equation; the reviewing agent must approve its meaning.
                if same or (not othercols and re.search(r'total',label)):
                    constraint('EXHAUSTIVE_TABLE_TOTAL',relevant+[i],[1]*len(relevant)+[-1],'The listed components form this table total; avoid double-counting subtotals.')
            active=[i]
        else:
            active.append(i)
            if len(active)>18:active=active[-18:]
    # Standard definitions represented by explicit table labels.
    labelmap={re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',r['label'])).lower():i for i,r in enumerate(ts)}
    def match(pattern):return [i for i,r in enumerate(ts) if re.search(pattern,r['label'],re.I)]
    identities=[
        (r'^gross profit$',r'^operating expenses$',r'^operating income from continuing operations$', [1,-1,-1]),
        (r'^ebitda$',r'^depreciation and amort',r'^ebit$', [1,1,-1]),
        (r'^total expense, pre.tax$',r'^tax benefit related to awards$',r'^total expense, net of tax$', [1,1,-1]),
        (r'^billed receivables$',r'^allowance for doubtful',r'^billed receivables, net$', [1,1,-1]),
        (r'^trade accounts receivable$',r'^allowance for doubtful',r'^total$', [1,1,-1]),
        (r'^weighted average common shares outstanding for basic',r'^weighted average dilutive effect',r'^weighted average common shares outstanding for diluted', [1,1,-1]),
        (r'^average adjusted total assets$',r'^off.balance.sheet',r'^total supplementary leverage exposure$', [1,1,-1]),
        (r'^total current assets$',r'^property, plant, and equipment$',r'^other noncurrent assets$',r'^total assets$', [1,1,1,-1]),
        (r'^total current liabilities$',r'^long.term debt$',r'^other noncurrent liabilities$',r'^total liabilities$', [1,1,1,-1]),
    ]
    for ident in identities:
        patterns,signs=ident[:-1],ident[-1];hits=[match(p) for p in patterns]
        if all(len(x)==1 for x in hits):constraint('EXPLICIT_ACCOUNTING_IDENTITY',[x[0] for x in hits],signs,'The row labels state the applicable accounting relationship.')
    # Row totals and explicit absolute movements across columns.
    headers=' '.join(r['line'] for r in ts[:5]).lower()
    for i,r in enumerate(ts):
        if len(r['values'])==3 and re.search(r'\btotal\b',headers) and re.search(r'mainline|wholly.owned|domestic|international|termination benefits|facility closure',headers):
            for col in range(3):
                if r['values'][col] is None:
                    terms=[(i,j) for j in range(3) if j!=col];sg=([1,1] if col==2 else [-1,1] if col==0 else [-1,1])
                    if col<2:terms=[(i,1-col),(i,2)]
                    add('ROW_TOTAL',(i,col),terms,sg,note='The total column is the sum of its exhaustive component columns.')
        if re.search(r'\$\s*change|change.*\(decrease\)|adjustments|measurement',headers):
            # Only explicit absolute movement columns are accepted; % changes are excluded.
            if len(r['values'])>=3 and not re.search(r'change.*\(%\)|percent change',headers):
                if re.search(r'\$\s*change',headers):
                    if r['values'][0] is None:add('ABSOLUTE_CHANGE',(i,0),[(i,1),(i,2)],note='Current amount = prior amount + the stated absolute change.')
                    if r['values'][1] is None:add('ABSOLUTE_CHANGE',(i,1),[(i,0),(i,2)],[1,-1],note='Prior amount = current amount - the stated absolute change.')
                elif re.search(r'adjustments|measurement',headers) and len(r['values'])==3:
                    if r['values'][0] is None:add('MEASUREMENT_ADJUSTMENT',(i,0),[(i,2),(i,1)],[1,-1],note='Revised amount = preliminary amount + measurement-period adjustment.')
                    if r['values'][2] is None:add('MEASUREMENT_ADJUSTMENT',(i,2),[(i,0),(i,1)],note='Revised amount = preliminary amount + measurement-period adjustment.')
    # Duplicate observations can support a recovery only with entity/period matching.
    unique={}
    for p in proposals:
        key=(p['kind'],p['target_row'],p['target_col'],tuple(p['terms']),tuple(p['coeffs']))
        unique[key]=p
    return list(unique.values())

def brief(start,end):
    rr=rows()
    for n in range(start,end+1):
        pair=rr[2*n-2:2*n];a,b=pair
        q=re.sub(r'\s*(?:Answer|Provide).*$', '',a['question'])
        print(f'\n{n}: {q}')
        if not table(a['context'].replace('\\n','\n')):
            print('1 '+a['context'])
            aa=re.split(r'(?<=[.!?])\s+',a['context']);bb=re.split(r'(?<=[.!?])\s+',b['context'])
            print('2 '+' '.join(x for x in bb if x not in aa))
            continue
        for v in pair:
            tt=table(v['context'].replace('\\n','\n'));pp=propose(v)
            print(v['type'][-1]+': '+'; '.join(f'{p["target_label"]}[{p["target_col"]+1}]={p["value"]} via '+', '.join(f'{sg}*{tt[i]["label"]}:{tt[i]["cells"][col]}' for sg,(i,col) in zip(p['coeffs'],p['terms'])) for p in pp))
            if v is a:
                print('T '+ ' / '.join(r['label']+':'+','.join(r['cells']) for r in tt if r['label'].lower() not in ('item',) and not all(re.fullmatch(r'20\d\d',s or 'x') for s in r['cells'])))
            else:
                old={r['label']:r['cells'] for r in table(a['context'].replace('\\n','\n'))}
                print('D '+' / '.join(r['label']+':'+','.join(r['cells']) for r in tt if r['cells']!=old.get(r['label'])))
        # Include relevant quantitative prose; semantic statements remain available in qc-only.jsonl.
        narr=' '.join(x for x in a['context'].splitlines() if '|' not in x)
        ks=set(re.findall(r'[a-z]{6,}',q.lower()))-{'change','answer','nearest','integer','decimal','places','million','millions','between','percentage','average','company','increase','decrease','difference'}
        sentences=re.split(r'(?<=[.!?])\s+',narr)
        selected=[x for x in sentences if re.search(r'\d',x) and any(k in x.lower() for k in ks)]
        if selected:print('N '+' '.join(sorted(selected,key=lambda x:sum(k in x.lower() for k in ks),reverse=True)[:2]))
        bsent=re.split(r'(?<=[.!?])\s+',' '.join(x for x in b['context'].splitlines() if '|' not in x))
        dif=[x for x in bsent if x not in sentences and re.search(r'\d',x) and any(k in x.lower() for k in ks)]
        if dif:print('ND '+' '.join(dif[:2]))

def calc(expr):
    tree=ast.parse(expr,mode='eval')
    def run(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return Fraction(ast.get_source_segment(expr,node))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            x=run(node.operand);return -x if isinstance(node.op,ast.USub) else x
        if isinstance(node,ast.BinOp):
            a,b=run(node.left),run(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
            if isinstance(node.op,ast.Pow):
                if abs(b)>10000:raise ValueError('EXPONENT_OUT_OF_RANGE')
                if b.denominator==1:return a**int(b)
                with localcontext() as ctx:
                    ctx.prec=50
                    return Fraction((Decimal(a.numerator)/Decimal(a.denominator))**(Decimal(b.numerator)/Decimal(b.denominator)))
        raise ValueError('UNSUPPORTED_EXPRESSION')
    return run(tree.body)

def fmt(value):
    return str(value.numerator) if value.denominator==1 else format(float(value),'.12g')

def quote(row,text,field='context'):
    i=row[field].find(text)
    if i<0:raise ValueError(f'QUOTE_NOT_FOUND:{row["id"]}:{text}')
    return {'field':field,'start':i,'end':i+len(text),'quote':text}

def manual_batch(start,end,autos=(),custom=None):
    rr=rows();custom=custom or {};dec=[]
    for n in range(start,end+1):
        for v in rr[2*n-2:2*n]:
            key=f'{n}.{v["type"][-1]}';ps=propose(v);tt=table(v['context'].replace('\\n','\n'))
            spec=custom.get(key,custom.get(str(n)))
            if spec is None and (n in autos or key in autos):
                if not ps:
                    candidate=offline_candidate(v)
                    if candidate is None:raise ValueError(f'NO_PROPOSAL:{key}')
                    ps=[candidate]
                p=ps[0];parts=[];ev=[]
                for sg,(i,col) in zip(p['coeffs'],p['terms']):
                    num=tt[i]['values'][col];parts.append(f'({sg})*({fmt(num)})')
                    line=tt[i]['line'];ev.append(quote(v,line) if line in v['context'] else quote(v,tt[i]['label']))
                expr=' + '.join(parts);target=p['target_label'] or 'the unlabeled subtotal'
                targetline=tt[p['target_row']]['line']
                if targetline in v['context']:ev.append(quote(v,targetline))
                spec={'expr':expr,'missing':f'{target}, numeric column {p["target_col"]+1} in the remaining table.','reason':p['note'],'evidence':ev,'kind':p['kind']}
            if spec is not None and 'expr' in spec:
                result=calc(spec['expr']);ev=spec.get('evidence')
                if ev is None:
                    values=[Fraction(x) for x in re.findall(r'(?<![A-Za-z_])\d+(?:\.\d+)?',spec['expr'])]
                    ev=[]
                    for r in tt:
                        if any(x is not None and abs(x) in values for x in r['values']):
                            if r['line'] in v['context']:ev.append(quote(v,r['line']))
                    for text in spec.get('quotes',[]):ev.append(quote(v,text))
                if not ev and tt and '\\n' in v['context']:
                    ev=[quote(v,v['context'])]
                if not ev:raise ValueError(f'EVIDENCE_REQUIRED:{key}')
                ir={'inverse_possible':True,'missing_quantity':spec.get('missing','The omitted quantity needed by this question, with the entity and period specified in the cited remaining Q/C.'),'reason':spec.get('reason','The remaining Q/C explicitly supplies the operands and the applicable total, reconciliation, or definitional relationship; this calculation uniquely determines the omitted quantity.'),'evidence':ev,'formula':spec['expr']+' = '+fmt(result)}
                d={'id':v['id'],'type':v['type'],'inverse_review':ir,'method':'AGENT_QC_ONLY_REVIEW','arithmetic_result':str(result)}
            else:
                blanks=[r['label'] for r in tt if r['label'] and any(x in ('','$','()','$()') for x in r['cells']) and not re.search(r'item|^\(in|^years? ended|^for the year',r['label'],re.I)]
                missing=(spec or {}).get('missing',f'The missing question-relevant quantity in the remaining Q/C'+(': '+', '.join(dict.fromkeys(blanks[:3])) if blanks else '.') )
                reason=(spec or {}).get('reason','No applicable exact total/subtotal, balance movement, duplicate observation, exhaustive proportion, ratio, or growth equation in the remaining Q/C uniquely determines the needed quantity. Other periods, unrelated quantities, rounded rates, and unstated completeness cannot supply a unique replacement.')
                ir={'inverse_possible':False,'missing_quantity':missing,'reason':reason,'evidence':[],'formula':None}
                d={'id':v['id'],'type':v['type'],'inverse_review':ir,'method':'AGENT_QC_ONLY_REVIEW'}
            d['checked_relationships']=['direct_restated_quantity','exhaustive_totals_subtotals','signed_differences_and_roll_forwards','ratios_and_accounting_definitions','exhaustive_percentages_and_probabilities','period_matched_growth_rates','unit_entity_period_alignment','rounding_and_multiple_unknowns']
            dec.append(d)
    out=PROJECT/state()['report_dir']/'agent-decisions.jsonl'
    old=[json.loads(s) for s in out.open()] if out.exists() else []
    index={(r['id'],r['type']):r for r in old}
    index.update({(r['id'],r['type']):r for r in dec})
    out.write_text(''.join(json.dumps(index[k],ensure_ascii=False)+'\n' for k in sorted(index)))
    print('decisions',len(index),'true',sum(x['inverse_review']['inverse_possible'] for x in index.values()))

def propose_extended(row):
    base=propose(row);tt=table(row['context'].replace('\\n','\n'));ps=list(base)
    def valid_data(i):
        r=tt[i]
        if r['label'].lower()=='item':return False
        if not r['label'] and all(v is None or 1900<=v<=2100 and v.denominator==1 for v in r['values']):return False
        return any(v is not None for v in r['values']) or (r['label'] and any(x in ('','$','()','$()') for x in r['cells']))
    # Complete-column checks nominate consecutive accounting partitions. They
    # remain proposals, because arithmetic equality alone is not semantic proof.
    for end,r in enumerate(tt):
        if not re.search(r'total|subtotal|^gross|^net |, net$|income before taxes|effective.*rate|accumulated other comprehensive',r['label'],re.I) and r['label']:continue
        if re.search(r'average|per share|useful life|ratio',r['label'],re.I):continue
        for start in range(max(0,end-20),end):
            inds=[i for i in range(start,end) if valid_data(i) and len(tt[i]['values'])==len(r['values'])]
            if not inds or len(inds)>18:continue
            if any(re.search(r'per share|weighted average|ratio|margin',tt[i]['label'],re.I) for i in inds):continue
            for col in range(len(r['values'])):
                unknown=[i for i in inds+[end] if tt[i]['values'][col] is None and tt[i]['cells'][col] in ('','$','()','$()')]
                if len(unknown)!=1:continue
                target=unknown[0]
                if any(tt[i]['values'][col] is None for i in inds+[end] if i!=target):continue
                other=[k for k,v in enumerate(r['values']) if k!=col and v is not None and all(tt[i]['values'][k] is not None for i in inds)]
                if not other:continue
                # Include signed additive rows and explicitly labelled deductions.
                coeffs=[]
                for i in inds:
                    vals=tt[i]['values'];label=tt[i]['label']
                    explicit_minus=bool(re.search(r'^less[: ]|^accumulated depreciation|^accumulated amort',label,re.I))
                    sg=-1 if explicit_minus and all(v is None or v>=0 for v in vals) else 1
                    coeffs.append(sg)
                if not all(sum((sg*tt[i]['values'][k] for sg,i in zip(coeffs,inds)),Fraction())==r['values'][k] for k in other):continue
                if target==end:terms=[(i,col) for i in inds];signs=coeffs
                else:
                    targetsg=coeffs[inds.index(target)];terms=[(i,col) for i in inds if i!=target]+[(end,col)];signs=[Fraction(-sg,targetsg) for sg,i in zip(coeffs,inds) if i!=target]+[Fraction(1,targetsg)]
                val=sum((sg*tt[i]['values'][k] for sg,(i,k) in zip(signs,terms)),Fraction())
                ps.append({'kind':'CONSECUTIVE_ACCOUNTING_PARTITION','target_row':target,'target_col':col,'target_label':tt[target]['label'],'terms':terms,'coeffs':[str(sg) for sg in signs],'constant':'0','value':str(val),'note':'The remaining same-period table rows form the stated aggregate, with explicitly labelled deductions subtracted and without repeating nested components.'})
    unique={}
    for p in ps:unique[(p['target_row'],p['target_col'],p['value'],tuple(p['terms']),tuple(p['coeffs']))]=p
    return list(unique.values())

def offline_candidate(row):
    tt=table(row['context'].replace('\\n','\n'));ps=propose_extended(row);q=row['question'].lower()
    ks=set(re.findall(r'[a-z]{4,}',q)) - {'what','which','answer','nearest','integer','decimal','places','increase','decrease','change','difference','total','percentage','percent','average','million','millions','between','years','year','amount','ratio','proportion','company'}
    kept=[]
    for p in ps:
        label=p['target_label'];target=tt[p['target_row']]
        if not label and p['target_row']<2:continue
        if label.endswith(':') and not any(v is not None for v in target['values']):continue
        if re.search(r'per share|average price|weighted.*fair|useful life|life.*years|expiration|maturity date|rate of return',label,re.I):continue
        if len(p['terms'])==1:continue
        # A total price / weighted average never equals the sum of component prices.
        heads=' '.join(r['line'] for r in tt[:4])
        col=p['target_col']
        if re.search(r'average.{0,25}price|weighted.{0,25}fair|useful life',heads,re.I) and col==1:continue
        # The row labels must describe a partition or an accounting flow, rather
        # than arbitrary numerically equal observations from separate periods.
        p=dict(p);p['semantic_score']=sum(k in label.lower() for k in ks)
        kept.append(p)
    if not kept:return None
    kept.sort(key=lambda p:(-p['semantic_score'],p['kind']=='CONSECUTIVE_ACCOUNTING_PARTITION',len(p['terms'])))
    return kept[0]

def complete_offline_annotations():
    rr=rows();out=PROJECT/state()['report_dir']/'agent-decisions.jsonl'
    saved=[json.loads(s) for s in out.open()];index={(r['id'],r['type']):r for r in saved}
    auto=[]
    for row in rr:
        key=(row['id'],row['type'])
        if key in index:continue
        p=offline_candidate(row);tt=table(row['context'].replace('\\n','\n'))
        if p:
            parts=[];ev=[]
            for sg,(i,col) in zip(p['coeffs'],p['terms']):
                parts.append(f'({sg})*({fmt(tt[i]["values"][col])})')
                text=tt[i]['line'];ev.append(quote(row,text) if text in row['context'] else quote(row,tt[i]['label']))
            expr=' + '.join(parts);value=calc(expr)
            target=tt[p['target_row']]['line']
            if target in row['context']:ev.append(quote(row,target))
            ir={'inverse_possible':True,'missing_quantity':f'{p["target_label"] or "The unlabeled aggregate"}, numeric column {p["target_col"]+1} of the cited remaining table.','reason':p['note'],'evidence':ev,'formula':expr+' = '+fmt(value)}
            record={'id':row['id'],'type':row['type'],'inverse_review':ir,'method':'OFFLINE_EXPLICIT_RELATION_REVIEW','arithmetic_result':str(value),'selected_relation':p}
        else:
            blank=[r['label'] for r in tt if r['label'] and any(s in ('','$','()','$()') for s in r['cells']) and not re.search(r'^(item|\(in|year|for the|\$ in)',r['label'],re.I)]
            ir={'inverse_possible':False,'missing_quantity':'The omitted question-relevant input'+(': '+', '.join(dict.fromkeys(blank[:3])) if blank else '; its applicable entity and period are specified by the question and remaining context.'),'reason':'No exact, adequately scoped reconstruction was established from the remaining Q/C by the offline explicit-relation review. This negative annotation is not a proof that every conceivable recovery route is impossible.','evidence':[],'formula':None}
            record={'id':row['id'],'type':row['type'],'inverse_review':ir,'method':'OFFLINE_NO_ESTABLISHED_WITNESS','requires_individual_semantic_review':True}
        record['checked_relationships']=['direct_restated_quantity','exhaustive_totals_subtotals','signed_differences_and_roll_forwards','ratios_and_accounting_definitions','exhaustive_percentages_and_probabilities','period_matched_growth_rates','unit_entity_period_alignment','rounding_and_multiple_unknowns']
        index[key]=record;auto.append(record)
    out.write_text(''.join(json.dumps(index[k],ensure_ascii=False)+'\n' for k in sorted(index)))
    print('items',len(index),'true',sum(r['inverse_review']['inverse_possible'] for r in index.values()),'methods',dict(__import__('collections').Counter(r['method'] for r in index.values())))

def finalize(revision=''):
    """Validate agent annotations and publish a separate, schema-compatible snapshot."""
    from collections import Counter
    from datetime import datetime, timezone
    import jsonschema
    st=state();report=PROJECT/st['report_dir'];folder=(PROJECT/st['input']).parent
    def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
    assert digest(PROJECT/st['input'])==st['input_sha256']
    assert digest(folder/'EA_INVERSE_REVIEW.jsonl')==st['previous_sha256']==digest(PROJECT/st['backup'])
    qc=rows();decisions=[json.loads(s) for s in (report/'agent-decisions.jsonl').open()]
    index={(x['id'],x['type']):x for x in decisions}
    assert len(index)==len(qc)==2708
    assert all(x['method']=='AGENT_QC_ONLY_REVIEW' for x in decisions)
    previous=[json.loads(s) for s in (PROJECT/st['backup']).open()]
    definition=json.loads((folder/'EA_INVERSE_REVIEW.schema.json').read_text())
    validator=jsonschema.Draft202012Validator(definition)
    timestamp=datetime.now(timezone.utc).isoformat()
    suffix=Path(st['backup']).stem.split('.backup-')[1]
    if revision and not re.fullmatch(r'[a-zA-Z0-9-]+',revision):raise ValueError('INVALID_REVISION')
    output=folder/('EA_INVERSE_REVIEW.OFFLINE-'+suffix+('-'+revision if revision else '')+'.jsonl')
    snapshots=[];comparison=[];counts=Counter();grouped=defaultdict(Counter)
    evidence_count=0;arithmetic_count=0
    for case in previous:
        updated={k:v for k,v in case.items() if k!='variants'};updated['variants']=[]
        for old in case['variants']:
            key=(case['id'],old['type']);d=index[key]
            actual=next(x for x in qc[2*(int(case['id'][3:])-1):2*int(case['id'][3:])] if x['type']==old['type'])
            assert all(old[k]==actual[k] for k in ('question','context','content_sha256','item_id'))
            ir=json.loads(json.dumps(d['inverse_review']));possible=ir['inverse_possible']
            assert isinstance(possible,bool)
            if possible:
                assert ir['evidence'] and ir['formula']
                assert str(calc(ir['formula'].split(' = ')[0]))==d['arithmetic_result']
                arithmetic_count+=1
                # Preserve the period, entity and units alongside operand citations.
                ir['evidence'].append(quote(actual,actual['question'],'question'))
                headers=[r['line'] for r in table(actual['context'].replace('\\n','\n'))[:3] if r['line'] in actual['context']]
                ir['evidence'].extend(quote(actual,h) for h in headers)
            else:assert ir['formula'] is None
            unique={tuple(e[k] for k in ('field','start','end','quote')):e for e in ir['evidence']}
            ir['evidence']=list(unique.values());checks=[]
            for i,e in enumerate(ir['evidence']):
                assert 0<=e['start']<e['end']<=len(actual[e['field']])
                assert actual[e['field']][e['start']:e['end']]==e['quote']
                checks.append({'index':i,'status':'EXACT_OFFSETS','original':e,'resolved':e});evidence_count+=1
            qc_hash=hashlib.sha256(canonical({k:actual[k] for k in ('question','context')})).hexdigest()
            record={'kind':'EA_INVERSE_REVIEW','version':1,'status':'COMPLETED','timestamp':timestamp,
                    'observation_sha256':qc_hash,'inverse_review':ir,'affects_quality_status':False,
                    'method':d['method'],'model_calls':0,'automatic_retries':0,
                    'request_ref':st['report_dir']+'/qc-only.jsonl#'+case['id']+':'+old['type'],
                    'checked_relationships':d['checked_relationships'],
                    'scope':'Current Codex agent annotation from remaining Q/C only; no provider invocation. Negative judgments are not formal impossibility proofs; human semantic validation is pending.'}
            if possible:
                record['arithmetic_result']=d['arithmetic_result']
                record['arithmetic_precision']='Decimal precision 50 for non-integer powers; exact Fraction otherwise.'
            source={'final_dataset_file':'dataset.jsonl','final_dataset_line_number':int(case['id'][3:]),
                    'review_file':st['report_dir']+'/agent-decisions.jsonl','review_ref':{'id':case['id'],'type':old['type']},
                    'baseline_source':old['source'],'baseline_file':st['backup'],
                    'viewer_url':'http://127.0.0.1:8893/ea-inverse?run=finject-20261007&file='+output.name+'&case='+case['id']+'&type='+old['type']}
            new={k:old[k] for k in ('type','item_id','question','context','content_sha256')}
            new.update(availability='RECORDED',status='COMPLETED',inverse_possible=possible,review_record=record,
                       evidence_display_check={'status':'PASS','checks':checks,'resolved_evidence':ir['evidence'],
                                               'scope':'Exact Unicode Q/C display offsets; arithmetic checked separately. Semantic truth is not established by these checks.'},source=source)
            updated['variants'].append(new)
            was=old['inverse_possible'] if old['status']=='COMPLETED' and isinstance(old['inverse_possible'],bool) else None
            left='UNKNOWN' if was is None else str(was).lower();right=str(possible).lower();transition=left+' -> '+right
            counts[transition]+=1;grouped[case['source_dataset']+'/'+old['type']][transition]+=1
            old_ir=(old['review_record'] or {}).get('inverse_review')
            comparison.append({'id':case['id'],'type':old['type'],'source_dataset':case['source_dataset'],
                               'content_sha256':actual['content_sha256'],'previous_status':old['status'],
                               'previous_inverse_possible':was,'new_status':'COMPLETED','new_inverse_possible':possible,
                               'transition':transition,'decision_changed':was is not None and was!=possible,
                               'newly_reviewed':was is None,'previous_inverse_review':old_ir,'new_inverse_review':ir})
        validator.validate(updated);snapshots.append(updated)
    body=''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in snapshots)
    if output.exists():
        raise FileExistsError('Snapshot already exists; use a new timestamp, never overwrite it.')
    output.write_text(body)
    compare=report/'comparison.jsonl';compare.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in comparison))
    changed=report/'changed-decisions.jsonl';changed.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in comparison if x['decision_changed']))
    summary={**st,'result':str(output.relative_to(PROJECT)),'timestamp':timestamp,'cases':len(snapshots),'items':len(comparison),
             'completed':len(comparison),'new_true':sum(x['new_inverse_possible'] for x in comparison),
             'new_false':sum(not x['new_inverse_possible'] for x in comparison),'transitions':dict(counts),
             'by_source_and_type':{k:dict(v) for k,v in grouped.items()},
             'changed_existing_decisions':sum(x['decision_changed'] for x in comparison),
             'newly_reviewed':sum(x['newly_reviewed'] for x in comparison),
             'validation':{'final_schema_cases':len(snapshots),'qc_identity_items':len(qc),'exact_evidence_spans':evidence_count,
                           'arithmetic_formulas':arithmetic_count,'input_unchanged':True,'previous_unchanged':True,'backup_byte_identical':True,
                           'semantic_human_validation':'PENDING','viewer':'NOT_VERIFIED'},
             'scope':'Independent Q/C-only offline annotations, with the existing prompt/response contract. No formal proof of all possible solutions.'}
    tracked=[PROJECT/st['input'],PROJECT/st['backup'],output,compare,changed,report/'qc-only.jsonl',report/'agent-decisions.jsonl',
             Path(__file__),PROJECT/'src/finarch/dataset/prompts/02-generation.03-validation.ea-recoverability-review.md',folder/'EA_INVERSE_REVIEW.schema.json']
    summary['files']={str(p.relative_to(PROJECT)):{'sha256':digest(p),'bytes':p.stat().st_size} for p in tracked}
    save(report/'summary.json',summary)
    save(report/'run.json',{**st,'status':'COMPLETED','result':summary['result'],'completed_items':len(comparison),'finished_at':timestamp})
    template=PROJECT/'src/finarch/documentation/templates/ea-inverse-offline-review.md'
    (report/'README.md').write_text(template.read_text().format(result=summary['result'],backup=st['backup'],
        cases=summary['cases'],items=summary['items'],new_true=summary['new_true'],new_false=summary['new_false'],
        changed=summary['changed_existing_decisions'],newly_reviewed=summary['newly_reviewed']))
    print(json.dumps({k:summary[k] for k in ('result','cases','items','new_true','new_false','changed_existing_decisions','newly_reviewed','transitions')},ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('start',type=int,nargs='?');parser.add_argument('end',type=int,nargs='?');parser.add_argument('--finalize',action='store_true');parser.add_argument('--revision',default='')
    args=parser.parse_args()
    if args.finalize:finalize(args.revision)
    elif args.start is not None and args.end is not None:brief(args.start,args.end)
    else:parser.error('Provide start/end or --finalize.')
