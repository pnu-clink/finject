"""Extract original numeric spans without launching a pipeline."""
import re

def numeric_index(context):
    pattern=r'(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?'
    return [{'text':m.group(),'span':[m.start(),m.end()],
             'nearby':context[max(0,m.start()-45):min(len(context),m.end()+45)]}
            for m in re.finditer(pattern,context)]

