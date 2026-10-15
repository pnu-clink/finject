"""Offline public input and private provenance sidecar contracts."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
from finarch.dataset.schemas.quality_scope import SourceRef

class PublicOriginal(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str
    context: str
    question: str

class BaselineRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    status: Literal['PREPARED', 'NOT_PREPARED']
    semantic_review: Literal['NOT_REVIEWED'] = 'NOT_REVIEWED'
    variants: list[str]
    approved_round: str | None
    source_dataset: str | None
    reference: dict
    provenance: dict
    qc_sha256: str | None
    references: dict[str, SourceRef]
    skip_reasons: list[str]

class BaselineReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['original-baseline-v1'] = 'original-baseline-v1'
    processor: Literal['offline-python'] = 'offline-python'
    model_calls: Literal[0] = 0
    run_id: str
    source_run: str
    status: Literal['PREPARED_NOT_RUN', 'PARTIAL_NOT_RUN']
    baseline_execution: Literal['DEFERRED_QWEN_MATCHED_CONDITIONS'] = 'DEFERRED_QWEN_MATCHED_CONDITIONS'
    records: list[BaselineRecord]
    summary: dict[str, int]
    public_manifest: str
    requests_directory: str
    request_settings: dict
    limitations: list[str]
