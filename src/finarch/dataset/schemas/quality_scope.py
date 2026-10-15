"""Versioned offline provenance sidecar; unrelated to the LLM audit contract."""
from typing import Literal
from pydantic import Field, model_validator
from finarch.dataset.schemas.common import StrictModel, Text


class SourceRef(StrictModel):
    path: Text
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class ScopeFinding(StrictModel):
    criterion: Literal['planned_change', 'unintended_change', 'readability']
    judgment: Literal['PASS', 'FAIL', 'UNKNOWN']
    reason: str


class AuditScope(StrictModel):
    version: int | None
    status: str | None
    scope: str | None
    model: str | None
    effort: str | None
    profile_id: str | None
    findings: list[ScopeFinding]
    findings_match_raw: bool | None
    recovery_review: str | None
    full_EA_verdict: str | None
    independent_answer_stage: str | None
    limitation: str | None


class ApprovalScope(StrictModel):
    method: Literal['BULK_AT_USER_DIRECTION', 'UNKNOWN']
    decision: str | None
    reviewer: str | None
    recorded_at: str | None
    reason: str | None
    history_contains_current: bool | None


class IndependentScope(StrictModel):
    status: Literal['NOT_REVIEWED']
    kind: Literal['NONE_DOCUMENTED_IN_SELECTED_EVIDENCE']
    scope: str
    reason: str


class QualityRecord(StrictModel):
    id: Text
    case: Text
    variant: Text
    repeat: None = None
    axis: str | None
    generation_status: str | None
    status: Literal['RECORDED', 'NOT_EVALUATED']
    qc_matches_frozen: bool | None
    audit: AuditScope
    approval: ApprovalScope
    independent_review: IndependentScope
    references: dict[str, SourceRef]
    bounded_recovery_status: Literal['RECOVERABLE', 'UNKNOWN', 'NO_WITNESS_IN_SCOPE'] | None
    skip_reasons: list[str]

    @model_validator(mode='after')
    def grounded(self):
        if self.approval.method == 'BULK_AT_USER_DIRECTION':
            if self.approval.reviewer != 'user-directed-bulk-accept' or 'decision' not in self.references:
                raise ValueError('BULK_PROVENANCE_REQUIRED')
        if self.status == 'RECORDED' and (self.skip_reasons or self.qc_matches_frozen is not True):
            raise ValueError('RECORDED_REQUIRES_MATCHED_EVIDENCE')
        return self


class QualityReport(StrictModel):
    schema_version: Literal['quality-scope-v1']
    rubric_version: Literal['audit-scope-and-approval-provenance-v1']
    run_id: Text
    source_run: Text
    created_at: Text
    processor: Literal['offline-python-adapter']
    model_calls: Literal[0]
    status: Literal['COMPLETE', 'PARTIAL', 'SNAPSHOT_CHANGED']
    records: list[QualityRecord]
    summary: dict[str, int]
    related_reports: dict[str, SourceRef]

    @model_validator(mode='after')
    def unique_records(self):
        if len({r.id for r in self.records}) != len(self.records):
            raise ValueError('DUPLICATE_QUALITY_RECORD')
        if self.summary.get('records') != len(self.records):
            raise ValueError('QUALITY_DENOMINATOR_MISMATCH')
        return self
