"""Source repair and arithmetic evidence review contracts."""
from typing import Literal
from pydantic import Field, JsonValue
from finarch.dataset.schemas.common import StrictModel, Text
from finarch.dataset.schemas.llm import Observation


class RevisionRequest(Observation):
    reference_answer: str | None = None
    reference_answer_type: Literal['integer', 'float'] | None = None
    reference_precision: int | None = Field(default=None, ge=0, le=100)

    findings: list[dict[str, JsonValue]]


class TextEdit(StrictModel):
    field: Literal['context', 'question']
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    before: str
    text: str
    reason: Text


class RevisionResponse(StrictModel):
    disposition: Literal['REVISED', 'AMBIGUOUS', 'UNCHANGED']
    edits: list[TextEdit]
    reason: Text


class EvidenceRequest(Observation):
    original_program: dict[str, JsonValue]
    independent_program: dict[str, JsonValue]
    original_result: Text
    independent_result: Text
    gold: Text


class EvidenceCitation(StrictModel):
    field: Literal['context', 'question']
    quote: Text
    reason: Text


class EvidenceResponse(StrictModel):
    conclusion: Literal['POT_ERROR', 'GOLD_ERROR', 'AMBIGUOUS', 'UNRESOLVED']
    evidence: list[EvidenceCitation] = Field(min_length=1)
    reason: Text
