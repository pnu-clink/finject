"""Fixed code-generation responses; mapping declarations are check evidence."""

from jsonschema import Draft202012Validator


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string"}
CONTRACT_VERSION = 'native-preprocessed-adapter-v3'
POINTER = {"type": "string", "pattern": r"^(|/.*)$"}
LOCATION = obj({"root": {"type": "string", "enum": ["record", "question"]}, "path": POINTER})

SOURCE = obj({
    "records_path": POINTER,
    "questions_path": POINTER,
    "include": {"type": "array", "items": obj({
        "path": POINTER, "equals": {"anyOf": [{"type": kind} for kind in ("string", "number", "boolean", "null")]}})},
})
ADAPTER = obj({
    "question": LOCATION,
    "answer": LOCATION,
    "context": {"type": "array", "minItems": 1, "items": obj({
        "root": {"type": "string", "enum": ["record", "question"]}, "path": POINTER,
        "kind": {"type": "string", "enum": ["text", "table"]}})},
    "answer_format": obj({
        "prefix": {"type": "string", "enum": ["", "$", "EUR", "USD", "GBP", "\u00a3", "\u20ac"]},
        "suffix": {"type": "string", "enum": ["", "%"]},
        "grouping_separator": {"type": "string", "enum": ["", ","]},
        "parentheses_negative": {"type": "boolean"},
    }),
})
PROVENANCE = obj({
    "dataset": TEXT,
    "required_fields": {"type": "array", "items": {"type": "string", "enum": ["dataset", "name", "sha256"]}},
})
PREPROCESS_SOURCE = obj({**SOURCE['properties'], 'fields': ADAPTER})


def response_schema(stage):
    specification = {1: PREPROCESS_SOURCE, 2: ADAPTER, 3: PROVENANCE}[stage]
    if stage == 3:
        # Python has already checked the complete, fixed registration inputs.
        # Unlike raw-field discovery, this stage has no missing-information path.
        return obj({"status": {"type": "string", "enum": ["ready"]},
                    "reason": TEXT, "specification": specification,
                    "implementation": {"type": "string", "minLength": 1}})
    return obj({"status": {"type": "string", "enum": ["ready", "needs_information"]},
                "reason": TEXT, "specification": {"anyOf": [specification, {"type": "null"}]},
                "implementation": {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]}})


def validate_response(stage, value):
    schema = response_schema(stage)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    if value["status"] != "ready":
        raise NeedsInformation(value["reason"] or "The raw data needs clarification.")
    if value["specification"] is None:
        raise ValueError("READY_SPECIFICATION_REQUIRED")
    if not value['implementation']:
        raise ValueError('READY_PYTHON_IMPLEMENTATION_REQUIRED')
    return value["specification"]


class NeedsInformation(ValueError):
    """An essential mapping is unavailable; retrying must not invent it."""
