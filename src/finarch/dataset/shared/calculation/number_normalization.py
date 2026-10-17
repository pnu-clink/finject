"""Explicit numeric-format rules, before Python execution; never rewrite source/code."""
import copy
import hashlib
import json
from pathlib import Path
import re
traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced

RULES_FILE=Path(__file__).with_name('number-rules.json')


def regex_replace(value,rule):
    if re.fullmatch(rule['match'],value):return re.sub(rule['pattern'],rule['replacement'],value)
    return value


def literal_replace(value,rule):
    return value.replace(rule['from'],rule['to'])


def strip_whitespace(value,rule):
    return value.strip()


# Only registered Python functions are allowed; rules cannot eval/import arbitrary code.
TRANSFORMS={'regex_replace':regex_replace,'literal_replace':literal_replace,'strip_whitespace':strip_whitespace}


def remove_adjacent_currency_prefix(text, fact, context, rule):
    """Correct only a verified adjacent source symbol; preserve the numeric span."""
    span=fact.get('span',[]);symbol=rule['symbol']
    if not isinstance(context,str) or len(span)!=2:return text
    start,end=span
    if type(start) is not int or type(end) is not int or not 0<=start<end<=len(context):return text
    actual=context[start:end]
    if (start>=len(symbol) and context[start-len(symbol):start]==symbol
            and text==symbol+actual and re.fullmatch(r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?',actual)):
        return actual
    return text


SOURCE_TRANSFORMS={'remove_adjacent_currency_prefix':remove_adjacent_currency_prefix}


def validate_rules(rules):
    if not isinstance(rules.get('version'),int) or not isinstance(rules.get('rules'),list):
        raise ValueError('INVALID_NUMBER_RULES')
    seen=set()
    for rule in rules['rules']:
        if not rule.get('id') or rule['id'] in seen or type(rule.get('enabled')) is not bool:
            raise ValueError('INVALID_NUMBER_RULE')
        seen.add(rule['id'])
        if rule.get('kind') not in TRANSFORMS:raise ValueError('UNREGISTERED_NUMBER_TRANSFORM')
        if rule['kind']=='regex_replace':
            re.compile(rule['match']);re.compile(rule['pattern'])
            if not isinstance(rule.get('replacement'),str):raise ValueError('INVALID_NUMBER_REPLACEMENT')
        elif rule['kind']=='literal_replace':
            if not isinstance(rule.get('from'),str) or not rule['from'] or not isinstance(rule.get('to'),str):
                raise ValueError('INVALID_NUMBER_REPLACEMENT')
    if not isinstance(rules.get('source_rules',[]),list):raise ValueError('INVALID_SOURCE_RULES')
    for rule in rules.get('source_rules',[]):
        if not rule.get('id') or rule['id'] in seen or type(rule.get('enabled')) is not bool:
            raise ValueError('INVALID_SOURCE_RULE')
        seen.add(rule['id'])
        if rule.get('kind') not in SOURCE_TRANSFORMS:raise ValueError('UNREGISTERED_SOURCE_TRANSFORM')
        if not isinstance(rule.get('symbol'),str) or not rule['symbol']:raise ValueError('INVALID_SOURCE_SYMBOL')


def load_rules():
    raw=RULES_FILE.read_bytes();rules=json.loads(raw)
    validate_rules(rules)
    return rules,hashlib.sha256(raw).hexdigest()


@traced()
def normalize_number(value,rules,steps=None):
    # [NN01] docs/02-architecture.md#NN01 They change the expression that fits the rule of thumb and don't interpret the meaning of the numbers.
    if not isinstance(value,str):raise ValueError('NUMBER_STRING_REQUIRED')
    normalized=value;applied=[]
    for rule in rules['rules']:
        if not rule['enabled']:continue
        operation=TRANSFORMS.get(rule['kind'])
        if operation is None:raise ValueError('UNREGISTERED_NUMBER_TRANSFORM')
        # Every enabled rule receives the previous rule's output, even after a match.
        new=operation(normalized,rule)
        if not isinstance(new,str):raise ValueError('NUMBER_TRANSFORM_MUST_RETURN_STRING')
        if steps is not None:steps.append({'rule_id':rule['id'],'kind':rule['kind'],
                                          'before':normalized,'after':new,'changed':new!=normalized})
        if new!=normalized:applied.append(rule['id'])
        normalized=new
    if ',' in normalized:raise ValueError('UNSUPPORTED_COMMA_FORMAT')
    return normalized,applied


@traced()
def align_source_text(fact,context,rules):
    # [NN05] docs/02-architecture.md#NN05 After verifying the mark difference, which is identified by the ZIP code, the strict original contrast continues.
    text=fact['text'];steps=[];applied=[]
    for rule in rules.get('source_rules',[]):
        if not rule['enabled']:continue
        operation=SOURCE_TRANSFORMS.get(rule['kind'])
        if operation is None:raise ValueError('UNREGISTERED_SOURCE_TRANSFORM')
        new=operation(text,fact,context,rule)
        steps.append({'rule_id':rule['id'],'before':text,'after':new,'changed':new!=text})
        if new!=text:applied.append(rule['id'])
        text=new
    return text,applied,steps


@traced()
def prepare_numeric_values(program):
    # [NN02] docs/02-architecture.md#NN02 It separates the source and the computation value and makes the conversion power.
    rules,digest=load_rules();prepared=copy.deepcopy(program)
    audit={'status':'PASS','rules_version':rules['version'],'rules_sha256':digest,
           'rules':rules['rules'],'source_rules':rules.get('source_rules',[]),'facts':[]}
    for name,fact in prepared['facts'].items():
        entry={'fact_id':name,'source_text':fact['text'],'original_value':fact['value'],
               'python_value':None,'applied_rules':[],'steps':[]}
        try:
            text,source_applied,source_steps=align_source_text(fact,prepared.get('question' if fact.get('origin') == 'QUESTION' else 'context'),rules)
            entry.update(validated_source_text=text,source_applied_rules=source_applied,source_steps=source_steps)
            fact['text']=text
            value,applied=normalize_number(fact['value'],rules,entry['steps'])
            entry.update(python_value=value,applied_rules=applied)
            fact['value']=value
        except ValueError as error:
            entry['error']=str(error);audit['status']='FAIL'
        audit['facts'].append(entry)
    return prepared,audit,rules
