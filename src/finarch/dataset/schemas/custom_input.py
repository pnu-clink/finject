"""Reviewer inputs retain the existing question, context and reference names."""
from decimal import Decimal
import re
from typing import Annotated, Literal
from pydantic import Field, RootModel, ConfigDict, model_validator
from finarch.dataset.schemas.common import StrictModel, Text
from finarch.dataset.schemas.prepared import AnswerMetadata, PreparedSample


class IntermediateSample(StrictModel):
    question: Text
    context: Text
    reference_answer: Text
    reference_precision: Annotated[int, Field(ge=0, le=100)]

    @model_validator(mode='after')
    def valid_reference(self):
        if not self.question.strip() or not self.context.strip():
            raise ValueError('EMPTY_QUESTION_OR_CONTEXT')
        if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?',
                            self.reference_answer):
            raise ValueError('ANSWER_MUST_BE_AN_UNAMBIGUOUS_NUMERIC_TOKEN')
        answer = Decimal(self.reference_answer)
        if not answer.is_finite():
            raise ValueError('NON_FINITE_REFERENCE')
        if max(0, -answer.as_tuple().exponent) != self.reference_precision:
            raise ValueError('REFERENCE_PRECISION_MISMATCH')
        return self


class SourceIdentity(StrictModel):
    name: Text
    sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class CustomProvenance(StrictModel):
    dataset: Literal['custom']
    name: Text
    adapter_sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    sources: Annotated[list[SourceIdentity], Field(min_length=1)]


class CustomAnswerMetadata(AnswerMetadata):
    scale: None = Field(description="This adapter route does not import or infer answer scale")


class CustomPreparedSample(PreparedSample):
    answer_metadata: CustomAnswerMetadata
    provenance: CustomProvenance


class CustomInputsSchema(RootModel[list[CustomPreparedSample]]):
    model_config = ConfigDict(strict=True)

    @model_validator(mode='after')
    def unique_ids(self):
        if not self.root:
            raise ValueError('EMPTY_INPUT_COLLECTION')
        for field in ('id', 'raw_id'):
            values = [getattr(sample, field) for sample in self.root]
            if len(values) != len(set(values)):
                raise ValueError('DUPLICATE_' + field.upper())
        return self
