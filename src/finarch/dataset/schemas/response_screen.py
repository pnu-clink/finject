"""Saved offline screening contract; not an LLM response schema."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from finarch.dataset.schemas.quality_scope import SourceRef

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Cue(Strict):
    quote: str
    start: int
    end: int

class Number(Strict):
    quote: str
    start: int
    end: int
    value: str
    unit: str | None
    decimal_places: int
    method: Literal['BARE_NUMBER']

class Comparison(Strict):
    A: str | None
    B: str | None
    A_origin: str = 'plan.original_graph.output.computed'
    B_origin: str = 'plan.execution.exact_value'
    unit: str | None = None
    decimal_places: int | None = None
    match: Literal['A', 'B', 'BOTH', 'NEITHER', 'UNRESOLVED']
    reason: str

class Validity(Strict):
    original: Literal['NOT_REVIEWED'] = 'NOT_REVIEWED'
    perturbation: Literal['INVALID', 'UNKNOWN', 'NOT_REVIEWED']
    reference: Literal['NOT_REVIEWED'] = 'NOT_REVIEWED'
    reason: str

class ScreenRecord(Strict):
    id: str
    case: str
    variant: str
    repeat: Literal[1] = 1
    execution: Literal['COMPLETE', 'TRUNCATED', 'TRANSPORT_ERROR', 'SCHEMA_ERROR', 'MISSING']
    execution_reason: str
    raw_finish_reason: str | None
    raw_content_is_null: bool | None
    answer: str | None
    cues: dict[str, list[Cue]] | None
    behavior_candidates: list[str] | None
    semantic_status: Literal['NOT_REVIEWED', 'NOT_EVALUATED']
    numeric_candidates: list[Number] | None
    comparison: Comparison
    validity: Validity
    references: dict[str, SourceRef]
    skip_reasons: list[str]

class ManualSample(Strict):
    id: str
    source: SourceRef
    quote: str
    method: Literal['BOUNDED_AGENT_INSPECTION']
    scope: Literal['CUE_EXTRACTION_AND_EXECUTION_ONLY']
    semantic_verdict: Literal['UNKNOWN', 'NOT_EVALUATED']
    note: str

class ScreenReport(Strict):
    schema_version: Literal['response-screen-v2'] = 'response-screen-v2'
    rubric_version: Literal['bounded-cues-bare-number-v1'] = 'bounded-cues-bare-number-v1'
    processor: Literal['offline-python'] = 'offline-python'
    model_calls: Literal[0] = 0
    run_id: str
    source_run: str
    created_at: str
    records: list[ScreenRecord]
    summary: dict[str, int]
    manual_samples: list[ManualSample] = Field(max_length=10)
    limitations: list[str]
    related_reports: dict[str, SourceRef]
