"""Reviewer adapters: a numeric Q/C/A contract without source-family assumptions."""
from typing import Annotated, Literal
from pydantic import Field, RootModel, ConfigDict, model_validator
from finarch.dataset.schemas.common import StrictModel, Text
from finarch.dataset.schemas.prepared import AnswerMetadata, PreparedSample
from finarch.shared.reference import Reference


class IntermediateSample(StrictModel):
    q: Text
    c: Text
    a: Text
    a_precision: Annotated[int, Field(ge=0, le=100)]
    a_type: Literal['integer', 'float']

    @model_validator(mode='after')
    def valid_reference(self):
        if not self.q.strip() or not self.c.strip():
            raise ValueError('EMPTY_QUESTION_OR_CONTEXT')
        Reference(self.a, self.a_type, self.a_precision)
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
