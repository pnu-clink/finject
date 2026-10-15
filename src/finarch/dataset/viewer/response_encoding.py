"""Encode directly to UTF-8, retaining the standard encoder as a fallback."""
import json
import math


def encode(value, *, sorted_keys=False):
    try:
        import orjson
    except ImportError:
        return json.dumps(value,sort_keys=sorted_keys,ensure_ascii=False).encode()
    def compatible(v):
        if isinstance(v,float):return math.isfinite(v)
        if isinstance(v,dict):return all(isinstance(k,(str,int,bool,type(None))) and compatible(x) for k,x in v.items())
        if isinstance(v,(list,tuple)):return all(compatible(x) for x in v)
        return True
    if compatible(value):
        try:
            return orjson.dumps(value,option=orjson.OPT_NON_STR_KEYS | (orjson.OPT_SORT_KEYS if sorted_keys else 0))
        except TypeError:
            pass
    return json.dumps(value,sort_keys=sorted_keys,ensure_ascii=False).encode()
