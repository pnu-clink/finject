"""Adapt the provider schema; keep uniqueness enforced by the canonical validator."""


def const_type(value):
    """Providers require an explicit JSON type even when a canonical schema uses const."""
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, int):
        return 'integer'
    if isinstance(value, float):
        return 'number'
    if isinstance(value, str):
        return 'string'
    if value is None:
        return 'null'
    return None


def for_openai(schema):
    """Preserve property names and describe unsupported array uniqueness in English."""
    if isinstance(schema, list):
        return [for_openai(value) for value in schema]
    if not isinstance(schema, dict):
        return schema
    result = {}
    for key, value in schema.items():
        if key == 'uniqueItems':
            continue
        if key in ('properties', '$defs', 'definitions', 'patternProperties'):
            result[key] = {name: for_openai(child) for name, child in value.items()}
        elif key in ('enum', 'const', 'default', 'examples'):
            result[key] = value
        else:
            result[key] = for_openai(value)
    if schema.get('uniqueItems'):
        result['description'] = (schema.get('description', '') + ' All items in this array must be unique.').strip()
    if 'type' not in result and 'const' in schema:
        inferred = const_type(schema['const'])
        if inferred is not None:
            result['type'] = inferred
    return result
