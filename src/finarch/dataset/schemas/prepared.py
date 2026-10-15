"""Prepared input schema. Source meaning remains unchanged by validation."""
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from pydantic import Field, RootModel, ConfigDict, model_validator
from finarch.shared.reference import Reference
from finarch.dataset.schemas.common import StrictModel, Text, Index, Span

class JsonSource(StrictModel):
    pointer: str = Field(description="JSON Pointer inside the serialized raw context")
    source_span: Span = Field(description="Literal token offsets in the unmodified raw context string")
    raw_text: str
    value_type: Literal["key", "string", "integer", "number", "boolean", "null"]
    decoded_span: Span = Field(description="Displayed fragment offsets within the decoded source token")
    markdown_escaped: bool

class TextLocation(StrictModel):
    id: Text
    text: str
    source_pointer: Text
    context_span: Span
    json_source: JsonSource | None = None

class Cell(TextLocation):
    row: Index
    column: Index

class Table(StrictModel):
    id: Text
    source_pointer: Text
    rows: list[list[str]]
    cells: list[Cell]

class SourceContent(StrictModel):
    paragraphs: list[TextLocation]
    tables: list[Table]

class NumberLocation(StrictModel):
    text: Text
    source_text_span: Span
    context_span: Span

class Segment(TextLocation):
    numbers: list[NumberLocation]

class ContextMapping(StrictModel):
    offset_unit: Literal["Unicode code points"]
    interval: Literal["[start, end)"]
    source_root: Text
    segments: list[Segment]
    number_status: Text

class AnswerMetadata(StrictModel):
    scale: Text | None = Field(description="null means no explicit source scale; not zero")
    negative: bool = Field(description="Explicit minus sign on the reference, including signed zero")

class ProvenanceBase(StrictModel):
    name: Text
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    url: Text
    commit: Text

class FinanceProvenance(ProvenanceBase):
    dataset: Literal["FinanceReasoning-native", "FinanceReasoning-embedded"]
    source_id: Text
    level: Text

class TatqaProvenance(ProvenanceBase):
    dataset: Literal["TAT-QA"]
    document_id: Text

class PreparedSample(StrictModel):
    id: Text
    raw_id: Text
    context: Text
    question: Text
    source_content: SourceContent
    context_mapping: ContextMapping
    reference_answer: Text
    reference_answer_type: Literal["integer", "float"]
    reference_precision: Annotated[int, Field(ge=0, le=100)]
    answer_metadata: AnswerMetadata
    provenance: Annotated[FinanceProvenance | TatqaProvenance, Field(discriminator="dataset")]

    @model_validator(mode="after")
    def consistent_reference(self):
        try:
            Reference(self.reference_answer, self.reference_answer_type, self.reference_precision)
            if self.answer_metadata.negative != Decimal(self.reference_answer).is_signed():
                raise ValueError("REFERENCE_SIGN_MISMATCH")
        except InvalidOperation as error:
            raise ValueError("INVALID_REFERENCE_NUMBER") from error
        return self

    @model_validator(mode="after")
    def valid_locations(self):
        segments = self.context_mapping.segments
        locations = self.source_content.paragraphs + [c for t in self.source_content.tables for c in t.cells]
        for item in [*segments, *locations]:
            start, end = item.context_span
            if not 0 <= start <= end <= len(self.context) or self.context[start:end] != item.text:
                raise ValueError("CONTEXT_LOCATION_MISMATCH")
        for item in segments:
            for number in item.numbers:
                a, b = number.source_text_span
                if not 0 <= a < b <= len(item.text) or item.text[a:b] != number.text:
                    raise ValueError("NUMBER_LOCATION_MISMATCH")
                if number.context_span != [item.context_span[0] + a, item.context_span[0] + b]:
                    raise ValueError("NUMBER_CONTEXT_LOCATION_MISMATCH")
        return self

class PreparedInputsSchema(RootModel[list[PreparedSample]]):
    model_config = ConfigDict(strict=True)

    @model_validator(mode="after")
    def unique_ids(self):
        if not self.root:
            raise ValueError("EMPTY_INPUT_COLLECTION")
        for field in ("id", "raw_id"):
            values = [getattr(s, field) for s in self.root]
            if len(values) != len(set(values)):
                raise ValueError("DUPLICATE_" + field.upper())
        return self
