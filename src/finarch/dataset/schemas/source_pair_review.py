"""Private offline SOURCE/VALUE pairing report, without semantic effect claims."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
from finarch.dataset.schemas.quality_scope import SourceRef

class PairRecord(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: str
    case: str
    source_type: Literal['SOURCE1','SOURCE2']
    source_id: str
    base_id: str
    repeat: Literal[1]=1
    match_status: Literal['MATCHED','EXCLUDED']
    reasons: list[str]
    dependency_source: str | None
    dependency_observation_sha256: str | None
    inverse_matches_base: bool
    value_identity: dict
    claim_location: dict
    responses: dict
    cue_comparison: dict | None
    semantic_effect: Literal['NOT_EVALUATED']='NOT_EVALUATED'
    ab_effect: Literal['UNRESOLVED']='UNRESOLVED'
    references: dict[str,SourceRef]

class PairReport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_version: Literal['source-pair-review-v1']='source-pair-review-v1'
    processor: Literal['offline-python']='offline-python'
    model_calls: Literal[0]=0
    run_id: str
    source_run: str
    records: list[PairRecord]
    summary: dict
    limitations: list[str]
