"""Self-contained dataset archive; production validation and ratings stay separate."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

TYPES = ('IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY',
         'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')
FORMAT = 'finarch-generated-dataset-v1'


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Rating(Record):
    item_id: str
    content_sha256: str
    reviewer: str
    decision: Literal['APPROVED', 'REJECTED', 'PENDING']
    confirmed: bool
    comment: str = ''
    updated_at: str | None = None


class Annotation(Record):
    status: Literal['UNREVIEWED', 'ANNOTATED', 'PASS'] = 'UNREVIEWED'
    ratings: list[Rating] = Field(default_factory=list)


class Item(Record):
    item_id: str
    type: str
    question: str | None
    context: str | None
    content_sha256: str | None
    automatic_validation: dict[str, Any]
    production_review: dict[str, Any]
    annotation: Annotation = Field(default_factory=Annotation)
    source: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetCase(Record):
    format: Literal['finarch-generated-dataset-v1'] = FORMAT
    run: str
    id: str
    source_input: dict[str, Any]
    original: Item
    variants: list[Item]
    production_selection: dict[str, Any]

    @model_validator(mode='after')
    def check_items(self):
        import hashlib
        import json
        if self.original.type != 'ORIGINAL' or tuple(v.type for v in self.variants) != TYPES:
            raise ValueError('EXACT_ORIGINAL_AND_SEVEN_TYPES_REQUIRED')
        for item in [self.original, *self.variants]:
            if item.item_id != f'{self.run}:{self.id}:{item.type}':
                raise ValueError('ITEM_ID_MISMATCH')
            complete = all(isinstance(v, str) for v in (item.question, item.context))
            expected = hashlib.sha256(json.dumps({'question': item.question, 'context': item.context},
                ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() if complete else None
            if item.content_sha256 != expected:
                raise ValueError('CONTENT_HASH_MISMATCH')
            if item.automatic_validation['status'] == 'PASS' and not complete:
                raise ValueError('PASS_WITHOUT_QUESTION_CONTEXT')
            if bool(item.annotation.ratings) != (item.annotation.status == 'ANNOTATED'):
                raise ValueError('ANNOTATION_STATE_MISMATCH')
            for rating in item.annotation.ratings:
                if rating.item_id != item.item_id or rating.content_sha256 != expected:
                    raise ValueError('ANNOTATION_CONTENT_MISMATCH')
        return self
